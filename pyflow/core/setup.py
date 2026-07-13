"""
PyFlow IDE — Setup Wizard Backend
===================================
Detects runtimes (Python/Go/Rust/Node/Java),
checks LSP server availability,
and provides one-click installation with streaming output.
"""
from __future__ import annotations
import json, os, platform, shutil, subprocess, sys
from pathlib import Path

# ── Platform detection ────────────────────────────────────────────
OS = platform.system()   # 'Darwin' | 'Linux' | 'Windows'

# ── Settings file (persistent, survives browser clear) ────────────
SETTINGS_FILE = Path.home() / '.pyflow' / 'settings.json'


def load_settings() -> dict:
    try:
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        if SETTINGS_FILE.exists():
            return json.loads(SETTINGS_FILE.read_text(encoding='utf-8'))
    except Exception:
        pass
    return {}


def save_settings(data: dict) -> bool:
    try:
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        existing = load_settings()
        existing.update(data)
        SETTINGS_FILE.write_text(json.dumps(existing, indent=2, ensure_ascii=False),
                                  encoding='utf-8')
        return True
    except Exception:
        return False


# ── Runtime definitions ───────────────────────────────────────────
RUNTIMES = [
    {
        'id':      'python',
        'display': 'Python',
        'cmd':     [sys.executable, '--version'],
        'icon':    'devicon-python-plain colored',
        'help':    'https://python.org/downloads/',
    },
    {
        'id':      'go',
        'display': 'Go',
        'cmd':     ['go', 'version'],
        'icon':    'devicon-go-original colored',
        'help':    'https://go.dev/dl/',
    },
    {
        'id':      'rust',
        'display': 'Rust',
        'cmd':     ['rustc', '--version'],
        'icon':    'devicon-rust-plain colored',
        'help':    'https://rustup.rs/',
    },
    {
        'id':      'node',
        'display': 'Node.js',
        'cmd':     ['node', '--version'],
        'icon':    'devicon-nodejs-plain colored',
        'help':    'https://nodejs.org/',
    },
    {
        'id':      'java',
        'display': 'Java',
        'cmd':     ['java', '-version'],
        'icon':    'devicon-java-plain colored',
        'help':    'https://adoptium.net/',
    },
]

# ── LSP definitions ───────────────────────────────────────────────
LSPS: list[dict] = [
    {
        'id':         'pylsp',
        'display':    'Python LSP (pylsp)',
        'lang':       'python',
        'check_cmd':  ['pylsp', '--version'],
        'check_alt':  [sys.executable, '-c', 'import pylsp; print(pylsp.__version__)'],
        'install':    [sys.executable, '-m', 'pip', 'install',
                       'python-lsp-server[all]', '--upgrade', '--quiet'],
        'requires':   'python',
        'note':       '包含 rope、pyflakes、autopep8',
        'icon':       'devicon-python-plain colored',
    },
    {
        'id':         'gopls',
        'display':    'Go LSP (gopls)',
        'lang':       'go',
        'check_cmd':  ['gopls', 'version'],
        'check_alt':  None,
        'install':    ['go', 'install', 'golang.org/x/tools/gopls@latest'],
        'requires':   'go',
        'note':       'Go 官方 LSP，自動補全、hover、跳轉',
        'icon':       'devicon-go-original colored',
    },
    {
        'id':         'rust-analyzer',
        'display':    'Rust Analyzer',
        'lang':       'rust',
        'check_cmd':  ['rust-analyzer', '--version'],
        'check_alt':  None,
        'install':    ['rustup', 'component', 'add', 'rust-analyzer'],
        'requires':   'rust',
        'note':       'rustup 安裝，自動補全、型別推斷',
        'icon':       'devicon-rust-plain colored',
    },
    {
        'id':         'typescript-language-server',
        'display':    'TypeScript LSP',
        'lang':       'typescript',
        'check_cmd':  ['typescript-language-server', '--version'],
        'check_alt':  None,
        'install':    ['npm', 'install', '-g',
                       'typescript-language-server', 'typescript'],
        'requires':   'node',
        'note':       '同時支援 JS 和 TS',
        'icon':       'devicon-typescript-plain colored',
    },
    {
        'id':         'clangd',
        'display':    'clangd（C / C++）',
        'lang':       'c',
        'check_cmd':  ['clangd', '--version'],
        'check_alt':  None,
        'install':    (['brew','install','llvm'] if OS=="Darwin" and shutil.which('brew') else ['sudo','apt','install','-y','clangd'] if OS=="Linux" and shutil.which('apt') else ['sudo','dnf','install','-y','clang-tools-extra'] if OS=="Linux" and shutil.which('dnf') else None),
        'requires':   None,
        'note':       ('Xcode 通常已內建，或用 brew 安裝' if OS=="Darwin" else 'apt install clangd' if OS=="Linux" else '請到 https://clangd.llvm.org/installation 下載'),
        'icon':       'devicon-cplusplus-plain colored',
    },
    {
        'id':         'bash-language-server',
        'display':    'Bash LSP',
        'lang':       'shell',
        'check_cmd':  ['bash-language-server', '--version'],
        'check_alt':  None,
        'install':    ['npm', 'install', '-g', 'bash-language-server'],
        'requires':   'node',
        'note':       'Shell 腳本補全、語法檢查',
        'icon':       'devicon-bash-plain colored',
    },
]


def _get_clangd_install() -> list | None:
    if OS == 'Darwin':
        if shutil.which('brew'):
            return ['brew', 'install', 'llvm']
    elif OS == 'Linux':
        if shutil.which('apt'):
            return ['sudo', 'apt', 'install', '-y', 'clangd']
        if shutil.which('dnf'):
            return ['sudo', 'dnf', 'install', '-y', 'clang-tools-extra']
    return None


def _get_clangd_note() -> str:
    if OS == 'Darwin':
        return 'Xcode 通常已內建，或用 brew 安裝'
    elif OS == 'Linux':
        return 'apt install clangd 或 apt install clang-tools-extra'
    else:
        return '請到 https://clangd.llvm.org/installation 下載'


# ── Check functions ───────────────────────────────────────────────

def check_runtime(runtime: dict) -> dict:
    """Check if a runtime is available and get its version."""
    cmd = runtime['cmd']
    # Try the primary executable
    exe = cmd[0]
    if exe != sys.executable and not shutil.which(exe):
        return {**runtime, 'available': False, 'version': None}
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        out = (r.stdout + r.stderr).strip().split('\n')[0][:80]
        return {**runtime, 'available': True, 'version': out}
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return {**runtime, 'available': False, 'version': None}


def check_lsp(lsp: dict) -> dict:
    """Check if an LSP server is installed."""
    # Primary check
    for cmd in [lsp['check_cmd'], lsp.get('check_alt')]:
        if not cmd:
            continue
        exe = cmd[0]
        if exe != sys.executable and not shutil.which(exe):
            continue
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if r.returncode == 0 or r.returncode == 1:  # some tools exit 1 for --version
                out = (r.stdout + r.stderr).strip().split('\n')[0][:80]
                return {**lsp, 'installed': True, 'version': out,
                        'can_install': False}
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass
    return {**lsp, 'installed': False, 'version': None,
            'can_install': lsp['install'] is not None}


def get_full_status() -> dict:
    """Get status of all runtimes and LSPs."""
    runtimes = [check_runtime(r) for r in RUNTIMES]
    runtime_map = {r['id']: r['available'] for r in runtimes}

    lsps = []
    for lsp in LSPS:
        status = check_lsp(lsp)
        req = lsp.get('requires')
        status['runtime_ok'] = (req is None or runtime_map.get(req, False))
        lsps.append(status)

    # Additional tools
    tools = []
    for name, cmd, display in [
        ('rg',       ['rg', '--version'],        'ripgrep（快速搜尋）'),
        ('shfmt',    ['shfmt', '--version'],      'shfmt（Shell 格式化）'),
        ('prettier', ['prettier', '--version'],   'Prettier（JS/TS 格式化）'),
        ('black',    ['black', '--version'],      'black（Python 格式化）'),
        ('gofmt',    ['gofmt', '-l'],             'gofmt（Go 格式化）'),
    ]:
        avail = bool(shutil.which(cmd[0]))
        tools.append({'id': name, 'display': display, 'available': avail})

    settings = load_settings()
    return {
        'runtimes': runtimes,
        'lsps':     lsps,
        'tools':    tools,
        'platform': OS,
        'python':   sys.executable,
        'api_key_set': bool(settings.get('anthropic_api_key') or
                            os.environ.get('ANTHROPIC_API_KEY')),
    }


def install_lsp_stream(lsp_id: str):
    """Generator: stream installation output line by line."""
    lsp = next((l for l in LSPS if l['id'] == lsp_id), None)
    if not lsp:
        yield f"data: {json.dumps({'type':'error','msg':'未知的 LSP: ' + lsp_id})}\n\n"
        return

    cmd = lsp.get('install')
    if not cmd:
        yield f"data: {json.dumps({'type':'error','msg':'此 LSP 需要手動安裝'})}\n\n"
        return

    yield f"data: {json.dumps({'type':'start','cmd':' '.join(cmd)})}\n\n"

    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1
        )
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                yield f"data: {json.dumps({'type':'line','line':line})}\n\n"
        proc.wait()
        success = proc.returncode == 0
        yield f"data: {json.dumps({'type':'done','code':proc.returncode,'ok':success})}\n\n"
    except FileNotFoundError as e:
        yield f"data: {json.dumps({'type':'error','msg':'找不到命令：' + str(e)})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'type':'error','msg':str(e)})}\n\n"
