"""
Migration script: reorganize tool/ from flat → feature-based structure.
Run from project root: python _migrate.py
"""
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).parent
TOOL = ROOT / "tool"

# ── 1. Định nghĩa cấu trúc mới ────────────────────────────────────────────
DIRS = [
    "tool/core",
    "tool/features",
    "tool/features/dataset",
    "tool/features/annotation",
    "tool/features/collection",
    "tool/features/analysis",
    "tool/features/detection",
    "tool/features/training",
    "tool/utils",
]

# (src_relative_to_tool, dst_relative_to_tool)
MOVES = [
    # core/
    ("app.py",               "core/app.py"),
    ("settings.py",          "core/settings.py"),
    ("constants.py",         "core/constants.py"),
    ("imports.py",           "core/imports.py"),
    ("ui_helpers.py",        "core/ui_helpers.py"),
    # features/dataset/
    ("tab_split.py",         "features/dataset/tab_split.py"),
    ("core_split.py",        "features/dataset/core_split.py"),
    ("tab_rename.py",        "features/dataset/tab_rename.py"),
    ("core_rename.py",       "features/dataset/core_rename.py"),
    ("tab_crop.py",          "features/dataset/tab_crop.py"),
    ("core_crop.py",         "features/dataset/core_crop.py"),
    ("tab_labelnorm.py",     "features/dataset/tab_labelnorm.py"),
    ("core_label_norm.py",   "features/dataset/core_label_norm.py"),
    # features/annotation/
    ("tab_bbox.py",          "features/annotation/tab_bbox.py"),
    ("tab_checker.py",       "features/annotation/tab_checker.py"),
    ("tab_ocr.py",           "features/annotation/tab_ocr.py"),
    # features/collection/
    ("tab_iparking_image.py","features/collection/tab_iparking_image.py"),
    ("tab_lotte.py",         "features/collection/tab_lotte.py"),
    ("lotte_image.py",       "features/collection/lotte_image.py"),
    ("lotte_consolidate.py", "features/collection/lotte_consolidate.py"),
    ("tab_parkingv8.py",     "features/collection/tab_parkingv8.py"),
    ("tab_parkingv6.py",     "features/collection/tab_parkingv6.py"),
    ("parkingv6_image.py",   "features/collection/parkingv6_image.py"),
    ("parkingv8_image.py",   "features/collection/parkingv8_image.py"),
    # features/analysis/
    ("tab_stats.py",         "features/analysis/tab_stats.py"),
    ("core_gt.py",           "features/analysis/core_gt.py"),
    ("tab_plate_search.py",  "features/analysis/tab_plate_search.py"),
    # features/detection/
    ("tab_yolo.py",          "features/detection/tab_yolo.py"),
    ("tab_lpr_tester.py",    "features/detection/tab_lpr_tester.py"),
    # features/training/
    ("tab_train.py",         "features/training/tab_train.py"),
    # utils/
    ("bad_image_viewer.py",  "utils/bad_image_viewer.py"),
    ("migrate_structure.py", "utils/migrate_structure.py"),
]

# ── 2. Import transforms theo vị trí đích ────────────────────────────────
# Format: (old_from_prefix, new_from_prefix)
# Applied per-file based on destination subfolder

# Cho files trong tool/features/*/  (3-level: tool.features.X.module)
TRANSFORMS_FEATURES = [
    ("from .constants import",   "from ...core.constants import"),
    ("from .settings import",    "from ...core.settings import"),
    ("from .ui_helpers import",  "from ...core.ui_helpers import"),
    ("from .imports import",     "from ...core.imports import"),
]

# Cho files trong tool/utils/  (2-level: tool.utils.module)
TRANSFORMS_UTILS = [
    ("from .constants import",   "from ..core.constants import"),
    ("from .settings import",    "from ..core.settings import"),
    ("from .ui_helpers import",  "from ..core.ui_helpers import"),
    ("from .imports import",     "from ..core.imports import"),
]

# Transforms chỉ áp dụng cho collection/
TRANSFORMS_COLLECTION = [
    ("from .bad_image_viewer import",  "from ...utils.bad_image_viewer import"),
    ("from .migrate_structure import", "from ...utils.migrate_structure import"),
]

# Transforms chỉ áp dụng cho annotation/ (tab_checker dùng core_gt)
TRANSFORMS_ANNOTATION = [
    ("from .core_gt import", "from ..analysis.core_gt import"),
]

# Transforms cho tool/core/app.py (import các tab)
TRANSFORMS_CORE_APP = [
    # infrastructure (same dir) → không đổi: from .imports, from .ui_helpers, etc.
    # Tab imports:
    ("from .tab_split import",           "from ..features.dataset.tab_split import"),
    ("from .tab_rename import",          "from ..features.dataset.tab_rename import"),
    ("from .tab_crop import",            "from ..features.dataset.tab_crop import"),
    ("from .tab_labelnorm import",       "from ..features.dataset.tab_labelnorm import"),
    ("from .tab_bbox import",            "from ..features.annotation.tab_bbox import"),
    ("from .tab_iparking_image import",  "from ..features.collection.tab_iparking_image import"),
    ("from .tab_checker import",         "from ..features.annotation.tab_checker import"),
    ("from .tab_stats import",           "from ..features.analysis.tab_stats import"),
    ("from .tab_plate_search import",    "from ..features.analysis.tab_plate_search import"),
    ("from .tab_yolo import",            "from ..features.detection.tab_yolo import"),
    ("from .tab_train import",           "from ..features.training.tab_train import"),
    ("from .tab_lpr_tester import",      "from ..features.detection.tab_lpr_tester import"),
]


def apply_transforms(content: str, transforms: list) -> str:
    for old, new in transforms:
        content = content.replace(old, new)
    return content


def migrate():
    print("=" * 60)
    print("KZTEK Image Tools — Migration to feature-based structure")
    print("=" * 60)

    # 1. Tạo thư mục
    for d in DIRS:
        target = ROOT / d
        target.mkdir(parents=True, exist_ok=True)
        init = target / "__init__.py"
        if not init.exists():
            init.write_text("", encoding="utf-8")
        print(f"  [DIR] {d}/")

    # 2. Copy + transform từng file
    for src_rel, dst_rel in MOVES:
        src = TOOL / src_rel
        dst = ROOT / "tool" / dst_rel

        if not src.exists():
            print(f"  [SKIP] {src_rel} — không tìm thấy")
            continue

        content = src.read_text(encoding="utf-8", errors="replace")
        original = content

        # Xác định transforms cần áp dụng
        dst_parts = Path(dst_rel).parts  # e.g. ('features', 'dataset', 'tab_split.py')
        is_features = dst_parts[0] == "features"
        is_utils = dst_parts[0] == "utils"
        is_core = dst_parts[0] == "core"
        feature_name = dst_parts[1] if is_features else None

        if is_features:
            content = apply_transforms(content, TRANSFORMS_FEATURES)
            if feature_name == "collection":
                content = apply_transforms(content, TRANSFORMS_COLLECTION)
            if feature_name == "annotation":
                content = apply_transforms(content, TRANSFORMS_ANNOTATION)
        elif is_utils:
            content = apply_transforms(content, TRANSFORMS_UTILS)
        elif is_core and src_rel == "app.py":
            content = apply_transforms(content, TRANSFORMS_CORE_APP)

        dst.write_text(content, encoding="utf-8")
        changed = " [TRANSFORMED]" if content != original else ""
        print(f"  [COPY] {src_rel:<35} -> {dst_rel}{changed}")

    print()
    print("Migration hoàn tất!")
    print("Bước tiếp theo:")
    print("  1. Kiểm tra imports thủ công nếu cần")
    print("  2. Chạy: python train-image-tool.py để kiểm tra")
    print("  3. Sau khi xác nhận OK, xóa file cũ trong tool/ root")


if __name__ == "__main__":
    migrate()
