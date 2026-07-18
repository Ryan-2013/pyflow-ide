from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


IDENTIFIER = r"[A-Za-z_][A-Za-z0-9_]*"


@dataclass
class ZyenStruct:
    name: str
    start: int
    opening: int
    closing: int
    line: int
    fields: list[dict[str, str]] = field(default_factory=list)
    doc: str = ""


@dataclass
class ZyenFunction:
    name: str
    start: int
    end: int
    line: int
    signature: str
    parameters: list[dict[str, str]]
    return_type: str
    body_opening: int = -1
    body_closing: int = -1
    parent: "ZyenFunction | None" = None
    owner_struct: ZyenStruct | None = None
    qualified_name: str = ""
    doc: str = ""

    @property
    def has_body(self) -> bool:
        return self.body_opening >= 0 and self.body_closing > self.body_opening


def _mask_source(code: str) -> str:
    chars = list(code)
    index = 0
    state = "code"
    escaped = False
    while index < len(chars):
        char = chars[index]
        following = chars[index + 1] if index + 1 < len(chars) else ""
        if state == "code":
            if char == "/" and following == "/":
                chars[index] = chars[index + 1] = " "
                index += 2
                state = "comment"
                continue
            if char == '"':
                chars[index] = " "
                state = "string"
                escaped = False
        elif state == "comment":
            if char == "\n":
                state = "code"
            else:
                chars[index] = " "
        elif state == "string":
            if escaped:
                escaped = False
                if char != "\n":
                    chars[index] = " "
            elif char == "\\":
                escaped = True
                chars[index] = " "
            elif char == '"':
                chars[index] = " "
                state = "code"
            elif char != "\n":
                chars[index] = " "
        index += 1
    return "".join(chars)


def _matching_delimiter(text: str, opening: int, left: str, right: str) -> int:
    depth = 0
    for index in range(opening, len(text)):
        char = text[index]
        if char == left:
            depth += 1
        elif char == right:
            depth -= 1
            if depth == 0:
                return index
    return -1


def _line_number(code: str, offset: int) -> int:
    return code.count("\n", 0, max(0, offset)) + 1


def _compact(text: str, limit: int = 220) -> str:
    value = " ".join(text.strip().split())
    return value if len(value) <= limit else value[: limit - 3] + "..."


def _top_level_split(text: str, delimiter: str) -> list[str]:
    parts: list[str] = []
    start = 0
    depths = {"(": 0, "[": 0, "{": 0, "<": 0}
    closing = {")": "(", "]": "[", "}": "{", ">": "<"}
    quote = ""
    escaped = False
    index = 0
    while index < len(text):
        char = text[index]
        if escaped:
            escaped = False
        elif quote and char == "\\":
            escaped = True
        elif char == '"':
            quote = "" if quote else '"'
        elif not quote:
            if char in depths:
                depths[char] += 1
            elif (
                char in closing
                and not (char == ">" and index > 0 and text[index - 1] == "-")
                and depths[closing[char]]
            ):
                depths[closing[char]] -= 1
            elif text.startswith(delimiter, index) and not any(depths.values()):
                parts.append(text[start:index].strip())
                start = index + len(delimiter)
                index += len(delimiter) - 1
        index += 1
    parts.append(text[start:].strip())
    return parts


def _parse_parameters(text: str) -> list[dict[str, str]]:
    parameters: list[dict[str, str]] = []
    for raw_parameter in _top_level_split(text, ","):
        if not raw_parameter:
            continue
        name_and_type = _top_level_split(raw_parameter, ":")
        name = name_and_type[0].strip()
        remainder = (
            ":".join(name_and_type[1:]).strip()
            if len(name_and_type) > 1
            else ""
        )
        type_and_default = _top_level_split(remainder, "=")
        parameter_type = type_and_default[0].strip() or "Any"
        default = (
            "=".join(type_and_default[1:]).strip()
            if len(type_and_default) > 1
            else ""
        )
        parameters.append(
            {"name": name or "Any", "type": parameter_type, "default": default}
        )
    return parameters


def _preceding_doc(code: str, line: int) -> str:
    lines = code.splitlines()
    parts: list[str] = []
    for index in range(line - 2, max(-1, line - 7), -1):
        if index < 0 or index >= len(lines):
            continue
        value = lines[index].strip()
        if value.startswith("//"):
            parts.append(value[2:].strip())
        elif not value:
            if parts:
                break
        else:
            break
    return _compact(" ".join(reversed(parts)), 180)


def _brace_depths(masked: str) -> list[int]:
    depths = [0] * (len(masked) + 1)
    depth = 0
    for index, char in enumerate(masked):
        depths[index] = depth
        if char == "{":
            depth += 1
        elif char == "}" and depth:
            depth -= 1
    depths[len(masked)] = depth
    return depths


def _statement_end(masked: str, start: int, limit: int) -> int:
    depths = {"(": 0, "[": 0, "{": 0, "<": 0}
    closing = {")": "(", "]": "[", "}": "{", ">": "<"}
    for index in range(start, min(limit, len(masked))):
        char = masked[index]
        if char in depths:
            depths[char] += 1
        elif (
            char in closing
            and not (char == ">" and index > 0 and masked[index - 1] == "-")
            and depths[closing[char]]
        ):
            depths[closing[char]] -= 1
        elif char == ";" and not any(depths.values()):
            return index
    return -1


def _scan_structs(code: str, masked: str) -> list[ZyenStruct]:
    structs: list[ZyenStruct] = []
    pattern = re.compile(rf"\bstruct\s+(?P<name>{IDENTIFIER})\s*\{{")
    for match in pattern.finditer(masked):
        opening = masked.find("{", match.start(), match.end())
        closing = _matching_delimiter(masked, opening, "{", "}")
        if opening < 0 or closing < 0:
            continue
        line = _line_number(code, match.start())
        structs.append(
            ZyenStruct(
                name=match.group("name"),
                start=match.start(),
                opening=opening,
                closing=closing,
                line=line,
                doc=_preceding_doc(code, line),
            )
        )

    depths = _brace_depths(masked)
    field_pattern = re.compile(
        rf"\blet\s+this\.(?P<name>{IDENTIFIER})\s*:"
    )
    for struct in structs:
        direct_depth = depths[struct.opening] + 1
        for match in field_pattern.finditer(masked, struct.opening + 1, struct.closing):
            if depths[match.start()] != direct_depth:
                continue
            end = _statement_end(masked, match.end(), struct.closing)
            if end < 0:
                continue
            raw = code[match.end() : end].strip()
            type_and_default = _top_level_split(raw, "=")
            struct.fields.append(
                {
                    "name": match.group("name"),
                    "type": type_and_default[0].strip() or "Any",
                    "default": (
                        "=".join(type_and_default[1:]).strip()
                        if len(type_and_default) > 1
                        else ""
                    ),
                }
            )
    return structs


def _signature_terminator(masked: str, start: int) -> int:
    depths = {"(": 0, "[": 0, "<": 0}
    closing = {")": "(", "]": "[", ">": "<"}
    for index in range(start, len(masked)):
        char = masked[index]
        if char in depths:
            depths[char] += 1
        elif (
            char in closing
            and not (char == ">" and index > 0 and masked[index - 1] == "-")
            and depths[closing[char]]
        ):
            depths[closing[char]] -= 1
        elif char in {"{", ";"} and not any(depths.values()):
            return index
    return -1


def _scan_functions(
    code: str,
    masked: str,
    structs: list[ZyenStruct],
) -> list[ZyenFunction]:
    functions: list[ZyenFunction] = []
    pattern = re.compile(rf"\bfn\s+(?P<name>{IDENTIFIER})\s*\(")
    for match in pattern.finditer(masked):
        opening = masked.find("(", match.start(), match.end())
        closing = _matching_delimiter(masked, opening, "(", ")")
        if opening < 0 or closing < 0:
            continue
        terminator = _signature_terminator(masked, closing + 1)
        if terminator < 0:
            continue
        tail = masked[closing + 1 : terminator]
        return_match = re.match(r"\s*->\s*", tail)
        return_type = "void"
        if return_match:
            raw_return_start = closing + 1 + return_match.end()
            return_type = _compact(code[raw_return_start:terminator]) or "void"
        body_opening = terminator if masked[terminator] == "{" else -1
        body_closing = (
            _matching_delimiter(masked, body_opening, "{", "}")
            if body_opening >= 0
            else -1
        )
        if body_opening >= 0 and body_closing < 0:
            continue
        end = body_closing + 1 if body_closing >= 0 else terminator + 1
        line = _line_number(code, match.start())
        functions.append(
            ZyenFunction(
                name=match.group("name"),
                start=match.start(),
                end=end,
                line=line,
                signature=_compact(code[match.start() : terminator]),
                parameters=_parse_parameters(code[opening + 1 : closing]),
                return_type=return_type,
                body_opening=body_opening,
                body_closing=body_closing,
                doc=_preceding_doc(code, line),
            )
        )

    for function in functions:
        parents = [
            candidate
            for candidate in functions
            if candidate is not function
            and candidate.has_body
            and candidate.body_opening < function.start < candidate.body_closing
        ]
        if parents:
            function.parent = min(
                parents, key=lambda item: item.body_closing - item.body_opening
            )
            continue
        owners = [
            struct
            for struct in structs
            if struct.opening < function.start < struct.closing
        ]
        if owners:
            function.owner_struct = min(
                owners, key=lambda item: item.closing - item.opening
            )

    def inherited_struct(function: ZyenFunction) -> ZyenStruct | None:
        if function.owner_struct is not None:
            return function.owner_struct
        if function.parent is not None:
            function.owner_struct = inherited_struct(function.parent)
        return function.owner_struct

    for function in functions:
        inherited_struct(function)

    def qualify(function: ZyenFunction) -> str:
        if function.qualified_name:
            return function.qualified_name
        if function.parent:
            function.qualified_name = f"{qualify(function.parent)}.{function.name}"
        elif function.owner_struct:
            function.qualified_name = f"{function.owner_struct.name}.{function.name}"
        else:
            function.qualified_name = function.name
        return function.qualified_name

    for function in functions:
        qualify(function)
    return functions


def _selected_functions(functions: list[ZyenFunction]) -> list[ZyenFunction]:
    selected: dict[str, ZyenFunction] = {}
    for function in functions:
        previous = selected.get(function.qualified_name)
        if previous is None or (function.has_body and not previous.has_body):
            selected[function.qualified_name] = function
    return sorted(selected.values(), key=lambda item: item.start)


def scan_zyenlang(code: str) -> dict[str, Any]:
    masked = _mask_source(code)
    structs = _scan_structs(code, masked)
    functions = _scan_functions(code, masked, structs)
    imports: list[dict[str, Any]] = []
    import_pattern = re.compile(
        rf"(?m)^\s*import\s+(?P<path><std/{IDENTIFIER}>|\"(?:\\.|[^\"\\])*\")"
        rf"(?:\s+as\s+(?P<alias>{IDENTIFIER}))?\s*;"
    )
    for match in import_pattern.finditer(code):
        path = match.group("path")
        alias = match.group("alias") or ""
        imports.append(
            {
                "path": path,
                "alias": alias,
                "line": _line_number(code, match.start()),
                "label": f"import {path}" + (f" as {alias}" if alias else ""),
            }
        )
    return {
        "masked": masked,
        "structs": structs,
        "functions": functions,
        "selected_functions": _selected_functions(functions),
        "imports": imports,
    }


def parse_zyenlang_source(code: str, path: str = "") -> dict[str, Any]:
    scan = scan_zyenlang(code)
    selected = scan["selected_functions"]
    definitions: list[dict[str, Any]] = []
    for imported in scan["imports"]:
        definitions.append(
            {
                "id": imported["label"],
                "label": imported["label"],
                "line": imported["line"],
                "type": "import",
                "detail": imported["label"],
                "methods": [],
            }
        )
    for struct in scan["structs"]:
        methods = [
            {
                "id": function.name,
                "name": function.name,
                "label": (
                    function.signature
                    if function.parent is None
                    else f"closure {function.qualified_name}"
                ),
                "line": function.line,
                "type": "method" if function.parent is None else "function",
                "detail": function.signature,
            }
            for function in selected
            if function.owner_struct is struct
        ]
        definitions.append(
            {
                "id": struct.name,
                "label": f"struct {struct.name}",
                "line": struct.line,
                "type": "class",
                "detail": f"struct {struct.name}",
                "fields": struct.fields,
                "methods": methods,
            }
        )
    for function in selected:
        if function.owner_struct is not None or function.parent is not None:
            continue
        def belongs_to(candidate: ZyenFunction) -> bool:
            parent = candidate.parent
            while parent is not None and parent is not function:
                parent = parent.parent
            return parent is function

        closures = [
            {
                "id": child.name,
                "name": child.name,
                "label": f"closure {child.qualified_name}",
                "line": child.line,
                "type": "function",
                "detail": child.signature,
            }
            for child in selected
            if belongs_to(child)
        ]
        definitions.append(
            {
                "id": function.name,
                "label": function.signature,
                "line": function.line,
                "type": "function",
                "detail": function.signature,
                "methods": closures,
            }
        )
    symbols = [
        {
            "name": definition["id"],
            "kind": definition["type"],
            "line": definition["line"],
        }
        for definition in definitions
    ]
    return {
        "flow": [],
        "definitions": sorted(definitions, key=lambda item: int(item["line"])),
        "symbols": symbols,
        "lang": "zyenlang",
        "path": path,
        "error": None,
    }


def _variable_struct_types(body: str, struct_names: set[str]) -> dict[str, str]:
    types: dict[str, str] = {}
    typed_pattern = re.compile(
        rf"\blet\s+\*?(?P<name>{IDENTIFIER})\s*:\s*(?P<type>{IDENTIFIER})\b"
    )
    for match in typed_pattern.finditer(body):
        if match.group("type") in struct_names:
            types[match.group("name")] = match.group("type")
    inferred_pattern = re.compile(
        rf"\blet\s+(?P<name>{IDENTIFIER})\s*=\s*(?P<type>{IDENTIFIER})\s*(?:\{{|;)"
    )
    for match in inferred_pattern.finditer(body):
        if match.group("type") in struct_names:
            types[match.group("name")] = match.group("type")
    return types


def build_zyenlang_graph(code: str, path: str = "") -> dict[str, Any]:
    max_nodes = 120
    max_edges = 320
    scan = scan_zyenlang(code)
    structs: list[ZyenStruct] = scan["structs"]
    functions: list[ZyenFunction] = scan["selected_functions"]
    masked: str = scan["masked"]

    nodes: list[dict[str, Any]] = [
        {
            "id": "__module__",
            "label": "Program entry",
            "kind": "module",
            "line": 1,
            "signature": "ZyenLang top-level code",
            "doc": "",
            "parameters": [],
            "return_type": "Any",
        }
    ]
    for struct in structs:
        if len(nodes) >= max_nodes:
            break
        field_summary = ", ".join(
            f"{item['name']}: {item['type']}" for item in struct.fields
        )
        nodes.append(
            {
                "id": struct.name,
                "label": struct.name,
                "kind": "class",
                "line": struct.line,
                "signature": _compact(
                    f"struct {struct.name}"
                    + (f" {{ {field_summary} }}" if field_summary else "")
                ),
                "doc": struct.doc,
                "parameters": struct.fields,
                "return_type": struct.name,
            }
        )
    function_by_id: dict[str, ZyenFunction] = {}
    for function in functions:
        if len(nodes) >= max_nodes:
            break
        function_by_id[function.qualified_name] = function
        nodes.append(
            {
                "id": function.qualified_name,
                "label": function.qualified_name,
                "kind": (
                    "method"
                    if function.owner_struct is not None and function.parent is None
                    else "function"
                ),
                "line": function.line,
                "signature": function.signature,
                "doc": function.doc,
                "parameters": function.parameters,
                "return_type": function.return_type,
            }
        )

    node_ids = {str(node["id"]) for node in nodes}
    exact = {name: name for name in function_by_id if name in node_ids}
    by_short: dict[str, list[str]] = {}
    for name in exact:
        by_short.setdefault(name.split(".")[-1], []).append(name)
    struct_names = {struct.name for struct in structs}

    def resolve_call(
        token: str,
        function: ZyenFunction,
        variable_types: dict[str, str],
    ) -> str | None:
        parts = token.split(".")
        if token in exact:
            return exact[token]
        if (
            len(parts) == 2
            and parts[0] == "this"
            and function.owner_struct is not None
        ):
            return exact.get(f"{function.owner_struct.name}.{parts[1]}")
        if len(parts) == 2 and parts[0] in variable_types:
            return exact.get(f"{variable_types[parts[0]]}.{parts[1]}")
        short = parts[-1]
        owner = function.qualified_name.rsplit(".", 1)[0]
        while owner:
            candidate = f"{owner}.{short}"
            if candidate in exact:
                return candidate
            owner = owner.rsplit(".", 1)[0] if "." in owner else ""
        candidates = by_short.get(short, [])
        return candidates[0] if len(candidates) == 1 else None

    ignored_calls = {
        "if", "for", "while", "fn", "print", "ptr", "List", "int",
        "float", "bool", "str", "void",
    }
    call_pattern = re.compile(
        rf"\b(?P<name>{IDENTIFIER}(?:\.{IDENTIFIER})*)\s*\("
    )
    edges: set[tuple[str, str]] = set()
    for function_id, function in function_by_id.items():
        if not function.has_body:
            continue
        body_start = function.body_opening + 1
        body_end = function.body_closing
        body_chars = list(masked[body_start:body_end])
        for child in scan["functions"]:
            if child is function or not (body_start <= child.start < body_end):
                continue
            relative_start = max(0, child.start - body_start)
            relative_end = min(len(body_chars), child.end - body_start)
            for index in range(relative_start, relative_end):
                if body_chars[index] != "\n":
                    body_chars[index] = " "
        body = "".join(body_chars)
        raw_body = code[body_start:body_end]
        variable_types = _variable_struct_types(raw_body, struct_names)
        for parameter in function.parameters:
            parameter_type = str(parameter.get("type") or "")
            if parameter_type in struct_names:
                variable_types[str(parameter.get("name") or "")] = parameter_type
        for match in call_pattern.finditer(body):
            token = match.group("name")
            if token.split(".")[-1] in ignored_calls:
                continue
            target = resolve_call(token, function, variable_types)
            if target and target != function_id and target in node_ids:
                edges.add((function_id, target))
                if len(edges) >= max_edges:
                    break
        if len(edges) >= max_edges:
            break

    if "main" in exact:
        edges.add(("__module__", "main"))
    bounded_edges = [
        {"source": source, "target": target}
        for source, target in sorted(edges)
    ][:max_edges]
    incoming = {node_id: 0 for node_id in node_ids}
    outgoing = {node_id: 0 for node_id in node_ids}
    calls: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
    for edge in bounded_edges:
        source = str(edge["source"])
        target = str(edge["target"])
        outgoing[source] += 1
        incoming[target] += 1
        calls[source].append(target)
    for node in nodes:
        node_id = str(node["id"])
        node["outgoing"] = outgoing[node_id]
        node["incoming"] = incoming[node_id]
        node["calls"] = calls[node_id][:12]

    total_definitions = 1 + len(structs) + len(functions)
    return {
        "nodes": nodes,
        "edges": bounded_edges,
        "truncated": total_definitions > len(nodes) or len(edges) >= max_edges,
        "total_definitions": total_definitions,
        "source_lines": code.count("\n") + 1,
        "language": "zyenlang",
        "path": path,
        "error": None,
    }
