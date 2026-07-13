# -*- mode: python ; coding: utf-8 -*-
# PyFlow IDE — PyInstaller 打包設定
# 將 Python 後端打包成單一執行檔

from PyInstaller.utils.hooks import collect_submodules, collect_data_files
import sys

# 收集 eventlet 所有子模組（Socket.IO 需要）
eventlet_hidden = collect_submodules('eventlet')
dns_hidden      = collect_submodules('dns')

a = Analysis(
    ['pyflow/app.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        # 靜態資源（前端 HTML/CSS/JS）
        ('pyflow/static',   'static'),
        ('pyflow/themes',   'themes'),
        ('pyflow/samples',  'samples'),
        ('pyflow/plugins',  'plugins'),
        ('pyflow/core',     'core'),
    ],
    hiddenimports=[
        # Flask 生態
        'flask', 'flask_socketio', 'werkzeug',
        'werkzeug.security', 'jinja2', 'click',
        # Socket.IO
        'eventlet', 'engineio', 'socketio',
        'engineio.async_drivers.eventlet',
        'socketio.async_drivers.eventlet',
        *eventlet_hidden,
        *dns_hidden,
        # 其他依賴
        'anthropic', 'chardet', 'pkg_resources',
        'bidict', 'six', 'greenlet',
        # PyFlow 插件（需要明確列出）
        'plugins', 'plugins.lang_python', 'plugins.lang_go',
        'plugins.lang_rust', 'plugins.lang_js_ts',
        'plugins.lang_java', 'plugins.lang_c',
        'plugins.lang_cpp', 'plugins.lang_shell',
        'plugins.lang_jupyter',
        'core.ast_parser', 'core.git_ops', 'core.lsp_client',
        'core.tracer', 'core.import_graph', 'core.search',
        'core.setup', 'core.plugin_watcher',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy', 'numpy', 'PIL',
              'PyQt5', 'wx', 'gi'],
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
    console=False,      # 不顯示黑色命令列視窗
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico' if sys.platform == 'win32' else (
         'assets/icon.icns' if sys.platform == 'darwin' else 'assets/icon.png'
    ),
)

# macOS .app bundle
app = BUNDLE(
    exe,
    name='PyFlow IDE.app',
    icon='assets/icon.icns',
    bundle_identifier='com.pyflow.ide',
    info_plist={
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleVersion': '1.0.0',
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': '11.0',
    },
)
