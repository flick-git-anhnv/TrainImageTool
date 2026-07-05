# cv_segment.py — Pure OpenCV click/drag-to-polygon segmentation (no model)
from __future__ import annotations
from PIL import Image


def compute_edge_mask(img: Image.Image, blur_ksize: int = 5,
                       canny_low: int = 50, canny_high: int = 150):
    """Bản đồ biên nhị phân (255=biên) từ GaussianBlur (thông thấp, khử nhiễu)
    + Canny (thông cao, tìm biên) + dilate nhẹ để nối biên đứt."""
    import cv2
    import numpy as np
    k = max(1, blur_ksize | 1)  # ép về số lẻ (yêu cầu của GaussianBlur)
    gray = np.array(img.convert("L"))
    blurred = cv2.GaussianBlur(gray, (k, k), 0)
    edges = cv2.Canny(blurred, canny_low, canny_high)
    return cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)


def empty_mask_like(edge_mask):
    return edge_mask * 0


def _bridge_fragments(mask_u8, min_area_ratio: float = 0.15, max_kernel: int = 81):
    """Nếu mask có ≥2 mảnh RỜI đáng kể (vật cản — cột điện, xe khác… — chia object
    thành nhiều blob, VD bánh xe tách khỏi thân xe), dùng morphological CLOSE tăng
    dần kernel để BẮC CẦU nối chúng thành 1 vùng liên thông trước khi lấy contour.

    Vì sao không dùng cách khác:
    - Lấy mảnh lớn nhất, bỏ mảnh còn lại → MẤT phần object thật (bánh xe biến mất).
    - `convexHull` gộp toàn bộ điểm → hình bao LỒI, cắt thẳng xuyên qua vùng vật cản
      ở giữa lẫn phần nền xung quanh 2 mảnh → sai hình dạng object.
    - Bắc cầu bằng closing: object "phình" ra vừa đủ để 2 mảnh chạm nhau rồi rút lại
      đúng bằng kernel đó — hình dạng cuối bám sát viền thật, chỉ "vá" đúng phần bị
      vật cản che ở giữa, không nuốt thêm vùng nền không liên quan.

    Trả về mask đã nối nếu bắc cầu thành công (chỉ còn 1 mảnh đáng kể); trả về mask
    GỐC nếu chỉ có 1 mảnh từ đầu, hoặc nếu khoảng cách quá xa (vượt `max_kernel`)
    không bắc cầu được — nơi gọi sẽ lấy mảnh lớn nhất trong mask gốc (an toàn, không
    lỗi), thay vì phình kernel vô hạn tới khi nối được 2 vật không liên quan."""
    import cv2
    import numpy as np
    contours, _ = cv2.findContours(mask_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if len(contours) <= 1:
        return mask_u8
    areas = [cv2.contourArea(c) for c in contours]
    max_area = max(areas) if areas else 0
    if max_area < 1 or sum(1 for a in areas if a >= min_area_ratio * max_area) <= 1:
        return mask_u8
    for k in (9, 17, 31, 51, 81):
        if k > max_kernel:
            break
        closed = cv2.morphologyEx(mask_u8, cv2.MORPH_CLOSE, np.ones((k, k), np.uint8))
        c2, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        a2 = [cv2.contourArea(c) for c in c2]
        if a2 and sum(1 for a in a2 if a >= min_area_ratio * max(a2)) <= 1:
            return closed   # bắc cầu thành công — chỉ còn 1 mảnh đáng kể
    return mask_u8   # không bắc cầu được trong giới hạn — giữ mask gốc


def mask_array_to_polygon(mask_arr, orig_h: int, orig_w: int) -> list[tuple] | None:
    """Trích polygon SẠCH từ 1 mask pixel thô (ultralytics `masks.data[i]`, giá trị
    0..1 hoặc 0/255) — resize về đúng kích thước ảnh gốc, BẮC CẦU nối các mảnh rời
    đáng kể do vật cản (`_bridge_fragments`) rồi `findContours(RETR_EXTERNAL)` lấy
    contour lớn nhất. Tự động bỏ lỗ bên trong + mảnh nhiễu nhỏ, dùng chung cho SAM
    (sam_utils._extract), YOLOE (yoloe_utils) và SAM3 (sam3_onnx_utils)."""
    import cv2
    import numpy as np
    m = np.asarray(mask_arr)
    if m.dtype != np.uint8 or m.max() <= 1:
        m = (m > 0.5).astype(np.uint8) * 255
    if m.shape != (orig_h, orig_w):
        m = cv2.resize(m, (orig_w, orig_h), interpolation=cv2.INTER_NEAREST)
    m = _bridge_fragments(m)
    contours, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    c = max(contours, key=cv2.contourArea)
    if cv2.contourArea(c) < 1:
        return None
    return [(float(p[0][0]), float(p[0][1])) for p in c]


def polygon_to_mask(pts: list[tuple], img_w: int, img_h: int):
    """Rasterize 1 polygon ĐÃ CÓ (đơn giản, không tự cắt chéo) thành mask đặc —
    dùng để 'seed' phiên CV Edge từ 1 segment có sẵn, cho phép MỞ RỘNG THÊM phần
    còn thiếu (VD: SAM Box bắt được thân xe nhưng bỏ sót bánh xe do khác màu/lẫn
    bóng) thay vì phải vẽ lại từ đầu."""
    import cv2
    import numpy as np
    mask = np.zeros((img_h, img_w), np.uint8)
    if len(pts) < 3:
        return mask
    arr = np.array([[(int(round(x)), int(round(y))) for x, y in pts]], dtype=np.int32)
    cv2.fillPoly(mask, arr, 255)
    return mask


def flood_region_mask(edge_mask, x: float, y: float):
    """Vùng liên thông bị bao kín bởi biên (edge_mask) và chứa điểm (x,y).
    None nếu điểm nằm ngay trên biên hoặc ngoài ảnh."""
    import cv2
    import numpy as np
    h, w = edge_mask.shape
    xi, yi = int(round(x)), int(round(y))
    if not (0 <= xi < w and 0 <= yi < h) or edge_mask[yi, xi] != 0:
        return None
    free = np.where(edge_mask == 0, 255, 0).astype(np.uint8)
    ff_mask = np.zeros((h + 2, w + 2), np.uint8)
    cv2.floodFill(free, ff_mask, (xi, yi), 128)
    return np.where(free == 128, 255, 0).astype(np.uint8)


def mask_to_polygon(mask, close_ksize: int = 15) -> list[tuple] | None:
    """Contour của mask → 1 polygon duy nhất.

    `close_ksize` nối các đảo liền kề (do biên nội bộ chia object thành nhiều mảnh
    khi kéo chuột qua từng phần, hoặc do vật cản — cột điện, xe khác… — chia object
    thành nhiều blob thật, VD bánh xe tách khỏi thân xe) trước khi lấy contour.
    Nếu sau khi CLOSE vẫn còn nhiều mảnh đáng kể, thử `_bridge_fragments` (tăng dần
    kernel để bắc cầu, hình dạng tự nhiên hơn); chỉ khi vẫn không nối được (khoảng
    cách quá xa, VD click ở 2 vị trí cách xa nhau) mới gộp bằng convex hull — LUÔN
    trả về đúng 1 polygon."""
    import cv2
    import numpy as np
    if close_ksize > 1:
        kernel = np.ones((close_ksize, close_ksize), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = _bridge_fragments(mask)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    c = contours[0] if len(contours) == 1 else cv2.convexHull(np.vstack(contours))
    if cv2.contourArea(c) < 1:
        return None
    return [(float(px), float(py)) for px, py in c.reshape(-1, 2)]


def clean_polygon(pts: list[tuple], img_w: int = None, img_h: int = None) -> list[tuple] | None:
    """Dọn polygon bị 'seam' — vệt kẻ lạ cắt ngang / khoét lởm chởm do mask gốc
    (SAM cũ, trước khi sam_utils._extract lấy trực tiếp từ mask pixel) có mảnh RỜI
    hoặc LỖ bên trong bị nối bằng đường thẳng xuyên ảnh.

    Dùng convex hull của toàn bộ điểm thay vì rasterize+fillPoly — fillPoly xử lý
    KHÔNG đáng tin cậy với polygon tự cắt chéo (lỗ thật vẫn bị giữ lại thay vì lấp
    đặc, đã kiểm chứng). Convex hull luôn cho polygon lồi liền mạch, không tự cắt
    chéo, loại bỏ hoàn toàn phần lõm do lỗi — đánh đổi 1 phần chi tiết lõm thật của
    object để đổi lấy đảm bảo hết lỗi. Nếu cần chi tiết lõm chính xác, tốt hơn nên
    Auto-tách lại segment đó (đã fix tận gốc) thay vì dọn polygon cũ."""
    import cv2
    import numpy as np
    if len(pts) < 3:
        return pts
    arr = np.array([[int(round(x)), int(round(y))] for x, y in pts], dtype=np.int32)
    hull = cv2.convexHull(arr)
    result = [(float(p[0][0]), float(p[0][1])) for p in hull]
    return result if len(result) >= 3 else pts


def run_cv_edge_segment(img: Image.Image, click_x: float, click_y: float, *,
                         blur_ksize: int = 5, canny_low: int = 50, canny_high: int = 150,
                         min_area: int = 80) -> list[tuple] | None:
    """1 click → polygon vùng bị bao kín bởi biên (Gaussian Blur + Canny + flood fill)."""
    edges = compute_edge_mask(img, blur_ksize, canny_low, canny_high)
    mask = flood_region_mask(edges, click_x, click_y)
    if mask is None or int(mask.sum() // 255) < min_area:
        return None
    return mask_to_polygon(mask)


def run_grabcut_box(img: Image.Image, x1: float, y1: float, x2: float, y2: float,
                     iterations: int = 8, pad_ratio: float = 0.25):
    """Kéo khung quanh object → GrabCut TỰ ĐỘNG tách foreground/background, không
    cần chỉnh Blur/Canny/Min area. Xử lý trên vùng crop quanh khung (thêm đệm
    `pad_ratio` để GrabCut có ngữ cảnh nền) thay vì cả ảnh gốc → nhanh hơn nhiều.

    Khởi tạo bằng GC_INIT_WITH_MASK thay vì rect thô: viền sát mép khung được
    coi là "có thể nền" (GC_PR_BGD) thay vì "có thể foreground" — vì bbox hình
    chữ nhật quanh 1 object bất kỳ luôn có phần góc/viền là nền, mẹo này giúp
    GrabCut tách sát object hơn nhiều so với coi cả khung là foreground.

    Trả về mask nhị phân (255=foreground) cùng kích thước ảnh gốc, hoặc None nếu
    khung quá nhỏ, khung chiếm gần hết ảnh (không đủ nền để học), GrabCut lỗi,
    hoặc không tách được gì (coi như thất bại — nên thử lại với khung khác/nhỏ
    hơn hoặc dùng SAM Box)."""
    import cv2
    import numpy as np

    iw, ih = img.size
    x1, x2 = sorted((float(x1), float(x2)))
    y1, y2 = sorted((float(y1), float(y2)))
    bw, bh = x2 - x1, y2 - y1
    if bw < 4 or bh < 4:
        return None
    if bw * bh > 0.85 * iw * ih:
        return None   # khung gần trùm hết ảnh → không còn nền để GrabCut học

    px, py = bw * pad_ratio, bh * pad_ratio
    cx1, cy1 = int(max(0, x1 - px)), int(max(0, y1 - py))
    cx2, cy2 = int(min(iw, x2 + px)), int(min(ih, y2 + py))
    crop = img.crop((cx1, cy1, cx2, cy2)).convert("RGB")
    arr = np.array(crop)[:, :, ::-1].copy()  # RGB → BGR cho OpenCV
    ch, cw = arr.shape[:2]

    rx1, ry1 = max(0, int(x1 - cx1)), max(0, int(y1 - cy1))
    rx2, ry2 = min(cw - 1, int(x2 - cx1)), min(ch - 1, int(y2 - cy1))
    if rx2 - rx1 < 4 or ry2 - ry1 < 4:
        return None

    rect_area = (rx2 - rx1) * (ry2 - ry1)
    bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)

    m = np.full((ch, cw), cv2.GC_BGD, np.uint8)
    m[ry1:ry2, rx1:rx2] = cv2.GC_PR_BGD
    ring = max(2, int(0.12 * min(rx2 - rx1, ry2 - ry1)))
    ix1, iy1, ix2, iy2 = rx1 + ring, ry1 + ring, rx2 - ring, ry2 - ring
    if ix2 > ix1 and iy2 > iy1:
        m[iy1:iy2, ix1:ix2] = cv2.GC_PR_FGD
    try:
        cv2.grabCut(arr, m, None, bgd, fgd, iterations, cv2.GC_INIT_WITH_MASK)
        fg = np.where((m == cv2.GC_FGD) | (m == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
        fg_area = int(fg.sum() // 255)
    except cv2.error:
        fg_area = 0

    if fg_area < 20 or fg_area > 0.93 * rect_area:
        # "Ring = có thể nền" thất bại — đúng khi object hình chữ nhật khớp SÁT khung
        # (biển số, bảng hiệu...) nên viền khung cũng là màu object, không phải nền,
        # khiến GrabCut hiểu nhầm cả khung là nền. Fallback: coi cả khung là "có thể
        # foreground" (không giả định viền là nền) — cách GrabCut kinh điển.
        m2 = np.zeros((ch, cw), np.uint8)
        bgd2, fgd2 = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
        try:
            cv2.grabCut(arr, m2, (rx1, ry1, rx2 - rx1, ry2 - ry1), bgd2, fgd2,
                        iterations, cv2.GC_INIT_WITH_RECT)
            fg2 = np.where((m2 == cv2.GC_FGD) | (m2 == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
            fg2_area = int(fg2.sum() // 255)
        except cv2.error:
            fg2_area = 0
        if fg2_area < 20:
            return None   # cả 2 cách đều thất bại — nền quá giống object hoặc lỗi khác
        fg = fg2

    full = np.zeros((ih, iw), np.uint8)
    full[cy1:cy1 + ch, cx1:cx1 + cw] = fg
    return full
