import os
import queue
import threading
import time
from datetime import datetime
from pathlib import Path
from tkinter import *
from tkinter import filedialog, messagebox, ttk

from ...core.constants import BG, CARD, ACCENT, ACCENT2, TEXT, DIM, F_MAIN, F_BOLD, F_MONO
from ...core.settings import _bind_cfg, _cfg_dir, _bind_history, _push_history, _get_history
from ...core.imports import _REQUESTS_OK, _CV2_OK
from .parkingv6_image import Parkingv6Worker, _P6SharedLaneState
from ...utils.bad_image_viewer import BadImageViewer
from ...utils.migrate_structure import open_migrate_window as _open_migrate_window
from ...core.ui_helpers import DateTimePicker


class Parkingv6ImageTab(Frame):
    def __init__(self, master, root):
        super().__init__(master, bg=BG)
        self.root     = root
        self._worker  = None
        self._thread  = None
        self._log_q   = queue.Queue()
        self._stat_q  = queue.Queue()
        self._running = False
        self._paused  = False
        self._pause_event = threading.Event()
        self._pause_event.set()
        self._failed_items = []
        self._run_start_time = None
        self._done_count = 0
        self._total_estimate = 0
        self._last_stat = {}
        self._all_thread_stats: dict = {}
        self._parallel_workers: list = []
        self._build()
        self._poll()

    # ── layout ────────────────────────────────────────────────────────────────

    def _build(self):
        top = Frame(self, bg=CARD, padx=16, pady=8)
        top.pack(fill=X)
        Label(top, text="Parkingv6Image — Thu thập ảnh iParkingv5 (ApiManagerv6)",
              bg=CARD, fg=TEXT, font=F_BOLD).pack(side=LEFT)
        if not _REQUESTS_OK:
            Label(top, text="  ⚠ pip install requests",
                  bg=CARD, fg="#ff8844", font=("Segoe UI", 9)).pack(side=LEFT, padx=8)
        if not _CV2_OK:
            Label(top, text="  ⚠ pip install opencv-python numpy",
                  bg=CARD, fg="#ff8844", font=("Segoe UI", 9)).pack(side=LEFT, padx=4)

        body = Frame(self, bg=BG, padx=14, pady=6)
        body.pack(fill=BOTH, expand=True)
        self._build_time(body)
        self._build_output(body)
        self._build_settings(body)
        self._build_controls(body)
        self._build_progress(body)
        self._build_dashboard(body)
        self._build_log(body)

    def _sep(self, parent, text):
        f = Frame(parent, bg=BG)
        f.pack(fill=X, pady=(8, 3))
        Label(f, text=text, font=("Segoe UI", 9, "bold"),
              fg=ACCENT2, bg=BG).pack(side=LEFT)
        Frame(f, bg=DIM, height=1).pack(side=LEFT, fill=X, expand=True, padx=(8, 0), pady=5)

    # ── time range ────────────────────────────────────────────────────────────

    def _build_time(self, p):
        self._sep(p, "Khoảng thời gian (UTC)")
        f = Frame(p, bg=BG)
        f.pack(fill=X)
        Label(f, text="Từ:", bg=BG, fg=TEXT, font=F_MAIN).grid(
            row=0, column=0, padx=(0, 4), sticky=W)
        self.from_var = StringVar(value="2026-05-01T00:00:00")
        _bind_cfg("p6.from", self.from_var)
        DateTimePicker(f, textvariable=self.from_var, mode="datetime_T").grid(
            row=0, column=1, padx=4)
        Label(f, text="Đến:", bg=BG, fg=TEXT, font=F_MAIN).grid(
            row=0, column=2, padx=(14, 4))
        self.to_var = StringVar(value=datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"))
        _bind_cfg("p6.to", self.to_var)
        DateTimePicker(f, textvariable=self.to_var, mode="datetime_T").grid(
            row=0, column=3, padx=4)
        Label(f, text="Chọn giờ UTC — Vietnam UTC+7: trừ 7 giờ",
              font=("Segoe UI", 8), fg=DIM, bg=BG).grid(
            row=1, column=1, columnspan=3, sticky=W, pady=(2, 0))

    # ── output dir ────────────────────────────────────────────────────────────

    def _build_output(self, p):
        self._sep(p, "Thư mục lưu ảnh")
        f = Frame(p, bg=BG)
        f.pack(fill=X)
        f.columnconfigure(0, weight=1)
        self.out_var = StringVar(value=str(Path.cwd() / "images_p6"))
        _bind_cfg("p6.out", self.out_var)
        self._out_combo = ttk.Combobox(f, textvariable=self.out_var,
              style="Dark.TCombobox", font=F_MAIN)
        self._out_combo.grid(row=0, column=0, sticky=EW, padx=(0, 8))
        _bind_history("h.p6.out", self._out_combo)
        Button(f, text="Chọn…", command=self._browse,
               bg=ACCENT2, fg="white", font=F_MAIN,
               activebackground=ACCENT, activeforeground="white",
               relief="flat", padx=10, cursor="hand2").grid(row=0, column=1)
        Button(f, text="📂", command=self._open_out,
               bg=CARD, fg=TEXT, font=F_MAIN,
               activebackground=ACCENT2, activeforeground="white",
               relief="flat", padx=6, cursor="hand2").grid(row=0, column=2, padx=(2, 0))
        Label(p,
              text="Cấu trúc: <thư mục> / <tên làn> / <loại xe> / <YYYY-MM-DD> / <HH> / HHmmss_BSX.jpg"
                   "   (loại xe: toan_canh | xe_may | xe_dap | xe_tai | o_to)",
              font=("Segoe UI", 8), fg=DIM, bg=BG, anchor=W).pack(
            fill=X, pady=(3, 0))

    # ── settings ─────────────────────────────────────────────────────────────

    def _build_settings(self, p):
        self._sep(p, "Cài đặt")
        f = Frame(p, bg=BG)
        f.pack(fill=X)

        Label(f, text="Page size:", bg=BG, fg=TEXT, font=F_MAIN).grid(
            row=0, column=0, padx=(0, 4), sticky=W)
        self.page_size_var = IntVar(value=100)
        _bind_cfg("p6.page_size", self.page_size_var)
        Spinbox(f, from_=10, to=500, textvariable=self.page_size_var,
                width=7, font=F_MAIN, bg=CARD, fg=TEXT,
                insertbackground=TEXT, buttonbackground=ACCENT2,
                relief="flat").grid(row=0, column=1, padx=4)

        Label(f, text="Max pages:", bg=BG, fg=TEXT, font=F_MAIN).grid(
            row=0, column=2, padx=(12, 4))
        self.max_pages_var = IntVar(value=10000)
        _bind_cfg("p6.max_pages", self.max_pages_var)
        Spinbox(f, from_=1, to=99999, textvariable=self.max_pages_var,
                width=8, font=F_MAIN, bg=CARD, fg=TEXT,
                insertbackground=TEXT, buttonbackground=ACCENT2,
                relief="flat").grid(row=0, column=3, padx=4)

        Label(f, text="Nghỉ (s):", bg=BG, fg=TEXT, font=F_MAIN).grid(
            row=0, column=4, padx=(12, 4))
        self.sleep_var = DoubleVar(value=0.1)
        _bind_cfg("p6.sleep", self.sleep_var)
        Entry(f, textvariable=self.sleep_var, width=6,
              bg=CARD, fg=TEXT, insertbackground=TEXT,
              relief="flat", font=F_MAIN, bd=4).grid(row=0, column=5, padx=4)

        self.use_minio = BooleanVar(value=True)
        _bind_cfg("p6.use_minio", self.use_minio)
        Checkbutton(f, text="MinIO", variable=self.use_minio,
                    bg=BG, fg=TEXT, selectcolor=CARD,
                    activebackground=BG, font=F_MAIN).grid(
            row=0, column=6, padx=(14, 0))

        Label(f, text="Luồng:", bg=BG, fg=TEXT, font=F_MAIN).grid(
            row=0, column=7, padx=(14, 4))
        self.parallel_var = IntVar(value=1)
        _bind_cfg("p6.parallel", self.parallel_var)
        Spinbox(f, from_=1, to=8, textvariable=self.parallel_var,
                width=4, font=F_MAIN, bg=CARD, fg=TEXT,
                insertbackground=TEXT, buttonbackground=ACCENT2,
                relief="flat").grid(row=0, column=8, padx=4)

        # Row 1 — limits
        Label(f, text="Max ảnh/làn:", bg=BG, fg=TEXT, font=F_MAIN).grid(
            row=1, column=0, padx=(0, 4), sticky=W, pady=(6, 0))
        self.max_per_lane_var = IntVar(value=1000)
        _bind_cfg("p6.max_per_lane", self.max_per_lane_var)
        Spinbox(f, from_=0, to=999999, textvariable=self.max_per_lane_var,
                width=8, font=F_MAIN, bg=CARD, fg=TEXT,
                insertbackground=TEXT, buttonbackground=ACCENT2,
                relief="flat").grid(row=1, column=1, padx=4, pady=(6, 0))

        Label(f, text="Max ảnh/loại/làn:", bg=BG, fg=TEXT, font=F_MAIN).grid(
            row=1, column=2, padx=(12, 4), sticky=W, pady=(6, 0))
        self.max_per_cat_var = IntVar(value=0)
        _bind_cfg("p6.max_per_cat", self.max_per_cat_var)
        Spinbox(f, from_=0, to=999999, textvariable=self.max_per_cat_var,
                width=8, font=F_MAIN, bg=CARD, fg=TEXT,
                insertbackground=TEXT, buttonbackground=ACCENT2,
                relief="flat").grid(row=1, column=3, padx=4, pady=(6, 0))

        Label(f, text="Max ảnh/giờ/làn:", bg=BG, fg=TEXT, font=F_MAIN).grid(
            row=1, column=4, padx=(12, 4), sticky=W, pady=(6, 0))
        self.max_per_hour_var = IntVar(value=0)
        _bind_cfg("p6.max_per_hour", self.max_per_hour_var)
        Spinbox(f, from_=0, to=99999, textvariable=self.max_per_hour_var,
                width=7, font=F_MAIN, bg=CARD, fg=TEXT,
                insertbackground=TEXT, buttonbackground=ACCENT2,
                relief="flat").grid(row=1, column=5, padx=4, pady=(6, 0))

        Label(f, text="(0 = không giới hạn)", bg=BG, fg=DIM,
              font=("Segoe UI", 8)).grid(
            row=1, column=6, padx=(4, 0), sticky=W, pady=(6, 0))

        Label(f,
              text="Max ảnh/làn: tổng cả lần chạy  "
                   "•  Max ảnh/loại/làn: tối đa mỗi ngày/loại/làn  "
                   "•  Max ảnh/giờ/làn: trải đều các giờ trong ngày",
              font=("Segoe UI", 7), fg=DIM, bg=BG).grid(
            row=2, column=0, columnspan=7, sticky=W, pady=(3, 0))

        # Row 3 — nguồn sự kiện
        Label(f, text="Nguồn SK:", bg=BG, fg=TEXT, font=F_MAIN).grid(
            row=3, column=0, padx=(0, 4), sticky=W, pady=(6, 0))
        self.event_source_var = StringVar(value="both")
        _bind_cfg("p6.event_source", self.event_source_var)
        src_combo = ttk.Combobox(f, textvariable=self.event_source_var,
                                 values=["both", "event-in", "event-out"],
                                 state="readonly", width=14, font=F_MAIN)
        src_combo.grid(row=3, column=1, padx=4, pady=(6, 0))
        Label(f, text="both=vào+ra  •  event-in=vào  •  event-out=ra",
              bg=BG, fg=DIM, font=("Segoe UI", 8)).grid(
            row=3, column=2, columnspan=4, sticky=W, padx=(4, 0), pady=(6, 0))

        # Advanced panel
        adv_wrapper = Frame(p, bg=BG)
        adv_wrapper.pack(fill=X, pady=(5, 0))
        self._adv_open = False
        adv_bar = Frame(adv_wrapper, bg=BG)
        adv_bar.pack(fill=X)
        self._adv_lbl = Label(adv_bar, text="▶ Nâng cao (API / MinIO / Token)",
                              font=("Segoe UI", 8, "underline"),
                              fg=ACCENT2, bg=BG, cursor="hand2")
        self._adv_lbl.pack(anchor=W)
        self._adv_lbl.bind("<Button-1>", self._toggle_adv)
        self._adv_frame = Frame(adv_wrapper, bg=CARD, bd=1, relief="flat",
                                padx=8, pady=6)
        self._build_adv(self._adv_frame)

    def _build_adv(self, p):
        from ...core.constants import _P6_API_URL, _P6_MINIO_EP, _P6_MINIO_BUCKET, _P6_MINIO_AK, _P6_MINIO_SK
        fields = [
            ("API URL:",        "cfg_api",  _P6_API_URL,       38, ""),
            ("MinIO endpoint:", "cfg_mep",  _P6_MINIO_EP,      28, ""),
            ("MinIO bucket:",   "cfg_mbk",  _P6_MINIO_BUCKET,  20, ""),
            ("MinIO AK:",       "cfg_mak",  _P6_MINIO_AK,      16, ""),
            ("MinIO SK:",       "cfg_msk",  _P6_MINIO_SK,      20, "*"),
        ]
        for i, (lbl, attr, default, width, show) in enumerate(fields):
            r, c = divmod(i, 2)
            Label(p, text=lbl, font=("Segoe UI", 8),
                  bg=CARD, fg=DIM).grid(
                row=r, column=c * 2,
                padx=(0 if c == 0 else 16, 4), pady=2, sticky=W)
            var = StringVar(value=default)
            setattr(self, attr, var)
            _bind_cfg(f"p6.{attr}", var)
            Entry(p, textvariable=var, width=width, show=show,
                  bg="#16162a", fg=TEXT, insertbackground=TEXT,
                  relief="flat", font=F_MAIN, bd=4).grid(
                row=r, column=c * 2 + 1, padx=(0, 4), pady=2)

        # Token field (full width, last row)
        token_row = (len(fields) + 1) // 2
        Label(p, text="Bearer Token:", font=("Segoe UI", 8),
              bg=CARD, fg=DIM).grid(
            row=token_row, column=0, padx=(0, 4), pady=(8, 2), sticky=W)
        self.cfg_token = StringVar(value="")
        _bind_cfg("p6.cfg_token", self.cfg_token)
        Entry(p, textvariable=self.cfg_token, width=60, show="",
              bg="#16162a", fg="#4fc3f7", insertbackground=TEXT,
              relief="flat", font=F_MAIN, bd=4).grid(
            row=token_row, column=1, columnspan=3, padx=(0, 4), pady=(8, 2), sticky=EW)
        Label(p,
              text="Token không cần 'Bearer ' prefix — chỉ nhập chuỗi token  •  "
                   "Token hết hạn: chạy lại sau khi cập nhật token mới",
              font=("Segoe UI", 7), fg=DIM, bg=CARD).grid(
            row=token_row + 1, column=0, columnspan=4, sticky=W, pady=(0, 2))

    def _toggle_adv(self, _=None):
        self._adv_open = not self._adv_open
        if self._adv_open:
            self._adv_frame.pack(fill=X, pady=(0, 4))
            self._adv_lbl.config(text="▼ Nâng cao (API / MinIO / Token)")
        else:
            self._adv_frame.pack_forget()
            self._adv_lbl.config(text="▶ Nâng cao (API / MinIO / Token)")

    # ── controls ──────────────────────────────────────────────────────────────

    def _build_controls(self, p):
        f = Frame(p, bg=BG)
        f.pack(fill=X, pady=(10, 4))
        self.start_btn = Button(
            f, text="▶  Bắt đầu", command=self._start,
            bg=ACCENT, fg="white", font=F_BOLD,
            activebackground="#c04010", activeforeground="white",
            relief="flat", padx=22, pady=7, cursor="hand2")
        self.start_btn.pack(side=LEFT, padx=(0, 8))
        self.stop_btn = Button(
            f, text="⬛  Dừng", command=self._stop,
            bg=DIM, fg=BG, font=F_BOLD,
            relief="flat", padx=22, pady=7,
            state=DISABLED, cursor="hand2")
        self.stop_btn.pack(side=LEFT, padx=(0, 8))
        self.pause_btn = Button(
            f, text="⏸  Tạm dừng", command=self._toggle_pause,
            bg=CARD, fg=TEXT, font=F_BOLD,
            activebackground=ACCENT2, activeforeground="white",
            relief="flat", padx=16, pady=7,
            state=DISABLED, cursor="hand2")
        self.pause_btn.pack(side=LEFT, padx=(0, 8))
        self.retry_btn = Button(
            f, text="↺  Thử lại lỗi", command=self._retry_failed,
            bg=CARD, fg=TEXT, font=F_BOLD,
            activebackground=ACCENT, activeforeground="white",
            relief="flat", padx=16, pady=7,
            state=DISABLED, cursor="hand2")
        self.retry_btn.pack(side=LEFT, padx=(0, 8))
        Button(
            f, text="Thống kê", command=self._show_stats,
            bg=ACCENT2, fg="white", font=F_BOLD,
            activebackground="#5a4fa0", activeforeground="white",
            relief="flat", padx=18, pady=7, cursor="hand2",
        ).pack(side=LEFT, padx=(0, 0))
        self.collect_bad_var = BooleanVar(value=False)
        _bind_cfg("p6.collect_bad", self.collect_bad_var)
        Checkbutton(
            f, text="Lấy ảnh xấu",
            variable=self.collect_bad_var,
            bg=BG, fg=TEXT, selectcolor="#251C53",
            activebackground=BG, font=F_MAIN, cursor="hand2",
        ).pack(side=LEFT, padx=(16, 0))
        Button(
            f, text="Xem ảnh xấu", command=self._show_bad_images,
            bg=ACCENT2, fg="white", font=F_MAIN,
            activebackground="#5a4fa0", activeforeground="white",
            relief="flat", padx=12, pady=4, cursor="hand2",
        ).pack(side=LEFT, padx=(8, 0))
        self.merge_btn = Button(
            f, text="Tổng hợp", command=self._consolidate,
            bg="#251C53", fg="white", font=F_MAIN,
            activebackground=ACCENT2, activeforeground="white",
            relief="flat", padx=12, pady=4, cursor="hand2",
        )
        self.merge_btn.pack(side=LEFT, padx=(8, 0))
        Button(
            f, text="Hiệu chỉnh", command=self._migrate_folder,
            bg="#2d4a1e", fg="#a0d080", font=F_MAIN,
            activebackground="#3a6028", activeforeground="white",
            relief="flat", padx=12, pady=4, cursor="hand2",
        ).pack(side=LEFT, padx=(8, 0))
        self.status_lbl = Label(f, text="Sẵn sàng",
                                font=F_MAIN, fg=ACCENT2, bg=BG)
        self.status_lbl.pack(side=RIGHT)

    # ── progress ──────────────────────────────────────────────────────────────

    def _build_progress(self, p):
        self._sep(p, "Tiến độ")
        f = Frame(p, bg=BG)
        f.pack(fill=X, pady=(0, 2))

        pbar_frame = Frame(f, bg=BG)
        pbar_frame.pack(fill=X)
        self.pbar = ttk.Progressbar(pbar_frame, mode="determinate",
                                    style="K.Horizontal.TProgressbar",
                                    maximum=100)
        self.pbar.pack(side=LEFT, fill=X, expand=True, padx=(0, 8))
        self.pct_lbl = Label(pbar_frame, text="0%", font=F_MONO,
                             fg=ACCENT, bg=BG, width=5, anchor=E)
        self.pct_lbl.pack(side=LEFT)
        self.eta_lbl = Label(pbar_frame, text="ETA: --:--", font=F_MONO,
                             fg=DIM, bg=BG, width=12, anchor=W)
        self.eta_lbl.pack(side=LEFT, padx=(6, 0))

        detail_row = Frame(f, bg=BG)
        detail_row.pack(fill=X, pady=(2, 0))
        self.item_lbl = Label(detail_row, text="", font=F_MONO,
                              fg=DIM, bg=BG, anchor=W)
        self.item_lbl.pack(side=LEFT)

        self.stat_lbl = Label(
            f,
            text="Trang: 0  |  SK: 0  |  Tìm: 0  |  Lưu: 0  |  Bỏ qua: 0  |  Lỗi: 0",
            font=F_MONO, fg=TEXT, bg=BG)
        self.stat_lbl.pack(anchor=W, pady=(2, 0))

    # ── dashboard ─────────────────────────────────────────────────────────────

    def _build_dashboard(self, p):
        self._dash_frame = Frame(p, bg=CARD, padx=10, pady=6)
        self._dash_visible = False

    def _show_dashboard(self, s):
        if not self._dash_visible:
            self._dash_frame.pack(fill=X, pady=(4, 2))
            self._dash_visible = True
        for w in self._dash_frame.winfo_children():
            w.destroy()
        Label(self._dash_frame, text="Kết quả lần chạy",
              font=("Segoe UI", 9, "bold"), fg=ACCENT2, bg=CARD).pack(anchor=W)
        row = Frame(self._dash_frame, bg=CARD)
        row.pack(fill=X, pady=(4, 0))
        items = [
            ("Tổng SK",  s.get("event", 0),   TEXT),
            ("Tìm thấy", s.get("found", 0),   TEXT),
            ("Đã lưu",   s.get("saved", 0),   "#4caf50"),
            ("Bỏ qua",   s.get("skipped", 0), DIM),
            ("Lỗi",      s.get("error", 0),   "#ff8844"),
            ("Ảnh xấu",  s.get("bad_saved", 0), ACCENT2),
        ]
        for label, val, color in items:
            cell = Frame(row, bg="#251C53", padx=8, pady=4)
            cell.pack(side=LEFT, padx=(0, 6))
            Label(cell, text=str(val), font=("Segoe UI Semibold", 13),
                  fg=color, bg="#251C53").pack()
            Label(cell, text=label, font=("Segoe UI", 8),
                  fg=DIM, bg="#251C53").pack()
        if self._failed_items:
            Label(self._dash_frame,
                  text=f"{len(self._failed_items)} ảnh lỗi — nhấn 'Thử lại lỗi' để tải lại",
                  font=("Segoe UI", 8), fg="#ff8844", bg=CARD).pack(anchor=W, pady=(4, 0))

    def _hide_dashboard(self):
        if self._dash_visible:
            self._dash_frame.pack_forget()
            self._dash_visible = False

    # ── log ───────────────────────────────────────────────────────────────────

    _THREAD_COLORS = ["#F05922", "#4fc3f7", "#81c784", "#ffb74d",
                      "#f06292", "#ba68c8", "#4dd0e1", "#ff8a65"]
    _LOG_MAX = 2000

    def _build_log(self, p):
        self._sep(p, "Nhật ký")
        f = Frame(p, bg=BG)
        f.pack(fill=BOTH, expand=True)
        f.columnconfigure(0, weight=1)
        f.rowconfigure(0, weight=1)
        self.log_txt = Text(
            f, height=11, font=F_MONO,
            bg="#16162a", fg="#d4d4d4",
            relief="flat", wrap=WORD,
            insertbackground="#d4d4d4", state=DISABLED)
        self.log_txt.grid(row=0, column=0, sticky=NSEW)
        for i, color in enumerate(self._THREAD_COLORS, 1):
            self.log_txt.tag_configure(f"T{i}", foreground=color)
        sb = ttk.Scrollbar(f, command=self.log_txt.yview)
        sb.grid(row=0, column=1, sticky=NS)
        self.log_txt["yscrollcommand"] = sb.set
        Button(f, text="Xóa log",
               command=lambda: (self.log_txt.configure(state=NORMAL),
                                self.log_txt.delete("1.0", END),
                                self.log_txt.configure(state=DISABLED)),
               bg=CARD, fg=DIM, font=F_MAIN,
               relief="flat", padx=8, cursor="hand2").grid(
            row=1, column=0, sticky=W, pady=(4, 0))

    # ── browse ────────────────────────────────────────────────────────────────

    def _open_out(self):
        import os
        p = self.out_var.get().strip()
        if p and os.path.isdir(p):
            os.startfile(p)

    def _browse(self):
        d = filedialog.askdirectory(title="Chọn thư mục lưu ảnh",
                                    initialdir=_cfg_dir("p6.out"))
        if d:
            self.out_var.set(d)
            _push_history("h.p6.out", d)
            self._out_combo["values"] = _get_history("h.p6.out")

    # ── pause ─────────────────────────────────────────────────────────────────

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

    # ── retry ─────────────────────────────────────────────────────────────────

    def _retry_failed(self):
        if not self._failed_items:
            return
        if self._running:
            messagebox.showwarning("Đang chạy", "Vui lòng chờ lần chạy hiện tại kết thúc.")
            return
        items = list(self._failed_items)
        self._failed_items.clear()
        self.retry_btn.config(state=DISABLED)
        self._hide_dashboard()
        cfg = self._last_cfg.copy() if hasattr(self, "_last_cfg") else {}
        cfg["retry_items"] = items
        for _q in (self._log_q, self._stat_q):
            while True:
                try: _q.get_nowait()
                except queue.Empty: break
        self._running = True
        self._paused  = False
        self._pause_event.set()
        self._run_start_time = time.monotonic()
        self._done_count = 0
        self._total_estimate = len(items)
        self.start_btn.config(state=DISABLED)
        self.stop_btn.config(state=NORMAL)
        self.pause_btn.config(state=NORMAL, text="⏸  Tạm dừng", fg=TEXT)
        self.pbar.config(value=0)
        self.pct_lbl.config(text="0%")
        self.eta_lbl.config(text="ETA: --:--")
        self.status_lbl.config(text="Thử lại lỗi...", fg=ACCENT)
        self._log(f"Thử lại {len(items)} ảnh lỗi...")
        self._worker = Parkingv6Worker(cfg, self._log_q, self._stat_q,
                                       pause_event=self._pause_event)
        self._thread = threading.Thread(target=self._run_worker, daemon=True)
        self._thread.start()

    # ── stats window ─────────────────────────────────────────────────────────

    _VTYPE_COLORS = {
        "toan_canh": "#B8B3D6",
        "xe_may":    "#F05922",
        "xe_dap":    "#4A3F8C",
        "xe_tai":    "#FFAA80",
        "o_to":      "#CBCBCB",
    }
    _LANE_PALETTE = ["#F05922", "#4A3F8C", "#B8B3D6", "#FFAA80",
                     "#7c6fc9", "#e87d5a", "#9b8ed4", "#f0a57a"]

    def _show_bad_images(self):
        out = Path(self.out_var.get().strip())
        if hasattr(self, "_bad_win") and self._bad_win.winfo_exists():
            self._bad_win.lift()
            return
        self._bad_win = BadImageViewer(self.root, out / "bad")

    def _show_stats(self):
        out = Path(self.out_var.get().strip())
        if hasattr(self, "_stats_win") and self._stats_win.winfo_exists():
            self._stats_out = out
            self._stats_win.lift()
            self._stats_rebuild()
            return
        win = Toplevel(self.root)
        win.title("Thống kê ảnh đã lưu — Parkingv6")
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
    def _scan_stats(out_path: Path) -> dict:
        from collections import defaultdict
        lt  = defaultdict(lambda: defaultdict(int))
        bd  = defaultdict(lambda: defaultdict(int))
        bhl = defaultdict(lambda: defaultdict(int))
        VTYPES = {"toan_canh", "xe_may", "xe_dap", "xe_tai", "o_to"}
        if out_path.exists():
            for img in out_path.rglob("*.jpg"):
                try:
                    p = img.relative_to(out_path).parts
                    if len(p) == 5:
                        lane, vtype, date_s, hour_s, fname = p
                    elif len(p) == 4:
                        lane, vtype, date_s, fname = p
                        hour_s = fname[:2]
                    else:
                        continue
                    if vtype not in VTYPES:
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
            Label(parent,
                  text="Cần cài matplotlib:\n  pip install matplotlib",
                  bg=BG, fg=DIM, font=F_MAIN, justify=CENTER).pack(expand=True)

    def _stats_tab_summary(self, nb, data, is_chart):
        VTYPES = ["toan_canh", "xe_may", "xe_dap", "xe_tai", "o_to"]
        lanes  = sorted(data["lt"])
        tab = Frame(nb, bg=BG)
        nb.add(tab, text="  Làn × Loại xe  ")
        if not is_chart:
            cols   = ["Làn"] + VTYPES + ["Tổng"]
            widths = [180] + [90] * len(VTYPES) + [80]
            tree   = self._make_tree(tab, cols, widths)
            totals = {v: 0 for v in VTYPES}
            totals["grand"] = 0
            for i, lane in enumerate(lanes):
                row, rt = [lane], 0
                for v in VTYPES:
                    n = data["lt"][lane].get(v, 0)
                    row.append(str(n) if n else "-")
                    totals[v] += n; rt += n
                totals["grand"] += rt
                row.append(str(rt))
                tree.insert("", END, values=row,
                            tags=("odd" if i % 2 else "even",))
            tree.insert("", END,
                        values=("TỔNG", *[str(totals[v]) for v in VTYPES],
                                str(totals["grand"])),
                        tags=("total",))
        else:
            def draw(ax):
                x = range(len(lanes))
                w = 0.15
                for i, vt in enumerate(VTYPES):
                    vals = [data["lt"][l].get(vt, 0) for l in lanes]
                    ax.bar([xi + i * w for xi in x], vals, w,
                           label=vt, color=self._VTYPE_COLORS.get(vt, "#aaa"), zorder=3)
                ax.set_xticks([xi + w * 2 for xi in x])
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
            tree = self._make_tree(tab, cols, widths)
            grand, grand_t = {l: 0 for l in lanes}, 0
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
                        values=("TỔNG", str(grand_t),
                                *[str(grand[l]) for l in lanes]),
                        tags=("total",))
        else:
            def draw(ax):
                bottom = [0] * len(dates)
                for i, lane in enumerate(lanes):
                    vals = [data["date"][d].get(lane, 0) for d in dates]
                    clr  = self._LANE_PALETTE[i % len(self._LANE_PALETTE)]
                    ax.bar(dates, vals, bottom=bottom, label=lane,
                           color=clr, zorder=3)
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
            tree = self._make_tree(tab, cols, widths, anchor_first="center")
            grand, grand_t = {l: 0 for l in lanes}, 0
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
                        values=("TỔNG", str(grand_t),
                                *[str(grand[l]) for l in lanes]),
                        tags=("total",))
        else:
            def draw(ax):
                hrs    = list(range(24))
                bottom = [0] * 24
                for i, lane in enumerate(lanes):
                    vals = [data["hour"].get(h, {}).get(lane, 0) for h in hrs]
                    clr  = self._LANE_PALETTE[i % len(self._LANE_PALETTE)]
                    ax.bar([f"{h:02d}" for h in hrs], vals,
                           bottom=bottom, label=lane, color=clr, zorder=3)
                    bottom = [b + v for b, v in zip(bottom, vals)]
                ax.set_xticklabels([f"{h:02d}" for h in hrs],
                                   fontsize=7, color="#d4d4d4")
                ax.set_title("Phân phối ảnh theo giờ trong ngày",
                             color="#d4d4d4", fontsize=10)
            self._make_chart(tab, draw)

    # ── log helper ────────────────────────────────────────────────────────────

    def _log(self, msg):
        import re as _re
        self.log_txt.configure(state=NORMAL)
        ts   = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}\n"
        m = _re.match(r'\[T(\d+)\]', msg)
        if m:
            tag = f"T{m.group(1)}"
            self.log_txt.insert(END, line, (tag,))
        else:
            self.log_txt.insert(END, line)
        lines = int(self.log_txt.index("end-1c").split(".")[0])
        if lines > self._LOG_MAX:
            self.log_txt.delete("1.0", f"{lines - self._LOG_MAX}.0")
        self.log_txt.see(END)
        self.log_txt.configure(state=DISABLED)

    # ── start ─────────────────────────────────────────────────────────────────

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
        token  = self.cfg_token.get().strip()
        if not from_d or not to_d or not out:
            messagebox.showerror("Thiếu thông tin",
                                 "Vui lòng điền đủ thời gian và thư mục."); return
        if not token:
            messagebox.showerror("Thiếu token",
                                 "Vui lòng nhập Bearer Token trong phần Nâng cao."); return
        try:
            os.makedirs(out, exist_ok=True)
        except Exception as e:
            messagebox.showerror("Lỗi thư mục", str(e)); return

        cfg = {
            "from_date":    from_d,
            "to_date":      to_d,
            "output_dir":   out,
            "page_size":    self.page_size_var.get(),
            "max_pages":    self.max_pages_var.get(),
            "sleep":        self.sleep_var.get(),
            "use_minio":    self.use_minio.get(),
            "max_per_lane": self.max_per_lane_var.get(),
            "max_per_cat":  self.max_per_cat_var.get(),
            "max_per_hour": self.max_per_hour_var.get(),
            "collect_bad":  self.collect_bad_var.get(),
            "parallel":     self.parallel_var.get(),
            "event_source": self.event_source_var.get(),
            "api_url":      self.cfg_api.get().strip(),
            "token":        token,
            "minio_ep":     self.cfg_mep.get().strip(),
            "minio_bucket": self.cfg_mbk.get().strip(),
            "minio_ak":     self.cfg_mak.get().strip(),
            "minio_sk":     self.cfg_msk.get().strip(),
        }
        self._last_cfg = cfg
        self._failed_items.clear()
        self.retry_btn.config(state=DISABLED)
        self._hide_dashboard()

        for _q in (self._log_q, self._stat_q):
            while True:
                try: _q.get_nowait()
                except queue.Empty: break

        self._running = True
        self._paused  = False
        self._pause_event.set()
        self._run_start_time = time.monotonic()
        self._done_count = 0
        self._total_estimate = 0
        self._all_thread_stats.clear()
        self._parallel_workers.clear()
        self.start_btn.config(state=DISABLED)
        self.stop_btn.config(state=NORMAL)
        self.pause_btn.config(state=NORMAL, text="⏸  Tạm dừng", fg=TEXT)
        self.pbar.config(value=0)
        self.pct_lbl.config(text="0%")
        self.eta_lbl.config(text="ETA: --:--")
        self.item_lbl.config(text="")
        self.status_lbl.config(text="Đang chạy...", fg=ACCENT)
        self._log(f"Bắt đầu: {from_d}  →  {to_d}")
        self._log(f"Nguồn: {cfg['event_source']}  |  Lưu vào: {out}")

        parallel = cfg.get("parallel", 1)
        if parallel > 1:
            self._thread = threading.Thread(
                target=self._run_parallel, args=(cfg, parallel), daemon=True)
            self._thread.start()
        else:
            self._worker = Parkingv6Worker(cfg, self._log_q, self._stat_q,
                                           pause_event=self._pause_event)
            self._thread = threading.Thread(target=self._run_worker, daemon=True)
            self._thread.start()

    def _run_worker(self):
        try:
            self._worker.run()
        except Exception as exc:
            self._log_q.put(f"[LỖI] {exc}")
            self._log_q.put("__DONE__")

    def _run_parallel(self, cfg: dict, n: int):
        """Chia ngày ra n luồng, chạy song song."""
        import json as _json
        from pathlib import Path as _Path
        try:
            out = _Path(cfg["output_dir"])
            from_d = cfg["from_date"].strip().replace(" ", "T")
            to_d   = cfg["to_date"].strip().replace(" ", "T")

            all_days = Parkingv6Worker._day_list(from_d, to_d)

            done_days: set = set()
            hist_f = out / Parkingv6Worker._HISTORY_FILE
            try:
                if hist_f.exists():
                    done_days = set(_json.loads(hist_f.read_text(encoding="utf-8")))
                    self._log_q.put(f"Lịch sử: {len(done_days)} ngày đã tải trước đó.")
            except Exception:
                pass

            pending = [d for d in all_days if d[2] not in done_days]
            skipped_hist = len(all_days) - len(pending)

            max_lane = cfg.get("max_per_lane", 0)
            max_cat  = cfg.get("max_per_cat",  0)
            max_hour = cfg.get("max_per_hour", 0)
            limits = []
            if max_lane: limits.append(f"{max_lane} ảnh/làn")
            if max_cat:  limits.append(f"{max_cat} ảnh/loại/làn/ngày")
            if max_hour: limits.append(f"{max_hour} ảnh/giờ/làn")
            self._log_q.put(
                f"Tổng: {len(all_days)} ngày | {n} luồng | page size={cfg['page_size']}")
            self._log_q.put(f"Giới hạn: {', '.join(limits) if limits else 'không'}")

            if skipped_hist:
                self._log_q.put(f"Bỏ qua {skipped_hist} ngày đã tải trước đó.")
            if not pending:
                self._log_q.put("Tất cả ngày đã tải. Không có việc gì để làm.")
                self._log_q.put("__DONE__")
                return

            groups: list = [[] for _ in range(n)]
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
                w = Parkingv6Worker(
                    cfg, self._log_q, self._stat_q,
                    pause_event=self._pause_event,
                    thread_id=tid,
                    days_list=day_group,
                    shared=shared,
                    send_done=False,
                    global_total_days=len(pending),
                )
                w._done_days = set(done_days)
                workers.append(w)

            self._parallel_workers = workers

            threads = [threading.Thread(target=w.run, daemon=True) for w in workers]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            total_ev  = sum(w.stats.get("event",    0) for w in workers)
            total_fd  = sum(w.stats.get("found",    0) for w in workers)
            total_sv  = sum(w.stats.get("saved",    0) for w in workers)
            total_sk  = sum(w.stats.get("skipped",  0) for w in workers)
            total_err = sum(w.stats.get("error",    0) for w in workers)
            total_bad = sum(w.stats.get("bad_saved",0) for w in workers)
            self._log_q.put(f"\n{'═'*52}")
            self._log_q.put(
                f"TỔNG KẾT ({n} luồng, {len(pending)} ngày"
                f"{f', bỏ qua {skipped_hist} đã tải' if skipped_hist else ''}):")
            self._log_q.put(
                f"  SK: {total_ev}  |  Tìm: {total_fd}  |  Lưu: {total_sv}"
                f"  |  Xấu: {total_bad}  |  Bỏ: {total_sk}  |  Lỗi: {total_err}")
            self._log_q.put(f"{'═'*52}")
        except Exception as exc:
            self._log_q.put(f"[LỖI] {exc}")
        finally:
            self._log_q.put("__DONE__")

    # ── stop ──────────────────────────────────────────────────────────────────

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
        self.pbar.stop()
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
            self.retry_btn.config(
                state=NORMAL,
                text=f"↺  Thử lại {len(self._failed_items)} lỗi")
        self._show_dashboard(self._last_stat)

    def _update_progress(self, s):
        saved  = s.get("saved", 0)
        found  = s.get("found", 0)
        total  = s.get("total_found", found) or found
        self._last_stat = s
        current = s.get("current_item", "")
        if current:
            self.item_lbl.config(text=f"Đang xử lý: {current}")
        failed = s.get("failed_items")
        if failed:
            for item in failed:
                if item not in self._failed_items:
                    self._failed_items.append(item)
        if total > 0:
            pct = min(int(saved * 100 / total), 99)
            self.pbar.config(value=pct)
            self.pct_lbl.config(text=f"{pct}%")
            elapsed = time.monotonic() - self._run_start_time
            if saved > 0:
                eta_sec = int(elapsed / saved * (total - saved))
                m, sec = divmod(eta_sec, 60)
                self.eta_lbl.config(text=f"ETA: {m:02d}:{sec:02d}")
        else:
            page = s.get("page", 0)
            if page > 0:
                pct = min(page % 100, 99)
                self.pbar.config(value=pct)
                self.pct_lbl.config(text=f"~{pct}%")

    # ── consolidate ───────────────────────────────────────────────────────────

    def _consolidate(self):
        from .lotte_consolidate import ConsolidateWindow
        out = Path(self.out_var.get().strip())
        if not out.exists():
            messagebox.showerror("Lỗi", "Thư mục không tồn tại."); return
        if hasattr(self, "_consolidate_win") and self._consolidate_win.winfo_exists():
            self._consolidate_win.lift()
            return
        self._consolidate_win = ConsolidateWindow(self.root, out)

    def _migrate_folder(self):
        out = Path(self.out_var.get().strip())
        if not out.exists():
            messagebox.showerror("Lỗi", "Thư mục không tồn tại."); return
        if hasattr(self, "_migrate_win") and self._migrate_win.winfo_exists():
            self._migrate_win.lift(); return
        self._migrate_win = _open_migrate_window(self.root, out)

    # ── poll ──────────────────────────────────────────────────────────────────

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
                self._update_progress(disp)
                self._refresh_stat_lbl(disp)
        except queue.Empty:
            pass
        self.root.after(200, self._poll)

    def _aggregate_stats(self) -> dict:
        all_s = list(self._all_thread_stats.values())
        total_days = all_s[0].get("total_days", 0) if all_s else 0
        items = [x.get("current_item", "") for x in all_s if x.get("current_item")]
        return {
            "event":   sum(x.get("event",    0) for x in all_s),
            "found":   sum(x.get("found",    0) for x in all_s),
            "saved":   sum(x.get("saved",    0) for x in all_s),
            "skipped": sum(x.get("skipped",  0) for x in all_s),
            "error":   sum(x.get("error",    0) for x in all_s),
            "bad_saved":sum(x.get("bad_saved",0) for x in all_s),
            "page":    sum(x.get("page",     0) for x in all_s),
            "day_idx": sum(x.get("day_idx",  0) for x in all_s),
            "total_days": total_days,
            "day_label": f"{len(all_s)} luồng",
            "thread_id": 0,
            "current_item": " | ".join(
                f"T{x.get('thread_id','?')}:{v}" for x, v in zip(all_s, items)),
            "total_found": sum(x.get("total_found", x.get("found", 0)) for x in all_s),
            "_parallel": len(all_s),
        }

    def _refresh_stat_lbl(self, s: dict):
        n_threads  = s.get("_parallel", 0)
        day_idx    = s.get("day_idx", 0)
        total_days = s.get("total_days", 0)
        bad_part   = f"  |  Xấu: {s['bad_saved']}" if s.get("bad_saved") else ""
        if n_threads > 1:
            day_info = (f"[{n_threads} luồng] Ngày: {day_idx}/{total_days}  |  "
                        if total_days else f"[{n_threads} luồng]  ")
        else:
            day_info = (f"Ngày: {s.get('day_label','')} ({day_idx}/{total_days})  |  "
                        if total_days else "")
        self.stat_lbl.config(
            text=(f"{day_info}"
                  f"Trang: {s.get('page',0)}  |  "
                  f"SK: {s.get('event',0)}  |  "
                  f"Tìm: {s.get('found',0)}  |  "
                  f"Lưu: {s.get('saved',0)}"
                  f"{bad_part}  |  "
                  f"Bỏ qua: {s.get('skipped',0)}  |  "
                  f"Lỗi: {s.get('error',0)}"))
