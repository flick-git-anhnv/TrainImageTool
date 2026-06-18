"""
Giao diện tổng hợp ảnh theo round-robin buổi.
Cấu trúc nguồn: <src>/<loai_xe>/<anh_xe|anh_toan_canh|anh_bsx>/<ngày>/<sang|trua|chieu|toi>/<lan>/HHmmss_BSX.jpg
Cấu trúc đích : <dest>/<loai_xe>/<anh_xe|anh_toan_canh|anh_bsx>/<lan>/*.jpg
"""
import queue
import shutil
import threading
from datetime import datetime
from pathlib import Path
from tkinter import *
from tkinter import filedialog, ttk

from ...core.constants import BG, CARD, ACCENT, ACCENT2, TEXT, DIM, F_MAIN, F_BOLD, F_MONO
from ...core.settings import _bind_cfg

_EXCLUDED  = {"bad", "train", "out"}
_BUOI_ORDER = ["sang", "trua", "chieu", "toi"]


# ── core logic ────────────────────────────────────────────────────────────────

def _scan_source(src: Path) -> dict:
    """
    Quét thư mục nguồn — hỗ trợ tất cả cấu trúc cũ/mới.
    Trả về: {key: {sub_folder: {buoi: [Path, ...]}}}
      key = "loai_xe/lan" (cấu trúc mới) hoặc "loai_xe" (cấu trúc cũ)
    """
    result: dict = {}
    if not src.exists():
        return result
    for img in sorted(src.rglob("*.jpg")):
        try:
            parts = img.relative_to(src).parts
            if parts[0] in _EXCLUDED:
                continue
            if len(parts) == 6:
                p0, p1, p2, p3, p4, _ = parts
                if p1.startswith("anh_"):
                    # cấu trúc mới: <loai_xe>/<sub>/<date>/<buoi>/<lan>/<file>
                    vtype_f, sub_f, _, p3b, lane_s, _ = parts
                    buoi = p3b if p3b in _BUOI_ORDER else None
                    if buoi is None:
                        continue
                    key = f"{vtype_f}/{lane_s}"
                else:
                    # cấu trúc cũ: <loai_xe>/<lan>/<sub>/<date>/<buoi>/<file>
                    vtype_f, lane_s, sub_f, _, p4b, _ = parts
                    buoi = p4b if p4b in _BUOI_ORDER else None
                    if buoi is None and p4b.isdigit() and 0 <= int(p4b) <= 23:
                        h = int(p4b)
                        buoi = ("sang" if h < 12 else "trua" if h < 14 else
                                "chieu" if h < 18 else "toi")
                    if buoi is None:
                        continue
                    key = f"{vtype_f}/{lane_s}"
            elif len(parts) == 5:
                # cấu trúc cũ: <loai_xe>/<sub>/<date>/<buoi|HH>/<file>
                p0, p1, _, p3, _ = parts
                vtype_f, sub_f = p0, p1
                buoi = p3 if p3 in _BUOI_ORDER else None
                if buoi is None and p3.isdigit() and 0 <= int(p3) <= 23:
                    h = int(p3)
                    buoi = ("sang" if h < 12 else "trua" if h < 14 else
                            "chieu" if h < 18 else "toi")
                if buoi is None:
                    continue
                key = vtype_f
            elif len(parts) == 4:
                p0, p1, _, fname = parts
                h_str = fname[:2]
                if not h_str.isdigit():
                    continue
                h = int(h_str)
                if not 0 <= h <= 23:
                    continue
                vtype_f, sub_f = p0, p1
                buoi = ("sang" if h < 12 else "trua" if h < 14 else
                        "chieu" if h < 18 else "toi")
                key = vtype_f
            else:
                continue
            (result
             .setdefault(key, {})
             .setdefault(sub_f, {})
             .setdefault(buoi, [])
             .append(img))
        except Exception:
            continue
    return result


def _round_robin_select(buoi_data: dict, max_count: int) -> list:
    """
    Chọn ảnh theo vòng round-robin qua các buổi (sang/trua/chieu/toi).
    buoi_data: {buoi_str: [Path, ...]}
    Trả về:    [Path, ...]
    """
    limit    = max_count if max_count > 0 else float("inf")
    selected = []
    keys     = [b for b in _BUOI_ORDER if b in buoi_data]
    if not keys:
        keys = sorted(buoi_data.keys())
    ptr  = {b: 0 for b in keys}

    while len(selected) < limit:
        made = False
        for b in keys:
            if len(selected) >= limit:
                break
            lst = buoi_data.get(b, [])
            if ptr[b] < len(lst):
                selected.append(lst[ptr[b]])
                ptr[b] += 1
                made = True
        if not made:
            break
    return selected


# ── window ────────────────────────────────────────────────────────────────────

class ConsolidateWindow(Toplevel):

    def __init__(self, root, src_path: Path):
        super().__init__(root)
        self.title("Tổng hợp ảnh")
        self.configure(bg=BG)
        self.geometry("1050x740")
        self.resizable(True, True)

        self._src      = Path(src_path)
        self._data: dict = {}
        self._log_q    = queue.Queue()
        self._running  = False

        self._dest_var = StringVar(value=str(self._src / "out"))
        self._max_var  = IntVar(value=100)
        _bind_cfg("consolidate.dest", self._dest_var)
        _bind_cfg("consolidate.max",  self._max_var)

        self._build()
        # rebuild table khi max thay đổi (debounced)
        self._max_var.trace_add("write", lambda *_: self.after(350, self._rebuild_table))
        self._scan()
        self.after(200, self._poll)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _sep(self, parent, text):
        f = Frame(parent, bg=BG)
        f.pack(fill=X, pady=(8, 3))
        Label(f, text=text, font=("Segoe UI", 9, "bold"),
              fg=ACCENT2, bg=BG).pack(side=LEFT)
        Frame(f, bg=DIM, height=1).pack(
            side=LEFT, fill=X, expand=True, padx=(8, 0), pady=5)

    def _build(self):
        body = Frame(self, bg=BG, padx=14, pady=8)
        body.pack(fill=BOTH, expand=True)

        # ── Cấu hình ──────────────────────────────────────────────────────────
        self._sep(body, "Cấu hình")
        cfg = Frame(body, bg=BG)
        cfg.pack(fill=X)

        r0 = Frame(cfg, bg=BG)
        r0.pack(fill=X, pady=2)
        Label(r0, text="Nguồn:", bg=BG, fg=TEXT, font=F_MAIN, width=10, anchor=W).pack(side=LEFT)
        Entry(r0, textvariable=StringVar(value=str(self._src)), state="readonly",
              bg=CARD, fg=DIM, relief="flat", font=F_MAIN, bd=4).pack(
            side=LEFT, fill=X, expand=True)

        r1 = Frame(cfg, bg=BG)
        r1.pack(fill=X, pady=2)
        Label(r1, text="Lưu vào:", bg=BG, fg=TEXT, font=F_MAIN, width=10, anchor=W).pack(side=LEFT)
        Entry(r1, textvariable=self._dest_var,
              bg=CARD, fg=TEXT, insertbackground=TEXT,
              relief="flat", font=F_MAIN, bd=4).pack(
            side=LEFT, fill=X, expand=True, padx=(0, 8))
        Button(r1, text="Chọn…", command=self._browse_dest,
               bg=ACCENT2, fg="white", font=F_MAIN,
               activebackground=ACCENT, activeforeground="white",
               relief="flat", padx=10, cursor="hand2").pack(side=LEFT)

        r2 = Frame(cfg, bg=BG)
        r2.pack(fill=X, pady=4)
        Label(r2, text="Max ảnh/loại:", bg=BG, fg=TEXT, font=F_MAIN).pack(side=LEFT)
        Spinbox(r2, from_=0, to=99999, textvariable=self._max_var,
                width=8, font=F_MAIN, bg=CARD, fg=TEXT,
                insertbackground=TEXT, buttonbackground=ACCENT2,
                relief="flat",
                command=self._rebuild_table).pack(side=LEFT, padx=(4, 12))
        Label(r2,
              text="(0 = không giới hạn)   •   Mỗi loại xe / phân loại lấy tối đa N ảnh, trải đều qua các buổi",
              bg=BG, fg=DIM, font=("Segoe UI", 8)).pack(side=LEFT)
        Button(r2, text="↻  Làm mới", command=self._scan,
               bg=CARD, fg=TEXT, font=F_MAIN,
               activebackground=ACCENT2, activeforeground="white",
               relief="flat", padx=12, cursor="hand2").pack(side=RIGHT)

        # ── Bảng tổng hợp ─────────────────────────────────────────────────────
        self._sep(body, "Bảng tổng hợp nguồn")
        tbl = Frame(body, bg=BG)
        tbl.pack(fill=BOTH, expand=True)
        tbl.columnconfigure(0, weight=1)
        tbl.rowconfigure(0, weight=1)

        s = ttk.Style()
        s.configure("C.Treeview",
                    background="#1e1e2e", foreground="#d4d4d4",
                    fieldbackground="#1e1e2e", rowheight=22, font=F_MONO)
        s.configure("C.Treeview.Heading",
                    background="#251C53", foreground="white",
                    font=("Segoe UI", 9, "bold"))
        s.map("C.Treeview", background=[("selected", "#4A3F8C")])

        cols = ("vtype_f", "sub_f", "buoi", "avail", "take")
        self._tree = ttk.Treeview(tbl, columns=cols, show="headings",
                                   style="C.Treeview")
        for col, hdr, w, anch in [
            ("vtype_f", "Loại xe",   160, "w"),
            ("sub_f",   "Phân loại", 130, "center"),
            ("buoi",    "Buổi",       80, "center"),
            ("avail",   "Có sẵn",     80, "center"),
            ("take",    "Sẽ lấy",     80, "center"),
        ]:
            self._tree.heading(col, text=hdr)
            self._tree.column(col, width=w, minwidth=w, anchor=anch)

        self._tree.tag_configure("odd",   background="#16162a")
        self._tree.tag_configure("even",  background="#1e1e2e")
        self._tree.tag_configure("total", background="#251C53", foreground="white")
        self._tree.tag_configure("full",  foreground="#7fffaa")  # lấy hết

        vsb = ttk.Scrollbar(tbl, orient=VERTICAL,   command=self._tree.yview)
        hsb = ttk.Scrollbar(tbl, orient=HORIZONTAL, command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self._tree.grid(row=0, column=0, sticky=NSEW)
        vsb.grid(row=0, column=1, sticky=NS)
        hsb.grid(row=1, column=0, sticky=EW)

        # ── Controls ──────────────────────────────────────────────────────────
        ctrl = Frame(body, bg=BG)
        ctrl.pack(fill=X, pady=(8, 0))

        self._run_btn = Button(
            ctrl, text="▶  Tổng hợp", command=self._run,
            bg=ACCENT, fg="white", font=F_BOLD,
            activebackground="#c04010", activeforeground="white",
            relief="flat", padx=22, pady=7, cursor="hand2")
        self._run_btn.pack(side=LEFT, padx=(0, 8))
        Button(ctrl, text="Mở folder đích", command=self._open_dest,
               bg=ACCENT2, fg="white", font=F_MAIN,
               activebackground="#5a4fa0", activeforeground="white",
               relief="flat", padx=14, pady=4, cursor="hand2").pack(side=LEFT)
        self._status_lbl = Label(ctrl, text="Đang quét...",
                                  fg=DIM, bg=BG, font=F_MAIN)
        self._status_lbl.pack(side=RIGHT)

        # ── Log ───────────────────────────────────────────────────────────────
        self._sep(body, "Nhật ký")
        log_f = Frame(body, bg=BG)
        log_f.pack(fill=X)
        log_f.columnconfigure(0, weight=1)

        self._log_txt = Text(log_f, height=7, font=F_MONO,
                              bg="#16162a", fg="#d4d4d4",
                              relief="flat", wrap=WORD,
                              insertbackground="#d4d4d4", state=DISABLED)
        self._log_txt.grid(row=0, column=0, sticky=EW)
        lsb = ttk.Scrollbar(log_f, command=self._log_txt.yview)
        lsb.grid(row=0, column=1, sticky=NS)
        self._log_txt["yscrollcommand"] = lsb.set

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _browse_dest(self):
        d = filedialog.askdirectory(title="Chọn thư mục lưu ảnh tổng hợp",
                                     initialdir=self._dest_var.get())
        if d:
            self._dest_var.set(d)

    def _open_dest(self):
        import subprocess
        p = Path(self._dest_var.get())
        p.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(["explorer", str(p)])

    def _log_append(self, msg: str):
        self._log_txt.configure(state=NORMAL)
        ts = datetime.now().strftime("%H:%M:%S")
        self._log_txt.insert(END, f"[{ts}] {msg}\n")
        self._log_txt.see(END)
        self._log_txt.configure(state=DISABLED)

    def _poll(self):
        try:
            while True:
                msg = self._log_q.get_nowait()
                if msg == "__DONE__":
                    self._on_done()
                else:
                    self._log_append(msg)
        except queue.Empty:
            pass
        if self.winfo_exists():
            self.after(200, self._poll)

    def _on_done(self):
        self._running = False
        self._run_btn.config(state=NORMAL)
        self._status_lbl.config(text="Hoàn thành", fg=ACCENT2)

    # ── Scan & table ──────────────────────────────────────────────────────────

    def _scan(self):
        self._status_lbl.config(text="Đang quét...", fg=DIM)
        self.update_idletasks()
        self._data = _scan_source(self._src)
        self._rebuild_table()

    def _rebuild_table(self, *_):
        self._tree.delete(*self._tree.get_children())
        max_n       = self._max_var.get()
        row_idx     = 0
        grand_avail = 0
        grand_take  = 0

        for vtype_f in sorted(self._data):
            sub_data = self._data[vtype_f]

            # Tính preview round-robin per sub_folder (không thay đổi dữ liệu gốc)
            take_cnt: dict = {}  # {(sub_f, buoi): count}
            for sub_f, buois in sub_data.items():
                for path in _round_robin_select(buois, max_n):
                    buoi = path.parent.name
                    k    = (sub_f, buoi)
                    take_cnt[k] = take_cnt.get(k, 0) + 1

            vtype_avail = 0
            vtype_take  = 0
            for sub_f in sorted(sub_data):
                buoi_order = [b for b in _BUOI_ORDER if b in sub_data[sub_f]]
                for buoi in buoi_order:
                    avail = len(sub_data[sub_f][buoi])
                    take  = take_cnt.get((sub_f, buoi), 0)
                    base  = "odd" if row_idx % 2 == 0 else "even"
                    tags  = (base, "full") if (take > 0 and take >= avail) else (base,)
                    self._tree.insert("", END, tags=tags,
                                      values=(vtype_f, sub_f, buoi, avail, take))
                    vtype_avail += avail
                    vtype_take  += take
                    row_idx     += 1

            self._tree.insert("", END, tags=("total",),
                               values=(f"  ∑ {vtype_f}", "", "",
                                       vtype_avail, vtype_take))
            row_idx     += 1
            grand_avail += vtype_avail
            grand_take  += vtype_take

        if grand_avail:
            self._tree.insert("", END, tags=("total",),
                               values=("TỔNG", "", "", grand_avail, grand_take))

        self._status_lbl.config(
            text=f"{len(self._data)} loại xe  |  {grand_avail} ảnh có sẵn  |  Sẽ lấy: {grand_take}",
            fg=ACCENT2)

    # ── Run ───────────────────────────────────────────────────────────────────

    def _run(self):
        dest  = Path(self._dest_var.get().strip())
        max_n = self._max_var.get()
        if not dest:
            return

        self._running = True
        self._run_btn.config(state=DISABLED)
        self._status_lbl.config(text="Đang tổng hợp...", fg=ACCENT)
        self._log_append("─" * 48)
        self._log_append(f"Đích: {dest}  |  max {max_n}/loại")

        data_snap = self._data

        def _worker():
            total  = 0
            errors = 0
            counts: dict = {}
            gt_cache: dict = {}  # {source_dir: {filename: plate}}

            def _load_gt(src_dir: Path) -> dict:
                if src_dir in gt_cache:
                    return gt_cache[src_dir]
                mapping = {}
                gt_file = src_dir / "gt.txt"
                if gt_file.exists():
                    try:
                        for line in gt_file.read_text(encoding="utf-8").splitlines():
                            parts = line.split("\t", 1)
                            if len(parts) == 2:
                                mapping[parts[0].strip()] = parts[1].strip()
                    except Exception:
                        pass
                gt_cache[src_dir] = mapping
                return mapping

            for vtype_f in sorted(data_snap):
                vtype_total = 0
                # key có dạng "loai_xe/lan" (mới) hoặc "loai_xe" (cũ)
                _kparts = vtype_f.split("/", 1)
                for sub_f, buois in sorted(data_snap[vtype_f].items()):
                    selected = _round_robin_select(buois, max_n)
                    for img_path in selected:
                        try:
                            if len(_kparts) == 2:
                                d = dest / _kparts[0] / sub_f / _kparts[1]
                            else:
                                d = dest / vtype_f / sub_f
                            d.mkdir(parents=True, exist_ok=True)
                            dst = d / img_path.name
                            idx = 0
                            while dst.exists():
                                idx += 1
                                dst  = d / f"{img_path.stem}_{idx:03d}.jpg"
                            shutil.copy2(img_path, dst)
                            plate = _load_gt(img_path.parent).get(img_path.name)
                            if plate:
                                with open(d / "gt.txt", "a", encoding="utf-8") as _f:
                                    _f.write(f"{dst.name}\t{plate}\n")
                            key = f"{vtype_f}/{sub_f}"
                            counts[key] = counts.get(key, 0) + 1
                            total += 1
                            vtype_total += 1
                        except Exception:
                            errors += 1
                self._log_q.put(f"  {vtype_f}: {vtype_total} ảnh")

            self._log_q.put(f"Hoàn thành: {total} ảnh → {dest}")
            for vt, n in sorted(counts.items()):
                self._log_q.put(f"  {vt:20s}: {n} ảnh")
            if errors:
                self._log_q.put(f"  Lỗi bỏ qua: {errors}")
            self._log_q.put("__DONE__")

        threading.Thread(target=_worker, daemon=True).start()
