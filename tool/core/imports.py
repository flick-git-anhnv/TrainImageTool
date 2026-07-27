# Optional dependency flags — centralised so each module can just import what it needs.
#
# Quy ước: thư viện NHẸ thì import thẳng; thư viện NẶNG (paddleocr kéo theo torch +
# transformers + matplotlib, gtts/ddgs gọi mạng) chỉ khai báo cờ khả dụng ở đây và
# nạp thật ở lần dùng đầu tiên — xem `tool/shared/lazy_import.py`. Trước đây
# paddleocr được import ở mức module nên MỞ APP là phải chờ nạp torch, dù user
# không hề dùng tab OCR.
from ..shared.lazy_import import module_available, lazy_callable

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

_GTTS_OK = module_available("gtts")
_gTTS    = lazy_callable("gtts", "gTTS")

try:
    import tkinterdnd2 as _dnd_mod
    _DND_OK = True
except ImportError:
    _dnd_mod = None
    _DND_OK  = False

_PADDLE_OK = module_available("paddleocr")
_PaddleOCR = lazy_callable("paddleocr", "PaddleOCR")

_DDGS_OK = module_available("ddgs")
_DDGS    = lazy_callable("ddgs", "DDGS")
