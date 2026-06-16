# ERRORS.md — Lỗi đã gặp & cách sửa

Đọc file này trước khi implement để tránh lặp lại lỗi cũ.

---

## [E001] Edit báo lỗi "File has been modified since read"
- **File:** Bất kỳ `tool/tab_*.py`
- **Triệu chứng:** `Edit` tool trả về lỗi `File has been modified since read, either by the user or by a linter`
- **Nguyên nhân:** Linter (Pylance, Ruff, Black…) tự động format file sau khi đã Read nhưng trước khi Edit
- **Cách sửa:** Gọi `Read` lại file ngay trước khi `Edit` trong cùng một message; không delay giữa Read và Edit
- **Ngày:** 2026-06-13

---

## [E002] old_string không match do indent/whitespace
- **File:** `tool/tab_crop.py`, `tool/tab_bbox.py`
- **Triệu chứng:** `Edit` tool báo old_string không tìm thấy mặc dù nhìn có vẻ đúng
- **Nguyên nhân:** `old_string` copy từ context bị thêm indent thừa (ví dụ 8 spaces thay vì 0), hoặc linter đã đổi indentation
- **Cách sửa:** Luôn dùng `Read` với line offset cụ thể để lấy chính xác đoạn cần thay; copy nguyên văn từ output của Read (bỏ số dòng ở đầu)
- **Ngày:** 2026-06-13

---

## [E003] Import thiếu _bind_history / _push_history
- **File:** Nhiều `tool/tab_*.py`
- **Triệu chứng:** `NameError: name '_bind_history' is not defined` khi chạy app
- **Nguyên nhân:** Chỉ import `_bind_cfg` từ settings, quên thêm `_bind_history, _push_history, _get_history`
- **Cách sửa:** Khi thêm history vào tab, luôn cập nhật dòng import thành: `from .settings import _bind_cfg, _cfg_dir, _bind_history, _push_history, _get_history`
- **Ngày:** 2026-06-13

---

## [E004] Double-click trên Canvas xung đột với single-click binding
- **File:** `tool/tab_bbox.py`
- **Triệu chứng:** Double-click mở zoom nhưng cũng trigger `<Button-1>` (bắt đầu vẽ bbox)
- **Nguyên nhân:** Tkinter khi nhận `<Double-Button-1>` vẫn fire `<Button-1>` trước đó 2 lần
- **Cách sửa:** Trong handler `<Button-1>`, kiểm tra `event.time` so với lần click trước; hoặc chấp nhận behavior này vì zoom window tách biệt không ảnh hưởng đến bbox drawing
- **Ngày:** 2026-06-14

---

## [E005] _zoom_image_window render trắng nếu gọi ngay khi window chưa mapped
- **File:** `tool/ui_helpers.py`
- **Triệu chứng:** Cửa sổ zoom hiện ra nhưng trắng/rỗng
- **Nguyên nhân:** `canvas.create_image()` được gọi trước khi Toplevel được map lên màn hình
- **Cách sửa:** Dùng `win.after(30, _render)` thay vì gọi `_render()` trực tiếp sau khi tạo window
- **Ngày:** 2026-06-14

---

## [E006] Combobox history không load khi khởi động nếu _bind_cfg và _bind_history dùng cùng key
- **File:** `tool/settings.py`
- **Triệu chứng:** Combobox trống khi mở app lần đầu dù đã từng nhập
- **Nguyên nhân:** `_bind_cfg` lưu giá trị đơn vào key `"tab.field"`, còn `_bind_history` lưu list vào key `"h.tab.field"` — hai key khác nhau, không xung đột, nhưng `_bind_cfg` set value overrides giá trị combo sau khi `_bind_history` đã set
- **Cách sửa:** Gọi `_bind_history` SAU `_bind_cfg`; hoặc không dùng `_bind_cfg` cho field đã có `_bind_history`
- **Ngày:** 2026-06-14

---

## [E007] Tab checker: self.img_dir là None khi double-click zoom trước khi load dataset
- **File:** `tool/tab_checker.py`
- **Triệu chứng:** `_zoom_cell_img` crash vì `self.img_dir` là `None`
- **Nguyên nhân:** `img_dir` chưa được gán trước khi `load_dataset()` được gọi
- **Cách sửa:** Guard trong `_zoom_cell_img`: `if not filename or not self.img_dir: return` — đã implement
- **Ngày:** 2026-06-14

---

## [E008] torch.load YOLOv5: No module named 'models.yolo'
- **File:** `tool/features/detection/tab_slot_classifier.py`
- **Triệu chứng:** Tất cả 3 stage load đều lỗi `No module named 'models.yolo'` hoặc `models.common`
- **Nguyên nhân:** YOLOv5 `.pt` được `torch.save(model)` pickle cùng class từ repo `ultralytics/yolov5`. Khi `torch.load` deserialized, Python cần `models.yolo`, `models.common` trong `sys.path`. `ultralytics` v8 KHÔNG load được YOLOv5 format. `torch.hub.load` cũng lỗi nếu chưa có internet lần đầu hoặc hub cache thiếu.
- **Cách sửa:** Dùng `pip install yolov5` và load bằng `yolov5.load(path)`. Fallback: inject hub cache vào `sys.path` trước khi `torch.load`. Thứ tự: yolov5 pkg → ultralytics v8 → torch.load + sys.path inject.
- **Ngày:** 2026-06-16

---

## [E009] ctypes Win32 pointer truncation → "access violation writing 0x20"
- **File:** `tool/features/detection/tab_lpr_tester.py` — `_copy_file_to_clipboard`
- **Triệu chứng:** `exception: access violation writing 0x0000000000000020` khi gọi `ctypes.memmove`
- **Nguyên nhân:** `ctypes.windll.kernel32.GlobalAlloc` và `GlobalLock` mặc định có `restype = c_int` (32-bit). Trên Python 64-bit, con trỏ HGLOBAL 64-bit bị cắt còn 32-bit thấp → thường ra `0x20` (32 decimal) thay vì địa chỉ thực
- **Cách sửa:** Khai báo rõ `restype = ctypes.c_void_p` và `argtypes` đúng kiểu cho `GlobalAlloc`, `GlobalLock`, `GlobalFree`, `SetClipboardData` trước khi gọi. Luôn kiểm tra NULL sau `GlobalAlloc`/`GlobalLock`.
- **Ngày:** 2026-06-16

---

## [E010] Worker gửi __DONE__ không kiểm tra send_done — premature UI completion ở parallel mode
- **File:** `tool/features/collection/parkingv8_image.py` — `Parkingv8Worker.run()`
- **Triệu chứng:** Khi chạy parallel (N > 1 worker), nếu bất kỳ P8 worker nào fail login, Start button bật lại trong khi các worker khác vẫn đang chạy.
- **Nguyên nhân:** Đường dẫn login failure dùng `self.log_q.put("__DONE__")` trực tiếp, không guard `if self._send_done`. LotteWorker và Parkingv6Worker đã guard đúng.
- **Cách sửa:** Thêm `if self._send_done:` trước `self.log_q.put("__DONE__")` ở mọi early-return path trong `run()`.
- **Ngày:** 2026-06-16

---

## [E011] `_clear_log` tìm sai attribute — Ctrl+L không xóa log
- **File:** `GetImageApp/RunGetParkingImage.py`, `tool/core/app.py`
- **Triệu chứng:** Ctrl+L không làm gì, log không bị xóa
- **Nguyên nhân:** `_clear_log` / `_global_ctrl_l` tìm attribute `("_log", "log")` — trong `IParkingImageTab`, `_log` là METHOD (truthy), nên `w = method`, `w.configure()` ném exception, nhưng `return` vẫn được gọi → widget `log_txt` không bao giờ được tìm thấy
- **Cách sửa:** Đổi lookup thành `("log_txt", "log")` và thêm guard `not callable(w)` để bỏ qua method
- **Ngày:** 2026-06-16

---

## [E012] `BuildGetImageGUI.py` dùng đường dẫn module cũ (pre-restructure)
- **File:** `GetImageApp/BuildGetImageGUI.py`
- **Triệu chứng:** Build exe thành công nhưng exe crash với `ModuleNotFoundError` khi chạy
- **Nguyên nhân:** Sau khi restructure `tool/` thành `tool/core/`, `tool/features/`, `tool/utils/`, các `--hidden-import` vẫn dùng đường dẫn phẳng cũ: `tool.settings`, `tool.parkingv8_image`, `tool.tab_iparking_image`… Exe không tìm thấy module đúng package path
- **Cách sửa:** Cập nhật toàn bộ `--hidden-import` sang đường dẫn mới: `tool.core.settings`, `tool.features.collection.parkingv8_image`, v.v.
- **Ngày:** 2026-06-16

---

*Cập nhật file này mỗi khi gặp lỗi mới. Format: `[Ennn]` tăng dần.*
