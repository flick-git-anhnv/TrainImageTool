import os
import re
import threading
from datetime import datetime
from pathlib import Path
from tkinter import *
from tkinter import filedialog, messagebox, ttk

from .constants import BG, CARD, ACCENT, ACCENT2, TEXT, DIM, F_MAIN, F_BOLD
from .settings import _bind_cfg, _cfg_dir, _bind_history, _push_history, _get_history
from .core_rename import build_rename_plan, execute_rename_plan
from .ui_helpers import _pb_row


def _apply_template(template, stem, ext, seq, mtime):
    result = template
    fmt_seq = re.search(r'\{seq:([^}]+)\}', result)
    if fmt_seq:
        try:
            result = result[:fmt_seq.start()] + format(seq, fmt_seq.group(1)) + result[fmt_seq.end():]
        except (ValueError, TypeError):
            result = result[:fmt_seq.start()] + str(seq) + result[fmt_seq.end():]
    else:
        result = result.replace("{seq}", str(seq))
    result = result.replace("{stem}", stem)
    result = result.replace("{ext}", ext.lstrip("."))
    try:
        date_str = datetime.fromtimestamp(mtime).strftime("%Y%m%d")
    except (OSError, OverflowError, ValueError):
        date_str = "00000000"
    result = result.replace("{date}", date_str)
    return result


class RenameTab(Frame):
    def __init__(self, master, root):
        super().__init__(master, bg=BG)
        self.root  = root
        self._plan = []
        self._undo_map = {}
        self._stop_flag = False
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
        self._folder_combo = ttk.Combobox(row1, textvariable=self.v_folder,
                                           style="Dark.TCombobox", font=F_MAIN, width=52)
        self._folder_combo.pack(side=LEFT, padx=10)
        _bind_history("h.rename.src", self._folder_combo)
        Button(row1, text="📂", command=self._open_src,
               bg=CARD, fg=TEXT, activebackground=ACCENT2,
               activeforeground="white", font=F_MAIN,
               relief="flat", padx=6, pady=5, cursor="hand2").pack(side=LEFT, padx=(0, 6))
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
        self._out_combo = ttk.Combobox(row2, textvariable=self.v_out,
                                        style="Dark.TCombobox", font=F_MAIN, width=52)
        self._out_combo.pack(side=LEFT, padx=10)
        _bind_history("h.rename.out", self._out_combo)
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

        extra_row = Frame(self, bg=BG, padx=16, pady=4)
        extra_row.pack(fill=X)

        regex_frame = Frame(extra_row, bg=CARD, padx=12, pady=8)
        regex_frame.pack(side=LEFT, fill=Y, padx=(0, 8))
        Label(regex_frame, text="Regex Find/Replace", bg=CARD, fg=TEXT,
              font=F_BOLD).grid(row=0, column=0, columnspan=4, sticky=W, pady=(0, 4))
        Label(regex_frame, text="Tìm (regex):", bg=CARD, fg=DIM,
              font=F_MAIN).grid(row=1, column=0, sticky=W)
        self.v_regex_find = StringVar()
        self.v_regex_find.trace_add("write", self._on_regex_change)
        _rf_combo = ttk.Combobox(regex_frame, textvariable=self.v_regex_find,
                                  style="Dark.TCombobox", font=F_MAIN, width=22)
        _rf_combo.grid(row=1, column=1, padx=(6, 12), sticky=W)
        _bind_history("h.rename.regex_find", _rf_combo)
        Label(regex_frame, text="Thay bằng:", bg=CARD, fg=DIM,
              font=F_MAIN).grid(row=1, column=2, sticky=W)
        self.v_regex_replace = StringVar()
        self.v_regex_replace.trace_add("write", self._on_regex_change)
        _rr_combo = ttk.Combobox(regex_frame, textvariable=self.v_regex_replace,
                                  style="Dark.TCombobox", font=F_MAIN, width=22)
        _rr_combo.grid(row=1, column=3, padx=(6, 0), sticky=W)
        _bind_history("h.rename.regex_replace", _rr_combo)
        self.lbl_regex_err = Label(regex_frame, text="", bg=CARD,
                                   fg="#ff6060", font=("Segoe UI", 9))
        self.lbl_regex_err.grid(row=2, column=0, columnspan=4, sticky=W, pady=(2, 0))

        tpl_frame = Frame(extra_row, bg=CARD, padx=12, pady=8)
        tpl_frame.pack(side=LEFT, fill=Y)
        Label(tpl_frame, text="Template Rename", bg=CARD, fg=TEXT,
              font=F_BOLD).grid(row=0, column=0, columnspan=2, sticky=W, pady=(0, 4))
        Label(tpl_frame, text="Template:", bg=CARD, fg=DIM,
              font=F_MAIN).grid(row=1, column=0, sticky=W)
        self.v_template = StringVar()
        self.v_template.trace_add("write", self._on_template_change)
        _tpl_combo = ttk.Combobox(tpl_frame, textvariable=self.v_template,
                                   style="Dark.TCombobox", font=F_MAIN, width=32)
        _tpl_combo.grid(row=1, column=1, padx=(6, 0), sticky=W)
        _bind_history("h.rename.template", _tpl_combo)
        Label(tpl_frame, text="Tokens: {seq:04d}  {stem}  {ext}  {date}",
              bg=CARD, fg=DIM, font=("Segoe UI", 9)).grid(
              row=2, column=0, columnspan=2, sticky=W, pady=(2, 2))
        self.lbl_tpl_preview = Label(tpl_frame, text="", bg=CARD, fg=ACCENT2,
                                     font=("Segoe UI", 9), anchor=W, justify=LEFT)
        self.lbl_tpl_preview.grid(row=3, column=0, columnspan=2, sticky=W)

        info = Frame(self, bg=CARD, padx=16, pady=6)
        info.pack(fill=X, padx=16, pady=(0, 3))
        self.lbl_summary = Label(info,
            text="Chọn folder rồi nhấn  🔍 Quét & Xem trước  để kiểm tra trước khi thực hiện.",
            bg=CARD, fg=DIM, font=("Segoe UI", 9), anchor=W)
        self.lbl_summary.pack(fill=X)
        self.lbl_overwrite = Label(info, text="", bg=CARD, fg="#ff6060",
                                   font=("Segoe UI", 9), anchor=W)
        self.lbl_overwrite.pack(fill=X)

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
        self.tree.tag_configure("same",     foreground=DIM)
        self.tree.tag_configure("change",   foreground=TEXT)
        self.tree.tag_configure("warn",     foreground="#f0c040")
        self.tree.tag_configure("overwrite",foreground="#ff4444")

        sb_tree_v.pack(side=RIGHT,  fill=Y)
        sb_tree_h.pack(side=BOTTOM, fill=X)
        self.tree.pack(fill=BOTH, expand=True)

        bot = Frame(self, bg=BG, padx=16, pady=8)
        bot.pack(fill=X)

        self.btn_run = Button(bot, text="✏  Thực hiện đổi tên  [Ctrl+S]",
                              command=self._run, state=DISABLED,
                              bg=ACCENT, fg="white", activebackground="#c04010",
                              activeforeground="white", font=F_BOLD,
                              relief="flat", padx=20, pady=8, cursor="hand2")
        self.btn_run.pack(side=LEFT)

        self.btn_stop = Button(bot, text="⏹  Dừng  [Esc]",
                               command=self._stop, state=DISABLED,
                               bg="#c0392b", fg="white",
                               activebackground="#e74c3c",
                               activeforeground="white", font=F_BOLD,
                               relief="flat", padx=14, pady=8, cursor="hand2")
        self.btn_stop.pack(side=LEFT, padx=(8, 0))

        self.btn_undo = Button(bot, text="↩  Hoàn tác  [Ctrl+Z]", command=self._undo,
                               state=DISABLED,
                               bg=ACCENT2, fg="white",
                               activebackground="#6a5fac",
                               activeforeground="white", font=F_BOLD,
                               relief="flat", padx=14, pady=8, cursor="hand2")
        self.btn_undo.pack(side=LEFT, padx=(10, 0))

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
        if p:
            self.v_folder.set(p)
            _push_history("h.rename.src", p)
            self._folder_combo["values"] = _get_history("h.rename.src")

    def _browse_out(self):
        p = filedialog.askdirectory(title="Chọn folder output",
                                    initialdir=_cfg_dir("rename.out"))
        if p:
            self.v_out.set(p)
            _push_history("h.rename.out", p)
            self._out_combo["values"] = _get_history("h.rename.out")

    def _open_src(self):
        p = self.v_folder.get().strip()
        if p and os.path.isdir(p):
            os.startfile(p)

    def _open_out(self):
        p = self.v_out.get().strip()
        if p and Path(p).exists():
            os.startfile(p)
        else:
            messagebox.showwarning("Chưa có output",
                                   "Nhập hoặc chạy xong để mở thư mục output.")

    def _on_regex_change(self, *_):
        pattern = self.v_regex_find.get()
        if not pattern:
            self.lbl_regex_err.config(text="")
            return
        try:
            re.compile(pattern)
            self.lbl_regex_err.config(text="")
        except re.error as e:
            self.lbl_regex_err.config(text=f"Regex lỗi: {e}")

    def _on_template_change(self, *_):
        template = self.v_template.get().strip()
        if not template or not self._plan:
            self.lbl_tpl_preview.config(text="")
            return
        lines = []
        for i, (src, _dst) in enumerate(self._plan[:5]):
            stem = src.stem
            ext  = src.suffix
            try:
                mtime = src.stat().st_mtime
            except OSError:
                mtime = 0
            try:
                new_stem = _apply_template(template, stem, ext, i + 1, mtime)
                lines.append(f"{src.name}  →  {new_stem}{ext}")
            except Exception as exc:
                lines.append(f"Lỗi: {exc}")
                break
        self.lbl_tpl_preview.config(text="\n".join(lines))

    def _get_regex_override(self):
        pattern = self.v_regex_find.get().strip()
        if not pattern:
            return None
        try:
            compiled = re.compile(pattern)
        except re.error:
            return None
        replacement = self.v_regex_replace.get()
        return compiled, replacement

    def _get_template_override(self):
        tpl = self.v_template.get().strip()
        return tpl if tpl else None

    def _scan(self):
        folder = self.v_folder.get().strip()
        if not folder:
            messagebox.showwarning("Chưa chọn", "Vui lòng chọn folder nguồn."); return
        if not Path(folder).is_dir():
            messagebox.showerror("Không tồn tại",
                                 f"Folder không tồn tại:\n{folder}"); return

        regex_err = self.lbl_regex_err.cget("text")
        if regex_err:
            messagebox.showwarning("Regex lỗi",
                                   "Vui lòng sửa lỗi regex trước khi quét.")
            return

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

        regex_override = self._get_regex_override()
        tpl_override   = self._get_template_override()

        if regex_override or tpl_override:
            compiled_re, repl = regex_override if regex_override else (None, None)
            new_plan = []
            seq = start
            for src, dst in self._plan:
                stem = src.stem
                ext  = src.suffix
                try:
                    mtime = src.stat().st_mtime
                except OSError:
                    mtime = 0
                if compiled_re is not None:
                    stem = compiled_re.sub(repl, stem)
                if tpl_override:
                    stem = _apply_template(tpl_override, stem, ext, seq, mtime)
                new_dst = dst.parent / (stem + (dst.suffix if keep_ext else forced_ext))
                new_plan.append((src, new_dst))
                seq += 1
            self._plan = new_plan

        out_path = Path(out_dir) if out_dir else None

        self.tree.delete(*self.tree.get_children())
        changes       = 0
        overwrite_cnt = 0
        PREVIEW_LIMIT = 2000
        for i, (src, dst) in enumerate(self._plan):
            same = src.resolve() == dst.resolve()
            if not same:
                changes += 1
            will_overwrite = (
                not same
                and out_path is not None
                and (out_path / dst.name).exists()
                and (out_path / dst.name).resolve() != src.resolve()
            ) or (
                not same
                and out_path is None
                and dst.exists()
                and dst.resolve() != src.resolve()
            )
            if will_overwrite:
                overwrite_cnt += 1
            if i < PREVIEW_LIMIT:
                dst_folder = dst.parent.name if out_dir else src.parent.name
                if will_overwrite:
                    tag = "overwrite"
                elif same:
                    tag = "same"
                else:
                    tag = "change"
                self.tree.insert("", END,
                                 values=(dst_folder, src.name, dst.name),
                                 tags=(tag,))

        total = len(self._plan)
        extra = total - PREVIEW_LIMIT
        if extra > 0:
            self.tree.insert("", END,
                             values=("…", f"(+{extra} file nữa)", ""),
                             tags=("warn",))

        if overwrite_cnt > 0:
            self.lbl_overwrite.config(
                text=f"⚠  {overwrite_cnt} file sẽ bị ghi đè!")
        else:
            self.lbl_overwrite.config(text="")

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
        self._on_template_change()

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

        pending_plan = list(self._plan)
        self._stop_flag = False
        self.btn_run.config(state=DISABLED, text="⏳  Đang xử lý…")
        self.btn_stop.config(state=NORMAL)
        self.btn_undo.config(state=DISABLED)
        self.pb["value"] = 0

        def worker():
            try:
                execute_rename_plan(
                    pending_plan,
                    action      = action,
                    log         = lambda m: self.root.after(
                        0, lambda msg=m: self.lbl_status.config(text=msg)),
                    progress    = lambda d, t: self.root.after(0, self._set_pb, d, t),
                    stop_check  = lambda: self._stop_flag,
                )
                self.root.after(0, self._done, True, pending_plan, action)
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Lỗi", str(e)))
                self.root.after(0, self._done, False, [], action)

        threading.Thread(target=worker, daemon=True).start()

    def _set_pb(self, done, total):
        pct = int(done / total * 100)
        self.pb["value"] = pct
        self.pb_lbl.config(text=f"{done:,} / {total:,}  ({pct}%)")

    def _done(self, success, completed_plan, action):
        self.btn_run.config(state=NORMAL, text="✏  Thực hiện đổi tên  [Ctrl+S]")
        self.btn_stop.config(state=DISABLED)
        if success:
            self.lbl_status.config(text="✅  Hoàn thành!")
            self._plan = []
            self.btn_run.config(state=DISABLED)
            if action in ("rename", "move") and completed_plan:
                self._undo_map = {}
                for src, dst in completed_plan:
                    if src.resolve() != dst.resolve():
                        self._undo_map[str(dst.resolve())] = str(src.resolve())
                if self._undo_map:
                    self.btn_undo.config(state=NORMAL)
                else:
                    self.btn_undo.config(state=DISABLED)
            else:
                self.btn_undo.config(state=DISABLED)

    def _undo(self):
        if not self._undo_map:
            self.btn_undo.config(state=DISABLED)
            return
        undo_items = list(self._undo_map.items())
        if not messagebox.askyesno(
            "Hoàn tác",
            f"Đổi tên ngược lại {len(undo_items):,} file về tên cũ?"
        ):
            return

        errors = []
        done_count = 0
        for new_path_str, old_path_str in undo_items:
            new_p = Path(new_path_str)
            old_p = Path(old_path_str)
            try:
                if new_p.exists():
                    new_p.rename(old_p)
                    done_count += 1
            except OSError as e:
                errors.append(f"{new_p.name}: {e}")

        self._undo_map = {}
        self.btn_undo.config(state=DISABLED)

        if errors:
            messagebox.showerror(
                "Hoàn tác – lỗi",
                f"Hoàn tác {done_count} file.\nLỗi ({len(errors)}):\n" +
                "\n".join(errors[:10])
            )
        else:
            self.lbl_status.config(text=f"↩  Đã hoàn tác {done_count} file.")

    def _stop(self):
        """Escape — dừng tiến trình đổi tên đang chạy."""
        self._stop_flag = True
        self.btn_stop.config(state=DISABLED)
        self.lbl_status.config(text="⚠  Đang dừng…")

    def _save(self):
        """Ctrl+S — thực hiện đổi tên (nếu đã có plan), hoặc scan trước."""
        if self._plan:
            self._run()
        else:
            self._scan()

    def _clear(self):
        self.tree.delete(*self.tree.get_children())
        self._plan = []
        self.btn_run.config(state=DISABLED)
        self.lbl_summary.config(
            text="Chọn folder rồi nhấn  🔍 Quét & Xem trước  để kiểm tra trước khi thực hiện.")
        self.lbl_overwrite.config(text="")
        self.lbl_status.config(text="")
        self.pb["value"] = 0
        self.pb_lbl.config(text="")
        self.lbl_tpl_preview.config(text="")
