"""
PyFlow Language Plugin — Go (v2)
==================================
增強版 Go 解析器，委派給 core/go_parser.py
新增更豐富的流程節點：
- goroutine 顯示被呼叫的函式名稱
- channel 方向（發送 ← / 接收 →）
- select case 展開
- defer 堆疊感知
- error wrapping (%w) 標記
- interface / struct method 方法列表
"""
from __future__ import annotations
import re, shutil, subprocess, os
from plugins import LanguagePlugin, register

# Additional Go flow patterns
_P_GOROUTINE = re.compile(r'\bgo\s+(\w+(?:\.\w+)?)\s*\(')
_P_GO_FUNC   = re.compile(r'\bgo\s+func\s*\(')
_P_CHAN_SEND = re.compile(r'(\w+)\s*<-\s*(\w+)')
_P_CHAN_RECV = re.compile(r'(\w+)\s*:?=\s*<-\s*(\w+)')
_P_SELECT    = re.compile(r'^\s*select\s*\{')
_P_CASE_CHAN = re.compile(r'^\s*case\s+(?:.+\s*<-\s*.+|<-\s*\w+):')
_P_DEFER     = re.compile(r'^\s*defer\s+(\w+(?:\.\w+)?)\s*\(')
_P_ERR_WRAP  = re.compile(r'fmt\.Errorf\s*\([^)]*%w[^)]*\)')
_P_IF_ERR    = re.compile(r'^\s*if\s+err\s*!=\s*nil')
_P_PANIC     = re.compile(r'\bpanic\s*\(')
_P_RECOVER   = re.compile(r'\brecover\s*\(\s*\)')
_P_MAKE_CHAN = re.compile(r'\bmake\s*\(\s*chan\s+')
_P_CLOSE_CH  = re.compile(r'\bclose\s*\(\s*(\w+)\s*\)')
_P_WG_WAIT   = re.compile(r'\bwg\.Wait\s*\(')
_P_WG_DONE   = re.compile(r'\bwg\.Done\s*\(')


def parse_go(code: str, path: str) -> dict:
    """Delegate to core go_parser then enhance flow nodes."""
    try:
        from core.go_parser import parse_go_file
        result = parse_go_file(code, path)
    except Exception:
        result = {'flow': [], 'definitions': [], 'error': None, 'error_line': 0}

    # Post-process: enhance flow nodes with Go-specific semantics
    extra_flow = []
    lines = code.split('\n')

    for i, raw in enumerate(lines, 1):
        s = raw.strip()
        if not s or s.startswith('//'):
            continue

        # goroutine with named function
        m = _P_GOROUTINE.search(s)
        if m:
            extra_flow.append({'id': f'go_{i}', 'type': 'goroutine',
                               'label': f'go {m.group(1)}()', 'line': i,
                               'detail': s[:60], 'calls': [m.group(1)]})
            continue

        # goroutine with anonymous function
        if _P_GO_FUNC.search(s):
            extra_flow.append({'id': f'go_anon_{i}', 'type': 'goroutine',
                               'label': 'go func() { … }', 'line': i,
                               'detail': s[:60], 'calls': []})
            continue

        # channel send
        m = _P_CHAN_SEND.search(s)
        if m and '<-' in s and ':=' not in s[:s.index('<-')]:
            extra_flow.append({'id': f'chs_{i}', 'type': 'context',
                               'label': f'{m.group(1)} ← {m.group(2)}',
                               'line': i, 'detail': 'channel send', 'calls': []})

        # channel receive
        m = _P_CHAN_RECV.search(s)
        if m:
            extra_flow.append({'id': f'chr_{i}', 'type': 'context',
                               'label': f'{m.group(1)} ← <-{m.group(2)}',
                               'line': i, 'detail': 'channel receive', 'calls': []})

        # make chan
        if _P_MAKE_CHAN.search(s):
            extra_flow.append({'id': f'mkch_{i}', 'type': 'assign',
                               'label': s[:55], 'line': i,
                               'detail': 'make channel', 'calls': []})

        # close channel
        m = _P_CLOSE_CH.search(s)
        if m:
            extra_flow.append({'id': f'clch_{i}', 'type': 'flow_ctrl',
                               'label': f'close({m.group(1)})', 'line': i,
                               'detail': 'close channel', 'calls': []})

        # select
        if _P_SELECT.match(s):
            extra_flow.append({'id': f'sel_{i}', 'type': 'match',
                               'label': 'select { … }', 'line': i,
                               'detail': 'channel select', 'calls': []})

        # defer
        m = _P_DEFER.match(s)
        if m:
            extra_flow.append({'id': f'def_{i}', 'type': 'flow_ctrl',
                               'label': f'defer {m.group(1)}()', 'line': i,
                               'detail': 'deferred call', 'calls': [m.group(1)]})

        # if err != nil (error handling — very common in Go)
        if _P_IF_ERR.match(s):
            extra_flow.append({'id': f'err_{i}', 'type': 'exception',
                               'label': 'if err != nil', 'line': i,
                               'detail': 'error check', 'calls': []})

        # fmt.Errorf with %w (error wrapping)
        if _P_ERR_WRAP.search(s):
            extra_flow.append({'id': f'wrap_{i}', 'type': 'exception',
                               'label': s[:50], 'line': i,
                               'detail': 'error wrap %w', 'calls': []})

        # panic / recover
        if _P_PANIC.search(s):
            extra_flow.append({'id': f'pnc_{i}', 'type': 'exception',
                               'label': s[:50], 'line': i,
                               'detail': 'panic', 'calls': []})
        if _P_RECOVER.search(s):
            extra_flow.append({'id': f'rec_{i}', 'type': 'exception',
                               'label': 'recover()', 'line': i,
                               'detail': 'recover from panic', 'calls': []})

        # WaitGroup
        if _P_WG_WAIT.search(s):
            extra_flow.append({'id': f'wgw_{i}', 'type': 'context',
                               'label': 'wg.Wait()', 'line': i,
                               'detail': 'sync: wait goroutines', 'calls': []})
        if _P_WG_DONE.search(s):
            extra_flow.append({'id': f'wgd_{i}', 'type': 'context',
                               'label': 'wg.Done()', 'line': i,
                               'detail': 'sync: goroutine done', 'calls': []})

    # Merge extra flow nodes, avoiding duplicates by line
    existing_lines = {n['line'] for n in result.get('flow', [])}
    for node in extra_flow:
        if node['line'] not in existing_lines:
            result['flow'].append(node)

    return result


class GoPlugin(LanguagePlugin):
    id          = 'go'
    name        = 'Go'
    version     = '2.0.0'
    extensions  = ['.go']
    monaco_id   = 'go'
    icon        = '🐹'
    color       = '#00ADD8'
    description = 'Go — goroutine/channel/select/defer/error-wrap visualization'

    def parse(self, code: str, path: str) -> dict:
        return parse_go(code, path)

    def extract_symbols(self, code, path, parse_result=None):
        r = parse_result or self.parse(code, path)
        syms = []
        for d in r.get('definitions', []):
            syms.append({'name': d['id'], 'kind': d['type'], 'line': d['line'],
                         'sig': d.get('detail', '')[:80], 'doc': '', 'source': 'user',
                         'module': '', 'parent': ''})
            for m in d.get('methods', []):
                syms.append({'name': m['label'], 'kind': 'method', 'line': m['line'],
                             'sig': d['id'] + '.' + m['label'] + '()', 'doc': '',
                             'source': 'user', 'module': d['id'], 'parent': d['id']})
        return syms

    def format_code(self, code: str) -> dict | None:
        if shutil.which('gofmt'):
            r = subprocess.run(['gofmt'], input=code, capture_output=True,
                               text=True, timeout=10)
            return {'formatted': r.stdout if r.returncode == 0 else code,
                    'error': r.stderr.strip() or None, 'tool': 'gofmt'}
        return None

    def get_lsp_command(self) -> list | None:
        if shutil.which('gopls'): return ['gopls', 'serve']
        return None

    def run_tests(self, path: str) -> dict | None:
        cwd = os.path.dirname(os.path.abspath(path))
        if shutil.which('go'):
            r = subprocess.run(['go', 'test', '-v', '-json', './...'],
                               cwd=cwd, capture_output=True, text=True, timeout=120)
            import json as _json
            results, ok_n, fail_n = [], 0, 0
            for line in r.stdout.splitlines():
                try:
                    d = _json.loads(line)
                    if d.get('Action') == 'pass': ok_n  += 1
                    if d.get('Action') == 'fail': fail_n += 1
                    if d.get('Action') in ('pass','fail') and d.get('Test'):
                        results.append({'name': d['Test'], 'status': d['Action'],
                                        'duration': d.get('Elapsed', 0), 'message': ''})
                except Exception:
                    pass
            return {'ok': fail_n == 0, 'results': results,
                    'summary': {'passed': ok_n, 'failed': fail_n, 'skipped': 0,
                                'errors': 0, 'duration': 0},
                    'output': r.stdout[-2000:], 'error': None}
        return None

    def get_run_command(self, path: str) -> list | None:
        if shutil.which('go'): return ['go', 'run', path]
        return None

    def get_node_types(self) -> dict:
        return {
            'goroutine': {'n': 'goroutine',    'c': '#1a3a1a'},
            'context':   {'n': 'channel op',   'c': '#1a2a3a'},
            'exception': {'n': 'error/panic',  'c': '#3a1a1a'},
        }


register(GoPlugin())
