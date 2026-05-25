# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the ICBC control panel single-file exe.
# Build with:   pyinstaller icbc-control-panel.spec --noconfirm

datas = [
    ("webui", "webui"),
    ("icbc_pos_list.csv", "."),
    ("config.example.yml", "."),
]

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "PIL", "scipy"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="icbc-control-panel",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
