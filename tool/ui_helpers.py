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


def _folder_row(parent, label_text, var, row, bg=BG):
    Label(parent, text=label_text, bg=bg, fg=DIM,
          font=F_MAIN, width=26, anchor=W).grid(row=row, column=0, sticky=W, pady=5)
    Entry(parent, textvariable=var, bg=CARD, fg=TEXT,
          insertbackground=TEXT, relief="flat", font=F_MAIN, bd=4).grid(
              row=row, column=1, sticky=EW, padx=(8, 8))
    Button(parent, text="Chọn…",
           command=lambda v=var: (
               p := filedialog.askdirectory(initialdir=v.get() or None)) and v.set(p),
           bg=ACCENT2, fg="white", activebackground=ACCENT,
           activeforeground="white", font=F_MAIN,
           relief="flat", padx=10, cursor="hand2").grid(row=row, column=2)
    parent.columnconfigure(1, weight=1)


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
