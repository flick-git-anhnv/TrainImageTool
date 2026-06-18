"""GetParkingImage — ứng dụng standalone thu thập ảnh từ hệ thống iParking."""

import sys
import os

# tool package nằm ở thư mục cha (3.Tools/)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tkinter import *
from tkinter import ttk, messagebox

from tool.core.imports import _DND_OK, _dnd_mod
from tool.core.ui_helpers import _style_all
from tool.core.constants import BG, CARD, ACCENT, ACCENT2, TEXT, DIM, F_MAIN, F_BOLD
from tool.core.settings import _cfg_save
from tool.features.collection.tab_iparking_image import IParkingImageTab

_AppBase = _dnd_mod.Tk if _DND_OK else Tk


class GetParkingImageApp(_AppBase):
    def __init__(self):
        super().__init__()
        self.title("KZTEK — Get Parking Image")
        self.geometry("1280x860")
        self.minsize(920, 620)
        try:
            self.state("zoomed")
        except Exception:
            pass
        self.configure(bg=BG)
        _style_all()

        # ── Topbar ────────────────────────────────────────────────────────────
        topbar = Frame(self, bg=CARD, height=38)
        topbar.pack(fill=X)
        topbar.pack_propagate(False)

        Label(topbar,
              text="  KZTEK — Get Parking Image  |  Thu thập ảnh từ hệ thống iParking",
              bg=CARD, fg=TEXT, font=F_BOLD).pack(side=LEFT, padx=4, pady=8)

        # ── Tab (IParkingImageTab quản lý scroll nội bộ) ──────────────────────
        self._tab = IParkingImageTab(self, self)
        self._tab.pack(fill=BOTH, expand=True)

        self._bind_shortcuts()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _bind_shortcuts(self):
        tab = self._tab
        self.bind("<F5>",        lambda _: self._dispatch(tab, "_start"))
        self.bind("<Escape>",    lambda _: self._dispatch(tab, "_stop"))
        self.bind("<Control-o>", lambda _: self._dispatch(tab, "_browse"))
        self.bind("<Control-s>", lambda _: self._dispatch(tab, "_show_stats"))
        self.bind("<Control-l>", lambda _: self._clear_log(tab))
        self.bind("<F1>",        lambda _: self._show_help())

    def _dispatch(self, tab, *methods):
        for m in methods:
            fn = getattr(tab, m, None)
            if fn and callable(fn):
                fn()
                return

    def _clear_log(self, tab):
        w = getattr(tab, "log_txt", None) or getattr(tab, "log", None)
        if w and not callable(w):
            try:
                w.configure(state=NORMAL)
                w.delete("1.0", END)
                w.configure(state=DISABLED)
            except Exception:
                pass

    def _show_help(self):
        messagebox.showinfo("Phím tắt — KZTEK Get Parking Image", (
            "F5              Bắt đầu thu thập ảnh\n"
            "Escape          Dừng\n"
            "Ctrl+O          Chọn thư mục lưu\n"
            "Ctrl+S          Thống kê ảnh đã lưu\n"
            "Ctrl+L          Xóa log\n"
            "F1              Hiện bảng phím tắt này\n"
        ))

    def _on_close(self):
        try:
            _cfg_save()
        except Exception:
            pass
        self.destroy()
        sys.exit(0)


if __name__ == "__main__":
    GetParkingImageApp().mainloop()
