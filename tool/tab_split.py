import os
import threading
from pathlib import Path
from tkinter import *
from tkinter import messagebox

from .constants import BG, CARD, ACCENT, ACCENT2, TEXT, DIM, F_MAIN, F_BOLD
from .settings import _bind_cfg
from .core_split import run_split
from .ui_helpers import _folder_row, _pb_row, _make_logbox, _append_log, _set_progress, _action_btn


class SplitTab(Frame):
    def __init__(self, master, root):
        super().__init__(master, bg=BG)
        self.root = root
        self._build()

    def _build(self):
        inp = Frame(self, bg=BG, padx=20, pady=14); inp.pack(fill=X)
        self.v_src = StringVar(); self.v_out = StringVar()
        _bind_cfg("split.src", self.v_src); _bind_cfg("split.out", self.v_out)
        _folder_row(inp, "📁  Thư mục nguồn",               self.v_src, 0)
        _folder_row(inp, "💾  Thư mục đầu ra (tuỳ chọn)",   self.v_out, 1)

        opt = Frame(self, bg=BG, padx=20, pady=4); opt.pack(fill=X)
        Label(opt, text="Tối đa ảnh / folder:", bg=BG, fg=DIM,
              font=F_MAIN).grid(row=0, column=0, sticky=W, padx=(0, 8))
        self.v_max = IntVar(value=1000)
        Spinbox(opt, from_=10, to=100000, increment=100, textvariable=self.v_max,
                bg=CARD, fg=TEXT, insertbackground=TEXT, buttonbackground=ACCENT2,
                relief="flat", font=F_MAIN, width=8).grid(row=0, column=1, sticky=W)
        Label(opt, text="   Hành động:", bg=BG, fg=DIM,
              font=F_MAIN).grid(row=0, column=2, sticky=W, padx=(24, 8))
        self.v_move = BooleanVar(value=False)
        for col, (lbl, val) in enumerate([("Sao chép", False), ("Di chuyển", True)]):
            Radiobutton(opt, text=lbl, variable=self.v_move, value=val,
                        bg=BG, fg=TEXT, selectcolor=CARD,
                        activebackground=BG, font=F_MAIN).grid(
                            row=0, column=3+col, padx=(6 if col else 0, 0))

        info = Frame(self, bg=CARD, padx=20, pady=8)
        info.pack(fill=X, padx=20, pady=(6, 4))
        for t in ["Tạo folder: part_01, part_02, … — mỗi folder tối đa N ảnh.",
                  "Để trống 'Thư mục đầu ra' → tự tạo folder <tên>_split bên cạnh thư mục nguồn."]:
            Label(info, text=t, bg=CARD, fg=DIM, font=("Segoe UI", 9)).pack(anchor=W)

        pb_f = Frame(self, bg=BG, padx=20); pb_f.pack(fill=X)
        self.pb_lbl, self.pb = _pb_row(pb_f)

        log_outer = Frame(self, bg=BG, padx=20); log_outer.pack(fill=BOTH, expand=True)
        log_f, self.log = _make_logbox(log_outer)
        log_f.pack(fill=BOTH, expand=True)

        btn_row = Frame(self, bg=BG, padx=20, pady=10); btn_row.pack(fill=X)
        self.btn = _action_btn(btn_row, "▶  Bắt đầu Split", self._run, ACCENT,
                               padx=20, pady=8)
        self.btn.pack(side=LEFT)
        _action_btn(btn_row, "🗂  Mở output", self._open, ACCENT2,
                    padx=14, pady=8).pack(side=LEFT, padx=(10, 0))
        Button(btn_row, text="🧹  Xóa log",
               command=lambda: (self.log.configure(state=NORMAL),
                                self.log.delete("1.0", END),
                                self.log.configure(state=DISABLED)),
               bg=CARD, fg=DIM, font=F_MAIN, relief="flat",
               padx=14, pady=8, cursor="hand2").pack(side=RIGHT)

    def _open(self):
        p = self.v_out.get().strip()
        if not p:
            src = self.v_src.get().strip()
            if src: p = str(Path(src).parent / (Path(src).name + "_split"))
        if p and Path(p).exists(): os.startfile(p)
        else: messagebox.showwarning("Chưa có output", "Chạy xong hoặc nhập thư mục đầu ra.")

    def _run(self):
        src = self.v_src.get().strip()
        if not src:
            messagebox.showwarning("Thiếu thông tin", "Vui lòng chọn thư mục nguồn."); return
        try:
            max_n = int(self.v_max.get())
            if max_n < 1: raise ValueError
        except (ValueError, TypeError):
            messagebox.showwarning("Giá trị không hợp lệ", "Tối đa ảnh / folder phải là số nguyên dương.")
            return

        self.btn.config(state=DISABLED, text="⏳  Đang xử lý…")
        self.pb["value"] = 0; self.pb_lbl.config(text="Đang khởi động…")
        move = self.v_move.get(); out = self.v_out.get().strip()

        def worker():
            try:
                run_split(src, out, max_n, move,
                          log=lambda m: self.root.after(0, _append_log, self.log, m),
                          progress=lambda d, t: self.root.after(
                              0, _set_progress, self.pb_lbl, self.pb, d, t, self.root))
            except Exception as e:
                self.root.after(0, _append_log, self.log, f"[LỖI] {e}")
            finally:
                self.root.after(0, lambda: (
                    self.btn.config(state=NORMAL, text="▶  Bắt đầu Split"),
                    self.pb_lbl.config(text="✅  Hoàn thành!")))

        threading.Thread(target=worker, daemon=True).start()
