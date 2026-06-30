namespace ClsTester.UI;

/// <summary>KZTEK brand palette + widget factory — dark theme.</summary>
internal static class Theme
{
    // ── Palette ────────────────────────────────────────────────────────────
    public static readonly Color BG      = Color.FromArgb(0x1e, 0x1e, 0x2e);
    public static readonly Color Card    = Color.FromArgb(0x2a, 0x2a, 0x3e);
    public static readonly Color Deep    = Color.FromArgb(0x16, 0x16, 0x2a);
    public static readonly Color NavyDk  = Color.FromArgb(0x18, 0x18, 0x2e);
    public static readonly Color Navy    = Color.FromArgb(0x4A, 0x3F, 0x8C);
    public static readonly Color Accent  = Color.FromArgb(0xF0, 0x59, 0x22);  // cam KZTEK
    public static readonly Color Txt     = Color.FromArgb(0xe0, 0xe0, 0xf0);
    public static readonly Color Dim     = Color.FromArgb(0x90, 0x90, 0xb0);
    public static readonly Color Border  = Color.FromArgb(0x3a, 0x3a, 0x50);
    public static readonly Color Ok      = Color.FromArgb(0x4c, 0xaf, 0x50);
    public static readonly Color Warn    = Color.FromArgb(0xff, 0xb3, 0x00);
    public static readonly Color Err     = Color.FromArgb(0xef, 0x53, 0x50);

    // ── Class palette (up to 10 classes with distinct colours) ─────────────
    private static readonly Color[] _classPalette =
    [
        Color.FromArgb(0xF0, 0x59, 0x22), // 0 — cam KZTEK
        Color.FromArgb(0x4f, 0xc3, 0xf7), // 1 — xanh nhạt
        Color.FromArgb(0x81, 0xc7, 0x84), // 2 — xanh lá
        Color.FromArgb(0xff, 0xf1, 0x76), // 3 — vàng
        Color.FromArgb(0xce, 0x93, 0xd8), // 4 — tím
        Color.FromArgb(0x80, 0xde, 0xea), // 5 — cyan
        Color.FromArgb(0xff, 0xab, 0x91), // 6 — đào
        Color.FromArgb(0xa5, 0xd6, 0xa7), // 7 — xanh mint
        Color.FromArgb(0x90, 0xca, 0xf9), // 8 — blue nhạt
        Color.FromArgb(0xff, 0xcc, 0x02), // 9 — vàng đậm
    ];

    public static Color ClassColor(int classId) =>
        _classPalette[((classId % _classPalette.Length) + _classPalette.Length) % _classPalette.Length];

    public static Color ConfColor(float conf) =>
        conf >= 0.70f ? Ok :
        conf >= 0.40f ? Warn : Err;

    // ── Fonts ─────────────────────────────────────────────────────────────
    public static readonly Font FMain  = new("Segoe UI", 9f);
    public static readonly Font FBold  = new("Segoe UI Semibold", 9f);
    public static readonly Font FSm    = new("Segoe UI", 8f);
    public static readonly Font FMono  = new("Consolas", 8.5f);

    // ── Widget factory ────────────────────────────────────────────────────

    public static Button Btn(string text, Color bg, Color? fg = null)
    {
        var b = new Button
        {
            Text       = text,
            BackColor  = bg,
            ForeColor  = fg ?? Txt,
            Font       = FMain,
            FlatStyle  = FlatStyle.Flat,
            Cursor     = Cursors.Hand,
            AutoSize   = false,
            Height     = 26,
        };
        b.FlatAppearance.BorderSize = 0;
        return b;
    }

    public static Label Lbl(string text, Font? font = null, Color? fg = null)
        => new() { Text = text, Font = font ?? FMain, ForeColor = fg ?? Txt,
                   AutoSize = true, BackColor = Color.Transparent };

    public static NumericUpDown Num(decimal min, decimal max, decimal val, int w)
        => new()
        {
            Minimum = min, Maximum = max, Value = Math.Clamp(val, min, max),
            Width = w, BackColor = Deep, ForeColor = Txt,
            BorderStyle = BorderStyle.FixedSingle, Font = FMain,
        };

    public static ListView MkListView(bool fullRow = true)
        => new()
        {
            View = View.Details, FullRowSelect = fullRow,
            BackColor = Deep, ForeColor = Txt, BorderStyle = BorderStyle.None,
            GridLines = false, HeaderStyle = ColumnHeaderStyle.Nonclickable,
            Font = FMain,
        };
}
