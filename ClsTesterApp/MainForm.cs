using ClsTester.Data;
using ClsTester.Forms;
using ClsTester.Inference;
using ClsTester.Models;
using ClsTester.UI;
using ClsTester.Workers;

namespace ClsTester;

/// <summary>
/// KZTEK Cls Tester — Form chính, hỗ trợ nhiều camera đồng thời.
///
/// Layout:
///   ┌─ Toolbar (model, device, conf, topN, interval, folder) ───────────────┐
///   ├─ Camera list (left, 180px) ──┬─ Video (flex) ─┬─ Right panel (flex) ──┤
///   │  [● Cam1] ▶ ✎ ✕             │  PictureBox     │  Region states        │
///   │  [● Cam2] ▶ ✎ ✕             │  bbox overlay   │  Event log            │
///   │  [➕ Thêm]                   │                 │                       │
///   └─ Status bar ──────────────────────────────────────────────────────────┘
///
/// Timer 200 ms:
///   • Cập nhật PictureBox từ active camera worker
///   • Vẽ bbox overlay cho active camera
///   • Refresh region state list (active camera)
///   • Flush events từ TẤT CẢ workers → event log
/// </summary>
public sealed partial class MainForm : Form
{
    // ── Core ──────────────────────────────────────────────────────────────
    private readonly AppSettings      _cfg    = AppSettings.Load();
    private readonly ClassifierRunner _runner = new();
    private readonly ClsDb            _db;

    // ── Multi-camera workers ──────────────────────────────────────────────
    private readonly Dictionary<string, StreamWorker> _workers    = [];
    private readonly Dictionary<string, Button>       _toggleBtns = [];
    private string _activeCamId = "";

    // ── UI controls ───────────────────────────────────────────────────────
    private ComboBox        _cmbModel     = null!;
    private ComboBox        _cmbDevice    = null!;
    private NumericUpDown   _nudConf      = null!;
    private NumericUpDown   _nudTopN      = null!;
    private NumericUpDown   _nudInterval  = null!;
    private Label           _lblModel     = null!;
    private TextBox         _txtImgFolder = null!;
    private Label           _lblVideoInfo = null!;
    private PictureBox      _pb           = null!;
    private ListView        _lvRegions    = null!;
    private ListView        _lvEvents     = null!;
    private Label           _lblStatus    = null!;
    private Label           _lblDbCount   = null!;
    private SplitContainer  _rightSplit   = null!;
    private FlowLayoutPanel _camFlow      = null!;

    // ── Cached render state (UI thread only) ──────────────────────────────
    private List<RegionClsState> _paintStates    = [];
    private long                 _cachedDbCount;
    private string               _lastStatusText = "";

    private readonly System.Windows.Forms.Timer _timer;
    private readonly Font _overlayFont = new("Segoe UI Semibold", 8.5f);

    // ══════════════════════════════════════════════════════════════════════
    // CONSTRUCTOR
    // ══════════════════════════════════════════════════════════════════════

    public MainForm()
    {
        _db = new ClsDb(_cfg.DbPath);

        Text           = "KZTEK — Cls Tester  (Multi-Camera + OpenVINO)";
        Size           = new Size(_cfg.FormW, _cfg.FormH);
        MinimumSize    = new Size(1000, 640);
        BackColor      = Theme.BG;
        ForeColor      = Theme.Txt;
        Font           = Theme.FMain;
        DoubleBuffered = true;

        BuildUI();
        RestoreSession();
        BindAutoSave();

        _timer = new System.Windows.Forms.Timer { Interval = 200 };
        _timer.Tick += OnTimerTick;
        _timer.Start();

        FormClosing += (_, _) => OnClose();
        Resize      += (_, _) => { _cfg.FormW = Width; _cfg.FormH = Height; };
        Shown       += (_, _) =>
        {
            if (_cfg.RightSplitDist > 80)
                try { _rightSplit.SplitterDistance = _cfg.RightSplitDist; } catch { }
        };
        KeyPreview = true;
        KeyDown   += OnKeyDown;
    }

    // ══════════════════════════════════════════════════════════════════════
    // BUILD UI
    // ══════════════════════════════════════════════════════════════════════

    private void BuildUI()
    {
        var toolbar = BuildToolbar();
        var content = BuildContent();
        _lblStatus = new Label
        {
            Dock = DockStyle.Bottom, Height = 24,
            BackColor = Theme.NavyDk, ForeColor = Theme.Dim,
            TextAlign = ContentAlignment.MiddleLeft,
            Padding   = new Padding(10, 0, 0, 0),
            Text      = "Sẵn sàng",
        };
        Controls.AddRange([content, toolbar, _lblStatus]);
    }

    private Panel BuildToolbar()
    {
        var bar = new Panel { Dock = DockStyle.Top, Height = 84, BackColor = Theme.Card };

        // Row 0: Model
        int x = 8, y = 8;
        bar.Controls.Add(MkLbl("Model:", x, y + 2)); x += 52;
        _cmbModel = new ComboBox
        {
            Left = x, Top = y, Width = 310, DropDownStyle = ComboBoxStyle.DropDown,
            BackColor = Theme.Deep, ForeColor = Theme.Txt,
        };
        bar.Controls.Add(_cmbModel); x += 314;

        var btnBrowse = Theme.Btn("📁", Theme.Card);
        btnBrowse.SetBounds(x, y - 1, 34, 26); btnBrowse.Click += OnBrowseModel;
        bar.Controls.Add(btnBrowse); x += 38;

        var btnLoad = Theme.Btn("⚙ Load", Theme.Accent);
        btnLoad.SetBounds(x, y - 1, 80, 26); btnLoad.Click += OnLoadModel;
        bar.Controls.Add(btnLoad); x += 88;

        bar.Controls.Add(MkLbl("Device:", x, y + 2)); x += 52;
        _cmbDevice = new ComboBox
        {
            Left = x, Top = y, Width = 86, DropDownStyle = ComboBoxStyle.DropDownList,
            BackColor = Theme.Deep, ForeColor = Theme.Txt,
        };
        _cmbDevice.Items.AddRange(["CPU", "GPU", "AUTO"]);
        _cmbDevice.SelectedIndex = 0;
        bar.Controls.Add(_cmbDevice); x += 92;

        bar.Controls.Add(MkLbl("Conf%:", x, y + 2)); x += 46;
        _nudConf = Theme.Num(1, 99, (decimal)(_cfg.Conf * 100), 55);
        _nudConf.SetBounds(x, y, 55, 24); bar.Controls.Add(_nudConf); x += 62;

        bar.Controls.Add(MkLbl("Top-N:", x, y + 2)); x += 46;
        _nudTopN = Theme.Num(1, 10, _cfg.TopN, 48);
        _nudTopN.SetBounds(x, y, 48, 24); bar.Controls.Add(_nudTopN);

        // Row 1: model info
        _lblModel = new Label
        {
            Left = 8, Top = 36, Width = bar.Width - 16, Height = 16,
            Anchor = AnchorStyles.Left | AnchorStyles.Right | AnchorStyles.Top,
            Text = "Chưa load model", ForeColor = Theme.Dim, BackColor = Color.Transparent,
            Font = Theme.FSm,
        };
        bar.Controls.Add(_lblModel);

        // Row 2: Image folder + Interval + video info
        x = 8; y = 56;
        bar.Controls.Add(MkLbl("Lưu ảnh:", x, y + 2)); x += 64;
        _txtImgFolder = new TextBox
        {
            Left = x, Top = y, Width = 280,
            BackColor = Theme.Deep, ForeColor = Theme.Txt, BorderStyle = BorderStyle.FixedSingle,
        };
        bar.Controls.Add(_txtImgFolder); x += 284;

        var btnFld = Theme.Btn("📁", Theme.Card);
        btnFld.SetBounds(x, y - 1, 34, 26); btnFld.Click += OnBrowseImgFolder;
        bar.Controls.Add(btnFld); x += 42;

        bar.Controls.Add(MkLbl("Interval(ms):", x, y + 2)); x += 90;
        _nudInterval = Theme.Num(100, 60000, _cfg.IntervalMs, 70);
        _nudInterval.Increment = 100;
        _nudInterval.SetBounds(x, y, 70, 24); bar.Controls.Add(_nudInterval); x += 78;

        _lblVideoInfo = new Label
        {
            Left = x, Top = y + 3, Width = 380, Height = 16,
            ForeColor = Theme.Dim, BackColor = Color.Transparent, Font = Theme.FSm,
        };
        bar.Controls.Add(_lblVideoInfo);

        return bar;
    }

    private Control BuildContent()
    {
        var sidebar = BuildCameraListPanel();

        var split = new SplitContainer
        {
            Dock = DockStyle.Fill, Orientation = Orientation.Vertical,
            SplitterWidth = 4, BackColor = Theme.Border,
        };
        split.Panel1.Controls.Add(BuildVideoPanel());
        split.Panel2.Controls.Add(BuildRightPanel());
        split.SplitterDistance = _cfg.SplitterDist;
        split.SplitterMoved   += (_, e) => _cfg.SplitterDist = e.SplitX;

        var wrapper = new Panel { Dock = DockStyle.Fill };
        wrapper.Controls.AddRange([split, sidebar]);
        return wrapper;
    }

    private Panel BuildCameraListPanel()
    {
        var panel = new Panel { Dock = DockStyle.Left, Width = 180, BackColor = Theme.Card };

        var hdr = new Panel { Dock = DockStyle.Top, Height = 38, BackColor = Theme.NavyDk };
        hdr.Controls.Add(Theme.Lbl("📷  Cameras", Theme.FBold, Theme.Txt)
            .Also(l => l.Location = new Point(8, 10)));
        var btnAdd = Theme.Btn("➕", Theme.Accent);
        btnAdd.SetBounds(148, 8, 26, 22);
        btnAdd.Anchor = AnchorStyles.Right | AnchorStyles.Top;
        btnAdd.Click += (_, _) => OnAddCamera();
        hdr.Controls.Add(btnAdd);

        var scroll = new Panel { Dock = DockStyle.Fill, AutoScroll = true };
        _camFlow = new FlowLayoutPanel
        {
            Dock = DockStyle.Top, AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink,
            FlowDirection = FlowDirection.TopDown, WrapContents = false,
            Width = 174, Padding = new Padding(3, 3, 0, 0),
        };
        scroll.Controls.Add(_camFlow);
        panel.Controls.AddRange([scroll, hdr]);

        // Right divider
        panel.Controls.Add(new Panel { Dock = DockStyle.Right, Width = 1, BackColor = Theme.Border });

        return panel;
    }

    private Panel BuildVideoPanel()
    {
        var root = new Panel { Dock = DockStyle.Fill, BackColor = Theme.BG };

        var hdr = new Panel { Dock = DockStyle.Top, Height = 34, BackColor = Theme.NavyDk };
        hdr.Controls.Add(Theme.Lbl("📹  Video + Bbox Overlay", Theme.FBold, Theme.Txt)
            .Also(l => l.Location = new Point(8, 8)));

        var btnEdit = Theme.Btn("✎ Edit Regions", Theme.Navy);
        btnEdit.SetBounds(hdr.Width - 136, 5, 126, 24);
        btnEdit.Anchor = AnchorStyles.Right | AnchorStyles.Top;
        btnEdit.Click += OnEditRegions;
        hdr.Controls.Add(btnEdit);

        _pb = new PictureBox
        {
            Dock = DockStyle.Fill, SizeMode = PictureBoxSizeMode.Zoom,
            BackColor = Color.FromArgb(10, 10, 20),
        };
        _pb.DoubleClick += OnPbDoubleClick;
        _pb.Paint       += OnPbOverlayPaint;

        root.Controls.AddRange([_pb, hdr]);
        return root;
    }

    private Panel BuildRightPanel()
    {
        var root = new Panel { Dock = DockStyle.Fill, BackColor = Theme.BG };

        _rightSplit = new SplitContainer
        {
            Dock = DockStyle.Fill, Orientation = Orientation.Horizontal,
            SplitterWidth = 4, BackColor = Theme.Border,
            Panel1MinSize = 80, Panel2MinSize = 80,
        };
        _rightSplit.SplitterMoved += (_, e) => { _cfg.RightSplitDist = e.SplitY; _cfg.Save(); };

        // ── Panel1: Region state ──────────────────────────────────────────
        var hdrR = new Panel { Dock = DockStyle.Top, Height = 34, BackColor = Theme.NavyDk };
        hdrR.Controls.Add(Theme.Lbl("📦  Trạng thái region", Theme.FBold, Theme.Txt)
            .Also(l => l.Location = new Point(8, 8)));
        var btnReport = Theme.Btn("📊 Báo cáo", Theme.Accent);
        btnReport.SetBounds(0, 5, 104, 24);
        btnReport.Anchor = AnchorStyles.Right | AnchorStyles.Top;
        btnReport.Click += (_, _) => new HistoryForm(_db, _cfg).Show(this);
        hdrR.Controls.Add(btnReport);
        _lblDbCount = new Label
        {
            Dock = DockStyle.Right, Width = 130,
            ForeColor = Theme.Dim, BackColor = Color.Transparent,
            TextAlign = ContentAlignment.MiddleRight, Font = Theme.FSm,
            Padding = new Padding(0, 0, 6, 0),
        };
        hdrR.Controls.Add(_lblDbCount);
        hdrR.SizeChanged += (_, _) =>
            btnReport.Left = hdrR.Width - _lblDbCount.Width - btnReport.Width - 6;

        _lvRegions = Theme.MkListView();
        _lvRegions.Dock = DockStyle.Fill;
        _lvRegions.Columns.AddRange([
            new ColumnHeader { Text = "Region",   Width = 110 },
            new ColumnHeader { Text = "Class",    Width = 100 },
            new ColumnHeader { Text = "Conf",     Width = 54  },
            new ColumnHeader { Text = "Top-2",    Width = 100 },
            new ColumnHeader { Text = "Cập nhật", Width = 78  },
        ]);
        _rightSplit.Panel1.Controls.AddRange([_lvRegions, hdrR]);

        // ── Panel2: Event log ─────────────────────────────────────────────
        var hdrE = new Panel { Dock = DockStyle.Top, Height = 34, BackColor = Theme.NavyDk };
        hdrE.Controls.Add(Theme.Lbl("📋  Sự kiện thay đổi", Theme.FBold, Theme.Txt)
            .Also(l => l.Location = new Point(8, 8)));
        var btnFlow = new FlowLayoutPanel
        {
            Dock = DockStyle.Right, Width = 172, Height = 34,
            FlowDirection = FlowDirection.RightToLeft,
            WrapContents = false, BackColor = Color.Transparent, Padding = new Padding(4),
        };
        var btnClear = Theme.Btn("Xóa log", Theme.Card, Theme.Dim); btnClear.Width = 76;
        var btnHist  = Theme.Btn("📜 Lịch sử", Theme.Navy);         btnHist.Width  = 86;
        btnClear.Click += (_, _) => _lvEvents.Items.Clear();
        btnHist.Click  += (_, _) => new HistoryForm(_db, _cfg).Show(this);
        btnFlow.Controls.AddRange([btnClear, btnHist]);
        hdrE.Controls.Add(btnFlow);

        _lvEvents = Theme.MkListView();
        _lvEvents.Dock = DockStyle.Fill;
        _lvEvents.Columns.AddRange([
            new ColumnHeader { Text = "Camera",    Width = 72 },
            new ColumnHeader { Text = "Thời gian", Width = 76 },
            new ColumnHeader { Text = "Region",    Width = 72 },
            new ColumnHeader { Text = "Trước",     Width = 66 },
            new ColumnHeader { Text = "Sau",       Width = 66 },
            new ColumnHeader { Text = "Conf",      Width = 46 },
        ]);
        _lvEvents.DoubleClick += OnEventDoubleClick;
        _rightSplit.Panel2.Controls.AddRange([_lvEvents, hdrE]);

        root.Controls.Add(_rightSplit);
        return root;
    }

    // ══════════════════════════════════════════════════════════════════════
    // TIMER — refresh UI
    // ══════════════════════════════════════════════════════════════════════

    private void OnTimerTick(object? s, EventArgs e)
    {
        // ── Update camera toggle buttons ──────────────────────────────────
        foreach (var (id, btn) in _toggleBtns)
        {
            bool running = _workers.TryGetValue(id, out var w) && w.IsRunning;
            if (running  && btn.Text != "■") { btn.Text = "■"; btn.BackColor = Theme.Err; }
            if (!running && btn.Text != "▶") { btn.Text = "▶"; btn.BackColor = Theme.Ok; }
        }

        // ── Active camera: frame + states ─────────────────────────────────
        if (_workers.TryGetValue(_activeCamId, out var worker))
        {
            var frame = worker.GetFrameClone();
            if (frame is not null)
            {
                var old = _pb.Image;
                _pb.Image = frame;
                old?.Dispose();
            }
            var states = worker.GetStates();
            _paintStates = states;
            RefreshRegionList(states);
        }
        _pb.Invalidate();

        // ── Flush events from ALL workers ─────────────────────────────────
        bool hadEvent = false;
        foreach (var (_, wk) in _workers)
        {
            while (wk.Events.TryDequeue(out var rec))
            { AddEventRow(rec); hadEvent = true; }
        }

        if (hadEvent)
        {
            _cachedDbCount   = _db.TotalCount();
            _lblDbCount.Text = $"Đã lưu: {_cachedDbCount} sự kiện";
        }

        // ── Status bar ────────────────────────────────────────────────────
        var cam        = _cfg.Cameras.FirstOrDefault(c => c.Id == _activeCamId);
        int regions    = cam?.Regions.Count ?? 0;
        bool isRunning = _workers.TryGetValue(_activeCamId, out var aw) && aw.IsRunning;

        var statusText =
            $"Model: {(_runner.IsLoaded ? Path.GetFileName(_runner.ModelPath) : "chưa load")}  │  " +
            $"{_cfg.Cameras.Count} cameras  │  {regions} regions  │  " +
            $"{(isRunning ? "🟢 Đang chạy" : "⬜ Dừng")}  │  " +
            $"Infer: {(aw?.LastInferMs ?? 0)} ms  │  " +
            $"Frames: {(aw?.FrameCount ?? 0)}  │  {_cachedDbCount} events";

        if (statusText != _lastStatusText)
        {
            _lblStatus.Text = statusText;
            _lastStatusText = statusText;
        }

        var url = cam?.Url ?? "";
        _lblVideoInfo.Text = isRunning && url.Length > 0
            ? $"● {cam!.Name}: {url[..Math.Min(50, url.Length)]}"
            : "";
    }

    // ── PictureBox Paint overlay ──────────────────────────────────────────

    private void OnPbOverlayPaint(object? s, PaintEventArgs e)
    {
        var cam = _cfg.Cameras.FirstOrDefault(c => c.Id == _activeCamId);
        if (cam is null || (cam.Regions.Count == 0 && _paintStates.Count == 0)) return;
        var dr = GetPbDisplayRect();
        if (dr.IsEmpty) return;

        var g = e.Graphics;
        g.SmoothingMode     = System.Drawing.Drawing2D.SmoothingMode.AntiAlias;
        g.TextRenderingHint = System.Drawing.Text.TextRenderingHint.ClearTypeGridFit;
        DrawBboxOverlays(g, dr, _paintStates, cam.Regions);
    }

    private Rectangle GetPbDisplayRect()
    {
        var img = _pb.Image;
        if (img is null) return new Rectangle(0, 0, _pb.Width, _pb.Height);
        float scaleX = (float)_pb.Width  / img.Width;
        float scaleY = (float)_pb.Height / img.Height;
        float scale  = Math.Min(scaleX, scaleY);
        int   nw     = (int)(img.Width  * scale);
        int   nh     = (int)(img.Height * scale);
        return new Rectangle((_pb.Width - nw) / 2, (_pb.Height - nh) / 2, nw, nh);
    }

    private void DrawBboxOverlays(Graphics g, Rectangle dr,
        List<RegionClsState> states, List<BboxRegion> regions)
    {
        if (regions.Count == 0) return;
        var stateMap = states.Count > 0 ? states.ToDictionary(s => s.RegionId) : [];

        foreach (var region in regions)
        {
            int px1 = dr.X + (int)(region.X1n * dr.Width);
            int py1 = dr.Y + (int)(region.Y1n * dr.Height);
            int px2 = dr.X + (int)(region.X2n * dr.Width);
            int py2 = dr.Y + (int)(region.Y2n * dr.Height);
            var rect = Rectangle.FromLTRB(px1, py1, px2, py2);

            stateMap.TryGetValue(region.Id, out var st);
            var col   = st is not null ? Theme.ClassColor(st.ClassId) : Theme.Dim;
            int alpha = st is not null ? 180 : 120;

            using (var fill = new SolidBrush(Color.FromArgb(40, col)))
                g.FillRectangle(fill, rect);
            using (var pen = new Pen(Color.FromArgb(alpha, col), 2f))
                g.DrawRectangle(pen, rect.X, rect.Y, rect.Width, rect.Height);

            string label = st is not null
                ? $"{region.Name}: {st.ClassName} ({st.Conf:P0})"
                : $"{region.Name}: …";
            var sz = g.MeasureString(label, _overlayFont);
            float tx = rect.X + 3, ty = rect.Y + 2;
            using (var bg = new SolidBrush(Color.FromArgb(170, 0, 0, 0)))
                g.FillRectangle(bg, tx - 1, ty - 1, sz.Width + 4, sz.Height + 1);
            using (var fg = new SolidBrush(Color.White))
                g.DrawString(label, _overlayFont, fg, tx, ty);

            if (st is not null && st.Conf > 0f)
            {
                int barW = Math.Min(rect.Width, (int)(st.Conf * rect.Width));
                int barY = rect.Y + (int)sz.Height + 4;
                using (var barBg = new SolidBrush(Color.FromArgb(80, 0, 0, 0)))
                    g.FillRectangle(barBg, rect.X, barY, rect.Width, 4);
                using (var barFg = new SolidBrush(col))
                    g.FillRectangle(barFg, rect.X, barY, barW, 4);
            }
        }
    }

    // ── Region state ListView ─────────────────────────────────────────────

    private void RefreshRegionList(List<RegionClsState> states)
    {
        _lvRegions.BeginUpdate();
        while (_lvRegions.Items.Count < states.Count)
        {
            var it = new ListViewItem(""); it.SubItems.AddRange(["", "", "", ""]);
            _lvRegions.Items.Add(it);
        }
        while (_lvRegions.Items.Count > states.Count)
            _lvRegions.Items.RemoveAt(_lvRegions.Items.Count - 1);

        for (int i = 0; i < states.Count; i++)
        {
            var st   = states[i];
            var item = _lvRegions.Items[i];
            var top2 = st.TopN.Count > 1 ? $"{st.TopN[1].ClassName} {st.TopN[1].Conf:P0}" : "—";
            var time = st.UpdatedAt != default ? st.UpdatedAt.ToString("HH:mm:ss") : "—";
            item.Text             = st.RegionName;
            item.SubItems[1].Text = st.ClassName;
            item.SubItems[2].Text = $"{st.Conf:P0}";
            item.SubItems[3].Text = top2;
            item.SubItems[4].Text = time;
            item.ForeColor        = Theme.ClassColor(st.ClassId);
        }
        _lvRegions.EndUpdate();
    }

    // ── Event log ─────────────────────────────────────────────────────────

    private void AddEventRow(ClsChangeRecord rec)
    {
        var item = new ListViewItem(rec.CameraName);
        item.SubItems.Add(rec.OccurredAt.ToString("HH:mm:ss.fff"));
        item.SubItems.Add(rec.RegionName);
        item.SubItems.Add(rec.PrevClass);
        item.SubItems.Add(rec.NewClass);
        item.SubItems.Add($"{rec.Confidence:P0}");
        item.ForeColor = Theme.ConfColor(rec.Confidence);
        item.Tag       = rec;
        _lvEvents.Items.Insert(0, item);
        while (_lvEvents.Items.Count > 500) _lvEvents.Items.RemoveAt(_lvEvents.Items.Count - 1);
    }

    private void OnEventDoubleClick(object? s, EventArgs e)
    {
        if (_lvEvents.SelectedItems.Count == 0) return;
        var rec = (ClsChangeRecord)_lvEvents.SelectedItems[0].Tag!;
        if (string.IsNullOrEmpty(rec.ImagePath) || !File.Exists(rec.ImagePath)) return;
        try { System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo(rec.ImagePath) { UseShellExecute = true }); }
        catch { }
    }

    // ══════════════════════════════════════════════════════════════════════
    // MODEL
    // ══════════════════════════════════════════════════════════════════════

    private void OnBrowseModel(object? s, EventArgs e)
    {
        var choice = MessageBox.Show(
            "Yes → chọn FOLDER openvino_model/\nNo  → chọn FILE (.xml / .onnx)",
            "Chọn model", MessageBoxButtons.YesNoCancel, MessageBoxIcon.Question);

        if (choice == DialogResult.Yes)
        {
            using var d = new FolderBrowserDialog { Description = "Folder OpenVINO (chứa .xml)" };
            if (d.ShowDialog() == DialogResult.OK) { _cmbModel.Text = d.SelectedPath; OnLoadModel(s, e); }
        }
        else if (choice == DialogResult.No)
        {
            using var d = new OpenFileDialog { Filter = "Model|*.xml;*.onnx|Tất cả|*.*" };
            if (d.ShowDialog() == DialogResult.OK) { _cmbModel.Text = d.FileName; OnLoadModel(s, e); }
        }
    }

    private async void OnLoadModel(object? s, EventArgs e)
    {
        var path = _cmbModel.Text.Trim();
        if (string.IsNullOrEmpty(path)) return;

        SyncCfgFromUI();
        _lblModel.Text      = "⏳ Đang load model…";
        _lblModel.ForeColor = Theme.Warn;
        SetStatus("Đang load model…");

        var device = _cmbDevice.SelectedItem?.ToString() ?? "CPU";
        try
        {
            await Task.Run(() => _runner.LoadModel(path, device));
            _cfg.ModelPath = path;
            _cfg.PushModelHistory(path);
            _cmbModel.Items.Clear();
            foreach (var h in _cfg.ModelHistory) _cmbModel.Items.Add(h);
            _cmbModel.Text      = path;
            _lblModel.Text      = $"✓  {_runner.ModelInfo}";
            _lblModel.ForeColor = Theme.Ok;
            SetStatus($"Model OK — {_runner.NumClasses} class [{_runner.ActualDevice}]");
        }
        catch (Exception ex)
        {
            _lblModel.Text      = $"✗  {ex.Message[..Math.Min(100, ex.Message.Length)]}";
            _lblModel.ForeColor = Theme.Err;
            SetStatus("Lỗi load model.");
        }
    }

    // ══════════════════════════════════════════════════════════════════════
    // CAMERA MANAGEMENT
    // ══════════════════════════════════════════════════════════════════════

    private void RefreshCameraList()
    {
        _camFlow.SuspendLayout();
        _camFlow.Controls.Clear();
        _toggleBtns.Clear();

        if (_cfg.Cameras.Count == 0)
        {
            _camFlow.Controls.Add(new Label
            {
                Text = "Chưa có camera.\nNhấn ➕ để thêm.",
                Width = 168, Height = 50,
                TextAlign = ContentAlignment.MiddleCenter,
                ForeColor = Theme.Dim, BackColor = Color.Transparent,
            });
            _camFlow.ResumeLayout();
            return;
        }

        foreach (var cam in _cfg.Cameras)
        {
            var camLocal  = cam;
            bool isActive = cam.Id == _activeCamId;
            bool running  = _workers.TryGetValue(cam.Id, out var wk) && wk.IsRunning;

            var item = new Panel
            {
                Width     = 168, Height = 74,
                BackColor = isActive ? Theme.Deep : Theme.Card,
                Margin    = new Padding(0, 2, 0, 0),
                Cursor    = Cursors.Hand,
            };
            var borderCol = isActive ? Theme.Accent : Theme.Border;
            item.Paint += (_, pe) =>
            {
                using var pen = new Pen(borderCol, 2);
                pe.Graphics.DrawRectangle(pen, 1, 1, item.Width - 3, item.Height - 3);
            };

            var dot = new Label
            {
                Text = "●", Left = 6, Top = 7, AutoSize = true,
                ForeColor = running ? Theme.Ok : Color.Gray, BackColor = Color.Transparent,
            };
            var lblName = new Label
            {
                Text = cam.Name.Length > 17 ? cam.Name[..17] + "…" : cam.Name,
                Left = 22, Top = 8, Width = 144, Height = 18,
                ForeColor = Theme.Txt, BackColor = Color.Transparent, Font = Theme.FBold,
            };
            var lblUrl = new Label
            {
                Text = cam.ShortUrl.Length > 22 ? cam.ShortUrl[..22] + "…" : cam.ShortUrl,
                Left = 6, Top = 30, Width = 162, Height = 14,
                ForeColor = Theme.Dim, BackColor = Color.Transparent, Font = Theme.FSm,
            };

            var btnToggle = Theme.Btn(running ? "■" : "▶", running ? Theme.Err : Theme.Ok);
            btnToggle.SetBounds(6, 50, 44, 18); btnToggle.Font = Theme.FSm;
            btnToggle.Click += (_, _) =>
            {
                if (_workers.TryGetValue(camLocal.Id, out var w2) && w2.IsRunning)
                    StopCamera(camLocal.Id);
                else
                    StartCamera(camLocal.Id);
            };
            _toggleBtns[cam.Id] = btnToggle;

            var btnEdit = Theme.Btn("✎", Theme.Navy);
            btnEdit.SetBounds(56, 50, 32, 18); btnEdit.Font = Theme.FSm;
            btnEdit.Click += (_, _) => OnEditCamera(camLocal);

            var btnDel = Theme.Btn("✕", Theme.Card, Theme.Err);
            btnDel.SetBounds(94, 50, 32, 18); btnDel.Font = Theme.FSm;
            btnDel.Click += (_, _) => OnRemoveCamera(camLocal);

            item.Controls.AddRange([dot, lblName, lblUrl, btnToggle, btnEdit, btnDel]);

            // Click anywhere → select camera
            foreach (Control c in new Control[] { item, lblName, lblUrl, dot })
                c.Click += (_, _) => SelectCamera(camLocal.Id);

            _camFlow.Controls.Add(item);
        }

        _camFlow.ResumeLayout();
    }

    private void SelectCamera(string id)
    {
        _activeCamId = id;
        _paintStates = [];
        _lvRegions.Items.Clear();

        var old = _pb.Image; _pb.Image = null; old?.Dispose();
        _pb.Invalidate();

        RefreshCameraList();
    }

    private void StartCamera(string id)
    {
        var cam = _cfg.Cameras.FirstOrDefault(c => c.Id == id);
        if (cam is null || string.IsNullOrEmpty(cam.Url)) return;

        if (_workers.TryGetValue(id, out var ex)) { ex.Stop(); ex.Dispose(); }
        var w = new StreamWorker(_runner, _cfg, _db, cam);
        w.Start();
        _workers[id] = w;
    }

    private void StopCamera(string id)
    {
        if (!_workers.TryGetValue(id, out var w)) return;
        w.Stop();
        if (id == _activeCamId)
        {
            _paintStates = [];
            var old = _pb.Image; _pb.Image = null; old?.Dispose();
            _pb.Invalidate();
        }
    }

    private void OnAddCamera()
    {
        using var form = new CameraSetupForm(null, _cfg.RtspHistory);
        if (form.ShowDialog(this) != DialogResult.OK || form.Result is null) return;

        _cfg.Cameras.Add(form.Result);
        _cfg.PushRtspHistory(form.Result.Url);
        _cfg.Save();

        StartCamera(form.Result.Id);
        SelectCamera(form.Result.Id);
    }

    private void OnEditCamera(CameraConfig cam)
    {
        using var form = new CameraSetupForm(cam, _cfg.RtspHistory);
        if (form.ShowDialog(this) != DialogResult.OK || form.Result is null) return;

        bool wasRunning = _workers.TryGetValue(cam.Id, out var w) && w.IsRunning;
        if (wasRunning) StopCamera(cam.Id);

        cam.Name = form.Result.Name;
        cam.Url  = form.Result.Url;
        _cfg.PushRtspHistory(cam.Url);
        _cfg.Save();

        if (wasRunning) StartCamera(cam.Id);
        RefreshCameraList();
    }

    private void OnRemoveCamera(CameraConfig cam)
    {
        if (MessageBox.Show($"Xóa camera '{cam.Name}'?", "Xác nhận",
            MessageBoxButtons.YesNo, MessageBoxIcon.Warning) != DialogResult.Yes) return;

        StopCamera(cam.Id);
        if (_workers.TryGetValue(cam.Id, out var w)) { w.Dispose(); _workers.Remove(cam.Id); }
        _toggleBtns.Remove(cam.Id);
        _cfg.Cameras.Remove(cam);
        _cfg.Save();

        if (_activeCamId == cam.Id)
        {
            _activeCamId = _cfg.Cameras.FirstOrDefault()?.Id ?? "";
            _paintStates = [];
            _lvRegions.Items.Clear();
            var old = _pb.Image; _pb.Image = null; old?.Dispose();
        }
        RefreshCameraList();
    }

    // ══════════════════════════════════════════════════════════════════════
    // REGIONS
    // ══════════════════════════════════════════════════════════════════════

    private void OnEditRegions(object? s, EventArgs e)
    {
        var cam = _cfg.Cameras.FirstOrDefault(c => c.Id == _activeCamId);
        if (cam is null) { MessageBox.Show("Chọn camera trước."); return; }

        var frame = _workers.TryGetValue(_activeCamId, out var w) ? w.GetFrameClone() : null;
        using var editor = new RegionEditor(cam.Regions, frame);
        var result = editor.ShowDialog();
        frame?.Dispose();

        if (result != DialogResult.OK) return;

        cam.Regions.Clear();
        cam.Regions.AddRange(editor.Result);
        _cfg.Save();

        // Restart để pick up regions mới
        if (_workers.TryGetValue(_activeCamId, out var wk) && wk.IsRunning)
        {
            StopCamera(_activeCamId);
            StartCamera(_activeCamId);
        }
    }

    // ══════════════════════════════════════════════════════════════════════
    // PREVIEW ZOOM
    // ══════════════════════════════════════════════════════════════════════

    private void OnPbDoubleClick(object? s, EventArgs e)
    {
        if (!_workers.TryGetValue(_activeCamId, out var w)) return;
        var frame = w.GetFrameClone();
        if (frame is null) return;

        var cam = _cfg.Cameras.FirstOrDefault(c => c.Id == _activeCamId);
        var win = new Form
        {
            Text = $"Preview — {cam?.Name ?? _activeCamId}",
            BackColor = Color.Black, Size = new Size(960, 680),
            StartPosition = FormStartPosition.CenterParent,
        };
        var pb2 = new PictureBox
        {
            Dock = DockStyle.Fill, SizeMode = PictureBoxSizeMode.Zoom,
            Image = frame, BackColor = Color.Black,
        };
        win.FormClosed += (_, _) => pb2.Image?.Dispose();
        win.Controls.Add(pb2);
        win.Show(this);
    }

    // ══════════════════════════════════════════════════════════════════════
    // HELPERS
    // ══════════════════════════════════════════════════════════════════════

    private void OnBrowseImgFolder(object? s, EventArgs e)
    {
        using var d = new FolderBrowserDialog { Description = "Thư mục lưu ảnh snapshot" };
        if (d.ShowDialog() != DialogResult.OK) return;
        _txtImgFolder.Text = d.SelectedPath;
        _cfg.ImageFolder   = d.SelectedPath;
        _cfg.Save();
    }

    private void SyncCfgFromUI()
    {
        _cfg.Conf        = (float)_nudConf.Value / 100f;
        _cfg.TopN        = (int)_nudTopN.Value;
        _cfg.IntervalMs  = (int)_nudInterval.Value;
        _cfg.ImageFolder = _txtImgFolder.Text.Trim();
        _cfg.Device      = _cmbDevice.SelectedItem?.ToString() ?? "CPU";
    }

    private void BindAutoSave()
    {
        _nudConf.ValueChanged     += (_, _) => { _cfg.Conf       = (float)_nudConf.Value / 100f; _cfg.Save(); };
        _nudTopN.ValueChanged     += (_, _) => { _cfg.TopN       = (int)_nudTopN.Value;           _cfg.Save(); };
        _nudInterval.ValueChanged += (_, _) => { _cfg.IntervalMs = (int)_nudInterval.Value;       _cfg.Save(); };
        _cmbDevice.SelectedIndexChanged += (_, _) =>
        {
            _cfg.Device = _cmbDevice.SelectedItem?.ToString() ?? "CPU";
            _cfg.Save();
        };
        _txtImgFolder.Leave += (_, _) =>
        {
            _cfg.ImageFolder = _txtImgFolder.Text.Trim();
            _cfg.Save();
        };
        _cmbModel.Leave += (_, _) =>
        {
            var p = _cmbModel.Text.Trim();
            if (!string.IsNullOrEmpty(p)) { _cfg.ModelPath = p; _cfg.Save(); }
        };
    }

    private void RestoreSession()
    {
        _cmbModel.Text = _cfg.ModelPath;
        foreach (var h in _cfg.ModelHistory) _cmbModel.Items.Add(h);

        _nudConf.Value     = (decimal)Math.Round(_cfg.Conf * 100);
        _nudTopN.Value     = _cfg.TopN;
        _nudInterval.Value = _cfg.IntervalMs;
        _txtImgFolder.Text = _cfg.ImageFolder;

        if (_cmbDevice.Items.Contains(_cfg.Device))
            _cmbDevice.SelectedItem = _cfg.Device;

        if (!string.IsNullOrEmpty(_cfg.ModelPath)
            && (File.Exists(_cfg.ModelPath) || Directory.Exists(_cfg.ModelPath)))
            OnLoadModel(this, EventArgs.Empty);

        // Start all cameras
        foreach (var cam in _cfg.Cameras)
            StartCamera(cam.Id);

        _activeCamId = _cfg.Cameras.FirstOrDefault()?.Id ?? "";
        RefreshCameraList();
    }

    private void OnClose()
    {
        _timer.Stop();
        SyncCfgFromUI();
        _cfg.ModelPath = _cmbModel.Text;
        _cfg.Save();
        foreach (var (_, w) in _workers) { w.Stop(); w.Dispose(); }
        _runner.Dispose();
        _db.Dispose();
    }

    private void OnKeyDown(object? s, KeyEventArgs e)
    {
        if (e.KeyCode == Keys.Escape)
        {
            foreach (var id in _workers.Keys.ToList()) StopCamera(id);
            e.Handled = true;
        }
        if (e.Control && e.KeyCode == Keys.L) { OnLoadModel(s, e); e.Handled = true; }
        if (e.Control && e.KeyCode == Keys.E) { OnEditRegions(s, e); e.Handled = true; }
        if (e.Control && e.KeyCode == Keys.H) { new HistoryForm(_db, _cfg).Show(this); e.Handled = true; }
        if (e.Control && e.KeyCode == Keys.N) { OnAddCamera(); e.Handled = true; }
    }

    private void SetStatus(string msg) => _lblStatus.Text = msg;

    private static Label MkLbl(string text, int x, int y) => new()
    {
        Text = text, Left = x, Top = y, AutoSize = true,
        ForeColor = Theme.Dim, BackColor = Color.Transparent, Font = Theme.FMain,
    };

    protected override void Dispose(bool disposing)
    {
        if (disposing) { _timer.Dispose(); _overlayFont.Dispose(); }
        base.Dispose(disposing);
    }
}

// ── Control extension ─────────────────────────────────────────────────────────
internal static class ControlExt
{
    public static T Also<T>(this T ctrl, Action<T> action) where T : Control
        { action(ctrl); return ctrl; }
}
