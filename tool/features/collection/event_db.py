"""EventDB — SQLite cache cho iParking image downloader.

Thay thế .lotte_done.json / .p8_done.json / .p6_done.json.
Lưu metadata sự kiện để tái dùng và planning time-diversity.
"""
import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source        TEXT    NOT NULL,
    event_id      TEXT,
    date          TEXT    NOT NULL,
    hour          INTEGER NOT NULL,
    minute        INTEGER NOT NULL,
    lane          TEXT    NOT NULL,
    vtype         TEXT    NOT NULL,
    plate         TEXT,
    has_gt        INTEGER DEFAULT 0,
    image_refs    TEXT,
    downloaded    INTEGER DEFAULT 0,
    save_path     TEXT,
    scanned_at    TEXT,
    downloaded_at TEXT,
    UNIQUE(source, event_id)
);

CREATE TABLE IF NOT EXISTS scan_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source      TEXT    NOT NULL,
    date        TEXT    NOT NULL,
    hour_from   INTEGER NOT NULL DEFAULT 0,
    hour_to     INTEGER NOT NULL DEFAULT 23,
    status      TEXT    NOT NULL,
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
"""


class EventDB:
    DB_FILENAME = ".iparking_cache.db"

    def __init__(self, output_dir: Path):
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        self._path = output_dir / self.DB_FILENAME
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(_SCHEMA_SQL)
            self._conn.commit()
        self._migrate_legacy(output_dir)

    # ── Scan log ──────────────────────────────────────────────────────────────

    def is_scanned(self, source: str, date: str,
                   hour_from: int = 0, hour_to: int = 23) -> bool:
        sql = ("SELECT 1 FROM scan_log "
               "WHERE source=? AND date=? AND hour_from=? AND hour_to=? AND status='done'")
        with self._lock:
            row = self._conn.execute(sql, (source, date, hour_from, hour_to)).fetchone()
        return row is not None

    def mark_scan_start(self, source: str, date: str,
                        hour_from: int = 0, hour_to: int = 23):
        sql = ("INSERT OR REPLACE INTO scan_log"
               "(source, date, hour_from, hour_to, status, scanned_at) "
               "VALUES (?,?,?,?,'scanning',?)")
        now = datetime.now().isoformat()
        with self._lock:
            self._conn.execute(sql, (source, date, hour_from, hour_to, now))
            self._conn.commit()

    def mark_scan_done(self, source: str, date: str,
                       hour_from: int = 0, hour_to: int = 23,
                       count: int = 0):
        sql = ("INSERT OR REPLACE INTO scan_log"
               "(source, date, hour_from, hour_to, status, event_count, scanned_at) "
               "VALUES (?,?,?,?,'done',?,?)")
        now = datetime.now().isoformat()
        with self._lock:
            self._conn.execute(sql, (source, date, hour_from, hour_to, count, now))
            self._conn.commit()

    def get_scanned_dates(self, source: str) -> set:
        sql = ("SELECT DISTINCT date FROM scan_log "
               "WHERE source=? AND hour_from=0 AND hour_to=23 AND status='done'")
        with self._lock:
            rows = self._conn.execute(sql, (source,)).fetchall()
        return {r["date"] for r in rows}

    # ── Events ────────────────────────────────────────────────────────────────

    def insert_events(self, source: str, events: list) -> int:
        """Batch insert. Trả về số dòng thực sự chèn (bỏ qua duplicate)."""
        if not events:
            return 0
        sql = ("INSERT OR IGNORE INTO events"
               "(source, event_id, date, hour, minute, lane, vtype, plate,"
               " has_gt, image_refs, scanned_at) "
               "VALUES (?,?,?,?,?,?,?,?,?,?,?)")
        rows = []
        for e in events:
            rows.append((
                source,
                str(e.get("event_id") or ""),
                str(e.get("date") or ""),
                int(e.get("hour") or 0),
                int(e.get("minute") or 0),
                str(e.get("lane") or ""),
                str(e.get("vtype") or ""),
                str(e.get("plate") or ""),
                int(bool(e.get("has_gt"))),
                json.dumps(e.get("image_refs") or [], ensure_ascii=False),
                str(e.get("scanned_at") or datetime.now().isoformat()),
            ))
        with self._lock:
            cur = self._conn.executemany(sql, rows)
            self._conn.commit()
            return cur.rowcount

    def mark_downloaded(self, source: str, event_id: str, save_path: str):
        sql = ("UPDATE events SET downloaded=1, save_path=?, downloaded_at=? "
               "WHERE source=? AND event_id=?")
        now = datetime.now().isoformat()
        with self._lock:
            self._conn.execute(sql, (save_path, now, source, event_id))
            self._conn.commit()

    def get_events(self, source: str, date: str = None, lane: str = None,
                   vtype: str = None, downloaded: int = None,
                   hour_from: int = None, hour_to: int = None) -> list:
        clauses = ["source=?"]
        params  = [source]
        if date:
            clauses.append("date=?"); params.append(date)
        if lane:
            clauses.append("lane=?"); params.append(lane)
        if vtype:
            clauses.append("vtype=?"); params.append(vtype)
        if downloaded is not None:
            clauses.append("downloaded=?"); params.append(downloaded)
        if hour_from is not None:
            clauses.append("hour>=?"); params.append(hour_from)
        if hour_to is not None:
            clauses.append("hour<=?"); params.append(hour_to)
        sql = f"SELECT * FROM events WHERE {' AND '.join(clauses)}"
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["image_refs"] = json.loads(d.get("image_refs") or "[]")
            except Exception:
                d["image_refs"] = []
            result.append(d)
        return result

    # ── Analytics ─────────────────────────────────────────────────────────────

    def get_coverage(self, source: str) -> dict:
        """Phân tích coverage theo (lane, vtype, date, hour, minute_bucket).
        minute_bucket = minute // 5  (mỗi slot = 5 phút → 12 slot/giờ).
        """
        sql = ("SELECT lane, vtype, date, hour, minute, downloaded "
               "FROM events WHERE source=?")
        with self._lock:
            rows = self._conn.execute(sql, (source,)).fetchall()
        by_slot:  dict = {}  # (lane, vtype, date, hour, mb): count_downloaded
        by_hour:  dict = {}  # (lane, vtype, hour): {'total': N, 'downloaded': M}
        lanes:    set  = set()
        vtypes:   set  = set()
        dates:    set  = set()
        for r in rows:
            lane, vtype, date, hour, minute, dl = (
                r["lane"], r["vtype"], r["date"], r["hour"], r["minute"], r["downloaded"])
            mb  = minute // 5
            key = (lane, vtype, date, hour, mb)
            if dl:
                by_slot[key] = by_slot.get(key, 0) + 1
            hk = (lane, vtype, hour)
            if hk not in by_hour:
                by_hour[hk] = {"total": 0, "downloaded": 0}
            by_hour[hk]["total"] += 1
            if dl:
                by_hour[hk]["downloaded"] += 1
            lanes.add(lane); vtypes.add(vtype); dates.add(date)
        return {
            "by_slot":  by_slot,
            "by_hour":  by_hour,
            "lanes":    sorted(lanes),
            "vtypes":   sorted(vtypes),
            "dates":    sorted(dates),
        }

    def count_summary(self, source: str) -> dict:
        with self._lock:
            total = self._conn.execute(
                "SELECT COUNT(*) FROM events WHERE source=?", (source,)).fetchone()[0]
            downloaded = self._conn.execute(
                "SELECT COUNT(*) FROM events WHERE source=? AND downloaded=1",
                (source,)).fetchone()[0]
        return {
            "total_scanned": total,
            "downloaded":    downloaded,
            "pending":       max(0, total - downloaded),
        }

    # ── Migration ─────────────────────────────────────────────────────────────

    def _migrate_legacy(self, output_dir: Path):
        for fname, source in [(".lotte_done.json", "lotte"),
                               (".p8_done.json",    "p8"),
                               (".p6_done.json",    "p6")]:
            f = output_dir / fname
            if not f.exists():
                continue
            if self.get_scanned_dates(source):
                continue  # DB đã có data → không migrate
            try:
                dates = json.loads(f.read_text(encoding="utf-8"))
                for d in dates:
                    self.mark_scan_done(source, d, 0, 23, 0)
            except Exception:
                pass

    def close(self):
        with self._lock:
            self._conn.close()
