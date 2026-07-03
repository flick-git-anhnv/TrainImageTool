# yolo_grid_mixin.py — YoloGridMixin — panel lưới thumbnail (filmstrip) có phân trang
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
from ...core.ui_helpers import GridPageNav
from .yolo_onnx import _THUMB_PALETTE
from .yolo_utils import _path_review_state


class YoloGridMixin:
    """Mixin: panel lưới thumbnail (filmstrip), phân trang, render thumbnail."""

    # ============================================================= GRID PANEL ==

    def _build_grid_panel(self):
        """Filmstrip grid: pagination n_rows×n_cols, fill toàn bộ panel."""
        parent = self._grid_outer

        # ── Nav bar ────────────────────────────────────────────────────────
        self._grid_page_nav = GridPageNav(
            parent,
            on_first=lambda: self._go_grid_page_abs(0),
            on_prev=lambda: self._go_grid_page(-1),
            on_next=lambda: self._go_grid_page(+1),
            on_last=lambda: self._go_grid_page_abs(-1),
            on_direct=self._go_grid_page_direct,
        )
        self._grid_page_nav.pack(side=BOTTOM, fill=X)

        # ── Toolbar: Cột + Hàng ────────────────────────────────────────────
        gtb = Frame(parent, bg=CARD, padx=6, pady=2)
        gtb.pack(side=BOTTOM, fill=X)

        for label, var, lo, hi in [
            ("Cột:", self._grid_cols_var, 1, 10),
            ("Hàng:", self._grid_rows_var, 1, 10),
        ]:
            Label(gtb, text=label, bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
            spn = Spinbox(gtb, from_=lo, to=hi, textvariable=var,
                          width=2, bg="#16162a", fg=TEXT, insertbackground=TEXT,
                          buttonbackground=ACCENT2, relief="flat", font=F_MAIN,
                          command=self._on_grid_size_change)
            spn.bind("<Return>",   lambda e: self._on_grid_size_change())
            spn.bind("<FocusOut>", lambda e: self._on_grid_size_change())
            spn.pack(side=LEFT, padx=(2, 10))

        # ── Grid area (không scrollbar — pagination fill panel) ────────────
        self._grid_frame = Frame(parent, bg="#0d0d1e")
        self._grid_frame.pack(fill=BOTH, expand=True)
        self._grid_frame.bind("<Configure>", self._on_grid_frame_configure)

        self._grid_inner = Frame(self._grid_frame, bg="#0d0d1e")
        self._grid_inner.pack(fill=BOTH, expand=True)

    def _on_grid_frame_configure(self, event):
        if self._grid_reflow_after:
            self.after_cancel(self._grid_reflow_after)
        self._grid_reflow_after = self.after(
            350, lambda: self._reflow_grid(event.width, event.height))

    def _reflow_grid(self, canvas_w: int, canvas_h: int):
        """Tính lại tw/th từ kích thước panel, re-render thumbnail không rebuild widget."""
        n_cols = max(1, self._grid_cols_var.get())
        n_rows = max(1, self._grid_rows_var.get())
        tw, th = self._calc_thumb_size(canvas_w, canvas_h, n_cols, n_rows)
        if tw == self._grid_thumb_w and th == self._grid_thumb_h:
            return
        self._grid_thumb_w, self._grid_thumb_h = tw, th
        self._grid_rendered_cache.clear()
        blank = self._make_blank_thumb(tw, th)
        for cell in self._grid_cells:
            cell["rendered"] = False
            try:
                if blank:
                    cell["img_lbl"].config(image=blank)
                    cell["img_lbl"]._blank_ref = blank
            except Exception:
                pass
        self._grid_render_idx = 0
        self._schedule_film_render()

    @staticmethod
    def _calc_thumb_size(cw: int, ch: int, n_cols: int, n_rows: int):
        tw = max(40, (cw - 4 * (n_cols + 1)) // n_cols)
        th = max(30, (ch - 4 * (n_rows + 1)) // n_rows)
        return tw, th

    def _on_grid_size_change(self):
        """Cols/rows thay đổi → rebuild trang hiện tại."""
        self._grid_rendered_cache.clear()
        self._schedule_grid_rebuild()

    def _schedule_grid_rebuild(self):
        if self._grid_rebuild_after:
            self.after_cancel(self._grid_rebuild_after)
        self._grid_rebuild_after = self.after(150, self._rebuild_grid)

    def _go_grid_page(self, delta: int):
        if not self.image_list:
            return
        n_cols   = max(1, self._grid_cols_var.get())
        n_rows   = max(1, self._grid_rows_var.get())
        per_page = n_cols * n_rows
        total    = len(self.image_list)
        max_page = max(0, (total - 1) // per_page)
        self._grid_page = max(0, min(max_page, self._grid_page + delta))
        self._rebuild_grid()

    def _go_grid_page_abs(self, page: int):
        """Nhảy tới trang đầu (0) hoặc trang cuối (-1)."""
        if not self.image_list:
            return
        n_cols   = max(1, self._grid_cols_var.get())
        n_rows   = max(1, self._grid_rows_var.get())
        per_page = n_cols * n_rows
        total    = len(self.image_list)
        max_page = max(0, (total - 1) // per_page)
        self._grid_page = 0 if page == 0 else max_page
        self._rebuild_grid()

    def _go_grid_page_direct(self):
        """Nhảy tới số trang nhập trong Entry (1-indexed, validate + clamp)."""
        if not self.image_list:
            return
        try:
            page = int(self._grid_page_nav.page_var.get()) - 1  # 1-indexed → 0-indexed
        except ValueError:
            self._grid_page_nav.page_var.set(str(self._grid_page + 1))
            return
        n_cols   = max(1, self._grid_cols_var.get())
        n_rows   = max(1, self._grid_rows_var.get())
        per_page = n_cols * n_rows
        total    = len(self.image_list)
        max_page = max(0, (total - 1) // per_page)
        new_page = max(0, min(max_page, page))
        if new_page == self._grid_page:
            self._grid_page_nav.page_var.set(str(new_page + 1))
            return
        self._grid_page = new_page
        self._rebuild_grid()

    def _rebuild_grid(self):
        if not hasattr(self, "_grid_inner"):
            return

        for w in self._grid_inner.winfo_children():
            w.destroy()
        self._grid_cells.clear()

        files    = self.image_list
        n_cols   = max(1, self._grid_cols_var.get())
        n_rows   = max(1, self._grid_rows_var.get())
        per_page = n_cols * n_rows
        total    = len(files)

        if not total:
            self._grid_page_nav.update(0, 0, 0)
            Label(self._grid_inner, text="Không có ảnh",
                  bg="#0d0d1e", fg=DIM, font=F_MAIN).grid(
                  row=0, column=0, pady=20)
            return

        max_page = max(0, (total - 1) // per_page)
        self._grid_page = max(0, min(max_page, self._grid_page))
        start = self._grid_page * per_page
        end   = min(start + per_page, total)
        self._grid_page_nav.update(self._grid_page, max_page, total)

        # Tính tw/th từ kích thước thực của frame
        fw = max(self._grid_frame.winfo_width(),  200)
        fh = max(self._grid_frame.winfo_height(), 200)
        tw, th = self._calc_thumb_size(fw, fh, n_cols, n_rows)
        if self._grid_thumb_w != tw or self._grid_thumb_h != th:
            self._grid_rendered_cache.clear()
        self._grid_thumb_w, self._grid_thumb_h = tw, th

        blank_img = self._make_blank_thumb(tw, th)

        for fi_off, fpath in enumerate(files[start:end]):
            row, col = divmod(fi_off, n_cols)
            is_cur   = (fpath == self.current_image_path)
            border   = ACCENT if is_cur else "#2a2a3e"

            cell = Frame(self._grid_inner, bg=border, padx=1, pady=1,
                         cursor="hand2")
            cell.grid(row=row, column=col, padx=2, pady=2, sticky="nsew")

            img_lbl = Label(cell, image=blank_img, bg="#1a1a2e", bd=0,
                            width=tw, height=th)
            img_lbl.pack(fill=BOTH, expand=True)

            det_data = self._det_cache.get(fpath)
            fname    = os.path.basename(fpath)
            n_suffix = (f" [{det_data['n']}]" if det_data is not None else "")
            if len(fname) > 18:
                fname = fname[:16] + "…"
            fn_lbl = Label(cell, text=fname + n_suffix, bg="#111130",
                           fg="#9090bb", font=("Consolas", 7), anchor=W, padx=2)
            fn_lbl.pack(fill=X)

            state = _path_review_state(fpath)
            if state == "correct":
                Label(cell, text="✔", bg="#1a3a1a", fg=SUCCESS,
                      font=("Segoe UI", 7)).pack(fill=X)
            elif state == "incorrect":
                Label(cell, text="✖", bg="#3a1a1a", fg="#e06060",
                      font=("Segoe UI", 7)).pack(fill=X)

            for widget in (cell, img_lbl, fn_lbl):
                widget.bind("<Button-1>", lambda e, p=fpath: self._grid_click(p))

            self._grid_cells.append({
                "path": fpath, "frame": cell, "img_lbl": img_lbl,
                "fn_lbl": fn_lbl, "rendered": False
            })

        for c in range(n_cols):
            self._grid_inner.columnconfigure(c, weight=1)
        for r in range(n_rows):
            self._grid_inner.rowconfigure(r, weight=1)

        self._grid_render_idx = 0
        self._schedule_film_render()

    def _make_blank_thumb(self, tw: int, th: int):
        if not _PIL_OK:
            return None
        blank = Image.new("RGB", (tw, th), "#1a1a2e")
        return ImageTk.PhotoImage(blank)

    def _schedule_film_render(self):
        BATCH = 10
        end = min(self._grid_render_idx + BATCH, len(self._grid_cells))
        for cell in self._grid_cells[self._grid_render_idx:end]:
            if not cell["rendered"]:
                pil = self._render_grid_thumb(cell["path"])
                if pil is not None:
                    try:
                        tk_img = ImageTk.PhotoImage(pil)
                        cell["img_lbl"].config(image=tk_img, width=0, height=0)
                        cell["img_lbl"]._tk_img = tk_img
                    except Exception:
                        pass
                cell["rendered"] = True
        self._grid_render_idx = end
        if end < len(self._grid_cells):
            self.after(40, self._schedule_film_render)

    def _render_grid_thumb(self, img_path: str):
        """Thumbnail với bbox overlay từ detect cache."""
        if not _PIL_OK:
            return None
        tw, th      = self._grid_thumb_w, self._grid_thumb_h
        in_cache    = img_path in self._det_cache
        lw          = max(1, self.v_line_width.get())
        conf_thresh = max(self.v_conf_thresh.get(), self.v_conf.get())
        cache_key   = (img_path, tw, th, in_cache, lw, conf_thresh)
        if cache_key in self._grid_rendered_cache:
            return self._grid_rendered_cache[cache_key]
        try:
            pil = Image.open(img_path).convert("RGB")
        except Exception:
            return None
        data = self._det_cache.get(img_path)
        if data and data["n"] > 0:
            from PIL import ImageDraw as _ID
            drw = _ID.Draw(pil)
            iw, ih = pil.size
            for box in data["boxes"]:
                if len(box) > 7 and float(box[7]) < conf_thresh:
                    continue
                cid, cx_n, cy_n, w_n, h_n = box[0], box[1], box[2], box[3], box[4]
                x1 = max(0, int((cx_n - w_n / 2) * iw))
                y1 = max(0, int((cy_n - h_n / 2) * ih))
                x2 = min(iw - 1, int((cx_n + w_n / 2) * iw))
                y2 = min(ih - 1, int((cy_n + h_n / 2) * ih))
                color = _THUMB_PALETTE[int(cid) % len(_THUMB_PALETTE)]
                drw.rectangle([x1, y1, x2, y2], outline=color, width=lw)
        pil.thumbnail((tw, th), Image.Resampling.LANCZOS)
        bg_img = Image.new("RGB", (tw, th), "#1a1a2e")
        ox = (tw - pil.width) // 2
        oy = (th - pil.height) // 2
        bg_img.paste(pil, (ox, oy))
        self._grid_rendered_cache[cache_key] = bg_img
        return bg_img

    def _grid_click(self, fpath: str):
        """Click thumbnail → điều hướng đến ảnh đó."""
        if fpath == self.current_image_path:
            return
        self._open_image(fpath)

    def _update_filmstrip(self):
        """Chuyển đúng trang chứa ảnh hiện tại; cập nhật highlight."""
        if not self.image_list or not hasattr(self, "_grid_inner"):
            return
        n_cols   = max(1, self._grid_cols_var.get())
        n_rows   = max(1, self._grid_rows_var.get())
        per_page = n_cols * n_rows
        if self.current_image_path in self.image_list:
            fi           = self.image_list.index(self.current_image_path)
            target_page  = fi // per_page
            if target_page != self._grid_page:
                self._grid_page = target_page
                self._rebuild_grid()
                return
        # Cùng trang — chỉ đổi border
        for cell in self._grid_cells:
            is_cur = (cell["path"] == self.current_image_path)
            try:
                cell["frame"].config(bg=ACCENT if is_cur else "#2a2a3e")
            except Exception:
                pass

    def _refresh_grid_cell(self, img_path: str):
        """Re-render thumbnail + label cho đúng 1 cell, không rebuild toàn grid."""
        if not hasattr(self, "_grid_cells"):
            return
        for cell in self._grid_cells:
            if cell["path"] != img_path:
                continue
            pil = self._render_grid_thumb(img_path)
            if pil is not None and _PIL_OK:
                try:
                    tk_img = ImageTk.PhotoImage(pil)
                    cell["img_lbl"].config(image=tk_img, width=0, height=0)
                    cell["img_lbl"]._tk_img = tk_img
                    cell["rendered"] = True
                except Exception:
                    pass
            det_data = self._det_cache.get(img_path)
            fname    = os.path.basename(img_path)
            if len(fname) > 22:
                fname = fname[:20] + "…"
            n_suffix = (f" [{det_data['n']}]" if det_data is not None else "")
            try:
                cell["fn_lbl"].config(text=fname + n_suffix)
            except Exception:
                pass
            break
