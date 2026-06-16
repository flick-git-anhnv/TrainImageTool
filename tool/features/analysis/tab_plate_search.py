# tab_plate_search.py — Ground Truth Plate Search tab
import csv
import difflib
import fnmatch
import os
import re
import shutil
from tkinter import *
from tkinter import ttk, filedialog, messagebox

from ...core.constants import BG, CARD, ACCENT, ACCENT2, TEXT, DIM, F_MAIN, F_BOLD, F_MONO
from ...core.settings import _bind_cfg, _CFG, _cfg_save, _push_history

try:
    from PIL import Image, ImageTk
    _PIL_OK = True
except ImportError:
    _PIL_OK = False

_CANVAS_BG  = "#0d0d1a"
_HIT_FG     = ACCENT
_ODD_BG     = "#232336"
_MATCH_FG   = "#FFD700"   # gold for matched chars
_FUZZY_FG   = "#4ddb6e"   # green tint for fuzzy similarity score


class PlateSearchTab(Frame):
    def __init__(self, master, root):
        super().__init__(master, bg=BG)
        self.root = root

        # (filename, plate) — base dataset
        self.all_rows: list = []
        # filtered rows: (filename, plate) or (filename, plate, similarity_pct, query_for_row)
        self.filtered:  list = []
        self.img_dir:   str  = ""
        self._photo_ref      = None
        self._current_img_path: str = ""

        # fuzzy state
        self.v_fuzzy      = BooleanVar(value=False)
        self.v_threshold  = StringVar(value="80")

        # batch-search state: list of query strings from file (empty = not in batch mode)
        self._batch_queries: list = []

        self.v_gt     = StringVar()
        self.v_imgdir = StringVar()
        _bind_cfg("plate_search.gt_path",  self.v_gt)
        _bind_cfg("plate_search.img_dir",  self.v_imgdir)

        self._build()
        self.after(120, self._auto_load)

    # ================================================================ BUILD ==
    def _build(self):
        self._build_toolbar()
        self._build_main()

    # ---- toolbar ----
    def _build_toolbar(self):
        bar = Frame(self, bg=CARD, pady=8)
        bar.pack(fill=X, padx=0, pady=(0, 2))

        # --- row 0: file paths ---
        r0 = Frame(bar, bg=CARD)
        r0.pack(fill=X, padx=10, pady=(0, 4))

        Label(r0, text="File GT:", font=F_BOLD, bg=CARD, fg=TEXT).pack(side=LEFT)
        Label(r0, textvariable=self.v_gt, font=F_MONO, bg=CARD, fg=DIM,
              width=52, anchor="w").pack(side=LEFT, padx=(6, 0))
        Button(r0, text="Mở GT...", command=self._load_file,
               bg=ACCENT, fg="white", font=F_MAIN, relief="flat",
               padx=8, cursor="hand2",
               activebackground="#c0411a", activeforeground="white",
               ).pack(side=LEFT, padx=(8, 0))

        Label(r0, text="  Ảnh:", font=F_BOLD, bg=CARD, fg=TEXT).pack(side=LEFT, padx=(16, 0))
        Label(r0, textvariable=self.v_imgdir, font=F_MONO, bg=CARD, fg=DIM,
              width=36, anchor="w").pack(side=LEFT, padx=(6, 0))
        Button(r0, text="Chọn...", command=self._pick_img_dir,
               bg=ACCENT2, fg="white", font=F_MAIN, relief="flat",
               padx=8, cursor="hand2",
               activebackground="#2e2560", activeforeground="white",
               ).pack(side=LEFT, padx=(6, 4))
        Button(r0, text="📂", command=self._open_img_dir,
               bg=CARD, fg=TEXT, font=F_MAIN, relief="flat",
               padx=6, cursor="hand2",
               activebackground=ACCENT2, activeforeground="white",
               ).pack(side=LEFT)

        # --- row 1: search + fuzzy ---
        r1 = Frame(bar, bg=CARD)
        r1.pack(fill=X, padx=10)

        Label(r1, text="Biển số:", font=F_BOLD, bg=CARD, fg=TEXT).pack(side=LEFT)

        self.v_query = StringVar()
        self.v_query.trace_add("write", lambda *_: self._apply_filter())
        Entry(r1, textvariable=self.v_query, font=("Segoe UI", 11),
              width=28, bg="#181828", fg=TEXT, insertbackground=TEXT,
              relief="flat", highlightthickness=1, highlightbackground=ACCENT2,
              ).pack(side=LEFT, padx=(6, 0))

        self.v_regex = BooleanVar(value=False)
        Checkbutton(r1, text="Regex", variable=self.v_regex,
                    command=self._apply_filter,
                    bg=CARD, fg=DIM, font=F_MAIN,
                    activebackground=CARD, selectcolor=CARD,
                    ).pack(side=LEFT, padx=(8, 0))

        Checkbutton(r1, text="Tìm gần đúng", variable=self.v_fuzzy,
                    command=self._on_fuzzy_toggle,
                    bg=CARD, fg=DIM, font=F_MAIN,
                    activebackground=CARD, selectcolor=CARD,
                    ).pack(side=LEFT, padx=(8, 0))

        Label(r1, text="Ngưỡng:", font=F_MAIN, bg=CARD, fg=DIM).pack(side=LEFT, padx=(4, 0))
        self.spin_threshold = Spinbox(
            r1, from_=1, to=100, textvariable=self.v_threshold,
            width=4, font=F_MAIN, bg="#181828", fg=TEXT,
            buttonbackground=CARD, relief="flat",
            command=self._apply_filter,
        )
        self.spin_threshold.pack(side=LEFT, padx=(2, 0))
        self.spin_threshold.bind("<Return>", lambda _: self._apply_filter())
        Label(r1, text="%", font=F_MAIN, bg=CARD, fg=DIM).pack(side=LEFT)

        Button(r1, text="Xóa", command=self._clear_search,
               bg="#333350", fg=TEXT, font=F_MAIN, relief="flat",
               padx=6, cursor="hand2",
               ).pack(side=LEFT, padx=(4, 0))

        # --- row 2: action buttons + chips ---
        r2 = Frame(bar, bg=CARD)
        r2.pack(fill=X, padx=10, pady=(6, 0))

        Button(r2, text="Xuất CSV", command=self._export_csv,
               bg="#1e6b3a", fg="white", font=F_MAIN, relief="flat",
               padx=8, cursor="hand2",
               activebackground="#145228", activeforeground="white",
               ).pack(side=LEFT)
        Button(r2, text="Xuất folder", command=self._export_folder,
               bg="#1a4e7a", fg="white", font=F_MAIN, relief="flat",
               padx=8, cursor="hand2",
               activebackground="#0e3358", activeforeground="white",
               ).pack(side=LEFT, padx=(4, 0))
        Button(r2, text="Tìm từ file", command=self._batch_search,
               bg="#5c3470", fg="white", font=F_MAIN, relief="flat",
               padx=8, cursor="hand2",
               activebackground="#3d2250", activeforeground="white",
               ).pack(side=LEFT, padx=(4, 0))
        Button(r2, text="Xóa batch", command=self._clear_batch,
               bg="#333350", fg=DIM, font=F_MAIN, relief="flat",
               padx=6, cursor="hand2",
               ).pack(side=LEFT, padx=(4, 0))

        chip_f = Frame(r2, bg=CARD)
        chip_f.pack(side=LEFT, padx=(16, 0))
        Label(chip_f, text="Nhanh:", font=F_MAIN, bg=CARD, fg=DIM).pack(side=LEFT)
        for lbl, pat in [
            ("Z*","Z*"), ("*000*","*000*"), ("*111*","*111*"),
            ("*888*","*888*"), ("*999*","*999*"), ("*1234*","*1234*"),
        ]:
            Button(chip_f, text=lbl,
                   command=lambda p=pat: (self.v_regex.set(False), self._clear_batch_silent(), self.v_query.set(p)),
                   bg="#2e2a50", fg=TEXT, font=("Segoe UI", 8, "bold"),
                   relief="flat", padx=6, pady=1, cursor="hand2",
                   activebackground=ACCENT2, activeforeground="white",
                   ).pack(side=LEFT, padx=2)

    # ---- main: table + preview ----
    def _build_main(self):
        paned = PanedWindow(self, orient=HORIZONTAL, bg="#111120",
                            sashwidth=5, sashrelief="flat", sashpad=1)
        paned.pack(fill=BOTH, expand=True)

        self._build_table_pane(paned)
        self._build_preview_pane(paned)

    def _build_table_pane(self, paned):
        frame = Frame(paned, bg=BG)
        paned.add(frame, minsize=380, width=820)

        style = ttk.Style()
        style.configure("GT.Treeview",
                         background=CARD, fieldbackground=CARD,
                         foreground=TEXT, font=F_MONO, rowheight=22)
        style.configure("GT.Treeview.Heading",
                         background=BG, foreground=TEXT,
                         font=F_BOLD, relief="flat")
        style.map("GT.Treeview",
                  background=[("selected", ACCENT2)],
                  foreground=[("selected", "white")])
        style.map("GT.Treeview.Heading",
                  background=[("active", ACCENT2)])

        # Columns vary depending on mode; we include all possible columns
        cols = ("stt", "filename", "plate", "similarity", "batch_query")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings",
                                  selectmode="browse", style="GT.Treeview",
                                  displaycolumns=("stt", "filename", "plate"))

        self.tree.heading("stt",         text="#",          anchor=CENTER)
        self.tree.heading("filename",    text="Tên file",   anchor=W)
        self.tree.heading("plate",       text="Biển số",    anchor=CENTER)
        self.tree.heading("similarity",  text="Độ khớp",   anchor=CENTER)
        self.tree.heading("batch_query", text="Biển tìm",   anchor=CENTER)
        self.tree.column("stt",         width=50,  stretch=False, anchor=CENTER)
        self.tree.column("filename",    width=560, stretch=True,  anchor=W)
        self.tree.column("plate",       width=130, stretch=False, anchor=CENTER)
        self.tree.column("similarity",  width=80,  stretch=False, anchor=CENTER)
        self.tree.column("batch_query", width=110, stretch=False, anchor=CENTER)

        self.tree.tag_configure("odd",   background=_ODD_BG)
        self.tree.tag_configure("hit",   foreground=_HIT_FG, font=(*F_MONO[:1], F_MONO[1], "bold"))
        self.tree.tag_configure("fuzzy", foreground=_FUZZY_FG, font=(*F_MONO[:1], F_MONO[1], "bold"))
        self.tree.tag_configure("batch", foreground=_MATCH_FG, font=(*F_MONO[:1], F_MONO[1], "bold"))

        vsb = ttk.Scrollbar(frame, orient=VERTICAL,   command=self.tree.yview)
        hsb = ttk.Scrollbar(frame, orient=HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        self.v_status = StringVar(value="Chưa tải file GT.")
        Label(frame, textvariable=self.v_status, font=F_MAIN,
              bg=BG, fg=DIM, anchor=W).grid(row=2, column=0, columnspan=2,
                                              sticky="ew", padx=4, pady=2)

        self.tree.bind("<<TreeviewSelect>>", self._on_row_select)
        self.tree.bind("<Button-3>", self._copy_menu)

    def _build_preview_pane(self, paned):
        frame = Frame(paned, bg=BG)
        paned.add(frame, minsize=240, width=460)

        hdr = Frame(frame, bg=ACCENT2, height=28)
        hdr.pack(fill=X)
        hdr.pack_propagate(False)
        Label(hdr, text="Xem ảnh", font=F_BOLD, fg="white", bg=ACCENT2
              ).pack(side=LEFT, padx=10)

        self.v_badge = StringVar(value="—")
        Label(frame, textvariable=self.v_badge,
              font=("Consolas", 20, "bold"),
              fg="white", bg=ACCENT, padx=12, pady=4,
              ).pack(fill=X)

        self.img_canvas = Canvas(frame, bg=_CANVAS_BG, highlightthickness=0,
                                  cursor="crosshair")
        self.img_canvas.pack(fill=BOTH, expand=True)
        self.img_canvas.bind("<Configure>", lambda _: self._rerender())
        self.img_canvas.bind("<Double-Button-1>", self._on_img_zoom)

        self.v_fname = StringVar(value="Chọn một dòng để xem ảnh")
        Label(frame, textvariable=self.v_fname,
              font=("Consolas", 7), fg=DIM, bg=BG,
              anchor=W, wraplength=440).pack(fill=X, padx=6, pady=(2, 4))

    # =============================================================== LOGIC ==
    def _auto_load(self):
        img_dir = self.v_imgdir.get()
        if img_dir and os.path.isdir(img_dir):
            self.img_dir = img_dir

        gt = self.v_gt.get()
        if gt and os.path.isfile(gt):
            self._load_file_from_path(gt)

    def _load_file(self):
        path = filedialog.askopenfilename(
            title="Chọn file Ground Truth",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            parent=self.root,
        )
        if path:
            _push_history("h.plate_search.gt", path)
            self._load_file_from_path(path)

    def _load_file_from_path(self, path: str):
        try:
            rows = []
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.rstrip("\n")
                    if "\t" in line:
                        parts = line.split("\t", 1)
                        rows.append((parts[0].strip(), parts[1].strip()))
            self.all_rows = rows
            self.v_gt.set(path)
            if not self.img_dir:
                d = os.path.dirname(path)
                self.img_dir = d
                self.v_imgdir.set(d)
            self._apply_filter()
            self.v_status.set(f"Đã tải {len(rows):,} dòng  ·  {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Lỗi", str(e), parent=self.root)

    def _open_img_dir(self):
        if self.img_dir and os.path.isdir(self.img_dir):
            os.startfile(self.img_dir)

    def _pick_img_dir(self):
        d = filedialog.askdirectory(title="Chọn thư mục chứa ảnh", parent=self.root)
        if d:
            self.img_dir = d
            self.v_imgdir.set(d)
            _push_history("h.plate_search.imgdir", d)
            sel = self.tree.selection()
            if sel:
                vals = self.tree.item(sel[0], "values")
                self._show_image(vals[1], vals[2])

    # ---- fuzzy helpers ----
    def _on_fuzzy_toggle(self):
        self._apply_filter()

    def _fuzzy_similarity(self, a: str, b: str) -> float:
        return difflib.SequenceMatcher(None, a.upper(), b.upper()).ratio() * 100

    def _get_threshold(self) -> float:
        try:
            v = float(self.v_threshold.get())
            return max(1.0, min(100.0, v))
        except ValueError:
            return 80.0

    # ---- filter / search ----
    def _clear_search(self):
        self.v_query.set("")

    def _clear_batch_silent(self):
        self._batch_queries = []

    def _clear_batch(self):
        self._batch_queries = []
        self._apply_filter()

    def _apply_filter(self):
        if self._batch_queries:
            self._apply_batch_filter()
            return

        query = self.v_query.get().strip()
        fuzzy  = self.v_fuzzy.get()
        thresh = self._get_threshold()

        if not query:
            self.filtered = [(f, p, "", "") for f, p in self.all_rows]
        elif fuzzy:
            results = []
            for fname, plate in self.all_rows:
                sim = self._fuzzy_similarity(query, plate)
                if sim >= thresh:
                    results.append((fname, plate, f"{sim:.0f}%", query))
            results.sort(key=lambda r: -float(r[2].rstrip("%")))
            self.filtered = results
        elif self.v_regex.get():
            try:
                pat = re.compile(query, re.IGNORECASE)
                self.filtered = [(f, p, "", query) for f, p in self.all_rows if pat.search(p)]
            except re.error:
                self.filtered = []
        else:
            q = query.upper()
            self.filtered = [(f, p, "", query) for f, p in self.all_rows
                             if fnmatch.fnmatch(p.upper(), q)]

        self._refresh_table()

    def _apply_batch_filter(self):
        fuzzy  = self.v_fuzzy.get()
        thresh = self._get_threshold()
        results = []
        for bq in self._batch_queries:
            bq_up = bq.upper()
            if fuzzy:
                for fname, plate in self.all_rows:
                    sim = self._fuzzy_similarity(bq, plate)
                    if sim >= thresh:
                        results.append((fname, plate, f"{sim:.0f}%", bq))
                results_for_bq = sorted(
                    [(f, p, s, q) for f, p, s, q in results if q == bq],
                    key=lambda r: -float(r[2].rstrip("%"))
                )
            else:
                for fname, plate in self.all_rows:
                    if fnmatch.fnmatch(plate.upper(), bq_up):
                        results.append((fname, plate, "", bq))
        self.filtered = results
        self._refresh_table()

    def _refresh_table(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        fuzzy       = self.v_fuzzy.get()
        batch_mode  = bool(self._batch_queries)
        has_sim     = fuzzy or any(r[2] for r in self.filtered)

        # adjust visible columns
        if batch_mode and has_sim:
            self.tree.configure(displaycolumns=("stt", "filename", "plate", "similarity", "batch_query"))
        elif batch_mode:
            self.tree.configure(displaycolumns=("stt", "filename", "plate", "batch_query"))
        elif has_sim:
            self.tree.configure(displaycolumns=("stt", "filename", "plate", "similarity"))
        else:
            self.tree.configure(displaycolumns=("stt", "filename", "plate"))

        query = self.v_query.get().strip()

        for i, row in enumerate(self.filtered, 1):
            fname, plate, sim, row_query = row
            if batch_mode:
                tag = "batch"
            elif sim:
                tag = "fuzzy"
            elif row_query:
                tag = "hit"
            else:
                tag = "odd" if i % 2 else ""
            self.tree.insert("", END, values=(i, fname, plate, sim, row_query), tags=(tag,))

        total = len(self.all_rows)
        found = len(self.filtered)
        if total:
            pct = found / total * 100
            label = self.v_query.get().strip() or (f"batch:{len(self._batch_queries)}" if batch_mode else "")
            self.v_status.set(
                f"Hiển thị {found:,} / {total:,} dòng  ({pct:.1f}%)"
                + (f'  ·  "{label}"' if label else "")
                + ("  [Gần đúng]" if fuzzy else "")
                + ("  [Batch]" if batch_mode else "")
            )
        self._clear_preview()

    # ---- batch search ----
    def _batch_search(self):
        path = filedialog.askopenfilename(
            title="Chọn file danh sách biển số (.txt)",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            parent=self.root,
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                queries = [ln.strip() for ln in f if ln.strip()]
        except Exception as e:
            messagebox.showerror("Lỗi", str(e), parent=self.root)
            return
        if not queries:
            messagebox.showinfo("Thông báo", "File không có biển số nào.", parent=self.root)
            return
        self._batch_queries = queries
        self.v_query.set("")
        self._apply_filter()

    # ---- export ----
    def _export_csv(self):
        if not self.filtered:
            messagebox.showinfo("Xuất CSV", "Không có kết quả để xuất.", parent=self.root)
            return
        path = filedialog.asksaveasfilename(
            title="Lưu kết quả CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            parent=self.root,
        )
        if not path:
            return
        try:
            fuzzy      = self.v_fuzzy.get()
            batch_mode = bool(self._batch_queries)
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                headers = ["#", "Tên file", "Biển số"]
                if fuzzy or any(r[2] for r in self.filtered):
                    headers.append("Độ khớp")
                if batch_mode:
                    headers.append("Biển tìm")
                writer.writerow(headers)
                for i, row in enumerate(self.filtered, 1):
                    fname, plate, sim, row_query = row
                    rec = [i, fname, plate]
                    if "Độ khớp" in headers:
                        rec.append(sim)
                    if "Biển tìm" in headers:
                        rec.append(row_query)
                    writer.writerow(rec)
            messagebox.showinfo("Xuất CSV", f"Đã lưu {len(self.filtered):,} dòng\n{path}", parent=self.root)
        except Exception as e:
            messagebox.showerror("Lỗi", str(e), parent=self.root)

    def _export_folder(self):
        if not self.filtered:
            messagebox.showinfo("Xuất folder", "Không có kết quả để xuất.", parent=self.root)
            return
        if not self.img_dir:
            messagebox.showwarning("Xuất folder", "Chưa chọn thư mục ảnh nguồn.", parent=self.root)
            return
        dest = filedialog.askdirectory(title="Chọn thư mục đích để sao chép ảnh", parent=self.root)
        if not dest:
            return
        ok = 0
        missing = 0
        for row in self.filtered:
            fname = row[0]
            src = os.path.join(self.img_dir, fname)
            if not os.path.isfile(src):
                if os.path.isfile(fname):
                    src = fname
                else:
                    missing += 1
                    continue
            dst = os.path.join(dest, os.path.basename(fname))
            try:
                shutil.copy2(src, dst)
                ok += 1
            except Exception:
                missing += 1
        msg = f"Đã sao chép {ok:,} ảnh vào:\n{dest}"
        if missing:
            msg += f"\n(Không tìm thấy {missing:,} file)"
        messagebox.showinfo("Xuất folder", msg, parent=self.root)

    # ---- row select / preview ----
    def _on_row_select(self, _=None):
        sel = self.tree.selection()
        if sel:
            vals = self.tree.item(sel[0], "values")
            self._show_image(vals[1], vals[2])

    def _show_image(self, filename: str, plate: str):
        self.v_badge.set(plate)
        self.v_fname.set(filename)
        if not _PIL_OK:
            self._draw_text("Pillow chưa được cài.\npip install Pillow")
            return
        img_path = os.path.join(self.img_dir, filename) if self.img_dir else filename
        if not os.path.isfile(img_path):
            if os.path.isfile(filename):
                img_path = filename
            else:
                self._draw_text(f"Không tìm thấy:\n{img_path}")
                self._current_img_path = ""
                return
        self._current_img_path = img_path
        self._rerender()

    def _rerender(self):
        if not self._current_img_path or not _PIL_OK:
            return
        try:
            img = Image.open(self._current_img_path)
        except Exception as e:
            self._draw_text(str(e))
            return
        cw = self.img_canvas.winfo_width()
        ch = self.img_canvas.winfo_height()
        if cw < 10 or ch < 10:
            self.after(50, self._rerender)
            return
        iw, ih = img.size
        scale = min(cw / iw, ch / ih)
        nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
        img = img.resize((nw, nh), Image.LANCZOS)
        self._photo_ref = ImageTk.PhotoImage(img)
        self.img_canvas.delete("all")
        self.img_canvas.create_image(cw // 2, ch // 2, anchor=CENTER,
                                      image=self._photo_ref)

    def _on_img_zoom(self, _event=None):
        if not self._current_img_path or not _PIL_OK:
            return
        try:
            img = Image.open(self._current_img_path).convert("RGB")
        except Exception:
            return
        from ...core.ui_helpers import _zoom_image_window, _load_label_bboxes
        fname = os.path.basename(self._current_img_path)
        bboxes = _load_label_bboxes(self._current_img_path)
        _zoom_image_window(self.root, img, fname, bboxes=bboxes)

    def _draw_text(self, msg: str):
        self._photo_ref = None
        cw = self.img_canvas.winfo_width()  or 400
        ch = self.img_canvas.winfo_height() or 300
        self.img_canvas.delete("all")
        self.img_canvas.create_text(cw // 2, ch // 2, text=msg,
                                     fill=DIM, font=F_MAIN,
                                     width=cw - 20, justify=CENTER)

    def _clear_preview(self):
        self._current_img_path = ""
        self._photo_ref = None
        self.v_badge.set("—")
        self.v_fname.set("Chọn một dòng để xem ảnh")
        self.img_canvas.delete("all")

    def _copy_menu(self, event):
        item = self.tree.identify_row(event.y)
        if not item:
            return
        vals = self.tree.item(item, "values")
        menu = Menu(self, tearoff=0, bg=CARD, fg=TEXT, activebackground=ACCENT2)
        menu.add_command(label=f"Sao chép biển số: {vals[2]}",
                         command=lambda: self._copy(vals[2]))
        menu.add_command(label="Sao chép tên file",
                         command=lambda: self._copy(vals[1]))
        menu.add_command(label="Sao chép cả dòng",
                         command=lambda: self._copy(f"{vals[1]}\t{vals[2]}"))
        menu.tk_popup(event.x_root, event.y_root)

    def _copy(self, text: str):
        self.clipboard_clear()
        self.clipboard_append(text)

    # ── Navigation aliases cho app.py ←/→ routing ────────────────────

    def _prev_image(self):
        """← — chọn dòng trên trong bảng kết quả."""
        sel = self.tree.selection()
        if sel:
            prev = self.tree.prev(sel[0])
            if prev:
                self.tree.selection_set(prev)
                self.tree.see(prev)
                self._on_row_select()
        elif self.tree.get_children():
            last = self.tree.get_children()[-1]
            self.tree.selection_set(last)
            self.tree.see(last)
            self._on_row_select()

    def _next_image(self):
        """→ — chọn dòng dưới trong bảng kết quả."""
        sel = self.tree.selection()
        if sel:
            nxt = self.tree.next(sel[0])
            if nxt:
                self.tree.selection_set(nxt)
                self.tree.see(nxt)
                self._on_row_select()
        elif self.tree.get_children():
            first = self.tree.get_children()[0]
            self.tree.selection_set(first)
            self.tree.see(first)
            self._on_row_select()
