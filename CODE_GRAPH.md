# CODE_GRAPH.md — KZTEK Image Tools
<!-- Cập nhật: 2026-07-03 | Segment tab: FIX phím tắt (bỏ root.bind_all riêng cho Ctrl+O/S/Z/Delete/Escape/◀▶ — bị WebImageTab tạo sau ghi đè; thêm alias method để App._global_* dispatcher tìm thấy); FIX chọn/kéo nhầm segment lớn khi 2 segment chồng nhau (ưu tiên diện tích nhỏ nhất chứa điểm click); FIX segment nhỏ bị đè khuất (vẽ segment đang chọn sau cùng + viền trắng nổi bật); thêm PanedWindow kéo được cho panel trái/phải; "Auto-tách segment"/"Auto-tách TẤT CẢ bbox" dùng bbox làm khung SAM/CV Box tự động | Refactor tab_yolo.py (7017→195 dòng) thành 17 file mixin/helper (yolo_*.py), theo pattern IParkingImageTab -->

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
    → tool.features.annotation.{tab_bbox, tab_segment, tab_checker, tab_ocr}
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

Tab đã đăng ký (theo thứ tự trong `_tab_defs`, xem `app.py` để biết danh sách đầy đủ hiện tại):
`SplitTab`, `RenameTab`, `CropByLabelTab`, `LabelNormTab`, `BBoxEditorTab`, `BBoxEditorTab2`,
`SegmentTab`, `IParkingImageTab`, `WebImageTab`, `CheckerTab`, `StatsTab`, `PlateSearchTab`,
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

#### `tool/shared/sam_utils.py`
| Symbol | Mô tả |
|---|---|
| `run_sam_points(model, img, pts_labels)` | SAM inference point-prompt → list polygon points |
| `run_sam_box(model, img, x1, y1, x2, y2)` | SAM inference box-prompt → list polygon points |
| `simplify(pts, epsilon_pct)` | Douglas-Peucker (`cv2.approxPolyDP`) đơn giản hóa polygon; fallback stride-sampling nếu thiếu cv2 |

#### `tool/shared/cv_segment.py`
| Symbol | Mô tả |
|---|---|
| `compute_edge_mask(img, blur_ksize, canny_low, canny_high)` | Bản đồ biên nhị phân: GaussianBlur (thông thấp) → Canny (thông cao) → dilate nối biên đứt |
| `empty_mask_like(edge_mask)` | Mask rỗng cùng shape, dùng làm accumulator ban đầu |
| `flood_region_mask(edge_mask, x, y)` | Flood-fill vùng liên thông bị bao kín bởi biên, chứa điểm (x,y); `None` nếu điểm nằm trên biên/ngoài ảnh |
| `mask_to_polygon(mask, close_ksize=15)` | Contour của mask → 1 polygon; morphological CLOSE nối các đảo rời rạc gần nhau, nếu vẫn nhiều mảnh thì gộp bằng `convexHull` → luôn trả về đúng 1 polygon |
| `run_cv_edge_segment(img, click_x, click_y, *, blur_ksize, canny_low, canny_high, min_area)` | Tiện ích 1-click: kết hợp 3 hàm trên cho 1 điểm duy nhất |
| `run_grabcut_box(img, x1, y1, x2, y2, iterations=5, pad_ratio=0.15)` | **Tự động, không cần chỉnh tham số**: kéo khung quanh object → `cv2.grabCut` tách foreground/background (xử lý trên crop quanh khung + đệm `pad_ratio` để nhanh hơn ảnh gốc) → trả mask cùng kích thước ảnh gốc |

⇢ Được dùng bởi: `tab_segment.py` — mode "🟩 CV Box" dùng `run_grabcut_box` (tự động hoàn toàn); mode "🌀 CV Edge" dùng `compute_edge_mask`/`flood_region_mask`/`mask_to_polygon`/`empty_mask_like` qua `_start_cv_drag`/`_grow_cv_mask` để tinh chỉnh thủ công (kéo=cộng, Shift+kéo=trừ)

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

#### `tab_segment.py` → Class `SegmentTab(Frame, CanvasZoomMixin)`
Annotation tool tạo nhãn polygon (YOLO-Seg: `class x1 y1 x2 y2 … xn yn`). 6 mode vẽ (Radiobutton `_mode_var`): `draw` (click từng điểm), `edit` (kéo điểm), `sam`/`sam_box` (SAM click/box prompt), `cv_box` (**GrabCut tự động** — kéo khung, không cần chỉnh tham số), `cv` (CV Edge — Quick Selection thủ công, click+kéo cộng/trừ vùng).

| Method | Mô tả |
|---|---|
| `_build_toolbar` | Thư mục ảnh, Class combobox, mode radio (Vẽ/Sửa/SAM/SAM Box/CV Box/CV Edge), nav ảnh (theo danh sách đã lọc), Lưu |
| `_build_lbl_dir_row` | Ô **"Thư mục label (tùy chọn)"** (giống BBox Editor `lbl_dir_var`) — để trống thì đọc/ghi `.txt` cạnh ảnh; đổi giá trị → `_on_lbl_dir_change` tự reload nhãn ảnh đang mở |
| `_build_left` | Danh sách ảnh + **bộ đếm** (`_img_count_lbl`, dạng "N/M ảnh") + filter **Tên** (debounce 250ms) + filter **"Chỉ hiện chưa có nhãn"** — giống panel trái BBox Editor |
| `_build_canvas` | Bọc canvas trong `wrap` + thanh công cụ riêng phía trên: nút **− / Fit% / +** zoom (dùng `_zoom_step`/`_zoom_reset` có sẵn từ `CanvasZoomMixin`), nhãn `_zoom_lbl` cập nhật trong `_render()` |
| `_build_sam_bar` | Nút load `mobile_sam.pt`/`sam_b.pt`/file .pt tùy chọn + slider Simplify (dùng chung cho SAM và CV) |
| `_build_cv_bar` | Thanh tham số **CV Edge** (Blur kernel, Canny thấp/cao, Min area px²) — chỉ ảnh hưởng mode `cv`; mode `cv_box` không cần tham số nào |
| `_label_path_for(img_path)` | Trả về đường dẫn `.txt` cho 1 ảnh bất kỳ, ưu tiên `_lbl_dir_var` nếu có set — dùng bởi `_lbl_path()` (ảnh hiện tại) và `_apply_filters()` (quét tất cả ảnh) |
| `_schedule_filter` / `_apply_filters` | Debounce 250ms cho filter Tên; `_apply_filters` quét `_img_files` → `_filtered_idx`, populate lại `_img_lb`, cập nhật `_img_count_lbl` — điều hướng (`_on_list_sel`/`_prev_img`/`_next_img`/`_load_img`) đều thao tác trên `_filtered_idx`, không phải index thô vào `_img_files` |
| `_load_dir` / `_load_img` | Quét thư mục ảnh (gọi `_apply_filters` để populate danh sách), load ảnh theo index tuyệt đối trong `_img_files`. **Thứ tự bắt buộc**: `_load_labels()` PHẢI chạy trước `_zoom_reset()` (render) — nếu render trước sẽ vẽ nhầm segment ảnh cũ lên ảnh mới (bug đã fix) |
| `_load_labels` | Đọc `.txt` cạnh ảnh — nhận cả segment (>=7 phần tử) lẫn **bbox YOLO thô (đúng 5 phần tử: `cid cx cy w h`) → tự động quy đổi thành polygon hình chữ nhật 4 điểm**, gán vào `self._n_from_bbox` để hiện trong status. Nhờ vậy nhãn bbox có sẵn (từ BBox Editor) không bị mất khi mở bằng Segment tab và Lưu đè |
| `_save` | Ghi `_segments` → `.txt` YOLO-Seg cạnh ảnh |
| `_point_in_poly(px, py, poly)` | @static: ray-casting kiểm tra điểm nằm trong đa giác |
| `_try_start_edit_drag(e) -> bool` | Hit-test: click trúng 1 điểm (ưu tiên) → kéo điểm đó (`_drag=(si,vi,...)`); không trúng điểm nhưng nằm trong thân 1 segment → chọn + kéo **cả segment** (`_drag=(si,None,...)`), ưu tiên segment có **diện tích nhỏ nhất** trong số các segment chứa điểm click (fix chọn nhầm segment lớn khi có segment nhỏ lồng bên trong, ví dụ license_plate nằm trong motorcycle); không trúng gì → `False`. Dùng chung bởi mode `edit` VÀ tự động bởi mode `draw` (xem `_on_click`) |
| `_bind_shortcuts` | CHỈ bind phím số 0-9 (`root.bind_all`, không tab nào khác dùng chữ số nên an toàn). Ctrl+O/S/Z, Delete, Escape, ◀▶ KHÔNG tự `root.bind_all` nữa (từng bị `WebImageTab` tạo sau ghi đè `<Escape>`) — thay bằng alias method `_browse`/`_undo`/`_delete_selected`/`_stop`/`_prev_image`/`_next_image` để `App._global_*` (bind trên toplevel, không xung đột giữa các tab) tự tìm thấy và dispatch đúng |
| `_render` (z-order) | Vẽ segment đang chọn (`_sel`) SAU CÙNG (`order = sorted(range(n), key=lambda i: i==_sel)`) + viền trắng dày đè thêm — đảm bảo segment nhỏ đang chọn không bị segment lớn khác che khuất khi chồng lấn |
| `_on_click` | Dispatch theo mode: **`draw`** — nếu chưa vẽ dở và `_try_start_edit_drag` trúng thì tự chuyển sang sửa (không cần bấm đổi radio "Sửa"), ngược lại thêm điểm polygon mới; `edit` — luôn gọi `_try_start_edit_drag`; sam click / sam_box & cv_box bắt đầu kéo khung / cv bắt đầu drag flood-fill |
| `_on_drag` | mode `edit`/`draw` với `_drag` đã set: `vi is None` → dịch **cả segment** theo delta chuột (tính bằng tọa độ ảnh, không phụ thuộc zoom); `vi` là số → di chuyển đúng điểm đó (như cũ) |
| `_on_right_click` | `sam`/`cv`/`cv_box` có `_preview_poly` → xác nhận; ngược lại đóng polygon vẽ tay |
| `_confirm_preview` | Thêm `_preview_poly` vào `_segments`, dùng chung cho SAM/CV Edge/CV Box |
| `_fire_sam` / `_run_sam_thread` / `_after_sam` | Chạy SAM (thread) → set `_preview_poly` chờ xác nhận |
| `_fire_cv_box` / `_run_cv_box_thread` / `_after_cv_box` | Thả chuột xong khung (mode `cv_box`) → chạy `cv_segment.run_grabcut_box` (thread, tự động — không tham số) → set `_cv_mask`/`_preview_poly` |
| `_start_cv_drag(e, subtract=False)` | Click đầu tiên mode `cv` (hoặc Shift+click qua `_on_shift_click`): tính `_cv_edges` (compute_edge_mask) + khởi tạo `_cv_mask` nếu chưa có (giữ nguyên mask cũ nếu đến từ CV Box để tinh chỉnh tiếp), gọi `_grow_cv_mask` |
| `_grow_cv_mask(ix, iy, subtract=False)` | Flood-fill vùng bao kín chứa điểm hiện tại; **cộng** (OR) hoặc **trừ** (AND NOT) vào `_cv_mask`; cập nhật `_preview_poly` từ `mask_to_polygon(_cv_mask)`. Gọi liên tục khi kéo chuột (đọc `e.state & 0x0001` mỗi frame để biết đang giữ Shift) — kiểu Quick Selection Photoshop |
| `_render` | Vẽ segments đã lưu + polygon đang vẽ + preview (SAM/CV, vàng nhạt) + khung kéo (SAM Box/CV Box, tọa độ được sort trước khi vẽ — tránh lỗi PIL khi kéo khung ngược hướng) + SAM points |
| `_on_numkey_label(n)` | Phím 0-9: chọn class n trong combobox; nếu có segment đang chọn (`_sel`) → relabel ngay (giống BBoxEditorTab) |
| `_simplify_selected` | Áp `_simplify()` (Douglas-Peucker, theo slider Simplify) lại cho RIÊNG segment đang chọn — tăng/giảm số điểm polygon ("đổi độ phân giải") mà không cần vẽ lại |
| `_auto_refine_selected` / `_auto_refine_all_bbox` / `_auto_refine_next` / `_start_auto_refine` | Dùng bbox (hộp bao) của segment đang chọn — hoặc TẤT CẢ segment còn trong `_bbox_derived` (bbox thô chưa tinh chỉnh) — làm khung cho `run_sam_box` (nếu đã load SAM) hoặc `run_grabcut_box` (fallback) để tự động tách polygon chính xác, **không cần kéo vẽ lại khung SAM Box/CV Box bằng tay**; `_auto_refine_all_bbox` xử lý tuần tự qua `_auto_refine_queue` |
| `_run_auto_refine_sam` / `_run_auto_refine_cv` / `_after_auto_refine` | Worker thread + callback; **`eps` (Simplify) phải đọc ở main thread rồi truyền vào thread** — đọc Tkinter Var trực tiếp trong thread nền từng gây `RuntimeError: main thread is not in main loop` |
| `_bbox_derived: set[int]` | Index trong `_segments` còn là bbox thô (rect 4 điểm, chưa auto-tách) của ảnh hiện tại — set lại mỗi lần `_load_labels()`, gỡ dần khi `_after_auto_refine` xử lý xong |
| `_delete_seg` / `_undo_pt` / `_cancel` | Xóa segment / hoàn tác điểm / hủy thao tác đang dở (reset cả `_cv_mask`) |

`_preview_poly: list|None` — polygon chờ xác nhận, dùng chung cho SAM/CV Edge/CV Box (chuột phải xác nhận, Esc hủy)
`_cv_mask` — mask tích lũy dùng chung giữa CV Box (khởi tạo bằng GrabCut) và CV Edge (cộng/trừ tiếp bằng flood-fill) — cho phép quy trình: kéo khung CV Box lấy kết quả nhanh, rồi chuyển CV Edge tinh chỉnh viền
Import: `...shared.canvas_zoom.CanvasZoomMixin`, `...shared.sam_utils.{run_sam_points, run_sam_box, simplify}`, `...shared.cv_segment.{compute_edge_mask, flood_region_mask, mask_to_polygon, empty_mask_like, run_grabcut_box}`

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

> **Mixin architecture (2026-07-03):** `tab_yolo.py` đã được refactor từ **7017 → 195 dòng**.
> Toàn bộ ~180 method được tách sang 17 file sibling trong cùng thư mục (2 file helper thuần
> không phụ thuộc `self` + 15 mixin); `YoloTab` kế thừa đa (multiple inheritance):
> ```
> YoloTab(Frame, YoloModelMixin, YoloImageListMixin, YoloReviewMixin,
>         YoloNavMixin, YoloCanvasMixin, YoloGridMixin, YoloCacheMixin,
>         YoloRenderMixin, YoloDetectMixin, YoloDetectAllMixin,
>         YoloLprMixin, YoloEvalMixin, YoloEvalValidateMixin,
>         YoloVideoMixin, YoloVideoWindowMixin, YoloLayoutMixin)
> ```
> `tab_yolo.py` chỉ còn: import + khai báo class + `__init__` + `_build` + `_build_statusbar`.
> Các flag optional-dependency (`_PIL_OK`, `_CV2_OK`, `_YOLO_OK`, `_RFDETR_OK`, `_DND_OK`,
> `_REQ_OK`, `_YTDLP_OK`) **không** import xuyên module (tránh circular import) — mỗi file mixin
> tự khai báo `try/except ImportError` riêng cho thư viện nó cần, giống pattern gốc.
> `_detect_mixin`, `_eval_mixin`, `_video_mixin` mỗi cái còn được tách tiếp làm 2 file vì gộp
> chung sẽ vượt giới hạn cứng 800 dòng/file — `YoloVideoWindowMixin` (~823L) là ngoại lệ duy nhất
> còn vượt nhẹ, do chứa nguyên vẹn 1 method gốc `_launch_video_window` dài ~789 dòng (nhiều
> closure lồng nhau) — không thể chia nhỏ thân hàm mà không đổi logic.

#### `yolo_onnx.py` — helper thuần (không dùng `self`)
| Class / Hằng số | Mô tả |
|---|---|
| `_OnnxDetResult` | Container kết quả inference ONNX, interface giống `sv.Detections` |
| `_OnnxRunner` | Chạy ONNX detection bằng `onnxruntime`, tự đọc input/output shape |
| `_contrast_text(bg_rgb)` | Trả về đen/trắng tuỳ độ sáng nền — dùng vẽ label tương phản |
| `_THUMB_PALETTE` | Bảng màu cố định cho thumbnail theo class id |
| `_REVIEW_ICON` | `{"correct": "✓", "incorrect": "✗", "": "○"}` |

⇢ Dùng bởi: `yolo_model_mixin`, `yolo_cache_mixin`, `yolo_grid_mixin`, `yolo_render_mixin`,
`yolo_video_window_mixin`, `yolo_imagelist_mixin`, `yolo_review_mixin`, `yolo_lpr_mixin`

#### `yolo_utils.py` — helper thuần dùng chung ≥2 mixin
| Hàm | Mô tả |
|---|---|
| `_path_review_state(path)` | `'correct'/'incorrect'/''` dựa theo tên folder cha (`true`/`false`) |
| `_iou_xywhn(...)` | IoU giữa 2 box dạng `(cx, cy, w, h)` normalized |

⇢ Dùng bởi: `yolo_imagelist_mixin`, `yolo_grid_mixin` (`_path_review_state`); `yolo_eval_mixin`,
`yolo_eval_validate_mixin` (`_iou_xywhn`)

#### `yolo_model_mixin.py` → Mixin `YoloModelMixin`
| Method | Mô tả |
|---|---|
| `_select_model` / `_select_model2` / `_select_model3` | Chọn file model 1/2/3 |
| `_on_model2_loaded` / `_on_model3_loaded` | Callback sau khi load xong model 2/3 |
| `_clear_model2` / `_clear_model3` | Bỏ model 2/3 |
| `_auto_load_pt` | Tự dò loại model (YOLO/RF-DETR/ONNX) từ đuôi file, load qua `_OnnxRunner` nếu `.onnx` |
| `_load_model` / `_on_model_loaded` | Load model 1 (thread nền) |
| `_auto_load_model` | Tự load model đã lưu trong config khi mở tab |
| `_auto_restore_session` | Khôi phục folder + ảnh cuối (`yolo.session.*`) |
| `_update_class_list` / `_update_path_combo` | Cập nhật UI sau khi có model/class list |

#### `yolo_imagelist_mixin.py` → Mixin `YoloImageListMixin`
| Method | Mô tả |
|---|---|
| `_on_drop` | Xử lý drag-drop file/folder vào canvas |
| `_load_path_input` / `_select_image` / `_select_folder` / `_open_check_folder` | Nhập đường dẫn / chọn ảnh / chọn thư mục |
| `_scan_images` / `_load_folder` / `_load_image_list` | Quét & load danh sách ảnh (hỗ trợ subfolder) |
| `_rebuild_tree` | Build lại Treeview sidebar (icon review state) |
| `_schedule_search` / `_toggle_search_hint` / `_do_search` | Tìm kiếm ảnh theo tên (debounce) |
| `_apply_filter` / `_update_filter_counts` | Lọc all/correct/incorrect/chưa review |

#### `yolo_review_mixin.py` → Mixin `YoloReviewMixin`
| Method | Mô tả |
|---|---|
| `_save_image_and_label` / `_save_page_image` | Lưu ảnh + nhãn YOLO ra thư mục review |
| `_mark_page_correct` / `_mark_page_incorrect` / `_mark_review` | Đánh dấu review đúng/sai, cập nhật `_review_state` |

#### `yolo_nav_mixin.py` → Mixin `YoloNavMixin`
| Method | Mô tả |
|---|---|
| `_open_image` / `_is_active` | Mở ảnh hiện tại, check tab đang active |
| `_bind_keys` | Bind phím tắt điều hướng (←/→, Delete, Enter…) |
| `_prev_image` / `_next_image` / `select_image` / `_nav_image` / `_on_image_select` | Điều hướng ảnh |
| `_run_detect` / `_on_delete` / `_on_return` / `_copy_path` / `_restore_result_label` | Action theo phím tắt |
| `_toggle_autoplay` / `_schedule_autoplay` / `_autoplay_step` | Auto-play qua các ảnh |

#### `yolo_canvas_mixin.py` → Mixin `YoloCanvasMixin`
| Method | Mô tả |
|---|---|
| `_on_canvas1_zoom` / `_on_canvas2_zoom` | Zoom riêng từng canvas so sánh model |
| `_render_display` | Vẽ `_pil1_full`/`_pil2_full` lên canvas theo `_zoom_factor`/`_img_pos` |
| `_on_canvas_configure` | Resize canvas → refit |
| `_on_pan_press/_drag` | Kéo chuột trái để pan |
| `_on_mmb_press/_drag/_release` | Pan bằng chuột giữa |
| `_zoom_step` / `_on_canvas_scroll` | Zoom in/out/fit bằng scroll chuột |

#### `yolo_grid_mixin.py` → Mixin `YoloGridMixin`
| Method | Mô tả |
|---|---|
| `_build_grid_panel` | Build thumbnail grid UI, dùng `GridPageNav` (`tool/core/ui_helpers.py`) |
| `_reflow_grid` / `_on_grid_frame_configure` | Tính lại số cột/hàng theo kích thước panel |
| `_calc_thumb_size` | @static: tính kích thước thumbnail |
| `_on_grid_size_change` / `_schedule_grid_rebuild` | Đổi cỡ thumbnail, debounce rebuild |
| `_go_grid_page` / `_go_grid_page_abs` / `_go_grid_page_direct` | Điều hướng trang grid |
| `_rebuild_grid` / `_make_blank_thumb` / `_schedule_film_render` / `_render_grid_thumb` | Render lại grid + thumbnail (bbox overlay từ cache) |
| `_grid_click` / `_update_filmstrip` / `_refresh_grid_cell` | Click chọn ảnh, đồng bộ filmstrip |

#### `yolo_cache_mixin.py` → Mixin `YoloCacheMixin`
| Method | Mô tả |
|---|---|
| `_cache_sv_result` / `_sv_summary` | Lưu / tóm tắt kết quả `sv.Detections`/`_OnnxDetResult` |
| `_update_class_filter_combo` | Cập nhật combo filter class từ cache |
| `_save_det_cache_to_disk` / `_load_det_cache_from_disk` / `_clear_cache` | Persist `_det_cache` ra `{folder}/.kztek_det_cache.json` |
| `_schedule_det_filter` / `_clear_det_filters` / `_apply_det_filters` | Debounce + áp dụng filter class/n_det/bbox |
| `_get_must_have_ids` / `_get_must_not_have_ids` / `_update_must_have_lists` | Danh sách "phải có"/"không có" class khi filter |
| `_cache_single_result` | Cache kết quả detect 1 ảnh (khác `_cache_sv_result` — dạng box tuple) |

Cache: `_det_cache = {path: {"n": int, "classes": {cid: count}, "boxes": [(cid, cx_n, cy_n, w_n, h_n, w_px, h_px, conf_score)]}}`
`conf_thresh` (slider Ngưỡng) là **display-time filter** — không xóa cache, filter boxes khi render

#### `yolo_render_mixin.py` → Mixin `YoloRenderMixin`
| Method | Mô tả |
|---|---|
| `_run_model` / `_results_summary` | Gọi model.predict + tóm tắt kết quả |
| `_is_seg_model(mdl)` | @static: `True` nếu `mdl.task == "segment"` |
| `_overlay_seg_masks` | Vẽ mask polygon (fill bán trong suốt + viền nét liền) |
| `_seg_has_poly(masks, i)` | @static: check polygon hợp lệ (≥3 điểm) |
| `_annotated_to_pil` / `_annotated_combined_pil` | Vẽ kết quả model 1 / M1+M2 lên PIL |
| `_rfdetr_summary` / `_draw_sv_on_pil` / `_draw_rfdetr_on_pil` | Vẽ kết quả RF-DETR/`sv.Detections` |
| `_draw_yolo_panel_on_pil` / `_draw_yolo_m3_on_pil` | Overlay model 2/3 lên panel |
| `_annotated_from_cache` | Vẽ lại từ `_det_cache` (không chạy lại model) |
| `_resize_pil` | Resize PIL giữ tỉ lệ |

`_PANEL1_COLOR`/`_PANEL2_COLOR`/`_PANEL3_COLOR` (class attr) — màu cố định từng panel khi so sánh multi-model
`_INSTANCE_COLORS` (class attr, 16 màu) — khi Segment chỉ có 1 class, tô mỗi đối tượng 1 màu riêng
Model Segment KHÔNG vẽ khung bbox chữ nhật — chỉ hiện viền polygon (`_overlay_seg_masks`) + nhãn; bbox chỉ vẽ fallback khi thiếu polygon
Nhãn model hiện `[SEG]` khi `mtype == "yolo"` và `_is_seg_model(mdl)` — áp dụng cho cả Model 1/2/3

#### `yolo_detect_mixin.py` → Mixin `YoloDetectMixin`
| Method | Mô tả |
|---|---|
| `_detect_and_display` | Pipeline detect 1 ảnh (thread nền) + hiển thị — đo thời gian `t1_ms/t2_ms/t3_ms` |
| `_on_detect_done` / `_on_detect_error` | Callback sau detect — cập nhật label kết quả + `⏱ Xms` |
| `_refresh_det_table` / `_on_det_row_select` | Cập nhật `DetTablePanel` (`det_table.py`), zoom khi click hàng |
| `_on_plot_param_change` / `_do_replot` | Debounce 200ms khi đổi font/line width → vẽ lại |
| `_sync_slider_labels` / `_on_conf_thresh_change` / `_on_slider_change` / `_get_sel_classes` | Slider conf/iou/ngưỡng hiển thị |

Cache `_det_cache` chỉ lưu bbox (không lưu polygon mask) → khi model1 là Segment, `_detect_and_display` **bỏ qua cache**, luôn detect lại để hiện mask tươi

#### `yolo_detect_all_mixin.py` → Mixin `YoloDetectAllMixin`
| Method | Mô tả |
|---|---|
| `_batch_export` | Export ảnh + nhãn hàng loạt (vẽ hoặc rename) |
| `_detect_all` / `_detect_all_run` / `_detect_page` | Detect toàn bộ ảnh trong folder, lưu cache, có nút Dừng |
| `_on_detect_page_done` / `_on_detect_all_progress` / `_on_detect_all_done` | Cập nhật tiến độ / kết thúc Detect All |

#### `yolo_lpr_mixin.py` → Mixin `YoloLprMixin`
| Method | Mô tả |
|---|---|
| `_test_lpr_connection` | Test kết nối LPR server bằng ảnh giả 4×4 |
| `_lpr_parse_plate` / `_lpr_call_crop` | Parse JSON response / POST crop ảnh lên LPR URL |
| `_lpr_draw_lines` / `_lpr_draw_from_results` / `_lpr_batch_for_path` | Vẽ nhiều dòng kết quả LPR1/2/3 lên ảnh |
| `_lpr_overlay_boxes_vid` / `_lpr_overlay_boxes` | Filter plate class → crop bbox → gọi LPR → vẽ nhãn; lưu `_last_lpr_plates_result` |
| `_update_wrong_path` / `_browse_wrong_folder` / `_open_wrong_folder` | Quản lý thư mục lưu ảnh sai (`v_wrong_folder`, 5 segment) |
| `_save_wrong_image` / `_save_wrong_page` | Copy ảnh hiện tại/trang vào wrong folder |
| `_extract_plate_from_filename` | @static: trích biển số từ tên file `sub_<plate>[_...]` |
| `_update_gt` | @static: upsert dòng `filename\tplate` trong `gt.txt` |
| `_save_lpr_error_image` / `_open_gt_folder` | Lưu ảnh full + crop biển số + cập nhật `gt.txt` |

#### `yolo_eval_mixin.py` → Mixin `YoloEvalMixin`
| Method | Mô tả |
|---|---|
| `_save_result` | Lưu ảnh đã annotate + kết quả detect ra file |
| `_start_map_calc` | Tính mAP so khớp với nhãn `.txt` (dùng `_iou_xywhn` từ `yolo_utils.py`) |

#### `yolo_eval_validate_mixin.py` → Mixin `YoloEvalValidateMixin`
| Method | Mô tả |
|---|---|
| `_validate_true_folder` | Validate thư mục true/false (positive/negative) — 1 method lớn duy nhất (~545 dòng), tách riêng file vì lý do kích thước |

#### `yolo_video_mixin.py` → Mixin `YoloVideoMixin`
| Method / Hằng số | Mô tả |
|---|---|
| `_open_video_detect` | Dialog chọn nguồn video (file / RTSP / YouTube / webcam) |
| `_resolve_youtube_stream` (module-level) | yt-dlp: link YouTube + độ phân giải → (stream URL, title, is_live), chạy nền |
| `_YT_QUALITY_FORMATS` / `_YT_QUALITY_DEFAULT` (module-level) | Map nhãn độ phân giải → format string yt-dlp |

#### `yolo_video_window_mixin.py` → Mixin `YoloVideoWindowMixin`
| Method | Mô tả |
|---|---|
| `_launch_video_window` | Cửa sổ detect liên tục: worker thread đọc frame + model, main thread poll queue 16ms, overlay LPR, seek bar |

#### `yolo_layout_mixin.py` → Mixin `YoloLayoutMixin`
| Method | Mô tả |
|---|---|
| `_build_toolbar` | Build toolbar: chọn model 1/2/3, cấu hình conf/iou/LPR/wrong-folder |
| `_build_content` | Build panel nội dung chính: 2 canvas so sánh model, sidebar Treeview, filter, `DetTablePanel`, grid panel |

Disk cache: `{folder}/.kztek_det_cache.json` — persist giữa session; validate model path + iou khi load
Session keys: `yolo.session.folder`, `yolo.session.image`
Hỗ trợ: YOLO v8/v11, dual-model, drag-drop, detect all + filter class/size + grid thumbnail panel + session restore + LPR overlay (crop bbox → API → vẽ biển số)
Nguồn video: file / RTSP / HTTP / webcam / **YouTube URL** (yt-dlp resolve → cv2.VideoCapture); yêu cầu `pip install yt-dlp` (flag `_YTDLP_OK`); history key `h.yolo.youtube_url`
YouTube độ phân giải: combobox readonly (Best/1080p/720p/480p/360p/240p/Worst) → `_YT_QUALITY_FORMATS` map sang yt-dlp `format` string; lưu lựa chọn cuối qua `_bind_cfg("yolo.youtube_quality", ...)` (không dùng history vì giá trị cố định)
Seek bar (thanh tua): hiện với file video HOẶC YouTube VOD (`enable_seek=True`, `is_live=False` từ yt-dlp); ẩn với webcam/RTSP/YouTube livestream — `_launch_video_window(..., enable_seek=bool)`

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
