import csv
import threading
from pathlib import Path
from tkinter import *
from tkinter import filedialog, messagebox, ttk

from .constants import (
    BG, CARD, ACCENT, ACCENT2, TEXT, DIM, SUCCESS,
    F_MAIN, F_BOLD, F_MONO, IMAGE_EXTENSIONS,
)
from .settings import _bind_cfg, _cfg_dir
from .imports import _PADDLE_OK, _PaddleOCR, _DND_OK, _dnd_mod


class OcrTab(Frame):
    _LANGS = [("Tiếng Việt", "vi"), ("English", "en"), ("Tiếng Trung", "ch")]

    def __init__(self, master, root):
        super().__init__(master, bg=BG)
        self.root = root
        self._files   = []
        self._results = []
        self._raw_detections = []
        self._ocr_engine = None
        self._running = False
        self._cur_preview = None
        self._roi = None

        self.v_lang       = StringVar(value="vi")
        self.v_use_gpu    = BooleanVar(value=False)
        self.v_angle      = BooleanVar(value=True)
        self.v_clean      = BooleanVar(value=True)
        self.v_out_dir    = StringVar()
        self.v_gt_dir     = StringVar()
        self.v_conf_thresh = DoubleVar(value=0.0)
        _bind_cfg("ocr.out_dir", self.v_out_dir)

        self._build()

    def _build(self):
        top = Frame(self, bg=CARD, padx=16, pady=8)
        top.pack(fill=X)
        Label(top, text="PaddleOCR PP-OCRv5 — Nhận dạng văn bản trong ảnh",
              bg=CARD, fg=TEXT, font=F_BOLD).pack(side=LEFT)
        Label(top, text="PP-OCRv5", bg=ACCENT, fg="white",
              font=("Segoe UI Semibold", 9), padx=6, pady=2).pack(side=LEFT, padx=10)
        if not _PADDLE_OK:
            Label(top,
                  text="⚠  paddleocr chưa cài  →  pip install paddleocr paddlepaddle",
                  bg=CARD, fg="#ff8844", font=("Segoe UI", 9)).pack(side=LEFT, padx=16)

        main = Frame(self, bg=BG)
        main.pack(fill=BOTH, expand=True, padx=8, pady=8)

        left = Frame(main, bg=BG, width=340)
        left.pack(side=LEFT, fill=Y, padx=(0, 6))
        left.pack_propagate(False)

        right = Frame(main, bg=BG)
        right.pack(side=LEFT, fill=BOTH, expand=True)

        self._build_left(left)
        self._build_right(right)

    def _build_left(self, parent):
        dz_wrap = Frame(parent, bg="#111122", bd=2, relief=RIDGE)
        dz_wrap.pack(fill=X, pady=(0, 5))
        self.drop_zone = Label(
            dz_wrap,
            text="📂  Kéo thả ảnh hoặc folder vào đây\n(hoặc click để chọn ảnh)",
            bg="#111122", fg=DIM, font=("Segoe UI", 10),
            pady=24, cursor="hand2", justify=CENTER, wraplength=300)
        self.drop_zone.pack(fill=X)
        self.drop_zone.bind("<Button-1>", lambda e: self._browse_files())

        if _DND_OK:
            self.drop_zone.drop_target_register(_dnd_mod.DND_FILES)
            self.drop_zone.dnd_bind("<<Drop>>",      self._on_drop)
            self.drop_zone.dnd_bind("<<DragEnter>>", self._on_drag_enter)
            self.drop_zone.dnd_bind("<<DragLeave>>", self._on_drag_leave)

        btn_row = Frame(parent, bg=BG)
        btn_row.pack(fill=X, pady=3)
        Button(btn_row, text="🖼  Chọn ảnh",   command=self._browse_files,
               bg=ACCENT2, fg="white", activebackground=ACCENT, activeforeground="white",
               font=F_BOLD, relief="flat", padx=10, pady=5, cursor="hand2").pack(side=LEFT)
        Button(btn_row, text="📂  Chọn folder", command=self._browse_folder,
               bg=ACCENT2, fg="white", activebackground=ACCENT, activeforeground="white",
               font=F_BOLD, relief="flat", padx=10, pady=5, cursor="hand2").pack(side=LEFT, padx=5)
        Button(btn_row, text="✕  Xóa",         command=self._clear_files,
               bg=CARD, fg=DIM, font=F_MAIN, relief="flat",
               padx=8, pady=5, cursor="hand2").pack(side=LEFT)

        self.lbl_files = Label(parent, text="Chưa chọn ảnh nào.",
                               bg=BG, fg=DIM, font=F_MAIN, anchor=W, wraplength=320)
        self.lbl_files.pack(fill=X, pady=2)

        Frame(parent, bg=ACCENT2, height=1).pack(fill=X, pady=8)

        opt = Frame(parent, bg=BG)
        opt.pack(fill=X)

        rw = Frame(opt, bg=BG)
        rw.pack(fill=X, pady=3)
        Label(rw, text="Ngôn ngữ:", bg=BG, fg=TEXT, font=F_MAIN,
              width=14, anchor=W).pack(side=LEFT)
        for name, val in self._LANGS:
            Radiobutton(rw, text=name, variable=self.v_lang, value=val,
                        bg=BG, fg=TEXT, selectcolor=CARD, activebackground=BG,
                        font=F_MAIN, command=self._invalidate_engine).pack(side=LEFT, padx=(0, 8))

        rw2 = Frame(opt, bg=BG)
        rw2.pack(fill=X, pady=3)
        Label(rw2, text="Tùy chọn:", bg=BG, fg=TEXT, font=F_MAIN,
              width=14, anchor=W).pack(side=LEFT)
        Checkbutton(rw2, text="Dùng GPU", variable=self.v_use_gpu,
                    bg=BG, fg=TEXT, selectcolor=CARD, activebackground=BG,
                    font=F_MAIN, command=self._invalidate_engine).pack(side=LEFT)
        Checkbutton(rw2, text="Nhận dạng góc nghiêng", variable=self.v_angle,
                    bg=BG, fg=TEXT, selectcolor=CARD, activebackground=BG,
                    font=F_MAIN, command=self._invalidate_engine).pack(side=LEFT, padx=6)

        rw3 = Frame(opt, bg=BG)
        rw3.pack(fill=X, pady=3)
        Label(rw3, text="Hậu xử lý:", bg=BG, fg=TEXT, font=F_MAIN,
              width=14, anchor=W).pack(side=LEFT)
        Checkbutton(rw3, text="Bỏ ký tự đặc biệt  (- . , space …)",
                    variable=self.v_clean,
                    bg=BG, fg=TEXT, selectcolor=CARD,
                    activebackground=BG, font=F_MAIN).pack(side=LEFT)

        Frame(parent, bg=ACCENT2, height=1).pack(fill=X, pady=8)

        conf_row = Frame(parent, bg=BG)
        conf_row.pack(fill=X, pady=3)
        Label(conf_row, text="Ngưỡng confidence:", bg=BG, fg=TEXT,
              font=F_MAIN, anchor=W).pack(side=LEFT)
        self.lbl_conf_val = Label(conf_row, text="0.00", bg=BG, fg=ACCENT,
                                  font=F_MONO, width=5)
        self.lbl_conf_val.pack(side=RIGHT)
        self.scale_conf = Scale(
            parent, variable=self.v_conf_thresh,
            from_=0.0, to=1.0, resolution=0.01,
            orient=HORIZONTAL, bg=BG, fg=TEXT,
            troughcolor=CARD, highlightthickness=0,
            activebackground=ACCENT, showvalue=False,
            command=self._on_conf_change)
        self.scale_conf.pack(fill=X, pady=(0, 2))
        self.lbl_filtered = Label(parent, text="", bg=BG, fg=DIM,
                                  font=("Segoe UI", 9), anchor=W)
        self.lbl_filtered.pack(fill=X)

        Frame(parent, bg=ACCENT2, height=1).pack(fill=X, pady=8)

        Label(parent, text="Output folder (để trống = ghi cạnh ảnh):",
              bg=BG, fg=TEXT, font=F_MAIN, anchor=W).pack(fill=X)
        orw = Frame(parent, bg=BG)
        orw.pack(fill=X, pady=2)
        Button(orw, text="📁", command=self._browse_out,
               bg=CARD, fg=TEXT, relief="flat", padx=6, pady=3,
               cursor="hand2").pack(side=LEFT)
        Entry(orw, textvariable=self.v_out_dir, bg="#16162a", fg=TEXT,
              insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4).pack(
              side=LEFT, fill=X, expand=True, padx=4)
        Button(orw, text="✕", command=lambda: self.v_out_dir.set(""),
               bg=CARD, fg=DIM, relief="flat", padx=6, pady=3,
               cursor="hand2").pack(side=LEFT)

        Frame(parent, bg=ACCENT2, height=1).pack(fill=X, pady=8)

        Label(parent, text="So sánh GT — folder chứa .txt GT:",
              bg=BG, fg=TEXT, font=F_MAIN, anchor=W).pack(fill=X)
        grw = Frame(parent, bg=BG)
        grw.pack(fill=X, pady=2)
        Button(grw, text="📁", command=self._browse_gt,
               bg=CARD, fg=TEXT, relief="flat", padx=6, pady=3,
               cursor="hand2").pack(side=LEFT)
        Entry(grw, textvariable=self.v_gt_dir, bg="#16162a", fg=TEXT,
              insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4).pack(
              side=LEFT, fill=X, expand=True, padx=4)
        Button(grw, text="✕", command=lambda: self.v_gt_dir.set(""),
               bg=CARD, fg=DIM, relief="flat", padx=6, pady=3,
               cursor="hand2").pack(side=LEFT)
        self.btn_compare = Button(parent, text="📊  So sánh GT",
                                  command=self._compare_gt,
                                  bg=ACCENT2, fg="white",
                                  activebackground=ACCENT, activeforeground="white",
                                  font=F_BOLD, relief="flat", padx=10, pady=5,
                                  cursor="hand2")
        self.btn_compare.pack(fill=X, pady=(4, 0))

        Frame(parent, bg=ACCENT2, height=1).pack(fill=X, pady=8)

        self.pb = ttk.Progressbar(parent, style="K.Horizontal.TProgressbar",
                                  length=300, mode="determinate")
        self.pb.pack(fill=X, pady=2)
        self.lbl_prog = Label(parent, text="", bg=BG, fg=DIM,
                              font=("Segoe UI", 9), anchor=W)
        self.lbl_prog.pack(fill=X)

        self.btn_run = Button(parent, text="▶   Nhận dạng",
                              command=self._start_ocr,
                              bg=SUCCESS, fg="white",
                              activebackground="#3d9140", activeforeground="white",
                              font=F_BOLD, relief="flat",
                              padx=16, pady=8, cursor="hand2")
        self.btn_run.pack(fill=X, pady=(8, 0))

    def _build_right(self, parent):
        hdr = Frame(parent, bg=CARD, padx=10, pady=6)
        hdr.pack(fill=X, pady=(0, 4))
        Label(hdr, text="Kết quả nhận dạng", bg=CARD, fg=TEXT,
              font=F_BOLD).pack(side=LEFT)
        self.lbl_count = Label(hdr, text="", bg=CARD, fg=DIM, font=("Segoe UI", 9))
        self.lbl_count.pack(side=LEFT, padx=12)
        self.lbl_stats = Label(hdr, text="", bg=CARD, fg=DIM, font=("Segoe UI", 9))
        self.lbl_stats.pack(side=LEFT)

        leg = Frame(hdr, bg=CARD)
        leg.pack(side=RIGHT)
        for txt, bg, fg in [("≥90%", "#1a3a1a", "#6ddd6d"),
                             ("70–89%", "#3a2e00", "#ddbb00"),
                             ("<70%", "#3a1010", "#dd6060")]:
            Label(leg, text=txt, bg=bg, fg=fg,
                  font=("Segoe UI", 8), padx=5, pady=1).pack(side=LEFT, padx=2)

        tbl = Frame(parent, bg="#111122")
        tbl.pack(fill=BOTH, expand=True)

        s = ttk.Style()
        s.configure("OCR.Treeview",
                    background="#16162a", foreground=TEXT,
                    fieldbackground="#16162a", rowheight=28, font=("Consolas", 10))
        s.configure("OCR.Treeview.Heading",
                    background=ACCENT2, foreground="white",
                    relief="flat", font=("Segoe UI Semibold", 9))
        s.map("OCR.Treeview",
              background=[("selected", ACCENT2)],
              foreground=[("selected", "white")])

        cols = ("file", "text", "conf")
        self.tree = ttk.Treeview(tbl, columns=cols, show="headings",
                                 style="OCR.Treeview", selectmode="browse")
        self.tree.heading("file", text="Tên file", anchor=W)
        self.tree.heading("text", text="Văn bản nhận dạng", anchor=W)
        self.tree.heading("conf", text="Tin cậy", anchor=CENTER)
        self.tree.column("file", width=150, minwidth=90,  stretch=False)
        self.tree.column("text", width=260, minwidth=120, stretch=True)
        self.tree.column("conf", width=70,  minwidth=55,  stretch=False, anchor=CENTER)
        self.tree.tag_configure("hi",  background="#0e2a0e", foreground="#7ddd7d")
        self.tree.tag_configure("mid", background="#2e2600", foreground="#ddbb44")
        self.tree.tag_configure("lo",  background="#2e0e0e", foreground="#dd7070")
        self.tree.tag_configure("err", background="#3a0a0a", foreground="#ff4444")

        vsb = ttk.Scrollbar(tbl, orient=VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side=RIGHT, fill=Y)
        self.tree.pack(fill=BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>",         self._on_edit)

        pf = Frame(parent, bg="#0d0d1e", bd=0)
        pf.pack(fill=X, pady=(4, 0))
        prev_hdr = Frame(pf, bg="#0d0d1e")
        prev_hdr.pack(fill=X, padx=8, pady=(4, 0))
        Label(prev_hdr, text="Xem trước", bg="#0d0d1e", fg=DIM,
              font=("Segoe UI", 9)).pack(side=LEFT)
        self.lbl_prev_text = Label(prev_hdr, text="", bg="#0d0d1e",
                                   fg=ACCENT, font=("Consolas", 11, "bold"))
        self.lbl_prev_text.pack(side=LEFT, padx=12)
        self.btn_roi = Button(prev_hdr, text="✂  Chọn vùng ROI",
                              command=self._open_roi_selector,
                              bg=CARD, fg=TEXT, font=F_MAIN, relief="flat",
                              padx=8, pady=2, cursor="hand2")
        self.btn_roi.pack(side=RIGHT, padx=4)
        self.lbl_roi = Label(prev_hdr, text="", bg="#0d0d1e", fg=DIM,
                             font=("Segoe UI", 9))
        self.lbl_roi.pack(side=RIGHT, padx=4)
        self.canvas_prev = Canvas(pf, bg="#0a0a18", height=155, highlightthickness=0)
        self.canvas_prev.pack(fill=X, padx=6, pady=(2, 6))

        Frame(parent, bg=ACCENT2, height=1).pack(fill=X, pady=4)
        brw = Frame(parent, bg=BG)
        brw.pack(fill=X)
        Button(brw, text="💾  Xuất gt.txt",
               command=self._export_gt,
               bg=ACCENT, fg="white", activebackground="#c04010", activeforeground="white",
               font=F_BOLD, relief="flat", padx=14, pady=6, cursor="hand2").pack(side=LEFT)
        Button(brw, text="📋  Copy tất cả",
               command=self._copy_results,
               bg=CARD, fg=TEXT, font=F_MAIN, relief="flat",
               padx=10, pady=6, cursor="hand2").pack(side=LEFT, padx=6)
        Button(brw, text="📊  Xuất CSV",
               command=self._export_csv,
               bg=ACCENT2, fg="white",
               activebackground=ACCENT, activeforeground="white",
               font=F_BOLD, relief="flat", padx=10, pady=6, cursor="hand2").pack(side=LEFT)
        Button(brw, text="🗑  Xóa kết quả",
               command=self._clear_results,
               bg=CARD, fg=DIM, font=F_MAIN, relief="flat",
               padx=10, pady=6, cursor="hand2").pack(side=LEFT, padx=6)

        self.lbl_status = Label(parent, text="", bg=BG, fg=DIM,
                                font=("Segoe UI", 9), anchor=W)
        self.lbl_status.pack(fill=X, pady=(2, 0))

    def _on_drag_enter(self, event):
        self.drop_zone.config(bg="#252540", fg=ACCENT)

    def _on_drag_leave(self, event):
        self.drop_zone.config(bg="#111122", fg=DIM)

    def _on_drop(self, event):
        self.drop_zone.config(bg="#111122", fg=DIM)
        import re
        parts = re.findall(r'\{[^}]+\}|[^\s]+', event.data)
        self._add_paths([p.strip("{}") for p in parts])

    def _browse_files(self):
        paths = filedialog.askopenfilenames(
            title="Chọn ảnh",
            filetypes=[("Image files",
                        " ".join(f"*{e}" for e in IMAGE_EXTENSIONS)),
                       ("All files", "*.*")])
        if paths:
            self._add_paths(list(paths))

    def _browse_folder(self):
        folder = filedialog.askdirectory(title="Chọn folder ảnh")
        if folder:
            self._add_paths([folder])

    def _browse_out(self):
        folder = filedialog.askdirectory(title="Chọn folder output",
                                         initialdir=_cfg_dir("ocr.out_dir"))
        if folder:
            self.v_out_dir.set(folder)

    def _add_paths(self, paths):
        for p in paths:
            p = Path(p)
            if p.is_dir():
                for img in sorted(p.rglob("*")):
                    if img.suffix.lower() in IMAGE_EXTENSIONS and img not in self._files:
                        self._files.append(img)
            elif p.suffix.lower() in IMAGE_EXTENSIONS and p not in self._files:
                self._files.append(p)
        self._update_file_label()

    def _clear_files(self):
        self._files.clear()
        self._update_file_label()

    def _update_file_label(self):
        n = len(self._files)
        if n == 0:
            self.lbl_files.config(text="Chưa chọn ảnh nào.", fg=DIM)
            self.drop_zone.config(
                text="📂  Kéo thả ảnh hoặc folder vào đây\n(hoặc click để chọn ảnh)",
                fg=DIM)
        else:
            dirs = len({f.parent for f in self._files})
            self.lbl_files.config(text=f"Đã chọn {n} ảnh từ {dirs} folder.", fg=TEXT)
            self.drop_zone.config(
                text=f"✅  {n} ảnh đã sẵn sàng\n(Kéo thả thêm để bổ sung)",
                fg=SUCCESS)

    def _invalidate_engine(self):
        self._ocr_engine = None

    _REC_V5 = {
        "vi": "latin_PP-OCRv5_mobile_rec",
        "en": "en_PP-OCRv5_mobile_rec",
        "ch": "PP-OCRv5_server_rec",
    }

    def _get_engine(self):
        if self._ocr_engine is None:
            if not _PADDLE_OK:
                raise RuntimeError(
                    "PaddleOCR chưa cài.\nChạy lệnh:\n\n"
                    "  pip install paddleocr paddlepaddle\n\n"
                    "rồi khởi động lại ứng dụng.")
            lang    = self.v_lang.get()
            rec     = self._REC_V5.get(lang, "latin_PP-OCRv5_mobile_rec")
            use_gpu = self.v_use_gpu.get()
            try:
                import paddle
                gpu_ok = (paddle.device.is_compiled_with_cuda() and
                          paddle.device.cuda.device_count() > 0)
            except Exception:
                gpu_ok = False
            if use_gpu and not gpu_ok:
                self.after(0, lambda: messagebox.showwarning(
                    "GPU không khả dụng",
                    "PaddlePaddle CPU-only đang được dùng.\n\n"
                    "Để dùng GPU hãy cài:\n  pip install paddlepaddle-gpu\n\n"
                    "Sẽ chạy bằng CPU.", parent=self))
                use_gpu = False
            kwargs = dict(
                text_detection_model_name="PP-OCRv5_mobile_det",
                text_recognition_model_name=rec,
                use_textline_orientation=self.v_angle.get(),
                text_det_thresh=0.2,
                text_det_box_thresh=0.5,
                text_det_unclip_ratio=1.8,
            )
            if use_gpu:
                kwargs["device"] = "gpu"
            else:
                kwargs["enable_mkldnn"] = False
            self._ocr_engine = _PaddleOCR(**kwargs)
        return self._ocr_engine

    def _start_ocr(self):
        if self._running: return
        if not self._files:
            messagebox.showwarning("Chưa chọn ảnh",
                                   "Hãy chọn ít nhất một ảnh.", parent=self); return
        if not _PADDLE_OK:
            messagebox.showerror(
                "Thiếu thư viện",
                "PaddleOCR chưa được cài đặt.\n\n"
                "Chạy lệnh:\n  pip install paddleocr paddlepaddle\n\n"
                "rồi khởi động lại ứng dụng.", parent=self); return
        self._running = True
        self.btn_run.config(state=DISABLED, text="⏳  Đang nhận dạng...")
        self.pb["value"] = 0
        self.lbl_prog.config(text="")
        threading.Thread(target=self._ocr_worker, daemon=True).start()

    def _ocr_worker(self):
        import tempfile, os as _os
        try:
            ocr = self._get_engine()
        except RuntimeError as e:
            self.after(0, lambda msg=str(e): messagebox.showerror("Lỗi", msg, parent=self))
            self.after(0, self._done)
            return

        total   = len(self._files)
        results = []
        raw_detections = []
        for i, img_path in enumerate(self._files):
            self.after(0, self._update_prog, i, total, img_path.name)
            try:
                roi = self._roi
                if roi is not None:
                    try:
                        from PIL import Image as _PILImage
                        import numpy as _np
                        import cv2 as _cv2
                        orig = _PILImage.open(str(img_path)).convert("RGB")
                        rx1, ry1, rx2, ry2 = roi
                        cropped = orig.crop((rx1, ry1, rx2, ry2))
                        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as _f:
                            tmp_roi = _f.name
                        cropped.save(tmp_roi)
                        raw = ocr.predict(tmp_roi)
                        try: _os.unlink(tmp_roi)
                        except Exception: pass
                        text, conf, dets = self._extract_text_full(raw, offset=(rx1, ry1))
                    except Exception as _roi_err:
                        raw = ocr.predict(str(img_path))
                        text, conf, dets = self._extract_text_full(raw)
                else:
                    raw  = ocr.predict(str(img_path))
                    text, conf, dets = self._extract_text_full(raw)

                if conf < 0.75 or not text.strip():
                    enhanced = self._auto_enhance(str(img_path))
                    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as _f:
                        tmp = _f.name
                    try:
                        enhanced.save(tmp)
                        raw2 = ocr.predict(tmp)
                        text2, conf2, dets2 = self._extract_text_full(raw2)
                        if conf2 > conf or (not text.strip() and text2.strip()):
                            text, conf, dets = text2, conf2, dets2
                    finally:
                        try: _os.unlink(tmp)
                        except Exception: pass
                if not text.strip():
                    text = "[⚠ chất lượng thấp]"
                if self.v_clean.get() and not text.startswith("["):
                    text = self._clean_text(text)
            except Exception as e:
                text, conf, dets = f"[Lỗi: {e}]", 0.0, []
            results.append((img_path, text, conf))
            raw_detections.append((img_path, dets))

        self._results = results
        self._raw_detections = raw_detections
        self.after(0, self._populate_tree)
        self.after(0, self._done)

    @staticmethod
    def _clean_text(text):
        import re
        return re.sub(r'[^A-Za-z0-9]', '', text).upper()

    @staticmethod
    def _auto_enhance(img_path):
        import cv2, numpy as np
        from PIL import Image
        img_bgr = cv2.imread(img_path)
        if img_bgr is None:
            return Image.open(img_path).convert('RGB')
        gray       = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        contrast   = float(gray.std())
        hsv        = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
        sat_mean   = float(hsv[:, :, 1].mean())
        is_colored = sat_mean > 60 and contrast < 35
        if is_colored:
            v_ch  = hsv[:, :, 2]
            clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(4, 4))
            src   = cv2.cvtColor(clahe.apply(v_ch), cv2.COLOR_GRAY2BGR)
        else:
            lab     = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe   = cv2.createCLAHE(clipLimit=4.0 if contrast < 30 else 2.5,
                                       tileGridSize=(8, 8))
            src     = cv2.cvtColor(cv2.merge([clahe.apply(l), a, b]), cv2.COLOR_LAB2BGR)
        h, w = src.shape[:2]
        if max(h, w) < 400:
            src = cv2.resize(src, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)
        blurred = cv2.GaussianBlur(src, (0, 0), 2.0)
        out_bgr = np.clip(cv2.addWeighted(src, 1.7, blurred, -0.7, 0), 0, 255).astype(np.uint8)
        return Image.fromarray(cv2.cvtColor(out_bgr, cv2.COLOR_BGR2RGB))

    @staticmethod
    def _extract_text(ocr_result):
        text, conf, _ = OcrTab._extract_text_full(ocr_result)
        return text, conf

    @staticmethod
    def _extract_text_full(ocr_result, offset=(0, 0)):
        lines, confs, dets = [], [], []
        ox, oy = offset
        if not ocr_result:
            return "", 0.0, []
        for page in ocr_result:
            if page is None: continue
            try:
                polys  = page["rec_polys"]
                texts  = page["rec_texts"]
                scores = page["rec_scores"]
                def _min_y(poly):
                    try:
                        import numpy as np
                        return float(np.asarray(poly)[:, 1].min())
                    except Exception:
                        return 0.0
                items = sorted(zip(polys, texts, scores), key=lambda x: _min_y(x[0]))
                for poly, t, c in items:
                    s = str(t).strip()
                    if s:
                        lines.append(s)
                        confs.append(float(c))
                        try:
                            import numpy as np
                            arr = np.asarray(poly)
                            x1 = int(arr[:, 0].min()) + ox
                            y1 = int(arr[:, 1].min()) + oy
                            x2 = int(arr[:, 0].max()) + ox
                            y2 = int(arr[:, 1].max()) + oy
                        except Exception:
                            x1 = y1 = x2 = y2 = 0
                        dets.append({"text": s, "conf": float(c),
                                     "x1": x1, "y1": y1, "x2": x2, "y2": y2})
                continue
            except (KeyError, TypeError):
                pass
            if not isinstance(page, list): continue
            for item in page:
                if item and len(item) >= 2 and item[1]:
                    t, c = item[1]
                    s = str(t).strip()
                    if s:
                        lines.append(s); confs.append(float(c))
                        dets.append({"text": s, "conf": float(c),
                                     "x1": 0, "y1": 0, "x2": 0, "y2": 0})
        text     = " ".join(lines)
        avg_conf = sum(confs) / len(confs) if confs else 0.0
        return text, avg_conf, dets

    def _on_conf_change(self, val=None):
        v = self.v_conf_thresh.get()
        self.lbl_conf_val.config(text=f"{v:.2f}")
        if self._results:
            self._populate_tree()

    def _update_prog(self, i, total, name):
        self.pb["value"] = int(i / total * 100)
        self.lbl_prog.config(text=f"({i}/{total})  {name}")

    def _done(self):
        self._running = False
        self.btn_run.config(state=NORMAL, text="▶   Nhận dạng")
        self.pb["value"] = 100
        self.lbl_prog.config(text=f"Hoàn thành — {len(self._results)} ảnh")

    def _populate_tree(self):
        thresh = self.v_conf_thresh.get()
        self.tree.delete(*self.tree.get_children())
        has_text   = 0
        total_conf = 0.0
        filtered   = 0
        for img_path, text, conf in self._results:
            if conf > 0 and conf < thresh and not text.startswith("["):
                filtered += 1
                continue
            if conf >= 0.90:   tag = "hi"
            elif conf >= 0.70: tag = "mid"
            elif conf > 0:     tag = "lo"
            else:              tag = "err"
            conf_str = f"{conf:.0%}" if conf > 0 else "—"
            self.tree.insert("", END, iid=str(img_path),
                             values=(img_path.name, text, conf_str), tags=(tag,))
            if text and not text.startswith("[Lỗi"):
                has_text += 1; total_conf += conf
        n   = len(self._results)
        avg = total_conf / has_text if has_text else 0.0
        self.lbl_count.config(text=f"  {n} ảnh")
        self.lbl_stats.config(
            text=f"│  {has_text} có text  │  avg {avg:.0%}" if has_text else "")
        if filtered > 0:
            self.lbl_filtered.config(
                text=f"Đã lọc {filtered} kết quả dưới ngưỡng {thresh:.2f}", fg=ACCENT)
        else:
            self.lbl_filtered.config(text="")

    def _on_select(self, event):
        sel = self.tree.selection()
        if not sel: return
        iid  = sel[0]
        self._show_preview(Path(iid))
        vals = self.tree.item(iid, "values")
        if vals:
            self.lbl_prev_text.config(text=vals[1] if vals[1] else "—")

    def _on_edit(self, event):
        sel = self.tree.selection()
        if not sel: return
        iid = sel[0]
        fname, text, conf = self.tree.item(iid)["values"]
        dlg = Toplevel(self)
        dlg.title("Sửa văn bản")
        dlg.configure(bg=CARD)
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.geometry("480x130")
        Label(dlg, text=f"Sửa nhận dạng cho:  {fname}",
              bg=CARD, fg=TEXT, font=F_BOLD).pack(padx=16, pady=(12, 4))
        var = StringVar(value=str(text))
        ent = Entry(dlg, textvariable=var, bg="#16162a", fg=TEXT,
                    insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4)
        ent.pack(fill=X, padx=16, pady=4)
        ent.focus_set(); ent.select_range(0, END)
        def _save():
            new_text = var.get().strip()
            self.tree.item(iid, values=(fname, new_text, conf))
            for i, (p, t, c) in enumerate(self._results):
                if str(p) == iid:
                    self._results[i] = (p, new_text, c); break
            dlg.destroy()
        br = Frame(dlg, bg=CARD); br.pack(pady=6)
        Button(br, text="Lưu", command=_save,
               bg=ACCENT, fg="white", relief="flat",
               padx=14, pady=4, cursor="hand2", font=F_BOLD).pack(side=LEFT, padx=6)
        Button(br, text="Hủy", command=dlg.destroy,
               bg=BG, fg=DIM, relief="flat",
               padx=14, pady=4, cursor="hand2", font=F_MAIN).pack(side=LEFT)
        ent.bind("<Return>", lambda e: _save())
        ent.bind("<Escape>", lambda e: dlg.destroy())

    def _show_preview(self, img_path):
        try:
            from PIL import Image, ImageTk
            img = Image.open(img_path)
            cw  = max(self.canvas_prev.winfo_width(), 400)
            img.thumbnail((cw, 130))
            photo = ImageTk.PhotoImage(img)
            self._cur_preview = photo
            w, h = img.size
            self.canvas_prev.config(height=h)
            self.canvas_prev.delete("all")
            self.canvas_prev.create_image(cw // 2, h // 2, image=photo)
        except Exception:
            pass

    def _export_gt(self):
        if not self._results:
            messagebox.showinfo("Chưa có kết quả",
                                "Hãy chạy nhận dạng trước.", parent=self); return
        out_dir = self.v_out_dir.get().strip()
        if out_dir:
            out_path = Path(out_dir) / "gt.txt"
            Path(out_dir).mkdir(parents=True, exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as f:
                for img_path, text, _ in self._results:
                    f.write(f"{img_path.name}\t{text}\n")
            n = len(self._results)
            self.lbl_status.config(text=f"✅  Đã xuất {n} dòng → {out_path}", fg=SUCCESS)
            messagebox.showinfo("Xuất thành công",
                                f"Đã ghi {n} dòng vào:\n{out_path}", parent=self)
        else:
            folders = {}
            for img_path, text, _ in self._results:
                folders.setdefault(img_path.parent, []).append((img_path.name, text))
            for folder, items in folders.items():
                with open(folder / "gt.txt", "w", encoding="utf-8") as f:
                    for fname, text in items:
                        f.write(f"{fname}\t{text}\n")
            n_f = len(folders); n_i = len(self._results)
            self.lbl_status.config(
                text=f"✅  Đã xuất {n_i} dòng vào {n_f} file gt.txt", fg=SUCCESS)
            messagebox.showinfo("Xuất thành công",
                                f"Đã ghi gt.txt vào {n_f} folder.\nTổng {n_i} ảnh.",
                                parent=self)

    def _export_csv(self):
        if not self._raw_detections:
            messagebox.showinfo("Chưa có kết quả",
                                "Hãy chạy nhận dạng trước.", parent=self); return
        save_path = filedialog.asksaveasfilename(
            title="Lưu CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not save_path:
            return
        thresh = self.v_conf_thresh.get()
        rows_written = 0
        with open(save_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["filename", "text", "confidence", "x1", "y1", "x2", "y2"])
            for img_path, dets in self._raw_detections:
                for d in dets:
                    if d["conf"] < thresh:
                        continue
                    writer.writerow([
                        img_path.name,
                        d["text"],
                        f"{d['conf']:.4f}",
                        d["x1"], d["y1"], d["x2"], d["y2"],
                    ])
                    rows_written += 1
        self.lbl_status.config(
            text=f"✅  Đã xuất {rows_written} dòng → {save_path}", fg=SUCCESS)
        messagebox.showinfo("Xuất CSV thành công",
                            f"Đã ghi {rows_written} dòng vào:\n{save_path}",
                            parent=self)

    def _copy_results(self):
        if not self._results: return
        lines = [f"{p.name}\t{t}" for p, t, _ in self._results]
        self.root.clipboard_clear()
        self.root.clipboard_append("\n".join(lines))
        self.lbl_status.config(
            text=f"✅  Đã copy {len(lines)} dòng vào clipboard", fg=SUCCESS)

    def _clear_results(self):
        self._results.clear()
        self._raw_detections.clear()
        self.tree.delete(*self.tree.get_children())
        for w in (self.lbl_count, self.lbl_stats, self.lbl_prev_text,
                  self.lbl_status, self.lbl_filtered):
            w.config(text="")
        self.pb["value"] = 0
        self.lbl_prog.config(text="")
        self.canvas_prev.delete("all")

    def _browse_gt(self):
        folder = filedialog.askdirectory(title="Chọn folder GT")
        if folder:
            self.v_gt_dir.set(folder)

    def _compare_gt(self):
        if not self._results:
            messagebox.showinfo("Chưa có kết quả",
                                "Hãy chạy nhận dạng trước.", parent=self); return
        gt_dir = self.v_gt_dir.get().strip()
        if not gt_dir or not Path(gt_dir).is_dir():
            messagebox.showwarning("Chưa chọn folder GT",
                                   "Hãy chọn folder chứa file GT (.txt).",
                                   parent=self); return
        gt_map = {}
        for txt_file in Path(gt_dir).glob("*.txt"):
            try:
                with open(txt_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.rstrip("\n")
                        if "\t" in line:
                            fname, gt_text = line.split("\t", 1)
                            gt_map[fname.strip()] = gt_text.strip()
            except Exception:
                pass

        if not gt_map:
            messagebox.showwarning("GT trống",
                                   "Không tìm thấy dữ liệu GT trong folder đã chọn.",
                                   parent=self); return

        rows = []
        total_cer_num = 0
        total_cer_den = 0
        total_wer_num = 0
        total_wer_den = 0
        matched = 0

        for img_path, pred_text, conf in self._results:
            fname = img_path.name
            if fname not in gt_map:
                rows.append((fname, pred_text, "—", "N/A", "N/A"))
                continue
            gt_text = gt_map[fname]
            char_acc = self._char_accuracy(pred_text, gt_text)
            word_acc = self._word_accuracy(pred_text, gt_text)
            rows.append((fname, pred_text, gt_text, f"{char_acc:.1%}", f"{word_acc:.1%}"))
            cer_ed = self._edit_distance(pred_text, gt_text)
            total_cer_num += cer_ed
            total_cer_den += max(len(gt_text), 1)
            wer_ed = self._word_edit_distance(pred_text, gt_text)
            gt_words = gt_text.split()
            total_wer_num += wer_ed
            total_wer_den += max(len(gt_words), 1)
            matched += 1

        overall_char_acc = (1 - total_cer_num / total_cer_den) if total_cer_den > 0 else 0.0
        overall_word_acc = (1 - total_wer_num / total_wer_den) if total_wer_den > 0 else 0.0

        self._show_compare_popup(rows, overall_char_acc, overall_word_acc, matched)

    def _show_compare_popup(self, rows, overall_char_acc, overall_word_acc, matched):
        dlg = Toplevel(self)
        dlg.title("So sánh GT — Kết quả")
        dlg.configure(bg=BG)
        dlg.geometry("900x540")
        dlg.grab_set()

        hf = Frame(dlg, bg=CARD, padx=12, pady=8)
        hf.pack(fill=X)
        Label(hf, text="So sánh GT", bg=CARD, fg=TEXT, font=F_BOLD).pack(side=LEFT)
        Label(hf,
              text=f"  {matched} ảnh khớp  │  Char Acc: {overall_char_acc:.1%}  │  Word Acc: {overall_word_acc:.1%}",
              bg=CARD, fg=ACCENT, font=("Segoe UI Semibold", 10)).pack(side=LEFT, padx=12)

        tbl = Frame(dlg, bg="#111122")
        tbl.pack(fill=BOTH, expand=True, padx=6, pady=6)

        cols = ("file", "pred", "gt", "char_acc", "word_acc")
        tree = ttk.Treeview(tbl, columns=cols, show="headings",
                            style="OCR.Treeview", selectmode="browse")
        tree.heading("file",      text="Tên file",   anchor=W)
        tree.heading("pred",      text="OCR",        anchor=W)
        tree.heading("gt",        text="GT",         anchor=W)
        tree.heading("char_acc",  text="Char Acc",   anchor=CENTER)
        tree.heading("word_acc",  text="Word Acc",   anchor=CENTER)
        tree.column("file",      width=160, minwidth=90,  stretch=False)
        tree.column("pred",      width=220, minwidth=100, stretch=True)
        tree.column("gt",        width=220, minwidth=100, stretch=True)
        tree.column("char_acc",  width=90,  minwidth=70,  stretch=False, anchor=CENTER)
        tree.column("word_acc",  width=90,  minwidth=70,  stretch=False, anchor=CENTER)
        tree.tag_configure("hi",  background="#0e2a0e", foreground="#7ddd7d")
        tree.tag_configure("mid", background="#2e2600", foreground="#ddbb44")
        tree.tag_configure("lo",  background="#2e0e0e", foreground="#dd7070")
        tree.tag_configure("na",  background="#1e1e2e", foreground="#9090b0")

        vsb = ttk.Scrollbar(tbl, orient=VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side=RIGHT, fill=Y)
        tree.pack(fill=BOTH, expand=True)

        for fname, pred, gt, char_acc, word_acc in rows:
            if char_acc == "N/A":
                tag = "na"
            else:
                try:
                    v = float(char_acc.strip("%")) / 100
                    tag = "hi" if v >= 0.9 else ("mid" if v >= 0.7 else "lo")
                except Exception:
                    tag = "na"
            tree.insert("", END, values=(fname, pred, gt, char_acc, word_acc), tags=(tag,))

        bf = Frame(dlg, bg=BG)
        bf.pack(fill=X, padx=6, pady=4)
        Button(bf, text="Đóng", command=dlg.destroy,
               bg=ACCENT2, fg="white", relief="flat",
               padx=14, pady=5, cursor="hand2", font=F_BOLD).pack(side=RIGHT)

    @staticmethod
    def _edit_distance(a, b):
        a, b = list(a), list(b)
        m, n = len(a), len(b)
        dp = list(range(n + 1))
        for i in range(1, m + 1):
            prev = dp[:]
            dp[0] = i
            for j in range(1, n + 1):
                if a[i - 1] == b[j - 1]:
                    dp[j] = prev[j - 1]
                else:
                    dp[j] = 1 + min(prev[j], dp[j - 1], prev[j - 1])
        return dp[n]

    @staticmethod
    def _word_edit_distance(a, b):
        a_w, b_w = a.split(), b.split()
        m, n = len(a_w), len(b_w)
        dp = list(range(n + 1))
        for i in range(1, m + 1):
            prev = dp[:]
            dp[0] = i
            for j in range(1, n + 1):
                if a_w[i - 1] == b_w[j - 1]:
                    dp[j] = prev[j - 1]
                else:
                    dp[j] = 1 + min(prev[j], dp[j - 1], prev[j - 1])
        return dp[n]

    @staticmethod
    def _char_accuracy(pred, gt):
        if not gt:
            return 1.0 if not pred else 0.0
        ed = OcrTab._edit_distance(pred, gt)
        return max(0.0, 1.0 - ed / len(gt))

    @staticmethod
    def _word_accuracy(pred, gt):
        gt_words = gt.split()
        if not gt_words:
            return 1.0 if not pred.strip() else 0.0
        ed = OcrTab._word_edit_distance(pred, gt)
        return max(0.0, 1.0 - ed / len(gt_words))

    def _open_roi_selector(self):
        sel = self.tree.selection()
        if sel:
            img_path = Path(sel[0])
        elif self._files:
            img_path = self._files[0]
        else:
            messagebox.showinfo("Chưa có ảnh",
                                "Hãy chọn ảnh trước rồi mới chọn ROI.", parent=self)
            return
        try:
            from PIL import Image, ImageTk
        except ImportError:
            messagebox.showerror("Thiếu Pillow",
                                 "Cài Pillow: pip install pillow", parent=self)
            return

        dlg = Toplevel(self)
        dlg.title(f"Chọn vùng ROI — {img_path.name}")
        dlg.configure(bg=BG)
        dlg.grab_set()

        orig = Image.open(img_path).convert("RGB")
        disp_w, disp_h = min(orig.width, 900), min(orig.height, 620)
        scale_x = orig.width  / disp_w
        scale_y = orig.height / disp_h
        thumb = orig.resize((disp_w, disp_h), Image.LANCZOS)
        photo = ImageTk.PhotoImage(thumb)

        info_lbl = Label(dlg, text="Kéo để vẽ hình chữ nhật. Nhấn Xác nhận để lưu ROI.",
                         bg=CARD, fg=TEXT, font=F_MAIN)
        info_lbl.pack(fill=X, padx=8, pady=4)

        canvas = Canvas(dlg, width=disp_w, height=disp_h,
                        bg="#0a0a18", highlightthickness=0, cursor="crosshair")
        canvas.pack(padx=8, pady=4)
        canvas.create_image(0, 0, anchor=NW, image=photo)
        canvas._photo = photo

        rect_id = [None]
        start    = [None, None]
        cur_roi  = [None]

        if self._roi is not None:
            rx1, ry1, rx2, ry2 = self._roi
            dx1 = int(rx1 / scale_x)
            dy1 = int(ry1 / scale_y)
            dx2 = int(rx2 / scale_x)
            dy2 = int(ry2 / scale_y)
            rect_id[0] = canvas.create_rectangle(
                dx1, dy1, dx2, dy2,
                outline=ACCENT, width=2, dash=(4, 2))
            cur_roi[0] = self._roi

        coord_lbl = Label(dlg, text="", bg=BG, fg=DIM, font=F_MONO)
        coord_lbl.pack(fill=X, padx=8)

        def _on_press(e):
            start[0], start[1] = e.x, e.y
            if rect_id[0]:
                canvas.delete(rect_id[0])
                rect_id[0] = None

        def _on_drag(e):
            if rect_id[0]:
                canvas.delete(rect_id[0])
            rect_id[0] = canvas.create_rectangle(
                start[0], start[1], e.x, e.y,
                outline=ACCENT, width=2, dash=(4, 2))
            rx1 = int(min(start[0], e.x) * scale_x)
            ry1 = int(min(start[1], e.y) * scale_y)
            rx2 = int(max(start[0], e.x) * scale_x)
            ry2 = int(max(start[1], e.y) * scale_y)
            coord_lbl.config(text=f"ROI: ({rx1}, {ry1}) → ({rx2}, {ry2})")
            cur_roi[0] = (rx1, ry1, rx2, ry2)

        def _on_release(e):
            if start[0] is None: return
            rx1 = int(min(start[0], e.x) * scale_x)
            ry1 = int(min(start[1], e.y) * scale_y)
            rx2 = int(max(start[0], e.x) * scale_x)
            ry2 = int(max(start[1], e.y) * scale_y)
            if rx2 - rx1 < 4 or ry2 - ry1 < 4:
                cur_roi[0] = None
                coord_lbl.config(text="ROI quá nhỏ, hãy vẽ lại.")
            else:
                cur_roi[0] = (rx1, ry1, rx2, ry2)
                coord_lbl.config(text=f"ROI: ({rx1}, {ry1}) → ({rx2}, {ry2})")

        canvas.bind("<ButtonPress-1>",   _on_press)
        canvas.bind("<B1-Motion>",       _on_drag)
        canvas.bind("<ButtonRelease-1>", _on_release)

        def _confirm():
            if cur_roi[0]:
                self._roi = cur_roi[0]
                rx1, ry1, rx2, ry2 = self._roi
                self.lbl_roi.config(
                    text=f"ROI ({rx1},{ry1})→({rx2},{ry2})", fg=ACCENT)
            dlg.destroy()

        def _clear_roi():
            self._roi = None
            self.lbl_roi.config(text="")
            dlg.destroy()

        bf = Frame(dlg, bg=BG)
        bf.pack(fill=X, padx=8, pady=6)
        Button(bf, text="✅  Xác nhận ROI", command=_confirm,
               bg=SUCCESS, fg="white", relief="flat",
               padx=14, pady=5, cursor="hand2", font=F_BOLD).pack(side=LEFT)
        Button(bf, text="🗑  Xóa ROI", command=_clear_roi,
               bg=CARD, fg=DIM, relief="flat",
               padx=10, pady=5, cursor="hand2", font=F_MAIN).pack(side=LEFT, padx=8)
        Button(bf, text="Hủy", command=dlg.destroy,
               bg=BG, fg=DIM, relief="flat",
               padx=10, pady=5, cursor="hand2", font=F_MAIN).pack(side=LEFT)
