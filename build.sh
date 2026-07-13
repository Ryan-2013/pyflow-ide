#!/usr/bin/env bash
# PyFlow IDE — 本地建置腳本（macOS / Linux）
set -euo pipefail

echo "⬡ PyFlow IDE — Build Script"
echo "=============================="

# 確認工具
command -v python3 >/dev/null || { echo "❌ 需要 Python 3"; exit 1; }
command -v node    >/dev/null || { echo "❌ 需要 Node.js"; exit 1; }
command -v npm     >/dev/null || { echo "❌ 需要 npm"; exit 1; }

echo "  Python:  $(python3 --version)"
echo "  Node.js: $(node --version)"

# 安裝 Python 依賴
echo ""
echo "📦 安裝 Python 依賴..."
python3 -m pip install -r pyflow/requirements.txt -q
python3 -m pip install pyinstaller -q

# 打包 Python 後端
echo ""
echo "🔨 打包 Python 後端（PyInstaller）..."
python3 -m PyInstaller pyflow.spec --distpath dist-server --clean --noconfirm
echo "  ✅ 後端打包完成：$(ls -la dist-server/pyflow-server* 2>/dev/null | head -1)"

# 安裝 Node 依賴
echo ""
echo "📦 安裝 Node.js 依賴..."
npm install --silent

# 建立 Electron 安裝包
echo ""
echo "🔨 建立安裝包..."
npm run dist

echo ""
echo "✅ 建置完成！"
echo "   輸出目錄：dist/"
ls -la dist/*.{dmg,AppImage,deb} 2>/dev/null || ls -la dist/ 2>/dev/null
