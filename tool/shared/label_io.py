# label_io.py — Đọc/ghi file nhãn YOLO (.txt) và sidecar attrs (.attrs.json)
# Dùng chung: tab_bbox, tab_yolo, merge tab DetectLabel
from __future__ import annotations
import json
from pathlib import Path

_ATTR_DEFAULTS = {
    "condition": "ban ngày",
    "occluded":  "không",
    "truncated": "không",
    "difficult": "không",
}


# ── YOLO normalized coords ────────────────────────────────────────────────────

def read_yolo_normalized(lbl_path) -> list:
    """Đọc .txt → list tuple normalized (cid, cx, cy, w, h) hoặc poly9."""
    boxes = []
    try:
        with open(lbl_path, encoding="utf-8") as f:
            for line in f:
                p = line.strip().split()
                if len(p) == 5:
                    boxes.append((int(p[0]),
                                  float(p[1]), float(p[2]),
                                  float(p[3]), float(p[4])))
                elif len(p) == 9:
                    boxes.append((int(p[0]),) + tuple(map(float, p[1:9])))
    except Exception:
        pass
    return boxes


def read_yolo_pixel(lbl_path, img_w: int, img_h: int) -> list:
    """Đọc .txt → list pixel [cid, x1, y1, x2, y2] hoặc poly [cid, x1,y1,...x4,y4]."""
    boxes = []
    try:
        with open(lbl_path, encoding="utf-8") as f:
            for line in f:
                p = line.strip().split()
                if len(p) == 5:
                    cid = int(p[0])
                    xc, yc, w, h = map(float, p[1:5])
                    boxes.append([cid,
                                  (xc - w / 2) * img_w, (yc - h / 2) * img_h,
                                  (xc + w / 2) * img_w, (yc + h / 2) * img_h])
                elif len(p) == 9:
                    cid = int(p[0])
                    pts = list(map(float, p[1:9]))
                    boxes.append([cid,
                                  pts[0]*img_w, pts[1]*img_h,
                                  pts[2]*img_w, pts[3]*img_h,
                                  pts[4]*img_w, pts[5]*img_h,
                                  pts[6]*img_w, pts[7]*img_h])
    except Exception:
        pass
    return boxes


def write_yolo_labels(lbl_path, bboxes_px: list, img_w: int, img_h: int):
    """Ghi list box pixel → file YOLO normalized."""
    lines = []
    for ann in bboxes_px:
        cid = int(ann[0])
        if len(ann) == 9:
            _, x1, y1, x2, y2, x3, y3, x4, y4 = ann
            pts = [x1/img_w, y1/img_h, x2/img_w, y2/img_h,
                   x3/img_w, y3/img_h, x4/img_w, y4/img_h]
            pts = [max(0.0, min(1.0, v)) for v in pts]
            lines.append(f"{cid} " + " ".join(f"{v:.6f}" for v in pts))
        else:
            _, x1, y1, x2, y2 = ann
            xc = max(0.0, min(1.0, ((x1 + x2) / 2) / img_w))
            yc = max(0.0, min(1.0, ((y1 + y2) / 2) / img_h))
            bw = max(1e-4, min(1.0, (x2 - x1) / img_w))
            bh = max(1e-4, min(1.0, (y2 - y1) / img_h))
            lines.append(f"{cid} {xc:.6f} {yc:.6f} {bw:.6f} {bh:.6f}")
    Path(lbl_path).write_text("\n".join(lines), encoding="utf-8")


def label_path_for(img_path, lbl_dir: str = "") -> Path:
    """Trả về Path file .txt tương ứng với ảnh."""
    fp = Path(img_path)
    if lbl_dir:
        return Path(lbl_dir) / (fp.stem + ".txt")
    return fp.parent / (fp.stem + ".txt")


# ── Attribute sidecar (.attrs.json) ──────────────────────────────────────────

def attrs_path_for(lbl_path) -> Path:
    return Path(lbl_path).with_suffix(".attrs.json")


def read_attrs(lbl_path, n_bboxes: int,
               defaults: dict | None = None) -> list:
    """Đọc .attrs.json; trả về list[dict] độ dài n_bboxes."""
    _def = defaults or _ATTR_DEFAULTS
    result: list = []
    ap = attrs_path_for(lbl_path)
    try:
        if ap.exists():
            data = json.loads(ap.read_text(encoding="utf-8"))
            if isinstance(data, list):
                result = [dict(_def, **d) if isinstance(d, dict) else dict(_def)
                          for d in data]
    except Exception:
        pass
    while len(result) < n_bboxes:
        result.append(dict(_def))
    return result[:n_bboxes]


def write_attrs(lbl_path, attrs: list,
                defaults: dict | None = None):
    """Ghi attrs ra .attrs.json; xóa file nếu toàn bộ là default."""
    _def = defaults or _ATTR_DEFAULTS
    ap = attrs_path_for(lbl_path)
    if not attrs or all(d == _def for d in attrs):
        try:
            ap.unlink(missing_ok=True)
        except Exception:
            pass
        return
    try:
        ap.write_text(json.dumps(attrs, ensure_ascii=False, indent=2),
                      encoding="utf-8")
    except Exception:
        pass


# ── Progress sidecar (.kztek_progress.json) ───────────────────────────────────

def load_progress(progress_file) -> set:
    """Đọc file tiến độ; trả về set tên file đã làm."""
    done: set = set()
    try:
        fp = Path(progress_file)
        if fp.exists():
            data = json.loads(fp.read_text(encoding="utf-8"))
            done = set(data.get("done", []))
    except Exception:
        pass
    return done


def save_progress(progress_file, done_set: set):
    """Ghi set tiến độ ra file."""
    try:
        Path(progress_file).write_text(
            json.dumps({"done": sorted(done_set)}, ensure_ascii=False, indent=2),
            encoding="utf-8")
    except Exception:
        pass
