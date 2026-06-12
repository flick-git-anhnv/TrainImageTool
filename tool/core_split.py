import math
import shutil
from pathlib import Path

from .constants import IMAGE_EXTENSIONS


def run_split(source_dir, output_dir, max_per_folder, do_move, log, progress):
    src = Path(source_dir)
    files = sorted(f for f in src.rglob("*")
                   if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS)
    total = len(files)
    if not total:
        log("⚠  Không tìm thấy ảnh trong thư mục nguồn."); return

    out = Path(output_dir) if output_dir else src.parent / (src.name + "_split")
    out.mkdir(parents=True, exist_ok=True)

    n_folders = math.ceil(total / max_per_folder)
    pad = len(str(n_folders))
    log(f"Tổng ảnh        : {total}")
    log(f"Tối đa / folder : {max_per_folder}")
    log(f"Số folder tạo   : {n_folders}")
    log(f"Hành động       : {'Di chuyển' if do_move else 'Sao chép'}")
    log(f"Thư mục đầu ra  : {out.resolve()}")
    log("─" * 58)

    for i, fp in enumerate(files):
        progress(i + 1, total)
        dest_folder = out / ("part_" + str(i // max_per_folder + 1).zfill(pad))
        dest_folder.mkdir(exist_ok=True)
        dest = dest_folder / fp.name
        c = 1
        while dest.exists():
            dest = dest_folder / f"{fp.stem}_{c}{fp.suffix}"; c += 1
        (shutil.move if do_move else shutil.copy2)(str(fp), dest)
        if (i + 1) % 100 == 0 or (i + 1) == total:
            log(f"✔  Đã xử lý: {i+1}/{total}  →  {dest_folder.name}")

    log("─" * 58)
    log(f"Hoàn thành! Đã tạo {n_folders} folder trong '{out.resolve()}'")
