"""
Rust 編譯器整合 — 呼叫 rustc 取得真正的借用檢查結果。

使用方式：
  POST /api/rust/check  { "code": "...", "edition": "2021" }

回傳：
  {
    "available": true/false,
    "errors": [{ "line", "col", "message", "level", "code", "snippet" }],
    "success": true/false
  }
"""
from __future__ import annotations
import json, os, shutil, subprocess, sys, tempfile

_RUSTC = None

def _find_rustc() -> str | None:
    global _RUSTC
    if _RUSTC:
        return _RUSTC
    for candidate in ('rustc', os.path.expanduser('~/.cargo/bin/rustc')):
        if shutil.which(candidate):
            _RUSTC = candidate
            return _RUSTC
    return None

def is_available() -> bool:
    return _find_rustc() is not None

def check(code: str, edition: str = '2021') -> dict:
    rustc = _find_rustc()
    if not rustc:
        return {'available': False, 'errors': [], 'success': None,
                'hint': '請安裝 Rust：https://rustup.rs/'}

    with tempfile.NamedTemporaryFile(suffix='.rs', mode='w', delete=False,
                                      encoding='utf-8') as f:
        f.write(code)
        tmp = f.name

    try:
        result = subprocess.run(
            [rustc,
             '--error-format=json',
             f'--edition={edition}',
             '--crate-type=bin',
             '-o', os.devnull,
             tmp],
            capture_output=True, text=True, timeout=30
        )
    except subprocess.TimeoutExpired:
        os.unlink(tmp)
        return {'available': True, 'errors': [], 'success': False, 'hint': '編譯逾時'}
    finally:
        try: os.unlink(tmp)
        except: pass

    errors = []
    for raw_line in result.stderr.split('\n'):
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        try:
            msg = json.loads(raw_line)
        except json.JSONDecodeError:
            continue

        level = msg.get('level', '')
        if level not in ('error', 'warning', 'error[E]'):
            continue

        message  = msg.get('message', '')
        err_code = (msg.get('code') or {}).get('code', '')
        rendered = msg.get('rendered', '')

        for span in msg.get('spans', []):
            if not span.get('is_primary'):
                continue
            errors.append({
                'line':    span.get('line_start', 0),
                'col':     span.get('column_start', 1),
                'end_line':span.get('line_end', span.get('line_start', 0)),
                'end_col': span.get('column_end', 1),
                'message': message,
                'level':   level,
                'code':    err_code,          # e.g. "E0502"
                'label':   span.get('label', ''),
                'snippet': span.get('text', [{}])[0].get('text', '')[:80],
            })

        # If no primary span, still report with line 0
        if not msg.get('spans') and level == 'error':
            errors.append({
                'line': 0, 'col': 1, 'end_line': 0, 'end_col': 1,
                'message': message, 'level': level,
                'code': err_code, 'label': '', 'snippet': rendered[:120],
            })

    return {
        'available': True,
        'errors':    errors,
        'success':   result.returncode == 0,
        'edition':   edition,
    }
