# yolo_detect_mixin.py — YoloDetectMixin — pipeline detect 1 ảnh + hiển thị, slider conf/iou
import os
import threading
import time
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
try:
    import requests as _requests
    _REQ_OK = True
except ImportError:
    _REQ_OK = False


class YoloDetectMixin:
    """Mixin: chạy detect 1 ảnh + hiển thị kết quả, slider conf/iou, det table."""

    # =========================================================== DETECTION ==

    def _sync_slider_labels(self):
        self.lbl_conf_thresh_val.config(text=f"{self.v_conf_thresh.get():.2f}")
        self.lbl_conf.config(text=f"{self.v_conf.get():.2f}")
        self.lbl_iou.config(text=f"{self.v_iou.get():.2f}")

    def _on_conf_thresh_change(self, _=None):
        self.lbl_conf_thresh_val.config(text=f"{self.v_conf_thresh.get():.2f}")
        # conf_thresh là bộ lọc hiển thị — KHÔNG xóa cache, chỉ re-render từ cache với ngưỡng mới
        self._grid_rendered_cache.clear()
        if self.current_image_path and self.model:
            self._detect_and_display()

    def _on_slider_change(self, _=None):
        self.lbl_conf.config(text=f"{self.v_conf.get():.2f}")
        self.lbl_iou.config(text=f"{self.v_iou.get():.2f}")
        if not self.current_image_path:
            return
        with self._det_cache_lock:
            in_cache = self.current_image_path in self._det_cache
        if in_cache:
            # Ảnh đã có cache → filter conf từ cache, không re-detect
            self._grid_rendered_cache.clear()
            self._detect_and_display()
        else:
            # Không có cache → chạy detect với params mới
            self._detect_and_display()

    def _get_sel_classes(self):
        sel_idx = self.lb_classes.curselection()
        return [self.class_ids[i] for i in sel_idx] if sel_idx else None

    def _on_plot_param_change(self):
        """Debounce 200 ms — tránh render liên tục khi kéo slider."""
        if self._plot_after:
            self.after_cancel(self._plot_after)
        self._plot_after = self.after(200, self._do_replot)

    def _do_replot(self):
        self._plot_after = None
        self._grid_rendered_cache.clear()
        if self._last_results1 is not None:
            try:
                pil1, ann1_bgr = self._annotated_to_pil(self._last_results1)
                self._last_annotated_bgr = ann1_bgr
                self._pil1_full = pil1
                self._render_display()
            except Exception:
                pass
        elif self.current_image_path and self.current_image_path in self._det_cache:
            # Đang hiển thị từ cache → vẽ lại với font/line mới
            try:
                pil1 = self._annotated_from_cache(self.current_image_path)
                ann1_bgr = cv2.cvtColor(np.array(pil1), cv2.COLOR_RGB2BGR)
                self._last_annotated_bgr = ann1_bgr
                self._pil1_full = pil1
                self._render_display()
            except Exception:
                pass
        self._schedule_grid_rebuild()

    def _detect_and_display(self):
        """Chạy YOLO detect trên background thread — không block UI."""
        if not self.current_image_path or not self.model:
            return
        if not _PIL_OK or not _CV2_OK:
            self.lbl_result.config(
                text="Cần cài: pip install Pillow opencv-python", fg=ACCENT)
            return
        if self._detecting:
            self._det_pending = True  # re-detect sau khi xong
            return
        self._detecting   = True
        self._det_pending = False
        self.lbl_result.config(text="⏳ Đang nhận diện…", fg=DIM)

        img_path         = self.current_image_path  # capture trước khi user chuyển ảnh
        model1           = self.model
        model1_type      = self._model1_type
        model1_names_cap = dict(self._model1_names)
        model2           = self.model2
        model2_type      = self._model2_type
        model2_names_cap = dict(self._model2_names)
        model3           = self.model3
        model3_type      = self._model3_type
        sel_cls          = self._get_sel_classes()
        # Capture params trên main thread (Tkinter widget không thread-safe)
        conf_val = max(self.v_conf_thresh.get(), self.v_conf.get())
        iou_val  = self.v_iou.get()
        check_lpr   = self.v_check_lpr.get()
        lpr_urls    = ([v.get().strip() for v in self._lpr_url_vars
                        if v.get().strip()] if check_lpr else [])
        lpr_timeout = self._lpr_timeout_var.get() if check_lpr else 10
        lpr_fullimg = [v.get() for v in self._lpr_fullimg_vars] if check_lpr else []
        # Dùng cache nếu có (nhất quán với grid thumbnail), trừ dual-model mode.
        # Cache chỉ lưu bbox (không lưu mask) → model Segment luôn detect lại để hiện mask.
        with self._det_cache_lock:
            cached = (self._det_cache.get(img_path)
                      if (model2 is None and model3 is None
                          and not self._is_seg_model(model1)) else None)

        def _run():
            try:
                if cached is not None:
                    # ── Cache hit: vẽ từ cache, filter theo max(conf_thresh, conf) ──
                    _t1 = time.time()
                    pil1     = self._annotated_from_cache(img_path)
                    ann1_bgr = cv2.cvtColor(np.array(pil1), cv2.COLOR_RGB2BGR)
                    try:
                        from PIL import ImageOps
                        pil_orig = Image.open(img_path).convert("RGB")
                        pil_orig = ImageOps.exif_transpose(pil_orig)
                    except Exception:
                        pil_orig = None
                    # Tính n_det và summary chỉ với boxes vượt qua effective threshold
                    filtered_boxes = [b for b in cached["boxes"]
                                      if (len(b) > 7 and float(b[7]) >= conf_val)]
                    n_det = len(filtered_boxes)
                    filtered_classes = {}
                    for b in filtered_boxes:
                        cid = int(b[0])
                        filtered_classes[cid] = filtered_classes.get(cid, 0) + 1
                    _names = model1_names_cap or {}
                    if not _names and hasattr(model1, "names"):
                        try:
                            _names = dict(model1.names) or {}
                        except Exception:
                            pass
                    summary = "  |  ".join(
                        f"{_names.get(k, str(k))}: {v}"
                        for k, v in filtered_classes.items())
                    # ── LPR overlay (B2+B3) ────────────────────────────────
                    if check_lpr and lpr_urls and _REQ_OK and filtered_boxes:
                        with self._lpr_cache_lock:
                            _lpr_hit = self._lpr_cache.get(img_path)
                        if _lpr_hit is not None:
                            pil1 = self._lpr_draw_from_results(pil1, _lpr_hit)
                        else:
                            iw, ih = pil1.size
                            bwc = [(
                                max(0, int((b[1] - b[3] / 2) * iw)),
                                max(0, int((b[2] - b[4] / 2) * ih)),
                                min(iw - 1, int((b[1] + b[3] / 2) * iw)),
                                min(ih - 1, int((b[2] + b[4] / 2) * ih)),
                                int(b[0]),
                            ) for b in filtered_boxes]
                            pil1 = self._lpr_overlay_boxes(
                                pil1, pil_orig, bwc, lpr_urls, lpr_timeout,
                                _names, lpr_fullimg)
                            with self._lpr_cache_lock:
                                self._lpr_cache[img_path] = list(
                                    self._last_lpr_plates_result)
                        ann1_bgr = cv2.cvtColor(np.array(pil1), cv2.COLOR_RGB2BGR)
                    t1_ms = (time.time() - _t1) * 1000
                    self.root.after(0, lambda: self._on_detect_done(
                        img_path, None, pil1, ann1_bgr, pil_orig,
                        n_det, summary, None, None, None, 0, "",
                        None, None, 0, "",
                        t1_ms, None, None))
                else:
                    # ── Không có cache: chạy model, lưu cache ──
                    try:
                        from PIL import ImageOps
                        pil_orig = Image.open(img_path).convert("RGB")
                        pil_orig = ImageOps.exif_transpose(pil_orig)
                    except Exception:
                        pil_orig = None

                    if model1_type == "yolo":
                        _t1 = time.time()
                        results1 = self._run_model(model1, img_path, sel_cls, conf_val, iou_val)
                        t1_ms = (time.time() - _t1) * 1000
                        n_det, summary = self._results_summary(results1, model1.names)
                        self._cache_single_result(img_path, results1)
                        pil1, ann1_bgr = self._annotated_to_pil(results1)
                        # ── LPR overlay ────────────────────────────────────
                        if check_lpr and lpr_urls and _REQ_OK:
                            _boxes = results1[0].boxes
                            if _boxes is not None and len(_boxes):
                                with self._lpr_cache_lock:
                                    _lpr_hit = self._lpr_cache.get(img_path)
                                if _lpr_hit is not None:
                                    pil1 = self._lpr_draw_from_results(pil1, _lpr_hit)
                                else:
                                    _cls_list = [int(c) for c in _boxes.cls.tolist()]
                                    _bwc = [(int(v[0]), int(v[1]), int(v[2]), int(v[3]),
                                             _cls_list[i])
                                            for i, v in enumerate(_boxes.xyxy.tolist())]
                                    _mn = dict(model1.names) if hasattr(model1, "names") else {}
                                    pil1 = self._lpr_overlay_boxes(
                                        pil1, pil_orig, _bwc, lpr_urls, lpr_timeout,
                                        _mn, lpr_fullimg)
                                    with self._lpr_cache_lock:
                                        self._lpr_cache[img_path] = list(
                                            self._last_lpr_plates_result)
                                ann1_bgr = cv2.cvtColor(np.array(pil1), cv2.COLOR_RGB2BGR)
                    else:
                        # M1 là RF-DETR hoặc ONNX
                        _t1 = time.time()
                        if model1_type == "rfdetr":
                            _pil_in1 = pil_orig.copy() if pil_orig else Image.open(img_path).convert("RGB")
                            dets1 = model1.predict(_pil_in1, threshold=conf_val)
                        else:
                            dets1 = model1.predict(img_path, threshold=conf_val)
                        t1_ms   = (time.time() - _t1) * 1000
                        n_det   = len(dets1.xyxy) if hasattr(dets1, "xyxy") and dets1.xyxy is not None else 0
                        summary = self._sv_summary(dets1, model1_names_cap)
                        self._cache_sv_result(img_path, dets1)
                        _base_pil = pil_orig.copy() if pil_orig else Image.open(img_path).convert("RGB")
                        pil1 = self._draw_sv_on_pil(_base_pil, dets1, model1_names_cap)
                        ann1_bgr = cv2.cvtColor(np.array(pil1), cv2.COLOR_RGB2BGR)
                        results1 = None

                    # ── Model 2 ────────────────────────────────────────────
                    t2_ms = None
                    if model2 is not None:
                        if model2_type == "yolo":
                            _t2 = time.time()
                            results2 = self._run_model(model2, img_path, sel_cls, conf_val, iou_val)
                            t2_ms = (time.time() - _t2) * 1000
                            n_det2, summary2 = self._results_summary(results2, model2.names)
                            if model1_type == "yolo":
                                # Gộp 2 model YOLO lên 1 ảnh (cyan M1, cam M2)
                                pil1, ann1_bgr = self._annotated_combined_pil(
                                    results1, results2, model2)
                            else:
                                # M1 non-YOLO: overlay M2 YOLO boxes lên pil1 đã có M1
                                pil1 = self._draw_yolo_panel_on_pil(
                                    pil1, results2,
                                    dict(model2.names) if hasattr(model2, "names") else model2_names_cap,
                                    self._PANEL2_COLOR, "M2:")
                                ann1_bgr = cv2.cvtColor(np.array(pil1), cv2.COLOR_RGB2BGR)
                        else:
                            # M2 là RF-DETR hoặc ONNX
                            _t2 = time.time()
                            if model2_type == "rfdetr":
                                _pil_in2 = pil_orig.copy() if pil_orig else Image.open(img_path).convert("RGB")
                                dets2 = model2.predict(_pil_in2, threshold=conf_val)
                            else:
                                dets2 = model2.predict(img_path, threshold=conf_val)
                            t2_ms    = (time.time() - _t2) * 1000
                            n_det2   = len(dets2.xyxy) if hasattr(dets2, "xyxy") and dets2.xyxy is not None else 0
                            summary2 = self._sv_summary(dets2, model2_names_cap)
                            pil1 = self._draw_sv_on_pil(pil1, dets2, model2_names_cap,
                                                         self._PANEL2_COLOR, "M2:")
                            ann1_bgr = cv2.cvtColor(np.array(pil1), cv2.COLOR_RGB2BGR)
                            results2 = None
                        # Áp LPR overlay từ cache (đã tính ở bước model1 phía trên)
                        if check_lpr and lpr_urls and _REQ_OK:
                            with self._lpr_cache_lock:
                                _lpr_c2 = self._lpr_cache.get(img_path)
                            if _lpr_c2 is not None:
                                pil1 = self._lpr_draw_from_results(pil1, _lpr_c2)
                                ann1_bgr = cv2.cvtColor(np.array(pil1), cv2.COLOR_RGB2BGR)
                        pil2 = None   # combined mode — không dùng side-by-side
                    else:
                        results2, pil2, n_det2, summary2 = None, None, 0, ""
                    # ── Model 3 (RF-DETR .pt  hoặc  YOLO .onnx) ──────────
                    t3_ms = None
                    if model3 is not None:
                        try:
                            if model3_type == "onnx":
                                # Generic ONNX via _OnnxRunner (tự đọc input name)
                                _t3    = time.time()
                                dets3  = model3.predict(img_path, threshold=conf_val)
                                t3_ms  = (time.time() - _t3) * 1000
                                n_det3 = len(dets3.xyxy) if dets3.xyxy is not None else 0
                                summary3 = self._rfdetr_summary(dets3)
                                pil1   = self._draw_rfdetr_on_pil(pil1, dets3)
                                dets3  = dets3
                            elif model3_type == "yolo":
                                # ONNX dùng ultralytics (legacy, kept for safety)
                                _t3      = time.time()
                                _res3    = self._run_model(model3, img_path, sel_cls,
                                                           conf_val, iou_val)
                                t3_ms    = (time.time() - _t3) * 1000
                                n_det3, summary3 = self._results_summary(
                                    _res3, model3.names)
                                pil1 = self._draw_yolo_m3_on_pil(pil1, _res3)
                                dets3 = _res3
                            else:
                                # RF-DETR .pt dùng rfdetr (sv.Detections)
                                from PIL import Image as _PILImg, ImageOps as _IOps
                                _pil_in = _PILImg.open(img_path).convert("RGB")
                                try:
                                    _pil_in = _IOps.exif_transpose(_pil_in)
                                except Exception:
                                    pass
                                _t3   = time.time()
                                dets3 = model3.predict(_pil_in, threshold=conf_val)
                                t3_ms = (time.time() - _t3) * 1000
                                _d3_len = (len(dets3.xyxy)
                                           if hasattr(dets3, "xyxy") and dets3.xyxy is not None
                                           else 0)
                                n_det3   = _d3_len
                                summary3 = self._rfdetr_summary(dets3)
                                pil1     = self._draw_rfdetr_on_pil(pil1, dets3)
                            ann1_bgr = cv2.cvtColor(np.array(pil1), cv2.COLOR_RGB2BGR)
                        except Exception as _e3:
                            dets3, n_det3, summary3 = None, 0, f"Err:{_e3}"
                    else:
                        dets3, n_det3, summary3 = None, 0, ""
                    _m3_ref  = model3
                    _d3_ref  = dets3
                    _n3_ref  = n_det3
                    _s3_ref  = summary3
                    self.root.after(0, lambda: self._on_detect_done(
                        img_path, results1, pil1, ann1_bgr, pil_orig, n_det, summary,
                        model2, results2, pil2, n_det2, summary2,
                        _m3_ref, _d3_ref, _n3_ref, _s3_ref,
                        t1_ms, t2_ms, t3_ms))
            except Exception as e:
                err = str(e)
                self.root.after(0, lambda: self._on_detect_error(err))

        threading.Thread(target=_run, daemon=True).start()

    def _on_detect_done(self, img_path, results1, pil1, ann1_bgr, pil_orig,
                         n_det, summary, model2, results2, pil2, n_det2, summary2,
                         model3=None, dets3=None, n_det3=0, summary3="",
                         t1_ms=None, t2_ms=None, t3_ms=None):
        self._detecting = False
        pending = self._det_pending
        self._det_pending = False
        # Bỏ qua nếu user đã chuyển sang ảnh khác trong lúc detect
        if img_path != self.current_image_path:
            if pending:
                self._detect_and_display()
            return

        self._last_annotated_bgr = ann1_bgr
        self._last_results1      = results1
        self._refresh_det_table(results1, model2, results2, model3, dets3)

        if model2 is not None or model3 is not None:
            # Combined mode — 1 ảnh, nhiều model, mỗi model 1 màu bbox
            _m1_tag = {"rfdetr": "[DETR]", "onnx": "[ONNX]"}.get(self._model1_type, "")
            m1_name = os.path.basename(self.v_model_path.get())
            title_parts = [f"M1{_m1_tag}:{m1_name} ({n_det})"]
            total_det   = n_det
            if model2 is not None:
                _m2_tag = {"rfdetr": "[DETR]", "onnx": "[ONNX]"}.get(self._model2_type, "")
                m2_name = os.path.basename(self.v_model2_path.get())
                title_parts.append(f"M2{_m2_tag}:{m2_name} ({n_det2})")
                total_det += n_det2
            if model3 is not None:
                m3_name = os.path.basename(self.v_model3_path.get())
                m3_tag  = "ONNX" if self._model3_type == "onnx" else "DETR"
                title_parts.append(f"M3({m3_tag}):{m3_name} ({n_det3})")
                total_det += n_det3
            self.lbl_panel1_title.config(text="  |  ".join(title_parts))
            self.panel2_frame.pack_forget()
            self.lbl_panel2_title.config(text="")

            self._pil1_full  = pil1
            self._pil1_orig  = pil_orig
            self._last_n_det = total_det
            self._render_display()

            # ── Per-model result labels với màu sai khác ──────────────────
            active_counts = [n_det]
            if model2 is not None: active_counts.append(n_det2)
            if model3 is not None: active_counts.append(n_det3)
            # Đa số (majority count)
            from collections import Counter as _Counter
            majority = _Counter(active_counts).most_common(1)[0][0]

            def _model_color(count, is_active):
                if not is_active:
                    return DIM
                if count == 0 and majority > 0:
                    return "#e53935"   # đỏ — không detect được gì trong khi model khác có
                if count != majority:
                    return ACCENT      # cam — sai khác so với đa số
                return SUCCESS         # xanh — khớp

            def _model_prefix(count, is_active):
                if not is_active: return ""
                if count == 0 and majority > 0: return "✗ "
                if count != majority: return "⚠ "
                return "✓ "

            # Cập nhật 3 label riêng (kèm thời gian nhận dạng ⏱ của từng model)
            _t1_txt = f"  ⏱{t1_ms:.0f}ms" if t1_ms is not None else ""
            _t2_txt = f"  ⏱{t2_ms:.0f}ms" if t2_ms is not None else ""
            _t3_txt = f"  ⏱{t3_ms:.0f}ms" if t3_ms is not None else ""
            m1txt = (f"{_model_prefix(n_det, True)}Model1{_m1_tag}: {n_det} obj"
                     + (f"  [{summary}]" if summary else "") + _t1_txt)
            self._lbl_m1_res.config(text=m1txt, fg=_model_color(n_det, True))

            if model2 is not None:
                m2txt = (f"{_model_prefix(n_det2, True)}Model2{_m2_tag}: {n_det2} obj"
                         + (f"  [{summary2}]" if summary2 else "") + _t2_txt)
                self._lbl_m2_res.config(text=m2txt, fg=_model_color(n_det2, True))
            else:
                self._lbl_m2_res.config(text="")

            if model3 is not None:
                m3txt = (f"{_model_prefix(n_det3, True)}Model3({m3_tag}): {n_det3} obj"
                         + (f"  [{summary3}]" if summary3 else "") + _t3_txt)
                self._lbl_m3_res.config(text=m3txt, fg=_model_color(n_det3, True))
            else:
                self._lbl_m3_res.config(text="")

            self.lbl_result.config(text="")
        else:
            # Single panel
            self.panel2_frame.pack_forget()
            self.lbl_panel1_title.config(text="")
            self._lbl_m1_res.config(text="")
            self._lbl_m2_res.config(text="")
            self._lbl_m3_res.config(text="")

            self._pil1_full = pil1
            self._pil1_orig = pil_orig
            self._last_n_det = n_det
            self._render_display()

            _time_txt = f"   ⏱ {t1_ms:.0f}ms" if t1_ms is not None else ""
            if n_det > 0:
                self.lbl_result.config(
                    text=f"Phát hiện {n_det} đối tượng  —  {summary}{_time_txt}", fg=SUCCESS)
            else:
                self.lbl_result.config(
                    text=f"Không phát hiện đối tượng nào{_time_txt}", fg=DIM)

        # Nếu slider thay đổi trong lúc detect → re-detect ngay với params mới
        if pending:
            self._detect_and_display()

    def _on_detect_error(self, err: str):
        self._detecting = False
        pending = self._det_pending
        self._det_pending = False
        self.lbl_result.config(text=f"Lỗi: {err}", fg=ACCENT)
        if pending:
            self._detect_and_display()

    # ============================================ DET TABLE HELPERS ==

    def _refresh_det_table(self, results1, model2, results2, model3, dets3):
        """Populate bảng chi tiết detect từ kết quả mới nhất."""
        if not self._det_table:
            return
        rows = []
        thresh = self.v_conf_thresh.get()

        # --- Model 1 (YOLO) ---
        if results1 is not None:
            boxes = results1[0].boxes
            names = getattr(self.model, "names", {}) or {}
            if boxes is not None:
                for box in boxes:
                    conf = float(box.conf[0])
                    if conf < thresh:
                        continue
                    x1, y1, x2, y2 = (int(v) for v in box.xyxy[0])
                    rows.append({
                        "model": "M1",
                        "class_name": names.get(int(box.cls[0]), str(int(box.cls[0]))),
                        "conf": conf, "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                        "w": x2 - x1, "h": y2 - y1,
                    })

        # --- Model 2 (YOLO) ---
        if model2 is not None and results2 is not None:
            boxes2 = results2[0].boxes
            names2 = getattr(model2, "names", {}) or {}
            if boxes2 is not None:
                for box in boxes2:
                    conf = float(box.conf[0])
                    if conf < thresh:
                        continue
                    x1, y1, x2, y2 = (int(v) for v in box.xyxy[0])
                    rows.append({
                        "model": "M2",
                        "class_name": names2.get(int(box.cls[0]), str(int(box.cls[0]))),
                        "conf": conf, "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                        "w": x2 - x1, "h": y2 - y1,
                    })

        # --- Model 3 (RF-DETR / ONNX / YOLO) ---
        if model3 is not None and dets3 is not None:
            names3 = self._model3_names
            if self._model3_type == "yolo":
                # dets3 là YOLO results list
                boxes3 = dets3[0].boxes if dets3 else None
                names3y = getattr(model3, "names", {}) or names3
                if boxes3 is not None:
                    for box in boxes3:
                        conf = float(box.conf[0])
                        if conf < thresh:
                            continue
                        x1, y1, x2, y2 = (int(v) for v in box.xyxy[0])
                        rows.append({
                            "model": "M3",
                            "class_name": names3y.get(int(box.cls[0]), str(int(box.cls[0]))),
                            "conf": conf, "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                            "w": x2 - x1, "h": y2 - y1,
                        })
            else:
                # dets3 là _OnnxDetResult / sv.Detections
                confs = getattr(dets3, "confidence", None)
                cids  = getattr(dets3, "class_id",  None)
                xyxys = getattr(dets3, "xyxy",      None)
                if xyxys is not None:
                    for i, box in enumerate(xyxys):
                        conf = float(confs[i]) if confs is not None else 0.0
                        if conf < thresh:
                            continue
                        x1, y1, x2, y2 = (int(v) for v in box)
                        cid = int(cids[i]) if cids is not None else 0
                        rows.append({
                            "model": "M3",
                            "class_name": names3.get(cid, str(cid)),
                            "conf": conf, "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                            "w": x2 - x1, "h": y2 - y1,
                        })

        self._det_table.update(rows)

    def _on_det_row_select(self, row):
        """Zoom canvas tới bbox được chọn trong bảng detect (double-click)."""
        pil = self._pil1_full or self._pil1_orig
        if pil is None:
            return
        x1, y1, x2, y2 = row["x1"], row["y1"], row["x2"], row["y2"]
        bw, bh = max(x2 - x1, 1), max(y2 - y1, 1)
        cw = max(self.canvas.winfo_width(),  400)
        ch = max(self.canvas.winfo_height(), 300)
        # Zoom để bbox chiếm ~60% canvas, có margin
        zoom = min(cw / (bw * 1.8), ch / (bh * 1.8), 12.0)
        zoom = max(zoom, 0.5)
        cx_img = (x1 + x2) / 2
        cy_img = (y1 + y2) / 2
        self._zoom_factor = zoom
        self._img_pos = [cw / 2 - cx_img * zoom, ch / 2 - cy_img * zoom]
        self._render_display()
