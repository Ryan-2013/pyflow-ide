# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import sys

ROOT = Path(SPECPATH)
ICON = ROOT / "assets" / (
    "icon.ico" if sys.platform == "win32" else "icon.icns"
)

a = Analysis(
    [str(ROOT / "pyflow" / "qt_app.py")],
    pathex=[str(ROOT / "pyflow")],
    binaries=[],
    datas=[
        (str(ROOT / "pyflow" / "samples"), "samples"),
    ],
    hiddenimports=[
        "qt_i18n",
        "qt_languages",
        "qt_services",
        "qt_zyenlang",
        "core.ast_parser",
        "core.formatter",
        "core.go_parser",
        "core.rust_parser",
        "core.search",
        "core.symbols",
        "plugins.lang_c",
        "plugins.lang_cpp",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "anthropic",
        "eventlet",
        "flask",
        "flask_socketio",
        "matplotlib",
        "numpy",
        "scipy",
        "tkinter",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PyFlow IDE",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(ICON),
)

app_files = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="PyFlow IDE",
)

if sys.platform == "darwin":
    app = BUNDLE(
        app_files,
        name="PyFlow IDE.app",
        icon=str(ICON),
        bundle_identifier="com.pyflow.ide",
        info_plist={
            "CFBundleShortVersionString": "1.1.0",
            "CFBundleVersion": "1.1.0",
            "NSHighResolutionCapable": True,
        },
    )
