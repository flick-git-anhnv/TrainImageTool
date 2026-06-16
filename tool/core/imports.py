# Optional dependency flags — centralised so each module can just import what it needs.

try:
    import requests as _req_mod
    _REQUESTS_OK = True
except ImportError:
    _req_mod = None
    _REQUESTS_OK = False

try:
    import cv2 as _cv2_mod
    import numpy as _np_mod
    _CV2_OK = True
except ImportError:
    _cv2_mod = None
    _np_mod  = None
    _CV2_OK  = False

try:
    import pythoncom
    import win32com.client
    _TTS_OK = True
except ImportError:
    _TTS_OK = False

try:
    from gtts import gTTS as _gTTS
    _GTTS_OK = True
except ImportError:
    _gTTS    = None
    _GTTS_OK = False

try:
    import tkinterdnd2 as _dnd_mod
    _DND_OK = True
except ImportError:
    _dnd_mod = None
    _DND_OK  = False

try:
    from paddleocr import PaddleOCR as _PaddleOCR
    _PADDLE_OK = True
except Exception:
    _PaddleOCR = None
    _PADDLE_OK = False
