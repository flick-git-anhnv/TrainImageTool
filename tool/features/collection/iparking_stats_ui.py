"""IParkingStatsMixin — cửa sổ thống kê ảnh đã lưu cho IParkingImageTab."""
import threading
from collections import Counter, defaultdict
from pathlib import Path
from tkinter import *
from tkinter import ttk

from ...core.constants import BG, CARD, ACCENT, ACCENT2, TEXT, DIM, F_MAIN, F_MONO
from .iparking_constants import _VTYPE_ORDER, _VTYPE_COLORS, _LANE_PALETTE


class IParkingStatsMixin:
    """Mixin chứa stats window, scan_stats, chart/table rendering."""

    _BUOI_DISP_ORDER = ["Sáng", "Trưa", "Chiều", "Tối"]
    _BUOI_RAW_MAP    = {"sang": "Sáng", "trua": "Trưa", "chieu": "Chiều", "toi": "Tối"}

    @staticmethod
    def _hour_to_buoi_disp(h: int) -> str:
        if h < 12: return "Sáng"
        if h < 14: return "Trưa"
        if h < 18: return "Chiều"
        return "Tối"

    # ── Entry point ───────────────────────────────────────────────────────────

    def _show_stats(self):
        out = Path(self.out_var.get().strip())
        if hasattr(self, "_stats_win") and self._stats_win.winfo_exists():
            self._stats_out = out
            self._stats_win.lift()
            self._stats_rebuild()
            return
        win = Toplevel(self.root)
        win.title("Thống kê ảnh đã lưu")
        win.configure(bg=BG)
        win.geometry("960x560")
        win.resizable(True, True)
        self._stats_win  = win
        self._stats_out  = out
        self._stats_view = StringVar(value="table")
        tb = Frame(win, bg=CARD, padx=10, pady=6)
        tb.pack(fill=X)
        Button(tb, text="Làm mới", command=self._stats_rebuild,
               bg=ACCENT, fg="white", font=F_MAIN,
               activebackground="#c04010", activeforeground="white",
               relief="flat", padx=14, pady=4, cursor="hand2").pack(side=LEFT)
        Frame(tb, bg=DIM, width=1).pack(side=LEFT, fill=Y, padx=14, pady=2)
        for lbl, val in [("Bảng", "table"), ("Biểu đồ", "chart")]:
            Radiobutton(tb, text=lbl, variable=self._stats_view, value=val,
                        bg=CARD, fg=TEXT, selectcolor="#251C53",
                        activebackground=CARD, font=F_MAIN, cursor="hand2",
                        command=self._stats_rebuild).pack(side=LEFT, padx=4)
        self._stats_body = Frame(win, bg=BG)
        self._stats_body.pack(fill=BOTH, expand=True)
        self._stats_rebuild()

    def _stats_rebuild(self):
        out = getattr(self, "_stats_out", Path(self.out_var.get().strip()))
        for w in self._stats_body.winfo_children():
            w.destroy()
        lbl = Label(self._stats_body, text="Đang quét...", bg=BG, fg=DIM, font=F_MAIN)
        lbl.pack(expand=True)

        def _worker():
            data = self._scan_stats(out)
            self.root.after(0, lambda: self._stats_populate(lbl, out, data))

        threading.Thread(target=_worker, daemon=True).start()

    def _stats_populate(self, loading_lbl, out, data):
        try:
            loading_lbl.destroy()
        except Exception:
            return
        if not data["detail"]:
            Label(self._stats_body,
                  text=f"Không tìm thấy ảnh trong:\n{out}",
                  bg=BG, fg=DIM, font=F_MAIN, justify=CENTER).pack(expand=True)
            return
        s = ttk.Style()
        s.configure("S.Treeview", background="#1e1e2e", foreground="#d4d4d4",
                    fieldbackground="#1e1e2e", rowheight=24, font=F_MONO)
        s.configure("S.Treeview.Heading", background="#251C53", foreground="white",
                    font=("Segoe UI", 9, "bold"))
        s.map("S.Treeview", background=[("selected", "#4A3F8C")])
        nb = ttk.Notebook(self._stats_body)
        nb.pack(fill=BOTH, expand=True, padx=8, pady=8)
        is_chart = self._stats_view.get() == "chart"
        self._stats_tab_summary(nb, data, is_chart)
        self._stats_tab_date(nb,    data, is_chart)
        self._stats_tab_buoi(nb,    data, is_chart)

    # ── Scan stats (static) ───────────────────────────────────────────────────

    @staticmethod
    def _scan_stats(out_path: Path) -> dict:
        detail  = Counter()
        by_date = defaultdict(Counter)
        buoi_raw = {"sang": "Sáng", "trua": "Trưa", "chieu": "Chiều", "toi": "Tối"}

        def _h2b(h):
            if h < 12: return "Sáng"
            if h < 14: return "Trưa"
            if h < 18: return "Chiều"
            return "Tối"

        if out_path.exists():
            for img in out_path.rglob("*.jpg"):
                try:
                    parts = img.relative_to(out_path).parts
                    if parts[0] in ("bad", "out", "train"):
                        continue
                    if len(parts) == 6:
                        p0, p1, p2, p3, p4, _ = parts
                        if p1.startswith("anh_"):
                            loai_xe, _, date_s, p3b, lan, _ = parts
                            buoi = buoi_raw.get(p3b) or (_h2b(int(p3b)) if p3b.isdigit() else "?")
                        else:
                            loai_xe, lan, _, date_s, p4b, _ = parts
                            buoi = buoi_raw.get(p4b) or (_h2b(int(p4b)) if p4b.isdigit() else "?")
                    elif len(parts) == 5:
                        loai_xe, _, date_s, p3, _ = parts
                        lan = ""
                        buoi = buoi_raw.get(p3) or (_h2b(int(p3)) if p3.isdigit() else "?")
                    elif len(parts) == 4:
                        loai_xe, _, date_s, fname = parts
                        lan = ""
                        h_s = fname[:2]
                        buoi = _h2b(int(h_s)) if h_s.isdigit() else "?"
                    else:
                        continue
                except Exception:
                    continue
                detail[(loai_xe, lan, buoi)] += 1
                by_date[date_s][(loai_xe, lan)] += 1

        return {"detail": dict(detail), "date": dict(by_date)}

    # ── Tree / chart helpers ──────────────────────────────────────────────────

    @staticmethod
    def _make_tree(parent, cols, col_widths, anchor_first="w"):
        f = Frame(parent, bg=BG)
        f.pack(fill=BOTH, expand=True, padx=4, pady=4)
        f.columnconfigure(0, weight=1)
        f.rowconfigure(0, weight=1)
        tree = ttk.Treeview(f, columns=cols, show="headings", style="S.Treeview")
        for i, (col, w) in enumerate(zip(cols, col_widths)):
            tree.heading(col, text=col)
            tree.column(col, width=w, minwidth=w,
                        anchor=anchor_first if i == 0 else "center")
        tree.tag_configure("total", background="#251C53", foreground="white")
        tree.tag_configure("odd",   background="#16162a")
        tree.tag_configure("even",  background="#1e1e2e")
        vsb = ttk.Scrollbar(f, orient=VERTICAL,   command=tree.yview)
        hsb = ttk.Scrollbar(f, orient=HORIZONTAL, command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        tree.grid(row=0, column=0, sticky=NSEW)
        vsb.grid(row=0, column=1, sticky=NS)
        hsb.grid(row=1, column=0, sticky=EW)
        return tree

    def _make_chart(self, parent, draw_fn):
        try:
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            fig = Figure(figsize=(9, 3.8), dpi=96, facecolor="#1e1e2e")
            ax  = fig.add_subplot(111, facecolor="#16162a")
            for spine in ax.spines.values():
                spine.set_color("#4A3F8C")
            ax.tick_params(colors="#d4d4d4", labelsize=8)
            draw_fn(ax)
            ax.legend(facecolor="#2a2a3e", edgecolor="#4A3F8C",
                      labelcolor="#d4d4d4", fontsize=8, loc="upper right")
            ax.grid(axis="y", color="#2a2a3e", linewidth=0.5, zorder=0)
            fig.tight_layout(pad=1.5)
            cv = FigureCanvasTkAgg(fig, parent)
            cv.draw()
            cv.get_tk_widget().pack(fill=BOTH, expand=True, padx=4, pady=4)
        except ImportError:
            Label(parent, text="Cần matplotlib:\n  pip install matplotlib",
                  bg=BG, fg=DIM, font=F_MAIN, justify=CENTER).pack(expand=True)

    # ── Tab: Tổng quan ────────────────────────────────────────────────────────

    def _stats_tab_summary(self, nb, data, is_chart):
        detail = data["detail"]
        loai_xe_found = {k[0] for k in detail}
        loai_xe_list  = [v for v in _VTYPE_ORDER if v in loai_xe_found] + \
                        sorted(loai_xe_found - set(_VTYPE_ORDER))
        buoi_list = self._BUOI_DISP_ORDER

        agg = defaultdict(lambda: defaultdict(int))
        for (lx, ln, b), cnt in detail.items():
            agg[(lx, ln)][b] += cnt

        tab = Frame(nb, bg=BG)
        nb.add(tab, text="  Tổng quan  ")

        if not is_chart:
            cols   = ["Loại xe", "Làn"] + buoi_list + ["Tổng"]
            widths = [130, 160] + [70] * 4 + [80]
            tree   = self._make_tree(tab, cols, widths)
            grand_buoi  = {b: 0 for b in buoi_list}
            grand_total = 0
            for row_idx, lx in enumerate(loai_xe_list):
                lanes    = sorted({k[1] for k in agg if k[0] == lx})
                lx_buoi  = {b: sum(agg[(lx, ln)].get(b, 0) for ln in lanes) for b in buoi_list}
                lx_total = sum(lx_buoi.values())
                for i, ln in enumerate(lanes):
                    ln_total = sum(agg[(lx, ln)].values())
                    row = [lx, ln or "(chung)"]
                    for b in buoi_list:
                        n = agg[(lx, ln)].get(b, 0)
                        row.append(str(n) if n else "─")
                    row.append(str(ln_total))
                    tree.insert("", END, values=row, tags=("odd" if i % 2 else "even",))
                sub_row = [f"∑ {lx}", f"({len(lanes)} làn)"]
                for b in buoi_list:
                    sub_row.append(str(lx_buoi[b]) if lx_buoi[b] else "─")
                sub_row.append(str(lx_total))
                tree.insert("", END, values=sub_row, tags=("total",))
                for b in buoi_list:
                    grand_buoi[b] += lx_buoi[b]
                grand_total += lx_total
            grand_row = ["TỔNG", ""]
            for b in buoi_list:
                grand_row.append(str(grand_buoi[b]))
            grand_row.append(str(grand_total))
            tree.insert("", END, values=grand_row, tags=("total",))
        else:
            def draw(ax):
                x      = range(len(loai_xe_list))
                w      = max(0.1, 0.8 / max(len(buoi_list), 1))
                colors = ["#F05922", "#4A3F8C", "#B8B3D6", "#FFAA80"]
                for i, b in enumerate(buoi_list):
                    vals = []
                    for lx in loai_xe_list:
                        lanes = {k[1] for k in agg if k[0] == lx}
                        vals.append(sum(agg[(lx, ln)].get(b, 0) for ln in lanes))
                    ax.bar([xi + i * w for xi in x], vals, w,
                           label=b, color=colors[i], zorder=3)
                ax.set_xticks([xi + w * 2 for xi in x])
                ax.set_xticklabels(loai_xe_list, rotation=15, ha="right",
                                   fontsize=7, color="#d4d4d4")
                ax.set_title("Số ảnh theo loại xe và buổi", color="#d4d4d4", fontsize=10)
            self._make_chart(tab, draw)

    # ── Tab: Theo ngày ────────────────────────────────────────────────────────

    def _stats_tab_date(self, nb, data, is_chart):
        by_date = data["date"]
        loai_xe_found = {k[0] for cnt in by_date.values() for k in cnt}
        loai_xe_list  = [v for v in _VTYPE_ORDER if v in loai_xe_found] + \
                        sorted(loai_xe_found - set(_VTYPE_ORDER))
        dates = sorted(by_date)
        date_lx: dict = {}
        for d, cnt in by_date.items():
            agg: dict = defaultdict(int)
            for (lx, _), n in cnt.items():
                agg[lx] += n
            date_lx[d] = dict(agg)

        tab = Frame(nb, bg=BG)
        nb.add(tab, text="  Theo ngày  ")

        if not is_chart:
            cols   = ["Ngày", "Tổng"] + loai_xe_list
            widths = [110, 70] + [max(90, len(lx) * 8) for lx in loai_xe_list]
            tree   = self._make_tree(tab, cols, widths)
            grand  = {lx: 0 for lx in loai_xe_list}
            grand_t = 0
            for i, d in enumerate(dates):
                row_t = sum(date_lx[d].values())
                row   = [d, str(row_t)]
                for lx in loai_xe_list:
                    n = date_lx[d].get(lx, 0)
                    row.append(str(n) if n else "─")
                    grand[lx] += n
                grand_t += row_t
                tree.insert("", END, values=row, tags=("odd" if i % 2 else "even",))
            tree.insert("", END,
                        values=("TỔNG", str(grand_t),
                                *[str(grand[lx]) for lx in loai_xe_list]),
                        tags=("total",))
        else:
            def draw(ax):
                bottom = [0] * len(dates)
                for i, lx in enumerate(loai_xe_list):
                    vals = [date_lx[d].get(lx, 0) for d in dates]
                    clr  = _VTYPE_COLORS.get(lx, _LANE_PALETTE[i % len(_LANE_PALETTE)])
                    ax.bar(dates, vals, bottom=bottom, label=lx, color=clr, zorder=3)
                    bottom = [b + v for b, v in zip(bottom, vals)]
                ax.set_xticklabels(dates, rotation=20, ha="right",
                                   fontsize=7, color="#d4d4d4")
                ax.set_title("Số ảnh theo ngày", color="#d4d4d4", fontsize=10)
            self._make_chart(tab, draw)

    # ── Tab: Theo buổi ────────────────────────────────────────────────────────

    def _stats_tab_buoi(self, nb, data, is_chart):
        detail = data["detail"]
        loai_xe_found = {k[0] for k in detail}
        loai_xe_list  = [v for v in _VTYPE_ORDER if v in loai_xe_found] + \
                        sorted(loai_xe_found - set(_VTYPE_ORDER))
        buoi_list = self._BUOI_DISP_ORDER
        buoi_lx: dict = defaultdict(lambda: defaultdict(int))
        for (lx, _, b), cnt in detail.items():
            buoi_lx[b][lx] += cnt

        tab = Frame(nb, bg=BG)
        nb.add(tab, text="  Theo buổi  ")

        if not is_chart:
            cols   = ["Buổi", "Tổng"] + loai_xe_list
            widths = [80, 70] + [max(90, len(lx) * 8) for lx in loai_xe_list]
            tree   = self._make_tree(tab, cols, widths, anchor_first="center")
            grand  = {lx: 0 for lx in loai_xe_list}
            grand_t = 0
            for i, b in enumerate(buoi_list):
                row_t = sum(buoi_lx[b].values())
                row   = [b, str(row_t) if row_t else "─"]
                for lx in loai_xe_list:
                    n = buoi_lx[b].get(lx, 0)
                    row.append(str(n) if n else "─")
                    grand[lx] += n
                grand_t += row_t
                tree.insert("", END, values=row, tags=("odd" if i % 2 else "even",))
            tree.insert("", END,
                        values=("TỔNG", str(grand_t),
                                *[str(grand[lx]) for lx in loai_xe_list]),
                        tags=("total",))
        else:
            def draw(ax):
                x = range(len(buoi_list))
                w = max(0.1, 0.8 / max(len(loai_xe_list), 1))
                for i, lx in enumerate(loai_xe_list):
                    vals = [buoi_lx[b].get(lx, 0) for b in buoi_list]
                    clr  = _VTYPE_COLORS.get(lx, _LANE_PALETTE[i % len(_LANE_PALETTE)])
                    ax.bar([xi + i * w for xi in x], vals, w,
                           label=lx, color=clr, zorder=3)
                ax.set_xticks([xi + w * len(loai_xe_list) / 2 for xi in x])
                ax.set_xticklabels(buoi_list, fontsize=9, color="#d4d4d4")
                ax.set_title("Phân phối ảnh theo buổi", color="#d4d4d4", fontsize=10)
            self._make_chart(tab, draw)
