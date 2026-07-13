"""Terminal subprocess manager for PyFlow IDE."""
import os
import sys
import subprocess
import threading
import shutil
from typing import Callable


def _default_shell() -> str:
    if sys.platform == 'win32':
        return os.environ.get('COMSPEC', 'cmd.exe')
    return os.environ.get('SHELL', shutil.which('bash') or '/bin/bash')


class Terminal:
    """
    Wraps an interactive shell subprocess and bridges I/O via callbacks.
    Uses pty on Unix for proper terminal behaviour (Ctrl+C, etc.),
    falls back to plain subprocess.PIPE on Windows or if pty is unavailable.
    """

    def __init__(self, cwd: str, on_output: Callable[[str], None]):
        self.cwd = cwd
        self.on_output = on_output
        self._proc: subprocess.Popen | None = None
        self._running = False
        self._master_fd: int | None = None

    # ─── Public ──────────────────────────────────────────────────

    def start(self):
        shell = _default_shell()
        try:
            self._start_pty(shell)
        except Exception:
            self._start_pipe(shell)

    def write(self, data: str):
        if self._master_fd is not None:
            try:
                os.write(self._master_fd, data.encode())
                return
            except OSError:
                pass
        if self._proc and self._proc.stdin:
            try:
                self._proc.stdin.write(data.encode())
                self._proc.stdin.flush()
            except OSError:
                pass

    def resize(self, rows: int, cols: int):
        """Send TIOCSWINSZ to the pty (Unix only)."""
        if self._master_fd is None:
            return
        try:
            import fcntl, termios, struct
            winsize = struct.pack('HHHH', rows, cols, 0, 0)
            fcntl.ioctl(self._master_fd, termios.TIOCSWINSZ, winsize)
        except Exception:
            pass

    def stop(self):
        self._running = False
        if self._master_fd is not None:
            try:
                os.close(self._master_fd)
            except OSError:
                pass
            self._master_fd = None
        if self._proc:
            try:
                self._proc.terminate()
            except Exception:
                pass

    # ─── Internal ────────────────────────────────────────────────

    def _start_pty(self, shell: str):
        import pty
        master_fd, slave_fd = pty.openpty()
        self._master_fd = master_fd
        self._proc = subprocess.Popen(
            [shell], stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
            cwd=self.cwd, close_fds=True,
            env={**os.environ, 'TERM': 'xterm-256color'},
        )
        os.close(slave_fd)
        self._running = True
        threading.Thread(target=self._read_pty, daemon=True).start()

    def _read_pty(self):
        while self._running:
            try:
                data = os.read(self._master_fd, 4096)
                if not data:
                    break
                self.on_output(data.decode('utf-8', errors='replace'))
            except OSError:
                break
        self.on_output('\r\n[terminal closed]\r\n')

    def _start_pipe(self, shell: str):
        self._proc = subprocess.Popen(
            [shell], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            cwd=self.cwd, bufsize=0,
            env={**os.environ},
        )
        self._running = True
        threading.Thread(target=self._read_pipe, daemon=True).start()

    def _read_pipe(self):
        assert self._proc and self._proc.stdout
        while self._running:
            try:
                chunk = self._proc.stdout.read(1024)
                if not chunk:
                    break
                self.on_output(chunk.decode('utf-8', errors='replace'))
            except OSError:
                break
        self.on_output('\r\n[terminal closed]\r\n')
