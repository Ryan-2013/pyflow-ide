"""PyFlow IDE — Flask backend (full-featured edition)"""
import argparse, json, os, subprocess, sys
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory, Response, stream_with_context
from flask_socketio import SocketIO

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from core.ast_parser     import parse_python_file
from core.go_parser      import parse_go_file
from core.rust_parser    import parse_rust_file
from core.symbols        import extract_symbols
from core.module_inspector import inspect_import, inspect_module
from core.go_stdlib      import get_symbols_for_package, parse_go_imports_from_code
from core.rust_stdlib    import get_symbols_for_use
from core.terminal       import Terminal
from core.watcher        import FileWatcher
from core.formatter      import format_code
from core.search         import search_files

# ── CLI args ────────────────────────────────────────────────────
_p = argparse.ArgumentParser(add_help=False)
_p.add_argument('--port', type=int, default=int(os.environ.get('PYFLOW_PORT', 5000)))
args, _ = _p.parse_known_args()
PORT      = args.port
START_DIR = os.environ.get('PYFLOW_START_DIR', str(Path.home()))

# ── App ─────────────────────────────────────────────────────────
app = Flask(__name__, static_folder='static')
app.config['SECRET_KEY'] = 'pyflow-electron'
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='threading')
_terminals: dict[str, Terminal] = {}

SKIP = {'__pycache__', '.git', '.hg', 'node_modules', '.venv', 'venv',
        'env', '.env', 'dist', 'build', '.pytest_cache', '.mypy_cache', '.tox'}

# File watcher
def _on_file_change(sid: str, path: str):
    socketio.emit('file_changed', {'path': path}, to=sid)
_watcher = FileWatcher(_on_file_change)

# ── Static ──────────────────────────────────────────────────────

# ════════════════════════════════════════════════════════════════
#  LANGUAGE PLUGIN SYSTEM — auto-load all plugins/lang_*.py
# ════════════════════════════════════════════════════════════════
import plugins as _plug_sys
from plugins import get_by_path as _plugin_for, all_plugins, get_by_id as _plugin_by_id

_PLUGINS_DIR = os.path.join(os.path.dirname(__file__), 'plugins')
_plug_sys.load_plugins_from_dir(_PLUGINS_DIR)

print(f"  Loaded {len(all_plugins())} language plugins: " +
      ", ".join(p.id for p in all_plugins()))

# ── /api/languages — list all registered plugins ─────────────────
@app.route('/api/languages')
def lang_list():
    return jsonify({
        'languages': [p.to_dict() for p in all_plugins()],
        'ext_map':   _plug_sys.all_extensions(),
    })

# ── /api/parse — plugin-based dispatcher ─────────────────────────
# Override existing /api/parse to use plugin system
# (The original route is below; this replaces it)
@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

# ── Meta ─────────────────────────────────────────────────────────
@app.route('/api/meta')
def meta():
    return jsonify({'port': PORT, 'cwd': START_DIR, 'python': sys.version})

# ── File System ──────────────────────────────────────────────────
@app.route('/api/files')
def list_files():
    path = request.args.get('path', START_DIR)
    path = str(Path(path).resolve())
    if not os.path.isdir(path):
        return jsonify({'error': 'Not a directory'}), 400
    entries = []
    for name in sorted(os.listdir(path), key=str.lower):
        if name.startswith('.') or name in SKIP: continue
        full = os.path.join(path, name)
        is_dir = os.path.isdir(full)
        entries.append({'name': name, 'path': full,
                        'type': 'dir' if is_dir else 'file',
                        'size': 0 if is_dir else os.path.getsize(full),
                        'is_python': name.endswith(('.py', '.pyw'))})
    entries.sort(key=lambda e: (0 if e['type'] == 'dir' else 1, e['name'].lower()))
    return jsonify({'path': path, 'name': os.path.basename(path) or path, 'entries': entries})


@app.route('/api/write', methods=['POST'])
def write_file():
    data = request.get_json(silent=True) or {}
    path, content = data.get('path', ''), data.get('content', '')
    if not path: return jsonify({'error': 'No path'}), 400
    try:
        Path(path).write_text(content, encoding='utf-8')
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/fs/create', methods=['POST'])
def fs_create():
    data = request.get_json(silent=True) or {}
    path, is_dir = data.get('path', ''), data.get('dir', False)
    if not path: return jsonify({'error': 'No path'}), 400
    try:
        if is_dir: os.makedirs(path, exist_ok=True)
        else:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            if not os.path.exists(path): Path(path).write_text('')
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/fs/rename', methods=['POST'])
def fs_rename():
    data = request.get_json(silent=True) or {}
    src, dst = data.get('src', ''), data.get('dst', '')
    if not src or not dst: return jsonify({'error': 'Missing paths'}), 400
    try:
        os.rename(src, dst); return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/fs/delete', methods=['POST'])
def fs_delete():
    import shutil
    data = request.get_json(silent=True) or {}
    path = data.get('path', '')
    if not path: return jsonify({'error': 'No path'}), 400
    try:
        if os.path.isdir(path): shutil.rmtree(path)
        else: os.unlink(path)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/serve')
def serve_raw():
    p = request.args.get('path', '')
    if not p or not os.path.isfile(p): return ('Not found', 404)
    return send_from_directory(os.path.dirname(os.path.abspath(p)), os.path.basename(p))

# ── Watch ─────────────────────────────────────────────────────────
@socketio.on('watch')
def on_watch(data):
    _watcher.watch(request.sid, data.get('path', ''))

@socketio.on('unwatch')
def on_unwatch(data):
    _watcher.unwatch(request.sid, data.get('path'))

# ── Parse ─────────────────────────────────────────────────────────
@app.route('/api/parse', methods=['POST'])
def parse():
    data   = request.get_json(silent=True) or {}
    code   = data.get('code', '')
    path   = data.get('path', '<string>')
    plugin = _plugin_for(path)
    if plugin:
        result = plugin.parse(code, path)
        result['lang']    = plugin.id
        result['symbols'] = plugin.extract_symbols(code, path, result)
        # Merge any custom node types into result
        result['node_types'] = plugin.get_node_types()
    else:
        # Fallback: plain text, no flow
        result = {'flow': [], 'definitions': [], 'error': 'No parser for this file type',
                  'lang': 'other', 'symbols': [], 'node_types': {}}
    return jsonify(result)

# ── Format ─────────────────────────────────────────────────────────
@app.route('/api/format', methods=['POST'])
def format_route():
    data   = request.get_json(silent=True) or {}
    lang   = data.get('lang', 'python')
    code   = data.get('code', '')
    plugin = _plugin_by_id(lang)
    if plugin and plugin.format_code(None) is not False:
        result = plugin.format_code(code)
        if result: return jsonify(result)
    # Fallback to old formatter
    from core.formatter import format_code
    return jsonify(format_code(code, lang))

# ── Search ─────────────────────────────────────────────────────────
@app.route('/api/search', methods=['POST'])
def search_route():
    data = request.get_json(silent=True) or {}
    result = search_files(
        data.get('dir', START_DIR),
        data.get('query', ''),
        case_sensitive=data.get('case', False),
        use_regex=data.get('regex', False),
    )
    return jsonify(result)

# ── Git ──────────────────────────────────────────────────────────
@app.route('/api/git/status')
def git_status():
    directory = request.args.get('dir', START_DIR)
    try:
        result = subprocess.run(
            ['git', 'status', '--porcelain', '--untracked-files=all'],
            cwd=directory, capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            return jsonify({'available': False, 'files': {}})
        files = {}
        for line in result.stdout.split('\n'):
            if len(line) >= 3:
                status = line[:2].strip() or '?'
                rel = line[3:].strip().split(' -> ')[-1]  # handle renames
                files[os.path.normpath(os.path.join(directory, rel))] = status
        return jsonify({'available': True, 'files': files})
    except Exception:
        return jsonify({'available': False, 'files': {}})

# ── Symbol APIs ──────────────────────────────────────────────────
@app.route('/api/module-symbols', methods=['POST'])
def module_symbols_route():
    data = request.get_json(silent=True) or {}
    all_syms: list[dict] = []
    for stmt in (data.get('imports') or [])[:20]:
        try: all_syms.extend(list(inspect_import(stmt.strip())))
        except: pass
    if data.get('module'):
        try: all_syms.extend(list(inspect_module(data['module'])))
        except: pass
    return jsonify({'symbols': all_syms})

@app.route('/api/go-symbols', methods=['POST'])
def go_symbols_route():
    data = request.get_json(silent=True) or {}
    pkg_map = parse_go_imports_from_code(data.get('code', ''))
    syms: list[dict] = []
    for alias, pkg in pkg_map.items():
        syms.extend(get_symbols_for_package(pkg, alias if alias != pkg.split('/')[-1] else None))
    return jsonify({'symbols': syms})

@app.route('/api/rust-symbols', methods=['POST'])
def rust_symbols_route():
    from core.rust_stdlib import RUST_MODULES
    data = request.get_json(silent=True) or {}
    use_stmts = data.get('use_stmts', [])
    all_syms: list[dict] = []
    seen: set[str] = set()
    for stmt in use_stmts[:30]:
        for s in get_symbols_for_use(stmt):
            k = s['name'] + '|' + (s.get('parent') or '')
            if k not in seen: seen.add(k); all_syms.append(s)
    for t in ('Option', 'Result', 'Vec', 'String', 'HashMap'):
        for s in get_symbols_for_use(f'use {t};'):
            k = s['name'] + '|' + (s.get('parent') or '')
            if k not in seen: seen.add(k); all_syms.append(s)
    return jsonify({'symbols': all_syms})

@app.route('/api/rust/check', methods=['POST'])
def rust_check_route():
    from core.rust_check import check as rust_check
    data = request.get_json(silent=True) or {}
    return jsonify(rust_check(data.get('code', ''), data.get('edition', '2021')))

@app.route('/api/rust/meta')
def rust_meta_route():
    from core.rust_parser import OWN_META
    from core.rust_check import is_available as rust_available
    return jsonify({'available': rust_available(), 'ownership_meta': OWN_META})

# ── Run (SSE) ────────────────────────────────────────────────────
@app.route('/api/run', methods=['POST'])
def run_file():
    data = request.get_json(silent=True) or {}
    path = data.get('path', '')
    if not path or not os.path.isfile(path):
        return jsonify({'error': 'File not found'}), 404
    def generate():
        env = {**os.environ, 'PYTHONIOENCODING': 'utf-8', 'PYTHONUNBUFFERED': '1'}
        proc = subprocess.Popen(
            [sys.executable, '-u', path] + data.get('args', []),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            cwd=str(Path(path).parent), text=True, bufsize=1, env=env,
        )
        yield f'data: {json.dumps({"type":"start","pid":proc.pid,"file":os.path.basename(path)})}\n\n'
        try:
            for line in proc.stdout:
                yield f'data: {json.dumps({"type":"stdout","line":line})}\n\n'
        except GeneratorExit:
            proc.terminate(); return
        proc.wait()
        yield f'data: {json.dumps({"type":"exit","code":proc.returncode})}\n\n'
    return Response(stream_with_context(generate()), content_type='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

# ── Terminal (WebSocket) ─────────────────────────────────────────
@socketio.on('terminal_start')
def on_start(data):
    sid, key = request.sid, data.get('key', 'default')
    full_key = f'{sid}:{key}'
    if full_key in _terminals: _terminals[full_key].stop()
    cwd = data.get('cwd', START_DIR)
    if not os.path.isdir(cwd): cwd = START_DIR
    def out(text): socketio.emit('terminal_output', {'data': text, 'key': key}, to=sid)
    t = Terminal(cwd, out)
    _terminals[full_key] = t
    t.start()

@socketio.on('terminal_input')
def on_input(data):
    key = data.get('key', 'default')
    full_key = f'{request.sid}:{key}'
    if full_key in _terminals: _terminals[full_key].write(data.get('data', ''))

@socketio.on('terminal_resize')
def on_resize(data):
    key = data.get('key', 'default')
    full_key = f'{request.sid}:{key}'
    if full_key in _terminals: _terminals[full_key].resize(data.get('rows', 24), data.get('cols', 80))

@socketio.on('terminal_close')
def on_term_close(data):
    key = data.get('key', 'default')
    full_key = f'{request.sid}:{key}'
    if full_key in _terminals: _terminals[full_key].stop(); del _terminals[full_key]

@socketio.on('disconnect')
def on_disconnect():
    sid = request.sid
    _watcher.unwatch(sid)
    for key in [k for k in _terminals if k.startswith(f'{sid}:')]:
        _terminals[key].stop(); del _terminals[key]

# ── LSP Manager ───────────────────────────────────────────────────
from core.lsp_client import LSPManager as _LSPManager
_lsp = _LSPManager(socketio)

@socketio.on('lsp_request')
def on_lsp_req(data):
    lang      = data.get('lang', 'python')
    workspace = data.get('workspace', START_DIR)
    method    = data.get('method', '')
    params    = data.get('params', {})
    req_id    = data.get('id')
    result    = _lsp.request(lang, workspace, request.sid, method, params)
    socketio.emit('lsp_response', {'id': req_id, 'result': result, 'error': None}, to=request.sid)

@socketio.on('lsp_notify')
def on_lsp_ntfy(data):
    lang      = data.get('lang', 'python')
    workspace = data.get('workspace', START_DIR)
    method    = data.get('method', '')
    params    = data.get('params', {})
    _lsp.notify(lang, workspace, request.sid, method, params)

@app.route('/api/lsp/status')
def lsp_status():
    base = _lsp.status()
    # Augment with plugin-detected LSP availability
    for p in all_plugins():
        cmd = p.get_lsp_command()
        base[p.id] = bool(cmd) and (bool(__import__('shutil').which(cmd[0])) if cmd else False)
    return jsonify(base)

if __name__ == '__main__':
    print(f'\n  PyFlow IDE -> http://localhost:{PORT}\n')
    socketio.run(app, host='127.0.0.1', port=PORT, debug=False, allow_unsafe_werkzeug=True)

# ── Function-specific flow ─────────────────────────────────────────
@app.route('/api/parse-fn', methods=['POST'])
def parse_fn_route():
    """提取指定函式的內部流程圖。"""
    from core.fn_parser import extract_fn_flow
    data = request.get_json(silent=True) or {}
    code    = data.get('code', '')
    path    = data.get('path', '<string>')
    fn_name = data.get('fn', '')
    ext     = path.rsplit('.', 1)[-1].lower() if '.' in path else ''
    lang    = {'go': 'go', 'rs': 'rust'}.get(ext, 'python')
    result  = extract_fn_flow(code, fn_name, lang, path)
    if result.get('flow'):
        from core.symbols import extract_symbols
        result['symbols'] = extract_symbols(result, lang, code)
    return jsonify(result)

# ── Test runner ────────────────────────────────────────────────────
@app.route('/api/test', methods=['POST'])
def test_route():
    """執行測試並傳回結構化結果。"""
    data   = request.get_json(silent=True) or {}
    path   = data.get('path', '')
    if not path:
        return jsonify({'ok': False, 'error': '未指定路徑', 'results': [], 'summary': {}}), 400
    plugin = _plugin_for(path)
    if plugin:
        result = plugin.run_tests(path)
        if result: return jsonify(result)
    # Fallback
    from core.test_runner import run_tests
    ext  = path.rsplit('.', 1)[-1].lower() if '.' in path else ''
    lang = {'go': 'go', 'rs': 'rust'}.get(ext, 'python')
    return jsonify(run_tests(path, lang))

# ── Git inline diff ────────────────────────────────────────────────
@app.route('/api/git/diff')
def git_diff_route():
    from core.git_diff import get_diff
    path = request.args.get('path', '')
    return jsonify(get_diff(path))

# ── Venv detection ─────────────────────────────────────────────────
@app.route('/api/venv')
def venv_route():
    from core.venv_detector import detect
    directory = request.args.get('dir', START_DIR)
    return jsonify(detect(directory))

# ── Call graph ─────────────────────────────────────────────────────
@app.route('/api/callgraph')
def callgraph_route():
    """分析目錄中所有 Python 檔案並建立靜態呼叫圖。"""
    directory = request.args.get('dir', START_DIR)
    max_files = int(request.args.get('max', 60))
    nodes, edges = {}, []
    seen_edges = set()
    count = 0
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in {'__pycache__', 'node_modules', '.git', '.venv', 'venv', 'dist', 'build'}]
        for fname in files:
            if not fname.endswith('.py'): continue
            if count >= max_files: break
            fpath = os.path.join(root, fname)
            try:
                code = open(fpath, encoding='utf-8', errors='replace').read()
                data = parse_python_file(code, fpath)
                # Collect definitions
                for d in (data.get('definitions') or []):
                    nid = d['id']
                    nodes[nid] = {'id': nid, 'label': d.get('label', nid), 'type': d.get('type', 'function'), 'file': fpath, 'line': d.get('line', 0)}
                # Collect calls from flow
                for n in (data.get('flow') or []):
                    src = n.get('id', '')
                    for tgt in (n.get('calls') or []):
                        key = f'{src}→{tgt}'
                        if key not in seen_edges:
                            seen_edges.add(key)
                            edges.append({'from': src, 'to': tgt})
                count += 1
            except Exception:
                pass
        if count >= max_files: break
    return jsonify({'nodes': list(nodes.values()), 'edges': edges, 'files': count})

# ════════════════════════════════════════════════════════════════
#  EXTRA ROUTES (profiler, coverage, debugger, workspace, export…)
# ════════════════════════════════════════════════════════════════
from core.extra import (run_profiler, run_coverage, DebugManager,
                        ws_load, ws_save, find_dead_code, export_html)
from core.git_ops import (diff_content, branches, checkout, staged_files,
                           unstaged_files, stage, unstage, commit as git_commit,
                           blame)
_dbg = DebugManager(socketio)

# ── Git ops ──────────────────────────────────────────────────────
@app.route('/api/git/diff-content')
def git_diff_content():
    return jsonify(diff_content(request.args.get('path', '')))

@app.route('/api/git/branches')
def git_branches():
    return jsonify(branches(request.args.get('dir', START_DIR)))

@app.route('/api/git/checkout', methods=['POST'])
def git_checkout():
    d = request.get_json(silent=True) or {}
    return jsonify(checkout(d.get('dir', START_DIR), d.get('branch', '')))

@app.route('/api/git/stage', methods=['POST'])
def git_stage():
    d = request.get_json(silent=True) or {}
    return jsonify(stage(d.get('path', ''), d.get('dir', START_DIR)))

@app.route('/api/git/unstage', methods=['POST'])
def git_unstage():
    d = request.get_json(silent=True) or {}
    return jsonify(unstage(d.get('path', ''), d.get('dir', START_DIR)))

@app.route('/api/git/commit', methods=['POST'])
def git_commit_route():
    d = request.get_json(silent=True) or {}
    return jsonify(git_commit(d.get('dir', START_DIR), d.get('message', 'Update'),
                              d.get('stage_all', False)))

@app.route('/api/git/staged')
def git_staged():
    return jsonify({'files': staged_files(request.args.get('dir', START_DIR))})

@app.route('/api/git/unstaged')
def git_unstaged_route():
    return jsonify({'files': unstaged_files(request.args.get('dir', START_DIR))})

@app.route('/api/git/blame')
def git_blame():
    return jsonify(blame(request.args.get('path', '')))

# ── LSP: references, rename ───────────────────────────────────────
@socketio.on('lsp_references')
def on_lsp_refs(data):
    lang      = data.get('lang', 'python')
    workspace = data.get('workspace', START_DIR)
    params    = data.get('params', {})
    result    = _lsp.request(lang, workspace, request.sid, 'textDocument/references', params)
    socketio.emit('lsp_refs_result', {'result': result, 'id': data.get('id')}, to=request.sid)

@socketio.on('lsp_rename')
def on_lsp_rename(data):
    lang      = data.get('lang', 'python')
    workspace = data.get('workspace', START_DIR)
    params    = data.get('params', {})
    result    = _lsp.request(lang, workspace, request.sid, 'textDocument/rename', params)
    socketio.emit('lsp_rename_result', {'result': result, 'id': data.get('id')}, to=request.sid)

# ── Profiler ──────────────────────────────────────────────────────
@app.route('/api/profile', methods=['POST'])
def profile_route():
    d = request.get_json(silent=True) or {}
    return jsonify(run_profiler(d.get('path', '')))

# ── Coverage ──────────────────────────────────────────────────────
@app.route('/api/coverage', methods=['POST'])
def coverage_route():
    d = request.get_json(silent=True) or {}
    return jsonify(run_coverage(d.get('path', '')))

# ── Debugger (Socket.IO) ──────────────────────────────────────────
@socketio.on('dbg_start')
def on_dbg_start(data):
    _dbg.start(request.sid, data.get('path', ''), data.get('breakpoints', {}))

@socketio.on('dbg_cmd')
def on_dbg_cmd(data):
    result = _dbg.cmd(request.sid, data.get('cmd', ''), data.get('args'))
    if result is not None:
        socketio.emit('dbg_result', {'cmd': data.get('cmd'), 'result': result}, to=request.sid)

@socketio.on('dbg_eval')
def on_dbg_eval(data):
    result = _dbg.evaluate(request.sid, data.get('expr', ''), data.get('frameId', 0))
    socketio.emit('dbg_eval_result', {'expr': data.get('expr'), 'result': result}, to=request.sid)

@socketio.on('dbg_stop')
def on_dbg_stop(_):
    _dbg.stop(request.sid)

# ── Dead code ─────────────────────────────────────────────────────
@app.route('/api/deadcode', methods=['POST'])
def dead_code_route():
    d = request.get_json(silent=True) or {}
    code = d.get('code', ''); path = d.get('path', '')
    ext  = path.rsplit('.', 1)[-1].lower() if '.' in path else ''
    if ext == 'go':
        from core.go_parser import parse_go_file; r = parse_go_file(code, path)
    elif ext == 'rs':
        from core.rust_parser import parse_rust_file; r = parse_rust_file(code, path)
    else:
        r = parse_python_file(code, path)
    dead = list(find_dead_code(r))
    return jsonify({'dead': dead})

# ── Export HTML ───────────────────────────────────────────────────
@app.route('/api/export-html', methods=['POST'])
def export_html_route():
    d    = request.get_json(silent=True) or {}
    html = export_html(d.get('graph', {}), d.get('filename', 'pyflow'))
    return Response(html, content_type='text/html; charset=utf-8',
                    headers={'Content-Disposition': f'attachment; filename="{d.get("filename","pyflow")}-flow.html"'})

# ── Workspace settings ────────────────────────────────────────────
@app.route('/api/workspace')
def workspace_load():
    return jsonify(ws_load(request.args.get('dir', START_DIR)))

@app.route('/api/workspace', methods=['POST'])
def workspace_save():
    d = request.get_json(silent=True) or {}
    return jsonify({'ok': ws_save(d.get('dir', START_DIR), d.get('config', {}))})

# ── Search & Replace ──────────────────────────────────────────────
@app.route('/api/replace', methods=['POST'])
def replace_route():
    from core.search import search_files
    import re as _re
    d     = request.get_json(silent=True) or {}
    query = d.get('query', '')
    repl  = d.get('replace', '')
    dry   = d.get('dry_run', True)
    case  = d.get('case', False)
    rx    = d.get('regex', False)
    if not query:
        return jsonify({'ok': False, 'replaced': 0, 'error': 'No query'})
    try:
        flags   = 0 if case else _re.IGNORECASE
        pattern = _re.compile(query if rx else _re.escape(query), flags)
    except _re.error as e:
        return jsonify({'ok': False, 'replaced': 0, 'error': str(e)})
    results = search_files(d.get('dir', START_DIR), query, case_sensitive=case, use_regex=rx)
    files_changed, total_replaced = 0, 0
    for fpath in {r['file'] for r in results.get('results', [])}:
        try:
            text    = Path(fpath).read_text(encoding='utf-8', errors='replace')
            new, n  = pattern.subn(repl, text)
            if n and not dry:
                Path(fpath).write_text(new, encoding='utf-8')
            total_replaced += n
            if n: files_changed += 1
        except Exception:
            pass
    return jsonify({'ok': True, 'replaced': total_replaced, 'files': files_changed})

# ════════════════════════════════════════════════════════════════
#  NEW ROUTES: Git remote, log, Jupyter cell, plugin hot-reload
# ════════════════════════════════════════════════════════════════
from core.git_ops import (remotes as git_remotes, fetch as git_fetch,
                           pull as git_pull, push as git_push,
                           git_log, git_show)
from core.plugin_watcher import PluginWatcher as _PlugWatcher
from plugins.lang_jupyter import run_notebook_cell

# Start plugin watcher
_plug_watcher = _PlugWatcher(_PLUGINS_DIR, socketio)

# ── Git remote ops ─────────────────────────────────────────────────
@app.route('/api/git/remotes')
def git_remotes_route():
    return jsonify(git_remotes(request.args.get('dir', START_DIR)))

@app.route('/api/git/fetch', methods=['POST'])
def git_fetch_route():
    d = request.get_json(silent=True) or {}
    return jsonify(git_fetch(d.get('dir', START_DIR), d.get('remote', 'origin')))

@app.route('/api/git/pull', methods=['POST'])
def git_pull_route():
    d = request.get_json(silent=True) or {}
    return jsonify(git_pull(d.get('dir', START_DIR), d.get('remote', 'origin'), d.get('branch', '')))

@app.route('/api/git/push', methods=['POST'])
def git_push_route():
    d = request.get_json(silent=True) or {}
    return jsonify(git_push(d.get('dir', START_DIR), d.get('remote', 'origin'),
                            d.get('branch', ''), d.get('force', False)))

@app.route('/api/git/log')
def git_log_route():
    path = request.args.get('path', '')
    n    = int(request.args.get('n', 40))
    return jsonify(git_log(path or START_DIR, n))

@app.route('/api/git/show')
def git_show_route():
    return jsonify(git_show(request.args.get('dir', START_DIR),
                            request.args.get('hash', 'HEAD'),
                            request.args.get('path', '')))

# ── Jupyter cell execution ─────────────────────────────────────────
@app.route('/api/notebook/run-cell', methods=['POST'])
def run_cell_route():
    d      = request.get_json(silent=True) or {}
    result = run_notebook_cell(d.get('path', ''), d.get('code', ''), d.get('kernel', 'python3'))
    return jsonify(result)

# ════════════════════════════════════════════════════════════════
#  AI ASSISTANT + TRACER + IMPORT GRAPH + ENCODING + SEARCH CTX
# ════════════════════════════════════════════════════════════════
from core.tracer      import run_with_trace, map_trace_to_nodes
from core.import_graph import build_import_graph

# ── AI Assistant ──────────────────────────────────────────────────
@app.route('/api/ai/chat', methods=['POST'])
def ai_chat():
    """Stream Claude response for the AI assistant panel."""
    import anthropic
    data     = request.get_json(silent=True) or {}
    messages = data.get('messages', [])
    context  = data.get('context', {})
    api_key  = data.get('api_key') or os.environ.get('ANTHROPIC_API_KEY', '')

    if not api_key:
        return jsonify({'error': '未設定 API Key。在設定面板輸入 Anthropic API Key。'}), 400

    system = (
        "You are an expert coding assistant integrated into PyFlow IDE, a code flow visualization tool. "
        "Users can see their code as interactive flow diagrams. Help them understand and improve their code. "
        "Be concise, technical, and practical. Reply in the same language the user uses (繁體中文 or English).\n"
    )
    if context.get('file'):
        system += f"Current file: {context['file']}\n"
    if context.get('lang'):
        system += f"Language: {context['lang']}\n"
    if context.get('fn'):
        system += f"Current function: {context['fn']}\n"
    if context.get('code'):
        system += f"\nCode context:\n```\n{context['code'][:4000]}\n```\n"
    if context.get('selection'):
        system += f"\nSelected code:\n```\n{context['selection'][:2000]}\n```\n"

    def generate():
        try:
            client = anthropic.Anthropic(api_key=api_key)
            with client.messages.stream(
                model='claude-sonnet-4-6', max_tokens=2048,
                system=system, messages=messages[-20:],
            ) as stream:
                for text in stream.text_stream:
                    yield f"data: {json.dumps({'t': text})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        except anthropic.AuthenticationError:
            yield f"data: {json.dumps({'error': 'API Key 無效'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(generate(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

@app.route('/api/ai/status')
def ai_status():
    has_key = bool(os.environ.get('ANTHROPIC_API_KEY', ''))
    return jsonify({'available': True, 'has_env_key': has_key})

# ── Execution Tracer ───────────────────────────────────────────────
@app.route('/api/trace', methods=['POST'])
def trace_route():
    data   = request.get_json(silent=True) or {}
    path   = data.get('path', '')
    flow   = data.get('flow', [])
    defs   = data.get('definitions', [])
    result = run_with_trace(path, timeout=30)
    if result['hits']:
        mapped = map_trace_to_nodes(result, flow, defs, path)
        result.update(mapped)
    return jsonify(result)

# ── Import Dependency Tree ─────────────────────────────────────────
@app.route('/api/import-graph')
def import_graph_route():
    directory    = request.args.get('dir', START_DIR)
    include_std  = request.args.get('stdlib', 'false') == 'true'
    include_3rd  = request.args.get('third', 'true') == 'true'
    return jsonify(build_import_graph(directory, include_stdlib=include_std,
                                      include_third_party=include_3rd))

# ── File read with encoding detection ─────────────────────────────
@app.route('/api/read')
def read_file():
    path = request.args.get('path', '')
    if not path or not os.path.isfile(path):
        return jsonify({'content': '', 'error': 'File not found', 'encoding': 'utf-8'}), 404
    try:
        import chardet
        raw      = open(path, 'rb').read()
        detected = chardet.detect(raw)
        encoding = detected.get('encoding') or 'utf-8'
        # Normalize common encoding names
        enc_map  = {'gb2312': 'gbk', 'gb18030': 'gbk', 'ascii': 'utf-8'}
        encoding = enc_map.get(encoding.lower(), encoding)
        content  = raw.decode(encoding, errors='replace')
        return jsonify({'content': content, 'encoding': encoding, 'error': None})
    except Exception as e:
        try:
            content = open(path, encoding='utf-8', errors='replace').read()
            return jsonify({'content': content, 'encoding': 'utf-8', 'error': None})
        except Exception as e2:
            return jsonify({'content': '', 'encoding': 'utf-8', 'error': str(e2)}), 500

# ── Search with context lines ──────────────────────────────────────
@app.route('/api/search-ctx', methods=['POST'])
def search_ctx():
    """Search with N lines of context before/after each match."""
    from core.search import search_files
    d       = request.get_json(silent=True) or {}
    q       = d.get('query', '')
    ctx     = d.get('context_lines', 2)
    case    = d.get('case_sensitive', False)
    use_re  = d.get('regex', False)
    if not q:
        return jsonify({'results': [], 'total': 0})

    raw     = search_files(d.get('dir', START_DIR), q, case_sensitive=case, use_regex=use_re)
    results = []
    for r in (raw.get('results') or []):
        fpath = r.get('file', '')
        line  = r.get('line', 1)
        try:
            lines = open(fpath, encoding='utf-8', errors='replace').read().split('\n')
            start = max(0, line - 1 - ctx)
            end   = min(len(lines), line + ctx)
            context_lines = [{'num': start + i + 1, 'text': lines[start + i],
                              'match': start + i + 1 == line}
                             for i in range(end - start)]
        except Exception:
            context_lines = []
        results.append({**r, 'context': context_lines})

    return jsonify({'results': results, 'total': len(results)})


# ── Git credentials helper ────────────────────────────────────────
@app.route('/api/git/set-credentials', methods=['POST'])
def git_set_credentials():
    d = request.get_json(silent=True) or {}
    cwd = d.get('dir', START_DIR)
    ctype = d.get('type', 'store')   # 'store' | 'token' | 'ssh-keygen'

    if ctype == 'store':
        # Enable git credential store
        out, err, rc = _git(['config', 'credential.helper', 'store'], cwd)
        return jsonify({'ok': rc == 0, 'message': 'Git credential.helper 已設為 store'})

    elif ctype == 'ssh-keygen':
        import subprocess
        keypath = os.path.expanduser('~/.ssh/id_ed25519')
        if not os.path.exists(keypath):
            r = subprocess.run(['ssh-keygen', '-t', 'ed25519', '-N', '', '-f', keypath],
                               capture_output=True, text=True)
        try:
            pubkey = open(keypath + '.pub').read().strip()
        except Exception:
            pubkey = ''
        return jsonify({'ok': True, 'pubkey': pubkey, 'keypath': keypath})

    return jsonify({'ok': False, 'message': '未知認證類型'})

@app.route('/api/git/remotes-detail')
def git_remotes_detail():
    cwd = request.args.get('dir', START_DIR)
    out, _, rc = _git(['remote', '-v'], cwd)
    remotes = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and '(fetch)' in line:
            remotes[parts[0]] = parts[1]
    return jsonify({'remotes': remotes, 'ok': rc == 0})

# ── Sample project ─────────────────────────────────────────────────
@app.route('/api/sample-path')
def sample_path():
    sample = os.path.join(os.path.dirname(__file__), 'samples', 'demo_flow.py')
    if os.path.exists(sample):
        return jsonify({'path': sample, 'ok': True})
    return jsonify({'path': None, 'ok': False})

# ════════════════════════════════════════════════════════════════
#  BIDIRECTIONAL CODE EDITING — nodes ↔ code
# ════════════════════════════════════════════════════════════════
import ast as _ast, textwrap as _tw

def _get_fn_end_line(code: str, start_line: int) -> int:
    """Find the last line of a function starting at start_line."""
    try:
        tree = _ast.parse(code)
        for node in _ast.walk(tree):
            if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef,
                                  _ast.ClassDef)):
                if node.lineno == start_line:
                    return node.end_lineno
    except Exception:
        pass
    # Fallback: find by indentation
    lines = code.split('\n')
    if start_line <= 0 or start_line > len(lines):
        return start_line
    first = lines[start_line - 1]
    base_indent = len(first) - len(first.lstrip())
    for i in range(start_line, len(lines)):
        line = lines[i]
        if line.strip() and (len(line) - len(line.lstrip())) <= base_indent and i > start_line - 1:
            return i
    return len(lines)


@app.route('/api/code/edit', methods=['POST'])
def code_edit():
    """
    Bidirectional code editing from diagram nodes.
    actions: insert-function | delete-function | insert-call |
             rename-symbol | add-param | move-function
    """
    d      = request.get_json(silent=True) or {}
    action = d.get('action', '')
    path   = d.get('path', '')

    if not path or not os.path.isfile(path):
        return jsonify({'ok': False, 'error': 'File not found'}), 404

    try:
        code = open(path, encoding='utf-8', errors='replace').read()
        ext  = path.rsplit('.', 1)[-1].lower() if '.' in path else 'py'

        # ── INSERT NEW FUNCTION ────────────────────────────────
        if action == 'insert-function':
            name   = d.get('name', 'new_function').strip().replace(' ', '_')
            params = d.get('params', '').strip()
            after_line = d.get('after_line')  # insert after this line (1-based)
            is_async   = d.get('is_async', False)
            docstring  = d.get('docstring', '')

            if ext == 'py':
                async_kw = 'async ' if is_async else ''
                doc = f'    """{docstring}"""\n' if docstring else ''
                snippet = f'\n\n{async_kw}def {name}({params}):\n{doc}    pass\n'
            elif ext == 'go':
                snippet = f'\n\nfunc {name}({params}) {{\n\t// TODO\n}}\n'
            elif ext == 'rs':
                snippet = f'\n\nfn {name}({params}) {{\n    todo!()\n}}\n'
            elif ext == 'ts' or ext == 'js':
                async_kw = 'async ' if is_async else ''
                snippet = f'\n\n{async_kw}function {name}({params}) {{\n  // TODO\n}}\n'
            elif ext == 'java':
                snippet = f'\n\n    public void {name}({params}) {{\n        // TODO\n    }}\n'
            else:
                snippet = f'\n\nfunction {name}({params}) {{\n}}\n'

            lines = code.split('\n')
            if after_line and 1 <= after_line <= len(lines):
                end = _get_fn_end_line(code, after_line)
                lines.insert(end, snippet.rstrip())
                new_code = '\n'.join(lines)
            else:
                new_code = code.rstrip() + snippet

        # ── DELETE FUNCTION / CLASS ────────────────────────────
        elif action == 'delete-function':
            start_line = d.get('line', 0)
            if not start_line:
                return jsonify({'ok': False, 'error': 'No line number'}), 400
            end_line = _get_fn_end_line(code, start_line)
            lines    = code.split('\n')
            # Remove the function and any blank lines immediately before it
            del_start = start_line - 1
            while del_start > 0 and not lines[del_start - 1].strip():
                del_start -= 1
            new_lines = lines[:del_start] + lines[end_line:]
            new_code  = '\n'.join(new_lines)

        # ── INSERT CALL AT CURSOR / END OF FUNCTION ────────────
        elif action == 'insert-call':
            fn_name    = d.get('fn_name', '')
            at_line    = d.get('at_line', 0)        # cursor line (1-based)
            in_fn_line = d.get('in_fn_line', 0)     # containing fn start line
            assign_var = d.get('assign_var', 'result')
            call_args  = d.get('args', '')

            lines = code.split('\n')
            target_line = at_line if at_line > 0 else len(lines)

            # Detect indentation at target
            if 1 <= target_line <= len(lines):
                ctx = lines[target_line - 1]
                indent = ' ' * (len(ctx) - len(ctx.lstrip()))
            else:
                indent = '    '

            if ext == 'py':
                call_line = f'{indent}{assign_var} = {fn_name}({call_args})'
            elif ext in ('ts', 'js'):
                call_line = f'{indent}const {assign_var} = {fn_name}({call_args});'
            elif ext == 'java':
                call_line = f'{indent}var {assign_var} = {fn_name}({call_args});'
            else:
                call_line = f'{indent}{fn_name}({call_args});'

            lines.insert(target_line, call_line)
            new_code = '\n'.join(lines)

        # ── RENAME SYMBOL (local, no LSP) ─────────────────────
        elif action == 'rename-local':
            old_name = d.get('old_name', '')
            new_name = d.get('new_name', '').strip().replace(' ', '_')
            if not old_name or not new_name:
                return jsonify({'ok': False, 'error': 'Missing names'}), 400
            import re as _re
            new_code = _re.sub(r'\b' + _re.escape(old_name) + r'\b', new_name, code)

        # ── ADD PARAMETER TO FUNCTION ──────────────────────────
        elif action == 'add-param':
            fn_line   = d.get('line', 0)
            param_str = d.get('param', 'new_param')
            lines = code.split('\n')
            if fn_line and 1 <= fn_line <= len(lines):
                import re as _re
                line = lines[fn_line - 1]
                # Add param before the closing paren
                if '()' in line:
                    lines[fn_line - 1] = line.replace('()', f'({param_str})', 1)
                else:
                    lines[fn_line - 1] = _re.sub(r'\)', f', {param_str})', line, count=1)
            new_code = '\n'.join(lines)

        # ── MOVE FUNCTION (swap two functions) ────────────────
        elif action == 'move-function':
            line_a = d.get('line_a', 0)
            line_b = d.get('line_b', 0)
            if not (line_a and line_b):
                return jsonify({'ok': False, 'error': 'Need line_a and line_b'}), 400
            end_a  = _get_fn_end_line(code, line_a)
            end_b  = _get_fn_end_line(code, line_b)
            lines  = code.split('\n')
            a_block = lines[line_a-1:end_a]
            b_block = lines[line_b-1:end_b]
            new_lines = (lines[:line_a-1] + b_block +
                         lines[end_a:line_b-1] + a_block +
                         lines[end_b:])
            new_code = '\n'.join(new_lines)

        else:
            return jsonify({'ok': False, 'error': f'Unknown action: {action}'}), 400

        # ── Write back ────────────────────────────────────────
        open(path, 'w', encoding='utf-8').write(new_code)
        return jsonify({'ok': True, 'code': new_code})

    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

# ── Terminal CWD tracking ──────────────────────────────────────────
_term_pid_map: dict[str, int] = {}   # sid → pty PID

@app.route('/api/term/cwd')
def term_cwd():
    """Get current working directory of a terminal pty process."""
    sid = request.args.get('sid', '')
    pid = _term_pid_map.get(sid)
    if pid:
        # Linux: /proc/{pid}/cwd symlink
        try:
            cwd = os.readlink(f'/proc/{pid}/cwd')
            return jsonify({'cwd': cwd, 'ok': True})
        except Exception:
            pass
        # macOS fallback
        try:
            import subprocess as _sp
            r = _sp.run(['lsof', '-p', str(pid), '-a', '-d', 'cwd', '-Fn'],
                       capture_output=True, text=True, timeout=3)
            for line in r.stdout.splitlines():
                if line.startswith('n'):
                    return jsonify({'cwd': line[1:], 'ok': True})
        except Exception:
            pass
    # Fallback: return START_DIR
    return jsonify({'cwd': START_DIR, 'ok': bool(START_DIR), 'fallback': True})

# Register pty PID when terminal opens (hook into existing terminal creation)
# This is called from Socket.IO terminal handler
def _register_term_pid(sid: str, pid: int):
    _term_pid_map[sid] = pid

# File list for fuzzy file finder (Ctrl+P)
_FILES_LIST_CACHE = {}

@app.route('/api/files-list')
def files_list():
    directory = request.args.get('dir', START_DIR)
    cached = _FILES_LIST_CACHE.get(directory)
    import os.path as _osp
    if cached:
        # Invalidate if mtime of dir changed
        try:
            mtime = _osp.getmtime(directory)
            if abs(mtime - cached['mtime']) < 0.5:
                return jsonify(cached['result'])
        except Exception:
            pass
    skip = {'__pycache__','.git','.venv','venv','node_modules','dist','build',
            '.pytest_cache','.mypy_cache','target','.next','.nuxt'}
    files = []
    try:
        for root, dirs, filenames in os.walk(directory):
            dirs[:] = sorted(d for d in dirs if d not in skip and not d.startswith('.'))
            for fname in sorted(filenames):
                fpath  = os.path.join(root, fname)
                rel    = os.path.relpath(fpath, directory)
                files.append({'path': fpath, 'rel': rel, 'name': fname})
                if len(files) >= 5000: break
            if len(files) >= 5000: break
    except Exception:
        pass
    result = {'files': files, 'dir': directory}
    try:
        _FILES_LIST_CACHE[directory] = {'result': result, 'mtime': _osp.getmtime(directory)}
    except Exception:
        pass
    return jsonify(result)

# ════════════════════════════════════════════════════════════════
#  SETUP WIZARD — runtime detection, LSP auto-install, settings
# ════════════════════════════════════════════════════════════════
from core.setup import get_full_status, install_lsp_stream, load_settings, save_settings

@app.route('/api/setup/status')
def setup_status():
    return jsonify(get_full_status())

@app.route('/api/setup/install')
def setup_install():
    """SSE stream: install an LSP server."""
    lsp_id = request.args.get('lsp', '')
    if not lsp_id:
        return jsonify({'error': 'Missing lsp parameter'}), 400
    return Response(
        install_lsp_stream(lsp_id),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'}
    )

@app.route('/api/settings/load')
def settings_load():
    return jsonify(load_settings())

@app.route('/api/settings/save', methods=['POST'])
def settings_save():
    d = request.get_json(silent=True) or {}
    ok = save_settings(d)
    return jsonify({'ok': ok})

@app.route('/api/settings/set-apikey', methods=['POST'])
def settings_set_apikey():
    d = request.get_json(silent=True) or {}
    key = d.get('key', '').strip()
    if key:
        ok = save_settings({'anthropic_api_key': key})
        if ok:
            os.environ['ANTHROPIC_API_KEY'] = key
        return jsonify({'ok': ok})
    return jsonify({'ok': False, 'error': 'Empty key'})

import hashlib as _hashlib, time as _perf_time

# ── Parse result LRU cache ────────────────────────────────────────
_PARSE_CACHE     = {}
_PARSE_CACHE_MAX = 150

def _cache_get(path, content):
    h = _hashlib.md5(content.encode('utf-8','replace')).hexdigest()
    e = _PARSE_CACHE.get(path)
    if e and e['h'] == h:
        e['t'] = _perf_time.time()
        return e['r']
    return None

def _cache_set(path, content, result):
    h = _hashlib.md5(content.encode('utf-8','replace')).hexdigest()
    _PARSE_CACHE[path] = {'h': h, 'r': result, 't': _perf_time.time()}
    if len(_PARSE_CACHE) > _PARSE_CACHE_MAX:
        del _PARSE_CACHE[min(_PARSE_CACHE, key=lambda k: _PARSE_CACHE[k]['t'])]

# ── Git status cache (5s TTL) ─────────────────────────────────────
_GIT_SC = {}

def _git_cache_get(d):
    e = _GIT_SC.get(d)
    if e and (_perf_time.time() - e['t']) < 5.0:
        return e['r']
    return None

def _git_cache_set(d, r):
    _GIT_SC[d] = {'r': r, 't': _perf_time.time()}

def _git_cache_clear(d):
    _GIT_SC.pop(d, None)


@app.route('/api/git/cache-clear', methods=['POST'])
def git_cache_clear():
    d = (request.get_json(silent=True) or {}).get('dir', START_DIR)
    _git_cache_clear(d)
    return jsonify({'ok': True})

# ════════════════════════════════════════════════════════════════
#  ChatGPT / OpenAI 整合
# ════════════════════════════════════════════════════════════════
@app.route('/api/ai/chat-openai', methods=['POST'])
def ai_chat_openai():
    """OpenAI GPT-4o SSE streaming — 對齊 Claude AI 格式"""
    import urllib.request as _ur, json as _js, ssl as _ssl
    d       = request.get_json(silent=True) or {}
    msgs    = d.get('messages', [])
    model   = d.get('model', 'gpt-4o')
    api_key = (d.get('key') or os.environ.get('OPENAI_API_KEY')
               or load_settings().get('openai_api_key', ''))

    if not api_key:
        return jsonify({'error': 'Missing OpenAI API key'}), 401

    def stream():
        body = _js.dumps({
            'model':       model,
            'messages':    msgs,
            'stream':      True,
            'max_tokens':  2048,
            'temperature': 0.7,
        }).encode()
        req = _ur.Request(
            'https://api.openai.com/v1/chat/completions',
            data=body,
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type':  'application/json',
            }
        )
        ctx = _ssl.create_default_context()
        try:
            with _ur.urlopen(req, context=ctx, timeout=60) as resp:
                for raw in resp:
                    line = raw.decode('utf-8', errors='replace').strip()
                    if not line.startswith('data: '): continue
                    data = line[6:]
                    if data == '[DONE]':
                        yield 'data: {"type":"done"}\n\n'
                        break
                    try:
                        chunk = _js.loads(data)
                        delta = chunk['choices'][0]['delta'].get('content', '')
                        if delta:
                            yield f'data: {_js.dumps({"type":"text","text":delta})}\n\n'
                    except Exception:
                        pass
        except Exception as e:
            yield f'data: {_js.dumps({"type":"error","error":str(e)})}\n\n'

    return Response(stream(), mimetype='text/event-stream',
                    headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})

@app.route('/api/settings/set-openai-key', methods=['POST'])
def settings_set_openai_key():
    d = request.get_json(silent=True) or {}
    key = d.get('key', '').strip()
    if key:
        ok = save_settings({'openai_api_key': key})
        if ok: os.environ['OPENAI_API_KEY'] = key
        return jsonify({'ok': ok})
    return jsonify({'ok': False, 'error': 'Empty key'})

@app.route('/api/ai/models')
def ai_models():
    """列出可用的 AI 模型"""
    settings = load_settings()
    has_claude = bool(settings.get('anthropic_api_key') or os.environ.get('ANTHROPIC_API_KEY'))
    has_openai = bool(settings.get('openai_api_key') or os.environ.get('OPENAI_API_KEY'))
    return jsonify({
        'models': [
            {'id':'claude-sonnet-4-6','name':'Claude Sonnet 4.6','provider':'anthropic',
             'available':has_claude,'icon':'⬡','desc':'Anthropic — 最聰明'},
            {'id':'gpt-4o',           'name':'GPT-4o',           'provider':'openai',
             'available':has_openai, 'icon':'✦','desc':'OpenAI — 第二聰明'},
            {'id':'gpt-4o-mini',      'name':'GPT-4o Mini',      'provider':'openai',
             'available':has_openai, 'icon':'✧','desc':'OpenAI — 快速便宜'},
        ],
        'has_claude': has_claude,
        'has_openai': has_openai,
    })

# ════════════════════════════════════════════════════════════════
#  AI AGENT — 本地 AI + 任務佇列 + 自動連續執行
# ════════════════════════════════════════════════════════════════
from core.agent import (add_task, get_tasks, get_task, update_task,
                        delete_task, clear_done, next_pending,
                        detect_local_ai, build_agent_prompt, QUICK_PROMPTS)

@app.route('/api/agent/tasks', methods=['GET'])
def agent_tasks_get():
    return jsonify({'tasks': get_tasks()})

@app.route('/api/agent/tasks', methods=['POST'])
def agent_tasks_post():
    d = request.get_json(silent=True) or {}
    task = add_task(
        title      = d.get('title', '未命名任務')[:120],
        prompt     = d.get('prompt', ''),
        context    = d.get('context', ''),
        quick_type = d.get('quick_type', ''),
    )
    return jsonify({'ok': True, 'task': task})

@app.route('/api/agent/tasks/<tid>', methods=['DELETE'])
def agent_task_delete(tid):
    delete_task(tid)
    return jsonify({'ok': True})

@app.route('/api/agent/tasks/clear-done', methods=['POST'])
def agent_clear_done():
    clear_done()
    return jsonify({'ok': True})

@app.route('/api/agent/run/<tid>')
def agent_run_task(tid):
    """SSE: 執行單一任務，串流回應"""
    import urllib.request as _ur, ssl as _ssl, json as _js

    task = get_task(tid)
    if not task:
        return jsonify({'error': 'Task not found'}), 404

    settings = load_settings()
    d_body   = request.args

    # Pick provider & key
    provider = request.args.get('provider', 'anthropic')
    model    = request.args.get('model', 'claude-sonnet-4-6')
    local_url= request.args.get('local_url', '')

    if provider == 'local' and local_url:
        api_key  = 'lm-studio'
        endpoint = local_url.rstrip('/') + '/v1/chat/completions'
    elif provider == 'openai':
        api_key  = (settings.get('openai_api_key') or
                    os.environ.get('OPENAI_API_KEY', ''))
        endpoint = 'https://api.openai.com/v1/chat/completions'
    else:
        # Use Claude via anthropic package
        pass

    def stream():
        update_task(tid, status='running', started_at=time.time(), result='', error='')
        yield f'data: {_js.dumps({"type":"status","status":"running","id":tid})}\n\n'

        prompt = build_agent_prompt(task)

        try:
            if provider == 'anthropic':
                # Use Anthropic SDK
                import anthropic as _ant
                api_key_ant = (settings.get('anthropic_api_key') or
                               os.environ.get('ANTHROPIC_API_KEY', ''))
                if not api_key_ant:
                    raise ValueError('Missing Anthropic API key')
                client = _ant.Anthropic(api_key=api_key_ant)
                result_text = ''
                with client.messages.stream(
                    model=model, max_tokens=4096,
                    messages=[{'role':'user','content':prompt}]
                ) as s:
                    for text in s.text_stream:
                        result_text += text
                        yield f'data: {_js.dumps({"type":"text","text":text,"id":tid})}\n\n'
                update_task(tid, status='done', result=result_text, done_at=time.time())

            else:
                # OpenAI-compatible (GPT-4o or Local AI)
                if not api_key:
                    raise ValueError(f'Missing API key for {provider}')
                body = _js.dumps({
                    'model': model, 'stream': True, 'max_tokens': 4096,
                    'messages': [{'role':'user','content':prompt}],
                }).encode()
                req = _ur.Request(endpoint, data=body, headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type':  'application/json',
                })
                ctx = _ssl._create_unverified_context()
                result_text = ''
                with _ur.urlopen(req, context=ctx, timeout=120) as resp:
                    for raw in resp:
                        line = raw.decode('utf-8','replace').strip()
                        if not line.startswith('data: '): continue
                        data = line[6:]
                        if data == '[DONE]': break
                        try:
                            chunk = _js.loads(data)
                            text  = chunk['choices'][0]['delta'].get('content','')
                            if text:
                                result_text += text
                                yield f'data: {_js.dumps({"type":"text","text":text,"id":tid})}\n\n'
                        except: pass
                update_task(tid, status='done', result=result_text, done_at=time.time())

            yield f'data: {_js.dumps({"type":"done","id":tid,"status":"done"})}\n\n'

        except Exception as e:
            err = str(e)[:200]
            update_task(tid, status='failed', error=err, done_at=time.time())
            yield f'data: {_js.dumps({"type":"error","error":err,"id":tid,"status":"failed"})}\n\n'

    return Response(stream(), mimetype='text/event-stream',
                    headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})

@app.route('/api/local-ai/status')
def local_ai_status():
    return jsonify(detect_local_ai())

@app.route('/api/agent/quick-types')
def agent_quick_types():
    return jsonify({'types': list(QUICK_PROMPTS.keys())})
