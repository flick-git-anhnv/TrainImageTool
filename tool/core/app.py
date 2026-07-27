import sys
from tkinter import *
from tkinter import ttk, messagebox

from .imports import _DND_OK, _dnd_mod
from .ui_helpers import _style_all
from .constants import BG, CARD, ACCENT, ACCENT2, TEXT, DIM, F_MAIN, F_BOLD
from .settings import _CFG, _cfg_save, _cfg_flush, last_save_error, _SETTINGS_FILE

from ..features.dataset.tab_split        import SplitTab
from ..features.dataset.tab_rename       import RenameTab
from ..features.dataset.tab_crop         import CropByLabelTab
from ..features.dataset.tab_labelnorm    import LabelNormTab
from ..features.annotation.tab_bbox      import BBoxEditorTab
from ..features.collection.tab_iparking_image import IParkingImageTab
from ..features.collection.tab_web_image     import WebImageTab
from ..features.annotation.tab_segment   import SegmentTab
from ..features.annotation.tab_checker   import CheckerTab
from ..features.analysis.tab_stats       import StatsTab
from ..features.analysis.tab_plate_search import PlateSearchTab
from ..features.detection.tab_yolo       import YoloTab
from ..features.training.tab_train       import TrainTab
from ..features.training.tab_classifier  import ClassifierTrainTab
from ..features.detection.tab_lpr_tester import LprTesterTab
from ..features.detection.tab_slot_classifier import SlotClassifierTab
from ..features.detection.tab_classifier_tester import ClassifierTesterTab

_AppBase = _dnd_mod.Tk if _DND_OK else Tk


def _fill_scrollable(outer, TabClass, root_ref, *extra_args):
    """Đổ Canvas+Scrollbar + TabClass vào một outer Frame đã có sẵn.

    Khi nội dung nhỏ hơn canvas thì frame tự co giãn theo canvas
    (giữ layout side=BOTTOM và expand=True hoạt động đúng).
    Khi nội dung cao hơn canvas thì scrollbar xuất hiện.

    Tách khỏi việc tạo `outer` để `App` có thể add tab rỗng vào Notebook trước
    (rẻ), rồi mới dựng nội dung ở lần user mở tab đó lần đầu — xem `_ensure_built`.
    """
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

    _mw_entered = [False]

    def _mw(ev): canvas.yview_scroll(int(-1 * (ev.delta / 120)), "units")

    def _on_enter(_):
        _mw_entered[0] = True
        canvas.bind_all("<MouseWheel>", _mw)

    def _on_leave(_):
        _mw_entered[0] = False
        canvas.after(20, lambda: canvas.unbind_all("<MouseWheel>") if not _mw_entered[0] else None)

    canvas.bind("<Enter>", _on_enter)
    canvas.bind("<Leave>", _on_leave)

    return tab


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

        # ── Toolbar ───────────────────────────────────────────────────────────
        topbar = Frame(self, bg=CARD, height=36)
        topbar.pack(fill=X, padx=0, pady=(0, 0))
        topbar.pack_propagate(False)

        Label(topbar, text="KZTEK Image Tools",
              bg=CARD, fg=TEXT, font=F_BOLD).pack(side=LEFT, padx=12)

        btn_cfg = Button(
            topbar, text="⚙  Cài đặt Tab",
            bg=ACCENT2, fg="white", activebackground=ACCENT, activeforeground="white",
            relief=FLAT, bd=0, padx=10, pady=0, cursor="hand2",
            font=F_MAIN, command=self._open_tab_config,
        )
        btn_cfg.pack(side=RIGHT, padx=8, pady=4)

        # ── Notebook ──────────────────────────────────────────────────────────
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
            ("✂️ Segment",        SegmentTab,        ()),
            ("📷 iParking Image", IParkingImageTab,  ()),
            ("🌐 Web Image",      WebImageTab,       ()),
            ("✔ Checker",        CheckerTab,        (nb,)),
            ("📊 Stats",          StatsTab,          ()),
            ("🔎 Plate Search",   PlateSearchTab,    ()),
            ("🤖 YOLO Detect",    YoloTab,           ()),
            ("🚀 Train",          TrainTab,          ()),
            ("🧠 Classifier",     ClassifierTrainTab,()),
            ("🔬 LPR Tester",     LprTesterTab,      ()),
            ("🅿 Slot Detect",    SlotClassifierTab,       ()),
            ("🧪 Cls Tester",    ClassifierTesterTab,     ()),
        ]

        # Khởi tạo lookup structures
        self._tab_titles: list = []      # [title, ...] theo đúng thứ tự hiển thị
        self._tab_outers: dict = {}      # title -> outer Frame
        self._outer_to_tab: dict = {}    # outer Frame -> tab_obj (CHỈ tab đã dựng)
        self._tab_shown: dict = {}       # title -> bool
        self._tab_pending: dict = {}     # outer Frame -> (title, TabClass, extra)

        saved_enabled = _CFG.get("app.enabled_tabs", {})

        # Chỉ add khung rỗng — nội dung tab được dựng ở lần mở đầu tiên
        # (_ensure_built). Dựng đủ 17 tab ngay lúc này tốn ~4 giây và phần lớn
        # là công vô ích: user thường chỉ dùng vài tab mỗi phiên.
        for title, TabClass, extra in _tab_defs:
            outer = Frame(nb, bg=BG)
            self._tab_titles.append(title)
            self._tab_outers[title] = outer
            self._tab_pending[outer] = (title, TabClass, extra)
            self._tab_shown[title] = bool(saved_enabled.get(title, True))
            nb.add(outer, text=f"  {title}  ")

        # Ẩn các tab bị tắt sau khi đã add tất cả
        for title in self._tab_titles:
            if not self._tab_shown[title]:
                nb.tab(self._tab_outers[title], state="hidden")

        nb.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        self._bind_shortcuts()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Dựng ngay tab đang được chọn (tab đầu tiên đang hiển thị) — sự kiện
        # <<NotebookTabChanged>> đầu tiên có thể đã bắn trước khi bind ở trên.
        self.after_idle(self._on_tab_changed)

    # ── Dựng tab lười ─────────────────────────────────────────────────────────

    def _ensure_built(self, outer):
        """Dựng nội dung của một tab nếu chưa dựng. Trả về tab object."""
        tab = self._outer_to_tab.get(outer)
        if tab is not None:
            return tab
        pending = self._tab_pending.pop(outer, None)
        if pending is None:
            return None
        _title, TabClass, extra = pending
        tab = _fill_scrollable(outer, TabClass, self, *extra)
        self._outer_to_tab[outer] = tab
        return tab

    def _on_tab_changed(self, _event=None):
        try:
            outer = self.nametowidget(self._nb.select())
        except Exception:
            return
        self._ensure_built(outer)

    @property
    def _tab_objects(self):
        """Danh sách tab ĐÃ dựng (giữ tương thích với code cũ)."""
        return list(self._outer_to_tab.values())

    # ── Config Tab Dialog ─────────────────────────────────────────────────────

    def _set_tab_visible(self, title: str, visible: bool):
        outer = self._tab_outers[title]
        self._nb.tab(outer, state="normal" if visible else "hidden")
        self._tab_shown[title] = visible

    def _open_tab_config(self):
        win = Toplevel(self)
        win.title("Cài đặt Tab hiển thị")
        win.configure(bg=BG)
        win.resizable(False, False)
        win.transient(self)
        win.grab_set()

        # ── Header ────────────────────────────────────────────────────────────
        hdr = Frame(win, bg=ACCENT2, height=40)
        hdr.pack(fill=X)
        hdr.pack_propagate(False)
        Label(hdr, text="  Chọn tab muốn hiển thị",
              bg=ACCENT2, fg="white", font=F_BOLD).pack(side=LEFT, padx=8)

        # ── Checkboxes ────────────────────────────────────────────────────────
        body = Frame(win, bg=BG, padx=24, pady=12)
        body.pack(fill=BOTH)

        Label(body, text="Bật/tắt từng tab — phải giữ ít nhất 1 tab.",
              bg=BG, fg=DIM, font=("Segoe UI", 9)).pack(anchor=W, pady=(0, 10))

        chk_vars: dict = {}
        for title in self._tab_titles:
            var = BooleanVar(value=self._tab_shown.get(title, True))
            chk_vars[title] = var
            row = Frame(body, bg=BG)
            row.pack(fill=X, pady=2)
            cb = Checkbutton(
                row, text=f"  {title}", variable=var,
                bg=BG, fg=TEXT, selectcolor=CARD,
                activebackground=BG, activeforeground=ACCENT,
                font=F_MAIN, anchor=W,
            )
            cb.pack(side=LEFT)

        # ── Nút Chọn tất / Bỏ tất ────────────────────────────────────────────
        quick = Frame(body, bg=BG)
        quick.pack(anchor=W, pady=(6, 2))

        def _select_all():
            for v in chk_vars.values():
                v.set(True)

        def _deselect_all():
            # Chừa lại tab đầu tiên
            first = True
            for v in chk_vars.values():
                v.set(first)
                first = False

        Button(quick, text="Chọn tất cả", bg=CARD, fg=TEXT, relief=FLAT,
               padx=6, font=F_MAIN, command=_select_all).pack(side=LEFT, padx=(0, 6))
        Button(quick, text="Bỏ tất cả (giữ 1)", bg=CARD, fg=TEXT, relief=FLAT,
               padx=6, font=F_MAIN, command=_deselect_all).pack(side=LEFT)

        # ── Buttons Apply / Cancel ─────────────────────────────────────────────
        sep = Frame(win, bg=ACCENT2, height=1)
        sep.pack(fill=X, pady=(8, 0))

        btn_row = Frame(win, bg=CARD, pady=8)
        btn_row.pack(fill=X)

        def _apply():
            # Validate: ít nhất 1 tab được bật
            if not any(v.get() for v in chk_vars.values()):
                messagebox.showwarning(
                    "Không hợp lệ",
                    "Phải giữ ít nhất 1 tab được bật.",
                    parent=win,
                )
                return

            new_state = {t: v.get() for t, v in chk_vars.items()}
            for title, visible in new_state.items():
                self._set_tab_visible(title, visible)

            _CFG["app.enabled_tabs"] = new_state
            _cfg_save()
            win.destroy()

        Button(btn_row, text="✔  Áp dụng",
               bg=ACCENT, fg="white", activebackground="#d04510",
               relief=FLAT, padx=14, pady=4, font=F_BOLD,
               command=_apply).pack(side=RIGHT, padx=(6, 12))
        Button(btn_row, text="Hủy",
               bg=CARD, fg=TEXT, activebackground=ACCENT2,
               relief=FLAT, padx=14, pady=4, font=F_MAIN,
               command=win.destroy).pack(side=RIGHT, padx=4)

        # Center dialog relative to main window
        self.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 380) // 2
        y = self.winfo_y() + (self.winfo_height() - 520) // 2
        win.geometry(f"380x{12 + 40 + 32 + len(self._tab_titles) * 30 + 120}+{x}+{y}")
        win.lift()
        win.focus_set()

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
            selected_path = self._nb.select()
            outer = self.nametowidget(selected_path)
            # _ensure_built thay vì .get(): phím tắt có thể bắn trước khi
            # <<NotebookTabChanged>> kịp dựng tab đang chọn.
            return self._ensure_built(outer)
        except Exception:
            return None

    def _tab_step(self, delta):
        try:
            all_tabs = self._nb.tabs()
            visible = [t for t in all_tabs
                       if self._nb.tab(t, "state") != "hidden"]
            if not visible:
                return
            cur = self._nb.select()
            idx = visible.index(cur) if cur in visible else 0
            self._nb.select(visible[(idx + delta) % len(visible)])
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
        # _cfg_flush: ghi ngay ca phan dang cho debounce (xem core/settings.py)
        if not _cfg_flush():
            # Truoc day loi ghi settings bi nuot im lang — user mat toan bo cau
            # hinh ma khong biet ly do. Bao ro va cho user co hoi huy thoat.
            if not messagebox.askokcancel(
                    "Không lưu được cài đặt",
                    f"Không ghi được file cài đặt:\n{_SETTINGS_FILE}\n\n"
                    f"Lý do: {last_save_error()}\n\n"
                    "Nhấn OK để thoát và mất các thay đổi, "
                    "hoặc Cancel để quay lại."):
                return
        self.destroy()
        sys.exit(0)
