"""IParkingSettingsMixin — tất cả _build_* panel cài đặt cho IParkingImageTab."""
from tkinter import *
from tkinter import ttk

from ...core.constants import (
    BG, CARD, ACCENT, ACCENT2, TEXT, DIM, F_MAIN, F_BOLD,
    _LI_API_BASE, _LI_USERNAME, _LI_PASSWORD,
    _LI_MINIO_EP, _LI_MINIO_AK, _LI_MINIO_SK, _LI_MINIO_BUCKET,
    _P8_LOGIN_URL, _P8_API_URL, _P8_CLIENT_ID, _P8_CLIENT_SECRET,
    _P8_USERNAME, _P8_PASSWORD,
    _P6_API_URL, _P6_MINIO_EP, _P6_MINIO_BUCKET, _P6_MINIO_AK, _P6_MINIO_SK,
)
from ...core.settings import _bind_cfg, _bind_history
from ...core.ui_helpers import DateTimePicker
from .iparking_constants import _VTYPE_ORDER


class IParkingSettingsMixin:
    """Mixin chứa _build_* cho các panel cài đặt thời gian, giới hạn, nguồn."""

    def _sep(self, parent, text):
        f = Frame(parent, bg=BG)
        f.pack(fill=X, pady=(8, 3))
        Label(f, text=text, font=("Segoe UI", 9, "bold"),
              fg=ACCENT2, bg=BG).pack(side=LEFT)
        Frame(f, bg="#CBCBCB", height=1).pack(side=LEFT, fill=X, expand=True,
                                               padx=(8, 0), pady=5)

    # ── Thời gian ─────────────────────────────────────────────────────────────

    def _build_time(self, p):
        f = Frame(p, bg=BG, padx=10, pady=4)
        f.pack(fill=X)
        self._sep(f, "Khoảng thời gian (UTC)")
        row = Frame(f, bg=BG)
        row.pack(fill=X)
        Label(row, text="Từ:", bg=BG, fg=TEXT, font=F_MAIN).grid(
            row=0, column=0, padx=(0, 4), sticky=W)
        self.from_var = StringVar(value="2026-05-01 00:00:00")
        _bind_cfg("ip.from", self.from_var)
        DateTimePicker(row, textvariable=self.from_var, mode="datetime").grid(
            row=0, column=1, padx=4)
        Label(row, text="Đến:", bg=BG, fg=TEXT, font=F_MAIN).grid(
            row=0, column=2, padx=(14, 4))
        from datetime import datetime
        self.to_var = StringVar(value=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))
        _bind_cfg("ip.to", self.to_var)
        DateTimePicker(row, textvariable=self.to_var, mode="datetime").grid(
            row=0, column=3, padx=4)
        self._time_hint_lbl = Label(row, text="", font=("Segoe UI", 8),
                                    fg=DIM, bg=BG)
        self._time_hint_lbl.grid(row=0, column=4, padx=(14, 0), sticky=W)

    # ── Thư mục đầu ra ────────────────────────────────────────────────────────

    def _build_output(self, p):
        from pathlib import Path
        from ...core.settings import _bind_history
        f = Frame(p, bg=BG, padx=10, pady=2)
        f.pack(fill=X)
        self._sep(f, "Thư mục lưu ảnh")
        row = Frame(f, bg=BG)
        row.pack(fill=X)
        row.columnconfigure(0, weight=1)
        self.out_var = StringVar(value=str(Path.cwd() / "images_ip"))
        _bind_cfg("ip.out", self.out_var)
        self._out_combo = ttk.Combobox(row, textvariable=self.out_var,
                                       style="Dark.TCombobox", font=F_MAIN)
        self._out_combo.grid(row=0, column=0, sticky=EW, padx=(0, 6))
        _bind_history("h.ip.out", self._out_combo)
        Button(row, text="Chọn…", command=self._browse,
               bg=ACCENT2, fg="white", font=F_MAIN,
               activebackground=ACCENT, activeforeground="white",
               relief="flat", padx=10, cursor="hand2").grid(row=0, column=1)
        Button(row, text="📂", command=self._open_out,
               bg=CARD, fg=TEXT, font=F_MAIN,
               activebackground=ACCENT2, activeforeground="white",
               relief="flat", padx=6, cursor="hand2").grid(row=0, column=2, padx=(2, 0))
        self._struct_lbl = Label(f, text="", font=("Segoe UI", 8),
                                 fg=DIM, bg=BG, anchor=W, wraplength=800, justify=LEFT)
        self._struct_lbl.pack(fill=X, pady=(3, 0))

    # ── Giới hạn chung ────────────────────────────────────────────────────────

    def _build_common_limits(self, p):
        f = Frame(p, bg=BG, padx=10, pady=2)
        f.pack(fill=X)
        self._sep(f, "Cài đặt chung")
        row1 = Frame(f, bg=BG)
        row1.pack(fill=X)
        for col, (lbl, attr, lo, hi, w, val) in enumerate([
            ("Page size:",     "page_size_var",    10,  500,   6,   100),
            ("Max pages:",     "max_pages_var",     1,  99999, 8, 10000),
            ("Nghỉ (s):",      None,                0,  0,     0,     0),
            ("Max SK/làn:",    "max_per_lane_var",  0,  999999,8,  1000),
            ("Max SK/loại:",   "max_per_cat_var",   0,  999999,8,     0),
            ("Max SK/buổi:",   "max_per_buoi_var",  0,  99999, 7,     0),
        ]):
            Label(row1, text=lbl, bg=BG, fg=TEXT, font=F_MAIN).grid(
                row=0, column=col * 2, padx=(14 if col else 0, 4), sticky=W)
            if attr is None:
                self.sleep_var = DoubleVar(value=0.1)
                _bind_cfg("ip.sleep", self.sleep_var)
                Entry(row1, textvariable=self.sleep_var, width=6,
                      bg=CARD, fg=TEXT, insertbackground=TEXT,
                      relief="flat", font=F_MAIN, bd=4).grid(
                    row=0, column=col * 2 + 1, padx=4)
            else:
                var = IntVar(value=val)
                setattr(self, attr, var)
                _bind_cfg(f"ip.{attr[:-4]}", var)
                Spinbox(row1, from_=lo, to=hi, textvariable=var,
                        width=w, font=F_MAIN, bg=CARD, fg=TEXT,
                        insertbackground=TEXT, buttonbackground=ACCENT2,
                        relief="flat").grid(row=0, column=col * 2 + 1, padx=4)
        row2 = Frame(f, bg=BG)
        row2.pack(fill=X, pady=(6, 0))
        Label(row2, text="Luồng song song:", bg=BG, fg=TEXT, font=F_MAIN).grid(
            row=0, column=0, padx=(0, 4), sticky=W)
        self.parallel_var = IntVar(value=1)
        _bind_cfg("ip.parallel", self.parallel_var)
        Spinbox(row2, from_=1, to=16, textvariable=self.parallel_var,
                width=4, font=F_MAIN, bg=CARD, fg=TEXT,
                insertbackground=TEXT, buttonbackground=ACCENT2,
                relief="flat").grid(row=0, column=1, padx=4)
        Label(row2, text="(chia ngày cho N luồng chạy đồng thời — áp dụng cho cả 3 nguồn)",
              bg=BG, fg=DIM, font=("Segoe UI", 8)).grid(
            row=0, column=2, padx=(4, 0), sticky=W)
        Label(f, text="Max SK/làn: tổng cả lần chạy  ·  Max SK/loại: tối đa/ngày/loại/làn  ·  Max SK/buổi: trải đều sáng-trưa-chiều-tối  ·  0 = không giới hạn",
              font=("Segoe UI", 7), fg=DIM, bg=BG, anchor=W).pack(fill=X, pady=(4, 0))

        _guide_row = Frame(f, bg=BG)
        _guide_row.pack(fill=X, pady=(4, 0))
        _guide_body = Frame(f, bg=CARD, padx=10, pady=6)

        def _toggle_guide():
            if _guide_body.winfo_ismapped():
                _guide_body.pack_forget()
                _guide_toggle_btn.config(text="▶  Hướng dẫn thiết lập Max SK")
            else:
                _guide_body.pack(fill=X, pady=(2, 4))
                _guide_toggle_btn.config(text="▼  Hướng dẫn thiết lập Max SK")

        _guide_toggle_btn = Button(
            _guide_row, text="▶  Hướng dẫn thiết lập Max SK",
            bg=BG, fg=DIM, font=("Segoe UI", 8, "underline"),
            relief="flat", padx=0, pady=0, cursor="hand2",
            activebackground=BG, activeforeground=TEXT,
            command=_toggle_guide)
        _guide_toggle_btn.pack(anchor=W)

        _GUIDE_LINES = (
            "Mục tiêu: N ảnh/loại xe  ·  K làn  ·  10 ngày liên tiếp  ·  4 buổi/ngày\n"
            "\n"
            "  Max SK/làn   =  N ÷ K                   ví dụ  N=1000, K=3  →   334\n"
            "  Max SK/loại  =  N ÷ (K × 10)            ví dụ  N=1000, K=3  →    34\n"
            "  Max SK/buổi  =  N ÷ (K × 10 × 4)       ví dụ  N=1000, K=3  →     9\n"
            "\n"
            "  Bảng nhanh (N = 1000):\n"
            "    K = 2 làn  →  Max SK/làn = 500  ·  Max SK/loại = 50  ·  Max SK/buổi = 13\n"
            "    K = 3 làn  →  Max SK/làn = 334  ·  Max SK/loại = 34  ·  Max SK/buổi =  9\n"
            "    K = 4 làn  →  Max SK/làn = 250  ·  Max SK/loại = 25  ·  Max SK/buổi =  7\n"
            "    K = 5 làn  →  Max SK/làn = 200  ·  Max SK/loại = 20  ·  Max SK/buổi =  5\n"
            "\n"
            "  Lưu ý: chỉ tick 1 loại xe mỗi lần chạy — nếu tick nhiều loại, Max SK/làn\n"
            "         bị chia sẻ giữa các loại và không đảm bảo đủ 1000 ảnh/loại."
        )
        Label(_guide_body, text=_GUIDE_LINES, bg=CARD, fg=TEXT,
              font=("Segoe UI", 8), justify=LEFT, anchor=W).pack(fill=X)

        row_gt = Frame(f, bg=BG)
        row_gt.pack(fill=X, pady=(8, 0))
        self.only_gt_var = BooleanVar(value=False)
        _bind_cfg("ip.only_gt", self.only_gt_var)
        Checkbutton(row_gt,
                    text="Chỉ lấy ảnh có GT  (biển vào = biển ra  hoặc  có biển số đăng ký)",
                    variable=self.only_gt_var, bg=BG, fg=TEXT, selectcolor="#251C53",
                    activebackground=BG, font=F_MAIN, cursor="hand2").pack(side=LEFT)

        self._sep(f, "Loại ảnh lấy")
        _VTYPE_LABELS = {
            "toan_canh_o_to":   "Toàn cảnh ô tô",
            "toan_canh_xe_may": "Toàn cảnh xe máy",
            "toan_canh_xe_dap": "Toàn cảnh xe đạp",
            "toan_canh":        "Toàn cảnh",
            "o_to":             "Ô tô",
            "xe_may":           "Xe máy",
            "xe_dap":           "Xe đạp",
            "xe_tai":           "Xe tải",
            "o_to_bsx_cut":     "Ô tô biển cắt",
            "xe_may_bsx_cut":   "Xe máy biển cắt",
            "xe_dap_bsx_cut":   "Xe đạp biển cắt",
        }
        self._vtype_vars: dict = {}
        for vt in _VTYPE_ORDER:
            var = BooleanVar(value=True)
            _bind_cfg(f"ip.vtype.{vt}", var)
            self._vtype_vars[vt] = var
        vt_btn_row = Frame(f, bg=BG)
        vt_btn_row.pack(fill=X, pady=(0, 4))
        Button(vt_btn_row, text="✔ Chọn tất cả",
               command=lambda: [v.set(True)  for v in self._vtype_vars.values()],
               bg=CARD, fg=TEXT, font=("Segoe UI", 8), relief="flat",
               padx=8, pady=2, cursor="hand2").pack(side=LEFT, padx=(0, 4))
        Button(vt_btn_row, text="✘ Bỏ tất cả",
               command=lambda: [v.set(False) for v in self._vtype_vars.values()],
               bg=CARD, fg=DIM, font=("Segoe UI", 8), relief="flat",
               padx=8, pady=2, cursor="hand2").pack(side=LEFT)
        vt_grid = Frame(f, bg=BG)
        vt_grid.pack(fill=X)
        for i, vt in enumerate(_VTYPE_ORDER):
            r, c = divmod(i, 4)
            Checkbutton(vt_grid,
                        text=_VTYPE_LABELS.get(vt, vt),
                        variable=self._vtype_vars[vt],
                        bg=BG, fg=TEXT, selectcolor="#251C53",
                        activebackground=BG, font=("Segoe UI", 8),
                        cursor="hand2").grid(
                row=r, column=c, sticky=W,
                padx=(0 if c == 0 else 14, 0), pady=1)
        Label(f, text="Bỏ check để bỏ qua loại đó  ·  bsx_cut chỉ có Parkingv8/v6",
              font=("Segoe UI", 7), fg=DIM, bg=BG, anchor=W).pack(fill=X, pady=(2, 0))

    # ── Lotte settings ────────────────────────────────────────────────────────

    def _build_lotte_settings(self, p):
        f = Frame(p, bg=BG, padx=10, pady=2)
        f.pack(fill=X)
        self._sep(f, "Cài đặt — LotteImage")
        row = Frame(f, bg=BG)
        row.pack(fill=X)
        self.l_use_minio = BooleanVar(value=True)
        _bind_cfg("lotte.use_minio", self.l_use_minio)
        Checkbutton(row, text="Dùng MinIO", variable=self.l_use_minio,
                    bg=BG, fg=TEXT, selectcolor=CARD,
                    activebackground=BG, font=F_MAIN).grid(
            row=0, column=0, padx=(0, 20))

        kw_row_l = Frame(f, bg=BG)
        kw_row_l.pack(fill=X, pady=(6, 0))
        Label(kw_row_l, text="Keyword:", bg=BG, fg=TEXT, font=F_MAIN).pack(side=LEFT, padx=(0, 6))
        self.l_keyword_var = StringVar(value="")
        _bind_cfg("lotte.keyword", self.l_keyword_var)
        self._l_kw_combo = ttk.Combobox(kw_row_l, textvariable=self.l_keyword_var,
                                         font=F_MAIN, width=40)
        self._l_kw_combo.pack(side=LEFT)
        _bind_history("h.lotte.keyword", self._l_kw_combo)
        Label(kw_row_l, text="Lọc sự kiện API theo biển số / tên thẻ  ·  bỏ trống = lấy tất cả",
              bg=BG, fg=DIM, font=("Segoe UI", 8)).pack(side=LEFT, padx=(8, 0))

        self._sep(f, "Phân loại phương tiện (từ khóa)")
        fv = Frame(f, bg=BG)
        fv.pack(fill=X)
        for r, (lbl, key_suffix, default) in enumerate([
            ("Toàn cảnh (mô tả ảnh):", "toan_canh", "toàn cảnh"),
            ("Xe máy (nhóm thẻ):",      "xe_may",    "xe máy"),
            ("Xe đạp (nhóm thẻ):",      "xe_dap",    "xe đạp"),
            ("Ô tô (nhóm thẻ):",        "o_to",      ""),
        ]):
            Label(fv, text=lbl, bg=BG, fg=TEXT, font=F_MAIN).grid(
                row=r, column=0, padx=(0, 6), sticky=W, pady=2)
            var = StringVar(value=default)
            setattr(self, f"l_kw_{key_suffix}", var)
            _bind_cfg(f"lotte.kw_{key_suffix}", var)
            Entry(fv, textvariable=var, width=48,
                  bg=CARD, fg=TEXT, insertbackground=TEXT,
                  relief="flat", font=F_MAIN, bd=4).grid(
                row=r, column=1, sticky=W, padx=4, pady=2)
        Label(f, text="Nhiều từ khóa cách nhau bởi dấu phẩy  ·  Ô tô = mặc định khi không khớp",
              font=("Segoe UI", 8), fg=DIM, bg=BG, anchor=W).pack(fill=X, pady=(2, 0))

        self._l_adv_open = False
        self._l_adv_lbl = Label(f, text="▶ Nâng cao (API / MinIO)",
                                 font=("Segoe UI", 8, "underline"),
                                 fg=ACCENT2, bg=BG, cursor="hand2")
        self._l_adv_lbl.pack(anchor=W, pady=(8, 0))
        self._l_adv_lbl.bind("<Button-1>", lambda _: self._toggle_adv("l"))
        self._l_adv_frm = Frame(f, bg=CARD, padx=8, pady=6)
        for i, (lbl, attr, default, width, show) in enumerate([
            ("API URL:",        "l_api",  _LI_API_BASE,     38, ""),
            ("Username:",       "l_user", _LI_USERNAME,     16, ""),
            ("Password:",       "l_pass", _LI_PASSWORD,     16, "*"),
            ("MinIO endpoint:", "l_mep",  _LI_MINIO_EP,     26, ""),
            ("MinIO bucket:",   "l_mbk",  _LI_MINIO_BUCKET, 20, ""),
            ("MinIO AK:",       "l_mak",  _LI_MINIO_AK,     16, ""),
            ("MinIO SK:",       "l_msk",  _LI_MINIO_SK,     20, "*"),
        ]):
            r, c = divmod(i, 2)
            Label(self._l_adv_frm, text=lbl, font=("Segoe UI", 8),
                  bg=CARD, fg=DIM).grid(
                row=r, column=c * 2, padx=(0 if c == 0 else 16, 4), pady=2, sticky=W)
            var = StringVar(value=default)
            setattr(self, attr, var)
            _bind_cfg(f"lotte.cfg_{attr[2:]}", var)
            Entry(self._l_adv_frm, textvariable=var, width=width, show=show,
                  bg="#16162a", fg=TEXT, insertbackground=TEXT,
                  relief="flat", font=F_MAIN, bd=4).grid(
                row=r, column=c * 2 + 1, padx=(0, 4), pady=2)

    # ── Parkingv8 settings ────────────────────────────────────────────────────

    def _build_p8_settings(self, p):
        f = Frame(p, bg=BG, padx=10, pady=2)
        f.pack(fill=X)
        self._sep(f, "Cài đặt — Parkingv8")
        row = Frame(f, bg=BG)
        row.pack(fill=X)
        Label(row, text="Nguồn sự kiện:", bg=BG, fg=TEXT, font=F_MAIN).grid(
            row=0, column=0, padx=(0, 4), sticky=W)
        self.p8_source_var = StringVar(value="exits")
        _bind_cfg("p8.source", self.p8_source_var)
        ttk.Combobox(row, textvariable=self.p8_source_var,
                     values=["exits", "entries", "both"],
                     width=10, state="readonly", font=F_MAIN).grid(
            row=0, column=1, padx=4)
        Label(row, text="exits=ra  ·  entries=vào  ·  both=cả hai",
              bg=BG, fg=DIM, font=("Segoe UI", 8)).grid(
            row=0, column=2, padx=(8, 0), sticky=W)

        row2 = Frame(f, bg=BG)
        row2.pack(fill=X, pady=(6, 0))
        Label(row2, text="Phương thức ảnh:", bg=BG, fg=TEXT, font=F_MAIN).grid(
            row=0, column=0, padx=(0, 4), sticky=W)
        self.p8_img_mode_var = StringVar(value="url")
        _bind_cfg("p8.img_mode", self.p8_img_mode_var)
        for col, (val, lbl) in enumerate([("url", "URL (PresignedUrl)"), ("base64", "Base64")], 1):
            Radiobutton(row2, text=lbl, variable=self.p8_img_mode_var, value=val,
                        bg=BG, fg=TEXT, selectcolor=BG,
                        activebackground=BG, font=F_MAIN, cursor="hand2").grid(
                row=0, column=col, padx=(0 if col == 1 else 16, 0), sticky=W)
        Label(row2, text="URL: tải qua HTTP  ·  Base64: giải mã trực tiếp từ response",
              bg=BG, fg=DIM, font=("Segoe UI", 8)).grid(
            row=0, column=3, padx=(16, 0), sticky=W)

        kw_row_p8 = Frame(f, bg=BG)
        kw_row_p8.pack(fill=X, pady=(6, 0))
        Label(kw_row_p8, text="Keyword:", bg=BG, fg=TEXT, font=F_MAIN).pack(side=LEFT, padx=(0, 6))
        self.p8_keyword_var = StringVar(value="")
        _bind_cfg("p8.keyword", self.p8_keyword_var)
        self._p8_kw_combo = ttk.Combobox(kw_row_p8, textvariable=self.p8_keyword_var,
                                          font=F_MAIN, width=40)
        self._p8_kw_combo.pack(side=LEFT)
        _bind_history("h.p8.keyword", self._p8_kw_combo)
        Label(kw_row_p8, text="Lọc theo biển số / mã thẻ / tên thẻ / ghi chú  ·  bỏ trống = lấy tất cả",
              bg=BG, fg=DIM, font=("Segoe UI", 8)).pack(side=LEFT, padx=(8, 0))

        self._p8_adv_open = False
        self._p8_adv_lbl = Label(f, text="▶ Nâng cao (API / Xác thực)",
                                  font=("Segoe UI", 8, "underline"),
                                  fg=ACCENT2, bg=BG, cursor="hand2")
        self._p8_adv_lbl.pack(anchor=W, pady=(10, 0))
        self._p8_adv_lbl.bind("<Button-1>", lambda _: self._toggle_adv("p8"))
        self._p8_adv_frm = Frame(f, bg=CARD, padx=8, pady=6)
        gt_row = Frame(self._p8_adv_frm, bg=CARD)
        gt_row.grid(row=0, column=0, columnspan=4, sticky=W, pady=(0, 6))
        Label(gt_row, text="Grant type:", font=("Segoe UI", 8),
              bg=CARD, fg=DIM).pack(side=LEFT, padx=(0, 8))
        self.p8_grant_var = StringVar(value="client_credentials")
        _bind_cfg("p8.grant_type", self.p8_grant_var)
        for val, lbl in [("client_credentials", "Client Credentials"),
                         ("password",           "Password")]:
            Radiobutton(gt_row, text=lbl, variable=self.p8_grant_var, value=val,
                        bg=CARD, fg=TEXT, selectcolor=CARD,
                        activebackground=CARD, font=("Segoe UI", 8)).pack(
                side=LEFT, padx=6)
        for i, (lbl, attr, default, width, show) in enumerate([
            ("Login URL:",     "p8_login_url",    _P8_LOGIN_URL,     32, ""),
            ("API URL:",       "p8_api_url",       _P8_API_URL,       32, ""),
            ("Client ID:",     "p8_client_id",     _P8_CLIENT_ID,     20, ""),
            ("Client Secret:", "p8_client_secret", _P8_CLIENT_SECRET, 24, "*"),
            ("Username:",      "p8_user",          _P8_USERNAME,      20, ""),
            ("Password:",      "p8_pass",          _P8_PASSWORD,      20, "*"),
        ]):
            r, c = divmod(i, 2)
            r += 1
            Label(self._p8_adv_frm, text=lbl, font=("Segoe UI", 8),
                  bg=CARD, fg=DIM).grid(
                row=r, column=c * 2, padx=(0 if c == 0 else 16, 4), pady=2, sticky=W)
            var = StringVar(value=default)
            setattr(self, attr, var)
            _bind_cfg(f"p8.cfg_{attr[3:]}", var)
            Entry(self._p8_adv_frm, textvariable=var, width=width, show=show,
                  bg="#16162a", fg=TEXT, insertbackground=TEXT,
                  relief="flat", font=F_MAIN, bd=4).grid(
                row=r, column=c * 2 + 1, padx=(0, 4), pady=2)

    # ── Parkingv6 settings ────────────────────────────────────────────────────

    def _build_p6_settings(self, p):
        f = Frame(p, bg=BG, padx=10, pady=2)
        f.pack(fill=X)
        self._sep(f, "Cài đặt — Parkingv6")
        row = Frame(f, bg=BG)
        row.pack(fill=X)
        self.p6_use_minio = BooleanVar(value=True)
        _bind_cfg("p6.use_minio", self.p6_use_minio)
        Checkbutton(row, text="Dùng MinIO", variable=self.p6_use_minio,
                    bg=BG, fg=TEXT, selectcolor=CARD,
                    activebackground=BG, font=F_MAIN).grid(
            row=0, column=0, padx=(0, 20))
        Label(row, text="Nguồn SK:", bg=BG, fg=TEXT, font=F_MAIN).grid(
            row=0, column=1, padx=(20, 4))
        self.p6_event_source_var = StringVar(value="both")
        _bind_cfg("p6.event_source", self.p6_event_source_var)
        ttk.Combobox(row, textvariable=self.p6_event_source_var,
                     values=["both", "event-in", "event-out"],
                     state="readonly", width=14, font=F_MAIN).grid(
            row=0, column=4, padx=4)
        Label(row, text="both=vào+ra  ·  event-in=vào  ·  event-out=ra",
              bg=BG, fg=DIM, font=("Segoe UI", 8)).grid(
            row=0, column=5, sticky=W, padx=(4, 0))

        kw_row_p6 = Frame(f, bg=BG)
        kw_row_p6.pack(fill=X, pady=(6, 0))
        Label(kw_row_p6, text="Keyword:", bg=BG, fg=TEXT, font=F_MAIN).pack(side=LEFT, padx=(0, 6))
        self.p6_keyword_var = StringVar(value="")
        _bind_cfg("p6.keyword", self.p6_keyword_var)
        self._p6_kw_combo = ttk.Combobox(kw_row_p6, textvariable=self.p6_keyword_var,
                                          font=F_MAIN, width=40)
        self._p6_kw_combo.pack(side=LEFT)
        _bind_history("h.p6.keyword", self._p6_kw_combo)
        Label(kw_row_p6, text="Lọc sự kiện API theo biển số / nhóm thẻ  ·  bỏ trống = lấy tất cả",
              bg=BG, fg=DIM, font=("Segoe UI", 8)).pack(side=LEFT, padx=(8, 0))

        self._p6_adv_open = False
        self._p6_adv_lbl = Label(f, text="▶ Nâng cao (API / MinIO / Token)",
                                  font=("Segoe UI", 8, "underline"),
                                  fg=ACCENT2, bg=BG, cursor="hand2")
        self._p6_adv_lbl.pack(anchor=W, pady=(10, 0))
        self._p6_adv_lbl.bind("<Button-1>", lambda _: self._toggle_adv("p6"))
        self._p6_adv_frm = Frame(f, bg=CARD, padx=8, pady=6)
        for i, (lbl, attr, default, width, show) in enumerate([
            ("API URL:",        "p6_api",  _P6_API_URL,       38, ""),
            ("MinIO endpoint:", "p6_mep",  _P6_MINIO_EP,      28, ""),
            ("MinIO bucket:",   "p6_mbk",  _P6_MINIO_BUCKET,  20, ""),
            ("MinIO AK:",       "p6_mak",  _P6_MINIO_AK,      16, ""),
            ("MinIO SK:",       "p6_msk",  _P6_MINIO_SK,      20, "*"),
        ]):
            r, c = divmod(i, 2)
            Label(self._p6_adv_frm, text=lbl, font=("Segoe UI", 8),
                  bg=CARD, fg=DIM).grid(
                row=r, column=c * 2, padx=(0 if c == 0 else 16, 4), pady=2, sticky=W)
            var = StringVar(value=default)
            setattr(self, attr, var)
            _bind_cfg(f"p6.cfg_{attr[3:]}", var)
            Entry(self._p6_adv_frm, textvariable=var, width=width, show=show,
                  bg="#16162a", fg=TEXT, insertbackground=TEXT,
                  relief="flat", font=F_MAIN, bd=4).grid(
                row=r, column=c * 2 + 1, padx=(0, 4), pady=2)
        tr = (len([0, 0, 0, 0, 0]) + 1) // 2
        Label(self._p6_adv_frm, text="Bearer Token:", font=("Segoe UI", 8),
              bg=CARD, fg=DIM).grid(
            row=tr, column=0, padx=(0, 4), pady=(8, 2), sticky=W)
        self.p6_token = StringVar(value="")
        _bind_cfg("p6.cfg_token", self.p6_token)
        Entry(self._p6_adv_frm, textvariable=self.p6_token, width=60,
              bg="#16162a", fg="#4fc3f7", insertbackground=TEXT,
              relief="flat", font=F_MAIN, bd=4).grid(
            row=tr, column=1, columnspan=3, padx=(0, 4), pady=(8, 2), sticky=EW)
        Label(self._p6_adv_frm,
              text="Chỉ nhập chuỗi token, không cần 'Bearer ' prefix",
              font=("Segoe UI", 7), fg=DIM, bg=CARD).grid(
            row=tr + 1, column=0, columnspan=4, sticky=W, pady=(0, 2))

    # ── 3-phase mode controls ─────────────────────────────────────────────────

    def _build_phase_controls(self, p):
        """Thêm khu vực 3-phase (Scan → Phân tích → Tải) phía trên nút Start."""
        f = Frame(p, bg=BG, padx=10, pady=4)
        f.pack(fill=X)
        self._sep(f, "Chế độ thu thập")

        # Radio chọn mode
        mode_row = Frame(f, bg=BG)
        mode_row.pack(fill=X, pady=(2, 6))
        self.phase_mode_var = StringVar(value="auto")
        _bind_cfg("ip.phase_mode", self.phase_mode_var)
        Radiobutton(mode_row, text="Tự động (1 bước)",
                    variable=self.phase_mode_var, value="auto",
                    bg=BG, fg=TEXT, selectcolor=CARD, activebackground=BG,
                    font=F_MAIN, command=self._on_phase_mode_change).pack(
            side=LEFT, padx=(0, 16))
        Radiobutton(mode_row, text="3 bước: Scan → Phân tích → Tải",
                    variable=self.phase_mode_var, value="3step",
                    bg=BG, fg=TEXT, selectcolor=CARD, activebackground=BG,
                    font=F_MAIN, command=self._on_phase_mode_change).pack(side=LEFT)

        # Frame chứa 3 nút phase (ẩn mặc định)
        self._phase_btn_frm = Frame(f, bg=BG)
        btn_cfg = dict(font=("Segoe UI", 9, "bold"), relief="flat",
                       cursor="hand2", padx=12, pady=6)
        Button(self._phase_btn_frm, text="🔍 Xem trước",
               bg="#1a3a5c", fg="white", command=self._show_preview,
               **btn_cfg).pack(side=LEFT, padx=(0, 14))
        self.scan_btn = Button(self._phase_btn_frm, text="1. Scan sự kiện ▶",
                               bg=ACCENT2, fg="white", command=self._start_scan,
                               **btn_cfg)
        self.scan_btn.pack(side=LEFT, padx=(0, 8))
        self.analyze_btn = Button(self._phase_btn_frm, text="2. Phân tích 📊",
                                  bg="#2d5a27", fg="white",
                                  command=self._show_analysis, **btn_cfg)
        self.analyze_btn.pack(side=LEFT, padx=(0, 8))
        self.plan_dl_btn = Button(self._phase_btn_frm, text="3. Tải theo kế hoạch ▶",
                                  bg=ACCENT, fg="white",
                                  command=self._start_download_from_plan, **btn_cfg)
        self.plan_dl_btn.pack(side=LEFT)

        # DB status label
        self._db_status_lbl = Label(f, text="", bg=BG, fg=DIM,
                                    font=("Segoe UI", 8))
        self._db_status_lbl.pack(anchor=W, pady=(4, 0))

        # Target per slot
        tgt_row = Frame(f, bg=BG)
        tgt_row.pack(fill=X, pady=(4, 0))
        Label(tgt_row, text="Target ảnh/slot:", bg=BG, fg=TEXT,
              font=F_MAIN).pack(side=LEFT, padx=(0, 6))
        self.target_per_slot_var = IntVar(value=5)
        _bind_cfg("ip.target_per_slot", self.target_per_slot_var)
        Spinbox(tgt_row, from_=1, to=100, textvariable=self.target_per_slot_var,
                width=5, bg="#16162a", fg=TEXT, relief="flat", font=F_MAIN,
                buttonbackground=CARD).pack(side=LEFT)
        Label(tgt_row, text="ảnh mỗi khoảng 5 phút (dùng ở bước 3)",
              bg=BG, fg=DIM, font=("Segoe UI", 8)).pack(side=LEFT, padx=(8, 0))

        self._on_phase_mode_change()

    def _on_phase_mode_change(self):
        if getattr(self, 'phase_mode_var', None) and \
                self.phase_mode_var.get() == "3step":
            self._phase_btn_frm.pack(fill=X, pady=(4, 0))
        elif hasattr(self, '_phase_btn_frm'):
            self._phase_btn_frm.pack_forget()

    def _refresh_db_status(self):
        """Cập nhật label trạng thái DB (gọi sau mỗi lần scan xong)."""
        if not hasattr(self, '_db_status_lbl'):
            return
        out = self.out_var.get().strip() if hasattr(self, 'out_var') else ""
        if not out:
            self._db_status_lbl.config(text=""); return
        try:
            db  = self._get_or_create_db()
            src = self.source_var.get()
            src_key = {"LotteImage": "lotte", "Parkingv8": "p8",
                       "Parkingv6": "p6"}.get(src, "lotte")
            s   = db.count_summary(src_key)
            from .event_planner import EventPlanner
            planner = EventPlanner(db, src_key)
            result  = planner.analyze()
            self._db_status_lbl.config(
                text=f"DB: {s['total_scanned']} sự kiện  |  "
                     f"Đã tải: {s['downloaded']}  |  "
                     f"Chờ: {s['pending']}  |  "
                     f"Coverage: {result['coverage_pct']}% slot",
                fg=ACCENT2)
        except Exception as exc:
            self._db_status_lbl.config(text=f"DB: {exc}", fg=DIM)

    # ── Toggle advanced ───────────────────────────────────────────────────────

    def _toggle_adv(self, src: str):
        lbl_attr = f"_{src}_adv_lbl"
        frm_attr = f"_{src}_adv_frm"
        open_attr = f"_{src}_adv_open"
        lbl = getattr(self, lbl_attr)
        frm = getattr(self, frm_attr)
        is_open = getattr(self, open_attr)
        if is_open:
            frm.pack_forget()
            lbl.config(text=lbl.cget("text").replace("▼", "▶"))
        else:
            frm.pack(fill=X, pady=(2, 4))
            lbl.config(text=lbl.cget("text").replace("▶", "▼"))
        setattr(self, open_attr, not is_open)
