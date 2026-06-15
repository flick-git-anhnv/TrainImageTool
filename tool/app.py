import sys
from tkinter import *
from tkinter import ttk

from .imports import _DND_OK, _dnd_mod
from .ui_helpers import _style_all
from .constants import BG

from .tab_split        import SplitTab
from .tab_rename       import RenameTab
from .tab_crop         import CropByLabelTab
from .tab_labelnorm    import LabelNormTab
from .tab_bbox         import BBoxEditorTab
from .tab_lotte        import LotteImageTab
from .tab_parkingv8    import Parkingv8ImageTab
from .tab_parkingv6    import Parkingv6ImageTab
from .tab_checker      import CheckerTab
from .tab_stats        import StatsTab
from .tab_plate_search import PlateSearchTab
from .tab_yolo         import YoloTab
from .tab_train        import TrainTab

_AppBase = _dnd_mod.Tk if _DND_OK else Tk


def _wrap_scrollable(nb_parent, TabClass, root_ref, *extra_args):
    """Tạo outer Frame có Canvas+Scrollbar, đặt TabClass bên trong.

    Khi nội dung nhỏ hơn canvas thì frame tự co giãn theo canvas
    (giữ layout side=BOTTOM và expand=True hoạt động đúng).
    Khi nội dung cao hơn canvas thì scrollbar xuất hiện.
    """
    outer = Frame(nb_parent, bg=BG)

    canvas = Canvas(outer, bg=BG, highlightthickness=0)
    vsb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=vsb.set)
    vsb.pack(side=RIGHT, fill=Y)
    canvas.pack(side=LEFT, fill=BOTH, expand=True)

    tab = TabClass(canvas, root_ref, *extra_args)
    cw = canvas.create_window((0, 0), window=tab, anchor="nw")

    def _on_tab_resize(_):
        canvas.configure(scrollregion=canvas.bbox("all"))
    tab.bind("<Configure>", _on_tab_resize)

    def _on_canvas_resize(e):
        req_h = tab.winfo_reqheight()
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

    return outer, tab


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

        self.configure(bg=BG)
        _style_all()

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill=BOTH, expand=True, padx=6, pady=6)
        nb = self._nb

        # (tiêu đề, lớp tab, tuple tham số thêm ngoài root)
        _tab_defs = [
            ("✂ Split",          SplitTab,          ()),
            ("✏ Rename",         RenameTab,         ()),
            ("🖼 Crop",           CropByLabelTab,    ()),
            ("⚙ LabelNorm",      LabelNormTab,      ()),
            ("🖊 BBox Editor",    BBoxEditorTab,     ()),
            ("🅻 LotteImage",     LotteImageTab,     ()),
            ("🅿 Parkingv8Image", Parkingv8ImageTab, ()),
            ("🅿 Parkingv6Image", Parkingv6ImageTab, ()),
            ("✔ Checker",        CheckerTab,        (nb,)),
            ("📊 Stats",          StatsTab,          ()),
            ("🔎 Plate Search",   PlateSearchTab,    ()),
            ("🤖 YOLO Detect",    YoloTab,           ()),
            ("🚀 Train",          TrainTab,          ()),
        ]

        self._tab_objects = []
        for title, TabClass, extra in _tab_defs:
            outer, tab_obj = _wrap_scrollable(nb, TabClass, self, *extra)
            nb.add(outer, text=f"  {title}  ")
            self._tab_objects.append(tab_obj)

        self._bind_shortcuts()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Phím tắt toàn cục ─────────────────────────────────────────────────

    def _bind_shortcuts(self):
        self.bind("<F5>",                self._global_f5)
        self.bind("<F1>",                self._global_f1)
        self.bind("<Escape>",            self._global_esc)
        self.bind("<Control-o>",         self._global_ctrl_o)
        self.bind("<Control-s>",         self._global_ctrl_s)
        self.bind("<Control-z>",         self._global_ctrl_z)
        self.bind("<Control-l>",         self._global_ctrl_l)
        self.bind("<Control-a>",         self._global_ctrl_a)
        self.bind("<Control-Tab>",       lambda e: self._tab_step(+1))
        self.bind("<Control-Shift-Tab>", lambda e: self._tab_step(-1))
        self.bind("<Left>",              self._global_left)
        self.bind("<Right>",             self._global_right)
        self.bind("<Delete>",            self._global_delete_key)
        self.bind("<Return>",            self._global_return)
        self.bind("<space>",             self._global_space)

    def _current_tab(self):
        try:
            idx = self._nb.index(self._nb.select())
            return self._tab_objects[idx]
        except Exception:
            return None

    def _tab_step(self, delta):
        try:
            n = len(self._nb.tabs())
            idx = (self._nb.index(self._nb.select()) + delta) % n
            self._nb.select(idx)
        except Exception:
            pass

    # F5 — bắt đầu / chạy hành động chính của tab
    def _global_f5(self, e=None):
        tab = self._current_tab()
        if not tab:
            return
        for m in ("_run", "_start_train", "_start", "_scan",
                  "load_dataset", "_load", "_refresh", "_run_detect"):
            if hasattr(tab, m) and callable(getattr(tab, m)):
                getattr(tab, m)()
                return

    # Esc — dừng tiến trình đang chạy
    def _global_esc(self, e=None):
        tab = self._current_tab()
        if not tab:
            return
        for m in ("_stop", "_stop_train", "stop_action"):
            if hasattr(tab, m) and callable(getattr(tab, m)):
                getattr(tab, m)()
                return

    # Ctrl+O — mở file/thư mục chính của tab
    def _global_ctrl_o(self, e=None):
        tab = self._current_tab()
        if not tab:
            return
        for m in ("_browse", "load_dataset", "_load",
                  "_load_file", "select_image", "_select_image", "_load_dataset"):
            if hasattr(tab, m) and callable(getattr(tab, m)):
                getattr(tab, m)()
                return

    # Ctrl+S — lưu / export
    def _global_ctrl_s(self, e=None):
        tab = self._current_tab()
        if not tab:
            return
        for m in ("_save", "_export", "_gen_yaml_only", "save_action", "_save_labels"):
            if hasattr(tab, m) and callable(getattr(tab, m)):
                getattr(tab, m)()
                return

    # Ctrl+L — xóa log box của tab hiện tại
    def _global_ctrl_l(self, e=None):
        tab = self._current_tab()
        if not tab:
            return
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

    # Ctrl+A — chọn tất cả trong widget đang focus
    def _global_ctrl_a(self, e=None):
        w = self.focus_get()
        if w is None:
            return
        if isinstance(w, Listbox):
            w.select_set(0, END)
            return "break"
        if isinstance(w, ttk.Treeview):
            for item in w.get_children():
                w.selection_add(item)
            return "break"
        if isinstance(w, Text):
            w.tag_add("sel", "1.0", "end")
            return "break"
        # Entry: để Tkinter xử lý mặc định

    # Ctrl+Z — undo
    def _global_ctrl_z(self, e=None):
        w = self.focus_get()
        if isinstance(w, (Entry, ttk.Combobox, Text, Spinbox)):
            return  # để widget tự xử lý undo nội bộ
        tab = self._current_tab()
        if not tab:
            return
        for m in ("_undo", "undo"):
            if hasattr(tab, m) and callable(getattr(tab, m)):
                getattr(tab, m)()
                return "break"

    # Delete — xóa item đang chọn
    def _global_delete_key(self, e=None):
        w = self.focus_get()
        if isinstance(w, (Entry, ttk.Combobox, Text, Spinbox)):
            return  # để widget tự xử lý
        tab = self._current_tab()
        if not tab:
            return
        for m in ("_on_delete", "_delete_selected", "_delete_current", "_delete_item"):
            if hasattr(tab, m) and callable(getattr(tab, m)):
                getattr(tab, m)()
                return "break"

    # Return — xác nhận hành động chính (YOLO: mark correct)
    def _global_return(self, e=None):
        w = self.focus_get()
        if isinstance(w, (Entry, ttk.Combobox, Text, Spinbox)):
            return
        tab = self._current_tab()
        if not tab:
            return
        for m in ("_on_return", "_confirm_current"):
            if hasattr(tab, m) and callable(getattr(tab, m)):
                getattr(tab, m)()
                return "break"

    # Space — toggle autoplay / play/pause
    def _global_space(self, e=None):
        w = self.focus_get()
        if isinstance(w, (Entry, ttk.Combobox, Text, Spinbox)):
            return
        tab = self._current_tab()
        if not tab:
            return
        for m in ("_toggle_autoplay", "_toggle_play"):
            if hasattr(tab, m) and callable(getattr(tab, m)):
                getattr(tab, m)()
                return "break"

    # F1 — hiện bảng phím tắt
    def _global_f1(self, e=None):
        from tkinter import messagebox
        tab = self._current_tab()
        if tab:
            for m in ("_show_help",):
                if hasattr(tab, m) and callable(getattr(tab, m)):
                    getattr(tab, m)()
                    return
        _HELP = (
            "Phím tắt — KZTEK Image Tools\n"
            "─────────────────────────────\n"
            "Ctrl+O          Mở file / thư mục chính\n"
            "Ctrl+S          Lưu / Export kết quả\n"
            "F5              Chạy / Bắt đầu xử lý\n"
            "Escape          Dừng tiến trình\n"
            "Ctrl+Z          Hoàn tác (Undo)\n"
            "Ctrl+L          Xóa log\n"
            "Ctrl+A          Chọn tất cả\n"
            "Delete          Xóa item đang chọn\n"
            "Ctrl+Tab        Tab kế tiếp\n"
            "Ctrl+Shift+Tab  Tab trước\n"
            "←  /  →         Ảnh trước / ảnh sau\n"
            "Return          Xác nhận (YOLO: Mark correct)\n"
            "Space           Toggle autoplay\n"
            "F1              Hiện bảng phím tắt này\n"
        )
        messagebox.showinfo("Phím tắt", _HELP)

    # ← điều hướng ảnh trước
    def _global_left(self, e=None):
        if isinstance(self.focus_get(), (Entry, ttk.Combobox, Text, Spinbox)):
            return  # không can thiệp khi đang nhập liệu
        tab = self._current_tab()
        if not tab:
            return
        for m in ("_prev_image", "nav_prev", "_on_prev_img"):
            if hasattr(tab, m) and callable(getattr(tab, m)):
                getattr(tab, m)()
                return

    # → điều hướng ảnh sau
    def _global_right(self, e=None):
        if isinstance(self.focus_get(), (Entry, ttk.Combobox, Text, Spinbox)):
            return
        tab = self._current_tab()
        if not tab:
            return
        for m in ("_next_image", "nav_next", "_on_next_img"):
            if hasattr(tab, m) and callable(getattr(tab, m)):
                getattr(tab, m)()
                return

    # ── Đóng ──────────────────────────────────────────────────────────────

    def _on_close(self):
        try:
            from .settings import _cfg_save
            _cfg_save()
        except Exception:
            pass
        self.destroy()
        sys.exit(0)
