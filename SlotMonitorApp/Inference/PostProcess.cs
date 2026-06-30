using SlotMonitor.Models;

namespace SlotMonitor.Inference;

/// <summary>
/// Giải mã output YOLOv8/v11 và áp dụng NMS.
/// Shape: [1, 4+numClasses, numAnchors]
/// Channel 0-3: cx, cy, w, h  |  Channel 4+: class score (0–1)
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

        HashSet<int>? enabledSet = enabledClasses is { Length: > 0 }
            ? new HashSet<int>(enabledClasses) : null;

        var candidates = new List<(int cid, float conf, float x1, float y1, float x2, float y2)>(128);

        for (int a = 0; a < numAnchors; a++)
        {
            float maxScore = 0f;
            int   maxClass = 0;
            for (int c = 0; c < numClasses; c++)
            {
                float score = data[(4 + c) * numAnchors + a];
                if (score > maxScore) { maxScore = score; maxClass = c; }
            }

            if (maxScore < confThresh) continue;
            if (enabledSet != null && !enabledSet.Contains(maxClass)) continue;

            float cx = data[0 * numAnchors + a];
            float cy = data[1 * numAnchors + a];
            float bw = data[2 * numAnchors + a];
            float bh = data[3 * numAnchors + a];

            float x1 = Math.Max(0,     (cx - bw * 0.5f - padX) / scale);
            float y1 = Math.Max(0,     (cy - bh * 0.5f - padY) / scale);
            float x2 = Math.Min(origW, (cx + bw * 0.5f - padX) / scale);
            float y2 = Math.Min(origH, (cy + bh * 0.5f - padY) / scale);

            if (x2 <= x1 + 1f || y2 <= y1 + 1f) continue;
            candidates.Add((maxClass, maxScore, x1, y1, x2, y2));
        }

        if (candidates.Count == 0) return [];
        candidates.Sort(static (a, b) => b.conf.CompareTo(a.conf));

        return ApplyNMS(candidates, iouThresh)
            .ConvertAll(b => new DetectBox(
                b.cid,
                b.cid < classNames.Length ? classNames[b.cid] : $"cls{b.cid}",
                b.conf, b.x1, b.y1, b.x2, b.y2));
    }

    private static List<(int cid, float conf, float x1, float y1, float x2, float y2)>
        ApplyNMS(List<(int cid, float conf, float x1, float y1, float x2, float y2)> boxes, float iouThresh)
    {
        var suppressed = new bool[boxes.Count];
        var result = new List<(int, float, float, float, float, float)>(boxes.Count);

        for (int i = 0; i < boxes.Count; i++)
        {
            if (suppressed[i]) continue;
            result.Add(boxes[i]);
            for (int j = i + 1; j < boxes.Count; j++)
            {
                if (!suppressed[j] && boxes[i].cid == boxes[j].cid && Iou(boxes[i], boxes[j]) > iouThresh)
                    suppressed[j] = true;
            }
        }
        return result;
    }

    private static float Iou(
        (int, float, float x1, float y1, float x2, float y2) a,
        (int, float, float x1, float y1, float x2, float y2) b)
    {
        float iw = Math.Max(0, Math.Min(a.x2, b.x2) - Math.Max(a.x1, b.x1));
        float ih = Math.Max(0, Math.Min(a.y2, b.y2) - Math.Max(a.y1, b.y1));
        float inter = iw * ih;
        if (inter <= 0) return 0f;
        float areaA = (a.x2 - a.x1) * (a.y2 - a.y1);
        float areaB = (b.x2 - b.x1) * (b.y2 - b.y1);
        return inter / (areaA + areaB - inter);
    }
}
