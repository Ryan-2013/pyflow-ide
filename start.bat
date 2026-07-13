@echo off
:: PyFlow IDE — Windows 啟動腳本
setlocal EnableDelayedExpansion

set SCRIPT_DIR=%~dp0
set PYFLOW_DIR=%SCRIPT_DIR%pyflow
set VENV_DIR=%SCRIPT_DIR%.pyflow-venv
set PORT=5000

echo ⬡ PyFlow IDE

:: 確認 Python
python --version >nul 2>&1
if errorlevel 1 (
  echo ❌ 找不到 Python，請安裝：https://python.org
  pause
  exit /b 1
)

:: 建立虛擬環境
if not exist "%VENV_DIR%\Scripts\activate.bat" (
  echo   首次執行，建立虛擬環境...
  python -m venv "%VENV_DIR%"
)

:: 啟動虛擬環境
call "%VENV_DIR%\Scripts\activate.bat"

:: 安裝依賴
pip install -q -r "%PYFLOW_DIR%\requirements.txt"

:: 開啟瀏覽器
start "" "http://localhost:%PORT%"

:: 啟動
echo   啟動 http://localhost:%PORT%
cd /d "%PYFLOW_DIR%"
python app.py --port %PORT%
pause
