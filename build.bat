@echo off
setlocal
cd /d "%~dp0"
set "VERSION=1.1.1"

echo =====================================
echo   PyFlow IDE - PyQt Windows Build
echo =====================================
echo.

python --version >nul 2>&1 || (
  echo ERROR: Python not found. Please install Python 3.10 or newer.
  pause
  exit /b 1
)

echo [1/3] Installing build dependencies...
python -m pip install -r pyflow\requirements.txt pyinstaller==6.3.0 || exit /b 1

echo [2/3] Building desktop application...
python -m PyInstaller pyflow.spec --distpath dist --workpath build\pyinstaller --clean --noconfirm || exit /b 1

echo [3/3] Creating release archive...
if exist "dist\PyFlow-IDE-Windows-v%VERSION%.zip" del /q "dist\PyFlow-IDE-Windows-v%VERSION%.zip"
powershell -NoProfile -Command "Compress-Archive -Path 'dist\PyFlow IDE\*' -DestinationPath 'dist\PyFlow-IDE-Windows-v%VERSION%.zip' -CompressionLevel Optimal" || exit /b 1

echo.
echo Build complete:
echo   dist\PyFlow-IDE-Windows-v%VERSION%.zip
echo.
pause
