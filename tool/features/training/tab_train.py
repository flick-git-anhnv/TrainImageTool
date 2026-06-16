import csv
import datetime
import json
import os
import queue
import random
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from tkinter import *
from tkinter import filedialog, messagebox, ttk

from ...core.constants import (BG, CARD, ACCENT, ACCENT2, TEXT, DIM, SUCCESS,
                         F_MAIN, F_BOLD, IMAGE_EXTENSIONS)
from ...core.settings import _bind_cfg, _cfg_dir, _bind_history, _push_history, _get_history
from ...core.ui_helpers import _folder_row, _make_logbox, _append_log

try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    _MPL_OK = True
except ImportError:
    _MPL_OK = False

try:
    from PIL import Image as _PILImage, ImageTk as _PILImageTk, ImageEnhance as _PILEnhance
    _PIL_OK = True
except ImportError:
    _PILImage = _PILImageTk = _PILEnhance = None
    _PIL_OK = False

_VAL_FG  = "#4fc3f7"
_EXCL_FG = DIM

_C_BOX      = "#F05922"
_C_CLS      = "#B8B3D6"
_C_DFL      = _VAL_FG
_C_MAP50    = "#F05922"
_C_MAP5095  = "#4caf50"
_C_PREC     = "#B8B3D6"
_C_REC      = _VAL_FG


class TrainTab(Frame):
    _MODELS = [
        ("yolo11n.pt", "Nano  – nhanh nhất, nhẹ nhất"),
        ("yolo11s.pt", "Small"),
        ("yolo11m.pt", "Medium"),
        ("yolo11l.pt", "Large"),
        ("yolo11x.pt", "XLarge – chính xác nhất"),
    ]

    def __init__(self, master, root):
        super().__init__(master, bg=BG)
        self.root = root

        self.train_dir    = StringVar()
        self.val_dir      = StringVar()
        self._labels_var  = StringVar(
            value="car,motorcycle,bus,truck,bicycle,license_plate")
        self._model_var   = StringVar(value="yolo11n.pt")
        _bind_cfg("train.dir",    self.train_dir)
        _bind_cfg("train.val",    self.val_dir)
        _bind_cfg("train.labels", self._labels_var)

        self._epochs_var      = StringVar(value="100")
        self._imgsz_var       = StringVar(value="640")
        self._batch_var       = StringVar(value="16")
        self._device_var      = StringVar(value="0")
        self._project_var     = StringVar()
        self._name_var        = StringVar(value="kztek_train")
        self._split_ratio_var = IntVar(value=80)
        self._recursive_var   = BooleanVar(value=False)
        _bind_cfg("train.project", self._project_var)

        self._early_stop_var     = BooleanVar(value=False)
        self._patience_var       = StringVar(value="10")

        self._optimizer_var     = StringVar(value="AdamW")
        self._lr0_var           = StringVar(value="0.01")
        self._lrf_var           = StringVar(value="0.01")
        self._close_mosaic_var  = StringVar(value="10")
        self._cache_var         = StringVar(value="False")
        self._workers_var       = StringVar(value="4")
        self._cos_lr_var        = BooleanVar(value=False)
        self._weight_decay_var  = StringVar(value="0.0005")
        _bind_cfg("train.optimizer",    self._optimizer_var)
        _bind_cfg("train.lr0",          self._lr0_var)
        _bind_cfg("train.lrf",          self._lrf_var)
        _bind_cfg("train.close_mosaic", self._close_mosaic_var)
        _bind_cfg("train.cache",        self._cache_var)
        _bind_cfg("train.workers",      self._workers_var)
        _bind_cfg("train.cos_lr",       self._cos_lr_var)
        _bind_cfg("train.weight_decay", self._weight_decay_var)

        self._proc       = None
        self._out_queue  = queue.Queue()
        self._poll_id    = None
        self._output_dir  = ""
        self._chart_poll_id = None

        self._sf_data: dict = {}

        self._chart_win    = None
        self._fig          = None
        self._axes         = None
        self._mpl_canvas   = None

        self._history_win  = None
        self._ckpt_win     = None
        self._aug_win      = None

        self._build()

    # ── Layout ────────────────────────────────────────────────────────────

    def _build(self):
        top = Frame(self, bg=CARD, padx=12, pady=10)
        top.pack(fill=X)
        g = Frame(top, bg=CARD)
        g.pack(fill=X)
        g.columnconfigure(1, weight=1)
        _folder_row(g, "Thư mục train :", self.train_dir, 0, bg=CARD, history_key="h.train.dir")
        _folder_row(g, "Thư mục val   :", self.val_dir,   1, bg=CARD, history_key="h.train.val")

        Label(g, text="Tỷ lệ tự chia:", bg=CARD, fg=DIM,
              font=F_MAIN, width=26, anchor=W).grid(row=2, column=0, sticky=W, pady=4)
        sr = Frame(g, bg=CARD)
        sr.grid(row=2, column=1, sticky=W, padx=(8, 0))
        Label(sr, text="Train", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        Spinbox(sr, from_=50, to=99, textvariable=self._split_ratio_var,
                width=4, bg="#16162a", fg=TEXT, insertbackground=TEXT,
                buttonbackground=ACCENT2, relief="flat", font=F_MAIN,
                command=self._on_split_change).pack(side=LEFT, padx=(4, 2))
        self._split_val_lbl = Label(sr, text="% / Val 10%",
                                     bg=CARD, fg=DIM, font=F_MAIN)
        self._split_val_lbl.pack(side=LEFT)
        Label(sr, text="  ← áp dụng khi không có subfolder Val",
              bg=CARD, fg="#f0c040",
              font=("Segoe UI", 8, "italic")).pack(side=LEFT)
        self._split_ratio_var.trace_add("write", self._on_split_change)

        Label(g, text="Danh sách nhãn:", bg=CARD, fg=DIM,
              font=F_MAIN, width=26, anchor=W).grid(row=3, column=0, sticky=W, pady=5)
        _lbl_combo = ttk.Combobox(g, textvariable=self._labels_var,
                                   style="Dark.TCombobox", font=F_MAIN)
        _lbl_combo.grid(row=3, column=1, sticky=EW, padx=(8, 8))
        _bind_history("h.train.labels", _lbl_combo)
        Button(g, text="📄 Tạo data.yaml", command=self._gen_yaml_only,
               bg=ACCENT2, fg="white", activebackground=ACCENT, activeforeground="white",
               font=F_MAIN, relief="flat", padx=10, cursor="hand2").grid(row=3, column=2)

        self._build_subfolder_panel()

        pf = Frame(self, bg=CARD, padx=14, pady=8)
        pf.pack(fill=X, padx=12)

        Label(pf, text="Cấu hình huấn luyện", bg=CARD, fg=TEXT,
              font=F_BOLD).grid(row=0, column=0, columnspan=10, sticky=W, pady=(0, 6))
        Label(pf, text="Model:", bg=CARD, fg=DIM, font=F_MAIN).grid(
            row=1, column=0, sticky=W)
        _mc_frame = Frame(pf, bg=CARD)
        _mc_frame.grid(row=1, column=1, sticky=W, padx=(4, 16))

        mc = ttk.Combobox(_mc_frame, textvariable=self._model_var, width=13,
                          state="readonly", font=F_MAIN,
                          values=[m for m, _ in self._MODELS])
        mc.pack(side=LEFT)
        mc.current(0)

        def _browse_model():
            p = filedialog.askopenfilename(
                title="Chọn model .pt",
                filetypes=[("PyTorch model", "*.pt"), ("All files", "*.*")],
                initialdir=str(Path(self._model_var.get()).parent)
                           if Path(self._model_var.get()).is_file() else ".")
            if p:
                self._model_var.set(p)
                self._model_desc.config(text=f"Custom: {Path(p).name}")

        Button(_mc_frame, text="📂", command=_browse_model,
               bg=CARD, fg=TEXT, activebackground=ACCENT2, activeforeground="white",
               font=F_MAIN, relief="flat", padx=4, cursor="hand2").pack(side=LEFT, padx=(2, 0))

        self._model_desc = Label(pf, text=self._MODELS[0][1],
                                  bg=CARD, fg=DIM,
                                  font=("Segoe UI", 8, "italic"))
        self._model_desc.grid(row=2, column=0, columnspan=2, sticky=W, pady=(0, 4))
        mc.bind("<<ComboboxSelected>>", self._on_model_change)

        for col, (lbl, var, tip) in enumerate([
            ("Epochs:",  self._epochs_var, "số lần lặp"),
            ("Imgsz:",   self._imgsz_var,  "kích thước ảnh"),
            ("Batch:",   self._batch_var,  "−1 = auto"),
            ("Device:",  self._device_var, "0=GPU, cpu"),
        ]):
            c = (col + 1) * 2
            Label(pf, text=lbl, bg=CARD, fg=DIM, font=F_MAIN).grid(
                row=1, column=c, sticky=W, padx=(16, 4))
            Entry(pf, textvariable=var, bg="#16162a", fg=TEXT,
                  insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4, width=7).grid(
                      row=1, column=c + 1, sticky=W)
            Label(pf, text=tip, bg=CARD, fg=DIM,
                  font=("Segoe UI", 7, "italic")).grid(
                      row=2, column=c, columnspan=2, sticky=W)

        Label(pf, text="Output folder:", bg=CARD, fg=DIM, font=F_MAIN).grid(
            row=3, column=0, sticky=W, pady=(6, 0))
        pr = Frame(pf, bg=CARD)
        pr.grid(row=3, column=1, columnspan=9, sticky=EW, pady=(6, 0))
        _proj_combo = ttk.Combobox(pr, textvariable=self._project_var,
                                    style="Dark.TCombobox", font=F_MAIN, width=30)
        _proj_combo.pack(side=LEFT)
        _bind_history("h.train.project", _proj_combo)

        def _pick_project():
            p = filedialog.askdirectory(initialdir=_cfg_dir("train.project"))
            if p:
                self._project_var.set(p)
                _push_history("h.train.project", p)
                _proj_combo["values"] = _get_history("h.train.project")
        Button(pr, text="…", command=_pick_project,
               bg=ACCENT2, fg="white", font=F_MAIN, relief="flat",
               padx=8, cursor="hand2").pack(side=LEFT, padx=(4, 4))
        Button(pr, text="📂", command=lambda: (
                   __import__("os").startfile(self._project_var.get().strip())
                   if self._project_var.get().strip() and
                   __import__("os").path.isdir(self._project_var.get().strip()) else None
               ),
               bg=CARD, fg=TEXT, font=F_MAIN, relief="flat",
               padx=6, cursor="hand2").pack(side=LEFT, padx=(0, 12))
        Label(pr, text="Run name:", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        _name_combo = ttk.Combobox(pr, textvariable=self._name_var,
                                    style="Dark.TCombobox", font=F_MAIN, width=18)
        _name_combo.pack(side=LEFT, padx=(4, 0))
        _bind_history("h.train.name", _name_combo)

        # ── Early stopping row ────────────────────────────────────────────
        es_row = Frame(pf, bg=CARD)
        es_row.grid(row=4, column=0, columnspan=10, sticky=W, pady=(6, 0))
        Checkbutton(es_row, text="Early stopping", variable=self._early_stop_var,
                    bg=CARD, fg=TEXT, activebackground=CARD, activeforeground=TEXT,
                    selectcolor="#16162a", font=F_MAIN,
                    command=self._on_early_stop_toggle).pack(side=LEFT)
        Label(es_row, text="Patience:", bg=CARD, fg=DIM, font=F_MAIN).pack(
            side=LEFT, padx=(12, 4))
        self._patience_entry = Entry(es_row, textvariable=self._patience_var,
                                     bg="#16162a", fg=TEXT, insertbackground=TEXT,
                                     relief="flat", font=F_MAIN, bd=4, width=5)
        self._patience_entry.pack(side=LEFT)
        Label(es_row, text="epochs", bg=CARD, fg=DIM,
              font=("Segoe UI", 8, "italic")).pack(side=LEFT, padx=(4, 0))
        self._early_note_lbl = Label(es_row, text="", bg=CARD, fg=DIM,
                                      font=("Segoe UI", 8, "italic"))
        self._early_note_lbl.pack(side=LEFT, padx=(14, 0))
        self._on_early_stop_toggle()

        # ── Advanced hyperparameters ──────────────────────────────────────
        Label(pf, text="Tham số nâng cao:", bg=CARD, fg=DIM,
              font=F_BOLD).grid(row=5, column=0, sticky=W, pady=(8, 2))
        adv1 = Frame(pf, bg=CARD)
        adv1.grid(row=5, column=1, columnspan=9, sticky=W, pady=(8, 2))

        Label(adv1, text="Optimizer:", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        ttk.Combobox(adv1, textvariable=self._optimizer_var, width=8,
                     state="readonly", font=F_MAIN,
                     values=["auto", "SGD", "Adam", "AdamW"]
                     ).pack(side=LEFT, padx=(4, 14))

        for _lbl, _var, _w in [
            ("LR0:",         self._lr0_var,          7),
            ("LRF:",         self._lrf_var,          7),
            ("Close Mosaic:",self._close_mosaic_var,  4),
            ("Workers:",     self._workers_var,       4),
            ("Weight Decay:",self._weight_decay_var,  9),
        ]:
            Label(adv1, text=_lbl, bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
            Entry(adv1, textvariable=_var, bg="#16162a", fg=TEXT,
                  insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4,
                  width=_w).pack(side=LEFT, padx=(4, 14))

        adv2 = Frame(pf, bg=CARD)
        adv2.grid(row=6, column=0, columnspan=10, sticky=W, pady=(2, 0))
        Checkbutton(adv2, text="Cosine LR", variable=self._cos_lr_var,
                    bg=CARD, fg=TEXT, activebackground=CARD, activeforeground=TEXT,
                    selectcolor="#16162a", font=F_MAIN).pack(side=LEFT)
        Label(adv2, text="  Cache:", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        ttk.Combobox(adv2, textvariable=self._cache_var, width=6,
                     state="readonly", font=F_MAIN,
                     values=["False", "ram", "disk"]).pack(side=LEFT, padx=(4, 0))
        Label(adv2,
              text="   (ram = load toàn bộ ảnh vào RAM, tăng tốc đáng kể)",
              bg=CARD, fg=DIM,
              font=("Segoe UI", 8, "italic")).pack(side=LEFT, padx=(8, 0))

        # ── Control bar ───────────────────────────────────────────────────
        ctrl = Frame(self, bg=BG, padx=12, pady=6)
        ctrl.pack(fill=X)
        self._btn_start = Button(ctrl, text="▶  Bắt đầu Train",
                                  command=self._start_train,
                                  bg="#2e7d32", fg="white",
                                  activebackground="#1b5e20", activeforeground="white",
                                  font=F_BOLD, relief="flat", padx=20, cursor="hand2")
        self._btn_start.pack(side=LEFT)
        self._btn_stop = Button(ctrl, text="⏹  Dừng",
                                command=self._stop_train,
                                bg="#c62828", fg="white",
                                activebackground="#8b0000", activeforeground="white",
                                font=F_BOLD, relief="flat", padx=14, cursor="hand2",
                                state=DISABLED)
        self._btn_stop.pack(side=LEFT, padx=(8, 0))

        self._btn_chart = Button(ctrl, text="📊  Biểu đồ",
                                  command=self._open_chart_window,
                                  bg=ACCENT2, fg="white",
                                  activebackground=ACCENT, activeforeground="white",
                                  font=F_BOLD, relief="flat", padx=14, cursor="hand2")
        self._btn_chart.pack(side=LEFT, padx=(8, 0))
        if not _MPL_OK:
            self._btn_chart.config(state=DISABLED,
                                    text="📊  Biểu đồ (cần matplotlib)")

        Button(ctrl, text="📋  Lịch sử train",
               command=self._open_history_window,
               bg=ACCENT2, fg="white",
               activebackground=ACCENT, activeforeground="white",
               font=F_BOLD, relief="flat", padx=14, cursor="hand2").pack(side=LEFT, padx=(8, 0))

        Button(ctrl, text="💾  Checkpoint",
               command=self._open_checkpoint_window,
               bg=ACCENT2, fg="white",
               activebackground=ACCENT, activeforeground="white",
               font=F_BOLD, relief="flat", padx=14, cursor="hand2").pack(side=LEFT, padx=(8, 0))

        Button(ctrl, text="🖼  Xem augmentation",
               command=self._open_aug_preview,
               bg=ACCENT2, fg="white",
               activebackground=ACCENT, activeforeground="white",
               font=F_BOLD, relief="flat", padx=14, cursor="hand2").pack(side=LEFT, padx=(8, 0))

        Button(ctrl, text="📈  Phân tích",
               command=self._analyze_results,
               bg=ACCENT2, fg="white",
               activebackground=ACCENT, activeforeground="white",
               font=F_BOLD, relief="flat", padx=14, cursor="hand2").pack(side=LEFT, padx=(8, 0))

        self._status_lbl = Label(ctrl, text="", bg=BG, fg=DIM, font=F_MAIN)
        self._status_lbl.pack(side=LEFT, padx=16)

        self._build_train_glossary()

        log_frame, self._log = _make_logbox(self)
        log_frame.pack(fill=BOTH, expand=True, padx=12, pady=(2, 0))

        res = Frame(self, bg=CARD, padx=12, pady=6)
        res.pack(fill=X, padx=12, pady=(2, 8), side=BOTTOM)
        Label(res, text="Kết quả:", bg=CARD, fg=TEXT, font=F_BOLD).pack(side=LEFT)
        self._result_lbl = Label(res, text="—", bg=CARD, fg=DIM, font=F_MAIN)
        self._result_lbl.pack(side=LEFT, padx=8)
        self._open_btn = Button(res, text="📂 Mở thư mục output",
                                command=self._open_output_dir,
                                bg=ACCENT2, fg="white",
                                activebackground=ACCENT, activeforeground="white",
                                font=F_MAIN, relief="flat", padx=10, cursor="hand2",
                                state=DISABLED)
        self._open_btn.pack(side=LEFT, padx=4)

    def _build_subfolder_panel(self):
        sf = LabelFrame(
            self,
            text=" Subfolder  (click ☑ để bật/tắt — click vai trò để đổi Train↔Val) ",
            bg=BG, fg=TEXT, font=F_BOLD, bd=1, relief="groove", padx=8, pady=6)
        sf.pack(fill=BOTH, expand=True, padx=12, pady=(6, 4))

        tb = Frame(sf, bg=BG)
        tb.pack(fill=X, pady=(0, 4))

        def _btn(parent, text, cmd, fg_col="white", bg_col=CARD):
            return Button(parent, text=text, command=cmd,
                          bg=bg_col, fg=fg_col,
                          activebackground=ACCENT2, activeforeground="white",
                          font=F_MAIN, relief="flat", padx=8, cursor="hand2")

        _btn(tb, "🔍  Quét subfolder", self._scan_subfolders,
             bg_col=ACCENT2).pack(side=LEFT)
        Checkbutton(tb, text="Đệ quy", variable=self._recursive_var,
                    bg=BG, fg=TEXT, activebackground=BG, activeforeground=TEXT,
                    selectcolor=CARD, font=F_MAIN).pack(side=LEFT, padx=(8, 14))
        _btn(tb, "☑ Chọn tất",  self._select_all).pack(side=LEFT)
        _btn(tb, "☐ Bỏ chọn",  self._deselect_all).pack(side=LEFT, padx=(4, 0))
        _btn(tb, "→ Train tất", lambda: self._set_all_role("Train")).pack(side=LEFT, padx=(8, 0))
        _btn(tb, "→ Val tất",   lambda: self._set_all_role("Val"),
             fg_col=_VAL_FG).pack(side=LEFT, padx=(4, 0))
        self._scan_lbl = Label(tb, text="Chưa quét",
                                bg=BG, fg=DIM, font=("Segoe UI", 8, "italic"))
        self._scan_lbl.pack(side=LEFT, padx=10)

        tf = Frame(sf, bg=BG)
        tf.pack(fill=BOTH, expand=True)

        cols = ("check", "name", "imgs", "lbls", "role")
        self._tree = ttk.Treeview(tf, columns=cols, show="headings",
                                   style="Dark.Treeview", height=7,
                                   selectmode="extended")
        self._tree.heading("check", text="☑")
        self._tree.heading("name",  text="Subfolder")
        self._tree.heading("imgs",  text="Ảnh")
        self._tree.heading("lbls",  text="Nhãn")
        self._tree.heading("role",  text="Vai trò")
        self._tree.column("check", width=32,  minwidth=28,  anchor=CENTER, stretch=False)
        self._tree.column("name",  width=320, minwidth=120, anchor=W)
        self._tree.column("imgs",  width=65,  minwidth=50,  anchor=CENTER, stretch=False)
        self._tree.column("lbls",  width=65,  minwidth=50,  anchor=CENTER, stretch=False)
        self._tree.column("role",  width=70,  minwidth=50,  anchor=CENTER, stretch=False)
        vsb = ttk.Scrollbar(tf, orient=VERTICAL,   command=self._tree.yview)
        hsb = ttk.Scrollbar(tf, orient=HORIZONTAL, command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side=RIGHT, fill=Y)
        hsb.pack(side=BOTTOM, fill=X)
        self._tree.pack(fill=BOTH, expand=True)
        self._tree.tag_configure("train",    foreground=TEXT)
        self._tree.tag_configure("val",      foreground=_VAL_FG)
        self._tree.tag_configure("excluded", foreground=_EXCL_FG)
        self._tree.bind("<ButtonRelease-1>", self._on_tree_click)

    # ── Subfolder scanning ────────────────────────────────────────────────

    def _scan_subfolders(self):
        root_str = self.train_dir.get().strip()
        if not root_str or not os.path.isdir(root_str):
            messagebox.showwarning("Chưa có thư mục", "Chọn thư mục train trước.")
            return
        for iid in self._tree.get_children():
            self._tree.delete(iid)
        self._sf_data.clear()

        root_path = Path(root_str)
        subs = (sorted(p for p in root_path.rglob("*") if p.is_dir())
                if self._recursive_var.get()
                else sorted(p for p in root_path.iterdir() if p.is_dir()))

        count = 0
        for sub in subs:
            img_dir = sub / "images" if (sub / "images").is_dir() else sub
            lbl_dir = (sub / "labels"
                       if img_dir != sub and (sub / "labels").is_dir() else sub)
            imgs = sum(1 for p in img_dir.iterdir()
                       if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS)
            if imgs == 0:
                continue
            lbls = sum(1 for p in lbl_dir.iterdir()
                       if p.is_file() and p.suffix.lower() == ".txt")
            rel  = str(sub.relative_to(root_path))
            iid  = self._tree.insert("", END,
                                      values=("☑", rel, imgs, lbls, "Train"),
                                      tags=("train",))
            self._sf_data[iid] = {"path": sub, "imgs": imgs, "lbls": lbls,
                                   "check": True, "role": "Train"}
            count += 1
        self._scan_lbl.config(
            text=f"Tìm thấy {count} subfolder có ảnh",
            fg=SUCCESS if count else "#f0c040")

    def _on_tree_click(self, event):
        if self._tree.identify_region(event.x, event.y) != "cell":
            return
        col = self._tree.identify_column(event.x)
        iid = self._tree.identify_row(event.y)
        if not iid:
            return
        data = self._sf_data.get(iid)
        if data is None:
            return
        if col == "#1":
            data["check"] = not data["check"]
        elif col == "#5":
            data["role"] = "Val" if data["role"] == "Train" else "Train"
        self._refresh_row(iid)

    def _refresh_row(self, iid):
        d   = self._sf_data[iid]
        rel = self._tree.item(iid, "values")[1]
        tag = ("excluded" if not d["check"]
               else "val" if d["role"] == "Val" else "train")
        self._tree.item(iid,
                        values=("☑" if d["check"] else "☐",
                                rel, d["imgs"], d["lbls"], d["role"]),
                        tags=(tag,))

    def _select_all(self):
        for iid, d in self._sf_data.items():
            d["check"] = True;  self._refresh_row(iid)

    def _deselect_all(self):
        for iid, d in self._sf_data.items():
            d["check"] = False; self._refresh_row(iid)

    def _set_all_role(self, role):
        for iid, d in self._sf_data.items():
            d["role"] = role;   self._refresh_row(iid)

    # ── Image collection ──────────────────────────────────────────────────

    def _collect_from_tree(self):
        if not self._sf_data:
            return None, None
        train_imgs, val_imgs = [], []
        for d in self._sf_data.values():
            if not d["check"]:
                continue
            sub     = d["path"]
            img_dir = sub / "images" if (sub / "images").is_dir() else sub
            imgs    = sorted(p for p in img_dir.iterdir()
                             if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS)
            (val_imgs if d["role"] == "Val" else train_imgs).extend(imgs)
        return train_imgs, val_imgs

    # ── Dataset building ──────────────────────────────────────────────────

    @staticmethod
    def _resolve_img_dir(folder):
        sub = os.path.join(folder, "images")
        return sub if os.path.isdir(sub) else folder

    def _needs_split(self, train_dir, val_dir):
        if not val_dir:
            return True
        try:
            return os.path.samefile(train_dir, val_dir)
        except Exception:
            return (os.path.normcase(os.path.abspath(train_dir)) ==
                    os.path.normcase(os.path.abspath(val_dir)))

    @staticmethod
    def _link_or_copy(src: Path, dst: Path):
        if dst.exists():
            return
        try:
            os.link(src, dst)
        except OSError:
            shutil.copy2(src, dst)

    def _build_dataset_dir(self, splits: dict):
        all_imgs   = [p for imgs in splits.values() for p in imgs]
        src_drives = {p.drive.upper() for p in all_imgs}
        root = (Path(next(iter(src_drives)) + "/") / "kztek_split"
                if len(src_drives) == 1
                else Path(tempfile.gettempdir()) / "kztek_split")
        for split, imgs in splits.items():
            (root / split / "images").mkdir(parents=True, exist_ok=True)
            (root / split / "labels").mkdir(parents=True, exist_ok=True)
            for img in imgs:
                self._link_or_copy(img, root / split / "images" / img.name)
                lbl = img.with_suffix(".txt")
                if not lbl.exists():
                    lbl = img.parent.parent / "labels" / (img.stem + ".txt")
                if lbl.exists():
                    self._link_or_copy(lbl, root / split / "labels" / lbl.name)
        return root

    def _resolve_images(self):
        train_imgs, val_imgs = self._collect_from_tree()
        if train_imgs is not None:
            if not train_imgs and not val_imgs:
                raise ValueError("Không có subfolder nào được chọn (☑).")
            if not train_imgs:
                raise ValueError("Không có subfolder nào được đặt làm Train.")
            split_msg = ""
            if not val_imgs:
                ratio      = max(50, min(99, int(self._split_ratio_var.get())))
                shuffled   = list(train_imgs)
                random.shuffle(shuffled)
                n          = max(1, int(len(shuffled) * ratio / 100))
                train_imgs = shuffled[:n]
                val_imgs   = shuffled[n:] or shuffled[-1:]
                split_msg  = (f"Tự chia {ratio}/{100 - ratio}: "
                              f"{len(train_imgs)} train / {len(val_imgs)} val")
            return train_imgs, val_imgs, split_msg

        train_dir = self.train_dir.get().strip()
        val_dir   = self.val_dir.get().strip() or None
        if not train_dir or not os.path.isdir(train_dir):
            raise ValueError("Vui lòng chọn thư mục train hợp lệ.")
        if self._needs_split(train_dir, val_dir):
            ratio    = max(50, min(99, int(self._split_ratio_var.get())))
            img_dir  = Path(self._resolve_img_dir(train_dir))
            all_imgs = sorted(p for p in img_dir.iterdir()
                              if p.suffix.lower() in IMAGE_EXTENSIONS)
            if not all_imgs:
                raise ValueError(f"Không tìm thấy ảnh trong {img_dir}")
            random.shuffle(all_imgs)
            n          = max(1, int(len(all_imgs) * ratio / 100))
            train_imgs = all_imgs[:n]
            val_imgs   = all_imgs[n:] or all_imgs[-1:]
            return train_imgs, val_imgs, (
                f"Tự chia {ratio}/{100 - ratio}: "
                f"{len(train_imgs)} train / {len(val_imgs)} val")
        train_imgs = sorted(p for p in
                            Path(self._resolve_img_dir(train_dir)).iterdir()
                            if p.suffix.lower() in IMAGE_EXTENSIONS)
        val_imgs   = sorted(p for p in
                            Path(self._resolve_img_dir(val_dir)).iterdir()
                            if p.suffix.lower() in IMAGE_EXTENSIONS)
        return train_imgs, val_imgs, ""

    def _write_yaml(self, labels):
        train_imgs, val_imgs, split_msg = self._resolve_images()
        nc        = len(labels)
        names_str = ", ".join(f"'{n}'" for n in labels)
        root      = self._build_dataset_dir({"train": train_imgs, "valid": val_imgs})
        yaml_path = str(root / "data.yaml")
        with open(yaml_path, "w", encoding="utf-8") as f:
            f.write(f"path: {root}\ntrain: train/images\nval:   valid/images\n"
                    f"nc: {nc}\nnames: [{names_str}]\n")
        return yaml_path, split_msg, len(train_imgs), len(val_imgs)

    # ── Early stopping ────────────────────────────────────────────────────

    def _on_early_stop_toggle(self):
        enabled = self._early_stop_var.get()
        state = NORMAL if enabled else DISABLED
        self._patience_entry.config(state=state)

    # ── Chart window ──────────────────────────────────────────────────────

    def _open_chart_window(self):
        if not _MPL_OK:
            messagebox.showwarning(
                "Thiếu thư viện",
                "Cài matplotlib để xem biểu đồ:\n\npip install matplotlib")
            return
        if self._chart_win and self._chart_win.winfo_exists():
            self._chart_win.lift()
            self._update_charts()
            return
        self._create_chart_window()

    def _create_chart_window(self):
        win = Toplevel(self.root)
        name = self._name_var.get().strip() or "train"
        win.title(f"KZTEK Train – Biểu đồ  [{name}]")
        win.geometry("960x620")
        win.configure(bg=BG)
        win.protocol("WM_DELETE_WINDOW", win.withdraw)
        self._chart_win = win

        tb = Frame(win, bg=CARD, padx=8, pady=4)
        tb.pack(fill=X)
        self._epoch_lbl = Label(tb, text="—", bg=CARD, fg=TEXT, font=F_BOLD)
        self._epoch_lbl.pack(side=LEFT)
        Button(tb, text="↻  Làm mới", command=self._update_charts,
               bg=ACCENT2, fg="white", activebackground=ACCENT, activeforeground="white",
               font=F_MAIN, relief="flat", padx=10, cursor="hand2").pack(side=RIGHT)

        fig = Figure(figsize=(10, 5.5), dpi=92, facecolor="#16162a")
        axes = fig.subplots(2, 2)
        fig.subplots_adjust(left=0.07, right=0.97, top=0.93,
                            bottom=0.08, wspace=0.28, hspace=0.42)
        self._fig   = fig
        self._axes  = axes

        for ax in axes.flat:
            ax.set_facecolor("#1e1e2e")
            for spine in ax.spines.values():
                spine.set_color("#2a2a3e")
            ax.tick_params(colors=DIM, labelsize=7)
            ax.xaxis.label.set_color(DIM)
            ax.yaxis.label.set_color(DIM)

        axes[0, 0].set_title("Train Loss",        color=TEXT, fontsize=9, pad=6)
        axes[0, 1].set_title("Val Loss",           color=TEXT, fontsize=9, pad=6)
        axes[1, 0].set_title("mAP",                color=TEXT, fontsize=9, pad=6)
        axes[1, 1].set_title("Precision / Recall", color=TEXT, fontsize=9, pad=6)

        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.get_tk_widget().pack(fill=BOTH, expand=True)
        self._mpl_canvas = canvas
        canvas.draw()

    def _read_csv(self):
        path = Path(self._output_dir) / "results.csv"
        if not path.exists():
            return []
        rows = []
        try:
            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rows.append({k.strip(): v.strip() for k, v in row.items()})
        except Exception:
            pass
        return rows

    # ── Phân tích kết quả ────────────────────────────────────────────

    def _analyze_results(self):
        """Đọc results.csv và hiển thị popup phân tích + đề xuất."""
        csv_path = None
        if self._output_dir:
            p = Path(self._output_dir) / "results.csv"
            if p.exists():
                csv_path = p
        if csv_path is None:
            initial = str(Path(self._project_var.get().strip())) if self._project_var.get().strip() else "."
            p = filedialog.askopenfilename(
                title="Chọn file results.csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialdir=initial)
            if not p:
                return
            csv_path = Path(p)
        rows = []
        try:
            with open(csv_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rows.append({k.strip(): v.strip() for k, v in row.items()})
        except Exception as exc:
            messagebox.showerror("Lỗi đọc CSV", str(exc))
            return
        if not rows:
            messagebox.showwarning("Không có dữ liệu", "File results.csv trống hoặc chưa có epoch nào.")
            return
        report = self._build_analysis_report(rows, csv_path)
        self._open_analysis_window(report)

    def _build_analysis_report(self, rows, csv_path):
        """Phân tích rows từ results.csv và trả về chuỗi report."""
        def gf(row, *keys):
            for k in keys:
                try:
                    v = float(row.get(k, ""))
                    if v == v:  # not NaN
                        return v
                except (ValueError, TypeError):
                    pass
            return float("nan")

        def isnan(x):
            return x != x

        n = len(rows)
        epochs_data = []
        for row in rows:
            ep      = gf(row, "epoch")
            map50   = gf(row, "metrics/mAP50(B)")
            map5095 = gf(row, "metrics/mAP50-95(B)")
            prec    = gf(row, "metrics/precision(B)")
            rec     = gf(row, "metrics/recall(B)")
            v_box   = gf(row, "val/box_loss")
            v_cls   = gf(row, "val/cls_loss")
            t_box   = gf(row, "train/box_loss")
            fitness = (0.1 * map50 + 0.9 * map5095) if not (isnan(map50) or isnan(map5095)) else float("nan")
            epochs_data.append(dict(ep=ep, map50=map50, map5095=map5095,
                                    prec=prec, rec=rec, v_box=v_box, v_cls=v_cls,
                                    t_box=t_box, fitness=fitness))

        best = max(epochs_data, key=lambda x: x["fitness"] if not isnan(x["fitness"]) else -1)

        last10 = [e for e in epochs_data[-10:] if not isnan(e["map50"])]
        mid_start = max(0, n // 2 - 5)
        mid10  = [e for e in epochs_data[mid_start:mid_start + 10] if not isnan(e["map50"])]

        def avg(lst, key):
            vals = [e[key] for e in lst if not isnan(e[key])]
            return sum(vals) / len(vals) if vals else float("nan")

        still_improving = (not isnan(avg(last10, "map50")) and not isnan(avg(mid10, "map50"))
                           and avg(last10, "map50") > avg(mid10, "map50") + 0.005)

        last10_v = [e["v_box"] for e in last10 if not isnan(e["v_box"])]
        last10_t = [e["t_box"] for e in last10 if not isnan(e["t_box"])]
        overfit = (len(last10_v) >= 5
                   and last10_v[-1] - last10_v[0] > 0.01
                   and (last10_t[-1] - last10_t[0] < -0.005 if last10_t else False))

        last10_fit = [e["fitness"] for e in last10 if not isnan(e["fitness"])]
        plateau = (len(last10_fit) >= 5
                   and max(last10_fit) - min(last10_fit) < 0.003)

        best_ep    = int(best["ep"]) if not isnan(best["ep"]) else "?"
        best_map50 = best["map50"]
        best_map95 = best["map5095"]
        best_prec  = best["prec"]
        best_rec   = best["rec"]
        best_fit   = best["fitness"]

        def fmt(v, digits=4):
            return f"{v:.{digits}f}" if not isnan(v) else "—"

        lines = []
        SEP = "=" * 62
        DIV = "─" * 62
        lines += [SEP,
                  "  KZTEK YOLO — PHÂN TÍCH KẾT QUẢ TRAINING",
                  SEP,
                  f"  File   : {csv_path}",
                  f"  Epochs : {n}",
                  ""]

        lines += [f"  {'BEST MODEL':─<58}",
                  f"  Epoch tốt nhất  : ep{best_ep}",
                  f"  mAP50           : {fmt(best_map50)}",
                  f"  mAP50-95        : {fmt(best_map95)}",
                  f"  Precision       : {fmt(best_prec)}",
                  f"  Recall          : {fmt(best_rec)}",
                  f"  Fitness         : {fmt(best_fit)}",
                  ""]

        lines.append(f"  {'ĐÁNH GIÁ CHỈ SỐ':─<58}")
        if not isnan(best_map50):
            if best_map50 >= 0.85:  lines.append(f"  ✅ mAP50    {fmt(best_map50)}  XUẤT SẮC (≥0.85)")
            elif best_map50 >= 0.75: lines.append(f"  ✅ mAP50    {fmt(best_map50)}  TỐT (0.75–0.85)")
            elif best_map50 >= 0.65: lines.append(f"  ⚠  mAP50    {fmt(best_map50)}  KHÁ — cần cải thiện")
            else:                    lines.append(f"  ❌ mAP50    {fmt(best_map50)}  THẤP — cần thêm data hoặc model lớn hơn")
        if not isnan(best_map95):
            if best_map95 >= 0.70:   lines.append(f"  ✅ mAP50-95 {fmt(best_map95)}  TỐT (≥0.70)")
            elif best_map95 >= 0.55: lines.append(f"  ⚠  mAP50-95 {fmt(best_map95)}  TRUNG BÌNH")
            else:                    lines.append(f"  ❌ mAP50-95 {fmt(best_map95)}  THẤP — định vị chưa chính xác")
        if not isnan(best_prec):
            if best_prec >= 0.95:    lines.append(f"  ✅ Precision {fmt(best_prec)}  CAO — ít báo nhầm")
            elif best_prec >= 0.85:  lines.append(f"  ⚠  Precision {fmt(best_prec)}  TRUNG BÌNH — vẫn có false positive")
            else:                    lines.append(f"  ❌ Precision {fmt(best_prec)}  THẤP — nhiều false positive")
        if not isnan(best_rec):
            if best_rec >= 0.85:     lines.append(f"  ✅ Recall    {fmt(best_rec)}  CAO — ít bỏ sót")
            elif best_rec >= 0.75:   lines.append(f"  ⚠  Recall    {fmt(best_rec)}  TRUNG BÌNH — vẫn bỏ sót đối tượng")
            else:                    lines.append(f"  ❌ Recall    {fmt(best_rec)}  THẤP — bỏ sót nhiều")
        lines.append("")

        lines.append(f"  {'XU HƯỚNG TRAINING':─<58}")
        lines.append("  ✅ Không overfit" if not overfit else "  ⚠  OVERFIT: val loss tăng khi train loss giảm")
        if still_improving:
            lines.append(f"  📈 Vẫn đang cải thiện ở ep{n} — nên train thêm epochs")
        elif plateau:
            lines.append(f"  📊 Đã hội tụ (plateau) — đây là giới hạn cấu hình hiện tại")
        else:
            lines.append("  📉 Ổn định — training hoàn tất bình thường")
        lines.append("")

        lines.append(f"  {'ĐỀ XUẤT CẢI THIỆN':─<58}")
        recs = []
        if not isnan(best_map50) and best_map50 < 0.75:
            recs.append(("❶ Thêm dữ liệu đa dạng",
                         "mAP50 thấp — thu thập thêm ảnh từ nhiều góc độ, ánh sáng, thời điểm khác nhau."))
            recs.append(("❷ Thử model lớn hơn",
                         "Đổi yolo11n → yolo11s hoặc yolo11m (1 dòng code, +3-7% mAP)."))
        if not isnan(best_rec) and best_rec < 0.80:
            gap = 0.80 - best_rec
            recs.append((f"❸ Cải thiện Recall (hiện {fmt(best_rec)}, thiếu {gap:.3f})",
                         "Thu thập thêm:\n"
                         "  • Ảnh ban đêm / thiếu sáng\n"
                         "  • Xe góc nghiêng, xa camera\n"
                         "  • Biển số bị che khuất một phần\n"
                         "  • Loại xe ít ảnh (truck, bus)"))
        if not isnan(best_prec) and best_prec < 0.90:
            recs.append(("❹ Cải thiện Precision",
                         "Thêm ảnh 'hard negative' (cảnh không có đối tượng nhưng dễ nhầm)."))
        if still_improving and not overfit:
            recs.append((f"❺ Tăng epochs (đang cải thiện ở ep{n})",
                         f"Thử epochs={int(n * 1.5)} để khai thác thêm tiềm năng mô hình."))
        if plateau and not still_improving:
            recs.append(("❺ Model đã hội tụ — thử kiến trúc lớn hơn",
                         "Nâng yolo11n → yolo11s/m hoặc bổ sung thêm dữ liệu có chất lượng cao."))
        if overfit:
            recs.append(("❻ Chống Overfit",
                         "Tăng Weight Decay (0.001–0.005), thêm Dropout, hoặc dùng patience nhỏ hơn."))
        if not isnan(best_map95) and best_map95 < 0.55:
            recs.append(("❼ Tăng độ phân giải (imgsz)",
                         "mAP50-95 thấp — thử imgsz=1280 để phát hiện đối tượng nhỏ tốt hơn."))
        if not recs:
            recs.append(("✅ Kết quả rất tốt!", "Không có đề xuất đặc biệt — model hoạt động ổn định."))
        # Luôn thêm gợi ý nhanh nhất
        recs.append(("💡 Nâng cấp nhanh nhất",
                     "yolo11n → yolo11s: 1 dòng code, tăng mAP50 trung bình 3-7%, thời gian train gấp ~2x."))
        for title, desc in recs:
            lines.append(f"\n  {title}")
            for dl in desc.split("\n"):
                lines.append(f"  {dl}")

        import datetime as _dt
        lines += ["", SEP,
                  f"  Phân tích tạo lúc: {_dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                  SEP]
        return "\n".join(lines)

    def _open_analysis_window(self, report_text):
        """Hiện Toplevel với report và nút lưu file."""
        win = Toplevel(self.root)
        win.title("KZTEK – Phân tích kết quả training")
        win.geometry("740x560")
        win.configure(bg=BG)
        win.resizable(True, True)
        win.protocol("WM_DELETE_WINDOW", win.destroy)

        tb = Frame(win, bg=CARD, padx=8, pady=6)
        tb.pack(fill=X)
        Label(tb, text="Phân tích & Đề xuất cải thiện",
              bg=CARD, fg=TEXT, font=F_BOLD).pack(side=LEFT)

        def _save():
            path = filedialog.asksaveasfilename(
                title="Lưu báo cáo phân tích",
                defaultextension=".txt",
                filetypes=[("Text file", "*.txt"), ("Markdown", "*.md")],
                initialfile="analysis_report.txt")
            if not path:
                return
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(report_text)
                messagebox.showinfo("Đã lưu", f"Báo cáo đã lưu tại:\n{path}")
            except Exception as exc:
                messagebox.showerror("Lỗi lưu file", str(exc))

        Button(tb, text="💾  Lưu file", command=_save,
               bg=ACCENT, fg="white",
               activebackground=ACCENT2, activeforeground="white",
               font=F_MAIN, relief="flat", padx=10, cursor="hand2").pack(side=RIGHT)

        txt_frame = Frame(win, bg=BG)
        txt_frame.pack(fill=BOTH, expand=True, padx=8, pady=(4, 8))
        vsb = Scrollbar(txt_frame, orient=VERTICAL)
        vsb.pack(side=RIGHT, fill=Y)
        hsb = Scrollbar(txt_frame, orient=HORIZONTAL)
        hsb.pack(side=BOTTOM, fill=X)
        txt = Text(txt_frame, bg="#16162a", fg=TEXT, font=("Consolas", 9),
                   relief="flat", wrap=NONE, padx=10, pady=8,
                   yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        txt.pack(fill=BOTH, expand=True)
        vsb.config(command=txt.yview)
        hsb.config(command=txt.xview)

        txt.tag_config("hdr",  foreground=ACCENT,    font=("Consolas", 9, "bold"))
        txt.tag_config("sec",  foreground=ACCENT2)
        txt.tag_config("good", foreground=SUCCESS)
        txt.tag_config("warn", foreground="#f0c040")
        txt.tag_config("bad",  foreground="#f05050")
        txt.tag_config("tip",  foreground="#4fc3f7")

        for line in report_text.split("\n"):
            if line.startswith("=") or "KZTEK" in line or "PHÂN TÍCH" in line:
                txt.insert(END, line + "\n", "hdr")
            elif line.startswith("  ─") or line.startswith("  ━"):
                txt.insert(END, line + "\n", "sec")
            elif "✅" in line or "XUẤT SẮC" in line:
                txt.insert(END, line + "\n", "good")
            elif "⚠" in line or "TRUNG BÌNH" in line or "KHÁ" in line or "📈" in line or "📊" in line:
                txt.insert(END, line + "\n", "warn")
            elif "❌" in line or "THẤP" in line or "OVERFIT" in line or "📉" in line:
                txt.insert(END, line + "\n", "bad")
            elif any(c in line for c in ("💡", "❶", "❷", "❸", "❹", "❺", "❻", "❼")):
                txt.insert(END, line + "\n", "tip")
            else:
                txt.insert(END, line + "\n")

        txt.config(state=DISABLED)
        win.lift()
        win.focus_set()
        win.bind("<Escape>", lambda _: win.destroy())

    # ── Charts ───────────────────────────────────────────────────────

    def _update_charts(self):
        if not _MPL_OK:
            return
        if not self._chart_win or not self._chart_win.winfo_exists():
            return
        rows = self._read_csv()
        if not rows:
            return

        def _v(key):
            result = []
            for r in rows:
                try:
                    result.append(float(r[key]))
                except (KeyError, ValueError):
                    result.append(float("nan"))
            return result

        epochs = list(range(1, len(rows) + 1))
        axes   = self._axes

        _legend_kw = dict(
            fontsize=7, labelcolor=TEXT,
            facecolor="#1e1e2e", edgecolor="#2a2a3e",
            loc="upper right")

        def _plot(ax, title, series):
            ax.cla()
            ax.set_facecolor("#1e1e2e")
            for spine in ax.spines.values():
                spine.set_color("#2a2a3e")
            ax.tick_params(colors=DIM, labelsize=7)
            ax.set_title(title, color=TEXT, fontsize=9, pad=6)
            ax.set_xlabel("Epoch", color=DIM, fontsize=7)
            ax.xaxis.set_major_locator(
                __import__("matplotlib.ticker", fromlist=["MaxNLocator"])
                .MaxNLocator(integer=True, min_n_ticks=1))
            if epochs:
                ax.set_xlim(max(0.5, epochs[0] - 0.5), epochs[-1] + 0.5)
            plotted = False
            for key, label, color in series:
                vals = _v(key)
                if any(v == v for v in vals):
                    ax.plot(epochs, vals, label=label,
                            color=color, linewidth=1.6, alpha=0.9)
                    plotted = True
            if plotted:
                ax.legend(**_legend_kw)
                ax.grid(True, color="#2a2a3e", linewidth=0.5, alpha=0.6)

        _plot(axes[0, 0], "Train Loss", [
            ("train/box_loss", "box", _C_BOX),
            ("train/cls_loss", "cls", _C_CLS),
            ("train/dfl_loss", "dfl", _C_DFL),
        ])
        _plot(axes[0, 1], "Val Loss", [
            ("val/box_loss", "box", _C_BOX),
            ("val/cls_loss", "cls", _C_CLS),
            ("val/dfl_loss", "dfl", _C_DFL),
        ])
        _plot(axes[1, 0], "mAP", [
            ("metrics/mAP50(B)",    "mAP50",    _C_MAP50),
            ("metrics/mAP50-95(B)", "mAP50-95", _C_MAP5095),
        ])
        _plot(axes[1, 1], "Precision / Recall", [
            ("metrics/precision(B)", "Precision", _C_PREC),
            ("metrics/recall(B)",    "Recall",    _C_REC),
        ])

        n = len(rows)
        try:
            total = int(self._epochs_var.get())
        except ValueError:
            total = "?"
        self._epoch_lbl.config(text=f"Epoch {n} / {total}")
        try:
            self._mpl_canvas.draw()
        except Exception:
            pass

    def _start_chart_poll(self):
        self._update_charts()
        self._chart_poll_id = self.root.after(5000, self._start_chart_poll)

    def _stop_chart_poll(self):
        if self._chart_poll_id:
            self.root.after_cancel(self._chart_poll_id)
            self._chart_poll_id = None

    # ── History (Lịch sử train) ───────────────────────────────────────────

    def _history_file(self):
        project = self._project_var.get().strip()
        if not project:
            return None
        return Path(project) / "train_history.json"

    def _load_history(self):
        hf = self._history_file()
        if hf is None or not hf.exists():
            return []
        try:
            with open(hf, encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def _save_history(self, records):
        hf = self._history_file()
        if hf is None:
            return
        try:
            hf.parent.mkdir(parents=True, exist_ok=True)
            with open(hf, "w", encoding="utf-8") as f:
                json.dump(records, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _append_history_record(self, stopped_early=False):
        rows = self._read_csv()
        best_map = "—"
        if rows:
            try:
                vals = [float(r.get("metrics/mAP50(B)", "nan")) for r in rows]
                vals = [v for v in vals if v == v]
                if vals:
                    best_map = f"{max(vals):.4f}"
            except Exception:
                pass
        record = {
            "date":          datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "model":         self._model_var.get(),
            "epochs_done":   len(rows),
            "epochs_total":  self._epochs_var.get(),
            "best_mAP":      best_map,
            "output_dir":    self._output_dir,
            "stopped_early": stopped_early,
        }
        records = self._load_history()
        records.append(record)
        self._save_history(records)
        if self._history_win and self._history_win.winfo_exists():
            self._populate_history_tree()

    def _open_history_window(self):
        if self._history_win and self._history_win.winfo_exists():
            self._history_win.lift()
            self._populate_history_tree()
            return
        win = Toplevel(self.root)
        win.title("KZTEK – Lịch sử train")
        win.geometry("860x400")
        win.configure(bg=BG)
        self._history_win = win

        tb = Frame(win, bg=CARD, padx=8, pady=6)
        tb.pack(fill=X)
        Label(tb, text="Lịch sử các lần train", bg=CARD, fg=TEXT,
              font=F_BOLD).pack(side=LEFT)
        Button(tb, text="↻ Làm mới", command=self._populate_history_tree,
               bg=ACCENT2, fg="white", activebackground=ACCENT, activeforeground="white",
               font=F_MAIN, relief="flat", padx=8, cursor="hand2").pack(side=RIGHT)
        Button(tb, text="🗑 Xóa lịch sử",
               command=self._clear_history,
               bg="#c62828", fg="white", activebackground="#8b0000", activeforeground="white",
               font=F_MAIN, relief="flat", padx=8, cursor="hand2").pack(side=RIGHT, padx=(0, 4))

        cols = ("date", "model", "epochs", "best_mAP", "early", "output")
        self._hist_tree = ttk.Treeview(win, columns=cols, show="headings",
                                        style="Dark.Treeview", height=14)
        self._hist_tree.heading("date",     text="Ngày train")
        self._hist_tree.heading("model",    text="Model")
        self._hist_tree.heading("epochs",   text="Epochs")
        self._hist_tree.heading("best_mAP", text="Best mAP50")
        self._hist_tree.heading("early",    text="Kết thúc")
        self._hist_tree.heading("output",   text="Output dir")
        self._hist_tree.column("date",     width=140, anchor=CENTER, stretch=False)
        self._hist_tree.column("model",    width=100, anchor=CENTER, stretch=False)
        self._hist_tree.column("epochs",   width=80,  anchor=CENTER, stretch=False)
        self._hist_tree.column("best_mAP", width=90,  anchor=CENTER, stretch=False)
        self._hist_tree.column("early",    width=100, anchor=CENTER, stretch=False)
        self._hist_tree.column("output",   width=320, anchor=W)
        vsb = ttk.Scrollbar(win, orient=VERTICAL, command=self._hist_tree.yview)
        hsb = ttk.Scrollbar(win, orient=HORIZONTAL, command=self._hist_tree.xview)
        self._hist_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side=RIGHT, fill=Y)
        hsb.pack(side=BOTTOM, fill=X)
        self._hist_tree.pack(fill=BOTH, expand=True)
        self._hist_tree.tag_configure("early", foreground="#f0c040")
        self._hist_tree.tag_configure("done",  foreground=SUCCESS)
        self._hist_tree.bind("<Double-1>", self._on_history_dbl_click)

        self._populate_history_tree()

    def _populate_history_tree(self):
        if not hasattr(self, "_hist_tree"):
            return
        for iid in self._hist_tree.get_children():
            self._hist_tree.delete(iid)
        records = self._load_history()
        for rec in reversed(records):
            early      = rec.get("stopped_early", False)
            done_ep    = rec.get("epochs_done", "?")
            total_ep   = rec.get("epochs_total", "?")
            ep_str     = f"{done_ep}/{total_ep}"
            end_str    = "Early stop" if early else "Hoàn tất"
            tag        = "early" if early else "done"
            self._hist_tree.insert("", END, values=(
                rec.get("date", ""),
                rec.get("model", ""),
                ep_str,
                rec.get("best_mAP", "—"),
                end_str,
                rec.get("output_dir", ""),
            ), tags=(tag,))

    def _on_history_dbl_click(self, event):
        iid = self._hist_tree.identify_row(event.y)
        if not iid:
            return
        vals = self._hist_tree.item(iid, "values")
        output_dir = vals[5] if len(vals) > 5 else ""
        if not output_dir or not os.path.isdir(output_dir):
            messagebox.showinfo("Thông báo", f"Thư mục không tồn tại:\n{output_dir}")
            return
        self._output_dir = output_dir
        if _MPL_OK:
            self._open_chart_window()
            self._update_charts()
        messagebox.showinfo("Đã tải", f"Đã chuyển sang run:\n{output_dir}")

    def _clear_history(self):
        if not messagebox.askyesno("Xác nhận", "Xóa toàn bộ lịch sử train?"):
            return
        hf = self._history_file()
        if hf and hf.exists():
            try:
                hf.unlink()
            except Exception as e:
                messagebox.showerror("Lỗi", str(e))
                return
        self._populate_history_tree()

    # ── Checkpoint manager ────────────────────────────────────────────────

    def _open_checkpoint_window(self):
        if self._ckpt_win and self._ckpt_win.winfo_exists():
            self._ckpt_win.lift()
            self._populate_ckpt_list()
            return
        win = Toplevel(self.root)
        win.title("KZTEK – Checkpoint Manager")
        win.geometry("720x420")
        win.configure(bg=BG)
        self._ckpt_win = win

        tb = Frame(win, bg=CARD, padx=8, pady=6)
        tb.pack(fill=X)
        Label(tb, text="Danh sách checkpoint (.pt)", bg=CARD, fg=TEXT,
              font=F_BOLD).pack(side=LEFT)
        Button(tb, text="↻ Làm mới", command=self._populate_ckpt_list,
               bg=ACCENT2, fg="white", activebackground=ACCENT, activeforeground="white",
               font=F_MAIN, relief="flat", padx=8, cursor="hand2").pack(side=RIGHT)

        cols = ("name", "size", "modified")
        self._ckpt_tree = ttk.Treeview(win, columns=cols, show="headings",
                                        style="Dark.Treeview", height=14)
        self._ckpt_tree.heading("name",     text="Tên file")
        self._ckpt_tree.heading("size",     text="Kích thước")
        self._ckpt_tree.heading("modified", text="Ngày sửa")
        self._ckpt_tree.column("name",     width=200, anchor=W)
        self._ckpt_tree.column("size",     width=100, anchor=CENTER, stretch=False)
        self._ckpt_tree.column("modified", width=160, anchor=CENTER, stretch=False)
        vsb = ttk.Scrollbar(win, orient=VERTICAL, command=self._ckpt_tree.yview)
        vsb.pack(side=RIGHT, fill=Y)
        self._ckpt_tree.pack(fill=BOTH, expand=True)
        self._ckpt_tree.configure(yscrollcommand=vsb.set)

        btn_row = Frame(win, bg=BG, padx=8, pady=6)
        btn_row.pack(fill=X)
        Button(btn_row, text="📂 Load checkpoint",
               command=self._load_selected_checkpoint,
               bg="#2e7d32", fg="white", activebackground="#1b5e20", activeforeground="white",
               font=F_MAIN, relief="flat", padx=10, cursor="hand2").pack(side=LEFT)
        Button(btn_row, text="🗑 Xóa checkpoint",
               command=self._delete_selected_checkpoints,
               bg="#c62828", fg="white", activebackground="#8b0000", activeforeground="white",
               font=F_MAIN, relief="flat", padx=10, cursor="hand2").pack(side=LEFT, padx=(8, 0))
        self._ckpt_info_lbl = Label(btn_row, text="", bg=BG, fg=DIM, font=F_MAIN)
        self._ckpt_info_lbl.pack(side=LEFT, padx=12)

        self._populate_ckpt_list()

    def _ckpt_search_dirs(self):
        dirs = []
        if self._output_dir and os.path.isdir(self._output_dir):
            dirs.append(Path(self._output_dir))
            weights_dir = Path(self._output_dir) / "weights"
            if weights_dir.is_dir():
                dirs.append(weights_dir)
        project = self._project_var.get().strip()
        if project and os.path.isdir(project):
            p = Path(project)
            name = self._name_var.get().strip() or "kztek_train"
            run_dir = p / name
            if run_dir.is_dir():
                dirs.append(run_dir)
                wd = run_dir / "weights"
                if wd.is_dir():
                    dirs.append(wd)
        return dirs

    def _populate_ckpt_list(self):
        if not hasattr(self, "_ckpt_tree"):
            return
        for iid in self._ckpt_tree.get_children():
            self._ckpt_tree.delete(iid)
        self._ckpt_paths = {}
        dirs = self._ckpt_search_dirs()
        found = set()
        for d in dirs:
            for pt in sorted(d.glob("*.pt")):
                if pt in found:
                    continue
                found.add(pt)
                size_bytes = pt.stat().st_size
                size_str   = (f"{size_bytes / 1024 / 1024:.1f} MB"
                              if size_bytes >= 1024 * 1024
                              else f"{size_bytes / 1024:.0f} KB")
                mtime = datetime.datetime.fromtimestamp(pt.stat().st_mtime)
                mtime_str = mtime.strftime("%Y-%m-%d %H:%M")
                iid = self._ckpt_tree.insert("", END, values=(pt.name, size_str, mtime_str))
                self._ckpt_paths[iid] = pt
        count = len(found)
        if hasattr(self, "_ckpt_info_lbl"):
            self._ckpt_info_lbl.config(
                text=f"{count} file .pt" if count else "Không tìm thấy .pt",
                fg=TEXT if count else DIM)

    def _load_selected_checkpoint(self):
        sel = self._ckpt_tree.selection()
        if not sel:
            messagebox.showwarning("Chưa chọn", "Chọn một file .pt để load.")
            return
        pt_path = self._ckpt_paths.get(sel[0])
        if pt_path and pt_path.exists():
            self._model_var.set(str(pt_path))
            messagebox.showinfo("Đã load", f"Model path đã được đặt thành:\n{pt_path}")
        else:
            messagebox.showerror("Lỗi", "File không tồn tại.")

    def _delete_selected_checkpoints(self):
        sel = self._ckpt_tree.selection()
        if not sel:
            messagebox.showwarning("Chưa chọn", "Chọn các file .pt muốn xóa.")
            return
        names = [self._ckpt_paths[iid].name for iid in sel if iid in self._ckpt_paths]
        if not messagebox.askyesno("Xác nhận xóa",
                                    f"Xóa {len(names)} file:\n" + "\n".join(names)):
            return
        errors = []
        for iid in sel:
            pt = self._ckpt_paths.get(iid)
            if pt and pt.exists():
                try:
                    pt.unlink()
                except Exception as e:
                    errors.append(f"{pt.name}: {e}")
        if errors:
            messagebox.showerror("Lỗi", "\n".join(errors))
        self._populate_ckpt_list()

    # ── Augmentation preview ──────────────────────────────────────────────

    def _open_aug_preview(self):
        if not _PIL_OK:
            messagebox.showwarning(
                "Thiếu thư viện",
                "Cài Pillow để xem augmentation:\n\npip install Pillow")
            return
        train_dir = self.train_dir.get().strip()
        if not train_dir or not os.path.isdir(train_dir):
            messagebox.showwarning("Chưa có thư mục", "Chọn thư mục train trước.")
            return

        img_files = []
        for ext in IMAGE_EXTENSIONS:
            img_files.extend(Path(train_dir).rglob(f"*{ext}"))
            img_files.extend(Path(train_dir).rglob(f"*{ext.upper()}"))
        img_files = list(set(img_files))
        if not img_files:
            messagebox.showwarning("Không có ảnh", f"Không tìm thấy ảnh trong:\n{train_dir}")
            return

        if self._aug_win and self._aug_win.winfo_exists():
            self._aug_win.destroy()
        win = Toplevel(self.root)
        win.title("KZTEK – Augmentation Preview")
        win.geometry("900x520")
        win.configure(bg=BG)
        self._aug_win = win

        tb = Frame(win, bg=CARD, padx=8, pady=6)
        tb.pack(fill=X)
        Label(tb, text="Xem augmentation – ảnh gốc vs. ảnh đã biến đổi",
              bg=CARD, fg=TEXT, font=F_BOLD).pack(side=LEFT)
        self._aug_img_paths = img_files

        Button(tb, text="↻ Ảnh ngẫu nhiên",
               command=lambda: self._aug_refresh(win),
               bg=ACCENT2, fg="white", activebackground=ACCENT, activeforeground="white",
               font=F_MAIN, relief="flat", padx=8, cursor="hand2").pack(side=RIGHT)

        aug_params = Frame(win, bg=BG, padx=8, pady=4)
        aug_params.pack(fill=X)
        Label(aug_params, text="Flip:", bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT)
        self._aug_flip_var = BooleanVar(value=True)
        Checkbutton(aug_params, text="Ngang", variable=self._aug_flip_var,
                    bg=BG, fg=TEXT, activebackground=BG, selectcolor=CARD,
                    font=F_MAIN).pack(side=LEFT)
        Label(aug_params, text="  Brightness ±:", bg=BG, fg=DIM,
              font=F_MAIN).pack(side=LEFT)
        self._aug_bright_var = DoubleVar(value=0.3)
        Scale(aug_params, variable=self._aug_bright_var,
              from_=0.0, to=1.0, resolution=0.05, orient=HORIZONTAL,
              bg=BG, fg=TEXT, troughcolor=CARD, highlightthickness=0,
              length=100, font=F_MAIN).pack(side=LEFT)
        Label(aug_params, text="  Hue shift ±:", bg=BG, fg=DIM,
              font=F_MAIN).pack(side=LEFT)
        self._aug_hue_var = IntVar(value=30)
        Scale(aug_params, variable=self._aug_hue_var,
              from_=0, to=90, orient=HORIZONTAL,
              bg=BG, fg=TEXT, troughcolor=CARD, highlightthickness=0,
              length=100, font=F_MAIN).pack(side=LEFT)
        Button(aug_params, text="Áp dụng",
               command=lambda: self._aug_refresh(win),
               bg=ACCENT, fg="white", activebackground=ACCENT2, activeforeground="white",
               font=F_MAIN, relief="flat", padx=8, cursor="hand2").pack(side=LEFT, padx=(8, 0))

        img_frame = Frame(win, bg=BG)
        img_frame.pack(fill=BOTH, expand=True, padx=8, pady=4)
        img_frame.columnconfigure(0, weight=1)
        img_frame.columnconfigure(1, weight=1)

        Label(img_frame, text="Ảnh gốc", bg=BG, fg=DIM,
              font=F_MAIN).grid(row=0, column=0)
        Label(img_frame, text="Sau augmentation", bg=BG, fg=DIM,
              font=F_MAIN).grid(row=0, column=1)

        self._aug_lbl_orig = Label(img_frame, bg=BG)
        self._aug_lbl_orig.grid(row=1, column=0, padx=4, pady=4, sticky=NSEW)
        self._aug_lbl_aug  = Label(img_frame, bg=BG)
        self._aug_lbl_aug.grid(row=1, column=1, padx=4, pady=4, sticky=NSEW)
        img_frame.rowconfigure(1, weight=1)

        self._aug_fname_lbl = Label(win, text="", bg=BG, fg=DIM,
                                     font=("Segoe UI", 8, "italic"))
        self._aug_fname_lbl.pack()

        self._aug_refresh(win)

    def _aug_refresh(self, win):
        if not _PIL_OK or not hasattr(self, "_aug_img_paths") or not self._aug_img_paths:
            return
        img_path = random.choice(self._aug_img_paths)
        try:
            orig = _PILImage.open(img_path).convert("RGB")
        except Exception as e:
            messagebox.showerror("Lỗi mở ảnh", str(e))
            return

        aug = orig.copy()

        if self._aug_flip_var.get() and random.random() > 0.5:
            aug = aug.transpose(_PILImage.FLIP_LEFT_RIGHT)

        bright_delta = self._aug_bright_var.get()
        if bright_delta > 0:
            factor = 1.0 + random.uniform(-bright_delta, bright_delta)
            factor = max(0.1, factor)
            aug = _PILEnhance.Brightness(aug).enhance(factor)

        hue_shift = self._aug_hue_var.get()
        if hue_shift > 0:
            try:
                import colorsys
                h_delta = random.randint(-hue_shift, hue_shift) / 360.0
                r, g, b = aug.split()
                r_arr = list(r.getdata())
                g_arr = list(g.getdata())
                b_arr = list(b.getdata())
                new_r, new_g, new_b = [], [], []
                for rv, gv, bv in zip(r_arr, g_arr, b_arr):
                    h, s, v = colorsys.rgb_to_hsv(rv / 255, gv / 255, bv / 255)
                    h = (h + h_delta) % 1.0
                    nr, ng, nb = colorsys.hsv_to_rgb(h, s, v)
                    new_r.append(int(nr * 255))
                    new_g.append(int(ng * 255))
                    new_b.append(int(nb * 255))
                aug_r = _PILImage.new("L", aug.size)
                aug_g = _PILImage.new("L", aug.size)
                aug_b = _PILImage.new("L", aug.size)
                aug_r.putdata(new_r)
                aug_g.putdata(new_g)
                aug_b.putdata(new_b)
                aug = _PILImage.merge("RGB", (aug_r, aug_g, aug_b))
            except Exception:
                pass

        max_w, max_h = 420, 360
        orig_disp = self._pil_fit(orig, max_w, max_h)
        aug_disp  = self._pil_fit(aug,  max_w, max_h)

        self._aug_tk_orig = _PILImageTk.PhotoImage(orig_disp)
        self._aug_tk_aug  = _PILImageTk.PhotoImage(aug_disp)
        self._aug_lbl_orig.config(image=self._aug_tk_orig)
        self._aug_lbl_aug.config(image=self._aug_tk_aug)
        self._aug_fname_lbl.config(
            text=f"{img_path.name}  ({orig.width}×{orig.height})")

    @staticmethod
    def _pil_fit(img, max_w, max_h):
        w, h = img.size
        scale = min(max_w / w, max_h / h, 1.0)
        if scale < 1.0:
            img = img.resize((int(w * scale), int(h * scale)), _PILImage.LANCZOS)
        return img

    # ── UI event handlers ─────────────────────────────────────────────────

    def _on_model_change(self, _event):
        val = self._model_var.get()
        for name, desc in self._MODELS:
            if name == val:
                self._model_desc.config(text=desc); break

    def _on_split_change(self, *_):
        try:
            r = max(50, min(99, int(self._split_ratio_var.get())))
            self._split_val_lbl.config(text=f"% / Val {100 - r}%")
        except (ValueError, TclError):
            pass

    def _parse_labels(self):
        raw = self._labels_var.get().strip()
        return [s.strip() for s in raw.replace("\n", ",").split(",") if s.strip()]

    # ── Actions ───────────────────────────────────────────────────────────

    def _gen_yaml_only(self):
        labels = self._parse_labels()
        if not labels:
            messagebox.showerror("Lỗi", "Vui lòng nhập danh sách nhãn."); return
        try:
            path, split_msg, n_train, n_val = self._write_yaml(labels)
            _append_log(self._log,
                f"✔  data.yaml: {path}  ({n_train} train / {n_val} val)"
                + (f"\n   {split_msg}" if split_msg else ""))
            messagebox.showinfo("Tạo data.yaml",
                                f"Đã tạo:\n{path}\n\n{n_train} train / {n_val} val"
                                + (f"\n{split_msg}" if split_msg else ""))
        except Exception as e:
            messagebox.showerror("Lỗi", str(e))

    def _start_train(self):
        labels = self._parse_labels()
        if not labels:
            messagebox.showerror("Lỗi", "Vui lòng nhập danh sách nhãn."); return

        model   = self._model_var.get()
        project = self._project_var.get().strip() or str(
            Path(self.train_dir.get().strip() or ".").parent / "runs")
        name    = self._name_var.get().strip() or "train"

        try:
            epochs = int(self._epochs_var.get())
            imgsz  = int(self._imgsz_var.get())
            batch  = int(self._batch_var.get())
        except ValueError:
            messagebox.showerror("Lỗi", "Epochs / Imgsz / Batch phải là số nguyên.")
            return
        device = self._device_var.get().strip() or "0"

        optimizer = self._optimizer_var.get().strip() or "AdamW"
        try:
            lr0 = float(self._lr0_var.get())
        except ValueError:
            lr0 = 0.01
        try:
            lrf = float(self._lrf_var.get())
        except ValueError:
            lrf = 0.01
        try:
            close_mosaic = int(self._close_mosaic_var.get())
        except ValueError:
            close_mosaic = 10
        try:
            workers = int(self._workers_var.get())
        except ValueError:
            workers = 4
        try:
            weight_decay = float(self._weight_decay_var.get())
        except ValueError:
            weight_decay = 0.0005
        cache_raw = self._cache_var.get().strip()
        cache_py  = "False" if cache_raw == "False" else f"'{cache_raw}'"
        cos_lr    = self._cos_lr_var.get()

        early_stop = self._early_stop_var.get()
        try:
            patience = int(self._patience_var.get())
        except ValueError:
            patience = 10

        try:
            yaml_path, split_msg, n_train, n_val = self._write_yaml(labels)
        except Exception as e:
            messagebox.showerror("Lỗi tạo data.yaml", str(e)); return

        early_stop_lines = ""
        if early_stop:
            early_stop_lines = (
                f"    import inspect\n"
                f"    _sig = inspect.signature(model.train)\n"
                f"    _kw = {{}}\n"
                f"    if 'patience' in _sig.parameters:\n"
                f"        _kw['patience'] = {patience}\n"
            )
            train_call = (
                f"    results = model.train(\n"
                f"        data={yaml_path!r},\n"
                f"        epochs={epochs},\n"
                f"        imgsz={imgsz},\n"
                f"        batch={batch},\n"
                f"        device={device!r},\n"
                f"        project={project!r},\n"
                f"        name={name!r},\n"
                f"        exist_ok=True,\n"
                f"        optimizer={optimizer!r},\n"
                f"        lr0={lr0},\n"
                f"        lrf={lrf},\n"
                f"        close_mosaic={close_mosaic},\n"
                f"        cache={cache_py},\n"
                f"        workers={workers},\n"
                f"        cos_lr={cos_lr},\n"
                f"        weight_decay={weight_decay},\n"
                f"        **_kw,\n"
                f"    )\n"
            )
        else:
            early_stop_lines = ""
            train_call = (
                f"    results = model.train(\n"
                f"        data={yaml_path!r},\n"
                f"        epochs={epochs},\n"
                f"        imgsz={imgsz},\n"
                f"        batch={batch},\n"
                f"        device={device!r},\n"
                f"        project={project!r},\n"
                f"        name={name!r},\n"
                f"        exist_ok=True,\n"
                f"        optimizer={optimizer!r},\n"
                f"        lr0={lr0},\n"
                f"        lrf={lrf},\n"
                f"        close_mosaic={close_mosaic},\n"
                f"        cache={cache_py},\n"
                f"        workers={workers},\n"
                f"        cos_lr={cos_lr},\n"
                f"        weight_decay={weight_decay},\n"
                f"    )\n"
            )

        script = (
            "import os, sys, multiprocessing\n"
            "multiprocessing.freeze_support()\n"
            "if __name__ == '__main__':\n"
            "    os.environ.setdefault('KMP_DUPLICATE_LIB_OK', 'TRUE')\n"
            "    try:\n"
            "        from ultralytics import YOLO\n"
            "    except ImportError:\n"
            "        print('[LỖI] ultralytics chưa được cài. Chạy: pip install ultralytics')\n"
            "        sys.exit(1)\n"
            f"    model = YOLO({model!r})\n"
            + early_stop_lines
            + train_call
            + "    print(f'KZTEK_SAVE_DIR: {results.save_dir}')\n"
            + f"    csv_path = str(results.save_dir) + '/results.csv'\n"
            + "    import csv as _csv, os as _os\n"
            + "    _epochs_done = 0\n"
            + "    if _os.path.exists(csv_path):\n"
            + "        with open(csv_path, newline='', encoding='utf-8') as _f:\n"
            + "            _epochs_done = sum(1 for _ in _csv.DictReader(_f))\n"
            + f"    if _epochs_done < {epochs}:\n"
            + "        print(f'KZTEK_EARLY_STOP: {_epochs_done}')\n"
        )
        tmp_script = Path(tempfile.gettempdir()) / "kztek_train_job.py"
        tmp_script.write_text(script, encoding="utf-8")

        self._log.configure(state=NORMAL)
        self._log.delete("1.0", END)
        self._log.configure(state=DISABLED)
        _append_log(self._log,
            f"▶  model={model}  epochs={epochs}  imgsz={imgsz}  "
            f"batch={batch}  device={device}")
        if early_stop:
            _append_log(self._log, f"   Early stopping: patience={patience}")
        _append_log(self._log, f"   data.yaml : {yaml_path}")
        _append_log(self._log, f"   dataset   : {n_train} train / {n_val} val")
        if split_msg:
            _append_log(self._log, f"   {split_msg}")
        _append_log(self._log, f"   output    : {project}/{name}")
        _append_log(self._log, "─" * 70)

        self._train_epochs_total = epochs
        self._train_stopped_early = False

        try:
            self._proc = subprocess.Popen(
                [sys.executable, str(tmp_script)],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1)
        except Exception as e:
            messagebox.showerror("Lỗi khởi động", str(e)); return

        self._output_dir = os.path.join(project, name)
        self._btn_start.config(state=DISABLED)
        self._btn_stop.config(state=NORMAL)
        self._status_lbl.config(text="⏳ Đang train…", fg=ACCENT)
        self._result_lbl.config(text="—")
        self._open_btn.config(state=DISABLED)

        if _MPL_OK:
            self._open_chart_window()
            self._stop_chart_poll()
            self._start_chart_poll()

        proc = self._proc
        q    = self._out_queue

        def _reader():
            for raw in iter(proc.stdout.readline, b""):
                q.put(raw.decode("utf-8", errors="replace"))
            q.put(None)

        threading.Thread(target=_reader, daemon=True).start()
        self._poll_output()

    def _stop_train(self):
        self._stop_chart_poll()
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            _append_log(self._log, "⚠  Training đã bị dừng thủ công.")
        self._btn_start.config(state=NORMAL)
        self._btn_stop.config(state=DISABLED)
        self._status_lbl.config(text="Đã dừng", fg="#f0c040")

    def _poll_output(self):
        try:
            while True:
                line = self._out_queue.get_nowait()
                if line is None:
                    self._on_done(); return
                text = line.rstrip()
                if not text:
                    continue
                if "KZTEK_SAVE_DIR:" in text:
                    self._output_dir = text.split("KZTEK_SAVE_DIR:", 1)[1].strip()
                    continue
                if "KZTEK_EARLY_STOP:" in text:
                    try:
                        done = int(text.split("KZTEK_EARLY_STOP:", 1)[1].strip())
                        self._train_stopped_early = done < getattr(
                            self, "_train_epochs_total", done + 1)
                    except Exception:
                        pass
                    continue
                text = re.sub(r"\x1b\[[0-9;]*[mKA-Z]", "", text)
                text = re.sub(r"\[[\d;]*m",             "", text)
                if text:
                    _append_log(self._log, text)
        except queue.Empty:
            pass
        self._poll_id = self.root.after(500, self._poll_output)

    def _on_done(self):
        self._stop_chart_poll()
        rc = -1
        if self._proc:
            try:
                self._proc.wait(timeout=10)
            except Exception:
                pass
            rc = self._proc.returncode
            if rc is None:
                rc = 0
        self._proc = None
        if self._poll_id:
            self.root.after_cancel(self._poll_id); self._poll_id = None
        self._btn_start.config(state=NORMAL)
        self._btn_stop.config(state=DISABLED)
        if rc == 0:
            best = os.path.join(self._output_dir, "weights", "best.pt")
            _append_log(self._log, "─" * 70)
            stopped_early = getattr(self, "_train_stopped_early", False)
            if stopped_early:
                _append_log(self._log, "⚡  Early stopping đã kích hoạt — training dừng sớm.")
                _append_log(self._log, f"   best.pt → {best}")
                self._status_lbl.config(text="⚡ Early stopped", fg="#f0c040")
                self._early_note_lbl.config(
                    text="(lần train trước: dừng sớm)", fg="#f0c040")
            else:
                _append_log(self._log, f"✔  Hoàn tất!  best.pt → {best}")
                self._status_lbl.config(text="✔ Hoàn tất", fg=SUCCESS)
                self._early_note_lbl.config(text="", fg=DIM)
            self._result_lbl.config(text=f"best.pt  →  {best}")
            self._open_btn.config(state=NORMAL)
            self._update_charts()
            self._append_history_record(stopped_early=stopped_early)
            if self._ckpt_win and self._ckpt_win.winfo_exists():
                self._populate_ckpt_list()
        else:
            _append_log(self._log, f"[LỖI]  Tiến trình kết thúc với exit code {rc}")
            self._status_lbl.config(text=f"Lỗi (exit {rc})", fg="#f05050")

    def _open_output_dir(self):
        d = self._output_dir
        if os.path.isdir(d):
            subprocess.Popen(["explorer", os.path.normpath(d)])
        else:
            messagebox.showinfo("Thông báo", f"Thư mục chưa tồn tại:\n{d}")

    # ── Shortcut aliases ─────────────────────────────────────────────

    def _browse(self):
        """Ctrl+O — chọn thư mục train."""
        p = filedialog.askdirectory(
            title="Chọn thư mục train",
            initialdir=_cfg_dir("train.dir"))
        if p:
            self.train_dir.set(p)
            _push_history("h.train.dir", p)

    def _start_action(self):
        """F5 — bắt đầu train."""
        self._start_train()

    def _stop(self):
        """Escape — dừng training."""
        self._stop_train()

    def _save(self):
        """Ctrl+S — tạo data.yaml."""
        self._gen_yaml_only()

    # ── Glossary ──────────────────────────────────────────────────────────────

    def _build_train_glossary(self):
        TERMS = [
            ("Model (yolo11n / s / m / l / x)",
             "Kích thước kiến trúc YOLO11: n=nano (nhỏ nhất, nhanh nhất), s=small, m=medium, l=large, x=xlarge (lớn nhất, chính xác nhất). Nano phù hợp nhúng/edge; large/xlarge cần GPU mạnh."),
            ("Epochs",
             "Số lần lặp toàn bộ tập dữ liệu. Epochs=50 nghĩa là model 'nhìn' mỗi ảnh đúng 50 lần. Quá ít → underfitting; quá nhiều → overfitting nếu không có early stopping."),
            ("Imgsz (Image Size)",
             "Kích thước ảnh đầu vào sau khi resize về hình vuông NxN (ví dụ 640x640). Ảnh lớn hơn → chính xác hơn với vật nhỏ nhưng chậm hơn và tốn VRAM hơn."),
            ("Batch Size",
             "Số ảnh xử lý trong một lần cập nhật trọng số (gradient step). Batch=16 nghĩa là mỗi bước tính loss trên 16 ảnh rồi mới cập nhật. Batch=-1 để YOLO tự chọn tối đa theo VRAM."),
            ("Device",
             "Phần cứng chạy training. '0' = GPU đầu tiên (CUDA), '0,1' = nhiều GPU, 'cpu' = CPU (chậm hơn ~10-50×). Kiểm tra bằng lệnh nvidia-smi."),
            ("Optimizer",
             "Thuật toán tối ưu gradient: SGD (ổn định, phổ biến), Adam (hội tụ nhanh hơn), AdamW (Adam + weight decay). Auto = YOLO tự chọn dựa vào số epochs."),
            ("LR0 (Learning Rate khởi đầu)",
             "Tốc độ học ban đầu. Giá trị lớn → học nhanh nhưng dễ dao động; giá trị nhỏ → ổn định nhưng hội tụ chậm. Finetune từ pretrained nên dùng LR0 nhỏ (0.0001–0.001)."),
            ("LRF (Learning Rate kết thúc)",
             "Hệ số nhân để tính LR cuối: LR_cuối = LR0 × LRF. Ví dụ LR0=0.01, LRF=0.1 → LR giảm xuống 0.001 ở epoch cuối. Cosine LR sẽ giảm dần theo hàm cosine trong khoảng này."),
            ("Cosine LR",
             "Lịch giảm learning rate hình cosine: LR giảm mượt từ LR0 xuống LR0×LRF thay vì giảm thẳng (linear). Thường cho kết quả tốt hơn linear decay vì tránh 'nhảy' đột ngột."),
            ("Close Mosaic",
             "Tắt augmentation mosaic trong N epoch cuối. Mosaic ghép 4 ảnh thành 1 giúp model học đa dạng hơn, nhưng ở giai đoạn tinh chỉnh cuối, tắt mosaic giúp val loss hội tụ chính xác hơn."),
            ("Weight Decay",
             "L2 regularization — phạt các trọng số quá lớn để tránh overfitting. Thêm hạng phạt λ×||w||² vào loss. Giá trị điển hình: 0.0005. Tăng nếu model overfit mạnh."),
            ("Workers",
             "Số luồng (thread) song song đọc và augment ảnh từ đĩa cứng. Workers cao hơn → GPU ít bị idle chờ dữ liệu, nhưng tốn RAM hơn. Trên Windows thường dùng 4–8."),
            ("Cache (False / ram / disk)",
             "Cách cache ảnh để tăng tốc: False=không cache (đọc từ disk mỗi epoch), 'disk'=cache dưới dạng .npy trên ổ cứng, 'ram'=load hết vào RAM. RAM nhanh nhất nhưng cần nhiều bộ nhớ."),
            ("Early Stopping / Patience",
             "Dừng training sớm nếu fitness không cải thiện sau Patience epoch liên tiếp. YOLO fitness = 0.1×mAP50 + 0.9×mAP50-95. Giúp tiết kiệm thời gian và tránh overfitting."),
            ("mAP50 / mAP50-95",
             "Độ chính xác detection. mAP50 = mean Average Precision tại ngưỡng IoU=50% (dễ đạt hơn). mAP50-95 = trung bình trên 10 ngưỡng IoU từ 50% đến 95% (khắt khe hơn, chuẩn COCO)."),
            ("Train Loss (box / cls / dfl)",
             "Loss trong quá trình train: box=sai số vị trí bounding box, cls=sai số phân loại class, dfl=Distribution Focal Loss (hình dạng bbox). Cả ba nên giảm đều theo epoch."),
            ("best.pt / last.pt",
             "Checkpoint lưu trọng số: best.pt=epoch có fitness cao nhất, last.pt=epoch cuối cùng. Dùng best.pt để inference. Khi early stop, last.pt có thể giống best.pt."),
            ("data.yaml",
             "File cấu hình dataset: đường dẫn train/val, số class (nc), tên class (names). YOLO bắt buộc cần file này. Nút 'Tạo YAML' sẽ tự sinh file này từ thư mục đã chọn."),
            ("Subfolder / Train / Val",
             "Trong panel Subfolder: mỗi dòng là một thư mục con, có thể gán vai trò Train hoặc Val. Có thể tự chia theo tỷ lệ (ví dụ 80/20) hoặc chỉ định thủ công."),
            ("Run Name / Output Folder",
             "Tên thư mục lưu kết quả training (weights/, results.csv, charts). Mặc định YOLO lưu vào runs/detect/<run_name>. Đặt tên có nghĩa để dễ so sánh nhiều lần train."),
        ]

        gloss_outer = Frame(self, bg=BG, padx=12)
        gloss_outer.pack(fill=X, pady=(4, 0))

        self._gloss_train_open = BooleanVar(value=False)
        toggle_btn = Button(gloss_outer,
                            text="ℹ  Giải thích thuật ngữ  ▾",
                            bg=CARD, fg=DIM, font=("Segoe UI", 9),
                            relief="flat", cursor="hand2", anchor="w",
                            command=self._toggle_train_glossary)
        toggle_btn.pack(fill=X, ipady=4)
        self._gloss_train_toggle_btn = toggle_btn

        self._gloss_train_frame = Frame(gloss_outer, bg=CARD)
        txt = Text(self._gloss_train_frame, bg=CARD, fg=TEXT,
                   font=("Segoe UI", 9), relief="flat", wrap=WORD,
                   cursor="arrow", height=18, padx=14, pady=8)
        txt.pack(fill=X)
        txt.tag_config("term", foreground=ACCENT, font=("Segoe UI", 9, "bold"))
        txt.tag_config("desc", foreground=TEXT, font=("Segoe UI", 9))
        for term, desc in TERMS:
            txt.insert(END, f"▸ {term}\n", "term")
            txt.insert(END, f"  {desc}\n\n", "desc")
        txt.config(state=DISABLED)

    def _toggle_train_glossary(self):
        if self._gloss_train_open.get():
            self._gloss_train_frame.pack_forget()
            self._gloss_train_toggle_btn.config(text="ℹ  Giải thích thuật ngữ  ▾")
            self._gloss_train_open.set(False)
        else:
            self._gloss_train_frame.pack(fill=X)
            self._gloss_train_toggle_btn.config(text="ℹ  Giải thích thuật ngữ  ▴")
            self._gloss_train_open.set(True)
