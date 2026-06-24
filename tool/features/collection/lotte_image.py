import base64
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
    _LI_API_BASE, _LI_USERNAME, _LI_PASSWORD,
    _LI_MINIO_EP, _LI_MINIO_AK, _LI_MINIO_SK, _LI_MINIO_BUCKET,
)
from ...core.imports import _req_mod, _REQUESTS_OK, _cv2_mod, _np_mod, _CV2_OK


def _li_img_type_to_path_parts(img_type: str):
    """Chuyển img_type → (vehicle_folder, sub_folder) cho cấu trúc mới."""
    if img_type.startswith("toan_canh_"):
        return img_type[len("toan_canh_"):], "anh_toan_canh"
    if img_type == "toan_canh":
        return "toan_canh", "anh_toan_canh"
    if img_type.endswith("_bsx_cut"):
        return img_type[:-len("_bsx_cut")], "anh_bsx"
    return img_type, "anh_xe"


def _li_hour_to_buoi(hour: int) -> str:
    if hour < 12:
        return "sang"
    if hour < 14:
        return "trua"
    if hour < 18:
        return "chieu"
    return "toi"


def _li_safe(s: str) -> str:
    nfkd = unicodedata.normalize("NFKD", str(s).strip())
    ascii_only = nfkd.encode("ascii", errors="ignore").decode("ascii")
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', ascii_only)
    cleaned = re.sub(r'_+', '_', cleaned).strip('_')
    return cleaned or "unknown"


def _li_bad_reason(rec: dict) -> Optional[Tuple[str, str, str]]:
    """Return (reason, plate_label, bad_direction) or None.

    bad_direction: 'in' | 'out' | 'both'  — which direction images to save.
    """
    plate_in  = re.sub(r"[^0-9A-Za-z]", "", str(rec.get("PlateIn")  or "")).upper()
    plate_out = re.sub(r"[^0-9A-Za-z]", "", str(rec.get("PlateOut") or "")).upper()
    plate_reg = re.sub(r"[^0-9A-Za-z]", "",
                       str(rec.get("RegistedPlate") or rec.get("RegisteredPlate") or
                           rec.get("CardPlate")     or rec.get("PlateNumber") or "")).upper()
    if not plate_in and not plate_out:
        return ("none", "", "both")
    if plate_in and plate_out and plate_in != plate_out:
        return ("in_out_mismatch", f"{plate_in}_{plate_out}", "both")
    if plate_reg:
        bad_in  = bool(plate_in)  and plate_in  != plate_reg
        bad_out = bool(plate_out) and plate_out != plate_reg
        if bad_in and bad_out:
            recognized = plate_out or plate_in
            return ("register_mismatch", f"{recognized}_{plate_reg}", "both")
        elif bad_in:
            return ("register_mismatch", f"{plate_in}_{plate_reg}", "in")
        elif bad_out:
            return ("register_mismatch", f"{plate_out}_{plate_reg}", "out")
    return None


def _vi_to_ascii(s: str) -> str:
    """Chuyển tiếng Việt → ASCII để so khớp không phân biệt dấu.
    Xử lý đặc biệt 'đ/Đ' vì NFKD không decompose ký tự này.
    """
    s = s.replace("đ", "d").replace("Đ", "D")
    return unicodedata.normalize("NFKD", s).encode("ascii", errors="ignore").decode()


def _li_match_kw(src: str, keywords: list) -> bool:
    """True nếu bất kỳ từ khóa nào khớp với src (không phân biệt dấu/hoa-thường)."""
    if not src or not keywords:
        return False
    s   = src.lower()
    s_n = _vi_to_ascii(s)
    for kw in keywords:
        k   = kw.lower()
        k_n = _vi_to_ascii(k)
        if k and (k in s or k_n in s_n):
            return True
    return False


def _li_categorize(description: str, card_group: str = "",
                   vtype_cfg: Optional[dict] = None) -> str:
    cfg = vtype_cfg or {}
    kw_tc  = cfg.get("toan_canh") or ["toàn cảnh"]
    kw_dap = cfg.get("xe_dap")    or ["xe đạp"]
    kw_may = cfg.get("xe_may")    or ["xe máy"]
    kw_oto = cfg.get("o_to")      or []

    # Xác định loại xe từ card_group
    if _li_match_kw(card_group, kw_dap):
        vtype = "xe_dap"
    elif _li_match_kw(card_group, kw_may):
        vtype = "xe_may"
    elif kw_oto and _li_match_kw(card_group, kw_oto):
        vtype = "o_to"
    else:
        vtype = "o_to"

    # description: toàn cảnh → kết hợp với loại xe
    if _li_match_kw(description, kw_tc):
        return f"toan_canh_{vtype}"
    return vtype


def _li_parse_dt(s: str) -> Optional[datetime]:
    if not s:
        return None
    s = str(s).strip().replace("Z", "")
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S",
                "%Y/%m/%d %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:19], fmt)
        except ValueError:
            pass
    return None


def _li_b64_like(s: str) -> bool:
    return (len(s) >= 256 and len(s) % 4 == 0
            and bool(re.fullmatch(r"[A-Za-z0-9+/]+={0,2}", s)))


class _SharedLaneState:
    """Thread-safe lane state shared across parallel LotteWorker instances."""
    __slots__ = ("_lock", "lane_total", "lane_warned", "known_lanes", "hist_lock")

    def __init__(self):
        self._lock        = threading.Lock()
        self.lane_total:  dict = {}   # {lane: total_saved}
        self.lane_warned: set  = set()
        self.known_lanes: set  = set()
        self.hist_lock    = threading.Lock()


class LotteApiClient:
    def __init__(self, cfg: dict):
        self.base     = cfg.get("api_base", _LI_API_BASE).rstrip("/")
        self.username = cfg.get("username", _LI_USERNAME)
        self.password = cfg.get("password", _LI_PASSWORD)
        self.timeout  = 60
        self.token: Optional[str] = None
        self._session = _req_mod.Session() if _req_mod else None
        self._minio   = None
        self._bucket  = cfg.get("minio_bucket", _LI_MINIO_BUCKET)

    def login(self) -> bool:
        if not self._session:
            return False
        try:
            import json as _json
            r = self._session.post(
                f"{self.base}/api/login",
                headers={"Content-Type": "application/json"},
                json={"username": self.username, "password": self.password},
                timeout=15,
            )
            r.raise_for_status()
            res = r.json().get("result")
            if res:
                self.token = _json.loads(res).get("Token")
            return bool(self.token)
        except Exception:
            return False

    def init_minio(self, ep: str, ak: str, sk: str, secure: bool = False) -> bool:
        try:
            from minio import Minio
            self._minio = Minio(ep, access_key=ak, secret_key=sk, secure=secure)
            self._minio.bucket_exists(self._bucket)
            return True
        except Exception:
            self._minio = None
            return False

    def search(self, from_date: str, to_date: str,
               page: int, size: int, keyword: str = "") -> Tuple[bool, dict, dict, dict]:
        import json as _json
        url  = f"{self.base}/api/tblcardevent/byPagingInOut"
        hdrs = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
        }
        body = {
            "keyword": keyword, "fromDate": from_date, "toDate": to_date,
            "cardgroupIds": "", "customergroupIds": "",
            "laneIds": "", "userIds": "", "plateNumber": "",
            "pageIndex": page, "pageSize": size,
        }
        for attempt in range(3):
            try:
                r = self._session.get(url, headers=hdrs, json=body,
                                      timeout=self.timeout)
                r.raise_for_status()
                raw  = r.json()
                res  = raw.get("result")
                data = _json.loads(res) if res else {}
                return True, data, body, raw
            except Exception:
                if attempt < 2:
                    time.sleep(2 * (attempt + 1))
        return False, {}, body, {}

    def fetch_image(self, file_path: str):
        if not file_path or not _CV2_OK:
            return None
        cv2 = _cv2_mod
        np  = _np_mod
        if file_path.startswith("data:image"):
            try:
                data = file_path.split(",", 1)[1]
                buf = np.frombuffer(base64.b64decode(data), np.uint8)
                return cv2.imdecode(buf, cv2.IMREAD_COLOR)
            except Exception:
                return None
        if _li_b64_like(file_path):
            try:
                buf = np.frombuffer(base64.b64decode(file_path), np.uint8)
                return cv2.imdecode(buf, cv2.IMREAD_COLOR)
            except Exception:
                return None
        if self._minio:
            try:
                key = file_path.lstrip("/")
                if key.lower().startswith(self._bucket.lower() + "/"):
                    key = key[len(self._bucket) + 1:]
                resp = self._minio.get_object(self._bucket, key)
                buf  = np.frombuffer(resp.read(), np.uint8)
                resp.close(); resp.release_conn()
                img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
                if img is not None:
                    return img
            except Exception:
                pass
        url = (file_path if file_path.startswith("http")
               else f"{self.base}/{file_path.lstrip('/')}")
        try:
            r = self._session.get(url, timeout=self.timeout,
                                  headers={"Authorization": f"Bearer {self.token}"})
            r.raise_for_status()
            buf = np.frombuffer(r.content, np.uint8)
            return cv2.imdecode(buf, cv2.IMREAD_COLOR)
        except Exception:
            return None


class LotteWorker:
    def __init__(self, cfg: dict, log_q: queue.Queue, stat_q: queue.Queue,
                 pause_event: threading.Event = None,
                 thread_id: int = 0,
                 days_list: list = None,
                 shared: '_SharedLaneState' = None,
                 send_done: bool = True,
                 global_total_days: int = None,
                 mode: str = 'full',
                 event_db=None):
        self.cfg         = cfg
        self.log_q       = log_q
        self.stat_q      = stat_q
        self._stop       = threading.Event()
        self._pause      = pause_event or threading.Event()
        self._pause.set()   # mặc định không pause
        self._thread_id        = thread_id
        self._days_list        = days_list        # None = tự tính từ cfg
        self._shared           = shared if shared is not None else _SharedLaneState()
        self._send_done        = send_done
        self._global_total_days = global_total_days
        self.stats: dict = {
            "page": 0, "total": 0, "event": 0, "found": 0,
            "saved": 0, "skipped": 0, "error": 0, "bad_saved": 0,
            "day_idx": 0, "total_days": 0, "day_label": "",
            "thread_id": thread_id,
        }
        self._mode     = mode
        self._event_db = event_db
        self._lane_cat: dict    = {}
        self._lane_hourly: dict = {}
        self._lane_buoi: dict   = {}
        self._done_days: set    = set()
        self._vtype_cfg: dict   = self._parse_vtype_cfg()

    # ── metadata extraction (scan_only mode) ──────────────────────────────

    def _extract_meta(self, rec: dict) -> dict:
        """Extract metadata từ API record mà không download ảnh."""
        event_id = str(rec.get("Id") or "")
        lane     = _li_safe(rec.get("InLaneName") or "unknown_lane")
        plate    = _li_safe(re.sub(r"[^0-9A-Za-z]", "",
                                   str(rec.get("PlateIn") or rec.get("PlateOut") or "")))
        dt_in    = _li_parse_dt(rec.get("DatetimeIn")) or datetime.now()
        cg       = str(rec.get("CardGroupName") or "")
        imgs_all = list(rec.get("ImagesIn") or []) + list(rec.get("ImagesOut") or [])
        desc0    = (imgs_all[0].get("Description", "") if imgs_all and
                    isinstance(imgs_all[0], dict) else "")
        vtype    = _li_categorize(desc0, cg, self._vtype_cfg)
        refs     = [i["FilePath"] for i in imgs_all
                    if isinstance(i, dict) and i.get("FilePath")]
        _preg = re.sub(r"[^0-9A-Za-z]", "",
                       str(rec.get("RegistedPlate") or rec.get("RegisteredPlate") or
                           rec.get("CardPlate") or "")).upper()
        _pin  = re.sub(r"[^0-9A-Za-z]", "", str(rec.get("PlateIn")  or "")).upper()
        _pout = re.sub(r"[^0-9A-Za-z]", "", str(rec.get("PlateOut") or "")).upper()
        has_gt = bool(_preg or (_pin and _pout and _pin == _pout))
        return {
            "event_id": event_id, "date": dt_in.strftime("%Y-%m-%d"),
            "hour": dt_in.hour,   "minute": dt_in.minute,
            "lane": lane,         "vtype": vtype,
            "plate": plate,       "has_gt": 1 if has_gt else 0,
            "image_refs": refs,   "scanned_at": datetime.now().isoformat(),
        }

    # ── lịch sử ngày đã tải ────────────────────────────────────────────────

    _HISTORY_FILE = ".lotte_done.json"

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

    # ────────────────────────────────────────────────────────────────────────

    def _parse_vtype_cfg(self) -> dict:
        def _kws(key: str, default: str) -> list:
            raw = self.cfg.get(key, default)
            return [k.strip() for k in str(raw).split(",") if k.strip()]
        return {
            "toan_canh": _kws("kw_toan_canh", "toàn cảnh"),
            "xe_may":    _kws("kw_xe_may",    "xe máy"),
            "xe_dap":    _kws("kw_xe_dap",    "xe đạp"),
            "o_to":      _kws("kw_o_to",      ""),
        }

    def stop(self):
        self._stop.set()

    def _log(self, msg: str):
        if self._thread_id:
            msg = f"[T{self._thread_id}] {msg}"
        self.log_q.put(msg)

    def _push(self):
        s = dict(self.stats)
        s["thread_id"] = self._thread_id
        self.stat_q.put(s)

    @staticmethod
    def _day_list(from_str: str, to_str: str):
        from_dt = _li_parse_dt(from_str) or datetime.now()
        to_dt   = _li_parse_dt(to_str)   or datetime.now()
        days, cur, end = [], from_dt.date(), to_dt.date()
        while cur <= end:
            d_from = (from_dt.strftime("%Y-%m-%dT%H:%M:%S")
                      if cur == from_dt.date() else f"{cur}T00:00:00")
            d_to   = (to_dt.strftime("%Y-%m-%dT%H:%M:%S")
                      if cur == to_dt.date()   else f"{cur}T23:59:59")
            days.append((d_from, d_to, str(cur)))
            cur += timedelta(days=1)
        return days

    def run(self):
        cfg = self.cfg
        out = Path(cfg["output_dir"])
        api = LotteApiClient(cfg)

        self._log("Đang đăng nhập...")
        if not api.login():
            self._log("[LỖI] Không lấy được token — kiểm tra địa chỉ / tài khoản.")
            if self._send_done:
                self.log_q.put("__DONE__")
            return
        self._log("Đăng nhập thành công.")

        if cfg.get("use_minio", True):
            ok = api.init_minio(
                cfg.get("minio_ep",  _LI_MINIO_EP),
                cfg.get("minio_ak",  _LI_MINIO_AK),
                cfg.get("minio_sk",  _LI_MINIO_SK),
            )
            self._log(f"MinIO: {'kết nối OK' if ok else 'không khả dụng — dùng HTTP'}")

        size    = cfg.get("page_size", 100)
        sleep_s = cfg.get("sleep", 0.05)

        if self._days_list is not None:
            # Chế độ song song: ngày được phân công bởi coordinator
            days       = self._days_list
            total_days = self._global_total_days if self._global_total_days is not None else len(days)
        else:
            # Chế độ đơn luồng: tự tính ngày từ config
            from_d = cfg["from_date"].strip().replace(" ", "T")
            to_d   = cfg["to_date"].strip().replace(" ", "T")
            days   = self._day_list(from_d, to_d)
            total_days = len(days)
            self._log(f"Khoảng thời gian: {from_d} → {to_d}")
            self._log(f"Tổng: {total_days} ngày | page size={size}")
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
            self._collect_day(api, d_from, d_to, out, size, sleep_s)
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

    def _collect_day(self, api: LotteApiClient, d_from: str, d_to: str,
                     out: Path, size: int, sleep_s: float):
        page, empty_n = 1, 0
        while not self._stop.is_set():
            self._pause.wait()   # chờ nếu đang tạm dừng
            if self._stop.is_set():
                return
            self._log(f"  [PAGE {page}] Đang gọi API...")
            t0 = time.time()
            ok, data, req_body, raw_resp = api.search(
                d_from, d_to, page, size,
                keyword=self.cfg.get("keyword", ""))
            elapsed = time.time() - t0
            if page == 1:
                import json as _j
                self._log(f"  ── REQUEST ──")
                self._log(f"  {_j.dumps(req_body, ensure_ascii=False)}")
                self._log(f"  ── RESPONSE (raw keys) ──")
                if raw_resp:
                    top_keys = {k: (str(v)[:120] if not isinstance(v, (dict, list)) else f"[{type(v).__name__}]")
                                for k, v in raw_resp.items()}
                    self._log(f"  {_j.dumps(top_keys, ensure_ascii=False)}")
                    if data and isinstance(data, dict):
                        recs = data.get("Data") or data.get("data") or []
                        self._log(f"  result parsed: TotalItems={data.get('TotalItems') or data.get('TotalRecords')}  records={len(recs)}")
                        if recs:
                            self._log(f"  record[0] keys: {list(recs[0].keys())}")
                            self._log(f"  record[0]: {_j.dumps(recs[0], ensure_ascii=False, default=str)[:400]}")
                else:
                    self._log(f"  (response rỗng)")
            if not ok:
                self.stats["error"] += 1
                self._log(f"  [PAGE {page}] Lỗi/timeout sau {elapsed:.0f}s — bỏ qua.")
                page += 1
                self._push()
                time.sleep(2)
                continue
            if isinstance(data, dict):
                day_total = data.get("TotalItems") or data.get("TotalRecords") or 0
                recs = data.get("Data") or data.get("data") or []
            else:
                day_total, recs = 0, (data if isinstance(data, list) else [])
            if not recs:
                empty_n += 1
                if empty_n >= 3:
                    self._log(f"  [PAGE {page}] Hết dữ liệu ngày này.")
                    break
                page += 1
                continue
            empty_n = 0
            total_info = f"/{day_total}" if day_total else ""
            self._log(f"  [PAGE {page}{total_info}] {len(recs)} sự kiện | {elapsed:.1f}s")
            self.stats["page"]  += 1
            self.stats["event"] += len(recs)
            scan_batch = [] if self._mode == 'scan_only' else None
            for rec in recs:
                if self._stop.is_set():
                    return
                if scan_batch is not None:
                    scan_batch.append(self._extract_meta(rec))
                else:
                    self._process(api, rec, out)
            if scan_batch and self._event_db is not None:
                self._event_db.insert_events('lotte', scan_batch)
            self._push()
            page += 1
            remaining = max(0.0, min(sleep_s, 5.0) - elapsed)
            if remaining > 0:
                time.sleep(remaining)

    def _process(self, api: LotteApiClient, rec: dict, out: Path):
        event_id = str(rec.get("Id") or "")[:8]
        lane_in  = _li_safe(rec.get("InLaneName")  or "unknown_lane")
        lane_out = _li_safe(rec.get("OutLaneName") or lane_in)
        plate    = _li_safe(re.sub(r"[^0-9A-Za-z]", "",
                                   str(rec.get("PlateIn") or rec.get("PlateOut") or "")))
        dt_in    = _li_parse_dt(rec.get("DatetimeIn"))  or datetime.now()
        dt_out   = _li_parse_dt(rec.get("DateTimeOut")) or dt_in
        imgs_in  = rec.get("ImagesIn")  or []
        imgs_out = rec.get("ImagesOut") or []
        bad_result    = _li_bad_reason(rec) if self.cfg.get("collect_bad") else None
        bad_reason    = bad_result[0] if bad_result else None
        bad_label     = bad_result[1] if bad_result else ""
        bad_direction = bad_result[2] if bad_result else ""
        card_group = str(rec.get("CardGroupName") or rec.get("VehicleType") or "")
        # xe đạp không có biển số là bình thường → không phải sự kiện xấu
        if bad_reason == "none" and _li_categorize("", card_group, self._vtype_cfg) == "xe_dap":
            bad_reason = None
            bad_label  = ""
            bad_direction = ""
        # GT plate: xe tháng → biển đăng ký; xe lượt → biển nếu PlateIn==PlateOut, else None
        _plate_reg = re.sub(r"[^0-9A-Za-z]", "",
                            str(rec.get("RegistedPlate") or rec.get("RegisteredPlate") or
                                rec.get("CardPlate") or "")).upper()
        _plate_in  = re.sub(r"[^0-9A-Za-z]", "", str(rec.get("PlateIn")  or "")).upper()
        _plate_out = re.sub(r"[^0-9A-Za-z]", "", str(rec.get("PlateOut") or "")).upper()
        if _plate_reg:
            gt_plate = _li_safe(_plate_reg)
        elif _plate_in and _plate_out and _plate_in == _plate_out:
            gt_plate = _li_safe(_plate_in)
        else:
            gt_plate = None
        cg_display = f" | nhóm thẻ: {card_group}" if card_group else ""
        self._log(f"  [{event_id}] {plate or '?':12s} | {lane_in} | {dt_in.strftime('%Y-%m-%d %H:%M')}"
                  f"{cg_display} | {len(imgs_in)+len(imgs_out)} ảnh"
                  + (f" | BAD:{bad_reason}[{bad_label}]" if bad_reason else ""))
        max_lane = self.cfg.get("max_per_lane", 0)
        if max_lane > 0:
            with self._shared._lock:
                self._shared.known_lanes.add(lane_in)
                if lane_out != lane_in:
                    self._shared.known_lanes.add(lane_out)

        event_folder = _li_safe(str(rec.get("Id") or event_id or "evt"))
        event_saved = False
        for idx, img_obj in enumerate(imgs_in, 1):
            if self._stop.is_set():
                return
            desc  = img_obj.get("Description", "") if isinstance(img_obj, dict) else ""
            vtype = _li_categorize(desc, card_group, self._vtype_cfg)
            self._log(f"    IN  [{idx}/{len(imgs_in)}] \"{desc}\" → {vtype}")
            if self._save_image(api, img_obj, lane_in, dt_in, plate, out,
                                bad_reason, bad_label, card_group, "in", bad_direction,
                                event_folder, gt_plate=gt_plate):
                event_saved = True
        for idx, img_obj in enumerate(imgs_out, 1):
            if self._stop.is_set():
                return
            desc  = img_obj.get("Description", "") if isinstance(img_obj, dict) else ""
            vtype = _li_categorize(desc, card_group, self._vtype_cfg)
            self._log(f"    OUT [{idx}/{len(imgs_out)}] \"{desc}\" → {vtype}")
            save_lane = lane_in if bad_reason else lane_out
            if self._save_image(api, img_obj, save_lane, dt_out, plate, out,
                                bad_reason, bad_label, card_group, "out", bad_direction,
                                event_folder, gt_plate=gt_plate):
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

    def _save_image(self, api: LotteApiClient, img_obj, lane: str,
                    dt: datetime, plate: str, out: Path,
                    bad_reason: Optional[str] = None, bad_label: str = "",
                    card_group: str = "", direction: str = "", bad_direction: str = "",
                    event_id: str = "", gt_plate: Optional[str] = None) -> bool:
        if not isinstance(img_obj, dict):
            return False
        file_path   = img_obj.get("FilePath")   or ""
        description = img_obj.get("Description") or ""
        if not file_path:
            return False

        img_type = _li_categorize(description, card_group, self._vtype_cfg)
        self.stats["found"] += 1

        if bad_reason:
            # chỉ lưu ảnh xe: bỏ qua toàn cảnh và xe đạp
            if img_type.startswith("toan_canh_") or img_type == "xe_dap":
                self.stats["skipped"] += 1
                return False
            # register_mismatch: chỉ lưu ảnh theo chiều có lỗi
            if bad_reason == "register_mismatch" and bad_direction in ("in", "out"):
                if direction != bad_direction:
                    self.stats["skipped"] += 1
                    return False
            img = api.fetch_image(file_path)
            if img is None:
                self.stats["error"] += 1
                return False
            # folder: bad/{lane}/{reason}/{date}/{event_id}/{in|out}/
            eid = event_id or "evt"
            save_dir = out / "bad" / lane / bad_reason / dt.strftime("%Y-%m-%d") / eid / direction
            save_dir.mkdir(parents=True, exist_ok=True)
            ts = dt.strftime("%H%M%S")
            base_name = f"{ts}_{bad_label}" if bad_label else ts
            idx = 0
            while True:
                sfx   = f"_{idx:03d}" if idx else ""
                fpath = save_dir / f"{base_name}{sfx}.jpg"
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

        buoi = _li_hour_to_buoi(dt.hour)   # tính sớm để dùng cho limit check

        # --- giới hạn tổng ảnh/làn (thread-safe) ---
        max_lane = self.cfg.get("max_per_lane", 0)
        if max_lane > 0:
            with self._shared._lock:
                if self._shared.lane_total.get(lane, 0) >= max_lane:
                    if lane not in self._shared.lane_warned:
                        self._log(f"      ⏭ Làn [{lane}] đủ {max_lane} ảnh — bỏ qua")
                        self._shared.lane_warned.add(lane)
                    self.stats["skipped"] += 1
                    return False

        # --- giới hạn ảnh/loại/làn/ngày → mỗi ngày đều có đủ mẫu ---
        max_cat = self.cfg.get("max_per_cat", 0)
        if max_cat > 0:
            cat_key = (lane, img_type, dt.strftime("%Y-%m-%d"))
            if self._lane_cat.get(cat_key, 0) >= max_cat:
                self.stats["skipped"] += 1
                return False

        # --- giới hạn ảnh/buổi/làn/ngày → đa dạng thời gian trong ngày ---
        max_buoi = self.cfg.get("max_per_buoi", 0)
        if max_buoi > 0:
            buoi_key = (lane, dt.strftime("%Y-%m-%d"), buoi)
            if self._lane_buoi.get(buoi_key, 0) >= max_buoi:
                self.stats["skipped"] += 1
                return False

        img = api.fetch_image(file_path)
        if img is None:
            self.stats["error"] += 1
            self._log(f"      ✗ Lỗi tải: {file_path}")
            return False

        vtype_folder, sub_folder = _li_img_type_to_path_parts(img_type)
        save_dir = out / vtype_folder / sub_folder / dt.strftime("%Y-%m-%d") / buoi / lane
        save_dir.mkdir(parents=True, exist_ok=True)
        ts_str    = dt.strftime("%H%M%S")
        base_name = f"{ts_str}_{plate}" if plate else ts_str
        idx = 0
        while True:
            suffix = f"_{idx:03d}" if idx else ""
            fpath  = save_dir / f"{base_name}{suffix}.jpg"
            if not fpath.exists():
                break
            idx += 1
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
                self._shared.lane_total[lane] = self._shared.lane_total.get(lane, 0) + 1
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
            self._log(f"      ✗ Lỗi encode: {file_path}")
            return False
