# tab_detect_label.py — Tab gộp YOLO Detect + BBox Label Editor
# Shared: FilmstripPanel, DetectCache, CanvasZoomMixin, bbox_renderer, label_io
from __future__ import annotations
import os
import threading
from pathlib import Path
from tkinter import *
from tkinter import filedialog, messagebox, ttk

from ...core.constants import (BG, CARD, ACCENT, ACCENT2, TEXT, DIM, SUCCESS,
                                F_MAIN, F_BOLD, F_MONO, IMAGE_EXTENSIONS)
from ...core.settings import _bind_cfg, _bind_history, _push_history
from ...core.ui_helpers import _folder_row
from ...shared.bbox_renderer import PALETTE, draw_bboxes_thumb, make_padded_thumb, open_image_safe
from ...shared.label_io import read_yolo_normalized, label_path_for
from ...shared.canvas_zoom import CanvasZoomMixin
from ...shared.detect_cache import DetectCache
from ...shared.filmstrip import FilmstripPanel

try:
    from PIL import Image, ImageTk
    _PIL_OK = True
except ImportError:
    _PIL_OK = False

try:
    from ultralytics import YOLO
    _YOLO_OK = True
except ImportError:
    _YOLO_OK = False


class DetectLabelTab(Frame, CanvasZoomMixin):
    """Tab gộp: chạy YOLO detect + xem/sửa bbox + lưu nhãn .txt.

    Workflow: Chọn model → Chọn folder → Detect (F5) → Sửa bbox → Lưu (Ctrl+S)
    """

    def __init__(self, master, root):
        Frame.__init__(self, master, bg=BG)
        self._zoom_init()
        self.root = root

        # ── Core state ─────────────────────────────────────────────────────
        self._files:     list  = []
        self._filtered:  list  = []
        self._current:   str   = ""
        self._boxes:     list  = []   # [(cid, cx_n, cy_n, w_n, h_n)]
        self._selected:  int   = -1
        self._modified:  bool  = False
        self._pil_img           = None
        self._photo_ref         = None
        self._render_nw_nh      = None
        self._render_cached     = None
        self._drawing:   bool  = False
        self._draw_start: tuple = (0, 0)
        self._draw_rect_id      = None
        self._det_cache  = DetectCache()
        self._det_stop   = threading.Event()
        self._det_thread = None
        self._model      = None
        self._filter_after = None

        # ── Tkinter vars ───────────────────────────────────────────────────
        self.v_folder      = StringVar()
        self.v_lbl_dir     = StringVar()
        self.v_model       = StringVar()
        self.v_conf        = DoubleVar(value=0.30)
        self.v_conf_thresh = DoubleVar(value=0.25)
        self.v_iou         = DoubleVar(value=0.45)
        self.v_subfolder   = BooleanVar(value=False)
        self.v_line_width  = IntVar(value=2)
        self._labels_var   = StringVar(value="car,lp")
        self._cur_class    = IntVar(value=0)
        self._flt_class    = StringVar(value="Tất cả")
        self._flt_ndet_min = StringVar(); self._flt_ndet_max = StringVar()
        self._flt_area_min = StringVar(); self._flt_area_max = StringVar()
        self._flt_w_min    = StringVar(); self._flt_w_max    = StringVar()
        self._flt_h_min    = StringVar(); self._flt_h_max    = StringVar()

        for key, var in [
            ("dl.folder", self.v_folder), ("dl.lbl_dir", self.v_lbl_dir),
            ("dl.model",  self.v_model),  ("dl.conf",    self.v_conf),
            ("dl.iou",    self.v_iou),    ("dl.lw",      self.v_line_width),
            ("dl.labels", self._labels_var),
        ]:
            _bind_cfg(key, var)

        self._build()
        self._bind_shortcuts()

    # ── Build ──────────────────────────────────────────────────────────────

    def _build(self):
        self._build_toolbar()
        paned = PanedWindow(self, orient=HORIZONTAL, bg=BG,
                            sashwidth=4, sashrelief=FLAT)
        paned.pack(fill=BOTH, expand=True)
        self._build_left(paned)
        self._build_canvas(paned)

    def _build_toolbar(self):
        tb = Frame(self, bg=CARD, pady=4, padx=8)
        tb.pack(fill=X)
        # Model
        Label(tb, text="Model:", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        model_cb = ttk.Combobox(tb, textvariable=self.v_model,
                                font=F_MONO, width=30)
        model_cb.pack(side=LEFT, padx=(2, 4))
        _bind_history("history.dl.model", model_cb)
        Button(tb, text="Chọn…", font=F_MAIN, bg=ACCENT2, fg=TEXT,
               relief=FLAT, cursor="hand2",
               command=lambda: self._pick_model(model_cb)).pack(side=LEFT)
        # Conf / IOU
        for lbl, var, fmt in [("Conf:", self.v_conf, ".2f"),
                               ("IoU:", self.v_iou, ".2f")]:
            Label(tb, text=lbl, bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT, padx=(10, 2))
            Scale(tb, variable=var, from_=0.01, to=0.99, resolution=0.01,
                  orient=HORIZONTAL, length=80, bg=CARD, fg=TEXT,
                  highlightthickness=0, troughcolor="#0d0d1a",
                  activebackground=ACCENT, sliderlength=12, showvalue=True).pack(side=LEFT)
        # Detect button
        self._btn_detect = Button(tb, text="▶ Detect (F5)", font=F_BOLD,
                                  bg=ACCENT, fg="white", relief=FLAT,
                                  cursor="hand2", padx=8,
                                  command=self._detect_folder)
        self._btn_detect.pack(side=LEFT, padx=(14, 4))
        Button(tb, text="■ Stop", font=F_MAIN, bg="#444", fg=TEXT,
               relief=FLAT, cursor="hand2",
               command=lambda: self._det_stop.set()).pack(side=LEFT)
        # Status
        self._lbl_status = Label(tb, text="", bg=CARD, fg=DIM, font=F_MONO)
        self._lbl_status.pack(side=LEFT, padx=12)

    def _build_left(self, paned):
        left = Frame(paned, bg=BG, width=300)
        paned.add(left, minsize=220)

        # Folder rows
        f_fold = Frame(left, bg=CARD, padx=6, pady=4)
        f_fold.pack(fill=X, pady=(0, 1))
        Label(f_fold, text="Ảnh:", bg=CARD, fg=DIM, font=F_MAIN).grid(row=0, column=0, sticky=W)
        e = ttk.Combobox(f_fold, textvariable=self.v_folder, font=F_MONO, width=24)
        e.grid(row=0, column=1, sticky=EW)
        _bind_history("history.dl.folder", e)
        Button(f_fold, text="…", font=F_MAIN, bg=ACCENT2, fg=TEXT, relief=FLAT,
               command=lambda: self._pick_folder(self.v_folder, e)).grid(row=0, column=2)
        Button(f_fold, text="📂 Load", font=F_MAIN, bg=ACCENT, fg="white",
               relief=FLAT, cursor="hand2",
               command=self._load_folder).grid(row=0, column=3, padx=(4, 0))
        f_fold.columnconfigure(1, weight=1)

        Label(f_fold, text="Nhãn:", bg=CARD, fg=DIM, font=F_MAIN).grid(row=1, column=0, sticky=W)
        e2 = ttk.Combobox(f_fold, textvariable=self.v_lbl_dir, font=F_MONO, width=24)
        e2.grid(row=1, column=1, columnspan=3, sticky=EW)
        _bind_history("history.dl.lbl_dir", e2)

        # Labels string
        f_lbl = Frame(left, bg=CARD, padx=6, pady=2)
        f_lbl.pack(fill=X, pady=(0, 1))
        Label(f_lbl, text="Classes:", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        Entry(f_lbl, textvariable=self._labels_var, bg="#1a1a2e", fg=TEXT,
              insertbackground=TEXT, font=F_MONO, relief=FLAT).pack(side=LEFT, fill=X, expand=True)
        self._labels_var.trace_add("write", lambda *_: self._refresh_class_combo())

        # Filter section
        self._build_filter(left)

        # Filmstrip
        self._filmstrip = FilmstripPanel(
            left, get_thumb=self._get_thumb, on_select=self._load_image)
        self._filmstrip.pack(fill=BOTH, expand=True)

    def _build_filter(self, parent):
        f = Frame(parent, bg=CARD, padx=6, pady=4)
        f.pack(fill=X, pady=(0, 1))
        Label(f, text="── Bộ lọc ──", bg=CARD, fg=DIM, font=F_MAIN).grid(
            row=0, column=0, columnspan=4, sticky=W)

        # Class combo
        Label(f, text="Class:", bg=CARD, fg=DIM, font=F_MAIN).grid(row=1, column=0, sticky=W)
        self._flt_cls_combo = ttk.Combobox(f, textvariable=self._flt_class,
                                            values=["Tất cả", "Không detect"],
                                            state="readonly", width=14, font=F_MAIN)
        self._flt_cls_combo.grid(row=1, column=1, columnspan=3, sticky=EW, pady=1)
        self._flt_class.trace_add("write", lambda *_: self._schedule_filter())

        # Size / W / H filters (compact 2-col pairs)
        pairs = [("Số bbox:", self._flt_ndet_min, self._flt_ndet_max),
                 ("Diện tích:", self._flt_area_min, self._flt_area_max),
                 ("Rộng px:", self._flt_w_min, self._flt_w_max),
                 ("Cao px:", self._flt_h_min, self._flt_h_max)]
        for row_off, (lbl, v_min, v_max) in enumerate(pairs, start=2):
            Label(f, text=lbl, bg=CARD, fg=DIM, font=F_MAIN).grid(
                row=row_off, column=0, sticky=W)
            Entry(f, textvariable=v_min, width=5, bg="#1a1a2e", fg=TEXT,
                  insertbackground=TEXT, font=F_MONO, relief=FLAT).grid(
                row=row_off, column=1, sticky=EW)
            Label(f, text="–", bg=CARD, fg=DIM, font=F_MAIN).grid(row=row_off, column=2)
            Entry(f, textvariable=v_max, width=5, bg="#1a1a2e", fg=TEXT,
                  insertbackground=TEXT, font=F_MONO, relief=FLAT).grid(
                row=row_off, column=3, sticky=EW)
            v_min.trace_add("write", lambda *_: self._schedule_filter())
            v_max.trace_add("write", lambda *_: self._schedule_filter())
        f.columnconfigure(1, weight=1); f.columnconfigure(3, weight=1)

        # Must-have / Must-not listboxes
        for title, attr in [("Phải có:", "_must_have_lb"), ("Không có:", "_must_not_lb")]:
            Label(f, text=title, bg=CARD, fg=DIM, font=F_MAIN).grid(
                row=f.grid_size()[1], column=0, columnspan=2, sticky=W)
            lb = Listbox(f, selectmode=MULTIPLE, height=3, exportselection=False,
                         bg="#0d0d1a", fg=TEXT, selectbackground=ACCENT,
                         selectforeground="white", font=F_MONO, relief=FLAT)
            lb.grid(row=f.grid_size()[1], column=0, columnspan=4, sticky=EW)
            lb.bind("<<ListboxSelect>>", lambda *_: self._schedule_filter())
            setattr(self, attr, lb)

        Button(f, text="Xóa bộ lọc", font=F_MAIN, bg=ACCENT2, fg=TEXT,
               relief=FLAT, cursor="hand2",
               command=self._clear_filter).grid(
            row=f.grid_size()[1], column=0, columnspan=4, sticky=EW, pady=(4, 0))

    def _build_canvas(self, paned):
        right = Frame(paned, bg=BG)
        paned.add(right, minsize=400)

        # Canvas toolbar
        ct = Frame(right, bg=CARD, padx=6, pady=2)
        ct.pack(fill=X)
        Label(ct, text="Class:", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        self._cls_combo = ttk.Combobox(ct, textvariable=self._cur_class,
                                        state="readonly", width=20, font=F_MAIN)
        self._cls_combo.pack(side=LEFT, padx=(2, 8))
        self._refresh_class_combo()

        for txt, cmd in [("+ Lưu (Ctrl+S)", self._save_labels),
                          ("Export cache→txt", self._export_cache),
                          ("← Prev", lambda: self._nav(-1)),
                          ("→ Next", lambda: self._nav(+1))]:
            bg = ACCENT if "Lưu" in txt else ACCENT2
            Button(ct, text=txt, font=F_MAIN, bg=bg, fg="white",
                   relief=FLAT, cursor="hand2", padx=6, command=cmd).pack(side=LEFT, padx=2)

        Label(ct, text="LW:", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT, padx=(10, 2))
        Spinbox(ct, from_=1, to=6, textvariable=self.v_line_width, width=2,
                bg="#1a1a2e", fg=TEXT, font=F_MAIN, relief=FLAT,
                command=lambda: self._render()).pack(side=LEFT)

        self._lbl_img_info = Label(ct, text="", bg=CARD, fg=DIM, font=F_MONO)
        self._lbl_img_info.pack(side=RIGHT, padx=8)

        # Canvas
        self._canvas = Canvas(right, bg="#0d0d1a", cursor="crosshair",
                              highlightthickness=0)
        self._canvas.pack(fill=BOTH, expand=True)

        self._canvas.bind("<Button-1>",         self._on_press)
        self._canvas.bind("<B1-Motion>",        self._on_drag)
        self._canvas.bind("<ButtonRelease-1>",  self._on_release)
        self._canvas.bind("<MouseWheel>",       self._on_zoom_wheel)
        self._canvas.bind("<Button-2>",         self._on_pan_start)
        self._canvas.bind("<B2-Motion>",        self._on_pan_drag)
        self._canvas.bind("<ButtonRelease-2>",  self._on_pan_end)
        self._canvas.bind("<Configure>",
                          lambda _e: self._render() if self._pil_img else None)

    # ── Helpers ────────────────────────────────────────────────────────────

    def _pick_model(self, combo):
        p = filedialog.askopenfilename(
            title="Chọn model YOLO", filetypes=[("PT", "*.pt"), ("All", "*.*")])
        if p:
            self.v_model.set(p)
            _push_history("history.dl.model", p)
            combo["values"] = [p] + list(combo["values"])

    def _pick_folder(self, var, combo):
        p = filedialog.askdirectory(title="Chọn thư mục ảnh")
        if p:
            var.set(p)
            _push_history(f"history.dl.folder", p)
            combo["values"] = [p] + list(combo["values"])

    def _refresh_class_combo(self):
        names = [s.strip() for s in self._labels_var.get().split(",") if s.strip()]
        values = [f"[{i}] {n}" for i, n in enumerate(names)]
        self._cls_combo["values"] = values
        if values and self._cls_combo.get() not in values:
            self._cls_combo.current(0)
        # Update must_have / must_not listboxes
        for lb in (self._must_have_lb, self._must_not_lb):
            lb.delete(0, END)
            for i, n in enumerate(names):
                lb.insert(END, f"[{i}] {n}")
                lb.itemconfig(END, fg=PALETTE[i % len(PALETTE)])
        # Update class filter combo
        self._flt_cls_combo["values"] = (
            ["Tất cả", "Không detect"] + [f"[{i}] {n}" for i, n in enumerate(names)])

    def _get_cur_cid(self) -> int:
        try:
            val = self._cls_combo.get()
            return int(val.split("]")[0].lstrip("["))
        except Exception:
            return 0

    # ── Load folder ────────────────────────────────────────────────────────

    def _load_folder(self):
        folder = self.v_folder.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showwarning("Chú ý", "Chọn thư mục ảnh hợp lệ.")
            return
        exts = set(IMAGE_EXTENSIONS)
        self._files = sorted(
            str(p) for p in Path(folder).rglob("*")
            if p.suffix.lower() in exts
        ) if self.v_subfolder.get() else sorted(
            str(p) for p in Path(folder).iterdir()
            if p.suffix.lower() in exts
        )
        self._det_cache.load_from_disk(folder, self.v_model.get(), self.v_iou.get())
        self._filtered = list(self._files)
        self._filmstrip.load(self._filtered)
        self._lbl_status.config(text=f"{len(self._files)} ảnh")
        if self._files:
            self._load_image(self._files[0])

    # ── Detection ──────────────────────────────────────────────────────────

    def _detect_folder(self):
        if not _YOLO_OK:
            messagebox.showerror("Lỗi", "Cần cài ultralytics: pip install ultralytics")
            return
        model_path = self.v_model.get().strip()
        if not model_path or not os.path.isfile(model_path):
            messagebox.showwarning("Chú ý", "Chọn file model .pt hợp lệ.")
            return
        if not self._files:
            self._load_folder()
        if not self._files:
            return
        if self._det_thread and self._det_thread.is_alive():
            return
        self._det_stop.clear()
        self._btn_detect.config(state=DISABLED)
        self._det_thread = threading.Thread(
            target=self._detect_thread, daemon=True)
        self._det_thread.start()

    def _detect_thread(self):
        try:
            self._model = YOLO(self.v_model.get().strip())
        except Exception as e:
            self.root.after(0, lambda: self._lbl_status.config(text=f"Lỗi model: {e}"))
            self.root.after(0, lambda: self._btn_detect.config(state=NORMAL))
            return

        conf = self.v_conf.get()
        iou  = self.v_iou.get()
        total = len(self._filtered) or len(self._files)
        targets = self._filtered or self._files

        for i, path in enumerate(targets):
            if self._det_stop.is_set():
                break
            if self._det_cache.has(path):
                continue
            try:
                results = self._model(path, conf=conf, iou=iou, verbose=False)
                boxes_obj = results[0].boxes
                box_list, cls_cnt = [], {}
                if boxes_obj is not None and len(boxes_obj):
                    for box in boxes_obj:
                        cid  = int(box.cls[0])
                        cx_n, cy_n, w_n, h_n = (float(v) for v in box.xywhn[0])
                        w_px, h_px = float(box.xywh[0][2]), float(box.xywh[0][3])
                        cf   = float(box.conf[0])
                        box_list.append((cid, cx_n, cy_n, w_n, h_n, w_px, h_px, cf))
                        cls_cnt[cid] = cls_cnt.get(cid, 0) + 1
                self._det_cache.put(path, len(box_list), cls_cnt, box_list)
            except Exception:
                pass

            if i % 5 == 0:
                pct = int((i + 1) * 100 / total)
                self.root.after(0, lambda p=pct, n=i+1:
                    self._lbl_status.config(text=f"{n}/{total} ({p}%)"))
                self.root.after(0, self._filmstrip.invalidate_cache)

        folder = self.v_folder.get().strip()
        self._det_cache.save_to_disk(folder, self.v_model.get(), conf, iou)
        self.root.after(0, lambda: self._lbl_status.config(
            text=f"Xong — {len(self._det_cache)} ảnh đã detect"))
        self.root.after(0, lambda: self._btn_detect.config(state=NORMAL))
        self.root.after(0, lambda: self._filmstrip.invalidate_cache())
        self.root.after(0, lambda: self._filmstrip.load(
            self._filtered or self._files, self._current))
        self.root.after(0, self._update_class_filter_values)

    def _update_class_filter_values(self):
        counts = self._det_cache.all_class_counts()
        names  = [s.strip() for s in self._labels_var.get().split(",") if s.strip()]
        extras = [f"[{cid}] {names[cid] if cid < len(names) else str(cid)}"
                  for cid in sorted(counts)]
        self._flt_cls_combo["values"] = (
            ["Tất cả", "Không detect"] + extras)

    # ── Load image + render ────────────────────────────────────────────────

    def _load_image(self, path: str):
        if self._modified and self._current:
            self._save_labels()
        pil = open_image_safe(path)
        if pil is None:
            return
        self._current  = path
        self._pil_img  = pil
        self._zoom_reset()
        self._render_nw_nh  = None
        self._render_cached = None
        # Load boxes: prefer .txt, fallback to cache
        lbl_dir = self.v_lbl_dir.get().strip()
        lp = label_path_for(path, lbl_dir)
        if lp.exists():
            self._boxes = [list(b) for b in read_yolo_normalized(lp)]
        else:
            data = self._det_cache.get(path)
            if data and data["n"] > 0:
                ct = self.v_conf_thresh.get()
                self._boxes = [list(b[:5]) for b in data["boxes"]
                               if len(b) > 7 and float(b[7]) >= ct]
            else:
                self._boxes = []
        self._selected = -1
        self._modified = False
        self._filmstrip.set_current(path)
        iw, ih = pil.size
        nb = len(self._boxes)
        self._lbl_img_info.config(text=f"{Path(path).name}  {iw}×{ih}  {nb}bbox")
        self._render()

    def _render(self, resample=None):
        if not _PIL_OK or self._pil_img is None:
            return
        from PIL import Image as _I
        scale, nw, nh, off_x, off_y = self._calc_zoom_offsets()
        if self._render_nw_nh != (nw, nh) or resample:
            rs = resample or _I.LANCZOS
            self._render_cached = self._pil_img.resize((nw, nh), rs)
            self._render_nw_nh  = (nw, nh)
        self._photo_ref = ImageTk.PhotoImage(self._render_cached)
        self._canvas.delete("all")
        self._canvas.create_image(off_x, off_y, anchor=NW, image=self._photo_ref)
        self._draw_boxes_canvas(off_x, off_y, scale)

    def _draw_boxes_canvas(self, off_x: int, off_y: int, scale: float):
        if not self._pil_img:
            return
        iw, ih = self._pil_img.size
        lw = max(1, self.v_line_width.get())
        for i, box in enumerate(self._boxes):
            cid = int(box[0])
            cx_n, cy_n, w_n, h_n = float(box[1]), float(box[2]), float(box[3]), float(box[4])
            x1c = int((cx_n - w_n/2) * iw * scale) + off_x
            y1c = int((cy_n - h_n/2) * ih * scale) + off_y
            x2c = int((cx_n + w_n/2) * iw * scale) + off_x
            y2c = int((cy_n + h_n/2) * ih * scale) + off_y
            color = PALETTE[cid % len(PALETTE)]
            width = lw + 2 if i == self._selected else lw
            self._canvas.create_rectangle(x1c, y1c, x2c, y2c,
                                           outline=color, width=width, tags=f"b{i}")

    # ── Thumbnail for filmstrip ────────────────────────────────────────────

    def _get_thumb(self, path: str, tw: int, th: int):
        pil = open_image_safe(path)
        if pil is None:
            return None
        ct = self.v_conf_thresh.get()
        data = self._det_cache.get(path)
        if data and data["n"] > 0:
            boxes = [b for b in data["boxes"] if len(b) > 7 and float(b[7]) >= ct]
            if boxes:
                pil = draw_bboxes_thumb(pil, boxes, conf_thresh=ct)
        else:
            lbl_dir = self.v_lbl_dir.get().strip()
            lp = label_path_for(path, lbl_dir)
            if lp.exists():
                norm = read_yolo_normalized(lp)
                if norm:
                    pil = draw_bboxes_thumb(pil, norm)
        return make_padded_thumb(pil, tw, th)

    # ── BBox editing ───────────────────────────────────────────────────────

    def _canvas_to_norm(self, cx: int, cy: int) -> tuple:
        if not self._pil_img or self._scale == 0:
            return 0.0, 0.0
        iw, ih = self._pil_img.size
        x = max(0.0, min(1.0, (cx - self._off_x) / (iw * self._scale)))
        y = max(0.0, min(1.0, (cy - self._off_y) / (ih * self._scale)))
        return x, y

    def _hit_test(self, cx: int, cy: int) -> int:
        if not self._pil_img or self._scale == 0:
            return -1
        iw, ih = self._pil_img.size
        sc = self._scale
        for i, box in enumerate(self._boxes):
            cx_n, cy_n, w_n, h_n = float(box[1]), float(box[2]), float(box[3]), float(box[4])
            x1c = int((cx_n - w_n/2) * iw * sc) + self._off_x
            y1c = int((cy_n - h_n/2) * ih * sc) + self._off_y
            x2c = int((cx_n + w_n/2) * iw * sc) + self._off_x
            y2c = int((cy_n + h_n/2) * ih * sc) + self._off_y
            if x1c <= cx <= x2c and y1c <= cy <= y2c:
                return i
        return -1

    def _on_press(self, event):
        if self._pil_img is None:
            return
        hit = self._hit_test(event.x, event.y)
        if hit >= 0:
            self._selected = hit
            self._drawing  = False
            self._draw_boxes_canvas(self._off_x, self._off_y, self._scale)
        else:
            self._selected = -1
            self._drawing  = True
            self._draw_start = (event.x, event.y)
            self._draw_rect_id = None

    def _on_drag(self, event):
        if not self._drawing:
            return
        if self._draw_rect_id:
            self._canvas.delete(self._draw_rect_id)
        x1, y1 = self._draw_start
        self._draw_rect_id = self._canvas.create_rectangle(
            x1, y1, event.x, event.y,
            outline=PALETTE[self._get_cur_cid() % len(PALETTE)],
            width=2, dash=(4, 2))

    def _on_release(self, event):
        if not self._drawing:
            return
        self._drawing = False
        if self._draw_rect_id:
            self._canvas.delete(self._draw_rect_id)
            self._draw_rect_id = None
        x1s, y1s = self._draw_start
        x2e, y2e = event.x, event.y
        if abs(x2e - x1s) < 5 or abs(y2e - y1s) < 5:
            return
        x1n, y1n = self._canvas_to_norm(min(x1s, x2e), min(y1s, y2e))
        x2n, y2n = self._canvas_to_norm(max(x1s, x2e), max(y1s, y2e))
        cid = self._get_cur_cid()
        self._boxes.append([cid, (x1n+x2n)/2, (y1n+y2n)/2, x2n-x1n, y2n-y1n])
        self._selected = len(self._boxes) - 1
        self._modified = True
        self._render()

    # ── Filter ─────────────────────────────────────────────────────────────

    def _schedule_filter(self):
        if self._filter_after:
            self.after_cancel(self._filter_after)
        self._filter_after = self.after(300, self._apply_filter)

    def _apply_filter(self):
        def _fv(v):
            s = v.get().strip()
            try: return float(s) if s else None
            except ValueError: return None

        must_have = {int(self._must_have_lb.get(i).split("]")[0].lstrip("["))
                     for i in self._must_have_lb.curselection()} or None
        must_not  = {int(self._must_not_lb.get(i).split("]")[0].lstrip("["))
                     for i in self._must_not_lb.curselection()} or None

        self._filtered = self._det_cache.filter_files(
            self._files,
            cls_filter=self._flt_class.get(),
            ndet_min=_fv(self._flt_ndet_min), ndet_max=_fv(self._flt_ndet_max),
            area_min=_fv(self._flt_area_min), area_max=_fv(self._flt_area_max),
            w_min=_fv(self._flt_w_min),       w_max=_fv(self._flt_w_max),
            h_min=_fv(self._flt_h_min),       h_max=_fv(self._flt_h_max),
            must_have=must_have, must_not=must_not,
        )
        self._filmstrip.load(self._filtered, self._current)
        self._lbl_status.config(text=f"{len(self._filtered)}/{len(self._files)} ảnh")

    def _clear_filter(self):
        self._flt_class.set("Tất cả")
        for v in (self._flt_ndet_min, self._flt_ndet_max,
                  self._flt_area_min, self._flt_area_max,
                  self._flt_w_min,    self._flt_w_max,
                  self._flt_h_min,    self._flt_h_max):
            v.set("")
        self._must_have_lb.selection_clear(0, END)
        self._must_not_lb.selection_clear(0, END)
        self._filtered = list(self._files)
        self._filmstrip.load(self._filtered, self._current)

    # ── Save / Export ──────────────────────────────────────────────────────

    def _save_labels(self):
        if not self._current:
            return
        lbl_dir = self.v_lbl_dir.get().strip()
        lp = label_path_for(self._current, lbl_dir)
        lp.parent.mkdir(parents=True, exist_ok=True)
        lines = []
        for box in self._boxes:
            cid, cx, cy, w, h = int(box[0]), float(box[1]), float(box[2]), float(box[3]), float(box[4])
            lines.append(f"{cid} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")
        lp.write_text("\n".join(lines), encoding="utf-8")
        self._modified = False
        self._filmstrip.invalidate_cache(self._current)
        self._lbl_status.config(text=f"Đã lưu {lp.name}")

    def _export_cache(self):
        """Ghi kết quả detect cache → .txt cho toàn bộ file đã detect."""
        ct = self.v_conf_thresh.get()
        lbl_dir = self.v_lbl_dir.get().strip()
        count = 0
        for path in self._files:
            data = self._det_cache.get(path)
            if not data or not data["boxes"]:
                continue
            boxes = [b[:5] for b in data["boxes"]
                     if len(b) > 7 and float(b[7]) >= ct]
            if not boxes:
                continue
            lp = label_path_for(path, lbl_dir)
            lp.parent.mkdir(parents=True, exist_ok=True)
            lines = [f"{int(b[0])} {float(b[1]):.6f} {float(b[2]):.6f} "
                     f"{float(b[3]):.6f} {float(b[4]):.6f}" for b in boxes]
            lp.write_text("\n".join(lines), encoding="utf-8")
            count += 1
        self._filmstrip.invalidate_cache()
        self._filmstrip.load(self._filtered or self._files, self._current)
        messagebox.showinfo("Export", f"Đã xuất {count} file nhãn.")

    # ── Navigation ─────────────────────────────────────────────────────────

    def _nav(self, delta: int):
        lst = self._filtered or self._files
        if not lst:
            return
        try:
            idx = lst.index(self._current)
        except ValueError:
            idx = -1
        nxt = max(0, min(len(lst) - 1, idx + delta))
        self._load_image(lst[nxt])

    # ── Shortcuts ──────────────────────────────────────────────────────────

    def _bind_shortcuts(self):
        self.root.bind_all("<F5>",         lambda _e: self._detect_folder())
        self.root.bind_all("<Escape>",     lambda _e: self._det_stop.set())
        self.root.bind_all("<Control-s>",  lambda _e: self._save_labels())
        self.root.bind_all("<Control-o>",  lambda _e: self._load_folder())
        self._canvas.bind("<Delete>",      self._on_delete)
        self._canvas.bind("<BackSpace>",   self._on_delete)
        self._canvas.bind("<Key>",         self._on_numkey)

    def _on_delete(self, _event):
        if self._selected < 0 or not self._boxes:
            return
        self._boxes.pop(self._selected)
        self._selected = -1
        self._modified = True
        self._render()

    def _on_numkey(self, event):
        if not event.char.isdigit():
            return
        n = int(event.char)
        names = [s.strip() for s in self._labels_var.get().split(",") if s.strip()]
        if n < len(names) and self._selected >= 0:
            self._boxes[self._selected][0] = n
            self._modified = True
            self._render()
        elif n < len(names):
            self._cur_class.set(n)
            vals = self._cls_combo["values"]
            if n < len(vals):
                self._cls_combo.current(n)
