using SlotMonitor.Models;
using SlotMonitor.UI;

namespace SlotMonitor.Forms;

/// <summary>
/// Editor trực quan cho slot box của một camera.
///
/// Tính năng:
///   - Hiển thị frame camera làm nền.
///   - Kéo-thả để vẽ box mới (click + drag trên vùng trống).
///   - Click chọn box → di chuyển hoặc xóa (Delete).
///   - Double-click box → đổi tên.
///   - Danh sách slot bên phải, click để select, nút Xóa.
///   - Lưu trả về list SlotBox đã cập nhật.
/// </summary>
public sealed class SlotBoxEditor : Form
{
    // ── Input / Output ─────────────────────────────────────────────────────
    private readonly Bitmap         _bgFrame;
    private readonly List<SlotBox>  _slots;
    public  IReadOnlyList<SlotBox>  Result => _slots;

    // ── Canvas state ───────────────────────────────────────────────────────
    private readonly Panel   _canvas;
    private Bitmap?          _composited;   // bgFrame + drawn boxes (cached)
    private bool             _dirty = true; // force recomposite on next paint

    // Draw mode
    private enum Mode { Idle, Drawing, Moving }
    private Mode    _mode;
    private Point   _dragStart;
    private Point   _dragCurrent;
    private int     _selectedIdx = -1;       // index vào _slots
    private Point   _moveOrigin;             // vị trí slot khi bắt đầu move (pixel)
    private float   _moveSlotNX, _moveSlotNY; // NX/NY ban đầu khi bắt đầu move

    // ── Sidebar controls ───────────────────────────────────────────────────
    private readonly ListBox _lstSlots;
    private readonly Label   _lblHint;
    private int              _autoIndex = 1;

    public SlotBoxEditor(IEnumerable<SlotBox> existing, Bitmap? frame = null)
    {
        _slots   = existing.Select(s => s.Clone()).ToList();
        _bgFrame = frame is not null ? (Bitmap)frame.Clone() : MakeBlank();
        _autoIndex = _slots.Count + 1;

        Text          = "KZTEK — Cấu hình Slot Box";
        Size          = new Size(1060, 640);
        MinimumSize   = new Size(800, 500);
        BackColor     = Theme.BG;
        ForeColor     = Theme.Txt;
        Font          = Theme.FMain;
        StartPosition = FormStartPosition.CenterParent;

        // ── Canvas (left, fill) ───────────────────────────────────────────
        _canvas = new Panel { Dock = DockStyle.Fill, BackColor = Color.Black };
        _canvas.Paint      += OnCanvasPaint;
        _canvas.MouseDown  += OnMouseDown;
        _canvas.MouseMove  += OnMouseMove;
        _canvas.MouseUp    += OnMouseUp;
        _canvas.DoubleClick += OnDoubleClick;
        _canvas.Resize     += (_, _) => { _dirty = true; _canvas.Invalidate(); };

        // ── Right sidebar ─────────────────────────────────────────────────
        var sidebar = new Panel
        {
            Dock = DockStyle.Right, Width = 210,
            BackColor = Theme.Card, Padding = new Padding(8),
        };

        var lblTitle = Theme.Lbl("Danh sách slot", Theme.FBold, Theme.Txt);
        lblTitle.SetBounds(0, 4, 194, 20);

        _lstSlots = new ListBox
        {
            Left = 0, Top = 28, Width = 194, Height = 300,
            BackColor = Theme.Deep, ForeColor = Theme.Txt,
            BorderStyle = BorderStyle.FixedSingle, SelectionMode = SelectionMode.One,
            HorizontalScrollbar = false,
        };
        _lstSlots.SelectedIndexChanged += OnListSelect;

        var btnAdd = Theme.Btn("+ Thêm slot", Theme.Accent);
        btnAdd.SetBounds(0, 334, 194, 28);
        btnAdd.Click += OnAddSlot;

        var btnDel = Theme.Btn("✕ Xóa slot", Theme.Err);
        btnDel.SetBounds(0, 366, 194, 28);
        btnDel.Click += OnDeleteSlot;

        var btnRename = Theme.Btn("✎ Đổi tên", Theme.Navy);
        btnRename.SetBounds(0, 398, 194, 28);
        btnRename.Click += OnRenameSlot;

        var btnClear = Theme.Btn("✕ Xóa tất cả", Theme.Card);
        btnClear.ForeColor = Theme.Dim;
        btnClear.SetBounds(0, 434, 194, 28);
        btnClear.Click += (_, _) =>
        {
            if (MessageBox.Show("Xóa tất cả slot?", "Xác nhận", MessageBoxButtons.YesNo) != DialogResult.Yes) return;
            _slots.Clear(); _selectedIdx = -1; RefreshList(); Invalidate();
        };

        _lblHint = new Label
        {
            Left = 0, Top = 472, Width = 194, Height = 100,
            Text = "Kéo thả trên canvas để vẽ slot mới.\nClick chọn, Delete để xóa.\nDouble-click để đổi tên.",
            ForeColor = Theme.Dim, BackColor = Color.Transparent,
            Font = Theme.FSm,
        };

        sidebar.Controls.AddRange([
            lblTitle, _lstSlots, btnAdd, btnDel, btnRename, btnClear, _lblHint,
        ]);

        // ── Bottom bar ─────────────────────────────────────────────────────
        var bottom = new Panel
        {
            Dock = DockStyle.Bottom, Height = 46, BackColor = Theme.NavyDk,
        };
        var btnSave = Theme.Btn("💾 Lưu", Theme.Accent);
        btnSave.SetBounds(bottom.Width - 200, 8, 90, 28);
        btnSave.Anchor = AnchorStyles.Right | AnchorStyles.Top;
        btnSave.Click  += (_, _) => { DialogResult = DialogResult.OK; Close(); };

        var btnCancel = Theme.Btn("Hủy", Theme.Card);
        btnCancel.ForeColor = Theme.Dim;
        btnCancel.SetBounds(bottom.Width - 104, 8, 90, 28);
        btnCancel.Anchor = AnchorStyles.Right | AnchorStyles.Top;
        btnCancel.Click  += (_, _) => { DialogResult = DialogResult.Cancel; Close(); };

        var lblInfo = new Label
        {
            Left = 8, Top = 12, AutoSize = true,
            Text = "Kéo thả để vẽ box. Click box để chọn/di chuyển. Delete để xóa.",
            ForeColor = Theme.Dim, BackColor = Color.Transparent, Font = Theme.FSm,
        };
        bottom.Controls.AddRange([lblInfo, btnSave, btnCancel]);

        Controls.AddRange([_canvas, sidebar, bottom]);

        RefreshList();
        KeyDown += OnKeyDown;
        KeyPreview = true;
    }

    // ══════════════════════════════════════════════════════════════════════
    // CANVAS PAINT
    // ══════════════════════════════════════════════════════════════════════

    private void OnCanvasPaint(object? s, PaintEventArgs e)
    {
        if (_dirty) BuildComposited();

        var g = e.Graphics;
        g.InterpolationMode = System.Drawing.Drawing2D.InterpolationMode.Bilinear;

        // Draw composited (bg + static boxes)
        if (_composited is not null)
            g.DrawImage(_composited, GetDisplayRect());

        // Draw in-progress drag rect
        if (_mode == Mode.Drawing)
        {
            var dragRaw = NormalizeRect(_dragStart, _dragCurrent);
            var pxRect  = CanvasToDisplay(dragRaw);
            using var pen = new Pen(Color.Yellow, 2) { DashStyle = System.Drawing.Drawing2D.DashStyle.Dash };
            g.DrawRectangle(pen, pxRect);
        }
    }

    private void BuildComposited()
    {
        _composited?.Dispose();
        _composited = new Bitmap(_canvas.Width, _canvas.Height);
        using var g = Graphics.FromImage(_composited);
        g.Clear(Color.Black);
        g.InterpolationMode = System.Drawing.Drawing2D.InterpolationMode.Bilinear;

        // Background frame
        var dr = GetDisplayRect();
        g.DrawImage(_bgFrame, dr);

        // Slot boxes
        for (int i = 0; i < _slots.Count; i++)
        {
            var slot  = _slots[i];
            var pxR   = SlotToDisplayRect(slot);
            bool sel  = i == _selectedIdx;

            // Semi-transparent fill
            using var br = new SolidBrush(Color.FromArgb(50, sel ? Color.Cyan : Color.LimeGreen));
            g.FillRectangle(br, pxR);

            // Border
            using var pen = new Pen(sel ? Color.Cyan : Color.LimeGreen, sel ? 2.5f : 1.5f);
            g.DrawRectangle(pen, pxR);

            // Label
            string label = $"[{i + 1}] {slot.Name}";
            using var fs = new Font("Segoe UI", 8f, FontStyle.Bold);
            var sz = g.MeasureString(label, fs);
            float tx = pxR.Left + 2, ty = pxR.Top + 2;
            using var bgBr = new SolidBrush(Color.FromArgb(140, Color.Black));
            g.FillRectangle(bgBr, tx - 1, ty - 1, sz.Width + 2, sz.Height + 2);
            g.DrawString(label, fs, Brushes.White, tx, ty);
        }

        _dirty = false;
    }

    // ══════════════════════════════════════════════════════════════════════
    // MOUSE EVENTS
    // ══════════════════════════════════════════════════════════════════════

    private void OnMouseDown(object? s, MouseEventArgs e)
    {
        if (e.Button == MouseButtons.Left)
        {
            int hit = HitTest(e.Location);
            if (hit >= 0)
            {
                // Select + start move
                _selectedIdx = hit;
                _mode        = Mode.Moving;
                _dragStart   = e.Location;
                _moveOrigin  = e.Location;
                _moveSlotNX  = _slots[hit].NX;
                _moveSlotNY  = _slots[hit].NY;
                _lstSlots.SelectedIndex = hit;
            }
            else
            {
                // Start drawing new box
                _selectedIdx = -1;
                _mode        = Mode.Drawing;
                _dragStart   = e.Location;
                _dragCurrent = e.Location;
            }
            _dirty = true; _canvas.Invalidate();
        }
        else if (e.Button == MouseButtons.Right)
        {
            int hit = HitTest(e.Location);
            if (hit >= 0) { _selectedIdx = hit; DeleteSelected(); }
        }
    }

    private void OnMouseMove(object? s, MouseEventArgs e)
    {
        if (_mode == Mode.Drawing)
        {
            _dragCurrent = e.Location;
            _canvas.Invalidate();
        }
        else if (_mode == Mode.Moving && _selectedIdx >= 0)
        {
            var dr = GetDisplayRect();
            if (dr.Width <= 0 || dr.Height <= 0) return;

            float dx = (e.X - _moveOrigin.X) / (float)dr.Width;
            float dy = (e.Y - _moveOrigin.Y) / (float)dr.Height;

            var slot = _slots[_selectedIdx];
            slot.NX = Math.Clamp(_moveSlotNX + dx, 0f, 1f - slot.NW);
            slot.NY = Math.Clamp(_moveSlotNY + dy, 0f, 1f - slot.NH);

            _dirty = true; _canvas.Invalidate();
        }
    }

    private void OnMouseUp(object? s, MouseEventArgs e)
    {
        if (_mode == Mode.Drawing)
        {
            var raw = CanvasToNormalized(NormalizeRect(_dragStart, e.Location));
            if (raw.Width > 0.01f && raw.Height > 0.01f)
            {
                var slot = new SlotBox
                {
                    Name = $"Slot {_autoIndex++}",
                    NX = raw.X, NY = raw.Y, NW = raw.Width, NH = raw.Height,
                };
                _slots.Add(slot);
                _selectedIdx = _slots.Count - 1;
                RefreshList();
            }
        }
        _mode  = Mode.Idle;
        _dirty = true;
        _canvas.Invalidate();
    }

    private void OnDoubleClick(object? s, EventArgs e)
    {
        if (_selectedIdx < 0) return;
        RenameSlotAt(_selectedIdx);
    }

    // ══════════════════════════════════════════════════════════════════════
    // SIDEBAR ACTIONS
    // ══════════════════════════════════════════════════════════════════════

    private void OnListSelect(object? s, EventArgs e)
    {
        _selectedIdx = _lstSlots.SelectedIndex;
        _dirty = true; _canvas.Invalidate();
    }

    private void OnAddSlot(object? s, EventArgs e)
    {
        var slot = new SlotBox
        {
            Name = $"Slot {_autoIndex++}",
            NX = 0.1f, NY = 0.1f, NW = 0.15f, NH = 0.15f,
        };
        _slots.Add(slot);
        _selectedIdx = _slots.Count - 1;
        RefreshList(); _dirty = true; _canvas.Invalidate();
    }

    private void OnDeleteSlot(object? s, EventArgs e) => DeleteSelected();
    private void OnRenameSlot(object? s, EventArgs e)
    {
        if (_selectedIdx < 0) { MessageBox.Show("Chọn slot trước."); return; }
        RenameSlotAt(_selectedIdx);
    }

    private void DeleteSelected()
    {
        if (_selectedIdx < 0 || _selectedIdx >= _slots.Count) return;
        _slots.RemoveAt(_selectedIdx);
        _selectedIdx = Math.Min(_selectedIdx, _slots.Count - 1);
        RefreshList(); _dirty = true; _canvas.Invalidate();
    }

    private void RenameSlotAt(int idx)
    {
        var dlg = new RenameDialog(_slots[idx].Name);
        if (dlg.ShowDialog(this) == DialogResult.OK && !string.IsNullOrEmpty(dlg.Result))
        {
            _slots[idx].Name = dlg.Result;
            RefreshList(); _dirty = true; _canvas.Invalidate();
        }
    }

    private void OnKeyDown(object? s, KeyEventArgs e)
    {
        if (e.KeyCode == Keys.Delete) { DeleteSelected(); e.Handled = true; }
        if (e.KeyCode == Keys.Escape && _mode != Mode.Idle)
        { _mode = Mode.Idle; _dirty = true; _canvas.Invalidate(); e.Handled = true; }
    }

    // ══════════════════════════════════════════════════════════════════════
    // COORDINATE HELPERS
    // ══════════════════════════════════════════════════════════════════════

    /// <summary>Hình chữ nhật vùng hiển thị ảnh trên canvas (fit letterbox).</summary>
    private Rectangle GetDisplayRect()
    {
        int cw = _canvas.Width, ch = _canvas.Height;
        float scale = Math.Min((float)cw / _bgFrame.Width, (float)ch / _bgFrame.Height);
        int w = (int)(_bgFrame.Width  * scale);
        int h = (int)(_bgFrame.Height * scale);
        return new Rectangle((cw - w) / 2, (ch - h) / 2, w, h);
    }

    private RectangleF SlotToDisplayRect(SlotBox slot)
    {
        var dr = GetDisplayRect();
        return new RectangleF(
            dr.Left + slot.NX * dr.Width,
            dr.Top  + slot.NY * dr.Height,
            slot.NW * dr.Width,
            slot.NH * dr.Height);
    }

    private RectangleF CanvasToDisplay(Rectangle raw) => raw;

    /// <summary>Chuyển hình chữ nhật pixel canvas → normalized tọa độ ảnh.</summary>
    private RectangleF CanvasToNormalized(Rectangle pxRect)
    {
        var dr = GetDisplayRect();
        if (dr.Width <= 0 || dr.Height <= 0) return RectangleF.Empty;
        float nx = (pxRect.Left   - dr.Left) / (float)dr.Width;
        float ny = (pxRect.Top    - dr.Top)  / (float)dr.Height;
        float nw = pxRect.Width   / (float)dr.Width;
        float nh = pxRect.Height  / (float)dr.Height;
        return new RectangleF(
            Math.Clamp(nx, 0f, 1f), Math.Clamp(ny, 0f, 1f),
            Math.Clamp(nw, 0f, 1f - nx), Math.Clamp(nh, 0f, 1f - ny));
    }

    private static Rectangle NormalizeRect(Point a, Point b) =>
        new(Math.Min(a.X, b.X), Math.Min(a.Y, b.Y),
            Math.Abs(a.X - b.X), Math.Abs(a.Y - b.Y));

    /// <summary>Tìm slot box tại vị trí con trỏ, trả về index hoặc -1.</summary>
    private int HitTest(Point pt)
    {
        for (int i = _slots.Count - 1; i >= 0; i--)  // reverse: top-drawn hits first
        {
            var r = SlotToDisplayRect(_slots[i]);
            if (r.Contains(pt)) return i;
        }
        return -1;
    }

    private void RefreshList()
    {
        _lstSlots.BeginUpdate();
        _lstSlots.Items.Clear();
        foreach (var s in _slots) _lstSlots.Items.Add(s.Name);
        if (_selectedIdx >= 0 && _selectedIdx < _lstSlots.Items.Count)
            _lstSlots.SelectedIndex = _selectedIdx;
        _lstSlots.EndUpdate();
    }

    private static Bitmap MakeBlank()
    {
        var bmp = new Bitmap(640, 480);
        using var g = Graphics.FromImage(bmp);
        g.Clear(Color.FromArgb(22, 22, 42));
        using var f = new Font("Segoe UI", 14f);
        g.DrawString("Chưa có frame\n(Khởi động camera rồi mở lại editor)", f,
            Brushes.DimGray, new RectangleF(0, 180, 640, 100),
            new StringFormat { Alignment = StringAlignment.Center });
        return bmp;
    }

    protected override void Dispose(bool disposing)
    {
        if (disposing) { _bgFrame.Dispose(); _composited?.Dispose(); }
        base.Dispose(disposing);
    }
}

// ── Inline rename dialog ───────────────────────────────────────────────────

internal sealed class RenameDialog : Form
{
    private readonly TextBox _txt;
    public string Result => _txt.Text.Trim();

    public RenameDialog(string current)
    {
        Text            = "Đổi tên slot";
        Size            = new Size(340, 120);
        FormBorderStyle = FormBorderStyle.FixedDialog;
        StartPosition   = FormStartPosition.CenterParent;
        MaximizeBox     = MinimizeBox = false;
        BackColor       = Theme.BG; ForeColor = Theme.Txt; Font = Theme.FMain;

        _txt = new TextBox
        {
            Text = current, Left = 10, Top = 10, Width = 300,
            BackColor = Theme.Deep, ForeColor = Theme.Txt, BorderStyle = BorderStyle.FixedSingle,
        };
        _txt.SelectAll();

        var btnOk     = Theme.Btn("OK",  Theme.Accent); btnOk.SetBounds(10,   40, 80, 26);
        var btnCancel = Theme.Btn("Hủy", Theme.Card);   btnCancel.SetBounds(96, 40, 80, 26);
        btnOk.Click     += (_, _) => { DialogResult = DialogResult.OK;     Close(); };
        btnCancel.Click += (_, _) => { DialogResult = DialogResult.Cancel; Close(); };

        Controls.AddRange([_txt, btnOk, btnCancel]);
        AcceptButton = btnOk; CancelButton = btnCancel;
    }
}
