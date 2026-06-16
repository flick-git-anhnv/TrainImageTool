import os
import queue
import re
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from tkinter import *
from tkinter import filedialog, messagebox, ttk

from ...core.constants import (BG, CARD, ACCENT, ACCENT2, TEXT, DIM, SUCCESS,
                                F_MAIN, F_BOLD, F_MONO)
from ...core.settings import (_bind_cfg, _bind_history,
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


# ── Embedded training script — runs as subprocess ───────────────────────────
_TRAIN_SCRIPT = r"""
import argparse
import logging
import os
import random
import shutil
import sys
from pathlib import Path

# Tắt output thừa của YOLO / tqdm
os.environ.setdefault("YOLO_VERBOSE", "False")
logging.getLogger("ultralytics").setLevel(logging.WARNING)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root",    required=True)
    ap.add_argument("--output",  required=True)
    ap.add_argument("--model",   default="yolo11n-cls.pt")
    ap.add_argument("--epochs",  type=int,   default=50)
    ap.add_argument("--batch",   type=int,   default=32)
    ap.add_argument("--lr0",     type=float, default=0.01)
    ap.add_argument("--workers", type=int,   default=4)
    ap.add_argument("--device",  default="")
    ap.add_argument("--split",   type=float, default=0.8)
    ap.add_argument("--imgsz",   type=int,   default=224)
    ap.add_argument("--name",    default="classifier")
    args = ap.parse_args()

    try:
        from ultralytics import YOLO
    except ImportError:
        print("__ERR__ Thieu ultralytics. Cai: pip install ultralytics", flush=True)
        sys.exit(1)

    root_dir = Path(args.root)
    out_dir  = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── Detect / auto-split ───────────────────────────────────────────
    train_dir = root_dir / "train"
    val_dir   = root_dir / "val"

    if train_dir.is_dir() and val_dir.is_dir():
        data_dir = root_dir
        print(f"__FOUND_SPLIT__ train:{train_dir} val:{val_dir}", flush=True)
    else:
        _EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
        classes = sorted([d.name for d in root_dir.iterdir()
                          if d.is_dir() and d.name not in ("train", "val")])
        if not classes:
            print("__ERR__ Khong tim thay thu muc class nao trong root folder", flush=True)
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
            n_tr = max(1, int(len(imgs) * args.split))
            tr_imgs = imgs[:n_tr]
            va_imgs = imgs[n_tr:]

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
        print(
            f"__AUTO_SPLIT__ classes:{len(classes)}"
            f" train:{n_tr_total} val:{n_va_total} ratio:{pct}%",
            flush=True,
        )

    # ── Dataset info ──────────────────────────────────────────────────
    _EXTS2 = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    tr_sub = data_dir / "train"
    va_sub = data_dir / "val"
    cls_names = sorted([d.name for d in tr_sub.iterdir() if d.is_dir()])
    n_tr = sum(1 for f in tr_sub.rglob("*") if f.suffix.lower() in _EXTS2)
    n_va = sum(1 for f in va_sub.rglob("*") if f.suffix.lower() in _EXTS2)
    print(f"__CLASSES__ {len(cls_names)} {' '.join(cls_names)}", flush=True)
    print(f"__SIZES__ train:{n_tr} val:{n_va}", flush=True)

    # ── YOLO model + callbacks ────────────────────────────────────────
    model = YOLO(args.model)

    best_top1 = [0.0]

    def on_train_start(trainer):
        dev = str(getattr(trainer, "device", "?"))
        print(f"__DEVICE__ {dev}", flush=True)

    def on_fit_epoch_end(trainer):
        ep    = trainer.epoch + 1
        total = trainer.epochs

        # Training loss
        try:
            tl = trainer.tloss
            if hasattr(tl, "__len__"):
                loss = float(tl[-1])
            else:
                loss = float(tl)
        except Exception:
            loss = 0.0

        # Val metrics (accuracy_top1 / top5 are in [0,1])
        metrics = getattr(trainer, "metrics", {}) or {}
        top1 = float(metrics.get("metrics/accuracy_top1",
                     metrics.get("accuracy_top1", 0))) * 100
        top5 = float(metrics.get("metrics/accuracy_top5",
                     metrics.get("accuracy_top5", 0))) * 100

        # LR
        try:
            lr = trainer.optimizer.param_groups[0]["lr"]
        except Exception:
            lr = 0.0

        print(
            f"__EPOCH__ {ep}/{total}"
            f" train_loss:{loss:.4f}"
            f" top1:{top1:.2f}"
            f" top5:{top5:.2f}"
            f" lr:{lr:.6f}",
            flush=True,
        )

        if top1 > best_top1[0]:
            best_top1[0] = top1
            print(f"__BEST__ epoch:{ep} top1:{top1:.2f}", flush=True)

    model.add_callback("on_train_start",    on_train_start)
    model.add_callback("on_fit_epoch_end",  on_fit_epoch_end)

    model.train(
        data=str(data_dir),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        lr0=args.lr0,
        workers=args.workers,
        device=args.device,
        project=str(out_dir),
        name=args.name,
        exist_ok=True,
        verbose=False,
        plots=False,
    )

    best = out_dir / args.name / "weights" / "best.pt"
    print(
        f"__DONE__ epochs:{args.epochs}"
        f" best_top1:{best_top1[0]:.2f}"
        f" best:{best}",
        flush=True,
    )


if __name__ == "__main__":
    main()
"""

_PRESET_MODELS = [
    "yolo11n-cls.pt",
    "yolo11s-cls.pt",
    "yolo11m-cls.pt",
    "yolo11l-cls.pt",
    "yolo11x-cls.pt",
]


class ClassifierTrainTab(Frame):
    """Tab huấn luyện Image Classifier dùng YOLO11 classification."""

    def __init__(self, master, root):
        super().__init__(master, bg=BG)
        self.root = root

        self._proc:        subprocess.Popen | None = None
        self._q            = queue.Queue()
        self._tmp_script:  str | None = None
        # (epoch, train_loss, top1, top5)
        self._epoch_data: list = []

        # ── Vars ──────────────────────────────────────────────────────
        self._root_var    = StringVar()
        self._out_var     = StringVar()
        self._model_var   = StringVar(value="yolo11n-cls.pt")
        self._epochs_var  = StringVar(value="50")
        self._batch_var   = StringVar(value="32")
        self._lr0_var     = StringVar(value="0.01")
        self._device_var  = StringVar(value="")
        self._workers_var = StringVar(value="4")
        self._imgsz_var   = StringVar(value="224")
        self._name_var    = StringVar(value="classifier")
        self._split_var   = IntVar(value=80)

        _bind_cfg("cls.root",    self._root_var)
        _bind_cfg("cls.out",     self._out_var)
        _bind_cfg("cls.model",   self._model_var)
        _bind_cfg("cls.epochs",  self._epochs_var)
        _bind_cfg("cls.batch",   self._batch_var)
        _bind_cfg("cls.lr0",     self._lr0_var)
        _bind_cfg("cls.device",  self._device_var)
        _bind_cfg("cls.workers", self._workers_var)
        _bind_cfg("cls.imgsz",   self._imgsz_var)
        _bind_cfg("cls.name",    self._name_var)
        _bind_cfg("cls.split",   self._split_var)

        self._build()

    # ── UI ────────────────────────────────────────────────────────────

    def _build(self):
        pad = {"padx": 12, "pady": 6}

        # ── Dataset ───────────────────────────────────────────────────
        ds = Frame(self, bg=CARD, padx=16, pady=12)
        ds.pack(fill=X, **pad)

        Label(ds, text="📁  Dataset", bg=CARD, fg=ACCENT, font=F_BOLD).grid(
            row=0, column=0, columnspan=4, sticky=W, pady=(0, 8))
        _folder_row(ds, "Root folder (chứa các class subfolder):",
                    self._root_var, 1, bg=CARD, history_key="h.cls.root")
        _folder_row(ds, "Output folder (lưu weights + auto-split):",
                    self._out_var,  2, bg=CARD, history_key="h.cls.out")
        Button(ds, text="🔍  Scan dataset", command=self._scan_dataset,
               bg=ACCENT2, fg="white", font=F_MAIN, relief=FLAT,
               padx=12, pady=4, cursor="hand2").grid(
                   row=3, column=0, columnspan=4, sticky=W, pady=(10, 0))

        # ── Dataset info ──────────────────────────────────────────────
        info_card = Frame(self, bg=CARD, padx=16, pady=10)
        info_card.pack(fill=X, **pad)
        Label(info_card, text="ℹ  Thông tin dataset",
              bg=CARD, fg=ACCENT, font=F_BOLD).pack(anchor=W)
        self._info_lbl = Label(
            info_card,
            text="Chọn Root folder và nhấn  Scan  để kiểm tra cấu trúc.",
            bg=CARD, fg=DIM, font=F_MAIN, justify=LEFT, anchor=W, wraplength=900)
        self._info_lbl.pack(anchor=W, pady=(4, 0))

        # ── Config ────────────────────────────────────────────────────
        cfg = Frame(self, bg=CARD, padx=16, pady=12)
        cfg.pack(fill=X, **pad)
        Label(cfg, text="⚙  Cài đặt huấn luyện",
              bg=CARD, fg=ACCENT, font=F_BOLD).grid(
                  row=0, column=0, columnspan=6, sticky=W, pady=(0, 10))

        # Row 1: Model (editable + browse) ─────────────────────────────
        Label(cfg, text="Model:", bg=CARD, fg=DIM, font=F_MAIN, anchor=W).grid(
            row=1, column=0, sticky=W, pady=4, padx=(0, 4))

        model_combo = ttk.Combobox(cfg, textvariable=self._model_var,
                                   values=_PRESET_MODELS,
                                   style="Dark.TCombobox", font=F_MAIN, width=20)
        model_combo.grid(row=1, column=1, sticky=W, pady=4)
        _bind_history("h.cls.model", model_combo)

        Button(cfg, text="Chọn .pt…", command=self._pick_model,
               bg=CARD, fg=TEXT, font=F_MAIN, relief=FLAT,
               padx=8, cursor="hand2").grid(row=1, column=2, padx=(4, 0))

        # Row 1 cont: Epochs, Batch ────────────────────────────────────
        self._add_field(cfg, "Epochs:",    self._epochs_var,  1, 3, width=7)
        self._add_field(cfg, "Batch:",     self._batch_var,   1, 5, width=7)

        # Row 2: lr0, device, workers, imgsz ──────────────────────────
        self._add_field(cfg, "LR0:",       self._lr0_var,     2, 0, width=10)
        self._add_field(cfg, "Device:",    self._device_var,  2, 2,
                        combo=True, vals=["", "cpu", "0", "1"], width=8)
        self._add_field(cfg, "Workers:",   self._workers_var, 2, 4, width=6)

        # Row 3: imgsz, name, split ────────────────────────────────────
        self._add_field(cfg, "Image size:", self._imgsz_var,  3, 0,
                        combo=True, vals=["224","256","320","384","448","512"], width=8)
        self._add_field(cfg, "Run name:",  self._name_var,    3, 2, width=14)

        sf = Frame(cfg, bg=CARD)
        sf.grid(row=3, column=4, columnspan=2, sticky=W, padx=(12, 0), pady=4)
        Label(sf, text="Split:", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        Spinbox(sf, from_=50, to=95, increment=5, textvariable=self._split_var,
                width=4, bg=CARD, fg=TEXT, insertbackground=TEXT,
                buttonbackground=ACCENT2, relief=FLAT, font=F_MAIN,
                state="readonly").pack(side=LEFT, padx=(4, 2))
        Label(sf, text="%  (áp dụng khi chưa có train/val)",
              bg=CARD, fg=DIM, font=("Segoe UI", 9)).pack(side=LEFT)

        # ── Actions ───────────────────────────────────────────────────
        act = Frame(self, bg=BG)
        act.pack(fill=X, padx=12, pady=(4, 4))

        self._btn_start = Button(
            act, text="▶  Bắt đầu huấn luyện  (F5)",
            command=self._start_train,
            bg=ACCENT, fg="white", font=F_BOLD,
            relief=FLAT, padx=18, pady=6, cursor="hand2")
        self._btn_start.pack(side=LEFT, padx=(0, 8))

        self._btn_stop = Button(
            act, text="■  Dừng  (Esc)",
            command=self._stop_train,
            bg=CARD, fg=TEXT, font=F_MAIN,
            relief=FLAT, padx=12, pady=6, cursor="hand2",
            state=DISABLED)
        self._btn_stop.pack(side=LEFT, padx=(0, 8))

        Button(act, text="📊  Biểu đồ",
               command=self._show_chart,
               bg=ACCENT2, fg="white", font=F_MAIN,
               relief=FLAT, padx=12, pady=6, cursor="hand2").pack(side=LEFT)

        # ── Progress ──────────────────────────────────────────────────
        pb_fr = Frame(self, bg=BG, padx=12)
        pb_fr.pack(fill=X)
        self._pb_lbl = Label(pb_fr, text="Sẵn sàng",
                             bg=BG, fg=DIM, font=F_MAIN)
        self._pb_lbl.pack(fill=X)
        self._pb = ttk.Progressbar(pb_fr,
                                   style="K.Horizontal.TProgressbar",
                                   maximum=100)
        self._pb.pack(fill=X, pady=(2, 8))

        # ── Log ───────────────────────────────────────────────────────
        log_fr, self._log = _make_logbox(self)
        log_fr.pack(fill=BOTH, expand=True, padx=12, pady=(0, 12))

    def _add_field(self, parent, lbl_txt, var, row, col,
                   combo=False, vals=None, width=12):
        Label(parent, text=lbl_txt, bg=CARD, fg=DIM, font=F_MAIN, anchor=W).grid(
            row=row, column=col, sticky=W,
            padx=(0 if col == 0 else 10, 4), pady=4)
        if combo and vals:
            ttk.Combobox(parent, textvariable=var, values=vals,
                         style="Dark.TCombobox", font=F_MAIN,
                         width=width, state="readonly").grid(
                             row=row, column=col + 1, sticky=W, pady=4)
        else:
            Entry(parent, textvariable=var,
                  bg=CARD, fg=TEXT, insertbackground=TEXT,
                  relief=FLAT, font=F_MAIN, bd=4, width=width).grid(
                      row=row, column=col + 1, sticky=W, pady=4)

    # ── Helpers ───────────────────────────────────────────────────────

    def _pick_model(self):
        p = filedialog.askopenfilename(
            title="Chọn model YOLO .pt",
            filetypes=[("Model file", "*.pt"), ("All files", "*.*")],
            initialdir=self._out_var.get() or None)
        if p:
            self._model_var.set(p)
            _push_history("h.cls.model", p)

    def _scan_dataset(self):
        root_path = Path(self._root_var.get().strip())
        if not root_path.is_dir():
            self._info_lbl.config(
                text="❌  Root folder không tồn tại.", fg="#f05050")
            return

        _EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

        def _count(d: Path) -> int:
            return sum(1 for f in d.rglob("*") if f.suffix.lower() in _EXTS)

        train_d = root_path / "train"
        val_d   = root_path / "val"

        if train_d.is_dir() and val_d.is_dir():
            classes = sorted([d.name for d in train_d.iterdir() if d.is_dir()])
            n_tr = _count(train_d)
            n_va = _count(val_d)
            self._info_lbl.config(
                fg=SUCCESS,
                text=(f"✅  Đã có train/val split sẵn\n"
                      f"Classes ({len(classes)}): {', '.join(classes) or '—'}\n"
                      f"Train: {n_tr} ảnh  |  Val: {n_va} ảnh"))
        else:
            cls_dirs = sorted([d for d in root_path.iterdir()
                               if d.is_dir() and d.name not in ("train", "val")])
            if not cls_dirs:
                self._info_lbl.config(
                    text="❌  Không tìm thấy thư mục class nào.", fg="#f05050")
                return

            counts = {d.name: _count(d) for d in cls_dirs}
            total  = sum(counts.values())
            ratio  = self._split_var.get() / 100
            est_tr = int(total * ratio)
            detail = "  |  ".join(f"{c}: {n}" for c, n in counts.items())
            self._info_lbl.config(
                fg="#f0c040",
                text=(f"⚠  Chưa có train/val — sẽ tự động split  "
                      f"{self._split_var.get()} / {100 - self._split_var.get()}\n"
                      f"Classes ({len(cls_dirs)}):  {detail}\n"
                      f"Tổng: {total} ảnh  →  Train ≈ {est_tr}  |  Val ≈ {total - est_tr}"))

        _append_log(self._log, f"✔  Scan xong: {root_path}")

    # ── Ctrl+O ────────────────────────────────────────────────────────

    def _browse(self):
        p = filedialog.askdirectory(initialdir=self._root_var.get() or None)
        if p:
            self._root_var.set(p)
            _push_history("h.cls.root", p)
            self._scan_dataset()

    # ── Train ─────────────────────────────────────────────────────────

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

        tmp = tempfile.NamedTemporaryFile(
            suffix=".py", delete=False, mode="w", encoding="utf-8")
        tmp.write(_TRAIN_SCRIPT)
        tmp.close()
        self._tmp_script = tmp.name

        try:
            epochs = int(self._epochs_var.get())
        except ValueError:
            epochs = 50

        self._epoch_data.clear()

        cf = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        self._proc = subprocess.Popen(
            [sys.executable, self._tmp_script,
             "--root",    root_dir,
             "--output",  out_dir,
             "--model",   self._model_var.get(),
             "--epochs",  str(epochs),
             "--batch",   self._batch_var.get(),
             "--lr0",     self._lr0_var.get(),
             "--device",  self._device_var.get(),
             "--workers", self._workers_var.get(),
             "--imgsz",   self._imgsz_var.get(),
             "--name",    self._name_var.get() or "classifier",
             "--split",   str(self._split_var.get() / 100),
            ],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            creationflags=cf)

        self._btn_start.config(state=DISABLED)
        self._btn_stop.config(state=NORMAL, bg=ACCENT)
        self._pb["value"] = 0
        self._pb_lbl.config(text="Đang khởi động...", fg=TEXT)

        model_name = Path(self._model_var.get()).name
        _append_log(self._log, f"✔  Bắt đầu — model: {model_name}")
        _append_log(self._log, f"   Root:   {root_dir}")
        _append_log(self._log, f"   Output: {out_dir}/{self._name_var.get()}")

        def _reader():
            for line in self._proc.stdout:
                self._q.put(line.rstrip())
            self._q.put("__PROC_END__")

        threading.Thread(target=_reader, daemon=True).start()
        self._poll_output()

    def _stop_train(self):
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            _append_log(self._log, "⚠  Đã dừng huấn luyện.")
            self._pb_lbl.config(text="Đã dừng.", fg=DIM)
        self._btn_start.config(state=NORMAL)
        self._btn_stop.config(state=DISABLED, bg=CARD)

    def _poll_output(self):
        try:
            while True:
                self._handle_line(self._q.get_nowait())
        except queue.Empty:
            pass
        if self._proc and self._proc.poll() is None:
            self.root.after(300, self._poll_output)

    def _handle_line(self, line: str):
        if line == "__PROC_END__":
            self._on_done()
            return

        if line.startswith("__ERR__"):
            _append_log(self._log, f"[LỖI] {line[7:].strip()}")

        elif line.startswith("__FOUND_SPLIT__"):
            _append_log(self._log, f"✔  Dùng split có sẵn: {line[15:].strip()}")

        elif line.startswith("__AUTO_SPLIT__"):
            _append_log(self._log, f"✔  Auto split: {line[14:].strip()}")

        elif line.startswith("__CLASSES__"):
            parts = line.split(maxsplit=2)
            nc    = parts[1] if len(parts) > 1 else "?"
            names = parts[2] if len(parts) > 2 else ""
            _append_log(self._log, f"✔  {nc} classes: {names}")

        elif line.startswith("__SIZES__"):
            _append_log(self._log, f"   Dataset: {line[9:].strip()}")

        elif line.startswith("__DEVICE__"):
            _append_log(self._log, f"   Device: {line[10:].strip()}")

        elif line.startswith("__EPOCH__"):
            rest = line[9:].strip()
            m = re.match(r"(\d+)/(\d+)", rest)
            if not m:
                return
            ep    = int(m.group(1))
            total = int(m.group(2))
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
            self._epoch_data.append((ep, tl, top1, top5))
            self._pb_lbl.config(
                text=(f"Epoch {ep}/{total}  —  "
                      f"top1: {top1:.1f}%  top5: {top5:.1f}%  loss: {tl:.4f}"),
                fg=TEXT)
            _append_log(self._log,
                f"   Epoch {ep:>3}/{total}"
                f"  loss={tl:.4f}"
                f"  top1={top1:.2f}%"
                f"  top5={top5:.2f}%"
                f"  lr={lr:.6f}")

        elif line.startswith("__BEST__"):
            _append_log(self._log, f"✔  Best: {line[8:].strip()}")

        elif line.startswith("__DONE__"):
            _append_log(self._log, f"✔  Hoàn thành! {line[8:].strip()}")
            self._pb["value"] = 100
            self._pb_lbl.config(text="✔  Huấn luyện hoàn tất!", fg=SUCCESS)

        else:
            if line.strip():
                _append_log(self._log, f"   {line}")

    def _on_done(self):
        if self._proc:
            self._proc.wait()
        self._btn_start.config(state=NORMAL)
        self._btn_stop.config(state=DISABLED, bg=CARD)
        if self._tmp_script:
            try:
                os.unlink(self._tmp_script)
            except OSError:
                pass
            self._tmp_script = None

    # ── Chart ─────────────────────────────────────────────────────────

    def _show_chart(self):
        if not _MPL_OK:
            messagebox.showinfo(
                "Thiếu thư viện",
                "Cài matplotlib để xem biểu đồ.\npip install matplotlib",
                parent=self)
            return
        if not self._epoch_data:
            messagebox.showinfo(
                "Chưa có dữ liệu",
                "Chưa có epoch nào được huấn luyện.",
                parent=self)
            return

        win = Toplevel(self.root)
        win.title("📊  YOLO Classifier — Training Curves")
        win.configure(bg=BG)
        win.resizable(True, True)
        win.protocol("WM_DELETE_WINDOW", win.destroy)
        win.geometry("900x460")

        epochs = [d[0] for d in self._epoch_data]
        t_loss = [d[1] for d in self._epoch_data]
        top1   = [d[2] for d in self._epoch_data]
        top5   = [d[3] for d in self._epoch_data]

        fig = Figure(figsize=(9, 4.2), dpi=96, facecolor=BG)
        ax1 = fig.add_subplot(1, 2, 1)
        ax2 = fig.add_subplot(1, 2, 2)

        for ax in (ax1, ax2):
            ax.set_facecolor(CARD)
            ax.tick_params(colors=DIM, labelsize=8)
            for sp in ax.spines.values():
                sp.set_color(DIM)

        ax1.plot(epochs, t_loss, color=ACCENT, linewidth=1.5, label="Train loss")
        ax1.set_title("Train Loss", color=TEXT, fontsize=10)
        ax1.set_xlabel("Epoch", color=DIM, fontsize=8)
        ax1.legend(fontsize=7, facecolor=CARD, labelcolor=TEXT)

        ax2.plot(epochs, top1, color=SUCCESS,    linewidth=1.5, label="Top-1 acc")
        ax2.plot(epochs, top5, color="#4fc3f7",  linewidth=1.5, label="Top-5 acc")
        ax2.set_title("Val Accuracy (%)", color=TEXT, fontsize=10)
        ax2.set_xlabel("Epoch", color=DIM, fontsize=8)
        ax2.legend(fontsize=7, facecolor=CARD, labelcolor=TEXT)

        fig.tight_layout(pad=2)
        cv = FigureCanvasTkAgg(fig, master=win)
        cv.get_tk_widget().pack(fill=BOTH, expand=True, padx=8, pady=8)
        cv.draw()

        win.bind("<Escape>", lambda _: win.destroy())
        win.lift()
        win.focus_set()
