# yolo_onnx.py — Helper thuần (không phụ thuộc self): ONNX runner + hằng số dùng chung

class _OnnxDetResult:
    """Container kết quả inference, interface giống sv.Detections."""
    def __init__(self, xyxy, confidence, class_id):
        import numpy as np
        self.xyxy       = (np.array(xyxy, dtype=np.float32)
                           if len(xyxy) else np.empty((0, 4), dtype=np.float32))
        self.confidence = np.array(confidence, dtype=np.float32)
        self.class_id   = np.array(class_id,   dtype=np.int32)

    def __len__(self):
        return len(self.xyxy)


class _OnnxRunner:
    """Chạy ONNX detection model bằng onnxruntime — tự đọc tên input từ model."""

    _MEAN = [0.485, 0.456, 0.406]
    _STD  = [0.229, 0.224, 0.225]

    def __init__(self, path: str):
        import onnxruntime as ort
        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        self.session = ort.InferenceSession(path, providers=providers)
        inp = self.session.get_inputs()[0]
        self.input_name  = inp.name
        shape = inp.shape
        self.input_h = int(shape[2]) if isinstance(shape[2], int) and shape[2] > 0 else 640
        self.input_w = int(shape[3]) if isinstance(shape[3], int) and shape[3] > 0 else 640
        self.output_names = [o.name for o in self.session.get_outputs()]
        self.names = {}
        # In thông tin model ra console để debug nếu cần
        print(f"[OnnxRunner] input : {self.input_name} {inp.shape}")
        for o in self.session.get_outputs():
            print(f"[OnnxRunner] output: {o.name} {o.shape}")

    def predict(self, img_src, threshold: float = 0.25) -> "_OnnxDetResult":
        import numpy as np
        from PIL import Image, ImageOps
        if isinstance(img_src, str):
            pil = Image.open(img_src).convert("RGB")
            try:
                pil = ImageOps.exif_transpose(pil)
            except Exception:
                pass
        else:
            pil = img_src.convert("RGB")
        orig_w, orig_h = pil.size
        pil_r = pil.resize((self.input_w, self.input_h))
        arr   = np.array(pil_r, dtype=np.float32) / 255.0
        arr   = (arr - np.array(self._MEAN, dtype=np.float32)) / np.array(self._STD, dtype=np.float32)
        arr   = arr.transpose(2, 0, 1)[np.newaxis]          # [1, 3, H, W]
        outs  = self.session.run(self.output_names, {self.input_name: arr})
        return self._parse(outs, orig_w, orig_h, threshold)

    def _parse(self, outs, orig_w, orig_h, threshold) -> "_OnnxDetResult":
        """Hỗ trợ các định dạng output phổ biến của DETR/YOLO ONNX.

        Thứ tự thử (từ đặc thù đến tổng quát):
          A. RF-DETR sigmoid — 2 outs: logits[1,N,C] + boxes[1,N,4] cxcywh norm
          B. Post-processed   — 3 outs: boxes(N,4), scores(N), labels(N)
          C. YOLO [1,N,6+]    — x1y1x2y2 conf cls (pixel hoặc norm)
          D. Classic DETR softmax — fallback với class "no-object" cuối
        """
        import numpy as np

        def _sigmoid(x):
            return 1.0 / (1.0 + np.exp(-np.clip(x, -88, 88)))

        def _cxcywh_to_xyxy(bx, w, h):
            x1 = (bx[:, 0] - bx[:, 2] / 2) * w
            y1 = (bx[:, 1] - bx[:, 3] / 2) * h
            x2 = (bx[:, 0] + bx[:, 2] / 2) * w
            y2 = (bx[:, 1] + bx[:, 3] / 2) * h
            return np.clip(np.stack([x1, y1, x2, y2], axis=1), 0, None)

        def _scale_xyxy(bx):
            if bx.size and bx.max() <= 1.5:   # normalised
                return bx * [orig_w, orig_h, orig_w, orig_h]
            return bx

        # ── A. RF-DETR sigmoid (2 outputs: pred_logits + pred_boxes) ──────
        if len(outs) >= 2:
            try:
                a0 = np.array(outs[0])
                a1 = np.array(outs[1])
                # Xác định output nào là logits (ndim=3, C > 4) và boxes (ndim=3, C==4)
                for la, ba in [(a0, a1), (a1, a0)]:
                    if la.ndim == 3 and ba.ndim == 3 and ba.shape[-1] == 4:
                        logits = la.squeeze(0)    # [N, num_classes]
                        boxes  = ba.squeeze(0)    # [N, 4]
                        probs  = _sigmoid(logits)
                        scores = probs.max(axis=1)
                        labels = probs.argmax(axis=1)
                        mask   = scores >= threshold
                        if mask.any():
                            return _OnnxDetResult(
                                _cxcywh_to_xyxy(boxes[mask], orig_w, orig_h),
                                scores[mask], labels[mask])
                        # Trả về rỗng (model chạy OK, chỉ không vượt ngưỡng)
                        return _OnnxDetResult([], [], [])
            except Exception:
                pass

        # ── B. Post-processed: [boxes(N,4), scores(N), labels(N)] ─────────
        if len(outs) >= 3:
            for ai, bi, ci in [(0, 1, 2), (1, 0, 2), (0, 2, 1)]:
                try:
                    boxes  = np.array(outs[ai]).reshape(-1, 4)
                    scores = np.array(outs[bi]).flatten()
                    labels = np.array(outs[ci]).flatten().astype(int)
                    if len(boxes) == len(scores) == len(labels) > 0:
                        mask = scores >= threshold
                        return _OnnxDetResult(_scale_xyxy(boxes[mask]),
                                              scores[mask], labels[mask])
                except Exception:
                    continue

        # ── C. YOLO [1, N, 6+] — x1y1x2y2 conf cls ───────────────────────
        if len(outs) >= 1:
            try:
                out = np.array(outs[0])
                if out.ndim == 3:
                    out = out[0]
                if out.ndim == 2 and out.shape[1] >= 6:
                    mask = out[:, 4] >= threshold
                    out  = out[mask]
                    return _OnnxDetResult(_scale_xyxy(out[:, :4]),
                                          out[:, 4], out[:, 5].astype(int))
            except Exception:
                pass

        # ── D. Classic DETR softmax với background class cuối (fallback) ──
        if len(outs) >= 2:
            try:
                a0 = np.array(outs[0]).squeeze(0)
                a1 = np.array(outs[1]).squeeze(0)
                for logits, boxes in [(a0, a1), (a1, a0)]:
                    if logits.ndim == 2 and boxes.ndim == 2 and boxes.shape[1] == 4:
                        e = np.exp(logits - logits.max(axis=1, keepdims=True))
                        probs  = e / e.sum(axis=1, keepdims=True)
                        probs  = probs[:, :-1]   # bỏ no-object
                        scores = probs.max(axis=1)
                        labels = probs.argmax(axis=1)
                        mask   = scores >= threshold
                        return _OnnxDetResult(
                            _cxcywh_to_xyxy(boxes[mask], orig_w, orig_h),
                            scores[mask], labels[mask])
            except Exception:
                pass

        return _OnnxDetResult([], [], [])


_THUMB_PALETTE = [
    "#F05922", "#4caf50", "#2196f3", "#9c27b0", "#ff9800",
    "#00bcd4", "#e91e63", "#8bc34a", "#ff5722", "#607d8b",
]


def _contrast_text(bg_rgb: tuple) -> tuple:
    """Trả về (0,0,0) hoặc (255,255,255) tuỳ độ sáng của màu nền."""
    r, g, b = bg_rgb
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    return (0, 0, 0) if lum > 150 else (255, 255, 255)


_REVIEW_ICON = {"correct": "✓", "incorrect": "✗", "": "○"}
