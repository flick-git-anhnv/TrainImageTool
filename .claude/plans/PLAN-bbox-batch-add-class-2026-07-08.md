---
task: bbox-batch-add-class
created: 2026-07-08
updated: 2026-07-08 21:41
status: completed
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
| 2.1 | Code tính năng trong `tab_bbox.py` theo TDD: thêm UI section "➕ Bổ sung class hàng loạt" (LabelFrame riêng), slot model batch, dropdown class model, ô label đích, 2 nút chế độ quét ("🔍 Quét toàn bộ" / "🔍 Quét lần lượt"), 3 nút điều khiển review ("✅ Áp dụng & tiếp theo" / "⏭ Bỏ qua" / "⏹ Dừng", ẩn/hiện tuỳ chế độ), progress bar/label, threading batch detect (đồng bộ đúng giữa thread nền và UI thread ở chế độ review), append label, cập nhật label_list, reload canvas nếu ảnh đang mở. Tái dùng tối đa code hiện có theo đúng TDD. PR description đầy đủ. | senior-developer | ✅ | `tool/features/annotation/tab_bbox.py` (commit e6b1f73) | 2026-07-08 19:25 | KHÔNG sửa tab_bbox2.py |

### Phase 3: Review & QA

| # | Bước | Agent | Status | Artifact | Hoàn thành lúc | Ghi chú |
|---|------|-------|--------|----------|-----------------|---------|
| 3.1 | Review code bước 2.1: kiểm tra tái dùng đúng, không copy-paste logic load model, threading an toàn (no race condition với tính năng detect đơn ảnh, đặc biệt cơ chế đợi/resume ở chế độ review không bị deadlock hoặc treo UI), `_write_yolo` không làm hỏng dòng OBB 9-token, reload canvas đúng, nút "⏹ Dừng" huỷ đúng giữa chừng không rò rỉ thread. Approve hoặc yêu cầu sửa (nếu sửa → vòng lại Senior Dev trước khi QA). | tech-lead | ✅ | **APPROVED** — commit e6b1f73 sẵn sàng QA. Không có blocker, chỉ 1 minor UX note (xem Handoff Log). | 2026-07-08 19:29 | Không cần vòng lại Senior Dev |
| 3.2 | Chạy app thật (`python app.py` hoặc entrypoint đúng tại `d:\Tool`), test smoke: (1) load model YOLO (vd `yolo11n.pt`), chọn class `person`, "Quét toàn bộ" trên bộ ảnh có label .txt sẵn → verify .txt được append đúng, không mất nhãn cũ; (2) "Quét lần lượt" trên cùng bộ ảnh → verify dừng đúng ở từng ảnh có box mới, preview hiển thị đúng, "Áp dụng & tiếp theo"/"Bỏ qua"/"Dừng" hoạt động đúng; (3) mở ảnh đang trong batch → verify canvas reload đúng sau khi batch xong; (4) detect đơn ảnh vẫn hoạt động bình thường. Ghi log kết quả smoke test nhúng vào artifact. | qa-engineer | ✅ | `docs/test-cases/TC-bbox-batch-add-class.md` (.docx ✅, .pdf ⚠️ RPC) | 2026-07-08 20:15 | Code-level test (agent headless). 20 PASS / 1 SKIP (GUI). Bug P3 ghi nhận. QA PASS. Commit fe7a1ec |

### Phase 4: Amendment — Model picker trong khung Batch + Import từ thư mục label có sẵn + Chế độ Thay thế/Chỉ thêm

> User phản hồi sau khi Phase 1-3 đã QA PASS (2026-07-08 20:40): (1) ô chọn model nằm tách rời khung "Bổ sung class hàng loạt" nên dễ bỏ sót; (2) cần thêm 1 nguồn nhãn mới KHÔNG qua model detect — đọc trực tiếp từ 1 thư mục label đã có sẵn (chỉ chứa nhãn class mới, ví dụ xuất từ nơi khác) rồi ghép vào file label tương ứng theo tên ảnh.

**Yêu cầu đã chốt qua AskUserQuestion (vòng 3):**

1. **Model picker tiện dụng:** Thêm 1 dòng trong khung Batch hiển thị tên model đang dùng (đồng bộ với `self._det_model_path`/`self._det_combo` đã có ở hàng "🤖 Model:" phía trên) + nút "📂 Đổi model" gọi lại `_browse_det_model` hiện có. KHÔNG tạo biến model mới — vẫn dùng chung `self._det_model`.
2. **Nguồn nhãn mới — 2 chế độ (radio/toggle), thêm SONG SONG với chế độ hiện có (không xoá chế độ cũ):**
   - **"🤖 Model detect"** (mặc định, hành vi hiện có — giữ nguyên).
   - **"📁 Thư mục label có sẵn"** (MỚI): hiện 1 `_folder_row`-style picker "Thư mục label nguồn:" (giống pattern `img_dir_var`/`lbl_dir_var`). Khi chọn chế độ này: ẩn dropdown "Class nguồn (model)", thay bằng 1 ô nhập "Class id nguồn (vd: 0 hoặc 0,2,5)" — cho phép nhập 1 HOẶC NHIỀU class_id (phân tách bằng dấu phẩy), ĐỀU map chung vào 1 "Nhãn đích" duy nhất (giữ nguyên field "Nhãn đích" hiện có, không thêm mapping nhiều-nhãn trong bản này — nếu cần map khác nhãn thì chạy lại thao tác với id khác).
   - Khi ở chế độ "Thư mục label có sẵn": với mỗi ảnh trong `img_dir_var` (tôn trọng `self.v_recursive` giống hệt cách match ảnh↔label hiện tại), tìm file label TƯƠNG ỨNG trong thư mục nguồn mới (match theo tên file/stem, đúng logic `_resolve_lbl_path` nhưng trỏ vào thư mục nguồn thay vì `lbl_dir_var`). Đọc TẤT CẢ dòng có `class_id` nằm trong tập id đã nhập (dùng đọc normalized trực tiếp — KHÔNG cần mở ảnh để quy đổi vì cả nguồn và đích đều là toạ độ normalized 0-1, chỉ cần đổi `class_id`). Ảnh không có file nguồn tương ứng → bỏ qua (không lỗi).
   - **CẢ 2 chế độ (model detect / thư mục label) đều dùng chung logic "Quét toàn bộ" / "Quét lần lượt" (preview, review Áp dụng/Bỏ qua/Dừng) đã có — không tạo luồng threading riêng, chỉ khác bước "lấy box mới" (detect model vs đọc file).**
3. **Chế độ ghi — áp dụng cho CẢ 2 nguồn (model detect và thư mục label), thêm 1 radio/checkbox mới:**
   - **"Chỉ thêm (append)"** — mặc định, hành vi hiện có, giữ nguyên.
   - **"Thay thế nhãn cùng class đích"** — TRƯỚC khi append, xoá khỏi file đích (label file của project) TẤT CẢ dòng có `class_id == index của "Nhãn đích" trong self.label_list` (tức xoá box cũ của đúng cái nhãn đích đang ghi, không đụng nhãn khác), rồi mới append box mới (đã remap class_id) vào. Áp dụng đúng lúc ghi file (trong `_write_yolo_ext`/hàm ghi mới, hoặc 1 bước lọc trước khi gọi `_write_yolo_ext` — Tech Lead quyết định vị trí đặt logic).

**Ngoài scope (không làm trong amendment này):** mapping nhiều class_id nguồn → nhiều nhãn đích khác nhau trong CÙNG 1 lần chạy; không đổi hành vi mặc định (Append + Model detect) của bản gốc.

**Agent chain:** `tech-lead` (cập nhật TDD) → `senior-developer` (code) → `tech-lead` (review) → `qa-engineer` (smoke test lại CẢ tính năng cũ lẫn mới, đảm bảo không regression).

| # | Bước | Agent | Status | Artifact | Hoàn thành lúc | Ghi chú |
|---|------|-------|--------|----------|-----------------|---------|
| 4.1 | Cập nhật TDD: thiết kế UI model-picker-trong-khung, radio nguồn nhãn (model/thư mục), ô nhập nhiều class_id, radio chế độ ghi (append/thay thế), refactor luồng lấy-box-mới thành 1 hàm trừu tượng dùng chung cho worker (model source vs folder source), vị trí đặt logic xoá-trước-khi-ghi. | tech-lead | ✅ | `docs/tech-design/TDD-batch-add-class.md` (mục 8 Amendment, +.docx ✓, .pdf ⚠️ RPC) | 2026-07-08 20:57 | Commit 3fa7f93. Chốt (a)-(g) + tên 7 biến + 6 method mới + 5 method sửa. Text-level write bảo toàn OBB 9-token |
| 4.2 | Code amendment vào `tab_bbox.py` theo TDD cập nhật. | senior-developer | ✅ | `tool/features/annotation/tab_bbox.py` (commit 970e598) | 2026-07-08 21:25 | KHÔNG phá hành vi mặc định (Append + Model detect) đã QA pass ở Phase 3 |
| 4.3 | Review code amendment — đặc biệt: logic xoá-trước-khi-ghi (Thay thế) không xoá nhầm nhãn khác, đọc nhiều class_id nguồn đúng, chế độ Thư mục label không cần load ảnh vẫn hoạt động đúng cho preview (review mode vẫn cần mở ảnh để vẽ canvas, nhưng KHÔNG cần model). | tech-lead | ✅ | **APPROVED** — commit 970e598 sẵn sàng QA. Không phát hiện bug thêm ngoài bug signature `_batch_show_review` mà Senior Dev đã sửa. AST + Import OK. | 2026-07-08 21:30 | Không cần vòng lại Senior Dev |
| 4.4 | Smoke test lại: (a) chế độ Model detect + Append vẫn hoạt động như Phase 3 (regression), (b) chế độ Model detect + Thay thế xoá đúng nhãn cũ, (c) chế độ Thư mục label + Append, (d) chế độ Thư mục label + Thay thế, (e) nhập nhiều class_id nguồn (vd "0,2"), (f) model-picker mới trong khung Batch hoạt động đúng, đồng bộ với ô Model phía trên. | qa-engineer | ✅ | `docs/test-cases/TC-bbox-batch-add-class.md` (cập nhật +mục Amendment, .docx ✅, .pdf ✅). Commit 0c57bed | 2026-07-08 21:41 | 24 PASS / 0 FAIL / 0 SKIP. Tk kha dung. QA PASS. |

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

### Bước 2.1 — Audit + hoàn thiện code Batch Add Class

- **Đã làm:** Audit toàn bộ ~518 dòng code do agent trước tạo (uncommitted). Xác nhận code đúng cú pháp và import được. Phát hiện 1 lỗi lệch TDD: nút "⏹ Dừng" được pack ngay lúc build (visible nhưng disabled) thay vì ẩn (pack_forget). Đã sửa: bỏ `.pack(side=LEFT)` ban đầu, `_batch_set_ui_state` dùng `pack_forget()`/`pack(side=LEFT)`. Chạy test OBB roundtrip thủ công (không commit vào repo), kết quả ALL PASSED.
- **File/module đã đọc hoặc đổi:**
  - Đọc: `docs/tech-design/TDD-batch-add-class.md` (toàn bộ), `.claude/plans/PLAN-bbox-batch-add-class-2026-07-08.md`, `git diff -- tool/features/annotation/tab_bbox.py`, `git show HEAD:tool/features/annotation/tab_bbox.py` (dòng _read_yolo/_write_yolo, _PIL_Image, _filtered_files, _on_det_model_loaded).
  - Sửa: `tool/features/annotation/tab_bbox.py` (2 chỗ nhỏ: nút Dừng pack_forget/pack).
- **Quyết định quan trọng:**
  - Không có lệch TDD về logic/threading. Chỉ có 1 lệch nhỏ về UI state của nút Dừng — đã sửa để khớp TDD §(c) state machine (idle=ẩn, running=hiện).
  - Code thêm `_on_batch_src_class_change` (auto-fill nhãn đích khi đổi class nguồn) và `_batch_set_ui_state` (refactor state management) — không có trong TDD nhưng không vi phạm TDD, là enhancement hợp lý.
  - `_batch_review_evt.clear()` đặt TRƯỚC `root.after(0, _batch_show_review, ...)` — an toàn hơn pseudocode TDD (clear trước, rồi mới queue UI callback, rồi wait).
- **Bước sau (Tech Lead review — bước 3.1) cần chú ý:**
  - **Threading race condition chấp nhận được:** `_batch_stop` set `cancel_evt` + `review_evt` → thread nền unblock, nhưng `_batch_show_review` đã được queued trong root.after. UI thread sẽ xử lý show_review rồi finish ngay sau — review frame flash cực ngắn rồi bị hide bởi `_batch_finish`. Hành vi này chấp nhận được theo TDD §(d) và §(i).
  - **`_batch_review_evt.wait()` không timeout:** Safe vì luôn có 1 trong 4 nút (Áp dụng/Bỏ qua/Dừng-row1/Dừng-batch_stop) gọi `_batch_review_evt.set()`. Nhưng nếu app crash giữa chừng → daemon thread tự die.
  - **`self._det_conf_var.get()` từ thread nền:** Kỹ thuật không thread-safe trong Tkinter, nhưng `_run_detect` hiện có cũng làm tương tự → chấp nhận được (giống pattern cũ).
  - **OBB 9-token:** `_read_yolo_ext` trả về len=9 list, `_write_yolo_ext` check `len(ann)==9` → viết đúng 8 tọa độ. Test roundtrip đã verify.

### Bước 3.1 — Tech Lead review commit e6b1f73

- **Đã làm:** Review commit e6b1f73 (518 dòng thêm mới) theo TDD checklist. Verify bằng cách đọc code thật (không chỉ tin lời Senior Dev): (1) `_batch_worker` — mọi UI update qua `root.after(0, ...)` — grep xác nhận không có ngoại lệ, chỉ có `self._batch_cancel_evt.is_set()` (non-Tk, safe) và `self._det_conf_var.get()` (giống pattern `_run_detect` hiện có — accepted); (2) `_read_yolo_ext`/`_write_yolo_ext` — đọc code trực tiếp, verify logic 5-token / 9-token đúng: `_read` trả list len=5 hoặc len=9 tuỳ format, `_write` check `if len(ann)==9` ghi đúng 8 tọa độ, `else` ghi 5-token (unpack 5 phần tử) — CORRECT, không phá OBB; (3) race condition `_batch_stop` vs queued `_batch_show_review` — trace: worker unblock từ wait() → break → `_batch_finish` queued sau `_batch_show_review` → UI thread chạy show_review (packs frame, sets preview) rồi ngay sau đó finish (clear preview + unpack frame + state=idle). Review frame flash ngắn — SAFE, không crash, chỉ hơi kém UX. Chấp nhận cho v1; (4) `_batch_review_evt.wait()` no-timeout — verify cả 4 điểm set event: apply/skip/stop-button/batch_stop, và fallback trong `_batch_show_review` (line 500-504) khi fp không có trong image_files → decision="skip" + set(). SAFE; (5) `_run_detect`/`_on_det_model_loaded` — chỉ thêm 1 dòng `self._refresh_batch_class_combo()` cuối `_on_det_model_loaded`. Không đụng flow khác. SAFE; (6) `_batch_maybe_reload_current` — set `_modified=False` + `_load_image(current_idx)` — CORRECT; (7) Cancel button — daemon=True, cancel_evt.is_set() check đầu vòng lặp → chỉ trễ 1 ảnh hiện tại đang inference (documented trong TDD §(i), acceptable); (8) `label_list` mutation — làm trên UI thread trong `_batch_start` TRƯỚC khi spawn worker — an toàn.
- **File/module đã đọc hoặc đổi:** Đọc: `docs/tech-design/TDD-batch-add-class.md` (toàn bộ), `git show e6b1f73` (toàn bộ diff), `tool/features/annotation/tab_bbox.py` (đoạn thêm mới line 172-183, 631-640, 1262-1266, 1319-1329, 3315-3320, 3742-4244 = toàn bộ block Batch Add Class), `_load_image` (line 1037-1092), `_autosave` (line 1892-1894), `_on_det_model_loaded` (line 3304-3318). KHÔNG SỬA code.
- **Quyết định quan trọng:**
  - **APPROVED** — không blocker, không request changes.
  - Không tự sửa gì (không có lỗi rõ ràng cần fix ngay).
  - Điểm race #1 mà Senior Dev cảnh báo: đã trace kỹ, chấp nhận được (flash ngắn, không crash).
  - Phát hiện MỚI 1 minor UX: `_load_image` không reset `_batch_preview_active`/`_batch_preview_boxes` (chỉ reset `_zoomtest_active`, `_verify_active`). Nếu user click image listbox chọn ảnh khác trong lúc `state="review-waiting"` → preview boxes cũ vẫn được vẽ trên ảnh mới với TOẠ ĐỘ SAI. Không crash, chỉ hiển thị sai. Ghi chú riêng cho QA verify — nếu QA thấy UX confusing thì fix ở PR sau (disable image listbox click khi state != idle, hoặc reset preview state trong _load_image nếu không phải flow batch_show_review).
- **Bước sau (QA Engineer — bước 3.2) cần biết:**
  - **Entry point ứng dụng:** `python app.py` tại thư mục `d:\Tool` (đã verify — `app.py` có `if __name__ == "__main__"` ở line 303). Tab cần test: **BBox Editor (v1)** — KHÔNG phải `BBox v2`.
  - **Vị trí UI mới:** LabelFrame **"➕ Bổ sung class hàng loạt"** nằm trong khối center panel, giữa Batch Relabel toolbar và Attribute bar. Có 3 hàng: Row 1 (Class nguồn combo + Nhãn đích entry + 2 nút Quét + nút Dừng ẩn ban đầu), Row 2 (progressbar + status label), Row 3 (2 nút Áp dụng/Bỏ qua, ẩn ban đầu, chỉ hiện ở chế độ Review khi worker đang chờ).
  - **Chuẩn bị test data:** Cần 1 thư mục ảnh có ít nhất 5-10 ảnh + file `.txt` YOLO đi kèm (có thể trống hoặc có sẵn box). Có ít nhất 1 file mix 5-token và 9-token (OBB) để verify không phá dòng cũ. Model test: `yolo11n.pt` (đã có tại thư mục gốc `d:\Tool\yolo11n.pt`) — YOLO Ultralytics có `.names` (80 class COCO), class 0 = person.
  - **4 kịch bản test bắt buộc:**
    1. **Auto — path chính:** Load thư mục ảnh có nhãn cũ → Load model `yolo11n.pt` → Chọn class `0: person` → Nhập nhãn đích (VD "person") → Bấm **🔍 Quét toàn bộ** → verify: (a) progressbar chạy 0→100%, (b) status label update từng ảnh, (c) nút Dừng hiện, 2 nút Quét disable, (d) sau khi xong, messagebox tổng kết hiện đúng số ảnh, (e) mở 1 vài file `.txt` bằng notepad → verify box CŨ vẫn còn (dòng đầu tiên), box MỚI được APPEND cuối, KHÔNG bị xoá nhãn cũ, (f) nếu file cũ có dòng 9-token OBB → verify vẫn giữ 9-token (KHÔNG bị convert sang 5-token).
    2. **Review — flow lần lượt:** Cùng bộ ảnh → Bấm **🔍 Quét lần lượt** → verify: (a) worker dừng ở ảnh đầu tiên có box mới, canvas load ảnh đó, preview box cam đứt nét `#F05922` hiển thị đè lên GT màu thường, (b) Row 3 hiện 2 nút Áp dụng/Bỏ qua, (c) bấm **✅ Áp dụng & tiếp theo** → file `.txt` được ghi, chuyển sang ảnh kế, (d) bấm **⏭ Bỏ qua** → file KHÔNG ghi, chuyển sang ảnh kế, (e) bấm **⏹ Dừng** → toàn bộ quá trình dừng, messagebox tổng kết hiện.
    3. **Reload canvas trong batch:** Mở 1 ảnh bằng cách click listbox → chạy Auto → khi worker đi qua đúng ảnh đang mở → verify canvas TỰ ĐỘNG reload để hiện box mới vừa được append (không cần user thao tác gì).
    4. **Detect đơn ảnh CŨ vẫn OK:** Load model → mở 1 ảnh → bấm "Detect" (nút cũ) → verify tính năng detect single-image vẫn chạy bình thường, KHÔNG bị phá vỡ.
  - **Edge case QA cần chú ý (phát hiện review):**
    - **UX bug minor (không blocker):** Trong lúc chế độ Review đang chờ user (state="review-waiting"), NẾU user click 1 ảnh khác trong image listbox (không bấm Apply/Skip trước) → preview boxes cam vẫn còn hiển thị trên ảnh MỚI với tọa độ SAI (tọa độ của ảnh cũ). Không crash — chỉ hiển thị nhầm. Nếu QA reproduce được → log riêng ra như 1 UX issue P3 (không blocker QA sign-off).
    - **Model ONNX:** Load 1 file `.onnx` → verify 2 nút Quét bị **disable**, status label ghi "Model ONNX / chưa load — batch chưa sẵn sàng".
    - **Không chọn class / không nhập nhãn đích / chưa load ảnh / chưa load model:** Bấm nút Quét → verify messagebox warning tương ứng hiện lên, KHÔNG có crash.
    - **Bấm Quét 2 lần liên tiếp:** verify messagebox "Đã có batch đang chạy" hiện, không có thread thứ 2 spawn.
    - **Nhập nhãn đích MỚI (chưa có trong label list):** verify label được append vào `label_list`, sidebar Listbox class + combobox class chính + Batch Relabel combos + filter combo + must-have/must-not-have listboxes ĐỀU cập nhật hiển thị nhãn mới.
    - **Threading:** Không mở dev tool để check thread count. Chỉ cần verify UI không treo khi Quét đang chạy: có thể pan/zoom canvas, scroll listbox — canvas responsive.
  - **Artifact bắt buộc bước 3.2:** `docs/test-cases/TC-bbox-batch-add-class.md` — ghi lại từng kịch bản (Given/When/Then), kết quả PASS/FAIL, screenshot (nếu có), thời gian test. Không cần chạy pytest — smoke test manual theo TDD §5 (task 2.1j).
  - **Commit hash bước 3.1:** không có (không sửa code — chỉ review + cập nhật plan).
  - **KHÔNG cần đọc lại toàn bộ code** — mọi hàm quan trọng đã được review và OK. QA chỉ cần chạy app thật theo 4 kịch bản trên.

### Bước 4.2 — Code amendment (model picker + import folder + replace mode)

- **Đã làm:** Audit toàn bộ 385 dòng thêm mới trong working tree (uncommitted từ session trước). Xác nhận syntax OK và import OK. Phát hiện và sửa 1 bug thật: `_batch_show_review` signature mismatch — được gọi với 2 tham số `(fp, new_boxes_px)` nhưng định nghĩa có 3 tham số `(fp, existing, new_boxes)` → TypeError khi Tkinter dispatch qua `root.after` (chế độ Review/Quét lần lượt sẽ không bao giờ hiện preview). Fix: bỏ tham số `existing` khỏi signature (không được dùng ở bất cứ đâu trong body — body chỉ dùng `new_boxes`). Chạy 20 test thủ công trong scratchpad (không commit) — 20 PASS, 0 FAIL. Commit 970e598.
- **File/module đã đọc hoặc đổi:**
  - Đọc: `.claude/plans/PLAN-bbox-batch-add-class-2026-07-08.md`, `docs/tech-design/TDD-batch-add-class.md` (mục 8), `tool/features/annotation/tab_bbox.py` (dòng 4029-4459 = toàn bộ amendment block, 4356-4408 = _batch_worker)
  - Sửa: `tool/features/annotation/tab_bbox.py` (1 dòng: signature `_batch_show_review` dòng 4419)
- **Quyết định quan trọng:**
  - Chỉ có 1 bug thật — signature mismatch `_batch_show_review`. Tất cả các điểm audit khác đều đúng theo TDD.
  - Audit các method: `_batch_worker` (signature + call args đều khớp), `_batch_start` (gọi worker đúng thứ tự 6 tham số), `_batch_set_ui_state` idle logic (`folder OR model_names` — đúng), `_batch_write_new_lines` (text-level, OBB 9-token không bị parse lại), `_batch_get_new_boxes_for_image` folder+auto (không mở ảnh), `_on_batch_src_mode_change` (pack_forget/pack đúng, không chồng lấn), `_batch_refresh_model_display` (gọi đúng ở init và `_on_det_model_loaded` dòng 3328).
  - Default path (source_mode="model", write_mode="append") không thay đổi so với Phase 3 — format dòng ghi `f"{cid} {xc:.6f} {yc:.6f} {bw:.6f} {bh:.6f}"` identical.
- **Bước sau (Tech Lead review — bước 4.3) cần chú ý:**
  - **Bug đã sửa:** `_batch_show_review` signature: `(fp, new_boxes_px)` → body dùng `new_boxes` đúng, không có vấn đề nào khác.
  - **Điểm soi kỹ khi review:**
    1. `_batch_write_new_lines` replace mode: xoá đúng `cid == dst_cid`, giữ nguyên mọi dòng khác kể cả OBB 9-token — verify bằng test A2 đã PASS.
    2. `_batch_get_new_boxes_for_image` folder+auto: trả `(lines, [], 0, 0)` không mở ảnh — verify bằng test C1 đã PASS.
    3. `_on_batch_src_mode_change` ẩn/hiện 2 frame: verify không có chồng lấn (code dùng `pack_forget` + `pack` đúng thứ tự).
    4. Chế độ Review ("Quét lần lượt") với folder source: worker gọi `_batch_get_new_boxes_for_image(..., need_preview_px=True)` — cần mở PIL chỉ để lấy size → convert normalized→pixel cho overlay. Path này CHƯA được test code-level (cần Tkinter GUI thật).
    5. `_batch_set_ui_state` nhánh idle: `can_run = (src_mode == "folder") or bool(self._det_model_names)` — logic đúng, folder mode không cần model.
  - **Không có vấn đề về threading** — worker signature và sync events giữ nguyên hoàn toàn từ Phase 3.

### Bước 4.1 — TDD Amendment (model picker + import folder + replace mode)

- **Đã làm:** Đọc lại code hiện tại (`tab_bbox.py` đoạn 3748-4245 = block Batch Add Class), TDD gốc (mục 1-7), verify line numbers thực tế sau Phase 1-3. Viết mục 8 (Amendment) vào cuối TDD — 7 mục con (8.1-8.5) gồm bối cảnh, 7 quyết định (a)-(g), sequence diagram mermaid, task breakdown 11 sub-task cho Senior Dev, checklist tài liệu. Commit 3fa7f93.
- **File/module đã đọc hoặc đổi:**
  - Đọc: `tool/features/annotation/tab_bbox.py` (line 140-190 init state, 3116-3146 _browse_det_model + _load_det_model, 3304-3318 _on_det_model_loaded, 3748-4245 block Batch Add Class hiện có, 1037-1091 _load_image, 1094-1138 _read_yolo/_write_yolo, 923-999 _load_dataset), `tool/core/ui_helpers.py` (line 128-177 _folder_row), `docs/tech-design/TDD-batch-add-class.md` (toàn bộ).
  - Sửa: `docs/tech-design/TDD-batch-add-class.md` (thêm mục 8, +475 dòng, không xoá gì).
  - Xuất: `docs/tech-design/TDD-batch-add-class.docx` (PDF thất bại — docx2pdf RPC error, non-blocker).
- **Quyết định quan trọng (Senior Dev KHÔNG cần suy luận lại — nhúng thẳng vào code):**
  1. **Model picker (Row A ĐẦU LabelFrame):** `Label "🤖 Model:" + Label self._batch_model_lbl + Button "📂 Đổi model" → self._browse_det_model`. Sync qua method mới `_batch_refresh_model_display` — gọi cuối `_build_batch_add_class_ui` (init) và cuối `_on_det_model_loaded` line 3318 (thêm 1 dòng sau `_refresh_batch_class_combo`).
  2. **UI 2 nguồn (Row B):** 2 Radiobutton `variable=self._batch_src_mode_var` value=`"model"`/`"folder"`, command=`_on_batch_src_mode_change`. Callback ẩn/hiện 2 Frame group `_batch_src_model_frame` / `_batch_src_folder_frame` bằng `pack_forget`/`pack` (pattern có sẵn từ Row 3 review).
  3. **Refactor abstract:** hàm mới `_batch_get_new_boxes_for_image(fp, src_ids, dst_cid, source_mode, src_label_dir, need_preview_px) → (new_lines_norm: list[str], new_boxes_px: list[tuple], iw: int, ih: int) | None`. Model source: mở PIL + inference (giữ nguyên logic cũ, thêm bước format lines normalized). Folder source: đọc raw text nguồn, filter cid ∈ src_ids, đổi cid → dst_cid, KHÔNG mở ảnh khi auto (mở PIL header khi review để convert normalized→pixel cho overlay).
  4. **Vị trí logic Thay thế:** hàm MỚI `_batch_write_new_lines(lbl_path, new_lines_norm, dst_cid, replace_mode)` — TEXT-LEVEL (đọc raw lines cũ giữ nguyên format, filter `cid == dst_cid` khi replace, append new_lines_norm, ghi lại). **KHÔNG đụng `_write_yolo_ext` cũ** — text-level = an toàn 100% với OBB 9-token (không parse-lại-ghi-lại, không round-trip float).
  5. **Class id parse:** hàm mới `_batch_parse_src_ids() → (set[int], err_msg: str)`. Support `"0"` / `"0,2,5"` / `"0; 2; 5"` (tolerance). Trả tuple để caller show messagebox chi tiết lỗi nhập sai.
  6. **Signature `_batch_worker` mới:** `_batch_worker(self, mode, src_ids, dst_cid, source_mode, src_label_dir, replace_mode)`. Vòng lặp gọi 2 helper trên. `_batch_show_review` signature mới: `(fp, new_boxes_px)` — BỎ tham số `existing` (không dùng nữa, text-level ghi tự đọc file trong helper).
  7. **`_batch_set_ui_state`:** sửa nhánh idle — enable nút quét khi `source_mode == "folder"` HOẶC `_det_model_names` không rỗng (folder mode KHÔNG cần model). `_refresh_batch_class_combo` gọi `_batch_set_ui_state(self._batch_state)` cuối hàm thay vì hard-code disable.
  8. **Default path IDENTICAL:** `_batch_src_mode_var=StringVar(value="model")`, `_batch_write_mode_var=StringVar(value="append")`. Với default, `new_lines_norm` được format y hệt `_write_yolo_ext` line 3946 (cùng `f"{cid} {xc:.6f} {yc:.6f} {bw:.6f} {bh:.6f}"`) → bit-by-bit identical với bản gốc. Regression test bắt buộc (Phase 4.4).
  9. **_bind_cfg persist:** khuyến khích bind 4 biến mới với key `bbox.batch.src_mode`, `bbox.batch.write_mode`, `bbox.batch.src_label_dir`, `bbox.batch.src_class_ids` (pattern có sẵn với `_det_model_path`).
  10. **Bug P3 (`_load_image` không reset preview):** Sub-task 4.2j (tuỳ chọn, <5 phút) — thêm 2 dòng reset sau line 1064. Không bắt buộc — không phá regression.
- **Bước sau (Senior Dev — bước 4.2) cần biết:**
  - **KHÔNG cần đọc lại `tab_bbox.py` từ đầu** — TDD mục 8 đã liệt kê chính xác số dòng thực tế cho từng vị trí sửa:
    * State variables mới → `__init__` line ~184 (sau khối "Batch Add Class" hiện có, sau `self._batch_dst_label_var`)
    * `_build_batch_add_class_ui` → line 3748 (thêm Row A trước Row 1 hiện có, thêm Row B source selector, tách Row 1 hiện có thành C1+C2 group frame, Row D thêm radio chế độ ghi)
    * `_refresh_batch_class_combo` → line 3831 (chuyển hard-code disable → gọi `_batch_set_ui_state(self._batch_state)`)
    * `_batch_set_ui_state` → line 3953 (nhánh idle: check `source_mode == "folder"` OR `_det_model_names`)
    * `_on_batch_src_class_change` → line 3824 (KHÔNG SỬA — chỉ dùng cho model source)
    * `_batch_start` → line 3976 (thêm validate theo `source_mode`, dispatch args mới)
    * `_batch_worker` → line 4067 (signature mới, thay block PIL.open+run_model_predict+filter → gọi `_batch_get_new_boxes_for_image`; thay `_read_yolo_ext + _write_yolo_ext` → gọi `_batch_write_new_lines`)
    * `_batch_show_review` → line 4142 (BỎ tham số `existing`, chỉ nhận `new_boxes_px`)
    * `_on_det_model_loaded` → line 3318 (thêm 1 dòng `self._batch_refresh_model_display()` sau `_refresh_batch_class_combo()`)
    * `_load_image` (tuỳ chọn 4.2j) → line 1064 (thêm 2 dòng reset `_batch_preview_boxes = []`, `_batch_preview_active = False`)
  - **KHÔNG xoá `_read_yolo_ext`/`_write_yolo_ext`** (line 3901-3949) — giữ nguyên phòng khi cần rollback. Chỉ không được gọi bởi worker nữa.
  - **7 biến state mới** (line ~184): `_batch_src_mode_var` `StringVar("model")`, `_batch_write_mode_var` `StringVar("append")`, `_batch_src_label_dir_var` `StringVar("")`, `_batch_src_class_ids_var` `StringVar("")`, cộng 3 widget refs `_batch_src_model_frame`, `_batch_src_folder_frame`, `_batch_model_lbl` (khởi tạo trong `_build_batch_add_class_ui`).
  - **6 method mới:** `_batch_refresh_model_display`, `_on_batch_src_mode_change`, `_batch_browse_src_label_dir`, `_batch_parse_src_ids`, `_batch_get_new_boxes_for_image`, `_batch_write_new_lines`. Tên đã CHỐT trong TDD §8.2(f) — Senior Dev phải theo đúng.
  - **Task breakdown chi tiết:** TDD §8.4 (11 sub-task, ước tính ~4h).
  - **Commit hash bước 4.1:** `3fa7f93` (chưa push — theo prompt).



### Bước 4.3 — Tech Lead review commit 970e598 (amendment)

- **Đã làm:** Review commit 970e598 (385 dòng thêm) theo 5 điểm Senior Dev đề nghị + TDD mục 8. Verify bằng cách đọc code thật + grep tất cả call site (không chỉ tin lời Senior Dev). Kết luận: **APPROVED, không phát hiện bug thêm.** Chi tiết:
  1. **Bug đã sửa (`_batch_show_review`)** — verify signature `def _batch_show_review(self, fp: Path, new_boxes: list)` (line 4419) khớp CHÍNH XÁC caller `self.root.after(0, self._batch_show_review, fp, new_boxes_px)` (line 4392) → 2 args + `self`. Body chỉ dùng `new_boxes` (line 4434) — không tham chiếu `existing` nào. FIX ĐÚNG.
  2. **`_batch_write_new_lines` replace mode** — verify text-level: đọc raw text lines (line 4187), filter `if cid == dst_cid: continue` (line 4202), giữ nguyên mọi dòng khác kể cả OBB 9-token có cid ≠ dst_cid (line 4204), append `new_lines_norm` (line 4207), ghi lại UTF-8 (line 4209). KHÔNG round-trip float → an toàn 100% OBB. Bảo toàn dòng lạ (không parse được cid) qua nhánh `except ValueError: keep.append(ln)` (line 4200). ĐÚNG.
  3. **`_batch_get_new_boxes_for_image` folder+auto** — verify line 4167-4169: `else: return (new_lines_norm, [], 0, 0)` — không mở PIL khi `need_preview_px=False`. Trả `iw=ih=0` (worker chỉ dùng `_iw`/`_ih` với dấu `_` — không sử dụng). Folder+review path (line 4147-4166) mở PIL header chỉ lấy size → convert normalized→pixel cho overlay — logic đúng (dùng `xc±w/2`, `yc±h/2` sau khi nhân iw/ih), verify bằng đọc code kỹ dù chưa test GUI thật. Skip dòng OBB 9-token từ source (line 4138-4139 `if len(parts) != 5: continue`) — hợp lý theo TDD (out of scope).
  4. **`_on_batch_src_mode_change` ẩn/hiện 2 frame** — verify line 4043-4048: `pack_forget` frame kia TRƯỚC khi `pack` frame mình → KHÔNG chồng lấn dù nhấn radio nhanh. `_batch_src_model_frame` pack ngay lúc build (line 3797 — default mode="model"), `_batch_src_folder_frame` KHÔNG pack lúc build (line 3810 comment).
  5. **`_batch_set_ui_state` idle** — line 4222: `can_run = (src_mode == "folder") or bool(self._det_model_names)` — folder mode luôn enable, model mode enable khi có `.names`. Consistent với `_refresh_batch_class_combo` (line 3933 delegate về `_batch_set_ui_state`).
  - **Grep exhaustive** 6 method mới + 4 biến state mới: mọi call site khớp definition (không có dangling reference như bug đã sửa).
  - **`_read_yolo_ext`/`_write_yolo_ext` cũ**: KHÔNG còn nơi nào gọi từ worker (chỉ còn tham chiếu trong docstring line 4360). Định nghĩa giữ nguyên phòng rollback (line 3977, 4003) như TDD yêu cầu.
  - **`_batch_start` validate**: line 4260-4303 — model mode check `_det_model / _det_model_names / _batch_src_class_var`; folder mode check `_batch_parse_src_ids / _batch_src_label_dir_var / Path.is_dir()`. Tất cả nhánh đều `messagebox.showwarning + return`, không thread nào bị spawn khi validate fail. ĐÚNG.
  - **Default path (model+append) IDENTICAL Phase 3**: `source_mode="model"` (line 186) + `write_mode="append"` (line 187). Format ghi `f"{int(dst_cid)} {xc:.6f} {yc:.6f} {bw:.6f} {bh:.6f}"` (line 4117) identical với Phase 3 `_write_yolo_ext`. Text-level append thay round-trip là improvement, không phải regression.
  - **UI Layout**: Row A (model picker MỚI) + Row B (source radio MỚI) + Row C1 (class combo — moved từ Row 1 cũ) + Row C2 (folder source MỚI, hidden) + Row D (nhãn đích Row 1 cũ + chế độ ghi MỚI) + Row E (3 nút quét Row 1 cũ) + Row F (progressbar Row 2 cũ) + Row G (review buttons Row 3 cũ, hidden). Insert TRƯỚC nút quét, không đảo thứ tự cũ. ĐÚNG.
- **File/module đã đọc hoặc đổi:** Đọc: `git show 970e598 --stat`, `.claude/plans/PLAN-bbox-batch-add-class-2026-07-08.md`, `tool/features/annotation/tab_bbox.py` (line 170-196 init state, 3315-3330 `_on_det_model_loaded`, 3758-3934 UI build + refresh combo + helpers, 3970-4025 `_resolve_lbl_path` + `_read_yolo_ext` + `_write_yolo_ext`, 4029-4210 6 method mới, 4214-4231 `_batch_set_ui_state`, 4240-4351 `_batch_start` + `_batch_stop`, 4356-4494 `_batch_worker` + UI callbacks). Grep exhaustive 6 method + 4 biến state. KHÔNG SỬA code (không có lỗi cần fix).
- **Quyết định quan trọng:**
  - **APPROVED** — không blocker, không request changes, không tự sửa gì thêm.
  - Bug `_batch_show_review` mà Senior Dev đã sửa được verify là ĐÚNG (single-source-of-truth: signature khớp caller, body dùng new_boxes).
  - Amendment KHÔNG phá default path Phase 3 — hành vi (model+append) identical bit-by-bit về output file.
  - Text-level ghi (`_batch_write_new_lines`) an toàn hơn round-trip cũ (`_write_yolo_ext`) — cải thiện, không phải regression.
  - Điểm 4 (folder+review path — chưa test code-level) đọc code kỹ và tự tin logic đúng, chờ QA GUI test để confirm cuối.
- **Bước sau (QA Engineer — bước 4.4) cần biết:**
  - **KHÔNG cần đọc lại toàn bộ code** — mọi hàm quan trọng đã được review + approve. QA chỉ cần chạy code-level test theo pattern Phase 3.
  - **Entry point**: `python app.py` tại `d:\Tool`. Tab **BBox Editor (v1)**, LabelFrame "➕ Bổ sung class hàng loạt".
  - **Môi trường**: Agent headless — KHÔNG có Tkinter GUI. QA Phase 3 đã dùng pattern code-level test (import các method rồi test logic) — TIẾP TỤC pattern đó.
  - **Chuẩn bị test data:**
    - Bộ ảnh có label (tái dùng data Phase 3): thư mục `runs/detect/train/` hoặc tương tự có ảnh + `.txt` YOLO.
    - **THÊM**: 1 thư mục label NGUỒN RIÊNG (khác với `lbl_dir_var` của project) để test folder source mode. Có thể tạo bằng script scratchpad: copy 1 vài file `.txt` từ project sang thư mục tạm, sửa lại vài class_id (VD viết đè 1 file có "0 0.5 0.5 0.2 0.2\n2 0.3 0.3 0.15 0.15" để test src_ids={0,2}).
    - **1 file .txt có mix 5-token + 9-token OBB** trong thư mục ĐÍCH — để test replace mode không phá OBB.
    - Model: `yolo11n.pt` (đã có tại `d:\Tool\yolo11n.pt`).
  - **6 kịch bản test bắt buộc (Phase 4):**
    1. **(a) Model detect + Append (REGRESSION)** — Load model YOLO, chọn class person, default "Chỉ thêm" → Quét toàn bộ → verify file .txt được append box mới, box cũ giữ nguyên (identical Phase 3 QA PASS). Có ít nhất 1 test với file có OBB 9-token → verify KHÔNG bị phá.
    2. **(b) Model detect + Thay thế** — Cùng thao tác nhưng chọn "Thay thế nhãn cùng class đích" → verify file .txt: (i) dòng có class_id == dst_cid ĐÃ BỊ XOÁ, (ii) dòng có class_id != dst_cid GIỮ NGUYÊN (kể cả OBB 9-token), (iii) box mới được append. Dùng `_batch_write_new_lines` trực tiếp với input mock (existing_lines + replace_mode=True) để verify từng nhánh.
    3. **(c) Thư mục label + Append** — Chọn radio "📁 Thư mục label", nhập thư mục nguồn, class_id="0", đích="test_person" → Quét toàn bộ → verify: (i) chỉ ảnh có file .txt tương ứng trong nguồn được xử lý, (ii) dòng cid=0 trong nguồn được đọc và append vào file đích với cid=index(test_person). Ảnh không có file nguồn tương ứng → skip im lặng (detected count không tăng).
    4. **(d) Thư mục label + Thay thế** — Cùng thao tác nhưng "Thay thế" → verify replace logic hoạt động đúng cả với folder source.
    5. **(e) Nhiều class_id nguồn** — Nhập "0,2,5" hoặc "0; 2; 5" → verify `_batch_parse_src_ids` parse đúng thành `{0,2,5}`, worker đọc TẤT CẢ dòng có cid ∈ {0,2,5} từ file nguồn và append với dst_cid duy nhất. Test edge case: "abc" → err_msg, "" → err_msg, "0,,2" → OK bỏ qua token trống.
    6. **(f) Model picker mới trong khung Batch** — Test `_batch_refresh_model_display` hiển thị đúng basename của `_det_model_path`, "(chưa load)" khi rỗng. Verify được gọi ở `_on_det_model_loaded` (line 3328) và cuối `_build_batch_add_class_ui` (line 3899). Nút "📂 Đổi model" gọi cùng `_browse_det_model` — verify không tạo model slot riêng.
  - **Edge case bổ sung:**
    - Toggle radio nguồn nhãn qua lại nhiều lần → verify không có widget chồng lấn (pack/pack_forget hoạt động đúng).
    - `_batch_set_ui_state("idle")` khi source_mode="folder" và model chưa load → verify 2 nút Quét vẫn ENABLE (folder mode không cần model).
    - `_batch_parse_src_ids` test unit riêng — pattern `str.replace(";", ",").split(",")` với input `"0"`, `"0,2,5"`, `"0; 2; 5"`, `"0 2 5"` (space không được — chỉ dấu phẩy/chấm phẩy), `"abc"`, `""`, `"0,,2"`.
    - `_batch_write_new_lines` với `lbl_path` không tồn tại (ảnh chưa có label) → verify tạo file mới đúng (dùng `mkdir parents`).
  - **KHÔNG cần regression full Phase 3** — chỉ cần 1 test (a) là đủ verify default path không đổi.
  - **Artifact bắt buộc bước 4.4:** cập nhật `docs/test-cases/TC-bbox-batch-add-class.md` (thêm mục Amendment, 6 kịch bản mới), gộp DOCX/PDF.
  - **Commit hash bước 4.3:** cập nhật riêng — Tech Lead approve KHÔNG sửa code.

### Bước 4.4 — QA smoke test amendment

- **Đã làm:** Chạy smoke test amendment (Bước 4.4). Tk khả dụng (Windows headless draw). Import `BBoxEditorTab` thành công. 24 test case — 24 PASS, 0 FAIL, 0 SKIP. Thêm mục "## Amendment (Phase 4)" vào cuối `TC-bbox-batch-add-class.md`. Xuất `.docx` (✅) + `.pdf` (✅). Commit `0c57bed`. Scratchpad dọn sạch.
- **File/module đã đọc hoặc đổi:**
  - Đọc: `tool/features/annotation/tab_bbox.py` (line 4029-4231 — 6 method amendment mới + `_batch_set_ui_state`), `docs/test-cases/TC-bbox-batch-add-class.md` (Phase 3 content)
  - Sửa: `docs/test-cases/TC-bbox-batch-add-class.md` (thêm mục Amendment)
  - Tạo: `docs/test-cases/TC-bbox-batch-add-class.pdf` (mới)
  - Tạo tạm (đã xóa): `scratchpad/qa_amend/` (test data + smoke script)
- **Quyết định quan trọng:**
  - Tất cả 6 kịch bản + edge cases PASS. Không có bug mới ngoài P3 đã biết từ Phase 3 (preview coords — non-blocker).
  - `"0 2 5"` (space-only) trả error message đúng — documented behavior, không phải bug.
  - `.docx` + `.pdf` đều xuất thành công (lần này PDF OK, khác Phase 3 lỗi RPC).
- **Bước sau cần biết:** KHÔNG CÓ — plan hoàn thành. QA sign-off PASS. Commit 970e598 sẵn sàng merge.

### Bước 3.2 — QA Engineer smoke test code-level

- **Đã làm:** Code-level smoke test (môi trường agent không có GUI Tkinter). Viết script Python import trực tiếp logic `_read_yolo_ext`, `_write_yolo_ext`, batch worker logic từ source. Chạy real YOLO detect với `yolo11n.pt` trên ảnh thật (`train_batch0.jpg`, có zebra class 22). Tổng 21 TC: 20 PASS, 1 SKIP (edge case GUI), 0 FAIL.
- **File/module đã đọc hoặc đổi:**
  - Đọc: `tool/features/annotation/tab_bbox.py` (dòng 3746-4245 — toàn bộ block Batch Add Class), `tool/shared/model_infer.py`
  - Tạo: `docs/test-cases/TC-bbox-batch-add-class.md` (+ .docx), scratchpad test script (không commit)
  - Cập nhật: `.claude/plans/PLAN-bbox-batch-add-class-2026-07-08.md`
- **Quyết định quan trọng:**
  - Test code-level vì agent không có GUI Tkinter. Không mock — gọi code thật + model thật.
  - Dùng `runs/detect/train/train_batch0.jpg` (zebra class 22) làm ảnh E2E thật vì ảnh giả PIL màu đơn không detect được object.
  - File `tab_bbox.py` có UTF-8 BOM (pre-existing) — dùng `encoding="utf-8-sig"` khi parse AST.
  - Bug P3 (`_load_image` không reset `_batch_preview_active`) — xác nhận đúng như Tech Lead mô tả, logged, non-blocker.
- **Bước sau cần biết:** Không có bước sau — plan hoàn thành. Merge có thể tiến hành.

## Artifacts dự kiến

- [ ] `docs/tech-design/TDD-batch-add-class.md` — Technical Design Doc (+ .docx + .pdf)
- [ ] `tool/features/annotation/tab_bbox.py` — đã thêm tính năng batch add class
- [x] `docs/test-cases/TC-bbox-batch-add-class.md` — Smoke test log + kết quả QA (commit fe7a1ec)

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
| 2026-07-08 19:25 | Bước 2.1 hoàn thành — Audit + hoàn thiện code tính năng Batch Add Class, sửa nút Dừng (pack_forget/pack thay vì state), OBB roundtrip test passed, AST+Import OK. Commit e6b1f73 (chưa push). | senior-developer |
| 2026-07-08 19:29 | Bước 3.1 hoàn thành — Tech Lead review APPROVED commit e6b1f73. Không có blocker. Phát hiện 1 minor UX (không chặn): `_load_image` không reset `_batch_preview_active` → nếu user click image listbox trong review-waiting sẽ thấy preview boxes sai toạ độ trên ảnh mới. Không crash. QA test riêng edge case này. Sẵn sàng chuyển QA. | tech-lead |
| 2026-07-08 20:15 | Bước 3.2 hoàn thành — QA smoke test code-level (agent headless). 20 PASS / 1 SKIP / 0 FAIL. Bug P3 ghi nhận (preview coords - non-blocker, đã biết). QA sign-off: PASS. Commit fe7a1ec. Plan status: completed. | qa-engineer |
| 2026-07-08 20:57 | Bước 4.1 hoàn thành — TDD Amendment (mục 8, +475 dòng) chốt 7 quyết định (a)-(g) + tên 7 biến/6 method mới + task breakdown 4.2 (~4h). Text-level write bảo toàn OBB 9-token 100%. Default path (model+append) IDENTICAL bit-by-bit với bản gốc. Commit 3fa7f93 (chưa push). DOCX ✓, PDF ⚠️ RPC (non-blocker). Sẵn sàng chuyển Senior Dev bước 4.2. | tech-lead |
| 2026-07-08 21:25 | Bước 4.2 hoàn thành — Audit + sửa bug `_batch_show_review` signature mismatch (existing param thừa), 20 test thủ công PASS, AST+Import OK. Commit 970e598 (chưa push). Sẵn sàng Tech Lead review bước 4.3. | senior-developer |
| 2026-07-08 21:30 | Bước 4.3 hoàn thành — Tech Lead review commit 970e598 APPROVED. Verify lại bug đã sửa (`_batch_show_review(fp, new_boxes)` khớp caller `root.after(0, ..., fp, new_boxes_px)`). Grep 6 method mới + 4 biến state mới: mọi call site khớp definition. `_read_yolo_ext`/`_write_yolo_ext` cũ KHÔNG còn được gọi bởi worker. Default path (model+append) IDENTICAL Phase 3. Text-level `_batch_write_new_lines` an toàn OBB 9-token. `_batch_start` validate đầy đủ theo `source_mode`. Layout Row A/B/C/D/E/F/G không phá cũ. Không sửa gì thêm. Sẵn sàng QA bước 4.4. | tech-lead |
| 2026-07-08 21:41 | Bước 4.4 hoàn thành — QA smoke test amendment (24 TC). Tk kha dung. 24 PASS / 0 FAIL / 0 SKIP. 0 bug moi. QA PASS — commit 970e598 du dieu kien merge. Commit 0c57bed. Plan status: completed. | qa-engineer |

---
**Status icons:** ⬜ Todo | 🔄 In Progress | ✅ Done | 🛑 Blocked | ⏭️ Skipped
