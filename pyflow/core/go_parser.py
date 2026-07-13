"""
Go flow parser for PyFlow IDE.
Handles: goroutines, channels, error patterns, defer, select,
struct/interface/func declarations, methods with receivers.
"""
import re

_uid = 0

def _id():
    global _uid; _uid += 1; return f'g{_uid}'

def _t(s: str, n: int = 38) -> str:
    if len(s) <= n: return s
    p = s.find('(')
    if 0 < p < n: return s[:p] + '(…)'
    return s[:n] + '…'

def _node(typ, s, lineno, children=None, calls=None, note=''):
    return {
        'id': _id(), 'type': typ,
        'label': (_t(s) + (' ' + note if note else '')),
        'detail': s[:80], 'line': lineno,
        'children': children or [], 'calls': calls or [],
        'custom_decorators': [],
    }

def _def(name, typ, s, lineno, icon='', methods=None):
    return {
        'id': name, 'type': typ,
        'label': _t(s, 46), 'detail': s,
        'line': lineno, 'qualifier_icon': icon,
        'is_async': False, 'custom_decorators': [],
        'decorators': [], 'methods': methods or [],
    }

# ── Brace-depth preprocessor ────────────────────────────────────

def _preprocess(code: str) -> list[dict]:
    """
    Returns list of {n: lineno, s: stripped, d: brace_depth_before_this_line}
    Skips blank lines, line comments, block comments, attribute lines, closing-brace-only lines.
    """
    result, depth = [], 0
    in_bc = False  # block comment

    for i, raw in enumerate(code.split('\n')):
        s = raw.strip()
        if in_bc:
            if '*/' in raw: in_bc = False
            continue
        if s.startswith('/*'):
            in_bc = True; continue
        if not s or s.startswith('//'):
            continue
        if re.match(r'^[})\]]+[,;]?\s*$', s):
            # Closing-only line — still update depth but don't emit
            for c in raw:
                if c == '{': depth += 1
                elif c == '}': depth = max(0, depth - 1)
            continue

        line_depth = depth

        j, in_str, sc, in_raw = 0, False, '', False
        while j < len(raw):
            c = raw[j]
            if in_raw:
                if c == '`': in_raw = False
            elif in_str:
                if c == '\\': j += 1
                elif c == sc: in_str = False
            else:
                if c == '`': in_raw = True
                elif c in ('"', "'"): in_str, sc = True, c
                elif c == '/' and j + 1 < len(raw):
                    if raw[j+1] == '/': break
                    if raw[j+1] == '*': in_bc = True
                elif c == '{': depth += 1
                elif c == '}': depth = max(0, depth - 1)
            j += 1

        result.append({'n': i + 1, 's': s, 'd': line_depth})

    return result


def _next_d0(proc: list, after: int) -> float:
    for p in proc:
        if p['n'] > after and p['d'] == 0:
            return p['n']
    return float('inf')

# ── Classifiers ─────────────────────────────────────────────────

def _cls_top(s: str) -> str:
    if re.match(r'^package\s', s): return 'package'
    if re.match(r'^import\b', s):  return 'import'
    if re.match(r'^type\s+\w+(?:\[[^\]]+\])?\s+struct\b', s):    return 'struct'
    if re.match(r'^type\s+\w+(?:\[[^\]]+\])?\s+interface\b', s): return 'interface'
    if re.match(r'^type\s', s): return 'type'
    if re.match(r'^func\s*\(', s): return 'method'   # func (r T) Name()
    if re.match(r'^func\s+\w', s): return 'func'
    if re.match(r'^(var|const)\s', s): return 'var'
    return 'other'

def _cls_stmt(s: str) -> str:
    if re.match(r'^go\s+', s): return 'goroutine'
    if re.match(r'^defer\s+', s): return 'defer'
    if re.match(r'^select\b', s): return 'select'
    if re.match(r'^switch\b', s): return 'switch'
    # Error check: if err != nil / if _, err := f(); err != nil
    if (re.match(r'^if\b', s) and re.search(r'err\s*!=\s*nil', s)):
        return 'error_check'
    if re.match(r'^if\b|^else\b', s): return 'condition'
    if re.match(r'^for\b', s): return 'loop'
    if re.match(r'^(return|panic|break|continue)\b', s): return 'flow_ctrl'
    if re.search(r'<-', s): return 'channel'
    if re.match(r'^(var\s|const\s)', s): return 'assign'
    if re.match(r'^[\w,\s\*\[\]]+\s*:?=', s): return 'assign'
    if re.match(r'^[\w\.]+\s*\(', s): return 'call'
    return 'other'

# ── Flow block parser ────────────────────────────────────────────

def _parse_block(all_lines: list, base: int) -> list:
    at_base = [l for l in all_lines if l['d'] == base]
    nodes = []

    for i, ln in enumerate(at_base):
        s, n = ln['s'], ln['n']
        t = _cls_stmt(s)

        next_n = at_base[i + 1]['n'] if i + 1 < len(at_base) else float('inf')

        children = []
        if t in ('condition', 'loop', 'select', 'switch', 'error_check'):
            sub = [l for l in all_lines if ln['n'] < l['n'] < next_n and l['d'] > base]
            if sub:
                children = _parse_block(sub, base + 1)

        # Special icons for Go-specific constructs
        note = ''
        if t == 'goroutine': note = '⇢'
        if t == 'channel':
            note = '→' if '<-' in s and re.search(r'\w+\s*<-', s) else '←'

        nodes.append(_node(t, s, n, children, note=note))

    return nodes

# ── Main entry point ─────────────────────────────────────────────

def _method_belongs(fn_sig: str, type_name: str) -> bool:
    """Check if a Go method func signature belongs to type_name (handles generics)."""
    # Extract receiver: everything before the first `)`
    recv = fn_sig.split(')')[0] if ')' in fn_sig else ''
    # The receiver type appears as: *TypeName or TypeName or *TypeName[T] or TypeName[T, ...]
    # Match after * and before ( [ whitespace or end
    import re as _re
    return bool(_re.search(rf'\*?\b{_re.escape(type_name)}(?:\[|\b)', recv))


def parse_go_file(code: str, path: str = '<go>') -> dict:
    global _uid; _uid = 0
    proc = _preprocess(code)
    top = [p for p in proc if p['d'] == 0]

    flow, definitions = [], []
    main_n = None

    for p in top:
        s, n = p['s'], p['n']
        t = _cls_top(s)

        if t == 'package': continue

        if t == 'import':
            flow.append(_node('import', s, n)); continue

        if t in ('var', 'const'):
            flow.append(_node('assign', s, n)); continue

        if t in ('struct', 'interface'):
            m = re.match(r'^type\s+(\w+)', s)
            name = m.group(1) if m else 'Type'
            icon = '◈' if t == 'interface' else ''
            # Attach methods that have this type as receiver
            meths = [q for q in top
                     if _cls_top(q['s']) == 'method'
                     and re.search(rf'\*?\b{re.escape(name)}\b',
                                   q['s'].split(')')[0] if ')' in q['s'] else '')]
            definitions.append({**_def(name, 'class', s, n, icon),
                                 'methods': [_meth(m) for m in meths]})
            continue

        if t in ('func', 'method'):
            m = re.match(r'^func\s+(?:\([^)]+\)\s+)?(\w+)', s)
            name = m.group(1) if m else 'fn'
            if name == 'main':
                main_n = n; continue
            icon = '⟨⟩' if t == 'method' else ''
            definitions.append(_def(name, 'function', s, n, icon)); continue

    # Parse main() body
    if main_n:
        end = _next_d0(proc, main_n)
        body = [p for p in proc if main_n < p['n'] < end]
        flow.extend(_parse_block(body, 1))

    # Step numbers on top-level flow
    for i, nd in enumerate(flow):
        nd['step'] = i + 1

    # Resolve calls to known definitions
    def_names = {d['id'] for d in definitions}
    def _fix(nodes):
        for nd in nodes:
            nd['calls'] = [w for w in re.findall(r'\b(\w+)\s*\(', nd['detail'])
                           if w in def_names]
            _fix(nd['children'])
    _fix(flow)

    return {'flow': flow, 'definitions': definitions, 'error': None}


def _meth(p: dict) -> dict:
    s = p['s']
    m = re.search(r'\)\s+(\w+)', s)
    name = m.group(1) if m else 'fn'
    return _def(name, 'function', s, p['n'], '⟨⟩')
