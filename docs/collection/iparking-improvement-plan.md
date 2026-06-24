# iParking Image — Kế hoạch cải tiến toàn diện

> Tài liệu: `docs/collection/iparking-improvement-plan.md`  
> Ngày: 2026-06-24  
> Phạm vi: `tool/features/collection/` — LotteImage, Parkingv8, Parkingv6

---

## Tổng quan các vấn đề

| # | Vấn đề | Mức độ | Độ phức tạp |
|---|---|---|---|
| I | Không dùng đa luồng khi 1 ngày / threads > ngày | Cao | Thấp |
| II | Lặp lại cùng khung giờ, thiếu đa dạng thời gian | Rất cao | Cao |
| III | Gọi lại API dù đã có kết quả cũ | Cao | Cao (liên quan II) |
| IV.a | Tiến độ thô (chỉ lưu ngày), crash mất progress | Trung bình | Trung bình |
| IV.b | Không kiểm tra ảnh hỏng sau download | Trung bình | Thấp |
| IV.c | Sleep cố định, không adaptive | Thấp | Thấp |
| IV.d | Không có preview trước khi tải | Trung bình | Trung bình |
| IV.e | Race condition nhỏ trong _done_days | Thấp | Thấp |
| V | tab_iparking_image.py vượt giới hạn 800 dòng (1811 dòng) | Cao | Trung bình |

---

## Thứ tự thực hiện

```
Bước 0  →  Bước 1  →  Bước 2  →  Bước 3  →  Bước 4  →  Bước 5
Refactor    Time-slice   EventDB     Planner     Workers     Tab UI
(prereq)    (quick win)  (core dep)  (plan)      (scan mode) (3-phase)

Song song bất kỳ lúc nào:
  Bước 6 (verify ảnh)
  Bước 7 (adaptive sleep)
  Bước 9 (thread safety)

Sau khi hoàn thành Bước 5:
  Bước 8 (preview scan UI)
```

---

## Bước 0 — Refactor tab_iparking_image.py

### Mục tiêu
Tách file 1811 dòng thành 4 file đúng kiến trúc, mỗi file ≤ 500 dòng.

### File mới / sửa đổi

| File | Nội dung | Dòng ước tính |
|---|---|---|
| `tab_iparking_image.py` | Frame chính + build skeleton + dispatcher | ~400 |
| `iparking_settings_panels.py` (mới) | `_build_time`, `_build_output`, `_build_common_limits`, `_build_lotte_settings`, `_build_p8_settings`, `_build_p6_settings` | ~500 |
| `iparking_runner.py` (mới) | `_run_parallel_lotte/p8/p6`, `_run_worker`, polling, progress | ~350 |
| `iparking_stats_ui.py` (mới) | `_show_stats`, `_stats_rebuild`, `_stats_populate`, 3 tab stats, `_scan_stats` | ~400 |

### Chi tiết tách

**`iparking_settings_panels.py`** — Mixin class `IParkingSettingsMixin`:
```python
class IParkingSettingsMixin:
    """Chứa tất cả _build_* methods cho các panel cài đặt."""
    def _build_time(self, p): ...
    def _build_output(self, p): ...
    def _build_common_limits(self, p): ...
    def _build_lotte_settings(self, p): ...
    def _build_p8_settings(self, p): ...
    def _build_p6_settings(self, p): ...
    def _toggle_adv(self, src): ...
```

**`iparking_runner.py`** — Mixin class `IParkingRunnerMixin`:
```python
class IParkingRunnerMixin:
    """Chứa logic parallel run, worker dispatch, polling, progress."""
    def _prepare_run(self): ...
    def _get_common_cfg(self): ...
    def _start_lotte(self, from_d, to_d, out): ...
    def _start_p8(self, from_d, to_d, out): ...
    def _start_p6(self, from_d, to_d, out): ...
    def _run_worker(self): ...
    def _run_parallel_lotte(self, cfg, n): ...
    def _run_parallel_p6(self, cfg, n): ...
    def _run_parallel_p8(self, cfg, n): ...
    def _poll(self): ...
    def _aggregate_stats(self): ...
    def _update_progress(self, s): ...
    def _refresh_stat_lbl(self, s): ...
```

**`iparking_stats_ui.py`** — Mixin class `IParkingStatsMixin`:
```python
class IParkingStatsMixin:
    """Stats window, scan_stats, chart/table rendering."""
    def _show_stats(self): ...
    def _stats_rebuild(self): ...
    def _stats_populate(self, ...): ...
    def _stats_tab_summary(self, ...): ...
    def _stats_tab_date(self, ...): ...
    def _stats_tab_buoi(self, ...): ...
    @staticmethod
    def _scan_stats(out_path): ...
    @staticmethod
    def _make_tree(parent, cols, ...): ...
    def _make_chart(self, parent, draw_fn): ...
```

**`tab_iparking_image.py`** sau refactor:
```python
from .iparking_settings_panels import IParkingSettingsMixin
from .iparking_runner import IParkingRunnerMixin
from .iparking_stats_ui import IParkingStatsMixin

class IParkingImageTab(Frame, IParkingSettingsMixin, IParkingRunnerMixin, IParkingStatsMixin):
    def __init__(self, master, root): ...
    def _build(self): ...          # chỉ gọi _build_* và tổ hợp layout
    def _build_controls(self, p): ...
    def _build_progress(self, p): ...
    def _build_dashboard(self, p): ...
    def _build_log(self, p): ...
    def _on_source_change(self, *_): ...
    # Actions nhỏ: _browse, _open_out, _toggle_pause, _stop, _on_done,
    #              _retry_failed, _show_bad_images, _consolidate,
    #              _migrate_folder, _clear_progress, _log, _log_batch,
    #              _show_dashboard, _hide_dashboard
```

### Kiểm tra sau refactor
- Chạy `python train-image-tool.py` → tab iParking Image hiển thị đúng
- Tất cả nút hoạt động bình thường
- Không có ImportError

---

## Bước 1 — Time-slicing khi 1 ngày / threads > ngày

### Vấn đề cụ thể
```
# Hiện tại: 1 ngày, 4 luồng
groups = [['2026-01-01'], [], [], []]   # T2, T3, T4 rỗng, lãng phí
```

### Giải pháp — Hàm `_split_time_windows`

Thêm vào `iparking_runner.py` (hoặc `lotte_image.py` làm staticmethod dùng chung):

```python
@staticmethod
def _split_time_windows(from_str: str, to_str: str, n: int) -> list[tuple]:
    """
    Chia khoảng [from_str, to_str] thành n phần đều nhau.
    Trả về list[(d_from, d_to, label)] giống định dạng _day_list().
    Dùng khi n_days < n_threads.

    Label: "YYYY-MM-DD/HH" cho slice trong ngày,
           "YYYY-MM-DD"    cho slice theo ngày đủ.
    """
    from_dt = _parse_dt(from_str)
    to_dt   = _parse_dt(to_str)
    total_s = (to_dt - from_dt).total_seconds()
    slice_s = total_s / n
    result  = []
    for i in range(n):
        s = from_dt + timedelta(seconds=i * slice_s)
        e = from_dt + timedelta(seconds=(i + 1) * slice_s)
        if i == n - 1:
            e = to_dt   # tránh lệch làm tròn
        label = s.strftime("%Y-%m-%d/%H:%M") if s.date() == e.date() else s.strftime("%Y-%m-%d")
        result.append((s.strftime("%Y-%m-%dT%H:%M:%S"),
                       e.strftime("%Y-%m-%dT%H:%M:%S"),
                       label))
    return result
```

### Logic dispatch trong `_run_parallel_lotte/p8/p6`

```python
all_days = Worker._day_list(from_d, to_d)
pending  = [d for d in all_days if d[2] not in done_days]

if len(pending) >= n:
    # Chia theo ngày (behavior hiện tại)
    groups = [[] for _ in range(n)]
    for i, day in enumerate(pending):
        groups[i % n].append(day)
else:
    # Chia theo time-window trong khoảng pending
    if pending:
        actual_from = pending[0][0]   # from của ngày chưa tải đầu tiên
        actual_to   = pending[-1][1]  # to của ngày chưa tải cuối cùng
    else:
        actual_from, actual_to = from_d, to_d
    windows = _split_time_windows(actual_from, actual_to, n)
    groups = [[w] for w in windows]   # mỗi thread 1 window
```

### Thay đổi trong Worker.run()
Worker hiện tại nhận `days_list: list[(from, to, label)]`.  
Time-slice windows có cùng format → **không cần thay đổi Worker**, chỉ thay đổi cách tạo `groups` trong coordinator.

### Kiểm tra
- 1 ngày, 4 luồng → 4 thread chạy, mỗi cái xử lý 6 giờ
- 3 ngày, 4 luồng → T1: ngày 1, T2: ngày 2, T3: ngày 3, T4: half-day window (nếu còn)
- 10 ngày, 4 luồng → behavior cũ (round-robin)
- Log phải hiển thị: `[T1] 2026-01-01 00:00 → 2026-01-01 05:59`

---

## Bước 2 — EventDB (SQLite cache)

### Mục tiêu
- File: `tool/features/collection/event_db.py` (≤ 300 dòng)
- Thay thế `.lotte_done.json`, `.p6_done.json`, `.p8_done.json`
- Lưu metadata sự kiện để tái dùng và planning

### Schema

```sql
-- Metadata sự kiện đã scan từ API
CREATE TABLE IF NOT EXISTS events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source        TEXT    NOT NULL,          -- 'lotte' | 'p8' | 'p6'
    event_id      TEXT,                      -- ID gốc từ API
    date          TEXT    NOT NULL,          -- 'YYYY-MM-DD'
    hour          INTEGER NOT NULL,          -- 0-23
    minute        INTEGER NOT NULL,          -- 0-59
    lane          TEXT    NOT NULL,
    vtype         TEXT    NOT NULL,          -- loại xe đã phân loại
    plate         TEXT,
    has_gt        INTEGER DEFAULT 0,         -- 1 nếu có biển đăng ký
    image_refs    TEXT,                      -- JSON array: path/url mỗi ảnh
    downloaded    INTEGER DEFAULT 0,         -- 0=chưa, 1=đã tải
    save_path     TEXT,                      -- đường dẫn file đã lưu
    scanned_at    TEXT,
    downloaded_at TEXT,
    UNIQUE(source, event_id)
);

-- Tiến độ scan theo khoảng thời gian
CREATE TABLE IF NOT EXISTS scan_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source      TEXT    NOT NULL,
    date        TEXT    NOT NULL,            -- 'YYYY-MM-DD'
    hour_from   INTEGER NOT NULL DEFAULT 0, -- 0-23
    hour_to     INTEGER NOT NULL DEFAULT 23,-- 0-23
    status      TEXT    NOT NULL,           -- 'scanning' | 'done' | 'error'
    event_count INTEGER DEFAULT 0,
    scanned_at  TEXT,
    UNIQUE(source, date, hour_from, hour_to)
);

CREATE INDEX IF NOT EXISTS idx_events_slot
    ON events(source, lane, vtype, date, hour, minute);

CREATE INDEX IF NOT EXISTS idx_events_dl
    ON events(source, downloaded);

CREATE INDEX IF NOT EXISTS idx_scan_log
    ON scan_log(source, date, hour_from, hour_to, status);
```

### Class EventDB

```python
class EventDB:
    DB_FILENAME = ".iparking_cache.db"

    def __init__(self, output_dir: Path):
        self._path = output_dir / self.DB_FILENAME
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._lock = threading.Lock()
        self._create_tables()

    # ── Scan log ─────────────────────────────────────────────────────────────

    def is_scanned(self, source: str, date: str,
                   hour_from: int = 0, hour_to: int = 23) -> bool:
        """True nếu khoảng thời gian đã scan xong."""

    def mark_scan_start(self, source: str, date: str,
                        hour_from: int = 0, hour_to: int = 23): ...

    def mark_scan_done(self, source: str, date: str,
                       hour_from: int = 0, hour_to: int = 23,
                       count: int = 0): ...

    def get_scanned_dates(self, source: str) -> set[str]:
        """Thay thế _done_days từ JSON cũ."""

    # ── Events ───────────────────────────────────────────────────────────────

    def insert_events(self, source: str, events: list[dict]) -> int:
        """
        Batch insert. events là list dict với keys:
          event_id, date, hour, minute, lane, vtype, plate,
          has_gt, image_refs (list), scanned_at
        Trả về số dòng thực sự chèn (bỏ qua duplicate).
        """

    def mark_downloaded(self, source: str, event_id: str, save_path: str): ...

    def get_events(self,
                   source: str,
                   date: str = None,
                   lane: str = None,
                   vtype: str = None,
                   downloaded: int = None,
                   hour_from: int = None,
                   hour_to: int = None) -> list[dict]: ...

    # ── Analytics ────────────────────────────────────────────────────────────

    def get_coverage(self, source: str) -> dict:
        """
        Trả về dict phân tích:
        {
          'by_slot': {(lane, vtype, date, hour, minute_bucket): count_downloaded},
          'by_hour': {(lane, vtype, hour): {'total': N, 'downloaded': M}},
          'lanes': [str],
          'vtypes': [str],
          'dates': [str],
        }
        minute_bucket = minute // 5   (mỗi slot = 5 phút)
        """

    def count_summary(self, source: str) -> dict:
        """{'total_scanned': N, 'downloaded': M, 'pending': K}"""

    def close(self): ...
```

### Migration từ JSON cũ
Khi `EventDB.__init__()` được gọi, tự động migrate:
```python
def _migrate_legacy(self, output_dir: Path):
    """Đọc .lotte_done.json → insert vào scan_log nếu DB còn mới."""
    for fname, source in [(".lotte_done.json", "lotte"),
                          (".p8_done.json",    "p8"),
                          (".p6_done.json",    "p6")]:
        f = output_dir / fname
        if f.exists() and not self.get_scanned_dates(source):
            try:
                dates = json.loads(f.read_text(encoding="utf-8"))
                for d in dates:
                    self.mark_scan_done(source, d, 0, 23, 0)
            except Exception:
                pass
```

---

## Bước 3 — EventPlanner (time-diversity planning)

### Mục tiêu
- File: `tool/features/collection/event_planner.py` (≤ 250 dòng)
- Phân tích coverage từ EventDB → tạo danh sách sự kiện ưu tiên tải

### Thuật toán "Time-Rotating Sampling"

**Vấn đề:** Nếu quota 7h là 34 ảnh, và tất cả ngày đều có xe nhiều lúc 7:00-7:04,  
→ mỗi ngày đều lấy từ 7:00, quota đầy, bỏ qua 7:05-7:59.

**Giải pháp: Slot-based priority scoring**
```
Slot = 5 phút (có thể cấu hình: 5, 10, 15 phút)

Với mỗi (lane, vtype, hour):
  Đếm số ảnh đã tải theo từng slot trong giờ:
    slot 0: 7:00-7:04 → 34 ảnh
    slot 1: 7:05-7:09 → 0  ảnh
    slot 2: 7:10-7:14 → 0  ảnh
    ...

Priority score của event = (slot_count_of_my_slot + 1) ^ -1
  → slot ít ảnh hơn = score cao hơn = ưu tiên tải trước

Target: phân phối đều qua tất cả slot trong giờ
```

### Class EventPlanner

```python
class EventPlanner:
    def __init__(self, db: EventDB, source: str, slot_minutes: int = 5):
        self._db     = db
        self._source = source
        self._slot   = slot_minutes   # kích thước slot tính bằng phút

    def analyze(self) -> dict:
        """
        Phân tích coverage hiện tại.
        Trả về dict:
        {
          'gaps': [(lane, vtype, hour, slot_idx, available_count, downloaded_count)],
          'coverage_pct': float,    # % slot đã có ≥ 1 ảnh
          'worst_slots': [...],     # 10 slot bị bỏ qua nhiều nhất
          'best_lanes': [...],      # lane có data đa dạng nhất
        }
        """

    def make_download_plan(self,
                           target_per_slot: int = 5,
                           max_total: int = 0) -> list[dict]:
        """
        Tạo danh sách event cần tải, sắp xếp theo priority.
        
        Thuật toán:
        1. Lấy coverage từ DB
        2. Với mỗi event chưa tải: tính priority_score
           = 1 / (slot_count + 1)  với slot_count = số ảnh đã có trong slot này
        3. Sort descending by score
        4. Nếu max_total > 0: cắt danh sách
        
        Trả về list[dict] với keys: event_id, lane, vtype, date, hour, minute,
                                    image_refs, priority_score
        """

    def get_slot_idx(self, minute: int) -> int:
        return minute // self._slot

    def get_next_batch(self, batch_size: int = 100) -> list[dict]:
        """Lấy batch tiếp theo chưa tải, ưu tiên slot underrepresented."""
```

### Cách sử dụng trong flow
```python
# Sau scan xong:
planner = EventPlanner(db, source="lotte", slot_minutes=5)
plan    = planner.make_download_plan(target_per_slot=5)

# Download theo plan:
for event in plan:
    download_image(event["image_refs"])
    db.mark_downloaded(source, event["event_id"], save_path)
```

---

## Bước 4 — Cập nhật Workers (chế độ Scan / Download)

### Thay đổi chung cho cả 3 workers

Thêm parameter `mode` và `event_db`:

```python
class LotteWorker:
    def __init__(self, cfg, log_q, stat_q,
                 pause_event=None, thread_id=0, days_list=None,
                 shared=None, send_done=True, global_total_days=None,
                 mode: str = 'full',      # 'full' | 'scan_only' | 'download_only'
                 event_db=None):          # EventDB instance (cho scan/download mode)
```

### Mode `scan_only`

Trong `_collect_day()`:
```python
if self._mode == 'scan_only':
    # Kiểm tra DB: đã scan chưa?
    if self._db.is_scanned(self._source, label, hour_from, hour_to):
        self._log(f"  ⏭ NGÀY {label} đã scan trong DB — bỏ qua")
        continue
    self._db.mark_scan_start(self._source, label)
    events_batch = []
    # ... gọi API như bình thường ...
    # Với mỗi record: extract metadata, KHÔNG download ảnh
    for rec in recs:
        event_meta = self._extract_meta(rec)    # hàm mới
        events_batch.append(event_meta)
    self._db.insert_events(self._source, events_batch)
    self._db.mark_scan_done(self._source, label, count=len(events_batch))
```

**Hàm `_extract_meta(rec)`** (thêm vào mỗi worker):
```python
def _extract_meta(self, rec: dict) -> dict:
    """Extract metadata từ API record, không download ảnh."""
    # Lấy datetime, lane, vtype, plate, has_gt
    # Lấy image_refs (list path/url) nhưng KHÔNG fetch
    return {
        'event_id': str(rec.get("Id") or ""),
        'date':     dt.strftime("%Y-%m-%d"),
        'hour':     dt.hour,
        'minute':   dt.minute,
        'lane':     lane,
        'vtype':    vtype,
        'plate':    plate,
        'has_gt':   1 if gt_plate else 0,
        'image_refs': image_refs_list,  # list[str] path/url
        'scanned_at': datetime.now().isoformat(),
    }
```

### Mode `download_only`

```python
def run_download_only(self, plan: list[dict]):
    """Download ảnh theo plan từ EventPlanner."""
    for event in plan:
        if self._stop.is_set():
            break
        self._pause.wait()
        for img_ref in event["image_refs"]:
            img = self._api.fetch_image(img_ref)
            if img is not None:
                save_path = self._save_to_disk(img, event)
                if save_path:
                    self._db.mark_downloaded(
                        self._source, event["event_id"], str(save_path))
                    self.stats["saved"] += 1
            self.stats["found"] += 1
        self._push()
```

### Mode `full` (backward compatible)
Không thay đổi — chạy như hiện tại. DB được update song song nếu `event_db` được truyền vào.

### Ghi vào DB trong mode `full` (optional enhancement)
Khi `event_db` không None và mode là `full`:
- Sau khi save ảnh thành công → `db.mark_downloaded(source, event_id, path)`
- Sau khi scan 1 ngày → `db.mark_scan_done(source, date)`
- Backward compatible: nếu `event_db=None` → chạy như cũ

---

## Bước 5 — Cập nhật Tab UI (3-phase mode)

### Thay đổi UI

**Thêm vào `_build_common_limits` hoặc panel riêng:**

```
┌─ Chế độ thu thập ──────────────────────────────────────────┐
│ ○ Tự động (1 bước)    ● 3 bước: Scan → Phân tích → Tải    │
└────────────────────────────────────────────────────────────┘
```

**Panel 3 bước (hiện khi chọn mode 3 bước):**
```
┌─ Tiến trình 3 bước ─────────────────────────────────────────────┐
│  [1. Scan sự kiện ▶]  [2. Phân tích 📊]  [3. Tải ảnh ▶]        │
│                                                                   │
│  DB: 1,234 sự kiện scan  |  Đã tải: 345  |  Chờ tải: 889       │
│  Coverage: 23% slot  |  Slot size: [5▼] phút                    │
└────────────────────────────────────────────────────────────────-┘
```

**Panel phân tích (hiện sau bước 2):**
```
┌─ Phân tích đa dạng thời gian ──────────────────────────────────┐
│  Lane: làn_1     Loại: o_to                                     │
│  Giờ 7: ████░░░░░░░░  slot 0: 34  slot 1: 0  slot 2: 0 ...    │
│  Giờ 8: ██████░░░░░░  slot 0: 45  slot 1: 12 ...               │
│  [Tải ảnh theo plan ▶]   Target: [5] ảnh/slot                  │
└────────────────────────────────────────────────────────────────┘
```

### Thay đổi trong `iparking_runner.py`

Thêm 3 method:
```python
def _start_scan(self):
    """Khởi động workers ở mode scan_only."""
    db = self._get_or_create_db()
    # Khởi tạo workers với mode='scan_only', event_db=db
    ...

def _show_analysis(self):
    """Mở cửa sổ phân tích coverage từ DB."""
    db = self._get_or_create_db()
    planner = EventPlanner(db, source)
    analysis = planner.analyze()
    # Hiển thị trong Toplevel

def _start_download_from_plan(self):
    """Đọc plan từ DB, chạy workers ở mode download_only."""
    db = self._get_or_create_db()
    planner = EventPlanner(db, source)
    plan = planner.make_download_plan(
        target_per_slot=self.target_per_slot_var.get())
    # Khởi tạo workers với mode='download_only', plan=plan
    ...

def _get_or_create_db(self) -> EventDB:
    """Tạo hoặc lấy EventDB cho output_dir hiện tại."""
    out = Path(self.out_var.get().strip())
    if not hasattr(self, '_event_db') or self._db_path != out:
        self._event_db = EventDB(out)
        self._db_path  = out
    return self._event_db
```

---

## Bước 6 — Verify ảnh sau download (IV.b)

### Thay đổi trong `_save_image` của cả 3 workers

Sau khi `fpath.write_bytes(buf)`:
```python
# Verify: decode lại để xác nhận file hợp lệ
try:
    verify_buf = np.frombuffer(fpath.read_bytes(), np.uint8)
    verify_img = cv2.imdecode(verify_buf, cv2.IMREAD_UNCHANGED)
    if verify_img is None or verify_img.size < 300:
        fpath.unlink(missing_ok=True)
        self.stats["error"] += 1
        self._log(f"      ✗ Ảnh hỏng sau decode — đã xóa: {fpath.name}")
        return False
except Exception:
    pass   # không block nếu verify lỗi
```

**Ngưỡng `size < 300`:** ảnh hợp lệ nhỏ nhất ~10×10 px = 300 pixel,  
mọi file nhỏ hơn là noise/placeholder.

**File size check (bổ sung, nhanh hơn):**
```python
if fpath.stat().st_size < 1024:   # < 1KB → nghi ngờ
    # Log warning nhưng không xóa (có thể là ảnh thumbnail nhỏ)
    self._log(f"      ⚠ File nhỏ ({fpath.stat().st_size}B): {fpath.name}")
```

---

## Bước 7 — Adaptive sleep (IV.c)

### Thay đổi trong `_collect_day()` của cả 3 workers

```python
# Config
min_interval = cfg.get("sleep", 0.1)    # giây giữa các page (đổi ý nghĩa)
max_sleep    = 5.0                        # không sleep quá lâu

# Trong vòng lặp page:
t0 = time.time()
ok, data, ... = api.search(...)
elapsed = time.time() - t0

# Adaptive: nếu API đã mất đủ thời gian, không cần sleep thêm
remaining = max(0.0, min_interval - elapsed)
remaining = min(remaining, max_sleep)
if remaining > 0:
    time.sleep(remaining)
```

**Thay đổi label trong UI:** "Nghỉ (s):" → "Khoảng cách tối thiểu giữa page (s):"

**Config key:** `ip.sleep` giữ nguyên (backward compatible).

---

## Bước 8 — Preview scan UI (IV.d)

### Nút "Xem trước" thêm vào controls

```python
Button(f, text="🔍 Xem trước", command=self._preview_scan,
       bg=CARD, fg=TEXT, ...)
```

**`_preview_scan()`:**
1. Validate config (thời gian, thư mục, nguồn)
2. Gọi scan_only trên 1-2 ngày đầu (sample)
3. Hiển thị popup:
   - Ước tính tổng sự kiện (từ TotalItems của API)
   - Phân phối theo giờ (bar chart)
   - ETA download dựa trên tốc độ download sample
4. Hỏi "Tiếp tục không?" → nếu Yes: chạy full scan

### Popup structure
```
┌─ Xem trước — iParking Lotte ────────────────────────────────────┐
│  Khoảng: 2026-01-01 → 2026-01-31  (31 ngày)                    │
│  Nguồn: làn_A, làn_B, làn_C                                     │
│                                                                   │
│  Sample từ ngày đầu (3 phút scan):                              │
│    • Tổng sự kiện ước tính: ~45,000                             │
│    • Sự kiện/ngày trung bình: ~1,450                            │
│    • Phân phối giờ:                                             │
│      6h ████░░░  7h ██████████  8h ████████  ...               │
│                                                                   │
│  ETA nếu tải tất cả: ~2h 15m  (với 4 luồng)                    │
│  ETA nếu dùng plan (target 5/slot): ~35m                        │
│                                                                   │
│         [Hủy]   [Chạy đầy đủ]   [Chạy theo plan]               │
└─────────────────────────────────────────────────────────────────┘
```

---

## Bước 9 — Thread safety fix (IV.e)

### Vấn đề
Trong `LotteWorker.run()` (single-thread mode), `_history_load` được gọi không có lock,  
nhưng `_history_mark` có `hist_lock`. Khi parallel mode, 2 worker cùng đọc file → potential race.

### Sửa
Trong `_history_load()` của cả 3 workers:
```python
def _history_load(self, out: Path):
    with self._shared.hist_lock:   # THÊM lock khi đọc
        try:
            f = out / self._HISTORY_FILE
            if f.exists():
                self._done_days = set(json.loads(
                    f.read_text(encoding="utf-8")))
                self._log(f"Lịch sử: {len(self._done_days)} ngày đã tải.")
        except Exception:
            self._done_days = set()
```

Sau khi có EventDB (Bước 2): thay toàn bộ `.lotte_done.json` bằng `scan_log` table  
→ SQLite tự xử lý concurrent access, không cần lock thủ công.

---

## Tóm tắt file thay đổi

| File | Thao tác | Lý do |
|---|---|---|
| `tab_iparking_image.py` | Sửa (shrink) | Bước 0 refactor |
| `iparking_settings_panels.py` | **Tạo mới** | Bước 0 |
| `iparking_runner.py` | **Tạo mới** | Bước 0, 1, 5 |
| `iparking_stats_ui.py` | **Tạo mới** | Bước 0 |
| `event_db.py` | **Tạo mới** | Bước 2 |
| `event_planner.py` | **Tạo mới** | Bước 3 |
| `lotte_image.py` | Sửa | Bước 4, 6, 7, 9 |
| `parkingv8_image.py` | Sửa | Bước 4, 6, 7, 9 |
| `parkingv6_image.py` | Sửa | Bước 4, 6, 7, 9 |
| `CODE_GRAPH.md` | Cập nhật | Sau mỗi bước |

---

## Ràng buộc kích thước file

| File | Giới hạn | Ước tính sau |
|---|---|---|
| `tab_iparking_image.py` | 500 dòng | ~380 dòng |
| `iparking_settings_panels.py` | 500 dòng | ~480 dòng |
| `iparking_runner.py` | 300 dòng | ~280 dòng |
| `iparking_stats_ui.py` | 300 dòng | ~380 dòng (*) |
| `event_db.py` | 300 dòng | ~220 dòng |
| `event_planner.py` | 300 dòng | ~200 dòng |
| `lotte_image.py` | 800 dòng | ~650 dòng |
| `parkingv8_image.py` | 800 dòng | ~600 dòng |
| `parkingv6_image.py` | 800 dòng | ~600 dòng |

(*) `iparking_stats_ui.py` nếu vượt 300 dòng → tách chart rendering ra `iparking_charts.py`

---

## Checklist thực hiện

- [ ] **Bước 0** — Refactor tab_iparking_image.py (tách 3 mixin)
- [ ] **Bước 1** — Time-slicing trong coordinator
- [ ] **Bước 2** — EventDB + migration từ JSON
- [ ] **Bước 3** — EventPlanner
- [ ] **Bước 4** — Workers: thêm mode + extract_meta
- [ ] **Bước 5** — Tab UI: mode selector + 3 button phase
- [ ] **Bước 6** — Verify ảnh sau download
- [ ] **Bước 7** — Adaptive sleep
- [ ] **Bước 8** — Preview scan popup
- [ ] **Bước 9** — Thread safety: lock trong history_load
- [ ] **Cuối** — Cập nhật CODE_GRAPH.md
