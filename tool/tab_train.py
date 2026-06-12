import csv
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

from .constants import (BG, CARD, ACCENT, ACCENT2, TEXT, DIM, SUCCESS,
                         F_MAIN, F_BOLD, IMAGE_EXTENSIONS)
from .settings import _bind_cfg, _cfg_dir
from .ui_helpers import _folder_row, _make_logbox, _append_log

try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    _MPL_OK = True
except ImportError:
    _MPL_OK = False

_VAL_FG  = "#4fc3f7"
_EXCL_FG = DIM

# chart palette
_C_BOX  = "#F05922"
_C_CLS  = "#B8B3D6"
_C_DFL  = _VAL_FG
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
        self._split_ratio_var = IntVar(value=90)
        self._recursive_var   = BooleanVar(value=False)
        _bind_cfg("train.project", self._project_var)

        self._proc       = None
        self._out_queue  = queue.Queue()
        self._poll_id    = None
        self._output_dir  = ""
        self._chart_poll_id = None

        # subfolder data
        self._sf_data: dict = {}

        # chart window
        self._chart_win    = None
        self._fig          = None
        self._axes         = None
        self._mpl_canvas   = None

        self._build()

    # ── Layout ────────────────────────────────────────────────────────────

    def _build(self):
        top = Frame(self, bg=CARD, padx=12, pady=10)
        top.pack(fill=X)
        g = Frame(top, bg=CARD)
        g.pack(fill=X)
        g.columnconfigure(1, weight=1)
        _folder_row(g, "Thư mục train :", self.train_dir, 0, bg=CARD)
        _folder_row(g, "Thư mục val   :", self.val_dir,   1, bg=CARD)

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
        Entry(g, textvariable=self._labels_var, bg=CARD, fg=TEXT,
              insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4).grid(
                  row=3, column=1, sticky=EW, padx=(8, 8))
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
        mc = ttk.Combobox(pf, textvariable=self._model_var, width=13,
                          state="readonly", font=F_MAIN,
                          values=[m for m, _ in self._MODELS])
        mc.grid(row=1, column=1, sticky=W, padx=(4, 16))
        mc.current(0)
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
        Entry(pr, textvariable=self._project_var, bg="#16162a", fg=TEXT,
              insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4, width=30).pack(side=LEFT)
        Button(pr, text="…",
               command=lambda: (p := filedialog.askdirectory(
                   initialdir=_cfg_dir("train.project"))) and self._project_var.set(p),
               bg=ACCENT2, fg="white", font=F_MAIN, relief="flat",
               padx=8, cursor="hand2").pack(side=LEFT, padx=(4, 16))
        Label(pr, text="Run name:", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        Entry(pr, textvariable=self._name_var, bg="#16162a", fg=TEXT,
              insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4, width=18).pack(
                  side=LEFT, padx=(4, 0))

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

        self._status_lbl = Label(ctrl, text="", bg=BG, fg=DIM, font=F_MAIN)
        self._status_lbl.pack(side=LEFT, padx=16)

        log_frame, self._log = _make_logbox(self)
        log_frame.pack(fill=BOTH, expand=True, padx=12, pady=(2, 0))

        res = Frame(self, bg=CARD, padx=12, pady=6)
        res.pack(fill=X, padx=12, pady=(2, 8))
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
            (root / "images" / split).mkdir(parents=True, exist_ok=True)
            (root / "labels" / split).mkdir(parents=True, exist_ok=True)
            for img in imgs:
                self._link_or_copy(img, root / "images" / split / img.name)
                lbl = img.with_suffix(".txt")
                if not lbl.exists():
                    lbl = img.parent.parent / "labels" / (img.stem + ".txt")
                if lbl.exists():
                    self._link_or_copy(lbl, root / "labels" / split / lbl.name)
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
        root      = self._build_dataset_dir({"train": train_imgs, "val": val_imgs})
        yaml_path = str(root / "data.yaml")
        with open(yaml_path, "w", encoding="utf-8") as f:
            f.write(f"path: {root}\ntrain: images/train\nval:   images/val\n"
                    f"nc: {nc}\nnames: [{names_str}]\n")
        return yaml_path, split_msg, len(train_imgs), len(val_imgs)

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

        # Toolbar
        tb = Frame(win, bg=CARD, padx=8, pady=4)
        tb.pack(fill=X)
        self._epoch_lbl = Label(tb, text="—", bg=CARD, fg=TEXT, font=F_BOLD)
        self._epoch_lbl.pack(side=LEFT)
        Button(tb, text="↻  Làm mới", command=self._update_charts,
               bg=ACCENT2, fg="white", activebackground=ACCENT, activeforeground="white",
               font=F_MAIN, relief="flat", padx=10, cursor="hand2").pack(side=RIGHT)

        # Figure
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
                if any(v == v for v in vals):   # any non-NaN
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
        """Refresh chart every 5 s while training — independent of stdout queue."""
        self._update_charts()
        self._chart_poll_id = self.root.after(5000, self._start_chart_poll)

    def _stop_chart_poll(self):
        if self._chart_poll_id:
            self.root.after_cancel(self._chart_poll_id)
            self._chart_poll_id = None

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

        try:
            yaml_path, split_msg, n_train, n_val = self._write_yaml(labels)
        except Exception as e:
            messagebox.showerror("Lỗi tạo data.yaml", str(e)); return

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
            f"    results = model.train(\n"
            f"        data={yaml_path!r},\n"
            f"        epochs={epochs},\n"
            f"        imgsz={imgsz},\n"
            f"        batch={batch},\n"
            f"        device={device!r},\n"
            f"        project={project!r},\n"
            f"        name={name!r},\n"
            f"        exist_ok=True,\n"
            f"    )\n"
            "    print(f'KZTEK_SAVE_DIR: {results.save_dir}')\n"
        )
        tmp_script = Path(tempfile.gettempdir()) / "kztek_train_job.py"
        tmp_script.write_text(script, encoding="utf-8")

        self._log.configure(state=NORMAL)
        self._log.delete("1.0", END)
        self._log.configure(state=DISABLED)
        _append_log(self._log,
            f"▶  model={model}  epochs={epochs}  imgsz={imgsz}  "
            f"batch={batch}  device={device}")
        _append_log(self._log, f"   data.yaml : {yaml_path}")
        _append_log(self._log, f"   dataset   : {n_train} train / {n_val} val")
        if split_msg:
            _append_log(self._log, f"   {split_msg}")
        _append_log(self._log, f"   output    : {project}/{name}")
        _append_log(self._log, "─" * 70)

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

        # Auto-open chart window and start refresh timer
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
                    continue        # don't print this internal marker
                # strip ANSI escape codes
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
                rc = 0          # stdout EOF = process finished normally
        self._proc = None
        if self._poll_id:
            self.root.after_cancel(self._poll_id); self._poll_id = None
        self._btn_start.config(state=NORMAL)
        self._btn_stop.config(state=DISABLED)
        if rc == 0:
            best = os.path.join(self._output_dir, "weights", "best.pt")
            _append_log(self._log, "─" * 70)
            _append_log(self._log, f"✔  Hoàn tất!  best.pt → {best}")
            self._status_lbl.config(text="✔ Hoàn tất", fg=SUCCESS)
            self._result_lbl.config(text=f"best.pt  →  {best}")
            self._open_btn.config(state=NORMAL)
            self._update_charts()   # final refresh
        else:
            _append_log(self._log, f"[LỖI]  Tiến trình kết thúc với exit code {rc}")
            self._status_lbl.config(text=f"Lỗi (exit {rc})", fg="#f05050")

    def _open_output_dir(self):
        d = self._output_dir
        if os.path.isdir(d):
            subprocess.Popen(["explorer", os.path.normpath(d)])
        else:
            messagebox.showinfo("Thông báo", f"Thư mục chưa tồn tại:\n{d}")
