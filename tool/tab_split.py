import math
import os
import random
import shutil
import threading
from pathlib import Path
from tkinter import *
from tkinter import messagebox

from .constants import BG, CARD, ACCENT, ACCENT2, TEXT, DIM, F_MAIN, F_BOLD, IMAGE_EXTENSIONS
from .settings import _bind_cfg
from .core_split import run_split
from .ui_helpers import _folder_row, _pb_row, _make_logbox, _append_log, _set_progress, _action_btn


class SplitTab(Frame):
    def __init__(self, master, root):
        super().__init__(master, bg=BG)
        self.root = root
        self._build()

    # ------------------------------------------------------------------
    def _build(self):
        inp = Frame(self, bg=BG, padx=20, pady=14)
        inp.pack(fill=X)
        self.v_src = StringVar()
        self.v_out = StringVar()
        _bind_cfg("split.src", self.v_src)
        _bind_cfg("split.out", self.v_out)
        _folder_row(inp, "📁  Thư mục nguồn",             self.v_src, 0)
        _folder_row(inp, "💾  Thư mục đầu ra (tuỳ chọn)", self.v_out, 1)
        self.v_src.trace_add("write", lambda *_: self._update_preview())

        # ── Split mode: by count or by ratio ──────────────────────────
        mode_f = Frame(self, bg=BG, padx=20, pady=2)
        mode_f.pack(fill=X)
        Label(mode_f, text="Chế độ chia:", bg=BG, fg=DIM, font=F_MAIN).grid(
            row=0, column=0, sticky=W, padx=(0, 8))
        self.v_mode = StringVar(value="count")
        Radiobutton(mode_f, text="Số lượng / part", variable=self.v_mode, value="count",
                    bg=BG, fg=TEXT, selectcolor=CARD, activebackground=BG, font=F_MAIN,
                    command=self._on_mode_change).grid(row=0, column=1, sticky=W, padx=(0, 12))
        Radiobutton(mode_f, text="Tỷ lệ %", variable=self.v_mode, value="ratio",
                    bg=BG, fg=TEXT, selectcolor=CARD, activebackground=BG, font=F_MAIN,
                    command=self._on_mode_change).grid(row=0, column=2, sticky=W)

        # ── Options row ───────────────────────────────────────────────
        opt = Frame(self, bg=BG, padx=20, pady=4)
        opt.pack(fill=X)

        # Count mode widgets
        self.count_frame = Frame(opt, bg=BG)
        self.count_frame.grid(row=0, column=0, sticky=W)
        Label(self.count_frame, text="Tối đa ảnh / folder:", bg=BG, fg=DIM,
              font=F_MAIN).grid(row=0, column=0, sticky=W, padx=(0, 8))
        self.v_max = IntVar(value=1000)
        self.spin_max = Spinbox(self.count_frame, from_=10, to=100000, increment=100,
                                textvariable=self.v_max,
                                bg=CARD, fg=TEXT, insertbackground=TEXT, buttonbackground=ACCENT2,
                                relief="flat", font=F_MAIN, width=8,
                                command=self._update_preview)
        self.spin_max.grid(row=0, column=1, sticky=W)
        self.v_max.trace_add("write", lambda *_: self._update_preview())

        # Ratio mode widgets
        self.ratio_frame = Frame(opt, bg=BG)
        self.ratio_frame.grid(row=0, column=0, sticky=W)
        Label(self.ratio_frame, text="Tỷ lệ % (vd: 70/20/10):", bg=BG, fg=DIM,
              font=F_MAIN).grid(row=0, column=0, sticky=W, padx=(0, 8))
        self.v_ratio = StringVar(value="70/20/10")
        Entry(self.ratio_frame, textvariable=self.v_ratio, width=14,
              bg=CARD, fg=TEXT, insertbackground=TEXT, relief="flat",
              font=F_MAIN).grid(row=0, column=1, sticky=W)
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
        self.v_shuffle = BooleanVar(value=False)
        Checkbutton(shuf_f, text="Shuffle ngẫu nhiên", variable=self.v_shuffle,
                    bg=BG, fg=TEXT, selectcolor=CARD, activebackground=BG,
                    font=F_MAIN, command=self._on_shuffle_change).grid(
                        row=0, column=0, sticky=W, padx=(0, 8))
        Label(shuf_f, text="Seed:", bg=BG, fg=DIM, font=F_MAIN).grid(
            row=0, column=1, sticky=W, padx=(0, 4))
        self.v_seed = StringVar(value="42")
        self.seed_entry = Entry(shuf_f, textvariable=self.v_seed, width=6,
                                bg=CARD, fg=DIM, insertbackground=TEXT, relief="flat",
                                font=F_MAIN, state=DISABLED)
        self.seed_entry.grid(row=0, column=2, sticky=W)

        # ── Preview label ─────────────────────────────────────────────
        prev_f = Frame(self, bg=CARD, padx=20, pady=8)
        prev_f.pack(fill=X, padx=20, pady=(6, 0))
        for t in ["Tạo folder: part_01, part_02, … — mỗi folder tối đa N ảnh.",
                  "Để trống 'Thư mục đầu ra' → tự tạo folder <tên>_split bên cạnh thư mục nguồn."]:
            Label(prev_f, text=t, bg=CARD, fg=DIM, font=("Segoe UI", 9)).pack(anchor=W)
        self.lbl_preview = Label(prev_f, text="", bg=CARD, fg=ACCENT, font=F_BOLD)
        self.lbl_preview.pack(anchor=W, pady=(4, 0))

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
        self.btn = _action_btn(btn_row, "▶  Bắt đầu Split", self._run, ACCENT, padx=20, pady=8)
        self.btn.pack(side=LEFT)
        _action_btn(btn_row, "🗂  Mở output", self._open, ACCENT2,
                    padx=14, pady=8).pack(side=LEFT, padx=(10, 0))
        Button(btn_row, text="🧹  Xóa log",
               command=lambda: (self.log.configure(state=NORMAL),
                                self.log.delete("1.0", END),
                                self.log.configure(state=DISABLED)),
               bg=CARD, fg=DIM, font=F_MAIN, relief="flat",
               padx=14, pady=8, cursor="hand2").pack(side=RIGHT)

        self._update_preview()

    # ------------------------------------------------------------------
    def _on_mode_change(self):
        if self.v_mode.get() == "count":
            self.ratio_frame.grid_remove()
            self.count_frame.grid()
        else:
            self.count_frame.grid_remove()
            self.ratio_frame.grid()
        self._update_preview()

    def _on_shuffle_change(self):
        self.seed_entry.config(
            state=NORMAL if self.v_shuffle.get() else DISABLED,
            fg=TEXT if self.v_shuffle.get() else DIM)

    # ------------------------------------------------------------------
    def _count_images(self):
        src = self.v_src.get().strip()
        if not src or not Path(src).is_dir():
            return 0
        return sum(
            1 for f in Path(src).rglob("*")
            if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
        )

    def _update_preview(self):
        total = self._count_images()
        if total == 0:
            self.lbl_preview.config(text="")
            return
        mode = self.v_mode.get()
        if mode == "count":
            try:
                max_n = int(self.v_max.get())
                if max_n < 1:
                    raise ValueError
            except (ValueError, TclError):
                self.lbl_preview.config(text="⚠  Giá trị tối đa không hợp lệ")
                return
            n_parts = math.ceil(total / max_n)
            avg = total / n_parts if n_parts else 0
            self.lbl_preview.config(
                text=f"Sẽ tạo {n_parts} part, ~{avg:.0f} ảnh/part  (tổng {total} ảnh)")
        else:
            ratios = self._parse_ratio()
            if ratios is None:
                self.lbl_preview.config(text="⚠  Tỷ lệ không hợp lệ (phải tổng = 100)")
                return
            parts_info = []
            for r in ratios:
                parts_info.append(f"~{round(total * r / 100)}")
            self.lbl_preview.config(
                text=f"Sẽ tạo {len(ratios)} part: {' / '.join(parts_info)} ảnh  (tổng {total} ảnh)")

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
                p = str(Path(src).parent / (Path(src).name + "_split"))
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
            if len(ratios) == 3:
                folder_names = ["train", "val", "test"]
            else:
                pad = len(str(len(ratios)))
                folder_names = [f"part_{str(i+1).zfill(pad)}" for i in range(len(ratios))]

        do_shuffle = self.v_shuffle.get()
        seed = 42
        if do_shuffle:
            try:
                seed = int(self.v_seed.get())
            except (ValueError, TypeError):
                messagebox.showwarning("Seed không hợp lệ", "Seed phải là số nguyên.")
                return

        dup_policy = self.v_dup.get()
        move = self.v_move.get()
        out_dir = self.v_out.get().strip()

        src_path = Path(src)
        files = sorted(f for f in src_path.rglob("*")
                       if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS)
        if not files:
            messagebox.showwarning("Không tìm thấy ảnh",
                                   "Không có ảnh nào trong thư mục nguồn.")
            return

        if do_shuffle:
            rng = random.Random(seed)
            rng.shuffle(files)

        out_path = Path(out_dir) if out_dir else src_path.parent / (src_path.name + "_split")

        if mode == "count":
            n_parts = math.ceil(len(files) / max_n)
            pad = len(str(n_parts))
            buckets = []
            for i in range(n_parts):
                name = "part_" + str(i + 1).zfill(pad)
                chunk = files[i * max_n:(i + 1) * max_n]
                buckets.append((name, chunk))
        else:
            total = len(files)
            buckets = []
            start = 0
            for idx, (r, fname) in enumerate(zip(ratios, folder_names)):
                if idx == len(ratios) - 1:
                    chunk = files[start:]
                else:
                    count = round(total * r / 100)
                    chunk = files[start:start + count]
                    start += count
                buckets.append((fname, chunk))

        # Detect duplicates before proceeding
        dup_count = sum(
            1 for (fname, chunk) in buckets
            for fp in chunk
            if (out_path / fname / fp.name).exists()
        )
        if dup_count > 0:
            action_label = "bỏ qua" if dup_policy == "skip" else "ghi đè"
            ok = messagebox.askyesno(
                "Phát hiện file trùng",
                f"Có {dup_count} file đích đã tồn tại.\n"
                f"Chính sách hiện tại: {action_label}.\n\n"
                f"Tiếp tục?")
            if not ok:
                return

        self.btn.config(state=DISABLED, text="⏳  Đang xử lý…")
        self.pb["value"] = 0
        self.pb_lbl.config(text="Đang khởi động…")

        def worker():
            try:
                total_files = sum(len(chunk) for _, chunk in buckets)
                done = 0
                out_path.mkdir(parents=True, exist_ok=True)
                skipped = 0
                overwritten = 0

                self.root.after(0, _append_log, self.log,
                                f"Tổng ảnh        : {total_files}")
                self.root.after(0, _append_log, self.log,
                                f"Số part tạo     : {len(buckets)}")
                self.root.after(0, _append_log, self.log,
                                f"Shuffle         : {'Có (seed=' + str(seed) + ')' if do_shuffle else 'Không'}")
                self.root.after(0, _append_log, self.log,
                                f"File trùng      : {'Bỏ qua' if dup_policy == 'skip' else 'Ghi đè'}")
                self.root.after(0, _append_log, self.log,
                                f"Hành động       : {'Di chuyển' if move else 'Sao chép'}")
                self.root.after(0, _append_log, self.log,
                                f"Thư mục đầu ra  : {out_path.resolve()}")
                self.root.after(0, _append_log, self.log, "─" * 58)

                for part_name, chunk in buckets:
                    dest_folder = out_path / part_name
                    dest_folder.mkdir(parents=True, exist_ok=True)
                    for fp in chunk:
                        done += 1
                        self.root.after(0, _set_progress,
                                        self.pb_lbl, self.pb, done, total_files, self.root)
                        dest = dest_folder / fp.name
                        if dest.exists():
                            if dup_policy == "skip":
                                skipped += 1
                                continue
                            else:
                                overwritten += 1
                        (shutil.move if move else shutil.copy2)(str(fp), dest)
                    self.root.after(0, _append_log, self.log,
                                    f"✔  {part_name}  →  {len(chunk)} ảnh")

                self.root.after(0, _append_log, self.log, "─" * 58)
                summary = f"Hoàn thành! {len(buckets)} part trong '{out_path.resolve()}'"
                if skipped:
                    summary += f"  |  Bỏ qua: {skipped}"
                if overwritten:
                    summary += f"  |  Ghi đè: {overwritten}"
                self.root.after(0, _append_log, self.log, summary)
            except Exception as e:
                self.root.after(0, _append_log, self.log, f"[LỖI] {e}")
            finally:
                self.root.after(0, lambda: (
                    self.btn.config(state=NORMAL, text="▶  Bắt đầu Split"),
                    self.pb_lbl.config(text="✅  Hoàn thành!")))

        threading.Thread(target=worker, daemon=True).start()
