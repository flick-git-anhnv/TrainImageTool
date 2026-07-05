"""Gọi locate-anything-cli.exe (open-vocabulary detection) qua subprocess.

Không chứa Tkinter — chỉ business logic, để tab UI orchestrate mỏng.
"""
import json
import subprocess
from pathlib import Path

# locate-anything.cpp downscale nội bộ chỉ kích hoạt khi lưới patch vượt 25600
# token (xem third_party image_io.cpp: kInTokenLimit) — ngưỡng này quá cao cho
# RAM máy thường: self-attention tốn bộ nhớ bậc hai theo số token, ảnh chạm gần
# giới hạn (vd 1920x2560) có thể khiến ggml xin cấp phát hàng chục GB và crash.
# Resize trước ở phía client xuống cạnh dài an toàn để tránh lỗi này.
DEFAULT_MAX_LONG_SIDE = 1280


def _safe_resize(image_path, out_dir, max_long_side, on_log=None):
    """Thu nhỏ ảnh nếu cạnh dài vượt max_long_side. Trả về (path_dùng_để_detect, đã_resize)."""
    if not max_long_side or max_long_side <= 0:
        return image_path, False
    from PIL import Image
    img_p = Path(image_path)
    with Image.open(img_p) as im:
        w, h = im.size
        long_side = max(w, h)
        if long_side <= max_long_side:
            return image_path, False
        scale = max_long_side / long_side
        new_w, new_h = max(1, int(w * scale)), max(1, int(h * scale))
        resized = im.convert("RGB").resize((new_w, new_h), Image.LANCZOS)
        tmp_path = Path(out_dir) / f"_resized_{img_p.stem}.jpg"
        resized.save(tmp_path, quality=92)
    if on_log:
        on_log(f"⚠ Ảnh {w}x{h} vượt giới hạn an toàn RAM — đã resize xuống {new_w}x{new_h}")
    return str(tmp_path), True


def build_cmd(cli_exe, model_path, image_path, prompt, mode,
              annotated_path, output_json_path, threads=None):
    cmd = [cli_exe, "detect",
           "--model", model_path,
           "--input", image_path,
           "--prompt", prompt,
           "--mode", mode,
           "--annotated", annotated_path,
           "--output", output_json_path]
    if threads:
        cmd += ["--threads", str(threads)]
    return cmd


def run_one(cli_exe, model_path, image_path, prompt, *, mode="hybrid",
            out_dir=None, threads=None, max_long_side=DEFAULT_MAX_LONG_SIDE,
            on_log=None, proc_holder=None):
    """Chạy detect cho 1 ảnh. Trả về dict {detections, annotated, json_path, error}.

    proc_holder: list 1 phần tử [None] — được gán subprocess.Popen đang chạy để
    caller có thể gọi .terminate() từ thread khác nhằm dừng giữa chừng (Escape).
    """
    img_p = Path(image_path)
    out_dir_p = Path(out_dir) if out_dir else img_p.parent
    out_dir_p.mkdir(parents=True, exist_ok=True)
    json_path = out_dir_p / f"{img_p.stem}_la.json"
    annotated_path = out_dir_p / f"{img_p.stem}_la.png"

    detect_input, _ = _safe_resize(str(img_p), out_dir_p, max_long_side, on_log)

    cmd = build_cmd(cli_exe, model_path, detect_input, prompt, mode,
                     str(annotated_path), str(json_path), threads)

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, text=True,
                                 encoding="utf-8", errors="replace")
    except OSError as e:
        return {"detections": [], "annotated": None, "json_path": None,
                "error": f"Không chạy được CLI: {e}"}

    if proc_holder is not None:
        proc_holder[0] = proc
    for line in proc.stdout:
        if on_log:
            on_log(line.rstrip())
    proc.wait()
    if proc_holder is not None:
        proc_holder[0] = None

    if proc.returncode != 0:
        return {"detections": [], "annotated": None, "json_path": None,
                "error": f"CLI thoát với mã {proc.returncode} (có thể đã bị dừng)"}
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception as e:
        return {"detections": [], "annotated": None, "json_path": None,
                "error": f"Không đọc được JSON kết quả: {e}"}
    return {"detections": data.get("detections", []),
            "annotated": str(annotated_path) if annotated_path.exists() else None,
            "json_path": str(json_path), "error": None}


def list_images(folder, exts):
    p = Path(folder)
    if not p.is_dir():
        return []
    return sorted(str(f) for f in p.iterdir()
                  if f.is_file() and f.suffix.lower() in exts)
