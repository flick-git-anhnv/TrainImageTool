"""
KZTEK Train Test — 10 epochs, 80/20 split, AdamW + Cosine LR
Data: K:/Software/2.AI-Tranining/1.Images/2.Output  (all subfolders)
"""
import os, sys, random, shutil, multiprocessing, csv, time
from pathlib import Path

multiprocessing.freeze_support()
os.environ.setdefault('KMP_DUPLICATE_LIB_OK', 'TRUE')

IMAGE_EXT  = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}
LABELS     = ['car', 'motorcycle', 'bus', 'truck', 'bicycle', 'license_plate']
TRAIN_DIR  = Path('K:/Software/2.AI-Tranining/1.Images/2.Output')
SPLIT_DIR  = Path('K:/kztek_split_test10ep')
PROJECT    = 'E:/KZTEK/AI/test-model/model-by-claude11'
MODEL_PT   = 'H:/Software/2.AI-Tranining/3.Tools/yolo11n.pt'

def link_or_copy(src: Path, dst: Path):
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)

if __name__ == '__main__':
    t0 = time.time()

    # ── 1. Collect valid image-label pairs ───────────────────────────────
    pairs = []
    for img in TRAIN_DIR.rglob('*'):
        if img.suffix.lower() in IMAGE_EXT:
            lbl = img.with_suffix('.txt')
            if lbl.exists() and lbl.stat().st_size > 0:
                pairs.append(img)
    print(f'[1/3] Collected {len(pairs)} valid image-label pairs', flush=True)

    # ── 2. 80/20 split ──────────────────────────────────────────────────
    random.seed(42)
    random.shuffle(pairs)
    n_train = int(len(pairs) * 0.80)
    train_imgs = pairs[:n_train]
    val_imgs   = pairs[n_train:]
    print(f'[2/3] Split -> Train={len(train_imgs)}  Val={len(val_imgs)}', flush=True)

    # ── 3. Build hardlinked dataset dir ─────────────────────────────────
    if SPLIT_DIR.exists():
        print(f'      Removing old split dir...', flush=True)
        shutil.rmtree(str(SPLIT_DIR))

    for split_name, imgs in [('train', train_imgs), ('val', val_imgs)]:
        img_out = SPLIT_DIR / 'images' / split_name
        lbl_out = SPLIT_DIR / 'labels' / split_name
        img_out.mkdir(parents=True, exist_ok=True)
        lbl_out.mkdir(parents=True, exist_ok=True)
        for idx, img in enumerate(imgs):
            lbl = img.with_suffix('.txt')
            link_or_copy(img, img_out / f'{idx:06d}{img.suffix}')
            link_or_copy(lbl, lbl_out / f'{idx:06d}.txt')
        print(f'      {split_name}: {len(imgs)} files linked ({time.time()-t0:.1f}s)', flush=True)

    # Write data.yaml
    names_str = ', '.join(f"'{c}'" for c in LABELS)
    yaml_path = SPLIT_DIR / 'data.yaml'
    yaml_path.write_text(
        f"path: {SPLIT_DIR}\n"
        f"train: images/train\n"
        f"val:   images/val\n"
        f"nc: {len(LABELS)}\n"
        f"names: [{names_str}]\n",
        encoding='utf-8')
    print(f'[3/3] data.yaml -> {yaml_path}', flush=True)
    print(f'      Setup done in {time.time()-t0:.1f}s', flush=True)
    print('─' * 60, flush=True)

    # ── 4. Train ─────────────────────────────────────────────────────────
    from ultralytics import YOLO
    model = YOLO(MODEL_PT)
    print(f'Model: {MODEL_PT}', flush=True)
    print(f'Training with: AdamW  lr0=0.01  lrf=0.01  cos_lr=True'
          f'  close_mosaic=3  weight_decay=0.0005  batch=auto', flush=True)
    print('─' * 60, flush=True)

    results = model.train(
        data=str(yaml_path),
        epochs=10,
        imgsz=640,
        batch=-1,          # auto batch (fits VRAM)
        device='0',
        project=PROJECT,
        name='kztek_train',
        exist_ok=True,
        optimizer='AdamW',
        lr0=0.01,
        lrf=0.01,
        close_mosaic=3,    # tắt mosaic ở 3 epoch cuối
        cache=False,
        workers=4,
        cos_lr=True,
        weight_decay=0.0005,
    )

    save_dir = str(results.save_dir)
    print(f'KZTEK_SAVE_DIR: {save_dir}', flush=True)

    # ── 5. Summary ───────────────────────────────────────────────────────
    csv_path = os.path.join(save_dir, 'results.csv')
    best_map50 = 0.0
    best_map95 = 0.0
    last_prec  = 0.0
    last_rec   = 0.0
    n_done = 0
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
                except Exception:
                    pass

    total_time = time.time() - t0
    print('═' * 60, flush=True)
    print(f'DONE  {n_done}/10 epochs  total={total_time/60:.1f} min', flush=True)
    print(f'  best mAP@50    : {best_map50:.4f}', flush=True)
    print(f'  best mAP@50-95 : {best_map95:.4f}', flush=True)
    print(f'  Precision      : {last_prec:.4f}', flush=True)
    print(f'  Recall         : {last_rec:.4f}', flush=True)
    print(f'  best.pt        -> {save_dir}/weights/best.pt', flush=True)
    print('═' * 60, flush=True)
