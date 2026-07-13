@echo off
:: PyFlow IDE — Windows Build Script
title PyFlow IDE Build

echo =====================================
echo   PyFlow IDE - Windows Build Script
echo =====================================
echo.

:: Check Python
python --version > nul 2>&1 || (
  echo ERROR: Python not found. Please install Python 3.8+
  pause & exit /b 1
)

:: Check Node.js
node --version > nul 2>&1 || (
  echo ERROR: Node.js not found. Please install Node.js 18+
  pause & exit /b 1
)

echo [1/4] Installing Python dependencies...
pip install -r pyflow\requirements.txt -q
pip install pyinstaller -q

echo [2/4] Bundling Python backend...
python -m PyInstaller pyflow.spec --distpath dist-server --clean --noconfirm

echo [3/4] Installing Node.js dependencies...
npm install --silent

echo [4/4] Building installer...
npm run dist:win

echo.
echo Build complete! Check dist\ folder.
dir dist\*.exe
pause
