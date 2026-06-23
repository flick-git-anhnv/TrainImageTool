using System.Collections.Concurrent;
using System.Text.Json;
using IParkingImage.Config;
using IParkingImage.Helpers;
using IParkingImage.Models;
using IParkingImage.UI;
using IParkingImage.Workers;
using static IParkingImage.UI.Theme;

namespace IParkingImage;

public class MainForm : Form
{
    private ComboBox _cmbSource = null!;
    private Label    _lblSrcDesc = null!;
    private DateTimePicker _dtpFrom = null!, _dtpTo = null!;
    private ComboBox _cmbOutput = null!;
    private Label    _lblStructure = null!;
    private NumericUpDown _nudPageSize = null!, _nudMaxPages = null!,
                          _nudMaxLane = null!,  _nudMaxCat = null!,
                          _nudMaxBuoi = null!,  _nudParallel = null!;
    private TextBox  _txtSleep = null!;
    private CheckBox _chkOnlyGT = null!, _chkCollectBad = null!;
    private readonly Dictionary<string, CheckBox> _vtypes = new();
    private Panel    _pnlLotte = null!, _pnlP8 = null!, _pnlP6 = null!;

    // Lotte
    private CheckBox _chkLotteMinIO = null!;
    private ComboBox _cmbLotteKeyword = null!;
    private TextBox  _txtLotteKwTC = null!, _txtLotteKwMay = null!,
                     _txtLotteKwDap = null!, _txtLotteKwOTo = null!;
    private TextBox  _txtLotteApi = null!, _txtLotteUser = null!, _txtLottePass = null!;
    private TextBox  _txtLotteMep = null!, _txtLotteMbk = null!,
                     _txtLotteMAk = null!, _txtLotteMsk = null!;
    // P8
    private ComboBox   _cmbP8Src = null!, _cmbP8Grant = null!;
    private RadioButton _rbP8Url = null!, _rbP8B64 = null!;
    private ComboBox   _cmbP8Keyword = null!;
    private TextBox    _txtP8Login = null!, _txtP8Api = null!,
                       _txtP8CId = null!,  _txtP8Sec = null!,
                       _txtP8User = null!, _txtP8Pass = null!;
    // P6
    private CheckBox _chkP6MinIO = null!;
    private ComboBox _cmbP6Src = null!, _cmbP6Keyword = null!;
    private TextBox  _txtP6Api = null!, _txtP6Mep = null!, _txtP6Mbk = null!,
                     _txtP6MAk = null!, _txtP6Msk = null!, _txtP6Token = null!;

    // Bottom
    private Button _btnStart = null!, _btnStop = null!,
                   _btnPause = null!, _btnRetry = null!;
    private Label  _lblStatus = null!;
    private Panel  _pbFill = null!;
    private Label  _lblPct = null!, _lblEta = null!, _lblItem = null!, _lblStats = null!;
    private Panel  _pnlDash = null!;
    private RichTextBox _rtb = null!;

    // State
    private CancellationTokenSource? _cts;
    private BaseWorker?               _worker;
    private List<BaseWorker>          _parallelWorkers = [];
    private readonly System.Windows.Forms.Timer _pollTimer;
    private DateTime _startTime;
    private bool     _running, _paused;
    private readonly List<string>     _failedItems = [];
    private WorkerStats               _latestStats  = new();
    private readonly object           _statsLock    = new();
    private readonly ConcurrentQueue<string> _logQ  = new();

    private static readonly (string key, string label)[] _vtypeDefs =
    [
        ("toan_canh_o_to",   "Toàn cảnh ô tô"),
        ("toan_canh_xe_may", "Toàn cảnh xe máy"),
        ("toan_canh_xe_dap", "Toàn cảnh xe đạp"),
        ("toan_canh",        "Toàn cảnh"),
        ("o_to",             "Ô tô"),
        ("xe_may",           "Xe máy"),
        ("xe_dap",           "Xe đạp"),
        ("xe_tai",           "Xe tải"),
        ("o_to_bsx_cut",     "Ô tô biển cắt"),
        ("xe_may_bsx_cut",   "Xe máy biển cắt"),
        ("xe_dap_bsx_cut",   "Xe đạp biển cắt"),
    ];

    // ════════════════════════════════════════════════════════════════════
    public MainForm()
    {
        Text          = "KZTEK — iParking Image Collector";
        Size          = new Size(1150, 860);
        MinimumSize   = new Size(900, 660);
        BackColor     = BG;
        ForeColor     = Txt;
        Font          = FMain;
        StartPosition = FormStartPosition.CenterScreen;

        SettingsManager.LoadHistory();
        BuildUI();
        LoadSettings();
        _btnStart.TabIndex = 0;  // ensure bottom button gets initial focus, not scroll-area DTPs

        _pollTimer = new System.Windows.Forms.Timer { Interval = 150 };
        _pollTimer.Tick += OnPollTick;
        _pollTimer.Start();
        FormClosing += (s, e) => { SaveSettings(); SettingsManager.SaveHistory(); };
    }

    // ════════════════════════════════════════════════════════════════════
    //  Build UI
    // ════════════════════════════════════════════════════════════════════
    private void BuildUI()
    {
        SuspendLayout();

        // ── Header bar ──────────────────────────────────────────────────
        var hdrPanel = new Panel { Height = 50, Dock = DockStyle.Top, BackColor = Card };
        var titleLbl = new Label {
            Text = "iParking Image — Thu thập ảnh từ hệ thống iParking",
            Dock = DockStyle.Left, ForeColor = Txt, Font = FBold,
            TextAlign = ContentAlignment.MiddleLeft, AutoSize = false, Width = 480,
        };
        _lblSrcDesc = new Label { Dock = DockStyle.Fill, ForeColor = Dim, Font = FSm, TextAlign = ContentAlignment.MiddleLeft };
        var srcPnl = new Panel { Dock = DockStyle.Right, Width = 320, BackColor = Card };
        var srcLbl = Lbl("Nguồn dữ liệu:", FBold); srcLbl.Location = new Point(8, 14);
        _cmbSource = Cmb(["LotteImage", "Parkingv8", "Parkingv6"], "LotteImage", true);
        _cmbSource.Width = 160; _cmbSource.Location = new Point(srcLbl.Right + 6, 12);
        _cmbSource.SelectedIndexChanged += (s, e) => OnSourceChange();
        srcPnl.Controls.Add(srcLbl); srcPnl.Controls.Add(_cmbSource);
        hdrPanel.Controls.Add(_lblSrcDesc);
        hdrPanel.Controls.Add(srcPnl);
        hdrPanel.Controls.Add(titleLbl);
        Controls.Add(hdrPanel);

        // ── Fixed bottom ────────────────────────────────────────────────
        var bottom = new Panel { Dock = DockStyle.Bottom, Height = 290, BackColor = BG };
        BuildBottomArea(bottom);
        Controls.Add(bottom);

        // ── Scrollable settings (NoFocusScrollPanel prevents focus-triggered scroll) ──────
        var scrollPnl = new NoFocusScrollPanel { Dock = DockStyle.Fill, AutoScroll = true, BackColor = BG };
        var inner     = new Panel { BackColor = BG, Location = new Point(0, 0) };

        bool _innerHLock = false;
        void RefreshInnerH() {
            if (_innerHLock) return; _innerHLock = true;
            try {
                inner.Height = Math.Max(10,
                    inner.Controls.Cast<Control>().Where(c => c.Visible)
                    .Sum(c => c.Height + c.Margin.Vertical));
            } finally { _innerHLock = false; }
        }
        scrollPnl.Resize += (s, e) => {
            int w = scrollPnl.ClientSize.Width;
            if (w > 0) inner.Width = w;
            RefreshInnerH();
        };
        inner.Layout += (s, e) => RefreshInnerH();

        // Dock=Top: last added = topmost — add in reverse visual order
        _pnlLotte = MakeSource(BuildLotteContent);
        _pnlP8    = MakeSource(BuildP8Content);
        _pnlP6    = MakeSource(BuildP6Content);
        inner.Controls.Add(_pnlP6);    // hidden; bottom of stack
        inner.Controls.Add(_pnlP8);    // hidden
        inner.Controls.Add(_pnlLotte); // shown per source; below sections

        AddSection(inner, "  Loại ảnh lấy",            BuildVTypeContent);   // section 4
        AddSection(inner, "  Cài đặt chung",            BuildCommonContent);  // section 3
        AddSection(inner, "  Thư mục lưu ảnh",          BuildOutputContent);  // section 2
        AddSection(inner, "  Khoảng thời gian (UTC)",   BuildTimeContent);    // section 1 → topmost

        scrollPnl.Controls.Add(inner);
        Controls.Add(scrollPnl);

        ResumeLayout(true);
        OnSourceChange();

        // After form is fully shown, reset scroll to top (prevents initial focus-triggered scroll)
        Shown += (s, e) => scrollPnl.AutoScrollPosition = new Point(0, 0);
    }

    private void AddSection(Panel inner, string title, Action<FlowLayoutPanel> build)
    {
        var body = new FlowLayoutPanel {
            FlowDirection = FlowDirection.TopDown, WrapContents = false,
            AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink,
            BackColor = BG, Padding = new Padding(10, 4, 10, 4),
            Dock = DockStyle.Top,
        };
        build(body);

        var hdr = new Panel { Height = 24, BackColor = Navy, Dock = DockStyle.Top };
        hdr.Controls.Add(new Label {
            Text = title, Dock = DockStyle.Fill, ForeColor = Color.White,
            Font = FSmB, TextAlign = ContentAlignment.MiddleLeft, BackColor = Color.Transparent,
        });

        // Dock=Top: last added = topmost. body first → bottom; hdr second → top.
        var wrap = new Panel { Dock = DockStyle.Top, BackColor = BG, Margin = new Padding(0, 4, 0, 2) };
        wrap.Controls.Add(body);
        wrap.Controls.Add(hdr);

        void SyncWrap() => wrap.Height = hdr.Height + body.Height;
        body.Resize += (s, e) => SyncWrap();
        SyncWrap();

        inner.Controls.Add(wrap);
    }

    // ════════════════════════════════════════════════════════════════════
    //  Section content builders — parameter is FlowLayoutPanel(TopDown)
    // ════════════════════════════════════════════════════════════════════

    private void BuildTimeContent(FlowLayoutPanel p)
    {
        var row = Row();
        _dtpFrom = new DateTimePicker { Format = DateTimePickerFormat.Custom, CustomFormat = "yyyy-MM-dd HH:mm:ss", Width = 188, BackColor = Card, CalendarForeColor = Txt };
        _dtpTo   = new DateTimePicker { Format = DateTimePickerFormat.Custom, CustomFormat = "yyyy-MM-dd HH:mm:ss", Width = 188, BackColor = Card, CalendarForeColor = Txt };
        _dtpFrom.Value = DateTime.Now.AddMonths(-1);
        _dtpTo.Value   = DateTime.Now;
        row.Controls.Add(Lbl("Từ:"));
        row.Controls.Add(_dtpFrom);
        row.Controls.Add(Lbl("  Đến:"));
        row.Controls.Add(_dtpTo);
        row.Controls.Add(Lbl("  (UTC — Việt Nam = UTC+7)", FSm, Dim));
        p.Controls.Add(row);
    }

    private void BuildOutputContent(FlowLayoutPanel p)
    {
        var row1 = Row();
        _cmbOutput = new ComboBox { Width = 550, BackColor = Card, ForeColor = Txt, Font = FMain };
        _cmbOutput.KeyDown += (s, e) => { if (e.KeyCode == Keys.Return) SettingsManager.PushHistory("ip.out", _cmbOutput.Text.Trim()); };
        SettingsManager.BindHistory(_cmbOutput, "ip.out");
        var btnBrowse = Btn("Chọn…", Navy);
        btnBrowse.Click += OnBrowseOutput;
        var btnOpen = Btn("📂", Card);
        btnOpen.Click += (s, e) => { var d = _cmbOutput.Text.Trim(); if (Directory.Exists(d)) System.Diagnostics.Process.Start("explorer.exe", d); };
        row1.Controls.Add(_cmbOutput); row1.Controls.Add(btnBrowse); row1.Controls.Add(btnOpen);
        p.Controls.Add(row1);

        _lblStructure = Lbl("", FSm, Dim);
        _lblStructure.AutoSize = true;
        p.Controls.Add(_lblStructure);
    }

    private void BuildCommonContent(FlowLayoutPanel p)
    {
        var r1 = Row();
        _nudPageSize  = Num(10, 500,    100, 68);
        _nudMaxPages  = Num(1, 99999, 10000, 80);
        _txtSleep     = Txt2("0.1", 52);
        _nudMaxLane   = Num(0, 999999, 1000, 80);
        _nudMaxCat    = Num(0, 999999,    0, 80);
        _nudMaxBuoi   = Num(0, 99999,     0, 80);
        foreach (var (lbl, ctrl) in new (string, Control)[] {
            ("Page size:", _nudPageSize), ("Max pages:", _nudMaxPages), ("Nghỉ (s):", _txtSleep),
            ("Max SK/làn:", _nudMaxLane), ("Max SK/loại:", _nudMaxCat), ("Max SK/buổi:", _nudMaxBuoi) })
        { r1.Controls.Add(Lbl(lbl)); r1.Controls.Add(ctrl); r1.Controls.Add(new Label { Width = 4 }); }
        p.Controls.Add(r1);

        var r2 = Row();
        _nudParallel = Num(1, 16, 1, 52);
        _chkOnlyGT   = Chk("Chỉ lấy ảnh có GT  (biển vào = biển ra hoặc có đăng ký)");
        r2.Controls.Add(Lbl("Luồng song song:")); r2.Controls.Add(_nudParallel);
        r2.Controls.Add(new Label { Width = 16 }); r2.Controls.Add(_chkOnlyGT);
        p.Controls.Add(r2);

        p.Controls.Add(Lbl("Max SK/làn: tổng cả lần chạy  ·  Max SK/loại: tối đa/ngày/loại/làn  ·  Max SK/buổi: trải đều sáng-trưa-chiều-tối  ·  0 = không giới hạn", FSm, Dim));
    }

    private void BuildVTypeContent(FlowLayoutPanel p)
    {
        var btnRow = Row();
        var bAll  = Btn("✔ Chọn tất cả", Card);
        var bNone = Btn("✘ Bỏ tất cả", Card);
        bAll.Click  += (s, e) => { foreach (var c in _vtypes.Values) c.Checked = true; };
        bNone.Click += (s, e) => { foreach (var c in _vtypes.Values) c.Checked = false; };
        btnRow.Controls.Add(bAll); btnRow.Controls.Add(bNone);
        p.Controls.Add(btnRow);

        var grid = new TableLayoutPanel {
            ColumnCount = 4, AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink,
            BackColor = BG,
        };
        for (int i = 0; i < 4; i++) grid.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 25f));
        for (int i = 0; i < _vtypeDefs.Length; i++)
        {
            var (key, label) = _vtypeDefs[i];
            var chk = Chk(label, true);
            _vtypes[key] = chk;
            grid.Controls.Add(chk, i % 4, i / 4);
        }
        p.Controls.Add(grid);
    }

    // ── Source panels: built directly into host (TableLayoutPanel style) ──

    private void BuildLotteContent(FlowLayoutPanel p)
    {
        var hdr = SectionHeader("  Cài đặt — LotteImage"); hdr.Height = 24; hdr.AutoSize = false;
        p.Controls.Add(hdr);

        var body = new FlowLayoutPanel { FlowDirection = FlowDirection.TopDown, WrapContents = false, AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink, BackColor = BG, Padding = new Padding(10, 4, 10, 6) };

        _chkLotteMinIO = Chk("Dùng MinIO", true);
        body.Controls.Add(Row(_chkLotteMinIO));

        _cmbLotteKeyword = Cmb([], ""); _cmbLotteKeyword.Width = 340;
        SettingsManager.BindHistory(_cmbLotteKeyword, "h.lotte.keyword");
        body.Controls.Add(Row(Lbl("Keyword:"), _cmbLotteKeyword, Lbl("  Lọc theo biển số / tên thẻ  ·  bỏ trống = lấy tất cả", FSm, Dim)));

        body.Controls.Add(Lbl("Phân loại phương tiện (từ khóa):", FSmB));
        foreach (var (lbl, attr, def) in new (string, string, string)[] {
            ("Toàn cảnh (mô tả ảnh):", "tc", "toàn cảnh"),
            ("Xe máy (nhóm thẻ):",      "may","xe máy"),
            ("Xe đạp (nhóm thẻ):",      "dap","xe đạp"),
            ("Ô tô (nhóm thẻ):",        "oto",""),
        })
        {
            var txt = Txt2(def, 280);
            if (attr == "tc")  _txtLotteKwTC  = txt;
            if (attr == "may") _txtLotteKwMay = txt;
            if (attr == "dap") _txtLotteKwDap = txt;
            if (attr == "oto") _txtLotteKwOTo = txt;
            body.Controls.Add(Row(Lbl(lbl), txt));
        }

        body.Controls.Add(BuildCollapsible("▶ Nâng cao (API / MinIO)", adv =>
        {
            _txtLotteApi  = Txt2(_LI_Const.ApiBase, 360);
            _txtLotteUser = Txt2(_LI_Const.Username, 150);
            _txtLottePass = Txt2(_LI_Const.Password, 150, true);
            _txtLotteMep  = Txt2(_LI_Const.MinioEp, 220);
            _txtLotteMbk  = Txt2(_LI_Const.MinioBkt, 160);
            _txtLotteMAk  = Txt2(_LI_Const.MinioAk, 150);
            _txtLotteMsk  = Txt2(_LI_Const.MinioSk, 150, true);
            foreach (var (lbl, ctrl) in new (string, Control)[] {
                ("API URL:", _txtLotteApi), ("Username:", _txtLotteUser), ("Password:", _txtLottePass),
                ("MinIO endpoint:", _txtLotteMep), ("MinIO bucket:", _txtLotteMbk),
                ("MinIO AK:", _txtLotteMAk), ("MinIO SK:", _txtLotteMsk) })
            { adv.Controls.Add(Row(Lbl(lbl, FSm, Dim), ctrl)); }
        }));

        p.Controls.Add(body);
    }

    private void BuildP8Content(FlowLayoutPanel p)
    {
        var hdr = SectionHeader("  Cài đặt — Parkingv8"); hdr.Height = 24; hdr.AutoSize = false;
        p.Controls.Add(hdr);

        var body = new FlowLayoutPanel { FlowDirection = FlowDirection.TopDown, WrapContents = false, AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink, BackColor = BG, Padding = new Padding(10, 4, 10, 6) };

        _cmbP8Src = Cmb(["exits", "entries", "both"], "exits", true);
        _rbP8Url  = Rad("URL (PresignedUrl)", true);
        _rbP8B64  = Rad("Base64");
        body.Controls.Add(Row(Lbl("Nguồn SK:"), _cmbP8Src, Lbl("  Ảnh:"), _rbP8Url, _rbP8B64, Lbl("  exits=ra  ·  entries=vào  ·  both=cả hai", FSm, Dim)));

        _cmbP8Keyword = Cmb([], ""); _cmbP8Keyword.Width = 340;
        SettingsManager.BindHistory(_cmbP8Keyword, "h.p8.keyword");
        body.Controls.Add(Row(Lbl("Keyword:"), _cmbP8Keyword, Lbl("  Lọc theo biển số / mã thẻ  ·  bỏ trống = lấy tất cả", FSm, Dim)));

        body.Controls.Add(BuildCollapsible("▶ Nâng cao (API / Xác thực)", adv =>
        {
            _cmbP8Grant = Cmb(["client_credentials", "password"], "client_credentials", true); _cmbP8Grant.Width = 180;
            adv.Controls.Add(Row(Lbl("Grant type:", FSm, Dim), _cmbP8Grant));
            _txtP8Login = Txt2("", 320); _txtP8Api = Txt2("", 320);
            _txtP8CId   = Txt2("", 180); _txtP8Sec = Txt2("", 180, true);
            _txtP8User  = Txt2("", 180); _txtP8Pass = Txt2("", 180, true);
            foreach (var (lbl, ctrl) in new (string, Control)[] {
                ("Login URL:", _txtP8Login), ("API URL:", _txtP8Api),
                ("Client ID:", _txtP8CId),   ("Client Secret:", _txtP8Sec),
                ("Username:",  _txtP8User),  ("Password:", _txtP8Pass) })
            { adv.Controls.Add(Row(Lbl(lbl, FSm, Dim), ctrl)); }
        }));

        p.Controls.Add(body);
    }

    private void BuildP6Content(FlowLayoutPanel p)
    {
        var hdr = SectionHeader("  Cài đặt — Parkingv6"); hdr.Height = 24; hdr.AutoSize = false;
        p.Controls.Add(hdr);

        var body = new FlowLayoutPanel { FlowDirection = FlowDirection.TopDown, WrapContents = false, AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink, BackColor = BG, Padding = new Padding(10, 4, 10, 6) };

        _chkP6MinIO = Chk("Dùng MinIO", true);
        _cmbP6Src   = Cmb(["both", "event-in", "event-out"], "both", true); _cmbP6Src.Width = 140;
        body.Controls.Add(Row(_chkP6MinIO, new Label { Width = 16 }, Lbl("Nguồn SK:"), _cmbP6Src, Lbl("  both=vào+ra  ·  event-in=vào  ·  event-out=ra", FSm, Dim)));

        _cmbP6Keyword = Cmb([], ""); _cmbP6Keyword.Width = 340;
        SettingsManager.BindHistory(_cmbP6Keyword, "h.p6.keyword");
        body.Controls.Add(Row(Lbl("Keyword:"), _cmbP6Keyword, Lbl("  Lọc theo biển số / nhóm thẻ  ·  bỏ trống = lấy tất cả", FSm, Dim)));

        body.Controls.Add(BuildCollapsible("▶ Nâng cao (API / MinIO / Token)", adv =>
        {
            _txtP6Api = Txt2("", 320); _txtP6Mep = Txt2("", 220);
            _txtP6Mbk = Txt2("", 160); _txtP6MAk = Txt2("", 150);
            _txtP6Msk = Txt2("", 150, true);
            foreach (var (lbl, ctrl) in new (string, Control)[] {
                ("API URL:", _txtP6Api), ("MinIO endpoint:", _txtP6Mep),
                ("MinIO bucket:", _txtP6Mbk), ("MinIO AK:", _txtP6MAk), ("MinIO SK:", _txtP6Msk) })
            { adv.Controls.Add(Row(Lbl(lbl, FSm, Dim), ctrl)); }
            _txtP6Token = Txt2("", 500);
            _txtP6Token.ForeColor = Color.FromArgb(79, 195, 247);
            adv.Controls.Add(Row(Lbl("Bearer Token:", FSm, Dim), _txtP6Token));
            adv.Controls.Add(Lbl("Chỉ nhập chuỗi token, không cần 'Bearer ' prefix", FSm, Dim));
        }));

        p.Controls.Add(body);
    }

    private Panel MakeSource(Action<FlowLayoutPanel> build)
    {
        var host = new FlowLayoutPanel {
            FlowDirection = FlowDirection.TopDown, WrapContents = false,
            AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink,
            BackColor = BG, Visible = false, Dock = DockStyle.Top,
        };
        build(host);
        return host;
    }

    // ── Row helpers ──────────────────────────────────────────────────────
    private static FlowLayoutPanel Row(params Control[] controls)
    {
        var r = new FlowLayoutPanel {
            FlowDirection = FlowDirection.LeftToRight, WrapContents = true,
            AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink,
            BackColor = Color.Transparent, Margin = new Padding(0, 2, 0, 2),
        };
        foreach (var c in controls) r.Controls.Add(c);
        return r;
    }

    // ── Collapsible ──────────────────────────────────────────────────────
    private Control BuildCollapsible(string title, Action<FlowLayoutPanel> buildBody)
    {
        var container = new FlowLayoutPanel {
            FlowDirection = FlowDirection.TopDown, WrapContents = false,
            AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink,
            BackColor = BG,
        };
        var togBtn = new LinkLabel { Text = title, AutoSize = true, Font = FSm, LinkColor = Navy, ActiveLinkColor = Accent };
        var body   = new FlowLayoutPanel {
            FlowDirection = FlowDirection.TopDown, WrapContents = false,
            AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink,
            BackColor = Card, Padding = new Padding(8, 6, 8, 6), Visible = false,
        };
        buildBody(body);
        togBtn.LinkClicked += (s, e) => {
            body.Visible = !body.Visible;
            togBtn.Text = body.Visible ? title.Replace("▶", "▼") : title.Replace("▼", "▶");
        };
        container.Controls.Add(togBtn);
        container.Controls.Add(body);
        return container;
    }

    // ── Bottom area ──────────────────────────────────────────────────────
    private void BuildBottomArea(Panel bottom)
    {
        var tbl = new TableLayoutPanel {
            Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 3, BackColor = BG,
        };
        tbl.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100f));
        tbl.RowStyles.Add(new RowStyle(SizeType.Percent, 100f));   // row 0: log (fills)
        tbl.RowStyles.Add(new RowStyle(SizeType.Absolute, 60f));   // row 1: progress
        tbl.RowStyles.Add(new RowStyle(SizeType.Absolute, 44f));   // row 2: controls

        // ── Log area (row 0) ─────────────────────────────────────────────
        var logPnl = new Panel { Dock = DockStyle.Fill, BackColor = BG };
        var logHdr = new Panel { Dock = DockStyle.Top, Height = 22, BackColor = BG };
        logHdr.Controls.Add(Lbl("  Nhật ký", FSmB, Navy));
        var btnClrLog = Btn("Xóa log", Card); btnClrLog.Font = FSm; btnClrLog.Height = 20;
        btnClrLog.Dock = DockStyle.Right;
        btnClrLog.Click += (s, e) => _rtb.Clear();
        logHdr.Controls.Add(btnClrLog);

        _rtb = new RichTextBox {
            Dock = DockStyle.Fill, BackColor = Deep, ForeColor = Color.FromArgb(212, 212, 212),
            Font = FMono, ReadOnly = true, BorderStyle = BorderStyle.None,
            ScrollBars = RichTextBoxScrollBars.Vertical,
        };
        logPnl.Controls.Add(_rtb);
        logPnl.Controls.Add(logHdr);   // Dock.Top → logHdr at top, _rtb fills rest
        tbl.Controls.Add(logPnl, 0, 0);

        // ── Progress area (row 1) ────────────────────────────────────────
        var progPnl = new Panel { Dock = DockStyle.Fill, BackColor = BG, Padding = new Padding(8, 2, 8, 2) };

        _lblStats = Lbl("Trang: 0  |  SK: 0  |  Tìm: 0  |  Lưu: 0  |  Bỏ: 0  |  Lỗi: 0", FMono);
        _lblStats.Dock = DockStyle.Top;

        _lblItem = Lbl("", FSm, Dim); _lblItem.Dock = DockStyle.Top;

        var pbRow = new Panel { Dock = DockStyle.Bottom, Height = 20 };
        var pbTrack = new Panel { Dock = DockStyle.Fill, BackColor = Card };
        _pbFill = new Panel { Location = new Point(0, 0), Width = 0, Height = 20, BackColor = Accent };
        pbTrack.Controls.Add(_pbFill);
        pbTrack.Resize += (s, e) => { if (_lastProgress > 0) _pbFill.Width = (int)(pbTrack.Width * _lastProgress / 100.0); };
        _lblPct = Lbl("0%", FBold, Accent); _lblPct.Dock = DockStyle.Right; _lblPct.Width = 40; _lblPct.TextAlign = ContentAlignment.MiddleCenter;
        _lblEta = Lbl("ETA: --:--", FMono, Dim); _lblEta.Dock = DockStyle.Right; _lblEta.Width = 88; _lblEta.TextAlign = ContentAlignment.MiddleRight;
        pbRow.Controls.Add(pbTrack); pbRow.Controls.Add(_lblPct); pbRow.Controls.Add(_lblEta);

        progPnl.Controls.Add(_lblItem);
        progPnl.Controls.Add(_lblStats);
        progPnl.Controls.Add(pbRow);
        tbl.Controls.Add(progPnl, 0, 1);

        // ── Controls row (row 2) ─────────────────────────────────────────
        var ctrlPnl = new Panel { Dock = DockStyle.Fill, BackColor = BG, Padding = new Padding(8, 4, 8, 4) };
        _btnStart = Btn("▶  Bắt đầu",  Accent);
        _btnStop  = Btn("⬛  Dừng",     Dim);    _btnStop.Enabled = false;
        _btnPause = Btn("⏸  Tạm dừng", Card);   _btnPause.Enabled = false;
        _btnRetry = Btn("↺  Thử lại lỗi", Card); _btnRetry.Enabled = false;
        var btnStats = Btn("Thống kê", Navy);
        _chkCollectBad = Chk("Lấy ảnh xấu");
        var btnBad    = Btn("Xem ảnh xấu", Navy);
        var btnConsolid = Btn("Tổng hợp", NavyDk);
        var btnClrProg  = Btn("🗑 Xóa tiến độ", Color.FromArgb(58, 26, 26));
        _lblStatus = Lbl("Sẵn sàng", null, Navy);

        _btnStart.Click += (s, e) => OnStart();
        _btnStop.Click  += (s, e) => OnStop();
        _btnPause.Click += (s, e) => OnPause();
        _btnRetry.Click += (s, e) => OnRetry();
        btnStats.Click  += (s, e) => ShowStats();
        btnBad.Click    += (s, e) => ShowBadImages();
        btnConsolid.Click   += (s, e) => ShowConsolidate();
        btnClrProg.Click    += (s, e) => ClearProgress();

        var flp = new FlowLayoutPanel { Dock = DockStyle.Fill, FlowDirection = FlowDirection.LeftToRight, WrapContents = true, BackColor = BG };
        foreach (Control c in new Control[] { _btnStart, _btnStop, _btnPause, _btnRetry, btnStats, _chkCollectBad, btnBad, btnConsolid, btnClrProg, _lblStatus })
            flp.Controls.Add(c);
        ctrlPnl.Controls.Add(flp);
        tbl.Controls.Add(ctrlPnl, 0, 2);

        bottom.Controls.Add(tbl);

        // Dashboard panel (hidden initially)
        _pnlDash = new Panel { Height = 0, Dock = DockStyle.Top, BackColor = Card, Visible = false };
        bottom.Controls.Add(_pnlDash);
    }

    private double _lastProgress = 0;

    // ════════════════════════════════════════════════════════════════════
    //  Source switch
    // ════════════════════════════════════════════════════════════════════
    private void OnSourceChange()
    {
        var src = _cmbSource.Text;
        _pnlLotte.Visible = src == "LotteImage";
        _pnlP8.Visible    = src == "Parkingv8";
        _pnlP6.Visible    = src == "Parkingv6";

        (_lblSrcDesc.Text, _lblStructure.Text) = src switch {
            "Parkingv8" => ("iParking v8 · vehicleType integer · có ảnh cắt biển số (*_bsx_cut)",
                            "Cấu trúc: <out>/<loai_xe>/anh_xe|anh_toan_canh|anh_bsx/<date>/<buoi>/<lan>/HHmmss_BSX.jpg"),
            "Parkingv6" => ("iParking v6 · vehicleType integer · MinIO fileKeys · Bearer token",
                            "Cấu trúc: <out>/<loai_xe>/anh_xe|anh_toan_canh|anh_bsx/<date>/<buoi>/<lan>/HHmmss_BSX.jpg"),
            _           => ("iParking Lotte · phân loại theo từ khóa · không có ảnh cắt biển số",
                            "Cấu trúc: <out>/<loai_xe>/anh_xe|anh_toan_canh/<date>/<buoi>/<lan>/HHmmss_BSX.jpg"),
        };
    }

    // ════════════════════════════════════════════════════════════════════
    //  Worker management
    // ════════════════════════════════════════════════════════════════════
    private void OnStart()
    {
        if (_running) return;
        var cfg = GetConfig();
        if (!ValidateConfig(cfg)) return;
        try { Directory.CreateDirectory(cfg.OutputDir); }
        catch (Exception ex) { MessageBox.Show("Lỗi thư mục: " + ex.Message, "Lỗi", MessageBoxButtons.OK, MessageBoxIcon.Error); return; }

        SaveSettings();
        _failedItems.Clear();
        _parallelWorkers.Clear();
        HideDashboard();

        _cts = new CancellationTokenSource();
        _running = true; _paused = false;

        _btnStart.Enabled = false; _btnStop.Enabled = true; _btnPause.Enabled = true; _btnRetry.Enabled = false;
        _lblStatus.Text = "Đang chạy..."; _lblStatus.ForeColor = Accent;
        _startTime = DateTime.Now;

        Action<string> logAct = msg => _logQ.Enqueue(msg);
        Action<WorkerStats> progressAct = stats => { lock (_statsLock) _latestStats = stats; };
        var shared = new LaneCounters();
        var token  = _cts.Token;
        int n = (int)_nudParallel.Value;

        if (n > 1)
        {
            _ = Task.Run(async () => {
                try { await RunParallelAsync(cfg, logAct, progressAct, shared, n, token); }
                catch (OperationCanceledException) { }
                catch (Exception ex) { _logQ.Enqueue($"[ERR]  {ex.Message}"); }
                finally { _logQ.Enqueue("__DONE__"); }
            }, token);
        }
        else
        {
            _worker = CreateWorker(cfg, logAct, progressAct, shared);
            _ = Task.Run(async () => {
                try { await _worker.RunAsync(token); }
                catch (OperationCanceledException) { }
                catch (Exception ex) { _logQ.Enqueue($"[ERR]  {ex.Message}"); }
                finally { _logQ.Enqueue("__DONE__"); }
            }, token);
        }
    }

    private async Task RunParallelAsync(AppConfig cfg, Action<string> log,
        Action<WorkerStats> progress, LaneCounters shared, int n, CancellationToken ct)
    {
        var days   = FileHelper.BuildDayList(cfg.FromDate, cfg.ToDate);
        var groups = Enumerable.Range(0, n).Select(_ => new List<DayRange>()).ToList();
        for (int i = 0; i < days.Count; i++) groups[i % n].Add(days[i]);
        log($"[INFO] Parallel: {n} luồng | {days.Count} ngày");

        var workers = new List<BaseWorker>();
        var tasks   = new List<Task>();
        for (int t = 0; t < n; t++)
        {
            if (groups[t].Count == 0) continue;
            int tid = t + 1;
            var grpCfg = CloneCfg(cfg, groups[t]);
            Action<string> tLog = msg => log($"[T{tid}] {msg}");
            var w = CreateWorker(grpCfg, tLog, progress, shared);
            workers.Add(w); _parallelWorkers.Add(w);
            tasks.Add(Task.Run(() => w.RunAsync(ct), ct));
        }
        await Task.WhenAll(tasks);
        var total = new WorkerStats();
        foreach (var w in workers) total.Add(w.Stats);
        log($"[INFO] TỔNG KẾT ({n} luồng): {total}");
    }

    private static AppConfig CloneCfg(AppConfig src, List<DayRange> days)
    {
        var cloned = JsonSerializer.Deserialize<AppConfig>(JsonSerializer.Serialize(src))!;
        cloned.FromDate = days.First().Start.ToString("yyyy-MM-dd HH:mm:ss");
        cloned.ToDate   = days.Last().End.ToString("yyyy-MM-dd HH:mm:ss");
        return cloned;
    }

    private BaseWorker CreateWorker(AppConfig cfg, Action<string> log, Action<WorkerStats> progress, LaneCounters shared) =>
        cfg.Source switch {
            "Parkingv8" => new Parkingv8Worker(cfg, log, progress, shared),
            "Parkingv6" => new Parkingv6Worker(cfg, log, progress, shared),
            _           => new LotteWorker(cfg, log, progress, shared),
        };

    private void OnStop()
    {
        _cts?.Cancel(); _worker?.Stop();
        foreach (var w in _parallelWorkers) w.Stop();
        SetStopped("Đã dừng", Dim);
    }

    private void OnPause()
    {
        if (!_running) return;
        if (_paused)
        {
            _paused = false; _worker?.Resume(); foreach (var w in _parallelWorkers) w.Resume();
            _btnPause.Text = "⏸  Tạm dừng"; _lblStatus.Text = "Đang chạy..."; _lblStatus.ForeColor = Accent;
        }
        else
        {
            _paused = true; _worker?.Pause(); foreach (var w in _parallelWorkers) w.Pause();
            _btnPause.Text = "▶  Tiếp tục"; _lblStatus.Text = "Tạm dừng"; _lblStatus.ForeColor = Warn;
        }
    }

    private void OnRetry() => MessageBox.Show("Tính năng Thử lại đang phát triển.", "Thông báo", MessageBoxButtons.OK, MessageBoxIcon.Information);

    private void SetStopped(string status, Color color)
    {
        _running = false; _paused = false;
        _btnStart.Enabled = true; _btnStop.Enabled = false; _btnPause.Enabled = false;
        _btnPause.Text = "⏸  Tạm dừng"; _lblStatus.Text = status; _lblStatus.ForeColor = color;
    }

    private void OnDone()
    {
        if (!_running) return;
        SetStopped("Hoàn thành", Ok);
        SetProgress(100); _lblEta.Text = "ETA: 00:00";
        WorkerStats s; lock (_statsLock) s = _latestStats;
        ShowDashboard(s);
    }

    // ════════════════════════════════════════════════════════════════════
    //  Poll timer
    // ════════════════════════════════════════════════════════════════════
    private void OnPollTick(object? sender, EventArgs e)
    {
        int count = 0;
        while (_logQ.TryDequeue(out var msg) && count++ < 200)
        {
            if (msg == "__DONE__") { OnDone(); break; }
            AppendLog(msg);
        }
        if (_running) { WorkerStats s; lock (_statsLock) s = _latestStats; UpdateProgressUI(s); }
    }

    private void AppendLog(string msg)
    {
        if (_rtb.IsDisposed) return;
        Color c = msg.Contains("[OK]")   ? Ok
                : msg.Contains("[ERR]")  ? Err
                : msg.Contains("[SKIP]") ? Dim
                : msg.Contains("[WARN]") ? Warn
                : Txt;
        var ts = DateTime.Now.ToString("HH:mm:ss");
        _rtb.SelectionStart = _rtb.TextLength; _rtb.SelectionLength = 0;
        _rtb.SelectionColor = c;
        _rtb.AppendText($"[{ts}] {msg}\n");
        _rtb.SelectionColor = _rtb.ForeColor;
        if (_rtb.Lines.Length > 2000) { int t = _rtb.GetFirstCharIndexFromLine(500); _rtb.Select(0, t); _rtb.SelectedText = ""; }
        _rtb.ScrollToCaret();
    }

    private void UpdateProgressUI(WorkerStats s)
    {
        if (s.Found > 0)
        {
            int pct = Math.Min((int)(s.Saved * 100.0 / s.Found), 99);
            SetProgress(pct);
            double el = (DateTime.Now - _startTime).TotalSeconds;
            if (s.Saved > 0) { double eta = el / s.Saved * (s.Found - s.Saved); _lblEta.Text = $"ETA: {(int)(eta/60):00}:{(int)(eta%60):00}"; }
        }
        else if (s.Page > 0) SetProgress(s.Page % 100);

        if (!string.IsNullOrEmpty(s.CurrentItem)) _lblItem.Text = $"Đang xử lý: {s.CurrentItem}";
        string dayInfo = s.TotalDays > 0 ? $"Ngày: {s.DayLabel} ({s.DayIdx}/{s.TotalDays})  |  " : "";
        string badPart = s.BadSaved > 0 ? $"  |  Xấu: {s.BadSaved}" : "";
        _lblStats.Text = $"{dayInfo}Trang: {s.Page}  |  SK: {s.Event}  |  Tìm: {s.Found}  |  Lưu: {s.Saved}{badPart}  |  Bỏ: {s.Skipped}  |  Lỗi: {s.Error}";
    }

    private void SetProgress(int pct)
    {
        _lastProgress = pct;
        if (_pbFill.Parent is Panel track) _pbFill.Width = (int)(track.Width * pct / 100.0);
        _lblPct.Text = $"{pct}%";
    }

    // ════════════════════════════════════════════════════════════════════
    //  Dashboard
    // ════════════════════════════════════════════════════════════════════
    private void ShowDashboard(WorkerStats s)
    {
        _pnlDash.Visible = true; _pnlDash.Height = 52;
        foreach (Control c in _pnlDash.Controls.Cast<Control>().ToList()) c.Dispose();
        _pnlDash.Controls.Clear();
        var row = new FlowLayoutPanel { Dock = DockStyle.Fill, BackColor = Card, FlowDirection = FlowDirection.LeftToRight };
        foreach (var (label, val, color) in new (string, int, Color)[] {
            ("Tổng SK",  s.Event,    Txt), ("Tìm thấy", s.Found,    Txt),
            ("Đã lưu",   s.Saved,    Ok),  ("Bỏ qua",   s.Skipped,  Dim),
            ("Lỗi",      s.Error,    Err), ("Ảnh xấu",  s.BadSaved, Navy) })
        {
            var cell = new Panel { Width = 100, Height = 50, BackColor = NavyDk, Margin = new Padding(2) };
            cell.Controls.Add(new Label { Text = label, Font = FSm, ForeColor = Dim, Dock = DockStyle.Bottom, TextAlign = ContentAlignment.MiddleCenter, Height = 16 });
            cell.Controls.Add(new Label { Text = val.ToString(), Font = new Font("Segoe UI Semibold", 13f), ForeColor = color, Dock = DockStyle.Fill, TextAlign = ContentAlignment.MiddleCenter });
            row.Controls.Add(cell);
        }
        _pnlDash.Controls.Add(row);
    }

    private void HideDashboard() { _pnlDash.Visible = false; _pnlDash.Height = 0; }

    // ════════════════════════════════════════════════════════════════════
    //  Misc actions
    // ════════════════════════════════════════════════════════════════════
    private void ShowStats()
    {
        var d = _cmbOutput.Text.Trim();
        if (!Directory.Exists(d)) { MessageBox.Show("Thư mục không tồn tại.", "Thông báo", MessageBoxButtons.OK, MessageBoxIcon.Information); return; }
        new Forms.StatsForm(d).Show(this);
    }

    private void ShowBadImages()
    {
        var bad = Path.Combine(_cmbOutput.Text.Trim(), "bad");
        if (!Directory.Exists(bad)) { MessageBox.Show("Không tìm thấy thư mục bad/.", "Thông báo", MessageBoxButtons.OK, MessageBoxIcon.Information); return; }
        System.Diagnostics.Process.Start("explorer.exe", bad);
    }

    private void ShowConsolidate() => MessageBox.Show("Tổng hợp: tính năng đang phát triển.", "Thông báo", MessageBoxButtons.OK, MessageBoxIcon.Information);

    private void ClearProgress()
    {
        var d = _cmbOutput.Text.Trim();
        if (string.IsNullOrEmpty(d)) return;
        var files = new[] { ".lotte_done.json", ".p8_done.json", ".p6_done.json" }
                    .Select(f => Path.Combine(d, f)).Where(File.Exists).ToList();
        if (files.Count == 0) { MessageBox.Show("Không tìm thấy file tiến độ.", "Thông báo", MessageBoxButtons.OK, MessageBoxIcon.Information); return; }
        if (MessageBox.Show($"Xóa {files.Count} file tiến độ?", "Xác nhận", MessageBoxButtons.YesNo, MessageBoxIcon.Question) == DialogResult.Yes)
        { foreach (var f in files) try { File.Delete(f); } catch { } AppendLog("[INFO] Đã xóa file tiến độ."); }
    }

    private void OnBrowseOutput(object? s, EventArgs e)
    {
        using var dlg = new FolderBrowserDialog { Description = "Chọn thư mục lưu ảnh" };
        if (!string.IsNullOrEmpty(_cmbOutput.Text) && Directory.Exists(_cmbOutput.Text)) dlg.SelectedPath = _cmbOutput.Text;
        if (dlg.ShowDialog() == DialogResult.OK) { _cmbOutput.Text = dlg.SelectedPath; SettingsManager.PushHistory("ip.out", dlg.SelectedPath); }
    }

    // ════════════════════════════════════════════════════════════════════
    //  Config
    // ════════════════════════════════════════════════════════════════════
    private bool ValidateConfig(AppConfig cfg)
    {
        if (string.IsNullOrEmpty(cfg.OutputDir)) { MessageBox.Show("Vui lòng chọn thư mục lưu ảnh.", "Thiếu thông tin", MessageBoxButtons.OK, MessageBoxIcon.Warning); return false; }
        if (cfg.Source == "Parkingv6" && string.IsNullOrEmpty(cfg.Parkingv6.Token)) { MessageBox.Show("Parkingv6 cần nhập Bearer Token.", "Thiếu thông tin", MessageBoxButtons.OK, MessageBoxIcon.Warning); return false; }
        return true;
    }

    private AppConfig GetConfig()
    {
        var allowed = _vtypes.Where(kv => kv.Value.Checked).Select(kv => kv.Key).ToList();
        return new AppConfig {
            Source = _cmbSource.Text,
            FromDate = _dtpFrom.Value.ToString("yyyy-MM-dd HH:mm:ss"),
            ToDate   = _dtpTo.Value.ToString("yyyy-MM-dd HH:mm:ss"),
            OutputDir = _cmbOutput.Text.Trim(),
            PageSize  = (int)_nudPageSize.Value, MaxPages = (int)_nudMaxPages.Value,
            SleepSeconds = double.TryParse(_txtSleep.Text, out var sl) ? sl : 0.1,
            MaxPerLane = (int)_nudMaxLane.Value, MaxPerCategory = (int)_nudMaxCat.Value,
            MaxPerBuoi = (int)_nudMaxBuoi.Value, Parallel = (int)_nudParallel.Value,
            CollectBad = _chkCollectBad.Checked, OnlyGT = _chkOnlyGT.Checked,
            AllowedVtypes = allowed.Count < _vtypeDefs.Length ? allowed : [],
            Lotte = new LotteConfig {
                ApiBase = _txtLotteApi.Text.Trim(), Username = _txtLotteUser.Text.Trim(), Password = _txtLottePass.Text,
                UseMinIO = _chkLotteMinIO.Checked,
                MinioEndpoint = _txtLotteMep.Text.Trim(), MinioBucket = _txtLotteMbk.Text.Trim(),
                MinioAccessKey = _txtLotteMAk.Text.Trim(), MinioSecretKey = _txtLotteMsk.Text,
                KeywordToanCanh = _txtLotteKwTC.Text.Trim(), KeywordXeMay = _txtLotteKwMay.Text.Trim(),
                KeywordXeDap = _txtLotteKwDap.Text.Trim(), KeywordOTo = _txtLotteKwOTo.Text.Trim(),
                Keyword = _cmbLotteKeyword.Text.Trim(),
            },
            Parkingv8 = new Parkingv8Config {
                LoginUrl = _txtP8Login.Text.Trim(), ApiUrl = _txtP8Api.Text.Trim(),
                ClientId = _txtP8CId.Text.Trim(), ClientSecret = _txtP8Sec.Text,
                Username = _txtP8User.Text.Trim(), Password = _txtP8Pass.Text,
                GrantType = _cmbP8Grant.Text, EventSource = _cmbP8Src.Text,
                ImgMode = _rbP8B64.Checked ? "base64" : "url", Keyword = _cmbP8Keyword.Text.Trim(),
            },
            Parkingv6 = new Parkingv6Config {
                ApiUrl = _txtP6Api.Text.Trim(), Token = _txtP6Token.Text.Trim(),
                UseMinIO = _chkP6MinIO.Checked,
                MinioEndpoint = _txtP6Mep.Text.Trim(), MinioBucket = _txtP6Mbk.Text.Trim(),
                MinioAccessKey = _txtP6MAk.Text.Trim(), MinioSecretKey = _txtP6Msk.Text,
                EventSource = _cmbP6Src.Text, Keyword = _cmbP6Keyword.Text.Trim(),
            },
        };
    }

    // ════════════════════════════════════════════════════════════════════
    //  Settings
    // ════════════════════════════════════════════════════════════════════
    private void LoadSettings()
    {
        var cfg = SettingsManager.Load();
        _cmbSource.Text  = cfg.Source;
        _dtpFrom.Value   = DateTime.TryParse(cfg.FromDate, out var fd) ? fd : DateTime.Now.AddMonths(-1);
        _dtpTo.Value     = DateTime.TryParse(cfg.ToDate,   out var td) ? td : DateTime.Now;
        _cmbOutput.Text  = cfg.OutputDir;
        _nudPageSize.Value  = Math.Clamp(cfg.PageSize,   10, 500);
        _nudMaxPages.Value  = Math.Clamp(cfg.MaxPages,    1, 99999);
        _txtSleep.Text      = cfg.SleepSeconds.ToString();
        _nudMaxLane.Value   = Math.Clamp(cfg.MaxPerLane,     0, 999999);
        _nudMaxCat.Value    = Math.Clamp(cfg.MaxPerCategory, 0, 999999);
        _nudMaxBuoi.Value   = Math.Clamp(cfg.MaxPerBuoi,     0, 99999);
        _nudParallel.Value  = Math.Clamp(cfg.Parallel,       1, 16);
        _chkOnlyGT.Checked     = cfg.OnlyGT;
        _chkCollectBad.Checked = cfg.CollectBad;
        if (cfg.AllowedVtypes is { Count: > 0 })
            foreach (var (key, chk) in _vtypes) chk.Checked = cfg.AllowedVtypes.Contains(key);

        _chkLotteMinIO.Checked = cfg.Lotte.UseMinIO;
        _cmbLotteKeyword.Text  = cfg.Lotte.Keyword;
        _txtLotteKwTC.Text     = cfg.Lotte.KeywordToanCanh;
        _txtLotteKwMay.Text    = cfg.Lotte.KeywordXeMay;
        _txtLotteKwDap.Text    = cfg.Lotte.KeywordXeDap;
        _txtLotteKwOTo.Text    = cfg.Lotte.KeywordOTo;
        _txtLotteApi.Text      = string.IsNullOrEmpty(cfg.Lotte.ApiBase)          ? _LI_Const.ApiBase  : cfg.Lotte.ApiBase;
        _txtLotteUser.Text     = cfg.Lotte.Username;
        _txtLottePass.Text     = cfg.Lotte.Password;
        _txtLotteMep.Text      = string.IsNullOrEmpty(cfg.Lotte.MinioEndpoint)   ? _LI_Const.MinioEp  : cfg.Lotte.MinioEndpoint;
        _txtLotteMbk.Text      = string.IsNullOrEmpty(cfg.Lotte.MinioBucket)     ? _LI_Const.MinioBkt : cfg.Lotte.MinioBucket;
        _txtLotteMAk.Text      = string.IsNullOrEmpty(cfg.Lotte.MinioAccessKey)  ? _LI_Const.MinioAk  : cfg.Lotte.MinioAccessKey;
        _txtLotteMsk.Text      = cfg.Lotte.MinioSecretKey;

        _cmbP8Src.Text   = cfg.Parkingv8.EventSource;
        _cmbP8Grant.Text = cfg.Parkingv8.GrantType;
        if (cfg.Parkingv8.ImgMode == "base64") _rbP8B64.Checked = true; else _rbP8Url.Checked = true;
        _cmbP8Keyword.Text = cfg.Parkingv8.Keyword;
        _txtP8Login.Text   = cfg.Parkingv8.LoginUrl;
        _txtP8Api.Text     = cfg.Parkingv8.ApiUrl;
        _txtP8CId.Text     = cfg.Parkingv8.ClientId;
        _txtP8Sec.Text     = cfg.Parkingv8.ClientSecret;
        _txtP8User.Text    = cfg.Parkingv8.Username;
        _txtP8Pass.Text    = cfg.Parkingv8.Password;

        _chkP6MinIO.Checked = cfg.Parkingv6.UseMinIO;
        _cmbP6Src.Text      = cfg.Parkingv6.EventSource;
        _cmbP6Keyword.Text  = cfg.Parkingv6.Keyword;
        _txtP6Api.Text      = cfg.Parkingv6.ApiUrl;
        _txtP6Token.Text    = cfg.Parkingv6.Token;
        _txtP6Mep.Text      = cfg.Parkingv6.MinioEndpoint;
        _txtP6Mbk.Text      = cfg.Parkingv6.MinioBucket;
        _txtP6MAk.Text      = cfg.Parkingv6.MinioAccessKey;
        _txtP6Msk.Text      = cfg.Parkingv6.MinioSecretKey;
        OnSourceChange();
    }

    private void SaveSettings() => SettingsManager.Save(GetConfig());

    private static class _LI_Const
    {
        public static string ApiBase  = "http://localhost:8080";
        public static string Username = "admin";
        public static string Password = "admin";
        public static string MinioEp  = "localhost:9000";
        public static string MinioBkt = "iparking";
        public static string MinioAk  = "minioadmin";
        public static string MinioSk  = "minioadmin";
    }

    // Prevents AutoScroll from chasing focused controls (DateTimePicker, ComboBox, etc.)
    private class NoFocusScrollPanel : Panel {
        protected override Point ScrollToControl(Control activeControl) => AutoScrollPosition;
    }
}
