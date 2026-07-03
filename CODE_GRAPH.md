# CODE_GRAPH.md — KZTEK Image Tools
<!-- Cập nhật: 2026-07-03 | YOLO Detect: test model Segment (viền polygon, màu theo instance khi 1 class, hiện thời gian nhận dạng ⏱); YOLO Train: thêm model Segment (yolo11*-seg.pt) vào dropdown Model -->

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
    → tool.features.collection.tab_web_image
    → tool.features.analysis.{tab_stats, tab_plate_search}
    → tool.features.detection.{tab_yolo, tab_lpr_tester, tab_slot_classifier, tab_classifier_tester}
    → tool.features.training.{tab_train, tab_classifier}

tool/core/* (HUB — không import features/shared/utils)
tool/shared/* → ..core.*        (2 dots) — dùng bởi nhiều features
tool/features/*/* → ...core.*   (3 dots), ...shared.*
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
| `GetImageApp/RunGetParkingImage.py` | `GetParkingImageApp` | `__init__`, `_bind_shortcuts`, `_on_close` | `tab_iparking_image.IParkingImageTab` |
| `GetPgsImageApp/RunGetPgsImage.py` | `GetPgsImageApp` | `__init__`, `_bind_shortcuts`, `_on_close` | `tab_pgs_image.PgsImageTab` |

---

### IParkingDetectApp/ (C# .NET 8 WinForms)

**Mục đích:** App C# test model YOLO (OpenVINO IR `.xml` + `.bin` hoặc ONNX `.onnx`) trên tập ảnh iParking. Tính năng tương đương YOLODetect tab trong Python tool.

**Build:** `dotnet build` | **Run:** `dotnet run` hoặc `IParkingDetect.exe`

| File | Class / Type | Hàm / Members chính |
|---|---|---|
| `IParkingDetectApp.csproj` | — | Deps: `Sdcb.OpenVINO`, `Sdcb.OpenVINO.runtime.win-x64` |
| `Program.cs` | — | Entry point |
| `DetectForm.cs` | `DetectForm : Form` | `BuildUI`, `OnLoadModel`, `OnLoadPath`, `OnDetectAll`, `DetectCurrent`, `NavigateTo`, `RefreshCanvas`, `SetReview`, `UpdateFilmstrip`, `RestoreSession`, `SaveSession` |
| `UI/Theme.cs` | `Theme` (static) | KZTEK brand colors + font + control factories: `Btn`, `Lbl`, `Cmb`, `Slider`, `Chk`, `Row`, `SectionHdr`, `BboxColor` |
| `Models/DetectBox.cs` | `DetectBox` (record), `ReviewState` (enum) | `ClassId`, `ClassName`, `Confidence`, `X1/Y1/X2/Y2`, `Width`, `Height`, `Area`, `Rect` |
| `Inference/YoloRunner.cs` | `YoloRunner : IDisposable` | `LoadModel(path, device)`, `Detect(bmp/path, conf, iou)`, `SetClassNames`, `LoadClassNamesFromYaml` (static); dùng Sdcb.OpenVINO; letterbox preprocess |
| `Inference/PostProcess.cs` | `PostProcess` (static) | `Decode(span, numCh, anchors, conf, iou, …)` — giải mã YOLOv8/v11 output + NMS |
| `Helpers/BboxRenderer.cs` | `BboxRenderer` (static) | `DrawBoxes(bmp, boxes)`, `MakeThumb(bmp, boxes, w, h)`, `FitImage` |
| `Helpers/AppSettings.cs` | `AppSettings` | `Load()`, `Save()`, `PushModelHistory`, `PushImageHistory`; persist vào `%AppData%\KZTEK\IParkingDetect\settings.json` |
| `Controls/ImageCanvas.cs` | `ImageCanvas : Panel` | `SetImage(bmp, fit)`, `FitToView()`, `ZoomStep(delta)`; zoom bằng mouse wheel, pan bằng drag |

**Luồng dữ liệu:**
```
DetectForm → YoloRunner.LoadModel(path) → Sdcb.OpenVINO.OVCore
DetectForm → YoloRunner.Detect(bmp) → Letterbox → OVCore.Infer → PostProcess.Decode → List<DetectBox>
DetectForm → BboxRenderer.DrawBoxes → ImageCanvas.SetImage → Display
```

**Phím tắt:**
| Phím | Hành động |
|---|---|
| `←` / `→` | Ảnh trước / sau |
| `Enter` | Đánh dấu ĐÚNG |
| `Delete` | Đánh dấu SAI |
| `F5` | Detect All |
| `Escape` | Dừng Detect All |
| `Ctrl+O` | Mở thư mục ảnh |
| `Ctrl+M` | Mở model |

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
Class: `GridPageNav(Frame)`, `DateTimePicker(Frame)`

| Hàm / Class | Chữ ký | Mô tả |
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
| `GridPageNav` | `(parent, *, on_prev, on_next, on_first, on_last, on_direct, extra_right=None)` | Thanh phân trang dùng chung (⏮ ◀ Trước … Sau ▶ ⏭); `.page_var`, `.update(cur, max, total)` |

---

#### `tool/core/imports.py`
Không có class/function. Chỉ flags:
`_REQUESTS_OK`, `_CV2_OK`, `_TTS_OK`, `_GTTS_OK`, `_DND_OK`, `_PADDLE_OK`

---

#### `tool/core/app.py`
Class: `App(Tk)`

| Thành phần | Mô tả |
|---|---|
| `_wrap_scrollable(nb_parent, TabClass, root_ref, *extra)` | Tạo scrollable tab frame → `(outer, tab_obj)` |
| `App.__init__` | Khởi tạo Notebook 15 tab, bind phím tắt |
| `App._set_tab_visible(title, visible)` | Ẩn/hiện tab trong Notebook |
| `App._open_tab_config()` | Dialog bật/tắt tab (lưu vào `app.enabled_tabs`) |
| `App._bind_shortcuts()` | Đăng ký tất cả phím tắt toàn cục |
| `App._current_tab()` | Trả về tab object đang active |
| `App._tab_step(delta)` | Chuyển tab kế tiếp/trước (Ctrl+Tab) |
| `App._global_f5/esc/ctrl_o/ctrl_s/ctrl_l/ctrl_a/ctrl_z` | Dispatcher phím tắt → method tương ứng của tab active |
| `App._global_delete_key/return/space/left/right/f1` | Dispatcher phím tắt điều hướng |
| `App._on_close()` | Lưu config rồi thoát app |

Tab đã đăng ký (theo thứ tự, 15 tab):
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

### tool/shared/

> Module tái dùng cho nhiều tab. Import pattern: `from ...shared.X import Y` (3 dots từ features).

#### `tool/shared/bbox_renderer.py`
| Symbol | Mô tả |
|---|---|
| `PALETTE: list[str]` | 15 màu hex cho class 0–14 (KZTEK brand đầu) |
| `hex_to_rgb(hex)` | Chuyển hex → tuple RGB |
| `draw_bboxes_on_pil(pil, boxes, class_names, *, conf_thresh, line_width, font_size, palette, single_color)` | Vẽ bbox + label text; trả về PIL mới |
| `draw_bboxes_thumb(pil, boxes, *, conf_thresh, filter_cid, line_width, palette)` | Vẽ bbox outline (không text) lên thumbnail |
| `make_padded_thumb(pil, tw, th, bg)` | Resize giữ tỉ lệ + padding vào nền tw×th |
| `open_image_safe(path)` | Mở PIL + EXIF rotate, trả None nếu lỗi |

#### `tool/shared/label_io.py`
| Symbol | Mô tả |
|---|---|
| `_ATTR_DEFAULTS` | Dict default cho sidecar attrs |
| `read_yolo_normalized(lbl_path)` | Đọc .txt → list tuple (cid, cx, cy, w, h) normalized |
| `read_yolo_pixel(lbl_path, img_w, img_h)` | Đọc .txt → list [cid, x1, y1, x2, y2] pixel |
| `write_yolo_labels(lbl_path, bboxes_px, img_w, img_h)` | Ghi pixel bboxes → YOLO normalized |
| `label_path_for(img_path, lbl_dir)` | Trả về Path .txt tương ứng |
| `attrs_path_for(lbl_path)` | Trả về Path .attrs.json |
| `read_attrs(lbl_path, n_bboxes, defaults)` | Đọc sidecar attrs |
| `write_attrs(lbl_path, attrs, defaults)` | Ghi sidecar attrs |
| `load_progress(progress_file)` | Đọc .kztek_progress.json → set tên file đã làm |
| `save_progress(progress_file, done_set)` | Ghi tiến độ |

#### `tool/shared/canvas_zoom.py`
| Symbol | Mô tả |
|---|---|
| `CanvasZoomMixin` | Mixin zoom/pan cho class có `_canvas` và `_pil_img` |
| `_zoom_init()` | Khởi tạo state (gọi trong `__init__`) |
| `_zoom_reset()` | Reset về fit-to-canvas |
| `_zoom_step(factor)` | Zoom theo factor, tâm canvas |
| `_on_zoom_wheel(event)` | Handler scroll-wheel zoom tại cursor |
| `_on_pan_start/drag/end(event)` | Middle-mouse pan handlers |
| `_calc_zoom_offsets()` | Trả về `(scale, nw, nh, off_x, off_y)` để render |

#### `tool/shared/detect_cache.py`
| Symbol | Mô tả |
|---|---|
| `CACHE_FILENAME` | `".kztek_det_cache.json"` |
| `DetectCache` | Thread-safe cache kết quả YOLO detect |
| `.get(path)` | Lấy entry |
| `.put(path, n, classes, boxes)` | Ghi entry |
| `.has(path)` | Kiểm tra tồn tại |
| `.pop(path)` | Xóa entry |
| `.clear()` | Xóa toàn bộ |
| `.snapshot()` | Bản sao shallow toàn bộ cache |
| `.save_to_disk(folder, model_path, conf, iou)` | Lưu disk |
| `.load_from_disk(folder, model_path, iou)` | Load disk; `True` nếu thành công |
| `.filter_files(files, *, cls_filter, ndet_min, ndet_max, area_min, area_max, w_min, w_max, h_min, h_max, must_have, must_not)` | Lọc file theo cache |
| `.all_class_counts()` | `{cid: count}` tổng hợp |

#### `tool/shared/filmstrip.py`
| Symbol | Mô tả |
|---|---|
| `FilmstripPanel(Frame)` | Grid filmstrip phân trang, lazy render |
| `__init__(master, *, get_thumb, on_select, cols_var, rows_var, extra_nav)` | `get_thumb(path,tw,th)->PIL.Image` |
| `.load(file_list, current_path)` | Nạp danh sách ảnh mới |
| `.set_current(path)` | Cập nhật ảnh đang chọn, scroll tới trang |
| `.invalidate_cache(path)` | Xóa thumbnail cache (khi label thay đổi) |

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
| `_delete_page_to_deleted` | Di chuyển toàn bộ ảnh+label trong trang grid vào thư mục `deleted/` (có thể khôi phục) |
| `_lbl_labelcount` | Label hiển thị tổng số bbox: không filter → đếm tất cả; có filter class → chỉ đếm class đó |
| `_on_canvas_wheel` | Mouse wheel → BILINEAR preview ngay + schedule LANCZOS settle 200ms |
| `_zoom_step(factor)` | Zoom +/- centered on canvas center; cancel settle, force LANCZOS |
| `_zoom_reset` | Reset zoom về Fit; cancel settle, clear render cache |
| `_render(resample)` | Re-render canvas; cache `_render_nw_nh` → skip PIL resize khi pan (size unchanged) |
| `_on_pan_start/drag/end` | Middle-mouse drag → pan khi zoomed in |
| `_ctrl_panning` | Flag: Ctrl+left-drag trên vùng trống → pan (thay rubber-band) |
| `_escape_action` | Escape: cancel poly/draw/deselect (khôi phục bbox ẩn) |
| `_hide_others` | Flag: khi đang vẽ/kéo/resize → `_draw_all_bboxes` chỉ vẽ bbox trong `_selected_set`, ẩn phần còn lại; tắt + render lại khi release |
| `_draw_all_bboxes` (only_draw) | Hover → chỉ vẽ bbox đang hover (+ bbox đang chọn), ẩn còn lại; vẽ/kéo/resize → chỉ bbox đang thao tác |
| `_go_page_abs(page)` | Nhảy tới trang đầu (0) hoặc trang cuối (-1) — nút ⏮ ⏭ |
| `_go_page_direct()` | Nhảy tới số trang nhập trong Entry (validate + clamp) |
| `_on_numkey_label(n)` | Phím 0-9: chọn class n; nếu có bbox đang chọn → relabel ngay |
| `_bbox_attrs` | List[dict] song song với `_bboxes`: `{condition, occluded, truncated, difficult}` mỗi bbox |
| `_default_attrs()` | Trả về dict attrs mặc định `{condition:day, occluded:none, truncated:false, difficult:false}` |
| `_attrs_path(lbl_path)` | Đường dẫn sidecar `.attrs.json` bên cạnh file `.txt` |
| `_read_attrs(path, n)` | Đọc sidecar JSON attrs; pad/trim về đúng `n` bbox |
| `_write_attrs(path)` | Ghi sidecar; xóa file nếu tất cả attrs là mặc định |
| `_write_attrs_to(path, attrs)` | Ghi attrs list tùy ý ra path (dùng cho copy_to_next) |
| `_refresh_attr_bar()` | Load attrs của bbox đang chọn vào thanh attribute bar |
| `_on_attr_change(key)` | Callback khi user đổi combobox attribute |
| `_set_attr_bar_state(state)` | Enable/disable toàn bộ combobox trong attr bar |
| `_restore_session()` | Khởi động: auto load folder + jump tới ảnh cuối cùng đã mở |
| `_do_restore_nav()` | Điều hướng đến `_restore_img` sau khi async filter hoàn thành |
| `_relabel_batch()` | Đổi nhãn hàng loạt: thay class_id từ → đến trong tất cả file label của bộ lọc hiện tại; reload ảnh đang mở nếu bị ảnh hưởng |

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
| `_detect_all` | Detect toàn bộ ảnh, lưu cache, có nút Dừng |
| `_on_detect_all_progress` | Cập nhật UI theo tiến độ detect all |
| `_on_detect_all_done` | Kết thúc detect all |
| `_update_class_filter_combo` | Cập nhật combo filter class từ cache |
| `_schedule_det_filter` | Debounce 300ms khi gõ filter kích thước |
| `_clear_det_filters` | Xóa tất cả detect filters |
| `_apply_det_filters` | Áp dụng filter class/n_det/bbox vào danh sách ảnh |
| `_save_det_cache_to_disk` | Lưu `_det_cache` ra `{folder}/.kztek_det_cache.json` sau Detect All |
| `_load_det_cache_from_disk` | Load cache từ disk khi `_load_image_list`; validate model + iou |

| `_browse_wrong_folder` | Mở dialog chọn thư mục lưu ảnh sai |
| `_open_wrong_folder` | Mở Explorer tại thư mục lưu ảnh sai |
| `_save_wrong_image` | Copy ảnh hiện tại vào `v_wrong_folder` (không move) |

| `_open_video_detect` | Dialog chọn nguồn video (file / RTSP / YouTube / webcam) |
| `_resolve_youtube_stream` (module-level) | yt-dlp: link YouTube + độ phân giải → (direct stream URL, title, is_live); chạy trong thread nền, không block dialog |
| `_launch_video_window` | Cửa sổ detect liên tục: worker thread đọc frame + YOLO, main thread poll queue 16ms |

| `_toggle_grid` | Ẩn/hiện grid panel bằng PanedWindow |
| `_build_grid_panel` | Build thumbnail grid UI với nav bar ⏮◀Entry▶⏭ |
| `_rebuild_grid` | Populate `_grid_inner` với cells từ `image_list`; cập nhật `_grid_page_entry_var` |
| `_go_grid_page_abs(page)` | Nhảy tới trang đầu (0) hoặc trang cuối (-1) — nút ⏮ ⏭ |
| `_go_grid_page_direct` | Nhảy tới số trang nhập trong Entry (validate + clamp, 1-indexed) |
| `_grid_render_batch` | Render thumbnail theo batch 20 ảnh/16ms (lazy) |
| `_render_grid_thumb` | Render thumbnail PIL với bbox overlay từ cache |
| `_set_grid_thumb` | Gán PIL → PhotoImage vào Label |
| `_grid_cell_bg` | Màu viền cell (current=ACCENT, correct=xanh, incorrect=đỏ) |
| `_refresh_grid_highlights` | Cập nhật màu viền cell khi navigation |
| `_grid_scroll_to_current` | Cuộn grid tới cell hiện tại |
| `_on_grid_size_change` | Đổi kích thước thumbnail, xóa cache render |
| `_schedule_grid_rebuild` | Debounce 200ms trước khi rebuild grid |
| `_auto_restore_session` | Load lại folder + ảnh từ `yolo.session.*` trong config (chạy 1 lần sau model load) |

| `_test_lpr_connection` | Test kết nối tới LPR server bằng ảnh giả 4×4, cập nhật `_lpr_conn_lbl` |
| `_lpr_parse_plate` | Trích biển số từ JSON response (hỗ trợ nested Results[0].Plate và flat plate) |
| `_lpr_call_crop` | POST PIL crop lên LPR URL (field `upload`), trả về plate string |
| `_lpr_overlay_boxes` | Filter plate class → crop từng bbox → gọi LPR → vẽ nhãn xanh; lưu vào `_last_lpr_plates_result` |
| `_extract_plate_from_filename` | @static: trích biển số từ tên file dạng `sub_<plate>[_...]` |
| `_update_gt` | @static: thêm/cập nhật dòng `filename\tplate` trong `gt.txt` (upsert theo filename) |
| `_save_lpr_error_image` | Lưu ảnh full + crops biển số vào wrong_folder; tạo/cập nhật `gt.txt` với plate GT |

Cache: `_det_cache = {path: {"n": int, "classes": {cid: count}, "boxes": [(cid, cx_n, cy_n, w_n, h_n, w_px, h_px, conf_score)]}}`
Disk cache: `{folder}/.kztek_det_cache.json` — persist giữa session; validate model path + iou khi load
`conf_thresh` (slider Ngưỡng) là **display-time filter** — không xóa cache, filter boxes khi render
Session keys: `yolo.session.folder`, `yolo.session.image`
Hỗ trợ: YOLO v8/v11, dual-model, drag-drop, detect all + filter class/size + grid thumbnail panel + session restore + LPR overlay (crop bbox → API → vẽ biển số)
Nguồn video: file / RTSP / HTTP / webcam / **YouTube URL** (yt-dlp resolve → cv2.VideoCapture); yêu cầu `pip install yt-dlp` (flag `_YTDLP_OK`); history key `h.yolo.youtube_url`
YouTube độ phân giải: combobox readonly (Best/1080p/720p/480p/360p/240p/Worst) → `_YT_QUALITY_FORMATS` map sang yt-dlp `format` string; lưu lựa chọn cuối qua `_bind_cfg("yolo.youtube_quality", ...)` (không dùng history vì giá trị cố định)
Seek bar (thanh tua): hiện với file video HOẶC YouTube VOD (`enable_seek=True`, `is_live=False` từ yt-dlp); ẩn với webcam/RTSP/YouTube livestream — `_launch_video_window(..., enable_seek=bool)`

**Test model Segment (YOLO-Seg):**
| Method | Mô tả |
|---|---|
| `_is_seg_model(mdl)` | @static: `True` nếu `mdl.task == "segment"` (model `yolo11*-seg.pt`) |
| `_seg_has_poly(masks, i)` | @static: `True` nếu `masks.xy[i]` là polygon hợp lệ (≥3 điểm) cho instance thứ i |
| `_overlay_seg_masks(pil_img, results, color_fn, alpha=90, line_width=2)` | Vẽ mask polygon (`results[0].masks.xy`): fill bán trong suốt + viền nét liền (`draw.line` khép kín); không đổi gì nếu model không có `.masks` |
| `_run_model` | Thêm `retina_masks=True` khi model là Segment → mask nét theo đúng độ phân giải ảnh gốc |

Gọi `_overlay_seg_masks` tại 3 điểm vẽ: `_annotated_to_pil` (panel model 1, màu theo class/palette), `_annotated_combined_pil` (M1+M2, màu theo `_PANEL1_COLOR`/`_PANEL2_COLOR`), `_draw_yolo_panel_on_pil` (overlay M2/M3 lên panel đã có sẵn, màu `panel_color`)
**Model Segment KHÔNG vẽ khung bbox chữ nhật** — mỗi instance có polygon hợp lệ (`_seg_has_poly`) chỉ hiện viền polygon (từ `_overlay_seg_masks`) + nhãn tên/conf; bbox chữ nhật chỉ vẽ fallback khi instance đó thiếu polygon (ví dụ model Detect thường)
Nhãn model hiện `[SEG]` (thay `[DETR]`/`[ONNX]`) khi `mtype == "yolo"` và `_is_seg_model(mdl)` — áp dụng cho cả Model 1/2/3
`_INSTANCE_COLORS` (class attr, 16 màu) — khi Segment chỉ phát hiện 1 class duy nhất trong ảnh (`_annotated_to_pil` tự đếm unique class), mỗi đối tượng được tô 1 màu riêng theo thứ tự index (thay vì cùng 1 màu class) để dễ phân biệt; áp dụng cho cả mask fill/viền lẫn box fallback + nhãn. Không áp dụng cho `_annotated_combined_pil`/`_draw_yolo_panel_on_pil` (màu ở đó biểu thị model, không phải instance)

**Thời gian nhận dạng (⏱):** `_detect_and_display._run()` đo `time.time()` quanh từng lệnh gọi model (`_run_model`/`model.predict`) riêng cho model1/2/3 → `t1_ms, t2_ms, t3_ms` truyền vào `_on_detect_done`. Hiển thị: panel đơn → nối `⏱ Xms` vào `lbl_result` (sau summary); combined mode → mỗi label `_lbl_m1_res/_lbl_m2_res/_lbl_m3_res` có `⏱Xms` riêng để so sánh tốc độ giữa các model. Nhánh cache-hit (redraw từ `_det_cache`, không chạy lại model) vẫn đo thời gian redraw+overlay, gán vào `t1_ms`
Cache `_det_cache` chỉ lưu bbox (không lưu polygon mask) → khi `model1` là Segment, `_detect_and_display` **bỏ qua cache**, luôn detect lại để hiện mask tươi; ảnh hưởng: grid thumbnail (`_render_grid_thumb`) và Detect All vẫn chỉ hiện bbox (không mask) do dùng chung cache box-only — giới hạn đã biết, chỉ ảnh live single-image mới có mask overlay đầy đủ

#### `tab_lpr_tester.py` → Class `LprTesterTab(Frame)`
| Hàm / Method | Mô tả |
|---|---|
| `_get_session()` | HTTP session với retry |
| `_load_image` / `_load_from_path` | Load ảnh đơn |
| `_detect_single` | Test LPR 1 ảnh (dùng 4pt crop nếu active) |
| `_folder_worker` | Test batch hàng loạt |
| `_export` | Xuất kết quả CSV |
| `_render_single` | Render `_pil_single` lên Canvas, scale/offset tracking |
| `_render_bbox_overlay` | Vẽ bbox detect đơn lên canvas (canvas rect, tag `bbox_ov`) |
| `_sv_toggle_4pt` | Bật/tắt chế độ 4 điểm |
| `_on_sv_press/drag/release/motion/rclick` | Canvas events cho 4pt |
| `_sv_pt_hit_test` | Hit-test điểm gần (cx,cy) |
| `_sv_draw_4pt` | Vẽ dots + polygon lên canvas |
| `_sv_clear_4pt` | Xóa 4pt state + canvas items |
| `_sv_apply_persp` | Tính warp (thread) |
| `_sv_persp_done` | Nhận kết quả warp, show preview, auto-detect |
| `_warp_perspective_lpr` (module) | cv2 → PIL → bbox fallback warp |
| `_parse_bbox_coords` (module) | Chuẩn hóa bbox dict/list → (x1,y1,x2,y2) |
| `_draw_bbox_on_pil` (module) | Vẽ bbox lên PIL Image bằng ImageDraw |

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
| `_pick_model` / `_load_model` | Chọn + load YOLO classify model |
| `_load_folder` / `_load_image_list` | Quét folder, build danh sách ảnh |
| `_rebuild_tree` | Build sidebar Treeview (support subfolder) |
| `_apply_filter` / `_update_filter_counts` | Lọc all/correct/incorrect/unreviewed |
| `_open_image` | Mở ảnh, tải PIL, gọi classify |
| `_render_display` | Vẽ ảnh lên Canvas (zoom fit/factor) |
| `_zoom_step` | Zoom in/out/fit |
| `_c2i` / `_i2c` | Chuyển toạ độ canvas↔image |
| `_on_press` / `_on_drag` / `_on_release` | Vẽ bbox (draw/move/resize 8 handle) |
| `_handle_hit` / `_inside_bbox` | Hit-test handle/bbox |
| `_redraw_bbox` | Vẽ lại bbox + 8 handle trên canvas |
| `_classify_current` | Classify toàn ảnh hoặc vùng bbox |
| `_show_result` | Hiện nhãn, bars, đổi màu bbox theo conf |
| `_mark_review` | Mark ✓/✗ → move to correct/incorrect/ |
| `_move_to_subfolder` | Di chuyển file vật lý sang subfolder |
| `_toggle_autoplay` / `_autoplay_step` | Auto-play điều hướng |
| `_update_bars` / `_clear_bars` | Top-N confidence bars |
| `_show_crop_preview` / `_clear_crop_preview` | Preview vùng bbox |
| `_batch_export` | Export CSV kết quả batch folder |
| `_save_result` | Lưu ảnh kết quả (có bbox + nhãn, hoặc perspective crop) |
| `_on_drop` | Drag-drop ảnh/folder |
| `_bind_keys` | Phím tắt: Enter=✓, Del=✗, Space=autoplay |
| `_set_crop_mode` | Chuyển chế độ "rect" ↔ "4pt", reset state |
| `_draw_4pt_overlay` | Vẽ 4 điểm + polygon outline lên canvas |
| `_clear_4pt` | Xóa toàn bộ 4pt canvas items + reset state |
| `_order_pts4` | Sắp xếp 4 điểm: TL→TR→BR→BL |
| `_apply_perspective_crop` | Kích hoạt warp (thread), rồi gọi `_on_persp_done` |
| `_on_persp_done` | Nhận kết quả warp, hiển thị preview, auto-classify |
| `_warp_perspective` | Thực hiện perspective transform (cv2 → PIL → bbox fallback) |
| `_review_state` (module-level) | Xác định trạng thái correct/incorrect/unreviewed |

---

### tool/features/training/

#### `tab_train.py` → Class `TrainTab(Frame)`
| Method | Mô tả |
|---|---|
| `_select_dataset` | Chọn dataset YAML |
| `_run_training` | Chạy training subprocess |
| `_plot_results` | Plot matplotlib metrics |
| `_monitor_training` | Theo dõi training live |
| `_open_miss_analysis` | Mở cửa sổ Miss Detection Analysis |
| `_run_miss_analysis` | Thread: batch predict → FN per class → lưu ảnh missed |
| `_open_fp_analysis` | Mở cửa sổ False Positive Analysis |
| `_run_fp_analysis` | Thread: batch predict → FP per class → confusion matrix → lưu ảnh FP + summary.json |
| `_open_imbalance_analysis` | Mở cửa sổ Class Imbalance Analysis |
| `_run_imbalance_analysis` | Thread: quét .txt labels → đếm per-class → ghi imbalance_summary.json |
| `_open_shape_analysis` | Mở cửa sổ Size & Shape Analysis |
| `_run_shape_analysis` | Thread: quét .txt labels → phân bố kích thước/tỉ lệ bbox → ghi shape_summary.json |
| `_open_brightness_analysis` | Mở cửa sổ Brightness Analysis |
| `_run_brightness_analysis` | Thread: đọc ảnh → tính mean brightness → phân bố 5 mức → per-class → ghi brightness_summary.json |
| `_generate_html_report` | Tổng hợp tất cả summary.json + results.csv → HTML report → mở browser |
| `_resume_train` | Tiếp tục training từ last.pt (resume=True) sau khi bị gián đoạn |
| `_find_last_pt` | Tìm last.pt tự động từ output_dir / project/name/weights |
| `_find_best_pt` | Tìm best.pt tự động từ output_dir / project/name/weights |
| `_ask_continue_params` | Dialog chọn best/last/custom .pt + số epochs train thêm |
| `_continue_train` | Train thêm epochs từ best.pt/last.pt sau khi train đã hoàn tất |

Models: yolo11n/s/m/l/x, rtdetr-l/x (tự chọn class YOLO/RTDETR theo tên model; rtdetr bỏ close_mosaic)
Model Segment: `_MODELS_SEG` = yolo11{n,s,m,l,x}-seg.pt (dropdown Model có separator "── Segment ──"); dùng chung class `YOLO` (ultralytics tự nhận diện task='segment' theo hậu tố `-seg`) + toàn bộ pipeline dataset/data.yaml/script train hiện có (format-agnostic); `_on_model_change` hiện cảnh báo "⚠ Cần nhãn dạng polygon (YOLO-Seg: class x1 y1 x2 y2 … xn yn)" — **KHÔNG tương thích** với nhãn bbox do BBox Editor tạo ra

#### `tab_classifier.py` → Class `ClassifierTrainTab(Frame)`
| Method | Mô tả |
|---|---|
| `_select_dataset` | Chọn dataset |
| `_run_training` | Chạy training classifier |
| `_plot_results` | Plot metrics |
| `_open_miss_analysis` | Mở cửa sổ Miss Classification Analysis |
| `_run_miss_analysis` | Thread: predict từng class subfolder → phân tích miss → lưu ảnh sai |

---

### tool/features/collection/

> **Mixin architecture (2026-06-24):** `tab_iparking_image.py` đã được refactor từ 1811 → 416 dòng.
> Logic được tách thành 4 file; `IParkingImageTab` kế thừa đa (multiple inheritance):
> ```
> IParkingImageTab(Frame, IParkingSettingsMixin, IParkingRunnerMixin, IParkingStatsMixin)
> ```

#### `iparking_constants.py`
Chỉ hằng số — không có class/function.

| Hằng số | Mô tả |
|---|---|
| `_VTYPE_ORDER` | Thứ tự chuẩn của vehicle-type key |
| `_VTYPE_COLORS` | Màu hex cho từng loại xe (UI chart) |
| `_LANE_PALETTE` | Màu hex cho từng làn (tối đa 8) |
| `_THREAD_COLORS` | Màu hex cho từng thread trong log |

Import: stdlib only. ⇢ Được dùng bởi: `iparking_settings_panels.py`, `iparking_stats_ui.py`, `iparking_runner.py`, `tab_iparking_image.py`

---

#### `iparking_settings_panels.py` → Mixin `IParkingSettingsMixin` (575L)
Chứa tất cả methods build widget cho phần cài đặt.

| Method | Mô tả |
|---|---|
| `_sep(p, title)` | Tạo separator đầu mục |
| `_build_time(p)` | Panel thời gian from/to + threads + sleep |
| `_build_output(p)` | Panel thư mục đầu ra + nút browse/open |
| `_build_common_limits(p)` | Giới hạn chung: max/day, max/hour, max/page |
| `_build_lotte_settings(p)` | Panel cài đặt Lotte (URL, apikey, lane, keyword, vehicle type) |
| `_build_p8_settings(p)` | Panel cài đặt Parkingv8 (URL, apikey, lane, vehicle type, img mode) |
| `_build_p6_settings(p)` | Panel cài đặt Parkingv6 (URL, token, lane, keyword, vehicle type) |
| `_build_phase_controls(p)` | Panel chế độ (Auto / 3-bước) + nút Xem trước/Scan/Phân tích/Tải + DB status label |
| `_on_phase_mode_change()` | Ẩn/hiện frame 3-nút phase khi mode thay đổi |
| `_refresh_db_status()` | Cập nhật nhãn trạng thái EventDB (tổng/đã tải/chờ/coverage%) |
| `_toggle_adv(src)` | Ẩn/hiện advanced settings frame |

Import: `...core.*`, `.iparking_constants._VTYPE_ORDER`, API constants, `DateTimePicker`, `_bind_cfg`, `_bind_history`

---

#### `iparking_stats_ui.py` → Mixin `IParkingStatsMixin`
Cửa sổ thống kê ảnh (Toplevel).

| Symbol | Mô tả |
|---|---|
| `_BUOI_DISP_ORDER` | Class attr — thứ tự hiển thị buổi |
| `_BUOI_RAW_MAP` | Class attr — map raw-key → tên hiển thị |
| `_hour_to_buoi_disp(h)` | (static) Giờ → buổi |
| `_show_stats()` | Mở / lift cửa sổ thống kê |
| `_stats_rebuild()` | Rescan + repopulate tất cả tabs |
| `_stats_populate(data)` | Populate 3 tab: Tổng hợp, Theo ngày, Theo buổi |
| `_scan_stats(out_path)` | (static) Quét thư mục → dict counts |
| `_make_tree(parent, cols)` | (static) Tạo Treeview có scrollbar |
| `_make_chart(parent, data)` | Vẽ biểu đồ cột bằng matplotlib |
| `_stats_tab_summary(nb, data)` | Tab Tổng hợp |
| `_stats_tab_date(nb, data)` | Tab Theo ngày |
| `_stats_tab_buoi(nb, data)` | Tab Theo buổi |

Import: `...core.*`, `.iparking_constants._VTYPE_ORDER/_VTYPE_COLORS/_LANE_PALETTE`

---

#### `iparking_runner.py` → Mixin `IParkingRunnerMixin` (580L)
Điều khiển workers (single + parallel) + polling UI.

| Method | Mô tả |
|---|---|
| `_prepare_run()` | Reset state UI trước khi chạy |
| `_clear_queues()` | Drain `_log_q` và `_stat_q` |
| `_get_common_cfg()` | Dict cấu hình dùng chung (date range, limits, threads, sleep) |
| `_split_time_windows(from_str, to_str, n)` | Chia range thời gian thành n windows khi n_days < n_threads |
| `_start_lotte(from_d, to_d, out)` | Khởi tạo + chạy LotteWorker (single hoặc parallel) |
| `_start_p8(from_d, to_d, out)` | Khởi tạo + chạy Parkingv8Worker |
| `_start_p6(from_d, to_d, out)` | Khởi tạo + chạy Parkingv6Worker |
| `_on_done_reset()` | Reset UI state về "sẵn sàng" |
| `_run_worker()` | Chạy `self._worker.run()` trong thread |
| `_retry_failed()` | Thử lại danh sách ảnh thất bại |
| `_run_parallel_lotte/p6/p8(cfg, n)` | N worker song song, time-slice khi n_days < n |
| `_poll()` | `root.after()` 100ms: đọc log_q + stat_q → cập nhật UI |
| `_aggregate_stats()` | Gộp stats từ tất cả shared-state objects |
| `_update_progress(s)` | Progress bar + ETA |
| `_log(msg, tag)` / `_log_batch(msgs)` | Ghi dòng log vào Text widget |

Import: `.lotte_image`, `.parkingv8_image`, `.parkingv6_image`, `.iparking_constants._VTYPE_ORDER`

---

#### `iparking_phase_runner.py` → Mixin `IParkingPhaseMixin` (311L)
3-phase workflow: Scan metadata → Phân tích coverage → Tải theo kế hoạch.

| Method | Mô tả |
|---|---|
| `_get_or_create_db()` | Tạo/lấy `EventDB` cho thư mục output hiện tại |
| `_start_scan()` | Chạy worker ở `mode='scan_only'` → chỉ thu thập metadata vào EventDB |
| `_show_analysis()` | Toplevel phân tích coverage: tổng scan, đã tải, worst 10 slot |
| `_start_download_from_plan()` | Tải ảnh theo kế hoạch từ EventPlanner (ưu tiên slot under-represented) |
| `_show_preview()` | Scan mẫu 1 ngày trong background thread → hiển thị phân phối giờ + ETA |

Import: `.event_db.EventDB`, `.event_planner.EventPlanner`, `.lotte_image`, `.parkingv6_image`

---

#### `event_db.py` → Class `EventDB` (247L)
SQLite cache cho metadata sự kiện + tracking download progress.

| Method | Mô tả |
|---|---|
| `is_scanned(src, date)` | Kiểm tra date đã scan chưa |
| `mark_scan_start/done(src, date)` | Đánh dấu trạng thái scan |
| `insert_events(src, records)` | Chèn batch metadata sự kiện |
| `mark_downloaded(src, event_id)` | Đánh dấu sự kiện đã tải |
| `get_events(src, downloaded)` | Truy vấn sự kiện (None=all, 0=chưa tải, 1=đã tải) |
| `get_coverage(src)` | Thống kê coverage theo lane/vtype/hour/slot |
| `count_summary(src)` | `{total_scanned, downloaded, pending}` |
| `_migrate_legacy(out)` | Auto-import từ `.lotte_done.json`/`.p8_done.json`/`.p6_done.json` |

Tables: `events(id, source, event_id, plate, dt, date, hour, minute, lane, vtype, image_refs, downloaded)`, `scan_log`

---

#### `event_planner.py` → Class `EventPlanner` (132L)
Time-Rotating Sampling — lên kế hoạch tải ảnh ưu tiên time-diversity.

| Method | Mô tả |
|---|---|
| `analyze()` | Phân tích coverage → gaps, worst_slots, coverage_pct |
| `make_download_plan(target_per_slot, max_total)` | Sắp xếp events theo priority = 1/(slot_dl+1) |
| `get_next_batch(batch_size)` | Lấy batch tiếp theo |
| `slot_label(hour, slot_idx)` | Format nhãn slot (ví dụ `08:00–08:04`) |
| `coverage_matrix()` | Ma trận coverage để hiển thị UI |

Thuật toán: 5-phút slot, score = `1/(slot_downloaded_count+1)` → slot ít ảnh nhất tải trước

---

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

Hàm module: `_p8_suffix_to_imgtype()`, `_b64decode(s)`, `_looks_b64(s)`
`Parkingv8ApiClient.fetch_detail(endpoint, id, img_mode)` — img_mode='url'→presignedUrl / 'base64'→imageBase64
`Parkingv8ApiClient.fetch_image(url)` — auto-detect data URI, raw base64, hoặc HTTP download
`Parkingv8ApiClient.extract_detail_images(detail, endpoint, img_mode)` — trích URL hoặc base64 field
`Parkingv8ApiClient.extract_images(rec, img_mode)` — fallback, check `_IMG_FIELDS_B64` khi base64
Image types: vehicle, plate crop, panorama, face, other (entry/exit riêng)
Config: `p8.img_mode` = `"url"` (default) | `"base64"`

#### `parkingv6_image.py`
| Class | Mô tả |
|---|---|
| `_P6SharedLaneState` | Thread-safe state (Parkingv6) |
| `Parkingv6ApiClient` | iParkingv5 API, Bearer token, MinIO |
| `Parkingv6Worker` | Worker thread |

Hàm tiện ích: `_p6_safe()`, `_p6_vi_to_ascii()`, `_p6_vtype_to_category()`, `_p6_img_type_from_key()`
Vehicle types: `o_to` (car), `xe_may` (motorbike), `xe_dap` (bicycle)
Config: `keyword` — truyền vào `filter.keyword` trong request body để lọc phía server

#### `pgs_image.py`
| Class / Hàm | Mô tả |
|---|---|
| `PgsImageWorker` | Worker thread duyệt file-share PGS, lọc & copy ảnh |
| `PgsImageWorker.run()` | Duyệt camera × ngày, lọc theo loại & giới hạn, copy sang output |
| `PgsImageWorker.stop()` | Set stop flag |
| `_parse_date(s)` | Parse chuỗi ngày YYYY-MM-DD / DD/MM/YYYY → datetime |
| `_date_range(start, end)` | Sinh list datetime mỗi ngày |
| `_filename_hour(name)` | Trích giờ từ HH_MM_SS_... |
| `_limit_by_hour(files, max)` | Giới hạn số file mỗi giờ |
| `_spread_sample(files, n)` | Chọn n file phân tán đều |

Cấu trúc nguồn: `<source>/<camera>/<year>/<month>/<day>/HH_MM_SS_<id>_<type>.jpg`
Config keys: `pgs.*` | Camera state: `pgs.cam_list`, `pgs.cam_selected`

#### `tab_pgs_image.py`
| Class | Mô tả |
|---|---|
| `PgsImageTab(Frame)` | Tab thu thập ảnh PGS — standalone & có thể nhúng vào main app |

| Hàm | Mô tả |
|---|---|
| `_build_source` | Source path + Discover button |
| `_build_cameras` | Camera list (checkboxes, discover, add, remove) |
| `_build_dates` | Date range + quick buttons |
| `_build_types` | Image type filter (suffix) |
| `_build_limits` | max/day, max/hour, max/cam, sleep, parallel |
| `_build_output` | Output folder |
| `_discover_cameras` | Quét source dir → thêm vào cam_vars |
| `_start/_pause/_stop` | Điều khiển worker |
| `_apply_stat` | Cập nhật progress bar + stat labels từ stat_q |

---

#### `lotte_consolidate.py`
| Class | Mô tả |
|---|---|
| `ConsolidateWindow(Toplevel)` | UI gom ảnh round-robin theo lane/loại xe/giờ |

Hàm: `_scan_source()` — scan by lane → vehicle type → hour

#### `tab_iparking_image.py` → Class `IParkingImageTab(Frame, IParkingSettingsMixin, IParkingRunnerMixin, IParkingPhaseMixin, IParkingStatsMixin)`
**457 dòng** (refactored từ 1811). Chỉ chứa UI skeleton + action handlers. Logic trong 4 mixins.

| Method | Mô tả |
|---|---|
| `__init__` | Khởi tạo tất cả instance vars, gọi `_build()` + `_poll()` |
| `_build` | Layout: header → source bar → scrollable canvas → gọi mixin `_build_*` |
| `_build_controls` | Row nút Start/Stop/Pause/Retry/Stats + Checkbutton + action buttons |
| `_build_progress` | Progress bar + pct + ETA + item_lbl + stat_lbl |
| `_build_dashboard` | Frame kết quả (ẩn khi chưa chạy xong) |
| `_build_log` | Text widget log + scrollbar + nút Xóa log |
| `_on_source_change` | Đổi nguồn (Lotte/v8/v6) → ẩn/hiện panel tương ứng + cập nhật hint |
| `_browse` / `_open_out` | Chọn / mở thư mục đầu ra |
| `_start` | Validate config → gọi `_start_lotte/p8/p6` (từ IParkingRunnerMixin) |
| `_toggle_pause` / `_stop` | Tạm dừng / dừng hẳn (set pause_event + stop flag) |
| `_on_done` | Khi tất cả workers xong → cập nhật UI + hiện dashboard |
| `_show_bad_images` | Mở `BadImageViewer` |
| `_consolidate` | Mở `ConsolidateWindow` |
| `_migrate_folder` | Mở UI migrate structure cũ → mới |
| `_clear_progress` | Xóa `.lotte_done.json` / `.p6_done.json` / `.p8_done.json` |
| `_show_dashboard(s)` / `_hide_dashboard` | Hiện/ẩn box kết quả với counters màu |

Import: `.iparking_constants._THREAD_COLORS`, `.iparking_settings_panels.IParkingSettingsMixin`, `.iparking_runner.IParkingRunnerMixin`, `.iparking_phase_runner.IParkingPhaseMixin`, `.iparking_stats_ui.IParkingStatsMixin`, `.lotte_consolidate`, `...utils.bad_image_viewer`, `...utils.migrate_structure`

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

#### `web_image.py` → `WebImageWorker`

Thu thập ảnh từ Bing/Google theo keyword, lưu vào `anh_chua_co/`.

| Symbol | Mô tả |
|---|---|
| `_DEFAULT_KEYWORDS` | Default keywords: viettelpost, taxi mai linh |
| `_safe_name(kw)` | Chuyển keyword tiếng Việt → tên thư mục ASCII |
| `_count_images(d)` | Đếm ảnh trong thư mục |
| `WebImageWorker` | Class chạy trong thread phụ |
| `WebImageWorker.run()` | Vòng lặp chính: crawl từng keyword |
| `WebImageWorker.stop()` | Set stop event |

Import: `...core.imports._ICRAWLER_OK`, `_BingCrawler`, `_GoogleCrawler`

---

#### `tab_web_image.py` → `WebImageTab(Frame)`

Tab UI thu thập ảnh web.

| Method | Mô tả |
|---|---|
| `__init__` | Khởi tạo, gọi `_build()`, `_poll()` |
| `_build / _build_content` | Xây dựng layout: output dir, engine, keywords, log |
| `_start()` | Đọc config → tạo `WebImageWorker` → chạy thread |
| `_stop()` | Gọi `worker.stop()` |
| `_poll()` | Drain log_q + stat_q mỗi 300ms |
| `_update_stat(s)` | Cập nhật thanh trạng thái |

Import: `.web_image.WebImageWorker`, `...core.{constants,imports,settings}`

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
