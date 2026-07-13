# ⬡ PyFlow IDE

> **程式碼流程可視化 IDE** — 讓你的程式碼「看得見」

PyFlow 是一個獨特的 IDE：寫程式時右側即時顯示**互動式流程圖**，支援 10 種語言、LSP 補全、Claude AI 助手、執行軌跡視覺化，以及雙向節點編程（直接在圖上修改程式碼）。

## ✨ 核心特色

- **即時流程圖** — 游標移動，對應節點高亮；雙向同步，節點即程式碼
- **執行軌跡** — 跑一次程式，流程圖高亮實際執行路徑 + 呼叫次數
- **AI 助手** — Claude API 整合，上下文感知（知道你的函式在幹嘛）
- **10 種語言** — Python / Go / Rust / JS / TS / Java / C / C++ / Shell / Jupyter
- **完整 IDE** — LSP、偵錯器、Git、搜尋、呼叫圖、Profiler、Coverage

## 🚀 快速開始

```bash
# macOS / Linux
git clone https://github.com/YOUR_USERNAME/pyflow-ide
cd pyflow-ide
./start.sh

# Windows
start.bat
```

啟動後點 **⚙** 按鈕一鍵安裝 LSP。

## ⚙️ 安裝 LSP

```bash
pip install python-lsp-server[all]           # Python
go install golang.org/x/tools/gopls@latest   # Go  
rustup component add rust-analyzer            # Rust
npm install -g typescript-language-server     # TypeScript/JS
```

## 🏗️ 架構

```
pyflow/
├── app.py          # Flask + Socket.IO 後端
├── core/           # LSP、Git、Tracer、Search、Setup
├── plugins/        # 10 個語言插件（可熱重載）
└── static/index.html  # 完整前端（8,335 行）
```

**新增語言**：把 `lang_X.py` 放進 `plugins/`，自動載入。

## 📊 測試

- Python 1,000 stdlib 檔案：**100% 準確率**，3.6ms/file
- 26 個 API 路由：**全部通過**

## ⌨️ 快捷鍵

| | |
|--|--|
| `Ctrl+P` | 模糊搜尋檔案 |
| `Ctrl+Shift+1/2/3` | 程式碼 / 並排 / 流程圖 |
| `Ctrl+Shift+T` | 恢復關閉的標籤 |
| `雙擊節點` | 重新命名函式 |
| `右鍵節點` | 新增/刪除/插入呼叫 |
| `拖曳 ● 綠點` | 建立函式呼叫關係 |


## 👥 開發者

<table>
  <tr>
    <td align="center">
      <a href="https://github.com/Ryan-2013">
        <img src="https://github.com/Ryan-2013.png" width="64"/><br/>
        <b>Ryan</b>
      </a><br/>
      <sub>創始人 · 產品設計</sub>
    </td>
    <td align="center">
      <a href="https://anthropic.com">
        <img src="https://avatars.githubusercontent.com/u/76263028?s=64" width="64"/><br/>
        <b>Claude</b>
      </a><br/>
      <sub>AI 協同開發 · 全端實作</sub>
    </td>
  </tr>
</table>

> 本專案由 Ryan 主導方向，Claude（Anthropic）負責全端實作，在一次對話中完成所有 19,810 行程式碼。

## 📄 授權

MIT License
