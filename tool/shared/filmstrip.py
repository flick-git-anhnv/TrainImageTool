# filmstrip.py — Grid filmstrip widget dùng chung cho tab_bbox và tab_yolo
# Dùng chung: tab_bbox, tab_yolo, merge tab DetectLabel
from __future__ import annotations
import os
from tkinter import *
from tkinter import ttk
from typing import Callable

from ..core.constants import ACCENT, CARD, DIM, TEXT, BG, F_MAIN
from ..core.ui_helpers import GridPageNav

try:
    from PIL import Image, ImageTk
    _PIL_OK = True
except ImportError:
    _PIL_OK = False

_BG_CELL  = "#1a1a2e"
_BG_FNAME = "#111130"
_BG_GRID  = "#0d0d1e"


class FilmstripPanel(Frame):
    """Grid filmstrip phân trang với thumbnail overlay.

    Args:
        get_thumb: callable(path, tw, th) -> PIL.Image | None
            Trả về PIL Image (không phải PhotoImage) để cache đúng.
            Gọi từ main thread. Render async theo batch.
        on_select: callable(path) -> None
        extra_nav: list[dict] nút thêm vào nav bar (text, command, bg, ...)
    """

    def __init__(self, master, *,
                 get_thumb: Callable,
                 on_select: Callable,
                 cols_var: "IntVar | None" = None,
                 rows_var: "IntVar | None" = None,
                 extra_nav: "list | None" = None,
                 **kw):
        super().__init__(master, bg=_BG_GRID, **kw)
        self._get_thumb = get_thumb
        self._on_select = on_select
        self._cols_var  = cols_var or IntVar(value=4)
        self._rows_var  = rows_var or IntVar(value=4)
        self._extra_nav = extra_nav or []

        self._files:        list = []
        self._current_path: str  = ""
        self._cells:        list = []
        self._render_idx:   int  = 0
        self._pil_cache:    dict = {}     # {(path,tw,th): PIL.Image}
        self._tk_cache:     dict = {}     # {(path,tw,th): ImageTk.PhotoImage}
        self._page:         int  = 0
        self._thumb_w:      int  = 0
        self._thumb_h:      int  = 0
        self._rebuild_after      = None
        self._reflow_after       = None
        self._blank_tk           = None

        self._build()

    # ── Build ──────────────────────────────────────────────────────────────────

    def _build(self):
        self._page_nav = GridPageNav(
            self,
            on_first=lambda: self._go_abs(0),
            on_prev= lambda: self._go_delta(-1),
            on_next= lambda: self._go_delta(+1),
            on_last= lambda: self._go_abs(-1),
            on_direct=self._go_direct,
            extra_right=self._extra_nav or None,
        )
        self._page_nav.pack(side=BOTTOM, fill=X)

        tb = Frame(self, bg=CARD, padx=6, pady=2)
        tb.pack(side=BOTTOM, fill=X)
        for label, var in (("Cột:", self._cols_var), ("Hàng:", self._rows_var)):
            Label(tb, text=label, bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
            spn = Spinbox(tb, from_=1, to=10, textvariable=var, width=2,
                          bg="#16162a", fg=TEXT, insertbackground=TEXT,
                          buttonbackground="#4A3F8C", relief="flat", font=F_MAIN,
                          command=self._on_size_change)
            spn.bind("<Return>",   lambda _e: self._on_size_change())
            spn.bind("<FocusOut>", lambda _e: self._on_size_change())
            spn.pack(side=LEFT, padx=(2, 10))

        self._grid_frame = Frame(self, bg=_BG_GRID)
        self._grid_frame.pack(fill=BOTH, expand=True)
        self._grid_frame.bind("<Configure>", self._on_frame_configure)

        self._inner = Frame(self._grid_frame, bg=_BG_GRID)
        self._inner.pack(fill=BOTH, expand=True)

    # ── Public API ─────────────────────────────────────────────────────────────

    def load(self, file_list: list, current_path: str = ""):
        """Nạp danh sách ảnh mới, rebuild grid từ đầu."""
        self._files = list(file_list)
        self._pil_cache.clear()
        self._tk_cache.clear()
        self._page = 0
        self._current_path = current_path
        self._rebuild()

    def set_current(self, path: str):
        """Cập nhật ảnh đang chọn; tự scroll tới trang nếu cần."""
        if path == self._current_path and path:
            self._refresh_highlights()
            return
        self._current_path = path
        if not self._files:
            return
        per = self._per_page()
        try:
            fi = self._files.index(path)
        except ValueError:
            self._refresh_highlights()
            return
        target = fi // per
        if target != self._page:
            self._page = target
            self._rebuild()
        else:
            self._invalidate(path)
            self._refresh_highlights()
            self._re_render_cell(path)

    def invalidate_cache(self, path: "str | None" = None):
        """Xóa thumbnail cache (khi label/detect thay đổi)."""
        if path is None:
            self._pil_cache.clear()
            self._tk_cache.clear()
        else:
            for k in [k for k in self._pil_cache if k[0] == path]:
                del self._pil_cache[k]
            for k in [k for k in self._tk_cache if k[0] == path]:
                del self._tk_cache[k]

    # ── Pagination ─────────────────────────────────────────────────────────────

    def _per_page(self) -> int:
        return max(1, self._cols_var.get()) * max(1, self._rows_var.get())

    def _max_page(self) -> int:
        n = len(self._files)
        return max(0, (n - 1) // self._per_page()) if n else 0

    def _go_delta(self, d: int):
        self._page = max(0, min(self._max_page(), self._page + d))
        self._rebuild()

    def _go_abs(self, p: int):
        self._page = 0 if p == 0 else self._max_page()
        self._rebuild()

    def _go_direct(self):
        try:
            p = int(self._page_nav.page_var.get()) - 1
        except ValueError:
            self._page_nav.page_var.set(str(self._page + 1))
            return
        self._page = max(0, min(self._max_page(), p))
        self._rebuild()

    def _on_size_change(self):
        self._pil_cache.clear()
        self._tk_cache.clear()
        self._schedule_rebuild()

    def _on_frame_configure(self, event):
        if self._reflow_after:
            self.after_cancel(self._reflow_after)
        self._reflow_after = self.after(350,
            lambda: self._reflow(event.width, event.height))

    def _reflow(self, cw: int, ch: int):
        nc = max(1, self._cols_var.get())
        nr = max(1, self._rows_var.get())
        tw = max(40, (cw - 4*(nc+1)) // nc)
        th = max(30, (ch - 4*(nr+1)) // nr)
        if tw == self._thumb_w and th == self._thumb_h:
            return
        self._thumb_w, self._thumb_h = tw, th
        self._pil_cache.clear()
        self._tk_cache.clear()
        self._blank_tk = None
        blank = self._make_blank()
        for cell in self._cells:
            cell["rendered"] = False
            try:
                cell["img_lbl"].config(image=blank)
                cell["img_lbl"]._blank = blank
            except Exception:
                pass
        self._render_idx = 0
        self._schedule_film_render()

    def _schedule_rebuild(self):
        if self._rebuild_after:
            self.after_cancel(self._rebuild_after)
        self._rebuild_after = self.after(150, self._rebuild)

    # ── Grid build ─────────────────────────────────────────────────────────────

    def _rebuild(self):
        for w in self._inner.winfo_children():
            w.destroy()
        self._cells.clear()

        total  = len(self._files)
        nc     = max(1, self._cols_var.get())
        nr     = max(1, self._rows_var.get())
        per    = nc * nr
        mp     = self._max_page()
        self._page = max(0, min(mp, self._page))
        start  = self._page * per
        end    = min(start + per, total)

        self._page_nav.update(self._page, mp, total)

        if not total:
            Label(self._inner, text="Không có ảnh",
                  bg=_BG_GRID, fg=DIM, font=F_MAIN).grid(row=0, column=0, pady=20)
            return

        fw = max(self._grid_frame.winfo_width(), 200)
        fh = max(self._grid_frame.winfo_height(), 200)
        tw = max(40, (fw - 4*(nc+1)) // nc)
        th = max(30, (fh - 4*(nr+1)) // nr)
        if tw != self._thumb_w or th != self._thumb_h:
            self._pil_cache.clear()
            self._tk_cache.clear()
        self._thumb_w, self._thumb_h = tw, th
        self._blank_tk = None

        blank = self._make_blank()
        for off, fpath in enumerate(self._files[start:end]):
            row, col = divmod(off, nc)
            is_cur   = (fpath == self._current_path)
            frame    = Frame(self._inner,
                             bg=ACCENT if is_cur else "#2a2a3e",
                             padx=1, pady=1, cursor="hand2")
            frame.grid(row=row, column=col, padx=2, pady=2, sticky="nsew")

            img_lbl = Label(frame, image=blank, bg=_BG_CELL,
                            bd=0, width=tw, height=th)
            img_lbl.pack(fill=BOTH, expand=True)

            name = os.path.basename(fpath)
            if len(name) > 20:
                name = name[:18] + "…"
            fn_lbl = Label(frame, text=name, bg=_BG_FNAME,
                           fg="#9090bb", font=("Consolas", 7), anchor=W, padx=2)
            fn_lbl.pack(fill=X)

            for w in (frame, img_lbl, fn_lbl):
                w.bind("<Button-1>", lambda _e, p=fpath: self._on_select(p))

            self._cells.append({
                "path": fpath, "frame": frame,
                "img_lbl": img_lbl, "rendered": False
            })

        for c in range(nc):
            self._inner.columnconfigure(c, weight=1)
        for r in range(nr):
            self._inner.rowconfigure(r, weight=1)

        self._render_idx = 0
        self._schedule_film_render()

    # ── Render helpers ─────────────────────────────────────────────────────────

    def _refresh_highlights(self):
        for cell in self._cells:
            is_cur = (cell["path"] == self._current_path)
            try:
                cell["frame"].config(bg=ACCENT if is_cur else "#2a2a3e")
            except Exception:
                pass

    def _re_render_cell(self, path: str):
        for cell in self._cells:
            if cell["path"] != path:
                continue
            tk_img = self._get_tk_img(path)
            if tk_img is not None:
                try:
                    cell["img_lbl"].config(image=tk_img, width=0, height=0)
                    cell["img_lbl"]._tk_img = tk_img
                    cell["rendered"] = True
                except Exception:
                    pass
            break

    def _schedule_film_render(self):
        BATCH = 8
        end = min(self._render_idx + BATCH, len(self._cells))
        for cell in self._cells[self._render_idx:end]:
            if not cell["rendered"]:
                tk_img = self._get_tk_img(cell["path"])
                if tk_img is not None:
                    try:
                        cell["img_lbl"].config(image=tk_img, width=0, height=0)
                        cell["img_lbl"]._tk_img = tk_img
                    except Exception:
                        pass
                cell["rendered"] = True
        self._render_idx = end
        if end < len(self._cells):
            self.after(40, self._schedule_film_render)

    def _get_tk_img(self, path: str):
        if not _PIL_OK:
            return None
        key = (path, self._thumb_w, self._thumb_h)
        if key in self._tk_cache:
            return self._tk_cache[key]
        if key not in self._pil_cache:
            pil = self._get_thumb(path, self._thumb_w, self._thumb_h)
            if pil is None:
                return None
            self._pil_cache[key] = pil
        try:
            tk_img = ImageTk.PhotoImage(self._pil_cache[key])
            self._tk_cache[key] = tk_img
            return tk_img
        except Exception:
            return None

    def _invalidate(self, path: str):
        for k in [k for k in self._pil_cache if k[0] == path]:
            del self._pil_cache[k]
        for k in [k for k in self._tk_cache if k[0] == path]:
            del self._tk_cache[k]

    def _make_blank(self):
        if self._blank_tk is not None:
            return self._blank_tk
        if not _PIL_OK:
            return None
        tw = self._thumb_w or 80
        th = self._thumb_h or 60
        self._blank_tk = ImageTk.PhotoImage(Image.new("RGB", (tw, th), _BG_CELL))
        return self._blank_tk
