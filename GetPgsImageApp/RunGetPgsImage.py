"""GetPgsImage — ứng dụng standalone thu thập ảnh từ hệ thống PGS (file-based)."""

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
from tool.features.collection.tab_pgs_image import PgsImageTab

_AppBase = _dnd_mod.Tk if _DND_OK else Tk


class GetPgsImageApp(_AppBase):
    def __init__(self):
        super().__init__()
        self.title("KZTEK — Get PGS Image")
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
              text="  KZTEK — Get PGS Image  |  Thu thập ảnh từ hệ thống PGS (file-based)",
              bg=CARD, fg=TEXT, font=F_BOLD).pack(side=LEFT, padx=4, pady=8)

        # ── Tab (scrollable container) ────────────────────────────────────────
        canvas = Canvas(self, bg=BG, highlightthickness=0)
        vsb    = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=RIGHT, fill=Y)
        canvas.pack(side=LEFT, fill=BOTH, expand=True)

        self._tab = PgsImageTab(canvas, self)
        cw = canvas.create_window((0, 0), window=self._tab, anchor="nw")

        def _on_tab_resize(_):
            canvas.configure(scrollregion=canvas.bbox("all"))
        self._tab.bind("<Configure>", _on_tab_resize)

        def _on_canvas_resize(e):
            req_h = self._tab.winfo_reqheight()
            h = max(req_h, e.height)
            canvas.itemconfig(cw, width=e.width, height=h)
            canvas.configure(scrollregion=canvas.bbox("all"))
        canvas.bind("<Configure>", _on_canvas_resize)

        def _enter(_):
            canvas.bind_all(
                "<MouseWheel>",
                lambda ev: canvas.yview_scroll(int(-1 * (ev.delta / 120)), "units"))
        def _leave(_):
            canvas.unbind_all("<MouseWheel>")
        canvas.bind("<Enter>", _enter)
        canvas.bind("<Leave>", _leave)

        self._bind_shortcuts()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _bind_shortcuts(self):
        tab = self._tab
        self.bind("<F5>",            lambda _: self._dispatch(tab, "_start"))
        self.bind("<Escape>",        lambda _: self._dispatch(tab, "_stop"))
        self.bind("<Control-o>",     lambda _: self._dispatch(tab, "_browse_source"))
        self.bind("<Control-s>",     lambda _: self._dispatch(tab, "_browse_output"))
        self.bind("<Control-l>",     lambda _: self._dispatch(tab, "_clear_log"))
        self.bind("<F1>",            lambda _: self._show_help())

    def _dispatch(self, tab, *methods):
        for m in methods:
            fn = getattr(tab, m, None)
            if fn and callable(fn):
                fn()
                return

    def _show_help(self):
        messagebox.showinfo("Phím tắt — KZTEK Get PGS Image", (
            "F5              Bắt đầu thu thập ảnh\n"
            "Escape          Dừng\n"
            "Ctrl+O          Chọn thư mục nguồn\n"
            "Ctrl+S          Chọn thư mục lưu\n"
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
    GetPgsImageApp().mainloop()
