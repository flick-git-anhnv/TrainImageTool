# tab_yolo.py — YOLO Detection tab
import fnmatch
import os
import queue as _q
import threading
import time
from tkinter import *
from tkinter import filedialog, messagebox, ttk

from ...core.constants import (BG, CARD, ACCENT, ACCENT2, TEXT, DIM, SUCCESS,
                         F_MAIN, F_BOLD, F_MONO, IMAGE_EXTENSIONS)
import shutil
from ...core.settings import _bind_cfg, _cfg_dir, _CFG, _cfg_save, _bind_history, _push_history, _get_history
from ...core.ui_helpers import GridPageNav

try:
    from PIL import Image, ImageDraw, ImageTk
    _PIL_OK = True
except ImportError:
    _PIL_OK = False

try:
    import cv2
    import numpy as np
    _CV2_OK = True
except ImportError:
    _CV2_OK = False

try:
    from ultralytics import YOLO
    _YOLO_OK = True
except ImportError:
    _YOLO_OK = False

try:
    from tkinterdnd2 import DND_FILES
    _DND_OK = True
except ImportError:
    _DND_OK = False

try:
    import requests as _requests
    _REQ_OK = True
except ImportError:
    _REQ_OK = False

_REVIEW_ICON = {"correct": "✓", "incorrect": "✗", "": "○"}

_THUMB_PALETTE = [
    "#F05922", "#4caf50", "#2196f3", "#9c27b0", "#ff9800",
    "#00bcd4", "#e91e63", "#8bc34a", "#ff5722", "#607d8b",
]


def _contrast_text(bg_rgb: tuple) -> tuple:
    """Trả về (0,0,0) hoặc (255,255,255) tuỳ độ sáng của màu nền."""
    r, g, b = bg_rgb
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    return (0, 0, 0) if lum > 150 else (255, 255, 255)


class YoloTab(Frame):
    def __init__(self, master, root):
        super().__init__(master, bg=BG)
        self.root = root

        self.current_image_path = None
        self.model = None
        self.model2 = None
        self.class_ids = []
        self.image_list = []
        self._photo_ref = None
        self._photo_ref2 = None
        self._last_annotated_bgr = None

        self.v_model_path    = StringVar()
        self.v_model2_path   = StringVar()
        self.v_subfolder     = BooleanVar(value=False)
        self.v_show_original = BooleanVar(value=False)
        self.v_check_folder  = StringVar()
        self.v_wrong_folder  = StringVar()
        self._v_wf_segs  = [StringVar() for _ in range(5)]
        self._wf_combos  = []
        self.v_conf_thresh   = DoubleVar(value=0.25)
        self.v_conf          = DoubleVar(value=0.30)
        self.v_iou           = DoubleVar(value=0.45)
        self.v_interval      = StringVar(value="2.0")
        self.v_line_width    = IntVar(value=2)
        self.v_font_size     = IntVar(value=11)
        self.v_export_draw   = BooleanVar(value=True)
        self.v_export_rename = BooleanVar(value=False)
        self._v_search       = StringVar()
        self._pil1_full = None
        self._pil1_orig = None
        self._pil2_full = None
        self._last_results1 = None
        self._zoom_factor = 0.0
        self._img_pos     = [0, 0]   # vị trí ảnh trên canvas (top-left)
        self._pan_start   = None     # điểm bắt đầu kéo chuột (left drag)
        self._pan_origin  = [0, 0]   # _img_pos tại lúc bắt đầu kéo
        self._mmb_pan_start  = None  # middle mouse / Ctrl+drag pan
        self._mmb_pan_origin = [0, 0]
        self._search_after = None
        self._autoplay_id = None
        self._last_n_det = -1
        self._tree_iid_map = {}
        self._path_to_iid = {}
        self._all_images = []
        self._base_folder = None
        self._active_filter = "all"
        self._review_state = dict(_CFG.get("yolo.review_states", {}))

        # Detect All cache & filters
        # box tuple: (cid, cx_n, cy_n, w_n, h_n, w_px, h_px, conf_score)  ← indices 0-7
        self._det_cache = {}
        self._det_cache_lock = threading.Lock()
        self._det_stop_flag = False
        self._det_running = False
        self._detecting   = False   # True khi single-image detect đang chạy
        self._det_pending = False   # re-detect queued sau khi detect xong
        self._plot_after  = None    # debounce id cho _on_plot_param_change
        self._flt_class_var = StringVar(value="Tất cả")
        self._flt_ndet_min_var = StringVar(value="")
        self._flt_ndet_max_var = StringVar(value="")
        self._flt_area_min_var = StringVar(value="")
        self._flt_area_max_var = StringVar(value="")
        self._flt_w_min_var = StringVar(value="")
        self._flt_w_max_var = StringVar(value="")
        self._flt_h_min_var = StringVar(value="")
        self._flt_h_max_var = StringVar(value="")
        self._flt_schedule_after = None

        # Grid panel (filmstrip)
        self._grid_page = 0
        self._grid_cols_var = IntVar(value=4)
        self._grid_rows_var = IntVar(value=4)
        self._grid_thumb_w = 0
        self._grid_thumb_h = 0
        self._grid_rendered_cache = {}
        self._grid_cells = []
        self._grid_render_idx = 0
        self._grid_rebuild_after = None
        self._grid_reflow_after  = None
        self._session_restored = False

        # LPR check (kiểm tra biển số sau detect)
        self.v_check_lpr      = BooleanVar(value=False)
        self._lpr_timeout_var = IntVar(value=10)
        self._lpr_url_vars    = [StringVar(value="http://localhost:8000/alpr"),
                                 StringVar(value=""),
                                 StringVar(value="")]
        self._lpr_url_combos  = [None, None, None]  # set in _build_toolbar
        self._lpr_fullimg_vars = [BooleanVar(value=False),
                                  BooleanVar(value=False),
                                  BooleanVar(value=False)]
        self._lpr_conn_lbl           = None   # set in _build_toolbar
        self._lpr_font_size_var      = IntVar(value=28)
        self.v_lpr_batch             = BooleanVar(value=False)
        self._lpr_cache              = {}     # {path: [(x1,y1,x2,y2,plate),...]}
        self._lpr_cache_lock         = threading.Lock()
        self._flt_lpr_var            = StringVar(value="Tất cả")
        self._last_lpr_plates_result = []     # [(x1,y1,x2,y2,plate), ...] từ lần overlay gần nhất

        _bind_cfg("yolo.model_path",    self.v_model_path)
        _bind_cfg("yolo.check_folder",  self.v_check_folder)
        _bind_cfg("yolo.conf_thresh",   self.v_conf_thresh)
        _bind_cfg("yolo.conf",          self.v_conf)
        _bind_cfg("yolo.iou",           self.v_iou)
        _bind_cfg("yolo.interval",      self.v_interval)
        _bind_cfg("yolo.subfolder",     self.v_subfolder)
        _bind_cfg("yolo.show_original", self.v_show_original)
        _bind_cfg("yolo.line_width",     self.v_line_width)
        _bind_cfg("yolo.font_size",      self.v_font_size)
        _bind_cfg("yolo.export_draw",   self.v_export_draw)
        _bind_cfg("yolo.export_rename", self.v_export_rename)
        _bind_cfg("yolo.grid_cols",     self._grid_cols_var)
        _bind_cfg("yolo.grid_rows",     self._grid_rows_var)
        _bind_cfg("yolo.check_lpr",      self.v_check_lpr)
        _bind_cfg("yolo.lpr_timeout",    self._lpr_timeout_var)
        _bind_cfg("yolo.lpr_font_size",  self._lpr_font_size_var)
        _bind_cfg("yolo.lpr_batch",      self.v_lpr_batch)
        for i, v in enumerate(self._lpr_fullimg_vars):
            _bind_cfg(f"yolo.lpr_fullimg{i+1}", v)
        for i, sv in enumerate(self._v_wf_segs):
            _bind_cfg(f"yolo.wf_s{i+1}", sv)
        # Migrate cài đặt cũ (1 ô) sang ô đầu tiên
        if not any(_CFG.get(f"yolo.wf_s{i+1}", "") for i in range(5)):
            old = _CFG.get("yolo.wrong_folder", "")
            if old:
                self._v_wf_segs[0].set(old)
        self._update_wrong_path()
        for sv in self._v_wf_segs:
            sv.trace_add("write", lambda *_: self._update_wrong_path())

        self._build()
        self.after(200, self._auto_load_model)
        self.after(300, self._bind_keys)
        self.after(400, self._sync_slider_labels)
        self.after(700, self._auto_restore_session)

    # ================================================================ BUILD ==

    def _build(self):
        self._build_toolbar()
        self._build_content()
        self._build_statusbar()

    def _build_toolbar(self):
        top = Frame(self, bg=CARD, padx=10, pady=8)
        top.pack(fill=X)

        # Row 0 — model 1 + model 2 (cùng 1 dòng)
        r0 = Frame(top, bg=CARD)
        r0.pack(fill=X)

        # Action buttons on RIGHT (pack trước để không bị squish)
        Button(r0, text="🔍 Validate true/", command=self._validate_true_folder,
               bg="#1a5276", fg="white", font=F_MAIN, relief="flat",
               padx=8, cursor="hand2",
               ).pack(side=RIGHT, padx=(4, 0))
        Button(r0, text="Tính mAP", command=self._start_map_calc,
               bg="#2e7d32", fg="white", font=F_MAIN, relief="flat",
               padx=8, cursor="hand2",
               ).pack(side=RIGHT, padx=(4, 0))
        Button(r0, text="Lưu kết quả", command=self._save_result,
               bg="#555570", fg="white", font=F_MAIN, relief="flat",
               padx=8, cursor="hand2",
               ).pack(side=RIGHT)

        # Model 1
        Button(r0, text="Model 1", command=self._select_model,
               bg=ACCENT2, fg="white", font=F_BOLD, relief="flat",
               padx=8, cursor="hand2",
               activebackground=ACCENT, activeforeground="white",
               ).pack(side=LEFT)
        self.lbl_model = Label(r0, text="Chưa chọn",
                               font=("Segoe UI", 9, "italic"),
                               bg=CARD, fg=DIM, width=18, anchor=W)
        self.lbl_model.pack(side=LEFT, padx=(4, 0))

        # Separator
        Frame(r0, bg=DIM, width=1).pack(side=LEFT, fill=Y, padx=(8, 8))

        # Model 2
        Button(r0, text="Model 2", command=self._select_model2,
               bg="#3a5a3a", fg="white", font=F_BOLD, relief="flat",
               padx=8, cursor="hand2",
               activebackground="#4a7a4a", activeforeground="white",
               ).pack(side=LEFT)
        self.lbl_model2 = Label(r0, text="Chưa chọn",
                                font=("Segoe UI", 9, "italic"),
                                bg=CARD, fg=DIM, width=18, anchor=W)
        self.lbl_model2.pack(side=LEFT, padx=(4, 0))
        Button(r0, text="×", command=self._clear_model2,
               bg=CARD, fg=DIM, font=F_BOLD, relief="flat",
               padx=4, cursor="hand2",
               activebackground="#3a1a1a", activeforeground=ACCENT,
               ).pack(side=LEFT, padx=(2, 0))

        # Row 0a — path input (ảnh hoặc thư mục kiểm tra)
        r0a = Frame(top, bg=CARD)
        r0a.pack(fill=X, pady=(6, 0))

        self.combo_path = ttk.Combobox(r0a, textvariable=self.v_check_folder,
                                       font=F_MAIN)
        self.combo_path.pack(side=LEFT, fill=X, expand=True, padx=(0, 4))
        _bind_history("h.yolo.path", self.combo_path)
        self.combo_path.bind("<Return>", lambda e: self._load_path_input())

        Button(r0a, text="▶ Tải", command=self._load_path_input,
               bg=ACCENT, fg="white", font=F_BOLD, relief="flat",
               padx=10, cursor="hand2",
               activebackground="#c0411a", activeforeground="white",
               ).pack(side=LEFT, padx=(0, 8))

        Button(r0a, text="Chọn Ảnh", command=self._select_image,
               bg=ACCENT, fg="white", font=F_MAIN, relief="flat",
               padx=8, cursor="hand2",
               activebackground="#c0411a", activeforeground="white",
               ).pack(side=LEFT, padx=(0, 4))

        Button(r0a, text="Chọn Thư Mục", command=self._select_folder,
               bg="#2e5fa3", fg="white", font=F_MAIN, relief="flat",
               padx=8, cursor="hand2",
               ).pack(side=LEFT, padx=(0, 4))

        Button(r0a, text="📂", command=self._open_check_folder,
               bg=CARD, fg=TEXT, font=F_MAIN, relief="flat",
               padx=6, cursor="hand2",
               activebackground=ACCENT2, activeforeground="white",
               ).pack(side=LEFT, padx=(0, 6))

        Checkbutton(r0a, text="Quét sub folder", variable=self.v_subfolder,
                    bg=CARD, fg=TEXT, activebackground=CARD,
                    activeforeground=TEXT, selectcolor="#16162a",
                    font=F_MAIN, cursor="hand2",
                    ).pack(side=LEFT, padx=(0, 10))

        Label(r0a, text="→ ✓ true/   ✗ false/",
              font=F_MAIN, bg=CARD, fg=DIM).pack(side=LEFT)

        # Row 0b — folder lưu ảnh sai (5 ô ghép path)
        r0b = Frame(top, bg=CARD)
        r0b.pack(fill=X, pady=(4, 0))

        Label(r0b, text="📁 Lưu ảnh sai:", font=F_MAIN, bg=CARD, fg=DIM).pack(side=LEFT, padx=(0, 4))

        # 5 ô: ô 1 expand (base path), ô 2-5 fixed width (sub-path)
        self._wf_combos = []
        _WF_WIDTHS = [0, 14, 14, 14, 12]  # 0 = expand
        _WF_KEYS   = [f"h.yolo.wf.s{i+1}" for i in range(5)]
        for i in range(5):
            if i > 0:
                Label(r0b, text="/", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
            cb = ttk.Combobox(r0b, textvariable=self._v_wf_segs[i], font=F_MAIN,
                              width=_WF_WIDTHS[i] or None)
            expand = (i == 0)
            cb.pack(side=LEFT, fill=X if expand else None,
                    expand=expand, padx=(0, 0))
            _bind_history(_WF_KEYS[i], cb)
            self._wf_combos.append(cb)

        Button(r0b, text="Chọn…", command=self._browse_wrong_folder,
               bg="#3a3a5a", fg=TEXT, font=F_MAIN, relief="flat",
               padx=8, cursor="hand2").pack(side=LEFT, padx=(4, 4))
        Button(r0b, text="📂", command=self._open_wrong_folder,
               bg=CARD, fg=TEXT, font=F_MAIN, relief="flat",
               padx=6, cursor="hand2",
               activebackground=ACCENT2, activeforeground="white").pack(side=LEFT)

        # Row 1 — conf slider (new feature: Ngưỡng confidence with resolution 0.05)
        r1 = Frame(top, bg=CARD)
        r1.pack(fill=X, pady=(8, 0))

        Label(r1, text="Ngưỡng confidence:", font=F_BOLD, bg=CARD, fg=TEXT).pack(side=LEFT)
        self.slider_conf_thresh = Scale(
            r1, from_=0.0, to=1.0, resolution=0.05,
            orient=HORIZONTAL, length=200,
            variable=self.v_conf_thresh,
            command=self._on_conf_thresh_change,
            bg=CARD, fg=TEXT, highlightthickness=0,
            troughcolor="#16162a", activebackground=ACCENT,
            relief="flat", bd=0, showvalue=False,
        )
        self.slider_conf_thresh.pack(side=LEFT, padx=(4, 2))
        self.lbl_conf_thresh_val = Label(r1, text="0.25", bg=CARD, fg=ACCENT,
                                         font=F_MONO, width=5)
        self.lbl_conf_thresh_val.pack(side=LEFT, padx=(0, 16))

        Label(r1, text="Conf:", font=F_BOLD, bg=CARD, fg=TEXT).pack(side=LEFT)
        self.slider_conf = ttk.Scale(r1, from_=0.01, to=1.0,
                                      variable=self.v_conf,
                                      orient=HORIZONTAL, length=160,
                                      command=self._on_slider_change)
        self.slider_conf.pack(side=LEFT, padx=(4, 2))
        self.lbl_conf = Label(r1, text="0.30", bg=CARD, fg=TEXT,
                               font=F_MONO, width=5)
        self.lbl_conf.pack(side=LEFT)

        Label(r1, text="  IoU:", font=F_BOLD, bg=CARD, fg=TEXT).pack(side=LEFT)
        self.slider_iou = ttk.Scale(r1, from_=0.01, to=1.0,
                                     variable=self.v_iou,
                                     orient=HORIZONTAL, length=160,
                                     command=self._on_slider_change)
        self.slider_iou.pack(side=LEFT, padx=(4, 2))
        self.lbl_iou = Label(r1, text="0.45", bg=CARD, fg=TEXT,
                              font=F_MONO, width=5)
        self.lbl_iou.pack(side=LEFT)

        # Row 2 — class filter (compact inline)
        r2 = Frame(top, bg=CARD)
        r2.pack(fill=X, pady=(4, 0))

        Label(r2, text="Lọc class:", font=F_MAIN, bg=CARD, fg=DIM,
              anchor=W).pack(side=LEFT, padx=(0, 4))
        cls_wrap = Frame(r2, bg=CARD)
        cls_wrap.pack(side=LEFT, fill=BOTH, expand=True)
        sb = Scrollbar(cls_wrap, orient=VERTICAL)
        sb.pack(side=RIGHT, fill=Y)
        self.lb_classes = Listbox(cls_wrap, selectmode=MULTIPLE,
                                   yscrollcommand=sb.set,
                                   height=2, font=F_MONO,
                                   bg="#16162a", fg=TEXT,
                                   selectbackground=ACCENT2,
                                   activestyle="none",
                                   relief="flat", bd=0)
        self.lb_classes.pack(side=LEFT, fill=BOTH, expand=True)
        sb.config(command=self.lb_classes.yview)
        self.lb_classes.bind("<<ListboxSelect>>",
                              lambda _: self._detect_and_display())

        # Row 3 — zoom, original toggle, auto-play, batch export
        r3 = Frame(top, bg=CARD)
        r3.pack(fill=X, pady=(6, 0))

        Label(r3, text="Zoom:", font=F_BOLD, bg=CARD, fg=TEXT).pack(side=LEFT)
        Button(r3, text="−", command=lambda: self._zoom_step(-0.2),
               bg=CARD, fg=TEXT, font=F_BOLD, relief="flat", padx=6,
               cursor="hand2").pack(side=LEFT, padx=(4, 0))
        self.lbl_zoom = Label(r3, text="Fit", bg=CARD, fg=ACCENT,
                              font=F_MONO, width=6)
        self.lbl_zoom.pack(side=LEFT)
        Button(r3, text="+", command=lambda: self._zoom_step(+0.2),
               bg=CARD, fg=TEXT, font=F_BOLD, relief="flat", padx=6,
               cursor="hand2").pack(side=LEFT, padx=(0, 2))
        Button(r3, text="Fit", command=lambda: self._zoom_step(0.0),
               bg="#333355", fg=TEXT, font=F_MAIN, relief="flat",
               padx=6, cursor="hand2").pack(side=LEFT, padx=(2, 16))

        Checkbutton(r3, text="Xem ảnh gốc", variable=self.v_show_original,
                    command=self._render_display,
                    bg=CARD, fg=TEXT, activebackground=CARD,
                    activeforeground=TEXT, selectcolor="#16162a",
                    font=F_MAIN, cursor="hand2").pack(side=LEFT, padx=(0, 16))

        self.btn_autoplay = Button(r3, text="▶ Auto",
                                   command=self._toggle_autoplay,
                                   bg="#2e5fa3", fg="white", font=F_MAIN,
                                   relief="flat", padx=8, cursor="hand2")
        self.btn_autoplay.pack(side=LEFT, padx=(0, 4))
        self.spin_interval = Spinbox(r3, from_=0.5, to=30.0, increment=0.5,
                                      width=5, format="%.1f",
                                      textvariable=self.v_interval,
                                      bg="#16162a", fg=TEXT, font=F_MONO,
                                      buttonbackground=CARD, relief="flat",
                                      insertbackground=TEXT)
        self.spin_interval.pack(side=LEFT, padx=(0, 2))
        Label(r3, text="s", font=F_MAIN, bg=CARD, fg=DIM).pack(side=LEFT,
                                                                padx=(0, 16))

        Button(r3, text="Export tất cả", command=self._batch_export,
               bg="#4a3f00", fg="#ffcc00", font=F_MAIN, relief="flat",
               padx=8, cursor="hand2").pack(side=LEFT)
        Checkbutton(r3, text="Vẽ lên hình", variable=self.v_export_draw,
                    bg=CARD, fg=TEXT, activebackground=CARD,
                    activeforeground=TEXT, selectcolor="#16162a",
                    font=F_MAIN, cursor="hand2").pack(side=LEFT, padx=(4, 0))
        Checkbutton(r3, text="Đổi tên", variable=self.v_export_rename,
                    bg=CARD, fg=TEXT, activebackground=CARD,
                    activeforeground=TEXT, selectcolor="#16162a",
                    font=F_MAIN, cursor="hand2").pack(side=LEFT, padx=(2, 0))

        Button(r3, text="📹 Video", command=self._open_video_detect,
               bg="#1a3a5a", fg="#7ab8e8", font=F_MAIN, relief="flat",
               padx=8, cursor="hand2",
               activebackground="#2a5a8a", activeforeground="white",
               ).pack(side=LEFT, padx=(4, 0))

        self.btn_detect_all = Button(r3, text="⚡ Detect All",
                                     command=self._detect_all,
                                     bg="#103020", fg="#4caf50", font=F_MAIN,
                                     relief="flat", padx=8, cursor="hand2",
                                     activebackground="#1a5030", activeforeground="#4caf50")
        self.btn_detect_all.pack(side=LEFT, padx=(4, 0))
        self.btn_detect_page = Button(r3, text="⚡ Detect trang",
                                      command=self._detect_page,
                                      bg="#102030", fg="#4caf50", font=F_MAIN,
                                      relief="flat", padx=8, cursor="hand2",
                                      activebackground="#1a3050", activeforeground="#4caf50")
        self.btn_detect_page.pack(side=LEFT, padx=(4, 0))
        self.lbl_cache_info = Label(r3, text="", font=F_MONO, bg=CARD, fg=DIM)
        self.lbl_cache_info.pack(side=LEFT, padx=(4, 0))
        Button(r3, text="🗑", command=self._clear_cache,
               bg=CARD, fg=DIM, font=F_MAIN, relief="flat",
               padx=4, cursor="hand2",
               activebackground="#3a1a1a", activeforeground=ACCENT,
               ).pack(side=LEFT, padx=(2, 0))

        Frame(r3, bg=DIM, width=1).pack(side=LEFT, fill=Y, padx=(12, 6))

        Label(r3, text="Nét:", font=F_BOLD, bg=CARD, fg=TEXT).pack(side=LEFT)
        lw_spn = Spinbox(r3, from_=1, to=8, textvariable=self.v_line_width,
                         width=3, bg="#16162a", fg=TEXT, insertbackground=TEXT,
                         buttonbackground=ACCENT2, relief="flat", font=F_MAIN,
                         command=self._on_plot_param_change)
        lw_spn.bind("<Return>",   lambda e: self._on_plot_param_change())
        lw_spn.bind("<FocusOut>", lambda e: self._on_plot_param_change())
        lw_spn.pack(side=LEFT, padx=(2, 8))

        Label(r3, text="Font:", font=F_BOLD, bg=CARD, fg=TEXT).pack(side=LEFT)
        fs_spn = Spinbox(r3, from_=6, to=48, textvariable=self.v_font_size,
                         width=3, bg="#16162a", fg=TEXT, insertbackground=TEXT,
                         buttonbackground=ACCENT2, relief="flat", font=F_MAIN,
                         command=self._on_plot_param_change)
        fs_spn.bind("<Return>",   lambda e: self._on_plot_param_change())
        fs_spn.bind("<FocusOut>", lambda e: self._on_plot_param_change())
        fs_spn.pack(side=LEFT, padx=(2, 0))

        # Row 4 — LPR server config (kiểm tra biển số sau YOLO detect)
        r4 = Frame(top, bg=CARD)
        r4.pack(fill=X, pady=(6, 0))

        # Sub-row 4a: checkboxes + params + test btn
        r4a = Frame(r4, bg=CARD)
        r4a.pack(fill=X)
        Checkbutton(r4a, text="🔍 Kiểm tra biển số", variable=self.v_check_lpr,
                    bg=CARD, fg=TEXT, activebackground=CARD,
                    activeforeground=TEXT, selectcolor="#16162a",
                    font=F_MAIN, cursor="hand2",
                    ).pack(side=LEFT, padx=(0, 6))
        Checkbutton(r4a, text="📦 Gọi khi batch", variable=self.v_lpr_batch,
                    bg=CARD, fg=DIM, activebackground=CARD,
                    activeforeground=TEXT, selectcolor="#16162a",
                    font=F_MAIN, cursor="hand2",
                    ).pack(side=LEFT, padx=(0, 10))
        Label(r4a, text="Timeout:", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        Spinbox(r4a, from_=1, to=120, textvariable=self._lpr_timeout_var,
                width=4, bg="#16162a", fg=TEXT, insertbackground=TEXT,
                buttonbackground=ACCENT2, relief="flat", font=F_MAIN,
                ).pack(side=LEFT, padx=(4, 2))
        Label(r4a, text="s", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT, padx=(0, 10))
        Label(r4a, text="Cỡ chữ:", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        Spinbox(r4a, from_=12, to=72, textvariable=self._lpr_font_size_var,
                width=4, bg="#16162a", fg=TEXT, insertbackground=TEXT,
                buttonbackground=ACCENT2, relief="flat", font=F_MAIN,
                ).pack(side=LEFT, padx=(4, 2))
        Label(r4a, text="px", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT, padx=(0, 10))
        Button(r4a, text="🔌 Test", command=self._test_lpr_connection,
               bg=ACCENT2, fg="white", font=F_MAIN, relief="flat",
               padx=8, cursor="hand2",
               activebackground=ACCENT, activeforeground="white",
               ).pack(side=LEFT, padx=(0, 6))
        self._lpr_conn_lbl = Label(r4a, text="", bg=CARD, fg=DIM,
                                    font=F_MAIN, width=24, anchor=W)
        self._lpr_conn_lbl.pack(side=LEFT)

        # Sub-row 4b: 3 URL comboboxes + checkbox ảnh gốc
        r4b = Frame(r4, bg=CARD)
        r4b.pack(fill=X, pady=(3, 0))
        _LPR_HIST_KEYS = ["h.yolo.lpr_url1", "h.yolo.lpr_url2", "h.yolo.lpr_url3"]
        for i in range(3):
            Label(r4b, text=f"LPR{i+1}:", bg=CARD, fg=DIM,
                  font=F_MAIN).pack(side=LEFT, padx=(0 if i == 0 else 8, 2))
            cb = ttk.Combobox(r4b, textvariable=self._lpr_url_vars[i],
                              width=30, font=F_MAIN)
            cb.pack(side=LEFT)
            _bind_history(_LPR_HIST_KEYS[i], cb)
            self._lpr_url_combos[i] = cb
            Checkbutton(r4b, text="Ảnh gốc", variable=self._lpr_fullimg_vars[i],
                        bg=CARD, fg=DIM, selectcolor=CARD,
                        font=F_MAIN).pack(side=LEFT, padx=(3, 0))


    def _build_content(self):
        content = Frame(self, bg=BG)
        content.pack(fill=BOTH, expand=True)

        # Sidebar — image list
        sidebar = Frame(content, bg=CARD, width=240)
        sidebar.pack(side=LEFT, fill=Y, padx=(0, 2))
        sidebar.pack_propagate(False)

        Label(sidebar, text="Danh sách ảnh",
              font=F_BOLD, bg=CARD, fg=TEXT).pack(pady=(8, 2))

        # Search box
        search_row = Frame(sidebar, bg=CARD)
        search_row.pack(fill=X, padx=4, pady=(0, 3))
        Label(search_row, text="🔍", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        self._search_combo = ttk.Combobox(
            search_row, textvariable=self._v_search,
            font=F_MONO, height=12)
        self._search_combo.pack(side=LEFT, fill=X, expand=True, padx=(2, 4))
        _bind_history("h.yolo.search", self._search_combo)
        self._search_combo.bind("<Return>", lambda e: self._do_search())
        self._search_combo.bind("<<ComboboxSelected>>",
                                lambda e: self._do_search())
        Button(search_row, text="Tìm", command=self._do_search,
               bg=ACCENT2, fg="white", font=F_MAIN, relief="flat",
               padx=6, cursor="hand2").pack(side=LEFT)
        self._hint_toggle_btn = Button(
            search_row, text="?", command=self._toggle_search_hint,
            bg=CARD, fg="#6060a0", font=("Segoe UI", 8),
            relief="flat", cursor="hand2", padx=3)
        self._hint_toggle_btn.pack(side=LEFT, padx=(2, 0))

        # Search hint — collapsed by default to preserve space for file list
        hint_lines = [
            "Cách dùng ô tìm kiếm:",
            "• Nhiều từ = AND:  sang cong 5",
            "• *  = bất kỳ chuỗi:  07*  *canh",
            "• ?  = đúng 1 ký tự:  07?507",
            "• Kết hợp:  sang 07*",
            "• Enter hoặc nút Tìm để áp dụng",
        ]
        self._search_row_ref = search_row
        self._hint_frame = Frame(sidebar, bg="#12122a", bd=0)
        for line in hint_lines:
            Label(self._hint_frame, text=line,
                  bg="#12122a", fg="#6060a0",
                  font=("Segoe UI", 7), anchor=W,
                  justify=LEFT).pack(fill=X, padx=4, pady=0)
        self._hint_shown = False  # ẩn mặc định

        # Filter buttons
        filter_row = Frame(sidebar, bg=CARD)
        filter_row.pack(fill=X, padx=4, pady=(0, 3))
        self._filter_btns = {}
        for code, lbl, fg in [
            ("all",        "All",  TEXT),
            ("correct",    "✓",   "#4caf50"),
            ("incorrect",  "✗",   ACCENT),
            ("unreviewed", "?",    DIM),
        ]:
            b = Button(filter_row, text=lbl, width=4,
                       command=lambda c=code: self._apply_filter(c),
                       bg=CARD, fg=fg, font=F_MAIN, relief="flat",
                       cursor="hand2", activebackground="#252540",
                       activeforeground=fg)
            b.pack(side=LEFT, padx=1)
            self._filter_btns[code] = b
        self._filter_btns["all"].config(relief="sunken", bg="#252540")

        # ── Detect result filters ────────────────────────────────────────────
        Frame(sidebar, bg=DIM, height=1).pack(fill=X, padx=6, pady=(2, 2))

        det_hdr = Frame(sidebar, bg=CARD)
        det_hdr.pack(fill=X, padx=4, pady=(0, 1))
        Label(det_hdr, text="Filter detect:", bg=CARD, fg=DIM,
              font=F_MAIN).pack(side=LEFT)
        Button(det_hdr, text="×", command=self._clear_det_filters,
               bg=CARD, fg=DIM, font=F_MAIN, relief="flat",
               cursor="hand2", padx=2).pack(side=RIGHT)

        flt_cls_row = Frame(sidebar, bg=CARD)
        flt_cls_row.pack(fill=X, padx=4, pady=(0, 2))
        Label(flt_cls_row, text="Class:", bg=CARD, fg=DIM,
              font=F_MAIN, width=7, anchor=W).pack(side=LEFT)
        self._flt_class_combo = ttk.Combobox(
            flt_cls_row, textvariable=self._flt_class_var,
            state="readonly", font=F_MAIN)
        self._flt_class_combo["values"] = ["Tất cả", "Không detect"]
        self._flt_class_combo.pack(side=LEFT, fill=X, expand=True)
        self._flt_class_combo.bind("<<ComboboxSelected>>",
                                   lambda _: self._apply_filter(self._active_filter))

        flt_n_row = Frame(sidebar, bg=CARD)
        flt_n_row.pack(fill=X, padx=4, pady=(0, 2))
        Label(flt_n_row, text="#Det:", bg=CARD, fg=DIM,
              font=F_MAIN, width=7, anchor=W).pack(side=LEFT)
        Entry(flt_n_row, textvariable=self._flt_ndet_min_var,
              bg="#16162a", fg=TEXT, insertbackground=TEXT,
              relief="flat", font=F_MONO, bd=2, width=5).pack(side=LEFT)
        Label(flt_n_row, text="–", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT, padx=1)
        Entry(flt_n_row, textvariable=self._flt_ndet_max_var,
              bg="#16162a", fg=TEXT, insertbackground=TEXT,
              relief="flat", font=F_MONO, bd=2, width=5).pack(side=LEFT)
        self._flt_ndet_min_var.trace_add("write", lambda *_: self._schedule_det_filter())
        self._flt_ndet_max_var.trace_add("write", lambda *_: self._schedule_det_filter())

        flt_area_row = Frame(sidebar, bg=CARD)
        flt_area_row.pack(fill=X, padx=4, pady=(0, 2))
        Label(flt_area_row, text="BBox px²:", bg=CARD, fg=DIM,
              font=F_MAIN, width=7, anchor=W).pack(side=LEFT)
        Entry(flt_area_row, textvariable=self._flt_area_min_var,
              bg="#16162a", fg=TEXT, insertbackground=TEXT,
              relief="flat", font=F_MONO, bd=2, width=5).pack(side=LEFT)
        Label(flt_area_row, text="–", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT, padx=1)
        Entry(flt_area_row, textvariable=self._flt_area_max_var,
              bg="#16162a", fg=TEXT, insertbackground=TEXT,
              relief="flat", font=F_MONO, bd=2, width=5).pack(side=LEFT)
        self._flt_area_min_var.trace_add("write", lambda *_: self._schedule_det_filter())
        self._flt_area_max_var.trace_add("write", lambda *_: self._schedule_det_filter())

        flt_w_row = Frame(sidebar, bg=CARD)
        flt_w_row.pack(fill=X, padx=4, pady=(0, 2))
        Label(flt_w_row, text="BBox W:", bg=CARD, fg=DIM,
              font=F_MAIN, width=7, anchor=W).pack(side=LEFT)
        Entry(flt_w_row, textvariable=self._flt_w_min_var,
              bg="#16162a", fg=TEXT, insertbackground=TEXT,
              relief="flat", font=F_MONO, bd=2, width=5).pack(side=LEFT)
        Label(flt_w_row, text="–", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT, padx=1)
        Entry(flt_w_row, textvariable=self._flt_w_max_var,
              bg="#16162a", fg=TEXT, insertbackground=TEXT,
              relief="flat", font=F_MONO, bd=2, width=5).pack(side=LEFT)
        self._flt_w_min_var.trace_add("write", lambda *_: self._schedule_det_filter())
        self._flt_w_max_var.trace_add("write", lambda *_: self._schedule_det_filter())

        flt_h_row = Frame(sidebar, bg=CARD)
        flt_h_row.pack(fill=X, padx=4, pady=(0, 2))
        Label(flt_h_row, text="BBox H:", bg=CARD, fg=DIM,
              font=F_MAIN, width=7, anchor=W).pack(side=LEFT)
        Entry(flt_h_row, textvariable=self._flt_h_min_var,
              bg="#16162a", fg=TEXT, insertbackground=TEXT,
              relief="flat", font=F_MONO, bd=2, width=5).pack(side=LEFT)
        Label(flt_h_row, text="–", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT, padx=1)
        Entry(flt_h_row, textvariable=self._flt_h_max_var,
              bg="#16162a", fg=TEXT, insertbackground=TEXT,
              relief="flat", font=F_MONO, bd=2, width=5).pack(side=LEFT)
        self._flt_h_min_var.trace_add("write", lambda *_: self._schedule_det_filter())
        self._flt_h_max_var.trace_add("write", lambda *_: self._schedule_det_filter())

        # ── Phải có / không có nhãn ─────────────────────────────────────────
        Frame(sidebar, bg=DIM, height=1).pack(fill=X, padx=6, pady=(3, 2))

        Label(sidebar, text="✔ Phải có nhãn:", bg=CARD, fg=DIM,
              font=F_MAIN, anchor=W).pack(fill=X, padx=6)
        mh_frm = Frame(sidebar, bg=CARD)
        mh_frm.pack(fill=X, padx=6, pady=(1, 2))
        self._must_have_lb = Listbox(mh_frm, bg="#16162a", fg=TEXT,
                                     selectbackground=ACCENT2,
                                     selectforeground="white",
                                     font=F_MONO, relief="flat", bd=0,
                                     selectmode=MULTIPLE, height=3,
                                     activestyle="none", exportselection=False)
        mh_sb = Scrollbar(mh_frm, command=self._must_have_lb.yview)
        self._must_have_lb.configure(yscrollcommand=mh_sb.set)
        mh_sb.pack(side=RIGHT, fill=Y)
        self._must_have_lb.pack(fill=X, expand=True)
        self._must_have_lb.bind("<<ListboxSelect>>",
                                lambda _: self._schedule_det_filter())

        Label(sidebar, text="✕ Không có nhãn:", bg=CARD, fg=DIM,
              font=F_MAIN, anchor=W).pack(fill=X, padx=6, pady=(2, 0))
        mn_frm = Frame(sidebar, bg=CARD)
        mn_frm.pack(fill=X, padx=6, pady=(1, 3))
        self._must_not_lb = Listbox(mn_frm, bg="#16162a", fg=TEXT,
                                    selectbackground="#c62828",
                                    selectforeground="white",
                                    font=F_MONO, relief="flat", bd=0,
                                    selectmode=MULTIPLE, height=3,
                                    activestyle="none", exportselection=False)
        mn_sb = Scrollbar(mn_frm, command=self._must_not_lb.yview)
        self._must_not_lb.configure(yscrollcommand=mn_sb.set)
        mn_sb.pack(side=RIGHT, fill=Y)
        self._must_not_lb.pack(fill=X, expand=True)
        self._must_not_lb.bind("<<ListboxSelect>>",
                               lambda _: self._schedule_det_filter())

        Frame(sidebar, bg=DIM, height=1).pack(fill=X, padx=6, pady=(2, 2))

        # ── LPR filter ──────────────────────────────────────────────────────
        lpr_flt_row = Frame(sidebar, bg=CARD)
        lpr_flt_row.pack(fill=X, padx=6, pady=(1, 3))
        Label(lpr_flt_row, text="🔍 LPR:", bg=CARD, fg=DIM,
              font=F_MAIN).pack(side=LEFT, padx=(0, 4))
        self._flt_lpr_combo = ttk.Combobox(
            lpr_flt_row, textvariable=self._flt_lpr_var, state="readonly",
            values=["Tất cả", "Có biển số", "Không biển số", "Chưa nhận dạng"],
            width=16, font=F_MAIN)
        self._flt_lpr_combo.pack(side=LEFT, fill=X, expand=True)
        self._flt_lpr_var.trace_add("write", lambda *_: self._schedule_det_filter())

        Frame(sidebar, bg=DIM, height=1).pack(fill=X, padx=6, pady=(0, 2))

        tree_frame = Frame(sidebar, bg=CARD)
        tree_frame.pack(fill=BOTH, expand=True, padx=2, pady=(0, 6))

        sb2 = Scrollbar(tree_frame, orient=VERTICAL)
        sb2.pack(side=RIGHT, fill=Y)
        sb2h = Scrollbar(tree_frame, orient=HORIZONTAL)
        sb2h.pack(side=BOTTOM, fill=X)

        style = ttk.Style()
        style.configure("YoloTree.Treeview",
                        background="#16162a", foreground=TEXT,
                        fieldbackground="#16162a", borderwidth=0,
                        rowheight=20, font=F_MAIN)
        style.map("YoloTree.Treeview",
                  background=[("selected", ACCENT2)],
                  foreground=[("selected", "white")])
        style.configure("YoloTree.Treeview.Heading", background=CARD,
                        foreground=TEXT)

        self.tree_images = ttk.Treeview(tree_frame, style="YoloTree.Treeview",
                                         selectmode="browse", show="tree",
                                         yscrollcommand=sb2.set,
                                         xscrollcommand=sb2h.set)
        self.tree_images.pack(fill=BOTH, expand=True)
        sb2.config(command=self.tree_images.yview)
        sb2h.config(command=self.tree_images.xview)
        self.tree_images.bind("<<TreeviewSelect>>", self._on_image_select)
        self.tree_images.tag_configure("correct",    foreground="#4caf50")
        self.tree_images.tag_configure("incorrect",  foreground=ACCENT)
        self.tree_images.tag_configure("unreviewed", foreground=TEXT)
        self.tree_images.tag_configure("folder",     foreground=DIM)

        # Right — result panels area
        right = Frame(content, bg=BG)
        right.pack(side=LEFT, fill=BOTH, expand=True)

        self.lbl_result = Label(right, text="", font=F_BOLD,
                                 bg=BG, fg=TEXT, anchor=W)
        self.lbl_result.pack(fill=X, padx=6, pady=(4, 0))

        # Mark buttons
        mark_row = Frame(right, bg=BG)
        mark_row.pack(fill=X, padx=6, pady=(2, 0))
        Button(mark_row, text="✓ Đúng  [Enter]",
               command=lambda: self._mark_review("correct"),
               bg="#1a3a1a", fg="#4caf50", font=F_MAIN, relief="flat",
               padx=8, cursor="hand2").pack(side=LEFT, padx=(0, 4))
        Button(mark_row, text="✗ Sai  [Del]",
               command=lambda: self._mark_review("incorrect"),
               bg="#3a1a1a", fg=ACCENT, font=F_MAIN, relief="flat",
               padx=8, cursor="hand2").pack(side=LEFT, padx=(0, 4))
        Button(mark_row, text="↺ Bỏ đánh dấu",
               command=lambda: self._mark_review(""),
               bg=CARD, fg=DIM, font=F_MAIN, relief="flat",
               padx=6, cursor="hand2").pack(side=LEFT)
        Button(mark_row, text="✓✓ Đúng trang",
               command=self._mark_page_correct,
               bg="#0d2a1a", fg="#4caf50", font=F_MAIN, relief="flat",
               padx=6, cursor="hand2").pack(side=LEFT, padx=(8, 0))
        Button(mark_row, text="✗✗ Sai trang",
               command=self._mark_page_incorrect,
               bg="#2a0d0d", fg=ACCENT, font=F_MAIN, relief="flat",
               padx=6, cursor="hand2").pack(side=LEFT, padx=(4, 0))
        Button(mark_row, text="💾 Lưu ảnh sai",
               command=self._save_wrong_image,
               bg="#2a1a0a", fg="#ffaa55", font=F_MAIN, relief="flat",
               padx=6, cursor="hand2").pack(side=LEFT, padx=(8, 0))
        Button(mark_row, text="💾💾 Sai trang",
               command=self._save_wrong_page,
               bg="#2a1a0a", fg="#ffaa55", font=F_MAIN, relief="flat",
               padx=6, cursor="hand2").pack(side=LEFT, padx=(4, 0))
        Button(mark_row, text="📋 Lưu lỗi+GT",
               command=self._save_lpr_error_image,
               bg="#0d2a1a", fg="#4cdf80", font=F_MAIN, relief="flat",
               padx=6, cursor="hand2").pack(side=LEFT, padx=(8, 0))
        Button(mark_row, text="📂 GT",
               command=self._open_gt_folder,
               bg=CARD, fg="#4cdf80", font=F_MAIN, relief="flat",
               padx=6, cursor="hand2").pack(side=LEFT, padx=(2, 0))
        self.lbl_mark_state = Label(mark_row, text="", font=F_MONO,
                                     bg=BG, fg=DIM)
        self.lbl_mark_state.pack(side=LEFT, padx=(12, 0))

        # Horizontal split: image view (left) | filmstrip grid (right)
        from tkinter import PanedWindow as _PW
        self._view_paned = _PW(right, orient=HORIZONTAL, sashwidth=5,
                               bg="#0d0d1e", sashrelief=RAISED, bd=0)
        self._view_paned.pack(fill=BOTH, expand=True)

        self.panels_frame = Frame(self._view_paned, bg=BG)
        self._view_paned.add(self.panels_frame, minsize=300, stretch="always")

        self._grid_outer = Frame(self._view_paned, bg="#0d0d1e")
        self._view_paned.add(self._grid_outer, minsize=160, stretch="never")
        self._build_grid_panel()

        # Panel 1
        self.panel1_frame = Frame(self.panels_frame, bg=BG)
        self.panel1_frame.pack(side=LEFT, fill=BOTH, expand=True)

        self.lbl_panel1_title = Label(self.panel1_frame, text="",
                                       font=F_BOLD, bg=CARD, fg=ACCENT2,
                                       anchor=CENTER, pady=3)
        self.lbl_panel1_title.pack(fill=X)

        self.canvas = Canvas(self.panel1_frame, bg="#0d0d1a",
                             highlightthickness=0, cursor="fleur")
        self.canvas.pack(fill=BOTH, expand=True, padx=0, pady=2)
        self._canvas_hint = self.canvas.create_text(
            400, 200, text="Chọn ảnh để nhận diện",
            fill=DIM, font=("Segoe UI", 14), anchor=CENTER, tags="hint")

        # Panel 2 (hidden by default)
        self.panel2_frame = Frame(self.panels_frame, bg=BG)

        self.lbl_panel2_title = Label(self.panel2_frame, text="",
                                       font=F_BOLD, bg=CARD, fg=ACCENT2,
                                       anchor=CENTER, pady=3)
        self.lbl_panel2_title.pack(fill=X)

        self.canvas2 = Canvas(self.panel2_frame, bg="#0d0d1a",
                              highlightthickness=0, cursor="fleur")
        self.canvas2.pack(fill=BOTH, expand=True, padx=0, pady=2)

        self.canvas.bind("<Configure>",          self._on_canvas_configure)
        self.canvas.bind("<MouseWheel>",         self._on_canvas_scroll)
        self.canvas.bind("<Control-MouseWheel>", self._on_canvas_scroll)
        self.canvas.bind("<ButtonPress-1>",      self._on_pan_press)
        self.canvas.bind("<B1-Motion>",          self._on_pan_drag)
        self.canvas.bind("<Double-Button-1>",    self._on_canvas1_zoom)
        self.canvas2.bind("<Double-Button-1>",   self._on_canvas2_zoom)
        # Middle mouse pan (like BBoxEditor)
        self.canvas.bind("<ButtonPress-2>",      self._on_mmb_press)
        self.canvas.bind("<B2-Motion>",          self._on_mmb_drag)
        self.canvas.bind("<ButtonRelease-2>",    self._on_mmb_release)
        # Ctrl+drag to pan
        self.canvas.bind("<Control-ButtonPress-1>", self._on_mmb_press)
        self.canvas.bind("<Control-B1-Motion>",     self._on_mmb_drag)
        self.canvas.bind("<Control-ButtonRelease-1>", self._on_mmb_release)

        if _DND_OK:
            try:
                self.canvas.drop_target_register(DND_FILES)
                self.canvas.dnd_bind("<<Drop>>", self._on_drop)
            except Exception:
                pass

    def _build_statusbar(self):
        self.v_status = StringVar(value="Sẵn sàng")
        Label(self, textvariable=self.v_status,
              font=F_MAIN, bg=CARD, fg=DIM, anchor=W, padx=8,
              ).pack(fill=X, side=BOTTOM)

    # ============================================================= LPR CONFIG ==

    def _test_lpr_connection(self):
        """Test kết nối LPR server bằng cách gửi ảnh 4×4 pixel."""
        if not _REQ_OK:
            messagebox.showerror("Thiếu thư viện",
                                  "pip install requests", parent=self.root)
            return
        if not _PIL_OK:
            messagebox.showerror("Thiếu thư viện",
                                  "pip install Pillow", parent=self.root)
            return
        # Test tất cả URL có giá trị
        urls_to_test = [(i, v.get().strip())
                        for i, v in enumerate(self._lpr_url_vars)
                        if v.get().strip()]
        if not urls_to_test:
            messagebox.showwarning("Chưa nhập URL",
                                    "Vui lòng nhập ít nhất 1 URL LPR.", parent=self.root)
            return
        _HIST_KEYS = ["h.yolo.lpr_url1", "h.yolo.lpr_url2", "h.yolo.lpr_url3"]
        for i, url in urls_to_test:
            _push_history(_HIST_KEYS[i], url)
            if self._lpr_url_combos[i]:
                self._lpr_url_combos[i]["values"] = _get_history(_HIST_KEYS[i])
        if self._lpr_conn_lbl:
            self._lpr_conn_lbl.config(text="Đang kiểm tra…", fg="#f0c040")

        def _do():
            from io import BytesIO
            buf = BytesIO()
            Image.new("RGB", (4, 4), (0, 0, 0)).save(buf, "JPEG")
            data = buf.getvalue()
            parts = []
            for i, url in urls_to_test:
                try:
                    resp = _requests.post(
                        url,
                        files={"upload": ("test.jpg", data, "image/jpeg")},
                        timeout=5)
                    ok = resp.status_code < 500
                    parts.append(f"LPR{i+1}:{'✔' if ok else '✗'}{resp.status_code}")
                except Exception as ex:
                    parts.append(f"LPR{i+1}:✗{str(ex)[:12]}")
            msg   = "  ".join(parts)
            color = SUCCESS if all("✔" in p for p in parts) else ACCENT
            self.root.after(0, lambda m=msg, c=color: (
                self._lpr_conn_lbl and
                self._lpr_conn_lbl.config(text=m, fg=c)
            ))

        threading.Thread(target=_do, daemon=True).start()

    # ============================================================= DRAG-DROP ==

    def _on_drop(self, event):
        paths = self.root.tk.splitlist(event.data)
        if not paths:
            return
        if len(paths) == 1 and os.path.isdir(paths[0]):
            self._load_folder(paths[0])
            return
        imgs = [p for p in paths
                if os.path.isfile(p)
                and os.path.splitext(p)[1].lower() in IMAGE_EXTENSIONS]
        if not imgs:
            messagebox.showwarning("Không hỗ trợ",
                                   "Chỉ hỗ trợ ảnh hoặc thư mục chứa ảnh.",
                                   parent=self.root)
            return
        self._load_image_list(sorted(imgs))

    # ============================================================ FILE LOAD ==

    def _select_model(self):
        path = filedialog.askopenfilename(
            title="Chọn file model YOLO 1 (.pt)",
            filetypes=[("PyTorch Model", "*.pt"), ("All files", "*.*")],
            initialdir=_cfg_dir("yolo.model_dir") or None,
            parent=self.root)
        if path:
            _push_history("h.yolo.model", path)
            self._load_model(path)

    def _select_model2(self):
        if not _YOLO_OK:
            messagebox.showerror("Thiếu thư viện",
                                  "pip install ultralytics", parent=self.root)
            return
        path = filedialog.askopenfilename(
            title="Chọn file model YOLO 2 (.pt)",
            filetypes=[("PyTorch Model", "*.pt"), ("All files", "*.*")],
            initialdir=_cfg_dir("yolo.model_dir") or None,
            parent=self.root)
        if not path:
            return
        _push_history("h.yolo.model2", path)
        try:
            self.model2 = YOLO(path)
            self.v_model2_path.set(path)
            self.lbl_model2.config(
                text=f"  {os.path.basename(path)}", fg="#4caf50")
            if self.current_image_path and self.model:
                self._detect_and_display()
        except Exception as e:
            messagebox.showerror("Lỗi load model 2", str(e), parent=self.root)

    def _clear_model2(self):
        self.model2 = None
        self.v_model2_path.set("")
        self.lbl_model2.config(text="Chưa chọn", fg=DIM)
        self.panel2_frame.pack_forget()
        self.lbl_panel1_title.config(text="")
        if self.current_image_path and self.model:
            self._detect_and_display()

    def _load_model(self, path: str):
        if not _YOLO_OK:
            messagebox.showerror("Thiếu thư viện",
                                  "pip install ultralytics", parent=self.root)
            return
        self.lbl_model.config(text=f"  ⏳ Đang load {os.path.basename(path)}…", fg=DIM)
        self.root.update_idletasks()

        def _do_load():
            try:
                mdl = YOLO(path)
                self.root.after(0, lambda: self._on_model_loaded(path, mdl, None))
            except Exception as e:
                self.root.after(0, lambda err=str(e): self._on_model_loaded(path, None, err))

        threading.Thread(target=_do_load, daemon=True).start()

    def _on_model_loaded(self, path: str, mdl, err: str | None):
        if err:
            messagebox.showerror("Lỗi load model", err, parent=self.root)
            self.lbl_model.config(text="  ✗ Lỗi load model", fg=ACCENT)
            return
        self.model = mdl
        self.v_model_path.set(path)
        self.lbl_model.config(text=f"  {os.path.basename(path)}", fg=SUCCESS)
        self._update_class_list()
        if self.current_image_path:
            self._detect_and_display()
        elif not self._session_restored:
            # Model vừa load xong (lần đầu) → thử restore session
            self.after(100, self._auto_restore_session)

    def _auto_load_model(self):
        saved = self.v_model_path.get()
        if saved and os.path.isfile(saved):
            self._load_model(saved)
        else:
            default = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "yolo11n.pt")
            if os.path.isfile(default):
                self._load_model(default)

    def _auto_restore_session(self):
        """Tự động load lại folder + ảnh từ phiên làm việc trước."""
        if self._session_restored:
            return
        if not self.model:
            return
        self._session_restored = True

        folder   = _CFG.get("yolo.session.folder", "")
        last_img = _CFG.get("yolo.session.image", "")

        if not folder or not os.path.isdir(folder):
            return

        # Update path combo nhưng không trigger _load_path_input
        self.v_check_folder.set(folder)

        # Load folder (sẽ mở ảnh đầu tiên mặc định)
        self._load_folder(folder)

        # Nếu có ảnh được lưu và tồn tại → navigate tới đó
        if last_img and os.path.isfile(last_img) and last_img in self.image_list:
            self._open_image(last_img)

    def _update_class_list(self):
        self.lb_classes.delete(0, END)
        self.class_ids.clear()
        if self.model and hasattr(self.model, "names"):
            for cid, cname in sorted(self.model.names.items()):
                self.class_ids.append(cid)
                self.lb_classes.insert(END, f"[{cid}] {cname}")
        self._update_must_have_lists()

    def _update_path_combo(self, path: str):
        self.v_check_folder.set(path)
        _push_history("h.yolo.path", path)
        self.combo_path["values"] = _get_history("h.yolo.path")

    def _load_path_input(self):
        p = self.v_check_folder.get().strip()
        if not p:
            return
        if not self.model:
            messagebox.showwarning("Chưa có model", "Vui lòng chọn model trước.",
                                   parent=self.root)
            return
        if os.path.isdir(p):
            _push_history("h.yolo.path", p)
            self.combo_path["values"] = _get_history("h.yolo.path")
            self._load_folder(p)
        elif os.path.isfile(p):
            _push_history("h.yolo.path", p)
            self.combo_path["values"] = _get_history("h.yolo.path")
            self._load_image_list([p])
        else:
            messagebox.showwarning("Không tìm thấy",
                                   f"Đường dẫn không hợp lệ:\n{p}", parent=self.root)

    def _select_image(self):
        if not self.model:
            messagebox.showwarning("Chưa có model",
                                   "Vui lòng chọn model trước.", parent=self.root)
            return
        cur = self.v_check_folder.get().strip()
        init = (os.path.dirname(cur) if cur and os.path.isfile(cur)
                else cur if cur and os.path.isdir(cur)
                else _cfg_dir("yolo.last_image_dir") or None)
        path = filedialog.askopenfilename(
            title="Chọn ảnh",
            initialdir=init,
            filetypes=[("Image Files", "*.jpg *.jpeg *.png *.bmp *.webp")],
            parent=self.root)
        if path:
            self._update_path_combo(path)
            self._load_image_list([path])

    def _open_check_folder(self):
        p = self.v_check_folder.get().strip()
        d = p if os.path.isdir(p) else os.path.dirname(p) if p else ""
        if d and os.path.isdir(d):
            os.startfile(d)

    def _select_folder(self):
        if not self.model:
            messagebox.showwarning("Chưa có model",
                                   "Vui lòng chọn model trước.", parent=self.root)
            return
        cur = self.v_check_folder.get().strip()
        init = (cur if cur and os.path.isdir(cur)
                else os.path.dirname(cur) if cur
                else _cfg_dir("yolo.check_folder") or None)
        folder = filedialog.askdirectory(
            title="Chọn thư mục kiểm tra",
            initialdir=init,
            parent=self.root)
        if folder:
            self._update_path_combo(folder)
            self._load_folder(folder)

    def _scan_images(self, folder: str) -> list:
        """Trả về list ảnh trực tiếp trong folder (không đệ quy vào true/false)."""
        if not folder or not os.path.isdir(folder):
            return []
        return sorted([
            os.path.join(folder, f) for f in os.listdir(folder)
            if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS
        ])

    def _load_folder(self, folder: str):
        self._base_folder = folder
        _SKIP = {"true", "false"}
        if self.v_subfolder.get():
            files = sorted([
                os.path.join(root, f)
                for root, dirs, fnames in os.walk(folder)
                for f in fnames
                if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS
                and os.path.basename(root) not in _SKIP
            ])
            # prune true/false from os.walk in-place
        else:
            files = sorted([
                os.path.join(folder, f)
                for f in os.listdir(folder)
                if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS
            ])
        if not files:
            messagebox.showinfo("Thông báo",
                                "Không tìm thấy ảnh trong thư mục!", parent=self.root)
            return
        self._load_image_list(files)

    def _load_image_list(self, files: list):
        self._all_images = list(files)
        self._det_cache.clear()
        with self._lpr_cache_lock:
            self._lpr_cache.clear()
        self._grid_rendered_cache.clear()
        self._grid_page = 0
        if hasattr(self, "lbl_cache_info"):
            self.lbl_cache_info.config(text="")
        if hasattr(self, "_flt_class_combo"):
            self._flt_class_combo["values"] = ["Tất cả", "Không detect"]
            self._flt_class_var.set("Tất cả")
        if not self._base_folder and files:
            self._base_folder = os.path.dirname(files[0])
        # Thử load cache từ disk (nếu model đã load và iou khớp)
        _cache_loaded = self._load_det_cache_from_disk()
        if hasattr(self, "lbl_cache_info") and _cache_loaded:
            n_cached = len(self._det_cache)
            self.lbl_cache_info.config(text=f"✓{n_cached}/{len(files)} (disk)")
            self.after(0, self._update_class_filter_combo)
        self._active_filter = "all"
        for code, btn in self._filter_btns.items():
            btn.config(relief="sunken" if code == "all" else "flat",
                       bg="#252540" if code == "all" else CARD)
        self._rebuild_tree(files)
        self._update_filter_counts()
        if files:
            # Lưu folder vào session
            _CFG["yolo.session.folder"] = self._base_folder or os.path.dirname(files[0])
            _cfg_save()
            self._open_image(files[0])

    def _rebuild_tree(self, files: list):
        """Rebuild the sidebar tree from a (possibly filtered) file list."""
        self.image_list = list(files)
        self._tree_iid_map = {}
        self._path_to_iid = {}
        tree = self.tree_images
        tree.delete(*tree.get_children())

        use_hierarchy = (len(self._all_images) > 1
                         and self.v_subfolder.get()
                         and self._all_images)
        base_dir = os.path.commonpath(self._all_images) if use_hierarchy else None

        if base_dir and files:
            folder_iids = {}
            for f in files:
                state = _path_review_state(f)
                tag = state or "unreviewed"
                icon = _REVIEW_ICON[state]
                try:
                    rel = os.path.relpath(f, base_dir)
                    parts = rel.replace("\\", "/").split("/")
                except ValueError:
                    parts = [os.path.basename(f)]
                parent_iid = ""
                for depth, part in enumerate(parts[:-1]):
                    folder_key = "/".join(parts[:depth + 1])
                    if folder_key not in folder_iids:
                        iid = tree.insert(parent_iid, END,
                                          text=f"\U0001f4c1 {part}",
                                          open=True, tags=("folder",))
                        folder_iids[folder_key] = iid
                    parent_iid = folder_iids[folder_key]
                iid = tree.insert(parent_iid, END,
                                  text=f"{icon} {parts[-1]}", tags=(tag,))
                self._tree_iid_map[iid] = f
                self._path_to_iid[f] = iid
        else:
            for f in files:
                state = _path_review_state(f)
                tag = state or "unreviewed"
                icon = _REVIEW_ICON[state]
                iid = tree.insert("", END,
                                  text=f"{icon} {os.path.basename(f)}", tags=(tag,))
                self._tree_iid_map[iid] = f
                self._path_to_iid[f] = iid

        # Re-select current image if still in this list
        iid = self._path_to_iid.get(self.current_image_path)
        if iid:
            tree.selection_set(iid)
            tree.see(iid)

        self._schedule_grid_rebuild()

    def _schedule_search(self):
        if self._search_after:
            self.after_cancel(self._search_after)
        self._search_after = self.after(300,
            lambda: self._apply_filter(self._active_filter))

    def _toggle_search_hint(self):
        if self._hint_shown:
            self._hint_frame.pack_forget()
            self._hint_toggle_btn.config(text="?", fg="#6060a0")
        else:
            self._hint_frame.pack(fill=X, padx=4, pady=(0, 3),
                                   after=self._search_row_ref)
            self._hint_toggle_btn.config(text="▲", fg=ACCENT2)
        self._hint_shown = not self._hint_shown

    def _do_search(self):
        """Push keyword vào history rồi áp dụng filter."""
        val = self._v_search.get().strip()
        if val:
            _push_history("h.yolo.search", val)
            self._search_combo["values"] = _get_history("h.yolo.search")
        self._apply_filter(self._active_filter)

    def _apply_filter(self, filter_type: str):
        self._active_filter = filter_type
        for code, btn in self._filter_btns.items():
            btn.config(relief="sunken" if code == filter_type else "flat",
                       bg="#252540" if code == filter_type else CARD)
        base = self._base_folder
        if filter_type == "correct":
            filtered = self._scan_images(os.path.join(base, "true")) if base else []
        elif filter_type == "incorrect":
            filtered = self._scan_images(os.path.join(base, "false")) if base else []
        elif filter_type == "unreviewed":
            filtered = list(self._all_images)
        else:  # "all"
            true_imgs  = self._scan_images(os.path.join(base, "true"))  if base else []
            false_imgs = self._scan_images(os.path.join(base, "false")) if base else []
            filtered = list(self._all_images) + true_imgs + false_imgs
        search = self._v_search.get().strip().lower()
        if search:
            terms = search.split()
            _base = self._base_folder or ""
            def _matches(f, ts=terms, b=_base):
                name = os.path.basename(f).lower()
                try:
                    rel = os.path.relpath(f, b).replace("\\", "/").lower() if b else f.lower()
                except ValueError:
                    rel = f.lower()
                for t in ts:
                    if "*" in t or "?" in t:
                        if not fnmatch.fnmatch(name, t):
                            return False
                    else:
                        if t not in rel:
                            return False
                return True
            filtered = [f for f in filtered if _matches(f)]
        filtered = self._apply_det_filters(filtered)
        self._rebuild_tree(filtered)

    def _update_filter_counts(self):
        if not hasattr(self, "_filter_btns"):
            return
        base = self._base_folder
        # Đếm từ _review_state (in-memory marks) + filesystem (moved files)
        n_mem_ok  = sum(1 for p in self._all_images
                        if self._review_state.get(p) == "correct")
        n_mem_bad = sum(1 for p in self._all_images
                        if self._review_state.get(p) == "incorrect")
        n_unmarked = len(self._all_images) - n_mem_ok - n_mem_bad
        n_fs_ok  = len(self._scan_images(os.path.join(base, "true")))  if base else 0
        n_fs_bad = len(self._scan_images(os.path.join(base, "false"))) if base else 0
        n_ok  = n_mem_ok  + n_fs_ok
        n_bad = n_mem_bad + n_fs_bad
        n_all = len(self._all_images) + n_fs_ok + n_fs_bad
        for code, label in [("all",        f"All({n_all})"),
                             ("correct",    f"✓({n_ok})"),
                             ("incorrect",  f"✗({n_bad})"),
                             ("unreviewed", f"?({n_unmarked})")]:
            self._filter_btns[code].config(text=label)

    def _save_image_and_label(self, path: str, state: str) -> bool:
        """Move image + write detection label vào true/ hoặc false/ subfolder.
        Trả về True nếu di chuyển thành công."""
        if not os.path.isfile(path):
            return False
        sub = "true" if state == "correct" else "false"
        # Luôn dùng _base_folder; nếu ảnh đang ở true/ hoặc false/ thì dùng grandparent
        parent_name = os.path.basename(os.path.dirname(path))
        if parent_name in ("true", "false"):
            root = os.path.dirname(os.path.dirname(path))
        else:
            root = self._base_folder or os.path.dirname(path)
        dest_dir = os.path.join(root, sub)
        try:
            os.makedirs(dest_dir, exist_ok=True)
            dest_img = os.path.join(dest_dir, os.path.basename(path))
            shutil.move(path, dest_img)

            base = os.path.splitext(os.path.basename(path))[0]
            boxes = (self._last_results1[0].boxes
                     if self._last_results1 is not None else None)
            with open(os.path.join(dest_dir, f"{base}.txt"), "w", encoding="utf-8") as f:
                if boxes is not None and len(boxes):
                    for box in boxes:
                        cid = int(box.cls[0])
                        cx, cy, bw, bh = box.xywhn[0].tolist()
                        f.write(f"{cid} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")

            icon = "✓" if state == "correct" else "✗"
            self.v_status.set(
                f"{icon} Đã chuyển vào {sub}/: {os.path.basename(path)}")
            return True
        except Exception as e:
            self.v_status.set(f"Lỗi di chuyển: {e}")
            return False

    def _save_page_image(self, path: str) -> bool:
        """Move 1 ảnh vào true/ + ghi label từ _det_cache (không dùng _last_results1)."""
        if not os.path.isfile(path):
            return False
        parent_name = os.path.basename(os.path.dirname(path))
        if parent_name in ("true", "false"):
            root = os.path.dirname(os.path.dirname(path))
        else:
            root = self._base_folder or os.path.dirname(path)
        dest_dir = os.path.join(root, "true")
        try:
            os.makedirs(dest_dir, exist_ok=True)
            shutil.move(path, os.path.join(dest_dir, os.path.basename(path)))
            base = os.path.splitext(os.path.basename(path))[0]
            with self._det_cache_lock:
                det = self._det_cache.get(path)
            with open(os.path.join(dest_dir, f"{base}.txt"), "w", encoding="utf-8") as f:
                if det and det.get("boxes"):
                    for box_t in det["boxes"]:
                        cid, cx, cy, bw, bh = box_t[0], box_t[1], box_t[2], box_t[3], box_t[4]
                        f.write(f"{cid} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")
            return True
        except Exception:
            return False

    def _mark_page_correct(self):
        """Batch-đánh dấu đúng toàn trang — move file + ghi label, không navigate."""
        if not self._grid_cells:
            return
        paths = [c["path"] for c in self._grid_cells if c.get("path")]
        if not paths:
            return

        do_move  = bool(self._base_folder)
        moved    = []
        marked   = []
        icon     = _REVIEW_ICON.get("correct", "✓")

        # Unbind TreeviewSelect để tránh trigger navigation khi update tree items
        self.tree_images.unbind("<<TreeviewSelect>>")
        try:
            for p in paths:
                if do_move:
                    ok = self._save_page_image(p)
                    if ok:
                        moved.append(p)
                    else:
                        # Move thất bại → chỉ mark in-memory
                        self._review_state[p] = "correct"
                        marked.append(p)
                else:
                    self._review_state[p] = "correct"
                    marked.append(p)

                # Cập nhật tree icon (ảnh đã move sẽ biến mất sau _apply_filter)
                iid = self._path_to_iid.get(p)
                if iid:
                    try:
                        if self.tree_images.exists(iid):
                            old  = self.tree_images.item(iid, "text")
                            bare = old[2:] if len(old) > 2 else old
                            self.tree_images.item(iid,
                                                  text=f"{icon} {bare}",
                                                  tags=("correct",))
                    except Exception:
                        pass
        finally:
            self.tree_images.bind("<<TreeviewSelect>>", self._on_image_select)

        # Cập nhật tracking structures cho ảnh đã move
        for p in moved:
            self._review_state.pop(p, None)
            if p in self._all_images:
                self._all_images.remove(p)
            if p in self._det_cache:
                with self._det_cache_lock:
                    self._det_cache.pop(p, None)

        changed = len(moved) + len(marked)
        if changed:
            _CFG["yolo.review_states"] = self._review_state
            _cfg_save()
            # Refresh list + counts một lần duy nhất
            self._apply_filter(self._active_filter)
            self._update_filter_counts()

        self.lbl_mark_state.config(text=f"✓ {changed} ảnh", fg=SUCCESS)
        self.after(2500, lambda: self.lbl_mark_state.config(text=""))

    def _mark_page_incorrect(self):
        """Batch-đánh dấu sai toàn trang — move file vào false/ + ghi label."""
        if not self._grid_cells:
            return
        paths = [c["path"] for c in self._grid_cells if c.get("path")]
        if not paths:
            return

        icon  = _REVIEW_ICON.get("incorrect", "✗")
        moved = []
        marked = []

        self.tree_images.unbind("<<TreeviewSelect>>")
        try:
            for p in paths:
                if self._base_folder:
                    ok = self._save_image_and_label(p, "incorrect")
                    if ok:
                        moved.append(p)
                    else:
                        self._review_state[p] = "incorrect"
                        marked.append(p)
                else:
                    self._review_state[p] = "incorrect"
                    marked.append(p)

                iid = self._path_to_iid.get(p)
                if iid:
                    try:
                        if self.tree_images.exists(iid):
                            old  = self.tree_images.item(iid, "text")
                            bare = old[2:] if len(old) > 2 else old
                            self.tree_images.item(iid,
                                                  text=f"{icon} {bare}",
                                                  tags=("incorrect",))
                    except Exception:
                        pass
        finally:
            self.tree_images.bind("<<TreeviewSelect>>", self._on_image_select)

        for p in moved:
            self._review_state.pop(p, None)
            if p in self._all_images:
                self._all_images.remove(p)
            with self._det_cache_lock:
                self._det_cache.pop(p, None)

        changed = len(moved) + len(marked)
        if changed:
            _CFG["yolo.review_states"] = self._review_state
            _cfg_save()
            self._apply_filter(self._active_filter)
            self._update_filter_counts()

        self.lbl_mark_state.config(text=f"✗ {changed} ảnh", fg=ACCENT)
        self.after(2500, lambda: self.lbl_mark_state.config(text=""))

    def _mark_review(self, state: str):
        path = self.current_image_path
        if not path:
            return

        # Update status label
        icons = {"correct": "✓ Đúng", "incorrect": "✗ Sai", "": "↺ Đã xóa"}
        self.lbl_mark_state.config(
            text=icons.get(state, ""),
            fg=("#4caf50" if state == "correct"
                else ACCENT if state == "incorrect" else DIM))

        if state in ("correct", "incorrect"):
            moved = self._save_image_and_label(path, state)
            if moved:
                # Remove from all tracking data structures
                self._review_state.pop(path, None)
                _CFG["yolo.review_states"] = self._review_state
                _cfg_save()

                old_idx = (self.image_list.index(path)
                           if path in self.image_list else 0)
                # Remove from unreviewed list if it was there
                if path in self._all_images:
                    self._all_images.remove(path)
                self.current_image_path = None
                self._last_results1 = None

                self._apply_filter(self._active_filter)
                self._update_filter_counts()
                if self.image_list:
                    next_idx = min(old_idx, len(self.image_list) - 1)
                    self._open_image(self.image_list[next_idx])
                return

        # No move (unmark or move failed) — update state + tag only
        if state:
            self._review_state[path] = state
        else:
            self._review_state.pop(path, None)
        _CFG["yolo.review_states"] = self._review_state
        _cfg_save()

        iid = self._path_to_iid.get(path)
        if iid and self.tree_images.exists(iid):
            icon = _REVIEW_ICON[state]
            old_text = self.tree_images.item(iid, "text")
            bare = old_text[2:] if len(old_text) > 2 else old_text
            self.tree_images.item(iid,
                                  text=f"{icon} {bare}",
                                  tags=(state or "unreviewed",))
        self._update_filter_counts()

    def _open_image(self, path: str):
        self.current_image_path = path
        iid = self._path_to_iid.get(path)
        if iid:
            self.tree_images.selection_set(iid)
            self.tree_images.see(iid)
        n = len(self.image_list)
        try:
            pos = self.image_list.index(path) + 1
        except ValueError:
            pos = 0
        label = f"{pos}/{n}  " if n else ""
        self.v_status.set(f"{label}{os.path.basename(path)}")
        self._zoom_factor = 0.0
        self._img_pos   = [0, 0]
        self._pan_start = None
        self._update_filmstrip()
        self._detect_and_display()
        # Lưu ảnh đang xem vào session
        _CFG["yolo.session.image"] = path
        _cfg_save()

    def _is_active(self):
        """Trả về True nếu YOLO tab đang được chọn trong Notebook."""
        try:
            w = self
            while w is not None:
                p = getattr(w, "master", None)
                if p is None:
                    break
                if isinstance(p, ttk.Notebook):
                    return p.select() == str(w)
                w = p
        except Exception:
            pass
        return False

    def _bind_keys(self):
        """Chỉ bind các phím đặc thù YOLO; dùng guard _is_active để không
        override binding của tab khác (BBox Editor, Checker…).
        ←/→ KHÔNG bind ở đây — app.py đã xử lý qua _prev_image/_next_image."""
        def _guard(fn):
            def _inner(*_):
                if self._is_active():
                    fn()
                    return "break"
            return _inner

        _INPUT_TYPES = (Entry, Text, Spinbox, ttk.Combobox, ttk.Entry, ttk.Spinbox)

        def _input_focused():
            try:
                return isinstance(self.root.focus_get(), _INPUT_TYPES)
            except Exception:
                return False

        def _space_handler(*_):
            if not self._is_active() or _input_focused():
                return
            self._toggle_autoplay()
            return "break"

        self.root.bind("<Return>",    _guard(lambda: self._mark_review("correct")), "+")
        self.root.bind("<Delete>",    _guard(lambda: self._mark_review("incorrect")), "+")
        self.root.bind("<space>",     _space_handler, "+")
        def _copy_handler(*_):
            if self._is_active() and not _input_focused():
                self._copy_path()
                return "break"
        self.root.bind("<Control-c>", _copy_handler, "+")

    # ── Aliases cho app.py global routing ────────────────────────────────
    def _prev_image(self): self._nav_image(-1)
    def _next_image(self): self._nav_image(+1)

    def select_image(self):
        """Alias không underscore — Ctrl+O routing từ app.py."""
        self._select_image()

    def _run_detect(self):
        """F5 routing từ app.py — detect ảnh hiện tại nếu đã load."""
        if self.current_image_path and self.model:
            self._open_image(self.current_image_path)

    def _on_delete(self):
        """Delete routing từ app.py — mark ảnh hiện tại là incorrect."""
        if self._is_active():
            self._mark_review("incorrect")

    def _on_return(self):
        """Return routing từ app.py — mark ảnh hiện tại là correct."""
        if self._is_active():
            self._mark_review("correct")

    def _copy_path(self):
        """Copy ảnh hiện tại vào clipboard dưới dạng bitmap (Ctrl+C)."""
        if not self.current_image_path or not _PIL_OK:
            return
        try:
            import io, ctypes

            kernel32 = ctypes.windll.kernel32
            user32   = ctypes.windll.user32

            # Khai báo đầy đủ argtypes + restype cho mọi hàm nhận/trả handle 64-bit
            kernel32.GlobalAlloc.argtypes  = [ctypes.c_uint, ctypes.c_size_t]
            kernel32.GlobalAlloc.restype   = ctypes.c_void_p
            kernel32.GlobalLock.argtypes   = [ctypes.c_void_p]
            kernel32.GlobalLock.restype    = ctypes.c_void_p
            kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
            kernel32.GlobalUnlock.restype  = ctypes.c_bool
            user32.OpenClipboard.argtypes  = [ctypes.c_void_p]
            user32.OpenClipboard.restype   = ctypes.c_bool
            user32.EmptyClipboard.argtypes = []
            user32.EmptyClipboard.restype  = ctypes.c_bool
            user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
            user32.SetClipboardData.restype  = ctypes.c_void_p
            user32.CloseClipboard.argtypes = []
            user32.CloseClipboard.restype  = ctypes.c_bool

            img = Image.open(self.current_image_path).convert("RGB")
            buf = io.BytesIO()
            img.save(buf, "BMP")
            data = buf.getvalue()[14:]  # bỏ 14-byte BMP file header, giữ DIB
            buf.close()

            CF_DIB = 8
            GMEM_MOVEABLE = 0x0002
            h = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
            p = kernel32.GlobalLock(h)
            ctypes.memmove(p, data, len(data))
            kernel32.GlobalUnlock(h)
            user32.OpenClipboard(None)
            user32.EmptyClipboard()
            user32.SetClipboardData(CF_DIB, h)
            user32.CloseClipboard()

            self.lbl_result.config(
                text=f"📋 Đã copy ảnh: {os.path.basename(self.current_image_path)}",
                fg=DIM)
            self.after(2000, self._restore_result_label)
        except Exception as e:
            self.v_status.set(f"Lỗi copy ảnh: {e}")

    def _restore_result_label(self):
        if self._last_n_det < 0:
            return
        if self._last_n_det > 0:
            self.lbl_result.config(
                text=f"Phát hiện {self._last_n_det} đối tượng", fg=SUCCESS)
        else:
            self.lbl_result.config(text="Không phát hiện đối tượng nào", fg=DIM)

    def _on_canvas1_zoom(self, _event=None):
        pil = self._pil1_full or self._pil1_orig
        if pil is None:
            return
        from ...core.ui_helpers import _zoom_image_window
        fname = os.path.basename(self.current_image_path) if self.current_image_path else "ảnh"
        _zoom_image_window(self.root, pil, fname)

    def _on_canvas2_zoom(self, _event=None):
        if self._pil2_full is None:
            return
        from ...core.ui_helpers import _zoom_image_window
        fname = os.path.basename(self.current_image_path) if self.current_image_path else "ảnh"
        _zoom_image_window(self.root, self._pil2_full, f"{fname} — Model 2")

    def _nav_image(self, step: int):
        if not self.image_list:
            return
        if self.current_image_path in self.image_list:
            idx = self.image_list.index(self.current_image_path)
        else:
            idx = 0
        new_idx = (idx + step) % len(self.image_list)
        self._open_image(self.image_list[new_idx])

    def _on_image_select(self, _event=None):
        sel = self.tree_images.selection()
        if not sel:
            return
        iid = sel[0]
        path = self._tree_iid_map.get(iid)
        if path and path != self.current_image_path:
            self._open_image(path)

    # ======================================================== ZOOM / RENDER ==

    def _render_display(self):
        """Re-render Canvas từ PIL với zoom & pan hiện tại."""
        if not _PIL_OK:
            return
        pil = (self._pil1_orig
               if (self.v_show_original.get() and self._pil1_orig)
               else self._pil1_full)
        if pil is None:
            return
        self.canvas.update_idletasks()
        cw = max(self.canvas.winfo_width(),  400)
        ch = max(self.canvas.winfo_height(), 300)
        if self._zoom_factor == 0.0:
            scale = min(cw / pil.width, ch / pil.height)  # fit inside, giữ tỉ lệ
            nw = max(1, int(pil.width  * scale))
            nh = max(1, int(pil.height * scale))
            img = pil.resize((nw, nh), Image.Resampling.LANCZOS)
            self._img_pos = [(cw - nw) // 2, (ch - nh) // 2]
            self.lbl_zoom.config(text="Fit")
        else:
            nw = max(1, int(pil.width  * self._zoom_factor))
            nh = max(1, int(pil.height * self._zoom_factor))
            img = pil.resize((nw, nh), Image.Resampling.LANCZOS)
            self.lbl_zoom.config(text=f"{int(self._zoom_factor * 100)}%")
        self._photo_ref = ImageTk.PhotoImage(image=img)
        self.canvas.delete("all")
        self.canvas.create_image(self._img_pos[0], self._img_pos[1],
                                  anchor=NW, image=self._photo_ref, tags="img")

    def _on_canvas_configure(self, _event=None):
        """Auto-refit khi canvas thay đổi kích thước."""
        if self._zoom_factor == 0.0:
            self._render_display()

    def _on_pan_press(self, event):
        if self._zoom_factor == 0.0:
            return
        self._pan_start  = (event.x, event.y)
        self._pan_origin = list(self._img_pos)

    def _on_pan_drag(self, event):
        if self._pan_start is None or self._zoom_factor == 0.0:
            return
        dx = event.x - self._pan_start[0]
        dy = event.y - self._pan_start[1]
        self._img_pos = [self._pan_origin[0] + dx, self._pan_origin[1] + dy]
        # Di chuyển item trực tiếp — không render lại
        items = self.canvas.find_withtag("img")
        if items:
            self.canvas.coords(items[0], self._img_pos[0], self._img_pos[1])

    def _on_mmb_press(self, event):
        """Middle mouse / Ctrl+drag — bắt đầu pan (hoạt động ở mọi zoom level)."""
        pil = self._pil1_full or self._pil1_orig
        if self._zoom_factor == 0.0 and pil:
            cw = max(self.canvas.winfo_width(), 400)
            ch = max(self.canvas.winfo_height(), 300)
            fit = min(cw / pil.width, ch / pil.height)
            self._zoom_factor = fit
            nw = int(pil.width * fit)
            nh = int(pil.height * fit)
            self._img_pos = [(cw - nw) // 2, (ch - nh) // 2]
            self._render_display()
        self._mmb_pan_start  = (event.x, event.y)
        self._mmb_pan_origin = list(self._img_pos)
        self.canvas.config(cursor="fleur")

    def _on_mmb_drag(self, event):
        """Middle mouse / Ctrl+drag — kéo pan."""
        if not hasattr(self, "_mmb_pan_start") or self._mmb_pan_start is None:
            return
        dx = event.x - self._mmb_pan_start[0]
        dy = event.y - self._mmb_pan_start[1]
        self._img_pos = [self._mmb_pan_origin[0] + dx,
                         self._mmb_pan_origin[1] + dy]
        items = self.canvas.find_withtag("img")
        if items:
            self.canvas.coords(items[0], self._img_pos[0], self._img_pos[1])

    def _on_mmb_release(self, event):
        """Middle mouse / Ctrl+drag — kết thúc pan."""
        self._mmb_pan_start = None
        self.canvas.config(cursor="fleur")

    def _zoom_step(self, delta: float):
        """delta=0.0 resets to fit; otherwise shifts zoom factor."""
        if delta == 0.0:
            self._zoom_factor = 0.0
            self._img_pos = [0, 0]
        else:
            pil = self._pil1_full
            cw  = max(self.canvas.winfo_width(),  400)
            ch  = max(self.canvas.winfo_height(), 300)
            if self._zoom_factor == 0.0:
                if pil:
                    self._zoom_factor = min(cw / pil.width, ch / pil.height)
                else:
                    self._zoom_factor = 1.0
            old = self._zoom_factor
            self._zoom_factor = max(0.05, min(8.0, self._zoom_factor + delta))
            # Zoom về tâm canvas
            if pil and old > 0:
                ratio = self._zoom_factor / old
                cx, cy = cw / 2, ch / 2
                self._img_pos[0] = int(cx - (cx - self._img_pos[0]) * ratio)
                self._img_pos[1] = int(cy - (cy - self._img_pos[1]) * ratio)
        self._render_display()

    def _on_canvas_scroll(self, event):
        """Scroll to zoom centered on cursor position (like BBoxEditor)."""
        pil = self._pil1_full or self._pil1_orig
        if pil is None:
            return
        factor = 1.15 if event.delta > 0 else (1.0 / 1.15)
        cw = max(self.canvas.winfo_width(), 400)
        ch = max(self.canvas.winfo_height(), 300)
        if self._zoom_factor == 0.0:
            fit = min(cw / pil.width, ch / pil.height)
            self._zoom_factor = fit
            nw = int(pil.width * fit)
            nh = int(pil.height * fit)
            self._img_pos = [(cw - nw) // 2, (ch - nh) // 2]
        old = self._zoom_factor
        new = max(0.05, min(8.0, old * factor))
        if abs(new - old) < 0.001:
            return
        ratio = new / old
        cx, cy = event.x, event.y
        self._img_pos[0] = int(cx - (cx - self._img_pos[0]) * ratio)
        self._img_pos[1] = int(cy - (cy - self._img_pos[1]) * ratio)
        self._zoom_factor = new
        self._render_display()

    # ======================================================== AUTO-PLAY ==

    def _toggle_autoplay(self):
        if self._autoplay_id is not None:
            self.root.after_cancel(self._autoplay_id)
            self._autoplay_id = None
            self.btn_autoplay.config(text="▶ Auto", bg="#2e5fa3")
        else:
            self.btn_autoplay.config(text="■ Stop", bg=ACCENT)
            self._schedule_autoplay()

    def _schedule_autoplay(self):
        try:
            interval = float(self.spin_interval.get())
        except ValueError:
            interval = 2.0
        ms = max(200, int(interval * 1000))
        self._autoplay_id = self.root.after(ms, self._autoplay_step)

    def _autoplay_step(self):
        if self._autoplay_id is None:
            return
        self._nav_image(+1)
        self._schedule_autoplay()

    # ======================================================== BATCH EXPORT ==

    def _batch_export(self):
        if not self.model:
            messagebox.showwarning("Chưa có model",
                                   "Vui lòng chọn model trước.", parent=self.root)
            return
        if not self.image_list:
            messagebox.showwarning("Chưa có ảnh",
                                   "Vui lòng chọn thư mục ảnh trước.", parent=self.root)
            return
        if not _CV2_OK:
            messagebox.showerror("Thiếu thư viện",
                                  "pip install opencv-python", parent=self.root)
            return

        out_dir = filedialog.askdirectory(
            title="Chọn thư mục lưu kết quả",
            initialdir=_cfg_dir("yolo.export_dir") or None,
            parent=self.root)
        if not out_dir:
            return
        _CFG["yolo.export_dir"] = out_dir
        _cfg_save()

        draw_on_image = self.v_export_draw.get()
        rename_file   = self.v_export_rename.get()

        _alive = [True]

        popup = Toplevel(self.root)
        popup.title("Export kết quả — Batch Detection")
        popup.configure(bg=BG)
        popup.geometry("560x320")
        popup.protocol("WM_DELETE_WINDOW", lambda: [_alive.__setitem__(0, False), popup.destroy()])

        Label(popup, text=f"Đang xử lý {len(self.image_list)} ảnh ...",
              font=F_BOLD, bg=BG, fg=TEXT).pack(pady=(12, 4))

        pb = ttk.Progressbar(popup, mode="determinate",
                              maximum=len(self.image_list))
        pb.pack(fill=X, padx=16, pady=(0, 4))

        v_prog = StringVar(value="0 / 0")
        Label(popup, textvariable=v_prog,
              font=F_MONO, bg=BG, fg=DIM).pack()

        txt_frame = Frame(popup, bg=BG)
        txt_frame.pack(fill=BOTH, expand=True, padx=8, pady=8)
        sb_log = Scrollbar(txt_frame, orient=VERTICAL)
        sb_log.pack(side=RIGHT, fill=Y)
        log_text = Text(txt_frame, bg="#0d0d1a", fg=TEXT, font=F_MONO,
                        relief="flat", bd=0, yscrollcommand=sb_log.set,
                        state=DISABLED)
        log_text.pack(fill=BOTH, expand=True)
        sb_log.config(command=log_text.yview)

        def _safe(fn):
            def _inner(*a, **kw):
                if not _alive[0]:
                    return
                try:
                    fn(*a, **kw)
                except Exception:
                    pass
            return _inner

        def append(line):
            log_text.config(state=NORMAL)
            log_text.insert(END, line + "\n")
            log_text.see(END)
            log_text.config(state=DISABLED)

        # Capture tất cả params trên main thread (Tkinter không thread-safe)
        sel_cls  = self._get_sel_classes()
        conf_val = max(self.v_conf_thresh.get(), self.v_conf.get())
        iou_val  = self.v_iou.get()
        line_w   = max(1, self.v_line_width.get())
        font_sz  = max(6, self.v_font_size.get())

        def run():
            import time
            from concurrent.futures import ThreadPoolExecutor


            images = list(self.image_list)
            total  = len(images)
            ok     = 0
            BATCH  = 8  # số ảnh predict cùng lúc

            log_buf  = []
            last_ui  = [time.monotonic()]
            pending  = []

            def _save_io(img_bgr, boxes_data, out_stem):
                try:
                    cv2.imwrite(os.path.join(out_dir, f"{out_stem}.jpg"), img_bgr)
                    with open(os.path.join(out_dir, f"{out_stem}.txt"),
                              "w", encoding="utf-8") as f:
                        for cid, cx, cy, bw, bh in boxes_data:
                            f.write(f"{cid} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")
                except Exception:
                    pass

            def _ui_flush(done, chunk):
                try:
                    pb.config(value=done)
                    v_prog.set(f"{done} / {total}")
                    if chunk:
                        append(chunk)
                except Exception:
                    pass

            io_pool = ThreadPoolExecutor(max_workers=4)

            for batch_start in range(0, total, BATCH):
                if not _alive[0]:
                    break
                batch_paths = images[batch_start:batch_start + BATCH]
                try:
                    results = self.model.predict(
                        source=batch_paths, classes=sel_cls,
                        conf=conf_val, iou=iou_val,
                        imgsz=640, agnostic_nms=True, verbose=False)
                    for img_path, res in zip(batch_paths, results):
                        base     = os.path.splitext(os.path.basename(img_path))[0]
                        out_stem = f"{base}_det" if rename_file else base
                        img_bgr  = (res.plot(line_width=line_w, font_size=font_sz)
                                    if draw_on_image else cv2.imread(img_path))
                        # Extract box data thành list thuần Python trước khi pass sang thread
                        boxes_data = []
                        if res.boxes is not None and len(res.boxes):
                            for box in res.boxes:
                                cid = int(box.cls[0])
                                cx, cy, bw, bh = box.xywhn[0].tolist()
                                boxes_data.append((cid, cx, cy, bw, bh))
                        if img_bgr is not None:
                            pending.append(
                                io_pool.submit(_save_io, img_bgr, boxes_data, out_stem))
                        n = len(boxes_data)
                        log_buf.append(f"  OK  {os.path.basename(img_path)}  ({n} obj)")
                        ok += 1
                except Exception as ex:
                    for p in batch_paths:
                        log_buf.append(f"  ERR {os.path.basename(p)}: {ex}")

                done = min(batch_start + BATCH, total)
                now  = time.monotonic()
                # Update UI tối đa mỗi 0.4s để không flood event queue
                if now - last_ui[0] >= 0.4 or done >= total:
                    last_ui[0] = now
                    chunk = "\n".join(log_buf); log_buf.clear()
                    self.root.after(0, _safe(lambda d=done, c=chunk: _ui_flush(d, c)))

            # Chờ tất cả I/O ghi xong
            for fut in pending:
                try:
                    fut.result(timeout=60)
                except Exception:
                    pass
            io_pool.shutdown(wait=False)

            self.root.after(0, _safe(lambda: pb.config(value=total)))
            self.root.after(0, _safe(lambda:
                append(f"\nHoàn tất: {ok}/{total} ảnh  →  {out_dir}")))

        threading.Thread(target=run, daemon=True).start()

    # ======================================================== DETECT ALL ==

    def _detect_all(self):
        if not self.model:
            messagebox.showwarning("Chưa có model",
                                   "Vui lòng chọn model trước.", parent=self.root)
            return
        if not self._all_images:
            messagebox.showwarning("Chưa có ảnh",
                                   "Vui lòng chọn thư mục ảnh trước.", parent=self.root)
            return
        if self._det_running:
            self._det_stop_flag = True
            return
        if not _CV2_OK or not _YOLO_OK:
            messagebox.showerror("Thiếu thư viện",
                                  "pip install ultralytics opencv-python", parent=self.root)
            return

        if hasattr(self, "lbl_cache_info"):
            self.lbl_cache_info.config(text="⏳…")

        all_images = list(self._all_images)
        sel_cls = self._get_sel_classes()
        conf    = max(self.v_conf_thresh.get(), self.v_conf.get())
        iou     = self.v_iou.get()

        def _prepare():
            # Load disk cache nếu bộ nhớ rỗng — chạy ở background để không block UI
            with self._det_cache_lock:
                cache_empty = not self._det_cache
            if cache_empty:
                self._load_det_cache_from_disk()

            # Tính pending: O(n) set lookup, không I/O
            with self._det_cache_lock:
                cached_nc = {os.path.normcase(k) for k in self._det_cache}
            pending = [p for p in all_images
                       if os.path.normcase(p) not in cached_nc]

            self.root.after(0, lambda: self._detect_all_run(
                pending, all_images, sel_cls, conf, iou))

        threading.Thread(target=_prepare, daemon=True).start()

    def _detect_all_run(self, pending: list, all_images: list,
                        sel_cls, conf: float, iou: float):
        """Tiếp tục detect sau khi pending list đã được tính trên background thread."""
        if not pending:
            n = len(self._det_cache)
            if hasattr(self, "lbl_cache_info"):
                self.lbl_cache_info.config(text=f"✓{n}/{n} (đã xong)")
            return

        self._det_stop_flag = False
        self._det_running = True
        self.btn_detect_all.config(text="■ Dừng", bg=ACCENT, fg="white")
        n_already   = len(all_images) - len(pending)
        n_total     = len(all_images)
        do_lpr      = (self.v_lpr_batch.get() and self.v_check_lpr.get()
                       and _REQ_OK and _PIL_OK)
        lpr_urls_b  = ([v.get().strip() for v in self._lpr_url_vars
                        if v.get().strip()] if do_lpr else [])
        lpr_tmout_b = self._lpr_timeout_var.get() if do_lpr else 10
        lpr_full_b  = [v.get() for v in self._lpr_fullimg_vars] if do_lpr else []

        def run():
            import time
            BATCH     = 8
            last_ui   = time.monotonic()
            n_pending = len(pending)

            for batch_start in range(0, n_pending, BATCH):
                if self._det_stop_flag:
                    break
                batch_paths = pending[batch_start:batch_start + BATCH]
                try:
                    results = self.model.predict(
                        source=batch_paths, classes=sel_cls,
                        conf=conf, iou=iou, imgsz=640,
                        agnostic_nms=True, verbose=False)
                    for img_path, res in zip(batch_paths, results):
                        boxes = res.boxes
                        n_det = len(boxes) if boxes is not None else 0
                        classes_count = {}
                        box_list = []
                        if boxes is not None and len(boxes):
                            for box in boxes:
                                cid        = int(box.cls[0])
                                conf_score = float(box.conf[0])
                                classes_count[cid] = classes_count.get(cid, 0) + 1
                                cx_n, cy_n, w_n, h_n = box.xywhn[0].tolist()
                                w_px = float(box.xywh[0][2])
                                h_px = float(box.xywh[0][3])
                                box_list.append((cid, cx_n, cy_n, w_n, h_n, w_px, h_px, conf_score))
                        with self._det_cache_lock:
                            self._det_cache[img_path] = {
                                "n": n_det,
                                "classes": classes_count,
                                "boxes": box_list,
                            }
                        # ── LPR batch ──────────────────────────────────────
                        if do_lpr and lpr_urls_b and box_list:
                            lpr_res = self._lpr_batch_for_path(
                                img_path, box_list, lpr_urls_b, lpr_tmout_b,
                                lpr_full_b)
                            with self._lpr_cache_lock:
                                self._lpr_cache[img_path] = lpr_res
                except Exception:
                    pass

                done_pending = min(batch_start + BATCH, n_pending)
                done_total   = n_already + done_pending
                now = time.monotonic()
                if now - last_ui >= 0.5 or done_pending >= n_pending:
                    last_ui = now
                    self.root.after(0, lambda d=done_total, t=n_total:
                        self.lbl_cache_info.config(text=f"{d}/{t}"))

            self.root.after(0, self._on_detect_all_done)

        threading.Thread(target=run, daemon=True).start()

    def _detect_page(self):
        """Detect chỉ các ảnh trên trang grid hiện tại."""
        if not self.model:
            messagebox.showwarning("Chưa có model",
                                   "Vui lòng chọn model trước.", parent=self.root)
            return
        if not self._grid_cells:
            return
        if self._det_running:
            messagebox.showwarning("Đang chạy",
                                   "Detect All đang chạy, vui lòng đợi.", parent=self.root)
            return
        if not _CV2_OK or not _YOLO_OK:
            return

        page_paths = [c["path"] for c in self._grid_cells if c.get("path")]
        if not page_paths:
            return

        total       = len(page_paths)
        self.btn_detect_page.config(text="■ …", bg=ACCENT, fg="white")
        self.lbl_cache_info.config(text=f"0/{total}")
        sel_cls     = self._get_sel_classes()
        conf        = max(self.v_conf_thresh.get(), self.v_conf.get())
        iou         = self.v_iou.get()
        do_lpr      = (self.v_lpr_batch.get() and self.v_check_lpr.get()
                       and _REQ_OK and _PIL_OK)
        lpr_urls_p  = ([v.get().strip() for v in self._lpr_url_vars
                        if v.get().strip()] if do_lpr else [])
        lpr_tmout_p = self._lpr_timeout_var.get() if do_lpr else 10
        lpr_full_p  = [v.get() for v in self._lpr_fullimg_vars] if do_lpr else []

        def run():
            import time
            BATCH   = 8
            for batch_start in range(0, total, BATCH):
                batch = page_paths[batch_start:batch_start + BATCH]
                try:
                    results = self.model.predict(
                        source=batch, classes=sel_cls,
                        conf=conf, iou=iou, imgsz=640,
                        agnostic_nms=True, verbose=False)
                    for img_path, res in zip(batch, results):
                        boxes = res.boxes
                        n_det = len(boxes) if boxes is not None else 0
                        classes_count = {}
                        box_list = []
                        if boxes is not None and len(boxes):
                            for box in boxes:
                                cid        = int(box.cls[0])
                                conf_score = float(box.conf[0])
                                classes_count[cid] = classes_count.get(cid, 0) + 1
                                cx_n, cy_n, w_n, h_n = box.xywhn[0].tolist()
                                w_px = float(box.xywh[0][2])
                                h_px = float(box.xywh[0][3])
                                box_list.append((cid, cx_n, cy_n, w_n, h_n, w_px, h_px, conf_score))
                        with self._det_cache_lock:
                            self._det_cache[img_path] = {
                                "n": n_det, "classes": classes_count, "boxes": box_list,
                            }
                        # ── LPR batch ──────────────────────────────────────
                        if do_lpr and lpr_urls_p and box_list:
                            lpr_res = self._lpr_batch_for_path(
                                img_path, box_list, lpr_urls_p, lpr_tmout_p,
                                lpr_full_p)
                            with self._lpr_cache_lock:
                                self._lpr_cache[img_path] = lpr_res
                except Exception:
                    pass
                done = min(batch_start + BATCH, total)
                self.root.after(0, lambda d=done, t=total:
                    self.lbl_cache_info.config(text=f"{d}/{t}"))

            self.root.after(0, self._on_detect_page_done)

        threading.Thread(target=run, daemon=True).start()

    def _on_detect_page_done(self):
        self.btn_detect_page.config(text="⚡ Detect trang", bg="#102030", fg="#4caf50")
        n = len(self._det_cache)
        total = len(self._all_images)
        self.lbl_cache_info.config(text=f"✓{n}/{total}")
        self._grid_rendered_cache.clear()
        self._rebuild_grid()
        self._save_det_cache_to_disk()

    def _on_detect_all_progress(self, done: int, total: int):
        self.lbl_cache_info.config(text=f"{done}/{total}")

    def _on_detect_all_done(self):
        self._det_running = False
        self._det_stop_flag = False
        self.btn_detect_all.config(text="⚡ Detect All",
                                   bg="#103020", fg="#4caf50")
        n = len(self._det_cache)
        total = len(self._all_images)
        self.lbl_cache_info.config(text=f"✓{n}/{total}")
        self._grid_rendered_cache.clear()
        self._update_class_filter_combo()
        self._apply_filter(self._active_filter)
        self._rebuild_grid()
        self._save_det_cache_to_disk()

    def _update_class_filter_combo(self):
        if not hasattr(self, "_flt_class_combo"):
            return
        all_classes = {}
        with self._det_cache_lock:
            snapshot = list(self._det_cache.values())
        for data in snapshot:
            for cid in data["classes"]:
                name = (self.model.names.get(cid, str(cid))
                        if self.model and hasattr(self.model, "names") else str(cid))
                all_classes[cid] = name
        vals = (["Tất cả", "Không detect"] +
                [f"[{cid}] {name}" for cid, name in sorted(all_classes.items())])
        cur = self._flt_class_var.get()
        self._flt_class_combo["values"] = vals
        if cur not in vals:
            self._flt_class_var.set("Tất cả")
        self._update_must_have_lists()

    # ================================================= CACHE DISK PERSISTENCE ==

    def _save_det_cache_to_disk(self):
        """Lưu _det_cache ra file JSON trong folder (background thread, atomic write)."""
        folder = self._base_folder
        if not folder or not os.path.isdir(folder):
            return
        cache_file = os.path.join(folder, ".kztek_det_cache.json")
        model_path = self.v_model_path.get()
        conf = max(self.v_conf_thresh.get(), self.v_conf.get())
        iou  = self.v_iou.get()

        # Snapshot toàn bộ cache trên main thread (thread-safe)
        try:
            with self._det_cache_lock:
                data = {
                    k: {
                        "n": v["n"],
                        "classes": {str(ck): cv for ck, cv in v["classes"].items()},
                        "boxes": [list(b) for b in v["boxes"]],
                    }
                    for k, v in self._det_cache.items()
                }
        except Exception as e:
            if hasattr(self, "v_status"):
                self.v_status.set(f"⚠ Snapshot cache lỗi: {e}")
            return

        payload = {
            "meta": {"model": model_path, "conf": round(conf, 4),
                     "iou": round(iou, 4), "version": 1},
            "data": data,
        }
        n = len(data)

        def _write():
            import json as _json
            tmp_file = cache_file + ".tmp"
            try:
                with open(tmp_file, "w", encoding="utf-8") as f:
                    _json.dump(payload, f, ensure_ascii=False)
                # Atomic rename — tránh corrupt nếu crash giữa chừng
                try:
                    os.replace(tmp_file, cache_file)
                except Exception:
                    os.rename(tmp_file, cache_file)
                self.root.after(0, lambda: (
                    hasattr(self, "lbl_cache_info") and
                    self.lbl_cache_info.config(text=f"✓{n} (đã lưu)")))
            except Exception as e:
                try:
                    if os.path.isfile(tmp_file):
                        os.remove(tmp_file)
                except Exception:
                    pass
                err = str(e)
                self.root.after(0, lambda msg=err: (
                    hasattr(self, "v_status") and
                    self.v_status.set(f"⚠ Lưu cache thất bại: {msg}")))

        threading.Thread(target=_write, daemon=True).start()

    def _load_det_cache_from_disk(self) -> bool:
        """Load _det_cache từ file JSON nếu model + iou khớp.
        Trả về True nếu load được ít nhất 1 ảnh."""
        import json as _json
        folder = self._base_folder
        if not folder or not os.path.isdir(folder):
            return False
        cache_file = os.path.join(folder, ".kztek_det_cache.json")
        if not os.path.isfile(cache_file):
            return False
        model_path = self.v_model_path.get()
        if not model_path:
            return False
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                payload = _json.load(f)
            meta = payload.get("meta", {})
            # Invalidate nếu model hoặc iou thay đổi (conf có thể filter lại display-time)
            if meta.get("model") != model_path:
                return False
            if abs(meta.get("iou", 0.0) - self.v_iou.get()) > 0.005:
                return False
            data = payload.get("data", {})
            # Dùng set từ _all_images thay vì os.path.isfile() để tránh 16k I/O calls
            valid_nc = {os.path.normcase(p) for p in self._all_images} if self._all_images else None
            loaded = {}
            for img_path, v in data.items():
                if valid_nc is not None and os.path.normcase(img_path) not in valid_nc:
                    continue
                loaded[img_path] = {
                    "n": v["n"],
                    "classes": {int(ck): cv for ck, cv in v.get("classes", {}).items()},
                    "boxes": [tuple(b) for b in v.get("boxes", [])],
                }
            if not loaded:
                return False
            with self._det_cache_lock:
                self._det_cache.update(loaded)
            return True
        except Exception:
            return False

    def _clear_cache(self):
        """Xóa toàn bộ detect cache (memory + file disk)."""
        with self._det_cache_lock:
            self._det_cache.clear()
        self._grid_rendered_cache.clear()
        folder = self._base_folder
        if folder:
            cache_file = os.path.join(folder, ".kztek_det_cache.json")
            try:
                if os.path.isfile(cache_file):
                    os.remove(cache_file)
            except Exception:
                pass
        if hasattr(self, "lbl_cache_info"):
            self.lbl_cache_info.config(text="")
        self._schedule_grid_rebuild()

    def _schedule_det_filter(self):
        if self._flt_schedule_after:
            self.after_cancel(self._flt_schedule_after)
        self._flt_schedule_after = self.after(
            300, lambda: self._apply_filter(self._active_filter))

    def _clear_det_filters(self):
        self._flt_class_var.set("Tất cả")
        self._flt_ndet_min_var.set("")
        self._flt_ndet_max_var.set("")
        self._flt_area_min_var.set("")
        self._flt_area_max_var.set("")
        self._flt_w_min_var.set("")
        self._flt_w_max_var.set("")
        self._flt_h_min_var.set("")
        self._flt_h_max_var.set("")
        if hasattr(self, "_must_have_lb"):
            self._must_have_lb.selection_clear(0, END)
        if hasattr(self, "_must_not_lb"):
            self._must_not_lb.selection_clear(0, END)
        self._flt_lpr_var.set("Tất cả")
        self._apply_filter(self._active_filter)

    def _get_must_have_ids(self) -> set:
        if not hasattr(self, "_must_have_lb"):
            return set()
        try:
            return {int(self._must_have_lb.get(i).split("]")[0].lstrip("["))
                    for i in self._must_have_lb.curselection()}
        except Exception:
            return set()

    def _get_must_not_have_ids(self) -> set:
        if not hasattr(self, "_must_not_lb"):
            return set()
        try:
            return {int(self._must_not_lb.get(i).split("]")[0].lstrip("["))
                    for i in self._must_not_lb.curselection()}
        except Exception:
            return set()

    def _update_must_have_lists(self):
        """Điền danh sách class vào 2 listbox phải/không có nhãn."""
        if not hasattr(self, "_must_have_lb"):
            return
        all_classes: dict = {}
        if self.model and hasattr(self.model, "names"):
            all_classes = dict(self.model.names)
        elif self._det_cache:
            with self._det_cache_lock:
                snapshot = list(self._det_cache.values())
            for data in snapshot:
                for cid in data["classes"]:
                    all_classes.setdefault(cid, str(cid))
        mh_sel = set(self._must_have_lb.curselection())
        mn_sel = set(self._must_not_lb.curselection())
        self._must_have_lb.delete(0, END)
        self._must_not_lb.delete(0, END)
        for cid, name in sorted(all_classes.items()):
            color = _THUMB_PALETTE[cid % len(_THUMB_PALETTE)]
            label = f"[{cid}] {name}"
            self._must_have_lb.insert(END, label)
            self._must_have_lb.itemconfig(END, fg=color)
            self._must_not_lb.insert(END, label)
            self._must_not_lb.itemconfig(END, fg=color)
        # Khôi phục selection (nếu list không thay đổi)
        for i in mh_sel:
            if i < self._must_have_lb.size():
                self._must_have_lb.selection_set(i)
        for i in mn_sel:
            if i < self._must_not_lb.size():
                self._must_not_lb.selection_set(i)

    def _apply_det_filters(self, files: list) -> list:
        """Lọc ảnh theo detect cache (class, n_det, kích thước bbox)."""
        def _fv(var):
            v = var.get().strip()
            try: return float(v) if v else None
            except ValueError: return None

        cls_filter    = self._flt_class_var.get()
        ndet_min      = _fv(self._flt_ndet_min_var)
        ndet_max      = _fv(self._flt_ndet_max_var)
        area_min      = _fv(self._flt_area_min_var)
        area_max      = _fv(self._flt_area_max_var)
        w_min         = _fv(self._flt_w_min_var)
        w_max         = _fv(self._flt_w_max_var)
        h_min         = _fv(self._flt_h_min_var)
        h_max         = _fv(self._flt_h_max_var)
        must_have_ids = self._get_must_have_ids()
        must_not_ids  = self._get_must_not_have_ids()
        lpr_filter    = self._flt_lpr_var.get()

        has_det_filter = (
            cls_filter not in ("Tất cả", "") or
            any(v is not None for v in (ndet_min, ndet_max,
                                        area_min, area_max,
                                        w_min, w_max, h_min, h_max)) or
            bool(must_have_ids) or
            bool(must_not_ids)
        )
        has_lpr_filter = lpr_filter not in ("Tất cả", "")

        if not has_det_filter and not has_lpr_filter:
            return files
        if has_det_filter and not self._det_cache and not has_lpr_filter:
            return files

        result = []
        for f in files:
            data = self._det_cache.get(f)
            if data is None:
                # Chưa detect → ẩn nếu có filter detect tích cực
                if ndet_min is not None and ndet_min > 0:
                    continue
                if cls_filter not in ("Tất cả", ""):
                    continue
                if any(v is not None for v in (area_min, area_max,
                                               w_min, w_max, h_min, h_max)):
                    continue
                if must_have_ids or must_not_ids:
                    continue
                # Filter LPR cho ảnh chưa detect
                if has_lpr_filter:
                    with self._lpr_cache_lock:
                        _lpr_e = self._lpr_cache.get(f)
                    if lpr_filter == "Chưa nhận dạng":
                        if _lpr_e is not None:
                            continue
                    elif lpr_filter == "Có biển số":
                        if not (_lpr_e is not None
                                and any(p for _, _, _, _, p in _lpr_e)):
                            continue
                    elif lpr_filter == "Không biển số":
                        if not (_lpr_e is not None
                                and not any(p for _, _, _, _, p in _lpr_e)):
                            continue
                result.append(f)
                continue

            n = data["n"]
            detected_cls = set(data["classes"].keys())

            # Filter class (combobox)
            if cls_filter == "Không detect":
                if n > 0:
                    continue
            elif cls_filter not in ("Tất cả", ""):
                try:
                    flt_cid = int(cls_filter.split("]")[0].lstrip("["))
                    if flt_cid not in data["classes"]:
                        continue
                except (ValueError, IndexError):
                    pass

            # Filter số lượng detection
            if ndet_min is not None and n < ndet_min:
                continue
            if ndet_max is not None and n > ndet_max:
                continue

            # Filter kích thước bbox (ít nhất 1 bbox thỏa mãn)
            dim_on = any(v is not None for v in (area_min, area_max,
                                                  w_min, w_max, h_min, h_max))
            if dim_on:
                boxes = data.get("boxes", [])
                if not boxes:
                    continue
                match = False
                for box in boxes:
                    bw, bh = box[5], box[6]
                    area = bw * bh
                    if area_min is not None and area < area_min: continue
                    if area_max is not None and area > area_max: continue
                    if w_min is not None and bw < w_min: continue
                    if w_max is not None and bw > w_max: continue
                    if h_min is not None and bh < h_min: continue
                    if h_max is not None and bh > h_max: continue
                    match = True
                    break
                if not match:
                    continue

            # Filter must-have / must-not labels
            if must_have_ids and not must_have_ids.issubset(detected_cls):
                continue
            if must_not_ids and must_not_ids.intersection(detected_cls):
                continue

            # Filter LPR
            if has_lpr_filter:
                with self._lpr_cache_lock:
                    _lpr_entry = self._lpr_cache.get(f)  # None = chưa chạy
                if lpr_filter == "Chưa nhận dạng":
                    if _lpr_entry is not None:
                        continue
                elif lpr_filter == "Có biển số":
                    if not (_lpr_entry is not None
                            and any(p for _, _, _, _, p in _lpr_entry)):
                        continue
                elif lpr_filter == "Không biển số":
                    if not (_lpr_entry is not None
                            and not any(p for _, _, _, _, p in _lpr_entry)):
                        continue

            result.append(f)
        return result

    # ============================================================= GRID PANEL ==

    def _build_grid_panel(self):
        """Filmstrip grid: pagination n_rows×n_cols, fill toàn bộ panel."""
        parent = self._grid_outer

        # ── Nav bar ────────────────────────────────────────────────────────
        self._grid_page_nav = GridPageNav(
            parent,
            on_first=lambda: self._go_grid_page_abs(0),
            on_prev=lambda: self._go_grid_page(-1),
            on_next=lambda: self._go_grid_page(+1),
            on_last=lambda: self._go_grid_page_abs(-1),
            on_direct=self._go_grid_page_direct,
        )
        self._grid_page_nav.pack(side=BOTTOM, fill=X)

        # ── Toolbar: Cột + Hàng ────────────────────────────────────────────
        gtb = Frame(parent, bg=CARD, padx=6, pady=2)
        gtb.pack(side=BOTTOM, fill=X)

        for label, var, lo, hi in [
            ("Cột:", self._grid_cols_var, 1, 10),
            ("Hàng:", self._grid_rows_var, 1, 10),
        ]:
            Label(gtb, text=label, bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
            spn = Spinbox(gtb, from_=lo, to=hi, textvariable=var,
                          width=2, bg="#16162a", fg=TEXT, insertbackground=TEXT,
                          buttonbackground=ACCENT2, relief="flat", font=F_MAIN,
                          command=self._on_grid_size_change)
            spn.bind("<Return>",   lambda e: self._on_grid_size_change())
            spn.bind("<FocusOut>", lambda e: self._on_grid_size_change())
            spn.pack(side=LEFT, padx=(2, 10))

        # ── Grid area (không scrollbar — pagination fill panel) ────────────
        self._grid_frame = Frame(parent, bg="#0d0d1e")
        self._grid_frame.pack(fill=BOTH, expand=True)
        self._grid_frame.bind("<Configure>", self._on_grid_frame_configure)

        self._grid_inner = Frame(self._grid_frame, bg="#0d0d1e")
        self._grid_inner.pack(fill=BOTH, expand=True)

    # ── Resize handler: reflow thumbnail size, KHÔNG tạo lại widget ────────
    def _on_grid_frame_configure(self, event):
        if self._grid_reflow_after:
            self.after_cancel(self._grid_reflow_after)
        self._grid_reflow_after = self.after(
            350, lambda: self._reflow_grid(event.width, event.height))

    def _reflow_grid(self, canvas_w: int, canvas_h: int):
        """Tính lại tw/th từ kích thước panel, re-render thumbnail không rebuild widget."""
        n_cols = max(1, self._grid_cols_var.get())
        n_rows = max(1, self._grid_rows_var.get())
        tw, th = self._calc_thumb_size(canvas_w, canvas_h, n_cols, n_rows)
        if tw == self._grid_thumb_w and th == self._grid_thumb_h:
            return
        self._grid_thumb_w, self._grid_thumb_h = tw, th
        self._grid_rendered_cache.clear()
        blank = self._make_blank_thumb(tw, th)
        for cell in self._grid_cells:
            cell["rendered"] = False
            try:
                if blank:
                    cell["img_lbl"].config(image=blank)
                    cell["img_lbl"]._blank_ref = blank
            except Exception:
                pass
        self._grid_render_idx = 0
        self._schedule_film_render()

    @staticmethod
    def _calc_thumb_size(cw: int, ch: int, n_cols: int, n_rows: int):
        tw = max(40, (cw - 4 * (n_cols + 1)) // n_cols)
        th = max(30, (ch - 4 * (n_rows + 1)) // n_rows)
        return tw, th

    def _on_grid_size_change(self):
        """Cols/rows thay đổi → rebuild trang hiện tại."""
        self._grid_rendered_cache.clear()
        self._schedule_grid_rebuild()

    def _schedule_grid_rebuild(self):
        if self._grid_rebuild_after:
            self.after_cancel(self._grid_rebuild_after)
        self._grid_rebuild_after = self.after(150, self._rebuild_grid)

    def _go_grid_page(self, delta: int):
        if not self.image_list:
            return
        n_cols   = max(1, self._grid_cols_var.get())
        n_rows   = max(1, self._grid_rows_var.get())
        per_page = n_cols * n_rows
        total    = len(self.image_list)
        max_page = max(0, (total - 1) // per_page)
        self._grid_page = max(0, min(max_page, self._grid_page + delta))
        self._rebuild_grid()

    def _go_grid_page_abs(self, page: int):
        """Nhảy tới trang đầu (0) hoặc trang cuối (-1)."""
        if not self.image_list:
            return
        n_cols   = max(1, self._grid_cols_var.get())
        n_rows   = max(1, self._grid_rows_var.get())
        per_page = n_cols * n_rows
        total    = len(self.image_list)
        max_page = max(0, (total - 1) // per_page)
        self._grid_page = 0 if page == 0 else max_page
        self._rebuild_grid()

    def _go_grid_page_direct(self):
        """Nhảy tới số trang nhập trong Entry (1-indexed, validate + clamp)."""
        if not self.image_list:
            return
        try:
            page = int(self._grid_page_nav.page_var.get()) - 1  # 1-indexed → 0-indexed
        except ValueError:
            self._grid_page_nav.page_var.set(str(self._grid_page + 1))
            return
        n_cols   = max(1, self._grid_cols_var.get())
        n_rows   = max(1, self._grid_rows_var.get())
        per_page = n_cols * n_rows
        total    = len(self.image_list)
        max_page = max(0, (total - 1) // per_page)
        new_page = max(0, min(max_page, page))
        if new_page == self._grid_page:
            self._grid_page_nav.page_var.set(str(new_page + 1))
            return
        self._grid_page = new_page
        self._rebuild_grid()

    def _rebuild_grid(self):
        if not hasattr(self, "_grid_inner"):
            return

        for w in self._grid_inner.winfo_children():
            w.destroy()
        self._grid_cells.clear()

        files    = self.image_list
        n_cols   = max(1, self._grid_cols_var.get())
        n_rows   = max(1, self._grid_rows_var.get())
        per_page = n_cols * n_rows
        total    = len(files)

        if not total:
            self._grid_page_nav.update(0, 0, 0)
            Label(self._grid_inner, text="Không có ảnh",
                  bg="#0d0d1e", fg=DIM, font=F_MAIN).grid(
                  row=0, column=0, pady=20)
            return

        max_page = max(0, (total - 1) // per_page)
        self._grid_page = max(0, min(max_page, self._grid_page))
        start = self._grid_page * per_page
        end   = min(start + per_page, total)
        self._grid_page_nav.update(self._grid_page, max_page, total)

        # Tính tw/th từ kích thước thực của frame
        fw = max(self._grid_frame.winfo_width(),  200)
        fh = max(self._grid_frame.winfo_height(), 200)
        tw, th = self._calc_thumb_size(fw, fh, n_cols, n_rows)
        if self._grid_thumb_w != tw or self._grid_thumb_h != th:
            self._grid_rendered_cache.clear()
        self._grid_thumb_w, self._grid_thumb_h = tw, th

        blank_img = self._make_blank_thumb(tw, th)

        for fi_off, fpath in enumerate(files[start:end]):
            row, col = divmod(fi_off, n_cols)
            is_cur   = (fpath == self.current_image_path)
            border   = ACCENT if is_cur else "#2a2a3e"

            cell = Frame(self._grid_inner, bg=border, padx=1, pady=1,
                         cursor="hand2")
            cell.grid(row=row, column=col, padx=2, pady=2, sticky="nsew")

            img_lbl = Label(cell, image=blank_img, bg="#1a1a2e", bd=0,
                            width=tw, height=th)
            img_lbl.pack(fill=BOTH, expand=True)

            det_data = self._det_cache.get(fpath)
            fname    = os.path.basename(fpath)
            n_suffix = (f" [{det_data['n']}]" if det_data is not None else "")
            if len(fname) > 18:
                fname = fname[:16] + "…"
            fn_lbl = Label(cell, text=fname + n_suffix, bg="#111130",
                           fg="#9090bb", font=("Consolas", 7), anchor=W, padx=2)
            fn_lbl.pack(fill=X)

            state = _path_review_state(fpath)
            if state == "correct":
                Label(cell, text="✔", bg="#1a3a1a", fg=SUCCESS,
                      font=("Segoe UI", 7)).pack(fill=X)
            elif state == "incorrect":
                Label(cell, text="✖", bg="#3a1a1a", fg="#e06060",
                      font=("Segoe UI", 7)).pack(fill=X)

            for widget in (cell, img_lbl, fn_lbl):
                widget.bind("<Button-1>", lambda e, p=fpath: self._grid_click(p))

            self._grid_cells.append({
                "path": fpath, "frame": cell, "img_lbl": img_lbl,
                "fn_lbl": fn_lbl, "rendered": False
            })

        for c in range(n_cols):
            self._grid_inner.columnconfigure(c, weight=1)
        for r in range(n_rows):
            self._grid_inner.rowconfigure(r, weight=1)

        self._grid_render_idx = 0
        self._schedule_film_render()

    def _make_blank_thumb(self, tw: int, th: int):
        if not _PIL_OK:
            return None
        blank = Image.new("RGB", (tw, th), "#1a1a2e")
        return ImageTk.PhotoImage(blank)

    def _schedule_film_render(self):
        BATCH = 10
        end = min(self._grid_render_idx + BATCH, len(self._grid_cells))
        for cell in self._grid_cells[self._grid_render_idx:end]:
            if not cell["rendered"]:
                pil = self._render_grid_thumb(cell["path"])
                if pil is not None:
                    try:
                        tk_img = ImageTk.PhotoImage(pil)
                        cell["img_lbl"].config(image=tk_img, width=0, height=0)
                        cell["img_lbl"]._tk_img = tk_img
                    except Exception:
                        pass
                cell["rendered"] = True
        self._grid_render_idx = end
        if end < len(self._grid_cells):
            self.after(40, self._schedule_film_render)

    def _render_grid_thumb(self, img_path: str):
        """Thumbnail với bbox overlay từ detect cache."""
        if not _PIL_OK:
            return None
        tw, th      = self._grid_thumb_w, self._grid_thumb_h
        in_cache    = img_path in self._det_cache
        lw          = max(1, self.v_line_width.get())
        conf_thresh = max(self.v_conf_thresh.get(), self.v_conf.get())
        cache_key   = (img_path, tw, th, in_cache, lw, conf_thresh)
        if cache_key in self._grid_rendered_cache:
            return self._grid_rendered_cache[cache_key]
        try:
            pil = Image.open(img_path).convert("RGB")
        except Exception:
            return None
        data = self._det_cache.get(img_path)
        if data and data["n"] > 0:
            from PIL import ImageDraw as _ID
            drw = _ID.Draw(pil)
            iw, ih = pil.size
            for box in data["boxes"]:
                if len(box) > 7 and float(box[7]) < conf_thresh:
                    continue
                cid, cx_n, cy_n, w_n, h_n = box[0], box[1], box[2], box[3], box[4]
                x1 = max(0, int((cx_n - w_n / 2) * iw))
                y1 = max(0, int((cy_n - h_n / 2) * ih))
                x2 = min(iw - 1, int((cx_n + w_n / 2) * iw))
                y2 = min(ih - 1, int((cy_n + h_n / 2) * ih))
                color = _THUMB_PALETTE[int(cid) % len(_THUMB_PALETTE)]
                drw.rectangle([x1, y1, x2, y2], outline=color, width=lw)
        pil.thumbnail((tw, th), Image.Resampling.LANCZOS)
        bg_img = Image.new("RGB", (tw, th), "#1a1a2e")
        ox = (tw - pil.width) // 2
        oy = (th - pil.height) // 2
        bg_img.paste(pil, (ox, oy))
        self._grid_rendered_cache[cache_key] = bg_img
        return bg_img

    def _grid_click(self, fpath: str):
        """Click thumbnail → điều hướng đến ảnh đó."""
        if fpath == self.current_image_path:
            return
        self._open_image(fpath)

    def _update_filmstrip(self):
        """Chuyển đúng trang chứa ảnh hiện tại; cập nhật highlight."""
        if not self.image_list or not hasattr(self, "_grid_inner"):
            return
        n_cols   = max(1, self._grid_cols_var.get())
        n_rows   = max(1, self._grid_rows_var.get())
        per_page = n_cols * n_rows
        if self.current_image_path in self.image_list:
            fi           = self.image_list.index(self.current_image_path)
            target_page  = fi // per_page
            if target_page != self._grid_page:
                self._grid_page = target_page
                self._rebuild_grid()
                return
        # Cùng trang — chỉ đổi border
        for cell in self._grid_cells:
            is_cur = (cell["path"] == self.current_image_path)
            try:
                cell["frame"].config(bg=ACCENT if is_cur else "#2a2a3e")
            except Exception:
                pass

    # =========================================================== DETECTION ==

    def _sync_slider_labels(self):
        self.lbl_conf_thresh_val.config(text=f"{self.v_conf_thresh.get():.2f}")
        self.lbl_conf.config(text=f"{self.v_conf.get():.2f}")
        self.lbl_iou.config(text=f"{self.v_iou.get():.2f}")

    def _on_conf_thresh_change(self, _=None):
        self.lbl_conf_thresh_val.config(text=f"{self.v_conf_thresh.get():.2f}")
        # conf_thresh là bộ lọc hiển thị — KHÔNG xóa cache, chỉ re-render từ cache với ngưỡng mới
        self._grid_rendered_cache.clear()
        if self.current_image_path and self.model:
            self._detect_and_display()

    def _on_slider_change(self, _=None):
        self.lbl_conf.config(text=f"{self.v_conf.get():.2f}")
        self.lbl_iou.config(text=f"{self.v_iou.get():.2f}")
        if not self.current_image_path:
            return
        with self._det_cache_lock:
            in_cache = self.current_image_path in self._det_cache
        if in_cache:
            # Ảnh đã có cache → filter conf từ cache, không re-detect
            self._grid_rendered_cache.clear()
            self._detect_and_display()
        else:
            # Không có cache → chạy detect với params mới
            self._detect_and_display()

    def _get_sel_classes(self):
        sel_idx = self.lb_classes.curselection()
        return [self.class_ids[i] for i in sel_idx] if sel_idx else None

    def _cache_single_result(self, img_path: str, results):
        """Ghi kết quả detect vào _det_cache và refresh grid cell tương ứng."""
        boxes_obj = results[0].boxes
        classes_count = {}
        box_list = []
        if boxes_obj is not None and len(boxes_obj):
            for box in boxes_obj:
                cid        = int(box.cls[0])
                conf_score = float(box.conf[0])
                classes_count[cid] = classes_count.get(cid, 0) + 1
                cx_n, cy_n, w_n, h_n = box.xywhn[0].tolist()
                w_px = float(box.xywh[0][2])
                h_px = float(box.xywh[0][3])
                box_list.append((cid, cx_n, cy_n, w_n, h_n, w_px, h_px, conf_score))
        with self._det_cache_lock:
            self._det_cache[img_path] = {
                "n": len(box_list), "classes": classes_count, "boxes": box_list
            }
        # Xóa thumbnail cache của ảnh này để render lại với bbox mới
        for key in list(self._grid_rendered_cache.keys()):
            if key[0] == img_path:
                del self._grid_rendered_cache[key]
        self._refresh_grid_cell(img_path)

    def _refresh_grid_cell(self, img_path: str):
        """Re-render thumbnail + label cho đúng 1 cell, không rebuild toàn grid."""
        if not hasattr(self, "_grid_cells"):
            return
        for cell in self._grid_cells:
            if cell["path"] != img_path:
                continue
            pil = self._render_grid_thumb(img_path)
            if pil is not None and _PIL_OK:
                try:
                    tk_img = ImageTk.PhotoImage(pil)
                    cell["img_lbl"].config(image=tk_img, width=0, height=0)
                    cell["img_lbl"]._tk_img = tk_img
                    cell["rendered"] = True
                except Exception:
                    pass
            det_data = self._det_cache.get(img_path)
            fname    = os.path.basename(img_path)
            if len(fname) > 22:
                fname = fname[:20] + "…"
            n_suffix = (f" [{det_data['n']}]" if det_data is not None else "")
            try:
                cell["fn_lbl"].config(text=fname + n_suffix)
            except Exception:
                pass
            break

    def _run_model(self, mdl, image_path, sel_cls,
                   conf: float = 0.25, iou: float = 0.45):
        return mdl.predict(
            source=image_path,
            classes=sel_cls,
            conf=conf,
            iou=iou,
            imgsz=640,
            agnostic_nms=True,
            verbose=False,
        )

    def _results_summary(self, results, model_names):
        boxes = results[0].boxes
        n_det = len(boxes) if boxes is not None else 0
        if n_det > 0:
            counts = {}
            for cls_id in boxes.cls.tolist():
                name = model_names[int(cls_id)]
                counts[name] = counts.get(name, 0) + 1
            summary = "  |  ".join(f"{n}: {c}" for n, c in counts.items())
            return n_det, summary
        return 0, ""

    def _on_plot_param_change(self):
        """Debounce 200 ms — tránh render liên tục khi kéo slider."""
        if self._plot_after:
            self.after_cancel(self._plot_after)
        self._plot_after = self.after(200, self._do_replot)

    def _do_replot(self):
        self._plot_after = None
        self._grid_rendered_cache.clear()
        if self._last_results1 is not None:
            try:
                pil1, ann1_bgr = self._annotated_to_pil(self._last_results1)
                self._last_annotated_bgr = ann1_bgr
                self._pil1_full = pil1
                self._render_display()
            except Exception:
                pass
        elif self.current_image_path and self.current_image_path in self._det_cache:
            # Đang hiển thị từ cache → vẽ lại với font/line mới
            try:
                pil1 = self._annotated_from_cache(self.current_image_path)
                ann1_bgr = cv2.cvtColor(np.array(pil1), cv2.COLOR_RGB2BGR)
                self._last_annotated_bgr = ann1_bgr
                self._pil1_full = pil1
                self._render_display()
            except Exception:
                pass
        self._schedule_grid_rebuild()

    # Màu cố định cho từng panel khi so sánh 2 model
    _PANEL1_COLOR = (0, 200, 255)    # cyan  — Model 1
    _PANEL2_COLOR = (240, 89, 34)    # orange ACCENT — Model 2

    def _annotated_to_pil(self, results, single_color=None):
        """Vẽ annotation bằng PIL để font_size hoạt động độc lập với line_width.
        single_color: tuple RGB — dùng màu cố định này cho mọi box (bỏ qua class).
        Dùng trong dual-panel mode để 2 panel có màu khác nhau rõ ràng."""
        from PIL import ImageFont, ImageDraw as _Draw

        lw = max(1, self.v_line_width.get())
        fs = max(6, self.v_font_size.get())

        orig_bgr = results[0].orig_img
        orig_rgb = cv2.cvtColor(orig_bgr, cv2.COLOR_BGR2RGB)
        pil_img  = Image.fromarray(orig_rgb)
        draw     = _Draw.Draw(pil_img)

        try:
            font = ImageFont.truetype("arial.ttf", fs)
        except Exception:
            try:
                font = ImageFont.load_default(size=fs)
            except Exception:
                font = ImageFont.load_default()

        # Màu theo class (single panel) hoặc màu cố định (dual panel)
        if single_color is None:
            try:
                from ultralytics.utils.plotting import colors as _yc
                def _color(cls_id):
                    c = _yc(int(cls_id), True)
                    return (int(c[2]), int(c[1]), int(c[0]))
            except Exception:
                _pal = [(0,200,255),(0,255,0),(255,100,0),(255,0,200),(200,200,0)]
                def _color(cls_id):
                    return _pal[int(cls_id) % len(_pal)]
        else:
            def _color(_):
                return single_color

        boxes = results[0].boxes
        names = getattr(results[0], "names", {}) or {}
        if not isinstance(names, dict):
            names = {}

        if boxes is not None and len(boxes):
            for box in boxes:
                x1, y1, x2, y2 = (int(v) for v in box.xyxy[0])
                cls_id   = int(box.cls[0])
                conf     = float(box.conf[0])
                cls_name = names.get(cls_id, str(cls_id))
                label    = f"{cls_name} {conf:.2f}"
                color    = _color(cls_id)

                draw.rectangle([x1, y1, x2, y2], outline=color, width=lw)

                try:
                    tb = draw.textbbox((0, 0), label, font=font)
                    tw, th = tb[2] - tb[0], tb[3] - tb[1]
                    ty = max(y1 - th - 4, 0)
                    draw.rectangle([x1, ty, x1 + tw + 6, ty + th + 4], fill=color)
                    draw.text((x1 + 3, ty + 2), label,
                              fill=_contrast_text(color), font=font)
                except Exception:
                    draw.text((x1, max(y1 - fs - 2, 0)), label,
                              fill=_contrast_text(color), font=font)

        ann_bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        return pil_img, ann_bgr

    def _annotated_combined_pil(self, results1, results2, model2):
        """Vẽ bbox từ 2 model lên cùng 1 ảnh: cyan (M1) + cam KZTEK (M2)."""
        from PIL import ImageFont, ImageDraw as _Draw

        lw = max(1, self.v_line_width.get())
        fs = max(6, self.v_font_size.get())

        orig_bgr = results1[0].orig_img
        orig_rgb = cv2.cvtColor(orig_bgr, cv2.COLOR_BGR2RGB)
        pil_img  = Image.fromarray(orig_rgb)
        draw     = _Draw.Draw(pil_img)

        try:
            font = ImageFont.truetype("arial.ttf", fs)
        except Exception:
            try:
                font = ImageFont.load_default(size=fs)
            except Exception:
                font = ImageFont.load_default()

        def _draw_boxes(boxes, names, color, prefix):
            if boxes is None or not len(boxes):
                return
            for box in boxes:
                x1, y1, x2, y2 = (int(v) for v in box.xyxy[0])
                cls_id = int(box.cls[0])
                conf   = float(box.conf[0])
                label  = f"{prefix}{names.get(cls_id, str(cls_id))} {conf:.2f}"
                draw.rectangle([x1, y1, x2, y2], outline=color, width=lw)
                try:
                    tb = draw.textbbox((0, 0), label, font=font)
                    tw, th = tb[2]-tb[0], tb[3]-tb[1]
                    ty = max(y1-th-4, 0)
                    draw.rectangle([x1, ty, x1+tw+6, ty+th+4], fill=color)
                    draw.text((x1+3, ty+2), label,
                               fill=_contrast_text(color), font=font)
                except Exception:
                    draw.text((x1, max(y1-fs-2, 0)), label, fill=color, font=font)

        _draw_boxes(results1[0].boxes,
                    getattr(self.model, "names", {}) or {},
                    self._PANEL1_COLOR, "M1:")
        _draw_boxes(results2[0].boxes,
                    getattr(model2, "names", {}) or {},
                    self._PANEL2_COLOR, "M2:")

        ann_bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        return pil_img, ann_bgr

    def _annotated_from_cache(self, img_path: str):
        """Vẽ annotated image từ _det_cache — nhất quán với grid thumbnail."""
        from PIL import ImageFont, ImageDraw as _Draw
        with self._det_cache_lock:
            data = self._det_cache.get(img_path)
        pil = Image.open(img_path).convert("RGB")
        try:
            from PIL import ImageOps
            pil = ImageOps.exif_transpose(pil)
        except Exception:
            pass
        if not data or data["n"] == 0:
            return pil
        conf_thresh = max(self.v_conf_thresh.get(), self.v_conf.get())
        visible_boxes = [b for b in data["boxes"]
                         if (len(b) > 7 and float(b[7]) >= conf_thresh)]
        if not visible_boxes:
            return pil
        lw = max(1, self.v_line_width.get())
        fs = max(6, self.v_font_size.get())
        iw, ih = pil.size
        draw = _Draw.Draw(pil)
        try:
            font = ImageFont.truetype("arial.ttf", fs)
        except Exception:
            try:
                font = ImageFont.load_default(size=fs)
            except Exception:
                font = ImageFont.load_default()
        try:
            from ultralytics.utils.plotting import colors as _yc
            def _color(cls_id):
                c = _yc(int(cls_id), True)
                return (int(c[2]), int(c[1]), int(c[0]))
        except Exception:
            _pal = [(0,200,255),(0,255,0),(255,100,0),(255,0,200),(200,200,0)]
            def _color(cls_id):
                return _pal[int(cls_id) % len(_pal)]
        names = {}
        if self.model:
            try:
                names = dict(self.model.names) or {}
            except Exception:
                pass
        for box_t in visible_boxes:
            cid        = int(box_t[0])
            cx_n, cy_n, w_n, h_n = box_t[1], box_t[2], box_t[3], box_t[4]
            conf_score = float(box_t[7]) if len(box_t) > 7 else 0.0
            x1 = max(0, int((cx_n - w_n / 2) * iw))
            y1 = max(0, int((cy_n - h_n / 2) * ih))
            x2 = min(iw - 1, int((cx_n + w_n / 2) * iw))
            y2 = min(ih - 1, int((cy_n + h_n / 2) * ih))
            cls_name = names.get(cid, str(cid))
            label    = f"{cls_name} {conf_score:.2f}"
            color    = _color(cid)
            draw.rectangle([x1, y1, x2, y2], outline=color, width=lw)
            try:
                tb = draw.textbbox((0, 0), label, font=font)
                tw2, th2 = tb[2] - tb[0], tb[3] - tb[1]
                ty = max(y1 - th2 - 4, 0)
                draw.rectangle([x1, ty, x1 + tw2 + 6, ty + th2 + 4], fill=color)
                draw.text((x1 + 3, ty + 2), label,
                          fill=_contrast_text(color), font=font)
            except Exception:
                draw.text((x1, max(y1 - fs - 2, 0)), label,
                          fill=_contrast_text(color), font=font)
        return pil

    def _resize_pil(self, pil_img, w, h):
        copy = pil_img.copy()
        copy.thumbnail((w - 10, h - 10), Image.Resampling.LANCZOS)
        return copy

    def _detect_and_display(self):
        """Chạy YOLO detect trên background thread — không block UI."""
        if not self.current_image_path or not self.model:
            return
        if not _PIL_OK or not _CV2_OK:
            self.lbl_result.config(
                text="Cần cài: pip install Pillow opencv-python", fg=ACCENT)
            return
        if self._detecting:
            self._det_pending = True  # re-detect sau khi xong
            return
        self._detecting   = True
        self._det_pending = False
        self.lbl_result.config(text="⏳ Đang nhận diện…", fg=DIM)

        img_path        = self.current_image_path  # capture trước khi user chuyển ảnh
        model1          = self.model
        model2          = self.model2
        sel_cls         = self._get_sel_classes()
        # Capture params trên main thread (Tkinter widget không thread-safe)
        conf_val = max(self.v_conf_thresh.get(), self.v_conf.get())
        iou_val  = self.v_iou.get()
        check_lpr   = self.v_check_lpr.get()
        lpr_urls    = ([v.get().strip() for v in self._lpr_url_vars
                        if v.get().strip()] if check_lpr else [])
        lpr_timeout = self._lpr_timeout_var.get() if check_lpr else 10
        lpr_fullimg = [v.get() for v in self._lpr_fullimg_vars] if check_lpr else []
        # Dùng cache nếu có (nhất quán với grid thumbnail), trừ dual-model mode
        with self._det_cache_lock:
            cached = self._det_cache.get(img_path) if model2 is None else None

        def _run():
            try:
                if cached is not None:
                    # ── Cache hit: vẽ từ cache, filter theo max(conf_thresh, conf) ──
                    pil1     = self._annotated_from_cache(img_path)
                    ann1_bgr = cv2.cvtColor(np.array(pil1), cv2.COLOR_RGB2BGR)
                    try:
                        from PIL import ImageOps
                        pil_orig = Image.open(img_path).convert("RGB")
                        pil_orig = ImageOps.exif_transpose(pil_orig)
                    except Exception:
                        pil_orig = None
                    # Tính n_det và summary chỉ với boxes vượt qua effective threshold
                    filtered_boxes = [b for b in cached["boxes"]
                                      if (len(b) > 7 and float(b[7]) >= conf_val)]
                    n_det = len(filtered_boxes)
                    filtered_classes = {}
                    for b in filtered_boxes:
                        cid = int(b[0])
                        filtered_classes[cid] = filtered_classes.get(cid, 0) + 1
                    _names = {}
                    try:
                        _names = dict(model1.names) or {}
                    except Exception:
                        pass
                    summary = "  |  ".join(
                        f"{_names.get(k, str(k))}: {v}"
                        for k, v in filtered_classes.items())
                    # ── LPR overlay (B2+B3) ────────────────────────────────
                    if check_lpr and lpr_urls and _REQ_OK and filtered_boxes:
                        with self._lpr_cache_lock:
                            _lpr_hit = self._lpr_cache.get(img_path)
                        if _lpr_hit is not None:
                            pil1 = self._lpr_draw_from_results(pil1, _lpr_hit)
                        else:
                            iw, ih = pil1.size
                            bwc = [(
                                max(0, int((b[1] - b[3] / 2) * iw)),
                                max(0, int((b[2] - b[4] / 2) * ih)),
                                min(iw - 1, int((b[1] + b[3] / 2) * iw)),
                                min(ih - 1, int((b[2] + b[4] / 2) * ih)),
                                int(b[0]),
                            ) for b in filtered_boxes]
                            pil1 = self._lpr_overlay_boxes(
                                pil1, pil_orig, bwc, lpr_urls, lpr_timeout,
                                _names, lpr_fullimg)
                            with self._lpr_cache_lock:
                                self._lpr_cache[img_path] = list(
                                    self._last_lpr_plates_result)
                        ann1_bgr = cv2.cvtColor(np.array(pil1), cv2.COLOR_RGB2BGR)
                    self.root.after(0, lambda: self._on_detect_done(
                        img_path, None, pil1, ann1_bgr, pil_orig,
                        n_det, summary, None, None, None, 0, ""))
                else:
                    # ── Không có cache: chạy model, lưu cache ──
                    results1 = self._run_model(model1, img_path, sel_cls, conf_val, iou_val)
                    n_det, summary = self._results_summary(results1, model1.names)
                    self._cache_single_result(img_path, results1)
                    pil1, ann1_bgr = self._annotated_to_pil(results1)
                    try:
                        from PIL import ImageOps
                        pil_orig = Image.open(img_path).convert("RGB")
                        pil_orig = ImageOps.exif_transpose(pil_orig)
                    except Exception:
                        pil_orig = None
                    # ── LPR overlay (B2+B3) ────────────────────────────────
                    if check_lpr and lpr_urls and _REQ_OK:
                        _boxes = results1[0].boxes
                        if _boxes is not None and len(_boxes):
                            with self._lpr_cache_lock:
                                _lpr_hit = self._lpr_cache.get(img_path)
                            if _lpr_hit is not None:
                                pil1 = self._lpr_draw_from_results(pil1, _lpr_hit)
                            else:
                                _cls_list = [int(c) for c in _boxes.cls.tolist()]
                                _bwc = [(int(v[0]), int(v[1]), int(v[2]), int(v[3]),
                                         _cls_list[i])
                                        for i, v in enumerate(_boxes.xyxy.tolist())]
                                _mn = {}
                                try:
                                    _mn = dict(model1.names) or {}
                                except Exception:
                                    pass
                                pil1 = self._lpr_overlay_boxes(
                                    pil1, pil_orig, _bwc, lpr_urls, lpr_timeout,
                                    _mn, lpr_fullimg)
                                with self._lpr_cache_lock:
                                    self._lpr_cache[img_path] = list(
                                        self._last_lpr_plates_result)
                            ann1_bgr = cv2.cvtColor(np.array(pil1),
                                                    cv2.COLOR_RGB2BGR)
                    if model2 is not None:
                        results2 = self._run_model(model2, img_path, sel_cls, conf_val, iou_val)
                        n_det2, summary2 = self._results_summary(results2, model2.names)
                        # Gộp 2 model lên 1 ảnh (cyan M1, cam M2)
                        pil1, ann1_bgr = self._annotated_combined_pil(
                            results1, results2, model2)
                        # Áp LPR overlay từ cache (đã tính ở bước model1 phía trên)
                        if check_lpr and lpr_urls and _REQ_OK:
                            with self._lpr_cache_lock:
                                _lpr_c2 = self._lpr_cache.get(img_path)
                            if _lpr_c2 is not None:
                                pil1 = self._lpr_draw_from_results(pil1, _lpr_c2)
                                ann1_bgr = cv2.cvtColor(np.array(pil1),
                                                        cv2.COLOR_RGB2BGR)
                        pil2 = None   # combined mode — không dùng side-by-side
                    else:
                        results2, pil2, n_det2, summary2 = None, None, 0, ""
                    self.root.after(0, lambda: self._on_detect_done(
                        img_path, results1, pil1, ann1_bgr, pil_orig, n_det, summary,
                        model2, results2, pil2, n_det2, summary2))
            except Exception as e:
                err = str(e)
                self.root.after(0, lambda: self._on_detect_error(err))

        threading.Thread(target=_run, daemon=True).start()

    def _on_detect_done(self, img_path, results1, pil1, ann1_bgr, pil_orig,
                         n_det, summary, model2, results2, pil2, n_det2, summary2):
        self._detecting = False
        pending = self._det_pending
        self._det_pending = False
        # Bỏ qua nếu user đã chuyển sang ảnh khác trong lúc detect
        if img_path != self.current_image_path:
            if pending:
                self._detect_and_display()
            return

        self._last_annotated_bgr = ann1_bgr
        self._last_results1      = results1

        if model2 is not None:
            # Combined mode — 1 ảnh, 2 màu bbox (cyan M1, cam M2)
            m1_name = os.path.basename(self.v_model_path.get())
            m2_name = os.path.basename(self.v_model2_path.get())
            self.lbl_panel1_title.config(
                text=(f"Model 1: {m1_name}  ({n_det} obj)"
                      f"    |    Model 2: {m2_name}  ({n_det2} obj)"))
            self.panel2_frame.pack_forget()
            self.lbl_panel2_title.config(text="")

            self._pil1_full  = pil1
            self._pil1_orig  = pil_orig
            self._last_n_det = n_det + n_det2
            self._render_display()

            txt = (f"Model1: {n_det} obj" + (f"  [{summary}]" if summary else "")
                   + f"    Model2: {n_det2} obj" + (f"  [{summary2}]" if summary2 else ""))
            self.lbl_result.config(text=txt, fg=SUCCESS if n_det or n_det2 else DIM)
        else:
            # Single panel
            self.panel2_frame.pack_forget()
            self.lbl_panel1_title.config(text="")

            self._pil1_full = pil1
            self._pil1_orig = pil_orig
            self._last_n_det = n_det
            self._render_display()

            if n_det > 0:
                self.lbl_result.config(
                    text=f"Phát hiện {n_det} đối tượng  —  {summary}", fg=SUCCESS)
            else:
                self.lbl_result.config(text="Không phát hiện đối tượng nào", fg=DIM)

        # Nếu slider thay đổi trong lúc detect → re-detect ngay với params mới
        if pending:
            self._detect_and_display()

    def _on_detect_error(self, err: str):
        self._detecting = False
        pending = self._det_pending
        self._det_pending = False
        self.lbl_result.config(text=f"Lỗi: {err}", fg=ACCENT)
        if pending:
            self._detect_and_display()

    # ============================================= LPR OVERLAY HELPERS ==

    def _lpr_parse_plate(self, raw) -> str:
        """Trích biển số từ JSON response của LPR server."""
        if isinstance(raw, list):
            raw = raw[0] if raw else {}
        if not isinstance(raw, dict):
            return str(raw)[:30] if raw else ""
        for rk in ("Results", "results"):
            sub = raw.get(rk)
            if isinstance(sub, list) and sub:
                item = sub[0]
                for pk in ("Plate", "plate", "PlateNumber", "plate_number"):
                    if item.get(pk):
                        return str(item[pk]).strip()
        for k in ("plate", "PlateNumber", "license_plate", "plateNumber", "text"):
            if raw.get(k):
                return str(raw[k]).strip()
        return ""

    def _lpr_call_crop(self, crop_pil, url: str, timeout: int) -> str:
        """Gửi ảnh crop lên LPR server, trả về biển số hoặc ''."""
        if not _REQ_OK or not _PIL_OK:
            return ""
        try:
            from io import BytesIO
            buf = BytesIO()
            img = crop_pil if crop_pil.mode == "RGB" else crop_pil.convert("RGB")
            img.save(buf, "JPEG", quality=90)
            data = buf.getvalue()
            resp = _requests.post(
                url,
                files={"upload": ("crop.jpg", data, "image/jpeg")},
                timeout=timeout)
            resp.raise_for_status()
            try:
                raw = resp.json()
            except Exception:
                return resp.text.strip()[:50]
            return self._lpr_parse_plate(raw)
        except Exception:
            return ""

    # ── Màu nền mỗi dòng LPR ──────────────────────────────────────────────
    # Màu prefix LPR1/2/3 — dùng làm text color trên nền tối
    _LPR_LINE_COLORS = [(80, 220, 100), (80, 160, 255), (255, 185, 60)]
    _LPR_BG          = (15, 15, 25, 210)   # nền tối bán trong suốt (RGBA)

    @staticmethod
    def _lpr_draw_lines(draw, font, x1: int, y1: int, x2: int, y2: int,
                        plates_tsv: str, iw: int, ih: int, fs: int):
        """Vẽ từng dòng kết quả LPR — nền tối, prefix màu riêng, diff màu vàng."""
        _COLORS = [(80, 220, 100), (80, 160, 255), (255, 185, 60)]
        _BG     = (15, 15, 25)
        _DIFF   = (255, 220, 0)    # vàng — dễ thấy trên nền tối
        _WHITE  = (255, 255, 255)

        raw = [p.upper() for p in plates_tsv.split("\t")] if plates_tsv else []
        ref = next((p for p in raw if p), "")
        multi = sum(1 for p in raw if p) > 1

        lines = []
        for i, p in enumerate(raw):
            if not p:
                continue
            prefix = f"LPR{i+1}: " if multi else ""
            lines.append((prefix, p, _COLORS[i % len(_COLORS)]))

        if not lines:
            return

        pad = 5
        line_gap = 2

        def _text_w(txt):
            try:
                return draw.textbbox((0, 0), txt, font=font)[2]
            except Exception:
                return len(txt) * 9

        def _text_h(txt):
            try:
                tb = draw.textbbox((0, 0), txt, font=font)
                return tb[3] - tb[1]
            except Exception:
                return fs

        # Tính max width để biết tx cần dịch vào bao nhiêu
        line_sizes = []
        for prefix, plate_text, pfx_color in lines:
            full  = prefix + plate_text
            tw    = _text_w(full)
            th    = _text_h(full)
            line_sizes.append((tw, th))

        max_tw   = max(tw for tw, _ in line_sizes) if line_sizes else 0
        row_h    = max(th for _, th in line_sizes) if line_sizes else fs
        total_h  = len(lines) * (row_h + pad * 2 + line_gap)

        # Vị trí Y: ưu tiên dưới bbox, nếu tràn thì đẩy lên trên
        ty = y2 + 3
        if ty + total_h > ih:
            ty = max(0, y1 - total_h - 3)

        # Vị trí X: căn theo x1 của bbox, dịch trái nếu tràn cạnh phải
        tx = min(x1, iw - max_tw - pad * 2 - 1)
        tx = max(0, tx)

        for (tw2, th2), (prefix, plate_text, pfx_color) in zip(line_sizes, lines):
            draw.rectangle([tx, ty, tx + tw2 + pad * 2, ty + th2 + pad * 2],
                           fill=_BG)
            cx, cy = tx + pad, ty + pad
            # Prefix màu riêng
            if prefix:
                draw.text((cx, cy), prefix, font=font, fill=pfx_color)
                cx += _text_w(prefix)
            # Từng ký tự: trắng nếu đúng, vàng nếu khác LPR1
            for pi, ch in enumerate(plate_text):
                ref_ch = ref[pi] if pi < len(ref) else None
                fill = _DIFF if (ref_ch is not None and ch != ref_ch) else _WHITE
                draw.text((cx, cy), ch, font=font, fill=fill)
                cx += _text_w(ch)
            ty += th2 + pad * 2 + line_gap

    def _lpr_draw_from_results(self, draw_pil, results: list):
        """Vẽ nhãn biển số từ results đã cache — không gọi API.
        results: [(x1,y1,x2,y2,plate), ...]
        """
        if not results or not _PIL_OK:
            return draw_pil
        from PIL import ImageDraw as _Draw, ImageFont
        iw, ih = draw_pil.size
        draw = _Draw.Draw(draw_pil)
        fs = max(1, int(self._lpr_font_size_var.get()))
        try:
            font = ImageFont.truetype("arial.ttf", fs)
        except Exception:
            try:
                font = ImageFont.load_default(size=fs)
            except Exception:
                font = ImageFont.load_default()
        self._last_lpr_plates_result = []
        for (x1, y1, x2, y2, plates_tsv) in results:
            self._last_lpr_plates_result.append((x1, y1, x2, y2, plates_tsv))
            if not plates_tsv:
                continue
            x1c = max(0, x1); y1c = max(0, y1)
            x2c = min(iw - 1, x2); y2c = min(ih - 1, y2)
            self._lpr_draw_lines(draw, font, x1c, y1c, x2c, y2c,
                                 plates_tsv, iw, ih, fs)
        return draw_pil

    def _lpr_batch_for_path(self, img_path: str, boxes: list,
                             urls, timeout: int,
                             use_full: list = None) -> list:
        """Gọi LPR song song tất cả URL cho từng bbox của 1 ảnh (dùng trong batch detect).

        boxes   : list[(cid, cx_n, cy_n, w_n, h_n, ...)] — format det_cache.
        urls    : str hoặc list[str].
        use_full: list[bool] tương ứng từng URL — True = gửi ảnh gốc, False = crop.
        Returns : [(x1,y1,x2,y2,plates_tsv), ...]  (rỗng nếu lỗi).
        """
        if isinstance(urls, str):
            urls = [urls] if urls else []
        if not _REQ_OK or not _PIL_OK or not boxes or not urls:
            return []
        use_full = list(use_full) if use_full else [False] * len(urls)
        while len(use_full) < len(urls):
            use_full.append(False)
        try:
            from PIL import Image as _PILImg
            pil = _PILImg.open(img_path).convert("RGB")
            iw, ih = pil.size
        except Exception:
            return []
        # Filter plate class
        names = {}
        try:
            if self.model:
                names = dict(self.model.names)
        except Exception:
            pass
        _PLATE_KW = {"plate", "lp", "bsx", "bien", "license", "bienso"}
        plate_cids = {
            cid for cid, name in names.items()
            if any(kw in str(name).lower() for kw in _PLATE_KW)
        }
        if plate_cids:
            to_proc = [b for b in boxes if int(b[0]) in plate_cids]
            if not to_proc:
                return []   # model có plate class nhưng ảnh không detect ra → không gọi LPR
        else:
            to_proc = boxes
        import concurrent.futures as _cf
        results = []
        for b in to_proc:
            cx_n, cy_n, w_n, h_n = float(b[1]), float(b[2]), float(b[3]), float(b[4])
            x1 = max(0, int((cx_n - w_n / 2) * iw))
            y1 = max(0, int((cy_n - h_n / 2) * ih))
            x2 = min(iw - 1, int((cx_n + w_n / 2) * iw))
            y2 = min(ih - 1, int((cy_n + h_n / 2) * ih))
            if x2 - x1 < 8 or y2 - y1 < 8:
                continue
            crop = pil.crop((x1, y1, x2, y2))
            plates = [""] * len(urls)
            def _call(idx, u):
                img = pil if use_full[idx] else crop
                return self._lpr_call_crop(img, u, timeout)
            if len(urls) == 1:
                plates[0] = _call(0, urls[0])
            else:
                with _cf.ThreadPoolExecutor(max_workers=len(urls)) as ex:
                    futs = {ex.submit(_call, i, u): i
                            for i, u in enumerate(urls)}
                    for fut in _cf.as_completed(futs):
                        plates[futs[fut]] = fut.result() or ""
            plates_tsv = "\t".join(p.upper() for p in plates)
            results.append((x1, y1, x2, y2, plates_tsv))
        return results

    def _lpr_overlay_boxes_vid(self, draw_pil, source_pil, boxes_with_cls,
                               urls, timeout, model_names, use_full, font_size):
        """Wrapper thread-safe cho video — nhận font_size trực tiếp, không đọc Tkinter var."""
        import contextlib
        class _FakeIntVar:
            def get(self): return font_size
        old = self._lpr_font_size_var
        self._lpr_font_size_var = _FakeIntVar()
        try:
            return self._lpr_overlay_boxes(draw_pil, source_pil, boxes_with_cls,
                                            urls, timeout, model_names, use_full)
        finally:
            self._lpr_font_size_var = old

    def _lpr_overlay_boxes(self, draw_pil, source_pil, boxes_with_cls: list,
                            urls, timeout: int, model_names: dict = None,
                            use_full: list = None):
        """Crop bbox biển số → gọi song song tất cả LPR URL → vẽ kết quả lên ảnh.

        draw_pil       : PIL Image đã annotated — vẽ text lên đây.
        source_pil     : PIL Image gốc để crop — None → dùng draw_pil.
        boxes_with_cls : list[(x1,y1,x2,y2,cid)] tọa độ pixel + class id.
        urls           : str hoặc list[str] — LPR server URL(s).
        model_names    : dict {cid: name} từ model.names để lọc plate class.
        use_full       : list[bool] tương ứng từng URL — True = gửi ảnh gốc.
        """
        if isinstance(urls, str):
            urls = [urls] if urls else []
        if not _PIL_OK:
            return draw_pil
        use_full = list(use_full) if use_full else [False] * len(urls)
        while len(use_full) < len(urls):
            use_full.append(False)
        from PIL import ImageDraw as _Draw, ImageFont

        # ── Lọc plate class nếu model có class biển số ──────────────────
        _PLATE_KW = {"plate", "lp", "bsx", "bien", "license", "bienso"}
        names = model_names or {}
        plate_cids = {
            cid for cid, name in names.items()
            if any(kw in str(name).lower() for kw in _PLATE_KW)
        }
        if plate_cids:
            to_process = [b for b in boxes_with_cls if b[4] in plate_cids]
            if not to_process:
                # Model có plate class nhưng ảnh không detect ra biển số → không gọi LPR
                self._last_lpr_plates_result = []
                return draw_pil
        else:
            to_process = boxes_with_cls      # model không có plate class → dùng tất cả bbox

        self._last_lpr_plates_result = []
        if not to_process:
            return draw_pil

        iw, ih = draw_pil.size
        draw = _Draw.Draw(draw_pil)
        fs = max(12, int(self._lpr_font_size_var.get()))
        try:
            font = ImageFont.truetype("arial.ttf", fs)
        except Exception:
            try:
                font = ImageFont.load_default(size=fs)
            except Exception:
                font = ImageFont.load_default()

        src = (source_pil if (source_pil is not None
                               and source_pil.size == draw_pil.size)
               else draw_pil)

        import concurrent.futures as _cf
        for (x1, y1, x2, y2, _cid) in to_process:
            x1 = max(0, x1); y1 = max(0, y1)
            x2 = min(iw - 1, x2); y2 = min(ih - 1, y2)
            if x2 - x1 < 8 or y2 - y1 < 8:
                continue
            crop = src.crop((x1, y1, x2, y2))
            # Gọi song song tất cả LPR URL — mỗi URL dùng crop hoặc ảnh gốc
            plates = [""] * len(urls)
            def _call(idx, u):
                img = src if use_full[idx] else crop
                return self._lpr_call_crop(img, u, timeout)
            if len(urls) == 1:
                plates[0] = _call(0, urls[0])
            else:
                with _cf.ThreadPoolExecutor(max_workers=len(urls)) as ex:
                    futs = {ex.submit(_call, i, u): i
                            for i, u in enumerate(urls)}
                    for fut in _cf.as_completed(futs):
                        plates[futs[fut]] = fut.result() or ""

            plates_tsv = "\t".join(p.upper() for p in plates)
            self._last_lpr_plates_result.append((x1, y1, x2, y2, plates_tsv))
            if not any(plates):
                continue
            self._lpr_draw_lines(draw, font, x1, y1, x2, y2,
                                 plates_tsv, iw, ih, fs)
        return draw_pil

    # ================================================ WRONG FOLDER SAVE ==

    def _update_wrong_path(self):
        """Ghép 5 ô thành v_wrong_folder."""
        parts = [sv.get().strip() for sv in self._v_wf_segs]
        parts = [p for p in parts if p]
        if not parts:
            self.v_wrong_folder.set("")
            return
        # Dùng string join (không dùng os.path.join) để tránh lỗi drive letter Windows
        path = parts[0].rstrip("/\\")
        for p in parts[1:]:
            path = path + "/" + p.strip("/\\")
        self.v_wrong_folder.set(path)

    def _browse_wrong_folder(self):
        cur = self.v_wrong_folder.get().strip()
        init = (cur if cur and os.path.isdir(cur)
                else os.path.dirname(cur) if cur else None)
        folder = filedialog.askdirectory(
            title="Chọn thư mục lưu ảnh sai",
            initialdir=init,
            parent=self.root)
        if not folder:
            return
        # Chia path thành 5 ô: 4 phần cuối → ô 2-5, phần còn lại → ô 1
        folder = folder.replace("\\", "/")
        raw = folder.split("/")
        # Xử lý drive letter Windows (e.g. "K:" → giữ nguyên trong raw[0])
        if len(raw) >= 5:
            s1 = "/".join(raw[:-4])
            segs = [s1] + raw[-4:]
        else:
            segs = raw + [""] * (5 - len(raw))
        for i, (sv, cb) in enumerate(zip(self._v_wf_segs, self._wf_combos)):
            val = segs[i] if i < len(segs) else ""
            sv.set(val)
            if val:
                _push_history(f"h.yolo.wf.s{i+1}", val)
                cb["values"] = _get_history(f"h.yolo.wf.s{i+1}")

    def _open_wrong_folder(self):
        p = self.v_wrong_folder.get().strip()
        if p and os.path.isdir(p):
            os.startfile(p)

    def _save_wrong_image(self):
        """Copy ảnh + label hiện tại vào folder lưu ảnh sai đã cấu hình."""
        path = self.current_image_path
        if not path or not os.path.isfile(path):
            messagebox.showwarning("Chưa có ảnh",
                                   "Vui lòng chọn ảnh trước.", parent=self.root)
            return
        dest_dir = self.v_wrong_folder.get().strip()
        if not dest_dir:
            messagebox.showwarning("Chưa chọn thư mục",
                                   "Vui lòng chọn thư mục lưu ảnh sai (ô phía trên).",
                                   parent=self.root)
            return
        try:
            os.makedirs(dest_dir, exist_ok=True)
            base     = os.path.splitext(os.path.basename(path))[0]
            dest_img = os.path.join(dest_dir, os.path.basename(path))
            dest_lbl = os.path.join(dest_dir, f"{base}.txt")

            shutil.copy2(path, dest_img)

            # 1) Ưu tiên: ghi label từ det_cache (boxes đã detect)
            with self._det_cache_lock:
                det = self._det_cache.get(path)
            if det is not None:
                conf_thresh = max(self.v_conf_thresh.get(), self.v_conf.get())
                with open(dest_lbl, "w", encoding="utf-8") as f:
                    for box_t in det.get("boxes", []):
                        if len(box_t) > 7 and float(box_t[7]) < conf_thresh:
                            continue
                        cid, cx, cy, bw, bh = (box_t[0], box_t[1],
                                                box_t[2], box_t[3], box_t[4])
                        f.write(f"{int(cid)} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")
            # 2) Fallback: kết quả detect trực tiếp (_last_results1)
            elif self._last_results1 is not None:
                boxes = self._last_results1[0].boxes
                with open(dest_lbl, "w", encoding="utf-8") as f:
                    if boxes is not None and len(boxes):
                        for box in boxes:
                            cid = int(box.cls[0])
                            cx, cy, bw, bh = box.xywhn[0].tolist()
                            f.write(f"{cid} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")
            # 3) Fallback cuối: copy file .txt gốc nếu tồn tại
            else:
                src_lbl = os.path.splitext(path)[0] + ".txt"
                if os.path.isfile(src_lbl):
                    shutil.copy2(src_lbl, dest_lbl)

            # Tự động đánh dấu sai
            self._review_state[path] = "incorrect"
            _CFG["yolo.review_states"] = self._review_state
            _cfg_save()
            iid = self._path_to_iid.get(path)
            if iid:
                try:
                    if self.tree_images.exists(iid):
                        icon = _REVIEW_ICON["incorrect"]
                        old_text = self.tree_images.item(iid, "text")
                        bare = old_text[2:] if len(old_text) > 2 else old_text
                        self.tree_images.item(iid,
                                              text=f"{icon} {bare}",
                                              tags=("incorrect",))
                except Exception:
                    pass
            self._update_filter_counts()

            self.lbl_mark_state.config(
                text=f"✗💾 {os.path.basename(path)}", fg="#ffaa55")
            self.after(3000, lambda: self.lbl_mark_state.config(text=""))
            lbl_note = " + label" if os.path.isfile(dest_lbl) else ""
            self.v_status.set(f"✗💾 Lưu ảnh sai{lbl_note} → {dest_dir}")
        except Exception as e:
            messagebox.showerror("Lỗi lưu ảnh", str(e), parent=self.root)

    def _save_wrong_page(self):
        """Copy toàn bộ ảnh trang grid hiện tại + label vào wrong_folder."""
        if not self._grid_cells:
            messagebox.showwarning("Chưa có ảnh",
                                   "Trang hiện tại không có ảnh.", parent=self.root)
            return
        dest_dir = self.v_wrong_folder.get().strip()
        if not dest_dir:
            messagebox.showwarning("Chưa chọn thư mục",
                                   "Vui lòng chọn thư mục lưu ảnh sai (ô phía trên).",
                                   parent=self.root)
            return

        paths = [c["path"] for c in self._grid_cells if c.get("path")]
        if not paths:
            return

        conf_thresh = max(self.v_conf_thresh.get(), self.v_conf.get())
        try:
            os.makedirs(dest_dir, exist_ok=True)
        except Exception as e:
            messagebox.showerror("Lỗi tạo thư mục", str(e), parent=self.root)
            return

        saved = 0
        errors = 0
        for p in paths:
            if not os.path.isfile(p):
                continue
            try:
                base     = os.path.splitext(os.path.basename(p))[0]
                dest_img = os.path.join(dest_dir, os.path.basename(p))
                dest_lbl = os.path.join(dest_dir, f"{base}.txt")

                shutil.copy2(p, dest_img)

                # Ghi label — ưu tiên det_cache → file .txt gốc
                with self._det_cache_lock:
                    det = self._det_cache.get(p)
                if det is not None:
                    with open(dest_lbl, "w", encoding="utf-8") as f:
                        for box_t in det.get("boxes", []):
                            if len(box_t) > 7 and float(box_t[7]) < conf_thresh:
                                continue
                            cid, cx, cy, bw, bh = (box_t[0], box_t[1],
                                                    box_t[2], box_t[3], box_t[4])
                            f.write(f"{int(cid)} {cx:.6f} {cy:.6f}"
                                    f" {bw:.6f} {bh:.6f}\n")
                else:
                    src_lbl = os.path.splitext(p)[0] + ".txt"
                    if os.path.isfile(src_lbl):
                        shutil.copy2(src_lbl, dest_lbl)

                # Tự động đánh dấu sai
                self._review_state[p] = "incorrect"
                iid = self._path_to_iid.get(p)
                if iid:
                    try:
                        if self.tree_images.exists(iid):
                            icon = _REVIEW_ICON["incorrect"]
                            old_text = self.tree_images.item(iid, "text")
                            bare = old_text[2:] if len(old_text) > 2 else old_text
                            self.tree_images.item(iid,
                                                  text=f"{icon} {bare}",
                                                  tags=("incorrect",))
                    except Exception:
                        pass
                saved += 1
            except Exception:
                errors += 1

        if saved:
            _CFG["yolo.review_states"] = self._review_state
            _cfg_save()
            self._update_filter_counts()

        msg = f"✗💾 {saved}/{len(paths)} ảnh → {dest_dir}"
        if errors:
            msg += f" ({errors} lỗi)"
        self.lbl_mark_state.config(text=f"✗💾 {saved} ảnh sai", fg="#ffaa55")
        self.after(3000, lambda: self.lbl_mark_state.config(text=""))
        self.v_status.set(msg)

    # ============================================ LPR ERROR SAVE + GT ==

    @staticmethod
    def _extract_plate_from_filename(fname: str) -> str:
        """Trích biển số từ tên file dạng sub_<biển số>[_...].
        VD: sub_29A12345_001 → '29A12345'
        """
        import re
        m = re.match(r'^sub_([A-Za-z0-9]+)', fname, re.IGNORECASE)
        return m.group(1).upper() if m else ""

    @staticmethod
    def _update_gt(gt_path: str, filename: str, plate: str):
        """Thêm hoặc cập nhật dòng 'filename\\tplate' trong gt.txt."""
        lines = []
        updated = False
        if os.path.isfile(gt_path):
            with open(gt_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.rstrip("\n")
                    if not line:
                        continue
                    parts = line.split("\t", 1)
                    if parts[0] == filename:
                        lines.append(f"{filename}\t{plate}")
                        updated = True
                    else:
                        lines.append(line)
        if not updated:
            lines.append(f"{filename}\t{plate}")
        with open(gt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    def _save_lpr_error_image(self):
        """Lưu ảnh lỗi kèm crop biển số + GT.

        1. Ảnh full (annotated nếu đã detect, else bản gốc) → wrong_folder/
        2. Crops từng bbox biển số → wrong_folder/crops/
        3. GT: wrong_folder/gt.txt  format: filename\\tplate
           Plate GT ưu tiên: tên file sub_<plate> → kết quả LPR
        """
        path = self.current_image_path
        if not path or not os.path.isfile(path):
            messagebox.showwarning("Chưa có ảnh",
                                   "Vui lòng chọn ảnh trước.", parent=self.root)
            return
        dest_dir = self.v_wrong_folder.get().strip()
        if not dest_dir:
            messagebox.showwarning("Chưa chọn thư mục",
                                   "Vui lòng chọn thư mục lưu ảnh sai (ô phía trên).",
                                   parent=self.root)
            return

        fname   = os.path.basename(path)
        base    = os.path.splitext(fname)[0]
        lpr_res = list(self._last_lpr_plates_result)  # snapshot

        # Plate GT: tên file → LPR (lấy plate đầu tiên có giá trị từ tab-separated)
        plate_gt = self._extract_plate_from_filename(base)
        if not plate_gt:
            plate_gt = next(
                (p for _, _, _, _, tsv in lpr_res
                 for p in tsv.split("\t") if p),
                ""
            )

        try:
            os.makedirs(dest_dir, exist_ok=True)

            # ── 1. Lưu ảnh full ──────────────────────────────────────────
            dest_full = os.path.join(dest_dir, fname)
            pil_full  = getattr(self, "_pil1_full", None)
            if pil_full is not None:
                pil_full.save(dest_full, quality=95)
            else:
                shutil.copy2(path, dest_full)

            # ── 2. Lưu crops bbox biển số ─────────────────────────────────
            n_crops  = 0
            pil_src  = getattr(self, "_pil1_orig", None)
            if pil_src is None:
                try:
                    from PIL import ImageOps
                    pil_src = Image.open(path).convert("RGB")
                    pil_src = ImageOps.exif_transpose(pil_src)
                except Exception:
                    pil_src = pil_full

            crop_gt_entries = []   # [(crop_fname, plate_str), ...]
            if pil_src is not None and lpr_res:
                crops_dir = os.path.join(dest_dir, "crops")
                os.makedirs(crops_dir, exist_ok=True)
                iw, ih = pil_src.size
                for i, (x1, y1, x2, y2, plates_tsv) in enumerate(lpr_res):
                    x1 = max(0, x1); y1 = max(0, y1)
                    x2 = min(iw - 1, x2); y2 = min(ih - 1, y2)
                    if x2 - x1 < 4 or y2 - y1 < 4:
                        continue
                    crop_img  = pil_src.crop((x1, y1, x2, y2))
                    crop_fname = f"{base}_crop{i:02d}.jpg"
                    crop_img.save(os.path.join(crops_dir, crop_fname), quality=95)
                    n_crops += 1
                    # GT cho crop: lấy plate đầu tiên có giá trị (ưu tiên LPR1)
                    crop_plate = plate_gt or next(
                        (p for p in plates_tsv.split("\t") if p), "")
                    if crop_plate:
                        crop_gt_entries.append((crop_fname, crop_plate))

            # ── 3. GT ─────────────────────────────────────────────────────
            gt_path = os.path.join(dest_dir, "gt.txt")
            if plate_gt:
                self._update_gt(gt_path, fname, plate_gt)
            # GT cho từng crop
            crops_gt_path = os.path.join(dest_dir, "crops", "gt.txt")
            for crop_fname, crop_plate in crop_gt_entries:
                self._update_gt(crops_gt_path, crop_fname, crop_plate)

            # Feedback
            gt_note = f"  GT={plate_gt}" if plate_gt else "  GT=—"
            crop_gt_note = f"+{len(crop_gt_entries)}crop" if crop_gt_entries else ""
            msg = f"📋 {fname}  crop={n_crops}{gt_note}{crop_gt_note}"
            self.lbl_mark_state.config(text=msg[:56], fg="#4cdf80")
            self.after(3000, lambda: self.lbl_mark_state.config(text=""))
            self.v_status.set(f"📋 Lưu lỗi+GT → {dest_dir}  {gt_note.strip()}")

        except Exception as e:
            messagebox.showerror("Lỗi lưu lỗi+GT", str(e), parent=self.root)

    def _open_gt_folder(self):
        p = self.v_wrong_folder.get().strip()
        if p and os.path.isdir(p):
            os.startfile(p)
        elif p:
            messagebox.showwarning("Thư mục không tồn tại",
                                   f"Chưa có thư mục:\n{p}", parent=self.root)
        else:
            messagebox.showwarning("Chưa chọn thư mục",
                                   "Vui lòng chọn thư mục lưu ảnh sai trước.",
                                   parent=self.root)

    # ======================================================= SAVE RESULT ==

    def _save_result(self):
        if self._last_annotated_bgr is None:
            messagebox.showwarning("Chưa có kết quả",
                                   "Vui lòng chạy detection trước.", parent=self.root)
            return
        if not _CV2_OK:
            messagebox.showerror("Thiếu thư viện",
                                  "pip install opencv-python", parent=self.root)
            return

        save_dir = filedialog.askdirectory(
            title="Chọn thư mục lưu kết quả", parent=self.root)
        if not save_dir:
            return

        base = os.path.splitext(os.path.basename(self.current_image_path))[0]
        img_out = os.path.join(save_dir, f"{base}_detected.jpg")
        cv2.imwrite(img_out, self._last_annotated_bgr)

        txt_out = None
        if self.model and self.current_image_path:
            try:
                sel_cls  = self._get_sel_classes()
                conf_val = max(self.v_conf_thresh.get(), self.v_conf.get())
                iou_val  = self.v_iou.get()
                results = self._run_model(self.model, self.current_image_path, sel_cls,
                                          conf_val, iou_val)
                boxes = results[0].boxes
                txt_out = os.path.join(save_dir, f"{base}_detected.txt")
                with open(txt_out, "w", encoding="utf-8") as f:
                    if boxes is not None and len(boxes):
                        for box in boxes:
                            cls_id = int(box.cls[0])
                            cx, cy, bw, bh = box.xywhn[0].tolist()
                            f.write(f"{cls_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")
            except Exception as e:
                messagebox.showerror("Lỗi lưu nhãn", str(e), parent=self.root)

        msg = f"Ảnh: {img_out}"
        if txt_out:
            msg += f"\nNhãn: {txt_out}"
        messagebox.showinfo("Đã lưu", msg, parent=self.root)

    # ========================================================== MAP CALC ==

    def _start_map_calc(self):
        if not self.model:
            messagebox.showwarning("Chưa có model",
                                   "Vui lòng chọn model trước.", parent=self.root)
            return
        if not _YOLO_OK:
            messagebox.showerror("Thiếu thư viện",
                                  "pip install ultralytics", parent=self.root)
            return

        folder = filedialog.askdirectory(
            title="Chọn thư mục chứa ảnh + nhãn .txt (YOLO format)",
            parent=self.root)
        if not folder:
            return

        if self.v_subfolder.get():
            img_files = sorted([
                os.path.join(root, f)
                for root, _, fnames in os.walk(folder)
                for f in fnames
                if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS
            ])
        else:
            img_files = sorted([
                os.path.join(folder, f)
                for f in os.listdir(folder)
                if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS
            ])
        if not img_files:
            messagebox.showinfo("Thông báo",
                                "Không tìm thấy ảnh trong thư mục!", parent=self.root)
            return

        popup = Toplevel(self.root)
        popup.title("Tính mAP@50")
        popup.configure(bg=BG)
        popup.geometry("680x480")

        Label(popup, text="Đang tính mAP@50 ...",
              font=F_BOLD, bg=BG, fg=TEXT).pack(pady=(10, 4))

        pb = ttk.Progressbar(popup, mode="determinate", maximum=len(img_files))
        pb.pack(fill=X, padx=16, pady=(0, 6))

        self.v_map_progress = StringVar(value="0 / 0")
        Label(popup, textvariable=self.v_map_progress,
              font=F_MONO, bg=BG, fg=DIM).pack()

        txt_frame = Frame(popup, bg=BG)
        txt_frame.pack(fill=BOTH, expand=True, padx=8, pady=8)
        sb_txt = Scrollbar(txt_frame, orient=VERTICAL)
        sb_txt.pack(side=RIGHT, fill=Y)
        result_text = Text(txt_frame, bg="#0d0d1a", fg=TEXT,
                           font=F_MONO, relief="flat", bd=0,
                           yscrollcommand=sb_txt.set, state=DISABLED)
        result_text.pack(fill=BOTH, expand=True)
        sb_txt.config(command=result_text.yview)

        def append(line):
            result_text.config(state=NORMAL)
            result_text.insert(END, line + "\n")
            result_text.see(END)
            result_text.config(state=DISABLED)

        conf_val = max(self.v_conf_thresh.get(), self.v_conf.get())
        iou_val  = self.v_iou.get()

        def run():
            iou_thresh = 0.5

            tp_total = 0
            fp_total = 0
            fn_total = 0
            per_class_tp = {}
            per_class_fp = {}
            per_class_fn = {}

            processed = 0
            skipped = 0

            for i, img_path in enumerate(img_files):
                base = os.path.splitext(img_path)[0]
                lbl_path = base + ".txt"

                self.root.after(0, lambda v=i: pb.config(value=v))
                self.root.after(0, lambda v=i+1, t=len(img_files):
                                self.v_map_progress.set(f"{v} / {t}"))

                if not os.path.isfile(lbl_path):
                    skipped += 1
                    continue

                try:
                    gt_boxes = []
                    with open(lbl_path, "r", encoding="utf-8") as f:
                        for line in f:
                            parts = line.strip().split()
                            if len(parts) == 5:
                                cls_id = int(parts[0])
                                cx, cy, bw, bh = map(float, parts[1:])
                                gt_boxes.append((cls_id, cx, cy, bw, bh))

                    results = self.model.predict(
                        source=img_path,
                        conf=conf_val,
                        iou=iou_val,
                        imgsz=640,
                        agnostic_nms=True,
                        verbose=False,
                    )
                    pred_boxes = []
                    boxes_res = results[0].boxes
                    if boxes_res is not None:
                        for box in boxes_res:
                            cls_id = int(box.cls[0])
                            xywhn = box.xywhn[0].tolist()
                            pred_boxes.append((cls_id, *xywhn))

                    matched_gt = set()
                    matched_pred = set()

                    for pi, pb_box in enumerate(pred_boxes):
                        p_cls = pb_box[0]
                        p_cx, p_cy, p_bw, p_bh = pb_box[1:]
                        best_iou = 0.0
                        best_gi = -1
                        for gi, gb_box in enumerate(gt_boxes):
                            if gi in matched_gt:
                                continue
                            g_cls = gb_box[0]
                            if g_cls != p_cls:
                                continue
                            g_cx, g_cy, g_bw, g_bh = gb_box[1:]
                            iou_v = _iou_xywhn(p_cx, p_cy, p_bw, p_bh,
                                               g_cx, g_cy, g_bw, g_bh)
                            if iou_v > best_iou:
                                best_iou = iou_v
                                best_gi = gi
                        if best_iou >= iou_thresh and best_gi >= 0:
                            matched_gt.add(best_gi)
                            matched_pred.add(pi)
                            tp_total += 1
                            per_class_tp[p_cls] = per_class_tp.get(p_cls, 0) + 1
                        else:
                            fp_total += 1
                            per_class_fp[p_cls] = per_class_fp.get(p_cls, 0) + 1

                    for gi, gb_box in enumerate(gt_boxes):
                        if gi not in matched_gt:
                            g_cls = gb_box[0]
                            fn_total += 1
                            per_class_fn[g_cls] = per_class_fn.get(g_cls, 0) + 1

                    processed += 1
                except Exception as ex:
                    self.root.after(0, lambda m=str(ex): append(f"  Lỗi: {m}"))

            precision = tp_total / (tp_total + fp_total) if (tp_total + fp_total) > 0 else 0.0
            recall = tp_total / (tp_total + fn_total) if (tp_total + fn_total) > 0 else 0.0
            f1 = (2 * precision * recall / (precision + recall)
                  if (precision + recall) > 0 else 0.0)
            map50 = precision * recall

            lines = [
                "=" * 52,
                f"Kết quả mAP@50 (IoU >= 0.5)",
                f"Thư mục: {folder}",
                f"Tổng ảnh: {len(img_files)}  |  Có nhãn: {processed}  |  Bỏ qua: {skipped}",
                "-" * 52,
                f"TP={tp_total}  FP={fp_total}  FN={fn_total}",
                f"Precision : {precision:.4f}",
                f"Recall    : {recall:.4f}",
                f"F1-Score  : {f1:.4f}",
                f"mAP@50    : {map50:.4f}",
                "-" * 52,
                "Chi tiết theo class:",
            ]
            all_cls = set(list(per_class_tp.keys())
                          + list(per_class_fp.keys())
                          + list(per_class_fn.keys()))
            for cls_id in sorted(all_cls):
                cname = self.model.names.get(cls_id, str(cls_id))
                tp_c = per_class_tp.get(cls_id, 0)
                fp_c = per_class_fp.get(cls_id, 0)
                fn_c = per_class_fn.get(cls_id, 0)
                p_c = tp_c / (tp_c + fp_c) if (tp_c + fp_c) > 0 else 0.0
                r_c = tp_c / (tp_c + fn_c) if (tp_c + fn_c) > 0 else 0.0
                lines.append(
                    f"  [{cls_id}] {cname:<20}  P={p_c:.3f}  R={r_c:.3f}"
                    f"  TP={tp_c} FP={fp_c} FN={fn_c}")
            lines.append("=" * 52)

            self.root.after(0, lambda: pb.config(value=len(img_files)))
            for ln in lines:
                self.root.after(0, lambda l=ln: append(l))

        threading.Thread(target=run, daemon=True).start()

    # ====================================================== VALIDATE TRUE/ ==

    def _validate_true_folder(self):
        if not self.model:
            messagebox.showwarning("Chưa có model",
                                   "Vui lòng chọn model trước.", parent=self.root)
            return
        if not _YOLO_OK:
            messagebox.showerror("Thiếu thư viện",
                                  "pip install ultralytics", parent=self.root)
            return

        # Xác định thư mục true/
        base = self._base_folder
        if not base:
            # Thử lấy từ ô path
            p = self.v_check_folder.get().strip()
            if os.path.isfile(p):
                base = os.path.dirname(p)
            elif os.path.isdir(p):
                base = p

        true_dir = os.path.join(base, "true") if base else None
        if not true_dir or not os.path.isdir(true_dir):
            # Fallback: hỏi người dùng chọn thư mục true/
            true_dir = filedialog.askdirectory(
                title="Chọn thư mục true/ (ảnh đã đánh dấu đúng)",
                parent=self.root)
            if not true_dir:
                return

        img_files = sorted([
            os.path.join(true_dir, f) for f in os.listdir(true_dir)
            if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS
        ])
        if not img_files:
            messagebox.showinfo("Thông báo",
                                f"Không tìm thấy ảnh trong:\n{true_dir}",
                                parent=self.root)
            return

        # ── Tạo cửa sổ kết quả ──
        popup = Toplevel(self.root)
        popup.title(f"Validate Model — {os.path.basename(true_dir)}")
        popup.configure(bg=BG)
        popup.geometry("820x620")
        popup.resizable(True, True)

        # Header
        Label(popup, text=f"🔍 Validate: {true_dir}",
              font=F_BOLD, bg=BG, fg=TEXT, anchor=W).pack(fill=X, padx=10, pady=(8, 2))

        pb = ttk.Progressbar(popup, mode="determinate", maximum=len(img_files))
        pb.pack(fill=X, padx=10, pady=(0, 2))
        v_prog = StringVar(value=f"0 / {len(img_files)}")
        Label(popup, textvariable=v_prog, font=F_MONO, bg=BG, fg=DIM).pack()

        # Summary frame
        sum_frame = Frame(popup, bg=CARD, padx=10, pady=6)
        sum_frame.pack(fill=X, padx=10, pady=(4, 2))
        lbl_sum = Label(sum_frame, text="Đang xử lý...",
                        font=F_MONO, bg=CARD, fg=TEXT, justify=LEFT, anchor=W)
        lbl_sum.pack(fill=X)

        # Assessment frame (hiện sau khi có kết quả)
        assess_frame = Frame(popup, bg="#0d0d1a", padx=10, pady=6)
        assess_frame.pack(fill=X, padx=10, pady=(0, 4))
        lbl_verdict = Label(assess_frame, text="",
                            font=F_BOLD, bg="#0d0d1a", fg=TEXT, justify=LEFT, anchor=W)
        lbl_verdict.pack(fill=X)
        lbl_advice = Label(assess_frame, text="",
                           font=F_MAIN, bg="#0d0d1a", fg=DIM, justify=LEFT, anchor=W,
                           wraplength=780)
        lbl_advice.pack(fill=X)

        # Notebook: per-class table | per-image list | glossary
        nb = ttk.Notebook(popup)
        nb.pack(fill=BOTH, expand=True, padx=10, pady=(4, 8))

        # Tab 1 — Per-class
        tab_cls = Frame(nb, bg=BG)
        nb.add(tab_cls, text="Theo Class")

        cls_style = ttk.Style()
        cls_style.configure("Val.Treeview",
                            background="#0d0d1a", foreground=TEXT,
                            fieldbackground="#0d0d1a", rowheight=22, font=F_MONO)
        cls_style.configure("Val.Treeview.Heading", background=CARD, foreground=TEXT)
        cls_style.map("Val.Treeview", background=[("selected", ACCENT2)])

        cls_cols = ("class", "tp", "fp", "fn", "precision", "recall", "f1")
        cls_tree = ttk.Treeview(tab_cls, columns=cls_cols, show="headings",
                                 style="Val.Treeview")
        for col, hd, w in [
            ("class",     "Class",     160),
            ("tp",        "TP",         50),
            ("fp",        "FP",         50),
            ("fn",        "FN",         50),
            ("precision", "Precision",  90),
            ("recall",    "Recall",     80),
            ("f1",        "F1",         70),
        ]:
            cls_tree.heading(col, text=hd)
            cls_tree.column(col, width=w, anchor=CENTER if col != "class" else W)
        sb_cls = Scrollbar(tab_cls, orient=VERTICAL, command=cls_tree.yview)
        cls_tree.configure(yscrollcommand=sb_cls.set)
        sb_cls.pack(side=RIGHT, fill=Y)
        cls_tree.pack(fill=BOTH, expand=True)
        cls_tree.tag_configure("good",   foreground="#4caf50")
        cls_tree.tag_configure("medium", foreground="#ffcc00")
        cls_tree.tag_configure("bad",    foreground=ACCENT)

        # Tab 2 — Per-image
        tab_img = Frame(nb, bg=BG)
        nb.add(tab_img, text="Theo Ảnh")

        img_cols = ("name", "gt", "pred", "tp", "fp", "fn", "status")
        img_tree = ttk.Treeview(tab_img, columns=img_cols, show="headings",
                                 style="Val.Treeview")
        for col, hd, w in [
            ("name",   "Tên ảnh",  200),
            ("gt",     "GT",        40),
            ("pred",   "Pred",      40),
            ("tp",     "TP",        40),
            ("fp",     "FP",        40),
            ("fn",     "FN",        40),
            ("status", "Trạng thái",100),
        ]:
            img_tree.heading(col, text=hd)
            img_tree.column(col, width=w, anchor=CENTER if col != "name" else W)
        sb_img_v = Scrollbar(tab_img, orient=VERTICAL, command=img_tree.yview)
        sb_img_h = Scrollbar(tab_img, orient=HORIZONTAL, command=img_tree.xview)
        img_tree.configure(yscrollcommand=sb_img_v.set, xscrollcommand=sb_img_h.set)
        sb_img_v.pack(side=RIGHT, fill=Y)
        sb_img_h.pack(side=BOTTOM, fill=X)
        img_tree.pack(fill=BOTH, expand=True)
        img_tree.tag_configure("perfect", foreground="#4caf50")
        img_tree.tag_configure("partial", foreground="#ffcc00")
        img_tree.tag_configure("bad",     foreground=ACCENT)
        img_tree.tag_configure("nolabel", foreground=DIM)

        # Tab 3 — Thuật ngữ
        tab_term = Frame(nb, bg=BG)
        nb.add(tab_term, text="Thuật ngữ")

        term_data = [
            ("TP  —  True Positive", "#4caf50",
             "Model phát hiện ĐÚNG một object: đúng class VÀ bbox chồng lấp ≥ 50% (IoU ≥ 0.5).",
             "Càng cao càng tốt."),
            ("FP  —  False Positive", ACCENT,
             "Model phát hiện THỪA: báo có object nhưng thực tế không có "
             "(hoặc detect sai class, hoặc trùng lặp).",
             "Càng thấp càng tốt.  Khắc phục: tăng Conf Threshold."),
            ("FN  —  False Negative", "#ff9800",
             "Model BỎ SÓT: có object trong label nhưng không detect được.",
             "Càng thấp càng tốt.  Khắc phục: giảm Conf Threshold hoặc thêm dữ liệu train."),
            ("GT  —  Ground Truth", "#90caf9",
             "Số bbox chuẩn được ghi trong file label .txt — dùng làm chuẩn để so sánh.",
             "Chuẩn tham chiếu, không đánh giá cao thấp."),
            ("Pred  —  Prediction", "#90caf9",
             "Số bbox model dự đoán ra trong ảnh.",
             "Lý tưởng: Pred ≈ GT.  Pred >> GT → nhiều FP.  Pred << GT → nhiều FN."),
            ("Precision", "#ce93d8",
             "= TP / (TP + FP)\n"
             "Tỷ lệ detect ĐÚNG trong tổng số lần model phát hiện.\n"
             "Ví dụ: Precision = 0.97  →  97% dự đoán của model là chính xác.",
             "≥ 0.90 là tốt."),
            ("Recall", "#ce93d8",
             "= TP / (TP + FN)\n"
             "Tỷ lệ tìm thấy trong tổng số object THỰC TẾ có trong ảnh.\n"
             "Ví dụ: Recall = 0.78  →  model tìm thấy 78%, bỏ sót 22%.",
             "≥ 0.80 là tốt."),
            ("F1-Score", "#ce93d8",
             "= 2 × Precision × Recall / (Precision + Recall)\n"
             "Chỉ số TỔNG HỢP cân bằng giữa Precision và Recall.\n"
             "F1 = 1.0 là hoàn hảo.  F1 = 0 là không detect được gì.",
             "≥ 0.85 là tốt.  Dùng F1 khi P và R lệch nhau."),
            ("IoU  —  Intersection over Union", "#80cbc4",
             "Độ chồng lấp giữa bbox dự đoán và bbox chuẩn.\n"
             "IoU = Diện tích phần giao / Diện tích phần hợp  (0 → 1).\n"
             "Công cụ này dùng ngưỡng IoU = 0.5 để xác định TP hay FP.",
             "0.5 là ngưỡng tiêu chuẩn (mAP@50).  0.75 là tiêu chuẩn nghiêm."),
        ]

        sb_term = Scrollbar(tab_term, orient=VERTICAL)
        sb_term.pack(side=RIGHT, fill=Y)
        term_txt = Text(tab_term, bg="#0d0d1a", fg=TEXT,
                        font=("Segoe UI", 10), relief="flat", bd=0,
                        wrap=WORD, padx=14, pady=8, state=NORMAL,
                        yscrollcommand=sb_term.set, cursor="arrow")
        term_txt.pack(fill=BOTH, expand=True)
        sb_term.config(command=term_txt.yview)

        # Cấu hình tag màu
        term_txt.tag_configure("term",    font=("Segoe UI", 11, "bold"), spacing1=10)
        term_txt.tag_configure("body",    font=("Segoe UI", 10),         lmargin1=20, lmargin2=20)
        term_txt.tag_configure("good",    font=("Segoe UI", 9, "italic"), lmargin1=20,
                                foreground="#aaaacc", spacing3=8)
        term_txt.tag_configure("divider", foreground="#333355", spacing1=2, spacing3=2)

        for term_name, term_color, meaning, good_when in term_data:
            term_txt.tag_configure(f"t_{term_name}", foreground=term_color)
            term_txt.insert(END, f"▌ {term_name}\n", ("term", f"t_{term_name}"))
            term_txt.insert(END, f"{meaning}\n", "body")
            term_txt.insert(END, f"  → Tốt khi: {good_when}\n", "good")
            term_txt.insert(END, "─" * 90 + "\n", "divider")

        term_txt.config(state=DISABLED)

        def _term_scroll(e):
            term_txt.yview_scroll(int(-1*(e.delta/120)), "units")
        term_txt.bind("<MouseWheel>", _term_scroll)

        # ── Capture params trên main thread trước khi spawn thread ──
        conf_val = max(self.v_conf_thresh.get(), self.v_conf.get())
        iou_val  = self.v_iou.get()

        # ── Background thread ──
        def run():
            iou_thresh = 0.5

            per_class_tp = {}; per_class_fp = {}; per_class_fn = {}
            img_results = []
            img_detail = {}
            tp_total = fp_total = fn_total = 0
            processed = skipped = 0

            for i, img_path in enumerate(img_files):
                self.root.after(0, lambda v=i+1: (
                    pb.config(value=v),
                    v_prog.set(f"{v} / {len(img_files)}"),
                ))

                base_name = os.path.splitext(os.path.basename(img_path))[0]
                lbl_path = os.path.join(os.path.dirname(img_path), base_name + ".txt")

                if not os.path.isfile(lbl_path):
                    img_results.append((img_path, None, None, None, None, None))
                    skipped += 1
                    continue

                try:
                    gt_boxes = []
                    with open(lbl_path, "r", encoding="utf-8") as f:
                        for line in f:
                            parts = line.strip().split()
                            if len(parts) == 5:
                                cid = int(parts[0])
                                cx, cy, bw, bh = map(float, parts[1:])
                                gt_boxes.append((cid, cx, cy, bw, bh))

                    results = self.model.predict(
                        source=img_path, conf=conf_val, iou=iou_val,
                        imgsz=640, agnostic_nms=True, verbose=False,
                    )
                    pred_boxes = []
                    boxes_res = results[0].boxes
                    if boxes_res is not None:
                        for box in boxes_res:
                            cid = int(box.cls[0])
                            xywhn = box.xywhn[0].tolist()
                            pred_boxes.append((cid, *xywhn))

                    matched_gt = set()
                    tp_img = fp_img = fn_img = 0
                    tp_pred_idx = set()

                    for pi, pb_box in enumerate(pred_boxes):
                        p_cls = pb_box[0]
                        p_cx, p_cy, p_bw, p_bh = pb_box[1:]
                        best_iou = 0.0; best_gi = -1
                        for gi, gb_box in enumerate(gt_boxes):
                            if gi in matched_gt or gb_box[0] != p_cls:
                                continue
                            iou_v = _iou_xywhn(p_cx, p_cy, p_bw, p_bh,
                                               gb_box[1], gb_box[2], gb_box[3], gb_box[4])
                            if iou_v > best_iou:
                                best_iou = iou_v; best_gi = gi
                        if best_iou >= iou_thresh and best_gi >= 0:
                            matched_gt.add(best_gi)
                            tp_pred_idx.add(pi)
                            tp_img += 1
                            per_class_tp[p_cls] = per_class_tp.get(p_cls, 0) + 1
                        else:
                            fp_img += 1
                            per_class_fp[p_cls] = per_class_fp.get(p_cls, 0) + 1

                    for gi, gb_box in enumerate(gt_boxes):
                        if gi not in matched_gt:
                            g_cls = gb_box[0]
                            fn_img += 1
                            per_class_fn[g_cls] = per_class_fn.get(g_cls, 0) + 1

                    img_detail[img_path] = {
                        "gt": list(gt_boxes),
                        "pred": list(pred_boxes),
                        "tp_pred": set(tp_pred_idx),
                        "matched_gt": set(matched_gt),
                    }
                    tp_total += tp_img; fp_total += fp_img; fn_total += fn_img
                    img_results.append((img_path, len(gt_boxes), len(pred_boxes),
                                        tp_img, fp_img, fn_img))
                    processed += 1

                except Exception as ex:
                    img_results.append((img_path, None, None, None, None, str(ex)))

            # ── Cập nhật UI từ main thread ──
            def _update_ui():
                pb.config(value=len(img_files))

                # Summary
                prec = tp_total / (tp_total + fp_total) if (tp_total + fp_total) > 0 else 0.0
                rec  = tp_total / (tp_total + fn_total) if (tp_total + fn_total) > 0 else 0.0
                f1   = (2*prec*rec / (prec+rec)) if (prec+rec) > 0 else 0.0
                lbl_sum.config(
                    text=(f"Thư mục: {true_dir}\n"
                          f"Tổng ảnh: {len(img_files)}  |  Có label: {processed}  |  Bỏ qua: {skipped}\n"
                          f"TP={tp_total}  FP={fp_total}  FN={fn_total}"
                          f"    Precision={prec:.4f}  Recall={rec:.4f}  F1={f1:.4f}")
                )

                # Đánh giá tổng thể
                if f1 >= 0.90:
                    verdict_text = "★★★★★  XUẤT SẮC"
                    verdict_color = "#4caf50"
                elif f1 >= 0.80:
                    verdict_text = "★★★★  TỐT — Model đáp ứng yêu cầu sử dụng"
                    verdict_color = "#8bc34a"
                elif f1 >= 0.65:
                    verdict_text = "★★★  KHÁ — Cần cải thiện thêm"
                    verdict_color = "#ffcc00"
                elif f1 >= 0.50:
                    verdict_text = "★★  TRUNG BÌNH — Chưa ổn định"
                    verdict_color = "#ff9800"
                else:
                    verdict_text = "★  YẾU — Cần train lại hoặc bổ sung dữ liệu"
                    verdict_color = ACCENT

                advice_lines = []
                if prec < 0.85:
                    advice_lines.append(
                        f"• Precision={prec:.3f} thấp → model detect nhầm nhiều (FP cao) "
                        "→ Tăng Conf Threshold hoặc lọc thêm dữ liệu nhiễu khi train.")
                if rec < 0.80:
                    advice_lines.append(
                        f"• Recall={rec:.3f} thấp → model bỏ sót object (FN cao) "
                        "→ Giảm Conf Threshold, hoặc thêm ảnh train đa dạng hơn.")

                # Cảnh báo class yếu
                all_cls_check = set(list(per_class_tp) + list(per_class_fp) + list(per_class_fn))
                weak_classes = []
                for cid in sorted(all_cls_check):
                    tp_c = per_class_tp.get(cid, 0)
                    fp_c = per_class_fp.get(cid, 0)
                    fn_c = per_class_fn.get(cid, 0)
                    p_c = tp_c / (tp_c + fp_c) if (tp_c + fp_c) > 0 else 0.0
                    r_c = tp_c / (tp_c + fn_c) if (tp_c + fn_c) > 0 else 0.0
                    f1_c = (2*p_c*r_c / (p_c+r_c)) if (p_c+r_c) > 0 else 0.0
                    cname = self.model.names.get(cid, str(cid))
                    if f1_c < 0.5:
                        weak_classes.append(f"[{cid}]{cname}(F1={f1_c:.2f})")
                if weak_classes:
                    advice_lines.append(
                        f"• Class yếu cần bổ sung dữ liệu: {', '.join(weak_classes)}")

                if not advice_lines:
                    advice_lines.append("Không có điểm yếu đáng kể. Model hoạt động ổn định.")

                lbl_verdict.config(text=f"Đánh giá: {verdict_text}  "
                                        f"(F1={f1:.4f}  P={prec:.4f}  R={rec:.4f})",
                                   fg=verdict_color)
                lbl_advice.config(text="\n".join(advice_lines))

                # Per-class table
                all_cls = set(list(per_class_tp) + list(per_class_fp) + list(per_class_fn))
                for cid in sorted(all_cls):
                    cname = self.model.names.get(cid, str(cid))
                    tp_c = per_class_tp.get(cid, 0)
                    fp_c = per_class_fp.get(cid, 0)
                    fn_c = per_class_fn.get(cid, 0)
                    p_c = tp_c / (tp_c + fp_c) if (tp_c + fp_c) > 0 else 0.0
                    r_c = tp_c / (tp_c + fn_c) if (tp_c + fn_c) > 0 else 0.0
                    f1_c = (2*p_c*r_c / (p_c+r_c)) if (p_c+r_c) > 0 else 0.0
                    tag = "good" if f1_c >= 0.8 else ("medium" if f1_c >= 0.5 else "bad")
                    cls_tree.insert("", END, values=(
                        f"[{cid}] {cname}", tp_c, fp_c, fn_c,
                        f"{p_c:.3f}", f"{r_c:.3f}", f"{f1_c:.3f}",
                    ), tags=(tag,))

                # Per-image table (sắp xếp: ảnh tệ nhất lên đầu)
                def sort_key(r):
                    if r[3] is None:  return (3, 0)
                    fp_i, fn_i = r[4] or 0, r[5] or 0
                    return (0 if (fp_i + fn_i) == 0 else 1 if (fp_i + fn_i) <= 2 else 2,
                            -(fp_i + fn_i))
                img_results.sort(key=sort_key)

                for row in img_results:
                    img_path, n_gt, n_pred, tp_i, fp_i, fn_i = row
                    fname = os.path.basename(img_path)
                    if n_gt is None and isinstance(fn_i, str):
                        img_tree.insert("", END,
                            values=(fname, "?", "?", "?", "?", "?", f"Lỗi: {fn_i}"),
                            tags=("bad",))
                    elif n_gt is None:
                        img_tree.insert("", END,
                            values=(fname, "-", "-", "-", "-", "-", "Không có label"),
                            tags=("nolabel",))
                    else:
                        if fp_i + fn_i == 0:
                            status, tag = "✓ Hoàn hảo", "perfect"
                        elif fp_i + fn_i <= 2:
                            status, tag = f"△ FP={fp_i} FN={fn_i}", "partial"
                        else:
                            status, tag = f"✗ FP={fp_i} FN={fn_i}", "bad"
                        img_tree.insert("", END,
                            values=(fname, n_gt, n_pred, tp_i, fp_i, fn_i, status),
                            tags=(tag,))

                # ── Click row → xem ảnh với bbox màu TP/FP/FN ──
                fname_to_path = {os.path.basename(p): p for p in img_detail}

                def _on_row_select(e, _tree=img_tree, _ftp=fname_to_path,
                                   _detail=img_detail, _pop=popup):
                    sel = _tree.selection()
                    if not sel:
                        return
                    vals = _tree.item(sel[0], "values")
                    if not vals:
                        return
                    ipath = _ftp.get(vals[0])
                    if not ipath or ipath not in _detail:
                        return
                    _show_img_detail(ipath, _detail[ipath], _pop)

                def _show_img_detail(ipath, detail, parent_win):
                    if not _PIL_OK:
                        messagebox.showerror("Lỗi", "Cần cài Pillow để xem ảnh",
                                             parent=parent_win)
                        return
                    try:
                        pil_src = Image.open(ipath).convert("RGB")
                    except Exception as ex:
                        messagebox.showerror("Lỗi ảnh", str(ex), parent=parent_win)
                        return

                    W, H = pil_src.size
                    pil_ann = pil_src.copy()
                    drw = ImageDraw.Draw(pil_ann)
                    mnames = self.model.names if self.model else {}
                    lw = max(2, int(min(W, H) / 250))

                    def _box_px(cx, cy, bw, bh):
                        return (max(0, int((cx-bw/2)*W)), max(0, int((cy-bh/2)*H)),
                                min(W-1, int((cx+bw/2)*W)), min(H-1, int((cy+bh/2)*H)))

                    def _label(x, y, text, color):
                        try:
                            drw.text((x, y), text, fill=color,
                                     stroke_width=1, stroke_fill="#000000")
                        except TypeError:
                            drw.text((x, y), text, fill=color)

                    # FN: missed GT — vàng, vẽ trước (lớp dưới)
                    for gi, gb in enumerate(detail["gt"]):
                        if gi not in detail["matched_gt"]:
                            cid, cx, cy, bw, bh = gb
                            x1, y1, x2, y2 = _box_px(cx, cy, bw, bh)
                            drw.rectangle([x1, y1, x2, y2], outline="#ffcc00", width=lw)
                            _label(x1+2, y1+2,
                                   f"FN [{cid}]{mnames.get(cid,str(cid))}", "#ffcc00")

                    # Pred boxes: TP=xanh, FP=cam — vẽ sau (lớp trên)
                    for pi, pb in enumerate(detail["pred"]):
                        cid, cx, cy, bw, bh = pb
                        x1, y1, x2, y2 = _box_px(cx, cy, bw, bh)
                        cname = mnames.get(cid, str(cid))
                        if pi in detail["tp_pred"]:
                            color, lbl = "#4caf50", f"TP [{cid}]{cname}"
                        else:
                            color, lbl = "#F05922", f"FP [{cid}]{cname}"
                        drw.rectangle([x1+lw, y1+lw, x2-lw, y2-lw],
                                      outline=color, width=lw)
                        ty = min(H-14, y2-lw-14)
                        _label(x1+lw+2, ty, lbl, color)

                    # Cửa sổ hiển thị
                    dwin = Toplevel(parent_win)
                    dwin.title(f"Chi tiết: {os.path.basename(ipath)}")
                    dwin.configure(bg=BG)
                    dwin.resizable(True, True)
                    dwin.protocol("WM_DELETE_WINDOW", dwin.destroy)

                    # Legend + stats
                    leg = Frame(dwin, bg=CARD, padx=8, pady=4)
                    leg.pack(fill=X)
                    n_tp = len(detail["tp_pred"])
                    n_fp = len(detail["pred"]) - n_tp
                    n_fn = len(detail["gt"]) - len(detail["matched_gt"])
                    for txt, col in [("■ TP (Đúng)", "#4caf50"),
                                     ("■ FP (Thừa)", "#F05922"),
                                     ("■ FN (Bỏ sót)", "#ffcc00")]:
                        Label(leg, text=txt, fg=col, bg=CARD,
                              font=F_MONO).pack(side=LEFT, padx=10)
                    Label(leg,
                          text=f"GT={len(detail['gt'])}  TP={n_tp}  FP={n_fp}  FN={n_fn}",
                          fg=DIM, bg=CARD, font=F_MONO).pack(side=RIGHT, padx=10)

                    # Scale ảnh vừa màn hình
                    sw2 = dwin.winfo_screenwidth()
                    sh2 = dwin.winfo_screenheight()
                    img_disp = pil_ann.copy()
                    img_disp.thumbnail((int(sw2*0.85), int(sh2*0.80)), Image.LANCZOS)

                    frm = Frame(dwin, bg="#0d0d1a")
                    frm.pack(fill=BOTH, expand=True)
                    det_canvas = Canvas(frm, bg="#0d0d1a", highlightthickness=0)
                    sb_dv = Scrollbar(frm, orient=VERTICAL, command=det_canvas.yview)
                    sb_dh = Scrollbar(dwin, orient=HORIZONTAL, command=det_canvas.xview)
                    det_canvas.configure(yscrollcommand=sb_dv.set,
                                         xscrollcommand=sb_dh.set)
                    sb_dh.pack(side=BOTTOM, fill=X)
                    sb_dv.pack(side=RIGHT, fill=Y)
                    det_canvas.pack(fill=BOTH, expand=True)

                    def _render_det(_c=det_canvas, _img=img_disp):
                        _tk = ImageTk.PhotoImage(_img)
                        _c.create_image(0, 0, anchor=NW, image=_tk)
                        _c.configure(scrollregion=(0, 0, _img.width, _img.height))
                        _c._tk_img = _tk

                    dwin.after(30, _render_det)
                    dwin.geometry(f"{min(img_disp.width+20, int(sw2*0.85))}"
                                  f"x{min(img_disp.height+60, int(sh2*0.80))}")
                    dwin.lift()
                    dwin.focus_set()
                    det_canvas.bind("<MouseWheel>",
                                    lambda e, c=det_canvas:
                                    c.yview_scroll(int(-1*(e.delta/120)), "units"))
                    dwin.bind("<Escape>", lambda _: dwin.destroy())

                img_tree.bind("<<TreeviewSelect>>", _on_row_select)

            self.root.after(0, _update_ui)

        threading.Thread(target=run, daemon=True).start()

    # ====================================================== VIDEO DETECTION ==

    def _open_video_detect(self):
        """Dialog chọn nguồn video, sau đó mở cửa sổ detect liên tục."""
        if not self.model:
            messagebox.showwarning("Chưa có model",
                                   "Vui lòng chọn model trước.", parent=self.root)
            return
        if not _CV2_OK or not _PIL_OK:
            messagebox.showerror("Thiếu thư viện",
                                  "pip install opencv-python Pillow", parent=self.root)
            return

        dlg = Toplevel(self.root)
        dlg.title("Chọn nguồn video")
        dlg.configure(bg=BG)
        dlg.resizable(False, False)
        dlg.protocol("WM_DELETE_WINDOW", dlg.destroy)
        dlg.grab_set()

        Label(dlg, text="Nhận dạng YOLO liên tục từ video",
              font=F_BOLD, bg=BG, fg=TEXT).pack(padx=24, pady=(16, 4))

        # File video row
        file_frame = Frame(dlg, bg=BG)
        file_frame.pack(fill=X, padx=16, pady=(8, 2))
        Label(file_frame, text="File video:", bg=BG, fg=DIM, font=F_MAIN,
              width=14, anchor=W).pack(side=LEFT)
        v_vidpath = StringVar()
        hist_vals = _get_history("h.yolo.video_path")
        combo_vid = ttk.Combobox(file_frame, textvariable=v_vidpath,
                                  font=F_MAIN, width=36)
        combo_vid["values"] = hist_vals
        if hist_vals:
            combo_vid.set(hist_vals[0])
        combo_vid.pack(side=LEFT, fill=X, expand=True, padx=(0, 4))
        _bind_history("h.yolo.video_path", combo_vid)

        def _pick_video():
            p = filedialog.askopenfilename(
                title="Chọn file video",
                filetypes=[("Video", "*.mp4 *.avi *.mkv *.mov *.wmv *.m4v *.ts *.flv"),
                           ("All files", "*.*")],
                parent=dlg)
            if p:
                v_vidpath.set(p)
                _push_history("h.yolo.video_path", p)
                combo_vid["values"] = _get_history("h.yolo.video_path")

        Button(file_frame, text="Duyệt…", command=_pick_video,
               bg=ACCENT2, fg="white", font=F_MAIN, relief="flat",
               padx=8, cursor="hand2").pack(side=LEFT)

        # Loop checkbox
        v_loop = BooleanVar(value=True)
        loop_row = Frame(dlg, bg=BG)
        loop_row.pack(fill=X, padx=16, pady=(2, 4))
        Label(loop_row, text="", bg=BG, width=14).pack(side=LEFT)
        Checkbutton(loop_row, text="Lặp lại (Loop) khi hết video",
                    variable=v_loop, bg=BG, fg=TEXT,
                    activebackground=BG, selectcolor="#16162a",
                    font=F_MAIN, cursor="hand2").pack(side=LEFT)

        # RTSP / HTTP stream row
        rtsp_row = Frame(dlg, bg=BG)
        rtsp_row.pack(fill=X, padx=16, pady=(8, 2))
        Label(rtsp_row, text="RTSP / HTTP:", bg=BG, fg=DIM, font=F_MAIN,
              width=14, anchor=W).pack(side=LEFT)
        v_rtsp = StringVar()
        rtsp_hist = _get_history("h.yolo.rtsp_url")
        combo_rtsp = ttk.Combobox(rtsp_row, textvariable=v_rtsp,
                                   font=F_MAIN, width=36)
        combo_rtsp["values"] = rtsp_hist
        combo_rtsp.set(rtsp_hist[0] if rtsp_hist else "rtsp://")
        combo_rtsp.pack(side=LEFT, fill=X, expand=True)
        _bind_history("h.yolo.rtsp_url", combo_rtsp)

        # Separator
        Frame(dlg, bg=DIM, height=1).pack(fill=X, padx=16, pady=4)

        # Webcam row
        cam_row = Frame(dlg, bg=BG)
        cam_row.pack(fill=X, padx=16, pady=(2, 16))
        Label(cam_row, text="Webcam index:", bg=BG, fg=DIM, font=F_MAIN,
              width=14, anchor=W).pack(side=LEFT)
        v_cam = StringVar(value="0")
        Spinbox(cam_row, from_=0, to=9, textvariable=v_cam,
                width=3, bg="#16162a", fg=TEXT, insertbackground=TEXT,
                buttonbackground=ACCENT2, relief="flat", font=F_MONO,
                ).pack(side=LEFT, padx=(0, 8))
        Label(cam_row, text="(0 = camera mặc định)", bg=BG, fg=DIM,
              font=("Segoe UI", 8)).pack(side=LEFT)

        # Buttons
        btn_frame = Frame(dlg, bg=BG)
        btn_frame.pack(pady=(0, 16))

        _result = [None]

        def _start_file():
            path = v_vidpath.get().strip()
            if not path:
                messagebox.showwarning("Chưa chọn", "Vui lòng chọn file video.",
                                       parent=dlg)
                return
            if not os.path.isfile(path):
                messagebox.showwarning("Không tìm thấy",
                                       f"File không tồn tại:\n{path}", parent=dlg)
                return
            _push_history("h.yolo.video_path", path)
            combo_vid["values"] = _get_history("h.yolo.video_path")
            _result[0] = ("file", path, v_loop.get())
            dlg.destroy()

        def _start_cam():
            try:
                idx = int(v_cam.get())
            except ValueError:
                idx = 0
            _result[0] = ("cam", idx, False)
            dlg.destroy()

        def _start_rtsp():
            url = v_rtsp.get().strip()
            if not url or url in ("rtsp://", "http://"):
                messagebox.showwarning("Chưa nhập URL",
                                       "Vui lòng nhập RTSP hoặc HTTP URL.",
                                       parent=dlg)
                return
            _push_history("h.yolo.rtsp_url", url)
            combo_rtsp["values"] = _get_history("h.yolo.rtsp_url")
            _result[0] = ("rtsp", url, False)
            dlg.destroy()

        Button(btn_frame, text="▶ Mở File Video", command=_start_file,
               bg=ACCENT, fg="white", font=F_BOLD, relief="flat",
               padx=12, cursor="hand2").pack(side=LEFT, padx=(0, 8))
        Button(btn_frame, text="📡 Mở RTSP", command=_start_rtsp,
               bg="#1a6b3c", fg="white", font=F_BOLD, relief="flat",
               padx=12, cursor="hand2").pack(side=LEFT, padx=(0, 8))
        Button(btn_frame, text="📷 Mở Webcam", command=_start_cam,
               bg="#2e5fa3", fg="white", font=F_BOLD, relief="flat",
               padx=12, cursor="hand2").pack(side=LEFT, padx=(0, 8))
        Button(btn_frame, text="Hủy", command=dlg.destroy,
               bg=CARD, fg=DIM, font=F_MAIN, relief="flat",
               padx=8, cursor="hand2").pack(side=LEFT)

        # Center dialog
        dlg.update_idletasks()
        x = (self.root.winfo_x()
             + (self.root.winfo_width()  - dlg.winfo_width())  // 2)
        y = (self.root.winfo_y()
             + (self.root.winfo_height() - dlg.winfo_height()) // 2)
        dlg.geometry(f"+{x}+{y}")

        self.root.wait_window(dlg)
        if _result[0] is None:
            return

        src_type, src_val, do_loop = _result[0]
        if src_type == "file":
            self._launch_video_window(src_val, os.path.basename(src_val), do_loop)
        elif src_type == "rtsp":
            self._launch_video_window(src_val, src_val, False)
        else:
            self._launch_video_window(src_val, f"Webcam #{src_val}", False)

    def _launch_video_window(self, source, source_name: str, loop_video: bool):
        """Cửa sổ detect video liên tục — worker thread gửi frame qua queue."""
        # speed map: label → multiplier (0.0 = tối đa, không sleep)
        _SPEED_MAP = {
            "0.25×": 0.25, "0.5×": 0.5, "1×": 1.0,
            "1.5×": 1.5,   "2×": 2.0,   "4×": 4.0, "Max": 0.0,
        }

        win = Toplevel(self.root)
        win.title(f"YOLO Video Detection — {source_name}")
        win.configure(bg=BG)
        win.resizable(True, True)
        win.minsize(640, 400)
        win.geometry("960x580")

        _running  = [True]
        _paused   = [False]
        _after_id = [None]
        _last_pil = [None]
        frame_q   = _q.Queue(maxsize=2)
        v_speed   = StringVar(value="1×")

        def _stop_and_close():
            _running[0] = False
            if _after_id[0]:
                try:
                    win.after_cancel(_after_id[0])
                except Exception:
                    pass
            try:
                win.destroy()
            except Exception:
                pass

        win.protocol("WM_DELETE_WINDOW", _stop_and_close)
        win.bind("<Escape>", lambda _: _stop_and_close())

        # ── Info bar ──────────────────────────────────────────────────────
        info_bar = Frame(win, bg=CARD, padx=8, pady=5)
        info_bar.pack(fill=X)

        Label(info_bar, text=f"▶ {source_name}",
              bg=CARD, fg=TEXT, font=F_BOLD).pack(side=LEFT, padx=(0, 12))

        lbl_fps = Label(info_bar, text="FPS: —",
                        bg=CARD, fg=ACCENT, font=F_MONO)
        lbl_fps.pack(side=LEFT, padx=(0, 8))

        # Native FPS label — updated once cap opens
        lbl_src_fps = Label(info_bar, text="",
                            bg=CARD, fg=DIM, font=F_MONO)
        lbl_src_fps.pack(side=LEFT, padx=(0, 12))

        lbl_ndet = Label(info_bar, text="Đối tượng: —",
                         bg=CARD, fg=SUCCESS, font=F_MONO)
        lbl_ndet.pack(side=LEFT, padx=(0, 12))

        lbl_det_info = Label(info_bar, text="",
                             bg=CARD, fg=DIM, font=F_MONO)
        lbl_det_info.pack(side=LEFT, anchor=W, padx=(0, 12))

        lbl_lpr_info = Label(info_bar, text="",
                             bg=CARD, fg="#50dc64", font=F_MONO)
        lbl_lpr_info.pack(side=LEFT, expand=True, anchor=W)

        lbl_status = Label(info_bar, text="Đang khởi động...",
                           bg=CARD, fg=DIM, font=F_MAIN)
        lbl_status.pack(side=RIGHT)

        # ── Video canvas ── pack sau tất cả các bar để controls luôn hiển thị
        vid_label = Label(win, bg="#0d0d1a",
                          text="Đang khởi tạo...", fg=DIM,
                          font=("Segoe UI", 14))

        def _on_zoom(_e=None):
            if _last_pil[0] is not None:
                from ...core.ui_helpers import _zoom_image_window
                _zoom_image_window(win, _last_pil[0], source_name)

        vid_label.bind("<Double-Button-1>", _on_zoom)

        # ── Control bar ──────────────────────────────────────────────────
        ctrl_bar = Frame(win, bg=CARD, padx=8, pady=6)
        ctrl_bar.pack(fill=X)

        btn_pause = Button(ctrl_bar, text="⏸ Tạm dừng",
                           command=lambda: _toggle_pause(),
                           bg=ACCENT2, fg="white", font=F_MAIN,
                           relief="flat", padx=10, cursor="hand2")
        btn_pause.pack(side=LEFT, padx=(0, 8))

        Button(ctrl_bar, text="■ Dừng & Đóng",
               command=_stop_and_close,
               bg=ACCENT, fg="white", font=F_MAIN,
               relief="flat", padx=10, cursor="hand2").pack(side=LEFT)

        # Speed control
        Frame(ctrl_bar, bg=DIM, width=1).pack(side=LEFT, fill=Y, padx=(12, 8))
        Label(ctrl_bar, text="Tốc độ:", bg=CARD, fg=TEXT,
              font=F_BOLD).pack(side=LEFT)
        speed_combo = ttk.Combobox(
            ctrl_bar, textvariable=v_speed,
            values=list(_SPEED_MAP.keys()),
            state="readonly", font=F_MAIN, width=5)
        speed_combo.pack(side=LEFT, padx=(4, 0))

        # Keyboard shortcuts: [ = slower, ] = faster
        _speed_keys = list(_SPEED_MAP.keys())

        def _speed_step(delta: int):
            cur = v_speed.get()
            idx = _speed_keys.index(cur) if cur in _speed_keys else 2
            new_idx = max(0, min(len(_speed_keys) - 1, idx + delta))
            v_speed.set(_speed_keys[new_idx])

        win.bind("[", lambda _: _speed_step(-1))
        win.bind("]", lambda _: _speed_step(+1))

        # Conf / IoU read-only display
        conf_val = max(self.v_conf_thresh.get(), self.v_conf.get())
        iou_val  = self.v_iou.get()
        Frame(ctrl_bar, bg=DIM, width=1).pack(side=LEFT, fill=Y, padx=(12, 8))
        Label(ctrl_bar, text=f"Conf: {conf_val:.2f}",
              bg=CARD, fg=DIM, font=F_MONO).pack(side=LEFT)
        Label(ctrl_bar, text=f"  IoU: {iou_val:.2f}",
              bg=CARD, fg=DIM, font=F_MONO).pack(side=LEFT, padx=(4, 0))
        if loop_video:
            Label(ctrl_bar, text="  [Loop]",
                  bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT, padx=(8, 0))

        Label(ctrl_bar,
              text="Space=pause  [ ]=tốc độ  Dbl-click=zoom",
              bg=CARD, fg=DIM, font=("Segoe UI", 8)).pack(side=RIGHT)

        win.bind("<space>", lambda _: _toggle_pause())

        # ── Seek bar (chỉ file video, không phải webcam/RTSP) ────────────
        _total_frames   = [0]
        _seek_requested = [None]   # frame index cần seek, None = không seek
        _seeking        = [False]  # đang kéo slider (tạm dừng cập nhật tự động)

        is_file_source = isinstance(source, str) and os.path.isfile(source)
        if is_file_source:
            seek_bar = Frame(win, bg=CARD, padx=8, pady=4)
            seek_bar.pack(fill=X)

            v_seek_pos  = IntVar(value=0)
            lbl_pos     = Label(seek_bar, text="00:00 / 00:00",
                                bg=CARD, fg=DIM, font=F_MONO)
            lbl_pos.pack(side=LEFT, padx=(0, 8))

            seek_slider = ttk.Scale(seek_bar, from_=0, to=1000,
                                    orient="horizontal", variable=v_seek_pos)
            seek_slider.pack(side=LEFT, fill=X, expand=True)

            def _fmt_time(frames, fps):
                if fps <= 0:
                    return "—"
                secs = int(frames / fps)
                return f"{secs // 60:02d}:{secs % 60:02d}"

            def _on_seek_press(_e):
                _seeking[0] = True

            def _on_seek_release(_e):
                if _total_frames[0] > 0:
                    frac = v_seek_pos.get() / 1000.0
                    _seek_requested[0] = int(frac * _total_frames[0])
                _seeking[0] = False

            seek_slider.bind("<ButtonPress-1>",   _on_seek_press)
            seek_slider.bind("<ButtonRelease-1>", _on_seek_release)

            def _update_seek(cur_frame):
                if _seeking[0] or _total_frames[0] <= 0:
                    return
                try:
                    v_seek_pos.set(int(cur_frame / _total_frames[0] * 1000))
                    fps_n = cap_fps_ref[0]
                    lbl_pos.config(
                        text=f"{_fmt_time(cur_frame, fps_n)} / "
                             f"{_fmt_time(_total_frames[0], fps_n)}")
                except Exception:
                    pass
        else:
            _update_seek   = None
            _seek_requested = [None]
        cap_fps_ref = [25.0]   # actualFPS из cap, обновляется в worker

        def _toggle_pause():
            _paused[0] = not _paused[0]
            btn_pause.config(
                text="▶ Tiếp tục" if _paused[0] else "⏸ Tạm dừng",
                bg="#c0411a" if _paused[0] else ACCENT2)
            lbl_status.config(
                text="Tạm dừng" if _paused[0] else "Đang chạy...")

        # vid_names cần trước save_bar (dùng để build class checkboxes)
        vid_names = {}
        try:
            if self.model:
                vid_names = dict(self.model.names)
        except Exception:
            pass

        # ── Save-frame panel ─────────────────────────────────────────────
        save_bar = Frame(win, bg="#16162a", padx=8, pady=5)
        save_bar.pack(fill=X)

        v_save_enable  = BooleanVar(value=False)
        v_save_no_det  = BooleanVar(value=True)   # lưu khi không detect được gì
        v_save_classes = {}                        # {class_name: BooleanVar} — lưu khi class xuất hiện
        v_save_interval = IntVar(value=500)        # ms giữa 2 lần lưu
        v_save_folder  = StringVar(
            value=_get_history("h.yolo.vid_save_folder")[0]
            if _get_history("h.yolo.vid_save_folder") else "")
        lbl_save_count = [None]                    # ref label đếm số frame đã lưu
        _save_frame_count = [0]
        _last_save_ms = [0]                        # time.monotonic() * 1000

        # Row 1: enable + folder
        sv_r1 = Frame(save_bar, bg="#16162a")
        sv_r1.pack(fill=X, pady=(0, 3))
        Checkbutton(sv_r1, text="💾 Lưu frame", variable=v_save_enable,
                    bg="#16162a", fg=TEXT, selectcolor="#16162a",
                    activebackground="#16162a", font=F_BOLD,
                    cursor="hand2").pack(side=LEFT, padx=(0, 8))
        Label(sv_r1, text="Thư mục:", bg="#16162a", fg=DIM,
              font=F_MAIN).pack(side=LEFT)
        sv_combo_folder = ttk.Combobox(sv_r1, textvariable=v_save_folder,
                                        font=F_MAIN, width=30)
        sv_combo_folder["values"] = _get_history("h.yolo.vid_save_folder")
        sv_combo_folder.pack(side=LEFT, padx=(4, 4))
        _bind_history("h.yolo.vid_save_folder", sv_combo_folder)

        def _pick_save_folder():
            p = filedialog.askdirectory(title="Chọn thư mục lưu frame", parent=win)
            if p:
                v_save_folder.set(p)
                _push_history("h.yolo.vid_save_folder", p)
                sv_combo_folder["values"] = _get_history("h.yolo.vid_save_folder")
        Button(sv_r1, text="Duyệt…", command=_pick_save_folder,
               bg=ACCENT2, fg="white", font=F_MAIN, relief="flat",
               padx=6, cursor="hand2").pack(side=LEFT)
        lbl_save_count[0] = Label(sv_r1, text="Đã lưu: 0",
                                   bg="#16162a", fg=DIM, font=F_MONO)
        lbl_save_count[0].pack(side=LEFT, padx=(12, 0))
        Button(sv_r1, text="📂", command=lambda: (
                   os.startfile(v_save_folder.get())
                   if v_save_folder.get() and os.path.isdir(v_save_folder.get())
                   else None),
               bg="#16162a", fg=DIM, font=F_MAIN, relief="flat",
               cursor="hand2").pack(side=LEFT, padx=(4, 0))

        # Duration: lưu tối đa N giây sau mỗi lần trigger (0 = không giới hạn)
        v_save_duration = IntVar(value=0)

        # Row 2: điều kiện — checkbox theo từng label + cài đặt
        sv_r2 = Frame(save_bar, bg="#16162a")
        sv_r2.pack(fill=X, pady=(2, 0))
        Label(sv_r2, text="Lưu khi:", bg="#16162a", fg=DIM,
              font=F_MAIN).pack(side=LEFT, padx=(0, 6))

        # Label đặc biệt: "Không có label" (không detect được gì)
        _KEY_EMPTY = "__empty__"
        v_save_no_det = BooleanVar(value=True)   # giữ lại var cho logic cũ
        v_save_classes[_KEY_EMPTY] = v_save_no_det
        Checkbutton(sv_r2, text="Không có label",
                    variable=v_save_no_det,
                    bg="#16162a", fg="#9090c0", selectcolor="#16162a",
                    activebackground="#16162a",
                    font=("Segoe UI", 8), cursor="hand2").pack(
            side=LEFT, padx=(0, 4))

        # Checkbox từng class trong model
        for _cid, _cname in sorted(vid_names.items(), key=lambda x: x[1]):
            _v = BooleanVar(value=False)
            v_save_classes[_cname] = _v
            Checkbutton(sv_r2, text=_cname, variable=_v,
                        bg="#16162a", fg=TEXT, selectcolor="#16162a",
                        activebackground="#16162a",
                        font=("Segoe UI", 8), cursor="hand2").pack(
                side=LEFT, padx=(0, 4))

        Frame(sv_r2, bg=DIM, width=1).pack(side=LEFT, fill=Y, padx=(8, 8))
        Label(sv_r2, text="Tần suất:", bg="#16162a", fg=DIM,
              font=F_MAIN).pack(side=LEFT)
        Spinbox(sv_r2, from_=100, to=10000, increment=100,
                textvariable=v_save_interval, width=5,
                bg="#0d0d1a", fg=TEXT, insertbackground=TEXT,
                buttonbackground=ACCENT2, relief="flat",
                font=F_MONO).pack(side=LEFT, padx=(4, 2))
        Label(sv_r2, text="ms", bg="#16162a", fg=DIM,
              font=F_MAIN).pack(side=LEFT)
        Frame(sv_r2, bg=DIM, width=1).pack(side=LEFT, fill=Y, padx=(8, 8))
        Label(sv_r2, text="Lưu trong:", bg="#16162a", fg=DIM,
              font=F_MAIN).pack(side=LEFT)
        Spinbox(sv_r2, from_=0, to=3600, increment=1,
                textvariable=v_save_duration, width=4,
                bg="#0d0d1a", fg=TEXT, insertbackground=TEXT,
                buttonbackground=ACCENT2, relief="flat",
                font=F_MONO).pack(side=LEFT, padx=(4, 2))
        Label(sv_r2, text="giây (0=∞)", bg="#16162a", fg=DIM,
              font=F_MAIN).pack(side=LEFT)

        # Video area — pack sau tất cả bars để chúng luôn hiện ở trên
        vid_label.pack(fill=BOTH, expand=True)

        # Capture params trên main thread
        sel_cls    = self._get_sel_classes()
        lw         = max(1, self.v_line_width.get())
        fs         = max(6, self.v_font_size.get())
        model2_vid = self.model2          # snapshot tại thời điểm mở cửa sổ video
        check_lpr  = self.v_check_lpr.get() and _REQ_OK and _PIL_OK
        lpr_urls   = ([v.get().strip() for v in self._lpr_url_vars
                       if v.get().strip()] if check_lpr else [])
        lpr_timeout  = self._lpr_timeout_var.get() if check_lpr else 10
        lpr_fullimg  = [v.get() for v in self._lpr_fullimg_vars] if check_lpr else []
        lpr_font_sz  = max(12, self._lpr_font_size_var.get()) if check_lpr else 16
        do_lpr       = bool(check_lpr and lpr_urls)
        _LPR_EVERY    = 3          # gọi LPR mỗi N frame (tránh làm giảm FPS)
        lpr_skip_ctr  = [0]        # đếm frame skip LPR
        lpr_last_text = [""]       # kết quả LPR cuối để hiển thị info bar
        _lpr_vid_cache = [None]    # [(x1,y1,x2,y2,plates_tsv)...] từ lần gọi LPR mới nhất

        # Snapshot dict — worker đọc từ đây (thread-safe, không gọi Tkinter từ thread phụ)
        _snap = {
            "save_enable":   False,
            "save_interval": 500,
            "save_duration": 0,    # giây, 0 = không giới hạn
            "save_folder":   "",
            "save_classes":  {},   # {class_name: bool} — kể cả "__empty__"
        }
        _save_start_ms = [0.0]     # thời điểm bắt đầu lưu (monotonic ms), 0 = chưa bắt đầu

        def _refresh_snap():
            """Cập nhật snapshot từ Tkinter vars — chỉ gọi từ main thread."""
            if not _running[0]:
                return
            _snap["save_enable"]   = v_save_enable.get()
            _snap["save_interval"] = max(100, v_save_interval.get())
            _snap["save_duration"] = max(0, v_save_duration.get())
            _snap["save_folder"]   = v_save_folder.get().strip()
            _snap["save_classes"]  = {k: v.get() for k, v in v_save_classes.items()}
            win.after(200, _refresh_snap)   # refresh 5 lần/s — đủ nhanh

        win.after(100, _refresh_snap)  # bắt đầu refresh sau khi UI ổn định

        # ── Worker thread: read + detect ─────────────────────────────────
        def _worker():
          try:
            cap = cv2.VideoCapture(source)
            if not cap.isOpened():
                self.root.after(0, lambda: messagebox.showerror(
                    "Lỗi mở video",
                    f"Không thể mở nguồn: {source}", parent=win))
                _running[0] = False
                return

            fps_native = cap.get(cv2.CAP_PROP_FPS)
            if fps_native <= 0:
                fps_native = 25.0
            cap_fps_ref[0] = fps_native

            total_f = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if total_f > 0:
                _total_frames[0] = total_f

            # Show native fps in info bar
            self.root.after(0, lambda f=fps_native:
                            lbl_src_fps.config(text=f"(src {f:.0f}fps)"))

            t0          = time.time()
            frame_count = 0
            fps_disp    = 0.0

            self.root.after(0, lambda: lbl_status.config(text="Đang chạy..."))

            cur_frame_idx = [0]

            while _running[0]:
                if _paused[0]:
                    time.sleep(0.05)
                    continue

                # Seek nếu user kéo slider
                if _seek_requested[0] is not None:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, _seek_requested[0])
                    cur_frame_idx[0] = _seek_requested[0]
                    _seek_requested[0] = None

                t_frame_start = time.time()

                ret, frame = cap.read()
                if not ret:
                    if loop_video and isinstance(source, str):
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        cur_frame_idx[0] = 0
                        continue
                    self.root.after(0, lambda: lbl_status.config(
                        text="Video kết thúc"))
                    break

                cur_frame_idx[0] += 1
                if _update_seek is not None:
                    self.root.after(0, lambda f=cur_frame_idx[0]:
                                    _update_seek(f))

                # Detect
                boxes = None   # reset mỗi frame để điều kiện lưu không dùng kết quả cũ
                try:
                    results = self.model.predict(
                        source=frame,
                        classes=sel_cls,
                        conf=conf_val,
                        iou=iou_val,
                        imgsz=640,
                        agnostic_nms=True,
                        verbose=False,
                    )
                    boxes = results[0].boxes
                    n_det = len(boxes) if boxes is not None else 0

                    if model2_vid is not None:
                        # Dual model — vẽ thủ công 2 màu cố định
                        try:
                            results2 = model2_vid.predict(
                                source=frame,
                                classes=sel_cls,
                                conf=conf_val,
                                iou=iou_val,
                                imgsz=640,
                                agnostic_nms=True,
                                verbose=False,
                            )
                            boxes2 = results2[0].boxes
                            n_det2 = len(boxes2) if boxes2 is not None else 0
                        except Exception:
                            boxes2 = None
                            n_det2 = 0

                        from PIL import ImageFont as _IFont
                        _orig_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        _pil_vid  = Image.fromarray(_orig_rgb)
                        _draw_vid = ImageDraw.Draw(_pil_vid)
                        try:
                            _ifont = _IFont.truetype("arial.ttf", fs)
                        except Exception:
                            try:
                                _ifont = _IFont.load_default(size=fs)
                            except Exception:
                                _ifont = _IFont.load_default()

                        _C1 = (0, 200, 255)    # cyan  — Model 1
                        _C2 = (240, 89, 34)    # cam KZTEK — Model 2

                        _names1 = getattr(self.model, "names", {}) or {}
                        if boxes is not None and len(boxes):
                            for _b in boxes:
                                _x1, _y1, _x2, _y2 = (int(v) for v in _b.xyxy[0])
                                _cid  = int(_b.cls[0])
                                _cf   = float(_b.conf[0])
                                _lbl  = f"M1:{_names1.get(_cid, str(_cid))} {_cf:.2f}"
                                _draw_vid.rectangle([_x1, _y1, _x2, _y2],
                                                    outline=_C1, width=lw)
                                try:
                                    _tb = _draw_vid.textbbox((0, 0), _lbl, font=_ifont)
                                    _tw, _th = _tb[2]-_tb[0], _tb[3]-_tb[1]
                                    _ty = max(_y1-_th-4, 0)
                                    _draw_vid.rectangle([_x1, _ty, _x1+_tw+6, _ty+_th+4],
                                                        fill=_C1)
                                    _draw_vid.text((_x1+3, _ty+2), _lbl,
                                                   fill=_contrast_text(_C1), font=_ifont)
                                except Exception:
                                    _draw_vid.text((_x1, max(_y1-fs-2, 0)),
                                                   _lbl, fill=_C1, font=_ifont)

                        _names2 = getattr(model2_vid, "names", {}) or {}
                        if boxes2 is not None and len(boxes2):
                            for _b in boxes2:
                                _x1, _y1, _x2, _y2 = (int(v) for v in _b.xyxy[0])
                                _cid  = int(_b.cls[0])
                                _cf   = float(_b.conf[0])
                                _lbl  = f"M2:{_names2.get(_cid, str(_cid))} {_cf:.2f}"
                                _draw_vid.rectangle([_x1, _y1, _x2, _y2],
                                                    outline=_C2, width=lw)
                                try:
                                    _tb = _draw_vid.textbbox((0, 0), _lbl, font=_ifont)
                                    _tw, _th = _tb[2]-_tb[0], _tb[3]-_tb[1]
                                    _ty = max(_y1-_th-4, 0)
                                    _draw_vid.rectangle([_x1, _ty, _x1+_tw+6, _ty+_th+4],
                                                        fill=_C2)
                                    _draw_vid.text((_x1+3, _ty+2), _lbl,
                                                   fill=_contrast_text(_C2), font=_ifont)
                                except Exception:
                                    _draw_vid.text((_x1, max(_y1-fs-2, 0)),
                                                   _lbl, fill=_C2, font=_ifont)

                        annotated_bgr = cv2.cvtColor(np.array(_pil_vid),
                                                     cv2.COLOR_RGB2BGR)
                        _cnts: dict = {}
                        if boxes is not None:
                            for _cid in boxes.cls.tolist():
                                _k = f"M1:{_names1.get(int(_cid), str(int(_cid)))}"
                                _cnts[_k] = _cnts.get(_k, 0) + 1
                        if boxes2 is not None:
                            for _cid in boxes2.cls.tolist():
                                _k = f"M2:{_names2.get(int(_cid), str(int(_cid)))}"
                                _cnts[_k] = _cnts.get(_k, 0) + 1
                        n_det      = n_det + n_det2
                        det_summary = "  ".join(f"{k}:{v}" for k, v in _cnts.items())

                    else:
                        # Single model — dùng results[0].plot() như cũ
                        annotated_bgr = results[0].plot(line_width=lw, font_size=fs)
                        if n_det > 0 and self.model and hasattr(self.model, "names"):
                            _cnts = {}
                            for _cid in boxes.cls.tolist():
                                _nm = self.model.names[int(_cid)]
                                _cnts[_nm] = _cnts.get(_nm, 0) + 1
                            det_summary = "  ".join(
                                f"{k}:{v}" for k, v in _cnts.items())
                        else:
                            det_summary = ""

                except Exception:
                    annotated_bgr = frame
                    n_det         = 0
                    det_summary   = ""

                # FPS counter (actual throughput)
                frame_count += 1
                elapsed = time.time() - t0
                if elapsed >= 0.5:
                    fps_disp    = frame_count / elapsed
                    frame_count = 0
                    t0          = time.time()

                # BGR → PIL
                rgb       = cv2.cvtColor(annotated_bgr, cv2.COLOR_BGR2RGB)
                pil_frame = Image.fromarray(rgb)

                # ── LPR (mỗi _LPR_EVERY frame, chỉ khi có detect) ──────────
                if do_lpr and n_det > 0 and boxes is not None:
                    lpr_skip_ctr[0] = (lpr_skip_ctr[0] + 1) % _LPR_EVERY
                    if lpr_skip_ctr[0] == 0:
                        # Gọi LPR thật + cập nhật cache
                        try:
                            bwc = [(int(x1), int(y1), int(x2), int(y2), int(cid))
                                   for (x1, y1, x2, y2), cid in zip(
                                       boxes.xyxy.tolist(), boxes.cls.tolist())]
                            pil_orig_lpr = Image.fromarray(
                                cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                            pil_frame = self._lpr_overlay_boxes_vid(
                                pil_frame, pil_orig_lpr, bwc, lpr_urls,
                                lpr_timeout, vid_names, lpr_fullimg, lpr_font_sz)
                            _lpr_vid_cache[0] = list(self._last_lpr_plates_result)
                            plates = [p for _, _, _, _, tsv in (_lpr_vid_cache[0] or [])
                                      for p in tsv.split("\t") if p]
                            lpr_last_text[0] = ("🔤 " + " | ".join(plates)
                                                 if plates else "")
                        except Exception:
                            pass
                    elif _lpr_vid_cache[0]:
                        # Frame skip: vẽ lại từ cache để không bị nháy
                        try:
                            from PIL import ImageDraw as _LDraw, ImageFont as _LFont
                            _draw = _LDraw.Draw(pil_frame)
                            _iw, _ih = pil_frame.size
                            try:
                                _font = _LFont.truetype("arial.ttf", lpr_font_sz)
                            except Exception:
                                try:
                                    _font = _LFont.load_default(size=lpr_font_sz)
                                except Exception:
                                    _font = _LFont.load_default()
                            for (cx1, cy1, cx2, cy2, _tsv) in _lpr_vid_cache[0]:
                                if _tsv:
                                    self._lpr_draw_lines(_draw, _font,
                                                         cx1, cy1, cx2, cy2,
                                                         _tsv, _iw, _ih, lpr_font_sz)
                        except Exception:
                            pass
                elif do_lpr and n_det == 0:
                    _lpr_vid_cache[0] = None
                    lpr_last_text[0] = ""

                # Push (drop if full — don't block worker)
                try:
                    frame_q.put_nowait((pil_frame, n_det, fps_disp,
                                        det_summary, lpr_last_text[0]))
                except _q.Full:
                    pass

                # ── Lưu frame theo điều kiện (dùng _snap, không đọc Tkinter) ──
                if _snap["save_enable"]:
                    now_ms    = time.monotonic() * 1000
                    interval  = _snap["save_interval"]
                    duration  = _snap["save_duration"]  # giây, 0 = không giới hạn
                    save_dir  = _snap["save_folder"]
                    # Kiểm tra duration: nếu đã lưu quá N giây kể từ lần trigger đầu → dừng
                    if (duration > 0 and _save_start_ms[0] > 0
                            and now_ms - _save_start_ms[0] > duration * 1000):
                        pass   # hết duration, không lưu
                    elif now_ms - _last_save_ms[0] >= interval and save_dir:
                        should_save = False
                        cls_map = _snap["save_classes"]
                        # "__empty__" = lưu khi không detect được gì
                        if n_det == 0 and cls_map.get("__empty__", False):
                            should_save = True
                        if not should_save and n_det > 0 and boxes is not None:
                            detected_cls = set()
                            for cid in boxes.cls.tolist():
                                nm = vid_names.get(int(cid), "")
                                if nm:
                                    detected_cls.add(nm)
                            for cname, enabled in cls_map.items():
                                if cname != "__empty__" and enabled and cname in detected_cls:
                                    should_save = True
                                    break
                        if should_save:
                            if _save_start_ms[0] == 0:
                                _save_start_ms[0] = now_ms  # ghi nhận lần trigger đầu
                            try:
                                import datetime as _dt
                                os.makedirs(save_dir, exist_ok=True)
                                ts = _dt.datetime.now().strftime(
                                    "%Y%m%d_%H%M%S_%f")[:21]
                                cv2.imwrite(
                                    os.path.join(save_dir, f"frame_{ts}.jpg"),
                                    frame)
                                _save_frame_count[0] += 1
                                cnt = _save_frame_count[0]
                                self.root.after(0, lambda c=cnt:
                                    lbl_save_count[0].config(
                                        text=f"Đã lưu: {c}", fg="#50dc64"))
                            except Exception:
                                pass
                            _last_save_ms[0] = now_ms
                        else:
                            _save_start_ms[0] = 0  # reset khi điều kiện không còn đúng

                # ── Speed throttle ────────────────────────────────────────
                speed_mul = _SPEED_MAP.get(v_speed.get(), 1.0)
                if speed_mul > 0 and fps_native > 0:
                    # target interval for this frame at the chosen multiplier
                    target_interval = 1.0 / (fps_native * speed_mul)
                    spent = time.time() - t_frame_start
                    sleep_dur = target_interval - spent
                    if sleep_dur > 0.001:
                        time.sleep(sleep_dur)
                # speed_mul == 0 → "Max": no sleep, run as fast as YOLO allows

            cap.release()
          except Exception as _worker_ex:
            import traceback as _tb
            _msg = _tb.format_exc()
            self.root.after(0, lambda m=_msg: messagebox.showerror(
                "Lỗi worker video", m[:1000], parent=win))
            _running[0] = False

        # ── Main-thread polling ──────────────────────────────────────────
        def _poll():
            try:
                item = frame_q.get_nowait()
                pil_frame = item[0]
                n_det      = item[1]
                fps_val    = item[2]
                det_summary = item[3]
                lpr_text   = item[4] if len(item) > 4 else ""
                _last_pil[0] = pil_frame

                cw = max(vid_label.winfo_width(),  640)
                ch = max(vid_label.winfo_height(), 360)
                img_w, img_h = pil_frame.size
                scale = min(cw / img_w, ch / img_h)
                new_w = max(1, int(img_w * scale))
                new_h = max(1, int(img_h * scale))
                display = pil_frame.resize(
                    (new_w, new_h), Image.Resampling.BILINEAR)

                tk_img = ImageTk.PhotoImage(display)
                vid_label.config(image=tk_img, text="")
                vid_label._tk_img = tk_img

                lbl_fps.config(text=f"FPS: {fps_val:.1f}")
                lbl_ndet.config(
                    text=f"Đối tượng: {n_det}",
                    fg=SUCCESS if n_det > 0 else DIM)
                lbl_det_info.config(text=det_summary)
                if do_lpr:
                    lbl_lpr_info.config(
                        text=lpr_text,
                        fg="#50dc64" if lpr_text else DIM)
            except _q.Empty:
                pass
            except Exception:
                pass

            if _running[0]:
                _after_id[0] = win.after(16, _poll)

        threading.Thread(target=_worker, daemon=True).start()
        win.after(200, _poll)


def _path_review_state(path: str) -> str:
    """Trả về 'correct'/'incorrect'/'' dựa trên tên folder chứa ảnh."""
    parent = os.path.basename(os.path.dirname(path))
    if parent == "true":  return "correct"
    if parent == "false": return "incorrect"
    return ""


def _iou_xywhn(cx1, cy1, w1, h1, cx2, cy2, w2, h2):
    x1_min = cx1 - w1 / 2; x1_max = cx1 + w1 / 2
    y1_min = cy1 - h1 / 2; y1_max = cy1 + h1 / 2
    x2_min = cx2 - w2 / 2; x2_max = cx2 + w2 / 2
    y2_min = cy2 - h2 / 2; y2_max = cy2 + h2 / 2
    inter_x = max(0.0, min(x1_max, x2_max) - max(x1_min, x2_min))
    inter_y = max(0.0, min(y1_max, y2_max) - max(y1_min, y2_min))
    inter = inter_x * inter_y
    union = w1 * h1 + w2 * h2 - inter
    return inter / union if union > 0 else 0.0
