"""tab_classifier_tester.py — Test YOLO Image Classifier.

Tính năng:
  * Load model YOLO classify (.pt)
  * Sidebar ảnh: tìm kiếm, lọc ✓/✗/?, subfolder
  * ← → điều hướng, Auto-play
  * Vẽ bbox tay → phân loại chỉ vùng đó (crosshair, 8 handle resize/move)
  * F5 = classify toàn ảnh (hoặc bbox nếu đã vẽ)
  * Conf slider, Top-N, Zoom Ctrl+scroll / −/+/Fit
  * Mark ✓/✗ → di chuyển ảnh vào correct/incorrect/
  * Batch export CSV
  * Drag-drop ảnh/folder
  * Top-N bars + crop preview + log box
"""

import os
import queue
import shutil
import threading
from tkinter import *
from tkinter import filedialog, messagebox, ttk

from ...core.constants import (BG, CARD, ACCENT, ACCENT2, TEXT, DIM, SUCCESS,
                                F_MAIN, F_BOLD, F_MONO, IMAGE_EXTENSIONS)
from ...core.settings import (_bind_cfg, _bind_history, _push_history,
                               _get_history, _CFG, _cfg_save)
from ...core.ui_helpers import _make_logbox, _append_log

try:
    from PIL import Image, ImageDraw, ImageTk
    _PIL_OK = True
except ImportError:
    _PIL_OK = False

try:
    from ultralytics import YOLO as _YOLO
    _YOLO_OK = True
except ImportError:
    _YOLO_OK = False

try:
    from tkinterdnd2 import DND_FILES
    _DND_OK = True
except ImportError:
    _DND_OK = False

_EXTS          = IMAGE_EXTENSIONS          # already dotted: {".jpg", ...}
_BAR_COLORS    = [ACCENT, "#4fc3f7", "#81c784", "#fff176", "#ce93d8"]
_HS            = 5                          # handle half-size (canvas px)
_CURSOR_DRAW   = "crosshair"
_CURSOR_MOVE   = "fleur"
_CURSOR_RESIZE = "sizing"
_REVIEW_ICON   = {"correct": "✓", "incorrect": "✗", "": "○"}


def _review_state(path: str) -> str:
    parent = os.path.basename(os.path.dirname(path))
    if parent == "correct":   return "correct"
    if parent == "incorrect": return "incorrect"
    return ""


class ClassifierTesterTab(Frame):
    """Tab test YOLO Image Classifier — ảnh đơn, bbox vẽ tay, batch folder."""

    def __init__(self, master, root):
        super().__init__(master, bg=BG)
        self.root = root

        # ── Model ─────────────────────────────────────────────────────────
        self._model        = None
        self._model_names: dict = {}

        # ── Image state ───────────────────────────────────────────────────
        self.current_image_path: str | None = None
        self._pil_full     = None   # PIL image hiện tại (full-res)
        self._tk_img       = None
        self._zoom_factor  = 0.0   # 0 = fit
        self._img_scale    = 1.0
        self._img_off_x    = 0
        self._img_off_y    = 0

        # ── Bbox state ────────────────────────────────────────────────────
        self._bx1 = self._by1 = self._bx2 = self._by2 = None
        self._rect_id:    int | None = None
        self._handle_ids: list = []
        self._mode        = "draw"   # "draw" | "move" | "resize_XX"
        self._drag_cx = self._drag_cy = 0
        self._drag_bx1 = self._drag_by1 = self._drag_bx2 = self._drag_by2 = 0.0
        self._draw_start  = None
        self._crop_pil    = None
        self._result_color = ACCENT

        # ── Crop mode ─────────────────────────────────────────────────────
        self._crop_mode     = "rect"   # "rect" | "4pt"
        self._pts4: list    = []       # image-space (ix, iy), max 4
        self._persp_pil     = None     # perspective-warped result
        self._drag_pt_idx   = None     # index 0-3 of point being dragged

        # ── Image list ────────────────────────────────────────────────────
        self.image_list:   list = []
        self._all_images:  list = []
        self._base_folder: str | None = None
        self._active_filter = "all"
        self._tree_iid_map: dict = {}
        self._path_to_iid:  dict = {}
        self._autoplay_id  = None
        self._search_after = None
        self._last_pairs:  list = []   # top-N từ lần classify cuối

        # ── Tkinter vars ──────────────────────────────────────────────────
        self.v_model_path = StringVar()
        self.v_check_path = StringVar()
        self.v_conf       = DoubleVar(value=0.25)
        self.v_top_n      = IntVar(value=5)
        self.v_subfolder  = BooleanVar(value=False)
        self.v_show_orig  = BooleanVar(value=False)
        self.v_interval   = StringVar(value="2.0")
        self.v_line_width = IntVar(value=2)
        self._v_search    = StringVar()

        _bind_cfg("cls_test.model_path",  self.v_model_path)
        _bind_cfg("cls_test.check_path",  self.v_check_path)
        _bind_cfg("cls_test.conf",        self.v_conf)
        _bind_cfg("cls_test.top_n",       self.v_top_n)
        _bind_cfg("cls_test.subfolder",   self.v_subfolder)
        _bind_cfg("cls_test.show_orig",   self.v_show_orig)
        _bind_cfg("cls_test.interval",    self.v_interval)
        _bind_cfg("cls_test.line_width",  self.v_line_width)

        self._build()
        self.after(200, self._auto_load_model)
        self.after(300, self._bind_keys)
        self.after(400, self._sync_conf_label)

    # ═══════════════════════════════════════════════════════════════ BUILD ══

    def _build(self):
        self._build_toolbar()
        self._build_content()
        self._build_statusbar()

    # ── Toolbar ───────────────────────────────────────────────────────────

    def _build_toolbar(self):
        bar = Frame(self, bg=CARD, padx=10, pady=8)
        bar.pack(fill=X)

        # Row 0: model ────────────────────────────────────────────────────
        r0 = Frame(bar, bg=CARD)
        r0.pack(fill=X)

        Button(r0, text="Chọn Model (.pt)", command=self._pick_model,
               bg=ACCENT2, fg="white", font=F_BOLD, relief=FLAT,
               padx=10, cursor="hand2",
               activebackground=ACCENT, activeforeground="white"
               ).pack(side=LEFT)

        self.lbl_model = Label(r0, text="Chưa chọn model",
                               font=("Segoe UI", 9, "italic"), bg=CARD, fg=DIM)
        self.lbl_model.pack(side=LEFT, padx=(6, 0))

        Button(r0, text="Lưu kết quả", command=self._save_result,
               bg="#555570", fg="white", font=F_MAIN, relief=FLAT,
               padx=8, cursor="hand2").pack(side=RIGHT)
        Button(r0, text="Export tất cả", command=self._batch_export,
               bg="#4a3f00", fg="#ffcc00", font=F_MAIN, relief=FLAT,
               padx=8, cursor="hand2").pack(side=RIGHT, padx=(0, 4))

        # Row 1: path input ───────────────────────────────────────────────
        r1 = Frame(bar, bg=CARD)
        r1.pack(fill=X, pady=(6, 0))

        self.combo_path = ttk.Combobox(
            r1, textvariable=self.v_check_path, font=F_MAIN)
        self.combo_path.pack(side=LEFT, fill=X, expand=True, padx=(0, 4))
        _bind_history("h.cls_test.path", self.combo_path)
        self.combo_path.bind("<Return>", lambda _: self._load_path_input())

        Button(r1, text="▶ Tải", command=self._load_path_input,
               bg=ACCENT, fg="white", font=F_BOLD, relief=FLAT,
               padx=10, cursor="hand2",
               activebackground="#c0411a", activeforeground="white"
               ).pack(side=LEFT, padx=(0, 8))
        Button(r1, text="Chọn Ảnh", command=self._select_image,
               bg=ACCENT, fg="white", font=F_MAIN, relief=FLAT,
               padx=8, cursor="hand2",
               activebackground="#c0411a", activeforeground="white"
               ).pack(side=LEFT, padx=(0, 4))
        Button(r1, text="Chọn Thư Mục", command=self._select_folder,
               bg="#2e5fa3", fg="white", font=F_MAIN, relief=FLAT,
               padx=8, cursor="hand2").pack(side=LEFT, padx=(0, 4))
        Button(r1, text="📂", command=self._open_folder,
               bg=CARD, fg=TEXT, font=F_MAIN, relief=FLAT,
               padx=6, cursor="hand2",
               activebackground=ACCENT2, activeforeground="white"
               ).pack(side=LEFT, padx=(0, 6))
        Checkbutton(r1, text="Quét sub folder", variable=self.v_subfolder,
                    bg=CARD, fg=TEXT, activebackground=CARD,
                    activeforeground=TEXT, selectcolor="#16162a",
                    font=F_MAIN, cursor="hand2").pack(side=LEFT)

        # Row 2: Conf + Top-N ─────────────────────────────────────────────
        r2 = Frame(bar, bg=CARD)
        r2.pack(fill=X, pady=(8, 0))

        Label(r2, text="Confidence:", font=F_BOLD, bg=CARD, fg=TEXT).pack(side=LEFT)
        Scale(r2, from_=0.0, to=1.0, resolution=0.05,
              orient=HORIZONTAL, length=200,
              variable=self.v_conf,
              command=self._on_conf_change,
              bg=CARD, fg=TEXT, highlightthickness=0,
              troughcolor="#16162a", activebackground=ACCENT,
              relief=FLAT, bd=0, showvalue=False
              ).pack(side=LEFT, padx=(4, 2))
        self.lbl_conf_val = Label(r2, text="0.25", bg=CARD, fg=ACCENT,
                                  font=F_MONO, width=5)
        self.lbl_conf_val.pack(side=LEFT, padx=(0, 20))

        Label(r2, text="Top-N:", font=F_BOLD, bg=CARD, fg=TEXT).pack(side=LEFT)
        Spinbox(r2, from_=1, to=10, textvariable=self.v_top_n,
                width=3, bg="#16162a", fg=TEXT, insertbackground=TEXT,
                buttonbackground=ACCENT2, relief=FLAT, font=F_MAIN,
                state="readonly").pack(side=LEFT, padx=(4, 0))

        # Row 3: Zoom + Show orig + Autoplay + bbox hint ──────────────────
        r3 = Frame(bar, bg=CARD)
        r3.pack(fill=X, pady=(8, 0))

        Label(r3, text="Zoom:", font=F_BOLD, bg=CARD, fg=TEXT).pack(side=LEFT)
        Button(r3, text="−", command=lambda: self._zoom_step(-0.2),
               bg=CARD, fg=TEXT, font=F_BOLD, relief=FLAT,
               padx=6, cursor="hand2").pack(side=LEFT, padx=(4, 0))
        self.lbl_zoom = Label(r3, text="Fit", bg=CARD, fg=ACCENT,
                              font=F_MONO, width=6)
        self.lbl_zoom.pack(side=LEFT)
        Button(r3, text="+", command=lambda: self._zoom_step(+0.2),
               bg=CARD, fg=TEXT, font=F_BOLD, relief=FLAT,
               padx=6, cursor="hand2").pack(side=LEFT, padx=(0, 2))
        Button(r3, text="Fit", command=lambda: self._zoom_step(0.0),
               bg="#333355", fg=TEXT, font=F_MAIN, relief=FLAT,
               padx=6, cursor="hand2").pack(side=LEFT, padx=(2, 16))

        Checkbutton(r3, text="Ảnh gốc (ẩn bbox)",
                    variable=self.v_show_orig,
                    command=self._render_display,
                    bg=CARD, fg=TEXT, activebackground=CARD,
                    activeforeground=TEXT, selectcolor="#16162a",
                    font=F_MAIN, cursor="hand2").pack(side=LEFT, padx=(0, 16))

        self.btn_autoplay = Button(r3, text="▶ Auto",
                                   command=self._toggle_autoplay,
                                   bg="#2e5fa3", fg="white", font=F_MAIN,
                                   relief=FLAT, padx=8, cursor="hand2")
        self.btn_autoplay.pack(side=LEFT, padx=(0, 4))
        Spinbox(r3, from_=0.5, to=30.0, increment=0.5, width=5, format="%.1f",
                textvariable=self.v_interval,
                bg="#16162a", fg=TEXT, font=F_MONO,
                buttonbackground=CARD, relief=FLAT,
                insertbackground=TEXT).pack(side=LEFT, padx=(0, 2))
        Label(r3, text="s", font=F_MAIN, bg=CARD, fg=DIM).pack(side=LEFT, padx=(0, 14))

        # Crop mode toggle
        Frame(r3, bg=DIM, width=1).pack(side=LEFT, fill=Y, padx=(8, 8))
        Label(r3, text="Cắt:", font=F_BOLD, bg=CARD, fg=TEXT).pack(side=LEFT)
        self._btn_mode_rect = Button(
            r3, text="⬜ Chữ nhật",
            command=lambda: self._set_crop_mode("rect"),
            relief="sunken", bg="#252540", fg=TEXT, font=F_MAIN,
            padx=6, cursor="hand2",
            activebackground=ACCENT, activeforeground="white")
        self._btn_mode_rect.pack(side=LEFT, padx=(4, 2))
        self._btn_mode_4pt = Button(
            r3, text="◈ 4 điểm",
            command=lambda: self._set_crop_mode("4pt"),
            relief="flat", bg=CARD, fg=TEXT, font=F_MAIN,
            padx=6, cursor="hand2",
            activebackground=ACCENT, activeforeground="white")
        self._btn_mode_4pt.pack(side=LEFT, padx=(0, 8))

        # Line-width control
        Frame(r3, bg=DIM, width=1).pack(side=LEFT, fill=Y, padx=(0, 8))
        Label(r3, text="Nét:", font=F_BOLD, bg=CARD, fg=TEXT).pack(side=LEFT)
        Spinbox(r3, from_=1, to=8, textvariable=self.v_line_width,
                width=2, bg="#16162a", fg=ACCENT, font=F_MONO,
                buttonbackground=CARD, relief=FLAT, insertbackground=TEXT,
                command=self._on_line_width_change,
                state="readonly").pack(side=LEFT, padx=(4, 10))

        self.lbl_crop_hint = Label(
            r3,
            text="✏ Kéo để vẽ bbox  |  Ctrl+scroll: zoom  |  Chuột phải: xóa",
            font=("Segoe UI", 8), bg=CARD, fg=DIM)
        self.lbl_crop_hint.pack(side=LEFT)

    # ── Content ───────────────────────────────────────────────────────────

    def _build_content(self):
        content = Frame(self, bg=BG)
        content.pack(fill=BOTH, expand=True)

        # ── Sidebar (190 px) ──────────────────────────────────────────────
        sidebar = Frame(content, bg=CARD, width=190)
        sidebar.pack(side=LEFT, fill=Y, padx=(0, 2))
        sidebar.pack_propagate(False)

        Label(sidebar, text="Danh sách ảnh",
              font=F_BOLD, bg=CARD, fg=TEXT).pack(pady=(8, 2))

        # Search
        sr = Frame(sidebar, bg=CARD)
        sr.pack(fill=X, padx=4, pady=(0, 3))
        Label(sr, text="🔍", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        Entry(sr, textvariable=self._v_search,
              bg="#16162a", fg=TEXT, insertbackground=TEXT,
              relief=FLAT, font=F_MONO, bd=2
              ).pack(side=LEFT, fill=X, expand=True, padx=(2, 0))
        self._v_search.trace_add("write", lambda *_: self._schedule_search())

        # Filter buttons
        fb = Frame(sidebar, bg=CARD)
        fb.pack(fill=X, padx=4, pady=(0, 3))
        self._filter_btns: dict = {}
        for code, lbl, fg in [
            ("all",        "All",  TEXT),
            ("correct",    "✓",   "#4caf50"),
            ("incorrect",  "✗",   ACCENT),
            ("unreviewed", "?",    DIM),
        ]:
            b = Button(fb, text=lbl, width=4,
                       command=lambda c=code: self._apply_filter(c),
                       bg=CARD, fg=fg, font=F_MAIN, relief=FLAT,
                       cursor="hand2", activebackground="#252540",
                       activeforeground=fg)
            b.pack(side=LEFT, padx=1)
            self._filter_btns[code] = b
        self._filter_btns["all"].config(relief="sunken", bg="#252540")

        # Treeview
        tf = Frame(sidebar, bg=CARD)
        tf.pack(fill=BOTH, expand=True, padx=2, pady=(0, 6))

        st = ttk.Style()
        st.configure("ClsT.Treeview",
                     background="#16162a", foreground=TEXT,
                     fieldbackground="#16162a", borderwidth=0,
                     rowheight=20, font=F_MAIN)
        st.map("ClsT.Treeview",
               background=[("selected", ACCENT2)],
               foreground=[("selected", "white")])
        st.configure("ClsT.Treeview.Heading",
                     background=CARD, foreground=TEXT)

        sb_y = Scrollbar(tf, orient=VERTICAL)
        sb_y.pack(side=RIGHT, fill=Y)
        sb_x = Scrollbar(tf, orient=HORIZONTAL)
        sb_x.pack(side=BOTTOM, fill=X)

        self.tree_images = ttk.Treeview(
            tf, style="ClsT.Treeview",
            selectmode="browse", show="tree",
            yscrollcommand=sb_y.set, xscrollcommand=sb_x.set)
        self.tree_images.pack(fill=BOTH, expand=True)
        sb_y.config(command=self.tree_images.yview)
        sb_x.config(command=self.tree_images.xview)
        self.tree_images.bind("<<TreeviewSelect>>", self._on_image_select)
        self.tree_images.tag_configure("correct",    foreground="#4caf50")
        self.tree_images.tag_configure("incorrect",  foreground=ACCENT)
        self.tree_images.tag_configure("unreviewed", foreground=TEXT)
        self.tree_images.tag_configure("folder",     foreground=DIM)

        # ── Main area ─────────────────────────────────────────────────────
        main = Frame(content, bg=BG)
        main.pack(side=LEFT, fill=BOTH, expand=True)

        # Result label
        self.lbl_result = Label(main, text="", font=F_BOLD,
                                 bg=BG, fg=TEXT, anchor=W)
        self.lbl_result.pack(fill=X, padx=6, pady=(4, 0))

        # Mark buttons
        mark_row = Frame(main, bg=BG)
        mark_row.pack(fill=X, padx=6, pady=(2, 0))
        Button(mark_row, text="✓ Đúng  [Enter]",
               command=lambda: self._mark_review("correct"),
               bg="#1a3a1a", fg="#4caf50", font=F_MAIN, relief=FLAT,
               padx=8, cursor="hand2").pack(side=LEFT, padx=(0, 4))
        Button(mark_row, text="✗ Sai  [Del]",
               command=lambda: self._mark_review("incorrect"),
               bg="#3a1a1a", fg=ACCENT, font=F_MAIN, relief=FLAT,
               padx=8, cursor="hand2").pack(side=LEFT, padx=(0, 4))
        Button(mark_row, text="↺ Bỏ đánh dấu",
               command=lambda: self._mark_review(""),
               bg=CARD, fg=DIM, font=F_MAIN, relief=FLAT,
               padx=6, cursor="hand2").pack(side=LEFT)
        self.lbl_mark_state = Label(mark_row, text="", font=F_MONO,
                                     bg=BG, fg=DIM)
        self.lbl_mark_state.pack(side=LEFT, padx=(12, 0))

        # Canvas (ảnh + bbox drawing)
        self.canvas = Canvas(main, bg="#0d0d1a", cursor=_CURSOR_DRAW,
                             highlightthickness=1, highlightbackground=ACCENT2)
        self.canvas.pack(fill=BOTH, expand=True, padx=4, pady=(4, 4))

        self.canvas.bind("<Configure>",          self._on_canvas_resize)
        self.canvas.bind("<Double-Button-1>",    self._on_canvas_dbl)
        self.canvas.bind("<Control-MouseWheel>", self._on_canvas_scroll)
        self.canvas.bind("<ButtonPress-1>",      self._on_press)
        self.canvas.bind("<B1-Motion>",           self._on_drag)
        self.canvas.bind("<ButtonRelease-1>",     self._on_release)
        self.canvas.bind("<Button-3>",            self._clear_box)
        self.canvas.bind("<Motion>",              self._on_motion)

        if _DND_OK:
            try:
                self.canvas.drop_target_register(DND_FILES)
                self.canvas.dnd_bind("<<Drop>>", self._on_drop)
            except Exception:
                pass

        self.canvas.create_text(
            300, 200,
            text="Chọn ảnh hoặc kéo thả vào đây\n"
                 "Vẽ bbox để phân loại vùng cụ thể\n"
                 "Double-click để phóng to  |  Ctrl+scroll để zoom",
            fill=DIM, font=("Segoe UI", 12), justify=CENTER, tags="hint")

        # ── Right panel (275 px) ──────────────────────────────────────────
        right = Frame(content, bg=CARD, width=275)
        right.pack(side=RIGHT, fill=Y)
        right.pack_propagate(False)

        Label(right, text="KẾT QUẢ",
              bg=CARD, fg=TEXT, font=F_BOLD).pack(pady=(10, 4))

        Button(right, text="⚡  Phân loại  (F5)",
               command=self._classify_current,
               bg=ACCENT, fg="white", font=("Segoe UI Semibold", 11),
               relief=FLAT, pady=6, cursor="hand2",
               activebackground="#d04010", activeforeground="white"
               ).pack(fill=X, padx=12, pady=(0, 8))

        # Top-N bars
        bars_fr = Frame(right, bg=CARD, padx=8)
        bars_fr.pack(fill=X)
        self._bar_rows: list = []
        for i in range(5):
            row = Frame(bars_fr, bg=CARD)
            row.pack(fill=X, pady=2)
            lbl_n = Label(row, text="—", bg=CARD, fg=DIM,
                          font=F_MAIN, anchor=W, width=13)
            lbl_n.pack(side=LEFT, padx=(0, 4))
            outer = Frame(row, bg="#333", height=15)
            outer.pack(side=LEFT, fill=X, expand=True)
            inner = Frame(outer, bg=_BAR_COLORS[i], height=15)
            inner.place(x=0, y=0, relheight=1.0, width=0)
            lbl_p = Label(row, text="", bg=CARD, fg=TEXT,
                          font=("Segoe UI", 8), width=6, anchor=E)
            lbl_p.pack(side=LEFT, padx=(3, 0))
            self._bar_rows.append((lbl_n, lbl_p, inner, outer))

        Frame(right, bg=DIM, height=1).pack(fill=X, padx=8, pady=6)

        # Crop preview
        Label(right, text="Vùng bbox",
              bg=CARD, fg=DIM, font=("Segoe UI", 9)).pack()
        self.prev_canvas = Canvas(right, bg="#0d0d1a",
                                  width=240, height=130,
                                  highlightthickness=1,
                                  highlightbackground=ACCENT2)
        self.prev_canvas.pack(padx=10, pady=(2, 4))
        self.prev_canvas.create_text(
            120, 65, text="Vùng bbox hiện ở đây",
            fill=DIM, font=("Segoe UI", 9), tags="prev_hint")
        self._prev_tk = None
        self.prev_canvas.bind("<Double-Button-1>", self._zoom_crop)

        Frame(right, bg=DIM, height=1).pack(fill=X, padx=8, pady=4)

        log_fr, self._log = _make_logbox(right)
        log_fr.pack(fill=BOTH, expand=True, padx=8, pady=(0, 8))

    def _build_statusbar(self):
        self.v_status = StringVar(value="Sẵn sàng")
        Label(self, textvariable=self.v_status,
              font=F_MAIN, bg=CARD, fg=DIM, anchor=W, padx=8
              ).pack(fill=X, side=BOTTOM)

    # ══════════════════════════════════════════════════════════ MODEL LOAD ══

    def _pick_model(self):
        p = filedialog.askopenfilename(
            title="Chọn model YOLO classifier (.pt)",
            filetypes=[("PyTorch model", "*.pt"), ("Tất cả", "*.*")],
            initialdir=os.path.dirname(self.v_model_path.get()) or ".")
        if not p:
            return
        self.v_model_path.set(p)
        _push_history("h.cls_test.model", p)
        self._load_model(p)

    def _auto_load_model(self):
        p = self.v_model_path.get().strip()
        if p and os.path.isfile(p):
            self._load_model(p)

    def _load_model(self, path: str):
        if not _YOLO_OK:
            _append_log(self._log, "⚠ Chưa cài ultralytics: pip install ultralytics")
            return
        self.lbl_model.config(text="⏳ Đang tải…", fg=DIM)
        threading.Thread(target=self._load_model_thread, args=(path,),
                         daemon=True).start()

    def _load_model_thread(self, path: str):
        try:
            model = _YOLO(path)
            task  = getattr(model, "task", "classify") or "classify"
            names: dict = {}
            try:
                names = getattr(model, "names", {}) or {}
            except Exception:
                pass
            if not names:
                try:
                    names = getattr(getattr(model, "model", None), "names", {}) or {}
                except Exception:
                    pass
            if isinstance(names, (list, tuple)):
                names = {i: str(n) for i, n in enumerate(names)}

            self._model       = model
            self._model_names = names
            nc   = len(names)
            n    = os.path.basename(path)
            prev = ", ".join(f"{i}:{v}" for i, v in list(names.items())[:6])
            if nc > 6:
                prev += "…"

            def _ok():
                self.lbl_model.config(
                    text=f"  {n}  [{task}]  {nc} classes", fg=SUCCESS)
                _append_log(self._log, f"✔ Model: {n}  [{task}]  {nc} classes")
                if prev:
                    _append_log(self._log, f"   {prev}")
                if self.current_image_path:
                    self._classify_current()

            self.root.after(0, _ok)

        except Exception as ex:
            msg = str(ex)
            def _err():
                self.lbl_model.config(text=f"  ✘ {msg[:60]}", fg="#f05050")
                _append_log(self._log, f"[LỖI] Tải model: {msg}")
            self.root.after(0, _err)

    # ══════════════════════════════════════════════════════════ FILE LOAD ══

    def _load_path_input(self):
        p = self.v_check_path.get().strip()
        if not p:
            return
        _push_history("h.cls_test.path", p)
        self.combo_path["values"] = _get_history("h.cls_test.path")
        if os.path.isdir(p):
            self._load_folder(p)
        elif os.path.isfile(p):
            self._load_image_list([p])
        else:
            messagebox.showwarning("Không tìm thấy",
                                   f"Đường dẫn không hợp lệ:\n{p}",
                                   parent=self.root)

    def _select_image(self):
        cur  = self.v_check_path.get().strip()
        init = (os.path.dirname(cur) if cur and os.path.isfile(cur)
                else cur              if cur and os.path.isdir(cur) else ".")
        path = filedialog.askopenfilename(
            title="Chọn ảnh",
            initialdir=init if os.path.isdir(init) else ".",
            filetypes=[("Ảnh", " ".join(_EXTS)), ("Tất cả", "*.*")],
            parent=self.root)
        if path:
            self.v_check_path.set(path)
            _push_history("h.cls_test.path", path)
            self.combo_path["values"] = _get_history("h.cls_test.path")
            self._load_image_list([path])

    def _select_folder(self):
        cur  = self.v_check_path.get().strip()
        init = cur if cur and os.path.isdir(cur) else "."
        folder = filedialog.askdirectory(
            title="Chọn thư mục ảnh",
            initialdir=init if os.path.isdir(init) else ".",
            parent=self.root)
        if folder:
            self.v_check_path.set(folder)
            _push_history("h.cls_test.path", folder)
            self.combo_path["values"] = _get_history("h.cls_test.path")
            self._load_folder(folder)

    def _open_folder(self):
        p = self.v_check_path.get().strip()
        d = p if os.path.isdir(p) else os.path.dirname(p) if p else ""
        if d and os.path.isdir(d):
            os.startfile(d)

    def _scan_images(self, folder: str) -> list:
        if not folder or not os.path.isdir(folder):
            return []
        return sorted(os.path.join(folder, f) for f in os.listdir(folder)
                      if os.path.splitext(f)[1].lower() in _EXTS)

    def _load_folder(self, folder: str):
        self._base_folder = folder
        _SKIP = {"correct", "incorrect"}
        if self.v_subfolder.get():
            files = sorted(
                os.path.join(r, f)
                for r, dirs, fnames in os.walk(folder)
                for f in fnames
                if os.path.splitext(f)[1].lower() in _EXTS
                and os.path.basename(r) not in _SKIP)
        else:
            files = sorted(
                os.path.join(folder, f) for f in os.listdir(folder)
                if os.path.splitext(f)[1].lower() in _EXTS)
        if not files:
            messagebox.showinfo(
                "Thông báo", "Không tìm thấy ảnh trong thư mục!",
                parent=self.root)
            return
        self._load_image_list(files)

    def _load_image_list(self, files: list):
        self._all_images = list(files)
        if not self._base_folder and files:
            self._base_folder = os.path.dirname(files[0])
        self._active_filter = "all"
        for code, btn in self._filter_btns.items():
            btn.config(
                relief="sunken" if code == "all" else "flat",
                bg="#252540" if code == "all" else CARD)
        self._rebuild_tree(files)
        self._update_filter_counts()
        if files:
            self._open_image(files[0])

    def _rebuild_tree(self, files: list):
        self.image_list       = list(files)
        self._tree_iid_map    = {}
        self._path_to_iid     = {}
        tree = self.tree_images
        tree.delete(*tree.get_children())

        use_hier = (self.v_subfolder.get()
                    and len(self._all_images) > 1
                    and self._all_images)
        base_dir = (os.path.commonpath(self._all_images)
                    if use_hier and self._all_images else None)

        if base_dir and files:
            folder_iids: dict = {}
            for f in files:
                state = _review_state(f)
                tag   = state or "unreviewed"
                icon  = _REVIEW_ICON[state]
                try:
                    parts = os.path.relpath(f, base_dir).replace("\\", "/").split("/")
                except ValueError:
                    parts = [os.path.basename(f)]
                parent_iid = ""
                for depth, part in enumerate(parts[:-1]):
                    fkey = "/".join(parts[:depth + 1])
                    if fkey not in folder_iids:
                        iid = tree.insert(parent_iid, END,
                                          text=f"📁 {part}",
                                          open=True, tags=("folder",))
                        folder_iids[fkey] = iid
                    parent_iid = folder_iids[fkey]
                iid = tree.insert(parent_iid, END,
                                  text=f"{icon} {parts[-1]}", tags=(tag,))
                self._tree_iid_map[iid] = f
                self._path_to_iid[f]    = iid
        else:
            for f in files:
                state = _review_state(f)
                tag   = state or "unreviewed"
                icon  = _REVIEW_ICON[state]
                iid = tree.insert("", END,
                                  text=f"{icon} {os.path.basename(f)}", tags=(tag,))
                self._tree_iid_map[iid] = f
                self._path_to_iid[f]    = iid

        iid = self._path_to_iid.get(self.current_image_path)
        if iid:
            tree.selection_set(iid)
            tree.see(iid)

    def _schedule_search(self):
        if self._search_after:
            self.after_cancel(self._search_after)
        self._search_after = self.after(
            300, lambda: self._apply_filter(self._active_filter))

    def _apply_filter(self, filter_type: str):
        self._active_filter = filter_type
        for code, btn in self._filter_btns.items():
            btn.config(
                relief="sunken" if code == filter_type else "flat",
                bg="#252540" if code == filter_type else CARD)
        base = self._base_folder
        if filter_type == "correct":
            filtered = self._scan_images(os.path.join(base, "correct")) if base else []
        elif filter_type == "incorrect":
            filtered = self._scan_images(os.path.join(base, "incorrect")) if base else []
        elif filter_type == "unreviewed":
            filtered = list(self._all_images)
        else:
            c = self._scan_images(os.path.join(base, "correct"))   if base else []
            i = self._scan_images(os.path.join(base, "incorrect"))  if base else []
            filtered = list(self._all_images) + c + i

        search = self._v_search.get().strip().lower()
        if search:
            filtered = [f for f in filtered
                        if search in os.path.basename(f).lower()]
        self._rebuild_tree(filtered)

    def _update_filter_counts(self):
        base  = self._base_folder
        n_un  = len(self._all_images)
        n_ok  = len(self._scan_images(os.path.join(base, "correct")))   if base else 0
        n_bad = len(self._scan_images(os.path.join(base, "incorrect"))) if base else 0
        n_all = n_un + n_ok + n_bad
        for code, lbl in [("all",        f"All({n_all})"),
                           ("correct",    f"✓({n_ok})"),
                           ("incorrect",  f"✗({n_bad})"),
                           ("unreviewed", f"?({n_un})")]:
            self._filter_btns[code].config(text=lbl)

    def _open_image(self, path: str):
        self.current_image_path = path
        iid = self._path_to_iid.get(path)
        if iid:
            self.tree_images.selection_set(iid)
            self.tree_images.see(iid)
        n = len(self.image_list)
        try:
            pos = self.image_list.index(path) + 1
        except ValueError:
            pos = 0
        self.v_status.set(f"{pos}/{n}  {os.path.basename(path)}")

        self._clear_box_silent()
        self._clear_bars()
        self._clear_crop_preview()
        self._last_pairs = []
        self.lbl_result.config(text="")
        self.lbl_mark_state.config(text="")

        if not _PIL_OK:
            _append_log(self._log, "⚠ Chưa cài Pillow")
            return
        try:
            img = Image.open(path).convert("RGB")
            self._pil_full = img
            self._render_display()
            if self._model:
                self._classify_current()
        except Exception as ex:
            _append_log(self._log, f"[LỖI] Tải ảnh: {ex}")

    def _on_image_select(self, _=None):
        sel = self.tree_images.selection()
        if not sel:
            return
        path = self._tree_iid_map.get(sel[0])
        if path and path != self.current_image_path:
            self._open_image(path)

    # ══════════════════════════════════════════════════════════ NAVIGATION ══

    def _prev_image(self): self._nav_image(-1)
    def _next_image(self): self._nav_image(+1)

    def _nav_image(self, step: int):
        if not self.image_list:
            return
        idx = (self.image_list.index(self.current_image_path)
               if self.current_image_path in self.image_list else 0)
        self._open_image(self.image_list[(idx + step) % len(self.image_list)])

    # ═══════════════════════════════════════════════════════ CANVAS RENDER ══

    def _render_display(self):
        if not self._pil_full or not _PIL_OK:
            return
        self.root.update_idletasks()
        cw = max(self.canvas.winfo_width(),  100)
        ch = max(self.canvas.winfo_height(), 100)

        if self._zoom_factor == 0.0:
            scale = min(cw / self._pil_full.width, ch / self._pil_full.height)
            self.lbl_zoom.config(text="Fit")
        else:
            scale = self._zoom_factor
            self.lbl_zoom.config(text=f"{int(scale * 100)}%")

        nw = max(1, int(self._pil_full.width  * scale))
        nh = max(1, int(self._pil_full.height * scale))
        self._img_scale = scale
        self._img_off_x = (cw - nw) // 2
        self._img_off_y = (ch - nh) // 2

        resized = self._pil_full.resize((nw, nh), Image.LANCZOS)
        self._tk_img = ImageTk.PhotoImage(resized)

        self.canvas.delete("all")
        self.canvas.create_image(
            self._img_off_x, self._img_off_y,
            anchor=NW, image=self._tk_img, tags="img")

        if self._has_bbox() and not self.v_show_orig.get():
            self._redraw_bbox()
        if self._crop_mode == "4pt" and self._pts4:
            self._draw_4pt_overlay()

    def _zoom_step(self, delta: float):
        if delta == 0.0:
            self._zoom_factor = 0.0
        else:
            if self._zoom_factor == 0.0 and self._pil_full:
                cw = max(self.canvas.winfo_width(), 100)
                ch = max(self.canvas.winfo_height(), 100)
                self._zoom_factor = min(
                    cw / self._pil_full.width,
                    ch / self._pil_full.height)
            self._zoom_factor = max(0.05, min(8.0, self._zoom_factor + delta))
        self._render_display()

    def _on_canvas_scroll(self, event):
        self._zoom_step(0.15 if event.delta > 0 else -0.15)

    def _on_canvas_resize(self, _=None):
        if self._pil_full:
            self._render_display()

    def _on_canvas_dbl(self, _=None):
        from ...core.ui_helpers import _zoom_image_window
        if self._crop_mode == "4pt" and self._persp_pil:
            _zoom_image_window(self.root, self._persp_pil, "Phóng to — Perspective Crop")
            return
        if not self._pil_full:
            return
        fname = (os.path.basename(self.current_image_path)
                 if self.current_image_path else "ảnh")
        _zoom_image_window(self.root, self._pil_full, fname)

    # ════════════════════════════════════════════════════════ BBOX DRAWING ══

    def _c2i(self, cx, cy):
        if self._img_scale == 0:
            return 0.0, 0.0
        ix = (cx - self._img_off_x) / self._img_scale
        iy = (cy - self._img_off_y) / self._img_scale
        if self._pil_full:
            ix = max(0.0, min(float(self._pil_full.width),  ix))
            iy = max(0.0, min(float(self._pil_full.height), iy))
        return ix, iy

    def _i2c(self, ix, iy):
        return (ix * self._img_scale + self._img_off_x,
                iy * self._img_scale + self._img_off_y)

    def _has_bbox(self):
        return (self._bx1 is not None and self._bx2 is not None
                and self._bx2 > self._bx1 and self._by2 > self._by1)

    def _handle_hit(self, cx, cy):
        if not self._has_bbox():
            return None
        c1x, c1y = self._i2c(self._bx1, self._by1)
        c2x, c2y = self._i2c(self._bx2, self._by2)
        mx,  my  = (c1x + c2x) / 2, (c1y + c2y) / 2
        pts = {"nw": (c1x, c1y), "n":  (mx,  c1y), "ne": (c2x, c1y),
               "e":  (c2x, my),  "se": (c2x, c2y), "s":  (mx,  c2y),
               "sw": (c1x, c2y), "w":  (c1x, my)}
        thresh = _HS + 4
        for name, (hx, hy) in pts.items():
            if abs(cx - hx) <= thresh and abs(cy - hy) <= thresh:
                return name
        return None

    def _inside_bbox(self, cx, cy):
        if not self._has_bbox():
            return False
        c1x, c1y = self._i2c(self._bx1, self._by1)
        c2x, c2y = self._i2c(self._bx2, self._by2)
        return c1x < cx < c2x and c1y < cy < c2y

    def _on_motion(self, e):
        if self._crop_mode == "4pt":
            hit = self._pt_hit_test(e.x, e.y) if self._pts4 else None
            self.canvas.config(cursor=_CURSOR_MOVE if hit is not None else "crosshair")
            return
        if not self._has_bbox():
            self.canvas.config(cursor=_CURSOR_DRAW)
            return
        if self._handle_hit(e.x, e.y):
            self.canvas.config(cursor=_CURSOR_RESIZE)
        elif self._inside_bbox(e.x, e.y):
            self.canvas.config(cursor=_CURSOR_MOVE)
        else:
            self.canvas.config(cursor=_CURSOR_DRAW)

    def _on_press(self, e):
        if not self._pil_full:
            return

        if self._crop_mode == "4pt":
            # Click gần điểm hiện có → bắt đầu kéo
            if self._pts4:
                hit = self._pt_hit_test(e.x, e.y)
                if hit is not None:
                    self._drag_pt_idx = hit
                    return
            # Thêm điểm mới (reset nếu đã đủ 4)
            if len(self._pts4) >= 4:
                self._clear_4pt()
            ix, iy = self._c2i(e.x, e.y)
            self._pts4.append((ix, iy))
            self._draw_4pt_overlay()
            if len(self._pts4) == 4:
                self._apply_perspective_crop()
            return

        self._drag_cx, self._drag_cy = e.x, e.y

        h = self._handle_hit(e.x, e.y)
        if h:
            self._mode = f"resize_{h}"
            self._drag_bx1, self._drag_by1 = self._bx1, self._by1
            self._drag_bx2, self._drag_by2 = self._bx2, self._by2
            return

        if self._inside_bbox(e.x, e.y):
            self._mode = "move"
            self._drag_bx1, self._drag_by1 = self._bx1, self._by1
            self._drag_bx2, self._drag_by2 = self._bx2, self._by2
            return

        self._mode = "draw"
        self._bx1 = self._by1 = self._bx2 = self._by2 = None
        self._result_color = ACCENT
        self._draw_start = self._c2i(e.x, e.y)
        self._clear_crop_preview()
        self._render_display()

    def _on_drag(self, e):
        if not self._pil_full:
            return
        if self._crop_mode == "4pt":
            if self._drag_pt_idx is not None:
                ix, iy = self._c2i(e.x, e.y)
                self._pts4[self._drag_pt_idx] = (ix, iy)
                self._draw_4pt_overlay()
            return
        dx_i = (e.x - self._drag_cx) / self._img_scale if self._img_scale else 0
        dy_i = (e.y - self._drag_cy) / self._img_scale if self._img_scale else 0

        if self._mode == "draw" and self._draw_start:
            ix, iy = self._c2i(e.x, e.y)
            sx, sy = self._draw_start
            self._bx1, self._by1 = min(sx, ix), min(sy, iy)
            self._bx2, self._by2 = max(sx, ix), max(sy, iy)
            self._redraw_bbox()

        elif self._mode == "move":
            iw = float(self._pil_full.width)
            ih = float(self._pil_full.height)
            w = self._drag_bx2 - self._drag_bx1
            h = self._drag_by2 - self._drag_by1
            nx1 = max(0.0, min(iw - w, self._drag_bx1 + dx_i))
            ny1 = max(0.0, min(ih - h, self._drag_by1 + dy_i))
            self._bx1, self._by1 = nx1, ny1
            self._bx2, self._by2 = nx1 + w, ny1 + h
            self._redraw_bbox()

        elif self._mode.startswith("resize_"):
            h_name = self._mode[7:]
            iw = float(self._pil_full.width)
            ih = float(self._pil_full.height)
            x1, y1 = self._drag_bx1, self._drag_by1
            x2, y2 = self._drag_bx2, self._drag_by2
            ix, iy  = self._c2i(e.x, e.y)

            if   h_name == "nw": x1, y1 = ix, iy
            elif h_name == "n":  y1 = iy
            elif h_name == "ne": x2, y1 = ix, iy
            elif h_name == "e":  x2 = ix
            elif h_name == "se": x2, y2 = ix, iy
            elif h_name == "s":  y2 = iy
            elif h_name == "sw": x1, y2 = ix, iy
            elif h_name == "w":  x1 = ix

            x1 = max(0.0, min(x1, iw))
            y1 = max(0.0, min(y1, ih))
            x2 = max(0.0, min(x2, iw))
            y2 = max(0.0, min(y2, ih))
            self._bx1 = min(x1, x2)
            self._by1 = min(y1, y2)
            self._bx2 = max(x1, x2)
            self._by2 = max(y1, y2)
            self._redraw_bbox()

    def _on_release(self, e):
        if not self._pil_full:
            return
        if self._crop_mode == "4pt":
            if self._drag_pt_idx is not None:
                ix, iy = self._c2i(e.x, e.y)
                self._pts4[self._drag_pt_idx] = (ix, iy)
                self._drag_pt_idx = None
                self._draw_4pt_overlay()
                if len(self._pts4) == 4:
                    self._apply_perspective_crop()
            return
        self._mode = "draw"
        if not self._has_bbox():
            return
        if (self._bx2 - self._bx1) < 5 or (self._by2 - self._by1) < 5:
            self._clear_box_silent()
            return
        if self._model:
            self._classify_current()

    def _redraw_bbox(self, color=None):
        for tag in ("bbox", "handle"):
            for item in self.canvas.find_withtag(tag):
                self.canvas.delete(item)
        self._rect_id    = None
        self._handle_ids = []

        if not self._has_bbox():
            return

        col = color or self._result_color
        lw  = max(1, self.v_line_width.get())
        cx1, cy1 = self._i2c(self._bx1, self._by1)
        cx2, cy2 = self._i2c(self._bx2, self._by2)
        mx,  my  = (cx1 + cx2) / 2, (cy1 + cy2) / 2

        self._rect_id = self.canvas.create_rectangle(
            cx1, cy1, cx2, cy2, outline=col, width=lw, tags="bbox")

        for hx, hy in [(cx1, cy1), (mx, cy1), (cx2, cy1),
                        (cx2, my),  (cx2, cy2), (mx, cy2),
                        (cx1, cy2), (cx1, my)]:
            hid = self.canvas.create_rectangle(
                hx - _HS, hy - _HS, hx + _HS, hy + _HS,
                fill=col, outline="white", width=1, tags="handle")
            self._handle_ids.append(hid)

    def _clear_box(self, _=None):
        if self._crop_mode == "4pt":
            if self._pts4:
                self._pts4.pop()
                self._draw_4pt_overlay()
                self._persp_pil = None
                self._clear_crop_preview()
            return
        self._clear_box_silent()
        self._clear_crop_preview()
        if self._last_pairs:
            self._update_bars(self._last_pairs)

    def _clear_box_silent(self):
        self._bx1 = self._by1 = self._bx2 = self._by2 = None
        self._draw_start   = None
        self._mode         = "draw"
        self._result_color = ACCENT
        for tag in ("bbox", "handle"):
            for item in self.canvas.find_withtag(tag):
                self.canvas.delete(item)
        self._rect_id    = None
        self._handle_ids = []
        self.canvas.config(cursor=_CURSOR_DRAW)

    # ════════════════════════════════════════════════════════ CLASSIFY ══

    def _classify_current(self, _=None):
        if not self._model:
            _append_log(self._log, "⚠ Chưa tải model")
            return
        if not self._pil_full:
            _append_log(self._log, "⚠ Chưa tải ảnh")
            return

        if self._crop_mode == "4pt" and self._persp_pil:
            pil_input      = self._persp_pil
            self._crop_pil = pil_input
            mode_lbl = f"4-pt perspective  ({pil_input.width}×{pil_input.height})"
        elif self._has_bbox():
            x1, y1 = int(self._bx1), int(self._by1)
            x2, y2 = int(self._bx2), int(self._by2)
            pil_input      = self._pil_full.crop((x1, y1, x2, y2))
            self._crop_pil = pil_input
            self._show_crop_preview(pil_input)
            mode_lbl = f"bbox ({x1},{y1})→({x2},{y2})"
        else:
            pil_input      = self._pil_full
            self._crop_pil = None
            mode_lbl = "toàn ảnh"

        model  = self._model
        names  = self._model_names
        top_n  = self.v_top_n.get()

        def _infer():
            try:
                results = model(pil_input, verbose=False)
                r = results[0]
                probs = r.probs
                if probs is None:
                    self.root.after(0, lambda: _append_log(
                        self._log, "⚠ Model không phải task=classify (probs=None)"))
                    return
                data = probs.data.tolist() if hasattr(probs, "data") else []
                tidx  = sorted(range(len(data)), key=lambda i: data[i], reverse=True)
                pairs = [(names.get(i, str(i)), data[i]) for i in tidx[:top_n]]
                self.root.after(0, lambda: self._show_result(pairs, mode_lbl))
            except Exception as ex:
                msg = str(ex)
                self.root.after(0, lambda: _append_log(
                    self._log, f"[LỖI] Classify: {msg}"))

        threading.Thread(target=_infer, daemon=True).start()

    def _show_result(self, pairs: list, mode_lbl: str = ""):
        if not pairs:
            return
        self._last_pairs = pairs
        top_cls, top_conf = pairs[0]
        color = (SUCCESS if top_conf >= 0.70 else
                 ACCENT  if top_conf >= 0.40 else "#f05050")

        result_txt = f"▶ {top_cls}  ({top_conf:.1%})"
        if mode_lbl:
            result_txt += f"  [{mode_lbl}]"
        self.lbl_result.config(text=result_txt, fg=color)
        self.v_status.set(
            f"{os.path.basename(self.current_image_path or '')}  "
            f"→  {top_cls}  {top_conf:.1%}")

        _append_log(self._log, f"✔ {top_cls}  {top_conf:.1%}  [{mode_lbl}]")
        for i, (cls, conf) in enumerate(pairs[1:], 1):
            _append_log(self._log, f"   Top-{i+1}: {cls:<18} {conf:.1%}")

        self._update_bars(pairs)

        # Đổi màu bbox theo kết quả
        self._result_color = color
        if self._has_bbox():
            self._redraw_bbox(color)

    # ══════════════════════════════════════════════════════ MARK REVIEW ══

    def _mark_review(self, state: str):
        path = self.current_image_path
        if not path:
            return
        icons = {"correct": "✓ Đúng", "incorrect": "✗ Sai", "": "↺ Bỏ"}
        self.lbl_mark_state.config(
            text=icons.get(state, ""),
            fg="#4caf50" if state == "correct" else (ACCENT if state == "incorrect" else DIM))

        if state in ("correct", "incorrect"):
            moved = self._move_to_subfolder(path, state)
            if moved:
                if path in self._all_images:
                    self._all_images.remove(path)
                old_idx = (self.image_list.index(path)
                           if path in self.image_list else 0)
                self.current_image_path = None
                self._apply_filter(self._active_filter)
                self._update_filter_counts()
                if self.image_list:
                    self._open_image(
                        self.image_list[min(old_idx, len(self.image_list) - 1)])
                return

        iid = self._path_to_iid.get(path)
        if iid and self.tree_images.exists(iid):
            icon    = _REVIEW_ICON.get(state, "○")
            old_txt = self.tree_images.item(iid, "text")
            bare    = old_txt[2:] if len(old_txt) > 2 else old_txt
            self.tree_images.item(iid,
                                  text=f"{icon} {bare}",
                                  tags=(state or "unreviewed",))
        self._update_filter_counts()

    def _move_to_subfolder(self, path: str, state: str) -> bool:
        if not os.path.isfile(path):
            return False
        sub    = "correct" if state == "correct" else "incorrect"
        parent = os.path.basename(os.path.dirname(path))
        root   = (os.path.dirname(os.path.dirname(path))
                  if parent in ("correct", "incorrect")
                  else self._base_folder or os.path.dirname(path))
        dest   = os.path.join(root, sub)
        try:
            os.makedirs(dest, exist_ok=True)
            shutil.move(path, os.path.join(dest, os.path.basename(path)))
            self.v_status.set(
                f"{'✓' if state == 'correct' else '✗'}  → {sub}/: {os.path.basename(path)}")
            return True
        except Exception as ex:
            self.v_status.set(f"Lỗi di chuyển: {ex}")
            return False

    # ════════════════════════════════════════════════════════ AUTOPLAY ══

    def _toggle_autoplay(self):
        if self._autoplay_id is not None:
            self.root.after_cancel(self._autoplay_id)
            self._autoplay_id = None
            self.btn_autoplay.config(text="▶ Auto", bg="#2e5fa3")
        else:
            self.btn_autoplay.config(text="■ Stop", bg=ACCENT)
            self._schedule_autoplay()

    def _schedule_autoplay(self):
        try:
            interval = float(self.v_interval.get())
        except ValueError:
            interval = 2.0
        self._autoplay_id = self.root.after(
            max(200, int(interval * 1000)), self._autoplay_step)

    def _autoplay_step(self):
        if self._autoplay_id is None:
            return
        self._nav_image(+1)
        self._schedule_autoplay()

    # ════════════════════════════════════════════════════ BARS / PREVIEW ══

    def _clear_bars(self):
        for lbl_n, lbl_p, inner, _ in self._bar_rows:
            lbl_n.config(text="—", fg=DIM)
            lbl_p.config(text="")
            inner.place(width=0)

    def _update_bars(self, pairs: list):
        self.update_idletasks()
        for i, (lbl_n, lbl_p, inner, outer) in enumerate(self._bar_rows):
            if i < len(pairs):
                cls, conf = pairs[i]
                lbl_n.config(text=cls[:13], fg=TEXT)
                lbl_p.config(text=f"{conf:.1%}", fg=TEXT)
                ow = max(outer.winfo_width(), 80)
                inner.place(x=0, y=0, relheight=1.0, width=int(conf * ow))
            else:
                lbl_n.config(text="—", fg=DIM)
                lbl_p.config(text="")
                inner.place(width=0)

    def _show_crop_preview(self, crop: "Image.Image"):
        if not _PIL_OK:
            return
        preview = crop.copy()
        preview.thumbnail((230, 120), Image.LANCZOS)
        tk_img = ImageTk.PhotoImage(preview)
        self.prev_canvas.delete("all")
        pw = self.prev_canvas.winfo_width()  or 240
        ph = self.prev_canvas.winfo_height() or 130
        self.prev_canvas.create_image(pw // 2, ph // 2, anchor=CENTER, image=tk_img)
        self._prev_tk = tk_img

    def _clear_crop_preview(self):
        self.prev_canvas.delete("all")
        self.prev_canvas.create_text(
            120, 65, text="Vùng bbox hiện ở đây",
            fill=DIM, font=("Segoe UI", 9), tags="prev_hint")
        self._prev_tk  = None
        self._crop_pil = None

    def _zoom_crop(self, _=None):
        if not self._crop_pil:
            return
        from ...core.ui_helpers import _zoom_image_window
        _zoom_image_window(self.root, self._crop_pil, "Phóng to vùng bbox")

    # ═══════════════════════════════════════════════════════ CONF LABEL ══

    def _on_conf_change(self, _=None):
        self.lbl_conf_val.config(text=f"{self.v_conf.get():.2f}")

    def _sync_conf_label(self):
        self.lbl_conf_val.config(text=f"{self.v_conf.get():.2f}")

    # ════════════════════════════════════════════════════════ SAVE / EXPORT ══

    def _save_result(self):
        if not self._pil_full:
            messagebox.showwarning("Chưa có ảnh",
                                   "Tải ảnh và phân loại trước.", parent=self.root)
            return
        save_dir = filedialog.askdirectory(
            title="Chọn thư mục lưu kết quả", parent=self.root)
        if not save_dir:
            return
        try:
            base = os.path.splitext(
                os.path.basename(self.current_image_path or "result"))[0]

            if self._crop_mode == "4pt" and self._persp_pil:
                pil_out = self._persp_pil.copy()
                if self._last_pairs:
                    draw = ImageDraw.Draw(pil_out)
                    top_cls, top_conf = self._last_pairs[0]
                    draw.text((6, 6), f"{top_cls}  {top_conf:.1%}",
                              fill=(240, 89, 34))
                out = os.path.join(save_dir, f"{base}_persp.jpg")
            else:
                pil_out = self._pil_full.copy()
                draw    = ImageDraw.Draw(pil_out)
                if self._last_pairs:
                    top_cls, top_conf = self._last_pairs[0]
                    draw.text((6, 6), f"{top_cls}  {top_conf:.1%}",
                              fill=(240, 89, 34))
                if self._has_bbox():
                    draw.rectangle(
                        [int(self._bx1), int(self._by1),
                         int(self._bx2), int(self._by2)],
                        outline=(240, 89, 34), width=2)
                out = os.path.join(save_dir, f"{base}_cls.jpg")

            pil_out.save(out, quality=92)
            messagebox.showinfo("Đã lưu", f"Ảnh: {out}", parent=self.root)
        except Exception as ex:
            messagebox.showerror("Lỗi", str(ex), parent=self.root)

    def _batch_export(self):
        if not self._model:
            messagebox.showwarning("Chưa có model",
                                   "Vui lòng chọn model trước.", parent=self.root)
            return
        if not self.image_list:
            messagebox.showwarning("Chưa có ảnh",
                                   "Vui lòng chọn thư mục ảnh trước.", parent=self.root)
            return
        out_dir = filedialog.askdirectory(
            title="Chọn thư mục lưu kết quả batch", parent=self.root)
        if not out_dir:
            return

        popup = Toplevel(self.root)
        popup.title("Batch Export — Cls Tester")
        popup.configure(bg=BG)
        popup.geometry("580x380")
        popup.resizable(True, True)

        Label(popup, text=f"Đang phân loại {len(self.image_list)} ảnh …",
              font=F_BOLD, bg=BG, fg=TEXT).pack(pady=(12, 4))
        pb = ttk.Progressbar(popup, mode="determinate",
                              maximum=len(self.image_list))
        pb.pack(fill=X, padx=16, pady=(0, 4))
        v_prog = StringVar(value="0 / 0")
        Label(popup, textvariable=v_prog, font=F_MONO, bg=BG, fg=DIM).pack()
        log_fr2, log2 = _make_logbox(popup)
        log_fr2.pack(fill=BOTH, expand=True, padx=8, pady=8)

        model = self._model
        names = self._model_names
        files = list(self.image_list)
        top_n = self.v_top_n.get()

        def _run():
            ok = 0
            csv = ["file,top1_class,top1_conf,top2_class,top2_conf"]
            for i, img_path in enumerate(files):
                self.root.after(0, lambda v=i: pb.config(value=v))
                self.root.after(0, lambda v=i + 1, t=len(files):
                                v_prog.set(f"{v} / {t}"))
                try:
                    if _PIL_OK:
                        pil = Image.open(img_path).convert("RGB")
                        res = model(pil, verbose=False)
                    else:
                        res = model(img_path, verbose=False)
                    probs = res[0].probs
                    data  = probs.data.tolist() if (probs and hasattr(probs, "data")) else []
                    tidx  = sorted(range(len(data)), key=lambda i: data[i], reverse=True)
                    pairs = [(names.get(i, str(i)), data[i]) for i in tidx[:top_n]]
                    t1    = pairs[0] if pairs         else ("?", 0.0)
                    t2    = pairs[1] if len(pairs) > 1 else ("?", 0.0)
                    fname = os.path.basename(img_path)
                    csv.append(f"{fname},{t1[0]},{t1[1]:.4f},{t2[0]},{t2[1]:.4f}")
                    msg = f"  {fname}  →  {t1[0]}  ({t1[1]:.1%})"
                    self.root.after(0, lambda m=msg: _append_log(log2, f"✔ {m}"))
                    ok += 1
                except Exception as ex:
                    fname = os.path.basename(img_path)
                    self.root.after(0, lambda m=str(ex), n=fname:
                                    _append_log(log2, f"[LỖI] {n}: {m}"))

            try:
                with open(os.path.join(out_dir, "results.csv"),
                          "w", encoding="utf-8") as f:
                    f.write("\n".join(csv))
            except Exception:
                pass
            self.root.after(0, lambda: pb.config(value=len(files)))
            self.root.after(0, lambda: _append_log(
                log2, f"✔ Xong: {ok}/{len(files)} ảnh  →  {out_dir}"))

        threading.Thread(target=_run, daemon=True).start()

    # ══════════════════════════════════════════ CROP MODE / 4-POINT PERSP ══

    def _on_line_width_change(self, _=None):
        """Redraw hiện tại khi người dùng đổi độ đậm nét."""
        if self._crop_mode == "4pt" and self._pts4:
            self._draw_4pt_overlay()
        elif self._has_bbox():
            self._redraw_bbox()

    def _set_crop_mode(self, mode: str):
        self._crop_mode = mode
        rect_on = mode == "rect"
        self._btn_mode_rect.config(
            relief="sunken" if rect_on else "flat",
            bg="#252540" if rect_on else CARD)
        self._btn_mode_4pt.config(
            relief="sunken" if not rect_on else "flat",
            bg="#252540" if not rect_on else CARD)
        if rect_on:
            self.lbl_crop_hint.config(
                text="✏ Kéo để vẽ bbox  |  Ctrl+scroll: zoom  |  Chuột phải: xóa")
            self.canvas.config(cursor=_CURSOR_DRAW)
            self._clear_4pt()
        else:
            self.lbl_crop_hint.config(
                text="◈ Click 4 góc theo thứ tự  |  Chuột phải: xóa điểm cuối")
            self.canvas.config(cursor="crosshair")
            self._clear_box_silent()
        self._persp_pil = None
        self._clear_crop_preview()

    def _draw_4pt_overlay(self):
        self.canvas.delete("4pt")
        n     = len(self._pts4)
        pts_c = [self._i2c(ix, iy) for ix, iy in self._pts4]
        lw    = max(1, self.v_line_width.get())
        _DOT_COLORS = [ACCENT, "#4fc3f7", "#81c784", "#fff176"]

        # Lines connecting points
        if n >= 2:
            flat = [c for pt in pts_c for c in pt]
            if n >= 3:
                self.canvas.create_polygon(
                    flat, outline=ACCENT, fill="", width=lw, dash=(5, 3), tags="4pt")
            else:
                self.canvas.create_line(flat, fill=ACCENT, width=lw, dash=(5, 3), tags="4pt")

        # Numbered dots — scale with line width but keep readable
        r = max(6, 5 + lw)
        for i, (cx, cy) in enumerate(pts_c):
            self.canvas.create_oval(
                cx - r, cy - r, cx + r, cy + r,
                fill=_DOT_COLORS[i % 4], outline="white", width=1, tags="4pt")
            self.canvas.create_text(
                cx, cy, text=str(i + 1),
                fill="white", font=("Segoe UI", 7, "bold"), tags="4pt")

        if n < 4:
            self.v_status.set(
                f"4 điểm: {n}/4  — click để thêm điểm  |  chuột phải để xóa điểm cuối")

    def _pt_hit_test(self, cx, cy) -> "int | None":
        """Trả về index điểm trong _pts4 nếu (cx,cy) chạm vào, ngược lại None."""
        r = max(6, 5 + self.v_line_width.get()) + 5   # dot radius + margin
        for i, (ix, iy) in enumerate(self._pts4):
            pcx, pcy = self._i2c(ix, iy)
            if abs(cx - pcx) <= r and abs(cy - pcy) <= r:
                return i
        return None

    def _clear_4pt(self):
        self.canvas.delete("4pt")
        self._pts4 = []
        self._persp_pil = None
        self._drag_pt_idx = None

    @staticmethod
    def _order_pts4(pts):
        """Sắp xếp 4 điểm: TL → TR → BR → BL."""
        s = sorted(pts, key=lambda p: p[1])
        top = sorted(s[:2], key=lambda p: p[0])
        bot = sorted(s[2:], key=lambda p: p[0])
        return [top[0], top[1], bot[1], bot[0]]

    def _apply_perspective_crop(self):
        if not self._pil_full or len(self._pts4) != 4:
            return
        ordered  = self._order_pts4(self._pts4)
        pil_full = self._pil_full

        def _compute():
            try:
                warped = self._warp_perspective(pil_full, ordered)
                self.root.after(0, lambda w=warped: self._on_persp_done(w))
            except Exception as ex:
                self.root.after(0, lambda e=str(ex): _append_log(
                    self._log, f"[LỖI] Perspective: {e}"))

        threading.Thread(target=_compute, daemon=True).start()

    def _on_persp_done(self, warped):
        self._persp_pil = warped
        self._show_crop_preview(warped)
        self.v_status.set(
            f"✔ Perspective crop: {warped.width}×{warped.height}px"
            "  — F5 để phân loại  |  double-click để phóng to")
        if self._model:
            self._classify_current()

    @staticmethod
    def _warp_perspective(pil_img, pts4):
        """Warp quadrilateral (TL,TR,BR,BL) → rectangle. Returns PIL.Image."""
        import math
        def _dist(a, b): return math.hypot(b[0] - a[0], b[1] - a[1])
        tl, tr, br, bl = pts4
        W = max(1, int(max(_dist(tl, tr), _dist(bl, br))))
        H = max(1, int(max(_dist(tl, bl), _dist(tr, br))))

        try:
            import cv2
            import numpy as np
            src = np.float32([[p[0], p[1]] for p in pts4])
            dst = np.float32([[0, 0], [W, 0], [W, H], [0, H]])
            M   = cv2.getPerspectiveTransform(src, dst)
            arr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
            out = cv2.warpPerspective(arr, M, (W, H))
            return Image.fromarray(cv2.cvtColor(out, cv2.COLOR_BGR2RGB))
        except ImportError:
            pass

        # PIL fallback (numpy only)
        try:
            import numpy as np
            src_pts = [(p[0], p[1]) for p in pts4]
            dst_pts = [(0, 0), (W, 0), (W, H), (0, H)]
            A, b = [], []
            for (xs, ys), (xd, yd) in zip(src_pts, dst_pts):
                A.append([xd, yd, 1, 0, 0, 0, -xs * xd, -xs * yd])
                A.append([0,  0,  0, xd, yd, 1, -ys * xd, -ys * yd])
                b.extend([xs, ys])
            coeffs = tuple(np.linalg.lstsq(np.array(A), np.array(b), rcond=None)[0])
            return pil_img.transform((W, H), Image.PERSPECTIVE, coeffs, Image.BICUBIC)
        except Exception:
            pass

        # Minimal fallback: bounding-box crop
        x1 = int(min(p[0] for p in pts4))
        y1 = int(min(p[1] for p in pts4))
        x2 = int(max(p[0] for p in pts4))
        y2 = int(max(p[1] for p in pts4))
        return pil_img.crop((x1, y1, x2, y2))

    # ═════════════════════════════════════════════════════════ DRAG-DROP ══

    def _on_drop(self, event):
        paths = self.root.tk.splitlist(event.data)
        if not paths:
            return
        if len(paths) == 1 and os.path.isdir(paths[0]):
            p = paths[0]
            self.v_check_path.set(p)
            _push_history("h.cls_test.path", p)
            self.combo_path["values"] = _get_history("h.cls_test.path")
            self._load_folder(p)
            return
        imgs = [p for p in paths
                if os.path.isfile(p)
                and os.path.splitext(p)[1].lower() in _EXTS]
        if imgs:
            self._load_image_list(sorted(imgs))

    # ════════════════════════════════════════════════════════ KEYBINDINGS ══

    def _is_active(self):
        try:
            w = self
            while w:
                p = getattr(w, "master", None)
                if p is None:
                    break
                if isinstance(p, ttk.Notebook):
                    return p.select() == str(w)
                w = p
        except Exception:
            pass
        return False

    def _bind_keys(self):
        def _guard(fn):
            def _inner(*_):
                if self._is_active():
                    fn(); return "break"
            return _inner

        self.root.bind("<Return>", _guard(lambda: self._mark_review("correct")), "+")
        self.root.bind("<Delete>", _guard(lambda: self._mark_review("incorrect")), "+")
        self.root.bind("<space>",  _guard(self._toggle_autoplay), "+")

    # ── Aliases for app.py global routing ────────────────────────────────
    def select_image(self):    self._select_image()
    def _browse(self):         self._select_image()
    def _run_detect(self):
        if self.current_image_path and self._model:
            self._classify_current()
    def _start(self):          self._classify_current()
    def _on_return(self):
        if self._is_active(): self._mark_review("correct")
    def _on_delete(self):
        if self._is_active(): self._mark_review("incorrect")
    def _toggle_play(self):    self._toggle_autoplay()
    def _stop_action(self):
        if self._autoplay_id:  self._toggle_autoplay()
