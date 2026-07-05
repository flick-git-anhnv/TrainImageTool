# Báo cáo Fine-tune v5.2 — KZTEK iParking (2026-07-04)

**Base model:** `kztek_v5_finetune_80ep/weights/best_0107_local.pt` (v5.1 best, mAP50-95=0.814)
**Dataset:** `D:\Software\PhanLoaiPhuongTien-TrainDataset` (+196 hard-negative images → 11296 train / 2850 val tại thời điểm train)
**Output:** `D:\Software\Model\kztek_v5_finetune2_80ep\`
**Trạng thái:** ✅ HOÀN THÀNH — ep80/80
**Thời gian:** 04/07/2026 — ~2.2h (resumed từ epoch30.pt)

---

## Kết quả cuối

| Metric | Giá trị | Epoch |
|---|---|---|
| **mAP50-95 (best)** | **0.8296** | ep1 |
| mAP50-95 (ep80) | 0.7996 | ep80 |
| mAP50 (ep80) | 0.944 | ep80 |
| Precision (ep80) | 0.946 | ep80 |
| Recall (ep80) | 0.905 | ep80 |
| val/box_loss (ep80) | 0.583 | ep80 |
| val/cls_loss (ep80) | 0.366 | ep80 |

---

## So sánh toàn bộ phiên bản

| Model | Train | Val | Epochs | mAP50-95 | mAP50 | Ghi chú |
|---|---|---|---|---|---|---|
| v4 (fine-tune) | ~7000 | ~2000 | 250 | 0.771 | 0.937 | 6 classes |
| v5 (scratch) | 9212 | 2298 | 193* | 0.812 | 0.954 | 9 classes |
| v5.1 (fine-tune) | 9212 | 2298 | 67* | 0.814 | 0.954 | — |
| **v5.2 (fine-tune)** | **11296** | **2850** | **1*** | **0.830** | **0.967** | best=ep1 |
| v5.2 (ep80 final) | 11296 | 2850 | 80 | 0.800 | 0.944 | — |

*best epoch / early stop

---

## Phân tích: Tại sao best = ep1?

**Hiện tượng:** Training bắt đầu từ 0.830 (ep1), sau đó dip xuống ~0.779 (ep32), hồi phục về 0.800 (ep58-80), nhưng không vượt được điểm khởi đầu.

**Nguyên nhân:**

1. **Val set thay đổi distribution**: 2,850 val vs 2,298 val trước — 552 ảnh mới thêm vào val gồm cả hard cases. Khi model bắt đầu fine-tune với hard negatives, nó phải "relearn" từ đầu với distribution mới.

2. **Hard negatives là ảnh model đã thất bại**: Những ảnh này có đặc điểm bất thường (góc chụp lạ, điều kiện sáng tối cực đoan, biển số bị che khuất). Fine-tune từ một model tốt với những ảnh như vậy có thể làm mất ổn định weights.

3. **LR chưa điều chỉnh**: Đáng nhẽ cần LR thấp hơn (lr0=0.0001) khi dataset thêm hard cases, để "nhúng nhẹ" kiến thức mới vào model thay vì overwrite.

**Kết luận:** `best.pt` (ep1 = 0.830) vẫn là model tốt nhất và nên dùng cho production.

---

## Cấu hình fine-tune v5.2

| Tham số | Giá trị |
|---|---|
| base | v5.1 best.pt |
| lr0 | 0.001 |
| lrf | 0.01 |
| warmup_epochs | 3 |
| epochs | 80 |
| patience | 30 |
| close_mosaic | 10 |
| batch / nbs | 16 / 64 |

---

## Diễn tiến training

| EP | mAP50-95 | Ghi chú |
|---|---|---|
| 1 | **0.830** ⭐ | **BEST — model loaded từ v5.1** |
| 31 | 0.782 | Crash — resumed từ epoch30.pt |
| 32 | 0.779 | Mid-training dip |
| 47 | 0.789 | Hồi phục chậm |
| 55 | 0.800 | Ổn định |
| 57 | 0.801 | Đỉnh sau ep1 |
| 70 | ~0.799 | close_mosaic không cải thiện thêm |
| 80 | 0.800 | Kết thúc |

---

## Checkpoint

| File | EP | mAP50-95 | Dùng cho |
|---|---|---|---|
| `best.pt` | 1 | **0.830** | **Production — dùng cái này** |
| `last.pt` | 80 | 0.800 | — |

---

## Hành động tiếp theo — v6 Scratch

Vì fine-tune với hard negatives không cải thiện mAP tổng thể, quyết định:

**Train lại từ đầu (v6 scratch)** với toàn bộ dataset đã bổ sung:
- Base: `yolo11n.pt` (COCO pretrained)
- Dataset: 11,419 train / 2,850 val
- Epochs: 200
- Dự kiến: 14–16h training

**Lý do chọn scratch thay vì fine-tune:**
- Dataset đã tăng ~24% (9,212 → 11,419 train)
- Hard negatives phân bố đều trong training từ đầu
- Tránh "bias" từ model cũ đã học trên distribution cũ
- Scratch cho phép optimizer học từ đầu trên distribution đầy đủ

**Kỳ vọng v6:** mAP50-95 ≥ 0.820 (vượt v5.1 rõ ràng, có thể vượt v5.2 best 0.830)
