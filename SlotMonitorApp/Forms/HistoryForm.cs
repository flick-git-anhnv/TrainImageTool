using SlotMonitor.Data;
using SlotMonitor.Helpers;
using SlotMonitor.UI;

namespace SlotMonitor.Forms;

/// <summary>Cửa sổ xem lịch sử thay đổi trạng thái từ DB.</summary>
public sealed class HistoryForm : Form
{
    private readonly SlotDb      _db;
    private readonly AppSettings _cfg;
    private readonly ListView    _list;
    private readonly ComboBox    _cmbCam;
    private readonly Label       _lblCount;

    public HistoryForm(SlotDb db, AppSettings cfg)
    {
        _db  = db;
        _cfg = cfg;

        Text          = "KZTEK — Lịch sử thay đổi trạng thái";
        Size          = new Size(960, 560);
        MinimumSize   = new Size(700, 400);
        BackColor     = Theme.BG;
        ForeColor     = Theme.Txt;
        Font          = Theme.FMain;
        StartPosition = FormStartPosition.CenterParent;

        // ── Toolbar ───────────────────────────────────────────────────────
        var toolbar = new Panel { Dock = DockStyle.Top, Height = 42, BackColor = Theme.Card };

        var lblCam = Theme.Lbl("Camera:");
        lblCam.Location = new Point(8, 12);

        _cmbCam = new ComboBox
        {
            Left = 70, Top = 8, Width = 200, DropDownStyle = ComboBoxStyle.DropDownList,
            BackColor = Theme.Deep, ForeColor = Theme.Txt,
        };
        _cmbCam.Items.Add("Tất cả");
        foreach (var c in cfg.Cameras) _cmbCam.Items.Add($"{c.Name} [{c.Id}]");
        _cmbCam.SelectedIndex = 0;

        var btnRefresh = Theme.Btn("🔄 Làm mới", Theme.Navy);
        btnRefresh.Location = new Point(282, 6);
        btnRefresh.Width = 110;

        _lblCount = Theme.Lbl("", Theme.FSm, Theme.Dim);
        _lblCount.Location = new Point(402, 13);

        var btnFolder = Theme.Btn("📁 Thư mục ảnh", Theme.Card);
        btnFolder.Location = new Point(toolbar.Width - 150, 6);
        btnFolder.Width    = 140;
        btnFolder.Anchor   = AnchorStyles.Right | AnchorStyles.Top;
        btnFolder.Click   += (_, _) =>
        {
            try { System.Diagnostics.Process.Start("explorer.exe", _cfg.ImageFolder); } catch { }
        };

        toolbar.Controls.AddRange([lblCam, _cmbCam, btnRefresh, _lblCount, btnFolder]);

        // ── ListView ──────────────────────────────────────────────────────
        _list = new ListView
        {
            Dock = DockStyle.Fill, View = View.Details, FullRowSelect = true,
            BackColor = Theme.Deep, ForeColor = Theme.Txt, BorderStyle = BorderStyle.None,
            GridLines = false,
        };
        _list.Columns.AddRange([
            new ColumnHeader { Text = "Thời gian",   Width = 155 },
            new ColumnHeader { Text = "Camera",      Width = 140 },
            new ColumnHeader { Text = "Trạng thái cũ", Width = 110 },
            new ColumnHeader { Text = "Trạng thái mới", Width = 110 },
            new ColumnHeader { Text = "Conf",        Width = 70  },
            new ColumnHeader { Text = "Detect",      Width = 60  },
            new ColumnHeader { Text = "Ảnh sự kiện", Width = 260 },
        ]);

        var vscroll = new VScrollBar { Dock = DockStyle.Right };
        _list.Scrollable = true;
        _list.DoubleClick += OnDoubleClick;

        Controls.AddRange([_list, toolbar]);

        btnRefresh.Click            += (_, _) => Reload();
        _cmbCam.SelectedIndexChanged += (_, _) => Reload();
        Reload();
    }

    private void Reload()
    {
        string? camId = null;
        int idx = _cmbCam.SelectedIndex;
        if (idx >= 1 && idx - 1 < _cfg.Cameras.Count)
            camId = _cfg.Cameras[idx - 1].Id;

        var records = _db.Query(camId, limit: 2000);
        _list.BeginUpdate();
        _list.Items.Clear();

        foreach (var r in records)
        {
            var item = new ListViewItem(r.OccurredAt.ToString("yyyy-MM-dd HH:mm:ss.fff"));
            item.SubItems.Add(r.CameraName);
            item.SubItems.Add(StateLabel(r.PrevState));
            item.SubItems.Add(StateLabel(r.NewState));
            item.SubItems.Add($"{r.Confidence:P0}");
            item.SubItems.Add(r.DetCount.ToString());
            item.SubItems.Add(r.ImagePath);
            item.ForeColor = Theme.StateColor(r.NewState);
            item.Tag       = r;
            _list.Items.Add(item);
        }

        _list.EndUpdate();
        _lblCount.Text = $"Tổng: {records.Count} sự kiện";
    }

    private void OnDoubleClick(object? s, EventArgs e)
    {
        if (_list.SelectedItems.Count == 0) return;
        var rec = (StateChangeRecord)_list.SelectedItems[0].Tag!;
        if (string.IsNullOrEmpty(rec.ImagePath)) return;
        if (!File.Exists(rec.ImagePath)) { MessageBox.Show("File ảnh không tồn tại."); return; }
        try
        {
            System.Diagnostics.Process.Start(
                new System.Diagnostics.ProcessStartInfo(rec.ImagePath) { UseShellExecute = true });
        }
        catch { }
    }

    private static string StateLabel(string s) => s switch
    {
        "Empty"    => "🟢 Trống",
        "Occupied" => "🔴 Có xe",
        _          => s,
    };
}
