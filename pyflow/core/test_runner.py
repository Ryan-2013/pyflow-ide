"""
測試執行器 — 整合 pytest / go test / cargo test。

回傳格式：
{
  'ok': bool,
  'summary': { 'passed': int, 'failed': int, 'skipped': int, 'errors': int, 'duration': float },
  'results': [
    {
      'name': str,       # 測試名稱
      'status': str,     # 'passed' | 'failed' | 'error' | 'skipped'
      'duration': float, # 秒
      'file': str,       # 檔案路徑（可選）
      'line': int,       # 行號（可選）
      'message': str,    # 失敗訊息（可選）
    }
  ],
  'output': str,         # 原始輸出
  'error': str | None,   # 執行錯誤
}
"""
from __future__ import annotations
import json, os, re, shutil, subprocess, sys, time
from pathlib import Path


# ── 工具函式 ──────────────────────────────────────────────────────

def _run(cmd: list, cwd: str, timeout: int = 120) -> tuple[str, str, int, float]:
    """回傳 (stdout, stderr, returncode, duration)"""
    t0 = time.time()
    try:
        r = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True,
            timeout=timeout, encoding='utf-8', errors='replace',
        )
        return r.stdout, r.stderr, r.returncode, time.time() - t0
    except subprocess.TimeoutExpired:
        return '', f'測試逾時（>{timeout}s）', 1, time.time() - t0
    except FileNotFoundError:
        return '', f'找不到指令：{cmd[0]}', 1, time.time() - t0


def _empty_result(error: str) -> dict:
    return {
        'ok': False,
        'summary': {'passed': 0, 'failed': 0, 'skipped': 0, 'errors': 0, 'duration': 0},
        'results': [],
        'output': '',
        'error': error,
    }


# ── Python / pytest ───────────────────────────────────────────────

def run_pytest(path: str) -> dict:
    """
    執行 pytest。
    優先使用 --json-report（若有安裝），否則解析文字輸出。
    """
    target = Path(path)
    cwd    = str(target.parent if target.is_file() else target)
    py     = sys.executable

    # 嘗試 JSON 模式（需要 pytest-json-report）
    has_json = subprocess.run(
        [py, '-m', 'pytest', '--co', '-q', '--json-report', '--help'],
        capture_output=True, timeout=5,
    ).returncode == 0

    if has_json:
        tmp = Path(cwd) / '.pyflow_test_report.json'
        cmd = [py, '-m', 'pytest', str(path), '-v',
               '--json-report', f'--json-report-file={tmp}',
               '--no-header', '-q', '--tb=short']
        stdout, stderr, rc, dur = _run(cmd, cwd)
        if tmp.exists():
            try:
                raw = json.loads(tmp.read_text())
                tmp.unlink()
                return _parse_pytest_json(raw, dur)
            except Exception:
                tmp.unlink(missing_ok=True)

    # Fallback：解析文字輸出
    cmd = [py, '-m', 'pytest', str(path), '-v', '--tb=short', '--no-header']
    stdout, stderr, rc, dur = _run(cmd, cwd)
    if not stdout and not stderr:
        return _empty_result('pytest 沒有輸出，請確認已安裝 pytest')
    return _parse_pytest_text(stdout + stderr, rc, dur)


def _parse_pytest_json(raw: dict, dur: float) -> dict:
    summary = raw.get('summary', {})
    results = []
    for t in raw.get('tests', []):
        node = t.get('nodeid', '')
        status = t.get('outcome', 'unknown')
        if status == 'passed': status = 'passed'
        elif status == 'failed': status = 'failed'
        elif status == 'skipped': status = 'skipped'
        else: status = 'error'
        msg = ''
        if status in ('failed','error'):
            call = t.get('call', {})
            msg = call.get('longrepr', call.get('crash', {}).get('message', ''))
            if isinstance(msg, dict): msg = msg.get('message', '')
        results.append({
            'name': node,
            'status': status,
            'duration': t.get('call', {}).get('duration', 0),
            'file': t.get('nodeid','').split('::')[0],
            'line': t.get('lineno', 0),
            'message': str(msg)[:300],
        })
    return {
        'ok': summary.get('failed', 1) == 0 and summary.get('error', 0) == 0,
        'summary': {
            'passed':  summary.get('passed', 0),
            'failed':  summary.get('failed', 0),
            'skipped': summary.get('skipped', 0),
            'errors':  summary.get('error', 0),
            'duration': dur,
        },
        'results': results,
        'output': '',
        'error': None,
    }


def _parse_pytest_text(out: str, rc: int, dur: float) -> dict:
    """
    解析 pytest -v 文字輸出。
    格式：  test_file.py::test_name PASSED [ 50%]
             test_file.py::test_name FAILED
    """
    results = []
    summary = {'passed': 0, 'failed': 0, 'skipped': 0, 'errors': 0, 'duration': dur}
    
    # 每一行測試結果
    line_re = re.compile(r'^([\w/\\.-]+::[\w\[\]-]+(?:\[.*?\])?)\s+(PASSED|FAILED|ERROR|SKIPPED|XFAILED|XPASSED)', re.M)
    fail_msgs: dict[str, str] = {}
    
    # 提取失敗訊息塊（簡化版）
    fail_block_re = re.compile(r'FAILED ([\w/\\.-]+::[\w\[\]-]+).*?(?=\n(?:FAILED|PASSED|=)|\Z)', re.S)
    for m in fail_block_re.finditer(out):
        fail_msgs[m.group(1)] = m.group(0)[:200]

    for m in line_re.finditer(out):
        name, status_raw = m.group(1), m.group(2)
        status = 'passed' if 'PASSED' in status_raw else \
                 'failed' if 'FAILED' in status_raw else \
                 'skipped' if 'SKIPPED' in status_raw else 'error'
        parts = name.split('::')
        results.append({
            'name': name,
            'status': status,
            'duration': 0,
            'file': parts[0],
            'line': 0,
            'message': fail_msgs.get(name, '')[:200],
        })
        summary[status if status in summary else 'errors'] += 1

    # Fallback: 底部摘要行 "5 passed, 2 failed in 1.23s"
    if not results:
        sm = re.search(r'(\d+) passed', out)
        fm = re.search(r'(\d+) failed', out)
        em = re.search(r'(\d+) error', out)
        sk = re.search(r'(\d+) skipped', out)
        summary['passed']  = int(sm.group(1)) if sm else 0
        summary['failed']  = int(fm.group(1)) if fm else 0
        summary['errors']  = int(em.group(1)) if em else 0
        summary['skipped'] = int(sk.group(1)) if sk else 0

    return {
        'ok': rc == 0,
        'summary': summary,
        'results': results,
        'output': out[-3000:],
        'error': None,
    }


# ── Go test ───────────────────────────────────────────────────────

def run_go_test(path: str) -> dict:
    if not shutil.which('go'):
        return _empty_result('找不到 go 指令，請安裝 Go')

    target = Path(path)
    cwd = str(target.parent if target.is_file() else target)

    # 找 go.mod 所在（module root）
    p = Path(cwd)
    while p != p.parent:
        if (p / 'go.mod').exists():
            cwd = str(p); break
        p = p.parent

    cmd  = ['go', 'test', '-v', '-json', '-count=1', './...']
    stdout, stderr, rc, dur = _run(cmd, cwd)

    if not stdout:
        return _empty_result(stderr or 'go test 無輸出')
    return _parse_go_test_json(stdout, stderr, rc, dur)


def _parse_go_test_json(stdout: str, stderr: str, rc: int, dur: float) -> dict:
    results = []
    summary = {'passed': 0, 'failed': 0, 'skipped': 0, 'errors': 0, 'duration': dur}
    msgs: dict[str, list[str]] = {}

    for line in stdout.split('\n'):
        line = line.strip()
        if not line: continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        action = ev.get('Action', '')
        test   = ev.get('Test', '')
        pkg    = ev.get('Package', '')
        if not test: continue

        name = f'{pkg}/{test}' if pkg else test
        if action in ('pass', 'fail', 'skip'):
            status = {'pass':'passed','fail':'failed','skip':'skipped'}.get(action,'error')
            results.append({
                'name': name,
                'status': status,
                'duration': ev.get('Elapsed', 0),
                'file': pkg,
                'line': 0,
                'message': '\n'.join(msgs.pop(name, []))[-200:],
            })
            summary[status if status in summary else 'errors'] += 1
        elif action == 'output':
            msgs.setdefault(name, []).append(ev.get('Output','').rstrip())

    return {
        'ok': rc == 0,
        'summary': summary,
        'results': results,
        'output': (stdout + stderr)[-3000:],
        'error': None,
    }


# ── Rust / cargo test ─────────────────────────────────────────────

def run_cargo_test(path: str) -> dict:
    if not shutil.which('cargo'):
        return _empty_result('找不到 cargo 指令，請安裝 Rust')

    target = Path(path)
    cwd = str(target.parent if target.is_file() else target)

    # 找 Cargo.toml
    p = Path(cwd)
    while p != p.parent:
        if (p / 'Cargo.toml').exists():
            cwd = str(p); break
        p = p.parent

    cmd = ['cargo', 'test', '--color=never', '--', '--format=terse']
    stdout, stderr, rc, dur = _run(cmd, cwd, timeout=180)
    output = stdout + stderr
    return _parse_cargo_output(output, rc, dur)


def _parse_cargo_output(out: str, rc: int, dur: float) -> dict:
    results = []
    summary = {'passed': 0, 'failed': 0, 'skipped': 0, 'errors': 0, 'duration': dur}

    # terse format: "test module::name ... ok" or "... FAILED"
    line_re = re.compile(r'^test ([\w:]+) \.\.\. (ok|FAILED|ignored)', re.M)
    
    # Collect failure details
    fail_section = re.search(r'failures:\n(.*?)(?:\ntest result|\Z)', out, re.S)
    fail_text = fail_section.group(1) if fail_section else ''
    fail_msgs: dict[str, str] = {}
    for m in re.finditer(r'---- ([\w:]+) stdout ----\n(.*?)(?=---- |\Z)', fail_text, re.S):
        fail_msgs[m.group(1)] = m.group(2)[:200]

    for m in line_re.finditer(out):
        name, status_raw = m.group(1), m.group(2)
        status = 'passed' if status_raw == 'ok' else \
                 'skipped' if status_raw == 'ignored' else 'failed'
        results.append({
            'name': name,
            'status': status,
            'duration': 0,
            'file': '',
            'line': 0,
            'message': fail_msgs.get(name, '')[:200],
        })
        summary[status if status in summary else 'errors'] += 1

    # Fallback from summary line: "test result: ok. 5 passed; 2 failed"
    sm = re.search(r'(\d+) passed', out)
    fm = re.search(r'(\d+) failed', out)
    sk = re.search(r'(\d+) ignored', out)
    if not results:
        summary['passed']  = int(sm.group(1)) if sm else 0
        summary['failed']  = int(fm.group(1)) if fm else 0
        summary['skipped'] = int(sk.group(1)) if sk else 0

    return {
        'ok': rc == 0,
        'summary': summary,
        'results': results,
        'output': out[-3000:],
        'error': None if rc == 0 else (re.search(r'error\[.*?\].*', out) or type('',(),{'group':lambda s,i:'build error'})()).group(0)[:100],
    }


# ── Main dispatcher ───────────────────────────────────────────────

def run_tests(path: str, lang: str) -> dict:
    """
    執行對應語言的測試。
    lang: 'python' | 'go' | 'rust'
    """
    if lang == 'go':    return run_go_test(path)
    if lang == 'rust':  return run_cargo_test(path)
    return run_pytest(path)
