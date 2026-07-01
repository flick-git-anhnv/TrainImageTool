# Báo cáo Fine-tune v5.1 — KZTEK iParking (2026-07-01)

**Base model:** `kztek_v5_scratch_200ep/weights/best.pt` (mAP50-95=0.812)  
**Dataset:** `D:\Software\PhanLoaiPhuongTien-TrainDataset` (+700 ảnh mới → 9212 train / 2298 val)  
**Output:** `D:\Software\Model\kztek_v5_finetune_80ep\`  
**Trạng thái:** ✅ HOÀN THÀNH — ep80/80  
**Thời gian:** 07:15 → 11:04 (01/07) — ~3.75h  

---

## Kết quả cuối

| Metric | Giá trị | Epoch |
|---|---|---|
| **mAP50-95 (best)** | **0.8139** | ep67 |
| mAP50 | 0.9535 | ep67 |
| Precision | 0.9384 | ep67 |
| Recall | 0.9143 | ep67 |
| val/box_loss | 0.6169 | ep67 |
| val/cls_loss | 0.3792 | ep67 |

---

## So sánh toàn bộ phiên bản

| Model | Classes | Epochs | mAP50-95 | mAP50 | Prec | Recall |
|---|---|---|---|---|---|---|
| v4 (fine-tune) | 6 | 250 | 0.7714 | 0.9370 | 0.942 | 0.918 |
| v5 (scratch) | 9 | 193* | 0.8118 | 0.9542 | 0.945 | 0.915 |
| **v5.1 (fine-tune)** | **9** | **67*** | **0.8139** | **0.9535** | **0.938** | **0.914** |

*early stop / best epoch

**v5.1 là model tốt nhất — vượt v5 scratch (+0.002) và v4 (+0.042).**

---

## Cấu hình fine-tune

| Tham số | Giá trị | So với scratch |
|---|---|---|
| base | v5 best.pt | COCO pretrained → v5 → v5.1 |
| lr0 | 0.001 | 10× thấp hơn scratch (0.01) |
| lrf | 0.01 | — |
| warmup_epochs | 3 | — |
| epochs | 80 | 200 (scratch) |
| patience | 30 | 50 (scratch) |
| close_mosaic | 10 | 20 (scratch) |
| mixup | 0.05 | 0.15 (scratch) — augmentation nhẹ hơn |
| copy_paste | 0.05 | 0.10 (scratch) |
| label_smoothing | 0.05 | 0.10 (scratch) |
| batch / nbs | 16 / 64 | — |
| iou / amp | 0.7 / True | — |

---

## Diễn tiến training

| EP | mAP50-95 | Ghi chú |
|---|---|---|
| 1 | 0.786 | Khởi đầu cao (từ v5 best) vs scratch ep1=0.484 |
| 8 | 0.764 | Warmup dip — LR ramp up |
| 21 | 0.771 | Phục hồi sau warmup |
| 28 | 0.782 | — |
| 43 | 0.797 | — |
| 54 | 0.810 | Gần bằng v5 best |
| **67** | **0.814** ⭐ | **BEST — vượt v5 (0.812)** |
| 70 | 0.813 | — |
| 71 | 0.810 | close_mosaic bắt đầu |
| 80 | 0.808 | Kết thúc |

---

## Nhận xét

1. **Fine-tune hiệu quả**: chỉ 67 ep đạt best, so với scratch cần 143 ep — **nhanh hơn 2×**
2. **Dataset mới giúp ích**: +700 ảnh mix → mAP tăng 0.002 so với v5 (0.812→0.814)
3. **val/cls_loss thấp hơn v5**: 0.379 vs 0.382 → phân biệt 9 class tốt hơn một chút
4. **close_mosaic ep71**: train/box giảm 9% (0.611→0.562) nhưng không cải thiện thêm val mAP — hội tụ trước ep70

---

## Checkpoint có sẵn

| File | EP | mAP50-95 | Dùng cho |
|---|---|---|---|
| `best.pt` | 67 | **0.814** | **Production ← dùng cái này** |
| `last.pt` | 80 | 0.808 | — |
| `epoch60.pt` | 60 | ~0.811 | Backup |
| `epoch70.pt` | 70 | ~0.813 | Backup |

---

## Đề xuất tiếp theo

1. **Test best.pt** trên video thực tế — so sánh v5 (0.812) vs v5.1 (0.814) xem có thấy khác biệt không
2. **Kiểm tra per-class mAP** — đặc biệt plate_vang/xanh/do sau khi thêm ảnh mới
3. **Thu thập thêm ảnh plate màu** nếu per-class mAP của 3 class này vẫn thấp
4. Nếu muốn cải thiện tiếp: fine-tune thêm 1 lượt với thêm ảnh plate màu chuyên biệt
