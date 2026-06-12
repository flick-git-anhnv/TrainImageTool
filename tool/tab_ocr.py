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
        self._ocr_engine = None
        self._running = False
        self._cur_preview = None

        self.v_lang    = StringVar(value="vi")
        self.v_use_gpu = BooleanVar(value=False)
        self.v_angle   = BooleanVar(value=True)
        self.v_clean   = BooleanVar(value=True)
        self.v_out_dir = StringVar()
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
        Button(brw, text="🗑  Xóa kết quả",
               command=self._clear_results,
               bg=CARD, fg=DIM, font=F_MAIN, relief="flat",
               padx=10, pady=6, cursor="hand2").pack(side=LEFT)

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
        for i, img_path in enumerate(self._files):
            self.after(0, self._update_prog, i, total, img_path.name)
            try:
                raw  = ocr.predict(str(img_path))
                text, conf = self._extract_text(raw)
                if conf < 0.75 or not text.strip():
                    enhanced = self._auto_enhance(str(img_path))
                    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as _f:
                        tmp = _f.name
                    try:
                        enhanced.save(tmp)
                        raw2 = ocr.predict(tmp)
                        text2, conf2 = self._extract_text(raw2)
                        if conf2 > conf or (not text.strip() and text2.strip()):
                            text, conf = text2, conf2
                    finally:
                        try: _os.unlink(tmp)
                        except Exception: pass
                if not text.strip():
                    text = "[⚠ chất lượng thấp]"
                if self.v_clean.get() and not text.startswith("["):
                    text = self._clean_text(text)
            except Exception as e:
                text, conf = f"[Lỗi: {e}]", 0.0
            results.append((img_path, text, conf))

        self._results = results
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
        lines, confs = [], []
        if not ocr_result:
            return "", 0.0
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
                for _, t, c in items:
                    s = str(t).strip()
                    if s:
                        lines.append(s); confs.append(float(c))
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
        text     = " ".join(lines)
        avg_conf = sum(confs) / len(confs) if confs else 0.0
        return text, avg_conf

    def _update_prog(self, i, total, name):
        self.pb["value"] = int(i / total * 100)
        self.lbl_prog.config(text=f"({i}/{total})  {name}")

    def _done(self):
        self._running = False
        self.btn_run.config(state=NORMAL, text="▶   Nhận dạng")
        self.pb["value"] = 100
        self.lbl_prog.config(text=f"Hoàn thành — {len(self._results)} ảnh")

    def _populate_tree(self):
        self.tree.delete(*self.tree.get_children())
        has_text   = 0
        total_conf = 0.0
        for img_path, text, conf in self._results:
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

    def _copy_results(self):
        if not self._results: return
        lines = [f"{p.name}\t{t}" for p, t, _ in self._results]
        self.root.clipboard_clear()
        self.root.clipboard_append("\n".join(lines))
        self.lbl_status.config(
            text=f"✅  Đã copy {len(lines)} dòng vào clipboard", fg=SUCCESS)

    def _clear_results(self):
        self._results.clear()
        self.tree.delete(*self.tree.get_children())
        for w in (self.lbl_count, self.lbl_stats, self.lbl_prev_text, self.lbl_status):
            w.config(text="")
        self.pb["value"] = 0
        self.lbl_prog.config(text="")
        self.canvas_prev.delete("all")
