"""
PyFlow 執行軌跡追蹤器
======================
透過 sys.settrace() 記錄 Python 程式的實際執行路徑，
並對應到流程圖節點，形成「動態執行視覺化」。

用法：
  後端以 subprocess 執行目標腳本 + 注入追蹤程式
  追蹤結果寫入臨時 JSON，回傳給前端
  前端把命中的節點在流程圖上高亮
"""
from __future__ import annotations
import json, os, subprocess, sys, tempfile
from pathlib import Path

# ── 注入的追蹤程式碼 ──────────────────────────────────────────────
_TRACER_CODE = r"""
import sys, json, atexit, os, time

_hits      = {}   # "file:line" → count
_fn_hits   = {}   # fn_name → count
_fn_times  = {}   # fn_name → ms
_fn_starts = {}   # id(frame) → perf_counter
_tgt_file  = os.environ.get('PYFLOW_TRACE_SCRIPT', '')
_out_file  = os.environ.get('PYFLOW_TRACE_OUTPUT', '/tmp/pyflow_trace.json')

def _trace(frame, event, arg):
    ffile = frame.f_code.co_filename
    # Only trace the target file (skip stdlib / site-packages)
    if _tgt_file and not ffile.endswith(_tgt_file) and _tgt_file not in ffile:
        return _trace
    if '/site-packages/' in ffile or '<frozen' in ffile:
        return _trace

    fname = frame.f_code.co_name
    if event == 'call':
        _fn_hits[fname] = _fn_hits.get(fname, 0) + 1
        _fn_starts[id(frame)] = time.perf_counter()
        return _trace
    elif event == 'return':
        start = _fn_starts.pop(id(frame), None)
        if start is not None:
            elapsed = (time.perf_counter() - start) * 1000
            _fn_times[fname] = _fn_times.get(fname, 0.0) + elapsed
    elif event == 'line':
        key = f'{ffile}:{frame.f_lineno}'
        _hits[key] = _hits.get(key, 0) + 1
    return _trace

def _save():
    with open(_out_file, 'w') as f:
        json.dump({'hits': _hits, 'fn_hits': _fn_hits,
                   'fn_times': _fn_times}, f)

atexit.register(_save)
sys.settrace(_trace)
"""

_RUNNER_CODE = r"""
import runpy, sys, os
target = os.environ.get('PYFLOW_TRACE_SCRIPT', '')
if target:
    sys.argv = [target]
    runpy.run_path(target, run_name='__main__')
"""


def run_with_trace(path: str, args: list | None = None,
                   timeout: int = 30) -> dict:
    """
    Execute path with sys.settrace() instrumentation.

    Returns:
    {
      "ok": bool,
      "hits": {"file:line": count},      # line-level execution counts
      "fn_hits": {"fn_name": count},     # function call counts
      "fn_times": {"fn_name": ms},       # function cumulative time (ms)
      "stdout": str,
      "stderr": str,
      "error": str | None,
    }
    """
    path = os.path.abspath(path)
    if not os.path.isfile(path):
        return {'ok': False, 'hits': {}, 'fn_hits': {}, 'fn_times': {},
                'stdout': '', 'stderr': '', 'error': 'File not found'}

    # Write combined tracer + runner to a temp file
    combined = _TRACER_CODE + '\n' + _RUNNER_CODE
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py',
                                     delete=False, encoding='utf-8') as tf:
        tf.write(combined)
        tracer_path = tf.name

    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as of:
        output_path = of.name

    env = {**os.environ,
           'PYFLOW_TRACE_SCRIPT': path,
           'PYFLOW_TRACE_OUTPUT': output_path,
           'PYTHONDONTWRITEBYTECODE': '1'}
    if args:
        env['PYFLOW_TRACE_ARGS'] = json.dumps(args)

    try:
        r = subprocess.run(
            [sys.executable, tracer_path],
            capture_output=True, text=True,
            timeout=timeout, env=env,
            cwd=os.path.dirname(path),
        )
        # Read trace output
        trace_data: dict = {}
        try:
            if os.path.exists(output_path):
                trace_data = json.loads(Path(output_path).read_text())
        except Exception:
            pass

        return {
            'ok':       r.returncode == 0,
            'hits':     trace_data.get('hits', {}),
            'fn_hits':  trace_data.get('fn_hits', {}),
            'fn_times': trace_data.get('fn_times', {}),
            'stdout':   r.stdout[-4000:],
            'stderr':   r.stderr[-2000:],
            'error':    None if r.returncode == 0 else r.stderr[-500:],
        }
    except subprocess.TimeoutExpired:
        return {'ok': False, 'hits': {}, 'fn_hits': {}, 'fn_times': {},
                'stdout': '', 'stderr': '', 'error': f'執行逾時（>{timeout}s）'}
    except Exception as e:
        return {'ok': False, 'hits': {}, 'fn_hits': {}, 'fn_times': {},
                'stdout': '', 'stderr': '', 'error': str(e)}
    finally:
        try: os.unlink(tracer_path)
        except: pass
        try: os.unlink(output_path)
        except: pass


def map_trace_to_nodes(trace: dict, flow_nodes: list,
                       fn_defs: list, file_path: str) -> dict:
    """
    Map line-level hits to flow nodes and definition nodes.

    Returns:
    {
      "node_hits": {"node_id": {"count": int, "time_ms": float}},
      "line_hits": {"line_no": count},
      "total_fn_calls": int,
    }
    """
    file_path = os.path.abspath(file_path)
    fname     = os.path.basename(file_path)

    # Normalize hits: extract lines for THIS file
    line_hits: dict[int, int] = {}
    for key, count in trace.get('hits', {}).items():
        try:
            file_part, line_part = key.rsplit(':', 1)
            if file_path in file_part or fname in file_part:
                line_hits[int(line_part)] = count
        except (ValueError, IndexError):
            pass

    fn_hits  = trace.get('fn_hits', {})
    fn_times = trace.get('fn_times', {})

    # Map to flow nodes by line number
    node_hits: dict[str, dict] = {}
    for node in flow_nodes:
        nid  = node.get('id', '')
        line = node.get('line', 0)
        if line and line in line_hits:
            node_hits[nid] = {
                'count':   line_hits[line],
                'time_ms': 0.0,
            }

    # Map to definition nodes by function name
    for defn in fn_defs:
        did   = defn.get('id', '')
        label = defn.get('label', did)
        for key in (did, label, did.split('.')[-1]):
            if key in fn_hits:
                node_hits[did] = {
                    'count':   fn_hits[key],
                    'time_ms': fn_times.get(key, 0.0),
                }
                break

    total = sum(fn_hits.values())
    return {
        'node_hits':      node_hits,
        'line_hits':      line_hits,
        'total_fn_calls': total,
    }
