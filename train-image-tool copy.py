"""
KZTEK Image Tools — GUI
  Tab 1: Crop by YOLO Label
  Tab 2: Split Images into folders
  Tab 3: Dataset Checker / OCR Review
  Tab 4: GT Stats — tiến độ & phân bố ký tự
  Tab 5: Rename — đổi tên file thành số thứ tự
"""

import json
import math
import os
import queue
import random
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from tkinter import *
from tkinter import filedialog, ttk, messagebox

import base64
import re
import time
import unicodedata
from datetime import datetime, timedelta
from typing import Optional, Tuple

try:
    import requests as _req_mod
    _REQUESTS_OK = True
except ImportError:
    _req_mod = None
    _REQUESTS_OK = False

try:
    import cv2 as _cv2_mod
    import numpy as _np_mod
    _CV2_OK = True
except ImportError:
    _cv2_mod = None
    _np_mod  = None
    _CV2_OK  = False

try:
    import pythoncom
    import win32com.client
    _TTS_OK = True
except ImportError:
    _TTS_OK = False

try:
    from gtts import gTTS as _gTTS
    _GTTS_OK = True
except ImportError:
    _GTTS_OK = False

try:
    import tkinterdnd2 as _dnd_mod
    _DND_OK = True
except ImportError:
    _dnd_mod = None
    _DND_OK = False

try:
    from paddleocr import PaddleOCR as _PaddleOCR
    _PADDLE_OK = True
except Exception:
    _PaddleOCR = None
    _PADDLE_OK = False

# ── constants ──────────────────────────────────────────────────────────────────

CLASS_NAMES = {
    0: "car", 1: "motorcycle", 2: "bus",
    3: "truck", 4: "bicycle", 5: "license_plate",
}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".gif",
                    ".tiff", ".tif", ".heic", ".heif"}

_VI = {
    '0': 'kong', '1': 'mot', '2': 'hai', '3': 'ba',
    '4': 'bon',  '5': 'nam', '6': 'sau', '7': 'bay',
    '8': 'tam',  '9': 'chin',
}
_VI_FULL = {
    'A': 'A',      'B': 'Bê',     'C': 'Xê',     'D': 'Đê',
    'E': 'E',      'F': 'Ép',     'G': 'Gờ',     'H': 'Hát',
    'I': 'I',      'J': 'Gi',     'K': 'Ca',     'L': 'Lờ',
    'M': 'Mờ',     'N': 'Nờ',     'O': 'O',      'P': 'Bê',
    'Q': 'Quy',    'R': 'Rờ',     'S': 'Ét',     'T': 'Tê',
    'U': 'U',      'V': 'Vê',     'W': 'Đáp liu','X': 'Ích',
    'Y': 'Y',      'Z': 'Rét',
    '0': 'Không',  '1': 'Một',    '2': 'Hai',    '3': 'Ba',
    '4': 'Bốn',    '5': 'Năm',    '6': 'Sáu',    '7': 'Bảy',
    '8': 'Tám',    '9': 'Chín',
}

BG      = "#1e1e2e"
CARD    = "#2a2a3e"
ACCENT  = "#F05922"
ACCENT2 = "#4A3F8C"
TEXT    = "#e0e0f0"
DIM     = "#9090b0"
SUCCESS = "#4caf50"
F_MAIN  = ("Segoe UI", 10)
F_BOLD  = ("Segoe UI Semibold", 11)
F_MONO  = ("Consolas", 9)

# ── LotteImage: API defaults ─────────────────────────────────────────────────
_LI_API_BASE     = "http://119.17.223.230:2100"
_LI_USERNAME     = "kztek"
_LI_PASSWORD     = "123456"
_LI_MINIO_EP     = "119.17.223.230:9080"
_LI_MINIO_AK     = "kztek"
_LI_MINIO_SK     = "Kztek123456"
_LI_MINIO_BUCKET = "parking-images"

# ── settings persistence ───────────────────────────────────────────────────────
_SETTINGS_FILE = Path(__file__).with_name(".kztek_tools_settings.json")
_CFG: dict = {}


def _cfg_load():
    global _CFG
    try:
        if _SETTINGS_FILE.exists():
            _CFG = json.loads(_SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        _CFG = {}


def _cfg_save():
    try:
        _SETTINGS_FILE.write_text(
            json.dumps(_CFG, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _bind_cfg(key: str, var):
    """Khôi phục giá trị đã lưu vào var và tự động lưu mỗi khi thay đổi."""
    if key in _CFG:
        try:
            var.set(_CFG[key])
        except Exception:
            pass

    def _cb(*_):
        _CFG[key] = var.get()
        _cfg_save()

    var.trace_add("write", _cb)


def _cfg_dir(key: str) -> str:
    """Trả về initialdir đã lưu cho key (hoặc '' nếu không hợp lệ)."""
    v = _CFG.get(key, "")
    return v if v and Path(v).exists() else ""


_cfg_load()


# ── core: crop ─────────────────────────────────────────────────────────────────

def _parse_label(path):
    boxes = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            p = line.strip().split()
            if len(p) >= 5:
                boxes.append((int(p[0]), *map(float, p[1:5])))
    return boxes


def _yolo_px(xc, yc, w, h, iw, ih):
    x1 = max(0,  int((xc - w/2) * iw))
    y1 = max(0,  int((yc - h/2) * ih))
    x2 = min(iw, int((xc + w/2) * iw))
    y2 = min(ih, int((yc + h/2) * ih))
    return x1, y1, x2, y2


def run_crop(image_dir, label_dir, output_dir, log, progress):
    from PIL import Image
    img_dir = Path(image_dir)
    lbl_dir = Path(label_dir)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for cn in CLASS_NAMES.values():
        (out_dir / cn).mkdir(exist_ok=True)

    files = sorted(f for f in img_dir.iterdir()
                   if f.suffix.lower() in IMAGE_EXTENSIONS)
    total = len(files)
    if not total:
        log("⚠  Không tìm thấy ảnh."); return

    saved = missing = 0
    for i, fp in enumerate(files, 1):
        progress(i, total)
        lp = lbl_dir / (fp.stem + ".txt")
        if not lp.exists():
            missing += 1; continue
        boxes = _parse_label(lp)
        if not boxes: continue
        try:
            img = Image.open(fp).convert("RGB")
        except Exception as e:
            log(f"[LỖI] {fp.name}: {e}"); continue
        iw, ih = img.size
        cnt = {}
        for cid, xc, yc, w, h in boxes:
            cn = CLASS_NAMES.get(cid, f"class{cid}")
            cnt[cn] = cnt.get(cn, 0) + 1
            x1, y1, x2, y2 = _yolo_px(xc, yc, w, h, iw, ih)
            if x2 <= x1 or y2 <= y1: continue
            img.crop((x1, y1, x2, y2)).save(
                out_dir / cn / f"{fp.stem}__{cn}_{cnt[cn]:03d}.jpg",
                "JPEG", quality=95)
            saved += 1
        log(f"✔  {fp.name}  ({len(boxes)} bbox)")

    log("─" * 58)
    log(f"Tổng ảnh xử lý : {total - missing} / {total}")
    log(f"Thiếu label     : {missing}")
    log(f"Crops đã lưu    : {saved}")
    log(f"Thư mục output  : {out_dir.resolve()}")


# ── core: crop by label (enhanced) ───────────────────────────────────────────

def run_crop_by_label(cfg, log, progress, stop_event):
    from PIL import Image as _PI
    img_dir = Path(cfg["image_dir"])
    lbl_dir = Path(cfg["label_dir"])
    out_dir = Path(cfg["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    state_file = out_dir / ".crop_by_label_state.json"
    state = {"processed": [], "src": [str(img_dir), str(lbl_dir)]}
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    if state.get("src") != [str(img_dir), str(lbl_dir)]:
        state = {"processed": [], "src": [str(img_dir), str(lbl_dir)]}
    done_set = set(state.get("processed", []))

    keep_cls   = set(cfg["keep_classes"]) if cfg.get("filter_classes") else None
    padding    = max(0, int(cfg.get("padding_px", 0)))
    min_w      = max(0, int(cfg.get("min_w_px", 0)))
    min_h      = max(0, int(cfg.get("min_h_px", 0)))
    by_class   = cfg.get("split_by_class", True)
    class_map  = cfg.get("class_names_map", {})
    quality    = int(cfg.get("jpeg_quality", 95))
    recursive  = cfg.get("recursive", False)

    if recursive:
        images = sorted(f for f in img_dir.rglob("*")
                        if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS)
    else:
        images = sorted(f for f in img_dir.iterdir()
                        if f.suffix.lower() in IMAGE_EXTENSIONS)

    total = len(images)
    if not total:
        log("⚠  Không tìm thấy ảnh."); return

    # State key dùng relative path để hỗ trợ recursive
    def _key(fp): return str(fp.relative_to(img_dir))

    prev = sum(1 for f in images if _key(f) in done_set)
    log(f"📂  Tổng: {total}  |  Đã có: {prev}  |  Còn lại: {total - prev}")
    if recursive:
        log(f"🔍  Quét đệ quy toàn bộ subfolder")

    saved = skipped = no_label = 0

    for i, fp in enumerate(images, 1):
        if stop_event.is_set():
            log("⚠  Dừng theo yêu cầu."); break
        progress(i, total)
        key = _key(fp)
        if key in done_set:
            skipped += 1; continue

        # Tìm label: giữ nguyên cấu trúc subfolder tương đối
        rel = fp.relative_to(img_dir)
        lp  = lbl_dir / rel.parent / (fp.stem + ".txt")
        if not lp.exists():
            no_label += 1; done_set.add(key); continue

        boxes = _parse_label(str(lp))
        if not boxes:
            done_set.add(key); continue

        try:
            img = _PI.open(fp).convert("RGB")
            iw, ih = img.size
        except Exception as e:
            log(f"[LỖI] {fp.name}: {e}"); continue

        cnt = {}
        n_crop = 0
        for cid, xc, yc, bw, bh in boxes:
            if keep_cls and cid not in keep_cls:
                continue
            cname = class_map.get(cid, f"class{cid}")
            cnt[cname] = cnt.get(cname, 0) + 1

            x1, y1, x2, y2 = _yolo_px(xc, yc, bw, bh, iw, ih)
            if padding:
                x1 = max(0, x1 - padding)
                y1 = max(0, y1 - padding)
                x2 = min(iw, x2 + padding)
                y2 = min(ih, y2 + padding)

            cw, ch = x2 - x1, y2 - y1
            if cw < max(min_w, 1) or ch < max(min_h, 1):
                continue

            dest = (out_dir / cname) if by_class else out_dir
            dest.mkdir(parents=True, exist_ok=True)
            # Prefix subfolder name vào filename khi recursive để tránh trùng
            prefix = rel.parent.as_posix().replace("/", "_") + "__" if recursive and rel.parent != Path(".") else ""
            out_name = f"{prefix}{fp.stem}__{cname}_{cnt[cname]:03d}.jpg"
            out_path = dest / out_name
            _col = 0
            while out_path.exists():
                _col += 1
                out_path = dest / f"{out_name[:-4]}_{_col:02d}.jpg"
            img.crop((x1, y1, x2, y2)).save(out_path, "JPEG", quality=quality)
            n_crop += 1

        if n_crop:
            saved += n_crop
            log(f"✔  {key}  →  {n_crop} crop(s)")
        done_set.add(key)
        if len(done_set) % 50 == 0:
            state["processed"] = list(done_set)
            state_file.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

    state["processed"] = list(done_set)
    state_file.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    log("─" * 58)
    log(f"Tổng ảnh       : {total}")
    log(f"Bỏ qua (đã có) : {skipped}")
    log(f"Thiếu label    : {no_label}")
    log(f"Crops đã lưu   : {saved}")
    log(f"Thư mục output : {out_dir.resolve()}")


# ── core: split ────────────────────────────────────────────────────────────────

def run_split(source_dir, output_dir, max_per_folder, do_move, log, progress):
    src = Path(source_dir)
    files = sorted(f for f in src.rglob("*")
                   if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS)
    total = len(files)
    if not total:
        log("⚠  Không tìm thấy ảnh trong thư mục nguồn."); return

    out = Path(output_dir) if output_dir else src.parent / (src.name + "_split")
    out.mkdir(parents=True, exist_ok=True)

    n_folders = math.ceil(total / max_per_folder)
    pad = len(str(n_folders))
    log(f"Tổng ảnh        : {total}")
    log(f"Tối đa / folder : {max_per_folder}")
    log(f"Số folder tạo   : {n_folders}")
    log(f"Hành động       : {'Di chuyển' if do_move else 'Sao chép'}")
    log(f"Thư mục đầu ra  : {out.resolve()}")
    log("─" * 58)

    for i, fp in enumerate(files):
        progress(i + 1, total)
        dest_folder = out / ("part_" + str(i // max_per_folder + 1).zfill(pad))
        dest_folder.mkdir(exist_ok=True)
        dest = dest_folder / fp.name
        c = 1
        while dest.exists():
            dest = dest_folder / f"{fp.stem}_{c}{fp.suffix}"; c += 1
        (shutil.move if do_move else shutil.copy2)(str(fp), dest)
        if (i + 1) % 100 == 0 or (i + 1) == total:
            log(f"✔  Đã xử lý: {i+1}/{total}  →  {dest_folder.name}")

    log("─" * 58)
    log(f"Hoàn thành! Đã tạo {n_folders} folder trong '{out.resolve()}'")


# ── core: gt analysis ──────────────────────────────────────────────────────────

def analyze_gt(gt_path):
    """Parse gt.txt → (labels, char_counts, length_counts)."""
    from collections import Counter
    labels = []
    try:
        with open(gt_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split("\t") if "\t" in line else line.split(" ", 1)
                labels.append(parts[1] if len(parts) >= 2 else "")
    except Exception:
        pass
    char_counts = Counter()
    for lbl in labels:
        for c in lbl.upper():
            if c.isalnum():
                char_counts[c] += 1
    length_counts = Counter(len(lbl) for lbl in labels)
    return labels, dict(char_counts), dict(length_counts)


def _heat_color(count, max_count):
    """Interpolate #252540 → #F05922 (sqrt scale) for heatmap cells."""
    if max_count == 0 or count == 0:
        return "#252540"
    t = (count / max_count) ** 0.5
    r = int(0x25 + (0xF0 - 0x25) * t)
    g = int(0x25 + (0x59 - 0x25) * t)
    b = int(0x40 + (0x22 - 0x40) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


# ── LotteImage: helpers ───────────────────────────────────────────────────────

def _li_safe(s: str) -> str:
    nfkd = unicodedata.normalize("NFKD", str(s).strip())
    ascii_only = nfkd.encode("ascii", errors="ignore").decode("ascii")
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', ascii_only)
    cleaned = re.sub(r'_+', '_', cleaned).strip('_')
    return cleaned or "unknown"


def _li_categorize(description: str) -> str:
    d = description.lower()
    if "toàn cảnh" in d or "toan canh" in d:
        return "overview"
    if "xe máy" in d or "xe may" in d:
        return "bike"
    return "car"


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


# ── LotteImage: ApiClient ─────────────────────────────────────────────────────

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
               page: int, size: int) -> Tuple[bool, dict]:
        import json as _json
        url  = f"{self.base}/api/tblcardevent/byPagingInOut"
        hdrs = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
        }
        body = {
            "keyword": "", "fromDate": from_date, "toDate": to_date,
            "cardgroupIds": "", "customergroupIds": "",
            "laneIds": "", "userIds": "", "plateNumber": "",
            "pageIndex": page, "pageSize": size,
        }
        for attempt in range(3):
            try:
                r = self._session.get(url, headers=hdrs, json=body,
                                      timeout=self.timeout)
                r.raise_for_status()
                res = r.json().get("result")
                return True, (_json.loads(res) if res else {})
            except Exception:
                if attempt < 2:
                    time.sleep(2 * (attempt + 1))
        return False, {}

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


# ── LotteImage: Worker ────────────────────────────────────────────────────────

class LotteWorker:
    def __init__(self, cfg: dict, log_q: queue.Queue, stat_q: queue.Queue):
        self.cfg    = cfg
        self.log_q  = log_q
        self.stat_q = stat_q
        self._stop  = threading.Event()
        self.stats: dict = {
            "page": 0, "total": 0, "event": 0, "found": 0,
            "saved": 0, "error": 0,
            "day_idx": 0, "total_days": 0, "day_label": "",
        }

    def stop(self):
        self._stop.set()

    def _log(self, msg: str):
        self.log_q.put(msg)

    def _push(self):
        self.stat_q.put(dict(self.stats))

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

        from_d = cfg["from_date"].strip().replace(" ", "T")
        to_d   = cfg["to_date"].strip().replace(" ", "T")
        size   = cfg.get("page_size", 100)
        sleep_s = cfg.get("sleep", 0.05)
        days   = self._day_list(from_d, to_d)
        total_days = len(days)
        self._log(f"Khoảng thời gian: {from_d} → {to_d}")
        self._log(f"Tổng: {total_days} ngày | page size={size}")

        for day_idx, (d_from, d_to, label) in enumerate(days, 1):
            if self._stop.is_set():
                break
            self.stats.update({"day_idx": day_idx, "total_days": total_days,
                                "day_label": label})
            self._push()
            self._log(f"\n{'═'*52}")
            self._log(f"  NGÀY {label}  ({day_idx}/{total_days})")
            self._log(f"{'═'*52}")
            self._collect_day(api, d_from, d_to, out, size, sleep_s)

        self._log("\n" + "─" * 52)
        self._log(
            f"Hoàn thành {total_days} ngày: "
            f"{self.stats['event']} sự kiện, "
            f"{self.stats['saved']} ảnh lưu, "
            f"{self.stats['error']} lỗi."
        )
        self._push()
        self.log_q.put("__DONE__")

    def _collect_day(self, api: LotteApiClient, d_from: str, d_to: str,
                     out: Path, size: int, sleep_s: float):
        page, empty_n = 1, 0
        while not self._stop.is_set():
            self._log(f"  [PAGE {page}] Đang gọi API...")
            t0 = time.time()
            ok, data = api.search(d_from, d_to, page, size)
            elapsed = time.time() - t0
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
            for rec in recs:
                if self._stop.is_set():
                    return
                self._process(api, rec, out)
            self._push()
            page += 1
            if sleep_s > 0:
                time.sleep(sleep_s)

    def _process(self, api: LotteApiClient, rec: dict, out: Path):
        event_id = str(rec.get("Id") or "")[:8]
        lane_in  = _li_safe(rec.get("InLaneName")  or "unknown_lane")
        lane_out = _li_safe(rec.get("OutLaneName") or lane_in)
        plate    = _li_safe(re.sub(r"[^0-9A-Za-z]", "",
                                   str(rec.get("PlateIn") or rec.get("PlateOut") or "")))
        dt_in    = _li_parse_dt(rec.get("DatetimeIn"))  or datetime.now()
        dt_out   = _li_parse_dt(rec.get("DateTimeOut")) or dt_in
        year, day_s = dt_in.strftime("%Y"), dt_in.strftime("%Y-%m-%d")
        ts_in,  ts_out = dt_in.strftime("%H%M%S"), dt_out.strftime("%H%M%S")
        imgs_in  = rec.get("ImagesIn")  or []
        imgs_out = rec.get("ImagesOut") or []
        self._log(f"  [{event_id}] {plate or '?':12s} | {lane_in} | {day_s} "
                  f"| {len(imgs_in)+len(imgs_out)} ảnh")
        for idx, img_obj in enumerate(imgs_in, 1):
            if self._stop.is_set():
                return
            desc = img_obj.get("Description", "") if isinstance(img_obj, dict) else ""
            self._log(f"    IN  [{idx}/{len(imgs_in)}] {desc}")
            self._save_image(api, img_obj, lane_in, year, day_s, ts_in, plate, out)
        for idx, img_obj in enumerate(imgs_out, 1):
            if self._stop.is_set():
                return
            desc = img_obj.get("Description", "") if isinstance(img_obj, dict) else ""
            self._log(f"    OUT [{idx}/{len(imgs_out)}] {desc}")
            self._save_image(api, img_obj, lane_out, year, day_s, ts_out, plate, out)

    def _save_image(self, api: LotteApiClient, img_obj, lane: str,
                    year: str, day_s: str, ts: str, plate: str, out: Path):
        if not isinstance(img_obj, dict):
            return
        file_path   = img_obj.get("FilePath")   or ""
        description = img_obj.get("Description") or ""
        if not file_path:
            return
        self.stats["found"] += 1
        img = api.fetch_image(file_path)
        if img is None:
            self.stats["error"] += 1
            self._log(f"      ✗ Lỗi tải: {file_path}")
            return
        img_type = _li_categorize(description)
        save_dir = out / lane / year / day_s / img_type
        save_dir.mkdir(parents=True, exist_ok=True)
        base_name = f"{ts}_{plate}" if plate else ts
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
            self.stats["saved"] += 1
            self._log(f"      ✓ {img_type}/{fpath.name}")
        else:
            self.stats["error"] += 1
            self._log(f"      ✗ Lỗi encode: {file_path}")


# ── core: label normalisation ─────────────────────────────────────────────────

def _box_area(box):
    return box[3] * box[4]


def _iou_norm(b1, b2):
    x1a = b1[1] - b1[3] / 2; y1a = b1[2] - b1[4] / 2
    x2a = b1[1] + b1[3] / 2; y2a = b1[2] + b1[4] / 2
    x1b = b2[1] - b2[3] / 2; y1b = b2[2] - b2[4] / 2
    x2b = b2[1] + b2[3] / 2; y2b = b2[2] + b2[4] / 2
    inter = max(0.0, min(x2a, x2b) - max(x1a, x1b)) * max(0.0, min(y2a, y2b) - max(y1a, y1b))
    union = b1[3] * b1[4] + b2[3] * b2[4] - inter
    return inter / union if union > 0 else 0.0


def _apply_label_filters(boxes, cfg):
    if cfg.get("use_class_filter") and cfg.get("keep_classes") is not None:
        keep = set(cfg["keep_classes"])
        boxes = [b for b in boxes if b[0] in keep]
    if not boxes:
        return boxes

    if cfg.get("use_min_area"):
        thr = cfg["min_area_pct"] / 100.0
        boxes = [b for b in boxes if _box_area(b) >= thr]
    if cfg.get("use_max_area"):
        thr = cfg["max_area_pct"] / 100.0
        boxes = [b for b in boxes if _box_area(b) <= thr]
    if cfg.get("use_min_side"):
        px = cfg["min_side_px"]
        iw, ih = cfg.get("iw", 1), cfg.get("ih", 1)
        boxes = [b for b in boxes if b[3] * iw >= px and b[4] * ih >= px]
    if cfg.get("use_aspect"):
        lo, hi = cfg["aspect_min"], cfg["aspect_max"]
        boxes = [b for b in boxes if b[4] > 0 and lo <= (b[3] / b[4]) <= hi]
    if cfg.get("use_edge"):
        m = cfg["edge_margin_pct"] / 100.0
        boxes = [b for b in boxes
                 if not (b[1]-b[3]/2 < m or b[2]-b[4]/2 < m or
                         b[1]+b[3]/2 > 1-m or b[2]+b[4]/2 > 1-m)]

    if not boxes:
        return boxes

    if cfg.get("use_largest"):
        n = max(1, cfg["keep_largest_n"])
        by_cls = {}
        for b in boxes:
            by_cls.setdefault(b[0], []).append(b)
        boxes = []
        for cls_boxes in by_cls.values():
            boxes.extend(sorted(cls_boxes, key=_box_area, reverse=True)[:n])
    elif cfg.get("use_smallest"):
        n = max(1, cfg["keep_smallest_n"])
        by_cls = {}
        for b in boxes:
            by_cls.setdefault(b[0], []).append(b)
        boxes = []
        for cls_boxes in by_cls.values():
            boxes.extend(sorted(cls_boxes, key=_box_area)[:n])

    if cfg.get("use_nms") and len(boxes) > 1:
        thr = cfg["nms_iou"]
        srt = sorted(boxes, key=_box_area, reverse=True)
        kept, skip = [], set()
        for i, b in enumerate(srt):
            if i in skip:
                continue
            kept.append(b)
            for j in range(i + 1, len(srt)):
                if j not in skip and _iou_norm(b, srt[j]) > thr:
                    skip.add(j)
        boxes = kept

    return boxes


def _subfolder_name(boxes, cfg):
    mode = cfg.get("split_mode", "none")
    if mode == "none" or not boxes:
        return ""
    if mode == "size":
        max_a = max(_box_area(b) for b in boxes)
        s = cfg.get("size_s_pct", 3.0) / 100.0
        l = cfg.get("size_l_pct", 15.0) / 100.0
        return "small" if max_a < s else ("large" if max_a >= l else "medium")
    if mode == "class":
        cid = boxes[0][0]
        return cfg.get("class_names_map", {}).get(cid, f"class{cid}")
    if mode == "count":
        return "single" if len(boxes) == 1 else "multi"
    # representative box = largest
    rep = max(boxes, key=_box_area)
    cx, cy, bw, bh = rep[1], rep[2], rep[3], rep[4]
    if mode == "position":
        # gần viền nếu tâm box nằm trong vùng biên
        m = cfg.get("pos_border_pct", 25.0) / 100.0
        near = cx < m or cx > 1 - m or cy < m or cy > 1 - m
        return "border" if near else "center"
    if mode == "region":
        # chia 3×3 theo tâm box
        col = "left" if cx < 1/3 else ("right" if cx > 2/3 else "center")
        row = "top"  if cy < 1/3 else ("bottom" if cy > 2/3 else "middle")
        if row == "middle" and col == "center":
            return "center"
        return f"{row}_{col}" if col != "center" else row
    if mode == "orientation":
        # theo tỉ lệ w/h của box đại diện
        thr = cfg.get("orient_thr", 1.3)
        ratio = bw / bh if bh > 0 else 1.0
        if ratio > thr:
            return "landscape"
        if ratio < 1.0 / thr:
            return "portrait"
        return "square"
    return ""


def run_label_norm(cfg, log, progress, stop_event):
    img_dir   = Path(cfg["image_dir"])
    lbl_dir   = Path(cfg["label_dir"])
    out_dir   = Path(cfg["output_dir"])
    recursive = cfg.get("recursive", False)
    out_dir.mkdir(parents=True, exist_ok=True)
    state_file = out_dir / ".label_norm_state.json"

    state = {"processed": [], "source_dirs": [str(img_dir), str(lbl_dir)]}
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    if state.get("source_dirs") != [str(img_dir), str(lbl_dir)]:
        state = {"processed": [], "source_dirs": [str(img_dir), str(lbl_dir)]}
    processed_set = set(state.get("processed", []))

    if recursive:
        all_imgs = sorted(f for f in img_dir.rglob("*")
                          if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS)
    else:
        all_imgs = sorted(f for f in img_dir.iterdir()
                          if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS)
    total = len(all_imgs)
    if not total:
        log("⚠  Không tìm thấy ảnh trong thư mục."); return

    def _key(fp):
        return str(fp.relative_to(img_dir)) if recursive else fp.name

    prev_done = sum(1 for f in all_imgs if _key(f) in processed_set)
    log(f"📂  Tổng: {total}  |  Đã xử lý trước: {prev_done}  |  Còn lại: {total - prev_done}")
    if recursive:
        log("🔍  Quét đệ quy toàn bộ subfolder")

    saved = skipped = no_label = removed_all = 0
    need_dims = cfg.get("use_min_side", False)

    for i, fp in enumerate(all_imgs, 1):
        if stop_event.is_set():
            log("⚠  Dừng theo yêu cầu."); break
        progress(i, total)
        key = _key(fp)
        if key in processed_set:
            skipped += 1; continue

        rel = fp.relative_to(img_dir)
        lp  = lbl_dir / rel.parent / (fp.stem + ".txt")
        if not lp.exists():
            no_label += 1
            processed_set.add(key)
            continue

        try:
            boxes = _parse_label(str(lp))
        except Exception as e:
            log(f"[LỖI] đọc label {fp.name}: {e}"); continue

        cfg["iw"], cfg["ih"] = 1, 1
        if need_dims:
            try:
                from PIL import Image as _PI
                with _PI.open(fp) as im:
                    cfg["iw"], cfg["ih"] = im.size
            except Exception:
                pass

        filtered = _apply_label_filters(list(boxes), cfg)

        if not filtered:
            removed_all += 1
            processed_set.add(key)
            if len(processed_set) % 50 == 0:
                state["processed"] = list(processed_set)
                state_file.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
            continue

        sub = _subfolder_name(filtered, cfg)
        # Khi recursive: giữ nguyên cấu trúc subfolder nguồn trong output
        if recursive and rel.parent != Path("."):
            dest = (out_dir / sub / rel.parent) if sub else (out_dir / rel.parent)
        else:
            dest = out_dir / sub if sub else out_dir
        dest.mkdir(parents=True, exist_ok=True)

        try:
            shutil.copy2(fp, dest / fp.name)
        except Exception as e:
            log(f"[LỖI] copy ảnh {fp.name}: {e}"); continue

        lines = [f"{b[0]} {b[1]:.6f} {b[2]:.6f} {b[3]:.6f} {b[4]:.6f}" for b in filtered]
        (dest / (fp.stem + ".txt")).write_text("\n".join(lines), encoding="utf-8")

        saved += 1
        processed_set.add(key)
        if len(processed_set) % 50 == 0:
            state["processed"] = list(processed_set)
            state_file.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

    state["processed"] = list(processed_set)
    state_file.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

    log("─" * 58)
    log(f"Tổng ảnh         : {total}")
    log(f"Bỏ qua (đã có)   : {skipped}")
    log(f"Thiếu label      : {no_label}")
    log(f"Bị lọc hết box   : {removed_all}")
    log(f"Đã lưu output    : {saved}")
    log(f"Thư mục output   : {out_dir.resolve()}")


# ── shared UI helpers ──────────────────────────────────────────────────────────

def _style_all():
    s = ttk.Style()
    s.theme_use("clam")
    s.configure("K.Horizontal.TProgressbar",
                troughcolor=CARD, background=ACCENT,
                bordercolor=BG, lightcolor=ACCENT, darkcolor=ACCENT)
    s.configure("Dark.TNotebook",       background=BG, borderwidth=0)
    s.configure("Dark.TNotebook.Tab",   background=CARD, foreground=DIM,
                padding=[18, 8], font=F_BOLD)
    s.map("Dark.TNotebook.Tab",
          background=[("selected", ACCENT2)],
          foreground=[("selected", "white")])
    s.configure("Dark.Treeview",
                background="#16162a", foreground=TEXT,
                fieldbackground="#16162a", rowheight=22, font=F_MONO)
    s.configure("Dark.Treeview.Heading",
                background=ACCENT2, foreground="white",
                relief="flat", font=("Segoe UI Semibold", 9))
    s.map("Dark.Treeview",
          background=[("selected", ACCENT2)],
          foreground=[("selected", "white")])


def _make_logbox(parent):
    frame = Frame(parent, bg=BG)
    log = Text(frame, bg=CARD, fg=TEXT, font=F_MONO, relief="flat",
               bd=0, state=DISABLED, wrap=NONE, height=10, insertbackground=TEXT)
    sb = Scrollbar(frame, command=log.yview)
    log.configure(yscrollcommand=sb.set)
    sb.pack(side=RIGHT, fill=Y)
    log.pack(fill=BOTH, expand=True)
    for tag, color in [("ok", SUCCESS), ("warn", "#f0c040"),
                       ("err", "#f05050"), ("dim", DIM)]:
        log.tag_config(tag, foreground=color)
    return frame, log


def _append_log(widget, msg):
    widget.configure(state=NORMAL)
    tag = ("ok"  if msg.startswith("✔") else
           "warn" if msg.startswith("⚠") else
           "err"  if msg.startswith("[LỖI]") else "dim")
    widget.insert(END, msg + "\n", tag)
    widget.see(END)
    widget.configure(state=DISABLED)


def _folder_row(parent, label_text, var, row, bg=BG):
    Label(parent, text=label_text, bg=bg, fg=DIM,
          font=F_MAIN, width=26, anchor=W).grid(row=row, column=0, sticky=W, pady=5)
    Entry(parent, textvariable=var, bg=CARD, fg=TEXT,
          insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4).grid(
              row=row, column=1, sticky=EW, padx=(8, 8))
    Button(parent, text="Chọn…",
           command=lambda v=var: (
               p := filedialog.askdirectory(initialdir=v.get() or None)) and v.set(p),
           bg=ACCENT2, fg="white", activebackground=ACCENT,
           activeforeground="white", font=F_MAIN,
           relief="flat", padx=10, cursor="hand2").grid(row=row, column=2)
    parent.columnconfigure(1, weight=1)


def _pb_row(parent):
    lbl = Label(parent, text="Sẵn sàng", bg=BG, fg=DIM, font=F_MAIN, anchor=W)
    lbl.pack(fill=X)
    pb = ttk.Progressbar(parent, style="K.Horizontal.TProgressbar",
                         maximum=100, length=400)
    pb.pack(fill=X, pady=(3, 8))
    return lbl, pb


def _set_progress(lbl, pb, done, total, root):
    pct = int(done / total * 100)
    pb["value"] = pct
    lbl.config(text=f"Đang xử lý: {done} / {total}  ({pct}%)")
    root.update_idletasks()


def _action_btn(parent, text, cmd, color, **kw):
    return Button(parent, text=text, command=cmd,
                  bg=color, fg="white", activebackground=color,
                  activeforeground="white", font=F_BOLD,
                  relief="flat", cursor="hand2", **kw)


# ── Tab 2: Split ───────────────────────────────────────────────────────────────

class SplitTab(Frame):
    def __init__(self, master, root):
        super().__init__(master, bg=BG)
        self.root = root
        self._build()

    def _build(self):
        inp = Frame(self, bg=BG, padx=20, pady=14); inp.pack(fill=X)
        self.v_src = StringVar(); self.v_out = StringVar()
        _bind_cfg("split.src", self.v_src); _bind_cfg("split.out", self.v_out)
        _folder_row(inp, "📁  Thư mục nguồn",               self.v_src, 0)
        _folder_row(inp, "💾  Thư mục đầu ra (tuỳ chọn)",   self.v_out, 1)

        opt = Frame(self, bg=BG, padx=20, pady=4); opt.pack(fill=X)
        Label(opt, text="Tối đa ảnh / folder:", bg=BG, fg=DIM,
              font=F_MAIN).grid(row=0, column=0, sticky=W, padx=(0, 8))
        self.v_max = IntVar(value=1000)
        Spinbox(opt, from_=10, to=100000, increment=100, textvariable=self.v_max,
                bg=CARD, fg=TEXT, insertbackground=TEXT, buttonbackground=ACCENT2,
                relief="flat", font=F_MAIN, width=8).grid(row=0, column=1, sticky=W)
        Label(opt, text="   Hành động:", bg=BG, fg=DIM,
              font=F_MAIN).grid(row=0, column=2, sticky=W, padx=(24, 8))
        self.v_move = BooleanVar(value=False)
        for col, (lbl, val) in enumerate([("Sao chép", False), ("Di chuyển", True)]):
            Radiobutton(opt, text=lbl, variable=self.v_move, value=val,
                        bg=BG, fg=TEXT, selectcolor=CARD,
                        activebackground=BG, font=F_MAIN).grid(
                            row=0, column=3+col, padx=(6 if col else 0, 0))

        info = Frame(self, bg=CARD, padx=20, pady=8)
        info.pack(fill=X, padx=20, pady=(6, 4))
        for t in ["Tạo folder: part_01, part_02, … — mỗi folder tối đa N ảnh.",
                  "Để trống 'Thư mục đầu ra' → tự tạo folder <tên>_split bên cạnh thư mục nguồn."]:
            Label(info, text=t, bg=CARD, fg=DIM, font=("Segoe UI", 9)).pack(anchor=W)

        pb_f = Frame(self, bg=BG, padx=20); pb_f.pack(fill=X)
        self.pb_lbl, self.pb = _pb_row(pb_f)

        log_outer = Frame(self, bg=BG, padx=20); log_outer.pack(fill=BOTH, expand=True)
        log_f, self.log = _make_logbox(log_outer)
        log_f.pack(fill=BOTH, expand=True)

        btn_row = Frame(self, bg=BG, padx=20, pady=10); btn_row.pack(fill=X)
        self.btn = _action_btn(btn_row, "▶  Bắt đầu Split", self._run, ACCENT,
                               padx=20, pady=8)
        self.btn.pack(side=LEFT)
        _action_btn(btn_row, "🗂  Mở output", self._open, ACCENT2,
                    padx=14, pady=8).pack(side=LEFT, padx=(10, 0))
        Button(btn_row, text="🧹  Xóa log",
               command=lambda: (self.log.configure(state=NORMAL),
                                self.log.delete("1.0", END),
                                self.log.configure(state=DISABLED)),
               bg=CARD, fg=DIM, font=F_MAIN, relief="flat",
               padx=14, pady=8, cursor="hand2").pack(side=RIGHT)

    def _open(self):
        p = self.v_out.get().strip()
        if not p:
            src = self.v_src.get().strip()
            if src: p = str(Path(src).parent / (Path(src).name + "_split"))
        if p and Path(p).exists(): os.startfile(p)
        else: messagebox.showwarning("Chưa có output", "Chạy xong hoặc nhập thư mục đầu ra.")

    def _run(self):
        src = self.v_src.get().strip()
        if not src:
            messagebox.showwarning("Thiếu thông tin", "Vui lòng chọn thư mục nguồn."); return
        try:
            max_n = int(self.v_max.get())
            if max_n < 1: raise ValueError
        except (ValueError, TypeError):
            messagebox.showwarning("Giá trị không hợp lệ", "Tối đa ảnh / folder phải là số nguyên dương.")
            return

        self.btn.config(state=DISABLED, text="⏳  Đang xử lý…")
        self.pb["value"] = 0; self.pb_lbl.config(text="Đang khởi động…")
        move = self.v_move.get(); out = self.v_out.get().strip()

        def worker():
            try:
                run_split(src, out, max_n, move,
                          log=lambda m: self.root.after(0, _append_log, self.log, m),
                          progress=lambda d, t: self.root.after(
                              0, _set_progress, self.pb_lbl, self.pb, d, t, self.root))
            except Exception as e:
                self.root.after(0, _append_log, self.log, f"[LỖI] {e}")
            finally:
                self.root.after(0, lambda: (
                    self.btn.config(state=NORMAL, text="▶  Bắt đầu Split"),
                    self.pb_lbl.config(text="✅  Hoàn thành!")))

        threading.Thread(target=worker, daemon=True).start()


# ── Tab 3: Dataset Checker ─────────────────────────────────────────────────────

class CheckerTab(Frame):
    def __init__(self, master, root, nb):
        super().__init__(master, bg=BG)
        self.root = root
        self.nb   = nb

        self.data_list    = []
        self.current_idx  = 0
        self.img_dir      = ""
        self.gt_path      = ""
        self.checked_img_dir = ""
        self.checked_gt_path = ""
        self.trash_img_dir   = ""
        self.history      = []
        self.current_img  = None
        self.corrections  = {}
        self.corrections_path = ""

        self.var_audio = BooleanVar(value=True)
        self.var_lang  = StringVar(value="gtts_vi" if _GTTS_OK else "sapi_vi")
        self.var_speed = IntVar(value=15)

        self._tts_q         = queue.Queue(maxsize=1)
        self._prefetch_q    = queue.Queue(maxsize=10)
        self._tts_cache     = {}
        self._prefetch_done = {}

        self._build()
        self._init_tts()
        root.bind("<Delete>", self._global_delete)

    # ── build ──────────────────────────────────────────────────────────────────

    def _build(self):
        from PIL import Image, ImageTk  # imported here so Pillow error is per-tab

        # ── top bar ──
        top = Frame(self, bg=CARD, padx=16, pady=8)
        top.pack(fill=X)
        Button(top, text="📂  Chọn thư mục dataset",
               command=self.load_dataset,
               bg=ACCENT2, fg="white", activebackground=ACCENT,
               activeforeground="white", font=F_BOLD,
               relief="flat", padx=14, pady=6, cursor="hand2").pack(side=LEFT)
        self.lbl_info = Label(top,
            text="Chọn thư mục chứa  raw_images/  và  gt.txt",
            bg=CARD, fg=DIM, font=F_MAIN)
        self.lbl_info.pack(side=LEFT, padx=16)

        # ── images row ──
        img_row = Frame(self, bg=BG, pady=6)
        img_row.pack(fill=X, padx=12)

        # left image
        left_col = Frame(img_row, bg=BG)
        left_col.pack(side=LEFT, padx=6)
        Label(left_col, text="Ảnh gốc (Raw)", bg=BG, fg=DIM,
              font=F_MAIN).pack(anchor=W)
        self.frame_left = Frame(left_col, width=490, height=260,
                                bg="#111122", relief=SUNKEN, bd=1)
        self.frame_left.pack(); self.frame_left.pack_propagate(False)
        self.lbl_img_left = Label(self.frame_left, bg="#111122")
        self.lbl_img_left.pack(expand=True)

        # right image + label display
        right_col = Frame(img_row, bg=BG)
        right_col.pack(side=LEFT, padx=6)
        Label(right_col, text="Preview", bg=BG, fg=DIM,
              font=F_MAIN).pack(anchor=W)
        self.frame_right = Frame(right_col, width=490, height=185,
                                 bg="#111122", relief=SUNKEN, bd=1)
        self.frame_right.pack(); self.frame_right.pack_propagate(False)
        self.lbl_img_right = Label(self.frame_right, bg="#111122")
        self.lbl_img_right.pack(expand=True)

        self.lbl_result = Label(right_col, text="", font=("Courier New", 34, "bold"),
                                bg="#1C1C2E", fg="#FFE000",
                                width=18, height=2, relief=SUNKEN, bd=2, anchor="center")
        self.lbl_result.pack(fill=X, pady=(4, 0))

        # ── label input ──
        entry_row = Frame(self, bg=BG, padx=14, pady=6)
        entry_row.pack(fill=X)
        Label(entry_row, text="Nhãn (Ground Truth):", bg=BG, fg=TEXT,
              font=("Segoe UI Semibold", 12)).pack(side=LEFT)
        self.entry_label = Entry(entry_row, font=("Courier New", 16), width=32,
                                 bg=CARD, fg="#FFE000", insertbackground="#FFE000",
                                 relief="flat", bd=4)
        self.entry_label.pack(side=LEFT, padx=10)
        self.entry_label.bind("<Return>",    self.save_current)
        self.entry_label.bind("<KeyRelease>", self._update_preview)
        self.entry_label.bind("<Right>",     self._on_right)
        self.entry_label.bind("<Left>",      self._on_left)

        self.lbl_correction = Label(self, text="", bg=BG, fg="#E07820",
                                    font=("Segoe UI", 10, "italic"), anchor=W)
        self.lbl_correction.pack(fill=X, padx=16)

        # ── action buttons ──
        btn_row = Frame(self, bg=BG, padx=14, pady=8)
        btn_row.pack(fill=X)

        self.btn_back = Button(btn_row, text="◀  Quay lại  (←)",
                               bg="#E07820", fg="white",
                               activebackground="#c06010", activeforeground="white",
                               font=F_BOLD, width=18, relief="flat",
                               cursor="hand2", command=self.go_back, state=DISABLED)
        self.btn_back.pack(side=LEFT, padx=(0, 8))

        Button(btn_row, text="✅  Lưu & Tiếp  (Enter / →)",
               bg="#2e7d32", fg="white",
               activebackground="#1b5e20", activeforeground="white",
               font=F_BOLD, width=24, relief="flat",
               cursor="hand2", command=self.save_current).pack(side=LEFT, padx=8)

        Button(btn_row, text="🗑  Xóa ảnh  (Del)",
               bg="#c62828", fg="white",
               activebackground="#8b0000", activeforeground="white",
               font=F_BOLD, width=18, relief="flat",
               cursor="hand2", command=self.delete_current).pack(side=LEFT, padx=8)

        Button(btn_row, text="🔤  Sắp xếp GT",
               bg=ACCENT2, fg="white",
               activebackground=ACCENT, activeforeground="white",
               font=F_BOLD, relief="flat",
               cursor="hand2", command=self._sort_gt).pack(side=LEFT, padx=8)

        # ── audio controls ──
        audio_row = Frame(self, bg=BG, padx=14, pady=4)
        audio_row.pack(fill=X)
        Checkbutton(audio_row, text="🔊 Phát âm", variable=self.var_audio,
                    bg=BG, fg=TEXT, selectcolor=CARD,
                    activebackground=BG, font=F_MAIN).pack(side=LEFT, padx=(0, 12))

        gtts_state = NORMAL if _GTTS_OK else DISABLED
        for lbl, val, state in [("Tiếng Việt · Google TTS", "gtts_vi", gtts_state),
                                 ("Tiếng Việt · Phonetic",  "sapi_vi", NORMAL),
                                 ("English",                 "sapi_en", NORMAL)]:
            Radiobutton(audio_row, text=lbl, variable=self.var_lang, value=val,
                        bg=BG, fg=TEXT, selectcolor=CARD,
                        activebackground=BG, font=F_MAIN,
                        state=state).pack(side=LEFT, padx=(0, 6))

        Label(audio_row, text="  Tốc độ:", bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT)
        Spinbox(audio_row, from_=1, to=20, textvariable=self.var_speed,
                width=3, bg=CARD, fg=TEXT, insertbackground=TEXT,
                buttonbackground=ACCENT2, relief="flat",
                font=F_MAIN).pack(side=LEFT, padx=(2, 4))
        Label(audio_row, text="(1–20)", bg=BG, fg=DIM,
              font=("Segoe UI", 9)).pack(side=LEFT)

        if not _TTS_OK:
            Label(audio_row, text="  ⚠ pip install pywin32",
                  bg=BG, fg="#f05050", font=("Segoe UI", 9)).pack(side=LEFT)
        elif not _GTTS_OK:
            Label(audio_row, text="  ⚠ pip install gtts",
                  bg=BG, fg="#f0c040", font=("Segoe UI", 9)).pack(side=LEFT)

        self._build_stats_panel()

    # ── load ───────────────────────────────────────────────────────────────────

    def load_dataset(self):
        folder = filedialog.askdirectory(
            title="Chọn thư mục train hoặc val",
            initialdir=_cfg_dir("checker.folder"))
        if not folder:
            return
        _CFG["checker.folder"] = folder; _cfg_save()
        self.img_dir = os.path.join(folder, "raw_images")
        self.gt_path = os.path.join(folder, "gt.txt")
        if not os.path.exists(self.img_dir) or not os.path.exists(self.gt_path):
            messagebox.showerror("Lỗi",
                "Thư mục không chứa 'raw_images' hoặc 'gt.txt'.\n"
                "Hãy chọn đúng thư mục train / val.")
            return

        parent_dir  = os.path.dirname(folder)
        checked     = os.path.join(parent_dir, os.path.basename(folder) + "_checked")
        self.checked_img_dir = os.path.join(checked, "raw_images")
        self.checked_gt_path = os.path.join(checked, "gt.txt")
        self.trash_img_dir   = os.path.join(checked, "deleted_images")
        os.makedirs(self.checked_img_dir, exist_ok=True)
        os.makedirs(self.trash_img_dir,   exist_ok=True)

        self.data_list = []
        with open(self.gt_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line: continue
                parts = line.split("\t") if "\t" in line else line.split(" ", 1)
                self.data_list.append(
                    (parts[0], parts[1] if len(parts) >= 2 else ""))

        self.current_idx = 0
        self.history     = []
        if not self.data_list:
            messagebox.showinfo("Thông báo", "File gt.txt trống hoặc đã duyệt xong!")
            return

        self._load_corrections()
        for i in range(min(6, len(self.data_list))):
            self._prefetch_gtts(self.data_list[i][1])
        self.show_current()
        self.root.after(80, self._refresh_stats)

    # ── display ────────────────────────────────────────────────────────────────

    def show_current(self):
        if self.current_idx >= len(self.data_list):
            self.lbl_info.config(text="✅  Hoàn thành! Đã kiểm tra toàn bộ dữ liệu.")
            for w in (self.lbl_img_left, self.lbl_img_right):
                w.config(image="")
            self.lbl_result.config(text="")
            self.entry_label.delete(0, END)
            messagebox.showinfo("Thành công", "Đã xử lý xong toàn bộ ảnh!")
            return

        from PIL import Image, ImageTk

        filename, gt_label = self.data_list[self.current_idx]
        total = len(self.data_list)
        self.lbl_info.config(
            text=f"Tiến độ: {self.current_idx + 1} / {total}   |   {filename}")

        display = self.corrections.get(gt_label, gt_label)
        self.entry_label.delete(0, END)
        self.entry_label.insert(0, display)
        self.lbl_correction.config(
            text=f"Tự sửa: [{gt_label}] → [{display}]" if display != gt_label else "")
        self.btn_back.config(state=NORMAL if self.history else DISABLED)

        img_path = os.path.join(self.img_dir, filename)
        self.current_img = None
        if os.path.exists(img_path):
            try:
                img = Image.open(img_path).convert("RGB")
                self.current_img = img

                img_l = img.copy(); img_l.thumbnail((480, 250))
                self.photo_left = ImageTk.PhotoImage(img_l)
                self.lbl_img_left.config(image=self.photo_left)

                img_r = img.copy(); img_r.thumbnail((480, 180))
                self.photo_right = ImageTk.PhotoImage(img_r)
                self.lbl_img_right.config(image=self.photo_right)

                self.lbl_result.config(text=display or "—")

                for off in range(min(5, total - self.current_idx)):
                    self._prefetch_gtts(self.data_list[self.current_idx + off][1])
                self._speak(display)
            except Exception as e:
                for w in (self.lbl_img_left, self.lbl_img_right):
                    w.config(image="")
                self.lbl_result.config(text="")
                print(f"Lỗi đọc ảnh {filename}: {e}")
        else:
            for w in (self.lbl_img_left, self.lbl_img_right):
                w.config(image="")
            self.lbl_result.config(text="")

        self.entry_label.focus_set()

    def _update_preview(self, _=None):
        lbl = self.entry_label.get()
        self.lbl_result.config(text=lbl or "—")

    # ── navigation ─────────────────────────────────────────────────────────────

    def _process_and_next(self, action, new_label=""):
        if self.current_idx >= len(self.data_list):
            return
        filename, old_label = self.data_list[self.current_idx]
        src   = os.path.join(self.img_dir,         filename)
        dst   = os.path.join(self.checked_img_dir, filename)
        trash = os.path.join(self.trash_img_dir,   filename)

        if action == "save":
            if os.path.exists(src): shutil.move(src, dst)
            with open(self.checked_gt_path, "a", encoding="utf-8") as f:
                f.write(f"{filename}\t{new_label}\n")
            self.history.append(("save", filename, new_label))
        elif action == "delete":
            if os.path.exists(src): shutil.move(src, trash)
            self.history.append(("delete", filename, old_label))

        self.current_idx += 1
        with open(self.gt_path, "w", encoding="utf-8") as f:
            for fn, lbl in self.data_list[self.current_idx:]:
                f.write(f"{fn}\t{lbl}\n")
        self.show_current()
        self.root.after(80, self._refresh_stats)

    def go_back(self):
        if not self.history: return
        action, filename, _ = self.history.pop()
        self.current_idx -= 1

        if action == "save":
            src = os.path.join(self.checked_img_dir, filename)
            dst = os.path.join(self.img_dir, filename)
            if os.path.exists(src): shutil.move(src, dst)
            if os.path.exists(self.checked_gt_path):
                with open(self.checked_gt_path, encoding="utf-8") as f:
                    lines = f.readlines()
                with open(self.checked_gt_path, "w", encoding="utf-8") as f:
                    f.writelines(lines[:-1])
        elif action == "delete":
            src = os.path.join(self.trash_img_dir, filename)
            dst = os.path.join(self.img_dir, filename)
            if os.path.exists(src): shutil.move(src, dst)

        with open(self.gt_path, "w", encoding="utf-8") as f:
            for fn, lbl in self.data_list[self.current_idx:]:
                f.write(f"{fn}\t{lbl}\n")
        self.show_current()
        self.root.after(80, self._refresh_stats)

    def _on_right(self, _):
        if self.entry_label.index(INSERT) == len(self.entry_label.get()):
            self.save_current(); return "break"

    def _on_left(self, _):
        if self.entry_label.index(INSERT) == 0:
            self.go_back(); return "break"

    def _global_delete(self, event=None):
        try:
            if self.nb.select() == str(self):
                self.delete_current()
        except Exception:
            pass

    # ── actions ────────────────────────────────────────────────────────────────

    def save_current(self, _=None):
        new_label = self.entry_label.get().strip()
        if not new_label:
            if not messagebox.askyesno("Cảnh báo", "Nhãn đang trống. Vẫn lưu?"): return
        _, gt_label = self.data_list[self.current_idx]
        if gt_label and new_label != gt_label:
            self._save_correction(gt_label, new_label)
        self._process_and_next("save", new_label)

    def delete_current(self, _=None):
        if not self.data_list or self.current_idx >= len(self.data_list):
            return
        if messagebox.askyesno("Xác nhận xóa", "Xóa ảnh này khỏi dataset?"):
            self._process_and_next("delete")

    def _sort_gt(self):
        if not self.data_list:
            messagebox.showinfo("Thông báo", "Chưa tải dataset."); return
        self.data_list.sort(key=lambda x: x[1])
        with open(self.gt_path, "w", encoding="utf-8") as f:
            for fn, lbl in self.data_list:
                f.write(f"{fn}\t{lbl}\n")
        self.current_idx = 0
        self.history = []
        self.show_current()
        self.root.after(80, self._refresh_stats)
        self.lbl_info.config(
            text=f"Đã sắp xếp {len(self.data_list):,} dòng theo biển số xe.")

    # ── corrections ────────────────────────────────────────────────────────────

    def _load_corrections(self):
        path = os.path.join(os.path.dirname(self.gt_path), "corrections.json")
        self.corrections_path = path
        try:
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    self.corrections = json.load(f)
        except Exception:
            self.corrections = {}

    def _save_correction(self, wrong, correct):
        self.corrections[wrong] = correct
        if self.corrections_path:
            try:
                with open(self.corrections_path, "w", encoding="utf-8") as f:
                    json.dump(self.corrections, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"corrections save: {e}")

    # ── TTS ────────────────────────────────────────────────────────────────────

    def _init_tts(self):
        if not _TTS_OK: return
        threading.Thread(target=self._tts_loop, daemon=True).start()
        if _GTTS_OK:
            threading.Thread(target=self._gtts_prefetch_loop, daemon=True).start()

    def _tts_loop(self):
        import ctypes, time as _t
        mci = ctypes.windll.winmm.mciSendStringW
        pythoncom.CoInitialize()
        spk = win32com.client.Dispatch("SAPI.SpVoice")
        spk.Volume = 100
        try:
            while True:
                text = self._tts_q.get()
                if text is None: break
                lang  = self.var_lang.get()
                speed = max(1, min(20, int(self.var_speed.get())))
                if lang == "gtts_vi" and _GTTS_OK:
                    self._gtts_speak(text, speed, mci)
                else:
                    spk.Rate = min(10, speed)
                    spk.Speak(text, 3)
                    while spk.Status.RunningState != 1:
                        _t.sleep(0.02)
                        try:
                            newer = self._tts_q.get_nowait()
                            if newer is None:
                                spk.Speak("", 3); return
                            text  = newer
                            speed = max(1, min(20, int(self.var_speed.get())))
                            spk.Rate = min(10, speed)
                            spk.Speak(text, 3)
                        except queue.Empty:
                            pass
        except Exception as e:
            print(f"TTS: {e}")
        finally:
            pythoncom.CoUninitialize()

    def _gtts_speak(self, text, speed, mci):
        cache_key = (text,)
        try:
            ev = self._prefetch_done.get(cache_key)
            if ev: ev.wait(timeout=12)
            fname = self._tts_cache.get(cache_key)
            if not fname or not os.path.exists(fname):
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                    fname = f.name
                _gTTS(text=text, lang="vi", slow=False).save(fname)
                self._tts_cache[cache_key] = fname
                self._trim_cache()
            alias = "_tts_g"
            mci_spd = min(3000, 500 + speed * 125)
            mci(f'open "{fname}" type mpegvideo alias {alias}', None, 0, None)
            mci(f'set {alias} speed {mci_spd}',                None, 0, None)
            mci(f'play {alias} wait',                          None, 0, None)
            mci(f'close {alias}',                              None, 0, None)
        except Exception as e:
            print(f"gTTS speak: {e}")

    def _gtts_prefetch_loop(self):
        while True:
            cache_key = self._prefetch_q.get()
            if cache_key is None: break
            ev = self._prefetch_done.setdefault(cache_key, threading.Event())
            try:
                if cache_key in self._tts_cache and os.path.exists(
                        self._tts_cache.get(cache_key, "")): continue
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                    fname = f.name
                _gTTS(text=cache_key[0], lang="vi", slow=False).save(fname)
                if os.path.getsize(fname) > 0:
                    self._tts_cache[cache_key] = fname
                    self._trim_cache()
                else:
                    try: os.unlink(fname)
                    except OSError: pass
            except Exception as e:
                print(f"prefetch: {e}")
            finally:
                ev.set()

    def _trim_cache(self, max_entries=30):
        while len(self._tts_cache) > max_entries:
            key, fpath = next(iter(self._tts_cache.items()))
            self._tts_cache.pop(key, None)
            self._prefetch_done.pop(key, None)
            try: os.unlink(fpath)
            except OSError: pass

    def _prefetch_gtts(self, raw_label):
        if not raw_label or not _GTTS_OK: return
        spoken    = " ".join(_VI_FULL.get(c, c)
                             for c in raw_label.upper().replace("-","").replace(" ",""))
        cache_key = (spoken,)
        if cache_key not in self._tts_cache:
            self._prefetch_done.setdefault(cache_key, threading.Event())
            try: self._prefetch_q.put_nowait(cache_key)
            except queue.Full: pass

    def _speak(self, text):
        if not _TTS_OK or not self.var_audio.get() or not text: return
        clean = text.upper().replace("-","").replace(" ","")
        lang  = self.var_lang.get()
        spoken = (" ".join(_VI_FULL.get(c,c) for c in clean) if lang == "gtts_vi" else
                  " ".join(_VI.get(c,c)      for c in clean) if lang == "sapi_vi" else
                  " ".join(list(clean)))
        try: self._tts_q.get_nowait()
        except queue.Empty: pass
        self._tts_q.put(spoken)

    # ── gt status panel ────────────────────────────────────────────────────────

    _MINI_COLS = 12
    _MINI_W    = 44
    _MINI_H    = 30

    def _build_stats_panel(self):
        self._gt_prog_pct = 0.0

        Frame(self, height=1, bg="#333355").pack(fill=X)

        hdr = Frame(self, bg=CARD, padx=14, pady=5)
        hdr.pack(fill=X)
        Label(hdr, text="GT STATUS", bg=CARD, fg=DIM,
              font=("Segoe UI Semibold", 9)).pack(side=LEFT)
        self.lbl_gt_prog = Label(hdr, text="—  chưa tải dataset",
                                  bg=CARD, fg=TEXT, font=F_MAIN)
        self.lbl_gt_prog.pack(side=LEFT, padx=12)
        Button(hdr, text="⟳", command=self._refresh_stats,
               bg=CARD, fg=DIM, font=("Segoe UI", 10),
               relief="flat", padx=6, cursor="hand2").pack(side=RIGHT)

        prog_frame = Frame(self, bg=BG, padx=14, pady=2)
        prog_frame.pack(fill=X)
        self._cv_mini_prog = Canvas(prog_frame, height=14, bg="#16162a",
                                    highlightthickness=0)
        self._cv_mini_prog.pack(fill=X)
        self._cv_mini_prog.bind("<Configure>", lambda e: self._redraw_mini_prog())

        hm_outer = Frame(self, bg=BG, padx=14, pady=4)
        hm_outer.pack(anchor=W)
        CHARS_REMAP = (list("0123456789AB") +
                       list("CDEFGHIJKLMN") +
                       list("OPQRSTUVWXYZ"))
        self._mini_cells = {}
        for i, ch in enumerate(CHARS_REMAP):
            r, c = divmod(i, self._MINI_COLS)
            cell = Frame(hm_outer, width=self._MINI_W, height=self._MINI_H,
                         bg="#252540", relief="flat", bd=0)
            cell.grid(row=r, column=c, padx=1, pady=1)
            cell.pack_propagate(False)
            lbl_ch = Label(cell, text=ch, bg="#252540", fg="#555570",
                           font=("Consolas", 10, "bold"))
            lbl_ch.pack(expand=True, pady=(2, 0))
            lbl_cnt = Label(cell, text="", bg="#252540", fg="#333350",
                            font=("Consolas", 6))
            lbl_cnt.pack()
            self._mini_cells[ch] = (cell, lbl_ch, lbl_cnt)

    def _redraw_mini_prog(self):
        cv = self._cv_mini_prog
        w  = cv.winfo_width()
        h  = cv.winfo_height()
        if w < 2:
            return
        cv.delete("all")
        fill_w = int(w * self._gt_prog_pct)
        if fill_w > 0:
            cv.create_rectangle(0, 0, fill_w, h, fill=ACCENT, outline="")
        cv.create_text(w // 2, h // 2,
                       text=f"{self._gt_prog_pct * 100:.1f}%",
                       fill="white", font=("Segoe UI Semibold", 7))

    def _refresh_stats(self):
        if not self.gt_path:
            return
        from collections import Counter
        n_rem = n_chk = 0
        rem_chars: dict = {}
        chk_chars: dict = {}

        if os.path.exists(self.gt_path):
            _, rem_chars, rem_lens = analyze_gt(self.gt_path)
            n_rem = sum(rem_lens.values()) if rem_lens else 0

        if self.checked_gt_path and os.path.exists(self.checked_gt_path):
            _, chk_chars, chk_lens = analyze_gt(self.checked_gt_path)
            n_chk = sum(chk_lens.values()) if chk_lens else 0

        n_total = n_rem + n_chk
        pct     = (n_chk / n_total) if n_total else 0.0
        self._gt_prog_pct = pct
        self.lbl_gt_prog.config(
            text=(f"Đã kiểm tra: {n_chk:,} / {n_total:,}  "
                  f"({pct * 100:.1f}%)   Còn lại: {n_rem:,}"))
        self._redraw_mini_prog()

        all_chars = Counter(rem_chars)
        all_chars.update(Counter(chk_chars))
        max_cnt = max(all_chars.values(), default=1)
        for ch, (cell, lbl_ch, lbl_cnt) in self._mini_cells.items():
            cnt = all_chars.get(ch, 0)
            bg  = _heat_color(cnt, max_cnt)
            fg  = "white"   if cnt else "#555570"
            fgn = "#cccccc" if cnt else "#333350"
            cell.config(bg=bg)
            lbl_ch.config(bg=bg, fg=fg)
            lbl_cnt.config(bg=bg, fg=fgn, text=f"{cnt:,}" if cnt else "")


# ── Tab 4: GT Stats ────────────────────────────────────────────────────────────

HEATMAP_CHARS = list("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ")
HMAP_COLS     = 10          # 4 rows: [0-9] [A-J] [K-T] [U-Z__]
CELL_W        = 68
CELL_H        = 54


class StatsTab(Frame):
    def __init__(self, master, root):
        super().__init__(master, bg=BG)
        self.root    = root
        self._folder = ""
        self._cells  = {}   # char → (Frame, char_lbl, cnt_lbl)
        self._build()

    # ── layout ─────────────────────────────────────────────────────────────────

    def _build(self):
        # top bar
        top = Frame(self, bg=CARD, padx=16, pady=8)
        top.pack(fill=X)
        Button(top, text="📂  Chọn folder dataset", command=self._load,
               bg=ACCENT2, fg="white", activebackground=ACCENT,
               activeforeground="white", font=F_BOLD,
               relief="flat", padx=14, pady=6, cursor="hand2").pack(side=LEFT)
        Button(top, text="🔄  Làm mới", command=self._refresh,
               bg=CARD, fg=TEXT, activebackground=ACCENT2,
               activeforeground="white", font=F_MAIN,
               relief="flat", padx=12, pady=6, cursor="hand2").pack(side=RIGHT)
        self.lbl_path = Label(top, text="Chưa chọn folder",
                              bg=CARD, fg=DIM, font=F_MAIN)
        self.lbl_path.pack(side=LEFT, padx=14)

        # ── progress section ──
        prog_outer = Frame(self, bg=BG, padx=16, pady=6)
        prog_outer.pack(fill=X)

        prog_card = Frame(prog_outer, bg=CARD, padx=16, pady=10)
        prog_card.pack(fill=X)

        Label(prog_card, text="TIẾN ĐỘ KIỂM TRA", bg=CARD, fg=DIM,
              font=("Segoe UI Semibold", 9)).pack(anchor=W)

        self.lbl_prog_nums = Label(prog_card, text="—", bg=CARD, fg=TEXT,
                                   font=("Segoe UI Semibold", 12))
        self.lbl_prog_nums.pack(anchor=W, pady=(4, 2))

        # custom canvas progress bar
        self.cv_prog = Canvas(prog_card, height=18, bg="#16162a",
                              highlightthickness=0)
        self.cv_prog.pack(fill=X, pady=(0, 4))
        self.cv_prog.bind("<Configure>", self._redraw_prog)
        self._prog_pct = 0.0

        self.lbl_prog_detail = Label(prog_card, text="", bg=CARD, fg=DIM,
                                     font=("Segoe UI", 9))
        self.lbl_prog_detail.pack(anchor=W)

        # ── heatmap section ──
        hm_outer = Frame(self, bg=BG, padx=16, pady=4)
        hm_outer.pack(fill=X)

        hm_card = Frame(hm_outer, bg=CARD, padx=14, pady=10)
        hm_card.pack(fill=X)

        Label(hm_card, text="PHÂN BỐ KÝ TỰ  (màu đậm = xuất hiện nhiều hơn)",
              bg=CARD, fg=DIM, font=("Segoe UI Semibold", 9)).pack(anchor=W, pady=(0, 8))

        grid_frame = Frame(hm_card, bg=CARD)
        grid_frame.pack(anchor=W)

        self._cells = {}
        for i, ch in enumerate(HEATMAP_CHARS):
            row, col = divmod(i, HMAP_COLS)
            cell = Frame(grid_frame, width=CELL_W, height=CELL_H,
                         bg="#252540", relief="flat", bd=0)
            cell.grid(row=row, column=col, padx=2, pady=2)
            cell.pack_propagate(False)
            lbl_ch  = Label(cell, text=ch,  bg="#252540", fg="white",
                            font=("Consolas", 15, "bold"))
            lbl_cnt = Label(cell, text="—", bg="#252540", fg="#888899",
                            font=("Consolas", 8))
            lbl_ch.pack(expand=True)
            lbl_cnt.pack()
            self._cells[ch] = (cell, lbl_ch, lbl_cnt)

        # legend
        leg_frame = Frame(hm_card, bg=CARD, pady=4)
        leg_frame.pack(anchor=W)
        Label(leg_frame, text="Ít  ", bg=CARD, fg=DIM,
              font=("Segoe UI", 8)).pack(side=LEFT)
        for lvl in [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]:
            c = _heat_color(lvl, 1.0) if lvl > 0 else "#252540"
            Frame(leg_frame, width=18, height=12, bg=c).pack(side=LEFT, padx=1)
        Label(leg_frame, text="  Nhiều", bg=CARD, fg=DIM,
              font=("Segoe UI", 8)).pack(side=LEFT)

        # ── detail table + length dist (side by side) ──
        bottom = Frame(self, bg=BG, padx=16, pady=6)
        bottom.pack(fill=BOTH, expand=True)
        bottom.columnconfigure(0, weight=3)
        bottom.columnconfigure(1, weight=2)

        # left: frequency table
        freq_card = Frame(bottom, bg=CARD, padx=12, pady=8)
        freq_card.grid(row=0, column=0, sticky=NSEW, padx=(0, 6))
        Label(freq_card, text="CHI TIẾT TẦN SUẤT KÝ TỰ",
              bg=CARD, fg=DIM, font=("Segoe UI Semibold", 9)).pack(anchor=W, pady=(0, 4))
        self.txt_freq = Text(freq_card, bg="#16162a", fg=TEXT, font=("Consolas", 9),
                             relief="flat", bd=0, state=DISABLED, height=9,
                             wrap=NONE)
        sb_freq = Scrollbar(freq_card, command=self.txt_freq.yview)
        self.txt_freq.configure(yscrollcommand=sb_freq.set)
        sb_freq.pack(side=RIGHT, fill=Y)
        self.txt_freq.pack(fill=BOTH, expand=True)
        self.txt_freq.tag_config("hdr",  foreground=DIM)
        self.txt_freq.tag_config("bar",  foreground=ACCENT)
        self.txt_freq.tag_config("hi",   foreground="#FFE000")

        # right: label length distribution
        len_card = Frame(bottom, bg=CARD, padx=12, pady=8)
        len_card.grid(row=0, column=1, sticky=NSEW)
        Label(len_card, text="ĐỘ DÀI NHÃN",
              bg=CARD, fg=DIM, font=("Segoe UI Semibold", 9)).pack(anchor=W, pady=(0, 4))
        self.txt_len = Text(len_card, bg="#16162a", fg=TEXT, font=("Consolas", 9),
                            relief="flat", bd=0, state=DISABLED, height=9,
                            wrap=NONE)
        self.txt_len.pack(fill=BOTH, expand=True)
        self.txt_len.tag_config("bar",  foreground=ACCENT)
        self.txt_len.tag_config("hdr",  foreground=DIM)

    # ── data load / refresh ────────────────────────────────────────────────────

    def _load(self):
        folder = filedialog.askdirectory(
            title="Chọn folder chứa gt.txt",
            initialdir=_cfg_dir("stats.folder"))
        if folder:
            _CFG["stats.folder"] = folder; _cfg_save()
            self._folder = folder
            self.lbl_path.config(text=folder)
            self._refresh()

    def _refresh(self):
        if not self._folder:
            messagebox.showwarning("Chưa chọn folder", "Vui lòng chọn folder trước."); return

        gt_remaining = os.path.join(self._folder, "gt.txt")
        if not os.path.exists(gt_remaining):
            messagebox.showerror("Không tìm thấy", f"Không có gt.txt trong:\n{self._folder}"); return

        # detect checked folder (same parent, name + "_checked")
        parent       = os.path.dirname(self._folder)
        checked_dir  = os.path.join(parent, os.path.basename(self._folder) + "_checked")
        gt_checked   = os.path.join(checked_dir, "gt.txt")

        _, rem_chars, rem_lens = analyze_gt(gt_remaining)
        n_remaining = sum(rem_lens.values()) if rem_lens else 0

        n_checked = 0
        chk_chars = {}
        chk_lens  = {}
        if os.path.exists(gt_checked):
            _, chk_chars, chk_lens = analyze_gt(gt_checked)
            n_checked = sum(chk_lens.values()) if chk_lens else 0

        n_total = n_remaining + n_checked
        pct     = (n_checked / n_total * 100) if n_total else 0.0

        # merge chars (remaining + checked = full picture)
        from collections import Counter
        all_chars = Counter(rem_chars) + Counter(chk_chars)

        self._update_progress(n_checked, n_remaining, n_total, pct, gt_checked)
        self._update_heatmap(all_chars)
        self._update_freq_table(all_chars)
        self._update_length_chart(rem_lens, chk_lens)

    # ── update helpers ─────────────────────────────────────────────────────────

    def _update_progress(self, done, remaining, total, pct, checked_path):
        self._prog_pct = pct / 100
        if total == 0:
            self.lbl_prog_nums.config(text="Chưa có dữ liệu")
            self.lbl_prog_detail.config(text="")
        else:
            self.lbl_prog_nums.config(
                text=f"Đã kiểm tra: {done:,} / {total:,}   ({pct:.1f}%)"
                     f"   —   Còn lại: {remaining:,}")
            detail = f"Output: {checked_path}" if os.path.exists(checked_path) else \
                     "Chưa có folder _checked (chưa duyệt ảnh nào)"
            self.lbl_prog_detail.config(text=detail)
        self._redraw_prog()

    def _redraw_prog(self, _=None):
        w = self.cv_prog.winfo_width()
        h = self.cv_prog.winfo_height()
        if w < 2: return
        self.cv_prog.delete("all")
        fill_w = int(w * self._prog_pct)
        if fill_w > 0:
            self.cv_prog.create_rectangle(0, 0, fill_w, h, fill=ACCENT, outline="")
        # pct text
        pct_str = f"{self._prog_pct*100:.1f}%"
        self.cv_prog.create_text(w // 2, h // 2, text=pct_str,
                                 fill="white", font=("Segoe UI Semibold", 8))

    def _update_heatmap(self, char_counts):
        max_count = max(char_counts.values(), default=1)
        for ch, (cell, lbl_ch, lbl_cnt) in self._cells.items():
            cnt  = char_counts.get(ch, 0)
            bg   = _heat_color(cnt, max_count)
            fg   = "white" if cnt else "#555570"
            fg_n = "#cccccc" if cnt else "#333350"
            cell.config(bg=bg)
            lbl_ch.config(bg=bg, fg=fg)
            lbl_cnt.config(bg=bg, fg=fg_n,
                           text=f"{cnt:,}" if cnt else "—")

    def _update_freq_table(self, char_counts):
        self.txt_freq.configure(state=NORMAL)
        self.txt_freq.delete("1.0", END)

        total_chars = sum(char_counts.values()) or 1
        sorted_chars = sorted(char_counts.items(), key=lambda x: -x[1])

        header = f"{'Ký tự':^6} {'Số lần':>8}  {'%':>6}  Biểu đồ\n"
        sep    = "─" * 54 + "\n"
        self.txt_freq.insert(END, header, "hdr")
        self.txt_freq.insert(END, sep,    "hdr")

        max_cnt = sorted_chars[0][1] if sorted_chars else 1
        BAR_MAX = 22
        for ch, cnt in sorted_chars:
            pct  = cnt / total_chars * 100
            bars = int(cnt / max_cnt * BAR_MAX)
            line = f"  {ch:^4}  {cnt:>8,}  {pct:>5.1f}%  "
            bar  = "█" * bars
            self.txt_freq.insert(END, line, "hi")
            self.txt_freq.insert(END, bar + "\n", "bar")

        if not sorted_chars:
            self.txt_freq.insert(END, "  (không có dữ liệu)\n", "hdr")
        self.txt_freq.configure(state=DISABLED)

    def _update_length_chart(self, rem_lens, chk_lens):
        from collections import Counter
        self.txt_len.configure(state=NORMAL)
        self.txt_len.delete("1.0", END)

        combined = Counter(rem_lens) + Counter(chk_lens)
        if not combined:
            self.txt_len.insert(END, "  (không có dữ liệu)\n", "hdr")
            self.txt_len.configure(state=DISABLED); return

        total = sum(combined.values())
        BAR_MAX = 18
        max_cnt = max(combined.values())
        header = f"{'Dài':>5}  {'Số ảnh':>7}  {'%':>6}  Biểu đồ\n"
        sep    = "─" * 44 + "\n"
        self.txt_len.insert(END, header, "hdr")
        self.txt_len.insert(END, sep,    "hdr")

        for length in sorted(combined):
            cnt  = combined[length]
            pct  = cnt / total * 100
            bars = int(cnt / max_cnt * BAR_MAX)
            r_cnt = rem_lens.get(length, 0)
            c_cnt = chk_lens.get(length, 0)
            line = f"  {length:>3}  {cnt:>8,}  {pct:>5.1f}%  "
            self.txt_len.insert(END, line, "hdr")
            self.txt_len.insert(END, "█" * bars + "\n", "bar")

        self.txt_len.configure(state=DISABLED)


# ── core: rename ──────────────────────────────────────────────────────────────

def build_rename_plan(parent_dir, out_dir, per_folder, padding,
                      start_num, keep_ext, forced_ext, recursive=False):
    """Returns list of (src_Path, dst_Path).
    out_dir=None → in-place rename; otherwise files go to out_dir.
    recursive=True → scan all nested subfolders.
    """
    parent = Path(parent_dir)
    out    = Path(out_dir) if out_dir else None

    if recursive:
        # Group images by directory, preserving depth order
        folder_imgs: dict = {}
        for f in sorted(parent.rglob("*")):
            if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS:
                folder_imgs.setdefault(f.parent, []).append(f)
        subfolders = sorted(folder_imgs.keys())
    else:
        subfolders = sorted(d for d in parent.iterdir() if d.is_dir())
        root_imgs  = sorted(f for f in parent.iterdir()
                            if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS)
        if root_imgs:
            subfolders = [parent] + subfolders
        folder_imgs = {}
        for folder in subfolders:
            src = root_imgs if folder == parent else sorted(
                f for f in folder.iterdir()
                if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS)
            folder_imgs[folder] = src

    plan = []
    if per_folder:
        for folder in subfolders:
            imgs = folder_imgs.get(folder, [])
            if not imgs:
                continue
            if out is not None:
                rel = folder.relative_to(parent) if folder != parent else Path(".")
                dst_folder = out / rel
            else:
                dst_folder = folder
            for idx, img in enumerate(imgs, start_num):
                ext = img.suffix.lower() if keep_ext else forced_ext
                plan.append((img, dst_folder / (str(idx).zfill(padding) + ext)))
    else:
        all_imgs = [img for folder in subfolders
                    for img in folder_imgs.get(folder, [])]
        for idx, img in enumerate(all_imgs, start_num):
            ext = img.suffix.lower() if keep_ext else forced_ext
            dst_folder = out if out is not None else img.parent
            plan.append((img, dst_folder / (str(idx).zfill(padding) + ext)))

    return plan


def execute_rename_plan(plan, action, log, progress):
    """action: 'rename' | 'copy' | 'move'"""
    total = len(plan)
    if not total:
        log("⚠  Không có file nào cần xử lý."); return

    cross_dir = action in ("copy", "move")

    if cross_dir:
        # Create all destination directories upfront
        dst_dirs = {dst.parent for _, dst in plan}
        for d in dst_dirs:
            d.mkdir(parents=True, exist_ok=True)

        done = 0
        lbl_done = 0
        for src, dst in plan:
            if action == "copy":
                shutil.copy2(src, dst)
            else:
                shutil.move(str(src), dst)
            src_lbl = src.with_suffix(".txt")
            if src_lbl.exists():
                dst_lbl = dst.with_suffix(".txt")
                if action == "copy":
                    shutil.copy2(src_lbl, dst_lbl)
                else:
                    shutil.move(str(src_lbl), dst_lbl)
                lbl_done += 1
            done += 1
            progress(done, total)
            if done % 50 == 0 or done == total:
                log(f"✔  {dst.parent.name}  /  {dst.name}")
        log("─" * 52)
        log(f"{'Đã sao chép' if action == 'copy' else 'Đã di chuyển'} : {done} file")
        if lbl_done:
            log(f"Label (.txt)        : {lbl_done} file")
    else:
        # In-place rename: use tmp names to avoid conflicts
        tmp_map = {}
        for i, (src, dst) in enumerate(plan):
            if src.resolve() == dst.resolve():
                continue
            tmp = src.parent / f"__rtmp{i:07d}__"
            src.rename(tmp)
            src_lbl = src.with_suffix(".txt")
            if src_lbl.exists():
                src_lbl.rename(src.parent / f"__rtmp{i:07d}__.txt")
            tmp_map[i] = (tmp, dst)

        done = 0
        lbl_done = 0
        for i in sorted(tmp_map):
            tmp, dst = tmp_map[i]
            tmp.rename(dst)
            tmp_lbl = tmp.parent / f"__rtmp{i:07d}__.txt"
            if tmp_lbl.exists():
                tmp_lbl.rename(dst.with_suffix(".txt"))
                lbl_done += 1
            done += 1
            progress(done, len(tmp_map))
            if done % 50 == 0 or done == len(tmp_map):
                log(f"✔  {dst.parent.name}  /  {dst.name}")

        unchanged = total - len(tmp_map)
        log("─" * 52)
        log(f"Đã đổi tên : {done} file")
        if lbl_done:
            log(f"Label (.txt) : {lbl_done} file")
        if unchanged:
            log(f"Giữ nguyên : {unchanged} file (đã đúng tên)")


# ── Tab 5: Rename ──────────────────────────────────────────────────────────────

class RenameTab(Frame):
    def __init__(self, master, root):
        super().__init__(master, bg=BG)
        self.root  = root
        self._plan = []
        self._build()

    # ── layout ─────────────────────────────────────────────────────────────────

    def _build(self):
        # ── row 1: source folder ──
        row1 = Frame(self, bg=CARD, padx=16, pady=7)
        row1.pack(fill=X)
        self.v_folder = StringVar()
        _bind_cfg("rename.src", self.v_folder)
        Button(row1, text="📂  Folder nguồn", command=self._browse,
               bg=ACCENT2, fg="white", activebackground=ACCENT,
               activeforeground="white", font=F_BOLD,
               relief="flat", padx=14, pady=5, cursor="hand2").pack(side=LEFT)
        Entry(row1, textvariable=self.v_folder, bg="#16162a", fg=TEXT,
              insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4,
              width=52).pack(side=LEFT, padx=10)
        Button(row1, text="🔍  Quét & Xem trước", command=self._scan,
               bg=ACCENT, fg="white", activebackground="#c04010",
               activeforeground="white", font=F_BOLD,
               relief="flat", padx=14, pady=5, cursor="hand2").pack(side=LEFT)

        # ── row 2: output folder ──
        row2 = Frame(self, bg=CARD, padx=16, pady=7)
        row2.pack(fill=X)
        self.v_out = StringVar()
        _bind_cfg("rename.out", self.v_out)
        Button(row2, text="💾  Folder output", command=self._browse_out,
               bg="#2a4a2a", fg="white", activebackground="#3a6a3a",
               activeforeground="white", font=F_BOLD,
               relief="flat", padx=14, pady=5, cursor="hand2").pack(side=LEFT)
        Entry(row2, textvariable=self.v_out, bg="#16162a", fg=TEXT,
              insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4,
              width=52).pack(side=LEFT, padx=10)
        Button(row2, text="✕  Xóa", command=lambda: self.v_out.set(""),
               bg=CARD, fg=DIM, font=F_MAIN,
               relief="flat", padx=8, pady=5, cursor="hand2").pack(side=LEFT)
        Label(row2, text="  (để trống = đổi tên tại chỗ)",
              bg=CARD, fg=DIM, font=("Segoe UI", 9)).pack(side=LEFT, padx=(8, 0))
        self.btn_open_out = Button(row2, text="🗂  Mở output",
                                   command=self._open_out,
                                   bg=CARD, fg=DIM, font=F_MAIN,
                                   relief="flat", padx=10, pady=5, cursor="hand2")
        self.btn_open_out.pack(side=RIGHT)

        # ── options row ──
        opt = Frame(self, bg=BG, padx=16, pady=7)
        opt.pack(fill=X)

        # scope
        Label(opt, text="Đánh số:", bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT)
        self.v_per_folder = BooleanVar(value=True)
        Radiobutton(opt, text="Riêng từng folder", variable=self.v_per_folder,
                    value=True, bg=BG, fg=TEXT, selectcolor=CARD,
                    activebackground=BG, font=F_MAIN).pack(side=LEFT, padx=(6, 0))
        Radiobutton(opt, text="Toàn bộ liên tiếp", variable=self.v_per_folder,
                    value=False, bg=BG, fg=TEXT, selectcolor=CARD,
                    activebackground=BG, font=F_MAIN).pack(side=LEFT, padx=(6, 18))

        self.v_recursive = BooleanVar(value=False)
        Checkbutton(opt, text="Quét tất cả subfolder (đệ quy)",
                    variable=self.v_recursive,
                    bg=BG, fg=TEXT, selectcolor=CARD,
                    activebackground=BG, font=F_MAIN).pack(side=LEFT, padx=(0, 18))

        # action (copy / move / rename-in-place)
        Label(opt, text="Khi có output:", bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT)
        self.v_action = StringVar(value="copy")
        Radiobutton(opt, text="Sao chép", variable=self.v_action, value="copy",
                    bg=BG, fg=TEXT, selectcolor=CARD,
                    activebackground=BG, font=F_MAIN).pack(side=LEFT, padx=(6, 0))
        Radiobutton(opt, text="Di chuyển", variable=self.v_action, value="move",
                    bg=BG, fg=TEXT, selectcolor=CARD,
                    activebackground=BG, font=F_MAIN).pack(side=LEFT, padx=(6, 18))

        # start number
        Label(opt, text="Bắt đầu từ:", bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT)
        self.v_start = IntVar(value=1)
        Spinbox(opt, from_=0, to=999999, increment=1, textvariable=self.v_start,
                bg=CARD, fg=TEXT, insertbackground=TEXT, buttonbackground=ACCENT2,
                relief="flat", font=F_MAIN, width=7).pack(side=LEFT, padx=(4, 18))

        # padding
        Label(opt, text="Số chữ số:", bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT)
        self.v_pad = IntVar(value=1)
        Spinbox(opt, from_=1, to=9, increment=1, textvariable=self.v_pad,
                bg=CARD, fg=TEXT, insertbackground=TEXT, buttonbackground=ACCENT2,
                relief="flat", font=F_MAIN, width=3).pack(side=LEFT, padx=(4, 4))
        Label(opt, text="(1→1.jpg  3→001.jpg)", bg=BG, fg=DIM,
              font=("Segoe UI", 9)).pack(side=LEFT, padx=(0, 18))

        # extension
        Label(opt, text="Phần mở rộng:", bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT)
        self.v_ext = StringVar(value="keep")
        for lbl, val in [("Giữ nguyên", "keep"), (".jpg", ".jpg"), (".png", ".png")]:
            Radiobutton(opt, text=lbl, variable=self.v_ext, value=val,
                        bg=BG, fg=TEXT, selectcolor=CARD,
                        activebackground=BG, font=F_MAIN).pack(side=LEFT, padx=(4, 0))

        # info card
        info = Frame(self, bg=CARD, padx=16, pady=6)
        info.pack(fill=X, padx=16, pady=(0, 6))
        self.lbl_summary = Label(info,
            text="Chọn folder rồi nhấn  🔍 Quét & Xem trước  để kiểm tra trước khi thực hiện.",
            bg=CARD, fg=DIM, font=("Segoe UI", 9), anchor=W)
        self.lbl_summary.pack(fill=X)

        # preview treeview
        tree_outer = Frame(self, bg=BG, padx=16)
        tree_outer.pack(fill=BOTH, expand=True)

        cols = ("folder", "old_name", "new_name")
        self.tree = ttk.Treeview(tree_outer, columns=cols, show="headings",
                                 style="Dark.Treeview", height=12)
        for col, txt, w in [("folder",   "Folder",   200),
                             ("old_name", "Tên cũ",   280),
                             ("new_name", "Tên mới",  180)]:
            self.tree.heading(col, text=txt)
            self.tree.column(col, width=w, anchor=W)

        sb_tree_v = Scrollbar(tree_outer, orient=VERTICAL,   command=self.tree.yview)
        sb_tree_h = Scrollbar(tree_outer, orient=HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=sb_tree_v.set,
                            xscrollcommand=sb_tree_h.set)
        self.tree.tag_configure("same",    foreground=DIM)
        self.tree.tag_configure("change",  foreground=TEXT)
        self.tree.tag_configure("warn",    foreground="#f0c040")

        sb_tree_v.pack(side=RIGHT,  fill=Y)
        sb_tree_h.pack(side=BOTTOM, fill=X)
        self.tree.pack(fill=BOTH, expand=True)

        # bottom bar
        bot = Frame(self, bg=BG, padx=16, pady=8)
        bot.pack(fill=X)

        self.btn_run = Button(bot, text="✏  Thực hiện đổi tên",
                              command=self._run, state=DISABLED,
                              bg=ACCENT, fg="white", activebackground="#c04010",
                              activeforeground="white", font=F_BOLD,
                              relief="flat", padx=20, pady=8, cursor="hand2")
        self.btn_run.pack(side=LEFT)

        Button(bot, text="🧹  Xóa", command=self._clear,
               bg=CARD, fg=DIM, font=F_MAIN,
               relief="flat", padx=14, pady=8, cursor="hand2").pack(side=LEFT, padx=(10, 0))

        self.lbl_status = Label(bot, text="", bg=BG, fg=DIM, font=F_MAIN)
        self.lbl_status.pack(side=LEFT, padx=16)

        pb_f = Frame(bot, bg=BG)
        pb_f.pack(side=RIGHT)
        self.pb_lbl = Label(pb_f, text="", bg=BG, fg=DIM, font=F_MAIN)
        self.pb_lbl.pack(anchor=E)
        self.pb = ttk.Progressbar(pb_f, style="K.Horizontal.TProgressbar",
                                  maximum=100, length=280)
        self.pb.pack()

    # ── actions ────────────────────────────────────────────────────────────────

    def _browse(self):
        p = filedialog.askdirectory(title="Chọn folder nguồn",
                                    initialdir=_cfg_dir("rename.src"))
        if p: self.v_folder.set(p)

    def _browse_out(self):
        p = filedialog.askdirectory(title="Chọn folder output",
                                    initialdir=_cfg_dir("rename.out"))
        if p: self.v_out.set(p)

    def _open_out(self):
        p = self.v_out.get().strip()
        if p and Path(p).exists():
            os.startfile(p)
        else:
            messagebox.showwarning("Chưa có output", "Nhập hoặc chạy xong để mở thư mục output.")

    def _scan(self):
        folder = self.v_folder.get().strip()
        if not folder:
            messagebox.showwarning("Chưa chọn", "Vui lòng chọn folder nguồn."); return
        if not Path(folder).is_dir():
            messagebox.showerror("Không tồn tại", f"Folder không tồn tại:\n{folder}"); return

        try:
            pad   = max(1, int(self.v_pad.get()))
            start = int(self.v_start.get())
        except (ValueError, TypeError):
            messagebox.showwarning("Giá trị không hợp lệ", "Padding / Số bắt đầu phải là số nguyên.")
            return

        out_dir    = self.v_out.get().strip() or None
        ext_choice = self.v_ext.get()
        keep_ext   = ext_choice == "keep"
        forced_ext = ext_choice if not keep_ext else ".jpg"

        self._plan = build_rename_plan(
            folder,
            out_dir    = out_dir,
            per_folder = self.v_per_folder.get(),
            padding    = pad,
            start_num  = start,
            keep_ext   = keep_ext,
            forced_ext = forced_ext,
            recursive  = self.v_recursive.get(),
        )

        # populate treeview
        self.tree.delete(*self.tree.get_children())
        changes = 0
        PREVIEW_LIMIT = 2000
        for i, (src, dst) in enumerate(self._plan):
            same = src.resolve() == dst.resolve()
            if not same:
                changes += 1
            tag = "same" if same else "change"
            if i < PREVIEW_LIMIT:
                # show output folder name in "Folder" column when out_dir is set
                dst_folder = dst.parent.name if out_dir else src.parent.name
                self.tree.insert("", END,
                                 values=(dst_folder, src.name, dst.name),
                                 tags=(tag,))

        total = len(self._plan)
        extra = total - PREVIEW_LIMIT
        if extra > 0:
            self.tree.insert("", END,
                             values=("…", f"(+{extra} file nữa)", ""),
                             tags=("warn",))

        lbl_count = sum(1 for src, dst in self._plan
                        if src.resolve() != dst.resolve()
                        and src.with_suffix(".txt").exists())
        action_label = (f"Sao chép → {out_dir}" if out_dir and self.v_action.get() == "copy"
                        else f"Di chuyển → {out_dir}" if out_dir
                        else "Đổi tên tại chỗ")
        lbl_info = f"   |   Label: {lbl_count:,} file" if lbl_count else ""
        self.lbl_summary.config(
            text=f"Tổng: {total:,} file   |   Thay đổi: {changes:,}{lbl_info}   |   {action_label}")
        self.btn_run.config(state=NORMAL if changes else DISABLED)
        self.lbl_status.config(text="")

    def _run(self):
        if not self._plan:
            return
        out_dir = self.v_out.get().strip() or None
        action  = self.v_action.get() if out_dir else "rename"

        confirm_msg = (
            f"{'Sao chép' if action=='copy' else 'Di chuyển' if action=='move' else 'Đổi tên'} "
            f"{len(self._plan):,} file?\n"
            + (f"Output: {out_dir}\n" if out_dir else "")
            + ("Hành động này không thể hoàn tác trực tiếp." if action != "copy" else "")
        )
        if not messagebox.askyesno("Xác nhận", confirm_msg):
            return

        self.btn_run.config(state=DISABLED, text="⏳  Đang xử lý…")
        self.pb["value"] = 0

        def worker():
            try:
                execute_rename_plan(
                    self._plan,
                    action   = action,
                    log      = lambda m: self.root.after(
                        0, lambda msg=m: self.lbl_status.config(text=msg)),
                    progress = lambda d, t: self.root.after(0, self._set_pb, d, t),
                )
                self.root.after(0, self._done, True)
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Lỗi", str(e)))
                self.root.after(0, self._done, False)

        threading.Thread(target=worker, daemon=True).start()

    def _set_pb(self, done, total):
        pct = int(done / total * 100)
        self.pb["value"] = pct
        self.pb_lbl.config(text=f"{done:,} / {total:,}  ({pct}%)")

    def _done(self, success):
        self.btn_run.config(state=NORMAL, text="✏  Thực hiện đổi tên")
        if success:
            self.lbl_status.config(text="✅  Hoàn thành!")
            self._plan = []
            self.btn_run.config(state=DISABLED)

    def _clear(self):
        self.tree.delete(*self.tree.get_children())
        self._plan = []
        self.btn_run.config(state=DISABLED)
        self.lbl_summary.config(
            text="Chọn folder rồi nhấn  🔍 Quét & Xem trước  để kiểm tra trước khi thực hiện.")
        self.lbl_status.config(text="")
        self.pb["value"] = 0
        self.pb_lbl.config(text="")


# ── PaddleOCR Tab ──────────────────────────────────────────────────────────────

class OcrTab(Frame):
    """Tab nhận dạng văn bản bằng PaddleOCR."""

    _LANGS = [("Tiếng Việt", "vi"), ("English", "en"), ("Tiếng Trung", "ch")]

    def __init__(self, master, root):
        super().__init__(master, bg=BG)
        self.root = root
        self._files = []          # list of Path
        self._results = []        # list of (Path, str, float)
        self._ocr_engine = None
        self._running = False
        self._cur_preview = None  # hold PhotoImage ref

        self.v_lang    = StringVar(value="vi")
        self.v_use_gpu = BooleanVar(value=False)
        self.v_angle   = BooleanVar(value=True)
        self.v_clean   = BooleanVar(value=True)
        self.v_out_dir = StringVar()
        _bind_cfg("ocr.out_dir", self.v_out_dir)

        self._build()

    # ── layout ─────────────────────────────────────────────────────────────────

    def _build(self):
        # top bar
        top = Frame(self, bg=CARD, padx=16, pady=8)
        top.pack(fill=X)
        Label(top, text="PaddleOCR PP-OCRv5 — Nhận dạng văn bản trong ảnh",
              bg=CARD, fg=TEXT, font=F_BOLD).pack(side=LEFT)
        Label(top, text="PP-OCRv5", bg=ACCENT, fg="white",
              font=("Segoe UI Semibold", 9), padx=6, pady=2).pack(side=LEFT, padx=10)
        if not _PADDLE_OK:
            Label(top,
                  text="⚠  paddleocr chưa cài  →  pip install paddleocr paddlepaddle",
                  bg=CARD, fg="#ff8844", font=("Segoe UI", 9)).pack(side=LEFT, padx=16)

        main = Frame(self, bg=BG)
        main.pack(fill=BOTH, expand=True, padx=8, pady=8)

        left = Frame(main, bg=BG, width=340)
        left.pack(side=LEFT, fill=Y, padx=(0, 6))
        left.pack_propagate(False)

        right = Frame(main, bg=BG)
        right.pack(side=LEFT, fill=BOTH, expand=True)

        self._build_left(left)
        self._build_right(right)

    def _build_left(self, parent):
        # drop zone
        dz_wrap = Frame(parent, bg="#111122", bd=2, relief=RIDGE)
        dz_wrap.pack(fill=X, pady=(0, 5))
        self.drop_zone = Label(
            dz_wrap,
            text="📂  Kéo thả ảnh hoặc folder vào đây\n(hoặc click để chọn ảnh)",
            bg="#111122", fg=DIM,
            font=("Segoe UI", 10),
            pady=24, cursor="hand2",
            justify=CENTER, wraplength=300,
        )
        self.drop_zone.pack(fill=X)
        self.drop_zone.bind("<Button-1>", lambda e: self._browse_files())

        if _DND_OK:
            self.drop_zone.drop_target_register(_dnd_mod.DND_FILES)
            self.drop_zone.dnd_bind("<<Drop>>",      self._on_drop)
            self.drop_zone.dnd_bind("<<DragEnter>>", self._on_drag_enter)
            self.drop_zone.dnd_bind("<<DragLeave>>", self._on_drag_leave)

        # file buttons
        btn_row = Frame(parent, bg=BG)
        btn_row.pack(fill=X, pady=3)
        Button(btn_row, text="🖼  Chọn ảnh",   command=self._browse_files,
               bg=ACCENT2, fg="white", activebackground=ACCENT, activeforeground="white",
               font=F_BOLD, relief="flat", padx=10, pady=5, cursor="hand2").pack(side=LEFT)
        Button(btn_row, text="📂  Chọn folder", command=self._browse_folder,
               bg=ACCENT2, fg="white", activebackground=ACCENT, activeforeground="white",
               font=F_BOLD, relief="flat", padx=10, pady=5, cursor="hand2").pack(side=LEFT, padx=5)
        Button(btn_row, text="✕  Xóa",          command=self._clear_files,
               bg=CARD, fg=DIM, font=F_MAIN, relief="flat",
               padx=8, pady=5, cursor="hand2").pack(side=LEFT)

        self.lbl_files = Label(parent, text="Chưa chọn ảnh nào.",
                               bg=BG, fg=DIM, font=F_MAIN, anchor=W, wraplength=320)
        self.lbl_files.pack(fill=X, pady=2)

        Frame(parent, bg=ACCENT2, height=1).pack(fill=X, pady=8)

        # options
        opt = Frame(parent, bg=BG)
        opt.pack(fill=X)

        rw = Frame(opt, bg=BG)
        rw.pack(fill=X, pady=3)
        Label(rw, text="Ngôn ngữ:", bg=BG, fg=TEXT, font=F_MAIN, width=14, anchor=W).pack(side=LEFT)
        for name, val in self._LANGS:
            Radiobutton(rw, text=name, variable=self.v_lang, value=val,
                        bg=BG, fg=TEXT, selectcolor=CARD, activebackground=BG,
                        font=F_MAIN, command=self._invalidate_engine).pack(side=LEFT, padx=(0, 8))

        rw2 = Frame(opt, bg=BG)
        rw2.pack(fill=X, pady=3)
        Label(rw2, text="Tùy chọn:", bg=BG, fg=TEXT, font=F_MAIN, width=14, anchor=W).pack(side=LEFT)
        Checkbutton(rw2, text="Dùng GPU", variable=self.v_use_gpu,
                    bg=BG, fg=TEXT, selectcolor=CARD, activebackground=BG,
                    font=F_MAIN, command=self._invalidate_engine).pack(side=LEFT)
        Checkbutton(rw2, text="Nhận dạng góc nghiêng", variable=self.v_angle,
                    bg=BG, fg=TEXT, selectcolor=CARD, activebackground=BG,
                    font=F_MAIN, command=self._invalidate_engine).pack(side=LEFT, padx=6)

        rw3 = Frame(opt, bg=BG)
        rw3.pack(fill=X, pady=3)
        Label(rw3, text="Hậu xử lý:", bg=BG, fg=TEXT, font=F_MAIN, width=14, anchor=W).pack(side=LEFT)
        Checkbutton(rw3, text="Bỏ ký tự đặc biệt  (- . , space …)",
                    variable=self.v_clean,
                    bg=BG, fg=TEXT, selectcolor=CARD, activebackground=BG,
                    font=F_MAIN).pack(side=LEFT)

        Frame(parent, bg=ACCENT2, height=1).pack(fill=X, pady=8)

        # output folder
        Label(parent, text="Output folder (để trống = ghi cạnh ảnh):",
              bg=BG, fg=TEXT, font=F_MAIN, anchor=W).pack(fill=X)
        orw = Frame(parent, bg=BG)
        orw.pack(fill=X, pady=2)
        Button(orw, text="📁", command=self._browse_out,
               bg=CARD, fg=TEXT, relief="flat", padx=6, pady=3,
               cursor="hand2").pack(side=LEFT)
        Entry(orw, textvariable=self.v_out_dir, bg="#16162a", fg=TEXT,
              insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4).pack(
              side=LEFT, fill=X, expand=True, padx=4)
        Button(orw, text="✕", command=lambda: self.v_out_dir.set(""),
               bg=CARD, fg=DIM, relief="flat", padx=6, pady=3,
               cursor="hand2").pack(side=LEFT)

        Frame(parent, bg=ACCENT2, height=1).pack(fill=X, pady=8)

        # progress
        self.pb = ttk.Progressbar(parent, style="K.Horizontal.TProgressbar",
                                  length=300, mode="determinate")
        self.pb.pack(fill=X, pady=2)
        self.lbl_prog = Label(parent, text="", bg=BG, fg=DIM,
                              font=("Segoe UI", 9), anchor=W)
        self.lbl_prog.pack(fill=X)

        # run button
        self.btn_run = Button(parent, text="▶   Nhận dạng",
                              command=self._start_ocr,
                              bg=SUCCESS, fg="white",
                              activebackground="#3d9140", activeforeground="white",
                              font=F_BOLD, relief="flat",
                              padx=16, pady=8, cursor="hand2")
        self.btn_run.pack(fill=X, pady=(8, 0))

    def _build_right(self, parent):
        # ── header bar ─────────────────────────────────────────────────────────
        hdr = Frame(parent, bg=CARD, padx=10, pady=6)
        hdr.pack(fill=X, pady=(0, 4))
        Label(hdr, text="Kết quả nhận dạng", bg=CARD, fg=TEXT,
              font=F_BOLD).pack(side=LEFT)
        self.lbl_count  = Label(hdr, text="", bg=CARD, fg=DIM,
                                font=("Segoe UI", 9))
        self.lbl_count.pack(side=LEFT, padx=12)
        self.lbl_stats  = Label(hdr, text="", bg=CARD, fg=DIM,
                                font=("Segoe UI", 9))
        self.lbl_stats.pack(side=LEFT)

        # ── legend badges (right side) ─────────────────────────────────────────
        leg = Frame(hdr, bg=CARD)
        leg.pack(side=RIGHT)
        for txt, bg, fg in [("≥90%", "#1a3a1a", "#6ddd6d"),
                             ("70–89%", "#3a2e00", "#ddbb00"),
                             ("<70%", "#3a1010", "#dd6060")]:
            Label(leg, text=txt, bg=bg, fg=fg,
                  font=("Segoe UI", 8), padx=5, pady=1).pack(side=LEFT, padx=2)

        # ── table ──────────────────────────────────────────────────────────────
        tbl = Frame(parent, bg="#111122")
        tbl.pack(fill=BOTH, expand=True)

        s = ttk.Style()
        s.configure("OCR.Treeview",
                    background="#16162a", foreground=TEXT,
                    fieldbackground="#16162a",
                    rowheight=28, font=("Consolas", 10))
        s.configure("OCR.Treeview.Heading",
                    background=ACCENT2, foreground="white",
                    relief="flat", font=("Segoe UI Semibold", 9))
        s.map("OCR.Treeview",
              background=[("selected", ACCENT2)],
              foreground=[("selected", "white")])

        cols = ("file", "text", "conf")
        self.tree = ttk.Treeview(tbl, columns=cols, show="headings",
                                 style="OCR.Treeview", selectmode="browse")
        self.tree.heading("file", text="Tên file", anchor=W)
        self.tree.heading("text", text="Văn bản nhận dạng", anchor=W)
        self.tree.heading("conf", text="Tin cậy", anchor=CENTER)
        self.tree.column("file", width=150, minwidth=90,  stretch=False)
        self.tree.column("text", width=260, minwidth=120, stretch=True)
        self.tree.column("conf", width=70,  minwidth=55,  stretch=False, anchor=CENTER)

        # confidence row tags
        self.tree.tag_configure("hi",  background="#0e2a0e", foreground="#7ddd7d")
        self.tree.tag_configure("mid", background="#2e2600", foreground="#ddbb44")
        self.tree.tag_configure("lo",  background="#2e0e0e", foreground="#dd7070")
        self.tree.tag_configure("err", background="#3a0a0a", foreground="#ff4444")
        self.tree.tag_configure("sel", background=ACCENT2,  foreground="white")

        vsb = ttk.Scrollbar(tbl, orient=VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side=RIGHT, fill=Y)
        self.tree.pack(fill=BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>",         self._on_edit)

        # ── preview ────────────────────────────────────────────────────────────
        pf = Frame(parent, bg="#0d0d1e", bd=0)
        pf.pack(fill=X, pady=(4, 0))

        prev_hdr = Frame(pf, bg="#0d0d1e")
        prev_hdr.pack(fill=X, padx=8, pady=(4, 0))
        Label(prev_hdr, text="Xem trước", bg="#0d0d1e",
              fg=DIM, font=("Segoe UI", 9)).pack(side=LEFT)
        self.lbl_prev_text = Label(prev_hdr, text="", bg="#0d0d1e",
                                   fg=ACCENT, font=("Consolas", 11, "bold"))
        self.lbl_prev_text.pack(side=LEFT, padx=12)

        self.canvas_prev = Canvas(pf, bg="#0a0a18", height=155,
                                  highlightthickness=0)
        self.canvas_prev.pack(fill=X, padx=6, pady=(2, 6))

        # ── export / action buttons ────────────────────────────────────────────
        sep = Frame(parent, bg=ACCENT2, height=1)
        sep.pack(fill=X, pady=4)

        brw = Frame(parent, bg=BG)
        brw.pack(fill=X)
        Button(brw, text="💾  Xuất gt.txt",
               command=self._export_gt,
               bg=ACCENT, fg="white",
               activebackground="#c04010", activeforeground="white",
               font=F_BOLD, relief="flat", padx=14, pady=6,
               cursor="hand2").pack(side=LEFT)
        Button(brw, text="📋  Copy tất cả",
               command=self._copy_results,
               bg=CARD, fg=TEXT, font=F_MAIN, relief="flat",
               padx=10, pady=6, cursor="hand2").pack(side=LEFT, padx=6)
        Button(brw, text="🗑  Xóa kết quả",
               command=self._clear_results,
               bg=CARD, fg=DIM, font=F_MAIN, relief="flat",
               padx=10, pady=6, cursor="hand2").pack(side=LEFT)

        self.lbl_status = Label(parent, text="", bg=BG, fg=DIM,
                                font=("Segoe UI", 9), anchor=W)
        self.lbl_status.pack(fill=X, pady=(2, 0))

    # ── drag & drop ────────────────────────────────────────────────────────────

    def _on_drag_enter(self, event):
        self.drop_zone.config(bg="#252540", fg=ACCENT)

    def _on_drag_leave(self, event):
        self.drop_zone.config(bg="#111122", fg=DIM)

    def _on_drop(self, event):
        self.drop_zone.config(bg="#111122", fg=DIM)
        import re
        parts = re.findall(r'\{[^}]+\}|[^\s]+', event.data)
        self._add_paths([p.strip("{}") for p in parts])

    # ── file selection ─────────────────────────────────────────────────────────

    def _browse_files(self):
        paths = filedialog.askopenfilenames(
            title="Chọn ảnh",
            filetypes=[("Image files",
                        " ".join(f"*{e}" for e in IMAGE_EXTENSIONS)),
                       ("All files", "*.*")],
        )
        if paths:
            self._add_paths(list(paths))

    def _browse_folder(self):
        folder = filedialog.askdirectory(title="Chọn folder ảnh")
        if folder:
            self._add_paths([folder])

    def _browse_out(self):
        folder = filedialog.askdirectory(title="Chọn folder output",
                                         initialdir=_cfg_dir("ocr.out_dir"))
        if folder:
            self.v_out_dir.set(folder)

    def _add_paths(self, paths):
        for p in paths:
            p = Path(p)
            if p.is_dir():
                for img in sorted(p.rglob("*")):
                    if img.suffix.lower() in IMAGE_EXTENSIONS and img not in self._files:
                        self._files.append(img)
            elif p.suffix.lower() in IMAGE_EXTENSIONS and p not in self._files:
                self._files.append(p)
        self._update_file_label()

    def _clear_files(self):
        self._files.clear()
        self._update_file_label()

    def _update_file_label(self):
        n = len(self._files)
        if n == 0:
            self.lbl_files.config(text="Chưa chọn ảnh nào.", fg=DIM)
            self.drop_zone.config(
                text="📂  Kéo thả ảnh hoặc folder vào đây\n(hoặc click để chọn ảnh)",
                fg=DIM)
        else:
            dirs = len({f.parent for f in self._files})
            self.lbl_files.config(
                text=f"Đã chọn {n} ảnh từ {dirs} folder.", fg=TEXT)
            self.drop_zone.config(
                text=f"✅  {n} ảnh đã sẵn sàng\n(Kéo thả thêm để bổ sung)",
                fg=SUCCESS)

    # ── OCR engine ─────────────────────────────────────────────────────────────

    def _invalidate_engine(self):
        self._ocr_engine = None

    # PP-OCRv5 server_det dùng PIR format → lỗi trên nhiều bản paddle.
    # Dùng mobile_det (classic IR) + rec model tương ứng từng ngôn ngữ.
    _REC_V5 = {
        "vi": "latin_PP-OCRv5_mobile_rec",
        "en": "en_PP-OCRv5_mobile_rec",
        "ch": "PP-OCRv5_server_rec",
    }

    def _get_engine(self):
        if self._ocr_engine is None:
            if not _PADDLE_OK:
                raise RuntimeError(
                    "PaddleOCR chưa cài.\nChạy lệnh:\n\n"
                    "  pip install paddleocr paddlepaddle\n\n"
                    "rồi khởi động lại ứng dụng.")
            lang     = self.v_lang.get()
            rec      = self._REC_V5.get(lang, "latin_PP-OCRv5_mobile_rec")
            use_gpu  = self.v_use_gpu.get()

            # Kiểm tra GPU thực sự khả dụng
            try:
                import paddle
                gpu_ok = paddle.device.is_compiled_with_cuda() and \
                         paddle.device.cuda.device_count() > 0
            except Exception:
                gpu_ok = False

            if use_gpu and not gpu_ok:
                # Thông báo và tự chuyển về CPU
                self.after(0, lambda: messagebox.showwarning(
                    "GPU không khả dụng",
                    "PaddlePaddle CPU-only đang được dùng.\n\n"
                    "Để dùng GPU hãy cài:\n"
                    "  pip install paddlepaddle-gpu\n\n"
                    "Sẽ chạy bằng CPU.", parent=self))
                use_gpu = False

            kwargs = dict(
                text_detection_model_name="PP-OCRv5_mobile_det",
                text_recognition_model_name=rec,
                use_textline_orientation=self.v_angle.get(),
                text_det_thresh=0.2,       # hạ ngưỡng để không bỏ sót dòng mờ
                text_det_box_thresh=0.5,
                text_det_unclip_ratio=1.8, # mở rộng vùng bao text
            )
            if use_gpu:
                kwargs["device"] = "gpu"
            else:
                kwargs["enable_mkldnn"] = False  # tránh bug PIR/OneDNN paddle 3.x trên CPU

            self._ocr_engine = _PaddleOCR(**kwargs)
        return self._ocr_engine

    # ── OCR run ────────────────────────────────────────────────────────────────

    def _start_ocr(self):
        if self._running:
            return
        if not self._files:
            messagebox.showwarning("Chưa chọn ảnh",
                                   "Hãy chọn ít nhất một ảnh.", parent=self)
            return
        if not _PADDLE_OK:
            messagebox.showerror(
                "Thiếu thư viện",
                "PaddleOCR chưa được cài đặt.\n\n"
                "Chạy lệnh:\n  pip install paddleocr paddlepaddle\n\n"
                "rồi khởi động lại ứng dụng.", parent=self)
            return
        self._running = True
        self.btn_run.config(state=DISABLED, text="⏳  Đang nhận dạng...")
        self.pb["value"] = 0
        self.lbl_prog.config(text="")
        threading.Thread(target=self._ocr_worker, daemon=True).start()

    def _ocr_worker(self):
        try:
            ocr = self._get_engine()
        except RuntimeError as e:
            self.after(0, lambda msg=str(e):
                       messagebox.showerror("Lỗi", msg, parent=self))
            self.after(0, self._done)
            return

        total = len(self._files)
        results = []
        for i, img_path in enumerate(self._files):
            self.after(0, self._update_prog, i, total, img_path.name)
            try:
                raw = ocr.predict(str(img_path))
                text, conf = self._extract_text(raw)

                # Adaptive retry: tự động enhance ảnh nếu confidence thấp hoặc không có text
                if conf < 0.75 or not text.strip():
                    import tempfile, os as _os
                    enhanced = self._auto_enhance(str(img_path))
                    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as _f:
                        tmp = _f.name
                    try:
                        enhanced.save(tmp)
                        raw2 = ocr.predict(tmp)
                        text2, conf2 = self._extract_text(raw2)
                        if conf2 > conf or (not text.strip() and text2.strip()):
                            text, conf = text2, conf2
                    finally:
                        try: _os.unlink(tmp)
                        except: pass

                # Đánh dấu ảnh chất lượng quá thấp
                if not text.strip():
                    text = "[⚠ chất lượng thấp]"

                if self.v_clean.get() and not text.startswith("["):
                    text = self._clean_text(text)
            except Exception as e:
                text, conf = f"[Lỗi: {e}]", 0.0
            results.append((img_path, text, conf))

        self._results = results
        self.after(0, self._populate_tree)
        self.after(0, self._done)

    @staticmethod
    def _clean_text(text):
        """Giữ lại A-Z 0-9, bỏ mọi ký tự đặc biệt, in hoa."""
        import re
        return re.sub(r'[^A-Za-z0-9]', '', text).upper()

    @staticmethod
    def _img_stats(img_bgr):
        import cv2, numpy as np
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY).astype(float)
        return float(gray.mean()), float(gray.std())

    @staticmethod
    def _auto_enhance(img_path):
        """CLAHE + Unsharp Mask; cho nền vàng dùng kênh HSV-Value.
        Trả về PIL.Image đã xử lý."""
        import cv2, numpy as np
        from PIL import Image

        img_bgr = cv2.imread(img_path)
        if img_bgr is None:
            return Image.open(img_path).convert('RGB')

        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        brightness = float(gray.mean())
        contrast   = float(gray.std())

        # Phát hiện nền vàng/đơn sắc: mean saturation cao, contrast thấp
        hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
        sat_mean = float(hsv[:, :, 1].mean())
        is_colored_bg = sat_mean > 60 and contrast < 35

        if is_colored_bg:
            # Dùng kênh V (value) trong HSV để loại bỏ màu nền
            v_ch = hsv[:, :, 2]
            clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(4, 4))
            v_enh = clahe.apply(v_ch)
            src = cv2.cvtColor(v_enh, cv2.COLOR_GRAY2BGR)
        else:
            # CLAHE trên kênh L (LAB) — giữ màu tự nhiên
            lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clip = 4.0 if contrast < 30 else 2.5
            clahe = cv2.createCLAHE(clipLimit=clip, tileGridSize=(8, 8))
            l2  = clahe.apply(l)
            src = cv2.cvtColor(cv2.merge([l2, a, b]), cv2.COLOR_LAB2BGR)

        # Upscale x2 nếu ảnh nhỏ (< 400px cạnh dài)
        h, w = src.shape[:2]
        if max(h, w) < 400:
            src = cv2.resize(src, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)

        # Unsharp Mask (tự nhiên hơn sharpen kernel)
        blurred = cv2.GaussianBlur(src, (0, 0), 2.0)
        out_bgr = cv2.addWeighted(src, 1.7, blurred, -0.7, 0)
        out_bgr = np.clip(out_bgr, 0, 255).astype(np.uint8)

        return Image.fromarray(cv2.cvtColor(out_bgr, cv2.COLOR_BGR2RGB))

    @staticmethod
    def _extract_text(ocr_result):
        """Flatten PaddleOCR 3.x result → (joined_text, avg_confidence).

        Sắp xếp các dòng theo tọa độ Y (trên→dưới) dựa vào rec_polys
        để biển số nhiều dòng được ghép đúng thứ tự.
        """
        lines, confs = [], []
        if not ocr_result:
            return "", 0.0
        for page in ocr_result:
            if page is None:
                continue
            # PaddleOCR 3.x: dict-like with rec_polys / rec_texts / rec_scores
            try:
                polys  = page["rec_polys"]
                texts  = page["rec_texts"]
                scores = page["rec_scores"]
                # sort top→bottom by min-Y of each bounding box polygon
                # rec_polys là numpy array shape (4,2) → dùng numpy .min()
                def _min_y(poly):
                    try:
                        import numpy as np
                        return float(np.asarray(poly)[:, 1].min())
                    except Exception:
                        return 0.0
                items = sorted(zip(polys, texts, scores), key=lambda x: _min_y(x[0]))
                for _, t, c in items:
                    s = str(t).strip()
                    if s:
                        lines.append(s)
                        confs.append(float(c))
                continue
            except (KeyError, TypeError):
                pass
            # Fallback: PaddleOCR 2.x nested list  [[bbox,(text,conf)],...]
            if not isinstance(page, list):
                continue
            for item in page:
                if item and len(item) >= 2 and item[1]:
                    t, c = item[1]
                    s = str(t).strip()
                    if s:
                        lines.append(s)
                        confs.append(float(c))
        text = " ".join(lines)
        avg_conf = sum(confs) / len(confs) if confs else 0.0
        return text, avg_conf

    def _update_prog(self, i, total, name):
        self.pb["value"] = int(i / total * 100)
        self.lbl_prog.config(text=f"({i}/{total})  {name}")

    def _done(self):
        self._running = False
        self.btn_run.config(state=NORMAL, text="▶   Nhận dạng")
        self.pb["value"] = 100
        self.lbl_prog.config(text=f"Hoàn thành — {len(self._results)} ảnh")

    # ── results table ──────────────────────────────────────────────────────────

    def _populate_tree(self):
        self.tree.delete(*self.tree.get_children())
        has_text = 0
        total_conf = 0.0
        for img_path, text, conf in self._results:
            if conf >= 0.90:
                tag = "hi"
            elif conf >= 0.70:
                tag = "mid"
            elif conf > 0:
                tag = "lo"
            else:
                tag = "err"
            conf_str = f"{conf:.0%}" if conf > 0 else "—"
            self.tree.insert("", END, iid=str(img_path),
                             values=(img_path.name, text, conf_str),
                             tags=(tag,))
            if text and not text.startswith("[Lỗi"):
                has_text += 1
                total_conf += conf
        n = len(self._results)
        avg = total_conf / has_text if has_text else 0.0
        self.lbl_count.config(text=f"  {n} ảnh")
        self.lbl_stats.config(
            text=f"│  {has_text} có text  │  avg {avg:.0%}" if has_text else ""
        )

    def _on_select(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        iid = sel[0]
        self._show_preview(Path(iid))
        vals = self.tree.item(iid, "values")
        if vals:
            self.lbl_prev_text.config(text=vals[1] if vals[1] else "—")

    def _on_edit(self, event):
        """Popup để sửa văn bản nhận dạng."""
        sel = self.tree.selection()
        if not sel:
            return
        iid = sel[0]
        fname, text, conf = self.tree.item(iid)["values"]

        dlg = Toplevel(self)
        dlg.title("Sửa văn bản")
        dlg.configure(bg=CARD)
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.geometry("480x130")
        Label(dlg, text=f"Sửa nhận dạng cho:  {fname}",
              bg=CARD, fg=TEXT, font=F_BOLD).pack(padx=16, pady=(12, 4))
        var = StringVar(value=str(text))
        ent = Entry(dlg, textvariable=var, bg="#16162a", fg=TEXT,
                    insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4)
        ent.pack(fill=X, padx=16, pady=4)
        ent.focus_set()
        ent.select_range(0, END)

        def _save():
            new_text = var.get().strip()
            self.tree.item(iid, values=(fname, new_text, conf))
            for i, (p, t, c) in enumerate(self._results):
                if str(p) == iid:
                    self._results[i] = (p, new_text, c)
                    break
            dlg.destroy()

        br = Frame(dlg, bg=CARD)
        br.pack(pady=6)
        Button(br, text="Lưu", command=_save,
               bg=ACCENT, fg="white", relief="flat",
               padx=14, pady=4, cursor="hand2", font=F_BOLD).pack(side=LEFT, padx=6)
        Button(br, text="Hủy", command=dlg.destroy,
               bg=BG, fg=DIM, relief="flat",
               padx=14, pady=4, cursor="hand2", font=F_MAIN).pack(side=LEFT)
        ent.bind("<Return>", lambda e: _save())
        ent.bind("<Escape>", lambda e: dlg.destroy())

    def _show_preview(self, img_path):
        try:
            from PIL import Image, ImageTk
            img = Image.open(img_path)
            cw = max(self.canvas_prev.winfo_width(), 400)
            img.thumbnail((cw, 130))
            photo = ImageTk.PhotoImage(img)
            self._cur_preview = photo
            w, h = img.size
            self.canvas_prev.config(height=h)
            self.canvas_prev.delete("all")
            self.canvas_prev.create_image(cw // 2, h // 2, image=photo)
        except Exception:
            pass

    # ── export ─────────────────────────────────────────────────────────────────

    def _export_gt(self):
        if not self._results:
            messagebox.showinfo("Chưa có kết quả",
                                "Hãy chạy nhận dạng trước.", parent=self)
            return

        out_dir = self.v_out_dir.get().strip()

        if out_dir:
            out_path = Path(out_dir) / "gt.txt"
            Path(out_dir).mkdir(parents=True, exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as f:
                for img_path, text, _ in self._results:
                    f.write(f"{img_path.name}\t{text}\n")
            n = len(self._results)
            self.lbl_status.config(
                text=f"✅  Đã xuất {n} dòng → {out_path}", fg=SUCCESS)
            messagebox.showinfo("Xuất thành công",
                                f"Đã ghi {n} dòng vào:\n{out_path}", parent=self)
        else:
            # Ghi gt.txt cạnh mỗi folder ảnh
            folders = {}
            for img_path, text, _ in self._results:
                folders.setdefault(img_path.parent, []).append((img_path.name, text))
            for folder, items in folders.items():
                with open(folder / "gt.txt", "w", encoding="utf-8") as f:
                    for fname, text in items:
                        f.write(f"{fname}\t{text}\n")
            n_f = len(folders)
            n_i = len(self._results)
            self.lbl_status.config(
                text=f"✅  Đã xuất {n_i} dòng vào {n_f} file gt.txt", fg=SUCCESS)
            messagebox.showinfo("Xuất thành công",
                                f"Đã ghi gt.txt vào {n_f} folder.\n"
                                f"Tổng {n_i} ảnh.", parent=self)

    def _copy_results(self):
        if not self._results:
            return
        lines = [f"{p.name}\t{t}" for p, t, _ in self._results]
        self.root.clipboard_clear()
        self.root.clipboard_append("\n".join(lines))
        self.lbl_status.config(
            text=f"✅  Đã copy {len(lines)} dòng vào clipboard", fg=SUCCESS)

    def _clear_results(self):
        self._results.clear()
        self.tree.delete(*self.tree.get_children())
        self.lbl_count.config(text="")
        self.lbl_stats.config(text="")
        self.lbl_prev_text.config(text="")
        self.lbl_status.config(text="")
        self.pb["value"] = 0
        self.lbl_prog.config(text="")
        self.canvas_prev.delete("all")


# ── Tab 7: LotteImage ─────────────────────────────────────────────────────────

class LotteImageTab(Frame):
    """Thu thập & phân loại ảnh từ API bãi đỗ xe KZTEK."""

    def __init__(self, master, root):
        super().__init__(master, bg=BG)
        self.root    = root
        self._worker: Optional[LotteWorker] = None
        self._thread = None
        self._log_q  = queue.Queue()
        self._stat_q = queue.Queue()
        self._build()
        self._poll()

    # ── build ──────────────────────────────────────────────────────────────────

    def _build(self):
        top = Frame(self, bg=CARD, padx=16, pady=8)
        top.pack(fill=X)
        Label(top, text="LotteImage — Thu thập & phân loại ảnh bãi đỗ xe",
              bg=CARD, fg=TEXT, font=F_BOLD).pack(side=LEFT)
        if not _REQUESTS_OK:
            Label(top, text="  ⚠ pip install requests",
                  bg=CARD, fg="#ff8844", font=("Segoe UI", 9)).pack(side=LEFT, padx=8)
        if not _CV2_OK:
            Label(top, text="  ⚠ pip install opencv-python numpy",
                  bg=CARD, fg="#ff8844", font=("Segoe UI", 9)).pack(side=LEFT, padx=4)

        body = Frame(self, bg=BG, padx=14, pady=6)
        body.pack(fill=BOTH, expand=True)
        self._build_time(body)
        self._build_output(body)
        self._build_settings(body)
        self._build_controls(body)
        self._build_progress(body)
        self._build_log(body)

    def _sep(self, parent, text: str):
        f = Frame(parent, bg=BG)
        f.pack(fill=X, pady=(8, 3))
        Label(f, text=text, font=("Segoe UI", 9, "bold"),
              fg=ACCENT2, bg=BG).pack(side=LEFT)
        Frame(f, bg=DIM, height=1).pack(
            side=LEFT, fill=X, expand=True, padx=(8, 0), pady=5)

    def _build_time(self, p):
        self._sep(p, "Khoảng thời gian")
        f = Frame(p, bg=BG)
        f.pack(fill=X)
        Label(f, text="Từ:", bg=BG, fg=TEXT, font=F_MAIN).grid(
            row=0, column=0, padx=(0, 4), sticky=W)
        self.from_var = StringVar(value="2026-05-01 00:00:00")
        Entry(f, textvariable=self.from_var, width=22,
              bg=CARD, fg=TEXT, insertbackground=TEXT,
              relief="flat", font=F_MAIN, bd=4).grid(row=0, column=1, padx=4)
        Label(f, text="Đến:", bg=BG, fg=TEXT, font=F_MAIN).grid(
            row=0, column=2, padx=(14, 4))
        self.to_var = StringVar(
            value=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        Entry(f, textvariable=self.to_var, width=22,
              bg=CARD, fg=TEXT, insertbackground=TEXT,
              relief="flat", font=F_MAIN, bd=4).grid(row=0, column=3, padx=4)
        Label(f, text="Định dạng: YYYY-MM-DD HH:MM:SS",
              font=("Segoe UI", 8), fg=DIM, bg=BG).grid(
            row=1, column=1, columnspan=3, sticky=W, pady=(2, 0))

    def _build_output(self, p):
        self._sep(p, "Thư mục lưu ảnh")
        f = Frame(p, bg=BG)
        f.pack(fill=X)
        f.columnconfigure(0, weight=1)
        self.out_var = StringVar(value=str(Path.cwd() / "images"))
        _bind_cfg("lotte.out", self.out_var)
        Entry(f, textvariable=self.out_var,
              bg=CARD, fg=TEXT, insertbackground=TEXT,
              relief="flat", font=F_MAIN, bd=4).grid(
            row=0, column=0, sticky=EW, padx=(0, 8))
        Button(f, text="Chọn…", command=self._browse,
               bg=ACCENT2, fg="white", font=F_MAIN,
               activebackground=ACCENT, activeforeground="white",
               relief="flat", padx=10, cursor="hand2").grid(row=0, column=1)
        Label(p,
              text="Cấu trúc: <thư mục> / <tên làn> / <năm> / <ngày>"
                   " / <overview|bike|car> / HHmmss_BSX.jpg",
              font=("Segoe UI", 8), fg=DIM, bg=BG, anchor=W).pack(
            fill=X, pady=(3, 0))

    def _build_settings(self, p):
        self._sep(p, "Cài đặt")
        f = Frame(p, bg=BG)
        f.pack(fill=X)
        Label(f, text="Page size:", bg=BG, fg=TEXT, font=F_MAIN).grid(
            row=0, column=0, padx=(0, 4), sticky=W)
        self.page_size_var = IntVar(value=100)
        Spinbox(f, from_=10, to=500, textvariable=self.page_size_var,
                width=7, font=F_MAIN, bg=CARD, fg=TEXT,
                insertbackground=TEXT, buttonbackground=ACCENT2,
                relief="flat").grid(row=0, column=1, padx=4)
        Label(f, text="Max pages:", bg=BG, fg=TEXT, font=F_MAIN).grid(
            row=0, column=2, padx=(12, 4))
        self.max_pages_var = IntVar(value=10000)
        Spinbox(f, from_=1, to=99999, textvariable=self.max_pages_var,
                width=8, font=F_MAIN, bg=CARD, fg=TEXT,
                insertbackground=TEXT, buttonbackground=ACCENT2,
                relief="flat").grid(row=0, column=3, padx=4)
        Label(f, text="Nghỉ (s):", bg=BG, fg=TEXT, font=F_MAIN).grid(
            row=0, column=4, padx=(12, 4))
        self.sleep_var = DoubleVar(value=0.1)
        Entry(f, textvariable=self.sleep_var, width=6,
              bg=CARD, fg=TEXT, insertbackground=TEXT,
              relief="flat", font=F_MAIN, bd=4).grid(row=0, column=5, padx=4)
        self.use_minio = BooleanVar(value=True)
        Checkbutton(f, text="MinIO", variable=self.use_minio,
                    bg=BG, fg=TEXT, selectcolor=CARD,
                    activebackground=BG, font=F_MAIN).grid(
            row=0, column=6, padx=(14, 0))

        adv_bar = Frame(p, bg=BG)
        adv_bar.pack(fill=X, pady=(5, 0))
        self._adv_open = False
        self._adv_lbl  = Label(adv_bar, text="▶ Nâng cao (API / MinIO)",
                                font=("Segoe UI", 8, "underline"),
                                fg=ACCENT2, bg=BG, cursor="hand2")
        self._adv_lbl.pack(anchor=W)
        self._adv_lbl.bind("<Button-1>", self._toggle_adv)
        self._adv_frame = Frame(p, bg=CARD, bd=1, relief="flat",
                                padx=8, pady=6)
        self._build_adv(self._adv_frame)

    def _build_adv(self, p):
        fields = [
            ("API URL:",        "cfg_api",  _LI_API_BASE,     38, ""),
            ("Username:",       "cfg_user", _LI_USERNAME,     16, ""),
            ("Password:",       "cfg_pass", _LI_PASSWORD,     16, "*"),
            ("MinIO endpoint:", "cfg_mep",  _LI_MINIO_EP,     26, ""),
            ("MinIO bucket:",   "cfg_mbk",  _LI_MINIO_BUCKET, 20, ""),
            ("MinIO AK:",       "cfg_mak",  _LI_MINIO_AK,     16, ""),
            ("MinIO SK:",       "cfg_msk",  _LI_MINIO_SK,     20, "*"),
        ]
        for i, (lbl, attr, default, width, show) in enumerate(fields):
            r, c = divmod(i, 2)
            Label(p, text=lbl, font=("Segoe UI", 8),
                  bg=CARD, fg=DIM).grid(
                row=r, column=c * 2,
                padx=(0 if c == 0 else 16, 4), pady=2, sticky=W)
            var = StringVar(value=default)
            setattr(self, attr, var)
            Entry(p, textvariable=var, width=width, show=show,
                  bg="#16162a", fg=TEXT, insertbackground=TEXT,
                  relief="flat", font=F_MAIN, bd=4).grid(
                row=r, column=c * 2 + 1, padx=(0, 4), pady=2)

    def _toggle_adv(self, _=None):
        self._adv_open = not self._adv_open
        if self._adv_open:
            self._adv_frame.pack(fill=X, pady=(0, 4))
            self._adv_lbl.config(text="▼ Nâng cao (API / MinIO)")
        else:
            self._adv_frame.pack_forget()
            self._adv_lbl.config(text="▶ Nâng cao (API / MinIO)")

    def _build_controls(self, p):
        f = Frame(p, bg=BG)
        f.pack(fill=X, pady=(10, 4))
        self.start_btn = Button(
            f, text="▶  Bắt đầu", command=self._start,
            bg=ACCENT, fg="white", font=F_BOLD,
            activebackground="#c04010", activeforeground="white",
            relief="flat", padx=22, pady=7, cursor="hand2")
        self.start_btn.pack(side=LEFT, padx=(0, 8))
        self.stop_btn = Button(
            f, text="⬛  Dừng", command=self._stop,
            bg=DIM, fg=BG, font=F_BOLD,
            relief="flat", padx=22, pady=7,
            state=DISABLED, cursor="hand2")
        self.stop_btn.pack(side=LEFT)
        self.status_lbl = Label(f, text="Sẵn sàng",
                                font=F_MAIN, fg=ACCENT2, bg=BG)
        self.status_lbl.pack(side=RIGHT)

    def _build_progress(self, p):
        self._sep(p, "Tiến độ")
        f = Frame(p, bg=BG)
        f.pack(fill=X, pady=(0, 4))
        self.pbar = ttk.Progressbar(f, mode="indeterminate",
                                    style="K.Horizontal.TProgressbar")
        self.pbar.pack(side=LEFT, fill=X, expand=True, padx=(0, 12))
        self.stat_lbl = Label(
            f,
            text="Trang: 0  |  Sự kiện: 0  |  Ảnh tìm: 0  |  Đã lưu: 0  |  Lỗi: 0",
            font=F_MONO, fg=TEXT, bg=BG)
        self.stat_lbl.pack(side=LEFT)

    def _build_log(self, p):
        self._sep(p, "Nhật ký")
        f = Frame(p, bg=BG)
        f.pack(fill=BOTH, expand=True)
        f.columnconfigure(0, weight=1)
        f.rowconfigure(0, weight=1)
        self.log_txt = Text(
            f, height=11, font=F_MONO,
            bg="#16162a", fg="#d4d4d4",
            relief="flat", wrap=WORD,
            insertbackground="#d4d4d4", state=DISABLED)
        self.log_txt.grid(row=0, column=0, sticky=NSEW)
        sb = ttk.Scrollbar(f, command=self.log_txt.yview)
        sb.grid(row=0, column=1, sticky=NS)
        self.log_txt["yscrollcommand"] = sb.set
        Button(f, text="Xóa log",
               command=lambda: (self.log_txt.configure(state=NORMAL),
                                self.log_txt.delete("1.0", END),
                                self.log_txt.configure(state=DISABLED)),
               bg=CARD, fg=DIM, font=F_MAIN,
               relief="flat", padx=8, cursor="hand2").grid(
            row=1, column=0, sticky=W, pady=(4, 0))

    # ── actions ────────────────────────────────────────────────────────────────

    def _browse(self):
        d = filedialog.askdirectory(title="Chọn thư mục lưu ảnh",
                                    initialdir=_cfg_dir("lotte.out"))
        if d:
            self.out_var.set(d)

    def _log(self, msg: str):
        self.log_txt.configure(state=NORMAL)
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_txt.insert(END, f"[{ts}] {msg}\n")
        self.log_txt.see(END)
        self.log_txt.configure(state=DISABLED)

    def _start(self):
        if not _REQUESTS_OK:
            messagebox.showerror("Thiếu thư viện",
                                 "Vui lòng cài:\n  pip install requests")
            return
        if not _CV2_OK:
            messagebox.showerror("Thiếu thư viện",
                                 "Vui lòng cài:\n  pip install opencv-python numpy")
            return
        from_d = self.from_var.get().strip()
        to_d   = self.to_var.get().strip()
        out    = self.out_var.get().strip()
        if not from_d or not to_d or not out:
            messagebox.showerror("Thiếu thông tin",
                                 "Vui lòng điền đủ thời gian và thư mục.")
            return
        try:
            os.makedirs(out, exist_ok=True)
        except Exception as e:
            messagebox.showerror("Lỗi thư mục", str(e))
            return
        cfg = {
            "from_date":    from_d,
            "to_date":      to_d,
            "output_dir":   out,
            "page_size":    self.page_size_var.get(),
            "max_pages":    self.max_pages_var.get(),
            "sleep":        self.sleep_var.get(),
            "use_minio":    self.use_minio.get(),
            "api_base":     self.cfg_api.get().strip(),
            "username":     self.cfg_user.get().strip(),
            "password":     self.cfg_pass.get().strip(),
            "minio_ep":     self.cfg_mep.get().strip(),
            "minio_bucket": self.cfg_mbk.get().strip(),
            "minio_ak":     self.cfg_mak.get().strip(),
            "minio_sk":     self.cfg_msk.get().strip(),
        }
        self.start_btn.config(state=DISABLED)
        self.stop_btn.config(state=NORMAL)
        self.pbar.start(12)
        self.status_lbl.config(text="Đang chạy...", fg=ACCENT)
        self._log(f"Bắt đầu: {from_d}  →  {to_d}")
        self._log(f"Lưu vào: {out}")
        self._worker = LotteWorker(cfg, self._log_q, self._stat_q)
        self._thread = threading.Thread(target=self._run_worker, daemon=True)
        self._thread.start()

    def _run_worker(self):
        try:
            self._worker.run()
        except Exception as exc:
            self._log_q.put(f"[LỖI] {exc}")
            self._log_q.put("__DONE__")

    def _stop(self):
        if self._worker:
            self._worker.stop()
        self.stop_btn.config(state=DISABLED)
        self.status_lbl.config(text="Đang dừng...", fg=DIM)

    def _on_done(self):
        self.pbar.stop()
        self.start_btn.config(state=NORMAL)
        self.stop_btn.config(state=DISABLED)
        self.status_lbl.config(text="Hoàn thành", fg=ACCENT2)

    # ── poll (main-thread queue drain) ─────────────────────────────────────────

    def _poll(self):
        try:
            while True:
                msg = self._log_q.get_nowait()
                if msg == "__DONE__":
                    self._on_done()
                else:
                    self._log(msg)
        except queue.Empty:
            pass
        try:
            while True:
                s = self._stat_q.get_nowait()
                day_info = (
                    f"Ngày: {s['day_label']} ({s['day_idx']}/{s['total_days']})  |  "
                    if s.get("total_days") else "")
                self.stat_lbl.config(
                    text=(f"{day_info}"
                          f"Trang: {s['page']}  |  "
                          f"Sự kiện: {s['event']}  |  "
                          f"Lưu: {s['saved']}  |  "
                          f"Lỗi: {s['error']}"))
        except queue.Empty:
            pass
        self.root.after(200, self._poll)


# ── Tab 8: BBox Editor ────────────────────────────────────────────────────────

class BBoxEditorTab(Frame):
    """Hiệu chỉnh bounding box – vẽ / sửa / xóa bbox, lưu YOLO .txt"""

    _PALETTE = [
        "#F05922", "#4caf50", "#2196f3", "#9c27b0", "#ff9800",
        "#00bcd4", "#e91e63", "#8bc34a", "#ff5722", "#607d8b",
        "#ffeb3b", "#3f51b5", "#009688", "#795548", "#f44336",
    ]

    def __init__(self, master, root):
        super().__init__(master, bg=BG)
        self.root = root

        self.img_dir_var  = StringVar()
        self.lbl_dir_var  = StringVar()
        self._labels_var  = StringVar(
            value="car,motorcycle,bus,truck,bicycle,license_plate")
        self.v_recursive  = BooleanVar(value=False)
        _bind_cfg("bbox.img",    self.img_dir_var)
        _bind_cfg("bbox.lbl",    self.lbl_dir_var)
        _bind_cfg("bbox.labels", self._labels_var)

        self.label_list   = []   # list[str]  class names
        self.image_files  = []   # list[Path]
        self.current_idx  = -1

        self._pil_img     = None
        self._tk_img      = None
        self._scale       = 1.0
        self._off_x       = 0
        self._off_y       = 0

        # bboxes: list of [class_id:int, x1:float, y1:float, x2:float, y2:float]
        # all coords are in *original image pixels*
        self._bboxes      = []
        self._selected    = -1
        self._modified    = False

        self._mode        = StringVar(value="draw")
        self._drawing     = False
        self._draw_start  = (0, 0)
        self._draw_rect   = None
        self._resize_after = None

        # drag / resize state (select mode)
        self._drag_op        = None   # None | "move" | "resize_*"
        self._drag_prev      = (0, 0)
        self._drag_press_pos = (0, 0)  # canvas pos at mouse-down
        self._drag_committed = True    # False → threshold not yet reached

        self._build()

    # ── build ─────────────────────────────────────────────────────────────────

    def _build(self):
        from PIL import Image, ImageTk
        self._PIL_Image = Image
        self._PIL_ImageTk = ImageTk

        # ── top: folder / label inputs ──
        top = Frame(self, bg=CARD, padx=12, pady=10)
        top.pack(fill=X)
        grid = Frame(top, bg=CARD)
        grid.pack(fill=X)

        _folder_row(grid, "Thư mục ảnh :", self.img_dir_var, 0, bg=CARD)
        _folder_row(grid, "Thư mục label:", self.lbl_dir_var, 1, bg=CARD)

        Label(grid, text="Danh sách nhãn:", bg=CARD, fg=DIM,
              font=F_MAIN, width=26, anchor=W).grid(
                  row=2, column=0, sticky=W, pady=5)
        Entry(grid, textvariable=self._labels_var, bg=CARD, fg=TEXT,
              insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4).grid(
                  row=2, column=1, sticky=EW, padx=(8, 8))
        lbl_btn_row = Frame(grid, bg=CARD)
        lbl_btn_row.grid(row=2, column=2, sticky=W)
        Checkbutton(lbl_btn_row, text="Đệ quy subfolder",
                    variable=self.v_recursive,
                    bg=CARD, fg=TEXT, selectcolor="#16162a",
                    activebackground=CARD, font=F_MAIN).pack(side=LEFT, padx=(0, 8))
        Button(lbl_btn_row, text="  ▶  Tải ảnh",
               command=self._load_dataset,
               bg=ACCENT, fg="white", activebackground="#c04010",
               activeforeground="white", font=F_BOLD,
               relief="flat", padx=14, cursor="hand2").pack(side=LEFT)

        # ── main: left list  |  center canvas ──
        main = Frame(self, bg=BG)
        main.pack(fill=BOTH, expand=True, padx=8, pady=6)

        # ── left panel ──
        left = Frame(main, bg=CARD, width=200)
        left.pack(side=LEFT, fill=Y, padx=(0, 6))
        left.pack_propagate(False)

        Label(left, text="Danh sách ảnh", bg=CARD, fg=TEXT,
              font=F_BOLD).pack(pady=(8, 2), padx=8, anchor=W)
        self._lbl_imgcount = Label(left, text="—", bg=CARD, fg=DIM, font=F_MAIN)
        self._lbl_imgcount.pack(padx=8, anchor=W)

        lf = Frame(left, bg=CARD)
        lf.pack(fill=BOTH, expand=True, padx=6, pady=(4, 0))
        self._img_lb = Listbox(lf, bg="#16162a", fg=TEXT,
                               selectbackground=ACCENT2, selectforeground="white",
                               font=F_MONO, relief="flat", bd=0, activestyle="none")
        sb_lb = Scrollbar(lf, command=self._img_lb.yview)
        self._img_lb.configure(yscrollcommand=sb_lb.set)
        sb_lb.pack(side=RIGHT, fill=Y)
        self._img_lb.pack(fill=BOTH, expand=True)
        self._img_lb.bind("<<ListboxSelect>>", self._on_list_select)

        nav = Frame(left, bg=CARD)
        nav.pack(fill=X, padx=6, pady=4)
        Button(nav, text="◀", command=self._prev_img,
               bg=ACCENT2, fg="white", font=F_BOLD,
               relief="flat", cursor="hand2", width=5).pack(side=LEFT)
        Button(nav, text="▶", command=self._next_img,
               bg=ACCENT2, fg="white", font=F_BOLD,
               relief="flat", cursor="hand2", width=5).pack(side=LEFT, padx=(4, 0))

        Label(left, text="Nhãn (class)", bg=CARD, fg=TEXT,
              font=F_BOLD).pack(pady=(8, 2), padx=8, anchor=W)
        self._cls_lb = Listbox(left, bg="#16162a", fg=TEXT,
                               selectbackground=ACCENT2, selectforeground="white",
                               font=F_MONO, relief="flat", bd=0,
                               activestyle="none", height=10, exportselection=False)
        self._cls_lb.pack(fill=X, padx=6, pady=(0, 6))
        self._cls_lb.bind("<<ListboxSelect>>", self._on_cls_select)

        # ── center ──
        center = Frame(main, bg=BG)
        center.pack(side=LEFT, fill=BOTH, expand=True)

        # toolbar
        tb = Frame(center, bg=CARD, pady=5, padx=8)
        tb.pack(fill=X)

        Label(tb, text="Chế độ:", bg=CARD, fg=DIM, font=F_MAIN).pack(
            side=LEFT, padx=(0, 4))
        for txt, val in [("✏ Vẽ bbox", "draw"), ("🖱 Chọn / sửa", "select")]:
            Radiobutton(tb, text=txt, variable=self._mode, value=val,
                        bg=CARD, fg=TEXT, selectcolor=ACCENT2,
                        activebackground=CARD, font=F_MAIN).pack(side=LEFT, padx=4)

        Frame(tb, bg=DIM, width=1).pack(side=LEFT, fill=Y, padx=8)

        Label(tb, text="Nhãn:", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        self._cls_combo = ttk.Combobox(tb, width=18, state="readonly", font=F_MAIN)
        self._cls_combo.pack(side=LEFT, padx=(4, 6))

        Button(tb, text="🏷 Đặt nhãn", command=self._relabel_selected,
               bg=ACCENT2, fg="white", activebackground=ACCENT,
               activeforeground="white", font=F_MAIN,
               relief="flat", padx=8, cursor="hand2").pack(side=LEFT, padx=2)
        Button(tb, text="🗑 Xóa bbox (Del)", command=self._delete_selected,
               bg="#c62828", fg="white", activebackground="#8b0000",
               activeforeground="white", font=F_MAIN,
               relief="flat", padx=8, cursor="hand2").pack(side=LEFT, padx=2)

        Frame(tb, bg=DIM, width=1).pack(side=LEFT, fill=Y, padx=8)

        Button(tb, text="💾 Lưu label (Ctrl+S)", command=self._save_labels,
               bg="#2e7d32", fg="white", activebackground="#1b5e20",
               activeforeground="white", font=F_BOLD,
               relief="flat", padx=10, cursor="hand2").pack(side=LEFT, padx=2)

        self._info_lbl = Label(tb, text="", bg=CARD, fg=DIM, font=F_MAIN)
        self._info_lbl.pack(side=RIGHT, padx=8)

        # canvas
        cf = Frame(center, bg="#111122", relief=SUNKEN, bd=1)
        cf.pack(fill=BOTH, expand=True, pady=(6, 0))
        self._canvas = Canvas(cf, bg="#111122", cursor="crosshair",
                              highlightthickness=0)
        self._canvas.pack(fill=BOTH, expand=True)

        self._canvas.bind("<ButtonPress-1>",  self._on_press)
        self._canvas.bind("<B1-Motion>",      self._on_drag)
        self._canvas.bind("<ButtonRelease-1>",self._on_release)
        self._canvas.bind("<Motion>",         self._on_hover)
        self._canvas.bind("<Configure>",      self._on_canvas_cfg)

        # keyboard — bind on canvas so it doesn't steal from other tabs
        self._canvas.bind("<Delete>",         lambda e: self._delete_selected())
        self._canvas.bind("<Control-s>",      lambda e: self._save_labels())
        self._canvas.bind("<Left>",           lambda e: self._prev_img())
        self._canvas.bind("<Right>",          lambda e: self._next_img())

        # status bar
        self._status = Label(center,
            text="Chọn thư mục ảnh và label, nhập danh sách nhãn rồi nhấn Tải ảnh",
            bg=BG, fg=DIM, font=F_MAIN, anchor=W)
        self._status.pack(fill=X, pady=(4, 0))

    # ── dataset loading ───────────────────────────────────────────────────────

    def _parse_label_list(self):
        raw = self._labels_var.get().strip()
        return [s.strip() for s in raw.replace("\n", ",").split(",") if s.strip()]

    def _load_dataset(self):
        self.label_list = self._parse_label_list()
        if not self.label_list:
            messagebox.showerror("Lỗi", "Vui lòng nhập danh sách nhãn (cách nhau bởi dấu phẩy).")
            return
        img_dir = self.img_dir_var.get().strip()
        if not img_dir or not os.path.isdir(img_dir):
            messagebox.showerror("Lỗi", "Vui lòng chọn thư mục ảnh hợp lệ.")
            return

        img_root = Path(img_dir)
        if self.v_recursive.get():
            self.image_files = sorted(
                p for p in img_root.rglob("*")
                if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
            )
        else:
            self.image_files = sorted(
                p for p in img_root.iterdir()
                if p.suffix.lower() in IMAGE_EXTENSIONS
            )

        self._img_lb.delete(0, END)
        for p in self.image_files:
            display = str(p.relative_to(img_root)) if self.v_recursive.get() else p.name
            self._img_lb.insert(END, display)
        self._lbl_imgcount.config(text=f"{len(self.image_files)} ảnh")

        # class list + combo
        self._cls_lb.delete(0, END)
        combo_vals = []
        for i, name in enumerate(self.label_list):
            color = self._PALETTE[i % len(self._PALETTE)]
            self._cls_lb.insert(END, f"  [{i}]  {name}")
            self._cls_lb.itemconfig(END, fg=color)
            combo_vals.append(f"{i}: {name}")
        self._cls_combo["values"] = combo_vals
        if combo_vals:
            self._cls_combo.current(0)

        if self.image_files:
            self.current_idx = 0
            self._img_lb.selection_set(0)
            self._load_image(0)

        self._status.config(
            text=f"Đã tải {len(self.image_files)} ảnh  |  {len(self.label_list)} nhãn")

    def _on_list_select(self, _event):
        sel = self._img_lb.curselection()
        if not sel or sel[0] == self.current_idx:
            return
        self._autosave()
        self._load_image(sel[0])

    def _on_cls_select(self, _event):
        sel = self._cls_lb.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx < len(self._cls_combo["values"]):
            self._cls_combo.current(idx)

    def _load_image(self, idx):
        self.current_idx = idx
        fp = self.image_files[idx]
        try:
            self._pil_img = self._PIL_Image.open(fp).convert("RGB")
        except Exception as e:
            self._status.config(text=f"Lỗi mở ảnh: {e}")
            return

        self._bboxes   = []
        self._selected = -1
        self._modified = False

        lbl_dir = self.lbl_dir_var.get().strip()
        lbl_path = (Path(lbl_dir) / (fp.stem + ".txt")
                    if lbl_dir else fp.parent / (fp.stem + ".txt"))
        if lbl_path.exists():
            self._bboxes = self._read_yolo(lbl_path)

        self._render()
        iw, ih = self._pil_img.size
        n = len(self._bboxes)
        self._status.config(
            text=f"{fp.name}   {iw}×{ih}   |   {n} bbox")

    # ── YOLO I/O ──────────────────────────────────────────────────────────────

    def _read_yolo(self, path):
        iw, ih = self._pil_img.size
        bboxes = []
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    p = line.strip().split()
                    if len(p) < 5:
                        continue
                    cid = int(p[0])
                    xc, yc, w, h = map(float, p[1:5])
                    x1 = (xc - w / 2) * iw
                    y1 = (yc - h / 2) * ih
                    x2 = (xc + w / 2) * iw
                    y2 = (yc + h / 2) * ih
                    bboxes.append([cid, x1, y1, x2, y2])
        except Exception:
            pass
        return bboxes

    def _write_yolo(self, path):
        iw, ih = self._pil_img.size
        lines = []
        for cid, x1, y1, x2, y2 in self._bboxes:
            xc = ((x1 + x2) / 2) / iw
            yc = ((y1 + y2) / 2) / ih
            bw  = (x2 - x1) / iw
            bh  = (y2 - y1) / ih
            xc  = max(0.0, min(1.0, xc))
            yc  = max(0.0, min(1.0, yc))
            bw  = max(1e-4, min(1.0, bw))
            bh  = max(1e-4, min(1.0, bh))
            lines.append(f"{int(cid)} {xc:.6f} {yc:.6f} {bw:.6f} {bh:.6f}")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    # ── rendering ─────────────────────────────────────────────────────────────

    def _render(self):
        if self._pil_img is None:
            return
        self._canvas.update_idletasks()
        cw = self._canvas.winfo_width()
        ch = self._canvas.winfo_height()
        if cw < 10 or ch < 10:
            self._canvas.after(80, self._render)
            return

        iw, ih = self._pil_img.size
        scale  = min(cw / iw, ch / ih, 1.0)
        nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
        self._scale = scale
        self._off_x = (cw - nw) // 2
        self._off_y = (ch - nh) // 2

        resized      = self._pil_img.resize((nw, nh), self._PIL_Image.LANCZOS)
        self._tk_img = self._PIL_ImageTk.PhotoImage(resized)

        self._canvas.delete("all")
        self._canvas.create_image(self._off_x, self._off_y,
                                  anchor=NW, image=self._tk_img)
        self._draw_all_bboxes()

    def _draw_all_bboxes(self):
        for i, (cid, x1, y1, x2, y2) in enumerate(self._bboxes):
            cx1 = int(x1 * self._scale) + self._off_x
            cy1 = int(y1 * self._scale) + self._off_y
            cx2 = int(x2 * self._scale) + self._off_x
            cy2 = int(y2 * self._scale) + self._off_y

            color    = self._PALETTE[cid % len(self._PALETTE)]
            selected = (i == self._selected)
            lw       = 3 if selected else 2
            dash     = () if selected else (5, 3)
            tag      = f"bb{i}"

            self._canvas.create_rectangle(cx1, cy1, cx2, cy2,
                                          outline=color, width=lw,
                                          dash=dash, tags=tag)

            cls_name  = (self.label_list[cid]
                         if cid < len(self.label_list) else str(cid))
            txt       = f" {cid}:{cls_name} "
            txt_w     = max(len(txt) * 7, 30)
            self._canvas.create_rectangle(cx1, cy1 - 17,
                                          cx1 + txt_w, cy1,
                                          fill=color, outline="", tags=tag)
            self._canvas.create_text(cx1 + 3, cy1 - 8, text=txt,
                                     fill="white",
                                     font=("Segoe UI", 8, "bold"),
                                     anchor=W, tags=tag)

            if selected:
                hw = 7
                mx = (cx1 + cx2) // 2
                my = (cy1 + cy2) // 2
                # corner handles (square)
                for hx, hy in [(cx1, cy1), (cx2, cy1), (cx1, cy2), (cx2, cy2)]:
                    self._canvas.create_rectangle(
                        hx - hw, hy - hw, hx + hw, hy + hw,
                        fill=color, outline="white", width=1, tags=tag)
                # edge handles (flat rectangle: wide for N/S, tall for W/E)
                for hx, hy, fw, fh in [
                    (mx, cy1, hw + 3, hw - 3),   # N
                    (mx, cy2, hw + 3, hw - 3),   # S
                    (cx1, my, hw - 3, hw + 3),   # W
                    (cx2, my, hw - 3, hw + 3),   # E
                ]:
                    self._canvas.create_rectangle(
                        hx - fw, hy - fh, hx + fw, hy + fh,
                        fill=color, outline="white", width=1, tags=tag)

    def _on_canvas_cfg(self, _event):
        if self._resize_after:
            self._canvas.after_cancel(self._resize_after)
        self._resize_after = self._canvas.after(120, self._render)

    # ── mouse interaction ─────────────────────────────────────────────────────

    def _img_coords(self, cx, cy):
        return ((cx - self._off_x) / self._scale,
                (cy - self._off_y) / self._scale)

    def _hit_test(self, cx, cy):
        for i in range(len(self._bboxes) - 1, -1, -1):
            _, x1, y1, x2, y2 = self._bboxes[i]
            bx1 = int(x1 * self._scale) + self._off_x
            by1 = int(y1 * self._scale) + self._off_y
            bx2 = int(x2 * self._scale) + self._off_x
            by2 = int(y2 * self._scale) + self._off_y
            if bx1 <= cx <= bx2 and by1 <= cy <= by2:
                return i
        return -1

    def _hit_test_all(self, cx, cy):
        """All bbox indices containing (cx,cy), ordered bottom→top (last = topmost)."""
        hits = []
        for i, (_, x1, y1, x2, y2) in enumerate(self._bboxes):
            bx1 = int(x1 * self._scale) + self._off_x
            by1 = int(y1 * self._scale) + self._off_y
            bx2 = int(x2 * self._scale) + self._off_x
            by2 = int(y2 * self._scale) + self._off_y
            if bx1 <= cx <= bx2 and by1 <= cy <= by2:
                hits.append(i)
        return hits

    def _cycle_at(self, cx, cy):
        """Cycle selection through all overlapping boxes at (cx,cy)."""
        hits = self._hit_test_all(cx, cy)
        if not hits:
            self._selected = -1
        elif self._selected in hits:
            pos = hits.index(self._selected)
            self._selected = hits[(pos - 1) % len(hits)]
        else:
            self._selected = hits[-1]
        self._render()
        if self._selected >= 0:
            cid  = self._bboxes[self._selected][0]
            name = (self.label_list[cid]
                    if cid < len(self.label_list) else str(cid))
            self._info_lbl.config(text=f"Đã chọn  [{cid}:{name}]")
            vals = list(self._cls_combo["values"])
            for k, v in enumerate(vals):
                if v.startswith(f"{cid}:"):
                    self._cls_combo.current(k)
                    break
        else:
            self._info_lbl.config(text="")

    _HIT_R = 9  # handle hit radius in canvas pixels

    def _handle_hit(self, cx, cy, idx):
        """Return resize op name if (cx,cy) is near a handle, else None.
        Corners are checked before edges so they take priority where they overlap."""
        _, x1, y1, x2, y2 = self._bboxes[idx]
        bx1 = int(x1 * self._scale) + self._off_x
        by1 = int(y1 * self._scale) + self._off_y
        bx2 = int(x2 * self._scale) + self._off_x
        by2 = int(y2 * self._scale) + self._off_y
        mx  = (bx1 + bx2) // 2
        my  = (by1 + by2) // 2
        r   = self._HIT_R
        # corners first
        for op, (hx, hy) in [
            ("resize_NW", (bx1, by1)), ("resize_NE", (bx2, by1)),
            ("resize_SW", (bx1, by2)), ("resize_SE", (bx2, by2)),
        ]:
            if abs(cx - hx) <= r and abs(cy - hy) <= r:
                return op
        # edge midpoints
        for op, (hx, hy) in [
            ("resize_N", (mx,  by1)), ("resize_S", (mx,  by2)),
            ("resize_W", (bx1, my)), ("resize_E", (bx2, my)),
        ]:
            if abs(cx - hx) <= r and abs(cy - hy) <= r:
                return op
        return None

    def _on_hover(self, event):
        if self._mode.get() != "select" or self._selected < 0:
            self._canvas.config(cursor="crosshair")
            return
        op = self._handle_hit(event.x, event.y, self._selected)
        if op in ("resize_NW", "resize_SE"):
            self._canvas.config(cursor="size_nw_se")
        elif op in ("resize_NE", "resize_SW"):
            self._canvas.config(cursor="size_ne_sw")
        elif op in ("resize_N", "resize_S"):
            self._canvas.config(cursor="sb_v_double_arrow")
        elif op in ("resize_W", "resize_E"):
            self._canvas.config(cursor="sb_h_double_arrow")
        else:
            _, x1, y1, x2, y2 = self._bboxes[self._selected]
            bx1 = int(x1 * self._scale) + self._off_x
            by1 = int(y1 * self._scale) + self._off_y
            bx2 = int(x2 * self._scale) + self._off_x
            by2 = int(y2 * self._scale) + self._off_y
            if bx1 <= event.x <= bx2 and by1 <= event.y <= by2:
                self._canvas.config(cursor="fleur")
            else:
                self._canvas.config(cursor="crosshair")

    def _on_press(self, event):
        if self._pil_img is None:
            return
        self._canvas.focus_set()
        cx, cy = event.x, event.y

        if self._mode.get() == "select":
            # 1. corner/edge handle → resize (commits immediately, no threshold)
            if self._selected >= 0:
                op = self._handle_hit(cx, cy, self._selected)
                if op:
                    self._drag_op        = op
                    self._drag_prev      = (cx, cy)
                    self._drag_committed = True
                    return

            # 2. inside selected bbox → potential move (wait for drag threshold)
            #    Pure click (no drag) will cycle to underlying box in _on_release
            if self._selected >= 0:
                _, x1, y1, x2, y2 = self._bboxes[self._selected]
                bx1 = int(x1 * self._scale) + self._off_x
                by1 = int(y1 * self._scale) + self._off_y
                bx2 = int(x2 * self._scale) + self._off_x
                by2 = int(y2 * self._scale) + self._off_y
                if bx1 <= cx <= bx2 and by1 <= cy <= by2:
                    self._drag_op        = "move"
                    self._drag_press_pos = (cx, cy)
                    self._drag_prev      = (cx, cy)
                    self._drag_committed = False
                    return

            # 3. click elsewhere → select topmost box at this point
            hits = self._hit_test_all(cx, cy)
            if hits:
                self._selected = hits[-1]
                self._drag_op        = "move"
                self._drag_press_pos = (cx, cy)
                self._drag_prev      = (cx, cy)
                self._drag_committed = True   # new selection: can drag immediately
            else:
                self._selected = -1
                self._drag_op  = None
            self._render()
            if self._selected >= 0:
                cid  = self._bboxes[self._selected][0]
                name = (self.label_list[cid]
                        if cid < len(self.label_list) else str(cid))
                self._info_lbl.config(text=f"Đã chọn  [{cid}:{name}]")
                vals = list(self._cls_combo["values"])
                for k, v in enumerate(vals):
                    if v.startswith(f"{cid}:"):
                        self._cls_combo.current(k)
                        break
            else:
                self._info_lbl.config(text="")
        else:
            self._drawing    = True
            self._draw_start = (cx, cy)
            self._draw_rect  = self._canvas.create_rectangle(
                cx, cy, cx, cy, outline=ACCENT, width=2, dash=(4, 2))

    _DRAG_THRESHOLD = 5  # canvas pixels before a "move" is committed

    def _on_drag(self, event):
        if self._drag_op and self._selected >= 0:
            cx, cy = event.x, event.y
            if not self._drag_committed:
                px0, py0 = self._drag_press_pos
                if ((cx - px0) ** 2 + (cy - py0) ** 2) ** 0.5 < self._DRAG_THRESHOLD:
                    return
                self._drag_committed = True
                self._drag_prev = (cx, cy)
                return
            px, py = self._drag_prev
            dx = (cx - px) / self._scale
            dy = (cy - py) / self._scale
            self._drag_prev = (cx, cy)
            self._apply_drag(dx, dy)
        elif self._drawing and self._draw_rect:
            x0, y0 = self._draw_start
            self._canvas.coords(self._draw_rect, x0, y0, event.x, event.y)

    def _apply_drag(self, dx, dy):
        bb = self._bboxes[self._selected]
        iw, ih = self._pil_img.size
        op = self._drag_op

        if op == "move":
            w = bb[3] - bb[1];  h = bb[4] - bb[2]
            nx1 = max(0.0, min(float(iw) - w, bb[1] + dx))
            ny1 = max(0.0, min(float(ih) - h, bb[2] + dy))
            bb[1] = nx1;  bb[2] = ny1
            bb[3] = nx1 + w;  bb[4] = ny1 + h
        elif op == "resize_NW":
            bb[1] = max(0.0,        min(bb[3] - 1.0, bb[1] + dx))
            bb[2] = max(0.0,        min(bb[4] - 1.0, bb[2] + dy))
        elif op == "resize_NE":
            bb[3] = min(float(iw),  max(bb[1] + 1.0, bb[3] + dx))
            bb[2] = max(0.0,        min(bb[4] - 1.0, bb[2] + dy))
        elif op == "resize_SW":
            bb[1] = max(0.0,        min(bb[3] - 1.0, bb[1] + dx))
            bb[4] = min(float(ih),  max(bb[2] + 1.0, bb[4] + dy))
        elif op == "resize_SE":
            bb[3] = min(float(iw),  max(bb[1] + 1.0, bb[3] + dx))
            bb[4] = min(float(ih),  max(bb[2] + 1.0, bb[4] + dy))
        elif op == "resize_N":
            bb[2] = max(0.0,        min(bb[4] - 1.0, bb[2] + dy))
        elif op == "resize_S":
            bb[4] = min(float(ih),  max(bb[2] + 1.0, bb[4] + dy))
        elif op == "resize_W":
            bb[1] = max(0.0,        min(bb[3] - 1.0, bb[1] + dx))
        elif op == "resize_E":
            bb[3] = min(float(iw),  max(bb[1] + 1.0, bb[3] + dx))

        self._modified = True
        self._render()

    def _on_release(self, event):
        if self._drag_op is not None:
            was_committed = self._drag_committed
            self._drag_op        = None
            self._drag_committed = True
            if not was_committed:
                # Pure click (no drag) → cycle through overlapping boxes
                self._cycle_at(event.x, event.y)
            return

        if not self._drawing:
            return
        self._drawing = False
        if self._draw_rect:
            self._canvas.delete(self._draw_rect)
            self._draw_rect = None

        x0, y0 = self._draw_start
        x1c = min(x0, event.x);  y1c = min(y0, event.y)
        x2c = max(x0, event.x);  y2c = max(y0, event.y)
        if (x2c - x1c) < 5 or (y2c - y1c) < 5:
            return

        iw, ih = self._pil_img.size
        ix1, iy1 = self._img_coords(x1c, y1c)
        ix2, iy2 = self._img_coords(x2c, y2c)
        ix1 = max(0.0, min(float(iw), ix1))
        iy1 = max(0.0, min(float(ih), iy1))
        ix2 = max(0.0, min(float(iw), ix2))
        iy2 = max(0.0, min(float(ih), iy2))
        if ix2 <= ix1 or iy2 <= iy1:
            return

        cid  = self._current_class_id()
        self._bboxes.append([cid, ix1, iy1, ix2, iy2])
        self._selected = len(self._bboxes) - 1
        self._modified = True
        self._render()
        name = (self.label_list[cid]
                if cid < len(self.label_list) else str(cid))
        self._status.config(
            text=f"Đã vẽ bbox  [{cid}:{name}]  |  {len(self._bboxes)} bbox tổng")

    # ── actions ───────────────────────────────────────────────────────────────

    def _current_class_id(self):
        val = self._cls_combo.get()
        if val and ":" in val:
            try:
                return int(val.split(":")[0])
            except ValueError:
                pass
        return 0

    def _relabel_selected(self):
        if self._selected < 0 or not self._bboxes:
            self._status.config(text="⚠  Chưa chọn bbox — dùng chế độ 'Chọn / sửa' rồi click vào bbox")
            return
        cid = self._current_class_id()
        self._bboxes[self._selected][0] = cid
        self._modified = True
        self._render()
        name = (self.label_list[cid]
                if cid < len(self.label_list) else str(cid))
        self._status.config(
            text=f"Đã đặt nhãn  [{cid}:{name}]  cho bbox #{self._selected}")

    def _delete_selected(self):
        if self._selected < 0 or not self._bboxes:
            return
        self._bboxes.pop(self._selected)
        self._selected = -1
        self._modified = True
        self._render()
        self._status.config(
            text=f"Đã xóa bbox  |  {len(self._bboxes)} bbox còn lại")

    def _save_labels(self):
        if not self.image_files or self.current_idx < 0 or self._pil_img is None:
            return
        fp = self.image_files[self.current_idx]
        lbl_dir = self.lbl_dir_var.get().strip()
        lbl_path = (Path(lbl_dir) / (fp.stem + ".txt")
                    if lbl_dir else fp.parent / (fp.stem + ".txt"))
        try:
            self._write_yolo(lbl_path)
            self._modified = False
            self._status.config(
                text=f"✔  Đã lưu: {lbl_path}  |  {len(self._bboxes)} bbox")
        except Exception as e:
            messagebox.showerror("Lỗi lưu file", str(e))

    def _autosave(self):
        if self._modified:
            self._save_labels()

    def _prev_img(self):
        if not self.image_files or self.current_idx <= 0:
            return
        self._autosave()
        new_idx = self.current_idx - 1
        self._img_lb.selection_clear(0, END)
        self._img_lb.selection_set(new_idx)
        self._img_lb.see(new_idx)
        self._load_image(new_idx)

    def _next_img(self):
        if not self.image_files or self.current_idx >= len(self.image_files) - 1:
            return
        self._autosave()
        new_idx = self.current_idx + 1
        self._img_lb.selection_clear(0, END)
        self._img_lb.selection_set(new_idx)
        self._img_lb.see(new_idx)
        self._load_image(new_idx)


# ── Tab 8: Label Norm ─────────────────────────────────────────────────────────

class LabelNormTab(Frame):
    def __init__(self, master, root):
        super().__init__(master, bg=BG)
        self.root = root
        self._stop_event = threading.Event()
        self._class_vars = {}
        self._build()

    def _build(self):
        top = Frame(self, bg=BG, padx=20, pady=10)
        top.pack(fill=X)
        self.v_img = StringVar()
        self.v_lbl = StringVar()
        self.v_out = StringVar()
        _bind_cfg("labelnorm.img",     self.v_img)
        _bind_cfg("labelnorm.lbl",     self.v_lbl)
        _bind_cfg("labelnorm.out",     self.v_out)
        _folder_row(top, "📁  Thư mục ảnh",         self.v_img, 0)
        _folder_row(top, "🏷  Thư mục label (.txt)", self.v_lbl, 1)
        _folder_row(top, "💾  Thư mục output",       self.v_out, 2)

        cr = Frame(top, bg=BG)
        cr.grid(row=3, column=0, columnspan=3, sticky=EW, pady=(6, 0))
        Label(cr, text="Danh sách nhãn:", bg=BG, fg=DIM,
              font=F_MAIN, width=26, anchor=W).pack(side=LEFT)
        self.v_classes = StringVar(
            value="car, motorbike, bus, truck, bicycle, license_plate")
        _bind_cfg("labelnorm.classes", self.v_classes)
        Entry(cr, textvariable=self.v_classes, bg=CARD, fg=TEXT,
              insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4).pack(
              side=LEFT, fill=X, expand=True, padx=(8, 0))
        Button(cr, text="Cập nhật ↺", command=self._refresh_classes,
               bg=ACCENT2, fg="white", activebackground=ACCENT,
               activeforeground="white", font=F_MAIN, relief="flat",
               padx=10, cursor="hand2").pack(side=LEFT, padx=(6, 0))

        mid = Frame(self, bg=BG, padx=20)
        mid.pack(fill=X, pady=(0, 2))
        mid.columnconfigure(0, weight=3)
        mid.columnconfigure(1, weight=2)

        flt = LabelFrame(mid, text=" Điều kiện lọc ",
                         bg=BG, fg=TEXT, font=F_BOLD, bd=1, relief="groove")
        flt.grid(row=0, column=0, sticky=NSEW, padx=(0, 8), pady=4)
        self._build_filters(flt)

        out_f = LabelFrame(mid, text=" Chia subfolder output ",
                           bg=BG, fg=TEXT, font=F_BOLD, bd=1, relief="groove")
        out_f.grid(row=0, column=1, sticky=NSEW, pady=4)
        self._build_split_opts(out_f)

        # Tạo widgets trước, pack theo đúng thứ tự để btn luôn hiển thị
        btn_row = Frame(self, bg=BG, padx=20, pady=6)
        self.btn_run = _action_btn(btn_row, "▶  Bắt đầu", self._run, ACCENT,
                                   padx=20, pady=7)
        self.btn_run.pack(side=LEFT)
        self.btn_stop = _action_btn(btn_row, "⏹  Dừng", self._stop, "#c0392b",
                                    padx=14, pady=7)
        self.btn_stop.pack(side=LEFT, padx=(8, 0))
        self.btn_stop.config(state=DISABLED)
        _action_btn(btn_row, "🔄  Xóa tiến độ", self._reset_state, ACCENT2,
                    padx=14, pady=7).pack(side=LEFT, padx=(8, 0))
        _action_btn(btn_row, "📂  Mở output", self._open_out, ACCENT2,
                    padx=14, pady=7).pack(side=LEFT, padx=(8, 0))
        Button(btn_row, text="🧹  Xóa log",
               command=lambda: (self.log.configure(state=NORMAL),
                                self.log.delete("1.0", END),
                                self.log.configure(state=DISABLED)),
               bg=CARD, fg=DIM, font=F_MAIN, relief="flat",
               padx=14, pady=7, cursor="hand2").pack(side=RIGHT)

        pb_f = Frame(self, bg=BG, padx=20)
        self.pb_lbl, self.pb = _pb_row(pb_f)

        log_outer = Frame(self, bg=BG, padx=20)
        log_f, self.log = _make_logbox(log_outer)
        log_f.pack(fill=BOTH, expand=True)

        # Pack BOTTOM trước để chốt vị trí, log lấy phần còn lại
        btn_row.pack(fill=X, side=BOTTOM)
        pb_f.pack(fill=X, side=BOTTOM)
        log_outer.pack(fill=BOTH, expand=True)

    def _build_filters(self, p):
        def _cb(text, var, row, col=0, span=1):
            Checkbutton(p, text=text, variable=var, bg=BG, fg=TEXT,
                        activebackground=BG, activeforeground=TEXT,
                        selectcolor=CARD, font=F_MAIN).grid(
                            row=row, column=col, columnspan=span,
                            sticky=W, padx=10, pady=2)

        def _ent(parent, var, w=6):
            return Entry(parent, textvariable=var, width=w, bg=CARD, fg=TEXT,
                         insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4)

        def _lbl(text, row, col, dim=True):
            Label(p, text=text, bg=BG, fg=DIM if dim else TEXT,
                  font=F_MAIN).grid(row=row, column=col, sticky=W, padx=4)

        r = 0
        Label(p, text="Nhãn lớp cần giữ:", bg=BG, fg=DIM, font=F_MAIN).grid(
            row=r, column=0, columnspan=4, sticky=W, padx=10, pady=(8, 2))
        r += 1
        self._class_frame = Frame(p, bg=BG)
        self._class_frame.grid(row=r, column=0, columnspan=4, sticky=W, padx=12, pady=(0, 4))
        r += 1
        Frame(p, bg=CARD, height=1).grid(row=r, column=0, columnspan=4,
                                          sticky=EW, padx=10, pady=5); r += 1

        self.v_use_largest = BooleanVar(); self.v_largest_n = IntVar(value=1)
        _cb("Giữ", self.v_use_largest, r)
        Spinbox(p, from_=1, to=99, textvariable=self.v_largest_n, width=4,
                bg=CARD, fg=TEXT, buttonbackground=CARD, relief="flat",
                font=F_MAIN).grid(row=r, column=1, sticky=W)
        _lbl("box LỚN nhất / mỗi loại nhãn", r, 2, dim=False); r += 1

        self.v_use_smallest = BooleanVar(); self.v_smallest_n = IntVar(value=1)
        _cb("Giữ", self.v_use_smallest, r)
        Spinbox(p, from_=1, to=99, textvariable=self.v_smallest_n, width=4,
                bg=CARD, fg=TEXT, buttonbackground=CARD, relief="flat",
                font=F_MAIN).grid(row=r, column=1, sticky=W)
        _lbl("box NHỎ nhất / mỗi loại nhãn", r, 2, dim=False); r += 1

        Frame(p, bg=CARD, height=1).grid(row=r, column=0, columnspan=4,
                                          sticky=EW, padx=10, pady=5); r += 1

        self.v_use_min_area = BooleanVar(); self.v_min_area = DoubleVar(value=0.5)
        _cb("Diện tích box tối thiểu:", self.v_use_min_area, r)
        f = Frame(p, bg=BG); f.grid(row=r, column=1, columnspan=3, sticky=W)
        _ent(f, self.v_min_area).pack(side=LEFT)
        Label(f, text="% diện tích ảnh", bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT, padx=4)
        r += 1

        self.v_use_max_area = BooleanVar(); self.v_max_area = DoubleVar(value=80.0)
        _cb("Diện tích box tối đa:", self.v_use_max_area, r)
        f = Frame(p, bg=BG); f.grid(row=r, column=1, columnspan=3, sticky=W)
        _ent(f, self.v_max_area).pack(side=LEFT)
        Label(f, text="% diện tích ảnh", bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT, padx=4)
        r += 1

        self.v_use_min_side = BooleanVar(); self.v_min_side = IntVar(value=20)
        _cb("Cạnh box tối thiểu:", self.v_use_min_side, r)
        f = Frame(p, bg=BG); f.grid(row=r, column=1, columnspan=3, sticky=W)
        _ent(f, self.v_min_side).pack(side=LEFT)
        Label(f, text="pixel (min w, h)", bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT, padx=4)
        r += 1

        self.v_use_aspect = BooleanVar()
        self.v_aspect_min = DoubleVar(value=0.2)
        self.v_aspect_max = DoubleVar(value=5.0)
        _cb("Tỉ lệ w/h (aspect) trong:", self.v_use_aspect, r)
        f = Frame(p, bg=BG); f.grid(row=r, column=1, columnspan=3, sticky=W)
        _ent(f, self.v_aspect_min, 5).pack(side=LEFT)
        Label(f, text=" – ", bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT)
        _ent(f, self.v_aspect_max, 5).pack(side=LEFT)
        r += 1

        self.v_use_edge = BooleanVar(); self.v_edge_margin = DoubleVar(value=2.0)
        _cb("Loại box sát rìa ảnh (margin:", self.v_use_edge, r)
        f = Frame(p, bg=BG); f.grid(row=r, column=1, columnspan=3, sticky=W)
        _ent(f, self.v_edge_margin, 5).pack(side=LEFT)
        Label(f, text="%)", bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT, padx=2)
        r += 1

        self.v_use_nms = BooleanVar(); self.v_nms_iou = DoubleVar(value=0.5)
        _cb("NMS – loại box chồng nhau (IoU >", self.v_use_nms, r)
        f = Frame(p, bg=BG); f.grid(row=r, column=1, columnspan=3, sticky=W)
        _ent(f, self.v_nms_iou, 5).pack(side=LEFT)
        Label(f, text=")", bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT, padx=2)
        r += 1

        self.v_skip_empty = BooleanVar(value=True)
        _cb("Bỏ qua ảnh không còn box sau lọc", self.v_skip_empty, r, span=4)
        r += 1

        self.v_recursive = BooleanVar(value=False)
        _cb("Quét tất cả subfolder (đệ quy)", self.v_recursive, r, span=4)
        r += 1

        self._refresh_classes()

    def _build_split_opts(self, p):
        self.v_split_mode = StringVar(value="none")
        for val, text in [
            ("none",        "Không chia – tất cả vào 1 folder"),
            ("size",        "Theo kích thước box  (S / M / L)"),
            ("class",       "Theo nhãn lớp"),
            ("count",       "Theo số lượng  (single / multi)"),
            ("position",    "Theo vị trí  (border / center)"),
            ("region",      "Theo vùng 3×3  (top_left / center ...)"),
            ("orientation", "Theo chiều hướng  (landscape / portrait / square)"),
        ]:
            Radiobutton(p, text=text, variable=self.v_split_mode, value=val,
                        bg=BG, fg=TEXT, activebackground=BG, selectcolor=CARD,
                        font=F_MAIN).pack(anchor=W, padx=10, pady=3)

        Frame(p, bg=CARD, height=1).pack(fill=X, padx=10, pady=5)

        # ── Ngưỡng kích thước S/M/L ──
        Label(p, text="Ngưỡng kích thước (S/M/L):",
              bg=BG, fg=DIM, font=F_MAIN).pack(anchor=W, padx=10)
        tf = Frame(p, bg=BG); tf.pack(anchor=W, padx=14, pady=3)
        self.v_size_s = DoubleVar(value=3.0)
        self.v_size_l = DoubleVar(value=15.0)
        Label(tf, text="Small <", bg=BG, fg=DIM, font=F_MAIN).grid(row=0, column=0)
        Entry(tf, textvariable=self.v_size_s, width=5, bg=CARD, fg=TEXT,
              insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4).grid(row=0, column=1, padx=4)
        Label(tf, text="%   Large >", bg=BG, fg=DIM, font=F_MAIN).grid(row=0, column=2)
        Entry(tf, textvariable=self.v_size_l, width=5, bg=CARD, fg=TEXT,
              insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4).grid(row=0, column=3, padx=4)
        Label(tf, text="%  (Medium = giữa)", bg=BG, fg=DIM, font=F_MAIN).grid(row=0, column=4)

        # ── Ngưỡng vị trí border/center ──
        Label(p, text="Ngưỡng vị trí gần viền (border):",
              bg=BG, fg=DIM, font=F_MAIN).pack(anchor=W, padx=10, pady=(6, 0))
        pf = Frame(p, bg=BG); pf.pack(anchor=W, padx=14, pady=3)
        self.v_pos_border = DoubleVar(value=25.0)
        Label(pf, text="Biên <", bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT)
        Entry(pf, textvariable=self.v_pos_border, width=5, bg=CARD, fg=TEXT,
              insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4).pack(side=LEFT, padx=4)
        Label(pf, text="% từ mỗi cạnh  (còn lại = center)",
              bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT)

        # ── Ngưỡng tỉ lệ chiều hướng ──
        Label(p, text="Ngưỡng tỉ lệ w/h (orientation):",
              bg=BG, fg=DIM, font=F_MAIN).pack(anchor=W, padx=10, pady=(6, 0))
        of = Frame(p, bg=BG); of.pack(anchor=W, padx=14, pady=3)
        self.v_orient_thr = DoubleVar(value=1.3)
        Label(of, text="Threshold:", bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT)
        Entry(of, textvariable=self.v_orient_thr, width=5, bg=CARD, fg=TEXT,
              insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4).pack(side=LEFT, padx=4)
        Label(of, text="(w/h > t → landscape, h/w > t → portrait)",
              bg=BG, fg=DIM, font=("Consolas", 8)).pack(side=LEFT)

        Frame(p, bg=CARD, height=1).pack(fill=X, padx=10, pady=5)
        for hint in ["• size     → small/ medium/ large/",
                     "• class    → car/ motorbike/ ...",
                     "• count    → single/ multi/",
                     "• position → border/ center/",
                     "• region   → top_left/ center/ bottom_right/ ...",
                     "• orient   → landscape/ portrait/ square/"]:
            Label(p, text=hint, bg=BG, fg=DIM,
                  font=("Consolas", 8)).pack(anchor=W, padx=14)

    def _refresh_classes(self):
        for w in self._class_frame.winfo_children():
            w.destroy()
        self._class_vars.clear()
        names = [n.strip() for n in
                 self.v_classes.get().replace(";", ",").split(",") if n.strip()]
        for i, name in enumerate(names):
            v = BooleanVar(value=True)
            self._class_vars[i] = (name, v)
            Checkbutton(self._class_frame, text=name, variable=v,
                        bg=BG, fg=TEXT, activebackground=BG,
                        activeforeground=TEXT, selectcolor=CARD,
                        font=F_MAIN).grid(row=i // 4, column=i % 4,
                                          sticky=W, padx=4, pady=1)

    def _get_cfg(self):
        keep_ids = [i for i, (_, v) in self._class_vars.items() if v.get()]
        class_map = {i: name for i, (name, _) in self._class_vars.items()}
        return {
            "image_dir":       self.v_img.get().strip(),
            "label_dir":       self.v_lbl.get().strip(),
            "output_dir":      self.v_out.get().strip(),
            "use_class_filter": bool(self._class_vars),
            "keep_classes":    keep_ids,
            "class_names_map": class_map,
            "use_largest":     self.v_use_largest.get(),
            "keep_largest_n":  self.v_largest_n.get(),
            "use_smallest":    self.v_use_smallest.get(),
            "keep_smallest_n": self.v_smallest_n.get(),
            "use_min_area":    self.v_use_min_area.get(),
            "min_area_pct":    self.v_min_area.get(),
            "use_max_area":    self.v_use_max_area.get(),
            "max_area_pct":    self.v_max_area.get(),
            "use_min_side":    self.v_use_min_side.get(),
            "min_side_px":     self.v_min_side.get(),
            "use_aspect":      self.v_use_aspect.get(),
            "aspect_min":      self.v_aspect_min.get(),
            "aspect_max":      self.v_aspect_max.get(),
            "use_edge":        self.v_use_edge.get(),
            "edge_margin_pct": self.v_edge_margin.get(),
            "use_nms":         self.v_use_nms.get(),
            "nms_iou":         self.v_nms_iou.get(),
            "skip_empty":      self.v_skip_empty.get(),
            "recursive":       self.v_recursive.get(),
            "split_mode":      self.v_split_mode.get(),
            "size_s_pct":      self.v_size_s.get(),
            "size_l_pct":      self.v_size_l.get(),
            "pos_border_pct":  self.v_pos_border.get(),
            "orient_thr":      self.v_orient_thr.get(),
        }

    def _run(self):
        cfg = self._get_cfg()
        if not cfg["image_dir"] or not cfg["label_dir"] or not cfg["output_dir"]:
            messagebox.showwarning("Thiếu thông tin", "Vui lòng chọn đủ 3 thư mục.")
            return
        self._stop_event.clear()
        self.btn_run.config(state=DISABLED, text="⏳  Đang xử lý…")
        self.btn_stop.config(state=NORMAL)
        self.pb["value"] = 0
        self.pb_lbl.config(text="Đang khởi động…")

        def worker():
            try:
                run_label_norm(
                    cfg,
                    log=lambda m: self.root.after(0, _append_log, self.log, m),
                    progress=lambda d, t: self.root.after(
                        0, _set_progress, self.pb_lbl, self.pb, d, t, self.root),
                    stop_event=self._stop_event)
            except Exception as e:
                self.root.after(0, _append_log, self.log, f"[LỖI] {e}")
            finally:
                self.root.after(0, lambda: (
                    self.btn_run.config(state=NORMAL, text="▶  Bắt đầu"),
                    self.btn_stop.config(state=DISABLED),
                    self.pb_lbl.config(text="✅  Hoàn thành!")))

        threading.Thread(target=worker, daemon=True).start()

    def _stop(self):
        self._stop_event.set()
        self.btn_stop.config(state=DISABLED)
        _append_log(self.log, "⚠  Đang dừng sau ảnh hiện tại…")

    def _reset_state(self):
        out = self.v_out.get().strip()
        if not out:
            messagebox.showwarning("Chưa chọn output", "Chọn thư mục output trước."); return
        sf = Path(out) / ".label_norm_state.json"
        if sf.exists():
            sf.unlink()
            _append_log(self.log, "🔄  Đã xóa tiến độ. Lần chạy tiếp sẽ xử lý lại từ đầu.")
        else:
            _append_log(self.log, "ℹ  Không có file tiến độ.")

    def _open_out(self):
        p = self.v_out.get().strip()
        if p and Path(p).exists():
            os.startfile(p)
        else:
            messagebox.showwarning("Chưa có output", "Chọn hoặc chạy xong để mở thư mục.")


# ── Tab: Crop Image by Label ──────────────────────────────────────────────────

class CropByLabelTab(Frame):
    def __init__(self, master, root):
        super().__init__(master, bg=BG)
        self.root = root
        self._stop_event = threading.Event()
        self._class_vars = {}
        self._build()

    def _build(self):
        # ── Folder inputs ──
        top = Frame(self, bg=BG, padx=20, pady=12)
        top.pack(fill=X)
        self.v_img = StringVar(); self.v_lbl = StringVar(); self.v_out = StringVar()
        _bind_cfg("crop.img", self.v_img)
        _bind_cfg("crop.lbl", self.v_lbl)
        _bind_cfg("crop.out", self.v_out)
        _folder_row(top, "📁  Thư mục ảnh",         self.v_img, 0)
        _folder_row(top, "🏷  Thư mục label (.txt)", self.v_lbl, 1)
        _folder_row(top, "💾  Thư mục output",       self.v_out, 2)

        # Class names
        cr = Frame(top, bg=BG)
        cr.grid(row=3, column=0, columnspan=3, sticky=EW, pady=(8, 0))
        Label(cr, text="Danh sách nhãn:", bg=BG, fg=DIM,
              font=F_MAIN, width=26, anchor=W).pack(side=LEFT)
        self.v_classes = StringVar(
            value="car, motorbike, bus, truck, bicycle, license_plate")
        _bind_cfg("crop.classes", self.v_classes)
        Entry(cr, textvariable=self.v_classes, bg=CARD, fg=TEXT,
              insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4).pack(
              side=LEFT, fill=X, expand=True, padx=(8, 0))
        Button(cr, text="Cập nhật ↺", command=self._refresh_classes,
               bg=ACCENT2, fg="white", activebackground=ACCENT,
               activeforeground="white", font=F_MAIN, relief="flat",
               padx=10, cursor="hand2").pack(side=LEFT, padx=(6, 0))

        # ── Options row ──
        opt = Frame(self, bg=BG, padx=20)
        opt.pack(fill=X, pady=(0, 4))
        opt.columnconfigure(0, weight=3)
        opt.columnconfigure(1, weight=2)

        # Left: class filter
        cls_f = LabelFrame(opt, text=" Nhãn lớp cần crop ",
                           bg=BG, fg=TEXT, font=F_BOLD, bd=1, relief="groove")
        cls_f.grid(row=0, column=0, sticky=NSEW, padx=(0, 8), pady=4)
        self._class_frame = Frame(cls_f, bg=BG)
        self._class_frame.pack(anchor=W, padx=10, pady=8)

        # Right: settings
        cfg_f = LabelFrame(opt, text=" Tùy chọn ",
                           bg=BG, fg=TEXT, font=F_BOLD, bd=1, relief="groove")
        cfg_f.grid(row=0, column=1, sticky=NSEW, pady=4)
        self._build_opts(cfg_f)

        # ── Bottom (anchored) ──
        btn_row = Frame(self, bg=BG, padx=20, pady=6)
        self.btn_run = _action_btn(btn_row, "✂  Bắt đầu Crop", self._run, ACCENT,
                                   padx=20, pady=7)
        self.btn_run.pack(side=LEFT)
        self.btn_stop = _action_btn(btn_row, "⏹  Dừng", self._stop, "#c0392b",
                                    padx=14, pady=7)
        self.btn_stop.pack(side=LEFT, padx=(8, 0))
        self.btn_stop.config(state=DISABLED)
        _action_btn(btn_row, "🔄  Xóa tiến độ", self._reset_state, ACCENT2,
                    padx=14, pady=7).pack(side=LEFT, padx=(8, 0))
        _action_btn(btn_row, "📂  Mở output", self._open_out, ACCENT2,
                    padx=14, pady=7).pack(side=LEFT, padx=(8, 0))
        Button(btn_row, text="🧹  Xóa log",
               command=lambda: (self.log.configure(state=NORMAL),
                                self.log.delete("1.0", END),
                                self.log.configure(state=DISABLED)),
               bg=CARD, fg=DIM, font=F_MAIN, relief="flat",
               padx=14, pady=7, cursor="hand2").pack(side=RIGHT)

        pb_f = Frame(self, bg=BG, padx=20)
        self.pb_lbl, self.pb = _pb_row(pb_f)

        log_outer = Frame(self, bg=BG, padx=20)
        log_f, self.log = _make_logbox(log_outer)
        log_f.pack(fill=BOTH, expand=True)

        btn_row.pack(fill=X, side=BOTTOM)
        pb_f.pack(fill=X, side=BOTTOM)
        log_outer.pack(fill=BOTH, expand=True)

        self._refresh_classes()

    def _build_opts(self, p):
        def _row(label, var, unit="", row=0, w=6):
            Label(p, text=label, bg=BG, fg=DIM, font=F_MAIN).grid(
                row=row, column=0, sticky=W, padx=10, pady=4)
            f = Frame(p, bg=BG); f.grid(row=row, column=1, sticky=W, padx=4)
            Entry(f, textvariable=var, width=w, bg=CARD, fg=TEXT,
                  insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4).pack(side=LEFT)
            if unit:
                Label(f, text=unit, bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT, padx=3)

        r = 0
        self.v_padding = IntVar(value=0)
        _row("Padding (mở rộng crop):", self.v_padding, "px", r); r += 1

        self.v_min_w = IntVar(value=0)
        _row("Crop tối thiểu (rộng):", self.v_min_w, "px", r); r += 1

        self.v_min_h = IntVar(value=0)
        _row("Crop tối thiểu (cao):", self.v_min_h, "px", r); r += 1

        self.v_quality = IntVar(value=95)
        _row("JPEG quality:", self.v_quality, "(1–100)", r); r += 1

        Frame(p, bg=CARD, height=1).grid(row=r, column=0, columnspan=2,
                                          sticky=EW, padx=10, pady=6); r += 1

        self.v_by_class = BooleanVar(value=True)
        Checkbutton(p, text="Chia subfolder theo từng nhãn",
                    variable=self.v_by_class, bg=BG, fg=TEXT,
                    activebackground=BG, activeforeground=TEXT,
                    selectcolor=CARD, font=F_MAIN).grid(
                    row=r, column=0, columnspan=2, sticky=W, padx=10, pady=2)
        r += 1

        self.v_filter_cls = BooleanVar(value=False)
        Checkbutton(p, text="Chỉ crop các nhãn đã tích",
                    variable=self.v_filter_cls, bg=BG, fg=TEXT,
                    activebackground=BG, activeforeground=TEXT,
                    selectcolor=CARD, font=F_MAIN).grid(
                    row=r, column=0, columnspan=2, sticky=W, padx=10, pady=2)
        r += 1

        self.v_recursive = BooleanVar(value=False)
        Checkbutton(p, text="Quét tất cả subfolder (đệ quy)",
                    variable=self.v_recursive, bg=BG, fg=TEXT,
                    activebackground=BG, activeforeground=TEXT,
                    selectcolor=CARD, font=F_MAIN).grid(
                    row=r, column=0, columnspan=2, sticky=W, padx=10, pady=2)

    def _refresh_classes(self):
        for w in self._class_frame.winfo_children():
            w.destroy()
        self._class_vars.clear()
        names = [n.strip() for n in
                 self.v_classes.get().replace(";", ",").split(",") if n.strip()]
        for i, name in enumerate(names):
            v = BooleanVar(value=True)
            self._class_vars[i] = (name, v)
            Checkbutton(self._class_frame, text=name, variable=v,
                        bg=BG, fg=TEXT, activebackground=BG,
                        activeforeground=TEXT, selectcolor=CARD,
                        font=F_MAIN).grid(row=i // 3, column=i % 3,
                                          sticky=W, padx=6, pady=2)

    def _get_cfg(self):
        keep_ids  = [i for i, (_, v) in self._class_vars.items() if v.get()]
        class_map = {i: name for i, (name, _) in self._class_vars.items()}
        return {
            "image_dir":    self.v_img.get().strip(),
            "label_dir":    self.v_lbl.get().strip(),
            "output_dir":   self.v_out.get().strip(),
            "filter_classes": self.v_filter_cls.get(),
            "keep_classes": keep_ids,
            "class_names_map": class_map,
            "padding_px":   self.v_padding.get(),
            "min_w_px":     self.v_min_w.get(),
            "min_h_px":     self.v_min_h.get(),
            "jpeg_quality": self.v_quality.get(),
            "split_by_class": self.v_by_class.get(),
            "recursive":      self.v_recursive.get(),
        }

    def _run(self):
        cfg = self._get_cfg()
        if not cfg["image_dir"] or not cfg["label_dir"] or not cfg["output_dir"]:
            messagebox.showwarning("Thiếu thông tin", "Vui lòng chọn đủ 3 thư mục.")
            return
        self._stop_event.clear()
        self.btn_run.config(state=DISABLED, text="⏳  Đang xử lý…")
        self.btn_stop.config(state=NORMAL)
        self.pb["value"] = 0
        self.pb_lbl.config(text="Đang khởi động…")

        def worker():
            try:
                run_crop_by_label(
                    cfg,
                    log=lambda m: self.root.after(0, _append_log, self.log, m),
                    progress=lambda d, t: self.root.after(
                        0, _set_progress, self.pb_lbl, self.pb, d, t, self.root),
                    stop_event=self._stop_event)
            except Exception as e:
                self.root.after(0, _append_log, self.log, f"[LỖI] {e}")
            finally:
                self.root.after(0, lambda: (
                    self.btn_run.config(state=NORMAL, text="✂  Bắt đầu Crop"),
                    self.btn_stop.config(state=DISABLED),
                    self.pb_lbl.config(text="✅  Hoàn thành!")))

        threading.Thread(target=worker, daemon=True).start()

    def _stop(self):
        self._stop_event.set()
        self.btn_stop.config(state=DISABLED)
        _append_log(self.log, "⚠  Đang dừng sau ảnh hiện tại…")

    def _reset_state(self):
        out = self.v_out.get().strip()
        if not out:
            messagebox.showwarning("Chưa chọn output", "Chọn thư mục output trước."); return
        sf = Path(out) / ".crop_by_label_state.json"
        if sf.exists():
            sf.unlink()
            _append_log(self.log, "🔄  Đã xóa tiến độ. Lần chạy tiếp sẽ xử lý lại từ đầu.")
        else:
            _append_log(self.log, "ℹ  Không có file tiến độ.")

    def _open_out(self):
        p = self.v_out.get().strip()
        if p and Path(p).exists():
            os.startfile(p)
        else:
            messagebox.showwarning("Chưa có output", "Chọn hoặc chạy xong để mở thư mục.")


# ── Tab 9: Train Model ────────────────────────────────────────────────────────

class TrainTab(Frame):
    """Huấn luyện YOLO11 — tự sinh data.yaml, chạy subprocess, log realtime"""

    _MODELS = [
        ("yolo11n.pt", "Nano  – nhanh nhất, nhẹ nhất"),
        ("yolo11s.pt", "Small"),
        ("yolo11m.pt", "Medium"),
        ("yolo11l.pt", "Large"),
        ("yolo11x.pt", "XLarge – chính xác nhất"),
    ]

    def __init__(self, master, root):
        super().__init__(master, bg=BG)
        self.root = root

        self.train_dir    = StringVar()
        self.val_dir      = StringVar()
        self._labels_var  = StringVar(
            value="car,motorcycle,bus,truck,bicycle,license_plate")
        self._model_var   = StringVar(value="yolo11n.pt")
        _bind_cfg("train.dir",     self.train_dir)
        _bind_cfg("train.val",     self.val_dir)
        _bind_cfg("train.labels",  self._labels_var)
        self._epochs_var  = StringVar(value="100")
        self._imgsz_var   = StringVar(value="640")
        self._batch_var   = StringVar(value="16")
        self._device_var  = StringVar(value="0")
        self._project_var    = StringVar()
        self._name_var       = StringVar(value="kztek_train")
        _bind_cfg("train.project", self._project_var)
        self._split_ratio_var = IntVar(value=90)

        self._proc       = None          # subprocess.Popen
        self._out_queue  = queue.Queue()
        self._poll_id    = None
        self._output_dir = ""

        self._build()

    # ── build ─────────────────────────────────────────────────────────────────

    def _build(self):
        # ── dataset rows ──
        top = Frame(self, bg=CARD, padx=12, pady=10)
        top.pack(fill=X)
        grid = Frame(top, bg=CARD)
        grid.pack(fill=X)
        _folder_row(grid, "Thư mục train :", self.train_dir, 0, bg=CARD)
        _folder_row(grid, "Thư mục val   :", self.val_dir,   1, bg=CARD)

        # split-ratio row (shown always; used when val == train or val is empty)
        Label(grid, text="Tỷ lệ tự chia:", bg=CARD, fg=DIM,
              font=F_MAIN, width=26, anchor=W).grid(row=2, column=0, sticky=W, pady=4)
        split_row = Frame(grid, bg=CARD)
        split_row.grid(row=2, column=1, sticky=W, padx=(8, 0))
        Label(split_row, text="Train", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        Spinbox(split_row, from_=50, to=99, textvariable=self._split_ratio_var,
                width=4, bg="#16162a", fg=TEXT, insertbackground=TEXT,
                buttonbackground=ACCENT2, relief="flat", font=F_MAIN,
                command=self._on_split_change).pack(side=LEFT, padx=(4, 2))
        self._split_val_lbl = Label(split_row, text="% / Val 10%",
                                     bg=CARD, fg=DIM, font=F_MAIN)
        self._split_val_lbl.pack(side=LEFT)
        self._split_info_lbl = Label(split_row,
            text="  ← áp dụng khi thư mục val trống hoặc trùng train",
            bg=CARD, fg="#f0c040", font=("Segoe UI", 8, "italic"))
        self._split_info_lbl.pack(side=LEFT)
        self._split_ratio_var.trace_add("write", self._on_split_change)

        Label(grid, text="Danh sách nhãn:", bg=CARD, fg=DIM,
              font=F_MAIN, width=26, anchor=W).grid(row=3, column=0, sticky=W, pady=5)
        Entry(grid, textvariable=self._labels_var, bg=CARD, fg=TEXT,
              insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4).grid(
                  row=3, column=1, sticky=EW, padx=(8, 8))
        Button(grid, text="📄 Tạo data.yaml",
               command=self._gen_yaml_only,
               bg=ACCENT2, fg="white", activebackground=ACCENT,
               activeforeground="white", font=F_MAIN,
               relief="flat", padx=10, cursor="hand2").grid(row=3, column=2)

        # ── training params ──
        pf = Frame(self, bg=CARD, padx=14, pady=10)
        pf.pack(fill=X, padx=12, pady=(6, 0))

        Label(pf, text="Cấu hình huấn luyện", bg=CARD, fg=TEXT,
              font=F_BOLD).grid(row=0, column=0, columnspan=8, sticky=W, pady=(0, 8))

        # model combobox + desc
        Label(pf, text="Model:", bg=CARD, fg=DIM, font=F_MAIN).grid(
            row=1, column=0, sticky=W)
        model_cb = ttk.Combobox(pf, textvariable=self._model_var, width=13,
                                state="readonly", font=F_MAIN,
                                values=[m for m, _ in self._MODELS])
        model_cb.grid(row=1, column=1, sticky=W, padx=(4, 16))
        model_cb.current(0)
        self._model_desc = Label(pf, text=self._MODELS[0][1],
                                  bg=CARD, fg=DIM, font=("Segoe UI", 8, "italic"))
        self._model_desc.grid(row=2, column=0, columnspan=2, sticky=W, pady=(0, 6))
        model_cb.bind("<<ComboboxSelected>>", self._on_model_change)

        # numeric params
        for col, (lbl, var, tip) in enumerate([
            ("Epochs:",  self._epochs_var, "số lần lặp"),
            ("Imgsz:",   self._imgsz_var,  "kích thước ảnh"),
            ("Batch:",   self._batch_var,  "−1 = auto"),
            ("Device:",  self._device_var, "0=GPU, cpu"),
        ]):
            c = (col + 1) * 2
            Label(pf, text=lbl, bg=CARD, fg=DIM, font=F_MAIN).grid(
                row=1, column=c, sticky=W, padx=(16, 4))
            e = Entry(pf, textvariable=var, bg="#16162a", fg=TEXT,
                      insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4, width=7)
            e.grid(row=1, column=c + 1, sticky=W)
            Label(pf, text=tip, bg=CARD, fg=DIM,
                  font=("Segoe UI", 7, "italic")).grid(
                      row=2, column=c, columnspan=2, sticky=W)

        # project / name
        Label(pf, text="Output folder:", bg=CARD, fg=DIM, font=F_MAIN).grid(
            row=3, column=0, sticky=W, pady=(8, 0))
        proj_row = Frame(pf, bg=CARD)
        proj_row.grid(row=3, column=1, columnspan=9, sticky=EW, pady=(8, 0))
        Entry(proj_row, textvariable=self._project_var, bg="#16162a", fg=TEXT,
              insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4, width=30).pack(side=LEFT)
        Button(proj_row, text="…",
               command=lambda: (p := filedialog.askdirectory(
                   initialdir=_cfg_dir("train.project"))) and self._project_var.set(p),
               bg=ACCENT2, fg="white", font=F_MAIN, relief="flat",
               padx=8, cursor="hand2").pack(side=LEFT, padx=(4, 16))
        Label(proj_row, text="Run name:", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        Entry(proj_row, textvariable=self._name_var, bg="#16162a", fg=TEXT,
              insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4, width=18).pack(
                  side=LEFT, padx=(4, 0))

        # ── control buttons ──
        ctrl = Frame(self, bg=BG, padx=12, pady=6)
        ctrl.pack(fill=X)
        self._btn_start = Button(ctrl, text="▶  Bắt đầu Train",
                                  command=self._start_train,
                                  bg="#2e7d32", fg="white",
                                  activebackground="#1b5e20", activeforeground="white",
                                  font=F_BOLD, relief="flat", padx=20, cursor="hand2")
        self._btn_start.pack(side=LEFT)
        self._btn_stop = Button(ctrl, text="⏹  Dừng",
                                command=self._stop_train,
                                bg="#c62828", fg="white",
                                activebackground="#8b0000", activeforeground="white",
                                font=F_BOLD, relief="flat", padx=14, cursor="hand2",
                                state=DISABLED)
        self._btn_stop.pack(side=LEFT, padx=(8, 0))
        self._status_lbl = Label(ctrl, text="", bg=BG, fg=DIM, font=F_MAIN)
        self._status_lbl.pack(side=LEFT, padx=16)

        # ── log ──
        log_frame, self._log = _make_logbox(self)
        log_frame.pack(fill=BOTH, expand=True, padx=12, pady=(4, 4))

        # ── result bar ──
        res = Frame(self, bg=CARD, padx=12, pady=6)
        res.pack(fill=X, padx=12, pady=(0, 8))
        Label(res, text="Kết quả:", bg=CARD, fg=TEXT, font=F_BOLD).pack(side=LEFT)
        self._result_lbl = Label(res, text="—", bg=CARD, fg=DIM, font=F_MAIN)
        self._result_lbl.pack(side=LEFT, padx=8)
        self._open_btn = Button(res, text="📂 Mở thư mục output",
                                command=self._open_output_dir,
                                bg=ACCENT2, fg="white",
                                activebackground=ACCENT, activeforeground="white",
                                font=F_MAIN, relief="flat", padx=10, cursor="hand2",
                                state=DISABLED)
        self._open_btn.pack(side=LEFT, padx=4)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _on_model_change(self, _event):
        val = self._model_var.get()
        for name, desc in self._MODELS:
            if name == val:
                self._model_desc.config(text=desc)
                break

    def _on_split_change(self, *_):
        try:
            r = int(self._split_ratio_var.get())
            r = max(50, min(99, r))
            self._split_val_lbl.config(text=f"% / Val {100 - r}%")
        except (ValueError, TclError):
            pass

    def _parse_labels(self):
        raw = self._labels_var.get().strip()
        return [s.strip() for s in raw.replace("\n", ",").split(",") if s.strip()]

    def _resolve_img_dir(self, folder):
        """Return images subfolder if present, else the folder itself."""
        sub = os.path.join(folder, "images")
        return sub if os.path.isdir(sub) else folder

    def _needs_split(self, train_dir, val_dir):
        """True when val is absent or points to the same location as train."""
        if not val_dir:
            return True
        try:
            return os.path.samefile(train_dir, val_dir)
        except Exception:
            return (os.path.normcase(os.path.abspath(train_dir)) ==
                    os.path.normcase(os.path.abspath(val_dir)))

    @staticmethod
    def _link_or_copy(src: Path, dst: Path):
        """Hard-link src→dst; fall back to shutil.copy2 on cross-drive writes."""
        if dst.exists():
            return
        try:
            os.link(src, dst)
        except OSError:
            shutil.copy2(src, dst)

    def _build_dataset_dir(self, splits: dict) -> Path:
        """Build images/labels train|val structure; return root for data.yaml 'path:'.

        Uses hard links when source and temp share a drive (fast, no disk overhead).
        Falls back to shutil.copy2 for cross-drive scenarios.
        splits = {'train': [Path, ...], 'val': [Path, ...]}
        Expects labels co-located with images (same stem, .txt extension).
        """
        src_drives = {p.drive.upper() for imgs in splits.values() for p in imgs}
        if len(src_drives) == 1:
            root = Path(next(iter(src_drives)) + "/") / "kztek_split"
        else:
            root = Path(tempfile.gettempdir()) / "kztek_split"

        for split, imgs in splits.items():
            (root / "images" / split).mkdir(parents=True, exist_ok=True)
            (root / "labels" / split).mkdir(parents=True, exist_ok=True)
            for img in imgs:
                self._link_or_copy(img, root / "images" / split / img.name)
                lbl = img.with_suffix(".txt")
                if lbl.exists():
                    self._link_or_copy(lbl, root / "labels" / split / lbl.name)
        return root

    def _write_yaml(self, train_dir, val_dir, labels):
        """Generate data.yaml. Auto-splits when val == train or val is empty.
        Returns (yaml_path, split_msg) where split_msg is '' for normal mode.
        Always creates a proper images/labels directory structure so ultralytics
        img2label_paths resolution works regardless of source path layout.
        """
        nc        = len(labels)
        names_str = ", ".join(f"'{n}'" for n in labels)
        yaml_path = os.path.join(os.path.dirname(os.path.abspath(train_dir)), "data.yaml")

        if self._needs_split(train_dir, val_dir):
            ratio    = max(50, min(99, int(self._split_ratio_var.get())))
            img_dir  = Path(self._resolve_img_dir(train_dir))
            all_imgs = sorted(p for p in img_dir.iterdir()
                              if p.suffix.lower() in IMAGE_EXTENSIONS)
            if not all_imgs:
                raise ValueError(f"Không tìm thấy ảnh trong {img_dir}")

            random.shuffle(all_imgs)
            n_train    = max(1, int(len(all_imgs) * ratio / 100))
            train_imgs = all_imgs[:n_train]
            val_imgs   = all_imgs[n_train:] or all_imgs[-1:]  # ≥1 val

            root = self._build_dataset_dir({"train": train_imgs, "val": val_imgs})

            with open(yaml_path, "w", encoding="utf-8") as f:
                f.write(f"path: {root}\n")
                f.write(f"train: images/train\n")
                f.write(f"val:   images/val\n")
                f.write(f"nc: {nc}\n")
                f.write(f"names: [{names_str}]\n")

            split_msg = (f"Tự chia {ratio}/{100-ratio}: "
                         f"{len(train_imgs)} train / {len(val_imgs)} val")
            return yaml_path, split_msg

        # Separate val folder — still use proper structure to avoid path confusion.
        train_imgs = sorted(p for p in Path(self._resolve_img_dir(train_dir)).iterdir()
                            if p.suffix.lower() in IMAGE_EXTENSIONS)
        val_imgs   = sorted(p for p in Path(self._resolve_img_dir(val_dir)).iterdir()
                            if p.suffix.lower() in IMAGE_EXTENSIONS)
        root = self._build_dataset_dir({"train": train_imgs, "val": val_imgs})

        with open(yaml_path, "w", encoding="utf-8") as f:
            f.write(f"path: {root}\n")
            f.write(f"train: images/train\n")
            f.write(f"val:   images/val\n")
            f.write(f"nc: {nc}\n")
            f.write(f"names: [{names_str}]\n")
        return yaml_path, f"{len(train_imgs)} train / {len(val_imgs)} val"

    def _gen_yaml_only(self):
        labels    = self._parse_labels()
        train_dir = self.train_dir.get().strip()
        if not train_dir or not os.path.isdir(train_dir):
            messagebox.showerror("Lỗi", "Vui lòng chọn thư mục train hợp lệ.")
            return
        if not labels:
            messagebox.showerror("Lỗi", "Vui lòng nhập danh sách nhãn.")
            return
        val_dir = self.val_dir.get().strip() or None
        try:
            path, split_msg = self._write_yaml(train_dir, val_dir, labels)
            info = f"\n{split_msg}" if split_msg else ""
            _append_log(self._log, f"✔  data.yaml: {path}{info}")
            messagebox.showinfo("Tạo data.yaml", f"Đã tạo:\n{path}"
                                + (f"\n\n{split_msg}" if split_msg else ""))
        except Exception as e:
            messagebox.showerror("Lỗi", str(e))

    # ── train ─────────────────────────────────────────────────────────────────

    def _start_train(self):
        labels    = self._parse_labels()
        train_dir = self.train_dir.get().strip()
        if not train_dir or not os.path.isdir(train_dir):
            messagebox.showerror("Lỗi", "Vui lòng chọn thư mục train hợp lệ.")
            return
        if not labels:
            messagebox.showerror("Lỗi", "Vui lòng nhập danh sách nhãn.")
            return

        val_dir = self.val_dir.get().strip() or None
        model   = self._model_var.get()
        project = self._project_var.get().strip() or str(
            Path(train_dir).parent / "runs")
        name    = self._name_var.get().strip() or "train"

        try:
            epochs = int(self._epochs_var.get())
            imgsz  = int(self._imgsz_var.get())
            batch  = int(self._batch_var.get())
        except ValueError:
            messagebox.showerror("Lỗi", "Epochs / Imgsz / Batch phải là số nguyên.")
            return
        device = self._device_var.get().strip() or "0"

        # generate yaml
        try:
            yaml_path, split_msg = self._write_yaml(train_dir, val_dir, labels)
        except Exception as e:
            messagebox.showerror("Lỗi tạo data.yaml", str(e))
            return

        # write temp training script
        # NOTE: must be inside if __name__ == '__main__' on Windows
        #       to avoid multiprocessing spawn RuntimeError
        script = (
            "import os, sys, multiprocessing\n"
            "multiprocessing.freeze_support()\n"
            "if __name__ == '__main__':\n"
            "    os.environ.setdefault('KMP_DUPLICATE_LIB_OK', 'TRUE')\n"
            "    try:\n"
            "        from ultralytics import YOLO\n"
            "    except ImportError:\n"
            "        print('[LỖI] ultralytics chưa được cài. Chạy: pip install ultralytics')\n"
            "        sys.exit(1)\n"
            f"    model = YOLO({model!r})\n"
            f"    results = model.train(\n"
            f"        data={yaml_path!r},\n"
            f"        epochs={epochs},\n"
            f"        imgsz={imgsz},\n"
            f"        batch={batch},\n"
            f"        device={device!r},\n"
            f"        project={project!r},\n"
            f"        name={name!r},\n"
            f"        exist_ok=True,\n"
            f"    )\n"
            "    print(f'KZTEK_SAVE_DIR: {results.save_dir}')\n"
        )
        tmp_script = Path(tempfile.gettempdir()) / "kztek_train_job.py"
        tmp_script.write_text(script, encoding="utf-8")

        # clear log
        self._log.configure(state=NORMAL)
        self._log.delete("1.0", END)
        self._log.configure(state=DISABLED)
        _append_log(self._log,
            f"▶  model={model}  epochs={epochs}  imgsz={imgsz}  "
            f"batch={batch}  device={device}")
        _append_log(self._log, f"   data.yaml : {yaml_path}")
        if split_msg:
            _append_log(self._log, f"   {split_msg}")
        _append_log(self._log, f"   output    : {project}/{name}")
        _append_log(self._log, "─" * 70)

        try:
            self._proc = subprocess.Popen(
                [sys.executable, str(tmp_script)],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                bufsize=1,
            )
        except Exception as e:
            messagebox.showerror("Lỗi khởi động", str(e))
            return

        self._output_dir = os.path.join(project, name)
        self._btn_start.config(state=DISABLED)
        self._btn_stop.config(state=NORMAL)
        self._status_lbl.config(text="⏳ Đang train…", fg=ACCENT)
        self._result_lbl.config(text="—")
        self._open_btn.config(state=DISABLED)

        proc = self._proc
        q    = self._out_queue
        def _reader():
            for raw in iter(proc.stdout.readline, b""):
                q.put(raw.decode("utf-8", errors="replace"))
            q.put(None)
        threading.Thread(target=_reader, daemon=True).start()
        self._poll_output()

    def _stop_train(self):
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            _append_log(self._log, "⚠  Training đã bị dừng thủ công.")
        self._btn_start.config(state=NORMAL)
        self._btn_stop.config(state=DISABLED)
        self._status_lbl.config(text="Đã dừng", fg="#f0c040")

    def _poll_output(self):
        try:
            while True:
                line = self._out_queue.get_nowait()
                if line is None:
                    self._on_done()
                    return
                text = line.rstrip()
                if not text:
                    continue
                if "KZTEK_SAVE_DIR:" in text:
                    self._output_dir = text.split("KZTEK_SAVE_DIR:", 1)[1].strip()
                _append_log(self._log, text)
        except queue.Empty:
            pass
        self._poll_id = self.root.after(120, self._poll_output)

    def _on_done(self):
        rc = self._proc.returncode if self._proc else -1
        self._proc = None
        if self._poll_id:
            self.root.after_cancel(self._poll_id)
            self._poll_id = None
        self._btn_start.config(state=NORMAL)
        self._btn_stop.config(state=DISABLED)
        if rc == 0:
            best = os.path.join(self._output_dir, "weights", "best.pt")
            _append_log(self._log, "─" * 70)
            _append_log(self._log, f"✔  Hoàn tất!  best.pt → {best}")
            self._status_lbl.config(text="✔ Hoàn tất", fg=SUCCESS)
            self._result_lbl.config(text=f"best.pt  →  {best}")
            self._open_btn.config(state=NORMAL)
        else:
            _append_log(self._log, f"[LỖI]  Tiến trình kết thúc với exit code {rc}")
            self._status_lbl.config(text=f"Lỗi (exit {rc})", fg="#f05050")

    def _open_output_dir(self):
        d = self._output_dir
        if os.path.isdir(d):
            subprocess.Popen(["explorer", os.path.normpath(d)])
        else:
            messagebox.showinfo("Thông báo", f"Thư mục chưa tồn tại:\n{d}")


# ── Main App ───────────────────────────────────────────────────────────────────

_AppBase = _dnd_mod.Tk if _DND_OK else Tk


class App(_AppBase):
    def __init__(self):
        super().__init__()
        self.title("KZTEK Image Tools")
        self.configure(bg=BG)
        self.resizable(True, True)
        self.minsize(900, 640)
        _style_all()
        self._build()
        self._center()

    def _build(self):
        hdr = Frame(self, bg=ACCENT2, pady=10)
        hdr.pack(fill=X)
        Label(hdr, text="KZTEK IMAGE TOOLS", bg=ACCENT2, fg="white",
              font=("Segoe UI Semibold", 14)).pack()
        Label(hdr, text="Xử lý ảnh dataset  |  kztek.net",
              bg=ACCENT2, fg="#c0b8e8", font=("Segoe UI", 9)).pack()

        nb = ttk.Notebook(self, style="Dark.TNotebook")
        nb.pack(fill=BOTH, expand=True)

        tab2 = SplitTab(nb, self)
        tab3 = CheckerTab(nb, self, nb)
        tab4 = StatsTab(nb, self)
        tab5 = RenameTab(nb, self)
        tab6 = OcrTab(nb, self)
        tab7 = LotteImageTab(nb, self)
        tab8  = BBoxEditorTab(nb, self)
        tab9  = LabelNormTab(nb, self)
        tab10 = TrainTab(nb, self)
        tab11 = CropByLabelTab(nb, self)

        nb.add(tab2,  text="  \U0001f4c2  Split Images  ")
        nb.add(tab3,  text="  \U0001f50d  Dataset Checker  ")
        nb.add(tab4,  text="  \U0001f4ca  GT Stats  ")
        nb.add(tab5,  text="  ✏  Đổi tên  ")
        nb.add(tab6,  text="  \U0001f524  PaddleOCR  ")
        nb.add(tab7,  text="  \U0001f185  LotteImage  ")
        nb.add(tab9,  text="  \U0001f3f7  Chuẩn hóa Label  ")
        nb.add(tab8,  text="  \U0001f58a  Hiệu chỉnh bbox  ")
        nb.add(tab10, text="  \U0001f680  Train Model  ")
        nb.add(tab11, text="  ✂  Crop by Label  ")

    def _center(self):
        self.update_idletasks()
        w, h = 1120, 800
        x = (self.winfo_screenwidth()  - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")


if __name__ == "__main__":
    App().mainloop()
