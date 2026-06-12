import os
import queue
import threading
from datetime import datetime
from pathlib import Path
from tkinter import *
from tkinter import filedialog, messagebox, ttk

from .constants import BG, CARD, ACCENT, ACCENT2, TEXT, DIM, F_MAIN, F_BOLD, F_MONO
from .settings import _bind_cfg, _cfg_dir
from .imports import _REQUESTS_OK, _CV2_OK
from .lotte_image import LotteWorker
from .bad_image_viewer import BadImageViewer


class LotteImageTab(Frame):
    def __init__(self, master, root):
        super().__init__(master, bg=BG)
        self.root    = root
        self._worker  = None
        self._thread  = None
        self._log_q   = queue.Queue()
        self._stat_q  = queue.Queue()
        self._running = False   # True chỉ khi worker đang chạy
        self._build()
        self._poll()

    def _build(self):
        top = Frame(self, bg=CARD, padx=16, pady=8)
        top.pack(fill=X)
        Label(top, text="LotteImage — Thu thập & phân loại ảnh bãi đỗ xe",
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
        self._build_log(body)

    def _sep(self, parent, text):
        f = Frame(parent, bg=BG)
        f.pack(fill=X, pady=(8, 3))
        Label(f, text=text, font=("Segoe UI", 9, "bold"),
              fg=ACCENT2, bg=BG).pack(side=LEFT)
        Frame(f, bg=DIM, height=1).pack(side=LEFT, fill=X, expand=True, padx=(8, 0), pady=5)

    def _build_time(self, p):
        self._sep(p, "Khoảng thời gian")
        f = Frame(p, bg=BG)
        f.pack(fill=X)
        Label(f, text="Từ:", bg=BG, fg=TEXT, font=F_MAIN).grid(
            row=0, column=0, padx=(0, 4), sticky=W)
        self.from_var = StringVar(value="2026-05-01 00:00:00")
        _bind_cfg("lotte.from", self.from_var)
        Entry(f, textvariable=self.from_var, width=22,
              bg=CARD, fg=TEXT, insertbackground=TEXT,
              relief="flat", font=F_MAIN, bd=4).grid(row=0, column=1, padx=4)
        Label(f, text="Đến:", bg=BG, fg=TEXT, font=F_MAIN).grid(
            row=0, column=2, padx=(14, 4))
        self.to_var = StringVar(value=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        _bind_cfg("lotte.to", self.to_var)
        Entry(f, textvariable=self.to_var, width=22,
              bg=CARD, fg=TEXT, insertbackground=TEXT,
              relief="flat", font=F_MAIN, bd=4).grid(row=0, column=3, padx=4)
        Label(f, text="Định dạng: YYYY-MM-DD HH:MM:SS",
              font=("Segoe UI", 8), fg=DIM, bg=BG).grid(
            row=1, column=1, columnspan=3, sticky=W, pady=(2, 0))

    def _build_output(self, p):
        self._sep(p, "Thư mục lưu ảnh")
        f = Frame(p, bg=BG)
        f.pack(fill=X)
        f.columnconfigure(0, weight=1)
        self.out_var = StringVar(value=str(Path.cwd() / "images"))
        _bind_cfg("lotte.out", self.out_var)
        Entry(f, textvariable=self.out_var,
              bg=CARD, fg=TEXT, insertbackground=TEXT,
              relief="flat", font=F_MAIN, bd=4).grid(
            row=0, column=0, sticky=EW, padx=(0, 8))
        Button(f, text="Chọn…", command=self._browse,
               bg=ACCENT2, fg="white", font=F_MAIN,
               activebackground=ACCENT, activeforeground="white",
               relief="flat", padx=10, cursor="hand2").grid(row=0, column=1)
        Label(p,
              text="Cấu trúc: <thư mục> / <tên làn> / <loại xe> / <YYYY-MM-DD> / HHmmss_BSX.jpg"
                   "   (loại xe: toan_canh | xe_may | xe_dap | o_to)",
              font=("Segoe UI", 8), fg=DIM, bg=BG, anchor=W).pack(
            fill=X, pady=(3, 0))

    def _build_settings(self, p):
        self._sep(p, "Cài đặt")
        f = Frame(p, bg=BG)
        f.pack(fill=X)
        Label(f, text="Page size:", bg=BG, fg=TEXT, font=F_MAIN).grid(
            row=0, column=0, padx=(0, 4), sticky=W)
        self.page_size_var = IntVar(value=100)
        _bind_cfg("lotte.page_size", self.page_size_var)
        Spinbox(f, from_=10, to=500, textvariable=self.page_size_var,
                width=7, font=F_MAIN, bg=CARD, fg=TEXT,
                insertbackground=TEXT, buttonbackground=ACCENT2,
                relief="flat").grid(row=0, column=1, padx=4)
        Label(f, text="Max pages:", bg=BG, fg=TEXT, font=F_MAIN).grid(
            row=0, column=2, padx=(12, 4))
        self.max_pages_var = IntVar(value=10000)
        _bind_cfg("lotte.max_pages", self.max_pages_var)
        Spinbox(f, from_=1, to=99999, textvariable=self.max_pages_var,
                width=8, font=F_MAIN, bg=CARD, fg=TEXT,
                insertbackground=TEXT, buttonbackground=ACCENT2,
                relief="flat").grid(row=0, column=3, padx=4)
        Label(f, text="Nghỉ (s):", bg=BG, fg=TEXT, font=F_MAIN).grid(
            row=0, column=4, padx=(12, 4))
        self.sleep_var = DoubleVar(value=0.1)
        _bind_cfg("lotte.sleep", self.sleep_var)
        Entry(f, textvariable=self.sleep_var, width=6,
              bg=CARD, fg=TEXT, insertbackground=TEXT,
              relief="flat", font=F_MAIN, bd=4).grid(row=0, column=5, padx=4)
        self.use_minio = BooleanVar(value=True)
        _bind_cfg("lotte.use_minio", self.use_minio)
        Checkbutton(f, text="MinIO", variable=self.use_minio,
                    bg=BG, fg=TEXT, selectcolor=CARD,
                    activebackground=BG, font=F_MAIN).grid(
            row=0, column=6, padx=(14, 0))

        # Row 1 — giới hạn lưu ảnh
        Label(f, text="Max ảnh/làn:", bg=BG, fg=TEXT, font=F_MAIN).grid(
            row=1, column=0, padx=(0, 4), sticky=W, pady=(6, 0))
        self.max_per_lane_var = IntVar(value=1000)
        _bind_cfg("lotte.max_per_lane", self.max_per_lane_var)
        Spinbox(f, from_=0, to=999999, textvariable=self.max_per_lane_var,
                width=8, font=F_MAIN, bg=CARD, fg=TEXT,
                insertbackground=TEXT, buttonbackground=ACCENT2,
                relief="flat").grid(row=1, column=1, padx=4, pady=(6, 0))
        Label(f, text="Max ảnh/loại/làn:", bg=BG, fg=TEXT, font=F_MAIN).grid(
            row=1, column=2, padx=(12, 4), sticky=W, pady=(6, 0))
        self.max_per_cat_var = IntVar(value=0)
        _bind_cfg("lotte.max_per_cat", self.max_per_cat_var)
        Spinbox(f, from_=0, to=999999, textvariable=self.max_per_cat_var,
                width=8, font=F_MAIN, bg=CARD, fg=TEXT,
                insertbackground=TEXT, buttonbackground=ACCENT2,
                relief="flat").grid(row=1, column=3, padx=4, pady=(6, 0))
        Label(f, text="Max ảnh/giờ/làn:", bg=BG, fg=TEXT, font=F_MAIN).grid(
            row=1, column=4, padx=(12, 4), sticky=W, pady=(6, 0))
        self.max_per_hour_var = IntVar(value=0)
        _bind_cfg("lotte.max_per_hour", self.max_per_hour_var)
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

        # Phân loại phương tiện
        self._sep(p, "Phân loại phương tiện")
        fv = Frame(p, bg=BG)
        fv.pack(fill=X)
        _vtype_rows = [
            ("Toàn cảnh (mô tả ảnh):", "kw_toan_canh", "toàn cảnh"),
            ("Xe máy (tên nhóm thẻ):",  "kw_xe_may",    "xe máy"),
            ("Xe đạp (tên nhóm thẻ):",  "kw_xe_dap",    "xe đạp"),
            ("Ô tô (tên nhóm thẻ):",    "kw_o_to",      ""),
        ]
        for _r, (_lbl, _attr, _default) in enumerate(_vtype_rows):
            Label(fv, text=_lbl, bg=BG, fg=TEXT, font=F_MAIN).grid(
                row=_r, column=0, padx=(0, 6), sticky=W, pady=2)
            _var = StringVar(value=_default)
            setattr(self, _attr, _var)
            _bind_cfg(f"lotte.{_attr}", _var)
            Entry(fv, textvariable=_var, width=46,
                  bg=CARD, fg=TEXT, insertbackground=TEXT,
                  relief="flat", font=F_MAIN, bd=4).grid(
                row=_r, column=1, sticky=W, padx=4, pady=2)
        Label(p, text="Nhiều từ khóa cách nhau bởi dấu phẩy  •  Ô tô = mặc định nếu không khớp từ khóa nào",
              font=("Segoe UI", 8), fg=DIM, bg=BG, anchor=W).pack(fill=X, pady=(2, 6))

        adv_bar = Frame(p, bg=BG)
        adv_bar.pack(fill=X, pady=(5, 0))
        self._adv_open = False
        self._adv_lbl  = Label(adv_bar, text="▶ Nâng cao (API / MinIO)",
                               font=("Segoe UI", 8, "underline"),
                               fg=ACCENT2, bg=BG, cursor="hand2")
        self._adv_lbl.pack(anchor=W)
        self._adv_lbl.bind("<Button-1>", self._toggle_adv)
        self._adv_frame = Frame(p, bg=CARD, bd=1, relief="flat", padx=8, pady=6)
        self._build_adv(self._adv_frame)

    def _build_adv(self, p):
        from .constants import (
            _LI_API_BASE, _LI_USERNAME, _LI_PASSWORD,
            _LI_MINIO_EP, _LI_MINIO_BUCKET, _LI_MINIO_AK, _LI_MINIO_SK,
        )
        fields = [
            ("API URL:",        "cfg_api",  _LI_API_BASE,     38, ""),
            ("Username:",       "cfg_user", _LI_USERNAME,     16, ""),
            ("Password:",       "cfg_pass", _LI_PASSWORD,     16, "*"),
            ("MinIO endpoint:", "cfg_mep",  _LI_MINIO_EP,     26, ""),
            ("MinIO bucket:",   "cfg_mbk",  _LI_MINIO_BUCKET, 20, ""),
            ("MinIO AK:",       "cfg_mak",  _LI_MINIO_AK,     16, ""),
            ("MinIO SK:",       "cfg_msk",  _LI_MINIO_SK,     20, "*"),
        ]
        for i, (lbl, attr, default, width, show) in enumerate(fields):
            r, c = divmod(i, 2)
            Label(p, text=lbl, font=("Segoe UI", 8),
                  bg=CARD, fg=DIM).grid(
                row=r, column=c * 2,
                padx=(0 if c == 0 else 16, 4), pady=2, sticky=W)
            var = StringVar(value=default)
            setattr(self, attr, var)
            _bind_cfg(f"lotte.{attr}", var)
            Entry(p, textvariable=var, width=width, show=show,
                  bg="#16162a", fg=TEXT, insertbackground=TEXT,
                  relief="flat", font=F_MAIN, bd=4).grid(
                row=r, column=c * 2 + 1, padx=(0, 4), pady=2)

    def _toggle_adv(self, _=None):
        self._adv_open = not self._adv_open
        if self._adv_open:
            self._adv_frame.pack(fill=X, pady=(0, 4))
            self._adv_lbl.config(text="▼ Nâng cao (API / MinIO)")
        else:
            self._adv_frame.pack_forget()
            self._adv_lbl.config(text="▶ Nâng cao (API / MinIO)")

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
        self.stop_btn.pack(side=LEFT)
        Button(
            f, text="Thống kê", command=self._show_stats,
            bg=ACCENT2, fg="white", font=F_BOLD,
            activebackground="#5a4fa0", activeforeground="white",
            relief="flat", padx=18, pady=7, cursor="hand2",
        ).pack(side=LEFT, padx=(8, 0))
        self.collect_bad_var = BooleanVar(value=False)
        _bind_cfg("lotte.collect_bad", self.collect_bad_var)
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
        f.pack(fill=X, pady=(0, 4))
        self.pbar = ttk.Progressbar(f, mode="indeterminate",
                                    style="K.Horizontal.TProgressbar")
        self.pbar.pack(side=LEFT, fill=X, expand=True, padx=(0, 12))
        self.stat_lbl = Label(
            f,
            text="Trang: 0  |  SK: 0  |  Tìm: 0  |  Lưu: 0  |  Bỏ qua: 0  |  Lỗi: 0",
            font=F_MONO, fg=TEXT, bg=BG)
        self.stat_lbl.pack(side=LEFT)

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

    def _browse(self):
        d = filedialog.askdirectory(title="Chọn thư mục lưu ảnh",
                                    initialdir=_cfg_dir("lotte.out"))
        if d:
            self.out_var.set(d)

    # ── Thống kê ─────────────────────────────────────────────────────────────

    _VTYPE_COLORS = {
        "toan_canh": "#B8B3D6",
        "xe_may":    "#F05922",
        "xe_dap":    "#4A3F8C",
        "o_to":      "#CBCBCB",
    }
    _LANE_PALETTE = ["#F05922","#4A3F8C","#B8B3D6","#FFAA80",
                     "#7c6fc9","#e87d5a","#9b8ed4","#f0a57a"]

    def _show_bad_images(self):
        out = Path(self.out_var.get().strip())
        if hasattr(self, "_bad_win") and self._bad_win.winfo_exists():
            self._bad_win.lift()
            return
        self._bad_win = BadImageViewer(self.root, out)

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

        # ── toolbar ──
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
        """Embed matplotlib figure. Falls back to message if not installed."""
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

    # ── Tab 1: Làn × Loại xe ─────────────────────────────────────────────────

    def _stats_tab_summary(self, nb, data, is_chart):
        VTYPES = ["toan_canh", "xe_may", "xe_dap", "o_to"]
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

    # ── Tab 2: Theo ngày ─────────────────────────────────────────────────────

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

    # ── Tab 3: Theo giờ ──────────────────────────────────────────────────────

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

    # ─────────────────────────────────────────────────────────────────────────

    _LOG_MAX = 1000  # số dòng tối đa

    def _log(self, msg):
        self.log_txt.configure(state=NORMAL)
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_txt.insert(END, f"[{ts}] {msg}\n")
        # xoá dòng cũ nếu vượt giới hạn
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
            "api_base":     self.cfg_api.get().strip(),
            "username":     self.cfg_user.get().strip(),
            "password":     self.cfg_pass.get().strip(),
            "minio_ep":     self.cfg_mep.get().strip(),
            "minio_bucket": self.cfg_mbk.get().strip(),
            "minio_ak":     self.cfg_mak.get().strip(),
            "minio_sk":     self.cfg_msk.get().strip(),
            "kw_toan_canh": self.kw_toan_canh.get().strip(),
            "kw_xe_may":    self.kw_xe_may.get().strip(),
            "kw_xe_dap":    self.kw_xe_dap.get().strip(),
            "kw_o_to":      self.kw_o_to.get().strip(),
        }
        # xoá message cũ còn sót từ lần chạy trước
        for _q in (self._log_q, self._stat_q):
            while True:
                try: _q.get_nowait()
                except queue.Empty: break

        self._running = True
        self.start_btn.config(state=DISABLED)
        self.stop_btn.config(state=NORMAL)
        self.pbar.start(12)
        self.status_lbl.config(text="Đang chạy...", fg=ACCENT)
        self._log(f"Bắt đầu: {from_d}  →  {to_d}")
        self._log(f"Lưu vào: {out}")
        self._worker = LotteWorker(cfg, self._log_q, self._stat_q)
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
        self.stop_btn.config(state=DISABLED)
        self.start_btn.config(state=NORMAL)
        self.pbar.stop()
        self.status_lbl.config(text="Đã dừng", fg=DIM)

    def _on_done(self):
        if not self._running:   # user đã bấm Dừng → đã reset rồi
            return
        self._running = False
        self.pbar.stop()
        self.start_btn.config(state=NORMAL)
        self.stop_btn.config(state=DISABLED)
        self.status_lbl.config(text="Hoàn thành", fg=ACCENT2)

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
