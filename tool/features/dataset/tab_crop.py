import csv
import os
import threading
from pathlib import Path
from tkinter import *
from tkinter import filedialog, messagebox, ttk

from ...core.constants import BG, CARD, ACCENT, ACCENT2, TEXT, DIM, F_MAIN, F_BOLD
from ...core.settings import _bind_cfg, _bind_history, _push_history, _get_history
from .core_crop import run_crop_by_label
from ...core.ui_helpers import (
    _folder_row, _pb_row, _make_logbox, _append_log,
    _set_progress, _action_btn,
)

try:
    from PIL import Image as _PILImage, ImageTk as _ImageTk
    _PIL_OK = True
except ImportError:
    _PIL_OK = False


_PREVIEW_W = 220
_PREVIEW_H = 180


class CropByLabelTab(Frame):
    def __init__(self, master, root):
        super().__init__(master, bg=BG)
        self.root = root
        self._stop_event = threading.Event()
        self._class_vars = {}
        self._last_stats = None
        self._preview_photo = None
        self._build()

    def _build(self):
        top = Frame(self, bg=BG, padx=20, pady=12)
        top.pack(fill=X)
        self.v_img = StringVar(); self.v_lbl = StringVar(); self.v_out = StringVar()
        _bind_cfg("crop.img", self.v_img)
        _bind_cfg("crop.lbl", self.v_lbl)
        _bind_cfg("crop.out", self.v_out)
        _folder_row(top, "📁  Thư mục ảnh",         self.v_img, 0, history_key="h.crop.img")
        _folder_row(top, "🏷  Thư mục label (.txt)", self.v_lbl, 1, history_key="h.crop.lbl")
        _folder_row(top, "💾  Thư mục output",       self.v_out, 2, history_key="h.crop.out")

        cr = Frame(top, bg=BG)
        cr.grid(row=3, column=0, columnspan=3, sticky=EW, pady=(8, 0))
        Label(cr, text="Danh sách nhãn:", bg=BG, fg=DIM,
              font=F_MAIN, width=26, anchor=W).pack(side=LEFT)
        self.v_classes = StringVar(
            value="car, motorbike, bus, truck, bicycle, license_plate")
        _bind_cfg("crop.classes", self.v_classes)
        _cls_combo = ttk.Combobox(cr, textvariable=self.v_classes,
                                   style="Dark.TCombobox", font=F_MAIN)
        _cls_combo.pack(side=LEFT, fill=X, expand=True, padx=(8, 0))
        _bind_history("h.crop.classes", _cls_combo)
        Button(cr, text="Cập nhật ↺", command=self._refresh_classes,
               bg=ACCENT2, fg="white", activebackground=ACCENT,
               activeforeground="white", font=F_MAIN, relief="flat",
               padx=10, cursor="hand2").pack(side=LEFT, padx=(6, 0))

        mid = Frame(self, bg=BG, padx=20)
        mid.pack(fill=X, pady=(0, 4))
        mid.columnconfigure(0, weight=3)
        mid.columnconfigure(1, weight=2)
        mid.columnconfigure(2, weight=0)

        cls_f = LabelFrame(mid, text=" Nhãn lớp cần crop ",
                           bg=BG, fg=TEXT, font=F_BOLD, bd=1, relief="groove")
        cls_f.grid(row=0, column=0, sticky=NSEW, padx=(0, 8), pady=4)
        self._class_frame = Frame(cls_f, bg=BG)
        self._class_frame.pack(anchor=W, padx=10, pady=8)

        cfg_f = LabelFrame(mid, text=" Tùy chọn ",
                           bg=BG, fg=TEXT, font=F_BOLD, bd=1, relief="groove")
        cfg_f.grid(row=0, column=1, sticky=NSEW, pady=4)
        self._build_opts(cfg_f)

        prev_f = LabelFrame(mid, text=" Xem trước crop ",
                            bg=BG, fg=TEXT, font=F_BOLD, bd=1, relief="groove")
        prev_f.grid(row=0, column=2, sticky=NSEW, padx=(8, 0), pady=4)
        self._build_preview_panel(prev_f)

        btn_row = Frame(self, bg=BG, padx=20, pady=6)
        self.btn_run = _action_btn(btn_row, "✂  Bắt đầu Crop", self._run, ACCENT,
                                   padx=20, pady=7)
        self.btn_run.pack(side=LEFT)
        self.btn_stop = _action_btn(btn_row, "⏹  Dừng", self._stop, "#c0392b",
                                    padx=14, pady=7)
        self.btn_stop.pack(side=LEFT, padx=(8, 0))
        self.btn_stop.config(state=DISABLED)
        _action_btn(btn_row, "🔄  Xóa tiến độ", self._reset_state, ACCENT2,
                    padx=14, pady=7).pack(side=LEFT, padx=(8, 0))
        _action_btn(btn_row, "📂  Mở output", self._open_out, ACCENT2,
                    padx=14, pady=7).pack(side=LEFT, padx=(8, 0))
        self.btn_stats = _action_btn(btn_row, "📊  Thống kê", self._show_stats, ACCENT2,
                                     padx=14, pady=7)
        self.btn_stats.pack(side=LEFT, padx=(8, 0))
        self.btn_stats.config(state=DISABLED)
        Button(btn_row, text="🧹  Xóa log",
               command=lambda: (self.log.configure(state=NORMAL),
                                self.log.delete("1.0", END),
                                self.log.configure(state=DISABLED)),
               bg=CARD, fg=DIM, font=F_MAIN, relief="flat",
               padx=14, pady=7, cursor="hand2").pack(side=RIGHT)

        pb_f = Frame(self, bg=BG, padx=20)
        self.pb_lbl, self.pb = _pb_row(pb_f)

        log_outer = Frame(self, bg=BG, padx=20)
        log_f, self.log = _make_logbox(log_outer)
        log_f.pack(fill=BOTH, expand=True)

        btn_row.pack(fill=X, side=BOTTOM)
        pb_f.pack(fill=X, side=BOTTOM)
        log_outer.pack(fill=BOTH, expand=True)

        self._refresh_classes()

        self.v_img.trace_add("write", lambda *_: self._refresh_file_list())
        self.v_lbl.trace_add("write", lambda *_: self._refresh_file_list())

    def _build_preview_panel(self, parent):
        list_f = Frame(parent, bg=BG)
        list_f.pack(fill=BOTH, expand=True, padx=6, pady=(6, 2))

        sb = Scrollbar(list_f, bg=CARD, troughcolor=BG, relief="flat")
        sb.pack(side=RIGHT, fill=Y)
        self._file_listbox = Listbox(
            list_f, bg="#16162a", fg=TEXT, selectbackground=ACCENT2,
            selectforeground="white", font=("Consolas", 8),
            relief="flat", bd=0, activestyle="none",
            yscrollcommand=sb.set, width=22, height=6,
        )
        self._file_listbox.pack(side=LEFT, fill=BOTH, expand=True)
        sb.config(command=self._file_listbox.yview)
        self._file_listbox.bind("<<ListboxSelect>>", self._on_file_select)

        self._preview_canvas = Canvas(
            parent, bg="#16162a",
            width=_PREVIEW_W, height=_PREVIEW_H,
            bd=0, highlightthickness=0,
        )
        self._preview_canvas.pack(padx=6, pady=(2, 6))
        self._preview_pil_full = None
        self._preview_img_path = None
        self._preview_lbl_path = None
        self._preview_canvas.bind("<Double-Button-1>", self._on_preview_zoom)
        self._preview_canvas.create_text(
            _PREVIEW_W // 2, _PREVIEW_H // 2,
            text="(chọn ảnh để xem)", fill=DIM, font=("Consolas", 8),
        )

        self._preview_info = Label(
            parent, bg=BG, fg=DIM, font=("Consolas", 8), text="", anchor=W,
        )
        self._preview_info.pack(fill=X, padx=6, pady=(0, 4))

        Button(parent, text="↺ Làm mới", command=self._refresh_file_list,
               bg=CARD, fg=DIM, font=F_MAIN, relief="flat",
               padx=8, pady=3, cursor="hand2").pack(pady=(0, 4))

    def _on_preview_zoom(self, _event=None):
        if self._preview_pil_full is None:
            return
        from ...core.ui_helpers import _zoom_image_window, _load_label_bboxes
        bboxes = (_load_label_bboxes(self._preview_img_path, self._preview_lbl_path)
                  if self._preview_img_path else None)
        _zoom_image_window(self.root, self._preview_pil_full, "Phóng to ảnh gốc",
                           bboxes=bboxes)

    def _set_preview_msg(self, msg):
        self._preview_canvas.delete("all")
        self._preview_canvas.create_text(
            _PREVIEW_W // 2, _PREVIEW_H // 2,
            text=msg, fill=DIM, font=("Consolas", 8), width=_PREVIEW_W - 8,
        )

    def _build_opts(self, p):
        def _row(label, var, unit="", row=0, w=6):
            Label(p, text=label, bg=BG, fg=DIM, font=F_MAIN).grid(
                row=row, column=0, sticky=W, padx=10, pady=4)
            f = Frame(p, bg=BG); f.grid(row=row, column=1, sticky=W, padx=4)
            Entry(f, textvariable=var, width=w, bg=CARD, fg=TEXT,
                  insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4).pack(side=LEFT)
            if unit:
                Label(f, text=unit, bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT, padx=3)

        r = 0
        self.v_padding = IntVar(value=0)
        _row("Padding (mở rộng crop):", self.v_padding, "px", r); r += 1
        self.v_min_w = IntVar(value=0)
        _row("Crop tối thiểu (rộng):", self.v_min_w, "px", r); r += 1
        self.v_min_h = IntVar(value=0)
        _row("Crop tối thiểu (cao):", self.v_min_h, "px", r); r += 1
        self.v_quality = IntVar(value=95)
        _row("JPEG quality:", self.v_quality, "(1–100)", r); r += 1

        Frame(p, bg=CARD, height=1).grid(row=r, column=0, columnspan=2,
                                          sticky=EW, padx=10, pady=6); r += 1

        self.v_by_class = BooleanVar(value=True)
        Checkbutton(p, text="Chia subfolder theo từng nhãn",
                    variable=self.v_by_class, bg=BG, fg=TEXT,
                    activebackground=BG, activeforeground=TEXT,
                    selectcolor=CARD, font=F_MAIN).grid(
                    row=r, column=0, columnspan=2, sticky=W, padx=10, pady=2); r += 1

        self.v_filter_cls = BooleanVar(value=False)
        Checkbutton(p, text="Chỉ crop các nhãn đã tích",
                    variable=self.v_filter_cls, bg=BG, fg=TEXT,
                    activebackground=BG, activeforeground=TEXT,
                    selectcolor=CARD, font=F_MAIN).grid(
                    row=r, column=0, columnspan=2, sticky=W, padx=10, pady=2); r += 1

        self.v_recursive = BooleanVar(value=False)
        Checkbutton(p, text="Quét tất cả subfolder (đệ quy)",
                    variable=self.v_recursive, bg=BG, fg=TEXT,
                    activebackground=BG, activeforeground=TEXT,
                    selectcolor=CARD, font=F_MAIN).grid(
                    row=r, column=0, columnspan=2, sticky=W, padx=10, pady=2)

    def _refresh_classes(self):
        for w in self._class_frame.winfo_children():
            w.destroy()
        self._class_vars.clear()
        names = [n.strip() for n in
                 self.v_classes.get().replace(";", ",").split(",") if n.strip()]
        for i, name in enumerate(names):
            v = BooleanVar(value=True)
            self._class_vars[i] = (name, v)
            Checkbutton(self._class_frame, text=name, variable=v,
                        bg=BG, fg=TEXT, activebackground=BG,
                        activeforeground=TEXT, selectcolor=CARD,
                        font=F_MAIN).grid(row=i // 3, column=i % 3,
                                          sticky=W, padx=6, pady=2)

    def _refresh_file_list(self):
        img_dir = self.v_img.get().strip()
        self._file_listbox.delete(0, END)
        self._set_preview_msg("(chọn ảnh để xem)")
        self._preview_info.config(text="")
        if not img_dir or not Path(img_dir).is_dir():
            return
        from ...core.constants import IMAGE_EXTENSIONS
        files = sorted(
            f.name for f in Path(img_dir).iterdir()
            if f.suffix.lower() in IMAGE_EXTENSIONS
        )
        for name in files:
            self._file_listbox.insert(END, name)

    def _on_file_select(self, event=None):
        sel = self._file_listbox.curselection()
        if not sel:
            return
        fname = self._file_listbox.get(sel[0])
        img_dir = self.v_img.get().strip()
        lbl_dir = self.v_lbl.get().strip()
        if not img_dir or not lbl_dir:
            return
        img_path = Path(img_dir) / fname
        lbl_path = Path(lbl_dir) / (Path(fname).stem + ".txt")
        self._render_preview(img_path, lbl_path)

    def _render_preview(self, img_path, lbl_path):
        if not _PIL_OK:
            self._set_preview_msg("PIL không khả dụng")
            return
        if not img_path.exists():
            self._set_preview_msg("Ảnh không tồn tại")
            return

        try:
            img = _PILImage.open(img_path).convert("RGB")
            iw, ih = img.size
        except Exception as e:
            self._set_preview_msg(f"Lỗi ảnh:\n{e}")
            return
        self._preview_pil_full = img
        self._preview_img_path = img_path
        self._preview_lbl_path = lbl_path

        if not lbl_path.exists():
            self._set_preview_msg("Không có label")
            self._preview_info.config(text=f"{img_path.name}  {iw}×{ih}")
            return

        import math as _math
        boxes = []
        try:
            with open(lbl_path, encoding="utf-8") as f:
                for line in f:
                    p = line.strip().split()
                    if len(p) >= 5:
                        vals = list(map(float, p[1:5]))
                        if not any(_math.isnan(v) or _math.isinf(v) for v in vals):
                            boxes.append((int(p[0]), *vals))
        except Exception:
            pass

        if not boxes:
            self._set_preview_msg("Label rỗng")
            self._preview_info.config(text=f"{img_path.name}  {iw}×{ih}")
            return

        keep_cls = None
        if self.v_filter_cls.get():
            keep_cls = {i for i, (_, v) in self._class_vars.items() if v.get()}

        box = None
        for cid, xc, yc, bw, bh in boxes:
            if keep_cls is not None and cid not in keep_cls:
                continue
            box = (cid, xc, yc, bw, bh)
            break

        if box is None:
            box = boxes[0]

        cid, xc, yc, bw, bh = box
        x1 = max(0,  int((xc - bw/2) * iw))
        y1 = max(0,  int((yc - bh/2) * ih))
        x2 = min(iw, int((xc + bw/2) * iw))
        y2 = min(ih, int((yc + bh/2) * ih))

        try:
            pad = self.v_padding.get()
        except Exception:
            pad = 0
        if pad:
            x1 = max(0, x1 - pad)
            y1 = max(0, y1 - pad)
            x2 = min(iw, x2 + pad)
            y2 = min(ih, y2 + pad)

        cw, ch = x2 - x1, y2 - y1
        if cw <= 0 or ch <= 0:
            self._set_preview_msg("Bbox không hợp lệ")
            return

        crop = img.crop((x1, y1, x2, y2))

        scale = min(_PREVIEW_W / cw, _PREVIEW_H / ch, 1.0)
        disp_w = max(1, int(cw * scale))
        disp_h = max(1, int(ch * scale))
        crop_disp = crop.resize((disp_w, disp_h), _PILImage.LANCZOS)

        canvas = _PILImage.new("RGB", (_PREVIEW_W, _PREVIEW_H), (22, 22, 46))
        ox = (_PREVIEW_W - disp_w) // 2
        oy = (_PREVIEW_H - disp_h) // 2
        canvas.paste(crop_disp, (ox, oy))

        self._preview_photo = _ImageTk.PhotoImage(canvas)
        self._preview_canvas.delete("all")
        self._preview_canvas.create_image(0, 0, anchor=NW, image=self._preview_photo)

        class_map = {i: name for i, (name, _) in self._class_vars.items()}
        cname = class_map.get(cid, f"class{cid}")
        self._preview_info.config(
            text=f"{cname}  {cw}×{ch}px  ({len(boxes)} bbox)"
        )

    def _get_cfg(self):
        keep_ids  = [i for i, (_, v) in self._class_vars.items() if v.get()]
        class_map = {i: name for i, (name, _) in self._class_vars.items()}
        return {
            "image_dir":      self.v_img.get().strip(),
            "label_dir":      self.v_lbl.get().strip(),
            "output_dir":     self.v_out.get().strip(),
            "filter_classes": self.v_filter_cls.get(),
            "keep_classes":   keep_ids,
            "class_names_map": class_map,
            "padding_px":     self.v_padding.get(),
            "min_w_px":       self.v_min_w.get(),
            "min_h_px":       self.v_min_h.get(),
            "jpeg_quality":   self.v_quality.get(),
            "split_by_class": self.v_by_class.get(),
            "recursive":      self.v_recursive.get(),
        }

    def _run(self):
        cfg = self._get_cfg()
        if not cfg["image_dir"] or not cfg["label_dir"] or not cfg["output_dir"]:
            messagebox.showwarning("Thiếu thông tin", "Vui lòng chọn đủ 3 thư mục."); return
        self._stop_event.clear()
        self._last_stats = None
        self.btn_run.config(state=DISABLED, text="⏳  Đang xử lý…")
        self.btn_stop.config(state=NORMAL)
        self.btn_stats.config(state=DISABLED)
        self.pb["value"] = 0; self.pb_lbl.config(text="Đang khởi động…")

        def worker():
            result = None
            try:
                result = run_crop_by_label(
                    cfg,
                    log=lambda m: self.root.after(0, _append_log, self.log, m),
                    progress=lambda d, t: self.root.after(
                        0, _set_progress, self.pb_lbl, self.pb, d, t, self.root),
                    stop_event=self._stop_event)
            except Exception as e:
                self.root.after(0, _append_log, self.log, f"[LỖI] {e}")
            finally:
                def _done():
                    self.btn_run.config(state=NORMAL, text="✂  Bắt đầu Crop")
                    self.btn_stop.config(state=DISABLED)
                    self.pb_lbl.config(text="✅  Hoàn thành!")
                    if result and result.get("class_stats"):
                        self._last_stats = result
                        self.btn_stats.config(state=NORMAL)
                self.root.after(0, _done)

        threading.Thread(target=worker, daemon=True).start()

    def _stop(self):
        self._stop_event.set()
        self.btn_stop.config(state=DISABLED)
        _append_log(self.log, "⚠  Đang dừng sau ảnh hiện tại…")

    def _browse(self):
        """Ctrl+O — mở hộp thoại chọn thư mục ảnh."""
        from tkinter import filedialog
        from ...core.settings import _cfg_dir, _push_history
        p = filedialog.askdirectory(title="Chọn thư mục ảnh",
                                    initialdir=_cfg_dir("crop.img"))
        if p:
            self.v_img.set(p)
            _push_history("h.crop.img", p)

    def _reset_state(self):
        out = self.v_out.get().strip()
        if not out:
            messagebox.showwarning("Chưa chọn output", "Chọn thư mục output trước."); return
        sf = Path(out) / ".crop_by_label_state.json"
        if sf.exists():
            sf.unlink()
            _append_log(self.log, "🔄  Đã xóa tiến độ. Lần chạy tiếp sẽ xử lý lại từ đầu.")
        else:
            _append_log(self.log, "ℹ  Không có file tiến độ.")

    def _open_out(self):
        p = self.v_out.get().strip()
        if p and Path(p).exists():
            os.startfile(p)
        else:
            messagebox.showwarning("Chưa có output", "Chọn hoặc chạy xong để mở thư mục.")

    def _show_stats(self):
        if not self._last_stats:
            messagebox.showinfo("Thống kê", "Chưa có dữ liệu. Hãy chạy crop trước.")
            return
        stats = self._last_stats
        class_stats = stats.get("class_stats", {})

        win = Toplevel(self.root)
        win.title("Thống kê Crop")
        win.configure(bg=BG)
        win.resizable(True, True)
        win.geometry("560x440")

        Label(win, text="Thống kê kết quả Crop", bg=BG, fg=TEXT,
              font=F_BOLD).pack(pady=(14, 4))

        summary_f = Frame(win, bg=CARD, padx=14, pady=8)
        summary_f.pack(fill=X, padx=16, pady=(0, 8))
        rows = [
            ("Tổng ảnh đã xử lý", stats.get("total", 0)),
            ("Bỏ qua (đã có)", stats.get("skipped", 0)),
            ("Thiếu label", stats.get("no_label", 0)),
            ("Bỏ qua (nhỏ hơn min size)", stats.get("size_skipped", 0)),
            ("Tổng crops đã lưu", stats.get("saved", 0)),
        ]
        for label, val in rows:
            rf = Frame(summary_f, bg=CARD)
            rf.pack(fill=X, pady=1)
            Label(rf, text=label, bg=CARD, fg=DIM, font=F_MAIN, anchor=W,
                  width=30).pack(side=LEFT)
            Label(rf, text=str(val), bg=CARD, fg=TEXT, font=F_BOLD,
                  anchor=W).pack(side=LEFT)

        Label(win, text="Chi tiết theo nhãn:", bg=BG, fg=TEXT,
              font=F_BOLD).pack(anchor=W, padx=16, pady=(4, 2))

        tbl_f = Frame(win, bg=BG, padx=16)
        tbl_f.pack(fill=BOTH, expand=True)

        cols = ("Nhãn", "Số crops", "TB rộng (px)", "TB cao (px)")
        col_w = (160, 90, 110, 110)

        hdr = Frame(tbl_f, bg=ACCENT2)
        hdr.pack(fill=X)
        for c, w in zip(cols, col_w):
            Label(hdr, text=c, bg=ACCENT2, fg="white", font=F_BOLD,
                  width=w // 8, anchor=W, padx=6, pady=4).pack(side=LEFT)

        data_outer = Frame(tbl_f, bg=BG)
        data_outer.pack(fill=BOTH, expand=True)
        canvas = Canvas(data_outer, bg="#16162a", highlightthickness=0)
        vsb = Scrollbar(data_outer, orient=VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=RIGHT, fill=Y)
        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        inner = Frame(canvas, bg="#16162a")
        canvas_win = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(
            scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(
            canvas_win, width=e.width))

        table_data = []
        for cname, cs in sorted(class_stats.items()):
            cnt = cs["count"]
            avg_w = cs["total_w"] / cnt if cnt else 0
            avg_h = cs["total_h"] / cnt if cnt else 0
            table_data.append((cname, cnt, round(avg_w, 1), round(avg_h, 1)))

        for ridx, (cname, cnt, avg_w, avg_h) in enumerate(table_data):
            row_bg = "#16162a" if ridx % 2 == 0 else CARD
            rf = Frame(inner, bg=row_bg)
            rf.pack(fill=X)
            for val, w in zip((cname, cnt, avg_w, avg_h), col_w):
                Label(rf, text=str(val), bg=row_bg, fg=TEXT, font=F_MAIN,
                      width=w // 8, anchor=W, padx=6, pady=3).pack(side=LEFT)

        btn_f = Frame(win, bg=BG, pady=10)
        btn_f.pack(fill=X, padx=16)

        def _export_csv():
            path = filedialog.asksaveasfilename(
                parent=win,
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialfile="crop_stats.csv",
                title="Xuất thống kê CSV",
            )
            if not path:
                return
            try:
                with open(path, "w", newline="", encoding="utf-8-sig") as f:
                    w = csv.writer(f)
                    w.writerow(["Nhãn", "Số crops", "TB rộng (px)", "TB cao (px)"])
                    for row in table_data:
                        w.writerow(row)
                    w.writerow([])
                    w.writerow(["Tổng ảnh", stats.get("total", 0)])
                    w.writerow(["Bỏ qua (đã có)", stats.get("skipped", 0)])
                    w.writerow(["Thiếu label", stats.get("no_label", 0)])
                    w.writerow(["Bỏ qua (nhỏ)", stats.get("size_skipped", 0)])
                    w.writerow(["Tổng crops", stats.get("saved", 0)])
                messagebox.showinfo("Xuất CSV", f"Đã lưu:\n{path}", parent=win)
            except Exception as e:
                messagebox.showerror("Lỗi", str(e), parent=win)

        _action_btn(btn_f, "📥  Xuất CSV", _export_csv, ACCENT,
                    padx=16, pady=6).pack(side=LEFT)
        Button(btn_f, text="Đóng", command=win.destroy,
               bg=CARD, fg=DIM, font=F_MAIN, relief="flat",
               padx=14, pady=6, cursor="hand2").pack(side=RIGHT)
