# det_table.py — Bảng chi tiết kết quả detect (dùng bởi tab_yolo.py)
from tkinter import *
from tkinter import ttk
from ...core.constants import BG, CARD, ACCENT2, TEXT, DIM, F_MAIN, F_BOLD, F_MONO

_M1_HEX = "#00c8ff"   # cyan  — Model 1
_M2_HEX = "#F05922"   # orange — Model 2
_M3_HEX = "#32dc32"   # lime green — Model 3
_COLS   = ("#", "Model", "Class", "Conf%", "W px", "H px", "Area", "X1,Y1")
_COL_W  = {"#": 30, "Model": 55, "Class": 110, "Conf%": 52,
            "W px": 58, "H px": 58, "Area": 72, "X1,Y1": 88}


class DetTablePanel(Frame):
    """Panel thu gọn được — danh sách từng bbox sau detect.

    Columns: # | Model | Class | Conf% | W px | H px | Area | X1,Y1
    Double-click hàng → gọi on_select(row_dict) để zoom canvas.
    """

    def __init__(self, master, *, on_select=None, **kw):
        super().__init__(master, bg=BG, **kw)
        self._on_select = on_select
        self._rows = []
        self._expanded = True
        self._build()

    # ---------------------------------------------------------------- build --

    def _build(self):
        hdr = Frame(self, bg=CARD, padx=6, pady=3)
        hdr.pack(fill=X)

        self._toggle_btn = Button(
            hdr, text="▼ Chi tiết detect (0)",
            bg=CARD, fg=ACCENT2, font=F_BOLD, relief="flat",
            anchor=W, cursor="hand2", command=self._toggle)
        self._toggle_btn.pack(side=LEFT)

        Label(hdr, text="2×click → zoom bbox",
              bg=CARD, fg=DIM, font=("Segoe UI", 7)).pack(side=RIGHT)

        self._table_frame = Frame(self, bg="#0d0d1e")
        self._table_frame.pack(fill=X)

        _style_tree()

        self._tree = ttk.Treeview(
            self._table_frame, style="DetTable.Treeview",
            columns=_COLS, show="headings", height=5,
            selectmode="browse")
        for c in _COLS:
            self._tree.heading(c, text=c)
            self._tree.column(c, width=_COL_W.get(c, 80),
                              anchor=CENTER, stretch=(c == "Class"))

        sb = ttk.Scrollbar(self._table_frame, orient=VERTICAL,
                           command=self._tree.yview)
        self._tree.configure(yscrollcommand=sb.set)
        sb.pack(side=RIGHT, fill=Y)
        self._tree.pack(fill=X, expand=True)

        self._tree.tag_configure("m1", foreground=_M1_HEX)
        self._tree.tag_configure("m2", foreground=_M2_HEX)
        self._tree.tag_configure("m3", foreground=_M3_HEX)
        self._tree.bind("<Double-Button-1>", self._on_dclick)

    # --------------------------------------------------------------- public --

    def update(self, rows):
        """rows: list[dict] keys = model, class_name, conf, x1, y1, x2, y2, w, h."""
        self._rows = rows
        self._tree.delete(*self._tree.get_children())
        for i, r in enumerate(rows, 1):
            model = r.get("model", "")
            tag   = "m1" if model == "M1" else ("m2" if model == "M2" else "m3")
            w, h  = r.get("w", 0), r.get("h", 0)
            area  = w * h
            conf  = f"{r.get('conf', 0) * 100:.1f}"
            pos   = f"{r.get('x1',0)},{r.get('y1',0)}"
            self._tree.insert("", END, iid=str(i - 1),
                              values=(i, model, r.get("class_name", "?"),
                                      conf, w, h, area, pos),
                              tags=(tag,))
        self._set_title(len(rows))

    def clear(self):
        self._rows.clear()
        self._tree.delete(*self._tree.get_children())
        self._set_title(0)

    # -------------------------------------------------------------- private --

    def _toggle(self):
        if self._expanded:
            self._table_frame.pack_forget()
        else:
            self._table_frame.pack(fill=X)
        self._expanded = not self._expanded
        self._set_title(len(self._rows))

    def _set_title(self, n):
        arrow = "▼" if self._expanded else "▶"
        self._toggle_btn.config(text=f"{arrow} Chi tiết detect ({n})")

    def _on_dclick(self, _event=None):
        sel = self._tree.selection()
        if not sel or not self._on_select:
            return
        idx = int(sel[0])
        if 0 <= idx < len(self._rows):
            self._on_select(self._rows[idx])


def _style_tree():
    style = ttk.Style()
    if "DetTable.Treeview" not in style.theme_names():
        pass  # always reconfigure
    style.configure("DetTable.Treeview",
                    background="#12122a", foreground=TEXT,
                    fieldbackground="#12122a", borderwidth=0,
                    rowheight=18, font=F_MONO)
    style.map("DetTable.Treeview",
              background=[("selected", ACCENT2)],
              foreground=[("selected", "white")])
    style.configure("DetTable.Treeview.Heading",
                    background=CARD, foreground=DIM, font=F_MAIN)
