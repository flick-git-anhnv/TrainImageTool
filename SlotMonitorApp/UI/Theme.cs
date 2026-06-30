namespace SlotMonitor.UI;

/// <summary>KZTEK brand palette + WinForms helpers — dark theme.</summary>
public static class Theme
{
    // ── Palette ───────────────────────────────────────────────────────────
    public static readonly Color BG     = Color.FromArgb(30,  30,  46);
    public static readonly Color Card   = Color.FromArgb(42,  42,  62);
    public static readonly Color Deep   = Color.FromArgb(22,  22,  42);
    public static readonly Color Accent = Color.FromArgb(240, 89,  34);   // #F05922
    public static readonly Color Navy   = Color.FromArgb(74,  63,  140);  // #4A3F8C
    public static readonly Color NavyDk = Color.FromArgb(37,  28,  83);   // #251C53
    public static readonly Color Txt    = Color.FromArgb(224, 224, 240);
    public static readonly Color Dim    = Color.FromArgb(144, 144, 176);
    public static readonly Color Ok     = Color.FromArgb(76,  175, 80);
    public static readonly Color Warn   = Color.FromArgb(255, 183, 77);
    public static readonly Color Err    = Color.FromArgb(239, 83,  80);
    public static readonly Color Border = Color.FromArgb(60,  60,  90);

    // ── Fonts ─────────────────────────────────────────────────────────────
    public static readonly Font FMain = new("Segoe UI",  9f);
    public static readonly Font FBold = new("Segoe UI",  9f, FontStyle.Bold);
    public static readonly Font FMono = new("Consolas",  8.5f);
    public static readonly Font FSm   = new("Segoe UI",  8f);
    public static readonly Font FLg   = new("Segoe UI",  11f, FontStyle.Bold);

    // ── State colors ──────────────────────────────────────────────────────
    public static Color StateColor(string state) => state switch
    {
        "Empty"    => Ok,
        "Occupied" => Err,
        _          => Dim,
    };

    // ── Control factories ─────────────────────────────────────────────────

    public static Button Btn(string text, Color? bg = null, Color? fg = null)
    {
        var b = new Button
        {
            Text = text, AutoSize = true, Height = 28,
            BackColor = bg ?? Navy, ForeColor = fg ?? Color.White,
            Font = FBold, FlatStyle = FlatStyle.Flat,
            Padding = new Padding(8, 0, 8, 0), Cursor = Cursors.Hand,
            UseVisualStyleBackColor = false,
        };
        b.FlatAppearance.BorderSize = 0;
        b.FlatAppearance.MouseOverBackColor = Lighten(bg ?? Navy, 20);
        return b;
    }

    public static ComboBox Cmb(string[]? items = null, bool readOnly = true, int w = 120) =>
        new()
        {
            Width = w, BackColor = Card, ForeColor = Txt, Font = FMain,
            DropDownStyle = readOnly ? ComboBoxStyle.DropDownList : ComboBoxStyle.DropDown,
            FlatStyle = FlatStyle.Flat,
            Items = { items is null ? (object)"" : "" },
        };

    public static NumericUpDown Num(decimal min, decimal max, decimal val, int w = 64) =>
        new()
        {
            Minimum = min, Maximum = max, Value = Math.Clamp(val, min, max),
            Width = w, BackColor = Card, ForeColor = Txt,
            BorderStyle = BorderStyle.FixedSingle,
            TextAlign = HorizontalAlignment.Center,
        };

    public static TextBox Txt_(string value = "", int w = 200) =>
        new()
        {
            Text = value, Width = w,
            BackColor = Card, ForeColor = Txt,
            BorderStyle = BorderStyle.FixedSingle,
        };

    public static Label Lbl(string text, Font? font = null, Color? fg = null) =>
        new()
        {
            Text = text, AutoSize = true, BackColor = Color.Transparent,
            ForeColor = fg ?? Dim, Font = font ?? FMain,
        };

    public static Color Lighten(Color c, int by) =>
        Color.FromArgb(
            Math.Min(255, c.R + by),
            Math.Min(255, c.G + by),
            Math.Min(255, c.B + by));
}
