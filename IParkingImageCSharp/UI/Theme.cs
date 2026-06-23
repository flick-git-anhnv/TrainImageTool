namespace IParkingImage.UI;

public static class Theme
{
    // ── KZTEK Brand Colors ──────────────────────────────────────────────
    public static readonly Color BG      = Color.FromArgb(30,  30,  46);
    public static readonly Color Card    = Color.FromArgb(42,  42,  62);
    public static readonly Color Deep    = Color.FromArgb(22,  22,  42);
    public static readonly Color Accent  = Color.FromArgb(240, 89,  34);   // Cam #F05922
    public static readonly Color Navy    = Color.FromArgb(74,  63,  140);  // #4A3F8C
    public static readonly Color NavyDk  = Color.FromArgb(37,  28,  83);   // #251C53
    public static readonly Color Txt     = Color.FromArgb(224, 224, 240);
    public static readonly Color Dim     = Color.FromArgb(144, 144, 176);
    public static readonly Color Ok      = Color.FromArgb(76,  175, 80);
    public static readonly Color Warn    = Color.FromArgb(255, 183, 77);
    public static readonly Color Err     = Color.FromArgb(255, 136, 68);

    // ── Fonts ───────────────────────────────────────────────────────────
    public static readonly Font FMain = new("Segoe UI", 9f);
    public static readonly Font FBold = new("Segoe UI", 9f, FontStyle.Bold);
    public static readonly Font FMono = new("Consolas", 8.5f);
    public static readonly Font FSm   = new("Segoe UI", 8f);
    public static readonly Font FSmB  = new("Segoe UI", 8f, FontStyle.Bold);

    // ── Control factories ────────────────────────────────────────────────

    public static Label Lbl(string text, Font? font = null, Color? fg = null) =>
        new Label {
            Text = text, AutoSize = true, BackColor = Color.Transparent,
            ForeColor = fg ?? Txt, Font = font ?? FMain,
        };

    public static Button Btn(string text, Color? bg = null, Color? fg = null) {
        var b = new Button {
            Text = text, AutoSize = true,
            BackColor = bg ?? Navy, ForeColor = fg ?? Color.White,
            Font = FBold, FlatStyle = FlatStyle.Flat, Height = 30,
            Padding = new Padding(10, 0, 10, 0), Cursor = Cursors.Hand,
            UseVisualStyleBackColor = false,
        };
        b.FlatAppearance.BorderSize = 0;
        b.FlatAppearance.MouseOverBackColor = Lighten(bg ?? Navy, 20);
        return b;
    }

    public static NumericUpDown Num(decimal min, decimal max, decimal val, int w = 72) =>
        new NumericUpDown {
            Minimum = min, Maximum = max, Value = Math.Clamp(val, min, max),
            Width = w, BackColor = Card, ForeColor = Txt,
            BorderStyle = BorderStyle.FixedSingle,
            Font = FMain, TextAlign = HorizontalAlignment.Center,
        };

    public static TextBox Txt2(string? text = null, int w = 200, bool password = false) =>
        new TextBox {
            Text = text ?? "", Width = w, BackColor = Card, ForeColor = Txt,
            BorderStyle = BorderStyle.FixedSingle, Font = FMain,
            PasswordChar = password ? '•' : '\0',
        };

    public static ComboBox Cmb(string[] items, string? sel = null, bool readOnly = false) {
        var c = new ComboBox {
            BackColor = Card, ForeColor = Txt, Font = FMain,
            DropDownStyle = readOnly ? ComboBoxStyle.DropDownList : ComboBoxStyle.DropDown,
            FlatStyle = FlatStyle.Flat,
        };
        c.Items.AddRange(items);
        if (sel != null) c.Text = sel;
        else if (items.Length > 0) c.SelectedIndex = 0;
        return c;
    }

    public static CheckBox Chk(string text, bool @checked = false) =>
        new CheckBox {
            Text = text, Checked = @checked, AutoSize = true,
            ForeColor = Txt, BackColor = Color.Transparent,
            FlatStyle = FlatStyle.Flat, Cursor = Cursors.Hand,
        };

    public static RadioButton Rad(string text, bool @checked = false) =>
        new RadioButton {
            Text = text, Checked = @checked, AutoSize = true,
            ForeColor = Txt, BackColor = Color.Transparent,
            FlatStyle = FlatStyle.Flat, Cursor = Cursors.Hand,
        };

    // ── Section header ───────────────────────────────────────────────────

    public static Panel SectionHeader(string title) {
        var p = new Panel { Height = 24, BackColor = Navy, Dock = DockStyle.Top };
        var lbl = new Label {
            Text = "  " + title, Dock = DockStyle.Fill, ForeColor = Color.White,
            Font = FSmB, TextAlign = ContentAlignment.MiddleLeft,
            BackColor = Color.Transparent,
        };
        p.Controls.Add(lbl);
        return p;
    }

    // ── Group box replacement ────────────────────────────────────────────

    /// <summary>Creates a titled section panel. Returns the inner content Panel.</summary>
    public static Panel Section(Control parent, string title, out Panel content, Padding? padding = null)
    {
        var outer = new Panel { BackColor = BG, Margin = new Padding(0, 0, 0, 4) };

        var header = SectionHeader(title);

        content = new Panel {
            BackColor = BG,
            Padding = padding ?? new Padding(8, 6, 8, 6),
            AutoSize = true,
            AutoSizeMode = AutoSizeMode.GrowAndShrink,
            Dock = DockStyle.Top,
        };

        // Order matters: Add content first (so it docks to top), then header
        // But header must appear above content visually → use Controls.SetChildIndex
        outer.Controls.Add(content);
        outer.Controls.Add(header);
        outer.Controls.SetChildIndex(header, 0);  // header on top
        outer.Controls.SetChildIndex(content, 1); // content below

        return outer;
    }

    /// <summary>Flow row (Left-to-Right) for grouping inline controls.</summary>
    public static FlowLayoutPanel Row(int height = 28) =>
        new FlowLayoutPanel {
            FlowDirection = FlowDirection.LeftToRight, WrapContents = true,
            AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink,
            BackColor = Color.Transparent, Margin = new Padding(0, 2, 0, 2),
        };

    private static Color Lighten(Color c, int by) =>
        Color.FromArgb(Math.Min(255, c.R + by), Math.Min(255, c.G + by), Math.Min(255, c.B + by));
}
