"""
PyFlow IDE — Language Plugin System
====================================
Base class, type definitions, and global plugin registry.

Usage (plugin author):
    # myfile.py → drop into pyflow/plugins/
    from plugins import LanguagePlugin, register

    class MyPlugin(LanguagePlugin):
        id         = "mylang"
        name       = "My Language"
        version    = "1.0.0"
        extensions = [".ml", ".mls"]
        monaco_id  = "plaintext"   # Monaco language ID
        icon       = "🟣"
        color      = "#7B2D8B"

        def parse(self, code: str, path: str) -> dict:
            return {"flow": [], "definitions": [], "error": None}

    register(MyPlugin())   # last line — registers automatically

Plugin authors only need to implement parse().
All other methods are optional and fall back to sensible defaults.
"""
from __future__ import annotations
import os, importlib, sys
from typing import Any


# ─── Type aliases (for documentation; not enforced at runtime) ────

# FlowNode keys:
#   id        str    — unique node ID within the file
#   type      str    — one of the TYPE_IDS below
#   label     str    — display label
#   line      int    — source line number (1-based)
#   detail    str    — secondary text
#   calls     list   — list of definition IDs this node invokes
#   children  list   — sub-nodes rendered inside this node
#   step      int    — optional step number badge

# Definition keys:
#   id        str    — unique function/class ID
#   type      str    — "function" | "class"
#   label     str    — display name
#   line      int    — definition line
#   detail    str    — signature or summary
#   methods   list   — list of method FlowNodes
#   is_async  bool   — async function?
#   qualifier_icon str — optional left-side icon

# ParseResult keys:
#   flow        list   — ordered list of FlowNodes
#   definitions list   — function/class definitions (right column)
#   error       str|None
#   error_line  int

# Symbol keys (for IntelliSense):
#   name     str    — symbol name
#   kind     str    — "function"|"class"|"variable"|"module"|"builtin"|"method"
#   line     int    — definition line (0 if unknown)
#   sig      str    — display signature
#   doc      str    — documentation string
#   source   str    — "user"|"import"|"module"|"builtin"
#   module   str    — parent module (optional)
#   parent   str    — parent class (optional)
#   ret      str    — return type (optional)
#   params   list   — parameter names (optional)

# ─── Valid flow node types ─────────────────────────────────────────
TYPE_IDS = frozenset({
    "import", "assign", "call", "goroutine", "channel",
    "match", "condition", "loop", "context", "exception",
    "flow_ctrl", "function", "class", "unsafe_block",
    "error_check", "defer", "select", "other",
})


# ─── LanguagePlugin base class ─────────────────────────────────────

class LanguagePlugin:
    """
    Base class for all PyFlow language plugins.

    Required class attributes (must override):
        id          Unique language ID ("python", "c", "ruby", …)
        name        Display name ("Python", "C Language", …)
        extensions  List of file extensions ([".py", ".pyw"])
        monaco_id   Monaco editor language ID ("python", "c", "plaintext")

    Optional class attributes (have defaults):
        version     Plugin version string         default: "1.0.0"
        icon        Emoji icon                    default: "📄"
        color       Hex brand color               default: "#888888"
        author      Author name/email             default: ""
        description Short description             default: ""
    """

    # ── Required ──────────────────────────────────────────────────
    id:         str  = ""
    name:       str  = "Unknown"
    extensions: list = []
    monaco_id:  str  = "plaintext"

    # ── Optional ──────────────────────────────────────────────────
    version:     str = "1.0.0"
    icon:        str = "📄"
    color:       str = "#888888"
    author:      str = ""
    description: str = ""

    # ── REQUIRED: Parse ───────────────────────────────────────────

    def parse(self, code: str, path: str) -> dict:
        """
        Parse source code and return flow graph data.

        Args:
            code:  Complete source code as string
            path:  Absolute file path (for error messages and context)

        Returns:
            {
              "flow":        list[FlowNode],     # top-level execution flow
              "definitions": list[Definition],   # function/class definitions
              "error":       str | None,         # parse error message
              "error_line":  int,                # error line (0 if unknown)
            }
        """
        raise NotImplementedError(
            f"Plugin '{self.id}' must implement parse()"
        )

    # ── OPTIONAL: Symbols ──────────────────────────────────────────

    def extract_symbols(self, code: str, path: str,
                        parse_result: dict | None = None) -> list:
        """
        Extract symbols for IntelliSense autocomplete and hover.

        If parse_result is provided, you can reuse already-parsed data
        instead of re-parsing the code.

        Returns: list[Symbol]
        """
        return []

    # ── OPTIONAL: Formatting ───────────────────────────────────────

    def format_code(self, code: str) -> dict | None:
        """
        Format source code using the language's official formatter.

        Returns:
            {"formatted": str, "error": str|None, "tool": str}
            or None if formatting is not supported.
        """
        return None   # Not supported

    # ── OPTIONAL: LSP ──────────────────────────────────────────────

    def get_lsp_command(self) -> list | None:
        """
        Return the command to launch the Language Server, or None.

        Example: ["clangd", "--background-index"]
                 ["typescript-language-server", "--stdio"]
        """
        return None

    # ── OPTIONAL: Testing ─────────────────────────────────────────

    def run_tests(self, path: str) -> dict | None:
        """
        Run the language's test suite.

        Returns the same format as test_runner.run_tests(), or None.
        """
        return None

    # ── OPTIONAL: Profiling ────────────────────────────────────────

    def profile(self, path: str) -> dict | None:
        """
        Profile code execution.
        Returns {functions: {name: {time_ms, cumtime_ms, calls}}, total_ms}
        or None if not supported.
        """
        return None

    # ── OPTIONAL: Node types ───────────────────────────────────────

    def get_node_types(self) -> dict:
        """
        Return additional node types specific to this language.

        Format: {"type_id": {"n": "Display Name", "c": "#hex_color"}}

        These are merged with the built-in node types.
        The built-in types are: import, assign, call, goroutine, channel,
        match, condition, loop, context, exception, flow_ctrl, function,
        class, unsafe_block, error_check, defer, select, other.
        """
        return {}

    # ── OPTIONAL: Run ─────────────────────────────────────────────

    def get_run_command(self, path: str) -> list | None:
        """
        Return the command to run a source file, or None.
        If None, the run button is disabled for this language.

        Example: ["python", path]
                 ["node", path]
        """
        return None

    # ── Metadata (for /api/languages) ─────────────────────────────

    def to_dict(self) -> dict:
        return {
            "id":          self.id,
            "name":        self.name,
            "version":     self.version,
            "extensions":  self.extensions,
            "monaco_id":   self.monaco_id,
            "icon":        self.icon,
            "color":       self.color,
            "author":      self.author,
            "description": self.description,
            "supports": {
                "format":   self.format_code.__class__ is not LanguagePlugin.format_code.__class__ or self.format_code(None) is not None,
                "lsp":      self.get_lsp_command() is not None,
                "tests":    self.run_tests.__class__ is not LanguagePlugin.run_tests.__class__,
                "profile":  self.profile.__class__ is not LanguagePlugin.profile.__class__,
                "run":      self.get_run_command("") is not None,
            }
        }

    def __repr__(self):
        return f"<LanguagePlugin {self.id!r} extensions={self.extensions}>"


# ─── Global Plugin Registry ───────────────────────────────────────

_REGISTRY: dict[str, LanguagePlugin] = {}   # id → plugin
_EXT_MAP:  dict[str, str]           = {}    # ".py" → "python"

def register(plugin: LanguagePlugin) -> None:
    """Register a plugin. Later registrations override earlier ones."""
    if not plugin.id:
        raise ValueError("Plugin must have a non-empty 'id'")
    _REGISTRY[plugin.id] = plugin
    for ext in plugin.extensions:
        _EXT_MAP[ext.lower()] = plugin.id

def get_by_id(lang_id: str) -> LanguagePlugin | None:
    return _REGISTRY.get(lang_id)

def get_by_path(path: str) -> LanguagePlugin | None:
    ext = os.path.splitext(path)[1].lower()
    lang_id = _EXT_MAP.get(ext)
    return _REGISTRY.get(lang_id) if lang_id else None

def get_by_ext(ext: str) -> LanguagePlugin | None:
    lang_id = _EXT_MAP.get(ext.lower())
    return _REGISTRY.get(lang_id) if lang_id else None

def all_plugins() -> list[LanguagePlugin]:
    return list(_REGISTRY.values())

def all_extensions() -> dict[str, str]:
    """Return {".ext": "lang_id"} for all registered languages."""
    return dict(_EXT_MAP)


# ─── Plugin Loader ────────────────────────────────────────────────

def load_plugins_from_dir(directory: str) -> list[str]:
    """
    Scan directory for Python files matching lang_*.py and load them.
    Returns list of successfully loaded plugin IDs.
    """
    loaded: list[str] = []
    directory = os.path.abspath(directory)
    if directory not in sys.path:
        sys.path.insert(0, os.path.dirname(directory))

    for fname in sorted(os.listdir(directory)):
        if not (fname.startswith('lang_') and fname.endswith('.py')):
            continue
        module_name = 'plugins.' + fname[:-3]
        try:
            if module_name in sys.modules:
                importlib.reload(sys.modules[module_name])
            else:
                importlib.import_module(module_name)
            # Collect newly registered plugins from this module
            loaded.extend(
                pid for pid, p in _REGISTRY.items()
                if pid not in loaded and hasattr(p, '__module__')
                and p.__module__ == module_name
            )
        except Exception as e:
            print(f"[plugin_loader] Failed to load {fname}: {e}")

    return loaded
