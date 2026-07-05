# tab_segment.py — YOLO Segmentation Annotation (N-point polygon + SAM auto)
from __future__ import annotations
import threading
from pathlib import Path
from tkinter import *
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk, ImageDraw

from ...core.constants import (BG, CARD, ACCENT, ACCENT2, TEXT, DIM,
                                F_MAIN, F_BOLD, IMAGE_EXTENSIONS, CLASS_NAMES)
from ...core.settings import (_bind_cfg, _cfg_save, _cfg_dir, _bind_history,
                              _push_history, _get_history)
from ...core.ui_helpers import _folder_row
from ...shared.canvas_zoom import CanvasZoomMixin
from ...shared.sam_utils import run_sam_points, run_sam_box, simplify as _simplify
from ...shared.cv_segment import (compute_edge_mask, flood_region_mask, mask_to_polygon,
                                   empty_mask_like, run_grabcut_box, clean_polygon, polygon_to_mask)
from ...shared.label_io import load_progress, save_progress
from ...shared.sam3_onnx_utils import load_sam3_onnx, run_sam3_text

_COLORS = ["#F05922", "#4A9FE0", "#4CAF50", "#E040FB",
           "#FFEB3B", "#00BCD4", "#FF5252", "#69F0AE"]


class SegmentTab(Frame, CanvasZoomMixin):

    def __init__(self, parent, root):
        super().__init__(parent, bg=BG)
        self.root = root
        self._zoom_init()

        self._img_dir     = StringVar()
        self._lbl_dir_var = StringVar()   # thư mục label riêng (tùy chọn) — để trống thì dùng cạnh ảnh
        self._recursive_var = BooleanVar(value=False)   # quét cả subfolder — giống BBox Editor
        self._img_root: Path | None = None
        self._filter_name_var  = StringVar()
        self._filter_unlabeled = BooleanVar(value=False)
        self._filter_progress_var = StringVar(value="Tất cả")
        self._filtered_idx: list[int] = []   # index vào _img_files đang hiện trong _img_lb (sau filter)
        self._filter_after_id = None
        self._progress_file = None
        self._progress_set: set = set()   # tên file ảnh đã đánh dấu "đã xử lý" (Enter)
        self._undo_stack: list = []   # snapshot _segments trước mỗi thao tác phá hủy (Ctrl+Z)
        self._img_files: list[Path] = []
        self._img_idx     = 0
        self._pil_img: Image.Image | None = None
        self._tk_img = None; self._render_base = None
        self._segments: list       = []
        self._n_from_bbox          = 0   # số segment vừa auto-convert từ bbox khi load nhãn
        self._bbox_derived: set[int] = set()   # index trong _segments còn là bbox thô (chưa auto-tách)
        self._auto_refine_queue: list[int] = []
        self._drawing: list[tuple] = []
        self._cursor: tuple | None = None
        self._sel: int             = -1
        self._drag: tuple | None   = None
        self._class_var    = StringVar(value="0")
        self._mode_var     = StringVar(value="draw")
        self._show_seg_var = BooleanVar(value=True)   # ẩn/hiện toàn bộ overlay segment
        self._status_var   = StringVar(value="Chọn thư mục ảnh để bắt đầu")
        self._simplify_var = DoubleVar(value=2.0)
        self._sam_model    = None
        self._sam_running  = False
        self._box_start: tuple | None = None
        self._box_end:   tuple | None = None
        self._sam_pts: list           = []   # [(ix,iy,label)] iterative prompts
        self._preview_poly: list | None = None  # polygon preview chưa confirm (SAM hoặc CV)
        self._pending_click: tuple | None = None   # click (canvas coords) chưa quyết định vẽ điểm hay kéo SAM Box
        self._draw_as_sambox = False   # đang kéo khung SAM Box tự nhận diện từ mode "Vẽ"
        self._cv_blur_var    = IntVar(value=5)
        self._cv_low_var     = IntVar(value=50)
        self._cv_high_var    = IntVar(value=150)
        self._cv_minarea_var = IntVar(value=80)
        self._cv_edges       = None   # edge mask cache của phiên kéo hiện tại
        self._cv_mask        = None   # mask tích lũy (union các vùng đã "sơn" khi kéo)
        self._cv_dragging    = False
        self._cv_last_pt: tuple | None = None
        self._cv_seed_si: int | None = None   # segment đang được MỞ RỘNG THÊM bằng CV Edge (thay vì tạo mới)
        self._sam3_model    = None
        self._sam3_running  = False
        self._sam3_dir_var  = StringVar()
        self._sam3_conf_var = DoubleVar(value=0.5)
        self._text_prompt_var = StringVar()

        _bind_cfg("seg.img_dir", self._img_dir)
        _bind_cfg("seg.lbl_dir", self._lbl_dir_var)
        _bind_cfg("seg.sam3_model_dir", self._sam3_dir_var)
        _bind_cfg("seg.sam3_conf", self._sam3_conf_var)
        self._lbl_dir_var.trace_add("write", self._on_lbl_dir_change)
        self._build()
        self._bind_shortcuts()

        d = self._img_dir.get()
        if d and Path(d).is_dir():
            self._load_dir(d)

    def _build(self):
        self._build_toolbar()
        self._build_lbl_dir_row()
        self._build_sam_bar()
        self._build_cv_bar()
        self._build_sam3_bar()
        # PanedWindow thay vì Frame cố định — kéo sash để đổi độ rộng panel trái/phải
        body = PanedWindow(self, orient=HORIZONTAL, bg="#111120",
                           sashwidth=5, sashrelief="flat", sashpad=1)
        body.pack(fill=BOTH, expand=True)
        self._build_left(body)
        self._build_canvas(body)
        self._build_right(body)
        Label(self, textvariable=self._status_var, bg=CARD, fg=DIM,
              font=F_MAIN, anchor="w").pack(fill=X, padx=4, pady=(0, 2))

    def _build_toolbar(self):
        tb = Frame(self, bg=CARD, pady=4)
        tb.pack(fill=X)

        Button(tb, text="📂 Mở thư mục", bg=ACCENT2, fg="white",
               relief=FLAT, padx=8, font=F_MAIN,
               command=self._browse_dir).pack(side=LEFT, padx=4)
        Label(tb, textvariable=self._img_dir, bg=CARD, fg=DIM,
              font=F_MAIN).pack(side=LEFT, padx=4)
        Checkbutton(tb, text="Đệ quy subfolder", variable=self._recursive_var,
                    bg=CARD, fg=TEXT, selectcolor="#16162a", activebackground=CARD,
                    font=F_MAIN, command=lambda: self._load_dir(self._img_dir.get())
                    ).pack(side=LEFT, padx=(0, 8))

        Label(tb, text="Class:", bg=CARD, fg=TEXT,
              font=F_MAIN).pack(side=LEFT, padx=(8, 2))
        vals = [f"{k}: {v}" for k, v in CLASS_NAMES.items()]
        self._cls_cb = ttk.Combobox(tb, textvariable=self._class_var,
                                    values=vals, width=14,
                                    state="readonly", font=F_MAIN)
        self._cls_cb.pack(side=LEFT, padx=2)
        if vals:
            self._cls_cb.set(vals[0])

        for txt, val in [("✏ Vẽ (tự nhận Sửa/SAM Box)","draw"),("↔ Sửa","edit"),("🪄 SAM","sam"),("⬜ SAM Box","sam_box"),
                         ("🟩 CV Box","cv_box"),("🌀 CV Edge","cv")]:
            Radiobutton(tb, text=txt, variable=self._mode_var, value=val,
                        bg=CARD, fg=TEXT, selectcolor=ACCENT2,
                        activebackground=CARD, font=F_MAIN).pack(side=LEFT, padx=4)

        Button(tb, text="◀", bg=CARD, fg=TEXT, relief=FLAT,
               font=F_MAIN, command=self._prev_img).pack(side=LEFT, padx=(12, 1))
        self._nav_lbl = Label(tb, text="0 / 0", bg=CARD, fg=TEXT,
                              font=F_MAIN, width=8)
        self._nav_lbl.pack(side=LEFT)
        Button(tb, text="▶", bg=CARD, fg=TEXT, relief=FLAT,
               font=F_MAIN, command=self._next_img).pack(side=LEFT, padx=(1, 8))

        Button(tb, text="💾 Lưu  Ctrl+S", bg=ACCENT, fg="white",
               relief=FLAT, padx=8, font=F_MAIN,
               command=self._save).pack(side=RIGHT, padx=8)
        Checkbutton(tb, text="👁 Hiện segment  H", variable=self._show_seg_var,
                    bg=CARD, fg=TEXT, selectcolor=ACCENT2, activebackground=CARD,
                    font=F_MAIN, command=self._render).pack(side=RIGHT, padx=(0, 8))

    def _build_lbl_dir_row(self):
        """Thư mục label riêng (tùy chọn) — cho dataset dạng images/ + labels/ tách folder
        (như BBox Editor). Để trống thì đọc/ghi .txt ngay cạnh ảnh như mặc định."""
        row = Frame(self, bg=CARD, pady=2)
        row.pack(fill=X)
        grid = Frame(row, bg=CARD)
        grid.pack(fill=X, padx=4)
        grid.columnconfigure(1, weight=1)
        _folder_row(grid, "Thư mục label (tùy chọn):", self._lbl_dir_var, 0,
                    bg=CARD, history_key="h.seg.lbl_dir")

    def _build_sam_bar(self):
        sb = Frame(self, bg="#1a1a2e", pady=3)
        sb.pack(fill=X)
        row1 = Frame(sb, bg="#1a1a2e")
        row1.pack(fill=X)
        Label(row1, text="🪄 SAM:", bg="#1a1a2e", fg=ACCENT, font=F_BOLD).pack(side=LEFT, padx=(8, 4))
        Button(row1, text="📥 mobile_sam  ~40MB", bg=CARD, fg=TEXT, relief=FLAT,
               font=F_MAIN, padx=6,
               command=lambda: self._load_sam_name("mobile_sam.pt")).pack(side=LEFT, padx=2)
        Button(row1, text="📥 SAM2.1 Base  ~80MB  (khuyên dùng)", bg=ACCENT2, fg="white", relief=FLAT,
               font=F_MAIN, padx=6,
               command=lambda: self._load_sam_name("sam2.1_b.pt")).pack(side=LEFT, padx=2)
        Button(row1, text="📥 sam_b  ~375MB", bg=CARD, fg=TEXT, relief=FLAT,
               font=F_MAIN, padx=6,
               command=lambda: self._load_sam_name("sam_b.pt")).pack(side=LEFT, padx=2)
        Button(row1, text="📂 File .pt có sẵn", bg=CARD, fg=TEXT, relief=FLAT,
               font=F_MAIN, padx=6,
               command=self._load_sam).pack(side=LEFT, padx=2)
        Label(row1, text="Simplify:", bg="#1a1a2e", fg=DIM, font=F_MAIN).pack(side=RIGHT, padx=(0, 2))
        # Spinbox thay Scale — cho phép gõ số trực tiếp (VD 0.1, 0.15) ngoài việc
        # bấm mũi tên tăng/giảm 0.1; Scale cũ chỉ kéo được số nguyên 0-10.
        simplify_spin = Spinbox(row1, textvariable=self._simplify_var,
                                from_=0, to=10, increment=0.1, format="%.2f",
                                width=5, bg="#16162a", fg=TEXT, insertbackground=TEXT,
                                buttonbackground=ACCENT2, relief="flat", font=F_MAIN)
        simplify_spin.pack(side=RIGHT, padx=(0, 8))
        # Dòng 2: text trạng thái riêng — full width, không còn tràn/đè lên slider Simplify
        row2 = Frame(sb, bg="#1a1a2e")
        row2.pack(fill=X)
        self._sam_lbl = Label(row2, text="Chưa load  —  chọn model rồi click 🪄 SAM vào object",
                              bg="#1a1a2e", fg=DIM, font=F_MAIN, anchor="w")
        self._sam_lbl.pack(fill=X, padx=8)

    def _build_cv_bar(self):
        cb = Frame(self, bg="#1a2e1a", pady=3)
        cb.pack(fill=X)
        row1 = Frame(cb, bg="#1a2e1a")
        row1.pack(fill=X)
        Label(row1, text="🟩 CV Box: kéo khung → TỰ ĐỘNG  |  🌀 CV Edge (nâng cao):",
              bg="#1a2e1a", fg=ACCENT, font=F_BOLD).pack(side=LEFT, padx=(8, 4))
        for lbl, var, lo, hi in [("Blur", self._cv_blur_var, 1, 21),
                                  ("Canny thấp", self._cv_low_var, 0, 255),
                                  ("Canny cao", self._cv_high_var, 0, 255),
                                  ("Min area", self._cv_minarea_var, 10, 2000)]:
            Label(row1, text=f"{lbl}:", bg="#1a2e1a", fg=DIM,
                  font=F_MAIN).pack(side=LEFT, padx=(6, 2))
            Scale(row1, variable=var, from_=lo, to=hi, orient=HORIZONTAL, length=90,
                  bg="#1a2e1a", fg=TEXT, troughcolor=CARD, highlightthickness=0,
                  showvalue=True, relief=FLAT).pack(side=LEFT)
        # Dòng 2: hướng dẫn riêng — full width, không còn bị cắt/đè ở mép phải
        row2 = Frame(cb, bg="#1a2e1a")
        row2.pack(fill=X)
        self._cv_lbl = Label(row2,
                             text="Không chắc chỉnh gì? Dùng 🟩 CV Box là đủ. CV Edge: kéo=cộng, Shift+kéo=trừ — "
                                  "nếu đang CHỌN 1 segment thì CV Edge sẽ MỞ RỘNG THÊM segment đó (vá phần thiếu)",
                             bg="#1a2e1a", fg=DIM, font=F_MAIN, anchor="w")
        self._cv_lbl.pack(fill=X, padx=8)

    def _build_sam3_bar(self):
        """Text-prompt segmentation bằng SAM 3 (ONNX — vietanhdev/segment-anything-3-onnx-models,
        Apache 2.0, không cần quyền HuggingFace gated). Open-vocabulary: nhập mô tả
        tiếng Anh, model tự tìm & phân đoạn TẤT CẢ instance khớp mô tả đó trong ảnh."""
        sb = Frame(self, bg="#2e1a2e", pady=3)
        sb.pack(fill=X)
        row1 = Frame(sb, bg="#2e1a2e")
        row1.pack(fill=X)
        Label(row1, text="🔤 Text Prompt (SAM 3):", bg="#2e1a2e", fg=ACCENT,
              font=F_BOLD).pack(side=LEFT, padx=(8, 4))
        self._sam3_dir_cb = ttk.Combobox(row1, textvariable=self._sam3_dir_var,
                                         style="Dark.TCombobox", font=F_MAIN, width=20)
        self._sam3_dir_cb.pack(side=LEFT, padx=(0, 2))
        _bind_history("h.seg.sam3_model_dir", self._sam3_dir_cb)
        Button(row1, text="📂", bg=CARD, fg=TEXT, relief=FLAT, font=F_MAIN, padx=4,
               command=self._browse_sam3_dir).pack(side=LEFT, padx=(0, 2))
        Button(row1, text="📥 Load SAM 3", bg=ACCENT2, fg="white", relief=FLAT,
               font=F_MAIN, padx=6, command=self._load_sam3_model).pack(side=LEFT, padx=2)
        self._prompt_cb = ttk.Combobox(row1, textvariable=self._text_prompt_var,
                                       style="Dark.TCombobox", font=F_MAIN, width=24)
        self._prompt_cb.pack(side=LEFT, padx=(6, 2), fill=X, expand=True)
        _bind_history("h.seg.sam3_prompt", self._prompt_cb)
        Label(row1, text="Ngưỡng:", bg="#2e1a2e", fg=DIM, font=F_MAIN).pack(side=LEFT, padx=(4, 2))
        Spinbox(row1, textvariable=self._sam3_conf_var,
                from_=0.05, to=0.95, increment=0.05, format="%.2f",
                width=5, bg="#16162a", fg=TEXT, insertbackground=TEXT,
                buttonbackground=ACCENT2, relief="flat", font=F_MAIN).pack(side=LEFT, padx=(0, 4))
        Button(row1, text="▶ Quét ảnh theo prompt", bg=ACCENT, fg="white", relief=FLAT,
               font=F_MAIN, padx=6, command=self._run_sam3_prompt).pack(side=LEFT, padx=(4, 8))
        row2 = Frame(sb, bg="#2e1a2e")
        row2.pack(fill=X)
        self._sam3_lbl = Label(row2,
                               text="Chưa load model — chọn thư mục chứa 3 file .onnx "
                                    "(sam3_image_encoder / sam3_language_encoder / sam3_decoder) "
                                    "rồi bấm Load. Nhập mô tả tiếng Anh cách nhau bởi dấu phẩy "
                                    "(VD: license plate, motorcycle) rồi bấm Quét — tự thêm 1 segment "
                                    "cho MỖI object khớp mô tả trong ảnh",
                               bg="#2e1a2e", fg=DIM, font=F_MAIN, anchor="w")
        self._sam3_lbl.pack(fill=X, padx=8)

    def _build_left(self, parent):
        f = Frame(parent, bg=CARD)
        parent.add(f, minsize=160, width=220)
        Label(f, text="Danh sách ảnh", bg=CARD, fg=TEXT,
              font=F_BOLD).pack(pady=(4, 0), padx=8, anchor=W)
        self._img_count_lbl = Label(f, text="—", bg=CARD, fg=DIM, font=F_MAIN, anchor=W)
        self._img_count_lbl.pack(padx=8, anchor=W, pady=(0, 4))

        flt_name = Frame(f, bg=CARD)
        flt_name.pack(fill=X, padx=6, pady=(0, 2))
        Label(flt_name, text="Tên:", bg=CARD, fg=DIM, font=F_MAIN, width=4,
              anchor=W).pack(side=LEFT)
        Entry(flt_name, textvariable=self._filter_name_var, bg="#16162a", fg=TEXT,
              insertbackground=TEXT, relief="flat", font=F_MAIN, bd=2).pack(
                  side=LEFT, fill=X, expand=True)
        self._filter_name_var.trace_add("write", lambda *_: self._schedule_filter())

        flt_unlab = Frame(f, bg=CARD)
        flt_unlab.pack(fill=X, padx=6, pady=(0, 2))
        Checkbutton(flt_unlab, text="Chỉ hiện chưa có nhãn", variable=self._filter_unlabeled,
                    bg=CARD, fg=TEXT, selectcolor="#16162a", activebackground=CARD,
                    font=F_MAIN, command=self._apply_filters).pack(side=LEFT, anchor=W)

        # Tiến độ xử lý (giống BBox Editor): Enter = lưu + đánh dấu đã xử lý + sang ảnh tiếp
        flt_prog = Frame(f, bg=CARD)
        flt_prog.pack(fill=X, padx=6, pady=(0, 2))
        Label(flt_prog, text="Tiến độ:", bg=CARD, fg=DIM, font=F_MAIN,
              width=6, anchor=W).pack(side=LEFT)
        self._filter_progress_combo = ttk.Combobox(
            flt_prog, textvariable=self._filter_progress_var, state="readonly",
            font=F_MAIN, width=10, values=["Tất cả", "Đã xử lý", "Chưa xử lý"])
        self._filter_progress_combo.pack(side=LEFT, fill=X, expand=True)
        self._filter_progress_combo.bind("<<ComboboxSelected>>", lambda e: self._apply_filters())
        self._progress_lbl = Label(f, text="", bg=CARD, fg="#4caf50", font=F_MAIN, anchor=W)
        self._progress_lbl.pack(fill=X, padx=8, pady=(0, 4))

        lf = Frame(f, bg=CARD)
        lf.pack(fill=BOTH, expand=True, padx=2)
        sb = Scrollbar(lf)
        sb.pack(side=RIGHT, fill=Y)
        self._img_lb = Listbox(lf, bg=BG, fg=TEXT, selectbackground=ACCENT2,
                               font=F_MAIN, yscrollcommand=sb.set, bd=0)
        self._img_lb.pack(fill=BOTH, expand=True)
        sb.config(command=self._img_lb.yview)
        self._img_lb.bind("<<ListboxSelect>>", self._on_list_sel)
        self._img_lb.bind("<Return>", lambda e: self._confirm_and_next())

    def _build_canvas(self, parent):
        wrap = Frame(parent, bg=BG)
        parent.add(wrap, minsize=300, stretch="always")

        ctb = Frame(wrap, bg=CARD, pady=3)
        ctb.pack(fill=X)
        self._zoom_lbl = Label(ctb, text="Fit", bg=CARD, fg="#5a5a7a",
                               font=("Consolas", 9), width=6, cursor="hand2")
        self._zoom_lbl.pack(side=RIGHT, padx=(0, 8))
        self._zoom_lbl.bind("<Button-1>", lambda e: self._zoom_reset())
        Button(ctb, text="−", command=lambda: self._zoom_step(0.8),
               bg=CARD, fg=TEXT, font=F_BOLD, relief="flat",
               cursor="hand2", width=2).pack(side=RIGHT)
        Button(ctb, text="+", command=lambda: self._zoom_step(1.25),
               bg=CARD, fg=TEXT, font=F_BOLD, relief="flat",
               cursor="hand2", width=2).pack(side=RIGHT, padx=(0, 1))
        Label(ctb, text="🔍", bg=CARD, fg=DIM, font=F_MAIN).pack(side=RIGHT, padx=(8, 2))

        self._canvas = Canvas(wrap, bg="#0d0d1a", cursor="crosshair",
                              highlightthickness=0)
        self._canvas.pack(fill=BOTH, expand=True)
        cv = self._canvas
        cv.bind("<Button-1>",        self._on_click)
        cv.bind("<Shift-Button-1>",  self._on_shift_click)
        cv.bind("<Button-3>",        self._on_right_click)
        cv.bind("<Double-Button-1>", self._on_double_click)
        cv.bind("<Motion>",          self._on_move)
        cv.bind("<B1-Motion>",       self._on_drag)
        cv.bind("<ButtonRelease-1>", self._on_release)
        cv.bind("<MouseWheel>",      self._on_zoom_wheel)
        cv.bind("<Button-2>",        self._on_pan_start)
        cv.bind("<B2-Motion>",       self._on_pan_drag)
        cv.bind("<ButtonRelease-2>", self._on_pan_end)
        cv.bind("<Configure>",       lambda e: self._render())
        cv.bind("<Return>",          lambda e: self._confirm_and_next())

    def _build_right(self, parent):
        f = Frame(parent, bg=CARD)
        parent.add(f, minsize=200, width=260)
        Label(f, text="Segments", bg=CARD, fg=TEXT,
              font=F_BOLD).pack(pady=(4, 2))
        sb = Scrollbar(f)
        sb.pack(side=RIGHT, fill=Y)
        self._seg_lb = Listbox(f, bg=BG, fg=TEXT, selectbackground=ACCENT2,
                               font=F_MAIN, yscrollcommand=sb.set, bd=0)
        self._seg_lb.pack(fill=BOTH, expand=True, padx=2)
        sb.config(command=self._seg_lb.yview)
        self._seg_lb.bind("<<ListboxSelect>>", self._on_seg_sel)

        Label(f, text="─" * 22, bg=CARD, fg=DIM).pack(pady=(4, 0))
        for txt, cmd in [("🗑 Xóa segment  Del",    self._delete_seg),
                         ("↩ Undo điểm  Ctrl+Z",    self._undo_pt),
                         ("➕ Thêm điểm (nắn chi tiết hơn)", self._add_points_selected),
                         ("➖ Giảm điểm (Simplify)",  self._simplify_selected),
                         ("🧹 Dọn vệt kẻ lạ (seam)", self._clean_selected),
                         ("✖ Hủy vẽ  Esc",          self._cancel)]:
            Button(f, text=txt, bg=CARD, fg=TEXT, relief=FLAT,
                   font=F_MAIN, command=cmd, anchor="w",
                   padx=6).pack(pady=2, padx=4, fill=X)

        Label(f, text="─" * 22, bg=CARD, fg=DIM).pack(pady=(6, 0))
        Label(f, text="Dùng bbox làm khung SAM/CV Box\n(khỏi kéo khung lại):",
              bg=CARD, fg=DIM, font=F_MAIN, justify=LEFT, anchor="w").pack(
                  fill=X, padx=4, pady=(2, 2))
        Button(f, text="🪄 Auto-tách segment này", bg=ACCENT2, fg="white", relief=FLAT,
               font=F_MAIN, command=self._auto_refine_selected, anchor="w",
               padx=6).pack(pady=2, padx=4, fill=X)
        self._auto_all_btn = Button(
            f, text="🪄 Auto-tách TẤT CẢ bbox (0)", bg=ACCENT2, fg="white", relief=FLAT,
            font=F_MAIN, command=self._auto_refine_all_bbox, anchor="w", padx=6)
        self._auto_all_btn.pack(pady=2, padx=4, fill=X)


    def _browse_dir(self):
        d = filedialog.askdirectory(initialdir=self._img_dir.get() or ".")
        if d: self._img_dir.set(d); _cfg_save(); self._load_dir(d)

    def _load_dir(self, d: str):
        self._img_root = Path(d)
        if self._recursive_var.get():
            self._img_files = sorted(
                p for p in self._img_root.rglob("*")
                if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS)
        else:
            self._img_files = sorted(
                p for p in self._img_root.iterdir()
                if p.suffix.lower() in IMAGE_EXTENSIONS)
        self._refresh_progress_file()
        self._apply_filters()
        if self._filtered_idx: self._load_img(self._filtered_idx[0])

    def _label_path_for(self, img_path: Path) -> Path:
        lbl_dir = self._lbl_dir_var.get().strip()
        return (Path(lbl_dir) / (img_path.stem + ".txt")) if lbl_dir else img_path.with_suffix(".txt")

    # ── Tiến độ xử lý (.kztek_progress.json) — giống BBox Editor ───────────────
    def _refresh_progress_file(self):
        lbl_dir = self._lbl_dir_var.get().strip()
        base = Path(lbl_dir) if lbl_dir else Path(self._img_dir.get().strip() or ".")
        self._progress_file = base / ".kztek_progress.json"
        self._progress_set = load_progress(self._progress_file)
        self._update_progress_display()

    def _is_done(self, fp: Path) -> bool:
        return fp.name in self._progress_set

    def _mark_done(self, fp: Path = None):
        if fp is None:
            if not self._img_files: return
            fp = self._img_files[self._img_idx]
        self._progress_set.add(fp.name)
        save_progress(self._progress_file, self._progress_set)
        self._update_progress_display()

    def _update_progress_display(self):
        if not hasattr(self, "_progress_lbl"):
            return   # gọi sớm trong lúc _build() (vd: _bind_history restore combobox) — chưa có widget
        if not self._img_files:
            self._progress_lbl.config(text=""); return
        total = len(self._img_files)
        done = sum(1 for fp in self._img_files if self._is_done(fp))
        pct = int(done * 100 / total) if total else 0
        bar_w = 10
        filled = int(bar_w * pct / 100)
        bar = "█" * filled + "░" * (bar_w - filled)
        self._progress_lbl.config(
            text=f"{bar} {done}/{total} ({pct}%)",
            fg="#4caf50" if pct == 100 else "#F05922" if pct > 0 else DIM)

    def _confirm_and_next(self):
        """Enter — lưu segment, đánh dấu ảnh đã xử lý, chuyển sang ảnh tiếp theo
        (giống BBox Editor)."""
        if not self._img_files:
            return
        self._save()
        self._mark_done(self._img_files[self._img_idx])
        self._apply_filters()
        self._next_img()

    def _schedule_filter(self):
        if self._filter_after_id:
            self.after_cancel(self._filter_after_id)
        self._filter_after_id = self.after(250, self._apply_filters)

    def _apply_filters(self):
        """Lọc danh sách ảnh theo tên / trạng thái nhãn / tiến độ xử lý — tương tự BBox Editor."""
        self._filter_after_id = None
        name_q = self._filter_name_var.get().strip().lower()
        only_unlabeled = self._filter_unlabeled.get()
        prog_q = self._filter_progress_var.get()
        self._filtered_idx = []
        for i, fp in enumerate(self._img_files):
            if name_q and name_q not in fp.name.lower():
                continue
            if only_unlabeled:
                lp = self._label_path_for(fp)
                if lp.exists() and lp.stat().st_size > 0:
                    continue
            if prog_q == "Đã xử lý" and not self._is_done(fp):
                continue
            if prog_q == "Chưa xử lý" and self._is_done(fp):
                continue
            self._filtered_idx.append(i)
        self._img_lb.delete(0, END)
        recursive = self._recursive_var.get()
        for i in self._filtered_idx:
            fp = self._img_files[i]
            done = self._is_done(fp)
            try:
                display = str(fp.relative_to(self._img_root)) if recursive and self._img_root else fp.name
            except ValueError:
                display = fp.name
            self._img_lb.insert(END, f"{'✓' if done else '○'} {display}")
            self._img_lb.itemconfig(END, fg="#4caf50" if done else TEXT)
        self._img_count_lbl.config(text=f"{len(self._filtered_idx)}/{len(self._img_files)} ảnh")
        self._update_progress_display()
        if self._img_files and self._img_idx in self._filtered_idx:
            pos = self._filtered_idx.index(self._img_idx)
            self._img_lb.selection_clear(0, END)
            self._img_lb.selection_set(pos); self._img_lb.see(pos)

    def _load_img(self, idx: int):
        if not self._img_files: return
        idx = max(0, min(idx, len(self._img_files) - 1))
        self._img_idx = idx
        if idx in self._filtered_idx:
            pos = self._filtered_idx.index(idx)
            self._img_lb.selection_clear(0, END)
            self._img_lb.selection_set(pos); self._img_lb.see(pos)
            self._nav_lbl.config(text=f"{pos + 1} / {len(self._filtered_idx)}")
        else:
            self._nav_lbl.config(text=f"{idx + 1} / {len(self._img_files)}")
        try:
            self._pil_img = Image.open(self._img_files[idx]).convert("RGB")
        except Exception as e:
            self._status_var.set(f"Lỗi load ảnh: {e}"); return
        self._render_base = None
        self._drawing.clear(); self._cursor = None; self._sel = -1; self._drag = None
        self._preview_poly = None; self._sam_pts.clear()
        self._undo_stack.clear()   # lịch sử hoàn tác không dùng chéo giữa các ảnh khác nhau
        self._pending_click = None; self._draw_as_sambox = False
        self._cv_mask = None; self._cv_edges = None; self._cv_dragging = False; self._cv_seed_si = None
        # Nạp nhãn TRƯỚC khi render (qua _zoom_reset) — nếu render trước sẽ vẽ nhầm
        # segment của ảnh cũ lên ảnh mới (đây là nguyên nhân lỗi "segment ảnh 1 dính sang ảnh 2")
        self._load_labels(); self._zoom_reset(); self._refresh_segs()
        iw, ih = self._pil_img.size
        bbox_note = f"  ({self._n_from_bbox} từ bbox, kéo góc để tinh chỉnh)" if self._n_from_bbox else ""
        self._status_var.set(f"{self._img_files[idx].name}  ({iw}×{ih})  —  {len(self._segments)} segment{bbox_note}")

    def _on_list_sel(self, _):
        sel = self._img_lb.curselection()
        if sel and sel[0] < len(self._filtered_idx):
            self._load_img(self._filtered_idx[sel[0]])

    def _prev_img(self):
        if not self._filtered_idx: return
        self._save()
        pos = self._filtered_idx.index(self._img_idx) if self._img_idx in self._filtered_idx else 0
        self._load_img(self._filtered_idx[max(0, pos - 1)])

    def _next_img(self):
        if not self._filtered_idx: return
        self._save()
        pos = self._filtered_idx.index(self._img_idx) if self._img_idx in self._filtered_idx else 0
        self._load_img(self._filtered_idx[min(len(self._filtered_idx) - 1, pos + 1)])

    def _lbl_path(self) -> Path | None:
        if not self._img_files:
            return None
        return self._label_path_for(self._img_files[self._img_idx])

    def _on_lbl_dir_change(self, *_):
        """Đổi thư mục label -> nạp lại nhãn của ảnh đang mở từ vị trí mới."""
        self._refresh_progress_file()   # .kztek_progress.json đi theo thư mục label (như BBox Editor)
        if self._filter_unlabeled.get() or self._filter_progress_var.get() != "Tất cả":
            self._apply_filters()
        if self._pil_img is None:
            return
        self._load_labels(); self._sel = -1; self._refresh_segs(); self._render()
        bbox_note = f"  ({self._n_from_bbox} từ bbox)" if self._n_from_bbox else ""
        self._status_var.set(f"Đã đổi thư mục label — {len(self._segments)} segment{bbox_note}")

    def _load_labels(self):
        """Đọc file .txt cạnh ảnh. Nhận cả 2 định dạng:
        - Segment (YOLO-Seg): `cid x1 y1 x2 y2 … xn yn` (>=7 phần tử, tọa độ chẵn)
        - BBox (YOLO Detect): `cid cx cy w h` (đúng 5 phần tử) — TỰ ĐỘNG quy đổi
          thành polygon hình chữ nhật 4 điểm để tinh chỉnh tiếp thành segment thật,
          thay vì bỏ qua như trước (tránh mất nhãn bbox có sẵn khi Lưu)."""
        self._segments = []
        self._bbox_derived = set()
        lp = self._lbl_path()
        if not lp or not lp.exists():
            return
        iw, ih = self._pil_img.size
        n_from_bbox = 0
        for line in lp.read_text(encoding="utf-8").splitlines():
            parts = line.strip().split()
            if not parts:
                continue
            if len(parts) == 5:
                try:
                    cid = int(parts[0])
                    cx, cy, w, h = map(float, parts[1:])
                    x1, y1 = (cx - w / 2) * iw, (cy - h / 2) * ih
                    x2, y2 = (cx + w / 2) * iw, (cy + h / 2) * ih
                    self._segments.append([cid, [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]])
                    self._bbox_derived.add(len(self._segments) - 1)
                    n_from_bbox += 1
                except Exception:
                    pass
                continue
            if len(parts) < 7:          # cid + min 3 điểm (6 values)
                continue
            try:
                cid = int(parts[0])
                coords = list(map(float, parts[1:]))
                if len(coords) % 2 != 0:
                    continue
                pts = [(coords[i] * iw, coords[i + 1] * ih)
                       for i in range(0, len(coords), 2)]
                self._segments.append([cid, pts])
            except Exception:
                continue
        self._n_from_bbox = n_from_bbox
        if hasattr(self, "_auto_all_btn"):
            self._auto_all_btn.config(text=f"🪄 Auto-tách TẤT CẢ bbox ({len(self._bbox_derived)})")

    def _save(self):
        if self._pil_img is None or self._drawing:
            return
        lp = self._lbl_path()
        if not lp:
            return
        iw, ih = self._pil_img.size
        lines = []
        for cid, pts in self._segments:
            if len(pts) < 3:
                continue
            coords = " ".join(
                f"{max(0.0, min(1.0, x / iw)):.6f} "
                f"{max(0.0, min(1.0, y / ih)):.6f}"
                for x, y in pts)
            lines.append(f"{cid} {coords}")
        lp.write_text("\n".join(lines), encoding="utf-8")
        self._status_var.set(f"Đã lưu  {lp.name}  ({len(lines)} segment)")

    def _c2i(self, cx: float, cy: float) -> tuple[float, float]:
        s = self._scale or 1.0
        return (cx - self._off_x) / s, (cy - self._off_y) / s

    def _i2c(self, ix: float, iy: float) -> tuple[float, float]:
        return ix * self._scale + self._off_x, iy * self._scale + self._off_y

    @staticmethod
    def _point_in_poly(px: float, py: float, poly: list[tuple]) -> bool:
        """Ray-casting: True nếu điểm (px,py) nằm trong đa giác `poly`."""
        inside = False
        x1, y1 = poly[-1]
        for x2, y2 in poly:
            if (y1 > py) != (y2 > py):
                x_at = x1 + (py - y1) * (x2 - x1) / (y2 - y1)
                if px < x_at:
                    inside = not inside
            x1, y1 = x2, y2
        return inside

    def _try_start_edit_drag(self, e) -> bool:
        """Nếu click trúng 1 điểm hoặc nằm trong thân 1 segment có sẵn, chọn + bắt
        đầu kéo (di chuyển điểm hoặc cả segment) và trả về True. Nhờ hàm này mà
        mode "Vẽ" tự nhận biết khi nào nên Sửa thay vì phải bấm đổi mode thủ công."""
        best_s, best_v, best_d = -1, -1, 12.0
        for si, (_, pts) in enumerate(self._segments):
            for vi, pt in enumerate(pts):
                cx, cy = self._i2c(*pt)
                d = ((e.x - cx) ** 2 + (e.y - cy) ** 2) ** 0.5
                if d < best_d:
                    best_d, best_s, best_v = d, si, vi
        if best_s >= 0:
            self._push_undo()   # lưu trước khi kéo — Ctrl+Z hoàn tác cả cú kéo (không phải từng pixel)
            self._sel = best_s
            self._drag = (best_s, best_v, e.x, e.y)
            self._refresh_segs(); self._render()
            return True
        # Nhiều segment chồng nhau (ví dụ license_plate nằm lọt trong motorcycle):
        # ưu tiên chọn segment có diện tích NHỎ NHẤT trong số các segment chứa điểm
        # click — đúng với kỳ vọng "click vào box nhỏ bên trong thì chọn box nhỏ đó",
        # thay vì luôn dính vào box lớn hơn duyệt trước.
        ix, iy = self._c2i(e.x, e.y)
        best_si, best_area = -1, None
        for si, (_, pts) in enumerate(self._segments):
            if not self._point_in_poly(ix, iy, pts):
                continue
            x1, y1, x2, y2 = self._seg_bbox(pts)
            area = (x2 - x1) * (y2 - y1)
            if best_area is None or area < best_area:
                best_si, best_area = si, area
        if best_si >= 0:
            self._push_undo()
            self._sel = best_si
            self._drag = (best_si, None, e.x, e.y)   # vi=None -> kéo cả segment
            self._refresh_segs(); self._render()
            return True
        return False

    def _on_click(self, e):
        if self._pil_img is None:
            return
        mode = self._mode_var.get()
        if mode in ("sam", "sam_box", "cv_box"):
            if mode == "sam":
                self._handle_sam_click(e)
            else:
                self._box_start = self._c2i(e.x, e.y)
                self._box_end = None
            return
        if mode == "cv":
            self._start_cv_drag(e)
            return
        if mode == "draw":
            # Chưa vẽ dở & click trúng điểm/segment có sẵn -> tự chuyển sang Sửa
            if not self._drawing and self._try_start_edit_drag(e):
                return
            if len(self._drawing) >= 3:
                fx, fy = self._i2c(*self._drawing[0])
                if abs(e.x - fx) < 10 and abs(e.y - fy) < 10:
                    self._close_poly()
                    return
            if not self._drawing:
                # Click ĐẦU TIÊN trên vùng trống (chưa vẽ dở gì) -> chưa vội quyết
                # định là thêm điểm vẽ hay bắt đầu kéo khung SAM Box; chờ xem người
                # dùng có kéo chuột hay không (xem _on_drag/_on_release).
                self._pending_click = (e.x, e.y)
                return
            ix, iy = self._c2i(e.x, e.y)
            self._drawing.append((ix, iy))
            self._render()
        else:
            self._try_start_edit_drag(e)

    def _on_move(self, e):
        if self._drawing and self._mode_var.get() == "draw":
            self._cursor = self._c2i(e.x, e.y)
            self._render()

    def _on_release(self, e):
        self._drag = None
        mode = self._mode_var.get()
        if mode == "cv":
            self._cv_dragging = False
            self._cv_last_pt = None
        if mode == "draw" and self._pending_click is not None:
            # Không kéo đủ xa để tính là drag -> coi như 1 click đơn giản -> thêm điểm vẽ
            ix, iy = self._c2i(*self._pending_click)
            self._pending_click = None
            self._drawing.append((ix, iy))
            self._render()
            return
        if mode == "draw" and self._draw_as_sambox:
            self._draw_as_sambox = False
            if self._box_start and self._box_end:
                x1, y1 = self._box_start; x2, y2 = self._box_end
                if abs(x2 - x1) > 5 and abs(y2 - y1) > 5:
                    self._fire_sam(box=(min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)))
            self._box_start = self._box_end = None
            self._render()
            return
        if mode == "sam_box" and self._box_start and self._box_end:
            x1, y1 = self._box_start; x2, y2 = self._box_end
            if abs(x2-x1) > 5 and abs(y2-y1) > 5:
                self._fire_sam(box=(min(x1,x2), min(y1,y2), max(x1,x2), max(y1,y2)))
        elif mode == "cv_box" and self._box_start and self._box_end:
            x1, y1 = self._box_start; x2, y2 = self._box_end
            if abs(x2-x1) > 5 and abs(y2-y1) > 5:
                self._fire_cv_box(min(x1,x2), min(y1,y2), max(x1,x2), max(y1,y2))
        self._box_start = self._box_end = None
        self._render()

    def _on_drag(self, e):
        mode = self._mode_var.get()
        if mode == "draw" and self._pending_click is not None:
            dx = e.x - self._pending_click[0]
            dy = e.y - self._pending_click[1]
            if (dx * dx + dy * dy) ** 0.5 > 6:
                # Kéo đủ xa khỏi click đầu tiên -> tự nhận diện là kéo khung SAM Box
                self._box_start = self._c2i(*self._pending_click)
                self._box_end = self._c2i(e.x, e.y)
                self._draw_as_sambox = True
                self._pending_click = None
                self._render()
            return
        if mode == "draw" and self._draw_as_sambox and self._box_start:
            self._box_end = self._c2i(e.x, e.y)
            self._render()
            return
        if mode in ("sam_box", "cv_box") and self._box_start:
            self._box_end = self._c2i(e.x, e.y)
            self._render()
            return
        if mode == "cv" and self._cv_dragging:
            ix, iy = self._c2i(e.x, e.y)
            lp = self._cv_last_pt
            if lp is None or (abs(ix - lp[0]) + abs(iy - lp[1])) > 3:
                self._cv_last_pt = (ix, iy)
                subtract = bool(e.state & 0x0001)   # giữ Shift trong lúc kéo = TRỪ vùng
                self._grow_cv_mask(ix, iy, subtract=subtract)
            return
        if self._drag is None or mode not in ("edit", "draw"):
            return
        si, vi = self._drag[0], self._drag[1]
        iw, ih = self._pil_img.size
        ix, iy = self._c2i(e.x, e.y)
        if vi is None:
            # Kéo cả segment: dịch tất cả điểm theo delta so với frame trước
            last_ix, last_iy = self._c2i(self._drag[2], self._drag[3])
            dx, dy = ix - last_ix, iy - last_iy
            self._segments[si][1] = [
                (max(0.0, min(float(iw), x + dx)), max(0.0, min(float(ih), y + dy)))
                for x, y in self._segments[si][1]]
            self._drag = (si, None, e.x, e.y)
        else:
            nx = max(0.0, min(float(iw), ix))
            ny = max(0.0, min(float(ih), iy))
            pts = self._segments[si][1]
            if si in self._bbox_derived and len(pts) == 4:
                # Segment còn là bbox thô (chưa auto-tách) — kéo góc = RESIZE giữ
                # nguyên hình chữ nhật (giống BBox Editor), không biến thành tứ giác
                # lệch tự do. Thứ tự điểm cố định: 0=TL 1=TR 2=BR 3=BL.
                x1, y1 = pts[0]; x2, _y1 = pts[1]; _x2, y2 = pts[2]
                if vi == 0:   x1, y1 = nx, ny
                elif vi == 1: x2, y1 = nx, ny
                elif vi == 2: x2, y2 = nx, ny
                elif vi == 3: x1, y2 = nx, ny
                self._segments[si][1] = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
            else:
                pts[vi] = (nx, ny)
            self._drag = (si, vi, e.x, e.y)
        self._render()

    def _on_shift_click(self, e):
        mode = self._mode_var.get()
        if mode == "sam":
            self._add_sam_pt(e, label=0)  # negative prompt
        elif mode == "cv":
            self._start_cv_drag(e, subtract=True)   # Shift+click/kéo = TRỪ vùng (giống Photoshop Alt-drag)

    def _on_right_click(self, e):
        mode = self._mode_var.get()
        if mode in ("sam", "cv", "cv_box") and self._preview_poly:
            self._confirm_preview()
        else:
            self._close_poly()

    def _add_sam_pt(self, e, label: int = 1):
        if self._pil_img is None: return
        ix, iy = self._c2i(e.x, e.y)
        iw, ih = self._pil_img.size
        if not (0 <= ix <= iw and 0 <= iy <= ih): return
        self._sam_pts.append((ix, iy, label))
        self._fire_sam(points=self._sam_pts)

    def _confirm_preview(self):
        if not self._preview_poly: return
        self._push_undo()
        if self._cv_seed_si is not None and 0 <= self._cv_seed_si < len(self._segments):
            # Phiên CV Edge này được seed từ 1 segment có sẵn (mở rộng thêm phần
            # thiếu) -> THAY THẾ đúng segment đó, không tạo segment mới trùng lặp.
            self._segments[self._cv_seed_si][1] = self._preview_poly
            self._sel = self._cv_seed_si
            msg = f"Đã mở rộng segment [{self._sel}]"
        else:
            self._segments.append([self._get_cid(), self._preview_poly])
            self._sel = len(self._segments) - 1
            msg = f"Đã thêm segment — {len(self._segments)} tổng"
        self._preview_poly = None; self._sam_pts.clear()
        self._cv_mask = None; self._cv_edges = None; self._cv_seed_si = None
        self._refresh_segs(); self._render()
        self._status_var.set(msg)

    def _close_poly(self):
        if len(self._drawing) >= 3:
            self._push_undo()
            cid = self._get_cid()
            self._segments.append([cid, list(self._drawing)])
            self._sel = len(self._segments) - 1
            self._refresh_segs()
        self._drawing.clear(); self._cursor = None; self._render()

    def _on_double_click(self, e):
        """Đang vẽ dở (>=3 điểm) → đóng polygon (hành vi cũ). Ngược lại (double-click
        không có tác dụng gì trước đây) → phóng to tại đúng điểm double-click, giống
        double-click zoom kiểu bản đồ — tái dùng logic zoom-tại-con-trỏ của _on_zoom_wheel."""
        if len(self._drawing) >= 3:
            self._close_poly()
            return
        if self._pil_img is None:
            return
        class _FakeWheel:
            x = e.x; y = e.y; delta = 120
        self._on_zoom_wheel(_FakeWheel())

    def _get_cid(self) -> int:
        try:
            return int(self._class_var.get().split(":")[0])
        except Exception:
            return 0

    def _render(self, resample=None):
        if self._pil_img is None:
            return
        self._zoom_lbl.config(
            text="Fit" if abs(self._zoom_level - 1.0) < 0.01 else f"{int(self._zoom_level * 100)}%")
        sc, nw, nh, ox, oy = self._calc_zoom_offsets()
        if self._render_base is None or self._render_nw_nh != (nw, nh):
            self._render_base = self._pil_img.resize(
                (nw, nh), Image.LANCZOS).convert("RGBA")
            self._render_nw_nh = (nw, nh)

        overlay = Image.new("RGBA", (nw, nh), (0, 0, 0, 0))
        dr = ImageDraw.Draw(overlay)

        def _dp(pts):
            return [(x * sc, y * sc) for x, y in pts]

        # Completed segments — mỗi OBJECT 1 màu riêng (_COLORS[si % 8], theo index
        # trong _segments) — không theo class, để phân biệt được nhiều object CÙNG
        # class (VD 4 người từ SAM3 text-prompt) đứng cạnh/chồng nhau. Segment đang
        # chọn được vẽ SAU CÙNG (luôn nổi lên trên, không bị segment khác đè khuất khi
        # chồng lấn — ví dụ license_plate nằm lọt trong motorcycle) + viền trắng dày
        # nổi bật để chắc chắn nhận ra, bất kể trùng màu với segment khác.
        # Nút "👁 Hiện segment" cho phép tắt hẳn overlay này để xem ảnh gốc sạch.
        order = sorted(range(len(self._segments)), key=lambda i: i == self._sel) \
            if self._show_seg_var.get() else []
        for si in order:
            cid, pts = self._segments[si]
            col = _COLORS[si % len(_COLORS)]
            r, g, b = int(col[1:3], 16), int(col[3:5], 16), int(col[5:7], 16)
            dp = _dp(pts)
            is_sel = (si == self._sel)
            if len(dp) >= 3:
                # Fill nhạt để vẫn thấy rõ object thật phía sau (chỉ dùng để nhận diện
                # vùng đã khoanh, không che khuất chi tiết ảnh) — viền đậm để phân định ranh giới
                alpha = 65 if is_sel else 28
                dr.polygon(dp, fill=(r, g, b, alpha), outline=(r, g, b, 220))
                if is_sel:
                    dr.line(dp + [dp[0]], fill=(255, 255, 255, 200), width=2)
            for vx, vy in dp:
                dr.ellipse([vx - 4, vy - 4, vx + 4, vy + 4],
                           fill=(r, g, b, 255), outline=(255, 255, 255, 200))

        # In-progress polygon
        if self._drawing:
            dp = _dp(self._drawing)
            ap = dp + [_dp([self._cursor])[0]] if self._cursor else dp
            for i in range(len(ap) - 1):
                dr.line([ap[i], ap[i + 1]], fill=(255, 200, 0, 255), width=2)
            # Snap indicator on first vertex
            if len(self._drawing) >= 3 and self._cursor:
                vx, vy = dp[0]
                dr.ellipse([vx - 8, vy - 8, vx + 8, vy + 8],
                           outline=(255, 200, 0, 200), width=2)
            for vx, vy in dp:
                dr.ellipse([vx - 4, vy - 4, vx + 4, vy + 4],
                           fill=(255, 200, 0, 255), outline=(255, 255, 255, 200))

        # SAM Box / CV Box drag preview
        if self._box_start and self._box_end:
            bx1,by1 = self._box_start[0]*sc, self._box_start[1]*sc
            bx2,by2 = self._box_end[0]*sc,   self._box_end[1]*sc
            bx1, bx2 = min(bx1, bx2), max(bx1, bx2)
            by1, by2 = min(by1, by2), max(by1, by2)
            dr.rectangle([bx1,by1,bx2,by2], outline=(255,220,0,220), width=2)

        # Click preview mask (SAM hoặc CV Edge) — vàng nhạt, chờ xác nhận
        if self._preview_poly:
            pv = _dp(self._preview_poly)
            if len(pv) >= 3:
                dr.polygon(pv, fill=(255,210,0,70), outline=(255,210,0,230))

        # SAM prompt points (xanh=positive, đỏ=negative)
        for ix, iy, lbl in self._sam_pts:
            cx,cy = ix*sc, iy*sc
            col = (30,200,30,255) if lbl==1 else (220,30,30,255)
            dr.ellipse([cx-6,cy-6,cx+6,cy+6], fill=col, outline=(255,255,255,220))

        result = Image.alpha_composite(self._render_base, overlay)
        self._tk_img = ImageTk.PhotoImage(result)
        self._canvas.delete("all")
        self._canvas.create_image(ox, oy, anchor="nw", image=self._tk_img)

    def _refresh_segs(self):
        self._seg_lb.delete(0, END)
        for i, (cid, pts) in enumerate(self._segments):
            name = CLASS_NAMES.get(cid, str(cid))
            mark = "▶ " if i == self._sel else "   "
            self._seg_lb.insert(END, f"{mark}[{i}] {name}  ({len(pts)}pt)")
        if 0 <= self._sel < self._seg_lb.size():
            self._seg_lb.selection_set(self._sel)
            self._seg_lb.see(self._sel)

    def _on_seg_sel(self, _):
        sel = self._seg_lb.curselection()
        if sel:
            self._sel = sel[0]
            self._render()

    def _delete_seg(self):
        if 0 <= self._sel < len(self._segments):
            self._push_undo()
            self._segments.pop(self._sel)
            self._sel = min(self._sel, len(self._segments) - 1)
            self._refresh_segs()
            self._render()

    def _on_numkey_label(self, n: int):
        """Phím 0-9: chọn class n; nếu có segment đang chọn → relabel ngay
        (giống `_on_numkey_label` của BBox Editor)."""
        vals = self._cls_cb["values"]
        match = next((v for v in vals if v.startswith(f"{n}:")), None)
        if match:
            self._class_var.set(match)
        if 0 <= self._sel < len(self._segments):
            self._push_undo()
            self._segments[self._sel][0] = n
            self._refresh_segs(); self._render()
            self._status_var.set(f"Đã đổi class segment [{self._sel}] → {n}: {CLASS_NAMES.get(n, n)}")

    def _add_points_selected(self):
        """Chèn thêm 1 điểm giữa MỖI cạnh của segment đang chọn (luôn tăng gấp đôi
        số điểm, kể cả hình chữ nhật 4 điểm từ bbox) — có thêm điểm để kéo nắn
        polygon chi tiết hơn theo đúng hình object thật."""
        if not (0 <= self._sel < len(self._segments)):
            self._status_var.set("Chưa chọn segment nào — click chọn 1 segment rồi thử lại"); return
        cid, pts = self._segments[self._sel]
        if len(pts) < 3:
            return
        self._push_undo()
        n = len(pts)
        new_pts = []
        for i in range(n):
            x1, y1 = pts[i]
            x2, y2 = pts[(i + 1) % n]
            new_pts.append((x1, y1))
            new_pts.append(((x1 + x2) / 2.0, (y1 + y2) / 2.0))
        n_old = n
        self._segments[self._sel][1] = new_pts
        self._refresh_segs(); self._render()
        self._status_var.set(
            f"Thêm điểm segment [{self._sel}]: {n_old} → {len(new_pts)} điểm — kéo các điểm mới để nắn hình")

    def _simplify_selected(self):
        """Áp dụng Douglas-Peucker (theo slider Simplify) để GIẢM bớt điểm của
        RIÊNG segment đang chọn — chỉ có tác dụng nếu polygon có điểm dư thừa
        (VD: hình chữ nhật 4 điểm từ bbox thì không giảm được nữa, dùng '➕ Thêm
        điểm' nếu muốn nắn chi tiết hơn)."""
        if not (0 <= self._sel < len(self._segments)):
            self._status_var.set("Chưa chọn segment nào — click chọn 1 segment rồi thử lại"); return
        eps = self._simplify_var.get()
        if eps <= 0:
            self._status_var.set("Kéo slider Simplify (thanh SAM) > 0 rồi bấm lại để giảm bớt điểm"); return
        cid, pts = self._segments[self._sel]
        n_old = len(pts)
        new_pts = _simplify(pts, eps)
        if len(new_pts) < 3:
            self._status_var.set("Không thể đơn giản hóa thêm (tối thiểu 3 điểm)"); return
        if len(new_pts) >= n_old:
            self._status_var.set(
                f"Segment [{self._sel}] ({n_old} điểm) đã tối giản — không giảm thêm được. "
                "Muốn nắn chi tiết hơn thì dùng '➕ Thêm điểm', hoặc kéo slider Simplify cao hơn.")
            return
        self._push_undo()
        self._segments[self._sel][1] = new_pts
        self._refresh_segs(); self._render()
        self._status_var.set(f"Giảm điểm segment [{self._sel}]: {n_old} → {len(new_pts)} điểm")

    def _clean_selected(self):
        """Dọn 'vệt kẻ lạ' (seam)/lỗ lởm chởm của segment đang chọn — lỗi cũ từ khi
        SAM còn dùng masks.xy (đã fix tận gốc trong sam_utils._extract, dùng cho
        segment MỚI từ giờ). Nút này chỉ để sửa segment CŨ đã lỡ tạo trước khi fix.
        Dùng convex hull nên có thể mất 1 phần chi tiết lõm thật — nếu cần chính
        xác cao hơn, Auto-tách LẠI segment này sẽ cho kết quả sạch ngay từ đầu."""
        if not (0 <= self._sel < len(self._segments)):
            self._status_var.set("Chưa chọn segment nào — click chọn 1 segment rồi thử lại"); return
        cid, pts = self._segments[self._sel]
        cleaned = clean_polygon(pts)
        if not cleaned or len(cleaned) < 3:
            self._status_var.set("Không dọn được polygon này"); return
        self._push_undo()
        n_old = len(pts)
        self._segments[self._sel][1] = cleaned
        self._refresh_segs(); self._render()
        self._status_var.set(
            f"Đã dọn seam segment [{self._sel}]: {n_old} → {len(cleaned)} điểm (convex hull — "
            "nếu mất chi tiết lõm quan trọng, thử Auto-tách LẠI segment này thay vì dọn)")

    @staticmethod
    def _seg_bbox(pts) -> tuple[float, float, float, float]:
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        return min(xs), min(ys), max(xs), max(ys)

    def _auto_refine_selected(self):
        """Dùng bbox (hộp bao) của segment đang chọn làm khung cho SAM Box (nếu đã
        load SAM) hoặc CV Box/GrabCut (nếu chưa) — tách polygon tự động, KHỎI phải
        kéo vẽ lại khung bằng tay."""
        if not (0 <= self._sel < len(self._segments)) or self._pil_img is None:
            self._status_var.set("Chưa chọn segment nào — click chọn 1 segment rồi thử lại"); return
        self._auto_refine_queue = []   # 1 segment đơn lẻ, không chuỗi tiếp theo
        self._start_auto_refine(self._sel)

    def _auto_refine_all_bbox(self):
        """Tự động tách LẦN LƯỢT tất cả segment còn là bbox thô (chưa tinh chỉnh)
        trong ảnh hiện tại — dùng SAM Box nếu có model, không thì CV Box (GrabCut)."""
        idxs = sorted(self._bbox_derived)
        if not idxs:
            self._status_var.set("Không có bbox nào cần tự động tách trong ảnh này"); return
        self._auto_refine_queue = idxs
        self._status_var.set(f"Đang tự động tách {len(idxs)} bbox…")
        self._auto_refine_next()

    def _auto_refine_next(self):
        if not self._auto_refine_queue:
            return
        si = self._auto_refine_queue.pop(0)
        if not (0 <= si < len(self._segments)):
            self._auto_refine_next(); return
        self._start_auto_refine(si)

    def _start_auto_refine(self, si: int):
        """Auto-tách LUÔN giữ chi tiết đầy đủ (eps=0, bỏ qua slider Simplify) —
        polygon object thật (xe máy, người...) có nhiều răng cưa nhỏ (bánh xe, tay
        lái, gương) nên Simplify tính theo % chu vi rất dễ phá vỡ hình dạng (VD:
        eps=2% từng biến 1 polygon xe máy chi tiết thành tam giác méo chỉ còn ~10
        điểm). Muốn giảm điểm thì dùng nút '➖ Giảm điểm' riêng SAU khi xem kết quả,
        có phản hồi rõ trước/sau thay vì áp mù."""
        self._push_undo()   # lưu trạng thái TRƯỚC khi ghi đè — Ctrl+Z khôi phục lại được
        cid, pts = self._segments[si]
        x1, y1, x2, y2 = self._seg_bbox(pts)
        eps = 0
        if self._sam_model is not None:
            self._status_var.set(f"Đang tự động tách segment [{si}] bằng SAM (giữ chi tiết đầy đủ)…")
            self._canvas.config(cursor="watch")
            img = self._pil_img.copy()
            threading.Thread(target=self._run_auto_refine_sam,
                             args=(img, si, x1, y1, x2, y2, eps), daemon=True).start()
        else:
            self._status_var.set(
                f"⚠ Chưa load SAM — đang dùng CV Box (GrabCut, kém chi tiết hơn SAM). "
                f"Load 1 trong 3 model SAM ở thanh trên rồi Auto-tách lại để có kết quả chính xác hơn.")
            self._canvas.config(cursor="watch")
            img = self._pil_img.copy()
            threading.Thread(target=self._run_auto_refine_cv,
                             args=(img, si, x1, y1, x2, y2, eps), daemon=True).start()

    def _run_auto_refine_sam(self, img, si, x1, y1, x2, y2, eps):
        try:
            pts = run_sam_box(self._sam_model, img, x1, y1, x2, y2)
            if pts: pts = _simplify(pts, eps)
            self.root.after(0, lambda: self._after_auto_refine(si, pts or None, method="SAM"))
        except Exception as ex:
            msg = str(ex)
            self.root.after(0, lambda: self._after_auto_refine(si, None, msg, method="SAM"))

    def _run_auto_refine_cv(self, img, si, x1, y1, x2, y2, eps):
        try:
            mask = run_grabcut_box(img, x1, y1, x2, y2)
            pts = mask_to_polygon(mask) if mask is not None else None
            if pts: pts = _simplify(pts, eps)
            self.root.after(0, lambda: self._after_auto_refine(si, pts or None, method="CV Box"))
        except Exception as ex:
            msg = str(ex)
            self.root.after(0, lambda: self._after_auto_refine(si, None, msg, method="CV Box"))

    def _after_auto_refine(self, si: int, pts, err: str = None, method: str = ""):
        self._canvas.config(cursor="crosshair")
        if err:
            self._status_var.set(f"Auto-tách segment [{si}] ({method}) lỗi: {err}")
        elif pts and 0 <= si < len(self._segments):
            self._segments[si][1] = pts
            self._bbox_derived.discard(si)
            self._refresh_segs(); self._render()
            if hasattr(self, "_auto_all_btn"):
                self._auto_all_btn.config(text=f"🪄 Auto-tách TẤT CẢ bbox ({len(self._bbox_derived)})")
            self._status_var.set(f"Đã auto-tách segment [{si}] bằng {method} — {len(pts)} điểm")
        else:
            self._status_var.set(f"Auto-tách segment [{si}] ({method}): không tách được — thử SAM/CV Box thủ công")
        if self._auto_refine_queue:
            self._auto_refine_next()

    def _push_undo(self):
        """Lưu snapshot _segments TRƯỚC 1 thao tác phá hủy (Auto-tách, xóa, đổi
        class, resize/move, thêm/giảm điểm, dọn seam, thêm segment mới...) để
        Ctrl+Z khôi phục lại được. Giới hạn 30 bước để tránh phình bộ nhớ."""
        import copy
        self._undo_stack.append(copy.deepcopy(self._segments))
        if len(self._undo_stack) > 30:
            self._undo_stack.pop(0)

    def _undo_segments(self) -> bool:
        if not self._undo_stack:
            return False
        self._segments = self._undo_stack.pop()
        self._sel = min(self._sel, len(self._segments) - 1)
        self._refresh_segs(); self._render()
        self._status_var.set(f"Đã hoàn tác (Ctrl+Z) — còn {len(self._undo_stack)} bước")
        return True

    def _undo_pt(self):
        if self._sam_pts:
            self._sam_pts.pop()
            if self._sam_pts: self._fire_sam(points=self._sam_pts)
            else: self._preview_poly = None; self._render()
        elif self._drawing:
            self._drawing.pop(); self._render()
        else:
            self._undo_segments()

    def _cancel(self):
        self._drawing.clear(); self._cursor = None
        self._sam_pts.clear(); self._preview_poly = None
        self._cv_mask = None; self._cv_edges = None; self._cv_dragging = False; self._cv_seed_si = None
        self._pending_click = None; self._draw_as_sambox = False
        self._box_start = self._box_end = None
        self._render()

    def _load_sam_name(self, name: str):
        self._sam_lbl.config(text=f"Đang tải {name} (lần đầu cần internet)...", fg=ACCENT)
        self.update_idletasks()
        threading.Thread(target=self._do_load_sam, args=(name,), daemon=True).start()

    def _load_sam(self):
        path = filedialog.askopenfilename(title="Chọn SAM model .pt",
            initialdir=str(Path("models")),
            filetypes=[("PyTorch model", "*.pt"), ("All files", "*.*")])
        if path:
            self._load_sam_name(path)

    def _do_load_sam(self, name_or_path: str):
        try:
            from ultralytics import SAM
            model = SAM(name_or_path)
            self._sam_model = model
            label = Path(name_or_path).name
            self.root.after(0, lambda: self._sam_lbl.config(
                text=f"✓ {label}  —  click vào object để tạo segment", fg="#4caf50"))
        except Exception as ex:
            self._sam_model = None
            msg = str(ex)
            self.root.after(0, lambda: self._sam_lbl.config(
                text=f"Lỗi: {msg}", fg="#f44336"))

    def _browse_sam3_dir(self):
        initial = self._sam3_dir_var.get().strip() or _cfg_dir("seg.sam3_model_dir")
        d = filedialog.askdirectory(
            title="Chọn thư mục chứa model SAM3 ONNX (3 file .onnx đã giải nén từ sam3_vit_h.zip)",
            initialdir=initial or None)
        if d:
            self._sam3_dir_var.set(d)
            _push_history("h.seg.sam3_model_dir", d)
            self._sam3_dir_cb["values"] = _get_history("h.seg.sam3_model_dir")

    def _load_sam3_model(self):
        model_dir = self._sam3_dir_var.get().strip()
        if not model_dir:
            self._sam3_lbl.config(
                text="Chưa chọn thư mục model — bấm '📂' để chọn thư mục chứa 3 file .onnx",
                fg="#f44336")
            return
        self._sam3_lbl.config(text="Đang load model SAM 3 (ONNX)...", fg=ACCENT)
        self.update_idletasks()
        threading.Thread(target=self._do_load_sam3, args=(model_dir,), daemon=True).start()

    def _do_load_sam3(self, model_dir: str):
        try:
            model = load_sam3_onnx(model_dir)
            self._sam3_model = model
            self.root.after(0, lambda: self._sam3_lbl.config(
                text="✓ SAM 3 (ONNX) đã load — nhập text prompt rồi bấm Quét ảnh theo prompt "
                     "(chạy CPU sẽ chậm ~30-50s/lần — bình thường với model này)",
                fg="#4caf50"))
        except Exception as ex:
            self._sam3_model = None
            msg = str(ex)
            self.root.after(0, lambda: self._sam3_lbl.config(text=f"Lỗi: {msg}", fg="#f44336"))

    def _label_to_cid(self, label: str) -> int:
        """Map nhãn model text-prompt trả về (tiếng Anh) sang class id trong CLASS_NAMES;
        không khớp được thì dùng class đang chọn ở toolbar làm mặc định."""
        norm = label.strip().lower()
        for cid, name in CLASS_NAMES.items():
            if name.lower().replace("_", " ") == norm or name.lower() == norm:
                return cid
        return self._get_cid()

    def _run_sam3_prompt(self):
        if self._pil_img is None:
            self._status_var.set("Chưa mở ảnh nào"); return
        if self._sam3_model is None:
            self._status_var.set("Chưa load SAM 3 — bấm '📥 Load SAM 3' trước"); return
        if self._sam3_running:
            return
        prompts = [p.strip() for p in self._text_prompt_var.get().split(",") if p.strip()]
        if not prompts:
            self._status_var.set("Nhập ít nhất 1 mô tả (VD: license plate) rồi thử lại"); return
        try:
            conf = float(self._sam3_conf_var.get())
        except (ValueError, TclError):
            conf = 0.5
        self._sam3_running = True
        self._status_var.set(f"Đang quét ảnh theo prompt: {', '.join(prompts)}… "
                             f"(ngưỡng {conf:.2f}, SAM3 CPU chậm, chờ chút)")
        self._canvas.config(cursor="watch")
        img = self._pil_img.copy()
        threading.Thread(target=self._run_sam3_thread, args=(img, prompts, conf), daemon=True).start()

    def _run_sam3_thread(self, img, prompts, conf):
        try:
            detections = run_sam3_text(self._sam3_model, img, prompts, conf=conf)
            self.root.after(0, lambda: self._after_sam3_prompt(detections))
        except Exception as ex:
            msg = str(ex)
            self.root.after(0, lambda: self._after_sam3_prompt(None, msg))

    def _after_sam3_prompt(self, detections, err: str = None):
        self._sam3_running = False
        self._canvas.config(cursor="crosshair")
        if err:
            self._status_var.set(f"SAM 3 lỗi: {err}"); return
        if not detections:
            self._status_var.set("SAM 3: không tìm thấy object nào khớp mô tả — thử mô tả khác"); return
        self._push_undo()
        eps = self._simplify_var.get()
        added = 0
        for label, conf, pts in detections:
            if eps:
                pts = _simplify(pts, eps)
            if len(pts) < 3:
                continue
            cid = self._label_to_cid(label)
            self._segments.append([cid, pts])
            added += 1
        self._sel = len(self._segments) - 1 if added else self._sel
        self._refresh_segs(); self._render()
        self._status_var.set(f"SAM 3: đã thêm {added} segment ({', '.join(d[0] for d in detections)})")

    def _handle_sam_click(self, e):
        self._add_sam_pt(e, label=1)  # positive prompt

    def _fire_sam(self, points=None, box=None):
        if self._sam_model is None:
            messagebox.showwarning("SAM", "Chưa load SAM model.")
            return
        if self._sam_running: return
        self._sam_running = True
        mode_label = "SAM" if points else "SAM Box"
        self._status_var.set(f"{mode_label} đang phân tích...")
        self._canvas.config(cursor="watch")
        img = self._pil_img.copy()
        eps = self._simplify_var.get()
        is_box = box is not None
        threading.Thread(target=self._run_sam_thread,
                         args=(img, points, box, eps, is_box), daemon=True).start()

    def _run_sam_thread(self, img, points, box, eps, is_box):
        try:
            pts = run_sam_box(self._sam_model, img, *box) if is_box \
                  else run_sam_points(self._sam_model, img, points)
            if pts: pts = _simplify(pts, eps)
            self.root.after(0, lambda: self._after_sam(pts or None, is_box))
        except Exception as ex:
            msg = str(ex)
            self.root.after(0, lambda: self._after_sam(None, is_box, msg))

    def _after_sam(self, pts, is_box: bool = False, err: str = None):
        self._sam_running = False
        self._canvas.config(cursor="crosshair")
        if err:
            self._status_var.set(f"SAM lỗi: {err}"); return
        if pts is None:
            self._status_var.set("SAM: không tìm thấy object"); return
        if is_box:
            # Box mode: xác nhận ngay
            self._segments.append([self._get_cid(), pts])
            self._sel = len(self._segments) - 1
            self._refresh_segs(); self._render()
            self._status_var.set(f"SAM Box: đã thêm  ({len(pts)} điểm)")
        else:
            # Click mode: preview, chờ chuột phải để xác nhận
            self._preview_poly = pts
            n_pos = sum(1 for *_, l in self._sam_pts if l == 1)
            n_neg = sum(1 for *_, l in self._sam_pts if l == 0)
            self._render()
            self._status_var.set(
                f"Preview: {len(pts)} điểm  |  ✅{n_pos} ❌{n_neg}  |  "
                "Click thêm để chỉnh  |  Shift+Click loại vùng  |  Chuột phải = xác nhận")

    def _fire_cv_box(self, x1: float, y1: float, x2: float, y2: float):
        """Kéo khung xong (mode CV Box) → chạy GrabCut tự động trong thread,
        không cần người dùng chỉnh bất kỳ tham số nào."""
        self._status_var.set("CV Box đang tự động phân vùng (GrabCut)...")
        self._canvas.config(cursor="watch")
        img = self._pil_img.copy()
        threading.Thread(target=self._run_cv_box_thread,
                         args=(img, x1, y1, x2, y2), daemon=True).start()

    def _run_cv_box_thread(self, img, x1, y1, x2, y2):
        try:
            mask = run_grabcut_box(img, x1, y1, x2, y2)
            self.root.after(0, lambda: self._after_cv_box(mask))
        except Exception as ex:
            msg = str(ex)
            self.root.after(0, lambda: self._after_cv_box(None, msg))

    def _after_cv_box(self, mask, err: str = None):
        self._canvas.config(cursor="crosshair")
        if err:
            self._status_var.set(f"CV Box lỗi: {err}"); return
        if mask is None:
            self._status_var.set(
                "CV Box: không tách được object (nền phức tạp/khung quá lớn) — "
                "thử kéo khung SÁT hơn quanh object, hoặc dùng 🪄 SAM Box (chính xác hơn cho ảnh phức tạp)")
            return
        self._cv_mask = mask
        self._cv_edges = None   # sẽ tính lại nếu người dùng tinh chỉnh thêm bằng CV Edge
        poly = mask_to_polygon(self._cv_mask)
        if not poly:
            self._status_var.set("CV Box: không tạo được polygon từ vùng tách được"); return
        eps = self._simplify_var.get()
        self._preview_poly = _simplify(poly, eps) if eps else poly
        self._render()
        px = int(self._cv_mask.sum() // 255)
        self._status_var.set(
            f"CV Box: {len(self._preview_poly)} điểm  ({px}px)  |  "
            "Chuyển 🌀 CV Edge để tinh chỉnh thêm (kéo=cộng, Shift+kéo=trừ)  |  Chuột phải = xác nhận")

    def _start_cv_drag(self, e, subtract: bool = False):
        """Click đầu tiên: dựng bản đồ biên rồi 'sơn' (hoặc 'tẩy' nếu Shift) vùng
        chứa điểm click. Giữ chuột kéo tiếp (xem `_on_drag`) để gộp/trừ thêm các
        vùng lân cận — giống công cụ Quick Selection / Magic Wand của Photoshop:
        kéo để mở rộng vùng chọn, giữ Shift để trừ bớt phần chọn nhầm."""
        if self._pil_img is None:
            return
        ix, iy = self._c2i(e.x, e.y)
        iw, ih = self._pil_img.size
        if not (0 <= ix <= iw and 0 <= iy <= ih):
            return
        try:
            self._cv_edges = compute_edge_mask(
                self._pil_img, self._cv_blur_var.get(),
                self._cv_low_var.get(), self._cv_high_var.get())
        except Exception as ex:
            self._status_var.set(f"CV Edge lỗi: {ex}"); return
        if self._cv_mask is None or self._cv_mask.shape != self._cv_edges.shape:
            self._cv_mask = empty_mask_like(self._cv_edges)
            self._cv_seed_si = None
            # Nếu đang có 1 segment được chọn (VD: kết quả Auto-tách/SAM Box bị
            # thiếu 1 phần, như bánh xe lẫn vào bóng) -> seed mask từ chính polygon
            # đó, để CV Edge MỞ RỘNG THÊM phần còn thiếu thay vì vẽ đè 1 segment mới.
            if 0 <= self._sel < len(self._segments):
                _, seed_pts = self._segments[self._sel]
                if len(seed_pts) >= 3:
                    self._cv_mask = polygon_to_mask(seed_pts, iw, ih)
                    self._cv_seed_si = self._sel
        self._cv_dragging = True
        self._cv_last_pt = (ix, iy)
        self._grow_cv_mask(ix, iy, subtract=subtract)

    def _grow_cv_mask(self, ix: float, iy: float, subtract: bool = False):
        """Gộp (hoặc trừ) vùng bao kín chứa (ix,iy) khỏi mask tích lũy, cập nhật preview."""
        if self._cv_edges is None:
            return
        m = flood_region_mask(self._cv_edges, ix, iy)
        if m is None or int(m.sum() // 255) < self._cv_minarea_var.get():
            return
        self._cv_mask = (self._cv_mask & (255 - m)) if subtract else (self._cv_mask | m)
        poly = mask_to_polygon(self._cv_mask)
        if not poly:
            self._preview_poly = None
            self._render()
            self._status_var.set("CV Edge: vùng chọn trống — kéo lại vào object để chọn")
            return
        eps = self._simplify_var.get()
        self._preview_poly = _simplify(poly, eps) if eps else poly
        self._render()
        px = int(self._cv_mask.sum() // 255)
        tag = "➖ TRỪ vùng" if subtract else "➕ Cộng vùng"
        self._status_var.set(
            f"CV Edge [{tag}]: {len(self._preview_poly)} điểm  ({px}px)  |  "
            "Kéo=mở rộng  Shift+kéo=trừ  |  Chuột phải=xác nhận  |  Esc=hủy")

    def _is_active(self) -> bool:
        """Trả về True nếu tab Segment đang visible (đang được chọn)."""
        try:
            return self.winfo_ismapped()
        except Exception:
            return False

    def _bind_shortcuts(self):
        """CHỈ bind phím số ở đây — Ctrl+O/S/Z, Delete, Escape, ◀▶ được xử lý qua
        alias method bên dưới để App._global_* (bind trên toplevel, không xung đột)
        dispatch tới, thay vì tự root.bind_all() riêng (dễ bị tab khác tạo SAU ghi
        đè mất, ví dụ WebImageTab cũng bind_all("<Escape>") làm Escape của Segment
        không hoạt động)."""
        for n in range(10):
            self.root.bind_all(f"<Key-{n}>",
                lambda e, n=n: self._on_numkey_label(n) if self._is_active() else None)
        self.root.bind_all("<Key-h>", lambda e: self._toggle_show_segments() if self._is_active() else None)

    def _toggle_show_segments(self):
        self._show_seg_var.set(not self._show_seg_var.get())
        self._render()

    # ── Alias cho App._global_* dispatcher (xem tool/core/app.py) ──────────────
    def _browse(self):        self._browse_dir()
    def _undo(self):          self._undo_pt()
    def _delete_selected(self): self._delete_seg()
    def _stop(self):          self._cancel()

    def _prev_image(self):
        self._save(); self._prev_img()

    def _next_image(self):
        self._save(); self._next_img()
