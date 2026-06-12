import sys
from tkinter import *
from tkinter import ttk

from .imports import _DND_OK, _dnd_mod
from .ui_helpers import _style_all

from .tab_split        import SplitTab
from .tab_rename       import RenameTab
from .tab_crop         import CropByLabelTab
from .tab_labelnorm    import LabelNormTab
from .tab_bbox         import BBoxEditorTab
from .tab_lotte        import LotteImageTab
from .tab_parkingv8    import Parkingv8ImageTab
from .tab_checker      import CheckerTab
from .tab_stats        import StatsTab
from .tab_plate_search import PlateSearchTab
from .tab_yolo         import YoloTab
from .tab_train        import TrainTab

_AppBase = _dnd_mod.Tk if _DND_OK else Tk


class App(_AppBase):
    def __init__(self):
        super().__init__()
        self.title("KZTEK Image Tools")
        self.geometry("1280x820")
        self.minsize(900, 600)
        try:
            self.state("zoomed")
        except Exception:
            pass

        from .constants import BG, CARD
        self.configure(bg=BG)

        _style_all()

        nb = ttk.Notebook(self)
        nb.pack(fill=BOTH, expand=True, padx=6, pady=6)

        # ── Dữ liệu ──────────────────────────────────────────────────────────
        tabs = [
            ("✂ Split",          SplitTab(nb, self)),
            ("✏ Rename",         RenameTab(nb, self)),
            ("🖼 Crop",           CropByLabelTab(nb, self)),
            ("⚙ LabelNorm",      LabelNormTab(nb, self)),
            # ── Gán nhãn ──────────────────────────────────────────────────────
            ("🖊 BBox Editor",    BBoxEditorTab(nb, self)),
            ("🅻 LotteImage",     LotteImageTab(nb, self)),
            ("🅿 Parkingv8Image", Parkingv8ImageTab(nb, self)),
            # ── Kiểm tra & Thống kê ────────────────────────────────────────────
            ("✔ Checker",        CheckerTab(nb, self, nb)),
            ("📊 Stats",          StatsTab(nb, self)),
            ("🔎 Plate Search",   PlateSearchTab(nb, self)),
            # ── AI / Model ─────────────────────────────────────────────────────
            ("🤖 YOLO Detect",    YoloTab(nb, self)),
            ("🚀 Train",          TrainTab(nb, self)),
        ]
        for title, tab in tabs:
            nb.add(tab, text=f"  {title}  ")

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        try:
            from .settings import _cfg_save
            _cfg_save()
        except Exception:
            pass
        self.destroy()
        sys.exit(0)
