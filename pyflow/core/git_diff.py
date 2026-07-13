"""
Git 行內 Diff — 取得檔案的行級變更資訊，用於 Monaco 邊欄裝飾。
"""
from __future__ import annotations
import os, re, subprocess


def get_diff(path: str) -> dict:
    """
    取得 path 相對於 git HEAD 的行變更。
    回傳: { available, changes:[{line,type}], added, modified, deleted }
    type: 'added' | 'modified' | 'deleted'
    """
    if not path or not os.path.isfile(path):
        return {'available': False, 'changes': [], 'error': 'File not found'}
    cwd = os.path.dirname(os.path.abspath(path))

    def _run(cmd):
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=5)

    try:
        # Prefer: diff HEAD vs working tree (includes both staged and unstaged)
        r = _run(['git', 'diff', 'HEAD', '--', path])
        if not r.stdout:
            # New file staged: diff against empty tree
            r = _run(['git', 'diff', '--cached', '--', path])
        if not r.stdout:
            # No changes
            return {'available': True, 'changes': [], 'added': 0, 'modified': 0, 'deleted': 0}

        changes = _parse_diff(r.stdout)
        stats = {
            'added':    sum(1 for c in changes if c['type'] == 'added'),
            'modified': sum(1 for c in changes if c['type'] == 'modified'),
            'deleted':  sum(1 for c in changes if c['type'] == 'deleted'),
        }
        return {'available': True, 'changes': changes, **stats}

    except FileNotFoundError:
        return {'available': False, 'changes': [], 'error': 'git not found'}
    except subprocess.TimeoutExpired:
        return {'available': False, 'changes': [], 'error': 'git timeout'}
    except Exception as e:
        return {'available': False, 'changes': [], 'error': str(e)}


def _parse_diff(text: str) -> list:
    """
    解析 unified diff 格式，回傳每行的變更類型。
    只追蹤新檔案（+行）的位置。
    """
    changes: list[dict] = []
    cur = 0          # 當前新檔案的行號

    # Track consecutive deleted lines to mark as 'deleted' hint
    pending_del: list[int] = []

    for line in text.split('\n'):
        if line.startswith('@@'):
            m = re.search(r'\+(\d+)(?:,(\d+))?', line)
            if m:
                cur = int(m.group(1))
            continue

        if line.startswith('+++') or line.startswith('---'):
            continue

        if line.startswith('+'):
            changes.append({'line': cur, 'type': 'added'})
            cur += 1
        elif line.startswith('-'):
            # Deleted lines: mark the line just after as "deletion above"
            changes.append({'line': max(cur, 1), 'type': 'deleted'})
        elif line.startswith('\\'):
            pass
        else:
            cur += 1

    # De-duplicate deleted markers (multiple deletes above same line)
    seen = set()
    deduped = []
    for c in changes:
        key = (c['line'], c['type'])
        if key not in seen:
            seen.add(key)
            deduped.append(c)

    # Mark added lines that are adjacent to deleted lines as 'modified'
    deleted_lines = {c['line'] for c in deduped if c['type'] == 'deleted'}
    result = []
    for c in deduped:
        if c['type'] == 'added' and c['line'] in deleted_lines:
            result.append({'line': c['line'], 'type': 'modified'})
        else:
            result.append(c)

    return result
