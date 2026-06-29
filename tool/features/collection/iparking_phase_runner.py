"""IParkingPhaseMixin — 3-phase workflow (Scan → Analyse → Download) + Preview."""


class IParkingPhaseMixin:
    """Mixin cho chế độ 3-bước: Scan metadata → Phân tích coverage → Tải ảnh."""

    # ── EventDB helper ────────────────────────────────────────────────────────

    def _get_or_create_db(self):
        """Tạo hoặc lấy EventDB cho thư mục output hiện tại."""
        from .event_db import EventDB
        from pathlib import Path
        out = Path(self.out_var.get().strip())
        if not hasattr(self, '_event_db') or getattr(self, '_db_path', None) != out:
            self._event_db = EventDB(out)
            self._db_path  = out
        return self._event_db

    # ── Bước 1: Scan metadata ─────────────────────────────────────────────────

    def _start_scan(self):
        """Chạy workers ở mode scan_only — chỉ thu thập metadata vào EventDB."""
        from tkinter import messagebox
        import os
        out = self.out_var.get().strip()
        if not out:
            messagebox.showerror("Lỗi", "Vui lòng chọn thư mục lưu."); return
        os.makedirs(out, exist_ok=True)
        db    = self._get_or_create_db()
        src   = self.source_var.get()
        from_d = self.from_var.get().strip()
        to_d   = self.to_var.get().strip()
        if not from_d or not to_d:
            messagebox.showerror("Lỗi", "Vui lòng điền đủ thời gian."); return
        self._prepare_run()
        self._log(f"[SCAN] Chế độ scan-only: {from_d} → {to_d}")
        cfg = self._get_common_cfg()
        cfg.update({"from_date": from_d.replace(" ", "T"),
                    "to_date":   to_d.replace(" ", "T")})
        if src == "LotteImage":
            from .lotte_image import LotteWorker
            cfg.update({"api_base": self.l_api.get().strip(),
                        "username": self.l_user.get().strip(),
                        "password": self.l_pass.get().strip(),
                        "use_minio": self.l_use_minio.get(),
                        "minio_ep": self.l_mep.get().strip(),
                        "minio_bucket": self.l_mbk.get().strip(),
                        "minio_ak": self.l_mak.get().strip(),
                        "minio_sk": self.l_msk.get().strip(),
                        "kw_toan_canh": self.l_kw_toan_canh.get().strip(),
                        "kw_xe_may": self.l_kw_xe_may.get().strip(),
                        "kw_xe_dap": self.l_kw_xe_dap.get().strip(),
                        "kw_o_to": self.l_kw_o_to.get().strip(),
                        "keyword": self.l_keyword_var.get().strip()})
            self._worker = LotteWorker(cfg, self._log_q, self._stat_q,
                                       pause_event=self._pause_event,
                                       mode='scan_only', event_db=db)
        elif src == "Parkingv6":
            from .parkingv6_image import Parkingv6Worker
            cfg.update({"api_url": self.p6_api.get().strip(),
                        "token": self.p6_token.get().strip(),
                        "use_minio": self.p6_use_minio.get(),
                        "minio_ep": self.p6_mep.get().strip(),
                        "minio_bucket": self.p6_mbk.get().strip(),
                        "minio_ak": self.p6_mak.get().strip(),
                        "minio_sk": self.p6_msk.get().strip(),
                        "event_source": self.p6_event_source_var.get(),
                        "keyword": self.p6_keyword_var.get().strip()})
            self._worker = Parkingv6Worker(cfg, self._log_q, self._stat_q,
                                           pause_event=self._pause_event,
                                           mode='scan_only', event_db=db)
        else:
            messagebox.showinfo("Thông báo",
                                "Scan-only hiện chỉ hỗ trợ LotteImage và Parkingv6.")
            self._on_done_reset(); return
        import threading as _t
        self._thread = _t.Thread(target=self._run_worker, daemon=True)
        self._thread.start()

    # ── Bước 2: Phân tích coverage ────────────────────────────────────────────

    def _show_analysis(self):
        """Mở cửa sổ phân tích coverage từ EventDB."""
        from tkinter import messagebox, Toplevel, ttk, Label, Frame, BOTH, Y
        from .event_planner import EventPlanner
        from ...core.constants import BG, ACCENT, TEXT, DIM, F_MAIN, F_BOLD
        out = self.out_var.get().strip()
        if not out:
            messagebox.showerror("Lỗi", "Vui lòng chọn thư mục lưu."); return
        db      = self._get_or_create_db()
        src     = self.source_var.get()
        src_key = {"LotteImage": "lotte", "Parkingv8": "p8",
                   "Parkingv6": "p6"}.get(src, "lotte")
        planner = EventPlanner(db, src_key)
        result  = planner.analyze()
        win = Toplevel(self.root)
        win.title(f"Phân tích Coverage — {src}")
        win.configure(bg=BG)
        win.geometry("600x420")
        win.resizable(True, True)
        s = result["summary"]
        info = (f"Tổng scan: {s['total_scanned']}  |  "
                f"Đã tải: {s['downloaded']}  |  Chờ: {s['pending']}  |  "
                f"Coverage: {result['coverage_pct']}%")
        Label(win, text=info, bg=BG, fg=ACCENT, font=F_BOLD,
              wraplength=580).pack(padx=10, pady=8, anchor="w")
        Label(win, text=f"Ngày: {', '.join(result['dates'][:5])}"
              + ("..." if len(result['dates']) > 5 else ""),
              bg=BG, fg=DIM, font=F_MAIN).pack(padx=10, anchor="w")
        Label(win, text=f"Làn: {', '.join(result['lanes'])}",
              bg=BG, fg=DIM, font=F_MAIN).pack(padx=10, anchor="w")
        Label(win, text="Top 10 slot thiếu ảnh nhất:",
              bg=BG, fg=TEXT, font=F_BOLD).pack(padx=10, pady=(12, 4), anchor="w")
        tv = ttk.Treeview(win, columns=("lane", "vtype", "h", "slot", "miss"),
                          show="headings", height=10)
        for col, hdr, w in [("lane", "Làn", 150), ("vtype", "Loại", 100),
                             ("h", "Giờ", 60), ("slot", "Slot", 80), ("miss", "Thiếu", 70)]:
            tv.heading(col, text=hdr); tv.column(col, width=w)
        for (lane, vtype, h, si), miss in result["worst_slots"]:
            label = planner.slot_label(h, si)
            tv.insert("", "end", values=(lane, vtype, f"{h:02d}h", label, miss))
        tv.pack(fill=BOTH, expand=True, padx=10, pady=4)

    # ── Bước 3: Tải theo kế hoạch ─────────────────────────────────────────────

    def _start_download_from_plan(self):
        """Tải ảnh theo kế hoạch từ EventDB (chế độ 3-bước)."""
        from tkinter import messagebox
        from .event_planner import EventPlanner
        out = self.out_var.get().strip()
        if not out:
            messagebox.showerror("Lỗi", "Vui lòng chọn thư mục lưu."); return
        db  = self._get_or_create_db()
        src = self.source_var.get()
        src_key = {"LotteImage": "lotte", "Parkingv8": "p8",
                   "Parkingv6": "p6"}.get(src, "lotte")
        planner = EventPlanner(db, src_key)
        target  = getattr(self, 'target_per_slot_var', None)
        tgt_n   = target.get() if target else 5
        plan    = planner.make_download_plan(target_per_slot=tgt_n)
        if not plan:
            messagebox.showinfo("Không có dữ liệu",
                                "DB trống hoặc đã tải đủ. Chạy Scan trước."); return
        self._prepare_run()
        self._log(f"[PLAN] Tải theo kế hoạch: {len(plan)} sự kiện (target={tgt_n}/slot)")
        cfg = self._get_common_cfg()
        cfg.update({"plan_events": plan, "from_date": "", "to_date": ""})
        if src == "LotteImage":
            from .lotte_image import LotteWorker
            cfg.update({"api_base": self.l_api.get().strip(),
                        "username": self.l_user.get().strip(),
                        "password": self.l_pass.get().strip(),
                        "use_minio": self.l_use_minio.get(),
                        "minio_ep": self.l_mep.get().strip(),
                        "minio_bucket": self.l_mbk.get().strip(),
                        "minio_ak": self.l_mak.get().strip(),
                        "minio_sk": self.l_msk.get().strip(),
                        "kw_toan_canh": self.l_kw_toan_canh.get().strip(),
                        "kw_xe_may": self.l_kw_xe_may.get().strip(),
                        "kw_xe_dap": self.l_kw_xe_dap.get().strip(),
                        "kw_o_to": self.l_kw_o_to.get().strip(),
                        "keyword": self.l_keyword_var.get().strip()})
            self._worker = LotteWorker(cfg, self._log_q, self._stat_q,
                                       pause_event=self._pause_event,
                                       mode='plan', event_db=db)
        elif src == "Parkingv6":
            from .parkingv6_image import Parkingv6Worker
            cfg.update({"api_url": self.p6_api.get().strip(),
                        "token": self.p6_token.get().strip(),
                        "use_minio": self.p6_use_minio.get(),
                        "minio_ep": self.p6_mep.get().strip(),
                        "minio_bucket": self.p6_mbk.get().strip(),
                        "minio_ak": self.p6_mak.get().strip(),
                        "minio_sk": self.p6_msk.get().strip(),
                        "event_source": self.p6_event_source_var.get(),
                        "keyword": self.p6_keyword_var.get().strip()})
            self._worker = Parkingv6Worker(cfg, self._log_q, self._stat_q,
                                           pause_event=self._pause_event,
                                           mode='plan', event_db=db)
        else:
            messagebox.showinfo("Thông báo",
                                "Plan-download hiện chỉ hỗ trợ LotteImage và Parkingv6.")
            self._on_done_reset(); return
        import threading as _t
        self._thread = _t.Thread(target=self._run_worker, daemon=True)
        self._thread.start()

    # ── Preview popup ─────────────────────────────────────────────────────────

    def _show_preview(self):
        """Scan thử 1 ngày, hiển thị phân phối giờ + ước tính ETA."""
        from tkinter import messagebox, Toplevel, Label, Frame, BOTH, Y, W
        from tkinter import ttk
        import threading as _t
        from datetime import datetime as _dt, timedelta as _td
        from ...core.constants import BG, ACCENT, ACCENT2, TEXT, DIM, F_MAIN, F_BOLD

        out = self.out_var.get().strip()
        src = self.source_var.get()
        if not out:
            messagebox.showerror("Lỗi", "Vui lòng chọn thư mục lưu."); return
        if self._running:
            messagebox.showwarning("Đang chạy", "Đợi lần chạy hiện tại kết thúc."); return

        from_str = self.from_var.get().strip()
        try:
            fd = _dt.fromisoformat(from_str[:10])
        except Exception:
            fd = _dt.utcnow().replace(hour=0, minute=0, second=0)
        sample_from = fd.strftime("%Y-%m-%dT00:00:00")
        sample_to   = (fd + _td(days=1)).strftime("%Y-%m-%dT00:00:00")

        win = Toplevel(self.root)
        win.title(f"Xem trước — {src}  ({fd.strftime('%Y-%m-%d')})")
        win.configure(bg=BG)
        win.geometry("560x480")
        win.resizable(True, True)

        lbl_status = Label(win, text="⏳ Đang scan 1 ngày mẫu...",
                           bg=BG, fg=ACCENT, font=F_BOLD)
        lbl_status.pack(pady=(18, 6))
        pbar = ttk.Progressbar(win, mode="indeterminate", length=480)
        pbar.pack(padx=20)
        pbar.start(12)
        result_frm = Frame(win, bg=BG)
        result_frm.pack(fill=BOTH, expand=True, padx=16, pady=8)

        def _do_scan():
            try:
                import time as _time
                cfg = self._get_common_cfg()
                cfg.update({"from_date": sample_from, "to_date": sample_to,
                             "page_size": 200, "max_pages": 5})
                hour_counts: dict = {}
                total = 0
                import queue as _q
                t0 = _time.monotonic()

                if src == "LotteImage":
                    from .lotte_image import LotteWorker
                    lq, sq = _q.Queue(), _q.Queue()
                    cfg.update({"api_base": self.l_api.get().strip(),
                                "username": self.l_user.get().strip(),
                                "password": self.l_pass.get().strip(),
                                "use_minio": False,
                                "keyword": self.l_keyword_var.get().strip()})
                    db = self._get_or_create_db()
                    LotteWorker(cfg, lq, sq, mode='scan_only', event_db=db).run()
                    for e in db.get_events('lotte', downloaded=None):
                        if str(e.get("date", "")).startswith(fd.strftime("%Y-%m-%d")):
                            h = e.get("hour", 0) or 0
                            hour_counts[h] = hour_counts.get(h, 0) + 1
                            total += 1
                elif src == "Parkingv6":
                    from .parkingv6_image import Parkingv6Worker
                    lq, sq = _q.Queue(), _q.Queue()
                    cfg.update({"api_url": self.p6_api.get().strip(),
                                "token": self.p6_token.get().strip(),
                                "use_minio": False,
                                "event_source": self.p6_event_source_var.get(),
                                "keyword": self.p6_keyword_var.get().strip()})
                    db = self._get_or_create_db()
                    Parkingv6Worker(cfg, lq, sq, mode='scan_only', event_db=db).run()
                    for e in db.get_events('p6', downloaded=None):
                        if str(e.get("date", "")).startswith(fd.strftime("%Y-%m-%d")):
                            h = e.get("hour", 0) or 0
                            hour_counts[h] = hour_counts.get(h, 0) + 1
                            total += 1
                else:
                    win.after(0, lambda: lbl_status.config(
                        text=f"⚠ Preview chưa hỗ trợ nguồn {src}", fg=DIM))
                    win.after(0, pbar.stop); return

                elapsed_1day = _time.monotonic() - t0
                n_days  = max(1, (_dt.fromisoformat(
                    self.to_var.get().strip()[:10]) - fd).days)
                sleep_s = self.sleep_var.get() if hasattr(self, 'sleep_var') else 0.5
                # scan ETA: extrapolate from measured 1-day sample
                scan_eta = n_days * elapsed_1day
                # download ETA: min 0.1s/event (API latency) even when sleep=0
                per_event_s = max(0.1, sleep_s)
                tgt = self.tgt_var.get() if hasattr(self, 'tgt_var') else 5
                # ước tính số event thực sự cần tải (có target/slot giới hạn)
                n_slots = 288  # 24h × 12 slot/h (5-phút)
                est_downloads = min(total, n_slots * tgt) * n_days
                download_eta = est_downloads * per_event_s
                eta_s   = scan_eta + download_eta
                eta_str = f"{int(eta_s//3600)}h {int((eta_s%3600)//60)}m"

                def _render():
                    pbar.stop(); pbar.pack_forget()
                    dl_info = f"~{est_downloads:,} ảnh cần tải"
                    lbl_status.config(
                        text=f"Mẫu: {total:,} SK/ngày  |  {n_days} ngày  |  "
                             f"{dl_info}  |  ETA ≈ {eta_str}", fg=ACCENT2)
                    Label(result_frm, text="Phân phối theo giờ:",
                          bg=BG, fg=TEXT, font=F_BOLD).pack(anchor=W, pady=(4, 4))
                    tv = ttk.Treeview(result_frm,
                                      columns=("hour", "count", "bar"),
                                      show="headings", height=min(18, 24))
                    tv.heading("hour", text="Giờ")
                    tv.heading("count", text="Số SV")
                    tv.heading("bar", text="Tỉ lệ")
                    tv.column("hour", width=60, anchor="center")
                    tv.column("count", width=80, anchor="center")
                    tv.column("bar", width=340)
                    max_c = max(hour_counts.values()) if hour_counts else 1
                    for h in range(24):
                        c = hour_counts.get(h, 0)
                        bar = "█" * int(c / max_c * 30) if c else ""
                        tv.insert("", "end", values=(f"{h:02d}:00", c, bar))
                    sv = ttk.Scrollbar(result_frm, orient="vertical",
                                       command=tv.yview)
                    tv.configure(yscrollcommand=sv.set)
                    sv.pack(side="right", fill=Y)
                    tv.pack(fill=BOTH, expand=True)

                win.after(0, _render)
            except Exception as exc:
                win.after(0, lambda: lbl_status.config(
                    text=f"Lỗi: {exc}", fg="#ff8844"))
                win.after(0, pbar.stop)

        _t.Thread(target=_do_scan, daemon=True).start()
