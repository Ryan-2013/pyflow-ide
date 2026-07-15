# -*- mode: python ; coding: utf-8 -*-
# PyFlow IDE — PyInstaller 打包設定（修正版）
# 將 Python 後端打包成單一執行檔

from PyInstaller.utils.hooks import collect_submodules
import sys

a = Analysis(
    ['pyflow/app.py'],
    pathex=['pyflow'],          # ← 讓 core / plugins 這些套件被當成模組找得到
    binaries=[],
    datas=[
        ('pyflow/static',   'static'),
        ('pyflow/themes',   'themes'),
        ('pyflow/samples',  'samples'),
        ('pyflow/plugins',  'plugins'),
        ('pyflow/core',     'core'),
    ],
    hiddenimports=[
        # Flask 生態
        'flask', 'flask_socketio', 'werkzeug', 'jinja2', 'click',
        # ★ 核心修正：app.py 用 async_mode='threading'
        #   必須明確帶入 threading driver + simple_websocket，
        #   否則 exe 啟動時會噴 "Invalid async_mode specified"。
        'engineio.async_drivers.threading',
        'simple_websocket',
        'engineio', 'socketio',
        # 其他依賴
        'chardet', 'pkg_resources', 'bidict', 'six',
        # core / plugins 全部子模組自動收集（app.py 幾乎全都會用到）
        *collect_submodules('core'),
        *collect_submodules('plugins'),
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy', 'numpy', 'PIL',
              'PyQt5', 'wx', 'gi', 'eventlet'],   # ← 不用 eventlet，排除以縮小體積
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='pyflow-server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico' if sys.platform == 'win32' else (
         'assets/icon.icns' if sys.platform == 'darwin' else 'assets/icon.png'
    ),
)

app = BUNDLE(
    exe,
    name='PyFlow IDE.app',
    icon='assets/icon.icns',
    bundle_identifier='com.pyflow.ide',
    info_plist={
        'CFBundleShortVersionString': '1.0.6',
        'CFBundleVersion': '1.0.6',
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': '11.0',
    },
)
