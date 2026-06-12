import os
import threading
from pathlib import Path
from tkinter import *
from tkinter import messagebox

from .constants import BG, CARD, ACCENT, ACCENT2, TEXT, DIM, F_MAIN, F_BOLD
from .settings import _bind_cfg
from .core_crop import run_crop_by_label
from .ui_helpers import (
    _folder_row, _pb_row, _make_logbox, _append_log,
    _set_progress, _action_btn,
)


class CropByLabelTab(Frame):
    def __init__(self, master, root):
        super().__init__(master, bg=BG)
        self.root = root
        self._stop_event = threading.Event()
        self._class_vars = {}
        self._build()

    def _build(self):
        top = Frame(self, bg=BG, padx=20, pady=12)
        top.pack(fill=X)
        self.v_img = StringVar(); self.v_lbl = StringVar(); self.v_out = StringVar()
        _bind_cfg("crop.img", self.v_img)
        _bind_cfg("crop.lbl", self.v_lbl)
        _bind_cfg("crop.out", self.v_out)
        _folder_row(top, "📁  Thư mục ảnh",         self.v_img, 0)
        _folder_row(top, "🏷  Thư mục label (.txt)", self.v_lbl, 1)
        _folder_row(top, "💾  Thư mục output",       self.v_out, 2)

        cr = Frame(top, bg=BG)
        cr.grid(row=3, column=0, columnspan=3, sticky=EW, pady=(8, 0))
        Label(cr, text="Danh sách nhãn:", bg=BG, fg=DIM,
              font=F_MAIN, width=26, anchor=W).pack(side=LEFT)
        self.v_classes = StringVar(
            value="car, motorbike, bus, truck, bicycle, license_plate")
        _bind_cfg("crop.classes", self.v_classes)
        Entry(cr, textvariable=self.v_classes, bg=CARD, fg=TEXT,
              insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4).pack(
              side=LEFT, fill=X, expand=True, padx=(8, 0))
        Button(cr, text="Cập nhật ↺", command=self._refresh_classes,
               bg=ACCENT2, fg="white", activebackground=ACCENT,
               activeforeground="white", font=F_MAIN, relief="flat",
               padx=10, cursor="hand2").pack(side=LEFT, padx=(6, 0))

        opt = Frame(self, bg=BG, padx=20)
        opt.pack(fill=X, pady=(0, 4))
        opt.columnconfigure(0, weight=3)
        opt.columnconfigure(1, weight=2)

        cls_f = LabelFrame(opt, text=" Nhãn lớp cần crop ",
                           bg=BG, fg=TEXT, font=F_BOLD, bd=1, relief="groove")
        cls_f.grid(row=0, column=0, sticky=NSEW, padx=(0, 8), pady=4)
        self._class_frame = Frame(cls_f, bg=BG)
        self._class_frame.pack(anchor=W, padx=10, pady=8)

        cfg_f = LabelFrame(opt, text=" Tùy chọn ",
                           bg=BG, fg=TEXT, font=F_BOLD, bd=1, relief="groove")
        cfg_f.grid(row=0, column=1, sticky=NSEW, pady=4)
        self._build_opts(cfg_f)

        btn_row = Frame(self, bg=BG, padx=20, pady=6)
        self.btn_run = _action_btn(btn_row, "✂  Bắt đầu Crop", self._run, ACCENT,
                                   padx=20, pady=7)
        self.btn_run.pack(side=LEFT)
        self.btn_stop = _action_btn(btn_row, "⏹  Dừng", self._stop, "#c0392b",
                                    padx=14, pady=7)
        self.btn_stop.pack(side=LEFT, padx=(8, 0))
        self.btn_stop.config(state=DISABLED)
        _action_btn(btn_row, "🔄  Xóa tiến độ", self._reset_state, ACCENT2,
                    padx=14, pady=7).pack(side=LEFT, padx=(8, 0))
        _action_btn(btn_row, "📂  Mở output", self._open_out, ACCENT2,
                    padx=14, pady=7).pack(side=LEFT, padx=(8, 0))
        Button(btn_row, text="🧹  Xóa log",
               command=lambda: (self.log.configure(state=NORMAL),
                                self.log.delete("1.0", END),
                                self.log.configure(state=DISABLED)),
               bg=CARD, fg=DIM, font=F_MAIN, relief="flat",
               padx=14, pady=7, cursor="hand2").pack(side=RIGHT)

        pb_f = Frame(self, bg=BG, padx=20)
        self.pb_lbl, self.pb = _pb_row(pb_f)

        log_outer = Frame(self, bg=BG, padx=20)
        log_f, self.log = _make_logbox(log_outer)
        log_f.pack(fill=BOTH, expand=True)

        btn_row.pack(fill=X, side=BOTTOM)
        pb_f.pack(fill=X, side=BOTTOM)
        log_outer.pack(fill=BOTH, expand=True)

        self._refresh_classes()

    def _build_opts(self, p):
        def _row(label, var, unit="", row=0, w=6):
            Label(p, text=label, bg=BG, fg=DIM, font=F_MAIN).grid(
                row=row, column=0, sticky=W, padx=10, pady=4)
            f = Frame(p, bg=BG); f.grid(row=row, column=1, sticky=W, padx=4)
            Entry(f, textvariable=var, width=w, bg=CARD, fg=TEXT,
                  insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4).pack(side=LEFT)
            if unit:
                Label(f, text=unit, bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT, padx=3)

        r = 0
        self.v_padding = IntVar(value=0)
        _row("Padding (mở rộng crop):", self.v_padding, "px", r); r += 1
        self.v_min_w = IntVar(value=0)
        _row("Crop tối thiểu (rộng):", self.v_min_w, "px", r); r += 1
        self.v_min_h = IntVar(value=0)
        _row("Crop tối thiểu (cao):", self.v_min_h, "px", r); r += 1
        self.v_quality = IntVar(value=95)
        _row("JPEG quality:", self.v_quality, "(1–100)", r); r += 1

        Frame(p, bg=CARD, height=1).grid(row=r, column=0, columnspan=2,
                                          sticky=EW, padx=10, pady=6); r += 1

        self.v_by_class = BooleanVar(value=True)
        Checkbutton(p, text="Chia subfolder theo từng nhãn",
                    variable=self.v_by_class, bg=BG, fg=TEXT,
                    activebackground=BG, activeforeground=TEXT,
                    selectcolor=CARD, font=F_MAIN).grid(
                    row=r, column=0, columnspan=2, sticky=W, padx=10, pady=2); r += 1

        self.v_filter_cls = BooleanVar(value=False)
        Checkbutton(p, text="Chỉ crop các nhãn đã tích",
                    variable=self.v_filter_cls, bg=BG, fg=TEXT,
                    activebackground=BG, activeforeground=TEXT,
                    selectcolor=CARD, font=F_MAIN).grid(
                    row=r, column=0, columnspan=2, sticky=W, padx=10, pady=2); r += 1

        self.v_recursive = BooleanVar(value=False)
        Checkbutton(p, text="Quét tất cả subfolder (đệ quy)",
                    variable=self.v_recursive, bg=BG, fg=TEXT,
                    activebackground=BG, activeforeground=TEXT,
                    selectcolor=CARD, font=F_MAIN).grid(
                    row=r, column=0, columnspan=2, sticky=W, padx=10, pady=2)

    def _refresh_classes(self):
        for w in self._class_frame.winfo_children():
            w.destroy()
        self._class_vars.clear()
        names = [n.strip() for n in
                 self.v_classes.get().replace(";", ",").split(",") if n.strip()]
        for i, name in enumerate(names):
            v = BooleanVar(value=True)
            self._class_vars[i] = (name, v)
            Checkbutton(self._class_frame, text=name, variable=v,
                        bg=BG, fg=TEXT, activebackground=BG,
                        activeforeground=TEXT, selectcolor=CARD,
                        font=F_MAIN).grid(row=i // 3, column=i % 3,
                                          sticky=W, padx=6, pady=2)

    def _get_cfg(self):
        keep_ids  = [i for i, (_, v) in self._class_vars.items() if v.get()]
        class_map = {i: name for i, (name, _) in self._class_vars.items()}
        return {
            "image_dir":      self.v_img.get().strip(),
            "label_dir":      self.v_lbl.get().strip(),
            "output_dir":     self.v_out.get().strip(),
            "filter_classes": self.v_filter_cls.get(),
            "keep_classes":   keep_ids,
            "class_names_map": class_map,
            "padding_px":     self.v_padding.get(),
            "min_w_px":       self.v_min_w.get(),
            "min_h_px":       self.v_min_h.get(),
            "jpeg_quality":   self.v_quality.get(),
            "split_by_class": self.v_by_class.get(),
            "recursive":      self.v_recursive.get(),
        }

    def _run(self):
        cfg = self._get_cfg()
        if not cfg["image_dir"] or not cfg["label_dir"] or not cfg["output_dir"]:
            messagebox.showwarning("Thiếu thông tin", "Vui lòng chọn đủ 3 thư mục."); return
        self._stop_event.clear()
        self.btn_run.config(state=DISABLED, text="⏳  Đang xử lý…")
        self.btn_stop.config(state=NORMAL)
        self.pb["value"] = 0; self.pb_lbl.config(text="Đang khởi động…")

        def worker():
            try:
                run_crop_by_label(
                    cfg,
                    log=lambda m: self.root.after(0, _append_log, self.log, m),
                    progress=lambda d, t: self.root.after(
                        0, _set_progress, self.pb_lbl, self.pb, d, t, self.root),
                    stop_event=self._stop_event)
            except Exception as e:
                self.root.after(0, _append_log, self.log, f"[LỖI] {e}")
            finally:
                self.root.after(0, lambda: (
                    self.btn_run.config(state=NORMAL, text="✂  Bắt đầu Crop"),
                    self.btn_stop.config(state=DISABLED),
                    self.pb_lbl.config(text="✅  Hoàn thành!")))

        threading.Thread(target=worker, daemon=True).start()

    def _stop(self):
        self._stop_event.set()
        self.btn_stop.config(state=DISABLED)
        _append_log(self.log, "⚠  Đang dừng sau ảnh hiện tại…")

    def _reset_state(self):
        out = self.v_out.get().strip()
        if not out:
            messagebox.showwarning("Chưa chọn output", "Chọn thư mục output trước."); return
        sf = Path(out) / ".crop_by_label_state.json"
        if sf.exists():
            sf.unlink()
            _append_log(self.log, "🔄  Đã xóa tiến độ. Lần chạy tiếp sẽ xử lý lại từ đầu.")
        else:
            _append_log(self.log, "ℹ  Không có file tiến độ.")

    def _open_out(self):
        p = self.v_out.get().strip()
        if p and Path(p).exists():
            os.startfile(p)
        else:
            messagebox.showwarning("Chưa có output", "Chọn hoặc chạy xong để mở thư mục.")
