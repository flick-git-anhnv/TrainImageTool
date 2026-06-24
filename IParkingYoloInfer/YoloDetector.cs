using Microsoft.ML.OnnxRuntime;
using Microsoft.ML.OnnxRuntime.Tensors;
using OpenCvSharp;

namespace IParkingYoloInfer;

/// <summary>
/// YOLO11 inference với ONNX Runtime.
/// Hỗ trợ model export từ: model.export(format='onnx') hoặc format='openvino' → convert sang onnx.
/// Input: [1,3,H,W] float32 (letterbox, normalized 0-1)
/// Output: [1, 4+nc, 8400] float32 (cx,cy,w,h + class_scores)
/// </summary>
public sealed class YoloDetector : IDisposable
{
    private readonly InferenceSession _session;
    private readonly string[]         _classNames;
    private readonly int              _inputW;
    private readonly int              _inputH;

    // Màu vẽ cho mỗi class (BGR cho OpenCv)
    private static readonly Scalar[] _palette =
    [
        new(86, 180, 233),   // xanh dương
        new(230, 159,   0),  // cam
        new(  0, 158, 115),  // xanh lá
        new(240, 228,  66),  // vàng
        new(  0, 114, 178),  // navy
        new(213,  94,   0),  // đỏ cam
        new(204, 121, 167),  // tím
        new( 89, 204, 197),  // cyan
    ];

    public YoloDetector(string modelPath, IEnumerable<string> classNames,
                        int inputW = 640, int inputH = 640,
                        bool useDirectML = false)
    {
        var opts = new SessionOptions();
        opts.GraphOptimizationLevel = GraphOptimizationLevel.ORT_ENABLE_ALL;
        opts.ExecutionMode = ExecutionMode.ORT_SEQUENTIAL;

        // Uncomment để dùng DirectML (GPU trên Windows mà không cần CUDA):
        // if (useDirectML) opts.AppendExecutionProvider_DML();

        // Uncomment để dùng OpenVINO EP (cần cài OpenVINO runtime):
        // opts.AppendExecutionProvider("OpenVINO");

        _session    = new InferenceSession(modelPath, opts);
        _classNames = classNames.ToArray();
        _inputW     = inputW;
        _inputH     = inputH;
    }

    /// <summary>Chạy detect trên 1 ảnh (BGR Mat). Trả về list box đã NMS.</summary>
    public List<DetectionResult> Detect(Mat image,
                                        float confThresh = 0.25f,
                                        float iouThresh  = 0.45f)
    {
        // Letterbox preprocess
        float[] inputData = Letterbox(image, out float scaleX, out float scaleY,
                                      out int padX, out int padY);

        var tensor = new DenseTensor<float>(inputData,
            new[] { 1, 3, _inputH, _inputW });

        string inputName = _session.InputMetadata.Keys.First();
        using var results = _session.Run(
            [NamedOnnxValue.CreateFromTensor(inputName, tensor)]);

        var output = results.First().AsTensor<float>();
        return Postprocess(output, image.Width, image.Height,
                           scaleX, scaleY, padX, padY, confThresh, iouThresh);
    }

    /// <summary>Draw boxes lên ảnh và trả về ảnh mới (không modify gốc).</summary>
    public Mat DrawDetections(Mat image, IEnumerable<DetectionResult> detections)
    {
        var result = image.Clone();
        foreach (var d in detections)
        {
            var color = _palette[d.ClassIndex % _palette.Length];
            Cv2.Rectangle(result,
                new Point((int)d.X1, (int)d.Y1),
                new Point((int)d.X2, (int)d.Y2),
                color, 2);

            string label = $"{d.ClassName} {d.Confidence:P0}";
            int baseline = 0;
            var sz = Cv2.GetTextSize(label, HersheyFonts.HersheySimplex, 0.55, 1, out baseline);
            Cv2.Rectangle(result,
                new Point((int)d.X1, (int)d.Y1 - sz.Height - 6),
                new Point((int)d.X1 + sz.Width + 2, (int)d.Y1),
                color, -1);
            Cv2.PutText(result, label,
                new Point((int)d.X1 + 1, (int)d.Y1 - 4),
                HersheyFonts.HersheySimplex, 0.55,
                new Scalar(255, 255, 255), 1);
        }
        return result;
    }

    // ── Private helpers ────────────────────────────────────────────────────

    private float[] Letterbox(Mat src, out float scaleX, out float scaleY,
                               out int padX, out int padY)
    {
        // Tính tỷ lệ letterbox
        float scaleW = _inputW / (float)src.Width;
        float scaleH = _inputH / (float)src.Height;
        float scale  = Math.Min(scaleW, scaleH);
        int newW     = (int)Math.Round(src.Width  * scale);
        int newH     = (int)Math.Round(src.Height * scale);
        padX         = (_inputW - newW) / 2;
        padY         = (_inputH - newH) / 2;
        scaleX       = scale;
        scaleY       = scale;

        using var resized = src.Resize(new Size(newW, newH), interpolation: InterpolationFlags.Linear);
        using var padded  = new Mat();
        Cv2.CopyMakeBorder(resized, padded, padY, _inputH - newH - padY,
                           padX, _inputW - newW - padX,
                           BorderTypes.Constant, new Scalar(114, 114, 114));

        // Mat (BGR byte) → float array (RGB, CHW, /255)
        float[] data = new float[3 * _inputH * _inputW];
        int area = _inputH * _inputW;
        unsafe
        {
            byte* ptr = padded.DataPointer;
            for (int i = 0; i < area; i++)
            {
                data[2 * area + i] = ptr[i * 3 + 0] / 255f; // B→R channel
                data[1 * area + i] = ptr[i * 3 + 1] / 255f; // G
                data[0 * area + i] = ptr[i * 3 + 2] / 255f; // R→B channel
            }
        }
        return data;
    }

    private List<DetectionResult> Postprocess(Tensor<float> output,
        int origW, int origH, float scaleX, float scaleY, int padX, int padY,
        float confThresh, float iouThresh)
    {
        // Shape: [1, 4+nc, 8400]
        int numDets = output.Dimensions[2];
        int nc      = output.Dimensions[1] - 4;

        var dets = new List<DetectionResult>();

        for (int i = 0; i < numDets; i++)
        {
            float maxConf = 0; int maxCls = 0;
            for (int c = 0; c < nc; c++)
            {
                float s = output[0, 4 + c, i];
                if (s > maxConf) { maxConf = s; maxCls = c; }
            }
            if (maxConf < confThresh) continue;

            // cx,cy,w,h trong không gian letterbox → pixel gốc
            float cx = output[0, 0, i];
            float cy = output[0, 1, i];
            float bw = output[0, 2, i];
            float bh = output[0, 3, i];

            float x1 = (cx - bw / 2 - padX) / scaleX;
            float y1 = (cy - bh / 2 - padY) / scaleY;
            float x2 = (cx + bw / 2 - padX) / scaleX;
            float y2 = (cy + bh / 2 - padY) / scaleY;

            x1 = Math.Clamp(x1, 0, origW); y1 = Math.Clamp(y1, 0, origH);
            x2 = Math.Clamp(x2, 0, origW); y2 = Math.Clamp(y2, 0, origH);

            string name = maxCls < _classNames.Length ? _classNames[maxCls] : $"cls{maxCls}";
            dets.Add(new DetectionResult(x1, y1, x2, y2, maxConf, maxCls, name));
        }

        return NMS(dets, iouThresh);
    }

    private static List<DetectionResult> NMS(List<DetectionResult> dets, float iouThresh)
    {
        var sorted = dets.OrderByDescending(d => d.Confidence).ToList();
        var keep   = new List<DetectionResult>();
        while (sorted.Count > 0)
        {
            var best = sorted[0];
            keep.Add(best);
            sorted.RemoveAt(0);
            sorted.RemoveAll(d => d.ClassIndex == best.ClassIndex && IoU(best, d) > iouThresh);
        }
        return keep;
    }

    private static float IoU(DetectionResult a, DetectionResult b)
    {
        float ix1 = Math.Max(a.X1, b.X1), iy1 = Math.Max(a.Y1, b.Y1);
        float ix2 = Math.Min(a.X2, b.X2), iy2 = Math.Min(a.Y2, b.Y2);
        float inter = Math.Max(0, ix2 - ix1) * Math.Max(0, iy2 - iy1);
        float aArea = a.Width * a.Height, bArea = b.Width * b.Height;
        return inter / (aArea + bArea - inter + 1e-6f);
    }

    public void Dispose() => _session.Dispose();
}
