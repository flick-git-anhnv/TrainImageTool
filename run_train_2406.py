"""
KZTEK YOLO11n — 2-Stage Training Session 2406
Dataset : K:/Software/PhanLoaiPhuongTien-TrainDataset (7226 train / 1807 val)
Model   : yolo11n.pt (nano)
Output  : K:/Software/1.PhanLoaiPhuongTienChuan/Model/VietAnh/kztek_train_2406
Epochs  : 90 total  (Stage1: 30 freeze backbone, Stage2: 60 full fine-tune)
Techniques: AMP, auto-batch, cosine LR, label_smoothing, mixup, copy_paste,
            degrees, cls_weight, warmup, 2-stage freeze
"""
import os, sys, json, datetime
from pathlib import Path

# Windows multiprocessing guard — bắt buộc khi workers > 0
if __name__ == "__main__":

    try:
        from ultralytics import YOLO
    except ImportError:
        sys.exit("ERROR: ultralytics not installed. Run: pip install ultralytics")

    # ── Paths ──────────────────────────────────────────────────────────────
    DATA      = r"K:/Software/PhanLoaiPhuongTien-TrainDataset/data.yaml"
    MODEL_PT  = r"K:/Software/3.Tools/yolo11n.pt"
    PROJECT   = r"K:/Software/1.PhanLoaiPhuongTienChuan/Model/VietAnh"
    S1_NAME   = "kztek_train_2406_s1"
    S2_NAME   = "kztek_train_2406"
    LOG_FILE  = os.path.join(PROJECT, "kztek_train_2406_progress.json")

    def _log(stage: str, status: str, **kw):
        data = {
            "stage": stage,
            "status": status,
            "timestamp": datetime.datetime.now().isoformat(),
            **kw,
        }
        os.makedirs(PROJECT, exist_ok=True)
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"[PROGRESS] {data}")

    # ── Common hyperparameters ──────────────────────────────────────────────
    COMMON = dict(
        data            = DATA,
        imgsz           = 640,
        batch           = -1,       # auto-batch theo VRAM
        amp             = True,     # FP16 mixed precision
        cos_lr          = True,     # cosine annealing LR
        lrf             = 0.01,
        momentum        = 0.937,
        weight_decay    = 0.0005,
        warmup_epochs   = 3,
        warmup_momentum = 0.8,
        warmup_bias_lr  = 0.1,
        cls             = 1.5,      # ↑ classification loss cho multi-class
        label_smoothing = 0.1,      # soft labels
        patience        = 30,
        workers         = 4,
        project         = PROJECT,
        exist_ok        = True,
        verbose         = True,
        plots           = True,
        save            = True,
        save_period     = 10,
    )

    # ── Stage 1 — Freeze backbone ───────────────────────────────────────────
    print("\n" + "=" * 70)
    print("STAGE 1 -- Freeze backbone layers 0-9 (30 epochs, minimal aug)")
    print("Dataset:", DATA)
    print("Model  :", MODEL_PT)
    print("=" * 70)
    _log("stage1", "started", model=MODEL_PT, epochs=30, freeze=10)

    m1 = YOLO(MODEL_PT)
    m1.train(
        **COMMON,
        name            = S1_NAME,
        epochs          = 30,
        freeze          = 10,
        lr0             = 0.001,
        mosaic          = 0.0,
        mixup           = 0.0,
        copy_paste      = 0.0,
        degrees         = 0.0,
        flipud          = 0.0,
        fliplr          = 0.5,
        scale           = 0.5,
        hsv_h           = 0.015,
        hsv_s           = 0.7,
        hsv_v           = 0.4,
    )

    s1_best = str(Path(PROJECT) / S1_NAME / "weights" / "best.pt")
    _log("stage1", "done", best=s1_best)
    print(f"\n[STAGE 1 DONE] Best weights: {s1_best}")

    # ── Stage 2 — Full fine-tune ────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("STAGE 2 -- Full fine-tune (60 epochs, full augmentation)")
    print("Resume from:", s1_best)
    print("=" * 70)
    _log("stage2", "started", resume_from=s1_best, epochs=60, freeze=0)

    m2 = YOLO(s1_best)
    m2.train(
        **COMMON,
        name            = S2_NAME,
        epochs          = 60,
        freeze          = 0,
        lr0             = 0.0005,
        mosaic          = 1.0,
        mixup           = 0.15,
        copy_paste      = 0.1,
        degrees         = 10.0,
        flipud          = 0.0,
        fliplr          = 0.5,
        scale           = 0.5,
        hsv_h           = 0.015,
        hsv_s           = 0.7,
        hsv_v           = 0.4,
    )

    s2_best = str(Path(PROJECT) / S2_NAME / "weights" / "best.pt")
    _log("stage2", "done", best=s2_best, training_complete=True)

    print("\n" + "=" * 70)
    print("TRAINING COMPLETE")
    print(f"Stage 1 best : {s1_best}")
    print(f"Stage 2 best : {s2_best}")
    print("=" * 70)
