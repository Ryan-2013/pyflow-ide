"""
程式碼格式化器 — 呼叫各語言的官方格式化工具。
  Python → black (python -m black)
  Go     → gofmt
  Rust   → rustfmt
若工具不存在，回傳原始程式碼並附上提示。
"""
from __future__ import annotations
import os, shutil, subprocess, sys, tempfile


def _run(cmd: list[str], code: str, stdin_code: bool = True,
         cwd: str | None = None, timeout: int = 15) -> tuple[str, str | None]:
    """
    執行格式化工具，傳回 (formatted_code, error_message)。
    stdin_code=True  → 透過 stdin 傳入程式碼（不需要暫存檔）
    stdin_code=False → code 是暫存檔路徑，直接執行
    """
    try:
        if stdin_code:
            result = subprocess.run(
                cmd, input=code, capture_output=True, text=True,
                timeout=timeout, cwd=cwd,
            )
            formatted = result.stdout if result.returncode == 0 else code
            err = result.stderr.strip() if result.returncode != 0 and result.stderr else None
        else:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd,
            )
            formatted = open(code, encoding='utf-8').read()  # code = tmp file path
            err = result.stderr.strip() if result.returncode != 0 and result.stderr else None
        return formatted, err
    except FileNotFoundError:
        return code, f'找不到工具 {cmd[0]!r}，請先安裝'
    except subprocess.TimeoutExpired:
        return code, '格式化逾時（>15s）'
    except Exception as e:
        return code, str(e)


def format_python(code: str) -> dict:
    """用 black 格式化 Python，不需要安裝 black 為系統指令。"""
    # Try: python -m black -
    formatted, err = _run([sys.executable, '-m', 'black', '-q', '-'], code)
    if err and '沒有模組' not in err and 'No module' not in err.lower():
        return {'formatted': formatted, 'error': err, 'tool': 'black'}
    if err and ('No module' in err or 'no module' in err.lower()):
        # Try system black
        if shutil.which('black'):
            formatted, err = _run(['black', '-q', '-'], code)
        else:
            return {
                'formatted': code,
                'error': 'black 未安裝，請執行：pip install black',
                'tool': 'black',
            }
    return {'formatted': formatted, 'error': err, 'tool': 'black'}


def format_go(code: str) -> dict:
    """用 gofmt 格式化 Go（支援 stdin）。"""
    if not shutil.which('gofmt'):
        return {'formatted': code, 'error': 'gofmt 未找到，請安裝 Go', 'tool': 'gofmt'}
    formatted, err = _run(['gofmt'], code)
    return {'formatted': formatted, 'error': err, 'tool': 'gofmt'}


def format_rust(code: str) -> dict:
    """用 rustfmt 格式化 Rust（需要暫存檔）。"""
    if not shutil.which('rustfmt'):
        return {'formatted': code, 'error': 'rustfmt 未找到，請安裝 Rust', 'tool': 'rustfmt'}
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(suffix='.rs', mode='w',
                                         delete=False, encoding='utf-8') as f:
            f.write(code)
            tmp = f.name
        formatted, err = _run(['rustfmt', '--edition', '2021', tmp],
                              tmp, stdin_code=False)
        return {'formatted': formatted, 'error': err, 'tool': 'rustfmt'}
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)


FORMATTERS = {
    'python':     format_python,
    'go':         format_go,
    'rust':       format_rust,
    # Aliases
    'py':         format_python,
    'rs':         format_rust,
}


def format_code(code: str, lang: str) -> dict:
    """
    統一入口，按語言呼叫對應格式化器。
    回傳 {'formatted': str, 'error': str|None, 'tool': str}
    """
    fn = FORMATTERS.get(lang.lower())
    if fn is None:
        return {'formatted': code, 'error': f'不支援 {lang!r} 的格式化', 'tool': ''}
    return fn(code)
