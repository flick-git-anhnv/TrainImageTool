using System.Drawing.Imaging;
using System.Runtime.InteropServices;
using System.Threading.Channels;
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
    // Batch model: THROUGHPUT hint — OpenVINO tạo multiple streams, mỗi stream ít threads
    // → Parallel.ForEach thực sự song song
    private CompiledModel? _compiled;
    // API model: LATENCY hint — dùng nhiều threads nhất cho 1 request → low latency
    private CompiledModel? _apiCompiled;
    // ThreadLocal batch pool
    private ThreadLocal<InferRequest>? _reqPool;
    // Channel pool riêng cho API — không compete với batch
    private Channel<InferRequest>?     _apiPool;
    public  int                        ApiParallelism { get; private set; } = 2;

    public bool     IsLoaded      => _compiled is not null;
    public string   ModelPath     { get; private set; } = "";
    public string   ActualDevice  { get; private set; } = "";   // thiết bị thực tế sau khi compile
    public int      InputW        { get; private set; } = 640;
    public int      InputH        { get; private set; } = 640;
    public int      NumClasses    { get; private set; } = 1;
    public string[] ClassNames    { get; set; } = [];
    /// <summary>Số luồng song song tối ưu cho Parallel.ForEach.</summary>
    public int      Parallelism   { get; private set; } = 1;

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

        // Cache compiled model → lần 2+ load gần như tức thì (thay vì 5–30s)
        var cacheDir = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
            "KZTEK", "IParkingDetect", "model_cache");
        Directory.CreateDirectory(cacheDir);
        // "" = global (tất cả device đều dùng cache)
        _core.SetDeviceProperty("", PropertyKeys.CacheDir, cacheDir);

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

            int  total  = Environment.ProcessorCount;
            bool isCpu  = device.Equals("CPU", StringComparison.OrdinalIgnoreCase);

            // Batch: THROUGHPUT → multiple streams, song song thật sự
            int batchThreads = Math.Max(1, total * 3 / 4);
            var batchOpts = new DeviceOptions(device)
            {
                PerformanceMode = PerformanceMode.Throughput,
            };
            // InferenceNumThreads chỉ có nghĩa với CPU — AUTO/GPU tự quản lý thread
            if (isCpu) batchOpts.InferenceNumThreads = batchThreads;
            _compiled = _core.CompileModel(model, batchOpts);

            // API: LATENCY → tối thiểu độ trễ cho 1 request
            int apiThreads = Math.Max(2, total / 4);
            var apiOpts = new DeviceOptions(device)
            {
                PerformanceMode = PerformanceMode.Latency,
            };
            if (isCpu) apiOpts.InferenceNumThreads = apiThreads;
            _apiCompiled = _core.CompileModel(model, apiOpts);
        }

        // Batch pool — THROUGHPUT model
        var compiled = _compiled;
        _reqPool = new ThreadLocal<InferRequest>(
            () => compiled.CreateInferRequest(), trackAllValues: true);

        // API pool — LATENCY model, không share với batch
        ApiParallelism = Math.Clamp(Environment.ProcessorCount / 4, 1, 4);
        var apiCompiled = _apiCompiled;
        _apiPool = Channel.CreateBounded<InferRequest>(ApiParallelism);
        for (int i = 0; i < ApiParallelism; i++)
            _apiPool.Writer.TryWrite(apiCompiled.CreateInferRequest());

        // Số luồng song song: logic core / 2, min 1, max 8
        Parallelism = Math.Clamp(Environment.ProcessorCount / 2, 1, 8);
        ModelPath = path;

        // Query thiết bị thực tế — AUTO plugin có thể chọn CPU hoặc GPU tự động
        try
        {
            var props = _compiled.Properties;
            if (props.TryGetValue("EXECUTION_DEVICES", out var exec) && !string.IsNullOrWhiteSpace(exec))
                ActualDevice = device.Equals("AUTO", StringComparison.OrdinalIgnoreCase)
                    ? $"AUTO→{exec}" : exec;
            else
                ActualDevice = device;
        }
        catch { ActualDevice = device; }

        // ThreadLocal letterbox canvas — khởi tạo sau khi InputW/H đã xác định
        int canvasW = InputW, canvasH = InputH;
        _letterboxCanvas = new ThreadLocal<Bitmap>(
            () => new Bitmap(canvasW, canvasH, PixelFormat.Format24bppRgb),
            trackAllValues: true);

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
        return RunInfer(_reqPool.Value!, bmp, conf, iou, enabledClasses);
    }

    /// <summary>
    /// Detect dành riêng cho API — pool InferRequest tách biệt với batch pool.
    /// Nhiều API request đồng thời: mỗi request lấy 1 slot riêng, không tranh với batch.
    /// </summary>
    public async Task<List<DetectBox>> DetectApiAsync(
        Bitmap bmp, float conf, float iou, CancellationToken ct = default)
    {
        if (_apiPool is null) return [];
        // Lấy 1 InferRequest rảnh từ pool (chờ nếu tất cả đang bận)
        var req = await _apiPool.Reader.ReadAsync(ct);
        try   { return RunInfer(req, bmp, conf, iou, null); }
        finally { _apiPool.Writer.TryWrite(req); }   // trả lại pool
    }

    // ── Image preprocessing ───────────────────────────────────────────────

    // ThreadLocal canvas: mỗi thread reuse 1 Bitmap 640×640 — không alloc mỗi frame
    // Bitmap/Graphics không thread-safe nên phải ThreadLocal
    private ThreadLocal<Bitmap>? _letterboxCanvas;

    // Lõi inference — dùng chung cho cả batch (Detect) và API (DetectApiAsync)
    private List<DetectBox> RunInfer(
        InferRequest req, Bitmap bmp, float conf, float iou, int[]? enabledClasses)
    {
        int origW = bmp.Width, origH = bmp.Height;

        // Viết thẳng vào OpenVINO input tensor — bỏ float[] 4.9 MB trung gian
        Span<float> inputSpan = req.Inputs[0].GetData<float>();
        LetterboxToSpan(bmp, InputW, InputH, inputSpan,
            out float scale, out float padX, out float padY);

        req.Run();

        Span<float> outData  = req.Outputs[0].GetData<float>();
        var         outShape = req.Outputs[0].Shape;
        int numCh      = (int)outShape[1];
        int numAnchors = (int)outShape[2];

        return PostProcess.Decode(outData, numCh, numAnchors, conf, iou,
            origW, origH, InputW, InputH, scale, padX, padY, ClassNames, enabledClasses);
    }

    private void LetterboxToSpan(Bitmap src, int tW, int tH, Span<float> dst,
        out float scale, out float padX, out float padY)
    {
        float sw = (float)tW / src.Width;
        float sh = (float)tH / src.Height;
        scale = Math.Min(sw, sh);

        int nw = (int)Math.Round(src.Width  * scale);
        int nh = (int)Math.Round(src.Height * scale);
        padX = (tW - nw) / 2f;
        padY = (tH - nh) / 2f;

        // Reuse canvas per-thread — không alloc Bitmap mới mỗi frame
        var canvas = _letterboxCanvas!.Value!;
        using var g = Graphics.FromImage(canvas);
        g.Clear(Color.FromArgb(114, 114, 114));
        g.InterpolationMode = System.Drawing.Drawing2D.InterpolationMode.Bilinear;
        g.DrawImage(src, (int)padX, (int)padY, nw, nh);

        // Viết pixel thẳng vào dst span — không alloc float[]
        WriteBitmapToNCHW(canvas, tW, tH, dst);
    }

    private static unsafe void WriteBitmapToNCHW(Bitmap bmp, int w, int h, Span<float> dst)
    {
        var bits = bmp.LockBits(new Rectangle(0, 0, w, h),
            ImageLockMode.ReadOnly, PixelFormat.Format24bppRgb);

        byte* ptr    = (byte*)bits.Scan0;
        int   stride = bits.Stride;
        int   plane  = h * w;

        for (int y = 0; y < h; y++)
        {
            byte* row = ptr + y * stride;
            int   yOff = y * w;
            for (int x = 0; x < w; x++)
            {
                int i3 = x * 3;
                dst[0 * plane + yOff + x] = row[i3 + 2] / 255f; // R
                dst[1 * plane + yOff + x] = row[i3 + 1] / 255f; // G
                dst[2 * plane + yOff + x] = row[i3 + 0] / 255f; // B
            }
        }

        bmp.UnlockBits(bits);
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
        if (_apiPool is not null)
        {
            while (_apiPool.Reader.TryRead(out var r)) r.Dispose();
            _apiPool = null;
        }
        if (_letterboxCanvas is not null)
        {
            foreach (var bmp in _letterboxCanvas.Values) bmp?.Dispose();
            _letterboxCanvas.Dispose();
            _letterboxCanvas = null;
        }
        _compiled?.Dispose();
        _apiCompiled?.Dispose();
        _core?.Dispose();
        _compiled = null; _apiCompiled = null; _core = null;
    }

    public void Dispose() => DisposeModel();
}
