# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = ['PIL._tkinter_finder', 'PIL.Image', 'PIL.ImageTk', 'PIL.BmpImagePlugin', 'PIL.JpegImagePlugin', 'PIL.PngImagePlugin', 'cv2', 'numpy', 'numpy.core._multiarray_umath', 'numpy.core._multiarray_tests', 'requests', 'requests.adapters', 'requests.auth', 'matplotlib', 'matplotlib.figure', 'matplotlib.backends.backend_tkagg', 'tkinterdnd2', 'collections.abc', 'tool', 'tool.imports', 'tool.settings', 'tool.constants', 'tool.ui_helpers', 'tool.parkingv8_image', 'tool.parkingv6_image', 'tool.lotte_image', 'tool.bad_image_viewer', 'tool.migrate_structure', 'tool.tab_iparking_image']
tmp_ret = collect_all('tkinterdnd2')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('matplotlib')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['H:\\Software\\2.AI-Tranining\\3.Tools\\GetImageApp\\RunGetParkingImage.py'],
    pathex=['H:\\Software\\2.AI-Tranining\\3.Tools'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['paddle', 'paddlepaddle', 'torch', 'torchvision', 'torchaudio', 'tensorflow', 'keras', 'sklearn', 'ultralytics', 'onnxruntime', 'onnx', 'jax', 'flax', 'pandas', 'scipy', 'IPython', 'jupyter', 'notebook', 'matplotlib.tests', 'matplotlib.testing', 'numpy.tests', 'PIL.tests', 'cv2.gapi', 'pytest', '_pytest', 'setuptools', 'distutils', 'doctest', 'unittest', 'pydoc', 'xmlrpc'],
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
    name='GetParkingImage',
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
