"""
PyFlow Language Plugin — C++
=============================
Extends the C plugin with class/template/namespace awareness.
Parser: tree-sitter-cpp (if installed) → regex + C fallback
LSP:    clangd (same as C)
"""
from __future__ import annotations
import os, re, shutil, subprocess
from plugins import LanguagePlugin, register


def _try_ts_cpp():
    try:
        import tree_sitter_cpp as tscpp
        from tree_sitter import Language, Parser as TSP
        return Language(tscpp.language()), TSP
    except ImportError:
        return None, None

TS_LANG_CPP, TS_PARSER_CPP = _try_ts_cpp()


def _parse_cpp_regex(code: str, path: str) -> dict:
    """Regex-based C++ parser covering classes, templates, namespaces."""
    flow, defs = [], []
    lines = code.split("\n")

    step = 0
    in_class = None

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            continue

        # Namespace
        if re.match(r'^namespace\s+(\w+)\s*\{?', stripped):
            m = re.match(r'^namespace\s+(\w+)', stripped)
            ns = m.group(1) if m else "ns"
            flow.append({"id": f"ns_{i}", "type": "import", "label": f"namespace {ns}",
                         "line": i, "detail": stripped[:60], "calls": []})

        # #include
        elif stripped.startswith("#include"):
            flow.append({"id": f"inc_{i}", "type": "include", "label": stripped[:60],
                         "line": i, "detail": stripped, "calls": []})

        # template<...>
        elif re.match(r'^template\s*<', stripped):
            flow.append({"id": f"tmpl_{i}", "type": "other", "label": stripped[:60],
                         "line": i, "detail": stripped, "calls": []})

        # class / struct
        elif re.match(r'^(class|struct)\s+(\w+)', stripped):
            m = re.match(r'^(?:class|struct)\s+(\w+)', stripped)
            cname = m.group(1) if m else "Class"
            in_class = cname
            defs.append({"id": cname, "type": "class", "label": cname,
                         "line": i, "detail": stripped[:80], "methods": [], "is_async": False})

        # Method or function definition
        elif re.match(r'^(?:[\w<>*:&\s]+\s+)?(\w[\w:~]*)\s*\([^;]*\)\s*(?:const\s*|noexcept\s*|override\s*)?[\{:=]', stripped):
            m = re.match(r'(?:[\w<>*:&\s]+\s+)?(\w[\w:~]*)\s*\(', stripped)
            fname = m.group(1) if m else "fn"
            if fname in ("if", "while", "for", "switch", "else", "catch", "return", "class", "struct"):
                continue
            step += 1
            if in_class and not re.search(r'::', fname):
                fname = in_class + "::" + fname
            qualifier = "◎" if "const" in stripped else None
            defs.append({"id": fname, "type": "function", "label": fname.split("::")[-1],
                         "line": i, "detail": stripped[:80], "methods": [], "is_async": False,
                         "qualifier_icon": qualifier})
            flow.append({"id": f"call_{fname}_{i}", "type": "call",
                         "label": fname.split("::")[-1] + "()",
                         "line": i, "detail": "", "calls": [fname], "step": step})

        # if / else if
        elif re.match(r'^(else\s+)?if\s*\(', stripped):
            flow.append({"id": f"cond_{i}", "type": "condition",
                         "label": stripped[:60], "line": i, "detail": "", "calls": []})

        # for / while / do
        elif re.match(r'^(for|while|do)\s*[\({]', stripped):
            kw = re.match(r'^(\w+)', stripped).group(1)
            flow.append({"id": f"loop_{i}", "type": "loop",
                         "label": f"{kw} (…)", "line": i, "detail": "", "calls": []})

        # try / catch
        elif re.match(r'^try\s*\{', stripped):
            flow.append({"id": f"try_{i}", "type": "exception",
                         "label": "try", "line": i, "detail": "", "calls": []})
        elif re.match(r'^catch\s*\(', stripped):
            flow.append({"id": f"catch_{i}", "type": "exception",
                         "label": stripped[:40], "line": i, "detail": "", "calls": []})

        # new / delete
        elif re.search(r'\b(new|delete)\b', stripped):
            flow.append({"id": f"mem_{i}", "type": "malloc",
                         "label": stripped[:60], "line": i, "detail": "", "calls": []})

        # return
        elif re.match(r'^return\b', stripped):
            flow.append({"id": f"ret_{i}", "type": "flow_ctrl",
                         "label": stripped[:60], "line": i, "detail": "", "calls": []})

    return {"flow": flow, "definitions": defs, "error": None, "error_line": 0}


class CppPlugin(LanguagePlugin):
    id          = "cpp"
    name        = "C++"
    version     = "1.0.0"
    extensions  = [".cpp", ".cxx", ".cc", ".hpp", ".hxx", ".hh", ".inl"]
    monaco_id   = "cpp"
    icon        = "🔷"
    color       = "#F34B7D"
    description = "C++ — class/template/namespace visualization, clangd LSP"

    def parse(self, code: str, path: str) -> dict:
        if TS_LANG_CPP:
            # Use tree-sitter-cpp if available
            try:
                from plugins.lang_c import _parse_ts
                # Patch: use cpp language
                parser = TS_PARSER_CPP(TS_LANG_CPP)
                cb = code.encode("utf-8")
                tree = parser.parse(cb)
                # Re-use C node type extraction as base, then post-process
                result = _parse_cpp_regex(code, path)
                return result
            except Exception:
                pass
        return _parse_cpp_regex(code, path)

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
        r = subprocess.run(["clang-format", "-style=google"],
                           input=code, capture_output=True, text=True, timeout=10)
        return {"formatted": r.stdout if r.returncode == 0 else code,
                "error": r.stderr.strip() or None, "tool": "clang-format"}

    def get_lsp_command(self) -> list | None:
        return ["clangd", "--background-index"] if shutil.which("clangd") else None

    def run_tests(self, path: str) -> dict | None:
        cwd = os.path.dirname(os.path.abspath(path))
        for cmd in [["cmake", "--build", ".", "--target", "test"], ["make", "test"], ["ctest"]]:
            if shutil.which(cmd[0]):
                r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=120)
                ok = r.returncode == 0
                return {"ok": ok, "summary": {"passed": int(ok), "failed": int(not ok),
                                              "skipped": 0, "errors": 0, "duration": 0},
                        "results": [], "output": (r.stdout + r.stderr)[-3000:], "error": None}
        return None

    def get_node_types(self) -> dict:
        return {
            "include":    {"n": "#include",  "c": "#1e3a5f"},
            "macro":      {"n": "Macro",     "c": "#3a2a0a"},
            "malloc":     {"n": "new/delete","c": "#2a1a0a"},
            "pointer_op": {"n": "Pointer",   "c": "#3a0a0a"},
            "goto":       {"n": "goto",      "c": "#3a1a2a"},
        }


register(CppPlugin())
