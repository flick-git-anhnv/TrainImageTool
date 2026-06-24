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
        self._batch_var       = StringVar(value="-1")
        self._device_var      = StringVar(value="0")
        self._project_var     = StringVar()
        self._name_var        = StringVar(value="kztek_train")
        self._split_ratio_var = IntVar(value=80)
        self._recursive_var   = BooleanVar(value=False)
        _bind_cfg("train.project", self._project_var)

        self._early_stop_var     = BooleanVar(value=False)
        self._patience_var       = StringVar(value="10")

        self._optimizer_var     = StringVar(value="AdamW")
        self._lr0_var           = StringVar(value="0.001")
        self._lrf_var           = StringVar(value="0.01")
        self._close_mosaic_var  = StringVar(value="10")
        self._cache_var         = StringVar(value="False")
        self._workers_var       = StringVar(value="4")
        self._cos_lr_var        = BooleanVar(value=True)
        self._weight_decay_var  = StringVar(value="0.0005")
        _bind_cfg("train.optimizer",    self._optimizer_var)
        _bind_cfg("train.lr0",          self._lr0_var)
        _bind_cfg("train.lrf",          self._lrf_var)
        _bind_cfg("train.close_mosaic", self._close_mosaic_var)
        _bind_cfg("train.cache",        self._cache_var)
        _bind_cfg("train.workers",      self._workers_var)
        _bind_cfg("train.cos_lr",       self._cos_lr_var)
        _bind_cfg("train.weight_decay", self._weight_decay_var)

        # ── Advanced training params ──────────────────────────────────────
        self._amp_var           = BooleanVar(value=True)
        self._label_smooth_var  = StringVar(value="0.1")
        self._mixup_var         = StringVar(value="0.15")
        self._copy_paste_var    = StringVar(value="0.1")
        self._degrees_var       = StringVar(value="10.0")
        self._cls_var           = StringVar(value="1.5")
        self._momentum_var      = StringVar(value="0.937")
        self._warmup_var        = StringVar(value="3")
        # ── 2-Stage training ─────────────────────────────────────────────
        self._two_stage_var     = BooleanVar(value=False)
        self._freeze_epochs_var = StringVar(value="30")
        self._freeze_layers_var = StringVar(value="10")
        self._freeze_lr_var     = StringVar(value="0.001")
        _bind_cfg("train.amp",          self._amp_var)
        _bind_cfg("train.label_smooth", self._label_smooth_var)
        _bind_cfg("train.mixup",        self._mixup_var)
        _bind_cfg("train.copy_paste",   self._copy_paste_var)
        _bind_cfg("train.degrees",      self._degrees_var)
        _bind_cfg("train.cls",          self._cls_var)
        _bind_cfg("train.momentum",     self._momentum_var)
        _bind_cfg("train.warmup",       self._warmup_var)
        _bind_cfg("train.two_stage",    self._two_stage_var)
        _bind_cfg("train.freeze_ep",    self._freeze_epochs_var)
        _bind_cfg("train.freeze_lay",   self._freeze_layers_var)
        _bind_cfg("train.freeze_lr",    self._freeze_lr_var)

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

        self._history_win    = None
        self._ckpt_win       = None
        self._aug_win        = None
        self._miss_win       = None
        self._fp_win         = None
        self._imbalance_win    = None
        self._shape_win        = None
        self._brightness_win   = None

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
            ("Batch:",   self._batch_var,  "−1=auto/0.9=90%VRAM"),
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
        Checkbutton(adv2, text="AMP", variable=self._amp_var,
                    bg=CARD, fg=TEXT, activebackground=CARD, activeforeground=TEXT,
                    selectcolor="#16162a", font=F_MAIN).pack(side=LEFT, padx=(14, 0))
        Label(adv2, text="  Cache:", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        ttk.Combobox(adv2, textvariable=self._cache_var, width=6,
                     state="readonly", font=F_MAIN,
                     values=["False", "ram", "disk"]).pack(side=LEFT, padx=(4, 0))
        Label(adv2,
              text="   (AMP: giảm ~40% VRAM, tăng tốc ~30%; ram: load ảnh vào RAM)",
              bg=CARD, fg=DIM,
              font=("Segoe UI", 8, "italic")).pack(side=LEFT, padx=(8, 0))

        # ── Augmentation nâng cao ─────────────────────────────────────────
        Label(pf, text="Augmentation:", bg=CARD, fg=DIM,
              font=F_BOLD).grid(row=7, column=0, sticky=W, pady=(8, 2))
        adv3 = Frame(pf, bg=CARD)
        adv3.grid(row=7, column=1, columnspan=9, sticky=W, pady=(8, 2))
        for _lbl, _var, _w, _tip in [
            ("Label Smooth:", self._label_smooth_var, 5, "0–0.2"),
            ("Mixup:",        self._mixup_var,         5, "0–0.5"),
            ("Copy-Paste:",   self._copy_paste_var,    5, "0–0.5"),
            ("Degrees:",      self._degrees_var,       5, "°rot"),
            ("CLS weight:",   self._cls_var,           4, "loss"),
            ("Momentum:",     self._momentum_var,      6, "SGD"),
            ("Warmup ep:",    self._warmup_var,        3, "ep"),
        ]:
            Label(adv3, text=_lbl, bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
            Entry(adv3, textvariable=_var, bg="#16162a", fg=TEXT,
                  insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4,
                  width=_w).pack(side=LEFT, padx=(2, 2))
            Label(adv3, text=_tip, bg=CARD, fg="#606080",
                  font=("Segoe UI", 7, "italic")).pack(side=LEFT, padx=(0, 8))

        # ── 2-Stage Training ──────────────────────────────────────────────
        adv4 = Frame(pf, bg=CARD)
        adv4.grid(row=8, column=0, columnspan=10, sticky=W, pady=(6, 0))
        Checkbutton(adv4, text="2-Stage Training  (Freeze Backbone → Full Fine-tune)",
                    variable=self._two_stage_var,
                    bg=CARD, fg=ACCENT, activebackground=CARD, activeforeground=ACCENT,
                    selectcolor="#16162a", font=F_BOLD,
                    command=self._on_two_stage_toggle).pack(side=LEFT)

        self._ts_frame = Frame(pf, bg=CARD)
        self._ts_frame.grid(row=9, column=0, columnspan=10, sticky=W, pady=(2, 6))
        Label(self._ts_frame, text="  Stage1 epochs:", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        self._ts_ep_e = Entry(self._ts_frame, textvariable=self._freeze_epochs_var,
                               bg="#16162a", fg=TEXT, insertbackground=TEXT,
                               relief="flat", font=F_MAIN, bd=4, width=5)
        self._ts_ep_e.pack(side=LEFT, padx=(2, 10))
        Label(self._ts_frame, text="Freeze layers:", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        self._ts_lay_e = Entry(self._ts_frame, textvariable=self._freeze_layers_var,
                                bg="#16162a", fg=TEXT, insertbackground=TEXT,
                                relief="flat", font=F_MAIN, bd=4, width=5)
        self._ts_lay_e.pack(side=LEFT, padx=(2, 10))
        Label(self._ts_frame, text="Stage1 LR:", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        self._ts_lr_e = Entry(self._ts_frame, textvariable=self._freeze_lr_var,
                               bg="#16162a", fg=TEXT, insertbackground=TEXT,
                               relief="flat", font=F_MAIN, bd=4, width=8)
        self._ts_lr_e.pack(side=LEFT, padx=(2, 10))
        Label(self._ts_frame,
              text="→ Stage2: main epochs + main lr0 + full network + mixup/copy-paste",
              bg=CARD, fg=DIM, font=("Segoe UI", 8, "italic")).pack(side=LEFT, padx=(4, 0))
        self._on_two_stage_toggle()

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

        self._btn_resume = Button(ctrl, text="↩  Tiếp tục Train",
                                   command=self._resume_train,
                                   bg="#1565c0", fg="white",
                                   activebackground="#0d47a1", activeforeground="white",
                                   font=F_BOLD, relief="flat", padx=14, cursor="hand2")
        self._btn_resume.pack(side=LEFT, padx=(8, 0))

        self._btn_continue = Button(ctrl, text="🔄  Train thêm",
                                     command=self._continue_train,
                                     bg="#6a1b9a", fg="white",
                                     activebackground="#4a148c", activeforeground="white",
                                     font=F_BOLD, relief="flat", padx=14, cursor="hand2")
        self._btn_continue.pack(side=LEFT, padx=(8, 0))

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

        Button(ctrl, text="🔍  Miss Analysis",
               command=self._open_miss_analysis,
               bg=ACCENT2, fg="white",
               activebackground=ACCENT, activeforeground="white",
               font=F_BOLD, relief="flat", padx=14, cursor="hand2").pack(side=LEFT, padx=(8, 0))

        Button(ctrl, text="⚠  FP Analysis",
               command=self._open_fp_analysis,
               bg=ACCENT2, fg="white",
               activebackground=ACCENT, activeforeground="white",
               font=F_BOLD, relief="flat", padx=14, cursor="hand2").pack(side=LEFT, padx=(8, 0))

        self._status_lbl = Label(ctrl, text="", bg=BG, fg=DIM, font=F_MAIN)
        self._status_lbl.pack(side=LEFT, padx=16)

        ctrl2 = Frame(self, bg=BG, padx=12, pady=2)
        ctrl2.pack(fill=X)
        Label(ctrl2, text="Dataset Analysis:", bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT)
        for _txt, _cmd in [
            ("📊  Imbalance",    self._open_imbalance_analysis),
            ("📐  Size & Shape", self._open_shape_analysis),
            ("☀  Brightness",   self._open_brightness_analysis),
            ("📋  HTML Report",  self._generate_html_report),
        ]:
            Button(ctrl2, text=_txt, command=_cmd,
                   bg=ACCENT2, fg="white",
                   activebackground=ACCENT, activeforeground="white",
                   font=F_MAIN, relief="flat", padx=12, cursor="hand2").pack(side=LEFT, padx=(8, 0))

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
        Button(res, text="⚡ Export Model",
               command=self._export_model,
               bg="#1565c0", fg="white",
               activebackground="#0d47a1", activeforeground="white",
               font=F_MAIN, relief="flat", padx=10, cursor="hand2").pack(side=LEFT, padx=4)

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

    def _on_two_stage_toggle(self):
        enabled = self._two_stage_var.get()
        state = NORMAL if enabled else DISABLED
        for e in (getattr(self, "_ts_ep_e", None),
                  getattr(self, "_ts_lay_e", None),
                  getattr(self, "_ts_lr_e", None)):
            if e:
                try:
                    e.config(state=state)
                except Exception:
                    pass

    # ── Export model ──────────────────────────────────────────────────────

    def _export_model(self):
        """Dialog export best.pt → ONNX / OpenVINO / TensorRT."""
        best_pt = self._find_best_pt()

        dlg = Toplevel(self.root)
        dlg.title("KZTEK – Export Model")
        dlg.configure(bg=BG)
        dlg.resizable(True, True)
        dlg.grab_set()

        _pt_var    = StringVar(value=str(best_pt) if best_pt else "")
        _fmt_var   = StringVar(value="onnx")
        _imgsz_var = StringVar(value=self._imgsz_var.get())
        _half_var  = BooleanVar(value=True)
        _dyn_var   = BooleanVar(value=False)

        Label(dlg, text="Export Model cho Deployment", bg=BG, fg=TEXT,
              font=F_BOLD, padx=16, pady=10).pack(anchor=W)

        pt_row = Frame(dlg, bg=BG)
        pt_row.pack(fill=X, padx=16, pady=4)
        Label(pt_row, text="Model (.pt):", bg=BG, fg=DIM, font=F_MAIN,
              width=14, anchor=W).pack(side=LEFT)
        Entry(pt_row, textvariable=_pt_var, bg="#16162a", fg=TEXT,
              insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4,
              width=42).pack(side=LEFT, padx=(4, 4))

        def _browse_pt():
            p = filedialog.askopenfilename(
                title="Chọn model .pt",
                filetypes=[("PyTorch model", "*.pt"), ("All files", "*.*")],
                initialdir=self._project_var.get().strip() or ".")
            if p:
                _pt_var.set(p)
        Button(pt_row, text="📂", command=_browse_pt,
               bg=CARD, fg=TEXT, activebackground=ACCENT2, activeforeground="white",
               font=F_MAIN, relief="flat", padx=6, cursor="hand2").pack(side=LEFT)

        Frame(dlg, bg=DIM, height=1).pack(fill=X, padx=16, pady=6)
        Label(dlg, text="Format xuất:", bg=BG, fg=TEXT,
              font=F_BOLD, padx=16).pack(anchor=W)
        for _lbl, _val, _note in [
            ("ONNX",           "onnx",      "→ dùng với C# OnnxRuntime, universal"),
            ("OpenVINO FP16",  "openvino",  "→ Intel CPU/iGPU nhanh nhất (~3× vs PyTorch)"),
            ("TensorRT",       "engine",    "→ NVIDIA GPU, cần TensorRT cài sẵn"),
        ]:
            r = Frame(dlg, bg=BG)
            r.pack(fill=X, padx=24, pady=2)
            Radiobutton(r, text=_lbl, variable=_fmt_var, value=_val,
                        bg=BG, fg=TEXT, activebackground=BG, activeforeground=ACCENT,
                        selectcolor=CARD, font=F_MAIN, width=16).pack(side=LEFT)
            Label(r, text=_note, bg=BG, fg=DIM,
                  font=("Segoe UI", 8, "italic")).pack(side=LEFT)

        Frame(dlg, bg=DIM, height=1).pack(fill=X, padx=16, pady=6)
        opt = Frame(dlg, bg=BG)
        opt.pack(fill=X, padx=16, pady=4)
        Label(opt, text="Imgsz:", bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT)
        Entry(opt, textvariable=_imgsz_var, bg="#16162a", fg=TEXT,
              insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4,
              width=6).pack(side=LEFT, padx=(4, 16))
        Checkbutton(opt, text="Half / FP16", variable=_half_var,
                    bg=BG, fg=TEXT, activebackground=BG, activeforeground=TEXT,
                    selectcolor=CARD, font=F_MAIN).pack(side=LEFT, padx=(0, 12))
        Checkbutton(opt, text="Dynamic batch", variable=_dyn_var,
                    bg=BG, fg=TEXT, activebackground=BG, activeforeground=TEXT,
                    selectcolor=CARD, font=F_MAIN).pack(side=LEFT)

        log_f = Frame(dlg, bg=BG)
        log_f.pack(fill=BOTH, expand=True, padx=16, pady=(6, 4))
        vsb = Scrollbar(log_f, orient=VERTICAL)
        vsb.pack(side=RIGHT, fill=Y)
        _log_txt = Text(log_f, bg="#16162a", fg=TEXT, font=("Consolas", 8),
                        height=7, relief="flat", state=DISABLED, wrap=NONE,
                        yscrollcommand=vsb.set)
        _log_txt.pack(fill=BOTH, expand=True)
        vsb.config(command=_log_txt.yview)

        def _append(msg):
            _log_txt.config(state=NORMAL)
            _log_txt.insert(END, msg)
            _log_txt.see(END)
            _log_txt.config(state=DISABLED)
            dlg.update_idletasks()

        def _run_export():
            pt = _pt_var.get().strip()
            if not pt or not Path(pt).exists():
                messagebox.showerror("Lỗi", "Chọn file .pt hợp lệ.", parent=dlg)
                return
            fmt   = _fmt_var.get()
            imgsz = _imgsz_var.get().strip() or "640"
            half  = _half_var.get()
            dyn   = _dyn_var.get()
            _append(f"▶ Export {Path(pt).name} → {fmt} (imgsz={imgsz}, half={half})\n")

            script = (
                "import os, sys\n"
                "os.environ.setdefault('KMP_DUPLICATE_LIB_OK', 'TRUE')\n"
                "from ultralytics import YOLO\n"
                f"model = YOLO({pt!r})\n"
                f"result = model.export(\n"
                f"    format={fmt!r},\n"
                f"    imgsz={imgsz},\n"
                f"    half={half},\n"
                f"    dynamic={dyn},\n"
                f")\n"
                "print(f'EXPORT_OK: {result}')\n"
            )
            tmp = Path(tempfile.gettempdir()) / "kztek_export_job.py"
            tmp.write_text(script, encoding="utf-8")

            import subprocess as _sp
            proc = _sp.Popen([sys.executable, str(tmp)],
                             stdout=_sp.PIPE, stderr=_sp.STDOUT, bufsize=1)

            def _stream():
                for raw in iter(proc.stdout.readline, b""):
                    _append(raw.decode("utf-8", errors="replace"))
                proc.wait()
                ok = proc.returncode == 0
                _append("\n✅ Export thành công!\n" if ok else "\n❌ Export thất bại!\n")

            threading.Thread(target=_stream, daemon=True).start()

        btn_row = Frame(dlg, bg=BG)
        btn_row.pack(fill=X, padx=16, pady=(4, 16))
        Button(btn_row, text="⚡  Export", command=_run_export,
               bg="#1565c0", fg="white",
               activebackground="#0d47a1", activeforeground="white",
               font=F_BOLD, relief="flat", padx=16, cursor="hand2").pack(side=LEFT)
        Button(btn_row, text="Đóng", command=dlg.destroy,
               bg=CARD, fg=DIM, activebackground=ACCENT2, activeforeground="white",
               font=F_MAIN, relief="flat", padx=12, cursor="hand2").pack(side=LEFT, padx=(8, 0))

        dlg.bind("<Escape>", lambda _: dlg.destroy())
        dlg.update_idletasks()
        sw = dlg.winfo_screenwidth(); sh = dlg.winfo_screenheight()
        w = max(dlg.winfo_reqwidth(), 620); h = max(dlg.winfo_reqheight(), 420)
        dlg.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")
        dlg.lift(); dlg.focus_set()

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
            _b_raw = self._batch_var.get().strip()
            batch  = float(_b_raw) if "." in _b_raw else int(_b_raw)
        except ValueError:
            messagebox.showerror("Lỗi", "Epochs/Imgsz là số nguyên; Batch: số (−1=auto, 0.9=90%VRAM).")
            return
        device = self._device_var.get().strip() or "0"

        optimizer = self._optimizer_var.get().strip() or "AdamW"
        try:
            lr0 = float(self._lr0_var.get())
        except ValueError:
            lr0 = 0.001
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
        amp       = self._amp_var.get()
        try:
            label_smooth = float(self._label_smooth_var.get())
        except ValueError:
            label_smooth = 0.1
        try:
            mixup = float(self._mixup_var.get())
        except ValueError:
            mixup = 0.15
        try:
            copy_paste = float(self._copy_paste_var.get())
        except ValueError:
            copy_paste = 0.1
        try:
            degrees = float(self._degrees_var.get())
        except ValueError:
            degrees = 10.0
        try:
            cls = float(self._cls_var.get())
        except ValueError:
            cls = 1.5
        try:
            momentum = float(self._momentum_var.get())
        except ValueError:
            momentum = 0.937
        try:
            warmup = int(self._warmup_var.get())
        except ValueError:
            warmup = 3
        two_stage = self._two_stage_var.get()
        try:
            freeze_epochs = int(self._freeze_epochs_var.get())
        except ValueError:
            freeze_epochs = 30
        try:
            freeze_layers = int(self._freeze_layers_var.get())
        except ValueError:
            freeze_layers = 10
        try:
            freeze_lr = float(self._freeze_lr_var.get())
        except ValueError:
            freeze_lr = 0.001

        early_stop = self._early_stop_var.get()
        try:
            patience = int(self._patience_var.get())
        except ValueError:
            patience = 10

        try:
            yaml_path, split_msg, n_train, n_val = self._write_yaml(labels)
        except Exception as e:
            messagebox.showerror("Lỗi tạo data.yaml", str(e)); return

        # ── Params chung cho cả 2 stage ──────────────────────────────────
        _cp = (
            f"        data={yaml_path!r},\n"
            f"        imgsz={imgsz},\n"
            f"        batch={batch},\n"
            f"        device={device!r},\n"
            f"        optimizer={optimizer!r},\n"
            f"        lrf={lrf},\n"
            f"        close_mosaic={close_mosaic},\n"
            f"        cache={cache_py},\n"
            f"        workers={workers},\n"
            f"        cos_lr={cos_lr},\n"
            f"        weight_decay={weight_decay},\n"
            f"        amp={amp},\n"
            f"        label_smoothing={label_smooth},\n"
            f"        momentum={momentum},\n"
            f"        warmup_epochs={warmup},\n"
        )
        # Augmentation nâng cao — chỉ dùng cho full fine-tune (stage 2 hoặc 1-stage)
        _ap = (
            f"        mixup={mixup},\n"
            f"        copy_paste={copy_paste},\n"
            f"        degrees={degrees},\n"
            f"        cls={cls},\n"
        )
        _ekw = ""
        _xkw = ""
        if early_stop:
            _ekw = (
                f"    import inspect as _insp\n"
                f"    _sig = _insp.signature(model.train)\n"
                f"    _kw = {{}}\n"
                f"    if 'patience' in _sig.parameters:\n"
                f"        _kw['patience'] = {patience}\n"
            )
            _xkw = "        **_kw,\n"

        if two_stage:
            train_call = (
                f"    print('===== STAGE 1: FREEZE (layers={freeze_layers}, {freeze_epochs}ep, lr={freeze_lr}) =====')\n"
                f"    results1 = model.train(\n"
                + _cp
                + f"        epochs={freeze_epochs},\n"
                + f"        project={project!r},\n"
                + f"        name={name + '_s1'!r},\n"
                + f"        exist_ok=True,\n"
                + f"        freeze={freeze_layers},\n"
                + f"        lr0={freeze_lr},\n"
                + f"    )\n"
                + f"    _best1 = str(results1.save_dir) + '/weights/best.pt'\n"
                + f"    print(f'Stage 1 xong. Best: {{_best1}}')\n"
                + f"    print('===== STAGE 2: FULL FINE-TUNE ({epochs}ep, lr={lr0}) =====')\n"
                + f"    model = YOLO(_best1)\n"
                + _ekw
                + f"    results = model.train(\n"
                + _cp
                + _ap
                + f"        epochs={epochs},\n"
                + f"        project={project!r},\n"
                + f"        name={name!r},\n"
                + f"        exist_ok=True,\n"
                + f"        freeze=0,\n"
                + f"        lr0={lr0},\n"
                + _xkw
                + f"    )\n"
            )
        else:
            train_call = (
                _ekw
                + f"    results = model.train(\n"
                + _cp
                + _ap
                + f"        epochs={epochs},\n"
                + f"        project={project!r},\n"
                + f"        name={name!r},\n"
                + f"        exist_ok=True,\n"
                + f"        lr0={lr0},\n"
                + _xkw
                + f"    )\n"
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
            + f"    model = YOLO({model!r})\n"
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
        self._btn_resume.config(state=NORMAL)
        self._btn_continue.config(state=NORMAL)
        self._btn_stop.config(state=DISABLED)
        self._status_lbl.config(text="Đã dừng", fg="#f0c040")

    def _resume_train(self):
        """Tiếp tục training từ last.pt sau khi bị gián đoạn."""
        # Tìm last.pt tự động từ output_dir hoặc project/name
        last_pt = self._find_last_pt()
        if last_pt is None:
            last_pt_str = filedialog.askopenfilename(
                title="Chọn file last.pt để tiếp tục train",
                filetypes=[("PyTorch checkpoint", "*.pt"), ("All files", "*.*")],
                initialdir=self._project_var.get().strip() or ".")
            if not last_pt_str:
                return
            last_pt = Path(last_pt_str)

        if not last_pt.exists():
            messagebox.showerror("Không tìm thấy", f"File không tồn tại:\n{last_pt}")
            return

        device = self._device_var.get().strip() or "0"
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
            f"    model = YOLO({str(last_pt)!r})\n"
            f"    results = model.train(resume=True, device={device!r})\n"
            "    print(f'KZTEK_SAVE_DIR: {results.save_dir}')\n"
        )
        tmp_script = Path(tempfile.gettempdir()) / "kztek_resume_job.py"
        tmp_script.write_text(script, encoding="utf-8")

        self._log.configure(state=NORMAL)
        self._log.delete("1.0", END)
        self._log.configure(state=DISABLED)
        _append_log(self._log, f"↩  Tiếp tục train từ checkpoint: {last_pt}")
        _append_log(self._log, f"   device={device}")
        _append_log(self._log, "─" * 70)

        self._train_stopped_early = False
        self._train_epochs_total  = 0

        try:
            self._proc = subprocess.Popen(
                [sys.executable, str(tmp_script)],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1)
        except Exception as e:
            messagebox.showerror("Lỗi khởi động", str(e)); return

        # Cập nhật output_dir về thư mục chứa last.pt (weights → parent)
        wd = last_pt.parent
        self._output_dir = str(wd.parent if wd.name == "weights" else wd)

        self._btn_start.config(state=DISABLED)
        self._btn_resume.config(state=DISABLED)
        self._btn_stop.config(state=NORMAL)
        self._status_lbl.config(text="⏳ Đang tiếp tục train…", fg=ACCENT)
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

    def _find_last_pt(self):
        """Tìm last.pt từ output_dir hoặc project/name/weights."""
        candidates = []
        if self._output_dir and os.path.isdir(self._output_dir):
            candidates.append(Path(self._output_dir) / "weights" / "last.pt")
            candidates.append(Path(self._output_dir) / "last.pt")
        project = self._project_var.get().strip()
        name    = self._name_var.get().strip() or "kztek_train"
        if project:
            candidates.append(Path(project) / name / "weights" / "last.pt")
        for p in candidates:
            if p.exists():
                return p
        return None

    def _find_best_pt(self):
        """Tìm best.pt từ output_dir hoặc project/name/weights."""
        candidates = []
        if self._output_dir and os.path.isdir(self._output_dir):
            candidates.append(Path(self._output_dir) / "weights" / "best.pt")
            candidates.append(Path(self._output_dir) / "best.pt")
        project = self._project_var.get().strip()
        name    = self._name_var.get().strip() or "kztek_train"
        if project:
            candidates.append(Path(project) / name / "weights" / "best.pt")
        for p in candidates:
            if p.exists():
                return p
        return None

    def _ask_continue_params(self, best_pt, last_pt):
        """Dialog hỏi: chọn best/last/custom .pt + số epochs train thêm.
        Returns (pt_path, epochs) hoặc None nếu user hủy."""
        result = [None]

        dlg = Toplevel(self.root)
        dlg.title("Train thêm epochs")
        dlg.configure(bg=BG)
        dlg.resizable(False, False)
        dlg.grab_set()

        Label(dlg, text="Chọn checkpoint để train thêm",
              bg=BG, fg=TEXT, font=F_BOLD,
              padx=16, pady=10).pack(anchor=W)

        _pt_choice = StringVar(
            value="best" if best_pt else ("last" if last_pt else "custom"))
        _custom_pt = StringVar()

        def _radio_row(text, value, pt_path):
            r = Frame(dlg, bg=BG)
            r.pack(fill=X, padx=16, pady=2)
            rb = Radiobutton(r, text=text, variable=_pt_choice, value=value,
                             bg=BG, fg=TEXT, activebackground=BG,
                             activeforeground=ACCENT, selectcolor=CARD, font=F_MAIN)
            rb.pack(side=LEFT)
            if pt_path:
                Label(r, text=str(pt_path), bg=BG, fg=DIM,
                      font=("Segoe UI", 8, "italic")).pack(side=LEFT, padx=(4, 0))
            else:
                rb.config(state=DISABLED, fg=DIM)

        _radio_row("best.pt  (model chính xác nhất)", "best", best_pt)
        _radio_row("last.pt  (checkpoint epoch cuối)", "last", last_pt)

        custom_row = Frame(dlg, bg=BG)
        custom_row.pack(fill=X, padx=16, pady=2)
        Radiobutton(custom_row, text="Chọn file khác…", variable=_pt_choice,
                    value="custom", bg=BG, fg=TEXT, activebackground=BG,
                    activeforeground=ACCENT, selectcolor=CARD,
                    font=F_MAIN).pack(side=LEFT)
        custom_entry = Entry(custom_row, textvariable=_custom_pt,
                             bg="#16162a", fg=TEXT, insertbackground=TEXT,
                             relief="flat", font=F_MAIN, bd=4, width=32)
        custom_entry.pack(side=LEFT, padx=(4, 4))

        def _browse():
            _pt_choice.set("custom")
            p = filedialog.askopenfilename(
                title="Chọn file .pt để train thêm",
                filetypes=[("PyTorch model", "*.pt"), ("All files", "*.*")],
                initialdir=self._project_var.get().strip() or ".")
            if p:
                _custom_pt.set(p)

        Button(custom_row, text="📂", command=_browse,
               bg=CARD, fg=TEXT, activebackground=ACCENT2, activeforeground="white",
               font=F_MAIN, relief="flat", padx=6, cursor="hand2").pack(side=LEFT)

        Frame(dlg, bg=DIM, height=1).pack(fill=X, padx=16, pady=10)

        ep_row = Frame(dlg, bg=BG)
        ep_row.pack(fill=X, padx=16, pady=4)
        Label(ep_row, text="Số epochs train thêm:", bg=BG, fg=TEXT,
              font=F_MAIN).pack(side=LEFT)
        _extra_ep = StringVar(value="50")
        Entry(ep_row, textvariable=_extra_ep,
              bg="#16162a", fg=TEXT, insertbackground=TEXT,
              relief="flat", font=F_MAIN, bd=4, width=8).pack(side=LEFT, padx=(8, 4))
        Label(ep_row, text="epochs", bg=BG, fg=DIM,
              font=("Segoe UI", 8, "italic")).pack(side=LEFT)

        Label(dlg,
              text="Output sẽ tạo run mới (không ghi đè run cũ)",
              bg=BG, fg=DIM, font=("Segoe UI", 8, "italic"),
              padx=16).pack(anchor=W, pady=(4, 0))

        btn_row = Frame(dlg, bg=BG)
        btn_row.pack(fill=X, padx=16, pady=(12, 16))

        def _ok():
            choice = _pt_choice.get()
            if choice == "best":
                pt = best_pt
            elif choice == "last":
                pt = last_pt
            else:
                raw = _custom_pt.get().strip()
                pt  = Path(raw) if raw else None
            if pt is None or not Path(str(pt)).exists():
                messagebox.showerror("Lỗi", "Vui lòng chọn file .pt hợp lệ.", parent=dlg)
                return
            try:
                ep = int(_extra_ep.get())
                if ep <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Lỗi", "Số epochs phải là số nguyên dương.", parent=dlg)
                return
            result[0] = (pt, ep)
            dlg.destroy()

        def _cancel():
            dlg.destroy()

        Button(btn_row, text="🔄  Bắt đầu Train thêm", command=_ok,
               bg="#6a1b9a", fg="white",
               activebackground="#4a148c", activeforeground="white",
               font=F_BOLD, relief="flat", padx=18, cursor="hand2").pack(side=LEFT)
        Button(btn_row, text="Hủy", command=_cancel,
               bg=CARD, fg=DIM, activebackground=ACCENT2, activeforeground="white",
               font=F_MAIN, relief="flat", padx=12, cursor="hand2").pack(side=LEFT, padx=(8, 0))

        dlg.bind("<Return>", lambda _e: _ok())
        dlg.bind("<Escape>", lambda _e: _cancel())
        dlg.update_idletasks()
        sw = dlg.winfo_screenwidth()
        sh = dlg.winfo_screenheight()
        w  = dlg.winfo_width()
        h  = dlg.winfo_height()
        dlg.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")
        dlg.wait_window()
        return result[0]

    def _continue_train(self):
        """Train thêm epochs từ best.pt/last.pt sau khi đã train xong đủ số epoch."""
        best_pt = self._find_best_pt()
        last_pt = self._find_last_pt()

        params = self._ask_continue_params(best_pt, last_pt)
        if params is None:
            return
        pt_file, extra_epochs = params

        labels = self._parse_labels()
        if not labels:
            messagebox.showerror("Lỗi", "Vui lòng nhập danh sách nhãn."); return

        try:
            yaml_path, split_msg, n_train, n_val = self._write_yaml(labels)
        except Exception as e:
            messagebox.showerror("Lỗi tạo data.yaml", str(e)); return

        project = self._project_var.get().strip() or str(
            Path(self.train_dir.get().strip() or ".").parent / "runs")
        name = self._name_var.get().strip() or "kztek_train"

        try:
            imgsz  = int(self._imgsz_var.get())
            _b_raw = self._batch_var.get().strip()
            batch  = float(_b_raw) if "." in _b_raw else int(_b_raw)
        except ValueError:
            messagebox.showerror("Lỗi", "Imgsz là số nguyên; Batch: số (−1=auto)."); return

        device    = self._device_var.get().strip() or "0"
        optimizer = self._optimizer_var.get().strip() or "AdamW"
        try:
            lr0 = float(self._lr0_var.get())
        except ValueError:
            lr0 = 0.001
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
        cache_raw    = self._cache_var.get().strip()
        cache_py     = "False" if cache_raw == "False" else f"'{cache_raw}'"
        cos_lr       = self._cos_lr_var.get()
        amp          = self._amp_var.get()
        try:
            label_smooth = float(self._label_smooth_var.get())
        except ValueError:
            label_smooth = 0.1
        try:
            mixup = float(self._mixup_var.get())
        except ValueError:
            mixup = 0.15
        try:
            copy_paste = float(self._copy_paste_var.get())
        except ValueError:
            copy_paste = 0.1
        try:
            degrees = float(self._degrees_var.get())
        except ValueError:
            degrees = 10.0
        try:
            cls = float(self._cls_var.get())
        except ValueError:
            cls = 1.5
        try:
            momentum = float(self._momentum_var.get())
        except ValueError:
            momentum = 0.937
        try:
            warmup = int(self._warmup_var.get())
        except ValueError:
            warmup = 3

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
            f"    model = YOLO({str(pt_file)!r})\n"
            f"    results = model.train(\n"
            f"        data={yaml_path!r},\n"
            f"        epochs={extra_epochs},\n"
            f"        imgsz={imgsz},\n"
            f"        batch={batch},\n"
            f"        device={device!r},\n"
            f"        project={project!r},\n"
            f"        name={name!r},\n"
            f"        exist_ok=False,\n"
            f"        optimizer={optimizer!r},\n"
            f"        lr0={lr0},\n"
            f"        lrf={lrf},\n"
            f"        close_mosaic={close_mosaic},\n"
            f"        cache={cache_py},\n"
            f"        workers={workers},\n"
            f"        cos_lr={cos_lr},\n"
            f"        weight_decay={weight_decay},\n"
            f"        amp={amp},\n"
            f"        label_smoothing={label_smooth},\n"
            f"        mixup={mixup},\n"
            f"        copy_paste={copy_paste},\n"
            f"        degrees={degrees},\n"
            f"        cls={cls},\n"
            f"        momentum={momentum},\n"
            f"        warmup_epochs={warmup},\n"
            f"    )\n"
            "    print(f'KZTEK_SAVE_DIR: {results.save_dir}')\n"
        )
        tmp_script = Path(tempfile.gettempdir()) / "kztek_continue_job.py"
        tmp_script.write_text(script, encoding="utf-8")

        self._log.configure(state=NORMAL)
        self._log.delete("1.0", END)
        self._log.configure(state=DISABLED)
        _append_log(self._log,
                    f"🔄  Train thêm {extra_epochs} epochs từ: {pt_file}")
        _append_log(self._log, f"   data.yaml : {yaml_path}")
        _append_log(self._log, f"   dataset   : {n_train} train / {n_val} val")
        if split_msg:
            _append_log(self._log, f"   {split_msg}")
        _append_log(self._log, f"   output    : {project}/{name}[+N]")
        _append_log(self._log, "─" * 70)

        self._train_epochs_total  = extra_epochs
        self._train_stopped_early = False

        try:
            self._proc = subprocess.Popen(
                [sys.executable, str(tmp_script)],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1)
        except Exception as e:
            messagebox.showerror("Lỗi khởi động", str(e)); return

        self._btn_start.config(state=DISABLED)
        self._btn_resume.config(state=DISABLED)
        self._btn_continue.config(state=DISABLED)
        self._btn_stop.config(state=NORMAL)
        self._status_lbl.config(text="⏳ Đang train thêm…", fg=ACCENT)
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
        self._btn_resume.config(state=NORMAL)
        self._btn_continue.config(state=NORMAL)
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

    # ── Miss Detection Analysis ───────────────────────────────────────────────

    def _open_miss_analysis(self):
        """Cửa sổ phân tích False Negative (bị bỏ sót) theo class."""
        if self._miss_win and self._miss_win.winfo_exists():
            self._miss_win.lift()
            return

        win = Toplevel(self.root)
        win.title("KZTEK – Miss Detection Analysis")
        win.geometry("820x660")
        win.configure(bg=BG)
        win.resizable(True, True)
        win.protocol("WM_DELETE_WINDOW", win.destroy)
        self._miss_win = win

        # ── Config ────────────────────────────────────────────────────
        cfg = Frame(win, bg=CARD, padx=12, pady=10)
        cfg.pack(fill=X, padx=8, pady=(8, 4))
        cfg.columnconfigure(1, weight=1)

        Label(cfg, text="Phân tích ảnh bị bỏ sót (False Negative) theo class",
              bg=CARD, fg=TEXT, font=F_BOLD).grid(
                  row=0, column=0, columnspan=3, sticky=W, pady=(0, 8))

        miss_model_var = StringVar()
        best_pt = os.path.join(self._output_dir, "weights", "best.pt") if self._output_dir else ""
        if best_pt and os.path.isfile(best_pt):
            miss_model_var.set(best_pt)

        miss_img_var = StringVar()
        miss_lbl_var = StringVar()

        def _pick_model():
            p = filedialog.askopenfilename(
                title="Chọn model .pt",
                filetypes=[("PyTorch model", "*.pt"), ("All", "*.*")],
                initialdir=str(Path(miss_model_var.get()).parent)
                           if miss_model_var.get() and os.path.isfile(miss_model_var.get()) else ".")
            if p:
                miss_model_var.set(p)

        def _pick_imgs():
            p = filedialog.askdirectory(title="Chọn thư mục val/images",
                                        initialdir=miss_img_var.get() or ".")
            if p:
                miss_img_var.set(p)
                cand = str(Path(p).parent / "labels")
                if os.path.isdir(cand):
                    miss_lbl_var.set(cand)

        def _pick_lbls():
            p = filedialog.askdirectory(title="Chọn thư mục val/labels",
                                        initialdir=miss_lbl_var.get() or miss_img_var.get() or ".")
            if p:
                miss_lbl_var.set(p)

        for row, (lbl_txt, var, cmd) in enumerate([
            ("Model (.pt):",  miss_model_var, _pick_model),
            ("Val images:",   miss_img_var,   _pick_imgs),
            ("Val labels:",   miss_lbl_var,   _pick_lbls),
        ], start=1):
            Label(cfg, text=lbl_txt, bg=CARD, fg=DIM, font=F_MAIN,
                  width=14, anchor=W).grid(row=row, column=0, sticky=W, pady=3)
            Entry(cfg, textvariable=var, bg="#16162a", fg=TEXT,
                  insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4).grid(
                      row=row, column=1, sticky=EW, padx=(8, 4))
            Button(cfg, text="…", command=cmd,
                   bg=ACCENT2, fg="white", font=F_MAIN, relief="flat",
                   padx=8, cursor="hand2").grid(row=row, column=2)

        pr = Frame(cfg, bg=CARD)
        pr.grid(row=4, column=0, columnspan=3, sticky=W, pady=(8, 0))
        miss_conf_var = StringVar(value="0.25")
        miss_iou_var  = StringVar(value="0.3")
        miss_max_var  = StringVar(value="80")
        miss_cls_var  = StringVar(value=self._labels_var.get())
        for lbl_t, var, w in [("Conf:", miss_conf_var, 5),
                               ("IoU:",  miss_iou_var,  5),
                               ("Max save:", miss_max_var, 5)]:
            Label(pr, text=lbl_t, bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
            Entry(pr, textvariable=var, bg="#16162a", fg=TEXT,
                  insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4,
                  width=w).pack(side=LEFT, padx=(4, 12))
        Label(pr, text="Classes:", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        Entry(pr, textvariable=miss_cls_var, bg="#16162a", fg=TEXT,
              insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4,
              width=32).pack(side=LEFT, padx=(4, 0))
        Label(pr, text="  (để trống = tất cả)", bg=CARD, fg=DIM,
              font=("Segoe UI", 7, "italic")).pack(side=LEFT)

        # ── Controls ──────────────────────────────────────────────────
        ctrl_row = Frame(win, bg=BG, padx=8, pady=4)
        ctrl_row.pack(fill=X)
        miss_run_btn = Button(ctrl_row, text="▶  Chạy phân tích",
                              bg="#2e7d32", fg="white",
                              activebackground="#1b5e20", activeforeground="white",
                              font=F_BOLD, relief="flat", padx=16, cursor="hand2")
        miss_run_btn.pack(side=LEFT)
        miss_open_btn = Button(ctrl_row, text="📂  Mở thư mục",
                               bg=ACCENT2, fg="white",
                               activebackground=ACCENT, activeforeground="white",
                               font=F_MAIN, relief="flat", padx=12, cursor="hand2",
                               state=DISABLED)
        miss_open_btn.pack(side=LEFT, padx=(8, 0))
        miss_status = Label(ctrl_row, text="", bg=BG, fg=DIM, font=F_MAIN)
        miss_status.pack(side=LEFT, padx=12)

        pb_f = Frame(win, bg=BG, padx=8)
        pb_f.pack(fill=X)
        miss_pb = ttk.Progressbar(pb_f, maximum=100)
        miss_pb.pack(fill=X, pady=(2, 4))

        # ── Results table ─────────────────────────────────────────────
        res_f = Frame(win, bg=BG, padx=8)
        res_f.pack(fill=BOTH, expand=True, pady=(4, 0))
        cols = ("cls", "total", "missed", "rate",
                "tiny", "small", "med", "large", "avg_sz")
        miss_tree = ttk.Treeview(res_f, columns=cols, show="headings",
                                  style="Dark.Treeview", height=10)
        for col, hdr, w, anc in [
            ("cls",    "Class",      120, W),
            ("total",  "Tổng GT",     70, CENTER),
            ("missed", "Missed",      70, CENTER),
            ("rate",   "Miss %",      80, CENTER),
            ("tiny",   "Tiny <2%",    80, CENTER),
            ("small",  "Small 2-5%",  80, CENTER),
            ("med",    "Med 5-15%",   80, CENTER),
            ("large",  "Large >15%",  80, CENTER),
            ("avg_sz", "Avg size%",   80, CENTER),
        ]:
            miss_tree.heading(col, text=hdr)
            miss_tree.column(col, width=w, anchor=anc, stretch=(col == "cls"))
        vsb = ttk.Scrollbar(res_f, orient=VERTICAL,   command=miss_tree.yview)
        hsb = ttk.Scrollbar(res_f, orient=HORIZONTAL, command=miss_tree.xview)
        miss_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side=RIGHT, fill=Y)
        hsb.pack(side=BOTTOM, fill=X)
        miss_tree.pack(fill=BOTH, expand=True)
        miss_tree.tag_configure("ok",   foreground=SUCCESS)
        miss_tree.tag_configure("warn", foreground="#f0c040")
        miss_tree.tag_configure("bad",  foreground="#f05050")

        sum_lbl = Label(win, text="", bg=BG, fg=DIM,
                        font=("Consolas", 9), anchor=W, padx=8)
        sum_lbl.pack(fill=X, pady=(2, 6))

        miss_out_dir = [None]

        def _do_run():
            model_path = miss_model_var.get().strip()
            img_dir    = miss_img_var.get().strip()
            lbl_dir    = miss_lbl_var.get().strip()
            if not model_path or not os.path.isfile(model_path):
                messagebox.showwarning("Thiếu model", "Chọn file model .pt hợp lệ.", parent=win)
                return
            if not img_dir or not os.path.isdir(img_dir):
                messagebox.showwarning("Thiếu val images", "Chọn thư mục val/images.", parent=win)
                return
            if not lbl_dir:
                lbl_dir = str(Path(img_dir).parent / "labels")
            if not os.path.isdir(lbl_dir):
                messagebox.showwarning("Thiếu labels",
                                       f"Không tìm thấy thư mục labels:\n{lbl_dir}", parent=win)
                return
            try:
                conf_v    = float(miss_conf_var.get())
                iou_v     = float(miss_iou_var.get())
                max_save  = int(miss_max_var.get())
            except ValueError:
                conf_v, iou_v, max_save = 0.25, 0.3, 80
            cls_filter = [c.strip() for c in
                          miss_cls_var.get().replace(",", " ").split() if c.strip()]
            out_dir = os.path.normpath(
                os.path.join(self._output_dir if self._output_dir else img_dir,
                             "missed_analysis"))
            miss_out_dir[0] = out_dir
            miss_run_btn.config(state=DISABLED)
            miss_open_btn.config(state=DISABLED)
            miss_pb["value"] = 0
            miss_status.config(text="Đang chạy…", fg=ACCENT)
            for iid in miss_tree.get_children():
                miss_tree.delete(iid)
            sum_lbl.config(text="")
            threading.Thread(
                target=self._run_miss_analysis,
                args=(model_path, img_dir, lbl_dir, out_dir, conf_v, iou_v,
                      max_save, cls_filter, miss_pb, miss_status, miss_tree,
                      sum_lbl, miss_run_btn, miss_open_btn),
                daemon=True).start()

        def _open_out():
            d = miss_out_dir[0]
            if d and os.path.isdir(d):
                subprocess.Popen(["explorer", os.path.normpath(d)])
            else:
                messagebox.showinfo("Chưa có kết quả", "Chạy phân tích trước.", parent=win)

        miss_run_btn.config(command=_do_run)
        miss_open_btn.config(command=_open_out)
        win.lift()
        win.focus_set()

    def _run_miss_analysis(self, model_path, img_dir, lbl_dir, out_dir,
                            conf, iou_thresh, max_save, cls_filter,
                            pb, status_lbl, tree, sum_lbl, run_btn, open_btn):
        """Thread: batch predict → tính FN per class → lưu ảnh → cập nhật UI."""
        def _ui(fn):
            self.root.after(0, fn)

        try:
            import cv2 as _cv2
            from ultralytics import YOLO as _YOLO
        except ImportError as exc:
            _ui(lambda e=str(exc): status_lbl.config(text=f"Lỗi import: {e}", fg="#f05050"))
            _ui(lambda: run_btn.config(state=NORMAL))
            return

        _ui(lambda: status_lbl.config(text="Đang load model…", fg=ACCENT))
        _ui(lambda: pb.config(value=5))

        try:
            model = _YOLO(model_path)
        except Exception as exc:
            _ui(lambda e=str(exc): status_lbl.config(text=f"Lỗi load model: {e}", fg="#f05050"))
            _ui(lambda: run_btn.config(state=NORMAL))
            return

        names = model.names  # {0: 'car', ...}
        target_ids = ([cid for cid, nm in names.items() if nm in cls_filter]
                      if cls_filter else list(names.keys()))
        if not target_ids:
            target_ids = list(names.keys())

        _EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
        img_paths = [p for p in Path(img_dir).iterdir()
                     if p.is_file() and p.suffix.lower() in _EXTS]
        target_imgs = []
        for ip in img_paths:
            lp = Path(lbl_dir) / (ip.stem + ".txt")
            if not lp.exists():
                continue
            try:
                with open(lp) as f:
                    classes = [int(l.split()[0]) for l in f if l.strip()]
            except Exception:
                continue
            if any(c in target_ids for c in classes):
                target_imgs.append(ip)

        total_imgs = len(target_imgs)
        _ui(lambda n=total_imgs: status_lbl.config(
            text=f"Tìm thấy {n} ảnh có target classes…", fg=DIM))

        if not target_imgs:
            _ui(lambda: status_lbl.config(text="Không có ảnh nào!", fg="#f0c040"))
            _ui(lambda: run_btn.config(state=NORMAL))
            return

        stats = {cid: {"name": names[cid], "total": 0, "missed": 0,
                       "sizes": [], "cases": []}
                 for cid in target_ids}

        def _iou(b1, b2):
            ix1 = max(b1[0], b2[0]); iy1 = max(b1[1], b2[1])
            ix2 = min(b1[2], b2[2]); iy2 = min(b1[3], b2[3])
            inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
            a1 = (b1[2]-b1[0])*(b1[3]-b1[1])
            a2 = (b2[2]-b2[0])*(b2[3]-b2[1])
            return inter / (a1 + a2 - inter + 1e-9)

        def _to_xyxy(cx, cy, w, h, W, H):
            return [int((cx-w/2)*W), int((cy-h/2)*H),
                    int((cx+w/2)*W), int((cy+h/2)*H)]

        import time as _time

        def _fmt_sec(s):
            s = int(s)
            return f"{s//3600}h{(s%3600)//60:02d}m" if s >= 3600 else f"{s//60}m{s%60:02d}s"

        t_start = _time.monotonic()
        BATCH = 32
        for i in range(0, total_imgs, BATCH):
            batch = target_imgs[i:i+BATCH]
            try:
                results = model(batch, conf=conf, verbose=False)
            except Exception as exc:
                _ui(lambda e=str(exc): status_lbl.config(text=f"Lỗi inference: {e}", fg="#f05050"))
                break

            for img_path, result in zip(batch, results):
                lp = Path(lbl_dir) / (img_path.stem + ".txt")
                img_tmp = _cv2.imread(str(img_path))
                if img_tmp is None:
                    continue
                H_img, W_img = img_tmp.shape[:2]
                gt = {cid: [] for cid in target_ids}
                try:
                    with open(lp) as f:
                        for line in f:
                            parts = line.strip().split()
                            if len(parts) < 5:
                                continue
                            cid = int(parts[0])
                            if cid in target_ids:
                                gt[cid].append(_to_xyxy(*map(float, parts[1:5]),
                                                        W_img, H_img))
                except Exception:
                    pass
                pred = {cid: [] for cid in target_ids}
                for box in result.boxes:
                    cid = int(box.cls)
                    if cid in target_ids:
                        pred[cid].append(box.xyxy[0].tolist())
                for cid in target_ids:
                    for g in gt[cid]:
                        stats[cid]["total"] += 1
                        if not any(_iou(g, p) >= iou_thresh for p in pred[cid]):
                            stats[cid]["missed"] += 1
                            x1, y1, x2, y2 = g
                            stats[cid]["sizes"].append(
                                (x2-x1)*(y2-y1)/(W_img*H_img)*100)
                            if len(stats[cid]["cases"]) < max_save:
                                stats[cid]["cases"].append(
                                    (str(img_path), g,
                                     {c: list(pred[c]) for c in target_ids}))

            pct  = min(100, int((i + BATCH) / total_imgs * 100))
            done = min(i + BATCH, total_imgs)
            elapsed = _time.monotonic() - t_start
            eta     = (elapsed / done * (total_imgs - done)) if done > 0 else 0
            _ui(lambda v=pct: pb.config(value=v))
            _ui(lambda d=done, el=elapsed, et=eta: status_lbl.config(
                text=f"Inference {d}/{total_imgs} ({d*100//total_imgs}%)"
                     f"  ⏱ {_fmt_sec(el)} / ETA {_fmt_sec(et)}",
                fg=DIM))

        # Save annotated images
        _ui(lambda: status_lbl.config(text="Đang lưu ảnh missed…", fg=DIM))
        import os as _os
        _os.makedirs(out_dir, exist_ok=True)
        COLORS = [(0, 165, 255), (0, 255, 0), (255, 165, 0),
                  (255, 0, 255), (0, 255, 255), (255, 255, 0)]
        for idx, cid in enumerate(target_ids):
            cls_name = stats[cid]["name"]
            cls_out  = _os.path.join(out_dir, cls_name + "_missed")
            _os.makedirs(cls_out, exist_ok=True)
            for img_path, gt_box, all_preds in stats[cid]["cases"]:
                img = _cv2.imread(img_path)
                if img is None:
                    continue
                x1, y1, x2, y2 = [int(v) for v in gt_box]
                _cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 255), 3)
                _cv2.putText(img, f"MISSED {cls_name}", (x1, max(y1-8, 16)),
                             _cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                for ci, (c, preds) in enumerate(all_preds.items()):
                    color = COLORS[ci % len(COLORS)]
                    for p in preds:
                        _cv2.rectangle(img,
                                       (int(p[0]), int(p[1])),
                                       (int(p[2]), int(p[3])), color, 2)
                _cv2.imwrite(_os.path.join(cls_out,
                                           Path(img_path).stem + "_miss.jpg"), img)

        def _refresh_tree():
            for iid in tree.get_children():
                tree.delete(iid)
            parts = []
            for cid in sorted(target_ids, key=lambda c: names[c]):
                s    = stats[cid]
                tot  = s["total"]
                miss = s["missed"]
                rate = (miss / tot * 100) if tot else 0.0
                szs  = s["sizes"]
                if szs:
                    tiny  = sum(1 for x in szs if x < 2)
                    small = sum(1 for x in szs if 2 <= x < 5)
                    med   = sum(1 for x in szs if 5 <= x < 15)
                    large = sum(1 for x in szs if x >= 15)
                    avg   = sum(szs) / len(szs)
                else:
                    tiny = small = med = large = 0
                    avg  = 0.0
                tag = "ok" if rate < 5 else ("warn" if rate < 20 else "bad")
                tree.insert("", END,
                            values=(s["name"], tot, miss, f"{rate:.1f}%",
                                    tiny, small, med, large, f"{avg:.1f}%"),
                            tags=(tag,))
                parts.append(f"{s['name']}: {miss}/{tot} ({rate:.1f}%)")
            elapsed_total = _time.monotonic() - t_start
            sum_lbl.config(
                text="  " + "   |   ".join(parts) if parts else "", fg=DIM)
            pb.config(value=100)
            status_lbl.config(
                text=f"✔  Hoàn tất trong {_fmt_sec(elapsed_total)} — ảnh lưu tại: {out_dir}",
                fg=SUCCESS)
            run_btn.config(state=NORMAL)
            open_btn.config(state=NORMAL)
            # Write summary JSON for HTML report
            try:
                summary_fn = _os.path.join(out_dir, "summary.json")
                _summary = {"classes": []}
                for cid in sorted(target_ids, key=lambda c: names[c]):
                    s = stats[cid]; szs = s["sizes"]; tot = s["total"]; miss = s["missed"]
                    _summary["classes"].append({
                        "name": s["name"], "total": tot, "missed": miss,
                        "miss_pct": round(miss/tot*100, 1) if tot else 0,
                        "tiny_pct": round(sum(1 for x in szs if x<2)/len(szs)*100,1) if szs else 0,
                    })
                with open(summary_fn, "w", encoding="utf-8") as _jf:
                    import json as _json; _json.dump(_summary, _jf, ensure_ascii=False, indent=2)
            except Exception:
                pass

        _ui(_refresh_tree)

    # ── False Positive Analysis ───────────────────────────────────────────────

    def _open_fp_analysis(self):
        """Cửa sổ phân tích False Positive (nhận nhầm) theo class."""
        if self._fp_win and self._fp_win.winfo_exists():
            self._fp_win.lift()
            return

        win = Toplevel(self.root)
        win.title("KZTEK – False Positive Analysis")
        win.geometry("900x720")
        win.configure(bg=BG)
        win.resizable(True, True)
        win.protocol("WM_DELETE_WINDOW", win.destroy)
        self._fp_win = win

        # ── Config ────────────────────────────────────────────────────
        cfg = Frame(win, bg=CARD, padx=12, pady=10)
        cfg.pack(fill=X, padx=8, pady=(8, 4))
        cfg.columnconfigure(1, weight=1)

        Label(cfg, text="Phân tích nhận nhầm (False Positive) — model dự đoán nhầm class nào",
              bg=CARD, fg=TEXT, font=F_BOLD).grid(
                  row=0, column=0, columnspan=3, sticky=W, pady=(0, 8))

        fp_model_var = StringVar()
        best_pt = os.path.join(self._output_dir, "weights", "best.pt") if self._output_dir else ""
        if best_pt and os.path.isfile(best_pt):
            fp_model_var.set(best_pt)

        fp_img_var = StringVar()
        fp_lbl_var = StringVar()

        def _pick_model():
            p = filedialog.askopenfilename(
                title="Chọn model .pt",
                filetypes=[("PyTorch model", "*.pt"), ("All", "*.*")],
                initialdir=str(Path(fp_model_var.get()).parent)
                           if fp_model_var.get() and os.path.isfile(fp_model_var.get()) else ".")
            if p:
                fp_model_var.set(p)

        def _pick_imgs():
            p = filedialog.askdirectory(title="Chọn thư mục val/images",
                                        initialdir=fp_img_var.get() or ".")
            if p:
                fp_img_var.set(p)
                cand = str(Path(p).parent / "labels")
                if os.path.isdir(cand):
                    fp_lbl_var.set(cand)

        def _pick_lbls():
            p = filedialog.askdirectory(title="Chọn thư mục val/labels",
                                        initialdir=fp_lbl_var.get() or fp_img_var.get() or ".")
            if p:
                fp_lbl_var.set(p)

        for row, (lbl_txt, var, cmd) in enumerate([
            ("Model (.pt):", fp_model_var, _pick_model),
            ("Val images:",  fp_img_var,   _pick_imgs),
            ("Val labels:",  fp_lbl_var,   _pick_lbls),
        ], start=1):
            Label(cfg, text=lbl_txt, bg=CARD, fg=DIM, font=F_MAIN,
                  width=14, anchor=W).grid(row=row, column=0, sticky=W, pady=3)
            Entry(cfg, textvariable=var, bg="#16162a", fg=TEXT,
                  insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4).grid(
                      row=row, column=1, sticky=EW, padx=(8, 4))
            Button(cfg, text="…", command=cmd,
                   bg=ACCENT2, fg="white", font=F_MAIN, relief="flat",
                   padx=8, cursor="hand2").grid(row=row, column=2)

        pr = Frame(cfg, bg=CARD)
        pr.grid(row=4, column=0, columnspan=3, sticky=W, pady=(8, 0))
        fp_conf_var    = StringVar(value="0.25")
        fp_iou_var     = StringVar(value="0.3")
        fp_bg_iou_var  = StringVar(value="0.1")
        fp_max_var     = StringVar(value="60")
        fp_cls_var     = StringVar(value=self._labels_var.get())

        for lbl_t, var, w, tip in [
            ("Conf:",        fp_conf_var,   5, "ngưỡng predict"),
            ("IoU match:",   fp_iou_var,    5, "≥ = TP"),
            ("IoU overlap:", fp_bg_iou_var, 5, "< = background FP"),
            ("Max save:",    fp_max_var,    5, "ảnh/class"),
        ]:
            Label(pr, text=lbl_t, bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
            Entry(pr, textvariable=var, bg="#16162a", fg=TEXT,
                  insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4,
                  width=w).pack(side=LEFT, padx=(4, 2))
            Label(pr, text=tip, bg=CARD, fg=DIM,
                  font=("Segoe UI", 7, "italic")).pack(side=LEFT, padx=(0, 10))

        pr2 = Frame(cfg, bg=CARD)
        pr2.grid(row=5, column=0, columnspan=3, sticky=W, pady=(4, 0))
        Label(pr2, text="Classes:", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        Entry(pr2, textvariable=fp_cls_var, bg="#16162a", fg=TEXT,
              insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4,
              width=40).pack(side=LEFT, padx=(4, 0))
        Label(pr2, text="  (để trống = tất cả)", bg=CARD, fg=DIM,
              font=("Segoe UI", 7, "italic")).pack(side=LEFT)

        # ── Controls ──────────────────────────────────────────────────
        ctrl_row = Frame(win, bg=BG, padx=8, pady=4)
        ctrl_row.pack(fill=X)
        fp_run_btn = Button(ctrl_row, text="▶  Chạy phân tích",
                            bg="#2e7d32", fg="white",
                            activebackground="#1b5e20", activeforeground="white",
                            font=F_BOLD, relief="flat", padx=16, cursor="hand2")
        fp_run_btn.pack(side=LEFT)
        fp_open_btn = Button(ctrl_row, text="📂  Mở thư mục",
                             bg=ACCENT2, fg="white",
                             activebackground=ACCENT, activeforeground="white",
                             font=F_MAIN, relief="flat", padx=12, cursor="hand2",
                             state=DISABLED)
        fp_open_btn.pack(side=LEFT, padx=(8, 0))
        fp_hn_btn = Button(ctrl_row, text="➕  Hard Negative",
                           bg="#5a3000", fg="white",
                           activebackground=ACCENT, activeforeground="white",
                           font=F_MAIN, relief="flat", padx=12, cursor="hand2",
                           state=DISABLED)
        fp_hn_btn.pack(side=LEFT, padx=(8, 0))
        fp_status = Label(ctrl_row, text="", bg=BG, fg=DIM, font=F_MAIN)
        fp_status.pack(side=LEFT, padx=12)

        pb_f = Frame(win, bg=BG, padx=8)
        pb_f.pack(fill=X)
        fp_pb = ttk.Progressbar(pb_f, maximum=100)
        fp_pb.pack(fill=X, pady=(2, 4))

        # ── Results: 2 bảng ──────────────────────────────────────────
        Label(win, text="Nhận nhầm theo class dự đoán",
              bg=BG, fg=TEXT, font=F_BOLD, padx=8, anchor=W).pack(fill=X)

        tbl1_f = Frame(win, bg=BG, padx=8)
        tbl1_f.pack(fill=BOTH, expand=True)
        cols1 = ("cls_pred", "total_pred", "fp_cnt", "fp_pct", "top_confusion")
        fp_tree1 = ttk.Treeview(tbl1_f, columns=cols1, show="headings",
                                 style="Dark.Treeview", height=6)
        for col, hdr, w, anc in [
            ("cls_pred",    "Class dự đoán",    140, W),
            ("total_pred",  "Tổng predict",       90, CENTER),
            ("fp_cnt",      "FP",                 60, CENTER),
            ("fp_pct",      "FP%",                70, CENTER),
            ("top_confusion","Nhầm từ GT class",  320, W),
        ]:
            fp_tree1.heading(col, text=hdr)
            fp_tree1.column(col, width=w, anchor=anc, stretch=(col == "top_confusion"))
        vsb1 = ttk.Scrollbar(tbl1_f, orient=VERTICAL,   command=fp_tree1.yview)
        hsb1 = ttk.Scrollbar(tbl1_f, orient=HORIZONTAL, command=fp_tree1.xview)
        fp_tree1.configure(yscrollcommand=vsb1.set, xscrollcommand=hsb1.set)
        vsb1.pack(side=RIGHT, fill=Y)
        hsb1.pack(side=BOTTOM, fill=X)
        fp_tree1.pack(fill=BOTH, expand=True)
        fp_tree1.tag_configure("ok",   foreground=SUCCESS)
        fp_tree1.tag_configure("warn", foreground="#f0c040")
        fp_tree1.tag_configure("bad",  foreground="#f05050")

        Label(win, text="Chi tiết nhầm: GT class nào bị dự đoán thành class khác",
              bg=BG, fg=TEXT, font=F_BOLD, padx=8, anchor=W).pack(fill=X, pady=(6, 0))

        tbl2_f = Frame(win, bg=BG, padx=8)
        tbl2_f.pack(fill=BOTH, expand=True)
        cols2 = ("gt_cls", "pred_cls", "count", "note")
        fp_tree2 = ttk.Treeview(tbl2_f, columns=cols2, show="headings",
                                  style="Dark.Treeview", height=5)
        for col, hdr, w, anc in [
            ("gt_cls",  "GT thực tế",      140, W),
            ("pred_cls","Dự đoán nhầm",    140, W),
            ("count",   "Số lần",           70, CENTER),
            ("note",    "Ghi chú",         260, W),
        ]:
            fp_tree2.heading(col, text=hdr)
            fp_tree2.column(col, width=w, anchor=anc, stretch=(col == "note"))
        vsb2 = ttk.Scrollbar(tbl2_f, orient=VERTICAL,   command=fp_tree2.yview)
        hsb2 = ttk.Scrollbar(tbl2_f, orient=HORIZONTAL, command=fp_tree2.xview)
        fp_tree2.configure(yscrollcommand=vsb2.set, xscrollcommand=hsb2.set)
        vsb2.pack(side=RIGHT, fill=Y)
        hsb2.pack(side=BOTTOM, fill=X)
        fp_tree2.pack(fill=BOTH, expand=True)
        fp_tree2.tag_configure("high", foreground="#f05050")
        fp_tree2.tag_configure("med",  foreground="#f0c040")

        sum_lbl = Label(win, text="", bg=BG, fg=DIM,
                        font=("Consolas", 9), anchor=W, padx=8)
        sum_lbl.pack(fill=X, pady=(2, 6))

        fp_out_dir   = [None]
        fp_cases_ref = [[]]   # list of original image paths that had FP

        def _do_run():
            model_path = fp_model_var.get().strip()
            img_dir    = fp_img_var.get().strip()
            lbl_dir    = fp_lbl_var.get().strip()
            if not model_path or not os.path.isfile(model_path):
                messagebox.showwarning("Thiếu model", "Chọn file model .pt hợp lệ.", parent=win)
                return
            if not img_dir or not os.path.isdir(img_dir):
                messagebox.showwarning("Thiếu val images", "Chọn thư mục val/images.", parent=win)
                return
            if not lbl_dir:
                lbl_dir = str(Path(img_dir).parent / "labels")
            if not os.path.isdir(lbl_dir):
                messagebox.showwarning("Thiếu labels",
                                       f"Không tìm thấy thư mục labels:\n{lbl_dir}", parent=win)
                return
            try:
                conf_v    = float(fp_conf_var.get())
                iou_v     = float(fp_iou_var.get())
                bg_iou_v  = float(fp_bg_iou_var.get())
                max_save  = int(fp_max_var.get())
            except ValueError:
                conf_v, iou_v, bg_iou_v, max_save = 0.25, 0.3, 0.1, 60
            cls_filter = [c.strip() for c in
                          fp_cls_var.get().replace(",", " ").split() if c.strip()]
            out_dir = os.path.normpath(
                os.path.join(self._output_dir if self._output_dir else img_dir,
                             "fp_analysis"))
            fp_out_dir[0] = out_dir
            fp_run_btn.config(state=DISABLED)
            fp_open_btn.config(state=DISABLED)
            fp_hn_btn.config(state=DISABLED)
            fp_cases_ref[0] = []
            fp_pb["value"] = 0
            fp_status.config(text="Đang chạy…", fg=ACCENT)
            for t in (fp_tree1, fp_tree2):
                for iid in t.get_children():
                    t.delete(iid)
            sum_lbl.config(text="")
            threading.Thread(
                target=self._run_fp_analysis,
                args=(model_path, img_dir, lbl_dir, out_dir, conf_v, iou_v,
                      bg_iou_v, max_save, cls_filter, fp_pb, fp_status,
                      fp_tree1, fp_tree2, sum_lbl, fp_run_btn, fp_open_btn,
                      fp_cases_ref, fp_hn_btn),
                daemon=True).start()

        def _open_out():
            d = fp_out_dir[0]
            if d and os.path.isdir(d):
                subprocess.Popen(["explorer", os.path.normpath(d)])
            else:
                messagebox.showinfo("Chưa có kết quả", "Chạy phân tích trước.", parent=win)

        def _do_add_hn():
            paths = fp_cases_ref[0]
            if not paths:
                messagebox.showinfo("Chưa có dữ liệu", "Chạy FP Analysis trước.", parent=win)
                return
            dest = filedialog.askdirectory(
                title="Chọn thư mục train để thêm Hard Negative",
                initialdir=self.train_dir.get().strip() or ".")
            if not dest:
                return
            img_out = Path(dest) / "images"
            lbl_out = Path(dest) / "labels"
            img_out.mkdir(parents=True, exist_ok=True)
            lbl_out.mkdir(parents=True, exist_ok=True)
            copied = skipped = 0
            for src in paths:
                src_p = Path(src)
                dst_img = img_out / src_p.name
                dst_lbl = lbl_out / (src_p.stem + ".txt")
                if dst_img.exists():
                    skipped += 1
                    continue
                try:
                    shutil.copy2(src_p, dst_img)
                    dst_lbl.write_text("")   # file rỗng → background
                    copied += 1
                except Exception:
                    skipped += 1
            messagebox.showinfo(
                "Hoàn tất",
                f"Đã thêm {copied} ảnh Hard Negative vào:\n{dest}\n\n"
                f"(bỏ qua {skipped} ảnh đã tồn tại)\n\n"
                f"Retrain để model học không nhận nhầm các vật thể này.",
                parent=win)

        fp_run_btn.config(command=_do_run)
        fp_open_btn.config(command=_open_out)
        fp_hn_btn.config(command=_do_add_hn)
        win.lift()
        win.focus_set()

    def _run_fp_analysis(self, model_path, img_dir, lbl_dir, out_dir,
                         conf, iou_thresh, bg_iou_thresh, max_save, cls_filter,
                         pb, status_lbl, tree1, tree2, sum_lbl, run_btn, open_btn,
                         fp_cases_ref=None, fp_hn_btn=None):
        """Thread: batch predict → phân tích FP per class → confusion matrix → lưu ảnh."""
        def _ui(fn):
            self.root.after(0, fn)

        try:
            import cv2 as _cv2
            from ultralytics import YOLO as _YOLO
        except ImportError as exc:
            _ui(lambda e=str(exc): status_lbl.config(text=f"Lỗi import: {e}", fg="#f05050"))
            _ui(lambda: run_btn.config(state=NORMAL))
            return

        _ui(lambda: status_lbl.config(text="Đang load model…", fg=ACCENT))
        _ui(lambda: pb.config(value=5))

        try:
            model = _YOLO(model_path)
        except Exception as exc:
            _ui(lambda e=str(exc): status_lbl.config(text=f"Lỗi load model: {e}", fg="#f05050"))
            _ui(lambda: run_btn.config(state=NORMAL))
            return

        names = model.names  # {0: 'car', ...}
        all_ids = list(names.keys())
        target_ids = ([cid for cid, nm in names.items() if nm in cls_filter]
                      if cls_filter else all_ids)
        if not target_ids:
            target_ids = all_ids

        _EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
        img_paths = sorted(p for p in Path(img_dir).iterdir()
                           if p.is_file() and p.suffix.lower() in _EXTS)

        total_imgs = len(img_paths)
        if not total_imgs:
            _ui(lambda: status_lbl.config(text="Không tìm thấy ảnh!", fg="#f0c040"))
            _ui(lambda: run_btn.config(state=NORMAL))
            return

        _ui(lambda n=total_imgs: status_lbl.config(
            text=f"Tìm thấy {n} ảnh…", fg=DIM))

        # fp_stats[pred_cid] = {"total": int, "fp": int, "confusion": {gt_cid: count}, "cases": [...]}
        fp_stats = {cid: {"name": names[cid], "total": 0, "fp": 0,
                          "confusion": {}, "cases": []}
                    for cid in target_ids}

        def _iou(b1, b2):
            ix1 = max(b1[0], b2[0]); iy1 = max(b1[1], b2[1])
            ix2 = min(b1[2], b2[2]); iy2 = min(b1[3], b2[3])
            inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
            a1 = (b1[2]-b1[0])*(b1[3]-b1[1])
            a2 = (b2[2]-b2[0])*(b2[3]-b2[1])
            return inter / (a1 + a2 - inter + 1e-9)

        def _to_xyxy(cx, cy, w, h, W, H):
            return [int((cx-w/2)*W), int((cy-h/2)*H),
                    int((cx+w/2)*W), int((cy+h/2)*H)]

        import time as _time
        def _fmt_sec(s):
            s = int(s)
            return f"{s//3600}h{(s%3600)//60:02d}m" if s >= 3600 else f"{s//60}m{s%60:02d}s"

        t_start = _time.monotonic()
        BATCH = 32
        for i in range(0, total_imgs, BATCH):
            batch = img_paths[i:i+BATCH]
            try:
                results = model(batch, conf=conf, verbose=False)
            except Exception as exc:
                _ui(lambda e=str(exc): status_lbl.config(text=f"Lỗi inference: {e}", fg="#f05050"))
                break

            for img_path, result in zip(batch, results):
                lp = Path(lbl_dir) / (img_path.stem + ".txt")
                img_tmp = _cv2.imread(str(img_path))
                if img_tmp is None:
                    continue
                H_img, W_img = img_tmp.shape[:2]

                # Load all GT boxes per class
                gt_all = {cid: [] for cid in all_ids}
                if lp.exists():
                    try:
                        with open(lp) as f:
                            for line in f:
                                parts = line.strip().split()
                                if len(parts) < 5:
                                    continue
                                cid = int(parts[0])
                                if cid in gt_all:
                                    gt_all[cid].append(
                                        _to_xyxy(*map(float, parts[1:5]), W_img, H_img))
                    except Exception:
                        pass

                # Evaluate each prediction
                for box in result.boxes:
                    pred_cid = int(box.cls)
                    if pred_cid not in target_ids:
                        continue
                    fp_stats[pred_cid]["total"] += 1
                    pb_box = box.xyxy[0].tolist()

                    # Check if this prediction matches any GT of the same class
                    matched = any(_iou(pb_box, g) >= iou_thresh
                                  for g in gt_all.get(pred_cid, []))
                    if matched:
                        continue

                    # It's a False Positive — find what GT class it overlaps with
                    fp_stats[pred_cid]["fp"] += 1
                    best_gt_cid = None
                    best_iou_val = bg_iou_thresh
                    for gt_cid, gt_boxes in gt_all.items():
                        if gt_cid == pred_cid:
                            continue
                        for g in gt_boxes:
                            ov = _iou(pb_box, g)
                            if ov > best_iou_val:
                                best_iou_val = ov
                                best_gt_cid  = gt_cid

                    if best_gt_cid is not None:
                        conf_dict = fp_stats[pred_cid]["confusion"]
                        conf_dict[best_gt_cid] = conf_dict.get(best_gt_cid, 0) + 1

                    if len(fp_stats[pred_cid]["cases"]) < max_save:
                        fp_stats[pred_cid]["cases"].append(
                            (str(img_path), pb_box, best_gt_cid,
                             {c: list(gt_all[c]) for c in gt_all}))

            pct  = min(100, int((i + BATCH) / total_imgs * 100))
            done = min(i + BATCH, total_imgs)
            elapsed = _time.monotonic() - t_start
            eta     = (elapsed / done * (total_imgs - done)) if done > 0 else 0
            _ui(lambda v=pct: pb.config(value=v))
            _ui(lambda d=done, el=elapsed, et=eta: status_lbl.config(
                text=f"Inference {d}/{total_imgs} ({d*100//total_imgs}%)"
                     f"  ⏱ {_fmt_sec(el)} / ETA {_fmt_sec(et)}",
                fg=DIM))

        # Save annotated FP images
        _ui(lambda: status_lbl.config(text="Đang lưu ảnh FP…", fg=DIM))
        import os as _os
        _os.makedirs(out_dir, exist_ok=True)
        for pred_cid in target_ids:
            s = fp_stats[pred_cid]
            if not s["cases"]:
                continue
            cls_out = _os.path.join(out_dir, f"{s['name']}_fp")
            _os.makedirs(cls_out, exist_ok=True)
            for img_path, fp_box, gt_cid, gt_all_saved in s["cases"]:
                img = _cv2.imread(img_path)
                if img is None:
                    continue
                # Draw FP box in red
                x1, y1, x2, y2 = [int(v) for v in fp_box]
                _cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 255), 3)
                label = f"FP:{s['name']}"
                if gt_cid is not None:
                    label += f" (GT:{names.get(gt_cid, str(gt_cid))})"
                _cv2.putText(img, label, (x1, max(y1-8, 16)),
                             _cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                # Draw GT boxes in green
                if gt_cid is not None:
                    for g in gt_all_saved.get(gt_cid, []):
                        gx1, gy1, gx2, gy2 = [int(v) for v in g]
                        _cv2.rectangle(img, (gx1, gy1), (gx2, gy2), (0, 255, 0), 2)
                        _cv2.putText(img, f"GT:{names.get(gt_cid, str(gt_cid))}",
                                     (gx1, max(gy1-6, 14)),
                                     _cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                out_name = _os.path.join(cls_out, Path(img_path).stem + "_fp.jpg")
                _cv2.imwrite(out_name, img)

        # Build confusion matrix pairs
        confusion_pairs = []
        for pred_cid, s in fp_stats.items():
            for gt_cid, cnt in s["confusion"].items():
                confusion_pairs.append((names.get(gt_cid, str(gt_cid)),
                                        s["name"], cnt))
        confusion_pairs.sort(key=lambda x: -x[2])

        def _refresh_tables():
            for t in (tree1, tree2):
                for iid in t.get_children():
                    t.delete(iid)

            summary_parts = []
            for pred_cid in sorted(target_ids, key=lambda c: names[c]):
                s    = fp_stats[pred_cid]
                tot  = s["total"]
                fp_c = s["fp"]
                rate = (fp_c / tot * 100) if tot else 0.0
                if not s["confusion"]:
                    top_str = "background (không có GT overlap)"
                else:
                    top_items = sorted(s["confusion"].items(), key=lambda x: -x[1])[:3]
                    top_str   = "  |  ".join(
                        f"{names.get(gc,'?')}→{s['name']} × {cnt}"
                        for gc, cnt in top_items)
                tag = "ok" if rate < 10 else ("warn" if rate < 30 else "bad")
                tree1.insert("", END,
                             values=(s["name"], tot, fp_c, f"{rate:.1f}%", top_str),
                             tags=(tag,))
                if fp_c > 0:
                    summary_parts.append(f"{s['name']}: {fp_c} FP ({rate:.1f}%)")

            for gt_nm, pred_nm, cnt in confusion_pairs:
                tag = "high" if cnt >= 5 else "med"
                note = f"GT '{gt_nm}' bị nhận nhầm thành '{pred_nm}' {cnt} lần"
                tree2.insert("", END,
                             values=(gt_nm, pred_nm, cnt, note),
                             tags=(tag,))

            # Collect unique original image paths for hard negative export
            unique_fp_paths = list({
                case[0]
                for s in fp_stats.values()
                for case in s["cases"]
            })
            if fp_cases_ref is not None:
                fp_cases_ref[0] = unique_fp_paths

            elapsed_total = _time.monotonic() - t_start
            sum_lbl.config(
                text="  " + "   |   ".join(summary_parts) if summary_parts
                else "  Không có FP nào!", fg=DIM)
            pb.config(value=100)
            status_lbl.config(
                text=f"✔  Hoàn tất trong {_fmt_sec(elapsed_total)} — ảnh lưu tại: {out_dir}",
                fg=SUCCESS)
            run_btn.config(state=NORMAL)
            open_btn.config(state=NORMAL)
            if fp_hn_btn is not None and unique_fp_paths:
                fp_hn_btn.config(state=NORMAL)
            # Write summary JSON for HTML report
            try:
                import json as _json; import os as _os2
                _os2.makedirs(out_dir, exist_ok=True)
                _fp_summary = {
                    "classes": [
                        {"name": fp_stats[c]["name"],
                         "total": fp_stats[c]["total"],
                         "fp": fp_stats[c]["fp"],
                         "fp_pct": round(fp_stats[c]["fp"]/fp_stats[c]["total"]*100, 1)
                                   if fp_stats[c]["total"] else 0,
                         "confusion": [
                             {"gt": names.get(gc,"?"), "count": cnt}
                             for gc, cnt in sorted(fp_stats[c]["confusion"].items(),
                                                   key=lambda x: -x[1])[:5]
                         ]}
                        for c in target_ids
                    ],
                    "confusion_pairs": [
                        {"gt": gt_nm, "pred": pred_nm, "count": cnt}
                        for gt_nm, pred_nm, cnt in confusion_pairs[:20]
                    ],
                }
                with open(_os2.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as _jf:
                    _json.dump(_fp_summary, _jf, ensure_ascii=False, indent=2)
            except Exception:
                pass

        _ui(_refresh_tables)

    # ── Class Imbalance Analysis ──────────────────────────────────────────────

    def _open_imbalance_analysis(self):
        if self._imbalance_win and self._imbalance_win.winfo_exists():
            self._imbalance_win.lift(); return
        win = Toplevel(self.root)
        win.title("KZTEK – Class Imbalance Analysis")
        win.geometry("720x560")
        win.configure(bg=BG)
        win.resizable(True, True)
        win.protocol("WM_DELETE_WINDOW", win.destroy)
        self._imbalance_win = win

        cfg = Frame(win, bg=CARD, padx=12, pady=10)
        cfg.pack(fill=X, padx=8, pady=(8, 4))
        cfg.columnconfigure(1, weight=1)
        Label(cfg, text="Phân tích mất cân bằng số lượng mẫu giữa các class",
              bg=CARD, fg=TEXT, font=F_BOLD).grid(row=0, column=0, columnspan=3, sticky=W, pady=(0,8))

        imb_dir_var = StringVar(value=self.train_dir.get().strip())
        Label(cfg, text="Thư mục labels:", bg=CARD, fg=DIM, font=F_MAIN,
              width=16, anchor=W).grid(row=1, column=0, sticky=W, pady=3)
        Entry(cfg, textvariable=imb_dir_var, bg="#16162a", fg=TEXT,
              insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4).grid(
                  row=1, column=1, sticky=EW, padx=(8,4))
        def _pick():
            p = filedialog.askdirectory(initialdir=imb_dir_var.get() or ".")
            if p: imb_dir_var.set(p)
        Button(cfg, text="…", command=_pick,
               bg=ACCENT2, fg="white", font=F_MAIN, relief="flat",
               padx=8, cursor="hand2").grid(row=1, column=2)

        imb_cls_var = StringVar(value=self._labels_var.get())
        Label(cfg, text="Classes:", bg=CARD, fg=DIM, font=F_MAIN,
              width=16, anchor=W).grid(row=2, column=0, sticky=W, pady=3)
        Entry(cfg, textvariable=imb_cls_var, bg="#16162a", fg=TEXT,
              insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4).grid(
                  row=2, column=1, columnspan=2, sticky=EW, padx=(8,0))
        Label(cfg, text="(thứ tự khớp class_id: 0,1,2...)",
              bg=CARD, fg=DIM, font=("Segoe UI",7,"italic")).grid(row=3, column=1, sticky=W, padx=(8,0))

        ctrl_r = Frame(win, bg=BG, padx=8, pady=4)
        ctrl_r.pack(fill=X)
        imb_run_btn = Button(ctrl_r, text="▶  Quét", bg="#2e7d32", fg="white",
                              activebackground="#1b5e20", activeforeground="white",
                              font=F_BOLD, relief="flat", padx=16, cursor="hand2")
        imb_run_btn.pack(side=LEFT)
        imb_status = Label(ctrl_r, text="", bg=BG, fg=DIM, font=F_MAIN)
        imb_status.pack(side=LEFT, padx=12)
        imb_pb = ttk.Progressbar(win, maximum=100)
        imb_pb.pack(fill=X, padx=8, pady=(0,4))

        tbl_f = Frame(win, bg=BG, padx=8)
        tbl_f.pack(fill=BOTH, expand=True)
        cols = ("cls","count","pct","bar","status")
        imb_tree = ttk.Treeview(tbl_f, columns=cols, show="headings",
                                  style="Dark.Treeview", height=14)
        for col, hdr, w, anc in [
            ("cls",    "Class",         140, W),
            ("count",  "Số instance",    90, CENTER),
            ("pct",    "%",              70, CENTER),
            ("bar",    "Biểu đồ",       260, W),
            ("status", "Đánh giá",      120, CENTER),
        ]:
            imb_tree.heading(col, text=hdr)
            imb_tree.column(col, width=w, anchor=anc, stretch=(col=="bar"))
        vsb = ttk.Scrollbar(tbl_f, orient=VERTICAL, command=imb_tree.yview)
        vsb.pack(side=RIGHT, fill=Y)
        imb_tree.pack(fill=BOTH, expand=True)
        imb_tree.configure(yscrollcommand=vsb.set)
        imb_tree.tag_configure("ok",   foreground=SUCCESS)
        imb_tree.tag_configure("warn", foreground="#f0c040")
        imb_tree.tag_configure("bad",  foreground="#f05050")
        sum_lbl = Label(win, text="", bg=BG, fg=DIM, font=("Consolas",9), anchor=W, padx=8)
        sum_lbl.pack(fill=X, pady=(2,6))

        def _do_run():
            lbl_dir = imb_dir_var.get().strip()
            if not lbl_dir or not os.path.isdir(lbl_dir):
                messagebox.showwarning("Thiếu thư mục", "Chọn thư mục chứa file .txt labels.", parent=win)
                return
            cls_names = [c.strip() for c in imb_cls_var.get().replace(","," ").split() if c.strip()]
            imb_run_btn.config(state=DISABLED)
            imb_pb["value"] = 0
            imb_status.config(text="Đang quét…", fg=ACCENT)
            for iid in imb_tree.get_children(): imb_tree.delete(iid)
            sum_lbl.config(text="")
            threading.Thread(target=self._run_imbalance_analysis,
                             args=(lbl_dir, cls_names, imb_pb, imb_status,
                                   imb_tree, sum_lbl, imb_run_btn),
                             daemon=True).start()
        imb_run_btn.config(command=_do_run)
        win.lift(); win.focus_set()

    def _run_imbalance_analysis(self, lbl_dir, cls_names, pb, status_lbl, tree, sum_lbl, run_btn):
        def _ui(fn): self.root.after(0, fn)
        _ui(lambda: pb.config(value=5))

        txt_files = [p for p in Path(lbl_dir).rglob("*.txt")]
        total = len(txt_files)
        if not total:
            _ui(lambda: status_lbl.config(text="Không tìm thấy file .txt!", fg="#f0c040"))
            _ui(lambda: run_btn.config(state=NORMAL))
            return

        counts = {}
        for i, fp in enumerate(txt_files):
            try:
                with open(fp) as f:
                    for line in f:
                        parts = line.strip().split()
                        if parts:
                            cid = int(parts[0])
                            counts[cid] = counts.get(cid, 0) + 1
            except Exception:
                pass
            if i % 200 == 0:
                pct = int(i / total * 90)
                _ui(lambda v=pct: pb.config(value=v))

        grand_total = sum(counts.values()) or 1
        max_count   = max(counts.values()) if counts else 1
        sorted_ids  = sorted(counts.keys())

        summary = {"lbl_dir": lbl_dir, "cls_names": cls_names, "counts": {}}

        def _refresh():
            for iid in tree.get_children(): tree.delete(iid)
            for cid in sorted_ids:
                cnt   = counts[cid]
                name  = cls_names[cid] if cid < len(cls_names) else f"class_{cid}"
                pct   = cnt / grand_total * 100
                ratio = cnt / max_count
                bar   = "█" * int(ratio * 30)
                if ratio >= 0.5:  tag, st = "ok",   "Cân bằng"
                elif ratio >= 0.2: tag, st = "warn", "Thiếu mẫu"
                else:              tag, st = "bad",  "⚠ Rất ít"
                tree.insert("", END, values=(name, cnt, f"{pct:.1f}%", bar, st), tags=(tag,))
                summary["counts"][name] = cnt
            pb.config(value=100)
            status_lbl.config(text=f"✔  Quét xong {total} file — {len(sorted_ids)} class", fg=SUCCESS)
            run_btn.config(state=NORMAL)
            parts = [f"{cls_names[c] if c<len(cls_names) else f'class_{c}'}: {counts[c]}"
                     for c in sorted_ids]
            sum_lbl.config(text="  " + "  |  ".join(parts), fg=DIM)
            # Write summary JSON for HTML report
            try:
                out = Path(lbl_dir).parent / "imbalance_summary.json"
                with open(out, "w", encoding="utf-8") as jf:
                    json.dump(summary, jf, ensure_ascii=False, indent=2)
            except Exception:
                pass
        _ui(_refresh)

    # ── Size & Shape Analysis ─────────────────────────────────────────────────

    def _open_shape_analysis(self):
        if self._shape_win and self._shape_win.winfo_exists():
            self._shape_win.lift(); return
        win = Toplevel(self.root)
        win.title("KZTEK – Size & Shape Analysis")
        win.geometry("780x600")
        win.configure(bg=BG)
        win.resizable(True, True)
        win.protocol("WM_DELETE_WINDOW", win.destroy)
        self._shape_win = win

        cfg = Frame(win, bg=CARD, padx=12, pady=10)
        cfg.pack(fill=X, padx=8, pady=(8,4))
        cfg.columnconfigure(1, weight=1)
        Label(cfg, text="Phân tích kích thước & tỉ lệ bbox — phát hiện object nhỏ, tỉ lệ bất thường",
              bg=CARD, fg=TEXT, font=F_BOLD).grid(row=0, column=0, columnspan=3, sticky=W, pady=(0,8))

        sh_dir_var = StringVar(value=self.train_dir.get().strip())
        Label(cfg, text="Thư mục labels:", bg=CARD, fg=DIM, font=F_MAIN,
              width=16, anchor=W).grid(row=1, column=0, sticky=W, pady=3)
        Entry(cfg, textvariable=sh_dir_var, bg="#16162a", fg=TEXT,
              insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4).grid(
                  row=1, column=1, sticky=EW, padx=(8,4))
        def _pick():
            p = filedialog.askdirectory(initialdir=sh_dir_var.get() or ".")
            if p: sh_dir_var.set(p)
        Button(cfg, text="…", command=_pick,
               bg=ACCENT2, fg="white", font=F_MAIN, relief="flat",
               padx=8, cursor="hand2").grid(row=1, column=2)

        sh_cls_var = StringVar(value=self._labels_var.get())
        Label(cfg, text="Classes:", bg=CARD, fg=DIM, font=F_MAIN,
              width=16, anchor=W).grid(row=2, column=0, sticky=W, pady=3)
        Entry(cfg, textvariable=sh_cls_var, bg="#16162a", fg=TEXT,
              insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4).grid(
                  row=2, column=1, columnspan=2, sticky=EW, padx=(8,0))

        ctrl_r = Frame(win, bg=BG, padx=8, pady=4)
        ctrl_r.pack(fill=X)
        sh_run_btn = Button(ctrl_r, text="▶  Quét", bg="#2e7d32", fg="white",
                             activebackground="#1b5e20", activeforeground="white",
                             font=F_BOLD, relief="flat", padx=16, cursor="hand2")
        sh_run_btn.pack(side=LEFT)
        sh_status = Label(ctrl_r, text="", bg=BG, fg=DIM, font=F_MAIN)
        sh_status.pack(side=LEFT, padx=12)
        sh_pb = ttk.Progressbar(win, maximum=100)
        sh_pb.pack(fill=X, padx=8, pady=(0,4))

        Label(win, text="Phân bố kích thước & tỉ lệ per class",
              bg=BG, fg=TEXT, font=F_BOLD, padx=8, anchor=W).pack(fill=X)
        tbl_f = Frame(win, bg=BG, padx=8)
        tbl_f.pack(fill=BOTH, expand=True)
        cols = ("cls","total","tiny","small","med","large","wide","tall","sq","warn")
        sh_tree = ttk.Treeview(tbl_f, columns=cols, show="headings",
                                style="Dark.Treeview", height=12)
        for col, hdr, w, anc in [
            ("cls",   "Class",      120, W),
            ("total", "Tổng",        55, CENTER),
            ("tiny",  "Tiny<2%",     65, CENTER),
            ("small", "Sm 2-5%",     65, CENTER),
            ("med",   "Med 5-15%",   65, CENTER),
            ("large", "Lg>15%",      65, CENTER),
            ("wide",  "Rộng>2:1",    70, CENTER),
            ("tall",  "Cao>2:1",     70, CENTER),
            ("sq",    "Vuông",       65, CENTER),
            ("warn",  "Cảnh báo",   160, W),
        ]:
            sh_tree.heading(col, text=hdr)
            sh_tree.column(col, width=w, anchor=anc, stretch=(col=="warn"))
        vsb = ttk.Scrollbar(tbl_f, orient=VERTICAL, command=sh_tree.yview)
        hsb = ttk.Scrollbar(tbl_f, orient=HORIZONTAL, command=sh_tree.xview)
        sh_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side=RIGHT, fill=Y)
        hsb.pack(side=BOTTOM, fill=X)
        sh_tree.pack(fill=BOTH, expand=True)
        sh_tree.tag_configure("ok",   foreground=SUCCESS)
        sh_tree.tag_configure("warn", foreground="#f0c040")
        sh_tree.tag_configure("bad",  foreground="#f05050")
        sum_lbl = Label(win, text="", bg=BG, fg=DIM, font=("Consolas",9), anchor=W, padx=8)
        sum_lbl.pack(fill=X, pady=(2,6))

        def _do_run():
            lbl_dir = sh_dir_var.get().strip()
            if not lbl_dir or not os.path.isdir(lbl_dir):
                messagebox.showwarning("Thiếu thư mục", "Chọn thư mục labels.", parent=win)
                return
            cls_names = [c.strip() for c in sh_cls_var.get().replace(","," ").split() if c.strip()]
            sh_run_btn.config(state=DISABLED)
            sh_pb["value"] = 0
            sh_status.config(text="Đang quét…", fg=ACCENT)
            for iid in sh_tree.get_children(): sh_tree.delete(iid)
            sum_lbl.config(text="")
            threading.Thread(target=self._run_shape_analysis,
                             args=(lbl_dir, cls_names, sh_pb, sh_status,
                                   sh_tree, sum_lbl, sh_run_btn),
                             daemon=True).start()
        sh_run_btn.config(command=_do_run)
        win.lift(); win.focus_set()

    def _run_shape_analysis(self, lbl_dir, cls_names, pb, status_lbl, tree, sum_lbl, run_btn):
        def _ui(fn): self.root.after(0, fn)
        txt_files = [p for p in Path(lbl_dir).rglob("*.txt")]
        total = len(txt_files)
        if not total:
            _ui(lambda: status_lbl.config(text="Không tìm thấy file .txt!", fg="#f0c040"))
            _ui(lambda: run_btn.config(state=NORMAL))
            return

        # per_class[cid] = {"areas":[], "ratios":[]}
        per_class = {}
        for i, fp in enumerate(txt_files):
            try:
                with open(fp) as f:
                    for line in f:
                        parts = line.strip().split()
                        if len(parts) < 5: continue
                        cid = int(parts[0])
                        w, h = float(parts[3]), float(parts[4])
                        area = w * h * 100  # percent of image
                        ratio = w / h if h > 0 else 1.0
                        if cid not in per_class:
                            per_class[cid] = {"areas": [], "ratios": []}
                        per_class[cid]["areas"].append(area)
                        per_class[cid]["ratios"].append(ratio)
            except Exception:
                pass
            if i % 200 == 0:
                _ui(lambda v=int(i/total*90): pb.config(value=v))

        summary = {"lbl_dir": lbl_dir, "cls_names": cls_names, "shape": {}}

        def _refresh():
            for iid in tree.get_children(): tree.delete(iid)
            warnings_list = []
            for cid in sorted(per_class.keys()):
                name   = cls_names[cid] if cid < len(cls_names) else f"class_{cid}"
                areas  = per_class[cid]["areas"]
                ratios = per_class[cid]["ratios"]
                n      = len(areas)
                tiny   = sum(1 for a in areas if a < 2)
                small  = sum(1 for a in areas if 2 <= a < 5)
                med    = sum(1 for a in areas if 5 <= a < 15)
                large  = sum(1 for a in areas if a >= 15)
                wide   = sum(1 for r in ratios if r > 2.0)
                tall   = sum(1 for r in ratios if r < 0.5)
                sq     = n - wide - tall
                warns  = []
                if tiny / n > 0.4:  warns.append(f"⚠ {tiny/n*100:.0f}% tiny → tăng imgsz")
                if wide / n > 0.5:  warns.append(f"⚠ bbox rất rộng ({wide/n*100:.0f}%)")
                if tall / n > 0.5:  warns.append(f"⚠ bbox rất cao ({tall/n*100:.0f}%)")
                tag = "bad" if warns else ("warn" if tiny/n > 0.2 else "ok")
                warn_str = "  ".join(warns) if warns else "OK"
                tree.insert("", END,
                            values=(name, n,
                                    f"{tiny/n*100:.0f}%", f"{small/n*100:.0f}%",
                                    f"{med/n*100:.0f}%",  f"{large/n*100:.0f}%",
                                    f"{wide/n*100:.0f}%", f"{tall/n*100:.0f}%",
                                    f"{sq/n*100:.0f}%",   warn_str),
                            tags=(tag,))
                if warns: warnings_list.append(f"{name}: {', '.join(warns)}")
                summary["shape"][name] = {
                    "total": n, "tiny_pct": round(tiny/n*100,1),
                    "wide_pct": round(wide/n*100,1), "tall_pct": round(tall/n*100,1),
                }
            pb.config(value=100)
            status_lbl.config(text=f"✔  Quét xong {total} file", fg=SUCCESS)
            run_btn.config(state=NORMAL)
            sum_lbl.config(
                text="  " + "  |  ".join(warnings_list) if warnings_list else "  Không có cảnh báo đặc biệt",
                fg="#f0c040" if warnings_list else SUCCESS)
            try:
                out = Path(lbl_dir).parent / "shape_summary.json"
                with open(out, "w", encoding="utf-8") as jf:
                    json.dump(summary, jf, ensure_ascii=False, indent=2)
            except Exception:
                pass
        _ui(_refresh)

    # ── Brightness Analysis ───────────────────────────────────────────────────

    def _open_brightness_analysis(self):
        if self._brightness_win and self._brightness_win.winfo_exists():
            self._brightness_win.lift(); return
        win = Toplevel(self.root)
        win.title("KZTEK – Brightness Analysis")
        win.geometry("820x620")
        win.configure(bg=BG)
        win.resizable(True, True)
        win.protocol("WM_DELETE_WINDOW", win.destroy)
        self._brightness_win = win

        cfg = Frame(win, bg=CARD, padx=12, pady=10)
        cfg.pack(fill=X, padx=8, pady=(8, 4))
        cfg.columnconfigure(1, weight=1)
        Label(cfg,
              text="Phân tích độ sáng ảnh — phát hiện thiếu data tối/sáng/ngược sáng",
              bg=CARD, fg=TEXT, font=F_BOLD).grid(
                  row=0, column=0, columnspan=3, sticky=W, pady=(0, 8))

        br_img_var = StringVar(value=self.train_dir.get().strip())
        br_lbl_var = StringVar()
        br_cls_var = StringVar(value=self._labels_var.get())

        for row, (lbl_txt, var, title) in enumerate([
            ("Thư mục images:", br_img_var, "Chọn thư mục images"),
            ("Thư mục labels:", br_lbl_var, "Chọn thư mục labels (tuỳ chọn)"),
        ], start=1):
            Label(cfg, text=lbl_txt, bg=CARD, fg=DIM, font=F_MAIN,
                  width=18, anchor=W).grid(row=row, column=0, sticky=W, pady=3)
            Entry(cfg, textvariable=var, bg="#16162a", fg=TEXT,
                  insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4).grid(
                      row=row, column=1, sticky=EW, padx=(8, 4))
            def _pick(v=var, t=title):
                p = filedialog.askdirectory(title=t, initialdir=v.get() or ".")
                if p: v.set(p)
            Button(cfg, text="…", command=_pick,
                   bg=ACCENT2, fg="white", font=F_MAIN, relief="flat",
                   padx=8, cursor="hand2").grid(row=row, column=2)

        Label(cfg, text="Classes:", bg=CARD, fg=DIM, font=F_MAIN,
              width=18, anchor=W).grid(row=3, column=0, sticky=W, pady=3)
        Entry(cfg, textvariable=br_cls_var, bg="#16162a", fg=TEXT,
              insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4).grid(
                  row=3, column=1, columnspan=2, sticky=EW, padx=(8, 0))
        Label(cfg, text="(để trống nếu không cần phân tích theo class)",
              bg=CARD, fg=DIM, font=("Segoe UI", 7, "italic")).grid(
                  row=4, column=1, sticky=W, padx=(8, 0))

        ctrl_r = Frame(win, bg=BG, padx=8, pady=4)
        ctrl_r.pack(fill=X)
        br_run_btn = Button(ctrl_r, text="▶  Quét", bg="#2e7d32", fg="white",
                             activebackground="#1b5e20", activeforeground="white",
                             font=F_BOLD, relief="flat", padx=16, cursor="hand2")
        br_run_btn.pack(side=LEFT)
        br_status = Label(ctrl_r, text="", bg=BG, fg=DIM, font=F_MAIN)
        br_status.pack(side=LEFT, padx=12)
        br_pb = ttk.Progressbar(win, maximum=100)
        br_pb.pack(fill=X, padx=8, pady=(0, 4))

        # ── Bảng 1: Phân bố toàn bộ dataset ──────────────────────────
        Label(win, text="Phân bố độ sáng toàn dataset",
              bg=BG, fg=TEXT, font=F_BOLD, padx=8, anchor=W).pack(fill=X)
        tbl1_f = Frame(win, bg=BG, padx=8)
        tbl1_f.pack(fill=X)
        cols1 = ("bucket", "count", "pct", "bar", "status")
        br_tree1 = ttk.Treeview(tbl1_f, columns=cols1, show="headings",
                                  style="Dark.Treeview", height=5)
        for col, hdr, w, anc in [
            ("bucket", "Mức sáng",     160, W),
            ("count",  "Số ảnh",        80, CENTER),
            ("pct",    "%",             60, CENTER),
            ("bar",    "Biểu đồ",      220, W),
            ("status", "Đánh giá",     130, CENTER),
        ]:
            br_tree1.heading(col, text=hdr)
            br_tree1.column(col, width=w, anchor=anc, stretch=(col == "bar"))
        vsb1 = ttk.Scrollbar(tbl1_f, orient=VERTICAL, command=br_tree1.yview)
        vsb1.pack(side=RIGHT, fill=Y)
        br_tree1.pack(fill=X)
        br_tree1.configure(yscrollcommand=vsb1.set)
        br_tree1.tag_configure("ok",   foreground=SUCCESS)
        br_tree1.tag_configure("warn", foreground="#f0c040")
        br_tree1.tag_configure("bad",  foreground="#f05050")

        # ── Bảng 2: Phân bố theo class ───────────────────────────────
        Label(win, text="Phân bố độ sáng theo class (% ảnh tối / bình thường / sáng)",
              bg=BG, fg=TEXT, font=F_BOLD, padx=8, anchor=W).pack(fill=X, pady=(8, 0))
        tbl2_f = Frame(win, bg=BG, padx=8)
        tbl2_f.pack(fill=BOTH, expand=True)
        cols2 = ("cls", "total", "v_dark", "dark", "normal", "bright", "v_bright",
                 "glare", "std", "warn")
        br_tree2 = ttk.Treeview(tbl2_f, columns=cols2, show="headings",
                                  style="Dark.Treeview", height=7)
        for col, hdr, w, anc in [
            ("cls",     "Class",         130, W),
            ("total",   "Ảnh",            55, CENTER),
            ("v_dark",  "Rất tối",        65, CENTER),
            ("dark",    "Tối",            65, CENTER),
            ("normal",  "Bình thường",    90, CENTER),
            ("bright",  "Sáng",           65, CENTER),
            ("v_bright","Rất sáng",       70, CENTER),
            ("glare",   "Chói% px>240",   90, CENTER),
            ("std",     "Std (tương phản)",90, CENTER),
            ("warn",    "Cảnh báo",      200, W),
        ]:
            br_tree2.heading(col, text=hdr)
            br_tree2.column(col, width=w, anchor=anc, stretch=(col == "warn"))
        vsb2 = ttk.Scrollbar(tbl2_f, orient=VERTICAL, command=br_tree2.yview)
        hsb2 = ttk.Scrollbar(tbl2_f, orient=HORIZONTAL, command=br_tree2.xview)
        br_tree2.configure(yscrollcommand=vsb2.set, xscrollcommand=hsb2.set)
        vsb2.pack(side=RIGHT, fill=Y)
        hsb2.pack(side=BOTTOM, fill=X)
        br_tree2.pack(fill=BOTH, expand=True)
        br_tree2.tag_configure("ok",   foreground=SUCCESS)
        br_tree2.tag_configure("warn", foreground="#f0c040")
        br_tree2.tag_configure("bad",  foreground="#f05050")

        sum_lbl = Label(win, text="", bg=BG, fg=DIM,
                        font=("Consolas", 9), anchor=W, padx=8)
        sum_lbl.pack(fill=X, pady=(2, 6))

        def _do_run():
            img_dir = br_img_var.get().strip()
            if not img_dir or not os.path.isdir(img_dir):
                messagebox.showwarning("Thiếu thư mục", "Chọn thư mục images.", parent=win)
                return
            lbl_dir   = br_lbl_var.get().strip() or None
            cls_names = [c.strip() for c in br_cls_var.get().replace(",", " ").split() if c.strip()]
            br_run_btn.config(state=DISABLED)
            br_pb["value"] = 0
            br_status.config(text="Đang quét…", fg=ACCENT)
            for t in (br_tree1, br_tree2):
                for iid in t.get_children(): t.delete(iid)
            sum_lbl.config(text="")
            threading.Thread(
                target=self._run_brightness_analysis,
                args=(img_dir, lbl_dir, cls_names, br_pb, br_status,
                      br_tree1, br_tree2, sum_lbl, br_run_btn),
                daemon=True).start()

        br_run_btn.config(command=_do_run)
        win.lift(); win.focus_set()

    def _run_brightness_analysis(self, img_dir, lbl_dir, cls_names,
                                  pb, status_lbl, tree1, tree2, sum_lbl, run_btn):
        def _ui(fn): self.root.after(0, fn)

        try:
            from PIL import Image as _PILImg
        except ImportError:
            _ui(lambda: status_lbl.config(text="Cần cài Pillow: pip install Pillow", fg="#f05050"))
            _ui(lambda: run_btn.config(state=NORMAL))
            return

        _EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
        img_paths = sorted(p for p in Path(img_dir).rglob("*")
                           if p.is_file() and p.suffix.lower() in _EXTS)
        total = len(img_paths)
        if not total:
            _ui(lambda: status_lbl.config(text="Không tìm thấy ảnh!", fg="#f0c040"))
            _ui(lambda: run_btn.config(state=NORMAL))
            return

        # Buckets: (label, min, max)
        BUCKETS = [
            ("Rất tối  (0–30)",    0,   30),
            ("Tối      (30–70)",   30,  70),
            ("Bình thường (70–170)", 70, 170),
            ("Sáng     (170–210)", 170, 210),
            ("Rất sáng (210–255)", 210, 256),
        ]
        bucket_counts = [0] * 5
        # per_class[cid] = [(bucket_idx, glare_pct, std), ...]
        per_class = {}

        for i, ip in enumerate(img_paths):
            mean = glare_pct = std = -1.0
            try:
                img      = _PILImg.open(ip).convert("L")  # grayscale
                pixels   = list(img.getdata())
                n_px     = len(pixels)
                mean     = sum(pixels) / n_px
                # std deviation (tương phản)
                variance = sum((p - mean) ** 2 for p in pixels) / n_px
                std      = variance ** 0.5
                # chói lóa: % pixel > 240
                glare_pct = sum(1 for p in pixels if p > 240) / n_px * 100
            except Exception:
                pass

            if mean >= 0:
                for bi, (_, lo, hi) in enumerate(BUCKETS):
                    if lo <= mean < hi:
                        bucket_counts[bi] += 1
                        break

            # Map to classes via label file
            if lbl_dir:
                lp = Path(lbl_dir) / (ip.stem + ".txt")
                if lp.exists():
                    try:
                        with open(lp) as f:
                            cids = {int(l.split()[0]) for l in f if l.strip()}
                        for cid in cids:
                            if cid not in per_class:
                                per_class[cid] = []
                            if mean >= 0:
                                for bi, (_, lo, hi) in enumerate(BUCKETS):
                                    if lo <= mean < hi:
                                        per_class[cid].append((bi, glare_pct, std))
                                        break
                    except Exception:
                        pass

            if i % 100 == 0:
                _ui(lambda v=int(i / total * 90): pb.config(value=v))

        valid_total = sum(bucket_counts)
        summary = {
            "img_dir": img_dir,
            "total": total,
            "buckets": {},
            "per_class": {},
        }

        def _refresh():
            for t in (tree1, tree2):
                for iid in t.get_children(): t.delete(iid)

            MAX_BAR = 200
            warnings = []
            for bi, (label, _, _) in enumerate(BUCKETS):
                cnt = bucket_counts[bi]
                pct = cnt / valid_total * 100 if valid_total else 0
                bar_w = int(pct / 100 * MAX_BAR)
                bar = "█" * (bar_w // 6)
                if bi in (0, 1):   # dark
                    col  = "#4fc3f7"
                    tag  = "warn" if pct > 40 else "ok"
                    st   = "⚠ Quá nhiều tối" if pct > 40 else "OK"
                elif bi == 2:      # normal
                    col  = "#4caf50"
                    tag  = "ok"
                    st   = "Tốt"
                else:              # bright
                    col  = "#f0c040"
                    tag  = "warn" if pct > 30 else "ok"
                    st   = "⚠ Quá sáng" if pct > 30 else "OK"
                if "⚠" in st:
                    warnings.append(f"{label.strip()}: {pct:.0f}%")
                tree1.insert("", END, values=(label, cnt, f"{pct:.1f}%", bar, st), tags=(tag,))
                summary["buckets"][label.strip()] = {"count": cnt, "pct": round(pct, 1)}

            # Per-class table
            for cid in sorted(per_class.keys()):
                name    = cls_names[cid] if cid < len(cls_names) else f"class_{cid}"
                entries = per_class[cid]   # list of (bucket_idx, glare_pct, std)
                n       = len(entries) or 1
                cnts    = [sum(1 for e in entries if e[0] == bi) for bi in range(5)]
                pcts    = [c / n * 100 for c in cnts]
                # glare & std averages (skip -1 sentinel)
                glare_vals = [e[1] for e in entries if e[1] >= 0]
                std_vals   = [e[2] for e in entries if e[2] >= 0]
                avg_glare  = sum(glare_vals) / len(glare_vals) if glare_vals else 0.0
                avg_std    = sum(std_vals)   / len(std_vals)   if std_vals   else 0.0
                dark_pct   = (cnts[0] + cnts[1]) / n
                bright_pct = (cnts[3] + cnts[4]) / n
                warns = []
                if dark_pct > 0.5:
                    warns.append(f"⚠ {dark_pct*100:.0f}% tối → thêm ảnh ban ngày")
                if bright_pct > 0.4:
                    warns.append(f"⚠ {bright_pct*100:.0f}% sáng → thêm ảnh ban đêm")
                if avg_glare > 5:
                    warns.append(f"⚠ Chói lóa {avg_glare:.1f}% px cháy trắng")
                if avg_std > 80:
                    warns.append(f"⚠ Tương phản cao std={avg_std:.0f}")
                if cnts[2] / n < 0.3:
                    warns.append("Thiếu ảnh điều kiện bình thường")
                tag = "bad" if len(warns) >= 2 else ("warn" if warns else "ok")
                tree2.insert("", END,
                             values=(name, n,
                                     f"{pcts[0]:.0f}%", f"{pcts[1]:.0f}%",
                                     f"{pcts[2]:.0f}%", f"{pcts[3]:.0f}%",
                                     f"{pcts[4]:.0f}%",
                                     f"{avg_glare:.1f}%",
                                     f"{avg_std:.0f}",
                                     "  ".join(warns) if warns else "OK"),
                             tags=(tag,))
                summary["per_class"][name] = {
                    "total":           n,
                    "very_dark_pct":   round(pcts[0], 1),
                    "dark_pct":        round(pcts[1], 1),
                    "normal_pct":      round(pcts[2], 1),
                    "bright_pct":      round(pcts[3], 1),
                    "very_bright_pct": round(pcts[4], 1),
                    "glare_pct":       round(avg_glare, 1),
                    "contrast_std":    round(avg_std, 1),
                }

            pb.config(value=100)
            status_lbl.config(text=f"✔  Quét xong {total} ảnh", fg=SUCCESS)
            run_btn.config(state=NORMAL)
            sum_lbl.config(
                text="  ⚠ " + "  |  ".join(warnings) if warnings
                else "  Phân bố độ sáng bình thường",
                fg="#f0c040" if warnings else SUCCESS)

            # Write summary JSON for HTML report
            try:
                out = Path(img_dir).parent / "brightness_summary.json"
                with open(out, "w", encoding="utf-8") as jf:
                    json.dump(summary, jf, ensure_ascii=False, indent=2)
            except Exception:
                pass

        _ui(_refresh)

    # ── HTML Report ───────────────────────────────────────────────────────────

    def _generate_html_report(self):
        """Tổng hợp tất cả phân tích → file HTML → mở browser."""
        import tempfile as _tmp
        import webbrowser as _wb

        base = Path(self._output_dir) if self._output_dir and os.path.isdir(self._output_dir) \
               else Path(self.train_dir.get().strip()) if self.train_dir.get().strip() \
               else Path(".")
        train_dir = self.train_dir.get().strip()

        # ── Collect data ──────────────────────────────────────────────
        # 1. Training metrics from results.csv
        metrics = {}
        csv_path = base / "results.csv"
        if csv_path.exists():
            try:
                with open(csv_path, newline="", encoding="utf-8") as f:
                    rows = [{k.strip(): v.strip() for k, v in r.items()}
                            for r in __import__("csv").DictReader(f)]
                if rows:
                    def _gf(row, *keys):
                        for k in keys:
                            try:
                                v = float(row.get(k, ""))
                                if v == v: return v
                            except Exception: pass
                        return float("nan")
                    best = max(rows, key=lambda r: (
                        lambda m, m9: 0.1*m+0.9*m9 if m==m and m9==m9 else -1
                    )(_gf(r,"metrics/mAP50(B)"), _gf(r,"metrics/mAP50-95(B)")))
                    last10 = rows[-10:]
                    v_losses = [_gf(r,"val/box_loss") for r in last10]
                    t_losses = [_gf(r,"train/box_loss") for r in last10]
                    v_ok = [v for v in v_losses if v==v]
                    t_ok = [v for v in t_losses if v==v]
                    overfit = (len(v_ok)>=5 and v_ok[-1]-v_ok[0]>0.01
                               and (t_ok[-1]-t_ok[0]<-0.005 if t_ok else False))
                    metrics = {
                        "epochs": len(rows),
                        "map50":  round(_gf(best,"metrics/mAP50(B)"), 4),
                        "map95":  round(_gf(best,"metrics/mAP50-95(B)"), 4),
                        "prec":   round(_gf(best,"metrics/precision(B)"), 4),
                        "rec":    round(_gf(best,"metrics/recall(B)"), 4),
                        "overfit": overfit,
                    }
            except Exception:
                pass

        # 2. FP analysis summary
        fp_data = {}
        for fp_dir in [base / "fp_analysis", base / "weights" / "fp_analysis"]:
            sj = fp_dir / "summary.json"
            if sj.exists():
                try:
                    with open(sj, encoding="utf-8") as f:
                        fp_data = json.load(f)
                    break
                except Exception:
                    pass

        # 3. Miss analysis summary
        miss_data = {}
        for md in [base / "missed_analysis", base / "weights" / "missed_analysis"]:
            sj = md / "summary.json"
            if sj.exists():
                try:
                    with open(sj, encoding="utf-8") as f:
                        miss_data = json.load(f)
                    break
                except Exception:
                    pass

        # 4. Imbalance summary
        imb_data = {}
        for ib in [Path(train_dir).parent / "imbalance_summary.json",
                   base / "imbalance_summary.json"]:
            if ib.exists():
                try:
                    with open(ib, encoding="utf-8") as f:
                        imb_data = json.load(f)
                    break
                except Exception:
                    pass

        # 5. Shape summary
        shape_data = {}
        for sd in [Path(train_dir).parent / "shape_summary.json",
                   base / "shape_summary.json"]:
            if sd.exists():
                try:
                    with open(sd, encoding="utf-8") as f:
                        shape_data = json.load(f)
                    break
                except Exception:
                    pass

        # 6. Brightness summary
        brightness_data = {}
        for bd in [Path(train_dir).parent / "brightness_summary.json",
                   base / "brightness_summary.json"]:
            if bd.exists():
                try:
                    with open(bd, encoding="utf-8") as f:
                        brightness_data = json.load(f)
                    break
                except Exception:
                    pass

        # ── Build HTML ────────────────────────────────────────────────
        def _nan_str(v, digits=4):
            if isinstance(v, float) and v != v: return "—"
            if isinstance(v, float): return f"{v:.{digits}f}"
            return str(v)

        def _pct_bar(pct, color="#F05922", width=120):
            w = max(0, min(int(pct / 100 * width), width))
            return (f'<div style="display:inline-block;vertical-align:middle;'
                    f'background:#2a2a3e;width:{width}px;height:10px;border-radius:3px">'
                    f'<div style="background:{color};width:{w}px;height:10px;border-radius:3px"></div>'
                    f'</div> {pct:.1f}%')

        def _status_badge(text, color):
            return (f'<span style="background:{color};color:#fff;padding:2px 8px;'
                    f'border-radius:4px;font-size:12px">{text}</span>')

        issues = []  # list of (issue, severity, status, action)

        # Overfitting
        if metrics:
            sev = "⚠ Cảnh báo" if metrics.get("overfit") else "✅ Bình thường"
            col = "#f0c040" if metrics.get("overfit") else "#4caf50"
            action = ("Tăng Weight Decay, dùng Early Stopping, bổ sung augmentation"
                      if metrics.get("overfit") else "Không cần xử lý")
            issues.append(("Overfitting", sev, col, action,
                           f"Val loss tăng khi train loss giảm" if metrics.get("overfit") else "Không phát hiện"))

        # Low precision / FP
        if metrics.get("prec") and metrics["prec"] == metrics["prec"]:
            if metrics["prec"] < 0.85:
                issues.append(("False Positive (Nhận nhầm)", "⚠ Cần xử lý", "#f0c040",
                               "Đã chạy FP Analysis + thêm Hard Negative → Retrain" if fp_data else
                               "Chạy FP Analysis → thêm Hard Negative → Retrain",
                               f"Precision = {_nan_str(metrics['prec'])} (< 0.85)"))
            else:
                issues.append(("False Positive (Nhận nhầm)", "✅ Tốt", "#4caf50",
                               "Không cần xử lý", f"Precision = {_nan_str(metrics['prec'])}"))

        # Low recall / FN
        if metrics.get("rec") and metrics["rec"] == metrics["rec"]:
            if metrics["rec"] < 0.80:
                issues.append(("False Negative (Bỏ sót)", "⚠ Cần xử lý", "#f0c040",
                               "Đã chạy Miss Analysis" if miss_data else
                               "Chạy Miss Analysis → thu thập thêm data góc/ánh sáng đó",
                               f"Recall = {_nan_str(metrics['rec'])} (< 0.80)"))
            else:
                issues.append(("False Negative (Bỏ sót)", "✅ Tốt", "#4caf50",
                               "Không cần xử lý", f"Recall = {_nan_str(metrics['rec'])}"))

        # Class imbalance
        if imb_data.get("counts"):
            cnt_vals = list(imb_data["counts"].values())
            if cnt_vals:
                ratio = min(cnt_vals) / max(cnt_vals) if max(cnt_vals) else 1
                if ratio < 0.2:
                    issues.append(("Class Imbalance", "❌ Nghiêm trọng", "#f05050",
                                   "Oversampling class ít / Undersampling class nhiều / Augment thêm",
                                   f"Tỉ lệ min/max = {ratio:.2f}"))
                elif ratio < 0.5:
                    issues.append(("Class Imbalance", "⚠ Cảnh báo", "#f0c040",
                                   "Cân nhắc thu thập thêm ảnh cho class ít mẫu",
                                   f"Tỉ lệ min/max = {ratio:.2f}"))
                else:
                    issues.append(("Class Imbalance", "✅ Cân bằng", "#4caf50",
                                   "Không cần xử lý", f"Tỉ lệ min/max = {ratio:.2f}"))

        # Small objects
        if shape_data.get("shape"):
            for cls_nm, sh in shape_data["shape"].items():
                if sh.get("tiny_pct", 0) > 40:
                    issues.append(("Object nhỏ (Tiny bbox)", "⚠ Cảnh báo", "#f0c040",
                                   f"Tăng imgsz (640→1280) để detect object nhỏ tốt hơn",
                                   f"Class '{cls_nm}': {sh['tiny_pct']}% bbox < 2% ảnh"))
                    break

        # Aspect ratio
        if shape_data.get("shape"):
            for cls_nm, sh in shape_data["shape"].items():
                if sh.get("wide_pct", 0) > 60 or sh.get("tall_pct", 0) > 60:
                    issues.append(("Tỉ lệ bbox bất thường", "⚠ Cảnh báo", "#f0c040",
                                   "Kiểm tra lại augmentation flip/rotate có phù hợp không",
                                   f"Class '{cls_nm}': wide={sh.get('wide_pct',0)}% tall={sh.get('tall_pct',0)}%"))
                    break

        # Brightness
        if brightness_data.get("buckets"):
            bkts = brightness_data["buckets"]
            dark_pct   = bkts.get("Rất tối  (0–30)",    {}).get("pct", 0) \
                       + bkts.get("Tối      (30–70)",   {}).get("pct", 0)
            bright_pct = bkts.get("Sáng     (170–210)", {}).get("pct", 0) \
                       + bkts.get("Rất sáng (210–255)", {}).get("pct", 0)
            if dark_pct > 50:
                issues.append(("Thiếu data ban ngày / sáng", "⚠ Cảnh báo", "#f0c040",
                               "Thu thập thêm ảnh điều kiện ánh sáng tốt",
                               f"{dark_pct:.0f}% ảnh trong dataset thuộc nhóm tối"))
            elif bright_pct > 40:
                issues.append(("Thiếu data ban đêm / tối", "⚠ Cảnh báo", "#f0c040",
                               "Thu thập thêm ảnh ban đêm / thiếu sáng",
                               f"{bright_pct:.0f}% ảnh trong dataset thuộc nhóm sáng"))
            else:
                issues.append(("Phân bố độ sáng", "✅ Cân bằng", "#4caf50",
                               "Không cần xử lý",
                               f"Tối {dark_pct:.0f}% / Sáng {bright_pct:.0f}%"))

        # ── HTML template ─────────────────────────────────────────────
        now_str = __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        run_name = self._name_var.get().strip() or "kztek_train"
        model_name = Path(self._model_var.get()).name if self._model_var.get() else "—"

        # Issue summary rows
        issue_rows = ""
        for issue, sev, col, action, detail in issues:
            issue_rows += f"""
            <tr>
              <td>{issue}</td>
              <td><span style="color:{col};font-weight:bold">{sev}</span></td>
              <td style="color:#9090b0;font-size:13px">{detail}</td>
              <td style="color:#e0e0f0">{action}</td>
            </tr>"""

        # FP confusion table
        fp_rows = ""
        if fp_data.get("confusion_pairs"):
            for pair in fp_data["confusion_pairs"][:15]:
                cnt = pair["count"]
                col = "#f05050" if cnt >= 5 else "#f0c040"
                fp_rows += f"""<tr>
                  <td>{pair['gt']}</td>
                  <td style="color:#F05922">→ {pair['pred']}</td>
                  <td style="color:{col}">{cnt}</td>
                </tr>"""

        # Miss table
        miss_rows = ""
        if miss_data.get("classes"):
            for cls in miss_data["classes"]:
                mp = cls.get("miss_pct", 0)
                col = "#f05050" if mp >= 20 else ("#f0c040" if mp >= 5 else "#4caf50")
                miss_rows += f"""<tr>
                  <td>{cls['name']}</td>
                  <td>{cls.get('total',0)}</td>
                  <td>{cls.get('missed',0)}</td>
                  <td style="color:{col}">{mp}%</td>
                  <td style="color:#9090b0;font-size:12px">
                    Tiny: {cls.get('tiny_pct',0)}%
                  </td>
                </tr>"""

        # Imbalance table
        imb_rows = ""
        if imb_data.get("counts"):
            cnt_vals = list(imb_data["counts"].values())
            max_c = max(cnt_vals) if cnt_vals else 1
            for name, cnt in sorted(imb_data["counts"].items(), key=lambda x: -x[1]):
                pct = cnt / sum(cnt_vals) * 100 if cnt_vals else 0
                ratio = cnt / max_c
                col = "#4caf50" if ratio >= 0.5 else ("#f0c040" if ratio >= 0.2 else "#f05050")
                bar_w = int(ratio * 160)
                imb_rows += f"""<tr>
                  <td>{name}</td>
                  <td style="text-align:right">{cnt}</td>
                  <td>{pct:.1f}%</td>
                  <td><div style="display:inline-block;background:#2a2a3e;width:160px;height:10px;border-radius:3px;vertical-align:middle">
                    <div style="background:{col};width:{bar_w}px;height:10px;border-radius:3px"></div>
                  </div></td>
                  <td style="color:{col}">{'Cân bằng' if ratio>=0.5 else ('Thiếu mẫu' if ratio>=0.2 else '⚠ Rất ít')}</td>
                </tr>"""

        # Shape table
        shape_rows = ""
        if shape_data.get("shape"):
            for name, sh in shape_data["shape"].items():
                tiny = sh.get("tiny_pct",0)
                col  = "#f05050" if tiny>40 else ("#f0c040" if tiny>20 else "#4caf50")
                shape_rows += (
                    "<tr><td>" + name + "</td>"
                    "<td>" + str(sh.get("total",0)) + "</td>"
                    '<td style="color:' + col + '">' + str(tiny) + "%</td>"
                    "<td>" + str(sh.get("wide_pct",0)) + "%</td>"
                    "<td>" + str(sh.get("tall_pct",0)) + "%</td></tr>"
                )

        # Brightness rows
        BUCKET_KEYS = [
            "Rất tối  (0–30)", "Tối      (30–70)",
            "Bình thường (70–170)", "Sáng     (170–210)", "Rất sáng (210–255)"
        ]
        BUCKET_COLORS = ["#4fc3f7", "#4fc3f7", "#4caf50", "#f0c040", "#f05050"]
        brightness_rows = ""
        if brightness_data.get("buckets"):
            for key, col in zip(BUCKET_KEYS, BUCKET_COLORS):
                bk = brightness_data["buckets"].get(key, {})
                cnt = bk.get("count", 0)
                pct = bk.get("pct", 0.0)
                bar_w = int(pct / 100 * 160)
                brightness_rows += (
                    "<tr><td>" + key.strip() + "</td>"
                    "<td>" + str(cnt) + "</td>"
                    "<td>" + str(pct) + "%</td>"
                    '<td><div style="display:inline-block;background:#1e1e2e;'
                    'width:160px;height:10px;border-radius:3px;vertical-align:middle">'
                    '<div style="background:' + col + ';width:' + str(bar_w) + 'px;'
                    'height:10px;border-radius:3px"></div></div></td></tr>'
                )
        brightness_cls_rows = ""
        if brightness_data.get("per_class"):
            for nm, bd in brightness_data["per_class"].items():
                dark  = bd.get("very_dark_pct", 0) + bd.get("dark_pct", 0)
                norm  = bd.get("normal_pct", 0)
                bri   = bd.get("bright_pct", 0) + bd.get("very_bright_pct", 0)
                glare = bd.get("glare_pct", 0)
                std   = bd.get("contrast_std", 0)
                dc    = "#f05050" if dark  > 50 else ("#f0c040" if dark  > 30 else "#4caf50")
                nc    = "#4caf50" if norm  > 40 else "#f0c040"
                bc    = "#f05050" if bri   > 40 else ("#f0c040" if bri   > 20 else "#4caf50")
                gc    = "#f05050" if glare > 5  else ("#f0c040" if glare > 2  else "#4caf50")
                sc    = "#f05050" if std   > 80 else ("#f0c040" if std   > 60 else "#4caf50")
                brightness_cls_rows += (
                    "<tr><td>" + nm + "</td>"
                    "<td>" + str(bd.get("total", 0)) + "</td>"
                    '<td style="color:' + dc + '">' + str(round(dark,  1)) + "%</td>"
                    '<td style="color:' + nc + '">' + str(norm)            + "%</td>"
                    '<td style="color:' + bc + '">' + str(round(bri,  1)) + "%</td>"
                    '<td style="color:' + gc + '">' + str(glare)           + "%</td>"
                    '<td style="color:' + sc + '">' + str(std)             + "</td></tr>"
                )

        # Metrics section
        map50_v = metrics.get("map50", float("nan"))
        map95_v = metrics.get("map95", float("nan"))
        prec_v  = metrics.get("prec",  float("nan"))
        rec_v   = metrics.get("rec",   float("nan"))
        def _mc(v, hi, lo):
            if v != v: return "#9090b0"
            return "#4caf50" if v >= hi else ("#f0c040" if v >= lo else "#f05050")

        metrics_html = ""
        if metrics:
            _metric_boxes = "".join(
                '<div class="metric-box">'
                '<div class="metric-label">' + lbl + '</div>'
                '<div class="metric-val" style="color:' + _mc(val, hi, lo) + '">'
                + _nan_str(val) + '</div></div>'
                for lbl, val, hi, lo in [
                    ("mAP50",    map50_v, 0.85, 0.65),
                    ("mAP50-95", map95_v, 0.70, 0.50),
                    ("Precision", prec_v, 0.95, 0.85),
                    ("Recall",    rec_v,  0.85, 0.70),
                ]
            )
            _overfit_banner = (
                '<div class="alert-warn">⚠ OVERFIT phát hiện: val loss tăng trong khi '
                'train loss giảm → tăng Weight Decay hoặc dùng Early Stopping</div>'
                if metrics.get("overfit") else ""
            )
            metrics_html = (
                '<div class="section">'
                '<h2>📊 Kết quả Training</h2>'
                '<p style="color:#9090b0">Model: <b style="color:#e0e0f0">' + model_name + '</b>'
                ' &nbsp;|&nbsp; Run: <b style="color:#e0e0f0">' + run_name + '</b>'
                ' &nbsp;|&nbsp; Epochs: <b style="color:#e0e0f0">'
                + str(metrics.get("epochs", "—")) + '</b></p>'
                '<div style="display:flex;gap:24px;flex-wrap:wrap;margin:12px 0">'
                + _metric_boxes +
                '</div>' + _overfit_banner + '</div>'
            )

        html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<title>KZTEK Training Issues Report — {run_name}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', sans-serif; background: #1e1e2e; color: #e0e0f0;
         font-size: 14px; padding: 24px; }}
  h1 {{ color: #F05922; font-size: 22px; margin-bottom: 4px; }}
  h2 {{ color: #B8B3D6; font-size: 16px; margin: 0 0 12px 0;
        padding-bottom: 6px; border-bottom: 1px solid #2a2a3e; }}
  .section {{ background: #2a2a3e; border-radius: 8px; padding: 18px 20px;
              margin-bottom: 18px; }}
  .subtitle {{ color: #9090b0; font-size: 12px; margin-bottom: 16px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{ background: #251C53; color: #B8B3D6; text-align: left;
        padding: 8px 10px; font-weight: 600; }}
  td {{ padding: 7px 10px; border-bottom: 1px solid #1e1e2e; color: #e0e0f0; }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover td {{ background: #32324a; }}
  .metric-box {{ background: #1e1e2e; border-radius: 6px; padding: 12px 18px;
                 min-width: 120px; text-align: center; }}
  .metric-label {{ color: #9090b0; font-size: 12px; margin-bottom: 4px; }}
  .metric-val {{ font-size: 22px; font-weight: 700; }}
  .alert-warn {{ background: #3a2a00; border-left: 3px solid #f0c040;
                 color: #f0c040; padding: 8px 12px; border-radius: 4px;
                 margin-top: 10px; font-size: 13px; }}
  .no-data {{ color: #9090b0; font-style: italic; font-size: 13px;
              padding: 8px 0; }}
  .tag-ok   {{ color: #4caf50; font-weight: bold; }}
  .tag-warn {{ color: #f0c040; font-weight: bold; }}
  .tag-bad  {{ color: #f05050; font-weight: bold; }}
</style>
</head>
<body>
<h1>KZTEK — Training Issues Report</h1>
<p class="subtitle">Run: <b style="color:#e0e0f0">{run_name}</b> &nbsp;|&nbsp;
   Model: <b style="color:#e0e0f0">{model_name}</b> &nbsp;|&nbsp;
   Tạo lúc: {now_str}</p>

<div class="section">
  <h2>🗂 Tổng quan các vấn đề</h2>
  {'<table><thead><tr><th>Vấn đề</th><th>Mức độ</th><th>Chi tiết</th><th>Cách xử lý</th></tr></thead><tbody>' + issue_rows + '</tbody></table>' if issues else '<p class="no-data">Chưa có dữ liệu — hãy chạy các phân tích trước.</p>'}
</div>

{metrics_html}

<div class="section">
  <h2>⚠ False Positive — Nhận nhầm</h2>
  {'<table><thead><tr><th>GT thực tế</th><th>Dự đoán nhầm</th><th>Số lần</th></tr></thead><tbody>' + fp_rows + '</tbody></table>' if fp_rows else '<p class="no-data">Chưa chạy FP Analysis hoặc không có FP nào.</p>'}
</div>

<div class="section">
  <h2>🔍 Miss Detection — Bỏ sót</h2>
  {'<table><thead><tr><th>Class</th><th>GT tổng</th><th>Bỏ sót</th><th>Miss%</th><th>Ghi chú</th></tr></thead><tbody>' + miss_rows + '</tbody></table>' if miss_rows else '<p class="no-data">Chưa chạy Miss Analysis.</p>'}
</div>

<div class="section">
  <h2>📊 Class Imbalance</h2>
  {'<table><thead><tr><th>Class</th><th>Số instance</th><th>%</th><th>Biểu đồ</th><th>Đánh giá</th></tr></thead><tbody>' + imb_rows + '</tbody></table>' if imb_rows else '<p class="no-data">Chưa chạy Imbalance Analysis.</p>'}
</div>

<div class="section">
  <h2>📐 Size & Shape</h2>
  {'<table><thead><tr><th>Class</th><th>Tổng</th><th>Tiny&lt;2%</th><th>Wide&gt;2:1</th><th>Tall&gt;2:1</th></tr></thead><tbody>' + shape_rows + '</tbody></table>' if shape_rows else '<p class="no-data">Chưa chạy Size & Shape Analysis.</p>'}
</div>

<div class="section">
  <h2>☀ Brightness — Phân bố độ sáng</h2>
  {'<table><thead><tr><th>Mức sáng</th><th>Số ảnh</th><th>%</th><th>Biểu đồ</th></tr></thead><tbody>' + brightness_rows + '</tbody></table>' if brightness_rows else '<p class="no-data">Chưa chạy Brightness Analysis.</p>'}
  {('<h3 style="color:#B8B3D6;font-size:14px;margin:14px 0 8px">Theo class (Tối% / Bình thường% / Sáng% / Chói% / Std)</h3><table><thead><tr><th>Class</th><th>Ảnh</th><th>Tối</th><th>Bình thường</th><th>Sáng</th><th>Chói% (px&gt;240)</th><th>Std (tương phản)</th></tr></thead><tbody>' + brightness_cls_rows + '</tbody></table>') if brightness_cls_rows else ''}
</div>

<div class="section">
  <h2>💡 Gợi ý tổng hợp</h2>
  <ul style="padding-left:20px;line-height:2">
    {''.join(f'<li style="color:#f0c040">{action} <span style="color:#9090b0">({detail})</span></li>' for issue, sev, col, action, detail in issues if "✅" not in sev)}
    {'<li style="color:#4caf50">Không có vấn đề nghiêm trọng nào cần xử lý.</li>' if all("✅" in sev for _, sev, _, _, _ in issues) and issues else ''}
  </ul>
</div>
</body>
</html>"""

        try:
            tmp = _tmp.NamedTemporaryFile(delete=False, suffix=".html",
                                          prefix="kztek_report_", mode="w", encoding="utf-8")
            tmp.write(html)
            tmp.close()
            _wb.open(f"file:///{tmp.name.replace(os.sep, '/')}")
        except Exception as exc:
            messagebox.showerror("Lỗi", f"Không thể tạo báo cáo HTML:\n{exc}")
