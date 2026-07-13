"""
PyFlow Language Plugin — C Language
=====================================
Parser: tree-sitter-c (if installed) → regex fallback
Format: clang-format
LSP:    clangd
Tests:  make test / ctest
"""
from __future__ import annotations
import os, re, shutil, subprocess
from plugins import LanguagePlugin, register


# ── Helper: try importing tree-sitter-c ───────────────────────────
def _try_ts_c():
    try:
        import tree_sitter_c as tsc
        from tree_sitter import Language, Parser as TSP
        return Language(tsc.language()), TSP
    except ImportError:
        return None, None

TS_LANG, TS_PARSER_CLS = _try_ts_c()


# ── Node type colors for C ────────────────────────────────────────
_C_COLORS = {
    "include":     {"n": "#include",   "c": "#1e3a5f"},
    "typedef":     {"n": "typedef",    "c": "#2a1e3a"},
    "macro":       {"n": "Macro",      "c": "#3a2a0a"},
    "struct_use":  {"n": "struct",     "c": "#1a2a3a"},
    "pointer_op":  {"n": "Pointer",    "c": "#3a0a0a"},
    "malloc":      {"n": "malloc/free","c": "#2a1a0a"},
    "goto":        {"n": "goto",       "c": "#3a1a2a"},
}


# ── tree-sitter based parser ──────────────────────────────────────

def _parse_ts(code: str, path: str) -> dict:
    parser = TS_PARSER_CLS(TS_LANG)
    cb = code.encode("utf-8")
    tree = parser.parse(cb)

    flow, defs = [], []
    step = [0]

    def text(n):
        return cb[n.start_byte:n.end_byte].decode("utf-8", "replace")

    def lineno(n):
        return n.start_point[0] + 1

    # Walk top-level declarations
    for node in tree.root_node.children:
        t = node.type

        if t == "preproc_include":
            # #include "..." or <...>
            raw = text(node).strip()
            flow.append({"id": f"inc_{lineno(node)}", "type": "include",
                         "label": raw[:60], "line": lineno(node), "detail": raw, "calls": []})

        elif t == "preproc_def":
            raw = text(node).strip()
            flow.append({"id": f"macro_{lineno(node)}", "type": "macro",
                         "label": raw[:60], "line": lineno(node), "detail": raw, "calls": []})

        elif t == "declaration":
            label = text(node)[:60].strip()
            flow.append({"id": f"decl_{lineno(node)}", "type": "assign",
                         "label": label, "line": lineno(node), "detail": "", "calls": []})

        elif t == "function_definition":
            # Extract function name
            declarator = next((c for c in node.children if "declarator" in c.type), None)
            fname = _extract_c_fn_name(declarator, cb) if declarator else "?"
            step[0] += 1
            # Parse body for flow nodes
            body = next((c for c in node.children if c.type == "compound_statement"), None)
            body_flow = _parse_c_body(body, cb, step) if body else []

            defs.append({
                "id":       fname,
                "type":     "function",
                "label":    fname,
                "line":     lineno(node),
                "detail":   text(node).split("{")[0].strip()[:80],
                "methods":  [],
                "is_async": False,
            })
            # Add a call node in flow
            flow.append({"id": f"call_{fname}", "type": "call",
                         "label": fname + "()", "line": lineno(node),
                         "detail": "", "calls": [fname], "step": step[0]})

        elif t in ("struct_specifier", "union_specifier", "enum_specifier"):
            sname = ""
            for c in node.children:
                if c.type == "type_identifier":
                    sname = text(c); break
            if sname:
                defs.append({"id": sname, "type": "class", "label": sname,
                             "line": lineno(node), "detail": t.split("_")[0],
                             "methods": [], "is_async": False})

    return {"flow": flow, "definitions": defs, "error": None, "error_line": 0}


def _extract_c_fn_name(declarator_node, cb: bytes) -> str:
    """Extract function name from a declarator node."""
    if declarator_node is None:
        return "?"
    for child in declarator_node.children:
        if child.type == "identifier":
            return cb[child.start_byte:child.end_byte].decode("utf-8", "replace")
        if "declarator" in child.type:
            result = _extract_c_fn_name(child, cb)
            if result != "?":
                return result
    return "?"


def _parse_c_body(body, cb: bytes, step: list) -> list:
    """Parse function body into flow nodes."""
    nodes = []

    def text(n):
        return cb[n.start_byte:n.end_byte].decode("utf-8", "replace")

    def ln(n):
        return n.start_point[0] + 1

    for node in body.children:
        t = node.type
        if t in ("{", "}"):
            continue
        elif t == "if_statement":
            cond = next((c for c in node.children if c.type == "parenthesized_expression"), None)
            label = "if " + (text(cond)[:40] if cond else "")
            nodes.append({"id": f"if_{ln(node)}", "type": "condition",
                          "label": label, "line": ln(node), "detail": "", "calls": []})
        elif t in ("while_statement", "for_statement", "do_statement"):
            label = t.split("_")[0] + " (…)"
            nodes.append({"id": f"loop_{ln(node)}", "type": "loop",
                          "label": label, "line": ln(node), "detail": "", "calls": []})
        elif t == "return_statement":
            val = text(node).strip()[:50]
            nodes.append({"id": f"ret_{ln(node)}", "type": "flow_ctrl",
                          "label": val, "line": ln(node), "detail": "", "calls": []})
        elif t == "expression_statement":
            raw = text(node).strip()[:60]
            # Detect malloc/free/calloc/realloc
            if re.search(r'\b(malloc|calloc|realloc|free)\b', raw):
                nodes.append({"id": f"mem_{ln(node)}", "type": "malloc",
                              "label": raw, "line": ln(node), "detail": "", "calls": []})
            # Detect pointer dereference or address-of
            elif re.search(r'[*&]', raw):
                nodes.append({"id": f"ptr_{ln(node)}", "type": "pointer_op",
                              "label": raw, "line": ln(node), "detail": "", "calls": []})
            else:
                # Try to detect function call
                m = re.match(r'(\w+)\s*\(', raw)
                calls = [m.group(1)] if m else []
                nodes.append({"id": f"expr_{ln(node)}", "type": "call",
                              "label": raw, "line": ln(node), "detail": "", "calls": calls})
        elif t == "goto_statement":
            nodes.append({"id": f"goto_{ln(node)}", "type": "goto",
                          "label": text(node).strip()[:40], "line": ln(node), "detail": "", "calls": []})
        elif t == "switch_statement":
            nodes.append({"id": f"switch_{ln(node)}", "type": "match",
                          "label": "switch", "line": ln(node), "detail": "", "calls": []})

    return nodes


# ── Regex-based fallback parser ───────────────────────────────────

def _parse_regex(code: str, path: str) -> dict:
    """Simple regex parser for when tree-sitter-c is not installed."""
    flow, defs = [], []
    lines = code.split("\n")

    # Remove block comments
    clean = re.sub(r"/\*.*?\*/", "", code, flags=re.S)
    clean = re.sub(r"//[^\n]*", "", clean)

    step = 0
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            continue

        # #include
        if stripped.startswith("#include"):
            flow.append({"id": f"inc_{i}", "type": "include", "label": stripped[:60],
                         "line": i, "detail": stripped, "calls": []})
        # #define
        elif stripped.startswith("#define"):
            flow.append({"id": f"def_{i}", "type": "macro", "label": stripped[:60],
                         "line": i, "detail": stripped, "calls": []})
        # Function definition: type name(...) {
        elif re.match(r'^[\w*\s]+\s+(\w+)\s*\([^;]*\)\s*\{?\s*$', stripped):
            m = re.match(r'(?:[\w*\s]+\s+)?(\w+)\s*\(', stripped)
            fname = m.group(1) if m else "fn"
            if fname not in ("if", "while", "for", "switch", "else"):
                step += 1
                defs.append({"id": fname, "type": "function", "label": fname,
                             "line": i, "detail": stripped[:80], "methods": [], "is_async": False})
                flow.append({"id": f"call_{fname}", "type": "call", "label": fname + "()",
                             "line": i, "detail": "", "calls": [fname], "step": step})
        # if/else if
        elif re.match(r'^(else\s+)?if\s*\(', stripped):
            flow.append({"id": f"cond_{i}", "type": "condition",
                         "label": stripped[:60], "line": i, "detail": "", "calls": []})
        # for/while/do
        elif re.match(r'^(for|while|do)\s*[\({]', stripped):
            kw = re.match(r'^(\w+)', stripped).group(1)
            flow.append({"id": f"loop_{i}", "type": "loop",
                         "label": f"{kw} (…)", "line": i, "detail": "", "calls": []})
        # struct/typedef struct
        elif re.match(r'^(typedef\s+)?struct\s+(\w+)', stripped):
            m = re.match(r'(?:typedef\s+)?struct\s+(\w+)', stripped)
            sname = m.group(1) if m else "struct"
            defs.append({"id": sname, "type": "class", "label": sname,
                         "line": i, "detail": "struct", "methods": [], "is_async": False})
        # malloc/free
        elif re.search(r'\b(malloc|calloc|realloc|free)\b', stripped):
            flow.append({"id": f"mem_{i}", "type": "malloc", "label": stripped[:60],
                         "line": i, "detail": "", "calls": []})
        # return
        elif re.match(r'^return\b', stripped):
            flow.append({"id": f"ret_{i}", "type": "flow_ctrl", "label": stripped[:60],
                         "line": i, "detail": "", "calls": []})

    return {"flow": flow, "definitions": defs, "error": None, "error_line": 0}


# ── Plugin class ──────────────────────────────────────────────────

class CPlugin(LanguagePlugin):
    id          = "c"
    name        = "C"
    version     = "1.0.0"
    extensions  = [".c", ".h"]
    monaco_id   = "c"
    icon        = "🅒"
    color       = "#A8B9CC"
    description = "C — pointer/malloc visualization, clangd LSP, tree-sitter parser"

    def parse(self, code: str, path: str) -> dict:
        if TS_LANG:
            return _parse_ts(code, path)
        return _parse_regex(code, path)

    def extract_symbols(self, code: str, path: str, parse_result=None) -> list:
        r = parse_result or self.parse(code, path)
        syms = []
        for d in r.get("definitions", []):
            syms.append({
                "name":   d["id"],
                "kind":   d["type"],
                "line":   d["line"],
                "sig":    d.get("detail", ""),
                "doc":    "",
                "source": "user",
                "module": "",
                "parent": "",
            })
        return syms

    def format_code(self, code: str) -> dict:
        if not shutil.which("clang-format"):
            return {"formatted": code, "error": "clang-format 未安裝", "tool": "clang-format"}
        r = subprocess.run(["clang-format", "-style=llvm"],
                           input=code, capture_output=True, text=True, timeout=10)
        return {"formatted": r.stdout if r.returncode == 0 else code,
                "error": r.stderr.strip() or None, "tool": "clang-format"}

    def get_lsp_command(self) -> list | None:
        return ["clangd", "--background-index"] if shutil.which("clangd") else None

    def run_tests(self, path: str) -> dict | None:
        """Try: make test → ctest → return results."""
        cwd = os.path.dirname(os.path.abspath(path))
        for cmd, cwd2 in [(["make", "test"], cwd), (["ctest", "--output-on-failure"], cwd)]:
            if shutil.which(cmd[0]):
                r = subprocess.run(cmd, cwd=cwd2, capture_output=True, text=True, timeout=60)
                ok = r.returncode == 0
                return {"ok": ok, "summary": {"passed": int(ok), "failed": int(not ok),
                                              "skipped": 0, "errors": 0, "duration": 0},
                        "results": [], "output": (r.stdout + r.stderr)[-3000:], "error": None}
        return None

    def get_run_command(self, path: str) -> list | None:
        return None   # C needs compilation first

    def get_node_types(self) -> dict:
        return _C_COLORS


register(CPlugin())
