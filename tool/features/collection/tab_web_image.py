import queue
import threading
from tkinter import *
from tkinter import filedialog, ttk

from ...core.constants import BG, CARD, ACCENT, ACCENT2, TEXT, DIM, F_MAIN, F_BOLD, F_MONO
from ...core.imports import _DDGS_OK, _REQUESTS_OK
from ...core.settings import _CFG, _cfg_save, _bind_cfg, _cfg_dir
from .web_image import WebImageWorker, _DEFAULT_KEYWORDS


class WebImageTab(Frame):
    """Tab thu thập ảnh từ Bing/Google theo keyword → anh_chua_co/."""

    _LOG_MAX = 1500

    def __init__(self, master, root):
        super().__init__(master, bg=BG)
        self.root     = root
        self._worker: WebImageWorker | None = None
        self._thread:  threading.Thread | None = None
        self._log_q   = queue.Queue()
        self._stat_q  = queue.Queue()
        self._running = False
        self._build()
        self._poll()

    # ── Layout ───────────────────────────────────────────────────────────────

    def _build(self):
        hdr = Frame(self, bg=CARD, padx=16, pady=8)
        hdr.pack(fill=X)
        Label(hdr, text="Web Image — Thu thập ảnh từ Bing/Google để label",
              bg=CARD, fg=TEXT, font=F_BOLD).pack(side=LEFT)
        if not _DDGS_OK:
            Label(hdr, text="  ⚠ pip install duckduckgo-search",
                  bg=CARD, fg="#ff8844", font=("Segoe UI", 9)).pack(side=LEFT, padx=8)
        if not _REQUESTS_OK:
            Label(hdr, text="  ⚠ pip install requests",
                  bg=CARD, fg="#ff8844", font=("Segoe UI", 9)).pack(side=LEFT, padx=8)

        canvas = Canvas(self, bg=BG, highlightthickness=0)
        vsb = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=RIGHT, fill=Y)
        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        inner = Frame(canvas, bg=BG)
        cwin  = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(cwin, width=e.width))
        inner.bind("<Configure>", lambda _: canvas.configure(scrollregion=canvas.bbox("all")))

        _mw = [False]
        def _scroll(e): canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        def _enter(_): _mw[0] = True;  canvas.bind_all("<MouseWheel>", _scroll)
        def _leave(_): _mw[0] = False; canvas.after(20, lambda: canvas.unbind_all("<MouseWheel>") if not _mw[0] else None)
        canvas.bind("<Enter>", _enter)
        canvas.bind("<Leave>", _leave)

        self._build_content(inner)

    def _build_content(self, p: Frame):
        pad = {"padx": 16, "pady": 6}

        # ── Output directory ─────────────────────────────────────────────────
        sec = Frame(p, bg=CARD, padx=12, pady=10)
        sec.pack(fill=X, **pad)
        Label(sec, text="Thư mục lưu  (sẽ tạo subfolder anh_chua_co/ bên trong)",
              bg=CARD, fg=TEXT, font=F_BOLD).pack(anchor=W)
        row = Frame(sec, bg=CARD)
        row.pack(fill=X, pady=(4, 0))
        self._out_var = StringVar()
        _bind_cfg("web_img.output_dir", self._out_var)
        out_entry = ttk.Entry(row, textvariable=self._out_var, font=F_MAIN)
        out_entry.pack(side=LEFT, fill=X, expand=True)
        Button(row, text="Chọn…", bg=ACCENT2, fg="white", font=F_MAIN,
               relief=FLAT, padx=8, cursor="hand2",
               command=self._pick_dir).pack(side=LEFT, padx=(6, 0))

        # ── Engine + limits ──────────────────────────────────────────────────
        sec2 = Frame(p, bg=CARD, padx=12, pady=10)
        sec2.pack(fill=X, **pad)
        Label(sec2, text="Cài đặt tải xuống",
              bg=CARD, fg=TEXT, font=F_BOLD).pack(anchor=W, pady=(0, 6))
        row2 = Frame(sec2, bg=CARD)
        row2.pack(fill=X)

        Label(row2, text="Engine:", bg=CARD, fg=TEXT, font=F_MAIN).pack(side=LEFT)
        self._engine_var = StringVar(value="Bing")
        _bind_cfg("web_img.engine", self._engine_var)
        ttk.Combobox(row2, textvariable=self._engine_var, values=["Bing", "Google"],
                     state="readonly", width=9, font=F_MAIN
                     ).pack(side=LEFT, padx=(4, 28))

        Label(row2, text="Max ảnh/từ khóa:", bg=CARD, fg=TEXT, font=F_MAIN).pack(side=LEFT)
        self._max_var = StringVar(value="100")
        _bind_cfg("web_img.max_per_kw", self._max_var)
        ttk.Entry(row2, textvariable=self._max_var, width=6, font=F_MAIN
                  ).pack(side=LEFT, padx=(4, 28))

        Label(row2, text="Lọc size DDG:", bg=CARD, fg=TEXT, font=F_MAIN).pack(side=LEFT)
        self._size_tag_var = StringVar(value="Large")
        _bind_cfg("web_img.size_tag", self._size_tag_var)
        ttk.Combobox(row2, textvariable=self._size_tag_var,
                     values=["Large", "Medium", "Small", "Wallpaper"],
                     state="readonly", width=11, font=F_MAIN
                     ).pack(side=LEFT, padx=(4, 28))

        Label(row2, text="Kích thước tối thiểu:", bg=CARD, fg=TEXT, font=F_MAIN).pack(side=LEFT)
        self._minw_var = StringVar(value="200")
        self._minh_var = StringVar(value="200")
        _bind_cfg("web_img.min_w", self._minw_var)
        _bind_cfg("web_img.min_h", self._minh_var)
        ttk.Entry(row2, textvariable=self._minw_var, width=5, font=F_MAIN).pack(side=LEFT, padx=(4, 0))
        Label(row2, text=" × ", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        ttk.Entry(row2, textvariable=self._minh_var, width=5, font=F_MAIN).pack(side=LEFT)
        Label(row2, text=" px", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)

        # ── Keywords ─────────────────────────────────────────────────────────
        sec3 = Frame(p, bg=CARD, padx=12, pady=10)
        sec3.pack(fill=X, **pad)
        Label(sec3, text="Từ khóa tìm kiếm (mỗi dòng 1 từ khóa)",
              bg=CARD, fg=TEXT, font=F_BOLD).pack(anchor=W)
        Label(sec3,
              text="Ảnh lưu vào: <thư_mục>/anh_chua_co/<tên_từ_khóa>/",
              bg=CARD, fg=DIM, font=("Segoe UI", 9)).pack(anchor=W, pady=(2, 6))

        kf = Frame(sec3, bg=CARD)
        kf.pack(fill=X)
        self._kw_text = Text(kf, height=8, font=F_MONO,
                              bg="#0d0d1a", fg=TEXT, insertbackground=TEXT,
                              relief=FLAT, padx=6, pady=4)
        kw_sb = ttk.Scrollbar(kf, orient="vertical", command=self._kw_text.yview)
        self._kw_text.configure(yscrollcommand=kw_sb.set)
        kw_sb.pack(side=RIGHT, fill=Y)
        self._kw_text.pack(side=LEFT, fill=X, expand=True)

        saved_kw = _CFG.get("web_img.keywords", _DEFAULT_KEYWORDS)
        self._kw_text.insert("1.0", saved_kw)
        self._kw_text.bind("<FocusOut>", self._save_keywords)

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_row = Frame(p, bg=BG, padx=16, pady=4)
        btn_row.pack(fill=X)
        self._btn_start = Button(
            btn_row, text="▶  Bắt đầu (F5)",
            bg=ACCENT, fg="white", font=F_BOLD,
            relief=FLAT, padx=20, pady=6, cursor="hand2",
            command=self._start,
        )
        self._btn_start.pack(side=LEFT, padx=(0, 8))
        self._btn_stop = Button(
            btn_row, text="⏹  Dừng (Esc)",
            bg="#555", fg="white", font=F_MAIN,
            relief=FLAT, padx=12, pady=6, cursor="hand2",
            state=DISABLED, command=self._stop,
        )
        self._btn_stop.pack(side=LEFT)

        # ── Stats ─────────────────────────────────────────────────────────────
        stat_row = Frame(p, bg=CARD, padx=12, pady=6)
        stat_row.pack(fill=X, **pad)
        self._stat_lbl = Label(stat_row, text="Sẵn sàng.",
                                bg=CARD, fg=DIM, font=F_MAIN)
        self._stat_lbl.pack(anchor=W)

        # ── Log ───────────────────────────────────────────────────────────────
        log_sec = Frame(p, bg=CARD, padx=12, pady=10)
        log_sec.pack(fill=BOTH, expand=True, **pad)

        log_hdr = Frame(log_sec, bg=CARD)
        log_hdr.pack(fill=X)
        Label(log_hdr, text="Log", bg=CARD, fg=TEXT, font=F_BOLD).pack(side=LEFT)
        Button(log_hdr, text="Xóa", bg=ACCENT2, fg="white", font=F_MAIN,
               relief=FLAT, padx=8, pady=1, cursor="hand2",
               command=self._clear_log).pack(side=RIGHT)

        lf = Frame(log_sec, bg=CARD)
        lf.pack(fill=BOTH, expand=True, pady=(4, 0))
        self._log_txt = Text(lf, height=14, font=F_MONO,
                              bg="#0d0d1a", fg=TEXT,
                              state=DISABLED, relief=FLAT, padx=6, pady=4)
        log_sb = ttk.Scrollbar(lf, orient="vertical", command=self._log_txt.yview)
        self._log_txt.configure(yscrollcommand=log_sb.set)
        log_sb.pack(side=RIGHT, fill=Y)
        self._log_txt.pack(side=LEFT, fill=BOTH, expand=True)

        self._bind_shortcuts()

    # ── Actions ──────────────────────────────────────────────────────────────

    def _bind_shortcuts(self):
        self.root.bind_all("<F5>",     lambda e: self._start() if not self._running else None)
        self.root.bind_all("<Escape>", lambda e: self._stop())

    def _pick_dir(self):
        d = filedialog.askdirectory(
            title="Chọn thư mục lưu ảnh",
            initialdir=_cfg_dir("web_img.output_dir"),
        )
        if d:
            self._out_var.set(d)
            _CFG["web_img.output_dir"] = d
            _cfg_save()

    def _save_keywords(self, *_):
        _CFG["web_img.keywords"] = self._kw_text.get("1.0", "end-1c")
        _cfg_save()

    def _start(self):
        if self._running:
            return
        out = self._out_var.get().strip()
        if not out:
            self._append_log("[LỖI] Chưa chọn thư mục lưu.")
            return
        kws = self._kw_text.get("1.0", "end-1c").strip()
        if not kws:
            self._append_log("[LỖI] Chưa nhập từ khóa.")
            return

        self._save_keywords()
        cfg = {
            "output_dir": out,
            "keywords":   kws,
            "engine":     self._engine_var.get(),
            "max_per_kw": self._max_var.get() or "100",
            "min_w":      self._minw_var.get() or "200",
            "min_h":      self._minh_var.get() or "200",
            "size_tag":   self._size_tag_var.get(),
        }
        self._log_q  = queue.Queue()
        self._stat_q = queue.Queue()
        self._worker = WebImageWorker(cfg, self._log_q, self._stat_q)
        self._thread = threading.Thread(target=self._worker.run, daemon=True)
        self._running = True
        self._btn_start.config(state=DISABLED)
        self._btn_stop.config(state=NORMAL)
        self._thread.start()
        n_kw = len([k for k in kws.splitlines() if k.strip()])
        self._append_log(f"▶ Bắt đầu | {n_kw} từ khóa | Engine: {cfg['engine']} | Max: {cfg['max_per_kw']}")

    def _stop(self):
        if self._worker:
            self._worker.stop()

    def _clear_log(self):
        self._log_txt.config(state=NORMAL)
        self._log_txt.delete("1.0", END)
        self._log_txt.config(state=DISABLED)

    def _append_log(self, msg: str):
        self._log_txt.config(state=NORMAL)
        self._log_txt.insert(END, msg + "\n")
        lines = int(self._log_txt.index("end-1c").split(".")[0])
        if lines > self._LOG_MAX:
            self._log_txt.delete("1.0", f"{lines - self._LOG_MAX}.0")
        self._log_txt.see(END)
        self._log_txt.config(state=DISABLED)

    # ── Poll queues ───────────────────────────────────────────────────────────

    def _poll(self):
        try:
            while True:
                msg = self._log_q.get_nowait()
                if msg == "__DONE__":
                    self._running = False
                    self._btn_start.config(state=NORMAL)
                    self._btn_stop.config(state=DISABLED)
                    self._stat_lbl.config(fg=ACCENT)
                    self._append_log("✅ Hoàn thành!")
                else:
                    self._append_log(msg)
        except queue.Empty:
            pass

        try:
            while True:
                s = self._stat_q.get_nowait()
                self._update_stat(s)
        except queue.Empty:
            pass

        self.after(300, self._poll)

    def _update_stat(self, s: dict):
        done  = s.get("done_kw", 0)
        total = s.get("total_kw", 0)
        n_img = s.get("total_img", 0)
        kw    = s.get("current_kw", "")
        err   = s.get("error", 0)
        parts = []
        if total:
            parts.append(f"Từ khóa: {done}/{total}")
        if kw:
            parts.append(f'"{kw}"')
        if n_img:
            parts.append(f"{n_img} ảnh đã tải")
        if err:
            parts.append(f"⚠ {err} lỗi")
        self._stat_lbl.config(
            text=" | ".join(parts) or "Đang chạy...",
            fg=TEXT,
        )
