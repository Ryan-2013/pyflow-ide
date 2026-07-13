"""PyFlow Language Plugin — Rust"""
from __future__ import annotations
import shutil
from plugins import LanguagePlugin, register


class RustPlugin(LanguagePlugin):
    id          = "rust"
    name        = "Rust"
    version     = "1.0.0"
    extensions  = [".rs"]
    monaco_id   = "rust"
    icon        = "🦀"
    color       = "#DEA584"
    description = "Rust — ownership visualization (●◎◈⚠), tree-sitter AST, borrow checker integration"

    def parse(self, code: str, path: str) -> dict:
        from core.rust_parser import parse_rust_file
        return parse_rust_file(code, path)

    def extract_symbols(self, code: str, path: str, parse_result=None) -> list:
        from core.symbols import extract_symbols
        from core.rust_stdlib import get_symbols_for_use
        r = parse_result or self.parse(code, path)
        syms = extract_symbols(r, "rust", code)
        # Pull stdlib symbols (Option, Result, Vec, etc.)
        for t in ("Option", "Result", "Vec", "String", "HashMap"):
            syms.extend(get_symbols_for_use(f"use {t};"))
        return syms

    def format_code(self, code: str) -> dict:
        from core.formatter import format_rust
        return format_rust(code)

    def get_lsp_command(self) -> list | None:
        return ["rust-analyzer"] if shutil.which("rust-analyzer") else None

    def run_tests(self, path: str) -> dict | None:
        from core.test_runner import run_cargo_test
        return run_cargo_test(path)

    def get_run_command(self, path: str) -> list | None:
        return None   # Rust needs cargo run, not direct file execution

    def get_node_types(self) -> dict:
        return {
            "unsafe_block": {"n": "Unsafe", "c": "#3a0a0a"},
            "match":        {"n": "Match",  "c": "#3a2a1a"},
        }

    def extra_meta(self) -> dict:
        """Rust-specific: ownership metadata for UI badges."""
        from core.rust_check import is_available
        return {
            "rustc_available": is_available(),
            "ownership_meta": {
                "owned":      {"icon": "●",  "color": "#22c55e", "label": "owned"},
                "shared_ref": {"icon": "◎",  "color": "#60a5fa", "label": "&T"},
                "mut_ref":    {"icon": "◈",  "color": "#f97316", "label": "&mut T"},
                "raw_const":  {"icon": "⚠",  "color": "#ef4444", "label": "*const T"},
                "raw_mut":    {"icon": "⚠",  "color": "#dc2626", "label": "*mut T"},
                "box":        {"icon": "□",  "color": "#a78bfa", "label": "Box<T>"},
                "rc":         {"icon": "⊙",  "color": "#38bdf8", "label": "Rc<T>"},
                "arc":        {"icon": "⊙",  "color": "#2dd4bf", "label": "Arc<T>"},
            },
        }


register(RustPlugin())
