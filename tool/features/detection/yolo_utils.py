# yolo_utils.py — Tiện ích nhỏ dùng chung giữa nhiều mixin của YoloTab
import os


def _path_review_state(path: str) -> str:
    """Trả về 'correct'/'incorrect'/'' dựa trên tên folder chứa ảnh."""
    parent = os.path.basename(os.path.dirname(path))
    if parent == "true":  return "correct"
    if parent == "false": return "incorrect"
    return ""


def _iou_xywhn(cx1, cy1, w1, h1, cx2, cy2, w2, h2):
    x1_min = cx1 - w1 / 2; x1_max = cx1 + w1 / 2
    y1_min = cy1 - h1 / 2; y1_max = cy1 + h1 / 2
    x2_min = cx2 - w2 / 2; x2_max = cx2 + w2 / 2
    y2_min = cy2 - h2 / 2; y2_max = cy2 + h2 / 2
    inter_x = max(0.0, min(x1_max, x2_max) - max(x1_min, x2_min))
    inter_y = max(0.0, min(y1_max, y2_max) - max(y1_min, y2_min))
    inter = inter_x * inter_y
    union = w1 * h1 + w2 * h2 - inter
    return inter / union if union > 0 else 0.0
