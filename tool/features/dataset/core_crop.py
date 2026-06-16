import json
import math
from pathlib import Path

from ...core.constants import CLASS_NAMES, IMAGE_EXTENSIONS


def _parse_label(path):
    boxes = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            p = line.strip().split()
            if len(p) >= 5:
                vals = list(map(float, p[1:5]))
                if any(math.isnan(v) or math.isinf(v) for v in vals):
                    continue
                boxes.append((int(p[0]), *vals))
    return boxes


def _yolo_px(xc, yc, w, h, iw, ih):
    x1 = max(0,  int((xc - w/2) * iw))
    y1 = max(0,  int((yc - h/2) * ih))
    x2 = min(iw, int((xc + w/2) * iw))
    y2 = min(ih, int((yc + h/2) * ih))
    return x1, y1, x2, y2


def run_crop(image_dir, label_dir, output_dir, log, progress):
    from PIL import Image
    img_dir = Path(image_dir)
    lbl_dir = Path(label_dir)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for cn in CLASS_NAMES.values():
        (out_dir / cn).mkdir(exist_ok=True)

    files = sorted(f for f in img_dir.iterdir()
                   if f.suffix.lower() in IMAGE_EXTENSIONS)
    total = len(files)
    if not total:
        log("⚠  Không tìm thấy ảnh."); return

    saved = missing = 0
    for i, fp in enumerate(files, 1):
        progress(i, total)
        lp = lbl_dir / (fp.stem + ".txt")
        if not lp.exists():
            missing += 1; continue
        boxes = _parse_label(lp)
        if not boxes: continue
        try:
            img = Image.open(fp).convert("RGB")
        except Exception as e:
            log(f"[LỖI] {fp.name}: {e}"); continue
        iw, ih = img.size
        cnt = {}
        for cid, xc, yc, w, h in boxes:
            cn = CLASS_NAMES.get(cid, f"class{cid}")
            cnt[cn] = cnt.get(cn, 0) + 1
            x1, y1, x2, y2 = _yolo_px(xc, yc, w, h, iw, ih)
            if x2 <= x1 or y2 <= y1: continue
            img.crop((x1, y1, x2, y2)).save(
                out_dir / cn / f"{fp.stem}__{cn}_{cnt[cn]:03d}.jpg",
                "JPEG", quality=95)
            saved += 1
        log(f"✔  {fp.name}  ({len(boxes)} bbox)")

    log("─" * 58)
    log(f"Tổng ảnh xử lý : {total - missing} / {total}")
    log(f"Thiếu label     : {missing}")
    log(f"Crops đã lưu    : {saved}")
    log(f"Thư mục output  : {out_dir.resolve()}")


def run_crop_by_label(cfg, log, progress, stop_event):
    from PIL import Image as _PI
    img_dir = Path(cfg["image_dir"])
    lbl_dir = Path(cfg["label_dir"])
    out_dir = Path(cfg["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    state_file = out_dir / ".crop_by_label_state.json"
    state = {"processed": [], "src": [str(img_dir), str(lbl_dir)]}
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    if state.get("src") != [str(img_dir), str(lbl_dir)]:
        state = {"processed": [], "src": [str(img_dir), str(lbl_dir)]}
    done_set = set(state.get("processed", []))

    keep_cls   = set(cfg["keep_classes"]) if cfg.get("filter_classes") else None
    padding    = max(0, int(cfg.get("padding_px", 0)))
    min_w      = max(0, int(cfg.get("min_w_px", 0)))
    min_h      = max(0, int(cfg.get("min_h_px", 0)))
    by_class   = cfg.get("split_by_class", True)
    class_map  = cfg.get("class_names_map", {})
    quality    = int(cfg.get("jpeg_quality", 95))
    recursive  = cfg.get("recursive", False)

    if recursive:
        images = sorted(f for f in img_dir.rglob("*")
                        if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS)
    else:
        images = sorted(f for f in img_dir.iterdir()
                        if f.suffix.lower() in IMAGE_EXTENSIONS)

    total = len(images)
    if not total:
        log("⚠  Không tìm thấy ảnh."); return

    def _key(fp): return str(fp.relative_to(img_dir))

    prev = sum(1 for f in images if _key(f) in done_set)
    log(f"📂  Tổng: {total}  |  Đã có: {prev}  |  Còn lại: {total - prev}")
    if recursive:
        log(f"🔍  Quét đệ quy toàn bộ subfolder")

    saved = skipped = no_label = size_skipped = 0
    class_stats = {}

    for i, fp in enumerate(images, 1):
        if stop_event.is_set():
            log("⚠  Dừng theo yêu cầu."); break
        progress(i, total)
        key = _key(fp)
        if key in done_set:
            skipped += 1; continue

        rel = fp.relative_to(img_dir)
        lp  = lbl_dir / rel.parent / (fp.stem + ".txt")
        if not lp.exists():
            no_label += 1; done_set.add(key); continue

        boxes = _parse_label(str(lp))
        if not boxes:
            done_set.add(key); continue

        try:
            img = _PI.open(fp).convert("RGB")
            iw, ih = img.size
        except Exception as e:
            log(f"[LỖI] {fp.name}: {e}"); continue

        cnt = {}
        n_crop = 0
        for cid, xc, yc, bw, bh in boxes:
            if keep_cls and cid not in keep_cls:
                continue
            cname = class_map.get(cid, f"class{cid}")
            cnt[cname] = cnt.get(cname, 0) + 1

            x1, y1, x2, y2 = _yolo_px(xc, yc, bw, bh, iw, ih)
            if padding:
                x1 = max(0, x1 - padding)
                y1 = max(0, y1 - padding)
                x2 = min(iw, x2 + padding)
                y2 = min(ih, y2 + padding)

            cw, ch = x2 - x1, y2 - y1
            if cw < max(min_w, 1) or ch < max(min_h, 1):
                size_skipped += 1
                continue

            dest = (out_dir / cname) if by_class else out_dir
            dest.mkdir(parents=True, exist_ok=True)
            prefix = rel.parent.as_posix().replace("/", "_") + "__" if recursive and rel.parent != Path(".") else ""
            out_name = f"{prefix}{fp.stem}__{cname}_{cnt[cname]:03d}.jpg"
            out_path = dest / out_name
            _col = 0
            while out_path.exists():
                _col += 1
                out_path = dest / f"{out_name[:-4]}_{_col:02d}.jpg"
            img.crop((x1, y1, x2, y2)).save(out_path, "JPEG", quality=quality)
            n_crop += 1

            if cname not in class_stats:
                class_stats[cname] = {"count": 0, "total_w": 0, "total_h": 0}
            class_stats[cname]["count"]   += 1
            class_stats[cname]["total_w"] += cw
            class_stats[cname]["total_h"] += ch

        if n_crop:
            saved += n_crop
            log(f"✔  {key}  →  {n_crop} crop(s)")
        done_set.add(key)
        if len(done_set) % 50 == 0:
            state["processed"] = list(done_set)
            state_file.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

    state["processed"] = list(done_set)
    state_file.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    log("─" * 58)
    log(f"Tổng ảnh       : {total}")
    log(f"Bỏ qua (đã có) : {skipped}")
    log(f"Thiếu label    : {no_label}")
    if size_skipped:
        log(f"Bỏ qua (nhỏ)   : {size_skipped}")
    log(f"Crops đã lưu   : {saved}")
    log(f"Thư mục output : {out_dir.resolve()}")

    return {
        "total": total,
        "skipped": skipped,
        "no_label": no_label,
        "size_skipped": size_skipped,
        "saved": saved,
        "class_stats": class_stats,
    }
