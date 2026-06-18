import os
from collections import Counter
from tkinter import *
from tkinter import filedialog, messagebox, ttk

from ...core.constants import BG, CARD, ACCENT, ACCENT2, TEXT, DIM, F_MAIN, F_BOLD, F_MONO
from ...core.settings import _CFG, _cfg_save, _cfg_dir, _push_history
from .core_gt import analyze_gt, _heat_color

HEATMAP_CHARS = list("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ")
HMAP_COLS     = 10
CELL_W        = 68
CELL_H        = 54

_WARN_FG  = "#FF6B35"
_DIFF_FG  = "#FFE000"
_ONLY1_FG = "#5BD4FF"
_ONLY2_FG = "#A8FF78"


class StatsTab(Frame):
    def __init__(self, master, root):
        super().__init__(master, bg=BG)
        self.root     = root
        self._folder  = ""
        self._folder2 = ""
        self._cells   = {}
        self._last_char_counts  = Counter()
        self._last_char_counts2 = Counter()
        self._last_rem_lens  = {}
        self._last_chk_lens  = {}
        self._last_rem_lens2 = {}
        self._last_chk_lens2 = {}
        self._all_class_names: list[str] = []
        self._selected_classes: set[str] = set()
        self._build()

    def _build(self):
        # ── TOP BAR ─────────────────────────────────────────────
        top = Frame(self, bg=CARD, padx=16, pady=8)
        top.pack(fill=X)

        # Dataset 1
        row1 = Frame(top, bg=CARD)
        row1.pack(fill=X)
        Label(row1, text="Dataset 1:", bg=CARD, fg=DIM, font=F_MAIN,
              width=10, anchor=W).pack(side=LEFT)
        Button(row1, text="📂  Chọn folder", command=self._load,
               bg=ACCENT2, fg="white", activebackground=ACCENT,
               activeforeground="white", font=F_BOLD,
               relief="flat", padx=12, pady=5, cursor="hand2").pack(side=LEFT)
        self.btn_open1 = Button(row1, text="📂 Mở", command=self._open_folder1,
               bg=CARD, fg=DIM, activebackground=ACCENT2,
               activeforeground="white", font=F_MAIN,
               relief="flat", padx=8, pady=5, cursor="hand2")
        self.btn_open1.pack(side=LEFT, padx=(4, 0))
        self.lbl_path = Label(row1, text="Chưa chọn folder",
                              bg=CARD, fg=DIM, font=F_MAIN)
        self.lbl_path.pack(side=LEFT, padx=10)

        # Dataset 2
        row2 = Frame(top, bg=CARD)
        row2.pack(fill=X, pady=(4, 0))
        Label(row2, text="Dataset 2:", bg=CARD, fg=DIM, font=F_MAIN,
              width=10, anchor=W).pack(side=LEFT)
        Button(row2, text="📂  Chọn folder", command=self._load2,
               bg="#3a3a5e", fg="white", activebackground=ACCENT2,
               activeforeground="white", font=F_MAIN,
               relief="flat", padx=12, pady=5, cursor="hand2").pack(side=LEFT)
        self.btn_open2 = Button(row2, text="📂 Mở", command=self._open_folder2,
               bg=CARD, fg=DIM, activebackground=ACCENT2,
               activeforeground="white", font=F_MAIN,
               relief="flat", padx=8, pady=5, cursor="hand2")
        self.btn_open2.pack(side=LEFT, padx=(4, 0))
        self.lbl_path2 = Label(row2, text="Chưa chọn (tùy chọn)",
                               bg=CARD, fg=DIM, font=F_MAIN)
        self.lbl_path2.pack(side=LEFT, padx=10)
        Button(row2, text="✖ Xóa", command=self._clear2,
               bg=CARD, fg=DIM, activebackground=CARD,
               activeforeground=ACCENT, font=F_MAIN,
               relief="flat", padx=8, pady=5, cursor="hand2").pack(side=LEFT)

        # Right-side buttons
        btn_frame = Frame(top, bg=CARD)
        btn_frame.pack(side=RIGHT, anchor=NE)
        Button(btn_frame, text="🔄  Làm mới", command=self._refresh,
               bg=CARD, fg=TEXT, activebackground=ACCENT2,
               activeforeground="white", font=F_MAIN,
               relief="flat", padx=12, pady=6, cursor="hand2").pack(side=LEFT, padx=(0, 6))
        Button(btn_frame, text="💾  Xuất ảnh", command=self._export_heatmap,
               bg=CARD, fg=TEXT, activebackground=ACCENT2,
               activeforeground="white", font=F_MAIN,
               relief="flat", padx=12, pady=6, cursor="hand2").pack(side=LEFT)

        # ── MAIN SCROLL AREA ────────────────────────────────────
        scroll_outer = Frame(self, bg=BG)
        scroll_outer.pack(fill=BOTH, expand=True)
        canvas_scroll = Canvas(scroll_outer, bg=BG, highlightthickness=0)
        vscroll = Scrollbar(scroll_outer, orient=VERTICAL, command=canvas_scroll.yview)
        canvas_scroll.configure(yscrollcommand=vscroll.set)
        vscroll.pack(side=RIGHT, fill=Y)
        canvas_scroll.pack(side=LEFT, fill=BOTH, expand=True)
        self._inner = Frame(canvas_scroll, bg=BG)
        self._inner_id = canvas_scroll.create_window((0, 0), window=self._inner, anchor=NW)
        self._inner.bind("<Configure>",
            lambda e: canvas_scroll.configure(scrollregion=canvas_scroll.bbox("all")))
        canvas_scroll.bind("<Configure>",
            lambda e: canvas_scroll.itemconfig(self._inner_id, width=e.width))
        def _mw(e): canvas_scroll.yview_scroll(-1 * (e.delta // 120), "units")
        _mw_ent = [False]
        def _mw_enter(_): _mw_ent[0] = True; canvas_scroll.bind_all("<MouseWheel>", _mw)
        def _mw_leave(_):
            _mw_ent[0] = False
            canvas_scroll.after(20, lambda: canvas_scroll.unbind_all("<MouseWheel>") if not _mw_ent[0] else None)
        canvas_scroll.bind("<Enter>", _mw_enter)
        canvas_scroll.bind("<Leave>", _mw_leave)

        inner = self._inner

        # ── PROGRESS ────────────────────────────────────────────
        prog_outer = Frame(inner, bg=BG, padx=16, pady=6)
        prog_outer.pack(fill=X)
        prog_card = Frame(prog_outer, bg=CARD, padx=16, pady=10)
        prog_card.pack(fill=X)
        Label(prog_card, text="TIẾN ĐỘ KIỂM TRA", bg=CARD, fg=DIM,
              font=("Segoe UI Semibold", 9)).pack(anchor=W)
        self.lbl_prog_nums = Label(prog_card, text="—", bg=CARD, fg=TEXT,
                                   font=("Segoe UI Semibold", 12))
        self.lbl_prog_nums.pack(anchor=W, pady=(4, 2))
        self.cv_prog = Canvas(prog_card, height=18, bg="#16162a",
                              highlightthickness=0)
        self.cv_prog.pack(fill=X, pady=(0, 4))
        self.cv_prog.bind("<Configure>", self._redraw_prog)
        self._prog_pct = 0.0
        self.lbl_prog_detail = Label(prog_card, text="", bg=CARD, fg=DIM,
                                     font=("Segoe UI", 9))
        self.lbl_prog_detail.pack(anchor=W)

        # ── WARNING LABEL ────────────────────────────────────────
        warn_outer = Frame(inner, bg=BG, padx=16, pady=2)
        warn_outer.pack(fill=X)
        warn_card = Frame(warn_outer, bg=CARD, padx=16, pady=8)
        warn_card.pack(fill=X)
        warn_top = Frame(warn_card, bg=CARD)
        warn_top.pack(fill=X)
        Label(warn_top, text="CẢNH BÁO MẤT CÂN BẰNG", bg=CARD, fg=DIM,
              font=("Segoe UI Semibold", 9)).pack(side=LEFT)
        Label(warn_top, text="Ngưỡng cảnh báo:", bg=CARD, fg=DIM,
              font=F_MAIN).pack(side=LEFT, padx=(20, 4))
        self._warn_thresh = StringVar(value="100")
        Entry(warn_top, textvariable=self._warn_thresh, width=7,
              bg="#16162a", fg=TEXT, insertbackground=TEXT,
              relief="flat", font=F_MONO).pack(side=LEFT)
        Button(warn_top, text="Áp dụng", command=self._reapply_warnings,
               bg=ACCENT2, fg="white", activebackground=ACCENT,
               activeforeground="white", font=F_MAIN,
               relief="flat", padx=8, pady=2, cursor="hand2").pack(side=LEFT, padx=(6, 0))
        self.lbl_warn = Label(warn_card, text="", bg=CARD, fg=_WARN_FG,
                              font=("Segoe UI", 9), justify=LEFT, wraplength=900)
        self.lbl_warn.pack(anchor=W, pady=(6, 0))

        # ── CLASS FILTER ─────────────────────────────────────────
        filt_outer = Frame(inner, bg=BG, padx=16, pady=2)
        filt_outer.pack(fill=X)
        filt_card = Frame(filt_outer, bg=CARD, padx=16, pady=8)
        filt_card.pack(fill=X)
        filt_top = Frame(filt_card, bg=CARD)
        filt_top.pack(fill=X)
        Label(filt_top, text="LỌC THEO KÝ TỰ", bg=CARD, fg=DIM,
              font=("Segoe UI Semibold", 9)).pack(side=LEFT)
        Button(filt_top, text="Chọn tất cả", command=self._select_all_classes,
               bg=ACCENT2, fg="white", activebackground=ACCENT,
               activeforeground="white", font=F_MAIN,
               relief="flat", padx=8, pady=2, cursor="hand2").pack(side=LEFT, padx=(20, 4))
        Button(filt_top, text="Bỏ chọn", command=self._deselect_all_classes,
               bg=CARD, fg=DIM, activebackground=ACCENT2,
               activeforeground="white", font=F_MAIN,
               relief="flat", padx=8, pady=2, cursor="hand2").pack(side=LEFT, padx=(0, 4))
        Button(filt_top, text="Áp dụng lọc", command=self._apply_filter,
               bg=ACCENT, fg="white", activebackground="#d04010",
               activeforeground="white", font=F_BOLD,
               relief="flat", padx=10, pady=2, cursor="hand2").pack(side=LEFT, padx=(6, 0))
        self.lbl_filter_hint = Label(filt_card,
                                     text="(Chưa có dữ liệu — tải dataset trước)",
                                     bg=CARD, fg=DIM, font=F_MAIN)
        self.lbl_filter_hint.pack(anchor=W, pady=(6, 0))
        lb_frame = Frame(filt_card, bg=CARD)
        lb_frame.pack(fill=X, pady=(4, 0))
        self.lb_classes = Listbox(lb_frame, selectmode=EXTENDED,
                                  bg="#16162a", fg=TEXT, font=("Consolas", 10),
                                  relief="flat", bd=0, height=4,
                                  selectbackground=ACCENT2, selectforeground="white",
                                  exportselection=False)
        sb_lb = Scrollbar(lb_frame, orient=HORIZONTAL, command=self.lb_classes.xview)
        self.lb_classes.configure(xscrollcommand=sb_lb.set)
        sb_lb.pack(side=BOTTOM, fill=X)
        self.lb_classes.pack(side=LEFT, fill=X, expand=True)

        # ── HEATMAP ──────────────────────────────────────────────
        hm_outer = Frame(inner, bg=BG, padx=16, pady=4)
        hm_outer.pack(fill=X)
        hm_card = Frame(hm_outer, bg=CARD, padx=14, pady=10)
        hm_card.pack(fill=X)
        self._hm_title = Label(hm_card,
                               text="PHÂN BỐ KÝ TỰ  (màu đậm = xuất hiện nhiều hơn)",
                               bg=CARD, fg=DIM, font=("Segoe UI Semibold", 9))
        self._hm_title.pack(anchor=W, pady=(0, 8))
        self._hm_card = hm_card
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

        leg_frame = Frame(hm_card, bg=CARD, pady=4)
        leg_frame.pack(anchor=W)
        Label(leg_frame, text="Ít  ", bg=CARD, fg=DIM,
              font=("Segoe UI", 8)).pack(side=LEFT)
        for lvl in [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]:
            c = _heat_color(lvl, 1.0) if lvl > 0 else "#252540"
            Frame(leg_frame, width=18, height=12, bg=c).pack(side=LEFT, padx=1)
        Label(leg_frame, text="  Nhiều", bg=CARD, fg=DIM,
              font=("Segoe UI", 8)).pack(side=LEFT)

        # legend for compare mode
        self._cmp_legend = Frame(hm_card, bg=CARD, pady=2)
        self._cmp_legend.pack(anchor=W)
        Label(self._cmp_legend, text="  Chỉ Dataset 1",
              bg=CARD, fg=_ONLY1_FG, font=("Segoe UI", 8)).pack(side=LEFT)
        Label(self._cmp_legend, text="  |  Chỉ Dataset 2",
              bg=CARD, fg=_ONLY2_FG, font=("Segoe UI", 8)).pack(side=LEFT)
        Label(self._cmp_legend, text="  |  Cả hai",
              bg=CARD, fg=_DIFF_FG, font=("Segoe UI", 8)).pack(side=LEFT)
        self._cmp_legend.pack_forget()

        # ── BOTTOM: FREQ + LENGTH ─────────────────────────────────
        bottom = Frame(inner, bg=BG, padx=16, pady=6)
        bottom.pack(fill=BOTH, expand=True)
        bottom.columnconfigure(0, weight=3)
        bottom.columnconfigure(1, weight=2)

        freq_card = Frame(bottom, bg=CARD, padx=12, pady=8)
        freq_card.grid(row=0, column=0, sticky=NSEW, padx=(0, 6))
        Label(freq_card, text="CHI TIẾT TẦN SUẤT KÝ TỰ",
              bg=CARD, fg=DIM, font=("Segoe UI Semibold", 9)).pack(anchor=W, pady=(0, 4))
        self.txt_freq = Text(freq_card, bg="#16162a", fg=TEXT, font=("Consolas", 9),
                             relief="flat", bd=0, state=DISABLED, height=9, wrap=NONE)
        sb_freq = Scrollbar(freq_card, command=self.txt_freq.yview)
        self.txt_freq.configure(yscrollcommand=sb_freq.set)
        sb_freq.pack(side=RIGHT, fill=Y)
        self.txt_freq.pack(fill=BOTH, expand=True)
        self.txt_freq.tag_config("hdr",  foreground=DIM)
        self.txt_freq.tag_config("bar",  foreground=ACCENT)
        self.txt_freq.tag_config("hi",   foreground="#FFE000")
        self.txt_freq.tag_config("only1", foreground=_ONLY1_FG)
        self.txt_freq.tag_config("only2", foreground=_ONLY2_FG)
        self.txt_freq.tag_config("diff",  foreground=_DIFF_FG)
        self.txt_freq.tag_config("bar1",  foreground=_ONLY1_FG)
        self.txt_freq.tag_config("bar2",  foreground=_ONLY2_FG)

        len_card = Frame(bottom, bg=CARD, padx=12, pady=8)
        len_card.grid(row=0, column=1, sticky=NSEW)
        Label(len_card, text="ĐỘ DÀI NHÃN",
              bg=CARD, fg=DIM, font=("Segoe UI Semibold", 9)).pack(anchor=W, pady=(0, 4))
        self.txt_len = Text(len_card, bg="#16162a", fg=TEXT, font=("Consolas", 9),
                            relief="flat", bd=0, state=DISABLED, height=9, wrap=NONE)
        self.txt_len.pack(fill=BOTH, expand=True)
        self.txt_len.tag_config("bar",   foreground=ACCENT)
        self.txt_len.tag_config("hdr",   foreground=DIM)
        self.txt_len.tag_config("bar1",  foreground=_ONLY1_FG)
        self.txt_len.tag_config("bar2",  foreground=_ONLY2_FG)

    # ── DATASET LOADING ──────────────────────────────────────────

    def _open_folder1(self):
        if self._folder and os.path.isdir(self._folder):
            os.startfile(self._folder)

    def _open_folder2(self):
        if self._folder2 and os.path.isdir(self._folder2):
            os.startfile(self._folder2)

    def _load(self):
        folder = filedialog.askdirectory(
            title="Chọn folder chứa gt.txt (Dataset 1)",
            initialdir=_cfg_dir("stats.folder"))
        if folder:
            _CFG["stats.folder"] = folder; _cfg_save()
            _push_history("h.stats.folder", folder)
            self._folder = folder
            self.lbl_path.config(text=folder)
            self._refresh()

    def _load2(self):
        folder = filedialog.askdirectory(
            title="Chọn folder chứa gt.txt (Dataset 2)",
            initialdir=_cfg_dir("stats.folder2"))
        if folder:
            _CFG["stats.folder2"] = folder; _cfg_save()
            _push_history("h.stats.folder2", folder)
            self._folder2 = folder
            self.lbl_path2.config(text=folder)
            self._refresh()

    def _clear2(self):
        self._folder2 = ""
        self.lbl_path2.config(text="Chưa chọn (tùy chọn)")
        self._last_char_counts2 = Counter()
        self._last_rem_lens2 = {}
        self._last_chk_lens2 = {}
        self._refresh()

    # ── REFRESH ──────────────────────────────────────────────────

    def _refresh(self):
        if not self._folder:
            messagebox.showwarning("Chưa chọn folder", "Vui lòng chọn folder trước."); return
        gt_remaining = os.path.join(self._folder, "gt.txt")
        if not os.path.exists(gt_remaining):
            messagebox.showerror("Không tìm thấy",
                                 f"Không có gt.txt trong:\n{self._folder}"); return

        parent      = os.path.dirname(self._folder)
        checked_dir = os.path.join(parent, os.path.basename(self._folder) + "_checked")
        gt_checked  = os.path.join(checked_dir, "gt.txt")

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

        self._last_char_counts  = Counter(rem_chars) + Counter(chk_chars)
        self._last_rem_lens  = rem_lens
        self._last_chk_lens  = chk_lens

        # Dataset 2
        has_ds2 = bool(self._folder2)
        if has_ds2:
            gt2 = os.path.join(self._folder2, "gt.txt")
            if not os.path.exists(gt2):
                messagebox.showwarning("Dataset 2",
                    f"Không tìm thấy gt.txt trong Dataset 2:\n{self._folder2}")
                has_ds2 = False
            else:
                parent2      = os.path.dirname(self._folder2)
                checked_dir2 = os.path.join(parent2,
                                             os.path.basename(self._folder2) + "_checked")
                gt_checked2  = os.path.join(checked_dir2, "gt.txt")
                _, rem2, rem_lens2 = analyze_gt(gt2)
                chk2, chk_lens2 = {}, {}
                if os.path.exists(gt_checked2):
                    _, chk2, chk_lens2 = analyze_gt(gt_checked2)
                self._last_char_counts2 = Counter(rem2) + Counter(chk2)
                self._last_rem_lens2 = rem_lens2
                self._last_chk_lens2 = chk_lens2

        if not has_ds2:
            self._last_char_counts2 = Counter()
            self._last_rem_lens2 = {}
            self._last_chk_lens2 = {}

        # Rebuild class filter list from all known chars
        all_chars_union = set(self._last_char_counts.keys()) | set(self._last_char_counts2.keys())
        self._all_class_names = sorted(all_chars_union)
        self._rebuild_class_listbox()

        self._update_progress(n_checked, n_remaining, n_total, pct, gt_checked)
        self._apply_warnings(self._last_char_counts, self._last_char_counts2)
        self._apply_filter()

    # ── PROGRESS ─────────────────────────────────────────────────

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
        pct_str = f"{self._prog_pct*100:.1f}%"
        self.cv_prog.create_text(w // 2, h // 2, text=pct_str,
                                 fill="white", font=("Segoe UI Semibold", 8))

    # ── WARNING ───────────────────────────────────────────────────

    def _get_thresh(self):
        try:
            return int(self._warn_thresh.get())
        except ValueError:
            return 100

    def _apply_warnings(self, counts1: Counter, counts2: Counter):
        thresh = self._get_thresh()
        lines = []
        all_chars = set(counts1.keys()) | set(counts2.keys())
        for ch in sorted(all_chars):
            c1 = counts1.get(ch, 0)
            c2 = counts2.get(ch, 0) if counts2 else 0
            if self._folder2 and counts2:
                if c1 < thresh or c2 < thresh:
                    parts = []
                    if c1 < thresh:
                        parts.append(f"DS1={c1}")
                    if c2 < thresh:
                        parts.append(f"DS2={c2}")
                    lines.append(f"'{ch}' ({', '.join(parts)} < {thresh})")
            else:
                if c1 < thresh:
                    lines.append(f"'{ch}' ({c1} < {thresh})")
        if lines:
            self.lbl_warn.config(
                text="⚠ Ký tự ít mẫu: " + ",  ".join(lines))
        else:
            self.lbl_warn.config(text="✓ Không có ký tự nào dưới ngưỡng." if all_chars else "")

    def _reapply_warnings(self):
        self._apply_warnings(self._last_char_counts, self._last_char_counts2)

    # ── CLASS FILTER ─────────────────────────────────────────────

    def _rebuild_class_listbox(self):
        self.lb_classes.delete(0, END)
        for ch in self._all_class_names:
            self.lb_classes.insert(END, ch)
        if self._all_class_names:
            self.lb_classes.select_set(0, END)
            self._selected_classes = set(self._all_class_names)
            self.lbl_filter_hint.config(
                text=f"Chọn ký tự để lọc thống kê ({len(self._all_class_names)} ký tự):")
        else:
            self.lbl_filter_hint.config(text="(Chưa có dữ liệu — tải dataset trước)")

    def _select_all_classes(self):
        self.lb_classes.select_set(0, END)

    def _deselect_all_classes(self):
        self.lb_classes.select_clear(0, END)

    def _apply_filter(self):
        sel_indices = self.lb_classes.curselection()
        if sel_indices:
            self._selected_classes = {self._all_class_names[i] for i in sel_indices}
        else:
            self._selected_classes = set(self._all_class_names)

        c1 = Counter({k: v for k, v in self._last_char_counts.items()
                      if k in self._selected_classes})
        c2 = Counter({k: v for k, v in self._last_char_counts2.items()
                      if k in self._selected_classes})

        has_ds2 = bool(self._folder2 and self._last_char_counts2)
        self._update_heatmap(c1, c2 if has_ds2 else None)
        self._update_freq_table(c1, c2 if has_ds2 else None)
        self._update_length_chart(self._last_rem_lens, self._last_chk_lens,
                                  self._last_rem_lens2 if has_ds2 else {},
                                  self._last_chk_lens2 if has_ds2 else {})

    # ── HEATMAP ───────────────────────────────────────────────────

    def _update_heatmap(self, char_counts1: Counter, char_counts2=None):
        compare = char_counts2 is not None and len(char_counts2) > 0
        if compare:
            self._hm_title.config(
                text="PHÂN BỐ KÝ TỰ — SO SÁNH DATASET 1 vs DATASET 2")
            self._cmp_legend.pack(anchor=W)
        else:
            self._hm_title.config(
                text="PHÂN BỐ KÝ TỰ  (màu đậm = xuất hiện nhiều hơn)")
            self._cmp_legend.pack_forget()

        all_counts = char_counts1 + (char_counts2 or Counter())
        max_count  = max(all_counts.values(), default=1)

        for ch, (cell, lbl_ch, lbl_cnt) in self._cells.items():
            c1 = char_counts1.get(ch, 0)
            c2 = char_counts2.get(ch, 0) if compare else 0
            cnt = c1 + c2

            if compare:
                if c1 > 0 and c2 > 0:
                    bg   = _heat_color(cnt, max_count * 2)
                    fg   = _DIFF_FG
                    fg_n = _DIFF_FG
                    label_text = f"{c1:,}|{c2:,}"
                elif c1 > 0:
                    bg   = _heat_color(c1, max_count)
                    fg   = _ONLY1_FG
                    fg_n = _ONLY1_FG
                    label_text = f"{c1:,}|—"
                elif c2 > 0:
                    bg   = _heat_color(c2, max_count)
                    fg   = _ONLY2_FG
                    fg_n = _ONLY2_FG
                    label_text = f"—|{c2:,}"
                else:
                    bg   = "#252540"
                    fg   = "#555570"
                    fg_n = "#333350"
                    label_text = "—"
            else:
                bg   = _heat_color(c1, max_count)
                fg   = "white" if c1 else "#555570"
                fg_n = "#cccccc" if c1 else "#333350"
                label_text = f"{c1:,}" if c1 else "—"

            cell.config(bg=bg)
            lbl_ch.config(bg=bg, fg=fg)
            lbl_cnt.config(bg=bg, fg=fg_n, text=label_text)

    # ── FREQ TABLE ────────────────────────────────────────────────

    def _update_freq_table(self, char_counts1: Counter, char_counts2=None):
        compare = char_counts2 is not None and len(char_counts2) > 0
        self.txt_freq.configure(state=NORMAL)
        self.txt_freq.delete("1.0", END)

        if compare:
            all_chars = sorted(set(char_counts1.keys()) | set(char_counts2.keys()),
                               key=lambda c: -(char_counts1.get(c, 0) + char_counts2.get(c, 0)))
            total1 = sum(char_counts1.values()) or 1
            total2 = sum(char_counts2.values()) or 1
            BAR_MAX = 16
            max_cnt = max((char_counts1.get(c, 0) + char_counts2.get(c, 0)
                           for c in all_chars), default=1)
            header = f"{'Ch':^4} {'DS1':>8} {'%1':>6} {'DS2':>8} {'%2':>6}  Biểu đồ\n"
            sep    = "─" * 64 + "\n"
            self.txt_freq.insert(END, header, "hdr")
            self.txt_freq.insert(END, sep,    "hdr")
            for ch in all_chars:
                c1 = char_counts1.get(ch, 0)
                c2 = char_counts2.get(ch, 0)
                p1 = c1 / total1 * 100
                p2 = c2 / total2 * 100
                bars1 = int(c1 / max_cnt * BAR_MAX) if max_cnt else 0
                bars2 = int(c2 / max_cnt * BAR_MAX) if max_cnt else 0
                if c1 > 0 and c2 > 0:
                    tag = "diff"
                elif c1 > 0:
                    tag = "only1"
                else:
                    tag = "only2"
                line = f"  {ch:^3} {c1:>8,} {p1:>5.1f}% {c2:>8,} {p2:>5.1f}%  "
                self.txt_freq.insert(END, line, tag)
                self.txt_freq.insert(END, "█" * bars1, "bar1")
                self.txt_freq.insert(END, "░" * bars2 + "\n", "bar2")
            if not all_chars:
                self.txt_freq.insert(END, "  (không có dữ liệu)\n", "hdr")
        else:
            total_chars = sum(char_counts1.values()) or 1
            sorted_chars = sorted(char_counts1.items(), key=lambda x: -x[1])
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

    # ── LENGTH CHART ─────────────────────────────────────────────

    def _update_length_chart(self, rem_lens1, chk_lens1, rem_lens2=None, chk_lens2=None):
        compare = bool(rem_lens2 or chk_lens2)
        self.txt_len.configure(state=NORMAL)
        self.txt_len.delete("1.0", END)
        combined1 = Counter(rem_lens1) + Counter(chk_lens1)
        combined2 = Counter(rem_lens2 or {}) + Counter(chk_lens2 or {})

        if not combined1 and not combined2:
            self.txt_len.insert(END, "  (không có dữ liệu)\n", "hdr")
            self.txt_len.configure(state=DISABLED); return

        all_lengths = sorted(set(combined1.keys()) | set(combined2.keys()))
        total1 = sum(combined1.values()) or 1
        total2 = sum(combined2.values()) or 1
        BAR_MAX = 14
        max_cnt = max(
            (combined1.get(l, 0) + combined2.get(l, 0) for l in all_lengths), default=1)

        if compare:
            header = f"{'Dài':>5}  {'DS1':>7} {'%':>6}  {'DS2':>7} {'%':>6}  Biểu đồ\n"
            sep    = "─" * 56 + "\n"
        else:
            header = f"{'Dài':>5}  {'Số ảnh':>7}  {'%':>6}  Biểu đồ\n"
            sep    = "─" * 44 + "\n"
        self.txt_len.insert(END, header, "hdr")
        self.txt_len.insert(END, sep,    "hdr")

        for length in all_lengths:
            c1 = combined1.get(length, 0)
            c2 = combined2.get(length, 0)
            if compare:
                p1 = c1 / total1 * 100
                p2 = c2 / total2 * 100
                b1 = int(c1 / max_cnt * BAR_MAX) if max_cnt else 0
                b2 = int(c2 / max_cnt * BAR_MAX) if max_cnt else 0
                line = f"  {length:>3}  {c1:>7,} {p1:>5.1f}%  {c2:>7,} {p2:>5.1f}%  "
                self.txt_len.insert(END, line, "hdr")
                self.txt_len.insert(END, "█" * b1, "bar1")
                self.txt_len.insert(END, "░" * b2 + "\n", "bar2")
            else:
                pct  = c1 / total1 * 100
                bars = int(c1 / max_cnt * BAR_MAX) if max_cnt else 0
                line = f"  {length:>3}  {c1:>8,}  {pct:>5.1f}%  "
                self.txt_len.insert(END, line, "hdr")
                self.txt_len.insert(END, "█" * bars + "\n", "bar")

        self.txt_len.configure(state=DISABLED)

    # ── EXPORT HEATMAP ────────────────────────────────────────────

    # ── Shortcut aliases ─────────────────────────────────────────────

    def _browse(self):
        """Ctrl+O — chọn Dataset 1."""
        self._load()

    def _start(self):
        """F5 — làm mới thống kê."""
        self._refresh()

    def _export_heatmap(self):
        path = filedialog.asksaveasfilename(
            title="Lưu ảnh heatmap",
            defaultextension=".png",
            filetypes=[("PNG Image", "*.png"), ("All files", "*.*")],
            initialfile="heatmap_stats.png")
        if not path:
            return

        try:
            import PIL.ImageGrab as ImageGrab
            self._hm_card.update_idletasks()
            x = self._hm_card.winfo_rootx()
            y = self._hm_card.winfo_rooty()
            w = self._hm_card.winfo_width()
            h = self._hm_card.winfo_height()
            img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
            img.save(path)
            messagebox.showinfo("Xuất ảnh thành công", f"Đã lưu:\n{path}")
            return
        except Exception:
            pass

        try:
            import subprocess
            import sys
            self._hm_card.update_idletasks()
            x = self._hm_card.winfo_rootx()
            y = self._hm_card.winfo_rooty()
            w = self._hm_card.winfo_width()
            h = self._hm_card.winfo_height()
            tmp_ps = path.replace(".png", "_tmp.ps")
            self._hm_card.winfo_toplevel().update()
            try:
                self._hm_card.postscript(file=tmp_ps)
            except Exception:
                pass
            messagebox.showinfo("Xuất ảnh",
                "PIL/Pillow chưa cài. Hãy chạy: pip install Pillow\n"
                "Sau đó thử lại để xuất ảnh PNG.")
        except Exception as e:
            messagebox.showerror("Lỗi xuất ảnh", str(e))
