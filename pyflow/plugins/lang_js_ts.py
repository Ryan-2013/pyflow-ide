"""
PyFlow Language Plugin — JavaScript / TypeScript (v2)
======================================================
Complete rewrite with proper scope-tracking parser.
Handles: ESM/CJS, classes+methods, arrow functions, async/await,
         TypeScript interfaces/enums/decorators, JSX, generics.
"""
from __future__ import annotations
import re, os, shutil, subprocess
from plugins import LanguagePlugin, register

# ── Keywords that are not function names ───────────────────────────
_KW = frozenset({
    'if','else','for','while','do','switch','case','default','break','continue',
    'return','throw','try','catch','finally','new','delete','typeof','instanceof',
    'void','in','of','import','export','from','as','class','extends','super',
    'this','true','false','null','undefined','let','const','var','async','await',
    'yield','static','get','set','function','debugger','with','arguments',
    'abstract','implements','interface','type','enum','namespace','declare',
    'public','private','protected','readonly','override',
})

def _preprocess(code: str) -> str:
    """Remove comments + string contents while preserving line count."""
    result, i, n = [], 0, len(code)
    while i < n:
        c = code[i]
        # Block comment
        if c == '/' and i+1 < n and code[i+1] == '*':
            j = code.find('*/', i+2)
            chunk = code[i:j+2] if j != -1 else code[i:]
            result.append('\n' * chunk.count('\n'))
            i = j + 2 if j != -1 else n
        # Line comment
        elif c == '/' and i+1 < n and code[i+1] == '/':
            j = code.find('\n', i)
            result.append('\n' if j != -1 else '')
            i = j if j != -1 else n
        # Template literal
        elif c == '`':
            result.append('`')
            i += 1
            depth = 0
            while i < n:
                cc = code[i]
                if cc == '\\' and i+1 < n:
                    result.append('  '); i += 2; continue
                if cc == '$' and i+1 < n and code[i+1] == '{':
                    result.append('${'); i += 2; depth += 1; continue
                if cc == '{' and depth > 0:
                    result.append('{'); i += 1; depth += 1; continue
                if cc == '}' and depth > 0:
                    result.append('}'); i += 1; depth -= 1; continue
                if cc == '`' and depth == 0:
                    result.append('`'); i += 1; break
                result.append('\n' if cc == '\n' else ' ')
                i += 1
        # Regular string
        elif c in ('"', "'"):
            result.append(c); i += 1
            while i < n:
                cc = code[i]
                if cc == '\\' and i+1 < n: result.append('  '); i += 2; continue
                if cc == '\n': result.append('\n'); i += 1; break
                if cc == c: result.append(c); i += 1; break
                result.append(' '); i += 1
        else:
            result.append(c); i += 1
    return ''.join(result)

def _fn_name_from_line(line: str) -> str | None:
    """Extract function/method name from a line."""
    # Standard: function foo(
    m = re.match(r'(?:export\s+)?(?:default\s+)?(?:async\s+)?function[*\s]+(\w+)\s*[\(<]', line)
    if m and m.group(1) not in _KW: return m.group(1)
    # Method shorthand: foo( or async foo( or static foo( or get foo( etc.
    m = re.match(r'(?:(?:public|private|protected|static|override|abstract|readonly|async|get|set)\s+)*(\w+)\s*(?:<[^>]*>)?\s*\(', line)
    if m and m.group(1) not in _KW: return m.group(1)
    return None

def _arrow_name(line: str) -> str | None:
    """Extract name from const foo = (...) => or const foo = async (...) =>"""
    m = re.match(r'(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(?:\([^)]*\)|\w+)\s*=>', line)
    return m.group(1) if m and m.group(1) not in _KW else None

def _class_name(line: str) -> str | None:
    m = re.match(r'(?:export\s+)?(?:default\s+)?(?:abstract\s+)?class\s+(\w+)', line)
    return m.group(1) if m else None

def _ts_type_name(line: str) -> tuple[str, str] | None:
    """Returns (name, kind) for TS interface/type/enum/namespace."""
    for kw in ('interface', 'type', 'enum', 'namespace'):
        m = re.match(rf'(?:export\s+)?(?:declare\s+)?{kw}\s+(\w+)', line)
        if m: return m.group(1), kw
    return None

def _import_label(line: str) -> str:
    return re.sub(r'\s+', ' ', line.strip())[:72]

def parse_js_ts(code: str, path: str, is_ts: bool = False) -> dict:
    """Scope-tracking JS/TS parser (v2)."""
    clean = _preprocess(code)
    raw_lines   = code.split('\n')
    clean_lines = clean.split('\n')

    flow: list = []
    defs: list = []
    step = 0

    # Scope stack: each entry = {'type': 'class'|'fn'|'obj'|'other', 'name': str, 'depth_open': int, 'def': dict|None}
    scopes: list = []
    depth = 0   # current brace depth

    for i, (raw, cl) in enumerate(zip(raw_lines, clean_lines), 1):
        s   = raw.strip()
        cls = cl.strip()
        if not s:
            depth += cls.count('{') - cls.count('}')
            continue

        opens  = cls.count('{')
        closes = cls.count('}')
        new_depth = depth + opens - closes

        # Pop closed scopes
        while scopes and scopes[-1]['depth_open'] > new_depth:
            popped = scopes.pop()

        top     = scopes[-1] if scopes else None
        in_cls  = top and top['type'] == 'class'
        top_lvl = depth == 0

        # ── Decorators (TypeScript) ────────────────────────────────
        if is_ts and re.match(r'@\w+', s) and depth <= 2:
            pass  # just note the decorator; next definition will be decorated

        # ── Import ────────────────────────────────────────────────
        if re.match(r'^import\s', s) or re.match(r'^(?:const|let|var)\s+\w+\s*=\s*require\s*\(', s):
            if depth <= 1:
                flow.append({'id': f'imp_{i}', 'type': 'import',
                             'label': _import_label(s), 'line': i, 'detail': s, 'calls': []})

        # ── Export (re-export) ────────────────────────────────────
        elif re.match(r'^export\s+(?:\{|\*)', s) and 'from' in s:
            if depth == 0:
                flow.append({'id': f'exp_{i}', 'type': 'import',
                             'label': _import_label(s), 'line': i, 'detail': s, 'calls': []})

        # ── Class declaration ─────────────────────────────────────
        elif _class_name(s) and depth <= 2:
            cname = _class_name(s)
            ia = False
            cls_def = {'id': cname, 'type': 'class', 'label': cname,
                       'line': i, 'detail': s[:80], 'methods': [], 'is_async': ia}
            defs.append(cls_def)
            if opens > closes:  # has a body open
                scopes.append({'type': 'class', 'name': cname,
                               'depth_open': depth + opens - closes, 'def': cls_def})
            step += 1
            flow.append({'id': f'cls_{cname}', 'type': 'call',
                         'label': cname + ' {}', 'line': i, 'detail': '', 'calls': [cname], 'step': step})

        # ── TypeScript: interface / type / enum / namespace ───────
        elif is_ts and _ts_type_name(s) and depth <= 2:
            tname, tkind = _ts_type_name(s)
            icon_map = {'interface': '◻', 'type': '≡', 'enum': '⊞', 'namespace': '⊡'}
            defs.append({'id': tname, 'type': 'class', 'label': tname,
                         'line': i, 'detail': f'{tkind}: {s[:60]}', 'methods': [],
                         'is_async': False, 'qualifier_icon': icon_map.get(tkind, '◻')})

        # ── Function declaration (top-level or exported) ──────────
        elif re.match(r'(?:export\s+)?(?:default\s+)?(?:async\s+)?function', s) and depth <= 1:
            fname = _fn_name_from_line(s) or 'fn'
            ia = bool(re.search(r'\basync\b', s[:40]))
            step += 1
            fn_def = {'id': fname, 'type': 'function', 'label': fname,
                      'line': i, 'detail': s[:80], 'methods': [], 'is_async': ia}
            defs.append(fn_def)
            flow.append({'id': f'fn_{fname}_{i}', 'type': 'context' if ia else 'call',
                         'label': fname + '()', 'line': i, 'detail': '', 'calls': [fname], 'step': step})
            if opens > closes:
                scopes.append({'type': 'fn', 'name': fname,
                               'depth_open': depth + opens - closes, 'def': fn_def})

        # ── Arrow function assignment ──────────────────────────────
        elif _arrow_name(s) and depth <= 1:
            aname = _arrow_name(s)
            ia = bool(re.search(r'\basync\b', s[:60]))
            step += 1
            fn_def = {'id': aname, 'type': 'function', 'label': aname,
                      'line': i, 'detail': s[:80], 'methods': [], 'is_async': ia}
            defs.append(fn_def)
            flow.append({'id': f'fn_{aname}_{i}', 'type': 'context' if ia else 'call',
                         'label': aname + '()', 'line': i, 'detail': '', 'calls': [aname], 'step': step})
            if opens > closes:
                scopes.append({'type': 'fn', 'name': aname,
                               'depth_open': depth + opens - closes, 'def': fn_def})

        # ── Class methods ─────────────────────────────────────────
        elif in_cls and top and depth == scopes[-1].get('depth_open', 999):
            mname = _fn_name_from_line(s)
            if mname and opens > closes:
                ia = bool(re.search(r'\basync\b', s[:40]))
                is_static = bool(re.search(r'\bstatic\b', s[:40]))
                is_private = mname.startswith('#') or bool(re.search(r'\bprivate\b', s[:30]))
                is_get_set = bool(re.match(r'(?:get|set)\s+\w', s))
                icon = '◎' if is_static else ('🔒' if is_private else ('⇌' if is_get_set else None))
                if top['def']:
                    top['def']['methods'].append({
                        'id': top['name'] + '.' + mname, 'label': mname,
                        'line': i, 'is_async': ia, 'qualifier_icon': icon,
                    })
                scopes.append({'type': 'fn', 'name': mname,
                               'depth_open': depth + opens - closes, 'def': None})

        # ── Flow nodes inside functions / top-level ───────────────
        if depth <= 2:
            if re.match(r'(?:else\s+)?if\s*\(', s):
                flow.append({'id': f'cond_{i}', 'type': 'condition',
                             'label': s[:64], 'line': i, 'detail': '', 'calls': []})
            elif re.match(r'(?:for|while|do)\b', s) and (re.search(r'\(', s) or s.startswith('do')):
                kw = re.match(r'(\w+)', s).group(1)
                flow.append({'id': f'loop_{i}', 'type': 'loop',
                             'label': f'{kw} (…)', 'line': i, 'detail': '', 'calls': []})
            elif re.match(r'switch\s*\(', s):
                flow.append({'id': f'sw_{i}', 'type': 'match',
                             'label': s[:50], 'line': i, 'detail': '', 'calls': []})
            elif re.match(r'try\s*\{', s):
                flow.append({'id': f'try_{i}', 'type': 'exception',
                             'label': 'try', 'line': i, 'detail': '', 'calls': []})
            elif re.match(r'throw\b', s):
                flow.append({'id': f'thr_{i}', 'type': 'exception',
                             'label': s[:50], 'line': i, 'detail': '', 'calls': []})
            elif 'await ' in s and depth == 0:
                flow.append({'id': f'aw_{i}', 'type': 'context',
                             'label': s[:60], 'line': i, 'detail': '', 'calls': [], 'is_async': True})
            elif re.match(r'return\b', s) and depth <= 1:
                flow.append({'id': f'ret_{i}', 'type': 'flow_ctrl',
                             'label': s[:60], 'line': i, 'detail': '', 'calls': []})
            elif re.match(r'(?:const|let|var)\s+\w+\s*=\s*(?!.*=>)', s) and ';' in s and depth == 0:
                flow.append({'id': f'asgn_{i}', 'type': 'assign',
                             'label': s[:64], 'line': i, 'detail': '', 'calls': []})

        depth = new_depth

    return {'flow': flow, 'definitions': defs, 'error': None, 'error_line': 0}

def _extract_js_symbols(parse_result: dict) -> list:
    syms, seen = [], set()
    for d in parse_result.get('definitions', []):
        if d['id'] in seen: continue
        seen.add(d['id'])
        syms.append({'name': d['id'], 'kind': d['type'], 'line': d['line'],
                     'sig': d.get('detail','')[:80], 'doc': '', 'source': 'user',
                     'module': '', 'parent': ''})
        for m in d.get('methods', []):
            mid = d['id'] + '.' + m['label']
            if mid in seen: continue
            seen.add(mid)
            syms.append({'name': m['label'], 'kind': 'method', 'line': m['line'],
                         'sig': mid + '()', 'doc': '', 'source': 'user',
                         'module': d['id'], 'parent': d['id']})
    return syms

def _format_js(code: str, is_ts: bool = False) -> dict | None:
    parser = 'typescript' if is_ts else 'babel'
    for cmd, args in [
        (['prettier'], ['--parser', parser]),
        (['biome'],    ['format', '--stdin-file-path', 'a.ts' if is_ts else 'a.js']),
        (['deno', 'fmt'], ['--ext', 'ts' if is_ts else 'js', '-']),
    ]:
        if shutil.which(cmd[0]):
            r = subprocess.run(cmd + args, input=code, capture_output=True, text=True, timeout=10)
            return {'formatted': r.stdout if r.returncode == 0 else code,
                    'error': r.stderr.strip() or None, 'tool': cmd[0]}
    return {'formatted': code, 'error': '未找到格式化工具（prettier/biome/deno）', 'tool': ''}

def _run_js_tests(path: str) -> dict | None:
    cwd = os.path.dirname(os.path.abspath(path))
    for _ in range(4):
        if os.path.exists(os.path.join(cwd, 'package.json')): break
        parent = os.path.dirname(cwd)
        if parent == cwd: break
        cwd = parent
    for tool, cmd in [
        ('vitest', ['npx', 'vitest', 'run', '--reporter=json']),
        ('jest',   ['npx', 'jest', '--json', '--no-coverage']),
    ]:
        if shutil.which('npx'):
            r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=60)
            if r.returncode in (0, 1):
                try:
                    import json; d = json.loads(r.stdout)
                    results = []
                    for s in d.get('testResults', []):
                        for t in s.get('assertionResults', []):
                            results.append({'name': t.get('fullName',''), 'status': t.get('status',''),
                                           'duration': t.get('duration',0)/1000, 'message': '\n'.join(t.get('failureMessages',[]))})
                    return {'ok': d.get('success', False), 'results': results,
                            'output': r.stdout[-2000:], 'error': None,
                            'summary': {'passed': d.get('numPassedTests',0), 'failed': d.get('numFailedTests',0),
                                        'skipped': 0, 'errors': 0, 'duration': 0}}
                except Exception: pass
    return None

class JavaScriptPlugin(LanguagePlugin):
    id='javascript'; name='JavaScript'; version='2.0.0'
    extensions=['.js','.mjs','.cjs','.jsx']; monaco_id='javascript'
    icon='🟨'; color='#F7DF1E'
    description='JavaScript — ESM/CJS/JSX, classes+methods, async/await, arrow functions'
    def parse(self, code, path): return parse_js_ts(code, path, is_ts=False)
    def extract_symbols(self, code, path, parse_result=None): return _extract_js_symbols(parse_result or self.parse(code,path))
    def format_code(self, code): return _format_js(code, False)
    def get_lsp_command(self):
        for cmd in [['typescript-language-server','--stdio'],['vscode-json-languageserver','--stdio']]:
            if shutil.which(cmd[0]): return cmd
        return None
    def run_tests(self, path): return _run_js_tests(path)
    def get_run_command(self, path):
        for rt in ['node','deno','bun']:
            if shutil.which(rt): return [rt, path]
        return None
    def get_node_types(self): return {'await_expr': {'n':'await','c':'#1a2a1a'}}

class TypeScriptPlugin(LanguagePlugin):
    id='typescript'; name='TypeScript'; version='2.0.0'
    extensions=['.ts','.tsx','.mts','.cts']; monaco_id='typescript'
    icon='🔷'; color='#3178C6'
    description='TypeScript — interfaces, generics, enums, decorators, namespace'
    def parse(self, code, path): return parse_js_ts(code, path, is_ts=True)
    def extract_symbols(self, code, path, parse_result=None): return _extract_js_symbols(parse_result or self.parse(code,path))
    def format_code(self, code): return _format_js(code, True)
    def get_lsp_command(self):
        for cmd in [['typescript-language-server','--stdio'],['tsserver']]:
            if shutil.which(cmd[0]): return cmd
        return None
    def run_tests(self, path): return _run_js_tests(path)
    def get_run_command(self, path):
        for rt in ['deno','ts-node','bun']:
            if shutil.which(rt): return [rt, 'run', path]
        return None
    def get_node_types(self):
        return {'interface':{'n':'Interface','c':'#1e2a4a'},'enum':{'n':'Enum','c':'#2a1e3a'},
                'decorator':{'n':'Decorator','c':'#3a2a1a'},'await_expr':{'n':'await','c':'#1a2a1a'}}

register(JavaScriptPlugin())
register(TypeScriptPlugin())
