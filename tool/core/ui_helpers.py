import os
from tkinter import *
from tkinter import filedialog, ttk

from .constants import (
    BG, CARD, ACCENT, ACCENT2, TEXT, DIM, SUCCESS,
    F_MAIN, F_BOLD, F_MONO,
)


def _style_all():
    s = ttk.Style()
    s.theme_use("clam")
    s.configure("K.Horizontal.TProgressbar",
                troughcolor=CARD, background=ACCENT,
                bordercolor=BG, lightcolor=ACCENT, darkcolor=ACCENT)
    s.configure("TNotebook",       background=BG, borderwidth=0)
    s.configure("TNotebook.Tab",   background=CARD, foreground=DIM,
                padding=[6, 6], font=F_BOLD)
    s.map("TNotebook.Tab",
          background=[("selected", ACCENT2)],
          foreground=[("selected", "white")])
    s.configure("Dark.Treeview",
                background="#16162a", foreground=TEXT,
                fieldbackground="#16162a", rowheight=22, font=F_MONO)
    s.configure("Dark.Treeview.Heading",
                background=ACCENT2, foreground="white",
                relief="flat", font=("Segoe UI Semibold", 9))
    s.map("Dark.Treeview",
          background=[("selected", ACCENT2)],
          foreground=[("selected", "white")])
    # Dark Combobox cho history fields
    s.configure("Dark.TCombobox",
                fieldbackground=CARD, background=CARD,
                foreground=TEXT, selectbackground=ACCENT2,
                selectforeground="white", arrowcolor=TEXT,
                borderwidth=0, relief="flat")
    s.map("Dark.TCombobox",
          fieldbackground=[("readonly", CARD), ("!readonly", CARD),
                           ("disabled", BG)],
          foreground=[("readonly", TEXT), ("!readonly", TEXT)],
          selectbackground=[("readonly", ACCENT2)],
          selectforeground=[("readonly", "white")],
          background=[("active", ACCENT2), ("!active", CARD)])


def _make_scrollable_frame(parent):
    """Trả về (canvas, inner_frame). Build widget vào inner_frame."""
    canvas = Canvas(parent, bg=BG, highlightthickness=0)
    vsb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=vsb.set)
    vsb.pack(side=RIGHT, fill=Y)
    canvas.pack(side=LEFT, fill=BOTH, expand=True)

    inner = Frame(canvas, bg=BG)
    cw = canvas.create_window((0, 0), window=inner, anchor="nw")

    def _on_inner(e):
        canvas.configure(scrollregion=canvas.bbox("all"))
    inner.bind("<Configure>", _on_inner)

    def _on_cv(e):
        req_h = inner.winfo_reqheight()
        h = max(req_h, e.height)
        canvas.itemconfig(cw, width=e.width, height=h)
        canvas.configure(scrollregion=canvas.bbox("all"))
    canvas.bind("<Configure>", _on_cv)

    def _enter(_):
        canvas.bind_all("<MouseWheel>",
                        lambda ev: canvas.yview_scroll(int(-1 * (ev.delta / 120)), "units"))
    def _leave(_):
        canvas.unbind_all("<MouseWheel>")
    canvas.bind("<Enter>", _enter)
    canvas.bind("<Leave>", _leave)

    return canvas, inner


def _make_logbox(parent):
    frame = Frame(parent, bg=BG)
    log = Text(frame, bg=CARD, fg=TEXT, font=F_MONO, relief="flat",
               bd=0, state=DISABLED, wrap=NONE, height=10, insertbackground=TEXT)
    sb = Scrollbar(frame, command=log.yview)
    log.configure(yscrollcommand=sb.set)
    sb.pack(side=RIGHT, fill=Y)
    log.pack(fill=BOTH, expand=True)
    for tag, color in [("ok", SUCCESS), ("warn", "#f0c040"),
                       ("err", "#f05050"), ("dim", DIM)]:
        log.tag_config(tag, foreground=color)
    return frame, log


def _append_log(widget, msg):
    widget.configure(state=NORMAL)
    tag = ("ok"  if msg.startswith("✔") else
           "warn" if msg.startswith("⚠") else
           "err"  if msg.startswith("[LỖI]") else "dim")
    widget.insert(END, msg + "\n", tag)
    widget.see(END)
    widget.configure(state=DISABLED)


def _folder_row(parent, label_text, var, row, bg=BG, history_key=None):
    """Tạo label + entry/combobox + browse button theo dạng grid.

    Nếu history_key được truyền vào, sử dụng Combobox với lịch sử,
    ngược lại dùng Entry thông thường.
    """
    Label(parent, text=label_text, bg=bg, fg=DIM,
          font=F_MAIN, width=26, anchor=W).grid(row=row, column=0, sticky=W, pady=5)

    if history_key:
        from .settings import _bind_history, _push_history, _get_history
        combo = ttk.Combobox(parent, textvariable=var,
                             style="Dark.TCombobox", font=F_MAIN)
        combo["values"] = _get_history(history_key)
        combo.grid(row=row, column=1, sticky=EW, padx=(8, 8))
        _bind_history(history_key, combo)

        def _pick(v=var, k=history_key, c=combo):
            p = filedialog.askdirectory(initialdir=v.get() or None)
            if p:
                v.set(p)
                _push_history(k, p)
                c["values"] = _get_history(k)
        btn_cmd = _pick
    else:
        Entry(parent, textvariable=var, bg=CARD, fg=TEXT,
              insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4).grid(
                  row=row, column=1, sticky=EW, padx=(8, 8))

        def _pick_plain(v=var):
            p = filedialog.askdirectory(initialdir=v.get() or None)
            if p:
                v.set(p)
        btn_cmd = _pick_plain

    Button(parent, text="Chọn…",
           command=btn_cmd,
           bg=ACCENT2, fg="white", activebackground=ACCENT,
           activeforeground="white", font=F_MAIN,
           relief="flat", padx=10, cursor="hand2").grid(row=row, column=2)

    def _open_dir(v=var):
        p = v.get().strip()
        if p and os.path.isdir(p):
            os.startfile(p)
    Button(parent, text="📂",
           command=_open_dir,
           bg=CARD, fg=TEXT, activebackground=ACCENT2,
           activeforeground="white", font=F_MAIN,
           relief="flat", padx=6, cursor="hand2").grid(row=row, column=3, padx=(2, 0))
    parent.columnconfigure(1, weight=1)


_ZOOM_PALETTE = [
    "#F05922", "#4caf50", "#2196f3", "#9c27b0", "#ff9800",
    "#00bcd4", "#e91e63", "#8bc34a", "#ff5722", "#607d8b",
    "#ffeb3b", "#3f51b5", "#009688", "#795548", "#f44336",
]


def _load_label_bboxes(img_path, lbl_path=None):
    """Đọc file YOLO .txt bên cạnh ảnh, trả về list [[cid,x1,y1,x2,y2]] pixel coords.
    Trả về None nếu không có file label hoặc lỗi."""
    try:
        from PIL import Image as _PILImg
        from pathlib import Path
        img_p = Path(img_path)
        lbl_p = Path(lbl_path) if lbl_path else img_p.parent / (img_p.stem + ".txt")
        if not lbl_p.exists() or lbl_p.stat().st_size == 0:
            return None
        with _PILImg.open(img_p) as _im:
            iw, ih = _im.size
        bboxes = []
        with open(lbl_p, encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) < 5:
                    continue
                cid = int(parts[0])
                xc, yc, w, h = map(float, parts[1:5])
                bboxes.append([cid,
                                (xc - w / 2) * iw, (yc - h / 2) * ih,
                                (xc + w / 2) * iw, (yc + h / 2) * ih])
        return bboxes or None
    except Exception:
        return None


def _zoom_image_window(root, pil_img, title="Phóng to ảnh",
                       bboxes=None, label_names=None):
    """Mở Toplevel hiển thị ảnh phóng to. Cuộn chuột để zoom thêm, Escape/Ctrl+W để đóng.

    bboxes: list [[cid, x1, y1, x2, y2]] tọa độ pixel gốc — được overlay lên ảnh.
    label_names: list[str] tên class theo index.
    """
    try:
        from PIL import Image, ImageTk
    except ImportError:
        return
    if pil_img is None:
        return

    win = Toplevel(root)
    win.title(title)
    win.configure(bg="#0d0d1a")
    win.resizable(True, True)
    win.protocol("WM_DELETE_WINDOW", win.destroy)

    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    max_w, max_h = int(sw * 0.85), int(sh * 0.85)
    orig = pil_img.copy()
    ow, oh = orig.size
    fit = min(max_w / max(ow, 1), max_h / max(oh, 1), 1.0)
    _s = [fit]

    sb_h = Scrollbar(win, orient=HORIZONTAL)
    sb_v = Scrollbar(win, orient=VERTICAL)
    cv = Canvas(win, bg="#0d0d1a", highlightthickness=0,
                xscrollcommand=sb_h.set, yscrollcommand=sb_v.set)
    sb_h.config(command=cv.xview)
    sb_v.config(command=cv.yview)
    sb_h.pack(side=BOTTOM, fill=X)
    sb_v.pack(side=RIGHT, fill=Y)
    cv.pack(fill=BOTH, expand=True)

    def _render():
        nw = max(1, int(ow * _s[0]))
        nh = max(1, int(oh * _s[0]))
        img = orig.resize((nw, nh), Image.LANCZOS)
        tk_img = ImageTk.PhotoImage(img)
        cv._tk_img = tk_img
        cv.delete("all")
        cv.create_image(0, 0, anchor=NW, image=tk_img)
        if bboxes:
            sc = _s[0]
            for bbox in bboxes:
                cid = int(bbox[0])
                cx1 = int(bbox[1] * sc)
                cy1 = int(bbox[2] * sc)
                cx2 = int(bbox[3] * sc)
                cy2 = int(bbox[4] * sc)
                color = _ZOOM_PALETTE[cid % len(_ZOOM_PALETTE)]
                cv.create_rectangle(cx1, cy1, cx2, cy2, outline=color, width=2)
                name = (label_names[cid] if (label_names and cid < len(label_names))
                        else str(cid))
                lbl_txt = f" {cid}:{name} "
                lbl_w = max(len(lbl_txt) * 7, 30)
                cv.create_rectangle(cx1, max(0, cy1 - 17), cx1 + lbl_w, cy1,
                                    fill=color, outline="")
                cv.create_text(cx1 + 3, max(8, cy1 - 8), text=lbl_txt, fill="white",
                               font=("Segoe UI", 8, "bold"), anchor=W)
        cv.configure(scrollregion=(0, 0, nw, nh))

    def _on_wheel(e):
        _s[0] = max(0.05, min(10.0, _s[0] * (1.1 if e.delta > 0 else 0.9)))
        _render()

    cv.bind("<MouseWheel>", _on_wheel)
    win.bind("<Escape>",    lambda _: win.destroy())
    win.bind("<Control-w>", lambda _: win.destroy())

    init_w = min(max_w, max(200, int(ow * fit) + 24))
    init_h = min(max_h, max(150, int(oh * fit) + 24))
    win.geometry(f"{init_w}x{init_h}")
    win.lift()
    win.focus_set()
    win.after(30, _render)


def _pb_row(parent):
    lbl = Label(parent, text="Sẵn sàng", bg=BG, fg=DIM, font=F_MAIN, anchor=W)
    lbl.pack(fill=X)
    pb = ttk.Progressbar(parent, style="K.Horizontal.TProgressbar",
                         maximum=100, length=400)
    pb.pack(fill=X, pady=(3, 8))
    return lbl, pb


def _set_progress(lbl, pb, done, total, root):
    pct = int(done / total * 100)
    pb["value"] = pct
    lbl.config(text=f"Đang xử lý: {done} / {total}  ({pct}%)")
    root.update_idletasks()


def _action_btn(parent, text, cmd, color, **kw):
    return Button(parent, text=text, command=cmd,
                  bg=color, fg="white", activebackground=color,
                  activeforeground="white", font=F_BOLD,
                  relief="flat", cursor="hand2", **kw)


class DateTimePicker(Frame):
    """Entry + nút lịch cho chọn ngày/giờ.

    mode:
        "datetime"   → YYYY-MM-DD HH:MM:SS
        "datetime_T" → YYYY-MM-DDTHH:MM:SS
        "date"       → YYYY-MM-DD
    """

    _FMT = {
        "datetime":   "%Y-%m-%d %H:%M:%S",
        "datetime_T": "%Y-%m-%dT%H:%M:%S",
        "date":       "%Y-%m-%d",
    }

    def __init__(self, parent, textvariable, mode="datetime", **kwargs):
        frame_bg = kwargs.pop("bg", BG)
        super().__init__(parent, bg=frame_bg, **kwargs)
        self._var    = textvariable
        self._mode   = mode
        self._bg     = frame_bg
        self._popup  = None

        entry_w = 12 if mode == "date" else 20
        self._entry = Entry(
            self, textvariable=textvariable, width=entry_w,
            bg=CARD, fg=TEXT, insertbackground=TEXT,
            relief="flat", font=F_MAIN, bd=4)
        self._entry.pack(side=LEFT)

        Button(
            self, text="📅", command=self._open_popup,
            bg=frame_bg, fg=ACCENT,
            font=("Segoe UI", 10),
            activebackground=ACCENT2, activeforeground="white",
            relief="flat", cursor="hand2", padx=4, pady=1,
        ).pack(side=LEFT, padx=(2, 0))

    # ── helpers ───────────────────────────────────────────────────────────

    def _parse(self):
        from datetime import datetime as _dt
        val = self._var.get().strip()
        try:
            return _dt.strptime(val, self._FMT[self._mode])
        except Exception:
            return _dt.now().replace(microsecond=0)

    def _fmt(self, dt):
        return dt.strftime(self._FMT[self._mode])

    # ── popup calendar ────────────────────────────────────────────────────

    def _open_popup(self):
        if self._popup and self._popup.winfo_exists():
            self._popup.lift()
            return

        import calendar as _cal
        from datetime import datetime as _dt, date as _date

        dt = self._parse()

        pop = Toplevel(self)
        pop.title("Chọn ngày" + ("" if self._mode == "date" else " & giờ"))
        pop.configure(bg=BG)
        pop.resizable(False, False)
        pop.protocol("WM_DELETE_WINDOW", pop.destroy)
        pop.transient(self.winfo_toplevel())
        self._popup = pop

        # position below the widget
        self.update_idletasks()
        rx = self.winfo_rootx()
        ry = self.winfo_rooty() + self.winfo_height() + 2
        pop.geometry(f"+{rx}+{ry}")

        _year      = [dt.year]
        _month     = [dt.month]
        _sel       = [_date(dt.year, dt.month, dt.day)]
        _day_btns  = {}

        # ── month header ──────────────────────────────────────────────
        hdr = Frame(pop, bg=BG, padx=10, pady=6)
        hdr.pack(fill=X)

        btn_prev = Button(hdr, text="◀", bg=BG, fg=TEXT,
                          activebackground=ACCENT2, activeforeground="white",
                          relief="flat", font=F_MAIN, cursor="hand2", padx=8)
        btn_prev.pack(side=LEFT)

        lbl_ym = Label(hdr, text="", bg=BG, fg=TEXT,
                       font=("Segoe UI Semibold", 10), width=14, anchor=CENTER)
        lbl_ym.pack(side=LEFT, expand=True)

        btn_next = Button(hdr, text="▶", bg=BG, fg=TEXT,
                          activebackground=ACCENT2, activeforeground="white",
                          relief="flat", font=F_MAIN, cursor="hand2", padx=8)
        btn_next.pack(side=RIGHT)

        # ── weekday labels ────────────────────────────────────────────
        cal_f = Frame(pop, bg=BG, padx=10)
        cal_f.pack()

        for ci, dn in enumerate(["T2", "T3", "T4", "T5", "T6", "T7", "CN"]):
            Label(cal_f, text=dn, bg=BG,
                  fg=(ACCENT if dn == "CN" else DIM),
                  font=("Segoe UI", 8, "bold"),
                  width=3, anchor=CENTER).grid(row=0, column=ci, padx=1, pady=(0, 3))

        # ── day grid ──────────────────────────────────────────────────
        def _render():
            for b in _day_btns.values():
                b.destroy()
            _day_btns.clear()

            lbl_ym.config(text=f"{_year[0]:04d}-{_month[0]:02d}")
            first_wd, num_days = _cal.monthrange(_year[0], _month[0])
            col = first_wd   # 0=Mon … 6=Sun
            row = 1
            today = _date.today()

            for day in range(1, num_days + 1):
                d = _date(_year[0], _month[0], day)
                is_sel   = (d == _sel[0])
                is_today = (d == today)
                is_sun   = (col == 6)

                if is_sel:
                    bg_c, fg_c = ACCENT, "white"
                elif is_today:
                    bg_c, fg_c = ACCENT2, "white"
                elif is_sun:
                    bg_c, fg_c = BG, ACCENT
                else:
                    bg_c, fg_c = BG, TEXT

                def _pick(d_=d):
                    _sel[0] = d_
                    _render()

                b = Button(cal_f, text=str(day),
                           bg=bg_c, fg=fg_c,
                           activebackground=ACCENT, activeforeground="white",
                           relief="flat", font=("Segoe UI", 9),
                           width=3, cursor="hand2", command=_pick)
                b.grid(row=row, column=col, padx=1, pady=1)
                _day_btns[day] = b

                col += 1
                if col > 6:
                    col = 0
                    row += 1

        def _prev():
            if _month[0] == 1:
                _month[0] = 12; _year[0] -= 1
            else:
                _month[0] -= 1
            _render()

        def _next():
            if _month[0] == 12:
                _month[0] = 1; _year[0] += 1
            else:
                _month[0] += 1
            _render()

        btn_prev.config(command=_prev)
        btn_next.config(command=_next)
        _render()

        # ── time spinboxes (datetime modes only) ──────────────────────
        h_var = IntVar(value=dt.hour)
        m_var = IntVar(value=dt.minute)
        s_var = IntVar(value=dt.second)

        if self._mode != "date":
            Frame(pop, bg=DIM, height=1).pack(fill=X, padx=10, pady=(6, 0))
            tf = Frame(pop, bg=BG, padx=10, pady=6)
            tf.pack()

            for lbl_txt, var, to_val in [
                ("Giờ",  h_var, 23),
                ("Phút", m_var, 59),
                ("Giây", s_var, 59),
            ]:
                Label(tf, text=lbl_txt + ":", bg=BG, fg=DIM,
                      font=F_MAIN).pack(side=LEFT)
                Spinbox(tf, from_=0, to=to_val, textvariable=var,
                        width=4, format="%02.0f",
                        bg=CARD, fg=TEXT, insertbackground=TEXT,
                        buttonbackground=ACCENT2, relief="flat",
                        font=F_MAIN).pack(side=LEFT, padx=(2, 10))

        # ── OK / Cancel ───────────────────────────────────────────────
        Frame(pop, bg=DIM, height=1).pack(fill=X, padx=10, pady=(4, 0))
        bf = Frame(pop, bg=BG, padx=10, pady=8)
        bf.pack()

        def _confirm():
            from datetime import datetime as _dt2
            d = _sel[0]
            if self._mode == "date":
                result = _dt2(d.year, d.month, d.day)
            else:
                result = _dt2(d.year, d.month, d.day,
                              h_var.get(), m_var.get(), s_var.get())
            self._var.set(self._fmt(result))
            pop.destroy()

        Button(bf, text="  OK  ", command=_confirm,
               bg=ACCENT, fg="white", font=F_MAIN,
               activebackground="#c04010", activeforeground="white",
               relief="flat", padx=10, pady=4, cursor="hand2").pack(side=LEFT, padx=(0, 8))
        Button(bf, text="  Hủy  ", command=pop.destroy,
               bg=CARD, fg=TEXT, font=F_MAIN,
               activebackground=DIM, activeforeground=TEXT,
               relief="flat", padx=10, pady=4, cursor="hand2").pack(side=LEFT)

        pop.bind("<Return>", lambda _: _confirm())
        pop.bind("<Escape>", lambda _: pop.destroy())
        pop.grab_set()
        pop.focus_set()
