import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import fnmatch
import os
import re
import json
from PIL import Image, ImageTk

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plate_search_config.json")

BRAND_NAVY    = "#251C53"
BRAND_ORANGE  = "#F05922"
BRAND_NAVY2   = "#4A3F8C"
BRAND_LIGHT   = "#B8B3D6"
BRAND_GRAY    = "#CBCBCB"
BRAND_WHITE   = "#FFFFFF"
BRAND_ORANGE2 = "#FFAA80"

class PlateSearchApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("KZTEK — Tra cứu Biển số xe")
        self.geometry("1380x720")
        self.configure(bg=BRAND_WHITE)
        self.resizable(True, True)

        self.all_rows: list[tuple[str, str]] = []
        self.filtered: list[tuple[str, str]] = []
        self.img_dir: str = ""
        self._photo_ref = None          # keep reference so GC won't free it

        self._build_ui()
        self._load_config()

    # ------------------------------------------------------------------ UI ---
    def _build_ui(self):
        self._build_header()
        self._build_toolbar()
        self._build_main()
        self._build_statusbar()

    def _build_header(self):
        hdr = tk.Frame(self, bg=BRAND_NAVY, height=56)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        tk.Label(hdr, text="KZTEK", font=("Segoe UI", 18, "bold"),
                 fg=BRAND_ORANGE, bg=BRAND_NAVY).pack(side="left", padx=18, pady=8)
        tk.Label(hdr, text="Tra cứu Biển số xe  |  Ground Truth Viewer",
                 font=("Segoe UI", 12), fg=BRAND_LIGHT, bg=BRAND_NAVY).pack(side="left", padx=4)

    def _build_toolbar(self):
        bar = tk.Frame(self, bg=BRAND_WHITE, pady=10)
        bar.pack(fill="x", padx=16)

        # --- File GT ---
        tk.Label(bar, text="File GT:", font=("Segoe UI", 10, "bold"),
                 bg=BRAND_WHITE, fg=BRAND_NAVY).grid(row=0, column=0, sticky="w")

        self.file_var = tk.StringVar(value="Chưa chọn file...")
        tk.Label(bar, textvariable=self.file_var, font=("Segoe UI", 9),
                 bg=BRAND_WHITE, fg=BRAND_NAVY2, width=55, anchor="w").grid(row=0, column=1, padx=(6,0))

        tk.Button(bar, text="Mở file GT...", command=self._load_file,
                  bg=BRAND_ORANGE, fg=BRAND_WHITE, font=("Segoe UI", 9, "bold"),
                  relief="flat", padx=10, cursor="hand2",
                  activebackground=BRAND_ORANGE2, activeforeground=BRAND_NAVY,
                  ).grid(row=0, column=2, padx=(10, 0))

        # --- Thư mục ảnh ---
        tk.Label(bar, text="Thư mục ảnh:", font=("Segoe UI", 10, "bold"),
                 bg=BRAND_WHITE, fg=BRAND_NAVY).grid(row=0, column=3, sticky="w", padx=(18,0))

        self.imgdir_var = tk.StringVar(value="(cùng thư mục file GT)")
        tk.Label(bar, textvariable=self.imgdir_var, font=("Segoe UI", 9),
                 bg=BRAND_WHITE, fg=BRAND_NAVY2, width=38, anchor="w").grid(row=0, column=4, padx=(6,0))

        tk.Button(bar, text="Chọn...", command=self._pick_img_dir,
                  bg=BRAND_GRAY, fg=BRAND_NAVY, font=("Segoe UI", 9),
                  relief="flat", padx=8, cursor="hand2",
                  ).grid(row=0, column=5, padx=(6, 0))

        # --- Search ---
        tk.Label(bar, text="Tìm biển số:", font=("Segoe UI", 10, "bold"),
                 bg=BRAND_WHITE, fg=BRAND_NAVY).grid(row=1, column=0, sticky="w", pady=(10,0))

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._apply_filter())

        entry = tk.Entry(bar, textvariable=self.search_var, font=("Segoe UI", 11),
                         width=32, relief="solid", bd=1,
                         fg=BRAND_NAVY, insertbackground=BRAND_NAVY)
        entry.grid(row=1, column=1, padx=(6,0), pady=(10,0), sticky="w")
        entry.bind("<Return>", lambda _: self._apply_filter())

        tk.Label(bar, text="Hỗ trợ: Z* · *000* · 11?A* · regex (bật nút bên phải)",
                 font=("Segoe UI", 8), fg=BRAND_GRAY, bg=BRAND_WHITE,
                 ).grid(row=2, column=1, sticky="w", padx=(6,0))

        self.regex_var = tk.BooleanVar(value=False)
        tk.Checkbutton(bar, text="Regex", variable=self.regex_var, command=self._apply_filter,
                       bg=BRAND_WHITE, fg=BRAND_NAVY2, font=("Segoe UI", 9),
                       activebackground=BRAND_WHITE, selectcolor=BRAND_WHITE,
                       ).grid(row=1, column=2, padx=(10,0), pady=(10,0), sticky="w")

        tk.Button(bar, text="Xóa", command=self._clear_search,
                  bg=BRAND_GRAY, fg=BRAND_NAVY, font=("Segoe UI", 9),
                  relief="flat", padx=8, cursor="hand2",
                  ).grid(row=1, column=3, padx=(6,0), pady=(10,0), sticky="w")

        # --- Chips ---
        chip_frame = tk.Frame(bar, bg=BRAND_WHITE)
        chip_frame.grid(row=3, column=0, columnspan=8, sticky="w", pady=(10,0))

        tk.Label(chip_frame, text="Nhanh:", font=("Segoe UI", 9),
                 bg=BRAND_WHITE, fg=BRAND_NAVY).pack(side="left")

        for label, pattern in [
            ("Z*","Z*"), ("*000*","*000*"), ("*111*","*111*"),
            ("*888*","*888*"), ("*999*","*999*"), ("*1234*","*1234*"),
            ("*5678*","*5678*"), ("*6789*","*6789*"),
        ]:
            tk.Button(chip_frame, text=label, command=lambda p=pattern: self._set_search(p),
                      bg=BRAND_LIGHT, fg=BRAND_NAVY, font=("Segoe UI", 8, "bold"),
                      relief="flat", padx=8, pady=2, cursor="hand2",
                      activebackground=BRAND_NAVY2, activeforeground=BRAND_WHITE,
                      ).pack(side="left", padx=3)

    def _build_main(self):
        """Horizontal PanedWindow: table (left) | image preview (right)."""
        self.paned = tk.PanedWindow(self, orient="horizontal", bg=BRAND_GRAY,
                                    sashwidth=5, sashrelief="flat", sashpad=1)
        self.paned.pack(fill="both", expand=True, padx=16, pady=(8, 0))

        self._build_table_pane()
        self._build_preview_pane()

    # ---- left pane: table ----
    def _build_table_pane(self):
        frame = tk.Frame(self.paned, bg=BRAND_WHITE)
        self.paned.add(frame, minsize=400, width=820)

        cols = ("stt", "filename", "plate")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="browse")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview",
                         background=BRAND_WHITE, fieldbackground=BRAND_WHITE,
                         foreground=BRAND_NAVY, font=("Consolas", 9), rowheight=22)
        style.configure("Treeview.Heading",
                         background=BRAND_NAVY, foreground=BRAND_WHITE,
                         font=("Segoe UI", 9, "bold"), relief="flat")
        style.map("Treeview",
                  background=[("selected", BRAND_ORANGE2)],
                  foreground=[("selected", BRAND_NAVY)])
        style.map("Treeview.Heading",
                  background=[("active", BRAND_NAVY2)])

        self.tree.heading("stt",      text="#",       anchor="center")
        self.tree.heading("filename", text="Tên file", anchor="w")
        self.tree.heading("plate",    text="Biển số",  anchor="center")

        self.tree.column("stt",      width=50,  stretch=False, anchor="center")
        self.tree.column("filename", width=640, stretch=True,  anchor="w")
        self.tree.column("plate",    width=130, stretch=False, anchor="center")

        self.tree.tag_configure("odd",  background="#F4F3FA")
        self.tree.tag_configure("even", background=BRAND_WHITE)
        self.tree.tag_configure("hit",  foreground=BRAND_ORANGE, font=("Consolas", 9, "bold"))

        vsb = ttk.Scrollbar(frame, orient="vertical",   command=self.tree.yview)
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        self.tree.bind("<<TreeviewSelect>>", self._on_row_select)
        self.tree.bind("<Button-3>", self._copy_menu)

    # ---- right pane: image preview ----
    def _build_preview_pane(self):
        self.preview_frame = tk.Frame(self.paned, bg=BRAND_NAVY, bd=0)
        self.paned.add(self.preview_frame, minsize=260, width=480)

        # header strip
        hdr = tk.Frame(self.preview_frame, bg=BRAND_NAVY2, height=30)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="Xem ảnh", font=("Segoe UI", 9, "bold"),
                 fg=BRAND_WHITE, bg=BRAND_NAVY2).pack(side="left", padx=10)

        # plate badge
        self.badge_var = tk.StringVar(value="—")
        badge = tk.Label(self.preview_frame, textvariable=self.badge_var,
                         font=("Consolas", 22, "bold"),
                         fg=BRAND_WHITE, bg=BRAND_ORANGE,
                         padx=16, pady=6)
        badge.pack(fill="x")

        # image canvas
        self.img_canvas = tk.Canvas(self.preview_frame, bg="#1a1232",
                                    highlightthickness=0, cursor="crosshair")
        self.img_canvas.pack(fill="both", expand=True)
        self.img_canvas.bind("<Configure>", self._on_canvas_resize)

        # filename label
        self.fname_var = tk.StringVar(value="Chọn một dòng trong bảng để xem ảnh")
        tk.Label(self.preview_frame, textvariable=self.fname_var,
                 font=("Consolas", 7), fg=BRAND_GRAY, bg=BRAND_NAVY,
                 anchor="w", wraplength=460).pack(fill="x", padx=6, pady=(2,4))

        self._current_img_path: str = ""   # path of image currently displayed

    def _build_statusbar(self):
        bar = tk.Frame(self, bg=BRAND_NAVY, height=26)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)

        self.status_var = tk.StringVar(value="Chưa tải file GT.")
        tk.Label(bar, textvariable=self.status_var, font=("Segoe UI", 9),
                 fg=BRAND_LIGHT, bg=BRAND_NAVY, anchor="w").pack(side="left", padx=12)
        tk.Label(bar, text="KZTEK © 2024", font=("Segoe UI", 8),
                 fg=BRAND_GRAY, bg=BRAND_NAVY).pack(side="right", padx=12)

    # --------------------------------------------------------------- Logic ---
    # ---------------------------------------------------------- Config I/O ---
    def _load_config(self):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return

        gt_path = cfg.get("gt_path", "")
        img_dir = cfg.get("img_dir", "")

        if img_dir and os.path.isdir(img_dir):
            self.img_dir = img_dir
            self.imgdir_var.set(img_dir)

        if gt_path and os.path.isfile(gt_path):
            self._load_file_from_path(gt_path)

    def _save_config(self):
        cfg = {
            "gt_path": self.file_var.get() if self.all_rows else "",
            "img_dir": self.img_dir,
        }
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ------------------------------------------------------------- File I/O ---
    def _load_file(self):
        path = filedialog.askopenfilename(
            title="Chọn file Ground Truth",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return
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
            self.file_var.set(path)
            # auto-set image dir to same folder as gt.txt (only if not already set)
            if not self.img_dir:
                self.img_dir = os.path.dirname(path)
                self.imgdir_var.set(self.img_dir)
            self._apply_filter()
            self.status_var.set(f"Đã tải {len(rows):,} dòng  ·  {os.path.basename(path)}")
            self._save_config()
        except Exception as e:
            messagebox.showerror("Lỗi", str(e))

    def _pick_img_dir(self):
        d = filedialog.askdirectory(title="Chọn thư mục chứa ảnh")
        if d:
            self.img_dir = d
            self.imgdir_var.set(d)
            self._save_config()
            # re-display current image with new dir
            sel = self.tree.selection()
            if sel:
                vals = self.tree.item(sel[0], "values")
                self._show_image(vals[1], vals[2])

    def _apply_filter(self):
        query = self.search_var.get().strip()
        use_regex = self.regex_var.get()

        if not query:
            self.filtered = list(self.all_rows)
        else:
            if use_regex:
                try:
                    pat = re.compile(query, re.IGNORECASE)
                    self.filtered = [(f, p) for f, p in self.all_rows if pat.search(p)]
                except re.error:
                    self.filtered = []
            else:
                q_up = query.upper()
                self.filtered = [
                    (f, p) for f, p in self.all_rows
                    if fnmatch.fnmatch(p.upper(), q_up)
                ]

        self._refresh_table()

    def _refresh_table(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        query = self.search_var.get().strip()
        for i, (fname, plate) in enumerate(self.filtered, start=1):
            tag = "hit" if query else ("odd" if i % 2 else "even")
            self.tree.insert("", "end", values=(i, fname, plate), tags=(tag,))

        total = len(self.all_rows)
        found = len(self.filtered)
        if total:
            pct = found / total * 100
            self.status_var.set(
                f"Hiển thị {found:,} / {total:,} dòng  ({pct:.1f}%)"
                + (f'  ·  Mẫu: "{self.search_var.get()}"' if query else "")
            )
        # clear preview when list changes
        self._clear_preview()

    def _on_row_select(self, _event=None):
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0], "values")
        # vals = (stt, filename, plate)
        self._show_image(vals[1], vals[2])

    def _show_image(self, filename: str, plate: str):
        self.badge_var.set(plate)
        self.fname_var.set(filename)

        img_path = os.path.join(self.img_dir, filename) if self.img_dir else filename

        if not os.path.isfile(img_path):
            # try without directory (absolute path in filename)
            if os.path.isfile(filename):
                img_path = filename
            else:
                self._show_no_image(f"Không tìm thấy:\n{img_path}")
                return

        self._current_img_path = img_path
        self._render_image()

    def _render_image(self):
        if not self._current_img_path:
            return
        try:
            img = Image.open(self._current_img_path)
        except Exception as e:
            self._show_no_image(str(e))
            return

        cw = self.img_canvas.winfo_width()
        ch = self.img_canvas.winfo_height()
        if cw < 10 or ch < 10:
            # canvas not yet realized — defer
            self.after(50, self._render_image)
            return

        # fit inside canvas maintaining aspect ratio
        iw, ih = img.size
        scale = min(cw / iw, ch / ih, 1.0)   # never upscale beyond 1:1
        nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
        img = img.resize((nw, nh), Image.LANCZOS)

        self._photo_ref = ImageTk.PhotoImage(img)
        self.img_canvas.delete("all")
        self.img_canvas.create_image(cw // 2, ch // 2, anchor="center",
                                     image=self._photo_ref)

    def _on_canvas_resize(self, _event=None):
        if self._current_img_path:
            self.after(30, self._render_image)

    def _show_no_image(self, msg: str):
        self._current_img_path = ""
        self._photo_ref = None
        cw = self.img_canvas.winfo_width()  or 400
        ch = self.img_canvas.winfo_height() or 300
        self.img_canvas.delete("all")
        self.img_canvas.create_text(cw // 2, ch // 2, text=msg,
                                    fill=BRAND_GRAY, font=("Segoe UI", 9),
                                    width=cw - 20, justify="center")

    def _clear_preview(self):
        self._current_img_path = ""
        self._photo_ref = None
        self.badge_var.set("—")
        self.fname_var.set("Chọn một dòng trong bảng để xem ảnh")
        self.img_canvas.delete("all")

    def _set_search(self, pattern: str):
        self.regex_var.set(False)
        self.search_var.set(pattern)

    def _clear_search(self):
        self.search_var.set("")

    def _copy_menu(self, event):
        item = self.tree.identify_row(event.y)
        if not item:
            return
        vals = self.tree.item(item, "values")
        menu = tk.Menu(self, tearoff=0)
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


if __name__ == "__main__":
    app = PlateSearchApp()
    app.mainloop()
