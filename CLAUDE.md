# CLAUDE.md — KZTEK Image Tools

## Tổng quan dự án

**KZTEK Image Tools** — ứng dụng desktop Python/Tkinter hỗ trợ chuẩn bị dữ liệu và huấn luyện mô hình YOLO cho hệ thống nhận dạng biển số (iParking).

| File / Thư mục | Vai trò |
|---|---|
| `train-image-tool.py` | Entry point chính |
| `models/` | File model YOLO (`yolo11n.pt`, `yolo26n.pt`, `best.pt`) |
| `tool/core/app.py` | `App(Tk)` — khung cửa sổ + Notebook 12 tab |
| `tool/core/settings.py` | Đọc/ghi `.kztek_tools_settings.json`; `_bind_cfg(key, var)` |
| `tool/core/constants.py` | Màu KZTEK, font, extension, hằng số API |
| `tool/core/ui_helpers.py` | Widget tái dùng: logbox, folder row, progressbar, style |
| `tool/core/imports.py` | Kiểm tra optional dependencies (cv2, requests, TTS…) |
| `tool/features/dataset/` | Tab + logic: Split, Rename, Crop, LabelNorm |
| `tool/features/annotation/` | Tab: BBox Editor, Checker, OCR |
| `tool/features/collection/` | Tab + API: iParking, Lotte, Parkingv8/v6 |
| `tool/features/analysis/` | Tab + logic: Stats, Plate Search, core_gt |
| `tool/features/detection/` | Tab: YOLO Detect, LPR Tester |
| `tool/features/training/` | Tab: YOLO Train |
| `tool/utils/` | Widget/tiện ích dùng chung: BadImageViewer, migrate_structure |
| `.kztek_tools_settings.json` | Persistence tất cả cài đặt người dùng |

### 12 Tab hiện có

```
✂ Split | ✏ Rename | 🖼 Crop | ⚙ LabelNorm | 🖊 BBox Editor
🅻 LotteImage | 🅿 Parkingv8Image | ✔ Checker | 📊 Stats
🔎 Plate Search | 🤖 YOLO Detect | 🚀 Train
```

### Palette màu (KZTEK brand)

```python
BG      = "#1e1e2e"   # nền chính (dark)
CARD    = "#2a2a3e"   # card/panel
ACCENT  = "#F05922"   # cam KZTEK — CTA, highlight
ACCENT2 = "#4A3F8C"   # navy — button thứ cấp
TEXT    = "#e0e0f0"
DIM     = "#9090b0"
SUCCESS = "#4caf50"
```

---

## Quy tắc bắt buộc — áp dụng cho MỌI thay đổi UI

### 1. Lưu lịch sử & tự động load tất cả ô nhập

**Mọi Entry/Combobox/Text** mà người dùng gõ tay đều phải:

- **Lưu lịch sử** N giá trị gần nhất (mặc định N=20) vào `.kztek_tools_settings.json`
- **Auto-load** danh sách lịch sử khi khởi động
- Cho phép chọn lại giá trị cũ qua **Combobox** (thay Entry đơn) hoặc **dropdown popup**
- Key lưu: `"history.<tab_name>.<field_name>"` → list[str]

**Cách triển khai chuẩn** — dùng helper trong `tool/core/settings.py`:

```python
def _bind_history(key: str, combo: ttk.Combobox, max_items: int = 20):
    """Bind Combobox với history list trong config."""
    saved = _CFG.get(key, [])
    combo["values"] = saved
    if saved:
        combo.set(saved[0])

    def _on_change(*_):
        val = combo.get().strip()
        if not val:
            return
        hist = list(_CFG.get(key, []))
        if val in hist:
            hist.remove(val)
        hist.insert(0, val)
        _CFG[key] = hist[:max_items]
        combo["values"] = _CFG[key]
        _cfg_save()

    combo.bind("<FocusOut>", _on_change)
    combo.bind("<Return>",   _on_change)
```

**Quan trọng:**
- Ô đường dẫn thư mục/file → sau khi chọn qua `filedialog` cũng phải ghi vào history
- Ô Entry số (epochs, batch…) → cũng lưu history qua `_bind_cfg` + history list
- Không lưu lịch sử: slider, checkbox, radiobutton, combobox readonly với giá trị cố định

---

### 2. UI phải hiển thị đầy đủ — không bị che, phải cuộn được

**Mọi tab** phải bọc nội dung trong canvas có scrollbar dọc:

```python
# Pattern chuẩn cho tab có nhiều widget
def _build(self):
    # Tạo scrollable container
    canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
    vsb = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=vsb.set)
    vsb.pack(side=RIGHT, fill=Y)
    canvas.pack(side=LEFT, fill=BOTH, expand=True)

    inner = Frame(canvas, bg=BG)
    canvas_window = canvas.create_window((0, 0), window=inner, anchor="nw")

    def _on_resize(e):
        canvas.itemconfig(canvas_window, width=e.width)
    canvas.bind("<Configure>", _on_resize)

    def _on_frame_resize(e):
        canvas.configure(scrollregion=canvas.bbox("all"))
    inner.bind("<Configure>", _on_frame_resize)

    # Scroll bằng chuột
    def _on_mousewheel(e):
        canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
    canvas.bind_all("<MouseWheel>", _on_mousewheel)

    # ── build widgets vào `inner` thay vì `self` ──
    self._build_content(inner)
```

**Quy tắc bổ sung:**
- Window `Toplevel` (chart, history, checkpoint, aug preview) tối thiểu `resizable(True, True)`
- Tất cả Treeview phải có cả scrollbar dọc lẫn ngang
- Không dùng `pack_propagate(False)` hoặc kích thước cố định che khuất widget dưới
- Khi màn hình nhỏ hơn `minsize`, app phải cuộn — không clip

---

### 3. Phím tắt bắt buộc

Mọi tab đều phải đăng ký các phím tắt này (bind vào `root` hoặc `self`):

| Phím | Hành động |
|---|---|
| `Ctrl+O` | Mở file / thư mục (ưu tiên action chính của tab) |
| `Ctrl+S` | Lưu / export kết quả (nếu có) |
| `F5` | Chạy / bắt đầu xử lý (Start, Train, Detect…) |
| `Escape` | Dừng tiến trình đang chạy |
| `Ctrl+Z` | Undo (với BBox Editor, Rename) |
| `Ctrl+A` | Chọn tất cả (Listbox, Treeview) |
| `Delete` | Xóa item đang chọn |
| `F1` | Hiện tooltip / help ngắn cho tab hiện tại |
| `Ctrl+Tab` | Chuyển tab kế tiếp |
| `Ctrl+Shift+Tab` | Chuyển tab trước |
| `←` / `→` | Điều hướng ảnh trước/sau (các tab xem ảnh) |

**Cách bind phím tắt chuẩn:**

```python
def _bind_shortcuts(self):
    self.root.bind_all("<Control-o>", lambda e: self._open_action())
    self.root.bind_all("<F5>",        lambda e: self._start_action())
    self.root.bind_all("<Escape>",    lambda e: self._stop_action())
    # Chỉ bind khi tab này active để tránh xung đột
```

**Tooltip phím tắt:** Hiển thị trong `title` của button hoặc `tooltip` khi hover.

---

### 4. Double-click phóng to ảnh

**Mọi widget hiển thị ảnh** (Label, Canvas dùng để show ảnh) đều phải hỗ trợ **double-click để phóng to** trong cửa sổ `Toplevel` riêng.

**Pattern chuẩn** — dùng helper `_zoom_image_window` trong `tool/core/ui_helpers.py`:

```python
def _zoom_image_window(root, pil_img: Image.Image, title: str = "Phóng to ảnh"):
    """Mở Toplevel hiển thị ảnh phóng to, hỗ trợ cuộn chuột để zoom thêm."""
    win = Toplevel(root)
    win.title(title)
    win.configure(bg=BG)
    win.resizable(True, True)
    win.protocol("WM_DELETE_WINDOW", win.destroy)

    # Fit ảnh vào 80% màn hình
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    max_w, max_h = int(sw * 0.8), int(sh * 0.8)
    img = pil_img.copy()
    img.thumbnail((max_w, max_h), Image.LANCZOS)

    cv = Canvas(win, bg="#0d0d1a", highlightthickness=0,
                width=img.width, height=img.height)
    cv.pack(fill=BOTH, expand=True)
    tk_img = ImageTk.PhotoImage(img)
    cv.create_image(img.width // 2, img.height // 2, anchor=CENTER, image=tk_img)
    cv._tk_img = tk_img   # giữ reference

    # Ctrl+W hoặc Escape đóng cửa sổ
    win.bind("<Escape>", lambda _: win.destroy())
    win.bind("<Control-w>", lambda _: win.destroy())
    win.geometry(f"{img.width}x{img.height}")
    win.lift(); win.focus_set()
```

**Cách bind vào widget ảnh:**

```python
# Label hiển thị ảnh
img_label = Label(parent, ...)
img_label.bind("<Double-Button-1>",
    lambda e, img=pil_img: _zoom_image_window(self.root, img, "Tên ảnh"))

# Canvas hiển thị ảnh
canvas.bind("<Double-Button-1>",
    lambda e: _zoom_image_window(self.root, self._current_pil_img))
```

**Quy tắc bắt buộc:**
- Tất cả tab có hiển thị ảnh (`annotation/tab_bbox.py`, `annotation/tab_checker.py`, `detection/tab_yolo.py`, `dataset/tab_crop.py`, `analysis/tab_plate_search.py`, `collection/tab_lotte.py`, `collection/tab_parkingv8.py`) đều phải bind double-click
- Tooltip "Double-click để phóng to" trên widget ảnh (dùng `tooltip` hoặc `title`)
- Cửa sổ zoom không block UI chính (`Toplevel`, không phải `Dialog`)
- Nếu ảnh chưa load (widget rỗng), double-click không làm gì

---

### 5. Luôn hỏi lại hoặc đề xuất nâng cao

Trước khi implement bất kỳ tính năng nào:

1. **Hỏi xác nhận** nếu yêu cầu mơ hồ hoặc có nhiều cách làm
2. **Đề xuất nâng cao** nếu có cách làm tốt hơn yêu cầu gốc
3. **Nêu trade-off** ngắn gọn (1-2 dòng) giữa các lựa chọn
4. Không implement khi chưa được xác nhận nếu thay đổi ảnh hưởng nhiều file

**Ví dụ:**
```
User: "Thêm nút clear log"
Claude: "Thêm nút Clear Log (Ctrl+L). Đề xuất thêm: 
  - Auto-scroll tới cuối khi có log mới (hiện tại đã có)
  - Lưu log ra file .txt (Ctrl+Shift+S)?
  Implement cơ bản hay cả 2 tính năng?"
```

---

### 6. Ghi nhận lỗi — không để tái hiện

**Mỗi khi gặp lỗi** (lỗi runtime, lỗi logic, lỗi khi implement) phải:

1. **Ghi vào `ERRORS.md`** ở thư mục gốc dự án ngay khi phát hiện
2. **Đọc `ERRORS.md`** trước khi bắt đầu implement bất kỳ task nào để tránh lặp lại
3. Mỗi entry gồm: mô tả lỗi, nguyên nhân gốc, cách sửa đúng

**Cấu trúc entry trong `ERRORS.md`:**

```markdown
## [E001] Tên lỗi ngắn gọn
- **File:** tool/tab_xxx.py
- **Triệu chứng:** Lỗi hiển thị / exception message
- **Nguyên nhân:** Giải thích gốc rễ
- **Cách sửa:** Giải pháp cụ thể
- **Ngày:** YYYY-MM-DD
```

**Loại lỗi cần ghi:**
- `Edit` tool báo lỗi "File has been modified" → re-read trước khi edit
- `old_string` không match do indent/whitespace → copy chính xác từ Read output
- Import thiếu dẫn đến `NameError` khi chạy
- Widget bị destroy trước khi callback chạy (`after()` timing)
- Lỗi thread safety (update UI từ thread phụ không qua `root.after()`)

---

## Quy ước code

### Settings / persistence

```python
# Lưu đường dẫn thư mục
_bind_cfg("tab_name.field", self.var)

# Lưu lịch sử nhập tay
_bind_history("history.tab_name.field", self.combo_widget)

# Đọc thư mục cuối cùng cho initialdir
_cfg_dir("tab_name.field")
```

### Widget chuẩn cho ô đường dẫn

```python
# Dùng Combobox thay Entry để hiện history
combo = ttk.Combobox(parent, textvariable=var, font=F_MAIN)
_bind_history("history.split.src_dir", combo)
btn = Button(parent, text="Chọn…", command=lambda: _pick_dir(var, combo))
```

### Thêm tab mới

1. Tạo file trong `tool/features/<feature>/tab_<name>.py` — class kế thừa `Frame`
2. Import trong `tool/core/app.py`: `from ..features.<feature>.tab_<name> import ...`
3. Đăng ký vào `_tab_defs` trong `App.__init__`
4. Settings key dùng prefix `"<name>."` để tránh xung đột
5. Bọc nội dung trong scrollable canvas (xem mục 2)
6. Bind phím tắt trong `_bind_shortcuts()` gọi từ `__init__`

---

## Môi trường & chạy

```bash
# Chạy app
python train-image-tool.py

# Chạy app cũ (standalone YOLO detect)
python app.py

# Build (nếu cần)
buildTool.bat
```

**Dependencies chính:** `tkinter`, `Pillow`, `opencv-python`, `ultralytics`, `matplotlib`, `tkinterdnd2`

**Python:** 3.10+ | **OS:** Windows 10/11 | **GPU:** CUDA optional

---

## Lưu ý đặc biệt

- `tool/core/settings.py` là nguồn sự thật duy nhất cho persistence — không tạo file config riêng
- Màu `ACCENT = "#F05922"` là màu cam KZTEK — dùng đúng, không dùng đỏ tươi
- Mọi `Toplevel` window phải `win.protocol("WM_DELETE_WINDOW", win.withdraw)` để tái dùng
- Thread training chạy subprocess riêng (không block UI) — giữ pattern này
- Hỏi trước khi sửa `tool/features/dataset/core_*.py` — các file này được dùng chung nhiều tab
- Import convention: files trong `features/*/` dùng `from ...core.X import` (3 dots); trong `utils/` dùng `from ..core.X import` (2 dots)
