"""
Module inspector — 用 Python 內建 inspect 模組在執行期擷取
任何已安裝模組的函式、類別、方法及其簽名。

支援：
  import os              → os.getcwd, os.listdir, os.path …
  from pathlib import Path → Path.read_text, Path.exists …
  import numpy as np     → np.array, np.zeros, np.mean …
"""
from __future__ import annotations
import importlib
import inspect
import sys
import re
from functools import lru_cache
from typing import Any

# 白名單：標準函式庫 + 常見第三方套件
# 防止用戶輸入惡意模組名稱並執行任意程式
_STDLIB_NAMES: frozenset[str] | None = None

def _is_allowed(module_name: str) -> bool:
    """Allow stdlib + known safe third-party packages."""
    global _STDLIB_NAMES
    root = module_name.split('.')[0]
    
    # Python 3.10+ has sys.stdlib_module_names
    if _STDLIB_NAMES is None:
        if hasattr(sys, 'stdlib_module_names'):
            _STDLIB_NAMES = sys.stdlib_module_names
        else:
            # Fallback for older Python
            _STDLIB_NAMES = frozenset(sys.builtin_module_names) | frozenset({
                'abc','ast','asyncio','base64','binascii','builtins','cgi',
                'collections','colorsys','concurrent','contextlib','copy',
                'csv','dataclasses','datetime','decimal','difflib','email',
                'enum','fnmatch','fractions','functools','glob','gzip',
                'hashlib','heapq','hmac','html','http','imaplib','importlib',
                'inspect','io','ipaddress','itertools','json','logging',
                'math','multiprocessing','numbers','operator','os','pathlib',
                'pickle','platform','pprint','queue','random','re','shutil',
                'signal','socket','sqlite3','ssl','stat','statistics','string',
                'struct','subprocess','sys','tempfile','textwrap','threading',
                'time','timeit','traceback','typing','unicodedata','unittest',
                'urllib','uuid','warnings','weakref','xml','xmlrpc','zipfile',
                'zlib',
            })
    
    THIRD_PARTY = frozenset({
        'numpy','pandas','scipy','matplotlib','sklearn','tensorflow','torch',
        'keras','flask','fastapi','django','requests','aiohttp','httpx',
        'pydantic','sqlalchemy','alembic','celery','redis','pymongo',
        'boto3','botocore','yaml','toml','dotenv','click','typer',
        'rich','tqdm','pillow','PIL','cv2','imageio','PyQt5','PyQt6',
        'tkinter','wx','gi','pygments','jinja2','markupsafe','werkzeug',
        'cryptography','paramiko','fabric','invoke','nox','pytest',
        'hypothesis','attrs','attr','cattrs','msgpack','protobuf',
        'grpc','websockets','socketio','uvicorn','gunicorn','starlette',
    })
    
    return root in _STDLIB_NAMES or root in THIRD_PARTY

# ── 型別名稱格式化 ────────────────────────────────────────────────

def _type_name(ann: Any) -> str | None:
    if ann is inspect.Parameter.empty or ann is inspect.Signature.empty:
        return None
    if isinstance(ann, str):
        return ann
    if hasattr(ann, '__name__'):
        return ann.__name__
    s = str(ann)
    # Clean up typing hints: typing.Optional[str] → Optional[str]
    s = re.sub(r'typing\.', '', s)
    s = re.sub(r'<class \'(.+?)\'>', r'\1', s)
    return s[:40]

# ── 函式簽名提取 ─────────────────────────────────────────────────

def _get_callable_info(obj: Any, display_name: str) -> tuple[str, list[str], str | None]:
    """
    Returns (signature_string, params_list, return_type).
    """
    try:
        sig = inspect.signature(obj)
    except (ValueError, TypeError):
        return f'{display_name}(...)', [], None
    
    params: list[str] = []
    for pname, p in list(sig.parameters.items())[:8]:
        if pname in ('self', 'cls'):
            continue
        ann_str = _type_name(p.annotation)
        ann = f': {ann_str}' if ann_str else ''
        
        if p.kind is p.VAR_POSITIONAL:
            params.append(f'*{pname}')
        elif p.kind is p.VAR_KEYWORD:
            params.append(f'**{pname}')
        elif p.default is not p.empty:
            try:
                default = repr(p.default)[:20]
            except Exception:
                default = '...'
            params.append(f'{pname}{ann}={default}')
        else:
            params.append(f'{pname}{ann}')
    
    if len(list(sig.parameters.items())) > 8:
        params.append('…')
    
    ret = _type_name(sig.return_annotation)
    sig_str = f'{display_name}({", ".join(params)})' + (f' -> {ret}' if ret else '')
    return sig_str, params, ret

# ── 主要入口 ──────────────────────────────────────────────────────

@lru_cache(maxsize=64)
def inspect_module(module_name: str, specific_names: tuple[str, ...] | None = None) -> tuple[dict, ...]:
    """
    Inspect a Python module; returns a tuple of symbol dicts (hashable for LRU cache).
    """
    if not _is_allowed(module_name):
        return ()
    
    try:
        mod = importlib.import_module(module_name)
    except Exception:
        return ()
    
    names_to_check = list(specific_names) if specific_names else [
        n for n in dir(mod)
        if not n.startswith('_')
        # Skip all-caps C kernel constants (e.g. CLONE_*, GRND_*, RLIMIT_*)
        and not (n.isupper() and '_' in n)
    ]
    
    symbols: list[dict] = []
    
    for name in names_to_check[:300]:
        if name.startswith('_'):
            continue
        try:
            obj = getattr(mod, name)
        except AttributeError:
            continue
        
        doc_raw = inspect.getdoc(obj) or ''
        doc = doc_raw.split('\n')[0][:100]
        
        if inspect.isfunction(obj) or inspect.isbuiltin(obj) or (
            callable(obj) and not inspect.isclass(obj) and not inspect.ismodule(obj)
        ):
            sig_str, params, ret = _get_callable_info(obj, f'{module_name}.{name}')
            symbols.append({
                'name':   name,
                'fqname': f'{module_name}.{name}',   # fully qualified
                'kind':   'function',
                'sig':    sig_str,
                'params': params,
                'ret':    ret,
                'doc':    doc,
                'source': 'module',
                'module': module_name,
                'parent': None,
            })
        
        elif inspect.isclass(obj):
            class_sig = f'{module_name}.{name}'
            symbols.append({
                'name':   name,
                'fqname': f'{module_name}.{name}',
                'kind':   'class',
                'sig':    class_sig,
                'params': [],
                'ret':    None,
                'doc':    doc,
                'source': 'module',
                'module': module_name,
                'parent': None,
            })
            # Class methods (public, non-dunder)
            for mname in sorted(dir(obj)):
                if mname.startswith('_'):
                    continue
                try:
                    m_obj = getattr(obj, mname)
                    if not callable(m_obj):
                        continue
                    m_sig, m_params, m_ret = _get_callable_info(
                        m_obj, f'{module_name}.{name}.{mname}'
                    )
                    m_doc = (inspect.getdoc(m_obj) or '').split('\n')[0][:80]
                    symbols.append({
                        'name':   mname,
                        'fqname': f'{module_name}.{name}.{mname}',
                        'kind':   'method',
                        'sig':    m_sig,
                        'params': m_params,
                        'ret':    m_ret,
                        'doc':    m_doc,
                        'source': 'module',
                        'module': module_name,
                        'parent': name,        # e.g. 'Path'
                        'class':  name,
                    })
                except Exception:
                    pass
        
        elif inspect.ismodule(obj):
            symbols.append({
                'name':   name,
                'fqname': f'{module_name}.{name}',
                'kind':   'module',
                'sig':    f'module {module_name}.{name}',
                'params': [],
                'ret':    None,
                'doc':    doc,
                'source': 'module',
                'module': module_name,
                'parent': None,
            })
        
        else:
            # Constants / attributes
            try:
                val = str(repr(obj))[:30]
            except Exception:
                val = '...'
            symbols.append({
                'name':   name,
                'fqname': f'{module_name}.{name}',
                'kind':   'variable',
                'sig':    f'{module_name}.{name} = {val}',
                'params': [],
                'ret':    None,
                'doc':    doc,
                'source': 'module',
                'module': module_name,
                'parent': None,
            })
    
    return tuple(symbols)


def inspect_import(import_stmt: str) -> list[dict]:
    """
    Given an import statement string, return all relevant symbols.
    
    Handles:
      'import os'            → all os.* members
      'import os.path'       → all os.path.* members
      'from pathlib import Path'    → all Path methods
      'from os import path, getcwd' → path.* + getcwd
    """
    results: list[dict] = []
    
    # from X import Y, Z
    m = re.match(r'^from\s+([\w.]+)\s+import\s+(.+?)(?:\s*#|$)', import_stmt)
    if m:
        mod_name, names_str = m.group(1), m.group(2).strip()
        names_str = names_str.strip('()')
        imported_names: list[str] = []
        for part in names_str.split(','):
            parts = part.strip().split(' as ')
            imported_names.append(parts[0].strip())
        
        # Get the module
        base_syms = inspect_module(mod_name)
        
        for iname in imported_names:
            # Find the object directly imported
            matching = [s for s in base_syms if s['name'] == iname]
            results.extend(matching)
            
            # Also find its sub-members if it's a class or module
            sub = [s for s in base_syms if s.get('parent') == iname or s.get('class') == iname]
            results.extend(sub)
            
            # If not found in base, try importing sub-module
            if not matching:
                sub_mod = f'{mod_name}.{iname}'
                sub_syms = inspect_module(sub_mod)
                results.extend(sub_syms)
        
        return results
    
    # import X or import X as Y
    m2 = re.match(r'^import\s+([\w.]+)(?:\s+as\s+(\w+))?', import_stmt)
    if m2:
        mod_name = m2.group(1)
        syms = inspect_module(mod_name)
        results.extend(syms)
        
        # If there's an alias, duplicate with alias as module name
        alias = m2.group(2)
        if alias:
            aliased = []
            for s in syms:
                if s['parent'] is None and s['module'] == mod_name:
                    s2 = dict(s)
                    s2['module'] = alias
                    s2['fqname'] = s['fqname'].replace(mod_name, alias, 1)
                    aliased.append(s2)
            results.extend(aliased)
    
    return results
