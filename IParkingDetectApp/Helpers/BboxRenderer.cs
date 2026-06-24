using System.Drawing.Drawing2D;
using IParkingDetect.Models;
using IParkingDetect.UI;

namespace IParkingDetect.Helpers;

/// <summary>Vẽ bounding boxes của YOLO lên Bitmap.</summary>
public static class BboxRenderer
{
    public static Bitmap DrawBoxes(Bitmap src, IReadOnlyList<DetectBox> boxes,
        int lineWidth = 2, int fontSize = 10, float alpha = 0.85f)
    {
        var result = new Bitmap(src);
        if (boxes.Count == 0) return result;

        using var g = Graphics.FromImage(result);
        g.SmoothingMode     = SmoothingMode.AntiAlias;
        g.TextRenderingHint = System.Drawing.Text.TextRenderingHint.ClearTypeGridFit;

        using var labelFont = new Font("Segoe UI", fontSize, FontStyle.Bold);

        foreach (var box in boxes)
        {
            var color = Theme.BboxColor(box.ClassId);
            using var pen  = new Pen(color, lineWidth);
            using var fill = new SolidBrush(Color.FromArgb(50, color));

            var rect = new RectangleF(box.X1, box.Y1, box.Width, box.Height);
            g.FillRectangle(fill, rect);
            g.DrawRectangle(pen, box.X1, box.Y1, box.Width, box.Height);

            // Label
            string label = $"{box.ClassName} {box.Confidence:P0}";
            var    size  = g.MeasureString(label, labelFont);
            float  lx    = box.X1;
            float  ly    = box.Y1 - size.Height - 2;
            if (ly < 0) ly = box.Y1 + 2;

            var lblRect = new RectangleF(lx, ly, size.Width + 4, size.Height + 2);
            using var bg = new SolidBrush(Color.FromArgb(200, color));
            g.FillRectangle(bg, lblRect);
            g.DrawString(label, labelFont, Brushes.White, lx + 2, ly + 1);
        }

        return result;
    }

    /// <summary>Tạo thumbnail 80×60 có bbox overlay, dùng cho filmstrip.</summary>
    public static Bitmap MakeThumb(Bitmap src, IReadOnlyList<DetectBox> boxes,
        int thumbW = 80, int thumbH = 60)
    {
        float scale = Math.Min((float)thumbW / src.Width, (float)thumbH / src.Height);
        int   dw    = (int)(src.Width  * scale);
        int   dh    = (int)(src.Height * scale);
        int   ox    = (thumbW - dw) / 2;
        int   oy    = (thumbH - dh) / 2;

        var thumb = new Bitmap(thumbW, thumbH);
        using var g = Graphics.FromImage(thumb);
        g.Clear(Color.FromArgb(22, 22, 42));
        g.InterpolationMode = InterpolationMode.Bilinear;
        g.DrawImage(src, ox, oy, dw, dh);

        // Vẽ bbox thu nhỏ
        foreach (var box in boxes)
        {
            var color = Theme.BboxColor(box.ClassId);
            using var pen = new Pen(color, 1.5f);
            float tx = ox + box.X1 * scale;
            float ty = oy + box.Y1 * scale;
            float tw = box.Width  * scale;
            float th = box.Height * scale;
            g.DrawRectangle(pen, tx, ty, tw, th);
        }

        return thumb;
    }

    /// <summary>Scale ảnh về maxW×maxH giữ tỷ lệ.</summary>
    public static Bitmap FitImage(Bitmap src, int maxW, int maxH)
    {
        float scale = Math.Min((float)maxW / src.Width, (float)maxH / src.Height);
        int   nw    = Math.Max(1, (int)(src.Width  * scale));
        int   nh    = Math.Max(1, (int)(src.Height * scale));
        var   result = new Bitmap(nw, nh);
        using var g = Graphics.FromImage(result);
        g.InterpolationMode = InterpolationMode.HighQualityBilinear;
        g.DrawImage(src, 0, 0, nw, nh);
        return result;
    }
}
