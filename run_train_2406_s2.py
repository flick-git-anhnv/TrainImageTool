"""
KZTEK — Stage 2 resume từ last.pt (epoch 19/60)
Dùng resume=True để tiếp tục đúng epoch, optimizer state, LR schedule
"""
import os, sys, json, datetime
from pathlib import Path

if __name__ == "__main__":
    from ultralytics import YOLO

    PROJECT  = r"K:/Software/1.PhanLoaiPhuongTienChuan/Model/VietAnh"
    S2_LAST  = r"K:/Software/1.PhanLoaiPhuongTienChuan/Model/VietAnh/kztek_train_2406/weights/last.pt"
    S1_BEST  = r"K:/Software/1.PhanLoaiPhuongTienChuan/Model/VietAnh/kztek_train_2406_s1/weights/best.pt"
    LOG_FILE = os.path.join(PROJECT, "kztek_train_2406_progress.json")

    def _log(stage, status, **kw):
        data = {"stage": stage, "status": status,
                "timestamp": datetime.datetime.now().isoformat(), **kw}
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"[PROGRESS] {data}")

    if os.path.exists(S2_LAST):
        # Resume đúng từ epoch 19, giữ nguyên optimizer state + LR schedule
        print("=" * 70)
        print("STAGE 2 -- RESUME từ last.pt (epoch 19 -> 60)")
        print("Checkpoint:", S2_LAST)
        print("=" * 70)
        _log("stage2", "started", resume_from=S2_LAST, note="resume=True")
        m = YOLO(S2_LAST)
        m.train(resume=True)
    else:
        # Fallback: restart từ S1 best nếu không có last.pt
        from pathlib import Path
        DATA    = r"K:/Software/PhanLoaiPhuongTien-TrainDataset/data.yaml"
        S2_NAME = "kztek_train_2406"
        print("=" * 70)
        print("STAGE 2 -- START từ S1 best.pt (last.pt không tìm thấy)")
        print("=" * 70)
        _log("stage2", "started", resume_from=S1_BEST)
        m = YOLO(S1_BEST)
        m.train(
            data=DATA, imgsz=640, batch=-1, amp=True, cos_lr=True,
            lr0=0.0005, lrf=0.01, momentum=0.937, weight_decay=0.0005,
            warmup_epochs=3, cls=1.5, label_smoothing=0.1, patience=30,
            workers=4, project=PROJECT, name=S2_NAME, epochs=60, freeze=0,
            exist_ok=True, verbose=True, plots=True, save=True, save_period=10,
            mosaic=1.0, mixup=0.15, copy_paste=0.1, degrees=10.0,
            flipud=0.0, fliplr=0.5, scale=0.5, hsv_h=0.015, hsv_s=0.7, hsv_v=0.4,
        )

    s2_best = str(Path(PROJECT) / "kztek_train_2406" / "weights" / "best.pt")
    _log("stage2", "done", best=s2_best, training_complete=True)
    print("\nSTAGE 2 COMPLETE -- Final best:", s2_best)
