using ClsTester.Models;
using ClsTester.UI;

namespace ClsTester.Forms;

/// <summary>Dialog thêm hoặc chỉnh sửa một camera (tên + URL).</summary>
public sealed class CameraSetupForm : Form
{
    public CameraConfig? Result { get; private set; }

    private readonly TextBox  _txtName;
    private readonly ComboBox _cmbUrl;
    private readonly CameraConfig? _existing;

    public CameraSetupForm(CameraConfig? existing, List<string> urlHistory)
    {
        _existing = existing;

        Text            = existing is null ? "Thêm camera" : "Chỉnh sửa camera";
        BackColor       = Theme.BG;
        ForeColor       = Theme.Txt;
        Font            = Theme.FMain;
        Size            = new Size(530, 190);
        FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox     = false;
        MinimizeBox     = false;
        StartPosition   = FormStartPosition.CenterParent;

        var lblN = MkLbl("Tên:", 12, 18);
        _txtName = new TextBox
        {
            Left = 82, Top = 16, Width = 400,
            BackColor = Theme.Deep, ForeColor = Theme.Txt, BorderStyle = BorderStyle.FixedSingle,
            Text = existing?.Name ?? $"Camera {DateTime.Now:HHmm}",
        };

        var lblU = MkLbl("RTSP/File:", 12, 54);
        _cmbUrl = new ComboBox
        {
            Left = 82, Top = 52, Width = 400, DropDownStyle = ComboBoxStyle.DropDown,
            BackColor = Theme.Deep, ForeColor = Theme.Txt,
        };
        foreach (var h in urlHistory) _cmbUrl.Items.Add(h);
        _cmbUrl.Text = existing?.Url ?? (urlHistory.Count > 0 ? urlHistory[0] : "");

        var btnBrowse = Theme.Btn("📂", Theme.Card);
        btnBrowse.SetBounds(488, 51, 28, 26);
        btnBrowse.Click += OnBrowse;

        var btnOk = Theme.Btn("✓ OK", Theme.Accent); btnOk.SetBounds(290, 112, 90, 30);
        var btnCc = Theme.Btn("Hủy",  Theme.Card);   btnCc.SetBounds(390, 112, 90, 30);
        btnOk.Click += OnOk;
        btnCc.Click += (_, _) => DialogResult = DialogResult.Cancel;

        Controls.AddRange([lblN, _txtName, lblU, _cmbUrl, btnBrowse, btnOk, btnCc]);
        AcceptButton = btnOk;
        CancelButton = btnCc;
    }

    private void OnBrowse(object? s, EventArgs e)
    {
        using var d = new OpenFileDialog { Filter = "Video|*.mp4;*.avi;*.mkv;*.mov;*.ts;*.m4v|Tất cả|*.*" };
        if (d.ShowDialog() == DialogResult.OK) _cmbUrl.Text = d.FileName;
    }

    private void OnOk(object? s, EventArgs e)
    {
        var name = _txtName.Text.Trim();
        var url  = _cmbUrl.Text.Trim();
        if (string.IsNullOrEmpty(name) || string.IsNullOrEmpty(url))
        { MessageBox.Show("Vui lòng nhập đầy đủ tên và URL."); return; }

        Result = new CameraConfig
        {
            Id      = _existing?.Id ?? Guid.NewGuid().ToString("N")[..8],
            Name    = name,
            Url     = url,
            Enabled = _existing?.Enabled ?? true,
            Regions = _existing?.Regions ?? [],
        };
        DialogResult = DialogResult.OK;
    }

    private static Label MkLbl(string text, int x, int y) => new()
    {
        Text = text, Left = x, Top = y, AutoSize = true,
        ForeColor = Theme.Dim, BackColor = Color.Transparent, Font = Theme.FMain,
    };
}
