"""Git operations: diff view, commit, branch, blame, staging."""
from __future__ import annotations
import os, re, subprocess
from pathlib import Path

def _git(args: list, cwd: str, timeout: int = 10) -> tuple[str, str, int]:
    r = subprocess.run(['git'] + args, cwd=cwd,
                       capture_output=True, text=True, timeout=timeout)
    return r.stdout, r.stderr, r.returncode

def diff_content(path: str) -> dict:
    """Return original (HEAD) vs current content for diff editor."""
    cwd = str(Path(path).parent)
    rel = os.path.basename(path)
    head, _, rc = _git(['show', f'HEAD:{rel}'], cwd)
    if rc != 0:
        head, _, rc = _git(['show', f'HEAD:./{rel}'], cwd)
    try:
        current = Path(path).read_text(encoding='utf-8', errors='replace')
    except Exception:
        current = ''
    return {'original': head if rc == 0 else '', 'modified': current, 'available': rc == 0}

def branches(cwd: str) -> dict:
    out, _, _ = _git(['branch', '-a', '--format=%(refname:short)'], cwd)
    cur, _, _ = _git(['branch', '--show-current'], cwd)
    return {
        'branches': [b.strip() for b in out.split('\n') if b.strip()],
        'current':  cur.strip(),
    }

def checkout(cwd: str, branch: str) -> dict:
    out, err, rc = _git(['checkout', branch], cwd)
    return {'ok': rc == 0, 'output': out or err}

def staged_files(cwd: str) -> list:
    out, _, _ = _git(['diff', '--cached', '--name-status'], cwd)
    result = []
    for line in out.strip().split('\n'):
        if not line: continue
        parts = line.split('\t', 1)
        if len(parts) == 2:
            result.append({'status': parts[0], 'file': parts[1]})
    return result

def unstaged_files(cwd: str) -> list:
    out, _, _ = _git(['status', '--porcelain'], cwd)
    result = []
    for line in out.strip().split('\n'):
        if not line: continue
        status = line[:2].strip()
        file   = line[3:].strip()
        if status and file:
            result.append({'status': status, 'file': file})
    return result

def stage(path: str, cwd: str) -> dict:
    _, err, rc = _git(['add', '--', path], cwd)
    return {'ok': rc == 0, 'error': err.strip()}

def unstage(path: str, cwd: str) -> dict:
    _, err, rc = _git(['reset', 'HEAD', '--', path], cwd)
    return {'ok': rc == 0, 'error': err.strip()}

def commit(cwd: str, message: str, stage_all: bool = False) -> dict:
    if stage_all:
        _git(['add', '-A'], cwd)
    out, err, rc = _git(['commit', '-m', message], cwd)
    return {'ok': rc == 0, 'output': (out + err).strip()}

def blame(path: str) -> dict:
    cwd = str(Path(path).parent)
    out, _, rc = _git(['blame', '--porcelain', '--', path], cwd)
    if rc != 0:
        return {'available': False, 'lines': []}
    lines, cur = [], {}
    for line in out.split('\n'):
        if line.startswith('\t'):
            lines.append({
                'hash':    cur.get('hash', '')[:8],
                'author':  cur.get('author', '?'),
                'time':    cur.get('time', ''),
                'summary': cur.get('summary', '')[:60],
            })
            cur = {}
        elif re.match(r'^[0-9a-f]{40}\s', line):
            cur['hash'] = line[:40]
        elif line.startswith('author '):
            cur['author'] = line[7:].strip()
        elif line.startswith('author-time '):
            from datetime import datetime
            try:
                cur['time'] = datetime.fromtimestamp(int(line[12:].strip())).strftime('%y-%m-%d')
            except Exception:
                cur['time'] = ''
        elif line.startswith('summary '):
            cur['summary'] = line[8:].strip()
    return {'available': True, 'lines': lines}


def remotes(cwd: str) -> dict:
    out, _, rc = _git(['remote', '-v'], cwd)
    r = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and '(fetch)' in line:
            r[parts[0]] = parts[1]
    return {'remotes': r, 'available': rc == 0}

def fetch(cwd: str, remote: str = 'origin') -> dict:
    out, err, rc = _git(['fetch', remote, '--prune'], cwd, timeout=30)
    return {'ok': rc == 0, 'output': (out + err).strip()}

def pull(cwd: str, remote: str = 'origin', branch: str = '') -> dict:
    args = ['pull', remote]
    if branch: args.append(branch)
    out, err, rc = _git(args + ['--rebase=false'], cwd, timeout=60)
    return {'ok': rc == 0, 'output': (out + err).strip()}

def push(cwd: str, remote: str = 'origin', branch: str = '', force: bool = False) -> dict:
    cur, _, _ = _git(['branch', '--show-current'], cwd)
    cur = cur.strip()
    args = ['push', remote, branch or cur]
    if force: args.append('--force-with-lease')
    out, err, rc = _git(args, cwd, timeout=60)
    return {'ok': rc == 0, 'output': (out + err).strip()}

def git_log(path: str, n: int = 40) -> dict:
    cwd = str(Path(path).parent) if path else '.'
    out, _, rc = _git(['log', '--pretty=format:%H|%h|%an|%ar|%s', f'-{n}', '--', path], cwd)
    if rc != 0:
        return {'available': False, 'commits': []}
    commits = []
    for line in out.strip().splitlines():
        if not line: continue
        parts = line.split('|', 4)
        if len(parts) == 5:
            commits.append({'full': parts[0], 'hash': parts[1], 'author': parts[2],
                           'when': parts[3], 'message': parts[4]})
    return {'available': True, 'commits': commits}

def git_show(cwd: str, commit_hash: str, path: str = '') -> dict:
    args = ['show', commit_hash]
    if path: args += ['--', path]
    out, err, rc = _git(args, cwd)
    return {'ok': rc == 0, 'content': out, 'error': err.strip()}
