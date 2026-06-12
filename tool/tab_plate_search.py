# tab_plate_search.py — Ground Truth Plate Search tab
import fnmatch
import os
import re
from tkinter import *
from tkinter import ttk, filedialog

from .constants import BG, CARD, ACCENT, ACCENT2, TEXT, DIM, F_MAIN, F_BOLD, F_MONO
from .settings  import _bind_cfg, _CFG, _cfg_save

try:
    from PIL import Image, ImageTk
    _PIL_OK = True
except ImportError:
    _PIL_OK = False

_CANVAS_BG = "#0d0d1a"
_HIT_FG    = ACCENT
_ODD_BG    = "#232336"


class PlateSearchTab(Frame):
    def __init__(self, master, root):
        super().__init__(master, bg=BG)
        self.root = root

        self.all_rows: list = []    # [(filename, plate), ...]
        self.filtered:  list = []
        self.img_dir:   str  = ""
        self._photo_ref      = None
        self._current_img_path: str = ""

        # StringVars for path display (also hooked to settings)
        self.v_gt     = StringVar()
        self.v_imgdir = StringVar()
        _bind_cfg("plate_search.gt_path",  self.v_gt)
        _bind_cfg("plate_search.img_dir",  self.v_imgdir)

        self._build()
        # auto-load saved paths after UI is realised
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
               ).pack(side=LEFT, padx=(6, 0))

        # --- row 1: search ---
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

        Button(r1, text="Xóa", command=lambda: self.v_query.set(""),
               bg="#333350", fg=TEXT, font=F_MAIN, relief="flat",
               padx=6, cursor="hand2",
               ).pack(side=LEFT, padx=(4, 0))

        # chips
        chip_f = Frame(r1, bg=CARD)
        chip_f.pack(side=LEFT, padx=(16, 0))
        Label(chip_f, text="Nhanh:", font=F_MAIN, bg=CARD, fg=DIM).pack(side=LEFT)
        for lbl, pat in [
            ("Z*","Z*"), ("*000*","*000*"), ("*111*","*111*"),
            ("*888*","*888*"), ("*999*","*999*"), ("*1234*","*1234*"),
        ]:
            Button(chip_f, text=lbl,
                   command=lambda p=pat: (self.v_regex.set(False), self.v_query.set(p)),
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

        cols = ("stt", "filename", "plate")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings",
                                  selectmode="browse", style="GT.Treeview")

        self.tree.heading("stt",      text="#",       anchor=CENTER)
        self.tree.heading("filename", text="Tên file", anchor=W)
        self.tree.heading("plate",    text="Biển số",  anchor=CENTER)
        self.tree.column("stt",      width=50,  stretch=False, anchor=CENTER)
        self.tree.column("filename", width=640, stretch=True,  anchor=W)
        self.tree.column("plate",    width=130, stretch=False, anchor=CENTER)

        self.tree.tag_configure("odd", background=_ODD_BG)
        self.tree.tag_configure("hit", foreground=_HIT_FG, font=(*F_MONO[:1], F_MONO[1], "bold"))

        vsb = ttk.Scrollbar(frame, orient=VERTICAL,   command=self.tree.yview)
        hsb = ttk.Scrollbar(frame, orient=HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        # status bar inside table pane
        self.v_status = StringVar(value="Chưa tải file GT.")
        Label(frame, textvariable=self.v_status, font=F_MAIN,
              bg=BG, fg=DIM, anchor=W).grid(row=2, column=0, columnspan=2,
                                              sticky="ew", padx=4, pady=2)

        self.tree.bind("<<TreeviewSelect>>", self._on_row_select)
        self.tree.bind("<Button-3>", self._copy_menu)

    def _build_preview_pane(self, paned):
        frame = Frame(paned, bg=BG)
        paned.add(frame, minsize=240, width=460)

        # header
        hdr = Frame(frame, bg=ACCENT2, height=28)
        hdr.pack(fill=X)
        hdr.pack_propagate(False)
        Label(hdr, text="Xem ảnh", font=F_BOLD, fg="white", bg=ACCENT2
              ).pack(side=LEFT, padx=10)

        # plate badge
        self.v_badge = StringVar(value="—")
        Label(frame, textvariable=self.v_badge,
              font=("Consolas", 20, "bold"),
              fg="white", bg=ACCENT, padx=12, pady=4,
              ).pack(fill=X)

        # canvas
        self.img_canvas = Canvas(frame, bg=_CANVAS_BG, highlightthickness=0,
                                  cursor="crosshair")
        self.img_canvas.pack(fill=BOTH, expand=True)
        self.img_canvas.bind("<Configure>", lambda _: self._rerender())

        # filename hint
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
            self.v_gt.set(path)           # also triggers _bind_cfg save
            if not self.img_dir:
                d = os.path.dirname(path)
                self.img_dir = d
                self.v_imgdir.set(d)
            self._apply_filter()
            self.v_status.set(f"Đã tải {len(rows):,} dòng  ·  {os.path.basename(path)}")
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Lỗi", str(e), parent=self.root)

    def _pick_img_dir(self):
        d = filedialog.askdirectory(title="Chọn thư mục chứa ảnh", parent=self.root)
        if d:
            self.img_dir = d
            self.v_imgdir.set(d)           # triggers _bind_cfg save
            sel = self.tree.selection()
            if sel:
                vals = self.tree.item(sel[0], "values")
                self._show_image(vals[1], vals[2])

    def _apply_filter(self):
        query = self.v_query.get().strip()
        if not query:
            self.filtered = list(self.all_rows)
        elif self.v_regex.get():
            try:
                pat = re.compile(query, re.IGNORECASE)
                self.filtered = [(f, p) for f, p in self.all_rows if pat.search(p)]
            except re.error:
                self.filtered = []
        else:
            q = query.upper()
            self.filtered = [(f, p) for f, p in self.all_rows
                             if fnmatch.fnmatch(p.upper(), q)]
        self._refresh_table()

    def _refresh_table(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        query = self.v_query.get().strip()
        for i, (fname, plate) in enumerate(self.filtered, 1):
            tag = "hit" if query else ("odd" if i % 2 else "")
            self.tree.insert("", END, values=(i, fname, plate), tags=(tag,))
        total, found = len(self.all_rows), len(self.filtered)
        if total:
            pct = found / total * 100
            self.v_status.set(
                f"Hiển thị {found:,} / {total:,} dòng  ({pct:.1f}%)"
                + (f'  ·  "{query}"' if query else "")
            )
        self._clear_preview()

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
        scale = min(cw / iw, ch / ih)        # allow upscale to fill canvas
        nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
        img = img.resize((nw, nh), Image.LANCZOS)
        self._photo_ref = ImageTk.PhotoImage(img)
        self.img_canvas.delete("all")
        self.img_canvas.create_image(cw // 2, ch // 2, anchor=CENTER,
                                      image=self._photo_ref)

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
