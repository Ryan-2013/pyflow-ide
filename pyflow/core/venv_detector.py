"""
Python 虛擬環境偵測器。
掃描常見的 venv 格式：.venv / venv / conda / pipenv / pyenv
"""
from __future__ import annotations
import os, re, subprocess, sys
from pathlib import Path


_VENV_DIRS   = ['.venv', 'venv', 'env', '.env', 'virtualenv', '.virtualenv']
_BIN_NAMES   = ['python3', 'python', 'python.exe', 'python3.exe']
_BIN_SUBDIRS = ['bin', 'Scripts']


def _py_version(exe: str) -> str:
    try:
        r = subprocess.run([exe, '--version'], capture_output=True, text=True, timeout=3)
        return (r.stdout or r.stderr).strip().replace('Python ', '')
    except Exception:
        return ''


def detect(directory: str) -> dict:
    """
    在 directory（及其父目錄）搜尋虛擬環境。

    回傳：
    {
      'detected': [ {path, type, name, version, priority} ],
      'active':   { ... },   # 最佳選項
      'system':   str,       # 系統 Python 路徑
    }
    """
    directory = str(Path(directory).resolve())
    candidates: list[dict] = []

    # ── 搜尋目錄 ─────────────────────────────────────────────────
    search_dirs = [directory]
    p = Path(directory)
    for _ in range(4):
        p = p.parent
        if p == p.parent: break
        search_dirs.append(str(p))

    for sdir in search_dirs:
        for vname in _VENV_DIRS:
            vdir = Path(sdir) / vname
            if not vdir.is_dir():
                continue
            # Check pyvenv.cfg to confirm it's a real venv
            cfg = vdir / 'pyvenv.cfg'
            if not cfg.exists():
                continue
            for bdir in _BIN_SUBDIRS:
                for pyname in _BIN_NAMES:
                    exe = vdir / bdir / pyname
                    if exe.exists():
                        ver = _py_version(str(exe))
                        candidates.append({
                            'path':     str(exe),
                            'type':     'venv',
                            'name':     f'{vname}  ({ver})',
                            'version':  ver,
                            'priority': 10 if sdir == directory else 8,
                        })
                        break  # found one Python in this venv

    # ── pyenv (.python-version) ───────────────────────────────────
    for sdir in search_dirs:
        pv = Path(sdir) / '.python-version'
        if pv.exists():
            version = pv.read_text().strip()
            pyenv_root = os.environ.get('PYENV_ROOT', str(Path.home() / '.pyenv'))
            exe = Path(pyenv_root) / 'versions' / version / 'bin' / 'python'
            if exe.exists():
                candidates.append({
                    'path':     str(exe),
                    'type':     'pyenv',
                    'name':     f'pyenv  {version}',
                    'version':  version,
                    'priority': 9,
                })
            break

    # ── conda (environment.yml) ───────────────────────────────────
    for sdir in search_dirs:
        for fname in ('environment.yml', 'environment.yaml'):
            envfile = Path(sdir) / fname
            if not envfile.exists(): continue
            try:
                content = envfile.read_text(encoding='utf-8', errors='replace')
                m = re.search(r'^name:\s*(\S+)', content, re.M)
                if not m: continue
                env_name = m.group(1)
                r = subprocess.run(
                    ['conda', 'run', '-n', env_name, 'python', '--version'],
                    capture_output=True, text=True, timeout=5
                )
                ver = (r.stdout or r.stderr).strip().replace('Python ', '')
                candidates.append({
                    'path':     f'conda:{env_name}',
                    'type':     'conda',
                    'name':     f'conda  {env_name}  ({ver})',
                    'version':  ver,
                    'priority': 7,
                })
            except Exception:
                pass
            break

    # ── Pipenv ───────────────────────────────────────────────────
    for sdir in search_dirs:
        if (Path(sdir) / 'Pipfile').exists():
            try:
                r = subprocess.run(
                    ['pipenv', '--py'], cwd=sdir,
                    capture_output=True, text=True, timeout=5
                )
                if r.returncode == 0:
                    exe = r.stdout.strip()
                    ver = _py_version(exe)
                    candidates.append({
                        'path':     exe,
                        'type':     'pipenv',
                        'name':     f'Pipenv  ({ver})',
                        'version':  ver,
                        'priority': 6,
                    })
            except Exception:
                pass
            break

    # ── System Python ─────────────────────────────────────────────
    sys_ver = sys.version.split()[0]
    candidates.append({
        'path':     sys.executable,
        'type':     'system',
        'name':     f'System Python  {sys_ver}',
        'version':  sys_ver,
        'priority': 0,
    })

    # Sort by priority, deduplicate by path
    seen_paths: set[str] = set()
    deduped: list[dict] = []
    for c in sorted(candidates, key=lambda x: -x['priority']):
        if c['path'] not in seen_paths:
            seen_paths.add(c['path'])
            deduped.append(c)

    return {
        'detected': deduped,
        'active':   deduped[0] if deduped else None,
        'system':   sys.executable,
    }
