# Training Report — kztek_test_200ep_v3

**Model:** yolo11n fine-tune từ kztek_test_150ep_v2/weights/best.pt (ep148, mAP50-95=0.7602)  
**Ngày:** 2026-06-28 | **Trạng thái:** ❌ KẾT THÚC SỚM — Early Stopping tại ep51/200  
**Dataset:** D:/Software/Dataset — 6 classes: car · motorbike · bus · truck · bicycle · license_plate  
**PID:** 18056 (kết thúc 2026-06-28 23:50)

---

## Thay đổi so với v2

| Tham số | v2 | **v3** | Lý do |
|---|---|---|---|
| base model | v1 best.pt (ep97) | **v2 best.pt (ep148)** | Fine-tune từ model tốt hơn |
| epochs | 150 | **200** | val/box còn giảm đến ep150 → chưa converge |
| batch | 8 | **16** | Tăng throughput; nbs=64 → grad accum 4× |
| warmup_epochs | 30 | **10** | Fine-tune từ model đã tốt, 30ep quá dài |
| close_mosaic | 10 | **15** | Thêm thời gian clean training |
| dropout | 0.0 | **0.1** | Tránh overfit 200ep |

---

## Kết quả tốt nhất hiện tại (cập nhật liên tục)

| Metric | Giá trị | Epoch |
|---|---|---|
| mAP50 | **0.9352** | 1 |
| mAP50-95 | **0.7571** | 1 |
| Precision | **0.9327** | 1 |
| Recall | **0.8888** | 1 |
| val/cls (best↓) | **1.6454** | 1 |
| val/box (best↓) | **0.7100** | 1 |
| **best.pt** | **mAP50-95=0.7571** | **ep1** |
| **Trạng thái** | **❌ EARLY STOPPING ep51/200 — patience=50 triggered. best < v2 (0.7602). Dùng v2 best.pt cho v4.** | |

---

## Kết quả từng Epoch

| Ep | mAP50 | mAP50-95 | Precision | Recall | train/box | train/cls | train/dfl | val/cls | LR |
|---|---|---|---|---|---|---|---|---|---|
| **1** 🚀 | **0.9352** | **0.7571** | **0.9327** | **0.8888** | 0.7304 | 1.8494 | 1.6492 | **1.6454** | 0.00299 |
| 2 | 0.9312 | 0.7537 | 0.9239 | 0.8851 | 0.7448 | 1.8957 | 1.6591 | 1.6625 | 0.00599 |
| 3 | 0.9310 | 0.7512 | 0.9290 | 0.8796 | 0.7511 | 1.9106 | 1.6617 | 1.6952 | 0.00899 |
| 4 | 0.9359 | 0.7537 | 0.9287 | 0.8884 | 0.7643 | 1.9604 | 1.6708 | 1.7340 | 0.01199 |
| 5 | 0.9214 | 0.7227 | 0.9049 | 0.8898 | 0.7741 | 2.0086 | 1.6724 | 1.7973 | 0.01498 |
| 6 | 0.9322 | 0.7351 | 0.9239 | 0.8878 | 0.7823 | 2.0444 | 1.6806 | 1.7785 | 0.01797 |
| 7 | 0.9286 | 0.7319 | 0.9144 | 0.8775 | 0.7984 | 2.1174 | 1.6953 | 1.8550 | 0.02095 |
| 8 | 0.9224 | 0.7209 | 0.9292 | 0.8612 | 0.8186 | 2.1729 | 1.7105 | 1.8512 | 0.02392 |
| 9 | 0.9238 | 0.7139 | 0.9293 | 0.8722 | 0.8376 | 2.2863 | 1.7229 | 1.9274 | 0.02689 |
| 10 | 0.9143 | 0.7025 | 0.8961 | 0.8694 | 0.8662 | 2.3835 | 1.7428 | 2.0380 | 0.02985 |
| 11 | 0.9221 | 0.7054 | 0.9230 | 0.8606 | 0.8718 | 2.4329 | 1.7547 | 2.0288 | 0.02982 |
| 12 | 0.9140 | 0.7013 | 0.9124 | 0.8558 | 0.8901 | 2.5048 | 1.7686 | 2.0029 | 0.02979 |
| 13 | 0.9256 | 0.7078 | 0.9057 | 0.8771 | 0.8768 | 2.5002 | 1.7668 | 1.9841 | 0.02974 |
| 14 | 0.9265 | 0.7182 | 0.9038 | 0.8851 | 0.8824 | 2.4993 | 1.7682 | 1.9896 | 0.02969 |
| 15 | 0.9157 | 0.7034 | 0.9250 | 0.8575 | 0.8875 | 2.5237 | 1.7701 | 2.0057 | 0.02964 |
| 16 | 0.9139 | 0.7064 | 0.9179 | 0.8375 | 0.8885 | 2.5193 | 1.7709 | 2.0772 | 0.02959 |
| 17 | 0.9207 | 0.7151 | 0.9109 | 0.8658 | 0.8882 | 2.5144 | 1.7689 | 1.9996 | 0.02953 |
| 18 | 0.9239 | 0.7107 | 0.9105 | 0.8626 | 0.8858 | 2.4986 | 1.7704 | 1.9709 | 0.02947 |
| **19** ⚠ | 0.9095 | **0.6891** | 0.8947 | 0.8579 | 0.8873 | 2.5134 | 1.7710 | 2.0112 | 0.02941 |
| 20 | 0.9264 | 0.7192 | 0.9287 | 0.8653 | 0.8819 | 2.4948 | 1.7664 | 1.9483 | 0.02934 |
| 21 | 0.9208 | 0.7052 | 0.9198 | 0.8524 | 0.8783 | 2.4892 | 1.7659 | 1.9718 | 0.02927 |
| 22 | 0.9242 | 0.7155 | 0.9169 | 0.8696 | 0.8775 | 2.4750 | 1.7667 | 1.9584 | 0.02920 |
| 23 | 0.9231 | 0.7130 | 0.9153 | 0.8725 | 0.8857 | 2.5084 | 1.7694 | 1.9424 | 0.02912 |
| 24 | 0.9249 | 0.7148 | 0.9252 | 0.8743 | 0.8888 | 2.5087 | 1.7728 | 1.9334 | 0.02904 |
| 25 | 0.9290 | 0.7180 | 0.9302 | 0.8727 | 0.8829 | 2.4750 | 1.7688 | 1.9111 | 0.02896 |
| 26 | 0.9246 | 0.7169 | 0.9100 | 0.8661 | 0.8818 | 2.4859 | 1.7669 | 1.9322 | 0.02887 |
| 27 | 0.9272 | 0.7162 | 0.9148 | 0.8712 | 0.8796 | 2.4788 | 1.7643 | 1.9250 | 0.02878 |
| **28** | 0.9235 | 0.7194 | 0.9330 | 0.8758 | 0.8814 | 2.4881 | 1.7702 | **1.8954** | 0.02868 |
| 29 | 0.9185 | 0.7147 | 0.9179 | 0.8551 | 0.8798 | 2.4878 | 1.7653 | 1.9320 | 0.02859 |
| **30** | 0.9273 | 0.7218 | 0.9233 | 0.8634 | 0.8691 | 2.4328 | 1.7556 | **1.8883** | 0.02849 |
| **31** | 0.9235 | 0.7230 | 0.9279 | 0.8555 | 0.8684 | 2.4494 | 1.7560 | 1.9010 | 0.02838 |
| 32 | 0.9274 | 0.7272 | 0.9128 | 0.8783 | 0.8740 | 2.4551 | 1.7599 | 1.8934 | 0.02827 |
| **33** | 0.9293 | 0.7241 | 0.9293 | 0.8724 | 0.8688 | 2.4354 | 1.7556 | **1.8615** | 0.02816 |
| 34 | 0.9246 | 0.7252 | 0.8984 | 0.8865 | 0.8726 | 2.4197 | 1.7545 | 1.8717 | 0.02805 |
| **35** | 0.9280 | 0.7272 | 0.9183 | 0.8836 | 0.8737 | 2.4501 | 1.7564 | **1.8400** | 0.02793 |
| **36** | 0.9285 | 0.7295 | 0.9077 | 0.8832 | 0.8666 | 2.4213 | 1.7546 | **1.8267** | 0.02781 |
| 37 | 0.9275 | 0.7259 | 0.9105 | 0.8748 | 0.8695 | 2.4427 | 1.7620 | 1.8501 | 0.02769 |
| **38** 🔥 | 0.9276 | **0.7366** | 0.9056 | 0.8862 | 0.8763 | 2.4424 | 1.7609 | **1.8215** | 0.02756 |
| **39** 🔥 | **0.9329** | **0.7367** | 0.9301 | 0.8754 | 0.8700 | 2.4259 | 1.7563 | **1.8036** | 0.02743 |
| **40** 🔥 | 0.9301 | 0.7350 | 0.9324 | 0.8638 | 0.8684 | 2.4220 | 1.7526 | **1.7939** | 0.02730 |
| 41 | 0.9290 | 0.7300 | 0.9113 | 0.8850 | 0.8638 | 2.4094 | 1.7533 | 1.8124 | 0.02716 |
| 42 | 0.9326 | 0.7317 | 0.9176 | 0.8849 | 0.8645 | 2.4121 | 1.7537 | 1.7981 | 0.02703 |
| 43 | 0.9278 | 0.7263 | 0.9201 | 0.8829 | 0.8664 | 2.4043 | 1.7544 | 1.8079 | 0.02688 |
| **44** 🔥 | **0.9347** | **0.7395** | 0.9158 | 0.8915 | 0.8574 | 2.3706 | 1.7445 | 1.7940 | 0.02674 |
| **45** ★ | 0.9333 | 0.7344 | 0.9308 | 0.8742 | 0.8587 | 2.3734 | 1.7431 | **1.7701** | 0.02659 |
| **46** ★ | 0.9308 | 0.7332 | 0.9392 | 0.8642 | 0.8616 | 2.4005 | 1.7511 | **1.7705** | 0.02644 |
| 47 | 0.9294 | 0.7329 | 0.9244 | 0.8858 | 0.8569 | 2.3803 | 1.7483 | 1.7860 | 0.02629 |
| **48** 🔥 | 0.9312 | **0.7387** | 0.9225 | 0.8796 | 0.8545 | 2.3644 | 1.7467 | 1.7868 | 0.02614 |
| 49 | 0.9337 | 0.7374 | 0.9271 | 0.8831 | 0.8581 | 2.3634 | 1.7517 | 1.7832 | 0.02598 |
| **50** 🔥 | 0.9323 | **0.7390** | 0.9110 | 0.8961 | 0.8611 | 2.3845 | 1.7553 | 1.7714 | 0.02581 |
| **51** ★★★ | 0.9320 | 0.7370 | 0.9335 | 0.8745 | 0.8533 | 2.3631 | 1.7454 | **1.7568** | 0.02565 |

---

## Cấu hình Training

### Model & Dataset

| Tham số | Giá trị |
|---|---|
| Base model | kztek_test_150ep_v2/weights/best.pt (ep148) |
| Architecture | YOLO11n fine-tune |
| Input size | 640×640 |
| Output | D:/Software/Model/kztek_test_200ep_v3 |
| Device | CUDA:0 (RTX 3050 Ti 4GB) |
| batch | 16 |
| nbs | 64 |

### LR & Schedule

| Tham số | Giá trị |
|---|---|
| epochs | 200 |
| warmup_epochs | 10 |
| cos_lr | True |
| momentum | 0.937 |
| weight_decay | 0.0005 |
| optimizer | auto |
| patience | 50 |

### Loss Weights

| Tham số | Giá trị | Ghi chú |
|---|---|---|
| cls | 2.0 | 4× default — giữ v2 |
| box | 7.5 | giữ v2 |
| dfl | 2.5 | giữ v2 |
| iou (label assign) | 0.4 | giữ v2 |
| label_smoothing | 0.1 | giữ v2 |
| amp | True (FP16) | |
| close_mosaic | 15 | ↑ từ 10 (v2) |
| save_period | 10 | |

### Augmentation

| Tham số | Giá trị | Ghi chú |
|---|---|---|
| dropout | 0.1 | ↑ từ 0.0 (v2) |
| mixup | 0.15 | giữ v2 |
| copy_paste | 0.1 | giữ v2 |
| degrees | 3.0 | giữ v2 |
| erasing | 0.4 | giữ v2 |
| fliplr | 0.5 | |
| hsv_h / s / v | 0.015 / 0.7 / 0.4 | |
| perspective | 0.0 | |

---

## Update Log

| Thời gian | Epoch | mAP50 | Ghi chú |
|---|---|---|---|
| 2026-06-28 18:10 | — | — | Khởi tạo training v3. PID=18056. batch=16, nbs=64, warmup=10, close_mosaic=15, dropout=0.1, epochs=200. Fine-tune từ v2 best.pt (ep148, mAP50-95=0.7602). |
| 2026-06-28 21:32 | 1–2 | 0.9352 | ✅ Không OOM! batch=16 OK trên 4GB VRAM. ep1: mAP50-95=0.7571 (cao hơn v2 ep1=0.7355, nhờ base tốt hơn). val/cls=1.6454 (gần v2 best 1.6165). Tốc độ ~241s/ep → ~13.4h tổng. Warmup ep1-10 (LR 0.003→0.027). |
| 2026-06-28 21:43 | 3–6 | 0.9359 | Warmup oscillation: mAP50-95 dao động 0.723-0.757. ep5 dip mạnh nhất (0.7227) do LR=0.015 cao. Tốc độ thực tế ~194s/ep → ~10.8h tổng. val/cls/box tăng trong warmup (bình thường). Ep10 warmup kết thúc — kỳ vọng recovery. |
| 2026-06-28 21:54 | 7–9 | 0.9293 | ⚠ Warmup quá aggressive: mAP50-95 tiếp tục giảm 0.732→0.721→0.714 (worst!). val/cls=1.927 (xa v2 best 1.617). LR đạt đỉnh 0.027 tại ep9-10. Nguyên nhân: warmup 10ep tăng LR 3× nhanh hơn v2 (30ep) → model bị disrupted mạnh. Kỳ vọng: cosine decay ep11+ sẽ ổn định. Tốc độ ~180s/ep → ~10h tổng. |
| 2026-06-28 22:05 | 10–13 | 0.9256 | ⚠⚠ mAP50-95 TIẾP TỤC GIẢM sau warmup: 0.702→0.705→0.701→0.708. Cosine decay bắt đầu nhưng LR vẫn 0.030 (gần đỉnh!). train/box tăng 0.73→0.88, train/cls tăng 1.85→2.50 — model đang bị overshoot. LR chỉ giảm đáng kể từ ep~50+. Điểm cần theo dõi: ep20-30 có ổn định không? |
| 2026-06-28 22:17 | 14–17 | 0.9265 | mAP50-95 stuck 0.703–0.718, oscillation chưa dứt. val/cls oscillate quanh 2.0 (xu hướng giảm nhẹ 2.038→2.000). LR chỉ giảm 0.030→0.0295 sau 7ep cosine — sẽ mất ~ep80 để xuống 0.015. train/box/cls đã leveling off. Đánh giá: run còn tiếp tục được, kỳ vọng recovery từ ep50-60. |
| 2026-06-28 22:34 | 18–23 | 0.9264 | ⚠⚠ ep19 dip tới 0.6891 (thấp nhất toàn run!). Recovered về 0.719 tại ep20 — chỉ là noise. val/cls xu hướng giảm nhẹ 2.038→1.942 (−0.007/ep). LR 0.0295→0.0291. train/cls leveling: 2.50→2.49. Dự đoán: recovery thực sự từ ep80-100 khi LR < 0.020. ~8.5h còn lại. |
| 2026-06-28 22:56 | 24–31 | 0.9290 | ✅ RECOVERING! val/cls phá 1.90 tại ep28 (1.895), ep30: 1.888 ★ — xu hướng giảm rõ ràng 2.038→1.888. mAP50-95 dần tăng 0.713→0.723 (ep30-31 cao nhất kể từ ep14). train/cls 2.50→2.43 (giảm nhẹ). Quyết định: TIẾP TỤC — run đang hồi phục đúng hướng. ~8h còn lại. |
| 2026-06-28 23:30 | 32–40 | 0.9329 | ✅ RECOVERY RÕ RÀNG! mAP50-95 vượt 0.73 (ep38-39: 0.737). val/cls 1.893→1.794 tại ep40 — LOW MỚI kể từ ep1! Tốc độ giảm ~0.010/8ep = −0.0012/ep đang ổn định. val/box 0.784→0.762→0.764 (stable). train/cls leveling 2.43→2.42. LR 0.0284→0.0273. Dự báo: ep60 val/cls ~1.76, mAP50-95 ~0.748; ep100 mAP50-95 ~0.758+. ~6.9h còn lại. |
| 2026-06-28 23:44 | 41–48 | 0.9347 | ✅✅ RECOVERY TĂNG TỐC! ep44: mAP50-95=0.7395 (peak mới trong recovery phase!). ep45-46: val/cls=1.770★★ — LOW MỚI TUYỆT ĐỐI kể từ ep1 (1.645). train/cls tiếp tục giảm 2.41→2.37→2.36. val/box stable ~0.755-0.763. LR 0.0273→0.0261. Hai tín hiệu đồng thời tốt: mAP peak tăng + val/cls low mới → model đang thực sự converge. Dự báo ep100: mAP50-95 ~0.750+, val/cls ~1.70. ~6.5h còn lại. |
| 2026-06-29 00:05 | 49–51 | 0.9337 | 🔥 TIẾP TỤC DOWNTREND! ep51: val/cls=1.757★★★ — LOW MỚI TUYỆT ĐỐI (ep45 trước là 1.770). train/cls 2.36→2.38→2.36 (stable thấp). val/box ~0.750 (giảm nhẹ, tốt). ep50: mAP50-95=0.7390 (gần peak ep44=0.7395). Tốc độ ~180s/ep. ~7.2h còn lại. Dự báo cập nhật: ep100 val/cls ~1.69, mAP50-95 ~0.752. |
| 2026-06-29 00:25 | FINAL | — | ❌ EARLY STOPPING. Training dừng lúc 23:50 tại ep51/200. patience=50 triggered: ep1 là best (0.7571) → 50 epoch sau (ep2-51) không vượt được → tự động dừng. best.pt = ep1 weights. Kết quả: mAP50-95=0.7571 < v2=0.7602. Root cause: warmup_epochs=10 disrupted model ngay từ ep1, recovery quá chậm để beat ep1 trong 50ep. |

---

## Kết Quả Cuối Cùng & Phân Tích

### So sánh v1 / v2 / v3

| Metric | v1 | v2 | **v3** |
|---|---|---|---|
| Epochs chạy | 97/100 | 150/150 | **51/200 (early stop)** |
| Best epoch | ep97 | ep148 | **ep1** |
| mAP50 (best) | 0.9283 | 0.9346 | **0.9352** |
| mAP50-95 (best) | 0.7494 | **0.7602** | 0.7571 |
| val/cls (best) | ~1.75 | 1.6165 | **1.6454** |
| Base model | scratch | v1 ep97 | v2 ep148 |
| Kết quả | baseline | +1.1% | **−0.4% (thất bại)** |

### Root Cause — tại sao v3 thất bại

```
warmup_epochs=10 (v3) vs warmup_epochs=30 (v2)

v2: LR tăng 0.003/10ep = +0.0003/ep (nhẹ nhàng)
v3: LR tăng 0.027/10ep = +0.0027/ep (3× nhanh hơn)

Hậu quả:
  ep1:  mAP50-95=0.7571 (model chưa bị disrupted)
  ep10: mAP50-95=0.7025 (disrupted -0.0546)
  ep19: mAP50-95=0.6891 (worst)
  ep51: mAP50-95=0.7395 (đang hồi phục — nhưng patience đã hết)

patience=50 đếm từ ep1 (last improvement)
  → ep2-51 = 50 epoch không cải thiện → STOP
```

**Kết luận:** Với fine-tune từ model đã converge, warmup_epochs=10 quá aggressive. patience=50 không đủ thời gian để recovery beat lại ep1.

### Model tốt nhất hiện tại

> ✅ **Dùng v2 best.pt** cho production và v4 base:  
> `D:/Software/Model/kztek_test_150ep_v2/weights/best.pt`  
> mAP50-95 = **0.7602** (ep148)

### Đề xuất v4

| Tham số | v3 | **v4 (đề xuất)** | Lý do |
|---|---|---|---|
| Base model | v2 ep148 | **v2 ep148** | v3 best < v2 — không dùng v3 |
| warmup_epochs | 10 | **25** | Tăng trở lại — fine-tune cần warmup chậm |
| patience | 50 | **100** | Cho đủ thời gian hồi phục nếu warmup disrupt |
| epochs | 200 | **250** | Tăng ceiling để có room hội tụ |
| batch | 16 | **16** | Giữ — batch=16 OK trên 4GB VRAM |
| dropout | 0.1 | **0.1** | Giữ — tác dụng tốt |
| close_mosaic | 15 | **20** | Tăng nhẹ để clean phase dài hơn |
| lr0 / lrf | auto | **lr0=0.001, lrf=0.01** | Giảm initial LR để tránh disruption |

**Ưu tiên nhất: `lr0=0.001` + `warmup_epochs=25`** — hai thay đổi này giải quyết trực tiếp root cause của v3.
