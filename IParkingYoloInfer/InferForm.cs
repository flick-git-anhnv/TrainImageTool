using OpenCvSharp;
using OpenCvSharp.Extensions;
using System.Diagnostics;

namespace IParkingYoloInfer;

public sealed class InferForm : Form
{
    // ── State ──────────────────────────────────────────────────────────────
    private YoloDetector? _detector;
    private Mat?          _currentMat;
    private string[]      _classNames = ["car", "motorcycle", "bus", "truck", "bicycle", "license_plate"];
    private string[]      _imageFiles = [];
    private int           _imageIndex = 0;

    // ── Controls ───────────────────────────────────────────────────────────
    private readonly TextBox   _modelBox;
    private readonly TextBox   _imageBox;
    private readonly TextBox   _classBox;
    private readonly PictureBox _pictureBox;
    private readonly ListBox   _detList;
    private readonly TrackBar  _confBar;
    private readonly Label     _confLbl;
    private readonly Label     _statsLbl;
    private readonly Button    _prevBtn;
    private readonly Button    _nextBtn;
    private readonly Label     _idxLbl;

    public InferForm()
    {
        Text            = "KZTEK — YOLO11 Inference Tester";
        Size            = new System.Drawing.Size(1280, 760);
        MinimumSize     = new System.Drawing.Size(900, 600);
        StartPosition   = FormStartPosition.CenterScreen;
        BackColor       = System.Drawing.Color.FromArgb(30, 30, 46);
        ForeColor       = System.Drawing.Color.FromArgb(224, 224, 240);
        Font            = new System.Drawing.Font("Segoe UI", 9f);

        // ── Top config panel ────────────────────────────────────────────
        var topPanel = new TableLayoutPanel
        {
            Dock = DockStyle.Top, Height = 130, Padding = new Padding(8),
            BackColor = System.Drawing.Color.FromArgb(42, 42, 62),
            ColumnCount = 3, RowCount = 4
        };
        topPanel.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 110));
        topPanel.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        topPanel.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 100));

        _modelBox = AddRow(topPanel, 0, "Model (.onnx):", out var modelBtn, "📂 Chọn");
        modelBtn.Click += (_, _) => PickModel();

        _imageBox = AddRow(topPanel, 1, "Ảnh / Thư mục:", out var imgBtn, "📂 Chọn");
        imgBtn.Click += (_, _) => PickImage();

        _classBox = AddRow(topPanel, 2, "Nhãn (,):", out var reloadBtn, "↻ Reload");
        _classBox.Text   = string.Join(",", _classNames);
        reloadBtn.Click += (_, _) => ReloadClasses();

        var confRow = new Panel { Dock = DockStyle.Fill, BackColor = System.Drawing.Color.Transparent };
        topPanel.Controls.Add(new Label { Text = "Confidence:", Dock = DockStyle.Left,
            Width = 94, TextAlign = System.Drawing.ContentAlignment.MiddleRight,
            ForeColor = System.Drawing.Color.FromArgb(144, 144, 176) }, 0, 3);
        _confBar = new TrackBar { Minimum = 1, Maximum = 99, Value = 25,
            TickFrequency = 10, Dock = DockStyle.Fill };
        _confBar.ValueChanged += (_, _) => { _confLbl.Text = $"{_confBar.Value}%"; RunInfer(); };
        _confLbl = new Label { Text = "25%", Width = 40,
            TextAlign = System.Drawing.ContentAlignment.MiddleLeft };
        confRow.Controls.Add(_confBar);
        topPanel.Controls.Add(confRow, 1, 3);
        topPanel.Controls.Add(_confLbl, 2, 3);
        Controls.Add(topPanel);

        // ── Main split ──────────────────────────────────────────────────
        var split = new SplitContainer
        {
            Dock = DockStyle.Fill, Orientation = Orientation.Vertical,
            SplitterDistance = 900, Panel1MinSize = 400, Panel2MinSize = 200,
            BackColor = System.Drawing.Color.FromArgb(30, 30, 46)
        };

        _pictureBox = new PictureBox
        {
            Dock = DockStyle.Fill, SizeMode = PictureBoxSizeMode.Zoom,
            BackColor = System.Drawing.Color.FromArgb(13, 13, 26)
        };
        split.Panel1.Controls.Add(_pictureBox);

        _detList = new ListBox
        {
            Dock = DockStyle.Fill,
            BackColor = System.Drawing.Color.FromArgb(22, 22, 42),
            ForeColor = System.Drawing.Color.FromArgb(224, 224, 240),
            BorderStyle = BorderStyle.None, Font = new System.Drawing.Font("Consolas", 8.5f)
        };
        split.Panel2.Controls.Add(_detList);
        Controls.Add(split);

        // ── Bottom bar ──────────────────────────────────────────────────
        var bot = new Panel
        {
            Dock = DockStyle.Bottom, Height = 36,
            BackColor = System.Drawing.Color.FromArgb(42, 42, 62), Padding = new Padding(6, 4, 6, 4)
        };
        _prevBtn = MakeBtn("◀ Prev", bot, DockStyle.Left);
        _prevBtn.Click += (_, _) => Navigate(-1);
        _nextBtn = MakeBtn("Next ▶", bot, DockStyle.Left);
        _nextBtn.Click += (_, _) => Navigate(1);
        _idxLbl = new Label { Text = "—", Dock = DockStyle.Left, Width = 120,
            TextAlign = System.Drawing.ContentAlignment.MiddleCenter };
        bot.Controls.Add(_idxLbl);
        MakeBtn("▶ Run", bot, DockStyle.Left).Click += (_, _) => RunInfer();
        MakeBtn("💾 Save", bot, DockStyle.Right).Click += (_, _) => SaveResult();
        _statsLbl = new Label { Dock = DockStyle.Fill, TextAlign = System.Drawing.ContentAlignment.MiddleLeft };
        bot.Controls.Add(_statsLbl);
        Controls.Add(bot);

        KeyPreview = true;
        KeyDown   += OnKey;
    }

    // ── Actions ────────────────────────────────────────────────────────────

    private void PickModel()
    {
        using var dlg = new OpenFileDialog
        {
            Title  = "Chọn file ONNX",
            Filter = "ONNX model|*.onnx|All files|*.*"
        };
        if (dlg.ShowDialog() != DialogResult.OK) return;
        _modelBox.Text = dlg.FileName;
        try
        {
            ReloadClasses();
            _detector?.Dispose();
            _detector = new YoloDetector(dlg.FileName, _classNames);
            _statsLbl.Text = $"✅ Model loaded: {Path.GetFileName(dlg.FileName)}";
            RunInfer();
        }
        catch (Exception ex)
        {
            MessageBox.Show($"Lỗi load model:\n{ex.Message}", "Error",
                MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }

    private void PickImage()
    {
        // Thử chọn folder trước, fallback sang file
        using var fbd = new FolderBrowserDialog { Description = "Chọn thư mục ảnh (hoặc Cancel để chọn file)" };
        if (fbd.ShowDialog() == DialogResult.OK)
        {
            _imageFiles = Directory.GetFiles(fbd.SelectedPath, "*.*")
                .Where(f => new[] { ".jpg", ".jpeg", ".png", ".bmp", ".webp" }
                    .Contains(Path.GetExtension(f).ToLower()))
                .Order().ToArray();
            _imageIndex = 0;
            _imageBox.Text = fbd.SelectedPath;
        }
        else
        {
            using var ofd = new OpenFileDialog
            {
                Title  = "Chọn ảnh",
                Filter = "Images|*.jpg;*.jpeg;*.png;*.bmp;*.webp|All|*.*",
                Multiselect = true
            };
            if (ofd.ShowDialog() != DialogResult.OK) return;
            _imageFiles = ofd.FileNames;
            _imageIndex = 0;
            _imageBox.Text = _imageFiles.Length == 1 ? _imageFiles[0] : $"{_imageFiles.Length} files";
        }
        LoadCurrentImage();
    }

    private void ReloadClasses()
    {
        _classNames = _classBox.Text.Split(',', StringSplitOptions.TrimEntries | StringSplitOptions.RemoveEmptyEntries);
    }

    private void Navigate(int delta)
    {
        if (_imageFiles.Length == 0) return;
        _imageIndex = (_imageIndex + delta + _imageFiles.Length) % _imageFiles.Length;
        LoadCurrentImage();
    }

    private void LoadCurrentImage()
    {
        if (_imageFiles.Length == 0) return;
        _currentMat?.Dispose();
        _currentMat  = Cv2.ImRead(_imageFiles[_imageIndex], ImreadModes.Color);
        _idxLbl.Text = $"{_imageIndex + 1} / {_imageFiles.Length}";
        Text = $"KZTEK YOLO Infer — {Path.GetFileName(_imageFiles[_imageIndex])}";
        RunInfer();
    }

    private void RunInfer()
    {
        if (_detector is null || _currentMat is null) return;
        float conf = _confBar.Value / 100f;

        var sw = Stopwatch.StartNew();
        var dets = _detector.Detect(_currentMat, confThresh: conf);
        sw.Stop();

        using var drawn = _detector.DrawDetections(_currentMat, dets);
        _pictureBox.Image?.Dispose();
        _pictureBox.Image = BitmapConverter.ToBitmap(drawn);

        _detList.BeginUpdate();
        _detList.Items.Clear();
        foreach (var d in dets.OrderByDescending(d => d.Confidence))
            _detList.Items.Add(d.ToString());
        _detList.EndUpdate();

        var counts = dets.GroupBy(d => d.ClassName)
            .Select(g => $"{g.Key}×{g.Count()}").ToArray();
        _statsLbl.Text = $"⚡ {sw.ElapsedMilliseconds}ms  |  {dets.Count} detections  |  " +
                         string.Join("  ", counts);
    }

    private void SaveResult()
    {
        if (_pictureBox.Image is null) return;
        using var sfd = new SaveFileDialog
        {
            Title = "Lưu ảnh kết quả",
            Filter = "PNG|*.png|JPEG|*.jpg",
            FileName = "result"
        };
        if (sfd.ShowDialog() != DialogResult.OK) return;
        _pictureBox.Image.Save(sfd.FileName);
        _statsLbl.Text = $"💾 Đã lưu: {sfd.FileName}";
    }

    private void OnKey(object? sender, KeyEventArgs e)
    {
        if (e.KeyCode == Keys.Left)  Navigate(-1);
        if (e.KeyCode == Keys.Right) Navigate(1);
        if (e.KeyCode == Keys.F5)    RunInfer();
    }

    protected override void OnFormClosed(FormClosedEventArgs e)
    {
        base.OnFormClosed(e);
        _detector?.Dispose();
        _currentMat?.Dispose();
    }

    // ── UI helpers ─────────────────────────────────────────────────────────

    private static TextBox AddRow(TableLayoutPanel table, int row, string label,
                                   out Button btn, string btnText)
    {
        table.Controls.Add(new Label
        {
            Text = label, Dock = DockStyle.Fill,
            TextAlign = System.Drawing.ContentAlignment.MiddleRight,
            ForeColor = System.Drawing.Color.FromArgb(144, 144, 176)
        }, 0, row);

        var txt = new TextBox
        {
            Dock = DockStyle.Fill, Margin = new Padding(2),
            BackColor = System.Drawing.Color.FromArgb(22, 22, 42),
            ForeColor = System.Drawing.Color.FromArgb(224, 224, 240),
            BorderStyle = BorderStyle.FixedSingle
        };
        table.Controls.Add(txt, 1, row);

        btn = new Button
        {
            Text = btnText, Dock = DockStyle.Fill, Margin = new Padding(2),
            BackColor = System.Drawing.Color.FromArgb(74, 63, 140),
            ForeColor = System.Drawing.Color.White, FlatStyle = FlatStyle.Flat,
            Cursor = Cursors.Hand
        };
        btn.FlatAppearance.BorderSize = 0;
        table.Controls.Add(btn, 2, row);
        return txt;
    }

    private static Button MakeBtn(string text, Control parent, DockStyle dock)
    {
        var btn = new Button
        {
            Text = text, Dock = dock, Width = 90,
            BackColor = System.Drawing.Color.FromArgb(74, 63, 140),
            ForeColor = System.Drawing.Color.White, FlatStyle = FlatStyle.Flat,
            Cursor = Cursors.Hand, Margin = new Padding(2)
        };
        btn.FlatAppearance.BorderSize = 0;
        parent.Controls.Add(btn);
        return btn;
    }
}
