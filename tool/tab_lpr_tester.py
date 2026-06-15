"""Tab kiểm thử LPR — nhận dạng biển số qua HTTP API (REST /read-plate)."""

import csv
import os
import shutil
import threading
from io import BytesIO
from tkinter import *
from tkinter import ttk, filedialog, messagebox

try:
    import requests
    _REQ_OK = True
except ImportError:
    _REQ_OK = False

try:
    from PIL import Image, ImageTk
    _PIL_OK = True
except ImportError:
    _PIL_OK = False

from .constants import BG, CARD, ACCENT, ACCENT2, TEXT, DIM, SUCCESS, F_MAIN, F_BOLD, F_MONO
from .settings import (
    _bind_cfg, _bind_history, _push_history, _get_history,
    _cfg_dir, _cfg_save, _CFG,
)
from .ui_helpers import _make_logbox, _append_log, _zoom_image_window, _action_btn

_IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".tif", ".webp"}
_LPR_TYPES = ["HTTP REST API (/read-plate)", "Kztek LPR AI Server", "OpenALPR (OpenAlpr)"]


def _parse_lpr_response(raw) -> dict:
    """Parse JSON trả về từ nhiều kiểu API LPR khác nhau.

    Trả về dict chuẩn hoá:
        plate, original, confidence, vehicle_type, bbox, lpr_image_b64
    """
    result = {
        "plate": "", "original": "", "confidence": 0.0,
        "vehicle_type": "", "bbox": None, "lpr_image_b64": None,
    }
    if isinstance(raw, list):
        raw = raw[0] if raw else {}
    if not isinstance(raw, dict):
        return result

    # Plate number
    for k in ("plate", "PlateNumber", "license_plate", "licensePlate",
              "plate_number", "plateNumber", "number_plate", "text"):
        if raw.get(k):
            result["plate"] = str(raw[k]).strip()
            break
    # Nested results list (OpenALPR style)
    if not result["plate"]:
        for k in ("results", "candidates"):
            sub = raw.get(k)
            if isinstance(sub, list) and sub:
                result["plate"] = str(sub[0].get("plate", "")).strip()
                break

    # Original / raw plate
    for k in ("original", "OriginalPlate", "original_plate", "originalPlate", "raw_plate"):
        if raw.get(k):
            result["original"] = str(raw[k]).strip()
            break

    # Confidence
    for k in ("confidence", "Confidence", "score", "Score", "prob"):
        if k in raw:
            try:
                v = float(raw[k])
                result["confidence"] = v / 100 if v > 1 else v
            except Exception:
                pass
            break

    # Vehicle type
    for k in ("vehicle_type", "VehicleType", "vehicleType", "vehicle", "type", "class"):
        if raw.get(k):
            result["vehicle_type"] = str(raw[k]).strip()
            break

    # Bounding box
    for k in ("bbox", "BoundingBox", "bounding_box", "box", "region"):
        if raw.get(k):
            result["bbox"] = raw[k]
            break

    # LPR crop (base64)
    for k in ("lpr_image", "LprImage", "plate_image", "plateImage",
              "image_base64", "plate_crop"):
        if raw.get(k):
            result["lpr_image_b64"] = raw[k]
            break

    return result


class LprTesterTab(Frame):
    """Tab kiểm thử LPR — test ảnh đơn hoặc toàn bộ thư mục."""

    def __init__(self, master, root):
        super().__init__(master, bg=BG)
        self.root = root
        self._cancel = False
        self._pil_single = None      # PIL Image ảnh đơn đang load
        self._pil_lpr_single = None  # PIL Image ảnh biển cắt (single test)
        self._folder_lpr = {}        # iid → PIL Image biển cắt (folder results)
        self._build()

    # ═══════════════════════════ BUILD UI ══════════════════════════════════

    def _build(self):
        self._build_config_strip()

        pw = PanedWindow(self, orient=HORIZONTAL, bg=DIM,
                         sashwidth=5, sashrelief="flat", relief="flat")
        pw.pack(fill=BOTH, expand=True, padx=8, pady=4)

        left = Frame(pw, bg=BG)
        right = Frame(pw, bg=BG)
        pw.add(left, minsize=360)
        pw.add(right, minsize=440)

        self._build_single(left)
        self._build_folder(right)

        log_wrap = Frame(self, bg=CARD, pady=2)
        log_wrap.pack(fill=X, padx=8, pady=(0, 6))
        Label(log_wrap, text="Log", bg=CARD, fg=DIM, font=F_BOLD, padx=8).pack(anchor=W)
        lf, self._log = _make_logbox(log_wrap)
        lf.pack(fill=X, padx=8, pady=(0, 4))

    # ── Config strip ──────────────────────────────────────────────────────

    def _build_config_strip(self):
        strip = Frame(self, bg=CARD, padx=10, pady=6)
        strip.pack(fill=X, padx=8, pady=(6, 2))

        Label(strip, text="Loại LPR:", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        self._type_var = StringVar(value=_LPR_TYPES[0])
        _bind_cfg("lpr.type", self._type_var)
        type_cb = ttk.Combobox(strip, textvariable=self._type_var, width=28,
                                style="Dark.TCombobox", values=_LPR_TYPES, state="readonly")
        type_cb.pack(side=LEFT, padx=(4, 14))
        type_cb.bind("<<ComboboxSelected>>", self._on_type_change)

        Label(strip, text="URL:", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        self._url_var = StringVar(value="http://localhost:8000/read-plate")
        self._url_cb = ttk.Combobox(strip, textvariable=self._url_var, width=42,
                                     style="Dark.TCombobox", font=F_MAIN)
        self._url_cb.pack(side=LEFT, padx=(4, 14))
        _bind_history("h.lpr.url", self._url_cb)

        Label(strip, text="Timeout:", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        self._timeout_var = IntVar(value=10)
        _bind_cfg("lpr.timeout", self._timeout_var)
        Spinbox(strip, from_=1, to=120, textvariable=self._timeout_var, width=5,
                bg=CARD, fg=TEXT, insertbackground=TEXT, buttonbackground=ACCENT2,
                relief="flat", font=F_MAIN).pack(side=LEFT, padx=(4, 2))
        Label(strip, text="s", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT, padx=(0, 14))

        Button(strip, text="🔌 Test kết nối", command=self._test_connection,
               bg=ACCENT2, fg="white", activebackground=ACCENT, activeforeground="white",
               font=F_MAIN, relief="flat", padx=10, cursor="hand2").pack(side=LEFT, padx=(0, 8))

        self._conn_var = StringVar(value="Chưa kiểm tra")
        self._conn_lbl = Label(strip, textvariable=self._conn_var,
                                bg=CARD, fg=DIM, font=F_MAIN, width=22, anchor=W)
        self._conn_lbl.pack(side=LEFT)

    # ── Single image pane (left) ──────────────────────────────────────────

    def _build_single(self, parent):
        Label(parent, text="Test ảnh đơn", bg=BG, fg=ACCENT,
              font=F_BOLD).pack(anchor=W, padx=8, pady=(6, 2))

        # Image preview box
        pic_frame = Frame(parent, bg=CARD, height=220)
        pic_frame.pack(fill=X, padx=8, pady=(2, 2))
        pic_frame.pack_propagate(False)
        self._pic_vehicle = Label(pic_frame, bg=CARD, fg=DIM, font=F_MAIN,
                                   text="(click để tải ảnh — double-click để phóng to)",
                                   cursor="hand2", wraplength=340)
        self._pic_vehicle.pack(fill=BOTH, expand=True)
        self._pic_vehicle.bind("<Button-1>",        lambda e: self._load_image())
        self._pic_vehicle.bind("<Double-Button-1>", lambda e: self._zoom_single())

        self._img_name_lbl = Label(parent, text="", bg=BG, fg=DIM,
                                    font=F_MONO, wraplength=360, anchor=CENTER)
        self._img_name_lbl.pack()

        # Buttons + options
        btn_row = Frame(parent, bg=BG)
        btn_row.pack(fill=X, padx=8, pady=(4, 2))
        _action_btn(btn_row, "📂 Load ảnh (Ctrl+O)", self._load_image,
                    ACCENT2, padx=10, pady=4).pack(side=LEFT, padx=(0, 8))
        self._btn_detect = _action_btn(btn_row, "🔍 Nhận dạng (F5)",
                                        self._detect_single, ACCENT, padx=10, pady=4)
        self._btn_detect.pack(side=LEFT)

        opt = Frame(parent, bg=BG)
        opt.pack(fill=X, padx=8, pady=2)
        self._is_car_var = BooleanVar(value=True)
        _bind_cfg("lpr.is_car", self._is_car_var)
        Checkbutton(opt, text="Loại xe ô tô", variable=self._is_car_var,
                    bg=BG, fg=TEXT, selectcolor=CARD, activebackground=BG,
                    font=F_MAIN).pack(side=LEFT, padx=(0, 14))
        Label(opt, text="Xoay (°):", bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT)
        self._rotate_var = IntVar(value=0)
        _bind_cfg("lpr.rotate", self._rotate_var)
        Spinbox(opt, from_=0, to=360, textvariable=self._rotate_var, width=5,
                bg=CARD, fg=TEXT, insertbackground=TEXT, buttonbackground=ACCENT2,
                relief="flat", font=F_MAIN).pack(side=LEFT, padx=4)

        # Result fields
        res = Frame(parent, bg=CARD, padx=10, pady=8)
        res.pack(fill=X, padx=8, pady=(4, 2))
        self._res_vars = {}
        for label, key in [
            ("Biển số",    "plate"),
            ("Biển gốc",   "original"),
            ("Loại xe",    "vehicle_type"),
            ("Confidence", "confidence"),
            ("Thời gian",  "elapsed_ms"),
            ("Bounding box", "bbox"),
        ]:
            row = Frame(res, bg=CARD)
            row.pack(fill=X, pady=1)
            Label(row, text=f"{label}:", bg=CARD, fg=DIM,
                  font=F_MAIN, width=13, anchor=W).pack(side=LEFT)
            v = StringVar(value="-")
            Entry(row, textvariable=v, bg=CARD, fg=TEXT,
                  insertbackground=TEXT, relief="flat", font=F_MONO,
                  state="readonly", readonlybackground=CARD).pack(side=LEFT, fill=X, expand=True)
            self._res_vars[key] = v

        # LPR crop image
        lpr_wrap = Frame(parent, bg=CARD)
        lpr_wrap.pack(fill=X, padx=8, pady=(2, 6))
        Label(lpr_wrap, text="Ảnh biển cắt (double-click để zoom):",
              bg=CARD, fg=DIM, font=F_MAIN).pack(anchor=W, padx=4, pady=(4, 0))
        self._pic_lpr = Label(lpr_wrap, bg=CARD, fg=DIM, font=F_MAIN,
                               text="(chưa nhận dạng)", height=4, cursor="hand2")
        self._pic_lpr.pack(fill=X, padx=4, pady=4)
        self._pic_lpr.bind("<Double-Button-1>", lambda e: _zoom_image_window(
            self.root, self._pil_lpr_single, "Ảnh biển số"))

    # ── Folder batch pane (right) ─────────────────────────────────────────

    def _build_folder(self, parent):
        Label(parent, text="Test thư mục", bg=BG, fg=ACCENT,
              font=F_BOLD).pack(anchor=W, padx=8, pady=(6, 2))

        # Folder row
        fr = Frame(parent, bg=BG)
        fr.pack(fill=X, padx=8, pady=2)
        self._folder_var = StringVar()
        _bind_cfg("lpr.folder", self._folder_var)
        self._folder_cb = ttk.Combobox(fr, textvariable=self._folder_var,
                                        style="Dark.TCombobox", font=F_MAIN)
        self._folder_cb.pack(side=LEFT, fill=X, expand=True, padx=(0, 4))
        _bind_history("h.lpr.folder", self._folder_cb)
        Button(fr, text="Chọn…", command=self._browse_folder,
               bg=ACCENT2, fg="white", activebackground=ACCENT, activeforeground="white",
               font=F_MAIN, relief="flat", padx=8, cursor="hand2").pack(side=LEFT, padx=(0, 4))
        Button(fr, text="📂", command=self._open_folder,
               bg=CARD, fg=TEXT, activebackground=ACCENT2, activeforeground="white",
               font=F_MAIN, relief="flat", padx=6, cursor="hand2").pack(side=LEFT)

        # Options row
        opt = Frame(parent, bg=BG)
        opt.pack(fill=X, padx=8, pady=2)
        self._subfolder_var = BooleanVar(value=False)
        _bind_cfg("lpr.subfolder", self._subfolder_var)
        Checkbutton(opt, text="Bao gồm thư mục con", variable=self._subfolder_var,
                    bg=BG, fg=TEXT, selectcolor=CARD, activebackground=BG,
                    font=F_MAIN).pack(side=LEFT, padx=(0, 12))
        self._f_is_car_var = BooleanVar(value=True)
        _bind_cfg("lpr.f_is_car", self._f_is_car_var)
        Checkbutton(opt, text="Loại xe ô tô", variable=self._f_is_car_var,
                    bg=BG, fg=TEXT, selectcolor=CARD, activebackground=BG,
                    font=F_MAIN).pack(side=LEFT, padx=(0, 12))
        Label(opt, text="Xoay:", bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT)
        self._f_rotate_var = IntVar(value=0)
        _bind_cfg("lpr.f_rotate", self._f_rotate_var)
        Spinbox(opt, from_=0, to=360, textvariable=self._f_rotate_var, width=5,
                bg=CARD, fg=TEXT, insertbackground=TEXT, buttonbackground=ACCENT2,
                relief="flat", font=F_MAIN).pack(side=LEFT, padx=(4, 12))
        Label(opt, text="Luồng:", bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT)
        self._workers_var = IntVar(value=1)
        _bind_cfg("lpr.workers", self._workers_var)
        Spinbox(opt, from_=1, to=8, textvariable=self._workers_var, width=4,
                bg=CARD, fg=TEXT, insertbackground=TEXT, buttonbackground=ACCENT2,
                relief="flat", font=F_MAIN).pack(side=LEFT, padx=4)

        # Action buttons
        btn_row = Frame(parent, bg=BG)
        btn_row.pack(fill=X, padx=8, pady=(4, 2))
        self._btn_start = _action_btn(btn_row, "▶ Test thư mục (F5)",
                                       self._start, ACCENT, padx=10, pady=4)
        self._btn_start.pack(side=LEFT, padx=(0, 8))
        self._btn_stop = _action_btn(btn_row, "■ Dừng (Esc)",
                                      self._stop, "#555", padx=10, pady=4)
        self._btn_stop.pack(side=LEFT, padx=(0, 8))
        self._btn_stop.config(state=DISABLED)
        _action_btn(btn_row, "↻ Retry lỗi", self._retry_failed,
                    ACCENT2, padx=8, pady=4).pack(side=LEFT, padx=(0, 8))
        _action_btn(btn_row, "💾 Xuất CSV (Ctrl+S)", self._export,
                    ACCENT2, padx=8, pady=4).pack(side=LEFT)

        # Progress + stats
        pg = Frame(parent, bg=BG)
        pg.pack(fill=X, padx=8, pady=2)
        self._prog_lbl = Label(pg, text="Sẵn sàng", bg=BG, fg=DIM, font=F_MAIN, anchor=W)
        self._prog_lbl.pack(fill=X)
        self._pb = ttk.Progressbar(pg, style="K.Horizontal.TProgressbar",
                                    maximum=100, value=0)
        self._pb.pack(fill=X, pady=(2, 2))
        self._stats_lbl = Label(pg, text="", bg=BG, fg=SUCCESS, font=F_MAIN, anchor=W)
        self._stats_lbl.pack(fill=X)

        # Results Treeview
        tv_frame = Frame(parent, bg=BG)
        tv_frame.pack(fill=BOTH, expand=True, padx=8, pady=(2, 2))
        cols = ("#", "Tên file", "Biển số", "Biển gốc", "Loại xe", "ms", "Trạng thái")
        self._tree = ttk.Treeview(tv_frame, columns=cols, show="headings",
                                   style="Dark.Treeview", selectmode="browse")
        for col, w in zip(cols, [38, 200, 120, 110, 90, 68, 110]):
            self._tree.heading(col, text=col)
            self._tree.column(col, width=w, minwidth=30,
                               stretch=(col in ("Tên file", "Trạng thái")))
        vsb = ttk.Scrollbar(tv_frame, orient=VERTICAL,   command=self._tree.yview)
        hsb = ttk.Scrollbar(tv_frame, orient=HORIZONTAL, command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side=RIGHT, fill=Y)
        hsb.pack(side=BOTTOM, fill=X)
        self._tree.pack(fill=BOTH, expand=True)
        self._tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self._tree.bind("<Double-Button-1>",  self._on_tree_dbl)

        # Preview row
        pv = Frame(parent, bg=CARD)
        pv.pack(fill=X, padx=8, pady=(2, 2))
        self._prev_lbl = Label(pv, text="(chọn dòng trong bảng để xem ảnh)",
                                bg=CARD, fg=DIM, font=F_MONO)
        self._prev_lbl.pack(anchor=W, padx=6, pady=(4, 2))

        img_row = Frame(pv, bg=CARD)
        img_row.pack(fill=X, padx=6, pady=(0, 4))
        self._pic_fv = Label(img_row, bg=CARD, fg=DIM, text="(ảnh xe)",
                              font=F_MAIN, height=8, width=30, cursor="hand2")
        self._pic_fv.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 4))
        self._pic_fv.bind("<Double-Button-1>", lambda e: self._zoom_fv())
        self._pic_fp = Label(img_row, bg=CARD, fg=DIM, text="(biển số)",
                              font=F_MAIN, height=8, width=18, cursor="hand2")
        self._pic_fp.pack(side=LEFT, fill=BOTH, expand=True)
        self._pic_fp.bind("<Double-Button-1>", lambda e: self._zoom_fp())

        # GT buttons
        gt = Frame(pv, bg=CARD)
        gt.pack(fill=X, padx=6, pady=(0, 6))
        self._btn_ok = Button(gt, text="✓ Đúng", command=self._save_correct,
                               bg="#2d6a2d", fg="white", activebackground=SUCCESS,
                               activeforeground="white", font=F_MAIN,
                               relief="flat", padx=12, pady=4, cursor="hand2", state=DISABLED)
        self._btn_ok.pack(side=LEFT, padx=(0, 8))
        self._btn_wrong = Button(gt, text="✗ Sai", command=self._save_wrong,
                                  bg="#6a2d2d", fg="white", activebackground="#f05050",
                                  activeforeground="white", font=F_MAIN,
                                  relief="flat", padx=12, pady=4, cursor="hand2", state=DISABLED)
        self._btn_wrong.pack(side=LEFT, padx=(0, 12))
        Label(gt, text="Lưu ảnh vào _gt/dung hoặc _gt/sai",
              bg=CARD, fg=DIM, font=("Segoe UI", 8)).pack(side=LEFT)

    # ═══════════════════════════ CONFIG ACTIONS ═══════════════════════════

    def _on_type_change(self, _=None):
        t = self._type_var.get()
        curr = self._url_var.get()
        if "HTTP REST" in t and "localhost:8000" not in curr:
            self._url_var.set("http://localhost:8000/read-plate")
        elif "Kztek" in t and "localhost:8000" in curr:
            self._url_var.set("http://localhost:5001/api/lpr/detect")
        elif "OpenALPR" in t and "localhost:8000" in curr:
            self._url_var.set("http://localhost:8080/v2/recognize")

    def _test_connection(self):
        if not _REQ_OK:
            messagebox.showerror("Lỗi", "Thư viện 'requests' chưa cài.\npip install requests")
            return
        url = self._url_var.get().strip()
        if not url:
            messagebox.showwarning("Thông báo", "Vui lòng nhập URL.")
            return
        self._conn_var.set("Đang kiểm tra...")
        self._conn_lbl.config(fg="#f0c040")

        def _chk():
            # Probe the base host with a GET / HEAD
            try:
                parts = url.split("/")
                base = "/".join(parts[:3])          # scheme://host:port
                r = requests.head(base, timeout=self._timeout_var.get())
                ok = r.status_code < 500
            except Exception:
                try:
                    r = requests.get(base, timeout=self._timeout_var.get())
                    ok = r.status_code < 500
                except Exception:
                    ok = False

            def _upd():
                if ok:
                    self._conn_var.set("✔ Server sẵn sàng")
                    self._conn_lbl.config(fg=SUCCESS)
                    _append_log(self._log, f"✔ Kết nối OK — {url}")
                else:
                    self._conn_var.set("✗ Không phản hồi")
                    self._conn_lbl.config(fg="#f05050")
                    _append_log(self._log, f"[LỖI] Kết nối thất bại — {url}")
            self.root.after(0, _upd)

        threading.Thread(target=_chk, daemon=True).start()

    # ═══════════════════════════ SINGLE IMAGE ═════════════════════════════

    def _load_image(self, _=None):
        if not _PIL_OK:
            messagebox.showerror("Lỗi", "Pillow chưa cài.\npip install Pillow")
            return
        path = filedialog.askopenfilename(
            title="Chọn ảnh xe",
            initialdir=_CFG.get("lpr.last_dir", "") or None,
            filetypes=[("Ảnh", "*.jpg *.jpeg *.png *.bmp *.webp *.gif *.tiff"),
                       ("Tất cả", "*.*")],
        )
        if not path:
            return
        _CFG["lpr.last_dir"] = os.path.dirname(path)
        _cfg_save()
        try:
            img = Image.open(path)
            self._pil_single = img.copy()
            img.close()
            self._show_img(self._pic_vehicle, self._pil_single, 360, 210)
            self._img_name_lbl.config(text=os.path.basename(path))
            self._clear_single_result()
            _append_log(self._log, f"✔ Đã tải: {path}")
        except Exception as ex:
            _append_log(self._log, f"[LỖI] Không tải được ảnh: {ex}")

    def _detect_single(self):
        if not _REQ_OK:
            messagebox.showerror("Lỗi", "Thư viện 'requests' chưa cài.")
            return
        if self._pil_single is None:
            messagebox.showwarning("Thông báo", "Chưa tải ảnh. Nhấn Load ảnh trước.")
            return
        url = self._url_var.get().strip()
        if not url:
            messagebox.showwarning("Thông báo", "Chưa nhập URL server.")
            return

        self._btn_detect.config(state=DISABLED, text="Đang nhận dạng...")
        self._clear_single_result()
        _append_log(self._log, f"⠿ Gửi ảnh → {url} ...")

        pil_copy = self._pil_single.copy()
        timeout = self._timeout_var.get()
        lpr_type = self._type_var.get()

        def _run():
            import time
            t0 = time.time()
            result, err = _api_call_pil(pil_copy, url, timeout, lpr_type)
            elapsed = int((time.time() - t0) * 1000)
            pil_copy.close()

            def _upd():
                self._btn_detect.config(state=NORMAL, text="🔍 Nhận dạng (F5)")
                if err:
                    _append_log(self._log, f"[LỖI] {err}")
                    return
                plate = result.get("plate", "")
                self._res_vars["plate"].set(plate or "(không nhận dạng)")
                self._res_vars["original"].set(result.get("original") or "-")
                self._res_vars["vehicle_type"].set(result.get("vehicle_type") or "-")
                conf = result.get("confidence", 0)
                self._res_vars["confidence"].set(f"{conf:.1%}" if conf else "-")
                self._res_vars["elapsed_ms"].set(f"{elapsed} ms")
                bbox = result.get("bbox")
                self._res_vars["bbox"].set(_fmt_bbox(bbox))

                # LPR crop
                b64 = result.get("lpr_image_b64")
                if b64 and _PIL_OK:
                    try:
                        import base64
                        self._pil_lpr_single = Image.open(BytesIO(base64.b64decode(b64)))
                        self._show_img(self._pic_lpr, self._pil_lpr_single, 360, 80)
                    except Exception:
                        pass

                _append_log(self._log,
                    f'✔ Biển số: "{plate}" | {elapsed}ms'
                    + (f" | Conf: {conf:.1%}" if conf else ""))
            self.root.after(0, _upd)

        threading.Thread(target=_run, daemon=True).start()

    def _clear_single_result(self):
        for v in self._res_vars.values():
            v.set("-")
        self._pic_lpr.config(image="", text="(chưa nhận dạng)")
        self._pil_lpr_single = None

    def _zoom_single(self):
        _zoom_image_window(self.root, self._pil_single, "Ảnh xe")

    # ═══════════════════════════ FOLDER BATCH ═════════════════════════════

    def _browse_folder(self):
        p = filedialog.askdirectory(
            title="Chọn thư mục ảnh",
            initialdir=self._folder_var.get() or _cfg_dir("lpr.folder") or None,
        )
        if p:
            self._folder_var.set(p)
            _push_history("h.lpr.folder", p)
            self._folder_cb["values"] = _get_history("h.lpr.folder")

    def _open_folder(self):
        p = self._folder_var.get().strip()
        if p and os.path.isdir(p):
            os.startfile(p)

    def _start(self):
        if not _REQ_OK:
            messagebox.showerror("Lỗi", "Thư viện 'requests' chưa cài.")
            return
        folder = self._folder_var.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showwarning("Thông báo", "Thư mục không hợp lệ.")
            return
        url = self._url_var.get().strip()
        if not url:
            messagebox.showwarning("Thông báo", "Chưa nhập URL server.")
            return

        # Reset
        self._cancel = False
        for pil in self._folder_lpr.values():
            try: pil.close()
            except Exception: pass
        self._folder_lpr.clear()
        self._tree.delete(*self._tree.get_children())
        self._clear_fpreview()
        self._btn_start.config(state=DISABLED)
        self._btn_stop.config(state=NORMAL)
        self._pb.config(value=0)

        threading.Thread(
            target=self._run_folder_worker,
            args=(folder, url, self._timeout_var.get(), self._type_var.get(),
                  self._subfolder_var.get()),
            daemon=True,
        ).start()

    def _stop(self):
        self._cancel = True
        _append_log(self._log, "⚠ Đang dừng...")

    def _run_folder_worker(self, folder, url, timeout, lpr_type, include_sub):
        import time

        if include_sub:
            files = []
            for rt, _, fnames in os.walk(folder):
                for f in fnames:
                    if os.path.splitext(f)[1].lower() in _IMG_EXTS:
                        files.append(os.path.join(rt, f))
        else:
            files = [
                os.path.join(folder, f) for f in os.listdir(folder)
                if os.path.splitext(f)[1].lower() in _IMG_EXTS
            ]
        files.sort()
        total = len(files)

        if total == 0:
            self.root.after(0, lambda: (
                _append_log(self._log, "⚠ Không tìm thấy ảnh nào."),
                self._btn_start.config(state=NORMAL),
                self._btn_stop.config(state=DISABLED),
            ))
            return

        self.root.after(0, lambda: (
            self._pb.config(maximum=total),
            _append_log(self._log, f"⠿ Bắt đầu: {total} ảnh | {url}"),
        ))

        ok_n = fail_n = 0
        total_ms = 0

        for i, fpath in enumerate(files):
            if self._cancel:
                break
            fname = os.path.relpath(fpath, folder) if include_sub else os.path.basename(fpath)
            t0 = time.time()
            try:
                result, err = _api_call_file(fpath, url, timeout, lpr_type)
                elapsed = int((time.time() - t0) * 1000)
                if err:
                    plate = orig = vtype = ""
                    status = f"Lỗi: {err}"
                    fail_n += 1
                    lpr_pil = None
                else:
                    plate = result.get("plate", "")
                    orig  = result.get("original", "")
                    vtype = result.get("vehicle_type", "")
                    status = "OK" if plate else "Không nhận dạng"
                    if plate:
                        ok_n += 1
                    else:
                        fail_n += 1
                    lpr_pil = None
                    b64 = result.get("lpr_image_b64")
                    if b64 and _PIL_OK:
                        try:
                            import base64
                            lpr_pil = Image.open(BytesIO(base64.b64decode(b64)))
                        except Exception:
                            pass
                total_ms += elapsed
            except Exception as ex:
                elapsed = 0
                plate = orig = vtype = ""
                status = f"Lỗi: {ex}"
                fail_n += 1
                lpr_pil = None

            # Closure-safe copies
            _i, _f, _pl, _or, _vt = i + 1, fname, plate, orig, vtype
            _ms, _st, _lpi = elapsed, status, lpr_pil
            _ok, _nk, _tms = ok_n, fail_n, total_ms

            def _ui(i=_i, f=_f, pl=_pl, orig=_or, vt=_vt,
                    ms=_ms, st=_st, lpi=_lpi, ok=_ok, nk=_nk, tms=_tms):
                iid = self._tree.insert("", END, values=(i, f, pl, orig, vt, ms or "-", st))
                if st == "OK":
                    self._tree.item(iid, tags=("ok",))
                elif st.startswith("Lỗi"):
                    self._tree.item(iid, tags=("err",))
                else:
                    self._tree.item(iid, tags=("warn",))
                if lpi:
                    self._folder_lpr[iid] = lpi
                self._tree.see(iid)
                self._pb["value"] = i
                self._prog_lbl.config(text=f"Đang xử lý: {i}/{total}  ({int(i/total*100)}%)")
                done = ok + nk
                avg = tms // done if done else 0
                rate = f"{ok/done:.1%}" if done else "—"
                self._stats_lbl.config(
                    text=f"OK: {ok}  |  Thất bại: {nk}  |  TB: {avg}ms  |  Tỉ lệ: {rate}")
            self.root.after(0, _ui)

        def _done():
            self._btn_start.config(state=NORMAL)
            self._btn_stop.config(state=DISABLED)
            done = ok_n + fail_n
            avg = total_ms // done if done else 0
            rate = f"{ok_n/done:.1%}" if done else "—"
            msg = (f"{'Dừng' if self._cancel else 'Hoàn thành'}: {done}/{total}  "
                   f"OK:{ok_n}  Thất bại:{fail_n}  TB:{avg}ms  Tỉ lệ:{rate}")
            self._prog_lbl.config(text=msg)
            _append_log(self._log, f"✔ {msg}")
        self.root.after(0, _done)

    def _retry_failed(self):
        url = self._url_var.get().strip()
        folder = self._folder_var.get().strip()
        if not url:
            messagebox.showwarning("Thông báo", "Chưa nhập URL.")
            return
        rows = [
            (iid, os.path.join(folder, str(self._tree.item(iid)["values"][1])))
            for iid in self._tree.get_children()
            if str(self._tree.item(iid)["values"][6]) in ("Không nhận dạng",)
            or str(self._tree.item(iid)["values"][6]).startswith("Lỗi")
        ]
        if not rows:
            messagebox.showinfo("Thông báo", "Không có dòng nào cần retry.")
            return
        _append_log(self._log, f"⠿ Retry {len(rows)} ảnh...")
        timeout = self._timeout_var.get()
        lpr_type = self._type_var.get()

        def _run():
            for iid, fpath in rows:
                if self._cancel or not os.path.isfile(fpath):
                    continue
                result, err = _api_call_file(fpath, url, timeout, lpr_type)
                plate = "" if err else result.get("plate", "")
                status = ("OK" if plate else "Không nhận dạng") if not err else f"Lỗi: {err}"

                def _upd(iid=iid, pl=plate, st=status):
                    vals = list(self._tree.item(iid)["values"])
                    vals[2] = pl; vals[6] = st
                    self._tree.item(iid, values=vals)
                    tag = "ok" if st == "OK" else ("err" if st.startswith("Lỗi") else "warn")
                    self._tree.item(iid, tags=(tag,))
                self.root.after(0, _upd)
            self.root.after(0, lambda: _append_log(self._log, "✔ Retry xong."))

        threading.Thread(target=_run, daemon=True).start()

    # ═══════════════════════════ FOLDER PREVIEW ═══════════════════════════

    def _on_tree_select(self, _=None):
        sel = self._tree.selection()
        if not sel:
            self._clear_fpreview()
            self._btn_ok.config(state=DISABLED)
            self._btn_wrong.config(state=DISABLED)
            return

        iid = sel[0]
        vals = self._tree.item(iid)["values"]
        if not vals:
            return

        fname = str(vals[1])
        plate = str(vals[2])
        ms    = str(vals[5])
        folder = self._folder_var.get().strip()

        has_file = bool(fname and folder)
        self._btn_ok.config(state=NORMAL if has_file else DISABLED)
        self._btn_wrong.config(state=NORMAL if has_file else DISABLED)

        info = plate if plate and plate not in ("-", "") else "(không nhận dạng)"
        if ms and ms != "-":
            info += f"   {ms}ms"
        self._prev_lbl.config(text=info)

        # Plate crop
        lpi = self._folder_lpr.get(iid)
        if lpi and _PIL_OK:
            self._show_img(self._pic_fp, lpi, 200, 80)
        else:
            self._pic_fp.config(image="", text="(biển số)")

        # Vehicle image
        if has_file:
            fpath = os.path.join(folder, fname)
            if os.path.isfile(fpath) and _PIL_OK:
                try:
                    img = Image.open(fpath)
                    self._show_img(self._pic_fv, img, 300, 180)
                    img.close()
                    return
                except Exception:
                    pass
        self._pic_fv.config(image="", text="(ảnh xe)")

    def _on_tree_dbl(self, _=None):
        sel = self._tree.selection()
        if not sel:
            return
        vals = self._tree.item(sel[0])["values"]
        fname = str(vals[1]) if vals else ""
        folder = self._folder_var.get().strip()
        if fname and folder and _PIL_OK:
            fpath = os.path.join(folder, fname)
            if os.path.isfile(fpath):
                try:
                    img = Image.open(fpath)
                    _zoom_image_window(self.root, img, fname)
                except Exception:
                    pass

    def _clear_fpreview(self):
        self._pic_fv.config(image="", text="(ảnh xe)")
        self._pic_fp.config(image="", text="(biển số)")
        self._prev_lbl.config(text="(chọn dòng trong bảng để xem ảnh)")

    def _zoom_fv(self):
        sel = self._tree.selection()
        if not sel or not _PIL_OK:
            return
        vals = self._tree.item(sel[0])["values"]
        fname = str(vals[1]) if vals else ""
        folder = self._folder_var.get().strip()
        if fname and folder:
            fpath = os.path.join(folder, fname)
            if os.path.isfile(fpath):
                try:
                    _zoom_image_window(self.root, Image.open(fpath), fname)
                except Exception:
                    pass

    def _zoom_fp(self):
        sel = self._tree.selection()
        if not sel:
            return
        lpi = self._folder_lpr.get(sel[0])
        if lpi:
            _zoom_image_window(self.root, lpi, "Biển số")

    # ═══════════════════════════ GT SAVE ══════════════════════════════════

    def _save_correct(self):
        self._save_gt(True)

    def _save_wrong(self):
        self._save_gt(False)

    def _save_gt(self, is_correct: bool):
        sel = self._tree.selection()
        if not sel:
            return
        vals = self._tree.item(sel[0])["values"]
        if not vals:
            return
        fname = str(vals[1])
        plate = str(vals[2])
        folder = self._folder_var.get().strip()
        if not fname or not folder:
            return
        src = os.path.join(folder, fname)
        if not os.path.isfile(src):
            _append_log(self._log, f"[LỖI] Không tìm thấy: {src}")
            return

        sub = "dung" if is_correct else "sai"
        dest_dir = os.path.join(folder, "_gt", sub)
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, os.path.basename(fname))
        try:
            shutil.copy2(src, dest)
            if is_correct and plate and plate not in ("-", "(không nhận dạng)"):
                with open(os.path.splitext(dest)[0] + ".txt", "w", encoding="utf-8") as f:
                    f.write(plate)
        except Exception as ex:
            _append_log(self._log, f"[LỖI] Copy: {ex}")
            return

        label = "GT: Đúng ✓" if is_correct else "GT: Sai ✗"
        new_vals = list(vals); new_vals[6] = label
        self._tree.item(sel[0], values=new_vals)
        tag = "gt_ok" if is_correct else "gt_err"
        self._tree.tag_configure(
            "gt_ok",  background="#1a2e1a", foreground=SUCCESS)
        self._tree.tag_configure(
            "gt_err", background="#2e1a1a", foreground="#f08080")
        self._tree.item(sel[0], tags=(tag,))
        _append_log(self._log, f"✔ {os.path.basename(fname)} → _gt/{sub}/ | {plate}")

    # ═══════════════════════════ EXPORT ═══════════════════════════════════

    def _export(self, _=None):
        if not self._tree.get_children():
            messagebox.showinfo("Thông báo", "Không có dữ liệu để xuất.")
            return
        from datetime import datetime
        path = filedialog.asksaveasfilename(
            title="Xuất kết quả CSV",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("Tất cả", "*.*")],
            initialfile=f"lpr_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(["STT", "Tên file", "Biển số", "Biển gốc",
                             "Loại xe", "Thời gian (ms)", "Trạng thái"])
                for iid in self._tree.get_children():
                    w.writerow(self._tree.item(iid)["values"])
            n = len(self._tree.get_children())
            _append_log(self._log, f"✔ Đã xuất {n} dòng → {path}")
            messagebox.showinfo("Xuất CSV", f"Xuất thành công {n} dòng.")
        except Exception as ex:
            _append_log(self._log, f"[LỖI] Xuất CSV: {ex}")

    # ═══════════════════════════ HELPERS ══════════════════════════════════

    @staticmethod
    def _show_img(widget: Label, pil_img, max_w: int, max_h: int):
        if not _PIL_OK or pil_img is None:
            return
        try:
            img = pil_img.copy()
            img.thumbnail((max_w, max_h), Image.LANCZOS)
            tk_img = ImageTk.PhotoImage(img)
            widget.config(image=tk_img, text="")
            widget._tk_img = tk_img
        except Exception:
            pass

    # ═══════════════════════ APP SHORTCUT HOOKS ═══════════════════════════

    def _run(self):
        """F5 — nhận dạng ảnh đơn (nếu đã load) hoặc test thư mục."""
        if self._pil_single is not None:
            self._detect_single()
        else:
            self._start()

    def _browse(self):
        """Ctrl+O — load ảnh đơn."""
        self._load_image()

    def _save(self):
        """Ctrl+S — xuất CSV."""
        self._export()

    def _prev_image(self):
        """← — dòng trước trong tree."""
        ch = self._tree.get_children()
        if not ch:
            return
        sel = self._tree.selection()
        idx = list(ch).index(sel[0]) if sel else 0
        target = ch[max(0, idx - 1)]
        self._tree.selection_set(target)
        self._tree.see(target)

    def _next_image(self):
        """→ — dòng sau trong tree."""
        ch = self._tree.get_children()
        if not ch:
            return
        sel = self._tree.selection()
        idx = list(ch).index(sel[0]) if sel else -1
        target = ch[min(len(ch) - 1, idx + 1)]
        self._tree.selection_set(target)
        self._tree.see(target)


# ════════════════════════ MODULE-LEVEL API HELPERS ════════════════════════

def _api_call_pil(pil_img, url: str, timeout: int, lpr_type: str) -> tuple:
    """Gửi PIL Image lên API, trả về (result_dict, error_str|None)."""
    if not _REQ_OK or not _PIL_OK:
        return {}, "requests hoặc Pillow chưa cài"
    try:
        buf = BytesIO()
        img = pil_img
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        img.save(buf, format="JPEG")
        buf.seek(0)
        return _api_call_bytes(buf.read(), url, timeout, lpr_type, ".jpg")
    except Exception as ex:
        return {}, str(ex)


def _api_call_file(fpath: str, url: str, timeout: int, lpr_type: str) -> tuple:
    """Gửi file ảnh theo đường dẫn lên API."""
    if not _REQ_OK:
        return {}, "requests chưa cài"
    try:
        with open(fpath, "rb") as f:
            data = f.read()
        ext = os.path.splitext(fpath)[1].lower()
        return _api_call_bytes(data, url, timeout, lpr_type, ext)
    except Exception as ex:
        return {}, str(ex)


def _api_call_bytes(data: bytes, url: str, timeout: int,
                    lpr_type: str, ext: str) -> tuple:
    """HTTP POST multipart/form-data lên endpoint."""
    _MIME = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".bmp": "image/bmp", ".webp": "image/webp",
    }
    mime = _MIME.get(ext, "image/jpeg")
    try:
        if "OpenALPR" in lpr_type:
            files = {"image": (f"img{ext}", data, mime)}
        else:
            # HTTP REST API (/read-plate) uses field 'upload'
            # Kztek LPR AI Server — thử field 'image' nếu không phải REST
            field = "upload" if "HTTP REST" in lpr_type else "image"
            files = {field: (f"img{ext}", data, mime)}

        resp = requests.post(url, files=files, timeout=timeout)
        resp.raise_for_status()

        try:
            raw = resp.json()
        except Exception:
            # Plain text response → treat as plate number
            raw = {"plate": resp.text.strip()}

        return _parse_lpr_response(raw), None

    except requests.Timeout:
        return {}, f"Timeout ({timeout}s)"
    except requests.ConnectionError:
        return {}, "Không kết nối được server"
    except requests.HTTPError as ex:
        return {}, f"HTTP {ex.response.status_code}: {ex.response.text[:120]}"
    except Exception as ex:
        return {}, str(ex)


def _fmt_bbox(bbox) -> str:
    if isinstance(bbox, dict):
        return (f"({bbox.get('xmin',0)}, {bbox.get('ymin',0)}) → "
                f"({bbox.get('xmax',0)}, {bbox.get('ymax',0)})")
    if isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
        return f"({bbox[0]}, {bbox[1]}) → ({bbox[2]}, {bbox[3]})"
    return "-"
