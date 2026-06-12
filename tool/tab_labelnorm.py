import os
import threading
from pathlib import Path
from tkinter import *
from tkinter import messagebox

from .constants import BG, CARD, ACCENT, ACCENT2, TEXT, DIM, F_MAIN, F_BOLD
from .settings import _bind_cfg
from .core_label_norm import run_label_norm
from .ui_helpers import (
    _folder_row, _pb_row, _make_logbox, _append_log,
    _set_progress, _action_btn,
)


class LabelNormTab(Frame):
    def __init__(self, master, root):
        super().__init__(master, bg=BG)
        self.root = root
        self._stop_event = threading.Event()
        self._class_vars = {}
        self._build()

    def _build(self):
        top = Frame(self, bg=BG, padx=20, pady=10)
        top.pack(fill=X)
        self.v_img = StringVar(); self.v_lbl = StringVar(); self.v_out = StringVar()
        _bind_cfg("labelnorm.img", self.v_img)
        _bind_cfg("labelnorm.lbl", self.v_lbl)
        _bind_cfg("labelnorm.out", self.v_out)
        _folder_row(top, "📁  Thư mục ảnh",         self.v_img, 0)
        _folder_row(top, "🏷  Thư mục label (.txt)", self.v_lbl, 1)
        _folder_row(top, "💾  Thư mục output",       self.v_out, 2)

        cr = Frame(top, bg=BG)
        cr.grid(row=3, column=0, columnspan=3, sticky=EW, pady=(6, 0))
        Label(cr, text="Danh sách nhãn:", bg=BG, fg=DIM,
              font=F_MAIN, width=26, anchor=W).pack(side=LEFT)
        self.v_classes = StringVar(
            value="car, motorbike, bus, truck, bicycle, license_plate")
        _bind_cfg("labelnorm.classes", self.v_classes)
        Entry(cr, textvariable=self.v_classes, bg=CARD, fg=TEXT,
              insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4).pack(
              side=LEFT, fill=X, expand=True, padx=(8, 0))
        Button(cr, text="Cập nhật ↺", command=self._refresh_classes,
               bg=ACCENT2, fg="white", activebackground=ACCENT,
               activeforeground="white", font=F_MAIN, relief="flat",
               padx=10, cursor="hand2").pack(side=LEFT, padx=(6, 0))

        mid = Frame(self, bg=BG, padx=20)
        mid.pack(fill=X, pady=(0, 2))
        mid.columnconfigure(0, weight=3)
        mid.columnconfigure(1, weight=2)

        flt = LabelFrame(mid, text=" Điều kiện lọc ",
                         bg=BG, fg=TEXT, font=F_BOLD, bd=1, relief="groove")
        flt.grid(row=0, column=0, sticky=NSEW, padx=(0, 8), pady=4)
        self._build_filters(flt)

        out_f = LabelFrame(mid, text=" Chia subfolder output ",
                           bg=BG, fg=TEXT, font=F_BOLD, bd=1, relief="groove")
        out_f.grid(row=0, column=1, sticky=NSEW, pady=4)
        self._build_split_opts(out_f)

        btn_row = Frame(self, bg=BG, padx=20, pady=6)
        self.btn_run = _action_btn(btn_row, "▶  Bắt đầu", self._run, ACCENT,
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

    def _build_filters(self, p):
        def _cb(text, var, row, col=0, span=1):
            Checkbutton(p, text=text, variable=var, bg=BG, fg=TEXT,
                        activebackground=BG, activeforeground=TEXT,
                        selectcolor=CARD, font=F_MAIN).grid(
                            row=row, column=col, columnspan=span,
                            sticky=W, padx=10, pady=2)

        def _ent(parent, var, w=6):
            return Entry(parent, textvariable=var, width=w, bg=CARD, fg=TEXT,
                         insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4)

        def _lbl(text, row, col, dim=True):
            Label(p, text=text, bg=BG, fg=DIM if dim else TEXT,
                  font=F_MAIN).grid(row=row, column=col, sticky=W, padx=4)

        r = 0
        Label(p, text="Nhãn lớp cần giữ:", bg=BG, fg=DIM, font=F_MAIN).grid(
            row=r, column=0, columnspan=4, sticky=W, padx=10, pady=(8, 2)); r += 1
        self._class_frame = Frame(p, bg=BG)
        self._class_frame.grid(row=r, column=0, columnspan=4, sticky=W, padx=12, pady=(0, 4)); r += 1
        Frame(p, bg=CARD, height=1).grid(row=r, column=0, columnspan=4,
                                          sticky=EW, padx=10, pady=5); r += 1

        self.v_use_largest = BooleanVar(); self.v_largest_n = IntVar(value=1)
        _cb("Giữ", self.v_use_largest, r)
        Spinbox(p, from_=1, to=99, textvariable=self.v_largest_n, width=4,
                bg=CARD, fg=TEXT, buttonbackground=CARD, relief="flat",
                font=F_MAIN).grid(row=r, column=1, sticky=W)
        _lbl("box LỚN nhất / mỗi loại nhãn", r, 2, dim=False); r += 1

        self.v_use_smallest = BooleanVar(); self.v_smallest_n = IntVar(value=1)
        _cb("Giữ", self.v_use_smallest, r)
        Spinbox(p, from_=1, to=99, textvariable=self.v_smallest_n, width=4,
                bg=CARD, fg=TEXT, buttonbackground=CARD, relief="flat",
                font=F_MAIN).grid(row=r, column=1, sticky=W)
        _lbl("box NHỎ nhất / mỗi loại nhãn", r, 2, dim=False); r += 1

        Frame(p, bg=CARD, height=1).grid(row=r, column=0, columnspan=4,
                                          sticky=EW, padx=10, pady=5); r += 1

        self.v_use_min_area = BooleanVar(); self.v_min_area = DoubleVar(value=0.5)
        _cb("Diện tích box tối thiểu:", self.v_use_min_area, r)
        f = Frame(p, bg=BG); f.grid(row=r, column=1, columnspan=3, sticky=W)
        _ent(f, self.v_min_area).pack(side=LEFT)
        Label(f, text="% diện tích ảnh", bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT, padx=4); r += 1

        self.v_use_max_area = BooleanVar(); self.v_max_area = DoubleVar(value=80.0)
        _cb("Diện tích box tối đa:", self.v_use_max_area, r)
        f = Frame(p, bg=BG); f.grid(row=r, column=1, columnspan=3, sticky=W)
        _ent(f, self.v_max_area).pack(side=LEFT)
        Label(f, text="% diện tích ảnh", bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT, padx=4); r += 1

        self.v_use_min_side = BooleanVar(); self.v_min_side = IntVar(value=20)
        _cb("Cạnh box tối thiểu:", self.v_use_min_side, r)
        f = Frame(p, bg=BG); f.grid(row=r, column=1, columnspan=3, sticky=W)
        _ent(f, self.v_min_side).pack(side=LEFT)
        Label(f, text="pixel (min w, h)", bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT, padx=4); r += 1

        self.v_use_aspect = BooleanVar()
        self.v_aspect_min = DoubleVar(value=0.2); self.v_aspect_max = DoubleVar(value=5.0)
        _cb("Tỉ lệ w/h (aspect) trong:", self.v_use_aspect, r)
        f = Frame(p, bg=BG); f.grid(row=r, column=1, columnspan=3, sticky=W)
        _ent(f, self.v_aspect_min, 5).pack(side=LEFT)
        Label(f, text=" – ", bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT)
        _ent(f, self.v_aspect_max, 5).pack(side=LEFT); r += 1

        self.v_use_edge = BooleanVar(); self.v_edge_margin = DoubleVar(value=2.0)
        _cb("Loại box sát rìa ảnh (margin:", self.v_use_edge, r)
        f = Frame(p, bg=BG); f.grid(row=r, column=1, columnspan=3, sticky=W)
        _ent(f, self.v_edge_margin, 5).pack(side=LEFT)
        Label(f, text="%)", bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT, padx=2); r += 1

        self.v_use_nms = BooleanVar(); self.v_nms_iou = DoubleVar(value=0.5)
        _cb("NMS – loại box chồng nhau (IoU >", self.v_use_nms, r)
        f = Frame(p, bg=BG); f.grid(row=r, column=1, columnspan=3, sticky=W)
        _ent(f, self.v_nms_iou, 5).pack(side=LEFT)
        Label(f, text=")", bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT, padx=2); r += 1

        self.v_skip_empty = BooleanVar(value=True)
        _cb("Bỏ qua ảnh không còn box sau lọc", self.v_skip_empty, r, span=4); r += 1
        self.v_recursive = BooleanVar(value=False)
        _cb("Quét tất cả subfolder (đệ quy)", self.v_recursive, r, span=4)
        self._refresh_classes()

    def _build_split_opts(self, p):
        self.v_split_mode = StringVar(value="none")
        for val, text in [
            ("none",        "Không chia – tất cả vào 1 folder"),
            ("size",        "Theo kích thước box  (S / M / L)"),
            ("class",       "Theo nhãn lớp"),
            ("count",       "Theo số lượng  (single / multi)"),
            ("position",    "Theo vị trí  (border / center)"),
            ("region",      "Theo vùng 3×3  (top_left / center ...)"),
            ("orientation", "Theo chiều hướng  (landscape / portrait / square)"),
        ]:
            Radiobutton(p, text=text, variable=self.v_split_mode, value=val,
                        bg=BG, fg=TEXT, activebackground=BG, selectcolor=CARD,
                        font=F_MAIN).pack(anchor=W, padx=10, pady=3)

        Frame(p, bg=CARD, height=1).pack(fill=X, padx=10, pady=5)

        Label(p, text="Ngưỡng kích thước (S/M/L):",
              bg=BG, fg=DIM, font=F_MAIN).pack(anchor=W, padx=10)
        tf = Frame(p, bg=BG); tf.pack(anchor=W, padx=14, pady=3)
        self.v_size_s = DoubleVar(value=3.0); self.v_size_l = DoubleVar(value=15.0)
        Label(tf, text="Small <", bg=BG, fg=DIM, font=F_MAIN).grid(row=0, column=0)
        Entry(tf, textvariable=self.v_size_s, width=5, bg=CARD, fg=TEXT,
              insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4).grid(row=0, column=1, padx=4)
        Label(tf, text="%   Large >", bg=BG, fg=DIM, font=F_MAIN).grid(row=0, column=2)
        Entry(tf, textvariable=self.v_size_l, width=5, bg=CARD, fg=TEXT,
              insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4).grid(row=0, column=3, padx=4)
        Label(tf, text="%  (Medium = giữa)", bg=BG, fg=DIM, font=F_MAIN).grid(row=0, column=4)

        Label(p, text="Ngưỡng vị trí gần viền (border):",
              bg=BG, fg=DIM, font=F_MAIN).pack(anchor=W, padx=10, pady=(6, 0))
        pf = Frame(p, bg=BG); pf.pack(anchor=W, padx=14, pady=3)
        self.v_pos_border = DoubleVar(value=25.0)
        Label(pf, text="Biên <", bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT)
        Entry(pf, textvariable=self.v_pos_border, width=5, bg=CARD, fg=TEXT,
              insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4).pack(side=LEFT, padx=4)
        Label(pf, text="% từ mỗi cạnh  (còn lại = center)",
              bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT)

        Label(p, text="Ngưỡng tỉ lệ w/h (orientation):",
              bg=BG, fg=DIM, font=F_MAIN).pack(anchor=W, padx=10, pady=(6, 0))
        of = Frame(p, bg=BG); of.pack(anchor=W, padx=14, pady=3)
        self.v_orient_thr = DoubleVar(value=1.3)
        Label(of, text="Threshold:", bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT)
        Entry(of, textvariable=self.v_orient_thr, width=5, bg=CARD, fg=TEXT,
              insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4).pack(side=LEFT, padx=4)
        Label(of, text="(w/h > t → landscape, h/w > t → portrait)",
              bg=BG, fg=DIM, font=("Consolas", 8)).pack(side=LEFT)

        Frame(p, bg=CARD, height=1).pack(fill=X, padx=10, pady=5)
        for hint in ["• size     → small/ medium/ large/",
                     "• class    → car/ motorbike/ ...",
                     "• count    → single/ multi/",
                     "• position → border/ center/",
                     "• region   → top_left/ center/ bottom_right/ ...",
                     "• orient   → landscape/ portrait/ square/"]:
            Label(p, text=hint, bg=BG, fg=DIM,
                  font=("Consolas", 8)).pack(anchor=W, padx=14)

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
                        font=F_MAIN).grid(row=i // 4, column=i % 4,
                                          sticky=W, padx=4, pady=1)

    def _get_cfg(self):
        keep_ids  = [i for i, (_, v) in self._class_vars.items() if v.get()]
        class_map = {i: name for i, (name, _) in self._class_vars.items()}
        return {
            "image_dir":       self.v_img.get().strip(),
            "label_dir":       self.v_lbl.get().strip(),
            "output_dir":      self.v_out.get().strip(),
            "use_class_filter": bool(self._class_vars),
            "keep_classes":    keep_ids,
            "class_names_map": class_map,
            "use_largest":     self.v_use_largest.get(),
            "keep_largest_n":  self.v_largest_n.get(),
            "use_smallest":    self.v_use_smallest.get(),
            "keep_smallest_n": self.v_smallest_n.get(),
            "use_min_area":    self.v_use_min_area.get(),
            "min_area_pct":    self.v_min_area.get(),
            "use_max_area":    self.v_use_max_area.get(),
            "max_area_pct":    self.v_max_area.get(),
            "use_min_side":    self.v_use_min_side.get(),
            "min_side_px":     self.v_min_side.get(),
            "use_aspect":      self.v_use_aspect.get(),
            "aspect_min":      self.v_aspect_min.get(),
            "aspect_max":      self.v_aspect_max.get(),
            "use_edge":        self.v_use_edge.get(),
            "edge_margin_pct": self.v_edge_margin.get(),
            "use_nms":         self.v_use_nms.get(),
            "nms_iou":         self.v_nms_iou.get(),
            "skip_empty":      self.v_skip_empty.get(),
            "recursive":       self.v_recursive.get(),
            "split_mode":      self.v_split_mode.get(),
            "size_s_pct":      self.v_size_s.get(),
            "size_l_pct":      self.v_size_l.get(),
            "pos_border_pct":  self.v_pos_border.get(),
            "orient_thr":      self.v_orient_thr.get(),
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
                run_label_norm(
                    cfg,
                    log=lambda m: self.root.after(0, _append_log, self.log, m),
                    progress=lambda d, t: self.root.after(
                        0, _set_progress, self.pb_lbl, self.pb, d, t, self.root),
                    stop_event=self._stop_event)
            except Exception as e:
                self.root.after(0, _append_log, self.log, f"[LỖI] {e}")
            finally:
                self.root.after(0, lambda: (
                    self.btn_run.config(state=NORMAL, text="▶  Bắt đầu"),
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
        sf = Path(out) / ".label_norm_state.json"
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
