#!/usr/bin/env bash
# PyFlow IDE — macOS / Linux 啟動腳本
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYFLOW_DIR="$SCRIPT_DIR/pyflow"
VENV_DIR="$SCRIPT_DIR/.pyflow-venv"
PYTHON="${PYTHON:-python3}"
PORT="${PORT:-5000}"

# ── 顏色 ──
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RESET='\033[0m'

echo -e "${GREEN}⬡ PyFlow IDE${RESET}"

# ── 確認 Python ──
if ! command -v "$PYTHON" &>/dev/null; then
  echo "❌ 找不到 Python 3，請先安裝：https://python.org"
  exit 1
fi

PY_VER=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo -e "  Python $PY_VER"

# ── 建立虛擬環境（若不存在）──
if [ ! -d "$VENV_DIR" ]; then
  echo -e "  ${YELLOW}首次執行，建立虛擬環境…${RESET}"
  "$PYTHON" -m venv "$VENV_DIR"
fi

# ── 啟動虛擬環境 ──
source "$VENV_DIR/bin/activate"

# ── 安裝/更新依賴 ──
pip install -q -r "$PYFLOW_DIR/requirements.txt" 2>/dev/null || {
  echo "  安裝依賴..."
  pip install -r "$PYFLOW_DIR/requirements.txt"
}

# ── 啟動 ──
echo -e "  ${GREEN}啟動 http://localhost:$PORT${RESET}"
echo "  Ctrl+C 停止"

# 嘗試開啟瀏覽器
if command -v open &>/dev/null; then
  (sleep 1.5 && open "http://localhost:$PORT") &
elif command -v xdg-open &>/dev/null; then
  (sleep 1.5 && xdg-open "http://localhost:$PORT") &
fi

cd "$PYFLOW_DIR"
exec python app.py --port "$PORT"
