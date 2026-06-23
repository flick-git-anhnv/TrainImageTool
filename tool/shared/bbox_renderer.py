# bbox_renderer.py — Pure functions vẽ YOLO bbox lên PIL image
# Dùng chung: tab_yolo, tab_bbox, merge tab DetectLabel
from __future__ import annotations

PALETTE: list[str] = [
    "#F05922", "#4caf50", "#2196f3", "#9c27b0", "#ff9800",
    "#00bcd4", "#e91e63", "#8bc34a", "#ff5722", "#607d8b",
    "#ffeb3b", "#3f51b5", "#009688", "#795548", "#f44336",
]


def hex_to_rgb(hex_color: str) -> tuple:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _load_font(size: int):
    from PIL import ImageFont
    try:
        return ImageFont.truetype("arial.ttf", size)
    except Exception:
        try:
            return ImageFont.load_default(size=size)
        except Exception:
            return ImageFont.load_default()


def draw_bboxes_on_pil(
    pil_img,
    boxes: list,
    class_names: "dict | list | None" = None,
    *,
    conf_thresh: float = 0.0,
    line_width: int = 2,
    font_size: int = 11,
    palette: "list[str] | None" = None,
    single_color: "tuple | None" = None,
):
    """Vẽ bbox lên PIL image với label text; trả về bản sao mới.

    boxes: list of (cid, cx_n, cy_n, w_n, h_n[, w_px, h_px, conf])
    class_names: dict {id: name} hoặc list[str]
    single_color: tuple RGB — màu cố định cho mọi box (dùng dual-panel)
    """
    from PIL import ImageDraw
    _pal = palette or PALETTE
    pil  = pil_img.copy()
    draw = ImageDraw.Draw(pil)
    iw, ih = pil.size
    font = _load_font(font_size)

    def _name(cid: int) -> str:
        if class_names is None:
            return str(cid)
        if isinstance(class_names, dict):
            return class_names.get(cid, str(cid))
        try:
            return class_names[cid]
        except (IndexError, TypeError):
            return str(cid)

    def _color(cid: int) -> tuple:
        if single_color is not None:
            return single_color
        return hex_to_rgb(_pal[cid % len(_pal)])

    for box in boxes:
        cid = int(box[0])
        cx_n, cy_n, w_n, h_n = float(box[1]), float(box[2]), float(box[3]), float(box[4])
        conf = float(box[7]) if len(box) > 7 else (float(box[5]) if len(box) > 5 else 1.0)
        if conf < conf_thresh:
            continue
        x1 = max(0, int((cx_n - w_n / 2) * iw))
        y1 = max(0, int((cy_n - h_n / 2) * ih))
        x2 = min(iw - 1, int((cx_n + w_n / 2) * iw))
        y2 = min(ih - 1, int((cy_n + h_n / 2) * ih))
        color = _color(cid)
        draw.rectangle([x1, y1, x2, y2], outline=color, width=line_width)
        label = f"{_name(cid)} {conf:.2f}" if conf < 1.0 else _name(cid)
        try:
            tb = draw.textbbox((0, 0), label, font=font)
            tw2, th2 = tb[2] - tb[0], tb[3] - tb[1]
            ty = max(y1 - th2 - 4, 0)
            draw.rectangle([x1, ty, x1 + tw2 + 6, ty + th2 + 4], fill=color)
            draw.text((x1 + 3, ty + 2), label, fill=(255, 255, 255), font=font)
        except Exception:
            draw.text((x1, max(y1 - font_size - 2, 0)), label, fill=color, font=font)
    return pil


def draw_bboxes_thumb(
    pil_img,
    boxes: list,
    *,
    conf_thresh: float = 0.0,
    filter_cid: "int | None" = None,
    line_width: int = 2,
    palette: "list[str] | None" = None,
):
    """Vẽ bbox outline lên thumbnail (không text). Trả về bản sao PIL."""
    from PIL import ImageDraw
    _pal = palette or PALETTE
    pil  = pil_img.copy()
    draw = ImageDraw.Draw(pil)
    iw, ih = pil.size
    for box in boxes:
        cid = int(box[0])
        if filter_cid is not None and cid != filter_cid:
            continue
        conf = float(box[7]) if len(box) > 7 else (float(box[5]) if len(box) > 5 else 1.0)
        if conf < conf_thresh:
            continue
        cx_n, cy_n, w_n, h_n = float(box[1]), float(box[2]), float(box[3]), float(box[4])
        x1 = max(0, int((cx_n - w_n / 2) * iw))
        y1 = max(0, int((cy_n - h_n / 2) * ih))
        x2 = min(iw - 1, int((cx_n + w_n / 2) * iw))
        y2 = min(ih - 1, int((cy_n + h_n / 2) * ih))
        draw.rectangle([x1, y1, x2, y2],
                       outline=_pal[cid % len(_pal)], width=line_width)
    return pil


def make_padded_thumb(pil_img, tw: int, th: int, bg: str = "#1a1a2e"):
    """Resize giữ tỉ lệ, paste vào nền tw×th màu bg. Trả về PIL Image (không phải PhotoImage)."""
    from PIL import Image
    pil = pil_img.copy()
    pil.thumbnail((tw, th), Image.LANCZOS)
    out = Image.new("RGB", (tw, th), bg)
    out.paste(pil, ((tw - pil.width) // 2, (th - pil.height) // 2))
    return out


def open_image_safe(path: str):
    """Mở PIL Image + EXIF rotate; trả về None nếu lỗi."""
    try:
        from PIL import Image, ImageOps
        img = Image.open(path).convert("RGB")
        try:
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass
        return img
    except Exception:
        return None
