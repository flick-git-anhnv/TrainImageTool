# sam_utils.py — SAM inference helpers (point prompt + box prompt + simplify)
from __future__ import annotations
from PIL import Image


def run_sam_points(model, img: Image.Image, pts_labels: list) -> list[tuple]:
    """pts_labels: [(x, y, label), ...] — label 1=positive, 0=negative."""
    pts   = [[x, y] for x, y, _ in pts_labels]
    lbls  = [l       for _, _, l in pts_labels]
    results = model(img, points=[pts], labels=[lbls], verbose=False)
    return _extract(results)


def run_sam_box(model, img: Image.Image, x1, y1, x2, y2) -> list[tuple]:
    results = model(img, bboxes=[[x1, y1, x2, y2]], verbose=False)
    return _extract(results)


def simplify(pts: list[tuple], epsilon_pct: float) -> list[tuple]:
    """Douglas-Peucker simplification. epsilon_pct = % of perimeter."""
    if not pts or epsilon_pct <= 0:
        return pts
    try:
        import cv2
        import numpy as np
        arr = np.array(pts, dtype=np.float32).reshape(-1, 1, 2)
        eps = (epsilon_pct / 100.0) * cv2.arcLength(arr, True)
        approx = cv2.approxPolyDP(arr, max(0.5, eps), True)
        result = [(float(p[0][0]), float(p[0][1])) for p in approx]
        return result if len(result) >= 3 else pts
    except ImportError:
        step = max(1, len(pts) // 50)
        return pts[::step]


def _extract(results) -> list[tuple]:
    """Lấy polygon từ mask SAM.

    KHÔNG dùng `masks.xy` (ultralytics `strategy="all"`) — khi mask có nhiều mảnh
    RỜI hoặc có LỖ bên trong (VD: gương xe máy tách biệt do nền tối, hoặc biển số
    sáng bị coi khác object nên tạo lỗ), nó nối/vòng qua bằng đường thẳng xuyên ảnh
    để gộp thành 1 polygon duy nhất → hiện vệt kẻ lạ cắt ngang hoặc khoét lởm chởm
    quanh object. Rasterize lại polygon đã lỗi (fillPoly) KHÔNG sửa được lỗ thật
    (fillPoly giữ nguyên phần lõm như 1 lỗ, không lấp đặc).

    Thay vào đó: lấy MASK PIXEL GỐC (`masks.data`) rồi dùng chung
    `cv_segment.mask_array_to_polygon` (findContours RETR_EXTERNAL, contour lớn
    nhất) — luôn cho 1 polygon liền mạch, tự động bỏ lỗ bên trong VÀ mảnh nhỏ rời
    rạc, không cần vá lại. Hàm này dùng chung với YOLOE (yoloe_utils)."""
    masks = results[0].masks
    if masks is None:
        return []
    try:
        from .cv_segment import mask_array_to_polygon
        data = masks.data
        if data is None or len(data) == 0:
            return []
        m = data[0]
        m = m.cpu().numpy() if hasattr(m, "cpu") else m
        oh, ow = masks.orig_shape
        pts = mask_array_to_polygon(m, oh, ow)
        if pts:
            return pts
    except Exception:
        pass
    # Fallback nếu cấu trúc masks khác dự kiến (đổi phiên bản ultralytics...)
    masks_xy = masks.xy
    if not masks_xy or len(masks_xy[0]) < 3:
        return []
    return [(float(p[0]), float(p[1])) for p in masks_xy[0]]
