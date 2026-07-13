"""
PyFlow 附加核心模組：
  profiler   — cProfile 整合，回傳每個函式的耗時
  coverage   — pytest-cov 整合，回傳行覆蓋率
  debugger   — debugpy DAP 橋接
  workspace  — .pyflow.json 設定讀寫
  export_html — 匯出互動式獨立 HTML
  dead_code   — 從呼叫圖找出未被呼叫的函式
"""
from __future__ import annotations
import cProfile, io, json, os, pstats, shutil, socket, subprocess, sys
import threading, time
from pathlib import Path


# ═══════════════════════════════════════════════════════════
# PROFILER
# ═══════════════════════════════════════════════════════════

def run_profiler(path: str) -> dict:
    """
    以 cProfile 執行 Python 腳本，回傳每個函式的耗時資料。
    Returns: { functions: {name: {file, line, calls, time_ms, cumtime_ms}},
               total_ms, error }
    """
    import copy, io as _io
    if not os.path.isfile(path):
        return {'functions': {}, 'total_ms': 0, 'error': 'File not found'}

    pr = cProfile.Profile()
    captured_out = _io.StringIO()
    old_stdout, old_stderr = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = captured_out

    try:
        pr.enable()
        exec(  # nosec
            compile(Path(path).read_text(encoding='utf-8', errors='replace'), path, 'exec'),
            {'__file__': path, '__name__': '__main__',
             '__spec__': None, '__builtins__': __builtins__},
        )
        pr.disable()
    except SystemExit:
        pr.disable()
    except Exception as e:
        pr.disable()
        return {'functions': {}, 'total_ms': 0, 'error': str(e),
                'output': captured_out.getvalue()}
    finally:
        sys.stdout, sys.stderr = old_stdout, old_stderr

    stats = pstats.Stats(pr, stream=io.StringIO())
    functions: dict = {}
    total = 0.0

    for (fname, lineno, funcname), (_, ncalls, tt, ct, _) in stats.stats.items():  # type: ignore
        is_own = fname == path or fname == os.path.abspath(path)
        functions[funcname] = {
            'file':       fname,
            'line':       lineno,
            'calls':      ncalls,
            'time_ms':    round(tt * 1000, 3),
            'cumtime_ms': round(ct * 1000, 3),
            'own':        is_own,
        }
        if is_own:
            total += ct

    # Sort by cumtime
    functions = dict(sorted(functions.items(), key=lambda x: -x[1]['cumtime_ms']))

    return {
        'functions': functions,
        'total_ms':  round(total * 1000, 3),
        'error':     None,
        'output':    captured_out.getvalue()[-2000:],
    }


# ═══════════════════════════════════════════════════════════
# COVERAGE
# ═══════════════════════════════════════════════════════════

def run_coverage(path: str) -> dict:
    """
    執行 pytest --cov，回傳每個檔案的行覆蓋率。
    Returns: { available, files: {path: {executed, missing, percent}}, total_percent }
    """
    cwd = str(Path(path).parent)
    cov_file = Path(cwd) / 'coverage.json'
    if cov_file.exists():
        cov_file.unlink()

    try:
        subprocess.run(
            [sys.executable, '-m', 'pytest', path,
             f'--cov={cwd}', '--cov-report=json', '-q', '--no-header', '--tb=no'],
            capture_output=True, text=True, timeout=60, cwd=cwd,
        )
    except subprocess.TimeoutExpired:
        return {'available': False, 'error': 'Timeout', 'files': {}}
    except FileNotFoundError:
        return {'available': False, 'error': 'pytest not found', 'files': {}}

    if not cov_file.exists():
        return {'available': False, 'error': 'coverage.json not generated (pip install pytest-cov)', 'files': {}}

    try:
        raw = json.loads(cov_file.read_text())
        files = {}
        for fname, data in raw.get('files', {}).items():
            files[fname] = {
                'executed': data.get('executed_lines', []),
                'missing':  data.get('missing_lines', []),
                'percent':  round(data.get('summary', {}).get('percent_covered', 0), 1),
            }
        return {
            'available':     True,
            'files':         files,
            'total_percent': round(raw.get('totals', {}).get('percent_covered', 0), 1),
        }
    except Exception as e:
        return {'available': False, 'error': str(e), 'files': {}}


# ═══════════════════════════════════════════════════════════
# DEBUGGER  (debugpy + DAP over TCP)
# ═══════════════════════════════════════════════════════════

class _DAPConn:
    """Raw DAP protocol over TCP."""

    def __init__(self, host: str, port: int, on_msg):
        self._s = socket.create_connection((host, port), timeout=10)
        self._on = on_msg
        self._pending: dict[int, threading.Event] = {}
        self._results: dict = {}
        self._seq = 0
        self._lock = threading.Lock()
        threading.Thread(target=self._recv, daemon=True).start()

    def _send(self, obj: dict):
        body = json.dumps(obj).encode()
        hdr  = f'Content-Length: {len(body)}\r\n\r\n'.encode()
        with self._lock:
            self._s.sendall(hdr + body)

    def request(self, cmd: str, args=None, timeout=6.0):
        self._seq += 1
        seq = self._seq
        ev  = threading.Event()
        self._pending[seq] = ev
        self._send({'seq': seq, 'type': 'request', 'command': cmd, 'arguments': args or {}})
        ev.wait(timeout)
        return self._results.pop(seq, None)

    def notify(self, method: str, params=None):
        self._seq += 1
        self._send({'seq': self._seq, 'type': 'request', 'command': method, 'arguments': params or {}})

    def _recv(self):
        buf = b''
        while True:
            try:
                chunk = self._s.recv(8192)
                if not chunk: break
                buf += chunk
                while b'\r\n\r\n' in buf:
                    hi = buf.index(b'\r\n\r\n')
                    hraw = buf[:hi].decode()
                    buf  = buf[hi+4:]
                    clen = 0
                    for h in hraw.split('\r\n'):
                        if h.lower().startswith('content-length:'):
                            clen = int(h.split(':',1)[1].strip())
                    while len(buf) < clen:
                        buf += self._s.recv(8192)
                    msg, buf = json.loads(buf[:clen]), buf[clen:]
                    if msg.get('type') == 'response':
                        seq = msg.get('request_seq')
                        self._results[seq] = msg.get('body')
                        ev  = self._pending.pop(seq, None)
                        if ev: ev.set()
                    elif msg.get('type') in ('event', 'request'):
                        try: self._on(msg)
                        except Exception: pass
            except Exception:
                break

    def close(self):
        try: self._s.close()
        except: pass


class DebugSession:
    """One active debug session."""

    def __init__(self, path: str, breakpoints: dict, sid: str, socketio):
        self._path = path
        self._bp   = breakpoints  # {filepath: [line, ...]}
        self._sid  = sid
        self._sio  = socketio
        self._dap: _DAPConn | None = None
        self._proc: subprocess.Popen | None = None
        with socket.socket() as s:
            s.bind(('', 0))
            self._port = s.getsockname()[1]

    def _emit(self, ev: str, data: dict):
        self._sio.emit('dbg_' + ev, data, to=self._sid)

    def _on_msg(self, msg: dict):
        ev   = msg.get('event', '')
        body = msg.get('body') or {}
        if ev == 'stopped':
            tid = body.get('threadId', 1)
            self._emit('stopped', {'reason': body.get('reason', 'pause'), 'threadId': tid})
            # Auto-fetch stack + variables
            stack = self._dap.request('stackTrace', {'threadId': tid, 'levels': 20}) or {}
            frames = stack.get('stackFrames', [])
            self._emit('stack', {'stackFrames': frames})
            if frames:
                fid = frames[0]['id']
                scopes = (self._dap.request('scopes', {'frameId': fid}) or {}).get('scopes', [])
                for sc in scopes:
                    if sc.get('name') in ('Locals', 'Local', 'Variables'):
                        vs = self._dap.request('variables', {'variablesReference': sc['variablesReference']}) or {}
                        self._emit('variables', {'variables': vs.get('variables', []), 'scope': sc['name']})
                        break
        elif ev in ('terminated', 'exited'):
            self._emit('terminated', {})
        elif ev == 'output':
            self._emit('output', {'category': body.get('category', 'stdout'), 'text': body.get('output', '')})

    def start(self):
        if not shutil.which('debugpy') and subprocess.run(
            [sys.executable, '-m', 'debugpy', '--version'],
            capture_output=True).returncode != 0:
            self._emit('error', {'message': 'debugpy 未安裝，請執行：pip install debugpy'})
            return

        cmd = [sys.executable, '-m', 'debugpy',
               '--listen', f'127.0.0.1:{self._port}',
               '--wait-for-client', self._path]
        self._proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=os.path.dirname(os.path.abspath(self._path)),
        )

        def _drain(pipe, cat):
            for line in pipe:
                self._emit('output', {'category': cat, 'text': line.decode('utf-8', 'replace')})
        threading.Thread(target=_drain, args=(self._proc.stdout, 'stdout'), daemon=True).start()
        threading.Thread(target=_drain, args=(self._proc.stderr, 'stderr'), daemon=True).start()

        def _connect():
            for _ in range(30):
                try:
                    self._dap = _DAPConn('127.0.0.1', self._port, self._on_msg)
                    break
                except Exception:
                    time.sleep(0.2)
            if not self._dap:
                self._emit('error', {'message': '無法連接 debugpy'}); return

            self._dap.request('initialize', {
                'adapterID': 'python', 'clientID': 'pyflow',
                'pathFormat': 'path', 'linesStartAt1': True, 'columnsStartAt1': True,
                'supportsVariableType': True, 'supportsEvaluateForHovers': True,
            })
            for fpath, lines in self._bp.items():
                self._dap.request('setBreakpoints', {
                    'source': {'path': fpath},
                    'breakpoints': [{'line': l} for l in lines],
                })
            self._dap.request('configurationDone', {})
            self._emit('started', {'port': self._port, 'pid': self._proc.pid})

        threading.Thread(target=_connect, daemon=True).start()

    def command(self, cmd: str, args=None):
        return self._dap.request(cmd, args) if self._dap else None

    def evaluate(self, expr: str, frame_id: int = 0) -> dict:
        r = self._dap.request('evaluate', {
            'expression': expr, 'frameId': frame_id, 'context': 'repl',
        }) if self._dap else None
        return r or {}

    def stop(self):
        if self._dap:
            self._dap.request('disconnect', {'restart': False})
            self._dap.close()
        if self._proc:
            self._proc.terminate()


class DebugManager:
    def __init__(self, socketio):
        self._sio = socketio
        self._sessions: dict[str, DebugSession] = {}

    def start(self, sid: str, path: str, breakpoints: dict) -> DebugSession:
        if sid in self._sessions:
            self._sessions[sid].stop()
        s = DebugSession(path, breakpoints, sid, self._sio)
        self._sessions[sid] = s
        s.start()
        return s

    def cmd(self, sid: str, command: str, args=None):
        s = self._sessions.get(sid)
        return s.command(command, args) if s else None

    def evaluate(self, sid: str, expr: str, frame_id: int = 0):
        s = self._sessions.get(sid)
        return s.evaluate(expr, frame_id) if s else {}

    def stop(self, sid: str):
        s = self._sessions.pop(sid, None)
        if s: s.stop()


# ═══════════════════════════════════════════════════════════
# WORKSPACE SETTINGS  (.pyflow.json)
# ═══════════════════════════════════════════════════════════

def ws_load(directory: str) -> dict:
    f = Path(directory) / '.pyflow.json'
    if not f.exists(): return {}
    try: return json.loads(f.read_text(encoding='utf-8'))
    except: return {}

def ws_save(directory: str, config: dict) -> bool:
    try:
        (Path(directory) / '.pyflow.json').write_text(
            json.dumps(config, indent=2, ensure_ascii=False), encoding='utf-8')
        return True
    except: return False


# ═══════════════════════════════════════════════════════════
# DEAD CODE DETECTION
# ═══════════════════════════════════════════════════════════

def find_dead_code(parse_result: dict, directory: str | None = None) -> set[str]:
    """
    從解析結果找出從未被呼叫的函式/方法。
    返回 dead function id 的集合。
    """
    definitions = {d['id'] for d in (parse_result.get('definitions') or [])}
    called: set[str] = set()

    # 從 flow 中的 calls 欄位收集所有被呼叫的函式
    for node in (parse_result.get('flow') or []):
        called.update(node.get('calls') or [])

    # 如果有目錄，也掃描同目錄其他檔案的呼叫
    # (簡化版：只做單檔案分析)
    dead = definitions - called
    # 排除 main、__init__、特殊方法等
    EXCLUDE = {'main', '__init__', '__main__', '__str__', '__repr__', '__enter__', '__exit__'}
    dead -= EXCLUDE
    return dead


# ═══════════════════════════════════════════════════════════
# EXPORT INTERACTIVE HTML
# ═══════════════════════════════════════════════════════════

_VIEWER_JS = """
// PyFlow Interactive Viewer (embedded)
const data={GRAPH_JSON};
const TI={NODE_TYPES_JSON};
const W=document.getElementById('cw').offsetWidth,H=document.getElementById('cw').offsetHeight;
const svgEl=document.getElementById('svg');
const $e=(t,a)=>{const e=document.createElementNS('http://www.w3.org/2000/svg',t);Object.entries(a||{}).forEach(([k,v])=>e.setAttribute(k,v));return e;};
const vp=svgEl.querySelector('#vp')||$e('g',{id:'vp'});svgEl.appendChild(vp);
let vx=0,vy=0,vz=1;
const setVP=()=>vp.setAttribute('transform',`translate(${vx},${vy}) scale(${vz})`);
svgEl.addEventListener('wheel',e=>{e.preventDefault();const f=e.deltaY<0?1.1:.91;const r=svgEl.getBoundingClientRect();vx-=(e.clientX-r.left-vx)*(f-1);vy-=(e.clientY-r.top-vy)*(f-1);vz=Math.max(.05,Math.min(4,vz*f));setVP();},{passive:false});
let pd=false,px=0,py=0;
svgEl.addEventListener('mousedown',e=>{pd=true;px=e.clientX-vx;py=e.clientY-vy;});
svgEl.addEventListener('mousemove',e=>{if(!pd)return;vx=e.clientX-px;vy=e.clientY-py;setVP();});
svgEl.addEventListener('mouseup',()=>pd=false);
// Render flow nodes
const NW=240,NS=16,MT=60;let cy=MT;
(data.flow||[]).forEach(n=>{
  const info=TI[n.type]||TI.other;
  const h=Math.max(34,28);
  const g=$e('g',{transform:`translate(${NW/2+40-NW/2},${cy})`});
  g.appendChild($e('rect',{width:NW,height:h,rx:4,fill:'#050505',stroke:'#1a1a1a','stroke-width':1}));
  g.appendChild($e('rect',{width:NW,height:16,rx:4,fill:info.c}));
  g.appendChild($e('rect',{y:8,width:NW,height:8,fill:info.c}));
  const tl=$e('text',{x:7,y:11.5,fill:'rgba(255,255,255,.25)',style:'font:9px monospace'}); tl.textContent=n.type.toUpperCase().slice(0,10);g.appendChild(tl);
  const lbl=$e('text',{x:8,y:28,fill:'#c8c8c8',style:'font:600 12.5px sans-serif'}); lbl.textContent=n.label;g.appendChild(lbl);
  if(n.line){const ll=$e('text',{x:NW-5,y:11.5,'text-anchor':'end',fill:'rgba(255,255,255,.25)',style:'font:10px monospace'}); ll.textContent='L'+n.line;g.appendChild(ll);}
  g.style.cursor='pointer';
  g.addEventListener('click',()=>{document.getElementById('info').textContent=`[${n.type}] ${n.label}${n.line?' L'+n.line:''}`});
  vp.appendChild(g); cy+=h+NS;
});
// Render definitions
let dy=MT;const DEF_X=820;
(data.definitions||[]).forEach(d=>{
  const h=34;
  const g=$e('g',{transform:`translate(${DEF_X},${dy})`});
  const bg=d.type==='function'?'#1e2a3a':'#2a1e2a';
  g.appendChild($e('rect',{width:260,height:h,rx:4,fill:'#050505',stroke:'#1a1a1a','stroke-width':1}));
  g.appendChild($e('rect',{width:260,height:18,rx:4,fill:bg}));
  g.appendChild($e('rect',{y:10,width:260,height:8,fill:bg}));
  const lbl=$e('text',{x:8,y:13,fill:'#e0e0e0',style:'font:700 11.5px sans-serif'}); lbl.textContent=(d.label||d.id).slice(0,26);g.appendChild(lbl);
  vp.appendChild(g); dy+=h+NS;
});
// Separator
const sep=$e('line',{x1:DEF_X-20,y1:0,x2:DEF_X-20,y2:Math.max(cy,dy)+100,stroke:'#0a0a0a','stroke-width':1});vp.appendChild(sep);
// Fit
const aw=Math.max(NW+80,DEF_X+280),ah=Math.max(cy,dy)+60;
const sw=svgEl.clientWidth||800,sh=svgEl.clientHeight||500;
const z=Math.min(sw/aw,sh/ah,.95);vx=(sw-aw*z)/2+10;vy=(sh-ah*z)/2+10;vz=z;setVP();
"""

def export_html(graph: dict, filename: str = 'pyflow') -> str:
    """Generate a self-contained interactive HTML file from graph data."""
    node_types = {
        'import':    '#1e3a5f','assign':'#1a3a2a','call':'#2a1a3a',
        'goroutine': '#1a3a1a','channel':'#0a2a2a','match':'#3a2a1a',
        'condition': '#3a2a1a','loop':'#1a2a3a','context':'#2a2a0a',
        'exception': '#3a1a1a','flow_ctrl':'#2a1a2a','function':'#1e2a3a',
        'class':     '#2a1e2a','unsafe_block':'#3a0a0a','error_check':'#3a1a0a',
        'defer':     '#1a1a3a','select':'#2a1a0a','other':'#0a0a0a',
    }
    ti_json = json.dumps({k: {'c': v} for k, v in node_types.items()})
    graph_json = json.dumps(graph)
    viewer_js = _VIEWER_JS.replace('{GRAPH_JSON}', graph_json).replace('{NODE_TYPES_JSON}', ti_json)

    html = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8">
<title>{filename} — PyFlow</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#000;color:#c8c8c8;font-family:system-ui,sans-serif;height:100vh;display:flex;flex-direction:column}}
.hdr{{padding:8px 16px;background:#080808;border-bottom:1px solid #141414;display:flex;align-items:center;gap:12px;flex-shrink:0}}
.hdr h1{{font-size:14px;font-weight:700;color:#c8c8c8}}
.hdr .sub{{font-size:11px;color:#3a3a3a}}
#info{{margin-left:auto;font-size:11px;color:#3b82f6;font-family:monospace}}
#cw{{flex:1;position:relative;overflow:hidden}}
svg{{width:100%;height:100%;display:block;cursor:grab}}
svg:active{{cursor:grabbing}}
defs{{display:none}}
</style>
</head>
<body>
<div class="hdr">
  <h1>⬡ PyFlow</h1>
  <span class="sub">{filename}</span>
  <span id="info">點擊節點查看詳情 · 滾輪縮放 · 拖曳平移</span>
</div>
<div id="cw">
  <svg id="svg">
    <defs>
      <pattern id="dotg" width="28" height="28" patternUnits="userSpaceOnUse">
        <circle cx="1.5" cy="1.5" r="1" fill="#080808"/>
      </pattern>
    </defs>
    <rect x="-99999" y="-99999" width="199998" height="199998" fill="url(#dotg)"/>
  </svg>
</div>
<script>{viewer_js}</script>
</body>
</html>"""
    return html
