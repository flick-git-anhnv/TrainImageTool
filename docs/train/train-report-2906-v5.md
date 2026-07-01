# Báo cáo Training v5 — KZTEK iParking (2026-06-30 → 07-01)

**Model:** yolo11n — scratch từ COCO pretrained  
**Dataset:** `D:\Software\PhanLoaiPhuongTien-TrainDataset` (đã rebuild + bổ sung ảnh)  
**Output:** `D:\Software\Model\kztek_v5_scratch_200ep\`  
**Trạng thái:** ✅ HOÀN THÀNH (Early stop ep193/200)  
**Thời gian:** 10:53 (30/06) → 03:20 (01/07) — tổng ~16.5h  

---

## Kết quả cuối

| Metric | Giá trị | Epoch |
|---|---|---|
| **mAP50-95 (best)** | **0.8118** | ep143 |
| mAP50 | 0.9542 | ep143 |
| Precision | 0.9451 | ep143 |
| Recall | 0.9150 | ep143 |
| val/box_loss | 0.6208 | ep143 |
| val/cls_loss | 0.3824 | ep143 |
| Early stop | ep193 | patience=50 từ ep143 |

---

## So sánh v4 vs v5 — KẾT QUẢ THỰC TẾ

| Metric | v4 (ep250, 6 class) | v5 (ep193, 9 class) | Thay đổi |
|---|---|---|---|
| **mAP50-95** | 0.7714 | **0.8118** | **+0.040 ✅** |
| mAP50 | 0.9370 | **0.9542** | +0.017 ✅ |
| Precision | 0.9420 | **0.9451** | +0.003 ✅ |
| Recall | 0.9180 | **0.9150** | -0.003 ≈ |
| Classes | 6 | **9** (+3 biển số màu) | — |
| Epochs chạy | 250 | 193 (early stop) | — |

**v5 vượt v4 trên tất cả metrics chính mặc dù có thêm 3 class.**

---

## Cấu hình training

| Tham số | Giá trị | Ghi chú |
|---|---|---|
| base model | yolo11n.pt | COCO pretrained — scratch (không fine-tune từ v4) |
| dataset | PhanLoaiPhuongTien-TrainDataset | 8661 train / 2169 val |
| nc | 9 | car, motorcycle, bus, truck, bicycle, license_plate, plate_vang, plate_xanh, plate_do |
| epochs | 200 (chạy 193) | early stop patience=50 |
| imgsz | 640 | — |
| batch | 16 / nbs 64 | — |
| device | 0 (GPU) | — |
| optimizer | auto (AdamW) | — |
| cos_lr | True | cosine decay |
| lr0 / lrf | 0.01 / 0.01 | lr min = 0.0001 |
| warmup_epochs | 3 | — |
| weight_decay | 0.0005 | — |
| momentum | 0.937 | — |
| iou | 0.7 | — |
| amp | True | mixed precision |
| label_smoothing | 0.1 | — |
| cls / box / dfl | 0.5 / 7.5 / 1.5 | — |
| mixup / copy_paste | 0.15 / 0.1 | — |
| degrees / erasing / fliplr | 3.0 / 0.4 / 0.5 | — |
| hsv_h/s/v | 0.015 / 0.7 / 0.4 | — |
| patience | 50 | early stop tại ep193 |
| close_mosaic | 20 | tắt mosaic ep181–200 |
| save_period | 10 | checkpoint mỗi 10 ep |
| cache | False | — |

---

## Kết quả theo epoch (các mốc chính)

| EP | mAP50-95 | mAP50 | Prec | Recall | vbox↓ | vcls↓ | Ghi chú |
|---|---|---|---|---|---|---|---|
| 1 | 0.484 | 0.669 | 0.813 | 0.613 | 0.952 | 1.009 | Warmup ep1 |
| 3 | 0.370 | 0.582 | 0.682 | 0.541 | 1.224 | 1.304 | Warmup peak LR=0.030 |
| 10 | 0.648 | 0.878 | 0.845 | 0.799 | 0.983 | 0.716 | Post-warmup |
| 14 | 0.686 | 0.902 | 0.921 | 0.824 | 0.909 | 0.618 | Resume sau gián đoạn |
| 25 | 0.726 | 0.928 | 0.911 | 0.877 | 0.856 | 0.544 | Vượt target 0.72 |
| 39 | 0.756 | 0.943 | 0.924 | 0.893 | 0.733 | 0.489 | — |
| 57 | 0.787 | 0.948 | 0.952 | 0.897 | 0.679 | 0.440 | Vượt v4 (0.771) |
| 70 | 0.791 | 0.948 | 0.939 | 0.906 | 0.665 | 0.416 | — |
| 84 | 0.794 | 0.951 | 0.936 | 0.908 | 0.644 | 0.406 | — |
| 98 | 0.801 | 0.953 | 0.950 | 0.911 | 0.635 | 0.398 | Vượt mốc 0.80 |
| 112 | 0.802 | 0.954 | 0.952 | 0.905 | 0.629 | 0.393 | — |
| 120 | 0.806 | 0.955 | 0.941 | 0.918 | 0.626 | 0.389 | — |
| 135 | 0.811 | 0.954 | 0.945 | 0.913 | 0.622 | 0.384 | — |
| **143** | **0.812** | **0.954** | **0.945** | **0.915** | **0.621** | **0.382** | **⭐ BEST** |
| 158 | 0.811 | 0.955 | 0.953 | 0.906 | 0.619 | 0.380 | Plateau |
| 178 | 0.808 | 0.958 | 0.950 | 0.913 | 0.619 | 0.378 | Gần close_mosaic |
| 181+ | 0.808 | 0.958 | 0.952 | 0.910 | 0.619 | 0.377 | close_mosaic: train/box giảm 17% |
| 193 | 0.808 | 0.959 | 0.956 | 0.909 | 0.618 | 0.376 | Early stop |

---

## Phân tích kết quả

### Điểm nổi bật
1. **v5 vượt v4** (+0.040 mAP50-95) dù thêm 3 class biển số màu — dataset mới chất lượng cao hơn
2. **Hội tụ nhanh**: vượt target 0.72 chỉ sau ep25, vượt v4 (0.771) tại ep57
3. **Early stop hợp lệ**: không cải thiện 50 ep liên tiếp từ ep143 → dừng tại ep193 là đúng
4. **close_mosaic**: tắt mosaic ep181 làm train/box giảm 17% nhưng không cải thiện thêm val mAP

### Tốc độ học
| Giai đoạn | ep | mAP50-95 | Tốc độ tăng |
|---|---|---|---|
| Warmup | 1–3 | 0.484→0.370 | dao động |
| Post-warmup | 3–57 | 0.370→0.787 | +0.0076/ep |
| Plateau 1 | 57–143 | 0.787→0.812 | +0.0003/ep |
| Plateau 2 | 143–193 | plateau 0.808–0.812 | ~0 |

### Checkpoints có sẵn
- `best.pt` — ep143, mAP50-95=0.812 ← **dùng cho production**
- `last.pt` — ep193 (same as best.pt, 5.5MB stripped)
- `epoch10.pt` → `epoch190.pt` — mỗi 10 ep (15.9MB full)

---

## Đề xuất tiếp theo

### Ngắn hạn
1. **Test best.pt** trên video/ảnh thực tế iParking với 9 class
2. **Kiểm tra per-class mAP** — xem plate_vang/plate_xanh/plate_do học được bao nhiêu
3. Deploy thử nghiệm song song v4 (6 class) và v5 (9 class)

### Nếu muốn cải thiện thêm
1. **Tăng patience=80** và **epochs=250** → cho model thêm cơ hội sau plateau
2. **Tăng dataset** plate_vang/xanh/do — các class mới thường cần nhiều ảnh hơn
3. **Thử fine-tune từ v5 best.pt** với augmentation nhẹ hơn (mixup=0.05, erasing=0.2) cho dataset production mới

---

## Update log

| Thời gian | Epoch | mAP50-95 | Ghi chú |
|---|---|---|---|
| 2026-06-30 ~10:53 | 1/200 | 0.484 | Training khởi động, warmup epoch 1/3 |
| 2026-06-30 ~19:09 | 3/200 | 0.370 | Warmup phase — lr=0.03 |
| 2026-06-30 ~19:38 | 14/200 | 0.686 | Resume sau gián đoạn máy |
| 2026-06-30 ~20:48 | 26/200 | 0.719 | Vượt target 0.72 |
| 2026-06-30 ~21:19 | 39/200 | 0.756 | — |
| 2026-06-30 ~22:02 | 57/200 | 0.787 | Vượt v4 (0.771) |
| 2026-06-30 ~22:33 | 70/200 | 0.791 | — |
| 2026-06-30 ~23:04 | 84/200 | 0.794 | — |
| 2026-06-30 ~23:24 | 93/200 | 0.798 | — |
| 2026-07-01 ~00:11 | 101/200 | 0.801 | Vượt 0.80 |
| 2026-07-01 ~00:57 | 112/200 | 0.804 | — |
| 2026-07-01 ~01:26 | 120/200 | 0.807 | — |
| 2026-07-01 ~02:07 | 140/200 | 0.811 | — |
| 2026-07-01 ~02:25 | 158/200 | 0.811 | Plateau bắt đầu |
| 2026-07-01 ~02:52 | 178/200 | 0.808 | Gần close_mosaic |
| 2026-07-01 03:23 | **143/200** | **0.812** | **⭐ BEST — Early stop ep193** |
