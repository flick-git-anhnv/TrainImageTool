import shutil
from pathlib import Path

from .constants import IMAGE_EXTENSIONS


def build_rename_plan(parent_dir, out_dir, per_folder, padding,
                      start_num, keep_ext, forced_ext, recursive=False):
    """Returns list of (src_Path, dst_Path).
    out_dir=None → in-place rename; otherwise files go to out_dir.
    """
    parent = Path(parent_dir)
    out    = Path(out_dir) if out_dir else None

    if recursive:
        folder_imgs: dict = {}
        for f in sorted(parent.rglob("*")):
            if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS:
                folder_imgs.setdefault(f.parent, []).append(f)
        subfolders = sorted(folder_imgs.keys())
    else:
        subfolders = sorted(d for d in parent.iterdir() if d.is_dir())
        root_imgs  = sorted(f for f in parent.iterdir()
                            if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS)
        if root_imgs:
            subfolders = [parent] + subfolders
        folder_imgs = {}
        for folder in subfolders:
            src = root_imgs if folder == parent else sorted(
                f for f in folder.iterdir()
                if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS)
            folder_imgs[folder] = src

    plan = []
    if per_folder:
        for folder in subfolders:
            imgs = folder_imgs.get(folder, [])
            if not imgs:
                continue
            if out is not None:
                rel = folder.relative_to(parent) if folder != parent else Path(".")
                dst_folder = out / rel
            else:
                dst_folder = folder
            for idx, img in enumerate(imgs, start_num):
                ext = img.suffix.lower() if keep_ext else forced_ext
                plan.append((img, dst_folder / (str(idx).zfill(padding) + ext)))
    else:
        all_imgs = [img for folder in subfolders
                    for img in folder_imgs.get(folder, [])]
        for idx, img in enumerate(all_imgs, start_num):
            ext = img.suffix.lower() if keep_ext else forced_ext
            dst_folder = out if out is not None else img.parent
            plan.append((img, dst_folder / (str(idx).zfill(padding) + ext)))

    return plan


def execute_rename_plan(plan, action, log, progress):
    """action: 'rename' | 'copy' | 'move'"""
    total = len(plan)
    if not total:
        log("⚠  Không có file nào cần xử lý."); return

    cross_dir = action in ("copy", "move")

    if cross_dir:
        dst_dirs = {dst.parent for _, dst in plan}
        for d in dst_dirs:
            d.mkdir(parents=True, exist_ok=True)

        done = 0
        lbl_done = 0
        for src, dst in plan:
            if action == "copy":
                shutil.copy2(src, dst)
            else:
                shutil.move(str(src), dst)
            src_lbl = src.with_suffix(".txt")
            if src_lbl.exists():
                dst_lbl = dst.with_suffix(".txt")
                if action == "copy":
                    shutil.copy2(src_lbl, dst_lbl)
                else:
                    shutil.move(str(src_lbl), dst_lbl)
                lbl_done += 1
            done += 1
            progress(done, total)
            if done % 50 == 0 or done == total:
                log(f"✔  {dst.parent.name}  /  {dst.name}")
        log("─" * 52)
        log(f"{'Đã sao chép' if action == 'copy' else 'Đã di chuyển'} : {done} file")
        if lbl_done:
            log(f"Label (.txt)        : {lbl_done} file")
    else:
        tmp_map = {}
        for i, (src, dst) in enumerate(plan):
            if src.resolve() == dst.resolve():
                continue
            tmp = src.parent / f"__rtmp{i:07d}__"
            src.rename(tmp)
            src_lbl = src.with_suffix(".txt")
            if src_lbl.exists():
                src_lbl.rename(src.parent / f"__rtmp{i:07d}__.txt")
            tmp_map[i] = (tmp, dst)

        done = 0
        lbl_done = 0
        for i in sorted(tmp_map):
            tmp, dst = tmp_map[i]
            tmp.rename(dst)
            tmp_lbl = tmp.parent / f"__rtmp{i:07d}__.txt"
            if tmp_lbl.exists():
                tmp_lbl.rename(dst.with_suffix(".txt"))
                lbl_done += 1
            done += 1
            progress(done, len(tmp_map))
            if done % 50 == 0 or done == len(tmp_map):
                log(f"✔  {dst.parent.name}  /  {dst.name}")

        unchanged = total - len(tmp_map)
        log("─" * 52)
        log(f"Đã đổi tên : {done} file")
        if lbl_done:
            log(f"Label (.txt) : {lbl_done} file")
        if unchanged:
            log(f"Giữ nguyên : {unchanged} file (đã đúng tên)")
