# yolo_layout_mixin.py — YoloLayoutMixin — layout toolbar + panel nội dung chính (2 canvas, filter, LPR config UI)
import os
from tkinter import *
from tkinter import filedialog, messagebox, ttk
from ...core.constants import (BG, CARD, ACCENT, ACCENT2, TEXT, DIM, SUCCESS,
                         F_MAIN, F_BOLD, F_MONO, IMAGE_EXTENSIONS)
from ...core.settings import (_bind_cfg, _cfg_dir, _CFG, _cfg_save,
                        _bind_history, _push_history, _get_history)
try:
    from tkinterdnd2 import DND_FILES
    _DND_OK = True
except ImportError:
    _DND_OK = False
try:
    from .det_table import DetTablePanel as _DetTablePanel
    _DET_TABLE_OK = True
except Exception:
    _DET_TABLE_OK = False


class YoloLayoutMixin:
    """Mixin: dựng toolbar (model/config) và panel nội dung chính (canvas, filter, det table)."""

    def _build_toolbar(self):
        top = Frame(self, bg=CARD, padx=10, pady=8)
        top.pack(fill=X)

        # Row 0 — model 1 + model 2 (cùng 1 dòng)
        r0 = Frame(top, bg=CARD)
        r0.pack(fill=X)

        # Action buttons on RIGHT (pack trước để không bị squish)
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

        # Model 1
        Button(r0, text="Model 1", command=self._select_model,
               bg=ACCENT2, fg="white", font=F_BOLD, relief="flat",
               padx=8, cursor="hand2",
               activebackground=ACCENT, activeforeground="white",
               ).pack(side=LEFT)
        self.lbl_model = Label(r0, text="Chưa chọn",
                               font=("Segoe UI", 9, "italic"),
                               bg=CARD, fg=DIM, width=18, anchor=W)
        self.lbl_model.pack(side=LEFT, padx=(4, 0))

        # Separator
        Frame(r0, bg=DIM, width=1).pack(side=LEFT, fill=Y, padx=(8, 8))

        # Model 2
        Button(r0, text="Model 2", command=self._select_model2,
               bg="#3a5a3a", fg="white", font=F_BOLD, relief="flat",
               padx=8, cursor="hand2",
               activebackground="#4a7a4a", activeforeground="white",
               ).pack(side=LEFT)
        self.lbl_model2 = Label(r0, text="Chưa chọn",
                                font=("Segoe UI", 9, "italic"),
                                bg=CARD, fg=DIM, width=18, anchor=W)
        self.lbl_model2.pack(side=LEFT, padx=(4, 0))
        Button(r0, text="×", command=self._clear_model2,
               bg=CARD, fg=DIM, font=F_BOLD, relief="flat",
               padx=4, cursor="hand2",
               activebackground="#3a1a1a", activeforeground=ACCENT,
               ).pack(side=LEFT, padx=(2, 0))

        # Separator
        Frame(r0, bg=DIM, width=1).pack(side=LEFT, fill=Y, padx=(8, 8))

        # Model 3 (RF-DETR)
        Button(r0, text="Model 3", command=self._select_model3,
               bg="#4a3a6a", fg="white", font=F_BOLD, relief="flat",
               padx=8, cursor="hand2",
               activebackground="#6a5a8a", activeforeground="white",
               ).pack(side=LEFT)
        self.lbl_model3 = Label(r0, text="Chưa chọn (RF-DETR)",
                                font=("Segoe UI", 9, "italic"),
                                bg=CARD, fg=DIM, width=22, anchor=W)
        self.lbl_model3.pack(side=LEFT, padx=(4, 0))
        Button(r0, text="×", command=self._clear_model3,
               bg=CARD, fg=DIM, font=F_BOLD, relief="flat",
               padx=4, cursor="hand2",
               activebackground="#3a1a1a", activeforeground=ACCENT,
               ).pack(side=LEFT, padx=(2, 0))

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

        # Row 0b — folder lưu ảnh sai (5 ô ghép path)
        r0b = Frame(top, bg=CARD)
        r0b.pack(fill=X, pady=(4, 0))

        Label(r0b, text="📁 Lưu ảnh sai:", font=F_MAIN, bg=CARD, fg=DIM).pack(side=LEFT, padx=(0, 4))

        # 5 ô: ô 1 expand (base path), ô 2-5 fixed width (sub-path)
        self._wf_combos = []
        _WF_WIDTHS = [0, 14, 14, 14, 12]  # 0 = expand
        _WF_KEYS   = [f"h.yolo.wf.s{i+1}" for i in range(5)]
        for i in range(5):
            if i > 0:
                Label(r0b, text="/", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
            cb = ttk.Combobox(r0b, textvariable=self._v_wf_segs[i], font=F_MAIN,
                              width=_WF_WIDTHS[i] or None)
            expand = (i == 0)
            cb.pack(side=LEFT, fill=X if expand else None,
                    expand=expand, padx=(0, 0))
            _bind_history(_WF_KEYS[i], cb)
            self._wf_combos.append(cb)

        Button(r0b, text="Chọn…", command=self._browse_wrong_folder,
               bg="#3a3a5a", fg=TEXT, font=F_MAIN, relief="flat",
               padx=8, cursor="hand2").pack(side=LEFT, padx=(4, 4))
        Button(r0b, text="📂", command=self._open_wrong_folder,
               bg=CARD, fg=TEXT, font=F_MAIN, relief="flat",
               padx=6, cursor="hand2",
               activebackground=ACCENT2, activeforeground="white").pack(side=LEFT)

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

        # Row 2 — class filter (compact inline)
        r2 = Frame(top, bg=CARD)
        r2.pack(fill=X, pady=(4, 0))

        Label(r2, text="Lọc class:", font=F_MAIN, bg=CARD, fg=DIM,
              anchor=W).pack(side=LEFT, padx=(0, 4))
        cls_wrap = Frame(r2, bg=CARD)
        cls_wrap.pack(side=LEFT, fill=BOTH, expand=True)
        sb = Scrollbar(cls_wrap, orient=VERTICAL)
        sb.pack(side=RIGHT, fill=Y)
        self.lb_classes = Listbox(cls_wrap, selectmode=MULTIPLE,
                                   yscrollcommand=sb.set,
                                   height=2, font=F_MONO,
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
        Checkbutton(r3, text="Vẽ lên hình", variable=self.v_export_draw,
                    bg=CARD, fg=TEXT, activebackground=CARD,
                    activeforeground=TEXT, selectcolor="#16162a",
                    font=F_MAIN, cursor="hand2").pack(side=LEFT, padx=(4, 0))
        Checkbutton(r3, text="Đổi tên", variable=self.v_export_rename,
                    bg=CARD, fg=TEXT, activebackground=CARD,
                    activeforeground=TEXT, selectcolor="#16162a",
                    font=F_MAIN, cursor="hand2").pack(side=LEFT, padx=(2, 0))

        Button(r3, text="📹 Video", command=self._open_video_detect,
               bg="#1a3a5a", fg="#7ab8e8", font=F_MAIN, relief="flat",
               padx=8, cursor="hand2",
               activebackground="#2a5a8a", activeforeground="white",
               ).pack(side=LEFT, padx=(4, 0))

        self.btn_detect_all = Button(r3, text="⚡ Detect All",
                                     command=self._detect_all,
                                     bg="#103020", fg="#4caf50", font=F_MAIN,
                                     relief="flat", padx=8, cursor="hand2",
                                     activebackground="#1a5030", activeforeground="#4caf50")
        self.btn_detect_all.pack(side=LEFT, padx=(4, 0))
        self.btn_detect_page = Button(r3, text="⚡ Detect trang",
                                      command=self._detect_page,
                                      bg="#102030", fg="#4caf50", font=F_MAIN,
                                      relief="flat", padx=8, cursor="hand2",
                                      activebackground="#1a3050", activeforeground="#4caf50")
        self.btn_detect_page.pack(side=LEFT, padx=(4, 0))
        self.lbl_cache_info = Label(r3, text="", font=F_MONO, bg=CARD, fg=DIM)
        self.lbl_cache_info.pack(side=LEFT, padx=(4, 0))
        Button(r3, text="🗑", command=self._clear_cache,
               bg=CARD, fg=DIM, font=F_MAIN, relief="flat",
               padx=4, cursor="hand2",
               activebackground="#3a1a1a", activeforeground=ACCENT,
               ).pack(side=LEFT, padx=(2, 0))

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
        fs_spn = Spinbox(r3, from_=6, to=48, textvariable=self.v_font_size,
                         width=3, bg="#16162a", fg=TEXT, insertbackground=TEXT,
                         buttonbackground=ACCENT2, relief="flat", font=F_MAIN,
                         command=self._on_plot_param_change)
        fs_spn.bind("<Return>",   lambda e: self._on_plot_param_change())
        fs_spn.bind("<FocusOut>", lambda e: self._on_plot_param_change())
        fs_spn.pack(side=LEFT, padx=(2, 0))

        # Row 4 — LPR server config (kiểm tra biển số sau YOLO detect)
        r4 = Frame(top, bg=CARD)
        r4.pack(fill=X, pady=(6, 0))

        # Sub-row 4a: checkboxes + params + test btn
        r4a = Frame(r4, bg=CARD)
        r4a.pack(fill=X)
        Checkbutton(r4a, text="🔍 Kiểm tra biển số", variable=self.v_check_lpr,
                    bg=CARD, fg=TEXT, activebackground=CARD,
                    activeforeground=TEXT, selectcolor="#16162a",
                    font=F_MAIN, cursor="hand2",
                    ).pack(side=LEFT, padx=(0, 6))
        Checkbutton(r4a, text="📦 Gọi khi batch", variable=self.v_lpr_batch,
                    bg=CARD, fg=DIM, activebackground=CARD,
                    activeforeground=TEXT, selectcolor="#16162a",
                    font=F_MAIN, cursor="hand2",
                    ).pack(side=LEFT, padx=(0, 10))
        Label(r4a, text="Timeout:", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        Spinbox(r4a, from_=1, to=120, textvariable=self._lpr_timeout_var,
                width=4, bg="#16162a", fg=TEXT, insertbackground=TEXT,
                buttonbackground=ACCENT2, relief="flat", font=F_MAIN,
                ).pack(side=LEFT, padx=(4, 2))
        Label(r4a, text="s", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT, padx=(0, 10))
        Label(r4a, text="Cỡ chữ:", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        Spinbox(r4a, from_=12, to=72, textvariable=self._lpr_font_size_var,
                width=4, bg="#16162a", fg=TEXT, insertbackground=TEXT,
                buttonbackground=ACCENT2, relief="flat", font=F_MAIN,
                ).pack(side=LEFT, padx=(4, 2))
        Label(r4a, text="px", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT, padx=(0, 10))
        Button(r4a, text="🔌 Test", command=self._test_lpr_connection,
               bg=ACCENT2, fg="white", font=F_MAIN, relief="flat",
               padx=8, cursor="hand2",
               activebackground=ACCENT, activeforeground="white",
               ).pack(side=LEFT, padx=(0, 6))
        self._lpr_conn_lbl = Label(r4a, text="", bg=CARD, fg=DIM,
                                    font=F_MAIN, width=24, anchor=W)
        self._lpr_conn_lbl.pack(side=LEFT)

        # Sub-row 4b: 3 URL comboboxes + checkbox ảnh gốc
        r4b = Frame(r4, bg=CARD)
        r4b.pack(fill=X, pady=(3, 0))
        _LPR_HIST_KEYS = ["h.yolo.lpr_url1", "h.yolo.lpr_url2", "h.yolo.lpr_url3"]
        for i in range(3):
            Label(r4b, text=f"LPR{i+1}:", bg=CARD, fg=DIM,
                  font=F_MAIN).pack(side=LEFT, padx=(0 if i == 0 else 8, 2))
            cb = ttk.Combobox(r4b, textvariable=self._lpr_url_vars[i],
                              width=30, font=F_MAIN)
            cb.pack(side=LEFT)
            _bind_history(_LPR_HIST_KEYS[i], cb)
            self._lpr_url_combos[i] = cb
            Checkbutton(r4b, text="Ảnh gốc", variable=self._lpr_fullimg_vars[i],
                        bg=CARD, fg=DIM, selectcolor=CARD,
                        font=F_MAIN).pack(side=LEFT, padx=(3, 0))

    def _build_content(self):
        content = Frame(self, bg=BG)
        content.pack(fill=BOTH, expand=True)

        # Sidebar — image list
        sidebar = Frame(content, bg=CARD, width=240)
        sidebar.pack(side=LEFT, fill=Y, padx=(0, 2))
        sidebar.pack_propagate(False)

        Label(sidebar, text="Danh sách ảnh",
              font=F_BOLD, bg=CARD, fg=TEXT).pack(pady=(8, 2))

        # Search box
        search_row = Frame(sidebar, bg=CARD)
        search_row.pack(fill=X, padx=4, pady=(0, 3))
        Label(search_row, text="🔍", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        self._search_combo = ttk.Combobox(
            search_row, textvariable=self._v_search,
            font=F_MONO, height=12)
        self._search_combo.pack(side=LEFT, fill=X, expand=True, padx=(2, 4))
        _bind_history("h.yolo.search", self._search_combo)
        self._search_combo.bind("<Return>", lambda e: self._do_search())
        self._search_combo.bind("<<ComboboxSelected>>",
                                lambda e: self._do_search())
        Button(search_row, text="Tìm", command=self._do_search,
               bg=ACCENT2, fg="white", font=F_MAIN, relief="flat",
               padx=6, cursor="hand2").pack(side=LEFT)
        self._hint_toggle_btn = Button(
            search_row, text="?", command=self._toggle_search_hint,
            bg=CARD, fg="#6060a0", font=("Segoe UI", 8),
            relief="flat", cursor="hand2", padx=3)
        self._hint_toggle_btn.pack(side=LEFT, padx=(2, 0))

        # Search hint — collapsed by default to preserve space for file list
        hint_lines = [
            "Cách dùng ô tìm kiếm:",
            "• Nhiều từ = AND:  sang cong 5",
            "• *  = bất kỳ chuỗi:  07*  *canh",
            "• ?  = đúng 1 ký tự:  07?507",
            "• Kết hợp:  sang 07*",
            "• Enter hoặc nút Tìm để áp dụng",
        ]
        self._search_row_ref = search_row
        self._hint_frame = Frame(sidebar, bg="#12122a", bd=0)
        for line in hint_lines:
            Label(self._hint_frame, text=line,
                  bg="#12122a", fg="#6060a0",
                  font=("Segoe UI", 7), anchor=W,
                  justify=LEFT).pack(fill=X, padx=4, pady=0)
        self._hint_shown = False  # ẩn mặc định

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

        # ── Detect result filters ────────────────────────────────────────────
        Frame(sidebar, bg=DIM, height=1).pack(fill=X, padx=6, pady=(2, 2))

        det_hdr = Frame(sidebar, bg=CARD)
        det_hdr.pack(fill=X, padx=4, pady=(0, 1))
        Label(det_hdr, text="Filter detect:", bg=CARD, fg=DIM,
              font=F_MAIN).pack(side=LEFT)
        Button(det_hdr, text="×", command=self._clear_det_filters,
               bg=CARD, fg=DIM, font=F_MAIN, relief="flat",
               cursor="hand2", padx=2).pack(side=RIGHT)

        flt_cls_row = Frame(sidebar, bg=CARD)
        flt_cls_row.pack(fill=X, padx=4, pady=(0, 2))
        Label(flt_cls_row, text="Class:", bg=CARD, fg=DIM,
              font=F_MAIN, width=7, anchor=W).pack(side=LEFT)
        self._flt_class_combo = ttk.Combobox(
            flt_cls_row, textvariable=self._flt_class_var,
            state="readonly", font=F_MAIN)
        self._flt_class_combo["values"] = ["Tất cả", "Không detect"]
        self._flt_class_combo.pack(side=LEFT, fill=X, expand=True)
        self._flt_class_combo.bind("<<ComboboxSelected>>",
                                   lambda _: self._apply_filter(self._active_filter))

        flt_n_row = Frame(sidebar, bg=CARD)
        flt_n_row.pack(fill=X, padx=4, pady=(0, 2))
        Label(flt_n_row, text="#Det:", bg=CARD, fg=DIM,
              font=F_MAIN, width=7, anchor=W).pack(side=LEFT)
        Entry(flt_n_row, textvariable=self._flt_ndet_min_var,
              bg="#16162a", fg=TEXT, insertbackground=TEXT,
              relief="flat", font=F_MONO, bd=2, width=5).pack(side=LEFT)
        Label(flt_n_row, text="–", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT, padx=1)
        Entry(flt_n_row, textvariable=self._flt_ndet_max_var,
              bg="#16162a", fg=TEXT, insertbackground=TEXT,
              relief="flat", font=F_MONO, bd=2, width=5).pack(side=LEFT)
        self._flt_ndet_min_var.trace_add("write", lambda *_: self._schedule_det_filter())
        self._flt_ndet_max_var.trace_add("write", lambda *_: self._schedule_det_filter())

        flt_area_row = Frame(sidebar, bg=CARD)
        flt_area_row.pack(fill=X, padx=4, pady=(0, 2))
        Label(flt_area_row, text="BBox px²:", bg=CARD, fg=DIM,
              font=F_MAIN, width=7, anchor=W).pack(side=LEFT)
        Entry(flt_area_row, textvariable=self._flt_area_min_var,
              bg="#16162a", fg=TEXT, insertbackground=TEXT,
              relief="flat", font=F_MONO, bd=2, width=5).pack(side=LEFT)
        Label(flt_area_row, text="–", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT, padx=1)
        Entry(flt_area_row, textvariable=self._flt_area_max_var,
              bg="#16162a", fg=TEXT, insertbackground=TEXT,
              relief="flat", font=F_MONO, bd=2, width=5).pack(side=LEFT)
        self._flt_area_min_var.trace_add("write", lambda *_: self._schedule_det_filter())
        self._flt_area_max_var.trace_add("write", lambda *_: self._schedule_det_filter())

        flt_w_row = Frame(sidebar, bg=CARD)
        flt_w_row.pack(fill=X, padx=4, pady=(0, 2))
        Label(flt_w_row, text="BBox W:", bg=CARD, fg=DIM,
              font=F_MAIN, width=7, anchor=W).pack(side=LEFT)
        Entry(flt_w_row, textvariable=self._flt_w_min_var,
              bg="#16162a", fg=TEXT, insertbackground=TEXT,
              relief="flat", font=F_MONO, bd=2, width=5).pack(side=LEFT)
        Label(flt_w_row, text="–", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT, padx=1)
        Entry(flt_w_row, textvariable=self._flt_w_max_var,
              bg="#16162a", fg=TEXT, insertbackground=TEXT,
              relief="flat", font=F_MONO, bd=2, width=5).pack(side=LEFT)
        self._flt_w_min_var.trace_add("write", lambda *_: self._schedule_det_filter())
        self._flt_w_max_var.trace_add("write", lambda *_: self._schedule_det_filter())

        flt_h_row = Frame(sidebar, bg=CARD)
        flt_h_row.pack(fill=X, padx=4, pady=(0, 2))
        Label(flt_h_row, text="BBox H:", bg=CARD, fg=DIM,
              font=F_MAIN, width=7, anchor=W).pack(side=LEFT)
        Entry(flt_h_row, textvariable=self._flt_h_min_var,
              bg="#16162a", fg=TEXT, insertbackground=TEXT,
              relief="flat", font=F_MONO, bd=2, width=5).pack(side=LEFT)
        Label(flt_h_row, text="–", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT, padx=1)
        Entry(flt_h_row, textvariable=self._flt_h_max_var,
              bg="#16162a", fg=TEXT, insertbackground=TEXT,
              relief="flat", font=F_MONO, bd=2, width=5).pack(side=LEFT)
        self._flt_h_min_var.trace_add("write", lambda *_: self._schedule_det_filter())
        self._flt_h_max_var.trace_add("write", lambda *_: self._schedule_det_filter())

        # ── Phải có / không có nhãn ─────────────────────────────────────────
        Frame(sidebar, bg=DIM, height=1).pack(fill=X, padx=6, pady=(3, 2))

        Label(sidebar, text="✔ Phải có nhãn:", bg=CARD, fg=DIM,
              font=F_MAIN, anchor=W).pack(fill=X, padx=6)
        mh_frm = Frame(sidebar, bg=CARD)
        mh_frm.pack(fill=X, padx=6, pady=(1, 2))
        self._must_have_lb = Listbox(mh_frm, bg="#16162a", fg=TEXT,
                                     selectbackground=ACCENT2,
                                     selectforeground="white",
                                     font=F_MONO, relief="flat", bd=0,
                                     selectmode=MULTIPLE, height=3,
                                     activestyle="none", exportselection=False)
        mh_sb = Scrollbar(mh_frm, command=self._must_have_lb.yview)
        self._must_have_lb.configure(yscrollcommand=mh_sb.set)
        mh_sb.pack(side=RIGHT, fill=Y)
        self._must_have_lb.pack(fill=X, expand=True)
        self._must_have_lb.bind("<<ListboxSelect>>",
                                lambda _: self._schedule_det_filter())

        Label(sidebar, text="✕ Không có nhãn:", bg=CARD, fg=DIM,
              font=F_MAIN, anchor=W).pack(fill=X, padx=6, pady=(2, 0))
        mn_frm = Frame(sidebar, bg=CARD)
        mn_frm.pack(fill=X, padx=6, pady=(1, 3))
        self._must_not_lb = Listbox(mn_frm, bg="#16162a", fg=TEXT,
                                    selectbackground="#c62828",
                                    selectforeground="white",
                                    font=F_MONO, relief="flat", bd=0,
                                    selectmode=MULTIPLE, height=3,
                                    activestyle="none", exportselection=False)
        mn_sb = Scrollbar(mn_frm, command=self._must_not_lb.yview)
        self._must_not_lb.configure(yscrollcommand=mn_sb.set)
        mn_sb.pack(side=RIGHT, fill=Y)
        self._must_not_lb.pack(fill=X, expand=True)
        self._must_not_lb.bind("<<ListboxSelect>>",
                               lambda _: self._schedule_det_filter())

        Frame(sidebar, bg=DIM, height=1).pack(fill=X, padx=6, pady=(2, 2))

        # ── LPR filter ──────────────────────────────────────────────────────
        lpr_flt_row = Frame(sidebar, bg=CARD)
        lpr_flt_row.pack(fill=X, padx=6, pady=(1, 3))
        Label(lpr_flt_row, text="🔍 LPR:", bg=CARD, fg=DIM,
              font=F_MAIN).pack(side=LEFT, padx=(0, 4))
        self._flt_lpr_combo = ttk.Combobox(
            lpr_flt_row, textvariable=self._flt_lpr_var, state="readonly",
            values=["Tất cả", "Có biển số", "Không biển số", "Chưa nhận dạng"],
            width=16, font=F_MAIN)
        self._flt_lpr_combo.pack(side=LEFT, fill=X, expand=True)
        self._flt_lpr_var.trace_add("write", lambda *_: self._schedule_det_filter())

        Frame(sidebar, bg=DIM, height=1).pack(fill=X, padx=6, pady=(0, 2))

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

        # Per-model result row (luôn pack, chỉ thay text để ẩn/hiện)
        self._model_result_frame = Frame(right, bg=BG)
        self._model_result_frame.pack(fill=X, padx=6, pady=(0, 0))
        self._lbl_m1_res = Label(self._model_result_frame, text="", font=F_BOLD,
                                  bg=BG, fg=SUCCESS, anchor=W)
        self._lbl_m1_res.pack(side=LEFT, padx=(0, 16))
        self._lbl_m2_res = Label(self._model_result_frame, text="", font=F_BOLD,
                                  bg=BG, fg=SUCCESS, anchor=W)
        self._lbl_m2_res.pack(side=LEFT, padx=(0, 16))
        self._lbl_m3_res = Label(self._model_result_frame, text="", font=F_BOLD,
                                  bg=BG, fg=SUCCESS, anchor=W)
        self._lbl_m3_res.pack(side=LEFT)

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
        Button(mark_row, text="✓✓ Đúng trang",
               command=self._mark_page_correct,
               bg="#0d2a1a", fg="#4caf50", font=F_MAIN, relief="flat",
               padx=6, cursor="hand2").pack(side=LEFT, padx=(8, 0))
        Button(mark_row, text="✗✗ Sai trang",
               command=self._mark_page_incorrect,
               bg="#2a0d0d", fg=ACCENT, font=F_MAIN, relief="flat",
               padx=6, cursor="hand2").pack(side=LEFT, padx=(4, 0))
        Button(mark_row, text="💾 Lưu ảnh sai",
               command=self._save_wrong_image,
               bg="#2a1a0a", fg="#ffaa55", font=F_MAIN, relief="flat",
               padx=6, cursor="hand2").pack(side=LEFT, padx=(8, 0))
        Button(mark_row, text="💾💾 Sai trang",
               command=self._save_wrong_page,
               bg="#2a1a0a", fg="#ffaa55", font=F_MAIN, relief="flat",
               padx=6, cursor="hand2").pack(side=LEFT, padx=(4, 0))
        Button(mark_row, text="📋 Lưu lỗi+GT",
               command=self._save_lpr_error_image,
               bg="#0d2a1a", fg="#4cdf80", font=F_MAIN, relief="flat",
               padx=6, cursor="hand2").pack(side=LEFT, padx=(8, 0))
        Button(mark_row, text="📂 GT",
               command=self._open_gt_folder,
               bg=CARD, fg="#4cdf80", font=F_MAIN, relief="flat",
               padx=6, cursor="hand2").pack(side=LEFT, padx=(2, 0))
        self.lbl_mark_state = Label(mark_row, text="", font=F_MONO,
                                     bg=BG, fg=DIM)
        self.lbl_mark_state.pack(side=LEFT, padx=(12, 0))

        # Detection detail table — đặt ở bottom trước khi pack expand area
        if _DET_TABLE_OK:
            self._det_table = _DetTablePanel(right, on_select=self._on_det_row_select)
            self._det_table.pack(fill=X, side=BOTTOM)
        else:
            self._det_table = None

        # Horizontal split: image view (left) | filmstrip grid (right)
        from tkinter import PanedWindow as _PW
        self._view_paned = _PW(right, orient=HORIZONTAL, sashwidth=5,
                               bg="#0d0d1e", sashrelief=RAISED, bd=0)
        self._view_paned.pack(fill=BOTH, expand=True)

        self.panels_frame = Frame(self._view_paned, bg=BG)
        self._view_paned.add(self.panels_frame, minsize=300, stretch="always")

        self._grid_outer = Frame(self._view_paned, bg="#0d0d1e")
        self._view_paned.add(self._grid_outer, minsize=160, stretch="never")
        self._build_grid_panel()

        # Panel 1
        self.panel1_frame = Frame(self.panels_frame, bg=BG)
        self.panel1_frame.pack(side=LEFT, fill=BOTH, expand=True)

        self.lbl_panel1_title = Label(self.panel1_frame, text="",
                                       font=F_BOLD, bg=CARD, fg=ACCENT2,
                                       anchor=CENTER, pady=3)
        self.lbl_panel1_title.pack(fill=X)

        self.canvas = Canvas(self.panel1_frame, bg="#0d0d1a",
                             highlightthickness=0, cursor="fleur")
        self.canvas.pack(fill=BOTH, expand=True, padx=0, pady=2)
        self._canvas_hint = self.canvas.create_text(
            400, 200, text="Chọn ảnh để nhận diện",
            fill=DIM, font=("Segoe UI", 14), anchor=CENTER, tags="hint")

        # Panel 2 (hidden by default)
        self.panel2_frame = Frame(self.panels_frame, bg=BG)

        self.lbl_panel2_title = Label(self.panel2_frame, text="",
                                       font=F_BOLD, bg=CARD, fg=ACCENT2,
                                       anchor=CENTER, pady=3)
        self.lbl_panel2_title.pack(fill=X)

        self.canvas2 = Canvas(self.panel2_frame, bg="#0d0d1a",
                              highlightthickness=0, cursor="fleur")
        self.canvas2.pack(fill=BOTH, expand=True, padx=0, pady=2)

        self.canvas.bind("<Configure>",          self._on_canvas_configure)
        self.canvas.bind("<MouseWheel>",         self._on_canvas_scroll)
        self.canvas.bind("<Control-MouseWheel>", self._on_canvas_scroll)
        self.canvas.bind("<ButtonPress-1>",      self._on_pan_press)
        self.canvas.bind("<B1-Motion>",          self._on_pan_drag)
        self.canvas.bind("<Double-Button-1>",    self._on_canvas1_zoom)
        self.canvas2.bind("<Double-Button-1>",   self._on_canvas2_zoom)
        # Middle mouse pan (like BBoxEditor)
        self.canvas.bind("<ButtonPress-2>",      self._on_mmb_press)
        self.canvas.bind("<B2-Motion>",          self._on_mmb_drag)
        self.canvas.bind("<ButtonRelease-2>",    self._on_mmb_release)
        # Ctrl+drag to pan
        self.canvas.bind("<Control-ButtonPress-1>", self._on_mmb_press)
        self.canvas.bind("<Control-B1-Motion>",     self._on_mmb_drag)
        self.canvas.bind("<Control-ButtonRelease-1>", self._on_mmb_release)

        if _DND_OK:
            try:
                self.canvas.drop_target_register(DND_FILES)
                self.canvas.dnd_bind("<<Drop>>", self._on_drop)
            except Exception:
                pass
