# PyFlow IDE 主題規範 v1.0
**Theme Specification Standard**

---

## 目錄

1. [概述](#概述)
2. [主題檔案格式](#主題檔案格式)
3. [色彩代幣（CSS Variables）](#色彩代幣)
4. [流程圖節點色彩](#流程圖節點色彩)
5. [Monaco 編輯器主題](#monaco-編輯器主題)
6. [終端機色彩](#終端機色彩)
7. [建立新主題](#建立新主題)
8. [工具使用方式](#工具使用方式)

---

## 概述

PyFlow IDE 的主題系統基於 **JSON 設定檔** 驅動。

```
pyflow/themes/
├── THEME_SPEC.md       ← 本規範文件
├── dark.json           ← 預設深色主題（參考用，請勿修改）
├── claude.json         ← Claude 風格主題
├── steam.json          ← Steam OS 主題
├── switch2.json        ← Nintendo Switch 2 主題
└── my_custom.json      ← 自訂主題（範例）
```

**規則：**
- 預設深色主題 (`dark`) 永遠存在於程式碼中，**不需要也不應該透過主題檔修改**
- 所有自訂主題透過 JSON 檔定義，放入 `themes/` 目錄即自動載入
- 主題 `id` 必須唯一，不可使用 `dark`

---

## 主題檔案格式

完整 JSON 結構：

```json
{
  "$schema": "https://pyflow-ide.dev/theme-schema/v1",
  "id":          "my-theme",
  "name":        "我的主題",
  "description": "一個自訂的 PyFlow 主題",
  "author":      "作者名稱",
  "version":     "1.0.0",
  "type":        "dark",
  "preview":     "🎨",
  "font":        "system-ui",

  "colors":  { ... },
  "nodes":   { ... },
  "editor":  { ... },
  "terminal": { ... }
}
```

### 欄位說明

| 欄位 | 類型 | 必填 | 說明 |
|------|------|------|------|
| `id` | `string` | ✅ | 主題識別碼，唯一，英數字+連字號，不可為 `dark` |
| `name` | `string` | ✅ | 顯示名稱（中英皆可） |
| `description` | `string` | — | 主題說明 |
| `author` | `string` | — | 作者 |
| `version` | `string` | — | 版本號 |
| `type` | `"dark"` \| `"light"` | ✅ | 底色模式，影響 Monaco 預設繼承主題 |
| `preview` | `string` | — | 設定面板預覽 emoji 或縮圖 URL |
| `font` | `string` | — | 主要字體族，覆蓋 `--sans` |

---

## 色彩代幣

### 背景層次（Background）

```json
"colors": {
  "bg":  "#000000",   // 最底層背景（主視窗、對話區）
  "bg2": "#080808",   // 第二層（終端機面板、分析面板）
  "bg3": "#111111",   // 第三層（卡片、浮動面板）
  "bg4": "#161616",   // 第四層（懸停狀態）
  "bg5": "#1a1a1a"    // 第五層（點選/啟用狀態）
}
```

**視覺層次規則：** `bg` < `bg2` < `bg3` < `bg4` < `bg5`
（深色主題越來越亮，淺色主題越來越深）

---

### 邊框（Border）

```json
"colors": {
  "bd":  "#141414",   // 主邊框（分隔線、面板邊緣）
  "bd2": "#1e1e1e",   // 次邊框（輸入框、下拉選單）
  "bd3": "#2a2a2a"    // 強邊框（選中狀態、焦點環）
}
```

---

### 文字（Text）

```json
"colors": {
  "tx":  "#c8c8c8",   // 主要文字（正文、標籤）
  "tx2": "#3a3a3a",   // 次要文字（說明、提示、未啟用狀態）
  "tx3": "#e0e0e0",   // 強調文字（標題、選中項目）
  "tx4": "#555555"    // 弱化文字（佔位符、禁用狀態）
}
```

---

### 強調色（Accent）

```json
"colors": {
  "acc":  "#3b82f6",  // 主要強調色（連結、主按鈕、選中指示器）
  "acc2": "#1d4ed8",  // 深強調色（按鈕懸停、點選狀態）
  "acc3": "#60a5fa",  // 淺強調色（文字連結、圖示）
  "sel":  "#0f1e35",  // 選中背景（選中行、高亮區域）
  "ya":   "#ffd43b"   // 黃色高亮（步驟序號、搜尋結果標記）
}
```

**規則：**
- `acc2` 應比 `acc` 更深（深色主題）或更淺（淺色主題）
- `acc3` 應比 `acc` 更亮
- `sel` 是 `acc` 的透明度降低版本

---

### 完整 colors 參考對照

| 代幣 | 深色預設 | 使用位置 |
|------|----------|----------|
| `bg` | `#000000` | 主視窗背景 |
| `bg2` | `#080808` | 終端機、輸出面板 |
| `bg3` | `#111111` | 上下文選單、設定面板 |
| `bg4` | `#161616` | Tab 懸停、工具列按鈕懸停 |
| `bg5` | `#1a1a1a` | 深色分隔、底部面板 |
| `bd` | `#141414` | 主要分隔線 |
| `bd2` | `#1e1e1e` | 輸入框、卡片邊框 |
| `bd3` | `#2a2a2a` | 焦點邊框、強調線 |
| `tx` | `#c8c8c8` | 正文、檔案名稱 |
| `tx2` | `#3a3a3a` | 說明文字、未選中 Tab |
| `tx3` | `#e0e0e0` | 標題、選中狀態 |
| `tx4` | `#555555` | 佔位符、禁用 |
| `acc` | `#3b82f6` | 主按鈕、鏈結 |
| `acc2` | `#1d4ed8` | 按鈕懸停 |
| `acc3` | `#60a5fa` | 圖示色、文字鏈結 |
| `sel` | `#0f1e35` | 選中行背景 |
| `ya` | `#ffd43b` | 步驟序號徽章 |

---

## 流程圖節點色彩

### nodes 格式

```json
"nodes": {
  "import": {
    "bg":     "#1e3a5f",  // 節點背景填充色
    "text":   "#93c5fd",  // 節點主標籤文字色
    "header": "#1e3a5f"   // 頂部色條顏色（可與 bg 相同或不同）
  },
  ...
}
```

**所有節點類型（必須全部定義）：**

| 類型 | 語義 | 深色預設 bg |
|------|------|------------|
| `import` | 匯入語句（import/use/from） | `#1e3a5f` |
| `assign` | 賦值（let/x=） | `#1a3a2a` |
| `call` | 函式呼叫 | `#2a1a3a` |
| `goroutine` | Go goroutine / Rust spawn | `#1a3a1a` |
| `channel` | Go channel 操作 | `#0a2a2a` |
| `match` | Rust match 表達式 | `#3a2a1a` |
| `condition` | if/else | `#3a2a1a` |
| `loop` | for/while/loop | `#1a2a3a` |
| `context` | defer/context manager | `#2a2a0a` |
| `exception` | try/except/raise | `#3a1a1a` |
| `flow_ctrl` | return/break/continue/? | `#2a1a2a` |
| `function` | 函式定義（右欄） | `#1e2a3a` |
| `class` | 類別/struct 定義（右欄） | `#2a1e2a` |
| `unsafe_block` | Rust unsafe 區塊 | `#3a0a0a` |
| `error_check` | Go if err != nil | `#3a1a0a` |
| `defer` | Go defer | `#1a1a3a` |
| `select` | Go select | `#2a1a0a` |
| `other` | 其他/未識別語句 | `#0a0a0a` |

**深色主題設計指引（bg 選色）：**
- 深色 bg：`#0a0a0a` 至 `#3a3a3a`
- 每種類型用不同色相區分語義
- `header` 可與 `bg` 相同，或稍微加亮 10%

**淺色主題設計指引（bg 選色）：**
- 淺色 bg：非常淡的色調（`#EFF6FF`、`#F0FDF4` 等）
- `text` 應深色，與 bg 形成高對比
- `header` 比 `bg` 稍深（如 `#DBEAFE` vs `#EFF6FF`）

---

## Monaco 編輯器主題

```json
"editor": {
  "base": "vs-dark",
  "inherit": true,

  "rules": [
    { "token": "",          "foreground": "c8c8c8", "background": "000000" },
    { "token": "comment",   "foreground": "555555", "fontStyle": "italic" },
    { "token": "string",    "foreground": "86efac" },
    { "token": "number",    "foreground": "fbbf24" },
    { "token": "keyword",   "foreground": "818cf8", "fontStyle": "bold" },
    { "token": "type",      "foreground": "60a5fa" },
    { "token": "class",     "foreground": "60a5fa" },
    { "token": "function",  "foreground": "93c5fd" },
    { "token": "variable",  "foreground": "fca5a5" },
    { "token": "operator",  "foreground": "6b7280" },
    { "token": "delimiter", "foreground": "374151" },
    { "token": "tag",       "foreground": "fbbf24" },
    { "token": "attribute.name",  "foreground": "60a5fa" },
    { "token": "attribute.value", "foreground": "86efac" }
  ],

  "colors": {
    "editor.background":                    "#000000",
    "editor.foreground":                    "#c8c8c8",
    "editorLineNumber.foreground":          "#1a1a1a",
    "editorLineNumber.activeForeground":    "#ffd43b",
    "editor.lineHighlightBackground":       "#080808",
    "editor.selectionBackground":           "#1e3a5f",
    "editor.inactiveSelectionBackground":   "#0f1e35",
    "editorCursor.foreground":              "#c8c8c8",
    "editorWhitespace.foreground":          "#1a1a1a",
    "editorIndentGuide.background1":        "#111111",
    "editorIndentGuide.activeBackground1":  "#3b82f6",
    "editorBracketMatch.background":        "#1e3a5f",
    "editorBracketMatch.border":            "#3b82f6",
    "editor.findMatchBackground":           "#1e3a5f",
    "editor.findMatchHighlightBackground":  "#0f1e35",
    "editorWidget.background":              "#0a0a0a",
    "editorWidget.border":                  "#1e1e1e",
    "editorSuggestWidget.background":       "#0a0a0a",
    "editorSuggestWidget.border":           "#1e1e1e",
    "editorSuggestWidget.selectedBackground": "#0f1e35",
    "editorSuggestWidget.selectedForeground": "#60a5fa",
    "editorSuggestWidget.highlightForeground": "#ffd43b",
    "editorHoverWidget.background":         "#0a0a0a",
    "editorHoverWidget.border":             "#1e1e1e",
    "scrollbarSlider.background":           "#1e1e1e80",
    "scrollbarSlider.hoverBackground":      "#2e2e2e80",
    "minimap.background":                   "#000000",
    "editorGutter.background":              "#000000",
    "focusBorder":                          "#3b82f6",
    "list.hoverBackground":                 "#0f1e35",
    "list.activeSelectionBackground":       "#0f1e35",
    "list.activeSelectionForeground":       "#60a5fa"
  }
}
```

**重要說明：**
- `base` 決定繼承的預設主題：`"vs"` (淺色)、`"vs-dark"` (深色)、`"hc-black"` (高對比)
- `rules[].token` 代幣不需前綴 `#`
- `colors` 的值需要有前綴 `#`
- 若 `inherit: true`，未定義的代幣/顏色會繼承 base 的值

---

## 終端機色彩

基於 [xterm.js ThemeInterface](https://xtermjs.org/docs/api/terminal/interfaces/itheme/)：

```json
"terminal": {
  "background":         "#000000",
  "foreground":         "#c8c8c8",
  "cursor":             "#c8c8c8",
  "cursorAccent":       "#000000",
  "selectionBackground": "#1e3a5f",

  "black":         "#000000",
  "red":           "#cd3131",
  "green":         "#0dbc79",
  "yellow":        "#e5e510",
  "blue":          "#2472c8",
  "magenta":       "#bc3fbc",
  "cyan":          "#11a8cd",
  "white":         "#e5e5e5",

  "brightBlack":   "#666666",
  "brightRed":     "#f14c4c",
  "brightGreen":   "#23d18b",
  "brightYellow":  "#f5f543",
  "brightBlue":    "#3b8eea",
  "brightMagenta": "#d670d6",
  "brightCyan":    "#29b8db",
  "brightWhite":   "#e5e5e5"
}
```

---

## 建立新主題

### 步驟

1. 複製 `themes/dark.json`（或 `themes/example_custom.json`）
2. 修改 `id`、`name`、`type`
3. 調整 `colors`（建議先從這裡開始）
4. 調整 `nodes`（根據 `type` 選擇深色或淺色底）
5. 調整 `editor` 和 `terminal`（可選）
6. 執行建置工具驗證

### 最小可用主題（只改主色）

只需定義 `colors` 中的關鍵色：

```json
{
  "id": "rose-pine",
  "name": "Rosé Pine",
  "type": "dark",
  "preview": "🌹",

  "colors": {
    "bg":   "#191724",
    "bg2":  "#1f1d2e",
    "bg3":  "#26233a",
    "bg4":  "#312e44",
    "bg5":  "#403d52",
    "bd":   "#26233a",
    "bd2":  "#312e44",
    "bd3":  "#6e6a86",
    "tx":   "#e0def4",
    "tx2":  "#6e6a86",
    "tx3":  "#f7f3f0",
    "tx4":  "#403d52",
    "acc":  "#c4a7e7",
    "acc2": "#9b7dd3",
    "acc3": "#d4b9f9",
    "sel":  "#2a2739",
    "ya":   "#f6c177"
  }
}
```

若省略 `nodes`、`editor`、`terminal`，工具會自動依 `type` 和 `colors` 推導預設值。

---

## 工具使用方式

### build_theme.py — 將 JSON 編譯為可用的 CSS/JS

```bash
# 驗證主題格式
python tools/build_theme.py themes/my-theme.json --validate

# 產生 CSS 預覽（印在終端）
python tools/build_theme.py themes/my-theme.json --output css

# 產生 JS 物件（可直接貼入 index.html）
python tools/build_theme.py themes/my-theme.json --output js

# 產生完整報告（顏色對比度、可用性警告）
python tools/build_theme.py themes/my-theme.json --report

# 套用到專案（自動修改 app.py 和 index.html）
python tools/build_theme.py themes/my-theme.json --apply
```

### 色彩對比度規則（WCAG AA）

| 用途 | 最低對比度 |
|------|-----------|
| 主要文字 (`tx`) vs 背景 (`bg`) | 4.5:1 |
| 次要文字 (`tx2`) vs 背景 (`bg`) | 3:1 |
| 強調色 (`acc`) vs 背景 (`bg`) | 3:1 |
| 按鈕文字 vs 按鈕背景 | 4.5:1 |

---

## 主題繼承

主題可以繼承現有主題並只覆蓋部分設定：

```json
{
  "id": "dark-rose",
  "name": "Dark Rose",
  "extends": "dark",

  "colors": {
    "acc":  "#f43f5e",
    "acc2": "#e11d48",
    "acc3": "#fb7185",
    "sel":  "#2a0a12",
    "ya":   "#f43f5e"
  }
}
```

只需定義要覆蓋的部分，其餘繼承自 `extends` 指定的主題。

---

*規範版本 v1.0 — PyFlow IDE Theme System*
