"""Layout mixin cho LocateAnythingTab — chỉ build widget, không chứa business logic.

Tách khỏi tab_locate_anything.py để giữ file tab dưới giới hạn 500 dòng
(xem CLAUDE.md — Clean Architecture, quy tắc tách file mixin)."""
import os
from tkinter import *
from tkinter import ttk, filedialog

from ...core.constants import (
    BG, CARD, ACCENT, ACCENT2, TEXT, DIM, F_MAIN, F_BOLD, F_MONO, IMAGE_EXTENSIONS,
)
from ...core.settings import _bind_cfg, _bind_history, _push_history, _get_history, _cfg_dir, _CFG
from ...core.ui_helpers import _make_logbox, _zoom_image_window, _action_btn
from ...shared.locate_anything_runner import DEFAULT_MAX_LONG_SIDE

_MODES = ["hybrid", "slow", "fast"]


class LocateAnythingLayoutMixin:

    def _build(self):
        self._build_config()
        pw = PanedWindow(self, orient=HORIZONTAL, bg=DIM,
                         sashwidth=5, sashrelief="flat", relief="flat")
        pw.pack(fill=BOTH, expand=True, padx=8, pady=4)
        left  = Frame(pw, bg=BG)
        right = Frame(pw, bg=BG)
        pw.add(left,  minsize=380)
        pw.add(right, minsize=460)
        self._build_single(left)
        self._build_batch(right)

        log_wrap = Frame(self, bg=CARD, pady=2)
        log_wrap.pack(fill=X, padx=8, pady=(0, 6))
        Label(log_wrap, text="Log", bg=CARD, fg=DIM, font=F_BOLD, padx=8).pack(anchor=W)
        lf, self._log = _make_logbox(log_wrap)
        lf.pack(fill=X, padx=8, pady=(0, 4))

    def _build_config(self):
        strip = Frame(self, bg=CARD, padx=10, pady=6)
        strip.pack(fill=X, padx=8, pady=(6, 2))

        r0 = Frame(strip, bg=CARD); r0.pack(fill=X, pady=(0, 4))
        Label(r0, text="Engine:", bg=CARD, fg=DIM, font=F_MAIN, width=10, anchor=W).pack(side=LEFT)
        self._engine_var = StringVar(value="cli")
        _bind_cfg("la.engine", self._engine_var)
        Radiobutton(r0, text="locate-anything.cpp (CLI, chính xác hơn)", variable=self._engine_var,
                    value="cli", bg=CARD, fg=TEXT, selectcolor=CARD, activebackground=CARD,
                    activeforeground=ACCENT, font=F_MAIN).pack(side=LEFT, padx=(0, 14))
        Radiobutton(r0, text="YOLOE (nhanh, nhẹ, GPU/CPU thoải mái)", variable=self._engine_var,
                    value="yoloe", bg=CARD, fg=TEXT, selectcolor=CARD, activebackground=CARD,
                    activeforeground=ACCENT, font=F_MAIN).pack(side=LEFT)

        r1 = Frame(strip, bg=CARD); r1.pack(fill=X, pady=(0, 4))
        Label(r1, text="CLI exe:", bg=CARD, fg=DIM, font=F_MAIN, width=10, anchor=W).pack(side=LEFT)
        self._cli_var = StringVar()
        cli_cb = ttk.Combobox(r1, textvariable=self._cli_var, style="Dark.TCombobox", font=F_MONO)
        cli_cb.pack(side=LEFT, fill=X, expand=True, padx=(4, 4))
        _bind_history("h.la.cli_exe", cli_cb)
        Button(r1, text="Chọn…", command=lambda: self._browse_file(
            self._cli_var, "h.la.cli_exe", cli_cb, "Chọn locate-anything-cli.exe",
            [("Executable", "*.exe"), ("Tất cả", "*.*")]),
            bg=ACCENT2, fg="white", activebackground=ACCENT, activeforeground="white",
            font=F_MAIN, relief="flat", padx=8, cursor="hand2").pack(side=LEFT)

        r2 = Frame(strip, bg=CARD); r2.pack(fill=X, pady=(0, 4))
        Label(r2, text="Model GGUF:", bg=CARD, fg=DIM, font=F_MAIN, width=10, anchor=W).pack(side=LEFT)
        self._model_var = StringVar()
        model_cb = ttk.Combobox(r2, textvariable=self._model_var, style="Dark.TCombobox", font=F_MONO)
        model_cb.pack(side=LEFT, fill=X, expand=True, padx=(4, 4))
        _bind_history("h.la.model", model_cb)
        Button(r2, text="Chọn…", command=lambda: self._browse_file(
            self._model_var, "h.la.model", model_cb, "Chọn model .gguf",
            [("GGUF model", "*.gguf"), ("Tất cả", "*.*")]),
            bg=ACCENT2, fg="white", activebackground=ACCENT, activeforeground="white",
            font=F_MAIN, relief="flat", padx=8, cursor="hand2").pack(side=LEFT)

        r3 = Frame(strip, bg=CARD); r3.pack(fill=X)
        Label(r3, text="Mode:", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        self._mode_var = StringVar(value="hybrid")
        _bind_cfg("la.mode", self._mode_var)
        ttk.Combobox(r3, textvariable=self._mode_var, values=_MODES, state="readonly",
                     style="Dark.TCombobox", width=8, font=F_MAIN).pack(side=LEFT, padx=(4, 14))
        Label(r3, text="Threads:", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        self._threads_var = IntVar(value=0)
        _bind_cfg("la.threads", self._threads_var)
        Spinbox(r3, from_=0, to=64, textvariable=self._threads_var, width=4,
                bg=CARD, fg=TEXT, insertbackground=TEXT, buttonbackground=ACCENT2,
                relief="flat", font=F_MAIN).pack(side=LEFT, padx=(4, 4))
        Label(r3, text="(0 = mặc định)", bg=CARD, fg=DIM, font=("Segoe UI", 8)).pack(side=LEFT, padx=(0, 14))
        Label(r3, text="Max cạnh ảnh (px):", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        self._maxside_var = IntVar(value=DEFAULT_MAX_LONG_SIDE)
        _bind_cfg("la.max_long_side", self._maxside_var)
        Spinbox(r3, from_=256, to=4096, increment=64, textvariable=self._maxside_var, width=6,
                bg=CARD, fg=TEXT, insertbackground=TEXT, buttonbackground=ACCENT2,
                relief="flat", font=F_MAIN).pack(side=LEFT, padx=(4, 14))
        Label(r3, text="Thư mục kết quả:", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        self._outdir_var = StringVar()
        _bind_cfg("la.out_dir", self._outdir_var)
        Entry(r3, textvariable=self._outdir_var, bg=BG, fg=TEXT, insertbackground=TEXT,
              relief="flat", font=F_MAIN, width=22).pack(side=LEFT, padx=(4, 4))
        Button(r3, text="Chọn…", command=self._browse_outdir,
               bg=ACCENT2, fg="white", activebackground=ACCENT, activeforeground="white",
               font=F_MAIN, relief="flat", padx=8, cursor="hand2").pack(side=LEFT)

        r4 = Frame(strip, bg=CARD); r4.pack(fill=X, pady=(4, 0))
        Label(r4, text="YOLOE model:", bg=CARD, fg=DIM, font=F_MAIN, width=10, anchor=W).pack(side=LEFT)
        self._yoloe_model_var = StringVar()
        yoloe_cb = ttk.Combobox(r4, textvariable=self._yoloe_model_var, style="Dark.TCombobox", font=F_MONO)
        yoloe_cb.pack(side=LEFT, fill=X, expand=True, padx=(4, 4))
        _bind_history("h.la.yoloe_model", yoloe_cb)
        self._yoloe_model_cb = yoloe_cb
        Button(r4, text="Chọn…", command=lambda: self._browse_file(
            self._yoloe_model_var, "h.la.yoloe_model", yoloe_cb, "Chọn model YOLOE (.pt)",
            [("YOLOE model", "*.pt"), ("Tất cả", "*.*")]),
            bg=ACCENT2, fg="white", activebackground=ACCENT, activeforeground="white",
            font=F_MAIN, relief="flat", padx=8, cursor="hand2").pack(side=LEFT, padx=(0, 14))
        Label(r4, text="Conf:", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        self._yoloe_conf_var = DoubleVar(value=0.25)
        _bind_cfg("la.yoloe_conf", self._yoloe_conf_var)
        Spinbox(r4, from_=0.05, to=0.95, increment=0.05, textvariable=self._yoloe_conf_var, width=5,
                bg=CARD, fg=TEXT, insertbackground=TEXT, buttonbackground=ACCENT2,
                relief="flat", font=F_MAIN).pack(side=LEFT, padx=(4, 4))
        Label(r4, text="(prompt YOLOE cách nhau bằng dấu phẩy, vd: car, person)",
              bg=CARD, fg=DIM, font=("Segoe UI", 8)).pack(side=LEFT, padx=(10, 0))

        self._prefill_defaults()

    def _prefill_defaults(self):
        """Gợi ý sẵn đường dẫn CLI/model đã build trong lúc test tích hợp, nếu tồn tại."""
        default_cli = r"D:\Tool\locate-anything.cpp\build\examples\cli\Release\locate-anything-cli.exe"
        default_model = r"D:\Tool\locate-anything.cpp\models\locate-anything-q4_k.gguf"
        default_yoloe = r"D:\Tool\yoloe-11s-seg.pt"
        if not self._cli_var.get().strip() and os.path.isfile(default_cli):
            self._cli_var.set(default_cli)
        if not self._model_var.get().strip() and os.path.isfile(default_model):
            self._model_var.set(default_model)
        if not self._yoloe_model_var.get().strip() and os.path.isfile(default_yoloe):
            self._yoloe_model_var.set(default_yoloe)

    # ── Single image pane ─────────────────────────────────────────────────

    def _build_single(self, parent):
        Label(parent, text="Detect ảnh đơn", bg=BG, fg=ACCENT, font=F_BOLD).pack(anchor=W, padx=8, pady=(6, 2))

        r = Frame(parent, bg=BG); r.pack(fill=X, padx=8, pady=2)
        self._img_var = StringVar()
        img_cb = ttk.Combobox(r, textvariable=self._img_var, style="Dark.TCombobox", font=F_MONO)
        img_cb.pack(side=LEFT, fill=X, expand=True, padx=(0, 4))
        _bind_history("h.la.image", img_cb)
        self._img_cb = img_cb
        Button(r, text="Chọn…", command=self._browse_image,
               bg=ACCENT2, fg="white", activebackground=ACCENT, activeforeground="white",
               font=F_MAIN, relief="flat", padx=8, cursor="hand2").pack(side=LEFT)

        Label(parent, text="Prompt (CLI: person</c>car — YOLOE: person, car):", bg=BG, fg=DIM, font=F_MAIN
              ).pack(anchor=W, padx=8, pady=(6, 0))
        pr = Frame(parent, bg=BG); pr.pack(fill=X, padx=8, pady=2)
        self._prompt_var = StringVar()
        prompt_cb = ttk.Combobox(pr, textvariable=self._prompt_var, style="Dark.TCombobox", font=F_MAIN)
        prompt_cb.pack(fill=X, expand=True)
        _bind_history("h.la.prompt", prompt_cb)
        self._prompt_cb = prompt_cb

        btn_row = Frame(parent, bg=BG); btn_row.pack(fill=X, padx=8, pady=(8, 4))
        self._btn_single = _action_btn(btn_row, "🔍 Detect (F5)", self._detect_single,
                                        ACCENT, padx=10, pady=4)
        self._btn_single.pack(side=LEFT, padx=(0, 8))
        self._btn_stop = _action_btn(btn_row, "■ Dừng (Esc)", self._stop, "#555", padx=10, pady=4)
        self._btn_stop.pack(side=LEFT)
        self._btn_stop.config(state=DISABLED)

        pic_outer = Frame(parent, bg="#0d0d1a", bd=2, relief="groove", height=280)
        pic_outer.pack(fill=X, padx=8, pady=(4, 2))
        pic_outer.pack_propagate(False)
        self._pic = Label(pic_outer, bg="#0d0d1a", fg=DIM, font=F_MAIN,
                           text="(chưa detect — double-click để phóng to sau khi có kết quả)",
                           cursor="hand2", wraplength=340, justify=CENTER)
        self._pic.pack(fill=BOTH, expand=True)
        self._pic.bind("<Double-Button-1>",
                        lambda e: _zoom_image_window(self.root, self._pil_preview, "Locate Anything — kết quả"))

        tv_f = Frame(parent, bg=BG); tv_f.pack(fill=BOTH, expand=True, padx=8, pady=(2, 6))
        self._tree_single = ttk.Treeview(tv_f, columns=("label", "box"), show="headings",
                                          style="Dark.Treeview", height=6)
        self._tree_single.heading("label", text="Nhãn")
        self._tree_single.heading("box", text="Box [x1,y1,x2,y2]")
        self._tree_single.column("label", width=100, anchor=W)
        self._tree_single.column("box", width=220, anchor=W)
        vsb = ttk.Scrollbar(tv_f, orient=VERTICAL, command=self._tree_single.yview)
        self._tree_single.configure(yscrollcommand=vsb.set)
        vsb.pack(side=RIGHT, fill=Y)
        self._tree_single.pack(fill=BOTH, expand=True)

    # ── Batch folder pane ─────────────────────────────────────────────────

    def _build_batch(self, parent):
        Label(parent, text="Detect cả thư mục", bg=BG, fg=ACCENT, font=F_BOLD).pack(anchor=W, padx=8, pady=(6, 2))

        r = Frame(parent, bg=BG); r.pack(fill=X, padx=8, pady=2)
        self._folder_var = StringVar()
        folder_cb = ttk.Combobox(r, textvariable=self._folder_var, style="Dark.TCombobox", font=F_MONO)
        folder_cb.pack(side=LEFT, fill=X, expand=True, padx=(0, 4))
        _bind_history("h.la.folder", folder_cb)
        self._folder_cb = folder_cb
        Button(r, text="Chọn…", command=self._browse_folder,
               bg=ACCENT2, fg="white", activebackground=ACCENT, activeforeground="white",
               font=F_MAIN, relief="flat", padx=8, cursor="hand2").pack(side=LEFT)

        btn_row = Frame(parent, bg=BG); btn_row.pack(fill=X, padx=8, pady=(8, 2))
        self._btn_batch = _action_btn(btn_row, "▶ Detect cả folder", self._detect_batch,
                                       ACCENT, padx=10, pady=4)
        self._btn_batch.pack(side=LEFT, padx=(0, 8))
        _action_btn(btn_row, "💾 Xuất CSV (Ctrl+S)", self._export_csv,
                    ACCENT2, padx=8, pady=4).pack(side=LEFT)

        pg = Frame(parent, bg=BG); pg.pack(fill=X, padx=8, pady=2)
        self._prog_lbl = Label(pg, text="Sẵn sàng", bg=BG, fg=DIM, font=F_MAIN, anchor=W)
        self._prog_lbl.pack(fill=X)
        self._pb = ttk.Progressbar(pg, style="K.Horizontal.TProgressbar", maximum=100, value=0)
        self._pb.pack(fill=X, pady=(2, 4))

        tv_f = Frame(parent, bg=BG); tv_f.pack(fill=BOTH, expand=True, padx=8, pady=(2, 6))
        cols = ("file", "count", "labels")
        self._tree_batch = ttk.Treeview(tv_f, columns=cols, show="headings",
                                         style="Dark.Treeview", selectmode="browse")
        for col, txt, w in [("file", "Tên file", 200), ("count", "Số detect", 70), ("labels", "Nhãn", 180)]:
            self._tree_batch.heading(col, text=txt)
            self._tree_batch.column(col, width=w, anchor=W if col != "count" else CENTER)
        vsb = ttk.Scrollbar(tv_f, orient=VERTICAL, command=self._tree_batch.yview)
        self._tree_batch.configure(yscrollcommand=vsb.set)
        vsb.pack(side=RIGHT, fill=Y)
        self._tree_batch.pack(fill=BOTH, expand=True)
        self._tree_batch.bind("<Double-Button-1>", self._on_batch_dbl)
        self._tree_batch.bind("<<TreeviewSelect>>", self._on_batch_select)

    # ═══════════════════════════ BROWSE HELPERS ═══════════════════════════

    def _browse_file(self, var, hist_key, combo, title, filetypes):
        p = filedialog.askopenfilename(title=title, initialdir=os.path.dirname(var.get()) or None,
                                        filetypes=filetypes)
        if p:
            var.set(p)
            _push_history(hist_key, p)
            combo["values"] = _get_history(hist_key)

    def _browse_image(self):
        exts = " ".join(f"*{e}" for e in sorted(IMAGE_EXTENSIONS))
        self._browse_file(self._img_var, "h.la.image", self._img_cb, "Chọn ảnh",
                           [("Ảnh", exts), ("Tất cả", "*.*")])

    def _browse_folder(self):
        p = filedialog.askdirectory(initialdir=self._folder_var.get() or _cfg_dir("la.folder") or None)
        if p:
            self._folder_var.set(p)
            _CFG["la.folder"] = p
            _push_history("h.la.folder", p)
            self._folder_cb["values"] = _get_history("h.la.folder")

    def _browse_outdir(self):
        p = filedialog.askdirectory(initialdir=self._outdir_var.get() or None)
        if p:
            self._outdir_var.set(p)
