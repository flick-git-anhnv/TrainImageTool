namespace IParkingDetect.UI;

/// <summary>KZTEK brand colors + WinForms control factories (dark theme).</summary>
public static class Theme
{
    public static readonly Color BG     = Color.FromArgb(30,  30,  46);
    public static readonly Color Card   = Color.FromArgb(42,  42,  62);
    public static readonly Color Deep   = Color.FromArgb(22,  22,  42);
    public static readonly Color Accent = Color.FromArgb(240, 89,  34);   // #F05922 cam
    public static readonly Color Navy   = Color.FromArgb(74,  63,  140);  // #4A3F8C
    public static readonly Color NavyDk = Color.FromArgb(37,  28,  83);   // #251C53
    public static readonly Color Txt    = Color.FromArgb(224, 224, 240);
    public static readonly Color Dim    = Color.FromArgb(144, 144, 176);
    public static readonly Color Ok     = Color.FromArgb(76,  175, 80);
    public static readonly Color Warn   = Color.FromArgb(255, 183, 77);
    public static readonly Color Err    = Color.FromArgb(255, 99,  71);
    public static readonly Color Border = Color.FromArgb(60,  60,  90);

    public static readonly Font FMain = new("Segoe UI", 9f);
    public static readonly Font FBold = new("Segoe UI", 9f, FontStyle.Bold);
    public static readonly Font FMono = new("Consolas", 8.5f);
    public static readonly Font FSm   = new("Segoe UI", 8f);
    public static readonly Font FSmB  = new("Segoe UI", 8f, FontStyle.Bold);
    public static readonly Font FLg   = new("Segoe UI", 10.5f, FontStyle.Bold);

    // ── Bbox palette per class ───────────────────────────────────────────
    private static readonly Color[] _bboxPalette =
    [
        Color.FromArgb(240, 89,  34),   // 0 cam (plate)
        Color.FromArgb(76,  175, 80),   // 1 xanh lá (vehicle)
        Color.FromArgb(33,  150, 243),  // 2 xanh dương
        Color.FromArgb(156, 39,  176),  // 3 tím
        Color.FromArgb(255, 183, 77),   // 4 vàng
        Color.FromArgb(0,   188, 212),  // 5 cyan
        Color.FromArgb(255, 87,  34),   // 6 deep orange
        Color.FromArgb(63,  81,  181),  // 7 indigo
    ];

    public static Color BboxColor(int classId) => _bboxPalette[classId % _bboxPalette.Length];

    // ── Control factories ─────────────────────────────────────────────────

    public static Label Lbl(string text, Font? font = null, Color? fg = null) => new()
    {
        Text = text, AutoSize = true, BackColor = Color.Transparent,
        ForeColor = fg ?? Txt, Font = font ?? FMain,
    };

    public static Button Btn(string text, Color? bg = null, Color? fg = null)
    {
        var b = new Button
        {
            Text = text, AutoSize = true,
            BackColor = bg ?? Navy, ForeColor = fg ?? Color.White,
            Font = FBold, FlatStyle = FlatStyle.Flat, Height = 28,
            Padding = new Padding(8, 0, 8, 0), Cursor = Cursors.Hand,
            UseVisualStyleBackColor = false,
        };
        b.FlatAppearance.BorderSize = 0;
        b.FlatAppearance.MouseOverBackColor = Lighten(bg ?? Navy, 20);
        return b;
    }

    public static TrackBar Slider(int min, int max, int val, int w = 130) => new()
    {
        Minimum = min, Maximum = max, Value = Math.Clamp(val, min, max),
        Width = w, Height = 24, TickFrequency = (max - min) / 5,
        BackColor = BG, TickStyle = TickStyle.None,
    };

    public static ComboBox Cmb(string[]? items = null, bool readOnly = false, int w = 180) {
        var c = new ComboBox {
            Width = w, BackColor = Card, ForeColor = Txt, Font = FMain,
            DropDownStyle = readOnly ? ComboBoxStyle.DropDownList : ComboBoxStyle.DropDown,
            FlatStyle = FlatStyle.Flat,
        };
        if (items != null) c.Items.AddRange(items);
        return c;
    }

    public static CheckBox Chk(string text, bool chk = false) => new()
    {
        Text = text, Checked = chk, AutoSize = true,
        ForeColor = Txt, BackColor = Color.Transparent,
        FlatStyle = FlatStyle.Flat, Cursor = Cursors.Hand,
    };

    public static NumericUpDown Num(decimal min, decimal max, decimal val, int w = 60) => new()
    {
        Minimum = min, Maximum = max, Value = Math.Clamp(val, min, max),
        Width = w, BackColor = Card, ForeColor = Txt,
        BorderStyle = BorderStyle.FixedSingle, Font = FMain,
        TextAlign = HorizontalAlignment.Center,
    };

    public static Panel SectionHdr(string title) {
        var p = new Panel { Height = 22, BackColor = NavyDk, Dock = DockStyle.Top };
        p.Controls.Add(new Label {
            Text = "  " + title, Dock = DockStyle.Fill,
            ForeColor = Color.White, Font = FSmB,
            TextAlign = ContentAlignment.MiddleLeft, BackColor = Color.Transparent,
        });
        return p;
    }

    public static FlowLayoutPanel Row() => new()
    {
        FlowDirection = FlowDirection.LeftToRight, WrapContents = false,
        AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink,
        BackColor = Color.Transparent, Margin = new Padding(0, 2, 0, 2),
    };

    public static Color Lighten(Color c, int by) =>
        Color.FromArgb(Math.Min(255, c.R + by), Math.Min(255, c.G + by), Math.Min(255, c.B + by));
}
