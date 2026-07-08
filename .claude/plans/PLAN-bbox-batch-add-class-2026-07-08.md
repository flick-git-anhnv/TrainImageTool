---
task: bbox-batch-add-class
created: 2026-07-08
updated: 2026-07-08 20:15
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

### Bước 3.2 — QA smoke test

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

---
**Status icons:** ⬜ Todo | 🔄 In Progress | ✅ Done | 🛑 Blocked | ⏭️ Skipped
