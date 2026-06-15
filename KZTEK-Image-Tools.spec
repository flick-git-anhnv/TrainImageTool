# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = ['PIL._tkinter_finder', 'PIL.Image', 'PIL.ImageTk', 'PIL.BmpImagePlugin', 'PIL.JpegImagePlugin', 'PIL.PngImagePlugin', 'cv2', 'numpy', 'numpy.core._multiarray_umath', 'numpy.core._multiarray_tests', 'requests', 'requests.adapters', 'requests.auth', 'win32com.client', 'win32com.shell.shell', 'pythoncom', 'pywintypes', 'gtts', 'tkinterdnd2', 'collections.abc', 'tool', 'tool.app', 'tool.imports', 'tool.settings', 'tool.constants', 'tool.ui_helpers', 'tool.core_split', 'tool.core_crop', 'tool.core_gt', 'tool.core_label_norm', 'tool.core_rename', 'tool.lotte_image', 'tool.parkingv8_image', 'tool.parkingv6_image', 'tool.bad_image_viewer', 'tool.lotte_consolidate', 'tool.tab_split', 'tool.tab_rename', 'tool.tab_crop', 'tool.tab_labelnorm', 'tool.tab_bbox', 'tool.tab_lotte', 'tool.tab_parkingv8', 'tool.tab_parkingv6', 'tool.tab_checker', 'tool.tab_stats', 'tool.tab_plate_search', 'tool.tab_yolo', 'tool.tab_train', 'tool.tab_ocr', 'tool.tab_lpr_tester']
hiddenimports += collect_submodules('win32com')
tmp_ret = collect_all('tkinterdnd2')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('ultralytics')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['train-image-tool.py'],
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
    name='KZTEK-Image-Tools',
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
)
