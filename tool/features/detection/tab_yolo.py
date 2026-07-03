# tab_yolo.py — YOLO Detection tab
#
# Mixin architecture (2026-07-03): file gốc ~7017 dòng đã được tách thành
# YoloTab (đây, ~230 dòng: __init__ + _build + _build_statusbar) + 17 file
# mixin/helper sibling trong cùng thư mục (xem CODE_GRAPH.md để biết chi tiết
# từng file). Theo đúng pattern đã dùng cho tab_iparking_image.py.
import threading
from tkinter import *

from ...core.constants import BG, CARD, DIM, F_MAIN
from ...core.settings import _bind_cfg, _CFG

from .yolo_model_mixin import YoloModelMixin
from .yolo_imagelist_mixin import YoloImageListMixin
from .yolo_review_mixin import YoloReviewMixin
from .yolo_nav_mixin import YoloNavMixin
from .yolo_canvas_mixin import YoloCanvasMixin
from .yolo_grid_mixin import YoloGridMixin
from .yolo_cache_mixin import YoloCacheMixin
from .yolo_render_mixin import YoloRenderMixin
from .yolo_detect_mixin import YoloDetectMixin
from .yolo_detect_all_mixin import YoloDetectAllMixin
from .yolo_lpr_mixin import YoloLprMixin
from .yolo_eval_mixin import YoloEvalMixin
from .yolo_eval_validate_mixin import YoloEvalValidateMixin
from .yolo_video_mixin import YoloVideoMixin
from .yolo_video_window_mixin import YoloVideoWindowMixin
from .yolo_layout_mixin import YoloLayoutMixin


class YoloTab(Frame, YoloModelMixin, YoloImageListMixin, YoloReviewMixin,
              YoloNavMixin, YoloCanvasMixin, YoloGridMixin, YoloCacheMixin,
              YoloRenderMixin, YoloDetectMixin, YoloDetectAllMixin,
              YoloLprMixin, YoloEvalMixin, YoloEvalValidateMixin,
              YoloVideoMixin, YoloVideoWindowMixin, YoloLayoutMixin):

    def __init__(self, master, root):
        super().__init__(master, bg=BG)
        self.root = root

        self.current_image_path = None
        self.model = None
        self.model2 = None
        self.model3 = None
        self._model1_type  = "yolo"     # "yolo" | "rfdetr" | "onnx"
        self._model1_names = {}
        self._model2_type  = "yolo"     # "yolo" | "rfdetr" | "onnx"
        self._model2_names = {}
        self._model3_names = {}
        self._model3_type  = "rfdetr"   # "rfdetr" | "yolo" | "onnx"
        self.class_ids = []
        self.image_list = []
        self._photo_ref = None
        self._photo_ref2 = None
        self._last_annotated_bgr = None

        self.v_model_path    = StringVar()
        self.v_model2_path   = StringVar()
        self.v_model3_path   = StringVar()
        self.v_subfolder     = BooleanVar(value=False)
        self.v_show_original = BooleanVar(value=False)
        self.v_check_folder  = StringVar()
        self.v_wrong_folder  = StringVar()
        self._v_wf_segs  = [StringVar() for _ in range(5)]
        self._wf_combos  = []
        self.v_conf_thresh   = DoubleVar(value=0.25)
        self.v_conf          = DoubleVar(value=0.30)
        self.v_iou           = DoubleVar(value=0.45)
        self.v_interval      = StringVar(value="2.0")
        self.v_line_width    = IntVar(value=2)
        self.v_font_size     = IntVar(value=11)
        self.v_export_draw   = BooleanVar(value=True)
        self.v_export_rename = BooleanVar(value=False)
        self._v_search       = StringVar()
        self._pil1_full = None
        self._pil1_orig = None
        self._pil2_full = None
        self._last_results1 = None
        self._zoom_factor = 0.0
        self._img_pos     = [0, 0]   # vị trí ảnh trên canvas (top-left)
        self._pan_start   = None     # điểm bắt đầu kéo chuột (left drag)
        self._pan_origin  = [0, 0]   # _img_pos tại lúc bắt đầu kéo
        self._mmb_pan_start  = None  # middle mouse / Ctrl+drag pan
        self._mmb_pan_origin = [0, 0]
        self._search_after = None
        self._autoplay_id = None
        self._last_n_det = -1
        self._tree_iid_map = {}
        self._path_to_iid = {}
        self._all_images = []
        self._base_folder = None
        self._active_filter = "all"
        self._review_state = dict(_CFG.get("yolo.review_states", {}))

        # Detect All cache & filters
        # box tuple: (cid, cx_n, cy_n, w_n, h_n, w_px, h_px, conf_score)  ← indices 0-7
        self._det_cache = {}
        self._det_cache_lock = threading.Lock()
        self._det_stop_flag = False
        self._det_running = False
        self._detecting   = False   # True khi single-image detect đang chạy
        self._det_pending = False   # re-detect queued sau khi detect xong
        self._plot_after  = None    # debounce id cho _on_plot_param_change
        self._flt_class_var = StringVar(value="Tất cả")
        self._flt_ndet_min_var = StringVar(value="")
        self._flt_ndet_max_var = StringVar(value="")
        self._flt_area_min_var = StringVar(value="")
        self._flt_area_max_var = StringVar(value="")
        self._flt_w_min_var = StringVar(value="")
        self._flt_w_max_var = StringVar(value="")
        self._flt_h_min_var = StringVar(value="")
        self._flt_h_max_var = StringVar(value="")
        self._flt_schedule_after = None

        # Grid panel (filmstrip)
        self._grid_page = 0
        self._grid_cols_var = IntVar(value=4)
        self._grid_rows_var = IntVar(value=4)
        self._grid_thumb_w = 0
        self._grid_thumb_h = 0
        self._grid_rendered_cache = {}
        self._grid_cells = []
        self._grid_render_idx = 0
        self._grid_rebuild_after = None
        self._grid_reflow_after  = None
        self._session_restored = False

        # LPR check (kiểm tra biển số sau detect)
        self.v_check_lpr      = BooleanVar(value=False)
        self._lpr_timeout_var = IntVar(value=10)
        self._lpr_url_vars    = [StringVar(value="http://localhost:8000/alpr"),
                                 StringVar(value=""),
                                 StringVar(value="")]
        self._lpr_url_combos  = [None, None, None]  # set in _build_toolbar
        self._lpr_fullimg_vars = [BooleanVar(value=False),
                                  BooleanVar(value=False),
                                  BooleanVar(value=False)]
        self._lpr_conn_lbl           = None   # set in _build_toolbar
        self._lpr_font_size_var      = IntVar(value=28)
        self.v_lpr_batch             = BooleanVar(value=False)
        self._lpr_cache              = {}     # {path: [(x1,y1,x2,y2,plate),...]}
        self._lpr_cache_lock         = threading.Lock()
        self._flt_lpr_var            = StringVar(value="Tất cả")
        self._last_lpr_plates_result = []     # [(x1,y1,x2,y2,plate), ...] từ lần overlay gần nhất

        _bind_cfg("yolo.model_path",    self.v_model_path)
        _bind_cfg("yolo.check_folder",  self.v_check_folder)
        _bind_cfg("yolo.conf_thresh",   self.v_conf_thresh)
        _bind_cfg("yolo.conf",          self.v_conf)
        _bind_cfg("yolo.iou",           self.v_iou)
        _bind_cfg("yolo.interval",      self.v_interval)
        _bind_cfg("yolo.subfolder",     self.v_subfolder)
        _bind_cfg("yolo.show_original", self.v_show_original)
        _bind_cfg("yolo.line_width",     self.v_line_width)
        _bind_cfg("yolo.font_size",      self.v_font_size)
        _bind_cfg("yolo.export_draw",   self.v_export_draw)
        _bind_cfg("yolo.export_rename", self.v_export_rename)
        _bind_cfg("yolo.grid_cols",     self._grid_cols_var)
        _bind_cfg("yolo.grid_rows",     self._grid_rows_var)
        _bind_cfg("yolo.check_lpr",      self.v_check_lpr)
        _bind_cfg("yolo.lpr_timeout",    self._lpr_timeout_var)
        _bind_cfg("yolo.lpr_font_size",  self._lpr_font_size_var)
        _bind_cfg("yolo.lpr_batch",      self.v_lpr_batch)
        for i, v in enumerate(self._lpr_fullimg_vars):
            _bind_cfg(f"yolo.lpr_fullimg{i+1}", v)
        for i, sv in enumerate(self._v_wf_segs):
            _bind_cfg(f"yolo.wf_s{i+1}", sv)
        # Migrate cài đặt cũ (1 ô) sang ô đầu tiên
        if not any(_CFG.get(f"yolo.wf_s{i+1}", "") for i in range(5)):
            old = _CFG.get("yolo.wrong_folder", "")
            if old:
                self._v_wf_segs[0].set(old)
        self._update_wrong_path()
        for sv in self._v_wf_segs:
            sv.trace_add("write", lambda *_: self._update_wrong_path())

        self._build()
        self.after(200, self._auto_load_model)
        self.after(300, self._bind_keys)
        self.after(400, self._sync_slider_labels)
        self.after(700, self._auto_restore_session)

    # ================================================================ BUILD ==

    def _build(self):
        self._build_toolbar()
        self._build_content()
        self._build_statusbar()

    def _build_statusbar(self):
        self.v_status = StringVar(value="Sẵn sàng")
        Label(self, textvariable=self.v_status,
              font=F_MAIN, bg=CARD, fg=DIM, anchor=W, padx=8,
              ).pack(fill=X, side=BOTTOM)

