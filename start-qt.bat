@echo off
setlocal
cd /d "%~dp0"
python pyflow\qt_app.py --folder "%~dp0pyflow"
if errorlevel 1 (
  echo.
  echo PyFlow Qt failed to start.
  echo If PySide6 is missing, run:
  echo   python -m pip install PySide6
  echo.
  pause
)
