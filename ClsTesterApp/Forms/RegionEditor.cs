using ClsTester.Models;
using ClsTester.UI;

namespace ClsTester.Forms;

/// <summary>
/// Form vẽ / chỉnh sửa BboxRegion trên nền frame video.
///
/// Chế độ Draw (Kéo):
///   • Kéo vùng trống → vẽ region mới
///   • Kéo handle (8 điểm) của region đang chọn → resize
///   • Kéo bên trong region đang chọn → di chuyển
///   • Click region khác → chọn  |  Chuột phải → xóa
///
/// Chế độ FourPoint (4 Điểm):
///   • Click 4 góc → tạo region từ bounding-rect của 4 điểm
///   • Esc → hủy đang vẽ
/// </summary>
public sealed class RegionEditor : Form
{
    // ── Result ────────────────────────────────────────────────────────────
    public List<BboxRegion> Result { get; private set; } = [];

    // ── Mode / state ──────────────────────────────────────────────────────
    private enum EditMode { Draw, FourPoint }
    private enum DragOp   { None, Drawing, Moving, Resizing }

    private EditMode _editMode  = EditMode.Draw;
    private DragOp   _dragOp    = DragOp.None;

    // draw
    private Point    _dragStart;
    private Rectangle? _drawRect;

    // move
    private PointF   _moveAnchor;   // normalized offset from region.X1n to click point

    // resize
    private int      _handleIdx;    // 0-7 which handle
    private Point    _resizeStart;  // screen point where resize started
    private float    _resX1, _resY1, _resX2, _resY2; // snapshot before resize

    // 4-point mode
    private readonly List<PointF> _fourPts = [];  // normalized coords
    private Point    _mousePos;                    // current mouse for rubber band

    // ── Regions / selection ───────────────────────────────────────────────
    private readonly List<BboxRegion> _regions;
    private readonly Bitmap?          _bgFrame;
    private BboxRegion?               _selected;

    // ── Controls ──────────────────────────────────────────────────────────
    private PictureBox _pb       = null!;
    private ListView   _lv       = null!;
    private Button     _btnRename = null!;
    private Button     _btnDelete = null!;
    private Label      _lblHint   = null!;
    private RadioButton _rbDraw   = null!;
    private RadioButton _rbFour   = null!;

    // ── Palette ───────────────────────────────────────────────────────────
    private static readonly Color[] _palette =
        Enumerable.Range(0, 10).Select(Theme.ClassColor).ToArray();

    // Cursors for resize handles (index 0-7 maps to handle positions)
    private static readonly Cursor[] _handleCursors =
    [
        Cursors.SizeNWSE, Cursors.SizeNS, Cursors.SizeNESW,
        Cursors.SizeWE,
        Cursors.SizeNWSE, Cursors.SizeNS, Cursors.SizeNESW,
        Cursors.SizeWE,
    ];

    // ══════════════════════════════════════════════════════════════════════

    public RegionEditor(IEnumerable<BboxRegion> current, Bitmap? bgFrame)
    {
        _regions = current.Select(DeepCopy).ToList();
        _bgFrame = bgFrame;

        Text           = "KZTEK — Chỉnh sửa Regions";
        BackColor      = Theme.BG;
        ForeColor      = Theme.Txt;
        Font           = Theme.FMain;
        Size           = new Size(1100, 680);
        MinimumSize    = new Size(800, 500);
        StartPosition  = FormStartPosition.CenterParent;
        DoubleBuffered = true;

        BuildUI();
        RefreshList();
    }

    // ── Build UI ──────────────────────────────────────────────────────────

    private void BuildUI()
    {
        // ── Header bar ────────────────────────────────────────────────────
        var hdrPb = new Panel { Dock = DockStyle.Top, Height = 34, BackColor = Theme.NavyDk };

        _rbDraw = MkRadio("✎ Kéo vẽ / Di chuyển", true);
        _rbFour = MkRadio("⊹ Click 4 điểm", false);
        _rbDraw.SetBounds(8, 6, 170, 22);
        _rbFour.SetBounds(186, 6, 130, 22);
        _rbDraw.CheckedChanged += (_, _) => SetMode(EditMode.Draw);
        _rbFour.CheckedChanged += (_, _) => SetMode(EditMode.FourPoint);

        _lblHint = new Label
        {
            AutoSize = true, ForeColor = Theme.Dim, BackColor = Color.Transparent,
            Font = Theme.FSm, Top = 9,
        };
        hdrPb.Controls.AddRange([_rbDraw, _rbFour, _lblHint]);
        UpdateHint();

        // ── PictureBox ────────────────────────────────────────────────────
        var pbPanel = new Panel { Dock = DockStyle.Fill, BackColor = Theme.BG };

        _pb = new PictureBox
        {
            Dock = DockStyle.Fill, SizeMode = PictureBoxSizeMode.Zoom,
            BackColor = Color.FromArgb(20, 20, 35), Cursor = Cursors.Cross,
        };
        _pb.Paint      += OnPbPaint;
        _pb.MouseDown  += OnPbMouseDown;
        _pb.MouseMove  += OnPbMouseMove;
        _pb.MouseUp    += OnPbMouseUp;
        _pb.MouseLeave += (_, _) => { _mousePos = Point.Empty; _pb.Invalidate(); };

        if (_bgFrame is not null) _pb.Image = _bgFrame;

        pbPanel.Controls.Add(_pb);
        pbPanel.Controls.Add(hdrPb);

        // ── Right panel ───────────────────────────────────────────────────
        var rightPanel = new Panel
        {
            Dock = DockStyle.Right, Width = 280,
            BackColor = Theme.Card, Padding = new Padding(8),
        };

        var hdrR = new Label
        {
            Dock = DockStyle.Top, Height = 30,
            Text = "Danh sách regions", Font = Theme.FBold, ForeColor = Theme.Txt,
            BackColor = Color.Transparent, TextAlign = ContentAlignment.MiddleLeft,
        };

        _lv = Theme.MkListView();
        _lv.Dock = DockStyle.Fill;
        _lv.Columns.AddRange([
            new ColumnHeader { Text = "#",      Width = 26  },
            new ColumnHeader { Text = "Tên",    Width = 120 },
            new ColumnHeader { Text = "Tọa độ", Width = 110 },
        ]);
        _lv.SelectedIndexChanged += (_, _) => OnLvSelect();
        _lv.DoubleClick          += (_, _) => RenameSelected();

        // Action buttons
        var btnFlow = new FlowLayoutPanel
        {
            Dock = DockStyle.Bottom, Height = 36,
            FlowDirection = FlowDirection.RightToLeft,
            BackColor = Color.Transparent, WrapContents = false, Padding = new Padding(2),
        };
        _btnRename = Theme.Btn("✎ Đổi tên", Theme.Navy);            _btnRename.Width = 86;
        _btnDelete = Theme.Btn("✕ Xóa",     Theme.Card, Theme.Err); _btnDelete.Width = 72;
        _btnRename.Click += (_, _) => RenameSelected();
        _btnDelete.Click += (_, _) => DeleteSelected();
        btnFlow.Controls.AddRange([_btnDelete, _btnRename]);

        // OK / Cancel
        var dialogFlow = new FlowLayoutPanel
        {
            Dock = DockStyle.Bottom, Height = 40,
            FlowDirection = FlowDirection.RightToLeft,
            BackColor = Color.Transparent, WrapContents = false, Padding = new Padding(4),
        };
        var btnCancel = Theme.Btn("Hủy",  Theme.Card);   btnCancel.Width = 70;
        var btnOk     = Theme.Btn("✔ OK", Theme.Accent); btnOk.Width     = 70;
        btnCancel.Click += (_, _) => { DialogResult = DialogResult.Cancel; Close(); };
        btnOk.Click     += (_, _) => Commit();
        dialogFlow.Controls.AddRange([btnCancel, btnOk]);

        var hint2 = new Label
        {
            Dock = DockStyle.Bottom, Height = 18,
            Text = "Del / Chuột phải → xóa  |  F2 → đổi tên",
            Font = Theme.FSm, ForeColor = Theme.Dim, BackColor = Color.Transparent,
            TextAlign = ContentAlignment.MiddleLeft,
        };
        rightPanel.Controls.AddRange([dialogFlow, hint2, btnFlow, _lv, hdrR]);

        // ── Splitter ─────────────────────────────────────────────────────
        var split = new SplitContainer
        {
            Dock = DockStyle.Fill, Orientation = Orientation.Vertical,
            SplitterWidth = 4, BackColor = Theme.Border,
        };
        split.Panel1.Controls.Add(pbPanel);
        split.Panel2.Controls.Add(rightPanel);
        split.SplitterDistance = (int)(ClientSize.Width * 0.72);
        Controls.Add(split);

        // Keyboard
        KeyPreview = true;
        KeyDown   += (_, e) =>
        {
            if (e.KeyCode == Keys.Escape)
            {
                if (_fourPts.Count > 0) { _fourPts.Clear(); _pb.Invalidate(); return; }
                DialogResult = DialogResult.Cancel; Close();
            }
            if (e.KeyCode == Keys.Delete) DeleteSelected();
            if (e.KeyCode == Keys.F2)     RenameSelected();
            if (e.KeyCode == Keys.Enter)  Commit();
        };
    }

    private static RadioButton MkRadio(string text, bool check) => new()
    {
        Text = text, Checked = check, AutoSize = true,
        ForeColor = Theme.Txt, BackColor = Color.Transparent, Font = Theme.FMain,
    };

    private void SetMode(EditMode m)
    {
        _editMode = m;
        _fourPts.Clear();
        _drawRect = null;
        _dragOp = DragOp.None;
        _pb.Cursor = m == EditMode.FourPoint ? Cursors.Cross : Cursors.Default;
        UpdateHint();
        _pb.Invalidate();
    }

    private void UpdateHint()
    {
        if (_editMode == EditMode.Draw)
            _lblHint.Text = "Kéo vùng trống → vẽ  |  Kéo trong region → di chuyển  |  Kéo handle → resize";
        else
            _lblHint.Text = $"Click góc ({_fourPts.Count}/4)  |  Esc → hủy";
        _lblHint.Left = _rbFour.Right + 12;
    }

    // ── ListView ──────────────────────────────────────────────────────────

    private void RefreshList()
    {
        _lv.BeginUpdate();
        _lv.Items.Clear();
        for (int i = 0; i < _regions.Count; i++)
        {
            var r    = _regions[i];
            var item = new ListViewItem((i + 1).ToString());
            item.SubItems.Add(r.Name);
            item.SubItems.Add(r.CoordsText);
            item.ForeColor = _palette[i % _palette.Length];
            item.Tag       = r;
            _lv.Items.Add(item);
        }
        _lv.EndUpdate();
        _pb.Invalidate();
    }

    private void OnLvSelect()
    {
        _selected = _lv.SelectedItems.Count > 0
            ? (BboxRegion)_lv.SelectedItems[0].Tag! : null;
        _pb.Invalidate();
    }

    // ── Mouse handling ────────────────────────────────────────────────────

    private void OnPbMouseDown(object? s, MouseEventArgs e)
    {
        if (e.Button == MouseButtons.Right) { RightClickDelete(e.Location); return; }
        if (e.Button != MouseButtons.Left) return;

        // ── FourPoint mode ────────────────────────────────────────────────
        if (_editMode == EditMode.FourPoint)
        {
            var norm = PbToNorm(e.Location);
            if (norm == PointF.Empty) return;
            _fourPts.Add(norm);
            UpdateHint();

            if (_fourPts.Count == 4)
            {
                float x1 = _fourPts.Min(p => p.X), y1 = _fourPts.Min(p => p.Y);
                float x2 = _fourPts.Max(p => p.X), y2 = _fourPts.Max(p => p.Y);
                _fourPts.Clear();

                if (x2 - x1 > 0.01f && y2 - y1 > 0.01f)
                {
                    var region = new BboxRegion
                    {
                        X1n = x1, Y1n = y1, X2n = x2, Y2n = y2,
                        Name = $"Region {_regions.Count + 1}",
                    };
                    _regions.Add(region);
                    _selected = region;
                    RefreshList();
                    RenameSelected();
                }
                UpdateHint();
            }
            _pb.Invalidate();
            return;
        }

        // ── Draw mode: check handle → resize ─────────────────────────────
        if (_selected is not null)
        {
            int hi = HitHandle(e.Location, _selected);
            if (hi >= 0)
            {
                _dragOp     = DragOp.Resizing;
                _handleIdx  = hi;
                _resizeStart = e.Location;
                _resX1 = _selected.X1n; _resY1 = _selected.Y1n;
                _resX2 = _selected.X2n; _resY2 = _selected.Y2n;
                return;
            }

            // Inside selected region → move
            if (HitRegion(e.Location, _selected))
            {
                _dragOp = DragOp.Moving;
                var norm = PbToNorm(e.Location);
                _moveAnchor = new PointF(norm.X - _selected.X1n, norm.Y - _selected.Y1n);
                return;
            }
        }

        // Hit any other region → select it
        var hit = FindRegionAt(e.Location);
        if (hit is not null && hit != _selected)
        {
            _selected = hit;
            var idx = _regions.IndexOf(hit);
            if (idx >= 0) { _lv.Items[idx].Selected = true; _lv.EnsureVisible(idx); }
            _pb.Invalidate();
            return;
        }

        // Empty area → draw new region
        _dragOp    = DragOp.Drawing;
        _dragStart = e.Location;
        _drawRect  = null;
        _selected  = null;
        _lv.SelectedItems.Clear();
        _pb.Invalidate();
    }

    private void OnPbMouseMove(object? s, MouseEventArgs e)
    {
        _mousePos = e.Location;

        switch (_dragOp)
        {
            case DragOp.Drawing:
                if (e.Button == MouseButtons.Left)
                    _drawRect = NormRect(_dragStart, e.Location);
                break;

            case DragOp.Moving:
                if (e.Button == MouseButtons.Left && _selected is not null)
                    DoMove(e.Location);
                break;

            case DragOp.Resizing:
                if (e.Button == MouseButtons.Left && _selected is not null)
                    DoResize(e.Location);
                break;
        }

        // Update cursor when idle
        if (_dragOp == DragOp.None && _editMode == EditMode.Draw)
            UpdateCursor(e.Location);

        _pb.Invalidate();
    }

    private void OnPbMouseUp(object? s, MouseEventArgs e)
    {
        if (e.Button != MouseButtons.Left) return;

        switch (_dragOp)
        {
            case DragOp.Drawing:
                FinishDraw();
                break;

            case DragOp.Moving:
            case DragOp.Resizing:
                _dragOp = DragOp.None;
                RefreshList();  // update coords display
                break;
        }

        _dragOp = DragOp.None;
        _pb.Cursor = Cursors.Default;
        _pb.Invalidate();
    }

    private void FinishDraw()
    {
        _dragOp = DragOp.None;
        if (_drawRect is null || _drawRect.Value.Width < 6 || _drawRect.Value.Height < 6)
        { _drawRect = null; return; }

        var imgRect = ToImageRect(_drawRect.Value);
        _drawRect = null;
        if (imgRect.Width < 4 || imgRect.Height < 4) return;

        var (fw, fh) = FrameSize();
        if (fw <= 0 || fh <= 0) return;

        var region = BboxRegion.FromPixelRect(imgRect, fw, fh);
        region.Name = $"Region {_regions.Count + 1}";
        _regions.Add(region);
        _selected = region;
        RefreshList();
        RenameSelected();
    }

    // ── Move / Resize helpers ─────────────────────────────────────────────

    private void DoMove(Point current)
    {
        if (_selected is null) return;
        var pbRect = GetPbImageRect();
        if (pbRect.IsEmpty) return;

        float curX = (float)(current.X - pbRect.X) / pbRect.Width;
        float curY = (float)(current.Y - pbRect.Y) / pbRect.Height;

        float w = _selected.X2n - _selected.X1n;
        float h = _selected.Y2n - _selected.Y1n;
        float x1 = Math.Clamp(curX - _moveAnchor.X, 0f, 1f - w);
        float y1 = Math.Clamp(curY - _moveAnchor.Y, 0f, 1f - h);

        _selected.X1n = x1; _selected.Y1n = y1;
        _selected.X2n = x1 + w; _selected.Y2n = y1 + h;
    }

    private void DoResize(Point current)
    {
        if (_selected is null) return;
        var pbRect = GetPbImageRect();
        if (pbRect.IsEmpty) return;

        float dx = (float)(current.X - _resizeStart.X) / pbRect.Width;
        float dy = (float)(current.Y - _resizeStart.Y) / pbRect.Height;
        const float minSz = 0.01f;

        float x1 = _resX1, y1 = _resY1, x2 = _resX2, y2 = _resY2;
        switch (_handleIdx)
        {
            case 0: x1 = Math.Min(_resX1 + dx, x2 - minSz); y1 = Math.Min(_resY1 + dy, y2 - minSz); break;
            case 1: y1 = Math.Min(_resY1 + dy, y2 - minSz); break;
            case 2: x2 = Math.Max(_resX2 + dx, x1 + minSz); y1 = Math.Min(_resY1 + dy, y2 - minSz); break;
            case 3: x2 = Math.Max(_resX2 + dx, x1 + minSz); break;
            case 4: x2 = Math.Max(_resX2 + dx, x1 + minSz); y2 = Math.Max(_resY2 + dy, y1 + minSz); break;
            case 5: y2 = Math.Max(_resY2 + dy, y1 + minSz); break;
            case 6: x1 = Math.Min(_resX1 + dx, x2 - minSz); y2 = Math.Max(_resY2 + dy, y1 + minSz); break;
            case 7: x1 = Math.Min(_resX1 + dx, x2 - minSz); break;
        }
        _selected.X1n = Math.Clamp(x1, 0f, 1f);
        _selected.Y1n = Math.Clamp(y1, 0f, 1f);
        _selected.X2n = Math.Clamp(x2, 0f, 1f);
        _selected.Y2n = Math.Clamp(y2, 0f, 1f);
    }

    private void UpdateCursor(Point pbPt)
    {
        if (_selected is not null)
        {
            int hi = HitHandle(pbPt, _selected);
            if (hi >= 0) { _pb.Cursor = _handleCursors[hi]; return; }
            if (HitRegion(pbPt, _selected)) { _pb.Cursor = Cursors.SizeAll; return; }
        }
        if (FindRegionAt(pbPt) is not null) { _pb.Cursor = Cursors.Hand; return; }
        _pb.Cursor = Cursors.Cross;
    }

    // ── Paint ─────────────────────────────────────────────────────────────

    private void OnPbPaint(object? s, PaintEventArgs e)
    {
        var g = e.Graphics;
        g.SmoothingMode     = System.Drawing.Drawing2D.SmoothingMode.AntiAlias;
        g.TextRenderingHint = System.Drawing.Text.TextRenderingHint.ClearTypeGridFit;

        for (int i = 0; i < _regions.Count; i++)
            DrawRegion(g, _regions[i], i, _regions[i] == _selected);

        // Draw-drag preview
        if (_drawRect.HasValue)
        {
            using var pen = new Pen(Color.White, 1.5f) { DashStyle = System.Drawing.Drawing2D.DashStyle.Dash };
            g.DrawRectangle(pen, _drawRect.Value);
        }

        // FourPoint preview
        if (_editMode == EditMode.FourPoint && _fourPts.Count > 0)
            DrawFourPointPreview(g);
    }

    private void DrawFourPointPreview(Graphics g)
    {
        var pbRect = GetPbImageRect();
        if (pbRect.IsEmpty) return;

        // Draw collected points
        foreach (var p in _fourPts)
        {
            int px = pbRect.X + (int)(p.X * pbRect.Width);
            int py = pbRect.Y + (int)(p.Y * pbRect.Height);
            g.FillEllipse(Brushes.Orange, px - 5, py - 5, 10, 10);
            using var ep = new Pen(Color.White, 1.5f);
            g.DrawEllipse(ep, px - 5, py - 5, 10, 10);
        }

        // Rubber band from last point to mouse
        if (_mousePos != Point.Empty && _fourPts.Count > 0)
        {
            var last = _fourPts[^1];
            int lx = pbRect.X + (int)(last.X * pbRect.Width);
            int ly = pbRect.Y + (int)(last.Y * pbRect.Height);
            using var rp = new Pen(Color.Orange, 1f) { DashStyle = System.Drawing.Drawing2D.DashStyle.Dash };
            g.DrawLine(rp, lx, ly, _mousePos.X, _mousePos.Y);
        }

        // Show bounding box preview when 3+ points
        if (_fourPts.Count >= 2)
        {
            float x1 = _fourPts.Min(p => p.X), y1 = _fourPts.Min(p => p.Y);
            float x2 = _fourPts.Max(p => p.X), y2 = _fourPts.Max(p => p.Y);
            int bx1 = pbRect.X + (int)(x1 * pbRect.Width);
            int by1 = pbRect.Y + (int)(y1 * pbRect.Height);
            int bx2 = pbRect.X + (int)(x2 * pbRect.Width);
            int by2 = pbRect.Y + (int)(y2 * pbRect.Height);
            using var bp = new Pen(Color.FromArgb(180, Color.Orange), 1f)
                { DashStyle = System.Drawing.Drawing2D.DashStyle.DashDot };
            g.DrawRectangle(bp, bx1, by1, bx2 - bx1, by2 - by1);
        }
    }

    private void DrawRegion(Graphics g, BboxRegion r, int idx, bool sel)
    {
        var pbRect = GetPbImageRect();
        if (pbRect.IsEmpty) return;

        int px1 = pbRect.X + (int)(r.X1n * pbRect.Width);
        int py1 = pbRect.Y + (int)(r.Y1n * pbRect.Height);
        int px2 = pbRect.X + (int)(r.X2n * pbRect.Width);
        int py2 = pbRect.Y + (int)(r.Y2n * pbRect.Height);
        var rect = Rectangle.FromLTRB(px1, py1, px2, py2);

        var col = _palette[idx % _palette.Length];
        using (var fill = new SolidBrush(Color.FromArgb(sel ? 70 : 35, col)))
            g.FillRectangle(fill, rect);
        using (var pen = new Pen(Color.FromArgb(sel ? 220 : 160, col), sel ? 2.5f : 1.5f))
            g.DrawRectangle(pen, rect);

        // Label
        string label = $"{idx + 1}: {r.Name}";
        var sz = g.MeasureString(label, Theme.FSm);
        float tx = rect.X + 3, ty = rect.Y + 2;
        using (var bg = new SolidBrush(Color.FromArgb(160, 0, 0, 0)))
            g.FillRectangle(bg, tx - 1, ty - 1, sz.Width + 2, sz.Height);
        using (var fg = new SolidBrush(sel ? Color.White : col))
            g.DrawString(label, Theme.FSm, fg, tx, ty);

        // Handles (selected only)
        if (!sel) return;
        foreach (var (hx, hy) in GetHandlePoints(r))
        {
            g.FillRectangle(Brushes.White, hx - 5, hy - 5, 10, 10);
            using var hp = new Pen(col, 1.5f);
            g.DrawRectangle(hp, hx - 5, hy - 5, 10, 10);
        }
    }

    // ── Hit testing ───────────────────────────────────────────────────────

    private (int x, int y)[] GetHandlePoints(BboxRegion r)
    {
        var pbRect = GetPbImageRect();
        int px1 = pbRect.X + (int)(r.X1n * pbRect.Width);
        int py1 = pbRect.Y + (int)(r.Y1n * pbRect.Height);
        int px2 = pbRect.X + (int)(r.X2n * pbRect.Width);
        int py2 = pbRect.Y + (int)(r.Y2n * pbRect.Height);
        int hmid = (px1 + px2) / 2, vmid = (py1 + py2) / 2;
        return [
            (px1, py1), (hmid, py1), (px2, py1),
            (px2, vmid),
            (px2, py2), (hmid, py2), (px1, py2),
            (px1, vmid),
        ];
    }

    private int HitHandle(Point pbPt, BboxRegion r)
    {
        var handles = GetHandlePoints(r);
        for (int i = 0; i < handles.Length; i++)
        {
            var (hx, hy) = handles[i];
            if (Math.Abs(pbPt.X - hx) <= 7 && Math.Abs(pbPt.Y - hy) <= 7)
                return i;
        }
        return -1;
    }

    private bool HitRegion(Point pbPt, BboxRegion r)
    {
        var display = GetPbImageRect();
        if (!display.Contains(pbPt)) return false;
        float relX = (float)(pbPt.X - display.X) / display.Width;
        float relY = (float)(pbPt.Y - display.Y) / display.Height;
        return relX >= r.X1n && relX <= r.X2n && relY >= r.Y1n && relY <= r.Y2n;
    }

    private BboxRegion? FindRegionAt(Point pbPt)
    {
        for (int i = _regions.Count - 1; i >= 0; i--)
            if (HitRegion(pbPt, _regions[i])) return _regions[i];
        return null;
    }

    private void RightClickDelete(Point pbPt)
    {
        var region = FindRegionAt(pbPt);
        if (region is null) return;
        if (MessageBox.Show($"Xóa region '{region.Name}'?", "Xác nhận",
            MessageBoxButtons.YesNo, MessageBoxIcon.Warning) != DialogResult.Yes) return;
        _regions.Remove(region);
        if (_selected == region) _selected = null;
        RefreshList();
    }

    // ── Coordinate helpers ────────────────────────────────────────────────

    private Rectangle GetPbImageRect()
    {
        if (_pb.Image is null)
            return new Rectangle(0, 0, _pb.Width, _pb.Height);
        float scaleX = (float)_pb.Width  / _pb.Image.Width;
        float scaleY = (float)_pb.Height / _pb.Image.Height;
        float scale  = Math.Min(scaleX, scaleY);
        int   nw     = (int)(_pb.Image.Width  * scale);
        int   nh     = (int)(_pb.Image.Height * scale);
        return new Rectangle((_pb.Width - nw) / 2, (_pb.Height - nh) / 2, nw, nh);
    }

    private (int w, int h) FrameSize()
        => _pb.Image is not null ? (_pb.Image.Width, _pb.Image.Height) : (_pb.Width, _pb.Height);

    private PointF PbToNorm(Point pbPt)
    {
        var display = GetPbImageRect();
        if (display.IsEmpty || !display.Contains(pbPt)) return PointF.Empty;
        return new PointF(
            Math.Clamp((float)(pbPt.X - display.X) / display.Width,  0f, 1f),
            Math.Clamp((float)(pbPt.Y - display.Y) / display.Height, 0f, 1f));
    }

    private Rectangle ToImageRect(Rectangle pbRect)
    {
        var display = GetPbImageRect();
        if (display.IsEmpty) return Rectangle.Empty;
        var (fw, fh) = FrameSize();
        float sx = (float)fw / display.Width, sy = (float)fh / display.Height;
        int x1 = (int)((pbRect.Left   - display.Left) * sx);
        int y1 = (int)((pbRect.Top    - display.Top)  * sy);
        int x2 = (int)((pbRect.Right  - display.Left) * sx);
        int y2 = (int)((pbRect.Bottom - display.Top)  * sy);
        return Rectangle.FromLTRB(
            Math.Max(0, x1), Math.Max(0, y1),
            Math.Min(fw, x2), Math.Min(fh, y2));
    }

    private static Rectangle NormRect(Point a, Point b) => Rectangle.FromLTRB(
        Math.Min(a.X, b.X), Math.Min(a.Y, b.Y),
        Math.Max(a.X, b.X), Math.Max(a.Y, b.Y));

    // ── Actions ───────────────────────────────────────────────────────────

    private void RenameSelected()
    {
        var r = _selected ?? (_lv.SelectedItems.Count > 0
            ? (BboxRegion?)_lv.SelectedItems[0].Tag : null);
        if (r is null) return;
        using var dlg = new RenameDialog(r.Name);
        if (dlg.ShowDialog(this) != DialogResult.OK) return;
        r.Name = dlg.NewName.Trim();
        RefreshList();
    }

    private void DeleteSelected()
    {
        var r = _selected ?? (_lv.SelectedItems.Count > 0
            ? (BboxRegion?)_lv.SelectedItems[0].Tag : null);
        if (r is null) return;
        if (MessageBox.Show($"Xóa region '{r.Name}'?", "Xác nhận",
            MessageBoxButtons.YesNo, MessageBoxIcon.Warning) != DialogResult.Yes) return;
        _regions.Remove(r);
        if (_selected == r) _selected = null;
        RefreshList();
    }

    private void Commit() { Result = _regions; DialogResult = DialogResult.OK; Close(); }

    private static BboxRegion DeepCopy(BboxRegion r) => new()
    {
        Id = r.Id, Name = r.Name,
        X1n = r.X1n, Y1n = r.Y1n, X2n = r.X2n, Y2n = r.Y2n,
    };

    protected override void Dispose(bool disposing)
    {
        if (disposing) _bgFrame?.Dispose();
        base.Dispose(disposing);
    }
}

// ── Inline rename dialog ──────────────────────────────────────────────────────

internal sealed class RenameDialog : Form
{
    public string NewName { get; private set; } = "";

    public RenameDialog(string current)
    {
        Text            = "Đổi tên region";
        BackColor       = Color.FromArgb(0x2a, 0x2a, 0x3e);
        ForeColor       = Color.FromArgb(0xe0, 0xe0, 0xf0);
        Font            = new Font("Segoe UI", 9f);
        FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox     = false; MinimizeBox = false;
        StartPosition   = FormStartPosition.CenterParent;
        Size            = new Size(340, 120);

        var lbl = new Label { Text = "Tên mới:", Left = 12, Top = 14, AutoSize = true };
        var tb  = new TextBox
        {
            Left = 70, Top = 11, Width = 240, Text = current,
            BackColor = Color.FromArgb(0x16, 0x16, 0x2a),
            ForeColor = Color.FromArgb(0xe0, 0xe0, 0xf0),
            BorderStyle = BorderStyle.FixedSingle,
        };
        tb.SelectAll();

        var btnOk  = new Button { Text = "OK",  Left = 140, Top = 46, Width = 80, Height = 26, DialogResult = DialogResult.OK };
        var btnCnl = new Button { Text = "Hủy", Left = 230, Top = 46, Width = 70, Height = 26, DialogResult = DialogResult.Cancel };
        btnOk.FlatStyle = btnCnl.FlatStyle = FlatStyle.Flat;
        btnOk.BackColor  = Color.FromArgb(0xF0, 0x59, 0x22);
        btnCnl.BackColor = Color.FromArgb(0x2a, 0x2a, 0x3e);

        btnOk.Click += (_, _) => { NewName = tb.Text; DialogResult = DialogResult.OK; Close(); };
        tb.KeyDown  += (_, e) => { if (e.KeyCode == Keys.Enter) btnOk.PerformClick(); };

        Controls.AddRange([lbl, tb, btnOk, btnCnl]);
        AcceptButton = btnOk; CancelButton = btnCnl;
    }
}
