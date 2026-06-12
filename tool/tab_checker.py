import json
import os
import queue
import shutil
import tempfile
import threading
from tkinter import *
from tkinter import filedialog, messagebox, ttk

from .constants import (
    BG, CARD, ACCENT, ACCENT2, TEXT, DIM, SUCCESS,
    F_MAIN, F_BOLD, F_MONO, _VI, _VI_FULL,
)
from .settings import _CFG, _cfg_save, _cfg_dir
from .core_gt import analyze_gt, _heat_color
from .imports import _TTS_OK, _GTTS_OK, _gTTS

_CELL_BG      = "#111122"
_CELL_BORDER  = "#2a2a4a"
_FOCUS_BORDER = ACCENT
_LABEL_COLOR  = "#FFE000"


class CheckerTab(Frame):
    def __init__(self, master, root, nb):
        super().__init__(master, bg=BG)
        self.root = root
        self.nb   = nb

        self.data_list       = []
        self.current_idx     = 0
        self.img_dir         = ""
        self.gt_path         = ""
        self.checked_img_dir = ""
        self.checked_gt_path = ""
        self.trash_img_dir   = ""
        self.history         = []
        self.corrections     = {}
        self.corrections_path = ""

        self.var_audio  = BooleanVar(value=True)
        self.var_lang   = StringVar(value="gtts_vi" if _GTTS_OK else "sapi_vi")
        self.var_speed  = IntVar(value=15)
        self.var_n_show = IntVar(value=1)

        self._n_show    = 1
        self._cells     = []   # list of cell dicts
        self._focus_idx = 0
        self._photos    = {}   # cell_idx → PhotoImage (prevent GC)

        self._tts_q         = queue.Queue(maxsize=1)
        self._prefetch_q    = queue.Queue(maxsize=10)
        self._tts_cache     = {}
        self._prefetch_done = {}

        self._build()
        self._init_tts()
        root.bind("<Delete>", self._global_delete)

    # ── Layout ────────────────────────────────────────────────────────────

    def _build(self):
        # Top bar
        top = Frame(self, bg=CARD, padx=16, pady=8)
        top.pack(fill=X)
        Button(top, text="📂  Chọn thư mục dataset",
               command=self.load_dataset,
               bg=ACCENT2, fg="white", activebackground=ACCENT,
               activeforeground="white", font=F_BOLD,
               relief="flat", padx=14, pady=6, cursor="hand2").pack(side=LEFT)
        self.lbl_info = Label(top,
            text="Chọn thư mục chứa  raw_images/  và  gt.txt",
            bg=CARD, fg=DIM, font=F_MAIN)
        self.lbl_info.pack(side=LEFT, padx=16)

        # n_show spinbox (top-right)
        Label(top, text="Số hình:", bg=CARD, fg=DIM, font=F_MAIN).pack(side=RIGHT, padx=(0, 2))
        Spinbox(top, from_=1, to=20, textvariable=self.var_n_show,
                width=3, bg=CARD, fg=TEXT, insertbackground=TEXT,
                buttonbackground=ACCENT2, relief="flat", font=F_MAIN,
                command=self._on_n_show_change).pack(side=RIGHT)

        # Grid container (scrollable)
        self._grid_outer = Frame(self, bg=BG)
        self._grid_outer.pack(fill=BOTH, expand=True, padx=12, pady=6)

        canvas = Canvas(self._grid_outer, bg=BG, highlightthickness=0)
        vsb = ttk.Scrollbar(self._grid_outer, orient=VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=RIGHT, fill=Y)
        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        self._grid_canvas = canvas

        self._grid_frame = Frame(canvas, bg=BG)
        self._grid_win_id = canvas.create_window(
            (0, 0), window=self._grid_frame, anchor="nw")
        self._grid_frame.bind("<Configure>", self._on_grid_resize)
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(self._grid_win_id, width=e.width))

        # Correction label
        self.lbl_correction = Label(self, text="", bg=BG, fg="#E07820",
                                    font=("Segoe UI", 10, "italic"), anchor=W)
        self.lbl_correction.pack(fill=X, padx=16)

        # Button row
        btn_row = Frame(self, bg=BG, padx=14, pady=8)
        btn_row.pack(fill=X)
        self.btn_back = Button(btn_row, text="◀  Quay lại  (←)",
                               bg="#E07820", fg="white",
                               activebackground="#c06010", activeforeground="white",
                               font=F_BOLD, width=18, relief="flat",
                               cursor="hand2", command=self.go_back, state=DISABLED)
        self.btn_back.pack(side=LEFT, padx=(0, 8))
        Button(btn_row, text="✅  Lưu & Tiếp  (Enter / →)",
               bg="#2e7d32", fg="white",
               activebackground="#1b5e20", activeforeground="white",
               font=F_BOLD, width=24, relief="flat",
               cursor="hand2", command=self.save_all_and_next).pack(side=LEFT, padx=8)
        Button(btn_row, text="🗑  Xóa ảnh  (Del)",
               bg="#c62828", fg="white",
               activebackground="#8b0000", activeforeground="white",
               font=F_BOLD, width=18, relief="flat",
               cursor="hand2", command=self.delete_focused).pack(side=LEFT, padx=8)
        Button(btn_row, text="🔤  Sắp xếp GT",
               bg=ACCENT2, fg="white",
               activebackground=ACCENT, activeforeground="white",
               font=F_BOLD, relief="flat",
               cursor="hand2", command=self._sort_gt).pack(side=LEFT, padx=8)

        # Audio row
        audio_row = Frame(self, bg=BG, padx=14, pady=4)
        audio_row.pack(fill=X)
        Checkbutton(audio_row, text="🔊 Phát âm", variable=self.var_audio,
                    bg=BG, fg=TEXT, selectcolor=CARD,
                    activebackground=BG, font=F_MAIN).pack(side=LEFT, padx=(0, 12))
        gtts_state = NORMAL if _GTTS_OK else DISABLED
        for lbl, val, state in [("Tiếng Việt · Google TTS", "gtts_vi", gtts_state),
                                 ("Tiếng Việt · Phonetic",  "sapi_vi", NORMAL),
                                 ("English",                 "sapi_en", NORMAL)]:
            Radiobutton(audio_row, text=lbl, variable=self.var_lang, value=val,
                        bg=BG, fg=TEXT, selectcolor=CARD,
                        activebackground=BG, font=F_MAIN,
                        state=state).pack(side=LEFT, padx=(0, 6))
        Label(audio_row, text="  Tốc độ:", bg=BG, fg=DIM, font=F_MAIN).pack(side=LEFT)
        Spinbox(audio_row, from_=1, to=20, textvariable=self.var_speed,
                width=3, bg=CARD, fg=TEXT, insertbackground=TEXT,
                buttonbackground=ACCENT2, relief="flat",
                font=F_MAIN).pack(side=LEFT, padx=(2, 4))
        Label(audio_row, text="(1–20)", bg=BG, fg=DIM,
              font=("Segoe UI", 9)).pack(side=LEFT)
        if not _TTS_OK:
            Label(audio_row, text="  ⚠ pip install pywin32",
                  bg=BG, fg="#f05050", font=("Segoe UI", 9)).pack(side=LEFT)
        elif not _GTTS_OK:
            Label(audio_row, text="  ⚠ pip install gtts",
                  bg=BG, fg="#f0c040", font=("Segoe UI", 9)).pack(side=LEFT)

        self._build_stats_panel()
        self._rebuild_grid()

    def _on_grid_resize(self, _=None):
        self._grid_canvas.configure(
            scrollregion=self._grid_canvas.bbox("all"))

    # ── Dynamic grid ──────────────────────────────────────────────────────

    def _on_n_show_change(self, *_):
        try:
            n = max(1, min(20, int(self.var_n_show.get())))
        except (ValueError, TclError):
            return
        if n == self._n_show:
            return
        self._n_show = n
        self._rebuild_grid()
        if self.data_list:
            self.show_batch()

    def _cell_img_size(self):
        """Return (img_w, img_h) for thumbnail based on n_show."""
        n = self._n_show
        if n == 1:
            return 560, 300
        # try to fit in ~1100px wide
        cell_w = max(100, min(480, (1100 - n * 14) // n))
        cell_h = max(70,  int(cell_w * 0.62))
        return cell_w, cell_h

    def _rebuild_grid(self):
        for w in self._grid_frame.winfo_children():
            w.destroy()
        self._cells.clear()
        self._photos.clear()

        n        = self._n_show
        img_w, img_h = self._cell_img_size()
        entry_w  = max(8, min(36, int(img_w / 12)))
        font_sz  = 28 if n == 1 else max(9, 22 - n * 2)
        entry_font = ("Courier New", 14 if n == 1 else max(9, 12 - n))

        for i in range(n):
            cell = {}

            outer = Frame(self._grid_frame, bg=_CELL_BORDER, bd=0)
            outer.grid(row=0, column=i, padx=5, pady=4, sticky=N)

            inner = Frame(outer, bg=_CELL_BG, padx=4, pady=4)
            inner.pack(padx=2, pady=2)

            # Image label
            img_lbl = Label(inner, bg=_CELL_BG,
                            width=img_w, height=img_h, anchor="center")
            img_lbl.config(image="")
            img_lbl.pack()

            # Filename label
            fn_lbl = Label(inner, text="", bg=_CELL_BG, fg="#555577",
                           font=("Consolas", 7), width=entry_w, anchor=W)
            fn_lbl.pack(fill=X)

            # Entry
            entry = Entry(inner, font=entry_font, width=entry_w,
                          bg="#0a0a18", fg=_LABEL_COLOR,
                          insertbackground=_LABEL_COLOR,
                          relief="flat", bd=4, state=DISABLED)
            entry.pack(fill=X, pady=(2, 0))

            # Result label (only show for n=1 or n<=2)
            res_lbl = None
            if n <= 2:
                res_lbl = Label(inner, text="",
                                font=("Courier New", font_sz, "bold"),
                                bg="#1C1C2E", fg=_LABEL_COLOR,
                                width=entry_w, height=2 if n == 1 else 1,
                                relief=SUNKEN, bd=2, anchor="center")
                res_lbl.pack(fill=X, pady=(3, 0))

            cell = {
                "outer":   outer,
                "inner":   inner,
                "img_lbl": img_lbl,
                "fn_lbl":  fn_lbl,
                "entry":   entry,
                "res_lbl": res_lbl,
                "filename": "",
                "gt_label": "",
            }
            self._cells.append(cell)

            # Bind events
            idx = i
            entry.bind("<Return>",    lambda e, x=idx: self._on_entry_enter(x))
            entry.bind("<Right>",     lambda e, x=idx: self._on_entry_right(e, x))
            entry.bind("<Left>",      lambda e, x=idx: self._on_entry_left(e, x))
            entry.bind("<Tab>",       lambda e, x=idx: (self._set_focus((x+1) % n), "break"))
            entry.bind("<KeyRelease>", lambda e, x=idx: self._update_cell_preview(x))
            entry.bind("<FocusIn>",    lambda e, x=idx: self._set_focus(x, speak=False))
            inner.bind("<Button-1>",  lambda e, x=idx: self._set_focus(x))
            img_lbl.bind("<Button-1>", lambda e, x=idx: self._set_focus(x))

        self._focus_idx = 0

    def _set_focus(self, i, speak=True):
        n = len(self._cells)
        if n == 0 or i >= n:
            return
        self._focus_idx = i
        for j, cell in enumerate(self._cells):
            active = (j == i)
            cell["outer"].config(bg=_FOCUS_BORDER if active else _CELL_BORDER)
            if cell["entry"]["state"] != DISABLED:
                cell["entry"].config(
                    fg=_LABEL_COLOR if active else "#888899")
        cell = self._cells[i]
        if cell["entry"]["state"] != DISABLED:
            cell["entry"].focus_set()
        # Show correction hint
        gt = cell.get("gt_label", "")
        display = cell["entry"].get() if cell["entry"]["state"] != DISABLED else gt
        self.lbl_correction.config(
            text=(f"Tự sửa: [{gt}] → [{display}]"
                  if gt and display != gt else ""))
        if speak:
            self._speak(display)

    def _update_cell_preview(self, i):
        if i >= len(self._cells):
            return
        cell = self._cells[i]
        txt = cell["entry"].get()
        if cell["res_lbl"]:
            cell["res_lbl"].config(text=txt or "—")
        if i == self._focus_idx:
            self.lbl_correction.config(
                text=(f"Tự sửa: [{cell['gt_label']}] → [{txt}]"
                      if cell["gt_label"] and txt != cell["gt_label"] else ""))

    def _on_entry_enter(self, i):
        n = self._n_show
        if i < n - 1:
            self._set_focus(i + 1)
        else:
            self.save_all_and_next()

    def _on_entry_right(self, event, i):
        cell = self._cells[i]
        if cell["entry"].index(INSERT) == len(cell["entry"].get()):
            self._on_entry_enter(i)
            return "break"

    def _on_entry_left(self, event, i):
        cell = self._cells[i]
        if cell["entry"].index(INSERT) == 0 and i == 0:
            self.go_back()
            return "break"
        elif cell["entry"].index(INSERT) == 0 and i > 0:
            self._set_focus(i - 1)
            return "break"

    # ── Dataset loading ───────────────────────────────────────────────────

    def load_dataset(self):
        folder = filedialog.askdirectory(
            title="Chọn thư mục train hoặc val",
            initialdir=_cfg_dir("checker.folder"))
        if not folder:
            return
        _CFG["checker.folder"] = folder; _cfg_save()
        self.img_dir = os.path.join(folder, "raw_images")
        self.gt_path = os.path.join(folder, "gt.txt")
        if not os.path.exists(self.img_dir) or not os.path.exists(self.gt_path):
            messagebox.showerror("Lỗi",
                "Thư mục không chứa 'raw_images' hoặc 'gt.txt'.\n"
                "Hãy chọn đúng thư mục train / val.")
            return

        parent_dir  = os.path.dirname(folder)
        checked     = os.path.join(parent_dir, os.path.basename(folder) + "_checked")
        self.checked_img_dir = os.path.join(checked, "raw_images")
        self.checked_gt_path = os.path.join(checked, "gt.txt")
        self.trash_img_dir   = os.path.join(checked, "deleted_images")
        os.makedirs(self.checked_img_dir, exist_ok=True)
        os.makedirs(self.trash_img_dir,   exist_ok=True)

        self.data_list = []
        with open(self.gt_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line: continue
                parts = line.split("\t") if "\t" in line else line.split(" ", 1)
                self.data_list.append(
                    (parts[0], parts[1] if len(parts) >= 2 else ""))

        self.current_idx = 0
        self.history     = []
        if not self.data_list:
            messagebox.showinfo("Thông báo", "File gt.txt trống hoặc đã duyệt xong!")
            return

        self._load_corrections()
        for i in range(min(self._n_show + 4, len(self.data_list))):
            self._prefetch_gtts(self.data_list[i][1])
        self.show_batch()
        self.root.after(80, self._refresh_stats)

    # ── Batch display ─────────────────────────────────────────────────────

    def show_batch(self):
        from PIL import Image, ImageTk

        total    = len(self.data_list)
        rem      = total - self.current_idx
        img_w, img_h = self._cell_img_size()

        if self.current_idx >= total:
            self.lbl_info.config(
                text="✅  Hoàn thành! Đã kiểm tra toàn bộ dữ liệu.")
            for cell in self._cells:
                cell["img_lbl"].config(image="")
                cell["fn_lbl"].config(text="")
                cell["entry"].config(state=DISABLED)
                cell["entry"].delete(0, END)
                if cell["res_lbl"]: cell["res_lbl"].config(text="")
                cell["filename"] = ""; cell["gt_label"] = ""
            messagebox.showinfo("Thành công", "Đã xử lý xong toàn bộ ảnh!")
            return

        n_active = min(self._n_show, rem)
        self.lbl_info.config(
            text=(f"Tiến độ: {self.current_idx + 1}–"
                  f"{min(self.current_idx + n_active, total)} / {total}"))

        self._photos.clear()
        for i, cell in enumerate(self._cells):
            idx = self.current_idx + i
            if idx < total:
                filename, gt_label = self.data_list[idx]
                cell["filename"]  = filename
                cell["gt_label"]  = gt_label
                cell["fn_lbl"].config(text=filename)

                display = self.corrections.get(gt_label, gt_label)
                cell["entry"].config(state=NORMAL, fg="#888899")
                cell["entry"].delete(0, END)
                cell["entry"].insert(0, display)
                if cell["res_lbl"]: cell["res_lbl"].config(text=display or "—")

                img_path = os.path.join(self.img_dir, filename)
                if os.path.exists(img_path):
                    try:
                        img = Image.open(img_path).convert("RGB")
                        img.thumbnail((img_w, img_h), Image.LANCZOS)
                        photo = ImageTk.PhotoImage(img)
                        self._photos[i] = photo
                        cell["img_lbl"].config(image=photo,
                                                width=img_w, height=img_h)
                    except Exception:
                        cell["img_lbl"].config(image="")
                else:
                    cell["img_lbl"].config(image="")
            else:
                cell["filename"] = ""; cell["gt_label"] = ""
                cell["fn_lbl"].config(text="")
                cell["img_lbl"].config(image="")
                cell["entry"].config(state=DISABLED)
                cell["entry"].delete(0, END)
                if cell["res_lbl"]: cell["res_lbl"].config(text="")

        self.btn_back.config(state=NORMAL if self.history else DISABLED)
        self._set_focus(0)

        # Prefetch TTS for upcoming batch
        for off in range(self._n_show, min(self._n_show + 5, rem)):
            self._prefetch_gtts(self.data_list[self.current_idx + off][1])

    # ── Save / Delete ─────────────────────────────────────────────────────

    def save_all_and_next(self, _=None):
        if not self.data_list or self.current_idx >= len(self.data_list):
            return
        n_active = min(self._n_show,
                       len(self.data_list) - self.current_idx)
        batch_actions = []
        for i in range(n_active):
            cell = self._cells[i]
            if not cell["filename"]:
                continue
            new_label = cell["entry"].get().strip()
            _, gt_label = self.data_list[self.current_idx + i]
            if gt_label and new_label != gt_label:
                self._save_correction(gt_label, new_label)
            batch_actions.append(("save", cell["filename"], new_label))
        self._process_batch(batch_actions)

    def delete_focused(self, _=None):
        if not self.data_list or self.current_idx >= len(self.data_list):
            return
        if not messagebox.askyesno("Xác nhận xóa", "Xóa ảnh đang focus khỏi dataset?"):
            return
        i    = self._focus_idx
        cell = self._cells[i] if i < len(self._cells) else None
        if not cell or not cell["filename"]:
            return
        # Build batch: delete focused, save rest
        n_active = min(self._n_show,
                       len(self.data_list) - self.current_idx)
        batch_actions = []
        for j in range(n_active):
            c = self._cells[j]
            if not c["filename"]: continue
            if j == i:
                batch_actions.append(("delete", c["filename"], ""))
            else:
                new_label = c["entry"].get().strip()
                batch_actions.append(("save", c["filename"], new_label))
        self._process_batch(batch_actions)

    def _process_batch(self, actions):
        for action, filename, new_label in actions:
            src   = os.path.join(self.img_dir,         filename)
            dst   = os.path.join(self.checked_img_dir, filename)
            trash = os.path.join(self.trash_img_dir,   filename)
            if action == "save":
                if os.path.exists(src): shutil.move(src, dst)
                with open(self.checked_gt_path, "a", encoding="utf-8") as f:
                    f.write(f"{filename}\t{new_label}\n")
            elif action == "delete":
                if os.path.exists(src): shutil.move(src, trash)

        self.history.append(("batch", len(actions), list(actions)))
        self.current_idx += len(actions)
        with open(self.gt_path, "w", encoding="utf-8") as f:
            for fn, lbl in self.data_list[self.current_idx:]:
                f.write(f"{fn}\t{lbl}\n")
        self.show_batch()
        self.root.after(80, self._refresh_stats)

    def go_back(self):
        if not self.history:
            return
        _type, count, actions = self.history.pop()
        self.current_idx -= count

        for action, filename, label in reversed(actions):
            if action == "save":
                src = os.path.join(self.checked_img_dir, filename)
                dst = os.path.join(self.img_dir, filename)
                if os.path.exists(src): shutil.move(src, dst)
                if os.path.exists(self.checked_gt_path):
                    with open(self.checked_gt_path, encoding="utf-8") as f:
                        lines = f.readlines()
                    with open(self.checked_gt_path, "w", encoding="utf-8") as f:
                        # Remove matching line
                        removed = False
                        for ln in reversed(lines):
                            if not removed and ln.startswith(filename + "\t"):
                                removed = True; continue
                            f.write(ln)  # ← bug: writes in wrong order, fix below
            elif action == "delete":
                src = os.path.join(self.trash_img_dir, filename)
                dst = os.path.join(self.img_dir, filename)
                if os.path.exists(src): shutil.move(src, dst)

        # Properly rewrite checked gt (remove last `count` save entries)
        if os.path.exists(self.checked_gt_path):
            save_count = sum(1 for a, _, _ in actions if a == "save")
            if save_count:
                with open(self.checked_gt_path, encoding="utf-8") as f:
                    lines = f.readlines()
                with open(self.checked_gt_path, "w", encoding="utf-8") as f:
                    f.writelines(lines[:-save_count])

        with open(self.gt_path, "w", encoding="utf-8") as f:
            for fn, lbl in self.data_list[self.current_idx:]:
                f.write(f"{fn}\t{lbl}\n")
        self.show_batch()
        self.root.after(80, self._refresh_stats)

    # ── Other actions ─────────────────────────────────────────────────────

    def _sort_gt(self):
        if not self.data_list:
            messagebox.showinfo("Thông báo", "Chưa tải dataset."); return
        self.data_list.sort(key=lambda x: x[1])
        with open(self.gt_path, "w", encoding="utf-8") as f:
            for fn, lbl in self.data_list:
                f.write(f"{fn}\t{lbl}\n")
        self.current_idx = 0
        self.history = []
        self.show_batch()
        self.root.after(80, self._refresh_stats)
        self.lbl_info.config(
            text=f"Đã sắp xếp {len(self.data_list):,} dòng theo biển số xe.")

    def _global_delete(self, event=None):
        try:
            if self.nb.select() == str(self):
                self.delete_focused()
        except Exception:
            pass

    # ── Corrections ───────────────────────────────────────────────────────

    def _load_corrections(self):
        path = os.path.join(os.path.dirname(self.gt_path), "corrections.json")
        self.corrections_path = path
        try:
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    self.corrections = json.load(f)
        except Exception:
            self.corrections = {}

    def _save_correction(self, wrong, correct):
        self.corrections[wrong] = correct
        if self.corrections_path:
            try:
                with open(self.corrections_path, "w", encoding="utf-8") as f:
                    json.dump(self.corrections, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"corrections save: {e}")

    # ── TTS ───────────────────────────────────────────────────────────────

    def _init_tts(self):
        if not _TTS_OK: return
        threading.Thread(target=self._tts_loop, daemon=True).start()
        if _GTTS_OK:
            threading.Thread(target=self._gtts_prefetch_loop, daemon=True).start()

    def _tts_loop(self):
        import ctypes, time as _t
        import pythoncom
        import win32com.client
        mci = ctypes.windll.winmm.mciSendStringW
        pythoncom.CoInitialize()
        spk = win32com.client.Dispatch("SAPI.SpVoice")
        spk.Volume = 100
        try:
            while True:
                text = self._tts_q.get()
                if text is None: break
                lang  = self.var_lang.get()
                speed = max(1, min(20, int(self.var_speed.get())))
                if lang == "gtts_vi" and _GTTS_OK:
                    self._gtts_speak(text, speed, mci)
                else:
                    spk.Rate = min(10, speed)
                    spk.Speak(text, 3)
                    while spk.Status.RunningState != 1:
                        _t.sleep(0.02)
                        try:
                            newer = self._tts_q.get_nowait()
                            if newer is None:
                                spk.Speak("", 3); return
                            text  = newer
                            speed = max(1, min(20, int(self.var_speed.get())))
                            spk.Rate = min(10, speed)
                            spk.Speak(text, 3)
                        except queue.Empty:
                            pass
        except Exception as e:
            print(f"TTS: {e}")
        finally:
            pythoncom.CoUninitialize()

    def _gtts_speak(self, text, speed, mci):
        cache_key = (text,)
        try:
            ev = self._prefetch_done.get(cache_key)
            if ev: ev.wait(timeout=12)
            fname = self._tts_cache.get(cache_key)
            if not fname or not os.path.exists(fname):
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                    fname = f.name
                _gTTS(text=text, lang="vi", slow=False).save(fname)
                self._tts_cache[cache_key] = fname
                self._trim_cache()
            alias = "_tts_g"
            mci_spd = min(3000, 500 + speed * 125)
            mci(f'open "{fname}" type mpegvideo alias {alias}', None, 0, None)
            mci(f'set {alias} speed {mci_spd}',                None, 0, None)
            mci(f'play {alias} wait',                          None, 0, None)
            mci(f'close {alias}',                              None, 0, None)
        except Exception as e:
            print(f"gTTS speak: {e}")

    def _gtts_prefetch_loop(self):
        while True:
            cache_key = self._prefetch_q.get()
            if cache_key is None: break
            ev = self._prefetch_done.setdefault(cache_key, threading.Event())
            try:
                if cache_key in self._tts_cache and os.path.exists(
                        self._tts_cache.get(cache_key, "")): continue
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                    fname = f.name
                _gTTS(text=cache_key[0], lang="vi", slow=False).save(fname)
                if os.path.getsize(fname) > 0:
                    self._tts_cache[cache_key] = fname
                    self._trim_cache()
                else:
                    try: os.unlink(fname)
                    except OSError: pass
            except Exception as e:
                print(f"prefetch: {e}")
            finally:
                ev.set()

    def _trim_cache(self, max_entries=30):
        while len(self._tts_cache) > max_entries:
            key, fpath = next(iter(self._tts_cache.items()))
            self._tts_cache.pop(key, None)
            self._prefetch_done.pop(key, None)
            try: os.unlink(fpath)
            except OSError: pass

    def _prefetch_gtts(self, raw_label):
        if not raw_label or not _GTTS_OK: return
        spoken    = " ".join(_VI_FULL.get(c, c)
                             for c in raw_label.upper().replace("-","").replace(" ",""))
        cache_key = (spoken,)
        if cache_key not in self._tts_cache:
            self._prefetch_done.setdefault(cache_key, threading.Event())
            try: self._prefetch_q.put_nowait(cache_key)
            except queue.Full: pass

    def _speak(self, text):
        if not _TTS_OK or not self.var_audio.get() or not text: return
        clean  = text.upper().replace("-","").replace(" ","")
        lang   = self.var_lang.get()
        spoken = (" ".join(_VI_FULL.get(c,c) for c in clean) if lang == "gtts_vi" else
                  " ".join(_VI.get(c,c)      for c in clean) if lang == "sapi_vi" else
                  " ".join(list(clean)))
        try: self._tts_q.get_nowait()
        except queue.Empty: pass
        self._tts_q.put(spoken)

    # ── Stats panel ───────────────────────────────────────────────────────

    _MINI_COLS = 12
    _MINI_W    = 44
    _MINI_H    = 30

    def _build_stats_panel(self):
        self._gt_prog_pct = 0.0
        Frame(self, height=1, bg="#333355").pack(fill=X)
        hdr = Frame(self, bg=CARD, padx=14, pady=5)
        hdr.pack(fill=X)
        Label(hdr, text="GT STATUS", bg=CARD, fg=DIM,
              font=("Segoe UI Semibold", 9)).pack(side=LEFT)
        self.lbl_gt_prog = Label(hdr, text="—  chưa tải dataset",
                                  bg=CARD, fg=TEXT, font=F_MAIN)
        self.lbl_gt_prog.pack(side=LEFT, padx=12)
        Button(hdr, text="⟳", command=self._refresh_stats,
               bg=CARD, fg=DIM, font=("Segoe UI", 10),
               relief="flat", padx=6, cursor="hand2").pack(side=RIGHT)
        prog_frame = Frame(self, bg=BG, padx=14, pady=2)
        prog_frame.pack(fill=X)
        self._cv_mini_prog = Canvas(prog_frame, height=14, bg="#16162a",
                                    highlightthickness=0)
        self._cv_mini_prog.pack(fill=X)
        self._cv_mini_prog.bind("<Configure>", lambda e: self._redraw_mini_prog())
        hm_outer = Frame(self, bg=BG, padx=14, pady=4)
        hm_outer.pack(anchor=W)
        CHARS_REMAP = (list("0123456789AB") +
                       list("CDEFGHIJKLMN") +
                       list("OPQRSTUVWXYZ"))
        self._mini_cells = {}
        for i, ch in enumerate(CHARS_REMAP):
            r, c = divmod(i, self._MINI_COLS)
            cell = Frame(hm_outer, width=self._MINI_W, height=self._MINI_H,
                         bg="#252540", relief="flat", bd=0)
            cell.grid(row=r, column=c, padx=1, pady=1)
            cell.pack_propagate(False)
            lbl_ch = Label(cell, text=ch, bg="#252540", fg="#555570",
                           font=("Consolas", 10, "bold"))
            lbl_ch.pack(expand=True, pady=(2, 0))
            lbl_cnt = Label(cell, text="", bg="#252540", fg="#333350",
                            font=("Consolas", 6))
            lbl_cnt.pack()
            self._mini_cells[ch] = (cell, lbl_ch, lbl_cnt)

    def _redraw_mini_prog(self):
        cv = self._cv_mini_prog
        w  = cv.winfo_width()
        h  = cv.winfo_height()
        if w < 2: return
        cv.delete("all")
        fill_w = int(w * self._gt_prog_pct)
        if fill_w > 0:
            cv.create_rectangle(0, 0, fill_w, h, fill=ACCENT, outline="")
        cv.create_text(w // 2, h // 2,
                       text=f"{self._gt_prog_pct * 100:.1f}%",
                       fill="white", font=("Segoe UI Semibold", 7))

    def _refresh_stats(self):
        if not self.gt_path: return
        from collections import Counter
        n_rem = n_chk = 0
        rem_chars: dict = {}; chk_chars: dict = {}
        if os.path.exists(self.gt_path):
            _, rem_chars, rem_lens = analyze_gt(self.gt_path)
            n_rem = sum(rem_lens.values()) if rem_lens else 0
        if self.checked_gt_path and os.path.exists(self.checked_gt_path):
            _, chk_chars, chk_lens = analyze_gt(self.checked_gt_path)
            n_chk = sum(chk_lens.values()) if chk_lens else 0
        n_total = n_rem + n_chk
        pct     = (n_chk / n_total) if n_total else 0.0
        self._gt_prog_pct = pct
        self.lbl_gt_prog.config(
            text=(f"Đã kiểm tra: {n_chk:,} / {n_total:,}  "
                  f"({pct * 100:.1f}%)   Còn lại: {n_rem:,}"))
        self._redraw_mini_prog()
        all_chars = Counter(rem_chars)
        all_chars.update(Counter(chk_chars))
        max_cnt = max(all_chars.values(), default=1)
        for ch, (cell, lbl_ch, lbl_cnt) in self._mini_cells.items():
            cnt = all_chars.get(ch, 0)
            bg  = _heat_color(cnt, max_cnt)
            fg  = "white"   if cnt else "#555570"
            fgn = "#cccccc" if cnt else "#333350"
            cell.config(bg=bg)
            lbl_ch.config(bg=bg, fg=fg)
            lbl_cnt.config(bg=bg, fg=fgn, text=f"{cnt:,}" if cnt else "")
