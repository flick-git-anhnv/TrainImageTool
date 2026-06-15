"""
KZTEK Fine-tune v2 — tiep tuc tu best.pt cua claude12 (kztek_train ep33)
Dataset: K:/kztek_split/data.yaml (cung dataset voi fresh train)

Fix so voi v1:
- lr0=0.0001  (giam 10x so voi fresh train 0.001)
- lrf=0.1     (final LR = 0.00001 — tranh LR qua thap khi close_mosaic)
- close_mosaic=10  (20% epochs cuoi, thay vi 10%)
- warmup_epochs=1  (ngan hon cho finetune)
"""
import os, sys, multiprocessing, csv, time
from pathlib import Path

multiprocessing.freeze_support()
os.environ.setdefault('KMP_DUPLICATE_LIB_OK', 'TRUE')

BEST_PT   = 'E:/KZTEK/AI/test-model/model-by-claude12/kztek_train/weights/best.pt'
YAML_PATH = 'K:/kztek_split/data.yaml'
PROJECT   = 'E:/KZTEK/AI/test-model/model-by-claude12'
RUN_NAME  = 'kztek_finetune_v2'
EPOCHS    = 50

if __name__ == '__main__':
    for label, path in [('best.pt', BEST_PT), ('data.yaml', YAML_PATH)]:
        if not Path(path).exists():
            print(f'[LOI] Khong tim thay {label}: {path}')
            sys.exit(1)

    print('=' * 60)
    print('KZTEK Fine-tune v2')
    print(f'  Base model   : {BEST_PT}')
    print(f'  Dataset      : {YAML_PATH}')
    print(f'  Epochs       : {EPOCHS}')
    print(f'  LR0 / LRF    : 0.0001 / 0.1  (final LR = 0.00001)')
    print(f'  cos_lr       : True')
    print(f'  close_mosaic : 10  (ep{EPOCHS-10+1}-{EPOCHS})')
    print(f'  warmup_epochs: 1')
    print(f'  Output       : {PROJECT}/{RUN_NAME}')
    print('=' * 60)

    t0 = time.time()

    from ultralytics import YOLO
    model = YOLO(BEST_PT)

    results = model.train(
        data=YAML_PATH,
        epochs=EPOCHS,
        imgsz=640,
        batch=6,
        device='0',
        project=PROJECT,
        name=RUN_NAME,
        exist_ok=True,
        optimizer='AdamW',
        lr0=0.0001,
        lrf=0.1,
        cos_lr=True,
        warmup_epochs=1,
        close_mosaic=10,
        cache=False,
        workers=4,
        weight_decay=0.0005,
        patience=20,
    )

    save_dir = str(results.save_dir)
    print(f'KZTEK_SAVE_DIR: {save_dir}')

    csv_path = os.path.join(save_dir, 'results.csv')
    best_map50 = 0.0
    best_map95 = 0.0
    best_ep    = 0
    last_prec  = 0.0
    last_rec   = 0.0
    n_done     = 0
    if os.path.exists(csv_path):
        with open(csv_path, newline='', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                row = {k.strip(): v.strip() for k, v in row.items()}
                n_done += 1
                try:
                    m50 = float(row.get('metrics/mAP50(B)', 0))
                    if m50 > best_map50:
                        best_map50 = m50
                        best_map95 = float(row.get('metrics/mAP50-95(B)', 0))
                        last_prec  = float(row.get('metrics/precision(B)', 0))
                        last_rec   = float(row.get('metrics/recall(B)', 0))
                        best_ep    = n_done
                except Exception:
                    pass

    total_min = (time.time() - t0) / 60
    print('=' * 60)
    print(f'DONE  {n_done}/{EPOCHS} epochs  tong={total_min:.1f} phut')
    print(f'  Best epoch     : {best_ep}')
    print(f'  best mAP@50    : {best_map50:.4f}')
    print(f'  best mAP@50-95 : {best_map95:.4f}')
    print(f'  Precision      : {last_prec:.4f}')
    print(f'  Recall         : {last_rec:.4f}')
    print(f'  best.pt        -> {save_dir}/weights/best.pt')
    print('=' * 60)
