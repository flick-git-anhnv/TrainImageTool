# CODE_GRAPH.md — KZTEK Image Tools
<!-- Cập nhật: 2026-06-23 | Thêm tool/shared/ + tab_detect_label.py (gộp YoloDetect + BBoxEditor) -->

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

#### `tab_detect_label.py` → Class `DetectLabelTab(Frame, CanvasZoomMixin)`
Tab gộp YOLO Detect + BBox Label Editor. Import: `shared.{bbox_renderer, label_io, canvas_zoom, detect_cache, filmstrip}`.

| Method | Mô tả |
|---|---|
| `_build_toolbar()` | Model path, conf/iou slider, Detect + Stop button |
| `_build_left(paned)` | Folder rows, labels, filter panel, FilmstripPanel |
| `_build_filter(parent)` | Class combo, nDet/size/W/H entries, must-have/not-have listboxes |
| `_build_canvas(paned)` | Canvas toolbar, Canvas widget, bind zoom/pan/draw events |
| `_load_folder()` | Scan image folder, load cache từ disk |
| `_detect_folder()` | Validate + spawn detect thread |
| `_detect_thread()` | Thread: run YOLO → DetectCache → save disk → update UI |
| `_load_image(path)` | Load PIL, boxes từ .txt hoặc cache, _zoom_reset, render |
| `_render(resample)` | Override CanvasZoomMixin: render PIL + draw bbox canvas items |
| `_get_thumb(path,tw,th)` | Callback filmstrip: PIL + bbox overlay → padded thumb |
| `_on_press/drag/release` | Draw new bbox bằng click+drag |
| `_hit_test(cx,cy)` | Trả về index bbox tại canvas coords |
| `_canvas_to_norm(cx,cy)` | Chuyển canvas px → normalized coords |
| `_apply_filter()` | Lọc qua DetectCache.filter_files() → reload filmstrip |
| `_save_labels()` | Ghi self._boxes → .txt (normalized) |
| `_export_cache()` | Ghi toàn bộ detect cache → .txt files |
| `_nav(delta)` | Điều hướng prev/next trong filtered list |
| `_on_numkey(event)` | Phím 0–9: đổi class bbox đang chọn hoặc set cur_class |

Settings keys prefix: `dl.*`

---

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

| `_open_video_detect` | Dialog chọn nguồn video (file / webcam) |
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

Cache: `_det_cache = {path: {"n": int, "classes": {cid: count}, "boxes": [(cid, cx_n, cy_n, w_n, h_n, w_px, h_px, conf_score)]}}`
Disk cache: `{folder}/.kztek_det_cache.json` — persist giữa session; validate model path + iou khi load
`conf_thresh` (slider Ngưỡng) là **display-time filter** — không xóa cache, filter boxes khi render
Session keys: `yolo.session.folder`, `yolo.session.image`
Hỗ trợ: YOLO v8/v11, dual-model, drag-drop, detect all + filter class/size + grid thumbnail panel + session restore

#### `tab_lpr_tester.py` → Class `LprTesterTab(Frame)`
| Hàm / Method | Mô tả |
|---|---|
| `_get_session()` | HTTP session với retry |
| `_load_image` / `_load_from_path` | Load ảnh đơn |
| `_detect_single` | Test LPR 1 ảnh (dùng 4pt crop nếu active) |
| `_folder_worker` | Test batch hàng loạt |
| `_export` | Xuất kết quả CSV |
| `_render_single` | Render `_pil_single` lên Canvas, scale/offset tracking |
| `_sv_toggle_4pt` | Bật/tắt chế độ 4 điểm |
| `_on_sv_press/drag/release/motion/rclick` | Canvas events cho 4pt |
| `_sv_pt_hit_test` | Hit-test điểm gần (cx,cy) |
| `_sv_draw_4pt` | Vẽ dots + polygon lên canvas |
| `_sv_clear_4pt` | Xóa 4pt state + canvas items |
| `_sv_apply_persp` | Tính warp (thread) |
| `_sv_persp_done` | Nhận kết quả warp, show preview, auto-detect |
| `_warp_perspective_lpr` (module) | cv2 → PIL → bbox fallback warp |

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

Models: yolo11n/s/m/l/x

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

#### `tab_iparking_image.py` → Class `IParkingImageTab(Frame)`
Tích hợp 3 nguồn: LotteImage, Parkingv8, Parkingv6.

| Method | Mô tả |
|---|---|
| `_build` | Build toàn bộ UI (gọi các `_build_*`) |
| `_build_time/output/common_limits` | Panel chọn thời gian, thư mục đầu ra, giới hạn chung |
| `_build_lotte/p8/p6_settings` | Panel cài đặt riêng mỗi nguồn |
| `_toggle_adv(src)` | Ẩn/hiện advanced settings |
| `_build_controls/progress/dashboard/log` | Panel điều khiển, progress bar, dashboard, log |
| `_on_source_change` | Đổi nguồn (Lotte/v8/v6) → ẩn/hiện panel tương ứng |
| `_browse` | Chọn thư mục đầu ra |
| `_start` | Validate config rồi bắt đầu download |
| `_start_lotte/p8/p6` | Khởi tạo config cho từng nguồn |
| `_run_worker` | Chạy 1 worker (single thread) |
| `_run_parallel_lotte/p6/p8(cfg, n)` | Chạy N worker song song |
| `_toggle_pause/_stop` | Tạm dừng / dừng hẳn |
| `_on_done/_on_done_reset` | Xử lý khi worker hoàn tất |
| `_poll` | Đọc queue log/progress định kỳ (`after()`) |
| `_aggregate_stats` | Gộp stats từ tất cả shared-state |
| `_update_progress(s)/_refresh_stat_lbl(s)` | Cập nhật progress bar & nhãn stats |
| `_log(msg)` | Ghi log ra Text widget |
| `_show_dashboard(s)/_hide_dashboard` | Hiện/ẩn lane dashboard |
| `_show_stats/_stats_rebuild/_stats_populate` | Cửa sổ Stats Toplevel |
| `_scan_stats(out_path)` | (static) Đếm ảnh theo lane/loại/ngày |
| `_show_bad_images` | Mở `BadImageViewer` |
| `_consolidate` | Mở `ConsolidateWindow` |
| `_migrate_folder` | Mở UI migrate structure cũ → mới |
| `_retry_failed` | Retry các lane thất bại |

Import: `.parkingv8_image`, `.parkingv6_image`, `.lotte_image`, `.lotte_consolidate`, `...utils.bad_image_viewer`, `...utils.migrate_structure`, `...core.ui_helpers.DateTimePicker`

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
