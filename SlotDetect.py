#!/usr/bin/env python3
"""
SlotDetect.py — KZTEK Parking Slot Detector  (Standalone)
Phân loại ô đỗ xe: load ảnh → vẽ / di chuyển / resize bbox → detect.pt → TRỐNG / CÓ XE

Run  : python SlotDetect.py
Build: buildSlotDetect.bat
"""

import os
import sys
import json
import threading
from tkinter import *
from tkinter import filedialog, ttk, messagebox

# ── Optional deps ─────────────────────────────────────────────────────────────
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
    from tkinterdnd2 import TkinterDnD, DND_FILES
    _DND_OK = True
except ImportError:
    _DND_OK = False

# ── Brand / UI constants ──────────────────────────────────────────────────────
BG      = "#1e1e2e"
CARD    = "#2a2a3e"
ACCENT  = "#F05922"   # cam KZTEK
ACCENT2 = "#4A3F8C"   # navy KZTEK
TEXT    = "#e0e0f0"
DIM     = "#9090b0"
SUCCESS = "#4caf50"

C_EMPTY    = "#4caf50"
C_OCCUPIED = "#f44336"
C_UNKNOWN  = ACCENT

F_MAIN  = ("Segoe UI", 10)
F_BOLD  = ("Segoe UI Semibold", 11)
F_MONO  = ("Consolas", 9)
F_BIG   = ("Segoe UI Semibold", 24)
F_GIANT = ("Segoe UI Semibold", 48)

IMG_EXTS = {"jpg", "jpeg", "png", "bmp", "webp", "gif", "tiff", "tif"}

EMPTY_KW    = {"empty","trong","trống","free","available",
               "no_car","no car","0","class0","vacant"}
OCCUPIED_KW = {"occupied","car","vehicle","xe","co_xe","có xe",
               "co xe","full","1","class1","taken"}

_HS = 5          # handle half-size (canvas px)
_CUR_DRAW   = "crosshair"
_CUR_MOVE   = "fleur"
_CUR_RESIZE = "sizing"

# ── Settings ──────────────────────────────────────────────────────────────────
_CFG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          ".slot_detect_settings.json")

class _Cfg:
    def __init__(self):
        self._d = {}
        self._load()

    def get(self, k, default=None):
        return self._d.get(k, default)

    def set(self, k, v):
        self._d[k] = v
        self._save()

    def _load(self):
        try:
            if os.path.exists(_CFG_PATH):
                with open(_CFG_PATH, "r", encoding="utf-8") as f:
                    self._d = json.load(f)
        except Exception:
            self._d = {}

    def _save(self):
        try:
            with open(_CFG_PATH, "w", encoding="utf-8") as f:
                json.dump(self._d, f, ensure_ascii=False, indent=2)
        except Exception:
            pass


_cfg = _Cfg()


def _bind_history(key, combo, max_items=20):
    saved = _cfg.get(key, [])
    combo["values"] = saved
    if saved:
        combo.set(saved[0])

    def _save(*_):
        val = combo.get().strip()
        if not val:
            return
        hist = list(_cfg.get(key, []))
        if val in hist:
            hist.remove(val)
        hist.insert(0, val)
        _cfg.set(key, hist[:max_items])
        combo["values"] = _cfg.get(key, [])

    combo.bind("<FocusOut>", _save)
    combo.bind("<Return>",   _save)


def _push_history(key, val, max_items=20):
    hist = list(_cfg.get(key, []))
    if val in hist:
        hist.remove(val)
    hist.insert(0, val)
    _cfg.set(key, hist[:max_items])


# ── TTK style ─────────────────────────────────────────────────────────────────
def _apply_style():
    s = ttk.Style()
    try:
        s.theme_use("clam")
    except Exception:
        pass
    s.configure("Dark.TCombobox",
                fieldbackground=CARD, background=CARD,
                foreground=TEXT, selectbackground=ACCENT2,
                selectforeground="white", arrowcolor=TEXT,
                borderwidth=0, relief="flat")
    s.map("Dark.TCombobox",
          fieldbackground=[("readonly", CARD), ("!readonly", CARD),
                           ("disabled", BG)],
          foreground=[("readonly", TEXT), ("!readonly", TEXT)],
          selectbackground=[("readonly", ACCENT2)],
          selectforeground=[("readonly", "white")],
          background=[("active", ACCENT2), ("!active", CARD)])
    s.configure("Flat.TScrollbar",
                background=CARD, troughcolor=BG,
                arrowcolor=DIM, borderwidth=0, relief="flat")


# ── Zoom window ───────────────────────────────────────────────────────────────
def _zoom(root, pil_img, title="Phóng to"):
    if not _PIL_OK or not pil_img:
        return
    win = Toplevel(root)
    win.title(title)
    win.configure(bg="#0d0d1a")
    win.resizable(True, True)
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    img = pil_img.copy()
    img.thumbnail((int(sw * 0.85), int(sh * 0.85)), Image.LANCZOS)

    def _render():
        cv = Canvas(win, bg="#0d0d1a", highlightthickness=0,
                    width=img.width, height=img.height)
        cv.pack(fill=BOTH, expand=True)
        tk_img = ImageTk.PhotoImage(img)
        cv.create_image(img.width // 2, img.height // 2,
                        anchor=CENTER, image=tk_img)
        cv._tk_img = tk_img
        win.geometry(f"{img.width}x{img.height}")

    win.after(30, _render)
    win.bind("<Escape>",    lambda _: win.destroy())
    win.bind("<Control-w>", lambda _: win.destroy())
    win.lift()
    win.focus_set()


# ═══════════════════════════════════════════════════════ Main Application ══════

class SlotDetectApp(TkinterDnD.Tk if _DND_OK else Tk):
    """Cửa sổ chính: Phân loại ô đỗ xe."""

    def __init__(self):
        super().__init__()
        self.title("KZTEK — Slot Detect  |  Phân loại ô đỗ xe")
        self.geometry("1100x700")
        self.minsize(860, 560)
        self.configure(bg=BG)
        try:
            self.state("zoomed")
        except Exception:
            pass
        _apply_style()

        # ── Model ─────────────────────────────────────────────────────────
        self._model       = None
        self._model_task  = "detect"
        self._model_names = {}

        # ── Image ─────────────────────────────────────────────────────────
        self._pil_img   = None
        self._tk_img    = None
        self._img_scale = 1.0
        self._img_off_x = 0
        self._img_off_y = 0

        # ── Bbox (image pixel, x1<x2, y1<y2) ─────────────────────────────
        self._bx1 = self._by1 = self._bx2 = self._by2 = None
        self._rect_id    = None
        self._handle_ids = []
        self._result_color = ACCENT

        # ── Interaction ───────────────────────────────────────────────────
        self._mode = "draw"
        self._drag_cx = self._drag_cy = 0
        self._drag_bx1 = self._drag_by1 = self._drag_bx2 = self._drag_by2 = 0
        self._draw_start = None
        self._crop_pil   = None

        # ── Tkinter vars ──────────────────────────────────────────────────
        self.v_model = StringVar()
        self.v_image = StringVar()
        self.v_conf  = DoubleVar(value=float(_cfg.get("conf", 0.25)))
        self.v_conf.trace_add("write",
            lambda *_: _cfg.set("conf", round(self.v_conf.get(), 2)))

        self._build()
        self.after(200, self._auto_load_model)
        self._bind_shortcuts()

    # ═══════════════════════════════════════════════════════════ BUILD ══

    def _build(self):
        self._build_titlebar()
        self._build_toolbar()
        self._build_body()

    def _build_titlebar(self):
        bar = Frame(self, bg=CARD, height=38)
        bar.pack(fill=X)
        bar.pack_propagate(False)

        Label(bar, text="  🅿  KZTEK  Slot Detect",
              bg=CARD, fg=TEXT, font=F_BOLD).pack(side=LEFT, padx=6)

        Label(bar,
              text="Phân loại ô đỗ xe trống / có xe",
              bg=CARD, fg=DIM, font=("Segoe UI", 9)).pack(side=LEFT, padx=2)

        # Keyboard hint
        Label(bar,
              text="F5: Phân loại  |  Ctrl+O: Mở ảnh  |  Esc: Xóa bbox",
              bg=CARD, fg=DIM, font=("Segoe UI", 8)).pack(side=RIGHT, padx=12)

    def _build_toolbar(self):
        bar = Frame(self, bg=CARD, padx=10, pady=7)
        bar.pack(fill=X)

        # Row 1: model
        r1 = Frame(bar, bg=CARD)
        r1.pack(fill=X, pady=(0, 3))

        Label(r1, text="Model:", bg=CARD, fg=TEXT,
              font=F_BOLD, width=7, anchor=W).pack(side=LEFT)
        self.cmb_model = ttk.Combobox(r1, textvariable=self.v_model,
                                      font=F_MAIN, style="Dark.TCombobox")
        self.cmb_model.pack(side=LEFT, fill=X, expand=True, padx=(0, 6))
        _bind_history("model_path", self.cmb_model)

        Button(r1, text="Chọn Model…", command=self._select_model,
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
        self.cmb_image = ttk.Combobox(r2, textvariable=self.v_image,
                                      font=F_MAIN, style="Dark.TCombobox")
        self.cmb_image.pack(side=LEFT, fill=X, expand=True, padx=(0, 6))
        _bind_history("image_path", self.cmb_image)

        Button(r2, text="Chọn Ảnh…  (Ctrl+O)", command=self._select_image,
               bg=ACCENT2, fg="white", font=F_MAIN, relief="flat",
               padx=8, cursor="hand2",
               activebackground=ACCENT, activeforeground="white"
               ).pack(side=LEFT, padx=(0, 14))

        Label(r2, text="Conf:", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        self._lbl_conf = Label(r2,
            text=f"{self.v_conf.get():.2f}",
            bg=CARD, fg=TEXT, font=F_MONO, width=4)
        self._lbl_conf.pack(side=LEFT, padx=(3, 0))
        Scale(r2, from_=0.05, to=0.95, resolution=0.05,
              variable=self.v_conf, orient=HORIZONTAL, length=110,
              bg=CARD, fg=TEXT, activebackground=ACCENT,
              highlightthickness=0, showvalue=False, troughcolor=BG,
              command=lambda v: self._lbl_conf.config(text=f"{float(v):.2f}")
              ).pack(side=LEFT)

    def _build_body(self):
        body = Frame(self, bg=BG)
        body.pack(fill=BOTH, expand=True)

        # ── Left: drawing canvas ──────────────────────────────────────────
        left = Frame(body, bg=BG)
        left.pack(side=LEFT, fill=BOTH, expand=True, padx=(6, 3), pady=6)

        Label(left,
              text="Kéo chuột để vẽ vùng  |  Kéo handle để resize  |  "
                   "Kéo trong bbox để di chuyển  |  Chuột phải: xóa  |  "
                   "Kéo thả file ảnh vào đây  |  Double-click: phóng to",
              bg=BG, fg=DIM, font=("Segoe UI", 8)).pack(anchor=W, pady=(0, 3))

        self.canvas = Canvas(left, bg="#0d0d1a", cursor=_CUR_DRAW,
                             highlightthickness=1, highlightbackground=ACCENT2)
        self.canvas.pack(fill=BOTH, expand=True)

        self.canvas.bind("<ButtonPress-1>",  self._on_press)
        self.canvas.bind("<B1-Motion>",       self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Button-3>",        self._clear_box)
        self.canvas.bind("<Double-Button-1>", self._zoom_image)
        self.canvas.bind("<Motion>",          self._on_motion)
        self.canvas.bind("<Configure>",       self._on_canvas_resize)

        if _DND_OK:
            try:
                self.canvas.drop_target_register(DND_FILES)
                self.canvas.dnd_bind("<<Drop>>", self._on_drop)
            except Exception:
                pass

        # ── Right: result panel ───────────────────────────────────────────
        right = Frame(body, bg=CARD, width=300)
        right.pack(side=RIGHT, fill=Y, padx=(3, 6), pady=6)
        right.pack_propagate(False)

        # ── Phân loại button — đặt đầu tiên để luôn hiển thị ─────────────
        Label(right, text="KẾT QUẢ PHÂN LOẠI",
              bg=CARD, fg=TEXT, font=F_BOLD).pack(pady=(14, 8))

        Button(right, text="⚡   PHÂN LOẠI   (F5)",
               command=self._run,
               bg=ACCENT, fg="white",
               font=("Segoe UI Semibold", 13),
               relief="flat", pady=9, cursor="hand2",
               activebackground="#d04010", activeforeground="white"
               ).pack(fill=X, padx=14, pady=(0, 12))

        # ── Preview crop ──────────────────────────────────────────────────
        self.prev_cv = Canvas(right, bg="#0d0d1a",
                              width=260, height=160,
                              highlightthickness=1,
                              highlightbackground=ACCENT2)
        self.prev_cv.pack(padx=14, pady=(0, 8))
        self._prev_hint = self.prev_cv.create_text(
            130, 80, text="Vùng cắt hiện ở đây",
            fill=DIM, font=("Segoe UI", 9))
        self._prev_tk   = None
        self.prev_cv.bind("<Double-Button-1>", self._zoom_crop)

        # ── Result text ───────────────────────────────────────────────────
        self.lbl_result = Label(right, text="—",
                                bg=CARD, fg=DIM, font=F_BIG)
        self.lbl_result.pack(pady=(4, 0))

        self.lbl_conf_disp = Label(right, text="",
                                   bg=CARD, fg=DIM,
                                   font=("Segoe UI", 11))
        self.lbl_conf_disp.pack()

        self.lbl_detail = Label(right, text="",
                                bg=CARD, fg=DIM,
                                font=F_MONO, wraplength=268, justify=LEFT)
        self.lbl_detail.pack(padx=12, pady=(4, 0))

        # ── Secondary controls ────────────────────────────────────────────
        Frame(right, bg=DIM, height=1).pack(fill=X, padx=14, pady=10)

        Button(right, text="🗑  Xóa vùng chọn  (Esc)",
               command=self._clear_box,
               bg=ACCENT2, fg="white", font=F_MAIN,
               relief="flat", pady=4, cursor="hand2",
               activebackground=ACCENT, activeforeground="white"
               ).pack(fill=X, padx=14)

        Label(right, text="Tọa độ (pixel):", bg=CARD, fg=DIM,
              font=("Segoe UI", 9)).pack(anchor=W, padx=14, pady=(8, 0))
        self.lbl_coords = Label(right, text="—",
                                bg=CARD, fg=TEXT, font=F_MONO)
        self.lbl_coords.pack(anchor=W, padx=14)

        # ── Log ───────────────────────────────────────────────────────────
        Frame(right, bg=DIM, height=1).pack(fill=X, padx=14, pady=(10, 6))

        lf = Frame(right, bg=BG)
        lf.pack(fill=BOTH, expand=True, padx=(14, 0), pady=(0, 8))

        self._log = Text(lf, bg="#0d0d1a", fg=TEXT, font=F_MONO,
                         wrap=WORD, state=DISABLED, relief="flat",
                         selectbackground=ACCENT2)
        _sb = ttk.Scrollbar(lf, command=self._log.yview,
                             style="Flat.TScrollbar")
        self._log.configure(yscrollcommand=_sb.set)
        _sb.pack(side=RIGHT, fill=Y)
        self._log.pack(side=LEFT, fill=BOTH, expand=True)

    # ══════════════════════════════════════════════════════════ SHORTCUTS ══

    def _bind_shortcuts(self):
        self.bind("<F5>",        lambda _: self._run())
        self.bind("<Control-o>", lambda _: self._select_image())
        self.bind("<Escape>",    lambda _: self._clear_box())
        self.bind("<Control-l>", self._clear_log)

    def _clear_log(self, _=None):
        self._log.config(state=NORMAL)
        self._log.delete("1.0", END)
        self._log.config(state=DISABLED)

    # ══════════════════════════════════════════════════════════════ MODEL ══

    def _select_model(self):
        hist = _cfg.get("model_path", [])
        init = os.path.dirname(hist[0]) if hist else "."
        path = filedialog.askopenfilename(
            title="Chọn model detect (.pt)",
            filetypes=[("PyTorch model", "*.pt"), ("Tất cả", "*.*")],
            initialdir=init if os.path.isdir(init) else "."
        )
        if not path:
            return
        self.v_model.set(path)
        _push_history("model_path", path)
        self.cmb_model["values"] = _cfg.get("model_path", [])
        self._load_model()

    def _auto_load_model(self):
        path = self.v_model.get().strip()
        if path and os.path.isfile(path):
            self._load_model()

    def _load_model(self):
        path = self.v_model.get().strip()
        if not path or not os.path.isfile(path):
            self._log_msg("⚠ Đường dẫn model không hợp lệ")
            return
        if not _TORCH_OK:
            self._log_msg("⚠ PyTorch chưa cài: pip install torch")
            return
        self.lbl_status.config(text="⏳ Đang tải model…", fg=DIM)
        self._log_msg(f"⏳ Tải model: {os.path.basename(path)}")
        threading.Thread(target=self._load_thread,
                         args=(path,), daemon=True).start()

    @staticmethod
    def _inject_yolov5_path():
        """Tìm yolov5 trong torch hub cache và inject vào sys.path."""
        try:
            import torch
            hub_dir = torch.hub.get_dir()
            if not os.path.isdir(hub_dir):
                return None
            for d in sorted(os.listdir(hub_dir), reverse=True):
                c = os.path.join(hub_dir, d)
                if (os.path.isdir(c) and
                        os.path.exists(os.path.join(c, "models", "yolo.py"))):
                    if c not in sys.path:
                        sys.path.insert(0, c)
                    return c
        except Exception:
            pass
        return None

    def _load_thread(self, path):
        errs = []

        # Stage 1: yolov5 pip package (pip install yolov5)
        try:
            import yolov5 as _yv5
            m = _yv5.load(path, device="cpu", verbose=False)
            names = m.names if hasattr(m, "names") else {}
            if isinstance(names, (list, tuple)):
                names = {i: str(n) for i, n in enumerate(names)}
            self._model, self._model_task = m, "yolo5_pkg"
            self._model_names = names
            self.after(0, lambda: self._model_ok(path, "YOLOv5 package", names))
            return
        except ImportError:
            errs.append("yolov5 pkg: chưa cài  →  pip install yolov5")
        except Exception as e:
            errs.append(f"yolov5 pkg: {e}")

        # Stage 2: ultralytics v8
        if _YOLO8_OK:
            try:
                m = _YOLO8(path)
                task = getattr(m, "task", "detect") or "detect"
                names = {}
                try:
                    names = m.names or {}
                except Exception:
                    pass
                if not names:
                    try:
                        names = getattr(getattr(m, "model", None), "names", {}) or {}
                    except Exception:
                        pass
                if isinstance(names, (list, tuple)):
                    names = {i: n for i, n in enumerate(names)}
                self._model, self._model_task = m, f"yolo8/{task}"
                self._model_names = names
                self.after(0, lambda: self._model_ok(
                    path, f"ultralytics v8 [{task}]", names))
                return
            except Exception as e:
                errs.append(f"ultralytics v8: {e}")

        # Stage 3: torch.load + inject hub sys.path
        try:
            import torch
            yv5_dir = self._inject_yolov5_path()
            if not yv5_dir:
                try:
                    torch.hub.load("ultralytics/yolov5", "custom",
                                   path=path, force_reload=False,
                                   verbose=False, trust_repo=True)
                    yv5_dir = self._inject_yolov5_path()
                except Exception:
                    pass

            ckpt = torch.load(path, map_location="cpu", weights_only=False)
            names, model_obj = {}, ckpt
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
            self._model, self._model_task = model_obj, "yolo5_raw"
            self._model_names = names
            self.after(0, lambda: self._model_ok(
                path, "YOLOv5 raw torch", names))
            return
        except Exception as e:
            errs.append(f"torch.load: {e}")

        self.after(0, lambda: self._model_err("\n".join(errs)))

    def _model_ok(self, path, mode, names):
        n = os.path.basename(path)
        cls = f"  classes={dict(names)}" if names else ""
        self.lbl_status.config(text=f"✔ {n}  [{mode}]{cls}", fg=SUCCESS)
        self._log_msg(f"✔ Model: {n}")
        self._log_msg(f"   Mode: {mode}" + (f"  |  {dict(names)}" if names else ""))

    def _model_err(self, err):
        self.lbl_status.config(
            text=f"✘ {err.split(chr(10))[0][:90]}", fg=C_OCCUPIED)
        self._log_msg(f"✘ Lỗi tải model:\n{err}")
        self._log_msg(
            "\n💡 Model YOLOv5 cần:  pip install yolov5\n"
            "   Model YOLO v8 cần: pip install ultralytics"
        )

    # ══════════════════════════════════════════════════════════════ IMAGE ══

    def _select_image(self):
        hist = _cfg.get("image_path", [])
        init = os.path.dirname(hist[0]) if hist else "."
        exts = " ".join(f"*.{e}" for e in IMG_EXTS)
        path = filedialog.askopenfilename(
            title="Chọn ảnh bãi đỗ xe",
            filetypes=[("Ảnh", exts), ("Tất cả", "*.*")],
            initialdir=init if os.path.isdir(init) else "."
        )
        if path:
            self._open_image(path)

    def _on_drop(self, event):
        raw = event.data.strip()
        if raw.startswith("{") and raw.endswith("}"):
            raw = raw[1:-1]
        path = raw.replace("\\", "/")
        ext = os.path.splitext(path)[1].lower().lstrip(".")
        if ext in IMG_EXTS:
            self._open_image(path)
        else:
            self._log_msg(f"⚠ Không phải file ảnh: {os.path.basename(path)}")

    def _open_image(self, path):
        if not _PIL_OK:
            self._log_msg("⚠ Pillow chưa cài: pip install Pillow")
            return
        try:
            img = Image.open(path).convert("RGB")
            self._pil_img = img
            self.v_image.set(path)
            _push_history("image_path", path)
            self.cmb_image["values"] = _cfg.get("image_path", [])
            self._clear_box()
            self.after(10, self._render_image)
            self._log_msg(f"✔ Ảnh: {os.path.basename(path)}  "
                          f"({img.width}×{img.height})")
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
        nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
        self._img_scale = scale
        self._img_off_x = (cw - nw) // 2
        self._img_off_y = (ch - nh) // 2
        resized = self._pil_img.resize((nw, nh), Image.LANCZOS)
        self._tk_img = ImageTk.PhotoImage(resized)
        self.canvas.delete("all")
        self.canvas.create_image(self._img_off_x, self._img_off_y,
                                  anchor=NW, image=self._tk_img, tags="img")
        self._rect_id = None
        self._handle_ids = []
        if self._has_bbox():
            self._redraw_bbox()

    # ═══════════════════════════════════════════════════════ BBOX COORDS ══

    def _c2i(self, cx, cy):
        if not self._img_scale:
            return 0.0, 0.0
        ix = (cx - self._img_off_x) / self._img_scale
        iy = (cy - self._img_off_y) / self._img_scale
        if self._pil_img:
            ix = max(0.0, min(float(self._pil_img.width),  ix))
            iy = max(0.0, min(float(self._pil_img.height), iy))
        return ix, iy

    def _i2c(self, ix, iy):
        return (ix * self._img_scale + self._img_off_x,
                iy * self._img_scale + self._img_off_y)

    def _has_bbox(self):
        return (self._bx1 is not None and self._bx2 is not None
                and self._bx2 > self._bx1 and self._by2 > self._by1)

    # ═══════════════════════════════════════════════════════ BBOX RENDER ══

    def _redraw_bbox(self, color=None):
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
            cx1, cy1, cx2, cy2, outline=col, width=2, tags="bbox")

        hs = _HS
        for hx, hy in [(cx1,cy1),(mx,cy1),(cx2,cy1),(cx2,my),
                        (cx2,cy2),(mx,cy2),(cx1,cy2),(cx1,my)]:
            hid = self.canvas.create_rectangle(
                hx-hs, hy-hs, hx+hs, hy+hs,
                fill=col, outline="white", width=1, tags="handle")
            self._handle_ids.append(hid)

        self._update_coords()

    def _handle_at(self, cx, cy):
        if not self._has_bbox():
            return None
        c1x, c1y = self._i2c(self._bx1, self._by1)
        c2x, c2y = self._i2c(self._bx2, self._by2)
        mx, my   = (c1x+c2x)/2, (c1y+c2y)/2
        pts = {"nw":(c1x,c1y),"n":(mx,c1y),"ne":(c2x,c1y),
               "e":(c2x,my),"se":(c2x,c2y),"s":(mx,c2y),
               "sw":(c1x,c2y),"w":(c1x,my)}
        t = _HS + 4
        for name,(hx,hy) in pts.items():
            if abs(cx-hx) <= t and abs(cy-hy) <= t:
                return name
        return None

    def _inside_bbox(self, cx, cy):
        if not self._has_bbox():
            return False
        c1x, c1y = self._i2c(self._bx1, self._by1)
        c2x, c2y = self._i2c(self._bx2, self._by2)
        return c1x < cx < c2x and c1y < cy < c2y

    # ═══════════════════════════════════════════════════════ MOUSE INPUT ══

    def _on_motion(self, e):
        if not self._has_bbox():
            self.canvas.config(cursor=_CUR_DRAW)
        elif self._handle_at(e.x, e.y):
            self.canvas.config(cursor=_CUR_RESIZE)
        elif self._inside_bbox(e.x, e.y):
            self.canvas.config(cursor=_CUR_MOVE)
        else:
            self.canvas.config(cursor=_CUR_DRAW)

    def _on_press(self, e):
        if not self._pil_img:
            return
        self._drag_cx, self._drag_cy = e.x, e.y
        h = self._handle_at(e.x, e.y)
        if h:
            self._mode = f"resize_{h}"
            self._drag_bx1, self._drag_by1 = self._bx1, self._by1
            self._drag_bx2, self._drag_by2 = self._bx2, self._by2
            return
        if self._inside_bbox(e.x, e.y):
            self._mode = "move"
            self._drag_bx1, self._drag_by1 = self._bx1, self._by1
            self._drag_bx2, self._drag_by2 = self._bx2, self._by2
            return
        self._mode = "draw"
        self._bx1 = self._by1 = self._bx2 = self._by2 = None
        self._result_color = ACCENT
        self._draw_start = self._c2i(e.x, e.y)
        self._redraw_bbox()
        self._reset_result()

    def _on_drag(self, e):
        if not self._pil_img:
            return
        dx_i = (e.x - self._drag_cx) / self._img_scale if self._img_scale else 0
        dy_i = (e.y - self._drag_cy) / self._img_scale if self._img_scale else 0

        if self._mode == "draw" and self._draw_start:
            ix, iy = self._c2i(e.x, e.y)
            sx, sy = self._draw_start
            self._bx1, self._by1 = min(sx,ix), min(sy,iy)
            self._bx2, self._by2 = max(sx,ix), max(sy,iy)
            self._redraw_bbox()

        elif self._mode == "move":
            iw = float(self._pil_img.width)
            ih = float(self._pil_img.height)
            w  = self._drag_bx2 - self._drag_bx1
            h  = self._drag_by2 - self._drag_by1
            nx1 = max(0.0, min(iw-w, self._drag_bx1 + dx_i))
            ny1 = max(0.0, min(ih-h, self._drag_by1 + dy_i))
            self._bx1, self._by1 = nx1, ny1
            self._bx2, self._by2 = nx1+w, ny1+h
            self._redraw_bbox()

        elif self._mode.startswith("resize_"):
            n  = self._mode[7:]
            iw = float(self._pil_img.width)
            ih = float(self._pil_img.height)
            x1, y1 = self._drag_bx1, self._drag_by1
            x2, y2 = self._drag_bx2, self._drag_by2
            ix, iy = self._c2i(e.x, e.y)
            if   n == "nw": x1, y1 = ix, iy
            elif n == "n":  y1 = iy
            elif n == "ne": x2, y1 = ix, iy
            elif n == "e":  x2 = ix
            elif n == "se": x2, y2 = ix, iy
            elif n == "s":  y2 = iy
            elif n == "sw": x1, y2 = ix, iy
            elif n == "w":  x1 = ix
            x1 = max(0.0, min(x1, iw)); y1 = max(0.0, min(y1, ih))
            x2 = max(0.0, min(x2, iw)); y2 = max(0.0, min(y2, ih))
            self._bx1, self._by1 = min(x1,x2), min(y1,y2)
            self._bx2, self._by2 = max(x1,x2), max(y1,y2)
            self._redraw_bbox()

    def _on_release(self, e):
        if not self._pil_img or not self._has_bbox():
            return
        self._mode = "draw"
        if self._bx2 - self._bx1 < 5 or self._by2 - self._by1 < 5:
            self._clear_box()
            return
        self._run()

    def _clear_box(self, _=None):
        self._bx1 = self._by1 = self._bx2 = self._by2 = None
        self._draw_start  = None
        self._mode        = "draw"
        self._result_color = ACCENT
        if self._rect_id:
            self.canvas.delete(self._rect_id)
            self._rect_id = None
        for hid in self._handle_ids:
            self.canvas.delete(hid)
        self._handle_ids = []
        self.lbl_coords.config(text="—")
        self.canvas.config(cursor=_CUR_DRAW)
        self._reset_result()

    def _update_coords(self):
        if not self._has_bbox():
            return
        self.lbl_coords.config(
            text=(f"({int(self._bx1)}, {int(self._by1)})  →  "
                  f"({int(self._bx2)}, {int(self._by2)})\n"
                  f"size: {int(self._bx2-self._bx1)}×"
                  f"{int(self._by2-self._by1)} px"))

    def _reset_result(self):
        self.lbl_result.config(text="—", fg=DIM)
        self.lbl_conf_disp.config(text="")
        self.lbl_detail.config(text="")
        self.prev_cv.delete("all")
        self._prev_hint = self.prev_cv.create_text(
            130, 80, text="Vùng cắt hiện ở đây",
            fill=DIM, font=("Segoe UI", 9))
        self._crop_pil = None

    # ════════════════════════════════════════════════════════ INFERENCE ══

    def _run(self, _=None):
        if not self._pil_img:
            self._log_msg("⚠ Chưa tải ảnh")
            return
        if not self._has_bbox():
            self._log_msg("⚠ Chưa vẽ vùng chọn")
            return
        if not self._model:
            self._log_msg("⚠ Chưa tải model — chọn detect.pt trước")
            return

        x1, y1 = int(self._bx1), int(self._by1)
        x2, y2 = int(self._bx2), int(self._by2)
        crop = self._pil_img.crop((x1, y1, x2, y2))
        self._crop_pil = crop
        self._show_preview(crop)

        conf  = self.v_conf.get()
        model = self._model
        task  = self._model_task
        names = self._model_names

        def _infer():
            try:
                lbl, c, detail = _do_infer(model, task, names, crop, conf)
                self.after(0, lambda: self._apply_result(lbl, c, detail))
            except Exception as ex:
                msg = str(ex)
                self.after(0, lambda: self._log_msg(f"✘ Lỗi predict: {msg}"))

        threading.Thread(target=_infer, daemon=True).start()

    def _show_preview(self, crop):
        if not _PIL_OK:
            return
        prev = crop.copy()
        prev.thumbnail((260, 160), Image.LANCZOS)
        tk_img = ImageTk.PhotoImage(prev)
        self.prev_cv.delete("all")
        pw = self.prev_cv.winfo_width() or 260
        ph = self.prev_cv.winfo_height() or 160
        self.prev_cv.create_image(pw//2, ph//2, anchor=CENTER, image=tk_img)
        self._prev_tk = tk_img

    def _apply_result(self, label, confidence, detail):
        ll = label.lower().replace("-", "_")
        if any(k in ll for k in EMPTY_KW):
            display, color = "🟢  TRỐNG", C_EMPTY
        elif any(k in ll for k in OCCUPIED_KW):
            display, color = "🔴  CÓ XE", C_OCCUPIED
        else:
            display, color = f"🔵  {label.upper()}", C_UNKNOWN

        self._result_color = color
        self.lbl_result.config(text=display, fg=color)
        self.lbl_conf_disp.config(
            text=f"Độ tin cậy: {confidence:.1%}", fg=TEXT)
        self.lbl_detail.config(text=detail[:160], fg=DIM)

        if self._rect_id:
            self.canvas.itemconfig(self._rect_id, outline=color, width=3)
        for hid in self._handle_ids:
            self.canvas.itemconfig(hid, fill=color)

        self._log_msg(f"✔ {display.strip()}  conf={confidence:.1%}  [{label}]")

    # ════════════════════════════════════════════════════════════ ZOOM ══

    def _zoom_image(self, _=None):
        _zoom(self, self._pil_img, "Phóng to ảnh gốc")

    def _zoom_crop(self, _=None):
        _zoom(self, self._crop_pil, "Phóng to vùng chọn")

    # ═══════════════════════════════════════════════════════════════ LOG ══

    def _log_msg(self, msg):
        self._log.config(state=NORMAL)
        self._log.insert(END, msg + "\n")
        self._log.see(END)
        self._log.config(state=DISABLED)


# ══════════════════════════════════════════════════════════ Inference fn ══

def _do_infer(model, task, names, crop_pil, conf_thresh):
    """Standalone inference. Returns (label, confidence, detail_str)."""
    import torch
    import numpy as np

    if task == "yolo5_pkg":
        results = model(crop_pil, size=640, augment=False)
        det = results.xyxy[0].cpu().numpy()
        if len(det) == 0:
            return "empty", 1.0, "Không phát hiện → TRỐNG"
        best = det[det[:, 4].argmax()]
        lbl  = names.get(int(best[5]), str(int(best[5])))
        return lbl, float(best[4]), "\n".join(
            f"{names.get(int(d[5]),int(d[5]))}: {d[4]:.3f}" for d in det)

    if task.startswith("yolo8/"):
        results = model(crop_pil, verbose=False, conf=conf_thresh)
        r = results[0]
        t = task.split("/")[1]
        if t == "classify":
            probs = r.probs
            top1 = int(probs.top1)
            lbl = names.get(top1, str(top1))
            detail = "\n".join(
                f"{names.get(i,i)}: {p:.3f}"
                for i, p in enumerate(probs.data.tolist()[:6])
            ) if hasattr(probs, "data") else ""
            return lbl, float(probs.top1conf), detail
        else:
            boxes = r.boxes
            if boxes is None or len(boxes) == 0:
                return "empty", 1.0, "Không phát hiện → TRỐNG"
            confs = boxes.conf.tolist()
            clss  = boxes.cls.tolist()
            best  = max(range(len(confs)), key=lambda i: confs[i])
            lbl   = names.get(int(clss[best]), str(int(clss[best])))
            return lbl, confs[best], "\n".join(
                f"{names.get(int(clss[i]),int(clss[i]))}: {confs[i]:.3f}"
                for i in range(len(confs)))

    if task == "yolo5_hub":
        results = model(crop_pil, size=640, augment=False)
        det = results.xyxy[0].cpu().numpy()
        if len(det) == 0:
            return "empty", 1.0, "Không phát hiện → TRỐNG"
        best = det[det[:, 4].argmax()]
        return (names.get(int(best[5]), str(int(best[5]))), float(best[4]),
                "\n".join(
                    f"{names.get(int(d[5]),int(d[5]))}: {d[4]:.3f}"
                    for d in det))

    if task == "yolo5_raw":
        size = 640
        img  = crop_pil.resize((size, size), Image.BILINEAR)
        arr  = np.array(img, dtype=np.float32) / 255.0
        ten  = torch.from_numpy(arr.transpose(2, 0, 1)).unsqueeze(0)
        model.eval()
        with torch.no_grad():
            pred = model(ten)
        if isinstance(pred, (list, tuple)):
            pred = pred[0]
        pred = pred.squeeze(0)
        nc  = max(1, pred.shape[1] - 5)
        obj = torch.sigmoid(pred[:, 4])
        cls_sc = torch.sigmoid(pred[:, 5:]) if pred.shape[1] > 5 \
                 else torch.ones(len(pred), 1)
        combined  = obj.unsqueeze(1) * cls_sc
        max_score = float(combined.max())
        if max_score < conf_thresh:
            return "empty", 1.0 - max_score, "Score thấp → TRỐNG"
        flat  = int(combined.argmax())
        c_idx = flat % nc
        lbl   = names.get(c_idx, str(c_idx)) if names else str(c_idx)
        return lbl, max_score, f"class {c_idx}: {max_score:.3f}"

    return "unknown", 0.0, f"task không rõ: {task}"


# ════════════════════════════════════════════════════════════ Entry point ══

if __name__ == "__main__":
    if not _PIL_OK:
        print("[WARN] Pillow chưa cài: pip install Pillow")
    if not _TORCH_OK:
        print("[WARN] PyTorch chưa cài: pip install torch")

    app = SlotDetectApp()
    app.mainloop()
