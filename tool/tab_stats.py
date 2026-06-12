import os
from tkinter import *
from tkinter import filedialog, messagebox

from .constants import BG, CARD, ACCENT, ACCENT2, TEXT, DIM, F_MAIN, F_BOLD, F_MONO
from .settings import _CFG, _cfg_save, _cfg_dir
from .core_gt import analyze_gt, _heat_color

HEATMAP_CHARS = list("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ")
HMAP_COLS     = 10
CELL_W        = 68
CELL_H        = 54


class StatsTab(Frame):
    def __init__(self, master, root):
        super().__init__(master, bg=BG)
        self.root    = root
        self._folder = ""
        self._cells  = {}
        self._build()

    def _build(self):
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

        prog_outer = Frame(self, bg=BG, padx=16, pady=6)
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

        leg_frame = Frame(hm_card, bg=CARD, pady=4)
        leg_frame.pack(anchor=W)
        Label(leg_frame, text="Ít  ", bg=CARD, fg=DIM,
              font=("Segoe UI", 8)).pack(side=LEFT)
        for lvl in [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]:
            c = _heat_color(lvl, 1.0) if lvl > 0 else "#252540"
            Frame(leg_frame, width=18, height=12, bg=c).pack(side=LEFT, padx=1)
        Label(leg_frame, text="  Nhiều", bg=CARD, fg=DIM,
              font=("Segoe UI", 8)).pack(side=LEFT)

        bottom = Frame(self, bg=BG, padx=16, pady=6)
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

        len_card = Frame(bottom, bg=CARD, padx=12, pady=8)
        len_card.grid(row=0, column=1, sticky=NSEW)
        Label(len_card, text="ĐỘ DÀI NHÃN",
              bg=CARD, fg=DIM, font=("Segoe UI Semibold", 9)).pack(anchor=W, pady=(0, 4))
        self.txt_len = Text(len_card, bg="#16162a", fg=TEXT, font=("Consolas", 9),
                            relief="flat", bd=0, state=DISABLED, height=9, wrap=NONE)
        self.txt_len.pack(fill=BOTH, expand=True)
        self.txt_len.tag_config("bar",  foreground=ACCENT)
        self.txt_len.tag_config("hdr",  foreground=DIM)

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

        from collections import Counter
        all_chars = Counter(rem_chars) + Counter(chk_chars)

        self._update_progress(n_checked, n_remaining, n_total, pct, gt_checked)
        self._update_heatmap(all_chars)
        self._update_freq_table(all_chars)
        self._update_length_chart(rem_lens, chk_lens)

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
            line = f"  {length:>3}  {cnt:>8,}  {pct:>5.1f}%  "
            self.txt_len.insert(END, line, "hdr")
            self.txt_len.insert(END, "█" * bars + "\n", "bar")
        self.txt_len.configure(state=DISABLED)
