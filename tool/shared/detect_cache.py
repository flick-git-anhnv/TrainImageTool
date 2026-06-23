# detect_cache.py — Thread-safe cache kết quả YOLO detect
# Dùng chung: tab_yolo, merge tab DetectLabel
# Box tuple: (cid, cx_n, cy_n, w_n, h_n, w_px, h_px, conf_score) — indices 0–7
from __future__ import annotations
import json
import os
import threading

CACHE_FILENAME = ".kztek_det_cache.json"


class DetectCache:
    """Thread-safe cache kết quả YOLO detect cho một folder ảnh.

    Mỗi entry: {"n": int, "classes": {cid: count}, "boxes": [tuple]}
    """

    def __init__(self):
        self._data: dict = {}
        self._lock = threading.Lock()

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def get(self, path: str) -> "dict | None":
        with self._lock:
            return self._data.get(path)

    def put(self, path: str, n: int, classes: dict, boxes: list):
        with self._lock:
            self._data[path] = {"n": n, "classes": classes, "boxes": boxes}

    def has(self, path: str) -> bool:
        with self._lock:
            return path in self._data

    def pop(self, path: str):
        with self._lock:
            self._data.pop(path, None)

    def clear(self):
        with self._lock:
            self._data.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)

    def __contains__(self, path: str) -> bool:
        return self.has(path)

    def snapshot(self) -> dict:
        """Trả về bản sao shallow của toàn bộ cache."""
        with self._lock:
            return dict(self._data)

    # ── Disk persistence ──────────────────────────────────────────────────────

    def save_to_disk(self, folder: str, model_path: str, conf: float, iou: float):
        """Lưu cache ra .kztek_det_cache.json trong folder."""
        if not folder or not os.path.isdir(folder):
            return
        with self._lock:
            data_copy = {
                k: {
                    "n": v["n"],
                    "classes": {str(ck): cv for ck, cv in v["classes"].items()},
                    "boxes": [list(b) for b in v["boxes"]],
                }
                for k, v in self._data.items()
            }
        payload = {
            "meta": {"model": model_path, "conf": round(conf, 4),
                     "iou": round(iou, 4), "version": 1},
            "data": data_copy,
        }
        try:
            with open(os.path.join(folder, CACHE_FILENAME), "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
        except Exception:
            pass

    def load_from_disk(self, folder: str, model_path: str, iou: float) -> bool:
        """Load cache nếu model + iou khớp. Trả về True nếu load được."""
        if not folder or not model_path:
            return False
        cache_file = os.path.join(folder, CACHE_FILENAME)
        if not os.path.isfile(cache_file):
            return False
        try:
            with open(cache_file, encoding="utf-8") as f:
                payload = json.load(f)
            meta = payload.get("meta", {})
            if meta.get("model") != model_path:
                return False
            if abs(meta.get("iou", 0.0) - iou) > 0.005:
                return False
            loaded = {}
            for img_path, v in payload.get("data", {}).items():
                if not os.path.isfile(img_path):
                    continue
                loaded[img_path] = {
                    "n": v["n"],
                    "classes": {int(ck): cv for ck, cv in v.get("classes", {}).items()},
                    "boxes": [tuple(b) for b in v.get("boxes", [])],
                }
            if not loaded:
                return False
            with self._lock:
                self._data.update(loaded)
            return True
        except Exception:
            return False

    # ── Filter files by detect result ────────────────────────────────────────

    def filter_files(
        self,
        files: list,
        *,
        cls_filter: str = "Tất cả",
        ndet_min: "float | None" = None,
        ndet_max: "float | None" = None,
        area_min: "float | None" = None,
        area_max: "float | None" = None,
        w_min: "float | None" = None,
        w_max: "float | None" = None,
        h_min: "float | None" = None,
        h_max: "float | None" = None,
        must_have: "set | None" = None,
        must_not:  "set | None" = None,
    ) -> list:
        """Lọc danh sách file theo kết quả cache. Trả về list đã lọc."""
        has_filter = (
            cls_filter not in ("Tất cả", "") or
            any(v is not None for v in (ndet_min, ndet_max,
                                        area_min, area_max,
                                        w_min, w_max, h_min, h_max)) or
            bool(must_have) or bool(must_not)
        )
        with self._lock:
            cache_snap = dict(self._data)
        if not has_filter or not cache_snap:
            return files

        dim_on = any(v is not None for v in
                     (area_min, area_max, w_min, w_max, h_min, h_max))
        result = []
        for f in files:
            data = cache_snap.get(f)
            if data is None:
                if ndet_min is not None and ndet_min > 0:
                    continue
                if cls_filter not in ("Tất cả", ""):
                    continue
                if dim_on or must_have or must_not:
                    continue
                result.append(f)
                continue

            n = data["n"]
            detected_cls = set(data["classes"].keys())

            if cls_filter == "Không detect":
                if n > 0:
                    continue
            elif cls_filter not in ("Tất cả", ""):
                try:
                    flt_cid = int(cls_filter.split("]")[0].lstrip("["))
                    if flt_cid not in data["classes"]:
                        continue
                except (ValueError, IndexError):
                    pass

            if ndet_min is not None and n < ndet_min:
                continue
            if ndet_max is not None and n > ndet_max:
                continue

            if dim_on:
                boxes = data.get("boxes", [])
                match = any(
                    (area_min is None or b[5]*b[6] >= area_min) and
                    (area_max is None or b[5]*b[6] <= area_max) and
                    (w_min is None or b[5] >= w_min) and
                    (w_max is None or b[5] <= w_max) and
                    (h_min is None or b[6] >= h_min) and
                    (h_max is None or b[6] <= h_max)
                    for b in boxes if len(b) > 6
                )
                if not match:
                    continue

            if must_have and not must_have.issubset(detected_cls):
                continue
            if must_not and must_not.intersection(detected_cls):
                continue

            result.append(f)
        return result

    # ── Utilities ─────────────────────────────────────────────────────────────

    def all_class_counts(self) -> dict:
        """Trả về {cid: total_count} tổng hợp từ toàn bộ cache."""
        with self._lock:
            snap = list(self._data.values())
        counts: dict = {}
        for data in snap:
            for cid, cnt in data.get("classes", {}).items():
                counts[int(cid)] = counts.get(int(cid), 0) + cnt
        return counts
