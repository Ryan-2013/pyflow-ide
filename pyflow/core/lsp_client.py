"""
LSP 管理器 — JSON-RPC stdio 橋接。
管理 pylsp / gopls / rust-analyzer 行程，轉發請求並推送診斷。

架構：
  Browser (Socket.IO) ←→ Flask ←→ LSPClient ←→ LSP server (subprocess stdio)
"""
from __future__ import annotations
import json, os, queue, shutil, subprocess, sys, threading, time
from typing import Any, Callable

# ── 可用的 LSP 伺服器指令 ────────────────────────────────────────

def _find_python_lsp() -> list[str] | None:
    # 1. pylsp (python-lsp-server)
    if shutil.which('pylsp'):
        return ['pylsp']
    # 2. python -m pylsp
    r = subprocess.run([sys.executable, '-m', 'pylsp', '--version'],
                       capture_output=True, timeout=3)
    if r.returncode == 0:
        return [sys.executable, '-m', 'pylsp']
    # 3. pyright-langserver (microsoft pyright)
    if shutil.which('pyright-langserver'):
        return ['pyright-langserver', '--stdio']
    return None

def _find_go_lsp() -> list[str] | None:
    if shutil.which('gopls'):
        return ['gopls', 'serve']
    return None

def _find_rust_lsp() -> list[str] | None:
    if shutil.which('rust-analyzer'):
        return ['rust-analyzer']
    return None

LSP_CMDS = {
    'python': _find_python_lsp,
    'go':     _find_go_lsp,
    'rust':   _find_rust_lsp,
}


# ── JSON-RPC stdio client ─────────────────────────────────────────

class LSPClient:
    """
    單一 LSP 伺服器的 JSON-RPC 用戶端。
    每種語言/工作區一個實例。
    """

    def __init__(self, cmd: list[str], workspace: str,
                 on_notify: Callable[[dict], None]):
        self._cmd       = cmd
        self._workspace = workspace
        self._on_notify = on_notify   # 接收伺服器主動推送的通知
        self._proc:     subprocess.Popen | None = None
        self._lock      = threading.Lock()
        self._pending:  dict[int, queue.Queue] = {}
        self._id_seq    = 0
        self._alive     = False
        self._start()

    # ── 啟動 ───────────────────────────────────────────────────────

    def _start(self):
        try:
            env = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}
            self._proc = subprocess.Popen(
                self._cmd,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                cwd=self._workspace, env=env,
            )
            threading.Thread(target=self._read_loop, daemon=True, name='lsp-read').start()
            threading.Thread(target=self._stderr_drain, daemon=True, name='lsp-err').start()
            self._initialize()
            self._alive = True
        except Exception as e:
            print(f'[LSP] 啟動失敗 {self._cmd[0]}: {e}')

    def _initialize(self):
        caps = {
            'textDocument': {
                'hover':      {'contentFormat': ['markdown', 'plaintext']},
                'completion': {'completionItem': {'snippetSupport': True,
                                                  'documentationFormat': ['markdown', 'plaintext']}},
                'definition': {'linkSupport': False},
                'references': {},
                'publishDiagnostics': {'relatedInformation': True, 'versionSupport': True},
                'signatureHelp': {'signatureInformation': {'documentationFormat': ['markdown']}},
            },
            'workspace': {'workspaceFolders': True},
        }
        root = self._workspace
        result = self._request('initialize', {
            'processId':        os.getpid(),
            'rootUri':          f'file://{root}',
            'rootPath':         root,
            'capabilities':     caps,
            'workspaceFolders': [{'uri': f'file://{root}', 'name': os.path.basename(root)}],
            'initializationOptions': {},
        })
        if result is not None:
            self._send_notify('initialized', {})

    # ── I/O ────────────────────────────────────────────────────────

    def _write(self, obj: dict):
        """Encode and write a JSON-RPC message to stdin."""
        body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        header = f'Content-Length: {len(body)}\r\n\r\n'.encode()
        try:
            with self._lock:
                self._proc.stdin.write(header + body)
                self._proc.stdin.flush()
        except (BrokenPipeError, OSError):
            self._alive = False

    def _read_loop(self):
        """Continuously read JSON-RPC messages from stdout."""
        buf = b''
        while True:
            try:
                chunk = self._proc.stdout.read(1)
                if not chunk:
                    break
                buf += chunk

                # Parse headers
                while b'\r\n\r\n' in buf:
                    header_end = buf.index(b'\r\n\r\n')
                    header_raw = buf[:header_end].decode('utf-8', errors='replace')
                    buf = buf[header_end + 4:]

                    length = 0
                    for line in header_raw.split('\r\n'):
                        if line.lower().startswith('content-length:'):
                            length = int(line.split(':', 1)[1].strip())

                    if not length:
                        continue

                    # Read exact body
                    while len(buf) < length:
                        more = self._proc.stdout.read(length - len(buf))
                        if not more:
                            return
                        buf += more

                    body_raw, buf = buf[:length], buf[length:]
                    try:
                        msg = json.loads(body_raw.decode('utf-8'))
                    except Exception:
                        continue

                    self._dispatch(msg)

            except Exception:
                break
        self._alive = False

    def _dispatch(self, msg: dict):
        """Route incoming message: response or notification."""
        if 'id' in msg:
            req_id = msg['id']
            q = self._pending.get(req_id)
            if q:
                q.put(msg)
        elif 'method' in msg:
            try:
                self._on_notify(msg)
            except Exception:
                pass

    def _stderr_drain(self):
        for line in self._proc.stderr:
            pass  # Silently drain stderr

    # ── Public API ─────────────────────────────────────────────────

    def _request(self, method: str, params: Any, timeout: float = 8.0) -> Any:
        self._id_seq += 1
        req_id = self._id_seq
        q: queue.Queue = queue.Queue()
        self._pending[req_id] = q
        self._write({'jsonrpc': '2.0', 'id': req_id, 'method': method, 'params': params})
        try:
            resp = q.get(timeout=timeout)
            return resp.get('result')
        except queue.Empty:
            return None
        finally:
            self._pending.pop(req_id, None)

    def _send_notify(self, method: str, params: Any):
        self._write({'jsonrpc': '2.0', 'method': method, 'params': params})

    def request(self, method: str, params: Any) -> Any:
        if not self._alive or not self._proc:
            return None
        return self._request(method, params)

    def notify(self, method: str, params: Any):
        if self._alive and self._proc:
            self._send_notify(method, params)

    def is_alive(self) -> bool:
        return self._alive and self._proc is not None and self._proc.poll() is None

    def stop(self):
        self._alive = False
        if self._proc:
            try:
                self._send_notify('exit', None)
                time.sleep(0.1)
                self._proc.terminate()
            except Exception:
                pass


# ── LSP Manager ───────────────────────────────────────────────────

class LSPManager:
    """
    管理多個語言的 LSP 伺服器。
    每個 (lang, workspace) 組合一個 LSPClient 實例。
    """

    def __init__(self, socketio):
        self._sio     = socketio
        self._clients: dict[str, LSPClient] = {}
        self._cache:   dict[str, list[str] | None] = {}  # cmd cache

    def _key(self, lang: str, workspace: str) -> str:
        return f'{lang}:{workspace}'

    def _get_cmd(self, lang: str) -> list[str] | None:
        if lang not in self._cache:
            fn = LSP_CMDS.get(lang)
            self._cache[lang] = fn() if fn else None
        return self._cache[lang]

    def _make_notify(self, sid: str):
        def _on_notify(msg: dict):
            self._sio.emit('lsp_notify', msg, to=sid)
        return _on_notify

    def get_client(self, lang: str, workspace: str, sid: str) -> LSPClient | None:
        key = self._key(lang, workspace)
        client = self._clients.get(key)
        if client and client.is_alive():
            return client
        # Start new
        cmd = self._get_cmd(lang)
        if not cmd:
            return None
        client = LSPClient(cmd, workspace, self._make_notify(sid))
        self._clients[key] = client
        return client

    def request(self, lang: str, workspace: str, sid: str,
                method: str, params: Any) -> Any:
        c = self.get_client(lang, workspace, sid)
        return c.request(method, params) if c else None

    def notify(self, lang: str, workspace: str, sid: str,
               method: str, params: Any):
        c = self.get_client(lang, workspace, sid)
        if c:
            c.notify(method, params)

    def available(self, lang: str) -> bool:
        return self._get_cmd(lang) is not None

    def status(self) -> dict:
        return {
            'python': self.available('python'),
            'go':     self.available('go'),
            'rust':   self.available('rust'),
        }

    def stop_all(self):
        for c in self._clients.values():
            c.stop()
        self._clients.clear()
