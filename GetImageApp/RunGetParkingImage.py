import sys
import os

# tool package nằm ở thư mục cha (3.Tools/)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tkinter import *
from tkinter import ttk, messagebox

from tool.core.imports import _DND_OK, _dnd_mod
from tool.core.ui_helpers import _style_all
from tool.core.constants import BG, CARD, ACCENT, ACCENT2, TEXT, DIM, F_MAIN, F_BOLD
from tool.core.settings import _CFG, _cfg_save
from tool.features.collection.tab_iparking_image import IParkingImageTab

_AppBase = _dnd_mod.Tk if _DND_OK else Tk


class GetParkingImageApp(_AppBase):
    def __init__(self):
        super().__init__()
        self.title("KZTEK — Get Parking Image")
        self.geometry("1280x820")
        self.minsize(900, 600)
        try:
            self.state("zoomed")
        except Exception:
            pass

        self.configure(bg=BG)
        _style_all()

        # ── Toolbar ──────────────────────────────────────────────────────────
        topbar = Frame(self, bg=CARD, height=36)
        topbar.pack(fill=X)
        topbar.pack_propagate(False)

        Label(topbar, text="  KZTEK — Get Parking Image",
              bg=CARD, fg=TEXT, font=F_BOLD).pack(side=LEFT, padx=4)

        # ── Scrollable content (IParkingImageTab) ────────────────────────────
        canvas = Canvas(self, bg=BG, highlightthickness=0)
        vsb = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=RIGHT, fill=Y)
        canvas.pack(side=LEFT, fill=BOTH, expand=True)

        self._tab = IParkingImageTab(canvas, self)
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

        def _on_enter(_):
            canvas.bind_all(
                "<MouseWheel>",
                lambda ev: canvas.yview_scroll(int(-1 * (ev.delta / 120)), "units"))

        def _on_leave(_):
            canvas.unbind_all("<MouseWheel>")

        canvas.bind("<Enter>", _on_enter)
        canvas.bind("<Leave>", _on_leave)

        self._bind_shortcuts()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _bind_shortcuts(self):
        tab = self._tab
        self.bind("<F5>",        lambda e: self._dispatch(tab, "_run", "_start"))
        self.bind("<Escape>",    lambda e: self._dispatch(tab, "_stop"))
        self.bind("<Control-o>", lambda e: self._dispatch(tab, "_browse", "_load"))
        self.bind("<Control-s>", lambda e: self._dispatch(tab, "_save", "_export"))
        self.bind("<Control-l>", lambda e: self._clear_log(tab))
        self.bind("<F1>",        lambda e: self._show_help())

    def _dispatch(self, tab, *methods):
        for m in methods:
            if hasattr(tab, m) and callable(getattr(tab, m)):
                getattr(tab, m)()
                return

    def _clear_log(self, tab):
        for attr in ("_log", "log"):
            w = getattr(tab, attr, None)
            if w:
                try:
                    w.configure(state=NORMAL)
                    w.delete("1.0", END)
                    w.configure(state=DISABLED)
                except Exception:
                    pass
                return

    def _show_help(self):
        _HELP = (
            "Phím tắt — KZTEK Get Parking Image\n"
            "────────────────────────────────────\n"
            "F5              Chạy / Bắt đầu tải ảnh\n"
            "Escape          Dừng tải\n"
            "Ctrl+O          Mở thư mục\n"
            "Ctrl+S          Lưu / Export\n"
            "Ctrl+L          Xóa log\n"
            "F1              Hiện bảng phím tắt này\n"
        )
        messagebox.showinfo("Phím tắt", _HELP)

    def _on_close(self):
        try:
            _cfg_save()
        except Exception:
            pass
        self.destroy()
        sys.exit(0)


if __name__ == "__main__":
    GetParkingImageApp().mainloop()
