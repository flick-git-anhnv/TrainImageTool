"""Locate Anything — ứng dụng standalone detect vật thể theo mô tả text (open-vocabulary),
dùng locate-anything.cpp (https://github.com/mudler/locate-anything.cpp) qua subprocess."""

import sys
import os

# tool package nằm ở thư mục cha (d:/Tool)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tkinter import *
from tkinter import messagebox

from tool.core.ui_helpers import _style_all
from tool.core.constants import BG, CARD, TEXT, F_BOLD
from tool.core.settings import _cfg_save
from tool.features.detection.tab_locate_anything import LocateAnythingTab


class LocateAnythingApp(Tk):
    def __init__(self):
        super().__init__()
        self.title("KZTEK — Locate Anything (open-vocabulary detection)")
        self.geometry("1280x860")
        self.minsize(960, 640)
        try:
            self.state("zoomed")
        except Exception:
            pass
        self.configure(bg=BG)
        _style_all()

        topbar = Frame(self, bg=CARD, height=38)
        topbar.pack(fill=X)
        topbar.pack_propagate(False)
        Label(topbar,
              text="  KZTEK — Locate Anything  |  Detect vật thể theo mô tả text (locate-anything.cpp)",
              bg=CARD, fg=TEXT, font=F_BOLD).pack(side=LEFT, padx=4, pady=8)

        self._tab = LocateAnythingTab(self, self)
        self._tab.pack(fill=BOTH, expand=True)

        self._bind_shortcuts()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _bind_shortcuts(self):
        tab = self._tab
        self.bind("<F5>",        lambda _: tab._detect_single())
        self.bind("<Escape>",    lambda _: tab._stop())
        self.bind("<Control-o>", lambda _: tab._browse_image())
        self.bind("<Control-s>", lambda _: tab._export_csv())
        self.bind("<Control-a>", lambda _: tab.select_all_batch())
        self.bind("<Left>",      lambda _: tab._nav_batch(-1))
        self.bind("<Right>",     lambda _: tab._nav_batch(1))
        self.bind("<F1>",        lambda _: self._show_help())

    def _show_help(self):
        messagebox.showinfo("Phím tắt — KZTEK Locate Anything", (
            "F5              Detect ảnh đơn\n"
            "Escape          Dừng tiến trình đang chạy\n"
            "Ctrl+O          Chọn ảnh đơn\n"
            "Ctrl+S          Xuất CSV kết quả batch\n"
            "Ctrl+A          Chọn tất cả dòng kết quả batch\n"
            "←  /  →         Điều hướng ảnh trước/sau (batch)\n"
            "F1              Hiện bảng phím tắt này\n"
            "\n"
            "Double-click ảnh kết quả để phóng to.\n"
        ))

    def _on_close(self):
        try:
            _cfg_save()
        except Exception:
            pass
        self.destroy()
        sys.exit(0)


if __name__ == "__main__":
    LocateAnythingApp().mainloop()
