# yolo_detect_all_mixin.py — YoloDetectAllMixin — Detect All hàng loạt trên thư mục + batch export
import os
import threading
import time
import queue as _q
from tkinter import *
from tkinter import filedialog, messagebox, ttk
from ...core.constants import (BG, CARD, ACCENT, ACCENT2, TEXT, DIM, SUCCESS,
                         F_MAIN, F_BOLD, F_MONO, IMAGE_EXTENSIONS)
from ...core.settings import (_bind_cfg, _cfg_dir, _CFG, _cfg_save,
                        _bind_history, _push_history, _get_history)
try:
    import cv2
    import numpy as np
    _CV2_OK = True
except ImportError:
    _CV2_OK = False
try:
    from PIL import Image, ImageDraw, ImageTk
    _PIL_OK = True
except ImportError:
    _PIL_OK = False
from ...shared.lazy_import import module_available, lazy_callable

_YOLO_OK = module_available("ultralytics")   # lazy — xem shared/lazy_import.py
YOLO     = lazy_callable("ultralytics", "YOLO")
try:
    import requests as _requests
    _REQ_OK = True
except ImportError:
    _REQ_OK = False


class YoloDetectAllMixin:
    """Mixin: chạy Detect All hàng loạt trên thư mục, batch export ảnh + nhãn."""

    # ======================================================== BATCH EXPORT ==

    def _batch_export(self):
        if not self.model:
            messagebox.showwarning("Chưa có model",
                                   "Vui lòng chọn model trước.", parent=self.root)
            return
        if not self.image_list:
            messagebox.showwarning("Chưa có ảnh",
                                   "Vui lòng chọn thư mục ảnh trước.", parent=self.root)
            return
        if not _CV2_OK:
            messagebox.showerror("Thiếu thư viện",
                                  "pip install opencv-python", parent=self.root)
            return

        out_dir = filedialog.askdirectory(
            title="Chọn thư mục lưu kết quả",
            initialdir=_cfg_dir("yolo.export_dir") or None,
            parent=self.root)
        if not out_dir:
            return
        _CFG["yolo.export_dir"] = out_dir
        _cfg_save()

        draw_on_image = self.v_export_draw.get()
        rename_file   = self.v_export_rename.get()

        _alive = [True]

        popup = Toplevel(self.root)
        popup.title("Export kết quả — Batch Detection")
        popup.configure(bg=BG)
        popup.geometry("560x320")
        popup.protocol("WM_DELETE_WINDOW", lambda: [_alive.__setitem__(0, False), popup.destroy()])

        Label(popup, text=f"Đang xử lý {len(self.image_list)} ảnh ...",
              font=F_BOLD, bg=BG, fg=TEXT).pack(pady=(12, 4))

        pb = ttk.Progressbar(popup, mode="determinate",
                              maximum=len(self.image_list))
        pb.pack(fill=X, padx=16, pady=(0, 4))

        v_prog = StringVar(value="0 / 0")
        Label(popup, textvariable=v_prog,
              font=F_MONO, bg=BG, fg=DIM).pack()

        txt_frame = Frame(popup, bg=BG)
        txt_frame.pack(fill=BOTH, expand=True, padx=8, pady=8)
        sb_log = Scrollbar(txt_frame, orient=VERTICAL)
        sb_log.pack(side=RIGHT, fill=Y)
        log_text = Text(txt_frame, bg="#0d0d1a", fg=TEXT, font=F_MONO,
                        relief="flat", bd=0, yscrollcommand=sb_log.set,
                        state=DISABLED)
        log_text.pack(fill=BOTH, expand=True)
        sb_log.config(command=log_text.yview)

        def _safe(fn):
            def _inner(*a, **kw):
                if not _alive[0]:
                    return
                try:
                    fn(*a, **kw)
                except Exception:
                    pass
            return _inner

        def append(line):
            log_text.config(state=NORMAL)
            log_text.insert(END, line + "\n")
            log_text.see(END)
            log_text.config(state=DISABLED)

        # Capture tất cả params trên main thread (Tkinter không thread-safe)
        sel_cls  = self._get_sel_classes()
        conf_val = max(self.v_conf_thresh.get(), self.v_conf.get())
        iou_val  = self.v_iou.get()
        line_w   = max(1, self.v_line_width.get())
        font_sz  = max(6, self.v_font_size.get())

        def run():
            import time
            from concurrent.futures import ThreadPoolExecutor


            images = list(self.image_list)
            total  = len(images)
            ok     = 0
            BATCH  = 8  # số ảnh predict cùng lúc

            log_buf  = []
            last_ui  = [time.monotonic()]
            pending  = []

            def _save_io(img_bgr, boxes_data, out_stem):
                try:
                    cv2.imwrite(os.path.join(out_dir, f"{out_stem}.jpg"), img_bgr)
                    with open(os.path.join(out_dir, f"{out_stem}.txt"),
                              "w", encoding="utf-8") as f:
                        for cid, cx, cy, bw, bh in boxes_data:
                            f.write(f"{cid} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")
                except Exception:
                    pass

            def _ui_flush(done, chunk):
                try:
                    pb.config(value=done)
                    v_prog.set(f"{done} / {total}")
                    if chunk:
                        append(chunk)
                except Exception:
                    pass

            io_pool = ThreadPoolExecutor(max_workers=4)

            for batch_start in range(0, total, BATCH):
                if not _alive[0]:
                    break
                batch_paths = images[batch_start:batch_start + BATCH]
                try:
                    results = self.model.predict(
                        source=batch_paths, classes=sel_cls,
                        conf=conf_val, iou=iou_val,
                        imgsz=640, agnostic_nms=True, verbose=False)
                    for img_path, res in zip(batch_paths, results):
                        base     = os.path.splitext(os.path.basename(img_path))[0]
                        out_stem = f"{base}_det" if rename_file else base
                        img_bgr  = (res.plot(line_width=line_w, font_size=font_sz)
                                    if draw_on_image else cv2.imread(img_path))
                        # Extract box data thành list thuần Python trước khi pass sang thread
                        boxes_data = []
                        if res.boxes is not None and len(res.boxes):
                            for box in res.boxes:
                                cid = int(box.cls[0])
                                cx, cy, bw, bh = box.xywhn[0].tolist()
                                boxes_data.append((cid, cx, cy, bw, bh))
                        if img_bgr is not None:
                            pending.append(
                                io_pool.submit(_save_io, img_bgr, boxes_data, out_stem))
                        n = len(boxes_data)
                        log_buf.append(f"  OK  {os.path.basename(img_path)}  ({n} obj)")
                        ok += 1
                except Exception as ex:
                    for p in batch_paths:
                        log_buf.append(f"  ERR {os.path.basename(p)}: {ex}")

                done = min(batch_start + BATCH, total)
                now  = time.monotonic()
                # Update UI tối đa mỗi 0.4s để không flood event queue
                if now - last_ui[0] >= 0.4 or done >= total:
                    last_ui[0] = now
                    chunk = "\n".join(log_buf); log_buf.clear()
                    self.root.after(0, _safe(lambda d=done, c=chunk: _ui_flush(d, c)))

            # Chờ tất cả I/O ghi xong
            for fut in pending:
                try:
                    fut.result(timeout=60)
                except Exception:
                    pass
            io_pool.shutdown(wait=False)

            self.root.after(0, _safe(lambda: pb.config(value=total)))
            self.root.after(0, _safe(lambda:
                append(f"\nHoàn tất: {ok}/{total} ảnh  →  {out_dir}")))

        threading.Thread(target=run, daemon=True).start()

    # ======================================================== DETECT ALL ==

    def _detect_all(self):
        if not self.model:
            messagebox.showwarning("Chưa có model",
                                   "Vui lòng chọn model trước.", parent=self.root)
            return
        if not self._all_images:
            messagebox.showwarning("Chưa có ảnh",
                                   "Vui lòng chọn thư mục ảnh trước.", parent=self.root)
            return
        if self._det_running:
            self._det_stop_flag = True
            return
        if not _CV2_OK and not _PIL_OK:
            messagebox.showerror("Thiếu thư viện",
                                  "pip install Pillow opencv-python", parent=self.root)
            return

        if hasattr(self, "lbl_cache_info"):
            self.lbl_cache_info.config(text="⏳…")

        all_images = list(self._all_images)
        sel_cls = self._get_sel_classes()
        conf    = max(self.v_conf_thresh.get(), self.v_conf.get())
        iou     = self.v_iou.get()

        def _prepare():
            # Load disk cache nếu bộ nhớ rỗng — chạy ở background để không block UI
            with self._det_cache_lock:
                cache_empty = not self._det_cache
            if cache_empty:
                self._load_det_cache_from_disk()

            # Tính pending: O(n) set lookup, không I/O
            with self._det_cache_lock:
                cached_nc = {os.path.normcase(k) for k in self._det_cache}
            pending = [p for p in all_images
                       if os.path.normcase(p) not in cached_nc]

            self.root.after(0, lambda: self._detect_all_run(
                pending, all_images, sel_cls, conf, iou))

        threading.Thread(target=_prepare, daemon=True).start()

    def _detect_all_run(self, pending: list, all_images: list,
                        sel_cls, conf: float, iou: float):
        """Tiếp tục detect sau khi pending list đã được tính trên background thread."""
        if not pending:
            n = len(self._det_cache)
            if hasattr(self, "lbl_cache_info"):
                self.lbl_cache_info.config(text=f"✓{n}/{n} (đã xong)")
            return

        self._det_stop_flag = False
        self._det_running = True
        self.btn_detect_all.config(text="■ Dừng", bg=ACCENT, fg="white")
        n_already   = len(all_images) - len(pending)
        n_total     = len(all_images)
        do_lpr      = (self.v_lpr_batch.get() and self.v_check_lpr.get()
                       and _REQ_OK and _PIL_OK)
        lpr_urls_b  = ([v.get().strip() for v in self._lpr_url_vars
                        if v.get().strip()] if do_lpr else [])
        lpr_tmout_b = self._lpr_timeout_var.get() if do_lpr else 10
        lpr_full_b  = [v.get() for v in self._lpr_fullimg_vars] if do_lpr else []

        def run():
            import time
            BATCH     = 8
            last_ui   = time.monotonic()
            n_pending = len(pending)
            _mtype    = self._model1_type  # snapshot (thread-safe read)

            for batch_start in range(0, n_pending, BATCH):
                if self._det_stop_flag:
                    break
                batch_paths = pending[batch_start:batch_start + BATCH]
                try:
                    if _mtype == "yolo":
                        results = self.model.predict(
                            source=batch_paths, classes=sel_cls,
                            conf=conf, iou=iou, imgsz=640,
                            agnostic_nms=True, verbose=False)
                        for img_path, res in zip(batch_paths, results):
                            boxes = res.boxes
                            n_det = len(boxes) if boxes is not None else 0
                            classes_count = {}
                            box_list = []
                            if boxes is not None and len(boxes):
                                for box in boxes:
                                    cid        = int(box.cls[0])
                                    conf_score = float(box.conf[0])
                                    classes_count[cid] = classes_count.get(cid, 0) + 1
                                    cx_n, cy_n, w_n, h_n = box.xywhn[0].tolist()
                                    w_px = float(box.xywh[0][2])
                                    h_px = float(box.xywh[0][3])
                                    box_list.append((cid, cx_n, cy_n, w_n, h_n, w_px, h_px, conf_score))
                            with self._det_cache_lock:
                                self._det_cache[img_path] = {
                                    "n": n_det,
                                    "classes": classes_count,
                                    "boxes": box_list,
                                }
                            # ── LPR batch ────────────────────────────────────
                            if do_lpr and lpr_urls_b and box_list:
                                lpr_res = self._lpr_batch_for_path(
                                    img_path, box_list, lpr_urls_b, lpr_tmout_b,
                                    lpr_full_b)
                                with self._lpr_cache_lock:
                                    self._lpr_cache[img_path] = lpr_res
                    else:
                        # RF-DETR / ONNX — xử lý từng ảnh (không hỗ trợ batch API)
                        from PIL import Image as _PImg, ImageOps as _IOps
                        for img_path in batch_paths:
                            if self._det_stop_flag:
                                break
                            try:
                                if _mtype == "rfdetr":
                                    _pil = _PImg.open(img_path).convert("RGB")
                                    try:
                                        _pil = _IOps.exif_transpose(_pil)
                                    except Exception:
                                        pass
                                    dets = self.model.predict(_pil, threshold=conf)
                                else:
                                    dets = self.model.predict(img_path, threshold=conf)
                                self._cache_sv_result(img_path, dets)
                            except Exception:
                                pass
                except Exception:
                    pass

                done_pending = min(batch_start + BATCH, n_pending)
                done_total   = n_already + done_pending
                now = time.monotonic()
                if now - last_ui >= 0.5 or done_pending >= n_pending:
                    last_ui = now
                    self.root.after(0, lambda d=done_total, t=n_total:
                        self.lbl_cache_info.config(text=f"{d}/{t}"))

            self.root.after(0, self._on_detect_all_done)

        threading.Thread(target=run, daemon=True).start()

    def _detect_page(self):
        """Detect chỉ các ảnh trên trang grid hiện tại."""
        if not self.model:
            messagebox.showwarning("Chưa có model",
                                   "Vui lòng chọn model trước.", parent=self.root)
            return
        if not self._grid_cells:
            return
        if self._det_running:
            messagebox.showwarning("Đang chạy",
                                   "Detect All đang chạy, vui lòng đợi.", parent=self.root)
            return
        if not _CV2_OK and not _PIL_OK:
            return

        page_paths = [c["path"] for c in self._grid_cells if c.get("path")]
        if not page_paths:
            return

        total       = len(page_paths)
        self.btn_detect_page.config(text="■ …", bg=ACCENT, fg="white")
        self.lbl_cache_info.config(text=f"0/{total}")
        sel_cls     = self._get_sel_classes()
        conf        = max(self.v_conf_thresh.get(), self.v_conf.get())
        iou         = self.v_iou.get()
        do_lpr      = (self.v_lpr_batch.get() and self.v_check_lpr.get()
                       and _REQ_OK and _PIL_OK)
        lpr_urls_p  = ([v.get().strip() for v in self._lpr_url_vars
                        if v.get().strip()] if do_lpr else [])
        lpr_tmout_p = self._lpr_timeout_var.get() if do_lpr else 10
        lpr_full_p  = [v.get() for v in self._lpr_fullimg_vars] if do_lpr else []
        _mtype_page = self._model1_type  # snapshot

        def run():
            import time
            BATCH   = 8
            for batch_start in range(0, total, BATCH):
                batch = page_paths[batch_start:batch_start + BATCH]
                try:
                    if _mtype_page == "yolo":
                        results = self.model.predict(
                            source=batch, classes=sel_cls,
                            conf=conf, iou=iou, imgsz=640,
                            agnostic_nms=True, verbose=False)
                        for img_path, res in zip(batch, results):
                            boxes = res.boxes
                            n_det = len(boxes) if boxes is not None else 0
                            classes_count = {}
                            box_list = []
                            if boxes is not None and len(boxes):
                                for box in boxes:
                                    cid        = int(box.cls[0])
                                    conf_score = float(box.conf[0])
                                    classes_count[cid] = classes_count.get(cid, 0) + 1
                                    cx_n, cy_n, w_n, h_n = box.xywhn[0].tolist()
                                    w_px = float(box.xywh[0][2])
                                    h_px = float(box.xywh[0][3])
                                    box_list.append((cid, cx_n, cy_n, w_n, h_n, w_px, h_px, conf_score))
                            with self._det_cache_lock:
                                self._det_cache[img_path] = {
                                    "n": n_det, "classes": classes_count, "boxes": box_list,
                                }
                            # ── LPR batch ────────────────────────────────────
                            if do_lpr and lpr_urls_p and box_list:
                                lpr_res = self._lpr_batch_for_path(
                                    img_path, box_list, lpr_urls_p, lpr_tmout_p,
                                    lpr_full_p)
                                with self._lpr_cache_lock:
                                    self._lpr_cache[img_path] = lpr_res
                    else:
                        # RF-DETR / ONNX — per image
                        from PIL import Image as _PImg, ImageOps as _IOps
                        for img_path in batch:
                            try:
                                if _mtype_page == "rfdetr":
                                    _pil = _PImg.open(img_path).convert("RGB")
                                    try:
                                        _pil = _IOps.exif_transpose(_pil)
                                    except Exception:
                                        pass
                                    dets = self.model.predict(_pil, threshold=conf)
                                else:
                                    dets = self.model.predict(img_path, threshold=conf)
                                self._cache_sv_result(img_path, dets)
                            except Exception:
                                pass
                except Exception:
                    pass
                done = min(batch_start + BATCH, total)
                self.root.after(0, lambda d=done, t=total:
                    self.lbl_cache_info.config(text=f"{d}/{t}"))

            self.root.after(0, self._on_detect_page_done)

        threading.Thread(target=run, daemon=True).start()

    def _on_detect_page_done(self):
        self.btn_detect_page.config(text="⚡ Detect trang", bg="#102030", fg="#4caf50")
        n = len(self._det_cache)
        total = len(self._all_images)
        self.lbl_cache_info.config(text=f"✓{n}/{total}")
        self._grid_rendered_cache.clear()
        self._rebuild_grid()
        self._save_det_cache_to_disk()

    def _on_detect_all_progress(self, done: int, total: int):
        self.lbl_cache_info.config(text=f"{done}/{total}")

    def _on_detect_all_done(self):
        self._det_running = False
        self._det_stop_flag = False
        self.btn_detect_all.config(text="⚡ Detect All",
                                   bg="#103020", fg="#4caf50")
        n = len(self._det_cache)
        total = len(self._all_images)
        self.lbl_cache_info.config(text=f"✓{n}/{total}")
        self._grid_rendered_cache.clear()
        self._update_class_filter_combo()
        self._apply_filter(self._active_filter)
        self._rebuild_grid()
        self._save_det_cache_to_disk()
