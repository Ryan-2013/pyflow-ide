"""
跨檔案搜尋 — 支援純文字、大小寫敏感、正規表達式。
限制：
  - 只搜尋文字型檔案（.py .go .rs .md .json .yaml 等）
  - 跳過 __pycache__ / node_modules / .git 等目錄
  - 最多回傳 500 個結果
"""
from __future__ import annotations
import os, re
from pathlib import Path

# 可搜尋的副檔名
TEXT_EXTS = frozenset({
    '.py', '.pyw', '.go', '.rs', '.md', '.mdx', '.txt',
    '.json', '.yaml', '.yml', '.toml', '.xml', '.html', '.htm',
    '.css', '.scss', '.less', '.js', '.jsx', '.ts', '.tsx',
    '.sh', '.bash', '.zsh', '.fish', '.sql', '.ini', '.env',
    '.cfg', '.conf', '.rb', '.php', '.r', '.swift', '.kt',
    '.gitignore', '.dockerignore', '.editorconfig',
    '.prettierrc', '.babelrc', 'Makefile', 'Dockerfile',
})

# 跳過的目錄
SKIP_DIRS = frozenset({
    '__pycache__', 'node_modules', '.git', '.hg', '.svn',
    '.venv', 'venv', 'env', '.env', 'dist', 'build',
    '.pytest_cache', '.mypy_cache', '.tox', 'target',
    '.cargo', 'vendor',
})

MAX_RESULTS = 500
MAX_FILE_SIZE = 2 * 1024 * 1024  # 2 MB


def search_files(
    directory: str,
    query: str,
    *,
    case_sensitive: bool = False,
    use_regex: bool = False,
    include_ext: list[str] | None = None,
) -> dict:
    """
    在 directory 中遞迴搜尋 query。
    
    Returns:
        {
          'results': [{file, name, line, col, text, match_start, match_end}],
          'total': int,
          'truncated': bool,
          'error': str | None,
        }
    """
    if not query or len(query.strip()) == 0:
        return {'results': [], 'total': 0, 'truncated': False, 'error': None}

    # Compile pattern
    try:
        flags = 0 if case_sensitive else re.IGNORECASE
        if use_regex:
            pattern = re.compile(query, flags)
        else:
            # Plain text — escape for regex
            pattern = re.compile(re.escape(query), flags)
    except re.error as e:
        return {'results': [], 'total': 0, 'truncated': False, 'error': f'正規表達式錯誤：{e}'}

    results: list[dict] = []
    total = 0
    truncated = False
    allowed_exts = {('.' + e.lstrip('.')) for e in include_ext} if include_ext else None

    for root, dirs, files in os.walk(directory, followlinks=False):
        # Prune skipped dirs in-place
        dirs[:] = sorted(
            d for d in dirs
            if not d.startswith('.') and d not in SKIP_DIRS
        )

        for fname in sorted(files):
            ext = Path(fname).suffix.lower() or fname.lower()
            if allowed_exts:
                if ext not in allowed_exts and fname.lower() not in allowed_exts:
                    continue
            elif ext not in TEXT_EXTS and fname.lower() not in TEXT_EXTS:
                continue

            fpath = os.path.join(root, fname)
            try:
                if os.path.getsize(fpath) > MAX_FILE_SIZE:
                    continue
                code = Path(fpath).read_text(encoding='utf-8', errors='replace')
            except (OSError, PermissionError):
                continue

            lines = code.split('\n')
            for lineno, line in enumerate(lines, 1):
                for m in pattern.finditer(line):
                    total += 1
                    if len(results) < MAX_RESULTS:
                        results.append({
                            'file':        fpath,
                            'name':        fname,
                            'line':        lineno,
                            'col':         m.start() + 1,
                            'text':        line[:300],
                            'match_start': m.start(),
                            'match_end':   m.end(),
                        })
                    else:
                        truncated = True

            if truncated:
                break
        if truncated:
            break

    return {
        'results':   results,
        'total':     total,
        'truncated': truncated,
        'error':     None,
    }


def search_files_rg(directory: str, query: str,
                    case_sensitive: bool = False,
                    use_regex: bool = False,
                    max_results: int = 200) -> dict:
    """
    ripgrep-powered search (10-100× faster than Python).
    Falls back to search_files() if rg not available.
    """
    import shutil, subprocess, json as _json

    if not shutil.which('rg'):
        return search_files(directory, query, case_sensitive=case_sensitive, use_regex=use_regex)

    args = ['rg', '--json', f'--max-count={max_results}',
            '--max-filesize=2M', '--hidden']
    if not case_sensitive:
        args.append('--ignore-case')
    if not use_regex:
        args.append('--fixed-strings')
    args.append('--')
    args.append(query)
    args.append(directory)

    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=15)
        results = []
        seen = 0
        for line in r.stdout.splitlines():
            if not line.strip(): continue
            try:
                obj = _json.loads(line)
            except Exception:
                continue
            if obj.get('type') == 'match':
                data = obj['data']
                fpath = data['path']['text']
                for sub in data['submatches']:
                    results.append({
                        'file':  fpath,
                        'line':  data['line_number'],
                        'text':  data['lines']['text'].rstrip('\n'),
                        'match': sub['match']['text'],
                    })
                    seen += 1
                    if seen >= max_results:
                        break
            if seen >= max_results:
                break
        return {'results': results, 'total': seen, 'engine': 'ripgrep'}
    except subprocess.TimeoutExpired:
        return search_files(directory, query, case_sensitive=case_sensitive, use_regex=use_regex)
    except Exception as e:
        return search_files(directory, query, case_sensitive=case_sensitive, use_regex=use_regex)
