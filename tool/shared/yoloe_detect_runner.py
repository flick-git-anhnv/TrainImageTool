"""Chạy YOLOE text-prompt detect cho 1 ảnh, trả về CÙNG shape dict với
locate_anything_runner.run_one — để tab UI dùng chung 1 code path bất kể engine.
"""
import json
from pathlib import Path

from .bbox_renderer import PALETTE, hex_to_rgb
from .yoloe_utils import run_yoloe_detect


def run_yoloe_one(model, image_path, prompts, *, conf=0.25, out_dir=None):
    from PIL import Image, ImageDraw

    img_p = Path(image_path)
    out_dir_p = Path(out_dir) if out_dir else img_p.parent
    out_dir_p.mkdir(parents=True, exist_ok=True)
    json_path = out_dir_p / f"{img_p.stem}_yoloe.json"
    annotated_path = out_dir_p / f"{img_p.stem}_yoloe.png"

    try:
        img = Image.open(img_p).convert("RGB")
    except Exception as e:
        return {"detections": [], "annotated": None, "json_path": None,
                "error": f"Không mở được ảnh: {e}"}

    try:
        raw = run_yoloe_detect(model, img, prompts, conf=conf)
    except Exception as e:
        return {"detections": [], "annotated": None, "json_path": None,
                "error": f"YOLOE lỗi: {e}"}

    draw = ImageDraw.Draw(img)
    detections = []
    for i, (label, score, box) in enumerate(raw):
        x1, y1, x2, y2 = [int(v) for v in box]
        color = hex_to_rgb(PALETTE[i % len(PALETTE)])
        draw.rectangle([x1, y1, x2, y2], outline=color, width=2)
        txt = f"{label} {score:.2f}"
        tw = 7 * len(txt) + 6
        ty = max(0, y1 - 16)
        draw.rectangle([x1, ty, x1 + tw, ty + 15], fill=color)
        draw.text((x1 + 3, ty + 1), txt, fill=(255, 255, 255))
        detections.append({"label": label, "box": [float(x1), float(y1), float(x2), float(y2)],
                            "conf": round(score, 4)})

    img.save(annotated_path)
    json_path.write_text(json.dumps({"detections": detections}, ensure_ascii=False),
                          encoding="utf-8")
    return {"detections": detections, "annotated": str(annotated_path),
            "json_path": str(json_path), "error": None}
