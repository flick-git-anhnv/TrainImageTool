using System.Drawing.Drawing2D;
using IParkingDetect.UI;

namespace IParkingDetect.Controls;

/// <summary>
/// Panel hiển thị ảnh với zoom/pan bằng chuột.
///  - MouseWheel: zoom vào/ra tại vị trí con trỏ
///  - LeftButton drag: pan
///  - DoubleClick: fit ảnh vào khung
/// </summary>
public sealed class ImageCanvas : Panel
{
    private Bitmap? _bmp;
    private float   _zoom   = 1f;
    private PointF  _origin = PointF.Empty;  // top-left của ảnh trên canvas (pixel)
    private Point   _dragStart;
    private PointF  _originAtDrag;
    private bool    _dragging;

    public float Zoom => _zoom;

    public void SetImage(Bitmap? bmp, bool fit = true)
    {
        _bmp?.Dispose();
        _bmp = bmp is null ? null : new Bitmap(bmp);
        if (fit) FitToView();
        else Invalidate();
    }

    public void FitToView()
    {
        if (_bmp is null || ClientSize.Width <= 0 || ClientSize.Height <= 0)
        {
            _zoom = 1f; _origin = PointF.Empty; return;
        }
        float sx = (float)ClientSize.Width  / _bmp.Width;
        float sy = (float)ClientSize.Height / _bmp.Height;
        _zoom = Math.Min(sx, sy);
        CenterImage();
        Invalidate();
    }

    public void ZoomStep(float delta)
    {
        float newZoom = Math.Clamp(_zoom * delta, 0.05f, 20f);
        // Zoom tại tâm canvas
        var center = new PointF(ClientSize.Width / 2f, ClientSize.Height / 2f);
        _origin.X = center.X - (center.X - _origin.X) * newZoom / _zoom;
        _origin.Y = center.Y - (center.Y - _origin.Y) * newZoom / _zoom;
        _zoom = newZoom;
        Invalidate();
    }

    // ── Paint ─────────────────────────────────────────────────────────────

    protected override void OnPaint(PaintEventArgs e)
    {
        var g = e.Graphics;
        g.Clear(Theme.Deep);

        if (_bmp is null)
        {
            using var b = new SolidBrush(Theme.Dim);
            var s = "Chưa có ảnh";
            var sz = g.MeasureString(s, Theme.FMain);
            g.DrawString(s, Theme.FMain, b,
                (ClientSize.Width - sz.Width) / 2f,
                (ClientSize.Height - sz.Height) / 2f);
            return;
        }

        g.InterpolationMode = _zoom >= 1f
            ? InterpolationMode.NearestNeighbor
            : InterpolationMode.Bilinear;

        float dw = _bmp.Width  * _zoom;
        float dh = _bmp.Height * _zoom;
        g.DrawImage(_bmp, _origin.X, _origin.Y, dw, dh);
    }

    // ── Mouse events ──────────────────────────────────────────────────────

    protected override void OnMouseDown(MouseEventArgs e)
    {
        base.OnMouseDown(e);
        if (e.Button == MouseButtons.Left)
        {
            _dragging     = true;
            _dragStart    = e.Location;
            _originAtDrag = _origin;
            Cursor        = Cursors.SizeAll;
        }
    }

    protected override void OnMouseMove(MouseEventArgs e)
    {
        base.OnMouseMove(e);
        if (_dragging)
        {
            _origin = new PointF(
                _originAtDrag.X + e.X - _dragStart.X,
                _originAtDrag.Y + e.Y - _dragStart.Y);
            Invalidate();
        }
    }

    protected override void OnMouseUp(MouseEventArgs e)
    {
        base.OnMouseUp(e);
        _dragging = false;
        Cursor    = Cursors.Default;
    }

    protected override void OnMouseWheel(MouseEventArgs e)
    {
        base.OnMouseWheel(e);
        float delta   = e.Delta > 0 ? 1.15f : 1f / 1.15f;
        float newZoom = Math.Clamp(_zoom * delta, 0.03f, 20f);

        // Zoom tại vị trí con trỏ
        _origin.X = e.X - (e.X - _origin.X) * newZoom / _zoom;
        _origin.Y = e.Y - (e.Y - _origin.Y) * newZoom / _zoom;
        _zoom     = newZoom;
        Invalidate();
    }

    protected override void OnDoubleClick(EventArgs e)
    {
        base.OnDoubleClick(e);
        FitToView();
    }

    protected override void OnResize(EventArgs e)
    {
        base.OnResize(e);
        if (_bmp is null) return;
        // Nếu đang fit (zoom ~ tỷ lệ fit), tự re-fit
        float expectedZoom = Math.Min(
            (float)ClientSize.Width  / _bmp.Width,
            (float)ClientSize.Height / _bmp.Height);
        if (Math.Abs(_zoom - expectedZoom) < 0.05f)
            FitToView();
        else
            Invalidate();
    }

    // ── Helpers ───────────────────────────────────────────────────────────

    private void CenterImage()
    {
        if (_bmp is null) return;
        float dw = _bmp.Width  * _zoom;
        float dh = _bmp.Height * _zoom;
        _origin = new PointF(
            (ClientSize.Width  - dw) / 2f,
            (ClientSize.Height - dh) / 2f);
    }

    protected override void Dispose(bool disposing)
    {
        if (disposing) _bmp?.Dispose();
        base.Dispose(disposing);
    }
}
