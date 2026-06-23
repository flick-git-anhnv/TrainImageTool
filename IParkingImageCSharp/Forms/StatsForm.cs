using IParkingImage.UI;
using static IParkingImage.UI.Theme;

namespace IParkingImage.Forms;

/// <summary>
/// Cửa sổ thống kê: quét thư mục output, đếm ảnh theo loại xe / ngày / buổi / làn.
/// </summary>
public class StatsForm : Form
{
    private readonly string _outDir;

    private TabControl _tabs = null!;
    private Label      _lblLoading = null!;
    private Button     _btnRefresh = null!;
    private Label      _lblTotal = null!;

    public StatsForm(string outputDir)
    {
        _outDir         = outputDir;
        Text            = "Thống kê ảnh — " + outputDir;
        Size            = new Size(960, 640);
        MinimumSize     = new Size(720, 440);
        BackColor       = BG;
        ForeColor       = Txt;
        Font            = FMain;
        StartPosition   = FormStartPosition.CenterParent;
        BuildUI();
        Shown += (s, e) => LoadStats();
    }

    // ════════════════════════════════════════════════════════════════════
    //  Build UI
    // ════════════════════════════════════════════════════════════════════

    private void BuildUI()
    {
        SuspendLayout();

        // Header
        var header = new Panel { Height = 40, Dock = DockStyle.Top, BackColor = Card, Padding = new Padding(10, 0, 10, 0) };
        var dirLbl = new Label { Text = $"Thư mục: {_outDir}", Dock = DockStyle.Left, ForeColor = Dim, Font = FSm, TextAlign = ContentAlignment.MiddleLeft, AutoSize = false, Width = 700 };
        _btnRefresh = Btn("↺  Làm mới", Navy); _btnRefresh.Dock = DockStyle.Right; _btnRefresh.Width = 100;
        _btnRefresh.Click += (s, e) => LoadStats();
        header.Controls.Add(dirLbl);
        header.Controls.Add(_btnRefresh);
        Controls.Add(header);

        // Footer stats
        var footer = new Panel { Height = 28, Dock = DockStyle.Bottom, BackColor = NavyDk, Padding = new Padding(8, 0, 8, 0) };
        _lblTotal = new Label { Dock = DockStyle.Fill, ForeColor = Txt, Font = FSmB, TextAlign = ContentAlignment.MiddleLeft };
        footer.Controls.Add(_lblTotal);
        Controls.Add(footer);

        // Loading label
        _lblLoading = new Label { Text = "Đang quét...", Dock = DockStyle.Fill, ForeColor = Accent, Font = FBold, TextAlign = ContentAlignment.MiddleCenter, Visible = false, BackColor = BG };

        // Tabs
        _tabs = new TabControl { Dock = DockStyle.Fill, BackColor = BG };
        _tabs.Appearance = TabAppearance.Normal;
        _tabs.DrawMode = TabDrawMode.OwnerDrawFixed;
        _tabs.ItemSize = new Size(140, 28);
        _tabs.DrawItem += OnDrawTab;

        _tabs.TabPages.Add(MakeTab("Theo loại xe", "vtypes"));
        _tabs.TabPages.Add(MakeTab("Theo ngày", "dates"));
        _tabs.TabPages.Add(MakeTab("Theo buổi", "buoi"));
        _tabs.TabPages.Add(MakeTab("Theo làn", "lane"));

        Controls.Add(_lblLoading);
        Controls.Add(_tabs);

        ResumeLayout(true);
    }

    private static TabPage MakeTab(string title, string tag)
    {
        var tp = new TabPage(title) { Tag = tag, BackColor = BG, UseVisualStyleBackColor = false };
        return tp;
    }

    private void OnDrawTab(object? sender, DrawItemEventArgs e)
    {
        var tc  = (TabControl)sender!;
        var tab = tc.TabPages[e.Index];
        var bg  = e.Index == tc.SelectedIndex ? Card : BG;
        var fg  = e.Index == tc.SelectedIndex ? Txt : Dim;
        e.Graphics.FillRectangle(new SolidBrush(bg), e.Bounds);
        var text = tab.Text;
        using var sf = new StringFormat { Alignment = StringAlignment.Center, LineAlignment = StringAlignment.Center };
        e.Graphics.DrawString(text, FSmB, new SolidBrush(fg), e.Bounds, sf);
        if (e.Index == tc.SelectedIndex)
            e.Graphics.DrawLine(new Pen(Accent, 2), e.Bounds.Left, e.Bounds.Bottom - 1, e.Bounds.Right, e.Bounds.Bottom - 1);
    }

    // ════════════════════════════════════════════════════════════════════
    //  Data loading
    // ════════════════════════════════════════════════════════════════════

    private void LoadStats()
    {
        _btnRefresh.Enabled = false;
        _lblLoading.Visible = true;
        _lblLoading.BringToFront();

        Task.Run(() =>
        {
            var stats = ScanDirectory(_outDir);
            Invoke(() =>
            {
                PopulateTabs(stats);
                _lblLoading.Visible = false;
                _btnRefresh.Enabled = true;
            });
        });
    }

    // ════════════════════════════════════════════════════════════════════
    //  Scanner
    // ════════════════════════════════════════════════════════════════════

    private record ImageEntry(string Vtype, string SubFolder, string Date, string Buoi, string Lane);

    private static List<ImageEntry> ScanDirectory(string root)
    {
        var result = new List<ImageEntry>();
        if (!Directory.Exists(root)) return result;

        // Structure: <root>/<vtype>/<subfolder>/<date>/<buoi>/<lane>/*.jpg
        foreach (var vtypeDir in Directory.EnumerateDirectories(root))
        {
            var vtype = Path.GetFileName(vtypeDir);
            if (vtype == "bad") continue;

            foreach (var subDir in Directory.EnumerateDirectories(vtypeDir))
            {
                var sub = Path.GetFileName(subDir);
                foreach (var dateDir in Directory.EnumerateDirectories(subDir))
                {
                    var date = Path.GetFileName(dateDir);
                    foreach (var buoiDir in Directory.EnumerateDirectories(dateDir))
                    {
                        var buoi = Path.GetFileName(buoiDir);
                        foreach (var laneDir in Directory.EnumerateDirectories(buoiDir))
                        {
                            var lane = Path.GetFileName(laneDir);
                            int count = Directory.EnumerateFiles(laneDir, "*.jpg", SearchOption.TopDirectoryOnly).Count();
                            for (int i = 0; i < count; i++)
                                result.Add(new ImageEntry(vtype, sub, date, buoi, lane));
                        }
                        // jpg directly in buoi (no lane subfolder)
                        int direct = Directory.EnumerateFiles(buoiDir, "*.jpg", SearchOption.TopDirectoryOnly).Count();
                        for (int i = 0; i < direct; i++)
                            result.Add(new ImageEntry(vtype, sub, date, buoi, "—"));
                    }
                }
            }
        }
        return result;
    }

    // ════════════════════════════════════════════════════════════════════
    //  Populate tabs
    // ════════════════════════════════════════════════════════════════════

    private void PopulateTabs(List<ImageEntry> data)
    {
        int total = data.Count;
        _lblTotal.Text = $"Tổng: {total:N0} ảnh";

        foreach (TabPage tp in _tabs.TabPages)
        {
            tp.Controls.Clear();
            var tag = (string)tp.Tag!;
            DataGridView grid = tag switch {
                "vtypes" => BuildVtypeGrid(data),
                "dates"  => BuildDateGrid(data),
                "buoi"   => BuildBuoiGrid(data),
                "lane"   => BuildLaneGrid(data),
                _        => new DataGridView()
            };
            tp.Controls.Add(grid);
        }
    }

    // ── By vehicle type ───────────────────────────────────────────────
    private DataGridView BuildVtypeGrid(List<ImageEntry> data)
    {
        var grouped = data
            .GroupBy(e => e.Vtype)
            .Select(g => new {
                LoaiXe = g.Key,
                AnhXe  = g.Count(e => !e.SubFolder.Contains("toan_canh") && !e.SubFolder.Contains("bsx")),
                ToanCanh = g.Count(e => e.SubFolder.Contains("toan_canh")),
                BSX    = g.Count(e => e.SubFolder.Contains("bsx")),
                Tong   = g.Count(),
            })
            .OrderByDescending(x => x.Tong)
            .ToList();

        var grid = MakeGrid();
        AddColumn(grid, "Loại xe",   250);
        AddColumn(grid, "Ảnh xe",    100);
        AddColumn(grid, "Toàn cảnh", 100);
        AddColumn(grid, "Biển cắt",  100);
        AddColumn(grid, "Tổng",      100, bold: true, color: Accent);

        foreach (var row in grouped)
            grid.Rows.Add(row.LoaiXe, row.AnhXe.ToString("N0"), row.ToanCanh.ToString("N0"), row.BSX.ToString("N0"), row.Tong.ToString("N0"));

        AddTotalRow(grid, ["", Sum(grouped, x => x.AnhXe), Sum(grouped, x => x.ToanCanh), Sum(grouped, x => x.BSX), Sum(grouped, x => x.Tong)]);
        return grid;
    }

    // ── By date ───────────────────────────────────────────────────────
    private DataGridView BuildDateGrid(List<ImageEntry> data)
    {
        var grouped = data
            .GroupBy(e => e.Date)
            .Select(g => new { Date = g.Key, Tong = g.Count(), VtypeCount = g.Select(e => e.Vtype).Distinct().Count() })
            .OrderBy(x => x.Date)
            .ToList();

        var grid = MakeGrid();
        AddColumn(grid, "Ngày",       130);
        AddColumn(grid, "Ảnh lưu",    120, bold: true, color: Ok);
        AddColumn(grid, "Loại xe",    80);

        foreach (var row in grouped)
            grid.Rows.Add(row.Date, row.Tong.ToString("N0"), row.VtypeCount.ToString());

        AddTotalRow(grid, ["Tổng", Sum(grouped, x => x.Tong), ""]);
        return grid;
    }

    // ── By buoi ───────────────────────────────────────────────────────
    private DataGridView BuildBuoiGrid(List<ImageEntry> data)
    {
        var order = new[] { "sang", "trua", "chieu", "toi" };
        var grouped = data
            .GroupBy(e => e.Buoi)
            .Select(g => new { Buoi = g.Key, Tong = g.Count() })
            .OrderBy(x => Array.IndexOf(order, x.Buoi) < 0 ? 99 : Array.IndexOf(order, x.Buoi))
            .ToList();

        var grid = MakeGrid();
        AddColumn(grid, "Buổi",       120);
        AddColumn(grid, "Ảnh lưu",    150, bold: true);
        AddColumn(grid, "Tỉ lệ %",    100);

        int total = grouped.Sum(x => x.Tong);
        foreach (var row in grouped)
        {
            double pct = total > 0 ? row.Tong * 100.0 / total : 0;
            var label = row.Buoi switch { "sang" => "Sáng (05-12h)", "trua" => "Trưa (12-14h)", "chieu" => "Chiều (14-18h)", "toi" => "Tối (18-05h)", _ => row.Buoi };
            grid.Rows.Add(label, row.Tong.ToString("N0"), $"{pct:F1}%");
        }
        AddTotalRow(grid, ["Tổng", total.ToString("N0"), "100%"]);
        return grid;
    }

    // ── By lane ───────────────────────────────────────────────────────
    private DataGridView BuildLaneGrid(List<ImageEntry> data)
    {
        var grouped = data
            .GroupBy(e => e.Lane)
            .Select(g => new { Lane = g.Key, Tong = g.Count(), Dates = g.Select(e => e.Date).Distinct().Count() })
            .OrderByDescending(x => x.Tong)
            .ToList();

        var grid = MakeGrid();
        AddColumn(grid, "Làn",         220);
        AddColumn(grid, "Ảnh lưu",     130, bold: true);
        AddColumn(grid, "Số ngày có ảnh", 130);

        foreach (var row in grouped)
            grid.Rows.Add(row.Lane, row.Tong.ToString("N0"), row.Dates.ToString());

        AddTotalRow(grid, ["Tổng", Sum(grouped, x => x.Tong), grouped.Count + " làn"]);
        return grid;
    }

    // ════════════════════════════════════════════════════════════════════
    //  Grid helpers
    // ════════════════════════════════════════════════════════════════════

    private static DataGridView MakeGrid()
    {
        var g = new DataGridView {
            Dock = DockStyle.Fill,
            BackgroundColor = BG, GridColor = Color.FromArgb(50, 50, 70),
            ForeColor = Txt, Font = FMain,
            RowHeadersVisible = false, AllowUserToAddRows = false,
            ReadOnly = true, SelectionMode = DataGridViewSelectionMode.FullRowSelect,
            AutoSizeRowsMode = DataGridViewAutoSizeRowsMode.AllCells,
            ColumnHeadersHeightSizeMode = DataGridViewColumnHeadersHeightSizeMode.DisableResizing,
            ColumnHeadersHeight = 28,
            BorderStyle = BorderStyle.None,
            CellBorderStyle = DataGridViewCellBorderStyle.SingleHorizontal,
        };
        g.ColumnHeadersDefaultCellStyle.BackColor  = NavyDk;
        g.ColumnHeadersDefaultCellStyle.ForeColor  = Color.White;
        g.ColumnHeadersDefaultCellStyle.Font       = FSmB;
        g.ColumnHeadersDefaultCellStyle.Alignment  = DataGridViewContentAlignment.MiddleLeft;
        g.DefaultCellStyle.BackColor    = BG;
        g.DefaultCellStyle.ForeColor    = Txt;
        g.DefaultCellStyle.SelectionBackColor = Navy;
        g.DefaultCellStyle.SelectionForeColor = Color.White;
        g.AlternatingRowsDefaultCellStyle.BackColor = Card;
        return g;
    }

    private static void AddColumn(DataGridView g, string header, int w, bool bold = false, Color? color = null)
    {
        var col = new DataGridViewTextBoxColumn {
            HeaderText = header, Width = w, SortMode = DataGridViewColumnSortMode.Automatic,
        };
        if (bold || color.HasValue)
        {
            col.DefaultCellStyle.Font      = bold ? FBold : FMain;
            col.DefaultCellStyle.ForeColor = color ?? Txt;
        }
        g.Columns.Add(col);
    }

    private static void AddTotalRow(DataGridView g, string[] values)
    {
        int idx = g.Rows.Add(values.Cast<object>().ToArray());
        var row = g.Rows[idx];
        row.DefaultCellStyle.BackColor = NavyDk;
        row.DefaultCellStyle.ForeColor = Accent;
        row.DefaultCellStyle.Font      = FBold;
    }

    private static string Sum<T>(IEnumerable<T> items, Func<T, int> sel) =>
        items.Sum(sel).ToString("N0");
}
