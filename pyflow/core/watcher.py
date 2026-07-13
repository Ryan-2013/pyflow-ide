"""
磁碟檔案監控器 — 輪詢式，無需 watchdog。
偵測到變更時透過 Socket.IO 推送 file_changed 事件。
"""
from __future__ import annotations
import os, threading, time
from typing import Callable


class FileWatcher:
    """
    每 1.5 秒輪詢各 Socket.IO session 所監視的檔案。
    偵測到 mtime 變化 → 呼叫 on_change(sid, path)。
    """

    def __init__(self, on_change: Callable[[str, str], None]):
        self._on_change = on_change
        self._watches: dict[str, dict[str, float]] = {}  # {sid: {path: mtime}}
        self._lock = threading.Lock()
        self._running = True
        threading.Thread(target=self._poll, daemon=True, name='FileWatcher').start()

    # ── Public ────────────────────────────────────────────────────

    def watch(self, sid: str, path: str):
        """開始監視 path（屬於 session sid）。"""
        if not path or not os.path.isfile(path):
            return
        with self._lock:
            if sid not in self._watches:
                self._watches[sid] = {}
            try:
                self._watches[sid][path] = os.path.getmtime(path)
            except OSError:
                pass

    def unwatch(self, sid: str, path: str | None = None):
        """停止監視 path 或整個 session 的所有路徑。"""
        with self._lock:
            if sid not in self._watches:
                return
            if path is None:
                del self._watches[sid]
            else:
                self._watches[sid].pop(path, None)

    def stop(self):
        self._running = False

    # ── Internal ──────────────────────────────────────────────────

    def _poll(self):
        while self._running:
            time.sleep(1.5)
            with self._lock:
                snapshot = {s: dict(paths) for s, paths in self._watches.items()}

            for sid, files in snapshot.items():
                for path, old_mtime in files.items():
                    try:
                        new_mtime = os.path.getmtime(path)
                    except OSError:
                        continue
                    if new_mtime != old_mtime:
                        with self._lock:
                            if sid in self._watches and path in self._watches[sid]:
                                self._watches[sid][path] = new_mtime
                        try:
                            self._on_change(sid, path)
                        except Exception:
                            pass
