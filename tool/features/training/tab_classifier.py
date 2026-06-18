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
import time
from pathlib import Path
from tkinter import *
from tkinter import filedialog, messagebox, ttk

from ...core.constants import (BG, CARD, ACCENT, ACCENT2, TEXT, DIM, SUCCESS,
                                F_MAIN, F_BOLD, F_MONO, IMAGE_EXTENSIONS)
from ...core.settings import (_bind_cfg, _cfg_dir, _bind_history,
                               _push_history, _get_history)
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


# ── Embedded training script ─────────────────────────────────────────────────
_TRAIN_SCRIPT = r"""
import argparse, logging, os, random, shutil, sys
from pathlib import Path

os.environ.setdefault("YOLO_VERBOSE", "False")
logging.getLogger("ultralytics").setLevel(logging.WARNING)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root",            required=True)
    ap.add_argument("--output",          required=True)
    ap.add_argument("--model",           default="yolo11n-cls.pt")
    ap.add_argument("--epochs",          type=int,   default=50)
    ap.add_argument("--imgsz",           type=int,   default=224)
    ap.add_argument("--batch",           type=int,   default=32)
    ap.add_argument("--device",          default="0")
    ap.add_argument("--name",            default="classifier")
    ap.add_argument("--split",           type=float, default=0.8)
    ap.add_argument("--optimizer",       default="AdamW")
    ap.add_argument("--lr0",             type=float, default=0.01)
    ap.add_argument("--lrf",             type=float, default=0.01)
    ap.add_argument("--workers",         type=int,   default=4)
    ap.add_argument("--weight_decay",    type=float, default=0.0005)
    ap.add_argument("--cos_lr",          action="store_true")
    ap.add_argument("--cache",           default="False")
    ap.add_argument("--freeze",          type=int,   default=0)
    ap.add_argument("--label_smoothing", type=float, default=0.0)
    ap.add_argument("--amp",             action="store_true")
    ap.add_argument("--patience",        type=int,   default=50)
    ap.add_argument("--classes",         nargs="*",  default=None)
    args = ap.parse_args()

    try:
        from ultralytics import YOLO
    except ImportError:
        print("__ERR__ Thieu ultralytics. Cai: pip install ultralytics", flush=True)
        sys.exit(1)

    root_dir = Path(args.root)
    out_dir  = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    _EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tiff", ".tif"}

    train_d = root_dir / "train"
    val_d   = root_dir / "val"

    if train_d.is_dir() and val_d.is_dir():
        data_dir = root_dir
        print(f"__FOUND_SPLIT__ train:{train_d} val:{val_d}", flush=True)
    else:
        classes = sorted([d.name for d in root_dir.iterdir()
                          if d.is_dir() and d.name not in ("train", "val")])
        if args.classes:
            classes = [c for c in classes if c in args.classes]
        if not classes:
            print("__ERR__ Khong tim thay thu muc class nao trong root", flush=True)
            sys.exit(1)

        split_root  = out_dir / "dataset"
        split_train = split_root / "train"
        split_val   = split_root / "val"
        split_train.mkdir(parents=True, exist_ok=True)
        split_val.mkdir(parents=True, exist_ok=True)

        n_tr_total = n_va_total = 0
        for cls in classes:
            imgs = [f for f in (root_dir / cls).iterdir()
                    if f.suffix.lower() in _EXTS]
            random.shuffle(imgs)
            n_tr    = max(1, int(len(imgs) * args.split))
            tr_imgs = imgs[:n_tr]
            va_imgs = imgs[n_tr:] if len(imgs) > n_tr else imgs[-1:]
            (split_train / cls).mkdir(exist_ok=True)
            (split_val   / cls).mkdir(exist_ok=True)
            for f in tr_imgs:
                shutil.copy2(f, split_train / cls / f.name)
            for f in va_imgs:
                shutil.copy2(f, split_val   / cls / f.name)
            n_tr_total += len(tr_imgs)
            n_va_total += len(va_imgs)

        data_dir = split_root
        pct = int(args.split * 100)
        print(f"__AUTO_SPLIT__ classes:{len(classes)} train:{n_tr_total} val:{n_va_total} ratio:{pct}%", flush=True)

    tr_sub    = data_dir / "train"
    cls_names = sorted([d.name for d in tr_sub.iterdir() if d.is_dir()])
    n_tr = sum(1 for f in tr_sub.rglob("*") if f.suffix.lower() in _EXTS)
    n_va = sum(1 for f in (data_dir / "val").rglob("*") if f.suffix.lower() in _EXTS)
    print(f"__CLASSES__ {len(cls_names)} {' '.join(cls_names)}", flush=True)
    print(f"__SIZES__ train:{n_tr} val:{n_va}", flush=True)

    model     = YOLO(args.model)
    best_top1 = [0.0]

    def on_train_start(trainer):
        print(f"__DEVICE__ {getattr(trainer, 'device', '?')}", flush=True)

    def on_train_epoch_start(trainer):
        ep    = trainer.epoch + 1
        total = trainer.epochs
        print(f"__EPOCH_START__ {ep}/{total}", flush=True)

    _batch_counter = [0]

    def on_train_batch_end(trainer):
        _batch_counter[0] += 1
        if _batch_counter[0] % 100 == 0:
            ep    = trainer.epoch + 1
            total = trainer.epochs
            try:
                _l = trainer.loss
                loss = _l.item() if hasattr(_l, "item") else float(_l)
            except Exception:
                loss = 0.0
            print(f"__BATCH__ ep:{ep}/{total} step:{_batch_counter[0]} loss:{loss:.4f}", flush=True)

    def on_fit_epoch_end(trainer):
        ep    = trainer.epoch + 1
        total = trainer.epochs
        try:
            tl   = trainer.tloss
            loss = tl.item() if hasattr(tl, "item") else float(tl)
        except Exception:
            loss = 0.0
        metrics = getattr(trainer, "metrics", {}) or {}
        top1 = float(metrics.get("metrics/accuracy_top1",
                                  metrics.get("accuracy_top1", 0))) * 100
        top5 = float(metrics.get("metrics/accuracy_top5",
                                  metrics.get("accuracy_top5", 0))) * 100
        try:
            lr = trainer.optimizer.param_groups[0]["lr"]
        except Exception:
            lr = 0.0
        print(
            f"__EPOCH__ {ep}/{total} train_loss:{loss:.4f}"
            f" top1:{top1:.2f} top5:{top5:.2f} lr:{lr:.6f}",
            flush=True,
        )
        if top1 > best_top1[0]:
            best_top1[0] = top1
            print(f"__BEST__ epoch:{ep} top1:{top1:.2f}", flush=True)

    model.add_callback("on_train_start",       on_train_start)
    model.add_callback("on_train_epoch_start", on_train_epoch_start)
    model.add_callback("on_train_batch_end",   on_train_batch_end)
    model.add_callback("on_fit_epoch_end",     on_fit_epoch_end)

    cache_val = args.cache
    if cache_val.lower() == "false":
        cache_val = False

    import inspect
    sig   = inspect.signature(model.train)
    extra = {}
    if "freeze"          in sig.parameters and args.freeze > 0:
        extra["freeze"]          = args.freeze
    if "label_smoothing" in sig.parameters and args.label_smoothing > 0:
        extra["label_smoothing"] = args.label_smoothing
    if "amp"             in sig.parameters:
        extra["amp"]             = args.amp
    if "patience"        in sig.parameters:
        extra["patience"]        = args.patience

    results = model.train(
        data=str(data_dir), task="classify",
        epochs=args.epochs, imgsz=args.imgsz, batch=args.batch,
        device=args.device, project=str(out_dir), name=args.name,
        exist_ok=True, optimizer=args.optimizer, lr0=args.lr0, lrf=args.lrf,
        workers=args.workers, weight_decay=args.weight_decay,
        cos_lr=args.cos_lr, cache=cache_val, verbose=False, plots=False,
        **extra,
    )

    save_dir = (str(results.save_dir) if results and hasattr(results, "save_dir")
                else str(out_dir / args.name))
    print(f"KZTEK_SAVE_DIR: {save_dir}", flush=True)

    import csv as _csv
    csv_path    = Path(save_dir) / "results.csv"
    epochs_done = 0
    if csv_path.exists():
        try:
            with open(csv_path, newline="", encoding="utf-8") as _f:
                epochs_done = sum(1 for _ in _csv.DictReader(_f))
        except Exception:
            pass
    if epochs_done < args.epochs:
        print(f"KZTEK_EARLY_STOP: {epochs_done}", flush=True)

    best = Path(save_dir) / "weights" / "best.pt"
    print(
        f"__DONE__ epochs:{epochs_done} best_top1:{best_top1[0]:.2f} best:{best}",
        flush=True,
    )


if __name__ == "__main__":
    main()
"""


_PRESET_MODELS = [
    ("yolo11n-cls.pt", "Nano  – nhanh nhất, nhẹ nhất"),
    ("yolo11s-cls.pt", "Small"),
    ("yolo11m-cls.pt", "Medium"),
    ("yolo11l-cls.pt", "Large"),
    ("yolo11x-cls.pt", "XLarge – ch\xednh x\xe1c nhất"),
]


class ClassifierTrainTab(Frame):
    """Tab huấn luyện Image Classifier d\xf9ng YOLO11 classification."""

    _MODELS = _PRESET_MODELS

    def __init__(self, master, root):
        super().__init__(master, bg=BG)
        self.root = root

        self._root_var         = StringVar()
        self._out_var          = StringVar()
        self._model_var        = StringVar(value="yolo11n-cls.pt")
        self._epochs_var       = StringVar(value="50")
        self._imgsz_var        = StringVar(value="224")
        self._batch_var        = StringVar(value="32")
        self._device_var       = StringVar(value="0")
        self._name_var         = StringVar(value="classifier")
        self._split_var        = IntVar(value=80)
        self._early_stop_var   = BooleanVar(value=False)
        self._patience_var     = StringVar(value="10")
        self._optimizer_var    = StringVar(value="AdamW")
        self._lr0_var          = StringVar(value="0.01")
        self._lrf_var          = StringVar(value="0.01")
        self._workers_var      = StringVar(value="4")
        self._weight_decay_var = StringVar(value="0.0005")
        self._cos_lr_var       = BooleanVar(value=False)
        self._cache_var        = StringVar(value="False")
        self._freeze_var       = StringVar(value="0")
        self._label_smooth_var = StringVar(value="0.0")
        self._amp_var          = BooleanVar(value=True)

        for key, var in [
            ("cls.root",         self._root_var),
            ("cls.out",          self._out_var),
            ("cls.model",        self._model_var),
            ("cls.epochs",       self._epochs_var),
            ("cls.imgsz",        self._imgsz_var),
            ("cls.batch",        self._batch_var),
            ("cls.device",       self._device_var),
            ("cls.name",         self._name_var),
            ("cls.split",        self._split_var),
            ("cls.early_stop",   self._early_stop_var),
            ("cls.patience",     self._patience_var),
            ("cls.optimizer",    self._optimizer_var),
            ("cls.lr0",          self._lr0_var),
            ("cls.lrf",          self._lrf_var),
            ("cls.workers",      self._workers_var),
            ("cls.weight_decay", self._weight_decay_var),
            ("cls.cos_lr",       self._cos_lr_var),
            ("cls.cache",        self._cache_var),
            ("cls.freeze",       self._freeze_var),
            ("cls.label_smooth", self._label_smooth_var),
            ("cls.amp",          self._amp_var),
        ]:
            _bind_cfg(key, var)

        self._proc                = None
        self._out_queue           = queue.Queue()
        self._poll_id             = None
        self._output_dir          = ""
        self._chart_poll_id       = None
        self._train_stopped_early = False
        self._train_epochs_total  = 50
        self._tmp_script          = None
        self._cls_data: dict      = {}
        self._aug_img_paths: list = []

        self._train_start   = 0.0
        self._prev_top1     = 0.0
        self._best_top1_ui  = 0.0

        self._chart_win  = None
        self._fig        = None
        self._axes       = None
        self._mpl_canvas = None
        self._epoch_lbl  = None

        self._history_win = None
        self._ckpt_win    = None
        self._aug_win     = None
        self._miss_win    = None

        self._build()

    # ──────────────────────────────────────────────────────────────────────

    def _build(self):
        # ── Top card: folder rows + split ratio ──────────────────────────
        top = Frame(self, bg=CARD, padx=12, pady=10)
        top.pack(fill=X)
        g = Frame(top, bg=CARD)
        g.pack(fill=X)
        g.columnconfigure(1, weight=1)
        _folder_row(g, "Root folder (chứa class subfolder):",
                    self._root_var, 0, bg=CARD, history_key="h.cls.root")
        _folder_row(g, "Output folder (lưu weights):",
                    self._out_var,  1, bg=CARD, history_key="h.cls.out")

        Label(g, text="Tỷ lệ tự chia:", bg=CARD, fg=DIM,
              font=F_MAIN, width=26, anchor=W).grid(row=2, column=0, sticky=W, pady=4)
        sr = Frame(g, bg=CARD)
        sr.grid(row=2, column=1, sticky=W, padx=(8, 0))
        Label(sr, text="Train", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        Spinbox(sr, from_=50, to=95, textvariable=self._split_var,
                width=4, bg="#16162a", fg=TEXT, insertbackground=TEXT,
                buttonbackground=ACCENT2, relief="flat", font=F_MAIN,
                command=self._on_split_change).pack(side=LEFT, padx=(4, 2))
        self._split_val_lbl = Label(sr, text="% / Val 20%", bg=CARD, fg=DIM, font=F_MAIN)
        self._split_val_lbl.pack(side=LEFT)
        Label(sr, text="  ← \xe1p dụng khi chưa c\xf3 subfolder train/val",
              bg=CARD, fg="#f0c040", font=("Segoe UI", 8, "italic")).pack(side=LEFT)
        self._split_var.trace_add("write", self._on_split_change)

        self._build_class_panel()
        self._build_config_panel()

        # ── Control bar ───────────────────────────────────────────────────
        ctrl = Frame(self, bg=BG, padx=12, pady=6)
        ctrl.pack(fill=X)
        self._btn_start = Button(
            ctrl, text="▶  Bắt đầu Train",
            command=self._start_train,
            bg="#2e7d32", fg="white",
            activebackground="#1b5e20", activeforeground="white",
            font=F_BOLD, relief="flat", padx=20, cursor="hand2")
        self._btn_start.pack(side=LEFT)
        self._btn_stop = Button(
            ctrl, text="⏹  Dừng",
            command=self._stop_train,
            bg="#c62828", fg="white",
            activebackground="#8b0000", activeforeground="white",
            font=F_BOLD, relief="flat", padx=14, cursor="hand2", state=DISABLED)
        self._btn_stop.pack(side=LEFT, padx=(8, 0))
        self._btn_chart = Button(
            ctrl, text="\U0001f4ca  Biểu đồ",
            command=self._open_chart_window,
            bg=ACCENT2, fg="white",
            activebackground=ACCENT, activeforeground="white",
            font=F_BOLD, relief="flat", padx=14, cursor="hand2")
        self._btn_chart.pack(side=LEFT, padx=(8, 0))
        if not _MPL_OK:
            self._btn_chart.config(state=DISABLED,
                                    text="\U0001f4ca  Biểu đồ (cần matplotlib)")
        for txt_btn, cmd in [
            ("\U0001f4cb  Lịch sử",     self._open_history_window),
            ("\U0001f4be  Checkpoint",  self._open_checkpoint_window),
            ("\U0001f5bc  Aug Preview", self._open_aug_preview),
            ("\U0001f4c8  Ph\xe2n t\xedch", self._analyze_results),
            ("\U0001f50d  Miss Analysis", self._open_miss_analysis),
            ("⬡  Export ONNX",    self._export_onnx),
        ]:
            Button(ctrl, text=txt_btn, command=cmd,
                   bg=ACCENT2, fg="white",
                   activebackground=ACCENT, activeforeground="white",
                   font=F_BOLD, relief="flat", padx=14, cursor="hand2").pack(
                       side=LEFT, padx=(8, 0))
        self._status_lbl = Label(ctrl, text="", bg=BG, fg=DIM, font=F_MAIN)
        self._status_lbl.pack(side=LEFT, padx=16)

        # ── Progress bar ───────────────────────────────────────────────────
        pb_fr = Frame(self, bg=BG, padx=12)
        pb_fr.pack(fill=X)
        self._pb_lbl = Label(pb_fr, text="Sẵn s\xe0ng", bg=BG, fg=DIM, font=F_MAIN)
        self._pb_lbl.pack(fill=X)
        self._pb = ttk.Progressbar(pb_fr, style="K.Horizontal.TProgressbar", maximum=100)
        self._pb.pack(fill=X, pady=(2, 4))

        self._build_cls_glossary()

        # ── Log box ────────────────────────────────────────────────────────
        log_frame, self._log = _make_logbox(self)
        log_frame.pack(fill=BOTH, expand=True, padx=12, pady=(2, 0))

        # ── Result bar (BOTTOM) ────────────────────────────────────────────
        res = Frame(self, bg=CARD, padx=12, pady=6)
        res.pack(fill=X, padx=12, pady=(2, 8), side=BOTTOM)
        Label(res, text="Kết quả:", bg=CARD, fg=TEXT, font=F_BOLD).pack(side=LEFT)
        self._result_lbl = Label(res, text="—", bg=CARD, fg=DIM, font=F_MAIN)
        self._result_lbl.pack(side=LEFT, padx=8)
        self._open_btn = Button(
            res, text="\U0001f4c2 Mở thư mục output",
            command=self._open_output_dir,
            bg=ACCENT2, fg="white",
            activebackground=ACCENT, activeforeground="white",
            font=F_MAIN, relief="flat", padx=10, cursor="hand2", state=DISABLED)
        self._open_btn.pack(side=LEFT, padx=4)

    # ── Class panel ────────────────────────────────────────────────────────

    def _build_class_panel(self):
        sf = LabelFrame(
            self, text=" Classes  (scan → click ☑ để bật/tắt) ",
            bg=BG, fg=TEXT, font=F_BOLD, bd=1, relief="groove", padx=8, pady=6)
        sf.pack(fill=BOTH, expand=True, padx=12, pady=(6, 4))
        tb = Frame(sf, bg=BG)
        tb.pack(fill=X, pady=(0, 4))

        def _btn(t, cmd, bg_col=CARD):
            return Button(tb, text=t, command=cmd, bg=bg_col, fg="white",
                          activebackground=ACCENT2, activeforeground="white",
                          font=F_MAIN, relief="flat", padx=8, cursor="hand2")

        _btn("\U0001f50d  Scan classes", self._scan_classes, ACCENT2).pack(side=LEFT)
        _btn("☑ Chọn tất",  self._select_all_cls).pack(side=LEFT, padx=(8, 0))
        _btn("☐ Bỏ chọn",   self._deselect_all_cls).pack(side=LEFT, padx=(4, 0))
        self._scan_cls_lbl = Label(tb, text="Chưa scan", bg=BG, fg=DIM,
                                    font=("Segoe UI", 8, "italic"))
        self._scan_cls_lbl.pack(side=LEFT, padx=10)

        tf = Frame(sf, bg=BG)
        tf.pack(fill=BOTH, expand=True)
        cols = ("check", "name", "count")
        self._cls_tree = ttk.Treeview(tf, columns=cols, show="headings",
                                       style="Dark.Treeview", height=5,
                                       selectmode="extended")
        self._cls_tree.heading("check", text="☑")
        self._cls_tree.heading("name",  text="Class name")
        self._cls_tree.heading("count", text="Ảnh")
        self._cls_tree.column("check", width=36,  minwidth=32,  anchor=CENTER, stretch=False)
        self._cls_tree.column("name",  width=280, minwidth=100, anchor=W)
        self._cls_tree.column("count", width=80,  minwidth=60,  anchor=CENTER, stretch=False)
        vsb = ttk.Scrollbar(tf, orient=VERTICAL,   command=self._cls_tree.yview)
        hsb = ttk.Scrollbar(tf, orient=HORIZONTAL, command=self._cls_tree.xview)
        self._cls_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side=RIGHT, fill=Y)
        hsb.pack(side=BOTTOM, fill=X)
        self._cls_tree.pack(fill=BOTH, expand=True)
        self._cls_tree.tag_configure("enabled",  foreground=TEXT)
        self._cls_tree.tag_configure("disabled", foreground=DIM)
        self._cls_tree.bind("<ButtonRelease-1>", self._on_cls_click)

    # ── Config panel ────────────────────────────────────────────────────────

    def _build_config_panel(self):
        pf = Frame(self, bg=CARD, padx=14, pady=8)
        pf.pack(fill=X, padx=12)
        Label(pf, text="C\xe0i đặt huấn luyện Classifier",
              bg=CARD, fg=TEXT, font=F_BOLD).grid(
                  row=0, column=0, columnspan=10, sticky=W, pady=(0, 6))

        # Model row
        Label(pf, text="Model:", bg=CARD, fg=DIM, font=F_MAIN).grid(row=1, column=0, sticky=W)
        mc_frame = Frame(pf, bg=CARD)
        mc_frame.grid(row=1, column=1, sticky=W, padx=(4, 16))
        mc = ttk.Combobox(mc_frame, textvariable=self._model_var, width=16,
                          state="readonly", font=F_MAIN,
                          values=[m for m, _ in self._MODELS])
        mc.pack(side=LEFT)
        mc.current(0)

        def _browse_model():
            p = filedialog.askopenfilename(
                title="Chọn model YOLO-cls .pt",
                filetypes=[("PyTorch model", "*.pt"), ("All files", "*.*")],
                initialdir=(str(Path(self._model_var.get()).parent)
                            if Path(self._model_var.get()).is_file() else "."))
            if p:
                self._model_var.set(p)
                self._model_desc.config(text=f"Custom: {Path(p).name}")

        Button(mc_frame, text="\U0001f4c2", command=_browse_model,
               bg=CARD, fg=TEXT, activebackground=ACCENT2, activeforeground="white",
               font=F_MAIN, relief="flat", padx=4, cursor="hand2").pack(side=LEFT, padx=(2, 0))
        self._model_desc = Label(pf, text=self._MODELS[0][1], bg=CARD, fg=DIM,
                                  font=("Segoe UI", 8, "italic"))
        self._model_desc.grid(row=2, column=0, columnspan=2, sticky=W, pady=(0, 4))
        mc.bind("<<ComboboxSelected>>", self._on_model_change)

        # Epoch / imgsz / batch / device
        for col_idx, (lbl, var, tip) in enumerate([
            ("Epochs:",  self._epochs_var, "số lần lặp to\xe0n bộ data"),
            ("Imgsz:",   self._imgsz_var,  "k\xedch thước ảnh đầu v\xe0o"),
            ("Batch:",   self._batch_var,  "−1 = auto"),
            ("Device:",  self._device_var, "0=GPU, cpu"),
        ]):
            c = (col_idx + 1) * 2
            Label(pf, text=lbl, bg=CARD, fg=DIM, font=F_MAIN).grid(
                row=1, column=c, sticky=W, padx=(16, 4))
            Entry(pf, textvariable=var, bg="#16162a", fg=TEXT,
                  insertbackground=TEXT, relief="flat", font=F_MAIN,
                  bd=4, width=7).grid(row=1, column=c + 1, sticky=W)
            Label(pf, text=tip, bg=CARD, fg=DIM,
                  font=("Segoe UI", 7, "italic")).grid(
                      row=2, column=c, columnspan=2, sticky=W)

        # Output folder + run name
        Label(pf, text="Output folder:", bg=CARD, fg=DIM, font=F_MAIN).grid(
            row=3, column=0, sticky=W, pady=(6, 0))
        pr = Frame(pf, bg=CARD)
        pr.grid(row=3, column=1, columnspan=9, sticky=EW, pady=(6, 0))
        _out_combo = ttk.Combobox(pr, textvariable=self._out_var,
                                   style="Dark.TCombobox", font=F_MAIN, width=30)
        _out_combo.pack(side=LEFT)
        _bind_history("h.cls.out", _out_combo)

        def _pick_output():
            p = filedialog.askdirectory(initialdir=_cfg_dir("cls.out"))
            if p:
                self._out_var.set(p)
                _push_history("h.cls.out", p)
                _out_combo["values"] = _get_history("h.cls.out")

        Button(pr, text="…", command=_pick_output,
               bg=ACCENT2, fg="white", font=F_MAIN, relief="flat",
               padx=8, cursor="hand2").pack(side=LEFT, padx=(4, 4))
        Button(pr, text="\U0001f4c2",
               command=lambda: (
                   os.startfile(self._out_var.get().strip())
                   if self._out_var.get().strip()
                   and os.path.isdir(self._out_var.get().strip()) else None),
               bg=CARD, fg=TEXT, font=F_MAIN, relief="flat",
               padx=6, cursor="hand2").pack(side=LEFT, padx=(0, 12))
        Label(pr, text="Run name:", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        _name_combo = ttk.Combobox(pr, textvariable=self._name_var,
                                    style="Dark.TCombobox", font=F_MAIN, width=18)
        _name_combo.pack(side=LEFT, padx=(4, 0))
        _bind_history("h.cls.name", _name_combo)

        # Early stopping
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

        # Advanced params row 1
        Label(pf, text="Tham số n\xe2ng cao:", bg=CARD, fg=DIM, font=F_BOLD).grid(
            row=5, column=0, sticky=W, pady=(8, 2))
        adv1 = Frame(pf, bg=CARD)
        adv1.grid(row=5, column=1, columnspan=9, sticky=W, pady=(8, 2))
        Label(adv1, text="Optimizer:", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        ttk.Combobox(adv1, textvariable=self._optimizer_var, width=8,
                     state="readonly", font=F_MAIN,
                     values=["auto", "SGD", "Adam", "AdamW"]).pack(
                         side=LEFT, padx=(4, 14))
        for _lbl, _var, _w in [
            ("LR0:",          self._lr0_var,          7),
            ("LRF:",          self._lrf_var,          7),
            ("Freeze:",       self._freeze_var,        4),
            ("Workers:",      self._workers_var,       4),
            ("Label Smooth:", self._label_smooth_var,  6),
            ("Weight Decay:", self._weight_decay_var,  9),
        ]:
            Label(adv1, text=_lbl, bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
            Entry(adv1, textvariable=_var, bg="#16162a", fg=TEXT,
                  insertbackground=TEXT, relief="flat", font=F_MAIN,
                  bd=4, width=_w).pack(side=LEFT, padx=(4, 14))

        # Advanced params row 2
        adv2 = Frame(pf, bg=CARD)
        adv2.grid(row=6, column=0, columnspan=10, sticky=W, pady=(2, 0))
        for text, var in [("Cosine LR", self._cos_lr_var),
                          ("AMP (Mixed Precision)", self._amp_var)]:
            Checkbutton(adv2, text=text, variable=var,
                        bg=CARD, fg=TEXT, activebackground=CARD, activeforeground=TEXT,
                        selectcolor="#16162a", font=F_MAIN).pack(side=LEFT, padx=(0, 12))
        Label(adv2, text="Cache:", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        ttk.Combobox(adv2, textvariable=self._cache_var, width=6,
                     state="readonly", font=F_MAIN,
                     values=["False", "ram", "disk"]).pack(side=LEFT, padx=(4, 0))
        Label(adv2,
              text="   (ram = load to\xe0n bộ ảnh v\xe0o RAM, tăng tốc đ\xe1ng kể)",
              bg=CARD, fg=DIM, font=("Segoe UI", 8, "italic")).pack(side=LEFT, padx=(8, 0))

    # ── Glossary ────────────────────────────────────────────────────────────

    def _build_cls_glossary(self):
        TERMS = [
            ("Model (yolo11n/s/m/l/x-cls)",
             "Kiến tr\xfac YOLO11 cho classification: n=nano (nhỏ nhất), "
             "s=small, m=medium, l=large, x=xlarge. "
             "Nano ph\xf9 hợp edge device; large/xlarge cần GPU mạnh hơn."),
            ("Top-1 Accuracy",
             "Phần trăm mẫu m\xe0 class được dự đo\xe1n "
             "cao nhất tr\xf9ng với nh\xe3n thật. Mục ti\xeau: ≥ 90%."),
            ("Top-5 Accuracy",
             "Phần trăm mẫu m\xe0 class thật nằm trong 5 class "
             "dự đo\xe1n cao nhất. Quan trọng khi số class lớn (>10)."),
            ("Freeze",
             "Đ\xf3ng băng N layer đầu ti\xean của backbone. "
             "Freeze=0 = train to\xe0n bộ. "
             "Hữu \xedch khi finetune với dataset nhỏ — "
             "tr\xe1nh overfitting backbone."),
            ("Label Smoothing",
             "Thay nh\xe3n hard (0/1) bằng soft. Gi\xe1 trị điển h\xecnh: 0.1. "
             "Để 0.0 nếu dataset lớn v\xe0 sạch."),
            ("AMP (Mixed Precision)",
             "D\xf9ng float16 cho forward, float32 cho gradient. "
             "Tiết kiệm ~50% VRAM, tăng tốc ~1.5–2\xd7. "
             "Tắt nếu gặp NaN loss."),
            ("Epochs",
             "Số lần lặp to\xe0n bộ dataset. "
             "Qu\xe1 \xedt → underfitting; qu\xe1 nhiều → overfitting."),
            ("Imgsz",
             "K\xedch thước ảnh resize trước khi đưa v\xe0o model. "
             "Mặc định 224. Tăng l\xean 320/448 nếu cần chi tiết."),
            ("Early Stopping / Patience",
             "Dừng sớm nếu Top-1 kh\xf4ng cải thiện sau Patience epoch. "
             "Tiết kiệm thời gian v\xe0 tr\xe1nh overfitting."),
        ]
        outer = Frame(self, bg=BG, padx=12)
        outer.pack(fill=X, pady=(4, 0))
        self._gloss_open = BooleanVar(value=False)
        self._gloss_btn  = Button(
            outer, text="i  Giải th\xedch thuật ngữ  ▾",
            bg=CARD, fg=DIM, font=("Segoe UI", 9),
            relief="flat", cursor="hand2", anchor="w",
            command=self._toggle_cls_glossary)
        self._gloss_btn.pack(fill=X, ipady=4)
        self._gloss_frame = Frame(outer, bg=CARD)
        txt = Text(self._gloss_frame, bg=CARD, fg=TEXT, font=("Segoe UI", 9),
                   relief="flat", wrap=WORD, cursor="arrow", height=12, padx=14, pady=8)
        txt.pack(fill=X)
        txt.tag_config("term", foreground=ACCENT, font=("Segoe UI", 9, "bold"))
        txt.tag_config("desc", foreground=TEXT,   font=("Segoe UI", 9))
        for term, desc in TERMS:
            txt.insert(END, f"▸ {term}\n", "term")
            txt.insert(END, f"  {desc}\n\n", "desc")
        txt.config(state=DISABLED)

    def _toggle_cls_glossary(self):
        if self._gloss_open.get():
            self._gloss_frame.pack_forget()
            self._gloss_btn.config(text="i  Giải th\xedch thuật ngữ  ▾")
            self._gloss_open.set(False)
        else:
            self._gloss_frame.pack(fill=X)
            self._gloss_btn.config(text="i  Giải th\xedch thuật ngữ  ▴")
            self._gloss_open.set(True)

    # ── Class panel helpers ─────────────────────────────────────────────────

    def _scan_classes(self):
        root_path = Path(self._root_var.get().strip())
        if not root_path.is_dir():
            messagebox.showwarning(
                "Chưa c\xf3 thư mục",
                "Chọn Root folder hợp lệ trước khi scan.",
                parent=self)
            return
        for iid in self._cls_tree.get_children():
            self._cls_tree.delete(iid)
        self._cls_data.clear()

        def _count(d):
            return sum(1 for f in d.rglob("*")
                       if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS)

        train_d = root_path / "train"
        src_dir = train_d if train_d.is_dir() else root_path
        classes = sorted([d.name for d in src_dir.iterdir()
                          if d.is_dir() and d.name not in ("train", "val")])
        for cls in classes:
            count = _count(src_dir / cls)
            iid   = self._cls_tree.insert(
                "", END, values=("☑", cls, count), tags=("enabled",))
            self._cls_data[iid] = {"name": cls, "count": count, "enabled": True}
        n = len(classes)
        self._scan_cls_lbl.config(
            text=f"{n} class t\xecm thấy", fg=SUCCESS if n else "#f0c040")
        _append_log(self._log, f"✔  Scan xong: {n} classes tại {root_path}")

    def _on_cls_click(self, event):
        if self._cls_tree.identify_region(event.x, event.y) != "cell":
            return
        col = self._cls_tree.identify_column(event.x)
        iid = self._cls_tree.identify_row(event.y)
        if not iid or col != "#1":
            return
        d = self._cls_data.get(iid)
        if d:
            d["enabled"] = not d["enabled"]
            self._refresh_cls_row(iid)

    def _refresh_cls_row(self, iid):
        d = self._cls_data[iid]
        self._cls_tree.item(
            iid,
            values=("☑" if d["enabled"] else "☐", d["name"], d["count"]),
            tags=("enabled" if d["enabled"] else "disabled",))

    def _select_all_cls(self):
        for iid, d in self._cls_data.items():
            d["enabled"] = True
            self._refresh_cls_row(iid)

    def _deselect_all_cls(self):
        for iid, d in self._cls_data.items():
            d["enabled"] = False
            self._refresh_cls_row(iid)

    # ── Config event handlers ────────────────────────────────────────────────

    def _on_model_change(self, _event=None):
        val = self._model_var.get()
        for name, desc in self._MODELS:
            if name == val:
                self._model_desc.config(text=desc)
                return
        self._model_desc.config(text="")

    def _on_split_change(self, *_):
        try:
            r = max(50, min(95, int(self._split_var.get())))
            self._split_val_lbl.config(text=f"% / Val {100 - r}%")
        except (ValueError, TclError):
            pass

    def _on_early_stop_toggle(self):
        self._patience_entry.config(
            state=NORMAL if self._early_stop_var.get() else DISABLED)

    # ── Browse (Ctrl+O) ─────────────────────────────────────────────────────

    def _browse(self):
        p = filedialog.askdirectory(
            title="Chọn Root folder",
            initialdir=_cfg_dir("cls.root") or None)
        if p:
            self._root_var.set(p)
            _push_history("h.cls.root", p)
            self._scan_classes()

    # ── Training ─────────────────────────────────────────────────────────────

    def _start_train(self):
        if self._proc and self._proc.poll() is None:
            return
        root_dir = self._root_var.get().strip()
        out_dir  = self._out_var.get().strip()
        if not root_dir or not Path(root_dir).is_dir():
            messagebox.showwarning(
                "Thiếu dữ liệu",
                "Chọn Root folder hợp lệ trước khi train.",
                parent=self)
            return
        if not out_dir:
            messagebox.showwarning(
                "Thiếu dữ liệu", "Chọn Output folder.", parent=self)
            return
        try:
            epochs = int(self._epochs_var.get())
        except ValueError:
            epochs = 50
        self._train_epochs_total  = epochs
        self._train_stopped_early = False
        self._train_start   = 0.0
        self._prev_top1     = 0.0
        self._best_top1_ui  = 0.0
        enabled_cls = [d["name"] for d in self._cls_data.values() if d["enabled"]]
        name        = self._name_var.get().strip() or "classifier"

        tmp = tempfile.NamedTemporaryFile(
            suffix=".py", delete=False, mode="w", encoding="utf-8")
        tmp.write(_TRAIN_SCRIPT)
        tmp.close()
        self._tmp_script = tmp.name

        cmd = [
            sys.executable, self._tmp_script,
            "--root",            root_dir,
            "--output",          out_dir,
            "--model",           self._model_var.get(),
            "--epochs",          str(epochs),
            "--imgsz",           self._imgsz_var.get(),
            "--batch",           self._batch_var.get(),
            "--device",          self._device_var.get(),
            "--name",            name,
            "--split",           str(self._split_var.get() / 100),
            "--optimizer",       self._optimizer_var.get(),
            "--lr0",             self._lr0_var.get(),
            "--lrf",             self._lrf_var.get(),
            "--workers",         self._workers_var.get(),
            "--weight_decay",    self._weight_decay_var.get(),
            "--cache",           self._cache_var.get(),
            "--freeze",          self._freeze_var.get(),
            "--label_smoothing", self._label_smooth_var.get(),
            "--patience",        self._patience_var.get(),
        ]
        if self._cos_lr_var.get():
            cmd.append("--cos_lr")
        if self._amp_var.get():
            cmd.append("--amp")
        if enabled_cls:
            cmd += ["--classes"] + enabled_cls

        cf = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        try:
            self._proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", creationflags=cf)
        except Exception as e:
            messagebox.showerror("Lỗi khởi động", str(e), parent=self)
            return

        self._output_dir = os.path.join(out_dir, name)
        self._btn_start.config(state=DISABLED)
        self._btn_stop.config(state=NORMAL)
        self._status_lbl.config(text="⏳ Đang train…", fg=ACCENT)
        self._result_lbl.config(text="—")
        self._open_btn.config(state=DISABLED)
        self._pb["value"] = 0
        self._pb_lbl.config(text="Đang khởi động…", fg=TEXT)
        self._log.configure(state=NORMAL)
        self._log.delete("1.0", END)
        self._log.configure(state=DISABLED)

        model_name = Path(self._model_var.get()).name
        _append_log(self._log,
                    f"▶  model={model_name}  epochs={epochs}"
                    f"  imgsz={self._imgsz_var.get()}  batch={self._batch_var.get()}"
                    f"  device={self._device_var.get()}")
        if self._early_stop_var.get():
            _append_log(self._log,
                        f"   Early stopping: patience={self._patience_var.get()}")
        _append_log(self._log, f"   root   : {root_dir}")
        _append_log(self._log, f"   output : {out_dir}/{name}")
        if enabled_cls:
            _append_log(self._log, f"   classes: {', '.join(enabled_cls)}")
        _append_log(self._log, "─" * 70)

        if _MPL_OK:
            self._open_chart_window()
            self._stop_chart_poll()
            self._start_chart_poll()

        def _reader():
            for line in self._proc.stdout:
                self._out_queue.put(line.rstrip())
            self._out_queue.put(None)

        threading.Thread(target=_reader, daemon=True).start()
        self._poll_output()

    def _stop_train(self):
        self._stop_chart_poll()
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            _append_log(self._log, "⚠  Training đ\xe3 bị dừng thủ c\xf4ng.")
        self._btn_start.config(state=NORMAL)
        self._btn_stop.config(state=DISABLED)
        self._status_lbl.config(text="Đ\xe3 dừng", fg="#f0c040")

    def _poll_output(self):
        try:
            while True:
                line = self._out_queue.get_nowait()
                if line is None:
                    self._on_done()
                    return
                self._handle_line(line)
        except queue.Empty:
            pass
        self._poll_id = self.root.after(400, self._poll_output)

    def _handle_line(self, line):
        if "KZTEK_SAVE_DIR:" in line:
            self._output_dir = line.split("KZTEK_SAVE_DIR:", 1)[1].strip()
            return
        if "KZTEK_EARLY_STOP:" in line:
            try:
                done = int(line.split("KZTEK_EARLY_STOP:", 1)[1].strip())
                self._train_stopped_early = done < self._train_epochs_total
            except Exception:
                pass
            return
        line = re.sub(r"\x1b\[[0-9;]*[mKA-Z]", "", line)
        if line.startswith("__ERR__"):
            _append_log(self._log, f"[LỖI] {line[7:].strip()}")
        elif line.startswith("__FOUND_SPLIT__"):
            _append_log(self._log,
                        f"✔  D\xf9ng split c\xf3 sẵn: {line[15:].strip()}")
        elif line.startswith("__AUTO_SPLIT__"):
            _append_log(self._log, f"✔  Auto split: {line[14:].strip()}")
        elif line.startswith("__CLASSES__"):
            parts = line.split(maxsplit=2)
            _append_log(self._log,
                        f"✔  {parts[1] if len(parts) > 1 else '?'} classes: "
                        f"{parts[2] if len(parts) > 2 else ''}")
        elif line.startswith("__SIZES__"):
            _append_log(self._log, f"   Dataset: {line[9:].strip()}")
        elif line.startswith("__EPOCH_START__"):
            rest = line[15:].strip()
            _append_log(self._log, f"▷  Epoch {rest} bắt đầu…")
            self._pb_lbl.config(text=f"Epoch {rest} đang chạy…", fg=DIM)
        elif line.startswith("__BATCH__"):
            rest = line[9:].strip()
            kv: dict = {}
            for tok in rest.split():
                if ":" in tok:
                    k, v = tok.split(":", 1)
                    kv[k] = v
            ep_s  = kv.get("ep",   "?")
            step  = kv.get("step", "?")
            loss  = kv.get("loss", "?")
            self._pb_lbl.config(
                text=f"Epoch {ep_s}  bước {step}  loss:{loss}  (đang chạy…)", fg=DIM)
        elif line.startswith("__DEVICE__"):
            dev = line[10:].strip()
            _append_log(self._log, f"   Device: {dev}")
            self._pb_lbl.config(text=f"Device: {dev}  —  Đang chạy epoch đầu tiên…", fg=TEXT)
            self._pb["value"] = 5
        elif line.startswith("__EPOCH__"):
            rest = line[9:].strip()
            m = re.match(r"(\d+)/(\d+)", rest)
            if not m:
                return
            ep, total = int(m.group(1)), int(m.group(2))
            self._pb["value"] = int(ep / total * 100)
            kv: dict = {}
            for tok in rest.split():
                if ":" in tok:
                    k, v = tok.split(":", 1)
                    try:
                        kv[k] = float(v)
                    except ValueError:
                        pass
            tl   = kv.get("train_loss", 0.0)
            top1 = kv.get("top1",       0.0)
            top5 = kv.get("top5",       0.0)
            lr   = kv.get("lr",         0.0)
            # ETA
            now = time.monotonic()
            if self._train_start == 0.0:
                self._train_start = now
            elapsed = now - self._train_start
            avg_sec = elapsed / ep
            eta_sec = avg_sec * (total - ep)
            if eta_sec < 3600:
                eta_str = f"{int(eta_sec/60)}m{int(eta_sec%60):02d}s"
            else:
                eta_str = f"{int(eta_sec/3600)}h{int((eta_sec%3600)/60):02d}m"
            # Δtop1
            delta     = top1 - self._prev_top1
            delta_str = f"+{delta:.2f}" if delta >= 0 else f"{delta:.2f}"
            self._prev_top1 = top1
            # Inline best marker
            is_best = top1 > self._best_top1_ui
            if is_best:
                self._best_top1_ui = top1
            best_mark = "  ★" if is_best else ""
            self._pb_lbl.config(
                text=f"Epoch {ep}/{total}  top1:{top1:.1f}%  Δ{delta_str}  ETA:{eta_str}",
                fg=TEXT)
            _append_log(
                self._log,
                f"  Ep{ep:>4}/{total}"
                f"  loss:{tl:.4f}"
                f"  top1:{top1:.2f}%  Δ{delta_str:>6}"
                f"  top5:{top5:.2f}%"
                f"  lr:{lr:.5f}"
                f"  ETA:{eta_str}"
                f"{best_mark}")
        elif line.startswith("__BEST__"):
            pass  # inline ★ trong epoch line
        elif line.startswith("__DONE__"):
            _append_log(self._log,
                        f"✔  Ho\xe0n th\xe0nh! {line[8:].strip()}")
            self._pb["value"] = 100
            self._pb_lbl.config(
                text="✔  Huấn luyện ho\xe0n tất!", fg=SUCCESS)
        else:
            if line.strip():
                _append_log(self._log, f"   {line}")

    def _on_done(self):
        self._stop_chart_poll()
        rc = 0
        if self._proc:
            try:
                self._proc.wait(timeout=10)
            except Exception:
                pass
            rc = self._proc.returncode or 0
        self._proc = None
        if self._poll_id:
            self.root.after_cancel(self._poll_id)
            self._poll_id = None
        if self._tmp_script:
            try:
                os.unlink(self._tmp_script)
            except OSError:
                pass
            self._tmp_script = None
        self._btn_start.config(state=NORMAL)
        self._btn_stop.config(state=DISABLED)
        if rc == 0:
            best = os.path.join(self._output_dir, "weights", "best.pt")
            _append_log(self._log, "─" * 70)
            if self._train_stopped_early:
                _append_log(self._log,
                            "⚡  Early stopping đ\xe3 k\xedch hoạt.")
                _append_log(self._log, f"   best.pt → {best}")
                self._status_lbl.config(text="⚡ Early stopped", fg="#f0c040")
                self._early_note_lbl.config(
                    text="(lần train trước: dừng sớm)", fg="#f0c040")
            else:
                _append_log(self._log,
                            f"✔  Ho\xe0n tất!  best.pt → {best}")
                self._status_lbl.config(text="✔ Ho\xe0n tất", fg=SUCCESS)
                self._early_note_lbl.config(text="", fg=DIM)
            self._result_lbl.config(text=f"best.pt  →  {best}")
            self._open_btn.config(state=NORMAL)
            self._update_charts()
            self._append_history_record(stopped_early=self._train_stopped_early)
            if self._ckpt_win and self._ckpt_win.winfo_exists():
                self._populate_ckpt_list()
        else:
            _append_log(self._log, f"[LỖI]  Exit code {rc}")
            self._status_lbl.config(text=f"Lỗi (exit {rc})", fg="#f05050")

    def _open_output_dir(self):
        d = self._output_dir
        if os.path.isdir(d):
            subprocess.Popen(["explorer", os.path.normpath(d)])
        else:
            messagebox.showinfo(
                "Th\xf4ng b\xe1o",
                f"Thư mục chưa tồn tại:\n{d}",
                parent=self)

    # ── Chart ─────────────────────────────────────────────────────────────────

    def _open_chart_window(self):
        if not _MPL_OK:
            messagebox.showwarning(
                "Thiếu thư viện",
                "C\xe0i matplotlib:\n\npip install matplotlib", parent=self)
            return
        if self._chart_win and self._chart_win.winfo_exists():
            self._chart_win.lift()
            self._update_charts()
            return
        self._create_chart_window()

    def _create_chart_window(self):
        run_name = self._name_var.get().strip() or "classifier"
        win = Toplevel(self.root)
        win.title(f"KZTEK Classifier – Biểu đồ  [{run_name}]")
        win.geometry("960x620")
        win.configure(bg=BG)
        win.protocol("WM_DELETE_WINDOW", win.withdraw)
        self._chart_win = win

        tb = Frame(win, bg=CARD, padx=8, pady=4)
        tb.pack(fill=X)
        self._epoch_lbl = Label(tb, text="—", bg=CARD, fg=TEXT, font=F_BOLD)
        self._epoch_lbl.pack(side=LEFT)
        Button(tb, text="↻  L\xe0m mới", command=self._update_charts,
               bg=ACCENT2, fg="white", activebackground=ACCENT, activeforeground="white",
               font=F_MAIN, relief="flat", padx=10, cursor="hand2").pack(side=RIGHT)

        fig  = Figure(figsize=(10, 5.5), dpi=92, facecolor="#16162a")
        axes = fig.subplots(2, 2)
        fig.subplots_adjust(left=0.07, right=0.97, top=0.93,
                            bottom=0.08, wspace=0.28, hspace=0.42)
        self._fig  = fig
        self._axes = axes
        for ax in axes.flat:
            ax.set_facecolor("#1e1e2e")
            for sp in ax.spines.values():
                sp.set_color("#2a2a3e")
            ax.tick_params(colors=DIM, labelsize=7)
        axes[0, 0].set_title("Train Loss",    color=TEXT, fontsize=9, pad=6)
        axes[0, 1].set_title("Val Loss",      color=TEXT, fontsize=9, pad=6)
        axes[1, 0].set_title("Top-1 Acc (%)", color=TEXT, fontsize=9, pad=6)
        axes[1, 1].set_title("Top-5 Acc (%)", color=TEXT, fontsize=9, pad=6)
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
                for row in csv.DictReader(f):
                    rows.append({k.strip(): v.strip() for k, v in row.items()})
        except Exception:
            pass
        return rows

    def _update_charts(self):
        if not (_MPL_OK and self._chart_win and self._chart_win.winfo_exists()):
            return
        rows = self._read_csv()
        if not rows:
            return

        def _vals(key):
            out = []
            for r in rows:
                try:
                    out.append(float(r[key]))
                except (KeyError, ValueError):
                    out.append(float("nan"))
            return out

        epochs = list(range(1, len(rows) + 1))
        _lk = dict(fontsize=7, labelcolor=TEXT, facecolor="#1e1e2e",
                   edgecolor="#2a2a3e", loc="upper right")

        def _plot(ax, title, series):
            ax.cla()
            ax.set_facecolor("#1e1e2e")
            for sp in ax.spines.values():
                sp.set_color("#2a2a3e")
            ax.tick_params(colors=DIM, labelsize=7)
            ax.set_title(title, color=TEXT, fontsize=9, pad=6)
            ax.set_xlabel("Epoch", color=DIM, fontsize=7)
            if epochs:
                ax.set_xlim(max(0.5, epochs[0] - 0.5), epochs[-1] + 0.5)
            plotted = False
            for key, label, color in series:
                vals = _vals(key)
                if any(v == v for v in vals):
                    ax.plot(epochs, vals, label=label, color=color,
                            linewidth=1.6, alpha=0.9)
                    plotted = True
            if plotted:
                ax.legend(**_lk)
                ax.grid(True, color="#2a2a3e", linewidth=0.5, alpha=0.6)

        _plot(self._axes[0, 0], "Train Loss",
              [("train/loss", "loss", ACCENT)])
        _plot(self._axes[0, 1], "Val Loss",
              [("val/loss",   "loss", "#4fc3f7")])
        _plot(self._axes[1, 0], "Top-1 Acc (%)",
              [("metrics/accuracy_top1", "top1", SUCCESS)])
        _plot(self._axes[1, 1], "Top-5 Acc (%)",
              [("metrics/accuracy_top5", "top5", "#B8B3D6")])

        n = len(rows)
        try:
            total = int(self._epochs_var.get())
        except ValueError:
            total = "?"
        if self._epoch_lbl:
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

    # ── History ───────────────────────────────────────────────────────────────

    def _history_file(self):
        out = self._out_var.get().strip()
        return Path(out) / "cls_history.json" if out else None

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
        rows      = self._read_csv()
        best_top1 = "—"
        if rows:
            try:
                vals = [float(r.get("metrics/accuracy_top1", "nan")) * 100
                        for r in rows]
                vals = [v for v in vals if v == v]
                if vals:
                    best_top1 = f"{max(vals):.2f}%"
            except Exception:
                pass
        record = {
            "date":          datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "model":         self._model_var.get(),
            "epochs_done":   len(rows),
            "epochs_total":  self._epochs_var.get(),
            "best_top1":     best_top1,
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
        win.title("KZTEK Classifier – Lịch sử train")
        win.geometry("880x400")
        win.configure(bg=BG)
        win.resizable(True, True)
        self._history_win = win

        tb = Frame(win, bg=CARD, padx=8, pady=6)
        tb.pack(fill=X)
        Label(tb, text="Lịch sử c\xe1c lần train classifier",
              bg=CARD, fg=TEXT, font=F_BOLD).pack(side=LEFT)
        Button(tb, text="↻ L\xe0m mới", command=self._populate_history_tree,
               bg=ACCENT2, fg="white", activebackground=ACCENT, activeforeground="white",
               font=F_MAIN, relief="flat", padx=8, cursor="hand2").pack(side=RIGHT)
        Button(tb, text="\U0001f5d1 X\xf3a lịch sử",
               command=self._clear_history,
               bg="#c62828", fg="white", activebackground="#8b0000", activeforeground="white",
               font=F_MAIN, relief="flat", padx=8, cursor="hand2").pack(
                   side=RIGHT, padx=(0, 4))

        cols = ("date", "model", "epochs", "best_top1", "early", "output")
        self._hist_tree = ttk.Treeview(win, columns=cols, show="headings",
                                        style="Dark.Treeview", height=14)
        self._hist_tree.heading("date",      text="Ng\xe0y train")
        self._hist_tree.heading("model",     text="Model")
        self._hist_tree.heading("epochs",    text="Epochs")
        self._hist_tree.heading("best_top1", text="Best Top-1")
        self._hist_tree.heading("early",     text="Kết th\xfac")
        self._hist_tree.heading("output",    text="Output dir")
        for col, w, anc, stretch in [
            ("date",      140, CENTER, False),
            ("model",     120, CENTER, False),
            ("epochs",     80, CENTER, False),
            ("best_top1",  90, CENTER, False),
            ("early",     100, CENTER, False),
            ("output",    320, W,      True),
        ]:
            self._hist_tree.column(col, width=w, anchor=anc, stretch=stretch)

        vsb = ttk.Scrollbar(win, orient=VERTICAL,   command=self._hist_tree.yview)
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
        for rec in reversed(self._load_history()):
            early  = rec.get("stopped_early", False)
            ep_str = f"{rec.get('epochs_done', '?')}/{rec.get('epochs_total', '?')}"
            tag    = "early" if early else "done"
            self._hist_tree.insert("", END, values=(
                rec.get("date",       ""),
                rec.get("model",      ""),
                ep_str,
                rec.get("best_top1", "—"),
                "Early stop" if early else "Ho\xe0n tất",
                rec.get("output_dir", ""),
            ), tags=(tag,))

    def _on_history_dbl_click(self, event):
        iid = self._hist_tree.identify_row(event.y)
        if not iid:
            return
        vals       = self._hist_tree.item(iid, "values")
        output_dir = vals[5] if len(vals) > 5 else ""
        if not output_dir or not os.path.isdir(output_dir):
            messagebox.showinfo(
                "Th\xf4ng b\xe1o",
                f"Thư mục kh\xf4ng tồn tại:\n{output_dir}",
                parent=self)
            return
        self._output_dir = output_dir
        if _MPL_OK:
            self._open_chart_window()
            self._update_charts()
        messagebox.showinfo(
            "Đ\xe3 tải",
            f"Đ\xe3 chuyển sang run:\n{output_dir}", parent=self)

    def _clear_history(self):
        if not messagebox.askyesno(
                "X\xe1c nhận",
                "X\xf3a to\xe0n bộ lịch sử train?", parent=self):
            return
        hf = self._history_file()
        if hf and hf.exists():
            try:
                hf.unlink()
            except Exception as e:
                messagebox.showerror("Lỗi", str(e), parent=self)
                return
        self._populate_history_tree()

    # ── Checkpoint manager ────────────────────────────────────────────────────

    def _open_checkpoint_window(self):
        if self._ckpt_win and self._ckpt_win.winfo_exists():
            self._ckpt_win.lift()
            self._populate_ckpt_list()
            return
        win = Toplevel(self.root)
        win.title("KZTEK Classifier – Checkpoint Manager")
        win.geometry("720x420")
        win.configure(bg=BG)
        win.resizable(True, True)
        self._ckpt_win = win

        tb = Frame(win, bg=CARD, padx=8, pady=6)
        tb.pack(fill=X)
        Label(tb, text="Danh s\xe1ch checkpoint (.pt)",
              bg=CARD, fg=TEXT, font=F_BOLD).pack(side=LEFT)
        Button(tb, text="↻ L\xe0m mới", command=self._populate_ckpt_list,
               bg=ACCENT2, fg="white", activebackground=ACCENT, activeforeground="white",
               font=F_MAIN, relief="flat", padx=8, cursor="hand2").pack(side=RIGHT)

        cols = ("name", "size", "modified")
        self._ckpt_tree = ttk.Treeview(win, columns=cols, show="headings",
                                        style="Dark.Treeview", height=14)
        self._ckpt_tree.heading("name",     text="T\xean file")
        self._ckpt_tree.heading("size",     text="K\xedch thước")
        self._ckpt_tree.heading("modified", text="Ng\xe0y sửa")
        self._ckpt_tree.column("name",     width=220, anchor=W)
        self._ckpt_tree.column("size",     width=100, anchor=CENTER, stretch=False)
        self._ckpt_tree.column("modified", width=160, anchor=CENTER, stretch=False)
        vsb = ttk.Scrollbar(win, orient=VERTICAL, command=self._ckpt_tree.yview)
        vsb.pack(side=RIGHT, fill=Y)
        self._ckpt_tree.pack(fill=BOTH, expand=True)
        self._ckpt_tree.configure(yscrollcommand=vsb.set)

        btn_row = Frame(win, bg=BG, padx=8, pady=6)
        btn_row.pack(fill=X)
        Button(btn_row, text="\U0001f4c2 Load checkpoint",
               command=self._load_selected_checkpoint,
               bg="#2e7d32", fg="white", activebackground="#1b5e20", activeforeground="white",
               font=F_MAIN, relief="flat", padx=10, cursor="hand2").pack(side=LEFT)
        Button(btn_row, text="\U0001f5d1 X\xf3a checkpoint",
               command=self._delete_selected_checkpoints,
               bg="#c62828", fg="white", activebackground="#8b0000", activeforeground="white",
               font=F_MAIN, relief="flat", padx=10, cursor="hand2").pack(
                   side=LEFT, padx=(8, 0))
        self._ckpt_info_lbl = Label(btn_row, text="", bg=BG, fg=DIM, font=F_MAIN)
        self._ckpt_info_lbl.pack(side=LEFT, padx=12)
        self._populate_ckpt_list()

    def _ckpt_search_dirs(self):
        dirs = []
        if self._output_dir and os.path.isdir(self._output_dir):
            p  = Path(self._output_dir)
            dirs.append(p)
            wd = p / "weights"
            if wd.is_dir():
                dirs.append(wd)
        out  = self._out_var.get().strip()
        name = self._name_var.get().strip() or "classifier"
        if out and os.path.isdir(out):
            rd = Path(out) / name
            if rd.is_dir() and rd not in dirs:
                dirs.append(rd)
                wd = rd / "weights"
                if wd.is_dir():
                    dirs.append(wd)
        return dirs

    def _populate_ckpt_list(self):
        if not hasattr(self, "_ckpt_tree"):
            return
        for iid in self._ckpt_tree.get_children():
            self._ckpt_tree.delete(iid)
        self._ckpt_paths: dict = {}
        found: set = set()
        for d in self._ckpt_search_dirs():
            for pt in sorted(d.glob("*.pt")):
                if pt in found:
                    continue
                found.add(pt)
                sz   = pt.stat().st_size
                sz_s = (f"{sz/1024/1024:.1f} MB"
                        if sz >= 1024 * 1024 else f"{sz/1024:.0f} KB")
                mtime = datetime.datetime.fromtimestamp(pt.stat().st_mtime)
                iid   = self._ckpt_tree.insert(
                    "", END,
                    values=(pt.name, sz_s, mtime.strftime("%Y-%m-%d %H:%M")))
                self._ckpt_paths[iid] = pt
        count = len(found)
        self._ckpt_info_lbl.config(
            text=f"{count} file .pt" if count else "Kh\xf4ng t\xecm thấy .pt",
            fg=TEXT if count else DIM)

    def _load_selected_checkpoint(self):
        sel = self._ckpt_tree.selection()
        if not sel:
            messagebox.showwarning(
                "Chưa chọn",
                "Chọn một file .pt để load.", parent=self)
            return
        pt = self._ckpt_paths.get(sel[0])
        if pt and pt.exists():
            self._model_var.set(str(pt))
            self._model_desc.config(text=f"Custom: {pt.name}")
            messagebox.showinfo(
                "Đ\xe3 load", f"Model path:\n{pt}", parent=self)
        else:
            messagebox.showerror("Lỗi", "File kh\xf4ng tồn tại.", parent=self)

    def _delete_selected_checkpoints(self):
        sel = self._ckpt_tree.selection()
        if not sel:
            messagebox.showwarning(
                "Chưa chọn",
                "Chọn c\xe1c file .pt muốn x\xf3a.", parent=self)
            return
        names = [self._ckpt_paths[iid].name
                 for iid in sel if iid in self._ckpt_paths]
        if not messagebox.askyesno(
                "X\xe1c nhận x\xf3a",
                f"X\xf3a {len(names)} file:\n" + "\n".join(names), parent=self):
            return
        errs = []
        for iid in sel:
            pt = self._ckpt_paths.get(iid)
            if pt and pt.exists():
                try:
                    pt.unlink()
                except Exception as e:
                    errs.append(f"{pt.name}: {e}")
        if errs:
            messagebox.showerror("Lỗi", "\n".join(errs), parent=self)
        self._populate_ckpt_list()

    # ── Augmentation preview ──────────────────────────────────────────────────

    def _open_aug_preview(self):
        if not _PIL_OK:
            messagebox.showwarning(
                "Thiếu thư viện",
                "C\xe0i Pillow:\n\npip install Pillow", parent=self)
            return
        root_path = Path(self._root_var.get().strip())
        if not root_path.is_dir():
            messagebox.showwarning(
                "Chưa c\xf3 thư mục",
                "Chọn Root folder trước.", parent=self)
            return
        img_files = []
        for ext in IMAGE_EXTENSIONS:
            img_files.extend(root_path.rglob(f"*{ext}"))
            img_files.extend(root_path.rglob(f"*{ext.upper()}"))
        img_files = list(set(img_files))
        if not img_files:
            messagebox.showwarning(
                "Kh\xf4ng c\xf3 ảnh",
                f"Kh\xf4ng t\xecm thấy ảnh trong:\n{root_path}", parent=self)
            return
        if self._aug_win and self._aug_win.winfo_exists():
            self._aug_win.destroy()
        win = Toplevel(self.root)
        win.title("KZTEK Classifier – Augmentation Preview")
        win.geometry("900x520")
        win.configure(bg=BG)
        win.resizable(True, True)
        self._aug_win       = win
        self._aug_img_paths = img_files

        tb = Frame(win, bg=CARD, padx=8, pady=6)
        tb.pack(fill=X)
        Label(tb, text="Ảnh gốc vs. ảnh sau augmentation",
              bg=CARD, fg=TEXT, font=F_BOLD).pack(side=LEFT)
        Button(tb, text="↻ Ảnh ngẫu nhi\xean",
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
        Label(aug_params, text="  Brightness \xb1:", bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT)
        self._aug_bright_var = DoubleVar(value=0.3)
        Scale(aug_params, variable=self._aug_bright_var, from_=0.0, to=1.0,
              resolution=0.05, orient=HORIZONTAL, bg=BG, fg=TEXT, troughcolor=CARD,
              highlightthickness=0, length=100, font=F_MAIN).pack(side=LEFT)
        Label(aug_params, text="  Hue \xb1:", bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT)
        self._aug_hue_var = IntVar(value=30)
        Scale(aug_params, variable=self._aug_hue_var, from_=0, to=90,
              orient=HORIZONTAL, bg=BG, fg=TEXT, troughcolor=CARD,
              highlightthickness=0, length=100, font=F_MAIN).pack(side=LEFT)
        Button(aug_params, text="\xc1p dụng",
               command=lambda: self._aug_refresh(win),
               bg=ACCENT, fg="white", activebackground=ACCENT2, activeforeground="white",
               font=F_MAIN, relief="flat", padx=8, cursor="hand2").pack(
                   side=LEFT, padx=(8, 0))

        img_frame = Frame(win, bg=BG)
        img_frame.pack(fill=BOTH, expand=True, padx=8, pady=4)
        img_frame.columnconfigure(0, weight=1)
        img_frame.columnconfigure(1, weight=1)
        Label(img_frame, text="Ảnh gốc",
              bg=BG, fg=DIM, font=F_MAIN).grid(row=0, column=0)
        Label(img_frame, text="Sau augmentation",
              bg=BG, fg=DIM, font=F_MAIN).grid(row=0, column=1)
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
        if not _PIL_OK or not self._aug_img_paths:
            return
        img_path = random.choice(self._aug_img_paths)
        try:
            orig = _PILImage.open(img_path).convert("RGB")
        except Exception as e:
            messagebox.showerror("Lỗi mở ảnh", str(e), parent=win)
            return
        aug = orig.copy()
        if self._aug_flip_var.get() and random.random() > 0.5:
            aug = aug.transpose(_PILImage.FLIP_LEFT_RIGHT)
        bd = self._aug_bright_var.get()
        if bd > 0:
            aug = _PILEnhance.Brightness(aug).enhance(
                max(0.1, 1.0 + random.uniform(-bd, bd)))
        hs = self._aug_hue_var.get()
        if hs > 0:
            try:
                import colorsys
                hd = random.randint(-hs, hs) / 360.0
                r_c, g_c, b_c = aug.split()
                ra = list(r_c.getdata())
                ga = list(g_c.getdata())
                ba = list(b_c.getdata())
                nr: list = []
                ng: list = []
                nb: list = []
                for rv, gv, bv in zip(ra, ga, ba):
                    h, s, v = colorsys.rgb_to_hsv(rv / 255, gv / 255, bv / 255)
                    r2, g2, b2 = colorsys.hsv_to_rgb((h + hd) % 1.0, s, v)
                    nr.append(int(r2 * 255))
                    ng.append(int(g2 * 255))
                    nb.append(int(b2 * 255))
                ar = _PILImage.new("L", aug.size); ar.putdata(nr)
                ag = _PILImage.new("L", aug.size); ag.putdata(ng)
                ab = _PILImage.new("L", aug.size); ab.putdata(nb)
                aug = _PILImage.merge("RGB", (ar, ag, ab))
            except Exception:
                pass
        self._aug_tk_orig = _PILImageTk.PhotoImage(self._pil_fit(orig, 420, 360))
        self._aug_tk_aug  = _PILImageTk.PhotoImage(self._pil_fit(aug,  420, 360))
        self._aug_lbl_orig.config(image=self._aug_tk_orig)
        self._aug_lbl_aug.config(image=self._aug_tk_aug)
        self._aug_fname_lbl.config(
            text=f"{img_path.name}  ({orig.width}\xd7{orig.height})")

    @staticmethod
    def _pil_fit(img, max_w, max_h):
        w, h  = img.size
        scale = min(max_w / w, max_h / h, 1.0)
        if scale < 1.0:
            img = img.resize((int(w * scale), int(h * scale)), _PILImage.LANCZOS)
        return img

    # ── Analysis ──────────────────────────────────────────────────────────────

    def _analyze_results(self):
        csv_path = None
        if self._output_dir:
            p = Path(self._output_dir) / "results.csv"
            if p.exists():
                csv_path = p
        if csv_path is None:
            p = filedialog.askopenfilename(
                title="Chọn file results.csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialdir=self._out_var.get().strip() or ".")
            if not p:
                return
            csv_path = Path(p)
        rows = []
        try:
            with open(csv_path, newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    rows.append({k.strip(): v.strip() for k, v in row.items()})
        except Exception as exc:
            messagebox.showerror("Lỗi đọc CSV", str(exc), parent=self)
            return
        if not rows:
            messagebox.showwarning(
                "Kh\xf4ng c\xf3 dữ liệu",
                "File results.csv trống.", parent=self)
            return
        self._open_analysis_window(self._build_analysis_report(rows, csv_path))

    def _build_analysis_report(self, rows, csv_path):
        def gf(row, *keys):
            for k in keys:
                try:
                    v = float(row.get(k, ""))
                    if v == v:
                        return v
                except (ValueError, TypeError):
                    pass
            return float("nan")

        def isnan(x):
            return x != x

        n    = len(rows)
        data = [{"top1":   gf(r, "metrics/accuracy_top1") * 100,
                 "top5":   gf(r, "metrics/accuracy_top5") * 100,
                 "t_loss": gf(r, "train/loss"),
                 "v_loss": gf(r, "val/loss")} for r in rows]

        best    = max(data, key=lambda x: x["top1"] if not isnan(x["top1"]) else -1)
        last10  = [e for e in data[-10:]            if not isnan(e["top1"])]
        mid_s   = max(0, n // 2 - 5)
        mid10   = [e for e in data[mid_s:mid_s + 10] if not isnan(e["top1"])]

        def avg(lst, k):
            vs = [e[k] for e in lst if not isnan(e[k])]
            return sum(vs) / len(vs) if vs else float("nan")

        still_improving = (not isnan(avg(last10, "top1"))
                           and not isnan(avg(mid10, "top1"))
                           and avg(last10, "top1") > avg(mid10, "top1") + 0.5)
        last_vl = [e["v_loss"] for e in last10 if not isnan(e["v_loss"])]
        last_tl = [e["t_loss"] for e in last10 if not isnan(e["t_loss"])]
        overfit = (len(last_vl) >= 5
                   and last_vl[-1] - last_vl[0] > 0.01
                   and (last_tl[-1] - last_tl[0] < -0.005 if last_tl else False))
        last_t1 = [e["top1"] for e in last10 if not isnan(e["top1"])]
        plateau = len(last_t1) >= 5 and max(last_t1) - min(last_t1) < 0.5
        bt1, bt5 = best["top1"], best["top5"]

        def fmt(v, d=2):
            return f"{v:.{d}f}" if not isnan(v) else "—"

        SEP   = "=" * 62
        lines = [
            SEP,
            "  KZTEK YOLO-CLS – PH\xc2N T\xcdCH KẾT QUẢ TRAINING",
            SEP,
            f"  File   : {csv_path}",
            f"  Epochs : {n}",
            "",
            f"  {'BEST MODEL':╀58}",
            f"  Best Top-1  : {fmt(bt1)}%",
            f"  Best Top-5  : {fmt(bt5)}%",
            "",
        ]

        _sec_acc = "ĐÁNH GIÁ ACCURACY"
        lines.append(f"  {_sec_acc:-<58}")
        if not isnan(bt1):
            if bt1 >= 95:
                lines.append(f"  ✅ Top-1 {fmt(bt1)}%  XUẤT SẮc (≥95%)")
            elif bt1 >= 90:
                lines.append(f"  ✅ Top-1 {fmt(bt1)}%  TỐT (90–95%)")
            elif bt1 >= 80:
                lines.append(f"  ⚠  Top-1 {fmt(bt1)}%  KH\xc1 — cần cải thiện")
            else:
                lines.append(
                    f"  ❌ Top-1 {fmt(bt1)}%  THẤP —"
                    " cần th\xeam data hoặc model lớn hơn")
        if not isnan(bt5):
            if bt5 >= 99:
                lines.append(f"  ✅ Top-5 {fmt(bt5)}%  XUẤT SẮc")
            elif bt5 >= 95:
                lines.append(f"  ✅ Top-5 {fmt(bt5)}%  TỐT")
            else:
                lines.append(
                    f"  ⚠  Top-5 {fmt(bt5)}%  THẤP —"
                    " kiểm tra lại data/class")
        lines.append("")
        _sec_xu = "XU HướNG"
        lines.append(f"  {_sec_xu:-<58}")
        lines.append(
            "  ✅ Kh\xf4ng overfit" if not overfit
            else "  ⚠  OVERFIT: val loss tăng khi train loss giảm")
        if still_improving:
            lines.append(
                f"  \U0001f4c8 Vẫn đang cải thiện ở"
                f" ep{n} — n\xean train th\xeam epochs")
        elif plateau:
            lines.append(
                f"  \U0001f4ca Đ\xe3 hội tụ (plateau) —"
                " giới hạn cấu h\xecnh hiện tại")
        else:
            lines.append("  \U0001f4c9 Ổn định — training ho\xe0n tất b\xecnh thường")
        lines.append("")
        lines.append(f"  {'ĐỀ XUẤT CẢI THIỆN':╀58}")
        recs = []
        if not isnan(bt1) and bt1 < 85:
            recs.append((
                "❶ Th\xeam dữ liệu đa dạng",
                "Top-1 thấp — thu thập th\xeam ảnh đa dạng g\xf3c độ, \xe1nh s\xe1ng."))
            recs.append((
                "❷ Thử model lớn hơn",
                "Đổi yolo11n-cls → yolo11s-cls hoặc m-cls (+3–8% Top-1)."))
        if not isnan(bt1) and bt1 < 92:
            recs.append((
                "❸ Tăng Imgsz",
                "Thử imgsz=320 hoặc 448 để giữ chi tiết ảnh tốt hơn."))
        if still_improving and not overfit:
            recs.append((
                f"❹ Tăng epochs (đang cải thiện ở ep{n})",
                f"Thử epochs={int(n * 1.5)} để khai th\xe1c th\xeam tiềm năng."))
        if overfit:
            recs.append((
                "❺ Chống Overfit",
                "Tăng Weight Decay (0.001–0.005), bật Label Smoothing (0.1), "
                "hoặc Freeze=10."))
        if plateau and not isnan(bt1) and bt1 < 95:
            recs.append((
                "❻ Model đ\xe3 hội tụ — thử model lớn hơn hoặc bổ sung data",
                "Model hiện tại đ\xe3 đạt giới hạn với tập data hiện c\xf3."))
        if not recs:
            recs.append((
                "✅ Kết quả rất tốt!",
                "Kh\xf4ng c\xf3 đề xuất đặc biệt — model hoạt động ổn định."))
        recs.append((
            "\U0001f4a1 N\xe2ng cấp nhanh nhất",
            "yolo11n-cls → yolo11s-cls: 1 d\xf2ng code, tăng Top-1 trung b\xecnh 3–7%."))
        for title, desc in recs:
            lines.append(f"\n  {title}")
            for dl in desc.split("\n"):
                lines.append(f"  {dl}")
        lines += [
            "",
            SEP,
            f"  Ph\xe2n t\xedch tạo l\xfac: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            SEP,
        ]
        return "\n".join(lines)

    def _open_analysis_window(self, report_text):
        win = Toplevel(self.root)
        win.title("KZTEK Classifier – Ph\xe2n t\xedch kết quả")
        win.geometry("740x560")
        win.configure(bg=BG)
        win.resizable(True, True)
        win.protocol("WM_DELETE_WINDOW", win.destroy)

        tb = Frame(win, bg=CARD, padx=8, pady=6)
        tb.pack(fill=X)
        Label(tb, text="Ph\xe2n t\xedch & Đề xuất cải thiện",
              bg=CARD, fg=TEXT, font=F_BOLD).pack(side=LEFT)

        def _save():
            path = filedialog.asksaveasfilename(
                title="Lưu b\xe1o c\xe1o", defaultextension=".txt",
                filetypes=[("Text file", "*.txt")], initialfile="cls_analysis.txt")
            if not path:
                return
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(report_text)
                messagebox.showinfo(
                    "Đ\xe3 lưu", f"Lưu tại:\n{path}", parent=win)
            except Exception as exc:
                messagebox.showerror("Lỗi", str(exc), parent=win)

        Button(tb, text="\U0001f4be  Lưu file", command=_save,
               bg=ACCENT, fg="white", activebackground=ACCENT2, activeforeground="white",
               font=F_MAIN, relief="flat", padx=10, cursor="hand2").pack(side=RIGHT)

        tf = Frame(win, bg=BG)
        tf.pack(fill=BOTH, expand=True, padx=8, pady=(4, 8))
        vsb = Scrollbar(tf, orient=VERTICAL)
        vsb.pack(side=RIGHT, fill=Y)
        hsb = Scrollbar(tf, orient=HORIZONTAL)
        hsb.pack(side=BOTTOM, fill=X)
        txt = Text(tf, bg="#16162a", fg=TEXT, font=("Consolas", 9),
                   relief="flat", wrap=NONE, padx=10, pady=8,
                   yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        txt.pack(fill=BOTH, expand=True)
        vsb.config(command=txt.yview)
        hsb.config(command=txt.xview)
        txt.tag_config("hdr",  foreground=ACCENT,  font=("Consolas", 9, "bold"))
        txt.tag_config("sec",  foreground=ACCENT2)
        txt.tag_config("good", foreground=SUCCESS)
        txt.tag_config("warn", foreground="#f0c040")
        txt.tag_config("bad",  foreground="#f05050")
        txt.tag_config("tip",  foreground="#4fc3f7")
        for line in report_text.split("\n"):
            if "=" * 10 in line or "KZTEK" in line or "PH\xc2N T\xcdCH" in line:
                txt.insert(END, line + "\n", "hdr")
            elif "─" * 8 in line:
                txt.insert(END, line + "\n", "sec")
            elif "✅" in line or "XUẤT SẮc" in line:
                txt.insert(END, line + "\n", "good")
            elif "⚠" in line or "KH\xc1" in line or "\U0001f4c8" in line:
                txt.insert(END, line + "\n", "warn")
            elif "❌" in line or "THẤP" in line or "OVERFIT" in line:
                txt.insert(END, line + "\n", "bad")
            elif any(c in line for c in
                     ("\U0001f4a1", "❶", "❷", "❸", "❹", "❺", "❻")):
                txt.insert(END, line + "\n", "tip")
            else:
                txt.insert(END, line + "\n")
        txt.config(state=DISABLED)
        win.lift()
        win.focus_set()
        win.bind("<Escape>", lambda _: win.destroy())

    # ── Export ONNX ───────────────────────────────────────────────────────────

    def _export_onnx(self):
        best = os.path.join(self._output_dir, "weights", "best.pt")
        if not os.path.isfile(best):
            p = filedialog.askopenfilename(
                title="Chọn best.pt để export ONNX",
                filetypes=[("PyTorch model", "*.pt")],
                initialdir=self._output_dir or self._out_var.get().strip() or ".")
            if not p:
                return
            best = p
        _append_log(self._log, f"⬡  Export ONNX: {best}")
        script = (
            "import sys\nfrom ultralytics import YOLO\n"
            f"model = YOLO({best!r})\n"
            "path = model.export(format='onnx')\n"
            "print(f'ONNX_DONE: {path}')\n"
        )
        tmp = tempfile.NamedTemporaryFile(
            suffix=".py", delete=False, mode="w", encoding="utf-8")
        tmp.write(script)
        tmp.close()
        cf = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

        def _run():
            try:
                proc = subprocess.Popen(
                    [sys.executable, tmp.name],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace", creationflags=cf)
                out, _ = proc.communicate()
                for line in out.splitlines():
                    if line.strip():
                        self.root.after(
                            0, lambda l=line.strip(): _append_log(self._log, f"   {l}"))
                if "ONNX_DONE:" in out:
                    onnx_path = out.split("ONNX_DONE:", 1)[1].strip().split("\n")[0]
                    self.root.after(
                        0, lambda: _append_log(
                            self._log,
                            f"✔  ONNX đ\xe3 lưu tại: {onnx_path}"))
                    self.root.after(
                        0, lambda: messagebox.showinfo(
                            "Export ONNX",
                            f"Đ\xe3 export th\xe0nh c\xf4ng:\n{onnx_path}",
                            parent=self))
                else:
                    self.root.after(
                        0, lambda: _append_log(
                            self._log,
                            "[LỖI] Export ONNX thất bại — xem log ph\xeda tr\xean."))
            finally:
                try:
                    os.unlink(tmp.name)
                except OSError:
                    pass

        threading.Thread(target=_run, daemon=True).start()

    # ── Shortcut aliases ───────────────────────────────────────────────────────

    def _start_action(self):
        self._start_train()

    def _stop(self):
        self._stop_train()

    # ── Miss Classification Analysis ──────────────────────────────────────────

    def _open_miss_analysis(self):
        """Cửa sổ phân tích ảnh bị phân loại sai (Misclassification) theo class."""
        if self._miss_win and self._miss_win.winfo_exists():
            self._miss_win.lift()
            return

        win = Toplevel(self.root)
        win.title("KZTEK Classifier – Miss Analysis")
        win.geometry("780x600")
        win.configure(bg=BG)
        win.resizable(True, True)
        win.protocol("WM_DELETE_WINDOW", win.destroy)
        self._miss_win = win

        # ── Config ────────────────────────────────────────────────────
        cfg = Frame(win, bg=CARD, padx=12, pady=10)
        cfg.pack(fill=X, padx=8, pady=(8, 4))
        cfg.columnconfigure(1, weight=1)

        Label(cfg, text="Phân tích ảnh bị phân loại sai (Misclassification) theo class",
              bg=CARD, fg=TEXT, font=F_BOLD).grid(
                  row=0, column=0, columnspan=3, sticky=W, pady=(0, 8))

        miss_model_var = StringVar()
        best_pt = os.path.join(self._output_dir, "weights", "best.pt") if self._output_dir else ""
        if best_pt and os.path.isfile(best_pt):
            miss_model_var.set(best_pt)

        miss_val_var = StringVar()
        # Try to find val folder inside output_dir
        if self._output_dir:
            cands = [Path(self._output_dir) / "dataset" / "val",
                     Path(self._output_dir) / "val"]
            for c in cands:
                if c.is_dir():
                    miss_val_var.set(str(c))
                    break

        def _pick_model():
            p = filedialog.askopenfilename(
                title="Chọn model .pt",
                filetypes=[("PyTorch model", "*.pt"), ("All", "*.*")],
                initialdir=str(Path(miss_model_var.get()).parent)
                           if miss_model_var.get() and os.path.isfile(miss_model_var.get()) else ".")
            if p:
                miss_model_var.set(p)

        def _pick_val():
            p = filedialog.askdirectory(title="Chọn thư mục val (chứa class subfolder)",
                                        initialdir=miss_val_var.get() or ".")
            if p:
                miss_val_var.set(p)

        for row, (lbl_txt, var, cmd) in enumerate([
            ("Model (.pt):", miss_model_var, _pick_model),
            ("Val folder:",  miss_val_var,   _pick_val),
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
        pr.grid(row=3, column=0, columnspan=3, sticky=W, pady=(8, 0))
        miss_conf_var = StringVar(value="0.25")
        miss_max_var  = StringVar(value="60")
        for lbl_t, var, w in [("Conf:", miss_conf_var, 6),
                               ("Max save/class:", miss_max_var, 5)]:
            Label(pr, text=lbl_t, bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
            Entry(pr, textvariable=var, bg="#16162a", fg=TEXT,
                  insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4,
                  width=w).pack(side=LEFT, padx=(4, 14))
        Label(pr, text="(ảnh sai sẽ lưu vào missed_analysis/ bên cạnh val folder)",
              bg=CARD, fg=DIM, font=("Segoe UI", 7, "italic")).pack(side=LEFT)

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
        cols = ("cls", "total", "correct", "wrong", "acc", "top_wrong")
        miss_tree = ttk.Treeview(res_f, columns=cols, show="headings",
                                  style="Dark.Treeview", height=10)
        for col, hdr, w, anc in [
            ("cls",       "Class",         140, W),
            ("total",     "Tổng",           70, CENTER),
            ("correct",   "Đúng",           70, CENTER),
            ("wrong",     "Sai",            70, CENTER),
            ("acc",       "Accuracy %",     90, CENTER),
            ("top_wrong", "Hay nhầm sang", 250, W),
        ]:
            miss_tree.heading(col, text=hdr)
            miss_tree.column(col, width=w, anchor=anc,
                             stretch=(col in ("cls", "top_wrong")))
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
            val_dir    = miss_val_var.get().strip()
            if not model_path or not os.path.isfile(model_path):
                messagebox.showwarning("Thiếu model", "Chọn file model .pt hợp lệ.", parent=win)
                return
            if not val_dir or not os.path.isdir(val_dir):
                messagebox.showwarning("Thiếu val folder",
                                       "Chọn thư mục val chứa class subfolder.", parent=win)
                return
            try:
                conf_v   = float(miss_conf_var.get())
                max_save = int(miss_max_var.get())
            except ValueError:
                conf_v, max_save = 0.25, 60
            out_dir = os.path.normpath(
                os.path.join(val_dir, "..", "missed_analysis"))
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
                args=(model_path, val_dir, out_dir, conf_v, max_save,
                      miss_pb, miss_status, miss_tree, sum_lbl,
                      miss_run_btn, miss_open_btn),
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

    def _run_miss_analysis(self, model_path, val_dir, out_dir, conf,
                            max_save, pb, status_lbl, tree, sum_lbl,
                            run_btn, open_btn):
        """Thread: predict từng class subfolder → phân tích miss → lưu ảnh sai."""
        def _ui(fn):
            self.root.after(0, fn)

        try:
            from ultralytics import YOLO as _YOLO
        except ImportError as exc:
            _ui(lambda e=str(exc): status_lbl.config(text=f"Lỗi import: {e}", fg="#f05050"))
            _ui(lambda: run_btn.config(state=NORMAL))
            return

        _ui(lambda: status_lbl.config(text="Đang load model…", fg=ACCENT))
        try:
            model = _YOLO(model_path)
        except Exception as exc:
            _ui(lambda e=str(exc): status_lbl.config(text=f"Lỗi load model: {e}", fg="#f05050"))
            _ui(lambda: run_btn.config(state=NORMAL))
            return

        _EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
        val_path = Path(val_dir)
        classes  = sorted([d.name for d in val_path.iterdir()
                           if d.is_dir() and not d.name.startswith(".")])

        if not classes:
            _ui(lambda: status_lbl.config(text="Không tìm thấy class subfolder!", fg="#f0c040"))
            _ui(lambda: run_btn.config(state=NORMAL))
            return

        # {cls_name: {total, correct, wrong_preds: Counter, wrong_imgs: list}}
        from collections import Counter
        stats = {c: {"total": 0, "correct": 0,
                     "wrong_preds": Counter(), "wrong_imgs": []}
                 for c in classes}

        total_imgs = sum(
            sum(1 for f in (val_path / c).iterdir()
                if f.is_file() and f.suffix.lower() in _EXTS)
            for c in classes)

        done_count = [0]
        import os as _os, shutil as _shutil, time as _time

        def _fmt_sec(s):
            s = int(s)
            return f"{s//3600}h{(s%3600)//60:02d}m" if s >= 3600 else f"{s//60}m{s%60:02d}s"

        t_start = _time.monotonic()
        _os.makedirs(out_dir, exist_ok=True)

        for cls_name in classes:
            cls_dir = val_path / cls_name
            imgs = [p for p in cls_dir.iterdir()
                    if p.is_file() and p.suffix.lower() in _EXTS]
            if not imgs:
                continue

            elapsed = _time.monotonic() - t_start
            _ui(lambda c=cls_name, el=elapsed: status_lbl.config(
                text=f"Class: {c}  ⏱ {_fmt_sec(el)}", fg=DIM))

            BATCH = 32
            for i in range(0, len(imgs), BATCH):
                batch = imgs[i:i+BATCH]
                try:
                    results = model(batch, conf=conf, verbose=False)
                except Exception:
                    done_count[0] += len(batch)
                    continue

                for img_path, result in zip(batch, results):
                    stats[cls_name]["total"] += 1
                    done_count[0] += 1
                    # Get top-1 prediction
                    if (result.probs is not None and
                            result.probs.top1 is not None):
                        pred_idx  = int(result.probs.top1)
                        pred_name = result.names.get(pred_idx, str(pred_idx))
                        if pred_name == cls_name:
                            stats[cls_name]["correct"] += 1
                        else:
                            stats[cls_name]["wrong_preds"][pred_name] += 1
                            if len(stats[cls_name]["wrong_imgs"]) < max_save:
                                stats[cls_name]["wrong_imgs"].append(
                                    (str(img_path), pred_name,
                                     float(result.probs.top1conf)
                                     if result.probs.top1conf is not None else 0.0))
                    else:
                        stats[cls_name]["wrong_preds"]["<no_pred>"] += 1

                pct     = min(99, int(done_count[0] / max(total_imgs, 1) * 100))
                elapsed = _time.monotonic() - t_start
                eta     = (elapsed / done_count[0] * (total_imgs - done_count[0])
                           if done_count[0] > 0 else 0)
                _ui(lambda v=pct: pb.config(value=v))
                _ui(lambda d=done_count[0], el=elapsed, et=eta: status_lbl.config(
                    text=f"Inference {d}/{total_imgs} ({d*100//max(total_imgs,1)}%)"
                         f"  ⏱ {_fmt_sec(el)} / ETA {_fmt_sec(et)}",
                    fg=DIM))

        # Save wrong images
        _ui(lambda: status_lbl.config(text="Đang lưu ảnh sai…", fg=DIM))
        for cls_name, s in stats.items():
            if not s["wrong_imgs"]:
                continue
            cls_out = _os.path.join(out_dir, cls_name + "_wrong")
            _os.makedirs(cls_out, exist_ok=True)
            for img_path, pred_name, pred_conf in s["wrong_imgs"]:
                try:
                    stem = Path(img_path).stem
                    ext  = Path(img_path).suffix
                    dst  = _os.path.join(cls_out,
                                         f"{stem}_pred_{pred_name}_{pred_conf:.2f}{ext}")
                    _shutil.copy2(img_path, dst)
                except Exception:
                    pass

        def _refresh_tree():
            for iid in tree.get_children():
                tree.delete(iid)
            parts = []
            for cls_name in sorted(classes):
                s     = stats[cls_name]
                tot   = s["total"]
                corr  = s["correct"]
                wrong = tot - corr
                acc   = corr / tot * 100 if tot else 0.0
                # top confused classes
                top_wrong = s["wrong_preds"].most_common(3)
                tw_str = ", ".join(f"{k}×{v}" for k, v in top_wrong) if top_wrong else "—"
                tag = "ok" if acc >= 90 else ("warn" if acc >= 75 else "bad")
                tree.insert("", END,
                            values=(cls_name, tot, corr, wrong,
                                    f"{acc:.1f}%", tw_str),
                            tags=(tag,))
                parts.append(f"{cls_name}: {acc:.1f}%")
            sum_lbl.config(
                text="  Accuracy — " + "   |   ".join(parts) if parts else "",
                fg=DIM)
            pb.config(value=100)
            elapsed_total = _time.monotonic() - t_start
            status_lbl.config(
                text=f"✔  Hoàn tất trong {_fmt_sec(elapsed_total)} — ảnh lưu tại: {out_dir}",
                fg=SUCCESS)
            run_btn.config(state=NORMAL)
            open_btn.config(state=NORMAL)

        _ui(_refresh_tree)
