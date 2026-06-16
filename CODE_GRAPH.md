# CODE_GRAPH.md — KZTEK Image Tools
<!-- Cập nhật: 2026-06-16 | Tự động duy trì: đọc trước khi đọc file code -->

## Hướng dẫn sử dụng

- **Đọc file này trước** khi mở bất kỳ file `.py` nào để biết ngay class/function cần tìm
- **Cập nhật ngay** sau khi thêm file, class, hoặc function mới
- Ký hiệu: `→` = import từ; `⇢` = được import bởi

---

## Sơ đồ phụ thuộc tổng quan

```
train-image-tool.py
    → tool.core.app.App

tool/core/app.py (App)
    → tool.core.{constants, settings, ui_helpers, imports}
    → tool.features.dataset.{tab_split, tab_rename, tab_crop, tab_labelnorm}
    → tool.features.annotation.{tab_bbox, tab_checker, tab_ocr}
    → tool.features.collection.tab_iparking_image
    → tool.features.analysis.{tab_stats, tab_plate_search}
    → tool.features.detection.{tab_yolo, tab_lpr_tester, tab_slot_classifier, tab_classifier_tester}
    → tool.features.training.{tab_train, tab_classifier}

tool/core/* (HUB — không import features/utils)
tool/features/*/* → ...core.*   (3 dots)
tool/utils/*      → ..core.*    (2 dots)
```

---

## Chi tiết từng file

### ROOT

| File | Class | Hàm / Điểm vào | Import local |
|---|---|---|---|
| `train-image-tool.py` | — | `main()` entry | `tool.core.app.App` |
| `app.py` | `YoloApp` | `__init__`, `_build_ui`, `select_model`, `select_image`, `select_folder`, `load_default_model`, `on_slider_change` | — |
| `SlotDetect.py` | `_Cfg`, `SlotDetectApp` | `__init__`, `_build`, `_load`, `_on_click_canvas`, `_detect`, `_update_status` | — |

---

### tool/core/

#### `tool/core/constants.py`
Không có class/function. Chỉ hằng số.

| Hằng số nhóm | Nội dung |
|---|---|
| UI Colors | `BG="#1e1e2e"`, `CARD="#2a2a3e"`, `ACCENT="#F05922"`, `ACCENT2="#4A3F8C"`, `TEXT`, `DIM`, `SUCCESS` |
| Fonts | `F_MAIN`, `F_BOLD`, `F_MONO` |
| Files | `IMAGE_EXTENSIONS`, `CLASS_NAMES` |
| API defaults | Lotte, Parkingv6, Parkingv8 endpoint defaults |

---

#### `tool/core/settings.py`
Global: `_CFG: dict`, `_SETTINGS_FILE: Path`

| Hàm | Chữ ký | Mô tả |
|---|---|---|
| `_cfg_load` | `()` | Đọc JSON từ `_SETTINGS_FILE` vào `_CFG` |
| `_cfg_save` | `()` | Ghi `_CFG` ra file JSON |
| `_bind_cfg` | `(key, var)` | Bind Tkinter Var ↔ config key |
| `_cfg_dir` | `(key) → str` | Trả về directory đã lưu (validated) |
| `_bind_history` | `(key, combo, max_items=20)` | Bind Combobox với history list |
| `_push_history` | `(key, val, max_items=20)` | Thêm val vào history |
| `_get_history` | `(key) → list` | Lấy danh sách history |

---

#### `tool/core/ui_helpers.py`
Class: `DateTimePicker(Frame)`

| Hàm | Chữ ký | Mô tả |
|---|---|---|
| `_style_all` | `()` | Cấu hình ttk styles theme tối KZTEK |
| `_make_scrollable_frame` | `(parent)` | Tạo Canvas + Frame cuộn được |
| `_make_logbox` | `(parent)` | Tạo Text widget log |
| `_append_log` | `(widget, msg)` | Thêm dòng log có timestamp |
| `_folder_row` | `(parent, label_text, var, row, ...)` | Build hàng chọn thư mục |
| `_load_label_bboxes` | `(img_path, lbl_path=None)` | Đọc YOLO bbox từ .txt |
| `_zoom_image_window` | `(root, pil_img, title)` | Mở popup phóng to ảnh |
| `_pb_row` | `(parent)` | Build hàng progress bar |
| `_set_progress` | `(lbl, pb, done, total, root)` | Cập nhật tiến trình |
| `_action_btn` | `(parent, text, cmd, color, **kw)` | Tạo nút hành động |

---

#### `tool/core/imports.py`
Không có class/function. Chỉ flags:
`_REQUESTS_OK`, `_CV2_OK`, `_TTS_OK`, `_GTTS_OK`, `_DND_OK`, `_PADDLE_OK`

---

#### `tool/core/app.py`
Class: `App(Tk)`

| Thành phần | Mô tả |
|---|---|
| `_wrap_scrollable(nb_parent, TabClass, root_ref, *extra)` | Tạo scrollable tab frame |
| `App.__init__` | Khởi tạo Notebook 12+ tab, bind phím tắt |
| `App._open_tab_config` | Mở cấu hình tab |

Tab đã đăng ký (theo thứ tự):
`SplitTab`, `RenameTab`, `CropByLabelTab`, `LabelNormTab`, `BBoxEditorTab`,
`IParkingImageTab`, `CheckerTab`, `StatsTab`, `PlateSearchTab`,
`YoloTab`, `TrainTab`, `ClassifierTrainTab`, `LprTesterTab`, `SlotClassifierTab`, `ClassifierTesterTab`

---

### tool/features/dataset/

#### `core_split.py`
| Hàm | Chữ ký | Mô tả |
|---|---|---|
| `run_split` | `(source_dir, output_dir, max_per_folder, do_move, log, progress)` | Chia ảnh vào thư mục con |

#### `tab_split.py` → Class `SplitTab(Frame)`
| Method | Mô tả |
|---|---|
| `_build` | Build UI |
| `_update_preview` | Cập nhật preview số lượng |
| `_on_mode_change` | Xử lý đổi mode copy/move |
| `_run` | Chạy split (thread) |
| `_stop` | Dừng tiến trình |

---

#### `core_rename.py`
| Hàm | Chữ ký | Mô tả |
|---|---|---|
| `build_rename_plan` | `(parent_dir, out_dir, per_folder, padding, start_num, keep_ext, forced_ext, recursive)` | Tạo kế hoạch đổi tên |
| `execute_rename_plan` | `(plan, action, log, progress, stop_check=None)` | Thực thi kế hoạch |

#### `tab_rename.py` → Class `RenameTab(Frame)`
| Method | Mô tả |
|---|---|
| `_build` | Build UI |
| `_browse` | Chọn thư mục |
| `_update_preview` | Preview kế hoạch đổi tên |
| `_run` | Thực thi rename |
| `_undo` | Hoàn tác rename |

---

#### `core_crop.py`
| Hàm | Chữ ký | Mô tả |
|---|---|---|
| `_parse_label` | `(path)` | Đọc file .txt YOLO |
| `_yolo_px` | `(xc, yc, w, h, iw, ih)` | Convert YOLO → pixel coords |
| `run_crop` | `(image_dir, label_dir, output_dir, log, progress)` | Crop cơ bản |
| `run_crop_by_label` | `(cfg, log, progress, stop_event)` | Crop nâng cao với filter |

#### `tab_crop.py` → Class `CropByLabelTab(Frame)`
| Method | Mô tả |
|---|---|
| `_refresh_classes` | Load danh sách class |
| `_run` | Chạy crop |
| `_update_stats` | Cập nhật thống kê |

---

#### `core_label_norm.py`
| Hàm | Chữ ký | Mô tả |
|---|---|---|
| `_box_area` | `(box) → float` | Diện tích box |
| `_iou_norm` | `(b1, b2) → float` | Tính IoU |
| `_apply_label_filters` | `(boxes, cfg)` | Lọc box theo class/area/aspect/edge |
| `_subfolder_name` | `(boxes, cfg) → str` | Xác định subfolder đích |
| `run_label_norm` | `(cfg, log, progress, stop_event)` | Pipeline chuẩn hóa label |

#### `tab_labelnorm.py` → Class `LabelNormTab(Frame)`
| Method | Mô tả |
|---|---|
| `_refresh_classes` | Load class list |
| `_on_filter_change` | Xử lý thay đổi filter |
| `_run` | Chạy label norm |
| `_preview_update` | Cập nhật preview |

---

### tool/features/annotation/

#### `tab_bbox.py` → Class `BBoxEditorTab(Frame)`
| Hàm / Method | Mô tả |
|---|---|
| `_lighten_color(hex, factor)` | Làm nhạt màu (hover effect) |
| `_build` | Build UI canvas |
| `_load_image_list` | Load danh sách ảnh/label |
| `_draw_bboxes` | Vẽ bbox lên canvas |
| `_on_canvas_click` | Xử lý click chuột |
| `_on_canvas_drag` | Xử lý kéo chuột |
| `_save_labels` | Lưu file .txt YOLO |

---

#### `tab_checker.py` → Class `CheckerTab(Frame)`
| Method | Mô tả |
|---|---|
| `_load_data` | Load ảnh + nhãn |
| `_show_batch` | Hiển thị lưới ảnh |
| `_on_cell_click` | Click chọn ô ảnh |
| `_speak` | Phát âm biển số (SAPI/gTTS) |
| `_prefetch_images` | Thread prefetch ảnh |
| `_save_corrections` | Lưu sửa đổi nhãn |

Import thêm: `..analysis.core_gt`

---

#### `tab_ocr.py` → Class `OcrTab(Frame)`
| Method | Mô tả |
|---|---|
| `_load_files` | Load danh sách ảnh |
| `_preview_update` | Preview ảnh hiện tại |
| `_run_ocr` | Chạy PaddleOCR |
| `_on_roi_draw` | Vẽ vùng ROI |

Yêu cầu: `_PADDLE_OK`

---

### tool/features/analysis/

#### `core_gt.py`
| Hàm | Chữ ký | Mô tả |
|---|---|---|
| `analyze_gt` | `(gt_path)` | Phân tích ground truth → (labels, char_counts, length_counts) |
| `_heat_color` | `(count, max_count) → str` | Màu heatmap #252540 → #F05922 |

⇢ Được dùng bởi: `tab_checker.py`, `tab_stats.py`

#### `tab_stats.py` → Class `StatsTab(Frame)`
| Method | Mô tả |
|---|---|
| `_load`, `_load2` | Load 1 hoặc 2 dataset |
| `_build_heatmap` | Tạo heatmap ký tự |
| `_filter_classes` | Lọc theo class |
| `_compare_datasets` | So sánh 2 dataset |

#### `tab_plate_search.py` → Class `PlateSearchTab(Frame)`
| Method | Mô tả |
|---|---|
| `_load_gt` | Load file ground truth |
| `_search` | Tìm kiếm fuzzy/wildcard |
| `_show_image` | Hiển thị ảnh kết quả |
| `_batch_search` | Tìm kiếm hàng loạt |

---

### tool/features/detection/

#### `tab_yolo.py` → Class `YoloTab(Frame)`
| Method | Mô tả |
|---|---|
| `_load_model` | Load YOLO model |
| `_select_image` | Chọn ảnh |
| `_run_detection` | Chạy detect 1 ảnh |
| `_draw_boxes` | Vẽ kết quả |
| `_batch_process` | Detect hàng loạt |

Hỗ trợ: YOLO v8/v11, dual-model, drag-drop

#### `tab_lpr_tester.py` → Class `LprTesterTab(Frame)`
| Hàm / Method | Mô tả |
|---|---|
| `_get_session()` | HTTP session với retry |
| `_load_images` | Load ảnh |
| `_run_detection` | Test LPR 1 ảnh |
| `_batch_test` | Test hàng loạt |
| `_save_results` | Xuất kết quả |

Modes: `lprdetect` (vehicle), `DirectLprDetect` (plate crop)
Targets: KZTEK LPR AI Server, OpenALPR

#### `tab_slot_classifier.py` → Class `SlotClassifierTab(Frame)`
| Method | Mô tả |
|---|---|
| `_load_model` | Load model |
| `_on_canvas_draw/move/resize` | Vẽ bbox thủ công |
| `_classify` | Phân loại slot |
| `_batch_process` | Hàng loạt |

#### `tab_classifier_tester.py` → Class `ClassifierTesterTab(Frame)`
| Method | Mô tả |
|---|---|
| `_load_model` | Load classifier model |
| `_classify_single` | Test 1 ảnh |
| `_batch_test` | Test folder (class-subfolder) |
| `_show_results` | Hiển thị Top-1/Top-5 |

---

### tool/features/training/

#### `tab_train.py` → Class `TrainTab(Frame)`
| Method | Mô tả |
|---|---|
| `_select_dataset` | Chọn dataset YAML |
| `_run_training` | Chạy training subprocess |
| `_plot_results` | Plot matplotlib metrics |
| `_monitor_training` | Theo dõi training live |

Models: yolo11n/s/m/l/x

#### `tab_classifier.py` → Class `ClassifierTrainTab(Frame)`
| Method | Mô tả |
|---|---|
| `_select_dataset` | Chọn dataset |
| `_run_training` | Chạy training classifier |
| `_plot_results` | Plot metrics |

---

### tool/features/collection/

#### `lotte_image.py`
| Class | Mô tả |
|---|---|
| `_SharedLaneState` | Trạng thái thread-safe theo lane |
| `LotteApiClient` | API client hệ thống Lotte |
| `LotteWorker` | Worker thread download/xử lý ảnh |

#### `parkingv8_image.py`
| Class | Mô tả |
|---|---|
| `_P8SharedLaneState` | Thread-safe state (Parkingv8) |
| `Parkingv8ApiClient` | API client Parkingv8 |
| `Parkingv8Worker` | Worker thread |

Hàm: `_p8_suffix_to_imgtype()` — map suffix → folder name
Image types: vehicle, plate crop, panorama, face, other (entry/exit riêng)

#### `parkingv6_image.py`
| Class | Mô tả |
|---|---|
| `_P6SharedLaneState` | Thread-safe state (Parkingv6) |
| `Parkingv6ApiClient` | iParkingv5 API, Bearer token, MinIO |
| `Parkingv6Worker` | Worker thread |

Hàm tiện ích: `_p6_safe()`, `_p6_vi_to_ascii()`, `_p6_vtype_to_category()`, `_p6_img_type_from_key()`
Vehicle types: `o_to` (car), `xe_may` (motorbike), `xe_dap` (bicycle)

#### `lotte_consolidate.py`
| Class | Mô tả |
|---|---|
| `ConsolidateWindow(Toplevel)` | UI gom ảnh round-robin theo lane/loại xe/giờ |

Hàm: `_scan_source()` — scan by lane → vehicle type → hour

#### `tab_iparking_image.py` → Class `IParkingImageTab(Frame)`
| Method | Mô tả |
|---|---|
| `_load_config` | Load config API |
| `_select_source` | Chọn nguồn (Lotte/v8/v6) |
| `_run_download` | Bắt đầu tải ảnh |
| `_view_bad_images` | Mở BadImageViewer |

Import: `.parkingv8_image`, `.parkingv6_image`, `.lotte_image`, `...utils.bad_image_viewer`, `...utils.migrate_structure`

---

### tool/utils/

#### `bad_image_viewer.py` → Class `BadImageViewer(Toplevel)`
| Hàm | Chữ ký | Mô tả |
|---|---|---|
| `_parse_direction` | `(stem) → "in"/"out"/""` | Phân tích chiều từ tên file |
| `_parse_plates` | `(stem, reason)` | Trích thông tin biển số |
| `_parse_plates_3col` | `()` | Parser định dạng 3 cột |
| `scan_bad_images` | `(out_path) → list[...]` | Quét ảnh lỗi |
| `_load_photo` | `()` | Load ảnh preview |
| `_norm_plate` | `()` | Chuẩn hóa chuỗi biển số |
| `_diff_segments` | `()` | So sánh biển số diff |
| `_crop_plate` | `()` | Crop vùng biển số |

Bad image reasons: `"none"` (thiếu biển), `"in_out_mismatch"`, `"register_mismatch"`

#### `migrate_structure.py`
| Hàm | Chữ ký | Mô tả |
|---|---|---|
| `migrate_image_structure` | `(out_path, log_fn, stop_event)` | Di chuyển cấu trúc thư mục cũ → mới (thêm HH subfolder) |
| `_remove_empty_dirs` | `(root) → int` | Xóa thư mục rỗng |
| `open_migrate_window` | `(root_tk, out_path)` | UI wrapper |

---

### GetImageApp/

| File | Class | Mô tả |
|---|---|---|
| `RunGetParkingImage.py` | `GetParkingImageApp(_AppBase)` | Standalone GUI wrapper IParkingImageTab |
| `BuildGetImageGUI.py` | `BuildApp(Tk)` | PyInstaller build utility với progress window |

---

## Quy tắc cập nhật CODE_GRAPH.md

Sau khi thêm/sửa code, cập nhật phần tương ứng:

1. **Thêm file mới** → thêm mục mới trong section đúng
2. **Thêm class** → thêm vào bảng class của file đó
3. **Thêm hàm/method** → thêm dòng vào bảng hàm
4. **Thêm import** → cập nhật mũi tên `→` trong sơ đồ phụ thuộc
5. **Xóa/rename** → cập nhật hoặc xóa entry tương ứng

Format cập nhật ở đầu file: `<!-- Cập nhật: YYYY-MM-DD -->`
