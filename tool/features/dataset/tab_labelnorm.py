import os
import threading
from pathlib import Path
from tkinter import *
from tkinter import messagebox, ttk

from ...core.constants import (
    BG, CARD, ACCENT, ACCENT2, TEXT, DIM, F_MAIN, F_BOLD, IMAGE_EXTENSIONS,
)
from ...core.settings import _bind_cfg, _bind_history, _push_history, _get_history
from .core_label_norm import run_label_norm
from ...core.ui_helpers import (
    _folder_row, _pb_row, _make_logbox, _append_log,
    _set_progress, _action_btn,
)

try:
    from PIL import Image, ImageTk
    _PIL_OK = True
except ImportError:
    _PIL_OK = False

_BOX_COLORS = [
    "#F05922", "#4A3F8C", "#4caf50", "#f0c040", "#00bcd4",
    "#e91e63", "#9c27b0", "#ff9800", "#8bc34a", "#03a9f4",
]


class LabelNormTab(Frame):
    def __init__(self, master, root):
        super().__init__(master, bg=BG)
        self.root = root
        self._stop_event = threading.Event()
        self._class_vars = {}
        self._preview_photo = None
        self._build()

    def _build(self):
        top = Frame(self, bg=BG, padx=20, pady=10)
        top.pack(fill=X)
        self.v_img = StringVar(); self.v_lbl = StringVar(); self.v_out = StringVar()
        _bind_cfg("labelnorm.img", self.v_img)
        _bind_cfg("labelnorm.lbl", self.v_lbl)
        _bind_cfg("labelnorm.out", self.v_out)
        _folder_row(top, "📁  Thư mục ảnh",         self.v_img, 0, history_key="h.labelnorm.img")
        _folder_row(top, "🏷  Thư mục label (.txt)", self.v_lbl, 1, history_key="h.labelnorm.lbl")
        _folder_row(top, "💾  Thư mục output",       self.v_out, 2, history_key="h.labelnorm.out")

        cr = Frame(top, bg=BG)
        cr.grid(row=3, column=0, columnspan=3, sticky=EW, pady=(6, 0))
        Label(cr, text="Danh sách nhãn:", bg=BG, fg=DIM,
              font=F_MAIN, width=26, anchor=W).pack(side=LEFT)
        self.v_classes = StringVar(
            value="car, motorbike, bus, truck, bicycle, license_plate")
        _bind_cfg("labelnorm.classes", self.v_classes)
        _cls_combo = ttk.Combobox(cr, textvariable=self.v_classes,
                                   style="Dark.TCombobox", font=F_MAIN)
        _cls_combo.pack(side=LEFT, fill=X, expand=True, padx=(8, 0))
        _bind_history("h.labelnorm.classes", _cls_combo)
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

        tools_f = LabelFrame(self, text=" Công cụ nhãn ",
                             bg=BG, fg=TEXT, font=F_BOLD, bd=1, relief="groove",
                             padx=12, pady=8)
        self._build_tools(tools_f)

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
        tools_f.pack(fill=BOTH, expand=True, padx=20, pady=(0, 4))

    def _build_tools(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=1)
        parent.columnconfigure(2, weight=2)

        remap_f = LabelFrame(parent, text=" Đổi class ",
                             bg=BG, fg=DIM, font=F_MAIN, bd=1, relief="groove",
                             padx=8, pady=6)
        remap_f.grid(row=0, column=0, sticky=NSEW, padx=(0, 6))

        rf = Frame(remap_f, bg=BG)
        rf.pack(fill=X)
        Label(rf, text="Class cũ:", bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT)
        self.v_remap_old = StringVar()
        Entry(rf, textvariable=self.v_remap_old, width=6, bg=CARD, fg=TEXT,
              insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4).pack(
              side=LEFT, padx=(4, 12))
        Label(rf, text="Class mới:", bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT)
        self.v_remap_new = StringVar()
        Entry(rf, textvariable=self.v_remap_new, width=6, bg=CARD, fg=TEXT,
              insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4).pack(
              side=LEFT, padx=(4, 8))
        Button(rf, text="Áp dụng", command=self._remap_class,
               bg=ACCENT2, fg="white", activebackground=ACCENT,
               activeforeground="white", font=F_MAIN, relief="flat",
               padx=10, cursor="hand2").pack(side=LEFT)

        del_f = LabelFrame(parent, text=" Xóa class ",
                           bg=BG, fg=DIM, font=F_MAIN, bd=1, relief="groove",
                           padx=8, pady=6)
        del_f.grid(row=0, column=1, sticky=NSEW, padx=(0, 6))

        df = Frame(del_f, bg=BG)
        df.pack(fill=X)
        Label(df, text="Xóa class:", bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT)
        self.v_del_class = StringVar()
        Entry(df, textvariable=self.v_del_class, width=6, bg=CARD, fg=TEXT,
              insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4).pack(
              side=LEFT, padx=(4, 8))
        Button(df, text="Xóa nhãn", command=self._delete_class,
               bg="#c0392b", fg="white", activebackground="#e74c3c",
               activeforeground="white", font=F_MAIN, relief="flat",
               padx=10, cursor="hand2").pack(side=LEFT)

        check_f = LabelFrame(parent, text=" Phát hiện nhãn bất thường ",
                             bg=BG, fg=DIM, font=F_MAIN, bd=1, relief="groove",
                             padx=8, pady=6)
        check_f.grid(row=0, column=2, sticky=NSEW)

        cf = Frame(check_f, bg=BG)
        cf.pack(fill=X)
        Button(cf, text="🔍  Kiểm tra", command=self._check_anomalies,
               bg=ACCENT2, fg="white", activebackground=ACCENT,
               activeforeground="white", font=F_MAIN, relief="flat",
               padx=12, cursor="hand2").pack(side=LEFT)
        Label(cf, text="Quét tất cả label — bbox ngoài [0,1], quá nhỏ, trùng lặp",
              bg=BG, fg=DIM, font=("Segoe UI", 9)).pack(side=LEFT, padx=(10, 0))

        preview_f = LabelFrame(parent, text=" Xem trước bbox ",
                               bg=BG, fg=DIM, font=F_MAIN, bd=1, relief="groove",
                               padx=8, pady=6)
        preview_f.grid(row=1, column=0, columnspan=3, sticky=NSEW, pady=(8, 0))
        parent.rowconfigure(1, weight=1)

        pv_top = Frame(preview_f, bg=BG)
        pv_top.pack(fill=X, pady=(0, 6))
        Label(pv_top, text="Chọn file label:", bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT)
        Button(pv_top, text="Tải danh sách ↺", command=self._load_file_list,
               bg=ACCENT2, fg="white", activebackground=ACCENT,
               activeforeground="white", font=F_MAIN, relief="flat",
               padx=10, cursor="hand2").pack(side=LEFT, padx=(8, 0))

        pv_body = Frame(preview_f, bg=BG)
        pv_body.pack(fill=BOTH, expand=True)
        pv_body.columnconfigure(0, weight=0)
        pv_body.columnconfigure(1, weight=1)

        list_f = Frame(pv_body, bg=BG)
        list_f.grid(row=0, column=0, sticky=NS, padx=(0, 8))

        self.file_listbox = Listbox(
            list_f, bg=CARD, fg=TEXT, font=("Consolas", 9),
            selectbackground=ACCENT2, selectforeground="white",
            relief="flat", bd=0, width=30, height=5,
        )
        lb_sb = Scrollbar(list_f, command=self.file_listbox.yview)
        self.file_listbox.configure(yscrollcommand=lb_sb.set)
        lb_sb.pack(side=RIGHT, fill=Y)
        self.file_listbox.pack(side=LEFT, fill=BOTH, expand=True)
        self.file_listbox.bind("<<ListboxSelect>>", self._on_file_select)

        canvas_f = Frame(pv_body, bg=CARD, bd=0)
        canvas_f.grid(row=0, column=1, sticky=NSEW)

        self.preview_canvas = Canvas(
            canvas_f, bg=CARD, bd=0, highlightthickness=0,
            width=520, height=100,
        )
        self.preview_canvas.pack(fill=BOTH, expand=True)
        self.preview_canvas.bind("<Configure>", self._on_canvas_resize)
        self.preview_canvas.bind("<Double-Button-1>", self._on_preview_zoom)
        self._pending_preview_file = None
        self._preview_pil_full = None

    def _build_filters(self, p):
        def _cb(text, var, row, col=0, span=1):
            Checkbutton(p, text=text, variable=var, bg=BG, fg=TEXT,
                        activebackground=BG, activeforeground=TEXT,
                        selectcolor=CARD, font=F_MAIN).grid(
                            row=row, column=col, columnspan=span,
                            sticky=W, padx=10, pady=1)

        def _ent(parent, var, w=6):
            return Entry(parent, textvariable=var, width=w, bg=CARD, fg=TEXT,
                         insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4)

        def _lbl(text, row, col, dim=True):
            Label(p, text=text, bg=BG, fg=DIM if dim else TEXT,
                  font=F_MAIN).grid(row=row, column=col, sticky=W, padx=4)

        r = 0
        Label(p, text="Nhãn lớp cần giữ:", bg=BG, fg=DIM, font=F_MAIN).grid(
            row=r, column=0, columnspan=4, sticky=W, padx=10, pady=(4, 2)); r += 1
        self._class_frame = Frame(p, bg=BG)
        self._class_frame.grid(row=r, column=0, columnspan=4, sticky=W, padx=12, pady=(0, 2)); r += 1
        Frame(p, bg=CARD, height=1).grid(row=r, column=0, columnspan=4,
                                          sticky=EW, padx=10, pady=3); r += 1

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
                                          sticky=EW, padx=10, pady=3); r += 1

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
                        font=F_MAIN).pack(anchor=W, padx=10, pady=1)

        Frame(p, bg=CARD, height=1).pack(fill=X, padx=10, pady=3)

        Label(p, text="Ngưỡng kích thước (S/M/L):",
              bg=BG, fg=DIM, font=F_MAIN).pack(anchor=W, padx=10)
        tf = Frame(p, bg=BG); tf.pack(anchor=W, padx=14, pady=2)
        self.v_size_s = DoubleVar(value=3.0); self.v_size_l = DoubleVar(value=15.0)
        Label(tf, text="Small <", bg=BG, fg=DIM, font=F_MAIN).grid(row=0, column=0)
        Entry(tf, textvariable=self.v_size_s, width=5, bg=CARD, fg=TEXT,
              insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4).grid(row=0, column=1, padx=4)
        Label(tf, text="%   Large >", bg=BG, fg=DIM, font=F_MAIN).grid(row=0, column=2)
        Entry(tf, textvariable=self.v_size_l, width=5, bg=CARD, fg=TEXT,
              insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4).grid(row=0, column=3, padx=4)
        Label(tf, text="%  (Medium = giữa)", bg=BG, fg=DIM, font=F_MAIN).grid(row=0, column=4)

        Label(p, text="Ngưỡng vị trí gần viền (border):",
              bg=BG, fg=DIM, font=F_MAIN).pack(anchor=W, padx=10, pady=(3, 0))
        pf = Frame(p, bg=BG); pf.pack(anchor=W, padx=14, pady=2)
        self.v_pos_border = DoubleVar(value=25.0)
        Label(pf, text="Biên <", bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT)
        Entry(pf, textvariable=self.v_pos_border, width=5, bg=CARD, fg=TEXT,
              insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4).pack(side=LEFT, padx=4)
        Label(pf, text="% từ mỗi cạnh  (còn lại = center)",
              bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT)

        Label(p, text="Ngưỡng tỉ lệ w/h (orientation):",
              bg=BG, fg=DIM, font=F_MAIN).pack(anchor=W, padx=10, pady=(3, 0))
        of = Frame(p, bg=BG); of.pack(anchor=W, padx=14, pady=2)
        self.v_orient_thr = DoubleVar(value=1.3)
        Label(of, text="Threshold:", bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT)
        Entry(of, textvariable=self.v_orient_thr, width=5, bg=CARD, fg=TEXT,
              insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4).pack(side=LEFT, padx=4)
        Label(of, text="(w/h > t → landscape, h/w > t → portrait)",
              bg=BG, fg=DIM, font=("Consolas", 8)).pack(side=LEFT)

        Frame(p, bg=CARD, height=1).pack(fill=X, padx=10, pady=3)
        Label(p, text="• size/class/count/position/region/orient → subfolder name",
              bg=BG, fg=DIM, font=("Consolas", 8)).pack(anchor=W, padx=14, pady=(2, 4))

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

    def _get_label_dir(self):
        return self.v_lbl.get().strip()

    def _collect_label_files(self):
        lbl_dir = self._get_label_dir()
        if not lbl_dir or not Path(lbl_dir).is_dir():
            return []
        result = []
        for p in sorted(Path(lbl_dir).rglob("*.txt")):
            result.append(p)
        return result

    def _remap_class(self):
        old_s = self.v_remap_old.get().strip()
        new_s = self.v_remap_new.get().strip()
        if not old_s or not new_s:
            messagebox.showwarning("Thiếu dữ liệu", "Nhập cả Class cũ và Class mới."); return
        try:
            old_id = int(old_s)
            new_id = int(new_s)
        except ValueError:
            messagebox.showerror("Lỗi", "Class ID phải là số nguyên."); return

        files = self._collect_label_files()
        if not files:
            messagebox.showwarning("Không tìm thấy", "Chưa chọn thư mục label hoặc không có file .txt."); return

        total_changed = 0
        for fp in files:
            try:
                lines = fp.read_text(encoding="utf-8").splitlines()
            except Exception:
                continue
            new_lines = []
            changed = False
            for line in lines:
                parts = line.strip().split()
                if parts and parts[0] == str(old_id):
                    parts[0] = str(new_id)
                    new_lines.append(" ".join(parts))
                    changed = True
                    total_changed += 1
                else:
                    new_lines.append(line)
            if changed:
                fp.write_text("\n".join(new_lines) + ("\n" if new_lines else ""),
                              encoding="utf-8")

        _append_log(self.log,
                    f"✔  Đổi class {old_id}→{new_id}: {total_changed} dòng trong {len(files)} file.")

    def _delete_class(self):
        cls_s = self.v_del_class.get().strip()
        if not cls_s:
            messagebox.showwarning("Thiếu dữ liệu", "Nhập Class ID cần xóa."); return
        try:
            del_id = int(cls_s)
        except ValueError:
            messagebox.showerror("Lỗi", "Class ID phải là số nguyên."); return

        if not messagebox.askyesno("Xác nhận", f"Xóa tất cả nhãn class {del_id} khỏi mọi file?\nHành động không thể hoàn tác."):
            return

        files = self._collect_label_files()
        if not files:
            messagebox.showwarning("Không tìm thấy", "Chưa chọn thư mục label hoặc không có file .txt."); return

        total_removed = 0
        for fp in files:
            try:
                lines = fp.read_text(encoding="utf-8").splitlines()
            except Exception:
                continue
            kept = []
            removed = 0
            for line in lines:
                parts = line.strip().split()
                if parts and parts[0] == str(del_id):
                    removed += 1
                else:
                    kept.append(line)
            if removed:
                fp.write_text("\n".join(kept) + ("\n" if kept else ""),
                              encoding="utf-8")
                total_removed += removed

        _append_log(self.log,
                    f"✔  Xóa class {del_id}: đã loại bỏ {total_removed} dòng trong {len(files)} file.")

    def _check_anomalies(self):
        files = self._collect_label_files()
        if not files:
            messagebox.showwarning("Không tìm thấy", "Chưa chọn thư mục label hoặc không có file .txt."); return

        win = Toplevel(self.root)
        win.title("Kết quả kiểm tra nhãn bất thường")
        win.configure(bg=BG)
        win.geometry("780x500")

        hdr = Frame(win, bg=BG, padx=12, pady=8)
        hdr.pack(fill=X)
        Label(hdr, text="Phát hiện nhãn bất thường", bg=BG, fg=TEXT,
              font=F_BOLD).pack(side=LEFT)

        body = Frame(win, bg=BG, padx=12, pady=(0, 12))
        body.pack(fill=BOTH, expand=True)

        txt = Text(body, bg=CARD, fg=TEXT, font=("Consolas", 9),
                   relief="flat", bd=0, wrap=NONE, state=NORMAL,
                   insertbackground=TEXT)
        sb_y = Scrollbar(body, command=txt.yview)
        sb_x = Scrollbar(body, orient=HORIZONTAL, command=txt.xview)
        txt.configure(yscrollcommand=sb_y.set, xscrollcommand=sb_x.set)
        sb_y.pack(side=RIGHT, fill=Y)
        sb_x.pack(side=BOTTOM, fill=X)
        txt.pack(fill=BOTH, expand=True)

        for tag, color in [("warn", "#f0c040"), ("err", "#f05050"),
                           ("ok", "#4caf50"), ("dim", DIM)]:
            txt.tag_config(tag, foreground=color)

        issue_count = 0

        def _emit(line, tag="dim"):
            nonlocal issue_count
            txt.insert(END, line + "\n", tag)

        _emit(f"Quét {len(files)} file...", "dim")

        for fp in files:
            try:
                lines = fp.read_text(encoding="utf-8").splitlines()
            except Exception as e:
                _emit(f"[LỖI đọc] {fp.name}: {e}", "err")
                issue_count += 1
                continue

            seen = set()
            for lineno, line in enumerate(lines, 1):
                parts = line.strip().split()
                if not parts:
                    continue
                if len(parts) < 5:
                    _emit(f"  {fp.name}:{lineno}  → thiếu cột ({len(parts)} cột)", "warn")
                    issue_count += 1
                    continue
                try:
                    cx, cy, bw, bh = (float(parts[i]) for i in (1, 2, 3, 4))
                except ValueError:
                    _emit(f"  {fp.name}:{lineno}  → giá trị không hợp lệ: {line.strip()}", "err")
                    issue_count += 1
                    continue

                if not (0.0 <= cx <= 1.0 and 0.0 <= cy <= 1.0 and
                        0.0 <= bw <= 1.0 and 0.0 <= bh <= 1.0):
                    _emit(f"  {fp.name}:{lineno}  → tọa độ ngoài [0,1]: cx={cx:.4f} cy={cy:.4f} w={bw:.4f} h={bh:.4f}", "err")
                    issue_count += 1

                if bw < 0.01 or bh < 0.01:
                    _emit(f"  {fp.name}:{lineno}  → bbox quá nhỏ: w={bw:.4f} h={bh:.4f}", "warn")
                    issue_count += 1

                key = (parts[0], f"{cx:.6f}", f"{cy:.6f}", f"{bw:.6f}", f"{bh:.6f}")
                if key in seen:
                    _emit(f"  {fp.name}:{lineno}  → trùng lặp: class={parts[0]} cx={cx:.4f} cy={cy:.4f} w={bw:.4f} h={bh:.4f}", "warn")
                    issue_count += 1
                else:
                    seen.add(key)

        if issue_count == 0:
            _emit(f"\n✔  Không phát hiện vấn đề nào trong {len(files)} file.", "ok")
        else:
            _emit(f"\n⚠  Tổng cộng {issue_count} vấn đề phát hiện.", "warn")

        txt.configure(state=DISABLED)

    def _load_file_list(self):
        files = self._collect_label_files()
        self.file_listbox.delete(0, END)
        lbl_dir = self._get_label_dir()
        base = Path(lbl_dir) if lbl_dir else None
        for fp in files:
            try:
                display = str(fp.relative_to(base)) if base else fp.name
            except ValueError:
                display = fp.name
            self.file_listbox.insert(END, display)
        self._label_file_paths = files
        if files:
            self.file_listbox.selection_set(0)
            self._show_preview(files[0])

    def _on_file_select(self, event):
        sel = self.file_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if not hasattr(self, "_label_file_paths") or idx >= len(self._label_file_paths):
            return
        fp = self._label_file_paths[idx]
        self._show_preview(fp)

    def _find_image_for_label(self, label_path):
        stem = label_path.stem
        img_dir = self.v_img.get().strip()
        candidates = []
        if img_dir and Path(img_dir).is_dir():
            for ext in IMAGE_EXTENSIONS:
                p = Path(img_dir) / (stem + ext)
                if p.exists():
                    candidates.append(p)
                p2 = Path(img_dir) / (stem + ext.upper())
                if p2.exists():
                    candidates.append(p2)
        if not candidates:
            for ext in IMAGE_EXTENSIONS:
                p = label_path.parent / (stem + ext)
                if p.exists():
                    candidates.append(p)
        return candidates[0] if candidates else None

    def _parse_label_boxes(self, label_path):
        boxes = []
        try:
            for line in label_path.read_text(encoding="utf-8").splitlines():
                parts = line.strip().split()
                if len(parts) >= 5:
                    try:
                        cls = int(parts[0])
                        cx, cy, bw, bh = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
                        boxes.append((cls, cx, cy, bw, bh))
                    except ValueError:
                        pass
        except Exception:
            pass
        return boxes

    def _show_preview(self, label_path):
        self._pending_preview_file = label_path
        self.preview_canvas.delete("all")
        self._preview_photo = None
        self._preview_pil_full = None  # reset zoom ref

        boxes = self._parse_label_boxes(label_path)
        img_path = self._find_image_for_label(label_path)

        cw = self.preview_canvas.winfo_width() or 520
        ch = self.preview_canvas.winfo_height() or 300

        if img_path and _PIL_OK:
            self._draw_preview_pil(img_path, boxes, cw, ch)
        else:
            self._draw_preview_fallback(boxes, cw, ch, label_path.name,
                                        no_pil=not _PIL_OK, no_img=img_path is None)

    def _draw_preview_pil(self, img_path, boxes, cw, ch):
        try:
            img = Image.open(img_path).convert("RGB")
        except Exception:
            self._draw_preview_fallback(boxes, cw, ch, img_path.name, no_img=True)
            return

        self._preview_pil_full = img  # lưu ảnh gốc để zoom
        iw, ih = img.size
        scale = min(cw / iw, ch / ih, 1.0)
        nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
        img = img.resize((nw, nh), Image.LANCZOS if hasattr(Image, "LANCZOS") else Image.ANTIALIAS)

        photo = ImageTk.PhotoImage(img)
        self._preview_photo = photo

        ox = (cw - nw) // 2
        oy = (ch - nh) // 2
        self.preview_canvas.create_image(ox, oy, anchor=NW, image=photo)

        for cls, cx, cy, bw, bh in boxes:
            color = _BOX_COLORS[cls % len(_BOX_COLORS)]
            x1 = ox + int((cx - bw / 2) * nw)
            y1 = oy + int((cy - bh / 2) * nh)
            x2 = ox + int((cx + bw / 2) * nw)
            y2 = oy + int((cy + bh / 2) * nh)
            self.preview_canvas.create_rectangle(x1, y1, x2, y2,
                                                  outline=color, width=2)
            self.preview_canvas.create_text(x1 + 3, y1 + 2,
                                             text=str(cls), anchor=NW,
                                             fill=color,
                                             font=("Consolas", 9, "bold"))

    def _draw_preview_fallback(self, boxes, cw, ch, name="", no_pil=False, no_img=False):
        self.preview_canvas.create_rectangle(2, 2, cw - 2, ch - 2,
                                              outline=DIM, dash=(4, 4))
        if no_pil:
            msg = "Cài Pillow để xem ảnh: pip install Pillow"
        elif no_img:
            msg = f"Không tìm thấy ảnh cho: {name}"
        else:
            msg = f"Không thể tải ảnh: {name}"
        self.preview_canvas.create_text(cw // 2, ch // 2 - 20,
                                         text=msg, fill=DIM,
                                         font=F_MAIN, anchor=CENTER)
        if boxes:
            self.preview_canvas.create_text(
                cw // 2, ch // 2 + 10,
                text=f"{len(boxes)} bbox(es) trong file label",
                fill=TEXT, font=F_MAIN, anchor=CENTER,
            )
            for i, (cls, cx, cy, bw, bh) in enumerate(boxes):
                color = _BOX_COLORS[cls % len(_BOX_COLORS)]
                x1 = int((cx - bw / 2) * cw)
                y1 = int((cy - bh / 2) * ch)
                x2 = int((cx + bw / 2) * cw)
                y2 = int((cy + bh / 2) * ch)
                self.preview_canvas.create_rectangle(x1, y1, x2, y2,
                                                      outline=color, width=2)
                self.preview_canvas.create_text(x1 + 3, y1 + 2,
                                                 text=str(cls), anchor=NW,
                                                 fill=color,
                                                 font=("Consolas", 9, "bold"))

    def _on_canvas_resize(self, event):
        if self._pending_preview_file:
            self._show_preview(self._pending_preview_file)

    def _on_preview_zoom(self, _event=None):
        """Double-click — phóng to ảnh gốc (không có bbox overlay)."""
        if not hasattr(self, "_preview_pil_full") or self._preview_pil_full is None:
            return
        from ...core.ui_helpers import _zoom_image_window
        name = ""
        if self._pending_preview_file:
            name = self._pending_preview_file.stem
        _zoom_image_window(self.root, self._preview_pil_full,
                           f"Phóng to — {name}" if name else "Phóng to ảnh")

    def _browse(self):
        """Ctrl+O — mở hộp thoại chọn thư mục ảnh."""
        from tkinter import filedialog
        from ...core.settings import _cfg_dir, _push_history
        p = filedialog.askdirectory(title="Chọn thư mục ảnh",
                                    initialdir=_cfg_dir("labelnorm.img"))
        if p:
            self.v_img.set(p)
            _push_history("h.labelnorm.img", p)
