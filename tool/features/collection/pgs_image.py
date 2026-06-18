"""PGS Image Worker — thu thập ảnh từ hệ thống PGS (file-based network share).

Cấu trúc nguồn:
    <source_path>/<camera>/<year>/<month>/<day>/<HH>_<MM>_<SS>_<id>_<type>.jpg

Ví dụ:
    \\\\192.168.1.1\\images\\images\\192.168.16.2_1\\2026\\1\\3\\00_45_28_9432434_overview.jpg
"""

import queue
import shutil
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}


def _parse_date(s: str) -> Optional[datetime]:
    s = str(s or "").strip()[:10]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    return None


def _date_range(start: datetime, end: datetime) -> List[datetime]:
    dates: List[datetime] = []
    curr = start.replace(hour=0, minute=0, second=0, microsecond=0)
    stop = end.replace(hour=0, minute=0, second=0, microsecond=0)
    while curr <= stop:
        dates.append(curr)
        curr += timedelta(days=1)
    return dates


def _filename_hour(name: str) -> int:
    """Trích giờ từ HH_MM_SS_... → 0–23, hoặc -1 nếu không parse được."""
    try:
        return int(name.split("_")[0])
    except (IndexError, ValueError):
        return -1


def _limit_by_hour(files: List[Path], max_per_hour: int) -> List[Path]:
    """Giới hạn số file tối đa mỗi giờ."""
    buckets: Dict[int, List[Path]] = {}
    for f in files:
        h = _filename_hour(f.name)
        buckets.setdefault(h, []).append(f)
    out: List[Path] = []
    for h in sorted(buckets):
        out.extend(buckets[h][:max_per_hour])
    return out


def _spread_sample(files: List[Path], n: int) -> List[Path]:
    """Chọn n file phân tán đều từ danh sách đã sắp xếp."""
    if len(files) <= n:
        return files
    step = len(files) / n
    return [files[int(i * step)] for i in range(n)]


class PgsImageWorker:
    """Thu thập ảnh từ hệ thống PGS (file-based).

    Duyệt cây thư mục <source>/<camera>/<year>/<month>/<day>/,
    lọc theo loại ảnh, áp dụng giới hạn số lượng rồi copy sang output.
    """

    def __init__(self, cfg: dict, log_q: queue.Queue, stat_q: queue.Queue,
                 pause_event: Optional[threading.Event] = None,
                 signal_done: bool = True):
        self.cfg         = cfg
        self.log_q       = log_q
        self.stat_q      = stat_q
        self.pause_event = pause_event or threading.Event()
        self.pause_event.set()
        self._stop_ev    = threading.Event()
        self._signal_done = signal_done

        self._saved   = 0
        self._skipped = 0
        self._errors  = 0

    def stop(self):
        self._stop_ev.set()

    def _log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_q.put(f"[{ts}] {msg}")

    def _stat(self, d: dict):
        self.stat_q.put(d)

    def run(self):
        cfg = self.cfg
        source       = Path(cfg.get("source_path", ""))
        output       = Path(cfg.get("output_path", ""))
        cameras      = [c.strip() for c in cfg.get("cameras", []) if c.strip()]
        date_from    = _parse_date(cfg.get("date_from", ""))
        date_to      = _parse_date(cfg.get("date_to", ""))
        img_types    = [t.strip().lower() for t in cfg.get("img_types", []) if t.strip()]
        max_per_day  = max(0, int(cfg.get("max_per_day",  0)))
        max_per_hour = max(0, int(cfg.get("max_per_hour", 0)))
        max_per_cam  = max(0, int(cfg.get("max_per_cam",  0)))
        sleep_sec    = max(0.0, float(cfg.get("sleep_sec", 0.0)))

        if not source.exists():
            self._log(f"[LỖI] Đường dẫn nguồn không tồn tại: {source}")
            self._stat({"done": True, "saved": 0, "errors": 1})
            return

        output.mkdir(parents=True, exist_ok=True)

        if not cameras:
            try:
                cameras = sorted(d.name for d in source.iterdir() if d.is_dir())
                names_preview = ", ".join(cameras[:5]) + ("…" if len(cameras) > 5 else "")
                self._log(f"Tự phát hiện {len(cameras)} camera: {names_preview}")
            except Exception as e:
                self._log(f"[LỖI] Không đọc được thư mục nguồn: {e}")
                self._stat({"done": True, "saved": 0, "errors": 1})
                return

        if not date_from or not date_to:
            self._log("[LỖI] Khoảng ngày không hợp lệ")
            self._stat({"done": True, "saved": 0, "errors": 1})
            return

        dates      = _date_range(date_from, date_to)
        total_jobs = max(len(cameras) * len(dates), 1)
        done_jobs  = 0

        self._log(
            f"Bắt đầu: {len(cameras)} camera × {len(dates)} ngày  "
            f"| max/ngày={max_per_day or '∞'}  max/giờ={max_per_hour or '∞'}  max/cam={max_per_cam or '∞'}"
        )

        for cam in cameras:
            if self._stop_ev.is_set():
                break
            cam_saved = 0

            for dt in dates:
                if self._stop_ev.is_set():
                    break
                self.pause_event.wait()

                day_path  = source / cam / str(dt.year) / str(dt.month) / str(dt.day)
                done_jobs += 1

                if not day_path.exists():
                    self._stat({"progress": done_jobs / total_jobs, "saved": self._saved})
                    continue

                # Liệt kê ảnh trong ngày
                try:
                    files = [
                        f for f in day_path.iterdir()
                        if f.is_file() and f.suffix.lower() in IMAGE_EXTS
                    ]
                except Exception as e:
                    self._log(f"[LỖI] Đọc {cam}/{dt.strftime('%Y-%m-%d')}: {e}")
                    self._errors += 1
                    continue

                # Lọc theo loại ảnh (suffix trong tên file)
                if img_types:
                    files = [f for f in files
                             if any(t in f.stem.lower() for t in img_types)]

                files.sort(key=lambda f: f.name)

                # Giới hạn theo giờ rồi theo ngày
                if max_per_hour > 0:
                    files = _limit_by_hour(files, max_per_hour)
                if max_per_day > 0:
                    files = _spread_sample(files, max_per_day)

                # Giới hạn tổng theo camera
                if max_per_cam > 0:
                    remaining = max_per_cam - cam_saved
                    if remaining <= 0:
                        self._log(f"[{cam}] Đạt max/cam={max_per_cam}, bỏ các ngày còn lại")
                        done_jobs += len(dates) - dates.index(dt) - 1
                        break
                    files = files[:remaining]

                out_day = output / cam / dt.strftime("%Y-%m-%d")
                out_day.mkdir(parents=True, exist_ok=True)

                day_n = 0
                for f in files:
                    if self._stop_ev.is_set():
                        break
                    self.pause_event.wait()
                    dst = out_day / f.name
                    if dst.exists():
                        self._skipped += 1
                        continue
                    try:
                        shutil.copy2(f, dst)
                        self._saved  += 1
                        cam_saved    += 1
                        day_n        += 1
                        if sleep_sec > 0:
                            time.sleep(sleep_sec)
                    except Exception as e:
                        self._log(f"[LỖI] Copy {f.name}: {e}")
                        self._errors += 1

                if day_n:
                    self._log(f"[{cam}] {dt.strftime('%Y-%m-%d')}: {day_n} ảnh → {out_day}")

                self._stat({
                    "progress": done_jobs / total_jobs,
                    "saved":    self._saved,
                    "skipped":  self._skipped,
                    "errors":   self._errors,
                    "camera":   cam,
                    "date":     dt.strftime("%Y-%m-%d"),
                })

        self._log(
            f"Xong: {self._saved} đã lưu  |  {self._skipped} bỏ qua  |  {self._errors} lỗi"
        )
        if self._signal_done:
            self._stat({
                "done":    True,
                "saved":   self._saved,
                "skipped": self._skipped,
                "errors":  self._errors,
            })
