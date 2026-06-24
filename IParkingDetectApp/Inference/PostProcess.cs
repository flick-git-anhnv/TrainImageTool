using IParkingDetect.Models;

namespace IParkingDetect.Inference;

/// <summary>
/// Giải mã output YOLOv8/v11 và áp dụng NMS.
///
/// Định dạng output chuẩn từ Ultralytics export:
///   Shape: [1, 4+numClasses, numAnchors]  (ví dụ [1,5,8400] cho 1 class)
///   Channel 0-3: cx, cy, w, h   (pixel space của input 640×640)
///   Channel 4+:  class score (đã qua sigmoid, giá trị 0–1)
/// </summary>
public static class PostProcess
{
    public static List<DetectBox> Decode(
        Span<float> data,
        int numCh, int numAnchors,
        float confThresh, float iouThresh,
        int origW, int origH,
        int inputW, int inputH,
        float scale, float padX, float padY,
        string[] classNames,
        int[]? enabledClasses = null)
    {
        int numClasses = numCh - 4;
        if (numClasses <= 0) return [];

        var candidates = new List<(int cid, float conf, float x1, float y1, float x2, float y2)>(
            capacity: 128);

        for (int a = 0; a < numAnchors; a++)
        {
            // Tìm class có score cao nhất
            float maxScore = 0f;
            int maxClass = 0;
            for (int c = 0; c < numClasses; c++)
            {
                float score = data[(4 + c) * numAnchors + a];
                if (score > maxScore) { maxScore = score; maxClass = c; }
            }

            if (maxScore < confThresh) continue;
            if (enabledClasses != null && !enabledClasses.Contains(maxClass)) continue;

            float cx = data[0 * numAnchors + a];
            float cy = data[1 * numAnchors + a];
            float bw = data[2 * numAnchors + a];
            float bh = data[3 * numAnchors + a];

            // Undo letterbox → tọa độ ảnh gốc
            float x1 = Math.Max(0, (cx - bw * 0.5f - padX) / scale);
            float y1 = Math.Max(0, (cy - bh * 0.5f - padY) / scale);
            float x2 = Math.Min(origW, (cx + bw * 0.5f - padX) / scale);
            float y2 = Math.Min(origH, (cy + bh * 0.5f - padY) / scale);

            if (x2 <= x1 + 1f || y2 <= y1 + 1f) continue;

            candidates.Add((maxClass, maxScore, x1, y1, x2, y2));
        }

        if (candidates.Count == 0) return [];

        return ApplyNMS(candidates, iouThresh)
            .Select(b => new DetectBox(
                b.cid,
                b.cid < classNames.Length ? classNames[b.cid] : $"cls{b.cid}",
                b.conf, b.x1, b.y1, b.x2, b.y2))
            .ToList();
    }

    // ── NMS ──────────────────────────────────────────────────────────────

    private static IEnumerable<(int cid, float conf, float x1, float y1, float x2, float y2)>
        ApplyNMS(List<(int cid, float conf, float x1, float y1, float x2, float y2)> boxes,
                 float iouThresh)
    {
        // Sort by confidence descending
        var sorted = boxes.OrderByDescending(b => b.conf).ToArray();
        var suppressed = new bool[sorted.Length];

        for (int i = 0; i < sorted.Length; i++)
        {
            if (suppressed[i]) continue;
            yield return sorted[i];

            for (int j = i + 1; j < sorted.Length; j++)
            {
                if (suppressed[j]) continue;
                // NMS per class
                if (sorted[i].cid == sorted[j].cid && Iou(sorted[i], sorted[j]) > iouThresh)
                    suppressed[j] = true;
            }
        }
    }

    private static float Iou(
        (int, float, float x1, float y1, float x2, float y2) a,
        (int, float, float x1, float y1, float x2, float y2) b)
    {
        float ix1 = Math.Max(a.x1, b.x1);
        float iy1 = Math.Max(a.y1, b.y1);
        float ix2 = Math.Min(a.x2, b.x2);
        float iy2 = Math.Min(a.y2, b.y2);
        float iw = Math.Max(0, ix2 - ix1);
        float ih = Math.Max(0, iy2 - iy1);
        float inter = iw * ih;
        if (inter <= 0) return 0f;
        float areaA = (a.x2 - a.x1) * (a.y2 - a.y1);
        float areaB = (b.x2 - b.x1) * (b.y2 - b.y1);
        return inter / (areaA + areaB - inter);
    }
}
