"""
符號提取器 — 為 IntelliSense、懸停提示、自動補全提供資料。

支援：Python / Go / Rust
輸出每個符號：name, kind, signature, params, return_type, doc, line, source, parent
"""
from __future__ import annotations
import re

# ── Python 內建符號 ─────────────────────────────────────────────

PY_BUILTINS: list[dict] = [
    # I/O
    {'name':'print',     'sig':'print(*values, sep=" ", end="\\n", file=None, flush=False)', 'params':['*values', 'sep=" "', 'end="\\n"'], 'ret':None, 'doc':'將 values 輸出到文字串流，預設換行。'},
    {'name':'input',     'sig':'input(prompt="") -> str', 'params':['prompt=""'], 'ret':'str', 'doc':'從標準輸入讀取一行（不含換行）。'},
    {'name':'open',      'sig':'open(file, mode="r", encoding=None, errors=None)', 'params':['file','mode="r"','encoding=None'], 'ret':'IO', 'doc':'開啟檔案，傳回檔案物件。'},
    # 類型
    {'name':'int',       'sig':'int(x=0, base=10) -> int', 'params':['x=0','base=10'], 'ret':'int', 'doc':'整數轉換/建構。'},
    {'name':'str',       'sig':'str(object="") -> str',    'params':['object=""'], 'ret':'str', 'doc':'字串轉換/建構。'},
    {'name':'float',     'sig':'float(x=0.0) -> float',   'params':['x=0.0'], 'ret':'float', 'doc':'浮點數轉換/建構。'},
    {'name':'bool',      'sig':'bool(x=False) -> bool',   'params':['x=False'], 'ret':'bool', 'doc':'布林值轉換/建構。'},
    {'name':'list',      'sig':'list(iterable=()) -> list','params':['iterable=()'], 'ret':'list', 'doc':'建立列表。'},
    {'name':'dict',      'sig':'dict(**kwargs) -> dict',   'params':['**kwargs'], 'ret':'dict', 'doc':'建立字典。'},
    {'name':'set',       'sig':'set(iterable=()) -> set',  'params':['iterable=()'], 'ret':'set', 'doc':'建立集合。'},
    {'name':'tuple',     'sig':'tuple(iterable=()) -> tuple','params':['iterable=()'],'ret':'tuple','doc':'建立元組。'},
    {'name':'bytes',     'sig':'bytes(source, encoding, errors) -> bytes','params':['source'],'ret':'bytes','doc':'建立位元組串。'},
    # 序列操作
    {'name':'len',       'sig':'len(s) -> int', 'params':['s'], 'ret':'int', 'doc':'傳回物件長度。'},
    {'name':'range',     'sig':'range(stop)  ·  range(start, stop[, step])', 'params':['start','stop','step=1'], 'ret':'range', 'doc':'建立不可變整數序列。'},
    {'name':'enumerate', 'sig':'enumerate(iterable, start=0)', 'params':['iterable','start=0'], 'ret':'enumerate', 'doc':'傳回 (index, value) 的迭代器。'},
    {'name':'zip',       'sig':'zip(*iterables)', 'params':['*iterables'], 'ret':'zip', 'doc':'將多個可迭代物件合併成 tuple 迭代器。'},
    {'name':'map',       'sig':'map(func, *iterables)', 'params':['func','*iterables'], 'ret':'map', 'doc':'對每個元素套用函式。'},
    {'name':'filter',    'sig':'filter(func, iterable)', 'params':['func','iterable'], 'ret':'filter', 'doc':'過濾不符合條件的元素。'},
    {'name':'sorted',    'sig':'sorted(iterable, *, key=None, reverse=False)', 'params':['iterable','key=None','reverse=False'], 'ret':'list', 'doc':'傳回已排序的新列表。'},
    {'name':'reversed',  'sig':'reversed(seq)', 'params':['seq'], 'ret':'reversed', 'doc':'傳回反向迭代器。'},
    {'name':'sum',       'sig':'sum(iterable, start=0)', 'params':['iterable','start=0'], 'ret':'number', 'doc':'計算序列總和。'},
    {'name':'max',       'sig':'max(iterable, *, key=None)  ·  max(a, b, ...)', 'params':['iterable','key=None'], 'ret':'T', 'doc':'傳回最大值。'},
    {'name':'min',       'sig':'min(iterable, *, key=None)  ·  min(a, b, ...)', 'params':['iterable','key=None'], 'ret':'T', 'doc':'傳回最小值。'},
    {'name':'abs',       'sig':'abs(x) -> T', 'params':['x'], 'ret':'T', 'doc':'傳回絕對值。'},
    {'name':'round',     'sig':'round(number, ndigits=None)', 'params':['number','ndigits=None'], 'ret':'float|int', 'doc':'四捨五入。'},
    # 物件操作
    {'name':'type',      'sig':'type(object) -> type', 'params':['object'], 'ret':'type', 'doc':'傳回物件的型別。'},
    {'name':'isinstance','sig':'isinstance(object, classinfo) -> bool', 'params':['object','classinfo'], 'ret':'bool', 'doc':'檢查是否為指定型別的實例。'},
    {'name':'issubclass','sig':'issubclass(class, classinfo) -> bool', 'params':['class','classinfo'], 'ret':'bool', 'doc':'檢查是否為指定類別的子類別。'},
    {'name':'hasattr',   'sig':'hasattr(object, name) -> bool', 'params':['object','name'], 'ret':'bool', 'doc':'檢查物件是否有指定屬性。'},
    {'name':'getattr',   'sig':'getattr(object, name[, default])', 'params':['object','name','default=...'], 'ret':'T', 'doc':'取得物件屬性值。'},
    {'name':'setattr',   'sig':'setattr(object, name, value)', 'params':['object','name','value'], 'ret':None, 'doc':'設定物件屬性值。'},
    {'name':'delattr',   'sig':'delattr(object, name)', 'params':['object','name'], 'ret':None, 'doc':'刪除物件屬性。'},
    {'name':'dir',       'sig':'dir([object]) -> list', 'params':['object=...'], 'ret':'list', 'doc':'傳回物件的屬性名稱列表。'},
    {'name':'vars',      'sig':'vars([object]) -> dict', 'params':['object=...'], 'ret':'dict', 'doc':'傳回物件的 __dict__。'},
    {'name':'repr',      'sig':'repr(object) -> str', 'params':['object'], 'ret':'str', 'doc':'傳回物件的字串表示。'},
    {'name':'hash',      'sig':'hash(object) -> int', 'params':['object'], 'ret':'int', 'doc':'傳回物件的雜湊值。'},
    {'name':'id',        'sig':'id(object) -> int', 'params':['object'], 'ret':'int', 'doc':'傳回物件的唯一識別碼（記憶體位址）。'},
    {'name':'callable',  'sig':'callable(object) -> bool', 'params':['object'], 'ret':'bool', 'doc':'檢查物件是否可呼叫。'},
    # 例外
    {'name':'Exception', 'sig':'Exception(*args)', 'params':['*args'], 'ret':None, 'doc':'一般例外基底類別。'},
    {'name':'ValueError','sig':'ValueError(*args)', 'params':['*args'], 'ret':None, 'doc':'值不合法時拋出。'},
    {'name':'TypeError', 'sig':'TypeError(*args)', 'params':['*args'], 'ret':None, 'doc':'型別不合法時拋出。'},
    {'name':'KeyError',  'sig':'KeyError(key)',     'params':['key'],   'ret':None, 'doc':'字典找不到鍵時拋出。'},
    {'name':'IndexError','sig':'IndexError(*args)', 'params':['*args'], 'ret':None, 'doc':'序列索引超出範圍時拋出。'},
    {'name':'FileNotFoundError','sig':'FileNotFoundError(*args)','params':['*args'],'ret':None,'doc':'檔案不存在時拋出。'},
    {'name':'RuntimeError','sig':'RuntimeError(*args)','params':['*args'],'ret':None,'doc':'執行期錯誤。'},
    {'name':'StopIteration','sig':'StopIteration(value=None)','params':[],'ret':None,'doc':'迭代器耗盡時拋出。'},
]

GO_BUILTINS: list[dict] = [
    {'name':'make',    'sig':'make(t Type, n ...IntegerType) Type', 'params':['t','size...'], 'ret':'T', 'doc':'建立 slice / map / channel。'},
    {'name':'new',     'sig':'new(T) *T',                         'params':['T'],         'ret':'*T',  'doc':'分配 T 的零值，傳回指針。'},
    {'name':'append',  'sig':'append(s []T, vs ...T) []T',        'params':['s','vs...'], 'ret':'[]T', 'doc':'追加元素到 slice。'},
    {'name':'copy',    'sig':'copy(dst, src []T) int',            'params':['dst','src'], 'ret':'int', 'doc':'複製 slice 元素，傳回複製數量。'},
    {'name':'delete',  'sig':'delete(m map[K]V, key K)',          'params':['m','key'],   'ret':None,  'doc':'從 map 刪除鍵。'},
    {'name':'len',     'sig':'len(v Type) int',                   'params':['v'],         'ret':'int', 'doc':'傳回 array/slice/map/string/channel 長度。'},
    {'name':'cap',     'sig':'cap(v Type) int',                   'params':['v'],         'ret':'int', 'doc':'傳回 slice/channel 容量。'},
    {'name':'close',   'sig':'close(c chan<- T)',                  'params':['c'],         'ret':None,  'doc':'關閉 channel。'},
    {'name':'panic',   'sig':'panic(v any)',                      'params':['v'],         'ret':None,  'doc':'觸發 panic，終止當前 goroutine。'},
    {'name':'recover', 'sig':'recover() any',                     'params':[],            'ret':'any', 'doc':'在 deferred 函式中捕獲 panic。'},
    {'name':'println', 'sig':'println(args ...Type)',              'params':['args...'],   'ret':None,  'doc':'輸出到標準錯誤（debugging 用）。'},
    {'name':'print',   'sig':'print(args ...Type)',                'params':['args...'],   'ret':None,  'doc':'輸出到標準錯誤（debugging 用）。'},
    {'name':'complex', 'sig':'complex(r, i FloatType) complex',   'params':['r','i'],     'ret':'complex','doc':'建立複數。'},
    {'name':'real',    'sig':'real(c ComplexType) float',         'params':['c'],         'ret':'float','doc':'傳回複數的實部。'},
    {'name':'imag',    'sig':'imag(c ComplexType) float',         'params':['c'],         'ret':'float','doc':'傳回複數的虛部。'},
]

RUST_BUILTINS: list[dict] = [
    {'name':'println!',  'sig':'println!("{}", value)',            'params':['format', 'args...'], 'ret':None, 'doc':'輸出格式化字串並換行。'},
    {'name':'print!',    'sig':'print!("{}", value)',              'params':['format', 'args...'], 'ret':None, 'doc':'輸出格式化字串（不換行）。'},
    {'name':'eprintln!', 'sig':'eprintln!("{}", value)',           'params':['format', 'args...'], 'ret':None, 'doc':'輸出到 stderr 並換行。'},
    {'name':'format!',   'sig':'format!("{}", value) -> String',  'params':['format', 'args...'], 'ret':'String', 'doc':'建立格式化字串。'},
    {'name':'vec!',      'sig':'vec![elem, ...]  ·  vec![elem; n]','params':['elems...'],         'ret':'Vec<T>', 'doc':'建立 Vec<T>。'},
    {'name':'panic!',    'sig':'panic!("message")',                'params':['message'],           'ret':'!',  'doc':'終止執行並顯示錯誤訊息。'},
    {'name':'todo!',     'sig':'todo!()',                          'params':[],                    'ret':'!',  'doc':'標記尚未實作的程式碼。'},
    {'name':'unimplemented!','sig':'unimplemented!()',             'params':[],                    'ret':'!',  'doc':'標記未實作功能。'},
    {'name':'assert!',   'sig':'assert!(expr)',                    'params':['expr'],              'ret':None, 'doc':'斷言（失敗則 panic）。'},
    {'name':'dbg!',      'sig':'dbg!(expr) -> &T',                'params':['expr'],              'ret':'&T', 'doc':'輸出 debug 資訊並傳回值。'},
    {'name':'Box::new',  'sig':'Box::new(x: T) -> Box<T>',        'params':['x: T'],              'ret':'Box<T>', 'doc':'在堆積分配值。'},
    {'name':'Rc::new',   'sig':'Rc::new(value: T) -> Rc<T>',      'params':['value: T'],          'ret':'Rc<T>', 'doc':'建立引用計數指針（單執行緒）。'},
    {'name':'Arc::new',  'sig':'Arc::new(value: T) -> Arc<T>',    'params':['value: T'],          'ret':'Arc<T>', 'doc':'建立原子引用計數指針（多執行緒）。'},
    {'name':'Some',      'sig':'Some(value: T) -> Option<T>',     'params':['value: T'],          'ret':'Option<T>', 'doc':'Option::Some — 有值。'},
    {'name':'None',      'sig':'None: Option<T>',                 'params':[],                    'ret':'Option<T>', 'doc':'Option::None — 無值。'},
    {'name':'Ok',        'sig':'Ok(value: T) -> Result<T, E>',    'params':['value: T'],          'ret':'Result<T,E>', 'doc':'Result::Ok — 成功。'},
    {'name':'Err',       'sig':'Err(err: E) -> Result<T, E>',     'params':['err: E'],            'ret':'Result<T,E>', 'doc':'Result::Err — 錯誤。'},
]

_BUILTINS = {'python': PY_BUILTINS, 'go': GO_BUILTINS, 'rust': RUST_BUILTINS}


# ── 參數提取 ─────────────────────────────────────────────────────

def _extract_params(sig: str) -> list[str]:
    """從簽名字串提取參數列表。"""
    m = re.search(r'\(([^)]*)\)', sig)
    if not m: return []
    raw = m.group(1).strip()
    if not raw: return []
    params, cur, depth = [], '', 0
    for c in raw:
        if c in ('(', '[', '{'): depth += 1; cur += c
        elif c in (')', ']', '}'): depth -= 1; cur += c
        elif c == ',' and depth == 0:
            p = cur.strip()
            if p and p not in ('self', 'cls', '&self', '&mut self', '*self'):
                params.append(p)
            cur = ''
        else:
            cur += c
    p = cur.strip()
    if p and p not in ('self', 'cls', '&self', '&mut self', '*self'):
        params.append(p)
    return params

def _extract_return(sig: str, lang: str) -> str | None:
    """提取函式回傳型別。"""
    if lang == 'python':
        m = re.search(r'->\s*([^:{]+?)(?:\s*:|$)', sig)
    elif lang == 'go':
        m = re.search(r'\)\s*([^\s{]+(?:\s*\([^)]+\))?)\s*\{?$', sig)
    elif lang == 'rust':
        m = re.search(r'->\s*(.+?)(?:\s*\{|$)', sig)
    else:
        m = None
    return m.group(1).strip() if m else None


# ── 匯入解析 ─────────────────────────────────────────────────────

def _parse_py_import(text: str, line: int) -> list[dict]:
    syms = []
    if text.startswith('from'):
        m = re.match(r'^from\s+([\w.]+)\s+import\s+(.+?)(?:\s*#|$)', text)
        if m:
            module, imports = m.group(1), m.group(2).strip().lstrip('(').rstrip(')')
            for imp in imports.split(','):
                parts = imp.strip().split(' as ')
                alias = parts[-1].strip()
                if alias and re.match(r'^\w+$', alias):
                    syms.append({'name': alias, 'kind': 'module',
                                 'sig': text, 'params': [], 'ret': None,
                                 'doc': f'from {module} import {parts[0].strip()}',
                                 'line': line, 'source': 'import', 'parent': module})
    elif text.startswith('import'):
        m = re.match(r'^import\s+(.+?)(?:\s*#|$)', text)
        if m:
            for imp in m.group(1).split(','):
                parts = imp.strip().split(' as ')
                alias = parts[-1].strip()
                if alias and re.match(r'^\w+$', alias):
                    syms.append({'name': alias, 'kind': 'module',
                                 'sig': text, 'params': [], 'ret': None,
                                 'doc': f'module {parts[0].strip()}',
                                 'line': line, 'source': 'import', 'parent': None})
    return syms

def _parse_go_import(text: str, line: int) -> list[dict]:
    # import "fmt" → name: fmt
    # import f "fmt" → name: f
    syms = []
    for m in re.finditer(r'(?:(\w+)\s+)?"([\w/]+)"', text):
        alias = m.group(1) or m.group(2).split('/')[-1]
        syms.append({'name': alias, 'kind': 'module', 'sig': text,
                     'params': [], 'ret': None, 'doc': f'package "{m.group(2)}"',
                     'line': line, 'source': 'import', 'parent': None})
    return syms

def _parse_rust_use(text: str, line: int) -> list[dict]:
    # use std::collections::HashMap → name: HashMap
    # use std::{fs, path::Path}     → names: fs, Path
    syms = []
    # Simple: last segment
    for m in re.finditer(r'\b(\w+)\s*(?:;|\s*})', text):
        name = m.group(1)
        if name not in ('crate', 'super', 'self', 'pub') and re.match(r'^[A-Z]\w+$|^[a-z][a-z_]+$', name):
            syms.append({'name': name, 'kind': 'module', 'sig': text,
                         'params': [], 'ret': None, 'doc': text,
                         'line': line, 'source': 'import', 'parent': None})
    return syms


# ── 變數提取 ─────────────────────────────────────────────────────

def _parse_var(text: str, line: int) -> list[dict]:
    """從賦值語句提取變數名稱（支援 Python / Rust let / Go var）。"""
    syms = []
    # Strip Rust / Go declaration keywords
    t = re.sub(r'^(?:let\s+(?:mut\s+)?|const\s+(?:mut\s+)?|static\s+(?:mut\s+)?|var\s+)',
               '', text.strip())
    if '=' not in t: return syms
    lhs = t.split('=')[0].strip()
    lhs = lhs.split(':')[0].strip()      # Remove type annotation
    # Go: 'x int' (name then type, no colon) → take first word
    lhs_words = lhs.split()
    if len(lhs_words) == 2 and re.match(r'^[a-zA-Z_]\w*$', lhs_words[0]):
        lhs = lhs_words[0]
    lhs = re.sub(r'[+\-*/%&|^~]+$', '', lhs).strip()
    for name in lhs.split(','):
        name = name.strip().lstrip('*').strip()
        if re.match(r'^[a-zA-Z_]\w*$', name) and name not in ('_','self','cls','err','ok'):
            syms.append({'name': name, 'kind': 'variable', 'sig': text[:60],
                         'params': [], 'ret': None, 'doc': None,
                         'line': line, 'source': 'user', 'parent': None})
    return syms


# ── 主提取函式 ────────────────────────────────────────────────────

def extract_symbols(parse_result: dict, language: str, code: str) -> list[dict]:
    """
    從解析結果提取符號表，加上語言內建函式。
    回傳 list of:
      { name, kind, sig(signature), params, ret(return_type), doc,
        line, source, parent }
    """
    syms: list[dict] = []

    # ── 1. 從 definitions 提取 ──
    for d in parse_result.get('definitions', []):
        sig = d.get('detail', d.get('label', d['id']))
        params = _extract_params(sig)
        syms.append({
            'name':   d['id'],
            'kind':   d['type'],  # 'function' or 'class'
            'sig':    sig,
            'params': params,
            'ret':    _extract_return(sig, language),
            'doc':    None,
            'line':   d['line'],
            'source': 'user',
            'parent': None,
        })
        # Methods
        for m in d.get('methods', []):
            ms = m.get('detail', m.get('label', m.get('id', '')))
            syms.append({
                'name':   m.get('id', m.get('name', '')),
                'kind':   'function',
                'sig':    ms,
                'params': _extract_params(ms),
                'ret':    _extract_return(ms, language),
                'doc':    None,
                'line':   m.get('line', 0),
                'source': 'user',
                'parent': d['id'],
            })
        # Rust enum variants / struct fields as completions
        for fld in d.get('fields', []):
            syms.append({
                'name':   fld.get('label', '').split(':')[0].strip(),
                'kind':   'field',
                'sig':    fld.get('label', ''),
                'params': [],
                'ret':    None,
                'doc':    None,
                'line':   fld.get('line', 0),
                'source': 'user',
                'parent': d['id'],
            })

    # ── 2. 從 flow 提取（匯入 + 變數） ──
    lang = language
    for nd in parse_result.get('flow', []):
        if nd['type'] == 'import':
            if lang == 'python':
                syms.extend(_parse_py_import(nd['detail'], nd['line']))
            elif lang == 'go':
                syms.extend(_parse_go_import(nd['detail'], nd['line']))
            elif lang == 'rust':
                syms.extend(_parse_rust_use(nd['detail'], nd['line']))
        elif nd['type'] in ('assign',):
            syms.extend(_parse_var(nd['detail'], nd['line']))
        # Also scan children of blocks
        for child in nd.get('children', []):
            if child.get('type') == 'assign':
                syms.extend(_parse_var(child.get('detail', ''), child.get('line', 0)))

    # ── 3. 內建符號 ──
    for b in _BUILTINS.get(lang, []):
        syms.append({
            'name':   b['name'],
            'kind':   'builtin',
            'sig':    b['sig'],
            'params': b['params'],
            'ret':    b.get('ret'),
            'doc':    b.get('doc'),
            'line':   0,
            'source': 'builtin',
            'parent': None,
        })

    # Deduplicate (keep user symbol over builtin if same name)
    seen: dict[str, int] = {}
    deduped = []
    for s in syms:
        key = s['name'] + '|' + (s.get('parent') or '')
        if key not in seen:
            seen[key] = len(deduped)
            deduped.append(s)
        else:
            existing = deduped[seen[key]]
            # User symbol wins over builtin
            if s['source'] == 'user' and existing['source'] == 'builtin':
                deduped[seen[key]] = s
            # For @overload duplicates: prefer the one WITHOUT '...' body
            # (the actual implementation, not the overload stubs)
            elif s['source'] == 'user' and existing['source'] == 'user':
                # Keep the one that has more detail (the implementation)
                if len(s.get('sig','')) > len(existing.get('sig','')):
                    deduped[seen[key]] = s
    return deduped
