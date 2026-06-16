# tab_slot_classifier.py — Parking Slot Classifier (trống / có xe)
# Supports: ultralytics YOLO v8, YOLOv5 (hub + raw), drag-drop, bbox resize/move
import os
import threading
from tkinter import *
from tkinter import filedialog, ttk

from ...core.constants import (BG, CARD, ACCENT, ACCENT2, TEXT, DIM, SUCCESS,
                               F_MAIN, F_BOLD, F_MONO, IMAGE_EXTENSIONS)
from ...core.settings import (_bind_cfg, _cfg_dir, _CFG, _cfg_save,
                               _bind_history, _push_history)

try:
    from PIL import Image, ImageTk
    _PIL_OK = True
except ImportError:
    _PIL_OK = False

try:
    from ultralytics import YOLO as _YOLO8
    _YOLO8_OK = True
except ImportError:
    _YOLO8_OK = False

try:
    import torch as _torch
    _TORCH_OK = True
except ImportError:
    _TORCH_OK = False

try:
    from tkinterdnd2 import DND_FILES
    _DND_OK = True
except ImportError:
    _DND_OK = False

_COLOR_EMPTY    = "#4caf50"
_COLOR_OCCUPIED = "#f44336"
_COLOR_UNKNOWN  = ACCENT
_HS = 5   # handle half-size in canvas pixels (square corners)

_EMPTY_KEYWORDS    = {"empty","trong","trống","free","available","no_car","no car","0","class0","vacant"}
_OCCUPIED_KEYWORDS = {"occupied","car","vehicle","xe","co_xe","co xe","có xe","full","1","class1","taken"}

_CURSOR_DRAW   = "crosshair"
_CURSOR_MOVE   = "fleur"
_CURSOR_RESIZE = "sizing"


class SlotClassifierTab(Frame):
    """Tab phân loại ô đỗ xe: load ảnh → vẽ/di chuyển/resize bbox → detect.pt → TRỐNG / CÓ XE."""

    def __init__(self, master, root):
        super().__init__(master, bg=BG)
        self.root = root

        # ── Model state ──────────────────────────────────────────────────
        self._model       = None
        self._model_task  = "detect"   # "yolo8/detect","yolo8/classify","yolo5_hub","yolo5_raw","torch_cls"
        self._model_names = {}

        # ── Image state ──────────────────────────────────────────────────
        self._pil_img      = None
        self._tk_img       = None
        self._img_scale    = 1.0
        self._img_off_x    = 0
        self._img_off_y    = 0

        # ── Bbox state (image pixel coords, always x1<x2, y1<y2) ────────
        self._bx1 = self._by1 = self._bx2 = self._by2 = None
        self._rect_id    = None
        self._handle_ids = []
        self._result_color = ACCENT

        # ── Interaction state ────────────────────────────────────────────
        self._mode        = "draw"   # "draw" | "move" | "resize_XX"
        self._drag_cx     = 0        # canvas x,y at drag start
        self._drag_cy     = 0
        self._drag_bx1 = self._drag_by1 = self._drag_bx2 = self._drag_by2 = 0
        self._draw_start  = None     # (ix,iy) in image coords

        self._crop_pil    = None

        # ── Vars ─────────────────────────────────────────────────────────
        self.v_model_path = StringVar()
        self.v_image_path = StringVar()
        self.v_conf       = DoubleVar(value=0.25)
        _bind_cfg("slot_cls.conf", self.v_conf)

        self._build()
        self.after(200, self._auto_load_model)

    # ═══════════════════════════════════════════════════════════ BUILD ══

    def _build(self):
        self._build_toolbar()
        self._build_body()

    def _build_toolbar(self):
        bar = Frame(self, bg=CARD, padx=10, pady=7)
        bar.pack(fill=X)

        # Row 1: model
        r1 = Frame(bar, bg=CARD)
        r1.pack(fill=X, pady=(0, 3))

        Label(r1, text="Model:", bg=CARD, fg=TEXT,
              font=F_BOLD, width=7, anchor=W).pack(side=LEFT)

        self.cmb_model = ttk.Combobox(r1, textvariable=self.v_model_path,
                                      font=F_MAIN, style="Dark.TCombobox")
        self.cmb_model.pack(side=LEFT, padx=(0, 5), fill=X, expand=True)
        _bind_history("history.slot_cls.model_path", self.cmb_model)

        Button(r1, text="Chọn Model", command=self._select_model,
               bg=ACCENT2, fg="white", font=F_MAIN, relief="flat",
               padx=8, cursor="hand2",
               activebackground=ACCENT, activeforeground="white"
               ).pack(side=LEFT, padx=(0, 8))

        self.lbl_status = Label(r1, text="Chưa tải model",
                                font=("Segoe UI", 9, "italic"),
                                bg=CARD, fg=DIM, anchor=W)
        self.lbl_status.pack(side=LEFT, fill=X, expand=True)

        # Row 2: image + conf
        r2 = Frame(bar, bg=CARD)
        r2.pack(fill=X)

        Label(r2, text="Ảnh:", bg=CARD, fg=TEXT,
              font=F_BOLD, width=7, anchor=W).pack(side=LEFT)

        self.cmb_image = ttk.Combobox(r2, textvariable=self.v_image_path,
                                      font=F_MAIN, style="Dark.TCombobox")
        self.cmb_image.pack(side=LEFT, padx=(0, 5), fill=X, expand=True)
        _bind_history("history.slot_cls.image_path", self.cmb_image)

        Button(r2, text="Chọn Ảnh (Ctrl+O)", command=self._select_image,
               bg=ACCENT2, fg="white", font=F_MAIN, relief="flat",
               padx=8, cursor="hand2",
               activebackground=ACCENT, activeforeground="white"
               ).pack(side=LEFT, padx=(0, 12))

        Label(r2, text="Conf:", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        self._lbl_conf = Label(r2, text="0.25", bg=CARD, fg=TEXT,
                               font=F_MONO, width=4)
        self._lbl_conf.pack(side=LEFT, padx=(3, 0))
        Scale(r2, from_=0.05, to=0.95, resolution=0.05,
              variable=self.v_conf, orient=HORIZONTAL, length=100,
              bg=CARD, fg=TEXT, activebackground=ACCENT,
              highlightthickness=0, showvalue=False, troughcolor=BG,
              command=lambda v: self._lbl_conf.config(text=f"{float(v):.2f}")
              ).pack(side=LEFT)

    def _build_body(self):
        body = Frame(self, bg=BG)
        body.pack(fill=BOTH, expand=True)

        # ── Left: canvas ─────────────────────────────────────────────────
        left = Frame(body, bg=BG)
        left.pack(side=LEFT, fill=BOTH, expand=True, padx=(6, 3), pady=6)

        self._hint = Label(left,
            text="Kéo chuột vẽ bbox  |  Di chuyển/resize bbox bằng handle  |  "
                 "Chuột phải: xóa  |  Kéo thả ảnh vào đây",
            bg=BG, fg=DIM, font=("Segoe UI", 9))
        self._hint.pack(anchor=W, pady=(0, 3))

        self.canvas = Canvas(left, bg="#0d0d1a", cursor=_CURSOR_DRAW,
                             highlightthickness=1, highlightbackground=ACCENT2)
        self.canvas.pack(fill=BOTH, expand=True)

        self.canvas.bind("<ButtonPress-1>",  self._on_press)
        self.canvas.bind("<B1-Motion>",       self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Button-3>",        self._clear_box)
        self.canvas.bind("<Double-Button-1>", self._zoom_full_image)
        self.canvas.bind("<Motion>",          self._on_motion)
        self.canvas.bind("<Configure>",       self._on_canvas_resize)

        # DND support
        if _DND_OK:
            try:
                self.canvas.drop_target_register(DND_FILES)
                self.canvas.dnd_bind("<<Drop>>", self._on_dnd_drop)
            except Exception:
                pass

        # ── Right: result panel ───────────────────────────────────────────
        right = Frame(body, bg=CARD, width=290)
        right.pack(side=RIGHT, fill=Y, padx=(3, 6), pady=6)
        right.pack_propagate(False)

        # ── Detect button (FIRST — always visible) ────────────────────────
        Label(right, text="KẾT QUẢ PHÂN LOẠI", bg=CARD, fg=TEXT,
              font=F_BOLD).pack(pady=(12, 8))

        Button(right, text="⚡   PHÂN LOẠI   (F5)",
               command=self._run,
               bg=ACCENT, fg="white", font=("Segoe UI Semibold", 12),
               relief="flat", pady=8, cursor="hand2",
               activebackground="#d04010", activeforeground="white"
               ).pack(fill=X, padx=14, pady=(0, 10))

        # ── Preview canvas (pixel-based, 240×150) ─────────────────────────
        self.prev_canvas = Canvas(right, bg="#0d0d1a",
                                  width=240, height=150,
                                  highlightthickness=1,
                                  highlightbackground=ACCENT2)
        self.prev_canvas.pack(padx=14, pady=(0, 6))
        self._prev_hint_id = self.prev_canvas.create_text(
            120, 75, text="Vùng cắt hiện ở đây",
            fill=DIM, font=("Segoe UI", 9))
        self._prev_img_id  = None
        self._prev_tk_img  = None
        self.prev_canvas.bind("<Double-Button-1>", self._zoom_crop)

        # ── Result label ──────────────────────────────────────────────────
        self.lbl_result = Label(right, text="—", bg=CARD, fg=DIM,
                                font=("Segoe UI", 24, "bold"))
        self.lbl_result.pack(pady=(4, 0))

        self.lbl_conf_disp = Label(right, text="", bg=CARD, fg=DIM,
                                   font=("Segoe UI", 11))
        self.lbl_conf_disp.pack()

        self.lbl_detail = Label(right, text="", bg=CARD, fg=DIM,
                                font=F_MONO, wraplength=255, justify=LEFT)
        self.lbl_detail.pack(padx=12, pady=(4, 0))

        # ── Controls ──────────────────────────────────────────────────────
        Frame(right, bg=DIM, height=1).pack(fill=X, padx=14, pady=10)

        Button(right, text="🗑  Xóa vùng chọn  (Esc)",
               command=self._clear_box,
               bg=ACCENT2, fg="white", font=F_MAIN,
               relief="flat", pady=4, cursor="hand2",
               activebackground=ACCENT, activeforeground="white"
               ).pack(fill=X, padx=14)

        Label(right, text="Tọa độ (pixel):", bg=CARD, fg=DIM,
              font=("Segoe UI", 9)).pack(anchor=W, padx=14, pady=(8, 0))
        self.lbl_coords = Label(right, text="—", bg=CARD, fg=TEXT, font=F_MONO)
        self.lbl_coords.pack(anchor=W, padx=14)

        # ── Log ───────────────────────────────────────────────────────────
        Frame(right, bg=DIM, height=1).pack(fill=X, padx=14, pady=(10, 6))

        log_frame = Frame(right, bg=BG)
        log_frame.pack(fill=BOTH, expand=True, padx=(14, 0), pady=(0, 8))

        self._log = Text(log_frame, bg="#0d0d1a", fg=TEXT, font=F_MONO,
                         wrap=WORD, state=DISABLED, relief="flat",
                         selectbackground=ACCENT2)
        _sb = ttk.Scrollbar(log_frame, command=self._log.yview)
        self._log.configure(yscrollcommand=_sb.set)
        _sb.pack(side=RIGHT, fill=Y)
        self._log.pack(side=LEFT, fill=BOTH, expand=True)

    # ═══════════════════════════════════════════════════════════ MODEL ══

    def _select_model(self):
        hist = _CFG.get("history.slot_cls.model_path", [])
        init = os.path.dirname(hist[0]) if hist else "models"
        path = filedialog.askopenfilename(
            title="Chọn model (.pt)",
            filetypes=[("PyTorch model", "*.pt"), ("Tất cả", "*.*")],
            initialdir=init if os.path.isdir(init) else "."
        )
        if not path:
            return
        self.v_model_path.set(path)
        _push_history("history.slot_cls.model_path", path)
        self.cmb_model["values"] = _CFG.get("history.slot_cls.model_path", [])
        self._load_model()

    def _auto_load_model(self):
        path = self.v_model_path.get().strip()
        if path and os.path.isfile(path):
            self._load_model()

    def _load_model(self):
        path = self.v_model_path.get().strip()
        if not path or not os.path.isfile(path):
            self._log_msg("⚠ Đường dẫn model không hợp lệ")
            return
        if not _TORCH_OK:
            self._log_msg("⚠ PyTorch chưa cài. Chạy: pip install torch")
            return
        self.lbl_status.config(text="⏳ Đang tải model…", fg=DIM)
        self._log_msg(f"⏳ Tải model: {os.path.basename(path)}")
        threading.Thread(target=self._load_model_thread,
                         args=(path,), daemon=True).start()

    @staticmethod
    def _inject_yolov5_path():
        """Tìm thư mục yolov5 trong hub cache và inject vào sys.path."""
        import sys as _sys
        try:
            import torch
            hub_dir = torch.hub.get_dir()
            if not os.path.isdir(hub_dir):
                return None
            # Ưu tiên thư mục có models/yolo.py
            for d in sorted(os.listdir(hub_dir), reverse=True):
                candidate = os.path.join(hub_dir, d)
                if (os.path.isdir(candidate) and
                        os.path.exists(os.path.join(candidate, "models", "yolo.py"))):
                    if candidate not in _sys.path:
                        _sys.path.insert(0, candidate)
                    return candidate
        except Exception:
            pass
        return None

    def _load_model_thread(self, path):
        import sys as _sys
        errs = []

        # ── Stage 1: yolov5 pip package ──────────────────────────────────
        # Đây là cách đáng tin cậy nhất cho YOLOv5 model
        # Cài: pip install yolov5
        try:
            import yolov5 as _yv5
            m = _yv5.load(path, device="cpu", verbose=False)
            names = m.names if hasattr(m, "names") else {}
            if isinstance(names, (list, tuple)):
                names = {i: str(n) for i, n in enumerate(names)}
            self._model = m
            self._model_task  = "yolo5_pkg"
            self._model_names = names
            self.root.after(0, lambda: self._on_model_ok(
                path, "YOLOv5 (package)", names))
            return
        except ImportError:
            errs.append("yolov5 pkg: chưa cài — chạy: pip install yolov5")
        except Exception as e:
            errs.append(f"yolov5 pkg: {e}")

        # ── Stage 2: ultralytics v8 ──────────────────────────────────────
        if _YOLO8_OK:
            try:
                m = _YOLO8(path)
                task = getattr(m, "task", "detect") or "detect"
                names = {}
                for attr in ("names", ):
                    try:
                        names = getattr(m, attr) or {}
                        break
                    except Exception:
                        pass
                if not names:
                    try:
                        names = getattr(getattr(m, "model", None), "names", {}) or {}
                    except Exception:
                        pass
                if isinstance(names, (list, tuple)):
                    names = {i: n for i, n in enumerate(names)}
                self._model = m
                self._model_task  = f"yolo8/{task}"
                self._model_names = names
                self.root.after(0, lambda: self._on_model_ok(
                    path, f"ultralytics v8 [{task}]", names))
                return
            except Exception as e:
                errs.append(f"ultralytics v8: {e}")

        # ── Stage 3: inject hub cache path rồi torch.load ────────────────
        # YOLOv5 .pt được pickle với class từ models.yolo — cần inject path
        try:
            import torch
            yv5_dir = self._inject_yolov5_path()

            # Nếu chưa có hub cache, thử download hub trước
            if not yv5_dir:
                try:
                    torch.hub.load("ultralytics/yolov5", "custom",
                                   path=path, force_reload=False,
                                   verbose=False, trust_repo=True)
                    yv5_dir = self._inject_yolov5_path()
                except Exception:
                    pass

            ckpt = torch.load(path, map_location="cpu", weights_only=False)
            names = {}
            model_obj = ckpt

            if isinstance(ckpt, dict):
                nn = ckpt.get("names", {})
                if isinstance(nn, (list, tuple)):
                    names = {i: str(n) for i, n in enumerate(nn)}
                elif isinstance(nn, dict):
                    names = {int(k): str(v) for k, v in nn.items()}
                if "model" in ckpt:
                    model_obj = ckpt["model"]
                    if hasattr(model_obj, "float"):
                        model_obj = model_obj.float()

            if hasattr(model_obj, "eval"):
                model_obj.eval()

            self._model = model_obj
            self._model_task  = "yolo5_raw"
            self._model_names = names
            self.root.after(0, lambda: self._on_model_ok(
                path, "YOLOv5 (raw torch)", names))
            return
        except Exception as e:
            errs.append(f"torch.load: {e}")

        # ── Tất cả đều thất bại ──────────────────────────────────────────
        err_msg = "\n".join(errs)
        self.root.after(0, lambda: self._on_model_err(err_msg))

    def _on_model_ok(self, path, mode_str, names):
        n = os.path.basename(path)
        cls_info = f"  classes={dict(names)}" if names else ""
        self.lbl_status.config(
            text=f"✔ {n}  [{mode_str}]{cls_info}", fg=SUCCESS)
        self._log_msg(f"✔ Tải model OK: {n}")
        self._log_msg(f"   Chế độ: {mode_str}"
                      + (f"  |  {dict(names)}" if names else ""))

    def _on_model_err(self, err):
        first_line = err.split("\n")[0][:100]
        self.lbl_status.config(text=f"✘ {first_line}", fg=_COLOR_OCCUPIED)
        self._log_msg(f"✘ Lỗi tải model:\n{err}")
        self._log_msg(
            "\n💡 Gợi ý — model YOLOv5 cần một trong:\n"
            "  pip install yolov5          ← khuyến nghị\n"
            "  pip install ultralytics     ← nếu là YOLO v8"
        )

    # ═══════════════════════════════════════════════════════════ IMAGE ══

    def _select_image(self):
        hist = _CFG.get("history.slot_cls.image_path", [])
        init = os.path.dirname(hist[0]) if hist else "."
        exts = " ".join(f"*.{e}" for e in IMAGE_EXTENSIONS)
        path = filedialog.askopenfilename(
            title="Chọn ảnh bãi đỗ xe",
            filetypes=[("Ảnh", exts), ("Tất cả", "*.*")],
            initialdir=init if os.path.isdir(init) else "."
        )
        if not path:
            return
        self._open_image(path)

    def _on_dnd_drop(self, event):
        raw = event.data.strip()
        # tkinterdnd2 wraps paths with spaces in {}
        if raw.startswith("{") and raw.endswith("}"):
            raw = raw[1:-1]
        path = raw.replace("\\", "/")
        ext = os.path.splitext(path)[1].lower().lstrip(".")
        if ext in IMAGE_EXTENSIONS:
            self._open_image(path)
        else:
            self._log_msg(f"⚠ Chỉ chấp nhận file ảnh (dropped: {os.path.basename(path)})")

    def _open_image(self, path: str):
        if not _PIL_OK:
            self._log_msg("⚠ Pillow chưa cài")
            return
        try:
            img = Image.open(path).convert("RGB")
            self._pil_img = img
            self.v_image_path.set(path)
            _push_history("history.slot_cls.image_path", path)
            self.cmb_image["values"] = _CFG.get("history.slot_cls.image_path", [])
            self._clear_box()
            self.after(10, self._render_image)
            self._log_msg(f"✔ Ảnh: {os.path.basename(path)}  ({img.width}×{img.height})")
        except Exception as ex:
            self._log_msg(f"✘ Lỗi tải ảnh: {ex}")

    def _on_canvas_resize(self, _=None):
        if self._pil_img:
            self._render_image()

    def _render_image(self):
        if not self._pil_img:
            return
        cw = max(self.canvas.winfo_width(), 50)
        ch = max(self.canvas.winfo_height(), 50)
        iw, ih = self._pil_img.size
        scale = min(cw / iw, ch / ih)
        nw = max(1, int(iw * scale))
        nh = max(1, int(ih * scale))
        self._img_scale = scale
        self._img_off_x = (cw - nw) // 2
        self._img_off_y = (ch - nh) // 2

        resized = self._pil_img.resize((nw, nh), Image.LANCZOS)
        self._tk_img = ImageTk.PhotoImage(resized)

        self.canvas.delete("all")
        self.canvas.create_image(
            self._img_off_x, self._img_off_y,
            anchor=NW, image=self._tk_img, tags="img"
        )
        self._rect_id    = None
        self._handle_ids = []
        if self._has_bbox():
            self._redraw_bbox()

    # ═════════════════════════════════════════════════════ BBOX COORDS ══

    def _c2i(self, cx, cy):
        """Canvas → image pixel coords (clamped)."""
        if self._img_scale == 0:
            return 0.0, 0.0
        ix = (cx - self._img_off_x) / self._img_scale
        iy = (cy - self._img_off_y) / self._img_scale
        if self._pil_img:
            ix = max(0.0, min(float(self._pil_img.width),  ix))
            iy = max(0.0, min(float(self._pil_img.height), iy))
        return ix, iy

    def _i2c(self, ix, iy):
        """Image pixel → canvas coords."""
        return (ix * self._img_scale + self._img_off_x,
                iy * self._img_scale + self._img_off_y)

    def _has_bbox(self):
        return (self._bx1 is not None and self._bx2 is not None
                and self._bx2 > self._bx1 and self._by2 > self._by1)

    # ══════════════════════════════════════════════════ BBOX RENDERING ══

    def _redraw_bbox(self, color=None):
        """Re-draw rectangle + 8 handles on canvas."""
        if self._rect_id:
            self.canvas.delete(self._rect_id)
            self._rect_id = None
        for hid in self._handle_ids:
            self.canvas.delete(hid)
        self._handle_ids = []

        if not self._has_bbox():
            return

        col = color or self._result_color
        cx1, cy1 = self._i2c(self._bx1, self._by1)
        cx2, cy2 = self._i2c(self._bx2, self._by2)
        mx, my   = (cx1 + cx2) / 2, (cy1 + cy2) / 2

        self._rect_id = self.canvas.create_rectangle(
            cx1, cy1, cx2, cy2,
            outline=col, width=2, tags="bbox"
        )

        hs = _HS
        for hx, hy in [(cx1, cy1), (mx, cy1), (cx2, cy1),
                        (cx2, my),
                        (cx2, cy2), (mx, cy2), (cx1, cy2),
                        (cx1, my)]:
            hid = self.canvas.create_rectangle(
                hx - hs, hy - hs, hx + hs, hy + hs,
                fill=col, outline="white", width=1, tags="handle"
            )
            self._handle_ids.append(hid)

        self._update_coords_label()

    def _handle_hit(self, cx, cy):
        """Return handle name ('nw','n',...) or None."""
        if not self._has_bbox():
            return None
        c1x, c1y = self._i2c(self._bx1, self._by1)
        c2x, c2y = self._i2c(self._bx2, self._by2)
        mx, my = (c1x + c2x) / 2, (c1y + c2y) / 2
        pts = {
            "nw": (c1x, c1y), "n": (mx, c1y), "ne": (c2x, c1y),
            "e":  (c2x, my),  "se": (c2x, c2y),
            "s":  (mx, c2y),  "sw": (c1x, c2y), "w": (c1x, my)
        }
        thresh = _HS + 4
        for name, (hx, hy) in pts.items():
            if abs(cx - hx) <= thresh and abs(cy - hy) <= thresh:
                return name
        return None

    def _inside_bbox(self, cx, cy):
        if not self._has_bbox():
            return False
        c1x, c1y = self._i2c(self._bx1, self._by1)
        c2x, c2y = self._i2c(self._bx2, self._by2)
        return c1x < cx < c2x and c1y < cy < c2y

    # ══════════════════════════════════════════════════ MOUSE HANDLERS ══

    def _on_motion(self, e):
        """Update cursor on hover (no button)."""
        if not self._has_bbox():
            self.canvas.config(cursor=_CURSOR_DRAW)
            return
        if self._handle_hit(e.x, e.y):
            self.canvas.config(cursor=_CURSOR_RESIZE)
        elif self._inside_bbox(e.x, e.y):
            self.canvas.config(cursor=_CURSOR_MOVE)
        else:
            self.canvas.config(cursor=_CURSOR_DRAW)

    def _on_press(self, e):
        if not self._pil_img:
            return
        self._drag_cx, self._drag_cy = e.x, e.y

        h = self._handle_hit(e.x, e.y)
        if h:
            # Start resize
            self._mode = f"resize_{h}"
            self._drag_bx1 = self._bx1
            self._drag_by1 = self._by1
            self._drag_bx2 = self._bx2
            self._drag_by2 = self._by2
            return

        if self._inside_bbox(e.x, e.y):
            # Start move
            self._mode = "move"
            self._drag_bx1 = self._bx1
            self._drag_by1 = self._by1
            self._drag_bx2 = self._bx2
            self._drag_by2 = self._by2
            return

        # Start new draw
        self._mode = "draw"
        self._bx1 = self._by1 = self._bx2 = self._by2 = None
        self._result_color = ACCENT
        self._draw_start = self._c2i(e.x, e.y)
        self._redraw_bbox()
        self._reset_result()

    def _on_drag(self, e):
        if not self._pil_img:
            return
        dx_c = e.x - self._drag_cx
        dy_c = e.y - self._drag_cy
        dx_i = dx_c / self._img_scale if self._img_scale else 0
        dy_i = dy_c / self._img_scale if self._img_scale else 0

        if self._mode == "draw" and self._draw_start:
            ix, iy = self._c2i(e.x, e.y)
            sx, sy = self._draw_start
            self._bx1, self._by1 = min(sx, ix), min(sy, iy)
            self._bx2, self._by2 = max(sx, ix), max(sy, iy)
            self._redraw_bbox()

        elif self._mode == "move":
            iw = self._pil_img.width if self._pil_img else 9999
            ih = self._pil_img.height if self._pil_img else 9999
            w = self._drag_bx2 - self._drag_bx1
            h = self._drag_by2 - self._drag_by1
            nx1 = max(0.0, min(iw - w, self._drag_bx1 + dx_i))
            ny1 = max(0.0, min(ih - h, self._drag_by1 + dy_i))
            self._bx1, self._by1 = nx1, ny1
            self._bx2, self._by2 = nx1 + w, ny1 + h
            self._redraw_bbox()

        elif self._mode.startswith("resize_"):
            h_name = self._mode[7:]
            iw = float(self._pil_img.width  if self._pil_img else 9999)
            ih = float(self._pil_img.height if self._pil_img else 9999)
            x1, y1 = self._drag_bx1, self._drag_by1
            x2, y2 = self._drag_bx2, self._drag_by2

            ix, iy = self._c2i(e.x, e.y)

            if   h_name == "nw": x1, y1 = ix, iy
            elif h_name == "n":  y1 = iy
            elif h_name == "ne": x2, y1 = ix, iy
            elif h_name == "e":  x2 = ix
            elif h_name == "se": x2, y2 = ix, iy
            elif h_name == "s":  y2 = iy
            elif h_name == "sw": x1, y2 = ix, iy
            elif h_name == "w":  x1 = ix

            # Clamp and keep valid (min 10px)
            x1 = max(0.0, min(x1, iw))
            y1 = max(0.0, min(y1, ih))
            x2 = max(0.0, min(x2, iw))
            y2 = max(0.0, min(y2, ih))
            self._bx1 = min(x1, x2)
            self._by1 = min(y1, y2)
            self._bx2 = max(x1, x2)
            self._by2 = max(y1, y2)
            self._redraw_bbox()

    def _on_release(self, e):
        if not self._pil_img:
            return
        prev_mode = self._mode
        self._mode = "draw"   # reset to draw for next interaction

        if not self._has_bbox():
            return
        w = self._bx2 - self._bx1
        h = self._by2 - self._by1
        if w < 5 or h < 5:
            self._clear_box()
            return

        # Auto-classify after drawing/moving/resizing
        self._run()

    def _clear_box(self, _=None):
        self._bx1 = self._by1 = self._bx2 = self._by2 = None
        self._draw_start = None
        self._mode = "draw"
        self._result_color = ACCENT
        if self._rect_id:
            self.canvas.delete(self._rect_id)
            self._rect_id = None
        for hid in self._handle_ids:
            self.canvas.delete(hid)
        self._handle_ids = []
        self.lbl_coords.config(text="—")
        self.canvas.config(cursor=_CURSOR_DRAW)
        self._reset_result()

    def _update_coords_label(self):
        if not self._has_bbox():
            return
        self.lbl_coords.config(
            text=(f"({int(self._bx1)}, {int(self._by1)})  →  "
                  f"({int(self._bx2)}, {int(self._by2)})\n"
                  f"size: {int(self._bx2-self._bx1)}×{int(self._by2-self._by1)} px")
        )

    def _reset_result(self):
        self.lbl_result.config(text="—", fg=DIM)
        self.lbl_conf_disp.config(text="")
        self.lbl_detail.config(text="")
        self.prev_canvas.delete("all")
        self._prev_hint_id = self.prev_canvas.create_text(
            120, 75, text="Vùng cắt hiện ở đây", fill=DIM, font=("Segoe UI", 9))
        self._crop_pil = None

    # ═════════════════════════════════════════════════════ INFERENCE ══

    def _run(self, _=None):
        """F5 / auto: phân loại vùng đang chọn."""
        if not self._pil_img:
            self._log_msg("⚠ Chưa tải ảnh")
            return
        if not self._has_bbox():
            self._log_msg("⚠ Chưa vẽ vùng chọn")
            return
        if not self._model:
            self._log_msg("⚠ Chưa tải model — chọn detect.pt trước")
            return

        x1, y1, x2, y2 = (int(self._bx1), int(self._by1),
                           int(self._bx2), int(self._by2))
        crop = self._pil_img.crop((x1, y1, x2, y2))
        self._crop_pil = crop
        self._show_crop_preview(crop)

        conf = self.v_conf.get()
        task = self._model_task
        model = self._model
        names = self._model_names

        def _infer():
            try:
                label, c, detail = self._do_infer(model, task, names, crop, conf)
                self.root.after(0, lambda: self._apply_result(label, c, detail))
            except Exception as ex:
                msg = str(ex)
                self.root.after(0, lambda: self._log_msg(f"✘ Lỗi predict: {msg}"))

        threading.Thread(target=_infer, daemon=True).start()

    @staticmethod
    def _do_infer(model, task, names, crop_pil, conf_thresh):
        """Run inference. Returns (label, confidence, detail_str)."""
        import torch
        import numpy as np

        # ── yolov5 package ─────────────────────────────────────────────
        if task == "yolo5_pkg":
            results = model(crop_pil, size=640, augment=False)
            det = results.xyxy[0].cpu().numpy()  # [N,6]
            if len(det) == 0:
                return "empty", 1.0, "Không phát hiện → TRỐNG"
            best = det[det[:, 4].argmax()]
            lbl  = names.get(int(best[5]), str(int(best[5])))
            c    = float(best[4])
            detail = "\n".join(
                f"{names.get(int(d[5]), int(d[5]))}: {d[4]:.3f}" for d in det
            )
            return lbl, c, detail

        # ── ultralytics v8 ─────────────────────────────────────────────
        if task.startswith("yolo8/"):
            results = model(crop_pil, verbose=False, conf=conf_thresh)
            r = results[0]
            t = task.split("/")[1]

            if t == "classify":
                probs = r.probs
                top1 = int(probs.top1)
                top1c = float(probs.top1conf)
                lbl = names.get(top1, str(top1))
                detail = "\n".join(
                    f"{names.get(i, i)}: {p:.3f}"
                    for i, p in enumerate(probs.data.tolist()[:6])
                ) if hasattr(probs, "data") else ""
                return lbl, top1c, detail

            else:  # detect / segment / pose
                boxes = r.boxes
                if boxes is None or len(boxes) == 0:
                    return "empty", 1.0, "Không phát hiện → TRỐNG"
                confs = boxes.conf.tolist()
                clss  = boxes.cls.tolist()
                best  = max(range(len(confs)), key=lambda i: confs[i])
                lbl   = names.get(int(clss[best]), str(int(clss[best])))
                detail = "\n".join(
                    f"{names.get(int(clss[i]), int(clss[i]))}: {confs[i]:.3f}"
                    for i in range(len(confs))
                )
                return lbl, confs[best], detail

        # ── YOLOv5 hub ─────────────────────────────────────────────────
        elif task == "yolo5_hub":
            results = model(crop_pil, size=640, augment=False)
            det = results.xyxy[0].cpu().numpy()  # [N,6]
            if len(det) == 0:
                return "empty", 1.0, "Không phát hiện → TRỐNG"
            best = det[det[:, 4].argmax()]
            lbl  = names.get(int(best[5]), str(int(best[5])))
            c    = float(best[4])
            detail = "\n".join(
                f"{names.get(int(d[5]), int(d[5]))}: {d[4]:.3f}" for d in det
            )
            return lbl, c, detail

        # ── YOLOv5 raw (no NMS, direct forward) ────────────────────────
        elif task == "yolo5_raw":
            size = 640
            img = crop_pil.resize((size, size), Image.BILINEAR)
            arr = np.array(img, dtype=np.float32) / 255.0
            tensor = torch.from_numpy(arr.transpose(2, 0, 1)).unsqueeze(0)

            model.eval()
            with torch.no_grad():
                pred = model(tensor)
            if isinstance(pred, (list, tuple)):
                pred = pred[0]
            pred = pred.squeeze(0)  # [num_preds, 5+nc]

            nc = max(1, pred.shape[1] - 5)
            obj = torch.sigmoid(pred[:, 4])
            if pred.shape[1] > 5:
                cls_sc = torch.sigmoid(pred[:, 5:])
                combined = obj.unsqueeze(1) * cls_sc  # [N, nc]
            else:
                combined = obj.unsqueeze(1)

            max_score = float(combined.max())
            if max_score < conf_thresh:
                return "empty", 1.0 - max_score, "Score thấp → TRỐNG"

            flat_idx = int(combined.argmax())
            pred_idx = flat_idx // nc
            cls_idx  = flat_idx % nc
            lbl = names.get(cls_idx, str(cls_idx)) if names else str(cls_idx)
            detail = f"class {cls_idx}: {max_score:.3f}  (obj: {float(obj[pred_idx]):.3f})"
            return lbl, max_score, detail

        else:
            return "unknown", 0.0, f"task không rõ: {task}"

    def _show_crop_preview(self, crop: "Image.Image"):
        preview = crop.copy()
        preview.thumbnail((240, 150), Image.LANCZOS)
        tk_img = ImageTk.PhotoImage(preview)

        self.prev_canvas.delete("all")
        pw = self.prev_canvas.winfo_width() or 240
        ph = self.prev_canvas.winfo_height() or 150
        self._prev_img_id = self.prev_canvas.create_image(
            pw // 2, ph // 2, anchor=CENTER, image=tk_img)
        self._prev_tk_img = tk_img

    def _apply_result(self, label: str, confidence: float, detail: str):
        ll = label.lower().replace("-", "_")

        if any(k in ll for k in _EMPTY_KEYWORDS):
            display, color = "🟢  TRỐNG", _COLOR_EMPTY
        elif any(k in ll for k in _OCCUPIED_KEYWORDS):
            display, color = "🔴  CÓ XE", _COLOR_OCCUPIED
        else:
            display, color = f"🔵  {label.upper()}", _COLOR_UNKNOWN

        self._result_color = color
        self.lbl_result.config(text=display, fg=color)
        self.lbl_conf_disp.config(text=f"Độ tin cậy: {confidence:.1%}", fg=TEXT)
        self.lbl_detail.config(text=detail[:150], fg=DIM)

        # Cập nhật màu viền bbox
        if self._rect_id:
            self.canvas.itemconfig(self._rect_id, outline=color, width=3)
        for hid in self._handle_ids:
            self.canvas.itemconfig(hid, fill=color)

        self._log_msg(f"✔ {display.strip()}  conf={confidence:.1%}  label={label}")

    # ═══════════════════════════════════════════════════════════ ZOOM ══

    def _zoom_full_image(self, _=None):
        if not self._pil_img:
            return
        try:
            from ...core.ui_helpers import _zoom_image_window
            _zoom_image_window(self.root, self._pil_img, "Phóng to ảnh gốc")
        except Exception as ex:
            self._log_msg(f"⚠ Zoom: {ex}")

    def _zoom_crop(self, _=None):
        if not self._crop_pil:
            return
        try:
            from ...core.ui_helpers import _zoom_image_window
            _zoom_image_window(self.root, self._crop_pil, "Phóng to vùng chọn")
        except Exception as ex:
            self._log_msg(f"⚠ Zoom: {ex}")

    # ═══════════════════════════════════════════════════════════════ LOG ══

    def _log_msg(self, msg: str):
        self._log.config(state=NORMAL)
        self._log.insert(END, msg + "\n")
        self._log.see(END)
        self._log.config(state=DISABLED)
