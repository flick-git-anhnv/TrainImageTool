# yoloe_utils.py — YOLOE text-prompt segmentation helpers (ultralytics, không cần SAM3)
from __future__ import annotations
from PIL import Image


def load_yoloe(model_path: str = "yoloe-11s-seg.pt"):
    from ultralytics import YOLOE
    return YOLOE(model_path)


def run_yoloe_detect(model, img: Image.Image, prompts: list[str], conf: float = 0.25):
    """Chạy YOLOE với text prompt(s) — CHỈ lấy bounding box (không cần mask/polygon).

    Trả về list (label, conf, [x1, y1, x2, y2]) tọa độ pixel gốc. Nhẹ hơn
    `run_yoloe_text` vì bỏ qua bước trích polygon từ mask — dùng khi chỉ cần
    detect (so sánh với locate-anything.cpp) thay vì segment."""
    model.set_classes(prompts, model.get_text_pe(prompts))
    results = model.predict(img, conf=conf, verbose=False)
    out = []
    r = results[0]
    if r.boxes is None:
        return out
    names = r.names
    for i, box in enumerate(r.boxes.xyxy):
        xyxy = box.cpu().numpy() if hasattr(box, "cpu") else box
        cls_id = int(r.boxes.cls[i])
        conf_i = float(r.boxes.conf[i])
        label = names.get(cls_id, prompts[0] if prompts else "object")
        out.append((label, conf_i, [float(v) for v in xyxy]))
    return out


def run_yoloe_text(model, img: Image.Image, prompts: list[str], conf: float = 0.25):
    """Chạy YOLOE với text prompt(s) trên ảnh — trả về list (label, conf, polygon).

    `prompts`: danh sách mô tả bằng tiếng Anh (VD ["motorcycle", "helmet"]) — YOLOE
    dùng CLIP-style text embedding nên hiểu tốt nhất với từ tiếng Anh thông dụng."""
    from .cv_segment import mask_array_to_polygon
    model.set_classes(prompts, model.get_text_pe(prompts))
    results = model.predict(img, conf=conf, verbose=False)
    out = []
    r = results[0]
    if r.masks is None or r.masks.data is None:
        return out
    oh, ow = r.masks.orig_shape
    names = r.names
    for i, mask_arr in enumerate(r.masks.data):
        m = mask_arr.cpu().numpy() if hasattr(mask_arr, "cpu") else mask_arr
        pts = mask_array_to_polygon(m, oh, ow)
        if not pts or len(pts) < 3:
            continue
        cls_id = int(r.boxes.cls[i]) if r.boxes is not None else 0
        label = names.get(cls_id, prompts[0] if prompts else "object")
        conf_i = float(r.boxes.conf[i]) if r.boxes is not None else 0.0
        out.append((label, conf_i, pts))
    return out
