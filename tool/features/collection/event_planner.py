"""EventPlanner — lên kế hoạch tải ảnh ưu tiên time-diversity.

Thuật toán Time-Rotating Sampling:
  Slot = slot_minutes phút (mặc định 5 phút → 12 slot/giờ)
  Priority score = 1 / (slot_count + 1)
  → slot ít ảnh = score cao = tải trước
"""
from .event_db import EventDB


class EventPlanner:
    def __init__(self, db: EventDB, source: str, slot_minutes: int = 5):
        self._db     = db
        self._source = source
        self._slot   = max(1, slot_minutes)

    # ── Public API ────────────────────────────────────────────────────────────

    def get_slot_idx(self, minute: int) -> int:
        return minute // self._slot

    def analyze(self) -> dict:
        """Phân tích coverage hiện tại.

        Trả về:
          gaps: [(lane, vtype, hour, slot_idx, avail, downloaded)]
          coverage_pct: float — % slot đã có ≥1 ảnh
          worst_slots: top 10 slot bị bỏ qua nhiều nhất
          summary: count_summary từ DB
        """
        cov    = self._db.get_coverage(self._source)
        by_h   = cov["by_hour"]
        by_s   = cov["by_slot"]
        n_slot = 60 // self._slot

        total_slots    = 0
        covered_slots  = 0
        gaps           = []
        slot_miss: dict = {}   # (lane, vtype, hour, slot_idx): avail-downloaded

        for (lane, vtype, hour), counts in by_h.items():
            avail = counts["total"]
            for si in range(n_slot):
                total_slots += 1
                k = (lane, vtype, hour, si)
                downloaded = sum(
                    v for (l, vt, _d, h, mb), v in by_s.items()
                    if l == lane and vt == vtype and h == hour and mb == si)
                if downloaded > 0:
                    covered_slots += 1
                slot_miss[k] = avail - downloaded
                if slot_miss[k] > 0:
                    gaps.append((lane, vtype, hour, si, avail, downloaded))

        gaps.sort(key=lambda x: x[4] - x[5], reverse=True)
        worst = sorted(slot_miss.items(), key=lambda kv: kv[1], reverse=True)[:10]
        cov_pct = (covered_slots / total_slots * 100) if total_slots > 0 else 0.0

        return {
            "gaps":         gaps,
            "coverage_pct": round(cov_pct, 1),
            "worst_slots":  worst,
            "summary":      self._db.count_summary(self._source),
            "lanes":        cov["lanes"],
            "vtypes":       cov["vtypes"],
            "dates":        cov["dates"],
        }

    def make_download_plan(self, target_per_slot: int = 5,
                           max_total: int = 0) -> list:
        """Tạo danh sách event cần tải theo thứ tự ưu tiên time-slot.

        priority_score = 1 / (slot_downloaded_count + 1)
        Sắp xếp descending → slot chưa có ảnh được tải trước.
        """
        cov    = self._db.get_coverage(self._source)
        by_s   = cov["by_slot"]
        events = self._db.get_events(self._source, downloaded=0)
        if not events:
            return []
        scored = []
        for e in events:
            mi      = e.get("minute") or 0
            slot_i  = self.get_slot_idx(mi)
            key     = (e.get("lane", ""), e.get("vtype", ""),
                       e.get("date", ""), e.get("hour") or 0, slot_i)
            slot_dl = by_s.get(key, 0)
            if slot_dl >= target_per_slot:
                continue   # slot đã đủ target
            score = 1.0 / (slot_dl + 1)
            e["priority_score"] = score
            e["slot_idx"]       = slot_i
            scored.append(e)
        scored.sort(key=lambda x: x["priority_score"], reverse=True)
        if max_total > 0:
            scored = scored[:max_total]
        return scored

    def get_next_batch(self, batch_size: int = 100) -> list:
        """Lấy batch tiếp theo chưa tải, ưu tiên slot under-represented."""
        plan = self.make_download_plan(max_total=batch_size)
        return plan

    def slot_label(self, hour: int, slot_idx: int) -> str:
        start_min = slot_idx * self._slot
        end_min   = min(59, start_min + self._slot - 1)
        return f"{hour:02d}:{start_min:02d}–{hour:02d}:{end_min:02d}"

    def coverage_matrix(self) -> dict:
        """Ma trận coverage để hiển thị UI.

        Trả về {(lane, vtype): {hour: {slot_idx: {'total': N, 'downloaded': M}}}}
        """
        cov  = self._db.get_coverage(self._source)
        by_h = cov["by_hour"]
        by_s = cov["by_slot"]
        n_slot = 60 // self._slot
        matrix: dict = {}
        for (lane, vtype, hour), counts in by_h.items():
            key = (lane, vtype)
            if key not in matrix:
                matrix[key] = {}
            matrix[key][hour] = {}
            for si in range(n_slot):
                dl = sum(
                    v for (l, vt, _d, h, mb), v in by_s.items()
                    if l == lane and vt == vtype and h == hour and mb == si)
                matrix[key][hour][si] = {
                    "total":      counts["total"],
                    "downloaded": dl,
                }
        return matrix
