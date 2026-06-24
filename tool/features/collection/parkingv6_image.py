import json
import queue
import re
import threading
import time
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple

from ...core.constants import (
    _P6_API_URL,
    _P6_MINIO_EP, _P6_MINIO_BUCKET, _P6_MINIO_AK, _P6_MINIO_SK,
)
from ...core.imports import _req_mod, _REQUESTS_OK, _cv2_mod, _np_mod, _CV2_OK


def _p6_safe(s: str) -> str:
    nfkd = unicodedata.normalize("NFKD", str(s).strip())
    ascii_only = nfkd.encode("ascii", errors="ignore").decode("ascii")
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', ascii_only)
    cleaned = re.sub(r'_+', '_', cleaned).strip('_')
    return cleaned or "unknown"


def _p6_vi_to_ascii(s: str) -> str:
    s = s.replace("đ", "d").replace("Đ", "D")
    return unicodedata.normalize("NFKD", s).encode("ascii", errors="ignore").decode()


# VehicleBaseType enum (iParkingv5): Unknown=-1, Car=0, MotorBike=2, Bike=4
_P6_VTYPE_CATEGORY = {0: "o_to", 2: "xe_may", 4: "xe_dap", -1: "o_to"}


def _p6_vtype_to_category(vt_int) -> str:
    try:
        return _P6_VTYPE_CATEGORY.get(int(vt_int), "o_to")
    except (TypeError, ValueError):
        return "o_to"


def _p6_img_type_to_path_parts(img_type: str):
    """Chuyển img_type → (vehicle_folder, sub_folder) cho cấu trúc mới."""
    if img_type.startswith("toan_canh_"):
        return img_type[len("toan_canh_"):], "anh_toan_canh"
    if img_type == "toan_canh":
        return "toan_canh", "anh_toan_canh"
    if img_type.endswith("_bsx_cut"):
        return img_type[:-len("_bsx_cut")], "anh_bsx"
    return img_type, "anh_xe"


def _p6_hour_to_buoi(hour: int) -> str:
    if hour < 12:
        return "sang"
    if hour < 14:
        return "trua"
    if hour < 18:
        return "chieu"
    return "toi"


def _p6_img_type_from_key(key: str, idx: int, vehicle_category: str) -> str:
    """Xác định loại ảnh từ tên key MinIO và vị trí trong fileKeys.

    LPR/BSX crop → <category>_bsx_cut       (e.g. o_to_bsx_cut)
    VEHICLE      → <category>                (e.g. o_to)
    OVERVIEW     → toan_canh_<category>      (e.g. toan_canh_o_to)
    """
    k = key.upper()
    if any(s in k for s in ("OVERVIEW", "TOAN_CANH", "TOAN-CANH", "FULL")):
        return f"toan_canh_{vehicle_category}"
    if any(s in k for s in ("LPR", "BSX", "PLATE")):
        return f"{vehicle_category}_bsx_cut"
    if any(s in k for s in ("VEHICLE", "VEH", "CAR")):
        return vehicle_category
    # Fallback: index 0 → toàn cảnh, còn lại → loại xe
    return f"toan_canh_{vehicle_category}" if idx == 0 else vehicle_category


def _p6_parse_dt(s) -> Optional[datetime]:
    if not s:
        return None
    s = str(s).strip().replace("Z", "")
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S",
                "%d/%m/%Y %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:26], fmt)
        except ValueError:
            pass
    return None


def _p6_get_nested(d: dict, path: str):
    """dot-path accessor: 'lane.name'"""
    curr = d
    for k in path.split("."):
        if not isinstance(curr, dict):
            return None
        curr = curr.get(k)
    return curr


def _p6_bad_reason(rec: dict) -> Optional[Tuple[str, str]]:
    """Return (reason, plate_label) if event has bad plate data, else None.

    reason: 'none' | 'in_out_mismatch' | 'register_mismatch'
    """
    plate     = re.sub(r"[^0-9A-Za-z]", "",
                       str(rec.get("plateNumber") or rec.get("PlateNumber") or "")).upper()
    plate_reg = re.sub(r"[^0-9A-Za-z]", "",
                       str(rec.get("registeredPlate") or rec.get("RegisteredPlate") or
                           rec.get("cardPlate")       or rec.get("CardPlate")       or "")).upper()
    plate_in  = re.sub(r"[^0-9A-Za-z]", "",
                       str(rec.get("plateIn")  or rec.get("PlateIn")  or
                           rec.get("plateNumberIn") or "")).upper()
    plate_out = re.sub(r"[^0-9A-Za-z]", "",
                       str(rec.get("plateOut") or rec.get("PlateOut") or
                           rec.get("plateNumberOut") or "")).upper()
    if not plate and not plate_in and not plate_out:
        return ("none", "")
    if plate_in and plate_out and plate_in != plate_out:
        return ("in_out_mismatch", f"{plate_in}_{plate_out}")
    effective = plate or plate_in or plate_out
    if plate_reg and effective and effective != plate_reg:
        return ("register_mismatch", f"{effective}_{plate_reg}")
    return None


# ── Shared state thread-safe cho parallel mode ────────────────────────────────

class _P6SharedLaneState:
    __slots__ = ("_lock", "lane_total", "lane_warned", "known_lanes", "hist_lock")

    def __init__(self):
        self._lock        = threading.Lock()
        self.lane_total:  dict = {}
        self.lane_warned: set  = set()
        self.known_lanes: set  = set()
        self.hist_lock    = threading.Lock()


# ── API Client ────────────────────────────────────────────────────────────────

class Parkingv6ApiClient:
    def __init__(self, cfg: dict):
        self.api_url  = cfg.get("api_url",  _P6_API_URL).rstrip("/")
        self.token    = cfg.get("token",    "").strip()
        self.timeout  = 60
        self._session = _req_mod.Session() if _req_mod else None
        self._minio   = None
        self._bucket  = cfg.get("minio_bucket", _P6_MINIO_BUCKET)

    def init_minio(self, ep: str, ak: str, sk: str, secure: bool = False) -> bool:
        try:
            from minio import Minio
            self._minio = Minio(ep, access_key=ak, secret_key=sk, secure=secure)
            self._minio.bucket_exists(self._bucket)
            return True
        except Exception:
            self._minio = None
            return False

    def search(self, source: str, from_dt: str, to_dt: str,
               page: int, size: int, keyword: str = "") -> Tuple[bool, dict]:
        """POST reporting/parking/{source} — pageIndex 0-based, filter camelCase."""
        if not self._session:
            return False, {}
        url  = f"{self.api_url}/reporting/parking/{source}"
        hdrs = {
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {self.token}",
        }
        body = {
            "filter": {
                "fromUtc":          from_dt,
                "toUtc":            to_dt,
                "keyword":          keyword,
                "laneIds":          [],
                "identityGroupIds": [],
                "transactionTypes": [],
                "upns":             [],
            },
            "pageIndex": page,
            "pageSize":  size,
            "paging":    True,
        }
        for attempt in range(3):
            try:
                r = self._session.post(url, json=body, headers=hdrs, timeout=self.timeout)
                r.raise_for_status()
                return True, r.json()
            except Exception:
                if attempt < 2:
                    time.sleep(2 * (attempt + 1))
        return False, {}

    def fetch_image(self, key: str):
        """Tải ảnh từ MinIO key, fallback về HTTP Bearer."""
        if not key or not _CV2_OK:
            return None
        cv2, np = _cv2_mod, _np_mod

        if self._minio:
            try:
                obj_key = key.lstrip("/")
                if obj_key.lower().startswith(self._bucket.lower() + "/"):
                    obj_key = obj_key[len(self._bucket) + 1:]
                resp = self._minio.get_object(self._bucket, obj_key)
                buf  = np.frombuffer(resp.read(), np.uint8)
                resp.close(); resp.release_conn()
                img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
                if img is not None:
                    return img
            except Exception:
                pass

        target = key if key.startswith("http") else f"{self.api_url}/{key.lstrip('/')}"
        try:
            r = self._session.get(target, timeout=self.timeout,
                                  headers={"Authorization": f"Bearer {self.token}"})
            r.raise_for_status()
            buf = np.frombuffer(r.content, np.uint8)
            return cv2.imdecode(buf, cv2.IMREAD_COLOR)
        except Exception:
            return None


# ── Worker ────────────────────────────────────────────────────────────────────

class Parkingv6Worker:
    _HISTORY_FILE = ".p6_done.json"

    def __init__(self, cfg: dict, log_q: queue.Queue, stat_q: queue.Queue,
                 pause_event: threading.Event = None,
                 thread_id: int = 0,
                 days_list: list = None,
                 shared: _P6SharedLaneState = None,
                 send_done: bool = True,
                 global_total_days: int = None,
                 mode: str = 'full',
                 event_db=None):
        self.cfg                = cfg
        self.log_q              = log_q
        self.stat_q             = stat_q
        self._stop              = threading.Event()
        self._pause             = pause_event or threading.Event()
        self._pause.set()
        self._thread_id         = thread_id
        self._days_list         = days_list
        self._shared            = shared if shared is not None else _P6SharedLaneState()
        self._send_done         = send_done
        self._global_total_days = global_total_days
        self.stats: dict = {
            "page": 0, "event": 0, "found": 0,
            "saved": 0, "skipped": 0, "error": 0, "bad_saved": 0,
            "day_idx": 0, "total_days": 0, "day_label": "",
            "thread_id": thread_id,
        }
        self._mode     = mode
        self._event_db = event_db
        self._lane_cat:     dict = {}
        self._lane_hourly:  dict = {}
        self._lane_buoi:    dict = {}
        self._done_days:    set  = set()
        self._vgroup_cache: dict = {}

    # ── metadata extraction (scan_only mode) ──────────────────────────────

    def _extract_meta(self, rec: dict) -> dict:
        """Extract metadata từ API record mà không download ảnh."""
        event_id = str(rec.get("id") or rec.get("Id") or "")
        plate    = _p6_safe(re.sub(r"[^0-9A-Za-z]", "",
                                   str(rec.get("plateNumber") or rec.get("PlateNumber") or "")))
        dt       = (_p6_parse_dt(rec.get("createdUtc") or rec.get("CreatedUtc") or
                                  rec.get("dateTimeIn") or rec.get("dateTime"))
                    or datetime.now())
        lane     = _p6_safe(
            rec.get("laneName") or _p6_get_nested(rec, "lane.name") or "unknown_lane")
        group_id   = str(rec.get("identityGroupId") or "").lower()
        group_name = str(rec.get("identityGroupName") or "").lower()
        vt_int     = self._vgroup_cache.get(group_id) if group_id else None
        if vt_int is None and group_name:
            vt_int = self._vgroup_cache.get(group_name)
        category   = _p6_vtype_to_category(vt_int if vt_int is not None else -1)
        file_keys  = list(rec.get("fileKeys") or rec.get("FileKeys") or [])
        refs       = [str(k) for k in file_keys if k]
        has_gt     = bool(plate)
        return {
            "event_id": event_id, "date": dt.strftime("%Y-%m-%d"),
            "hour": dt.hour,      "minute": dt.minute,
            "lane": lane,         "vtype": category,
            "plate": plate,       "has_gt": 1 if has_gt else 0,
            "image_refs": refs,   "scanned_at": datetime.now().isoformat(),
        }

    # ── helpers ──────────────────────────────────────────────────────────────

    def _prefetch_identity_groups(self, api: Parkingv6ApiClient) -> dict:
        """Fetch toàn bộ identity groups, cache {id_lower: vehicleType_int, name_lower: vehicleType_int}."""
        cache = {}
        if not api._session:
            return cache
        try:
            url  = f"{api.api_url}/identity-group/search"
            hdrs = {"Content-Type": "application/json",
                    "Authorization": f"Bearer {api.token}"}
            body = {"pageIndex": 0, "pageSize": 1000, "filter": "", "fields": []}
            r = api._session.post(url, json=body, headers=hdrs, timeout=30)
            if r.ok:
                groups = r.json().get("data") or []
                for g in groups:
                    vt  = g.get("vehicleType")
                    vt_int = int(vt) if vt is not None else -1
                    gid  = g.get("id")
                    name = g.get("name") or g.get("code")
                    if gid:
                        cache[str(gid).lower()] = vt_int
                    if name:
                        cache[str(name).lower()] = vt_int
                self._log(f"Identity groups: {len(groups)} nhóm đã cache vehicleType")
            else:
                self._log(f"  [WARN] /identity-group/search → HTTP {r.status_code}")
        except Exception as e:
            self._log(f"  [WARN] Không load identity groups: {e}")
        return cache

    def stop(self): self._stop.set()

    def _log(self, msg: str):
        if self._thread_id:
            msg = f"[T{self._thread_id}] {msg}"
        self.log_q.put(msg)

    def _push(self):
        s = dict(self.stats)
        s["thread_id"] = self._thread_id
        self.stat_q.put(s)

    # ── history ──────────────────────────────────────────────────────────────

    def _history_load(self, out: Path):
        with self._shared.hist_lock:
            try:
                f = out / self._HISTORY_FILE
                if f.exists():
                    self._done_days = set(json.loads(f.read_text(encoding="utf-8")))
                    self._log(f"Lịch sử: {len(self._done_days)} ngày đã tải trước đó.")
            except Exception:
                self._done_days = set()

    def _history_mark(self, out: Path, label: str):
        self._done_days.add(label)
        try:
            with self._shared.hist_lock:
                f = out / self._HISTORY_FILE
                if f.exists():
                    try:
                        existing = set(json.loads(f.read_text(encoding="utf-8")))
                        existing.update(self._done_days)
                        self._done_days = existing
                    except Exception:
                        pass
                f.write_text(json.dumps(sorted(self._done_days), ensure_ascii=False),
                             encoding="utf-8")
        except Exception:
            pass

    # ── day list ─────────────────────────────────────────────────────────────

    @staticmethod
    def _day_list(from_str: str, to_str: str) -> list:
        from_dt = _p6_parse_dt(from_str) or datetime.now()
        to_dt   = _p6_parse_dt(to_str)   or datetime.now()
        days, cur, end = [], from_dt.date(), to_dt.date()
        while cur <= end:
            d_from = (from_dt.strftime("%Y-%m-%dT%H:%M:%S")
                      if cur == from_dt.date() else f"{cur}T00:00:00")
            d_to   = (to_dt.strftime("%Y-%m-%dT%H:%M:%S")
                      if cur == to_dt.date()   else f"{cur}T23:59:59")
            days.append((d_from, d_to, str(cur)))
            cur += timedelta(days=1)
        return days

    # ── main run ─────────────────────────────────────────────────────────────

    def run(self):
        cfg = self.cfg
        out = Path(cfg["output_dir"])
        api = Parkingv6ApiClient(cfg)

        if not api.token:
            self._log("[LỖI] Chưa nhập token — vui lòng điền token vào phần Nâng cao.")
            if self._send_done:
                self.log_q.put("__DONE__")
            return

        self._log(f"Token: {api.token[:16]}...")

        if cfg.get("use_minio", True):
            ok = api.init_minio(
                cfg.get("minio_ep",  _P6_MINIO_EP),
                cfg.get("minio_ak",  _P6_MINIO_AK),
                cfg.get("minio_sk",  _P6_MINIO_SK),
            )
            self._log(f"MinIO: {'kết nối OK' if ok else 'không khả dụng — dùng HTTP'}")

        self._vgroup_cache = self._prefetch_identity_groups(api)

        size    = cfg.get("page_size", 100)
        sleep_s = cfg.get("sleep", 0.05)

        src_raw = cfg.get("event_source", "both")
        sources = []
        if src_raw in ("event-in",  "both"): sources.append("event-in")
        if src_raw in ("event-out", "both"): sources.append("event-out")
        if not sources:
            sources = ["event-in"]

        if self._days_list is not None:
            days       = self._days_list
            total_days = (self._global_total_days
                          if self._global_total_days is not None else len(days))
        else:
            from_d = cfg["from_date"].strip().replace(" ", "T")
            to_d   = cfg["to_date"].strip().replace(" ", "T")
            days   = self._day_list(from_d, to_d)
            total_days = len(days)
            self._log(f"Khoảng thời gian: {from_d} → {to_d}")
            self._log(f"Tổng: {total_days} ngày | page size={size} | nguồn={', '.join(sources)}")
            max_lane = cfg.get("max_per_lane", 0)
            max_cat  = cfg.get("max_per_cat",  0)
            max_hour = cfg.get("max_per_hour", 0)
            limits = []
            if max_lane: limits.append(f"{max_lane} ảnh/làn")
            if max_cat:  limits.append(f"{max_cat} ảnh/loại/làn/ngày")
            if max_hour: limits.append(f"{max_hour} ảnh/giờ/làn")
            self._log(f"Giới hạn: {', '.join(limits) if limits else 'không'}")
            self._history_load(out)

        skipped_days = 0
        for local_idx, (d_from, d_to, label) in enumerate(days, 1):
            if self._stop.is_set():
                break
            self.stats.update({"day_idx": local_idx, "total_days": total_days,
                                "day_label": label})
            self._push()
            if label in self._done_days:
                skipped_days += 1
                self._log(f"  ⏭ NGÀY {label} — đã tải trước đó, bỏ qua")
                continue
            self._log(f"\n{'═'*52}")
            self._log(f"  NGÀY {label}  ({local_idx}/{len(days)})")
            self._log(f"{'═'*52}")
            for src in sources:
                self._collect_day(api, src, d_from, d_to, out, size, sleep_s)
            if not self._stop.is_set():
                self._history_mark(out, label)

        self._log(f"\n{'─'*52}")
        self._log(
            f"Xong {len(days)} ngày"
            f"{f' (bỏ qua {skipped_days} đã tải)' if skipped_days else ''}: "
            f"{self.stats['event']} SK, "
            f"{self.stats['found']} tìm, "
            f"{self.stats['saved']} lưu, "
            f"{self.stats['skipped']} bỏ, "
            f"{self.stats['error']} lỗi."
        )
        self._push()
        if self._send_done:
            self.log_q.put("__DONE__")

    # ── collect one day ───────────────────────────────────────────────────────

    def _collect_day(self, api: Parkingv6ApiClient, source: str,
                     d_from: str, d_to: str, out: Path,
                     size: int, sleep_s: float):
        page, empty_n = 0, 0
        max_pages = self.cfg.get("max_pages", 10000)
        while not self._stop.is_set() and page < max_pages:
            self._pause.wait()
            if self._stop.is_set():
                return
            self._log(f"  [{source.upper()} PAGE {page}] Đang gọi API...")
            t0 = time.time()
            ok, data = api.search(source, d_from, d_to, page, size,
                                  keyword=self.cfg.get("keyword", ""))
            elapsed = time.time() - t0
            if not ok:
                self.stats["error"] += 1
                self._log(f"  [PAGE {page}] Lỗi/timeout sau {elapsed:.0f}s — bỏ qua.")
                page += 1
                self._push()
                time.sleep(2)
                continue

            total_count = (data.get("totalCount") or data.get("TotalCount") or 0)
            total_pages = (data.get("totalPage")  or data.get("TotalPage")  or 0)
            recs = data.get("data") or data.get("Data") or []

            if not recs:
                empty_n += 1
                if empty_n >= 3:
                    self._log(f"  [{source.upper()} PAGE {page}] Hết dữ liệu ngày này.")
                    break
                page += 1
                continue
            empty_n = 0

            tp_info = f"/{total_pages}" if total_pages else ""
            self._log(
                f"  [{source.upper()} PAGE {page}{tp_info}] "
                f"{len(recs)} SK | {elapsed:.1f}s | tổng={total_count}")
            self.stats["page"]  += 1
            self.stats["event"] += len(recs)
            scan_batch = [] if self._mode == 'scan_only' else None
            for rec in recs:
                if self._stop.is_set():
                    return
                if scan_batch is not None:
                    scan_batch.append(self._extract_meta(rec))
                else:
                    self._process(api, rec, source, out)
            if scan_batch and self._event_db is not None:
                self._event_db.insert_events('p6', scan_batch)
            self._push()

            page += 1
            if total_pages and page >= total_pages:
                break
            if total_count and self.stats["event"] >= total_count:
                break
            remaining = max(0.0, min(sleep_s, 5.0) - elapsed)
            if remaining > 0:
                time.sleep(remaining)

    # ── process one record ────────────────────────────────────────────────────

    def _process(self, api: Parkingv6ApiClient, rec: dict, source: str, out: Path):
        event_id = str(rec.get("id") or rec.get("Id") or "")[:8]
        plate    = _p6_safe(re.sub(r"[^0-9A-Za-z]", "",
                                   str(rec.get("plateNumber") or
                                       rec.get("PlateNumber") or "")))
        lane = _p6_safe(
            rec.get("laneName")  or rec.get("LaneName")  or
            _p6_get_nested(rec, "lane.name")   or
            _p6_get_nested(rec, "Lane.Name")   or
            _p6_get_nested(rec, "laneIn.name") or
            _p6_get_nested(rec, "laneOut.name") or
            "unknown_lane")
        dt = (
            _p6_parse_dt(rec.get("createdUtc")  or rec.get("CreatedUtc"))  or
            _p6_parse_dt(rec.get("dateTimeIn")   or rec.get("DateTimeIn")) or
            _p6_parse_dt(rec.get("dateTime")     or rec.get("DateTime"))   or
            datetime.now()
        )
        # Phân loại xe theo VehicleBaseType enum từ identity-group cache
        group_id   = str(rec.get("identityGroupId")   or "").lower()
        group_name = str(rec.get("identityGroupName") or "").lower()
        vt_int     = self._vgroup_cache.get(group_id) \
                  if group_id else None
        if vt_int is None and group_name:
            vt_int = self._vgroup_cache.get(group_name)
        if vt_int is None:
            vt_int = -1
        category   = _p6_vtype_to_category(vt_int)

        vt_label = group_name or f"vt={vt_int}"
        file_keys = list(rec.get("fileKeys") or rec.get("FileKeys") or [])

        bad_result = _p6_bad_reason(rec) if self.cfg.get("collect_bad") else None
        bad_reason = bad_result[0] if bad_result else None
        bad_label  = bad_result[1] if bad_result else ""
        gt_plate   = plate if plate else None

        self._log(
            f"  [{event_id}] {plate or '?':12s} | {lane} | "
            f"{dt.strftime('%Y-%m-%d %H:%M')} | [{source}] {category} ({vt_label}) | "
            f"{len(file_keys)} ảnh"
            + (f" | BAD:{bad_reason}" if bad_reason else ""))

        max_lane = self.cfg.get("max_per_lane", 0)
        if max_lane > 0:
            with self._shared._lock:
                self._shared.known_lanes.add(lane)

        event_saved = False
        for idx, key in enumerate(file_keys):
            if self._stop.is_set():
                return
            if not key:
                continue
            img_type = _p6_img_type_from_key(key, idx, category)
            self._log(f"    [{idx+1}/{len(file_keys)}] {str(key)[:50]} → {img_type}")
            direction = "in" if "in" in source else "out"
            if self._save_image(api, str(key), img_type, lane, dt, plate, out,
                                bad_reason, bad_label, event_id, direction, gt_plate=gt_plate):
                event_saved = True
        if event_saved:
            self.stats["saved"] += 1

        # Dừng sớm khi tất cả các làn đã đủ SK
        if max_lane > 0:
            with self._shared._lock:
                if (self._shared.known_lanes
                        and self._shared.lane_warned.issuperset(self._shared.known_lanes)):
                    self._log("  ✅ Tất cả các làn đã đủ SK — dừng sớm")
                    self._stop.set()

    # ── save one image ────────────────────────────────────────────────────────

    def _save_image(self, api: Parkingv6ApiClient, key: str, img_type: str,
                    lane: str, dt: datetime, plate: str, out: Path,
                    bad_reason: Optional[str] = None, bad_label: str = "",
                    event_id: str = "", direction: str = "in", gt_plate: Optional[str] = None) -> bool:
        self.stats["found"] += 1

        if bad_reason:
            if img_type.startswith("toan_canh_"):
                self.stats["skipped"] += 1
                return False
            img = api.fetch_image(key)
            if img is None:
                self.stats["error"] += 1
                return False
            eid = event_id or "evt"
            save_dir = out / "bad" / lane / bad_reason / dt.strftime("%Y-%m-%d") / eid / direction
            save_dir.mkdir(parents=True, exist_ok=True)
            ts   = dt.strftime("%H%M%S")
            base = f"{ts}_{bad_label}" if bad_label else ts
            i = 0
            while True:
                sfx   = f"_{i:03d}" if i else ""
                fpath = save_dir / f"{base}{sfx}.jpg"
                if not fpath.exists():
                    break
                i += 1
            ok_enc, buf = _cv2_mod.imencode(".jpg", img)
            if ok_enc:
                fpath.write_bytes(buf.tobytes())
                self.stats["bad_saved"] += 1
                self._log(f"      ✗[{bad_reason}] {fpath.name}")
            else:
                self.stats["error"] += 1
            return False

        # GT filter — chỉ lưu ảnh khi có biển số GT
        if self.cfg.get("only_gt") and gt_plate is None:
            self.stats["skipped"] += 1
            return False

        # Type filter — chỉ lưu loại ảnh được chọn
        _allowed = self.cfg.get("allowed_vtypes")
        if _allowed and img_type not in _allowed:
            self.stats["skipped"] += 1
            return False

        buoi = _p6_hour_to_buoi(dt.hour)   # tính sớm để dùng cho limit check

        # Giới hạn tổng ảnh/làn
        max_lane = self.cfg.get("max_per_lane", 0)
        if max_lane > 0:
            with self._shared._lock:
                if self._shared.lane_total.get(lane, 0) >= max_lane:
                    if lane not in self._shared.lane_warned:
                        self._log(f"      ⏭ Làn [{lane}] đủ {max_lane} ảnh — bỏ qua")
                        self._shared.lane_warned.add(lane)
                    self.stats["skipped"] += 1
                    return False

        # Giới hạn ảnh/loại/làn/ngày
        max_cat = self.cfg.get("max_per_cat", 0)
        if max_cat > 0:
            cat_key = (lane, img_type, dt.strftime("%Y-%m-%d"))
            if self._lane_cat.get(cat_key, 0) >= max_cat:
                self.stats["skipped"] += 1
                return False

        # Giới hạn ảnh/buổi/làn/ngày
        max_buoi = self.cfg.get("max_per_buoi", 0)
        if max_buoi > 0:
            buoi_key = (lane, dt.strftime("%Y-%m-%d"), buoi)
            if self._lane_buoi.get(buoi_key, 0) >= max_buoi:
                self.stats["skipped"] += 1
                return False

        img = api.fetch_image(key)
        if img is None:
            self.stats["error"] += 1
            self._log(f"      ✗ Lỗi tải: {key[:60]}")
            return False

        vtype_folder, sub_folder = _p6_img_type_to_path_parts(img_type)
        save_dir = out / vtype_folder / sub_folder / dt.strftime("%Y-%m-%d") / buoi / lane
        save_dir.mkdir(parents=True, exist_ok=True)
        ts_str    = dt.strftime("%H%M%S")
        base_name = f"{ts_str}_{plate}" if plate else ts_str
        i = 0
        while True:
            suffix = f"_{i:03d}" if i else ""
            fpath  = save_dir / f"{base_name}{suffix}.jpg"
            if not fpath.exists():
                break
            i += 1
        ok_enc, buf = _cv2_mod.imencode(".jpg", img)
        if ok_enc:
            fpath.write_bytes(buf.tobytes())
            try:
                chk = _cv2_mod.imdecode(
                    _np_mod.frombuffer(fpath.read_bytes(), _np_mod.uint8),
                    _cv2_mod.IMREAD_UNCHANGED)
                if chk is None or chk.size < 300:
                    fpath.unlink(missing_ok=True)
                    self.stats["error"] += 1
                    self._log(f"      ✗ Ảnh hỏng sau decode — đã xóa: {fpath.name}")
                    return False
            except Exception:
                pass
            with self._shared._lock:
                self._shared.lane_total[lane] = (
                    self._shared.lane_total.get(lane, 0) + 1)
            cat_key  = (lane, img_type, dt.strftime("%Y-%m-%d"))
            self._lane_cat[cat_key] = self._lane_cat.get(cat_key, 0) + 1
            buoi_key = (lane, dt.strftime("%Y-%m-%d"), buoi)
            self._lane_buoi[buoi_key] = self._lane_buoi.get(buoi_key, 0) + 1
            self._log(f"      ✓ {vtype_folder}/{sub_folder}/{buoi}/{fpath.name}")
            if gt_plate and sub_folder in ("anh_xe", "anh_bsx"):
                with open(save_dir / "gt.txt", "a", encoding="utf-8") as _f:
                    _f.write(f"{fpath.name}\t{gt_plate}\n")
            return True
        else:
            self.stats["error"] += 1
            self._log(f"      ✗ Lỗi encode: {key[:60]}")
            return False
