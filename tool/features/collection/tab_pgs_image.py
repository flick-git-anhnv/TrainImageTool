"""Tab thu thập ảnh PGS — duyệt file-share theo cấu trúc thư mục ngày."""

import os
import queue
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from tkinter import *
from tkinter import filedialog, messagebox, ttk

from ...core.constants import (
    BG, CARD, ACCENT, ACCENT2, TEXT, DIM, F_MAIN, F_BOLD, F_MONO,
)
from ...core.settings import (
    _CFG, _cfg_save, _bind_cfg, _bind_history, _push_history, _get_history,
)
from ...core.ui_helpers import _make_logbox, _append_log
from .pgs_image import PgsImageWorker


class PgsImageTab(Frame):
    _LOG_MAX = 2000
    _POLL_MS = 200

    def __init__(self, master, root):
        super().__init__(master, bg=BG)
        self.root = root

        self._worker: PgsImageWorker | None = None
        self._thread:  threading.Thread | None = None
        self._log_q   = queue.Queue()
        self._stat_q  = queue.Queue()
        self._running = False
        self._paused  = False
        self._pause_event = threading.Event()
        self._pause_event.set()
        self._parallel_workers: list[PgsImageWorker] = []
        self._parallel_total  = 1
        self._parallel_done   = 0
        self._run_start       = 0.0

        # Consolidate state
        self._cons_thread:  threading.Thread | None = None
        self._cons_running: bool = False
        self._cons_stop     = threading.Event()

        # Dedup state
        self._dedup_thread:  threading.Thread | None = None
        self._dedup_running: bool = False
        self._dedup_stop     = threading.Event()

        # Camera list state: name → BooleanVar
        self._cam_vars: dict[str, BooleanVar] = {}
        self._cam_frame_inner: Frame | None = None
        self._cam_count_lbl:   Label | None = None

        self._build()
        self._poll()

    # ── separator helper ───────────────────────────────────────────────────────

    def _sep(self, parent, text: str):
        f = Frame(parent, bg=BG)
        f.pack(fill=X, pady=(10, 3))
        Label(f, text=text, font=("Segoe UI", 9, "bold"),
              fg=ACCENT2, bg=BG).pack(side=LEFT)
        Frame(f, bg=DIM, height=1).pack(side=LEFT, fill=X, expand=True,
                                        padx=(8, 0), pady=5)

    # ── layout ─────────────────────────────────────────────────────────────────

    def _build(self):
        # Header
        hdr = Frame(self, bg=CARD, padx=16, pady=10)
        hdr.pack(fill=X)
        Label(hdr, text="PGS Image — Thu thập ảnh từ hệ thống PGS (file-based / network share)",
              bg=CARD, fg=TEXT, font=F_BOLD).pack(side=LEFT)

        # Scrollable body
        canvas = Canvas(self, bg=BG, highlightthickness=0)
        vsb    = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=RIGHT, fill=Y)
        canvas.pack(side=LEFT, fill=BOTH, expand=True)

        inner = Frame(canvas, bg=BG)
        cw    = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _resize(e):
            canvas.itemconfig(cw, width=e.width)
        canvas.bind("<Configure>", _resize)
        inner.bind("<Configure>",
                   lambda _: canvas.configure(scrollregion=canvas.bbox("all")))

        _mw_entered = [False]
        def _mw(ev): canvas.yview_scroll(int(-1 * (ev.delta / 120)), "units")
        def _enter(_):
            _mw_entered[0] = True; canvas.bind_all("<MouseWheel>", _mw)
        def _leave(_):
            _mw_entered[0] = False
            canvas.after(20, lambda: canvas.unbind_all("<MouseWheel>") if not _mw_entered[0] else None)
        canvas.bind("<Enter>", _enter)
        canvas.bind("<Leave>", _leave)

        p = inner
        self._build_source(p)
        self._build_cameras(p)
        self._build_dates(p)
        self._build_types(p)
        self._build_limits(p)
        self._build_output(p)
        self._build_consolidate(p)
        self._build_dedup(p)
        self._build_controls(p)
        self._build_progress(p)
        self._build_log(p)

    # ── section: Source ────────────────────────────────────────────────────────

    def _build_source(self, p):
        f = Frame(p, bg=BG, padx=10, pady=2)
        f.pack(fill=X)
        self._sep(f, "Đường dẫn nguồn (PGS share)")

        row = Frame(f, bg=BG)
        row.pack(fill=X)
        row.columnconfigure(0, weight=1)

        self.src_var = StringVar(value=_CFG.get("pgs.source_path", ""))
        _bind_cfg("pgs.source_path", self.src_var)

        self._src_combo = ttk.Combobox(row, textvariable=self.src_var,
                                       style="Dark.TCombobox", font=F_MAIN)
        self._src_combo.grid(row=0, column=0, sticky=EW, padx=(0, 6))
        _bind_history("h.pgs.source_path", self._src_combo)

        Button(row, text="Chọn…", command=self._browse_source,
               bg=ACCENT2, fg="white", font=F_MAIN,
               activebackground=ACCENT, activeforeground="white",
               relief="flat", padx=10, cursor="hand2").grid(row=0, column=1, padx=(0, 4))

        Button(row, text="🔍 Khám phá camera", command=self._discover_cameras,
               bg=ACCENT, fg="white", font=F_MAIN,
               activebackground="#c0421a", activeforeground="white",
               relief="flat", padx=10, cursor="hand2").grid(row=0, column=2)

        Label(f, text=(
            "Ví dụ: \\\\192.168.1.1\\images\\images  "
            "|  Cấu trúc: <nguồn>\\<camera>\\<năm>\\<tháng>\\<ngày>\\"
        ), font=("Segoe UI", 8), fg=DIM, bg=BG, anchor=W).pack(fill=X, pady=(3, 0))

    # ── section: Camera list ────────────────────────────────────────────────────

    def _build_cameras(self, p):
        f = Frame(p, bg=BG, padx=10, pady=2)
        f.pack(fill=X)
        self._sep(f, "Danh sách camera")

        # Manual add row
        add_row = Frame(f, bg=BG)
        add_row.pack(fill=X, pady=(0, 4))
        add_row.columnconfigure(0, weight=1)

        self._cam_entry_var = StringVar()
        Entry(add_row, textvariable=self._cam_entry_var,
              bg=CARD, fg=TEXT, insertbackground=TEXT,
              relief="flat", font=F_MAIN, bd=4).grid(
            row=0, column=0, sticky=EW, padx=(0, 6))
        Label(add_row, text="(tên thư mục camera, VD: 192.168.16.2_1)",
              bg=BG, fg=DIM, font=("Segoe UI", 8)).grid(
            row=1, column=0, sticky=W, pady=(2, 0))

        Button(add_row, text="+ Thêm", command=self._add_camera,
               bg=ACCENT2, fg="white", font=F_MAIN,
               activebackground=ACCENT, activeforeground="white",
               relief="flat", padx=8, cursor="hand2").grid(
            row=0, column=1, padx=(0, 4))

        Button(add_row, text="✘ Xóa đã check", command=self._remove_cameras,
               bg=CARD, fg=DIM, font=F_MAIN,
               activebackground="#4a0000", activeforeground="white",
               relief="flat", padx=8, cursor="hand2").grid(row=0, column=2)

        # Select-all / none row
        sel_row = Frame(f, bg=BG)
        sel_row.pack(fill=X, pady=(0, 4))
        Button(sel_row, text="✔ Tất cả",
               command=lambda: [self._set_all_cameras(True)],
               bg=CARD, fg=TEXT, font=("Segoe UI", 8),
               relief="flat", padx=8, pady=2, cursor="hand2").pack(side=LEFT, padx=(0, 4))
        Button(sel_row, text="✘ Bỏ tất cả",
               command=lambda: [self._set_all_cameras(False)],
               bg=CARD, fg=DIM, font=("Segoe UI", 8),
               relief="flat", padx=8, pady=2, cursor="hand2").pack(side=LEFT)
        self._cam_count_lbl = Label(sel_row, text="(chưa có camera)",
                                    bg=BG, fg=DIM, font=("Segoe UI", 8))
        self._cam_count_lbl.pack(side=LEFT, padx=(12, 0))

        # Scrollable checkbox list
        outer = Frame(f, bg=CARD, relief="flat")
        outer.pack(fill=X)

        cam_canvas = Canvas(outer, bg=CARD, highlightthickness=0, height=140)
        cam_sb     = ttk.Scrollbar(outer, orient="vertical", command=cam_canvas.yview)
        cam_canvas.configure(yscrollcommand=cam_sb.set)
        cam_sb.pack(side=RIGHT, fill=Y)
        cam_canvas.pack(side=LEFT, fill=BOTH, expand=True)

        self._cam_frame_inner = Frame(cam_canvas, bg=CARD)
        cam_cw = cam_canvas.create_window((0, 0), window=self._cam_frame_inner, anchor="nw")

        def _resize_cam(e):
            cam_canvas.itemconfig(cam_cw, width=e.width)
        cam_canvas.bind("<Configure>", _resize_cam)
        self._cam_frame_inner.bind(
            "<Configure>",
            lambda _: cam_canvas.configure(scrollregion=cam_canvas.bbox("all")))

        _cam_ent = [False]
        def _cam_mw(e): cam_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        def _cam_enter(_): _cam_ent[0] = True; cam_canvas.bind_all("<MouseWheel>", _cam_mw)
        def _cam_leave(_):
            _cam_ent[0] = False
            cam_canvas.after(20, lambda: cam_canvas.unbind_all("<MouseWheel>") if not _cam_ent[0] else None)
        cam_canvas.bind("<Enter>", _cam_enter)
        cam_canvas.bind("<Leave>", _cam_leave)

        # Restore saved camera list
        saved    = _CFG.get("pgs.cam_list", [])
        selected = set(_CFG.get("pgs.cam_selected", saved))
        for name in saved:
            self._cam_vars[name] = BooleanVar(value=(name in selected))
        self._rebuild_cam_widgets()

    # ── section: Date range ────────────────────────────────────────────────────

    def _build_dates(self, p):
        f = Frame(p, bg=BG, padx=10, pady=2)
        f.pack(fill=X)
        self._sep(f, "Khoảng thời gian")

        today    = datetime.now().strftime("%Y-%m-%d")
        week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

        row = Frame(f, bg=BG)
        row.pack(fill=X)

        Label(row, text="Từ ngày:", bg=BG, fg=TEXT, font=F_MAIN).grid(
            row=0, column=0, padx=(0, 6), sticky=W)
        self.date_from_var = StringVar(value=_CFG.get("pgs.date_from", week_ago))
        _bind_cfg("pgs.date_from", self.date_from_var)
        Entry(row, textvariable=self.date_from_var, width=13,
              bg=CARD, fg=TEXT, insertbackground=TEXT,
              relief="flat", font=F_MAIN, bd=4).grid(row=0, column=1, padx=4)

        Label(row, text="Đến ngày:", bg=BG, fg=TEXT, font=F_MAIN).grid(
            row=0, column=2, padx=(16, 6), sticky=W)
        self.date_to_var = StringVar(value=_CFG.get("pgs.date_to", today))
        _bind_cfg("pgs.date_to", self.date_to_var)
        Entry(row, textvariable=self.date_to_var, width=13,
              bg=CARD, fg=TEXT, insertbackground=TEXT,
              relief="flat", font=F_MAIN, bd=4).grid(row=0, column=3, padx=4)

        Label(row, text="(YYYY-MM-DD)", bg=BG, fg=DIM,
              font=("Segoe UI", 8)).grid(row=0, column=4, padx=(10, 0), sticky=W)

        # Quick range buttons
        qrow = Frame(f, bg=BG)
        qrow.pack(fill=X, pady=(5, 0))
        Label(qrow, text="Nhanh:", bg=BG, fg=DIM, font=("Segoe UI", 8)).pack(side=LEFT)
        for label, days in [("Hôm nay", 0), ("3 ngày", 3), ("7 ngày", 7),
                             ("30 ngày", 30), ("90 ngày", 90)]:
            Button(qrow, text=label,
                   command=lambda d=days: self._quick_range(d),
                   bg=CARD, fg=TEXT, font=("Segoe UI", 8),
                   relief="flat", padx=7, pady=2, cursor="hand2").pack(side=LEFT, padx=3)

    # ── section: Image types ───────────────────────────────────────────────────

    def _build_types(self, p):
        f = Frame(p, bg=BG, padx=10, pady=2)
        f.pack(fill=X)
        self._sep(f, "Loại ảnh (lọc theo chuỗi trong tên file)")

        row = Frame(f, bg=BG)
        row.pack(fill=X)
        Label(row, text="Hậu tố:", bg=BG, fg=TEXT, font=F_MAIN).pack(side=LEFT, padx=(0, 8))
        self.img_types_var = StringVar(value=_CFG.get("pgs.img_types", "overview"))
        _bind_cfg("pgs.img_types", self.img_types_var)
        Entry(row, textvariable=self.img_types_var, width=45,
              bg=CARD, fg=TEXT, insertbackground=TEXT,
              relief="flat", font=F_MAIN, bd=4).pack(side=LEFT, padx=(0, 8))
        Label(row, text="(phân cách bằng dấu phẩy — để trống = lấy tất cả)",
              bg=BG, fg=DIM, font=("Segoe UI", 8)).pack(side=LEFT)

        qrow = Frame(f, bg=BG)
        qrow.pack(fill=X, pady=(4, 0))
        Label(qrow, text="Thêm nhanh:", bg=BG, fg=DIM, font=("Segoe UI", 8)).pack(side=LEFT)
        for t in ["overview", "plate", "vehicle", "full", "face"]:
            Button(qrow, text=t, command=lambda x=t: self._add_img_type(x),
                   bg=CARD, fg=TEXT, font=("Segoe UI", 8),
                   relief="flat", padx=6, pady=2, cursor="hand2").pack(side=LEFT, padx=2)
        Button(qrow, text="✘ Xóa",
               command=lambda: self.img_types_var.set(""),
               bg=CARD, fg=DIM, font=("Segoe UI", 8),
               relief="flat", padx=6, pady=2, cursor="hand2").pack(side=LEFT, padx=(8, 0))

    # ── section: Limits ────────────────────────────────────────────────────────

    def _build_limits(self, p):
        f = Frame(p, bg=BG, padx=10, pady=2)
        f.pack(fill=X)
        self._sep(f, "Cài đặt giới hạn")

        row = Frame(f, bg=BG)
        row.pack(fill=X)

        # Max per day
        Label(row, text="Max ảnh/ngày/cam:", bg=BG, fg=TEXT, font=F_MAIN).grid(
            row=0, column=0, padx=(0, 4), sticky=W)
        self.max_per_day_var = IntVar(value=int(_CFG.get("pgs.max_per_day", 100)))
        _bind_cfg("pgs.max_per_day", self.max_per_day_var)
        Spinbox(row, from_=0, to=99999, textvariable=self.max_per_day_var,
                width=8, font=F_MAIN, bg=CARD, fg=TEXT,
                insertbackground=TEXT, buttonbackground=ACCENT2,
                relief="flat").grid(row=0, column=1, padx=4)

        # Max per hour
        Label(row, text="Max ảnh/giờ/cam:", bg=BG, fg=TEXT, font=F_MAIN).grid(
            row=0, column=2, padx=(14, 4), sticky=W)
        self.max_per_hour_var = IntVar(value=int(_CFG.get("pgs.max_per_hour", 0)))
        _bind_cfg("pgs.max_per_hour", self.max_per_hour_var)
        Spinbox(row, from_=0, to=9999, textvariable=self.max_per_hour_var,
                width=7, font=F_MAIN, bg=CARD, fg=TEXT,
                insertbackground=TEXT, buttonbackground=ACCENT2,
                relief="flat").grid(row=0, column=3, padx=4)

        # Max per camera
        Label(row, text="Max ảnh/cam:", bg=BG, fg=TEXT, font=F_MAIN).grid(
            row=0, column=4, padx=(14, 4), sticky=W)
        self.max_per_cam_var = IntVar(value=int(_CFG.get("pgs.max_per_cam", 0)))
        _bind_cfg("pgs.max_per_cam", self.max_per_cam_var)
        Spinbox(row, from_=0, to=999999, textvariable=self.max_per_cam_var,
                width=9, font=F_MAIN, bg=CARD, fg=TEXT,
                insertbackground=TEXT, buttonbackground=ACCENT2,
                relief="flat").grid(row=0, column=5, padx=4)

        # Sleep
        Label(row, text="Nghỉ (s):", bg=BG, fg=TEXT, font=F_MAIN).grid(
            row=0, column=6, padx=(14, 4), sticky=W)
        self.sleep_sec_var = DoubleVar(value=float(_CFG.get("pgs.sleep_sec", 0.0)))
        _bind_cfg("pgs.sleep_sec", self.sleep_sec_var)
        Entry(row, textvariable=self.sleep_sec_var, width=6,
              bg=CARD, fg=TEXT, insertbackground=TEXT,
              relief="flat", font=F_MAIN, bd=4).grid(row=0, column=7, padx=4)

        # Parallel
        row2 = Frame(f, bg=BG)
        row2.pack(fill=X, pady=(6, 0))
        Label(row2, text="Luồng song song:", bg=BG, fg=TEXT, font=F_MAIN).grid(
            row=0, column=0, padx=(0, 4), sticky=W)
        self.parallel_var = IntVar(value=int(_CFG.get("pgs.parallel", 1)))
        _bind_cfg("pgs.parallel", self.parallel_var)
        Spinbox(row2, from_=1, to=16, textvariable=self.parallel_var,
                width=4, font=F_MAIN, bg=CARD, fg=TEXT,
                insertbackground=TEXT, buttonbackground=ACCENT2,
                relief="flat").grid(row=0, column=1, padx=4)
        Label(row2, text="(chia danh sách camera cho N luồng chạy đồng thời)",
              bg=BG, fg=DIM, font=("Segoe UI", 8)).grid(
            row=0, column=2, padx=(4, 0), sticky=W)

        Label(f,
              text="Max/ngày & Max/giờ: 0 = không giới hạn  ·  Max/cam: tổng cả lần chạy  "
                   "·  Max/giờ áp dụng dựa trên HH trong tên file (HH_MM_SS_...)",
              font=("Segoe UI", 7), fg=DIM, bg=BG, anchor=W).pack(fill=X, pady=(4, 0))

    # ── section: Output ────────────────────────────────────────────────────────

    def _build_output(self, p):
        f = Frame(p, bg=BG, padx=10, pady=2)
        f.pack(fill=X)
        self._sep(f, "Thư mục lưu ảnh")

        row = Frame(f, bg=BG)
        row.pack(fill=X)
        row.columnconfigure(0, weight=1)

        self.out_var = StringVar(
            value=_CFG.get("pgs.output_path", str(Path.cwd() / "images_pgs")))
        _bind_cfg("pgs.output_path", self.out_var)

        self._out_combo = ttk.Combobox(row, textvariable=self.out_var,
                                       style="Dark.TCombobox", font=F_MAIN)
        self._out_combo.grid(row=0, column=0, sticky=EW, padx=(0, 6))
        _bind_history("h.pgs.output_path", self._out_combo)

        Button(row, text="Chọn…", command=self._browse_output,
               bg=ACCENT2, fg="white", font=F_MAIN,
               activebackground=ACCENT, activeforeground="white",
               relief="flat", padx=10, cursor="hand2").grid(row=0, column=1, padx=(0, 4))
        Button(row, text="📂", command=self._open_output,
               bg=CARD, fg=TEXT, font=F_MAIN,
               activebackground=ACCENT2, activeforeground="white",
               relief="flat", padx=6, cursor="hand2").grid(row=0, column=2)

        Label(f,
              text="Cấu trúc lưu: <thư mục>\\<camera>\\<YYYY-MM-DD>\\<tên file gốc>",
              font=("Segoe UI", 8), fg=DIM, bg=BG, anchor=W).pack(fill=X, pady=(3, 0))

    # ── section: Consolidate ───────────────────────────────────────────────────

    def _build_consolidate(self, p):
        f = Frame(p, bg=BG, padx=10, pady=2)
        f.pack(fill=X)
        self._sep(f, "Tổng hợp ảnh về 1 thư mục phẳng")

        # Dest folder row
        drow = Frame(f, bg=BG)
        drow.pack(fill=X)
        drow.columnconfigure(0, weight=1)

        self.cons_dest_var = StringVar(
            value=_CFG.get("pgs.cons_dest", str(Path.cwd() / "images_pgs_flat")))
        _bind_cfg("pgs.cons_dest", self.cons_dest_var)

        self._cons_dest_combo = ttk.Combobox(drow, textvariable=self.cons_dest_var,
                                              style="Dark.TCombobox", font=F_MAIN)
        self._cons_dest_combo.grid(row=0, column=0, sticky=EW, padx=(0, 6))
        _bind_history("h.pgs.cons_dest", self._cons_dest_combo)

        Button(drow, text="Chọn…", command=self._browse_cons_dest,
               bg=ACCENT2, fg="white", font=F_MAIN,
               activebackground=ACCENT, activeforeground="white",
               relief="flat", padx=10, cursor="hand2").grid(row=0, column=1, padx=(0, 4))
        Button(drow, text="📂", command=self._open_cons_dest,
               bg=CARD, fg=TEXT, font=F_MAIN,
               activebackground=ACCENT2, activeforeground="white",
               relief="flat", padx=6, cursor="hand2").grid(row=0, column=2)

        # Options + start row
        orow = Frame(f, bg=BG)
        orow.pack(fill=X, pady=(5, 0))

        self._cons_overwrite_var = BooleanVar(value=bool(_CFG.get("pgs.cons_overwrite", False)))
        _bind_cfg("pgs.cons_overwrite", self._cons_overwrite_var)
        Checkbutton(orow, text="Ghi đè file đã tồn tại",
                    variable=self._cons_overwrite_var,
                    bg=BG, fg=TEXT, selectcolor="#251C53",
                    activebackground=BG, font=F_MAIN, cursor="hand2").pack(side=LEFT)

        self._cons_stop_btn = Button(
            orow, text="■ Dừng", command=self._stop_consolidate,
            bg=CARD, fg=DIM, font=F_MAIN,
            activebackground="#4a0000", activeforeground="white",
            relief="flat", padx=10, pady=4, cursor="hand2", state=DISABLED)
        self._cons_stop_btn.pack(side=RIGHT, padx=(4, 0))

        self._cons_start_btn = Button(
            orow, text="🔀 Bắt đầu tổng hợp", command=self._start_consolidate,
            bg=ACCENT2, fg="white", font=F_BOLD,
            activebackground=ACCENT, activeforeground="white",
            relief="flat", padx=14, pady=4, cursor="hand2")
        self._cons_start_btn.pack(side=RIGHT)

        # Status row
        srow = Frame(f, bg=BG)
        srow.pack(fill=X, pady=(4, 0))
        Label(srow, text="Trạng thái:", bg=BG, fg=DIM, font=("Segoe UI", 8)).pack(side=LEFT)
        self._cons_status_lbl = Label(srow, text="Sẵn sàng",
                                       bg=BG, fg=DIM, font=("Segoe UI", 8))
        self._cons_status_lbl.pack(side=LEFT, padx=(4, 0))

        self._cons_count_lbl = Label(srow, text="",
                                      bg=BG, fg=TEXT, font=("Segoe UI Semibold", 9))
        self._cons_count_lbl.pack(side=LEFT, padx=(16, 0))

        Label(f,
              text="Tên file đích: <camera>_<tên file gốc>  "
                   "→  ảnh cùng camera xếp liền nhau khi sort theo tên",
              font=("Segoe UI", 7), fg=DIM, bg=BG, anchor=W).pack(fill=X, pady=(3, 0))

    # ── section: Controls ──────────────────────────────────────────────────────

    def _build_controls(self, p):
        f = Frame(p, bg=BG, padx=10, pady=8)
        f.pack(fill=X)

        self.start_btn = Button(
            f, text="▶  Bắt đầu (F5)", command=self._start,
            bg=ACCENT, fg="white", font=F_BOLD,
            activebackground="#c0421a", activeforeground="white",
            relief="flat", padx=20, pady=6, cursor="hand2")
        self.start_btn.pack(side=LEFT, padx=(0, 8))

        self.pause_btn = Button(
            f, text="⏸  Tạm dừng", command=self._pause,
            bg=ACCENT2, fg="white", font=F_BOLD,
            activebackground="#2a1f6c", activeforeground="white",
            relief="flat", padx=16, pady=6, cursor="hand2", state=DISABLED)
        self.pause_btn.pack(side=LEFT, padx=(0, 8))

        self.stop_btn = Button(
            f, text="■  Dừng (Esc)", command=self._stop,
            bg=CARD, fg=DIM, font=F_BOLD,
            activebackground="#4a0000", activeforeground="white",
            relief="flat", padx=16, pady=6, cursor="hand2", state=DISABLED)
        self.stop_btn.pack(side=LEFT)

        self.status_lbl = Label(f, text="Sẵn sàng", bg=BG, fg=DIM, font=F_MAIN)
        self.status_lbl.pack(side=LEFT, padx=(20, 0))

    # ── section: Progress ──────────────────────────────────────────────────────

    def _build_progress(self, p):
        f = Frame(p, bg=BG, padx=10, pady=4)
        f.pack(fill=X)

        prow = Frame(f, bg=BG)
        prow.pack(fill=X)
        self.pbar = ttk.Progressbar(
            prow, style="K.Horizontal.TProgressbar",
            mode="determinate", maximum=100, value=0)
        self.pbar.pack(side=LEFT, fill=X, expand=True, padx=(0, 8))
        self.pct_lbl = Label(prow, text="0%", bg=BG, fg=TEXT, font=F_MAIN, width=5)
        self.pct_lbl.pack(side=LEFT)
        self.eta_lbl = Label(prow, text="ETA: --:--", bg=BG, fg=DIM, font=F_MAIN)
        self.eta_lbl.pack(side=LEFT, padx=(8, 0))

        srow = Frame(f, bg=BG)
        srow.pack(fill=X, pady=(4, 0))
        self._stat_labels: dict[str, Label] = {}
        for key, label, color in [
            ("saved",   "Đã lưu:",  "#4caf50"),
            ("skipped", "Bỏ qua:", DIM),
            ("errors",  "Lỗi:",    "#f05050"),
            ("camera",  "Camera:", TEXT),
            ("date",    "Ngày:",   TEXT),
        ]:
            sf = Frame(srow, bg=BG)
            sf.pack(side=LEFT, padx=(0, 18))
            Label(sf, text=label, bg=BG, fg=DIM, font=("Segoe UI", 8)).pack(side=LEFT)
            lbl = Label(sf,
                        text=("0" if key in ("saved", "skipped", "errors") else "—"),
                        bg=BG, fg=color, font=("Segoe UI Semibold", 9))
            lbl.pack(side=LEFT, padx=(3, 0))
            self._stat_labels[key] = lbl

    # ── section: Log ───────────────────────────────────────────────────────────

    def _build_log(self, p):
        f = Frame(p, bg=BG, padx=10, pady=4)
        f.pack(fill=BOTH, expand=True)
        self._sep(f, "Log")

        log_frm, self.log_txt = _make_logbox(f)
        log_frm.pack(fill=BOTH, expand=True)

        brow = Frame(f, bg=BG)
        brow.pack(fill=X, pady=(4, 0))
        Button(brow, text="Xóa log (Ctrl+L)", command=self._clear_log,
               bg=CARD, fg=DIM, font=("Segoe UI", 8),
               relief="flat", padx=8, pady=2, cursor="hand2").pack(side=LEFT)

    # ── camera management ──────────────────────────────────────────────────────

    def _discover_cameras(self):
        src = self.src_var.get().strip()
        if not src:
            messagebox.showwarning("Thiếu thông tin", "Vui lòng nhập đường dẫn nguồn trước.")
            return
        path = Path(src)
        if not path.exists():
            messagebox.showerror("Lỗi", f"Đường dẫn không tồn tại:\n{src}")
            return
        try:
            found = sorted(d.name for d in path.iterdir() if d.is_dir())
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không đọc được thư mục:\n{e}")
            return
        if not found:
            messagebox.showinfo("Thông báo", "Không tìm thấy thư mục camera nào.")
            return
        new_cams = [c for c in found if c not in self._cam_vars]
        for name in new_cams:
            self._cam_vars[name] = BooleanVar(value=True)
        self._rebuild_cam_widgets()
        self._save_cam_cfg()
        self._do_log(f"Phát hiện {len(found)} camera, thêm mới {len(new_cams)}")

    def _add_camera(self):
        name = self._cam_entry_var.get().strip()
        if not name:
            return
        if name in self._cam_vars:
            messagebox.showinfo("Thông báo", f"Camera '{name}' đã có trong danh sách.")
            return
        self._cam_vars[name] = BooleanVar(value=True)
        self._cam_entry_var.set("")
        self._rebuild_cam_widgets()
        self._save_cam_cfg()

    def _remove_cameras(self):
        to_rm = [n for n, v in self._cam_vars.items() if v.get()]
        if not to_rm:
            messagebox.showinfo("Thông báo", "Hãy check những camera muốn xóa khỏi danh sách.")
            return
        if not messagebox.askyesno("Xác nhận", f"Xóa {len(to_rm)} camera khỏi danh sách?"):
            return
        for n in to_rm:
            del self._cam_vars[n]
        self._rebuild_cam_widgets()
        self._save_cam_cfg()

    def _set_all_cameras(self, value: bool):
        for v in self._cam_vars.values():
            v.set(value)
        self._update_cam_count()
        self._save_cam_cfg()

    def _rebuild_cam_widgets(self):
        if self._cam_frame_inner is None:
            return
        for w in self._cam_frame_inner.winfo_children():
            w.destroy()
        for i, (name, var) in enumerate(sorted(self._cam_vars.items())):
            r, c = divmod(i, 3)
            Checkbutton(
                self._cam_frame_inner, text=name, variable=var,
                bg=CARD, fg=TEXT, selectcolor="#251C53",
                activebackground=CARD, font=F_MAIN, cursor="hand2",
                command=lambda: (self._update_cam_count(), self._save_cam_cfg()),
            ).grid(row=r, column=c, sticky=W, padx=(8, 24), pady=2)
        self._update_cam_count()

    def _update_cam_count(self):
        if self._cam_count_lbl is None:
            return
        n   = len(self._cam_vars)
        sel = sum(1 for v in self._cam_vars.values() if v.get())
        self._cam_count_lbl.config(
            text=f"{sel}/{n} camera được chọn" if n else "(chưa có camera)")

    def _save_cam_cfg(self):
        _CFG["pgs.cam_list"]     = sorted(self._cam_vars.keys())
        _CFG["pgs.cam_selected"] = [n for n, v in self._cam_vars.items() if v.get()]
        _cfg_save()

    # ── quick helpers ──────────────────────────────────────────────────────────

    def _quick_range(self, days: int):
        today = datetime.now().strftime("%Y-%m-%d")
        self.date_to_var.set(today)
        if days == 0:
            self.date_from_var.set(today)
        else:
            self.date_from_var.set(
                (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d"))

    def _add_img_type(self, t: str):
        cur   = self.img_types_var.get().strip()
        parts = [x.strip() for x in cur.split(",") if x.strip()]
        if t not in parts:
            parts.append(t)
        self.img_types_var.set(", ".join(parts))

    # ── file / folder dialogs ──────────────────────────────────────────────────

    def _browse_source(self):
        p = filedialog.askdirectory(initialdir=self.src_var.get() or None)
        if p:
            self.src_var.set(p)
            _push_history("h.pgs.source_path", p)
            self._src_combo["values"] = _get_history("h.pgs.source_path")

    def _browse_output(self):
        p = filedialog.askdirectory(initialdir=self.out_var.get() or None)
        if p:
            self.out_var.set(p)
            _push_history("h.pgs.output_path", p)
            self._out_combo["values"] = _get_history("h.pgs.output_path")

    def _open_output(self):
        p = self.out_var.get().strip()
        if p and Path(p).is_dir():
            os.startfile(p)

    # ── run control ────────────────────────────────────────────────────────────

    def _start(self):
        if self._running:
            return

        src      = self.src_var.get().strip()
        out      = self.out_var.get().strip()
        cameras  = [n for n, v in self._cam_vars.items() if v.get()]
        d_from   = self.date_from_var.get().strip()
        d_to     = self.date_to_var.get().strip()

        if not src:
            messagebox.showwarning("Thiếu thông tin", "Vui lòng nhập đường dẫn nguồn.")
            return
        if not out:
            messagebox.showwarning("Thiếu thông tin", "Vui lòng nhập thư mục lưu.")
            return
        if not d_from or not d_to:
            messagebox.showwarning("Thiếu thông tin", "Vui lòng nhập khoảng ngày.")
            return
        if not cameras:
            if not messagebox.askyesno(
                    "Xác nhận",
                    "Chưa chọn camera nào.\n"
                    "Tự động phát hiện từ thư mục nguồn khi chạy?"):
                return

        img_types = [t.strip() for t in self.img_types_var.get().split(",") if t.strip()]

        cfg = {
            "source_path":  src,
            "output_path":  out,
            "cameras":      cameras,
            "date_from":    d_from,
            "date_to":      d_to,
            "img_types":    img_types,
            "max_per_day":  self.max_per_day_var.get(),
            "max_per_hour": self.max_per_hour_var.get(),
            "max_per_cam":  self.max_per_cam_var.get(),
            "sleep_sec":    self.sleep_sec_var.get(),
        }

        self._running = True
        self._paused  = False
        self._pause_event.set()
        self._run_start = time.time()
        self._parallel_done = 0

        self.start_btn.config(state=DISABLED)
        self.stop_btn.config(state=NORMAL)
        self.pause_btn.config(state=NORMAL)
        self.status_lbl.config(text="Đang chạy…", fg=ACCENT)
        self.pbar.config(value=0)
        self.pct_lbl.config(text="0%")
        self.eta_lbl.config(text="ETA: --:--")
        for lbl in self._stat_labels.values():
            lbl.config(text="0" if lbl.cget("text").isdigit() else "—")
        self._stat_labels["saved"].config(text="0")
        self._stat_labels["skipped"].config(text="0")
        self._stat_labels["errors"].config(text="0")
        self._stat_labels["camera"].config(text="—")
        self._stat_labels["date"].config(text="—")

        n_parallel = max(1, min(16, self.parallel_var.get()))

        if n_parallel > 1 and len(cameras) > 1:
            # Split cameras across N workers
            chunks = [[] for _ in range(n_parallel)]
            for i, c in enumerate(cameras):
                chunks[i % n_parallel].append(c)
            chunks = [ch for ch in chunks if ch]
            self._parallel_total  = len(chunks)
            self._parallel_workers = []
            threads = []
            for chunk in chunks:
                c = dict(cfg)
                c["cameras"] = chunk
                w = PgsImageWorker(c, self._log_q, self._stat_q,
                                   pause_event=self._pause_event,
                                   signal_done=True)
                self._parallel_workers.append(w)
                threads.append(threading.Thread(
                    target=self._run_worker_instance, args=(w,), daemon=True))
            self._thread = threading.Thread(
                target=self._launch_parallel, args=(threads,), daemon=True)
            self._thread.start()
        else:
            self._parallel_total = 1
            self._worker = PgsImageWorker(cfg, self._log_q, self._stat_q,
                                          pause_event=self._pause_event,
                                          signal_done=True)
            self._thread = threading.Thread(
                target=self._run_worker_instance, args=(self._worker,), daemon=True)
            self._thread.start()

    def _run_worker_instance(self, worker: PgsImageWorker):
        try:
            worker.run()
        except Exception as e:
            self._log_q.put(f"[LỖI] Worker exception: {e}")
            self._stat_q.put({"done": True, "saved": 0, "errors": 1})

    def _launch_parallel(self, threads: list):
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    def _pause(self):
        if not self._running:
            return
        if self._paused:
            self._paused = False
            self._pause_event.set()
            self.pause_btn.config(text="⏸  Tạm dừng", fg="white")
            self.status_lbl.config(text="Tiếp tục…", fg=ACCENT)
        else:
            self._paused = True
            self._pause_event.clear()
            self.pause_btn.config(text="▶  Tiếp tục", fg=ACCENT)
            self.status_lbl.config(text="Tạm dừng", fg=DIM)

    def _stop(self):
        if self._worker:
            self._worker.stop()
        for w in self._parallel_workers:
            w.stop()
        self._running = False
        self._paused  = False
        self._pause_event.set()
        self.stop_btn.config(state=DISABLED)
        self.pause_btn.config(state=DISABLED, text="⏸  Tạm dừng", fg="white")
        self.start_btn.config(state=NORMAL)
        self.pbar.config(value=0)
        self.pct_lbl.config(text="0%")
        self.eta_lbl.config(text="ETA: --:--")
        self.status_lbl.config(text="Đã dừng", fg=DIM)

    def _on_done(self):
        self._running = False
        self._paused  = False
        self._pause_event.set()
        self.pbar.config(value=100)
        self.pct_lbl.config(text="100%")
        self.eta_lbl.config(text="ETA: 00:00")
        self.start_btn.config(state=NORMAL)
        self.stop_btn.config(state=DISABLED)
        self.pause_btn.config(state=DISABLED, text="⏸  Tạm dừng", fg="white")
        self.status_lbl.config(text="Hoàn thành", fg="#4caf50")

    # ── poll loop ──────────────────────────────────────────────────────────────

    def _poll(self):
        # Drain log queue
        try:
            for _ in range(80):
                self._do_log(self._log_q.get_nowait())
        except queue.Empty:
            pass

        # Take latest stat
        latest: dict = {}
        try:
            while True:
                latest = self._stat_q.get_nowait()
        except queue.Empty:
            pass

        if latest:
            self._apply_stat(latest)

        self.after(self._POLL_MS, self._poll)

    def _apply_stat(self, d: dict):
        for key in ("saved", "skipped", "errors"):
            if key in d:
                lbl = self._stat_labels.get(key)
                if lbl:
                    lbl.config(text=str(d[key]))
        for key in ("camera", "date"):
            if key in d:
                lbl = self._stat_labels.get(key)
                if lbl:
                    lbl.config(text=str(d[key]))

        if "progress" in d:
            pct = min(100, int(d["progress"] * 100))
            self.pbar.config(value=pct)
            self.pct_lbl.config(text=f"{pct}%")
            elapsed = time.time() - self._run_start
            if d["progress"] > 0.02 and elapsed > 1:
                total_est = elapsed / d["progress"]
                remain    = max(0, total_est - elapsed)
                mm, ss    = divmod(int(remain), 60)
                hh, mm    = divmod(mm, 60)
                if hh:
                    self.eta_lbl.config(text=f"ETA: {hh}:{mm:02d}:{ss:02d}")
                else:
                    self.eta_lbl.config(text=f"ETA: {mm}:{ss:02d}")

        if d.get("done"):
            self._parallel_done += 1
            if self._parallel_done >= self._parallel_total:
                self._on_done()

    # ── log ────────────────────────────────────────────────────────────────────

    def _do_log(self, msg: str):
        try:
            lines = int(self.log_txt.index("end-1c").split(".")[0])
            if lines > self._LOG_MAX:
                self.log_txt.configure(state=NORMAL)
                self.log_txt.delete("1.0", "500.0")
                self.log_txt.configure(state=DISABLED)
            _append_log(self.log_txt, msg)
        except Exception:
            pass

    def _clear_log(self):
        self.log_txt.configure(state=NORMAL)
        self.log_txt.delete("1.0", END)
        self.log_txt.configure(state=DISABLED)

    # ── consolidate ────────────────────────────────────────────────────────────

    def _browse_cons_dest(self):
        p = filedialog.askdirectory(initialdir=self.cons_dest_var.get() or None)
        if p:
            self.cons_dest_var.set(p)
            _push_history("h.pgs.cons_dest", p)
            self._cons_dest_combo["values"] = _get_history("h.pgs.cons_dest")

    def _open_cons_dest(self):
        p = self.cons_dest_var.get().strip()
        if p and Path(p).is_dir():
            os.startfile(p)

    def _start_consolidate(self):
        if self._cons_running:
            return

        src  = self.out_var.get().strip()        # nguồn = thư mục lưu ảnh
        dest = self.cons_dest_var.get().strip()

        if not src:
            messagebox.showwarning("Thiếu thông tin",
                                   "Thư mục lưu ảnh (nguồn tổng hợp) chưa được chọn.")
            return
        if not dest:
            messagebox.showwarning("Thiếu thông tin", "Vui lòng chọn thư mục đích.")
            return
        if not Path(src).exists():
            messagebox.showerror("Lỗi", f"Thư mục nguồn không tồn tại:\n{src}")
            return

        overwrite = self._cons_overwrite_var.get()
        self._cons_running = True
        self._cons_stop.clear()
        self._cons_start_btn.config(state=DISABLED)
        self._cons_stop_btn.config(state=NORMAL)
        self._cons_status_lbl.config(text="Đang chạy…", fg=ACCENT)
        self._cons_count_lbl.config(text="")

        self._cons_thread = threading.Thread(
            target=self._run_consolidate,
            args=(Path(src), Path(dest), overwrite),
            daemon=True)
        self._cons_thread.start()

    def _stop_consolidate(self):
        self._cons_stop.set()

    def _run_consolidate(self, src: Path, dest: Path, overwrite: bool):
        """Chạy trong thread: copy <src>/<cam>/<date>/<file> → <dest>/<cam>_<file>."""
        import shutil

        ts = datetime.now().strftime("%H:%M:%S")
        self._log_q.put(f"[{ts}] [Tổng hợp] Bắt đầu: {src} → {dest}")

        try:
            dest.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self._log_q.put(f"[LỖI] Không tạo được thư mục đích: {e}")
            self.after(0, self._cons_done, 0, 0, 1)
            return

        copied = skipped = errors = 0

        # Duyệt <src>/<camera>/<date_or_subdir>/<file>
        try:
            cam_dirs = sorted(d for d in src.iterdir() if d.is_dir())
        except Exception as e:
            self._log_q.put(f"[LỖI] Đọc thư mục nguồn: {e}")
            self.after(0, self._cons_done, 0, 0, 1)
            return

        for cam_dir in cam_dirs:
            if self._cons_stop.is_set():
                break
            cam = cam_dir.name

            # Duyệt đệ quy tất cả file ảnh trong cam_dir
            try:
                all_files = [
                    f for f in cam_dir.rglob("*")
                    if f.is_file() and f.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp"}
                ]
            except Exception as e:
                self._log_q.put(f"[LỖI] Đọc {cam}: {e}")
                errors += 1
                continue

            cam_copied = 0
            for f in sorted(all_files, key=lambda x: x.name):
                if self._cons_stop.is_set():
                    break

                dest_name = f"{cam}_{f.name}"
                dst       = dest / dest_name

                # Xử lý trùng tên: thêm _2, _3, ...
                if dst.exists() and not overwrite:
                    skipped += 1
                    continue
                if dst.exists() and overwrite:
                    pass  # sẽ ghi đè
                elif not dst.exists():
                    # Kiểm tra xem tên có bị trùng với file từ camera khác không
                    counter = 2
                    while dst.exists():
                        stem = dest_name.rsplit(".", 1)[0]
                        ext  = f.suffix
                        dst  = dest / f"{stem}_{counter}{ext}"
                        counter += 1

                try:
                    shutil.copy2(f, dst)
                    copied    += 1
                    cam_copied += 1
                    self.after(0, self._cons_update, copied, skipped, errors)
                except Exception as e:
                    self._log_q.put(f"[LỖI] Copy {f.name}: {e}")
                    errors += 1

            if cam_copied:
                ts2 = datetime.now().strftime("%H:%M:%S")
                self._log_q.put(f"[{ts2}] [Tổng hợp] {cam}: {cam_copied} file")

        self.after(0, self._cons_done, copied, skipped, errors)

    def _cons_update(self, copied: int, skipped: int, errors: int):
        self._cons_count_lbl.config(
            text=f"Đã copy: {copied}  |  Bỏ qua: {skipped}"
                 + (f"  |  Lỗi: {errors}" if errors else ""))

    def _cons_done(self, copied: int, skipped: int, errors: int):
        self._cons_running = False
        self._cons_start_btn.config(state=NORMAL)
        self._cons_stop_btn.config(state=DISABLED)

        if self._cons_stop.is_set():
            self._cons_status_lbl.config(text="Đã dừng", fg=DIM)
        elif errors and not copied:
            self._cons_status_lbl.config(text="Thất bại", fg="#f05050")
        else:
            self._cons_status_lbl.config(text="Hoàn thành", fg="#4caf50")

        self._cons_count_lbl.config(
            text=f"Đã copy: {copied}  |  Bỏ qua: {skipped}"
                 + (f"  |  Lỗi: {errors}" if errors else ""))

        ts = datetime.now().strftime("%H:%M:%S")
        self._log_q.put(
            f"[{ts}] [Tổng hợp] Xong: {copied} đã copy  |  {skipped} bỏ qua  |  {errors} lỗi")

    # ── dedup ──────────────────────────────────────────────────────────────────

    def _build_dedup(self, p):
        f = Frame(p, bg=BG, padx=10, pady=2)
        f.pack(fill=X)
        self._sep(f, "Lọc ảnh trùng (theo nội dung file)")

        # Source folder
        drow = Frame(f, bg=BG)
        drow.pack(fill=X)
        drow.columnconfigure(0, weight=1)

        self.dedup_src_var = StringVar(
            value=_CFG.get("pgs.dedup_src", ""))
        _bind_cfg("pgs.dedup_src", self.dedup_src_var)

        self._dedup_src_combo = ttk.Combobox(drow, textvariable=self.dedup_src_var,
                                              style="Dark.TCombobox", font=F_MAIN)
        self._dedup_src_combo.grid(row=0, column=0, sticky=EW, padx=(0, 6))
        _bind_history("h.pgs.dedup_src", self._dedup_src_combo)

        Button(drow, text="Chọn…", command=self._browse_dedup_src,
               bg=ACCENT2, fg="white", font=F_MAIN,
               activebackground=ACCENT, activeforeground="white",
               relief="flat", padx=10, cursor="hand2").grid(row=0, column=1, padx=(0, 4))
        Button(drow, text="📂", command=self._open_dedup_src,
               bg=CARD, fg=TEXT, font=F_MAIN,
               activebackground=ACCENT2, activeforeground="white",
               relief="flat", padx=6, cursor="hand2").grid(row=0, column=2, padx=(0, 4))
        Button(drow, text="← Dùng thư mục tổng hợp",
               command=lambda: self.dedup_src_var.set(self.cons_dest_var.get()),
               bg=CARD, fg=DIM, font=("Segoe UI", 8),
               activebackground=ACCENT2, activeforeground="white",
               relief="flat", padx=8, cursor="hand2").grid(row=0, column=3)

        # Action options
        opt_row = Frame(f, bg=BG)
        opt_row.pack(fill=X, pady=(6, 0))

        self._dedup_action_var = StringVar(value=_CFG.get("pgs.dedup_action", "move"))
        _bind_cfg("pgs.dedup_action", self._dedup_action_var)

        Label(opt_row, text="Khi phát hiện trùng:", bg=BG, fg=TEXT, font=F_MAIN).pack(side=LEFT)
        for label, val in [("Chuyển vào _duplicates (an toàn)", "move"),
                           ("Xóa vĩnh viễn", "delete")]:
            Radiobutton(opt_row, text=label, variable=self._dedup_action_var, value=val,
                        bg=BG, fg=TEXT, selectcolor="#251C53",
                        activebackground=BG, font=F_MAIN, cursor="hand2").pack(
                side=LEFT, padx=(10, 0))

        self._dedup_dry_var = BooleanVar(value=bool(_CFG.get("pgs.dedup_dry", False)))
        _bind_cfg("pgs.dedup_dry", self._dedup_dry_var)
        Checkbutton(opt_row, text="Chạy thử (chỉ đếm)",
                    variable=self._dedup_dry_var,
                    bg=BG, fg=TEXT, selectcolor="#251C53",
                    activebackground=BG, font=F_MAIN, cursor="hand2").pack(
            side=LEFT, padx=(20, 0))

        # Method row
        mrow = Frame(f, bg=BG)
        mrow.pack(fill=X, pady=(5, 0))
        Label(mrow, text="Phương pháp:", bg=BG, fg=TEXT, font=F_MAIN).pack(side=LEFT)
        self._dedup_method_var = StringVar(value=_CFG.get("pgs.dedup_method", "md5"))
        _bind_cfg("pgs.dedup_method", self._dedup_method_var)
        Radiobutton(mrow, text="MD5 (byte chính xác, nhanh)",
                    variable=self._dedup_method_var, value="md5",
                    bg=BG, fg=TEXT, selectcolor="#251C53",
                    activebackground=BG, font=F_MAIN, cursor="hand2").pack(
            side=LEFT, padx=(8, 0))
        Radiobutton(mrow, text="pHash (hình ảnh tương đồng — cần Pillow)",
                    variable=self._dedup_method_var, value="phash",
                    bg=BG, fg=TEXT, selectcolor="#251C53",
                    activebackground=BG, font=F_MAIN, cursor="hand2").pack(
            side=LEFT, padx=(8, 0))
        Label(mrow, text="Ngưỡng:", bg=BG, fg=TEXT, font=F_MAIN).pack(
            side=LEFT, padx=(14, 4))
        self._dedup_threshold_var = IntVar(value=int(_CFG.get("pgs.dedup_threshold", 5)))
        _bind_cfg("pgs.dedup_threshold", self._dedup_threshold_var)
        Spinbox(mrow, from_=0, to=20, textvariable=self._dedup_threshold_var,
                width=4, font=F_MAIN, bg=CARD, fg=TEXT,
                insertbackground=TEXT, buttonbackground=ACCENT2,
                relief="flat").pack(side=LEFT)
        Label(mrow,
              text="(0=giống hệt, ≤5=gần giống, ≤10=tương đồng cao — chỉ áp dụng cho pHash)",
              bg=BG, fg=DIM, font=("Segoe UI", 7)).pack(side=LEFT, padx=(5, 0))

        # Control + status row
        ctrl_row = Frame(f, bg=BG)
        ctrl_row.pack(fill=X, pady=(6, 0))

        self._dedup_start_btn = Button(
            ctrl_row, text="🔍 Bắt đầu lọc trùng", command=self._start_dedup,
            bg=ACCENT2, fg="white", font=F_BOLD,
            activebackground=ACCENT, activeforeground="white",
            relief="flat", padx=14, pady=4, cursor="hand2")
        self._dedup_start_btn.pack(side=LEFT)

        self._dedup_stop_btn = Button(
            ctrl_row, text="■ Dừng", command=self._stop_dedup,
            bg=CARD, fg=DIM, font=F_MAIN,
            activebackground="#4a0000", activeforeground="white",
            relief="flat", padx=10, pady=4, cursor="hand2", state=DISABLED)
        self._dedup_stop_btn.pack(side=LEFT, padx=(6, 0))

        self._dedup_status_lbl = Label(ctrl_row, text="Sẵn sàng",
                                        bg=BG, fg=DIM, font=("Segoe UI", 8))
        self._dedup_status_lbl.pack(side=LEFT, padx=(14, 0))

        self._dedup_count_lbl = Label(ctrl_row, text="",
                                       bg=BG, fg=TEXT, font=("Segoe UI Semibold", 9))
        self._dedup_count_lbl.pack(side=LEFT, padx=(12, 0))

        Label(f,
              text="MD5: so sánh byte chính xác, nhanh — "
                   "pHash: so sánh nội dung hình ảnh, tìm ảnh nhìn giống nhau dù byte khác "
                   "(VD: JPEG có timestamp nhúng, camera offline frame...)",
              font=("Segoe UI", 7), fg=DIM, bg=BG, anchor=W).pack(fill=X, pady=(3, 0))

    def _browse_dedup_src(self):
        p = filedialog.askdirectory(initialdir=self.dedup_src_var.get() or None)
        if p:
            self.dedup_src_var.set(p)
            _push_history("h.pgs.dedup_src", p)
            self._dedup_src_combo["values"] = _get_history("h.pgs.dedup_src")

    def _open_dedup_src(self):
        p = self.dedup_src_var.get().strip()
        if p and Path(p).is_dir():
            os.startfile(p)

    def _start_dedup(self):
        if self._dedup_running:
            return
        src = self.dedup_src_var.get().strip()
        if not src:
            messagebox.showwarning("Thiếu thông tin", "Vui lòng chọn thư mục cần lọc.")
            return
        if not Path(src).is_dir():
            messagebox.showerror("Lỗi", f"Thư mục không tồn tại:\n{src}")
            return

        action    = self._dedup_action_var.get()
        dry       = self._dedup_dry_var.get()
        method    = self._dedup_method_var.get()
        threshold = self._dedup_threshold_var.get()

        if action == "delete" and not dry:
            if not messagebox.askyesno(
                    "Xác nhận xóa",
                    "Chế độ XÓA VĨNH VIỄN được chọn.\n"
                    "Ảnh trùng sẽ bị xóa và KHÔNG THỂ khôi phục.\n\n"
                    "Tiếp tục?"):
                return

        self._dedup_running = True
        self._dedup_stop.clear()
        self._dedup_start_btn.config(state=DISABLED)
        self._dedup_stop_btn.config(state=NORMAL)
        self._dedup_status_lbl.config(text="Đang quét…", fg=ACCENT)
        self._dedup_count_lbl.config(text="")

        self._dedup_thread = threading.Thread(
            target=self._run_dedup,
            args=(Path(src), action, dry, method, threshold),
            daemon=True)
        self._dedup_thread.start()

    def _stop_dedup(self):
        self._dedup_stop.set()

    def _run_dedup(self, folder: Path, action: str, dry: bool,
                   method: str = "md5", threshold: int = 5):
        import shutil

        IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}
        ts = datetime.now().strftime("%H:%M:%S")
        mode_lbl   = "chạy thử" if dry else ("xóa" if action == "delete" else "chuyển _duplicates")
        method_lbl = "MD5" if method == "md5" else f"pHash(ngưỡng≤{threshold})"
        self._log_q.put(
            f"[{ts}] [Dedup] Quét: {folder}  |  {method_lbl}  |  chế độ: {mode_lbl}")

        if method == "phash":
            try:
                from PIL import Image as _PIL_Image  # noqa: F401 — kiểm tra sẵn
            except ImportError:
                self._log_q.put(
                    "[LỖI] pHash cần Pillow.  Cài: pip install Pillow  "
                    "hoặc chọn lại chế độ MD5.")
                self.after(0, self._dedup_done, 0, 0, 0, 1)
                return

        # Thu thập file ảnh — loại trừ _duplicates đã tách lần trước
        try:
            all_files = [
                f for f in folder.rglob("*")
                if f.is_file()
                and f.suffix.lower() in IMAGE_EXTS
                and "_duplicates" not in f.parts
            ]
        except Exception as e:
            self._log_q.put(f"[LỖI] Đọc thư mục: {e}")
            self.after(0, self._dedup_done, 0, 0, 0, 1)
            return

        total = len(all_files)
        self._log_q.put(f"[{ts}] [Dedup] Tìm thấy {total} file ảnh, đang tính hash…")
        self.after(0, self._dedup_update_status, f"Quét 0/{total}…", 0, 0)

        duplicates: list[Path] = []
        scanned = 0

        if method == "md5":
            # ── MD5: gom theo size → hash chỉ nhóm cùng size ─────────────────
            by_size: dict[int, list[Path]] = {}
            for f in all_files:
                try:
                    sz = f.stat().st_size
                    by_size.setdefault(sz, []).append(f)
                except Exception:
                    pass

            seen_md5: dict[str, Path] = {}
            for sz, grp in by_size.items():
                if self._dedup_stop.is_set():
                    break
                if len(grp) == 1:
                    scanned += 1
                    continue
                for f in grp:
                    if self._dedup_stop.is_set():
                        break
                    try:
                        h = self._md5(f)
                    except Exception as e:
                        self._log_q.put(f"[LỖI] MD5 {f.name}: {e}")
                        scanned += 1
                        continue
                    if h in seen_md5:
                        duplicates.append(f)
                    else:
                        seen_md5[h] = f
                    scanned += 1
                    if scanned % 50 == 0:
                        self.after(0, self._dedup_update_status,
                                   f"Quét {scanned}/{total}…", len(duplicates), 0)

        else:
            # ── pHash: so sánh nội dung hình ảnh ─────────────────────────────
            if threshold > 0 and total > 8000:
                self._log_q.put(
                    f"[CẢNH BÁO] pHash ngưỡng>0 với {total} file mất nhiều thời gian. "
                    "Thử ngưỡng=0 trước để kiểm tra.")

            hash_list: list[tuple[int, Path]] = []
            for f in all_files:
                if self._dedup_stop.is_set():
                    break
                try:
                    h = self._phash_int(f)
                    hash_list.append((h, f))
                except Exception as e:
                    self._log_q.put(f"[LỖI] pHash {f.name}: {e}")
                scanned += 1
                if scanned % 100 == 0:
                    self.after(0, self._dedup_update_status,
                               f"Tính hash {scanned}/{total}…", len(duplicates), 0)

            if not self._dedup_stop.is_set():
                if threshold == 0:
                    # Exact pHash match — O(n) dict lookup
                    seen_ph: dict[int, Path] = {}
                    for h, f in hash_list:
                        if h in seen_ph:
                            duplicates.append(f)
                        else:
                            seen_ph[h] = f
                else:
                    # Hamming distance ≤ threshold — sort + compare vs kept list
                    hash_list.sort(key=lambda x: x[0])
                    kept: list[tuple[int, Path]] = []
                    compare_step = 0
                    for h, f in hash_list:
                        if self._dedup_stop.is_set():
                            break
                        is_dup = any(
                            bin(h ^ kh).count("1") <= threshold
                            for kh, _ in kept
                        )
                        if is_dup:
                            duplicates.append(f)
                        else:
                            kept.append((h, f))
                        compare_step += 1
                        if compare_step % 100 == 0:
                            self.after(0, self._dedup_update_status,
                                       f"So sánh {compare_step}/{total}…",
                                       len(duplicates), 0)

        if self._dedup_stop.is_set():
            self.after(0, self._dedup_done, scanned, len(duplicates), 0, 0)
            return

        n_dup = len(duplicates)
        ts2   = datetime.now().strftime("%H:%M:%S")
        self._log_q.put(f"[{ts2}] [Dedup] Quét xong: {n_dup} file trùng / {total} file")

        if n_dup == 0:
            self._log_q.put(f"[{ts2}] [Dedup] Không có ảnh trùng.")
            self.after(0, self._dedup_done, scanned, 0, 0, 0)
            return

        if dry:
            for f in duplicates:
                self._log_q.put(f"[Dedup][thử] Trùng: {f.name}")
            self.after(0, self._dedup_done, scanned, n_dup, 0, 0)
            return

        # Xử lý duplicate
        handled = errors = 0
        if action == "move":
            dup_dir = folder / "_duplicates"
            try:
                dup_dir.mkdir(exist_ok=True)
            except Exception as e:
                self._log_q.put(f"[LỖI] Tạo _duplicates: {e}")
                self.after(0, self._dedup_done, scanned, n_dup, 0, 1)
                return

        for f in duplicates:
            if self._dedup_stop.is_set():
                break
            try:
                if action == "move":
                    dst = dup_dir / f.name
                    counter = 2
                    while dst.exists():
                        dst = dup_dir / f"{f.stem}_{counter}{f.suffix}"
                        counter += 1
                    shutil.move(str(f), dst)
                else:
                    f.unlink()
                handled += 1
                self.after(0, self._dedup_update_status,
                           f"Đã xử lý {handled}/{n_dup}…", n_dup, handled)
            except Exception as e:
                self._log_q.put(f"[LỖI] Xử lý {f.name}: {e}")
                errors += 1

        self.after(0, self._dedup_done, scanned, n_dup, handled, errors)

    @staticmethod
    def _md5(path: Path, chunk_size: int = 65536) -> str:
        import hashlib
        h = hashlib.md5()
        with open(path, "rb") as fh:
            buf = fh.read(chunk_size)
            while buf:
                h.update(buf)
                buf = fh.read(chunk_size)
        return h.hexdigest()

    @staticmethod
    def _phash_int(path: Path, hash_size: int = 8) -> int:
        """Perceptual hash: resize → grayscale 8×8 → bits above mean → 64-bit int."""
        from PIL import Image
        img = Image.open(path).convert("L").resize(
            (hash_size, hash_size), Image.LANCZOS)
        pixels = list(img.getdata())
        avg = sum(pixels) / len(pixels)
        return sum(1 << i for i, p in enumerate(pixels) if p > avg)

    def _dedup_update_status(self, status: str, found: int, handled: int):
        self._dedup_status_lbl.config(text=status, fg=ACCENT)
        if found:
            txt = f"Trùng: {found}"
            if handled:
                txt += f"  |  Đã xử lý: {handled}"
            self._dedup_count_lbl.config(text=txt, fg="#f0c040")
        else:
            self._dedup_count_lbl.config(text="")

    def _dedup_done(self, scanned: int, found: int, handled: int, errors: int):
        self._dedup_running = False
        self._dedup_start_btn.config(state=NORMAL)
        self._dedup_stop_btn.config(state=DISABLED)

        stopped = self._dedup_stop.is_set()
        if stopped:
            self._dedup_status_lbl.config(text="Đã dừng", fg=DIM)
        elif errors and not handled:
            self._dedup_status_lbl.config(text="Lỗi", fg="#f05050")
        else:
            self._dedup_status_lbl.config(text="Hoàn thành", fg="#4caf50")

        color = "#f0c040" if found else "#4caf50"
        if found:
            txt = f"Trùng: {found}  |  Đã xử lý: {handled}"
        else:
            txt = "Không có ảnh trùng"
        if errors:
            txt += f"  |  Lỗi: {errors}"
        self._dedup_count_lbl.config(text=txt, fg=color)

        ts = datetime.now().strftime("%H:%M:%S")
        self._log_q.put(
            f"[{ts}] [Dedup] Xong: quét {scanned} file  |  "
            f"trùng {found}  |  xử lý {handled}  |  lỗi {errors}")
