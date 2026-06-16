# tab_yolo.py — YOLO Detection tab
import os
import threading
from tkinter import *
from tkinter import filedialog, messagebox, ttk

from ...core.constants import (BG, CARD, ACCENT, ACCENT2, TEXT, DIM, SUCCESS,
                         F_MAIN, F_BOLD, F_MONO, IMAGE_EXTENSIONS)
import shutil
from ...core.settings import _bind_cfg, _cfg_dir, _CFG, _cfg_save, _bind_history, _push_history, _get_history

try:
    from PIL import Image, ImageDraw, ImageTk
    _PIL_OK = True
except ImportError:
    _PIL_OK = False

try:
    import cv2
    import numpy as np
    _CV2_OK = True
except ImportError:
    _CV2_OK = False

try:
    from ultralytics import YOLO
    _YOLO_OK = True
except ImportError:
    _YOLO_OK = False

try:
    from tkinterdnd2 import DND_FILES
    _DND_OK = True
except ImportError:
    _DND_OK = False

_REVIEW_ICON = {"correct": "✓", "incorrect": "✗", "": "○"}


class YoloTab(Frame):
    def __init__(self, master, root):
        super().__init__(master, bg=BG)
        self.root = root

        self.current_image_path = None
        self.model = None
        self.model2 = None
        self.class_ids = []
        self.image_list = []
        self._photo_ref = None
        self._photo_ref2 = None
        self._last_annotated_bgr = None

        self.v_model_path    = StringVar()
        self.v_model2_path   = StringVar()
        self.v_subfolder     = BooleanVar(value=False)
        self.v_show_original = BooleanVar(value=False)
        self.v_check_folder  = StringVar()
        self.v_conf_thresh   = DoubleVar(value=0.25)
        self.v_conf          = DoubleVar(value=0.30)
        self.v_iou           = DoubleVar(value=0.45)
        self.v_interval      = StringVar(value="2.0")
        self.v_line_width    = IntVar(value=2)
        self.v_font_size     = IntVar(value=11)
        self._v_search       = StringVar()
        self._pil1_full = None
        self._pil1_orig = None
        self._pil2_full = None
        self._last_results1 = None
        self._zoom_factor = 0.0
        self._search_after = None
        self._autoplay_id = None
        self._last_n_det = -1
        self._tree_iid_map = {}
        self._path_to_iid = {}
        self._all_images = []
        self._base_folder = None
        self._active_filter = "all"
        self._review_state = dict(_CFG.get("yolo.review_states", {}))

        _bind_cfg("yolo.model_path",    self.v_model_path)
        _bind_cfg("yolo.check_folder",  self.v_check_folder)
        _bind_cfg("yolo.conf_thresh",   self.v_conf_thresh)
        _bind_cfg("yolo.conf",          self.v_conf)
        _bind_cfg("yolo.iou",           self.v_iou)
        _bind_cfg("yolo.interval",      self.v_interval)
        _bind_cfg("yolo.subfolder",     self.v_subfolder)
        _bind_cfg("yolo.show_original", self.v_show_original)
        _bind_cfg("yolo.line_width",    self.v_line_width)
        _bind_cfg("yolo.font_size",     self.v_font_size)

        self._build()
        self.after(200, self._auto_load_model)
        self.after(300, self._bind_keys)
        self.after(400, self._sync_slider_labels)

    # ================================================================ BUILD ==

    def _build(self):
        self._build_toolbar()
        self._build_content()
        self._build_statusbar()

    def _build_toolbar(self):
        top = Frame(self, bg=CARD, padx=10, pady=8)
        top.pack(fill=X)

        # Row 0 — model 1
        r0 = Frame(top, bg=CARD)
        r0.pack(fill=X)

        Button(r0, text="Chọn Model 1 (.pt)", command=self._select_model,
               bg=ACCENT2, fg="white", font=F_BOLD, relief="flat",
               padx=10, cursor="hand2",
               activebackground=ACCENT, activeforeground="white",
               ).pack(side=LEFT)

        self.lbl_model = Label(r0, text="Chưa chọn model",
                               font=("Segoe UI", 9, "italic"),
                               bg=CARD, fg=DIM)
        self.lbl_model.pack(side=LEFT, padx=(6, 0))

        Button(r0, text="🔍 Validate true/", command=self._validate_true_folder,
               bg="#1a5276", fg="white", font=F_MAIN, relief="flat",
               padx=8, cursor="hand2",
               ).pack(side=RIGHT, padx=(4, 0))

        Button(r0, text="Tính mAP", command=self._start_map_calc,
               bg="#2e7d32", fg="white", font=F_MAIN, relief="flat",
               padx=8, cursor="hand2",
               ).pack(side=RIGHT, padx=(4, 0))

        Button(r0, text="Lưu kết quả", command=self._save_result,
               bg="#555570", fg="white", font=F_MAIN, relief="flat",
               padx=8, cursor="hand2",
               ).pack(side=RIGHT)

        # Row 0a — path input (ảnh hoặc thư mục kiểm tra)
        r0a = Frame(top, bg=CARD)
        r0a.pack(fill=X, pady=(6, 0))

        self.combo_path = ttk.Combobox(r0a, textvariable=self.v_check_folder,
                                       font=F_MAIN)
        self.combo_path.pack(side=LEFT, fill=X, expand=True, padx=(0, 4))
        _bind_history("h.yolo.path", self.combo_path)
        self.combo_path.bind("<Return>", lambda e: self._load_path_input())

        Button(r0a, text="▶ Tải", command=self._load_path_input,
               bg=ACCENT, fg="white", font=F_BOLD, relief="flat",
               padx=10, cursor="hand2",
               activebackground="#c0411a", activeforeground="white",
               ).pack(side=LEFT, padx=(0, 8))

        Button(r0a, text="Chọn Ảnh", command=self._select_image,
               bg=ACCENT, fg="white", font=F_MAIN, relief="flat",
               padx=8, cursor="hand2",
               activebackground="#c0411a", activeforeground="white",
               ).pack(side=LEFT, padx=(0, 4))

        Button(r0a, text="Chọn Thư Mục", command=self._select_folder,
               bg="#2e5fa3", fg="white", font=F_MAIN, relief="flat",
               padx=8, cursor="hand2",
               ).pack(side=LEFT, padx=(0, 4))

        Button(r0a, text="📂", command=self._open_check_folder,
               bg=CARD, fg=TEXT, font=F_MAIN, relief="flat",
               padx=6, cursor="hand2",
               activebackground=ACCENT2, activeforeground="white",
               ).pack(side=LEFT, padx=(0, 6))

        Checkbutton(r0a, text="Quét sub folder", variable=self.v_subfolder,
                    bg=CARD, fg=TEXT, activebackground=CARD,
                    activeforeground=TEXT, selectcolor="#16162a",
                    font=F_MAIN, cursor="hand2",
                    ).pack(side=LEFT, padx=(0, 10))

        Label(r0a, text="→ ✓ true/   ✗ false/",
              font=F_MAIN, bg=CARD, fg=DIM).pack(side=LEFT)

        # Row 0b — model 2
        r0b = Frame(top, bg=CARD)
        r0b.pack(fill=X, pady=(6, 0))

        Button(r0b, text="Chọn Model 2 (.pt)", command=self._select_model2,
               bg="#3a5a3a", fg="white", font=F_BOLD, relief="flat",
               padx=10, cursor="hand2",
               activebackground="#4a7a4a", activeforeground="white",
               ).pack(side=LEFT)

        self.lbl_model2 = Label(r0b, text="Chưa chọn model 2",
                                font=("Segoe UI", 9, "italic"),
                                bg=CARD, fg=DIM)
        self.lbl_model2.pack(side=LEFT, padx=(6, 8))

        Button(r0b, text="Xoá Model 2", command=self._clear_model2,
               bg=CARD, fg=DIM, font=F_MAIN, relief="flat",
               padx=6, cursor="hand2",
               ).pack(side=LEFT)

        # Row 1 — conf slider (new feature: Ngưỡng confidence with resolution 0.05)
        r1 = Frame(top, bg=CARD)
        r1.pack(fill=X, pady=(8, 0))

        Label(r1, text="Ngưỡng confidence:", font=F_BOLD, bg=CARD, fg=TEXT).pack(side=LEFT)
        self.slider_conf_thresh = Scale(
            r1, from_=0.0, to=1.0, resolution=0.05,
            orient=HORIZONTAL, length=200,
            variable=self.v_conf_thresh,
            command=self._on_conf_thresh_change,
            bg=CARD, fg=TEXT, highlightthickness=0,
            troughcolor="#16162a", activebackground=ACCENT,
            relief="flat", bd=0, showvalue=False,
        )
        self.slider_conf_thresh.pack(side=LEFT, padx=(4, 2))
        self.lbl_conf_thresh_val = Label(r1, text="0.25", bg=CARD, fg=ACCENT,
                                         font=F_MONO, width=5)
        self.lbl_conf_thresh_val.pack(side=LEFT, padx=(0, 16))

        Label(r1, text="Conf:", font=F_BOLD, bg=CARD, fg=TEXT).pack(side=LEFT)
        self.slider_conf = ttk.Scale(r1, from_=0.01, to=1.0,
                                      variable=self.v_conf,
                                      orient=HORIZONTAL, length=160,
                                      command=self._on_slider_change)
        self.slider_conf.pack(side=LEFT, padx=(4, 2))
        self.lbl_conf = Label(r1, text="0.30", bg=CARD, fg=TEXT,
                               font=F_MONO, width=5)
        self.lbl_conf.pack(side=LEFT)

        Label(r1, text="  IoU:", font=F_BOLD, bg=CARD, fg=TEXT).pack(side=LEFT)
        self.slider_iou = ttk.Scale(r1, from_=0.01, to=1.0,
                                     variable=self.v_iou,
                                     orient=HORIZONTAL, length=160,
                                     command=self._on_slider_change)
        self.slider_iou.pack(side=LEFT, padx=(4, 2))
        self.lbl_iou = Label(r1, text="0.45", bg=CARD, fg=TEXT,
                              font=F_MONO, width=5)
        self.lbl_iou.pack(side=LEFT)

        # Row 2 — class filter
        r2 = Frame(top, bg=CARD)
        r2.pack(fill=X, pady=(8, 0))

        Label(r2, text="Lọc class (bỏ trống = tất cả):",
              font=F_MAIN, bg=CARD, fg=DIM).pack(anchor=W)

        cls_wrap = Frame(r2, bg=CARD)
        cls_wrap.pack(fill=X)
        sb = Scrollbar(cls_wrap, orient=VERTICAL)
        sb.pack(side=RIGHT, fill=Y)
        self.lb_classes = Listbox(cls_wrap, selectmode=MULTIPLE,
                                   yscrollcommand=sb.set,
                                   height=4, font=F_MONO,
                                   bg="#16162a", fg=TEXT,
                                   selectbackground=ACCENT2,
                                   activestyle="none",
                                   relief="flat", bd=0)
        self.lb_classes.pack(side=LEFT, fill=BOTH, expand=True)
        sb.config(command=self.lb_classes.yview)
        self.lb_classes.bind("<<ListboxSelect>>",
                              lambda _: self._detect_and_display())

        # Row 3 — zoom, original toggle, auto-play, batch export
        r3 = Frame(top, bg=CARD)
        r3.pack(fill=X, pady=(6, 0))

        Label(r3, text="Zoom:", font=F_BOLD, bg=CARD, fg=TEXT).pack(side=LEFT)
        Button(r3, text="−", command=lambda: self._zoom_step(-0.2),
               bg=CARD, fg=TEXT, font=F_BOLD, relief="flat", padx=6,
               cursor="hand2").pack(side=LEFT, padx=(4, 0))
        self.lbl_zoom = Label(r3, text="Fit", bg=CARD, fg=ACCENT,
                              font=F_MONO, width=6)
        self.lbl_zoom.pack(side=LEFT)
        Button(r3, text="+", command=lambda: self._zoom_step(+0.2),
               bg=CARD, fg=TEXT, font=F_BOLD, relief="flat", padx=6,
               cursor="hand2").pack(side=LEFT, padx=(0, 2))
        Button(r3, text="Fit", command=lambda: self._zoom_step(0.0),
               bg="#333355", fg=TEXT, font=F_MAIN, relief="flat",
               padx=6, cursor="hand2").pack(side=LEFT, padx=(2, 16))

        Checkbutton(r3, text="Xem ảnh gốc", variable=self.v_show_original,
                    command=self._render_display,
                    bg=CARD, fg=TEXT, activebackground=CARD,
                    activeforeground=TEXT, selectcolor="#16162a",
                    font=F_MAIN, cursor="hand2").pack(side=LEFT, padx=(0, 16))

        self.btn_autoplay = Button(r3, text="▶ Auto",
                                   command=self._toggle_autoplay,
                                   bg="#2e5fa3", fg="white", font=F_MAIN,
                                   relief="flat", padx=8, cursor="hand2")
        self.btn_autoplay.pack(side=LEFT, padx=(0, 4))
        self.spin_interval = Spinbox(r3, from_=0.5, to=30.0, increment=0.5,
                                      width=5, format="%.1f",
                                      textvariable=self.v_interval,
                                      bg="#16162a", fg=TEXT, font=F_MONO,
                                      buttonbackground=CARD, relief="flat",
                                      insertbackground=TEXT)
        self.spin_interval.pack(side=LEFT, padx=(0, 2))
        Label(r3, text="s", font=F_MAIN, bg=CARD, fg=DIM).pack(side=LEFT,
                                                                padx=(0, 16))

        Button(r3, text="Export tất cả", command=self._batch_export,
               bg="#4a3f00", fg="#ffcc00", font=F_MAIN, relief="flat",
               padx=8, cursor="hand2").pack(side=LEFT)

        Frame(r3, bg=DIM, width=1).pack(side=LEFT, fill=Y, padx=(12, 6))

        Label(r3, text="Nét:", font=F_BOLD, bg=CARD, fg=TEXT).pack(side=LEFT)
        lw_spn = Spinbox(r3, from_=1, to=8, textvariable=self.v_line_width,
                         width=3, bg="#16162a", fg=TEXT, insertbackground=TEXT,
                         buttonbackground=ACCENT2, relief="flat", font=F_MAIN,
                         command=self._on_plot_param_change)
        lw_spn.bind("<Return>",   lambda e: self._on_plot_param_change())
        lw_spn.bind("<FocusOut>", lambda e: self._on_plot_param_change())
        lw_spn.pack(side=LEFT, padx=(2, 8))

        Label(r3, text="Font:", font=F_BOLD, bg=CARD, fg=TEXT).pack(side=LEFT)
        fs_spn = Spinbox(r3, from_=6, to=24, textvariable=self.v_font_size,
                         width=3, bg="#16162a", fg=TEXT, insertbackground=TEXT,
                         buttonbackground=ACCENT2, relief="flat", font=F_MAIN,
                         command=self._on_plot_param_change)
        fs_spn.bind("<Return>",   lambda e: self._on_plot_param_change())
        fs_spn.bind("<FocusOut>", lambda e: self._on_plot_param_change())
        fs_spn.pack(side=LEFT, padx=(2, 0))


    def _build_content(self):
        content = Frame(self, bg=BG)
        content.pack(fill=BOTH, expand=True)

        # Sidebar — image list
        sidebar = Frame(content, bg=CARD, width=200)
        sidebar.pack(side=LEFT, fill=Y, padx=(0, 2))
        sidebar.pack_propagate(False)

        Label(sidebar, text="Danh sách ảnh",
              font=F_BOLD, bg=CARD, fg=TEXT).pack(pady=(8, 2))

        # Search box
        search_row = Frame(sidebar, bg=CARD)
        search_row.pack(fill=X, padx=4, pady=(0, 3))
        Label(search_row, text="🔍", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        Entry(search_row, textvariable=self._v_search,
              bg="#16162a", fg=TEXT, insertbackground=TEXT,
              relief="flat", font=F_MONO, bd=2).pack(side=LEFT, fill=X, expand=True, padx=(2, 0))
        self._v_search.trace_add("write", lambda *_: self._schedule_search())

        # Filter buttons
        filter_row = Frame(sidebar, bg=CARD)
        filter_row.pack(fill=X, padx=4, pady=(0, 3))
        self._filter_btns = {}
        for code, lbl, fg in [
            ("all",        "All",  TEXT),
            ("correct",    "✓",   "#4caf50"),
            ("incorrect",  "✗",   ACCENT),
            ("unreviewed", "?",    DIM),
        ]:
            b = Button(filter_row, text=lbl, width=4,
                       command=lambda c=code: self._apply_filter(c),
                       bg=CARD, fg=fg, font=F_MAIN, relief="flat",
                       cursor="hand2", activebackground="#252540",
                       activeforeground=fg)
            b.pack(side=LEFT, padx=1)
            self._filter_btns[code] = b
        self._filter_btns["all"].config(relief="sunken", bg="#252540")

        tree_frame = Frame(sidebar, bg=CARD)
        tree_frame.pack(fill=BOTH, expand=True, padx=2, pady=(0, 6))

        sb2 = Scrollbar(tree_frame, orient=VERTICAL)
        sb2.pack(side=RIGHT, fill=Y)
        sb2h = Scrollbar(tree_frame, orient=HORIZONTAL)
        sb2h.pack(side=BOTTOM, fill=X)

        style = ttk.Style()
        style.configure("YoloTree.Treeview",
                        background="#16162a", foreground=TEXT,
                        fieldbackground="#16162a", borderwidth=0,
                        rowheight=20, font=F_MAIN)
        style.map("YoloTree.Treeview",
                  background=[("selected", ACCENT2)],
                  foreground=[("selected", "white")])
        style.configure("YoloTree.Treeview.Heading", background=CARD,
                        foreground=TEXT)

        self.tree_images = ttk.Treeview(tree_frame, style="YoloTree.Treeview",
                                         selectmode="browse", show="tree",
                                         yscrollcommand=sb2.set,
                                         xscrollcommand=sb2h.set)
        self.tree_images.pack(fill=BOTH, expand=True)
        sb2.config(command=self.tree_images.yview)
        sb2h.config(command=self.tree_images.xview)
        self.tree_images.bind("<<TreeviewSelect>>", self._on_image_select)
        self.tree_images.tag_configure("correct",    foreground="#4caf50")
        self.tree_images.tag_configure("incorrect",  foreground=ACCENT)
        self.tree_images.tag_configure("unreviewed", foreground=TEXT)
        self.tree_images.tag_configure("folder",     foreground=DIM)

        # Right — result panels area
        right = Frame(content, bg=BG)
        right.pack(side=LEFT, fill=BOTH, expand=True)

        self.lbl_result = Label(right, text="", font=F_BOLD,
                                 bg=BG, fg=TEXT, anchor=W)
        self.lbl_result.pack(fill=X, padx=6, pady=(4, 0))

        # Mark buttons
        mark_row = Frame(right, bg=BG)
        mark_row.pack(fill=X, padx=6, pady=(2, 0))
        Button(mark_row, text="✓ Đúng  [Enter]",
               command=lambda: self._mark_review("correct"),
               bg="#1a3a1a", fg="#4caf50", font=F_MAIN, relief="flat",
               padx=8, cursor="hand2").pack(side=LEFT, padx=(0, 4))
        Button(mark_row, text="✗ Sai  [Del]",
               command=lambda: self._mark_review("incorrect"),
               bg="#3a1a1a", fg=ACCENT, font=F_MAIN, relief="flat",
               padx=8, cursor="hand2").pack(side=LEFT, padx=(0, 4))
        Button(mark_row, text="↺ Bỏ đánh dấu",
               command=lambda: self._mark_review(""),
               bg=CARD, fg=DIM, font=F_MAIN, relief="flat",
               padx=6, cursor="hand2").pack(side=LEFT)
        self.lbl_mark_state = Label(mark_row, text="", font=F_MONO,
                                     bg=BG, fg=DIM)
        self.lbl_mark_state.pack(side=LEFT, padx=(12, 0))

        # Panel container for single/side-by-side display
        self.panels_frame = Frame(right, bg=BG)
        self.panels_frame.pack(fill=BOTH, expand=True)

        # Panel 1
        self.panel1_frame = Frame(self.panels_frame, bg=BG)
        self.panel1_frame.pack(side=LEFT, fill=BOTH, expand=True)

        self.lbl_panel1_title = Label(self.panel1_frame, text="",
                                       font=F_BOLD, bg=CARD, fg=ACCENT2,
                                       anchor=CENTER, pady=3)
        self.lbl_panel1_title.pack(fill=X)

        self.canvas = Label(self.panel1_frame,
                             text="Chọn ảnh để nhận diện",
                             bg="#0d0d1a", fg=DIM,
                             font=("Segoe UI", 14),
                             compound="center",
                             relief="flat")
        self.canvas.pack(fill=BOTH, expand=True, padx=0, pady=2)

        # Panel 2 (hidden by default)
        self.panel2_frame = Frame(self.panels_frame, bg=BG)

        self.lbl_panel2_title = Label(self.panel2_frame, text="",
                                       font=F_BOLD, bg=CARD, fg="#4a8a4a",
                                       anchor=CENTER, pady=3)
        self.lbl_panel2_title.pack(fill=X)

        self.canvas2 = Label(self.panel2_frame,
                              text="",
                              bg="#0d0d1a", fg=DIM,
                              font=("Segoe UI", 14),
                              compound="center",
                              relief="flat")
        self.canvas2.pack(fill=BOTH, expand=True, padx=0, pady=2)

        self.canvas.bind("<Control-MouseWheel>", self._on_canvas_scroll)
        self.canvas.bind("<Double-Button-1>",   self._on_canvas1_zoom)
        self.canvas2.bind("<Double-Button-1>",  self._on_canvas2_zoom)

        if _DND_OK:
            try:
                self.canvas.drop_target_register(DND_FILES)
                self.canvas.dnd_bind("<<Drop>>", self._on_drop)
            except Exception:
                pass

    def _build_statusbar(self):
        self.v_status = StringVar(value="Sẵn sàng")
        Label(self, textvariable=self.v_status,
              font=F_MAIN, bg=CARD, fg=DIM, anchor=W, padx=8,
              ).pack(fill=X, side=BOTTOM)

    # ============================================================= DRAG-DROP ==

    def _on_drop(self, event):
        paths = self.root.tk.splitlist(event.data)
        if not paths:
            return
        if len(paths) == 1 and os.path.isdir(paths[0]):
            self._load_folder(paths[0])
            return
        imgs = [p for p in paths
                if os.path.isfile(p)
                and os.path.splitext(p)[1].lower() in IMAGE_EXTENSIONS]
        if not imgs:
            messagebox.showwarning("Không hỗ trợ",
                                   "Chỉ hỗ trợ ảnh hoặc thư mục chứa ảnh.",
                                   parent=self.root)
            return
        self._load_image_list(sorted(imgs))

    # ============================================================ FILE LOAD ==

    def _select_model(self):
        path = filedialog.askopenfilename(
            title="Chọn file model YOLO 1 (.pt)",
            filetypes=[("PyTorch Model", "*.pt"), ("All files", "*.*")],
            initialdir=_cfg_dir("yolo.model_dir") or None,
            parent=self.root)
        if path:
            _push_history("h.yolo.model", path)
            self._load_model(path)

    def _select_model2(self):
        if not _YOLO_OK:
            messagebox.showerror("Thiếu thư viện",
                                  "pip install ultralytics", parent=self.root)
            return
        path = filedialog.askopenfilename(
            title="Chọn file model YOLO 2 (.pt)",
            filetypes=[("PyTorch Model", "*.pt"), ("All files", "*.*")],
            initialdir=_cfg_dir("yolo.model_dir") or None,
            parent=self.root)
        if not path:
            return
        _push_history("h.yolo.model2", path)
        try:
            self.model2 = YOLO(path)
            self.v_model2_path.set(path)
            self.lbl_model2.config(
                text=f"  {os.path.basename(path)}", fg="#4caf50")
            if self.current_image_path and self.model:
                self._detect_and_display()
        except Exception as e:
            messagebox.showerror("Lỗi load model 2", str(e), parent=self.root)

    def _clear_model2(self):
        self.model2 = None
        self.v_model2_path.set("")
        self.lbl_model2.config(text="Chưa chọn model 2", fg=DIM)
        self.panel2_frame.pack_forget()
        self.lbl_panel1_title.config(text="")
        if self.current_image_path and self.model:
            self._detect_and_display()

    def _load_model(self, path: str):
        if not _YOLO_OK:
            messagebox.showerror("Thiếu thư viện",
                                  "pip install ultralytics", parent=self.root)
            return
        try:
            self.model = YOLO(path)
            self.v_model_path.set(path)
            self.lbl_model.config(
                text=f"  {os.path.basename(path)}", fg=SUCCESS)
            self._update_class_list()
            if self.current_image_path:
                self._detect_and_display()
        except Exception as e:
            messagebox.showerror("Lỗi load model", str(e), parent=self.root)

    def _auto_load_model(self):
        saved = self.v_model_path.get()
        if saved and os.path.isfile(saved):
            self._load_model(saved)
        else:
            default = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "yolo11n.pt")
            if os.path.isfile(default):
                self._load_model(default)

    def _update_class_list(self):
        self.lb_classes.delete(0, END)
        self.class_ids.clear()
        if self.model and hasattr(self.model, "names"):
            for cid, cname in sorted(self.model.names.items()):
                self.class_ids.append(cid)
                self.lb_classes.insert(END, f"[{cid}] {cname}")

    def _update_path_combo(self, path: str):
        self.v_check_folder.set(path)
        _push_history("h.yolo.path", path)
        self.combo_path["values"] = _get_history("h.yolo.path")

    def _load_path_input(self):
        p = self.v_check_folder.get().strip()
        if not p:
            return
        if not self.model:
            messagebox.showwarning("Chưa có model", "Vui lòng chọn model trước.",
                                   parent=self.root)
            return
        if os.path.isdir(p):
            _push_history("h.yolo.path", p)
            self.combo_path["values"] = _get_history("h.yolo.path")
            self._load_folder(p)
        elif os.path.isfile(p):
            _push_history("h.yolo.path", p)
            self.combo_path["values"] = _get_history("h.yolo.path")
            self._load_image_list([p])
        else:
            messagebox.showwarning("Không tìm thấy",
                                   f"Đường dẫn không hợp lệ:\n{p}", parent=self.root)

    def _select_image(self):
        if not self.model:
            messagebox.showwarning("Chưa có model",
                                   "Vui lòng chọn model trước.", parent=self.root)
            return
        cur = self.v_check_folder.get().strip()
        init = (os.path.dirname(cur) if cur and os.path.isfile(cur)
                else cur if cur and os.path.isdir(cur)
                else _cfg_dir("yolo.last_image_dir") or None)
        path = filedialog.askopenfilename(
            title="Chọn ảnh",
            initialdir=init,
            filetypes=[("Image Files", "*.jpg *.jpeg *.png *.bmp *.webp")],
            parent=self.root)
        if path:
            self._update_path_combo(path)
            self._load_image_list([path])

    def _open_check_folder(self):
        p = self.v_check_folder.get().strip()
        d = p if os.path.isdir(p) else os.path.dirname(p) if p else ""
        if d and os.path.isdir(d):
            os.startfile(d)

    def _select_folder(self):
        if not self.model:
            messagebox.showwarning("Chưa có model",
                                   "Vui lòng chọn model trước.", parent=self.root)
            return
        cur = self.v_check_folder.get().strip()
        init = (cur if cur and os.path.isdir(cur)
                else os.path.dirname(cur) if cur
                else _cfg_dir("yolo.check_folder") or None)
        folder = filedialog.askdirectory(
            title="Chọn thư mục kiểm tra",
            initialdir=init,
            parent=self.root)
        if folder:
            self._update_path_combo(folder)
            self._load_folder(folder)

    def _scan_images(self, folder: str) -> list:
        """Trả về list ảnh trực tiếp trong folder (không đệ quy vào true/false)."""
        if not folder or not os.path.isdir(folder):
            return []
        return sorted([
            os.path.join(folder, f) for f in os.listdir(folder)
            if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS
        ])

    def _load_folder(self, folder: str):
        self._base_folder = folder
        _SKIP = {"true", "false"}
        if self.v_subfolder.get():
            files = sorted([
                os.path.join(root, f)
                for root, dirs, fnames in os.walk(folder)
                for f in fnames
                if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS
                and os.path.basename(root) not in _SKIP
            ])
            # prune true/false from os.walk in-place
        else:
            files = sorted([
                os.path.join(folder, f)
                for f in os.listdir(folder)
                if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS
            ])
        if not files:
            messagebox.showinfo("Thông báo",
                                "Không tìm thấy ảnh trong thư mục!", parent=self.root)
            return
        self._load_image_list(files)

    def _load_image_list(self, files: list):
        self._all_images = list(files)
        if not self._base_folder and files:
            self._base_folder = os.path.dirname(files[0])
        self._active_filter = "all"
        for code, btn in self._filter_btns.items():
            btn.config(relief="sunken" if code == "all" else "flat",
                       bg="#252540" if code == "all" else CARD)
        self._rebuild_tree(files)
        self._update_filter_counts()
        if files:
            self._open_image(files[0])

    def _rebuild_tree(self, files: list):
        """Rebuild the sidebar tree from a (possibly filtered) file list."""
        self.image_list = list(files)
        self._tree_iid_map = {}
        self._path_to_iid = {}
        tree = self.tree_images
        tree.delete(*tree.get_children())

        use_hierarchy = (len(self._all_images) > 1
                         and self.v_subfolder.get()
                         and self._all_images)
        base_dir = os.path.commonpath(self._all_images) if use_hierarchy else None

        if base_dir and files:
            folder_iids = {}
            for f in files:
                state = _path_review_state(f)
                tag = state or "unreviewed"
                icon = _REVIEW_ICON[state]
                try:
                    rel = os.path.relpath(f, base_dir)
                    parts = rel.replace("\\", "/").split("/")
                except ValueError:
                    parts = [os.path.basename(f)]
                parent_iid = ""
                for depth, part in enumerate(parts[:-1]):
                    folder_key = "/".join(parts[:depth + 1])
                    if folder_key not in folder_iids:
                        iid = tree.insert(parent_iid, END,
                                          text=f"\U0001f4c1 {part}",
                                          open=True, tags=("folder",))
                        folder_iids[folder_key] = iid
                    parent_iid = folder_iids[folder_key]
                iid = tree.insert(parent_iid, END,
                                  text=f"{icon} {parts[-1]}", tags=(tag,))
                self._tree_iid_map[iid] = f
                self._path_to_iid[f] = iid
        else:
            for f in files:
                state = _path_review_state(f)
                tag = state or "unreviewed"
                icon = _REVIEW_ICON[state]
                iid = tree.insert("", END,
                                  text=f"{icon} {os.path.basename(f)}", tags=(tag,))
                self._tree_iid_map[iid] = f
                self._path_to_iid[f] = iid

        # Re-select current image if still in this list
        iid = self._path_to_iid.get(self.current_image_path)
        if iid:
            tree.selection_set(iid)
            tree.see(iid)

    def _schedule_search(self):
        if self._search_after:
            self.after_cancel(self._search_after)
        self._search_after = self.after(300,
            lambda: self._apply_filter(self._active_filter))

    def _apply_filter(self, filter_type: str):
        self._active_filter = filter_type
        for code, btn in self._filter_btns.items():
            btn.config(relief="sunken" if code == filter_type else "flat",
                       bg="#252540" if code == filter_type else CARD)
        base = self._base_folder
        if filter_type == "correct":
            filtered = self._scan_images(os.path.join(base, "true")) if base else []
        elif filter_type == "incorrect":
            filtered = self._scan_images(os.path.join(base, "false")) if base else []
        elif filter_type == "unreviewed":
            filtered = list(self._all_images)
        else:  # "all"
            true_imgs  = self._scan_images(os.path.join(base, "true"))  if base else []
            false_imgs = self._scan_images(os.path.join(base, "false")) if base else []
            filtered = list(self._all_images) + true_imgs + false_imgs
        search = self._v_search.get().strip().lower()
        if search:
            filtered = [f for f in filtered
                        if search in os.path.basename(f).lower()]
        self._rebuild_tree(filtered)

    def _update_filter_counts(self):
        if not hasattr(self, "_filter_btns"):
            return
        base = self._base_folder
        n_todo = len(self._all_images)
        n_ok   = len(self._scan_images(os.path.join(base, "true")))  if base else 0
        n_bad  = len(self._scan_images(os.path.join(base, "false"))) if base else 0
        n_all  = n_todo + n_ok + n_bad
        for code, label in [("all",        f"All({n_all})"),
                             ("correct",    f"✓({n_ok})"),
                             ("incorrect",  f"✗({n_bad})"),
                             ("unreviewed", f"?({n_todo})")]:
            self._filter_btns[code].config(text=label)

    def _save_image_and_label(self, path: str, state: str) -> bool:
        """Move image + write detection label vào true/ hoặc false/ subfolder.
        Trả về True nếu di chuyển thành công."""
        if not os.path.isfile(path):
            return False
        sub = "true" if state == "correct" else "false"
        # Luôn dùng _base_folder; nếu ảnh đang ở true/ hoặc false/ thì dùng grandparent
        parent_name = os.path.basename(os.path.dirname(path))
        if parent_name in ("true", "false"):
            root = os.path.dirname(os.path.dirname(path))
        else:
            root = self._base_folder or os.path.dirname(path)
        dest_dir = os.path.join(root, sub)
        try:
            os.makedirs(dest_dir, exist_ok=True)
            dest_img = os.path.join(dest_dir, os.path.basename(path))
            shutil.move(path, dest_img)

            base = os.path.splitext(os.path.basename(path))[0]
            boxes = (self._last_results1[0].boxes
                     if self._last_results1 is not None else None)
            with open(os.path.join(dest_dir, f"{base}.txt"), "w", encoding="utf-8") as f:
                if boxes is not None and len(boxes):
                    for box in boxes:
                        cid = int(box.cls[0])
                        cx, cy, bw, bh = box.xywhn[0].tolist()
                        f.write(f"{cid} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")

            icon = "✓" if state == "correct" else "✗"
            self.v_status.set(
                f"{icon} Đã chuyển vào {sub}/: {os.path.basename(path)}")
            return True
        except Exception as e:
            self.v_status.set(f"Lỗi di chuyển: {e}")
            return False

    def _mark_review(self, state: str):
        path = self.current_image_path
        if not path:
            return

        # Update status label
        icons = {"correct": "✓ Đúng", "incorrect": "✗ Sai", "": "↺ Đã xóa"}
        self.lbl_mark_state.config(
            text=icons.get(state, ""),
            fg=("#4caf50" if state == "correct"
                else ACCENT if state == "incorrect" else DIM))

        if state in ("correct", "incorrect"):
            moved = self._save_image_and_label(path, state)
            if moved:
                # Remove from all tracking data structures
                self._review_state.pop(path, None)
                _CFG["yolo.review_states"] = self._review_state
                _cfg_save()

                old_idx = (self.image_list.index(path)
                           if path in self.image_list else 0)
                # Remove from unreviewed list if it was there
                if path in self._all_images:
                    self._all_images.remove(path)
                self.current_image_path = None
                self._last_results1 = None

                self._apply_filter(self._active_filter)
                self._update_filter_counts()
                if self.image_list:
                    next_idx = min(old_idx, len(self.image_list) - 1)
                    self._open_image(self.image_list[next_idx])
                return

        # No move (unmark or move failed) — update state + tag only
        if state:
            self._review_state[path] = state
        else:
            self._review_state.pop(path, None)
        _CFG["yolo.review_states"] = self._review_state
        _cfg_save()

        iid = self._path_to_iid.get(path)
        if iid and self.tree_images.exists(iid):
            icon = _REVIEW_ICON[state]
            old_text = self.tree_images.item(iid, "text")
            bare = old_text[2:] if len(old_text) > 2 else old_text
            self.tree_images.item(iid,
                                  text=f"{icon} {bare}",
                                  tags=(state or "unreviewed",))
        self._update_filter_counts()

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
        label = f"{pos}/{n}  " if n else ""
        self.v_status.set(f"{label}{os.path.basename(path)}")
        self._detect_and_display()

    def _is_active(self):
        """Trả về True nếu YOLO tab đang được chọn trong Notebook."""
        try:
            w = self
            while w is not None:
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
        """Chỉ bind các phím đặc thù YOLO; dùng guard _is_active để không
        override binding của tab khác (BBox Editor, Checker…).
        ←/→ KHÔNG bind ở đây — app.py đã xử lý qua _prev_image/_next_image."""
        def _guard(fn):
            def _inner(*_):
                if self._is_active():
                    fn()
                    return "break"
            return _inner

        self.root.bind("<Return>", _guard(lambda: self._mark_review("correct")), "+")
        self.root.bind("<Delete>", _guard(lambda: self._mark_review("incorrect")), "+")
        self.root.bind("<space>",  _guard(lambda: self._toggle_autoplay()), "+")

    # ── Aliases cho app.py global routing ────────────────────────────────
    def _prev_image(self): self._nav_image(-1)
    def _next_image(self): self._nav_image(+1)

    def select_image(self):
        """Alias không underscore — Ctrl+O routing từ app.py."""
        self._select_image()

    def _run_detect(self):
        """F5 routing từ app.py — detect ảnh hiện tại nếu đã load."""
        if self.current_image_path and self.model:
            self._open_image(self.current_image_path)

    def _on_delete(self):
        """Delete routing từ app.py — mark ảnh hiện tại là incorrect."""
        if self._is_active():
            self._mark_review("incorrect")

    def _on_return(self):
        """Return routing từ app.py — mark ảnh hiện tại là correct."""
        if self._is_active():
            self._mark_review("correct")

    def _on_canvas1_zoom(self, _event=None):
        pil = self._pil1_full or self._pil1_orig
        if pil is None:
            return
        from ...core.ui_helpers import _zoom_image_window
        fname = os.path.basename(self.current_image_path) if self.current_image_path else "ảnh"
        _zoom_image_window(self.root, pil, fname)

    def _on_canvas2_zoom(self, _event=None):
        if self._pil2_full is None:
            return
        from ...core.ui_helpers import _zoom_image_window
        fname = os.path.basename(self.current_image_path) if self.current_image_path else "ảnh"
        _zoom_image_window(self.root, self._pil2_full, f"{fname} — Model 2")

    def _nav_image(self, step: int):
        if not self.image_list:
            return
        if self.current_image_path in self.image_list:
            idx = self.image_list.index(self.current_image_path)
        else:
            idx = 0
        new_idx = (idx + step) % len(self.image_list)
        self._open_image(self.image_list[new_idx])

    def _on_image_select(self, _event=None):
        sel = self.tree_images.selection()
        if not sel:
            return
        iid = sel[0]
        path = self._tree_iid_map.get(iid)
        if path and path != self.current_image_path:
            self._open_image(path)

    # ======================================================== ZOOM / RENDER ==

    def _render_display(self):
        """Re-render canvas from stored PIL with current zoom & original settings."""
        if not _PIL_OK:
            return
        pil = (self._pil1_orig
               if (self.v_show_original.get() and self._pil1_orig)
               else self._pil1_full)
        if pil is None:
            return
        self.root.update_idletasks()
        w = max(self.canvas.winfo_width(), 800)
        h = max(self.canvas.winfo_height(), 400)
        if self._zoom_factor == 0.0:
            img = self._resize_pil(pil, w, h)
            self.lbl_zoom.config(text="Fit")
        else:
            nw = max(1, int(pil.width * self._zoom_factor))
            nh = max(1, int(pil.height * self._zoom_factor))
            img = pil.resize((nw, nh), Image.Resampling.LANCZOS)
            self.lbl_zoom.config(text=f"{int(self._zoom_factor * 100)}%")
        self._photo_ref = ImageTk.PhotoImage(image=img)
        self.canvas.config(image=self._photo_ref, text="")

    def _zoom_step(self, delta: float):
        """delta=0.0 resets to fit; otherwise shifts zoom factor."""
        if delta == 0.0:
            self._zoom_factor = 0.0
        else:
            if self._zoom_factor == 0.0:
                pil = self._pil1_full
                if pil and self.canvas.winfo_width() > 1:
                    fw = max(self.canvas.winfo_width(), 800) - 10
                    fh = max(self.canvas.winfo_height(), 400) - 10
                    self._zoom_factor = min(fw / pil.width, fh / pil.height)
                else:
                    self._zoom_factor = 1.0
            self._zoom_factor = max(0.05, min(8.0, self._zoom_factor + delta))
        self._render_display()

    def _on_canvas_scroll(self, event):
        delta = 0.15 if event.delta > 0 else -0.15
        self._zoom_step(delta)

    # ======================================================== AUTO-PLAY ==

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
            interval = float(self.spin_interval.get())
        except ValueError:
            interval = 2.0
        ms = max(200, int(interval * 1000))
        self._autoplay_id = self.root.after(ms, self._autoplay_step)

    def _autoplay_step(self):
        if self._autoplay_id is None:
            return
        self._nav_image(+1)
        self._schedule_autoplay()

    # ======================================================== BATCH EXPORT ==

    def _batch_export(self):
        if not self.model:
            messagebox.showwarning("Chưa có model",
                                   "Vui lòng chọn model trước.", parent=self.root)
            return
        if not self.image_list:
            messagebox.showwarning("Chưa có ảnh",
                                   "Vui lòng chọn thư mục ảnh trước.", parent=self.root)
            return
        if not _CV2_OK:
            messagebox.showerror("Thiếu thư viện",
                                  "pip install opencv-python", parent=self.root)
            return

        out_dir = filedialog.askdirectory(
            title="Chọn thư mục lưu kết quả",
            initialdir=_cfg_dir("yolo.export_dir") or None,
            parent=self.root)
        if not out_dir:
            return
        _CFG["yolo.export_dir"] = out_dir
        _cfg_save()

        save_labels = messagebox.askyesno(
            "Lưu nhãn YOLO",
            "Lưu kèm file nhãn .txt (YOLO format) không?",
            parent=self.root)

        popup = Toplevel(self.root)
        popup.title("Export kết quả — Batch Detection")
        popup.configure(bg=BG)
        popup.geometry("560x320")

        Label(popup, text=f"Đang xử lý {len(self.image_list)} ảnh ...",
              font=F_BOLD, bg=BG, fg=TEXT).pack(pady=(12, 4))

        pb = ttk.Progressbar(popup, mode="determinate",
                              maximum=len(self.image_list))
        pb.pack(fill=X, padx=16, pady=(0, 4))

        v_prog = StringVar(value="0 / 0")
        Label(popup, textvariable=v_prog,
              font=F_MONO, bg=BG, fg=DIM).pack()

        txt_frame = Frame(popup, bg=BG)
        txt_frame.pack(fill=BOTH, expand=True, padx=8, pady=8)
        sb_log = Scrollbar(txt_frame, orient=VERTICAL)
        sb_log.pack(side=RIGHT, fill=Y)
        log_text = Text(txt_frame, bg="#0d0d1a", fg=TEXT, font=F_MONO,
                        relief="flat", bd=0, yscrollcommand=sb_log.set,
                        state=DISABLED)
        log_text.pack(fill=BOTH, expand=True)
        sb_log.config(command=log_text.yview)

        def append(line):
            log_text.config(state=NORMAL)
            log_text.insert(END, line + "\n")
            log_text.see(END)
            log_text.config(state=DISABLED)

        def run():
            sel_cls = self._get_sel_classes()
            conf_val = max(self.v_conf_thresh.get(), self.slider_conf.get())
            iou_val = self.slider_iou.get()
            ok = 0
            for i, img_path in enumerate(self.image_list):
                self.root.after(0, lambda v=i: pb.config(value=v))
                self.root.after(0, lambda v=i + 1, t=len(self.image_list):
                                v_prog.set(f"{v} / {t}"))
                try:
                    res = self.model.predict(
                        source=img_path, classes=sel_cls,
                        conf=conf_val, iou=iou_val,
                        imgsz=640, agnostic_nms=True, verbose=False)
                    annotated = res[0].plot(
                        line_width=max(1, self.v_line_width.get()),
                        font_size=max(6, self.v_font_size.get()),
                    )
                    base = os.path.splitext(os.path.basename(img_path))[0]
                    cv2.imwrite(os.path.join(out_dir, f"{base}_det.jpg"), annotated)
                    if save_labels:
                        boxes = res[0].boxes
                        with open(os.path.join(out_dir, f"{base}_det.txt"),
                                  "w", encoding="utf-8") as f:
                            if boxes is not None and len(boxes):
                                for box in boxes:
                                    cid = int(box.cls[0])
                                    cx, cy, bw, bh = box.xywhn[0].tolist()
                                    f.write(f"{cid} {cx:.6f} {cy:.6f}"
                                            f" {bw:.6f} {bh:.6f}\n")
                    n = len(res[0].boxes) if res[0].boxes else 0
                    self.root.after(0, lambda nm=os.path.basename(img_path),
                                    nd=n: append(f"  OK  {nm}  ({nd} obj)"))
                    ok += 1
                except Exception as ex:
                    self.root.after(0, lambda m=str(ex),
                                    nm=os.path.basename(img_path):
                                    append(f"  ERR {nm}: {m}"))
            self.root.after(0, lambda: pb.config(value=len(self.image_list)))
            self.root.after(0, lambda:
                            append(f"\nHoan tat: {ok}/{len(self.image_list)}"
                                   f" anh  ->  {out_dir}"))

        threading.Thread(target=run, daemon=True).start()

    # =========================================================== DETECTION ==

    def _sync_slider_labels(self):
        self.lbl_conf_thresh_val.config(text=f"{self.v_conf_thresh.get():.2f}")
        self.lbl_conf.config(text=f"{self.v_conf.get():.2f}")
        self.lbl_iou.config(text=f"{self.v_iou.get():.2f}")

    def _on_conf_thresh_change(self, _=None):
        self.lbl_conf_thresh_val.config(text=f"{self.v_conf_thresh.get():.2f}")
        if self.current_image_path and self.model:
            self._detect_and_display()

    def _on_slider_change(self, _=None):
        self.lbl_conf.config(text=f"{self.v_conf.get():.2f}")
        self.lbl_iou.config(text=f"{self.v_iou.get():.2f}")
        if self.current_image_path:
            self._detect_and_display()

    def _get_sel_classes(self):
        sel_idx = self.lb_classes.curselection()
        return [self.class_ids[i] for i in sel_idx] if sel_idx else None

    def _run_model(self, mdl, image_path, sel_cls):
        conf = max(self.v_conf_thresh.get(), self.slider_conf.get())
        return mdl.predict(
            source=image_path,
            classes=sel_cls,
            conf=conf,
            iou=self.slider_iou.get(),
            imgsz=640,
            agnostic_nms=True,
            verbose=False,
        )

    def _results_summary(self, results, model_names):
        boxes = results[0].boxes
        n_det = len(boxes) if boxes is not None else 0
        if n_det > 0:
            counts = {}
            for cls_id in boxes.cls.tolist():
                name = model_names[int(cls_id)]
                counts[name] = counts.get(name, 0) + 1
            summary = "  |  ".join(f"{n}: {c}" for n, c in counts.items())
            return n_det, summary
        return 0, ""

    def _on_plot_param_change(self):
        if self.current_image_path and self.model:
            self._detect_and_display()

    def _annotated_to_pil(self, results):
        annotated = results[0].plot(
            line_width=max(1, self.v_line_width.get()),
            font_size=max(6, self.v_font_size.get()),
        )
        rgb = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
        return Image.fromarray(rgb), annotated

    def _resize_pil(self, pil_img, w, h):
        copy = pil_img.copy()
        copy.thumbnail((w - 10, h - 10), Image.Resampling.LANCZOS)
        return copy

    def _detect_and_display(self):
        if not self.current_image_path or not self.model:
            return
        if not _PIL_OK or not _CV2_OK:
            self.lbl_result.config(
                text="Cần cài: pip install Pillow opencv-python", fg=ACCENT)
            return
        try:
            sel_cls = self._get_sel_classes()
            results1 = self._run_model(self.model, self.current_image_path, sel_cls)
            n_det, summary = self._results_summary(results1, self.model.names)

            pil1, ann1_bgr = self._annotated_to_pil(results1)
            self._last_annotated_bgr = ann1_bgr
            self._last_results1 = results1

            self.root.update_idletasks()

            if self.model2 is not None:
                # Side-by-side mode
                self.panel2_frame.pack(side=LEFT, fill=BOTH, expand=True)
                m1_name = os.path.basename(self.v_model_path.get())
                m2_name = os.path.basename(self.v_model2_path.get())

                results2 = self._run_model(self.model2, self.current_image_path, sel_cls)
                n_det2, summary2 = self._results_summary(results2, self.model2.names)
                pil2, _ = self._annotated_to_pil(results2)

                self.lbl_panel1_title.config(
                    text=f"Model 1: {m1_name}  ({n_det} obj)")
                self.lbl_panel2_title.config(
                    text=f"Model 2: {m2_name}  ({n_det2} obj)")

                half_w = max(self.panels_frame.winfo_width() // 2, 400)
                ph = max(self.panels_frame.winfo_height(), 400)

                pil1r = self._resize_pil(pil1, half_w, ph)
                pil2r = self._resize_pil(pil2, half_w, ph)

                self._pil2_full = pil2
                self._photo_ref = ImageTk.PhotoImage(image=pil1r)
                self._photo_ref2 = ImageTk.PhotoImage(image=pil2r)
                self.canvas.config(image=self._photo_ref, text="")
                self.canvas2.config(image=self._photo_ref2, text="")

                txt = (f"Model1: {n_det} obj"
                       + (f"  [{summary}]" if summary else "")
                       + f"    Model2: {n_det2} obj"
                       + (f"  [{summary2}]" if summary2 else ""))
                self.lbl_result.config(text=txt, fg=SUCCESS if n_det or n_det2 else DIM)
            else:
                # Single panel mode
                self.panel2_frame.pack_forget()
                self.lbl_panel1_title.config(text="")

                self._pil1_full = pil1
                self._pil1_orig = Image.open(self.current_image_path).convert("RGB")
                self._last_n_det = n_det
                self._render_display()

                if n_det > 0:
                    self.lbl_result.config(
                        text=f"Phát hiện {n_det} đối tượng  —  {summary}",
                        fg=SUCCESS)
                else:
                    self.lbl_result.config(
                        text="Không phát hiện đối tượng nào", fg=DIM)

        except Exception as e:
            self.lbl_result.config(text=f"Lỗi: {e}", fg=ACCENT)

    # ================================================ UNDETECTED SAVE ==

    # ======================================================= SAVE RESULT ==

    def _save_result(self):
        if self._last_annotated_bgr is None:
            messagebox.showwarning("Chưa có kết quả",
                                   "Vui lòng chạy detection trước.", parent=self.root)
            return
        if not _CV2_OK:
            messagebox.showerror("Thiếu thư viện",
                                  "pip install opencv-python", parent=self.root)
            return

        save_dir = filedialog.askdirectory(
            title="Chọn thư mục lưu kết quả", parent=self.root)
        if not save_dir:
            return

        base = os.path.splitext(os.path.basename(self.current_image_path))[0]
        img_out = os.path.join(save_dir, f"{base}_detected.jpg")
        cv2.imwrite(img_out, self._last_annotated_bgr)

        save_txt = messagebox.askyesno(
            "Lưu nhãn YOLO",
            "Bạn có muốn lưu file nhãn .txt định dạng YOLO không?",
            parent=self.root)

        if save_txt and self.model and self.current_image_path:
            try:
                sel_cls = self._get_sel_classes()
                results = self._run_model(self.model, self.current_image_path, sel_cls)
                boxes = results[0].boxes
                txt_out = os.path.join(save_dir, f"{base}_detected.txt")
                orig_h, orig_w = self._last_annotated_bgr.shape[:2]
                with open(txt_out, "w", encoding="utf-8") as f:
                    if boxes is not None and len(boxes):
                        for box in boxes:
                            cls_id = int(box.cls[0])
                            xywhn = box.xywhn[0].tolist()
                            cx, cy, bw, bh = xywhn
                            f.write(f"{cls_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")
                messagebox.showinfo(
                    "Đã lưu",
                    f"Ảnh: {img_out}\nNhãn: {txt_out}",
                    parent=self.root)
            except Exception as e:
                messagebox.showerror("Lỗi lưu nhãn", str(e), parent=self.root)
        else:
            messagebox.showinfo("Đã lưu", f"Ảnh: {img_out}", parent=self.root)

    # ========================================================== MAP CALC ==

    def _start_map_calc(self):
        if not self.model:
            messagebox.showwarning("Chưa có model",
                                   "Vui lòng chọn model trước.", parent=self.root)
            return
        if not _YOLO_OK:
            messagebox.showerror("Thiếu thư viện",
                                  "pip install ultralytics", parent=self.root)
            return

        folder = filedialog.askdirectory(
            title="Chọn thư mục chứa ảnh + nhãn .txt (YOLO format)",
            parent=self.root)
        if not folder:
            return

        if self.v_subfolder.get():
            img_files = sorted([
                os.path.join(root, f)
                for root, _, fnames in os.walk(folder)
                for f in fnames
                if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS
            ])
        else:
            img_files = sorted([
                os.path.join(folder, f)
                for f in os.listdir(folder)
                if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS
            ])
        if not img_files:
            messagebox.showinfo("Thông báo",
                                "Không tìm thấy ảnh trong thư mục!", parent=self.root)
            return

        popup = Toplevel(self.root)
        popup.title("Tính mAP@50")
        popup.configure(bg=BG)
        popup.geometry("680x480")

        Label(popup, text="Đang tính mAP@50 ...",
              font=F_BOLD, bg=BG, fg=TEXT).pack(pady=(10, 4))

        pb = ttk.Progressbar(popup, mode="determinate", maximum=len(img_files))
        pb.pack(fill=X, padx=16, pady=(0, 6))

        self.v_map_progress = StringVar(value="0 / 0")
        Label(popup, textvariable=self.v_map_progress,
              font=F_MONO, bg=BG, fg=DIM).pack()

        txt_frame = Frame(popup, bg=BG)
        txt_frame.pack(fill=BOTH, expand=True, padx=8, pady=8)
        sb_txt = Scrollbar(txt_frame, orient=VERTICAL)
        sb_txt.pack(side=RIGHT, fill=Y)
        result_text = Text(txt_frame, bg="#0d0d1a", fg=TEXT,
                           font=F_MONO, relief="flat", bd=0,
                           yscrollcommand=sb_txt.set, state=DISABLED)
        result_text.pack(fill=BOTH, expand=True)
        sb_txt.config(command=result_text.yview)

        def append(line):
            result_text.config(state=NORMAL)
            result_text.insert(END, line + "\n")
            result_text.see(END)
            result_text.config(state=DISABLED)

        def run():
            conf_val = max(self.v_conf_thresh.get(), self.slider_conf.get())
            iou_val = self.slider_iou.get()
            iou_thresh = 0.5

            tp_total = 0
            fp_total = 0
            fn_total = 0
            per_class_tp = {}
            per_class_fp = {}
            per_class_fn = {}

            processed = 0
            skipped = 0

            for i, img_path in enumerate(img_files):
                base = os.path.splitext(img_path)[0]
                lbl_path = base + ".txt"

                self.root.after(0, lambda v=i: pb.config(value=v))
                self.root.after(0, lambda v=i+1, t=len(img_files):
                                self.v_map_progress.set(f"{v} / {t}"))

                if not os.path.isfile(lbl_path):
                    skipped += 1
                    continue

                try:
                    gt_boxes = []
                    with open(lbl_path, "r", encoding="utf-8") as f:
                        for line in f:
                            parts = line.strip().split()
                            if len(parts) == 5:
                                cls_id = int(parts[0])
                                cx, cy, bw, bh = map(float, parts[1:])
                                gt_boxes.append((cls_id, cx, cy, bw, bh))

                    results = self.model.predict(
                        source=img_path,
                        conf=conf_val,
                        iou=iou_val,
                        imgsz=640,
                        agnostic_nms=True,
                        verbose=False,
                    )
                    pred_boxes = []
                    boxes_res = results[0].boxes
                    if boxes_res is not None:
                        for box in boxes_res:
                            cls_id = int(box.cls[0])
                            xywhn = box.xywhn[0].tolist()
                            pred_boxes.append((cls_id, *xywhn))

                    matched_gt = set()
                    matched_pred = set()

                    for pi, pb_box in enumerate(pred_boxes):
                        p_cls = pb_box[0]
                        p_cx, p_cy, p_bw, p_bh = pb_box[1:]
                        best_iou = 0.0
                        best_gi = -1
                        for gi, gb_box in enumerate(gt_boxes):
                            if gi in matched_gt:
                                continue
                            g_cls = gb_box[0]
                            if g_cls != p_cls:
                                continue
                            g_cx, g_cy, g_bw, g_bh = gb_box[1:]
                            iou_v = _iou_xywhn(p_cx, p_cy, p_bw, p_bh,
                                               g_cx, g_cy, g_bw, g_bh)
                            if iou_v > best_iou:
                                best_iou = iou_v
                                best_gi = gi
                        if best_iou >= iou_thresh and best_gi >= 0:
                            matched_gt.add(best_gi)
                            matched_pred.add(pi)
                            tp_total += 1
                            per_class_tp[p_cls] = per_class_tp.get(p_cls, 0) + 1
                        else:
                            fp_total += 1
                            per_class_fp[p_cls] = per_class_fp.get(p_cls, 0) + 1

                    for gi, gb_box in enumerate(gt_boxes):
                        if gi not in matched_gt:
                            g_cls = gb_box[0]
                            fn_total += 1
                            per_class_fn[g_cls] = per_class_fn.get(g_cls, 0) + 1

                    processed += 1
                except Exception as ex:
                    self.root.after(0, lambda m=str(ex): append(f"  Lỗi: {m}"))

            precision = tp_total / (tp_total + fp_total) if (tp_total + fp_total) > 0 else 0.0
            recall = tp_total / (tp_total + fn_total) if (tp_total + fn_total) > 0 else 0.0
            f1 = (2 * precision * recall / (precision + recall)
                  if (precision + recall) > 0 else 0.0)
            map50 = precision * recall

            lines = [
                "=" * 52,
                f"Kết quả mAP@50 (IoU >= 0.5)",
                f"Thư mục: {folder}",
                f"Tổng ảnh: {len(img_files)}  |  Có nhãn: {processed}  |  Bỏ qua: {skipped}",
                "-" * 52,
                f"TP={tp_total}  FP={fp_total}  FN={fn_total}",
                f"Precision : {precision:.4f}",
                f"Recall    : {recall:.4f}",
                f"F1-Score  : {f1:.4f}",
                f"mAP@50    : {map50:.4f}",
                "-" * 52,
                "Chi tiết theo class:",
            ]
            all_cls = set(list(per_class_tp.keys())
                          + list(per_class_fp.keys())
                          + list(per_class_fn.keys()))
            for cls_id in sorted(all_cls):
                cname = self.model.names.get(cls_id, str(cls_id))
                tp_c = per_class_tp.get(cls_id, 0)
                fp_c = per_class_fp.get(cls_id, 0)
                fn_c = per_class_fn.get(cls_id, 0)
                p_c = tp_c / (tp_c + fp_c) if (tp_c + fp_c) > 0 else 0.0
                r_c = tp_c / (tp_c + fn_c) if (tp_c + fn_c) > 0 else 0.0
                lines.append(
                    f"  [{cls_id}] {cname:<20}  P={p_c:.3f}  R={r_c:.3f}"
                    f"  TP={tp_c} FP={fp_c} FN={fn_c}")
            lines.append("=" * 52)

            self.root.after(0, lambda: pb.config(value=len(img_files)))
            for ln in lines:
                self.root.after(0, lambda l=ln: append(l))

        threading.Thread(target=run, daemon=True).start()

    # ====================================================== VALIDATE TRUE/ ==

    def _validate_true_folder(self):
        if not self.model:
            messagebox.showwarning("Chưa có model",
                                   "Vui lòng chọn model trước.", parent=self.root)
            return
        if not _YOLO_OK:
            messagebox.showerror("Thiếu thư viện",
                                  "pip install ultralytics", parent=self.root)
            return

        # Xác định thư mục true/
        base = self._base_folder
        if not base:
            # Thử lấy từ ô path
            p = self.v_check_folder.get().strip()
            if os.path.isfile(p):
                base = os.path.dirname(p)
            elif os.path.isdir(p):
                base = p

        true_dir = os.path.join(base, "true") if base else None
        if not true_dir or not os.path.isdir(true_dir):
            # Fallback: hỏi người dùng chọn thư mục true/
            true_dir = filedialog.askdirectory(
                title="Chọn thư mục true/ (ảnh đã đánh dấu đúng)",
                parent=self.root)
            if not true_dir:
                return

        img_files = sorted([
            os.path.join(true_dir, f) for f in os.listdir(true_dir)
            if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS
        ])
        if not img_files:
            messagebox.showinfo("Thông báo",
                                f"Không tìm thấy ảnh trong:\n{true_dir}",
                                parent=self.root)
            return

        # ── Tạo cửa sổ kết quả ──
        popup = Toplevel(self.root)
        popup.title(f"Validate Model — {os.path.basename(true_dir)}")
        popup.configure(bg=BG)
        popup.geometry("820x620")
        popup.resizable(True, True)

        # Header
        Label(popup, text=f"🔍 Validate: {true_dir}",
              font=F_BOLD, bg=BG, fg=TEXT, anchor=W).pack(fill=X, padx=10, pady=(8, 2))

        pb = ttk.Progressbar(popup, mode="determinate", maximum=len(img_files))
        pb.pack(fill=X, padx=10, pady=(0, 2))
        v_prog = StringVar(value=f"0 / {len(img_files)}")
        Label(popup, textvariable=v_prog, font=F_MONO, bg=BG, fg=DIM).pack()

        # Summary frame
        sum_frame = Frame(popup, bg=CARD, padx=10, pady=6)
        sum_frame.pack(fill=X, padx=10, pady=(4, 2))
        lbl_sum = Label(sum_frame, text="Đang xử lý...",
                        font=F_MONO, bg=CARD, fg=TEXT, justify=LEFT, anchor=W)
        lbl_sum.pack(fill=X)

        # Assessment frame (hiện sau khi có kết quả)
        assess_frame = Frame(popup, bg="#0d0d1a", padx=10, pady=6)
        assess_frame.pack(fill=X, padx=10, pady=(0, 4))
        lbl_verdict = Label(assess_frame, text="",
                            font=F_BOLD, bg="#0d0d1a", fg=TEXT, justify=LEFT, anchor=W)
        lbl_verdict.pack(fill=X)
        lbl_advice = Label(assess_frame, text="",
                           font=F_MAIN, bg="#0d0d1a", fg=DIM, justify=LEFT, anchor=W,
                           wraplength=780)
        lbl_advice.pack(fill=X)

        # Notebook: per-class table | per-image list | glossary
        nb = ttk.Notebook(popup)
        nb.pack(fill=BOTH, expand=True, padx=10, pady=(4, 8))

        # Tab 1 — Per-class
        tab_cls = Frame(nb, bg=BG)
        nb.add(tab_cls, text="Theo Class")

        cls_style = ttk.Style()
        cls_style.configure("Val.Treeview",
                            background="#0d0d1a", foreground=TEXT,
                            fieldbackground="#0d0d1a", rowheight=22, font=F_MONO)
        cls_style.configure("Val.Treeview.Heading", background=CARD, foreground=TEXT)
        cls_style.map("Val.Treeview", background=[("selected", ACCENT2)])

        cls_cols = ("class", "tp", "fp", "fn", "precision", "recall", "f1")
        cls_tree = ttk.Treeview(tab_cls, columns=cls_cols, show="headings",
                                 style="Val.Treeview")
        for col, hd, w in [
            ("class",     "Class",     160),
            ("tp",        "TP",         50),
            ("fp",        "FP",         50),
            ("fn",        "FN",         50),
            ("precision", "Precision",  90),
            ("recall",    "Recall",     80),
            ("f1",        "F1",         70),
        ]:
            cls_tree.heading(col, text=hd)
            cls_tree.column(col, width=w, anchor=CENTER if col != "class" else W)
        sb_cls = Scrollbar(tab_cls, orient=VERTICAL, command=cls_tree.yview)
        cls_tree.configure(yscrollcommand=sb_cls.set)
        sb_cls.pack(side=RIGHT, fill=Y)
        cls_tree.pack(fill=BOTH, expand=True)
        cls_tree.tag_configure("good",   foreground="#4caf50")
        cls_tree.tag_configure("medium", foreground="#ffcc00")
        cls_tree.tag_configure("bad",    foreground=ACCENT)

        # Tab 2 — Per-image
        tab_img = Frame(nb, bg=BG)
        nb.add(tab_img, text="Theo Ảnh")

        img_cols = ("name", "gt", "pred", "tp", "fp", "fn", "status")
        img_tree = ttk.Treeview(tab_img, columns=img_cols, show="headings",
                                 style="Val.Treeview")
        for col, hd, w in [
            ("name",   "Tên ảnh",  200),
            ("gt",     "GT",        40),
            ("pred",   "Pred",      40),
            ("tp",     "TP",        40),
            ("fp",     "FP",        40),
            ("fn",     "FN",        40),
            ("status", "Trạng thái",100),
        ]:
            img_tree.heading(col, text=hd)
            img_tree.column(col, width=w, anchor=CENTER if col != "name" else W)
        sb_img_v = Scrollbar(tab_img, orient=VERTICAL, command=img_tree.yview)
        sb_img_h = Scrollbar(tab_img, orient=HORIZONTAL, command=img_tree.xview)
        img_tree.configure(yscrollcommand=sb_img_v.set, xscrollcommand=sb_img_h.set)
        sb_img_v.pack(side=RIGHT, fill=Y)
        sb_img_h.pack(side=BOTTOM, fill=X)
        img_tree.pack(fill=BOTH, expand=True)
        img_tree.tag_configure("perfect", foreground="#4caf50")
        img_tree.tag_configure("partial", foreground="#ffcc00")
        img_tree.tag_configure("bad",     foreground=ACCENT)
        img_tree.tag_configure("nolabel", foreground=DIM)

        # Tab 3 — Thuật ngữ
        tab_term = Frame(nb, bg=BG)
        nb.add(tab_term, text="Thuật ngữ")

        term_data = [
            ("TP  —  True Positive", "#4caf50",
             "Model phát hiện ĐÚNG một object: đúng class VÀ bbox chồng lấp ≥ 50% (IoU ≥ 0.5).",
             "Càng cao càng tốt."),
            ("FP  —  False Positive", ACCENT,
             "Model phát hiện THỪA: báo có object nhưng thực tế không có "
             "(hoặc detect sai class, hoặc trùng lặp).",
             "Càng thấp càng tốt.  Khắc phục: tăng Conf Threshold."),
            ("FN  —  False Negative", "#ff9800",
             "Model BỎ SÓT: có object trong label nhưng không detect được.",
             "Càng thấp càng tốt.  Khắc phục: giảm Conf Threshold hoặc thêm dữ liệu train."),
            ("GT  —  Ground Truth", "#90caf9",
             "Số bbox chuẩn được ghi trong file label .txt — dùng làm chuẩn để so sánh.",
             "Chuẩn tham chiếu, không đánh giá cao thấp."),
            ("Pred  —  Prediction", "#90caf9",
             "Số bbox model dự đoán ra trong ảnh.",
             "Lý tưởng: Pred ≈ GT.  Pred >> GT → nhiều FP.  Pred << GT → nhiều FN."),
            ("Precision", "#ce93d8",
             "= TP / (TP + FP)\n"
             "Tỷ lệ detect ĐÚNG trong tổng số lần model phát hiện.\n"
             "Ví dụ: Precision = 0.97  →  97% dự đoán của model là chính xác.",
             "≥ 0.90 là tốt."),
            ("Recall", "#ce93d8",
             "= TP / (TP + FN)\n"
             "Tỷ lệ tìm thấy trong tổng số object THỰC TẾ có trong ảnh.\n"
             "Ví dụ: Recall = 0.78  →  model tìm thấy 78%, bỏ sót 22%.",
             "≥ 0.80 là tốt."),
            ("F1-Score", "#ce93d8",
             "= 2 × Precision × Recall / (Precision + Recall)\n"
             "Chỉ số TỔNG HỢP cân bằng giữa Precision và Recall.\n"
             "F1 = 1.0 là hoàn hảo.  F1 = 0 là không detect được gì.",
             "≥ 0.85 là tốt.  Dùng F1 khi P và R lệch nhau."),
            ("IoU  —  Intersection over Union", "#80cbc4",
             "Độ chồng lấp giữa bbox dự đoán và bbox chuẩn.\n"
             "IoU = Diện tích phần giao / Diện tích phần hợp  (0 → 1).\n"
             "Công cụ này dùng ngưỡng IoU = 0.5 để xác định TP hay FP.",
             "0.5 là ngưỡng tiêu chuẩn (mAP@50).  0.75 là tiêu chuẩn nghiêm."),
        ]

        sb_term = Scrollbar(tab_term, orient=VERTICAL)
        sb_term.pack(side=RIGHT, fill=Y)
        term_txt = Text(tab_term, bg="#0d0d1a", fg=TEXT,
                        font=("Segoe UI", 10), relief="flat", bd=0,
                        wrap=WORD, padx=14, pady=8, state=NORMAL,
                        yscrollcommand=sb_term.set, cursor="arrow")
        term_txt.pack(fill=BOTH, expand=True)
        sb_term.config(command=term_txt.yview)

        # Cấu hình tag màu
        term_txt.tag_configure("term",    font=("Segoe UI", 11, "bold"), spacing1=10)
        term_txt.tag_configure("body",    font=("Segoe UI", 10),         lmargin1=20, lmargin2=20)
        term_txt.tag_configure("good",    font=("Segoe UI", 9, "italic"), lmargin1=20,
                                foreground="#aaaacc", spacing3=8)
        term_txt.tag_configure("divider", foreground="#333355", spacing1=2, spacing3=2)

        for term_name, term_color, meaning, good_when in term_data:
            term_txt.tag_configure(f"t_{term_name}", foreground=term_color)
            term_txt.insert(END, f"▌ {term_name}\n", ("term", f"t_{term_name}"))
            term_txt.insert(END, f"{meaning}\n", "body")
            term_txt.insert(END, f"  → Tốt khi: {good_when}\n", "good")
            term_txt.insert(END, "─" * 90 + "\n", "divider")

        term_txt.config(state=DISABLED)

        def _term_scroll(e):
            term_txt.yview_scroll(int(-1*(e.delta/120)), "units")
        term_txt.bind("<MouseWheel>", _term_scroll)

        # ── Background thread ──
        def run():
            conf_val = max(self.v_conf_thresh.get(), self.v_conf.get())
            iou_val = self.v_iou.get()
            iou_thresh = 0.5

            per_class_tp = {}; per_class_fp = {}; per_class_fn = {}
            img_results = []
            img_detail = {}
            tp_total = fp_total = fn_total = 0
            processed = skipped = 0

            for i, img_path in enumerate(img_files):
                self.root.after(0, lambda v=i+1: (
                    pb.config(value=v),
                    v_prog.set(f"{v} / {len(img_files)}"),
                ))

                base_name = os.path.splitext(os.path.basename(img_path))[0]
                lbl_path = os.path.join(os.path.dirname(img_path), base_name + ".txt")

                if not os.path.isfile(lbl_path):
                    img_results.append((img_path, None, None, None, None, None))
                    skipped += 1
                    continue

                try:
                    gt_boxes = []
                    with open(lbl_path, "r", encoding="utf-8") as f:
                        for line in f:
                            parts = line.strip().split()
                            if len(parts) == 5:
                                cid = int(parts[0])
                                cx, cy, bw, bh = map(float, parts[1:])
                                gt_boxes.append((cid, cx, cy, bw, bh))

                    results = self.model.predict(
                        source=img_path, conf=conf_val, iou=iou_val,
                        imgsz=640, agnostic_nms=True, verbose=False,
                    )
                    pred_boxes = []
                    boxes_res = results[0].boxes
                    if boxes_res is not None:
                        for box in boxes_res:
                            cid = int(box.cls[0])
                            xywhn = box.xywhn[0].tolist()
                            pred_boxes.append((cid, *xywhn))

                    matched_gt = set()
                    tp_img = fp_img = fn_img = 0
                    tp_pred_idx = set()

                    for pi, pb_box in enumerate(pred_boxes):
                        p_cls = pb_box[0]
                        p_cx, p_cy, p_bw, p_bh = pb_box[1:]
                        best_iou = 0.0; best_gi = -1
                        for gi, gb_box in enumerate(gt_boxes):
                            if gi in matched_gt or gb_box[0] != p_cls:
                                continue
                            iou_v = _iou_xywhn(p_cx, p_cy, p_bw, p_bh,
                                               gb_box[1], gb_box[2], gb_box[3], gb_box[4])
                            if iou_v > best_iou:
                                best_iou = iou_v; best_gi = gi
                        if best_iou >= iou_thresh and best_gi >= 0:
                            matched_gt.add(best_gi)
                            tp_pred_idx.add(pi)
                            tp_img += 1
                            per_class_tp[p_cls] = per_class_tp.get(p_cls, 0) + 1
                        else:
                            fp_img += 1
                            per_class_fp[p_cls] = per_class_fp.get(p_cls, 0) + 1

                    for gi, gb_box in enumerate(gt_boxes):
                        if gi not in matched_gt:
                            g_cls = gb_box[0]
                            fn_img += 1
                            per_class_fn[g_cls] = per_class_fn.get(g_cls, 0) + 1

                    img_detail[img_path] = {
                        "gt": list(gt_boxes),
                        "pred": list(pred_boxes),
                        "tp_pred": set(tp_pred_idx),
                        "matched_gt": set(matched_gt),
                    }
                    tp_total += tp_img; fp_total += fp_img; fn_total += fn_img
                    img_results.append((img_path, len(gt_boxes), len(pred_boxes),
                                        tp_img, fp_img, fn_img))
                    processed += 1

                except Exception as ex:
                    img_results.append((img_path, None, None, None, None, str(ex)))

            # ── Cập nhật UI từ main thread ──
            def _update_ui():
                pb.config(value=len(img_files))

                # Summary
                prec = tp_total / (tp_total + fp_total) if (tp_total + fp_total) > 0 else 0.0
                rec  = tp_total / (tp_total + fn_total) if (tp_total + fn_total) > 0 else 0.0
                f1   = (2*prec*rec / (prec+rec)) if (prec+rec) > 0 else 0.0
                lbl_sum.config(
                    text=(f"Thư mục: {true_dir}\n"
                          f"Tổng ảnh: {len(img_files)}  |  Có label: {processed}  |  Bỏ qua: {skipped}\n"
                          f"TP={tp_total}  FP={fp_total}  FN={fn_total}"
                          f"    Precision={prec:.4f}  Recall={rec:.4f}  F1={f1:.4f}")
                )

                # Đánh giá tổng thể
                if f1 >= 0.90:
                    verdict_text = "★★★★★  XUẤT SẮC"
                    verdict_color = "#4caf50"
                elif f1 >= 0.80:
                    verdict_text = "★★★★  TỐT — Model đáp ứng yêu cầu sử dụng"
                    verdict_color = "#8bc34a"
                elif f1 >= 0.65:
                    verdict_text = "★★★  KHÁ — Cần cải thiện thêm"
                    verdict_color = "#ffcc00"
                elif f1 >= 0.50:
                    verdict_text = "★★  TRUNG BÌNH — Chưa ổn định"
                    verdict_color = "#ff9800"
                else:
                    verdict_text = "★  YẾU — Cần train lại hoặc bổ sung dữ liệu"
                    verdict_color = ACCENT

                advice_lines = []
                if prec < 0.85:
                    advice_lines.append(
                        f"• Precision={prec:.3f} thấp → model detect nhầm nhiều (FP cao) "
                        "→ Tăng Conf Threshold hoặc lọc thêm dữ liệu nhiễu khi train.")
                if rec < 0.80:
                    advice_lines.append(
                        f"• Recall={rec:.3f} thấp → model bỏ sót object (FN cao) "
                        "→ Giảm Conf Threshold, hoặc thêm ảnh train đa dạng hơn.")

                # Cảnh báo class yếu
                all_cls_check = set(list(per_class_tp) + list(per_class_fp) + list(per_class_fn))
                weak_classes = []
                for cid in sorted(all_cls_check):
                    tp_c = per_class_tp.get(cid, 0)
                    fp_c = per_class_fp.get(cid, 0)
                    fn_c = per_class_fn.get(cid, 0)
                    p_c = tp_c / (tp_c + fp_c) if (tp_c + fp_c) > 0 else 0.0
                    r_c = tp_c / (tp_c + fn_c) if (tp_c + fn_c) > 0 else 0.0
                    f1_c = (2*p_c*r_c / (p_c+r_c)) if (p_c+r_c) > 0 else 0.0
                    cname = self.model.names.get(cid, str(cid))
                    if f1_c < 0.5:
                        weak_classes.append(f"[{cid}]{cname}(F1={f1_c:.2f})")
                if weak_classes:
                    advice_lines.append(
                        f"• Class yếu cần bổ sung dữ liệu: {', '.join(weak_classes)}")

                if not advice_lines:
                    advice_lines.append("Không có điểm yếu đáng kể. Model hoạt động ổn định.")

                lbl_verdict.config(text=f"Đánh giá: {verdict_text}  "
                                        f"(F1={f1:.4f}  P={prec:.4f}  R={rec:.4f})",
                                   fg=verdict_color)
                lbl_advice.config(text="\n".join(advice_lines))

                # Per-class table
                all_cls = set(list(per_class_tp) + list(per_class_fp) + list(per_class_fn))
                for cid in sorted(all_cls):
                    cname = self.model.names.get(cid, str(cid))
                    tp_c = per_class_tp.get(cid, 0)
                    fp_c = per_class_fp.get(cid, 0)
                    fn_c = per_class_fn.get(cid, 0)
                    p_c = tp_c / (tp_c + fp_c) if (tp_c + fp_c) > 0 else 0.0
                    r_c = tp_c / (tp_c + fn_c) if (tp_c + fn_c) > 0 else 0.0
                    f1_c = (2*p_c*r_c / (p_c+r_c)) if (p_c+r_c) > 0 else 0.0
                    tag = "good" if f1_c >= 0.8 else ("medium" if f1_c >= 0.5 else "bad")
                    cls_tree.insert("", END, values=(
                        f"[{cid}] {cname}", tp_c, fp_c, fn_c,
                        f"{p_c:.3f}", f"{r_c:.3f}", f"{f1_c:.3f}",
                    ), tags=(tag,))

                # Per-image table (sắp xếp: ảnh tệ nhất lên đầu)
                def sort_key(r):
                    if r[3] is None:  return (3, 0)
                    fp_i, fn_i = r[4] or 0, r[5] or 0
                    return (0 if (fp_i + fn_i) == 0 else 1 if (fp_i + fn_i) <= 2 else 2,
                            -(fp_i + fn_i))
                img_results.sort(key=sort_key)

                for row in img_results:
                    img_path, n_gt, n_pred, tp_i, fp_i, fn_i = row
                    fname = os.path.basename(img_path)
                    if n_gt is None and isinstance(fn_i, str):
                        img_tree.insert("", END,
                            values=(fname, "?", "?", "?", "?", "?", f"Lỗi: {fn_i}"),
                            tags=("bad",))
                    elif n_gt is None:
                        img_tree.insert("", END,
                            values=(fname, "-", "-", "-", "-", "-", "Không có label"),
                            tags=("nolabel",))
                    else:
                        if fp_i + fn_i == 0:
                            status, tag = "✓ Hoàn hảo", "perfect"
                        elif fp_i + fn_i <= 2:
                            status, tag = f"△ FP={fp_i} FN={fn_i}", "partial"
                        else:
                            status, tag = f"✗ FP={fp_i} FN={fn_i}", "bad"
                        img_tree.insert("", END,
                            values=(fname, n_gt, n_pred, tp_i, fp_i, fn_i, status),
                            tags=(tag,))

                # ── Click row → xem ảnh với bbox màu TP/FP/FN ──
                fname_to_path = {os.path.basename(p): p for p in img_detail}

                def _on_row_select(e, _tree=img_tree, _ftp=fname_to_path,
                                   _detail=img_detail, _pop=popup):
                    sel = _tree.selection()
                    if not sel:
                        return
                    vals = _tree.item(sel[0], "values")
                    if not vals:
                        return
                    ipath = _ftp.get(vals[0])
                    if not ipath or ipath not in _detail:
                        return
                    _show_img_detail(ipath, _detail[ipath], _pop)

                def _show_img_detail(ipath, detail, parent_win):
                    if not _PIL_OK:
                        messagebox.showerror("Lỗi", "Cần cài Pillow để xem ảnh",
                                             parent=parent_win)
                        return
                    try:
                        pil_src = Image.open(ipath).convert("RGB")
                    except Exception as ex:
                        messagebox.showerror("Lỗi ảnh", str(ex), parent=parent_win)
                        return

                    W, H = pil_src.size
                    pil_ann = pil_src.copy()
                    drw = ImageDraw.Draw(pil_ann)
                    mnames = self.model.names if self.model else {}
                    lw = max(2, int(min(W, H) / 250))

                    def _box_px(cx, cy, bw, bh):
                        return (max(0, int((cx-bw/2)*W)), max(0, int((cy-bh/2)*H)),
                                min(W-1, int((cx+bw/2)*W)), min(H-1, int((cy+bh/2)*H)))

                    def _label(x, y, text, color):
                        try:
                            drw.text((x, y), text, fill=color,
                                     stroke_width=1, stroke_fill="#000000")
                        except TypeError:
                            drw.text((x, y), text, fill=color)

                    # FN: missed GT — vàng, vẽ trước (lớp dưới)
                    for gi, gb in enumerate(detail["gt"]):
                        if gi not in detail["matched_gt"]:
                            cid, cx, cy, bw, bh = gb
                            x1, y1, x2, y2 = _box_px(cx, cy, bw, bh)
                            drw.rectangle([x1, y1, x2, y2], outline="#ffcc00", width=lw)
                            _label(x1+2, y1+2,
                                   f"FN [{cid}]{mnames.get(cid,str(cid))}", "#ffcc00")

                    # Pred boxes: TP=xanh, FP=cam — vẽ sau (lớp trên)
                    for pi, pb in enumerate(detail["pred"]):
                        cid, cx, cy, bw, bh = pb
                        x1, y1, x2, y2 = _box_px(cx, cy, bw, bh)
                        cname = mnames.get(cid, str(cid))
                        if pi in detail["tp_pred"]:
                            color, lbl = "#4caf50", f"TP [{cid}]{cname}"
                        else:
                            color, lbl = "#F05922", f"FP [{cid}]{cname}"
                        drw.rectangle([x1+lw, y1+lw, x2-lw, y2-lw],
                                      outline=color, width=lw)
                        ty = min(H-14, y2-lw-14)
                        _label(x1+lw+2, ty, lbl, color)

                    # Cửa sổ hiển thị
                    dwin = Toplevel(parent_win)
                    dwin.title(f"Chi tiết: {os.path.basename(ipath)}")
                    dwin.configure(bg=BG)
                    dwin.resizable(True, True)
                    dwin.protocol("WM_DELETE_WINDOW", dwin.destroy)

                    # Legend + stats
                    leg = Frame(dwin, bg=CARD, padx=8, pady=4)
                    leg.pack(fill=X)
                    n_tp = len(detail["tp_pred"])
                    n_fp = len(detail["pred"]) - n_tp
                    n_fn = len(detail["gt"]) - len(detail["matched_gt"])
                    for txt, col in [("■ TP (Đúng)", "#4caf50"),
                                     ("■ FP (Thừa)", "#F05922"),
                                     ("■ FN (Bỏ sót)", "#ffcc00")]:
                        Label(leg, text=txt, fg=col, bg=CARD,
                              font=F_MONO).pack(side=LEFT, padx=10)
                    Label(leg,
                          text=f"GT={len(detail['gt'])}  TP={n_tp}  FP={n_fp}  FN={n_fn}",
                          fg=DIM, bg=CARD, font=F_MONO).pack(side=RIGHT, padx=10)

                    # Scale ảnh vừa màn hình
                    sw2 = dwin.winfo_screenwidth()
                    sh2 = dwin.winfo_screenheight()
                    img_disp = pil_ann.copy()
                    img_disp.thumbnail((int(sw2*0.85), int(sh2*0.80)), Image.LANCZOS)

                    frm = Frame(dwin, bg="#0d0d1a")
                    frm.pack(fill=BOTH, expand=True)
                    det_canvas = Canvas(frm, bg="#0d0d1a", highlightthickness=0)
                    sb_dv = Scrollbar(frm, orient=VERTICAL, command=det_canvas.yview)
                    sb_dh = Scrollbar(dwin, orient=HORIZONTAL, command=det_canvas.xview)
                    det_canvas.configure(yscrollcommand=sb_dv.set,
                                         xscrollcommand=sb_dh.set)
                    sb_dh.pack(side=BOTTOM, fill=X)
                    sb_dv.pack(side=RIGHT, fill=Y)
                    det_canvas.pack(fill=BOTH, expand=True)

                    def _render_det(_c=det_canvas, _img=img_disp):
                        _tk = ImageTk.PhotoImage(_img)
                        _c.create_image(0, 0, anchor=NW, image=_tk)
                        _c.configure(scrollregion=(0, 0, _img.width, _img.height))
                        _c._tk_img = _tk

                    dwin.after(30, _render_det)
                    dwin.geometry(f"{min(img_disp.width+20, int(sw2*0.85))}"
                                  f"x{min(img_disp.height+60, int(sh2*0.80))}")
                    dwin.lift()
                    dwin.focus_set()
                    det_canvas.bind("<MouseWheel>",
                                    lambda e, c=det_canvas:
                                    c.yview_scroll(int(-1*(e.delta/120)), "units"))
                    dwin.bind("<Escape>", lambda _: dwin.destroy())

                img_tree.bind("<<TreeviewSelect>>", _on_row_select)

            self.root.after(0, _update_ui)

        threading.Thread(target=run, daemon=True).start()


def _path_review_state(path: str) -> str:
    """Trả về 'correct'/'incorrect'/'' dựa trên tên folder chứa ảnh."""
    parent = os.path.basename(os.path.dirname(path))
    if parent == "true":  return "correct"
    if parent == "false": return "incorrect"
    return ""


def _iou_xywhn(cx1, cy1, w1, h1, cx2, cy2, w2, h2):
    x1_min = cx1 - w1 / 2; x1_max = cx1 + w1 / 2
    y1_min = cy1 - h1 / 2; y1_max = cy1 + h1 / 2
    x2_min = cx2 - w2 / 2; x2_max = cx2 + w2 / 2
    y2_min = cy2 - h2 / 2; y2_max = cy2 + h2 / 2
    inter_x = max(0.0, min(x1_max, x2_max) - max(x1_min, x2_min))
    inter_y = max(0.0, min(y1_max, y2_max) - max(y1_min, y2_min))
    inter = inter_x * inter_y
    union = w1 * h1 + w2 * h2 - inter
    return inter / union if union > 0 else 0.0
