# PyFlow IDE — 宣傳文案包

---

## 🐦 Twitter / X

### 主貼文（展示型）
```
我做了一個 IDE，讓你的程式碼「看得見」⬡

右側即時顯示流程圖 → 游標移動節點高亮 → 直接在圖上改程式碼

支援 10 種語言，內建 AI 助手、執行軌跡追蹤

完全免費開源 👇
https://github.com/Ryan-2013/pyflow-ide
```

### 延伸串文（Thread）
```
🧵 1/ 傳統 IDE 的問題：
你只能「讀」程式碼，很難快速理解一個陌生專案的結構

PyFlow 的做法：打字的同時，右邊即時生成互動式流程圖

2/ 不只是靜態圖：
- 游標在函式裡 → 對應節點橙色高亮
- 雙擊節點 → 進入函式內部看細節
- 右鍵節點 → 直接重新命名、刪除、新增參數

3/ 執行軌跡（最酷的功能）：
跑一次程式 → 流程圖上高亮「實際執行過的路徑」
每個函式顯示被呼叫幾次、花了幾毫秒

Debug 的效率直接翻倍

4/ 技術棧：
- 後端：Flask + Socket.IO（Python）
- 前端：Monaco Editor + SVG
- 10 種語言插件系統（可熱重載）
- 完全開源 MIT

5/ 有趣的是——這整個專案是我和 @AnthropicAI 的 Claude
在一次對話裡完成的

19,810 行程式碼 / 52 個檔案 / 26 個 API 路由

人機協作的邊界到底在哪裡？🤔

👉 https://github.com/Ryan-2013/pyflow-ide
```

---

## 📱 Reddit

### r/programming
```
標題：I built an IDE that shows your code as a real-time interactive flow diagram

Body:
Hey r/programming,

I've been working on PyFlow IDE — an open-source code editor that visualizes your code as an interactive flow diagram in real-time as you type.

The key differentiator from VS Code/Zed: you can **see your code's execution flow** while editing it.

Features:
- Real-time bidirectional sync: code changes ↔ diagram updates instantly
- Cursor sync: moving your cursor highlights the corresponding node
- **Execution tracing**: run your code once → the diagram highlights which paths were actually executed, with call counts and timing
- Bidirectional editing: double-click a node to rename it, right-click to add/delete functions
- 10 language plugins (Python, Go, Rust, JS, TS, Java, C, C++, Shell, Jupyter)
- Full LSP integration with one-click install wizard
- Claude AI assistant with code context awareness
- Built on Monaco Editor (same as VS Code)

The execution tracing is my favorite feature — it turns debugging from "reading" to "seeing".

GitHub: https://github.com/Ryan-2013/pyflow-ide

Happy to answer any questions about the architecture or specific features!
```

### r/Python
```
標題：PyFlow — A Python IDE that turns your code into a live flow diagram

I built an open-source IDE specifically designed for Python developers who want to **understand code visually**.

When you write Python, the right panel shows a real-time flow diagram of your code. But unlike static visualizers, it's interactive:

- Move your cursor into a function → that function's node highlights in the diagram
- **Execute your script** → the diagram overlays which paths were actually run (using sys.settrace())
- Click on the diagram to jump to the code
- One-click pylsp installation from the setup wizard

It also supports Go, Rust, TypeScript, Java, C/C++, Shell, and Jupyter notebooks.

Python test results: 100% accuracy on 1,000 stdlib files at 3.6ms/file.

https://github.com/Ryan-2013/pyflow-ide

(MIT licensed, completely free)
```

### r/SideProject
```
標題：After months of building, I launched an open-source code flow visualization IDE

Built entirely in collaboration with Claude AI — which itself is kind of meta.

The project: https://github.com/Ryan-2013/pyflow-ide

What it does: shows your code as an interactive, real-time flow diagram while you're editing it. The diagram and editor stay in sync — your cursor moves, a node highlights.

Stats:
- 19,810 lines of code
- 10 language plugins
- 52 files
- 0 dollars spent on development

The most interesting part: it was built in a single multi-hour conversation with Claude (Anthropic's AI). I provided the direction and design decisions; Claude wrote the code. Every feature was tested and iterated on in real-time.

This changes how I think about what "building something" means.

Would love your feedback on both the tool itself and the human-AI development approach!
```

### r/coolgithubprojects
```
標題：PyFlow IDE — Your code, but as a live flow diagram

https://github.com/Ryan-2013/pyflow-ide

Real-time bidirectional sync between Monaco editor and interactive flow diagram. 
Supports 10 languages. Built with Flask + Socket.IO.

The execution tracing feature is wild — run your code and watch the actual execution path light up on the diagram.
```

---

## 🟠 Hacker News

### Show HN
```
標題：Show HN: PyFlow IDE – Real-time code flow visualization while you edit

URL: https://github.com/Ryan-2013/pyflow-ide

Body:
PyFlow is an open-source IDE built on Monaco Editor that shows your code as an interactive flow diagram in real-time.

The core idea: most developers spend significant time understanding unfamiliar codebases. Static documentation helps, but what if the IDE showed you the execution structure as you moved your cursor?

Key features:
- Bidirectional sync: edit code → diagram updates; click diagram → jumps to code
- Cursor tracking: moving into a function highlights its flow node
- Execution tracing: uses sys.settrace() to overlay which code paths actually ran
- 10 language plugins via a hot-reloadable plugin system
- LSP integration (pylsp, gopls, rust-analyzer, clangd, typescript-language-server)
- One-click LSP installation wizard
- Built-in Claude AI assistant (needs your own API key)

Technical stack: Python/Flask/Socket.IO backend, Monaco Editor frontend, SVG for diagrams, Web Worker for call graph force simulation.

The project was built through human-AI collaboration — I provided product direction and Claude (Anthropic) wrote the implementation. ~20k lines in a single conversation. Interesting exercise in AI-assisted development at scale.

Python parser accuracy: 100% on 1,000 stdlib files, ~3.6ms/file.

Would love feedback on both the visualization approach and the architecture decisions.
```

---

## 💼 LinkedIn

```
🚀 剛開源了一個做了很久的 side project

PyFlow IDE — 讓程式碼「看得見」的開發環境

傳統 IDE 你只能讀程式碼。PyFlow 讓你在寫程式的同時，右側即時顯示互動式流程圖。

最特別的功能是「執行軌跡視覺化」：
執行一次程式 → 流程圖自動高亮實際跑過的路徑 + 每個函式的呼叫次數
把 debugging 從「猜」變成「看」

技術棧：
✅ Python / Flask / Socket.IO
✅ Monaco Editor（同 VS Code）
✅ 10 種語言支援
✅ LSP 整合 + 一鍵安裝
✅ Claude AI 助手

有趣的是——這個專案是我和 Claude AI 在一次對話裡協作完成的
19,810 行程式碼，52 個檔案，全部在這次對話裡產出

這讓我重新思考：AI 時代，「建構一個產品」的定義是什麼？

完全開源 MIT，歡迎 Star ⭐

🔗 https://github.com/Ryan-2013/pyflow-ide

#OpenSource #Developer #AI #Python #IDE #SideProject
```

---

## 📝 Dev.to 文章標題建議

1. `I built a full-featured IDE in one conversation with Claude — here's how`
2. `PyFlow: See your Python code as a live flow diagram while you type`
3. `From 0 to 20k lines: Human-AI pair programming at scale`
4. `How we visualize code execution in real-time (open source)`

---

## 🎯 最佳發文時機（UTC+8 台灣時間）

| 平台 | 最佳時間 |
|------|----------|
| Twitter/X | 週一到週四 早上 9-11 點 |
| Reddit | 週二到週四 晚上 9-11 點（美國時間） |
| Hacker News | 週一到週五 早上 8-9 點（美國東部） |
| LinkedIn | 週二、週三 早上 9-10 點 |

---

## 📊 發文策略

1. **先發 HN**（最大開發者流量）→ 有討論的話截圖分享到 Twitter
2. **Reddit 多個 subreddit** 分散發文（不要同一天）
3. **Twitter 串文**比單貼更容易傳播
4. **LinkedIn** 用中文，台灣開發者社群

---

## 🏷️ Hashtags

```
#OpenSource #IDE #Python #JavaScript #TypeScript #Go #Rust
#Developer #CodeVisualization #AIAssisted #SideProject #GitHub
```
