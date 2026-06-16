import json
import shutil
from pathlib import Path

from ...core.constants import IMAGE_EXTENSIONS
from .core_crop import _parse_label


def _box_area(box):
    return box[3] * box[4]


def _iou_norm(b1, b2):
    x1a = b1[1] - b1[3] / 2; y1a = b1[2] - b1[4] / 2
    x2a = b1[1] + b1[3] / 2; y2a = b1[2] + b1[4] / 2
    x1b = b2[1] - b2[3] / 2; y1b = b2[2] - b2[4] / 2
    x2b = b2[1] + b2[3] / 2; y2b = b2[2] + b2[4] / 2
    inter = max(0.0, min(x2a, x2b) - max(x1a, x1b)) * max(0.0, min(y2a, y2b) - max(y1a, y1b))
    union = b1[3] * b1[4] + b2[3] * b2[4] - inter
    return inter / union if union > 0 else 0.0


def _apply_label_filters(boxes, cfg):
    if cfg.get("use_class_filter") and cfg.get("keep_classes") is not None:
        keep = set(cfg["keep_classes"])
        boxes = [b for b in boxes if b[0] in keep]
    if not boxes:
        return boxes

    if cfg.get("use_min_area"):
        thr = cfg["min_area_pct"] / 100.0
        boxes = [b for b in boxes if _box_area(b) >= thr]
    if cfg.get("use_max_area"):
        thr = cfg["max_area_pct"] / 100.0
        boxes = [b for b in boxes if _box_area(b) <= thr]
    if cfg.get("use_min_side"):
        px = cfg["min_side_px"]
        iw, ih = cfg.get("iw", 1), cfg.get("ih", 1)
        boxes = [b for b in boxes if b[3] * iw >= px and b[4] * ih >= px]
    if cfg.get("use_aspect"):
        lo, hi = cfg["aspect_min"], cfg["aspect_max"]
        boxes = [b for b in boxes if b[4] > 0 and lo <= (b[3] / b[4]) <= hi]
    if cfg.get("use_edge"):
        m = cfg["edge_margin_pct"] / 100.0
        boxes = [b for b in boxes
                 if not (b[1]-b[3]/2 < m or b[2]-b[4]/2 < m or
                         b[1]+b[3]/2 > 1-m or b[2]+b[4]/2 > 1-m)]

    if not boxes:
        return boxes

    if cfg.get("use_largest"):
        n = max(1, cfg["keep_largest_n"])
        by_cls = {}
        for b in boxes:
            by_cls.setdefault(b[0], []).append(b)
        boxes = []
        for cls_boxes in by_cls.values():
            boxes.extend(sorted(cls_boxes, key=_box_area, reverse=True)[:n])
    elif cfg.get("use_smallest"):
        n = max(1, cfg["keep_smallest_n"])
        by_cls = {}
        for b in boxes:
            by_cls.setdefault(b[0], []).append(b)
        boxes = []
        for cls_boxes in by_cls.values():
            boxes.extend(sorted(cls_boxes, key=_box_area)[:n])

    if cfg.get("use_nms") and len(boxes) > 1:
        thr = cfg["nms_iou"]
        srt = sorted(boxes, key=_box_area, reverse=True)
        kept, skip = [], set()
        for i, b in enumerate(srt):
            if i in skip:
                continue
            kept.append(b)
            for j in range(i + 1, len(srt)):
                if j not in skip and _iou_norm(b, srt[j]) > thr:
                    skip.add(j)
        boxes = kept

    return boxes


def _subfolder_name(boxes, cfg):
    mode = cfg.get("split_mode", "none")
    if mode == "none" or not boxes:
        return ""
    if mode == "size":
        max_a = max(_box_area(b) for b in boxes)
        s = cfg.get("size_s_pct", 3.0) / 100.0
        l = cfg.get("size_l_pct", 15.0) / 100.0
        return "small" if max_a < s else ("large" if max_a >= l else "medium")
    if mode == "class":
        cid = boxes[0][0]
        return cfg.get("class_names_map", {}).get(cid, f"class{cid}")
    if mode == "count":
        return "single" if len(boxes) == 1 else "multi"
    rep = max(boxes, key=_box_area)
    cx, cy, bw, bh = rep[1], rep[2], rep[3], rep[4]
    if mode == "position":
        m = cfg.get("pos_border_pct", 25.0) / 100.0
        near = cx < m or cx > 1 - m or cy < m or cy > 1 - m
        return "border" if near else "center"
    if mode == "region":
        col = "left" if cx < 1/3 else ("right" if cx > 2/3 else "center")
        row = "top"  if cy < 1/3 else ("bottom" if cy > 2/3 else "middle")
        if row == "middle" and col == "center":
            return "center"
        return f"{row}_{col}" if col != "center" else row
    if mode == "orientation":
        thr = cfg.get("orient_thr", 1.3)
        ratio = bw / bh if bh > 0 else 1.0
        if ratio > thr:
            return "landscape"
        if ratio < 1.0 / thr:
            return "portrait"
        return "square"
    return ""


def run_label_norm(cfg, log, progress, stop_event):
    img_dir   = Path(cfg["image_dir"])
    lbl_dir   = Path(cfg["label_dir"])
    out_dir   = Path(cfg["output_dir"])
    recursive = cfg.get("recursive", False)
    out_dir.mkdir(parents=True, exist_ok=True)
    state_file = out_dir / ".label_norm_state.json"

    state = {"processed": [], "source_dirs": [str(img_dir), str(lbl_dir)]}
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    if state.get("source_dirs") != [str(img_dir), str(lbl_dir)]:
        state = {"processed": [], "source_dirs": [str(img_dir), str(lbl_dir)]}
    processed_set = set(state.get("processed", []))

    if recursive:
        all_imgs = sorted(f for f in img_dir.rglob("*")
                          if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS)
    else:
        all_imgs = sorted(f for f in img_dir.iterdir()
                          if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS)
    total = len(all_imgs)
    if not total:
        log("⚠  Không tìm thấy ảnh trong thư mục."); return

    def _key(fp):
        return str(fp.relative_to(img_dir)) if recursive else fp.name

    prev_done = sum(1 for f in all_imgs if _key(f) in processed_set)
    log(f"📂  Tổng: {total}  |  Đã xử lý trước: {prev_done}  |  Còn lại: {total - prev_done}")
    if recursive:
        log("🔍  Quét đệ quy toàn bộ subfolder")

    saved = skipped = no_label = removed_all = 0
    need_dims = cfg.get("use_min_side", False)

    for i, fp in enumerate(all_imgs, 1):
        if stop_event.is_set():
            log("⚠  Dừng theo yêu cầu."); break
        progress(i, total)
        key = _key(fp)
        if key in processed_set:
            skipped += 1; continue

        rel = fp.relative_to(img_dir)
        lp  = lbl_dir / rel.parent / (fp.stem + ".txt")
        if not lp.exists():
            no_label += 1
            processed_set.add(key)
            continue

        try:
            boxes = _parse_label(str(lp))
        except Exception as e:
            log(f"[LỖI] đọc label {fp.name}: {e}"); continue

        cfg["iw"], cfg["ih"] = 1, 1
        if need_dims:
            try:
                from PIL import Image as _PI
                with _PI.open(fp) as im:
                    cfg["iw"], cfg["ih"] = im.size
            except Exception:
                pass

        filtered = _apply_label_filters(list(boxes), cfg)

        if not filtered:
            removed_all += 1
            processed_set.add(key)
            if len(processed_set) % 50 == 0:
                state["processed"] = list(processed_set)
                state_file.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
            continue

        sub = _subfolder_name(filtered, cfg)
        if recursive and rel.parent != Path("."):
            dest = (out_dir / sub / rel.parent) if sub else (out_dir / rel.parent)
        else:
            dest = out_dir / sub if sub else out_dir
        dest.mkdir(parents=True, exist_ok=True)

        try:
            shutil.copy2(fp, dest / fp.name)
        except Exception as e:
            log(f"[LỖI] copy ảnh {fp.name}: {e}"); continue

        lines = [f"{b[0]} {b[1]:.6f} {b[2]:.6f} {b[3]:.6f} {b[4]:.6f}" for b in filtered]
        (dest / (fp.stem + ".txt")).write_text("\n".join(lines), encoding="utf-8")

        saved += 1
        processed_set.add(key)
        if len(processed_set) % 50 == 0:
            state["processed"] = list(processed_set)
            state_file.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

    state["processed"] = list(processed_set)
    state_file.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

    log("─" * 58)
    log(f"Tổng ảnh         : {total}")
    log(f"Bỏ qua (đã có)   : {skipped}")
    log(f"Thiếu label      : {no_label}")
    log(f"Bị lọc hết box   : {removed_all}")
    log(f"Đã lưu output    : {saved}")
    log(f"Thư mục output   : {out_dir.resolve()}")
