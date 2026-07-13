"""
Python AST-based parser for PyFlow IDE.
Accurately handles: decorators, class qualifiers, async def,
type annotations, try/except/finally, comprehensions, and more.
Requires Python >= 3.9 (for ast.unparse).
"""
import ast
import sys
from typing import Any

# Python 3.11+ except* support
_TryStar = getattr(ast, 'TryStar', None)
_TryTypes = (ast.Try,) + ((_TryStar,) if _TryStar else ())

QUALIFIERS = {'staticmethod', 'classmethod', 'property',
               'abstractmethod', 'cached_property',
               'abc.abstractmethod', 'functools.cached_property'}

QUALIFIER_ICONS = {
    'staticmethod':  '⊡',
    'classmethod':   '⊠',
    'property':      '⊙',
    'abstractmethod':'◇',
    'cached_property':'⊙',
}


def _u(node) -> str:
    """Safely unparse an AST node."""
    try:
        return ast.unparse(node)
    except Exception:
        return '...'


def _trunc(s: str, n: int) -> str:
    if len(s) <= n:
        return s
    # Try to cut at a paren for readability
    p = s.find('(')
    if 0 < p < n:
        return s[:p] + '(…)'
    return s[:n] + '…'


def parse_python_file(code: str, path: str = '<string>') -> dict:
    """Entry point: parse Python source and return graph JSON."""
    try:
        tree = ast.parse(code, filename=path, type_comments=False)
    except SyntaxError as e:
        return {
            'flow': [], 'definitions': [],
            'error': f'SyntaxError 第 {e.lineno} 行: {e.msg}',
        }
    except Exception as e:
        return {'flow': [], 'definitions': [], 'error': str(e)}

    lines = code.splitlines()
    visitor = _Visitor(lines)
    visitor.process(tree)
    return {
        'flow':        visitor.flow,
        'definitions': visitor.defs,
        'error':       None,
    }


# ─── Decorator helpers ────────────────────────────────────────────

def _dec_info(dec: ast.expr) -> dict:
    if isinstance(dec, ast.Name):
        return {'name': dec.id, 'args': [], 'display': f'@{dec.id}'}
    if isinstance(dec, ast.Attribute):
        name = _u(dec)
        return {'name': name, 'args': [], 'display': f'@{name}'}
    if isinstance(dec, ast.Call):
        name = _u(dec.func)
        args = [_u(a) for a in dec.args]
        kwargs = {kw.arg: _u(kw.value) for kw in dec.keywords}
        arg_str = ', '.join(args + [f'{k}={v}' for k, v in kwargs.items()])
        return {'name': name, 'args': args, 'kwargs': kwargs,
                'display': f'@{name}({_trunc(arg_str, 30)})'}
    return {'name': _u(dec), 'args': [], 'display': f'@{_u(dec)}'}


def _get_qualifier(decs: list[dict]) -> str | None:
    for d in decs:
        n = d['name'].split('.')[-1]
        if n in QUALIFIERS or d['name'] in QUALIFIERS:
            return n
    return None


# ─── Main visitor class ───────────────────────────────────────────

class _Visitor:
    def __init__(self, lines: list[str]):
        self.lines = lines
        self.flow: list[dict] = []
        self.defs: list[dict] = []
        self._top_names: set[str] = set()
        self._uid = 0

    def _id(self, prefix='n') -> str:
        self._uid += 1
        return f'{prefix}_{self._uid}'

    def _src(self, lineno: int) -> str:
        if 1 <= lineno <= len(self.lines):
            return self.lines[lineno - 1].strip()
        return ''

    def process(self, tree: ast.Module):
        # Collect top-level definition names for call resolution
        for stmt in tree.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._top_names.add(stmt.name)
            elif isinstance(stmt, ast.ClassDef):
                self._top_names.add(stmt.name)

        for stmt in tree.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                self.defs.append(self._make_def(stmt))
            else:
                node = self._stmt_node(stmt)
                if node:
                    self.flow.append(node)

        self._resolve_calls(self.flow)

    def _resolve_calls(self, nodes: list[dict]):
        for n in nodes:
            n['calls'] = [c for c in n.get('calls', []) if c in self._top_names]
            self._resolve_calls(n.get('children', []))

    # ─── Definition builder ──────────────────────────────────────

    def _make_def(self, stmt) -> dict:
        is_class = isinstance(stmt, ast.ClassDef)
        is_async = isinstance(stmt, ast.AsyncFunctionDef)

        decs = [_dec_info(d) for d in stmt.decorator_list]
        qualifier = _get_qualifier(decs) if not is_class else None
        custom_decs = [d for d in decs
                       if d['name'].split('.')[-1] not in QUALIFIERS
                       and d['name'] not in QUALIFIERS]

        label, detail = self._def_labels(stmt, is_class, is_async, qualifier)

        d: dict = {
            'id':              stmt.name,
            'type':            'class' if is_class else 'function',
            'label':           label,
            'detail':          detail,
            'line':            stmt.lineno,
            'decorators':      decs,
            'custom_decorators': custom_decs,
            'qualifier':       qualifier,
            'qualifier_icon':  QUALIFIER_ICONS.get(qualifier or '', ''),
            'is_async':        is_async,
            'methods':         [],
        }

        if is_class:
            d['bases'] = [_u(b) for b in stmt.bases]
            for item in stmt.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    d['methods'].append(self._make_def(item))
            # Collect class-level assignments (class variables)
            class_vars = []
            for item in stmt.body:
                if isinstance(item, (ast.Assign, ast.AnnAssign)):
                    class_vars.append({
                        'label': _trunc(self._src(item.lineno), 50),
                        'line':  item.lineno,
                    })
            d['class_vars'] = class_vars

        return d

    def _def_labels(self, stmt, is_class: bool, is_async: bool, qualifier: str | None):
        if is_class:
            base_str = ''
            if stmt.bases:
                bases = ', '.join(_u(b) for b in stmt.bases[:3])
                base_str = f'({bases})'
            label  = _trunc(f'class {stmt.name}{base_str}', 46)
            detail = f'class {stmt.name}' + (f'({", ".join(_u(b) for b in stmt.bases)})' if stmt.bases else '')
            return label, detail

        # Function
        icon = QUALIFIER_ICONS.get(qualifier or '', '')
        prefix = (icon + ' ') if icon else ''
        async_p = 'async ' if is_async else ''
        args_str = self._fmt_args(stmt.args)
        ret = (f' → {_u(stmt.returns)}') if stmt.returns else ''
        label  = _trunc(f'{prefix}{async_p}def {stmt.name}({args_str}){ret}', 46)
        detail = f'{async_p}def {stmt.name}({args_str}){ret}'
        return label, detail

    def _fmt_args(self, args: ast.arguments) -> str:
        parts: list[str] = []
        # positional-only (3.8+)
        for a in getattr(args, 'posonlyargs', []):
            ann = (f': {_u(a.annotation)}') if a.annotation else ''
            parts.append(f'{a.arg}{ann}')
        for a in args.args:
            ann = (f': {_u(a.annotation)}') if a.annotation else ''
            parts.append(f'{a.arg}{ann}')
        if args.vararg:
            parts.append(f'*{args.vararg.arg}')
        for a in args.kwonlyargs:
            parts.append(a.arg)
        if args.kwarg:
            parts.append(f'**{args.kwarg.arg}')
        if len(parts) > 5:
            return ', '.join(parts[:4]) + ', …'
        return ', '.join(parts)

    # ─── Flow node builder ───────────────────────────────────────

    def _stmt_node(self, stmt) -> dict | None:
        if stmt is None:
            return None
        lineno = getattr(stmt, 'lineno', 0)
        src    = self._src(lineno)
        node: dict = {
            'id':       self._id(),
            'line':     lineno,
            'detail':   _trunc(src, 80),
            'children': [],
            'calls':    [],
        }

        if isinstance(stmt, (ast.Import, ast.ImportFrom)):
            node['type']  = 'import'
            node['label'] = _trunc(src or _u(stmt), 40)

        elif isinstance(stmt, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            node['type']  = 'assign'
            node['label'] = _trunc(src, 40)
            node['calls'] = self._calls_in(stmt)

        elif isinstance(stmt, ast.Expr):
            if isinstance(stmt.value, ast.Call):
                node['type']  = 'call'
                node['label'] = _trunc(src or _u(stmt.value), 40)
                node['calls'] = self._calls_in(stmt)
            else:
                node['type']  = 'other'
                node['label'] = _trunc(src, 40)

        elif isinstance(stmt, ast.If):
            node['type']     = 'condition'
            node['label']    = _trunc(f'if {_u(stmt.test)}', 40)
            node['detail']   = f'if {_u(stmt.test)}'
            node['children'] = self._process_if(stmt)

        elif isinstance(stmt, (ast.For, ast.AsyncFor)):
            ap = 'async ' if isinstance(stmt, ast.AsyncFor) else ''
            node['type']     = 'loop'
            node['label']    = _trunc(f'{ap}for {_u(stmt.target)} in {_u(stmt.iter)}', 40)
            node['children'] = self._body_nodes(stmt.body)

        elif isinstance(stmt, ast.While):
            node['type']     = 'loop'
            node['label']    = _trunc(f'while {_u(stmt.test)}', 40)
            node['children'] = self._body_nodes(stmt.body)

        elif isinstance(stmt, _TryTypes):
            node['type']     = 'exception'
            node['label']    = 'try:'
            node['children'] = self._process_try(stmt)

        elif isinstance(stmt, (ast.With, ast.AsyncWith)):
            ap = 'async ' if isinstance(stmt, ast.AsyncWith) else ''
            items = ', '.join(_u(item) for item in stmt.items)
            node['type']     = 'context'
            node['label']    = _trunc(f'{ap}with {items}', 40)
            node['children'] = self._body_nodes(stmt.body)

        elif isinstance(stmt, (ast.Return, ast.Yield, ast.YieldFrom)):
            node['type']  = 'flow_ctrl'
            node['label'] = _trunc(src or _u(stmt), 40)

        elif isinstance(stmt, ast.Raise):
            exc = f' {_u(stmt.exc)}' if stmt.exc else ''
            node['type']  = 'flow_ctrl'
            node['label'] = _trunc(f'raise{exc}', 40)

        elif isinstance(stmt, (ast.Break, ast.Continue, ast.Pass)):
            node['type']  = 'flow_ctrl'
            node['label'] = type(stmt).__name__.lower()

        elif isinstance(stmt, ast.Assert):
            node['type']  = 'other'
            node['label'] = _trunc(src or f'assert {_u(stmt.test)}', 40)

        elif isinstance(stmt, (ast.Global, ast.Nonlocal)):
            node['type']  = 'other'
            node['label'] = _trunc(src, 40)

        elif isinstance(stmt, ast.Delete):
            node['type']  = 'other'
            node['label'] = _trunc(src or 'del ...', 40)

        elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            # Nested def/class inside a flow block
            node['type']  = 'function' if not isinstance(stmt, ast.ClassDef) else 'class'
            node['label'] = _trunc(src, 40)

        else:
            node['type']  = 'other'
            node['label'] = _trunc(src, 40)

        return node

    def _body_nodes(self, stmts: list) -> list[dict]:
        result = []
        for s in stmts:
            # Skip nested def/class in flow body
            if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            n = self._stmt_node(s)
            if n:
                result.append(n)
        return result

    def _process_if(self, stmt: ast.If) -> list[dict]:
        children = self._body_nodes(stmt.body)
        if stmt.orelse:
            if len(stmt.orelse) == 1 and isinstance(stmt.orelse[0], ast.If):
                # elif
                elif_s = stmt.orelse[0]
                children.append({
                    'id':       self._id(),
                    'type':     'condition',
                    'label':    _trunc(f'elif {_u(elif_s.test)}', 40),
                    'detail':   f'elif {_u(elif_s.test)}:',
                    'line':     elif_s.lineno,
                    'children': self._process_if(elif_s),
                    'calls':    [],
                })
            else:
                # else
                else_line = stmt.orelse[0].lineno - 1 if stmt.orelse else stmt.lineno
                children.append({
                    'id':       self._id(),
                    'type':     'condition',
                    'label':    'else:',
                    'detail':   'else:',
                    'line':     max(1, else_line),
                    'children': self._body_nodes(stmt.orelse),
                    'calls':    [],
                })
        return children

    def _process_try(self, stmt) -> list[dict]:
        children = self._body_nodes(stmt.body)

        for h in stmt.handlers:
            exc_type = _u(h.type) if h.type else ''
            exc_name = h.name or ''
            label = 'except'
            if exc_type:
                label += f' {exc_type}'
            if exc_name:
                label += f' as {exc_name}'
            label += ':'
            children.append({
                'id':       self._id(),
                'type':     'exception',
                'label':    _trunc(label, 40),
                'detail':   label,
                'line':     h.lineno,
                'children': self._body_nodes(h.body),
                'calls':    [],
            })

        if stmt.orelse:
            children.append({
                'id':       self._id(),
                'type':     'exception',
                'label':    'else: (try 成功後)',
                'detail':   'else:',
                'line':     stmt.orelse[0].lineno,
                'children': self._body_nodes(stmt.orelse),
                'calls':    [],
            })

        if stmt.finalbody:
            children.append({
                'id':       self._id(),
                'type':     'exception',
                'label':    'finally:',
                'detail':   'finally:',
                'line':     stmt.finalbody[0].lineno,
                'children': self._body_nodes(stmt.finalbody),
                'calls':    [],
            })

        return children

    def _calls_in(self, node: ast.AST) -> list[str]:
        calls: list[str] = []
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    calls.append(child.func.id)
                elif isinstance(child.func, ast.Attribute):
                    calls.append(child.func.attr)
        return list(set(calls))
