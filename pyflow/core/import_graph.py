"""
Import 依賴樹
=============
分析 Python 專案中所有 import 語句，建立模組層次依賴圖。
不同於呼叫圖（函式→函式），這裡是模組→模組的依賴關係。
"""
from __future__ import annotations
import ast, os, sys
from pathlib import Path

_SKIP_DIRS  = {'__pycache__', '.git', '.venv', 'venv', 'env', 'node_modules',
               'dist', 'build', '.pytest_cache', '.mypy_cache', 'target', '.eggs'}
_STDLIB     = set(sys.stdlib_module_names) if hasattr(sys, 'stdlib_module_names') else set()


def _rel_to_module(rel_path: str) -> str:
    """Convert relative path to module name: a/b/c.py → a.b.c"""
    return rel_path.replace(os.sep, '.').replace('/', '.').removesuffix('.py').lstrip('.')


def _parse_imports(code: str) -> list[tuple[str, str]]:
    """
    Return list of (from, name) import tuples.
    from: "" for plain imports, "module" for from-imports.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    result = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                result.append(('', alias.name.split('.')[0]))
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                result.append((node.module, node.module.split('.')[0]))
            elif node.level > 0:
                # relative import: can't resolve without package info
                pass
    return result


def build_import_graph(directory: str, max_files: int = 150,
                       include_stdlib: bool = False,
                       include_third_party: bool = True) -> dict:
    """
    Build a module dependency graph for a Python project.

    Returns:
    {
      "nodes": [{"id", "label", "file", "rel", "is_local", "import_count"}],
      "edges": [{"from", "to", "kind": "direct"|"relative"}],
      "files": int,
      "stats": {"local": int, "stdlib": int, "third_party": int},
    }
    """
    directory = os.path.abspath(directory)
    local_modules: set[str] = set()
    file_map: dict[str, str] = {}   # module_name → abs_path
    file_codes: dict[str, str] = {} # abs_path → code

    # ── 1. Scan project files ────────────────────────────────────────
    count = 0
    for root, dirs, files in os.walk(directory):
        dirs[:] = sorted(d for d in dirs if d not in _SKIP_DIRS and not d.startswith('.'))
        for fname in sorted(files):
            if not fname.endswith('.py'): continue
            if count >= max_files: break
            fpath = os.path.join(root, fname)
            rel   = os.path.relpath(fpath, directory)
            mod   = _rel_to_module(rel)
            local_modules.add(mod)
            # Also register top-level package names
            top = mod.split('.')[0]
            local_modules.add(top)
            file_map[mod] = fpath
            try:
                file_codes[fpath] = open(fpath, encoding='utf-8', errors='replace').read()
            except Exception:
                pass
            count += 1
        if count >= max_files: break

    # ── 2. Build graph ───────────────────────────────────────────────
    nodes:      dict[str, dict] = {}
    edges:      list[dict]      = []
    seen_edges: set[str]        = set()
    stats = {'local': 0, 'stdlib': 0, 'third_party': 0, 'skipped': 0}

    def add_node(mod: str, fpath: str | None = None, rel: str | None = None) -> bool:
        if mod in nodes: return True
        is_local = mod in local_modules or mod.split('.')[0] in local_modules
        is_std   = mod in _STDLIB or mod.split('.')[0] in _STDLIB
        is_third = not is_local and not is_std
        if is_std   and not include_stdlib:      stats['skipped'] += 1; return False
        if is_third and not include_third_party: stats['skipped'] += 1; return False
        if is_local:    stats['local']       += 1
        elif is_std:    stats['stdlib']      += 1
        else:           stats['third_party'] += 1
        nodes[mod] = {
            'id':           mod,
            'label':        mod.split('.')[-1] if '.' in mod else mod,
            'full':         mod,
            'file':         fpath or '',
            'rel':          rel or mod,
            'is_local':     is_local,
            'is_stdlib':    is_std,
            'is_third':     is_third,
            'import_count': 0,
        }
        return True

    # Add all local modules first
    for mod, fpath in file_map.items():
        rel = os.path.relpath(fpath, directory)
        add_node(mod, fpath, rel)

    # Parse imports and build edges
    for mod, fpath in file_map.items():
        code = file_codes.get(fpath, '')
        for _, imported in _parse_imports(code):
            if not imported: continue
            if add_node(imported):
                key = f'{mod}→{imported}'
                if key not in seen_edges and mod != imported:
                    seen_edges.add(key)
                    edges.append({'from': mod, 'to': imported,
                                  'local_to_local': (mod in local_modules and imported in local_modules)})
                    if imported in nodes:
                        nodes[imported]['import_count'] += 1

    # Detect circular imports
    adjacency: dict[str, set[str]] = {}
    for e in edges:
        adjacency.setdefault(e['from'], set()).add(e['to'])

    def has_cycle(start: str, target: str, visited: set) -> bool:
        if start == target: return True
        if start in visited: return False
        visited.add(start)
        return any(has_cycle(n, target, visited) for n in adjacency.get(start, set()))

    for e in edges:
        if has_cycle(e['to'], e['from'], set()):
            e['cyclic'] = True

    return {
        'nodes': list(nodes.values()),
        'edges': edges,
        'files': count,
        'stats': stats,
    }
