# yolo_canvas_mixin.py — YoloCanvasMixin — render canvas, zoom, pan (dual canvas so sánh model)
import os
from tkinter import *
from tkinter import filedialog, messagebox, ttk
from ...core.constants import (BG, CARD, ACCENT, ACCENT2, TEXT, DIM, SUCCESS,
                         F_MAIN, F_BOLD, F_MONO, IMAGE_EXTENSIONS)
from ...core.settings import (_bind_cfg, _cfg_dir, _CFG, _cfg_save,
                        _bind_history, _push_history, _get_history)
try:
    from PIL import Image, ImageDraw, ImageTk
    _PIL_OK = True
except ImportError:
    _PIL_OK = False


class YoloCanvasMixin:
    """Mixin: vẽ ảnh lên canvas, zoom/pan chuột giữa + kéo chuột trái."""

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

    # ======================================================== ZOOM / RENDER ==

    def _render_display(self):
        """Re-render Canvas từ PIL với zoom & pan hiện tại."""
        if not _PIL_OK:
            return
        pil = (self._pil1_orig
               if (self.v_show_original.get() and self._pil1_orig)
               else self._pil1_full)
        if pil is None:
            return
        self.canvas.update_idletasks()
        cw = max(self.canvas.winfo_width(),  400)
        ch = max(self.canvas.winfo_height(), 300)
        if self._zoom_factor == 0.0:
            scale = min(cw / pil.width, ch / pil.height)  # fit inside, giữ tỉ lệ
            nw = max(1, int(pil.width  * scale))
            nh = max(1, int(pil.height * scale))
            img = pil.resize((nw, nh), Image.Resampling.LANCZOS)
            self._img_pos = [(cw - nw) // 2, (ch - nh) // 2]
            self.lbl_zoom.config(text="Fit")
        else:
            nw = max(1, int(pil.width  * self._zoom_factor))
            nh = max(1, int(pil.height * self._zoom_factor))
            img = pil.resize((nw, nh), Image.Resampling.LANCZOS)
            self.lbl_zoom.config(text=f"{int(self._zoom_factor * 100)}%")
        self._photo_ref = ImageTk.PhotoImage(image=img)
        self.canvas.delete("all")
        self.canvas.create_image(self._img_pos[0], self._img_pos[1],
                                  anchor=NW, image=self._photo_ref, tags="img")
        self._draw_zoomtest_overlay()

    def _draw_zoomtest_overlay(self):
        """Vẽ overlay tạm (tím, tag zoomtest_item) cho kết quả '🔎 Test vùng zoom' —
        tách biệt hoàn toàn khỏi kết quả detect chính (_pil1_full), không lưu label/cache."""
        if not getattr(self, "_zoomtest_active", False) or not self._zoomtest_boxes:
            return
        # _zoom_factor==0.0 (Fit) chỉ là sentinel — scale thật đã áp dụng cho ảnh hiển thị
        # trong _render_display() phía trên nhưng không lưu lại, nên tính lại ở đây.
        pil = self._pil1_orig or self._pil1_full
        if pil is None:
            return
        cw = max(self.canvas.winfo_width(), 400)
        ch = max(self.canvas.winfo_height(), 300)
        scale = self._zoom_factor if self._zoom_factor > 0 else min(cw / pil.width, ch / pil.height)
        off_x, off_y = self._img_pos[0], self._img_pos[1]
        color = "#e040fb"
        for cid, x1, y1, x2, y2, conf in self._zoomtest_boxes:
            cx1 = int(x1 * scale) + off_x
            cy1 = int(y1 * scale) + off_y
            cx2 = int(x2 * scale) + off_x
            cy2 = int(y2 * scale) + off_y
            name  = self._model1_names.get(cid, str(cid))
            txt   = f" 🔎{cid}:{name} {conf:.2f} "
            txt_w = max(len(txt) * 7, 30)
            self.canvas.create_rectangle(cx1, cy1, cx2, cy2,
                outline=color, width=2, dash=(3, 2), tags="zoomtest_item")
            self.canvas.create_rectangle(cx1, cy1 - 17, cx1 + txt_w, cy1,
                fill=color, outline="", tags="zoomtest_item")
            self.canvas.create_text(cx1 + 3, cy1 - 8, text=txt, fill="white",
                font=("Segoe UI", 8, "bold"), anchor=W, tags="zoomtest_item")

    def _on_canvas_configure(self, _event=None):
        """Auto-refit khi canvas thay đổi kích thước."""
        if self._zoom_factor == 0.0:
            self._render_display()

    def _on_pan_press(self, event):
        if self._zoom_factor == 0.0:
            return
        self._clear_zoomtest_overlay()  # raw pan chỉ move ảnh, không re-render → overlay sẽ lệch
        self._pan_start  = (event.x, event.y)
        self._pan_origin = list(self._img_pos)

    def _on_pan_drag(self, event):
        if self._pan_start is None or self._zoom_factor == 0.0:
            return
        dx = event.x - self._pan_start[0]
        dy = event.y - self._pan_start[1]
        self._img_pos = [self._pan_origin[0] + dx, self._pan_origin[1] + dy]
        # Di chuyển item trực tiếp — không render lại
        items = self.canvas.find_withtag("img")
        if items:
            self.canvas.coords(items[0], self._img_pos[0], self._img_pos[1])

    def _on_mmb_press(self, event):
        """Middle mouse / Ctrl+drag — bắt đầu pan (hoạt động ở mọi zoom level)."""
        pil = self._pil1_full or self._pil1_orig
        if self._zoom_factor == 0.0 and pil:
            cw = max(self.canvas.winfo_width(), 400)
            ch = max(self.canvas.winfo_height(), 300)
            fit = min(cw / pil.width, ch / pil.height)
            self._zoom_factor = fit
            nw = int(pil.width * fit)
            nh = int(pil.height * fit)
            self._img_pos = [(cw - nw) // 2, (ch - nh) // 2]
            self._render_display()
        self._clear_zoomtest_overlay()  # raw pan chỉ move ảnh, không re-render → overlay sẽ lệch
        self._mmb_pan_start  = (event.x, event.y)
        self._mmb_pan_origin = list(self._img_pos)
        self.canvas.config(cursor="fleur")

    def _on_mmb_drag(self, event):
        """Middle mouse / Ctrl+drag — kéo pan."""
        if not hasattr(self, "_mmb_pan_start") or self._mmb_pan_start is None:
            return
        dx = event.x - self._mmb_pan_start[0]
        dy = event.y - self._mmb_pan_start[1]
        self._img_pos = [self._mmb_pan_origin[0] + dx,
                         self._mmb_pan_origin[1] + dy]
        items = self.canvas.find_withtag("img")
        if items:
            self.canvas.coords(items[0], self._img_pos[0], self._img_pos[1])

    def _on_mmb_release(self, event):
        """Middle mouse / Ctrl+drag — kết thúc pan."""
        self._mmb_pan_start = None
        self.canvas.config(cursor="fleur")

    def _zoom_step(self, delta: float):
        """delta=0.0 resets to fit; otherwise shifts zoom factor."""
        if delta == 0.0:
            self._zoom_factor = 0.0
            self._img_pos = [0, 0]
        else:
            pil = self._pil1_full
            cw  = max(self.canvas.winfo_width(),  400)
            ch  = max(self.canvas.winfo_height(), 300)
            if self._zoom_factor == 0.0:
                if pil:
                    self._zoom_factor = min(cw / pil.width, ch / pil.height)
                else:
                    self._zoom_factor = 1.0
            old = self._zoom_factor
            self._zoom_factor = max(0.05, min(8.0, self._zoom_factor + delta))
            # Zoom về tâm canvas
            if pil and old > 0:
                ratio = self._zoom_factor / old
                cx, cy = cw / 2, ch / 2
                self._img_pos[0] = int(cx - (cx - self._img_pos[0]) * ratio)
                self._img_pos[1] = int(cy - (cy - self._img_pos[1]) * ratio)
        self._render_display()

    def _on_canvas_scroll(self, event):
        """Scroll to zoom centered on cursor position (like BBoxEditor)."""
        pil = self._pil1_full or self._pil1_orig
        if pil is None:
            return
        factor = 1.15 if event.delta > 0 else (1.0 / 1.15)
        cw = max(self.canvas.winfo_width(), 400)
        ch = max(self.canvas.winfo_height(), 300)
        if self._zoom_factor == 0.0:
            fit = min(cw / pil.width, ch / pil.height)
            self._zoom_factor = fit
            nw = int(pil.width * fit)
            nh = int(pil.height * fit)
            self._img_pos = [(cw - nw) // 2, (ch - nh) // 2]
        old = self._zoom_factor
        new = max(0.05, min(8.0, old * factor))
        if abs(new - old) < 0.001:
            return
        ratio = new / old
        cx, cy = event.x, event.y
        self._img_pos[0] = int(cx - (cx - self._img_pos[0]) * ratio)
        self._img_pos[1] = int(cy - (cy - self._img_pos[1]) * ratio)
        self._zoom_factor = new
        self._render_display()
