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
    if results[0].masks is None:
        return []
    masks_xy = results[0].masks.xy
    if not masks_xy or len(masks_xy[0]) < 3:
        return []
    return [(float(p[0]), float(p[1])) for p in masks_xy[0]]
