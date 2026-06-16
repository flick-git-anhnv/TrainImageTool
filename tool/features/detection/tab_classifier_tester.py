"""tab_classifier_tester.py — Test YOLO Image Classifier sau khi train.

Hai chế độ:
  * Ảnh đơn  — classify 1 ảnh, hiện top-N class + thanh confidence.
  * Batch    — chạy toàn bộ thư mục test (class-subfolder layout),
               tính Top-1 / Top-5 accuracy, liệt kê kết quả trong Treeview.
"""

import os
import queue
import threading
from pathlib import Path
from tkinter import *
from tkinter import filedialog, messagebox, ttk

from ...core.constants import (BG, CARD, ACCENT, ACCENT2, TEXT, DIM, SUCCESS,
                                F_MAIN, F_BOLD, F_MONO, IMAGE_EXTENSIONS)
from ...core.settings import (_bind_cfg, _bind_history, _push_history, _CFG)
from ...core.ui_helpers import _make_logbox, _append_log

try:
    from PIL import Image, ImageTk
    _PIL_OK = True
except ImportError:
    _PIL_OK = False

try:
    from ultralytics import YOLO as _YOLO
    _YOLO_OK = True
except ImportError:
    _YOLO_OK = False

_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tiff", ".tif"}
_BAR_COLORS = [ACCENT, "#4fc3f7", "#81c784", "#fff176", "#ce93d8"]


class ClassifierTesterTab(Frame):
    """Tab test model YOLO Image Classifier — ảnh đơn & batch folder."""

    def __init__(self, master, root):
        super().__init__(master, bg=BG)
        self.root = root

        self._model = None
        self._model_names: dict = {}
        self._pil_img = None
        self._tk_img = None
        self._stop_flag = threading.Event()
        self._batch_thread = None
        self._q: queue.Queue = queue.Queue()

        # Vars
        self._v_model  = StringVar()
        self._v_image  = StringVar()
        self._v_folder = StringVar()
        self._v_mode   = StringVar(value="single")
        self._v_top_n  = IntVar(value=5)

        _bind_cfg("cls_test.model",  self._v_model)
        _bind_cfg("cls_test.image",  self._v_image)
        _bind_cfg("cls_test.folder", self._v_folder)
        _bind_cfg("cls_test.top_n",  self._v_top_n)

        self._build()
        self.after(400, self._auto_load_model)

    # ═══════════════════════════════════════════════════════════════ BUILD ══

    def _build(self):
        pad = {"padx": 12, "pady": 6}

        # ── Model card ────────────────────────────────────────────────────
        mc = Frame(self, bg=CARD, padx=16, pady=12)
        mc.pack(fill=X, **pad)

        Label(mc, text="🤖  Model Classifier",
              bg=CARD, fg=ACCENT, font=F_BOLD).grid(
            row=0, column=0, columnspan=5, sticky=W, pady=(0, 8))

        Label(mc, text="File .pt:", bg=CARD, fg=DIM, font=F_MAIN).grid(
            row=1, column=0, sticky=W, padx=(0, 6))

        self._cmb_model = ttk.Combobox(
            mc, textvariable=self._v_model,
            font=F_MAIN, style="Dark.TCombobox")
        self._cmb_model.grid(row=1, column=1, sticky=EW, padx=(0, 6))
        mc.columnconfigure(1, weight=1)
        _bind_history("h.cls_test.model", self._cmb_model)

        Button(mc, text="Chọn .pt…", command=self._pick_model,
               bg=CARD, fg=TEXT, font=F_MAIN, relief=FLAT,
               padx=8, cursor="hand2").grid(row=1, column=2, padx=(0, 6))

        Button(mc, text="⏩ Tải model", command=self._load_model,
               bg=ACCENT2, fg="white", font=F_MAIN, relief=FLAT,
               padx=10, pady=2, cursor="hand2").grid(row=1, column=3, padx=(0, 10))

        self._lbl_status = Label(
            mc, text="Chưa tải model",
            bg=CARD, fg=DIM, font=("Segoe UI", 9, "italic"), anchor=W)
        self._lbl_status.grid(row=1, column=4, sticky=W)

        # ── Mode selector ─────────────────────────────────────────────────
        mf = Frame(self, bg=BG, padx=12)
        mf.pack(fill=X, pady=(2, 0))

        for val, lbl in (("single", "🖼  Ảnh đơn"), ("batch", "📂  Batch folder")):
            Radiobutton(mf, text=lbl, variable=self._v_mode, value=val,
                        command=self._on_mode_change,
                        bg=BG, fg=TEXT, selectcolor=CARD,
                        activebackground=BG, font=F_MAIN).pack(side=LEFT, padx=(0, 20))

        # ── Input container (switches between single/batch) ───────────────
        self._input_container = Frame(self, bg=BG)
        self._input_container.pack(fill=X, padx=12, pady=(4, 0))

        self._frm_single = self._build_single_input(self._input_container)
        self._frm_batch  = self._build_batch_input(self._input_container)

        # ── Actions ───────────────────────────────────────────────────────
        act = Frame(self, bg=BG, padx=12)
        act.pack(fill=X, pady=(6, 4))

        self._btn_run = Button(
            act, text="▶  Phân loại  (F5)",
            command=self._run,
            bg=ACCENT, fg="white", font=F_BOLD,
            relief=FLAT, padx=18, pady=6, cursor="hand2")
        self._btn_run.pack(side=LEFT, padx=(0, 8))

        self._btn_stop = Button(
            act, text="■  Dừng  (Esc)",
            command=self._stop,
            bg=CARD, fg=TEXT, font=F_MAIN,
            relief=FLAT, padx=12, pady=6, cursor="hand2",
            state=DISABLED)
        self._btn_stop.pack(side=LEFT, padx=(0, 12))

        self._pb = ttk.Progressbar(
            act, style="K.Horizontal.TProgressbar",
            maximum=100, length=200)
        self._pb.pack(side=LEFT, padx=(0, 8))

        self._lbl_prog = Label(act, text="", bg=BG, fg=DIM, font=F_MAIN)
        self._lbl_prog.pack(side=LEFT)

        # ── Body: left content + right panel ─────────────────────────────
        body = Frame(self, bg=BG)
        body.pack(fill=BOTH, expand=True, padx=12, pady=(0, 12))

        # Left: canvas (single) or treeview (batch) ───────────────────────
        left = Frame(body, bg=BG)
        left.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 6))

        # Single: image canvas
        self._canvas = Canvas(left, bg="#0d0d1a", cursor="hand2",
                              highlightthickness=1, highlightbackground=ACCENT2)
        self._canvas.pack(fill=BOTH, expand=True)
        self._canvas.bind("<Configure>", self._on_canvas_resize)
        self._canvas.bind("<Double-Button-1>", self._zoom_image)
        self._hint_id = self._canvas.create_text(
            200, 150,
            text="Chọn ảnh để hiển thị\nDouble-click để phóng to",
            fill=DIM, font=("Segoe UI", 11), justify=CENTER)

        # Batch: treeview frame
        self._tree_fr = Frame(left, bg=BG)
        cols = ("file", "true_cls", "pred_cls", "conf", "ok")
        self._tree = ttk.Treeview(
            self._tree_fr, columns=cols, show="headings",
            style="Dark.Treeview")
        hdrs = [("file", "File", 220), ("true_cls", "True class", 120),
                ("pred_cls", "Predicted", 150), ("conf", "Conf %", 80),
                ("ok", "✓", 40)]
        for cid, text, w in hdrs:
            self._tree.heading(cid, text=text)
            self._tree.column(cid, width=w, minwidth=40,
                              anchor=CENTER if cid != "file" else W)

        tsb_y = ttk.Scrollbar(self._tree_fr, command=self._tree.yview)
        tsb_x = ttk.Scrollbar(self._tree_fr, orient=HORIZONTAL, command=self._tree.xview)
        self._tree.configure(yscrollcommand=tsb_y.set, xscrollcommand=tsb_x.set)
        tsb_y.pack(side=RIGHT, fill=Y)
        tsb_x.pack(side=BOTTOM, fill=X)
        self._tree.pack(fill=BOTH, expand=True)

        self._lbl_acc = Label(self._tree_fr, text="",
                              bg=BG, fg=SUCCESS, font=F_BOLD)
        self._lbl_acc.pack(anchor=W, pady=(4, 0))

        # Right: top-N bars + log ─────────────────────────────────────────
        right = Frame(body, bg=CARD, width=290)
        right.pack(side=RIGHT, fill=Y)
        right.pack_propagate(False)

        Label(right, text="TOP PREDICTIONS",
              bg=CARD, fg=TEXT, font=F_BOLD).pack(pady=(12, 6))

        bars_fr = Frame(right, bg=CARD, padx=10)
        bars_fr.pack(fill=X)

        self._bar_rows = []
        for i in range(5):
            row = Frame(bars_fr, bg=CARD)
            row.pack(fill=X, pady=3)

            lbl_n = Label(row, text="—", bg=CARD, fg=DIM,
                          font=F_MAIN, anchor=W, width=13)
            lbl_n.pack(side=LEFT, padx=(0, 4))

            outer = Frame(row, bg="#333", height=16)
            outer.pack(side=LEFT, fill=X, expand=True)
            inner = Frame(outer, bg=_BAR_COLORS[i], height=16)
            inner.place(x=0, y=0, relheight=1.0, width=0)

            lbl_p = Label(row, text="", bg=CARD, fg=TEXT,
                          font=("Segoe UI", 8), width=6, anchor=E)
            lbl_p.pack(side=LEFT, padx=(3, 0))

            self._bar_rows.append((lbl_n, lbl_p, inner, outer))

        Frame(right, bg=DIM, height=1).pack(fill=X, padx=10, pady=8)

        log_fr, self._log = _make_logbox(right)
        log_fr.pack(fill=BOTH, expand=True, padx=8, pady=(0, 8))

        self._on_mode_change()

    def _build_single_input(self, parent):
        fr = Frame(parent, bg=CARD, padx=16, pady=10)

        Label(fr, text="📁  Ảnh đầu vào",
              bg=CARD, fg=ACCENT, font=F_BOLD).grid(
            row=0, column=0, columnspan=4, sticky=W, pady=(0, 6))

        Label(fr, text="Ảnh:", bg=CARD, fg=DIM, font=F_MAIN).grid(
            row=1, column=0, sticky=W, padx=(0, 6))

        self._cmb_image = ttk.Combobox(
            fr, textvariable=self._v_image,
            font=F_MAIN, style="Dark.TCombobox")
        self._cmb_image.grid(row=1, column=1, sticky=EW, padx=(0, 6))
        fr.columnconfigure(1, weight=1)
        _bind_history("h.cls_test.image", self._cmb_image)

        Button(fr, text="Chọn ảnh  (Ctrl+O)",
               command=self._pick_image,
               bg=ACCENT2, fg="white", font=F_MAIN, relief=FLAT,
               padx=10, cursor="hand2").grid(row=1, column=2)

        return fr

    def _build_batch_input(self, parent):
        fr = Frame(parent, bg=CARD, padx=16, pady=10)

        Label(fr, text="📂  Batch folder",
              bg=CARD, fg=ACCENT, font=F_BOLD).grid(
            row=0, column=0, columnspan=4, sticky=W, pady=(0, 6))

        Label(fr, text="Thư mục:", bg=CARD, fg=DIM, font=F_MAIN).grid(
            row=1, column=0, sticky=W, padx=(0, 6))

        self._cmb_folder = ttk.Combobox(
            fr, textvariable=self._v_folder,
            font=F_MAIN, style="Dark.TCombobox")
        self._cmb_folder.grid(row=1, column=1, sticky=EW, padx=(0, 6))
        fr.columnconfigure(1, weight=1)
        _bind_history("h.cls_test.folder", self._cmb_folder)

        Button(fr, text="Chọn thư mục  (Ctrl+O)",
               command=self._pick_folder,
               bg=ACCENT2, fg="white", font=F_MAIN, relief=FLAT,
               padx=10, cursor="hand2").grid(row=1, column=2)

        self._lbl_folder_info = Label(
            fr,
            text="Cấu trúc thư mục: <folder>/<class_name>/<image.jpg>",
            bg=CARD, fg=DIM, font=("Segoe UI", 9), anchor=W, justify=LEFT)
        self._lbl_folder_info.grid(
            row=2, column=0, columnspan=4, sticky=W, pady=(6, 0))

        return fr

    def _on_mode_change(self):
        mode = self._v_mode.get()
        # Show/hide input cards
        self._frm_single.pack_forget()
        self._frm_batch.pack_forget()
        if mode == "single":
            self._frm_single.pack(fill=X)
            self._canvas.pack(fill=BOTH, expand=True)
            self._tree_fr.pack_forget()
            self._btn_run.config(text="▶  Phân loại  (F5)")
        else:
            self._frm_batch.pack(fill=X)
            self._canvas.pack_forget()
            self._tree_fr.pack(fill=BOTH, expand=True)
            self._btn_run.config(text="▶  Chạy batch  (F5)")

    # ══════════════════════════════════════════════════════════ MODEL LOAD ══

    def _pick_model(self):
        p = filedialog.askopenfilename(
            title="Chọn model YOLO classifier (.pt)",
            filetypes=[("PyTorch model", "*.pt"), ("Tất cả", "*.*")],
            initialdir=os.path.dirname(self._v_model.get()) or ".")
        if not p:
            return
        self._v_model.set(p)
        _push_history("h.cls_test.model", p)
        self._cmb_model["values"] = _CFG.get("h.cls_test.model", [])
        self._load_model()

    def _auto_load_model(self):
        p = self._v_model.get().strip()
        if p and os.path.isfile(p):
            self._load_model()

    def _load_model(self):
        if not _YOLO_OK:
            _append_log(self._log, "⚠ Chưa cài ultralytics. Chạy: pip install ultralytics")
            return
        path = self._v_model.get().strip()
        if not path or not os.path.isfile(path):
            _append_log(self._log, "⚠ Đường dẫn model không hợp lệ")
            return
        self._lbl_status.config(text="⏳ Đang tải…", fg=DIM)
        _append_log(self._log, f"⏳ Tải model: {os.path.basename(path)}")
        threading.Thread(target=self._load_model_thread, args=(path,),
                         daemon=True).start()

    def _load_model_thread(self, path: str):
        try:
            model = _YOLO(path)
            task  = getattr(model, "task", "classify") or "classify"
            names: dict = {}
            for attr in ("names",):
                try:
                    names = getattr(model, attr, {}) or {}
                    break
                except Exception:
                    pass
            if not names:
                try:
                    names = getattr(getattr(model, "model", None), "names", {}) or {}
                except Exception:
                    pass
            if isinstance(names, (list, tuple)):
                names = {i: str(n) for i, n in enumerate(names)}

            self._model       = model
            self._model_names = names
            nc = len(names)
            basename = os.path.basename(path)
            cls_preview = ", ".join(
                f"{i}:{v}" for i, v in list(names.items())[:8])
            if nc > 8:
                cls_preview += "…"

            def _ok():
                self._lbl_status.config(
                    text=f"✔ {basename}  [{task}]  {nc} classes", fg=SUCCESS)
                _append_log(self._log, f"✔ Model: {basename}  [{task}]  {nc} classes")
                if cls_preview:
                    _append_log(self._log, f"   {cls_preview}")

            self.root.after(0, _ok)

        except Exception as ex:
            msg = str(ex)
            def _err():
                self._lbl_status.config(text=f"✘ {msg[:80]}", fg="#f05050")
                _append_log(self._log, f"[LỖI] Tải model: {msg}")
            self.root.after(0, _err)

    # ══════════════════════════════════════════════════════════════ IMAGE ══

    def _pick_image(self):
        exts = " ".join(f"*.{e}" for e in IMAGE_EXTENSIONS)
        init = os.path.dirname(self._v_image.get()) or "."
        p = filedialog.askopenfilename(
            title="Chọn ảnh để test",
            filetypes=[("Ảnh", exts), ("Tất cả", "*.*")],
            initialdir=init if os.path.isdir(init) else ".")
        if p:
            self._open_image(p)

    def _open_image(self, path: str):
        if not _PIL_OK:
            _append_log(self._log, "⚠ Chưa cài Pillow")
            return
        try:
            img = Image.open(path).convert("RGB")
            self._pil_img = img
            self._v_image.set(path)
            _push_history("h.cls_test.image", path)
            self._cmb_image["values"] = _CFG.get("h.cls_test.image", [])
            self._clear_bars()
            self.after(10, self._render_image)
            _append_log(self._log,
                        f"✔ Ảnh: {os.path.basename(path)}  ({img.width}×{img.height})")
        except Exception as ex:
            _append_log(self._log, f"[LỖI] Tải ảnh: {ex}")

    def _on_canvas_resize(self, _=None):
        if self._pil_img:
            self._render_image()

    def _render_image(self):
        if not self._pil_img or not _PIL_OK:
            return
        cw = max(self._canvas.winfo_width(),  50)
        ch = max(self._canvas.winfo_height(), 50)
        img = self._pil_img.copy()
        img.thumbnail((cw, ch), Image.LANCZOS)
        self._tk_img = ImageTk.PhotoImage(img)
        self._canvas.delete("all")
        self._canvas.create_image(cw // 2, ch // 2, anchor=CENTER, image=self._tk_img)

    def _zoom_image(self, _=None):
        if not self._pil_img:
            return
        try:
            from ...core.ui_helpers import _zoom_image_window
            _zoom_image_window(self.root, self._pil_img, "Phóng to ảnh")
        except Exception as ex:
            _append_log(self._log, f"⚠ Zoom: {ex}")

    # ══════════════════════════════════════════════════════════════ FOLDER ══

    def _pick_folder(self):
        init = self._v_folder.get().strip()
        p = filedialog.askdirectory(
            title="Chọn thư mục test (class subfolder layout)",
            initialdir=init if os.path.isdir(init) else ".")
        if p:
            self._v_folder.set(p)
            _push_history("h.cls_test.folder", p)
            self._cmb_folder["values"] = _CFG.get("h.cls_test.folder", [])
            self._scan_folder(p)

    def _scan_folder(self, path: str):
        p = Path(path)
        cls_dirs = sorted([d for d in p.iterdir() if d.is_dir()])
        if not cls_dirs:
            self._lbl_folder_info.config(
                text="⚠ Không tìm thấy class subfolder nào", fg="#f09040")
            return
        counts = {d.name: sum(1 for f in d.iterdir()
                               if f.suffix.lower() in _EXTS)
                  for d in cls_dirs}
        total = sum(counts.values())
        detail = "  |  ".join(f"{c}: {n}" for c, n in counts.items())
        self._lbl_folder_info.config(
            text=f"✔  {len(cls_dirs)} classes  |  {total} ảnh\n{detail}",
            fg=SUCCESS, justify=LEFT)
        _append_log(self._log,
                    f"✔ Scan: {len(cls_dirs)} classes, {total} ảnh")

    # ══════════════════════════════════════════════════════════════ RUN ══

    def _run(self, _=None):
        if self._v_mode.get() == "single":
            self._run_single()
        else:
            self._run_batch()

    # ── Single image ──────────────────────────────────────────────────────

    def _run_single(self):
        if not self._model:
            _append_log(self._log, "⚠ Chưa tải model")
            return
        img_path = self._v_image.get().strip()
        if not img_path:
            self._pick_image()
            return
        if not os.path.isfile(img_path):
            _append_log(self._log, f"⚠ File không tồn tại: {img_path}")
            return

        # Ensure PIL image is loaded for the current path
        if self._pil_img is None:
            self._open_image(img_path)
            self.after(80, self._run_single)
            return

        pil   = self._pil_img
        model = self._model
        names = self._model_names
        top_n = self._v_top_n.get()

        def _infer():
            try:
                results = model(pil, verbose=False)
                r = results[0]
                probs = r.probs
                if probs is None:
                    self.root.after(0, lambda: _append_log(
                        self._log, "⚠ Model không phải task=classify (probs=None)"))
                    return
                data = probs.data.tolist() if hasattr(probs, "data") else []
                top_idx = sorted(range(len(data)), key=lambda i: data[i], reverse=True)
                pairs = [(names.get(i, str(i)), data[i]) for i in top_idx[:top_n]]
                self.root.after(0, lambda: self._show_single_result(pairs))
            except Exception as ex:
                msg = str(ex)
                self.root.after(0, lambda: _append_log(
                    self._log, f"[LỖI] Predict: {msg}"))

        threading.Thread(target=_infer, daemon=True).start()

    def _show_single_result(self, pairs: list):
        if not pairs:
            return
        top_cls, top_conf = pairs[0]
        _append_log(self._log,
                    f"✔ Kết quả: {top_cls}  ({top_conf:.1%})")
        for i, (cls, conf) in enumerate(pairs):
            _append_log(self._log, f"   Top-{i+1}: {cls:<20} {conf:.1%}")
        self._update_bars(pairs)

    # ── Batch folder ──────────────────────────────────────────────────────

    def _run_batch(self):
        if not self._model:
            _append_log(self._log, "⚠ Chưa tải model")
            return
        folder = self._v_folder.get().strip()
        if not folder or not os.path.isdir(folder):
            self._pick_folder()
            return

        root_p   = Path(folder)
        cls_dirs = sorted([d for d in root_p.iterdir() if d.is_dir()])
        items = []
        for d in cls_dirs:
            for f in sorted(d.iterdir()):
                if f.suffix.lower() in _EXTS:
                    items.append((str(f), d.name))

        if not items:
            _append_log(self._log, "⚠ Không tìm thấy ảnh nào trong thư mục")
            return

        # Reset treeview
        for row in self._tree.get_children():
            self._tree.delete(row)
        self._lbl_acc.config(text="")
        self._clear_bars()

        self._stop_flag.clear()
        self._pb.config(value=0, maximum=len(items))
        self._btn_run.config(state=DISABLED)
        self._btn_stop.config(state=NORMAL, bg=ACCENT)
        self._lbl_prog.config(text=f"0 / {len(items)}", fg=TEXT)
        _append_log(self._log,
                    f"✔ Bắt đầu batch: {len(items)} ảnh  |  {len(cls_dirs)} classes")

        model  = self._model
        names  = self._model_names
        top_n  = self._v_top_n.get()

        def _worker():
            c1 = c5 = total = 0
            for idx, (img_path, true_cls) in enumerate(items):
                if self._stop_flag.is_set():
                    break
                try:
                    if _PIL_OK:
                        pil_img = Image.open(img_path).convert("RGB")
                        results = model(pil_img, verbose=False)
                    else:
                        results = model(img_path, verbose=False)

                    r = results[0]
                    probs = r.probs
                    if probs is None:
                        self._q.put(("row", os.path.basename(img_path),
                                     true_cls, "N/A", "—", "?", False))
                        self._q.put(("progress", idx + 1))
                        continue

                    data = probs.data.tolist() if hasattr(probs, "data") else []
                    top_idx = sorted(range(len(data)),
                                     key=lambda i: data[i], reverse=True)
                    pred_cls  = names.get(top_idx[0], str(top_idx[0]))
                    pred_conf = data[top_idx[0]]
                    top5_cls  = {names.get(i, str(i)) for i in top_idx[:5]}

                    ok1 = pred_cls == true_cls
                    ok5 = true_cls in top5_cls
                    if ok1:
                        c1 += 1
                    if ok5:
                        c5 += 1
                    total += 1

                    self._q.put(("row",
                                 os.path.basename(img_path),
                                 true_cls, pred_cls,
                                 f"{pred_conf:.1%}",
                                 "✓" if ok1 else "✗", ok1))
                    self._q.put(("progress", idx + 1))

                except Exception as ex:
                    self._q.put(("row", os.path.basename(img_path),
                                 true_cls, "ERROR", "—", "✗", False))
                    self._q.put(("progress", idx + 1))

            a1 = c1 / total * 100 if total else 0.0
            a5 = c5 / total * 100 if total else 0.0
            self._q.put(("done", total, c1, c5, a1, a5))

        self._batch_thread = threading.Thread(target=_worker, daemon=True)
        self._batch_thread.start()
        self._poll_batch()

    def _poll_batch(self):
        try:
            while True:
                msg = self._q.get_nowait()
                kind = msg[0]
                if kind == "row":
                    _, fname, true_cls, pred_cls, conf_s, ok_s, ok1 = msg
                    tag = "ok" if ok1 else "err"
                    iid = self._tree.insert(
                        "", END,
                        values=(fname, true_cls, pred_cls, conf_s, ok_s),
                        tags=(tag,))
                    self._tree.tag_configure("ok",  foreground=SUCCESS)
                    self._tree.tag_configure("err", foreground="#f05050")
                    self._tree.see(iid)
                elif kind == "progress":
                    n = msg[1]
                    total = int(self._pb["maximum"])
                    self._pb["value"] = n
                    self._lbl_prog.config(text=f"{n} / {total}")
                elif kind == "done":
                    _, total, c1, c5, a1, a5 = msg
                    self._on_batch_done(total, c1, c5, a1, a5)
                    return
        except queue.Empty:
            pass
        if self._batch_thread and self._batch_thread.is_alive():
            self.root.after(200, self._poll_batch)

    def _on_batch_done(self, total: int, c1: int, c5: int, a1: float, a5: float):
        self._btn_run.config(state=NORMAL)
        self._btn_stop.config(state=DISABLED, bg=CARD)
        stopped = self._stop_flag.is_set()
        prefix = "⚠ (Đã dừng)" if stopped else "✔"
        acc_text = (f"{prefix}  Top-1: {a1:.1f}%  |  Top-5: {a5:.1f}%"
                    f"  |  {c1} / {total} đúng")
        self._lbl_acc.config(text=acc_text, fg=SUCCESS if not stopped else DIM)
        self._lbl_prog.config(text=f"{total} / {total}", fg=DIM)
        _append_log(self._log, f"{prefix} Batch xong: {total} ảnh")
        _append_log(self._log, f"   Top-1: {a1:.1f}%  ({c1}/{total})")
        _append_log(self._log, f"   Top-5: {a5:.1f}%  ({c5}/{total})")

    def _stop(self, _=None):
        self._stop_flag.set()
        self._btn_stop.config(state=DISABLED, bg=CARD)
        _append_log(self._log, "⚠ Đang dừng sau ảnh hiện tại…")

    # ══════════════════════════════════════════════════════════ BARS / UI ══

    def _clear_bars(self):
        for lbl_n, lbl_p, inner, _ in self._bar_rows:
            lbl_n.config(text="—", fg=DIM)
            lbl_p.config(text="")
            inner.place(width=0)

    def _update_bars(self, pairs: list):
        self.update_idletasks()
        for i, (lbl_n, lbl_p, inner, outer) in enumerate(self._bar_rows):
            if i < len(pairs):
                cls, conf = pairs[i]
                lbl_n.config(text=cls[:13], fg=TEXT)
                lbl_p.config(text=f"{conf:.1%}", fg=TEXT)
                ow = max(outer.winfo_width(), 100)
                inner.place(x=0, y=0, relheight=1.0, width=int(conf * ow))
            else:
                lbl_n.config(text="—", fg=DIM)
                lbl_p.config(text="")
                inner.place(width=0)

    # ══════════════════════════════════════════════════════ HOTKEY HOOKS ══

    def _browse(self):
        """Ctrl+O từ app.py."""
        if self._v_mode.get() == "single":
            self._pick_image()
        else:
            self._pick_folder()

    def _start(self):
        """F5 từ app.py."""
        self._run()

    def _stop_action(self):
        """Esc từ app.py — dừng batch nếu đang chạy."""
        if self._batch_thread and self._batch_thread.is_alive():
            self._stop()
