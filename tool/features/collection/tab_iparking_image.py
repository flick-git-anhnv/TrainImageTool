import os
import queue
import threading
import time
from datetime import datetime
from pathlib import Path
from tkinter import *
from tkinter import filedialog, messagebox, ttk

from ...core.constants import BG, CARD, ACCENT, ACCENT2, TEXT, DIM, F_MAIN, F_BOLD, F_MONO
from ...core.imports import _REQUESTS_OK, _CV2_OK
from ...core.settings import _bind_cfg, _cfg_dir, _push_history, _get_history
from ...utils.bad_image_viewer import BadImageViewer
from ...utils.migrate_structure import open_migrate_window as _open_migrate_window
from .iparking_constants import _THREAD_COLORS
from .iparking_settings_panels import IParkingSettingsMixin
from .iparking_runner import IParkingRunnerMixin
from .iparking_phase_runner import IParkingPhaseMixin
from .iparking_stats_ui import IParkingStatsMixin


class IParkingImageTab(Frame, IParkingSettingsMixin, IParkingRunnerMixin,
                       IParkingPhaseMixin, IParkingStatsMixin):
    SOURCES  = ["LotteImage", "Parkingv8", "Parkingv6"]
    _LOG_MAX = 2000

    def __init__(self, master, root):
        super().__init__(master, bg=BG)
        self.root = root
        self._worker           = None
        self._thread           = None
        self._log_q            = queue.Queue()
        self._stat_q           = queue.Queue()
        self._running          = False
        self._paused           = False
        self._pause_event      = threading.Event()
        self._pause_event.set()
        self._failed_items     = []
        self._run_start_time   = None
        self._last_stat        = {}
        self._last_cfg         = {}
        self._last_source      = "LotteImage"
        self._all_thread_stats = {}
        self._parallel_workers = []
        self._build()
        self._poll()

    # ── Layout skeleton ───────────────────────────────────────────────────────

    def _build(self):
        top = Frame(self, bg=CARD, padx=16, pady=8)
        top.pack(fill=X)
        Label(top, text="iParking Image — Thu thập ảnh từ hệ thống iParking",
              bg=CARD, fg=TEXT, font=F_BOLD).pack(side=LEFT)
        if not _REQUESTS_OK:
            Label(top, text="  ⚠ pip install requests",
                  bg=CARD, fg="#ff8844", font=("Segoe UI", 9)).pack(side=LEFT, padx=8)
        if not _CV2_OK:
            Label(top, text="  ⚠ pip install opencv-python numpy",
                  bg=CARD, fg="#ff8844", font=("Segoe UI", 9)).pack(side=LEFT, padx=4)

        src_bar = Frame(self, bg=CARD, padx=16, pady=6)
        src_bar.pack(fill=X)
        Label(src_bar, text="Nguồn dữ liệu:", bg=CARD, fg=TEXT, font=F_BOLD).pack(
            side=LEFT, padx=(0, 10))
        self.source_var = StringVar(value="LotteImage")
        _bind_cfg("ip.source", self.source_var)
        src_cb = ttk.Combobox(src_bar, textvariable=self.source_var,
                              values=self.SOURCES, state="readonly",
                              width=16, font=F_BOLD)
        src_cb.pack(side=LEFT)
        src_cb.bind("<<ComboboxSelected>>", self._on_source_change)
        self._src_desc_lbl = Label(src_bar, text="", bg=CARD, fg=DIM,
                                   font=("Segoe UI", 9))
        self._src_desc_lbl.pack(side=LEFT, padx=(14, 0))

        canvas = Canvas(self, bg=BG, highlightthickness=0)
        vsb = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=RIGHT, fill=Y)
        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        inner = Frame(canvas, bg=BG)
        cwin = canvas.create_window((0, 0), window=inner, anchor="nw")

        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(cwin, width=e.width))
        inner.bind("<Configure>",
                   lambda _: canvas.configure(scrollregion=canvas.bbox("all")))

        _mw_entered = [False]

        def _mw(ev): canvas.yview_scroll(int(-1 * (ev.delta / 120)), "units")

        def _on_enter(_):
            _mw_entered[0] = True
            canvas.bind_all("<MouseWheel>", _mw)

        def _on_leave(_):
            _mw_entered[0] = False
            canvas.after(20, lambda: canvas.unbind_all("<MouseWheel>") if not _mw_entered[0] else None)

        canvas.bind("<Enter>", _on_enter)
        canvas.bind("<Leave>", _on_leave)

        p = inner
        self._build_time(p)
        self._build_output(p)
        self._build_common_limits(p)

        self._src_container = Frame(p, bg=BG)
        self._src_container.pack(fill=X)
        self._lotte_frm = Frame(self._src_container, bg=BG)
        self._p8_frm    = Frame(self._src_container, bg=BG)
        self._p6_frm    = Frame(self._src_container, bg=BG)
        self._build_lotte_settings(self._lotte_frm)
        self._build_p8_settings(self._p8_frm)
        self._build_p6_settings(self._p6_frm)

        self._build_phase_controls(p)
        self._check_auto_3step()
        self._build_controls(p)
        self._build_progress(p)
        self._build_dashboard(p)
        self._build_log(p)
        self._on_source_change()

    # ── Controls ──────────────────────────────────────────────────────────────

    def _build_controls(self, p):
        f = Frame(p, bg=BG, padx=10, pady=6)
        f.pack(fill=X)
        self.start_btn = Button(
            f, text="▶  Bắt đầu", command=self._start,
            bg=ACCENT, fg="white", font=F_BOLD,
            activebackground="#c04010", activeforeground="white",
            relief="flat", padx=22, pady=7, cursor="hand2")
        self.start_btn.pack(side=LEFT, padx=(0, 6))
        self.stop_btn = Button(
            f, text="⬛  Dừng", command=self._stop,
            bg=DIM, fg=BG, font=F_BOLD, relief="flat",
            padx=22, pady=7, state=DISABLED, cursor="hand2")
        self.stop_btn.pack(side=LEFT, padx=(0, 6))
        self.pause_btn = Button(
            f, text="⏸  Tạm dừng", command=self._toggle_pause,
            bg=CARD, fg=TEXT, font=F_BOLD,
            activebackground=ACCENT2, activeforeground="white",
            relief="flat", padx=16, pady=7, state=DISABLED, cursor="hand2")
        self.pause_btn.pack(side=LEFT, padx=(0, 6))
        self.retry_btn = Button(
            f, text="↺  Thử lại lỗi", command=self._retry_failed,
            bg=CARD, fg=TEXT, font=F_BOLD,
            activebackground=ACCENT, activeforeground="white",
            relief="flat", padx=16, pady=7, state=DISABLED, cursor="hand2")
        self.retry_btn.pack(side=LEFT, padx=(0, 6))
        Button(f, text="Thống kê", command=self._show_stats,
               bg=ACCENT2, fg="white", font=F_BOLD,
               activebackground="#5a4fa0", activeforeground="white",
               relief="flat", padx=18, pady=7, cursor="hand2").pack(side=LEFT, padx=(0, 16))
        self.collect_bad_var = BooleanVar(value=False)
        _bind_cfg("ip.collect_bad", self.collect_bad_var)
        Checkbutton(f, text="Lấy ảnh xấu", variable=self.collect_bad_var,
                    bg=BG, fg=TEXT, selectcolor="#251C53",
                    activebackground=BG, font=F_MAIN, cursor="hand2").pack(
            side=LEFT, padx=(0, 4))
        Button(f, text="Xem ảnh xấu", command=self._show_bad_images,
               bg=ACCENT2, fg="white", font=F_MAIN,
               activebackground="#5a4fa0", activeforeground="white",
               relief="flat", padx=10, pady=4, cursor="hand2").pack(
            side=LEFT, padx=(0, 4))
        Button(f, text="Tổng hợp", command=self._consolidate,
               bg="#251C53", fg="white", font=F_MAIN,
               activebackground=ACCENT2, activeforeground="white",
               relief="flat", padx=10, pady=4, cursor="hand2").pack(
            side=LEFT, padx=(0, 4))
        Button(f, text="Hiệu chỉnh", command=self._migrate_folder,
               bg="#2d4a1e", fg="#a0d080", font=F_MAIN,
               activebackground="#3a6028", activeforeground="white",
               relief="flat", padx=10, pady=4, cursor="hand2").pack(
            side=LEFT, padx=(0, 4))
        Button(f, text="🗑 Xóa tiến độ", command=self._clear_progress,
               bg="#3a1a1a", fg="#e08080", font=F_MAIN,
               activebackground="#5a2020", activeforeground="white",
               relief="flat", padx=10, pady=4, cursor="hand2").pack(
            side=LEFT, padx=(0, 4))
        self.status_lbl = Label(f, text="Sẵn sàng", font=F_MAIN,
                                fg=ACCENT2, bg=BG)
        self.status_lbl.pack(side=RIGHT)

    def _build_progress(self, p):
        f = Frame(p, bg=BG, padx=10, pady=2)
        f.pack(fill=X)
        self._sep(f, "Tiến độ")
        pbar_row = Frame(f, bg=BG)
        pbar_row.pack(fill=X)
        self.pbar = ttk.Progressbar(pbar_row, mode="determinate",
                                    style="K.Horizontal.TProgressbar", maximum=100)
        self.pbar.pack(side=LEFT, fill=X, expand=True, padx=(0, 8))
        self.pct_lbl = Label(pbar_row, text="0%", font=F_MONO,
                             fg=ACCENT, bg=BG, width=5, anchor=E)
        self.pct_lbl.pack(side=LEFT)
        self.eta_lbl = Label(pbar_row, text="ETA: --:--", font=F_MONO,
                             fg=DIM, bg=BG, width=12, anchor=W)
        self.eta_lbl.pack(side=LEFT, padx=(6, 0))
        self.item_lbl = Label(f, text="", font=F_MONO, fg=DIM, bg=BG, anchor=W)
        self.item_lbl.pack(fill=X, pady=(2, 0))
        self.stat_lbl = Label(
            f,
            text="Trang: 0  |  SK: 0  |  Tìm: 0  |  Lưu: 0  |  Bỏ: 0  |  Lỗi: 0",
            font=F_MONO, fg=TEXT, bg=BG)
        self.stat_lbl.pack(anchor=W, pady=(2, 0))

    def _build_dashboard(self, p):
        self._dash_frame   = Frame(p, bg=CARD, padx=10, pady=6)
        self._dash_visible = False

    def _build_log(self, p):
        f = Frame(p, bg=BG, padx=10, pady=4)
        f.pack(fill=BOTH, expand=True)
        self._log_frame = f
        self._sep(f, "Nhật ký")
        inner = Frame(f, bg=BG)
        inner.pack(fill=BOTH, expand=True)
        inner.columnconfigure(0, weight=1)
        inner.rowconfigure(0, weight=1)
        self.log_txt = Text(inner, height=12, font=F_MONO,
                            bg="#16162a", fg="#d4d4d4",
                            relief="flat", wrap=WORD,
                            insertbackground="#d4d4d4", state=DISABLED)
        self.log_txt.grid(row=0, column=0, sticky=NSEW)
        for i, color in enumerate(_THREAD_COLORS, 1):
            self.log_txt.tag_configure(f"T{i}", foreground=color)
        sb = ttk.Scrollbar(inner, command=self.log_txt.yview)
        sb.grid(row=0, column=1, sticky=NS)
        self.log_txt["yscrollcommand"] = sb.set
        Button(inner, text="Xóa log",
               command=lambda: (self.log_txt.configure(state=NORMAL),
                                self.log_txt.delete("1.0", END),
                                self.log_txt.configure(state=DISABLED)),
               bg=CARD, fg=DIM, font=F_MAIN, relief="flat",
               padx=8, cursor="hand2").grid(row=1, column=0, sticky=W, pady=(4, 0))

    # ── Source switch ─────────────────────────────────────────────────────────

    def _on_source_change(self, *_):
        src = self.source_var.get()
        for frm in (self._lotte_frm, self._p8_frm, self._p6_frm):
            frm.pack_forget()
        if src == "LotteImage":
            self._lotte_frm.pack(fill=X)
            self._src_desc_lbl.config(
                text="iParking Lotte · phân loại theo từ khóa · không có ảnh cắt biển số")
            self._time_hint_lbl.config(text="UTC  ·  Việt Nam = UTC+7")
            self._struct_lbl.config(
                text="Cấu trúc: <out>/<o_to|xe_may|xe_dap>/anh_toan_canh|anh_xe|anh_bsx/<YYYY-MM-DD>/<sang|trua|chieu|toi>/<làn>/HHmmss_BSX.jpg")
        elif src == "Parkingv8":
            self._p8_frm.pack(fill=X)
            self._src_desc_lbl.config(
                text="iParking v8 · vehicleType integer · có ảnh cắt biển số (*_bsx_cut)")
            self._time_hint_lbl.config(text="UTC  ·  Việt Nam = UTC+7")
            self._struct_lbl.config(
                text="Cấu trúc: <out>/<o_to|xe_may|xe_dap>/anh_toan_canh|anh_xe|anh_bsx/<YYYY-MM-DD>/<sang|trua|chieu|toi>/<làn>/HHmmss_BSX_type.jpg")
        elif src == "Parkingv6":
            self._p6_frm.pack(fill=X)
            self._src_desc_lbl.config(
                text="iParking v6 · vehicleType integer · MinIO · Bearer token")
            self._time_hint_lbl.config(text="UTC  ·  Việt Nam = UTC+7  (API nhận UTC)")
            self._struct_lbl.config(
                text="Cấu trúc: <out>/<o_to|xe_may|xe_dap>/anh_toan_canh|anh_xe|anh_bsx/<YYYY-MM-DD>/<sang|trua|chieu|toi>/<làn>/HHmmss_BSX.jpg")

    # ── Actions ───────────────────────────────────────────────────────────────

    def _browse(self):
        d = filedialog.askdirectory(title="Chọn thư mục lưu ảnh",
                                    initialdir=_cfg_dir("ip.out"))
        if d:
            self.out_var.set(d)
            _push_history("h.ip.out", d)
            self._out_combo["values"] = _get_history("h.ip.out")

    def _open_out(self):
        p = self.out_var.get().strip()
        if p and os.path.isdir(p):
            os.startfile(p)

    def _toggle_pause(self):
        if not self._running:
            return
        if self._paused:
            self._paused = False
            self._pause_event.set()
            self.pause_btn.config(text="⏸  Tạm dừng", fg=TEXT)
            self.status_lbl.config(text="Đang chạy...", fg=ACCENT)
            self._log("Tiếp tục...")
        else:
            self._paused = True
            self._pause_event.clear()
            self.pause_btn.config(text="▶  Tiếp tục", fg=ACCENT)
            self.status_lbl.config(text="Tạm dừng", fg="#ffaa00")
            self._log("Tạm dừng — đang chờ item hiện tại hoàn tất...")

    def _stop(self):
        if self._worker:
            self._worker.stop()
        for w in self._parallel_workers:
            w.stop()
        self._running = False
        self._paused  = False
        self._pause_event.set()
        self.stop_btn.config(state=DISABLED)
        self.pause_btn.config(state=DISABLED, text="⏸  Tạm dừng", fg=TEXT)
        self.start_btn.config(state=NORMAL)
        self.pbar.config(value=0)
        self.pct_lbl.config(text="0%")
        self.eta_lbl.config(text="ETA: --:--")
        self.item_lbl.config(text="")
        self.status_lbl.config(text="Đã dừng", fg=DIM)

    def _on_done(self):
        if not self._running:
            return
        self._running = False
        self._paused  = False
        self._pause_event.set()
        self.pbar.config(value=100)
        self.pct_lbl.config(text="100%")
        self.eta_lbl.config(text="ETA: 00:00")
        self.item_lbl.config(text="")
        self.start_btn.config(state=NORMAL)
        self.stop_btn.config(state=DISABLED)
        self.pause_btn.config(state=DISABLED, text="⏸  Tạm dừng", fg=TEXT)
        self.status_lbl.config(text="Hoàn thành", fg=ACCENT2)
        if self._failed_items:
            self.retry_btn.config(state=NORMAL,
                                   text=f"↺  Thử lại {len(self._failed_items)} lỗi")
        self._show_dashboard(self._last_stat)
        self._refresh_db_status()

    def _start(self):
        if not _REQUESTS_OK:
            messagebox.showerror("Thiếu thư viện", "Vui lòng cài:\n  pip install requests")
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
            messagebox.showerror("Lỗi thư mục", str(e)); return
        src = self.source_var.get()
        self._last_source = src
        self._failed_items.clear()
        self._hide_dashboard()
        self._prepare_run()
        if src == "LotteImage":
            self._start_lotte(from_d, to_d, out)
        elif src == "Parkingv8":
            self._start_p8(from_d, to_d, out)
        elif src == "Parkingv6":
            self._start_p6(from_d, to_d, out)

    def _show_bad_images(self):
        out = Path(self.out_var.get().strip())
        if not out.exists():
            messagebox.showerror("Lỗi", "Thư mục không tồn tại."); return
        if hasattr(self, "_bad_win") and self._bad_win.winfo_exists():
            self._bad_win.lift(); return
        self._bad_win = BadImageViewer(self.root, out)

    def _consolidate(self):
        from .lotte_consolidate import ConsolidateWindow
        out = Path(self.out_var.get().strip())
        if not out.exists():
            messagebox.showerror("Lỗi", "Thư mục không tồn tại."); return
        if hasattr(self, "_consolidate_win") and self._consolidate_win.winfo_exists():
            self._consolidate_win.lift(); return
        self._consolidate_win = ConsolidateWindow(self.root, out)

    def _migrate_folder(self):
        out = Path(self.out_var.get().strip())
        if not out.exists():
            messagebox.showerror("Lỗi", "Thư mục không tồn tại."); return
        if hasattr(self, "_migrate_win") and self._migrate_win.winfo_exists():
            self._migrate_win.lift(); return
        self._migrate_win = _open_migrate_window(self.root, out)

    def _clear_progress(self):
        out = self.out_var.get().strip()
        if not out:
            messagebox.showerror("Lỗi", "Chưa chọn thư mục lưu ảnh."); return
        out_path = Path(out)
        history_files = [
            (".lotte_done.json", "LotteImage"),
            (".p6_done.json",    "Parkingv6"),
            (".p8_done.json",    "Parkingv8"),
        ]
        found = [(f, label) for f, label in history_files if (out_path / f).exists()]
        if not found:
            messagebox.showinfo("Xóa tiến độ",
                                "Không tìm thấy file tiến độ nào trong thư mục."); return
        names = "\n".join(f"  • {label} ({f})" for f, label in found)
        if not messagebox.askyesno("Xóa tiến độ cũ",
                                   f"Xóa tiến độ đã lưu của:\n{names}\n\n"
                                   "Lần chạy tiếp theo sẽ tải lại tất cả các ngày từ đầu.\nTiếp tục?"):
            return
        cleared = []
        for fname, label in found:
            try:
                (out_path / fname).unlink()
                cleared.append(label)
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không xóa được {fname}:\n{e}"); return
        self._log("🗑 Đã xóa tiến độ: " + ", ".join(cleared))
        messagebox.showinfo("Xóa tiến độ", "Đã xóa tiến độ: " + ", ".join(cleared))

    # ── Dashboard ─────────────────────────────────────────────────────────────

    def _show_dashboard(self, s: dict):
        if not self._dash_visible:
            self._dash_frame.pack(fill=X, padx=10, pady=(4, 2),
                                  before=self._log_frame)
            self._dash_visible = True
        for w in self._dash_frame.winfo_children():
            w.destroy()
        Label(self._dash_frame, text="Kết quả lần chạy",
              font=("Segoe UI", 9, "bold"), fg=ACCENT2, bg=CARD).pack(anchor=W)
        row = Frame(self._dash_frame, bg=CARD)
        row.pack(fill=X, pady=(4, 0))
        for label, val, color in [
            ("Tổng SK",  s.get("event",    0), TEXT),
            ("Tìm thấy", s.get("found",    0), TEXT),
            ("Đã lưu",   s.get("saved",    0), "#4caf50"),
            ("Bỏ qua",   s.get("skipped",  0), DIM),
            ("Lỗi",      s.get("error",    0), "#ff8844"),
            ("Ảnh xấu",  s.get("bad_saved",0), ACCENT2),
        ]:
            cell = Frame(row, bg="#251C53", padx=8, pady=4)
            cell.pack(side=LEFT, padx=(0, 6))
            Label(cell, text=str(val), font=("Segoe UI Semibold", 13),
                  fg=color, bg="#251C53").pack()
            Label(cell, text=label, font=("Segoe UI", 8),
                  fg=DIM, bg="#251C53").pack()
        if self._failed_items:
            Label(self._dash_frame,
                  text=f"{len(self._failed_items)} ảnh lỗi — nhấn 'Thử lại lỗi' để tải lại",
                  font=("Segoe UI", 8), fg="#ff8844", bg=CARD).pack(
                anchor=W, pady=(4, 0))

    def _hide_dashboard(self):
        if self._dash_visible:
            self._dash_frame.pack_forget()
            self._dash_visible = False
