import math
import os
import random
import shutil
import threading
from pathlib import Path
from tkinter import *
from tkinter import messagebox, ttk

from .constants import BG, CARD, ACCENT, ACCENT2, TEXT, DIM, F_MAIN, F_BOLD, IMAGE_EXTENSIONS, CLASS_NAMES
from .settings import _bind_cfg, _bind_history, _push_history, _get_history, _cfg_dir
from .ui_helpers import _folder_row, _pb_row, _make_logbox, _append_log, _set_progress, _action_btn


def _find_label_file(img_path: Path, labels_dir: Path, src_path: Path):
    """Tìm file label .txt tương ứng với ảnh, hỗ trợ nhiều cấu trúc thư mục."""
    stem = img_path.stem

    # 1. Cùng thư mục với ảnh
    candidate = img_path.parent / (stem + ".txt")
    if candidate.exists():
        return candidate

    # 2. labels_dir/<stem>.txt  (flat)
    candidate = labels_dir / (stem + ".txt")
    if candidate.exists():
        return candidate

    # 3. labels_dir/<relative_parent>/<stem>.txt  (mirror subfolder)
    try:
        rel = img_path.parent.relative_to(src_path)
        candidate = labels_dir / rel / (stem + ".txt")
        if candidate.exists():
            return candidate
    except ValueError:
        pass

    return None


class SplitTab(Frame):
    def __init__(self, master, root):
        super().__init__(master, bg=BG)
        self.root = root
        self._stop_event = threading.Event()
        self._build()

    # ------------------------------------------------------------------
    def _build(self):
        # ── Thư mục nguồn / đầu ra ────────────────────────────────────
        inp = Frame(self, bg=BG, padx=20, pady=14)
        inp.pack(fill=X)
        self.v_src = StringVar()
        self.v_out = StringVar()
        _bind_cfg("split.src", self.v_src)
        _bind_cfg("split.out", self.v_out)
        _folder_row(inp, "📁  Thư mục nguồn",             self.v_src, 0, history_key="h.split.src")
        _folder_row(inp, "💾  Thư mục đầu ra (tuỳ chọn)", self.v_out, 1, history_key="h.split.out")
        self.v_src.trace_add("write", lambda *_: self._update_preview())

        # ── Chế độ chia ───────────────────────────────────────────────
        mode_f = Frame(self, bg=BG, padx=20, pady=2)
        mode_f.pack(fill=X)
        Label(mode_f, text="Chế độ:", bg=BG, fg=DIM, font=F_MAIN).grid(
            row=0, column=0, sticky=W, padx=(0, 8))
        self.v_mode = StringVar(value="train")
        Radiobutton(mode_f, text="Train/Val (YOLO) — Chia theo folder",
                    variable=self.v_mode, value="train",
                    bg=BG, fg=TEXT, selectcolor=CARD, activebackground=BG, font=F_MAIN,
                    command=self._on_mode_change).grid(row=0, column=1, sticky=W, padx=(0, 12))
        Radiobutton(mode_f, text="Chia số lượng / part",
                    variable=self.v_mode, value="count",
                    bg=BG, fg=TEXT, selectcolor=CARD, activebackground=BG, font=F_MAIN,
                    command=self._on_mode_change).grid(row=0, column=2, sticky=W, padx=(0, 12))
        Radiobutton(mode_f, text="Chia tỷ lệ %",
                    variable=self.v_mode, value="ratio",
                    bg=BG, fg=TEXT, selectcolor=CARD, activebackground=BG, font=F_MAIN,
                    command=self._on_mode_change).grid(row=0, column=3, sticky=W)

        # ── Options row ───────────────────────────────────────────────
        opt = Frame(self, bg=BG, padx=20, pady=4)
        opt.pack(fill=X)

        # Train mode widgets
        self.train_opt_frame = Frame(opt, bg=BG)
        self.train_opt_frame.grid(row=0, column=0, sticky=W)
        Label(self.train_opt_frame, text="Tỷ lệ train/val:", bg=BG, fg=DIM,
              font=F_MAIN).grid(row=0, column=0, sticky=W, padx=(0, 8))
        self.v_train_ratio = StringVar(value="80/20")
        _tratio_combo = ttk.Combobox(self.train_opt_frame, textvariable=self.v_train_ratio,
                                      values=["80/20", "75/25", "70/30", "90/10"],
                                      width=10, style="Dark.TCombobox", font=F_MAIN)
        _tratio_combo.grid(row=0, column=1, sticky=W)
        _bind_history("h.split.train_ratio", _tratio_combo)
        self.v_train_ratio.trace_add("write", lambda *_: self._update_preview())

        # Count mode widgets
        self.count_frame = Frame(opt, bg=BG)
        self.count_frame.grid(row=0, column=0, sticky=W)
        Label(self.count_frame, text="Tối đa ảnh / folder:", bg=BG, fg=DIM,
              font=F_MAIN).grid(row=0, column=0, sticky=W, padx=(0, 8))
        self.v_max = IntVar(value=1000)
        Spinbox(self.count_frame, from_=10, to=100000, increment=100,
                textvariable=self.v_max,
                bg=CARD, fg=TEXT, insertbackground=TEXT, buttonbackground=ACCENT2,
                relief="flat", font=F_MAIN, width=8,
                command=self._update_preview).grid(row=0, column=1, sticky=W)
        self.v_max.trace_add("write", lambda *_: self._update_preview())
        self.count_frame.grid_remove()

        # Ratio mode widgets
        self.ratio_frame = Frame(opt, bg=BG)
        self.ratio_frame.grid(row=0, column=0, sticky=W)
        Label(self.ratio_frame, text="Tỷ lệ % (vd: 70/20/10):", bg=BG, fg=DIM,
              font=F_MAIN).grid(row=0, column=0, sticky=W, padx=(0, 8))
        self.v_ratio = StringVar(value="70/20/10")
        _ratio_combo = ttk.Combobox(self.ratio_frame, textvariable=self.v_ratio,
                                     width=14, style="Dark.TCombobox", font=F_MAIN)
        _ratio_combo.grid(row=0, column=1, sticky=W)
        _bind_history("h.split.ratio", _ratio_combo)
        self.v_ratio.trace_add("write", lambda *_: self._update_preview())
        self.ratio_frame.grid_remove()

        # Action (copy / move)
        Label(opt, text="   Hành động:", bg=BG, fg=DIM, font=F_MAIN).grid(
            row=0, column=2, sticky=W, padx=(24, 8))
        self.v_move = BooleanVar(value=False)
        for col, (lbl, val) in enumerate([("Sao chép", False), ("Di chuyển", True)]):
            Radiobutton(opt, text=lbl, variable=self.v_move, value=val,
                        bg=BG, fg=TEXT, selectcolor=CARD,
                        activebackground=BG, font=F_MAIN).grid(
                            row=0, column=3 + col, padx=(6 if col else 0, 0))

        # ── Duplicate handling ────────────────────────────────────────
        dup_f = Frame(self, bg=BG, padx=20, pady=2)
        dup_f.pack(fill=X)
        Label(dup_f, text="File trùng tên:", bg=BG, fg=DIM, font=F_MAIN).grid(
            row=0, column=0, sticky=W, padx=(0, 8))
        self.v_dup = StringVar(value="skip")
        Radiobutton(dup_f, text="Bỏ qua trùng", variable=self.v_dup, value="skip",
                    bg=BG, fg=TEXT, selectcolor=CARD, activebackground=BG,
                    font=F_MAIN).grid(row=0, column=1, sticky=W, padx=(0, 12))
        Radiobutton(dup_f, text="Ghi đè", variable=self.v_dup, value="overwrite",
                    bg=BG, fg=TEXT, selectcolor=CARD, activebackground=BG,
                    font=F_MAIN).grid(row=0, column=2, sticky=W)

        # ── Shuffle ───────────────────────────────────────────────────
        shuf_f = Frame(self, bg=BG, padx=20, pady=2)
        shuf_f.pack(fill=X)
        self.v_shuffle = BooleanVar(value=True)
        Checkbutton(shuf_f, text="Shuffle ngẫu nhiên", variable=self.v_shuffle,
                    bg=BG, fg=TEXT, selectcolor=CARD, activebackground=BG,
                    font=F_MAIN, command=self._on_shuffle_change).grid(
                        row=0, column=0, sticky=W, padx=(0, 8))
        Label(shuf_f, text="Seed:", bg=BG, fg=DIM, font=F_MAIN).grid(
            row=0, column=1, sticky=W, padx=(0, 4))
        self.v_seed = StringVar(value="42")
        self.seed_entry = Entry(shuf_f, textvariable=self.v_seed, width=6,
                                bg=CARD, fg=TEXT, insertbackground=TEXT, relief="flat",
                                font=F_MAIN)
        self.seed_entry.grid(row=0, column=2, sticky=W)

        # ── Train extra: labels dir + class names ─────────────────────
        self.train_extra = Frame(self, bg=BG, padx=20, pady=4)
        self.train_extra.pack(fill=X)
        self.v_labels = StringVar()
        _bind_cfg("split.labels", self.v_labels)
        _folder_row(self.train_extra, "📁  Labels (.txt) — để trống để tự tìm:",
                    self.v_labels, 0, history_key="h.split.labels")
        Label(self.train_extra, text="Tên class (phân cách bởi dấu phẩy):", bg=BG, fg=DIM,
              font=F_MAIN).grid(row=1, column=0, sticky=W, pady=(4, 0))
        default_classes = ",".join(CLASS_NAMES[i] for i in sorted(CLASS_NAMES.keys()))
        self.v_classes = StringVar(value=default_classes)
        _cls_combo = ttk.Combobox(self.train_extra, textvariable=self.v_classes,
                                   style="Dark.TCombobox", font=F_MAIN)
        _cls_combo.grid(row=1, column=1, sticky=EW, padx=(8, 8), columnspan=2)
        _bind_history("h.split.classes", _cls_combo)
        self.train_extra.pack_forget()   # sẽ show khi mode=train

        # ── Preview ───────────────────────────────────────────────────
        prev_f = Frame(self, bg=CARD, padx=20, pady=8)
        prev_f.pack(fill=X, padx=20, pady=(6, 0))
        self.lbl_hint = Label(prev_f, text="", bg=CARD, fg=DIM, font=("Segoe UI", 9))
        self.lbl_hint.pack(anchor=W)
        self.lbl_preview = Label(prev_f, text="", bg=CARD, fg=ACCENT, font=F_BOLD,
                                 justify=LEFT, wraplength=720)
        self.lbl_preview.pack(anchor=W, pady=(4, 0))

        # ── Giải thích thuật ngữ (collapsible) ───────────────────────
        self._build_glossary()

        # ── Progress + log ────────────────────────────────────────────
        pb_f = Frame(self, bg=BG, padx=20)
        pb_f.pack(fill=X)
        self.pb_lbl, self.pb = _pb_row(pb_f)

        log_outer = Frame(self, bg=BG, padx=20)
        log_outer.pack(fill=BOTH, expand=True)
        log_f, self.log = _make_logbox(log_outer)
        log_f.pack(fill=BOTH, expand=True)

        # ── Buttons ───────────────────────────────────────────────────
        btn_row = Frame(self, bg=BG, padx=20, pady=10)
        btn_row.pack(fill=X, side=BOTTOM)
        self.btn = _action_btn(btn_row, "▶  Bắt đầu Split  [F5]", self._run, ACCENT, padx=20, pady=8)
        self.btn.pack(side=LEFT)
        self.btn_stop = _action_btn(btn_row, "⏹  Dừng  [Esc]", self._stop, "#c0392b",
                                    padx=14, pady=8)
        self.btn_stop.pack(side=LEFT, padx=(8, 0))
        self.btn_stop.config(state=DISABLED)
        _action_btn(btn_row, "🗂  Mở output", self._open, ACCENT2,
                    padx=14, pady=8).pack(side=LEFT, padx=(10, 0))
        Button(btn_row, text="🧹  Xóa log  [Ctrl+L]",
               command=lambda: (self.log.configure(state=NORMAL),
                                self.log.delete("1.0", END),
                                self.log.configure(state=DISABLED)),
               bg=CARD, fg=DIM, font=F_MAIN, relief="flat",
               padx=14, pady=8, cursor="hand2").pack(side=RIGHT)

        self._on_mode_change()

    # ------------------------------------------------------------------
    def _on_mode_change(self):
        mode = self.v_mode.get()
        self.train_opt_frame.grid_remove()
        self.count_frame.grid_remove()
        self.ratio_frame.grid_remove()
        if mode == "train":
            self.train_opt_frame.grid()
            self.train_extra.pack(fill=X)
            self.lbl_hint.config(
                text="Chia 80/20 theo từng subfolder — output: train/images, train/labels, valid/images, valid/labels, data.yaml")
        elif mode == "count":
            self.count_frame.grid()
            self.train_extra.pack_forget()
            self.lbl_hint.config(text="Tạo folder: part_01, part_02, … — mỗi folder tối đa N ảnh.")
        else:
            self.ratio_frame.grid()
            self.train_extra.pack_forget()
            self.lbl_hint.config(text="Chia ảnh theo tỷ lệ phần trăm vào các folder riêng.")
        self._update_preview()

    def _on_shuffle_change(self):
        self.seed_entry.config(fg=TEXT if self.v_shuffle.get() else DIM)

    # ------------------------------------------------------------------
    def _scan_subfolders(self, src_path: Path):
        """
        Quét đệ quy toàn bộ cây thư mục.
        Trả về list (folder_path, [image_files]) cho mọi folder
        có chứa ảnh trực tiếp (không lồng thêm cấp).
        """
        result = []
        # Duyệt tất cả thư mục con ở mọi cấp, theo thứ tự alphabet
        all_dirs = sorted([src_path] + [d for d in src_path.rglob("*") if d.is_dir()])
        for d in all_dirs:
            imgs = sorted([f for f in d.iterdir()
                           if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS])
            if imgs:
                result.append((d, imgs))
        return result

    def _count_images_total(self):
        src = self.v_src.get().strip()
        if not src or not Path(src).is_dir():
            return 0
        return sum(1 for f in Path(src).rglob("*")
                   if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS)

    def _update_preview(self):
        src = self.v_src.get().strip()
        mode = self.v_mode.get()

        if not src or not Path(src).is_dir():
            self.lbl_preview.config(text="")
            return

        src_path = Path(src)

        if mode == "train":
            ratio = self._parse_train_ratio()
            if ratio is None:
                self.lbl_preview.config(text="⚠  Tỷ lệ không hợp lệ (vd: 80/20, tổng = 100)")
                return
            folders = self._scan_subfolders(src_path)
            if not folders:
                self.lbl_preview.config(text="Không tìm thấy ảnh.")
                return
            total_train = total_val = total_imgs = 0
            lines = []
            for folder, imgs in folders:
                n = len(imgs)
                n_train = round(n * ratio[0] / 100)
                n_val = n - n_train
                total_train += n_train
                total_val += n_val
                total_imgs += n
                name = folder.name if folder != src_path else "(root)"
                lines.append(f"{name}: {n} ảnh → train {n_train} / valid {n_val}")
            MAX_SHOW = 8
            preview = f"Tổng: {total_imgs} ảnh  |  Train: {total_train}  |  Valid: {total_val}\n"
            preview += "\n".join(lines[:MAX_SHOW])
            if len(lines) > MAX_SHOW:
                preview += f"\n  … (+{len(lines) - MAX_SHOW} folder khác)"
            self.lbl_preview.config(text=preview)

        elif mode == "count":
            total = self._count_images_total()
            if total == 0:
                self.lbl_preview.config(text="")
                return
            try:
                max_n = int(self.v_max.get())
                if max_n < 1:
                    raise ValueError
            except (ValueError, TclError):
                self.lbl_preview.config(text="⚠  Giá trị không hợp lệ")
                return
            n_parts = math.ceil(total / max_n)
            self.lbl_preview.config(
                text=f"Sẽ tạo {n_parts} part, ~{total/n_parts:.0f} ảnh/part  (tổng {total})")

        else:  # ratio
            total = self._count_images_total()
            if total == 0:
                self.lbl_preview.config(text="")
                return
            ratios = self._parse_ratio()
            if ratios is None:
                self.lbl_preview.config(text="⚠  Tỷ lệ không hợp lệ (phải tổng = 100)")
                return
            parts_info = [f"~{round(total * r / 100)}" for r in ratios]
            self.lbl_preview.config(
                text=f"Sẽ tạo {len(ratios)} part: {' / '.join(parts_info)} ảnh  (tổng {total})")

    def _parse_train_ratio(self):
        raw = self.v_train_ratio.get().strip()
        try:
            parts = [int(x.strip()) for x in raw.split("/")]
            if len(parts) != 2 or any(p <= 0 for p in parts) or sum(parts) != 100:
                return None
            return parts
        except (ValueError, AttributeError):
            return None

    def _parse_ratio(self):
        raw = self.v_ratio.get().strip()
        try:
            parts = [int(x.strip()) for x in raw.split("/")]
            if any(p <= 0 for p in parts) or sum(parts) != 100:
                return None
            return parts
        except (ValueError, AttributeError):
            return None

    # ------------------------------------------------------------------
    def _open(self):
        p = self.v_out.get().strip()
        if not p:
            src = self.v_src.get().strip()
            if src:
                mode = self.v_mode.get()
                suffix = "_train" if mode == "train" else "_split"
                p = str(Path(src).parent / (Path(src).name + suffix))
        if p and Path(p).exists():
            os.startfile(p)
        else:
            messagebox.showwarning("Chưa có output", "Chạy xong hoặc nhập thư mục đầu ra.")

    # ------------------------------------------------------------------
    def _run(self):
        src = self.v_src.get().strip()
        if not src:
            messagebox.showwarning("Thiếu thông tin", "Vui lòng chọn thư mục nguồn.")
            return

        mode = self.v_mode.get()
        do_shuffle = self.v_shuffle.get()
        seed = 42
        try:
            seed = int(self.v_seed.get())
        except (ValueError, TypeError):
            pass

        dup_policy = self.v_dup.get()
        move = self.v_move.get()
        out_dir = self.v_out.get().strip()
        src_path = Path(src)

        # ── TRAIN / VAL (per-folder) ─────────────────────────────────
        if mode == "train":
            self._run_train(src_path, out_dir, do_shuffle, seed, dup_policy, move)
            return

        # ── COUNT / RATIO modes ──────────────────────────────────────
        max_n = None
        ratios = None
        folder_names = None

        if mode == "count":
            try:
                max_n = int(self.v_max.get())
                if max_n < 1:
                    raise ValueError
            except (ValueError, TypeError, TclError):
                messagebox.showwarning("Giá trị không hợp lệ",
                                       "Tối đa ảnh / folder phải là số nguyên dương.")
                return
        else:
            ratios = self._parse_ratio()
            if ratios is None:
                messagebox.showwarning("Tỷ lệ không hợp lệ",
                                       "Tổng tỷ lệ phải bằng 100.\nVí dụ: 70/20/10")
                return
            folder_names = (["train", "val", "test"] if len(ratios) == 3
                            else [f"part_{str(i+1).zfill(len(str(len(ratios))))}"
                                  for i in range(len(ratios))])

        files = sorted(f for f in src_path.rglob("*")
                       if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS)
        if not files:
            messagebox.showwarning("Không tìm thấy ảnh", "Không có ảnh trong thư mục nguồn.")
            return

        if do_shuffle:
            rng = random.Random(seed)
            rng.shuffle(files)

        out_path = Path(out_dir) if out_dir else src_path.parent / (src_path.name + "_split")

        if mode == "count":
            n_parts = math.ceil(len(files) / max_n)
            pad = len(str(n_parts))
            buckets = [("part_" + str(i+1).zfill(pad), files[i*max_n:(i+1)*max_n])
                       for i in range(n_parts)]
        else:
            buckets = []
            start = 0
            total = len(files)
            for idx, (r, fname) in enumerate(zip(ratios, folder_names)):
                count = (total - start) if idx == len(ratios) - 1 else round(total * r / 100)
                buckets.append((fname, files[start:start + count]))
                start += count

        self._start_worker(lambda: self._worker_simple(buckets, out_path, move, dup_policy, seed, do_shuffle))

    # ------------------------------------------------------------------
    def _run_train(self, src_path, out_dir, do_shuffle, seed, dup_policy, move):
        train_ratio = self._parse_train_ratio()
        if train_ratio is None:
            messagebox.showwarning("Tỷ lệ không hợp lệ",
                                   "Tỷ lệ train/val phải gồm 2 phần và tổng = 100.\nVí dụ: 80/20")
            return

        folders = self._scan_subfolders(src_path)
        if not folders:
            messagebox.showwarning("Không tìm thấy ảnh", "Không có ảnh trong thư mục nguồn.")
            return

        labels_dir_input = self.v_labels.get().strip()
        if labels_dir_input:
            labels_dir = Path(labels_dir_input)
        elif (src_path / "labels").is_dir():
            labels_dir = src_path / "labels"
        elif (src_path.parent / "labels").is_dir():
            labels_dir = src_path.parent / "labels"
        else:
            labels_dir = src_path

        classes_str = self.v_classes.get().strip()
        class_list = ([c.strip() for c in classes_str.split(",") if c.strip()]
                      if classes_str else
                      [CLASS_NAMES[i] for i in sorted(CLASS_NAMES.keys())])

        out_path = Path(out_dir) if out_dir else src_path.parent / (src_path.name + "_train")

        self._start_worker(lambda: self._worker_train(
            folders, src_path, labels_dir, out_path,
            train_ratio, do_shuffle, seed, dup_policy, move, class_list
        ))

    def _worker_train(self, folders, src_path, labels_dir, out_path,
                      train_ratio, do_shuffle, seed, dup_policy, move, class_list):
        """
        Chia train/valid theo từng subfolder độc lập.
        Cấu trúc output (YOLO chuẩn):
          train/images/...
          train/labels/...
          valid/images/...
          valid/labels/...
          data.yaml
        """
        try:
            rng = random.Random(seed)
            total_train_count = total_val_count = 0
            labels_missing = 0
            skipped = 0
            overwritten = 0
            done = 0

            # Tính tổng để làm progress
            total_files = sum(len(imgs) for _, imgs in folders)

            self.root.after(0, _append_log, self.log,
                            f"Tổng ảnh        : {total_files}")
            self.root.after(0, _append_log, self.log,
                            f"Số subfolder    : {len(folders)}")
            self.root.after(0, _append_log, self.log,
                            f"Tỷ lệ           : train {train_ratio[0]}% / valid {train_ratio[1]}%")
            self.root.after(0, _append_log, self.log,
                            f"Shuffle         : {'Có (seed=' + str(seed) + ')' if do_shuffle else 'Không'}")
            self.root.after(0, _append_log, self.log,
                            f"Labels từ       : {labels_dir.resolve()}")
            self.root.after(0, _append_log, self.log,
                            f"Thư mục đầu ra  : {out_path.resolve()}")
            self.root.after(0, _append_log, self.log, "─" * 60)

            for folder_path, imgs in folders:
                if self._stop_event.is_set():
                    break

                folder_name = folder_path.name if folder_path != src_path else "_root"

                if do_shuffle:
                    imgs = list(imgs)
                    rng.shuffle(imgs)

                n_train = round(len(imgs) * train_ratio[0] / 100)
                train_imgs = imgs[:n_train]
                val_imgs = imgs[n_train:]

                self.root.after(0, _append_log, self.log,
                                f"📂 {folder_name}  ({len(imgs)} ảnh → "
                                f"train {len(train_imgs)} / valid {len(val_imgs)})")

                for split_name, chunk in [("train", train_imgs), ("valid", val_imgs)]:
                    img_dest = out_path / split_name / "images"
                    lbl_dest = out_path / split_name / "labels"
                    img_dest.mkdir(parents=True, exist_ok=True)
                    lbl_dest.mkdir(parents=True, exist_ok=True)

                    for fp in chunk:
                        if self._stop_event.is_set():
                            break

                        done += 1
                        self.root.after(0, _set_progress,
                                        self.pb_lbl, self.pb, done, total_files, self.root)

                        dest_img = img_dest / fp.name
                        if dest_img.exists():
                            if dup_policy == "skip":
                                skipped += 1
                                continue
                            overwritten += 1

                        (shutil.move if move else shutil.copy2)(str(fp), dest_img)

                        label_file = _find_label_file(fp, labels_dir, src_path)
                        if label_file:
                            dest_lbl = lbl_dest / (fp.stem + ".txt")
                            if not dest_lbl.exists() or dup_policy == "overwrite":
                                shutil.copy2(str(label_file), dest_lbl)
                        else:
                            labels_missing += 1

                total_train_count += len(train_imgs)
                total_val_count += len(val_imgs)

            # Ghi data.yaml
            if not self._stop_event.is_set():
                yaml_content = (
                    f"train: train/images\n"
                    f"val: valid/images\n"
                    f"nc: {len(class_list)}\n"
                    f"names: {class_list}\n"
                )
                yaml_path = out_path / "data.yaml"
                yaml_path.write_text(yaml_content, encoding="utf-8")
                self.root.after(0, _append_log, self.log, f"✔  data.yaml → {yaml_path}")

            self.root.after(0, _append_log, self.log, "─" * 60)
            if self._stop_event.is_set():
                self.root.after(0, _append_log, self.log,
                                f"⚠  Đã dừng. Xử lý {done}/{total_files} ảnh.")
            else:
                summary = (f"✅  Hoàn thành!  Train: {total_train_count}  |  Valid: {total_val_count}")
                if labels_missing:
                    summary += f"  |  Labels thiếu: {labels_missing}"
                if skipped:
                    summary += f"  |  Bỏ qua: {skipped}"
                if overwritten:
                    summary += f"  |  Ghi đè: {overwritten}"
                self.root.after(0, _append_log, self.log, summary)
                self.root.after(0, _append_log, self.log,
                                f"📁  Output: {out_path.resolve()}")

        except Exception as e:
            self.root.after(0, _append_log, self.log, f"[LỖI] {e}")
        finally:
            self.root.after(0, self._done_ui)

    def _worker_simple(self, buckets, out_path, move, dup_policy, seed, do_shuffle):
        try:
            total_files = sum(len(chunk) for _, chunk in buckets)
            done = 0
            skipped = 0
            overwritten = 0
            out_path.mkdir(parents=True, exist_ok=True)

            self.root.after(0, _append_log, self.log, f"Tổng ảnh: {total_files}")
            self.root.after(0, _append_log, self.log, f"Shuffle : {'Có (seed=' + str(seed) + ')' if do_shuffle else 'Không'}")
            self.root.after(0, _append_log, self.log, f"Output  : {out_path.resolve()}")
            self.root.after(0, _append_log, self.log, "─" * 58)

            for part_name, chunk in buckets:
                if self._stop_event.is_set():
                    break
                dest_folder = out_path / part_name
                dest_folder.mkdir(parents=True, exist_ok=True)
                for fp in chunk:
                    if self._stop_event.is_set():
                        break
                    done += 1
                    self.root.after(0, _set_progress,
                                    self.pb_lbl, self.pb, done, total_files, self.root)
                    dest = dest_folder / fp.name
                    if dest.exists():
                        if dup_policy == "skip":
                            skipped += 1
                            continue
                        overwritten += 1
                    (shutil.move if move else shutil.copy2)(str(fp), dest)
                if not self._stop_event.is_set():
                    self.root.after(0, _append_log, self.log,
                                    f"✔  {part_name}  →  {len(chunk)} ảnh")

            self.root.after(0, _append_log, self.log, "─" * 58)
            if self._stop_event.is_set():
                self.root.after(0, _append_log, self.log, f"⚠  Đã dừng ({done}/{total_files}).")
            else:
                msg = f"✅  Hoàn thành! {len(buckets)} part tại '{out_path.resolve()}'"
                if skipped:
                    msg += f"  |  Bỏ qua: {skipped}"
                if overwritten:
                    msg += f"  |  Ghi đè: {overwritten}"
                self.root.after(0, _append_log, self.log, msg)
        except Exception as e:
            self.root.after(0, _append_log, self.log, f"[LỖI] {e}")
        finally:
            self.root.after(0, self._done_ui)

    # ------------------------------------------------------------------
    def _start_worker(self, fn):
        self._stop_event.clear()
        self.btn.config(state=DISABLED, text="⏳  Đang xử lý…")
        self.btn_stop.config(state=NORMAL)
        self.pb["value"] = 0
        self.pb_lbl.config(text="Đang khởi động…")
        threading.Thread(target=fn, daemon=True).start()

    def _done_ui(self):
        self.btn.config(state=NORMAL, text="▶  Bắt đầu Split  [F5]")
        self.btn_stop.config(state=DISABLED)
        if not self._stop_event.is_set():
            self.pb_lbl.config(text="✅  Hoàn thành!")

    # ------------------------------------------------------------------
    def _build_glossary(self):
        """Panel giải thích thuật ngữ — có thể thu gọn/mở rộng."""
        TERMS = [
            ("Chế độ Train/Val (YOLO)",
             "Chia ảnh thành 2 tập: train (mô hình học từ đây) và val (đo độ chính xác sau mỗi epoch).\n"
             "Đây là format chuẩn mà YOLO yêu cầu để huấn luyện."),

            ("Chia theo từng folder",
             "Mỗi subfolder bên trong thư mục nguồn được split 80/20 độc lập.\n"
             "Ví dụ: camera_01 có 100 ảnh → 80 vào train, 20 vào val.\n"
             "camera_02 có 200 ảnh → 160 train, 40 val.\n"
             "Cách này đảm bảo train và val đều có ảnh từ MỌI camera/địa điểm, tránh bị lệch phân phối."),

            ("Tỷ lệ train/val  (80/20)",
             "80% số ảnh của mỗi folder → tập train.  20% còn lại → tập val.\n"
             "Tỷ lệ phổ biến: 80/20 (cân bằng), 90/10 (khi ít ảnh val OK), 70/30 (khi cần val kỹ hơn)."),

            ("Shuffle  (xáo trộn)",
             "Xáo trộn ngẫu nhiên thứ tự ảnh TRƯỚC khi chia.\n"
             "Vì sao cần: ảnh từ camera thường được đặt tên theo thứ tự thời gian (frame_001, frame_002…).\n"
             "Nếu không shuffle → val sẽ toàn ảnh cuối video (có thể khác điều kiện ánh sáng/góc chụp so với train).\n"
             "Nếu shuffle → train và val đều có ảnh rải đều trong suốt video → phân phối đồng đều hơn.\n"
             "Khuyến nghị: BẬT shuffle cho hầu hết trường hợp."),

            ("Seed",
             "Số nguyên dùng để khởi tạo bộ sinh số ngẫu nhiên cho shuffle.\n"
             "Cùng seed → cùng kết quả xáo trộn dù chạy bao nhiêu lần.\n"
             "Hữu ích khi cần tái lập thí nghiệm hoặc so sánh các lần train.\n"
             "Ví dụ: seed=42 là giá trị mặc định phổ biến trong cộng đồng ML."),

            ("Labels (.txt)",
             "File nhãn YOLO — mỗi ảnh có 1 file .txt cùng tên.\n"
             "Nội dung mỗi dòng: <class_id> <cx> <cy> <width> <height>  (tọa độ chuẩn hóa 0-1).\n"
             "Ví dụ: '5 0.512 0.348 0.124 0.089' = biển số (class 5) ở giữa ảnh.\n"
             "Để trống ô này → tool tự tìm labels trong thư mục 'labels/' bên cạnh thư mục ảnh."),

            ("Tên class",
             "Danh sách tên class theo đúng thứ tự ID trong file label.\n"
             "ID 0 = class đầu tiên, ID 1 = class thứ hai, …\n"
             "Ví dụ: 'car,motorcycle,bus,truck,bicycle,license_plate'\n"
             "Thông tin này được ghi vào data.yaml để YOLO biết tên từng class khi hiển thị kết quả."),

            ("Sao chép / Di chuyển",
             "Sao chép: giữ nguyên file gốc, tạo bản sao vào output. An toàn hơn.\n"
             "Di chuyển: chuyển file gốc sang output, xóa khỏi thư mục nguồn. Tiết kiệm ổ đĩa."),

            ("File trùng tên — Bỏ qua / Ghi đè",
             "Khi file đích đã tồn tại (output đã có sẵn từ lần chạy trước):\n"
             "Bỏ qua: giữ file cũ, bỏ qua file mới → output không thay đổi.\n"
             "Ghi đè: thay file cũ bằng file mới.\n"
             "Cũng áp dụng khi 2 subfolder khác nhau có ảnh trùng tên — nên đảm bảo tên ảnh unique."),

            ("data.yaml",
             "File cấu hình YOLO tự động tạo sau khi split.\n"
             "Nội dung: đường dẫn train/val + số class (nc) + tên class (names).\n"
             "Dùng trực tiếp trong lệnh train: model.train(data='data.yaml', ...)"),

            ("Chia số lượng / part",
             "Chia toàn bộ ảnh (gộp) thành nhiều folder nhỏ, mỗi folder tối đa N ảnh.\n"
             "Dùng khi cần phân phối ảnh vào nhiều máy/worker để label song song."),

            ("Chia tỷ lệ %",
             "Chia tổng ảnh (gộp từ mọi subfolder) theo % vào 2-4 folder.\n"
             "Ví dụ: 70/20/10 → tạo folder train (70%), val (20%), test (10%).\n"
             "Khác với Train/Val YOLO: không giữ phân phối theo subfolder."),
        ]

        gloss_outer = Frame(self, bg=BG, padx=20)
        gloss_outer.pack(fill=X, pady=(4, 0))

        # Toggle button
        self._gloss_open = BooleanVar(value=False)
        toggle_btn = Button(gloss_outer,
                            text="ℹ  Giải thích thuật ngữ  ▾",
                            bg=CARD, fg=DIM, font=("Segoe UI", 9),
                            relief="flat", cursor="hand2", anchor=W,
                            command=self._toggle_glossary)
        toggle_btn.pack(fill=X, ipady=4)
        self._gloss_toggle_btn = toggle_btn

        # Collapsible content
        self._gloss_frame = Frame(gloss_outer, bg=CARD)
        txt = Text(self._gloss_frame, bg=CARD, fg=TEXT,
                   font=("Segoe UI", 9), relief="flat",
                   wrap=WORD, cursor="arrow",
                   height=16, padx=14, pady=8,
                   state=NORMAL)
        txt.pack(fill=X)

        txt.tag_config("term",  foreground=ACCENT,  font=("Segoe UI", 9, "bold"))
        txt.tag_config("desc",  foreground=TEXT,     font=("Segoe UI", 9))
        txt.tag_config("space", foreground=BG)

        for term, desc in TERMS:
            txt.insert(END, f"▸ {term}\n", "term")
            txt.insert(END, f"  {desc}\n\n", "desc")

        txt.config(state=DISABLED)

    def _toggle_glossary(self):
        if self._gloss_open.get():
            self._gloss_frame.pack_forget()
            self._gloss_toggle_btn.config(text="ℹ  Giải thích thuật ngữ  ▾")
            self._gloss_open.set(False)
        else:
            self._gloss_frame.pack(fill=X)
            self._gloss_toggle_btn.config(text="ℹ  Giải thích thuật ngữ  ▴")
            self._gloss_open.set(True)

    # ------------------------------------------------------------------
    def _stop(self):
        self._stop_event.set()
        self.btn_stop.config(state=DISABLED)

    def _browse(self):
        from tkinter import filedialog
        p = filedialog.askdirectory(title="Chọn thư mục nguồn",
                                    initialdir=_cfg_dir("split.src"))
        if p:
            self.v_src.set(p)
            _push_history("h.split.src", p)
