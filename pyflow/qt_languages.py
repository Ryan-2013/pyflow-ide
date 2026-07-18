from __future__ import annotations

import ast
import builtins
import keyword
import re

from PySide6 import QtCore, QtGui


EDITOR_LANGUAGES = {"python", "rust", "go", "c", "cpp", "zyenlang"}

LANGUAGE_KEYWORDS = {
    "python": set(keyword.kwlist) | set(getattr(keyword, "softkwlist", [])),
    "go": {
        "break", "case", "chan", "const", "continue", "default", "defer",
        "else", "fallthrough", "for", "func", "go", "goto", "if", "import",
        "interface", "map", "package", "range", "return", "select", "struct",
        "switch", "type", "var",
    },
    "rust": {
        "as", "async", "await", "break", "const", "continue", "crate", "dyn",
        "else", "enum", "extern", "false", "fn", "for", "if", "impl", "in",
        "let", "loop", "match", "mod", "move", "mut", "pub", "ref", "return",
        "self", "Self", "static", "struct", "super", "trait", "true", "type",
        "unsafe", "use", "where", "while", "yield",
    },
    "c": {
        "auto", "break", "case", "char", "const", "continue", "default", "do",
        "double", "else", "enum", "extern", "float", "for", "goto", "if",
        "inline", "int", "long", "register", "restrict", "return", "short",
        "signed", "sizeof", "static", "struct", "switch", "typedef", "union",
        "unsigned", "void", "volatile", "while", "_Alignas", "_Alignof",
        "_Atomic", "_Bool", "_Complex", "_Generic", "_Noreturn", "_Static_assert",
    },
    "cpp": {
        "alignas", "alignof", "and", "and_eq", "asm", "auto", "bitand", "bitor",
        "bool", "break", "case", "catch", "char", "char8_t", "char16_t",
        "char32_t", "class", "compl", "concept", "const", "consteval",
        "constexpr", "constinit", "const_cast", "continue", "co_await", "co_return",
        "co_yield", "decltype", "default", "delete", "do", "double", "dynamic_cast",
        "else", "enum", "explicit", "export", "extern", "false", "float", "for",
        "friend", "goto", "if", "inline", "int", "long", "mutable", "namespace",
        "new", "noexcept", "not", "not_eq", "nullptr", "operator", "or", "or_eq",
        "private", "protected", "public", "register", "reinterpret_cast", "requires",
        "return", "short", "signed", "sizeof", "static", "static_assert",
        "static_cast", "struct", "switch", "template", "this", "thread_local",
        "throw", "true", "try", "typedef", "typeid", "typename", "union",
        "unsigned", "using", "virtual", "void", "volatile", "wchar_t", "while",
        "xor", "xor_eq",
    },
    "zyenlang": {
        "import", "as", "struct", "fn", "let", "const", "set", "if",
        "else", "for", "return", "break", "continue", "pass", "stop",
        "this", "true", "false", "None",
    },
}

LANGUAGE_TYPES = {
    "python": {
        "bool", "bytes", "dict", "float", "frozenset", "int", "list", "object",
        "set", "str", "tuple", "type", "None",
    },
    "go": {
        "any", "bool", "byte", "complex64", "complex128", "error", "float32",
        "float64", "int", "int8", "int16", "int32", "int64", "rune", "string",
        "uint", "uint8", "uint16", "uint32", "uint64", "uintptr",
    },
    "rust": {
        "bool", "char", "f32", "f64", "i8", "i16", "i32", "i64", "i128",
        "isize", "str", "String", "u8", "u16", "u32", "u64", "u128", "usize",
        "Box", "Option", "Result", "Vec", "HashMap", "HashSet", "Rc", "Arc",
    },
    "c": {
        "bool", "char", "double", "float", "int", "int8_t", "int16_t", "int32_t",
        "int64_t", "size_t", "uint8_t", "uint16_t", "uint32_t", "uint64_t", "void",
    },
    "cpp": {
        "bool", "char", "double", "float", "int", "long", "short", "size_t",
        "string", "vector", "map", "unordered_map", "set", "optional", "variant",
        "unique_ptr", "shared_ptr", "weak_ptr", "void",
    },
    "zyenlang": {"int", "float", "bool", "str", "List", "void", "ptr"},
}

LANGUAGE_BUILTINS = {
    "python": set(dir(builtins)) | {
        "append", "clear", "copy", "count", "decode", "encode", "endswith",
        "extend", "find", "format", "get", "index", "insert", "items", "join",
        "keys", "lower", "pop", "remove", "replace", "reverse", "sort", "split",
        "startswith", "strip", "update", "upper", "values",
    },
    "go": {
        "append", "cap", "clear", "close", "complex", "copy", "delete", "imag",
        "len", "make", "max", "min", "new", "panic", "print", "println", "real",
        "recover", "Errorf", "Printf", "Println", "Sprintf",
    },
    "rust": {
        "assert!", "dbg!", "eprintln!", "format!", "panic!", "print!", "println!",
        "todo!", "unimplemented!", "vec!", "clone", "collect", "enumerate", "filter",
        "iter", "iter_mut", "map", "new", "push", "unwrap", "unwrap_or",
    },
    "c": {
        "calloc", "fclose", "fopen", "fprintf", "free", "malloc", "memcpy",
        "memset", "printf", "puts", "realloc", "scanf", "snprintf", "strcmp",
        "strcpy", "strlen",
    },
    "cpp": {
        "begin", "cout", "cerr", "cin", "emplace_back", "end", "endl", "make_shared",
        "make_unique", "move", "pop_back", "push_back", "size", "sort", "swap",
    },
    "zyenlang": {"print"},
}

CALL_COMPLETIONS = {
    "python": {
        "abs", "all", "any", "bool", "dict", "enumerate", "filter", "float",
        "format", "getattr", "hasattr", "help", "input", "int", "isinstance",
        "len", "list", "map", "max", "min", "next", "open", "print", "range",
        "repr", "reversed", "round", "set", "sorted", "str", "sum", "super",
        "tuple", "type", "zip",
    },
    "go": {
        "append", "cap", "clear", "close", "copy", "delete", "len", "make", "new",
        "panic", "print", "println", "recover", "Errorf", "Printf", "Println", "Sprintf",
    },
    "rust": {
        "assert!", "dbg!", "eprintln!", "format!", "panic!", "print!", "println!",
        "todo!", "unimplemented!", "vec!", "collect", "filter", "map", "new", "push",
        "unwrap", "unwrap_or",
    },
    "c": {
        "calloc", "fclose", "fopen", "fprintf", "free", "malloc", "memcpy", "memset",
        "printf", "puts", "realloc", "scanf", "snprintf", "strcmp", "strcpy", "strlen",
    },
    "cpp": {
        "begin", "emplace_back", "end", "make_shared", "make_unique", "move",
        "pop_back", "push_back", "size", "sort", "swap",
    },
    "zyenlang": {"print"},
}


def completion_words(language: str, code: str = "") -> list[str]:
    if language not in EDITOR_LANGUAGES:
        return []
    words = (
        set(LANGUAGE_KEYWORDS.get(language, set()))
        | set(LANGUAGE_TYPES.get(language, set()))
        | set(LANGUAGE_BUILTINS.get(language, set()))
    )
    if code and len(code) <= 600_000:
        words.update(re.findall(r"\b[A-Za-z_][A-Za-z0-9_]{1,79}\b", code))
        if language == "rust":
            words.update(re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*!", code))
    return sorted(words)


def call_completions(language: str) -> set[str]:
    return CALL_COMPLETIONS.get(language, set())


def document_callables(language: str, code: str) -> set[str]:
    patterns = {
        "python": [
            r"(?m)^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)",
            r"(?m)^\s*class\s+([A-Za-z_]\w*)",
        ],
        "go": [r"(?m)^\s*func\s*(?:\([^)]*\)\s*)?([A-Za-z_]\w*)"],
        "rust": [
            r"(?m)^\s*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?fn\s+([A-Za-z_]\w*)",
            r"(?m)^\s*(?:pub\s+)?(?:struct|enum)\s+([A-Za-z_]\w*)",
        ],
        "c": [
            r"(?m)^\s*(?!if\b|for\b|while\b|switch\b|return\b)"
            r"[A-Za-z_]\w[\w\s*]*?\s+([A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{"
        ],
        "cpp": [
            r"(?m)^\s*(?!if\b|for\b|while\b|switch\b|return\b)"
            r"[A-Za-z_~]\w[\w\s:*&<>,~]*?\s+([A-Za-z_~]\w*)\s*\([^;{}]*\)"
            r"\s*(?:const\s*)?(?:noexcept\s*)?\{"
        ],
        "zyenlang": [
            r"(?m)^\s*fn\s+([A-Za-z_]\w*)\s*\(",
        ],
    }
    found: set[str] = set()
    if len(code) > 600_000:
        return found
    for pattern in patterns.get(language, []):
        found.update(re.findall(pattern, code))
    return found


def _python_parameters_text(raw_parameters: str) -> str:
    parts: list[str] = []
    depth = 0
    start = 0
    raw_items: list[str] = []
    for index, char in enumerate(raw_parameters):
        if char in "([{":
            depth += 1
        elif char in ")]}" and depth:
            depth -= 1
        elif char == "," and depth == 0:
            raw_items.append(raw_parameters[start:index].strip())
            start = index + 1
    tail = raw_parameters[start:].strip()
    if tail:
        raw_items.append(tail)

    for raw_item in raw_items:
        item = raw_item.strip()
        if not item or item in {"/", "*", "self", "cls"}:
            continue
        default = ""
        if "=" in item:
            item, default = item.split("=", 1)
            item, default = item.strip(), default.strip()
        if ":" in item:
            name, parameter_type = item.split(":", 1)
            name, parameter_type = name.strip(), parameter_type.strip() or "Any"
        else:
            name, parameter_type = item, "Any"
        rendered = f"{name}: {parameter_type}"
        if default:
            rendered += f" = {default}"
        parts.append(rendered)
    return ", ".join(parts)


def _matching_delimiter(text: str, opening: int, left: str, right: str) -> int:
    depth = 0
    quote = ""
    escaped = False
    for index in range(opening, len(text)):
        char = text[index]
        if escaped:
            escaped = False
            continue
        if quote and char == "\\":
            escaped = True
            continue
        if char in {'"', "'"}:
            quote = "" if quote == char else (char if not quote else quote)
            continue
        if quote:
            continue
        if char == left:
            depth += 1
        elif char == right:
            depth -= 1
            if depth == 0:
                return index
    return -1


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
        elif char in {'"', "'"}:
            quote = "" if quote == char else (char if not quote else quote)
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


def _zyenlang_completion_details(code: str) -> dict[str, str]:
    details: dict[str, str] = {}
    function_pattern = re.compile(r"(?m)^\s*fn\s+(?P<name>[A-Za-z_]\w*)\s*\(")
    for match in function_pattern.finditer(code):
        name = match.group("name")
        opening = code.find("(", match.start())
        closing = _matching_delimiter(code, opening, "(", ")")
        if closing < 0:
            continue
        rendered_parameters: list[str] = []
        for raw_parameter in _top_level_split(code[opening + 1 : closing], ","):
            if not raw_parameter:
                continue
            name_and_rest = _top_level_split(raw_parameter, ":")
            parameter_name = name_and_rest[0].strip()
            remainder = (
                ":".join(name_and_rest[1:]).strip()
                if len(name_and_rest) > 1
                else ""
            )
            type_and_default = _top_level_split(remainder, "=")
            parameter_type = type_and_default[0].strip() or "Any"
            rendered = f"{parameter_name}: {parameter_type}"
            if len(type_and_default) > 1:
                rendered += " = " + "=".join(type_and_default[1:]).strip()
            rendered_parameters.append(rendered)
        tail = code[closing + 1 :]
        return_match = re.match(r"\s*->\s*", tail)
        return_type = "void"
        if return_match:
            type_start = return_match.end()
            terminator = len(tail)
            for marker in ("{", ";"):
                marker_index = tail.find(marker, type_start)
                if marker_index >= 0:
                    terminator = min(terminator, marker_index)
            return_type = " ".join(tail[type_start:terminator].split()) or "void"
        details[name] = (
            f"{name}({', '.join(rendered_parameters)}) -> {return_type}"
        )

    for match in re.finditer(r"(?m)^\s*struct\s+([A-Za-z_]\w*)\s*\{", code):
        details[match.group(1)] = f"struct {match.group(1)}"
    for match in re.finditer(
        r"(?m)^\s*(?:let|const)\s+\*?([A-Za-z_]\w*)"
        r"\s*(?::\s*([^=;]+))?",
        code,
    ):
        details.setdefault(
            match.group(1),
            f"{match.group(1)}: {(match.group(2) or 'Any').strip()}",
        )
    return details


def completion_details(language: str, code: str) -> dict[str, str]:
    details: dict[str, str] = {}
    for word in LANGUAGE_KEYWORDS.get(language, set()):
        details[word] = "keyword"
    for word in LANGUAGE_TYPES.get(language, set()):
        details[word] = "type"
    calls = call_completions(language)
    for word in LANGUAGE_BUILTINS.get(language, set()):
        details[word] = f"{word}(...) -> Any" if word in calls else "Any"

    for name in document_callables(language, code):
        details[name] = f"{name}(...) -> Any"

    if language == "python" and len(code) <= 600_000:
        function_pattern = re.compile(
            r"(?m)^\s*(?P<async>async\s+)?def\s+(?P<name>[A-Za-z_]\w*)"
            r"\s*\((?P<params>[^)]*)\)\s*(?:->\s*(?P<return>[^:]+))?:"
        )
        for match in function_pattern.finditer(code):
            name = match.group("name")
            parameters = _python_parameters_text(match.group("params"))
            return_type = (match.group("return") or "Any").strip()
            prefix = "async " if match.group("async") else ""
            details[name] = f"{prefix}{name}({parameters}) -> {return_type}"

        for match in re.finditer(
            r"(?m)^\s*class\s+([A-Za-z_]\w*)\s*(?:\([^)]*\))?\s*:", code
        ):
            name = match.group(1)
            details[name] = f"class {name}"

        for match in re.finditer(
            r"(?m)^\s*([A-Za-z_]\w*)\s*(?::\s*([^=\n]+))?\s*=", code
        ):
            name = match.group(1)
            variable_type = (match.group(2) or "Any").strip()
            details.setdefault(name, f"{name}: {variable_type}")
    elif language == "zyenlang":
        if len(code) <= 600_000:
            details.update(_zyenlang_completion_details(code))
        details["print"] = "print(value: str) -> void"
    return details


def context_completion_details(
    language: str,
    code: str,
    cursor_position: int,
) -> dict[str, str]:
    position = max(0, min(len(code), cursor_position))
    if language == "python":
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return {}
        line = code.count("\n", 0, position) + 1
        candidates = [
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.lineno <= line <= int(getattr(node, "end_lineno", node.lineno))
        ]
        if not candidates:
            return {}
        function = min(
            candidates,
            key=lambda node: int(getattr(node, "end_lineno", node.lineno)) - node.lineno,
        )
        details: dict[str, str] = {}
        arguments = list(function.args.posonlyargs) + list(function.args.args)
        arguments += list(function.args.kwonlyargs)
        if function.args.vararg:
            arguments.append(function.args.vararg)
        if function.args.kwarg:
            arguments.append(function.args.kwarg)
        for argument in arguments:
            try:
                argument_type = ast.unparse(argument.annotation) if argument.annotation else "Any"
            except Exception:
                argument_type = "Any"
            details[argument.arg] = f"{argument.arg}: {argument_type}  |  parameter"
        return details

    if language != "zyenlang":
        return {}
    try:
        from qt_zyenlang import scan_zyenlang

        scan = scan_zyenlang(code)
    except Exception:
        return {}
    candidates = [
        function
        for function in scan["functions"]
        if function.has_body
        and function.body_opening < position <= function.body_closing
    ]
    if not candidates:
        return {}
    current = min(
        candidates,
        key=lambda function: function.body_closing - function.body_opening,
    )
    details: dict[str, str] = {}
    scope = current
    scope_limit = position
    while scope is not None:
        for parameter in scope.parameters:
            name = str(parameter.get("name") or "")
            if name:
                details.setdefault(
                    name,
                    f"{name}: {parameter.get('type') or 'Any'}  |  parameter",
                )
        local_source = code[scope.body_opening + 1 : min(scope.body_closing, scope_limit)]
        for match in re.finditer(
            r"\b(?:let|const)\s+\*?([A-Za-z_]\w*)"
            r"\s*(?::\s*([^=;]+))?",
            local_source,
        ):
            name = match.group(1)
            local_type = " ".join((match.group(2) or "Any").split())
            details.setdefault(name, f"{name}: {local_type}  |  local")
        scope_limit = scope.start
        scope = scope.parent

    if current.owner_struct is not None:
        details.setdefault("this", f"this: {current.owner_struct.name}")
        for field in current.owner_struct.fields:
            name = str(field.get("name") or "")
            if name:
                details.setdefault(
                    name,
                    f"{name}: {field.get('type') or 'Any'}  |  field",
                )
        for function in scan["selected_functions"]:
            if function.owner_struct is current.owner_struct and function.parent is None:
                details.setdefault(
                    function.name,
                    f"{function.signature}  |  method",
                )
    return details


class LanguageHighlighter(QtGui.QSyntaxHighlighter):
    def __init__(self, document: QtGui.QTextDocument) -> None:
        super().__init__(document)
        self.language = "text"

        self.keyword_format = QtGui.QTextCharFormat()
        self.keyword_format.setForeground(QtGui.QColor("#d99172"))
        self.keyword_format.setFontWeight(QtGui.QFont.Weight.Bold)

        self.type_format = QtGui.QTextCharFormat()
        self.type_format.setForeground(QtGui.QColor("#7fa8c9"))

        self.function_format = QtGui.QTextCharFormat()
        self.function_format.setForeground(QtGui.QColor("#e1bc7a"))

        self.string_format = QtGui.QTextCharFormat()
        self.string_format.setForeground(QtGui.QColor("#a8c57f"))

        self.number_format = QtGui.QTextCharFormat()
        self.number_format.setForeground(QtGui.QColor("#b9a0cf"))

        self.comment_format = QtGui.QTextCharFormat()
        self.comment_format.setForeground(QtGui.QColor("#77756e"))
        self.comment_format.setFontItalic(True)

        self.preprocessor_format = QtGui.QTextCharFormat()
        self.preprocessor_format.setForeground(QtGui.QColor("#c79573"))

        self.error_format = QtGui.QTextCharFormat()
        self.error_format.setForeground(QtGui.QColor("#ef8d86"))
        self.error_format.setUnderlineColor(QtGui.QColor("#ef8d86"))
        self.error_format.setUnderlineStyle(
            QtGui.QTextCharFormat.UnderlineStyle.WaveUnderline
        )

        self.keyword_pattern = QtCore.QRegularExpression("(?!)")
        self.type_pattern = QtCore.QRegularExpression("(?!)")
        self.number_pattern = QtCore.QRegularExpression(
            r"\b(?:0[xX][0-9A-Fa-f_]+|0[bB][01_]+|\d[\d_]*(?:\.\d[\d_]*)?(?:[eE][+-]?\d+)?)\b"
        )
        self.string_pattern = QtCore.QRegularExpression(
            r'''(?:[rubfRUBF]{0,2})(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')'''
        )
        self.function_pattern = QtCore.QRegularExpression("(?!)")
        self.function_capture = 0
        self.call_pattern = QtCore.QRegularExpression(
            r"\b([A-Za-z_][A-Za-z0-9_]*!?)\s*(?=\()"
        )

    def set_language(self, language: str) -> None:
        self.language = language
        self.keyword_pattern = self._word_pattern(LANGUAGE_KEYWORDS.get(language, set()))
        self.type_pattern = self._word_pattern(LANGUAGE_TYPES.get(language, set()))
        patterns = {
            "python": r"\b(?:def|class)\s+([A-Za-z_]\w*)",
            "rust": r"\b(?:fn|struct|enum|trait|impl)\s+([A-Za-z_]\w*)",
            "go": r"\b(?:func|type)\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)",
            "c": r"\b([A-Za-z_]\w*)\s*(?=\()",
            "cpp": r"\b([A-Za-z_~]\w*)\s*(?=\()",
            "zyenlang": r"\b(?:fn|struct)\s+([A-Za-z_]\w*)",
        }
        self.function_pattern = QtCore.QRegularExpression(patterns.get(language, "(?!)"))
        self.function_capture = 1
        self.rehighlight()

    @staticmethod
    def _word_pattern(words: set[str]) -> QtCore.QRegularExpression:
        identifiers = sorted(
            (word for word in words if re.match(r"^[A-Za-z_]\w*$", word)),
            key=lambda value: (-len(value), value),
        )
        if not identifiers:
            return QtCore.QRegularExpression("(?!)")
        return QtCore.QRegularExpression(
            r"\b(?:" + "|".join(re.escape(word) for word in identifiers) + r")\b"
        )

    def _apply_pattern(
        self,
        text: str,
        pattern: QtCore.QRegularExpression,
        char_format: QtGui.QTextCharFormat,
        capture: int = 0,
    ) -> None:
        matches = pattern.globalMatch(text)
        while matches.hasNext():
            match = matches.next()
            start = match.capturedStart(capture)
            length = match.capturedLength(capture)
            if start >= 0 and length > 0:
                self.setFormat(start, length, char_format)

    @staticmethod
    def _marker_outside_string(text: str, marker: str, start: int = 0) -> int:
        quote = ""
        escaped = False
        index = start
        while index <= len(text) - len(marker):
            char = text[index]
            if escaped:
                escaped = False
            elif char == "\\" and quote:
                escaped = True
            elif char in {"'", '"'}:
                quote = "" if quote == char else (char if not quote else quote)
            elif not quote and text.startswith(marker, index):
                return index
            index += 1
        return -1

    def _apply_python_triple_strings(self, text: str) -> None:
        previous = self.previousBlockState()
        if previous in {2, 3}:
            marker = "'''" if previous == 2 else '"""'
            end = text.find(marker)
            if end < 0:
                self.setFormat(0, len(text), self.string_format)
                self.setCurrentBlockState(previous)
                return
            self.setFormat(0, end + 3, self.string_format)
            search_from = end + 3
        else:
            search_from = 0

        while search_from < len(text):
            single = text.find("'''", search_from)
            double = text.find('"""', search_from)
            starts = [(value, state, marker) for value, state, marker in (
                (single, 2, "'''"), (double, 3, '"""')
            ) if value >= 0]
            if not starts:
                return
            start, state, marker = min(starts, key=lambda item: item[0])
            end = text.find(marker, start + 3)
            if end < 0:
                self.setFormat(start, len(text) - start, self.string_format)
                self.setCurrentBlockState(state)
                return
            self.setFormat(start, end + 3 - start, self.string_format)
            search_from = end + 3

    def _apply_c_style_comments(self, text: str) -> None:
        previous = self.previousBlockState()
        search_from = 0
        if previous == 1:
            end = text.find("*/")
            if end < 0:
                self.setFormat(0, len(text), self.comment_format)
                self.setCurrentBlockState(1)
                return
            self.setFormat(0, end + 2, self.comment_format)
            search_from = end + 2

        while search_from < len(text):
            start = self._marker_outside_string(text, "/*", search_from)
            if start < 0:
                break
            end = text.find("*/", start + 2)
            if end < 0:
                self.setFormat(start, len(text) - start, self.comment_format)
                self.setCurrentBlockState(1)
                return
            self.setFormat(start, end + 2 - start, self.comment_format)
            search_from = end + 2

        line_comment = self._marker_outside_string(text, "//")
        if line_comment >= 0:
            self.setFormat(line_comment, len(text) - line_comment, self.comment_format)

    def highlightBlock(self, text: str) -> None:
        self.setCurrentBlockState(0)
        if self.language not in EDITOR_LANGUAGES:
            return
        self._apply_pattern(text, self.call_pattern, self.function_format, 1)
        self._apply_pattern(text, self.keyword_pattern, self.keyword_format)
        self._apply_pattern(text, self.type_pattern, self.type_format)
        self._apply_pattern(text, self.number_pattern, self.number_format)
        self._apply_pattern(
            text,
            self.function_pattern,
            self.function_format,
            self.function_capture,
        )
        self._apply_pattern(text, self.string_pattern, self.string_format)

        if self.language == "python":
            self._apply_python_triple_strings(text)
            comment = self._marker_outside_string(text, "#")
            if comment >= 0:
                self.setFormat(comment, len(text) - comment, self.comment_format)
            decorator = QtCore.QRegularExpression(r"^\s*@\w+(?:\.\w+)*")
            self._apply_pattern(text, decorator, self.preprocessor_format)
        else:
            self._apply_c_style_comments(text)
            if self.language in {"c", "cpp"}:
                preprocessor = QtCore.QRegularExpression(r"^\s*#\s*\w+.*$")
                self._apply_pattern(text, preprocessor, self.preprocessor_format)
            elif self.language == "zyenlang":
                invalid_while = QtCore.QRegularExpression(r"\bwhile\b")
                self._apply_pattern(text, invalid_while, self.error_format)
