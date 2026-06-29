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
        """Tạo danh sách event cần tải — thuật toán 2 pha.

        Pha 1 — phân phối đều:
          Vòng qua tất cả slot, mỗi vòng lấy 1 event/slot cho đến khi
          slot đạt target_per_slot.  Slot ít ảnh nhất được ưu tiên.

        Pha 2 — bù thiếu (chỉ khi max_total > 0):
          Nếu tổng < max_total, tiếp tục lấy từ slot còn event (bỏ
          giới hạn target) cho đến khi đủ max_total hoặc hết event.

        Ví dụ: target=5, max_total=10, slot A có 100 SK, slot B có 1 SK
          Pha 1 → A×5 + B×1 = 6
          Pha 2 → A×4 thêm = 10  ✓

        Frontier priority:
          base=10.0 nếu event sau thời điểm cuối đã tải (mở rộng)
          base= 0.5 nếu event trước frontier (backfill)
        """
        from collections import defaultdict
        frontier_map = self._db.get_frontier(self._source)
        cov    = self._db.get_coverage(self._source)
        by_s   = cov["by_slot"]
        events = self._db.get_events(self._source, downloaded=0)
        if not events:
            return []

        # Nhóm event theo slot, gán base priority
        slot_events: dict = defaultdict(list)
        for e in events:
            mi     = e.get("minute") or 0
            slot_i = self.get_slot_idx(mi)
            key    = (e.get("lane", ""), e.get("vtype", ""),
                      e.get("date", ""), e.get("hour") or 0, slot_i)
            date        = e.get("date", "")
            event_dt    = e.get("dt", "") or ""
            frontier_dt = frontier_map.get(date, "")
            if frontier_dt and event_dt and event_dt <= frontier_dt:
                base = 0.5
            else:
                base = 10.0
            e["_base"]       = base
            e["_slot_key"]   = key
            e["is_backfill"] = bool(frontier_dt and event_dt and event_dt <= frontier_dt)
            e["slot_idx"]    = slot_i
            slot_events[key].append(e)

        # Trong mỗi slot: expand trước, backfill sau
        for v in slot_events.values():
            v.sort(key=lambda x: x["_base"], reverse=True)

        # Thứ tự slot: slot nhiều event expand → ưu tiên trước
        def _slot_score(k):
            es = slot_events[k]
            return sum(e["_base"] for e in es) / max(1, len(es))
        all_keys = sorted(slot_events.keys(), key=_slot_score, reverse=True)

        slot_taken = {k: 0 for k in slot_events}
        result: list = []

        def _take_one(key) -> bool:
            taken = slot_taken[key]
            es    = slot_events[key]
            if taken >= len(es):
                return False
            e  = es[taken]
            dl = by_s.get(key, 0)
            e["priority_score"] = e["_base"] / (dl + taken + 1)
            result.append(e)
            slot_taken[key] = taken + 1
            return True

        # ── Pha 1: phân phối đều đến target_per_slot ──────────────────
        progressed = True
        while progressed:
            progressed = False
            for key in all_keys:
                dl    = by_s.get(key, 0)
                taken = slot_taken[key]
                if dl + taken >= target_per_slot:
                    continue
                if _take_one(key):
                    progressed = True
                if max_total > 0 and len(result) >= max_total:
                    return result

        # ── Pha 2: bù thiếu nếu max_total chưa đạt ───────────────────
        if max_total > 0 and len(result) < max_total:
            progressed = True
            while progressed:
                progressed = False
                for key in all_keys:
                    if _take_one(key):
                        progressed = True
                    if len(result) >= max_total:
                        return result

        return result

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
