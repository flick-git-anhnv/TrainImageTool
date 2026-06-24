using System.Collections.Concurrent;
using IParkingDetect.Controls;
using IParkingDetect.Helpers;
using IParkingDetect.Inference;
using IParkingDetect.Models;
using IParkingDetect.UI;

namespace IParkingDetect;

/// <summary>
/// KZTEK — iParking Detection Tester
/// Giao diện test model YOLO (OpenVINO IR / ONNX) trên tập ảnh iParking.
/// Tính năng tương đương YOLODetect tab (Python):
///   - Load model .xml/.onnx, load YAML class names
///   - Duyệt thư mục / file ảnh (có sub-folder)
///   - Hiển thị bbox với zoom/pan
///   - Bộ lọc: class, số detect, diện tích bbox
///   - Đánh dấu ảnh đúng/sai, lưu ảnh sai
///   - Detect all (background thread), cache kết quả
///   - Filmstrip thumbnail, tìm kiếm tên ảnh
///   - Lưu cài đặt, khôi phục phiên làm việc
/// </summary>
public sealed class DetectForm : Form
{
    // ── Inference / Data ──────────────────────────────────────────────────
    private readonly YoloRunner  _yolo    = new();
    private readonly AppSettings _cfg     = AppSettings.Load();
    private readonly ConcurrentDictionary<string, List<DetectBox>> _cache = new();
    private readonly Dictionary<string, ReviewState>     _review = [];
    private CancellationTokenSource? _detectCts;

    private List<string> _imageList  = [];
    private int          _currentIdx = -1;
    private Bitmap?      _origBmp;            // ảnh gốc đang hiển thị
    private bool         _isDetecting;

    // ── Timing ────────────────────────────────────────────────────────────
    private long _lastDetectMs  = 0;   // ms của lần detect hiện tại
    private long _batchTotalMs  = 0;   // tổng ms (Interlocked khi parallel)
    private long _batchCount    = 0;   // số ảnh đã detect (Interlocked khi parallel)

    // ── Controls (toolbar row 0) ──────────────────────────────────────────
    private ComboBox _cmbModel = null!;
    private Label    _lblModelInfo = null!;

    // toolbar row 1
    private ComboBox  _cmbPath    = null!;
    private CheckBox  _chkSub     = null!;

    // toolbar row 2
    private TrackBar _sldConf = null!, _sldIou = null!;
    private Label    _lblConf = null!, _lblIou = null!;
    private Button   _btnDetectAll = null!, _btnStop = null!;
    private Label    _lblCacheInfo = null!;
    private ProgressBar _pbDetect = null!;

    // left panel
    private TextBox  _txtSearch = null!;
    private TreeView _tree      = null!;
    private Button   _btnAllFilter = null!, _btnOkFilter = null!,
                     _btnWrongFilter = null!, _btnUnrevFilter = null!;
    private ComboBox     _cmbClassFlt = null!;
    private NumericUpDown _nudDetMin = null!, _nudDetMax = null!;
    private string _activeFilter = "all";

    // center
    private ImageCanvas _canvas = null!;
    private Label       _lblNav = null!;
    private CheckBox    _chkOrig = null!;
    private FlowLayoutPanel _filmstrip = null!;

    // right panel
    private Label    _lblImgPath  = null!;
    private ListView _lstResult   = null!;
    private Label    _lblTiming   = null!;   // thời gian xử lý
    private Label    _lblMark     = null!;
    private Button   _btnOk       = null!, _btnWrong = null!, _btnClearMark = null!;
    private ComboBox _cmbWrongDir = null!;
    private Button   _btnSaveWrong = null!;

    // status
    private Label _lblStatus = null!;

    // ── Constructor ───────────────────────────────────────────────────────
    public DetectForm()
    {
        Text            = "KZTEK — iParking Detection Tester";
        Size            = new Size(_cfg.FormW, _cfg.FormH);
        MinimumSize     = new Size(1000, 640);
        BackColor       = Theme.BG;
        ForeColor       = Theme.Txt;
        Font            = Theme.FMain;
        DoubleBuffered  = true;

        BuildUI();
        RestoreSession();
        BindShortcuts();

        FormClosing += (_, _) => SaveSession();
        Resize      += (_, _) => { _cfg.FormW = Width; _cfg.FormH = Height; };
    }

    // ═════════════════════════════════════════════════════════════════════
    // BUILD UI
    // ═════════════════════════════════════════════════════════════════════

    private void BuildUI()
    {
        var toolbar  = BuildToolbar();
        var statusBar = BuildStatusBar();
        var mainPanel = new Panel { Dock = DockStyle.Fill, BackColor = Theme.BG };
        BuildMainPanel(mainPanel);

        Controls.Add(mainPanel);
        Controls.Add(toolbar);
        Controls.Add(statusBar);
    }

    // ── Toolbar (top 3 rows) ──────────────────────────────────────────────

    private Panel BuildToolbar()
    {
        var toolbar = new Panel
        {
            Dock = DockStyle.Top, Height = 106, BackColor = Theme.Card,
            Padding = new Padding(8, 4, 8, 4),
        };

        // Row 0 — Model
        var r0 = Theme.Row(); r0.Margin = new Padding(0, 2, 0, 2);
        _cmbModel = Theme.Cmb(w: 340);
        _cmbModel.Items.AddRange(_cfg.ModelHistory.ToArray());
        if (_cfg.ModelHistory.Count > 0) _cmbModel.Text = _cfg.ModelHistory[0];
        var btnBrowseModel = Theme.Btn("📂 Model…");
        var btnLoadModel   = Theme.Btn("⚡ Load", Theme.Accent);
        var btnYaml        = Theme.Btn("📋 YAML…");
        _lblModelInfo = Theme.Lbl("Chưa load model", fg: Theme.Dim);
        _lblModelInfo.Margin = new Padding(8, 0, 0, 0);

        r0.Controls.AddRange([Theme.Lbl("Model:", Theme.FBold),
            _cmbModel, btnBrowseModel, btnLoadModel, btnYaml, _lblModelInfo]);

        // Row 1 — Path
        var r1 = Theme.Row(); r1.Margin = new Padding(0, 2, 0, 2);
        _cmbPath = Theme.Cmb(w: 380);
        _cmbPath.Items.AddRange(_cfg.ImageHistory.ToArray());
        if (_cfg.ImageHistory.Count > 0) _cmbPath.Text = _cfg.ImageHistory[0];
        var btnBrowseImg  = Theme.Btn("📂 Ảnh…");
        var btnBrowseDir  = Theme.Btn("📁 Thư mục…");
        var btnLoad       = Theme.Btn("▶ Tải", Theme.Accent);
        _chkSub           = Theme.Chk("Sub-folder", _cfg.ScanSubfolders);

        r1.Controls.AddRange([Theme.Lbl("Path:", Theme.FBold),
            _cmbPath, btnBrowseImg, btnBrowseDir, btnLoad, _chkSub]);

        // Row 2 — Params
        var r2 = Theme.Row(); r2.Margin = new Padding(0, 2, 0, 2);
        _sldConf = Theme.Slider(0, 100, (int)(_cfg.Conf * 100), 120);
        _lblConf = Theme.Lbl($"{_cfg.Conf:F2}");
        _sldIou  = Theme.Slider(0, 100, (int)(_cfg.Iou  * 100), 120);
        _lblIou  = Theme.Lbl($"{_cfg.Iou:F2}");
        _btnDetectAll = Theme.Btn("⚡ Detect All");
        _btnStop      = Theme.Btn("■ Stop",  Theme.Err) ;
        _btnStop.Visible = false;
        _pbDetect     = new ProgressBar { Width = 140, Height = 18, Visible = false,
            Style = ProgressBarStyle.Continuous };
        _lblCacheInfo = Theme.Lbl("Cache: 0/0", fg: Theme.Dim);

        r2.Controls.AddRange([Theme.Lbl("Conf:"), _sldConf, _lblConf,
            Theme.Lbl("  IoU:"), _sldIou, _lblIou,
            new Label { Width = 10, BackColor = Color.Transparent },
            _btnDetectAll, _btnStop, _pbDetect, _lblCacheInfo]);

        // Stack rows
        toolbar.Controls.Add(r2); toolbar.Controls.Add(r1); toolbar.Controls.Add(r0);
        r0.Dock = r1.Dock = r2.Dock = DockStyle.Top;

        // Wire events
        btnBrowseModel.Click += OnBrowseModel;
        btnLoadModel.Click   += OnLoadModel;
        btnYaml.Click        += OnLoadYaml;
        _cmbModel.KeyDown    += (s, e) => { if (e.KeyCode == Keys.Return) OnLoadModel(s, e); };

        btnBrowseImg.Click   += (_, _) => BrowseFile();
        btnBrowseDir.Click   += (_, _) => BrowseFolder();
        btnLoad.Click        += OnLoadPath;
        _cmbPath.KeyDown     += (s, e) => { if (e.KeyCode == Keys.Return) OnLoadPath(s, e); };

        _sldConf.ValueChanged += (_, _) => { _cfg.Conf = _sldConf.Value / 100f; _lblConf.Text = $"{_cfg.Conf:F2}"; RefreshCurrentDetect(); };
        _sldIou.ValueChanged  += (_, _) => { _cfg.Iou  = _sldIou.Value  / 100f; _lblIou.Text  = $"{_cfg.Iou:F2}"; };
        _btnDetectAll.Click   += OnDetectAll;
        _btnStop.Click        += (_, _) => _detectCts?.Cancel();

        return toolbar;
    }

    // ── Status bar ────────────────────────────────────────────────────────

    private Panel BuildStatusBar()
    {
        var bar = new Panel { Dock = DockStyle.Bottom, Height = 24, BackColor = Theme.NavyDk };
        _lblStatus = Theme.Lbl("Sẵn sàng");
        _lblStatus.Dock = DockStyle.Fill;
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

    // ── Left panel (image list) ───────────────────────────────────────────

    private void BuildLeftPanel(Panel p)
    {
        // Search
        var searchRow = Theme.Row();
        searchRow.Dock = DockStyle.Top;
        _txtSearch = new TextBox {
            Width = 150, BackColor = Theme.Card, ForeColor = Theme.Txt,
            BorderStyle = BorderStyle.FixedSingle, Font = Theme.FMain,
        };
        _txtSearch.TextChanged += (_, _) => RebuildTree();
        searchRow.Controls.AddRange([Theme.Lbl("🔍"), _txtSearch]);

        // Filter chips
        var filterRow = Theme.Row(); filterRow.Dock = DockStyle.Top;
        _btnAllFilter   = MakeFilterBtn("Tất cả", "all");
        _btnOkFilter    = MakeFilterBtn("✓ Đúng",  "ok");
        _btnWrongFilter = MakeFilterBtn("✗ Sai",   "wrong");
        _btnUnrevFilter = MakeFilterBtn("?",        "none");
        filterRow.Controls.AddRange([_btnAllFilter, _btnOkFilter, _btnWrongFilter, _btnUnrevFilter]);
        HighlightFilter();

        // Detect filter
        var detRow = Theme.Row(); detRow.Dock = DockStyle.Top;
        _cmbClassFlt = Theme.Cmb(["Tất cả"], readOnly: true, w: 90);
        _nudDetMin   = Theme.Num(0, 99, 0, 48);
        _nudDetMax   = Theme.Num(0, 99, 99, 48);
        detRow.Controls.AddRange([Theme.Lbl("Class:"), _cmbClassFlt,
            new Label { Width = 4, BackColor = Color.Transparent },
            Theme.Lbl("#Det:"), _nudDetMin, Theme.Lbl("–"), _nudDetMax]);

        // TreeView
        _tree = new TreeView {
            Dock = DockStyle.Fill, BackColor = Theme.Card, ForeColor = Theme.Txt,
            BorderStyle = BorderStyle.None, ShowRootLines = false, ShowLines = true,
            ItemHeight = 18, Font = Theme.FSm,
        };
        _tree.AfterSelect += OnTreeSelect;

        // Pack
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
        b.Height  = 22; b.Font = Theme.FSm;
        b.Click  += (_, _) => { _activeFilter = filter; HighlightFilter(); RebuildTree(); };
        return b;
    }

    // ── Center panel (canvas + nav + filmstrip) ───────────────────────────

    private void BuildCenterPanel(Panel p)
    {
        // Filmstrip
        var filmPanel = new Panel {
            Dock = DockStyle.Bottom, Height = _cfg.SplitFilm, BackColor = Theme.Deep
        };
        var filmScroll = new Panel {
            Dock = DockStyle.Fill, AutoScroll = true, BackColor = Theme.Deep
        };
        _filmstrip = new FlowLayoutPanel {
            FlowDirection = FlowDirection.LeftToRight, AutoSize = true,
            WrapContents = false, BackColor = Theme.Deep,
        };
        filmScroll.Controls.Add(_filmstrip);
        filmPanel.Controls.Add(filmScroll);
        filmPanel.Controls.Add(Theme.SectionHdr("Filmstrip"));

        // Nav row
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
        nr.Controls.AddRange([btnPrev, _lblNav, btnNext,
            new Label { Width = 12, BackColor = Color.Transparent },
            zoomOut, zoomIn, zoomFit, _chkOrig]);
        navRow.Controls.Add(nr);

        // Canvas
        _canvas = new ImageCanvas { Dock = DockStyle.Fill, BackColor = Theme.Deep };

        p.Controls.Add(_canvas);
        p.Controls.Add(navRow);
        p.Controls.Add(filmPanel);
    }

    // ── Right panel (results, marks, filter) ─────────────────────────────

    private void BuildRightPanel(Panel p)
    {
        p.Padding = new Padding(4);

        // Image path
        _lblImgPath = Theme.Lbl("", fg: Theme.Dim); _lblImgPath.Font = Theme.FSm;
        _lblImgPath.Dock = DockStyle.Top; _lblImgPath.Height = 32;
        _lblImgPath.AutoSize = false;

        // Detection list
        _lstResult = new ListView {
            Dock = DockStyle.Fill, BackColor = Theme.Card, ForeColor = Theme.Txt,
            View = View.Details, FullRowSelect = true, GridLines = false,
            BorderStyle = BorderStyle.None, Font = Theme.FSm,
            MultiSelect = false,
        };
        _lstResult.Columns.Add("Class",  90);
        _lstResult.Columns.Add("Conf",   55);
        _lstResult.Columns.Add("W×H",    65);

        // Mark section
        var markHdr = Theme.SectionHdr("Đánh giá");
        var markRow = Theme.Row(); markRow.Dock = DockStyle.Bottom;
        _btnOk        = Theme.Btn("✓ Đúng [Enter]", Theme.Ok);
        _btnWrong     = Theme.Btn("✗ Sai [Del]",    Theme.Err);
        _btnClearMark = Theme.Btn("↺ Xóa");
        foreach (var b in new[] { _btnOk, _btnWrong, _btnClearMark }) b.Height = 24;
        _lblMark  = Theme.Lbl("", fg: Theme.Dim); _lblMark.Font = Theme.FSm;
        markRow.Controls.AddRange([_btnOk, _btnWrong, _btnClearMark]);

        var wrongRow = Theme.Row(); wrongRow.Dock = DockStyle.Bottom;
        _cmbWrongDir = Theme.Cmb(w: 130);
        _cmbWrongDir.Text = _cfg.WrongFolder;
        var btnWrongBrowse = Theme.Btn("📁"); btnWrongBrowse.Height = 24;
        _btnSaveWrong = Theme.Btn("💾 Lưu sai"); _btnSaveWrong.Height = 24;
        wrongRow.Controls.AddRange([_cmbWrongDir, btnWrongBrowse, _btnSaveWrong]);

        // Timing label (giữa listview và mark section)
        _lblTiming = Theme.Lbl("", fg: Theme.Dim);
        _lblTiming.Font   = Theme.FMono;
        _lblTiming.Dock   = DockStyle.Bottom;
        _lblTiming.Height = 32;
        _lblTiming.AutoSize = false;
        _lblTiming.TextAlign = ContentAlignment.MiddleLeft;
        _lblTiming.Padding   = new Padding(2, 0, 0, 0);

        p.Controls.Add(_lstResult);
        p.Controls.Add(_lblTiming);
        p.Controls.Add(_lblMark);
        p.Controls.Add(wrongRow);
        p.Controls.Add(markRow);
        p.Controls.Add(markHdr);
        p.Controls.Add(_lblImgPath);

        // Wire
        _btnOk.Click         += (_, _) => SetReview(ReviewState.Ok);
        _btnWrong.Click      += (_, _) => SetReview(ReviewState.Wrong);
        _btnClearMark.Click  += (_, _) => SetReview(ReviewState.None);
        _btnSaveWrong.Click  += OnSaveWrong;
        btnWrongBrowse.Click += (_, _) =>
        {
            using var d = new FolderBrowserDialog();
            if (d.ShowDialog() == DialogResult.OK) _cmbWrongDir.Text = d.SelectedPath;
        };
        _cmbWrongDir.Leave += (_, _) => _cfg.WrongFolder = _cmbWrongDir.Text;
    }

    // ═════════════════════════════════════════════════════════════════════
    // EVENT HANDLERS — Model
    // ═════════════════════════════════════════════════════════════════════

    private void OnBrowseModel(object? s, EventArgs e)
    {
        // Hỏi user: chọn file .xml/.onnx hay chọn folder (openvino_model/)
        var choice = MessageBox.Show(
            "Chọn 'Yes' để duyệt FOLDER openvino_model/\n" +
            "Chọn 'No'  để duyệt FILE (.xml hoặc .onnx)",
            "Chọn model", MessageBoxButtons.YesNoCancel, MessageBoxIcon.Question);

        if (choice == DialogResult.Yes)
        {
            using var d = new FolderBrowserDialog
            {
                Description = "Chọn folder chứa model OpenVINO (có file .xml bên trong)",
                UseDescriptionForTitle = true,
            };
            if (d.ShowDialog() == DialogResult.OK)
            {
                _cmbModel.Text = d.SelectedPath;
                OnLoadModel(s, e);
            }
        }
        else if (choice == DialogResult.No)
        {
            using var d = new OpenFileDialog
            {
                Title  = "Chọn file model OpenVINO / ONNX",
                Filter = "Model files|*.xml;*.onnx|OpenVINO IR|*.xml|ONNX|*.onnx",
            };
            if (d.ShowDialog() == DialogResult.OK)
            {
                _cmbModel.Text = d.FileName;
                OnLoadModel(s, e);
            }
        }
    }

    private async void OnLoadModel(object? s, EventArgs e)
    {
        var path = _cmbModel.Text.Trim();
        if (string.IsNullOrEmpty(path)) return;

        SetStatus($"Đang load model: {Path.GetFileName(path)}…");
        _lblModelInfo.Text = "⏳ Loading…"; _lblModelInfo.ForeColor = Theme.Warn;
        _btnDetectAll.Enabled = false;

        try
        {
            await Task.Run(() => _yolo.LoadModel(path));
            _cfg.PushModelHistory(path);
            RefreshModelCombo();
            UpdateModelInfoLabel();
            UpdateClassFilterCombo();
            _cache.Clear();
            UpdateCacheLabel();
            SetStatus($"Model loaded: {Path.GetFileName(path)} — {_yolo.NumClasses} class(es)");
        }
        catch (Exception ex)
        {
            _lblModelInfo.Text = "✗ Load thất bại"; _lblModelInfo.ForeColor = Theme.Err;
            MessageBox.Show($"Lỗi load model:\n{ex.Message}", "Load Model",
                MessageBoxButtons.OK, MessageBoxIcon.Error);
            SetStatus("Lỗi load model.");
        }
        finally
        {
            _btnDetectAll.Enabled = true;
        }
    }

    private void OnLoadYaml(object? s, EventArgs e)
    {
        using var d = new OpenFileDialog
        {
            Title = "Chọn data.yaml (class names)", Filter = "YAML|*.yaml;*.yml"
        };
        if (d.ShowDialog() != DialogResult.OK) return;
        try
        {
            var names = YoloRunner.LoadClassNamesFromYaml(d.FileName);
            if (names.Length == 0) { MessageBox.Show("Không tìm thấy names: trong file YAML."); return; }
            _yolo.ClassNames = names;
            UpdateModelInfoLabel();
            UpdateClassFilterCombo();
            _cache.Clear();
            SetStatus($"Loaded {names.Length} class names từ YAML.");
        }
        catch (Exception ex) { MessageBox.Show($"Lỗi đọc YAML:\n{ex.Message}"); }
    }

    // ═════════════════════════════════════════════════════════════════════
    // EVENT HANDLERS — Path / Images
    // ═════════════════════════════════════════════════════════════════════

    private void BrowseFile()
    {
        using var d = new OpenFileDialog
        {
            Title  = "Chọn ảnh", Multiselect = false,
            Filter = "Images|*.jpg;*.jpeg;*.png;*.bmp;*.webp",
        };
        if (d.ShowDialog() == DialogResult.OK) { _cmbPath.Text = d.FileName; OnLoadPath(null, EventArgs.Empty); }
    }

    private void BrowseFolder()
    {
        using var d = new FolderBrowserDialog { Description = "Chọn thư mục ảnh" };
        if (d.ShowDialog() == DialogResult.OK) { _cmbPath.Text = d.SelectedPath; OnLoadPath(null, EventArgs.Empty); }
    }

    private void OnLoadPath(object? s, EventArgs e)
    {
        var path = _cmbPath.Text.Trim();
        if (string.IsNullOrEmpty(path)) return;

        _cfg.PushImageHistory(path);
        RefreshPathCombo();

        var exts = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
            { ".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tiff" };

        if (File.Exists(path) && exts.Contains(Path.GetExtension(path)))
        {
            _imageList = [path];
        }
        else if (Directory.Exists(path))
        {
            var opt = _chkSub.Checked ? SearchOption.AllDirectories : SearchOption.TopDirectoryOnly;
            _imageList = Directory.GetFiles(path, "*.*", opt)
                .Where(f => exts.Contains(Path.GetExtension(f)))
                .OrderBy(f => f)
                .ToList();
        }
        else { SetStatus("Đường dẫn không hợp lệ."); return; }

        _cache.Clear();
        UpdateCacheLabel();
        _currentIdx = -1;
        RebuildTree();
        SetStatus($"Loaded {_imageList.Count} ảnh.");

        if (_imageList.Count > 0) NavigateTo(0);
    }

    // ═════════════════════════════════════════════════════════════════════
    // TREE & NAVIGATION
    // ═════════════════════════════════════════════════════════════════════

    private void RebuildTree()
    {
        _tree.BeginUpdate();
        _tree.Nodes.Clear();

        var filtered = GetFilteredImages();
        var grouped  = filtered.GroupBy(p => Path.GetDirectoryName(p) ?? "");

        foreach (var grp in grouped.OrderBy(g => g.Key))
        {
            var folderNode = new TreeNode(Path.GetFileName(grp.Key.TrimEnd('\\', '/')) ?? grp.Key)
            {
                ForeColor = Theme.Dim, Tag = null,
            };
            foreach (var imgPath in grp)
            {
                var state = _review.GetValueOrDefault(imgPath, ReviewState.None);
                var node  = new TreeNode(Path.GetFileName(imgPath))
                {
                    Tag      = imgPath,
                    ForeColor = state == ReviewState.Ok    ? Theme.Ok  :
                                state == ReviewState.Wrong ? Theme.Err : Theme.Txt,
                };
                if (_cache.TryGetValue(imgPath, out var boxes))
                    node.Text += $"  [{boxes.Count}]";
                folderNode.Nodes.Add(node);
            }
            _tree.Nodes.Add(folderNode);
        }

        // Expand all if few nodes
        if (_tree.Nodes.Count <= 10) _tree.ExpandAll();
        _tree.EndUpdate();
    }

    private List<string> GetFilteredImages()
    {
        var search  = _txtSearch.Text.Trim().ToLowerInvariant();
        var clsFlt  = _cmbClassFlt.SelectedIndex > 0 ? _cmbClassFlt.Text : null;
        int detMin  = (int)_nudDetMin.Value;
        int detMax  = (int)_nudDetMax.Value;

        return _imageList.Where(p =>
        {
            // Search by filename
            if (search.Length > 0 && !Path.GetFileName(p).ToLowerInvariant().Contains(search))
                return false;

            // Review filter
            var state = _review.GetValueOrDefault(p, ReviewState.None);
            if (_activeFilter == "ok"    && state != ReviewState.Ok)    return false;
            if (_activeFilter == "wrong" && state != ReviewState.Wrong) return false;
            if (_activeFilter == "none"  && state != ReviewState.None)  return false;

            // Detection filter (only if cached)
            if (_cache.TryGetValue(p, out var boxes))
            {
                if (boxes.Count < detMin || boxes.Count > detMax) return false;
                if (clsFlt != null && boxes.All(b => b.ClassName != clsFlt)) return false;
            }

            return true;
        }).ToList();
    }

    private void OnTreeSelect(object? s, TreeViewEventArgs e)
    {
        if (e.Node?.Tag is string path)
        {
            int idx = _imageList.IndexOf(path);
            if (idx >= 0) NavigateTo(idx);
        }
    }

    private void Navigate(int delta)
    {
        if (_imageList.Count == 0) return;
        NavigateTo(Math.Clamp(_currentIdx + delta, 0, _imageList.Count - 1));
    }

    private void NavigateTo(int idx)
    {
        if (idx < 0 || idx >= _imageList.Count) return;
        _currentIdx = idx;
        LoadCurrentImage();
    }

    private void LoadCurrentImage()
    {
        if (_currentIdx < 0 || _currentIdx >= _imageList.Count) return;
        var path = _imageList[_currentIdx];

        // Load bitmap
        _origBmp?.Dispose();
        try { _origBmp = new Bitmap(path); }
        catch { _origBmp = null; }

        // Auto detect if model loaded
        if (_yolo.IsLoaded && !_cache.ContainsKey(path))
            DetectCurrent();

        RefreshCanvas();
        UpdateResultPanel(path);
        UpdateNavLabel();
        UpdateFilmstrip();
    }

    // ═════════════════════════════════════════════════════════════════════
    // DETECTION
    // ═════════════════════════════════════════════════════════════════════

    private void DetectCurrent()
    {
        if (!_yolo.IsLoaded || _origBmp is null || _currentIdx < 0) return;
        var path = _imageList[_currentIdx];
        if (_cache.ContainsKey(path)) return;

        try
        {
            var sw = System.Diagnostics.Stopwatch.StartNew();
            var boxes = _yolo.Detect(_origBmp, _cfg.Conf, _cfg.Iou);
            sw.Stop();
            _lastDetectMs = sw.ElapsedMilliseconds;
            _cache[path] = boxes;
        }
        catch { _cache[path] = []; }

        UpdateCacheLabel();
    }

    private void RefreshCurrentDetect()
    {
        if (_currentIdx < 0 || _currentIdx >= _imageList.Count) return;
        var path = _imageList[_currentIdx];
        _cache.TryRemove(path, out _);
        if (_yolo.IsLoaded && _origBmp is not null)
        {
            try
            {
                var sw = System.Diagnostics.Stopwatch.StartNew();
                _cache[path] = _yolo.Detect(_origBmp, _cfg.Conf, _cfg.Iou);
                sw.Stop();
                _lastDetectMs = sw.ElapsedMilliseconds;
            }
            catch { _cache[path] = []; _lastDetectMs = 0; }
        }
        RefreshCanvas();
        UpdateResultPanel(path);
    }

    private async void OnDetectAll(object? s, EventArgs e)
    {
        if (!_yolo.IsLoaded) { MessageBox.Show("Hãy load model trước."); return; }
        if (_imageList.Count == 0) { MessageBox.Show("Hãy load ảnh trước."); return; }
        if (_isDetecting) return;

        _isDetecting  = true;
        _batchTotalMs = 0;
        _batchCount   = 0;
        _detectCts    = new CancellationTokenSource();
        _btnDetectAll.Visible = false; _btnStop.Visible = true;
        _pbDetect.Maximum = _imageList.Count; _pbDetect.Value = 0; _pbDetect.Visible = true;

        var token     = _detectCts.Token;
        var batchSw   = System.Diagnostics.Stopwatch.StartNew();
        int processed = 0;
        float conf    = _cfg.Conf;
        float iou     = _cfg.Iou;
        int   total   = _imageList.Count;

        // Snapshot danh sách để tránh race với UI thread
        var images = _imageList.ToList();

        await Task.Run(() =>
        {
            var opts = new ParallelOptions
            {
                MaxDegreeOfParallelism = _yolo.Parallelism,
                CancellationToken      = token,
            };

            try
            {
                Parallel.ForEach(images, opts, path =>
                {
                    if (!_cache.ContainsKey(path))
                    {
                        var sw = System.Diagnostics.Stopwatch.StartNew();
                        List<DetectBox> boxes;
                        try
                        {
                            using var bmp = new Bitmap(path);
                            boxes = _yolo.Detect(bmp, conf, iou);
                        }
                        catch { boxes = []; }
                        sw.Stop();

                        _cache[path] = boxes;
                        Interlocked.Add(ref _batchTotalMs, sw.ElapsedMilliseconds);
                        Interlocked.Increment(ref _batchCount);
                    }

                    int p = Interlocked.Increment(ref processed);
                    if (p % 5 == 0 || p == total)
                    {
                        Invoke(() =>
                        {
                            _pbDetect.Value = Math.Min(p, _pbDetect.Maximum);
                            UpdateCacheLabel();
                            long cnt   = Interlocked.Read(ref _batchCount);
                            long tms   = Interlocked.Read(ref _batchTotalMs);
                            long avgMs = cnt > 0 ? tms / cnt : 0;
                            SetStatus($"Detecting… {p}/{total}  " +
                                      $"avg {avgMs}ms/ảnh  " +
                                      $"({(avgMs > 0 ? 1000f / avgMs : 0):F1} FPS)  " +
                                      $"[{_yolo.Parallelism} luồng]");
                        });
                    }
                });
            }
            catch (OperationCanceledException) { }
        });

        batchSw.Stop();
        _isDetecting = false;
        _btnDetectAll.Visible = true; _btnStop.Visible = false; _pbDetect.Visible = false;
        RebuildTree();
        RefreshCanvas();

        long finalCnt = Interlocked.Read(ref _batchCount);
        long finalAvg = finalCnt > 0 ? Interlocked.Read(ref _batchTotalMs) / finalCnt : 0;
        float fps     = finalAvg > 0 ? 1000f / finalAvg : 0;
        SetStatus($"✓ Detect All: {processed}/{_imageList.Count} ảnh  |  " +
                  $"avg {finalAvg}ms/ảnh  {fps:F1} FPS  |  " +
                  $"tổng {FormatDuration(batchSw.ElapsedMilliseconds)}  [{_yolo.Parallelism} luồng]");
    }

    // ═════════════════════════════════════════════════════════════════════
    // DISPLAY
    // ═════════════════════════════════════════════════════════════════════

    private void RefreshCanvas()
    {
        if (_origBmp is null) { _canvas.SetImage(null); return; }

        if (_chkOrig.Checked)
        {
            _canvas.SetImage(_origBmp, fit: false);
            return;
        }

        var path  = _currentIdx >= 0 ? _imageList[_currentIdx] : "";
        var boxes = _cache.GetValueOrDefault(path, []);
        var drew  = BboxRenderer.DrawBoxes(_origBmp, boxes);
        _canvas.SetImage(drew);
        drew.Dispose();
    }

    private void UpdateResultPanel(string path)
    {
        _lblImgPath.Text = Path.GetFileName(path);
        _lstResult.Items.Clear();

        bool fromCache = _cache.TryGetValue(path, out var boxes);
        if (!fromCache) { _lblTiming.Text = ""; return; }

        foreach (var b in boxes!)
        {
            var item = new ListViewItem(b.ClassName);
            item.SubItems.Add($"{b.Confidence:P0}");
            item.SubItems.Add($"{b.Width:F0}×{b.Height:F0}");
            item.ForeColor = Theme.BboxColor(b.ClassId);
            _lstResult.Items.Add(item);
        }

        // Timing
        if (_lastDetectMs > 0)
        {
            float fps = _lastDetectMs > 0 ? 1000f / _lastDetectMs : 0;
            _lblTiming.Text      = $"⏱ {_lastDetectMs}ms  ({fps:F1} FPS)  |  {boxes.Count} obj";
            _lblTiming.ForeColor = _lastDetectMs < 50  ? Theme.Ok   :
                                   _lastDetectMs < 200 ? Theme.Warn : Theme.Err;
        }
        else if (_batchCount > 0)
        {
            // Lấy từ batch stats (ảnh đã detect trước đó)
            long avg = _batchTotalMs / _batchCount;
            float fps = avg > 0 ? 1000f / avg : 0;
            _lblTiming.Text      = $"⏱ ~{avg}ms/ảnh  ({fps:F1} FPS avg)  |  {boxes.Count} obj";
            _lblTiming.ForeColor = Theme.Dim;
        }
        else
        {
            _lblTiming.Text = boxes.Count > 0 ? $"📦 {boxes.Count} đối tượng (cached)" : "";
            _lblTiming.ForeColor = Theme.Dim;
        }

        var state = _review.GetValueOrDefault(path, ReviewState.None);
        _lblMark.Text = state switch {
            ReviewState.Ok    => "✓ Đã đánh dấu ĐÚNG",
            ReviewState.Wrong => "✗ Đã đánh dấu SAI",
            _ => ""
        };
        _lblMark.ForeColor = state == ReviewState.Ok ? Theme.Ok :
                             state == ReviewState.Wrong ? Theme.Err : Theme.Dim;
    }

    private void UpdateNavLabel()
    {
        _lblNav.Text = _imageList.Count > 0
            ? $"  {_currentIdx + 1} / {_imageList.Count}  "
            : "  –  ";
    }

    private void UpdateFilmstrip()
    {
        _filmstrip.Controls.Clear();

        // Show 30 images centered around current
        int half  = 15;
        int start = Math.Max(0, _currentIdx - half);
        int end   = Math.Min(_imageList.Count - 1, start + 30);

        for (int i = start; i <= end; i++)
        {
            var idx  = i;
            var path = _imageList[i];

            var cell = new Panel {
                Width = 84, Height = 66, BackColor = Theme.Deep, Margin = new Padding(2),
                Cursor = Cursors.Hand,
            };

            // Border = review state / selected
            var state     = _review.GetValueOrDefault(path, ReviewState.None);
            cell.BackColor = idx == _currentIdx ? Theme.Accent :
                             state == ReviewState.Ok    ? Theme.Ok  :
                             state == ReviewState.Wrong ? Theme.Err : Theme.Border;

            // Thumb
            var pb = new PictureBox {
                Width = 80, Height = 60, Location = new Point(2, 2),
                SizeMode = PictureBoxSizeMode.StretchImage,
                BackColor = Theme.Deep,
            };

            // Load thumb async
            Task.Run(() =>
            {
                try
                {
                    using var bmp  = new Bitmap(path);
                    var boxes      = _cache.GetValueOrDefault(path, []);
                    var thumb      = BboxRenderer.MakeThumb(bmp, boxes, 80, 60);
                    if (!pb.IsDisposed) pb.Invoke(() => { pb.Image?.Dispose(); pb.Image = thumb; });
                }
                catch { }
            });

            cell.Click += (_, _) => NavigateTo(idx);
            pb.Click   += (_, _) => NavigateTo(idx);
            cell.Controls.Add(pb);
            _filmstrip.Controls.Add(cell);
        }
    }

    // ═════════════════════════════════════════════════════════════════════
    // REVIEW / MARKS
    // ═════════════════════════════════════════════════════════════════════

    private void SetReview(ReviewState state)
    {
        if (_currentIdx < 0) return;
        var path = _imageList[_currentIdx];
        if (state == ReviewState.None) _review.Remove(path);
        else _review[path] = state;

        UpdateResultPanel(path);
        UpdateFilmstrip();
        RebuildTree();
    }

    private void OnSaveWrong(object? s, EventArgs e)
    {
        if (_currentIdx < 0) return;
        var dest = _cmbWrongDir.Text.Trim();
        if (string.IsNullOrEmpty(dest)) { MessageBox.Show("Chưa chọn thư mục lưu ảnh sai."); return; }
        try
        {
            Directory.CreateDirectory(dest);
            var src      = _imageList[_currentIdx];
            var destFile = Path.Combine(dest, Path.GetFileName(src));
            File.Copy(src, destFile, overwrite: true);
            SetReview(ReviewState.Wrong);
            SetStatus($"Đã lưu: {Path.GetFileName(destFile)}");
        }
        catch (Exception ex) { MessageBox.Show($"Lỗi lưu file:\n{ex.Message}"); }
    }

    // ═════════════════════════════════════════════════════════════════════
    // UI HELPERS
    // ═════════════════════════════════════════════════════════════════════

    private void UpdateModelInfoLabel()
    {
        if (!_yolo.IsLoaded)
        {
            _lblModelInfo.Text = "Chưa load model"; _lblModelInfo.ForeColor = Theme.Dim; return;
        }
        var names = string.Join(", ", _yolo.ClassNames.Take(6));
        if (_yolo.ClassNames.Length > 6) names += "…";
        _lblModelInfo.Text = $"✓ {Path.GetFileName(_yolo.ModelPath)}  " +
                             $"In:{_yolo.InputW}×{_yolo.InputH}  " +
                             $"Classes:{_yolo.NumClasses} [{names}]";
        _lblModelInfo.ForeColor = Theme.Ok;
    }

    private void UpdateClassFilterCombo()
    {
        _cmbClassFlt.Items.Clear();
        _cmbClassFlt.Items.Add("Tất cả");
        foreach (var n in _yolo.ClassNames) _cmbClassFlt.Items.Add(n);
        _cmbClassFlt.SelectedIndex = 0;
    }

    private void UpdateCacheLabel() =>
        _lblCacheInfo.Text = $"Cache: {_cache.Count}/{_imageList.Count}";

    private void HighlightFilter()
    {
        var btns = new[] { _btnAllFilter, _btnOkFilter, _btnWrongFilter, _btnUnrevFilter };
        var fltrs = new[] { "all", "ok", "wrong", "none" };
        for (int i = 0; i < btns.Length; i++)
            btns[i].BackColor = fltrs[i] == _activeFilter ? Theme.Navy : Theme.Card;
    }

    private void RefreshModelCombo()
    {
        _cmbModel.Items.Clear();
        _cmbModel.Items.AddRange(_cfg.ModelHistory.ToArray());
        if (_cfg.ModelHistory.Count > 0) _cmbModel.Text = _cfg.ModelHistory[0];
    }

    private void RefreshPathCombo()
    {
        _cmbPath.Items.Clear();
        _cmbPath.Items.AddRange(_cfg.ImageHistory.ToArray());
        if (_cfg.ImageHistory.Count > 0) _cmbPath.Text = _cfg.ImageHistory[0];
    }

    private void SetStatus(string msg) => _lblStatus.Text = msg;

    private static string FormatDuration(long ms)
    {
        if (ms < 1000)  return $"{ms}ms";
        if (ms < 60000) return $"{ms / 1000.0:F1}s";
        return $"{ms / 60000}m {(ms % 60000) / 1000}s";
    }

    // ═════════════════════════════════════════════════════════════════════
    // KEYBOARD SHORTCUTS
    // ═════════════════════════════════════════════════════════════════════

    private void BindShortcuts()
    {
        KeyPreview = true;
        KeyDown += (_, e) =>
        {
            switch (e.KeyCode)
            {
                case Keys.Left:  Navigate(-1); e.Handled = true; break;
                case Keys.Right: Navigate(+1); e.Handled = true; break;
                case Keys.Return when _currentIdx >= 0:
                    SetReview(ReviewState.Ok);   e.Handled = true; break;
                case Keys.Delete when _currentIdx >= 0:
                    SetReview(ReviewState.Wrong); e.Handled = true; break;
                case Keys.Escape: _detectCts?.Cancel(); break;
                case Keys.F5:    _btnDetectAll.PerformClick(); e.Handled = true; break;
                case Keys.O when e.Control: BrowseFolder(); e.Handled = true; break;
                case Keys.M when e.Control: OnBrowseModel(this, e); e.Handled = true; break;
            }
        };
    }

    // ═════════════════════════════════════════════════════════════════════
    // SESSION SAVE / RESTORE
    // ═════════════════════════════════════════════════════════════════════

    private void RestoreSession()
    {
        _sldConf.Value = (int)(_cfg.Conf * 100);
        _sldIou.Value  = (int)(_cfg.Iou  * 100);
        _chkOrig.Checked = _cfg.ShowOriginal;
        _cmbWrongDir.Text = _cfg.WrongFolder;

        // Handle cả file path và folder path (openvino_model/)
        if (!string.IsNullOrEmpty(_cfg.ModelPath) &&
            (File.Exists(_cfg.ModelPath) || Directory.Exists(_cfg.ModelPath)))
        {
            _cmbModel.Text = _cfg.ModelPath;
            OnLoadModel(this, EventArgs.Empty);
        }
        if (!string.IsNullOrEmpty(_cfg.ImagePath) &&
            (File.Exists(_cfg.ImagePath) || Directory.Exists(_cfg.ImagePath)))
        {
            _cmbPath.Text = _cfg.ImagePath;
            OnLoadPath(this, EventArgs.Empty);
        }
    }

    private void SaveSession()
    {
        _cfg.ModelPath   = _cmbModel.Text;
        _cfg.ImagePath   = _cmbPath.Text;
        _cfg.WrongFolder = _cmbWrongDir.Text;
        _cfg.ScanSubfolders = _chkSub.Checked;
        _cfg.ShowOriginal   = _chkOrig.Checked;
        _cfg.Save();
    }

    // ═════════════════════════════════════════════════════════════════════
    // DISPOSE
    // ═════════════════════════════════════════════════════════════════════

    protected override void Dispose(bool disposing)
    {
        if (disposing)
        {
            _detectCts?.Dispose();
            _origBmp?.Dispose();
            _yolo.Dispose();
            foreach (var b in _cache.Values.SelectMany(x => x)) { /* DetectBox is record, no dispose needed */ }
        }
        base.Dispose(disposing);
    }
}
