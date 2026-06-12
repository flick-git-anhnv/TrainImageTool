import os
from pathlib import Path
from tkinter import *
from tkinter import messagebox, ttk

from .constants import BG, CARD, ACCENT, ACCENT2, TEXT, DIM, F_MAIN, F_BOLD, F_MONO, IMAGE_EXTENSIONS
from .settings import _bind_cfg
from .ui_helpers import _folder_row


class BBoxEditorTab(Frame):
    _PALETTE = [
        "#F05922", "#4caf50", "#2196f3", "#9c27b0", "#ff9800",
        "#00bcd4", "#e91e63", "#8bc34a", "#ff5722", "#607d8b",
        "#ffeb3b", "#3f51b5", "#009688", "#795548", "#f44336",
    ]

    def __init__(self, master, root):
        super().__init__(master, bg=BG)
        self.root = root

        self.img_dir_var  = StringVar()
        self.lbl_dir_var  = StringVar()
        self._labels_var  = StringVar(
            value="car,motorcycle,bus,truck,bicycle,license_plate")
        self.v_recursive  = BooleanVar(value=False)
        _bind_cfg("bbox.img",    self.img_dir_var)
        _bind_cfg("bbox.lbl",    self.lbl_dir_var)
        _bind_cfg("bbox.labels", self._labels_var)

        self.label_list  = []
        self.image_files = []
        self.current_idx = -1
        self._filtered_files  = []   # list of (real_idx, Path)
        self._filter_name_var  = StringVar()
        self._filter_label_var = StringVar(value="Tất cả")
        self._filter_after     = None

        self._pil_img  = None
        self._tk_img   = None
        self._scale    = 1.0
        self._off_x    = 0
        self._off_y    = 0

        self._bboxes        = []
        self._selected      = -1
        self._selected_set  = set()
        self._modified      = False

        self._mode        = StringVar(value="draw")
        self._drawing     = False
        self._draw_start  = (0, 0)
        self._draw_rect   = None
        self._resize_after = None

        self._drag_op        = None
        self._drag_prev      = (0, 0)
        self._drag_press_pos = (0, 0)
        self._drag_committed = True

        self._rubber_band  = False
        self._rubber_rect  = None
        self._rubber_start = (0, 0)

        # Grid panel (paginated)
        self._thumb_n_var   = IntVar(value=3)   # columns
        self._thumb_w       = 160
        self._thumb_h       = 100
        self._thumb_cache: dict = {}
        self._film_cells: list  = []
        self._film_render_idx   = 0
        self._film_ncols        = 3
        self._film_page         = 0

        self._build()

    def _build(self):
        from PIL import Image, ImageTk
        self._PIL_Image   = Image
        self._PIL_ImageTk = ImageTk

        top = Frame(self, bg=CARD, padx=12, pady=10)
        top.pack(fill=X)
        grid = Frame(top, bg=CARD)
        grid.pack(fill=X)

        _folder_row(grid, "Thư mục ảnh :",  self.img_dir_var, 0, bg=CARD)
        _folder_row(grid, "Thư mục label:", self.lbl_dir_var, 1, bg=CARD)

        Label(grid, text="Danh sách nhãn:", bg=CARD, fg=DIM,
              font=F_MAIN, width=26, anchor=W).grid(
                  row=2, column=0, sticky=W, pady=5)
        Entry(grid, textvariable=self._labels_var, bg=CARD, fg=TEXT,
              insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4).grid(
                  row=2, column=1, sticky=EW, padx=(8, 8))
        lbl_btn_row = Frame(grid, bg=CARD)
        lbl_btn_row.grid(row=2, column=2, sticky=W)
        Checkbutton(lbl_btn_row, text="Đệ quy subfolder",
                    variable=self.v_recursive,
                    bg=CARD, fg=TEXT, selectcolor="#16162a",
                    activebackground=CARD, font=F_MAIN).pack(side=LEFT, padx=(0, 8))
        Button(lbl_btn_row, text="  ▶  Tải ảnh",
               command=self._load_dataset,
               bg=ACCENT, fg="white", activebackground="#c04010",
               activeforeground="white", font=F_BOLD,
               relief="flat", padx=14, cursor="hand2").pack(side=LEFT)

        main = Frame(self, bg=BG)
        main.pack(fill=BOTH, expand=True, padx=8, pady=6)

        left = Frame(main, bg=CARD, width=200)
        left.pack(side=LEFT, fill=Y, padx=(0, 6))
        left.pack_propagate(False)

        Label(left, text="Danh sách ảnh", bg=CARD, fg=TEXT,
              font=F_BOLD).pack(pady=(8, 2), padx=8, anchor=W)
        self._lbl_imgcount = Label(left, text="—", bg=CARD, fg=DIM, font=F_MAIN)
        self._lbl_imgcount.pack(padx=8, anchor=W)

        flt_name = Frame(left, bg=CARD)
        flt_name.pack(fill=X, padx=6, pady=(4, 1))
        Label(flt_name, text="Tên:", bg=CARD, fg=DIM, font=F_MAIN, width=4,
              anchor=W).pack(side=LEFT)
        Entry(flt_name, textvariable=self._filter_name_var,
              bg="#16162a", fg=TEXT, insertbackground=TEXT,
              relief="flat", font=F_MONO, bd=2).pack(side=LEFT, fill=X, expand=True)
        self._filter_name_var.trace_add("write", lambda *_: self._schedule_filter())

        flt_lbl = Frame(left, bg=CARD)
        flt_lbl.pack(fill=X, padx=6, pady=(0, 2))
        Label(flt_lbl, text="Nhãn:", bg=CARD, fg=DIM, font=F_MAIN, width=4,
              anchor=W).pack(side=LEFT)
        self._filter_label_combo = ttk.Combobox(
            flt_lbl, textvariable=self._filter_label_var,
            state="readonly", font=F_MAIN, width=10)
        self._filter_label_combo["values"] = ["Tất cả"]
        self._filter_label_combo.pack(side=LEFT, fill=X, expand=True, padx=(0, 2))
        self._filter_label_combo.bind("<<ComboboxSelected>>",
                                      lambda _: self._apply_filters())
        Button(flt_lbl, text="✕", command=self._clear_filters,
               bg=CARD, fg=DIM, activebackground=CARD,
               font=F_MAIN, relief="flat", cursor="hand2", width=2).pack(side=LEFT)

        lf = Frame(left, bg=CARD)
        lf.pack(fill=BOTH, expand=True, padx=6, pady=(4, 0))
        self._img_lb = Listbox(lf, bg="#16162a", fg=TEXT,
                               selectbackground=ACCENT2, selectforeground="white",
                               font=F_MONO, relief="flat", bd=0, activestyle="none")
        sb_lb = Scrollbar(lf, command=self._img_lb.yview)
        self._img_lb.configure(yscrollcommand=sb_lb.set)
        sb_lb.pack(side=RIGHT, fill=Y)
        self._img_lb.pack(fill=BOTH, expand=True)
        self._img_lb.bind("<<ListboxSelect>>", self._on_list_select)

        nav = Frame(left, bg=CARD)
        nav.pack(fill=X, padx=6, pady=4)
        Button(nav, text="◀", command=self._prev_img,
               bg=ACCENT2, fg="white", font=F_BOLD,
               relief="flat", cursor="hand2", width=5).pack(side=LEFT)
        Button(nav, text="▶", command=self._next_img,
               bg=ACCENT2, fg="white", font=F_BOLD,
               relief="flat", cursor="hand2", width=5).pack(side=LEFT, padx=(4, 0))

        Label(left, text="Nhãn (class)", bg=CARD, fg=TEXT,
              font=F_BOLD).pack(pady=(8, 2), padx=8, anchor=W)
        self._cls_lb = Listbox(left, bg="#16162a", fg=TEXT,
                               selectbackground=ACCENT2, selectforeground="white",
                               font=F_MONO, relief="flat", bd=0,
                               activestyle="none", height=10, exportselection=False)
        self._cls_lb.pack(fill=X, padx=6, pady=(0, 6))
        self._cls_lb.bind("<<ListboxSelect>>", self._on_cls_select)

        center = Frame(main, bg=BG)
        center.pack(side=LEFT, fill=BOTH, expand=True)

        tb = Frame(center, bg=CARD, pady=5, padx=8)
        tb.pack(fill=X)

        Label(tb, text="Chế độ:", bg=CARD, fg=DIM, font=F_MAIN).pack(
            side=LEFT, padx=(0, 4))
        for txt, val in [("✏ Vẽ bbox", "draw"), ("🖱 Chọn / sửa", "select")]:
            Radiobutton(tb, text=txt, variable=self._mode, value=val,
                        bg=CARD, fg=TEXT, selectcolor=ACCENT2,
                        activebackground=CARD, font=F_MAIN).pack(side=LEFT, padx=4)

        Frame(tb, bg=DIM, width=1).pack(side=LEFT, fill=Y, padx=8)

        Label(tb, text="Nhãn:", bg=CARD, fg=DIM, font=F_MAIN).pack(side=LEFT)
        self._cls_combo = ttk.Combobox(tb, width=18, state="readonly", font=F_MAIN)
        self._cls_combo.pack(side=LEFT, padx=(4, 6))

        Button(tb, text="🏷 Đặt nhãn", command=self._relabel_selected,
               bg=ACCENT2, fg="white", activebackground=ACCENT,
               activeforeground="white", font=F_MAIN,
               relief="flat", padx=8, cursor="hand2").pack(side=LEFT, padx=2)
        Button(tb, text="🗑 Xóa bbox (Del)", command=self._delete_selected,
               bg="#c62828", fg="white", activebackground="#8b0000",
               activeforeground="white", font=F_MAIN,
               relief="flat", padx=8, cursor="hand2").pack(side=LEFT, padx=2)

        Frame(tb, bg=DIM, width=1).pack(side=LEFT, fill=Y, padx=8)

        Button(tb, text="💾 Lưu label (Ctrl+S)", command=self._save_labels,
               bg="#2e7d32", fg="white", activebackground="#1b5e20",
               activeforeground="white", font=F_BOLD,
               relief="flat", padx=10, cursor="hand2").pack(side=LEFT, padx=2)

        self._info_lbl = Label(tb, text="", bg=CARD, fg=DIM, font=F_MAIN)
        self._info_lbl.pack(side=RIGHT, padx=8)

        _spn = Spinbox(tb, from_=1, to=6, textvariable=self._thumb_n_var,
                       width=3, bg="#16162a", fg=TEXT, insertbackground=TEXT,
                       buttonbackground=ACCENT2, relief="flat", font=F_MAIN,
                       command=self._rebuild_filmstrip)
        _spn.bind("<Return>", lambda e: self._rebuild_filmstrip())
        _spn.bind("<FocusOut>", lambda e: self._rebuild_filmstrip())
        _spn.pack(side=RIGHT)
        Label(tb, text="Cột:", bg=CARD, fg=DIM, font=F_MAIN).pack(
            side=RIGHT, padx=(8, 2))

        # Horizontal split: canvas left | grid right
        from tkinter import PanedWindow as _PW
        paned = _PW(center, orient=HORIZONTAL, sashwidth=5,
                    bg="#0d0d1e", sashrelief=RAISED, bd=0)
        paned.pack(fill=BOTH, expand=True, pady=(6, 0))

        cf = Frame(paned, bg="#111122", relief=SUNKEN, bd=1)
        paned.add(cf, minsize=300, stretch="always")
        self._canvas = Canvas(cf, bg="#111122", cursor="crosshair",
                              highlightthickness=0)
        self._canvas.pack(fill=BOTH, expand=True)

        self._film_outer = Frame(paned, bg="#0d0d1e")
        paned.add(self._film_outer, minsize=200, stretch="always")

        # Page nav bar — packed first to reserve bottom space
        _nav = Frame(self._film_outer, bg=CARD, pady=5)
        _nav.pack(side=BOTTOM, fill=X)
        Button(_nav, text="◀  Trước", width=9,
               command=lambda: self._go_page(-1),
               bg=ACCENT2, fg="white", activebackground=ACCENT,
               activeforeground="white", relief=FLAT, font=F_MAIN
               ).pack(side=LEFT, padx=(6, 4))
        self._film_nav_lbl = Label(_nav, text="—", bg=CARD, fg=TEXT,
                                   font=F_BOLD)
        self._film_nav_lbl.pack(side=LEFT, padx=6, expand=True)
        Button(_nav, text="Sau  ▶", width=9,
               command=lambda: self._go_page(1),
               bg=ACCENT2, fg="white", activebackground=ACCENT,
               activeforeground="white", relief=FLAT, font=F_MAIN
               ).pack(side=RIGHT, padx=(4, 6))

        # Scrollable grid area
        _grid_area = Frame(self._film_outer, bg="#0d0d1e")
        _grid_area.pack(fill=BOTH, expand=True)

        self._film_canvas = Canvas(_grid_area, bg="#0d0d1e",
                                   highlightthickness=0)
        _film_vsb = Scrollbar(_grid_area, orient=VERTICAL,
                              command=self._film_canvas.yview)
        _film_vsb.pack(side=RIGHT, fill=Y)
        self._film_canvas.config(yscrollcommand=_film_vsb.set)
        self._film_canvas.pack(side=LEFT, fill=BOTH, expand=True)

        self._film_inner = Frame(self._film_canvas, bg="#0d0d1e")
        self._film_canvas_win = self._film_canvas.create_window(
            (0, 0), window=self._film_inner, anchor="nw")

        self._film_inner.bind("<Configure>", lambda e: (
            self._film_canvas.configure(
                scrollregion=self._film_canvas.bbox("all"))))
        self._film_canvas.bind("<Configure>", lambda e: (
            self._film_canvas.itemconfig(
                self._film_canvas_win, width=e.width)))

        def _film_scroll(e):
            self._film_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        self._film_canvas.bind("<MouseWheel>", _film_scroll)
        self._film_inner.bind("<MouseWheel>", _film_scroll)

        self._canvas.bind("<ButtonPress-1>",   self._on_press)
        self._canvas.bind("<B1-Motion>",       self._on_drag)
        self._canvas.bind("<ButtonRelease-1>", self._on_release)
        self._canvas.bind("<Motion>",          self._on_hover)
        self._canvas.bind("<Configure>",       self._on_canvas_cfg)
        self._canvas.bind("<Delete>",          lambda e: self._delete_selected())
        self._canvas.bind("<Control-s>",       lambda e: self._save_labels())
        self._canvas.bind("<Return>",          lambda e: self._save_labels())
        self._canvas.bind("<Control-a>",       lambda e: self._select_all())
        self._canvas.bind("<Escape>",          lambda e: self._deselect_all())
        self._canvas.bind("<Left>",  lambda e: self._prev_img())
        self._canvas.bind("<Right>", lambda e: self._next_img())
        self._img_lb.bind("<Left>",  lambda e: self._prev_img())
        self._img_lb.bind("<Right>", lambda e: self._next_img())
        self._img_lb.bind("<Return>", lambda e: self._save_labels())

        self._status = Label(center,
            text="Chọn thư mục ảnh và label, nhập danh sách nhãn rồi nhấn Tải ảnh",
            bg=BG, fg=DIM, font=F_MAIN, anchor=W)
        self._status.pack(fill=X, pady=(4, 0))

    def _parse_label_list(self):
        raw = self._labels_var.get().strip()
        return [s.strip() for s in raw.replace("\n", ",").split(",") if s.strip()]

    def _load_dataset(self):
        self.label_list = self._parse_label_list()
        if not self.label_list:
            messagebox.showerror("Lỗi",
                "Vui lòng nhập danh sách nhãn (cách nhau bởi dấu phẩy)."); return
        img_dir = self.img_dir_var.get().strip()
        if not img_dir or not os.path.isdir(img_dir):
            messagebox.showerror("Lỗi", "Vui lòng chọn thư mục ảnh hợp lệ."); return
        self._film_page = 0
        self._thumb_cache.clear()

        img_root = Path(img_dir)
        if self.v_recursive.get():
            self.image_files = sorted(
                p for p in img_root.rglob("*")
                if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS)
        else:
            self.image_files = sorted(
                p for p in img_root.iterdir()
                if p.suffix.lower() in IMAGE_EXTENSIONS)

        self._cls_lb.delete(0, END)
        combo_vals = []
        for i, name in enumerate(self.label_list):
            color = self._PALETTE[i % len(self._PALETTE)]
            self._cls_lb.insert(END, f"  [{i}]  {name}")
            self._cls_lb.itemconfig(END, fg=color)
            combo_vals.append(f"{i}: {name}")
        self._cls_combo["values"] = combo_vals
        if combo_vals:
            self._cls_combo.current(0)

        filter_opts = (["Tất cả", "Không có label"] +
                       [f"{i}: {n}" for i, n in enumerate(self.label_list)])
        self._filter_label_combo["values"] = filter_opts
        self._filter_label_var.set("Tất cả")
        self._filter_name_var.set("")

        self.current_idx = -1
        self._apply_filters()

        if self._filtered_files:
            real_idx = self._filtered_files[0][0]
            self._img_lb.selection_set(0)
            self._load_image(real_idx)

        self._status.config(
            text=f"Đã tải {len(self.image_files)} ảnh  |  {len(self.label_list)} nhãn")

    def _on_list_select(self, _event):
        sel = self._img_lb.curselection()
        if not sel: return
        fi = sel[0]
        if fi >= len(self._filtered_files): return
        real_idx = self._filtered_files[fi][0]
        if real_idx == self.current_idx: return
        self._autosave()
        self._load_image(real_idx)

    def _on_cls_select(self, _event):
        sel = self._cls_lb.curselection()
        if not sel: return
        idx = sel[0]
        if idx < len(self._cls_combo["values"]):
            self._cls_combo.current(idx)

    def _load_image(self, idx):
        self.current_idx = idx
        fp = self.image_files[idx]
        try:
            self._pil_img = self._PIL_Image.open(fp).convert("RGB")
        except Exception as e:
            self._status.config(text=f"Lỗi mở ảnh: {e}"); return

        self._bboxes       = []
        self._selected     = -1
        self._selected_set = set()
        self._modified     = False

        lbl_dir  = self.lbl_dir_var.get().strip()
        lbl_path = (Path(lbl_dir) / (fp.stem + ".txt")
                    if lbl_dir else fp.parent / (fp.stem + ".txt"))
        if lbl_path.exists():
            self._bboxes = self._read_yolo(lbl_path)

        self._render()
        iw, ih = self._pil_img.size
        self._status.config(text=f"{fp.name}   {iw}×{ih}   |   {len(self._bboxes)} bbox")
        self._update_filmstrip()

    def _read_yolo(self, path):
        iw, ih = self._pil_img.size
        bboxes = []
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    p = line.strip().split()
                    if len(p) < 5: continue
                    cid = int(p[0])
                    xc, yc, w, h = map(float, p[1:5])
                    bboxes.append([cid,
                                   (xc - w / 2) * iw, (yc - h / 2) * ih,
                                   (xc + w / 2) * iw, (yc + h / 2) * ih])
        except Exception:
            pass
        return bboxes

    def _write_yolo(self, path):
        iw, ih = self._pil_img.size
        lines  = []
        for cid, x1, y1, x2, y2 in self._bboxes:
            xc  = max(0.0, min(1.0, ((x1 + x2) / 2) / iw))
            yc  = max(0.0, min(1.0, ((y1 + y2) / 2) / ih))
            bw  = max(1e-4, min(1.0, (x2 - x1) / iw))
            bh  = max(1e-4, min(1.0, (y2 - y1) / ih))
            lines.append(f"{int(cid)} {xc:.6f} {yc:.6f} {bw:.6f} {bh:.6f}")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def _render(self):
        if self._pil_img is None: return
        self._canvas.update_idletasks()
        cw = self._canvas.winfo_width()
        ch = self._canvas.winfo_height()
        if cw < 10 or ch < 10:
            self._canvas.after(80, self._render); return

        iw, ih = self._pil_img.size
        scale   = min(cw / iw, ch / ih, 1.0)
        nw, nh  = max(1, int(iw * scale)), max(1, int(ih * scale))
        self._scale = scale
        self._off_x = (cw - nw) // 2
        self._off_y = (ch - nh) // 2

        resized      = self._pil_img.resize((nw, nh), self._PIL_Image.LANCZOS)
        self._tk_img = self._PIL_ImageTk.PhotoImage(resized)

        self._canvas.delete("all")
        self._canvas.create_image(self._off_x, self._off_y,
                                  anchor=NW, image=self._tk_img)
        self._draw_all_bboxes()

    def _active_label_filter_id(self):
        val = self._filter_label_var.get()
        if not val or val in ("Tất cả", "Không có label"):
            return None
        try:
            return int(val.split(":")[0])
        except (ValueError, IndexError):
            return None

    def _draw_all_bboxes(self):
        only_cid = self._active_label_filter_id()
        for i, (cid, x1, y1, x2, y2) in enumerate(self._bboxes):
            if only_cid is not None and cid != only_cid:
                continue
            cx1 = int(x1 * self._scale) + self._off_x
            cy1 = int(y1 * self._scale) + self._off_y
            cx2 = int(x2 * self._scale) + self._off_x
            cy2 = int(y2 * self._scale) + self._off_y
            color      = self._PALETTE[cid % len(self._PALETTE)]
            is_primary = (i == self._selected)
            in_set     = (i in self._selected_set)
            self._canvas.create_rectangle(cx1, cy1, cx2, cy2,
                                          outline=color,
                                          width=5 if is_primary else (3 if in_set else 2),
                                          dash=() if (is_primary or in_set) else (5, 3),
                                          tags=f"bb{i}")
            cls_name = (self.label_list[cid]
                        if cid < len(self.label_list) else str(cid))
            txt   = f" {cid}:{cls_name} "
            txt_w = max(len(txt) * 7, 30)
            self._canvas.create_rectangle(cx1, cy1 - 17, cx1 + txt_w, cy1,
                                          fill=color, outline="", tags=f"bb{i}")
            self._canvas.create_text(cx1 + 3, cy1 - 8, text=txt, fill="white",
                                     font=("Segoe UI", 8, "bold"),
                                     anchor=W, tags=f"bb{i}")
            if is_primary:
                hw = 7
                mx, my = (cx1 + cx2) // 2, (cy1 + cy2) // 2
                for hx, hy in [(cx1, cy1), (cx2, cy1), (cx1, cy2), (cx2, cy2)]:
                    self._canvas.create_rectangle(
                        hx - hw, hy - hw, hx + hw, hy + hw,
                        fill=color, outline="white", width=1, tags=f"bb{i}")
                for hx, hy, fw, fh in [(mx, cy1, hw+3, hw-3), (mx, cy2, hw+3, hw-3),
                                        (cx1, my, hw-3, hw+3), (cx2, my, hw-3, hw+3)]:
                    self._canvas.create_rectangle(
                        hx - fw, hy - fh, hx + fw, hy + fh,
                        fill=color, outline="white", width=1, tags=f"bb{i}")

    def _on_canvas_cfg(self, _event):
        if self._resize_after:
            self._canvas.after_cancel(self._resize_after)
        self._resize_after = self._canvas.after(120, self._render)

    def _img_coords(self, cx, cy):
        return ((cx - self._off_x) / self._scale,
                (cy - self._off_y) / self._scale)

    def _hit_test_all(self, cx, cy):
        hits = []
        for i, (_, x1, y1, x2, y2) in enumerate(self._bboxes):
            bx1 = int(x1 * self._scale) + self._off_x
            by1 = int(y1 * self._scale) + self._off_y
            bx2 = int(x2 * self._scale) + self._off_x
            by2 = int(y2 * self._scale) + self._off_y
            if bx1 <= cx <= bx2 and by1 <= cy <= by2:
                hits.append(i)
        return hits

    def _cycle_at(self, cx, cy):
        hits = self._hit_test_all(cx, cy)
        if not hits:
            self._selected = -1
        elif self._selected in hits:
            self._selected = hits[(hits.index(self._selected) - 1) % len(hits)]
        else:
            self._selected = hits[-1]
        self._selected_set = {self._selected} if self._selected >= 0 else set()
        self._render()
        self._update_info_lbl()

    _HIT_R = 9

    def _handle_hit(self, cx, cy, idx):
        _, x1, y1, x2, y2 = self._bboxes[idx]
        bx1 = int(x1 * self._scale) + self._off_x
        by1 = int(y1 * self._scale) + self._off_y
        bx2 = int(x2 * self._scale) + self._off_x
        by2 = int(y2 * self._scale) + self._off_y
        mx, my = (bx1 + bx2) // 2, (by1 + by2) // 2
        r = self._HIT_R
        for op, (hx, hy) in [("resize_NW", (bx1, by1)), ("resize_NE", (bx2, by1)),
                               ("resize_SW", (bx1, by2)), ("resize_SE", (bx2, by2))]:
            if abs(cx - hx) <= r and abs(cy - hy) <= r: return op
        for op, (hx, hy) in [("resize_N", (mx, by1)), ("resize_S", (mx, by2)),
                               ("resize_W", (bx1, my)), ("resize_E", (bx2, my))]:
            if abs(cx - hx) <= r and abs(cy - hy) <= r: return op
        return None

    def _on_hover(self, event):
        if self._mode.get() != "select" or self._selected < 0:
            self._canvas.config(cursor="crosshair"); return
        op = self._handle_hit(event.x, event.y, self._selected)
        cursor = ("size_nw_se"        if op in ("resize_NW", "resize_SE") else
                  "size_ne_sw"        if op in ("resize_NE", "resize_SW") else
                  "sb_v_double_arrow" if op in ("resize_N",  "resize_S")  else
                  "sb_h_double_arrow" if op in ("resize_W",  "resize_E")  else None)
        if cursor:
            self._canvas.config(cursor=cursor)
        else:
            _, x1, y1, x2, y2 = self._bboxes[self._selected]
            bx1 = int(x1 * self._scale) + self._off_x
            by1 = int(y1 * self._scale) + self._off_y
            bx2 = int(x2 * self._scale) + self._off_x
            by2 = int(y2 * self._scale) + self._off_y
            self._canvas.config(
                cursor="fleur" if bx1 <= event.x <= bx2 and by1 <= event.y <= by2
                else "crosshair")

    def _on_press(self, event):
        if self._pil_img is None: return
        self._canvas.focus_set()
        cx, cy = event.x, event.y
        ctrl = bool(event.state & 0x4)

        if self._mode.get() == "select":
            # Handle hit on primary (resize) — only without Ctrl
            if self._selected >= 0 and not ctrl:
                op = self._handle_hit(cx, cy, self._selected)
                if op:
                    self._drag_op = op
                    self._drag_prev = (cx, cy)
                    self._drag_committed = True
                    return

            hits = self._hit_test_all(cx, cy)

            if hits:
                top = hits[-1]
                if ctrl:
                    # Ctrl+Click: toggle in selection set
                    if top in self._selected_set:
                        self._selected_set.discard(top)
                        self._selected = (max(self._selected_set)
                                          if self._selected_set else -1)
                    else:
                        self._selected_set.add(top)
                        self._selected = top
                    self._render()
                    self._update_info_lbl()
                else:
                    if top not in self._selected_set:
                        self._selected = top
                        self._selected_set = {top}
                        self._render()
                        self._update_info_lbl()
                    else:
                        self._selected = top
                    self._drag_op        = "move"
                    self._drag_press_pos = (cx, cy)
                    self._drag_prev      = (cx, cy)
                    self._drag_committed = (len(self._selected_set) > 1)
            else:
                if not ctrl:
                    self._selected = -1
                    self._selected_set = set()
                    self._render()
                    self._update_info_lbl()
                # Start rubber-band selection
                self._rubber_band  = True
                self._rubber_start = (cx, cy)
                self._rubber_rect  = self._canvas.create_rectangle(
                    cx, cy, cx, cy, outline="#aaaaff", width=1, dash=(3, 3))
        else:
            self._drawing    = True
            self._draw_start = (cx, cy)
            self._draw_rect  = self._canvas.create_rectangle(
                cx, cy, cx, cy, outline=ACCENT, width=2, dash=(4, 2))

    _DRAG_THRESHOLD = 5

    def _on_drag(self, event):
        if self._drag_op and self._selected >= 0:
            cx, cy = event.x, event.y
            if not self._drag_committed:
                px0, py0 = self._drag_press_pos
                if ((cx - px0) ** 2 + (cy - py0) ** 2) ** 0.5 < self._DRAG_THRESHOLD:
                    return
                self._drag_committed = True
                self._drag_prev = (cx, cy)
                return
            px, py = self._drag_prev
            self._drag_prev = (cx, cy)
            self._apply_drag((cx - px) / self._scale,
                             (cy - py) / self._scale)
        elif self._rubber_band and self._rubber_rect:
            x0, y0 = self._rubber_start
            self._canvas.coords(self._rubber_rect, x0, y0, event.x, event.y)
        elif self._drawing and self._draw_rect:
            x0, y0 = self._draw_start
            self._canvas.coords(self._draw_rect, x0, y0, event.x, event.y)

    def _apply_drag(self, dx, dy):
        bb = self._bboxes[self._selected]
        iw, ih = self._pil_img.size
        op = self._drag_op
        if op == "move" and len(self._selected_set) > 1:
            for i in self._selected_set:
                b = self._bboxes[i]
                w = b[3] - b[1]; h = b[4] - b[2]
                nx1 = max(0.0, min(float(iw) - w, b[1] + dx))
                ny1 = max(0.0, min(float(ih) - h, b[2] + dy))
                b[1] = nx1; b[2] = ny1; b[3] = nx1 + w; b[4] = ny1 + h
        elif op == "move":
            w = bb[3] - bb[1]; h = bb[4] - bb[2]
            nx1 = max(0.0, min(float(iw) - w, bb[1] + dx))
            ny1 = max(0.0, min(float(ih) - h, bb[2] + dy))
            bb[1] = nx1; bb[2] = ny1; bb[3] = nx1 + w; bb[4] = ny1 + h
        elif op == "resize_NW":
            bb[1] = max(0.0, min(bb[3]-1.0, bb[1]+dx))
            bb[2] = max(0.0, min(bb[4]-1.0, bb[2]+dy))
        elif op == "resize_NE":
            bb[3] = min(float(iw), max(bb[1]+1.0, bb[3]+dx))
            bb[2] = max(0.0, min(bb[4]-1.0, bb[2]+dy))
        elif op == "resize_SW":
            bb[1] = max(0.0, min(bb[3]-1.0, bb[1]+dx))
            bb[4] = min(float(ih), max(bb[2]+1.0, bb[4]+dy))
        elif op == "resize_SE":
            bb[3] = min(float(iw), max(bb[1]+1.0, bb[3]+dx))
            bb[4] = min(float(ih), max(bb[2]+1.0, bb[4]+dy))
        elif op == "resize_N":
            bb[2] = max(0.0, min(bb[4]-1.0, bb[2]+dy))
        elif op == "resize_S":
            bb[4] = min(float(ih), max(bb[2]+1.0, bb[4]+dy))
        elif op == "resize_W":
            bb[1] = max(0.0, min(bb[3]-1.0, bb[1]+dx))
        elif op == "resize_E":
            bb[3] = min(float(iw), max(bb[1]+1.0, bb[3]+dx))
        self._modified = True
        self._render()

    def _on_release(self, event):
        if self._rubber_band:
            self._rubber_band = False
            if self._rubber_rect:
                self._canvas.delete(self._rubber_rect)
                self._rubber_rect = None
            x0, y0 = self._rubber_start
            rx1, ry1 = min(x0, event.x), min(y0, event.y)
            rx2, ry2 = max(x0, event.x), max(y0, event.y)
            ctrl = bool(event.state & 0x4)
            if not ctrl:
                self._selected_set = set()
            if (rx2 - rx1) >= 4 and (ry2 - ry1) >= 4:
                for i, (_, x1, y1, x2, y2) in enumerate(self._bboxes):
                    bx1 = int(x1 * self._scale) + self._off_x
                    by1 = int(y1 * self._scale) + self._off_y
                    bx2 = int(x2 * self._scale) + self._off_x
                    by2 = int(y2 * self._scale) + self._off_y
                    cx_bb = (bx1 + bx2) / 2
                    cy_bb = (by1 + by2) / 2
                    if rx1 <= cx_bb <= rx2 and ry1 <= cy_bb <= ry2:
                        self._selected_set.add(i)
            self._selected = (max(self._selected_set)
                              if self._selected_set else -1)
            self._render()
            self._update_info_lbl()
            return
        if self._drag_op is not None:
            was_committed = self._drag_committed
            self._drag_op        = None
            self._drag_committed = True
            if not was_committed:
                self._cycle_at(event.x, event.y)
            return
        if not self._drawing: return
        self._drawing = False
        if self._draw_rect:
            self._canvas.delete(self._draw_rect)
            self._draw_rect = None
        x0, y0 = self._draw_start
        x1c = min(x0, event.x); y1c = min(y0, event.y)
        x2c = max(x0, event.x); y2c = max(y0, event.y)
        if (x2c - x1c) < 5 or (y2c - y1c) < 5: return
        iw, ih = self._pil_img.size
        ix1, iy1 = self._img_coords(x1c, y1c)
        ix2, iy2 = self._img_coords(x2c, y2c)
        ix1 = max(0.0, min(float(iw), ix1)); iy1 = max(0.0, min(float(ih), iy1))
        ix2 = max(0.0, min(float(iw), ix2)); iy2 = max(0.0, min(float(ih), iy2))
        if ix2 <= ix1 or iy2 <= iy1: return
        cid = self._current_class_id()
        self._bboxes.append([cid, ix1, iy1, ix2, iy2])
        self._selected = len(self._bboxes) - 1
        self._modified = True
        self._render()
        name = (self.label_list[cid] if cid < len(self.label_list) else str(cid))
        self._status.config(
            text=f"Đã vẽ bbox  [{cid}:{name}]  |  {len(self._bboxes)} bbox tổng")

    def _current_class_id(self):
        val = self._cls_combo.get()
        if val and ":" in val:
            try: return int(val.split(":")[0])
            except ValueError: pass
        return 0

    def _relabel_selected(self):
        if not self._selected_set:
            self._status.config(
                text="⚠  Chưa chọn bbox — dùng chế độ 'Chọn / sửa' rồi click vào bbox")
            return
        cid = self._current_class_id()
        for i in self._selected_set:
            self._bboxes[i][0] = cid
        self._modified = True
        self._render()
        name = (self.label_list[cid] if cid < len(self.label_list) else str(cid))
        n = len(self._selected_set)
        self._status.config(
            text=f"Đã đặt nhãn  [{cid}:{name}]  cho {n} bbox")

    def _delete_selected(self):
        if not self._selected_set: return
        for i in sorted(self._selected_set, reverse=True):
            self._bboxes.pop(i)
        n = len(self._selected_set)
        self._selected     = -1
        self._selected_set = set()
        self._modified     = True
        self._render()
        self._status.config(
            text=f"Đã xóa {n} bbox  |  {len(self._bboxes)} bbox còn lại")

    def _save_labels(self):
        if not self.image_files or self.current_idx < 0 or self._pil_img is None: return
        fp       = self.image_files[self.current_idx]
        lbl_dir  = self.lbl_dir_var.get().strip()
        lbl_path = (Path(lbl_dir) / (fp.stem + ".txt")
                    if lbl_dir else fp.parent / (fp.stem + ".txt"))
        try:
            self._write_yolo(lbl_path)
            self._modified = False
            self._status.config(
                text=f"✔  Đã lưu: {lbl_path}  |  {len(self._bboxes)} bbox")
            self._update_filmstrip()
        except Exception as e:
            messagebox.showerror("Lỗi lưu file", str(e))

    def _autosave(self):
        if self._modified:
            self._save_labels()

    def _update_info_lbl(self):
        n = len(self._selected_set)
        if n == 0:
            self._info_lbl.config(text="")
        elif n == 1 and self._selected >= 0 and self._selected < len(self._bboxes):
            cid  = self._bboxes[self._selected][0]
            name = self.label_list[cid] if cid < len(self.label_list) else str(cid)
            self._info_lbl.config(text=f"Đã chọn  [{cid}:{name}]")
            for k, v in enumerate(list(self._cls_combo["values"])):
                if v.startswith(f"{cid}:"):
                    self._cls_combo.current(k); break
        else:
            self._info_lbl.config(text=f"Đã chọn  {n} bbox")

    def _select_all(self):
        self._selected_set = set(range(len(self._bboxes)))
        self._selected = len(self._bboxes) - 1 if self._bboxes else -1
        self._render()
        self._update_info_lbl()

    def _deselect_all(self):
        self._selected     = -1
        self._selected_set = set()
        self._render()
        self._update_info_lbl()

    def _schedule_filter(self):
        if self._filter_after:
            self.after_cancel(self._filter_after)
        self._filter_after = self.after(300, self._apply_filters)

    def _clear_filters(self):
        self._filter_name_var.set("")
        self._filter_label_var.set("Tất cả")
        self._apply_filters()

    def _apply_filters(self):
        if not self.image_files:
            self._filtered_files = []
            self._lbl_imgcount.config(text="—")
            return

        name_q   = self._filter_name_var.get().strip().lower()
        label_q  = self._filter_label_var.get()
        lbl_dir  = self.lbl_dir_var.get().strip()
        img_root = Path(self.img_dir_var.get().strip())

        # Decode label filter
        label_id = None   # None = no filter
        if label_q and label_q != "Tất cả":
            if label_q == "Không có label":
                label_id = -2
            else:
                try:
                    label_id = int(label_q.split(":")[0])
                except (ValueError, IndexError):
                    label_id = None

        result = []
        for real_idx, fp in enumerate(self.image_files):
            if name_q and name_q not in fp.name.lower():
                continue
            if label_id is not None:
                lbl_path = (Path(lbl_dir) / (fp.stem + ".txt")
                            if lbl_dir else fp.parent / (fp.stem + ".txt"))
                if label_id == -2:
                    if lbl_path.exists() and lbl_path.stat().st_size > 0:
                        continue
                else:
                    if not lbl_path.exists():
                        continue
                    found = False
                    try:
                        with open(lbl_path, encoding="utf-8") as f:
                            for line in f:
                                parts = line.strip().split()
                                if parts and int(parts[0]) == label_id:
                                    found = True
                                    break
                    except Exception:
                        pass
                    if not found:
                        continue
            result.append((real_idx, fp))

        self._filtered_files = result

        self._img_lb.delete(0, END)
        for _, fp in self._filtered_files:
            display = (str(fp.relative_to(img_root))
                       if self.v_recursive.get() else fp.name)
            self._img_lb.insert(END, display)

        total = len(self.image_files)
        shown = len(self._filtered_files)
        self._lbl_imgcount.config(
            text=f"{shown}/{total} ảnh" if shown != total else f"{total} ảnh")

        # Restore selection if current image still in filtered list
        if self.current_idx >= 0:
            for fi, (ri, _) in enumerate(self._filtered_files):
                if ri == self.current_idx:
                    self._img_lb.selection_set(fi)
                    self._img_lb.see(fi)
                    break

        self.after(50, self._rebuild_filmstrip)

    def _prev_img(self):
        if not self._filtered_files: return
        cur_fi = next((i for i, (ri, _) in enumerate(self._filtered_files)
                       if ri == self.current_idx), -1)
        if cur_fi <= 0: return
        self._autosave()
        new_fi = cur_fi - 1
        real_idx = self._filtered_files[new_fi][0]
        self._img_lb.selection_clear(0, END)
        self._img_lb.selection_set(new_fi)
        self._img_lb.see(new_fi)
        self._load_image(real_idx)

    def _next_img(self):
        if not self._filtered_files: return
        cur_fi = next((i for i, (ri, _) in enumerate(self._filtered_files)
                       if ri == self.current_idx), -1)
        if cur_fi < 0 or cur_fi >= len(self._filtered_files) - 1: return
        self._autosave()
        new_fi = cur_fi + 1
        real_idx = self._filtered_files[new_fi][0]
        self._img_lb.selection_clear(0, END)
        self._img_lb.selection_set(new_fi)
        self._img_lb.see(new_fi)
        self._load_image(real_idx)

    # ── Grid filmstrip ─────────────────────────────────────────────────────

    def _label_path_for(self, img_path: Path) -> Path:
        lbl_dir = self.lbl_dir_var.get().strip()
        if lbl_dir:
            return Path(lbl_dir) / (img_path.stem + ".txt")
        return img_path.parent / (img_path.stem + ".txt")

    def _grid_filter_id(self):
        """Return label_id to show in grid: None=all, -2=none (unlabeled filter), int=class id."""
        label_q = self._filter_label_var.get()
        if not label_q or label_q == "Tất cả":
            return None
        if label_q == "Không có label":
            return -2
        try:
            return int(label_q.split(":")[0])
        except (ValueError, IndexError):
            return None

    def _render_thumb(self, img_path: Path, tw: int, th: int, filter_id=None):
        from PIL import Image as _Img, ImageTk as _ITk, ImageDraw as _IDraw
        cache_key = (str(img_path), tw, th, filter_id)
        if cache_key in self._thumb_cache:
            return self._thumb_cache[cache_key]
        try:
            img = _Img.open(img_path).convert("RGB")
            iw, ih = img.size
            img.thumbnail((tw, th), _Img.LANCZOS)
            tw2, th2 = img.size

            lbl = self._label_path_for(img_path)
            if lbl.exists() and filter_id != -2:
                draw = _IDraw.Draw(img)
                sx, sy = tw2 / iw, th2 / ih
                with open(lbl, encoding="utf-8") as f:
                    for line in f:
                        p = line.strip().split()
                        if len(p) < 5: continue
                        cid = int(p[0])
                        if filter_id is not None and cid != filter_id:
                            continue
                        xc, yc, bw, bh = map(float, p[1:5])
                        x1 = int((xc - bw / 2) * iw * sx)
                        y1 = int((yc - bh / 2) * ih * sy)
                        x2 = int((xc + bw / 2) * iw * sx)
                        y2 = int((yc + bh / 2) * ih * sy)
                        color = self._PALETTE[cid % len(self._PALETTE)]
                        draw.rectangle([x1, y1, x2, y2], outline=color, width=2)

            tk_img = _ITk.PhotoImage(img)
            self._thumb_cache[cache_key] = tk_img
            return tk_img
        except Exception:
            return None

    def _make_blank_thumb(self, tw: int, th: int):
        from PIL import Image as _Img, ImageTk as _ITk
        img = _Img.new("RGB", (tw, th), "#1a1a2e")
        return _ITk.PhotoImage(img)

    def _current_fi(self) -> int:
        return next((i for i, (ri, _) in enumerate(self._filtered_files)
                     if ri == self.current_idx), -1)

    def _go_page(self, delta: int):
        if not self._filtered_files: return
        n_cols = max(1, min(6, self._thumb_n_var.get()))
        per_page = n_cols * 4
        total    = len(self._filtered_files)
        max_page = max(0, (total - 1) // per_page)
        self._film_page = max(0, min(max_page, self._film_page + delta))
        self._rebuild_filmstrip()

    def _rebuild_filmstrip(self):
        for w in self._film_inner.winfo_children():
            w.destroy()
        self._film_cells.clear()

        if not self._filtered_files:
            self._film_nav_lbl.config(text="—")
            return

        n_cols = max(1, min(6, self._thumb_n_var.get()))
        self._thumb_n_var.set(n_cols)
        self._film_ncols = n_cols
        per_page = n_cols * 4

        total    = len(self._filtered_files)
        max_page = max(0, (total - 1) // per_page)
        self._film_page = max(0, min(max_page, self._film_page))

        start      = self._film_page * per_page
        end        = min(start + per_page, total)
        page_files = self._filtered_files[start:end]

        self._film_nav_lbl.config(
            text=f"Trang {self._film_page + 1} / {max_page + 1}   ({total} ảnh)")

        canvas_w = self._film_canvas.winfo_width() or 500
        pad = 4
        tw = max(120, (canvas_w - pad * (n_cols + 1) - 14) // n_cols)
        th = max(80,  int(tw * 0.625))

        # Invalidate cache only if size changed
        if self._thumb_w != tw or self._thumb_h != th:
            self._thumb_cache.clear()
        self._thumb_w, self._thumb_h = tw, th

        blank = self._make_blank_thumb(tw, th)

        for fi_off, (real_idx, fp) in enumerate(page_files):
            row, col = divmod(fi_off, n_cols)
            is_cur   = (real_idx == self.current_idx)
            border   = "#F05922" if is_cur else "#2a2a3e"

            cell = Frame(self._film_inner, bg=border, padx=2, pady=2,
                         cursor="hand2")
            cell.grid(row=row, column=col, padx=3, pady=3, sticky="nw")

            img_lbl = Label(cell, image=blank, bg="#1a1a2e", bd=0)
            img_lbl.pack()

            fn_text = fp.name if len(fp.name) <= 24 else fp.name[:21] + "..."
            fn_lbl = Label(cell, text=fn_text, bg="#111130",
                           fg="#9090bb", font=("Consolas", 7), anchor=W, padx=2)
            fn_lbl.pack(fill=X)

            for widget in (cell, img_lbl, fn_lbl):
                widget.bind("<Button-1>",
                            lambda e, ri=real_idx: self._film_click_real(ri))
                widget.bind("<MouseWheel>", lambda e: (
                    self._film_canvas.yview_scroll(
                        int(-1 * (e.delta / 120)), "units")))

            self._film_cells.append({
                "frame": cell, "img_lbl": img_lbl, "fn_lbl": fn_lbl,
                "tk_img": blank, "real_idx": real_idx, "rendered": False
            })

        self._film_canvas.update_idletasks()
        self._film_canvas.configure(scrollregion=self._film_canvas.bbox("all"))
        self._film_canvas.yview_moveto(0)

        self._film_render_idx = 0
        self._schedule_film_render()

    def _schedule_film_render(self):
        BATCH = 10
        fid = self._grid_filter_id()
        end = min(self._film_render_idx + BATCH, len(self._film_cells))
        for cell in self._film_cells[self._film_render_idx:end]:
            if not cell["rendered"]:
                fp = self.image_files[cell["real_idx"]]
                tk_img = self._render_thumb(fp, self._thumb_w, self._thumb_h, fid)
                if tk_img is None:
                    tk_img = self._make_blank_thumb(self._thumb_w, self._thumb_h)
                cell["tk_img"] = tk_img
                cell["img_lbl"].config(image=tk_img)
                cell["rendered"] = True
        self._film_render_idx = end
        if end < len(self._film_cells):
            self.after(40, self._schedule_film_render)

    def _film_click_real(self, real_idx: int):
        if real_idx == self.current_idx: return
        fi = next((i for i, (ri, _) in enumerate(self._filtered_files)
                   if ri == real_idx), -1)
        if fi < 0: return
        self._autosave()
        self._img_lb.selection_clear(0, END)
        self._img_lb.selection_set(fi)
        self._img_lb.see(fi)
        self._load_image(real_idx)

    def _update_filmstrip(self):
        if not self._filtered_files:
            return
        if not self._film_cells:
            self._rebuild_filmstrip()
            return

        # Auto-jump to the page containing current image
        n_cols   = max(1, min(6, self._thumb_n_var.get()))
        per_page = n_cols * 4
        fi       = self._current_fi()
        if fi >= 0:
            target_page = fi // per_page
            if target_page != self._film_page:
                self._film_page = target_page
                self._rebuild_filmstrip()
                return

        # Update border highlights on current page
        for cell in self._film_cells:
            is_cur = (cell["real_idx"] == self.current_idx)
            cell["frame"].config(bg="#F05922" if is_cur else "#2a2a3e")

        # Re-render current image thumb (bbox may have changed after save)
        fid = self._grid_filter_id()
        for cell in self._film_cells:
            if cell["real_idx"] == self.current_idx:
                fp  = self.image_files[self.current_idx]
                key = (str(fp), self._thumb_w, self._thumb_h, fid)
                self._thumb_cache.pop(key, None)
                tk_img = self._render_thumb(fp, self._thumb_w, self._thumb_h, fid)
                if tk_img is None:
                    tk_img = self._make_blank_thumb(self._thumb_w, self._thumb_h)
                cell["tk_img"] = tk_img
                cell["img_lbl"].config(image=tk_img)
                break
