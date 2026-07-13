"""
PyFlow Language Plugin — Jupyter Notebook (.ipynb)
====================================================
Parses notebook cells into a flow diagram.
Each cell becomes a flow node (code_cell / markdown_cell).
"""
from __future__ import annotations
import json, os, re, shutil, subprocess, sys, tempfile
from plugins import LanguagePlugin, register


def _cell_preview(source_lines: list) -> str:
    src = ''.join(source_lines).strip()
    # First non-empty, non-comment line
    for line in src.split('\n'):
        line = line.strip()
        if line and not line.startswith('#'):
            return line[:60]
    return src[:60]


def _calls_in_cell(source: str) -> list:
    """Find function calls in a code cell."""
    calls = []
    for m in re.finditer(r'\b(\w+)\s*\(', source):
        name = m.group(1)
        if name not in {'if','for','while','print','len','type','range','list','dict','set','tuple'}:
            calls.append(name)
    return list(dict.fromkeys(calls))[:5]  # unique, max 5


class JupyterPlugin(LanguagePlugin):
    id          = "jupyter"
    name        = "Jupyter Notebook"
    version     = "1.0.0"
    extensions  = [".ipynb"]
    monaco_id   = "json"
    icon        = "📓"
    color       = "#F37626"
    description = "Jupyter Notebook — cell visualization, inline execution, output display"

    def parse(self, code: str, path: str) -> dict:
        try:
            nb = json.loads(code)
        except json.JSONDecodeError as e:
            return {"flow": [], "definitions": [], "error": f"Invalid notebook JSON: {e}", "error_line": 0}

        cells     = nb.get("cells", [])
        flow      = []
        defs      = []
        code_step = 0

        for i, cell in enumerate(cells, 1):
            cell_type = cell.get("cell_type", "code")
            source    = cell.get("source", [])
            if isinstance(source, list):
                source = "".join(source)
            outputs   = cell.get("outputs", [])
            num_outputs = len(outputs)

            preview = _cell_preview(source.split('\n'))

            if cell_type == "code":
                code_step += 1
                calls = _calls_in_cell(source)
                node_type = "call"
                if re.search(r'\bimport\b', source[:100]):
                    node_type = "import"
                elif re.search(r'^\s*def\s+\w+', source, re.M):
                    node_type = "function"
                    # Also add to definitions
                    for m in re.finditer(r'^\s*def\s+(\w+)', source, re.M):
                        defs.append({
                            "id": m.group(1), "type": "function", "label": m.group(1),
                            "line": i, "detail": f"Cell {i}", "methods": [], "is_async": False,
                        })
                elif re.search(r'^\s*class\s+\w+', source, re.M):
                    node_type = "class"

                flow.append({
                    "id":     f"cell_{i}",
                    "type":   node_type,
                    "label":  f"[{code_step}] {preview}",
                    "line":   i,
                    "detail": f"Cell {i} · {num_outputs} 個輸出",
                    "calls":  calls,
                    "step":   code_step,
                    "cell_source": source,
                    "cell_outputs": _format_outputs(outputs),
                })
            elif cell_type == "markdown":
                # Show first heading or first line
                heading = ""
                for line in source.split('\n'):
                    m = re.match(r'^#{1,3}\s+(.+)', line)
                    if m:
                        heading = m.group(1)[:50]
                        break
                label = heading or preview[:50] or "Markdown"
                flow.append({
                    "id":     f"md_{i}",
                    "type":   "context",
                    "label":  f"📝 {label}",
                    "line":   i,
                    "detail": "Markdown",
                    "calls":  [],
                    "cell_source": source,
                })

        return {
            "flow":         flow,
            "definitions":  defs,
            "error":        None,
            "error_line":   0,
            "notebook_meta": nb.get("metadata", {}),
            "cell_count":   len(cells),
            "kernel":       nb.get("metadata", {}).get("kernelspec", {}).get("name", "python3"),
        }

    def extract_symbols(self, code: str, path: str, parse_result=None) -> list:
        r = parse_result or self.parse(code, path)
        syms = []
        for d in r.get("definitions", []):
            syms.append({
                "name": d["id"], "kind": d["type"], "line": d["line"],
                "sig": d.get("detail", ""), "doc": "", "source": "user",
                "module": "", "parent": "",
            })
        return syms

    def get_node_types(self) -> dict:
        return {
            "code_cell":     {"n": "Code Cell",     "c": "#1e2a3a"},
            "markdown_cell": {"n": "Markdown Cell",  "c": "#2a1e3a"},
            "raw_cell":      {"n": "Raw Cell",       "c": "#1a1a1a"},
        }

    def get_run_command(self, path: str) -> list | None:
        if shutil.which("jupyter"):
            return ["jupyter", "nbconvert", "--to", "script", "--execute", path]
        return None


def _format_outputs(outputs: list) -> list:
    """Extract text/plain outputs from a cell's outputs."""
    result = []
    for out in outputs[:5]:
        out_type = out.get("output_type", "")
        if out_type == "stream":
            text = "".join(out.get("text", []))
            result.append({"type": "stream", "name": out.get("name","stdout"), "text": text[:500]})
        elif out_type in ("display_data", "execute_result"):
            data = out.get("data", {})
            if "text/plain" in data:
                text = "".join(data["text/plain"]) if isinstance(data["text/plain"], list) else data["text/plain"]
                result.append({"type": "result", "text": text[:300]})
            elif "text/html" in data:
                result.append({"type": "html", "text": "[HTML 輸出]"})
            elif "image/png" in data:
                result.append({"type": "image", "text": "[圖片輸出]"})
        elif out_type == "error":
            result.append({"type": "error",
                           "text": out.get("ename","") + ": " + out.get("evalue","")})
    return result


# ── Cell execution via kernel ──────────────────────────────────────

def run_notebook_cell(path: str, cell_source: str, kernel: str = "python3") -> dict:
    """
    Execute a single notebook cell.
    Uses jupyter nbconvert as a fallback if no live kernel.
    """
    # Try direct Python execution (simplest)
    if kernel in ("python3", "python"):
        tmp = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".py", mode="w",
                                             delete=False, encoding="utf-8") as f:
                f.write(cell_source)
                tmp = f.name
            python = sys.executable
            result = subprocess.run(
                [python, tmp],
                capture_output=True, text=True, timeout=30,
            )
            return {
                "ok":     result.returncode == 0,
                "stdout": result.stdout[-3000:],
                "stderr": result.stderr[-1000:],
                "type":   "stream",
            }
        except subprocess.TimeoutExpired:
            return {"ok": False, "stdout": "", "stderr": "執行逾時（>30s）", "type": "error"}
        except Exception as e:
            return {"ok": False, "stdout": "", "stderr": str(e), "type": "error"}
        finally:
            if tmp and os.path.exists(tmp):
                os.unlink(tmp)
    return {"ok": False, "stdout": "", "stderr": f"不支援 kernel: {kernel}", "type": "error"}


register(JupyterPlugin())
