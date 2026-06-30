using ClsTester.Data;
using ClsTester.Models;
using ClsTester.UI;

namespace ClsTester.Forms;

/// <summary>
/// Form duyệt lịch sử thay đổi phân loại.
///
/// Tính năng:
///   • Lọc theo camera, region, khoảng thời gian
///   • Preview ảnh snapshot khi chọn bản ghi
///   • Double-click → mở ảnh bằng viewer ngoài
///   • Export CSV
///   • Xóa theo region hoặc xóa tất cả
/// </summary>
public sealed class HistoryForm : Form
{
    private readonly ClsDb       _db;
    private readonly AppSettings _cfg;

    // ── Controls ──────────────────────────────────────────────────────────
    private ComboBox       _cmbCamera  = null!;
    private ComboBox       _cmbRegion  = null!;
    private DateTimePicker _dtpFrom    = null!;
    private DateTimePicker _dtpTo      = null!;
    private CheckBox       _chkFrom    = null!;
    private CheckBox       _chkTo      = null!;
    private ListView       _lv         = null!;
    private PictureBox     _pbPreview  = null!;
    private Label          _lblCount   = null!;
    private Label          _lblImgInfo = null!;

    private List<ClsChangeRecord> _records = [];

    public HistoryForm(ClsDb db, AppSettings cfg)
    {
        _db  = db;
        _cfg = cfg;

        Text           = "KZTEK — Lịch sử thay đổi phân loại";
        BackColor      = Theme.BG;
        ForeColor      = Theme.Txt;
        Font           = Theme.FMain;
        Size           = new Size(1280, 720);
        MinimumSize    = new Size(800, 480);
        StartPosition  = FormStartPosition.CenterParent;
        DoubleBuffered = true;

        BuildUI();
        LoadFilters();
        Reload();
    }

    // ── Build UI ──────────────────────────────────────────────────────────

    private void BuildUI()
    {
        // ── Toolbar ───────────────────────────────────────────────────────
        var toolbar = new Panel { Dock = DockStyle.Top, Height = 90, BackColor = Theme.Card };

        int x = 8, y = 8;
        toolbar.Controls.Add(MkLbl("Camera:", x, y + 2)); x += 58;
        _cmbCamera = new ComboBox
        {
            Left = x, Top = y, Width = 140, DropDownStyle = ComboBoxStyle.DropDownList,
            BackColor = Theme.Deep, ForeColor = Theme.Txt,
        };
        _cmbCamera.SelectedIndexChanged += (_, _) => { LoadRegions(); Reload(); };
        toolbar.Controls.Add(_cmbCamera); x += 148;

        toolbar.Controls.Add(MkLbl("Region:", x, y + 2)); x += 56;
        _cmbRegion = new ComboBox
        {
            Left = x, Top = y, Width = 160, DropDownStyle = ComboBoxStyle.DropDownList,
            BackColor = Theme.Deep, ForeColor = Theme.Txt,
        };
        _cmbRegion.SelectedIndexChanged += (_, _) => Reload();
        toolbar.Controls.Add(_cmbRegion); x += 168;

        toolbar.Controls.Add(MkLbl("Từ:", x, y + 2)); x += 28;
        _chkFrom = new CheckBox { Left = x, Top = y + 1, Width = 18, BackColor = Color.Transparent }; x += 20;
        toolbar.Controls.Add(_chkFrom);
        _dtpFrom = new DateTimePicker { Left = x, Top = y, Width = 155, Format = DateTimePickerFormat.Custom, CustomFormat = "yyyy-MM-dd HH:mm" };
        _dtpFrom.Value = DateTime.Today;
        toolbar.Controls.Add(_dtpFrom); x += 162;

        toolbar.Controls.Add(MkLbl("Đến:", x, y + 2)); x += 36;
        _chkTo = new CheckBox { Left = x, Top = y + 1, Width = 18, BackColor = Color.Transparent }; x += 20;
        toolbar.Controls.Add(_chkTo);
        _dtpTo = new DateTimePicker { Left = x, Top = y, Width = 155, Format = DateTimePickerFormat.Custom, CustomFormat = "yyyy-MM-dd HH:mm" };
        _dtpTo.Value = DateTime.Now;
        toolbar.Controls.Add(_dtpTo); x += 162;

        _chkFrom.CheckedChanged += (_, _) => { _dtpFrom.Enabled = _chkFrom.Checked; Reload(); };
        _chkTo.CheckedChanged   += (_, _) => { _dtpTo.Enabled   = _chkTo.Checked;   Reload(); };
        _dtpFrom.ValueChanged   += (_, _) => { if (_chkFrom.Checked) Reload(); };
        _dtpTo.ValueChanged     += (_, _) => { if (_chkTo.Checked)   Reload(); };
        _dtpFrom.Enabled = _dtpTo.Enabled = false;

        var btnReload = Theme.Btn("🔄 Tải lại", Theme.Navy); btnReload.SetBounds(x, y - 1, 86, 26);
        btnReload.Click += (_, _) => Reload();
        toolbar.Controls.Add(btnReload);

        // Row 2: action buttons + count
        x = 8; y = 50;
        var btnExport  = Theme.Btn("📥 Export CSV",  Theme.Card);              btnExport.SetBounds(x, y, 116, 26);  btnExport.Click  += OnExportCsv;           toolbar.Controls.Add(btnExport);  x += 122;
        var btnOpen    = Theme.Btn("🖼 Mở crop",     Theme.Card);              btnOpen.SetBounds(x, y, 90, 26);     btnOpen.Click    += OnOpenImageExternal;   toolbar.Controls.Add(btnOpen);    x += 96;
        var btnFolder  = Theme.Btn("📂 Mở thư mục", Theme.Card);              btnFolder.SetBounds(x, y, 112, 26);  btnFolder.Click  += OnOpenFolder;          toolbar.Controls.Add(btnFolder);  x += 118;
        var btnDelAll  = Theme.Btn("✕ Xóa tất cả",  Theme.Card, Theme.Err);  btnDelAll.SetBounds(x, y, 110, 26);  btnDelAll.Click  += OnDeleteAll;           toolbar.Controls.Add(btnDelAll);

        _lblCount = new Label
        {
            Left = toolbar.Width - 216, Top = y + 5, Width = 200, Height = 20,
            Anchor = AnchorStyles.Right | AnchorStyles.Top,
            Text = "0 bản ghi", ForeColor = Theme.Dim, BackColor = Color.Transparent,
            TextAlign = ContentAlignment.MiddleRight, Font = Theme.FSm,
        };
        toolbar.Controls.Add(_lblCount);

        // ── Content: SplitContainer (list | preview) ──────────────────────
        var split = new SplitContainer
        {
            Dock = DockStyle.Fill, Orientation = Orientation.Vertical,
            SplitterWidth = 4, BackColor = Theme.Border,
            Panel2MinSize = 220,
        };
        // Đặt sau khi form hiển thị mới có kích thước thực
        Shown += (_, _) =>
        {
            try { split.SplitterDistance = Math.Max(split.Panel1MinSize, ClientSize.Width - 340); }
            catch { }
        };

        // ── ListView ──────────────────────────────────────────────────────
        _lv = Theme.MkListView();
        _lv.Dock = DockStyle.Fill;
        _lv.Columns.AddRange([
            new ColumnHeader { Text = "Thời gian",   Width = 148 },
            new ColumnHeader { Text = "Camera",      Width = 90  },
            new ColumnHeader { Text = "Region",      Width = 110 },
            new ColumnHeader { Text = "Trước",       Width = 100 },
            new ColumnHeader { Text = "Sau",         Width = 100 },
            new ColumnHeader { Text = "Conf",        Width = 60  },
            new ColumnHeader { Text = "Top-N",       Width = 240 },
        ]);
        _lv.DoubleClick           += OnOpenImageExternal;
        _lv.SelectedIndexChanged  += OnSelectionChanged;
        split.Panel1.Controls.Add(_lv);

        // ── Image preview panel ───────────────────────────────────────────
        var previewPanel = new Panel { Dock = DockStyle.Fill, BackColor = Theme.Deep };
        _pbPreview = new PictureBox
        {
            Dock = DockStyle.Fill, SizeMode = PictureBoxSizeMode.Zoom,
            BackColor = Color.FromArgb(10, 10, 20),
        };
        _pbPreview.DoubleClick += OnOpenImageExternal;

        _lblImgInfo = new Label
        {
            Dock = DockStyle.Bottom, Height = 36,
            BackColor = Theme.Card, ForeColor = Theme.Dim, Font = Theme.FSm,
            TextAlign = ContentAlignment.MiddleCenter, Padding = new Padding(4),
            Text = "Chọn bản ghi có ảnh để xem preview\nDouble-click → mở bằng viewer",
        };
        previewPanel.Controls.AddRange([_pbPreview, _lblImgInfo]);
        split.Panel2.Controls.Add(previewPanel);

        // ── Status bar ────────────────────────────────────────────────────
        var status = new Label
        {
            Dock = DockStyle.Bottom, Height = 22,
            Text = "Double-click để mở ảnh snapshot bằng viewer mặc định",
            BackColor = Theme.NavyDk, ForeColor = Theme.Dim, Font = Theme.FSm,
            TextAlign = ContentAlignment.MiddleLeft, Padding = new Padding(8, 0, 0, 0),
        };

        Controls.AddRange([split, toolbar, status]);
    }

    // ── Load filters ──────────────────────────────────────────────────────

    // Simple wrapper so ComboBox can display Name while we retrieve Id
    private sealed class FilterItem(string id, string name)
    {
        public string Id   { get; } = id;
        public string Name { get; } = name;
        public override string ToString() => Name;
    }

    private void LoadFilters()
    {
        var cameras = _db.DistinctCameras();
        _cmbCamera.Items.Clear();
        _cmbCamera.Items.Add(new FilterItem("", "(Tất cả cameras)"));
        foreach (var (id, name) in cameras) _cmbCamera.Items.Add(new FilterItem(id, name));
        _cmbCamera.SelectedIndex = 0;

        LoadRegions();
    }

    private void LoadRegions()
    {
        var regions = _db.DistinctRegions();
        _cmbRegion.Items.Clear();
        _cmbRegion.Items.Add(new FilterItem("", "(Tất cả regions)"));
        foreach (var (id, name) in regions) _cmbRegion.Items.Add(new FilterItem(id, name));
        _cmbRegion.SelectedIndex = 0;
    }

    private string? GetSelectedCameraId()
        => (_cmbCamera.SelectedItem as FilterItem) is { Id: var id } && id.Length > 0 ? id : null;

    private string? GetSelectedRegionId()
        => (_cmbRegion.SelectedItem as FilterItem) is { Id: var id } && id.Length > 0 ? id : null;

    private void Reload()
    {
        string? cameraId = GetSelectedCameraId();
        string? regionId = GetSelectedRegionId();
        DateTime? from   = _chkFrom.Checked ? _dtpFrom.Value : null;
        DateTime? to     = _chkTo.Checked   ? _dtpTo.Value   : null;

        _records = _db.Query(cameraId, regionId, from, to, 1000);
        _lv.BeginUpdate();
        _lv.Items.Clear();
        foreach (var rec in _records)
        {
            var item = new ListViewItem(rec.OccurredAt.ToString("yyyy-MM-dd HH:mm:ss.fff"));
            item.SubItems.Add(rec.CameraName.Length > 0 ? rec.CameraName : "—");
            item.SubItems.Add(rec.RegionName);
            item.SubItems.Add(rec.PrevClass);
            item.SubItems.Add(rec.NewClass);
            item.SubItems.Add($"{rec.Confidence:P1}");
            item.SubItems.Add(FormatTopN(rec.TopNJson));
            item.ForeColor = ConfColor(rec.Confidence);
            item.Tag       = rec;
            _lv.Items.Add(item);
        }
        _lv.EndUpdate();
        _lblCount.Text = $"{_records.Count} bản ghi";

        ClearPreview();
    }

    // ── Preview ───────────────────────────────────────────────────────────

    private void OnSelectionChanged(object? s, EventArgs e)
    {
        if (_lv.SelectedItems.Count == 0) { ClearPreview(); return; }
        var rec = (ClsChangeRecord)_lv.SelectedItems[0].Tag!;

        if (!string.IsNullOrEmpty(rec.ImagePath) && File.Exists(rec.ImagePath))
        {
            try
            {
                var img = Image.FromFile(rec.ImagePath);
                var old = _pbPreview.Image;
                _pbPreview.Image = img;
                old?.Dispose();
                var folder   = Path.GetDirectoryName(rec.ImagePath) ?? "";
                var fullPath = Path.Combine(folder, "full.jpg");
                _lblImgInfo.Text =
                    $"Crop: {Path.GetFileName(rec.ImagePath)}" +
                    (File.Exists(fullPath) ? "  •  full.jpg ✓" : "") + "\n" +
                    $"{rec.OccurredAt:HH:mm:ss}  •  {rec.CameraName}  •  {rec.RegionName}  •  {rec.PrevClass} → {rec.NewClass}";
                return;
            }
            catch { }
        }

        ClearPreview();
        _lblImgInfo.Text = string.IsNullOrEmpty(rec.ImagePath)
            ? "Bản ghi này không có ảnh snapshot"
            : "Không tìm thấy file ảnh";
    }

    private void ClearPreview()
    {
        var old = _pbPreview.Image; _pbPreview.Image = null; old?.Dispose();
        _lblImgInfo.Text = "Chọn bản ghi có ảnh để xem preview\nDouble-click → mở bằng viewer";
    }

    // ── Actions ───────────────────────────────────────────────────────────

    private void OnOpenImageExternal(object? s, EventArgs e)
    {
        if (_lv.SelectedItems.Count == 0) return;
        var rec = (ClsChangeRecord)_lv.SelectedItems[0].Tag!;
        if (string.IsNullOrEmpty(rec.ImagePath) || !File.Exists(rec.ImagePath))
        { MessageBox.Show("Không tìm thấy file ảnh.", "Thông báo"); return; }
        try { System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo(rec.ImagePath) { UseShellExecute = true }); }
        catch (Exception ex) { MessageBox.Show(ex.Message); }
    }

    private void OnOpenFolder(object? s, EventArgs e)
    {
        if (_lv.SelectedItems.Count == 0) return;
        var rec    = (ClsChangeRecord)_lv.SelectedItems[0].Tag!;
        var folder = string.IsNullOrEmpty(rec.ImagePath)
            ? null
            : Path.GetDirectoryName(rec.ImagePath);
        if (folder is null || !Directory.Exists(folder))
        { MessageBox.Show("Không tìm thấy thư mục ảnh.", "Thông báo"); return; }
        try { System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo("explorer.exe", folder) { UseShellExecute = true }); }
        catch (Exception ex) { MessageBox.Show(ex.Message); }
    }

    private void OnExportCsv(object? s, EventArgs e)
    {
        using var dlg = new SaveFileDialog
        {
            Title = "Xuất CSV", Filter = "CSV|*.csv",
            FileName = $"cls_history_{DateTime.Now:yyyyMMdd_HHmm}.csv",
        };
        if (dlg.ShowDialog(this) != DialogResult.OK) return;

        var lines = new List<string>
        {
            "id,occurred_at,camera_name,region_name,prev_class,new_class,confidence,image_path,top_n"
        };
        foreach (var r in _records)
            lines.Add($"{r.Id},{r.OccurredAt:o},{Esc(r.CameraName)},{Esc(r.RegionName)},{Esc(r.PrevClass)},{Esc(r.NewClass)},{r.Confidence:F4},{Esc(r.ImagePath)},{Esc(r.TopNJson)}");

        try
        {
            File.WriteAllLines(dlg.FileName, lines, System.Text.Encoding.UTF8);
            MessageBox.Show($"Đã xuất {lines.Count - 1} bản ghi.\n{dlg.FileName}", "Thành công");
        }
        catch (Exception ex) { MessageBox.Show(ex.Message); }
    }

    private void OnDeleteAll(object? s, EventArgs e)
    {
        if (MessageBox.Show("Xóa toàn bộ lịch sử?", "Xác nhận",
            MessageBoxButtons.YesNo, MessageBoxIcon.Warning) != DialogResult.Yes) return;
        _db.DeleteAll();
        LoadFilters();
        Reload();
    }

    protected override void OnFormClosed(FormClosedEventArgs e)
    {
        base.OnFormClosed(e);
        var img = _pbPreview.Image; _pbPreview.Image = null; img?.Dispose();
    }

    // ── Helpers ───────────────────────────────────────────────────────────

    private static string FormatTopN(string json)
    {
        if (string.IsNullOrEmpty(json)) return "";
        try
        {
            var items = System.Text.Json.JsonSerializer.Deserialize<List<System.Text.Json.JsonElement>>(json);
            if (items is null) return json[..Math.Min(80, json.Length)];
            return string.Join("  ", items.Take(3).Select(e =>
                $"{e.GetProperty("ClassName").GetString()}:{e.GetProperty("Conf").GetDouble():P0}"));
        }
        catch { return json[..Math.Min(80, json.Length)]; }
    }

    private static Color ConfColor(float conf)
        => conf >= 0.70f ? Theme.Ok : conf >= 0.40f ? Theme.Warn : Theme.Err;

    private static string Esc(string s) => $"\"{s.Replace("\"", "\"\"")}\"";

    private static Label MkLbl(string text, int x, int y) => new()
    {
        Text = text, Left = x, Top = y, AutoSize = true,
        ForeColor = Theme.Dim, BackColor = Color.Transparent, Font = Theme.FMain,
    };
}
