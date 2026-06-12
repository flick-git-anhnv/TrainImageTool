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
    _P8_LOGIN_URL, _P8_API_URL, _P8_CLIENT_ID, _P8_CLIENT_SECRET,
    _P8_USERNAME, _P8_PASSWORD,
)
from .settings import _bind_cfg, _cfg_dir
from .imports import _REQUESTS_OK, _CV2_OK
from .parkingv8_image import Parkingv8Worker
from .bad_image_viewer import BadImageViewer


class Parkingv8ImageTab(Frame):
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
        self._last_stat = {}
        self._build()
        self._poll()

    # ── layout ───────────────────────────────────────────────────────────────

    def _build(self):
        top = Frame(self, bg=CARD, padx=16, pady=8)
        top.pack(fill=X)
        Label(top, text="Parkingv8Image — Thu thập & phân loại ảnh iParkingv8",
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
        Frame(f, bg=DIM, height=1).pack(side=LEFT, fill=X, expand=True,
                                         padx=(8, 0), pady=5)

    def _build_time(self, p):
        self._sep(p, "Khoảng thời gian (UTC)")
        f = Frame(p, bg=BG)
        f.pack(fill=X)
        Label(f, text="Từ:", bg=BG, fg=TEXT, font=F_MAIN).grid(
            row=0, column=0, padx=(0, 4), sticky=W)
        self.from_var = StringVar(value="2026-05-01 00:00:00")
        _bind_cfg("p8.from", self.from_var)
        Entry(f, textvariable=self.from_var, width=22,
              bg=CARD, fg=TEXT, insertbackground=TEXT,
              relief="flat", font=F_MAIN, bd=4).grid(row=0, column=1, padx=4)
        Label(f, text="Đến:", bg=BG, fg=TEXT, font=F_MAIN).grid(
            row=0, column=2, padx=(14, 4))
        self.to_var = StringVar(value=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))
        _bind_cfg("p8.to", self.to_var)
        Entry(f, textvariable=self.to_var, width=22,
              bg=CARD, fg=TEXT, insertbackground=TEXT,
              relief="flat", font=F_MAIN, bd=4).grid(row=0, column=3, padx=4)
        Label(f, text="Định dạng: YYYY-MM-DD HH:MM:SS  (giờ UTC — Việt Nam = UTC+7)",
              font=("Segoe UI", 8), fg=DIM, bg=BG).grid(
            row=1, column=1, columnspan=3, sticky=W, pady=(2, 0))

    def _build_output(self, p):
        self._sep(p, "Thư mục lưu ảnh")
        f = Frame(p, bg=BG)
        f.pack(fill=X)
        f.columnconfigure(0, weight=1)
        self.out_var = StringVar(value=str(Path.cwd() / "images_p8"))
        _bind_cfg("p8.out", self.out_var)
        Entry(f, textvariable=self.out_var,
              bg=CARD, fg=TEXT, insertbackground=TEXT,
              relief="flat", font=F_MAIN, bd=4).grid(
            row=0, column=0, sticky=EW, padx=(0, 8))
        Button(f, text="Chọn…", command=self._browse,
               bg=ACCENT2, fg="white", font=F_MAIN,
               activebackground=ACCENT, activeforeground="white",
               relief="flat", padx=10, cursor="hand2").grid(row=0, column=1)
        Label(p,
              text="Cấu trúc: <thư mục> / <tên làn> / <loại xe> / <YYYY-MM-DD> / HHmmss_BSX_type.jpg"
                   "   (loại xe: o_to | xe_may | xe_dap | xe_tai)",
              font=("Segoe UI", 8), fg=DIM, bg=BG, anchor=W).pack(
            fill=X, pady=(3, 0))

    def _build_settings(self, p):
        self._sep(p, "Cài đặt")
        f = Frame(p, bg=BG)
        f.pack(fill=X)

        Label(f, text="Page size:", bg=BG, fg=TEXT, font=F_MAIN).grid(
            row=0, column=0, padx=(0, 4), sticky=W)
        self.page_size_var = IntVar(value=100)
        _bind_cfg("p8.page_size", self.page_size_var)
        Spinbox(f, from_=10, to=500, textvariable=self.page_size_var,
                width=7, font=F_MAIN, bg=CARD, fg=TEXT,
                insertbackground=TEXT, buttonbackground=ACCENT2,
                relief="flat").grid(row=0, column=1, padx=4)

        Label(f, text="Max pages:", bg=BG, fg=TEXT, font=F_MAIN).grid(
            row=0, column=2, padx=(12, 4))
        self.max_pages_var = IntVar(value=10000)
        _bind_cfg("p8.max_pages", self.max_pages_var)
        Spinbox(f, from_=1, to=99999, textvariable=self.max_pages_var,
                width=8, font=F_MAIN, bg=CARD, fg=TEXT,
                insertbackground=TEXT, buttonbackground=ACCENT2,
                relief="flat").grid(row=0, column=3, padx=4)

        Label(f, text="Nghỉ (s):", bg=BG, fg=TEXT, font=F_MAIN).grid(
            row=0, column=4, padx=(12, 4))
        self.sleep_var = DoubleVar(value=0.1)
        _bind_cfg("p8.sleep", self.sleep_var)
        Entry(f, textvariable=self.sleep_var, width=6,
              bg=CARD, fg=TEXT, insertbackground=TEXT,
              relief="flat", font=F_MAIN, bd=4).grid(row=0, column=5, padx=4)

        Label(f, text="Nguồn:", bg=BG, fg=TEXT, font=F_MAIN).grid(
            row=0, column=6, padx=(14, 4))
        self.source_var = StringVar(value="exits")
        _bind_cfg("p8.source", self.source_var)
        src_cb = ttk.Combobox(f, textvariable=self.source_var,
                              values=["exits", "entries", "both"],
                              width=9, state="readonly", font=F_MAIN)
        src_cb.grid(row=0, column=7, padx=4)

        Label(f, text="Max ảnh/làn:", bg=BG, fg=TEXT, font=F_MAIN).grid(
            row=1, column=0, padx=(0, 4), sticky=W, pady=(6, 0))
        self.max_per_lane_var = IntVar(value=1000)
        _bind_cfg("p8.max_per_lane", self.max_per_lane_var)
        Spinbox(f, from_=0, to=999999, textvariable=self.max_per_lane_var,
                width=8, font=F_MAIN, bg=CARD, fg=TEXT,
                insertbackground=TEXT, buttonbackground=ACCENT2,
                relief="flat").grid(row=1, column=1, padx=4, pady=(6, 0))

        Label(f, text="Max ảnh/loại/làn:", bg=BG, fg=TEXT, font=F_MAIN).grid(
            row=1, column=2, padx=(12, 4), sticky=W, pady=(6, 0))
        self.max_per_cat_var = IntVar(value=0)
        _bind_cfg("p8.max_per_cat", self.max_per_cat_var)
        Spinbox(f, from_=0, to=999999, textvariable=self.max_per_cat_var,
                width=8, font=F_MAIN, bg=CARD, fg=TEXT,
                insertbackground=TEXT, buttonbackground=ACCENT2,
                relief="flat").grid(row=1, column=3, padx=4, pady=(6, 0))

        Label(f, text="Max ảnh/giờ/làn:", bg=BG, fg=TEXT, font=F_MAIN).grid(
            row=1, column=4, padx=(12, 4), sticky=W, pady=(6, 0))
        self.max_per_hour_var = IntVar(value=0)
        _bind_cfg("p8.max_per_hour", self.max_per_hour_var)
        Spinbox(f, from_=0, to=99999, textvariable=self.max_per_hour_var,
                width=7, font=F_MAIN, bg=CARD, fg=TEXT,
                insertbackground=TEXT, buttonbackground=ACCENT2,
                relief="flat").grid(row=1, column=5, padx=4, pady=(6, 0))
        Label(f, text="(0 = không giới hạn)", bg=BG, fg=DIM,
              font=("Segoe UI", 8)).grid(
            row=1, column=6, columnspan=2, padx=(4, 0), sticky=W, pady=(6, 0))
        Label(f,
              text="Max ảnh/làn: tổng cả lần chạy  "
                   "•  Max ảnh/loại/làn: tối đa mỗi ngày/loại/làn  "
                   "•  Max ảnh/giờ/làn: trải đều các giờ trong ngày",
              font=("Segoe UI", 7), fg=DIM, bg=BG).grid(
            row=2, column=0, columnspan=8, sticky=W, pady=(3, 0))

        self._sep(p, "Phân loại phương tiện")
        fv = Frame(p, bg=BG)
        fv.pack(fill=X)
        _vtype_rows = [
            ("Xe máy (vehicleType):", "kw_xe_may", "motor, xe_may"),
            ("Xe đạp (vehicleType):",  "kw_xe_dap", "bicycle, xe_dap"),
            ("Xe tải (vehicleType):",  "kw_xe_tai", "bus, truck, xe_tai"),
            ("Ô tô (vehicleType):",    "kw_o_to",   ""),
        ]
        for _r, (_lbl, _attr, _default) in enumerate(_vtype_rows):
            Label(fv, text=_lbl, bg=BG, fg=TEXT, font=F_MAIN).grid(
                row=_r, column=0, padx=(0, 6), sticky=W, pady=2)
            _var = StringVar(value=_default)
            setattr(self, _attr, _var)
            _bind_cfg(f"p8.{_attr}", _var)
            Entry(fv, textvariable=_var, width=46,
                  bg=CARD, fg=TEXT, insertbackground=TEXT,
                  relief="flat", font=F_MAIN, bd=4).grid(
                row=_r, column=1, sticky=W, padx=4, pady=2)
        Label(p, text="Nhiều từ khóa cách nhau bởi dấu phẩy  •  Ô tô = mặc định nếu không khớp  "
                      "•  Ảnh xấu bỏ qua: xe đạp + ảnh toàn cảnh (fi/fo/full)",
              font=("Segoe UI", 8), fg=DIM, bg=BG, anchor=W).pack(fill=X, pady=(2, 6))

        adv_wrapper = Frame(p, bg=BG)
        adv_wrapper.pack(fill=X, pady=(5, 0))
        self._adv_open = False
        adv_bar = Frame(adv_wrapper, bg=BG)
        adv_bar.pack(fill=X)
        self._adv_lbl  = Label(adv_bar, text="▶ Nâng cao (API / Xác thực)",
                               font=("Segoe UI", 8, "underline"),
                               fg=ACCENT2, bg=BG, cursor="hand2")
        self._adv_lbl.pack(anchor=W)
        self._adv_lbl.bind("<Button-1>", self._toggle_adv)
        self._adv_frame = Frame(adv_wrapper, bg=CARD, bd=1, relief="flat", padx=8, pady=6)
        self._build_adv(self._adv_frame)

    def _build_adv(self, p):
        gt_row = Frame(p, bg=CARD)
        gt_row.grid(row=0, column=0, columnspan=4, sticky=W, pady=(0, 6))
        Label(gt_row, text="Grant type:", font=("Segoe UI", 8),
              bg=CARD, fg=DIM).pack(side=LEFT, padx=(0, 8))
        self.grant_var = StringVar(value="client_credentials")
        _bind_cfg("p8.grant_type", self.grant_var)
        for val, lbl in [("client_credentials", "Client Credentials"),
                         ("password", "Password (username/password)")]:
            Radiobutton(gt_row, text=lbl, variable=self.grant_var, value=val,
                        bg=CARD, fg=TEXT, selectcolor=CARD,
                        activebackground=CARD, font=("Segoe UI", 8),
                        ).pack(side=LEFT, padx=6)

        fields = [
            ("Login URL:",     "cfg_login_url",    _P8_LOGIN_URL,    32, ""),
            ("API URL:",       "cfg_api_url",       _P8_API_URL,      32, ""),
            ("Client ID:",     "cfg_client_id",     _P8_CLIENT_ID,    20, ""),
            ("Client Secret:", "cfg_client_secret", _P8_CLIENT_SECRET,24, "*"),
            ("Username:",      "cfg_user",          _P8_USERNAME,     20, ""),
            ("Password:",      "cfg_pass",          _P8_PASSWORD,     20, "*"),
        ]
        for i, (lbl, attr, default, width, show) in enumerate(fields):
            r, c = divmod(i, 2)
            r += 1
            Label(p, text=lbl, font=("Segoe UI", 8),
                  bg=CARD, fg=DIM).grid(
                row=r, column=c * 2,
                padx=(0 if c == 0 else 16, 4), pady=2, sticky=W)
            var = StringVar(value=default)
            setattr(self, attr, var)
            _bind_cfg(f"p8.{attr}", var)
            Entry(p, textvariable=var, width=width, show=show,
                  bg="#16162a", fg=TEXT, insertbackground=TEXT,
                  relief="flat", font=F_MAIN, bd=4).grid(
                row=r, column=c * 2 + 1, padx=(0, 4), pady=2)

    def _toggle_adv(self, _=None):
        self._adv_open = not self._adv_open
        if self._adv_open:
            self._adv_frame.pack(fill=X, pady=(0, 4))
            self._adv_lbl.config(text="▼ Nâng cao (API / Xác thực)")
        else:
            self._adv_frame.pack_forget()
            self._adv_lbl.config(text="▶ Nâng cao (API / Xác thực)")

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
        ).pack(side=LEFT)
        self.collect_bad_var = BooleanVar(value=False)
        _bind_cfg("p8.collect_bad", self.collect_bad_var)
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
        self.status_lbl = Label(f, text="Sẵn sàng",
                                font=F_MAIN, fg=ACCENT2, bg=BG)
        self.status_lbl.pack(side=RIGHT)

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
            ("Tổng SK",    s.get("event", 0),   TEXT),
            ("Tìm thấy",   s.get("found", 0),   TEXT),
            ("Đã lưu",     s.get("saved", 0),   "#4caf50"),
            ("Bỏ qua",     s.get("skipped", 0), DIM),
            ("Lỗi",        s.get("error", 0),   "#ff8844"),
            ("Ảnh xấu",    s.get("bad_saved", 0), ACCENT2),
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

    # ── actions ───────────────────────────────────────────────────────────────

    def _browse(self):
        d = filedialog.askdirectory(title="Chọn thư mục lưu ảnh",
                                    initialdir=_cfg_dir("p8.out"))
        if d:
            self.out_var.set(d)

    # ── pause/resume ──────────────────────────────────────────────────────────

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

    # ── retry failed ──────────────────────────────────────────────────────────

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
        self.start_btn.config(state=DISABLED)
        self.stop_btn.config(state=NORMAL)
        self.pause_btn.config(state=NORMAL, text="⏸  Tạm dừng", fg=TEXT)
        self.pbar.config(value=0)
        self.pct_lbl.config(text="0%")
        self.eta_lbl.config(text="ETA: --:--")
        self.status_lbl.config(text="Thử lại lỗi...", fg=ACCENT)
        self._log(f"Thử lại {len(items)} ảnh lỗi...")
        self._worker = Parkingv8Worker(cfg, self._log_q, self._stat_q,
                                       pause_event=self._pause_event)
        self._thread = threading.Thread(target=self._run_worker, daemon=True)
        self._thread.start()

    _LOG_MAX = 1000

    def _log(self, msg):
        self.log_txt.configure(state=NORMAL)
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_txt.insert(END, f"[{ts}] {msg}\n")
        lines = int(self.log_txt.index("end-1c").split(".")[0])
        if lines > self._LOG_MAX:
            self.log_txt.delete("1.0", f"{lines - self._LOG_MAX}.0")
        self.log_txt.see(END)
        self.log_txt.configure(state=DISABLED)

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

        cfg = {
            "from_date":     from_d,
            "to_date":       to_d,
            "output_dir":    out,
            "page_size":     self.page_size_var.get(),
            "max_pages":     self.max_pages_var.get(),
            "sleep":         self.sleep_var.get(),
            "event_source":  self.source_var.get(),
            "max_per_lane":  self.max_per_lane_var.get(),
            "max_per_cat":   self.max_per_cat_var.get(),
            "max_per_hour":  self.max_per_hour_var.get(),
            "collect_bad":   self.collect_bad_var.get(),
            "login_url":     self.cfg_login_url.get().strip(),
            "api_url":       self.cfg_api_url.get().strip(),
            "grant_type":    self.grant_var.get(),
            "client_id":     self.cfg_client_id.get().strip(),
            "client_secret": self.cfg_client_secret.get().strip(),
            "username":      self.cfg_user.get().strip(),
            "password":      self.cfg_pass.get().strip(),
            "kw_xe_may":     self.kw_xe_may.get().strip(),
            "kw_xe_dap":     self.kw_xe_dap.get().strip(),
            "kw_xe_tai":     self.kw_xe_tai.get().strip(),
            "kw_o_to":       self.kw_o_to.get().strip(),
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
        self.start_btn.config(state=DISABLED)
        self.stop_btn.config(state=NORMAL)
        self.pause_btn.config(state=NORMAL, text="⏸  Tạm dừng", fg=TEXT)
        self.pbar.config(value=0)
        self.pct_lbl.config(text="0%")
        self.eta_lbl.config(text="ETA: --:--")
        self.item_lbl.config(text="")
        self.status_lbl.config(text="Đang chạy...", fg=ACCENT)
        self._log(f"Bắt đầu: {from_d}  →  {to_d}")
        self._log(f"Lưu vào: {out}")
        self._log(f"Nguồn: {cfg['event_source']} | Grant: {cfg['grant_type']}")
        self._worker = Parkingv8Worker(cfg, self._log_q, self._stat_q,
                                       pause_event=self._pause_event)
        self._thread = threading.Thread(target=self._run_worker, daemon=True)
        self._thread.start()

    def _run_worker(self):
        try:
            self._worker.run()
        except Exception as exc:
            self._log_q.put(f"[LỖI] {exc}")
            self._log_q.put("__DONE__")

    def _stop(self):
        if self._worker:
            self._worker.stop()
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
                self._update_progress(s)
                day_info = (
                    f"Ngày: {s['day_label']} ({s['day_idx']}/{s['total_days']})  |  "
                    if s.get("total_days") else "")
                bad_part = (f"  |  Xấu: {s['bad_saved']}"
                            if s.get("bad_saved") else "")
                self.stat_lbl.config(
                    text=(f"{day_info}"
                          f"Trang: {s['page']}  |  "
                          f"SK: {s['event']}  |  "
                          f"Tìm: {s['found']}  |  "
                          f"Lưu: {s['saved']}"
                          f"{bad_part}  |  "
                          f"Bỏ qua: {s.get('skipped', 0)}  |  "
                          f"Lỗi: {s['error']}"))
        except queue.Empty:
            pass
        self.root.after(200, self._poll)

    # ── statistics popup ──────────────────────────────────────────────────────

    def _show_bad_images(self):
        out = Path(self.out_var.get().strip())
        if hasattr(self, "_bad_win") and self._bad_win.winfo_exists():
            self._bad_win.lift()
            return
        self._bad_win = BadImageViewer(self.root, out)

    _VTYPE_COLORS = {
        "o_to":   "#4A3F8C",
        "xe_may": "#F05922",
        "xe_dap": "#B8B3D6",
        "xe_tai": "#CBCBCB",
    }
    _LANE_PALETTE = ["#F05922","#4A3F8C","#B8B3D6","#FFAA80",
                     "#7c6fc9","#e87d5a","#9b8ed4","#f0a57a"]

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
            Label(self._stats_body, text=f"Không tìm thấy ảnh trong:\n{out}",
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
        if out_path.exists():
            for img in out_path.rglob("*.jpg"):
                try:
                    p = img.relative_to(out_path).parts
                    if len(p) != 4:
                        continue
                    lane, vtype, date_s, fname = p
                except Exception:
                    continue
                lt[lane][vtype]  += 1
                bd[date_s][lane] += 1
                h = fname[:2]
                if h.isdigit() and 0 <= int(h) <= 23:
                    bhl[int(h)][lane] += 1
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
        VTYPES = ["o_to", "xe_may", "xe_dap", "xe_tai"]
        lanes  = sorted(data["lt"])
        tab = Frame(nb, bg=BG)
        nb.add(tab, text="  Làn × Loại xe  ")

        if not is_chart:
            cols   = ["Làn"] + VTYPES + ["Tổng"]
            widths = [180] + [90] * len(VTYPES) + [80]
            tree = self._make_tree(tab, cols, widths)
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
                w = 0.18
                for i, vt in enumerate(VTYPES):
                    vals = [data["lt"][l].get(vt, 0) for l in lanes]
                    ax.bar([xi + i * w for xi in x], vals, w,
                           label=vt, color=self._VTYPE_COLORS[vt], zorder=3)
                ax.set_xticks([xi + w * 1.5 for xi in x])
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
