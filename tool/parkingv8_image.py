import json
import queue
import re
import threading
import time
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple

from .constants import (
    _P8_LOGIN_URL, _P8_API_URL,
    _P8_CLIENT_ID, _P8_CLIENT_SECRET,
    _P8_USERNAME, _P8_PASSWORD,
)
from .imports import _req_mod, _REQUESTS_OK, _cv2_mod, _np_mod, _CV2_OK

# EmImageType enum: 0=VEHICLE, 1=PLATE_NUMBER, 2=PANORAMA, 3=FACE, 4=OTHER
_IMG_TYPE_SUFFIX_EXIT  = {0: "vo", 1: "po", 2: "fo", 3: "face_o", 4: "other_o"}
_IMG_TYPE_SUFFIX_ENTRY = {0: "vi", 1: "pi", 2: "fi", 3: "face_i", 4: "other_i"}

# Suffix nào là ảnh toàn cảnh → bỏ qua khi lưu ảnh xấu
_FULL_SUFFIXES  = {"fo", "fi"}

# Suffix ảnh biển số cắt (plate crop)
_PLATE_SUFFIXES = {"po", "pi"}


def _p8_suffix_to_imgtype(suffix: str, vtype: str) -> str:
    """Ánh xạ suffix ảnh → tên thư mục lưu.

    fo/fi → toan_canh_<vtype>   (panorama, phân theo loại xe)
    po/pi → <vtype>_bsx_cut     (plate crop)
    vo/vi → <vtype>              (vehicle image)
    """
    if suffix in _FULL_SUFFIXES:
        return f"toan_canh_{vtype}"
    if suffix in _PLATE_SUFFIXES:
        return f"{vtype}_bsx_cut"
    return vtype

# Mapping từ field name cũ → suffix (fallback nếu server không dùng PresignedUrl)
_IMG_SUFFIX: dict = {
    "imageFullIn":  "fi",  "imageFullOut":  "fo",
    "imagePlateIn": "pi",  "imagePlateOut": "po",
    "imageIn":      "in",  "imageOut":      "out",
    "imageFull":    "full","imagePlate":    "plate",
    "imageUrl":     "img", "images":        "img",
    "imageUrls":    "img",
}

# All image fields to probe on a record (fallback)
_IMG_FIELDS = [
    "imageFullIn", "imageFullOut",
    "imagePlateIn", "imagePlateOut",
    "imageIn", "imageOut",
    "imageFull", "imagePlate",
    "imageUrl", "imageUrls",
]


def _p8_safe(s: str) -> str:
    nfkd = unicodedata.normalize("NFKD", str(s).strip())
    ascii_only = nfkd.encode("ascii", errors="ignore").decode("ascii")
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', ascii_only)
    cleaned = re.sub(r'_+', '_', cleaned).strip('_')
    return cleaned or "unknown"


def _p8_bad_reason(rec: dict) -> Optional[Tuple[str, str]]:
    """Return (reason, plate_label) if event has bad plate data, else None.

    reason: 'none' | 'register_mismatch'
    plate_label: embedded in filename so both plates are visible.
      - none              → ""
      - register_mismatch → "BSX_nhan_dien_BSX_dang_ky"  (xe tháng)
    """
    plate_rec = re.sub(r"[^0-9A-Za-z]", "",
                       str(rec.get("plateNumber") or rec.get("PlateNumber") or "")).upper()
    plate_reg = re.sub(r"[^0-9A-Za-z]", "",
                       str(_get_nested(rec, "accessKey.collection.plateNumber") or
                           _get_nested(rec, "accessKey.plateNumber")           or "")).upper()
    if not plate_rec:
        return ("none", "")
    if plate_reg and plate_rec != plate_reg:
        return ("register_mismatch", f"{plate_rec}_{plate_reg}")
    return None


def _p8_match_kw(src: str, keywords: list) -> bool:
    """True nếu bất kỳ từ khóa nào khớp với src (không phân biệt dấu/hoa-thường)."""
    if not src or not keywords:
        return False
    s   = src.lower()
    s_n = unicodedata.normalize("NFKD", s).encode("ascii", errors="ignore").decode()
    for kw in keywords:
        k   = kw.lower()
        k_n = unicodedata.normalize("NFKD", k).encode("ascii", errors="ignore").decode()
        if k and (k in s or k_n in s_n):
            return True
    return False


# EmVehicleType enum: 0=CAR, 1=MOTORBIKE, 2=BIKE
_VT_INT_MAP = {0: "o_to", 1: "xe_may", 2: "xe_dap"}


def _p8_categorize(vehicle_type: str, vtype_cfg: Optional[dict] = None) -> str:
    """Phân loại xe theo keyword (fallback khi không có integer enum)."""
    cfg    = vtype_cfg or {}
    kw_may = cfg.get("xe_may") or ["motor", "xe_may", "motorbike"]
    kw_dap = cfg.get("xe_dap") or ["bicycle", "xe_dap", "bike"]
    kw_oto = cfg.get("o_to")   or []

    vt = vehicle_type or ""
    if _p8_match_kw(vt, kw_dap): return "xe_dap"
    if _p8_match_kw(vt, kw_may): return "xe_may"
    if kw_oto and _p8_match_kw(vt, kw_oto): return "o_to"
    return "o_to"


def _p8_parse_dt(s: str) -> Optional[datetime]:
    if not s:
        return None
    s = str(s).strip().replace("Z", "")
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",    "%Y/%m/%d %H:%M:%S",
    ):
        try:
            return datetime.strptime(s[:26], fmt)
        except ValueError:
            pass
    return None


def _get_nested(d: dict, path: str):
    """dot-path accessor: 'accessKey.collection.vehicleType'"""
    curr = d
    for k in path.split("."):
        if not isinstance(curr, dict):
            return None
        curr = curr.get(k)
    return curr


def _p8_make_filter(start: str, end: str, page: int, size: int) -> dict:
    """Build the request body for /exits/search or /entries/search."""
    filter_obj = {
        "and": [
            {"and": [
                {
                    "QueryKey": "createdUtc", "QueryType": "DATETIME",
                    "QueryValue": f"[{start},{end}]", "Operation": "between",
                },
            ]},
            {"or": [
                {"QueryKey": "plateNumber",     "QueryType": "TEXT",
                 "QueryValue": "", "Operation": "contains"},
                {"QueryKey": "accessKey.code",  "QueryType": "TEXT",
                 "QueryValue": "", "Operation": "contains"},
                {"QueryKey": "accessKey.name",  "QueryType": "TEXT",
                 "QueryValue": "", "Operation": "contains"},
                {"QueryKey": "note",            "QueryType": "TEXT",
                 "QueryValue": "", "Operation": "contains"},
            ]},
        ]
    }
    return {
        "pageIndex": page,
        "pageSize":  size,
        "paging":    True,
        "filter":    json.dumps(filter_obj, ensure_ascii=False),
        "fields":    [],
    }


# ─────────────────────────────────────────────────────────────────────────────

class Parkingv8ApiClient:
    def __init__(self, cfg: dict):
        self.login_url     = cfg.get("login_url",     _P8_LOGIN_URL).rstrip("/")
        self.api_url       = cfg.get("api_url",       _P8_API_URL).rstrip("/")
        self.grant_type    = cfg.get("grant_type",    "client_credentials")
        self.client_id     = cfg.get("client_id",     _P8_CLIENT_ID)
        self.client_secret = cfg.get("client_secret", _P8_CLIENT_SECRET)
        self.username      = cfg.get("username",      _P8_USERNAME)
        self.password      = cfg.get("password",      _P8_PASSWORD)
        self.timeout       = 60
        self.token: Optional[str] = None
        self._session = _req_mod.Session() if _req_mod else None

    def login(self) -> bool:
        if not self._session:
            return False
        url = f"{self.login_url}/connect/token"
        if self.grant_type == "client_credentials":
            data = {
                "grant_type":    "client_credentials",
                "client_id":     self.client_id,
                "client_secret": self.client_secret,
            }
        else:
            data = {
                "grant_type":    "password",
                "client_id":     "27ee5d4a-4251-4e5a-a440-a8f8e22f99a6",
                "client_secret": "TcMKwrekvf9UIUgNKh",
                "username":      self.username,
                "password":      self.password,
            }
        try:
            r = self._session.post(url, data=data, timeout=15)
            r.raise_for_status()
            self.token = r.json().get("access_token")
            return bool(self.token)
        except Exception:
            return False

    def search(self, endpoint: str, start: str, end: str,
               page: int, size: int):
        url  = f"{self.api_url}/{endpoint}/search"
        hdrs = {
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {self.token}",
        }
        body = _p8_make_filter(start, end, page, size)
        for attempt in range(3):
            try:
                r = self._session.post(
                    url, headers=hdrs, json=body, timeout=self.timeout)
                r.raise_for_status()
                return True, r.json()
            except Exception:
                if attempt < 2:
                    time.sleep(2 * (attempt + 1))
        return False, {}

    def fetch_detail(self, endpoint: str, record_id: str) -> dict:
        """GET {api_url}/{endpoint}/{id}?presignedUrl=true — trả về record kèm presigned URL ảnh."""
        url = f"{self.api_url}/{endpoint}/{record_id}"
        try:
            r = self._session.get(
                url, timeout=self.timeout,
                headers={"Authorization": f"Bearer {self.token}"},
                params={"presignedUrl": "true"})
            if r.ok:
                return r.json()
        except Exception:
            pass
        return {}

    def fetch_image(self, url: str):
        """Tải ảnh từ PresignedUrl.

        Presigned URL: GET trực tiếp (không cần auth).
        URL tương đối hoặc bearer-protected: thêm Authorization header.
        """
        if not url or not _CV2_OK:
            return None
        cv2, np = _cv2_mod, _np_mod

        # Relative path → build absolute URL
        target = url if url.startswith("http") else f"{self.api_url}/{url.lstrip('/')}"

        # 1st attempt: plain GET (presigned / public URLs)
        try:
            r = self._session.get(target, timeout=self.timeout)
            if r.ok:
                buf = np.frombuffer(r.content, np.uint8)
                img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
                if img is not None:
                    return img
        except Exception:
            pass

        # 2nd attempt: with Bearer token
        try:
            r = self._session.get(
                target, timeout=self.timeout,
                headers={"Authorization": f"Bearer {self.token}"})
            r.raise_for_status()
            buf = np.frombuffer(r.content, np.uint8)
            return cv2.imdecode(buf, cv2.IMREAD_COLOR)
        except Exception:
            return None

    @staticmethod
    def extract_detail_images(detail: dict, endpoint: str) -> list:
        """Trích ảnh từ detail record (GET /exits/{id} hoặc /entries/{id}).

        Format: images = [{presignedUrl: str, type: int}, ...]
        Trả về: [(presigned_url, suffix), ...]
          - exit  images: type 0→"fo", 1→"vo", 2→"po"
          - entry images: type 0→"fi", 1→"vi", 2→"pi"
        Ảnh từ entry sub-record chỉ lấy khi endpoint="exits" (tránh duplicate khi "both").
        """
        images = []
        main_map = (_IMG_TYPE_SUFFIX_EXIT if endpoint == "exits"
                    else _IMG_TYPE_SUFFIX_ENTRY)

        for img in (detail.get("images") or []):
            if not isinstance(img, dict):
                continue
            url = (img.get("presignedUrl") or img.get("PresignedUrl") or
                   img.get("url") or img.get("Url") or "")
            if not url:
                continue
            typ = img.get("type")
            suf = main_map.get(typ, f"t{typ}" if typ is not None else "img")
            images.append((url, suf))

        # Ảnh entry lồng trong exit record
        if endpoint == "exits":
            for img in (detail.get("entry") or {}).get("images") or []:
                if not isinstance(img, dict):
                    continue
                url = (img.get("presignedUrl") or img.get("PresignedUrl") or
                       img.get("url") or img.get("Url") or "")
                if not url:
                    continue
                typ = img.get("type")
                suf = _IMG_TYPE_SUFFIX_ENTRY.get(typ, f"t{typ}" if typ is not None else "img")
                images.append((url, suf))

        return images

    @staticmethod
    def extract_images(rec: dict) -> list:
        """Fallback: trích ảnh từ các field name cũ (server không dùng PresignedUrl)."""
        images = []
        for field in _IMG_FIELDS:
            val = rec.get(field)
            if not val:
                continue
            suffix = _IMG_SUFFIX.get(field, field)
            if isinstance(val, str):
                images.append((val, suffix))
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, str) and item:
                        images.append((item, suffix))
                    elif isinstance(item, dict):
                        url = (item.get("url") or item.get("Url")
                               or item.get("path") or item.get("Path") or "")
                        typ = item.get("type") or item.get("Type") or suffix
                        if url:
                            images.append((url, _IMG_SUFFIX.get(str(typ), str(typ))))
        return images


# ─────────────────────────────────────────────────────────────────────────────

class Parkingv8Worker:
    _HISTORY_FILE = ".p8_done.json"

    def __init__(self, cfg: dict, log_q: queue.Queue, stat_q: queue.Queue,
                 pause_event: threading.Event = None):
        self.cfg    = cfg
        self.log_q  = log_q
        self.stat_q = stat_q
        self._stop  = threading.Event()
        self._pause = pause_event or threading.Event()
        self._pause.set()
        self.stats: dict = {
            "page": 0, "event": 0, "found": 0,
            "saved": 0, "skipped": 0, "error": 0, "bad_saved": 0,
            "day_idx": 0, "total_days": 0, "day_label": "",
        }
        self._lane_total:  dict = {}   # {lane: count}
        self._lane_cat:    dict = {}   # {(lane, vtype, "YYYY-MM-DD"): count} ← daily
        self._lane_hourly: dict = {}   # {(lane, "YYYY-MM-DD HH"): count}
        self._lane_warned: set  = set()
        self._done_days:   set  = set()
        self._vtype_cfg:   dict = self._parse_vtype_cfg()

    def _parse_vtype_cfg(self) -> dict:
        def _kws(key: str, default: str) -> list:
            raw = self.cfg.get(key, default)
            return [k.strip() for k in str(raw).split(",") if k.strip()]
        return {
            "xe_may": _kws("kw_xe_may", "motor, xe_may"),
            "xe_dap": _kws("kw_xe_dap", "bicycle, xe_dap"),
            "o_to":   _kws("kw_o_to",   ""),
        }

    def stop(self):          self._stop.set()
    def _log(self, msg: str): self.log_q.put(msg)
    def _push(self):          self.stat_q.put(dict(self.stats))

    # ── history ──────────────────────────────────────────────────────────────

    def _history_load(self, out: Path):
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
            (out / self._HISTORY_FILE).write_text(
                json.dumps(sorted(self._done_days), ensure_ascii=False),
                encoding="utf-8")
        except Exception:
            pass

    # ── helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _day_list(from_str: str, to_str: str) -> list:
        def _parse(s):
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    return datetime.strptime(s[:19], fmt)
                except ValueError:
                    pass
            return datetime.now()

        from_dt = _parse(from_str)
        to_dt   = _parse(to_str)
        days, cur, end = [], from_dt.date(), to_dt.date()
        while cur <= end:
            d_from = (from_dt.strftime("%Y-%m-%d %H:%M:%S")
                      if cur == from_dt.date() else f"{cur} 00:00:00")
            d_to   = (to_dt.strftime("%Y-%m-%d %H:%M:%S")
                      if cur == to_dt.date()   else f"{cur} 23:59:59")
            days.append((d_from, d_to, str(cur)))
            cur += timedelta(days=1)
        return days

    # ── main loop ─────────────────────────────────────────────────────────────

    def run(self):
        cfg = self.cfg
        out = Path(cfg["output_dir"])
        api = Parkingv8ApiClient(cfg)

        self._log("Đang đăng nhập...")
        if not api.login():
            self._log("[LỖI] Không lấy được token — kiểm tra URL / tài khoản.")
            self.log_q.put("__DONE__")
            return
        self._log("Đăng nhập thành công.")

        endpoints = []
        src = cfg.get("event_source", "exits")
        if src in ("exits", "both"):
            endpoints.append("exits")
        if src in ("entries", "both"):
            endpoints.append("entries")

        from_d    = cfg["from_date"].strip().replace("T", " ")
        to_d      = cfg["to_date"].strip().replace("T", " ")
        size      = cfg.get("page_size", 100)
        sleep_s   = cfg.get("sleep", 0.05)
        days      = self._day_list(from_d, to_d)
        total_days = len(days)
        self._log(f"Khoảng thời gian: {from_d} → {to_d}")
        self._log(f"Tổng: {total_days} ngày | page size={size} | nguồn={', '.join(endpoints)}")

        max_lane = cfg.get("max_per_lane", 0)
        max_cat  = cfg.get("max_per_cat",  0)
        max_hour = cfg.get("max_per_hour", 0)
        limits   = []
        if max_lane: limits.append(f"{max_lane} ảnh/làn")
        if max_cat:  limits.append(f"{max_cat} ảnh/loại/làn/ngày")
        if max_hour: limits.append(f"{max_hour} ảnh/giờ/làn")
        self._log(f"Giới hạn: {', '.join(limits) if limits else 'không'}")

        self._history_load(out)
        skipped_days = 0

        for day_idx, (d_from, d_to, label) in enumerate(days, 1):
            if self._stop.is_set():
                break
            self.stats.update({"day_idx": day_idx, "total_days": total_days,
                                "day_label": label})
            self._push()
            if label in self._done_days:
                skipped_days += 1
                self._log(f"  ⏭ NGÀY {label} — đã tải trước đó, bỏ qua")
                continue
            self._log(f"\n{'═'*52}")
            self._log(f"  NGÀY {label}  ({day_idx}/{total_days})")
            self._log(f"{'═'*52}")
            for ep in endpoints:
                self._collect_day(api, ep, d_from, d_to, out, size, sleep_s)
            if not self._stop.is_set():
                self._history_mark(out, label)

        self._log("\n" + "─" * 52)
        self._log(
            f"Hoàn thành {total_days} ngày"
            f"{f' (bỏ qua {skipped_days} ngày đã tải)' if skipped_days else ''}: "
            f"{self.stats['event']} sự kiện, "
            f"{self.stats['found']} tìm thấy, "
            f"{self.stats['saved']} lưu, "
            f"{self.stats['skipped']} skip giới hạn, "
            f"{self.stats['error']} lỗi."
        )
        self._push()
        self.log_q.put("__DONE__")

    def _collect_day(self, api: Parkingv8ApiClient, endpoint: str,
                     d_from: str, d_to: str,
                     out: Path, size: int, sleep_s: float):
        page, empty_n = 0, 0
        max_pages = self.cfg.get("max_pages", 10000)
        while not self._stop.is_set() and page < max_pages:
            self._pause.wait()   # chờ nếu đang tạm dừng
            if self._stop.is_set():
                return
            self._log(f"  [{endpoint.upper()} PAGE {page}] Đang gọi API...")
            t0 = time.time()
            ok, data = api.search(endpoint, d_from, d_to, page, size)
            elapsed = time.time() - t0
            if not ok:
                self.stats["error"] += 1
                self._log(f"  [PAGE {page}] Lỗi/timeout sau {elapsed:.0f}s — bỏ qua.")
                page += 1
                self._push()
                time.sleep(2)
                continue

            total_count = (data.get("TotalCount") or data.get("totalCount") or 0)
            total_pages = (data.get("TotalPage")  or data.get("totalPage")  or 0)
            recs = (data.get("Data") or data.get("data") or [])

            if not recs:
                empty_n += 1
                if empty_n >= 3:
                    self._log(f"  [{endpoint.upper()} PAGE {page}] Hết dữ liệu ngày này.")
                    break
                page += 1
                continue
            empty_n = 0

            tp_info = f"/{total_pages}" if total_pages else ""
            self._log(
                f"  [{endpoint.upper()} PAGE {page}{tp_info}] "
                f"{len(recs)} sự kiện | {elapsed:.1f}s | tổng={total_count}")
            self.stats["page"]  += 1
            self.stats["event"] += len(recs)

            for rec in recs:
                if self._stop.is_set():
                    return
                self._process(api, rec, endpoint, out)

            self._push()

            # Stop if we've fetched all pages
            if total_pages and (page + 1) >= total_pages:
                break
            if total_count and self.stats["event"] >= total_count:
                break

            page += 1
            if sleep_s > 0:
                time.sleep(sleep_s)

    def _process(self, api: Parkingv8ApiClient, rec: dict, endpoint: str, out: Path):
        event_id = str(rec.get("id") or rec.get("Id") or "")[:8]
        plate    = _p8_safe(re.sub(r"[^0-9A-Za-z]", "",
                                   str(rec.get("plateNumber") or
                                       rec.get("PlateNumber") or "")))
        # datetime: try exit time first, fall back to entry time
        dt = (_p8_parse_dt(rec.get("createdUtc") or rec.get("CreatedUtc"))
              or _p8_parse_dt(_get_nested(rec, "entry.createdUtc"))
              or datetime.now())
        # lane name: exit device → entry device → "unknown_lane"
        lane = _p8_safe(
            _get_nested(rec, "device.name") or
            _get_nested(rec, "Device.Name") or
            _get_nested(rec, "entry.device.name") or
            "unknown_lane")
        # vehicle type: ưu tiên integer enum (EmVehicleType), fallback keyword trên name
        vt_int = _get_nested(rec, "collection.vehicleType")
        if vt_int is None:
            vt_int = _get_nested(rec, "accessKey.collection.vehicleType")
        if isinstance(vt_int, int) and vt_int in _VT_INT_MAP:
            vtype = _VT_INT_MAP[vt_int]
        else:
            vt_name = (_get_nested(rec, "collection.name") or
                       _get_nested(rec, "accessKey.collection.name") or "")
            vtype = _p8_categorize(str(vt_name), self._vtype_cfg)

        # Gọi detail API để lấy ảnh (search result trả images=[])
        full_id = str(rec.get("id") or rec.get("Id") or "")
        detail = api.fetch_detail(endpoint, full_id)
        if detail:
            images = api.extract_detail_images(detail, endpoint)
        else:
            images = api.extract_images(rec)   # fallback nếu detail API lỗi

        bad_result = _p8_bad_reason(rec) if self.cfg.get("collect_bad") else None
        bad_reason = bad_result[0] if bad_result else None
        bad_label  = bad_result[1] if bad_result else ""
        self._log(
            f"  [{event_id}] {plate or '?':12s} | {lane} | "
            f"{dt.strftime('%Y-%m-%d %H:%M')} | vt={vtype} | {len(images)} ảnh"
            + (f" | BAD:{bad_reason}[{bad_label}]" if bad_reason else ""))

        for img_url, img_suffix in images:
            if self._stop.is_set():
                return
            self._save_image(api, img_url, img_suffix, lane, vtype, dt, plate, out,
                             bad_reason, bad_label)

    def _save_image(self, api: Parkingv8ApiClient, url: str, suffix: str,
                    lane: str, vtype: str, dt: datetime, plate: str, out: Path,
                    bad_reason: Optional[str] = None, bad_label: str = ""):
        self.stats["found"] += 1

        if bad_reason:
            # chỉ lưu ảnh xe (bỏ ảnh toàn cảnh: fo=full-out, fi=full-in)
            if suffix in _FULL_SUFFIXES or suffix.lower() == "full":
                self.stats["skipped"] += 1
                return
            img = api.fetch_image(url)
            if img is None:
                self.stats["error"] += 1
                return
            save_dir = out / lane / "bad" / bad_reason / dt.strftime("%Y-%m-%d") / dt.strftime("%H")
            save_dir.mkdir(parents=True, exist_ok=True)
            ts = dt.strftime("%H%M%S")
            base = (f"{ts}_{bad_label}_{suffix}" if bad_label
                    else f"{ts}_{suffix}")
            idx = 0
            while True:
                sfx   = f"_{idx:03d}" if idx else ""
                fpath = save_dir / f"{base}{sfx}.jpg"
                if not fpath.exists():
                    break
                idx += 1
            ok_enc, buf = _cv2_mod.imencode(".jpg", img)
            if ok_enc:
                fpath.write_bytes(buf.tobytes())
                self.stats["bad_saved"] += 1
                self._log(f"      ✗[{bad_reason}] {fpath.name}")
            else:
                self.stats["error"] += 1
            return

        # giới hạn tổng ảnh/làn
        max_lane = self.cfg.get("max_per_lane", 0)
        if max_lane > 0 and self._lane_total.get(lane, 0) >= max_lane:
            if lane not in self._lane_warned:
                self._log(f"      ⏭ Làn [{lane}] đủ {max_lane} ảnh — bỏ qua")
                self._lane_warned.add(lane)
            self.stats["skipped"] += 1
            return

        # giới hạn ảnh/loại/làn/ngày → mỗi ngày đều có đủ mẫu
        max_cat = self.cfg.get("max_per_cat", 0)
        if max_cat > 0:
            cat_key = (lane, vtype, dt.strftime("%Y-%m-%d"))
            if self._lane_cat.get(cat_key, 0) >= max_cat:
                self.stats["skipped"] += 1
                return

        # giới hạn ảnh/giờ/làn
        max_hour = self.cfg.get("max_per_hour", 0)
        if max_hour > 0:
            hour_key = (lane, dt.strftime("%Y-%m-%d %H"))
            if self._lane_hourly.get(hour_key, 0) >= max_hour:
                self.stats["skipped"] += 1
                return

        img = api.fetch_image(url)
        if img is None:
            self.stats["error"] += 1
            self._log(f"      ✗ Lỗi tải: {url[:80]}")
            return

        # Xác định thư mục theo loại ảnh (overview/vehicle/plate)
        img_type = _p8_suffix_to_imgtype(suffix, vtype)

        # cấu trúc: <out>/<lane>/<img_type>/<YYYY-MM-DD>/<HH>/HHmmss_BSX_suffix.jpg
        save_dir = out / lane / img_type / dt.strftime("%Y-%m-%d") / dt.strftime("%H")
        save_dir.mkdir(parents=True, exist_ok=True)
        base = f"{dt.strftime('%H%M%S')}_{plate}_{suffix}" if plate else \
               f"{dt.strftime('%H%M%S')}_{suffix}"
        idx = 0
        while True:
            sfx  = f"_{idx:03d}" if idx else ""
            fpath = save_dir / f"{base}{sfx}.jpg"
            if not fpath.exists():
                break
            idx += 1

        ok_enc, buf = _cv2_mod.imencode(".jpg", img)
        if ok_enc:
            fpath.write_bytes(buf.tobytes())
            self.stats["saved"] += 1
            self._lane_total[lane] = self._lane_total.get(lane, 0) + 1
            cat_key  = (lane, vtype, dt.strftime("%Y-%m-%d"))
            self._lane_cat[cat_key] = self._lane_cat.get(cat_key, 0) + 1
            hour_key = (lane, dt.strftime("%Y-%m-%d %H"))
            self._lane_hourly[hour_key] = self._lane_hourly.get(hour_key, 0) + 1
            self._log(f"      ✓ {lane}/{img_type}/{fpath.name}")
            # Tạo file GT cho ảnh biển số cắt: <tên_file>\t<biển_số>
            if img_type.endswith("_bsx_cut") and plate:
                fpath.with_suffix(".txt").write_text(
                    f"{fpath.name}\t{plate}\n", encoding="utf-8")
        else:
            self.stats["error"] += 1
            self._log(f"      ✗ Lỗi encode: {url[:80]}")
