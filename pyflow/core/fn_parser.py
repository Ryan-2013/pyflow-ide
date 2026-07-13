"""
函式體解析器 — 提取任意函式/方法的內部流程。
解決「只能看 main()」的最大限制。
"""
from __future__ import annotations
import ast, re, textwrap

# ── Python ────────────────────────────────────────────────────────

def _py_find_fn(tree, fn_name: str):
    """在 AST 中找到第一個名為 fn_name 的函式節點。"""
    parts = fn_name.split('.')          # 'MyClass.method' → ['MyClass', 'method']
    if len(parts) == 2:
        cls_name, mth_name = parts
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == cls_name:
                for item in ast.walk(node):
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if item.name == mth_name:
                            return item
    else:
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == fn_name:
                    return node
    return None


def extract_python_fn(code: str, fn_name: str, path: str = '<string>') -> dict:
    from core.ast_parser import parse_python_file

    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return {'flow': [], 'definitions': [], 'error': str(e), 'fn_name': fn_name}

    fn_node = _py_find_fn(tree, fn_name)
    if fn_node is None:
        return {
            'flow': [], 'definitions': [],
            'error': f'找不到函式 {fn_name!r}',
            'fn_name': fn_name,
        }

    lines = code.split('\n')
    fn_lineno = fn_node.lineno

    # 取出函式「體」的行（去掉 def 行本身）
    if fn_node.body:
        body_start = fn_node.body[0].lineno          # 第一個語句行
    else:
        return {'flow': [], 'definitions': [], 'fn_name': fn_name, 'fn_line': fn_lineno}

    body_end = fn_node.end_lineno if hasattr(fn_node, 'end_lineno') else len(lines)
    body_lines = lines[body_start - 1: body_end]

    # Dedent（移除縮排）後重新解析
    body_code = textwrap.dedent('\n'.join(body_lines))
    result = parse_python_file(body_code, path)

    # 修正行號（offset 回原始行）
    offset = body_start - 1

    def fix_lines(nodes):
        for n in nodes:
            if n.get('line'):
                n['line'] += offset
            fix_lines(n.get('children', []))

    fix_lines(result.get('flow', []))

    return {
        **result,
        'fn_name':   fn_name,
        'fn_line':   fn_lineno,
        'fn_async':  isinstance(fn_node, ast.AsyncFunctionDef),
        'fn_args':   [a.arg for a in fn_node.args.args if a.arg not in ('self','cls')],
    }


# ── Go ────────────────────────────────────────────────────────────

def extract_go_fn(code: str, fn_name: str, path: str = '<go>') -> dict:
    from core.go_parser import parse_go_file, _preprocess, _cls_top, _next_d0, _parse_stmts

    proc = _preprocess(code)
    top  = [p for p in proc if p['d'] == 0]

    # Find the function
    target = None
    for p in top:
        s = p['s']
        t = _cls_top(s)
        if t in ('func', 'method'):
            # Extract name
            m = re.match(r'^func\s+(?:\([^)]+\)\s+)?(\w+)', s)
            name = m.group(1) if m else ''
            if name == fn_name or s.endswith(fn_name + '(') or fn_name in s:
                target = p
                break

    if target is None:
        return {'flow': [], 'definitions': [], 'error': f'找不到函式 {fn_name!r}', 'fn_name': fn_name}

    end = _next_d0(proc, target['n'])
    body = [p for p in proc if target['n'] < p['n'] < end]
    flow = _parse_stmts(body, 1)
    for i, n in enumerate(flow): n['step'] = i + 1

    return {'flow': flow, 'definitions': [], 'fn_name': fn_name, 'fn_line': target['n']}


# ── Rust ─────────────────────────────────────────────────────────

def extract_rust_fn(code: str, fn_name: str, path: str = '<rs>') -> dict:
    from core.rust_parser import _TS_OK

    if not _TS_OK:
        return {'flow': [], 'definitions': [], 'error': 'tree-sitter 未載入', 'fn_name': fn_name}

    import tree_sitter_rust as tsr
    from tree_sitter import Language, Parser as TSP
    from core.rust_parser import _parse_block_ts, _node_text, _lineno

    LANG = Language(tsr.language())
    parser = TSP(LANG)
    cb = code.encode('utf-8')
    tree = parser.parse(cb)

    def find_fn(node, name):
        if node.type == 'function_item':
            n = next((c for c in node.children if c.type == 'identifier'), None)
            if n and _node_text(n, cb).strip() == name:
                return node
        for child in node.children:
            found = find_fn(child, name)
            if found:
                return found
        return None

    fn_node = find_fn(tree.root_node, fn_name)
    if fn_node is None:
        return {'flow': [], 'definitions': [], 'error': f'找不到函式 {fn_name!r}', 'fn_name': fn_name}

    block = next((c for c in fn_node.children if c.type == 'block'), None)
    if not block:
        return {'flow': [], 'definitions': [], 'fn_name': fn_name, 'fn_line': _lineno(fn_node)}

    flow = _parse_block_ts(block, cb)
    for i, n in enumerate(flow): n['step'] = i + 1

    return {'flow': flow, 'definitions': [], 'fn_name': fn_name, 'fn_line': _lineno(fn_node)}


# ── Main dispatcher ───────────────────────────────────────────────

def extract_fn_flow(code: str, fn_name: str, lang: str = 'python', path: str = '<string>') -> dict:
    """
    提取任意函式的內部流程。

    Args:
        code:    完整原始程式碼
        fn_name: 函式名稱（支援 'ClassName.method' 格式）
        lang:    'python' | 'go' | 'rust'
        path:    檔案路徑（用於相對行號）

    Returns:
        {flow, definitions, fn_name, fn_line, error?}
    """
    if lang == 'go':
        return extract_go_fn(code, fn_name, path)
    elif lang == 'rust':
        return extract_rust_fn(code, fn_name, path)
    else:
        return extract_python_fn(code, fn_name, path)
