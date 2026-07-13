"""
PyFlow Language Plugin — Shell / Bash / Zsh / Fish
====================================================
Parser:  regex + line-by-line state machine
Format:  shfmt (shell script formatter)
LSP:     bash-language-server
Tests:   bats (Bash Automated Testing System)

Unique visualizations:
  - Pipeline chains  (cmd1 | cmd2 | cmd3) as connected nodes
  - Background jobs  (cmd &)              as goroutine-like nodes
  - Trap handlers    (trap ... EXIT/ERR)  as exception nodes
  - Source/dot       (source ./lib.sh)    as import nodes
  - Heredoc          (<<EOF)              as context nodes
"""
from __future__ import annotations
import re, shutil, subprocess
from plugins import LanguagePlugin, register

# ── Patterns ──────────────────────────────────────────────────────

_P_FUNC = re.compile(
    r'^(?:function\s+(\w[\w.:-]*)\s*(?:\(\s*\))?'   # function foo() or function foo
    r'|(\w[\w.:-]*)\s*\(\s*\))'                       # foo()
    r'\s*\{?\s*$'
)
_P_SOURCE = re.compile(r'^\s*(?:source|\.|\.)\s+(\S+)')
_P_EXPORT = re.compile(r'^\s*export\s+(?:-[a-z]\s+)?(\w+)(?:=|$)')
_P_ASSIGN = re.compile(r'^\s*(?:local\s+|declare\s+[^=]*\s+)?(\w+)=')
_P_IF     = re.compile(r'^\s*(?:elif\s+|if\s+)')
_P_FOR    = re.compile(r'^\s*for\s+')
_P_WHILE  = re.compile(r'^\s*while\s+')
_P_UNTIL  = re.compile(r'^\s*until\s+')
_P_CASE   = re.compile(r'^\s*case\s+')
_P_TRAP   = re.compile(r'^\s*trap\s+')
_P_RETURN = re.compile(r'^\s*return\b')
_P_EXIT   = re.compile(r'^\s*exit\b')
_P_PIPE   = re.compile(r'\|\s*\w')
_P_BG     = re.compile(r'&\s*$|&\s*#')
_P_HEREDOC= re.compile(r'<<-?\s*[\'"]?(\w+)[\'"]?')
_P_CMD_SUB= re.compile(r'\$\((.{1,40})\)')
_P_SHEBANG= re.compile(r'^#!\s*(/\S+)')

_BUILTINS = frozenset({
    'echo','printf','read','cd','ls','cat','grep','sed','awk','cut','sort',
    'uniq','wc','head','tail','find','xargs','mkdir','rm','cp','mv','touch',
    'chmod','chown','ln','test','[','[[','true','false','pwd','env','set',
    'unset','shift','getopts','eval','exec','wait','sleep','date','kill',
    'ps','which','type','hash','alias','unalias','readonly','local','declare',
    'typeset','let','expr','basename','dirname','realpath','stat','file',
})

def _strip_sh_comment(line: str) -> str:
    """Remove inline comment from a line, respecting quoted strings."""
    in_sq = in_dq = False
    for j, c in enumerate(line):
        if c == "'" and not in_dq: in_sq = not in_sq
        elif c == '"' and not in_sq: in_dq = not in_dq
        elif c == '#' and not in_sq and not in_dq:
            return line[:j].rstrip()
    return line

def _first_cmd(line: str) -> str:
    """Return the first command/word of a line."""
    stripped = line.strip()
    m = re.match(r'(\w[\w./:-]*)', stripped)
    return m.group(1) if m else stripped[:20]

def _pipe_label(line: str) -> str:
    """Summarize a pipeline."""
    parts = re.split(r'\s*\|\s*', line.strip())
    if len(parts) <= 1:
        return line.strip()[:60]
    cmds = [_first_cmd(p) for p in parts[:4]]
    suffix = ' | …' if len(parts) > 4 else ''
    return ' | '.join(cmds) + suffix

def parse_shell(code: str, path: str) -> dict:
    flow:   list = []
    defs:   list = []
    lines = code.split('\n')

    step        = 0
    in_fn       = False
    fn_name     = None
    fn_brace    = 0
    brace_depth = 0
    heredoc_end = None  # token to end a heredoc

    for i, raw in enumerate(lines, 1):
        # End heredoc
        if heredoc_end:
            if raw.strip() == heredoc_end or raw.strip() == heredoc_end.strip("\"'"):
                heredoc_end = None
            continue

        line = _strip_sh_comment(raw)
        stripped = line.strip()

        if not stripped:
            continue

        # Shebang → show as import
        if i == 1 and _P_SHEBANG.match(stripped):
            m = _P_SHEBANG.match(stripped)
            flow.append({'id': 'shebang', 'type': 'import',
                         'label': stripped, 'line': 1, 'detail': m.group(1), 'calls': []})
            continue

        # Skip comment-only lines
        if stripped.startswith('#'):
            continue

        # Detect heredoc start
        hm = _P_HEREDOC.search(stripped)
        if hm:
            heredoc_end = hm.group(1)

        # Track brace depth
        opens  = line.count('{') - line.count('\\{')
        closes = line.count('}') - line.count('\\}')

        # ── Function definition ────────────────────────────────────
        fm = _P_FUNC.match(stripped)
        if fm:
            fname = fm.group(1) or fm.group(2)
            if fname:
                in_fn    = True
                fn_name  = fname
                fn_brace = brace_depth + 1
                step += 1
                defs.append({'id': fname, 'type': 'function', 'label': fname,
                             'line': i, 'detail': stripped[:70], 'methods': [], 'is_async': False})
                flow.append({'id': f'fn_{fname}', 'type': 'call',
                             'label': fname + '()', 'line': i, 'detail': '', 'calls': [fname], 'step': step})
                brace_depth += opens - closes
                continue

        # Exit function when brace depth drops
        if in_fn and brace_depth <= fn_brace - 1:
            in_fn = False; fn_name = None

        brace_depth += opens - closes

        # ── Source / . ────────────────────────────────────────────
        sm = _P_SOURCE.match(stripped)
        if sm:
            flow.append({'id': f'src_{i}', 'type': 'import',
                         'label': f'source {sm.group(1)}', 'line': i, 'detail': stripped, 'calls': []})
            continue

        # ── Trap ──────────────────────────────────────────────────
        if _P_TRAP.match(stripped):
            flow.append({'id': f'trap_{i}', 'type': 'exception',
                         'label': stripped[:60], 'line': i, 'detail': stripped, 'calls': []})
            continue

        # ── Control flow ───────────────────────────────────────────
        if _P_IF.match(stripped):
            flow.append({'id': f'cond_{i}', 'type': 'condition',
                         'label': stripped[:60], 'line': i, 'detail': '', 'calls': []})
            continue

        if _P_FOR.match(stripped):
            m = re.match(r'for\s+(\w+)\s+in\s+(.{0,30})', stripped)
            label = f'for {m.group(1)} in {m.group(2)}…' if m else stripped[:60]
            flow.append({'id': f'for_{i}', 'type': 'loop',
                         'label': label, 'line': i, 'detail': '', 'calls': []})
            continue

        if _P_WHILE.match(stripped):
            flow.append({'id': f'while_{i}', 'type': 'loop',
                         'label': stripped[:60], 'line': i, 'detail': '', 'calls': []})
            continue

        if _P_UNTIL.match(stripped):
            flow.append({'id': f'until_{i}', 'type': 'loop',
                         'label': stripped[:60], 'line': i, 'detail': '', 'calls': []})
            continue

        if _P_CASE.match(stripped):
            m = re.match(r'case\s+(\S+)', stripped)
            label = f'case {m.group(1)}' if m else 'case'
            flow.append({'id': f'case_{i}', 'type': 'match',
                         'label': label, 'line': i, 'detail': '', 'calls': []})
            continue

        # ── Return / exit ──────────────────────────────────────────
        if _P_RETURN.match(stripped) or _P_EXIT.match(stripped):
            flow.append({'id': f'ret_{i}', 'type': 'flow_ctrl',
                         'label': stripped[:50], 'line': i, 'detail': '', 'calls': []})
            continue

        # ── Export ────────────────────────────────────────────────
        if _P_EXPORT.match(stripped):
            flow.append({'id': f'exp_{i}', 'type': 'assign',
                         'label': stripped[:60], 'line': i, 'detail': '', 'calls': []})
            continue

        # ── Variable assignment ───────────────────────────────────
        if _P_ASSIGN.match(stripped) and '(' not in stripped:
            flow.append({'id': f'var_{i}', 'type': 'assign',
                         'label': stripped[:60], 'line': i, 'detail': '', 'calls': []})
            continue

        # ── Pipeline ──────────────────────────────────────────────
        if _P_PIPE.search(stripped):
            label = _pipe_label(stripped)
            # Extract called commands as "calls"
            cmds  = [_first_cmd(p) for p in re.split(r'\s*\|\s*', stripped) if _first_cmd(p) not in _BUILTINS]
            flow.append({'id': f'pipe_{i}', 'type': 'call',
                         'label': label, 'line': i, 'detail': stripped, 'calls': cmds})
            continue

        # ── Background process ────────────────────────────────────
        if _P_BG.search(stripped):
            flow.append({'id': f'bg_{i}', 'type': 'goroutine',
                         'label': stripped[:60] + ' &', 'line': i, 'detail': stripped, 'calls': []})
            continue

        # ── Heredoc ───────────────────────────────────────────────
        if heredoc_end:
            flow.append({'id': f'hd_{i}', 'type': 'context',
                         'label': f'<<{heredoc_end}', 'line': i, 'detail': stripped, 'calls': []})
            continue

        # ── Generic command call ───────────────────────────────────
        cmd = _first_cmd(stripped)
        if cmd and cmd not in _BUILTINS and not cmd.startswith(('fi','done','esac','then','do','elif','else',';;')):
            calls = [cmd] if cmd in (d['id'] for d in defs) else []
            flow.append({'id': f'cmd_{i}', 'type': 'call',
                         'label': stripped[:64], 'line': i, 'detail': stripped, 'calls': calls})

    return {'flow': flow, 'definitions': defs, 'error': None, 'error_line': 0}


class ShellPlugin(LanguagePlugin):
    id          = 'shell'
    name        = 'Shell Script'
    version     = '1.0.0'
    extensions  = ['.sh', '.bash', '.zsh', '.fish', '.ksh', '.dash']
    monaco_id   = 'shell'
    icon        = '🐚'
    color       = '#89E051'
    description = 'Shell/Bash/Zsh — pipeline visualization, trap/heredoc, background jobs'

    def parse(self, code: str, path: str) -> dict:
        return parse_shell(code, path)

    def extract_symbols(self, code: str, path: str, parse_result=None) -> list:
        r = parse_result or self.parse(code, path)
        return [{'name': d['id'], 'kind': 'function', 'line': d['line'],
                 'sig': d.get('detail', ''), 'doc': '', 'source': 'user',
                 'module': '', 'parent': ''}
                for d in r.get('definitions', [])]

    def format_code(self, code: str) -> dict | None:
        if shutil.which('shfmt'):
            r = subprocess.run(['shfmt', '-i', '2', '-ci'], input=code,
                               capture_output=True, text=True, timeout=10)
            return {'formatted': r.stdout if r.returncode == 0 else code,
                    'error': r.stderr.strip() or None, 'tool': 'shfmt'}
        return None

    def get_lsp_command(self) -> list | None:
        for cmd in [['bash-language-server', 'start'],
                    ['shellcheck', '--format=json']]:
            if shutil.which(cmd[0]): return cmd
        return None

    def run_tests(self, path: str) -> dict | None:
        if shutil.which('bats'):
            import os
            r = subprocess.run(['bats', '--tap', path],
                               cwd=os.path.dirname(os.path.abspath(path)),
                               capture_output=True, text=True, timeout=60)
            ok = r.returncode == 0
            passed = len(re.findall(r'^ok ', r.stdout, re.M))
            failed = len(re.findall(r'^not ok ', r.stdout, re.M))
            return {'ok': ok, 'summary': {'passed': passed, 'failed': failed,
                                          'skipped': 0, 'errors': 0, 'duration': 0},
                    'results': [], 'output': r.stdout[-2000:], 'error': None}
        return None

    def get_run_command(self, path: str) -> list | None:
        if shutil.which('bash'): return ['bash', path]
        if shutil.which('sh'):   return ['sh', path]
        return None

    def get_node_types(self) -> dict:
        return {
            'goroutine': {'n': 'Background &', 'c': '#1a3a1a'},
            'exception': {'n': 'trap',          'c': '#3a1a0a'},
        }


register(ShellPlugin())
