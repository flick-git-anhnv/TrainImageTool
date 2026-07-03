# yolo_render_mixin.py — YoloRenderMixin — vẽ kết quả detect (bbox/mask) lên ảnh PIL
import os
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
from .yolo_onnx import _contrast_text


class YoloRenderMixin:
    """Mixin: annotate/draw bbox, mask segment, so sánh nhiều model lên PIL."""

    def _run_model(self, mdl, image_path, sel_cls,
                   conf: float = 0.25, iou: float = 0.45):
        # Model Segment → retina_masks=True cho mask nét theo đúng độ phân giải ảnh gốc
        seg_kw = {"retina_masks": True} if self._is_seg_model(mdl) else {}
        return mdl.predict(
            source=image_path,
            classes=sel_cls,
            conf=conf,
            iou=iou,
            imgsz=640,
            agnostic_nms=True,
            verbose=False,
            **seg_kw,
        )

    def _results_summary(self, results, model_names):
        boxes = results[0].boxes
        n_det = len(boxes) if boxes is not None else 0
        if n_det > 0:
            counts = {}
            for cls_id in boxes.cls.tolist():
                name = model_names[int(cls_id)]
                counts[name] = counts.get(name, 0) + 1
            summary = "  |  ".join(f"{n}: {c}" for n, c in counts.items())
            return n_det, summary
        return 0, ""

    # Màu cố định cho từng panel khi so sánh multi-model
    _PANEL1_COLOR = (0, 200, 255)    # cyan  — Model 1
    _PANEL2_COLOR = (240, 89, 34)    # orange ACCENT — Model 2
    _PANEL3_COLOR = (50, 220, 50)    # lime green — Model 3 (RF-DETR)

    # Bảng màu theo instance — dùng khi Segment chỉ có 1 class, tô mỗi đối tượng 1 màu
    _INSTANCE_COLORS = [
        (66, 133, 244), (234, 67, 53),  (52, 168, 83),  (251, 188, 5),
        (154, 52, 182), (0, 172, 193),  (255, 112, 67), (156, 204, 101),
        (63, 81, 181),  (233, 30, 99),  (0, 150, 136),  (255, 193, 7),
        (121, 85, 72),  (96, 125, 139), (244, 67, 54),  (139, 195, 74),
    ]

    @staticmethod
    def _is_seg_model(mdl) -> bool:
        """True nếu model YOLO đã load là model Segment (yolo11*-seg.pt)."""
        return mdl is not None and getattr(mdl, "task", "") == "segment"

    def _overlay_seg_masks(self, pil_img, results, color_fn, alpha=90, line_width=2):
        """Vẽ mask (polygon) của model YOLO-Seg lên PIL Image: fill bán trong suốt
        + viền polygon nét liền (thay cho khung bbox chữ nhật).
        color_fn(cls_id, idx) -> (r,g,b) — idx là thứ tự instance trong ảnh
        (dùng khi cần tô mỗi đối tượng 1 màu, ví dụ model chỉ có 1 class).
        Không đổi gì nếu results không có masks (model Detect hoặc không phát hiện gì)."""
        masks = getattr(results[0], "masks", None) if results else None
        if masks is None or masks.xy is None or len(masks.xy) == 0:
            return pil_img
        boxes   = results[0].boxes
        overlay = Image.new("RGBA", pil_img.size, (0, 0, 0, 0))
        odraw   = ImageDraw.Draw(overlay)
        for i, poly in enumerate(masks.xy):
            if poly is None or len(poly) < 3:
                continue
            cls_id = int(boxes.cls[i]) if boxes is not None and i < len(boxes) else 0
            r, g, b = color_fn(cls_id, i)
            pts = [(float(x), float(y)) for x, y in poly]
            odraw.polygon(pts, fill=(r, g, b, alpha))
            odraw.line(pts + [pts[0]], fill=(r, g, b, 255),
                       width=max(1, line_width), joint="curve")
        return Image.alpha_composite(pil_img.convert("RGBA"), overlay).convert("RGB")

    @staticmethod
    def _seg_has_poly(masks, i: int) -> bool:
        """True nếu masks.xy[i] là polygon hợp lệ (≥3 điểm) — dùng để quyết định
        vẽ viền polygon thay vì khung bbox chữ nhật cho instance thứ i."""
        return bool(masks is not None and masks.xy is not None
                    and i < len(masks.xy) and masks.xy[i] is not None
                    and len(masks.xy[i]) >= 3)

    def _annotated_to_pil(self, results, single_color=None):
        """Vẽ annotation bằng PIL để font_size hoạt động độc lập với line_width.
        single_color: tuple RGB — dùng màu cố định này cho mọi box (bỏ qua class).
        Dùng trong dual-panel mode để 2 panel có màu khác nhau rõ ràng."""
        from PIL import ImageFont, ImageDraw as _Draw

        lw = max(1, self.v_line_width.get())
        fs = max(6, self.v_font_size.get())

        orig_bgr = results[0].orig_img
        orig_rgb = cv2.cvtColor(orig_bgr, cv2.COLOR_BGR2RGB)
        pil_img  = Image.fromarray(orig_rgb)

        try:
            font = ImageFont.truetype("arial.ttf", fs)
        except Exception:
            try:
                font = ImageFont.load_default(size=fs)
            except Exception:
                font = ImageFont.load_default()

        boxes = results[0].boxes
        names = getattr(results[0], "names", {}) or {}
        if not isinstance(names, dict):
            names = {}
        masks = getattr(results[0], "masks", None)

        # Segment + chỉ 1 class trong ảnh → tô mỗi đối tượng 1 màu riêng (theo index)
        # cho dễ phân biệt, thay vì tất cả cùng 1 màu class.
        _n_uniq_cls = (len({int(b.cls[0]) for b in boxes})
                       if boxes is not None and len(boxes) else 0)
        _use_instance_color = (single_color is None and masks is not None
                                and masks.xy is not None and len(masks.xy) > 0
                                and _n_uniq_cls <= 1)

        # Màu theo class (single panel), theo instance (segment 1-class), hoặc cố định (dual panel)
        if single_color is not None:
            def _color(_cls_id, _idx):
                return single_color
        elif _use_instance_color:
            def _color(_cls_id, idx):
                return self._INSTANCE_COLORS[idx % len(self._INSTANCE_COLORS)]
        else:
            try:
                from ultralytics.utils.plotting import colors as _yc
                def _color(cls_id, _idx):
                    c = _yc(int(cls_id), True)
                    return (int(c[2]), int(c[1]), int(c[0]))
            except Exception:
                _pal = [(0,200,255),(0,255,0),(255,100,0),(255,0,200),(200,200,0)]
                def _color(cls_id, _idx):
                    return _pal[int(cls_id) % len(_pal)]

        # Model Segment (YOLO-Seg) → vẽ mask polygon (fill + viền) trước, label sau
        pil_img = self._overlay_seg_masks(pil_img, results, _color, line_width=lw)
        draw    = _Draw.Draw(pil_img)

        if boxes is not None and len(boxes):
            for i, box in enumerate(boxes):
                x1, y1, x2, y2 = (int(v) for v in box.xyxy[0])
                cls_id   = int(box.cls[0])
                conf     = float(box.conf[0])
                cls_name = names.get(cls_id, str(cls_id))
                label    = f"{cls_name} {conf:.2f}"
                color    = _color(cls_id, i)

                # Segment: viền polygon đã vẽ trong _overlay_seg_masks → không vẽ khung chữ nhật
                if not self._seg_has_poly(masks, i):
                    draw.rectangle([x1, y1, x2, y2], outline=color, width=lw)

                try:
                    tb = draw.textbbox((0, 0), label, font=font)
                    tw, th = tb[2] - tb[0], tb[3] - tb[1]
                    ty = max(y1 - th - 4, 0)
                    draw.rectangle([x1, ty, x1 + tw + 6, ty + th + 4], fill=color)
                    draw.text((x1 + 3, ty + 2), label,
                              fill=_contrast_text(color), font=font)
                except Exception:
                    draw.text((x1, max(y1 - fs - 2, 0)), label,
                              fill=_contrast_text(color), font=font)

        ann_bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        return pil_img, ann_bgr

    def _annotated_combined_pil(self, results1, results2, model2):
        """Vẽ bbox từ 2 model lên cùng 1 ảnh: cyan (M1) + cam KZTEK (M2)."""
        from PIL import ImageFont, ImageDraw as _Draw

        lw = max(1, self.v_line_width.get())
        fs = max(6, self.v_font_size.get())

        orig_bgr = results1[0].orig_img
        orig_rgb = cv2.cvtColor(orig_bgr, cv2.COLOR_BGR2RGB)
        pil_img  = Image.fromarray(orig_rgb)

        try:
            font = ImageFont.truetype("arial.ttf", fs)
        except Exception:
            try:
                font = ImageFont.load_default(size=fs)
            except Exception:
                font = ImageFont.load_default()

        # Model Segment (YOLO-Seg) → overlay mask (fill + viền) theo màu panel trước khi vẽ bbox
        pil_img = self._overlay_seg_masks(pil_img, results1, lambda _c, _i: self._PANEL1_COLOR, line_width=lw)
        pil_img = self._overlay_seg_masks(pil_img, results2, lambda _c, _i: self._PANEL2_COLOR, line_width=lw)
        draw    = _Draw.Draw(pil_img)

        def _draw_boxes(boxes, names, color, prefix, masks=None):
            if boxes is None or not len(boxes):
                return
            for i, box in enumerate(boxes):
                x1, y1, x2, y2 = (int(v) for v in box.xyxy[0])
                cls_id = int(box.cls[0])
                conf   = float(box.conf[0])
                label  = f"{prefix}{names.get(cls_id, str(cls_id))} {conf:.2f}"
                # Segment: viền polygon đã vẽ ở overlay → không vẽ khung chữ nhật
                if not self._seg_has_poly(masks, i):
                    draw.rectangle([x1, y1, x2, y2], outline=color, width=lw)
                try:
                    tb = draw.textbbox((0, 0), label, font=font)
                    tw, th = tb[2]-tb[0], tb[3]-tb[1]
                    ty = max(y1-th-4, 0)
                    draw.rectangle([x1, ty, x1+tw+6, ty+th+4], fill=color)
                    draw.text((x1+3, ty+2), label,
                               fill=_contrast_text(color), font=font)
                except Exception:
                    draw.text((x1, max(y1-fs-2, 0)), label, fill=color, font=font)

        _draw_boxes(results1[0].boxes,
                    getattr(self.model, "names", {}) or {},
                    self._PANEL1_COLOR, "M1:",
                    getattr(results1[0], "masks", None))
        _draw_boxes(results2[0].boxes,
                    getattr(model2, "names", {}) or {},
                    self._PANEL2_COLOR, "M2:",
                    getattr(results2[0], "masks", None) if results2 else None)

        ann_bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        return pil_img, ann_bgr

    def _rfdetr_summary(self, dets) -> str:
        """Tóm tắt kết quả RF-DETR: 'name: count | ...'"""
        if dets is None:
            return ""
        ids = getattr(dets, "class_id", None)
        if ids is None or len(ids) == 0:
            return ""
        counts = {}
        for cid in ids:
            name = self._model3_names.get(int(cid), str(cid))
            counts[name] = counts.get(name, 0) + 1
        return "  |  ".join(f"{n}: {c}" for n, c in counts.items())

    def _draw_sv_on_pil(self, pil_img, dets, names: dict,
                        panel_color=None, prefix: str = ""):
        """Vẽ sv.Detections/_OnnxDetResult lên PIL.
        panel_color=None → palette màu theo class_id; ngược lại dùng màu cố định."""
        from PIL import ImageFont, ImageDraw as _Draw
        if dets is None or not hasattr(dets, "xyxy") or dets.xyxy is None or len(dets.xyxy) == 0:
            return pil_img
        lw = max(1, self.v_line_width.get())
        fs = max(6, self.v_font_size.get())
        pil_out = pil_img.copy()
        draw = _Draw.Draw(pil_out)
        try:
            font = ImageFont.truetype("arial.ttf", fs)
        except Exception:
            try:
                font = ImageFont.load_default(size=fs)
            except Exception:
                font = ImageFont.load_default()
        if panel_color is None:
            try:
                from ultralytics.utils.plotting import colors as _yc
                def _clr(cid):
                    c = _yc(int(cid), True)
                    return (int(c[2]), int(c[1]), int(c[0]))
            except Exception:
                _pal = [(0, 200, 255), (0, 255, 0), (255, 100, 0),
                        (255, 0, 200), (200, 200, 0)]
                def _clr(cid):
                    return _pal[int(cid) % len(_pal)]
        else:
            def _clr(_):
                return panel_color
        confs = getattr(dets, "confidence", None)
        cids  = getattr(dets, "class_id",  None)
        for i, box in enumerate(dets.xyxy):
            x1, y1, x2, y2 = (int(v) for v in box)
            cls_id = int(cids[i])  if cids  is not None else 0
            conf   = float(confs[i]) if confs is not None else 0.0
            label  = f"{prefix}{names.get(cls_id, str(cls_id))} {conf:.2f}"
            color  = _clr(cls_id)
            draw.rectangle([x1, y1, x2, y2], outline=color, width=lw)
            try:
                tb = draw.textbbox((0, 0), label, font=font)
                tw, th = tb[2] - tb[0], tb[3] - tb[1]
                ty = max(y1 - th - 4, 0)
                draw.rectangle([x1, ty, x1 + tw + 6, ty + th + 4], fill=color)
                draw.text((x1 + 3, ty + 2), label,
                           fill=_contrast_text(color), font=font)
            except Exception:
                draw.text((x1, max(y1 - fs - 2, 0)), label, fill=color, font=font)
        return pil_out

    def _draw_rfdetr_on_pil(self, pil_img, dets):
        """Vẽ RF-DETR boxes (lime green, prefix M3:) lên PIL Image, trả về PIL mới."""
        return self._draw_sv_on_pil(pil_img, dets, self._model3_names,
                                    self._PANEL3_COLOR, "M3:")

    def _draw_yolo_panel_on_pil(self, pil_img, results, names: dict,
                                  panel_color, prefix: str):
        """Vẽ YOLO results lên PIL với màu và prefix tùy chọn (dùng cho M2/M3 overlay)."""
        from PIL import ImageFont, ImageDraw as _Draw
        boxes = results[0].boxes if results else None
        if boxes is None or len(boxes) == 0:
            return pil_img
        lw = max(1, self.v_line_width.get())
        fs = max(6, self.v_font_size.get())
        masks = getattr(results[0], "masks", None) if results else None
        # Model Segment (YOLO-Seg) → overlay mask (fill + viền) theo panel_color trước khi vẽ bbox
        pil_out = self._overlay_seg_masks(pil_img.copy(), results, lambda _c, _i: panel_color, line_width=lw)
        draw    = _Draw.Draw(pil_out)
        try:
            font = ImageFont.truetype("arial.ttf", fs)
        except Exception:
            try:
                font = ImageFont.load_default(size=fs)
            except Exception:
                font = ImageFont.load_default()
        for i, box in enumerate(boxes):
            x1, y1, x2, y2 = (int(v) for v in box.xyxy[0])
            cls_id = int(box.cls[0])
            conf   = float(box.conf[0])
            label  = f"{prefix}{names.get(cls_id, str(cls_id))} {conf:.2f}"
            # Segment: viền polygon đã vẽ ở overlay → không vẽ khung chữ nhật
            if not self._seg_has_poly(masks, i):
                draw.rectangle([x1, y1, x2, y2], outline=panel_color, width=lw)
            try:
                tb = draw.textbbox((0, 0), label, font=font)
                tw, th = tb[2] - tb[0], tb[3] - tb[1]
                ty = max(y1 - th - 4, 0)
                draw.rectangle([x1, ty, x1 + tw + 6, ty + th + 4], fill=panel_color)
                draw.text((x1 + 3, ty + 2), label,
                          fill=_contrast_text(panel_color), font=font)
            except Exception:
                draw.text((x1, max(y1 - fs - 2, 0)), label, fill=panel_color, font=font)
        return pil_out

    def _draw_yolo_m3_on_pil(self, pil_img, results):
        """Vẽ YOLO results (M3, lime green, prefix M3:) lên PIL Image."""
        return self._draw_yolo_panel_on_pil(
            pil_img, results, self._model3_names, self._PANEL3_COLOR, "M3:")

    def _annotated_from_cache(self, img_path: str):
        """Vẽ annotated image từ _det_cache — nhất quán với grid thumbnail."""
        from PIL import ImageFont, ImageDraw as _Draw
        with self._det_cache_lock:
            data = self._det_cache.get(img_path)
        pil = Image.open(img_path).convert("RGB")
        try:
            from PIL import ImageOps
            pil = ImageOps.exif_transpose(pil)
        except Exception:
            pass
        if not data or data["n"] == 0:
            return pil
        conf_thresh = max(self.v_conf_thresh.get(), self.v_conf.get())
        visible_boxes = [b for b in data["boxes"]
                         if (len(b) > 7 and float(b[7]) >= conf_thresh)]
        if not visible_boxes:
            return pil
        lw = max(1, self.v_line_width.get())
        fs = max(6, self.v_font_size.get())
        iw, ih = pil.size
        draw = _Draw.Draw(pil)
        try:
            font = ImageFont.truetype("arial.ttf", fs)
        except Exception:
            try:
                font = ImageFont.load_default(size=fs)
            except Exception:
                font = ImageFont.load_default()
        try:
            from ultralytics.utils.plotting import colors as _yc
            def _color(cls_id):
                c = _yc(int(cls_id), True)
                return (int(c[2]), int(c[1]), int(c[0]))
        except Exception:
            _pal = [(0,200,255),(0,255,0),(255,100,0),(255,0,200),(200,200,0)]
            def _color(cls_id):
                return _pal[int(cls_id) % len(_pal)]
        names = {}
        if self.model:
            try:
                names = dict(self.model.names) or {}
            except Exception:
                pass
        for box_t in visible_boxes:
            cid        = int(box_t[0])
            cx_n, cy_n, w_n, h_n = box_t[1], box_t[2], box_t[3], box_t[4]
            conf_score = float(box_t[7]) if len(box_t) > 7 else 0.0
            x1 = max(0, int((cx_n - w_n / 2) * iw))
            y1 = max(0, int((cy_n - h_n / 2) * ih))
            x2 = min(iw - 1, int((cx_n + w_n / 2) * iw))
            y2 = min(ih - 1, int((cy_n + h_n / 2) * ih))
            cls_name = names.get(cid, str(cid))
            label    = f"{cls_name} {conf_score:.2f}"
            color    = _color(cid)
            draw.rectangle([x1, y1, x2, y2], outline=color, width=lw)
            try:
                tb = draw.textbbox((0, 0), label, font=font)
                tw2, th2 = tb[2] - tb[0], tb[3] - tb[1]
                ty = max(y1 - th2 - 4, 0)
                draw.rectangle([x1, ty, x1 + tw2 + 6, ty + th2 + 4], fill=color)
                draw.text((x1 + 3, ty + 2), label,
                          fill=_contrast_text(color), font=font)
            except Exception:
                draw.text((x1, max(y1 - fs - 2, 0)), label,
                          fill=_contrast_text(color), font=font)
        return pil

    def _resize_pil(self, pil_img, w, h):
        copy = pil_img.copy()
        copy.thumbnail((w - 10, h - 10), Image.Resampling.LANCZOS)
        return copy
