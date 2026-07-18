# PyFlow IDE

PyFlow IDE 是一套純 PyQt 桌面程式碼編輯器，採用 Claude 風格深色介面，重點是讓程式碼結構與呼叫關係能直接視覺化。

## Windows 下載

1. 前往 [GitHub Releases](https://github.com/Ryan-2013/pyflow-ide/releases)。
2. 下載最新的 `PyFlow-IDE-Windows-v*.zip`。
3. 解壓縮整個 ZIP。
4. 雙擊資料夾中的 `PyFlow IDE.exe`。

Windows 套件採資料夾型封裝，執行時不需要 Electron 或本機 Web 伺服器，也不會把整個應用程式解壓到記憶體。請勿只把 EXE 單獨移出資料夾。

## 目前功能

- 中文與 English 介面
- 檔案／資料夾建立、重新命名、刪除與搜尋
- 行號、語法高亮、自動縮排、程式碼補全與函式簽名
- Python、Rust、Go、C、C++、ZyenLang 呼叫關係節點圖
- 節點搜尋、呼叫者／被呼叫者資訊與前往程式碼
- 可停止的 Python 執行程序
- 內建互動式 PowerShell，可使用 `Ctrl+`` 開啟或關閉
- 全介面快速縮放

執行 Python 檔案需要電腦已安裝 Python 3。封裝版會從 `PATH` 自動尋找 Python，也可用 `PYFLOW_PYTHON` 環境變數指定 `python.exe`。

## 從原始碼啟動

需要 Python 3.10 或更新版本：

```powershell
python -m pip install -r pyflow/requirements.txt
python pyflow/qt_app.py
```

Windows 也可直接執行 `start-qt.bat`。

## 建置 Windows 套件

```powershell
.\build.bat
```

輸出檔案位於 `dist/PyFlow-IDE-Windows-v1.1.0.zip`。

## 驗證

```powershell
python pyflow/qt_app.py --self-test
python -m py_compile pyflow/qt_app.py pyflow/qt_services.py pyflow/qt_languages.py pyflow/qt_zyenlang.py
```

## 授權

MIT
