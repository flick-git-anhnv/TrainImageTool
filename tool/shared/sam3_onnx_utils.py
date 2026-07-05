# sam3_onnx_utils.py — SAM3 (Segment Anything 3) text-prompt segmentation qua ONNX Runtime
#
# Dùng bộ ONNX export sẵn từ vietanhdev/segment-anything-3-onnx-models (Apache 2.0,
# không cần quyền HuggingFace gated) — thay cho bản PyTorch gốc facebook/sam3 (yêu cầu
# torch/CUDA mới hơn + xin quyền truy cập). Chạy được với onnxruntime + clip đã có sẵn
# trong môi trường, không cần cài thêm package nào.
#
# Kiến trúc 3 ONNX model (theo samexporter — github.com/vietanhdev/samexporter):
#   1. image encoder    — ảnh → backbone features (vision_pos_enc_*, backbone_fpn_*)
#   2. language encoder — text prompt (tokenize CLIP, context_length=32) → text embedding
#   3. decoder          — kết hợp vision + language + prompt hình học (rỗng khi thuần
#                          text) → masks (N,1,H,W) bool + scores (N,) + boxes (N,4)
from __future__ import annotations
import os
from pathlib import Path

from PIL import Image


def _create_ort_session(path: str):
    """Tạo InferenceSession — CPU-only cho tới khi có bản onnxruntime-gpu mới hơn.

    Đã thử ép CUDAExecutionProvider (kể cả tự thêm PATH tới cuDNN 9.x qua package
    pip `nvidia-cudnn-cu12`) nhưng onnxruntime-gpu 1.23.2 (bản mới nhất hiện có)
    CHƯA implement kernel CUDA cho "Squeeze" ở opset 21 (model SAM3 export dùng
    opset này) — báo lỗi "Version mismatch... kernel is not supported in
    CUDAExecutionProvider" ngay khi khởi tạo session, không liên quan gì tới DLL.
    Thử prepend PATH tới cuDNN 9.x còn làm VỠ import torch/clip (xung đột version
    cuBLAS với bản torch 2.5.1+cu121 đang cài) — rủi ro hơn lợi ích, đã bỏ.
    → Chạy CPU (đã verify đúng kết quả, chỉ chậm ~15-20s/prompt). Khi onnxruntime-gpu
    ra bản mới hỗ trợ opset 21 trên CUDA, có thể thử lại theo hướng adr này."""
    import onnxruntime as ort
    available = ort.get_available_providers()
    gpu_providers = [p for p in available
                     if p in ("CUDAExecutionProvider",) ]
    if gpu_providers:
        try:
            return ort.InferenceSession(path, providers=gpu_providers + ["CPUExecutionProvider"])
        except Exception:
            pass
    return ort.InferenceSession(path, providers=["CPUExecutionProvider"])


def find_sam3_onnx_files(model_dir: str) -> dict | None:
    """Quét `model_dir` (đệ quy) tìm 3 file .onnx theo tên khớp keyword.
    Trả về dict {"image_encoder":path, "language_encoder":path, "decoder":path}
    hoặc None nếu thiếu file nào."""
    found = {"image_encoder": None, "language_encoder": None, "decoder": None}
    for root, _dirs, files in os.walk(model_dir):
        for f in files:
            if not f.lower().endswith(".onnx"):
                continue
            low = f.lower()
            path = os.path.join(root, f)
            if "language" in low or "text" in low:
                found["language_encoder"] = path
            elif "decoder" in low:
                found["decoder"] = path
            elif "encoder" in low or "image" in low or "vision" in low:
                found["image_encoder"] = path
    if not all(found.values()):
        return None
    return found


def load_sam3_onnx(model_dir: str) -> "Sam3Onnx":
    """Load bộ 3 ONNX model SAM3 từ thư mục đã giải nén sam3_vit_h.zip."""
    files = find_sam3_onnx_files(model_dir)
    if not files:
        raise FileNotFoundError(
            f"Không tìm thấy đủ 3 file .onnx (image/language encoder + decoder) "
            f"trong {model_dir}")
    return Sam3Onnx(files["image_encoder"], files["decoder"], files["language_encoder"])


def run_sam3_text(model: "Sam3Onnx", img: Image.Image, prompts: list[str],
                  conf: float = 0.5):
    """Chạy SAM3-ONNX với text prompt(s) trên ảnh — trả về list (label, conf, polygon).

    Mỗi prompt trong `prompts` là 1 khái niệm (VD "motorcycle helmet") — SAM3 tự tìm
    và trả về TẤT CẢ instance khớp khái niệm đó trong ảnh (open-vocabulary), khác YOLOE
    ở chỗ mỗi lần encode() chỉ nhận 1 câu text (không set_classes hàng loạt)."""
    import numpy as np
    from .cv_segment import mask_array_to_polygon

    cv_img = np.array(img.convert("RGB"))[:, :, ::-1]  # RGB → BGR (giống cv2.imread)
    oh, ow = cv_img.shape[:2]
    out = []
    for prompt in prompts:
        prompt = prompt.strip()
        if not prompt:
            continue
        masks, scores = model.predict_text(cv_img, prompt, confidence_threshold=conf)
        for i in range(masks.shape[0]):
            m = masks[i, 0].astype(np.uint8) * 255  # bool (H,W) → uint8 mask
            pts = mask_array_to_polygon(m, oh, ow)
            if not pts or len(pts) < 3:
                continue
            out.append((prompt, float(scores[i]), pts))
    return out


class Sam3Onnx:
    """Wrapper 3 ONNX session (image encoder + language encoder + decoder).

    Rút gọn từ `samexporter.sam3_onnx.SegmentAnything3ONNX` — khác biệt chính: dùng
    `clip.tokenize` (package `clip` gốc OpenAI, đã có sẵn) thay vì `osam` để tokenize
    text, và `predict_text()` trả về CẢ scores đã filter (bản gốc chỉ trả masks)."""

    def __init__(self, image_encoder_path: str, decoder_path: str,
                 language_encoder_path: str):
        self._img_sess  = _create_ort_session(image_encoder_path)
        self._lang_sess = _create_ort_session(language_encoder_path)
        self._dec_sess  = _create_ort_session(decoder_path)

        enc_in = self._img_sess.get_inputs()[0]
        self._img_input_name = enc_in.name
        shape = enc_in.shape
        # Model export [3, H, W] (không batch dim) hoặc legacy [1, 3, H, W]
        self._img_h = int(shape[1]) if len(shape) == 3 else int(shape[2])
        self._img_w = int(shape[2]) if len(shape) == 3 else int(shape[3])
        self._img_dtype_is_float = ("float" in enc_in.type)

        self._dec_input_names = {i.name for i in self._dec_sess.get_inputs()}

    # ── image encoder ────────────────────────────────────────────────────
    def _prepare_image(self, cv_img_bgr):
        import cv2
        import numpy as np
        img = cv2.cvtColor(cv_img_bgr, cv2.COLOR_BGR2RGB)
        img = cv2.resize(img, (self._img_w, self._img_h), interpolation=cv2.INTER_LINEAR)
        img = img.transpose(2, 0, 1)  # (H,W,C) → (C,H,W)
        if self._img_dtype_is_float:
            tensor = ((img / 255.0) - 0.5) / 0.5
            return tensor.astype(np.float32)
        return img.astype(np.uint8)

    def _encode_image(self, cv_img_bgr):
        tensor = self._prepare_image(cv_img_bgr)
        outs = self._img_sess.run(None, {self._img_input_name: tensor})
        return {
            "vision_pos_enc_0": outs[0], "vision_pos_enc_1": outs[1],
            "vision_pos_enc_2": outs[2],
            "backbone_fpn_0": outs[3], "backbone_fpn_1": outs[4],
            "backbone_fpn_2": outs[5],
        }

    # ── language encoder ─────────────────────────────────────────────────
    def _encode_text(self, text: str):
        import numpy as np
        import clip
        tokens = clip.tokenize([text], context_length=32).numpy().astype(np.int64)
        outs = self._lang_sess.run(None, {"tokens": tokens})
        return {"language_mask": outs[0], "language_features": outs[1],
                "language_embeds": outs[2]}

    # ── decoder + postprocess ────────────────────────────────────────────
    def predict_text(self, cv_img_bgr, text_prompt: str, confidence_threshold: float = 0.5):
        """Trả về (masks, scores) đã lọc theo confidence_threshold.
        masks: bool (N,1,H,W) đúng kích thước ảnh gốc — không cần resize thêm."""
        import numpy as np
        oh, ow = cv_img_bgr.shape[:2]

        vis  = self._encode_image(cv_img_bgr)
        lang = self._encode_text(text_prompt)

        # Không có prompt hình học (điểm/box) → box giả, box_masks=True (bỏ qua trong model)
        box_coords = np.array([[[0.0, 0.0, 0.0, 0.0]]], dtype=np.float32)
        box_labels = np.array([[1]], dtype=np.int64)
        box_masks  = np.array([[True]], dtype=np.bool_)

        inputs = {
            "original_height": np.array(oh, dtype=np.int64),
            "original_width":  np.array(ow, dtype=np.int64),
            **vis, **lang,
            "box_coords": box_coords, "box_labels": box_labels, "box_masks": box_masks,
        }
        inputs = {k: v for k, v in inputs.items()
                  if k in self._dec_input_names and v is not None}
        outs = self._dec_sess.run(None, inputs)
        boxes, scores, masks = outs[0], outs[1], outs[2]  # thứ tự export ONNX

        if len(scores) == 0:
            return masks[:0], scores[:0]
        keep = np.where(scores > confidence_threshold)[0]
        if len(keep) == 0:
            return masks[:0], scores[:0]
        return masks[keep], scores[keep]
