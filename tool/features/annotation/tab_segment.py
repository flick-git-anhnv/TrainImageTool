# tab_segment.py — YOLO Segmentation Annotation (N-point polygon + SAM auto)
from __future__ import annotations
import threading
from pathlib import Path
from tkinter import *
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk, ImageDraw

from ...core.constants import (BG, CARD, ACCENT, ACCENT2, TEXT, DIM,
                                F_MAIN, F_BOLD, IMAGE_EXTENSIONS, CLASS_NAMES)
from ...core.settings import _bind_cfg, _cfg_save
from ...shared.canvas_zoom import CanvasZoomMixin
from ...shared.sam_utils import run_sam_points, run_sam_box, simplify as _simplify

_COLORS = ["#F05922", "#4A9FE0", "#4CAF50", "#E040FB",
           "#FFEB3B", "#00BCD4", "#FF5252", "#69F0AE"]


class SegmentTab(Frame, CanvasZoomMixin):

    def __init__(self, parent, root):
        super().__init__(parent, bg=BG)
        self.root = root
        self._zoom_init()

        self._img_dir     = StringVar()
        self._img_files: list[Path] = []
        self._img_idx     = 0
        self._pil_img: Image.Image | None = None
        self._tk_img = None; self._render_base = None
        self._segments: list       = []
        self._drawing: list[tuple] = []
        self._cursor: tuple | None = None
        self._sel: int             = -1
        self._drag: tuple | None   = None
        self._class_var    = StringVar(value="0")
        self._mode_var     = StringVar(value="draw")
        self._status_var   = StringVar(value="Chọn thư mục ảnh để bắt đầu")
        self._simplify_var = IntVar(value=2)
        self._sam_model    = None
        self._sam_running  = False
        self._box_start: tuple | None = None
        self._box_end:   tuple | None = None
        self._sam_pts: list           = []   # [(ix,iy,label)] iterative prompts
        self._sam_preview: list | None = None  # polygon preview chưa confirm

        _bind_cfg("seg.img_dir", self._img_dir)
        self._build()
        self._bind_shortcuts()

        d = self._img_dir.get()
        if d and Path(d).is_dir():
            self._load_dir(d)

    def _build(self):
        self._build_toolbar()
        self._build_sam_bar()
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

        for txt, val in [("✏ Vẽ","draw"),("↔ Sửa","edit"),("🪄 SAM","sam"),("⬜ SAM Box","sam_box")]:
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

    def _build_sam_bar(self):
        sb = Frame(self, bg="#1a1a2e", pady=3)
        sb.pack(fill=X)
        Label(sb, text="🪄 SAM:", bg="#1a1a2e", fg=ACCENT, font=F_BOLD).pack(side=LEFT, padx=(8, 4))
        Button(sb, text="📥 mobile_sam  ~40MB", bg=ACCENT2, fg="white", relief=FLAT,
               font=F_MAIN, padx=6,
               command=lambda: self._load_sam_name("mobile_sam.pt")).pack(side=LEFT, padx=2)
        Button(sb, text="📥 sam_b  ~375MB", bg=CARD, fg=TEXT, relief=FLAT,
               font=F_MAIN, padx=6,
               command=lambda: self._load_sam_name("sam_b.pt")).pack(side=LEFT, padx=2)
        Button(sb, text="📂 File .pt có sẵn", bg=CARD, fg=TEXT, relief=FLAT,
               font=F_MAIN, padx=6,
               command=self._load_sam).pack(side=LEFT, padx=2)
        self._sam_lbl = Label(sb, text="Chưa load  —  chọn model rồi click 🪄 SAM vào object",
                              bg="#1a1a2e", fg=DIM, font=F_MAIN)
        self._sam_lbl.pack(side=LEFT, padx=8)
        Label(sb, text="Simplify:", bg="#1a1a2e", fg=DIM, font=F_MAIN).pack(side=RIGHT, padx=(0,2))
        Scale(sb, variable=self._simplify_var, from_=0, to=10, orient=HORIZONTAL,
              length=100, bg="#1a1a2e", fg=TEXT, troughcolor=CARD, highlightthickness=0,
              showvalue=True, relief=FLAT).pack(side=RIGHT, padx=(0,8))

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
        cv.bind("<Shift-Button-1>",  self._on_shift_click)
        cv.bind("<Button-3>",        self._on_right_click)
        cv.bind("<Double-Button-1>", lambda e: self._close_poly())
        cv.bind("<Motion>",          self._on_move)
        cv.bind("<B1-Motion>",       self._on_drag)
        cv.bind("<ButtonRelease-1>", self._on_release)
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


    def _browse_dir(self):
        d = filedialog.askdirectory(initialdir=self._img_dir.get() or ".")
        if d: self._img_dir.set(d); _cfg_save(); self._load_dir(d)

    def _load_dir(self, d: str):
        self._img_files = sorted(p for p in Path(d).iterdir()
                                 if p.suffix.lower() in IMAGE_EXTENSIONS)
        self._img_lb.delete(0, END)
        for p in self._img_files: self._img_lb.insert(END, p.name)
        if self._img_files: self._load_img(0)

    def _load_img(self, idx: int):
        if not self._img_files: return
        idx = max(0, min(idx, len(self._img_files) - 1))
        self._img_idx = idx
        self._img_lb.selection_clear(0, END)
        self._img_lb.selection_set(idx); self._img_lb.see(idx)
        self._nav_lbl.config(text=f"{idx + 1} / {len(self._img_files)}")
        try:
            self._pil_img = Image.open(self._img_files[idx]).convert("RGB")
        except Exception as e:
            self._status_var.set(f"Lỗi load ảnh: {e}"); return
        self._render_base = None
        self._drawing.clear(); self._cursor = None; self._sel = -1; self._drag = None
        self._zoom_reset(); self._load_labels(); self._refresh_segs()
        iw, ih = self._pil_img.size
        self._status_var.set(f"{self._img_files[idx].name}  ({iw}×{ih})  —  {len(self._segments)} segment")

    def _on_list_sel(self, _):
        sel = self._img_lb.curselection()
        if sel: self._load_img(sel[0])

    def _prev_img(self):
        if self._img_files: self._save(); self._load_img(self._img_idx - 1)

    def _next_img(self):
        if self._img_files: self._save(); self._load_img(self._img_idx + 1)

    def _lbl_path(self) -> Path | None:
        return self._img_files[self._img_idx].with_suffix(".txt") if self._img_files else None

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

    def _c2i(self, cx: float, cy: float) -> tuple[float, float]:
        s = self._scale or 1.0
        return (cx - self._off_x) / s, (cy - self._off_y) / s

    def _i2c(self, ix: float, iy: float) -> tuple[float, float]:
        return ix * self._scale + self._off_x, iy * self._scale + self._off_y

    def _on_click(self, e):
        if self._pil_img is None:
            return
        mode = self._mode_var.get()
        if mode in ("sam", "sam_box"):
            if mode == "sam":
                self._handle_sam_click(e)
            else:
                self._box_start = self._c2i(e.x, e.y)
                self._box_end = None
            return
        if mode == "draw":
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

    def _on_release(self, e):
        self._drag = None
        if self._mode_var.get() == "sam_box" and self._box_start and self._box_end:
            x1, y1 = self._box_start; x2, y2 = self._box_end
            if abs(x2-x1) > 5 and abs(y2-y1) > 5:
                self._fire_sam(box=(min(x1,x2), min(y1,y2), max(x1,x2), max(y1,y2)))
        self._box_start = self._box_end = None
        self._render()

    def _on_drag(self, e):
        mode = self._mode_var.get()
        if mode == "sam_box" and self._box_start:
            self._box_end = self._c2i(e.x, e.y)
            self._render()
            return
        if self._drag is None or mode != "edit":
            return
        si, vi = self._drag[0], self._drag[1]
        iw, ih = self._pil_img.size
        ix, iy = self._c2i(e.x, e.y)
        self._segments[si][1][vi] = (max(0.0, min(float(iw), ix)),
                                     max(0.0, min(float(ih), iy)))
        self._drag = (si, vi, e.x, e.y)
        self._render()

    def _on_shift_click(self, e):
        if self._mode_var.get() == "sam":
            self._add_sam_pt(e, label=0)  # negative prompt

    def _on_right_click(self, e):
        mode = self._mode_var.get()
        if mode == "sam" and self._sam_preview:
            self._confirm_sam_preview()
        else:
            self._close_poly()

    def _add_sam_pt(self, e, label: int = 1):
        if self._pil_img is None: return
        ix, iy = self._c2i(e.x, e.y)
        iw, ih = self._pil_img.size
        if not (0 <= ix <= iw and 0 <= iy <= ih): return
        self._sam_pts.append((ix, iy, label))
        self._fire_sam(points=self._sam_pts)

    def _confirm_sam_preview(self):
        if not self._sam_preview: return
        self._segments.append([self._get_cid(), self._sam_preview])
        self._sam_preview = None; self._sam_pts.clear()
        self._sel = len(self._segments) - 1
        self._refresh_segs(); self._render()
        self._status_var.set(f"Đã thêm segment — {len(self._segments)} tổng")

    def _close_poly(self):
        if len(self._drawing) >= 3:
            cid = self._get_cid()
            self._segments.append([cid, list(self._drawing)])
            self._sel = len(self._segments) - 1
            self._refresh_segs()
        self._drawing.clear(); self._cursor = None; self._render()

    def _get_cid(self) -> int:
        try:
            return int(self._class_var.get().split(":")[0])
        except Exception:
            return 0

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

        # SAM Box drag preview
        if self._box_start and self._box_end:
            bx1,by1 = self._box_start[0]*sc, self._box_start[1]*sc
            bx2,by2 = self._box_end[0]*sc,   self._box_end[1]*sc
            dr.rectangle([bx1,by1,bx2,by2], outline=(255,220,0,220), width=2)

        # SAM Click preview mask (vàng nhạt, chờ xác nhận)
        if self._sam_preview:
            pv = _dp(self._sam_preview)
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
            self._segments.pop(self._sel)
            self._sel = min(self._sel, len(self._segments) - 1)
            self._refresh_segs()
            self._render()

    def _undo_pt(self):
        if self._sam_pts:
            self._sam_pts.pop()
            if self._sam_pts: self._fire_sam(points=self._sam_pts)
            else: self._sam_preview = None; self._render()
        elif self._drawing: self._drawing.pop(); self._render()

    def _cancel(self):
        self._drawing.clear(); self._cursor = None
        self._sam_pts.clear(); self._sam_preview = None
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
            self.root.after(0, lambda: self._sam_lbl.config(
                text=f"Lỗi: {ex}", fg="#f44336"))

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
            self.root.after(0, lambda: self._after_sam(None, is_box, str(ex)))

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
            self._sam_preview = pts
            n_pos = sum(1 for *_, l in self._sam_pts if l == 1)
            n_neg = sum(1 for *_, l in self._sam_pts if l == 0)
            self._render()
            self._status_var.set(
                f"Preview: {len(pts)} điểm  |  ✅{n_pos} ❌{n_neg}  |  "
                "Click thêm để chỉnh  |  Shift+Click loại vùng  |  Chuột phải = xác nhận")

    def _is_active(self) -> bool:
        """Trả về True nếu tab Segment đang visible (đang được chọn)."""
        try:
            return self.winfo_ismapped()
        except Exception:
            return False

    def _bind_shortcuts(self):
        self.root.bind_all("<Control-o>", lambda e: self._browse_dir() if self._is_active() else None)
        self.root.bind_all("<Control-s>", lambda e: self._save() if self._is_active() else None)
        self.root.bind_all("<Control-z>", lambda e: self._undo_pt() if self._is_active() else None)
        self.root.bind_all("<Delete>",    lambda e: self._delete_seg() if self._is_active() else None)
        self.root.bind_all("<Escape>",    lambda e: self._cancel() if self._is_active() else None)
        self.root.bind_all("<Left>",      lambda e: (self._save(), self._prev_img()) if self._is_active() else None)
        self.root.bind_all("<Right>",     lambda e: (self._save(), self._next_img()) if self._is_active() else None)
