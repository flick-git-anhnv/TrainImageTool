using System.Drawing.Imaging;
using System.Runtime.InteropServices;
using IParkingDetect.Models;
using Sdcb.OpenVINO;

namespace IParkingDetect.Inference;

/// <summary>
/// Wrapper OpenVINO inference cho YOLO.
/// Hỗ trợ:
///   - ONNX (.onnx) — Ultralytics export trực tiếp
///   - OpenVINO IR (.xml + .bin) — Ultralytics export --format openvino
/// </summary>
public sealed class YoloRunner : IDisposable
{
    private OVCore?        _core;
    private CompiledModel? _compiled;
    // ThreadLocal: mỗi thread có InferRequest riêng → Parallel.ForEach không chờ nhau
    private ThreadLocal<InferRequest>? _reqPool;

    public bool     IsLoaded    => _compiled is not null;
    public string   ModelPath   { get; private set; } = "";
    public int      InputW      { get; private set; } = 640;
    public int      InputH      { get; private set; } = 640;
    public int      NumClasses  { get; private set; } = 1;
    public string[] ClassNames  { get; set; } = [];
    /// <summary>Số luồng song song tối ưu cho Parallel.ForEach.</summary>
    public int      Parallelism { get; private set; } = 1;

    // ── Load model ────────────────────────────────────────────────────────

    /// <summary>
    /// Load model từ path.
    /// Chấp nhận: file .onnx, file .xml, hoặc folder chứa .xml (Ultralytics openvino_model/).
    /// Gọi trên background thread.
    /// </summary>
    public void LoadModel(string path, string device = "CPU")
    {
        // Resolve folder → tìm .xml bên trong (Ultralytics export tạo folder openvino_model/)
        if (Directory.Exists(path))
        {
            var xmlFiles = Directory.GetFiles(path, "*.xml");
            if (xmlFiles.Length == 0)
                throw new FileNotFoundException(
                    $"Không tìm thấy file .xml trong thư mục:\n{path}");
            path = xmlFiles[0];  // lấy .xml đầu tiên
        }

        DisposeModel();
        _core = new OVCore();

        Model model;
        if (path.EndsWith(".xml", StringComparison.OrdinalIgnoreCase))
        {
            var binPath = Path.ChangeExtension(path, ".bin");
            if (!File.Exists(binPath))
                throw new FileNotFoundException($"Không tìm thấy file .bin tương ứng:\n{binPath}");
            model = _core.ReadModel(path, binPath);
        }
        else
        {
            model = _core.ReadModel(path);
        }

        using (model)
        {
            // Đọc input shape
            try
            {
                var shape = model.Inputs[0].Shape;
                InputH = shape.Rank >= 3 ? (int)shape[2] : 640;
                InputW = shape.Rank >= 4 ? (int)shape[3] : 640;
                if (InputH <= 0) InputH = 640;
                if (InputW <= 0) InputW = 640;
            }
            catch { InputH = InputW = 640; }

            _compiled = _core.CompileModel(model, device);
        }

        // Tạo ThreadLocal pool — factory gọi lazy khi thread đầu tiên access .Value
        var compiled = _compiled;
        _reqPool = new ThreadLocal<InferRequest>(
            () => compiled.CreateInferRequest(), trackAllValues: true);

        // Số luồng song song: logic core / 2, min 1, max 8
        Parallelism = Math.Clamp(Environment.ProcessorCount / 2, 1, 8);
        ModelPath = path;

        // Đọc số class từ output shape: [1, 4+N, anchors]
        try
        {
            var outShape = _compiled.Outputs[0].Shape;
            NumClasses = Math.Max(1, (int)outShape[1] - 4);
        }
        catch { NumClasses = 1; }

        // Auto-load class names từ metadata.yaml / data.yaml trong cùng folder
        if (!TryAutoLoadYaml(path) || ClassNames.Length != NumClasses)
            ClassNames = Enumerable.Range(0, NumClasses).Select(i => $"cls{i}").ToArray();
    }

    // ── Inference ─────────────────────────────────────────────────────────

    public List<DetectBox> Detect(string imagePath, float conf, float iou, int[]? enabledClasses = null)
    {
        if (!IsLoaded) return [];
        using var bmp = TryLoadBitmap(imagePath);
        if (bmp is null) return [];
        return Detect(bmp, conf, iou, enabledClasses);
    }

    public List<DetectBox> Detect(Bitmap bmp, float conf, float iou, int[]? enabledClasses = null)
    {
        if (_reqPool is null) return [];

        // Lấy InferRequest của thread hiện tại (tạo mới nếu lần đầu thread này chạy)
        var req = _reqPool.Value!;

        int origW = bmp.Width, origH = bmp.Height;

        // Letterbox + chuyển NCHW float
        float[] blob = Letterbox(bmp, InputW, InputH, out float scale, out float padX, out float padY);

        // Set input
        Span<float> inputSpan = req.Inputs[0].GetData<float>();
        if (blob.Length != inputSpan.Length)
            throw new InvalidOperationException(
                $"Input size mismatch: model expects {inputSpan.Length} floats, got {blob.Length}.");
        blob.AsSpan().CopyTo(inputSpan);

        // Infer (chỉ req này, các thread khác chạy req của riêng chúng song song)
        req.Run();

        // Đọc output
        Span<float> outData  = req.Outputs[0].GetData<float>();
        var          outShape = req.Outputs[0].Shape;
        int numCh      = (int)outShape[1];
        int numAnchors = (int)outShape[2];

        return PostProcess.Decode(outData, numCh, numAnchors, conf, iou,
            origW, origH, InputW, InputH, scale, padX, padY, ClassNames, enabledClasses);
    }

    // ── Image preprocessing ───────────────────────────────────────────────

    private static float[] Letterbox(Bitmap src, int tW, int tH,
        out float scale, out float padX, out float padY)
    {
        float sw = (float)tW / src.Width;
        float sh = (float)tH / src.Height;
        scale = Math.Min(sw, sh);

        int nw = (int)Math.Round(src.Width  * scale);
        int nh = (int)Math.Round(src.Height * scale);
        padX = (tW - nw) / 2f;
        padY = (tH - nh) / 2f;

        using var canvas = new Bitmap(tW, tH, PixelFormat.Format24bppRgb);
        using var g = Graphics.FromImage(canvas);
        g.Clear(Color.FromArgb(114, 114, 114));
        g.InterpolationMode = System.Drawing.Drawing2D.InterpolationMode.Bilinear;
        g.DrawImage(src, (int)padX, (int)padY, nw, nh);

        return BitmapToNCHW(canvas, tW, tH);
    }

    private static unsafe float[] BitmapToNCHW(Bitmap bmp, int w, int h)
    {
        float[] blob = new float[3 * h * w];
        var bits = bmp.LockBits(new Rectangle(0, 0, w, h),
            ImageLockMode.ReadOnly, PixelFormat.Format24bppRgb);

        byte* ptr    = (byte*)bits.Scan0;
        int   stride = bits.Stride;

        for (int y = 0; y < h; y++)
        {
            byte* row = ptr + y * stride;
            for (int x = 0; x < w; x++)
            {
                int i3 = x * 3;
                blob[0 * h * w + y * w + x] = row[i3 + 2] / 255f; // R
                blob[1 * h * w + y * w + x] = row[i3 + 1] / 255f; // G
                blob[2 * h * w + y * w + x] = row[i3 + 0] / 255f; // B
            }
        }

        bmp.UnlockBits(bits);
        return blob;
    }

    // ── YAML class name loader ────────────────────────────────────────────

    /// <summary>Đọc class names từ data.yaml của Ultralytics.</summary>
    public static string[] LoadClassNamesFromYaml(string yamlPath)
    {
        var lines   = File.ReadAllLines(yamlPath);
        var inNames = false;
        var result  = new SortedDictionary<int, string>();  // id → name (hỗ trợ dict format)
        var listResult = new List<string>();

        foreach (var line in lines)
        {
            if (line.TrimStart().StartsWith("names:", StringComparison.Ordinal))
            {
                // names: ['plate', 'vehicle']  — inline list
                int start = line.IndexOf('[');
                int end   = line.LastIndexOf(']');
                if (start >= 0 && end > start)
                {
                    listResult.AddRange(line[(start + 1)..end]
                        .Split(',')
                        .Select(s => s.Trim().Trim('\'', '"'))
                        .Where(s => s.Length > 0));
                    break;
                }
                inNames = true;
                continue;
            }
            if (inNames)
            {
                var trimmed = line.TrimStart();
                if (string.IsNullOrWhiteSpace(trimmed)) continue;

                // Dict format: "  0: car"  (Ultralytics metadata.yaml)
                var colonIdx = trimmed.IndexOf(':');
                if (colonIdx > 0 && int.TryParse(trimmed[..colonIdx].Trim(), out int id))
                {
                    result[id] = trimmed[(colonIdx + 1)..].Trim().Trim('\'', '"');
                    continue;
                }

                // List format: "  - car"
                if (trimmed.StartsWith('-'))
                {
                    listResult.Add(trimmed.TrimStart('-').Trim().Trim('\'', '"'));
                    continue;
                }

                break; // done
            }
        }

        // Dict format wins over list format
        if (result.Count > 0) return result.Values.ToArray();
        return listResult.Count > 0 ? listResult.ToArray() : [];
    }

    /// <summary>
    /// Tự động tìm và load YAML trong thư mục model (metadata.yaml từ Ultralytics).
    /// Trả về true nếu load được class names.
    /// </summary>
    public bool TryAutoLoadYaml(string modelFolderOrFile)
    {
        var dir = Directory.Exists(modelFolderOrFile)
            ? modelFolderOrFile
            : Path.GetDirectoryName(modelFolderOrFile) ?? "";

        // Ưu tiên: metadata.yaml → data.yaml → *.yaml
        var candidates = new[] { "metadata.yaml", "data.yaml" }
            .Select(f => Path.Combine(dir, f))
            .Concat(Directory.Exists(dir)
                ? Directory.GetFiles(dir, "*.yaml")
                : [])
            .Distinct()
            .FirstOrDefault(File.Exists);

        if (candidates is null) return false;

        try
        {
            var names = LoadClassNamesFromYaml(candidates);
            if (names.Length > 0) { ClassNames = names; return true; }
        }
        catch { }
        return false;
    }

    // ── Helpers ───────────────────────────────────────────────────────────

    private static Bitmap? TryLoadBitmap(string path)
    {
        try { return new Bitmap(path); }
        catch { return null; }
    }

    private void DisposeModel()
    {
        if (_reqPool is not null)
        {
            foreach (var r in _reqPool.Values) r?.Dispose();
            _reqPool.Dispose();
            _reqPool = null;
        }
        _compiled?.Dispose();
        _core?.Dispose();
        _compiled = null; _core = null;
    }

    public void Dispose() => DisposeModel();
}
