"""IParkingRunnerMixin — dispatch, parallel run, polling, progress cho IParkingImageTab."""
import json
import queue
import re
import threading
import time
from datetime import datetime
from pathlib import Path

from datetime import timedelta

from ...core.constants import ACCENT, ACCENT2, TEXT, DIM, F_MAIN, F_BOLD, F_MONO
from .iparking_constants import _VTYPE_ORDER
from .lotte_image import LotteWorker, _SharedLaneState
from .parkingv6_image import Parkingv6Worker, _P6SharedLaneState
from .parkingv8_image import Parkingv8Worker


class IParkingRunnerMixin:
    """Mixin chứa toàn bộ logic start/parallel/polling/progress/log."""

    # ── Khởi tạo chạy ────────────────────────────────────────────────────────

    def _prepare_run(self):
        self._clear_queues()
        self._all_thread_stats.clear()
        self._parallel_workers.clear()
        self._running = True
        self._paused  = False
        self._pause_event.set()
        self._run_start_time = time.monotonic()
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.pause_btn.config(state="normal", text="⏸  Tạm dừng", fg=TEXT)
        self.retry_btn.config(state="disabled")
        self.pbar.config(value=0)
        self.pct_lbl.config(text="0%")
        self.eta_lbl.config(text="ETA: --:--")
        self.item_lbl.config(text="")
        self.status_lbl.config(text="Đang chạy...", fg=ACCENT)

    def _clear_queues(self):
        for _q in (self._log_q, self._stat_q):
            while True:
                try: _q.get_nowait()
                except queue.Empty: break

    def _get_common_cfg(self) -> dict:
        checked = [vt for vt, var in self._vtype_vars.items() if var.get()]
        return {
            "output_dir":     self.out_var.get().strip(),
            "page_size":      self.page_size_var.get(),
            "max_pages":      self.max_pages_var.get(),
            "sleep":          self.sleep_var.get(),
            "max_per_lane":   self.max_per_lane_var.get(),
            "max_per_cat":    self.max_per_cat_var.get(),
            "max_per_buoi":   self.max_per_buoi_var.get(),
            "collect_bad":    self.collect_bad_var.get(),
            "only_gt":        self.only_gt_var.get(),
            "allowed_vtypes": checked if len(checked) < len(_VTYPE_ORDER) else [],
        }

    # ── Time-slicing helper ───────────────────────────────────────────────────

    @staticmethod
    def _split_time_windows(from_str: str, to_str: str, n: int) -> list:
        """Chia [from_str, to_str] thành n window đều nhau.
        Trả về list[(d_from, d_to, label)] — cùng format _day_list().
        Dùng khi n_pending_days < n_threads.
        """
        fmt = "%Y-%m-%dT%H:%M:%S"
        def _parse(s: str) -> "datetime":
            from datetime import datetime as _dt
            for f in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try: return _dt.strptime(s[:19], f)
                except ValueError: pass
            return _dt.now()
        from_dt = _parse(from_str)
        to_dt   = _parse(to_str)
        total_s = max(1, (to_dt - from_dt).total_seconds())
        slice_s = total_s / n
        result  = []
        for i in range(n):
            s = from_dt + timedelta(seconds=i * slice_s)
            e = from_dt + timedelta(seconds=(i + 1) * slice_s)
            if i == n - 1:
                e = to_dt
            label = (s.strftime("%Y-%m-%d/%H:%M")
                     if s.date() == e.date()
                     else s.strftime("%Y-%m-%d"))
            result.append((s.strftime(fmt), e.strftime(fmt), label))
        return result

    # ── Start dispatch ────────────────────────────────────────────────────────

    def _start_lotte(self, from_d, to_d, out):
        from_t = from_d.replace(" ", "T")
        to_t   = to_d.replace(" ", "T")
        cfg = self._get_common_cfg()
        cfg.update({
            "from_date":    from_t,
            "to_date":      to_t,
            "use_minio":    self.l_use_minio.get(),
            "parallel":     self.parallel_var.get(),
            "api_base":     self.l_api.get().strip(),
            "username":     self.l_user.get().strip(),
            "password":     self.l_pass.get().strip(),
            "minio_ep":     self.l_mep.get().strip(),
            "minio_bucket": self.l_mbk.get().strip(),
            "minio_ak":     self.l_mak.get().strip(),
            "minio_sk":     self.l_msk.get().strip(),
            "kw_toan_canh": self.l_kw_toan_canh.get().strip(),
            "kw_xe_may":    self.l_kw_xe_may.get().strip(),
            "kw_xe_dap":    self.l_kw_xe_dap.get().strip(),
            "kw_o_to":      self.l_kw_o_to.get().strip(),
            "keyword":      self.l_keyword_var.get().strip(),
        })
        self._last_cfg = cfg
        self._log(f"[Lotte] Bắt đầu: {from_t}  →  {to_t}")
        self._log(f"Lưu vào: {out}  |  MinIO: {cfg['use_minio']}  |  Luồng: {cfg['parallel']}")
        n = cfg.get("parallel", 1)
        if n > 1:
            self._thread = threading.Thread(
                target=self._run_parallel_lotte, args=(cfg, n), daemon=True)
        else:
            self._worker = LotteWorker(cfg, self._log_q, self._stat_q,
                                       pause_event=self._pause_event)
            self._thread = threading.Thread(target=self._run_worker, daemon=True)
        self._thread.start()

    def _start_p8(self, from_d, to_d, out):
        cfg = self._get_common_cfg()
        cfg.update({
            "from_date":     from_d,
            "to_date":       to_d,
            "event_source":  self.p8_source_var.get(),
            "img_mode":      self.p8_img_mode_var.get(),
            "grant_type":    self.p8_grant_var.get(),
            "login_url":     self.p8_login_url.get().strip(),
            "api_url":       self.p8_api_url.get().strip(),
            "client_id":     self.p8_client_id.get().strip(),
            "client_secret": self.p8_client_secret.get().strip(),
            "username":      self.p8_user.get().strip(),
            "password":      self.p8_pass.get().strip(),
            "keyword":       self.p8_keyword_var.get().strip(),
        })
        n = self.parallel_var.get()
        cfg.update({"parallel": n})
        self._last_cfg = cfg
        self._log(f"[Parkingv8] Bắt đầu: {from_d}  →  {to_d}")
        self._log(f"Nguồn: {cfg['event_source']}  |  Grant: {cfg['grant_type']}  |  Luồng: {n}  |  Lưu: {out}")
        if n > 1:
            self._thread = threading.Thread(
                target=self._run_parallel_p8, args=(cfg, n), daemon=True)
        else:
            self._worker = Parkingv8Worker(cfg, self._log_q, self._stat_q,
                                           pause_event=self._pause_event)
            self._thread = threading.Thread(target=self._run_worker, daemon=True)
        self._thread.start()

    def _start_p6(self, from_d, to_d, out):
        from tkinter import messagebox
        token = self.p6_token.get().strip()
        if not token:
            messagebox.showerror("Thiếu token",
                                 "Vui lòng nhập Bearer Token trong phần Nâng cao.")
            self._on_done_reset()
            return
        from_t = from_d.replace(" ", "T")
        to_t   = to_d.replace(" ", "T")
        cfg = self._get_common_cfg()
        cfg.update({
            "from_date":    from_t,
            "to_date":      to_t,
            "use_minio":    self.p6_use_minio.get(),
            "parallel":     self.parallel_var.get(),
            "event_source": self.p6_event_source_var.get(),
            "api_url":      self.p6_api.get().strip(),
            "token":        token,
            "minio_ep":     self.p6_mep.get().strip(),
            "minio_bucket": self.p6_mbk.get().strip(),
            "minio_ak":     self.p6_mak.get().strip(),
            "minio_sk":     self.p6_msk.get().strip(),
            "keyword":      self.p6_keyword_var.get().strip(),
        })
        self._last_cfg = cfg
        self._log(f"[Parkingv6] Bắt đầu: {from_t}  →  {to_t}")
        self._log(f"Nguồn: {cfg['event_source']}  |  MinIO: {cfg['use_minio']}  |  Lưu: {out}")
        n = cfg.get("parallel", 1)
        if n > 1:
            self._thread = threading.Thread(
                target=self._run_parallel_p6, args=(cfg, n), daemon=True)
        else:
            self._worker = Parkingv6Worker(cfg, self._log_q, self._stat_q,
                                           pause_event=self._pause_event)
            self._thread = threading.Thread(target=self._run_worker, daemon=True)
        self._thread.start()

    def _on_done_reset(self):
        self._running = False
        self._pause_event.set()
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.pause_btn.config(state="disabled")
        self.status_lbl.config(text="Sẵn sàng", fg=ACCENT2)

    def _run_worker(self):
        try:
            self._worker.run()
        except Exception as exc:
            self._log_q.put(f"[LỖI] {exc}")
            self._log_q.put("__DONE__")

    # ── Retry ─────────────────────────────────────────────────────────────────

    def _retry_failed(self):
        from tkinter import messagebox
        if not self._failed_items or self._running:
            if self._running:
                messagebox.showwarning("Đang chạy",
                                       "Vui lòng chờ lần chạy hiện tại kết thúc.")
            return
        items = list(self._failed_items)
        self._failed_items.clear()
        self.retry_btn.config(state="disabled")
        self._hide_dashboard()
        cfg = self._last_cfg.copy()
        cfg["retry_items"] = items
        self._prepare_run()
        self._log(f"Thử lại {len(items)} ảnh lỗi...")
        src = self._last_source
        if src == "LotteImage":
            self._worker = LotteWorker(cfg, self._log_q, self._stat_q,
                                       pause_event=self._pause_event)
        elif src == "Parkingv8":
            self._worker = Parkingv8Worker(cfg, self._log_q, self._stat_q,
                                           pause_event=self._pause_event)
        elif src == "Parkingv6":
            self._worker = Parkingv6Worker(cfg, self._log_q, self._stat_q,
                                           pause_event=self._pause_event)
        else:
            return
        self._thread = threading.Thread(target=self._run_worker, daemon=True)
        self._thread.start()

    # ── Parallel runners ──────────────────────────────────────────────────────

    def _run_parallel_lotte(self, cfg, n):
        try:
            out    = Path(cfg["output_dir"])
            from_d = cfg["from_date"]
            to_d   = cfg["to_date"]
            all_days  = LotteWorker._day_list(from_d, to_d)
            done_days = set()
            hist_f = out / LotteWorker._HISTORY_FILE
            try:
                if hist_f.exists():
                    done_days = set(json.loads(hist_f.read_text(encoding="utf-8")))
                    self._log_q.put(f"Lịch sử: {len(done_days)} ngày đã tải trước đó.")
            except Exception:
                pass
            pending = [d for d in all_days if d[2] not in done_days]
            skipped = len(all_days) - len(pending)
            self._log_q.put(
                f"Tổng: {len(all_days)} ngày | {n} luồng | page_size={cfg['page_size']}")
            if skipped:
                self._log_q.put(f"Bỏ qua {skipped} ngày đã tải.")
            if not pending:
                self._log_q.put("Tất cả ngày đã tải. Không có việc gì.")
                self._log_q.put("__DONE__"); return
            if len(pending) >= n:
                groups = [[] for _ in range(n)]
                for i, day in enumerate(pending):
                    groups[i % n].append(day)
                for tid, g in enumerate(groups, 1):
                    if g:
                        self._log_q.put(
                            f"[T{tid}] Được giao {len(g)} ngày: {g[0][2]} → {g[-1][2]}")
            else:
                actual_from = pending[0][0]
                actual_to   = pending[-1][1]
                windows = IParkingRunnerMixin._split_time_windows(actual_from, actual_to, n)
                groups  = [[w] for w in windows]
                self._log_q.put(
                    f"⏱ Time-slicing: {len(pending)} ngày < {n} luồng → {n} cửa sổ thời gian")
                for tid, w in enumerate(windows, 1):
                    self._log_q.put(f"[T{tid}] {w[2]}  ({w[0][11:16]} → {w[1][11:16]})")
            shared = _SharedLaneState()
            workers = []
            for tid, day_group in enumerate(groups, 1):
                if not day_group:
                    continue
                w = LotteWorker(cfg, self._log_q, self._stat_q,
                                pause_event=self._pause_event,
                                thread_id=tid, days_list=day_group,
                                shared=shared, send_done=False,
                                global_total_days=len(pending))
                workers.append(w)
            self._parallel_workers = workers
            threads = [threading.Thread(target=w.run, daemon=True) for w in workers]
            for t in threads: t.start()
            for t in threads: t.join()
            total = {k: sum(w.stats.get(k, 0) for w in workers)
                     for k in ("event", "found", "saved", "skipped", "error", "bad_saved")}
            sep = "═" * 52
            self._log_q.put(f"\n{sep}")
            self._log_q.put(
                f"TỔNG KẾT ({n} luồng, {len(pending)} ngày): "
                f"SK:{total['event']}  Tìm:{total['found']}  Lưu:{total['saved']}  "
                f"Xấu:{total['bad_saved']}  Bỏ:{total['skipped']}  Lỗi:{total['error']}")
            self._log_q.put(sep)
        except Exception as exc:
            self._log_q.put(f"[LỖI] {exc}")
        finally:
            self._log_q.put("__DONE__")

    def _run_parallel_p6(self, cfg, n):
        try:
            out    = Path(cfg["output_dir"])
            from_d = cfg["from_date"]
            to_d   = cfg["to_date"]
            all_days  = Parkingv6Worker._day_list(from_d, to_d)
            done_days = set()
            hist_f = out / Parkingv6Worker._HISTORY_FILE
            try:
                if hist_f.exists():
                    done_days = set(json.loads(hist_f.read_text(encoding="utf-8")))
                    self._log_q.put(f"Lịch sử: {len(done_days)} ngày đã tải trước đó.")
            except Exception:
                pass
            pending = [d for d in all_days if d[2] not in done_days]
            skipped = len(all_days) - len(pending)
            self._log_q.put(
                f"Tổng: {len(all_days)} ngày | {n} luồng | page_size={cfg['page_size']}")
            if skipped:
                self._log_q.put(f"Bỏ qua {skipped} ngày đã tải.")
            if not pending:
                self._log_q.put("Tất cả ngày đã tải. Không có việc gì.")
                self._log_q.put("__DONE__"); return
            if len(pending) >= n:
                groups = [[] for _ in range(n)]
                for i, day in enumerate(pending):
                    groups[i % n].append(day)
                for tid, g in enumerate(groups, 1):
                    if g:
                        self._log_q.put(
                            f"[T{tid}] Được giao {len(g)} ngày: {g[0][2]} → {g[-1][2]}")
            else:
                actual_from = pending[0][0]
                actual_to   = pending[-1][1]
                windows = IParkingRunnerMixin._split_time_windows(actual_from, actual_to, n)
                groups  = [[w] for w in windows]
                self._log_q.put(
                    f"⏱ Time-slicing: {len(pending)} ngày < {n} luồng → {n} cửa sổ thời gian")
                for tid, w in enumerate(windows, 1):
                    self._log_q.put(f"[T{tid}] {w[2]}  ({w[0][11:16]} → {w[1][11:16]})")
            shared = _P6SharedLaneState()
            workers = []
            for tid, day_group in enumerate(groups, 1):
                if not day_group:
                    continue
                w = Parkingv6Worker(cfg, self._log_q, self._stat_q,
                                    pause_event=self._pause_event,
                                    thread_id=tid, days_list=day_group,
                                    shared=shared, send_done=False,
                                    global_total_days=len(pending))
                workers.append(w)
            self._parallel_workers = workers
            threads = [threading.Thread(target=w.run, daemon=True) for w in workers]
            for t in threads: t.start()
            for t in threads: t.join()
            total = {k: sum(w.stats.get(k, 0) for w in workers)
                     for k in ("event", "found", "saved", "skipped", "error", "bad_saved")}
            sep = "═" * 52
            self._log_q.put(f"\n{sep}")
            self._log_q.put(
                f"TỔNG KẾT ({n} luồng, {len(pending)} ngày): "
                f"SK:{total['event']}  Tìm:{total['found']}  Lưu:{total['saved']}  "
                f"Xấu:{total['bad_saved']}  Bỏ:{total['skipped']}  Lỗi:{total['error']}")
            self._log_q.put(sep)
        except Exception as exc:
            self._log_q.put(f"[LỖI] {exc}")
        finally:
            self._log_q.put("__DONE__")

    def _run_parallel_p8(self, cfg, n):
        try:
            from .parkingv8_image import _P8SharedLaneState
            out    = Path(cfg["output_dir"])
            from_d = cfg["from_date"]
            to_d   = cfg["to_date"]
            all_days  = Parkingv8Worker._day_list(from_d, to_d)
            done_days = set()
            hist_f = out / Parkingv8Worker._HISTORY_FILE
            try:
                if hist_f.exists():
                    done_days = set(json.loads(hist_f.read_text(encoding="utf-8")))
                    self._log_q.put(f"Lịch sử: {len(done_days)} ngày đã tải trước đó.")
            except Exception:
                pass
            pending = [d for d in all_days if d[2] not in done_days]
            skipped = len(all_days) - len(pending)
            self._log_q.put(
                f"Tổng: {len(all_days)} ngày | {n} luồng | page_size={cfg['page_size']}")
            if skipped:
                self._log_q.put(f"Bỏ qua {skipped} ngày đã tải.")
            if not pending:
                self._log_q.put("Tất cả ngày đã tải. Không có việc gì.")
                self._log_q.put("__DONE__"); return
            if len(pending) >= n:
                groups = [[] for _ in range(n)]
                for i, day in enumerate(pending):
                    groups[i % n].append(day)
                for tid, g in enumerate(groups, 1):
                    if g:
                        self._log_q.put(
                            f"[T{tid}] Được giao {len(g)} ngày: {g[0][2]} → {g[-1][2]}")
            else:
                actual_from = pending[0][0]
                actual_to   = pending[-1][1]
                windows = IParkingRunnerMixin._split_time_windows(actual_from, actual_to, n)
                groups  = [[w] for w in windows]
                self._log_q.put(
                    f"⏱ Time-slicing: {len(pending)} ngày < {n} luồng → {n} cửa sổ thời gian")
                for tid, w in enumerate(windows, 1):
                    self._log_q.put(f"[T{tid}] {w[2]}  ({w[0][11:16]} → {w[1][11:16]})")
            shared = _P8SharedLaneState()
            workers = []
            for tid, day_group in enumerate(groups, 1):
                if not day_group:
                    continue
                w = Parkingv8Worker(cfg, self._log_q, self._stat_q,
                                    pause_event=self._pause_event,
                                    thread_id=tid, days_list=day_group,
                                    shared=shared, send_done=False,
                                    global_total_days=len(pending))
                workers.append(w)
            self._parallel_workers = workers
            threads = [threading.Thread(target=w.run, daemon=True) for w in workers]
            for t in threads: t.start()
            for t in threads: t.join()
            total = {k: sum(w.stats.get(k, 0) for w in workers)
                     for k in ("event", "found", "saved", "skipped", "error", "bad_saved")}
            sep = "═" * 52
            self._log_q.put(f"\n{sep}")
            self._log_q.put(
                f"TỔNG KẾT ({n} luồng, {len(pending)} ngày): "
                f"SK:{total['event']}  Tìm:{total['found']}  Lưu:{total['saved']}  "
                f"Xấu:{total['bad_saved']}  Bỏ:{total['skipped']}  Lỗi:{total['error']}")
            self._log_q.put(sep)
        except Exception as exc:
            self._log_q.put(f"[LỖI] {exc}")
        finally:
            self._log_q.put("__DONE__")

    # ── Polling ───────────────────────────────────────────────────────────────

    def _poll(self):
        batch, done_flag = [], False
        for _ in range(200):
            try:
                msg = self._log_q.get_nowait()
                if msg == "__DONE__":
                    done_flag = True
                    break
                else:
                    batch.append(msg)
            except queue.Empty:
                break
        if batch:
            self._log_batch(batch)
        if done_flag:
            self._on_done()
        _last_s = None
        try:
            while True:
                s = self._stat_q.get_nowait()
                tid = s.get("thread_id", 0)
                if tid > 0:
                    self._all_thread_stats[tid] = s
                _last_s = s
        except queue.Empty:
            pass
        if _last_s is not None:
            disp = self._aggregate_stats() if self._all_thread_stats else _last_s
            self._last_stat = disp
            self._update_progress(disp)
            self._refresh_stat_lbl(disp)
        self.root.after(200, self._poll)

    def _aggregate_stats(self) -> dict:
        all_s = list(self._all_thread_stats.values())
        total_days = all_s[0].get("total_days", 0) if all_s else 0
        items = [x.get("current_item", "") for x in all_s if x.get("current_item")]
        return {
            "event":      sum(x.get("event",     0) for x in all_s),
            "found":      sum(x.get("found",     0) for x in all_s),
            "saved":      sum(x.get("saved",     0) for x in all_s),
            "skipped":    sum(x.get("skipped",   0) for x in all_s),
            "error":      sum(x.get("error",     0) for x in all_s),
            "bad_saved":  sum(x.get("bad_saved", 0) for x in all_s),
            "page":       sum(x.get("page",      0) for x in all_s),
            "day_idx":    sum(x.get("day_idx",   0) for x in all_s),
            "total_days": total_days,
            "day_label":  "",
            "thread_id":  0,
            "current_item": " | ".join(
                f"T{x.get('thread_id','?')}:{v}" for x, v in zip(all_s, items)),
            "total_found": sum(x.get("total_found", x.get("found", 0)) for x in all_s),
            "_parallel":  len(all_s),
        }

    def _update_progress(self, s: dict):
        saved = s.get("saved", 0)
        found = s.get("found", 0)
        total = s.get("total_found", found) or found
        item  = s.get("current_item", "")
        if item:
            self.item_lbl.config(text=f"Đang xử lý: {item}")
        failed = s.get("failed_items")
        if failed:
            for it in failed:
                if it not in self._failed_items:
                    self._failed_items.append(it)
        if total > 0:
            pct = min(int(saved * 100 / total), 99)
            self.pbar.config(value=pct)
            self.pct_lbl.config(text=f"{pct}%")
            elapsed = time.monotonic() - (self._run_start_time or time.monotonic())
            if saved > 0:
                eta = int(elapsed / saved * (total - saved))
                m, sec = divmod(eta, 60)
                self.eta_lbl.config(text=f"ETA: {m:02d}:{sec:02d}")
        elif s.get("page", 0) > 0:
            pct = min(s["page"] % 100, 99)
            self.pbar.config(value=pct)
            self.pct_lbl.config(text=f"~{pct}%")

    def _refresh_stat_lbl(self, s: dict):
        n_threads  = s.get("_parallel", 0)
        day_idx    = s.get("day_idx", 0)
        total_days = s.get("total_days", 0)
        bad_part   = f"  |  Xấu: {s['bad_saved']}" if s.get("bad_saved") else ""
        if n_threads > 1:
            day_info = (f"[{n_threads} luồng] Ngày: {day_idx}/{total_days}  |  "
                        if total_days else f"[{n_threads} luồng]  ")
        elif total_days:
            day_info = f"Ngày: {s.get('day_label','')} ({day_idx}/{total_days})  |  "
        else:
            day_info = ""
        self.stat_lbl.config(
            text=(f"{day_info}"
                  f"Trang: {s.get('page',0)}  |  "
                  f"SK: {s.get('event',0)}  |  "
                  f"Tìm: {s.get('found',0)}  |  "
                  f"Lưu: {s.get('saved',0)}"
                  f"{bad_part}  |  "
                  f"Bỏ: {s.get('skipped',0)}  |  "
                  f"Lỗi: {s.get('error',0)}"))

    # ── Log ───────────────────────────────────────────────────────────────────

    def _log(self, msg: str):
        self._log_batch([msg])

    def _log_batch(self, msgs: list):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_txt.configure(state="normal")
        for msg in msgs:
            line = f"[{ts}] {msg}\n"
            m = re.match(r'\[T(\d+)\]', msg)
            if m:
                self.log_txt.insert("end", line, (f"T{m.group(1)}",))
            else:
                self.log_txt.insert("end", line)
        lines = int(self.log_txt.index("end-1c").split(".")[0])
        if lines > self._LOG_MAX:
            self.log_txt.delete("1.0", f"{lines - self._LOG_MAX}.0")
        self.log_txt.see("end")
        self.log_txt.configure(state="disabled")
