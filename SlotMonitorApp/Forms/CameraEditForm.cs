using SlotMonitor.Models;
using SlotMonitor.UI;

namespace SlotMonitor.Forms;

/// <summary>Dialog thêm / sửa thông tin camera RTSP.</summary>
public sealed class CameraEditForm : Form
{
    private readonly TextBox  _txtName;
    private readonly TextBox  _txtUrl;
    private readonly CheckBox _chkEnabled;

    public CameraConfig Result { get; private set; }

    public CameraEditForm(CameraConfig? existing = null)
    {
        Result = existing is null
            ? new CameraConfig()
            : new CameraConfig
            {
                Id      = existing.Id,
                Name    = existing.Name,
                RtspUrl = existing.RtspUrl,
                Enabled = existing.Enabled,
            };

        Text            = existing is null ? "Thêm camera" : "Sửa camera";
        Size            = new Size(500, 230);
        MinimumSize     = new Size(420, 210);
        BackColor       = Theme.BG;
        ForeColor       = Theme.Txt;
        Font            = Theme.FMain;
        FormBorderStyle = FormBorderStyle.FixedDialog;
        StartPosition   = FormStartPosition.CenterParent;
        MaximizeBox     = false;
        MinimizeBox     = false;

        var tbl = new TableLayoutPanel
        {
            Dock = DockStyle.Fill, ColumnCount = 2, RowCount = 4,
            Padding = new Padding(14, 10, 14, 0),
        };
        tbl.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 110));
        tbl.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        tbl.RowStyles.Add(new RowStyle(SizeType.Absolute, 36));
        tbl.RowStyles.Add(new RowStyle(SizeType.Absolute, 36));
        tbl.RowStyles.Add(new RowStyle(SizeType.Absolute, 36));
        tbl.RowStyles.Add(new RowStyle(SizeType.Percent, 100));

        _txtName    = AddRow(tbl, 0, "Tên camera:", Result.Name);
        _txtUrl     = AddRow(tbl, 1, "RTSP URL:",   Result.RtspUrl);
        _txtUrl.Font = Theme.FMono;

        _chkEnabled = new CheckBox
        {
            Text = "Kích hoạt", Checked = Result.Enabled,
            ForeColor = Theme.Txt, BackColor = Color.Transparent,
            FlatStyle = FlatStyle.Flat,
        };
        tbl.Controls.Add(MkLabel("Trạng thái:"), 0, 2);
        tbl.Controls.Add(_chkEnabled, 1, 2);

        var btnPanel = new FlowLayoutPanel
        {
            Dock = DockStyle.Bottom, Height = 50, BackColor = Theme.Card,
            FlowDirection = FlowDirection.RightToLeft,
            Padding = new Padding(8), WrapContents = false,
        };

        var btnCancel = Theme.Btn("Hủy", Theme.Card, Theme.Dim);
        var btnOk     = Theme.Btn("💾 Lưu", Theme.Accent, Color.White);
        btnOk.Width = btnCancel.Width = 90;

        btnCancel.Click += (_, _) => { DialogResult = DialogResult.Cancel; Close(); };
        btnOk.Click     += OnSave;

        btnPanel.Controls.AddRange([btnCancel, btnOk]);
        Controls.AddRange([tbl, btnPanel]);

        AcceptButton = btnOk;
        CancelButton = btnCancel;
    }

    private void OnSave(object? s, EventArgs e)
    {
        var name = _txtName.Text.Trim();
        var url  = _txtUrl.Text.Trim();
        if (string.IsNullOrEmpty(name)) { MessageBox.Show("Vui lòng nhập tên camera.", "Thông báo"); return; }
        if (string.IsNullOrEmpty(url))  { MessageBox.Show("Vui lòng nhập RTSP URL.",   "Thông báo"); return; }
        Result.Name    = name;
        Result.RtspUrl = url;
        Result.Enabled = _chkEnabled.Checked;
        DialogResult   = DialogResult.OK;
        Close();
    }

    private static TextBox AddRow(TableLayoutPanel t, int row, string label, string value)
    {
        t.Controls.Add(MkLabel(label), 0, row);
        var tb = new TextBox
        {
            Text = value, Dock = DockStyle.Fill,
            BackColor = Theme.Deep, ForeColor = Theme.Txt,
            BorderStyle = BorderStyle.FixedSingle,
        };
        t.Controls.Add(tb, 1, row);
        return tb;
    }

    private static Label MkLabel(string text) => new()
    {
        Text = text, ForeColor = Theme.Dim, BackColor = Color.Transparent,
        TextAlign = ContentAlignment.MiddleLeft, Dock = DockStyle.Fill,
    };
}
