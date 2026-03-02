# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

ROOT = Path.cwd()
THEMES = ROOT / "themes"
ASSETS = ROOT / "assets"
STAGING = Path(os.environ["PULSEWAVE11_STAGING"]) if os.environ.get("PULSEWAVE11_STAGING") else None

datas = []
if THEMES.exists():
    datas.append((str(THEMES), "themes"))
if ASSETS.exists():
    datas.append((str(ASSETS), "assets"))

# Optional native binary created by Cython setup.
binaries = []
for pattern in ("pulsewave_11_native*.pyd", "pulsewave_11_native*.so", "pulsewave_11_native*.dylib"):
    for match in ROOT.glob(pattern):
        binaries.append((str(match), "."))

block_cipher = None
entry_script = ROOT / "pulsewave_11_cli.py"
analysis_paths = [str(ROOT)]
if STAGING is not None and STAGING.exists():
    entry_script = STAGING / "pulsewave_11_cli.py"
    analysis_paths.insert(0, str(STAGING))

a = Analysis(
    [str(entry_script)],
    pathex=analysis_paths,
    binaries=binaries,
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    exclude_binaries=False,
    name="pulsewave-11",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)
