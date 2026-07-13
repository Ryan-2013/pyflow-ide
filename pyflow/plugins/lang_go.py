"""PyFlow Language Plugin — Go"""
from __future__ import annotations
import shutil
from plugins import LanguagePlugin, register


class GoPlugin(LanguagePlugin):
    id          = "go"
    name        = "Go"
    version     = "1.0.0"
    extensions  = [".go"]
    monaco_id   = "go"
    icon        = "🐹"
    color       = "#00ADD8"
    description = "Go — goroutine/channel visualization, generic type support"

    def parse(self, code: str, path: str) -> dict:
        from core.go_parser import parse_go_file
        return parse_go_file(code, path)

    def extract_symbols(self, code: str, path: str, parse_result=None) -> list:
        from core.symbols import extract_symbols
        from core.go_stdlib import parse_go_imports_from_code, get_symbols_for_package
        r = parse_result or self.parse(code, path)
        syms = extract_symbols(r, "go", code)
        # Also pull stdlib symbols
        pkg_map = parse_go_imports_from_code(code)
        for alias, pkg in pkg_map.items():
            syms.extend(get_symbols_for_package(pkg, alias if alias != pkg.split("/")[-1] else None))
        return syms

    def format_code(self, code: str) -> dict:
        from core.formatter import format_go
        return format_go(code)

    def get_lsp_command(self) -> list | None:
        return ["gopls", "serve"] if shutil.which("gopls") else None

    def run_tests(self, path: str) -> dict | None:
        from core.test_runner import run_go_test
        return run_go_test(path)

    def get_run_command(self, path: str) -> list | None:
        return ["go", "run", path] if shutil.which("go") else None

    def get_node_types(self) -> dict:
        return {
            "goroutine": {"n": "Goroutine", "c": "#1a3a1a"},
            "channel":   {"n": "Channel",   "c": "#0a2a2a"},
            "defer":     {"n": "Defer",     "c": "#1a1a3a"},
            "select":    {"n": "Select",    "c": "#2a1a0a"},
            "error_check": {"n": "Error Check", "c": "#3a1a0a"},
        }


register(GoPlugin())
