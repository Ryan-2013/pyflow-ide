#!/usr/bin/env bash
# PyFlow IDE — 完整安裝腳本
set -euo pipefail

echo "⬡ PyFlow IDE 安裝程式"
echo "========================="

# 確認系統需求
command -v python3 >/dev/null 2>&1 || { echo "❌ 需要 Python 3.8+"; exit 1; }
PY_VER=$(python3 -c "import sys; v=sys.version_info; print(f'{v.major}.{v.minor}')")
echo "  Python $PY_VER ✓"

command -v node >/dev/null 2>&1 && echo "  Node.js $(node --version) ✓" || echo "  ⚠ Node.js 未安裝（可選）"

# 建立虛擬環境
VENV=".pyflow-venv"
python3 -m venv "$VENV"
source "$VENV/bin/activate"
pip install -q --upgrade pip

# 安裝依賴
echo "  安裝 Python 依賴..."
pip install -q -r pyflow/requirements.txt

# 安裝 Node.js 依賴（Electron 用）
if command -v npm >/dev/null 2>&1 && [ -f package.json ]; then
  echo "  安裝 Electron 依賴..."
  npm install --quiet
fi

# 加上執行權限
chmod +x start.sh

echo ""
echo "✅ 安裝完成！"
echo ""
echo "  啟動方式："
echo "    ./start.sh          # 瀏覽器模式（推薦）"
echo "    npm start           # Electron 模式（需要 Node.js）"
echo ""
echo "  API Key 設定（AI 助手功能）："
echo "    export ANTHROPIC_API_KEY=sk-ant-..."
