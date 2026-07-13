"""
Rust 語義分析器 — 使用 tree-sitter-rust 精確解析。

保證涵蓋：
  ● 所有權 (owned / move)
  ◎ 共享借用 (&T)
  ◈ 可變借用 (&mut T)
  ⚠ 原始指針 (*const T / *mut T)
  □ 堆疊分配 (Box<T>)
  ⊙ 引用計數 (Rc<T> / Arc<T>)
  ⊞ 內部可變性 (Cell / RefCell / Mutex / RwLock)
  ⚡ 非同步函式 (async fn)
  🔴 unsafe 區塊
  ≈ Cow<T>

若 tree-sitter-rust 不可用，自動降回高精度 regex 解析器。
"""
from __future__ import annotations
import re, sys
from typing import Optional

# ── tree-sitter 設定 ──────────────────────────────────────────────
_TS_OK = False
try:
    import tree_sitter_rust as _tsr
    from tree_sitter import Language, Parser as _TSParser
    _RUST_LANG  = Language(_tsr.language())
    _ts_parser  = _TSParser(_RUST_LANG)
    _TS_OK = True
except Exception:
    pass

# ── 工具函式 ─────────────────────────────────────────────────────
_uid = 0
def _id(p='r'):
    global _uid; _uid += 1; return f'{p}{_uid}'

def _t(s: str, n: int = 40) -> str:
    if len(s) <= n: return s
    p = s.find('(')
    if 0 < p < n: return s[:p] + '(…)'
    return s[:n] + '…'

# ── 所有權分類器 ──────────────────────────────────────────────────
OWNERSHIP_TABLE = {
    # pattern           → ownership tag
    r'\*\s*mut\b':       'raw_mut',
    r'\*\s*const\b':     'raw_const',
    r'NonNull<':         'raw_mut',    # wraps *mut
    r'AtomicPtr<':       'raw_mut',
    r'&\s*mut\b':        'mut_ref',
    r"&\s*'\w+\s+mut\b": 'mut_ref',
    r'&':                'shared_ref',
    r'Box<':             'box',
    r'Arc<':             'arc',
    r'Rc<':              'rc',
    r'Weak<':            'weak',
    r'RefCell<':         'refcell',
    r'Mutex<':           'mutex',
    r'RwLock<':          'rwlock',
    r'Cell<':            'cell',
    r'Cow<':             'cow',
    r'Pin<':             'pin',
}

OWNERSHIP_RHS = {
    r'^Box::new\b':       'box',
    r'^Arc::new\b':       'arc',
    r'^Rc::new\b':        'rc',
    r'^RefCell::new\b':   'refcell',
    r'^Mutex::new\b':     'mutex',
    r'^RwLock::new\b':    'rwlock',
    r'^Cell::new\b':      'cell',
    r'^&\s*mut\s':        'mut_ref',
    r'^&\s*\w':           'shared_ref',
    r'as\s+\*\s*mut':     'raw_mut',
    r'as\s+\*\s*const':   'raw_const',
    r'ptr::null_mut\b':   'raw_mut',
    r'ptr::null\b':       'raw_const',
    r'NonNull::new\b':    'raw_mut',
    r'Box::into_raw\b':   'raw_mut',
    r'Box::from_raw\b':   'box',
    r'Cow::Borrowed\b':   'cow',
    r'Cow::Owned\b':      'cow',
}

def _classify_own(stmt: str) -> Optional[str]:
    """
    從 let 語句精確分類所有權類型。
    優先級：型別標注 > 右側表達式 > 預設 owned
    """
    # 1. 型別標注 (let x: TYPE = ...)
    ann = re.search(r':\s*([\w<>\[\]&*\s\']+?)\s*=', stmt)
    if ann:
        ty = ann.group(1).strip()
        for pat, tag in OWNERSHIP_TABLE.items():
            if re.search(pat, ty):
                return tag
    # 2. 右側表達式
    rhs_m = re.search(r'=\s*(.+?)(?:;|$)', stmt)
    if rhs_m:
        rhs = rhs_m.group(1).strip()
        for pat, tag in OWNERSHIP_RHS.items():
            if re.search(pat, rhs):
                return tag
        if re.match(r'&\s*mut\s', rhs): return 'mut_ref'
        if re.match(r'&', rhs):          return 'shared_ref'
    return 'owned'

# 所有權 badge 元資料
OWN_META = {
    'owned':       {'icon':'●', 'color':'#22c55e', 'label':'owned',        'tip':'擁有所有權'},
    'shared_ref':  {'icon':'◎', 'color':'#60a5fa', 'label':'&T',           'tip':'共享借用（不可變）'},
    'mut_ref':     {'icon':'◈', 'color':'#f97316', 'label':'&mut T',       'tip':'獨佔借用（可變）'},
    'raw_const':   {'icon':'⚠', 'color':'#ef4444', 'label':'*const T',     'tip':'原始不可變指針 — unsafe!'},
    'raw_mut':     {'icon':'⚠', 'color':'#dc2626', 'label':'*mut T',       'tip':'原始可變指針 — unsafe!'},
    'box':         {'icon':'□', 'color':'#a78bfa', 'label':'Box<T>',       'tip':'堆疊分配，唯一所有者'},
    'rc':          {'icon':'⊙', 'color':'#38bdf8', 'label':'Rc<T>',        'tip':'引用計數（單執行緒）'},
    'arc':         {'icon':'⊙', 'color':'#2dd4bf', 'label':'Arc<T>',       'tip':'原子引用計數（多執行緒）'},
    'weak':        {'icon':'◌', 'color':'#6b7280', 'label':'Weak<T>',      'tip':'弱引用（不增加引用計數）'},
    'refcell':     {'icon':'⊞', 'color':'#fbbf24', 'label':'RefCell<T>',   'tip':'執行期借用檢查'},
    'mutex':       {'icon':'⊟', 'color':'#fbbf24', 'label':'Mutex<T>',     'tip':'互斥鎖'},
    'rwlock':      {'icon':'⊟', 'color':'#fbbf24', 'label':'RwLock<T>',    'tip':'讀寫鎖'},
    'cell':        {'icon':'⊞', 'color':'#fbbf24', 'label':'Cell<T>',      'tip':'複製型內部可變性'},
    'cow':         {'icon':'≈',  'color':'#a3e635', 'label':'Cow<T>',       'tip':'寫時複製'},
    'pin':         {'icon':'⊠', 'color':'#818cf8', 'label':'Pin<T>',       'tip':'固定記憶體位置'},
}

# ── tree-sitter 解析器 ────────────────────────────────────────────

def _node_text(node, code_bytes: bytes) -> str:
    return code_bytes[node.start_byte:node.end_byte].decode('utf-8', errors='replace').strip()

def _first_line(text: str) -> str:
    return text.split('\n')[0].strip()

def _node_from_ts(typ, text, lineno, children=None, ownership=None, note='', extra=None):
    n = {
        'id': _id(), 'type': typ,
        'label': _t(text) + (' ' + note if note else ''),
        'detail': text[:120], 'line': lineno,
        'children': children or [], 'calls': [],
        'custom_decorators': [], 'ownership': ownership,
    }
    if extra: n.update(extra)
    return n

def _lineno(node) -> int:
    return node.start_point[0] + 1

# ── tree-sitter 流程塊解析 ────────────────────────────────────────

def _parse_block_ts(block_node, code_bytes: bytes) -> list:
    """遞迴解析函式體 / 塊。"""
    nodes = []
    for stmt in block_node.children:
        t = stmt.type
        text = _first_line(_node_text(stmt, code_bytes))
        ln   = _lineno(stmt)

        if t == 'let_declaration':
            own = _classify_own(_node_text(stmt, code_bytes))
            is_mut = any(c.type == 'mutable_specifier' for c in stmt.children)
            nodes.append(_node_from_ts(
                'assign', text, ln, ownership=own,
                note='[mut]' if is_mut else ''
            ))

        elif t == 'expression_statement':
            inner = stmt.children[0] if stmt.children else None
            if inner is None: continue
            it = inner.type
            if it == 'call_expression':
                fn_text = _node_text(inner.children[0], code_bytes) if inner.children else text
                # Detect spawn
                if re.search(r'(tokio|thread|rayon)\s*::\s*spawn', fn_text):
                    nodes.append(_node_from_ts('goroutine', text, ln, note='⇢'))
                else:
                    nodes.append(_node_from_ts('call', text, ln))
            elif it == 'await_expression':
                nodes.append(_node_from_ts('call', text, ln, note='.await'))
            elif it == 'assignment_expression':
                # Check if it's a raw pointer write: *ptr = val
                if text.startswith('*'):
                    nodes.append(_node_from_ts('assign', text, ln, ownership='raw_mut',
                                               note='⚠ ptr write'))
                else:
                    nodes.append(_node_from_ts('assign', text, ln))
            elif it == 'try_expression':
                nodes.append(_node_from_ts('flow_ctrl', text, ln, note='?'))
            elif it == 'macro_invocation':
                nodes.append(_node_from_ts('call', text, ln))
            else:
                nodes.append(_node_from_ts('other', text, ln))

        elif t == 'if_expression':
            cond_children = []
            for c in stmt.children:
                if c.type == 'block':
                    cond_children.extend(_parse_block_ts(c, code_bytes))
            # else branch
            else_node = next((c for c in stmt.children if c.type == 'else_clause'), None)
            if else_node:
                else_block = next((c for c in else_node.children if c.type in ('block', 'if_expression')), None)
                if else_block:
                    if else_block.type == 'if_expression':
                        cond_children.extend(_parse_block_ts_stmt(else_block, code_bytes))
                    else:
                        cond_children.append(_node_from_ts('condition', 'else {…}', _lineno(else_node),
                                             children=_parse_block_ts(else_block, code_bytes)))
            nodes.append(_node_from_ts('condition', text, ln, children=cond_children))

        elif t == 'match_expression':
            arms = []
            body = next((c for c in stmt.children if c.type == 'match_block'), None)
            if body:
                for arm in body.children:
                    if arm.type == 'match_arm':
                        pat = next((c for c in arm.children if c.type in ('match_pattern','_pattern','tuple_pattern','struct_pattern','identifier','_')), None)
                        pat_text = _node_text(pat, code_bytes) if pat else '_'
                        arm_body = next((c for c in arm.children if c.type == 'block'), None)
                        arm_children = _parse_block_ts(arm_body, code_bytes) if arm_body else []
                        arms.append(_node_from_ts('condition', f'{pat_text} =>', _lineno(arm),
                                                  children=arm_children))
            nodes.append(_node_from_ts('match', text, ln, children=arms))

        elif t in ('while_expression', 'for_expression', 'loop_expression'):
            body = next((c for c in stmt.children if c.type == 'block'), None)
            ch = _parse_block_ts(body, code_bytes) if body else []
            nodes.append(_node_from_ts('loop', text, ln, children=ch))

        elif t == 'unsafe_block':
            inner_block = next((c for c in stmt.children if c.type == 'block'), None)
            ch = _parse_block_ts(inner_block, code_bytes) if inner_block else []
            nodes.append(_node_from_ts('unsafe_block', 'unsafe { … }', ln,
                                       children=ch, note='⛔'))

        elif t == 'return_expression':
            nodes.append(_node_from_ts('flow_ctrl', text, ln))

        elif t == 'break_expression':
            nodes.append(_node_from_ts('flow_ctrl', text, ln))

        elif t == 'continue_expression':
            nodes.append(_node_from_ts('flow_ctrl', text, ln))

        elif t in ('comment', 'line_comment', 'block_comment', '}', '{'):
            continue

    return nodes

def _parse_block_ts_stmt(node, code_bytes: bytes) -> list:
    """For when we get an if_expression directly (elif-like)."""
    return [_node_from_ts('condition', _first_line(_node_text(node, code_bytes)), _lineno(node),
                          children=_parse_block_ts(node, code_bytes))]

def _get_fn_info(node, code_bytes: bytes) -> dict:
    """Extract function name, params, return type, lifetimes."""
    is_async = any(c.type == 'async' for c in node.children)
    name_node = next((c for c in node.children if c.type == 'identifier'), None)
    name = _node_text(name_node, code_bytes) if name_node else 'fn'

    # Parameters with ownership info
    params_node = next((c for c in node.children if c.type == 'parameters'), None)
    params_info = []
    if params_node:
        for p in params_node.children:
            if p.type == 'parameter':
                pt = _node_text(p, code_bytes)
                own = _classify_own(pt + ' = dummy') if ':' in pt else 'owned'
                params_info.append({'text': pt, 'ownership': own})
            elif p.type == 'self_parameter':
                pt = _node_text(p, code_bytes)
                own = 'mut_ref' if '&mut' in pt else ('shared_ref' if '&' in pt else 'owned')
                params_info.append({'text': pt, 'ownership': own})

    # Return type
    ret_node = next((c for c in node.children if c.type == 'type_identifier'
                     and c.start_byte > (params_node.end_byte if params_node else 0)), None)
    ret_text = _node_text(ret_node, code_bytes) if ret_node else ''

    # Lifetimes from generics
    gen_node = next((c for c in node.children if c.type in ('type_parameters', 'lifetime_parameters')), None)
    lifetimes = re.findall(r"'([a-z]+|\bstatic\b)", _node_text(gen_node, code_bytes) if gen_node else '')

    return {
        'name': name, 'is_async': is_async,
        'params': params_info, 'lifetimes': lifetimes,
        'return_type': ret_text,
    }

# ── 頂層解析 ─────────────────────────────────────────────────────

def _parse_ts(code: str) -> dict:
    code_bytes = code.encode('utf-8')
    tree  = _ts_parser.parse(code_bytes)
    root  = tree.root_node

    flow, definitions = [], []
    main_node = None

    for item in root.children:
        t    = item.type
        text = _first_line(_node_text(item, code_bytes))
        ln   = _lineno(item)

        if t in ('use_declaration', 'extern_crate_declaration'):
            flow.append(_node_from_ts('import', text, ln))

        elif t in ('const_item', 'static_item'):
            own = _classify_own(_node_text(item, code_bytes))
            flow.append(_node_from_ts('assign', text, ln, ownership=own))

        elif t == 'struct_item':
            name_node = next((c for c in item.children if c.type == 'type_identifier'), None)
            name = _node_text(name_node, code_bytes) if name_node else 'Struct'
            # Fields with ownership annotations
            fields_node = next((c for c in item.children if c.type == 'field_declaration_list'), None)
            fields = []
            if fields_node:
                for f in fields_node.children:
                    if f.type == 'field_declaration':
                        ft = _node_text(f, code_bytes)
                        own = _classify_own('let x: ' + ft.split(':')[-1].strip() + ' = dummy')
                        fields.append({'label': ft, 'ownership': own})
            definitions.append({
                'id': name, 'type': 'class', 'label': _t(text, 46), 'detail': text,
                'line': ln, 'qualifier_icon': '', 'is_async': False,
                'custom_decorators': [], 'decorators': [],
                'methods': [], 'fields': fields,
            })

        elif t == 'enum_item':
            name_node = next((c for c in item.children if c.type == 'type_identifier'), None)
            name = _node_text(name_node, code_bytes) if name_node else 'Enum'
            body = next((c for c in item.children if c.type == 'enum_variant_list'), None)
            variants = []
            if body:
                for v in body.children:
                    if v.type == 'enum_variant':
                        vt = _node_text(v, code_bytes)
                        variants.append({
                            'id': vt.split('(')[0].split('{')[0].strip(), 'type': 'function',
                            'label': _t(vt, 44), 'detail': vt, 'line': _lineno(v),
                            'qualifier_icon': '◆', 'is_async': False,
                            'custom_decorators': [], 'decorators': [], 'methods': [],
                        })
            definitions.append({
                'id': name, 'type': 'class', 'label': _t(text, 46), 'detail': text,
                'line': ln, 'qualifier_icon': '◆', 'is_async': False,
                'custom_decorators': [], 'decorators': [],
                'methods': variants, 'fields': [],
            })

        elif t == 'trait_item':
            name_node = next((c for c in item.children if c.type == 'type_identifier'), None)
            name = _node_text(name_node, code_bytes) if name_node else 'Trait'
            body = next((c for c in item.children if c.type == 'declaration_list'), None)
            fns = []
            if body:
                for fn_node in body.children:
                    if fn_node.type == 'function_item':
                        info = _get_fn_info(fn_node, code_bytes)
                        fns.append({
                            'id': info['name'], 'type': 'function',
                            'label': _t(_first_line(_node_text(fn_node, code_bytes)), 44),
                            'detail': _first_line(_node_text(fn_node, code_bytes)),
                            'line': _lineno(fn_node), 'qualifier_icon': '⚡' if info['is_async'] else '',
                            'is_async': info['is_async'], 'lifetimes': info['lifetimes'],
                            'params': info['params'],
                            'custom_decorators': [], 'decorators': [], 'methods': [],
                        })
            definitions.append({
                'id': name, 'type': 'class', 'label': _t(text, 46), 'detail': text,
                'line': ln, 'qualifier_icon': '◈', 'is_async': False,
                'custom_decorators': [], 'decorators': [], 'methods': fns, 'fields': [],
            })

        elif t == 'impl_item':
            # impl Type / impl<T> Type<T> / impl Trait for Type
            type_node = next((c for c in item.children if c.type == 'type_identifier'), None)
            if type_node is None:
                # Generic: impl<T> Cache<T> → look inside generic_type
                gen = next((c for c in item.children if c.type == 'generic_type'), None)
                if gen:
                    type_node = next((c for c in gen.children if c.type == 'type_identifier'), None)
            name = _node_text(type_node, code_bytes).strip() if type_node else 'Impl'
            body = next((c for c in item.children if c.type == 'declaration_list'), None)
            fns = []
            if body:
                for fn_node in body.children:
                    if fn_node.type == 'function_item':
                        info = _get_fn_info(fn_node, code_bytes)
                        fns.append({
                            'id': info['name'], 'type': 'function',
                            'label': _t(_first_line(_node_text(fn_node, code_bytes)), 44),
                            'detail': _first_line(_node_text(fn_node, code_bytes)),
                            'line': _lineno(fn_node),
                            'qualifier_icon': '⚡' if info['is_async'] else '⟨⟩',
                            'is_async': info['is_async'], 'lifetimes': info['lifetimes'],
                            'params': info['params'],
                            'custom_decorators': [], 'decorators': [], 'methods': [],
                        })
            # Merge into existing struct/enum
            existing = next((d for d in definitions if d['id'] == name), None)
            if existing:
                existing['methods'].extend(fns)
            else:
                definitions.append({
                    'id': name, 'type': 'class', 'label': _t(text, 46), 'detail': text,
                    'line': ln, 'qualifier_icon': '⊡', 'is_async': False,
                    'custom_decorators': [], 'decorators': [], 'methods': fns, 'fields': [],
                })

        elif t == 'function_item':
            info = _get_fn_info(item, code_bytes)
            if info['name'] == 'main':
                main_node = item
            else:
                definitions.append({
                    'id': info['name'], 'type': 'function',
                    'label': _t(text, 46), 'detail': text,
                    'line': ln, 'qualifier_icon': '⚡' if info['is_async'] else '',
                    'is_async': info['is_async'], 'lifetimes': info['lifetimes'],
                    'params': info['params'],
                    'custom_decorators': [], 'decorators': [], 'methods': [], 'fields': [],
                })

        elif t == 'mod_item':
            name_node = next((c for c in item.children if c.type == 'identifier'), None)
            name = _node_text(name_node, code_bytes) if name_node else 'mod'
            definitions.append({
                'id': name, 'type': 'class', 'label': _t(text, 46), 'detail': text,
                'line': ln, 'qualifier_icon': '◻', 'is_async': False,
                'custom_decorators': [], 'decorators': [], 'methods': [], 'fields': [],
            })

    # Parse fn main() body
    if main_node:
        body = next((c for c in main_node.children if c.type == 'block'), None)
        if body:
            flow.extend(_parse_block_ts(body, code_bytes))

    # Step numbers + call resolution
    def_names = {d['id'] for d in definitions}
    for i, nd in enumerate(flow):
        nd['step'] = i + 1
    def _fix(nodes):
        for nd in nodes:
            nd['calls'] = list({w for w in re.findall(r'\b(\w+)\s*[!]?\s*[(]', nd['detail'])
                                 if w in def_names})
            _fix(nd.get('children', []))
    _fix(flow)

    return {'flow': flow, 'definitions': definitions, 'error': None, 'parser': 'tree-sitter'}


# ── regex 降回解析器 ──────────────────────────────────────────────

def _parse_regex(code: str, path: str) -> dict:
    """高精度 regex 後備解析器（當 tree-sitter 不可用時）。"""
    from .go_parser import _preprocess  # 借用 brace-depth 處理器
    proc = _preprocess(code)
    top  = [p for p in proc if p['d'] == 0]

    flow, definitions, main_n = [], [], None
    for p in top:
        s, n = p['s'], p['n']
        pub_s = re.sub(r'^pub(\s*\([^)]+\))?\s+', '', s).strip()
        if re.match(r'^use\b', pub_s) or re.match(r'^extern\b', pub_s):
            flow.append({'id':_id(),'type':'import','label':_t(s),'detail':s,'line':n,
                         'children':[],'calls':[],'custom_decorators':[],'ownership':None})
        elif re.match(r'^(const|static)\b', pub_s):
            own = _classify_own(s + ' = dummy')
            flow.append({'id':_id(),'type':'assign','label':_t(s),'detail':s,'line':n,
                         'children':[],'calls':[],'custom_decorators':[],'ownership':own})
        elif re.match(r'^struct\b', pub_s):
            m = re.search(r'struct\s+(\w+)', s); name=m.group(1) if m else 'Struct'
            definitions.append({'id':name,'type':'class','label':_t(s,46),'detail':s,'line':n,
                                 'qualifier_icon':'','is_async':False,'custom_decorators':[],
                                 'decorators':[],'methods':[],'fields':[]})
        elif re.match(r'^enum\b', pub_s):
            m = re.search(r'enum\s+(\w+)', s); name=m.group(1) if m else 'Enum'
            definitions.append({'id':name,'type':'class','label':_t(s,46),'detail':s,'line':n,
                                 'qualifier_icon':'◆','is_async':False,'custom_decorators':[],
                                 'decorators':[],'methods':[],'fields':[]})
        elif re.match(r'^trait\b', pub_s):
            m = re.search(r'trait\s+(\w+)', s); name=m.group(1) if m else 'Trait'
            definitions.append({'id':name,'type':'class','label':_t(s,46),'detail':s,'line':n,
                                 'qualifier_icon':'◈','is_async':False,'custom_decorators':[],
                                 'decorators':[],'methods':[],'fields':[]})
        elif re.match(r'^impl\b', s):
            m = re.search(r'impl(?:<[^>]*>)?\s+(?:\w+\s+for\s+)?(\w+)', s)
            name = m.group(1) if m else 'Impl'
            existing = next((d for d in definitions if d['id']==name), None)
            if not existing:
                definitions.append({'id':name,'type':'class','label':_t(s,46),'detail':s,'line':n,
                                     'qualifier_icon':'⊡','is_async':False,'custom_decorators':[],
                                     'decorators':[],'methods':[],'fields':[]})
        elif re.match(r'^(?:async\s+)?fn\b', pub_s):
            m = re.search(r'fn\s+(\w+)', s); name=m.group(1) if m else 'fn'
            if name=='main': main_n=n; continue
            is_async=bool(re.match(r'^async\s+fn',pub_s))
            lts=re.findall(r"'([a-z]+|\bstatic\b)",s)
            definitions.append({'id':name,'type':'function','label':_t(s,46),'detail':s,'line':n,
                                 'qualifier_icon':'⚡' if is_async else '','is_async':is_async,
                                 'lifetimes':lts,'custom_decorators':[],'decorators':[],'methods':[],'fields':[]})

    if main_n:
        from .go_parser import _preprocess as _pp, _next_d0
        proc2=_pp(code)
        end=_next_d0(proc2,main_n)
        body=[p for p in proc2 if main_n<p['n']<end]
        at1=[l for l in body if l['d']==1]
        for i,ln in enumerate(at1):
            s,nn=ln['s'],ln['n']
            nxt=at1[i+1]['n'] if i+1<len(at1) else float('inf')
            own=_classify_own(s) if re.match(r'^let\b',s) else None
            is_unsafe=bool(re.match(r'^unsafe\b',s))
            is_spawn=bool(re.search(r'(tokio|thread)\s*::\s*spawn',s))
            is_match=bool(re.match(r'^match\b',s))
            if is_unsafe: t='unsafe_block'
            elif is_spawn: t='goroutine'
            elif is_match: t='match'
            elif re.match(r'^let\b',s): t='assign'
            elif re.match(r'^(return|break|continue|panic!|todo!)\b',s): t='flow_ctrl'
            elif re.match(r'^(if|else)\b',s): t='condition'
            elif re.match(r'^(for|while|loop)\b',s): t='loop'
            elif re.match(r'^\w+.*\(', s): t='call'
            else: t='other'
            sub=[l for l in body if ln['n']<l['n']<nxt and l['d']>1]
            ch=[]
            if sub and t in ('condition','loop','match','unsafe_block','goroutine'):
                at2=[l for l in sub if l['d']==2]
                for j,l2 in enumerate(at2):
                    nx2=at2[j+1]['n'] if j+1<len(at2) else float('inf')
                    flow.append(None)  # placeholder, handled below
                    o2=_classify_own(l2['s']) if re.match(r'^let\b',l2['s']) else None
                    ch.append({'id':_id(),'type':'other','label':_t(l2['s']),'detail':l2['s'],
                               'line':l2['n'],'children':[],'calls':[],'custom_decorators':[],'ownership':o2})
            flow.append({'id':_id(),'type':t,'label':_t(s),'detail':s,'line':nn,
                         'children':ch,'calls':[],'custom_decorators':[],'ownership':own})
        # Remove None placeholders
        flow=[f for f in flow if f is not None]

    for i,nd in enumerate(flow): nd['step']=i+1
    return {'flow':flow,'definitions':definitions,'error':None,'parser':'regex'}


# ── 主入口 ────────────────────────────────────────────────────────

def parse_rust_file(code: str, path: str = '<rs>') -> dict:
    global _uid; _uid = 0
    if _TS_OK:
        try:
            return _parse_ts(code)
        except Exception as e:
            pass  # Fall through to regex
    return _parse_regex(code, path)

# Expose ownership metadata for frontend
def ownership_meta() -> dict:
    return OWN_META
