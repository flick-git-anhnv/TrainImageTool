# tab_segment.py — YOLO Segmentation Annotation (N-point polygon)
from __future__ import annotations
from pathlib import Path
from tkinter import *
from tkinter import ttk, filedialog
from PIL import Image, ImageTk, ImageDraw

from ...core.constants import (BG, CARD, ACCENT, ACCENT2, TEXT, DIM,
                                F_MAIN, F_BOLD, IMAGE_EXTENSIONS, CLASS_NAMES)
from ...core.settings import _bind_cfg, _cfg_save
from ...shared.canvas_zoom import CanvasZoomMixin

_COLORS = ["#F05922", "#4A9FE0", "#4CAF50", "#E040FB",
           "#FFEB3B", "#00BCD4", "#FF5252", "#69F0AE"]


class SegmentTab(Frame, CanvasZoomMixin):

    def __init__(self, parent, root):
        super().__init__(parent, bg=BG)
        self.root = root
        self._zoom_init()

        # ── State ──────────────────────────────────────────────────────────
        self._img_dir     = StringVar()
        self._img_files: list[Path] = []
        self._img_idx     = 0
        self._pil_img: Image.Image | None = None
        self._tk_img      = None
        self._render_base = None          # cached resized PIL (RGBA)

        self._segments: list          = []   # [[cid, [(px,py),...]], ...]
        self._drawing: list[tuple]    = []   # [(px,py)] polygon đang vẽ
        self._cursor: tuple | None    = None # vị trí chuột preview
        self._sel: int                = -1   # segment đang chọn
        self._drag: tuple | None      = None # (si, vi, ex, ey)

        self._class_var  = StringVar(value="0")
        self._mode_var   = StringVar(value="draw")  # "draw" | "edit"
        self._status_var = StringVar(value="Chọn thư mục ảnh để bắt đầu")

        _bind_cfg("seg.img_dir", self._img_dir)
        self._build()
        self._bind_shortcuts()

        d = self._img_dir.get()
        if d and Path(d).is_dir():
            self._load_dir(d)

    # ── Build UI ───────────────────────────────────────────────────────────

    def _build(self):
        self._build_toolbar()
        body = Frame(self, bg=BG)
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

        Label(tb, text="Class:", bg=CARD, fg=TEXT,
              font=F_MAIN).pack(side=LEFT, padx=(8, 2))
        vals = [f"{k}: {v}" for k, v in CLASS_NAMES.items()]
        self._cls_cb = ttk.Combobox(tb, textvariable=self._class_var,
                                    values=vals, width=14,
                                    state="readonly", font=F_MAIN)
        self._cls_cb.pack(side=LEFT, padx=2)
        if vals:
            self._cls_cb.set(vals[0])

        for txt, val in [("✏ Vẽ", "draw"), ("↔ Sửa", "edit")]:
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

    def _build_left(self, parent):
        f = Frame(parent, bg=CARD, width=180)
        f.pack(side=LEFT, fill=Y, padx=(4, 0), pady=4)
        f.pack_propagate(False)
        Label(f, text="Danh sách ảnh", bg=CARD, fg=TEXT,
              font=F_BOLD).pack(pady=(4, 2))
        sb = Scrollbar(f)
        sb.pack(side=RIGHT, fill=Y)
        self._img_lb = Listbox(f, bg=BG, fg=TEXT, selectbackground=ACCENT2,
                               font=F_MAIN, yscrollcommand=sb.set, bd=0)
        self._img_lb.pack(fill=BOTH, expand=True, padx=2)
        sb.config(command=self._img_lb.yview)
        self._img_lb.bind("<<ListboxSelect>>", self._on_list_sel)

    def _build_canvas(self, parent):
        self._canvas = Canvas(parent, bg="#0d0d1a", cursor="crosshair",
                              highlightthickness=0)
        self._canvas.pack(side=LEFT, fill=BOTH, expand=True, padx=4, pady=4)
        cv = self._canvas
        cv.bind("<Button-1>",        self._on_click)
        cv.bind("<Button-3>",        lambda e: self._close_poly())
        cv.bind("<Double-Button-1>", lambda e: self._close_poly())
        cv.bind("<Motion>",          self._on_move)
        cv.bind("<B1-Motion>",       self._on_drag)
        cv.bind("<ButtonRelease-1>", lambda e: setattr(self, "_drag", None))
        cv.bind("<MouseWheel>",      self._on_zoom_wheel)
        cv.bind("<Button-2>",        self._on_pan_start)
        cv.bind("<B2-Motion>",       self._on_pan_drag)
        cv.bind("<ButtonRelease-2>", self._on_pan_end)
        cv.bind("<Configure>",       lambda e: self._render())

    def _build_right(self, parent):
        f = Frame(parent, bg=CARD, width=180)
        f.pack(side=RIGHT, fill=Y, padx=(0, 4), pady=4)
        f.pack_propagate(False)
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
                         ("✖ Hủy vẽ  Esc",          self._cancel)]:
            Button(f, text=txt, bg=CARD, fg=TEXT, relief=FLAT,
                   font=F_MAIN, command=cmd, anchor="w",
                   padx=6).pack(pady=2, padx=4, fill=X)

        Label(f, text="─" * 22, bg=CARD, fg=DIM).pack(pady=(4, 0))
        Label(f, text="Hướng dẫn:", bg=CARD, fg=DIM, font=F_MAIN).pack(anchor="w", padx=6)
        tips = ("• Click: thêm điểm\n"
                "• Click điểm đầu /\n  Chuột phải /\n  Double-click: đóng\n"
                "• Ctrl+Z: xóa điểm cuối\n"
                "• Tab Sửa: kéo vertex\n"
                "• Scroll: zoom\n"
                "• Giữ chuột giữa: pan")
        Label(f, text=tips, bg=CARD, fg=DIM, font=("Segoe UI", 8),
              justify="left").pack(anchor="w", padx=6, pady=(2, 4))

    # ── Directory / Image ──────────────────────────────────────────────────

    def _browse_dir(self):
        d = filedialog.askdirectory(initialdir=self._img_dir.get() or ".")
        if d:
            self._img_dir.set(d)
            _cfg_save()
            self._load_dir(d)

    def _load_dir(self, d: str):
        files = sorted(p for p in Path(d).iterdir()
                       if p.suffix.lower() in IMAGE_EXTENSIONS)
        self._img_files = files
        self._img_lb.delete(0, END)
        for p in files:
            self._img_lb.insert(END, p.name)
        if files:
            self._load_img(0)

    def _load_img(self, idx: int):
        if not self._img_files:
            return
        idx = max(0, min(idx, len(self._img_files) - 1))
        self._img_idx = idx
        self._img_lb.selection_clear(0, END)
        self._img_lb.selection_set(idx)
        self._img_lb.see(idx)
        self._nav_lbl.config(text=f"{idx + 1} / {len(self._img_files)}")
        try:
            self._pil_img = Image.open(self._img_files[idx]).convert("RGB")
        except Exception as e:
            self._status_var.set(f"Lỗi load ảnh: {e}")
            return
        self._render_base = None
        self._drawing.clear()
        self._cursor = None
        self._sel = -1
        self._drag = None
        self._zoom_reset()          # gọi _render() bên trong
        self._load_labels()
        self._refresh_segs()
        p = self._img_files[idx]
        iw, ih = self._pil_img.size
        self._status_var.set(f"{p.name}  ({iw}×{ih})  —  {len(self._segments)} segment")

    def _on_list_sel(self, _):
        sel = self._img_lb.curselection()
        if sel:
            self._load_img(sel[0])

    def _prev_img(self):
        if self._img_files:
            self._save()
            self._load_img(self._img_idx - 1)

    def _next_img(self):
        if self._img_files:
            self._save()
            self._load_img(self._img_idx + 1)

    # ── Label IO ───────────────────────────────────────────────────────────

    def _lbl_path(self) -> Path | None:
        if not self._img_files:
            return None
        return self._img_files[self._img_idx].with_suffix(".txt")

    def _load_labels(self):
        self._segments = []
        lp = self._lbl_path()
        if not lp or not lp.exists():
            return
        iw, ih = self._pil_img.size
        for line in lp.read_text(encoding="utf-8").splitlines():
            parts = line.strip().split()
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

    # ── Canvas helpers ─────────────────────────────────────────────────────

    def _c2i(self, cx: float, cy: float) -> tuple[float, float]:
        """Canvas coords → image pixel coords."""
        s = self._scale or 1.0
        return (cx - self._off_x) / s, (cy - self._off_y) / s

    def _i2c(self, ix: float, iy: float) -> tuple[float, float]:
        """Image pixel → canvas coords."""
        return ix * self._scale + self._off_x, iy * self._scale + self._off_y

    # ── Canvas events ──────────────────────────────────────────────────────

    def _on_click(self, e):
        if self._pil_img is None:
            return
        if self._mode_var.get() == "draw":
            ix, iy = self._c2i(e.x, e.y)
            if len(self._drawing) >= 3:
                fx, fy = self._i2c(*self._drawing[0])
                if abs(e.x - fx) < 10 and abs(e.y - fy) < 10:
                    self._close_poly()
                    return
            self._drawing.append((ix, iy))
            self._render()
        else:
            best_s, best_v, best_d = -1, -1, 12.0
            for si, (_, pts) in enumerate(self._segments):
                for vi, pt in enumerate(pts):
                    cx, cy = self._i2c(*pt)
                    d = ((e.x - cx) ** 2 + (e.y - cy) ** 2) ** 0.5
                    if d < best_d:
                        best_d, best_s, best_v = d, si, vi
            if best_s >= 0:
                self._sel = best_s
                self._drag = (best_s, best_v, e.x, e.y)
                self._refresh_segs()
                self._render()

    def _on_move(self, e):
        if self._drawing and self._mode_var.get() == "draw":
            self._cursor = self._c2i(e.x, e.y)
            self._render()

    def _on_drag(self, e):
        if self._drag is None or self._mode_var.get() != "edit":
            return
        si, vi = self._drag[0], self._drag[1]
        iw, ih = self._pil_img.size
        ix, iy = self._c2i(e.x, e.y)
        self._segments[si][1][vi] = (max(0.0, min(float(iw), ix)),
                                     max(0.0, min(float(ih), iy)))
        self._drag = (si, vi, e.x, e.y)
        self._render()

    def _close_poly(self):
        if len(self._drawing) >= 3:
            cid = self._get_cid()
            self._segments.append([cid, list(self._drawing)])
            self._sel = len(self._segments) - 1
            self._refresh_segs()
        self._drawing.clear()
        self._cursor = None
        self._render()

    def _get_cid(self) -> int:
        try:
            return int(self._class_var.get().split(":")[0])
        except Exception:
            return 0

    # ── Render ─────────────────────────────────────────────────────────────

    def _render(self, resample=None):
        if self._pil_img is None:
            return
        sc, nw, nh, ox, oy = self._calc_zoom_offsets()
        if self._render_base is None or self._render_nw_nh != (nw, nh):
            self._render_base = self._pil_img.resize(
                (nw, nh), Image.LANCZOS).convert("RGBA")
            self._render_nw_nh = (nw, nh)

        overlay = Image.new("RGBA", (nw, nh), (0, 0, 0, 0))
        dr = ImageDraw.Draw(overlay)

        def _dp(pts):
            return [(x * sc, y * sc) for x, y in pts]

        # Completed segments
        for si, (cid, pts) in enumerate(self._segments):
            col = _COLORS[cid % len(_COLORS)]
            r, g, b = int(col[1:3], 16), int(col[3:5], 16), int(col[5:7], 16)
            dp = _dp(pts)
            if len(dp) >= 3:
                alpha = 110 if si == self._sel else 55
                dr.polygon(dp, fill=(r, g, b, alpha), outline=(r, g, b, 230))
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

        result = Image.alpha_composite(self._render_base, overlay)
        self._tk_img = ImageTk.PhotoImage(result)
        self._canvas.delete("all")
        self._canvas.create_image(ox, oy, anchor="nw", image=self._tk_img)

    # ── Segment list ───────────────────────────────────────────────────────

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
            self._segments.pop(self._sel)
            self._sel = min(self._sel, len(self._segments) - 1)
            self._refresh_segs()
            self._render()

    def _undo_pt(self):
        if self._drawing:
            self._drawing.pop()
            self._render()

    def _cancel(self):
        self._drawing.clear()
        self._cursor = None
        self._render()

    # ── Shortcuts ──────────────────────────────────────────────────────────

    def _bind_shortcuts(self):
        self.root.bind_all("<Control-o>", lambda e: self._browse_dir())
        self.root.bind_all("<Control-s>", lambda e: self._save())
        self.root.bind_all("<Control-z>", lambda e: self._undo_pt())
        self.root.bind_all("<Delete>",    lambda e: self._delete_seg())
        self.root.bind_all("<Escape>",    lambda e: self._cancel())
        self.root.bind_all("<Left>",      lambda e: (self._save(), self._prev_img()))
        self.root.bind_all("<Right>",     lambda e: (self._save(), self._next_img()))
