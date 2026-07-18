from __future__ import annotations

import ast
import os
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PYFLOW_DIR = Path(__file__).resolve().parent
if str(PYFLOW_DIR) not in sys.path:
    sys.path.insert(0, str(PYFLOW_DIR))


TEXT_EXTS = {
    ".py", ".pyw", ".go", ".rs", ".js", ".jsx", ".ts", ".tsx",
    ".json", ".md", ".txt", ".toml", ".yaml", ".yml", ".html",
    ".htm", ".css", ".scss", ".xml", ".sql", ".sh", ".bat",
    ".ps1", ".c", ".h", ".cpp", ".cc", ".cxx", ".hpp", ".hxx",
    ".hh", ".inl", ".zy",
    ".ini", ".cfg", ".conf", ".env", ".gitignore",
}

SKIP_DIRS = {
    "__pycache__", ".git", ".hg", ".svn", "node_modules", ".venv",
    "venv", "env", ".env", "dist", "build", ".pytest_cache",
    ".mypy_cache", ".tox", "target",
}


@dataclass
class ReadResult:
    content: str
    encoding: str
    error: str | None = None


@dataclass
class WriteResult:
    ok: bool
    error: str | None = None


def normalize_path(path: str | os.PathLike[str]) -> str:
    return str(Path(path).expanduser().resolve())


def language_for_path(path: str) -> str:
    ext = Path(path).suffix.lower()
    return {
        ".py": "python",
        ".pyw": "python",
        ".go": "go",
        ".rs": "rust",
        ".c": "c",
        ".h": "c",
        ".cpp": "cpp",
        ".cc": "cpp",
        ".cxx": "cpp",
        ".hpp": "cpp",
        ".hxx": "cpp",
        ".hh": "cpp",
        ".inl": "cpp",
        ".zy": "zyenlang",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".json": "json",
        ".md": "markdown",
        ".html": "html",
        ".htm": "html",
        ".css": "css",
        ".toml": "toml",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".sql": "sql",
        ".sh": "shell",
        ".ps1": "shell",
        ".bat": "shell",
    }.get(ext, "text")


def is_likely_text(path: str) -> bool:
    p = Path(path)
    if p.name in {"Makefile", "Dockerfile"}:
        return True
    if p.suffix.lower() in TEXT_EXTS:
        return True
    try:
        sample = p.read_bytes()[:4096]
    except OSError:
        return False
    return b"\x00" not in sample


def detect_encoding(raw: bytes) -> str:
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    for enc in ("utf-8", "utf-16", "cp950", "big5", "cp1252"):
        try:
            raw.decode(enc)
            return enc
        except UnicodeDecodeError:
            pass
    try:
        import chardet  # type: ignore

        detected = chardet.detect(raw).get("encoding")
        if detected:
            return {"ascii": "utf-8", "gb2312": "gbk", "gb18030": "gbk"}.get(
                detected.lower(), detected
            )
    except Exception:
        pass
    return "utf-8"


def read_text(path: str) -> ReadResult:
    try:
        raw = Path(path).read_bytes()
        encoding = detect_encoding(raw)
        return ReadResult(raw.decode(encoding, errors="replace"), encoding)
    except Exception as exc:
        return ReadResult("", "utf-8", str(exc))


def write_text(path: str, content: str, encoding: str = "utf-8") -> WriteResult:
    try:
        Path(path).write_text(content, encoding=encoding, newline="")
        return WriteResult(True)
    except Exception as exc:
        return WriteResult(False, str(exc))


def _project_path(path: str, root: str, *, allow_root: bool = False) -> Path:
    target = Path(path).expanduser().resolve()
    project = Path(root).expanduser().resolve()
    if not target.is_relative_to(project):
        raise ValueError("只能操作目前專案資料夾內的檔案")
    if not allow_root and target == project:
        raise ValueError("不能修改或刪除專案根目錄")
    return target


def create_file(directory: str, name: str, root: str) -> WriteResult:
    try:
        if not name.strip() or Path(name).name != name or name in {".", ".."}:
            raise ValueError("請輸入有效的檔案名稱")
        parent = _project_path(directory, root, allow_root=True)
        target = _project_path(str(parent / name), root)
        target.touch(exist_ok=False)
        return WriteResult(True)
    except Exception as exc:
        return WriteResult(False, str(exc))


def create_directory(directory: str, name: str, root: str) -> WriteResult:
    try:
        if not name.strip() or Path(name).name != name or name in {".", ".."}:
            raise ValueError("請輸入有效的資料夾名稱")
        parent = _project_path(directory, root, allow_root=True)
        target = _project_path(str(parent / name), root)
        target.mkdir()
        return WriteResult(True)
    except Exception as exc:
        return WriteResult(False, str(exc))


def rename_path(path: str, new_name: str, root: str) -> tuple[WriteResult, str | None]:
    try:
        if not new_name.strip() or Path(new_name).name != new_name or new_name in {".", ".."}:
            raise ValueError("請輸入有效的新名稱")
        source = _project_path(path, root)
        target = _project_path(str(source.with_name(new_name)), root)
        if target.exists():
            raise FileExistsError(f"{new_name} 已經存在")
        source.rename(target)
        return WriteResult(True), str(target)
    except Exception as exc:
        return WriteResult(False, str(exc)), None


def delete_path(path: str, root: str) -> WriteResult:
    try:
        target = _project_path(path, root)
        if target.is_dir() and not target.is_symlink():
            shutil.rmtree(target)
        else:
            target.unlink()
        return WriteResult(True)
    except Exception as exc:
        return WriteResult(False, str(exc))


def list_files(directory: str) -> dict[str, Any]:
    root = Path(directory)
    entries: list[dict[str, Any]] = []
    try:
        for child in sorted(root.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            if child.name.startswith(".") or child.name in SKIP_DIRS:
                continue
            entries.append(
                {
                    "name": child.name,
                    "path": str(child),
                    "type": "dir" if child.is_dir() else "file",
                    "size": 0 if child.is_dir() else child.stat().st_size,
                    "is_python": child.suffix.lower() in {".py", ".pyw"},
                }
            )
        return {"path": str(root), "name": root.name or str(root), "entries": entries}
    except Exception as exc:
        return {"path": str(root), "name": root.name or str(root), "entries": [], "error": str(exc)}


def parse_source(path: str, code: str) -> dict[str, Any]:
    lang = language_for_path(path)
    try:
        if lang == "python":
            from core.ast_parser import parse_python_file

            result = parse_python_file(code, path)
        elif lang == "go":
            from core.go_parser import parse_go_file

            result = parse_go_file(code, path)
        elif lang == "rust":
            from core.rust_parser import parse_rust_file

            result = parse_rust_file(code, path)
        elif lang == "c":
            from plugins.lang_c import parse_c

            result = parse_c(code, path)
        elif lang == "cpp":
            from plugins.lang_cpp import parse_cpp

            result = parse_cpp(code, path)
        elif lang == "zyenlang":
            from qt_zyenlang import parse_zyenlang_source

            result = parse_zyenlang_source(code, path)
        else:
            result = {"flow": [], "definitions": [], "error": None}

        try:
            from core.symbols import extract_symbols

            if lang != "zyenlang":
                result["symbols"] = extract_symbols(result, lang, code)
        except Exception:
            result.setdefault("symbols", [])
        result["lang"] = lang
        return result
    except Exception as exc:
        return {"flow": [], "definitions": [], "symbols": [], "lang": lang, "error": str(exc)}


def build_python_graph(code: str) -> dict[str, Any]:
    """Build a bounded function and method call graph for the Qt node view."""
    max_nodes = 120
    max_edges = 320
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return {"nodes": [], "edges": [], "error": f"第 {exc.lineno or 0} 行：{exc.msg}"}
    except Exception as exc:
        return {"nodes": [], "edges": [], "error": str(exc)}

    nodes: list[dict[str, Any]] = [
        {
            "id": "__module__",
            "label": "程式入口",
            "kind": "module",
            "line": 1,
            "signature": "頂層程式碼",
            "doc": "模組匯入與直接執行的程式碼",
            "parameters": [],
            "return_type": "Any",
        }
    ]
    owners: dict[ast.AST, str] = {}
    known: dict[str, str] = {}
    definition_count = 0

    def one_line(value: str | None, limit: int = 150) -> str:
        text = " ".join((value or "").strip().split())
        return text if len(text) <= limit else text[: limit - 1] + "…"

    def function_signature(
        item: ast.FunctionDef | ast.AsyncFunctionDef,
        display_name: str,
    ) -> str:
        try:
            args = ast.unparse(item.args)
            returns = f" → {ast.unparse(item.returns)}" if item.returns else ""
            prefix = "async " if isinstance(item, ast.AsyncFunctionDef) else ""
            return one_line(f"{prefix}{display_name}({args}){returns}")
        except Exception:
            return display_name

    def expression_text(value: ast.AST | None, fallback: str = "Any") -> str:
        if value is None:
            return fallback
        try:
            return ast.unparse(value)
        except Exception:
            return fallback

    def function_parameters(
        item: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> list[dict[str, str]]:
        parameters: list[dict[str, str]] = []
        positional = list(item.args.posonlyargs) + list(item.args.args)
        defaults: list[ast.AST | None] = [None] * (
            len(positional) - len(item.args.defaults)
        ) + list(item.args.defaults)
        for argument, default in zip(positional, defaults):
            if argument.arg in {"self", "cls"}:
                continue
            parameters.append(
                {
                    "name": argument.arg,
                    "type": expression_text(argument.annotation),
                    "default": expression_text(default, "") if default else "",
                }
            )
        if item.args.vararg:
            parameters.append(
                {
                    "name": "*" + item.args.vararg.arg,
                    "type": expression_text(item.args.vararg.annotation),
                    "default": "",
                }
            )
        for argument, default in zip(item.args.kwonlyargs, item.args.kw_defaults):
            parameters.append(
                {
                    "name": argument.arg,
                    "type": expression_text(argument.annotation),
                    "default": expression_text(default, "") if default else "",
                }
            )
        if item.args.kwarg:
            parameters.append(
                {
                    "name": "**" + item.args.kwarg.arg,
                    "type": expression_text(item.args.kwarg.annotation),
                    "default": "",
                }
            )
        return parameters

    def class_signature(item: ast.ClassDef) -> str:
        try:
            bases = ", ".join(ast.unparse(base) for base in item.bases)
            return one_line(f"class {item.name}({bases})" if bases else f"class {item.name}")
        except Exception:
            return f"class {item.name}"

    def add_node(item: ast.AST, node: dict[str, Any], lookup_name: str) -> bool:
        if len(nodes) >= max_nodes:
            return False
        nodes.append(node)
        node_id = str(node["id"])
        owners[item] = node_id
        known.setdefault(lookup_name, node_id)
        return True

    for item in tree.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            definition_count += 1
            node_id = item.name
            add_node(
                item,
                {
                    "id": node_id,
                    "label": item.name,
                    "kind": "async" if isinstance(item, ast.AsyncFunctionDef) else "function",
                    "line": item.lineno,
                    "signature": function_signature(item, item.name),
                    "doc": one_line(ast.get_docstring(item)),
                    "parameters": function_parameters(item),
                    "return_type": expression_text(item.returns),
                },
                item.name,
            )
        elif isinstance(item, ast.ClassDef):
            definition_count += 1
            class_id = item.name
            add_node(
                item,
                {
                    "id": class_id,
                    "label": item.name,
                    "kind": "class",
                    "line": item.lineno,
                    "signature": class_signature(item),
                    "doc": one_line(ast.get_docstring(item)),
                    "parameters": [],
                    "return_type": item.name,
                },
                item.name,
            )
            for child in item.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    definition_count += 1
                    node_id = f"{item.name}.{child.name}"
                    add_node(
                        child,
                        {
                            "id": node_id,
                            "label": node_id,
                            "kind": "method",
                            "line": child.lineno,
                            "signature": function_signature(child, node_id),
                            "doc": one_line(ast.get_docstring(child)),
                            "parameters": function_parameters(child),
                            "return_type": expression_text(child.returns),
                        },
                        child.name,
                    )

    edges: set[tuple[str, str]] = set()

    def call_name(call: ast.Call) -> str | None:
        if isinstance(call.func, ast.Name):
            return call.func.id
        if isinstance(call.func, ast.Attribute):
            return call.func.attr
        return None

    class CallCollector(ast.NodeVisitor):
        def __init__(self, owner_id: str) -> None:
            self.owner_id = owner_id

        def visit_Call(self, node: ast.Call) -> None:
            if len(edges) < max_edges:
                name = call_name(node)
                target = known.get(name or "")
                if target and target != self.owner_id:
                    edges.add((self.owner_id, target))
            self.generic_visit(node)

        def visit_FunctionDef(self, _: ast.FunctionDef) -> None:
            return

        def visit_AsyncFunctionDef(self, _: ast.AsyncFunctionDef) -> None:
            return

        def visit_ClassDef(self, _: ast.ClassDef) -> None:
            return

    def record_calls(owner_id: str, body: list[ast.stmt]) -> None:
        collector = CallCollector(owner_id)
        for statement in body:
            if len(edges) >= max_edges:
                break
            collector.visit(statement)

    top_level: list[ast.stmt] = []
    for item in tree.body:
        owner_id = owners.get(item)
        if owner_id:
            if isinstance(item, ast.ClassDef):
                class_body = [
                    child
                    for child in item.body
                    if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                ]
                record_calls(owner_id, class_body)
                for child in item.body:
                    method_id = owners.get(child)
                    if method_id:
                        record_calls(method_id, getattr(child, "body", []))
            else:
                record_calls(owner_id, getattr(item, "body", []))
        else:
            top_level.append(item)
    record_calls("__module__", top_level)

    node_ids = {str(node["id"]) for node in nodes}
    bounded_edges = [
        {"source": source, "target": target}
        for source, target in sorted(edges)
        if source in node_ids and target in node_ids
    ][:max_edges]
    incoming = {node_id: 0 for node_id in node_ids}
    outgoing = {node_id: 0 for node_id in node_ids}
    call_targets: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
    for edge in bounded_edges:
        source = str(edge["source"])
        target = str(edge["target"])
        outgoing[source] += 1
        incoming[target] += 1
        call_targets[source].append(target)
    for node in nodes:
        node_id = str(node["id"])
        node["outgoing"] = outgoing[node_id]
        node["incoming"] = incoming[node_id]
        node["calls"] = call_targets[node_id][:12]

    return {
        "nodes": nodes,
        "edges": bounded_edges,
        "truncated": definition_count + 1 > len(nodes) or len(edges) >= max_edges,
        "total_definitions": definition_count + 1,
        "source_lines": code.count("\n") + 1,
        "error": None,
    }


def _mask_brace_language(code: str) -> str:
    """Mask comments and strings while preserving offsets and line breaks."""
    chars = list(code)
    index = 0
    state = "code"
    quote = ""
    while index < len(chars):
        current = chars[index]
        following = chars[index + 1] if index + 1 < len(chars) else ""
        if state == "code":
            if current == "/" and following == "/":
                chars[index] = chars[index + 1] = " "
                index += 2
                state = "line_comment"
                continue
            if current == "/" and following == "*":
                chars[index] = chars[index + 1] = " "
                index += 2
                state = "block_comment"
                continue
            if current in {'"', "'"}:
                quote = current
                chars[index] = " "
                state = "string"
        elif state == "line_comment":
            if current == "\n":
                state = "code"
            else:
                chars[index] = " "
        elif state == "block_comment":
            if current == "*" and following == "/":
                chars[index] = chars[index + 1] = " "
                index += 2
                state = "code"
                continue
            if current != "\n":
                chars[index] = " "
        elif state == "string":
            if current == "\\" and following:
                if current != "\n":
                    chars[index] = " "
                if following != "\n":
                    chars[index + 1] = " "
                index += 2
                continue
            if current == quote:
                chars[index] = " "
                state = "code"
            elif current != "\n":
                chars[index] = " "
        index += 1
    return "".join(chars)


def _split_signature_items(text: str) -> list[str]:
    items: list[str] = []
    start = 0
    depths = {"(": 0, "[": 0, "{": 0, "<": 0}
    closing = {")": "(", "]": "[", "}": "{", ">": "<"}
    quote = ""
    escaped = False
    for index, char in enumerate(text):
        if escaped:
            escaped = False
            continue
        if char == "\\" and quote:
            escaped = True
            continue
        if char in {'"', "'"}:
            quote = "" if quote == char else (char if not quote else quote)
            continue
        if quote:
            continue
        if char in depths:
            depths[char] += 1
        elif char in closing and depths[closing[char]]:
            depths[closing[char]] -= 1
        elif char == "," and not any(depths.values()):
            items.append(text[start:index].strip())
            start = index + 1
    tail = text[start:].strip()
    if tail:
        items.append(tail)
    return items


def _brace_signature_details(
    signature: str,
    name: str,
    lang: str,
) -> tuple[list[dict[str, str]], str]:
    name_match = re.search(rf"(?<![\w]){re.escape(name)}\s*\(", signature)
    if not name_match:
        return [], "Any"
    opening = signature.find("(", name_match.start())
    depth = 0
    closing = -1
    for index in range(opening, len(signature)):
        if signature[index] == "(":
            depth += 1
        elif signature[index] == ")":
            depth -= 1
            if depth == 0:
                closing = index
                break
    if closing < 0:
        return [], "Any"

    parameters: list[dict[str, str]] = []
    raw_parameters = signature[opening + 1 : closing].strip()
    for raw_item in _split_signature_items(raw_parameters):
        item = raw_item.strip()
        if not item or item == "void" or item in {"self", "&self", "&mut self"}:
            continue
        default = ""
        default_parts = _split_signature_items(item.replace("=", ",", 1))
        if "=" in item and len(default_parts) >= 2:
            item, default = item.split("=", 1)
            item = item.strip()
            default = default.strip()

        parameter_name = ""
        parameter_type = "Any"
        if lang == "rust":
            if ":" in item:
                left, right = item.split(":", 1)
                parameter_name = re.sub(r"^(?:mut|ref)\s+", "", left.strip())
                parameter_type = right.strip() or "Any"
            else:
                parameter_name = item.lstrip("&").strip()
        elif lang == "go":
            parts = item.split()
            if len(parts) >= 2:
                parameter_name = parts[0]
                parameter_type = " ".join(parts[1:])
            else:
                parameter_name = item
        else:
            match = re.search(r"([A-Za-z_]\w*)\s*(\[[^\]]*\])?$", item)
            if match:
                parameter_name = match.group(1)
                suffix = match.group(2) or ""
                parameter_type = (
                    item[: match.start(1)].strip() + suffix
                ).strip() or "Any"
            else:
                parameter_name = item
        if parameter_name in {"self", "cls"}:
            continue
        parameters.append(
            {
                "name": parameter_name or "Any",
                "type": parameter_type or "Any",
                "default": default,
            }
        )

    before_name = signature[: name_match.start()].strip()
    after_parameters = signature[closing + 1 :].strip().rstrip("{").strip()
    if lang == "rust":
        return_match = re.search(r"->\s*(.+)$", after_parameters)
        return_type = return_match.group(1).strip() if return_match else "()"
    elif lang == "go":
        return_type = after_parameters or "void"
    else:
        return_type = before_name or "Any"
        return_type = re.sub(
            r"^(?:template\s*<[^>]*>\s*)?(?:(?:static|inline|constexpr|extern|virtual)\s+)*",
            "",
            return_type,
        ).strip() or "Any"
    return parameters, return_type


def _build_brace_graph(path: str, code: str, lang: str) -> dict[str, Any]:
    max_nodes = 120
    max_edges = 320
    parsed = parse_source(path, code)
    if parsed.get("error"):
        return {"nodes": [], "edges": [], "error": str(parsed["error"])}

    language_names = {"go": "Go", "rust": "Rust", "c": "C", "cpp": "C++"}
    nodes: list[dict[str, Any]] = [
        {
            "id": "__module__",
            "label": "程式入口",
            "kind": "module",
            "line": 1,
            "signature": f"{language_names.get(lang, lang)} 頂層程式碼",
            "doc": "",
            "parameters": [],
            "return_type": "Any",
        }
    ]
    function_nodes: list[dict[str, Any]] = []
    seen_line_names: set[tuple[int, str]] = set()
    used_ids = {"__module__"}
    source_lines = code.splitlines()
    total_definitions = 1

    def clean_name(value: object) -> str:
        text = str(value or "").strip()
        match = re.search(r"([A-Za-z_~][\w~]*)\s*(?:\(|$)", text)
        return match.group(1) if match else text.split(".")[-1].split("::")[-1]

    def preceding_doc(line: int) -> str:
        parts: list[str] = []
        for index in range(line - 2, max(-1, line - 6), -1):
            if index < 0 or index >= len(source_lines):
                continue
            text = source_lines[index].strip()
            if text.startswith(("//", "///", "//!")):
                parts.append(text.lstrip("/! "))
            elif not text:
                if parts:
                    break
            else:
                break
        return " ".join(reversed(parts))[:180]

    def unique_id(base: str, line: int) -> str:
        candidate = base or f"node_{line}"
        if candidate not in used_ids:
            used_ids.add(candidate)
            return candidate
        candidate = f"{candidate}@{line}"
        suffix = 2
        while candidate in used_ids:
            candidate = f"{base}@{line}_{suffix}"
            suffix += 1
        used_ids.add(candidate)
        return candidate

    def add_definition(
        raw: dict[str, Any],
        *,
        parent: str = "",
        force_kind: str | None = None,
    ) -> None:
        nonlocal total_definitions
        detail = str(raw.get("detail") or raw.get("signature") or "").strip()
        if raw.get("type") != "class" and re.match(r"^(?:return|co_return)\b", detail):
            return
        name = clean_name(raw.get("id") or raw.get("name") or raw.get("label"))
        line = int(raw.get("line") or 0)
        if not name or line <= 0 or (line, name) in seen_line_names:
            return
        seen_line_names.add((line, name))
        total_definitions += 1
        if len(nodes) >= max_nodes:
            return
        kind = force_kind or ("class" if raw.get("type") == "class" else "function")
        label = f"{parent}.{name}" if parent else name
        node = {
            "id": unique_id(label, line),
            "lookup": name,
            "label": label,
            "kind": kind,
            "line": line,
            "signature": " ".join(
                str(detail or raw.get("label") or label).split()
            )[:180],
            "doc": preceding_doc(line),
        }
        nodes.append(node)
        if kind != "class":
            function_nodes.append(node)

    for definition in parsed.get("definitions") or []:
        add_definition(definition)
        parent = clean_name(definition.get("id") or definition.get("label"))
        for method in definition.get("methods") or []:
            add_definition(method, parent=parent, force_kind="method")

    discovery_patterns = {
        "go": re.compile(
            r"(?m)^[ \t]*func\s*(?:\([^)]+\)\s*)?(?P<name>[A-Za-z_]\w*)\s*\([^)]*\)[^{\n]*\{"
        ),
        "rust": re.compile(
            r"(?m)^[ \t]*(?:pub(?:\([^)]*\))?\s+)?(?:unsafe\s+)?(?:async\s+)?"
            r"(?:extern\s+\"[^\"]+\"\s+)?fn\s+(?P<name>[A-Za-z_]\w*)\s*"
            r"(?:<[^>{}]*>)?\s*\([^)]*\)[^{;]*\{"
        ),
        "c": re.compile(
            r"(?m)^[ \t]*(?!if\b|for\b|while\b|switch\b|return\b)"
            r"(?P<signature>[A-Za-z_][\w\s*]*?\s+(?P<name>[A-Za-z_]\w*)\s*\([^;{}]*\)\s*)\{"
        ),
        "cpp": re.compile(
            r"(?m)^[ \t]*(?!if\b|for\b|while\b|switch\b|catch\b|return\b|co_return\b)"
            r"(?P<signature>[A-Za-z_~][\w\s:*&<>,~]*?\s+(?P<name>[A-Za-z_~]\w*(?:::\w+)*)"
            r"\s*\([^;{}]*\)\s*(?:const\s*)?(?:noexcept\s*)?)\{"
        ),
    }
    pattern = discovery_patterns.get(lang)
    if pattern:
        for match in pattern.finditer(code):
            line = code.count("\n", 0, match.start()) + 1
            raw_name = match.group("name")
            name = raw_name.split("::")[-1]
            signature = match.groupdict().get("signature") or match.group(0).rsplit("{", 1)[0]
            if (line, name) in seen_line_names:
                existing = next(
                    (
                        node
                        for node in function_nodes
                        if int(node.get("line") or 0) == line
                        and str(node.get("lookup") or "") == name
                    ),
                    None,
                )
                if existing and len(str(signature)) > len(str(existing.get("signature") or "")):
                    existing["signature"] = " ".join(str(signature).split())[:180]
                continue
            add_definition(
                {"id": name, "line": line, "type": "function", "detail": signature}
            )

    masked = _mask_brace_language(code)
    line_offsets = [0]
    for match in re.finditer("\n", masked):
        line_offsets.append(match.end())

    def body_range(line: int) -> tuple[int, int] | None:
        if line <= 0 or line > len(line_offsets):
            return None
        start = line_offsets[line - 1]
        opening = masked.find("{", start, min(len(masked), start + 5000))
        if opening < 0:
            return None
        semicolon = masked.find(";", start, opening)
        if semicolon >= 0:
            return None
        depth = 0
        for index in range(opening, len(masked)):
            if masked[index] == "{":
                depth += 1
            elif masked[index] == "}":
                depth -= 1
                if depth == 0:
                    return opening + 1, index
        return None

    known: dict[str, str] = {}
    for node in nodes:
        node_id = str(node["id"])
        lookup = str(node.get("lookup") or node.get("label") or node_id)
        known.setdefault(lookup, node_id)
        known.setdefault(str(node.get("label") or ""), node_id)

    call_pattern = re.compile(
        r"\b([A-Za-z_~]\w*(?:(?:::|\.|->)[A-Za-z_~]\w*)*)\s*!?\s*\("
    )
    ignored = {
        "if", "for", "while", "switch", "match", "catch", "sizeof", "alignof",
        "return", "func", "fn", "unsafe", "Some", "Ok", "Err",
    }
    edges: set[tuple[str, str]] = set()
    for node in function_nodes:
        bounds = body_range(int(node["line"]))
        if not bounds:
            continue
        body = masked[bounds[0] : bounds[1]]
        for match in call_pattern.finditer(body):
            token = match.group(1)
            short_name = re.split(r"::|\.|->", token)[-1]
            if short_name in ignored:
                continue
            target = known.get(token) or known.get(short_name)
            if target and target != node["id"]:
                edges.add((str(node["id"]), target))
                if len(edges) >= max_edges:
                    break
        if len(edges) >= max_edges:
            break

    if "main" in known:
        edges.add(("__module__", known["main"]))

    bounded_edges = [
        {"source": source, "target": target}
        for source, target in sorted(edges)
    ][:max_edges]
    node_ids = {str(node["id"]) for node in nodes}
    incoming = {node_id: 0 for node_id in node_ids}
    outgoing = {node_id: 0 for node_id in node_ids}
    call_targets: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
    for edge in bounded_edges:
        source = str(edge["source"])
        target = str(edge["target"])
        if source not in outgoing or target not in incoming:
            continue
        outgoing[source] += 1
        incoming[target] += 1
        call_targets[source].append(target)
    for node in nodes:
        node_id = str(node["id"])
        node["outgoing"] = outgoing[node_id]
        node["incoming"] = incoming[node_id]
        node["calls"] = call_targets[node_id][:12]
        if node.get("kind") == "class":
            node.setdefault("parameters", [])
            node.setdefault("return_type", str(node.get("label") or "Any"))
        elif node_id != "__module__":
            parameters, return_type = _brace_signature_details(
                str(node.get("signature") or ""),
                str(node.get("lookup") or node.get("label") or ""),
                lang,
            )
            node["parameters"] = parameters
            node["return_type"] = return_type
        node.pop("lookup", None)

    return {
        "nodes": nodes,
        "edges": bounded_edges,
        "truncated": total_definitions > len(nodes) or len(edges) >= max_edges,
        "total_definitions": total_definitions,
        "source_lines": code.count("\n") + 1,
        "language": lang,
        "error": None,
    }


def build_code_graph(path: str, code: str) -> dict[str, Any]:
    lang = language_for_path(path)
    if lang == "python":
        graph = build_python_graph(code)
        graph["language"] = "python"
        return graph
    if lang in {"go", "rust", "c", "cpp"}:
        return _build_brace_graph(path, code, lang)
    if lang == "zyenlang":
        from qt_zyenlang import build_zyenlang_graph

        return build_zyenlang_graph(code, path)
    return {
        "nodes": [],
        "edges": [],
        "error": f"{lang} 目前不支援節點呼叫圖",
        "language": lang,
    }


def format_source(path: str, code: str) -> dict[str, Any]:
    try:
        from core.formatter import format_code

        return format_code(code, language_for_path(path))
    except Exception as exc:
        return {"formatted": code, "error": str(exc), "tool": ""}


def search_in_directory(
    directory: str,
    query: str,
    *,
    case_sensitive: bool = False,
    use_regex: bool = False,
) -> dict[str, Any]:
    try:
        from core.search import search_files

        return search_files(directory, query, case_sensitive=case_sensitive, use_regex=use_regex)
    except Exception as exc:
        return {"results": [], "total": 0, "truncated": False, "error": str(exc)}
