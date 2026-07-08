---
task: bbox-batch-add-class
created: 2026-07-08
updated: 2026-07-08 18:36
status: in-progress
workflow: WF-FEATURE (rút gọn — PM/BA/UX đã hoàn thành qua AskUserQuestion)
priority: P2
---

# PLAN: Bổ sung class hàng loạt (Batch Add Class) — BBox Editor Tab

## Mô tả

Thêm tính năng "Bổ sung class hàng loạt" vào tab `BBox Editor (v1)` (`tool/features/annotation/tab_bbox.py`). Tính năng cho phép user chọn model detect + class nguồn, sau đó duyệt toàn bộ thư mục ảnh, detect và APPEND các box mới (đúng class được lọc) vào file label YOLO hiện có — mà không xoá nhãn cũ, không phá vỡ tính năng detect đơn ảnh hiện có.

Có 2 chế độ quét (chốt qua AskUserQuestion lần 2):

1. **Quét toàn bộ (Auto)** — chạy tự động hết toàn bộ ảnh trong thư mục, không dừng lại, ghi thẳng vào file `.txt` từng ảnh, xong thì báo tổng kết.
2. **Quét lần lượt (Review từng ảnh)** — với MỖI ảnh có detect được box mới (sau khi lọc đúng class nguồn): dừng lại, hiển thị ảnh đó + preview box mới (màu khác để phân biệt với box cũ) trên canvas chính, chờ user bấm **"✅ Áp dụng & ảnh tiếp theo"** (ghi append vào file rồi qua ảnh kế) hoặc **"⏭ Bỏ qua"** (không ghi, qua ảnh kế) hoặc **"⏹ Dừng"** (huỷ toàn bộ quá trình quét). Ảnh không có box mới detect được thì tự động bỏ qua (không cần dừng hỏi).

## Nguồn yêu cầu

- Yêu cầu gốc: Chốt qua AskUserQuestion — xem phần "Bối cảnh" trong prompt task-planner.
- Workflow: WF-FEATURE rút gọn — PM/BA/UX hoàn thành bằng Q&A, còn lại: Tech Lead → Senior Developer → Tech Lead (review) → QA Engineer.
- Agent chain: `tech-lead` → `senior-developer` → `tech-lead` (review) → `qa-engineer`

## Scope rõ ràng

- **IN SCOPE:** Chỉ `tool/features/annotation/tab_bbox.py` (BBox Editor v1). Tái dùng `tool/shared/model_infer.py::run_model_predict`, pattern threading/progress hiện có, `_read_yolo`/`_write_yolo` hiện có trong file, cơ chế load model `_browse_det_model`/`_auto_load_det_model`.
- **OUT OF SCOPE:** `tab_bbox2.py`, `tab_yolo.py`, các tab khác. Không thêm IoU dedup (future work). Không sửa `tool/shared/label_io.py` (để nguyên, không bắt buộc refactor sang label_io trong task này).

## Phases & Steps

> **Session isolation (CLAUDE.md §16.5):** Mỗi bước ⬜/🔄 PHẢI chạy tách session — LOCAL dùng `Agent` subagent. Agent tự commit+push+cập nhật plan (status, artifact, thời gian, Handoff Log) trước khi trả về tóm tắt.

### Phase 1: Thiết kế kỹ thuật

| # | Bước | Agent | Status | Artifact | Hoàn thành lúc | Ghi chú |
|---|------|-------|--------|----------|-----------------|---------|
| 1.1 | Đọc code hiện có (`tab_bbox.py`, `model_infer.py`, `_auto_load_det_model`, `_run_detect`, `_write_yolo`, threading pattern), quyết định: (a) model slot dùng chung hay riêng cho batch, (b) cách lấy `.names` cho YOLO/RF-DETR/ONNX, (c) vị trí UI section trong layout (bao gồm 2 nút "Quét toàn bộ"/"Quét lần lượt" + control review "Áp dụng & tiếp theo"/"Bỏ qua"/"Dừng"), (d) luồng threading + progress + cancel cho CẢ 2 chế độ (auto chạy hết trong 1 thread nền; review dừng thread nền tại từng ảnh, đợi callback từ UI thread trước khi resume — cần cơ chế đồng bộ an toàn, ví dụ `threading.Event`/queue), (e) cách vẽ preview box mới (màu riêng) trên canvas ở chế độ review mà không trộn với `self._bboxes` cho tới khi user bấm Áp dụng, (f) cách cập nhật `label_list`/combobox, (g) cách reload canvas nếu ảnh đang mở nằm trong batch (cả 2 chế độ). Viết TDD ngắn gọn. | tech-lead | ✅ | `docs/tech-design/TDD-batch-add-class.md` | 2026-07-08 18:36 | Bước duy nhất Phase 1 |

### Phase 2: Triển khai

| # | Bước | Agent | Status | Artifact | Hoàn thành lúc | Ghi chú |
|---|------|-------|--------|----------|-----------------|---------|
| 2.1 | Code tính năng trong `tab_bbox.py` theo TDD: thêm UI section "➕ Bổ sung class hàng loạt" (LabelFrame riêng), slot model batch, dropdown class model, ô label đích, 2 nút chế độ quét ("🔍 Quét toàn bộ" / "🔍 Quét lần lượt"), 3 nút điều khiển review ("✅ Áp dụng & tiếp theo" / "⏭ Bỏ qua" / "⏹ Dừng", ẩn/hiện tuỳ chế độ), progress bar/label, threading batch detect (đồng bộ đúng giữa thread nền và UI thread ở chế độ review), append label, cập nhật label_list, reload canvas nếu ảnh đang mở. Tái dùng tối đa code hiện có theo đúng TDD. PR description đầy đủ. | senior-developer | ⬜ | `tool/features/annotation/tab_bbox.py` (đã sửa) | - | KHÔNG sửa tab_bbox2.py |

### Phase 3: Review & QA

| # | Bước | Agent | Status | Artifact | Hoàn thành lúc | Ghi chú |
|---|------|-------|--------|----------|-----------------|---------|
| 3.1 | Review code bước 2.1: kiểm tra tái dùng đúng, không copy-paste logic load model, threading an toàn (no race condition với tính năng detect đơn ảnh, đặc biệt cơ chế đợi/resume ở chế độ review không bị deadlock hoặc treo UI), `_write_yolo` không làm hỏng dòng OBB 9-token, reload canvas đúng, nút "⏹ Dừng" huỷ đúng giữa chừng không rò rỉ thread. Approve hoặc yêu cầu sửa (nếu sửa → vòng lại Senior Dev trước khi QA). | tech-lead | ⬜ | Review comment / approved | - | |
| 3.2 | Chạy app thật (`python app.py` hoặc entrypoint đúng tại `d:\Tool`), test smoke: (1) load model YOLO (vd `yolo11n.pt`), chọn class `person`, "Quét toàn bộ" trên bộ ảnh có label .txt sẵn → verify .txt được append đúng, không mất nhãn cũ; (2) "Quét lần lượt" trên cùng bộ ảnh → verify dừng đúng ở từng ảnh có box mới, preview hiển thị đúng, "Áp dụng & tiếp theo"/"Bỏ qua"/"Dừng" hoạt động đúng; (3) mở ảnh đang trong batch → verify canvas reload đúng sau khi batch xong; (4) detect đơn ảnh vẫn hoạt động bình thường. Ghi log kết quả smoke test nhúng vào artifact. | qa-engineer | ⬜ | `docs/test-cases/TC-bbox-batch-add-class.md` | - | Chạy app thật — KHÔNG mock |

## Handoff Log (BẮT BUỘC — xem CLAUDE.md §16.5 Bước 4)

> Mỗi bước chạy session/subagent riêng nên KHÔNG thấy lịch sử bước trước. Agent hoàn thành bước PHẢI thêm 1 entry dưới đây; task-planner PHẢI nhúng nguyên văn mục này vào prompt của bước kế tiếp — tránh đọc lại/nghiên cứu lại.

<!-- Thêm entry mới ở cuối, KHÔNG xoá entry cũ -->

### Bước 1.1 — Thiết kế kỹ thuật TDD

- **Đã làm:** Đọc `tab_bbox.py` (khoảng ~1600 dòng liên quan), `tool/shared/model_infer.py`, `tool/features/detection/yolo_onnx.py`, `tool/core/ui_helpers.py`. Viết TDD `docs/tech-design/TDD-batch-add-class.md` chốt 9 quyết định (a)-(i) + pseudocode threading + preview overlay + task breakdown cho Senior Dev (10 sub-task ước tính ~4h30) + mermaid sequence diagram.
- **File/module đã đọc hoặc đổi:**
  - Đọc: `tool/features/annotation/tab_bbox.py` (dòng 1-300, 470-620, 750-830, 880-990, 1023-1350, 1859-1880, 2321-2420, 3080-3700), `tool/shared/model_infer.py` (toàn bộ), `tool/features/detection/yolo_onnx.py` (dòng 1-80), `tool/core/ui_helpers.py` (dòng 360-390).
  - Tạo: `docs/tech-design/TDD-batch-add-class.md` + `.docx` + `.pdf`.
- **Quyết định quan trọng (đóng lại — Senior Dev KHÔNG cần suy luận lại):**
  1. **Model slot:** DÙNG CHUNG `self._det_model` — không tạo slot riêng. Refresh dropdown class khi `_on_det_model_loaded` chạy xong.
  2. **Nguồn class:** CHỈ dùng `self._det_model_names` (dict). YOLO Ultralytics có. RF-DETR có thể có. ONNX (`_OnnxRunner`) có `names={}` rỗng → **disable nút quét khi rỗng**, hiển thị lý do trên status. KHÔNG cho user nhập tay class_id.
  3. **UI:** 1 `LabelFrame` mới trong `center`, đặt SAU `rl_tb` (Batch Relabel, dòng ~594-621) và TRƯỚC `self._attr_bar` (dòng ~624). Row 1 = class nguồn + label đích + 3 nút (Quét toàn bộ, Quét lần lượt, Dừng). Row 2 = progressbar (`K.Horizontal.TProgressbar` có sẵn) + status. Row 3 = 2 nút Review (Áp dụng, Bỏ qua) — pack_forget/pack theo state.
  4. **Threading:** 1 daemon thread duy nhất chạy vòng `for fp in self.image_files`, dùng 2 `threading.Event` — `_batch_cancel_evt` (Dừng) và `_batch_review_evt` (chờ user review). Mọi update UI qua `self.root.after(0, ...)` giống pattern `_run_detect`/`_load_det_model`.
  5. **Preview:** `self._batch_preview_boxes` + `self._batch_preview_active` (2 biến state MỚI). Hàm `_draw_batch_preview_overlay()` bám pattern `_draw_zoomtest_overlay` (dòng ~3671-3692), tag `"batch_preview_item"`, màu `#F05922` đứt nét `dash=(8,4)`. Chèn vào `_render()` (dòng 1250) và `_redraw_bboxes_only()` (dòng 1313).
  6. **Label list:** Nếu `dst_label` chưa có → append vào `self.label_list`, update `self._labels_var` (comma-join), refresh 7 chỗ dùng `label_list`: `_cls_lb`, `_cls_combo`, `_filter_label_combo`, `_rl_from_combo`, `_rl_to_combo`, `_must_have_lb`, `_must_not_lb`. Refactor thành hàm `_refresh_label_widgets()` để tái dùng.
  7. **Reload ảnh:** Sau MỖI ghi file trong worker, `root.after(0, _batch_maybe_reload_current, fp)`; nếu `image_files[current_idx] == fp` → set `_modified=False` + `_load_image(current_idx)` để đồng bộ. Trước khi start batch, phải `_autosave()` ảnh đang mở.
  8. **Helper mới:** `_read_yolo_ext(path, iw, ih)` và `_write_yolo_ext(path, bboxes, iw, ih)` — bản explicit của `_read_yolo`/`_write_yolo`, không phụ thuộc `self._pil_img`/`self._bboxes`. GIỮ NGUYÊN logic 5-token / 9-token (poly4) — không phá dòng OBB khi merge box 5-token mới vào file có 9-token cũ.
  9. **Names hàm/method (17 method + 8 biến state — CHỐT tên, xem bảng ở TDD mục 3(h)):** `_build_batch_add_class_ui`, `_refresh_batch_class_combo`, `_refresh_label_widgets`, `_batch_start_auto/review`, `_batch_worker`, `_batch_show_review`, `_batch_review_apply/skip`, `_batch_stop`, `_batch_hide_review_ui`, `_batch_update_progress`, `_batch_maybe_reload_current`, `_batch_finish`, `_resolve_lbl_path`, `_read_yolo_ext`, `_write_yolo_ext`, `_draw_batch_preview_overlay`.
- **Bước sau cần biết:**
  - **KHÔNG cần đọc lại `tab_bbox.py` từ đầu** — TDD đã liệt kê từng số dòng tham chiếu. Senior Dev chỉ cần đọc TDD + jump tới đúng vị trí đã ghi (VD: layout dòng 594-624, `_render` dòng 1211-1250, `_write_yolo` dòng 1105-1124, `_load_image` dòng 1023-1078, `_on_det_model_loaded` dòng 3287-3300).
  - `_write_yolo` hiện tại phụ thuộc `self._pil_img.size` + `self._bboxes` → KHÔNG dùng trực tiếp trong worker. Phải viết bản `_write_yolo_ext(path, bboxes, iw, ih)` mới (Senior Dev có thể copy logic hiện có + thay 2 nguồn dữ liệu).
  - `_OnnxRunner.names = {}` (dòng 32 của `yolo_onnx.py`) — hard-coded rỗng. Nếu về sau muốn hỗ trợ ONNX cần bổ sung metadata riêng — ngoài scope task này.
  - Task breakdown Phase 2 chi tiết ~4h30 công (10 sub-task) — xem mục 5 của TDD.
  - Commit hash bước 1.1: `0eb85ff` (chưa push).

## Artifacts dự kiến

- [ ] `docs/tech-design/TDD-batch-add-class.md` — Technical Design Doc (+ .docx + .pdf)
- [ ] `tool/features/annotation/tab_bbox.py` — đã thêm tính năng batch add class
- [ ] `docs/test-cases/TC-bbox-batch-add-class.md` — Smoke test log + kết quả QA

## Blockers

Không có

## Quyết định / Ghi chú

- PM/BA/UX scope đã được xác nhận qua AskUserQuestion — coi như AC đã chốt, không cần thêm agent product-manager/business-analyst/ui-ux-designer.
- IoU dedup KHÔNG cần implement trong bản đầu — ghi "future work" trong code nếu Tech Lead thấy phù hợp.
- Chỉ áp dụng cho `tab_bbox.py` (BBox Editor v1), KHÔNG sửa `tab_bbox2.py`.
- UX/UI Reviewer KHÔNG cần thiết trong plan này — user đã xác nhận scope UI qua Q&A (layout: thêm LabelFrame riêng cuối tab, không redesign tab). Nếu Tech Lead thấy UI phức tạp hơn dự kiến sau khi thiết kế → có thể thêm bước UXR vào Phase 3 trước QA.
- Quy tắc §20 CLAUDE.md (WinForms/KztekComponent) KHÔNG áp dụng — project Python/Tkinter.

## Lịch sử cập nhật

| Ngày | Cập nhật | Agent |
|------|----------|-------|
| 2026-07-08 | Plan tạo mới | task-planner |
| 2026-07-08 | Bổ sung yêu cầu 2 chế độ quét: "Quét toàn bộ" (auto) và "Quét lần lượt" (dừng lại từng ảnh để review/áp dụng/bỏ qua/dừng), cập nhật bước 1.1/2.1/3.1/3.2 tương ứng | dispatcher |
| 2026-07-08 18:36 | Bước 1.1 hoàn thành — TDD `docs/tech-design/TDD-batch-add-class.md` (+ .docx + .pdf) chốt (a)-(i) + task breakdown Phase 2. Commit 0eb85ff (chưa push). Status plan: planning → in-progress | tech-lead |

---
**Status icons:** ⬜ Todo | 🔄 In Progress | ✅ Done | 🛑 Blocked | ⏭️ Skipped
