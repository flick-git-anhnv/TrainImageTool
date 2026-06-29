using IParkingDetect.Controls;
using IParkingDetect.Models;
using IParkingDetect.UI;

namespace IParkingDetect;

// Phần khai báo controls và khởi tạo UI — chỉ chứa code tạo widget, KHÔNG chứa logic nghiệp vụ.
partial class DetectForm
{
    // ── Controls toolbar row 0 ────────────────────────────────────────────
    private ComboBox _cmbModel    = null!;
    private ComboBox _cmbDevice   = null!;
    private Label    _lblModelInfo = null!;

    // toolbar row 1
    private ComboBox  _cmbPath = null!;
    private CheckBox  _chkSub  = null!;

    // toolbar row 2
    private TrackBar      _sldConf = null!, _sldIou = null!;
    private Label         _lblConf = null!, _lblIou = null!;
    private NumericUpDown _nudParallel = null!;
    private Button        _btnDetect = null!, _btnDetectAll = null!, _btnStop = null!;
    private CheckBox      _chkSaveLabel = null!;
    private Label         _lblCacheInfo = null!;
    private ProgressBar   _pbDetect = null!;

    // left panel
    private TextBox       _txtSearch    = null!;
    private TreeView      _tree         = null!;
    private Button        _btnAllFilter = null!, _btnOkFilter  = null!,
                          _btnWrongFilter = null!, _btnUnrevFilter = null!;
    private ComboBox      _cmbClassFlt  = null!;
    private NumericUpDown _nudDetMin = null!, _nudDetMax = null!;

    // center
    private ImageCanvas     _canvas    = null!;
    private Label           _lblNav    = null!;
    private CheckBox        _chkOrig   = null!;
    private FlowLayoutPanel _filmstrip = null!;

    // right panel
    private Label    _lblImgPath   = null!;
    private ListView _lstResult    = null!;
    private Label    _lblTiming    = null!;
    private Label    _lblMark      = null!;
    private Button   _btnOk = null!, _btnWrong = null!, _btnClearMark = null!;
    private ComboBox _cmbWrongDir  = null!;
    private Button   _btnSaveWrong = null!;

    // toolbar row 3 — API
    private NumericUpDown _nudApiPort   = null!;
    private Button        _btnApiToggle = null!;
    private Label         _lblApiStatus = null!;
    private CheckBox      _chkApiAuto   = null!;

    // log panel
    private ListView                     _lvLog       = null!;
    private Label                        _lblLogCount = null!;
    private System.Windows.Forms.Timer   _logTimer    = null!;

    // status bar
    private Label _lblStatus = null!;

    // ═════════════════════════════════════════════════════════════════════
    // INITIALIZE COMPONENT
    // ═════════════════════════════════════════════════════════════════════

    private void InitializeComponent()
    {
        var toolbar   = BuildToolbar();
        var statusBar = BuildStatusBar();
        var mainPanel = new Panel { Dock = DockStyle.Fill, BackColor = Theme.BG };
        BuildMainPanel(mainPanel);
        var logPanel  = BuildLogPanel();

        Controls.Add(mainPanel);
        Controls.Add(logPanel);
        Controls.Add(toolbar);
        Controls.Add(statusBar);
    }

    // ── Toolbar (4 rows) ──────────────────────────────────────────────────

    private Panel BuildToolbar()
    {
        var toolbar = new Panel
        {
            Dock = DockStyle.Top, Height = 140, BackColor = Theme.Card,
            Padding = new Padding(8, 4, 8, 4),
        };

        // Row 0 — Model
        var r0 = Theme.Row(); r0.Margin = new Padding(0, 2, 0, 2);

        // Ô combobox model có viền Accent rõ ràng
        _cmbModel = Theme.Cmb(w: 348);
        _cmbModel.Items.AddRange(_cfg.ModelHistory.ToArray());
        if (_cfg.ModelHistory.Count > 0) _cmbModel.Text = _cfg.ModelHistory[0];
        var cmbModelBorder = new Panel
        {
            Width       = 350,
            BackColor   = Theme.Accent,   // viền 1px màu cam KZTEK
            Padding     = new Padding(1),
            Margin      = new Padding(0, 2, 4, 2),
            BorderStyle = BorderStyle.None,
        };
        cmbModelBorder.Controls.Add(_cmbModel);
        _cmbModel.Dock = DockStyle.Fill;

        var btnBrowseModel = Theme.Btn("📂 Model…");
        var btnLoadModel   = Theme.Btn("⚡ Load", Theme.Accent);
        var btnYaml        = Theme.Btn("📋 YAML…");

        _cmbDevice = new ComboBox
        {
            DropDownStyle = ComboBoxStyle.DropDownList,
            Width = 72, Font = Theme.FMain,
            BackColor = Theme.Card, ForeColor = Theme.Txt,
        };
        _cmbDevice.Items.AddRange(["CPU", "AUTO", "GPU"]);
        _cmbDevice.Text = _cfg.Device;
        new ToolTip().SetToolTip(_cmbDevice, "Thiết bị inference: CPU / AUTO (iGPU+CPU) / GPU");

        _lblModelInfo = Theme.Lbl("Chưa load model", fg: Theme.Dim);
        _lblModelInfo.Margin = new Padding(8, 0, 0, 0);

        r0.Controls.AddRange([
            Theme.Lbl("Model:", Theme.FBold), cmbModelBorder,
            btnBrowseModel, btnLoadModel,
            Theme.Lbl("Dev:"), _cmbDevice,
            btnYaml, _lblModelInfo]);

        // Row 1 — Path
        var r1 = Theme.Row(); r1.Margin = new Padding(0, 2, 0, 2);
        _cmbPath = Theme.Cmb(w: 380);
        _cmbPath.Items.AddRange(_cfg.ImageHistory.ToArray());
        if (_cfg.ImageHistory.Count > 0) _cmbPath.Text = _cfg.ImageHistory[0];
        var btnBrowseImg = Theme.Btn("📂 Ảnh…");
        var btnBrowseDir = Theme.Btn("📁 Thư mục…");
        var btnLoad      = Theme.Btn("▶ Tải", Theme.Accent);
        _chkSub          = Theme.Chk("Sub-folder", _cfg.ScanSubfolders);

        r1.Controls.AddRange([
            Theme.Lbl("Path:", Theme.FBold), _cmbPath,
            btnBrowseImg, btnBrowseDir, btnLoad, _chkSub]);

        // Row 2 — Params
        var r2 = Theme.Row(); r2.Margin = new Padding(0, 2, 0, 2);
        _sldConf = Theme.Slider(0, 100, (int)(_cfg.Conf * 100), 120);
        _lblConf = Theme.Lbl($"{_cfg.Conf:F2}");
        _sldIou  = Theme.Slider(0, 100, (int)(_cfg.Iou  * 100), 120);
        _lblIou  = Theme.Lbl($"{_cfg.Iou:F2}");
        _nudParallel = Theme.Num(min: 1, max: 16, val: _cfg.Parallelism, w: 52);
        _nudParallel.Font = Theme.FMain;
        new ToolTip().SetToolTip(_nudParallel, "Số ảnh detect song song cùng lúc (luồng)");

        // Nút detect đơn (ảnh hiện tại) — viền Accent rõ ràng
        _btnDetect = Theme.Btn("⚡ Detect", Theme.Accent);
        new ToolTip().SetToolTip(_btnDetect, "Detect ảnh hiện tại + lưu nhãn (nếu bật)");

        // Detect All — màu xanh nhạt để phân biệt
        _btnDetectAll = Theme.Btn("⚡ Detect All", Color.FromArgb(46, 125, 50));
        new ToolTip().SetToolTip(_btnDetectAll, "Detect toàn bộ ảnh trong danh sách (F5)");

        _btnStop      = Theme.Btn("■ Stop", Theme.Err);
        _btnStop.Visible = false;
        _pbDetect = new ProgressBar
        {
            Width = 140, Height = 18, Visible = false,
            Style = ProgressBarStyle.Continuous,
        };
        _lblCacheInfo = Theme.Lbl("Cache: 0/0", fg: Theme.Dim);
        var btnClearCache = Theme.Btn("🗑 Cache");
        btnClearCache.Height = 22;
        new ToolTip().SetToolTip(btnClearCache, "Xóa toàn bộ cache detect (Ctrl+Shift+Delete)");
        btnClearCache.Click += (_, _) => ClearCache();

        _chkSaveLabel = Theme.Chk("💾 Lưu nhãn", _cfg.SaveLabel);
        new ToolTip().SetToolTip(_chkSaveLabel, "Tự động lưu file .txt (YOLO format) sau khi detect");

        r2.Controls.AddRange([
            Theme.Lbl("Conf:"), _sldConf, _lblConf,
            Theme.Lbl("  IoU:"), _sldIou, _lblIou,
            new Label { Width = 10, BackColor = Color.Transparent },
            Theme.Lbl("Luồng:"), _nudParallel,
            new Label { Width = 6,  BackColor = Color.Transparent },
            _btnDetect, _btnDetectAll, _btnStop, _pbDetect, _lblCacheInfo, btnClearCache,
            new Label { Width = 6,  BackColor = Color.Transparent },
            _chkSaveLabel]);

        // Row 3 — API Host
        var r3 = Theme.Row(); r3.Margin = new Padding(0, 2, 0, 2);
        _nudApiPort   = Theme.Num(1024, 65535, _cfg.ApiPort, w: 64);
        new ToolTip().SetToolTip(_nudApiPort, "Cổng HTTP API (1024–65535)");
        _btnApiToggle = Theme.Btn("🌐 Start API");
        _chkApiAuto   = Theme.Chk("Auto-start", _cfg.ApiAutoStart);
        _lblApiStatus = Theme.Lbl("● Stopped", fg: Theme.Dim);
        _lblApiStatus.Font = Theme.FSmB;

        r3.Controls.AddRange([
            Theme.Lbl("API Host:", Theme.FBold),
            Theme.Lbl("Port:"), _nudApiPort, _btnApiToggle, _chkApiAuto,
            new Label { Width = 8, BackColor = Color.Transparent },
            _lblApiStatus]);

        // Stack rows (ngược thứ tự vì DockStyle.Top)
        toolbar.Controls.Add(r3);
        toolbar.Controls.Add(r2);
        toolbar.Controls.Add(r1);
        toolbar.Controls.Add(r0);
        r0.Dock = r1.Dock = r2.Dock = r3.Dock = DockStyle.Top;

        // Wire events
        btnBrowseModel.Click += OnBrowseModel;
        btnLoadModel.Click   += OnLoadModel;
        btnYaml.Click        += OnLoadYaml;
        _cmbModel.KeyDown    += (s, e) => { if (e.KeyCode == Keys.Return) OnLoadModel(s, e); };

        btnBrowseImg.Click   += (_, _) => BrowseFile();
        btnBrowseDir.Click   += (_, _) => BrowseFolder();
        btnLoad.Click        += OnLoadPath;
        _cmbPath.KeyDown     += (s, e) => { if (e.KeyCode == Keys.Return) OnLoadPath(s, e); };

        _sldConf.ValueChanged     += (_, _) => { _cfg.Conf = _sldConf.Value / 100f; _lblConf.Text = $"{_cfg.Conf:F2}"; RefreshCurrentDetect(); };
        _sldIou.ValueChanged      += (_, _) => { _cfg.Iou  = _sldIou.Value  / 100f; _lblIou.Text  = $"{_cfg.Iou:F2}"; };
        _nudParallel.ValueChanged += (_, _) => _cfg.Parallelism = (int)_nudParallel.Value;
        _btnDetect.Click          += OnDetectCurrent;
        _btnDetectAll.Click       += OnDetectAll;
        _btnStop.Click            += (_, _) => _detectCts?.Cancel();
        _chkSaveLabel.CheckedChanged += (_, _) => _cfg.SaveLabel = _chkSaveLabel.Checked;

        _nudApiPort.ValueChanged   += (_, _) => _cfg.ApiPort     = (int)_nudApiPort.Value;
        _chkApiAuto.CheckedChanged += (_, _) => _cfg.ApiAutoStart = _chkApiAuto.Checked;
        _btnApiToggle.Click        += OnToggleApi;

        return toolbar;
    }

    // ── Status bar ────────────────────────────────────────────────────────

    private Panel BuildStatusBar()
    {
        var bar = new Panel { Dock = DockStyle.Bottom, Height = 24, BackColor = Theme.NavyDk };
        _lblStatus = Theme.Lbl("Sẵn sàng");
        _lblStatus.Dock      = DockStyle.Fill;
        _lblStatus.TextAlign = ContentAlignment.MiddleLeft;
        _lblStatus.Padding   = new Padding(8, 0, 0, 0);
        bar.Controls.Add(_lblStatus);
        return bar;
    }

    // ── Main panel (left | center | right) ───────────────────────────────

    private void BuildMainPanel(Panel parent)
    {
        var sc1 = new SplitContainer
        {
            Dock = DockStyle.Fill, Orientation = Orientation.Vertical,
            SplitterWidth = 4, BackColor = Theme.Border,
            FixedPanel = FixedPanel.Panel1,
        };
        sc1.Panel1.BackColor = sc1.Panel2.BackColor = Theme.BG;
        sc1.SplitterDistance = _cfg.SplitLeft;

        BuildLeftPanel(sc1.Panel1);

        var sc2 = new SplitContainer
        {
            Dock = DockStyle.Fill, Orientation = Orientation.Vertical,
            SplitterWidth = 4, BackColor = Theme.Border,
            FixedPanel = FixedPanel.Panel2,
        };
        sc2.Panel1.BackColor = sc2.Panel2.BackColor = Theme.BG;
        sc2.SplitterDistance = Math.Max(300, sc1.Panel2.Width - _cfg.SplitRight - 4);

        BuildCenterPanel(sc2.Panel1);
        BuildRightPanel(sc2.Panel2);

        sc1.Panel2.Controls.Add(sc2);
        parent.Controls.Add(sc1);

        sc1.SplitterMoved += (_, _) => _cfg.SplitLeft  = sc1.SplitterDistance;
        sc2.SplitterMoved += (_, _) => _cfg.SplitRight = sc1.Panel2.Width - sc2.SplitterDistance - 4;
    }

    // ── Left panel (image list + filters) ────────────────────────────────

    private void BuildLeftPanel(Panel p)
    {
        var searchRow = Theme.Row(); searchRow.Dock = DockStyle.Top;
        _txtSearch = new TextBox
        {
            Width = 150, BackColor = Theme.Card, ForeColor = Theme.Txt,
            BorderStyle = BorderStyle.FixedSingle, Font = Theme.FMain,
        };
        _txtSearch.TextChanged += (_, _) => RebuildTree();
        searchRow.Controls.AddRange([Theme.Lbl("🔍"), _txtSearch]);

        var filterRow = Theme.Row(); filterRow.Dock = DockStyle.Top;
        _btnAllFilter   = MakeFilterBtn("Tất cả", "all");
        _btnOkFilter    = MakeFilterBtn("✓ Đúng",  "ok");
        _btnWrongFilter = MakeFilterBtn("✗ Sai",   "wrong");
        _btnUnrevFilter = MakeFilterBtn("?",        "none");
        filterRow.Controls.AddRange([_btnAllFilter, _btnOkFilter, _btnWrongFilter, _btnUnrevFilter]);
        HighlightFilter();

        var detRow = Theme.Row(); detRow.Dock = DockStyle.Top;
        _cmbClassFlt = Theme.Cmb(["Tất cả"], readOnly: true, w: 90);
        _nudDetMin   = Theme.Num(0, 99, 0,  48);
        _nudDetMax   = Theme.Num(0, 99, 99, 48);
        detRow.Controls.AddRange([
            Theme.Lbl("Class:"), _cmbClassFlt,
            new Label { Width = 4, BackColor = Color.Transparent },
            Theme.Lbl("#Det:"), _nudDetMin, Theme.Lbl("–"), _nudDetMax]);

        _tree = new TreeView
        {
            Dock = DockStyle.Fill, BackColor = Theme.Card, ForeColor = Theme.Txt,
            BorderStyle = BorderStyle.None, ShowRootLines = false, ShowLines = true,
            ItemHeight = 18, Font = Theme.FSm,
        };
        _tree.AfterSelect += OnTreeSelect;

        p.Controls.Add(_tree);
        p.Controls.Add(detRow);
        p.Controls.Add(filterRow);
        p.Controls.Add(searchRow);

        _cmbClassFlt.SelectedIndexChanged += (_, _) => RebuildTree();
        _nudDetMin.ValueChanged            += (_, _) => RebuildTree();
        _nudDetMax.ValueChanged            += (_, _) => RebuildTree();
    }

    private Button MakeFilterBtn(string text, string filter)
    {
        var b = Theme.Btn(text, Theme.Card, Theme.Txt);
        b.Height = 22; b.Font = Theme.FSm;
        b.Click += (_, _) => { _activeFilter = filter; HighlightFilter(); RebuildTree(); };
        return b;
    }

    // ── Center panel (canvas + nav + filmstrip) ───────────────────────────

    private void BuildCenterPanel(Panel p)
    {
        var filmPanel = new Panel
        {
            Dock = DockStyle.Bottom, Height = _cfg.SplitFilm, BackColor = Theme.Deep,
        };
        var filmScroll = new Panel { Dock = DockStyle.Fill, AutoScroll = true, BackColor = Theme.Deep };
        _filmstrip = new FlowLayoutPanel
        {
            FlowDirection = FlowDirection.LeftToRight, AutoSize = true,
            WrapContents = false, BackColor = Theme.Deep,
        };
        filmScroll.Controls.Add(_filmstrip);
        filmPanel.Controls.Add(filmScroll);
        filmPanel.Controls.Add(Theme.SectionHdr("Filmstrip"));

        var navRow = new Panel { Dock = DockStyle.Bottom, Height = 28, BackColor = Theme.Card };
        var btnPrev = Theme.Btn("◄", Theme.Navy); btnPrev.Click += (_, _) => Navigate(-1);
        var btnNext = Theme.Btn("►", Theme.Navy); btnNext.Click += (_, _) => Navigate(+1);
        btnPrev.Height = btnNext.Height = 24;
        _lblNav  = Theme.Lbl("–");
        _chkOrig = Theme.Chk("Xem gốc", _cfg.ShowOriginal);
        _chkOrig.CheckedChanged += (_, _) => { _cfg.ShowOriginal = _chkOrig.Checked; RefreshCanvas(); };

        var zoomIn  = Theme.Btn("+");  zoomIn.Click  += (_, _) => _canvas.ZoomStep(1.3f);
        var zoomOut = Theme.Btn("−");  zoomOut.Click += (_, _) => _canvas.ZoomStep(1f / 1.3f);
        var zoomFit = Theme.Btn("Fit"); zoomFit.Click += (_, _) => _canvas.FitToView();
        foreach (var b in new[] { zoomIn, zoomOut, zoomFit }) b.Height = 24;

        var nr = Theme.Row(); nr.Dock = DockStyle.Fill;
        nr.Controls.AddRange([
            btnPrev, _lblNav, btnNext,
            new Label { Width = 12, BackColor = Color.Transparent },
            zoomOut, zoomIn, zoomFit, _chkOrig]);
        navRow.Controls.Add(nr);

        _canvas = new ImageCanvas { Dock = DockStyle.Fill, BackColor = Theme.Deep };

        p.Controls.Add(_canvas);
        p.Controls.Add(navRow);
        p.Controls.Add(filmPanel);
    }

    // ── Right panel (results + review + timing) ───────────────────────────

    private void BuildRightPanel(Panel p)
    {
        p.Padding = new Padding(4);

        _lblImgPath = Theme.Lbl("", fg: Theme.Dim);
        _lblImgPath.Font     = Theme.FSm;
        _lblImgPath.Dock     = DockStyle.Top;
        _lblImgPath.Height   = 32;
        _lblImgPath.AutoSize = false;

        _lstResult = new ListView
        {
            Dock = DockStyle.Fill, BackColor = Theme.Card, ForeColor = Theme.Txt,
            View = View.Details, FullRowSelect = true, GridLines = false,
            BorderStyle = BorderStyle.None, Font = Theme.FSm,
            MultiSelect = false,
        };
        _lstResult.Columns.Add("Class", 90);
        _lstResult.Columns.Add("Conf",  55);
        _lstResult.Columns.Add("W×H",   65);

        var markHdr = Theme.SectionHdr("Đánh giá");
        var markRow = Theme.Row(); markRow.Dock = DockStyle.Bottom;
        _btnOk        = Theme.Btn("✓ Đúng [Enter]", Theme.Ok);
        _btnWrong     = Theme.Btn("✗ Sai [Del]",    Theme.Err);
        _btnClearMark = Theme.Btn("↺ Xóa");
        foreach (var b in new[] { _btnOk, _btnWrong, _btnClearMark }) b.Height = 24;
        _lblMark = Theme.Lbl("", fg: Theme.Dim); _lblMark.Font = Theme.FSm;
        markRow.Controls.AddRange([_btnOk, _btnWrong, _btnClearMark]);

        var wrongRow = Theme.Row(); wrongRow.Dock = DockStyle.Bottom;
        _cmbWrongDir  = Theme.Cmb(w: 130);
        _cmbWrongDir.Text = _cfg.WrongFolder;
        var btnWrongBrowse = Theme.Btn("📁"); btnWrongBrowse.Height = 24;
        _btnSaveWrong = Theme.Btn("💾 Lưu sai"); _btnSaveWrong.Height = 24;
        wrongRow.Controls.AddRange([_cmbWrongDir, btnWrongBrowse, _btnSaveWrong]);

        _lblTiming = Theme.Lbl("", fg: Theme.Dim);
        _lblTiming.Font      = Theme.FMono;
        _lblTiming.Dock      = DockStyle.Bottom;
        _lblTiming.Height    = 32;
        _lblTiming.AutoSize  = false;
        _lblTiming.TextAlign = ContentAlignment.MiddleLeft;
        _lblTiming.Padding   = new Padding(2, 0, 0, 0);

        p.Controls.Add(_lstResult);
        p.Controls.Add(_lblTiming);
        p.Controls.Add(_lblMark);
        p.Controls.Add(wrongRow);
        p.Controls.Add(markRow);
        p.Controls.Add(markHdr);
        p.Controls.Add(_lblImgPath);

        _btnOk.Click        += (_, _) => SetReview(ReviewState.Ok);
        _btnWrong.Click     += (_, _) => SetReview(ReviewState.Wrong);
        _btnClearMark.Click += (_, _) => SetReview(ReviewState.None);
        _btnSaveWrong.Click += OnSaveWrong;
        btnWrongBrowse.Click += (_, _) =>
        {
            using var d = new FolderBrowserDialog();
            if (d.ShowDialog() == DialogResult.OK) _cmbWrongDir.Text = d.SelectedPath;
        };
        _cmbWrongDir.Leave += (_, _) => _cfg.WrongFolder = _cmbWrongDir.Text;
    }

    // ── Log panel (API request log) ───────────────────────────────────────

    private Panel BuildLogPanel()
    {
        var panel = new Panel { Dock = DockStyle.Bottom, Height = 155, BackColor = Theme.Card };

        var hdr = new Panel { Dock = DockStyle.Top, Height = 26, BackColor = Theme.NavyDk };
        _lblLogCount = Theme.Lbl("📋 API Log  —  0 yêu cầu", fg: Color.White);
        _lblLogCount.Font      = Theme.FSmB;
        _lblLogCount.Dock      = DockStyle.Left;
        _lblLogCount.Padding   = new Padding(6, 0, 0, 0);
        _lblLogCount.TextAlign = ContentAlignment.MiddleLeft;

        var btnClear = Theme.Btn("🗑 Xóa");
        btnClear.Dock   = DockStyle.Right;
        btnClear.Click += (_, _) => { _lvLog.Items.Clear(); _logItems.Clear(); UpdateLogCount(); };
        hdr.Controls.Add(_lblLogCount);
        hdr.Controls.Add(btnClear);

        _lvLog = new ListView
        {
            Dock = DockStyle.Fill, View = View.Details, FullRowSelect = true,
            BackColor = Theme.BG, ForeColor = Theme.Txt, BorderStyle = BorderStyle.None,
            GridLines = true, Font = Theme.FMain,
        };
        _lvLog.Columns.Add("Ảnh",         180);
        _lvLog.Columns.Add("Trạng thái",  110);
        _lvLog.Columns.Add("Bắt đầu",      90);
        _lvLog.Columns.Add("Xử lý xong",   90);
        _lvLog.Columns.Add("Infer (ms)",    80);
        _lvLog.Columns.Add("Tổng (ms)",     80);

        var tt = new ToolTip();
        _lvLog.MouseMove += (_, e) =>
        {
            var hit  = _lvLog.HitTest(e.Location);
            var path = hit.Item?.Tag as string ?? "";
            if (path.Length > 0 && tt.GetToolTip(_lvLog) != path)
                tt.SetToolTip(_lvLog, path);
        };

        panel.Controls.Add(_lvLog);
        panel.Controls.Add(hdr);

        _logTimer = new System.Windows.Forms.Timer { Interval = 200 };
        _logTimer.Tick += (_, _) => FlushLogQueue();
        _logTimer.Start();

        return panel;
    }
}
