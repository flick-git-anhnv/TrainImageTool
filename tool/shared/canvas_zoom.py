# canvas_zoom.py — Mixin zoom/pan cho Tkinter Canvas viewer
# Dùng chung: tab_bbox, tab_yolo, merge tab DetectLabel
# Pattern BBoxEditor: zoom_level = multiplier trên fit-scale; pan_x/y = pixel offset
from __future__ import annotations


class CanvasZoomMixin:
    """Mixin cung cấp zoom/pan cho bất kỳ class có _canvas và _pil_img.

    Cách dùng:
        class MyView(Frame, CanvasZoomMixin):
            def __init__(self, ...):
                self._zoom_init()
                # bind handlers
                self._canvas.bind("<MouseWheel>", self._on_zoom_wheel)
                self._canvas.bind("<Button-2>",   self._on_pan_start)
                self._canvas.bind("<B2-Motion>",  self._on_pan_drag)
                self._canvas.bind("<ButtonRelease-2>", self._on_pan_end)

            def _render(self, resample=None):
                # sử dụng self._calc_zoom_offsets() để lấy nw,nh,off_x,off_y
                ...
    """

    def _zoom_init(self):
        """Gọi trong __init__ để khởi tạo state."""
        self._zoom_level:       float = 1.0
        self._pan_x:            int   = 0
        self._pan_y:            int   = 0
        self._panning:          bool  = False
        self._pan_start:        tuple = (0, 0)
        self._pan_start_offset: tuple = (0, 0)
        self._zoom_settle_after        = None
        self._render_nw_nh             = None
        # Được cập nhật bởi _calc_zoom_offsets; dùng để zoom-at-cursor
        self._scale: float = 1.0
        self._off_x: int   = 0
        self._off_y: int   = 0

    # ── Override trong subclass ────────────────────────────────────────────────

    def _render(self, resample=None):
        """Re-render canvas. Override bắt buộc trong subclass."""
        raise NotImplementedError("_render() must be implemented by the subclass")

    # ── Public API ─────────────────────────────────────────────────────────────

    def _zoom_reset(self):
        """Reset về fit-to-canvas."""
        if self._zoom_settle_after:
            self._canvas.after_cancel(self._zoom_settle_after)
            self._zoom_settle_after = None
        self._zoom_level = 1.0
        self._pan_x = 0
        self._pan_y = 0
        self._render_nw_nh = None
        self._render()

    def _zoom_step(self, factor: float):
        """Zoom theo factor (>1 phóng to, <1 thu nhỏ), tâm là center canvas."""
        if getattr(self, "_pil_img", None) is None:
            return
        new_zoom = max(0.1, min(20.0, self._zoom_level * factor))
        if abs(new_zoom - self._zoom_level) < 0.001:
            return
        cw = self._canvas.winfo_width()
        ch = self._canvas.winfo_height()
        cx, cy = cw // 2, ch // 2
        # Tính image coords tại center trước khi zoom
        if self._scale > 0:
            img_x = (cx - self._off_x) / self._scale
            img_y = (cy - self._off_y) / self._scale
        else:
            iw, ih = self._pil_img.size
            img_x, img_y = iw / 2.0, ih / 2.0
        iw, ih = self._pil_img.size
        fit_scale = min(cw / iw, ch / ih, 1.0)
        new_scale = fit_scale * new_zoom
        nw = int(iw * new_scale)
        nh = int(ih * new_scale)
        self._pan_x = int(cx - img_x * new_scale - (cw - nw) // 2)
        self._pan_y = int(cy - img_y * new_scale - (ch - nh) // 2)
        self._zoom_level = new_zoom
        if self._zoom_settle_after:
            self._canvas.after_cancel(self._zoom_settle_after)
            self._zoom_settle_after = None
        self._render_nw_nh = None
        self._render()

    def _on_zoom_wheel(self, event):
        """Bind: self._canvas.bind('<MouseWheel>', self._on_zoom_wheel)"""
        if getattr(self, "_pil_img", None) is None:
            return
        factor = 1.25 if event.delta > 0 else (1.0 / 1.25)
        cw = self._canvas.winfo_width()
        ch = self._canvas.winfo_height()
        cx, cy = event.x, event.y
        if self._scale > 0:
            img_x = (cx - self._off_x) / self._scale
            img_y = (cy - self._off_y) / self._scale
        else:
            iw, ih = self._pil_img.size
            img_x, img_y = iw / 2.0, ih / 2.0
        new_zoom = max(0.1, min(20.0, self._zoom_level * factor))
        if abs(new_zoom - self._zoom_level) < 0.001:
            return
        iw, ih = self._pil_img.size
        fit_scale = min(cw / iw, ch / ih, 1.0)
        new_scale = fit_scale * new_zoom
        nw = int(iw * new_scale)
        nh = int(ih * new_scale)
        self._pan_x = int(cx - img_x * new_scale - (cw - nw) // 2)
        self._pan_y = int(cy - img_y * new_scale - (ch - nh) // 2)
        self._zoom_level = new_zoom
        try:
            from PIL import Image as _I
            self._render(resample=_I.BILINEAR)
        except ImportError:
            self._render()
        if self._zoom_settle_after:
            self._canvas.after_cancel(self._zoom_settle_after)

        def _settle():
            self._render_nw_nh = None
            self._render()

        self._zoom_settle_after = self._canvas.after(200, _settle)

    def _on_pan_start(self, event):
        """Bind: self._canvas.bind('<Button-2>', self._on_pan_start)"""
        if getattr(self, "_pil_img", None) is None:
            return
        self._panning = True
        self._pan_start = (event.x, event.y)
        self._pan_start_offset = (self._pan_x, self._pan_y)
        self._canvas.config(cursor="fleur")

    def _on_pan_drag(self, event):
        """Bind: self._canvas.bind('<B2-Motion>', self._on_pan_drag)"""
        if not self._panning:
            return
        dx = event.x - self._pan_start[0]
        dy = event.y - self._pan_start[1]
        self._pan_x = self._pan_start_offset[0] + dx
        self._pan_y = self._pan_start_offset[1] + dy
        self._render()

    def _on_pan_end(self, event):
        """Bind: self._canvas.bind('<ButtonRelease-2>', self._on_pan_end)"""
        self._panning = False
        self._canvas.config(cursor="crosshair")

    # ── Helper tính offset để render ──────────────────────────────────────────

    def _calc_zoom_offsets(self) -> "tuple[float, int, int, int, int]":
        """Trả về (scale, nw, nh, off_x, off_y) dùng để render PIL→canvas.

        Cập nhật self._scale, self._off_x, self._off_y cho zoom-at-cursor.
        """
        if getattr(self, "_pil_img", None) is None:
            return 1.0, 1, 1, 0, 0
        self._canvas.update_idletasks()
        cw = max(self._canvas.winfo_width(), 1)
        ch = max(self._canvas.winfo_height(), 1)
        iw, ih = self._pil_img.size
        fit = min(cw / iw, ch / ih, 1.0)
        scale = fit * self._zoom_level
        nw = max(1, int(iw * scale))
        nh = max(1, int(ih * scale))
        if self._zoom_level <= 1.0:
            self._pan_x = 0
            self._pan_y = 0
        else:
            limit_x = max(cw // 2, nw // 2)
            limit_y = max(ch // 2, nh // 2)
            self._pan_x = max(-limit_x, min(limit_x, self._pan_x))
            self._pan_y = max(-limit_y, min(limit_y, self._pan_y))
        off_x = (cw - nw) // 2 + self._pan_x
        off_y = (ch - nh) // 2 + self._pan_y
        self._scale = scale
        self._off_x = off_x
        self._off_y = off_y
        return scale, nw, nh, off_x, off_y
