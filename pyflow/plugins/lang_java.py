"""
PyFlow Language Plugin — Java
==============================
Parser:  regex + brace-depth state machine
Format:  google-java-format / palantir-java-format
LSP:     Eclipse JDT Language Server (jdtls)
Tests:   Maven (mvn test) / Gradle (gradle test) / JUnit runner

Supports:
  - Classes, interfaces, enums, records, annotations (@interface)
  - Methods with access modifiers, generics, throws clauses
  - Constructors, static blocks, inner classes
  - Lambda expressions → 'lambda' flow nodes
  - Stream API chains  → 'context' flow nodes
  - Spring annotations → special qualifier icons
  - try-with-resources, multi-catch
  - Java 16+ records, sealed classes, text blocks
"""
from __future__ import annotations
import os, re, shutil, subprocess
from plugins import LanguagePlugin, register

# ── Spring/Jakarta annotations that get special icons ─────────────
_SPRING_ICONS = {
    'Controller': '🌐', 'RestController': '🌐', 'Service': '⚙',
    'Repository': '🗄', 'Component': '◈', 'Bean': '🫘',
    'Autowired': '⚡', 'Inject': '⚡', 'Configuration': '⚙',
    'SpringBootApplication': '🚀', 'Entity': '📦', 'Table': '📋',
}

# ── Patterns ──────────────────────────────────────────────────────
_P_IMPORT   = re.compile(r'^\s*import\s+(?:static\s+)?([\w.]+(?:\.\*)?)\s*;')
_P_PACKAGE  = re.compile(r'^\s*package\s+([\w.]+)\s*;')
_P_ANNOT    = re.compile(r'^\s*@(\w+)(?:\([^)]*\))?\s*$')
_P_CLASS    = re.compile(
    r'(?:public|protected|private|abstract|final|sealed|non-sealed|static)?\s*'
    r'(?:class|interface|enum|record|@interface)\s+(\w+)'
)
_P_METHOD   = re.compile(
    r'(?:(?:public|protected|private|static|final|abstract|synchronized|native|default|override)\s+)*'
    r'(?:<[^>]+>\s+)?'        # generics
    r'(?:[\w<>\[\],\s.?]+?)\s+'   # return type
    r'(\w+)\s*\('              # method name + (
)
_P_CTOR     = re.compile(r'(?:public|protected|private)?\s+(\w+)\s*\([^)]*\)\s*(?:throws\s+[\w,\s]+)?\s*\{')
_P_LAMBDA   = re.compile(r'(?:\([^)]*\)|\w+)\s*->')
_P_STREAM   = re.compile(r'\.(stream|filter|map|flatMap|collect|reduce|forEach|sorted|distinct|limit|skip|anyMatch|allMatch|noneMatch|findFirst|findAny)\s*\(')
_P_IF       = re.compile(r'^\s*(?:else\s+)?if\s*\(')
_P_ELSE     = re.compile(r'^\s*else\s*\{?$')
_P_FOR      = re.compile(r'^\s*for\s*\(')
_P_WHILE    = re.compile(r'^\s*while\s*\(')
_P_DO       = re.compile(r'^\s*do\s*\{?$')
_P_SWITCH   = re.compile(r'^\s*(?:yield\s+)?switch\s*[\(\{]')
_P_TRY      = re.compile(r'^\s*try\s*[\({]')
_P_CATCH    = re.compile(r'^\s*catch\s*\(')
_P_THROW    = re.compile(r'^\s*throw\b')
_P_RETURN   = re.compile(r'^\s*return\b')

_KW_SKIP = frozenset({'if','else','for','while','do','switch','try','catch','finally',
                      'throw','return','new','this','super','class','interface','enum',
                      'break','continue','instanceof','yield'})

def _strip_java_comment(line: str) -> str:
    """Remove // comment respecting strings."""
    in_str = False
    for j, c in enumerate(line):
        if c == '"' and (j == 0 or line[j-1] != '\\'): in_str = not in_str
        elif c == '/' and line[j:j+2] == '//' and not in_str:
            return line[:j]
    return line

def parse_java(code: str, path: str) -> dict:
    flow:  list = []
    defs:  list = []
    lines  = code.split('\n')

    # Remove block comments (preserve line count)
    clean = re.sub(r'/\*.*?\*/', lambda m: '\n' * m.group().count('\n'), code, flags=re.S)
    clean_lines = clean.split('\n')

    depth = 0          # brace depth
    step  = 0
    pending_annots: list[str] = []   # annotations collected before next declaration

    # Scope stack: {'type': 'class'|'method', 'name': str, 'depth': int, 'def': dict|None}
    scopes: list[dict] = []

    package = ''

    for i, (raw, cl) in enumerate(zip(lines, clean_lines), 1):
        s   = raw.strip()
        cls = cl.strip()
        if not s: depth += cls.count('{') - cls.count('}'); continue

        s_nc = _strip_java_comment(s)
        opens  = cls.count('{') - cls.count('\\{')
        closes = cls.count('}') - cls.count('\\}')
        new_depth = depth + opens - closes

        # Pop closed scopes
        while scopes and scopes[-1]['depth'] > new_depth:
            scopes.pop()

        top    = scopes[-1] if scopes else None
        in_cls = top and top['type'] == 'class'
        t_lvl  = depth == 0

        # ── Package ──────────────────────────────────────────────
        pm = _P_PACKAGE.match(s_nc)
        if pm:
            package = pm.group(1)
            flow.append({'id': 'package', 'type': 'import',
                         'label': 'package ' + pm.group(1), 'line': i, 'detail': s, 'calls': []})
            depth += opens - closes; continue

        # ── Import ────────────────────────────────────────────────
        im = _P_IMPORT.match(s_nc)
        if im:
            flow.append({'id': f'imp_{i}', 'type': 'import',
                         'label': 'import ' + im.group(1), 'line': i, 'detail': s, 'calls': []})
            depth += opens - closes; continue

        # ── Annotation line (collect) ─────────────────────────────
        am = _P_ANNOT.match(s_nc)
        if am:
            pending_annots.append(am.group(1))
            depth += opens - closes; continue

        # ── Class / Interface / Enum / Record ─────────────────────
        if re.search(r'\b(?:class|interface|enum|record|@interface)\b', s_nc) and depth <= (1 if package else 0) * 4 + 4:
            cm = _P_CLASS.search(s_nc)
            if cm:
                cname = cm.group(1)
                kind  = re.search(r'\b(class|interface|enum|record)\b', s_nc)
                kind  = kind.group(1) if kind else 'class'
                icon  = next((SPRING_ICONS_V.get(a) for a in pending_annots if a in _SPRING_ICONS), None)
                full_annots = [f'@{a}' for a in pending_annots]
                cls_def = {
                    'id': cname, 'type': 'class', 'label': cname,
                    'line': i, 'detail': ('; '.join(full_annots) + ' | ' if full_annots else '') + s_nc[:60],
                    'methods': [], 'is_async': False,
                    'qualifier_icon': icon,
                    'custom_decorators': full_annots,
                }
                defs.append(cls_def)
                pending_annots = []
                if opens > closes:
                    scopes.append({'type': 'class', 'name': cname,
                                   'depth': depth + opens - closes, 'def': cls_def})
                depth += opens - closes; continue

        # ── Method declaration ─────────────────────────────────────
        if in_cls and '(' in s_nc and opens > 0 and not any(
            kw in s_nc.split('(')[0] for kw in ('if','else','while','for','switch','try','catch')):
            mm = _P_METHOD.match(s_nc)
            if not mm:
                # Constructor
                mm2 = _P_CTOR.match(s_nc)
                if mm2 and mm2.group(1) not in _KW_SKIP and top and top['name'] == mm2.group(1):
                    mm_name = mm2.group(1)
                    icon = '⊕'
                    if top['def']:
                        top['def']['methods'].insert(0, {'id': mm_name + '()', 'label': mm_name,
                                                         'line': i, 'is_async': False, 'qualifier_icon': icon})
                    scopes.append({'type': 'method', 'name': mm_name,
                                   'depth': depth + opens - closes, 'def': None})
                    pending_annots = []
                    depth += opens - closes; continue
            if mm:
                mname = mm.group(1)
                if mname not in _KW_SKIP:
                    is_static  = 'static'  in s_nc[:mm.start(1)]
                    is_private = 'private' in s_nc[:mm.start(1)]
                    is_abs     = 'abstract' in s_nc[:mm.start(1)]
                    is_ovr     = 'Override' in pending_annots
                    ann_icon   = next((_SPRING_ICONS.get(a) for a in pending_annots if a in _SPRING_ICONS), None)
                    icon = ann_icon or ('◎' if is_static else ('🔒' if is_private else ('○' if is_abs else ('▲' if is_ovr else None))))
                    if top and top['def']:
                        top['def']['methods'].append({'id': (top['name'] + '.' + mname),
                                                      'label': mname, 'line': i,
                                                      'is_async': False, 'qualifier_icon': icon})
                    scopes.append({'type': 'method', 'name': mname,
                                   'depth': depth + opens - closes, 'def': None})
                    pending_annots = []
                    depth += opens - closes; continue

        pending_annots = []

        # ── Flow nodes inside methods / top-level ─────────────────
        if depth <= 6:
            if _P_IF.match(s_nc):
                flow.append({'id': f'cond_{i}', 'type': 'condition',
                             'label': s_nc[:64], 'line': i, 'detail': '', 'calls': []})
            elif _P_FOR.match(s_nc):
                # for-each vs traditional
                if ':' in s_nc.split(')')[0]:
                    m = re.search(r'for\s*\(\s*\w[\w<>, ]*\s+(\w+)\s*:\s*(\w+)', s_nc)
                    label = f'for ({m.group(1)} : {m.group(2)})' if m else s_nc[:60]
                else:
                    label = s_nc[:60]
                flow.append({'id': f'for_{i}', 'type': 'loop',
                             'label': label, 'line': i, 'detail': '', 'calls': []})
            elif _P_WHILE.match(s_nc) or _P_DO.match(s_nc):
                flow.append({'id': f'loop_{i}', 'type': 'loop',
                             'label': s_nc[:60], 'line': i, 'detail': '', 'calls': []})
            elif _P_SWITCH.match(s_nc):
                m = re.search(r'switch\s*[\(]?\s*(\w+)', s_nc)
                flow.append({'id': f'sw_{i}', 'type': 'match',
                             'label': f'switch {m.group(1) if m else ""}', 'line': i, 'detail': '', 'calls': []})
            elif _P_TRY.match(s_nc):
                # try-with-resources?
                label = 'try-with-resources' if '(' in s_nc else 'try'
                flow.append({'id': f'try_{i}', 'type': 'exception',
                             'label': label, 'line': i, 'detail': '', 'calls': []})
            elif _P_CATCH.match(s_nc):
                m = re.search(r'catch\s*\(\s*([\w|, ]+)', s_nc)
                label = f'catch ({m.group(1).strip()[:40]})' if m else 'catch'
                flow.append({'id': f'catch_{i}', 'type': 'exception',
                             'label': label, 'line': i, 'detail': '', 'calls': []})
            elif _P_THROW.match(s_nc):
                flow.append({'id': f'thr_{i}', 'type': 'exception',
                             'label': s_nc[:60], 'line': i, 'detail': '', 'calls': []})
            elif _P_RETURN.match(s_nc) and depth <= 4:
                flow.append({'id': f'ret_{i}', 'type': 'flow_ctrl',
                             'label': s_nc[:60], 'line': i, 'detail': '', 'calls': []})
            elif _P_LAMBDA.search(s_nc) and depth <= 4:
                flow.append({'id': f'lmb_{i}', 'type': 'context',
                             'label': s_nc[:60], 'line': i, 'detail': 'lambda →', 'calls': [], 'is_async': False})
            elif _P_STREAM.search(s_nc) and depth <= 4:
                m = _P_STREAM.search(s_nc)
                flow.append({'id': f'str_{i}', 'type': 'call',
                             'label': s_nc[:60], 'line': i, 'detail': f'.{m.group(1)}(…)', 'calls': []})

        depth = new_depth

    return {'flow': flow, 'definitions': defs, 'error': None, 'error_line': 0}

# Reference dict for icons
SPRING_ICONS_V = _SPRING_ICONS

def _extract_java_symbols(parse_result: dict) -> list:
    syms, seen = [], set()
    for d in parse_result.get('definitions', []):
        if d['id'] in seen: continue
        seen.add(d['id'])
        syms.append({'name': d['id'], 'kind': d['type'], 'line': d['line'],
                     'sig': d.get('detail','')[:80], 'doc': '', 'source': 'user',
                     'module': '', 'parent': ''})
        for m in d.get('methods', []):
            mn = m['label']
            if mn in seen: continue
            seen.add(mn)
            syms.append({'name': mn, 'kind': 'method', 'line': m['line'],
                         'sig': d['id'] + '.' + mn + '()', 'doc': '', 'source': 'user',
                         'module': d['id'], 'parent': d['id']})
    return syms


class JavaPlugin(LanguagePlugin):
    id          = 'java'
    name        = 'Java'
    version     = '1.0.0'
    extensions  = ['.java']
    monaco_id   = 'java'
    icon        = '☕'
    color       = '#B07219'
    description = 'Java — classes/interfaces/records, annotations, Stream API, Spring icons'

    def parse(self, code: str, path: str) -> dict:
        return parse_java(code, path)

    def extract_symbols(self, code: str, path: str, parse_result=None) -> list:
        return _extract_java_symbols(parse_result or self.parse(code, path))

    def format_code(self, code: str) -> dict | None:
        for cmd in [['google-java-format', '-'],
                    ['palantir-java-format', '--stdin'],
                    ['clang-format', '--style=google', '--assume-filename=A.java']]:
            if shutil.which(cmd[0]):
                r = subprocess.run(cmd, input=code, capture_output=True, text=True, timeout=15)
                return {'formatted': r.stdout if r.returncode == 0 else code,
                        'error': r.stderr.strip() or None, 'tool': cmd[0]}
        return None

    def get_lsp_command(self) -> list | None:
        # jdtls is usually installed in a directory
        for p in [shutil.which('jdtls'), shutil.which('java-language-server')]:
            if p: return [p]
        return None

    def run_tests(self, path: str) -> dict | None:
        cwd = os.path.dirname(os.path.abspath(path))
        # Walk up to find pom.xml or build.gradle
        p = cwd
        for _ in range(5):
            if os.path.exists(os.path.join(p, 'pom.xml')):
                if shutil.which('mvn'):
                    r = subprocess.run(['mvn', 'test', '-q'], cwd=p,
                                       capture_output=True, text=True, timeout=120)
                    ok = r.returncode == 0
                    return {'ok': ok, 'summary': {'passed': 0, 'failed': int(not ok),
                                                  'skipped': 0, 'errors': 0, 'duration': 0},
                            'results': [], 'output': (r.stdout+r.stderr)[-3000:], 'error': None}
            if os.path.exists(os.path.join(p, 'build.gradle')) or os.path.exists(os.path.join(p, 'build.gradle.kts')):
                grad = shutil.which('gradlew') or shutil.which('gradle')
                if grad:
                    r = subprocess.run([grad, 'test'], cwd=p,
                                       capture_output=True, text=True, timeout=120)
                    ok = r.returncode == 0
                    return {'ok': ok, 'summary': {'passed': 0, 'failed': int(not ok),
                                                  'skipped': 0, 'errors': 0, 'duration': 0},
                            'results': [], 'output': (r.stdout+r.stderr)[-3000:], 'error': None}
            parent = os.path.dirname(p)
            if parent == p: break
            p = parent
        return None

    def get_run_command(self, path: str) -> list | None:
        return None  # Java needs compilation; show in terminal

    def get_node_types(self) -> dict:
        return {
            'lambda':  {'n': 'Lambda →',  'c': '#1a2a3a'},
            'record':  {'n': 'Record',     'c': '#2a1a3a'},
            'context': {'n': 'Stream',     'c': '#1a1a3a'},
        }


register(JavaPlugin())
