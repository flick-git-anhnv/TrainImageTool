import json
import os
import queue
import threading
import time
from datetime import datetime
from pathlib import Path
from tkinter import *
from tkinter import filedialog, messagebox, ttk

from .constants import (
    BG, CARD, ACCENT, ACCENT2, TEXT, DIM, F_MAIN, F_BOLD, F_MONO,
    _LI_API_BASE, _LI_USERNAME, _LI_PASSWORD,
    _LI_MINIO_EP, _LI_MINIO_AK, _LI_MINIO_SK, _LI_MINIO_BUCKET,
    _P8_LOGIN_URL, _P8_API_URL, _P8_CLIENT_ID, _P8_CLIENT_SECRET,
    _P8_USERNAME, _P8_PASSWORD,
    _P6_API_URL, _P6_MINIO_EP, _P6_MINIO_BUCKET, _P6_MINIO_AK, _P6_MINIO_SK,
)
from .imports import _REQUESTS_OK, _CV2_OK
from .settings import _bind_cfg, _cfg_dir, _bind_history, _push_history, _get_history
from .parkingv8_image import Parkingv8Worker
from .parkingv6_image import Parkingv6Worker, _P6SharedLaneState
from .lotte_image import LotteWorker, _SharedLaneState
from .bad_image_viewer import BadImageViewer
from .migrate_structure import open_migrate_window as _open_migrate_window
from .ui_helpers import DateTimePicker


_VTYPE_ORDER = [
    "toan_canh_o_to", "toan_canh_xe_may", "toan_canh_xe_dap",
    "o_to", "xe_may", "xe_dap",
    "o_to_bsx_cut", "xe_may_bsx_cut", "xe_dap_bsx_cut",
    "toan_canh", "xe_tai",
]
_VTYPE_COLORS = {
    "toan_canh_o_to":   "#5a4fa0",
    "toan_canh_xe_may": "#e87d5a",
    "toan_canh_xe_dap": "#9b8ed4",
    "o_to":             "#4A3F8C",
    "xe_may":           "#F05922",
    "xe_dap":           "#B8B3D6",
    "o_to_bsx_cut":     "#FFAA80",
    "xe_may_bsx_cut":   "#CBCBCB",
    "xe_dap_bsx_cut":   "#f0a57a",
    "toan_canh":        "#9090b0",
    "xe_tai":           "#888888",
}
_LANE_PALETTE = [
    "#F05922", "#4A3F8C", "#B8B3D6", "#FFAA80",
    "#7c6fc9", "#e87d5a", "#9b8ed4", "#f0a57a",
]
_THREAD_COLORS = [
    "#F05922", "#4fc3f7", "#81c784", "#ffb74d",
    "#f06292", "#ba68c8", "#4dd0e1", "#ff8a65",
]


class IParkingImageTab(Frame):
    SOURCES = ["LotteImage", "Parkingv8", "Parkingv6"]
    _LOG_MAX = 2000

    def __init__(self, master, root):
        super().__init__(master, bg=BG)
        self.root = root
        self._worker           = None
        self._thread           = None
        self._log_q            = queue.Queue()
        self._stat_q           = queue.Queue()
        self._running          = False
        self._paused           = False
        self._pause_event      = threading.Event()
        self._pause_event.set()
        self._failed_items     = []
        self._run_start_time   = None
        self._last_stat        = {}
        self._last_cfg         = {}
        self._last_source      = "LotteImage"
        self._all_thread_stats = {}
        self._parallel_workers = []
        self._build()
        self._poll()

    # ── layout ───────────────────────────────────────────────────────────────

    def _build(self):
        # Header bar
        top = Frame(self, bg=CARD, padx=16, pady=8)
        top.pack(fill=X)
        Label(top, text="iParking Image — Thu thập ảnh từ hệ thống iParking",
              bg=CARD, fg=TEXT, font=F_BOLD).pack(side=LEFT)
        if not _REQUESTS_OK:
            Label(top, text="  ⚠ pip install requests",
                  bg=CARD, fg="#ff8844", font=("Segoe UI", 9)).pack(side=LEFT, padx=8)
        if not _CV2_OK:
            Label(top, text="  ⚠ pip install opencv-python numpy",
                  bg=CARD, fg="#ff8844", font=("Segoe UI", 9)).pack(side=LEFT, padx=4)

        # Source selector bar
        src_bar = Frame(self, bg=CARD, padx=16, pady=6)
        src_bar.pack(fill=X)
        Label(src_bar, text="Nguồn dữ liệu:", bg=CARD, fg=TEXT, font=F_BOLD).pack(
            side=LEFT, padx=(0, 10))
        self.source_var = StringVar(value="LotteImage")
        _bind_cfg("ip.source", self.source_var)
        src_cb = ttk.Combobox(src_bar, textvariable=self.source_var,
                              values=self.SOURCES, state="readonly",
                              width=16, font=F_BOLD)
        src_cb.pack(side=LEFT)
        src_cb.bind("<<ComboboxSelected>>", self._on_source_change)
        self._src_desc_lbl = Label(src_bar, text="", bg=CARD, fg=DIM,
                                   font=("Segoe UI", 9))
        self._src_desc_lbl.pack(side=LEFT, padx=(14, 0))

        # Scrollable body — inner canvas overrides outer _wrap_scrollable's bind
        canvas = Canvas(self, bg=BG, highlightthickness=0)
        vsb = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=RIGHT, fill=Y)
        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        inner = Frame(canvas, bg=BG)
        cwin = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_canvas_resize(e):
            canvas.itemconfig(cwin, width=e.width)
        canvas.bind("<Configure>", _on_canvas_resize)
        inner.bind("<Configure>",
                   lambda _: canvas.configure(scrollregion=canvas.bbox("all")))

        def _on_enter(_):
            canvas.bind_all(
                "<MouseWheel>",
                lambda ev: canvas.yview_scroll(int(-1 * (ev.delta / 120)), "units"))
        def _on_leave(_):
            canvas.unbind_all("<MouseWheel>")
        canvas.bind("<Enter>", _on_enter)
        canvas.bind("<Leave>", _on_leave)

        p = inner

        self._build_time(p)
        self._build_output(p)
        self._build_common_limits(p)

        # Source-specific settings — dùng container cố định vị trí trong pack
        self._src_container = Frame(p, bg=BG)
        self._src_container.pack(fill=X)
        self._lotte_frm = Frame(self._src_container, bg=BG)
        self._p8_frm    = Frame(self._src_container, bg=BG)
        self._p6_frm    = Frame(self._src_container, bg=BG)
        self._build_lotte_settings(self._lotte_frm)
        self._build_p8_settings(self._p8_frm)
        self._build_p6_settings(self._p6_frm)

        self._build_controls(p)
        self._build_progress(p)
        self._build_dashboard(p)
        self._build_log(p)

        self._on_source_change()

    def _sep(self, parent, text):
        f = Frame(parent, bg=BG)
        f.pack(fill=X, pady=(8, 3))
        Label(f, text=text, font=("Segoe UI", 9, "bold"),
              fg=ACCENT2, bg=BG).pack(side=LEFT)
        Frame(f, bg=DIM, height=1).pack(side=LEFT, fill=X, expand=True,
                                         padx=(8, 0), pady=5)

    # ── common sections ───────────────────────────────────────────────────────

    def _build_time(self, p):
        f = Frame(p, bg=BG, padx=10, pady=4)
        f.pack(fill=X)
        self._sep(f, "Khoảng thời gian (UTC)")
        row = Frame(f, bg=BG)
        row.pack(fill=X)
        Label(row, text="Từ:", bg=BG, fg=TEXT, font=F_MAIN).grid(
            row=0, column=0, padx=(0, 4), sticky=W)
        self.from_var = StringVar(value="2026-05-01 00:00:00")
        _bind_cfg("ip.from", self.from_var)
        DateTimePicker(row, textvariable=self.from_var, mode="datetime").grid(
            row=0, column=1, padx=4)
        Label(row, text="Đến:", bg=BG, fg=TEXT, font=F_MAIN).grid(
            row=0, column=2, padx=(14, 4))
        self.to_var = StringVar(value=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))
        _bind_cfg("ip.to", self.to_var)
        DateTimePicker(row, textvariable=self.to_var, mode="datetime").grid(
            row=0, column=3, padx=4)
        self._time_hint_lbl = Label(row, text="", font=("Segoe UI", 8),
                                    fg=DIM, bg=BG)
        self._time_hint_lbl.grid(row=0, column=4, padx=(14, 0), sticky=W)

    def _build_output(self, p):
        f = Frame(p, bg=BG, padx=10, pady=2)
        f.pack(fill=X)
        self._sep(f, "Thư mục lưu ảnh")
        row = Frame(f, bg=BG)
        row.pack(fill=X)
        row.columnconfigure(0, weight=1)
        self.out_var = StringVar(value=str(Path.cwd() / "images_ip"))
        _bind_cfg("ip.out", self.out_var)
        self._out_combo = ttk.Combobox(row, textvariable=self.out_var,
                                       style="Dark.TCombobox", font=F_MAIN)
        self._out_combo.grid(row=0, column=0, sticky=EW, padx=(0, 6))
        _bind_history("h.ip.out", self._out_combo)
        Button(row, text="Chọn…", command=self._browse,
               bg=ACCENT2, fg="white", font=F_MAIN,
               activebackground=ACCENT, activeforeground="white",
               relief="flat", padx=10, cursor="hand2").grid(row=0, column=1)
        Button(row, text="📂", command=self._open_out,
               bg=CARD, fg=TEXT, font=F_MAIN,
               activebackground=ACCENT2, activeforeground="white",
               relief="flat", padx=6, cursor="hand2").grid(row=0, column=2, padx=(2, 0))
        self._struct_lbl = Label(f, text="", font=("Segoe UI", 8),
                                 fg=DIM, bg=BG, anchor=W, wraplength=800, justify=LEFT)
        self._struct_lbl.pack(fill=X, pady=(3, 0))

    def _build_common_limits(self, p):
        f = Frame(p, bg=BG, padx=10, pady=2)
        f.pack(fill=X)
        self._sep(f, "Cài đặt chung")
        row1 = Frame(f, bg=BG)
        row1.pack(fill=X)
        for col, (lbl, attr, lo, hi, w, val) in enumerate([
            ("Page size:",     "page_size_var",    10,  500,   6,   100),
            ("Max pages:",     "max_pages_var",     1,  99999, 8, 10000),
            ("Nghỉ (s):",      None,                0,  0,     0,     0),
            ("Max ảnh/làn:",   "max_per_lane_var",  0,  999999,8,  1000),
            ("Max ảnh/loại:",  "max_per_cat_var",   0,  999999,8,     0),
            ("Max ảnh/giờ:",   "max_per_hour_var",  0,  99999, 7,     0),
        ]):
            Label(row1, text=lbl, bg=BG, fg=TEXT, font=F_MAIN).grid(
                row=0, column=col * 2, padx=(14 if col else 0, 4), sticky=W)
            if attr is None:
                # sleep entry
                self.sleep_var = DoubleVar(value=0.1)
                _bind_cfg("ip.sleep", self.sleep_var)
                Entry(row1, textvariable=self.sleep_var, width=6,
                      bg=CARD, fg=TEXT, insertbackground=TEXT,
                      relief="flat", font=F_MAIN, bd=4).grid(
                    row=0, column=col * 2 + 1, padx=4)
            else:
                var = IntVar(value=val)
                setattr(self, attr, var)
                _bind_cfg(f"ip.{attr[:-4]}", var)
                Spinbox(row1, from_=lo, to=hi, textvariable=var,
                        width=w, font=F_MAIN, bg=CARD, fg=TEXT,
                        insertbackground=TEXT, buttonbackground=ACCENT2,
                        relief="flat").grid(row=0, column=col * 2 + 1, padx=4)
        # parallel workers row
        row2 = Frame(f, bg=BG)
        row2.pack(fill=X, pady=(6, 0))
        Label(row2, text="Luồng song song:", bg=BG, fg=TEXT, font=F_MAIN).grid(
            row=0, column=0, padx=(0, 4), sticky=W)
        self.parallel_var = IntVar(value=1)
        _bind_cfg("ip.parallel", self.parallel_var)
        Spinbox(row2, from_=1, to=16, textvariable=self.parallel_var,
                width=4, font=F_MAIN, bg=CARD, fg=TEXT,
                insertbackground=TEXT, buttonbackground=ACCENT2,
                relief="flat").grid(row=0, column=1, padx=4)
        Label(row2, text="(chia ngày cho N luồng chạy đồng thời — áp dụng cho cả 3 nguồn)",
              bg=BG, fg=DIM, font=("Segoe UI", 8)).grid(
            row=0, column=2, padx=(4, 0), sticky=W)
        Label(f, text="Max ảnh/làn: tổng cả lần chạy  ·  Max ảnh/loại: tối đa mỗi ngày/loại/làn  ·  Max ảnh/giờ: trải đều theo giờ  ·  0 = không giới hạn",
              font=("Segoe UI", 7), fg=DIM, bg=BG, anchor=W).pack(fill=X, pady=(4, 0))

    # ── Lotte settings ────────────────────────────────────────────────────────

    def _build_lotte_settings(self, p):
        f = Frame(p, bg=BG, padx=10, pady=2)
        f.pack(fill=X)
        self._sep(f, "Cài đặt — LotteImage")
        row = Frame(f, bg=BG)
        row.pack(fill=X)
        self.l_use_minio = BooleanVar(value=True)
        _bind_cfg("lotte.use_minio", self.l_use_minio)
        Checkbutton(row, text="Dùng MinIO", variable=self.l_use_minio,
                    bg=BG, fg=TEXT, selectcolor=CARD,
                    activebackground=BG, font=F_MAIN).grid(
            row=0, column=0, padx=(0, 20))

        self._sep(f, "Phân loại phương tiện (từ khóa)")
        fv = Frame(f, bg=BG)
        fv.pack(fill=X)
        for r, (lbl, key_suffix, default) in enumerate([
            ("Toàn cảnh (mô tả ảnh):", "toan_canh", "toàn cảnh"),
            ("Xe máy (nhóm thẻ):",      "xe_may",    "xe máy"),
            ("Xe đạp (nhóm thẻ):",      "xe_dap",    "xe đạp"),
            ("Ô tô (nhóm thẻ):",        "o_to",      ""),
        ]):
            Label(fv, text=lbl, bg=BG, fg=TEXT, font=F_MAIN).grid(
                row=r, column=0, padx=(0, 6), sticky=W, pady=2)
            var = StringVar(value=default)
            setattr(self, f"l_kw_{key_suffix}", var)
            _bind_cfg(f"lotte.kw_{key_suffix}", var)
            Entry(fv, textvariable=var, width=48,
                  bg=CARD, fg=TEXT, insertbackground=TEXT,
                  relief="flat", font=F_MAIN, bd=4).grid(
                row=r, column=1, sticky=W, padx=4, pady=2)
        Label(f, text="Nhiều từ khóa cách nhau bởi dấu phẩy  ·  Ô tô = mặc định khi không khớp",
              font=("Segoe UI", 8), fg=DIM, bg=BG, anchor=W).pack(fill=X, pady=(2, 0))

        # Advanced (collapsible)
        self._l_adv_open = False
        self._l_adv_lbl = Label(f, text="▶ Nâng cao (API / MinIO)",
                                 font=("Segoe UI", 8, "underline"),
                                 fg=ACCENT2, bg=BG, cursor="hand2")
        self._l_adv_lbl.pack(anchor=W, pady=(8, 0))
        self._l_adv_lbl.bind("<Button-1>", lambda _: self._toggle_adv("l"))
        self._l_adv_frm = Frame(f, bg=CARD, padx=8, pady=6)
        for i, (lbl, attr, default, width, show) in enumerate([
            ("API URL:",        "l_api",  _LI_API_BASE,     38, ""),
            ("Username:",       "l_user", _LI_USERNAME,     16, ""),
            ("Password:",       "l_pass", _LI_PASSWORD,     16, "*"),
            ("MinIO endpoint:", "l_mep",  _LI_MINIO_EP,     26, ""),
            ("MinIO bucket:",   "l_mbk",  _LI_MINIO_BUCKET, 20, ""),
            ("MinIO AK:",       "l_mak",  _LI_MINIO_AK,     16, ""),
            ("MinIO SK:",       "l_msk",  _LI_MINIO_SK,     20, "*"),
        ]):
            r, c = divmod(i, 2)
            Label(self._l_adv_frm, text=lbl, font=("Segoe UI", 8),
                  bg=CARD, fg=DIM).grid(
                row=r, column=c * 2, padx=(0 if c == 0 else 16, 4), pady=2, sticky=W)
            var = StringVar(value=default)
            setattr(self, attr, var)
            _bind_cfg(f"lotte.cfg_{attr[2:]}", var)
            Entry(self._l_adv_frm, textvariable=var, width=width, show=show,
                  bg="#16162a", fg=TEXT, insertbackground=TEXT,
                  relief="flat", font=F_MAIN, bd=4).grid(
                row=r, column=c * 2 + 1, padx=(0, 4), pady=2)

    # ── Parkingv8 settings ────────────────────────────────────────────────────

    def _build_p8_settings(self, p):
        f = Frame(p, bg=BG, padx=10, pady=2)
        f.pack(fill=X)
        self._sep(f, "Cài đặt — Parkingv8")
        row = Frame(f, bg=BG)
        row.pack(fill=X)
        Label(row, text="Nguồn sự kiện:", bg=BG, fg=TEXT, font=F_MAIN).grid(
            row=0, column=0, padx=(0, 4), sticky=W)
        self.p8_source_var = StringVar(value="exits")
        _bind_cfg("p8.source", self.p8_source_var)
        ttk.Combobox(row, textvariable=self.p8_source_var,
                     values=["exits", "entries", "both"],
                     width=10, state="readonly", font=F_MAIN).grid(
            row=0, column=1, padx=4)
        Label(row, text="exits=ra  ·  entries=vào  ·  both=cả hai",
              bg=BG, fg=DIM, font=("Segoe UI", 8)).grid(
            row=0, column=2, padx=(8, 0), sticky=W)

        # Advanced (collapsible)
        self._p8_adv_open = False
        self._p8_adv_lbl = Label(f, text="▶ Nâng cao (API / Xác thực)",
                                  font=("Segoe UI", 8, "underline"),
                                  fg=ACCENT2, bg=BG, cursor="hand2")
        self._p8_adv_lbl.pack(anchor=W, pady=(10, 0))
        self._p8_adv_lbl.bind("<Button-1>", lambda _: self._toggle_adv("p8"))
        self._p8_adv_frm = Frame(f, bg=CARD, padx=8, pady=6)
        gt_row = Frame(self._p8_adv_frm, bg=CARD)
        gt_row.grid(row=0, column=0, columnspan=4, sticky=W, pady=(0, 6))
        Label(gt_row, text="Grant type:", font=("Segoe UI", 8),
              bg=CARD, fg=DIM).pack(side=LEFT, padx=(0, 8))
        self.p8_grant_var = StringVar(value="client_credentials")
        _bind_cfg("p8.grant_type", self.p8_grant_var)
        for val, lbl in [("client_credentials", "Client Credentials"),
                         ("password",           "Password")]:
            Radiobutton(gt_row, text=lbl, variable=self.p8_grant_var, value=val,
                        bg=CARD, fg=TEXT, selectcolor=CARD,
                        activebackground=CARD, font=("Segoe UI", 8)).pack(
                side=LEFT, padx=6)
        for i, (lbl, attr, default, width, show) in enumerate([
            ("Login URL:",     "p8_login_url",    _P8_LOGIN_URL,     32, ""),
            ("API URL:",       "p8_api_url",       _P8_API_URL,       32, ""),
            ("Client ID:",     "p8_client_id",     _P8_CLIENT_ID,     20, ""),
            ("Client Secret:", "p8_client_secret", _P8_CLIENT_SECRET, 24, "*"),
            ("Username:",      "p8_user",          _P8_USERNAME,      20, ""),
            ("Password:",      "p8_pass",          _P8_PASSWORD,      20, "*"),
        ]):
            r, c = divmod(i, 2)
            r += 1
            Label(self._p8_adv_frm, text=lbl, font=("Segoe UI", 8),
                  bg=CARD, fg=DIM).grid(
                row=r, column=c * 2, padx=(0 if c == 0 else 16, 4), pady=2, sticky=W)
            var = StringVar(value=default)
            setattr(self, attr, var)
            _bind_cfg(f"p8.cfg_{attr[3:]}", var)
            Entry(self._p8_adv_frm, textvariable=var, width=width, show=show,
                  bg="#16162a", fg=TEXT, insertbackground=TEXT,
                  relief="flat", font=F_MAIN, bd=4).grid(
                row=r, column=c * 2 + 1, padx=(0, 4), pady=2)

    # ── Parkingv6 settings ────────────────────────────────────────────────────

    def _build_p6_settings(self, p):
        f = Frame(p, bg=BG, padx=10, pady=2)
        f.pack(fill=X)
        self._sep(f, "Cài đặt — Parkingv6")
        row = Frame(f, bg=BG)
        row.pack(fill=X)
        self.p6_use_minio = BooleanVar(value=True)
        _bind_cfg("p6.use_minio", self.p6_use_minio)
        Checkbutton(row, text="Dùng MinIO", variable=self.p6_use_minio,
                    bg=BG, fg=TEXT, selectcolor=CARD,
                    activebackground=BG, font=F_MAIN).grid(
            row=0, column=0, padx=(0, 20))
        Label(row, text="Nguồn SK:", bg=BG, fg=TEXT, font=F_MAIN).grid(
            row=0, column=1, padx=(20, 4))
        self.p6_event_source_var = StringVar(value="both")
        _bind_cfg("p6.event_source", self.p6_event_source_var)
        ttk.Combobox(row, textvariable=self.p6_event_source_var,
                     values=["both", "event-in", "event-out"],
                     state="readonly", width=14, font=F_MAIN).grid(
            row=0, column=4, padx=4)
        Label(row, text="both=vào+ra  ·  event-in=vào  ·  event-out=ra",
              bg=BG, fg=DIM, font=("Segoe UI", 8)).grid(
            row=0, column=5, sticky=W, padx=(4, 0))

        # Advanced (collapsible)
        self._p6_adv_open = False
        self._p6_adv_lbl = Label(f, text="▶ Nâng cao (API / MinIO / Token)",
                                  font=("Segoe UI", 8, "underline"),
                                  fg=ACCENT2, bg=BG, cursor="hand2")
        self._p6_adv_lbl.pack(anchor=W, pady=(10, 0))
        self._p6_adv_lbl.bind("<Button-1>", lambda _: self._toggle_adv("p6"))
        self._p6_adv_frm = Frame(f, bg=CARD, padx=8, pady=6)
        for i, (lbl, attr, default, width, show) in enumerate([
            ("API URL:",        "p6_api",  _P6_API_URL,       38, ""),
            ("MinIO endpoint:", "p6_mep",  _P6_MINIO_EP,      28, ""),
            ("MinIO bucket:",   "p6_mbk",  _P6_MINIO_BUCKET,  20, ""),
            ("MinIO AK:",       "p6_mak",  _P6_MINIO_AK,      16, ""),
            ("MinIO SK:",       "p6_msk",  _P6_MINIO_SK,      20, "*"),
        ]):
            r, c = divmod(i, 2)
            Label(self._p6_adv_frm, text=lbl, font=("Segoe UI", 8),
                  bg=CARD, fg=DIM).grid(
                row=r, column=c * 2, padx=(0 if c == 0 else 16, 4), pady=2, sticky=W)
            var = StringVar(value=default)
            setattr(self, attr, var)
            _bind_cfg(f"p6.cfg_{attr[3:]}", var)
            Entry(self._p6_adv_frm, textvariable=var, width=width, show=show,
                  bg="#16162a", fg=TEXT, insertbackground=TEXT,
                  relief="flat", font=F_MAIN, bd=4).grid(
                row=r, column=c * 2 + 1, padx=(0, 4), pady=2)
        tr = (len([0, 0, 0, 0, 0]) + 1) // 2   # row after 5 items → row 3
        Label(self._p6_adv_frm, text="Bearer Token:", font=("Segoe UI", 8),
              bg=CARD, fg=DIM).grid(
            row=tr, column=0, padx=(0, 4), pady=(8, 2), sticky=W)
        self.p6_token = StringVar(value="")
        _bind_cfg("p6.cfg_token", self.p6_token)
        Entry(self._p6_adv_frm, textvariable=self.p6_token, width=60,
              bg="#16162a", fg="#4fc3f7", insertbackground=TEXT,
              relief="flat", font=F_MAIN, bd=4).grid(
            row=tr, column=1, columnspan=3, padx=(0, 4), pady=(8, 2), sticky=EW)
        Label(self._p6_adv_frm,
              text="Chỉ nhập chuỗi token, không cần 'Bearer ' prefix",
              font=("Segoe UI", 7), fg=DIM, bg=CARD).grid(
            row=tr + 1, column=0, columnspan=4, sticky=W, pady=(0, 2))

    def _toggle_adv(self, src: str):
        lbl_attr = f"_{src}_adv_lbl"
        frm_attr = f"_{src}_adv_frm"
        open_attr = f"_{src}_adv_open"
        lbl = getattr(self, lbl_attr)
        frm = getattr(self, frm_attr)
        is_open = getattr(self, open_attr)
        if is_open:
            frm.pack_forget()
            lbl.config(text=lbl.cget("text").replace("▼", "▶"))
        else:
            frm.pack(fill=X, pady=(2, 4))
            lbl.config(text=lbl.cget("text").replace("▶", "▼"))
        setattr(self, open_attr, not is_open)

    # ── controls ──────────────────────────────────────────────────────────────

    def _build_controls(self, p):
        f = Frame(p, bg=BG, padx=10, pady=6)
        f.pack(fill=X)
        self.start_btn = Button(
            f, text="▶  Bắt đầu", command=self._start,
            bg=ACCENT, fg="white", font=F_BOLD,
            activebackground="#c04010", activeforeground="white",
            relief="flat", padx=22, pady=7, cursor="hand2")
        self.start_btn.pack(side=LEFT, padx=(0, 6))
        self.stop_btn = Button(
            f, text="⬛  Dừng", command=self._stop,
            bg=DIM, fg=BG, font=F_BOLD, relief="flat",
            padx=22, pady=7, state=DISABLED, cursor="hand2")
        self.stop_btn.pack(side=LEFT, padx=(0, 6))
        self.pause_btn = Button(
            f, text="⏸  Tạm dừng", command=self._toggle_pause,
            bg=CARD, fg=TEXT, font=F_BOLD,
            activebackground=ACCENT2, activeforeground="white",
            relief="flat", padx=16, pady=7, state=DISABLED, cursor="hand2")
        self.pause_btn.pack(side=LEFT, padx=(0, 6))
        self.retry_btn = Button(
            f, text="↺  Thử lại lỗi", command=self._retry_failed,
            bg=CARD, fg=TEXT, font=F_BOLD,
            activebackground=ACCENT, activeforeground="white",
            relief="flat", padx=16, pady=7, state=DISABLED, cursor="hand2")
        self.retry_btn.pack(side=LEFT, padx=(0, 6))
        Button(f, text="Thống kê", command=self._show_stats,
               bg=ACCENT2, fg="white", font=F_BOLD,
               activebackground="#5a4fa0", activeforeground="white",
               relief="flat", padx=18, pady=7, cursor="hand2").pack(side=LEFT, padx=(0, 16))
        self.collect_bad_var = BooleanVar(value=False)
        _bind_cfg("ip.collect_bad", self.collect_bad_var)
        Checkbutton(f, text="Lấy ảnh xấu", variable=self.collect_bad_var,
                    bg=BG, fg=TEXT, selectcolor="#251C53",
                    activebackground=BG, font=F_MAIN, cursor="hand2").pack(
            side=LEFT, padx=(0, 4))
        Button(f, text="Xem ảnh xấu", command=self._show_bad_images,
               bg=ACCENT2, fg="white", font=F_MAIN,
               activebackground="#5a4fa0", activeforeground="white",
               relief="flat", padx=10, pady=4, cursor="hand2").pack(
            side=LEFT, padx=(0, 4))
        Button(f, text="Tổng hợp", command=self._consolidate,
               bg="#251C53", fg="white", font=F_MAIN,
               activebackground=ACCENT2, activeforeground="white",
               relief="flat", padx=10, pady=4, cursor="hand2").pack(
            side=LEFT, padx=(0, 4))
        Button(f, text="Hiệu chỉnh", command=self._migrate_folder,
               bg="#2d4a1e", fg="#a0d080", font=F_MAIN,
               activebackground="#3a6028", activeforeground="white",
               relief="flat", padx=10, pady=4, cursor="hand2").pack(
            side=LEFT, padx=(0, 4))
        self.status_lbl = Label(f, text="Sẵn sàng", font=F_MAIN,
                                fg=ACCENT2, bg=BG)
        self.status_lbl.pack(side=RIGHT)

    # ── progress ──────────────────────────────────────────────────────────────

    def _build_progress(self, p):
        f = Frame(p, bg=BG, padx=10, pady=2)
        f.pack(fill=X)
        self._sep(f, "Tiến độ")
        pbar_row = Frame(f, bg=BG)
        pbar_row.pack(fill=X)
        self.pbar = ttk.Progressbar(pbar_row, mode="determinate",
                                    style="K.Horizontal.TProgressbar", maximum=100)
        self.pbar.pack(side=LEFT, fill=X, expand=True, padx=(0, 8))
        self.pct_lbl = Label(pbar_row, text="0%", font=F_MONO,
                             fg=ACCENT, bg=BG, width=5, anchor=E)
        self.pct_lbl.pack(side=LEFT)
        self.eta_lbl = Label(pbar_row, text="ETA: --:--", font=F_MONO,
                             fg=DIM, bg=BG, width=12, anchor=W)
        self.eta_lbl.pack(side=LEFT, padx=(6, 0))
        self.item_lbl = Label(f, text="", font=F_MONO, fg=DIM, bg=BG, anchor=W)
        self.item_lbl.pack(fill=X, pady=(2, 0))
        self.stat_lbl = Label(
            f,
            text="Trang: 0  |  SK: 0  |  Tìm: 0  |  Lưu: 0  |  Bỏ: 0  |  Lỗi: 0",
            font=F_MONO, fg=TEXT, bg=BG)
        self.stat_lbl.pack(anchor=W, pady=(2, 0))

    def _build_dashboard(self, p):
        self._dash_frame   = Frame(p, bg=CARD, padx=10, pady=6)
        self._dash_visible = False

    def _build_log(self, p):
        f = Frame(p, bg=BG, padx=10, pady=4)
        f.pack(fill=BOTH, expand=True)
        self._sep(f, "Nhật ký")
        inner = Frame(f, bg=BG)
        inner.pack(fill=BOTH, expand=True)
        inner.columnconfigure(0, weight=1)
        inner.rowconfigure(0, weight=1)
        self.log_txt = Text(inner, height=12, font=F_MONO,
                            bg="#16162a", fg="#d4d4d4",
                            relief="flat", wrap=WORD,
                            insertbackground="#d4d4d4", state=DISABLED)
        self.log_txt.grid(row=0, column=0, sticky=NSEW)
        for i, color in enumerate(_THREAD_COLORS, 1):
            self.log_txt.tag_configure(f"T{i}", foreground=color)
        sb = ttk.Scrollbar(inner, command=self.log_txt.yview)
        sb.grid(row=0, column=1, sticky=NS)
        self.log_txt["yscrollcommand"] = sb.set
        Button(inner, text="Xóa log",
               command=lambda: (self.log_txt.configure(state=NORMAL),
                                self.log_txt.delete("1.0", END),
                                self.log_txt.configure(state=DISABLED)),
               bg=CARD, fg=DIM, font=F_MAIN, relief="flat",
               padx=8, cursor="hand2").grid(row=1, column=0, sticky=W, pady=(4, 0))

    # ── source switch ─────────────────────────────────────────────────────────

    def _on_source_change(self, *_):
        src = self.source_var.get()
        for frm in (self._lotte_frm, self._p8_frm, self._p6_frm):
            frm.pack_forget()
        if src == "LotteImage":
            self._lotte_frm.pack(fill=X)
            self._src_desc_lbl.config(
                text="iParking Lotte · phân loại theo từ khóa · không có ảnh cắt biển số")
            self._time_hint_lbl.config(text="UTC  ·  Việt Nam = UTC+7")
            self._struct_lbl.config(
                text="Cấu trúc thư mục: <out>/<làn>/toan_canh_o_to|toan_canh_xe_may|o_to|xe_may|xe_dap/<YYYY-MM-DD>/<HH>/HHmmss_BSX.jpg")
        elif src == "Parkingv8":
            self._p8_frm.pack(fill=X)
            self._src_desc_lbl.config(
                text="iParking v8 · vehicleType integer · có ảnh cắt biển số (*_bsx_cut)")
            self._time_hint_lbl.config(text="UTC  ·  Việt Nam = UTC+7")
            self._struct_lbl.config(
                text="Cấu trúc thư mục: <out>/<làn>/toan_canh_o_to|o_to|o_to_bsx_cut|xe_may|…/<YYYY-MM-DD>/<HH>/HHmmss_BSX_type.jpg")
        elif src == "Parkingv6":
            self._p6_frm.pack(fill=X)
            self._src_desc_lbl.config(
                text="iParking v6 · vehicleType integer · MinIO · Bearer token")
            self._time_hint_lbl.config(text="UTC  ·  Việt Nam = UTC+7  (API nhận UTC)")
            self._struct_lbl.config(
                text="Cấu trúc thư mục: <out>/<làn>/toan_canh_o_to|o_to|o_to_bsx_cut|xe_may|…/<YYYY-MM-DD>/<HH>/HHmmss_BSX.jpg")

    # ── actions ───────────────────────────────────────────────────────────────

    def _browse(self):
        d = filedialog.askdirectory(title="Chọn thư mục lưu ảnh",
                                    initialdir=_cfg_dir("ip.out"))
        if d:
            self.out_var.set(d)
            _push_history("h.ip.out", d)
            self._out_combo["values"] = _get_history("h.ip.out")

    def _open_out(self):
        p = self.out_var.get().strip()
        if p and os.path.isdir(p):
            os.startfile(p)

    def _toggle_pause(self):
        if not self._running:
            return
        if self._paused:
            self._paused = False
            self._pause_event.set()
            self.pause_btn.config(text="⏸  Tạm dừng", fg=TEXT)
            self.status_lbl.config(text="Đang chạy...", fg=ACCENT)
            self._log("Tiếp tục...")
        else:
            self._paused = True
            self._pause_event.clear()
            self.pause_btn.config(text="▶  Tiếp tục", fg=ACCENT)
            self.status_lbl.config(text="Tạm dừng", fg="#ffaa00")
            self._log("Tạm dừng — đang chờ item hiện tại hoàn tất...")

    def _stop(self):
        if self._worker:
            self._worker.stop()
        for w in self._parallel_workers:
            w.stop()
        self._running = False
        self._paused  = False
        self._pause_event.set()
        self.stop_btn.config(state=DISABLED)
        self.pause_btn.config(state=DISABLED, text="⏸  Tạm dừng", fg=TEXT)
        self.start_btn.config(state=NORMAL)
        self.pbar.config(value=0)
        self.pct_lbl.config(text="0%")
        self.eta_lbl.config(text="ETA: --:--")
        self.item_lbl.config(text="")
        self.status_lbl.config(text="Đã dừng", fg=DIM)

    def _on_done(self):
        if not self._running:
            return
        self._running = False
        self._paused  = False
        self._pause_event.set()
        self.pbar.config(value=100)
        self.pct_lbl.config(text="100%")
        self.eta_lbl.config(text="ETA: 00:00")
        self.item_lbl.config(text="")
        self.start_btn.config(state=NORMAL)
        self.stop_btn.config(state=DISABLED)
        self.pause_btn.config(state=DISABLED, text="⏸  Tạm dừng", fg=TEXT)
        self.status_lbl.config(text="Hoàn thành", fg=ACCENT2)
        if self._failed_items:
            self.retry_btn.config(state=NORMAL,
                                   text=f"↺  Thử lại {len(self._failed_items)} lỗi")
        self._show_dashboard(self._last_stat)

    def _retry_failed(self):
        if not self._failed_items or self._running:
            if self._running:
                messagebox.showwarning("Đang chạy",
                                       "Vui lòng chờ lần chạy hiện tại kết thúc.")
            return
        items = list(self._failed_items)
        self._failed_items.clear()
        self.retry_btn.config(state=DISABLED)
        self._hide_dashboard()
        cfg = self._last_cfg.copy()
        cfg["retry_items"] = items
        self._prepare_run()
        self._log(f"Thử lại {len(items)} ảnh lỗi...")
        src = self._last_source
        if src == "LotteImage":
            self._worker = LotteWorker(cfg, self._log_q, self._stat_q,
                                       pause_event=self._pause_event)
        elif src == "Parkingv8":
            self._worker = Parkingv8Worker(cfg, self._log_q, self._stat_q,
                                           pause_event=self._pause_event)
        elif src == "Parkingv6":
            self._worker = Parkingv6Worker(cfg, self._log_q, self._stat_q,
                                           pause_event=self._pause_event)
        else:
            return
        self._thread = threading.Thread(target=self._run_worker, daemon=True)
        self._thread.start()

    def _show_bad_images(self):
        out = Path(self.out_var.get().strip())
        src = self.source_var.get()
        bad_path = out if src == "Parkingv8" else out / "bad"
        if hasattr(self, "_bad_win") and self._bad_win.winfo_exists():
            self._bad_win.lift()
            return
        self._bad_win = BadImageViewer(self.root, bad_path)

    def _consolidate(self):
        from .lotte_consolidate import ConsolidateWindow
        out = Path(self.out_var.get().strip())
        if not out.exists():
            messagebox.showerror("Lỗi", "Thư mục không tồn tại."); return
        if hasattr(self, "_consolidate_win") and self._consolidate_win.winfo_exists():
            self._consolidate_win.lift(); return
        self._consolidate_win = ConsolidateWindow(self.root, out)

    def _migrate_folder(self):
        out = Path(self.out_var.get().strip())
        if not out.exists():
            messagebox.showerror("Lỗi", "Thư mục không tồn tại."); return
        if hasattr(self, "_migrate_win") and self._migrate_win.winfo_exists():
            self._migrate_win.lift(); return
        self._migrate_win = _open_migrate_window(self.root, out)

    # ── start dispatch ────────────────────────────────────────────────────────

    def _prepare_run(self):
        self._clear_queues()
        self._all_thread_stats.clear()
        self._parallel_workers.clear()
        self._running = True
        self._paused  = False
        self._pause_event.set()
        self._run_start_time = time.monotonic()
        self.start_btn.config(state=DISABLED)
        self.stop_btn.config(state=NORMAL)
        self.pause_btn.config(state=NORMAL, text="⏸  Tạm dừng", fg=TEXT)
        self.retry_btn.config(state=DISABLED)
        self.pbar.config(value=0)
        self.pct_lbl.config(text="0%")
        self.eta_lbl.config(text="ETA: --:--")
        self.item_lbl.config(text="")
        self.status_lbl.config(text="Đang chạy...", fg=ACCENT)

    def _clear_queues(self):
        for _q in (self._log_q, self._stat_q):
            while True:
                try: _q.get_nowait()
                except queue.Empty: break

    def _get_common_cfg(self):
        return {
            "output_dir":    self.out_var.get().strip(),
            "page_size":     self.page_size_var.get(),
            "max_pages":     self.max_pages_var.get(),
            "sleep":         self.sleep_var.get(),
            "max_per_lane":  self.max_per_lane_var.get(),
            "max_per_cat":   self.max_per_cat_var.get(),
            "max_per_hour":  self.max_per_hour_var.get(),
            "collect_bad":   self.collect_bad_var.get(),
        }

    def _start(self):
        if not _REQUESTS_OK:
            messagebox.showerror("Thiếu thư viện",
                                 "Vui lòng cài:\n  pip install requests"); return
        if not _CV2_OK:
            messagebox.showerror("Thiếu thư viện",
                                 "Vui lòng cài:\n  pip install opencv-python numpy"); return
        from_d = self.from_var.get().strip()
        to_d   = self.to_var.get().strip()
        out    = self.out_var.get().strip()
        if not from_d or not to_d or not out:
            messagebox.showerror("Thiếu thông tin",
                                 "Vui lòng điền đủ thời gian và thư mục."); return
        try:
            os.makedirs(out, exist_ok=True)
        except Exception as e:
            messagebox.showerror("Lỗi thư mục", str(e)); return
        src = self.source_var.get()
        self._last_source = src
        self._failed_items.clear()
        self._hide_dashboard()
        self._prepare_run()
        if src == "LotteImage":
            self._start_lotte(from_d, to_d, out)
        elif src == "Parkingv8":
            self._start_p8(from_d, to_d, out)
        elif src == "Parkingv6":
            self._start_p6(from_d, to_d, out)

    def _start_lotte(self, from_d, to_d, out):
        from_t = from_d.replace(" ", "T")
        to_t   = to_d.replace(" ", "T")
        cfg = self._get_common_cfg()
        cfg.update({
            "from_date":    from_t,
            "to_date":      to_t,
            "use_minio":    self.l_use_minio.get(),
            "parallel":     self.parallel_var.get(),
            "api_base":     self.l_api.get().strip(),
            "username":     self.l_user.get().strip(),
            "password":     self.l_pass.get().strip(),
            "minio_ep":     self.l_mep.get().strip(),
            "minio_bucket": self.l_mbk.get().strip(),
            "minio_ak":     self.l_mak.get().strip(),
            "minio_sk":     self.l_msk.get().strip(),
            "kw_toan_canh": self.l_kw_toan_canh.get().strip(),
            "kw_xe_may":    self.l_kw_xe_may.get().strip(),
            "kw_xe_dap":    self.l_kw_xe_dap.get().strip(),
            "kw_o_to":      self.l_kw_o_to.get().strip(),
        })
        self._last_cfg = cfg
        self._log(f"[Lotte] Bắt đầu: {from_t}  →  {to_t}")
        self._log(f"Lưu vào: {out}  |  MinIO: {cfg['use_minio']}  |  Luồng: {cfg['parallel']}")
        n = cfg.get("parallel", 1)
        if n > 1:
            self._thread = threading.Thread(
                target=self._run_parallel_lotte, args=(cfg, n), daemon=True)
        else:
            self._worker = LotteWorker(cfg, self._log_q, self._stat_q,
                                       pause_event=self._pause_event)
            self._thread = threading.Thread(target=self._run_worker, daemon=True)
        self._thread.start()

    def _start_p8(self, from_d, to_d, out):
        cfg = self._get_common_cfg()
        cfg.update({
            "from_date":     from_d,
            "to_date":       to_d,
            "event_source":  self.p8_source_var.get(),
            "grant_type":    self.p8_grant_var.get(),
            "login_url":     self.p8_login_url.get().strip(),
            "api_url":       self.p8_api_url.get().strip(),
            "client_id":     self.p8_client_id.get().strip(),
            "client_secret": self.p8_client_secret.get().strip(),
            "username":      self.p8_user.get().strip(),
            "password":      self.p8_pass.get().strip(),
        })
        n = self.parallel_var.get()
        cfg.update({"parallel": n})
        self._last_cfg = cfg
        self._log(f"[Parkingv8] Bắt đầu: {from_d}  →  {to_d}")
        self._log(f"Nguồn: {cfg['event_source']}  |  Grant: {cfg['grant_type']}  |  Luồng: {n}  |  Lưu: {out}")
        if n > 1:
            self._thread = threading.Thread(
                target=self._run_parallel_p8, args=(cfg, n), daemon=True)
        else:
            self._worker = Parkingv8Worker(cfg, self._log_q, self._stat_q,
                                           pause_event=self._pause_event)
            self._thread = threading.Thread(target=self._run_worker, daemon=True)
        self._thread.start()

    def _start_p6(self, from_d, to_d, out):
        token = self.p6_token.get().strip()
        if not token:
            messagebox.showerror("Thiếu token",
                                 "Vui lòng nhập Bearer Token trong phần Nâng cao.")
            self._on_done_reset()
            return
        from_t = from_d.replace(" ", "T")
        to_t   = to_d.replace(" ", "T")
        cfg = self._get_common_cfg()
        cfg.update({
            "from_date":    from_t,
            "to_date":      to_t,
            "use_minio":    self.p6_use_minio.get(),
            "parallel":     self.parallel_var.get(),
            "event_source": self.p6_event_source_var.get(),
            "api_url":      self.p6_api.get().strip(),
            "token":        token,
            "minio_ep":     self.p6_mep.get().strip(),
            "minio_bucket": self.p6_mbk.get().strip(),
            "minio_ak":     self.p6_mak.get().strip(),
            "minio_sk":     self.p6_msk.get().strip(),
        })
        self._last_cfg = cfg
        self._log(f"[Parkingv6] Bắt đầu: {from_t}  →  {to_t}")
        self._log(f"Nguồn: {cfg['event_source']}  |  MinIO: {cfg['use_minio']}  |  Lưu: {out}")
        n = cfg.get("parallel", 1)
        if n > 1:
            self._thread = threading.Thread(
                target=self._run_parallel_p6, args=(cfg, n), daemon=True)
        else:
            self._worker = Parkingv6Worker(cfg, self._log_q, self._stat_q,
                                           pause_event=self._pause_event)
            self._thread = threading.Thread(target=self._run_worker, daemon=True)
        self._thread.start()

    def _on_done_reset(self):
        self._running = False
        self.start_btn.config(state=NORMAL)
        self.stop_btn.config(state=DISABLED)
        self.pause_btn.config(state=DISABLED)
        self.status_lbl.config(text="Sẵn sàng", fg=ACCENT2)

    def _run_worker(self):
        try:
            self._worker.run()
        except Exception as exc:
            self._log_q.put(f"[LỖI] {exc}")
            self._log_q.put("__DONE__")

    def _run_parallel_lotte(self, cfg, n):
        try:
            out    = Path(cfg["output_dir"])
            from_d = cfg["from_date"]
            to_d   = cfg["to_date"]
            all_days  = LotteWorker._day_list(from_d, to_d)
            done_days = set()
            hist_f = out / LotteWorker._HISTORY_FILE
            try:
                if hist_f.exists():
                    done_days = set(json.loads(hist_f.read_text(encoding="utf-8")))
                    self._log_q.put(f"Lịch sử: {len(done_days)} ngày đã tải trước đó.")
            except Exception:
                pass
            pending = [d for d in all_days if d[2] not in done_days]
            skipped = len(all_days) - len(pending)
            self._log_q.put(
                f"Tổng: {len(all_days)} ngày | {n} luồng | page_size={cfg['page_size']}")
            if skipped:
                self._log_q.put(f"Bỏ qua {skipped} ngày đã tải.")
            if not pending:
                self._log_q.put("Tất cả ngày đã tải. Không có việc gì.")
                self._log_q.put("__DONE__"); return
            groups = [[] for _ in range(n)]
            for i, day in enumerate(pending):
                groups[i % n].append(day)
            for tid, g in enumerate(groups, 1):
                if g:
                    self._log_q.put(
                        f"[T{tid}] Được giao {len(g)} ngày: {g[0][2]} → {g[-1][2]}")
            shared = _SharedLaneState()
            workers = []
            for tid, day_group in enumerate(groups, 1):
                if not day_group:
                    continue
                w = LotteWorker(cfg, self._log_q, self._stat_q,
                                pause_event=self._pause_event,
                                thread_id=tid, days_list=day_group,
                                shared=shared, send_done=False,
                                global_total_days=len(pending))
                workers.append(w)
            self._parallel_workers = workers
            threads = [threading.Thread(target=w.run, daemon=True) for w in workers]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            total = {k: sum(w.stats.get(k, 0) for w in workers)
                     for k in ("event", "found", "saved", "skipped", "error", "bad_saved")}
            sep = "═" * 52
            self._log_q.put(f"\n{sep}")
            self._log_q.put(
                f"TỔNG KẾT ({n} luồng, {len(pending)} ngày): "
                f"SK:{total['event']}  Tìm:{total['found']}  Lưu:{total['saved']}  "
                f"Xấu:{total['bad_saved']}  Bỏ:{total['skipped']}  Lỗi:{total['error']}")
            self._log_q.put(sep)
        except Exception as exc:
            self._log_q.put(f"[LỖI] {exc}")
        finally:
            self._log_q.put("__DONE__")

    def _run_parallel_p6(self, cfg, n):
        try:
            out    = Path(cfg["output_dir"])
            from_d = cfg["from_date"]
            to_d   = cfg["to_date"]
            all_days  = Parkingv6Worker._day_list(from_d, to_d)
            done_days = set()
            hist_f = out / Parkingv6Worker._HISTORY_FILE
            try:
                if hist_f.exists():
                    done_days = set(json.loads(hist_f.read_text(encoding="utf-8")))
                    self._log_q.put(f"Lịch sử: {len(done_days)} ngày đã tải trước đó.")
            except Exception:
                pass
            pending = [d for d in all_days if d[2] not in done_days]
            skipped = len(all_days) - len(pending)
            self._log_q.put(
                f"Tổng: {len(all_days)} ngày | {n} luồng | page_size={cfg['page_size']}")
            if skipped:
                self._log_q.put(f"Bỏ qua {skipped} ngày đã tải.")
            if not pending:
                self._log_q.put("Tất cả ngày đã tải. Không có việc gì.")
                self._log_q.put("__DONE__"); return
            groups = [[] for _ in range(n)]
            for i, day in enumerate(pending):
                groups[i % n].append(day)
            for tid, g in enumerate(groups, 1):
                if g:
                    self._log_q.put(
                        f"[T{tid}] Được giao {len(g)} ngày: {g[0][2]} → {g[-1][2]}")
            shared = _P6SharedLaneState()
            workers = []
            for tid, day_group in enumerate(groups, 1):
                if not day_group:
                    continue
                w = Parkingv6Worker(cfg, self._log_q, self._stat_q,
                                    pause_event=self._pause_event,
                                    thread_id=tid, days_list=day_group,
                                    shared=shared, send_done=False,
                                    global_total_days=len(pending))
                workers.append(w)
            self._parallel_workers = workers
            threads = [threading.Thread(target=w.run, daemon=True) for w in workers]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            total = {k: sum(w.stats.get(k, 0) for w in workers)
                     for k in ("event", "found", "saved", "skipped", "error", "bad_saved")}
            sep = "═" * 52
            self._log_q.put(f"\n{sep}")
            self._log_q.put(
                f"TỔNG KẾT ({n} luồng, {len(pending)} ngày): "
                f"SK:{total['event']}  Tìm:{total['found']}  Lưu:{total['saved']}  "
                f"Xấu:{total['bad_saved']}  Bỏ:{total['skipped']}  Lỗi:{total['error']}")
            self._log_q.put(sep)
        except Exception as exc:
            self._log_q.put(f"[LỖI] {exc}")
        finally:
            self._log_q.put("__DONE__")

    def _run_parallel_p8(self, cfg, n):
        try:
            from .parkingv8_image import _P8SharedLaneState
            out    = Path(cfg["output_dir"])
            from_d = cfg["from_date"]
            to_d   = cfg["to_date"]
            all_days  = Parkingv8Worker._day_list(from_d, to_d)
            done_days = set()
            hist_f = out / Parkingv8Worker._HISTORY_FILE
            try:
                if hist_f.exists():
                    done_days = set(json.loads(hist_f.read_text(encoding="utf-8")))
                    self._log_q.put(f"Lịch sử: {len(done_days)} ngày đã tải trước đó.")
            except Exception:
                pass
            pending = [d for d in all_days if d[2] not in done_days]
            skipped = len(all_days) - len(pending)
            self._log_q.put(
                f"Tổng: {len(all_days)} ngày | {n} luồng | page_size={cfg['page_size']}")
            if skipped:
                self._log_q.put(f"Bỏ qua {skipped} ngày đã tải.")
            if not pending:
                self._log_q.put("Tất cả ngày đã tải. Không có việc gì.")
                self._log_q.put("__DONE__"); return
            groups = [[] for _ in range(n)]
            for i, day in enumerate(pending):
                groups[i % n].append(day)
            for tid, g in enumerate(groups, 1):
                if g:
                    self._log_q.put(
                        f"[T{tid}] Được giao {len(g)} ngày: {g[0][2]} → {g[-1][2]}")
            shared = _P8SharedLaneState()
            workers = []
            for tid, day_group in enumerate(groups, 1):
                if not day_group:
                    continue
                w = Parkingv8Worker(cfg, self._log_q, self._stat_q,
                                    pause_event=self._pause_event,
                                    thread_id=tid, days_list=day_group,
                                    shared=shared, send_done=False,
                                    global_total_days=len(pending))
                workers.append(w)
            self._parallel_workers = workers
            threads = [threading.Thread(target=w.run, daemon=True) for w in workers]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            total = {k: sum(w.stats.get(k, 0) for w in workers)
                     for k in ("event", "found", "saved", "skipped", "error", "bad_saved")}
            sep = "═" * 52
            self._log_q.put(f"\n{sep}")
            self._log_q.put(
                f"TỔNG KẾT ({n} luồng, {len(pending)} ngày): "
                f"SK:{total['event']}  Tìm:{total['found']}  Lưu:{total['saved']}  "
                f"Xấu:{total['bad_saved']}  Bỏ:{total['skipped']}  Lỗi:{total['error']}")
            self._log_q.put(sep)
        except Exception as exc:
            self._log_q.put(f"[LỖI] {exc}")
        finally:
            self._log_q.put("__DONE__")

    # ── polling ───────────────────────────────────────────────────────────────

    def _poll(self):
        try:
            while True:
                msg = self._log_q.get_nowait()
                if msg == "__DONE__":
                    self._on_done()
                else:
                    self._log(msg)
        except queue.Empty:
            pass
        try:
            while True:
                s = self._stat_q.get_nowait()
                tid = s.get("thread_id", 0)
                if tid > 0:
                    self._all_thread_stats[tid] = s
                disp = self._aggregate_stats() if self._all_thread_stats else s
                self._last_stat = disp
                self._update_progress(disp)
                self._refresh_stat_lbl(disp)
        except queue.Empty:
            pass
        self.root.after(200, self._poll)

    def _aggregate_stats(self):
        all_s = list(self._all_thread_stats.values())
        total_days = all_s[0].get("total_days", 0) if all_s else 0
        items = [x.get("current_item", "") for x in all_s if x.get("current_item")]
        return {
            "event":      sum(x.get("event",     0) for x in all_s),
            "found":      sum(x.get("found",     0) for x in all_s),
            "saved":      sum(x.get("saved",     0) for x in all_s),
            "skipped":    sum(x.get("skipped",   0) for x in all_s),
            "error":      sum(x.get("error",     0) for x in all_s),
            "bad_saved":  sum(x.get("bad_saved", 0) for x in all_s),
            "page":       sum(x.get("page",      0) for x in all_s),
            "day_idx":    sum(x.get("day_idx",   0) for x in all_s),
            "total_days": total_days,
            "day_label":  "",
            "thread_id":  0,
            "current_item": " | ".join(
                f"T{x.get('thread_id','?')}:{v}" for x, v in zip(all_s, items)),
            "total_found": sum(x.get("total_found", x.get("found", 0)) for x in all_s),
            "_parallel":  len(all_s),
        }

    def _update_progress(self, s):
        saved = s.get("saved", 0)
        found = s.get("found", 0)
        total = s.get("total_found", found) or found
        item  = s.get("current_item", "")
        if item:
            self.item_lbl.config(text=f"Đang xử lý: {item}")
        failed = s.get("failed_items")
        if failed:
            for it in failed:
                if it not in self._failed_items:
                    self._failed_items.append(it)
        if total > 0:
            pct = min(int(saved * 100 / total), 99)
            self.pbar.config(value=pct)
            self.pct_lbl.config(text=f"{pct}%")
            elapsed = time.monotonic() - (self._run_start_time or time.monotonic())
            if saved > 0:
                eta = int(elapsed / saved * (total - saved))
                m, sec = divmod(eta, 60)
                self.eta_lbl.config(text=f"ETA: {m:02d}:{sec:02d}")
        elif s.get("page", 0) > 0:
            pct = min(s["page"] % 100, 99)
            self.pbar.config(value=pct)
            self.pct_lbl.config(text=f"~{pct}%")

    def _refresh_stat_lbl(self, s):
        n_threads  = s.get("_parallel", 0)
        day_idx    = s.get("day_idx", 0)
        total_days = s.get("total_days", 0)
        bad_part   = f"  |  Xấu: {s['bad_saved']}" if s.get("bad_saved") else ""
        if n_threads > 1:
            day_info = (f"[{n_threads} luồng] Ngày: {day_idx}/{total_days}  |  "
                        if total_days else f"[{n_threads} luồng]  ")
        elif total_days:
            day_info = f"Ngày: {s.get('day_label','')} ({day_idx}/{total_days})  |  "
        else:
            day_info = ""
        self.stat_lbl.config(
            text=(f"{day_info}"
                  f"Trang: {s.get('page',0)}  |  "
                  f"SK: {s.get('event',0)}  |  "
                  f"Tìm: {s.get('found',0)}  |  "
                  f"Lưu: {s.get('saved',0)}"
                  f"{bad_part}  |  "
                  f"Bỏ: {s.get('skipped',0)}  |  "
                  f"Lỗi: {s.get('error',0)}"))

    def _log(self, msg):
        import re as _re
        self.log_txt.configure(state=NORMAL)
        ts   = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}\n"
        m = _re.match(r'\[T(\d+)\]', msg)
        if m:
            self.log_txt.insert(END, line, (f"T{m.group(1)}",))
        else:
            self.log_txt.insert(END, line)
        lines = int(self.log_txt.index("end-1c").split(".")[0])
        if lines > self._LOG_MAX:
            self.log_txt.delete("1.0", f"{lines - self._LOG_MAX}.0")
        self.log_txt.see(END)
        self.log_txt.configure(state=DISABLED)

    # ── dashboard ─────────────────────────────────────────────────────────────

    def _show_dashboard(self, s):
        if not self._dash_visible:
            self._dash_frame.pack(fill=X, padx=10, pady=(4, 2))
            self._dash_visible = True
        for w in self._dash_frame.winfo_children():
            w.destroy()
        Label(self._dash_frame, text="Kết quả lần chạy",
              font=("Segoe UI", 9, "bold"), fg=ACCENT2, bg=CARD).pack(anchor=W)
        row = Frame(self._dash_frame, bg=CARD)
        row.pack(fill=X, pady=(4, 0))
        for label, val, color in [
            ("Tổng SK",  s.get("event",    0), TEXT),
            ("Tìm thấy", s.get("found",    0), TEXT),
            ("Đã lưu",   s.get("saved",    0), "#4caf50"),
            ("Bỏ qua",   s.get("skipped",  0), DIM),
            ("Lỗi",      s.get("error",    0), "#ff8844"),
            ("Ảnh xấu",  s.get("bad_saved",0), ACCENT2),
        ]:
            cell = Frame(row, bg="#251C53", padx=8, pady=4)
            cell.pack(side=LEFT, padx=(0, 6))
            Label(cell, text=str(val), font=("Segoe UI Semibold", 13),
                  fg=color, bg="#251C53").pack()
            Label(cell, text=label, font=("Segoe UI", 8),
                  fg=DIM, bg="#251C53").pack()
        if self._failed_items:
            Label(self._dash_frame,
                  text=f"{len(self._failed_items)} ảnh lỗi — nhấn 'Thử lại lỗi' để tải lại",
                  font=("Segoe UI", 8), fg="#ff8844", bg=CARD).pack(
                anchor=W, pady=(4, 0))

    def _hide_dashboard(self):
        if self._dash_visible:
            self._dash_frame.pack_forget()
            self._dash_visible = False

    # ── statistics ────────────────────────────────────────────────────────────

    def _show_stats(self):
        out = Path(self.out_var.get().strip())
        if hasattr(self, "_stats_win") and self._stats_win.winfo_exists():
            self._stats_out = out
            self._stats_win.lift()
            self._stats_rebuild()
            return
        win = Toplevel(self.root)
        win.title("Thống kê ảnh đã lưu")
        win.configure(bg=BG)
        win.geometry("960x560")
        win.resizable(True, True)
        self._stats_win  = win
        self._stats_out  = out
        self._stats_view = StringVar(value="table")
        tb = Frame(win, bg=CARD, padx=10, pady=6)
        tb.pack(fill=X)
        Button(tb, text="Làm mới", command=self._stats_rebuild,
               bg=ACCENT, fg="white", font=F_MAIN,
               activebackground="#c04010", activeforeground="white",
               relief="flat", padx=14, pady=4, cursor="hand2").pack(side=LEFT)
        Frame(tb, bg=DIM, width=1).pack(side=LEFT, fill=Y, padx=14, pady=2)
        for lbl, val in [("Bảng", "table"), ("Biểu đồ", "chart")]:
            Radiobutton(tb, text=lbl, variable=self._stats_view, value=val,
                        bg=CARD, fg=TEXT, selectcolor="#251C53",
                        activebackground=CARD, font=F_MAIN, cursor="hand2",
                        command=self._stats_rebuild).pack(side=LEFT, padx=4)
        self._stats_body = Frame(win, bg=BG)
        self._stats_body.pack(fill=BOTH, expand=True)
        self._stats_rebuild()

    def _stats_rebuild(self):
        out = getattr(self, "_stats_out", Path(self.out_var.get().strip()))
        for w in self._stats_body.winfo_children():
            w.destroy()
        lbl = Label(self._stats_body, text="Đang quét...", bg=BG, fg=DIM, font=F_MAIN)
        lbl.pack(expand=True)
        self._stats_body.update()
        data = self._scan_stats(out)
        lbl.destroy()
        if not data["lt"]:
            Label(self._stats_body,
                  text=f"Không tìm thấy ảnh trong:\n{out}",
                  bg=BG, fg=DIM, font=F_MAIN, justify=CENTER).pack(expand=True)
            return
        s = ttk.Style()
        s.configure("S.Treeview", background="#1e1e2e", foreground="#d4d4d4",
                    fieldbackground="#1e1e2e", rowheight=24, font=F_MONO)
        s.configure("S.Treeview.Heading", background="#251C53", foreground="white",
                    font=("Segoe UI", 9, "bold"))
        s.map("S.Treeview", background=[("selected", "#4A3F8C")])
        nb = ttk.Notebook(self._stats_body)
        nb.pack(fill=BOTH, expand=True, padx=8, pady=8)
        is_chart = self._stats_view.get() == "chart"
        self._stats_tab_summary(nb, data, is_chart)
        self._stats_tab_date(nb,    data, is_chart)
        self._stats_tab_hour(nb,    data, is_chart)

    @staticmethod
    def _scan_stats(out_path):
        from collections import defaultdict
        lt  = defaultdict(lambda: defaultdict(int))
        bd  = defaultdict(lambda: defaultdict(int))
        bhl = defaultdict(lambda: defaultdict(int))
        if out_path.exists():
            for img in out_path.rglob("*.jpg"):
                try:
                    parts = img.relative_to(out_path).parts
                    if len(parts) == 5:
                        lane, vtype, date_s, hour_s, _ = parts
                    elif len(parts) == 4:
                        lane, vtype, date_s, fname = parts
                        hour_s = fname[:2]
                    else:
                        continue
                    if lane in ("bad",) or vtype in ("bad",):
                        continue
                except Exception:
                    continue
                lt[lane][vtype]  += 1
                bd[date_s][lane] += 1
                if hour_s.isdigit() and 0 <= int(hour_s) <= 23:
                    bhl[int(hour_s)][lane] += 1
        return {"lt": dict(lt), "date": dict(bd), "hour": dict(bhl)}

    @staticmethod
    def _make_tree(parent, cols, col_widths, anchor_first="w"):
        f = Frame(parent, bg=BG)
        f.pack(fill=BOTH, expand=True, padx=4, pady=4)
        f.columnconfigure(0, weight=1)
        f.rowconfigure(0, weight=1)
        tree = ttk.Treeview(f, columns=cols, show="headings", style="S.Treeview")
        for i, (col, w) in enumerate(zip(cols, col_widths)):
            tree.heading(col, text=col)
            tree.column(col, width=w, minwidth=w,
                        anchor=anchor_first if i == 0 else "center")
        tree.tag_configure("total", background="#251C53", foreground="white")
        tree.tag_configure("odd",   background="#16162a")
        tree.tag_configure("even",  background="#1e1e2e")
        vsb = ttk.Scrollbar(f, orient=VERTICAL,   command=tree.yview)
        hsb = ttk.Scrollbar(f, orient=HORIZONTAL, command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        tree.grid(row=0, column=0, sticky=NSEW)
        vsb.grid(row=0, column=1, sticky=NS)
        hsb.grid(row=1, column=0, sticky=EW)
        return tree

    def _make_chart(self, parent, draw_fn):
        try:
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            fig = Figure(figsize=(9, 3.8), dpi=96, facecolor="#1e1e2e")
            ax  = fig.add_subplot(111, facecolor="#16162a")
            for spine in ax.spines.values():
                spine.set_color("#4A3F8C")
            ax.tick_params(colors="#d4d4d4", labelsize=8)
            draw_fn(ax)
            ax.legend(facecolor="#2a2a3e", edgecolor="#4A3F8C",
                      labelcolor="#d4d4d4", fontsize=8, loc="upper right")
            ax.grid(axis="y", color="#2a2a3e", linewidth=0.5, zorder=0)
            fig.tight_layout(pad=1.5)
            cv = FigureCanvasTkAgg(fig, parent)
            cv.draw()
            cv.get_tk_widget().pack(fill=BOTH, expand=True, padx=4, pady=4)
        except ImportError:
            Label(parent, text="Cần matplotlib:\n  pip install matplotlib",
                  bg=BG, fg=DIM, font=F_MAIN, justify=CENTER).pack(expand=True)

    def _stats_tab_summary(self, nb, data, is_chart):
        found_vtypes = {v for lane_d in data["lt"].values() for v in lane_d}
        vtypes = [v for v in _VTYPE_ORDER if v in found_vtypes]
        if not vtypes:
            vtypes = sorted(found_vtypes)
        lanes = sorted(data["lt"])
        tab = Frame(nb, bg=BG)
        nb.add(tab, text="  Làn × Loại xe  ")
        if not is_chart:
            cols   = ["Làn"] + vtypes + ["Tổng"]
            widths = [180] + [90] * len(vtypes) + [80]
            tree   = self._make_tree(tab, cols, widths)
            totals = {v: 0 for v in vtypes}
            grand  = 0
            for i, lane in enumerate(lanes):
                row, rt = [lane], 0
                for v in vtypes:
                    n = data["lt"][lane].get(v, 0)
                    row.append(str(n) if n else "-")
                    totals[v] += n; rt += n
                grand += rt
                row.append(str(rt))
                tree.insert("", END, values=row,
                            tags=("odd" if i % 2 else "even",))
            tree.insert("", END,
                        values=("TỔNG", *[str(totals[v]) for v in vtypes], str(grand)),
                        tags=("total",))
        else:
            def draw(ax):
                x = range(len(lanes))
                w = max(0.1, 0.8 / max(len(vtypes), 1))
                for i, vt in enumerate(vtypes):
                    vals = [data["lt"][l].get(vt, 0) for l in lanes]
                    clr  = _VTYPE_COLORS.get(vt, "#888888")
                    ax.bar([xi + i * w for xi in x], vals, w,
                           label=vt, color=clr, zorder=3)
                ax.set_xticks([xi + w * len(vtypes) / 2 for xi in x])
                ax.set_xticklabels(lanes, rotation=18, ha="right",
                                   fontsize=7, color="#d4d4d4")
                ax.set_title("Số ảnh theo làn và loại xe",
                             color="#d4d4d4", fontsize=10)
            self._make_chart(tab, draw)

    def _stats_tab_date(self, nb, data, is_chart):
        lanes = sorted({l for d in data["date"].values() for l in d})
        dates = sorted(data["date"])
        tab = Frame(nb, bg=BG)
        nb.add(tab, text="  Theo ngày  ")
        if not is_chart:
            cols   = ["Ngày", "Tổng"] + lanes
            widths = [110, 70] + [max(100, len(l) * 8) for l in lanes]
            tree   = self._make_tree(tab, cols, widths)
            grand  = {l: 0 for l in lanes}
            grand_t = 0
            for i, d in enumerate(dates):
                row_t = sum(data["date"][d].values())
                row = [d, str(row_t)]
                for l in lanes:
                    n = data["date"][d].get(l, 0)
                    row.append(str(n) if n else "-")
                    grand[l] += n
                grand_t += row_t
                tree.insert("", END, values=row,
                            tags=("odd" if i % 2 else "even",))
            tree.insert("", END,
                        values=("TỔNG", str(grand_t), *[str(grand[l]) for l in lanes]),
                        tags=("total",))
        else:
            def draw(ax):
                bottom = [0] * len(dates)
                for i, lane in enumerate(lanes):
                    vals = [data["date"][d].get(lane, 0) for d in dates]
                    clr  = _LANE_PALETTE[i % len(_LANE_PALETTE)]
                    ax.bar(dates, vals, bottom=bottom, label=lane, color=clr, zorder=3)
                    bottom = [b + v for b, v in zip(bottom, vals)]
                ax.set_xticklabels(dates, rotation=20, ha="right",
                                   fontsize=7, color="#d4d4d4")
                ax.set_title("Số ảnh theo ngày", color="#d4d4d4", fontsize=10)
            self._make_chart(tab, draw)

    def _stats_tab_hour(self, nb, data, is_chart):
        lanes = sorted({l for h in data["hour"].values() for l in h})
        tab = Frame(nb, bg=BG)
        nb.add(tab, text="  Theo giờ  ")
        if not is_chart:
            cols   = ["Giờ", "Tổng"] + lanes
            widths = [55, 70] + [max(100, len(l) * 8) for l in lanes]
            tree   = self._make_tree(tab, cols, widths, anchor_first="center")
            grand  = {l: 0 for l in lanes}
            grand_t = 0
            for i in range(24):
                row_t = sum(data["hour"].get(i, {}).values())
                row = [f"{i:02d}:00", str(row_t) if row_t else "-"]
                for l in lanes:
                    n = data["hour"].get(i, {}).get(l, 0)
                    row.append(str(n) if n else "-")
                    grand[l] += n
                grand_t += row_t
                tree.insert("", END, values=row,
                            tags=("odd" if i % 2 else "even",))
            tree.insert("", END,
                        values=("TỔNG", str(grand_t), *[str(grand[l]) for l in lanes]),
                        tags=("total",))
        else:
            def draw(ax):
                hrs = list(range(24))
                bottom = [0] * 24
                for i, lane in enumerate(lanes):
                    vals = [data["hour"].get(h, {}).get(lane, 0) for h in hrs]
                    clr  = _LANE_PALETTE[i % len(_LANE_PALETTE)]
                    ax.bar([f"{h:02d}" for h in hrs], vals,
                           bottom=bottom, label=lane, color=clr, zorder=3)
                    bottom = [b + v for b, v in zip(bottom, vals)]
                ax.set_xticklabels([f"{h:02d}" for h in hrs],
                                   fontsize=7, color="#d4d4d4")
                ax.set_title("Phân phối ảnh theo giờ",
                             color="#d4d4d4", fontsize=10)
            self._make_chart(tab, draw)
