import os
import threading
from pathlib import Path
from tkinter import *
from tkinter import filedialog, messagebox, ttk

from .constants import BG, CARD, ACCENT, ACCENT2, TEXT, DIM, F_MAIN, F_BOLD
from .settings import _bind_cfg, _cfg_dir
from .core_rename import build_rename_plan, execute_rename_plan
from .ui_helpers import _pb_row


class RenameTab(Frame):
    def __init__(self, master, root):
        super().__init__(master, bg=BG)
        self.root  = root
        self._plan = []
        self._build()

    def _build(self):
        row1 = Frame(self, bg=CARD, padx=16, pady=7)
        row1.pack(fill=X)
        self.v_folder = StringVar()
        _bind_cfg("rename.src", self.v_folder)
        Button(row1, text="📂  Folder nguồn", command=self._browse,
               bg=ACCENT2, fg="white", activebackground=ACCENT,
               activeforeground="white", font=F_BOLD,
               relief="flat", padx=14, pady=5, cursor="hand2").pack(side=LEFT)
        Entry(row1, textvariable=self.v_folder, bg="#16162a", fg=TEXT,
              insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4,
              width=52).pack(side=LEFT, padx=10)
        Button(row1, text="🔍  Quét & Xem trước", command=self._scan,
               bg=ACCENT, fg="white", activebackground="#c04010",
               activeforeground="white", font=F_BOLD,
               relief="flat", padx=14, pady=5, cursor="hand2").pack(side=LEFT)

        row2 = Frame(self, bg=CARD, padx=16, pady=7)
        row2.pack(fill=X)
        self.v_out = StringVar()
        _bind_cfg("rename.out", self.v_out)
        Button(row2, text="💾  Folder output", command=self._browse_out,
               bg="#2a4a2a", fg="white", activebackground="#3a6a3a",
               activeforeground="white", font=F_BOLD,
               relief="flat", padx=14, pady=5, cursor="hand2").pack(side=LEFT)
        Entry(row2, textvariable=self.v_out, bg="#16162a", fg=TEXT,
              insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4,
              width=52).pack(side=LEFT, padx=10)
        Button(row2, text="✕  Xóa", command=lambda: self.v_out.set(""),
               bg=CARD, fg=DIM, font=F_MAIN,
               relief="flat", padx=8, pady=5, cursor="hand2").pack(side=LEFT)
        Label(row2, text="  (để trống = đổi tên tại chỗ)",
              bg=CARD, fg=DIM, font=("Segoe UI", 9)).pack(side=LEFT, padx=(8, 0))
        self.btn_open_out = Button(row2, text="🗂  Mở output",
                                   command=self._open_out,
                                   bg=CARD, fg=DIM, font=F_MAIN,
                                   relief="flat", padx=10, pady=5, cursor="hand2")
        self.btn_open_out.pack(side=RIGHT)

        opt = Frame(self, bg=BG, padx=16, pady=7)
        opt.pack(fill=X)

        Label(opt, text="Đánh số:", bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT)
        self.v_per_folder = BooleanVar(value=True)
        Radiobutton(opt, text="Riêng từng folder", variable=self.v_per_folder,
                    value=True, bg=BG, fg=TEXT, selectcolor=CARD,
                    activebackground=BG, font=F_MAIN).pack(side=LEFT, padx=(6, 0))
        Radiobutton(opt, text="Toàn bộ liên tiếp", variable=self.v_per_folder,
                    value=False, bg=BG, fg=TEXT, selectcolor=CARD,
                    activebackground=BG, font=F_MAIN).pack(side=LEFT, padx=(6, 18))

        self.v_recursive = BooleanVar(value=False)
        Checkbutton(opt, text="Quét tất cả subfolder (đệ quy)",
                    variable=self.v_recursive,
                    bg=BG, fg=TEXT, selectcolor=CARD,
                    activebackground=BG, font=F_MAIN).pack(side=LEFT, padx=(0, 18))

        Label(opt, text="Khi có output:", bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT)
        self.v_action = StringVar(value="copy")
        Radiobutton(opt, text="Sao chép", variable=self.v_action, value="copy",
                    bg=BG, fg=TEXT, selectcolor=CARD,
                    activebackground=BG, font=F_MAIN).pack(side=LEFT, padx=(6, 0))
        Radiobutton(opt, text="Di chuyển", variable=self.v_action, value="move",
                    bg=BG, fg=TEXT, selectcolor=CARD,
                    activebackground=BG, font=F_MAIN).pack(side=LEFT, padx=(6, 18))

        Label(opt, text="Bắt đầu từ:", bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT)
        self.v_start = IntVar(value=1)
        Spinbox(opt, from_=0, to=999999, increment=1, textvariable=self.v_start,
                bg=CARD, fg=TEXT, insertbackground=TEXT, buttonbackground=ACCENT2,
                relief="flat", font=F_MAIN, width=7).pack(side=LEFT, padx=(4, 18))

        Label(opt, text="Số chữ số:", bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT)
        self.v_pad = IntVar(value=1)
        Spinbox(opt, from_=1, to=9, increment=1, textvariable=self.v_pad,
                bg=CARD, fg=TEXT, insertbackground=TEXT, buttonbackground=ACCENT2,
                relief="flat", font=F_MAIN, width=3).pack(side=LEFT, padx=(4, 4))
        Label(opt, text="(1→1.jpg  3→001.jpg)", bg=BG, fg=DIM,
              font=("Segoe UI", 9)).pack(side=LEFT, padx=(0, 18))

        Label(opt, text="Phần mở rộng:", bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT)
        self.v_ext = StringVar(value="keep")
        for lbl, val in [("Giữ nguyên", "keep"), (".jpg", ".jpg"), (".png", ".png")]:
            Radiobutton(opt, text=lbl, variable=self.v_ext, value=val,
                        bg=BG, fg=TEXT, selectcolor=CARD,
                        activebackground=BG, font=F_MAIN).pack(side=LEFT, padx=(4, 0))

        info = Frame(self, bg=CARD, padx=16, pady=6)
        info.pack(fill=X, padx=16, pady=(0, 6))
        self.lbl_summary = Label(info,
            text="Chọn folder rồi nhấn  🔍 Quét & Xem trước  để kiểm tra trước khi thực hiện.",
            bg=CARD, fg=DIM, font=("Segoe UI", 9), anchor=W)
        self.lbl_summary.pack(fill=X)

        tree_outer = Frame(self, bg=BG, padx=16)
        tree_outer.pack(fill=BOTH, expand=True)

        cols = ("folder", "old_name", "new_name")
        self.tree = ttk.Treeview(tree_outer, columns=cols, show="headings",
                                 style="Dark.Treeview", height=12)
        for col, txt, w in [("folder",   "Folder",   200),
                             ("old_name", "Tên cũ",   280),
                             ("new_name", "Tên mới",  180)]:
            self.tree.heading(col, text=txt)
            self.tree.column(col, width=w, anchor=W)

        sb_tree_v = Scrollbar(tree_outer, orient=VERTICAL,   command=self.tree.yview)
        sb_tree_h = Scrollbar(tree_outer, orient=HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=sb_tree_v.set,
                            xscrollcommand=sb_tree_h.set)
        self.tree.tag_configure("same",   foreground=DIM)
        self.tree.tag_configure("change", foreground=TEXT)
        self.tree.tag_configure("warn",   foreground="#f0c040")

        sb_tree_v.pack(side=RIGHT,  fill=Y)
        sb_tree_h.pack(side=BOTTOM, fill=X)
        self.tree.pack(fill=BOTH, expand=True)

        bot = Frame(self, bg=BG, padx=16, pady=8)
        bot.pack(fill=X)

        self.btn_run = Button(bot, text="✏  Thực hiện đổi tên",
                              command=self._run, state=DISABLED,
                              bg=ACCENT, fg="white", activebackground="#c04010",
                              activeforeground="white", font=F_BOLD,
                              relief="flat", padx=20, pady=8, cursor="hand2")
        self.btn_run.pack(side=LEFT)

        Button(bot, text="🧹  Xóa", command=self._clear,
               bg=CARD, fg=DIM, font=F_MAIN,
               relief="flat", padx=14, pady=8, cursor="hand2").pack(side=LEFT, padx=(10, 0))

        self.lbl_status = Label(bot, text="", bg=BG, fg=DIM, font=F_MAIN)
        self.lbl_status.pack(side=LEFT, padx=16)

        pb_f = Frame(bot, bg=BG)
        pb_f.pack(side=RIGHT)
        self.pb_lbl = Label(pb_f, text="", bg=BG, fg=DIM, font=F_MAIN)
        self.pb_lbl.pack(anchor=E)
        self.pb = ttk.Progressbar(pb_f, style="K.Horizontal.TProgressbar",
                                  maximum=100, length=280)
        self.pb.pack()

    def _browse(self):
        p = filedialog.askdirectory(title="Chọn folder nguồn",
                                    initialdir=_cfg_dir("rename.src"))
        if p: self.v_folder.set(p)

    def _browse_out(self):
        p = filedialog.askdirectory(title="Chọn folder output",
                                    initialdir=_cfg_dir("rename.out"))
        if p: self.v_out.set(p)

    def _open_out(self):
        p = self.v_out.get().strip()
        if p and Path(p).exists():
            os.startfile(p)
        else:
            messagebox.showwarning("Chưa có output",
                                   "Nhập hoặc chạy xong để mở thư mục output.")

    def _scan(self):
        folder = self.v_folder.get().strip()
        if not folder:
            messagebox.showwarning("Chưa chọn", "Vui lòng chọn folder nguồn."); return
        if not Path(folder).is_dir():
            messagebox.showerror("Không tồn tại",
                                 f"Folder không tồn tại:\n{folder}"); return

        try:
            pad   = max(1, int(self.v_pad.get()))
            start = int(self.v_start.get())
        except (ValueError, TypeError):
            messagebox.showwarning("Giá trị không hợp lệ",
                                   "Padding / Số bắt đầu phải là số nguyên.")
            return

        out_dir    = self.v_out.get().strip() or None
        ext_choice = self.v_ext.get()
        keep_ext   = ext_choice == "keep"
        forced_ext = ext_choice if not keep_ext else ".jpg"

        self._plan = build_rename_plan(
            folder,
            out_dir    = out_dir,
            per_folder = self.v_per_folder.get(),
            padding    = pad,
            start_num  = start,
            keep_ext   = keep_ext,
            forced_ext = forced_ext,
            recursive  = self.v_recursive.get(),
        )

        self.tree.delete(*self.tree.get_children())
        changes      = 0
        PREVIEW_LIMIT = 2000
        for i, (src, dst) in enumerate(self._plan):
            same = src.resolve() == dst.resolve()
            if not same:
                changes += 1
            tag = "same" if same else "change"
            if i < PREVIEW_LIMIT:
                dst_folder = dst.parent.name if out_dir else src.parent.name
                self.tree.insert("", END,
                                 values=(dst_folder, src.name, dst.name),
                                 tags=(tag,))

        total = len(self._plan)
        extra = total - PREVIEW_LIMIT
        if extra > 0:
            self.tree.insert("", END,
                             values=("…", f"(+{extra} file nữa)", ""),
                             tags=("warn",))

        lbl_count = sum(1 for src, dst in self._plan
                        if src.resolve() != dst.resolve()
                        and src.with_suffix(".txt").exists())
        action_label = (f"Sao chép → {out_dir}" if out_dir and self.v_action.get() == "copy"
                        else f"Di chuyển → {out_dir}" if out_dir
                        else "Đổi tên tại chỗ")
        lbl_info = f"   |   Label: {lbl_count:,} file" if lbl_count else ""
        self.lbl_summary.config(
            text=f"Tổng: {total:,} file   |   Thay đổi: {changes:,}{lbl_info}"
                 f"   |   {action_label}")
        self.btn_run.config(state=NORMAL if changes else DISABLED)
        self.lbl_status.config(text="")

    def _run(self):
        if not self._plan:
            return
        out_dir = self.v_out.get().strip() or None
        action  = self.v_action.get() if out_dir else "rename"

        confirm_msg = (
            f"{'Sao chép' if action=='copy' else 'Di chuyển' if action=='move' else 'Đổi tên'} "
            f"{len(self._plan):,} file?\n"
            + (f"Output: {out_dir}\n" if out_dir else "")
            + ("Hành động này không thể hoàn tác trực tiếp." if action != "copy" else "")
        )
        if not messagebox.askyesno("Xác nhận", confirm_msg):
            return

        self.btn_run.config(state=DISABLED, text="⏳  Đang xử lý…")
        self.pb["value"] = 0

        def worker():
            try:
                execute_rename_plan(
                    self._plan,
                    action   = action,
                    log      = lambda m: self.root.after(
                        0, lambda msg=m: self.lbl_status.config(text=msg)),
                    progress = lambda d, t: self.root.after(0, self._set_pb, d, t),
                )
                self.root.after(0, self._done, True)
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Lỗi", str(e)))
                self.root.after(0, self._done, False)

        threading.Thread(target=worker, daemon=True).start()

    def _set_pb(self, done, total):
        pct = int(done / total * 100)
        self.pb["value"] = pct
        self.pb_lbl.config(text=f"{done:,} / {total:,}  ({pct}%)")

    def _done(self, success):
        self.btn_run.config(state=NORMAL, text="✏  Thực hiện đổi tên")
        if success:
            self.lbl_status.config(text="✅  Hoàn thành!")
            self._plan = []
            self.btn_run.config(state=DISABLED)

    def _clear(self):
        self.tree.delete(*self.tree.get_children())
        self._plan = []
        self.btn_run.config(state=DISABLED)
        self.lbl_summary.config(
            text="Chọn folder rồi nhấn  🔍 Quét & Xem trước  để kiểm tra trước khi thực hiện.")
        self.lbl_status.config(text="")
        self.pb["value"] = 0
        self.pb_lbl.config(text="")
