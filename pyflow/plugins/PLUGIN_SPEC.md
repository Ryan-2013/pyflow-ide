# PyFlow Language Plugin Specification v1.0

> 讓任何人可以為 PyFlow IDE 添加新語言支援，只需一個 Python 檔案。

---

## 目錄

1. [快速開始](#快速開始)
2. [插件接口完整說明](#插件接口完整說明)
3. [回傳資料格式](#回傳資料格式)
4. [節點類型列表](#節點類型列表)
5. [完整範例：TypeScript 插件](#完整範例typescript-插件)
6. [安裝插件](#安裝插件)
7. [測試插件](#測試插件)

---

## 快速開始

**最小可用插件（只需 5 行）：**

```python
# pyflow/plugins/lang_lua.py
from plugins import LanguagePlugin, register

class LuaPlugin(LanguagePlugin):
    id         = "lua"
    name       = "Lua"
    extensions = [".lua"]
    monaco_id  = "lua"
    icon       = "🌙"
    color      = "#000080"

    def parse(self, code: str, path: str) -> dict:
        return {"flow": [], "definitions": [], "error": None, "error_line": 0}

register(LuaPlugin())
```

把這個檔案放入 `pyflow/plugins/`，重啟 PyFlow，Lua 的 `.lua` 檔案就能被識別。

---

## 插件接口完整說明

```python
class LanguagePlugin:
    # ══ 必填屬性 ══════════════════════════════════════════════════
    
    id: str
    # 唯一識別碼，小寫英文+連字號
    # 例："python", "go", "rust", "c", "typescript", "ruby"
    # 不可與現有插件衝突（除非你要覆寫它）
    
    name: str
    # 顯示名稱
    # 例："Python", "Go", "TypeScript"
    
    extensions: list[str]
    # 檔案副檔名（含點，小寫）
    # 例：[".ts", ".tsx"]
    
    monaco_id: str
    # Monaco Editor 的語言 ID
    # 例："typescript", "python", "c", "cpp", "plaintext"
    # 完整列表：https://microsoft.github.io/monaco-editor/
    
    # ══ 選填屬性 ══════════════════════════════════════════════════
    
    version: str     = "1.0.0"  # 語義化版本號
    icon: str        = "📄"      # Emoji，顯示在檔案樹和標題欄
    color: str       = "#888888" # 十六進制品牌色
    author: str      = ""        # 作者名稱或 email
    description: str = ""        # 一行說明
    
    # ══ 必填方法 ══════════════════════════════════════════════════
    
    def parse(self, code: str, path: str) -> dict:
        """
        解析原始碼，回傳流程圖資料。
        
        參數：
            code  完整原始碼字串
            path  絕對檔案路徑（用於相對行號和錯誤訊息）
        
        回傳 ParseResult（見下方格式說明）
        """
        ...
    
    # ══ 選填方法 ══════════════════════════════════════════════════
    
    def extract_symbols(self, code, path, parse_result=None) -> list[Symbol]:
        """
        提取 IntelliSense 符號（補全、懸停）。
        
        若 parse_result 已有，可重用避免重複解析。
        回傳 Symbol 列表（見下方格式說明）。
        預設：回傳空列表
        """
        return []
    
    def format_code(self, code: str) -> dict | None:
        """
        格式化原始碼。
        
        回傳 {"formatted": str, "error": str|None, "tool": str}
        或 None（不支援格式化）。
        """
        return None
    
    def get_lsp_command(self) -> list[str] | None:
        """
        回傳 LSP 伺服器的啟動命令列，或 None。
        
        例：["typescript-language-server", "--stdio"]
             ["clangd", "--background-index"]
             ["solargraph", "stdio"]
        """
        return None
    
    def run_tests(self, path: str) -> dict | None:
        """
        執行語言的測試工具。
        
        回傳與 core/test_runner.py 相同格式的 dict，或 None。
        格式：
        {
          "ok": bool,
          "summary": {"passed": int, "failed": int, "skipped": int, "errors": int, "duration": float},
          "results": [{"name": str, "status": str, "duration": float, "message": str}],
          "output": str,
          "error": str | None,
        }
        """
        return None
    
    def profile(self, path: str) -> dict | None:
        """
        執行效能分析。
        
        回傳：
        {
          "functions": {name: {"time_ms": float, "cumtime_ms": float, "calls": int, "own": bool}},
          "total_ms": float,
          "error": str | None,
        }
        或 None（不支援）。
        """
        return None
    
    def get_run_command(self, path: str) -> list[str] | None:
        """
        回傳直接執行腳本的命令列，或 None（需要編譯則回傳 None）。
        
        例：["node", path]
             ["ruby", path]
             ["python3", path]
        回傳 None 時，「執行」按鈕對此語言停用。
        """
        return None
    
    def get_node_types(self) -> dict:
        """
        定義此語言專屬的流程圖節點類型。
        
        格式：{"type_id": {"n": "顯示名稱", "c": "#hex色碼"}}
        
        與內建節點類型合併（可以覆寫內建類型的顏色）。
        預設：回傳空字典（只用內建類型）
        
        例：
        {
            "goroutine": {"n": "Goroutine", "c": "#1a3a1a"},
            "template":  {"n": "Template",  "c": "#2a1a3a"},
        }
        """
        return {}
```

---

## 回傳資料格式

### ParseResult

```python
{
    "flow":        list[FlowNode],     # 主執行流（左欄）
    "definitions": list[Definition],   # 函式/類別定義（右欄）
    "error":       str | None,         # 解析錯誤訊息
    "error_line":  int,                # 錯誤行號（0 = 未知）
}
```

### FlowNode

```python
{
    "id":       str,           # 節點 ID（在同一檔案中唯一）
    "type":     str,           # 節點類型（見下方節點類型列表）
    "label":    str,           # 顯示文字（主要標籤）
    "line":     int,           # 對應的原始碼行號（1-based，0=未知）
    "detail":   str,           # 第二行說明文字（可空）
    "calls":    list[str],     # 此節點呼叫的 Definition.id 列表
    "children": list[FlowNode],# 子節點（內嵌顯示於節點內）
    "step":     int,           # 序號徽章（0 = 不顯示）
    
    # 選填（語義標記）
    "ownership":     str,      # Rust 所有權："owned"|"shared_ref"|"mut_ref" 等
    "is_async":      bool,     # 是否為 async 操作
}
```

### Definition

```python
{
    "id":            str,           # 全域唯一 ID（通常是函式名）
    "type":          str,           # "function" 或 "class"
    "label":         str,           # 顯示名稱
    "line":          int,           # 定義行號
    "detail":        str,           # 函式簽名或類別摘要
    "methods":       list[Method],  # 類別方法列表
    "is_async":      bool,          # async 函式？
    "qualifier_icon": str | None,   # 左側圖示（如 "○" 表示靜態方法）
    "custom_decorators": list[str], # 裝飾器名稱列表
}
```

### Method（Definition.methods 的元素）

```python
{
    "id":            str,
    "label":         str,
    "line":          int,
    "qualifier_icon": str | None,
    "is_async":      bool,
}
```

### Symbol

```python
{
    "name":   str,      # 符號名稱
    "kind":   str,      # "function"|"class"|"variable"|"module"|"builtin"|"method"
    "line":   int,      # 定義行（0=未知）
    "sig":    str,      # 顯示簽名（如 "def foo(x, y) -> int"）
    "doc":    str,      # 文件字串
    "source": str,      # "user"|"import"|"module"|"builtin"
    "module": str,      # 所屬模組（可空）
    "parent": str,      # 父類別名（可空）
    "ret":    str,      # 回傳類型（可空）
    "params": list[str],# 參數名稱列表
    "fqname": str,      # 全限定名（如 "os.path.join"）
}
```

---

## 節點類型列表

PyFlow 內建的節點類型（可在 `get_node_types()` 中覆寫顏色）：

| type_id       | 預設顯示名 | 語義 |
|---------------|-----------|------|
| `import`      | 匯入      | import / use / require / #include |
| `assign`      | 賦值      | 變數賦值 / let / const / var |
| `call`        | 呼叫      | 函式呼叫 |
| `condition`   | 條件      | if / else if |
| `loop`        | 迴圈      | for / while / loop |
| `exception`   | 例外      | try / catch / throw |
| `flow_ctrl`   | 控制流    | return / break / continue |
| `match`       | Match    | switch / match / when |
| `context`     | 上下文    | with / using / defer（上下文管理） |
| `function`    | 函式      | 函式定義（右欄） |
| `class`       | 類別      | class / struct / interface（右欄） |
| `goroutine`   | Goroutine | Go goroutine |
| `channel`     | 通道      | Go channel 操作 |
| `unsafe_block`| Unsafe    | Rust unsafe 區塊 |
| `error_check` | 錯誤檢查  | Go `if err != nil` |
| `defer`       | Defer     | Go defer |
| `select`      | Select    | Go select |
| `other`       | 其他      | 未分類語句 |

---

## 完整範例：TypeScript 插件

```python
# pyflow/plugins/lang_typescript.py
"""PyFlow Language Plugin — TypeScript / TSX"""
from __future__ import annotations
import re, shutil
from plugins import LanguagePlugin, register


class TypeScriptPlugin(LanguagePlugin):
    id          = "typescript"
    name        = "TypeScript"
    version     = "1.0.0"
    extensions  = [".ts", ".tsx", ".mts", ".cts"]
    monaco_id   = "typescript"
    icon        = "🔷"
    color       = "#3178C6"
    description = "TypeScript — type-aware flow visualization, typescript-language-server"

    def parse(self, code: str, path: str) -> dict:
        flow, defs = [], []
        lines = code.split("\n")
        step = 0

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("//"):
                continue

            # import
            if re.match(r'^import\s', stripped):
                flow.append({"id": f"imp_{i}", "type": "import",
                             "label": stripped[:60], "line": i, "detail": stripped, "calls": []})

            # interface / type alias
            elif re.match(r'^(export\s+)?(interface|type)\s+(\w+)', stripped):
                m = re.match(r'(?:export\s+)?(?:interface|type)\s+(\w+)', stripped)
                name = m.group(1) if m else "Type"
                defs.append({"id": name, "type": "class", "label": name,
                             "line": i, "detail": "interface/type", "methods": [], "is_async": False})

            # function / async function / arrow
            elif re.match(r'^(?:export\s+)?(?:async\s+)?function\s+(\w+)', stripped):
                m = re.match(r'(?:export\s+)?(?:async\s+)?function\s+(\w+)', stripped)
                fname = m.group(1) if m else "fn"
                is_async = "async" in stripped[:30]
                step += 1
                defs.append({"id": fname, "type": "function", "label": fname,
                             "line": i, "detail": stripped[:80], "methods": [],
                             "is_async": is_async})
                flow.append({"id": f"call_{fname}", "type": "call",
                             "label": fname + "()", "line": i, "detail": "",
                             "calls": [fname], "step": step})

            # class
            elif re.match(r'^(?:export\s+)?(?:abstract\s+)?class\s+(\w+)', stripped):
                m = re.match(r'(?:export\s+)?(?:abstract\s+)?class\s+(\w+)', stripped)
                cname = m.group(1) if m else "Class"
                defs.append({"id": cname, "type": "class", "label": cname,
                             "line": i, "detail": stripped[:80], "methods": [], "is_async": False})

            # if / else if
            elif re.match(r'^(?:else\s+)?if\s*\(', stripped):
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

            # return / throw
            elif re.match(r'^(return|throw)\b', stripped):
                flow.append({"id": f"ret_{i}", "type": "flow_ctrl",
                             "label": stripped[:60], "line": i, "detail": "", "calls": []})

            # await expression
            elif "await " in stripped:
                flow.append({"id": f"await_{i}", "type": "context",
                             "label": stripped[:60], "line": i, "detail": "", "calls": [],
                             "is_async": True})

        return {"flow": flow, "definitions": defs, "error": None, "error_line": 0}

    def format_code(self, code: str) -> dict:
        if shutil.which("prettier"):
            import subprocess
            r = subprocess.run(["prettier", "--parser", "typescript"],
                               input=code, capture_output=True, text=True, timeout=10)
            return {"formatted": r.stdout if r.returncode == 0 else code,
                    "error": r.stderr.strip() or None, "tool": "prettier"}
        if shutil.which("deno"):
            import subprocess
            r = subprocess.run(["deno", "fmt", "--ext", "ts", "-"],
                               input=code, capture_output=True, text=True, timeout=10)
            return {"formatted": r.stdout if r.returncode == 0 else code,
                    "error": r.stderr.strip() or None, "tool": "deno fmt"}
        return None

    def get_lsp_command(self) -> list | None:
        if shutil.which("typescript-language-server"):
            return ["typescript-language-server", "--stdio"]
        if shutil.which("tsserver"):
            return ["tsserver"]
        return None

    def get_run_command(self, path: str) -> list | None:
        if shutil.which("deno"):
            return ["deno", "run", path]
        if shutil.which("ts-node"):
            return ["ts-node", path]
        return None

    def get_node_types(self) -> dict:
        return {
            "interface": {"n": "Interface", "c": "#1a2a3a"},
            "decorator": {"n": "Decorator", "c": "#2a1a3a"},
        }


register(TypeScriptPlugin())
```

把這個檔案放入 `pyflow/plugins/`，TypeScript 支援就自動啟用。

---

## 安裝插件

```bash
# 1. 把插件檔案放入 plugins 目錄
cp my_plugin.py pyflow/plugins/lang_mylang.py

# 2. 確認命名規則：必須以 lang_ 開頭
ls pyflow/plugins/
# lang_python.py  lang_go.py  lang_rust.py  lang_c.py  lang_cpp.py  lang_mylang.py

# 3. 重啟 PyFlow（插件在啟動時自動載入）
python pyflow/app.py

# 4. 確認已載入
curl http://localhost:5000/api/languages
# 應該看到你的語言在列表中
```

---

## 測試插件

```python
# test_my_plugin.py
import sys
sys.path.insert(0, 'pyflow')

from plugins.lang_mylang import MyPlugin

plugin = MyPlugin()

# 測試 parse
result = plugin.parse("""
def main():
    x = 1
    return x
""", "test.py")

assert len(result['flow']) > 0, "flow 不能是空的"
assert result['error'] is None, f"解析錯誤：{result['error']}"

# 測試節點類型
for node in result['flow']:
    assert 'id'    in node, "每個節點必須有 id"
    assert 'type'  in node, "每個節點必須有 type"
    assert 'label' in node, "每個節點必須有 label"
    assert 'line'  in node, "每個節點必須有 line"

print("✅ 插件測試通過！")
```

---

## 插件 API 版本

| 版本 | 說明 |
|------|------|
| 1.0  | 初始版本：parse + 選填方法 |

*規範版本 v1.0 — PyFlow IDE Language Plugin System*
