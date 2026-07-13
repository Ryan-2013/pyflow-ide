"""
Plugin Hot-Reload Watcher
=========================
Polls plugins/ directory every 1.5s.
On change → importlib.reload → broadcast 'plugins_reloaded' via Socket.IO.
"""
from __future__ import annotations
import importlib, os, sys, threading, time


class PluginWatcher:
    def __init__(self, plugins_dir: str, socketio):
        self._dir = plugins_dir
        self._sio = socketio
        self._mtimes: dict[str, float] = {}
        self._lock = threading.Lock()
        self._running = True
        self._scan()
        threading.Thread(target=self._poll, daemon=True, name='PluginWatcher').start()

    def _scan(self):
        for fname in os.listdir(self._dir):
            if fname.startswith('lang_') and fname.endswith('.py'):
                p = os.path.join(self._dir, fname)
                try:
                    self._mtimes[p] = os.path.getmtime(p)
                except OSError:
                    pass

    def _poll(self):
        while self._running:
            time.sleep(1.5)
            changed = []
            for fname in os.listdir(self._dir):
                if not (fname.startswith('lang_') and fname.endswith('.py')):
                    continue
                p = os.path.join(self._dir, fname)
                try:
                    mtime = os.path.getmtime(p)
                    with self._lock:
                        if self._mtimes.get(p) != mtime:
                            self._mtimes[p] = mtime
                            changed.append(fname)
                except OSError:
                    pass

            if changed:
                self._reload(changed)

    def _reload(self, changed_files: list[str]):
        import plugins as plug_sys
        for fname in changed_files:
            module_name = 'plugins.' + fname[:-3]
            try:
                if module_name in sys.modules:
                    importlib.reload(sys.modules[module_name])
                else:
                    importlib.import_module(module_name)
                print(f'[PluginWatcher] Reloaded {module_name}')
            except Exception as e:
                print(f'[PluginWatcher] Error reloading {module_name}: {e}')
                self._sio.emit('plugin_error', {'file': fname, 'error': str(e)})
                continue

        try:
            data = {'plugins': [p.to_dict() for p in plug_sys.all_plugins()],
                    'reloaded': changed_files}
            self._sio.emit('plugins_reloaded', data)
            print(f'[PluginWatcher] Broadcast reload: {changed_files}')
        except Exception as e:
            print(f'[PluginWatcher] Broadcast error: {e}')

    def stop(self):
        self._running = False
