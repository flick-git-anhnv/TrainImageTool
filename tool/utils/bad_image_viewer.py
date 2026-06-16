"""Viewer for bad images saved under <out>/<lane>/bad/<reason>/<date>/*.jpg"""
import base64
import csv
import difflib
import json
import re
import shutil
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from tkinter import *
from tkinter import filedialog, messagebox, ttk

from ..core.constants import BG, CARD, ACCENT, ACCENT2, TEXT, DIM, F_MAIN, F_BOLD, F_MONO
from ..core.imports import _cv2_mod, _CV2_OK, _req_mod, _REQUESTS_OK
from ..core.settings import _bind_cfg
from ..core.ui_helpers import DateTimePicker

try:
    from PIL import Image as _PIL, ImageTk as _ITk
    _PIL_OK = True
except ImportError:
    _PIL_OK = False

_P8_SUFFIXES = {"fi", "fo", "pi", "po", "in", "out", "full", "plate", "img"}

_REASON_LABEL = {
    "none":              "Không có BSX",
    "in_out_mismatch":   "BSX vào ≠ ra",
    "register_mismatch": "BSX ≠ đăng ký",
}
_REASON_COLOR = {
    "none":              "#FFAA80",
    "in_out_mismatch":   "#F05922",
    "register_mismatch": "#B8B3D6",
}
_ALL_REASONS = ("none", "in_out_mismatch", "register_mismatch")

_ENTRY_STYLE = dict(font=("Segoe UI", 12), bg="#2a2a3e", fg=TEXT,
                    insertbackground=TEXT, relief="flat",
                    highlightthickness=1, highlightcolor=ACCENT,
                    highlightbackground=DIM)


# ── filename parsing ──────────────────────────────────────────────────────────

def _parse_direction(stem: str) -> str:
    parts = stem.split("_")
    if len(parts) < 2:
        return ""
    if parts and re.fullmatch(r"\d{3}", parts[-1]):
        parts = parts[:-1]
    if not parts:
        return ""
    last = parts[-1].lower()
    return last if last in ("in", "out") else ""


def _parse_plates(stem: str, reason: str):
    if reason == "none":
        return "", ""
    parts = stem.split("_")
    if len(parts) < 2:
        return "", ""
    parts = parts[1:]
    if parts and re.fullmatch(r"\d{3}", parts[-1]):
        parts = parts[:-1]
    if parts and parts[-1].lower() in _P8_SUFFIXES:
        parts = parts[:-1]
    if len(parts) >= 2:
        return parts[0], parts[1]
    return (parts[0], "") if parts else ("", "")


def _parse_plates_3col(stem: str, reason: str, direction: str):
    """Return (plate_in, plate_out, plate_reg)."""
    if reason == "none":
        return "", "", ""
    p1, p2 = _parse_plates(stem, reason)
    if reason == "in_out_mismatch":
        return p1, p2, ""
    if reason == "register_mismatch":
        if direction == "in":
            return p1, "", p2
        if direction == "out":
            return "", p1, p2
        return p1, "", p2
    return p1, p2, ""


# ── folder scan ───────────────────────────────────────────────────────────────

def scan_bad_images(out_path: Path) -> list:
    """Scan bad images.
    Structure: {out}/bad/{lane}/{reason}/{date}/{event_id}/in/*.jpg
                                                          /out/*.jpg
    """
    if not out_path.exists():
        return []

    events: dict = {}
    for img in sorted(out_path.rglob("*.jpg")):
        try:
            rel = img.relative_to(out_path).parts
            # expect 7 parts: "bad" / lane / reason / date / event_id / direction / fname
            if len(rel) != 7 or rel[0] != "bad" or rel[5] not in ("in", "out"):
                continue
            _, lane, reason, date_s, event_id, direction, _fname = rel
            key = (lane, reason, date_s, event_id)
            if key not in events:
                events[key] = {"lane": lane, "reason": reason,
                               "date": date_s, "event_id": event_id,
                               "paths_in": [], "paths_out": []}
            events[key]["paths_in" if direction == "in" else "paths_out"].append(str(img))
        except Exception:
            continue

    rows = []
    for key in sorted(events):
        ev = events[key]
        paths_in  = sorted(ev["paths_in"])
        paths_out = sorted(ev["paths_out"])
        anchor    = paths_in[0] if paths_in else paths_out[0]
        stem      = Path(anchor).stem
        ts_raw    = stem[:6]
        time_s    = (f"{ts_raw[0:2]}:{ts_raw[2:4]}:{ts_raw[4:6]}"
                     if len(ts_raw) == 6 and ts_raw.isdigit() else "??:??:??")
        anchor_dir = "in" if paths_in else "out"
        pin, pout, preg = _parse_plates_3col(stem, ev["reason"], anchor_dir)
        direction  = "pair" if (paths_in and paths_out) else anchor_dir
        rows.append({
            "event_id":  ev["event_id"],
            "lane":      ev["lane"],
            "reason":    ev["reason"],
            "date":      ev["date"],
            "time":      time_s,
            "plate_in":  pin,
            "plate_out": pout,
            "plate_reg": preg,
            "fname":     Path(anchor).name,
            "direction": direction,
            "path":      anchor,
            "path_in":   paths_in[0]  if paths_in  else "",
            "path_out":  paths_out[0] if paths_out else "",
        })
    return rows


# ── image helpers ─────────────────────────────────────────────────────────────

def _load_photo(path: str, max_w: int, max_h: int):
    if _PIL_OK:
        try:
            img = _PIL.open(path)
            img.thumbnail((max_w, max_h), _PIL.LANCZOS)
            return _ITk.PhotoImage(img)
        except Exception:
            return None
    if _CV2_OK:
        try:
            img = _cv2_mod.imread(str(path))
            if img is None:
                return None
            h, w = img.shape[:2]
            scale = min(max_w / w, max_h / h, 1.0)
            if scale < 1.0:
                img = _cv2_mod.resize(img, (int(w * scale), int(h * scale)))
            img_rgb = _cv2_mod.cvtColor(img, _cv2_mod.COLOR_BGR2RGB)
            ok, buf = _cv2_mod.imencode(".png", img_rgb)
            if ok:
                return PhotoImage(data=base64.b64encode(buf.tobytes()))
        except Exception:
            return None
    return None


def _norm_plate(s: str) -> str:
    return re.sub(r"[^0-9A-Za-z]", "", str(s or "")).upper()


def _diff_segments(p1: str, p2: str):
    """Return (segs1, segs2) where each is list of (text, is_diff).
    Uses SequenceMatcher so works for plates of unequal length.
    """
    sm = difflib.SequenceMatcher(None, p1, p2, autojunk=False)
    segs1, segs2 = [], []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            segs1.append((p1[i1:i2], False))
            segs2.append((p2[j1:j2], False))
        elif op == "replace":
            segs1.append((p1[i1:i2], True))
            segs2.append((p2[j1:j2], True))
        elif op == "delete":
            segs1.append((p1[i1:i2], True))
        elif op == "insert":
            segs2.append((p2[j1:j2], True))
    return segs1, segs2


def _crop_plate(path: str, box: dict, max_w: int = 260, max_h: int = 60):
    """Return PhotoImage of cropped plate region, or None."""
    x1 = int(box.get("Xmin") or box.get("xmin") or 0)
    y1 = int(box.get("Ymin") or box.get("ymin") or 0)
    x2 = int(box.get("Xmax") or box.get("xmax") or 0)
    y2 = int(box.get("Ymax") or box.get("ymax") or 0)
    if x2 <= x1 or y2 <= y1:
        return None
    if _PIL_OK:
        try:
            img = _PIL.open(path)
            crop = img.crop((x1, y1, x2, y2))
            crop.thumbnail((max_w, max_h), _PIL.LANCZOS)
            return _ITk.PhotoImage(crop)
        except Exception:
            return None
    if _CV2_OK:
        try:
            img = _cv2_mod.imread(str(path))
            if img is None:
                return None
            h, w = img.shape[:2]
            crop = img[max(0, y1):min(h, y2), max(0, x1):min(w, x2)]
            if crop.size == 0:
                return None
            ch, cw = crop.shape[:2]
            scale = min(max_w / cw, max_h / ch, 1.0)
            if scale < 1.0:
                crop = _cv2_mod.resize(crop, (int(cw * scale), int(ch * scale)))
            ok, buf = _cv2_mod.imencode(".png",
                                        _cv2_mod.cvtColor(crop, _cv2_mod.COLOR_BGR2RGB))
            if ok:
                return PhotoImage(data=base64.b64encode(buf.tobytes()))
        except Exception:
            return None
    return None


# ── viewer window ─────────────────────────────────────────────────────────────

class BadImageViewer(Toplevel):

    def __init__(self, root, out_path: Path):
        super().__init__(root)
        self.out_path = Path(out_path)
        self.title("Xem ảnh xấu")
        self.configure(bg=BG)
        self.geometry("1500x820")
        self.resizable(True, True)
        self._records: list = []
        self._current_rec = None
        self._detected: dict = {}

        self._sash_var = IntVar(value=720)
        _bind_cfg("bad_viewer.sash", self._sash_var)

        self._lpr_url_var = StringVar(value="")
        _bind_cfg("bad_viewer.lpr_url", self._lpr_url_var)

        self._save_dir_var = StringVar(value="")
        _bind_cfg("bad_viewer.save_dir", self._save_dir_var)

        self._var_plate          = StringVar(value="")
        self._var_date_from      = StringVar(value="")
        self._var_date_to        = StringVar(value="")
        self._var_gt_filter      = StringVar(value="Tất cả")
        self._var_status_filter  = StringVar(value="Tất cả")
        self._var_det_filter     = StringVar(value="Tất cả")

        # auto-save after detect
        self._auto_save_var = IntVar(value=0)
        _bind_cfg("bad_viewer.auto_save", self._auto_save_var)

        # slideshow
        self._slideshow_active = False
        self._slideshow_after  = None
        self._slideshow_delay_var = IntVar(value=3000)
        _bind_cfg("bad_viewer.slideshow_delay", self._slideshow_delay_var)
        self._batch_cancel = False

        # per-slot zoom factors
        self._zoom_factors = {1: 1.0, 2: 1.0}

        # persistent state: status, saved plates, edit history
        self._state: dict = {}
        self._state_path: Path | None = None
        self._load_state()

        self._build()
        self._refresh()
        self.after(50, self._restore_sash)

    # ── build ─────────────────────────────────────────────────────────────────

    def _build(self):
        self._build_toolbar()
        self._paned = PanedWindow(self, orient=HORIZONTAL,
                                   bg=DIM, sashwidth=5, sashpad=2,
                                   relief="flat", bd=0)
        self._paned.pack(fill=BOTH, expand=True)
        self._build_table(self._paned)
        self._build_preview(self._paned)
        self._paned.bind("<ButtonRelease-1>", self._save_sash)
        # navigation
        self.bind("<Left>",  lambda e: self._nav_record(-1))
        self.bind("<Right>", lambda e: self._nav_record(+1))
        # shortcuts: D=detect both, S=save both, 1/2=save slot, Space=toggle done
        self.bind("<d>", lambda e: self._detect_both())
        self.bind("<D>", lambda e: self._detect_both())
        self.bind("<s>", lambda e: self._save_both())
        self.bind("<S>", lambda e: self._save_both())
        self.bind("1",   lambda e: self._save_img(1))
        self.bind("2",   lambda e: self._save_img(2))
        self.bind("<space>", lambda e: self._toggle_done())

    def _build_toolbar(self):
        # ── Row 1: navigation + filters ───────────────────────────────────────
        tb = Frame(self, bg=CARD, padx=10, pady=6)
        tb.pack(fill=X)

        Button(tb, text="Làm mới", command=self._refresh,
               bg=ACCENT, fg="white", font=F_MAIN,
               activebackground="#c04010", activeforeground="white",
               relief="flat", padx=14, pady=4, cursor="hand2").pack(side=LEFT, padx=(0, 4))
        Button(tb, text="Mở folder", command=self._open_out_folder,
               bg="#2a2a4e", fg="white", font=F_MAIN,
               activebackground="#4A3F8C", activeforeground="white",
               relief="flat", padx=14, pady=4, cursor="hand2").pack(side=LEFT)
        Frame(tb, bg=DIM, width=1).pack(side=LEFT, fill=Y, padx=10, pady=2)

        Label(tb, text="Lý do:", bg=CARD, fg=TEXT, font=F_MAIN).pack(side=LEFT)
        self._var_reason = StringVar(value="Tất cả")
        self._cb_reason  = ttk.Combobox(tb, textvariable=self._var_reason,
                                         state="readonly", width=14, font=F_MAIN)
        self._cb_reason["values"] = ["Tất cả"] + [_REASON_LABEL[r] for r in _ALL_REASONS]
        self._cb_reason.pack(side=LEFT, padx=(4, 8))
        self._cb_reason.bind("<<ComboboxSelected>>", lambda _: self._apply_filter())

        Label(tb, text="Làn:", bg=CARD, fg=TEXT, font=F_MAIN).pack(side=LEFT)
        self._var_lane = StringVar(value="Tất cả")
        self._cb_lane  = ttk.Combobox(tb, textvariable=self._var_lane,
                                       state="readonly", width=14, font=F_MAIN)
        self._cb_lane.pack(side=LEFT, padx=(4, 8))
        self._cb_lane.bind("<<ComboboxSelected>>", lambda _: self._apply_filter())

        Frame(tb, bg=DIM, width=1).pack(side=LEFT, fill=Y, padx=8, pady=2)

        Label(tb, text="BSX:", bg=CARD, fg=TEXT, font=F_MAIN).pack(side=LEFT)
        Entry(tb, textvariable=self._var_plate, width=12, **_ENTRY_STYLE).pack(
              side=LEFT, padx=(4, 8))
        self._var_plate.trace_add("write", lambda *_: self._apply_filter())

        Label(tb, text="Từ:", bg=CARD, fg=TEXT, font=F_MAIN).pack(side=LEFT)
        DateTimePicker(tb, textvariable=self._var_date_from, mode="date",
                       bg=CARD).pack(side=LEFT, padx=(4, 4))
        Label(tb, text="→", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        DateTimePicker(tb, textvariable=self._var_date_to, mode="date",
                       bg=CARD).pack(side=LEFT, padx=(4, 8))
        self._var_date_from.trace_add("write", lambda *_: self._apply_filter())
        self._var_date_to.trace_add("write",   lambda *_: self._apply_filter())

        self._lbl_count = Label(tb, text="", bg=CARD, fg=DIM, font=F_MAIN)
        self._lbl_count.pack(side=LEFT, padx=8)

        # ── Row 2: actions + extra filters ────────────────────────────────────
        tb2 = Frame(self, bg="#1a1a2e", padx=10, pady=5)
        tb2.pack(fill=X)

        # Batch detect
        self._btn_batch = Button(tb2, text="Nhận diện tất cả",
               command=self._batch_detect,
               bg="#4A3F8C", fg="white", font=F_MAIN,
               activebackground=ACCENT, activeforeground="white",
               relief="flat", padx=12, pady=3, cursor="hand2")
        self._btn_batch.pack(side=LEFT, padx=(0, 4))
        self._lbl_batch_progress = Label(tb2, text="", bg="#1a1a2e",
                                          fg=DIM, font=F_MAIN)
        self._lbl_batch_progress.pack(side=LEFT, padx=(0, 8))

        Frame(tb2, bg=DIM, width=1).pack(side=LEFT, fill=Y, padx=8, pady=2)

        # Auto-save toggle
        Checkbutton(tb2, text="Tự lưu sau detect",
                    variable=self._auto_save_var,
                    bg="#1a1a2e", fg=TEXT, selectcolor="#251C53",
                    activebackground="#1a1a2e", font=F_MAIN,
                    cursor="hand2").pack(side=LEFT, padx=(0, 10))

        Frame(tb2, bg=DIM, width=1).pack(side=LEFT, fill=Y, padx=8, pady=2)

        # GT filter
        Label(tb2, text="GT:", bg="#1a1a2e", fg=TEXT, font=F_MAIN).pack(side=LEFT)
        self._cb_gt = ttk.Combobox(tb2, textvariable=self._var_gt_filter,
                                    state="readonly", width=12, font=F_MAIN)
        self._cb_gt["values"] = ["Tất cả", "Chưa lưu", "Đã lưu"]
        self._cb_gt.pack(side=LEFT, padx=(4, 8))
        self._cb_gt.bind("<<ComboboxSelected>>", lambda _: self._apply_filter())

        # Status filter
        Label(tb2, text="Trạng thái:", bg="#1a1a2e", fg=TEXT, font=F_MAIN).pack(side=LEFT)
        self._cb_status = ttk.Combobox(tb2, textvariable=self._var_status_filter,
                                        state="readonly", width=12, font=F_MAIN)
        self._cb_status["values"] = ["Tất cả", "Chưa xử lý", "Done", "Skip"]
        self._cb_status.pack(side=LEFT, padx=(4, 8))
        self._cb_status.bind("<<ComboboxSelected>>", lambda _: self._apply_filter())

        # NĐ lại filter
        Label(tb2, text="NĐ lại:", bg="#1a1a2e", fg=TEXT, font=F_MAIN).pack(side=LEFT)
        self._cb_det = ttk.Combobox(tb2, textvariable=self._var_det_filter,
                                     state="readonly", width=14, font=F_MAIN)
        self._cb_det["values"] = ["Tất cả", "Vào ≠ Ra", "Thiếu NĐ lại"]
        self._cb_det.pack(side=LEFT, padx=(4, 8))
        self._cb_det.bind("<<ComboboxSelected>>", lambda _: self._apply_filter())

        Frame(tb2, bg=DIM, width=1).pack(side=LEFT, fill=Y, padx=8, pady=2)

        # Done / Skip mark buttons
        Button(tb2, text="✓ Done", command=lambda: self._set_status("done"),
               bg="#1e5c1e", fg="white", font=F_MAIN,
               activebackground="#2a8a2a", relief="flat",
               padx=10, pady=3, cursor="hand2").pack(side=LEFT, padx=(0, 4))
        Button(tb2, text="⊘ Skip", command=lambda: self._set_status("skip"),
               bg="#5c3a1e", fg="white", font=F_MAIN,
               activebackground="#8a5a2a", relief="flat",
               padx=10, pady=3, cursor="hand2").pack(side=LEFT, padx=(0, 8))

        Frame(tb2, bg=DIM, width=1).pack(side=LEFT, fill=Y, padx=8, pady=2)

        # Bulk export GT
        Button(tb2, text="Xuất GT chọn", command=self._bulk_export_gt,
               bg="#251C53", fg="white", font=F_MAIN,
               activebackground="#4A3F8C", relief="flat",
               padx=10, pady=3, cursor="hand2").pack(side=LEFT, padx=(0, 4))

        # Stats
        Button(tb2, text="Thống kê", command=self._show_stats,
               bg="#251C53", fg="white", font=F_MAIN,
               activebackground="#4A3F8C", relief="flat",
               padx=10, pady=3, cursor="hand2").pack(side=LEFT, padx=(0, 4))

        # Export history
        Button(tb2, text="Xuất lịch sử", command=self._export_history,
               bg="#251C53", fg="white", font=F_MAIN,
               activebackground="#4A3F8C", relief="flat",
               padx=10, pady=3, cursor="hand2").pack(side=LEFT, padx=(0, 8))

        Frame(tb2, bg=DIM, width=1).pack(side=LEFT, fill=Y, padx=8, pady=2)

        # Slideshow
        Label(tb2, text="Auto (s):", bg="#1a1a2e", fg=TEXT, font=F_MAIN).pack(side=LEFT)
        Spinbox(tb2, from_=1, to=30, textvariable=self._slideshow_delay_var,
                width=4, bg="#2a2a3e", fg=TEXT, font=F_MAIN,
                insertbackground=TEXT, relief="flat",
                buttonbackground="#333355").pack(side=LEFT, padx=(4, 4))
        self._btn_slideshow = Button(tb2, text="▶ Chạy",
               command=self._toggle_slideshow,
               bg="#333355", fg="white", font=F_MAIN,
               activebackground="#4A3F8C", relief="flat",
               padx=10, pady=3, cursor="hand2")
        self._btn_slideshow.pack(side=LEFT)

    def _build_table(self, paned):
        f = Frame(paned, bg=BG)
        paned.add(f, minsize=300, stretch="always")
        f.columnconfigure(0, weight=1)
        f.rowconfigure(0, weight=1)

        s = ttk.Style()
        s.configure("Bad.Treeview",
                    background="#1e1e2e", foreground="#d4d4d4",
                    fieldbackground="#1e1e2e", rowheight=24, font=F_MONO)
        s.configure("Bad.Treeview.Heading",
                    background="#251C53", foreground="white",
                    font=("Segoe UI", 9, "bold"))
        s.map("Bad.Treeview", background=[("selected", "#4A3F8C")])

        cols = ("status", "lane", "reason", "date", "time",
                "plate_in", "plate_out", "plate_reg",
                "det_in", "det_out", "fname")
        self._tree = ttk.Treeview(f, columns=cols, show="headings",
                                   style="Bad.Treeview", selectmode="extended")
        spec = [
            ("status",    "",             30, "center"),
            ("lane",      "Làn",         110, "w"),
            ("reason",    "Lý do",       130, "w"),
            ("date",      "Ngày",         88, "center"),
            ("time",      "Giờ",          60, "center"),
            ("plate_in",  "Biển vào",    100, "center"),
            ("plate_out", "Biển ra",     100, "center"),
            ("plate_reg", "Đăng ký",     100, "center"),
            ("det_in",    "NĐ lại vào",  100, "center"),
            ("det_out",   "NĐ lại ra",   100, "center"),
            ("fname",     "Tên file",    200, "w"),
        ]
        for col, hdr, w, anchor in spec:
            self._tree.heading(col, text=hdr)
            self._tree.column(col, width=w, minwidth=20, anchor=anchor)

        for reason, color in _REASON_COLOR.items():
            self._tree.tag_configure(reason, foreground=color)
        self._tree.tag_configure("odd",          background="#16162a")
        self._tree.tag_configure("even",         background="#1e1e2e")
        self._tree.tag_configure("done",         foreground="#7fffaa")
        self._tree.tag_configure("skip",         foreground="#888888")
        self._tree.tag_configure("det_mismatch", background="#2a1510")

        vsb = ttk.Scrollbar(f, orient=VERTICAL,   command=self._tree.yview)
        hsb = ttk.Scrollbar(f, orient=HORIZONTAL, command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self._tree.grid(row=0, column=0, sticky=NSEW)
        vsb.grid(row=0, column=1, sticky=NS)
        hsb.grid(row=1, column=0, sticky=EW)

        self._tree.bind("<<TreeviewSelect>>", self._on_select)
        self._tree.bind("<Double-1>", lambda e: self._on_dblclick_img(1))

        # right-click context menu on tree
        self._tree_menu = Menu(self, tearoff=0, bg=CARD, fg=TEXT,
                                activebackground="#4A3F8C", activeforeground="white")
        self._tree_menu.add_command(label="✓ Đánh dấu Done",
                                    command=lambda: self._set_status("done"))
        self._tree_menu.add_command(label="⊘ Đánh dấu Skip",
                                    command=lambda: self._set_status("skip"))
        self._tree_menu.add_command(label="✕ Xóa trạng thái",
                                    command=lambda: self._set_status(""))
        self._tree_menu.add_separator()
        self._tree_menu.add_command(label="Xuất GT các mục chọn",
                                    command=self._bulk_export_gt)
        self._tree.bind("<Button-3>", self._on_tree_right_click)

    # ── preview panel ─────────────────────────────────────────────────────────

    def _build_preview(self, paned):
        outer = Frame(paned, bg=CARD)
        paned.add(outer, minsize=220, stretch="always")
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(3, weight=1)

        # row 0: LPR URL
        r0 = Frame(outer, bg=CARD, padx=10, pady=6)
        r0.grid(row=0, column=0, sticky=EW)
        Label(r0, text="LPR URL:", bg=CARD, fg=TEXT,
              font=("Segoe UI", 10)).pack(side=LEFT)
        Entry(r0, textvariable=self._lpr_url_var, **_ENTRY_STYLE).pack(
              side=LEFT, fill=X, expand=True, padx=(4, 0))

        # row 1: Save folder
        r1 = Frame(outer, bg=CARD, padx=10, pady=6)
        r1.grid(row=1, column=0, sticky=EW)
        Label(r1, text="Lưu vào:", bg=CARD, fg=TEXT,
              font=("Segoe UI", 10)).pack(side=LEFT)
        Entry(r1, textvariable=self._save_dir_var, **_ENTRY_STYLE).pack(
              side=LEFT, fill=X, expand=True, padx=(4, 4))
        Button(r1, text="...", command=self._browse_save_dir,
               bg=DIM, fg=TEXT, font=("Segoe UI", 10),
               relief="flat", padx=6, pady=2, cursor="hand2").pack(side=LEFT)

        # row 2: separator
        Frame(outer, bg=DIM, height=1).grid(row=2, column=0, sticky=EW)

        # row 3: main content — hai slot nằm ngang
        main = Frame(outer, bg=CARD, padx=10, pady=8)
        main.grid(row=3, column=0, sticky=NSEW)
        main.columnconfigure(0, weight=1)
        main.columnconfigure(2, weight=1)
        main.rowconfigure(0, weight=1)
        main.rowconfigure(1, weight=0)
        main.rowconfigure(2, weight=0)
        self._preview_main = main

        self._slot1 = self._make_img_slot(main, 1)
        self._slot1["frame"].grid(row=0, column=0, sticky=NSEW)

        self._slot_sep = Frame(main, bg=CARD, width=72)
        self._slot_sep.grid(row=0, column=1, sticky=NSEW, padx=2)
        self._slot_sep.rowconfigure(0, weight=1)
        self._slot_sep.columnconfigure(0, weight=0)
        self._slot_sep.columnconfigure(1, weight=1)
        self._slot_sep.columnconfigure(2, weight=0)
        Frame(self._slot_sep, bg=DIM, width=2).grid(row=0, column=0, sticky=NS)
        self._compare_lbl = Label(self._slot_sep, text="", bg=CARD,
                                   font=("Segoe UI", 28, "bold"), anchor="s")
        self._compare_lbl.grid(row=0, column=1, sticky="sew", pady=(0, 24))
        Frame(self._slot_sep, bg=DIM, width=2).grid(row=0, column=2, sticky=NS)

        self._slot2 = self._make_img_slot(main, 2)
        self._slot2["frame"].grid(row=0, column=2, sticky=NSEW)

        Frame(main, bg=DIM, height=1).grid(row=1, column=0, columnspan=3,
                                            sticky=EW, pady=(8, 4))

        self._info_var = StringVar(value="")
        Label(main, textvariable=self._info_var, bg=CARD, fg=TEXT,
              font=F_MONO, justify=LEFT, anchor="nw").grid(
              row=2, column=0, columnspan=3, sticky=EW, pady=(0, 4))

    def _make_img_slot(self, parent, slot_idx: int) -> dict:
        f = Frame(parent, bg=CARD)
        f.columnconfigure(0, weight=1)
        f.rowconfigure(0, weight=0)  # type label
        f.rowconfigure(1, weight=1)  # image
        f.rowconfigure(2, weight=0)  # detect row: [btn] [crop]
        f.rowconfigure(3, weight=0)  # result text widget
        f.rowconfigure(4, weight=0)  # match + save row

        type_lbl = Label(f, text="", bg=CARD, fg=ACCENT,
                          font=("Segoe UI", 14, "bold"), anchor="w")
        type_lbl.grid(row=0, column=0, sticky=EW, pady=(0, 3))

        img_lbl = Label(f, bg="#16162a", fg=DIM, font=F_MAIN, cursor="hand2",
                         text="Chọn ảnh\nđể xem" if slot_idx == 1 else "")
        img_lbl.grid(row=1, column=0, sticky=NSEW)
        img_lbl.bind("<Double-1>", lambda e, s=slot_idx: self._on_dblclick_img(s))
        img_lbl.bind("<MouseWheel>",   lambda e, s=slot_idx: self._on_scroll_img(e, s))
        img_lbl.bind("<Button-4>",     lambda e, s=slot_idx: self._on_scroll_img(e, s))
        img_lbl.bind("<Button-5>",     lambda e, s=slot_idx: self._on_scroll_img(e, s))
        img_lbl.bind("<Button-3>",     lambda e, s=slot_idx: self._on_right_click_img(e, s))

        # ── detect row: [button] [crop_image] ─────────────────────────────
        det = Frame(f, bg=CARD)
        det.grid(row=2, column=0, sticky=EW, pady=(7, 2))

        lpr_btn = Button(det, text="Nhận diện BSX",
                          command=lambda s=slot_idx: self._lpr_check(s),
                          bg="#4A3F8C", fg="white", font=("Segoe UI", 13),
                          activebackground=ACCENT, activeforeground="white",
                          relief="flat", padx=12, pady=5, cursor="hand2")
        lpr_btn.pack(side=LEFT)

        # crop image ngay cạnh nút nhận diện — kích đúp để phóng to
        plate_crop_lbl = Label(det, bg="#1a1a2e", fg=DIM, text="",
                                cursor="hand2", relief="flat", borderwidth=1)
        plate_crop_lbl.pack(side=LEFT, padx=(10, 0))
        plate_crop_lbl.bind("<Double-1>", lambda e, s=slot_idx: self._zoom_crop(s))

        # ── result text widget (row below detect row) ──────────────────────
        result_txt = Text(f, height=2, bg=CARD, fg="#d4d4d4",
                           font=("Segoe UI", 16, "bold"),
                           relief="flat", bd=0, wrap=WORD,
                           state=DISABLED, cursor="arrow")
        result_txt.tag_configure("diff", foreground="#ff5555")
        result_txt.tag_configure("normal", foreground="#d4d4d4")
        result_txt.grid(row=3, column=0, sticky=EW, padx=(4, 4), pady=(2, 4))

        # ── match + save row ───────────────────────────────────────────────
        sv = Frame(f, bg=CARD)
        sv.grid(row=4, column=0, sticky=EW, pady=(2, 4))

        match_lbl = Label(sv, text="", bg=CARD,
                           font=("Segoe UI", 15, "bold"), anchor="w")
        match_lbl.pack(side=LEFT, padx=(0, 8))

        # arrow button: copy plate from other slot
        other = 2 if slot_idx == 1 else 1
        arrow_sym = "→" if slot_idx == 1 else "←"
        copy_btn = Button(sv, text=f"{arrow_sym} Dùng biển {other}",
                           command=lambda s=slot_idx: self._copy_plate_from_other(s),
                           bg="#333355", fg="white", font=("Segoe UI", 11),
                           activebackground="#4A3F8C", activeforeground="white",
                           relief="flat", padx=8, pady=3, cursor="hand2")
        copy_btn.pack(side=LEFT, padx=(0, 6))

        plate_var = StringVar(value="")
        plate_var.trace_add("write", lambda *_, s=slot_idx: self._refresh_result_txt(s))
        Label(sv, text="BSX:", bg=CARD, fg=DIM,
              font=("Segoe UI", 12)).pack(side=LEFT)
        plate_entry = Entry(sv, textvariable=plate_var, width=12, **_ENTRY_STYLE)
        plate_entry.pack(side=LEFT, padx=(2, 6))
        plate_entry.bind("<Return>", lambda e, s=slot_idx: self._save_img(s))

        Button(sv, text="Lưu + GT",
               command=lambda s=slot_idx: self._save_img(s),
               bg="#1e5c1e", fg="white", font=("Segoe UI", 12),
               activebackground="#2a8a2a", activeforeground="white",
               relief="flat", padx=10, pady=4, cursor="hand2").pack(side=LEFT)
        save_status = Label(sv, text="", bg=CARD, fg="#aaaaaa",
                             font=("Segoe UI", 11), anchor="w")
        save_status.pack(side=LEFT, padx=(10, 0), fill=X, expand=True)

        return {"frame": f, "type_lbl": type_lbl, "img_lbl": img_lbl,
                "lpr_btn": lpr_btn, "result_txt": result_txt,
                "plate_crop_lbl": plate_crop_lbl, "match_lbl": match_lbl,
                "plate_var": plate_var, "save_status": save_status,
                "_det_suffix": "",
                "_photo": None, "_crop_photo": None,
                "_crop_path": None, "_crop_box": None}

    # ── sash ──────────────────────────────────────────────────────────────────

    def _restore_sash(self):
        pos = self._sash_var.get()
        if pos > 0:
            try:
                self._paned.sash_place(0, pos, 0)
            except Exception:
                pass

    def _save_sash(self, _=None):
        try:
            x, _ = self._paned.sash_coord(0)
            self._sash_var.set(x)
        except Exception:
            pass

    def _browse_save_dir(self):
        d = filedialog.askdirectory(title="Chọn folder lưu ảnh",
                                     initialdir=self._save_dir_var.get() or str(self.out_path))
        if d:
            self._save_dir_var.set(d)

    # ── data ──────────────────────────────────────────────────────────────────

    def _refresh(self):
        self._records = scan_bad_images(self.out_path)
        lanes = sorted({r["lane"] for r in self._records})
        self._cb_lane["values"] = ["Tất cả"] + lanes
        # giữ nguyên bộ lọc hiện tại sau khi làm mới
        self._apply_filter()

    def _apply_filter(self):
        sel_r       = self._var_reason.get()
        sel_l       = self._var_lane.get()
        plate_kw    = self._var_plate.get().strip().upper()
        date_from   = self._var_date_from.get().strip()
        date_to     = self._var_date_to.get().strip()
        gt_filter   = self._var_gt_filter.get()
        st_filter   = self._var_status_filter.get()
        det_filter  = self._var_det_filter.get()
        self._tree.delete(*self._tree.get_children())
        shown = 0
        for i, r in enumerate(self._records):
            rl  = _REASON_LABEL.get(r["reason"], r["reason"])
            ek  = self._event_key(r)
            rst = self._state.get(ek, {})
            status  = rst.get("status", "")
            det_in  = rst.get("plate_in",  "")
            det_out = rst.get("plate_out", "")

            if sel_r != "Tất cả" and rl != sel_r:             continue
            if sel_l != "Tất cả" and r["lane"] != sel_l:      continue
            if plate_kw:
                plates = [r.get("plate_in",""), r.get("plate_out",""), r.get("plate_reg",""),
                          det_in, det_out]
                if not any(plate_kw in p.upper() for p in plates if p): continue
            if date_from and r["date"] < date_from:            continue
            if date_to   and r["date"] > date_to:              continue
            # GT filter
            has_gt = bool(det_in or det_out)
            if gt_filter == "Đã lưu"   and not has_gt:        continue
            if gt_filter == "Chưa lưu" and has_gt:            continue
            # status filter
            if st_filter == "Chưa xử lý" and status:           continue
            if st_filter == "Done"        and status != "done": continue
            if st_filter == "Skip"        and status != "skip": continue
            # NĐ lại filter
            _ni = _norm_plate(det_in)
            _no = _norm_plate(det_out)
            if det_filter == "Vào ≠ Ra":
                if not (_ni and _no and _ni != _no):           continue
            elif det_filter == "Thiếu NĐ lại":
                if _ni and _no:                                 continue

            status_sym = {"done": "✓", "skip": "⊘"}.get(status, "")
            row_tag    = "odd" if shown % 2 else "even"
            tags       = (row_tag, r["reason"])
            if status in ("done", "skip"):
                tags = tags + (status,)
            if _ni and _no and _ni != _no:
                tags = tags + ("det_mismatch",)
            self._tree.insert("", END, iid=str(i), tags=tags,
                              values=(status_sym, r["lane"], rl, r["date"], r["time"],
                                      r["plate_in"], r["plate_out"], r["plate_reg"],
                                      det_in, det_out, r["fname"]))
            shown += 1
        self._lbl_count.config(text=f"{shown} ảnh")

    # ── interaction ───────────────────────────────────────────────────────────

    def _selected(self):
        sel = self._tree.selection()
        return self._records[int(sel[0])] if sel else None

    def _on_select(self, _=None):
        rec = self._selected()
        if not rec:
            return
        self._show_preview(rec)
        if self._lpr_url_var.get().strip() and _REQUESTS_OK:
            self.after(120, lambda: self._lpr_check(1,
                on_done=lambda: self._lpr_check(2)))

    def _on_dblclick_img(self, slot_idx: int):
        rec = self._current_rec
        if not rec:
            return
        path = self._slot_path(rec, slot_idx)
        if path:
            self._open_zoom(path)

    def _slot_path(self, rec: dict, slot_idx: int) -> str:
        return rec.get("path_in", "") if slot_idx == 1 else rec.get("path_out", "")

    # ── preview ───────────────────────────────────────────────────────────────

    def _set_pair_mode(self, _pair=True):
        pass  # both slots always visible via fixed horizontal layout

    def _set_slot_img(self, slot: dict, photo, fallback: str):
        slot["_photo"] = photo
        if photo:
            slot["img_lbl"].config(image=photo, text="")
        elif not _PIL_OK and not _CV2_OK:
            slot["img_lbl"].config(image="", text="Cần Pillow:\npip install Pillow")
        else:
            slot["img_lbl"].config(image="", text=fallback)

    @staticmethod
    def _clear_result_txt(txt_widget):
        txt_widget.config(state=NORMAL)
        txt_widget.delete("1.0", END)
        txt_widget.config(state=DISABLED)

    def _set_result_plain(self, slot: dict, text: str, fg: str = "#d4d4d4"):
        w = slot["result_txt"]
        w.config(state=NORMAL)
        w.delete("1.0", END)
        w.tag_configure("plain", foreground=fg)
        w.insert(END, text, "plain")
        w.config(state=DISABLED)

    def _refresh_result_txt(self, slot_idx: int):
        """Redraw result_txt using plate_var (so display always matches textbox)."""
        slot = self._slot1 if slot_idx == 1 else self._slot2
        other_idx = 2 if slot_idx == 1 else 1
        other_slot = self._slot1 if other_idx == 1 else self._slot2

        suffix = slot.get("_det_suffix", "")
        plate  = slot["plate_var"].get().strip()

        if not plate and not suffix:
            return  # not yet detected

        normed       = _norm_plate(plate)
        other_plate  = _norm_plate(other_slot["plate_var"].get().strip())

        w = slot["result_txt"]
        w.config(state=NORMAL)
        w.delete("1.0", END)
        w.tag_configure("normal", foreground="#d4d4d4")
        w.tag_configure("diff",   foreground="#ff5555")

        if normed and other_plate and normed != other_plate:
            if slot_idx == 1:
                segs, _ = _diff_segments(normed, other_plate)
            else:
                _, segs = _diff_segments(other_plate, normed)
            w.insert(END, "BSX: ", "normal")
            for seg_text, is_diff in segs:
                w.insert(END, seg_text, "diff" if is_diff else "normal")
        else:
            w.insert(END, f"BSX: {plate or '?'}", "normal")

        if suffix:
            w.insert(END, suffix, "normal")
        w.config(state=DISABLED)

    def _show_preview(self, rec: dict):
        self._current_rec = rec
        self._detected: dict = {}          # reset detected plates for comparison
        self._compare_lbl.config(text="")
        for sl in (self._slot1, self._slot2):
            sl["_det_suffix"] = ""
            self._clear_result_txt(sl["result_txt"])
            sl["save_status"].config(text="")
            sl["match_lbl"].config(text="")
            sl["plate_crop_lbl"].config(image="", text="")
            sl["_crop_photo"] = None
            sl["_crop_path"]  = None
            sl["_crop_box"]   = None

        self._set_pair_mode()
        reason = rec["reason"]

        # type labels
        if reason == "in_out_mismatch":
            self._slot1["type_lbl"].config(text="◀ Biển vào")
            self._slot2["type_lbl"].config(text="▶ Biển ra")
        elif reason == "register_mismatch":
            t1 = ("◀ Biển vào (≠ đăng ký)" if rec.get("plate_in")
                  else "◀ Biển vào")
            t2 = ("▶ Biển ra (≠ đăng ký)"  if rec.get("plate_out")
                  else "▶ Biển ra")
            self._slot1["type_lbl"].config(text=t1)
            self._slot2["type_lbl"].config(text=t2)
        else:
            self._slot1["type_lbl"].config(text="◀ Biển vào / Ảnh xe")
            self._slot2["type_lbl"].config(text="▶ Biển ra")

        # pre-fill BSX for GT (register_mismatch: use plate_reg)
        preg = rec.get("plate_reg", "")
        if reason == "register_mismatch" and preg:
            self._slot1["plate_var"].set(preg)
            self._slot2["plate_var"].set(preg)
        else:
            self._slot1["plate_var"].set("")
            self._slot2["plate_var"].set("")

        # images
        self._preview_main.update_idletasks()
        pw = max(self._slot1["img_lbl"].winfo_width()  - 8, 180)
        ph = max(self._slot1["img_lbl"].winfo_height() - 8, 100)

        path_in  = rec.get("path_in",  "")
        path_out = rec.get("path_out", "")
        self._set_slot_img(
            self._slot1,
            _load_photo(path_in, pw, ph) if path_in else None,
            "Không tải được ảnh vào" if path_in else "Không có ảnh vào")
        self._set_slot_img(
            self._slot2,
            _load_photo(path_out, pw, ph) if path_out else None,
            "Không tải được ảnh ra" if path_out else "Không có ảnh ra")

        # info row
        parts = []
        if rec.get("plate_in"):  parts.append(f"Vào: {rec['plate_in']}")
        if rec.get("plate_out"): parts.append(f"Ra : {rec['plate_out']}")
        if rec.get("plate_reg"): parts.append(f"ĐK : {rec['plate_reg']}")
        info = (f"Làn: {rec['lane']}  |  {_REASON_LABEL.get(reason, reason)}"
                f"  |  {rec['date']} {rec['time']}")
        if parts:
            info += "\n" + "  ".join(parts)
        self._info_var.set(info)

    def _open_zoom(self, path: str):
        win = Toplevel(self)
        win.title(Path(path).name)
        win.configure(bg="black")
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        photo = _load_photo(path, max_w=int(sw * 0.9), max_h=int(sh * 0.9))
        if photo:
            lbl = Label(win, image=photo, bg="black")
            lbl.image = photo
            lbl.pack()
            win.geometry(f"{photo.width()}x{photo.height()}")
        else:
            Label(win, text=f"Không tải được:\n{path}",
                  bg="black", fg="white", font=F_MAIN).pack(expand=True)

    # ── save + GT ─────────────────────────────────────────────────────────────

    def _check_save_dir(self, slot: dict) -> Path | None:
        d = self._save_dir_var.get().strip()
        if not d:
            slot["save_status"].config(text="Chưa chọn folder lưu")
            return None
        p = Path(d)
        try:
            p.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            slot["save_status"].config(text=f"Lỗi tạo folder: {e}")
            return None
        return p

    def _save_img(self, slot_idx: int):
        slot = self._slot1 if slot_idx == 1 else self._slot2
        rec  = self._current_rec
        if not rec:
            slot["save_status"].config(text="Chưa chọn ảnh")
            return
        save_dir = self._check_save_dir(slot)
        if not save_dir:
            return
        src = self._slot_path(rec, slot_idx)
        if not src or not Path(src).exists():
            slot["save_status"].config(text="Không tìm thấy file ảnh")
            return
        dst = save_dir / Path(src).name
        try:
            shutil.copy2(src, dst)
            plate = slot["plate_var"].get().strip()
            if plate:
                img_stem = Path(src).stem
                gt_path  = save_dir / f"{img_stem}.txt"
                gt_path.write_text(f"{img_stem}\t{plate}", encoding="utf-8")
                slot["save_status"].config(text=f"✓ {dst.name}  [{plate}]")
                # persist to state
                ek = self._event_key(rec)
                if ek not in self._state:
                    self._state[ek] = {}
                plate_key = "plate_in" if slot_idx == 1 else "plate_out"
                orig = rec.get(plate_key, "")
                if plate != orig:
                    self._state[ek].setdefault("edits", []).append({
                        "slot": slot_idx, "original": orig, "corrected": plate,
                        "file": Path(src).name,
                        "ts": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                    })
                self._state[ek][plate_key] = plate
                self._state[ek].setdefault("status", "done")
                self._save_state()
                self._apply_filter()
            else:
                slot["save_status"].config(text=f"✓ {dst.name}  (chưa có BSX)")
        except Exception as e:
            slot["save_status"].config(text=f"Lỗi: {e}")

    def _copy_plate_from_other(self, slot_idx: int):
        """Copy detected/entered plate from the other slot, then save."""
        other_idx = 2 if slot_idx == 1 else 1
        other_slot = self._slot1 if other_idx == 1 else self._slot2
        plate = other_slot["plate_var"].get().strip()
        if not plate:
            # try detected dict
            plate = self._detected.get(other_idx, "")
        if not plate:
            slot = self._slot1 if slot_idx == 1 else self._slot2
            slot["save_status"].config(text="Slot kia chưa có biển số")
            return
        slot = self._slot1 if slot_idx == 1 else self._slot2
        slot["plate_var"].set(plate)
        self._save_img(slot_idx)

    def _open_out_folder(self):
        import subprocess
        path = self.out_path / "bad"
        if not path.exists():
            path = self.out_path
        subprocess.Popen(["explorer", str(path)])

    def _nav_record(self, delta: int):
        """Move selection by delta in the tree (+1 next, -1 prev)."""
        items = self._tree.get_children()
        if not items:
            return
        sel = self._tree.selection()
        if sel:
            try:
                idx = items.index(sel[0])
            except ValueError:
                idx = 0
        else:
            idx = -1
        new_idx = max(0, min(len(items) - 1, idx + delta))
        iid = items[new_idx]
        self._tree.selection_set(iid)
        self._tree.see(iid)
        self._on_select()

    def _zoom_crop(self, slot_idx: int):
        slot = self._slot1 if slot_idx == 1 else self._slot2
        path = slot.get("_crop_path")
        box  = slot.get("_crop_box")
        if not path or not box:
            return
        win = Toplevel(self)
        win.title("Biển số (phóng to)")
        win.configure(bg="black")
        win.resizable(True, True)
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        photo = _crop_plate(path, box,
                             max_w=int(sw * 0.85), max_h=int(sh * 0.55))
        if photo:
            w, h = photo.width(), photo.height()
            win.geometry(f"{w + 40}x{h + 40}")
            win.minsize(200, 80)
            lbl = Label(win, image=photo, bg="black", padx=20, pady=20)
            lbl.image = photo
            lbl.pack(fill=BOTH, expand=True)
        else:
            Label(win, text="Không tải được ảnh cắt",
                  bg="black", fg="white", font=F_MAIN).pack(expand=True)

    # ── LPR check ─────────────────────────────────────────────────────────────

    def _lpr_check(self, slot_idx: int, on_done=None):
        """Nhận diện BSX cho slot_idx. on_done() được gọi sau khi xong (cả OK lẫn lỗi)."""
        slot = self._slot1 if slot_idx == 1 else self._slot2
        rec  = self._current_rec
        url  = self._lpr_url_var.get().strip()

        if not rec:
            self._set_result_plain(slot, "Chưa chọn ảnh", "#ffaa44")
            if on_done: on_done()
            return
        if not url:
            self._set_result_plain(slot, "Chưa nhập LPR URL", "#ffaa44")
            if on_done: on_done()
            return
        if not _REQUESTS_OK:
            self._set_result_plain(slot, "Cần: pip install requests", "#ffaa44")
            if on_done: on_done()
            return

        path = self._slot_path(rec, slot_idx)
        if not path or not Path(path).exists():
            self._set_result_plain(slot, "Không tìm thấy file ảnh", "#ffaa44")
            return

        plate_reg       = _norm_plate(rec.get("plate_reg", ""))
        is_reg_mismatch = rec.get("reason") == "register_mismatch"

        self._set_result_plain(slot, "Đang nhận diện...")
        slot["match_lbl"].config(text="")
        slot["plate_crop_lbl"].config(image="", text="")
        slot["lpr_btn"].config(state=DISABLED)

        def _call():
            t0 = time.time()
            try:
                with open(path, "rb") as fh:
                    data = fh.read()
                resp = _req_mod.post(url,
                                     files={"upload": ("image.jpg", data, "image/jpeg")},
                                     timeout=10)
                resp.raise_for_status()
                elapsed = time.time() - t0
                j = resp.json()
                results = j.get("results") or j.get("Results") or []
                if not results:
                    self.after(0, lambda: _done_empty(elapsed))
                    return
                r0      = results[0]
                det_plate = r0.get("Plate") or r0.get("plate") or ""
                color     = r0.get("Color") or r0.get("color") or ""
                vehicle   = r0.get("Vehicle") or r0.get("vehicle") or {}
                vtype     = (vehicle.get("Vehicle_type") or
                             vehicle.get("vehicle_type") or "")
                box       = r0.get("Box") or r0.get("box") or {}
                crop_photo = _crop_plate(path, box, max_w=320, max_h=90) if box else None
                self.after(0, lambda: _done_ok(det_plate, color, vtype, box,
                                               crop_photo, elapsed))
            except Exception as e:
                elapsed = time.time() - t0
                self.after(0, lambda: _done_err(str(e), elapsed))

        def _done_empty(elapsed: float):
            self._set_result_plain(slot,
                f"Không nhận diện được BSX  ({int(elapsed * 1000)}ms)", "#ffaa44")
            slot["lpr_btn"].config(state=NORMAL)
            if on_done: on_done()

        def _done_err(err: str, elapsed: float):
            self._set_result_plain(slot,
                f"Lỗi ({int(elapsed * 1000)}ms): {err}", "#ff6666")
            slot["lpr_btn"].config(state=NORMAL)
            if on_done: on_done()

        def _done_ok(det_plate: str, color: str, vtype: str,
                     box: dict, crop_photo, elapsed: float):
            normed = _norm_plate(det_plate)

            # per-slot match icon — chỉ dùng cho register_mismatch (so với biển đăng ký)
            if is_reg_mismatch and plate_reg:
                if normed == plate_reg:
                    slot["match_lbl"].config(text="✓ Khớp đăng ký", fg="#7fffaa", bg=CARD)
                else:
                    slot["match_lbl"].config(text="✗ Không khớp đăng ký", fg="#ff5555", bg=CARD)
            else:
                slot["match_lbl"].config(text="")

            # plate crop image — store path+box for zoom
            slot["_crop_path"] = path
            slot["_crop_box"]  = box
            if crop_photo:
                slot["_crop_photo"] = crop_photo
                slot["plate_crop_lbl"].config(image=crop_photo, text="")
            else:
                slot["plate_crop_lbl"].config(image="", text="(no crop)")

            slot["lpr_btn"].config(state=NORMAL)

            # center comparison icon: compare both detected plates
            self._detected[slot_idx] = normed
            other_idx = 2 if slot_idx == 1 else 1
            if 1 in self._detected and 2 in self._detected:
                p1, p2 = self._detected[1], self._detected[2]
                if p1 and p2:
                    if p1 == p2:
                        self._compare_lbl.config(text="=", fg="#7fffaa")
                    else:
                        self._compare_lbl.config(text="≠", fg="#ff5555")

            # store suffix; _refresh_result_txt uses plate_var + this suffix
            info_suffix = ""
            if color: info_suffix += f"  Màu: {color}"
            if vtype: info_suffix += f"  Loại: {vtype}"
            info_suffix += f"  ({int(elapsed * 1000)}ms)"
            slot["_det_suffix"] = info_suffix

            # auto-fill BSX field if empty
            if det_plate and not slot["plate_var"].get():
                slot["plate_var"].set(det_plate)

            # always refresh display (handles case where plate_var already had a value)
            self._refresh_result_txt(slot_idx)
            # refresh other slot if already detected (update its diff highlighting)
            if other_idx in self._detected and self._detected[other_idx]:
                self._refresh_result_txt(other_idx)

            # auto-save if enabled
            if self._auto_save_var.get() and self._save_dir_var.get().strip():
                self._save_img(slot_idx)

            if on_done: on_done()

        threading.Thread(target=_call, daemon=True).start()

    # ══════════════════════════════════════════════════════════════════════════
    # ── STATE MANAGEMENT ─────────────────────────────────────────────────────

    def _event_key(self, rec: dict) -> str:
        return f"{rec['lane']}/{rec['reason']}/{rec['date']}/{rec['event_id']}"

    def _load_state(self):
        self._state_path = self.out_path / ".bad_viewer_state.json"
        if self._state_path.exists():
            try:
                self._state = json.loads(
                    self._state_path.read_text(encoding="utf-8"))
            except Exception:
                self._state = {}
        else:
            self._state = {}

    def _save_state(self):
        if self._state_path:
            try:
                self._state_path.write_text(
                    json.dumps(self._state, ensure_ascii=False, indent=2),
                    encoding="utf-8")
            except Exception:
                pass

    # ── STATUS MARK ──────────────────────────────────────────────────────────

    def _set_status(self, status: str):
        """Mark selected records as done/skip/'' and refresh tree."""
        sel = self._tree.selection()
        if not sel:
            return
        for iid in sel:
            rec = self._records[int(iid)]
            ek  = self._event_key(rec)
            if ek not in self._state:
                self._state[ek] = {}
            self._state[ek]["status"] = status
        self._save_state()
        self._apply_filter()

    def _toggle_done(self):
        rec = self._selected()
        if not rec:
            return
        ek     = self._event_key(rec)
        cur    = self._state.get(ek, {}).get("status", "")
        new_st = "" if cur == "done" else "done"
        if ek not in self._state:
            self._state[ek] = {}
        self._state[ek]["status"] = new_st
        self._save_state()
        self._apply_filter()

    def _on_tree_right_click(self, event):
        iid = self._tree.identify_row(event.y)
        if iid:
            if iid not in self._tree.selection():
                self._tree.selection_set(iid)
        self._tree_menu.post(event.x_root, event.y_root)

    # ── KEYBOARD SHORTCUTS ────────────────────────────────────────────────────

    def _detect_both(self):
        if not self._current_rec:
            return
        url = self._lpr_url_var.get().strip()
        if url and _REQUESTS_OK:
            self._lpr_check(1, on_done=lambda: self._lpr_check(2))

    def _save_both(self):
        self._save_img(1)
        self._save_img(2)

    # ── SCROLL ZOOM ───────────────────────────────────────────────────────────

    def _on_scroll_img(self, event, slot_idx: int):
        delta = getattr(event, "delta", 0)
        if delta == 0:
            delta = 120 if event.num == 4 else -120
        if delta > 0:
            self._zoom_factors[slot_idx] = min(
                self._zoom_factors[slot_idx] * 1.25, 10.0)
        else:
            self._zoom_factors[slot_idx] = max(
                self._zoom_factors[slot_idx] / 1.25, 0.1)
        rec = self._current_rec
        if not rec:
            return
        path = self._slot_path(rec, slot_idx)
        if not path:
            return
        slot = self._slot1 if slot_idx == 1 else self._slot2
        pw   = max(slot["img_lbl"].winfo_width()  - 4, 180)
        ph   = max(slot["img_lbl"].winfo_height() - 4, 100)
        z    = self._zoom_factors[slot_idx]
        photo = _load_photo(path, int(pw * z), int(ph * z))
        if photo:
            slot["_photo"] = photo
            slot["img_lbl"].config(image=photo, text="")

    # ── RIGHT-CLICK ON IMAGE ──────────────────────────────────────────────────

    def _on_right_click_img(self, event, slot_idx: int):
        rec = self._current_rec
        if not rec:
            return
        path = self._slot_path(rec, slot_idx)
        menu = Menu(self, tearoff=0, bg=CARD, fg=TEXT,
                    activebackground="#4A3F8C", activeforeground="white",
                    font=F_MAIN)
        if path:
            menu.add_command(label="Sao chép đường dẫn",
                             command=lambda p=path: self._copy_to_clipboard(p))
            menu.add_command(label="Mở vị trí trong Explorer",
                             command=lambda p=path: subprocess.Popen(
                                 ["explorer", "/select,", p]))
            menu.add_command(label="Mở bằng ứng dụng mặc định",
                             command=lambda p=path: subprocess.Popen(
                                 ["start", "", p], shell=True))
            menu.add_separator()
        menu.add_command(label="Đặt zoom về 100%",
                         command=lambda s=slot_idx: self._reset_zoom(s))
        menu.post(event.x_root, event.y_root)

    def _copy_to_clipboard(self, text: str):
        self.clipboard_clear()
        self.clipboard_append(text)

    def _reset_zoom(self, slot_idx: int):
        self._zoom_factors[slot_idx] = 1.0
        rec = self._current_rec
        if rec:
            path = self._slot_path(rec, slot_idx)
            if path:
                slot = self._slot1 if slot_idx == 1 else self._slot2
                pw = max(slot["img_lbl"].winfo_width()  - 4, 180)
                ph = max(slot["img_lbl"].winfo_height() - 4, 100)
                photo = _load_photo(path, pw, ph)
                if photo:
                    slot["_photo"] = photo
                    slot["img_lbl"].config(image=photo, text="")

    # ── SLIDESHOW ─────────────────────────────────────────────────────────────

    def _toggle_slideshow(self):
        if self._slideshow_active:
            self._stop_slideshow()
        else:
            self._start_slideshow()

    def _start_slideshow(self):
        self._slideshow_active = True
        self._btn_slideshow.config(text="⏹ Dừng")
        self._slideshow_step()

    def _stop_slideshow(self):
        self._slideshow_active = False
        self._btn_slideshow.config(text="▶ Chạy")
        if self._slideshow_after:
            self.after_cancel(self._slideshow_after)
            self._slideshow_after = None

    def _slideshow_step(self):
        if not self._slideshow_active:
            return
        items = self._tree.get_children()
        if not items:
            self._stop_slideshow()
            return
        sel = self._tree.selection()
        if sel:
            try:
                idx = items.index(sel[0])
            except ValueError:
                idx = -1
        else:
            idx = -1
        next_idx = idx + 1
        if next_idx >= len(items):
            self._stop_slideshow()
            return
        iid = items[next_idx]
        self._tree.selection_set(iid)
        self._tree.see(iid)
        self._on_select()
        delay = max(500, self._slideshow_delay_var.get() * 1000)
        self._slideshow_after = self.after(delay, self._slideshow_step)

    # ── BATCH DETECT ──────────────────────────────────────────────────────────

    def _batch_detect(self):
        url = self._lpr_url_var.get().strip()
        if not url or not _REQUESTS_OK:
            messagebox.showwarning("LPR", "Chưa cấu hình LPR URL hoặc thiếu thư viện requests")
            return
        items = self._tree.get_children()
        if not items:
            return
        records = [self._records[int(iid)] for iid in items]
        total   = len(records)
        self._btn_batch.config(state=DISABLED, text="Đang xử lý...")
        self._lbl_batch_progress.config(text=f"0/{total}")
        self._batch_cancel = False

        save_dir_str = self._save_dir_var.get().strip()
        auto_save    = bool(self._auto_save_var.get() and save_dir_str)

        def _run():
            for i, rec in enumerate(records):
                if self._batch_cancel:
                    break
                for slot_idx in (1, 2):
                    path = self._slot_path(rec, slot_idx)
                    if not path or not Path(path).exists():
                        continue
                    try:
                        with open(path, "rb") as fh:
                            data = fh.read()
                        resp = _req_mod.post(
                            url,
                            files={"upload": ("image.jpg", data, "image/jpeg")},
                            timeout=10)
                        resp.raise_for_status()
                        results = (resp.json().get("results")
                                   or resp.json().get("Results") or [])
                        if not results:
                            continue
                        plate = (results[0].get("Plate")
                                 or results[0].get("plate") or "").strip()
                        if not plate:
                            continue
                        ek        = self._event_key(rec)
                        plate_key = "plate_in" if slot_idx == 1 else "plate_out"
                        if ek not in self._state:
                            self._state[ek] = {}
                        self._state[ek][plate_key] = plate
                        if auto_save:
                            save_dir = Path(save_dir_str)
                            save_dir.mkdir(parents=True, exist_ok=True)
                            src = Path(path)
                            shutil.copy2(src, save_dir / src.name)
                            gt = save_dir / f"{src.stem}.txt"
                            gt.write_text(f"{src.stem}\t{plate}", encoding="utf-8")
                    except Exception:
                        pass
                self.after(0, lambda n=i+1: self._lbl_batch_progress.config(
                    text=f"{n}/{total}"))
            self._save_state()
            self.after(0, self._batch_done)

        threading.Thread(target=_run, daemon=True).start()

    def _batch_done(self):
        self._btn_batch.config(state=NORMAL, text="Nhận diện tất cả")
        self._lbl_batch_progress.config(text="✓ Hoàn tất")
        self._apply_filter()

    # ── BULK EXPORT GT ────────────────────────────────────────────────────────

    def _bulk_export_gt(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("Xuất GT",
                "Chưa chọn ảnh nào.\nCtrl+click hoặc Shift+click để chọn nhiều.")
            return
        save_dir_str = self._save_dir_var.get().strip()
        if not save_dir_str:
            save_dir_str = filedialog.askdirectory(title="Chọn folder lưu GT")
            if not save_dir_str:
                return
            self._save_dir_var.set(save_dir_str)
        save_dir = Path(save_dir_str)
        save_dir.mkdir(parents=True, exist_ok=True)
        ok = skip = 0
        for iid in sel:
            rec  = self._records[int(iid)]
            ek   = self._event_key(rec)
            rst  = self._state.get(ek, {})
            for slot_idx in (1, 2):
                path      = self._slot_path(rec, slot_idx)
                plate_key = "plate_in" if slot_idx == 1 else "plate_out"
                plate     = rst.get(plate_key) or rec.get(plate_key, "")
                if not path or not Path(path).exists() or not plate:
                    skip += 1
                    continue
                src = Path(path)
                shutil.copy2(src, save_dir / src.name)
                (save_dir / f"{src.stem}.txt").write_text(
                    f"{src.stem}\t{plate}", encoding="utf-8")
                ok += 1
        messagebox.showinfo("Xuất GT",
            f"Đã xuất {ok} ảnh + GT.\nBỏ qua {skip} (thiếu ảnh hoặc BSX).")

    # ── STATISTICS ────────────────────────────────────────────────────────────

    def _show_stats(self):
        win = Toplevel(self)
        win.title("Thống kê ảnh xấu")
        win.configure(bg=BG)
        win.geometry("640x540")
        win.resizable(True, True)

        by_reason: dict = {}
        by_lane:   dict = {}
        by_date:   dict = {}
        done_count = skip_count = saved_count = 0
        total = len(self._records)

        for rec in self._records:
            rl  = _REASON_LABEL.get(rec["reason"], rec["reason"])
            ek  = self._event_key(rec)
            rst = self._state.get(ek, {})
            by_reason[rl]         = by_reason.get(rl, 0)        + 1
            by_lane[rec["lane"]]  = by_lane.get(rec["lane"], 0) + 1
            by_date[rec["date"]]  = by_date.get(rec["date"], 0) + 1
            if rst.get("status") == "done": done_count += 1
            if rst.get("status") == "skip": skip_count += 1
            if rst.get("plate_in") or rst.get("plate_out"): saved_count += 1

        lines = [
            f"TỔNG: {total} sự kiện",
            f"  Đã Done   : {done_count}",
            f"  Đã Skip   : {skip_count}",
            f"  Đã lưu GT : {saved_count}",
            f"  Chưa xử lý: {total - done_count - skip_count}",
            "",
            "─── Theo lý do ───────────────────────",
        ]
        for k, v in sorted(by_reason.items(), key=lambda x: -x[1]):
            bar = "█" * min(v, 40)
            lines.append(f"  {k:<28} {v:>4}  {bar}")
        lines += ["", "─── Theo làn ─────────────────────────"]
        for k, v in sorted(by_lane.items(), key=lambda x: -x[1]):
            bar = "█" * min(v, 40)
            lines.append(f"  {k:<28} {v:>4}  {bar}")
        lines += ["", "─── Theo ngày (top 15) ───────────────"]
        for k, v in sorted(by_date.items(), key=lambda x: -x[1])[:15]:
            bar = "█" * min(v, 40)
            lines.append(f"  {k:<15} {v:>4}  {bar}")

        txt = Text(win, bg=CARD, fg=TEXT, font=("Consolas", 11),
                   padx=14, pady=10, relief="flat", bd=0)
        txt.pack(fill=BOTH, expand=True)
        txt.insert(END, "\n".join(lines))
        txt.config(state=DISABLED)

        def _export():
            p = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV", "*.csv")],
                title="Lưu thống kê")
            if not p:
                return
            with open(p, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(["Phân loại", "Giá trị", "Số lượng"])
                for k, v in by_reason.items():
                    w.writerow(["Lý do", k, v])
                for k, v in by_lane.items():
                    w.writerow(["Làn", k, v])
                for k, v in by_date.items():
                    w.writerow(["Ngày", k, v])
            messagebox.showinfo("OK", f"Đã lưu → {p}")

        Button(win, text="Xuất CSV", command=_export,
               bg=ACCENT, fg="white", font=F_MAIN,
               relief="flat", padx=14, pady=5).pack(pady=8)

    # ── EXPORT EDIT HISTORY ───────────────────────────────────────────────────

    def _export_history(self):
        rows = []
        for ek, st in self._state.items():
            for edit in st.get("edits", []):
                rows.append([
                    ek,
                    edit.get("file", ""),
                    edit.get("slot", ""),
                    edit.get("original", ""),
                    edit.get("corrected", ""),
                    edit.get("ts", ""),
                ])
        if not rows:
            messagebox.showinfo("Lịch sử", "Chưa có lịch sử chỉnh sửa nào.")
            return
        p = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            title="Xuất lịch sử chỉnh sửa")
        if not p:
            return
        with open(p, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["Event key", "File", "Slot", "Biển gốc", "Biển sửa", "Thời gian"])
            w.writerows(rows)
        messagebox.showinfo("OK", f"Đã lưu {len(rows)} dòng → {p}")
