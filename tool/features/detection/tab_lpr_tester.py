"""Tab kiểm thử LPR — Kztek LPR AI Server & American LPR (OpenALPR).

Hai chế độ nhận dạng:
  lprdetect      — Gửi ảnh xe, server tự cắt biển (field: image)
  DirectLprDetect — Gửi ảnh biển đã cắt (field: upload, endpoint /read-plate)
"""

import csv
import os
import re
import shutil
import threading
from io import BytesIO
from tkinter import *
from tkinter import ttk, filedialog, messagebox

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    _REQ_OK = True
except ImportError:
    _REQ_OK = False

try:
    from PIL import Image, ImageTk
    _PIL_OK = True
except ImportError:
    _PIL_OK = False

from ...core.constants import BG, CARD, ACCENT, ACCENT2, TEXT, DIM, SUCCESS, F_MAIN, F_BOLD, F_MONO
from ...core.imports import _DND_OK
from ...core.settings import (
    _bind_cfg, _bind_history, _push_history, _get_history,
    _cfg_dir, _cfg_save, _CFG,
)
from ...core.ui_helpers import _make_logbox, _append_log, _zoom_image_window, _action_btn

_IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".tif", ".webp"}
_LPR_TYPES = ["Kztek LPR AI Server", "American LPR (OpenALPR)"]
_MODE_VEHICLE = "lprdetect"
_MODE_DIRECT  = "DirectLprDetect"
_URL_HINTS = {
    ("Kztek LPR AI Server",     _MODE_VEHICLE): "http://localhost:8000/alpr",
    ("Kztek LPR AI Server",     _MODE_DIRECT):  "http://localhost:8000/read-plate",
    ("American LPR (OpenALPR)", _MODE_VEHICLE): "http://localhost:8080/v2/recognize",
    ("American LPR (OpenALPR)", _MODE_DIRECT):  "http://localhost:8080/read-plate",
}
_MIME = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
    ".bmp": "image/bmp",  ".webp": "image/webp", ".gif": "image/gif",
    ".tiff": "image/tiff", ".tif": "image/tiff",
}
_REVIEW_ICON = {"correct": "✓", "incorrect": "✗", "": "○"}

_SESSION = None


def _get_session():
    global _SESSION
    if _SESSION is None and _REQ_OK:
        s = requests.Session()
        r = Retry(total=0, raise_on_status=False)
        s.mount("http://",  HTTPAdapter(max_retries=r, pool_connections=4, pool_maxsize=8))
        s.mount("https://", HTTPAdapter(max_retries=r, pool_connections=4, pool_maxsize=8))
        _SESSION = s
    return _SESSION


def _parse_lpr_response(raw) -> dict:
    res = {"plate": "", "original": "", "confidence": 0.0,
           "vehicle_type": "", "bbox": None, "lpr_image_b64": None}
    if isinstance(raw, list):
        raw = raw[0] if raw else {}
    if not isinstance(raw, dict):
        return res

    # Kztek /alpr response: {"Results": [{"Plate": "...", "Box": {...}, "Vehicle": {...}}]}
    for results_key in ("Results", "results"):
        sub = raw.get(results_key)
        if isinstance(sub, list) and sub:
            item = sub[0]
            for pk in ("Plate", "plate", "PlateNumber", "plate_number"):
                if item.get(pk):
                    res["plate"] = str(item[pk]).strip()
                    break
            # BBox: thử cả lowercase và PascalCase
            box = item.get("box") or item.get("Box") or item.get("bbox") or item.get("BoundingBox")
            if box:
                res["bbox"] = box
            # Vehicle type
            veh = item.get("Vehicle") or item.get("vehicle") or {}
            if isinstance(veh, dict):
                for vk in ("VehicleType", "vehicle_type", "type", "class"):
                    if veh.get(vk):
                        res["vehicle_type"] = str(veh[vk])
                        break
            for k in ("lpr_image", "LprImage", "plate_image", "PlateImage"):
                if item.get(k):
                    res["lpr_image_b64"] = item[k]
                    break
            return res

    # Fallback: flat response
    for k in ("plate", "PlateNumber", "license_plate", "licensePlate",
              "plate_number", "plateNumber", "number_plate", "text"):
        if raw.get(k):
            res["plate"] = str(raw[k]).strip(); break
    for k in ("original", "OriginalPlate", "original_plate", "originalPlate"):
        if raw.get(k):
            res["original"] = str(raw[k]).strip(); break
    for k in ("score", "Score", "confidence", "Confidence", "prob"):
        if k in raw:
            try:
                v = float(raw[k])
                res["confidence"] = v / 100 if v > 1.5 else v
            except Exception: pass
            break
    for k in ("vehicle_type", "VehicleType", "vehicleType", "vehicle", "type", "class"):
        if raw.get(k):
            res["vehicle_type"] = str(raw[k]).strip(); break
    for k in ("bbox", "BoundingBox", "bounding_box", "box", "Box", "region"):
        if raw.get(k):
            res["bbox"] = raw[k]; break
    for k in ("lpr_image", "LprImage", "plate_image", "plateImage", "image_base64", "plate_crop"):
        if raw.get(k):
            res["lpr_image_b64"] = raw[k]; break
    return res


def _fmt_bbox(bbox) -> str:
    if isinstance(bbox, dict):
        xmin = bbox.get('xmin', bbox.get('Xmin', 0))
        ymin = bbox.get('ymin', bbox.get('Ymin', 0))
        xmax = bbox.get('xmax', bbox.get('Xmax', 0))
        ymax = bbox.get('ymax', bbox.get('Ymax', 0))
        return f"({xmin}, {ymin}) → ({xmax}, {ymax})"
    if isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
        return f"({bbox[0]}, {bbox[1]}) → ({bbox[2]}, {bbox[3]})"
    return "-"


def _dnd_parse(data: str) -> list:
    return [m.group(1) or m.group(2) for m in re.finditer(r"\{([^}]+)\}|(\S+)", data)
            if m.group(1) or m.group(2)]


# ═══════════════════════════════════════════════════════════════════════════


class LprTesterTab(Frame):

    def __init__(self, master, root):
        super().__init__(master, bg=BG)
        self.root = root
        self._cancel      = False
        self._pil_single  = None
        self._loaded_path = None
        self._pil_lpr     = None
        self._folder_lpr  = {}          # iid → PIL Image biển
        self._folder_files = {}         # iid → full file path
        self._all_tree_order = []       # [(iid, file_path)] — toàn bộ kết quả

        # Resume support
        self._all_queued_files: list = []  # toàn bộ file list của batch hiện tại
        self._resume_from: int = 0         # index kế tiếp cần xử lý
        self._batch_folder: str = ""       # folder của batch hiện tại

        # Review state (giống YOLO)
        self._review_state: dict = dict(_CFG.get("lpr.review_states", {}))
        self._gt_btns: dict = {}
        self._gt_filter  = "all"   # gt: all/match/mismatch/no_gt

        # ── 4-point single-image crop state ──────────────────────────────
        self._lpr4_pts:     list = []
        self._lpr4_drag_idx      = None
        self._lpr4_pil           = None   # perspective-warped result
        self._lpr4_active        = False
        self._sv_scale           = 1.0
        self._sv_off_x           = 0
        self._sv_off_y           = 0
        self.v_lpr4_line_w       = IntVar(value=2)
        _bind_cfg("lpr.sv4_line_w", self.v_lpr4_line_w)

        self._sv_result_bbox     = None   # bbox từ kết quả detect đơn lẻ
        self._folder_bbox: dict  = {}     # iid → bbox dict

        self._build()

    # ═══════════════════════════════ BUILD ════════════════════════════════

    def _build(self):
        self._build_config()
        pw = PanedWindow(self, orient=HORIZONTAL, bg=DIM,
                         sashwidth=5, sashrelief="flat", relief="flat")
        pw.pack(fill=BOTH, expand=True, padx=8, pady=4)
        left  = Frame(pw, bg=BG)
        right = Frame(pw, bg=BG)
        pw.add(left,  minsize=360)
        pw.add(right, minsize=460)
        self._build_single(left)
        self._build_folder(right)
        log_wrap = Frame(self, bg=CARD, pady=2)
        log_wrap.pack(fill=X, padx=8, pady=(0, 6))
        Label(log_wrap, text="Log", bg=CARD, fg=DIM, font=F_BOLD, padx=8).pack(anchor=W)
        lf, self._log = _make_logbox(log_wrap)
        lf.pack(fill=X, padx=8, pady=(0, 4))

    # ── Config strip ──────────────────────────────────────────────────────

    def _build_config(self):
        strip = Frame(self, bg=CARD, padx=10, pady=6)
        strip.pack(fill=X, padx=8, pady=(6, 2))
        r = Frame(strip, bg=CARD)
        r.pack(fill=X)

        Label(r, text="LPR Server:", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        self._type_var = StringVar(value=_LPR_TYPES[0])
        _bind_cfg("lpr.type", self._type_var)
        type_cb = ttk.Combobox(r, textvariable=self._type_var, width=22,
                                style="Dark.TCombobox", values=_LPR_TYPES, state="readonly")
        type_cb.pack(side=LEFT, padx=(4, 14))
        type_cb.bind("<<ComboboxSelected>>", self._on_mode_change)

        Label(r, text="Chế độ:", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        self._detect_mode = StringVar(value=_MODE_DIRECT)
        _bind_cfg("lpr.detect_mode", self._detect_mode)
        for label, val in [("Đọc từ xe", _MODE_VEHICLE), ("Đọc từ biển số", _MODE_DIRECT)]:
            Radiobutton(r, text=label, variable=self._detect_mode, value=val,
                        bg=CARD, fg=TEXT, selectcolor=CARD, activebackground=CARD,
                        activeforeground=ACCENT, font=F_MAIN,
                        command=self._on_mode_change).pack(side=LEFT, padx=(4, 0))
        Frame(r, bg=CARD, width=12).pack(side=LEFT)

        Label(r, text="URL:", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        self._url_var = StringVar(value="http://localhost:8000/read-plate")
        self._url_cb = ttk.Combobox(r, textvariable=self._url_var, width=40,
                                     style="Dark.TCombobox", font=F_MAIN)
        self._url_cb.pack(side=LEFT, padx=(4, 14))
        _bind_history("h.lpr.url", self._url_cb)

        Label(r, text="Timeout:", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        self._timeout_var = IntVar(value=10)
        _bind_cfg("lpr.timeout", self._timeout_var)
        Spinbox(r, from_=1, to=120, textvariable=self._timeout_var, width=4,
                bg=CARD, fg=TEXT, insertbackground=TEXT, buttonbackground=ACCENT2,
                relief="flat", font=F_MAIN).pack(side=LEFT, padx=(4, 2))
        Label(r, text="s", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT, padx=(0, 10))
        Button(r, text="🔌 Test kết nối", command=self._test_connection,
               bg=ACCENT2, fg="white", activebackground=ACCENT, activeforeground="white",
               font=F_MAIN, relief="flat", padx=10, cursor="hand2").pack(side=LEFT, padx=(0, 8))
        self._conn_var = StringVar(value="Chưa kiểm tra")
        self._conn_lbl = Label(r, textvariable=self._conn_var,
                                bg=CARD, fg=DIM, font=F_MAIN, width=22, anchor=W)
        self._conn_lbl.pack(side=LEFT)

    # ── Single image pane ─────────────────────────────────────────────────

    def _build_single(self, parent):
        hdr = Frame(parent, bg=BG)
        hdr.pack(fill=X, padx=8, pady=(6, 2))
        Label(hdr, text="Test ảnh đơn", bg=BG, fg=ACCENT, font=F_BOLD).pack(side=LEFT)
        self._auto_var = BooleanVar(value=True)
        _bind_cfg("lpr.auto_detect", self._auto_var)
        Checkbutton(hdr, text="Tự động nhận dạng", variable=self._auto_var,
                    bg=BG, fg=DIM, selectcolor=CARD, activebackground=BG,
                    font=("Segoe UI", 9)).pack(side=RIGHT)

        pic_outer = Frame(parent, bg="#0d0d1a", bd=2, relief="groove", height=300)
        pic_outer.pack(fill=X, padx=8, pady=(2, 2))
        pic_outer.pack_propagate(False)
        hint = "(Kéo-thả ảnh  |  Click để chọn file)" if _DND_OK else "(Click để chọn file)"
        self._pic_vehicle = Canvas(pic_outer, bg="#0d0d1a", highlightthickness=0,
                                    cursor="hand2")
        self._pic_vehicle.pack(fill=BOTH, expand=True)
        self._pic_vehicle.create_text(200, 140, text=hint, fill=DIM, font=F_MAIN,
                                       justify=CENTER, tags="hint")
        self._pic_vehicle.bind("<Button-1>",        self._on_sv_press)
        self._pic_vehicle.bind("<B1-Motion>",        self._on_sv_drag)
        self._pic_vehicle.bind("<ButtonRelease-1>",  self._on_sv_release)
        self._pic_vehicle.bind("<Motion>",           self._on_sv_motion)
        self._pic_vehicle.bind("<Button-3>",         self._on_sv_rclick)
        self._pic_vehicle.bind("<Double-Button-1>",  self._on_sv_dbl)
        self._pic_vehicle.bind("<Configure>",        lambda e: self._render_single())
        if _DND_OK:
            try:
                self._pic_vehicle.drop_target_register("DND_Files")
                self._pic_vehicle.dnd_bind("<<Drop>>", self._on_drop)
                pic_outer.drop_target_register("DND_Files")
                pic_outer.dnd_bind("<<Drop>>", self._on_drop)
            except Exception: pass

        # 4pt toolbar
        pt_bar = Frame(parent, bg=BG)
        pt_bar.pack(fill=X, padx=8, pady=(1, 0))
        self._btn_sv4pt = Button(
            pt_bar, text="◈ 4 điểm",
            command=self._sv_toggle_4pt,
            bg=CARD, fg=TEXT, font=F_MAIN, relief="flat",
            padx=8, pady=3, cursor="hand2",
            activebackground=ACCENT, activeforeground="white")
        self._btn_sv4pt.pack(side=LEFT)
        Frame(pt_bar, bg=DIM, width=1).pack(side=LEFT, fill=Y, padx=(8, 8))
        Label(pt_bar, text="Nét:", bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT)
        Spinbox(pt_bar, from_=1, to=8, textvariable=self.v_lpr4_line_w,
                width=2, bg="#16162a", fg=ACCENT, font=("Consolas", 9),
                buttonbackground=BG, relief="flat", insertbackground=TEXT,
                command=self._sv_redraw_overlay,
                state="readonly").pack(side=LEFT, padx=(4, 0))
        self._sv4pt_lbl = Label(pt_bar, text="", bg=BG, fg=DIM, font=F_MAIN)
        self._sv4pt_lbl.pack(side=LEFT, padx=(10, 0))

        self._img_lbl = Label(parent, text="", bg=BG, fg=DIM,
                               font=F_MONO, wraplength=360, anchor=CENTER)
        self._img_lbl.pack()

        btn_row = Frame(parent, bg=BG)
        btn_row.pack(fill=X, padx=8, pady=(4, 2))
        _action_btn(btn_row, "📂 Load ảnh (Ctrl+O)", self._load_image,
                    ACCENT2, padx=10, pady=4).pack(side=LEFT, padx=(0, 8))
        self._btn_detect = _action_btn(btn_row, "🔍 Nhận dạng (F5)",
                                        self._detect_single, ACCENT, padx=10, pady=4)
        self._btn_detect.pack(side=LEFT)

        opt = Frame(parent, bg=BG)
        opt.pack(fill=X, padx=8, pady=2)
        self._is_car_var = BooleanVar(value=True)
        _bind_cfg("lpr.is_car", self._is_car_var)
        Checkbutton(opt, text="Loại xe ô tô", variable=self._is_car_var,
                    bg=BG, fg=TEXT, selectcolor=CARD, activebackground=BG,
                    font=F_MAIN).pack(side=LEFT, padx=(0, 14))
        Label(opt, text="Xoay (°):", bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT)
        self._rotate_var = IntVar(value=0)
        _bind_cfg("lpr.rotate", self._rotate_var)
        Spinbox(opt, from_=0, to=360, textvariable=self._rotate_var, width=5,
                bg=CARD, fg=TEXT, insertbackground=TEXT, buttonbackground=ACCENT2,
                relief="flat", font=F_MAIN).pack(side=LEFT, padx=4)

        res = Frame(parent, bg=CARD, padx=10, pady=8)
        res.pack(fill=X, padx=8, pady=(4, 2))
        self._res = {}
        for label, key in [("Biển số", "plate"), ("Biển gốc", "original"),
                            ("Loại xe", "vehicle_type"), ("Confidence", "confidence"),
                            ("Thời gian", "elapsed_ms"), ("Bounding box", "bbox")]:
            row = Frame(res, bg=CARD); row.pack(fill=X, pady=1)
            Label(row, text=f"{label}:", bg=CARD, fg=DIM,
                  font=F_MAIN, width=13, anchor=W).pack(side=LEFT)
            v = StringVar(value="-")
            Entry(row, textvariable=v, bg=CARD, fg=TEXT,
                  insertbackground=TEXT, relief="flat", font=F_MONO,
                  state="readonly", readonlybackground=CARD).pack(side=LEFT, fill=X, expand=True)
            self._res[key] = v

        lc = Frame(parent, bg=CARD)
        lc.pack(fill=X, padx=8, pady=(2, 6))
        Label(lc, text="Ảnh biển cắt (double-click để zoom):",
              bg=CARD, fg=DIM, font=F_MAIN).pack(anchor=W, padx=4, pady=(4, 0))
        self._pic_lpr = Label(lc, bg=CARD, fg=DIM, font=F_MAIN,
                               text="(chưa nhận dạng)", height=4, cursor="hand2")
        self._pic_lpr.pack(fill=X, padx=4, pady=4)
        self._pic_lpr.bind("<Double-Button-1>",
                            lambda e: _zoom_image_window(self.root, self._pil_lpr, "Ảnh biển số"))

    # ── Folder batch pane ─────────────────────────────────────────────────

    def _build_folder(self, parent):
        Label(parent, text="Test thư mục", bg=BG, fg=ACCENT,
              font=F_BOLD).pack(anchor=W, padx=8, pady=(6, 2))

        fr = Frame(parent, bg=BG)
        fr.pack(fill=X, padx=8, pady=2)
        self._folder_var = StringVar()
        _bind_cfg("lpr.folder", self._folder_var)
        self._folder_cb = ttk.Combobox(fr, textvariable=self._folder_var,
                                        style="Dark.TCombobox", font=F_MAIN)
        self._folder_cb.pack(side=LEFT, fill=X, expand=True, padx=(0, 4))
        _bind_history("h.lpr.folder", self._folder_cb)
        Button(fr, text="Chọn…", command=self._browse_folder,
               bg=ACCENT2, fg="white", activebackground=ACCENT, activeforeground="white",
               font=F_MAIN, relief="flat", padx=8, cursor="hand2").pack(side=LEFT, padx=(0, 4))
        Button(fr, text="📂", command=self._open_folder,
               bg=CARD, fg=TEXT, activebackground=ACCENT2, activeforeground="white",
               font=F_MAIN, relief="flat", padx=6, cursor="hand2").pack(side=LEFT)

        opt = Frame(parent, bg=BG)
        opt.pack(fill=X, padx=8, pady=2)
        self._subfolder_var = BooleanVar(value=False)
        _bind_cfg("lpr.subfolder", self._subfolder_var)
        Checkbutton(opt, text="Bao gồm thư mục con", variable=self._subfolder_var,
                    bg=BG, fg=TEXT, selectcolor=CARD, activebackground=BG,
                    font=F_MAIN).pack(side=LEFT, padx=(0, 12))
        self._f_is_car_var = BooleanVar(value=True)
        _bind_cfg("lpr.f_is_car", self._f_is_car_var)
        Checkbutton(opt, text="Loại xe ô tô", variable=self._f_is_car_var,
                    bg=BG, fg=TEXT, selectcolor=CARD, activebackground=BG,
                    font=F_MAIN).pack(side=LEFT, padx=(0, 12))
        Label(opt, text="Xoay:", bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT)
        self._f_rotate_var = IntVar(value=0)
        _bind_cfg("lpr.f_rotate", self._f_rotate_var)
        Spinbox(opt, from_=0, to=360, textvariable=self._f_rotate_var, width=5,
                bg=CARD, fg=TEXT, insertbackground=TEXT, buttonbackground=ACCENT2,
                relief="flat", font=F_MAIN).pack(side=LEFT, padx=(4, 12))
        Label(opt, text="Luồng:", bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT)
        self._workers_var = IntVar(value=1)
        _bind_cfg("lpr.workers", self._workers_var)
        Spinbox(opt, from_=1, to=8, textvariable=self._workers_var, width=4,
                bg=CARD, fg=TEXT, insertbackground=TEXT, buttonbackground=ACCENT2,
                relief="flat", font=F_MAIN).pack(side=LEFT, padx=4)

        btn_row = Frame(parent, bg=BG)
        btn_row.pack(fill=X, padx=8, pady=(4, 2))
        self._btn_start = _action_btn(btn_row, "▶ Test thư mục (F5)",
                                       self._start, ACCENT, padx=10, pady=4)
        self._btn_start.pack(side=LEFT, padx=(0, 8))
        self._btn_stop = _action_btn(btn_row, "■ Dừng (Esc)", self._stop, "#555", padx=10, pady=4)
        self._btn_stop.pack(side=LEFT, padx=(0, 8))
        self._btn_stop.config(state=DISABLED)
        self._btn_resume = _action_btn(btn_row, "▶ Tiếp tục", self._resume, "#2a5a2a", padx=10, pady=4)
        self._btn_resume.pack(side=LEFT, padx=(0, 8))
        self._btn_resume.config(state=DISABLED)
        _action_btn(btn_row, "↻ Retry lỗi", self._retry_failed,
                    ACCENT2, padx=8, pady=4).pack(side=LEFT, padx=(0, 8))
        _action_btn(btn_row, "💾 Xuất CSV (Ctrl+S)", self._export,
                    ACCENT2, padx=8, pady=4).pack(side=LEFT, padx=(0, 8))
        _action_btn(btn_row, "🗑 Xóa cache", self._clear_folder_cache,
                    "#4a3030", padx=8, pady=4).pack(side=LEFT)

        pg = Frame(parent, bg=BG)
        pg.pack(fill=X, padx=8, pady=2)
        self._prog_lbl = Label(pg, text="Sẵn sàng", bg=BG, fg=DIM, font=F_MAIN, anchor=W)
        self._prog_lbl.pack(fill=X)
        self._pb = ttk.Progressbar(pg, style="K.Horizontal.TProgressbar", maximum=100, value=0)
        self._pb.pack(fill=X, pady=(2, 2))
        self._stats_lbl = Label(pg, text="", bg=BG, fg=SUCCESS, font=F_MAIN, anchor=W)
        self._stats_lbl.pack(fill=X)

        # ── Row 1: Keyword search ─────────────────────────────────────────
        filter_row2 = Frame(parent, bg=BG)
        filter_row2.pack(fill=X, padx=8, pady=(1, 4))
        Label(filter_row2, text="Biển:", bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT, padx=(0, 4))
        self._kw_var = StringVar()
        kw_entry = Entry(filter_row2, textvariable=self._kw_var, width=18,
                         bg=CARD, fg=TEXT, insertbackground=TEXT, relief="flat",
                         font=F_MONO)
        kw_entry.pack(side=LEFT, padx=(0, 4))
        kw_entry.bind("<KeyRelease>", lambda e: self._apply_all_filters())
        Button(filter_row2, text="✕", command=self._clear_kw,
               bg=CARD, fg=DIM, font=F_MAIN, relief="flat",
               padx=4, cursor="hand2").pack(side=LEFT)
        Label(filter_row2, text="(* = đầu/cuối  ? = 1 ký tự)",
              bg=BG, fg=DIM, font=("Segoe UI", 8)).pack(side=LEFT, padx=(6, 0))

        # ── Row 3: GT comparison filter ───────────────────────────────────
        filter_row3 = Frame(parent, bg=BG)
        filter_row3.pack(fill=X, padx=8, pady=(0, 4))
        Label(filter_row3, text="So sánh GT:", bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT, padx=(0, 4))
        for code, lbl_text, fg in [
            ("all",      "Tất cả",      TEXT),
            ("match",    "✓ Đúng",      SUCCESS),
            ("mismatch", "✗ Sai",       "#f05050"),
            ("no_gt",    "Không có GT", DIM),
        ]:
            btn = Button(filter_row3, text=lbl_text,
                         command=lambda c=code: self._set_gt_filter(c),
                         bg=CARD, fg=fg, font=F_MAIN, relief="flat",
                         padx=8, cursor="hand2", activebackground="#252540",
                         activeforeground=fg)
            btn.pack(side=LEFT, padx=2)
            self._gt_btns[code] = btn
        self._gt_btns["all"].config(relief="sunken", bg="#252540")

        # ── Horizontal PanedWindow: kết quả (trái) | preview ảnh (phải) ──
        hpw = PanedWindow(parent, orient=HORIZONTAL, bg=DIM,
                          sashwidth=5, sashrelief="flat", relief="flat")
        hpw.pack(fill=BOTH, expand=True, padx=8, pady=(2, 4))
        self._hpw_result = hpw

        # ── TRÁI: Treeview + mark + sửa biển ─────────────────────────────
        left_pane = Frame(hpw, bg=BG)
        hpw.add(left_pane, minsize=300)

        tv_f = Frame(left_pane, bg=BG)
        tv_f.pack(fill=BOTH, expand=True)
        cols = ("#", "Tên file", "Biển số", "Biển gốc", "Loại xe", "ms", "Trạng thái", "GT", "📂", "📋")
        self._tree = ttk.Treeview(tv_f, columns=cols, show="headings",
                                   style="Dark.Treeview", selectmode="browse")
        col_widths = [38, 190, 115, 105, 85, 60, 110, 75, 34, 34]
        for col, w in zip(cols, col_widths):
            self._tree.heading(col, text=col)
            stretch = col in ("Tên file", "Trạng thái")
            self._tree.column(col, width=w, minwidth=w if col in ("📂", "📋") else 30,
                               stretch=stretch, anchor=CENTER if col in ("📂", "📋", "#", "ms", "GT") else W)
        vsb = ttk.Scrollbar(tv_f, orient=VERTICAL,   command=self._tree.yview)
        hsb = ttk.Scrollbar(tv_f, orient=HORIZONTAL, command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side=RIGHT, fill=Y)
        hsb.pack(side=BOTTOM, fill=X)
        self._tree.pack(fill=BOTH, expand=True)
        self._tree.tag_configure("ok",        background="#1a2e1a", foreground=TEXT)
        self._tree.tag_configure("err",       background="#2e1a1a", foreground=TEXT)
        self._tree.tag_configure("warn",      background="#2a2820", foreground=TEXT)
        self._tree.tag_configure("gt_ok",     background="#0d2b0d", foreground=SUCCESS)
        self._tree.tag_configure("gt_err",    background="#2b0d0d", foreground="#f08080")
        self._tree.tag_configure("unreviewed",background="#16162a", foreground=DIM)
        self._tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self._tree.bind("<Double-Button-1>",  self._on_tree_dbl)
        self._tree.bind("<Button-1>",         self._on_tree_click)

        mark_row = Frame(left_pane, bg=BG)
        mark_row.pack(fill=X, pady=(4, 1))
        Button(mark_row, text="✓ Đúng  [Enter]",
               command=lambda: self._mark_current("correct"),
               bg="#1a3a1a", fg=SUCCESS, font=F_MAIN, relief="flat",
               padx=10, pady=4, cursor="hand2",
               activebackground="#2d6a2d", activeforeground="white").pack(side=LEFT, padx=(0, 6))
        Button(mark_row, text="✗ Sai  [Del]",
               command=lambda: self._mark_current("incorrect"),
               bg="#3a1a1a", fg="#f05050", font=F_MAIN, relief="flat",
               padx=10, pady=4, cursor="hand2",
               activebackground="#6a2d2d", activeforeground="white").pack(side=LEFT, padx=(0, 6))
        Button(mark_row, text="↺ Bỏ đánh dấu",
               command=lambda: self._mark_current(""),
               bg=CARD, fg=DIM, font=F_MAIN, relief="flat",
               padx=8, pady=4, cursor="hand2",
               activebackground="#252540", activeforeground=TEXT).pack(side=LEFT, padx=(0, 12))
        self._mark_lbl = Label(mark_row, text="", bg=BG, fg=DIM, font=F_MONO)
        self._mark_lbl.pack(side=LEFT, expand=True, fill=X)
        Button(mark_row, text="📂 GT Đúng",
               command=lambda: self._open_gt_folder("dung"),
               bg=CARD, fg=SUCCESS, font=F_MAIN, relief="flat",
               padx=8, pady=4, cursor="hand2").pack(side=LEFT, padx=(0, 4))
        Button(mark_row, text="📂 GT Sai",
               command=lambda: self._open_gt_folder("sai"),
               bg=CARD, fg="#f05050", font=F_MAIN, relief="flat",
               padx=8, pady=4, cursor="hand2").pack(side=LEFT)

        # Ô sửa biển số GT (inline)
        edit_row = Frame(left_pane, bg=BG)
        edit_row.pack(fill=X, pady=(1, 4))
        Label(edit_row, text="Sửa biển GT:", bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT, padx=(0, 4))
        self._plate_edit_var = StringVar()
        self._plate_edit = ttk.Combobox(edit_row, textvariable=self._plate_edit_var,
                                         style="Dark.TCombobox", font=F_MONO, width=18)
        self._plate_edit.pack(side=LEFT, fill=X, expand=True)
        self._plate_edit.bind("<Return>", lambda e: self._save_plate_edit())
        _bind_history("h.lpr.plate_edit", self._plate_edit)

        # ── PHẢI: Preview ảnh ─────────────────────────────────────────────
        right_pane = Frame(hpw, bg=CARD)
        hpw.add(right_pane, minsize=180)
        hpw.bind("<ButtonRelease-1>", self._save_sash)

        self._prev_lbl = Label(right_pane, text="(chọn dòng để xem ảnh)",
                                bg=CARD, fg=DIM, font=F_MONO)
        self._prev_lbl.pack(anchor=W, padx=6, pady=(4, 2))
        self._pic_fv = Label(right_pane, bg="#0d0d1a", fg=DIM, text="(ảnh xe)",
                              font=F_MAIN, cursor="hand2")
        self._pic_fv.pack(fill=BOTH, expand=True, padx=4, pady=(0, 2))
        self._pic_fv.bind("<Double-Button-1>", lambda e: self._zoom_fv())
        Label(right_pane, text="Biển số nhận dạng:", bg=CARD, fg=DIM,
              font=F_MAIN).pack(anchor=W, padx=6, pady=(0, 1))
        # fp_frame: ảnh TRÁI — diff text PHẢI
        fp_frame = Frame(right_pane, bg="#0d0d1a", height=140)
        fp_frame.pack(fill=X, padx=4, pady=(0, 4))
        fp_frame.pack_propagate(False)

        # Ảnh biển số bên trái (chiều ngang tự co theo ảnh)
        self._pic_fp = Label(fp_frame, bg="#0d0d1a", fg=DIM, text="(biển số)",
                              font=F_MAIN, cursor="hand2")
        self._pic_fp.pack(side=LEFT, fill=Y, padx=(0, 6))
        self._pic_fp.bind("<Double-Button-1>", lambda e: self._zoom_fp())

        # Diff text bên phải, font lớn hơn
        self._diff_txt = Text(fp_frame, bg="#0d0d1a", fg=TEXT,
                              font=("Consolas", 14, "bold"), relief="flat",
                              state=DISABLED, cursor="arrow", wrap="none")
        self._diff_txt.pack(side=LEFT, fill=BOTH, expand=True)

        self.root.after(200, self._restore_sash)

    # ═══════════════════════════ CONFIG ACTIONS ═══════════════════════════

    _LEGACY_URLS = {
        "http://localhost:8000/detect",
    }

    def _on_mode_change(self, _=None):
        key  = (self._type_var.get(), self._detect_mode.get())
        hint = _URL_HINTS.get(key, "")
        curr = self._url_var.get().strip()
        if curr in _URL_HINTS.values() or curr in self._LEGACY_URLS or not curr:
            self._url_var.set(hint)

    def _test_connection(self):
        if not _REQ_OK:
            messagebox.showerror("Lỗi", "pip install requests"); return
        url = self._url_var.get().strip()
        if not url:
            messagebox.showwarning("Thông báo", "Vui lòng nhập URL."); return
        self._conn_var.set("Đang kiểm tra...")
        self._conn_lbl.config(fg="#f0c040")

        def _chk():
            try:
                base = "/".join(url.split("/")[:3])
                r = _get_session().head(base, timeout=self._timeout_var.get())
                ok = r.status_code < 500
            except Exception:
                try:
                    r = _get_session().get(base, timeout=self._timeout_var.get())
                    ok = r.status_code < 500
                except Exception:
                    ok = False
            def _upd():
                if ok:
                    self._conn_var.set("✔ Server sẵn sàng")
                    self._conn_lbl.config(fg=SUCCESS)
                    _append_log(self._log, f"✔ Kết nối OK — {url}")
                else:
                    self._conn_var.set("✗ Không phản hồi")
                    self._conn_lbl.config(fg="#f05050")
                    _append_log(self._log, f"[LỖI] Không kết nối được — {url}")
            self.root.after(0, _upd)
        threading.Thread(target=_chk, daemon=True).start()

    # ═══════════════════════════ SINGLE IMAGE ═════════════════════════════

    def _load_image(self, _=None):
        if not _PIL_OK:
            messagebox.showerror("Lỗi", "pip install Pillow"); return
        path = filedialog.askopenfilename(
            title="Chọn ảnh xe",
            initialdir=_CFG.get("lpr.last_dir") or None,
            filetypes=[("Ảnh", "*.jpg *.jpeg *.png *.bmp *.webp *.gif *.tiff"),
                       ("Tất cả", "*.*")],
        )
        if path:
            self._load_from_path(path)

    def _on_drop(self, event):
        paths = _dnd_parse(event.data)
        if not paths: return
        path = paths[0]
        if os.path.isfile(path) and os.path.splitext(path)[1].lower() in _IMG_EXTS:
            self._load_from_path(path)
        else:
            _append_log(self._log, f"⚠ File không hợp lệ: {path}")

    def _load_from_path(self, path: str):
        if not _PIL_OK: return
        _CFG["lpr.last_dir"] = os.path.dirname(path)
        _cfg_save()
        try:
            img = Image.open(path)
            self._pil_single  = img.copy()
            self._loaded_path = path
            img.close()
            self._sv_clear_4pt()
            self.root.after(50, self._render_single)
            self._img_lbl.config(text=os.path.basename(path))
            self._clear_single_result()
            _append_log(self._log, f"✔ Đã tải: {path}")
            if self._auto_var.get():
                self.root.after(50, self._detect_single)
        except Exception as ex:
            _append_log(self._log, f"[LỖI] Không tải được ảnh: {ex}")

    def _detect_single(self):
        if not _REQ_OK:
            messagebox.showerror("Lỗi", "pip install requests"); return
        if self._pil_single is None and not self._loaded_path:
            messagebox.showwarning("Thông báo", "Chưa tải ảnh."); return
        url = self._url_var.get().strip()
        if not url:
            messagebox.showwarning("Thông báo", "Chưa nhập URL."); return

        self._btn_detect.config(state=DISABLED, text="Đang nhận dạng...")
        self._clear_single_result()
        # Nếu 4pt mode đang active và có ảnh warped → gửi ảnh đã crop
        if self._lpr4_active and self._lpr4_pil:
            path     = None
            pil_copy = self._lpr4_pil.copy()
            _append_log(self._log, "◈ Dùng vùng 4 điểm đã crop")
        else:
            path     = self._loaded_path
            pil_copy = self._pil_single.copy() if self._pil_single else None
        timeout  = self._timeout_var.get()
        mode     = self._detect_mode.get()
        lpr_type = self._type_var.get()
        _append_log(self._log, f"⠿ [{mode}] → {url}")

        def _run():
            import time
            t0 = time.perf_counter()
            if path and os.path.isfile(path):
                result, err = _api_call_file(path, url, timeout, mode, lpr_type)
            elif pil_copy:
                result, err = _api_call_pil(pil_copy, url, timeout, mode, lpr_type)
                pil_copy.close()
            else:
                result, err = {}, "Không có ảnh"
            elapsed = int((time.perf_counter() - t0) * 1000)

            def _upd():
                self._btn_detect.config(state=NORMAL, text="🔍 Nhận dạng (F5)")
                if err:
                    _append_log(self._log, f"[LỖI] {err}"); return
                plate = result.get("plate", "")
                self._res["plate"].set(plate or "(không nhận dạng)")
                self._res["original"].set(result.get("original") or "-")
                self._res["vehicle_type"].set(result.get("vehicle_type") or "-")
                conf = result.get("confidence", 0)
                self._res["confidence"].set(f"{conf:.1%}" if conf else "-")
                self._res["elapsed_ms"].set(f"{elapsed} ms")
                self._res["bbox"].set(_fmt_bbox(result.get("bbox")))
                self._sv_result_bbox = result.get("bbox")
                self._render_bbox_overlay()
                b64 = result.get("lpr_image_b64")
                if b64 and _PIL_OK:
                    try:
                        import base64
                        self._pil_lpr = Image.open(BytesIO(base64.b64decode(b64)))
                        self._show_img(self._pic_lpr, self._pil_lpr, 360, 80)
                    except Exception: pass
                log_msg = f'✔ "{plate}"  {elapsed}ms'
                if conf: log_msg += f"  conf:{conf:.1%}"
                _append_log(self._log, log_msg)
            self.root.after(0, _upd)
        threading.Thread(target=_run, daemon=True).start()

    def _clear_single_result(self):
        for v in self._res.values(): v.set("-")
        self._pic_lpr.config(image="", text="(chưa nhận dạng)")
        self._pil_lpr  = None
        self._lpr4_pil = None
        self._sv_result_bbox = None
        self._pic_vehicle.delete("bbox_ov")

    # ═══════════════════════════ FOLDER BATCH ═════════════════════════════

    def _browse_folder(self):
        p = filedialog.askdirectory(
            title="Chọn thư mục ảnh",
            initialdir=self._folder_var.get() or _cfg_dir("lpr.folder") or None)
        if p:
            self._folder_var.set(p)
            _push_history("h.lpr.folder", p)
            self._folder_cb["values"] = _get_history("h.lpr.folder")

    def _open_folder(self):
        p = self._folder_var.get().strip()
        if p and os.path.isdir(p): os.startfile(p)

    def _start(self):
        if not _REQ_OK:
            messagebox.showerror("Lỗi", "pip install requests"); return
        folder = self._folder_var.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showwarning("Thông báo", "Thư mục không hợp lệ."); return
        url = self._url_var.get().strip()
        if not url:
            messagebox.showwarning("Thông báo", "Chưa nhập URL."); return

        # Thu thập danh sách file
        include_sub = self._subfolder_var.get()
        if include_sub:
            files = []
            for rt, _, fnames in os.walk(folder):
                for f in fnames:
                    if os.path.splitext(f)[1].lower() in _IMG_EXTS:
                        files.append(os.path.join(rt, f))
        else:
            files = [os.path.join(folder, f) for f in os.listdir(folder)
                     if os.path.splitext(f)[1].lower() in _IMG_EXTS]
        files.sort()
        if not files:
            messagebox.showinfo("Thông báo", "Không tìm thấy ảnh nào trong thư mục."); return

        self._cancel = False
        self._all_queued_files = files
        self._resume_from = 0
        self._batch_folder = folder
        for pil in self._folder_lpr.values():
            try: pil.close()
            except Exception: pass
        self._folder_lpr.clear()
        self._folder_bbox.clear()
        self._folder_files.clear()
        self._all_tree_order.clear()
        self._tree.delete(*self._tree.get_children())
        self._clear_fpreview()
        self._mark_lbl.config(text="")
        self._btn_start.config(state=DISABLED)
        self._btn_stop.config(state=NORMAL)
        self._btn_resume.config(state=DISABLED)
        self._pb.config(value=0, maximum=len(files))
        self._kw_var.set("")
        self._gt_filter = "all"
        for code, btn in self._gt_btns.items():
            btn.config(relief="sunken" if code == "all" else "flat",
                       bg="#252540" if code == "all" else CARD)

        _append_log(self._log, f"⠿ [{self._detect_mode.get()}] {len(files)} ảnh → {url}")
        threading.Thread(
            target=self._folder_worker,
            args=(files, folder, url, self._timeout_var.get(),
                  self._detect_mode.get(), self._type_var.get(),
                  0, 0, 0, 0),
            daemon=True).start()

    def _resume(self):
        """Tiếp tục từ vị trí đã dừng."""
        if not self._all_queued_files or self._resume_from >= len(self._all_queued_files):
            messagebox.showinfo("Thông báo", "Không có gì để tiếp tục."); return
        url = self._url_var.get().strip()
        if not url:
            messagebox.showwarning("Thông báo", "Chưa nhập URL."); return

        self._cancel = False
        self._btn_start.config(state=DISABLED)
        self._btn_stop.config(state=NORMAL)
        self._btn_resume.config(state=DISABLED)

        # Tính lại ok/fail/ms từ tree hiện tại
        all_iids = [iid for iid, _ in self._all_tree_order]
        init_ok = init_fail = init_ms = 0
        for iid in all_iids:
            vals = self._tree.item(iid, "values")
            if not vals: continue
            st = str(vals[6])
            ms_val = str(vals[5])
            if st == "OK": init_ok += 1
            elif st != "GT: Đúng ✓": init_fail += 1
            try: init_ms += int(ms_val)
            except Exception: pass

        remaining = self._all_queued_files[self._resume_from:]
        _append_log(self._log, (
            f"▶ Tiếp tục từ #{self._resume_from + 1} — còn {len(remaining)} ảnh"))
        threading.Thread(
            target=self._folder_worker,
            args=(self._all_queued_files, self._batch_folder, url,
                  self._timeout_var.get(), self._detect_mode.get(),
                  self._type_var.get(),
                  self._resume_from, init_ok, init_fail, init_ms),
            daemon=True).start()

    def _stop(self):
        self._cancel = True
        _append_log(self._log, "⚠ Đang dừng...")

    def _folder_worker(self, all_files, folder, url, timeout, mode, lpr_type,
                       start_from, init_ok, init_fail, init_ms):
        import time, json as _json
        total   = len(all_files)
        ok_n    = init_ok
        fail_n  = init_fail
        total_ms = init_ms

        # Tải cache từ thư mục nguồn
        _cache_path = os.path.join(folder, ".kztek_lpr_cache.json")
        try:
            with open(_cache_path, "r", encoding="utf-8") as _cf:
                _cache = _json.load(_cf)
        except Exception:
            _cache = {}
        _cache_dirty = False

        def _flush_cache():
            nonlocal _cache_dirty
            if not _cache_dirty: return
            try:
                with open(_cache_path, "w", encoding="utf-8") as _cf:
                    _json.dump(_cache, _cf, ensure_ascii=False)
                _cache_dirty = False
            except Exception: pass

        self.root.after(0, lambda: self._pb.config(maximum=total))

        for i in range(start_from, total):
            if self._cancel:
                self._resume_from = i   # lưu điểm tiếp tục
                break
            fpath = all_files[i]
            fname = os.path.relpath(fpath, folder) if folder else os.path.basename(fpath)

            # Kiểm tra cache theo fname + mtime
            try:
                _mtime = str(round(os.path.getmtime(fpath), 3))
            except Exception:
                _mtime = ""
            _cached = _cache.get(fname)
            _hit = bool(_cached and _cached.get("mtime") == _mtime and "plate" in _cached)

            def _crop_plate(img_path, bbox):
                """Crop vùng biển số từ ảnh gốc dùng bbox dict."""
                if not bbox or not _PIL_OK: return None
                try:
                    with Image.open(img_path) as _im:
                        w, h = _im.size
                        x1 = int(bbox.get("xmin", bbox.get("Xmin", 0)))
                        y1 = int(bbox.get("ymin", bbox.get("Ymin", 0)))
                        x2 = int(bbox.get("xmax", bbox.get("Xmax", w)))
                        y2 = int(bbox.get("ymax", bbox.get("Ymax", h)))
                        if x2 > x1 and y2 > y1:
                            return _im.crop((x1, y1, x2, y2)).copy()
                except Exception: pass
                return None

            t0 = time.perf_counter()
            lpr_pil  = None
            lpr_bbox = None
            if _hit:
                plate   = _cached.get("plate", "")
                vtype   = _cached.get("vehicle_type", "")
                elapsed = _cached.get("ms", 0)
                status  = ("OK" if plate else "Không nhận dạng") + " ★Cache"
                lpr_bbox = _cached.get("bbox")
                lpr_pil  = _crop_plate(fpath, lpr_bbox)
                if plate: ok_n += 1
                else:     fail_n += 1
                total_ms += elapsed
            else:
                try:
                    result, err = _api_call_file(fpath, url, timeout, mode, lpr_type)
                    elapsed = int((time.perf_counter() - t0) * 1000)
                    if err:
                        plate = vtype = ""; status = f"Lỗi: {err}"; fail_n += 1
                    else:
                        plate = result.get("plate", "")
                        vtype = result.get("vehicle_type", "")
                        status = "OK" if plate else "Không nhận dạng"
                        if plate: ok_n += 1
                        else:     fail_n += 1
                        bbox     = result.get("bbox")
                        lpr_bbox = bbox
                        lpr_pil  = _crop_plate(fpath, bbox)
                        # Lưu cache khi không lỗi kết nối
                        if not err:
                            _cache[fname] = {
                                "mtime":        _mtime,
                                "plate":        plate,
                                "vehicle_type": vtype,
                                "ms":           elapsed,
                                "bbox":         bbox,
                            }
                            _cache_dirty = True
                    total_ms += elapsed
                except Exception as ex:
                    elapsed = 0; plate = vtype = ""; status = f"Lỗi: {ex}"
                    fail_n += 1

            # Flush cache mỗi 20 ảnh để tránh mất kết quả nếu bị ngắt giữa chừng
            if _cache_dirty and i % 20 == 0:
                _flush_cache()

            gt_plate = _load_gt(fpath)      # đọc 1 lần dùng cho cả 2 chỗ
            orig     = gt_plate             # Biển gốc = GT từ file .txt
            _gt      = _cmp_plate(plate, gt_plate)
            _i, _f, _pl, _or, _vt = i + 1, fname, plate, orig, vtype
            _ms, _st, _lpi, _fp = elapsed, status, lpr_pil, fpath
            _lbx = lpr_bbox
            _ok, _nk, _tms = ok_n, fail_n, total_ms

            def _ui(i=_i, f=_f, pl=_pl, orig=_or, vt=_vt,
                    ms=_ms, st=_st, lpi=_lpi, fp=_fp, lbx=_lbx,
                    ok=_ok, nk=_nk, tms=_tms, gt=_gt):
                # Nếu có GT: tự động áp dụng kết quả so sánh vào trạng thái
                if gt == "✓ Đúng":
                    display_st = "GT: Đúng ✓"
                    tag = "gt_ok"
                elif gt == "✗ Sai":
                    display_st = "GT: Sai ✗"
                    tag = "gt_err"
                else:
                    display_st = st
                    tag = "ok" if st == "OK" else ("err" if st.startswith("Lỗi") else "warn")
                iid = self._tree.insert("", END, values=(i, f, pl, orig, vt, ms or "-", display_st, gt, "📂", "📋"))
                self._tree.item(iid, tags=(tag,))
                self._folder_files[iid] = fp
                self._all_tree_order.append((iid, fp))
                if lpi:  self._folder_lpr[iid]  = lpi
                if lbx:  self._folder_bbox[iid] = lbx
                self._tree.see(iid)
                self._pb["value"] = i
                self._prog_lbl.config(text=f"Đang xử lý: {i}/{total}  ({int(i/total*100)}%)")
                done = ok + nk
                avg  = tms // done if done else 0
                rate = f"{ok/done:.1%}" if done else "—"
                self._stats_lbl.config(
                    text=f"OK: {ok}  |  Thất bại: {nk}  |  TB: {avg}ms  |  Tỉ lệ: {rate}")
            self.root.after(0, _ui)
        else:
            # Vòng lặp kết thúc tự nhiên (không bị cancel)
            self._resume_from = total

        _flush_cache()   # lưu cache cuối cùng
        _cancelled = self._cancel
        _ok_n, _fail_n, _total_ms = ok_n, fail_n, total_ms

        def _done():
            self._btn_start.config(state=NORMAL)
            self._btn_stop.config(state=DISABLED)
            has_remaining = _cancelled and self._resume_from < total
            self._btn_resume.config(state=NORMAL if has_remaining else DISABLED)
            done = _ok_n + _fail_n
            avg  = _total_ms // done if done else 0
            rate = f"{_ok_n/done:.1%}" if done else "—"
            if _cancelled and has_remaining:
                msg = (f"Đã dừng: {self._resume_from}/{total}  "
                       f"OK:{_ok_n}  Thất bại:{_fail_n}  TB:{avg}ms  "
                       f"— còn {total - self._resume_from} ảnh chưa xử lý")
            else:
                msg = (f"Hoàn thành: {done}/{total}  "
                       f"OK:{_ok_n}  Thất bại:{_fail_n}  TB:{avg}ms  Tỉ lệ:{rate}")
            self._prog_lbl.config(text=msg)
            _append_log(self._log, f"✔ {msg}")
            self._update_filter_counts()
        self.root.after(0, _done)

    def _retry_failed(self):
        url = self._url_var.get().strip()
        folder = self._folder_var.get().strip()
        if not url:
            messagebox.showwarning("Thông báo", "Chưa nhập URL."); return
        rows = [
            (iid, self._folder_files.get(iid, ""))
            for iid in self._tree.get_children()
            if str(self._tree.item(iid)["values"][6]) in ("Không nhận dạng",)
            or str(self._tree.item(iid)["values"][6]).startswith("Lỗi")
        ]
        if not rows:
            messagebox.showinfo("Thông báo", "Không có dòng nào cần retry."); return
        _append_log(self._log, f"⠿ Retry {len(rows)} ảnh...")
        timeout  = self._timeout_var.get()
        mode     = self._detect_mode.get()
        lpr_type = self._type_var.get()

        def _run():
            for iid, fpath in rows:
                if self._cancel or not os.path.isfile(fpath): continue
                result, err = _api_call_file(fpath, url, timeout, mode, lpr_type)
                plate  = "" if err else result.get("plate", "")
                status = ("OK" if plate else "Không nhận dạng") if not err else f"Lỗi: {err}"
                gt_cmp = _cmp_plate(plate, _load_gt(fpath))
                def _upd(iid=iid, pl=plate, st=status, gt=gt_cmp):
                    vals = list(self._tree.item(iid)["values"])
                    vals[2] = pl; vals[6] = st
                    if len(vals) > 7:
                        vals[7] = gt
                    self._tree.item(iid, values=vals)
                    tag = "ok" if st == "OK" else ("err" if st.startswith("Lỗi") else "warn")
                    self._tree.item(iid, tags=(tag,))
                self.root.after(0, _upd)
            self.root.after(0, lambda: _append_log(self._log, "✔ Retry xong."))
        threading.Thread(target=_run, daemon=True).start()

    # ═══════════════════════════ MARK / REVIEW (YOLO style) ═══════════════

    def _ask_correct_plate(self, current: str) -> str:
        """Popup nhập biển số đúng. Trả về chuỗi plate hoặc '' nếu cancel."""
        win = Toplevel(self.root)
        win.title("Nhập biển số đúng")
        win.configure(bg=CARD)
        win.resizable(False, False)
        win.grab_set()

        Label(win, text="Biển số đúng:", bg=CARD, fg=TEXT, font=F_BOLD,
              padx=16, pady=10).pack(anchor=W)
        hint = current if current not in ("", "-", "(không nhận dạng)") else ""
        var = StringVar(value=hint)
        ent = Entry(win, textvariable=var, bg=BG, fg=TEXT, insertbackground=TEXT,
                    font=F_MONO, width=26, relief="flat")
        ent.pack(padx=16, pady=(0, 4))
        ent.select_range(0, END)
        ent.focus_set()

        result = [""]

        def _ok(_=None):
            result[0] = var.get().strip()
            win.destroy()

        def _cancel(_=None):
            result[0] = ""
            win.destroy()

        btn_row = Frame(win, bg=CARD)
        btn_row.pack(padx=16, pady=12, fill=X)
        Button(btn_row, text="✓ Lưu", command=_ok,
               bg=ACCENT, fg="white", font=F_MAIN, relief="flat",
               padx=14, pady=4, cursor="hand2",
               activebackground="#c0401a", activeforeground="white").pack(side=LEFT, padx=(0, 8))
        Button(btn_row, text="Hủy", command=_cancel,
               bg=CARD, fg=DIM, font=F_MAIN, relief="flat",
               padx=10, pady=4, cursor="hand2",
               activebackground="#252540", activeforeground=TEXT).pack(side=LEFT)

        ent.bind("<Return>",  _ok)
        ent.bind("<Escape>",  _cancel)

        win.update_idletasks()
        cx = self.root.winfo_x() + (self.root.winfo_width()  - win.winfo_width())  // 2
        cy = self.root.winfo_y() + (self.root.winfo_height() - win.winfo_height()) // 2
        win.geometry(f"+{cx}+{cy}")
        self.root.wait_window(win)
        return result[0]

    def _mark_current(self, state: str):
        """Đánh dấu đúng/sai/bỏ cho ảnh đang chọn. state='correct'|'incorrect'|''."""
        sel = self._tree.selection()
        if not sel: return
        iid  = sel[0]
        vals = self._tree.item(iid)["values"]
        if not vals: return

        fname  = str(vals[1])
        plate  = str(vals[2])
        fpath  = self._folder_files.get(iid, "")
        folder = self._folder_var.get().strip()

        if not fpath and folder:
            fpath = os.path.join(folder, fname)

        # GT plate = nội dung textbox (ưu tiên GT sẵn có, fallback biển nhận diện)
        gt_plate = self._plate_edit_var.get().strip() or plate

        if state in ("correct", "incorrect"):
            # Copy ảnh vào _gt/dung hoặc _gt/sai
            sub = "dung" if state == "correct" else "sai"
            dest_dir = os.path.join(folder or os.path.dirname(fpath), "_gt", sub)
            os.makedirs(dest_dir, exist_ok=True)

            # Tên file đích = biển số (đã chuẩn hóa) + ext
            ext = os.path.splitext(os.path.basename(fname))[1]
            if gt_plate:
                base_name = re.sub(r"[^A-Za-z0-9]", "", gt_plate).upper() + ext
                dest = os.path.join(dest_dir, base_name)
                if os.path.exists(dest) and os.path.exists(fpath) \
                        and not os.path.samefile(fpath, dest):
                    stem_orig = os.path.splitext(os.path.basename(fname))[0]
                    base_name = re.sub(r"[^A-Za-z0-9]", "", gt_plate).upper() + "_" + stem_orig + ext
                    dest = os.path.join(dest_dir, base_name)
            else:
                dest = os.path.join(dest_dir, os.path.basename(fname))

            try:
                shutil.copy2(fpath, dest)
                # Ghi gt.txt vào folder _gt/ (KHÔNG ghi đè gt.txt nguồn)
                if gt_plate:
                    _save_gt_to_file(dest_dir, os.path.basename(dest), gt_plate)
                _append_log(self._log,
                             f"✔ {os.path.basename(fname)} → _gt/{sub}/{os.path.basename(dest)}  | GT: {gt_plate or '(chưa có)'}")
            except Exception as ex:
                _append_log(self._log, f"[LỖI] Copy: {ex}")

            # Cập nhật tree: Biển gốc + Trạng thái + GT column
            gt_cmp = _cmp_plate(plate, gt_plate)
            label  = "GT: Đúng ✓" if state == "correct" else "GT: Sai ✗"
            new_vals = list(vals)
            new_vals[3] = gt_plate          # Biển gốc
            new_vals[6] = label             # Trạng thái
            if len(new_vals) > 7:
                new_vals[7] = gt_cmp        # GT column
            self._tree.item(iid, values=new_vals)
            new_tag = "gt_ok" if state == "correct" else "gt_err"
            self._tree.item(iid, tags=(new_tag,))

            icons = {"correct": "✓ Đúng", "incorrect": "✗ Sai"}
            self._mark_lbl.config(text=icons[state],
                                  fg=(SUCCESS if state == "correct" else "#f05050"))

            self._update_filter_counts()

            # Auto-advance sang ảnh kế tiếp chưa mark
            ch = self._tree.get_children()
            if ch:
                try:
                    idx = list(ch).index(iid)
                    next_iid = None
                    for j in range(idx + 1, len(ch)):
                        if "gt_ok" not in self._tree.item(ch[j], "tags") and \
                           "gt_err" not in self._tree.item(ch[j], "tags"):
                            next_iid = ch[j]; break
                    if next_iid is None and idx > 0:
                        next_iid = ch[idx - 1]
                    elif next_iid is None:
                        next_iid = ch[min(idx, len(ch) - 1)]
                    if next_iid:
                        self._tree.selection_set(next_iid)
                        self._tree.see(next_iid)
                except (ValueError, IndexError): pass
        else:
            # Bỏ đánh dấu
            old_st = str(vals[6])
            if old_st.startswith("GT:"):
                orig_plate = str(vals[2])
                restored_st = "OK" if orig_plate and orig_plate not in ("-", "") else "Không nhận dạng"
                new_vals = list(vals); new_vals[6] = restored_st
                self._tree.item(iid, values=new_vals)
                tag = "ok" if restored_st == "OK" else "warn"
                self._tree.item(iid, tags=(tag,))
            self._mark_lbl.config(text="↺ Bỏ đánh dấu", fg=DIM)
            self._update_filter_counts()

    def _update_filter_counts(self):
        """Cập nhật số đếm trong nút filter — tính từ _all_tree_order (bỏ qua detach)."""
        all_iids = [iid for iid, _ in self._all_tree_order]
        n_all = len(all_iids)

        n_gt_match    = sum(1 for iid in all_iids
                            if len(self._tree.item(iid, "values")) > 7
                            and str(self._tree.item(iid, "values")[7]).strip() == "✓ Đúng")
        n_gt_mismatch = sum(1 for iid in all_iids
                            if len(self._tree.item(iid, "values")) > 7
                            and str(self._tree.item(iid, "values")[7]).strip() == "✗ Sai")
        n_no_gt       = n_all - n_gt_match - n_gt_mismatch
        for code, btn in self._gt_btns.items():
            btn.config(text={
                "all":      f"Tất cả ({n_all})",
                "match":    f"✓ Đúng ({n_gt_match})",
                "mismatch": f"✗ Sai ({n_gt_mismatch})",
                "no_gt":    f"Không có GT ({n_no_gt})",
            }[code])

    def _set_gt_filter(self, filter_type: str):
        self._gt_filter = filter_type
        for code, btn in self._gt_btns.items():
            btn.config(relief="sunken" if code == filter_type else "flat",
                       bg="#252540" if code == filter_type else CARD)
        self._apply_all_filters()

    def _clear_kw(self):
        self._kw_var.set("")
        self._apply_all_filters()

    def _apply_all_filters(self):
        """Tổng hợp filter: GT comparison + keyword wildcard."""
        import fnmatch
        kw = self._kw_var.get().strip()
        # Nếu không có * hay ? thì wrap thành *kw* để search substring
        if kw and "*" not in kw and "?" not in kw:
            kw_pat = f"*{kw}*"
        else:
            kw_pat = kw

        for iid in list(self._tree.get_children()):
            self._tree.detach(iid)

        for iid, _ in self._all_tree_order:
            vals = self._tree.item(iid, "values")
            tags = self._tree.item(iid, "tags")
            if not vals:
                continue

            plate  = str(vals[2]).strip()

            # --- GT filter ---
            gt_val = str(vals[7]).strip() if len(vals) > 7 else ""
            gt_pass = (
                self._gt_filter == "all" or
                (self._gt_filter == "match"    and gt_val == "✓ Đúng") or
                (self._gt_filter == "mismatch" and gt_val == "✗ Sai") or
                (self._gt_filter == "no_gt"    and gt_val == "")
            )
            if not gt_pass:
                continue

            # --- Keyword filter (wildcard trên cột biển số) ---
            if kw_pat:
                kw_ok = fnmatch.fnmatch(plate.upper(), kw_pat.upper())
                if not kw_ok:
                    continue

            self._tree.reattach(iid, "", "end")

    # ═══════════════════════════ FOLDER PREVIEW ═══════════════════════════

    def _on_tree_select(self, _=None):
        sel = self._tree.selection()
        if not sel:
            self._clear_fpreview()
            self._mark_lbl.config(text=""); return
        iid  = sel[0]
        vals = self._tree.item(iid)["values"]
        if not vals: return
        fname  = str(vals[1]); plate = str(vals[2]); ms = str(vals[5])
        fpath  = self._folder_files.get(iid, "")
        folder = self._folder_var.get().strip()
        if not fpath and folder: fpath = os.path.join(folder, fname)

        info = plate if plate and plate not in ("-", "") else "(không nhận dạng)"
        if ms and ms != "-": info += f"   {ms}ms"
        self._prev_lbl.config(text=info)

        # Điền textbox: ưu tiên GT (col 3), fallback biển nhận diện
        gt_orig = str(vals[3]).strip() if len(vals) > 3 else ""
        self._plate_edit_var.set(
            gt_orig if gt_orig and gt_orig not in ("-", "")
            else (plate if plate and plate not in ("-", "") else "")
        )

        # Hiển thị diff biển nhận diện vs GT (col 3)
        gt_col = str(vals[3]).strip() if len(vals) > 3 else ""
        self._update_diff_display(plate, gt_col)

        # Cập nhật mark label
        state = self._review_state.get(fpath, "")
        if state == "correct":
            self._mark_lbl.config(text="✓ Đúng", fg=SUCCESS)
        elif state == "incorrect":
            self._mark_lbl.config(text="✗ Sai", fg="#f05050")
        else:
            tags = self._tree.item(iid, "tags")
            if "gt_ok" in tags:
                self._mark_lbl.config(text="✓ Đúng", fg=SUCCESS)
            elif "gt_err" in tags:
                self._mark_lbl.config(text="✗ Sai", fg="#f05050")
            else:
                self._mark_lbl.config(text="○ Chưa đánh dấu", fg=DIM)

        lpi = self._folder_lpr.get(iid)
        if lpi and _PIL_OK:
            self._show_img(self._pic_fp, lpi, 500, 138)
        else:
            self._pic_fp.config(image="", text="(biển số)")

        if fpath and os.path.isfile(fpath) and _PIL_OK:
            try:
                img  = Image.open(fpath)
                bbox = self._folder_bbox.get(iid)
                if bbox:
                    img = _draw_bbox_on_pil(img, bbox)
                self._show_img(self._pic_fv, img, 300, 180)
                img.close(); return
            except Exception: pass
        self._pic_fv.config(image="", text="(ảnh xe)")

    def _on_tree_dbl(self, _=None):
        sel = self._tree.selection()
        if not sel or not _PIL_OK: return
        iid   = sel[0]
        fpath = self._folder_files.get(iid, "")
        if fpath and os.path.isfile(fpath):
            try: _zoom_image_window(self.root, Image.open(fpath), os.path.basename(fpath))
            except Exception: pass

    def _on_tree_click(self, event):
        """Xử lý click vào cột 📂 hoặc 📋."""
        col_id = self._tree.identify_column(event.x)   # '#1', '#2', ...
        row_id = self._tree.identify_row(event.y)
        if not row_id: return
        col_num = int(col_id.lstrip("#"))               # 1-based
        cols = self._tree["columns"]
        if col_num < 1 or col_num > len(cols): return
        col_name = cols[col_num - 1]
        if col_name == "📂":
            self._flash_row(row_id, "#1a4a1a")
            self._open_file_location(row_id)
        elif col_name == "📋":
            self._flash_row(row_id, "#1a1a4a")
            self._copy_file_to_clipboard(row_id)

    def _open_file_location(self, iid: str):
        """Mở Explorer đến thư mục chứa file và chọn file đó."""
        fpath = self._folder_files.get(iid, "")
        if not fpath:
            vals = self._tree.item(iid, "values")
            fname = str(vals[1]) if vals else ""
            fpath = os.path.join(self._batch_folder, fname)
        if os.path.isfile(fpath):
            import subprocess
            subprocess.Popen(["explorer", "/select,", os.path.normpath(fpath)])
        elif os.path.isdir(os.path.dirname(fpath)):
            os.startfile(os.path.dirname(fpath))

    def _copy_file_to_clipboard(self, iid: str):
        """Copy ảnh vào Windows clipboard (CF_DIB format)."""
        fpath = self._folder_files.get(iid, "")
        if not fpath:
            vals = self._tree.item(iid, "values")
            fname = str(vals[1]) if vals else ""
            fpath = os.path.join(self._batch_folder, fname)
        if not os.path.isfile(fpath):
            _append_log(self._log, f"⚠ Không tìm thấy file: {fpath}"); return
        try:
            import ctypes, io as _io
            from PIL import Image as _Img
            # Đọc ảnh → BMP bytes → bỏ 14-byte file header → DIB
            img = _Img.open(fpath).convert("RGB")
            buf = _io.BytesIO()
            img.save(buf, format="BMP")
            dib = buf.getvalue()[14:]
            buf.close(); img.close()

            k32 = ctypes.windll.kernel32
            u32 = ctypes.windll.user32
            # Phải khai báo restype đúng (c_void_p) để tránh truncate con trỏ 64-bit
            k32.GlobalAlloc.restype   = ctypes.c_void_p
            k32.GlobalAlloc.argtypes  = [ctypes.c_uint, ctypes.c_size_t]
            k32.GlobalLock.restype    = ctypes.c_void_p
            k32.GlobalLock.argtypes   = [ctypes.c_void_p]
            k32.GlobalUnlock.argtypes = [ctypes.c_void_p]
            k32.GlobalFree.restype    = ctypes.c_void_p
            k32.GlobalFree.argtypes   = [ctypes.c_void_p]
            u32.OpenClipboard.argtypes   = [ctypes.c_void_p]
            u32.SetClipboardData.restype  = ctypes.c_void_p
            u32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]

            GMEM_MOVEABLE = 0x0002
            hMem = k32.GlobalAlloc(GMEM_MOVEABLE, len(dib))
            if not hMem:
                raise RuntimeError("GlobalAlloc thất bại")
            pMem = k32.GlobalLock(hMem)
            if not pMem:
                k32.GlobalFree(hMem)
                raise RuntimeError("GlobalLock thất bại")
            ctypes.memmove(pMem, dib, len(dib))
            k32.GlobalUnlock(hMem)

            if not u32.OpenClipboard(None):
                k32.GlobalFree(hMem)
                raise RuntimeError("OpenClipboard thất bại")
            u32.EmptyClipboard()
            u32.SetClipboardData(8, hMem)   # CF_DIB = 8
            u32.CloseClipboard()
            _append_log(self._log, f"📋 Đã copy: {os.path.basename(fpath)}")
        except Exception as ex:
            _append_log(self._log, f"[LỖI] Copy clipboard: {ex}")

    def _update_diff_display(self, plate: str, gt: str):
        """Hiển thị diff ký tự giữa biển nhận diện và GT trong _diff_txt."""
        import difflib as _diff
        tw = self._diff_txt
        tw.config(state=NORMAL)
        tw.delete("1.0", END)
        norm = lambda s: re.sub(r"[^A-Za-z0-9]", "", s).upper()
        p = norm(plate); g = norm(gt)
        tw.tag_config("same",   foreground="#4caf50")
        tw.tag_config("diff_p", foreground="#f05050")
        tw.tag_config("diff_g", foreground="#f05050")
        tw.tag_config("lbl",    foreground=DIM)
        if not g:
            # Không có GT: hiện biển nhận diện, không tô màu
            if p:
                tw.insert(END, "Nhận dạng: ", "lbl")
                tw.insert(END, p, "same")
            tw.config(state=DISABLED); return
        matcher = _diff.SequenceMatcher(None, p, g, autojunk=False)
        tw.insert(END, "Nhận dạng: ", "lbl")
        for op, i1, i2, j1, j2 in matcher.get_opcodes():
            tw.insert(END, p[i1:i2], "same" if op == "equal" else "diff_p")
        tw.insert(END, "\n")
        tw.insert(END, "GT:        ", "lbl")
        for op, i1, i2, j1, j2 in matcher.get_opcodes():
            tw.insert(END, g[j1:j2], "same" if op == "equal" else "diff_g")
        tw.config(state=DISABLED)

    def _open_gt_folder(self, sub: str):
        """Mở thư mục _gt/dung hoặc _gt/sai trong Explorer."""
        folder = self._folder_var.get().strip()
        if not folder:
            _append_log(self._log, "⚠ Chưa chọn thư mục nguồn."); return
        gt_dir = os.path.join(folder, "_gt", sub)
        os.makedirs(gt_dir, exist_ok=True)
        import subprocess
        subprocess.Popen(["explorer", os.path.normpath(gt_dir)])

    def _clear_folder_cache(self):
        """Xóa file cache .kztek_lpr_cache.json trong thư mục hiện tại."""
        folder = self._folder_var.get().strip()
        if not folder:
            _append_log(self._log, "⚠ Chưa chọn thư mục."); return
        import json as _json
        cache_path = os.path.join(folder, ".kztek_lpr_cache.json")
        try:
            os.remove(cache_path)
            _append_log(self._log, f"🗑 Đã xóa cache: {cache_path}")
        except FileNotFoundError:
            _append_log(self._log, "Cache chưa có hoặc đã bị xóa.")
        except Exception as ex:
            _append_log(self._log, f"[LỖI] Xóa cache: {ex}")

    def _flash_row(self, iid: str, color: str, ms: int = 300):
        """Nhấp nháy màu nền tạm thời cho row iid rồi phục hồi sau ms ms."""
        if not self._tree.exists(iid): return
        orig_tags = self._tree.item(iid, "tags")
        self._tree.tag_configure("_flash_tmp", background=color)
        self._tree.item(iid, tags=("_flash_tmp",))
        def _restore(tags=orig_tags):
            try:
                if self._tree.exists(iid):
                    self._tree.item(iid, tags=tags)
            except Exception: pass
        self.root.after(ms, _restore)

    def _save_sash(self, _=None):
        try:
            if hasattr(self, "_hpw_result"):
                x, _ = self._hpw_result.sash_coord(0)
                _CFG["lpr.result_hsash"] = x
                _cfg_save()
        except Exception: pass

    def _restore_sash(self):
        try:
            v = _CFG.get("lpr.result_hsash")
            if v is not None and hasattr(self, "_hpw_result"):
                self._hpw_result.sash_place(0, int(v), 0)
        except Exception: pass

    def _save_plate_edit(self):
        """Lưu biển GT từ textbox vào gt.txt và cập nhật cây."""
        sel = self._tree.selection()
        if not sel: return
        new_gt = self._plate_edit_var.get().strip()
        if not new_gt: return
        iid  = sel[0]
        vals = list(self._tree.item(iid)["values"])
        if not vals: return
        plate = str(vals[2])
        fname = str(vals[1])
        fpath = self._folder_files.get(iid, "")
        folder = self._folder_var.get().strip()
        if not fpath and folder:
            fpath = os.path.join(folder, fname)
        src_folder = os.path.dirname(fpath) if fpath else folder
        try:
            # Lưu vào gt.txt format: <filename>\t<plate>
            _save_gt_to_file(src_folder, os.path.basename(fname), new_gt)
            gt_cmp = _cmp_plate(plate, new_gt)
            vals[3] = new_gt
            if len(vals) > 7:
                vals[7] = gt_cmp
            if gt_cmp == "✓ Đúng":
                vals[6] = "GT: Đúng ✓"
                self._tree.item(iid, values=vals, tags=("gt_ok",))
            elif gt_cmp == "✗ Sai":
                vals[6] = "GT: Sai ✗"
                self._tree.item(iid, values=vals, tags=("gt_err",))
            else:
                self._tree.item(iid, values=vals)
            self._update_filter_counts()
            _push_history("h.lpr.plate_edit", new_gt)
            self._plate_edit["values"] = _get_history("h.lpr.plate_edit")
            self._update_diff_display(plate, new_gt)
            _append_log(self._log, f"✔ GT lưu: {new_gt}  ({fname})")
        except Exception as ex:
            _append_log(self._log, f"[LỖI] Lưu GT: {ex}")

    def _clear_fpreview(self):
        self._pic_fv.config(image="", text="(ảnh xe)")
        self._pic_fp.config(image="", text="(biển số)")
        self._prev_lbl.config(text="(chọn dòng trong bảng để xem ảnh)")
        self._update_diff_display("", "")

    def _zoom_fv(self):
        sel = self._tree.selection()
        if not sel or not _PIL_OK: return
        iid   = sel[0]
        fpath = self._folder_files.get(iid, "")
        if fpath and os.path.isfile(fpath):
            try:
                img  = Image.open(fpath)
                bbox = self._folder_bbox.get(iid)
                if bbox:
                    img = _draw_bbox_on_pil(img, bbox)
                _zoom_image_window(self.root, img, os.path.basename(fpath))
            except Exception: pass

    def _zoom_fp(self):
        sel = self._tree.selection()
        if not sel: return
        lpi = self._folder_lpr.get(sel[0])
        if lpi: _zoom_image_window(self.root, lpi, "Biển số")

    # ═══════════════════════════ EXPORT ═══════════════════════════════════

    def _export(self, _=None):
        if not self._tree.get_children():
            messagebox.showinfo("Thông báo", "Không có dữ liệu để xuất."); return
        from datetime import datetime
        path = filedialog.asksaveasfilename(
            title="Xuất kết quả CSV", defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("Tất cả", "*.*")],
            initialfile=f"lpr_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        if not path: return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(["STT", "Tên file", "Biển số", "Biển gốc",
                             "Loại xe", "Thời gian (ms)", "Trạng thái", "So sánh GT"])
                for iid in self._all_tree_order:
                    iid = iid[0]
                    w.writerow(self._tree.item(iid)["values"][:8])  # bỏ cột 📂 📋
            n = len(self._all_tree_order)
            _append_log(self._log, f"✔ Đã xuất {n} dòng → {path}")
            messagebox.showinfo("Xuất CSV", f"Xuất thành công {n} dòng.")
        except Exception as ex:
            _append_log(self._log, f"[LỖI] Xuất CSV: {ex}")

    # ═══════════════════════════ HELPERS ══════════════════════════════════

    @staticmethod
    def _show_img(widget: Label, pil_img, max_w: int, max_h: int):
        if not _PIL_OK or pil_img is None: return
        try:
            img = pil_img.copy()
            img.thumbnail((max_w, max_h), Image.LANCZOS)
            tk_img = ImageTk.PhotoImage(img)
            widget.config(image=tk_img, text="")
            widget._tk_img = tk_img
        except Exception: pass

    def _is_active(self) -> bool:
        try:
            w = self
            while w is not None:
                p = getattr(w, "master", None)
                if p is None: break
                if isinstance(p, ttk.Notebook):
                    return p.select() == str(w)
                w = p
        except Exception: pass
        return False

    # ═══════════════════════════ APP SHORTCUTS ════════════════════════════

    def _run(self):
        if self._pil_single is not None or self._loaded_path:
            self._detect_single()
        else:
            self._start()

    def _browse(self):   self._load_image()
    def _save(self):     self._export()

    def _on_return(self):
        """Enter → đánh dấu Đúng (chỉ khi tab này active)."""
        if self._is_active():
            self._mark_current("correct")

    def _on_delete(self):
        """Del → đánh dấu Sai (chỉ khi tab này active)."""
        if self._is_active():
            self._mark_current("incorrect")

    def _prev_image(self):
        ch = self._tree.get_children()
        if not ch: return
        sel = self._tree.selection()
        idx = list(ch).index(sel[0]) if sel else 1
        t = ch[max(0, idx - 1)]
        self._tree.selection_set(t); self._tree.see(t)

    def _next_image(self):
        ch = self._tree.get_children()
        if not ch: return
        sel = self._tree.selection()
        idx = list(ch).index(sel[0]) if sel else -1
        t = ch[min(len(ch) - 1, idx + 1)]
        self._tree.selection_set(t); self._tree.see(t)

    # ══════════════════════════════════ SINGLE-IMAGE 4-POINT CROP ══════════

    def _render_single(self):
        if not self._pil_single or not _PIL_OK:
            return
        cv = self._pic_vehicle
        cv.update_idletasks()
        cw = max(cv.winfo_width(),  100)
        ch = max(cv.winfo_height(), 100)
        scale = min(cw / self._pil_single.width, ch / self._pil_single.height)
        nw = max(1, int(self._pil_single.width  * scale))
        nh = max(1, int(self._pil_single.height * scale))
        self._sv_scale  = scale
        self._sv_off_x  = (cw - nw) // 2
        self._sv_off_y  = (ch - nh) // 2
        resized = self._pil_single.resize((nw, nh), Image.LANCZOS)
        tk_img  = ImageTk.PhotoImage(resized)
        cv.delete("all")
        cv.create_image(self._sv_off_x, self._sv_off_y,
                        anchor=NW, image=tk_img, tags="img")
        cv._tk_img = tk_img
        if self._lpr4_active and self._lpr4_pts:
            self._sv_draw_4pt()
        if self._sv_result_bbox:
            self._render_bbox_overlay()

    def _render_bbox_overlay(self):
        """Vẽ bbox detect đơn lên canvas ảnh xe (canvas rect, không sửa PIL)."""
        cv = self._pic_vehicle
        cv.delete("bbox_ov")
        if not self._sv_result_bbox or not self._pil_single:
            return
        x1, y1, x2, y2 = _parse_bbox_coords(self._sv_result_bbox)
        if x2 <= x1 or y2 <= y1:
            return
        cx1 = x1 * self._sv_scale + self._sv_off_x
        cy1 = y1 * self._sv_scale + self._sv_off_y
        cx2 = x2 * self._sv_scale + self._sv_off_x
        cy2 = y2 * self._sv_scale + self._sv_off_y
        cv.create_rectangle(cx1, cy1, cx2, cy2,
                            outline=ACCENT, width=2, tags="bbox_ov")

    def _sv_c2i(self, cx, cy):
        if self._sv_scale == 0:
            return 0.0, 0.0
        ix = (cx - self._sv_off_x) / self._sv_scale
        iy = (cy - self._sv_off_y) / self._sv_scale
        if self._pil_single:
            ix = max(0.0, min(float(self._pil_single.width),  ix))
            iy = max(0.0, min(float(self._pil_single.height), iy))
        return ix, iy

    def _sv_i2c(self, ix, iy):
        return (ix * self._sv_scale + self._sv_off_x,
                iy * self._sv_scale + self._sv_off_y)

    def _sv_pt_hit_test(self, cx, cy):
        r = max(6, 5 + self.v_lpr4_line_w.get()) + 5
        for i, (ix, iy) in enumerate(self._lpr4_pts):
            pcx, pcy = self._sv_i2c(ix, iy)
            if abs(cx - pcx) <= r and abs(cy - pcy) <= r:
                return i
        return None

    def _sv_draw_4pt(self):
        cv = self._pic_vehicle
        cv.delete("4pt")
        n     = len(self._lpr4_pts)
        pts_c = [self._sv_i2c(ix, iy) for ix, iy in self._lpr4_pts]
        lw    = max(1, self.v_lpr4_line_w.get())
        _DOT_COLORS = [ACCENT, "#4fc3f7", "#81c784", "#fff176"]

        if n >= 2:
            flat = [c for pt in pts_c for c in pt]
            if n >= 3:
                cv.create_polygon(flat, outline=ACCENT, fill="",
                                  width=lw, dash=(5, 3), tags="4pt")
            else:
                cv.create_line(flat, fill=ACCENT, width=lw, dash=(5, 3), tags="4pt")

        r = max(6, 5 + lw)
        for i, (pcx, pcy) in enumerate(pts_c):
            cv.create_oval(pcx - r, pcy - r, pcx + r, pcy + r,
                           fill=_DOT_COLORS[i % 4], outline="white", width=1, tags="4pt")
            cv.create_text(pcx, pcy, text=str(i + 1),
                           fill="white", font=("Segoe UI", 7, "bold"), tags="4pt")

        if n < 4:
            self._sv4pt_lbl.config(
                text=f"{n}/4 điểm  — click để thêm  |  chuột phải: xóa điểm cuối",
                fg=DIM)

    def _sv_clear_4pt(self):
        try:
            self._pic_vehicle.delete("4pt")
        except Exception:
            pass
        self._lpr4_pts     = []
        self._lpr4_drag_idx = None
        self._lpr4_pil     = None
        self._sv4pt_lbl.config(text="")

    def _sv_redraw_overlay(self, _=None):
        if self._lpr4_active and self._lpr4_pts:
            self._sv_draw_4pt()

    def _sv_toggle_4pt(self):
        self._lpr4_active = not self._lpr4_active
        if self._lpr4_active:
            self._btn_sv4pt.config(relief="sunken", bg="#252540")
            self._pic_vehicle.config(cursor="crosshair")
            self._sv4pt_lbl.config(text="0/4 điểm  — click góc để thêm  |  chuột phải: xóa", fg=DIM)
        else:
            self._btn_sv4pt.config(relief="flat", bg=CARD)
            self._pic_vehicle.config(
                cursor="crosshair" if self._pil_single else "hand2")
            self._sv_clear_4pt()

    # ── Canvas events ──────────────────────────────────────────────────────

    def _on_sv_press(self, e):
        if not self._pil_single:
            self._load_image(); return

        if self._lpr4_active:
            # Kéo điểm cũ?
            if self._lpr4_pts:
                hit = self._sv_pt_hit_test(e.x, e.y)
                if hit is not None:
                    self._lpr4_drag_idx = hit
                    return
            # Thêm điểm mới
            if len(self._lpr4_pts) >= 4:
                self._sv_clear_4pt()
            ix, iy = self._sv_c2i(e.x, e.y)
            self._lpr4_pts.append((ix, iy))
            self._sv_draw_4pt()
            if len(self._lpr4_pts) == 4:
                self._sv_apply_persp()

    def _on_sv_drag(self, e):
        if not self._lpr4_active or self._lpr4_drag_idx is None:
            return
        ix, iy = self._sv_c2i(e.x, e.y)
        self._lpr4_pts[self._lpr4_drag_idx] = (ix, iy)
        self._sv_draw_4pt()

    def _on_sv_release(self, e):
        if not self._lpr4_active or self._lpr4_drag_idx is None:
            return
        ix, iy = self._sv_c2i(e.x, e.y)
        self._lpr4_pts[self._lpr4_drag_idx] = (ix, iy)
        self._lpr4_drag_idx = None
        self._sv_draw_4pt()
        if len(self._lpr4_pts) == 4:
            self._sv_apply_persp()

    def _on_sv_motion(self, e):
        if not self._lpr4_active:
            return
        hit = self._sv_pt_hit_test(e.x, e.y) if self._lpr4_pts else None
        self._pic_vehicle.config(cursor="fleur" if hit is not None else "crosshair")

    def _on_sv_rclick(self, e):
        if self._lpr4_active and self._lpr4_pts:
            self._lpr4_pts.pop()
            self._lpr4_pil = None
            self._sv_draw_4pt()

    def _on_sv_dbl(self, e):
        if self._lpr4_pil:
            _zoom_image_window(self.root, self._lpr4_pil, "4-pt crop")
        elif self._pil_single:
            target = self._pil_single
            if self._sv_result_bbox:
                target = _draw_bbox_on_pil(target, self._sv_result_bbox)
            _zoom_image_window(self.root, target, "Ảnh xe")

    # ── Perspective warp ───────────────────────────────────────────────────

    def _sv_apply_persp(self):
        if not self._pil_single or len(self._lpr4_pts) != 4:
            return
        s = sorted(self._lpr4_pts, key=lambda p: p[1])
        top = sorted(s[:2], key=lambda p: p[0])
        bot = sorted(s[2:], key=lambda p: p[0])
        ordered  = [top[0], top[1], bot[1], bot[0]]
        pil_full = self._pil_single

        def _compute():
            try:
                warped = _warp_perspective_lpr(pil_full, ordered)
                self.root.after(0, lambda w=warped: self._sv_persp_done(w))
            except Exception as ex:
                self.root.after(0, lambda e=str(ex): _append_log(
                    self._log, f"[LỖI] 4-pt warp: {e}"))

        threading.Thread(target=_compute, daemon=True).start()

    def _sv_persp_done(self, warped):
        self._lpr4_pil = warped
        self._show_img(self._pic_lpr, warped, 360, 80)
        self._sv4pt_lbl.config(
            text=f"✔ Crop {warped.width}×{warped.height}  — F5 để nhận dạng",
            fg=SUCCESS)
        if self._auto_var.get():
            self.root.after(50, self._detect_single)


# ════════════════════════ MODULE-LEVEL API HELPERS ════════════════════════

def _parse_bbox_coords(bbox) -> tuple:
    """Trả về (x1, y1, x2, y2) từ bbox dict hoặc list/tuple."""
    if isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
        return int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
    if isinstance(bbox, dict):
        x1 = int(bbox.get("xmin", bbox.get("Xmin", 0)))
        y1 = int(bbox.get("ymin", bbox.get("Ymin", 0)))
        x2 = int(bbox.get("xmax", bbox.get("Xmax", 0)))
        y2 = int(bbox.get("ymax", bbox.get("Ymax", 0)))
        return x1, y1, x2, y2
    return 0, 0, 0, 0


def _draw_bbox_on_pil(pil_img, bbox) -> "Image.Image":
    """Vẽ bbox lên bản copy của PIL image bằng ImageDraw."""
    if not _PIL_OK or not bbox:
        return pil_img
    try:
        from PIL import ImageDraw
        x1, y1, x2, y2 = _parse_bbox_coords(bbox)
        if x2 <= x1 or y2 <= y1:
            return pil_img
        img  = pil_img.copy()
        draw = ImageDraw.Draw(img)
        lw   = max(2, min(img.width, img.height) // 120)
        draw.rectangle([x1, y1, x2, y2], outline="#F05922", width=lw)
        return img
    except Exception:
        return pil_img


def _save_gt_to_file(folder: str, fname: str, plate: str):
    """Ghi/cập nhật gt.txt trong folder với format: <filename>\t<plate>"""
    gt_path = os.path.join(folder, "gt.txt")
    entries: dict = {}
    if os.path.isfile(gt_path):
        try:
            with open(gt_path, encoding="utf-8-sig") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"): continue
                    parts = line.split("\t", 1)
                    if len(parts) == 2:
                        entries[parts[0]] = parts[1].strip()
        except Exception: pass
    entries[fname] = plate
    with open(gt_path, "w", encoding="utf-8") as f:
        for k in sorted(entries):
            f.write(f"{k}\t{entries[k]}\n")


def _load_gt(img_path: str) -> str:
    """Đọc GT plate cho ảnh.
    Thứ tự tìm:
      1. gt.txt trong cùng thư mục  (format: '<filename>\\t<plate>')
      2. <tên_ảnh>.txt cùng thư mục (fallback format cũ)
    """
    folder = os.path.dirname(img_path)
    fname  = os.path.basename(img_path)

    # 1. gt.txt chung (ưu tiên)
    gt_file = os.path.join(folder, "gt.txt")
    if os.path.isfile(gt_file):
        try:
            with open(gt_file, encoding="utf-8-sig") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"): continue
                    parts = line.split("\t", 1)
                    if len(parts) == 2 and parts[0] == fname:
                        return parts[1].strip()
        except Exception: pass

    # 2. File .txt riêng cùng tên (fallback)
    txt = os.path.splitext(img_path)[0] + ".txt"
    if os.path.isfile(txt):
        try:
            with open(txt, encoding="utf-8-sig") as f:
                return f.read().strip()
        except Exception: pass

    return ""


def _cmp_plate(plate: str, gt: str) -> str:
    """So sánh biển số nhận dạng với GT. Trả về '✓ Đúng', '✗ Sai', hoặc '' nếu không có GT."""
    if not gt:
        return ""
    norm = lambda s: re.sub(r"[^A-Za-z0-9]", "", s).upper()
    p = norm(plate)
    g = norm(gt)
    if not p and not g:
        return ""
    return "✓ Đúng" if p == g else "✗ Sai"


def _warp_perspective_lpr(pil_img, pts4):
    """Warp quadrilateral (TL,TR,BR,BL) → rectangle. Returns PIL.Image."""
    import math
    def _d(a, b): return math.hypot(b[0]-a[0], b[1]-a[1])
    tl, tr, br, bl = pts4
    W = max(1, int(max(_d(tl, tr), _d(bl, br))))
    H = max(1, int(max(_d(tl, bl), _d(tr, br))))
    try:
        import cv2, numpy as np
        src = np.float32([[p[0], p[1]] for p in pts4])
        dst = np.float32([[0, 0], [W, 0], [W, H], [0, H]])
        M   = cv2.getPerspectiveTransform(src, dst)
        arr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        out = cv2.warpPerspective(arr, M, (W, H))
        return Image.fromarray(cv2.cvtColor(out, cv2.COLOR_BGR2RGB))
    except ImportError:
        pass
    try:
        import numpy as np
        A, b = [], []
        for (xs, ys), (xd, yd) in zip(pts4, [(0,0),(W,0),(W,H),(0,H)]):
            A.append([xd, yd, 1, 0, 0, 0, -xs*xd, -xs*yd])
            A.append([0,  0,  0, xd, yd, 1, -ys*xd, -ys*yd])
            b.extend([xs, ys])
        coeffs = tuple(np.linalg.lstsq(np.array(A), np.array(b), rcond=None)[0])
        return pil_img.transform((W, H), Image.PERSPECTIVE, coeffs, Image.BICUBIC)
    except Exception:
        pass
    x1 = int(min(p[0] for p in pts4)); y1 = int(min(p[1] for p in pts4))
    x2 = int(max(p[0] for p in pts4)); y2 = int(max(p[1] for p in pts4))
    return pil_img.crop((x1, y1, x2, y2))


def _api_call_pil(pil_img, url, timeout, mode, lpr_type) -> tuple:
    if not _REQ_OK or not _PIL_OK:
        return {}, "requests hoặc Pillow chưa cài"
    try:
        buf = BytesIO()
        img = pil_img if pil_img.mode in ("RGB", "L") else pil_img.convert("RGB")
        img.save(buf, format="JPEG", quality=90)
        buf.seek(0)
        return _api_call_bytes(buf.read(), url, timeout, mode, lpr_type, ".jpg")
    except Exception as ex:
        return {}, str(ex)


def _api_call_file(fpath, url, timeout, mode, lpr_type) -> tuple:
    if not _REQ_OK:
        return {}, "requests chưa cài"
    try:
        with open(fpath, "rb") as f:
            data = f.read()
        ext = os.path.splitext(fpath)[1].lower()
        return _api_call_bytes(data, url, timeout, mode, lpr_type, ext)
    except Exception as ex:
        return {}, str(ex)


def _api_call_bytes(data: bytes, url: str, timeout: int,
                    mode: str, lpr_type: str, ext: str) -> tuple:
    mime  = _MIME.get(ext, "image/jpeg")
    field = "upload"  # Kztek /alpr và OpenALPR đều dùng "upload"
    try:
        files = {field: (f"img{ext}", data, mime)}
        resp  = _get_session().post(url, files=files, timeout=timeout)
        resp.raise_for_status()
        try:
            raw = resp.json()
        except Exception:
            raw = {"plate": resp.text.strip()}
        return _parse_lpr_response(raw), None
    except requests.Timeout:
        return {}, f"Timeout ({timeout}s)"
    except requests.ConnectionError:
        return {}, "Không kết nối được server"
    except requests.HTTPError as ex:
        body = ex.response.text[:120] if ex.response is not None else ""
        return {}, f"HTTP {ex.response.status_code}: {body}"
    except Exception as ex:
        return {}, str(ex)
