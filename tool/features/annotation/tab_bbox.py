import math
import os
from pathlib import Path
from tkinter import *
from tkinter import messagebox, ttk

from ...core.constants import BG, CARD, ACCENT, ACCENT2, TEXT, DIM, F_MAIN, F_BOLD, F_MONO, IMAGE_EXTENSIONS
from ...core.settings import _bind_cfg, _bind_history, _push_history, _get_history
from ...core.ui_helpers import _folder_row, GridPageNav


def _lighten_color(hex_color: str, factor: float) -> str:
    """Sáng (factor>0) hoặc tối (factor<0) một màu hex. factor ∈ [-1, 1]."""
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    if factor >= 0:
        r = int(r + (255 - r) * factor)
        g = int(g + (255 - g) * factor)
        b = int(b + (255 - b) * factor)
    else:
        r = int(r * (1 + factor))
        g = int(g * (1 + factor))
        b = int(b * (1 + factor))
    return f"#{max(0,min(255,r)):02x}{max(0,min(255,g)):02x}{max(0,min(255,b)):02x}"


class BBoxEditorTab(Frame):
    _PALETTE = [
        "#F05922", "#4caf50", "#2196f3", "#9c27b0", "#ff9800",
        "#00bcd4", "#e91e63", "#8bc34a", "#ff5722", "#607d8b",
        "#ffeb3b", "#3f51b5", "#009688", "#795548", "#f44336",
    ]

    def __init__(self, master, root):
        super().__init__(master, bg=BG)
        self.root = root

        self.img_dir_var  = StringVar()
        self.lbl_dir_var  = StringVar()
        self._labels_var  = StringVar(
            value="car,motorcycle,bus,truck,bicycle,license_plate")
        self.v_recursive  = BooleanVar(value=False)
        _bind_cfg("bbox.img",    self.img_dir_var)
        _bind_cfg("bbox.lbl",    self.lbl_dir_var)
        _bind_cfg("bbox.labels", self._labels_var)

        self._line_width_var = IntVar(value=3)
        _bind_cfg("bbox.line_width", self._line_width_var)

        self._show_label_var = BooleanVar(value=True)
        self._show_size_var  = BooleanVar(value=True)
        _bind_cfg("bbox.show_label", self._show_label_var)
        _bind_cfg("bbox.show_size",  self._show_size_var)

        self._last_image_var = StringVar()
        _bind_cfg("bbox.last_image", self._last_image_var)
        self._restore_img = ""   # path to jump to after next filter completes
        self._loaded_img_dir  = ""   # folder path của lần load trước
        self._loaded_recursive = False

        self.label_list  = []
        self.image_files = []
        self.current_idx = -1
        self._filtered_files  = []
        self._filter_name_var  = StringVar()
        self._filter_label_var = StringVar(value="Tất cả")
        self._filter_after     = None
        self._filter_gen       = 0          # bumped each call; workers abort on mismatch
        self._filter_unlabeled = BooleanVar(value=False)
        self._present_label_cids: list = []
        self._progress_set:        set  = set()
        self._progress_file:       object = None
        self._filter_progress_var  = StringVar(value="Tất cả")
        self._filter_size_min_var  = StringVar(value="")
        self._filter_size_max_var  = StringVar(value="")
        self._filter_w_min_var     = StringVar(value="")
        self._filter_w_max_var     = StringVar(value="")
        self._filter_h_min_var     = StringVar(value="")
        self._filter_h_max_var     = StringVar(value="")
        self._img_size_cache: dict = {}  # {str(path): (w, h)}

        self._pil_img  = None
        self._tk_img   = None
        self._scale    = 1.0
        self._off_x    = 0
        self._off_y    = 0
        self._hover_idx = -1

        self._bboxes        = []
        self._bbox_attrs    = []   # parallel list of dicts per bbox (condition/occluded/truncated/difficult)
        self._selected      = -1
        self._selected_set  = set()
        self._modified      = False

        self._mode        = StringVar(value="draw")
        self._drawing     = False
        self._draw_start  = (0, 0)
        self._draw_rect   = None
        self._resize_after = None

        self._drag_op        = None
        self._drag_prev      = (0, 0)
        self._drag_press_pos = (0, 0)
        self._drag_committed = True
        self._hide_others    = False  # ẩn bbox khác khi đang vẽ / kéo / resize

        self._rubber_band  = False
        self._rubber_rect  = None
        self._rubber_start = (0, 0)

        # Zoom & pan state (Paint-like canvas zoom)
        self._zoom_level        = 1.0   # multiplier on top of fit-to-canvas scale
        self._pan_x             = 0     # viewport pan offset in canvas pixels
        self._pan_y             = 0
        self._panning           = False # True while middle-mouse is held
        self._pan_start         = (0, 0)
        self._pan_start_offset  = (0, 0)
        self._ctrl_panning      = False # True while Ctrl+left-drag panning
        self._zoom_settle_after = None  # after-ID for LANCZOS quality settle
        self._render_nw_nh      = None  # (nw, nh) of cached _tk_img (pan reuse)

        # Undo/Redo stacks
        self._undo_stack = []
        self._redo_stack = []

        self._copy_count_var = IntVar(value=1)
        self._annot_mode = StringVar(value="bbox")  # "bbox" or "poly4"

        # Chấm 4 điểm
        self._poly_placing       = False  # đang trong quá trình chấm điểm
        self._poly_pts: list     = []     # [(x_img, y_img), ...] đã chấm (0-3 điểm)
        self._poly_prev_items: list = []  # canvas item IDs của preview

        # Grid panel (paginated)
        self._thumb_n_var   = IntVar(value=3)
        self._thumb_w       = 160
        self._thumb_h       = 100
        self._thumb_cache: dict = {}
        self._film_cells: list  = []
        self._film_render_idx   = 0
        self._film_ncols        = 3
        self._film_page         = 0
        self._film_max_page     = 0

        # ── Auto-detect (YOLO / RF-DETR / ONNX) ──────────────────────────
        self._det_model       = None
        self._det_model_type  = "yolo"   # "yolo" | "rfdetr" | "onnx"
        self._det_model_names = {}
        self._det_model_path  = StringVar()
        self._det_conf_var    = DoubleVar(value=0.25)
        self._det_replace_var = BooleanVar(value=False)
        _bind_cfg("bbox.det_model_path", self._det_model_path)
        _bind_cfg("bbox.det_conf",       self._det_conf_var)
        _bind_cfg("bbox.det_replace",    self._det_replace_var)

        # ── Verify (so sánh label với model) ──────────────────────────────
        self._verify_boxes           = []
        self._verify_matched_gt      = set()
        self._verify_matched_det     = set()
        self._verify_gt_iou          = {}   # gi → best IoU achieved (kể cả khi < threshold)
        self._verify_active          = False
        self._verify_iou_var         = DoubleVar(value=0.3)
        self._verify_show_wrong_only = BooleanVar(value=False)
        _bind_cfg("bbox.verify_iou",        self._verify_iou_var)
        _bind_cfg("bbox.verify_wrong_only", self._verify_show_wrong_only)

        # ── Test detect vùng đang zoom (crop vùng hiển thị → detect lại, chỉ xem không ghi) ──
        self._zoomtest_boxes  = []    # [cid, x1, y1, x2, y2, conf] tọa độ ẢNH GỐC
        self._zoomtest_active = False

        # ── Batch Relabel ──────────────────────────────────────────────────
        self._rl_from_var  = StringVar()
        self._rl_to_var    = StringVar()
        self._rl_scope_var = StringVar(value="filtered")

        # ── Batch Add Class ──────────────────────────────────────────────────
        self._batch_state           = "idle"   # idle | auto | review-scanning | review-waiting
        self._batch_cancel_evt      = None     # threading.Event, tạo mới mỗi lần start
        self._batch_review_evt      = None     # threading.Event
        self._batch_review_decision = None     # "apply" | "skip" | "stop"
        self._batch_dst_cid         = -1
        self._batch_preview_boxes   = []       # [(cid, x1, y1, x2, y2), ...] tọa độ ảnh gốc
        self._batch_preview_active  = False
        self._batch_src_class_var   = StringVar()  # combobox class nguồn
        self._batch_dst_label_var   = StringVar()  # entry tên label đích
        # Amendment Phase 4 — biến state mới
        self._batch_src_mode_var      = StringVar(value="model")  # "model" | "folder"
        self._batch_write_mode_var    = StringVar(value="append") # "append" | "replace"
        self._batch_src_label_dir_var = StringVar(value="")
        self._batch_src_class_ids_var = StringVar(value="")
        _bind_cfg("bbox.batch.src_mode",       self._batch_src_mode_var)
        _bind_cfg("bbox.batch.write_mode",     self._batch_write_mode_var)
        _bind_cfg("bbox.batch.src_label_dir",  self._batch_src_label_dir_var)
        _bind_cfg("bbox.batch.src_class_ids",  self._batch_src_class_ids_var)
        # Phase 6 — collapsed state (IntVar: 1=thu gọn, 0=mở rộng; mặc định thu gọn)
        self._batch_collapsed_var = IntVar(value=1)
        _bind_cfg("bbox.batch.collapsed",      self._batch_collapsed_var)

        self._build()
        self.after(200, self._restore_session)

    def _build(self):
        from PIL import Image, ImageTk
        self._PIL_Image   = Image
        self._PIL_ImageTk = ImageTk

        top = Frame(self, bg=CARD, padx=12, pady=10)
        top.pack(fill=X)
        grid = Frame(top, bg=CARD)
        grid.pack(fill=X)

        _folder_row(grid, "Thư mục ảnh :",  self.img_dir_var, 0, bg=CARD, history_key="h.bbox.img")
        _folder_row(grid, "Thư mục label:", self.lbl_dir_var, 1, bg=CARD, history_key="h.bbox.lbl")

        Label(grid, text="Danh sách nhãn:", bg=CARD, fg=DIM,
              font=F_MAIN, width=26, anchor=W).grid(
                  row=2, column=0, sticky=W, pady=5)
        _lbls_combo = ttk.Combobox(grid, textvariable=self._labels_var,
                                    style="Dark.TCombobox", font=F_MAIN)
        _lbls_combo.grid(row=2, column=1, sticky=EW, padx=(8, 8))
        _bind_history("h.bbox.labels", _lbls_combo)
        lbl_btn_row = Frame(grid, bg=CARD)
        lbl_btn_row.grid(row=2, column=2, sticky=W)
        Checkbutton(lbl_btn_row, text="Đệ quy subfolder",
                    variable=self.v_recursive,
                    bg=CARD, fg=TEXT, selectcolor="#16162a",
                    activebackground=CARD, font=F_MAIN).pack(side=LEFT, padx=(0, 8))
        Button(lbl_btn_row, text="  ▶  Tải ảnh",
               command=self._load_dataset,
               bg=ACCENT, fg="white", activebackground="#c04010",
               activeforeground="white", font=F_BOLD,
               relief="flat", padx=14, cursor="hand2").pack(side=LEFT)
        Button(lbl_btn_row, text="🔍 Thiếu label",
               command=self._check_missing_labels,
               bg=ACCENT2, fg="white", activebackground=ACCENT,
               activeforeground="white", font=F_MAIN,
               relief="flat", padx=10, cursor="hand2").pack(side=LEFT, padx=(8, 0))

        main = Frame(self, bg=BG)
        main.pack(fill=BOTH, expand=True, padx=8, pady=6)

        left = Frame(main, bg=CARD, width=260)
        left.pack(side=LEFT, fill=Y, padx=(0, 6))
        left.pack_propagate(False)

        Label(left, text="Danh sách ảnh", bg=CARD, fg=TEXT,
              font=F_BOLD).pack(pady=(8, 2), padx=8, anchor=W)
        self._lbl_imgcount = Label(left, text="—", bg=CARD, fg=DIM, font=F_MAIN)
        self._lbl_imgcount.pack(padx=8, anchor=W)
        self._lbl_labelcount = Label(left, text="", bg=CARD, fg=DIM, font=F_MAIN)
        self._lbl_labelcount.pack(padx=8, anchor=W)

        flt_name = Frame(left, bg=CARD)
        flt_name.pack(fill=X, padx=6, pady=(4, 1))
        Label(flt_name, text="Tên:", bg=CARD, fg=DIM, font=F_MAIN, width=4,
              anchor=W).pack(side=LEFT)
        Entry(flt_name, textvariable=self._filter_name_var,
              bg="#16162a", fg=TEXT, insertbackground=TEXT,
              relief="flat", font=F_MONO, bd=2).pack(side=LEFT, fill=X, expand=True)
        self._filter_name_var.trace_add("write", lambda *_: self._schedule_filter())

        flt_lbl = Frame(left, bg=CARD)
        flt_lbl.pack(fill=X, padx=6, pady=(0, 2))
        Label(flt_lbl, text="Nhãn:", bg=CARD, fg=DIM, font=F_MAIN, width=4,
              anchor=W).pack(side=LEFT)
        self._filter_label_combo = ttk.Combobox(
            flt_lbl, textvariable=self._filter_label_var,
            state="readonly", font=F_MAIN, width=10)
        self._filter_label_combo["values"] = ["Tất cả"]
        self._filter_label_combo.pack(side=LEFT, fill=X, expand=True, padx=(0, 2))
        self._filter_label_combo.bind("<<ComboboxSelected>>",
                                      lambda _: self._apply_filters())
        Button(flt_lbl, text="✕", command=self._clear_filters,
               bg=CARD, fg=DIM, activebackground=CARD,
               font=F_MAIN, relief="flat", cursor="hand2", width=2).pack(side=LEFT)

        # Filter: chỉ hiện ảnh chưa có nhãn
        flt_unlabeled = Frame(left, bg=CARD)
        flt_unlabeled.pack(fill=X, padx=6, pady=(0, 2))
        Checkbutton(flt_unlabeled, text="Chỉ hiện chưa có nhãn",
                    variable=self._filter_unlabeled,
                    bg=CARD, fg=TEXT, selectcolor="#16162a",
                    activebackground=CARD, font=F_MAIN,
                    command=self._apply_filters).pack(side=LEFT, anchor=W)

        # Filter: tiến độ xử lý
        flt_prog = Frame(left, bg=CARD)
        flt_prog.pack(fill=X, padx=6, pady=(0, 2))
        Label(flt_prog, text="Tiến độ:", bg=CARD, fg=DIM, font=F_MAIN,
              width=6, anchor=W).pack(side=LEFT)
        self._filter_progress_combo = ttk.Combobox(
            flt_prog, textvariable=self._filter_progress_var,
            state="readonly", font=F_MAIN, width=10,
            values=["Tất cả", "Đã xử lý", "Chưa xử lý"])
        self._filter_progress_combo.pack(side=LEFT, fill=X, expand=True)
        self._filter_progress_combo.bind("<<ComboboxSelected>>",
                                         lambda _: self._apply_filters())
        self._progress_lbl = Label(left, text="", bg=CARD, fg="#4caf50",
                                   font=F_MAIN, anchor=W)
        self._progress_lbl.pack(fill=X, padx=8, pady=(0, 2))

        # Filter: kích thước bbox (khoảng px²)
        flt_size = Frame(left, bg=CARD)
        flt_size.pack(fill=X, padx=6, pady=(0, 3))
        Label(flt_size, text="BBox px²:", bg=CARD, fg=DIM, font=F_MAIN,
              width=7, anchor=W).pack(side=LEFT)
        Entry(flt_size, textvariable=self._filter_size_min_var,
              bg="#16162a", fg=TEXT, insertbackground=TEXT,
              relief="flat", font=F_MONO, bd=2, width=6).pack(side=LEFT)
        Label(flt_size, text="–", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT, padx=2)
        Entry(flt_size, textvariable=self._filter_size_max_var,
              bg="#16162a", fg=TEXT, insertbackground=TEXT,
              relief="flat", font=F_MONO, bd=2, width=6).pack(side=LEFT)
        self._filter_size_min_var.trace_add("write", lambda *_: self._schedule_filter())
        self._filter_size_max_var.trace_add("write", lambda *_: self._schedule_filter())

        # Filter: bbox width khoảng [min, max] px
        flt_w = Frame(left, bg=CARD)
        flt_w.pack(fill=X, padx=6, pady=(0, 2))
        Label(flt_w, text="BBox W:", bg=CARD, fg=DIM, font=F_MAIN,
              width=7, anchor=W).pack(side=LEFT)
        Entry(flt_w, textvariable=self._filter_w_min_var,
              bg="#16162a", fg=TEXT, insertbackground=TEXT,
              relief="flat", font=F_MONO, bd=2, width=6).pack(side=LEFT)
        Label(flt_w, text="–", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT, padx=2)
        Entry(flt_w, textvariable=self._filter_w_max_var,
              bg="#16162a", fg=TEXT, insertbackground=TEXT,
              relief="flat", font=F_MONO, bd=2, width=6).pack(side=LEFT)
        self._filter_w_min_var.trace_add("write", lambda *_: self._schedule_filter())
        self._filter_w_max_var.trace_add("write", lambda *_: self._schedule_filter())

        # Filter: bbox height khoảng [min, max] px
        flt_h = Frame(left, bg=CARD)
        flt_h.pack(fill=X, padx=6, pady=(0, 3))
        Label(flt_h, text="BBox H:", bg=CARD, fg=DIM, font=F_MAIN,
              width=7, anchor=W).pack(side=LEFT)
        Entry(flt_h, textvariable=self._filter_h_min_var,
              bg="#16162a", fg=TEXT, insertbackground=TEXT,
              relief="flat", font=F_MONO, bd=2, width=6).pack(side=LEFT)
        Label(flt_h, text="–", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT, padx=2)
        Entry(flt_h, textvariable=self._filter_h_max_var,
              bg="#16162a", fg=TEXT, insertbackground=TEXT,
              relief="flat", font=F_MONO, bd=2, width=6).pack(side=LEFT)
        self._filter_h_min_var.trace_add("write", lambda *_: self._schedule_filter())
        self._filter_h_max_var.trace_add("write", lambda *_: self._schedule_filter())


        # Filter: phải có / không có nhãn (multi-select)
        Frame(left, bg=DIM, height=1).pack(fill=X, padx=6, pady=(0, 3))

        Label(left, text="✔ Phải có nhãn:", bg=CARD, fg=DIM,
              font=F_MAIN, anchor=W).pack(fill=X, padx=6)
        mh_frm = Frame(left, bg=CARD)
        mh_frm.pack(fill=X, padx=6, pady=(1, 2))
        self._must_have_lb = Listbox(mh_frm, bg="#16162a", fg=TEXT,
                                     selectbackground=ACCENT2, selectforeground="white",
                                     font=F_MONO, relief="flat", bd=0,
                                     selectmode=MULTIPLE, height=3,
                                     activestyle="none", exportselection=False)
        mh_sb = Scrollbar(mh_frm, command=self._must_have_lb.yview)
        self._must_have_lb.configure(yscrollcommand=mh_sb.set)
        mh_sb.pack(side=RIGHT, fill=Y)
        self._must_have_lb.pack(fill=X, expand=True)
        self._must_have_lb.bind("<<ListboxSelect>>", lambda _: self._schedule_filter())

        Label(left, text="✕ Không có nhãn:", bg=CARD, fg=DIM,
              font=F_MAIN, anchor=W).pack(fill=X, padx=6, pady=(2, 0))
        mn_frm = Frame(left, bg=CARD)
        mn_frm.pack(fill=X, padx=6, pady=(1, 4))
        self._must_not_lb = Listbox(mn_frm, bg="#16162a", fg=TEXT,
                                    selectbackground="#c62828", selectforeground="white",
                                    font=F_MONO, relief="flat", bd=0,
                                    selectmode=MULTIPLE, height=3,
                                    activestyle="none", exportselection=False)
        mn_sb = Scrollbar(mn_frm, command=self._must_not_lb.yview)
        self._must_not_lb.configure(yscrollcommand=mn_sb.set)
        mn_sb.pack(side=RIGHT, fill=Y)
        self._must_not_lb.pack(fill=X, expand=True)
        self._must_not_lb.bind("<<ListboxSelect>>", lambda _: self._schedule_filter())

        lf = Frame(left, bg=CARD)
        lf.pack(fill=BOTH, expand=True, padx=6, pady=(4, 0))
        self._img_lb = Listbox(lf, bg="#16162a", fg=TEXT,
                               selectbackground=ACCENT2, selectforeground="white",
                               font=F_MONO, relief="flat", bd=0, activestyle="none")
        sb_lb = Scrollbar(lf, command=self._img_lb.yview)
        self._img_lb.configure(yscrollcommand=sb_lb.set)
        sb_lb.pack(side=RIGHT, fill=Y)
        self._img_lb.pack(fill=BOTH, expand=True)
        self._img_lb.bind("<<ListboxSelect>>", self._on_list_select)

        nav = Frame(left, bg=CARD)
        nav.pack(fill=X, padx=6, pady=4)
        Button(nav, text="◀", command=self._prev_img,
               bg=ACCENT2, fg="white", font=F_BOLD,
               relief="flat", cursor="hand2", width=5).pack(side=LEFT)
        Button(nav, text="▶", command=self._next_img,
               bg=ACCENT2, fg="white", font=F_BOLD,
               relief="flat", cursor="hand2", width=5).pack(side=LEFT, padx=(4, 0))
        Button(nav, text="🗑 Xóa", command=self._delete_current_image,
               bg="#c62828", fg="white", activebackground="#8b0000",
               activeforeground="white", font=F_MAIN,
               relief="flat", cursor="hand2").pack(side=RIGHT)

        # ── Nhãn có trong ảnh hiện tại ──
        Frame(left, bg=DIM, height=1).pack(fill=X, padx=6, pady=(0, 2))
        Label(left, text="Nhãn trong ảnh:", bg=CARD, fg=TEXT,
              font=F_BOLD).pack(pady=(4, 1), padx=8, anchor=W)
        pres_frm = Frame(left, bg=CARD)
        pres_frm.pack(fill=X, padx=6, pady=(0, 4))
        self._present_lb = Listbox(pres_frm, bg="#16162a", fg=TEXT,
                                   selectbackground=ACCENT2, selectforeground="white",
                                   font=F_MONO, relief="flat", bd=0,
                                   selectmode=BROWSE, height=7,
                                   activestyle="none", exportselection=False)
        pres_sb = Scrollbar(pres_frm, command=self._present_lb.yview)
        pres_sb_x = Scrollbar(pres_frm, orient=HORIZONTAL, command=self._present_lb.xview)
        self._present_lb.configure(yscrollcommand=pres_sb.set, xscrollcommand=pres_sb_x.set)
        pres_sb.pack(side=RIGHT, fill=Y)
        pres_sb_x.pack(side=BOTTOM, fill=X)
        self._present_lb.pack(fill=BOTH, expand=True)
        self._present_lb.bind("<<ListboxSelect>>", self._on_present_lb_select)

        Label(left, text="Nhãn (class)", bg=CARD, fg=TEXT,
              font=F_BOLD).pack(pady=(4, 2), padx=8, anchor=W)
        self._cls_lb = Listbox(left, bg="#16162a", fg=TEXT,
                               selectbackground=ACCENT2, selectforeground="white",
                               font=F_MONO, relief="flat", bd=0,
                               activestyle="none", height=10, exportselection=False)
        self._cls_lb.pack(fill=X, padx=6, pady=(0, 6))
        self._cls_lb.bind("<<ListboxSelect>>", self._on_cls_select)

        center = Frame(main, bg=BG)
        center.pack(side=LEFT, fill=BOTH, expand=True)

        tb = Frame(center, bg=CARD, pady=5, padx=8)
        tb.pack(fill=X)

        # ── RIGHT side packed FIRST so they anchor to right edge before LEFT items claim space ──
        self._info_lbl = Label(tb, text="", bg=CARD, fg=DIM, font=F_MAIN)
        self._info_lbl.pack(side=RIGHT, padx=8)

        Frame(tb, bg=DIM, width=1).pack(side=RIGHT, fill=Y, padx=(6, 0))
        self._zoom_lbl = Label(tb, text="Fit", bg=CARD, fg="#5a5a7a",
                               font=("Consolas", 9), width=5, cursor="hand2")
        self._zoom_lbl.pack(side=RIGHT)
        self._zoom_lbl.bind("<Button-1>", lambda e: self._zoom_reset())
        Button(tb, text="−", command=lambda: self._zoom_step(0.8),
               bg=CARD, fg=TEXT, font=F_BOLD, relief="flat",
               cursor="hand2", width=2).pack(side=RIGHT)
        Button(tb, text="+", command=lambda: self._zoom_step(1.25),
               bg=CARD, fg=TEXT, font=F_BOLD, relief="flat",
               cursor="hand2", width=2).pack(side=RIGHT, padx=(0, 1))
        Label(tb, text="🔍", bg=CARD, fg=DIM, font=F_MAIN).pack(
            side=RIGHT, padx=(8, 2))

        _spn = Spinbox(tb, from_=1, to=6, textvariable=self._thumb_n_var,
                       width=3, bg="#16162a", fg=TEXT, insertbackground=TEXT,
                       buttonbackground=ACCENT2, relief="flat", font=F_MAIN,
                       command=self._rebuild_filmstrip)
        _spn.bind("<Return>", lambda e: self._rebuild_filmstrip())
        _spn.bind("<FocusOut>", lambda e: self._rebuild_filmstrip())
        _spn.pack(side=RIGHT)
        Label(tb, text="Cột:", bg=CARD, fg=DIM, font=F_MAIN).pack(
            side=RIGHT, padx=(8, 2))

        Frame(tb, bg=DIM, width=1).pack(side=RIGHT, fill=Y, padx=6)
        Checkbutton(tb, text="Kích thước", variable=self._show_size_var,
                    bg=CARD, fg=TEXT, selectcolor="#16162a",
                    activebackground=CARD, font=F_MAIN,
                    command=self._redraw_bboxes_only).pack(side=RIGHT, padx=(2, 0))
        Checkbutton(tb, text="Tên nhãn", variable=self._show_label_var,
                    bg=CARD, fg=TEXT, selectcolor="#16162a",
                    activebackground=CARD, font=F_MAIN,
                    command=self._redraw_bboxes_only).pack(side=RIGHT, padx=(4, 2))
        Label(tb, text="Hiện:", bg=CARD, fg=DIM, font=F_MAIN).pack(
            side=RIGHT, padx=(8, 2))

        Frame(tb, bg=DIM, width=1).pack(side=RIGHT, fill=Y, padx=6)
        _lw_spn = Spinbox(tb, from_=1, to=8, textvariable=self._line_width_var,
                          width=3, bg="#16162a", fg=TEXT, insertbackground=TEXT,
                          buttonbackground=ACCENT2, relief="flat", font=F_MAIN,
                          command=self._render)
        _lw_spn.bind("<Return>",   lambda e: self._render())
        _lw_spn.bind("<FocusOut>", lambda e: self._render())
        _lw_spn.pack(side=RIGHT)
        Label(tb, text="Nét:", bg=CARD, fg=DIM, font=F_MAIN).pack(
            side=RIGHT, padx=(0, 2))

        Frame(tb, bg=DIM, width=1).pack(side=RIGHT, fill=Y, padx=6)
        Radiobutton(tb, text="4 Điểm", variable=self._annot_mode, value="poly4",
                    bg=CARD, fg=TEXT, selectcolor="#16162a",
                    activebackground=CARD, activeforeground=TEXT,
                    font=F_MAIN, cursor="hand2").pack(side=RIGHT, padx=(2, 0))
        Radiobutton(tb, text="BBox", variable=self._annot_mode, value="bbox",
                    bg=CARD, fg=TEXT, selectcolor="#16162a",
                    activebackground=CARD, activeforeground=TEXT,
                    font=F_MAIN, cursor="hand2").pack(side=RIGHT, padx=(4, 2))
        Label(tb, text="Nhãn bằng:", bg=CARD, fg=DIM, font=F_MAIN).pack(
            side=RIGHT, padx=(8, 2))

        # ── LEFT side packed after RIGHT so they fill remaining space ──
        Label(tb, text="⚡ Tự động  (click=chọn · drag=kéo · empty=vẽ  Ctrl+drag=kéo hình)",
              bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT, padx=(0, 8))

        Frame(tb, bg=DIM, width=1).pack(side=LEFT, fill=Y, padx=8)

        Label(tb, text="Nhãn:", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        self._cls_combo = ttk.Combobox(tb, width=18, state="readonly", font=F_MAIN)
        self._cls_combo.pack(side=LEFT, padx=(4, 6))

        self._cls_combo.bind("<<ComboboxSelected>>", self._on_cls_combo_change)
        Button(tb, text="🗑 Xóa bbox (Del)", command=self._delete_selected,
               bg="#c62828", fg="white", activebackground="#8b0000",
               activeforeground="white", font=F_MAIN,
               relief="flat", padx=8, cursor="hand2").pack(side=LEFT, padx=2)

        Frame(tb, bg=DIM, width=1).pack(side=LEFT, fill=Y, padx=8)

        Button(tb, text="💾 Lưu label (Ctrl+S)", command=self._save_labels,
               bg="#2e7d32", fg="white", activebackground="#1b5e20",
               activeforeground="white", font=F_BOLD,
               relief="flat", padx=10, cursor="hand2").pack(side=LEFT, padx=2)

        Label(tb, text="📋 Copy sang", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT, padx=(4, 2))
        Spinbox(tb, from_=1, to=999, textvariable=self._copy_count_var,
                width=4, bg="#16162a", fg=TEXT, insertbackground=TEXT,
                buttonbackground=ACCENT2, relief="flat", font=F_MAIN).pack(side=LEFT)
        Label(tb, text="ảnh tiếp", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT, padx=(2, 0))
        Button(tb, text="▶", command=self._copy_to_next,
               bg=ACCENT2, fg="white", activebackground=ACCENT,
               activeforeground="white", font=F_BOLD,
               relief="flat", padx=6, cursor="hand2").pack(side=LEFT, padx=(4, 2))

        # ── YOLO auto-detect row ──────────────────────────────────────────────
        det_tb = Frame(center, bg=CARD, pady=4, padx=8)
        det_tb.pack(fill=X)

        Label(det_tb, text="🤖 Model:", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)

        # Combobox ô model có viền ACCENT cam (1px)
        _det_border = Frame(det_tb, bg=ACCENT, padx=1, pady=1)
        _det_border.pack(side=LEFT, padx=(4, 0))
        self._det_combo = ttk.Combobox(_det_border, textvariable=self._det_model_path,
                                        width=28, font=F_MAIN)
        self._det_combo.pack()
        _bind_history("h.bbox.det_model", self._det_combo)
        self._det_combo.bind("<Return>", lambda e: self._load_det_model(self._det_model_path.get().strip()))

        Button(det_tb, text="📂", command=self._browse_det_model,
               bg=CARD, fg=TEXT, font=F_MAIN, relief="flat",
               padx=6, cursor="hand2").pack(side=LEFT, padx=(4, 0))

        self._btn_detect = Button(det_tb, text="⚡ Detect",
               command=self._run_detect,
               bg=ACCENT, fg="white", activebackground="#c04010",
               activeforeground="white", font=F_BOLD,
               relief="flat", padx=10, cursor="hand2")
        self._btn_detect.pack(side=LEFT, padx=(6, 0))

        Frame(det_tb, bg=DIM, width=1).pack(side=LEFT, fill=Y, padx=(6, 2))
        self._btn_verify = Button(det_tb, text="🔍 Kiểm tra",
               command=self._run_verify,
               bg=ACCENT2, fg="white", activebackground=ACCENT,
               activeforeground="white", font=F_BOLD,
               relief="flat", padx=10, cursor="hand2")
        self._btn_verify.pack(side=LEFT, padx=(2, 0))
        Label(det_tb, text="IoU≥", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT, padx=(8, 2))
        Entry(det_tb, textvariable=self._verify_iou_var, width=4,
              bg="#16162a", fg=TEXT, insertbackground=TEXT,
              relief="flat", font=F_MONO, bd=2).pack(side=LEFT)
        Button(det_tb, text="✕ Xóa KT", command=self._clear_verify,
               bg=CARD, fg=DIM, activebackground="#333355",
               font=F_MAIN, relief="flat", cursor="hand2").pack(side=LEFT, padx=(4, 0))
        Checkbutton(det_tb, text="Chỉ hiện bbox sai",
                    variable=self._verify_show_wrong_only,
                    bg=CARD, fg=TEXT, selectcolor="#16162a",
                    activebackground=CARD, font=F_MAIN,
                    command=self._on_verify_filter_change).pack(side=LEFT, padx=(6, 0))

        Frame(det_tb, bg=DIM, width=1).pack(side=LEFT, fill=Y, padx=(6, 2))
        self._btn_zoomtest = Button(det_tb, text="🔎 Test vùng zoom",
               command=self._run_zoomtest_detect,
               bg="#8e24aa", fg="white", activebackground="#6a1b9a",
               activeforeground="white", font=F_BOLD,
               relief="flat", padx=10, cursor="hand2")
        self._btn_zoomtest.pack(side=LEFT, padx=(2, 0))
        Button(det_tb, text="➕ Thêm vào label", command=self._commit_zoomtest_to_label,
               bg="#2e7d32", fg="white", activebackground="#1b5e20",
               activeforeground="white", font=F_MAIN, relief="flat",
               padx=8, cursor="hand2").pack(side=LEFT, padx=(2, 0))
        Button(det_tb, text="✕", command=self._clear_zoomtest,
               bg=CARD, fg=DIM, activebackground="#333355",
               font=F_MAIN, relief="flat", cursor="hand2").pack(side=LEFT, padx=(2, 0))

        Label(det_tb, text="Conf:", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT, padx=(10, 2))
        self._det_conf_lbl = Label(det_tb, text=f"{self._det_conf_var.get():.2f}",
                                    bg=CARD, fg=ACCENT, font=F_MONO, width=4)
        self._det_conf_lbl.pack(side=LEFT)
        Scale(det_tb, from_=0.05, to=1.0, resolution=0.05,
              orient=HORIZONTAL, length=120,
              variable=self._det_conf_var,
              command=lambda v: self._det_conf_lbl.config(text=f"{float(v):.2f}"),
              bg=CARD, fg=TEXT, highlightthickness=0,
              troughcolor="#16162a", activebackground=ACCENT,
              relief="flat", bd=0, showvalue=False).pack(side=LEFT, padx=(0, 4))

        Checkbutton(det_tb, text="Thay thế bbox cũ", variable=self._det_replace_var,
                    bg=CARD, fg=TEXT, selectcolor="#16162a",
                    activebackground=CARD, font=F_MAIN).pack(side=LEFT, padx=(6, 0))

        self._det_status_lbl = Label(det_tb, text="", bg=CARD, fg=DIM, font=F_MAIN)
        self._det_status_lbl.pack(side=LEFT, padx=(8, 0))

        self._det_model_lbl = Label(det_tb, text="Chưa load", bg=CARD, fg=DIM, font=F_MAIN)
        self._det_model_lbl.pack(side=RIGHT, padx=(0, 4))

        # ── Batch Relabel toolbar ────────────────────────────────────────────
        rl_tb = Frame(center, bg=CARD, pady=4, padx=8)
        rl_tb.pack(fill=X)

        Label(rl_tb, text="🔄 Đổi nhãn:", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        Label(rl_tb, text="Từ:", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT, padx=(8, 2))
        self._rl_from_combo = ttk.Combobox(rl_tb, textvariable=self._rl_from_var,
                                            state="readonly", font=F_MAIN, width=16)
        self._rl_from_combo.pack(side=LEFT, padx=(0, 4))
        Label(rl_tb, text="→", bg=CARD, fg=ACCENT, font=F_BOLD).pack(side=LEFT, padx=2)
        Label(rl_tb, text="Thành:", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT, padx=(2, 2))
        self._rl_to_combo = ttk.Combobox(rl_tb, textvariable=self._rl_to_var,
                                          state="readonly", font=F_MAIN, width=16)
        self._rl_to_combo.pack(side=LEFT, padx=(0, 8))
        Frame(rl_tb, bg=DIM, width=1).pack(side=LEFT, fill=Y, padx=(0, 6))
        Radiobutton(rl_tb, text="Ảnh hiện tại", variable=self._rl_scope_var, value="current",
                    bg=CARD, fg=TEXT, selectcolor="#16162a",
                    activebackground=CARD, font=F_MAIN).pack(side=LEFT, padx=(0, 4))
        Radiobutton(rl_tb, text="Tất cả đang lọc", variable=self._rl_scope_var, value="filtered",
                    bg=CARD, fg=TEXT, selectcolor="#16162a",
                    activebackground=CARD, font=F_MAIN).pack(side=LEFT, padx=(0, 8))
        Button(rl_tb, text="▶ Đổi nhãn",
               command=self._relabel_batch,
               bg=ACCENT2, fg="white", activebackground=ACCENT,
               activeforeground="white", font=F_BOLD,
               relief="flat", padx=10, cursor="hand2").pack(side=LEFT)
        self._rl_status_lbl = Label(rl_tb, text="", bg=CARD, fg=DIM, font=F_MAIN)
        self._rl_status_lbl.pack(side=LEFT, padx=(10, 0))

        # ── Batch Add Class UI ───────────────────────────────────────────────
        self._build_batch_add_class_ui(center)

        # ── Attribute bar (shows when 1 bbox selected) ──────────────────────
        self._attr_bar = Frame(center, bg=CARD, pady=4, padx=8)
        self._attr_bar.pack(fill=X)

        Label(self._attr_bar, text="📋 Attributes:", bg=CARD, fg=DIM,
              font=F_MAIN).pack(side=LEFT, padx=(0, 8))

        _ATTR_DEFS = [
            ("condition",  "Ánh sáng",  ["ban ngày", "ban đêm", "mưa", "sương mù"]),
            ("occluded",   "Bị che",    ["không", "một phần", "nhiều"]),
            ("truncated",  "Cắt mép",   ["không", "có"]),
            ("difficult",  "Khó NĐ",    ["không", "có"]),
        ]
        self._attr_vars   = {}
        self._attr_combos = {}
        for key, label, opts in _ATTR_DEFS:
            Label(self._attr_bar, text=f"{label}:", bg=CARD, fg=DIM,
                  font=F_MAIN).pack(side=LEFT, padx=(6, 2))
            var = StringVar(value=opts[0])
            cb  = ttk.Combobox(self._attr_bar, textvariable=var,
                               values=opts, state="readonly",
                               font=F_MAIN, width=8)
            cb.pack(side=LEFT, padx=(0, 4))
            cb.bind("<<ComboboxSelected>>",
                    lambda e, k=key: self._on_attr_change(k))
            self._attr_vars[key]   = var
            self._attr_combos[key] = cb
        self._attr_hint = Label(self._attr_bar, text="← chọn bbox để chỉnh",
                                bg=CARD, fg="#5a5a7a", font=F_MAIN)
        self._attr_hint.pack(side=LEFT, padx=(10, 0))
        self._set_attr_bar_state("disabled")

        # Horizontal split: canvas left | grid right
        from tkinter import PanedWindow as _PW
        paned = _PW(center, orient=HORIZONTAL, sashwidth=5,
                    bg="#0d0d1e", sashrelief=RAISED, bd=0)
        paned.pack(fill=BOTH, expand=True, pady=(6, 0))

        cf = Frame(paned, bg="#111122", relief=SUNKEN, bd=1)
        paned.add(cf, minsize=300, stretch="always")
        self._canvas = Canvas(cf, bg="#111122", cursor="crosshair",
                              highlightthickness=0)
        self._canvas.pack(fill=BOTH, expand=True)
        self._canvas.bind("<Double-Button-1>", self._on_canvas_zoom)

        self._film_outer = Frame(paned, bg="#0d0d1e")
        paned.add(self._film_outer, minsize=200, stretch="always")

        self._page_nav = GridPageNav(
            self._film_outer,
            on_first=lambda: self._go_page_abs(0),
            on_prev=lambda: self._go_page(-1),
            on_next=lambda: self._go_page(1),
            on_last=lambda: self._go_page_abs(-1),
            on_direct=self._go_page_direct,
            extra_right=[dict(text="🗑 Xóa trang",
                              command=self._delete_page_to_deleted,
                              bg="#c62828", activebackground="#8b0000")],
        )
        self._page_nav.pack(side=BOTTOM, fill=X)

        _grid_area = Frame(self._film_outer, bg="#0d0d1e")
        _grid_area.pack(fill=BOTH, expand=True)

        self._film_canvas = Canvas(_grid_area, bg="#0d0d1e",
                                   highlightthickness=0)
        _film_vsb = Scrollbar(_grid_area, orient=VERTICAL,
                              command=self._film_canvas.yview)
        _film_vsb.pack(side=RIGHT, fill=Y)
        self._film_canvas.config(yscrollcommand=_film_vsb.set)
        self._film_canvas.pack(side=LEFT, fill=BOTH, expand=True)

        self._film_inner = Frame(self._film_canvas, bg="#0d0d1e")
        self._film_canvas_win = self._film_canvas.create_window(
            (0, 0), window=self._film_inner, anchor="nw")

        self._film_inner.bind("<Configure>", lambda e: (
            self._film_canvas.configure(
                scrollregion=self._film_canvas.bbox("all"))))
        self._film_canvas.bind("<Configure>", lambda e: (
            self._film_canvas.itemconfig(
                self._film_canvas_win, width=e.width)))

        def _film_scroll(e):
            self._film_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        self._film_canvas.bind("<MouseWheel>", _film_scroll)
        self._film_inner.bind("<MouseWheel>", _film_scroll)

        self._canvas.bind("<ButtonPress-1>",   self._on_press)
        self._canvas.bind("<B1-Motion>",       self._on_drag)
        self._canvas.bind("<ButtonRelease-1>", self._on_release)
        self._canvas.bind("<Motion>",          self._on_hover)
        self._canvas.bind("<Leave>",           self._on_canvas_leave)
        self._canvas.bind("<Configure>",       self._on_canvas_cfg)
        self._canvas.bind("<Delete>",          lambda e: self._delete_selected())
        self._canvas.bind("<Control-s>",       lambda e: self._save_labels())
        self._canvas.bind("<Return>",          lambda e: self._confirm_and_next())
        self._canvas.bind("<Control-a>",       lambda e: self._select_all())
        self._canvas.bind("<Escape>",          lambda e: self._escape_action())
        self._canvas.bind("<Left>",            lambda e: (self._prev_img(), "break")[-1])
        self._canvas.bind("<Right>",           lambda e: (self._next_img(), "break")[-1])
        self._canvas.bind("<Control-z>",       lambda e: (self._undo(), "break")[-1])
        self._canvas.bind("<Control-y>",       lambda e: (self._redo(), "break")[-1])
        self._canvas.bind("<Control-Z>",       lambda e: (self._redo(), "break")[-1])
        self._canvas.bind("<a>",               lambda e: self._prev_img())
        self._canvas.bind("<d>",               lambda e: self._next_img())
        self._canvas.bind("<c>",               lambda e: self._cycle_class())
        self._canvas.bind("<Control-c>",       lambda e: self._copy_to_next())
        for _k in range(10):
            self._canvas.bind(f"<Key-{_k}>", lambda e, k=_k: self._on_numkey_label(k))
        self._canvas.bind("<MouseWheel>",      self._on_canvas_wheel)
        self._canvas.bind("<ButtonPress-2>",   self._on_pan_start)
        self._canvas.bind("<B2-Motion>",       self._on_pan_drag)
        self._canvas.bind("<ButtonRelease-2>", self._on_pan_end)
        self._canvas.bind("<Control-0>",       lambda e: self._zoom_reset())
        self._canvas.bind("<F5>",              lambda e: self._zoom_reset())
        self._canvas.bind("<Control-equal>",   lambda e: self._zoom_step(1.25))
        self._canvas.bind("<Control-minus>",   lambda e: self._zoom_step(0.8))

        self._img_lb.bind("<Left>",   lambda e: (self._prev_img(), "break")[-1])
        self._img_lb.bind("<Right>",  lambda e: (self._next_img(), "break")[-1])
        self._img_lb.bind("<Return>", lambda e: self._confirm_and_next())

        # Status bar with shortcuts hint
        status_row = Frame(center, bg=BG)
        status_row.pack(fill=X, pady=(4, 0))

        self._status = Label(status_row,
            text="Chọn thư mục ảnh và label, nhập danh sách nhãn rồi nhấn Tải ảnh",
            bg=BG, fg=DIM, font=F_MAIN, anchor=W)
        self._status.pack(side=LEFT, fill=X, expand=True)

        self._shortcut_lbl = Label(status_row,
            text="A/←=trước  D/→=sau  Del=xóa  Ctrl+S=lưu  Enter=lưu+✓  C=class  0-9=đặt nhãn  Ctrl+Z/Y=undo/redo"
                 "  Ctrl+A=all  Ctrl+click=multi  Scroll=zoom  Mid/Ctrl+drag=pan  Ctrl+0=fit",
            bg=BG, fg="#5a5a7a", font=("Segoe UI", 8), anchor=E)
        self._shortcut_lbl.pack(side=RIGHT, padx=6)

    # ── Undo / Redo ────────────────────────────────────────────────────────

    def _snapshot(self):
        import copy
        return (copy.deepcopy(self._bboxes), copy.deepcopy(self._bbox_attrs))

    def _push_undo(self):
        self._undo_stack.append(self._snapshot())
        self._redo_stack.clear()
        self._update_undo_status()

    def _undo(self):
        if not self._undo_stack: return
        self._redo_stack.append(self._snapshot())
        self._bboxes, self._bbox_attrs = self._undo_stack.pop()
        self._selected = -1
        self._selected_set = set()
        self._modified = True
        self._render()
        self._refresh_present_labels()
        self._update_undo_status()
        self._refresh_attr_bar()

    def _redo(self):
        if not self._redo_stack: return
        self._undo_stack.append(self._snapshot())
        self._bboxes, self._bbox_attrs = self._redo_stack.pop()
        self._selected = -1
        self._selected_set = set()
        self._modified = True
        self._render()
        self._refresh_present_labels()
        self._update_undo_status()
        self._refresh_attr_bar()

    def _update_undo_status(self):
        u = len(self._undo_stack)
        r = len(self._redo_stack)
        if u or r:
            self._status.config(
                text=f"Undo: {u}  Redo: {r}  |  {len(self._bboxes)} bbox")

    # ── Keyboard: cycle class ──────────────────────────────────────────────

    def _cycle_class(self):
        vals = list(self._cls_combo["values"])
        if not vals: return
        cur = self._cls_combo.current()
        nxt = (cur + 1) % len(vals)
        self._cls_combo.current(nxt)
        self._cls_lb.selection_clear(0, END)
        self._cls_lb.selection_set(nxt)
        self._cls_lb.see(nxt)
        name = vals[nxt]
        self._status.config(text=f"Class: {name}")

    def _on_numkey_label(self, n: int):
        """Phím số 0-9: chuyển sang class n. Nếu đang chọn bbox, đặt lại nhãn ngay."""
        vals = list(self._cls_combo["values"])
        if not vals or n >= len(vals):
            self._status.config(text=f"Không có class {n}")
            return
        self._cls_combo.current(n)
        self._cls_lb.selection_clear(0, END)
        self._cls_lb.selection_set(n)
        self._cls_lb.see(n)
        name = self.label_list[n] if n < len(self.label_list) else str(n)
        if self._selected_set:
            self._relabel_selected()
        else:
            self._status.config(text=f"Class [{n}:{name}] — click bbox để áp dụng")

    # ── Copy bboxes to next image ──────────────────────────────────────────

    def _copy_to_next(self):
        if not self._filtered_files or self._pil_img is None: return
        if not self._bboxes:
            self._status.config(text="Không có bbox nào để sao chép")
            return
        cur_fi = next((i for i, (ri, _) in enumerate(self._filtered_files)
                       if ri == self.current_idx), -1)
        if cur_fi < 0 or cur_fi >= len(self._filtered_files) - 1:
            self._status.config(text="Không có ảnh tiếp theo để sao chép")
            return

        try:
            count = max(1, int(self._copy_count_var.get()))
        except (ValueError, TypeError):
            count = 1

        lbl_dir = self.lbl_dir_var.get().strip()
        ciw, cih = self._pil_img.size
        import copy as _copy
        nb = len(self._bboxes)
        copied = 0
        last_fi = cur_fi

        for step in range(1, count + 1):
            target_fi = cur_fi + step
            if target_fi >= len(self._filtered_files):
                break
            target_ri = self._filtered_files[target_fi][0]
            target_fp = self.image_files[target_ri]
            target_lbl = (Path(lbl_dir) / (target_fp.stem + ".txt")
                          if lbl_dir else target_fp.parent / (target_fp.stem + ".txt"))
            try:
                lines = []
                for ann in _copy.deepcopy(self._bboxes):
                    cid = ann[0]
                    if len(ann) == 9:
                        _, x1, y1, x2, y2, x3, y3, x4, y4 = ann
                        pts = [x1/ciw, y1/cih, x2/ciw, y2/cih,
                               x3/ciw, y3/cih, x4/ciw, y4/cih]
                        pts = [max(0.0, min(1.0, v)) for v in pts]
                        lines.append(f"{int(cid)} " + " ".join(f"{v:.6f}" for v in pts))
                    else:
                        _, x1, y1, x2, y2 = ann
                        xc = max(0.0, min(1.0, ((x1 + x2) / 2) / ciw))
                        yc = max(0.0, min(1.0, ((y1 + y2) / 2) / cih))
                        bw = max(1e-4, min(1.0, (x2 - x1) / ciw))
                        bh = max(1e-4, min(1.0, (y2 - y1) / cih))
                        lines.append(f"{int(cid)} {xc:.6f} {yc:.6f} {bw:.6f} {bh:.6f}")
                target_lbl.parent.mkdir(parents=True, exist_ok=True)
                with open(target_lbl, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines))
                self._write_attrs_to(self._attrs_path(target_lbl),
                                     _copy.deepcopy(self._bbox_attrs))
                copied += 1
                last_fi = target_fi
            except Exception as e:
                messagebox.showerror("Lỗi sao chép", str(e))
                break

        self._autosave()
        if copied:
            self._img_lb.selection_clear(0, END)
            self._img_lb.selection_set(last_fi)
            self._img_lb.see(last_fi)
            self._load_image(self._filtered_files[last_fi][0])
            self._status.config(
                text=f"Đã sao chép {nb} bbox sang {copied} ảnh tiếp theo")

    # ── Parse label list ──────────────────────────────────────────────────

    def _parse_label_list(self):
        raw = self._labels_var.get().strip()
        return [s.strip() for s in raw.replace("\n", ",").split(",") if s.strip()]

    def _load_dataset(self):
        self.label_list = self._parse_label_list()
        if not self.label_list:
            messagebox.showerror("Lỗi",
                "Vui lòng nhập danh sách nhãn (cách nhau bởi dấu phẩy)."); return
        img_dir = self.img_dir_var.get().strip()
        if not img_dir or not os.path.isdir(img_dir):
            messagebox.showerror("Lỗi", "Vui lòng chọn thư mục ảnh hợp lệ."); return
        same_folder = (img_dir == self._loaded_img_dir and
                       self.v_recursive.get() == self._loaded_recursive)
        if not same_folder:
            self._film_page = 0
        self._thumb_cache.clear()
        self._img_size_cache.clear()

        img_root = Path(img_dir)
        if self.v_recursive.get():
            self.image_files = sorted(
                p for p in img_root.rglob("*")
                if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS)
        else:
            self.image_files = sorted(
                p for p in img_root.iterdir()
                if p.suffix.lower() in IMAGE_EXTENSIONS)

        self._cls_lb.delete(0, END)
        combo_vals = []
        for i, name in enumerate(self.label_list):
            color = self._PALETTE[i % len(self._PALETTE)]
            self._cls_lb.insert(END, f"  [{i}]  {name}")
            self._cls_lb.itemconfig(END, fg=color)
            combo_vals.append(f"{i}: {name}")
        self._cls_combo["values"] = combo_vals
        if combo_vals:
            self._cls_combo.current(0)

        if hasattr(self, "_rl_from_combo"):
            self._rl_from_combo["values"] = combo_vals
            self._rl_to_combo["values"]   = combo_vals
            if combo_vals:
                self._rl_from_var.set(combo_vals[0])
                self._rl_to_var.set(combo_vals[min(1, len(combo_vals) - 1)])

        filter_opts = (["Tất cả", "Không có label"] +
                       [f"{i}: {n}" for i, n in enumerate(self.label_list)])
        self._filter_label_combo["values"] = filter_opts
        self._filter_label_var.set("Tất cả")
        self._filter_name_var.set("")
        self._filter_unlabeled.set(False)
        self._filter_progress_var.set("Tất cả")

        # Load progress file từ label dir hoặc img dir
        lbl_dir = self.lbl_dir_var.get().strip()
        prog_dir = Path(lbl_dir) if lbl_dir else Path(img_dir)
        self._progress_file = prog_dir / ".kztek_progress.json"
        self._load_progress()
        self._update_progress_display()

        self._must_have_lb.delete(0, END)
        self._must_not_lb.delete(0, END)
        for i, name in enumerate(self.label_list):
            color = self._PALETTE[i % len(self._PALETTE)]
            self._must_have_lb.insert(END, f"{i}: {name}")
            self._must_have_lb.itemconfig(END, fg=color)
            self._must_not_lb.insert(END, f"{i}: {name}")
            self._must_not_lb.itemconfig(END, fg=color)

        if not same_folder:
            self.current_idx = -1
        self._loaded_img_dir   = img_dir
        self._loaded_recursive = self.v_recursive.get()
        self._apply_filters()

        if self._filtered_files:
            real_idx = self._filtered_files[0][0]
            self._img_lb.selection_set(0)
            self._load_image(real_idx)

        self._status.config(
            text=f"Đã tải {len(self.image_files)} ảnh  |  {len(self.label_list)} nhãn")

    def _on_list_select(self, _event):
        sel = self._img_lb.curselection()
        if not sel: return
        fi = sel[0]
        if fi >= len(self._filtered_files): return
        real_idx = self._filtered_files[fi][0]
        if real_idx == self.current_idx: return
        self._autosave()
        self._load_image(real_idx)

    def _on_cls_select(self, _event):
        sel = self._cls_lb.curselection()
        if not sel: return
        idx = sel[0]
        if idx < len(self._cls_combo["values"]):
            self._cls_combo.current(idx)
        if self._selected_set:
            self._relabel_selected()

    def _on_cls_combo_change(self, _event):
        """Combo thay đổi → sync cls_lb và tự relabel nếu đang chọn bbox."""
        val = self._cls_combo.get()
        if not val: return
        try:
            idx = int(val.split(":")[0])
            self._cls_lb.selection_clear(0, END)
            self._cls_lb.selection_set(idx)
            self._cls_lb.see(idx)
        except (ValueError, IndexError):
            pass
        if self._selected_set:
            self._relabel_selected()

    def _load_image(self, idx):
        if idx < 0 or idx >= len(self.image_files):
            return
        self.current_idx = idx
        fp = self.image_files[idx]
        try:
            self._pil_img = self._PIL_Image.open(fp).convert("RGB")
        except Exception as e:
            self._status.config(text=f"Lỗi mở ảnh: {e}"); return

        self._bboxes       = []
        self._bbox_attrs   = []
        self._selected     = -1
        self._selected_set = set()
        self._modified     = False
        self._undo_stack   = []
        self._redo_stack   = []
        self._zoom_level         = 1.0
        self._pan_x              = 0
        self._pan_y              = 0
        self._render_nw_nh       = None
        self._verify_boxes       = []
        self._verify_matched_gt  = set()
        self._verify_matched_det = set()
        self._verify_gt_iou      = {}
        self._verify_active      = False
        self._zoomtest_boxes     = []
        self._zoomtest_active    = False
        if self._zoom_settle_after:
            self._canvas.after_cancel(self._zoom_settle_after)
            self._zoom_settle_after = None

        lbl_dir  = self.lbl_dir_var.get().strip()
        lbl_path = (Path(lbl_dir) / (fp.stem + ".txt")
                    if lbl_dir else fp.parent / (fp.stem + ".txt"))
        if lbl_path.exists():
            self._bboxes     = self._read_yolo(lbl_path)
            self._bbox_attrs = self._read_attrs(self._attrs_path(lbl_path), len(self._bboxes))
        else:
            try:
                lbl_path.parent.mkdir(parents=True, exist_ok=True)
                lbl_path.touch()
            except Exception:
                pass

        if len(self._bboxes) == 1:
            self._selected     = 0
            self._selected_set = {0}

        self._render()
        self._refresh_present_labels()
        self._refresh_attr_bar()
        iw, ih = self._pil_img.size
        self._status.config(text=f"{fp.name}   {iw}×{ih}   |   {len(self._bboxes)} bbox")
        self._last_image_var.set(str(fp))
        self._update_filmstrip()

    def _read_yolo(self, path):
        iw, ih = self._pil_img.size
        bboxes = []
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    p = line.strip().split()
                    if len(p) == 5:
                        cid = int(p[0])
                        xc, yc, w, h = map(float, p[1:5])
                        if not all(math.isfinite(v) for v in (xc, yc, w, h)):
                            continue  # bỏ qua dòng có NaN/Inf
                        bboxes.append([cid,
                                       (xc - w / 2) * iw, (yc - h / 2) * ih,
                                       (xc + w / 2) * iw, (yc + h / 2) * ih])
                    elif len(p) == 9:
                        cid = int(p[0])
                        pts = list(map(float, p[1:9]))
                        if not all(math.isfinite(v) for v in pts):
                            continue  # bỏ qua dòng có NaN/Inf
                        bboxes.append([cid,
                                       pts[0]*iw, pts[1]*ih,
                                       pts[2]*iw, pts[3]*ih,
                                       pts[4]*iw, pts[5]*ih,
                                       pts[6]*iw, pts[7]*ih])
        except Exception:
            pass
        return bboxes

    def _write_yolo(self, path):
        iw, ih = self._pil_img.size
        lines  = []
        for ann in self._bboxes:
            cid = ann[0]
            if len(ann) == 9:
                _, x1, y1, x2, y2, x3, y3, x4, y4 = ann
                pts = [x1/iw, y1/ih, x2/iw, y2/ih, x3/iw, y3/ih, x4/iw, y4/ih]
                pts = [max(0.0, min(1.0, v)) for v in pts]
                lines.append(f"{int(cid)} " + " ".join(f"{v:.6f}" for v in pts))
            else:
                _, x1, y1, x2, y2 = ann
                xc  = max(0.0, min(1.0, ((x1 + x2) / 2) / iw))
                yc  = max(0.0, min(1.0, ((y1 + y2) / 2) / ih))
                bw  = max(1e-4, min(1.0, (x2 - x1) / iw))
                bh  = max(1e-4, min(1.0, (y2 - y1) / ih))
                lines.append(f"{int(cid)} {xc:.6f} {yc:.6f} {bw:.6f} {bh:.6f}")
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    # ── Attribute sidecar helpers ──────────────────────────────────────────

    _ATTR_DEFAULTS = {"condition": "ban ngày", "occluded": "không",
                      "truncated": "không", "difficult": "không"}

    def _default_attrs(self) -> dict:
        return dict(self._ATTR_DEFAULTS)

    def _attrs_path(self, lbl_path: Path) -> Path:
        return lbl_path.with_suffix(".attrs.json")

    def _read_attrs(self, path: Path, n_bboxes: int) -> list:
        import json
        result = []
        try:
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    result = [dict(self._ATTR_DEFAULTS, **d)
                              if isinstance(d, dict) else self._default_attrs()
                              for d in data]
        except Exception:
            pass
        while len(result) < n_bboxes:
            result.append(self._default_attrs())
        return result[:n_bboxes]

    def _write_attrs(self, path: Path):
        self._write_attrs_to(path, self._bbox_attrs)

    def _write_attrs_to(self, path: Path, attrs: list):
        import json
        if not attrs or all(d == self._ATTR_DEFAULTS for d in attrs):
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(attrs, ensure_ascii=False, indent=2),
                encoding="utf-8")
        except Exception:
            pass

    # ── Attribute bar helpers ──────────────────────────────────────────────

    def _set_attr_bar_state(self, state: str):
        for cb in self._attr_combos.values():
            cb.configure(state=state)

    def _refresh_attr_bar(self):
        if len(self._selected_set) == 1 and self._selected >= 0:
            idx = self._selected
            # Pad _bbox_attrs nếu bbox này chưa có entry (load từ file cũ)
            while len(self._bbox_attrs) <= idx:
                self._bbox_attrs.append(self._default_attrs())
            d = self._bbox_attrs[idx]
            for key, var in self._attr_vars.items():
                var.set(d.get(key, self._ATTR_DEFAULTS[key]))
            cid  = self._bboxes[idx][0] if idx < len(self._bboxes) else 0
            name = self.label_list[cid] if cid < len(self.label_list) else str(cid)
            self._attr_hint.config(text=f"bbox #{idx}  [{name}]")
            self._set_attr_bar_state("readonly")
            return
        # Reset về mặc định khi không có bbox đơn nào được chọn
        for key, var in self._attr_vars.items():
            var.set(self._ATTR_DEFAULTS[key])
        self._set_attr_bar_state("disabled")
        self._attr_hint.config(text="← chọn bbox để chỉnh")

    def _on_attr_change(self, key: str):
        if self._selected < 0 or not self._selected_set:
            return
        val = self._attr_vars[key].get()
        # Pad nếu cần trước khi ghi
        while len(self._bbox_attrs) <= self._selected:
            self._bbox_attrs.append(self._default_attrs())
        for i in self._selected_set:
            while len(self._bbox_attrs) <= i:
                self._bbox_attrs.append(self._default_attrs())
            self._bbox_attrs[i][key] = val
        self._modified = True

    def _render(self, resample=None):
        if self._pil_img is None: return
        self._canvas.update_idletasks()
        cw = self._canvas.winfo_width()
        ch = self._canvas.winfo_height()
        if cw < 10 or ch < 10:
            self._canvas.after(80, self._render); return

        iw, ih = self._pil_img.size
        fit_scale    = min(cw / iw, ch / ih, 1.0)
        actual_scale = fit_scale * self._zoom_level
        nw, nh       = max(1, int(iw * actual_scale)), max(1, int(ih * actual_scale))
        self._scale  = actual_scale

        base_x = (cw - nw) // 2
        base_y = (ch - nh) // 2
        if self._zoom_level <= 1.0:
            self._pan_x = 0
            self._pan_y = 0
        else:
            limit_x = max(cw // 2, nw // 2)
            limit_y = max(ch // 2, nh // 2)
            self._pan_x = max(-limit_x, min(limit_x, self._pan_x))
            self._pan_y = max(-limit_y, min(limit_y, self._pan_y))
        self._off_x = base_x + self._pan_x
        self._off_y = base_y + self._pan_y

        # Skip PIL resize when size unchanged (pan doesn't change nw/nh)
        if (nw, nh) != self._render_nw_nh:
            _rs = resample if resample is not None else self._PIL_Image.LANCZOS
            resized = self._pil_img.resize((nw, nh), _rs)
            self._tk_img = self._PIL_ImageTk.PhotoImage(resized)
            self._render_nw_nh = (nw, nh)

        self._canvas.delete("all")
        self._canvas.create_image(self._off_x, self._off_y,
                                  anchor=NW, image=self._tk_img)
        self._draw_all_bboxes()
        self._draw_verify_overlay()
        self._draw_zoomtest_overlay()
        self._draw_batch_preview_overlay()

        # Update zoom indicator
        pct = int(actual_scale * 100)
        if hasattr(self, "_zoom_lbl"):
            self._zoom_lbl.config(
                text="Fit" if self._zoom_level == 1.0 else f"{pct}%")

    def _active_label_filter_id(self):
        val = self._filter_label_var.get()
        if not val or val in ("Tất cả", "Không có label"):
            return None
        try:
            return int(val.split(":")[0])
        except (ValueError, IndexError):
            return None

    def _get_visible_indices(self):
        """Trả về set index các bbox đang được hiển thị (qua tất cả filter hiện tại)."""
        only_cid = self._active_label_filter_id()

        def _fv(var):
            v = var.get().strip()
            try: return float(v) if v else None
            except ValueError: return None
        df_smin = _fv(self._filter_size_min_var)
        df_smax = _fv(self._filter_size_max_var)
        df_wmin = _fv(self._filter_w_min_var)
        df_wmax = _fv(self._filter_w_max_var)
        df_hmin = _fv(self._filter_h_min_var)
        df_hmax = _fv(self._filter_h_max_var)
        _dim_on = any(v is not None for v in (df_smin, df_smax, df_wmin, df_wmax, df_hmin, df_hmax))

        visible = set()
        for i, ann in enumerate(self._bboxes):
            cid = ann[0]
            is_poly4 = (len(ann) == 9)
            if only_cid is not None and cid != only_cid:
                continue
            if _dim_on:
                if is_poly4:
                    _, px1, py1, px2, py2, px3, py3, px4, py4 = ann
                    xs = [px1, px2, px3, px4]; ys = [py1, py2, py3, py4]
                    x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)
                else:
                    _, x1, y1, x2, y2 = ann
                bw_px = x2 - x1; bh_px = y2 - y1
                if df_smin is not None and bw_px * bh_px < df_smin: continue
                if df_smax is not None and bw_px * bh_px > df_smax: continue
                if df_wmin is not None and bw_px < df_wmin: continue
                if df_wmax is not None and bw_px > df_wmax: continue
                if df_hmin is not None and bh_px < df_hmin: continue
                if df_hmax is not None and bh_px > df_hmax: continue
            visible.add(i)
        return visible

    def _redraw_bboxes_only(self):
        """Xóa và vẽ lại chỉ bbox — không reload ảnh nền."""
        self._canvas.delete("bbox_item")
        self._canvas.delete("verify_item")
        self._canvas.delete("zoomtest_item")
        self._canvas.delete("batch_preview_item")
        self._draw_all_bboxes()
        self._draw_verify_overlay()
        self._draw_zoomtest_overlay()
        self._draw_batch_preview_overlay()

    def _draw_all_bboxes(self):
        only_cid = self._active_label_filter_id()
        lw = max(1, self._line_width_var.get())
        any_hover = (self._hover_idx >= 0
                     and self._hover_idx != self._selected
                     and self._hover_idx not in self._selected_set)

        def _fv(var):
            v = var.get().strip()
            try: return float(v) if v else None
            except ValueError: return None
        df_smin = _fv(self._filter_size_min_var)
        df_smax = _fv(self._filter_size_max_var)
        df_wmin = _fv(self._filter_w_min_var)
        df_wmax = _fv(self._filter_w_max_var)
        df_hmin = _fv(self._filter_h_min_var)
        df_hmax = _fv(self._filter_h_max_var)
        _dim_on = any(v is not None for v in (df_smin, df_smax, df_wmin, df_wmax, df_hmin, df_hmax))

        # Xác định tập bbox được phép vẽ (ẩn phần còn lại):
        #  - đang vẽ/kéo/resize → chỉ bbox đang thao tác (_selected_set)
        #  - đang hover → chỉ bbox đang hover (+ bbox đang chọn)
        if self._hide_others:
            only_draw = set(self._selected_set)
        elif self._hover_idx >= 0:
            only_draw = set(self._selected_set) | {self._hover_idx}
        else:
            only_draw = None

        _wrong_only = (self._verify_active and self._verify_show_wrong_only.get())

        for i, ann in enumerate(self._bboxes):
            cid = ann[0]
            is_poly4 = (len(ann) == 9)

            if only_draw is not None and i not in only_draw:
                continue

            if only_cid is not None and cid != only_cid:
                continue

            # Ẩn bbox đúng (TP) khi chế độ "chỉ hiện bbox sai" đang bật
            if _wrong_only and i in self._verify_matched_gt:
                continue

            # Tính bounding rect để check filter kích thước
            if is_poly4:
                _, px1, py1, px2, py2, px3, py3, px4, py4 = ann
                if not all(math.isfinite(v) for v in (px1, py1, px2, py2, px3, py3, px4, py4)):
                    print(f"[WARN] Bỏ qua box lỗi (NaN/Inf) tại index {i}")
                    continue
                xs = [px1, px2, px3, px4]; ys = [py1, py2, py3, py4]
                x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)
            else:
                _, x1, y1, x2, y2 = ann
                if not all(math.isfinite(v) for v in (x1, y1, x2, y2)):
                    print(f"[WARN] Bỏ qua box lỗi (NaN/Inf) tại index {i}")
                    continue

            if _dim_on:
                bw_px = x2 - x1; bh_px = y2 - y1
                if df_smin is not None and bw_px * bh_px < df_smin: continue
                if df_smax is not None and bw_px * bh_px > df_smax: continue
                if df_wmin is not None and bw_px < df_wmin: continue
                if df_wmax is not None and bw_px > df_wmax: continue
                if df_hmin is not None and bh_px < df_hmin: continue
                if df_hmax is not None and bh_px > df_hmax: continue

            color      = self._PALETTE[cid % len(self._PALETTE)]
            is_primary = (i == self._selected)
            in_set     = (i in self._selected_set)
            is_hover   = (i == self._hover_idx and not is_primary and not in_set)

            if is_hover:
                draw_color = _lighten_color(color, 0.45)
            elif any_hover and not is_primary and not in_set:
                draw_color = _lighten_color(color, -0.35)
            else:
                draw_color = color

            width = lw + 2 if is_primary else (lw + 1 if (in_set or is_hover) else lw)
            dash  = () if (is_primary or in_set or is_hover) else (5, 3)
            tags  = (f"bb{i}", "bbox_item")
            cls_name = (self.label_list[cid] if cid < len(self.label_list) else str(cid))
            _show_lbl  = self._show_label_var.get()
            _show_size = self._show_size_var.get()
            _parts = [f" {cid}"]
            if _show_lbl:
                _parts.append(f":{cls_name}")
            if _show_size:
                _parts.append(f" {int(x2-x1)}×{int(y2-y1)}")
            _parts.append(" ")
            txt   = "".join(_parts)
            txt_w = max(len(txt) * 7, 30)

            if is_poly4:
                cpts = [
                    int(px1 * self._scale) + self._off_x, int(py1 * self._scale) + self._off_y,
                    int(px2 * self._scale) + self._off_x, int(py2 * self._scale) + self._off_y,
                    int(px3 * self._scale) + self._off_x, int(py3 * self._scale) + self._off_y,
                    int(px4 * self._scale) + self._off_x, int(py4 * self._scale) + self._off_y,
                ]
                self._canvas.create_polygon(cpts, outline=draw_color, fill="",
                                            width=width, dash=dash, tags=tags)
                if is_hover:
                    self._canvas.create_polygon(cpts, fill=draw_color, outline="",
                                                stipple="gray12", tags=tags)
                lx, ly = cpts[0], cpts[1]
                self._canvas.create_rectangle(lx, ly - 17, lx + txt_w, ly,
                                              fill=draw_color, outline="", tags=tags)
                self._canvas.create_text(lx + 3, ly - 8, text=txt, fill="white",
                                         font=("Segoe UI", 8, "bold"), anchor=W, tags=tags)
                if is_primary:
                    hw = 7
                    for k in range(4):
                        hx, hy = cpts[k * 2], cpts[k * 2 + 1]
                        self._canvas.create_rectangle(
                            hx - hw, hy - hw, hx + hw, hy + hw,
                            fill=color, outline="white", width=1, tags=tags)
            else:
                cx1 = int(x1 * self._scale) + self._off_x
                cy1 = int(y1 * self._scale) + self._off_y
                cx2 = int(x2 * self._scale) + self._off_x
                cy2 = int(y2 * self._scale) + self._off_y

                self._canvas.create_rectangle(cx1, cy1, cx2, cy2,
                                              outline=draw_color,
                                              width=width, dash=dash, tags=tags)
                if is_hover:
                    self._canvas.create_rectangle(cx1 + 1, cy1 + 1, cx2 - 1, cy2 - 1,
                                                  fill=draw_color, stipple="gray12",
                                                  outline="", tags=tags)
                self._canvas.create_rectangle(cx1, cy1 - 17, cx1 + txt_w, cy1,
                                              fill=draw_color, outline="", tags=tags)
                self._canvas.create_text(cx1 + 3, cy1 - 8, text=txt, fill="white",
                                         font=("Segoe UI", 8, "bold"),
                                         anchor=W, tags=tags)
                if is_primary:
                    hw = 7
                    mx, my = (cx1 + cx2) // 2, (cy1 + cy2) // 2
                    for hx, hy in [(cx1, cy1), (cx2, cy1), (cx1, cy2), (cx2, cy2)]:
                        self._canvas.create_rectangle(
                            hx - hw, hy - hw, hx + hw, hy + hw,
                            fill=color, outline="white", width=1, tags=tags)
                    for hx, hy, fw, fh in [(mx, cy1, hw+3, hw-3), (mx, cy2, hw+3, hw-3),
                                            (cx1, my, hw-3, hw+3), (cx2, my, hw-3, hw+3)]:
                        self._canvas.create_rectangle(
                            hx - fw, hy - fh, hx + fw, hy + fh,
                            fill=color, outline="white", width=1, tags=tags)

    def _on_canvas_cfg(self, _event):
        if self._resize_after:
            self._canvas.after_cancel(self._resize_after)
        self._resize_after = self._canvas.after(120, self._render)

    def _img_coords(self, cx, cy):
        return ((cx - self._off_x) / self._scale,
                (cy - self._off_y) / self._scale)

    def _hit_test_all(self, cx, cy):
        visible = self._get_visible_indices()
        hits = []
        for i, ann in enumerate(self._bboxes):
            if i not in visible:
                continue
            if len(ann) == 9:
                _, px1, py1, px2, py2, px3, py3, px4, py4 = ann
                xs = [px1, px2, px3, px4]; ys = [py1, py2, py3, py4]
                bx1 = int(min(xs) * self._scale) + self._off_x
                by1 = int(min(ys) * self._scale) + self._off_y
                bx2 = int(max(xs) * self._scale) + self._off_x
                by2 = int(max(ys) * self._scale) + self._off_y
            else:
                _, x1, y1, x2, y2 = ann
                bx1 = int(x1 * self._scale) + self._off_x
                by1 = int(y1 * self._scale) + self._off_y
                bx2 = int(x2 * self._scale) + self._off_x
                by2 = int(y2 * self._scale) + self._off_y
            if bx1 <= cx <= bx2 and by1 <= cy <= by2:
                hits.append(i)
        return hits

    def _cycle_at(self, cx, cy):
        hits = self._hit_test_all(cx, cy)
        if not hits:
            self._selected = -1
        elif self._selected in hits:
            self._selected = hits[(hits.index(self._selected) - 1) % len(hits)]
        else:
            self._selected = hits[-1]
        self._selected_set = {self._selected} if self._selected >= 0 else set()
        self._render()
        self._update_info_lbl()

    _HIT_R = 9

    def _handle_hit(self, cx, cy, idx):
        ann = self._bboxes[idx]
        r = self._HIT_R
        if len(ann) == 9:
            _, px1, py1, px2, py2, px3, py3, px4, py4 = ann
            pts = [(px1, py1), (px2, py2), (px3, py3), (px4, py4)]
            for k, (px, py) in enumerate(pts):
                hx = int(px * self._scale) + self._off_x
                hy = int(py * self._scale) + self._off_y
                if abs(cx - hx) <= r and abs(cy - hy) <= r:
                    return f"poly_{k}"
            return None
        else:
            _, x1, y1, x2, y2 = ann
            bx1 = int(x1 * self._scale) + self._off_x
            by1 = int(y1 * self._scale) + self._off_y
            bx2 = int(x2 * self._scale) + self._off_x
            by2 = int(y2 * self._scale) + self._off_y
            mx, my = (bx1 + bx2) // 2, (by1 + by2) // 2
            for op, (hx, hy) in [("resize_NW", (bx1, by1)), ("resize_NE", (bx2, by1)),
                                   ("resize_SW", (bx1, by2)), ("resize_SE", (bx2, by2))]:
                if abs(cx - hx) <= r and abs(cy - hy) <= r: return op
            for op, (hx, hy) in [("resize_N", (mx, by1)), ("resize_S", (mx, by2)),
                                   ("resize_W", (bx1, my)), ("resize_E", (bx2, my))]:
                if abs(cx - hx) <= r and abs(cy - hy) <= r: return op
            return None

    def _op_cursor(self, op):
        if op and op.startswith("poly_"):
            return "fleur"
        return ("size_nw_se"        if op in ("resize_NW", "resize_SE") else
                "size_ne_sw"        if op in ("resize_NE", "resize_SW") else
                "sb_v_double_arrow" if op in ("resize_N",  "resize_S")  else
                "sb_h_double_arrow" if op in ("resize_W",  "resize_E")  else "crosshair")

    def _on_hover(self, event):
        visible = self._get_visible_indices()
        # Show resize cursor for selected bbox handles (only if selected is visible)
        if self._selected >= 0 and self._selected in visible:
            op = self._handle_hit(event.x, event.y, self._selected)
            if op:
                self._canvas.config(cursor=self._op_cursor(op))
                return
        # Show resize cursor if hovering over any visible bbox handle
        for i in sorted(visible, reverse=True):
            op = self._handle_hit(event.x, event.y, i)
            if op:
                self._canvas.config(cursor=self._op_cursor(op))
                return
        # Show move cursor over any visible bbox body + highlight hovered bbox
        hits = self._hit_test_all(event.x, event.y)
        ctrl = bool(event.state & 0x4)
        self._canvas.config(cursor="fleur" if hits else ("fleur" if ctrl else "crosshair"))
        new_hover = hits[-1] if hits else -1
        if new_hover != self._hover_idx:
            self._hover_idx = new_hover
            self._redraw_bboxes_only()

    def _on_canvas_leave(self, event):
        if self._hover_idx != -1:
            self._hover_idx = -1
            self._redraw_bboxes_only()

    def _on_press(self, event):
        if self._pil_img is None: return
        self._canvas.focus_set()
        cx, cy = event.x, event.y
        ctrl = bool(event.state & 0x4)

        if not ctrl:
            # Priority 1: resize handles on visible bboxes only (topmost first)
            _visible = self._get_visible_indices()
            for i in sorted(_visible, reverse=True):
                op = self._handle_hit(cx, cy, i)
                if op:
                    if i != self._selected or i not in self._selected_set:
                        self._selected = i
                        self._selected_set = {i}
                        self._render()
                    self._push_undo()
                    self._drag_op = op
                    self._drag_prev = (cx, cy)
                    self._drag_committed = True
                    return

        # Priority 2: bbox body (select + move candidate)
        hits = self._hit_test_all(cx, cy)

        if hits:
            top = hits[-1]
            if ctrl:
                if top in self._selected_set:
                    self._selected_set.discard(top)
                    self._selected = (max(self._selected_set)
                                      if self._selected_set else -1)
                else:
                    self._selected_set.add(top)
                    self._selected = top
                self._render()
                self._update_info_lbl()
            else:
                if top not in self._selected_set:
                    self._selected = top
                    self._selected_set = {top}
                    self._render()
                    self._update_info_lbl()
                else:
                    self._selected = top
                self._push_undo()
                self._drag_op        = "move"
                self._drag_press_pos = (cx, cy)
                self._drag_prev      = (cx, cy)
                self._drag_committed = (len(self._selected_set) > 1)
        else:
            # Priority 3: empty area
            if ctrl:
                # Ctrl+drag on empty area = pan canvas
                self._ctrl_panning = True
                self._pan_start = (cx, cy)
                self._pan_start_offset = (self._pan_x, self._pan_y)
                self._canvas.config(cursor="fleur")
            else:
                # Deselect then draw new bbox
                self._selected = -1
                self._selected_set = set()
                self._render()
                self._update_info_lbl()
                self._drawing    = True
                self._draw_start = (cx, cy)
                self._hide_others = True
                self._canvas.delete("bbox_item")   # ẩn các bbox khác khi đang vẽ
                self._draw_rect  = self._canvas.create_rectangle(
                    cx, cy, cx, cy, outline=ACCENT,
                    width=max(2, self._line_width_var.get()), dash=(4, 2))

    _DRAG_THRESHOLD = 5

    def _on_drag(self, event):
        if self._drag_op and self._selected >= 0:
            cx, cy = event.x, event.y
            if not self._drag_committed:
                px0, py0 = self._drag_press_pos
                if ((cx - px0) ** 2 + (cy - py0) ** 2) ** 0.5 < self._DRAG_THRESHOLD:
                    return
                self._drag_committed = True
                self._drag_prev = (cx, cy)
                return
            px, py = self._drag_prev
            self._drag_prev = (cx, cy)
            self._hide_others = True
            self._apply_drag((cx - px) / self._scale,
                             (cy - py) / self._scale)
        elif self._ctrl_panning:
            dx = event.x - self._pan_start[0]
            dy = event.y - self._pan_start[1]
            self._pan_x = self._pan_start_offset[0] + dx
            self._pan_y = self._pan_start_offset[1] + dy
            self._render()
        elif self._rubber_band and self._rubber_rect:
            x0, y0 = self._rubber_start
            self._canvas.coords(self._rubber_rect, x0, y0, event.x, event.y)
        elif self._drawing and self._draw_rect:
            x0, y0 = self._draw_start
            self._canvas.coords(self._draw_rect, x0, y0, event.x, event.y)

    def _apply_drag(self, dx, dy):
        bb = self._bboxes[self._selected]
        iw, ih = self._pil_img.size
        op = self._drag_op
        if op == "move" and len(self._selected_set) > 1:
            for i in self._selected_set:
                b = self._bboxes[i]
                if len(b) == 9:
                    for k in range(4):
                        b[1 + k*2] = max(0.0, min(float(iw), b[1 + k*2] + dx))
                        b[2 + k*2] = max(0.0, min(float(ih), b[2 + k*2] + dy))
                else:
                    w = b[3] - b[1]; h = b[4] - b[2]
                    nx1 = max(0.0, min(float(iw) - w, b[1] + dx))
                    ny1 = max(0.0, min(float(ih) - h, b[2] + dy))
                    b[1] = nx1; b[2] = ny1; b[3] = nx1 + w; b[4] = ny1 + h
        elif op == "move":
            if len(bb) == 9:
                for k in range(4):
                    bb[1 + k*2] = max(0.0, min(float(iw), bb[1 + k*2] + dx))
                    bb[2 + k*2] = max(0.0, min(float(ih), bb[2 + k*2] + dy))
            else:
                w = bb[3] - bb[1]; h = bb[4] - bb[2]
                nx1 = max(0.0, min(float(iw) - w, bb[1] + dx))
                ny1 = max(0.0, min(float(ih) - h, bb[2] + dy))
                bb[1] = nx1; bb[2] = ny1; bb[3] = nx1 + w; bb[4] = ny1 + h
        elif op and op.startswith("poly_"):
            k = int(op[5:])
            xi = 1 + k * 2; yi = 2 + k * 2
            bb[xi] = max(0.0, min(float(iw), bb[xi] + dx))
            bb[yi] = max(0.0, min(float(ih), bb[yi] + dy))
        elif op == "resize_NW":
            bb[1] = max(0.0, min(bb[3]-1.0, bb[1]+dx))
            bb[2] = max(0.0, min(bb[4]-1.0, bb[2]+dy))
        elif op == "resize_NE":
            bb[3] = min(float(iw), max(bb[1]+1.0, bb[3]+dx))
            bb[2] = max(0.0, min(bb[4]-1.0, bb[2]+dy))
        elif op == "resize_SW":
            bb[1] = max(0.0, min(bb[3]-1.0, bb[1]+dx))
            bb[4] = min(float(ih), max(bb[2]+1.0, bb[4]+dy))
        elif op == "resize_SE":
            bb[3] = min(float(iw), max(bb[1]+1.0, bb[3]+dx))
            bb[4] = min(float(ih), max(bb[2]+1.0, bb[4]+dy))
        elif op == "resize_N":
            bb[2] = max(0.0, min(bb[4]-1.0, bb[2]+dy))
        elif op == "resize_S":
            bb[4] = min(float(ih), max(bb[2]+1.0, bb[4]+dy))
        elif op == "resize_W":
            bb[1] = max(0.0, min(bb[3]-1.0, bb[1]+dx))
        elif op == "resize_E":
            bb[3] = min(float(iw), max(bb[1]+1.0, bb[3]+dx))
        self._modified = True
        self._redraw_bboxes_only()

    def _on_release(self, event):
        if self._ctrl_panning:
            self._ctrl_panning = False
            self._canvas.config(cursor="crosshair")
            return
        if self._rubber_band:
            self._rubber_band = False
            if self._rubber_rect:
                self._canvas.delete(self._rubber_rect)
                self._rubber_rect = None
            x0, y0 = self._rubber_start
            rx1, ry1 = min(x0, event.x), min(y0, event.y)
            rx2, ry2 = max(x0, event.x), max(y0, event.y)
            ctrl = bool(event.state & 0x4)
            if not ctrl:
                self._selected_set = set()
            if (rx2 - rx1) >= 4 and (ry2 - ry1) >= 4:
                _visible = self._get_visible_indices()
                for i, ann in enumerate(self._bboxes):
                    if i not in _visible:
                        continue
                    if len(ann) == 9:
                        _, px1, py1, px2, py2, px3, py3, px4, py4 = ann
                        xs = [px1, px2, px3, px4]; ys = [py1, py2, py3, py4]
                        cx_bb = (sum(xs) / 4) * self._scale + self._off_x
                        cy_bb = (sum(ys) / 4) * self._scale + self._off_y
                    else:
                        _, x1, y1, x2, y2 = ann
                        bx1 = int(x1 * self._scale) + self._off_x
                        by1 = int(y1 * self._scale) + self._off_y
                        bx2 = int(x2 * self._scale) + self._off_x
                        by2 = int(y2 * self._scale) + self._off_y
                        cx_bb = (bx1 + bx2) / 2
                        cy_bb = (by1 + by2) / 2
                    if rx1 <= cx_bb <= rx2 and ry1 <= cy_bb <= ry2:
                        self._selected_set.add(i)
            self._selected = (max(self._selected_set)
                              if self._selected_set else -1)
            self._render()
            self._update_info_lbl()
            return
        if self._drag_op is not None:
            was_committed = self._drag_committed
            self._drag_op        = None
            self._drag_committed = True
            self._hide_others    = False
            if not was_committed:
                # Pop the undo snapshot we pushed on press since no drag happened
                if self._undo_stack:
                    self._undo_stack.pop()
                self._cycle_at(event.x, event.y)
            else:
                # Hiện lại tất cả bbox sau khi kéo/resize xong
                self._redraw_bboxes_only()
                self._update_info_lbl()
            return
        if not self._drawing: return
        self._drawing = False
        self._hide_others = False
        if self._draw_rect:
            self._canvas.delete(self._draw_rect)
            self._draw_rect = None
        x0, y0 = self._draw_start
        x1c = min(x0, event.x); y1c = min(y0, event.y)
        x2c = max(x0, event.x); y2c = max(y0, event.y)
        if (x2c - x1c) < 5 or (y2c - y1c) < 5:
            self._render(); return   # hủy vẽ → hiện lại bbox
        iw, ih = self._pil_img.size
        ix1, iy1 = self._img_coords(x1c, y1c)
        ix2, iy2 = self._img_coords(x2c, y2c)
        ix1 = max(0.0, min(float(iw), ix1)); iy1 = max(0.0, min(float(ih), iy1))
        ix2 = max(0.0, min(float(iw), ix2)); iy2 = max(0.0, min(float(ih), iy2))
        if ix2 <= ix1 or iy2 <= iy1:
            self._render(); return   # hủy vẽ → hiện lại bbox
        cid = self._current_class_id()
        self._push_undo()
        if self._annot_mode.get() == "poly4":
            # TL, TR, BR, BL — 4 góc điều chỉnh độc lập
            self._bboxes.append([cid, ix1, iy1, ix2, iy1, ix2, iy2, ix1, iy2])
            kind = "4điểm"
        else:
            self._bboxes.append([cid, ix1, iy1, ix2, iy2])
            kind = "bbox"
        self._bbox_attrs.append(self._default_attrs())
        self._selected = len(self._bboxes) - 1
        self._selected_set = {self._selected}
        self._modified = True
        self._render()
        self._refresh_present_labels()
        self._update_info_lbl()
        self._refresh_attr_bar()
        name = (self.label_list[cid] if cid < len(self.label_list) else str(cid))
        self._status.config(
            text=f"Đã vẽ {kind}  [{cid}:{name}]  |  {len(self._bboxes)} nhãn tổng")

    def _current_class_id(self):
        val = self._cls_combo.get()
        if val and ":" in val:
            try: return int(val.split(":")[0])
            except ValueError: pass
        return 0

    def _relabel_selected(self):
        if not self._selected_set:
            self._status.config(text="Chưa chọn bbox — click vào bbox rồi đặt nhãn")
            return
        cid = self._current_class_id()
        self._push_undo()
        for i in self._selected_set:
            self._bboxes[i][0] = cid
        self._modified = True
        self._render()
        self._refresh_present_labels()
        name = (self.label_list[cid] if cid < len(self.label_list) else str(cid))
        n = len(self._selected_set)
        self._status.config(
            text=f"Đã đặt nhãn  [{cid}:{name}]  cho {n} bbox")

    def _delete_selected(self):
        if not self._selected_set: return
        self._push_undo()
        for i in sorted(self._selected_set, reverse=True):
            self._bboxes.pop(i)
            if i < len(self._bbox_attrs):
                self._bbox_attrs.pop(i)
        n = len(self._selected_set)
        self._selected     = -1
        self._selected_set = set()
        self._modified     = True
        self._render()
        self._refresh_present_labels()
        self._refresh_attr_bar()
        self._status.config(
            text=f"Đã xóa {n} bbox  |  {len(self._bboxes)} bbox còn lại")

    def _save_labels(self):
        if not self.image_files or self.current_idx < 0 or self._pil_img is None: return
        fp       = self.image_files[self.current_idx]
        lbl_dir  = self.lbl_dir_var.get().strip()
        lbl_path = (Path(lbl_dir) / (fp.stem + ".txt")
                    if lbl_dir else fp.parent / (fp.stem + ".txt"))
        try:
            self._write_yolo(lbl_path)
            self._write_attrs(self._attrs_path(lbl_path))
            self._modified = False
            self._status.config(
                text=f"Đã lưu: {lbl_path}  |  {len(self._bboxes)} bbox")
            self._update_filmstrip()
        except Exception as e:
            messagebox.showerror("Lỗi lưu file", str(e))

    def _autosave(self):
        if self._modified:
            self._save_labels()

    def _update_info_lbl(self):
        n = len(self._selected_set)
        if n == 0:
            self._info_lbl.config(text="")
        elif n == 1 and self._selected >= 0 and self._selected < len(self._bboxes):
            ann  = self._bboxes[self._selected]
            cid  = ann[0]
            name = self.label_list[cid] if cid < len(self.label_list) else str(cid)
            if len(ann) == 9:
                _, px1, py1, px2, py2, px3, py3, px4, py4 = ann
                bw = int(max(px1, px2, px3, px4) - min(px1, px2, px3, px4))
                bh = int(max(py1, py2, py3, py4) - min(py1, py2, py3, py4))
            else:
                _, x1, y1, x2, y2 = ann
                bw, bh = int(x2 - x1), int(y2 - y1)
            self._info_lbl.config(text=f"Đã chọn  [{cid}:{name}]  {bw}×{bh} px")
            for k, v in enumerate(list(self._cls_combo["values"])):
                if v.startswith(f"{cid}:"):
                    self._cls_combo.current(k); break
        else:
            self._info_lbl.config(text=f"Đã chọn  {n} bbox")
        self._refresh_attr_bar()

    def _select_all(self):
        self._selected_set = set(range(len(self._bboxes)))
        self._selected = len(self._bboxes) - 1 if self._bboxes else -1
        self._render()
        self._update_info_lbl()

    def _deselect_all(self):
        self._selected     = -1
        self._selected_set = set()
        self._render()
        self._update_info_lbl()

    def _schedule_filter(self):
        if self._filter_after:
            self.after_cancel(self._filter_after)
        self._filter_after = self.after(300, self._apply_filters)

    def _get_must_have_ids(self) -> set:
        try:
            return {int(self._must_have_lb.get(i).split(":")[0])
                    for i in self._must_have_lb.curselection()}
        except Exception:
            return set()

    def _get_must_not_have_ids(self) -> set:
        try:
            return {int(self._must_not_lb.get(i).split(":")[0])
                    for i in self._must_not_lb.curselection()}
        except Exception:
            return set()

    # ── Progress tracking ─────────────────────────────────────────────────────

    def _progress_key(self, fp) -> str:
        return fp.name

    def _load_progress(self):
        self._progress_set = set()
        if self._progress_file and self._progress_file.exists():
            try:
                import json
                data = json.loads(self._progress_file.read_text(encoding="utf-8"))
                self._progress_set = set(data.get("done", []))
            except Exception:
                pass

    def _save_progress(self):
        if not self._progress_file:
            return
        try:
            import json
            self._progress_file.write_text(
                json.dumps({"done": sorted(self._progress_set)}, ensure_ascii=False, indent=2),
                encoding="utf-8")
        except Exception:
            pass

    def _is_done(self, fp) -> bool:
        return self._progress_key(fp) in self._progress_set

    def _mark_done(self, fp=None):
        if fp is None:
            if self.current_idx < 0 or not self.image_files:
                return
            fp = self.image_files[self.current_idx]
        self._progress_set.add(self._progress_key(fp))
        self._save_progress()
        self._update_progress_display()

    def _toggle_done(self, fp=None):
        if fp is None:
            if self.current_idx < 0 or not self.image_files:
                return
            fp = self.image_files[self.current_idx]
        key = self._progress_key(fp)
        if key in self._progress_set:
            self._progress_set.discard(key)
        else:
            self._progress_set.add(key)
        self._save_progress()
        self._update_progress_display()

    def _update_progress_display(self):
        if not self.image_files:
            self._progress_lbl.config(text="")
            return
        total = len(self.image_files)
        done  = sum(1 for fp in self.image_files if self._is_done(fp))
        pct   = int(done * 100 / total) if total else 0
        bar_w = 10
        filled = int(bar_w * pct / 100)
        bar = "█" * filled + "░" * (bar_w - filled)
        self._progress_lbl.config(
            text=f"{bar} {done}/{total} ({pct}%)",
            fg="#4caf50" if pct == 100 else "#F05922" if pct > 0 else DIM)

    def _refresh_lb_item(self, fi: int):
        """Cập nhật icon ✓/○ và màu cho 1 item trong listbox (không re-filter toàn bộ)."""
        if fi < 0 or fi >= len(self._filtered_files):
            return
        _, fp = self._filtered_files[fi]
        img_root = Path(self.img_dir_var.get().strip())
        done    = self._is_done(fp)
        prefix  = "✓" if done else "○"
        display = (str(fp.relative_to(img_root)) if self.v_recursive.get() else fp.name)
        self._img_lb.delete(fi)
        self._img_lb.insert(fi, f"{prefix} {display}")
        self._img_lb.itemconfig(fi, fg="#4caf50" if done else "#9090b0")
        self._img_lb.selection_set(fi)

    def _confirm_and_next(self):
        """Lưu label, đánh dấu đã xử lý, chuyển sang ảnh tiếp theo."""
        self._save_labels()
        if self.current_idx < 0 or not self.image_files:
            return
        self._mark_done(self.image_files[self.current_idx])
        cur_fi = next((i for i, (ri, _) in enumerate(self._filtered_files)
                       if ri == self.current_idx), -1)
        # Cập nhật icon ngay cho item hiện tại
        self._refresh_lb_item(cur_fi)

        if self._filter_progress_var.get() == "Chưa xử lý":
            # Ảnh vừa xác nhận sẽ biến khỏi filter → rebuild toàn bộ
            self._apply_filters()
            if self._filtered_files:
                self._img_lb.selection_set(0)
                self._img_lb.see(0)
                self._load_image(self._filtered_files[0][0])
        else:
            self._next_img()

    # ── Nhãn trong ảnh ────────────────────────────────────────────────────────

    def _refresh_present_labels(self):
        self._present_lb.delete(0, END)
        self._present_label_cids = []
        if not self._bboxes:
            return
        from collections import defaultdict
        groups: dict = defaultdict(list)
        for ann in self._bboxes:
            cid = ann[0]
            if len(ann) == 9:
                _, px1, py1, px2, py2, px3, py3, px4, py4 = ann
                xs = [px1, px2, px3, px4]; ys = [py1, py2, py3, py4]
                groups[cid].append((max(xs) - min(xs), max(ys) - min(ys)))
            else:
                _, x1, y1, x2, y2 = ann
                groups[cid].append((x2 - x1, y2 - y1))
        for cid in sorted(groups):
            sizes = groups[cid]
            cnt   = len(sizes)
            name  = self.label_list[cid] if cid < len(self.label_list) else str(cid)
            color = self._PALETTE[cid % len(self._PALETTE)]
            avg_w = int(sum(w for w, h in sizes) / cnt)
            avg_h = int(sum(h for w, h in sizes) / cnt)
            area  = avg_w * avg_h
            prefix = "" if cnt == 1 else "~"
            size_hint = f"  {prefix}{avg_w}×{avg_h}={area:,}px²"
            self._present_lb.insert(END, f"  [{cid}] {name}  ×{cnt}{size_hint}")
            self._present_lb.itemconfig(END, fg=color)
            self._present_label_cids.append(cid)

    def _on_present_lb_select(self, _event):
        sel = self._present_lb.curselection()
        if not sel: return
        idx = sel[0]
        if idx >= len(self._present_label_cids): return
        cid = self._present_label_cids[idx]
        self._selected_set = {i for i, b in enumerate(self._bboxes) if b[0] == cid}
        self._selected = max(self._selected_set) if self._selected_set else -1
        self._render()
        self._update_info_lbl()

    # ── Xóa hình hiện tại ─────────────────────────────────────────────────────

    def _delete_current_image(self):
        if not self.image_files or self.current_idx < 0:
            return
        fp = self.image_files[self.current_idx]
        if not messagebox.askyesno(
                "Xóa hình",
                f"Xóa file ảnh và nhãn của:\n{fp.name}\n\nHành động này không thể hoàn tác!",
                icon="warning"):
            return
        lbl_dir  = self.lbl_dir_var.get().strip()
        lbl_path = (Path(lbl_dir) / (fp.stem + ".txt")
                    if lbl_dir else fp.parent / (fp.stem + ".txt"))
        try:
            if lbl_path.exists():
                lbl_path.unlink()
            fp.unlink()
        except Exception as e:
            messagebox.showerror("Lỗi xóa", str(e))
            return

        old_idx = self.current_idx
        self.image_files.pop(old_idx)
        self._thumb_cache.clear()
        self.current_idx = -1
        self._apply_filters()

        if not self.image_files:
            self._pil_img    = None
            self._bboxes     = []
            self._bbox_attrs = []
            self._canvas.delete("all")
            self._refresh_present_labels()
            self._refresh_attr_bar()
            self._status.config(text="Đã xóa — không còn ảnh nào")
            return

        if self._filtered_files:
            best_fi, best_dist = 0, float("inf")
            for fi, (ri, _) in enumerate(self._filtered_files):
                d = abs(ri - old_idx)
                if d < best_dist:
                    best_dist = d; best_fi = fi
            self._img_lb.selection_set(best_fi)
            self._img_lb.see(best_fi)
            self._load_image(self._filtered_files[best_fi][0])
        self._status.config(text=f"Đã xóa {fp.name}")

    def _delete_page_to_deleted(self):
        """Di chuyển tất cả ảnh & label trong trang grid hiện tại vào thư mục 'deleted'."""
        if not self._film_cells:
            messagebox.showinfo("Xóa trang", "Không có ảnh nào trong trang này.")
            return

        page_items = [(cell["real_idx"], self.image_files[cell["real_idx"]])
                      for cell in self._film_cells]
        n = len(page_items)
        if not messagebox.askyesno(
                "Xóa trang",
                f"Di chuyển {n} ảnh (và label tương ứng) trong trang này\n"
                f"vào thư mục 'deleted'?\n\nCó thể khôi phục lại từ thư mục 'deleted'.",
                icon="warning"):
            return

        import shutil
        lbl_dir = self.lbl_dir_var.get().strip()
        moved_paths: set = set()
        errors: list = []

        for ri, fp in page_items:
            try:
                img_del = fp.parent / "deleted"
                img_del.mkdir(parents=True, exist_ok=True)
                shutil.move(str(fp), str(img_del / fp.name))

                lbl_path = (Path(lbl_dir) / (fp.stem + ".txt")
                            if lbl_dir else fp.parent / (fp.stem + ".txt"))
                if lbl_path.exists():
                    lbl_del = (Path(lbl_dir) / "deleted" if lbl_dir
                               else fp.parent / "deleted")
                    lbl_del.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(lbl_path), str(lbl_del / lbl_path.name))

                moved_paths.add(fp)
                self._progress_set.discard(self._progress_key(fp))
            except Exception as e:
                errors.append(f"{fp.name}: {e}")

        if errors:
            messagebox.showerror("Lỗi di chuyển", "\n".join(errors[:5]))

        if not moved_paths:
            return

        old_fp = (self.image_files[self.current_idx]
                  if 0 <= self.current_idx < len(self.image_files) else None)
        self.image_files = [fp for fp in self.image_files if fp not in moved_paths]
        self._thumb_cache.clear()
        self._img_size_cache.clear()
        self._save_progress()

        if old_fp and old_fp not in moved_paths:
            try:
                self.current_idx = self.image_files.index(old_fp)
            except ValueError:
                self.current_idx = -1
        else:
            self.current_idx = -1

        self._apply_filters()

        if self.current_idx < 0:
            if self._filtered_files:
                self._img_lb.selection_set(0)
                self._img_lb.see(0)
                self._load_image(self._filtered_files[0][0])
            else:
                self._pil_img    = None
                self._bboxes     = []
                self._bbox_attrs = []
                self._canvas.delete("all")
                self._refresh_present_labels()
                self._refresh_attr_bar()
                self._status.config(text="Đã di chuyển — không còn ảnh nào")
                return

        self._status.config(
            text=f"Đã di chuyển {len(moved_paths)} ảnh vào thư mục 'deleted'")

    def _clear_filters(self):
        self._filter_name_var.set("")
        self._filter_label_var.set("Tất cả")
        self._filter_unlabeled.set(False)
        self._filter_progress_var.set("Tất cả")
        self._filter_size_min_var.set("")
        self._filter_size_max_var.set("")
        self._filter_w_min_var.set("")
        self._filter_w_max_var.set("")
        self._filter_h_min_var.set("")
        self._filter_h_max_var.set("")
        self._must_have_lb.selection_clear(0, END)
        self._must_not_lb.selection_clear(0, END)
        self._apply_filters()

    # ── Đổi nhãn hàng loạt ───────────────────────────────────────────────────

    def _relabel_batch(self):
        from_val = self._rl_from_var.get().strip()
        to_val   = self._rl_to_var.get().strip()
        if not from_val or not to_val:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn nhãn nguồn và nhãn đích.")
            return
        try:
            from_id = int(from_val.split(":")[0])
            to_id   = int(to_val.split(":")[0])
        except (ValueError, IndexError):
            messagebox.showerror("Lỗi", "Nhãn không hợp lệ.")
            return
        if from_id == to_id:
            messagebox.showwarning("Cảnh báo", "Nhãn nguồn và đích phải khác nhau.")
            return

        scope = self._rl_scope_var.get()
        if scope == "current":
            if self.current_idx < 0 or not self.image_files:
                messagebox.showwarning("Cảnh báo", "Chưa mở ảnh nào.")
                return
            files = [self.image_files[self.current_idx]]
        else:
            files = [fp for _, fp in self._filtered_files]
            if not files:
                messagebox.showwarning("Cảnh báo", "Không có ảnh nào trong bộ lọc hiện tại.")
                return

        from_name = (self.label_list[from_id] if from_id < len(self.label_list) else str(from_id))
        to_name   = (self.label_list[to_id]   if to_id   < len(self.label_list) else str(to_id))
        scope_desc = ("ảnh hiện tại" if scope == "current"
                      else f"{len(files)} ảnh đang lọc")
        if not messagebox.askyesno(
                "Xác nhận đổi nhãn",
                f"Đổi tất cả nhãn:\n"
                f"  [{from_id}: {from_name}]  →  [{to_id}: {to_name}]\n"
                f"trong {scope_desc}?\n\n"
                f"Thao tác sẽ sửa trực tiếp file label (.txt)."):
            return

        lbl_dir = self.lbl_dir_var.get().strip()
        changed_files  = 0
        changed_bboxes = 0

        for fp in files:
            lbl_path = (Path(lbl_dir) / (fp.stem + ".txt")
                        if lbl_dir else fp.parent / (fp.stem + ".txt"))
            if not lbl_path.exists():
                continue
            try:
                raw_lines = lbl_path.read_text(encoding="utf-8").splitlines()
                out_lines  = []
                file_changed = False
                for line in raw_lines:
                    parts = line.strip().split()
                    if not parts:
                        out_lines.append(line)
                        continue
                    try:
                        cid = int(parts[0])
                    except ValueError:
                        out_lines.append(line)
                        continue
                    if cid == from_id:
                        parts[0] = str(to_id)
                        out_lines.append(" ".join(parts))
                        file_changed   = True
                        changed_bboxes += 1
                    else:
                        out_lines.append(line)
                if file_changed:
                    lbl_path.write_text("\n".join(out_lines), encoding="utf-8")
                    changed_files += 1
            except Exception:
                pass

        # Reload ảnh hiện tại nếu bị ảnh hưởng
        if self.current_idx >= 0 and self._pil_img is not None:
            fp = self.image_files[self.current_idx]
            lbl_path = (Path(lbl_dir) / (fp.stem + ".txt")
                        if lbl_dir else fp.parent / (fp.stem + ".txt"))
            if lbl_path.exists():
                self._bboxes     = self._read_yolo(lbl_path)
                self._bbox_attrs = self._read_attrs(
                    self._attrs_path(lbl_path), len(self._bboxes))
            self._modified = False
            self._render()
            self._refresh_present_labels()

        self._thumb_cache.clear()
        self._update_filmstrip()
        msg = (f"✅ [{from_name}] → [{to_name}]  |  "
               f"{changed_bboxes} bbox trong {changed_files} ảnh")
        self._rl_status_lbl.config(text=msg, fg="#4caf50")
        self._status.config(text=msg)

    # ── Kiểm tra ảnh thiếu file label ────────────────────────────────────────

    def _check_missing_labels(self):
        if not self.image_files:
            messagebox.showinfo("Thiếu label", "Chưa tải ảnh — nhấn 'Tải ảnh' trước.")
            return

        lbl_dir = self.lbl_dir_var.get().strip()
        missing = []
        for real_idx, fp in enumerate(self.image_files):
            lbl_path = (Path(lbl_dir) / (fp.stem + ".txt")
                        if lbl_dir else fp.parent / (fp.stem + ".txt"))
            if not lbl_path.exists():
                missing.append((real_idx, fp))

        total = len(self.image_files)
        if not missing:
            messagebox.showinfo(
                "Kiểm tra hoàn tất",
                f"Tất cả {total} ảnh đều có file label.")
            return

        win = Toplevel(self.root)
        win.title(f"Thiếu file label — {len(missing)}/{total} ảnh")
        win.configure(bg=BG)
        win.resizable(True, True)
        win.geometry("540x420")
        win.protocol("WM_DELETE_WINDOW", win.destroy)

        from ...core.constants import F_BOLD as _FB, F_MONO as _FM
        Label(win,
              text=f"⚠  {len(missing)} / {total} ảnh chưa có file label (.txt)",
              bg=BG, fg=ACCENT, font=_FB).pack(pady=(12, 4), padx=12, anchor=W)
        Label(win,
              text="Double-click để nhảy tới ảnh đó",
              bg=BG, fg=DIM, font=F_MAIN).pack(padx=12, anchor=W)

        frm = Frame(win, bg=BG)
        frm.pack(fill=BOTH, expand=True, padx=12, pady=8)
        lb = Listbox(frm, bg="#16162a", fg=TEXT,
                     selectbackground=ACCENT2, selectforeground="white",
                     font=_FM, relief="flat", bd=0, activestyle="none")
        sb = Scrollbar(frm, command=lb.yview)
        lb.configure(yscrollcommand=sb.set)
        sb.pack(side=RIGHT, fill=Y)
        lb.pack(fill=BOTH, expand=True)

        img_root = Path(self.img_dir_var.get().strip())
        for _, fp in missing:
            try:
                display = str(fp.relative_to(img_root))
            except ValueError:
                display = fp.name
            lb.insert(END, display)

        def _jump(e):
            sel = lb.curselection()
            if not sel: return
            real_idx, _ = missing[sel[0]]
            fi = next((i for i, (ri, _) in enumerate(self._filtered_files)
                       if ri == real_idx), -1)
            if fi >= 0:
                self._img_lb.selection_clear(0, END)
                self._img_lb.selection_set(fi)
                self._img_lb.see(fi)
            self._autosave()
            self._load_image(real_idx)
            win.lift()

        lb.bind("<Double-Button-1>", _jump)

        btn_row = Frame(win, bg=BG)
        btn_row.pack(fill=X, padx=12, pady=(0, 10))

        def _filter_missing():
            # Lọc danh sách chính chỉ hiện các ảnh thiếu label
            missing_ri = {ri for ri, _ in missing}
            self._filtered_files = [(ri, fp) for ri, fp in
                                    [(ri, self.image_files[ri]) for ri in sorted(missing_ri)]]
            self._img_lb.delete(0, END)
            for ri, fp in self._filtered_files:
                try:
                    display = str(fp.relative_to(img_root))
                except ValueError:
                    display = fp.name
                self._img_lb.insert(END, f"○ {display}")
                self._img_lb.itemconfig(END, fg="#9090b0")
            n = len(self._filtered_files)
            self._lbl_imgcount.config(text=f"{n} / {total}  ảnh thiếu label")
            if self._filtered_files:
                self._img_lb.selection_set(0)
                self._load_image(self._filtered_files[0][0])
            win.destroy()

        Button(btn_row, text="Lọc danh sách ảnh thiếu label",
               command=_filter_missing,
               bg=ACCENT, fg="white", activebackground="#c04010",
               activeforeground="white", font=F_MAIN,
               relief="flat", padx=10, cursor="hand2").pack(side=LEFT)
        Button(btn_row, text="Đóng",
               command=win.destroy,
               bg=CARD, fg=TEXT, activebackground=ACCENT2,
               activeforeground="white", font=F_MAIN,
               relief="flat", padx=10, cursor="hand2").pack(side=RIGHT)

        win.lift()
        win.focus_set()

    def _apply_filters(self):
        if not self.image_files:
            self._filtered_files = []
            self._lbl_imgcount.config(text="—")
            self._lbl_labelcount.config(text="")
            return

        # Bump generation — any in-flight worker with an older gen will abort
        self._filter_gen += 1
        gen = self._filter_gen

        # Snapshot all filter params on the main thread (thread-safe reads)
        name_q         = self._filter_name_var.get().strip().lower()
        label_q        = self._filter_label_var.get()
        only_unlabeled = self._filter_unlabeled.get()
        prog_q         = self._filter_progress_var.get()
        lbl_dir        = self.lbl_dir_var.get().strip()
        img_root       = Path(self.img_dir_var.get().strip())
        recursive      = self.v_recursive.get()
        must_have      = self._get_must_have_ids()
        must_not       = self._get_must_not_have_ids()

        label_id = None
        if label_q and label_q != "Tất cả":
            if label_q == "Không có label":
                label_id = -2
            else:
                try:
                    label_id = int(label_q.split(":")[0])
                except (ValueError, IndexError):
                    pass

        def _fv(s):
            try: return float(s.strip()) if s.strip() else None
            except ValueError: return None

        size_min = _fv(self._filter_size_min_var.get())
        size_max = _fv(self._filter_size_max_var.get())
        w_min    = _fv(self._filter_w_min_var.get())
        w_max    = _fv(self._filter_w_max_var.get())
        h_min    = _fv(self._filter_h_min_var.get())
        h_max    = _fv(self._filter_h_max_var.get())
        _dim_active = any(v is not None for v in
                          (size_min, size_max, w_min, w_max, h_min, h_max))

        # Immutable snapshots safe to hand off to the worker thread
        image_files   = list(self.image_files)
        progress_snap = frozenset(self._progress_set)
        cache_snap    = dict(self._img_size_cache)

        n = len(image_files)
        self._status.config(text=f"Đang lọc {n:,} ảnh…")
        self._lbl_imgcount.config(text="…")

        import threading

        def _worker():
            result    = []
            new_cache = {}

            for real_idx, fp in enumerate(image_files):
                if self._filter_gen != gen:
                    return  # superseded — abort

                if name_q and name_q not in fp.name.lower():
                    continue

                fname = fp.name
                if prog_q == "Đã xử lý"   and fname not in progress_snap: continue
                if prog_q == "Chưa xử lý" and fname in progress_snap:     continue

                lbl_path = (Path(lbl_dir) / (fp.stem + ".txt")
                            if lbl_dir else fp.parent / (fp.stem + ".txt"))

                if only_unlabeled:
                    try:
                        if lbl_path.exists() and lbl_path.stat().st_size > 0:
                            continue
                    except OSError:
                        pass

                if label_id is not None:
                    if label_id == -2:
                        try:
                            if lbl_path.exists() and lbl_path.stat().st_size > 0:
                                continue
                        except OSError:
                            pass
                    else:
                        try:
                            if not lbl_path.exists():
                                continue
                            found = False
                            with open(lbl_path, encoding="utf-8") as f:
                                for line in f:
                                    parts = line.strip().split()
                                    if parts and int(parts[0]) == label_id:
                                        found = True; break
                            if not found:
                                continue
                        except Exception:
                            continue

                if must_have or must_not:
                    file_cids: set = set()
                    try:
                        if lbl_path.exists():
                            with open(lbl_path, encoding="utf-8") as f:
                                for line in f:
                                    parts = line.strip().split()
                                    if parts:
                                        file_cids.add(int(parts[0]))
                    except Exception:
                        pass
                    if must_have and not must_have.issubset(file_cids): continue
                    if must_not  and must_not.intersection(file_cids):  continue

                if _dim_active:
                    try:
                        if not lbl_path.exists() or lbl_path.stat().st_size == 0:
                            continue
                        key = str(fp)
                        if key in cache_snap:
                            iw, ih = cache_snap[key]
                        else:
                            from PIL import Image as _PILImg
                            with _PILImg.open(fp) as _im:
                                iw, ih = _im.size
                            new_cache[key] = (iw, ih)
                            cache_snap[key] = (iw, ih)
                        if iw == 0 or ih == 0:
                            continue
                        dim_pass = False
                        with open(lbl_path, encoding="utf-8") as f:
                            for line in f:
                                parts = line.strip().split()
                                if len(parts) == 5:
                                    if label_id is not None and label_id >= 0 \
                                            and int(parts[0]) != label_id:
                                        continue
                                    bw = float(parts[3]) * iw
                                    bh = float(parts[4]) * ih
                                elif len(parts) == 9:
                                    if label_id is not None and label_id >= 0 \
                                            and int(parts[0]) != label_id:
                                        continue
                                    xs = [float(parts[k]) * iw for k in (1, 3, 5, 7)]
                                    ys = [float(parts[k]) * ih for k in (2, 4, 6, 8)]
                                    bw = max(xs) - min(xs); bh = max(ys) - min(ys)
                                else:
                                    continue
                                if size_min is not None and bw * bh < size_min: continue
                                if size_max is not None and bw * bh > size_max: continue
                                if w_min    is not None and bw < w_min:          continue
                                if w_max    is not None and bw > w_max:          continue
                                if h_min    is not None and bh < h_min:          continue
                                if h_max    is not None and bh > h_max:          continue
                                dim_pass = True; break
                        if not dim_pass:
                            continue
                    except Exception:
                        continue

                result.append((real_idx, fp))

            if self._filter_gen != gen:
                return  # superseded

            self.after(0, lambda: self._finish_filter(
                result, gen, img_root, recursive, lbl_dir, label_id, new_cache))

        threading.Thread(target=_worker, daemon=True).start()

    def _finish_filter(self, result, gen, img_root, recursive,
                       lbl_dir, label_id, new_cache):
        """Main-thread callback invoked by the filter worker thread."""
        if self._filter_gen != gen:
            return  # superseded by a newer call

        self._img_size_cache.update(new_cache)
        self._filtered_files = result

        total = len(self.image_files)
        shown = len(result)
        self._lbl_imgcount.config(
            text=f"{shown}/{total} ảnh" if shown != total else f"{total} ảnh")
        self._lbl_labelcount.config(text="")

        # Build display strings entirely in-memory (fast)
        progress_set = self._progress_set
        items  = []
        colors = []
        for _, fp in result:
            done = fp.name in progress_set
            try:
                display = str(fp.relative_to(img_root)) if recursive else fp.name
            except ValueError:
                display = fp.name
            items.append(("✓ " if done else "○ ") + display)
            colors.append("#4caf50" if done else "#9090b0")

        lb      = self._img_lb
        cur_idx = self.current_idx

        lb.delete(0, END)
        # Set default fg to gray; only done items get an explicit green itemconfig
        lb.config(fg="#9090b0")

        def _chunk(start: int):
            if self._filter_gen != gen:
                return
            CHUNK = 500
            end   = min(start + CHUNK, len(items))
            if start < end:
                # One Tk round-trip for the whole chunk instead of N Python calls
                lb.tk.call(lb._w, 'insert', 'end', *items[start:end])
                # Only call itemconfig for done (green) items — gray is the default
                for i in range(start, end):
                    if colors[i] == "#4caf50":
                        lb.itemconfig(i, fg="#4caf50")
            if end < len(items):
                self.after(0, lambda: _chunk(end))
            else:
                # All chunks inserted — restore or re-select then rebuild filmstrip
                if self._restore_img:
                    self._do_restore_nav()
                elif cur_idx >= 0:
                    for fi, (ri, _) in enumerate(self._filtered_files):
                        if ri == cur_idx:
                            lb.selection_set(fi)
                            lb.see(fi)
                            break
                self._status.config(
                    text=f"Đã lọc {shown:,} / {total:,} ảnh")
                self.after(50, self._rebuild_filmstrip)

        _chunk(0)

    def _prev_image(self): self._prev_img()
    def _next_image(self): self._next_img()

    def _on_canvas_zoom(self, _event=None):
        if self._pil_img is None:
            return
        from ...core.ui_helpers import _zoom_image_window
        _zoom_image_window(self.root, self._pil_img, "Phóng to ảnh",
                           bboxes=self._bboxes or None,
                           label_names=self.label_list)

    # ── Paint-like canvas zoom & pan ──────────────────────────────────────────

    def _on_canvas_wheel(self, event):
        """Scroll wheel zooms in/out centered at cursor position."""
        if self._pil_img is None:
            return
        cx, cy = event.x, event.y
        # Image coords at cursor before zoom change
        img_x = (cx - self._off_x) / self._scale
        img_y = (cy - self._off_y) / self._scale

        factor = 1.25 if event.delta > 0 else (1.0 / 1.25)
        new_zoom = max(0.1, min(20.0, self._zoom_level * factor))
        if abs(new_zoom - self._zoom_level) < 0.001:
            return

        self._canvas.update_idletasks()
        cw = self._canvas.winfo_width()
        ch = self._canvas.winfo_height()
        iw, ih = self._pil_img.size
        fit_scale = min(cw / iw, ch / ih, 1.0)
        new_scale = fit_scale * new_zoom
        nw = int(iw * new_scale)
        nh = int(ih * new_scale)
        base_x = (cw - nw) // 2
        base_y = (ch - nh) // 2
        # Adjust pan so cursor stays over same image point
        self._pan_x = int(cx - img_x * new_scale - base_x)
        self._pan_y = int(cy - img_y * new_scale - base_y)
        self._zoom_level = new_zoom
        self._render(resample=self._PIL_Image.BILINEAR)
        if self._zoom_settle_after:
            self._canvas.after_cancel(self._zoom_settle_after)

        def _settle():
            self._render_nw_nh = None
            self._render()

        self._zoom_settle_after = self._canvas.after(200, _settle)

    def _zoom_step(self, factor: float):
        """Zoom centered on canvas center (used by +/- buttons)."""
        if self._pil_img is None:
            return
        new_zoom = max(0.1, min(20.0, self._zoom_level * factor))
        if abs(new_zoom - self._zoom_level) < 0.001:
            return
        cw = self._canvas.winfo_width()
        ch = self._canvas.winfo_height()
        iw, ih = self._pil_img.size
        fit_scale = min(cw / iw, ch / ih, 1.0)
        new_scale = fit_scale * new_zoom
        nw = int(iw * new_scale)
        nh = int(ih * new_scale)
        cx, cy = cw // 2, ch // 2
        img_x = (cx - self._off_x) / self._scale
        img_y = (cy - self._off_y) / self._scale
        base_x = (cw - nw) // 2
        base_y = (ch - nh) // 2
        self._pan_x = int(cx - img_x * new_scale - base_x)
        self._pan_y = int(cy - img_y * new_scale - base_y)
        self._zoom_level = new_zoom
        if self._zoom_settle_after:
            self._canvas.after_cancel(self._zoom_settle_after)
            self._zoom_settle_after = None
        self._render_nw_nh = None
        self._render()

    def _zoom_reset(self):
        """Reset zoom to fit-to-canvas (Ctrl+0 or click zoom label)."""
        if self._zoom_settle_after:
            self._canvas.after_cancel(self._zoom_settle_after)
            self._zoom_settle_after = None
        self._zoom_level = 1.0
        self._pan_x = 0
        self._pan_y = 0
        self._render_nw_nh = None
        self._render()

    def _on_pan_start(self, event):
        """Middle-mouse press — begin panning."""
        if self._pil_img is None:
            return
        self._panning = True
        self._pan_start = (event.x, event.y)
        self._pan_start_offset = (self._pan_x, self._pan_y)
        self._canvas.config(cursor="fleur")

    def _on_pan_drag(self, event):
        """Middle-mouse drag — update pan offset."""
        if not self._panning:
            return
        dx = event.x - self._pan_start[0]
        dy = event.y - self._pan_start[1]
        self._pan_x = self._pan_start_offset[0] + dx
        self._pan_y = self._pan_start_offset[1] + dy
        self._render()

    def _on_pan_end(self, event):
        """Middle-mouse release — end panning."""
        self._panning = False
        self._canvas.config(cursor="crosshair")

    def _escape_action(self):
        """Escape: cancel active operation or deselect all."""
        if self._poly_placing:
            self._poly_placing = False
            for iid in self._poly_prev_items:
                self._canvas.delete(iid)
            self._poly_prev_items.clear()
            self._poly_pts.clear()
            self._render()
            return
        if self._drawing:
            self._drawing = False
            self._hide_others = False
            if self._draw_rect:
                self._canvas.delete(self._draw_rect)
                self._draw_rect = None
            self._render()   # hiện lại các bbox đã ẩn khi vẽ
            return
        self._deselect_all()

    def _prev_img(self):
        if not self._filtered_files: return
        cur_fi = next((i for i, (ri, _) in enumerate(self._filtered_files)
                       if ri == self.current_idx), -1)
        if cur_fi <= 0: return
        self._autosave()
        new_fi = cur_fi - 1
        real_idx = self._filtered_files[new_fi][0]
        self._img_lb.selection_clear(0, END)
        self._img_lb.selection_set(new_fi)
        self._img_lb.see(new_fi)
        self._load_image(real_idx)

    def _next_img(self):
        if not self._filtered_files: return
        cur_fi = next((i for i, (ri, _) in enumerate(self._filtered_files)
                       if ri == self.current_idx), -1)
        if cur_fi < 0 or cur_fi >= len(self._filtered_files) - 1: return
        self._autosave()
        new_fi = cur_fi + 1
        real_idx = self._filtered_files[new_fi][0]
        self._img_lb.selection_clear(0, END)
        self._img_lb.selection_set(new_fi)
        self._img_lb.see(new_fi)
        self._load_image(real_idx)

    # ── Session restore ────────────────────────────────────────────────────

    def _restore_session(self):
        """Tự động load lại folder và ảnh cuối cùng khi khởi động app."""
        img_dir = self.img_dir_var.get().strip()
        if not img_dir or not os.path.isdir(img_dir):
            return
        saved = self._last_image_var.get().strip()
        if saved:
            self._restore_img = saved
        self._load_dataset()

    def _do_restore_nav(self):
        """Điều hướng đến self._restore_img sau khi filter hoàn thành."""
        target_str = self._restore_img
        self._restore_img = ""
        if not target_str:
            return
        target = Path(target_str)
        try:
            real_idx = self.image_files.index(target)
        except ValueError:
            if self._filtered_files:
                self._img_lb.selection_set(0)
                self._load_image(self._filtered_files[0][0])
            return
        fi = next((i for i, (ri, _) in enumerate(self._filtered_files)
                   if ri == real_idx), -1)
        if fi < 0:
            if self._filtered_files:
                self._img_lb.selection_set(0)
                self._load_image(self._filtered_files[0][0])
            return
        n_cols   = max(1, min(6, self._thumb_n_var.get()))
        per_page = n_cols * 4
        self._film_page = fi // per_page
        self._img_lb.selection_set(fi)
        self._img_lb.see(fi)
        self._load_image(real_idx)

    # ── Grid filmstrip ─────────────────────────────────────────────────────

    def _label_path_for(self, img_path: Path) -> Path:
        lbl_dir = self.lbl_dir_var.get().strip()
        if lbl_dir:
            return Path(lbl_dir) / (img_path.stem + ".txt")
        return img_path.parent / (img_path.stem + ".txt")

    def _grid_filter_id(self):
        label_q = self._filter_label_var.get()
        if not label_q or label_q == "Tất cả":
            return None
        if label_q == "Không có label":
            return -2
        try:
            return int(label_q.split(":")[0])
        except (ValueError, IndexError):
            return None

    def _render_thumb(self, img_path: Path, tw: int, th: int, filter_id=None):
        from PIL import Image as _Img, ImageTk as _ITk, ImageDraw as _IDraw
        cache_key = (str(img_path), tw, th, filter_id)
        if cache_key in self._thumb_cache:
            return self._thumb_cache[cache_key]
        try:
            img = _Img.open(img_path).convert("RGB")
            iw, ih = img.size
            img.thumbnail((tw, th), _Img.LANCZOS)
            tw2, th2 = img.size

            lbl = self._label_path_for(img_path)
            if lbl.exists() and filter_id != -2:
                draw = _IDraw.Draw(img)
                sx, sy = tw2 / iw, th2 / ih
                with open(lbl, encoding="utf-8") as f:
                    for line in f:
                        p = line.strip().split()
                        if len(p) < 5: continue
                        cid = int(p[0])
                        if filter_id is not None and cid != filter_id:
                            continue
                        xc, yc, bw, bh = map(float, p[1:5])
                        x1 = int((xc - bw / 2) * iw * sx)
                        y1 = int((yc - bh / 2) * ih * sy)
                        x2 = int((xc + bw / 2) * iw * sx)
                        y2 = int((yc + bh / 2) * ih * sy)
                        color = self._PALETTE[cid % len(self._PALETTE)]
                        draw.rectangle([x1, y1, x2, y2], outline=color, width=2)

            tk_img = _ITk.PhotoImage(img)
            self._thumb_cache[cache_key] = tk_img
            return tk_img
        except Exception:
            return None

    def _make_blank_thumb(self, tw: int, th: int):
        from PIL import Image as _Img, ImageTk as _ITk
        img = _Img.new("RGB", (tw, th), "#1a1a2e")
        return _ITk.PhotoImage(img)

    def _current_fi(self) -> int:
        return next((i for i, (ri, _) in enumerate(self._filtered_files)
                     if ri == self.current_idx), -1)

    def _go_page(self, delta: int):
        if not self._filtered_files: return
        n_cols = max(1, min(6, self._thumb_n_var.get()))
        per_page = n_cols * 4
        total    = len(self._filtered_files)
        max_page = max(0, (total - 1) // per_page)
        self._film_page = max(0, min(max_page, self._film_page + delta))
        self._rebuild_filmstrip()

    def _go_page_abs(self, page: int):
        """Nhảy tới trang đầu (0) hoặc trang cuối (-1)."""
        if not self._filtered_files: return
        if page < 0:
            self._film_page = self._film_max_page
        else:
            self._film_page = 0
        self._rebuild_filmstrip()

    def _go_page_direct(self):
        """Nhảy tới số trang nhập trực tiếp trong entry."""
        if not self._filtered_files: return
        try:
            page_num = int(self._page_nav.page_var.get())
        except ValueError:
            self._page_nav.page_var.set(str(self._film_page + 1))
            return
        target = max(0, min(self._film_max_page, page_num - 1))
        if target != self._film_page:
            self._film_page = target
            self._rebuild_filmstrip()
        else:
            self._page_nav.page_var.set(str(self._film_page + 1))

    def _rebuild_filmstrip(self):
        for w in self._film_inner.winfo_children():
            w.destroy()
        self._film_cells.clear()

        if not self._filtered_files:
            self._page_nav.update(0, 0, 0)
            self._film_max_page = 0
            return

        n_cols = max(1, min(6, self._thumb_n_var.get()))
        self._thumb_n_var.set(n_cols)
        self._film_ncols = n_cols
        per_page = n_cols * 4

        total    = len(self._filtered_files)
        max_page = max(0, (total - 1) // per_page)
        self._film_page = max(0, min(max_page, self._film_page))

        start      = self._film_page * per_page
        end        = min(start + per_page, total)
        page_files = self._filtered_files[start:end]

        self._film_max_page = max_page
        self._page_nav.update(self._film_page, max_page, total)

        canvas_w = self._film_canvas.winfo_width() or 500
        pad = 4
        tw = max(120, (canvas_w - pad * (n_cols + 1) - 14) // n_cols)
        th = max(80,  int(tw * 0.625))

        if self._thumb_w != tw or self._thumb_h != th:
            self._thumb_cache.clear()
        self._thumb_w, self._thumb_h = tw, th

        blank = self._make_blank_thumb(tw, th)

        for fi_off, (real_idx, fp) in enumerate(page_files):
            row, col = divmod(fi_off, n_cols)
            is_cur   = (real_idx == self.current_idx)
            border   = "#F05922" if is_cur else "#2a2a3e"

            cell = Frame(self._film_inner, bg=border, padx=2, pady=2,
                         cursor="hand2")
            cell.grid(row=row, column=col, padx=3, pady=3, sticky="nw")

            img_lbl = Label(cell, image=blank, bg="#1a1a2e", bd=0)
            img_lbl.pack()

            fn_text = fp.name if len(fp.name) <= 24 else fp.name[:21] + "..."
            fn_lbl = Label(cell, text=fn_text, bg="#111130",
                           fg="#9090bb", font=("Consolas", 7), anchor=W, padx=2)
            fn_lbl.pack(fill=X)

            for widget in (cell, img_lbl, fn_lbl):
                widget.bind("<Button-1>",
                            lambda e, ri=real_idx: self._film_click_real(ri))
                widget.bind("<MouseWheel>", lambda e: (
                    self._film_canvas.yview_scroll(
                        int(-1 * (e.delta / 120)), "units")))

            self._film_cells.append({
                "frame": cell, "img_lbl": img_lbl, "fn_lbl": fn_lbl,
                "tk_img": blank, "real_idx": real_idx, "rendered": False
            })

        self._film_canvas.update_idletasks()
        self._film_canvas.configure(scrollregion=self._film_canvas.bbox("all"))
        self._film_canvas.yview_moveto(0)

        self._film_render_idx = 0
        self._schedule_film_render()

    def _schedule_film_render(self):
        BATCH = 10
        fid = self._grid_filter_id()
        end = min(self._film_render_idx + BATCH, len(self._film_cells))
        for cell in self._film_cells[self._film_render_idx:end]:
            if not cell["rendered"]:
                fp = self.image_files[cell["real_idx"]]
                tk_img = self._render_thumb(fp, self._thumb_w, self._thumb_h, fid)
                if tk_img is None:
                    tk_img = self._make_blank_thumb(self._thumb_w, self._thumb_h)
                cell["tk_img"] = tk_img
                cell["img_lbl"].config(image=tk_img)
                cell["rendered"] = True
        self._film_render_idx = end
        if end < len(self._film_cells):
            self.after(40, self._schedule_film_render)

    def _film_click_real(self, real_idx: int):
        if real_idx == self.current_idx: return
        fi = next((i for i, (ri, _) in enumerate(self._filtered_files)
                   if ri == real_idx), -1)
        if fi < 0: return
        self._autosave()
        self._img_lb.selection_clear(0, END)
        self._img_lb.selection_set(fi)
        self._img_lb.see(fi)
        self._load_image(real_idx)

    def _update_filmstrip(self):
        if not self._filtered_files:
            return
        if not self._film_cells:
            self._rebuild_filmstrip()
            return

        n_cols   = max(1, min(6, self._thumb_n_var.get()))
        per_page = n_cols * 4
        fi       = self._current_fi()
        if fi >= 0:
            target_page = fi // per_page
            if target_page != self._film_page:
                self._film_page = target_page
                self._rebuild_filmstrip()
                return

        for cell in self._film_cells:
            is_cur = (cell["real_idx"] == self.current_idx)
            cell["frame"].config(bg="#F05922" if is_cur else "#2a2a3e")

        fid = self._grid_filter_id()
        for cell in self._film_cells:
            if cell["real_idx"] == self.current_idx:
                fp  = self.image_files[self.current_idx]
                key = (str(fp), self._thumb_w, self._thumb_h, fid)
                self._thumb_cache.pop(key, None)
                tk_img = self._render_thumb(fp, self._thumb_w, self._thumb_h, fid)
                if tk_img is None:
                    tk_img = self._make_blank_thumb(self._thumb_w, self._thumb_h)
                cell["tk_img"] = tk_img
                cell["img_lbl"].config(image=tk_img)
                break

    # ══════════════════════════════════════════════════ AUTO-DETECT (YOLO/DETR) ══

    def _browse_det_model(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="Chọn file model (.pt YOLO/RF-DETR hoặc .onnx)",
            filetypes=[("Model files", "*.pt *.onnx"),
                       ("PyTorch Model", "*.pt"),
                       ("ONNX Model", "*.onnx"),
                       ("All files", "*.*")],
            parent=self.root)
        if not path:
            return
        _push_history("h.bbox.det_model", path)
        self._det_combo["values"] = _get_history("h.bbox.det_model")
        self._det_model_path.set(path)
        self._load_det_model(path)

    def _load_det_model(self, path: str):
        if not path or not os.path.isfile(path):
            return
        self._det_model_lbl.config(text=f"⏳ {os.path.basename(path)}…", fg=DIM)
        self._btn_detect.config(state="disabled")

        def _do():
            try:
                mdl, names, mtype = self._auto_load_det_model(path)
                self.root.after(0, lambda: self._on_det_model_loaded(path, mdl, names, mtype, None))
            except Exception as e:
                self.root.after(0, lambda err=str(e): self._on_det_model_loaded(path, None, {}, "yolo", err))

        import threading
        threading.Thread(target=_do, daemon=True).start()

    def _auto_load_det_model(self, path: str):
        """Tự phân biệt YOLO / RF-DETR / ONNX, trả về (model, names, mtype)."""
        ext = os.path.splitext(path)[1].lower()
        if ext == ".onnx":
            # Dùng _OnnxRunner từ yolo_onnx (đã được test kỹ; tách khỏi tab_yolo.py 2026-07-03)
            try:
                from ..detection.yolo_onnx import _OnnxRunner, _OnnxDetResult  # noqa
                runner = _OnnxRunner(path)
                return runner, {}, "onnx"
            except ImportError:
                pass
            # Fallback inline nếu import thất bại
            try:
                import onnxruntime as ort
            except ImportError:
                raise ImportError("pip install onnxruntime")
            import numpy as _np

            providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
            sess  = ort.InferenceSession(path, providers=providers)
            inp   = sess.get_inputs()[0]
            shape = inp.shape
            iH = int(shape[2]) if isinstance(shape[2], int) and shape[2] > 0 else 640
            iW = int(shape[3]) if isinstance(shape[3], int) and shape[3] > 0 else 640
            onames = [o.name for o in sess.get_outputs()]
            _MEAN  = _np.array([0.485, 0.456, 0.406], dtype=_np.float32)
            _STD   = _np.array([0.229, 0.224, 0.225], dtype=_np.float32)
            _iname = inp.name

            def _make_det(xyxy, conf, cid):
                xyxy = _np.array(xyxy, dtype=_np.float32)
                return type("D", (), {
                    "xyxy":       xyxy if len(xyxy) else _np.empty((0, 4), dtype=_np.float32),
                    "confidence": _np.array(conf, dtype=_np.float32),
                    "class_id":   _np.array(cid,  dtype=_np.int32),
                    "__len__":    lambda self: len(self.xyxy),
                })()

            def _sigmoid(x): return 1.0 / (1.0 + _np.exp(-_np.clip(x, -88, 88)))

            def _cxcywh(bx, w, h):
                x1 = (bx[:, 0] - bx[:, 2] / 2) * w
                y1 = (bx[:, 1] - bx[:, 3] / 2) * h
                x2 = (bx[:, 0] + bx[:, 2] / 2) * w
                y2 = (bx[:, 1] + bx[:, 3] / 2) * h
                return _np.clip(_np.stack([x1, y1, x2, y2], axis=1), 0, None)

            def _scale(bx, w, h):
                if bx.size and bx.max() <= 1.5:
                    return bx * [w, h, w, h]
                return bx

            def _parse(outs, orig_w, orig_h, threshold):
                # A. RF-DETR sigmoid — thử cả 2 thứ tự output
                if len(outs) >= 2:
                    try:
                        a0, a1 = _np.array(outs[0]), _np.array(outs[1])
                        for la, ba in [(a0, a1), (a1, a0)]:
                            if la.ndim == 3 and ba.ndim == 3 and ba.shape[-1] == 4:
                                logits = la.squeeze(0)
                                boxes  = ba.squeeze(0)
                                probs  = _sigmoid(logits)
                                scores = probs.max(axis=1)
                                labels = probs.argmax(axis=1)
                                mask   = scores >= threshold
                                if mask.any():
                                    return _make_det(_cxcywh(boxes[mask], orig_w, orig_h),
                                                     scores[mask], labels[mask])
                                return _make_det([], [], [])
                    except Exception:
                        pass
                # B. Post-processed: boxes(N,4) + scores(N) + labels(N)
                if len(outs) >= 3:
                    for ai, bi, ci in [(0,1,2), (1,0,2), (0,2,1)]:
                        try:
                            bx = _np.array(outs[ai]).reshape(-1, 4)
                            sc = _np.array(outs[bi]).flatten()
                            lb = _np.array(outs[ci]).flatten().astype(int)
                            if len(bx) == len(sc) == len(lb) > 0:
                                mask = sc >= threshold
                                return _make_det(_scale(bx[mask], orig_w, orig_h),
                                                 sc[mask], lb[mask])
                        except Exception:
                            continue
                # C. YOLO [1,N,6+]
                if len(outs) >= 1:
                    try:
                        out = _np.array(outs[0])
                        if out.ndim == 3: out = out[0]
                        if out.ndim == 2 and out.shape[1] >= 6:
                            mask = out[:, 4] >= threshold
                            out  = out[mask]
                            return _make_det(_scale(out[:, :4], orig_w, orig_h),
                                             out[:, 4], out[:, 5].astype(int))
                    except Exception:
                        pass
                # D. Classic DETR softmax
                if len(outs) >= 2:
                    try:
                        a0 = _np.array(outs[0]).squeeze(0)
                        a1 = _np.array(outs[1]).squeeze(0)
                        for logits, boxes in [(a0, a1), (a1, a0)]:
                            if logits.ndim == 2 and boxes.ndim == 2 and boxes.shape[1] == 4:
                                e = _np.exp(logits - logits.max(axis=1, keepdims=True))
                                probs  = e / e.sum(axis=1, keepdims=True)
                                probs  = probs[:, :-1]
                                scores = probs.max(axis=1)
                                labels = probs.argmax(axis=1)
                                mask   = scores >= threshold
                                return _make_det(_cxcywh(boxes[mask], orig_w, orig_h),
                                                 scores[mask], labels[mask])
                    except Exception:
                        pass
                return _make_det([], [], [])

            class _InlineRunner:
                names = {}
                def predict(self_r, pil_img, threshold=0.25):
                    from PIL import Image as _Img
                    pil = pil_img.convert("RGB") if hasattr(pil_img, "convert") else _Img.fromarray(pil_img).convert("RGB")
                    ow, oh = pil.size
                    arr   = _np.array(pil.resize((iW, iH)), dtype=_np.float32) / 255.0
                    arr   = (arr - _MEAN) / _STD
                    arr   = arr.transpose(2, 0, 1)[_np.newaxis]
                    outs  = sess.run(onames, {_iname: arr})
                    return _parse(outs, ow, oh, threshold)

            return _InlineRunner(), {}, "onnx"

        # .pt: thử YOLO trước
        yolo_err = None
        try:
            from ultralytics import YOLO as _YOLO
            mdl   = _YOLO(path)
            names = dict(mdl.names) if hasattr(mdl, "names") else {}
            return mdl, names, "yolo"
        except ImportError:
            yolo_err = ImportError("pip install ultralytics")
        except Exception as e:
            yolo_err = e
        # Thử RF-DETR
        try:
            from rfdetr import RFDETRBase as _RFDETR
            mdl   = _RFDETR(pretrain_weights=path)
            names = {}
            if hasattr(mdl, "model") and hasattr(mdl.model, "names"):
                raw = mdl.model.names
                names = ({i: n for i, n in enumerate(raw)}
                         if isinstance(raw, (list, tuple)) else dict(raw))
            return mdl, names, "rfdetr"
        except ImportError:
            pass
        if yolo_err:
            raise yolo_err
        raise ImportError("pip install ultralytics  hoặc  pip install rfdetr")

    def _on_det_model_loaded(self, path: str, mdl, names: dict, mtype: str, err):
        self._btn_detect.config(state="normal")
        if err:
            self._det_model_lbl.config(text="✗ Lỗi load", fg=ACCENT)
            messagebox.showerror("Lỗi load model", err, parent=self.root)
            return
        self._det_model      = mdl
        self._det_model_type = mtype
        self._det_model_names = names
        name = os.path.basename(path)
        tag  = {"rfdetr": " [DETR]", "onnx": " [ONNX]"}.get(mtype, "")
        n_cls = len(names)
        cls_info = f" [{n_cls}cls]" if n_cls else ""
        self._det_model_lbl.config(text=f"✓ {name}{tag}{cls_info}", fg="#4caf50")
        self._refresh_batch_class_combo()
        self._batch_refresh_model_display()

    def _run_detect(self):
        path = self._det_model_path.get().strip()
        if not path:
            messagebox.showwarning("Chưa chọn model",
                                   "Vui lòng chọn file model (.pt hoặc .onnx).", parent=self.root)
            return
        if self._pil_img is None:
            messagebox.showwarning("Chưa có ảnh",
                                   "Vui lòng tải ảnh trước.", parent=self.root)
            return

        # Load model nếu chưa có (lần đầu hoặc đổi model)
        if self._det_model is None:
            self._load_det_model(path)
            self._det_status_lbl.config(text="⏳ Đang load model, nhấn Detect lại sau…", fg=DIM)
            return

        self._btn_detect.config(state="disabled")
        self._det_status_lbl.config(text="⏳ Đang detect…", fg=DIM)

        import threading
        import numpy as np
        conf      = self._det_conf_var.get()
        model     = self._det_model
        mtype     = self._det_model_type
        pil_copy  = self._pil_img.copy()
        img_arr   = np.array(pil_copy)

        def _do():
            try:
                boxes = []
                if mtype == "yolo":
                    results = model.predict(img_arr, conf=conf, verbose=False)
                    if results and results[0].boxes is not None:
                        for box in results[0].boxes:
                            cid = int(box.cls[0])
                            x1, y1, x2, y2 = box.xyxy[0].tolist()
                            boxes.append([cid, x1, y1, x2, y2])
                else:
                    dets = model.predict(pil_copy, threshold=conf)
                    if dets and len(dets) > 0:
                        for i in range(len(dets.xyxy)):
                            cid = int(dets.class_id[i]) if dets.class_id is not None else 0
                            x1, y1, x2, y2 = dets.xyxy[i].tolist()
                            boxes.append([cid, x1, y1, x2, y2])
                self.root.after(0, lambda b=boxes: self._on_detect_done(b, None))
            except Exception as e:
                self.root.after(0, lambda err=str(e): self._on_detect_done([], err))

        threading.Thread(target=_do, daemon=True).start()

    def _on_detect_done(self, boxes: list, err: str | None):
        self._btn_detect.config(state="normal")
        if err:
            self._det_status_lbl.config(text=f"✗ {err[:50]}", fg=ACCENT)
            return
        if not boxes:
            self._det_status_lbl.config(text="Không detect được đối tượng nào.", fg=DIM)
            return

        iw, ih = self._pil_img.size
        self._push_undo()

        if self._det_replace_var.get():
            self._bboxes.clear()
            self._bbox_attrs.clear()

        n_added = 0
        for b in boxes:
            cid = int(b[0])
            x1 = max(0.0, min(float(b[1]), float(iw)))
            y1 = max(0.0, min(float(b[2]), float(ih)))
            x2 = max(0.0, min(float(b[3]), float(iw)))
            y2 = max(0.0, min(float(b[4]), float(ih)))
            if x2 > x1 and y2 > y1:
                self._bboxes.append([cid, x1, y1, x2, y2])
                self._bbox_attrs.append(self._default_attrs())
                n_added += 1

        self._modified = True
        self._save_labels()
        self._redraw_bboxes_only()
        self._refresh_present_labels()

        mode = "thay thế" if self._det_replace_var.get() else "thêm"
        self._det_status_lbl.config(
            text=f"✓ {n_added} bbox ({mode}) · đã lưu label", fg="#4caf50")
        self.after(5000, lambda: self._det_status_lbl.config(text="", fg=DIM))

    # ═══════════════════════════════════════════════════════ VERIFY OVERLAY ══

    def _run_verify(self):
        """Chạy model detect rồi so sánh với label hiện tại (không thay đổi label)."""
        path = self._det_model_path.get().strip()
        if not path:
            messagebox.showwarning("Chưa chọn model", "Chọn file model (.pt hoặc .onnx).", parent=self.root)
            return
        if self._pil_img is None:
            messagebox.showwarning("Chưa có ảnh", "Vui lòng tải ảnh trước.", parent=self.root)
            return
        if self._det_model is None:
            self._load_det_model(path)
            self._det_status_lbl.config(text="⏳ Đang load model, nhấn Kiểm tra lại sau…", fg=DIM)
            return

        self._btn_verify.config(state="disabled")
        self._btn_detect.config(state="disabled")
        self._det_status_lbl.config(text="⏳ Đang kiểm tra…", fg=DIM)

        import threading
        import numpy as np
        conf      = self._det_conf_var.get()
        model     = self._det_model
        mtype     = self._det_model_type
        pil_copy  = self._pil_img.copy()
        img_arr   = np.array(pil_copy)

        def _do():
            try:
                boxes = []
                if mtype == "yolo":
                    results = model.predict(img_arr, conf=conf, verbose=False)
                    if results and results[0].boxes is not None:
                        for box in results[0].boxes:
                            cid      = int(box.cls[0])
                            x1, y1, x2, y2 = box.xyxy[0].tolist()
                            conf_val = float(box.conf[0])
                            boxes.append([cid, x1, y1, x2, y2, conf_val])
                else:
                    dets = model.predict(pil_copy, threshold=conf)
                    if dets and len(dets) > 0:
                        for i in range(len(dets.xyxy)):
                            cid      = int(dets.class_id[i]) if dets.class_id is not None else 0
                            x1, y1, x2, y2 = dets.xyxy[i].tolist()
                            conf_val = float(dets.confidence[i]) if dets.confidence is not None else conf
                            boxes.append([cid, x1, y1, x2, y2, conf_val])
                self.root.after(0, lambda b=boxes: self._on_verify_done(b, None))
            except Exception as e:
                self.root.after(0, lambda err=str(e): self._on_verify_done([], err))

        threading.Thread(target=_do, daemon=True).start()

    def _on_verify_done(self, det_boxes: list, err):
        self._btn_verify.config(state="normal")
        self._btn_detect.config(state="normal")
        if err:
            self._det_status_lbl.config(text=f"✗ Lỗi: {err[:50]}", fg=ACCENT)
            return

        self._verify_boxes  = det_boxes
        self._verify_active = True

        try:
            iou_thresh = float(self._verify_iou_var.get())
        except (ValueError, TypeError):
            iou_thresh = 0.5
        iou_thresh = max(0.01, min(1.0, iou_thresh))

        # Chuyển GT bboxes về bounding rect (handle cả poly4)
        gt_rects = []
        for ann in self._bboxes:
            if len(ann) == 9:
                _, px1, py1, px2, py2, px3, py3, px4, py4 = ann
                xs = [px1, px2, px3, px4]; ys = [py1, py2, py3, py4]
                gt_rects.append([ann[0], min(xs), min(ys), max(xs), max(ys)])
            else:
                gt_rects.append(list(ann[:5]))

        self._verify_matched_gt, self._verify_matched_det, self._verify_gt_iou = \
            self._match_verify(det_boxes, gt_rects, iou_thresh)

        n_gt  = len(gt_rects)
        n_det = len(det_boxes)
        tp    = len(self._verify_matched_gt)
        fn    = n_gt  - tp
        fp    = n_det - len(self._verify_matched_det)

        self._render()
        all_ok = (fn == 0 and fp == 0)
        color  = "#4caf50" if all_ok else "#ff9800"
        self._det_status_lbl.config(
            text=f"🔍 GT={n_gt}  Det={n_det}  ✓Đúng={tp}  ✗Thiếu={fn}  ⚡Thừa={fp}",
            fg=color)

    def _on_verify_filter_change(self):
        """Callback khi toggle 'Chỉ hiện bbox sai' — redraw nếu verify đang active."""
        if self._verify_active:
            self._render()

    def _clear_verify(self):
        self._verify_boxes       = []
        self._verify_matched_gt  = set()
        self._verify_matched_det = set()
        self._verify_gt_iou      = {}
        self._verify_active      = False
        self._det_status_lbl.config(text="", fg=DIM)
        self._render()

    def _compute_iou(self, b1: list, b2: list) -> float:
        """IoU giữa 2 box dạng [cid, x1, y1, x2, y2, ...]."""
        ix1 = max(b1[1], b2[1]); iy1 = max(b1[2], b2[2])
        ix2 = min(b1[3], b2[3]); iy2 = min(b1[4], b2[4])
        inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
        if inter == 0.0:
            return 0.0
        a1    = (b1[3] - b1[1]) * (b1[4] - b1[2])
        a2    = (b2[3] - b2[1]) * (b2[4] - b2[2])
        union = a1 + a2 - inter
        return inter / union if union > 0 else 0.0

    def _match_verify(self, det_boxes: list, gt_rects: list, iou_thresh: float):
        """Greedy matching GT ↔ detection theo IoU giảm dần.
        Returns: (matched_gt_indices, matched_det_indices, gt_best_iou_dict)
        gt_best_iou_dict: {gi → best IoU đạt được, kể cả khi < threshold}
        """
        matched_gt   = set()
        matched_det  = set()
        gt_best_iou  = {}
        for gi, gt in enumerate(gt_rects):
            best_iou, best_di = 0.0, -1
            for di, det in enumerate(det_boxes):
                if di in matched_det:
                    continue
                iou = self._compute_iou(gt, det)
                if iou > best_iou:
                    best_iou = iou
                    best_di  = di
            gt_best_iou[gi] = best_iou
            if best_iou >= iou_thresh and best_di >= 0:
                matched_gt.add(gi)
                matched_det.add(best_di)
        return matched_gt, matched_det, gt_best_iou

    def _draw_verify_overlay(self):
        """Vẽ overlay so sánh: badge ✓/✗ lên GT bbox + detect box màu cyan/cam."""
        if not self._verify_active or self._pil_img is None:
            return
        lw = max(1, self._line_width_var.get())

        # ── Badge ✓/✗ trên mỗi GT bbox ──────────────────────────────────
        for i, ann in enumerate(self._bboxes):
            if len(ann) == 9:
                _, px1, py1, px2, py2, px3, py3, px4, py4 = ann
                xs = [px1, px2, px3, px4]; ys = [py1, py2, py3, py4]
                x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)
            else:
                _, x1, y1, x2, y2 = ann
            cx1 = int(x1 * self._scale) + self._off_x
            cy1 = int(y1 * self._scale) + self._off_y
            cx2 = int(x2 * self._scale) + self._off_x

            if i in self._verify_matched_gt:
                bg   = "#2e7d32"
                mark = "✓"
            else:
                bg       = "#c62828"
                best_iou = self._verify_gt_iou.get(i, 0.0)
                mark     = f"✗{best_iou:.2f}" if best_iou > 0 else "✗"

            badge_w = max(20, len(mark) * 7 + 6)
            bx1, by1, bx2, by2 = cx2 - badge_w, cy1 - 18, cx2, cy1
            self._canvas.create_rectangle(bx1, by1, bx2, by2,
                fill=bg, outline="white", width=1, tags="verify_item")
            self._canvas.create_text((bx1 + bx2) // 2, (by1 + by2) // 2,
                text=mark, fill="white",
                font=("Consolas", 7, "bold"), tags="verify_item")

        # ── Detect boxes: cyan = matched, cam = FP ───────────────────────
        _wrong_only = self._verify_show_wrong_only.get()
        for di, det in enumerate(self._verify_boxes):
            # Ẩn detect box đã khớp khi chế độ "chỉ hiện bbox sai"
            if _wrong_only and di in self._verify_matched_det:
                continue
            cid  = det[0]
            x1, y1, x2, y2 = det[1], det[2], det[3], det[4]
            conf = det[5] if len(det) > 5 else 0.0

            cx1 = int(x1 * self._scale) + self._off_x
            cy1 = int(y1 * self._scale) + self._off_y
            cx2 = int(x2 * self._scale) + self._off_x
            cy2 = int(y2 * self._scale) + self._off_y

            color    = "#00e5ff" if di in self._verify_matched_det else "#ff9800"
            cls_name = self.label_list[cid] if cid < len(self.label_list) else str(cid)
            txt      = f" {cid}:{cls_name} {conf:.2f} "
            txt_w    = max(len(txt) * 7, 30)

            self._canvas.create_rectangle(cx1, cy1, cx2, cy2,
                outline=color, width=lw, dash=(6, 3), tags="verify_item")
            self._canvas.create_rectangle(cx1, cy2, cx1 + txt_w, cy2 + 17,
                fill=color, outline="", tags="verify_item")
            self._canvas.create_text(cx1 + 3, cy2 + 8, text=txt, fill="white",
                font=("Segoe UI", 8, "bold"), anchor=W, tags="verify_item")

    # ═══════════════════════════════════════════════════ TEST VÙNG ZOOM ══

    def _run_zoomtest_detect(self):
        """Crop đúng vùng đang hiển thị trên canvas (theo zoom/pan hiện tại) từ ẢNH GỐC
        rồi detect lại trên crop đó — kiểm tra model có nhận ra vật thể khi được "phóng to"
        hay không. CHỈ hiển thị overlay tạm trên canvas, KHÔNG ghi vào _bboxes/label."""
        path = self._det_model_path.get().strip()
        if not path:
            messagebox.showwarning("Chưa chọn model",
                                   "Chọn file model (.pt hoặc .onnx).", parent=self.root)
            return
        if self._pil_img is None:
            messagebox.showwarning("Chưa có ảnh", "Vui lòng tải ảnh trước.", parent=self.root)
            return
        if self._det_model is None:
            self._load_det_model(path)
            self._det_status_lbl.config(text="⏳ Đang load model, nhấn lại sau…", fg=DIM)
            return

        from ...shared.canvas_zoom import canvas_view_to_image_box
        iw, ih = self._pil_img.size
        cw = self._canvas.winfo_width()
        ch = self._canvas.winfo_height()
        x1, y1, x2, y2 = canvas_view_to_image_box(self._scale, self._off_x, self._off_y,
                                                    cw, ch, iw, ih)
        if (x2 - x1) < 10 or (y2 - y1) < 10:
            messagebox.showwarning("Vùng zoom quá nhỏ",
                                   "Zoom to hơn để có vùng ảnh đủ lớn khi test.", parent=self.root)
            return

        crop_box = (int(x1), int(y1), int(x2), int(y2))
        crop     = self._pil_img.crop(crop_box)

        self._btn_zoomtest.config(state="disabled")
        self._det_status_lbl.config(text="⏳ Đang test detect vùng zoom…", fg=DIM)

        import threading
        from ...shared.model_infer import run_model_predict
        conf  = self._det_conf_var.get()
        model = self._det_model
        mtype = self._det_model_type

        def _do():
            try:
                boxes = run_model_predict(model, mtype, crop, conf)
                self.root.after(0, lambda b=boxes: self._on_zoomtest_done(b, crop_box, None))
            except Exception as e:
                self.root.after(0, lambda err=str(e): self._on_zoomtest_done([], crop_box, err))

        threading.Thread(target=_do, daemon=True).start()

    def _on_zoomtest_done(self, crop_boxes: list, crop_box: tuple, err: str | None):
        self._btn_zoomtest.config(state="normal")
        if err:
            self._det_status_lbl.config(text=f"✗ {err[:50]}", fg=ACCENT)
            return

        # Quy đổi tọa độ crop-local → ảnh gốc (cộng offset góc trên-trái của crop)
        ox, oy = crop_box[0], crop_box[1]
        self._zoomtest_boxes = [[cid, x1 + ox, y1 + oy, x2 + ox, y2 + oy, conf]
                                 for cid, x1, y1, x2, y2, conf in crop_boxes]
        self._zoomtest_active = True
        self._render()

        n = len(self._zoomtest_boxes)
        self._det_status_lbl.config(
            text=f"🔎 Test vùng zoom: {n} object (chỉ xem, chưa ghi label)",
            fg="#4caf50" if n else DIM)

    def _clear_zoomtest(self):
        self._zoomtest_boxes  = []
        self._zoomtest_active = False
        self._canvas.delete("zoomtest_item")
        self._det_status_lbl.config(text="", fg=DIM)

    def _draw_zoomtest_overlay(self):
        """Vẽ overlay tạm (màu tím/magenta) cho kết quả Test vùng zoom — không phải _bboxes."""
        if not self._zoomtest_active or self._pil_img is None:
            return
        lw    = max(1, self._line_width_var.get())
        color = "#e040fb"
        for cid, x1, y1, x2, y2, conf in self._zoomtest_boxes:
            cx1 = int(x1 * self._scale) + self._off_x
            cy1 = int(y1 * self._scale) + self._off_y
            cx2 = int(x2 * self._scale) + self._off_x
            cy2 = int(y2 * self._scale) + self._off_y

            cls_name = self.label_list[cid] if cid < len(self.label_list) else str(cid)
            txt      = f" 🔎{cid}:{cls_name} {conf:.2f} "
            txt_w    = max(len(txt) * 7, 30)

            self._canvas.create_rectangle(cx1, cy1, cx2, cy2,
                outline=color, width=lw, dash=(3, 2), tags="zoomtest_item")
            self._canvas.create_rectangle(cx1, cy1 - 17, cx1 + txt_w, cy1,
                fill=color, outline="", tags="zoomtest_item")
            self._canvas.create_text(cx1 + 3, cy1 - 8, text=txt, fill="white",
                font=("Segoe UI", 8, "bold"), anchor=W, tags="zoomtest_item")

    def _commit_zoomtest_to_label(self):
        """Ghi các bbox từ 'Test vùng zoom' (đã xác nhận đúng bằng mắt) vào _bboxes thật
        rồi lưu label — khác _run_detect (chạy trên toàn ảnh); ở đây dùng lại kết quả đã
        detect trên crop, không detect lại."""
        if not self._zoomtest_boxes:
            messagebox.showinfo("Chưa có kết quả",
                                "Bấm '🔎 Test vùng zoom' trước để có bbox cần thêm.",
                                parent=self.root)
            return

        iw, ih = self._pil_img.size
        self._push_undo()

        n_added = 0
        for cid, x1, y1, x2, y2, conf in self._zoomtest_boxes:
            x1 = max(0.0, min(float(x1), float(iw)))
            y1 = max(0.0, min(float(y1), float(ih)))
            x2 = max(0.0, min(float(x2), float(iw)))
            y2 = max(0.0, min(float(y2), float(ih)))
            if x2 > x1 and y2 > y1:
                self._bboxes.append([int(cid), x1, y1, x2, y2])
                self._bbox_attrs.append(self._default_attrs())
                n_added += 1

        self._modified = True
        self._save_labels()
        self._clear_zoomtest()
        self._redraw_bboxes_only()
        self._refresh_present_labels()

        self._det_status_lbl.config(
            text=f"✓ Đã thêm {n_added} bbox từ vùng zoom vào label", fg="#4caf50")
        self.after(5000, lambda: self._det_status_lbl.config(text="", fg=DIM))

    # ══════════════════════════════════════════════ BATCH ADD CLASS ══════════

    def _build_batch_add_class_ui(self, parent):
        """Tạo LabelFrame '➕ Bổ sung class hàng loạt' và các widget con.
        Amendment Phase 4: thêm Row A (model picker), Row B (source radio),
        Row C1/C2 (model / folder group), Row D (nhãn đích + chế độ ghi).
        Phase 6: LabelFrame thu gọn được qua button toggle trong labelwidget."""
        lf = LabelFrame(parent, bg=CARD, fg=ACCENT2, font=F_BOLD,
                        labelanchor=NW, relief="groove", padx=8, pady=4)
        # Tạo button toggle SAU KHI lf đã tồn tại (tránh circular reference)
        self._batch_toggle_btn = Button(lf, command=self._batch_toggle_collapse,
                                        bg=CARD, fg=ACCENT2, font=F_BOLD,
                                        relief="flat", activebackground=CARD,
                                        cursor="hand2")
        lf.configure(labelwidget=self._batch_toggle_btn)
        lf.pack(fill=X, pady=(2, 0))

        # Container cho toàn bộ Row A-G — pack/pack_forget khi toggle collapse
        self._batch_body = Frame(lf, bg=CARD)

        # Row A: Model picker (MỚI — đầu LabelFrame)
        row_a = Frame(self._batch_body, bg=CARD)
        row_a.pack(fill=X, pady=(2, 2))
        Label(row_a, text="🤖 Model:", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        self._batch_model_lbl = Label(row_a, text="(chưa load)", bg=CARD, fg=DIM,
                                      font=F_MAIN, width=30, anchor=W)
        self._batch_model_lbl.pack(side=LEFT, padx=(4, 8))
        Button(row_a, text="📂 Đổi model",
               command=self._browse_det_model,
               bg=ACCENT2, fg="white",
               activebackground=ACCENT, activeforeground="white",
               font=F_MAIN, relief="flat", padx=6, cursor="hand2").pack(side=LEFT)

        # Row B: Source selector radio (MỚI)
        row_b = Frame(self._batch_body, bg=CARD)
        row_b.pack(fill=X, pady=(0, 2))
        Label(row_b, text="Nguồn nhãn:", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        Radiobutton(row_b, text="🤖 Model detect",
                    variable=self._batch_src_mode_var, value="model",
                    command=self._on_batch_src_mode_change,
                    bg=CARD, fg=TEXT, selectcolor=CARD,
                    activebackground=CARD, font=F_MAIN).pack(side=LEFT, padx=(4, 8))
        Radiobutton(row_b, text="📁 Thư mục label",
                    variable=self._batch_src_mode_var, value="folder",
                    command=self._on_batch_src_mode_change,
                    bg=CARD, fg=TEXT, selectcolor=CARD,
                    activebackground=CARD, font=F_MAIN).pack(side=LEFT)

        # Row C1: Model source group (hiện mặc định khi mode="model")
        self._batch_src_model_frame = Frame(self._batch_body, bg=CARD)
        self._batch_src_model_frame.pack(fill=X, pady=(0, 2))
        Label(self._batch_src_model_frame, text="Class nguồn:",
              bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        self._batch_src_class_combo = ttk.Combobox(
            self._batch_src_model_frame, state="readonly",
            textvariable=self._batch_src_class_var,
            font=F_MAIN, width=22)
        self._batch_src_class_combo.pack(side=LEFT, padx=(4, 8))
        self._batch_src_class_combo.bind("<<ComboboxSelected>>",
                                         self._on_batch_src_class_change)

        # Row C2: Folder source group (ẩn ban đầu, hiện khi mode="folder")
        self._batch_src_folder_frame = Frame(self._batch_body, bg=CARD)
        # KHÔNG pack ngay — hiện theo _on_batch_src_mode_change
        Label(self._batch_src_folder_frame, text="Thư mục label nguồn:",
              bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        Entry(self._batch_src_folder_frame,
              textvariable=self._batch_src_label_dir_var,
              bg="#16162a", fg=TEXT, insertbackground=TEXT,
              relief="flat", font=F_MAIN, bd=2, width=20).pack(side=LEFT, padx=(4, 2))
        Button(self._batch_src_folder_frame, text="📁",
               command=self._batch_browse_src_label_dir,
               bg=ACCENT2, fg="white",
               activebackground=ACCENT, activeforeground="white",
               font=F_MAIN, relief="flat", padx=6, cursor="hand2").pack(side=LEFT,
                                                                         padx=(0, 8))
        Label(self._batch_src_folder_frame, text="Class id nguồn (vd: 0 hoặc 0,2,5):",
              bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        Entry(self._batch_src_folder_frame,
              textvariable=self._batch_src_class_ids_var,
              bg="#16162a", fg=TEXT, insertbackground=TEXT,
              relief="flat", font=F_MAIN, bd=2, width=14).pack(side=LEFT, padx=(4, 0))

        # Row D: Nhãn đích + chế độ ghi (MỚI — gộp Nhãn đích từ Row 1 cũ + thêm radio)
        row_d = Frame(self._batch_body, bg=CARD)
        row_d.pack(fill=X, pady=(0, 2))
        Label(row_d, text="→ Nhãn đích:", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        # Phase 6: đổi Entry → Combobox editable (KHÔNG readonly — user cần gõ tên mới)
        self._batch_dst_combo = ttk.Combobox(
            row_d, textvariable=self._batch_dst_label_var,
            values=list(self.label_list), font=F_MAIN, width=16)
        self._batch_dst_combo.pack(side=LEFT, padx=(4, 12))
        Label(row_d, text="Chế độ:", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        Radiobutton(row_d, text="Chỉ thêm",
                    variable=self._batch_write_mode_var, value="append",
                    bg=CARD, fg=TEXT, selectcolor=CARD,
                    activebackground=CARD, font=F_MAIN).pack(side=LEFT, padx=(4, 4))
        Radiobutton(row_d, text="Thay thế",
                    variable=self._batch_write_mode_var, value="replace",
                    bg=CARD, fg=TEXT, selectcolor=CARD,
                    activebackground=CARD, font=F_MAIN).pack(side=LEFT)

        # Row E: nút bấm quét
        row_e = Frame(self._batch_body, bg=CARD)
        row_e.pack(fill=X, pady=(2, 2))
        self._btn_batch_auto = Button(row_e, text="🔍 Quét toàn bộ",
                                      command=self._batch_start_auto,
                                      bg=ACCENT2, fg="white",
                                      activebackground=ACCENT, activeforeground="white",
                                      font=F_BOLD, relief="flat", padx=10, cursor="hand2")
        self._btn_batch_auto.pack(side=LEFT, padx=(0, 4))

        self._btn_batch_review = Button(row_e, text="🔍 Quét lần lượt",
                                        command=self._batch_start_review,
                                        bg=ACCENT2, fg="white",
                                        activebackground=ACCENT, activeforeground="white",
                                        font=F_BOLD, relief="flat", padx=10, cursor="hand2")
        self._btn_batch_review.pack(side=LEFT, padx=(0, 4))

        self._btn_batch_stop = Button(row_e, text="⏹ Dừng",
                                      command=self._batch_stop,
                                      bg="#555577", fg="white",
                                      activebackground="#333355", activeforeground="white",
                                      font=F_BOLD, relief="flat", padx=8, cursor="hand2")
        # Không pack ngay — ẩn ban đầu, hiện khi batch đang chạy

        # Row F: progressbar + status
        row_f = Frame(self._batch_body, bg=CARD)
        row_f.pack(fill=X, pady=(0, 2))
        self._batch_pb = ttk.Progressbar(row_f, style="K.Horizontal.TProgressbar",
                                         orient=HORIZONTAL, mode="determinate",
                                         maximum=100)
        self._batch_pb.pack(side=LEFT, fill=X, expand=True, padx=(0, 8))
        self._batch_status_lbl = Label(row_f, text="", bg=CARD, fg=DIM, font=F_MAIN,
                                       anchor=W)
        self._batch_status_lbl.pack(side=LEFT, fill=X, expand=False)

        # Row G: review buttons — ẩn ban đầu, chỉ pack khi review-waiting
        self._batch_review_frame = Frame(self._batch_body, bg=CARD)
        # KHÔNG pack ngay

        Button(self._batch_review_frame, text="✅ Áp dụng & tiếp theo",
               command=self._batch_review_apply,
               bg="#2e7d32", fg="white", activebackground="#1b5e20",
               activeforeground="white", font=F_BOLD, relief="flat", padx=10,
               cursor="hand2").pack(side=LEFT, padx=(0, 4))
        Button(self._batch_review_frame, text="⏭ Bỏ qua",
               command=self._batch_review_skip,
               bg=ACCENT2, fg="white", activebackground=ACCENT,
               activeforeground="white", font=F_BOLD, relief="flat", padx=10,
               cursor="hand2").pack(side=LEFT)

        # Khởi tạo combo + model display sau khi widget đã tạo
        self._refresh_batch_class_combo()
        self._batch_refresh_model_display()
        # Phase 6: áp dụng trạng thái collapsed ban đầu (đọc từ config hoặc mặc định thu gọn)
        self._batch_apply_collapse_state()

    def _batch_toggle_collapse(self):
        """Đảo trạng thái thu gọn/mở rộng khung Batch (Phase 6)."""
        self._batch_collapsed_var.set(0 if self._batch_collapsed_var.get() else 1)
        # _bind_cfg trace tự lưu config — không cần gọi save thủ công
        self._batch_apply_collapse_state()

    def _batch_apply_collapse_state(self):
        """Áp dụng trạng thái thu gọn/mở rộng dựa trên _batch_collapsed_var (Phase 6)."""
        if self._batch_collapsed_var.get():  # 1 = thu gọn
            self._batch_body.pack_forget()
            self._batch_toggle_btn.config(text="▶ ➕ Bổ sung class hàng loạt")
        else:  # 0 = mở rộng
            self._batch_body.pack(fill=X)
            self._batch_toggle_btn.config(text="▼ ➕ Bổ sung class hàng loạt")

    def _on_batch_src_class_change(self, _event=None):
        """Cập nhật nhãn đích khi user đổi class nguồn (chỉ khi đích đang rỗng)."""
        sel = self._batch_src_class_var.get()
        if sel and ":" in sel and not self._batch_dst_label_var.get().strip():
            name = sel.split(":", 1)[1].strip()
            self._batch_dst_label_var.set(name)

    def _refresh_batch_class_combo(self):
        """Đổ lại class nguồn từ _det_model_names. Enable/disable nút quét."""
        if not hasattr(self, "_batch_src_class_combo"):
            return
        if not self._det_model_names:
            self._batch_src_class_combo["values"] = [
                "(Model chưa load hoặc không có .names — dùng YOLO .pt)"]
            self._batch_src_class_combo.current(0)
            # Chỉ cập nhật status khi model mode và idle (folder mode không cần model)
            if (self._batch_state == "idle"
                    and self._batch_src_mode_var.get() == "model"):
                self._batch_status_lbl.config(
                    text="Model ONNX / chưa load — batch chưa sẵn sàng", fg=DIM)
        else:
            vals = [f"{cid}: {name}"
                    for cid, name in sorted(self._det_model_names.items())]
            self._batch_src_class_combo["values"] = vals
            if vals:
                self._batch_src_class_combo.current(0)
                # Gợi ý tên nhãn đích = tên class đầu tiên (chỉ khi đích chưa điền)
                if not self._batch_dst_label_var.get().strip():
                    first_name = sorted(self._det_model_names.items())[0][1]
                    self._batch_dst_label_var.set(first_name)
            self._batch_status_lbl.config(text="", fg=DIM)
        # Delegate enable/disable nút quét cho _batch_set_ui_state (check source_mode)
        self._batch_set_ui_state(self._batch_state)

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _refresh_label_widgets(self):
        """Đồng bộ mọi widget tham chiếu label_list sau khi label_list đã cập nhật."""
        combo_vals = [f"{i}: {name}" for i, name in enumerate(self.label_list)]

        # Listbox class (panel trái)
        self._cls_lb.delete(0, END)
        for i, name in enumerate(self.label_list):
            color = self._PALETTE[i % len(self._PALETTE)]
            self._cls_lb.insert(END, f"  [{i}]  {name}")
            self._cls_lb.itemconfig(END, fg=color)

        # Combobox class (toolbar)
        self._cls_combo["values"] = combo_vals

        # Batch Relabel combos
        if hasattr(self, "_rl_from_combo"):
            self._rl_from_combo["values"] = combo_vals
            self._rl_to_combo["values"]   = combo_vals

        # Filter label combo
        filter_opts = (["Tất cả", "Không có label"] + combo_vals)
        self._filter_label_combo["values"] = filter_opts

        # Must-have / Must-not-have listboxes
        self._must_have_lb.delete(0, END)
        self._must_not_lb.delete(0, END)
        for i, name in enumerate(self.label_list):
            color = self._PALETTE[i % len(self._PALETTE)]
            self._must_have_lb.insert(END, f"{i}: {name}")
            self._must_have_lb.itemconfig(END, fg=color)
            self._must_not_lb.insert(END, f"{i}: {name}")
            self._must_not_lb.itemconfig(END, fg=color)

        # Phase 6: Combobox nhãn đích batch — dùng plain name (không format "idx: name")
        # vì _batch_dst_label_var được so khớp trực tiếp bằng string tên nhãn ở _batch_start
        if hasattr(self, "_batch_dst_combo"):
            self._batch_dst_combo["values"] = list(self.label_list)

    def _resolve_lbl_path(self, fp: Path) -> Path:
        """Tính đường dẫn .txt label từ image path (giống logic _load_image)."""
        lbl_dir = self.lbl_dir_var.get().strip()
        if lbl_dir:
            return Path(lbl_dir) / (fp.stem + ".txt")
        return fp.parent / (fp.stem + ".txt")

    def _read_yolo_ext(self, path: Path, iw: int, ih: int) -> list:
        """Đọc YOLO .txt với kích thước ảnh explicit (không dùng self._pil_img).
        Giữ nguyên logic _read_yolo: hỗ trợ cả 5-token bbox và 9-token poly4/OBB."""
        bboxes = []
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    p = line.strip().split()
                    if len(p) == 5:
                        cid = int(p[0])
                        xc, yc, w, h = map(float, p[1:5])
                        if not all(math.isfinite(v) for v in (xc, yc, w, h)):
                            continue  # bỏ qua dòng có NaN/Inf
                        bboxes.append([cid,
                                       (xc - w / 2) * iw, (yc - h / 2) * ih,
                                       (xc + w / 2) * iw, (yc + h / 2) * ih])
                    elif len(p) == 9:
                        cid = int(p[0])
                        pts = list(map(float, p[1:9]))
                        if not all(math.isfinite(v) for v in pts):
                            continue  # bỏ qua dòng có NaN/Inf
                        bboxes.append([cid,
                                       pts[0] * iw, pts[1] * ih,
                                       pts[2] * iw, pts[3] * ih,
                                       pts[4] * iw, pts[5] * ih,
                                       pts[6] * iw, pts[7] * ih])
        except Exception:
            pass
        return bboxes

    def _write_yolo_ext(self, path: Path, bboxes: list, iw: int, ih: int):
        """Ghi YOLO .txt với kích thước ảnh explicit (không dùng self._pil_img / self._bboxes).
        Giữ đúng format 5-token (bbox) và 9-token (poly4/OBB) theo len(ann).
        Box batch mới thêm luôn là 5-token — không phá dòng 9-token cũ."""
        lines = []
        for ann in bboxes:
            cid = ann[0]
            if len(ann) == 9:
                _, x1, y1, x2, y2, x3, y3, x4, y4 = ann
                pts = [x1 / iw, y1 / ih, x2 / iw, y2 / ih,
                       x3 / iw, y3 / ih, x4 / iw, y4 / ih]
                pts = [max(0.0, min(1.0, v)) for v in pts]
                lines.append(f"{int(cid)} " + " ".join(f"{v:.6f}" for v in pts))
            else:
                _, x1, y1, x2, y2 = ann
                xc = max(0.0, min(1.0, ((x1 + x2) / 2) / iw))
                yc = max(0.0, min(1.0, ((y1 + y2) / 2) / ih))
                bw = max(1e-4, min(1.0, (x2 - x1) / iw))
                bh = max(1e-4, min(1.0, (y2 - y1) / ih))
                lines.append(f"{int(cid)} {xc:.6f} {yc:.6f} {bw:.6f} {bh:.6f}")
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    # ── Amendment Phase 4 — helper methods mới ───────────────────────────────

    def _batch_refresh_model_display(self):
        """Cập nhật label model trong khung Batch từ _det_model_path."""
        if not hasattr(self, "_batch_model_lbl"):
            return
        path = self._det_model_path.get().strip() if hasattr(self, "_det_model_path") else ""
        if path:
            import os
            self._batch_model_lbl.config(text=os.path.basename(path), fg=TEXT)
        else:
            self._batch_model_lbl.config(text="(chưa load)", fg=DIM)

    def _on_batch_src_mode_change(self, _event=None):
        """Ẩn/hiện group C1 (model) hoặc C2 (folder) theo radio Nguồn nhãn."""
        mode = self._batch_src_mode_var.get()
        if mode == "model":
            self._batch_src_folder_frame.pack_forget()
            self._batch_src_model_frame.pack(fill=X, pady=(0, 2))
            # Tính lại status text (có thể cần hiện cảnh báo ONNX/chưa load)
            # _refresh_batch_class_combo đã gọi _batch_set_ui_state ở cuối
            self._refresh_batch_class_combo()
        else:  # "folder"
            self._batch_src_model_frame.pack_forget()
            self._batch_src_folder_frame.pack(fill=X, pady=(0, 2))
            # Xoá status cũ còn sót từ khi source_mode là "model"
            self._batch_status_lbl.config(text="", fg=DIM)
            # Cập nhật trạng thái nút quét (folder mode luôn enable)
            self._batch_set_ui_state(self._batch_state)

    def _batch_browse_src_label_dir(self):
        """Mở dialog chọn thư mục label nguồn (folder source mode)."""
        from tkinter import filedialog
        d = filedialog.askdirectory(title="Chọn thư mục label nguồn",
                                    parent=self.root)
        if d:
            self._batch_src_label_dir_var.set(d)

    def _batch_parse_src_ids(self) -> tuple:
        """Parse ô class_id nguồn (dùng khi source_mode='folder').
        Chấp nhận '0' / '0,2,5' / '0; 2; 5' / '0 2 5' (tolerance dấu phẩy/chấm phẩy).
        Trả về (ids: set[int], err_msg: str). Nếu err_msg != '' → invalid."""
        raw = self._batch_src_class_ids_var.get().strip()
        if not raw:
            return set(), "Vui lòng nhập ít nhất 1 class id nguồn (VD: 0 hoặc 0,2,5)."
        ids = set()
        for tok in raw.replace(";", ",").split(","):
            t = tok.strip()
            if not t:
                continue
            try:
                ids.add(int(t))
            except ValueError:
                return set(), f"Class id không hợp lệ: '{t}' (phải là số nguyên)."
        if not ids:
            return set(), "Không parse được class id nào."
        return ids, ""

    def _batch_get_new_boxes_for_image(self, fp: Path, src_ids: set, dst_cid: int,
                                        source_mode: str, src_label_dir,
                                        need_preview_px: bool):
        """Lấy danh sách box mới cho 1 ảnh theo source_mode.

        Trả về (new_lines_norm: list[str], new_boxes_px: list[tuple], iw: int, ih: int)
        hoặc None nếu không có box nào.

        - new_lines_norm : dòng YOLO đã format, cid = dst_cid, normalized 0-1.
        - new_boxes_px   : tọa độ pixel cho preview overlay (chế độ review).
        - iw, ih         : kích thước ảnh. Trả về 0/0 nếu folder+auto (không mở ảnh).
        """
        from ...shared.model_infer import run_model_predict

        if source_mode == "model":
            # Mở PIL + inference (giữ nguyên logic bản gốc)
            try:
                pil = self._PIL_Image.open(fp).convert("RGB")
                iw, ih = pil.size
                if iw <= 0 or ih <= 0:
                    return None  # ảnh lỗi, không xử lý
                boxes = run_model_predict(
                    self._det_model, self._det_model_type, pil,
                    self._det_conf_var.get())
            except Exception:
                return None
            matched = [(x1, y1, x2, y2)
                       for cid, x1, y1, x2, y2, _sc in boxes
                       if cid in src_ids]
            if not matched:
                return None
            new_lines_norm = []
            new_boxes_px   = []
            for x1, y1, x2, y2 in matched:
                xc = max(0.0, min(1.0, ((x1 + x2) / 2) / iw))
                yc = max(0.0, min(1.0, ((y1 + y2) / 2) / ih))
                bw = max(1e-4, min(1.0, (x2 - x1) / iw))
                bh = max(1e-4, min(1.0, (y2 - y1) / ih))
                if not all(math.isfinite(v) for v in (xc, yc, bw, bh)):
                    continue  # bỏ qua box có toạ độ NaN/Inf sau khi tính
                new_lines_norm.append(
                    f"{int(dst_cid)} {xc:.6f} {yc:.6f} {bw:.6f} {bh:.6f}")
                new_boxes_px.append((dst_cid, x1, y1, x2, y2))
            if not new_lines_norm:
                return None
            return (new_lines_norm, new_boxes_px, iw, ih)

        else:  # source_mode == "folder"
            src_lbl_path = Path(src_label_dir) / (fp.stem + ".txt")
            if not src_lbl_path.exists():
                return None  # ảnh không có file nguồn — bỏ qua im lặng
            new_lines_norm = []
            try:
                with open(src_lbl_path, encoding="utf-8") as f:
                    for line in f:
                        parts = line.strip().split()
                        if len(parts) < 5:
                            continue  # dòng trống / thiếu token
                        try:
                            cid_src = int(parts[0])
                        except ValueError:
                            continue
                        if cid_src not in src_ids:
                            continue
                        if len(parts) != 5:
                            continue  # OBB 9-token từ nguồn — bỏ qua (out of scope)
                        # Parse float + validate — KHÔNG copy string thô (tránh ghi NaN/Inf)
                        try:
                            cx = float(parts[1]); cy = float(parts[2])
                            bw = float(parts[3]); bh = float(parts[4])
                        except ValueError:
                            continue
                        # Range check với tolerance 0.001 — tránh false positive
                        # từ exporter có floating-point rounding (VD cx=1.0000001).
                        # NaN/Inf vẫn bị chặn bởi isfinite; box lệch <=0.001 vô hại
                        # (render lệch ~1px, downstream tự clamp nếu cần).
                        if not (math.isfinite(cx) and math.isfinite(cy) and
                                math.isfinite(bw) and math.isfinite(bh) and
                                -0.001 <= cx <= 1.001 and -0.001 <= cy <= 1.001 and
                                bw > 0 and bh > 0):
                            continue  # loại bỏ NaN/Inf/âm rõ ràng/ngoài dải bất thường
                        new_lines_norm.append(
                            f"{int(dst_cid)} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
            except Exception:
                return None
            if not new_lines_norm:
                return None
            if need_preview_px:
                # Review mode: mở PIL chỉ lấy size để convert normalized→pixel
                try:
                    with self._PIL_Image.open(fp) as _im:
                        iw, ih = _im.size
                except Exception:
                    iw, ih = 0, 0
                new_boxes_px = []
                for ln in new_lines_norm:
                    p = ln.strip().split()
                    if len(p) != 5:
                        continue
                    _, xc_s, yc_s, w_s, h_s = p
                    xc, yc, w, h = float(xc_s), float(yc_s), float(w_s), float(h_s)
                    x1 = (xc - w / 2) * iw
                    y1 = (yc - h / 2) * ih
                    x2 = (xc + w / 2) * iw
                    y2 = (yc + h / 2) * ih
                    new_boxes_px.append((dst_cid, x1, y1, x2, y2))
                return (new_lines_norm, new_boxes_px, iw, ih)
            else:
                # Auto mode + folder: KHÔNG mở ảnh, không cần pixel coords
                return (new_lines_norm, [], 0, 0)

    def _batch_write_new_lines(self, lbl_path: Path, new_lines_norm: list,
                                dst_cid: int, replace_mode: bool) -> None:
        """Ghi file .txt đích theo chế độ append/replace, thao tác text-level.

        - Đọc raw text lines hiện có (giữ nguyên format 5-token / 9-token OBB).
        - replace_mode=True: xoá TẤT CẢ dòng có class_id == dst_cid,
          giữ mọi dòng khác (kể cả 9-token OBB có cid ≠ dst_cid).
        - Append new_lines_norm vào cuối.
        - Ghi lại file (mkdir parents nếu cần).

        KHÔNG cần iw/ih. Text-level → an toàn 100% với OBB 9-token (không parse lại).
        """
        existing_lines: list = []
        if lbl_path.exists():
            try:
                with open(lbl_path, encoding="utf-8") as f:
                    existing_lines = [ln.rstrip("\n") for ln in f if ln.strip()]
            except Exception:
                existing_lines = []

        if replace_mode:
            keep = []
            for ln in existing_lines:
                parts = ln.strip().split()
                if not parts:
                    continue
                try:
                    cid = int(parts[0])
                except ValueError:
                    keep.append(ln)  # giữ dòng lạ (không có cid số)
                    continue
                if cid == dst_cid:
                    continue         # XOÁ dòng có class_id == dst_cid
                keep.append(ln)
            existing_lines = keep

        all_lines = existing_lines + list(new_lines_norm)
        lbl_path.parent.mkdir(parents=True, exist_ok=True)
        with open(lbl_path, "w", encoding="utf-8") as f:
            f.write("\n".join(all_lines))

    # ── State management ─────────────────────────────────────────────────────

    def _batch_set_ui_state(self, state: str):
        """Cập nhật trạng thái nút batch theo state.
        Idle: ẩn nút Dừng (pack_forget). Running: hiện nút Dừng (pack).
        Amendment: folder mode luôn có thể chạy dù model chưa load."""
        self._batch_state = state
        if state == "idle":
            # Enable nút quét: folder mode không cần model
            src_mode = self._batch_src_mode_var.get()
            can_run  = (src_mode == "folder") or bool(self._det_model_names)
            n_st = "normal" if can_run else "disabled"
            self._btn_batch_auto.config(state=n_st)
            self._btn_batch_review.config(state=n_st)
            self._btn_batch_stop.pack_forget()   # ẩn khi idle
        else:  # any running state
            self._btn_batch_auto.config(state="disabled")
            self._btn_batch_review.config(state="disabled")
            self._btn_batch_stop.pack(side=LEFT)  # hiện khi chạy

    # ── Batch start / stop ───────────────────────────────────────────────────

    def _batch_start_auto(self):
        self._batch_start("auto")

    def _batch_start_review(self):
        self._batch_start("review")

    def _batch_start(self, mode: str):
        """Validate input rồi spawn worker thread cho mode='auto'|'review'.
        Amendment Phase 4: validate theo source_mode, dispatch args mới cho worker."""
        import threading

        if self._batch_state != "idle":
            messagebox.showwarning("Đang chạy",
                                   "Đã có batch đang chạy. Bấm ⏹ Dừng trước.",
                                   parent=self.root)
            return
        if not self.image_files:
            messagebox.showwarning("Chưa tải ảnh",
                                   "Vui lòng tải thư mục ảnh trước.",
                                   parent=self.root)
            return

        source_mode = self._batch_src_mode_var.get()    # "model" | "folder"
        replace_mode = (self._batch_write_mode_var.get() == "replace")

        # Validate theo source_mode
        if source_mode == "model":
            if self._det_model is None:
                messagebox.showwarning("Chưa load model",
                                       "Vui lòng load model detect trước.",
                                       parent=self.root)
                return
            if not self._det_model_names:
                messagebox.showwarning("Model không hỗ trợ",
                                       "Model hiện tại không có .names — "
                                       "không dùng được với nguồn Model.\n"
                                       "Vui lòng load model YOLO .pt.",
                                       parent=self.root)
                return
            sel = self._batch_src_class_var.get()
            if not sel or sel.startswith("("):
                messagebox.showwarning("Chưa chọn class",
                                       "Vui lòng chọn class nguồn từ dropdown.",
                                       parent=self.root)
                return
            try:
                src_cid = int(sel.split(":")[0])
            except (ValueError, IndexError):
                messagebox.showerror("Lỗi", "Class nguồn không hợp lệ.", parent=self.root)
                return
            src_ids = {src_cid}
            src_label_dir = None
        else:  # source_mode == "folder"
            src_ids, err = self._batch_parse_src_ids()
            if err:
                messagebox.showwarning("Class id nguồn không hợp lệ", err,
                                       parent=self.root)
                return
            src_label_dir_str = self._batch_src_label_dir_var.get().strip()
            if not src_label_dir_str:
                messagebox.showwarning("Chưa chọn thư mục nguồn",
                                       "Vui lòng chọn thư mục label nguồn hợp lệ.",
                                       parent=self.root)
                return
            src_label_dir = Path(src_label_dir_str)
            if not src_label_dir.is_dir():
                messagebox.showwarning("Thư mục không tồn tại",
                                       f"Thư mục label nguồn không tồn tại:\n{src_label_dir_str}",
                                       parent=self.root)
                return

        # Lấy và validate label đích (chung cho cả 2 nguồn)
        dst_label = self._batch_dst_label_var.get().strip()
        if not dst_label:
            messagebox.showwarning("Thiếu nhãn đích",
                                   "Vui lòng nhập tên nhãn đích.",
                                   parent=self.root)
            return

        # Đảm bảo dst_label có trong label_list
        if dst_label in self.label_list:
            dst_cid = self.label_list.index(dst_label)
        else:
            self.label_list.append(dst_label)
            self._labels_var.set(",".join(self.label_list))
            dst_cid = len(self.label_list) - 1
            self._refresh_label_widgets()
        self._batch_dst_cid = dst_cid

        # Lưu ảnh đang mở trước khi bắt đầu
        self._autosave()

        # Khởi tạo sync events
        self._batch_cancel_evt      = threading.Event()
        self._batch_review_evt      = threading.Event()
        self._batch_review_decision = None

        # Cập nhật UI
        init_state = "auto" if mode == "auto" else "review-scanning"
        self._batch_set_ui_state(init_state)
        self._batch_pb["value"] = 0
        self._batch_status_lbl.config(
            text=f"⏳ Chuẩn bị quét {len(self.image_files)} ảnh…", fg=DIM)

        # Spawn worker daemon thread với signature mới
        threading.Thread(
            target=self._batch_worker,
            args=(mode, src_ids, dst_cid, source_mode, src_label_dir, replace_mode),
            daemon=True
        ).start()

    def _batch_stop(self):
        """Huỷ batch đang chạy (set cancel + unblock review nếu đang chờ)."""
        if self._batch_cancel_evt:
            self._batch_cancel_evt.set()
        self._batch_review_decision = "stop"
        if self._batch_review_evt:
            self._batch_review_evt.set()
        self._batch_status_lbl.config(text="⏳ Đang dừng sau ảnh hiện tại…", fg=DIM)

    # ── Worker thread ────────────────────────────────────────────────────────

    def _batch_worker(self, mode: str, src_ids: set, dst_cid: int,
                      source_mode: str, src_label_dir, replace_mode: bool):
        """Chạy trong daemon thread. mode ∈ {'auto', 'review'}.
        Amendment Phase 4: signature mới, gọi _batch_get_new_boxes_for_image +
        _batch_write_new_lines thay cho PIL+inference+_write_yolo_ext inline.
        Mọi update UI qua self.root.after(0, ...) — tuyệt đối không động canvas trực tiếp."""
        total    = len(self.image_files)
        applied  = 0
        skipped  = 0
        detected = 0

        for i, fp in enumerate(self.image_files):
            if self._batch_cancel_evt.is_set():
                break
            self.root.after(0, self._batch_update_progress, i, total, fp.name)

            # Lấy box mới theo source_mode (model inference / đọc file folder)
            need_preview = (mode == "review")
            result = self._batch_get_new_boxes_for_image(
                fp, src_ids, dst_cid, source_mode, src_label_dir, need_preview)
            # TODO: IoU dedup (future work)
            if result is None:
                continue
            new_lines_norm, new_boxes_px, _iw, _ih = result
            detected += 1

            lbl_path = self._resolve_lbl_path(fp)

            if mode == "auto":
                # Ghi thẳng + reload nếu ảnh đang mở
                self._batch_write_new_lines(lbl_path, new_lines_norm, dst_cid, replace_mode)
                applied += 1
                self.root.after(0, self._batch_maybe_reload_current, fp)
            else:  # mode == "review"
                # Gửi preview lên UI thread, chờ quyết định
                self._batch_review_evt.clear()
                self.root.after(0, self._batch_show_review, fp, new_boxes_px)
                self._batch_review_evt.wait()  # BLOCK cho tới khi user bấm nút review

                if (self._batch_cancel_evt.is_set()
                        or self._batch_review_decision == "stop"):
                    break
                if self._batch_review_decision == "apply":
                    self._batch_write_new_lines(lbl_path, new_lines_norm, dst_cid,
                                                replace_mode)
                    applied += 1
                    self.root.after(0, self._batch_maybe_reload_current, fp)
                else:  # "skip"
                    skipped += 1
                self.root.after(0, self._batch_hide_review_ui)

        # Kết thúc — gọi _batch_finish trên UI thread
        self.root.after(0, self._batch_finish, applied, skipped, detected, total)

    # ── UI thread callbacks (gọi qua root.after) ────────────────────────────

    def _batch_update_progress(self, i: int, total: int, name: str):
        """Cập nhật progressbar + status label (UI thread)."""
        pct = int((i / total) * 100) if total > 0 else 0
        self._batch_pb["value"] = pct
        short = name if len(name) <= 40 else "…" + name[-38:]
        self._batch_status_lbl.config(text=f"[{i + 1}/{total}] {short}", fg=DIM)

    def _batch_show_review(self, fp: Path, new_boxes: list):
        """Mở ảnh fp, set preview overlay, hiện Row 3 review buttons (UI thread).
        Gọi _autosave() trước để không mất thay đổi chưa lưu của ảnh trước."""
        self._autosave()

        try:
            real_idx = self.image_files.index(fp)
        except ValueError:
            # Ảnh không còn trong list — tự động skip
            self._batch_review_decision = "skip"
            if self._batch_review_evt:
                self._batch_review_evt.set()
            return

        # Set preview TRƯỚC _load_image để _render() vẽ đúng
        self._batch_preview_boxes  = list(new_boxes)
        self._batch_preview_active = True

        # Điều hướng image listbox nếu ảnh có trong filtered list
        fi = next((idx for idx, (ri, _) in enumerate(self._filtered_files)
                   if ri == real_idx), -1)
        if fi >= 0:
            self._img_lb.selection_clear(0, END)
            self._img_lb.selection_set(fi)
            self._img_lb.see(fi)

        self._load_image(real_idx)   # đọc _bboxes từ .txt + gọi _render()

        # Hiện Row 3 review buttons
        self._batch_review_frame.pack(fill=X, pady=(2, 2))
        self._batch_state = "review-waiting"

    def _batch_hide_review_ui(self):
        """Xoá preview overlay + ẩn Row 3 review buttons (UI thread)."""
        self._batch_preview_boxes  = []
        self._batch_preview_active = False
        self._canvas.delete("batch_preview_item")
        self._batch_review_frame.pack_forget()
        if self._batch_state == "review-waiting":
            self._batch_state = "review-scanning"

    def _batch_review_apply(self):
        """User bấm 'Áp dụng & tiếp theo'."""
        self._batch_review_decision = "apply"
        if self._batch_review_evt:
            self._batch_review_evt.set()

    def _batch_review_skip(self):
        """User bấm 'Bỏ qua'."""
        self._batch_review_decision = "skip"
        if self._batch_review_evt:
            self._batch_review_evt.set()

    def _batch_maybe_reload_current(self, fp: Path):
        """Nếu ảnh vừa ghi là ảnh đang mở → reload để _bboxes khớp file mới (UI thread).
        ⚠️ Ưu tiên batch: discard unsaved canvas changes của ảnh đang mở."""
        if self.current_idx < 0:
            return
        if self.image_files[self.current_idx] == fp:
            self._modified = False
            self._load_image(self.current_idx)

    def _batch_finish(self, applied: int, skipped: int, detected: int, total: int):
        """Reset state + hiển thị tổng kết (UI thread)."""
        self._batch_pb["value"] = 100
        self._batch_hide_review_ui()
        self._batch_set_ui_state("idle")
        self._batch_status_lbl.config(
            text=f"✓ Xong: {applied}/{detected} ảnh đã ghi", fg="#4caf50")
        msg = (f"Hoàn thành batch!\n\n"
               f"Tổng ảnh quét    : {total}\n"
               f"Ảnh có box mới   : {detected}\n"
               f"Đã ghi (áp dụng) : {applied}\n"
               f"Đã bỏ qua        : {skipped}")
        messagebox.showinfo("Batch Add Class", msg, parent=self.root)
        self.after(8000,
                   lambda: self._batch_status_lbl.config(text="", fg=DIM)
                   if self._batch_state == "idle" else None)

    # ── Preview overlay ──────────────────────────────────────────────────────

    def _draw_batch_preview_overlay(self):
        """Vẽ overlay preview (màu cam đứt nét #F05922) cho box mới do batch detect.
        KHÔNG trộn vào self._bboxes — chỉ hiển thị tới khi user bấm Áp dụng/Bỏ qua.
        Bám pattern _draw_zoomtest_overlay, dùng tag riêng 'batch_preview_item'."""
        if not self._batch_preview_active or self._pil_img is None:
            return
        lw    = max(2, self._line_width_var.get() + 1)
        color = "#F05922"  # ACCENT cam
        for cid, x1, y1, x2, y2 in self._batch_preview_boxes:
            cx1 = int(x1 * self._scale) + self._off_x
            cy1 = int(y1 * self._scale) + self._off_y
            cx2 = int(x2 * self._scale) + self._off_x
            cy2 = int(y2 * self._scale) + self._off_y
            name = self.label_list[cid] if cid < len(self.label_list) else str(cid)
            txt  = f" ➕ {name} "
            tw   = max(len(txt) * 7, 30)
            self._canvas.create_rectangle(cx1, cy1, cx2, cy2,
                outline=color, width=lw, dash=(8, 4), tags="batch_preview_item")
            self._canvas.create_rectangle(cx1, cy1 - 17, cx1 + tw, cy1,
                fill=color, outline="", tags="batch_preview_item")
            self._canvas.create_text(cx1 + 3, cy1 - 8, text=txt, fill="white",
                font=("Segoe UI", 8, "bold"), anchor=W, tags="batch_preview_item")
