# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Orphanaut (Windows folder build + macOS .app bundle)."""

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

src = Path(SPECPATH)
sys.path.insert(0, str(src / "src"))
from orphanaut import __version__  # noqa: E402

datas = []
if sys.platform == "win32":
    datas.append((str(src / "WINDOWS-STUDENTS.txt"), "."))
# Google API discovery documents are loaded from package data at runtime.
datas += collect_data_files("googleapiclient")
datas += collect_data_files("botocore")

hiddenimports = (
    collect_submodules("orphanaut")
    + collect_submodules("azure.identity")
    + collect_submodules("azure.mgmt.compute")
    + collect_submodules("azure.mgmt.network")
    + collect_submodules("azure.mgmt.storage")
    + collect_submodules("msal")
    + collect_submodules("google.auth")
    + collect_submodules("google.oauth2")
    + collect_submodules("googleapiclient")
    + ["boto3", "botocore", "requests"]
)

a = Analysis(
    [str(src / "src" / "orphanaut" / "main.py")],
    pathex=[str(src / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "pytest"],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

icon = str(src / "assets" / ("icon.ico" if sys.platform == "win32" else "icon.icns"))

# Folder (onedir) builds on every platform: they start fast and antivirus / SmartScreen
# trust them far more than one-file apps that unpack to TEMP.
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Orphanaut",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Orphanaut",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Orphanaut.app",
        icon=icon,
        bundle_identifier="io.github.rajinikanthvadla-ai.orphanaut",
        version=__version__,
        info_plist={
            "CFBundleName": "Orphanaut",
            "CFBundleDisplayName": "Orphanaut",
            "CFBundleShortVersionString": __version__,
            "CFBundleVersion": __version__,
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
            "NSHumanReadableCopyright": "MIT License — made by Rajinikanth Vadla",
        },
    )
