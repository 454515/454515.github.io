# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for onefile build (single exe).

Output: dist/jc.exe — models/ and all DLLs are embedded; at launch the
bootloader extracts them to the ASCII-only %TEMP%\\_MEIxxxx dir, so a
Chinese exe dir (e.g. D:\\zjy\\项目\\…) is safe for PaddleX (decision 13).
"""
from PyInstaller.utils.hooks import collect_all, copy_metadata

datas = [('models', 'models')]
binaries = []
hiddenimports = []
tmp_ret = collect_all('paddleocr')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('paddle')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('paddlex')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
for _pkg in ("pyclipper", "shapely", "python_bidi", "imagesize"):
    tmp_ret = collect_all(_pkg)
    datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
for _pkg in ("opencv-contrib-python", "pypdfium2", "python-bidi"):
    datas += copy_metadata(_pkg)


a = Analysis(
    ['src\\app.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='jc',
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
    icon=['assets\\icon.ico'],
)
