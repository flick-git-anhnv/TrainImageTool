using System.Drawing.Imaging;
using System.Runtime.InteropServices;
using System.Threading.Channels;
using SlotMonitor.Models;
using Sdcb.OpenVINO;

namespace SlotMonitor.Inference;

/// <summary>
/// Wrapper OpenVINO inference cho YOLO.
/// Thread-safe: mỗi thread có InferRequest riêng (ThreadLocal pool).
/// Hỗ trợ ONNX (.onnx) và OpenVINO IR (.xml + .bin).
/// </summary>
public sealed class YoloRunner : IDisposable
{
    private OVCore?        _core;
    private CompiledModel? _compiled;
    private CompiledModel? _apiCompiled;
    private ThreadLocal<InferRequest>? _reqPool;
    private Channel<InferRequest>?     _apiPool;
    private ThreadLocal<Bitmap>?       _letterboxCanvas;

    public int     ApiParallelism     { get; private set; } = 2;
    public bool    IsLoaded           => _compiled is not null;
    public string  ModelPath          { get; private set; } = "";
    public string  ActualDevice       { get; private set; } = "";
    public int     InputW             { get; private set; } = 640;
    public int     InputH             { get; private set; } = 640;
    public int     NumClasses         { get; private set;  } = 1;
    public string[] ClassNames        { get; set;          } = [];
    public int     Parallelism        { get; private set; } = 1;
    /// <summary>Shape info của output lần detect gần nhất — dùng để debug.</summary>
    public string  LastOutputShapeInfo { get; private set; } = "";

    // ── Load ──────────────────────────────────────────────────────────────

    /// <summary>Load model. Chấp nhận file .onnx, file .xml, hoặc folder chứa .xml.</summary>
    public void LoadModel(string path, string device = "CPU")
    {
        if (Directory.Exists(path))
        {
            var xmlFiles = Directory.GetFiles(path, "*.xml");
            if (xmlFiles.Length == 0)
                throw new FileNotFoundException($"Không tìm thấy file .xml trong:\n{path}");
            path = xmlFiles[0];
        }

        DisposeModel();
        _core = new OVCore();

        var cacheDir = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
            "KZTEK", "SlotMonitor", "model_cache");
        Directory.CreateDirectory(cacheDir);
        _core.SetDeviceProperty("", PropertyKeys.CacheDir, cacheDir);

        Model model;
        if (path.EndsWith(".xml", StringComparison.OrdinalIgnoreCase))
        {
            var bin = Path.ChangeExtension(path, ".bin");
            if (!File.Exists(bin))
                throw new FileNotFoundException($"Không tìm thấy file .bin:\n{bin}");
            model = _core.ReadModel(path, bin);
        }
        else model = _core.ReadModel(path);

        using (model)
        {
            try
            {
                var shape = model.Inputs[0].Shape;
                InputH = shape.Rank >= 3 ? (int)shape[2] : 640;
                InputW = shape.Rank >= 4 ? (int)shape[3] : 640;
                if (InputH <= 0) InputH = 640;
                if (InputW <= 0) InputW = 640;
            }
            catch { InputH = InputW = 640; }

            int  total = Environment.ProcessorCount;
            bool isCpu = device.Equals("CPU", StringComparison.OrdinalIgnoreCase);

            var batchOpts = new DeviceOptions(device) { PerformanceMode = PerformanceMode.Throughput };
            if (isCpu) batchOpts.InferenceNumThreads = Math.Max(1, total * 3 / 4);
            _compiled = _core.CompileModel(model, batchOpts);

            var apiOpts = new DeviceOptions(device) { PerformanceMode = PerformanceMode.Latency };
            if (isCpu) apiOpts.InferenceNumThreads = Math.Max(2, total / 4);
            _apiCompiled = _core.CompileModel(model, apiOpts);

            try
            {
                var outShape = _compiled.Outputs[0].Shape;
                int d1 = outShape.Rank >= 2 ? (int)outShape[outShape.Rank >= 3 ? 1 : 0] : -1;
                int d2 = outShape.Rank >= 2 ? (int)outShape[outShape.Rank >= 3 ? 2 : 1] : -1;
                int ch = (d1 > 0 && d2 > 0) ? Math.Min(d1, d2) : 5;
                NumClasses = Math.Max(1, ch - 4);
            }
            catch { NumClasses = 1; }
        }

        var compiled = _compiled;
        _reqPool = new ThreadLocal<InferRequest>(
            () => compiled.CreateInferRequest(), trackAllValues: true);

        ApiParallelism = Math.Clamp(Environment.ProcessorCount / 4, 1, 4);
        var apiCompiled = _apiCompiled;
        _apiPool = Channel.CreateBounded<InferRequest>(ApiParallelism);
        for (int i = 0; i < ApiParallelism; i++)
            _apiPool.Writer.TryWrite(apiCompiled.CreateInferRequest());

        Parallelism = Math.Clamp(Environment.ProcessorCount / 2, 1, 8);
        ModelPath   = path;

        try
        {
            var props = _compiled.Properties;
            if (props.TryGetValue("EXECUTION_DEVICES", out var exec) && !string.IsNullOrWhiteSpace(exec))
                ActualDevice = device.Equals("AUTO", StringComparison.OrdinalIgnoreCase)
                    ? $"AUTO→{exec}" : exec;
            else ActualDevice = device;
        }
        catch { ActualDevice = device; }

        int cW = InputW, cH = InputH;
        _letterboxCanvas = new ThreadLocal<Bitmap>(
            () => new Bitmap(cW, cH, PixelFormat.Format24bppRgb), trackAllValues: true);

        if (!TryAutoLoadYaml(path) || ClassNames.Length != NumClasses)
            ClassNames = Enumerable.Range(0, NumClasses).Select(i => $"cls{i}").ToArray();
    }

    // ── Inference ─────────────────────────────────────────────────────────

    public List<DetectBox> Detect(Bitmap bmp, float conf, float iou, int[]? enabledClasses = null)
    {
        if (_reqPool is null) return [];
        return RunInfer(_reqPool.Value!, bmp, conf, iou, enabledClasses);
    }

    public async Task<List<DetectBox>> DetectApiAsync(
        Bitmap bmp, float conf, float iou, CancellationToken ct = default)
    {
        if (_apiPool is null) return [];
        var req = await _apiPool.Reader.ReadAsync(ct);
        try   { return RunInfer(req, bmp, conf, iou, null); }
        finally { _apiPool.Writer.TryWrite(req); }
    }

    private List<DetectBox> RunInfer(
        InferRequest req, Bitmap bmp, float conf, float iou, int[]? enabledClasses)
    {
        int origW = bmp.Width, origH = bmp.Height;
        Span<float> inputSpan = req.Inputs[0].GetData<float>();
        LetterboxToSpan(bmp, InputW, InputH, inputSpan, out float scale, out float padX, out float padY);
        req.Run();

        // ── Kiểm tra số output của model ─────────────────────────────────
        int numOutputs = req.Outputs.Count;

        Span<float> outData  = req.Outputs[0].GetData<float>();
        var         outShape = req.Outputs[0].Shape;

        int numCh, numAnchors;
        if (outShape.Rank >= 3)
        {
            int d1 = (int)outShape[1], d2 = (int)outShape[2];
            if (d1 < d2) { numCh = d1; numAnchors = d2; }
            else         { numCh = d2; numAnchors = d1; }
        }
        else if (outShape.Rank == 2)
        {
            int d0 = (int)outShape[0], d1 = (int)outShape[1];
            if (d0 < d1) { numCh = d0; numAnchors = d1; }
            else         { numCh = d1; numAnchors = d0; }
        }
        else return [];

        // Model có 2 output riêng: [bbox: 4ch] + [class scores: nCls ch]
        // Ví dụ YOLOv8 export với separate heads: out0=[1,4,N], out1=[1,nc,N]
        if (numCh == 4 && numOutputs >= 2)
        {
            var clsShape = req.Outputs[1].Shape;
            int clsCh = 0, clsAnchors = 0;
            if (clsShape.Rank >= 3)
            {
                int c1 = (int)clsShape[1], c2 = (int)clsShape[2];
                if (c1 < c2) { clsCh = c1; clsAnchors = c2; }
                else         { clsCh = c2; clsAnchors = c1; }
            }
            else if (clsShape.Rank == 2)
            {
                int c0 = (int)clsShape[0], c1 = (int)clsShape[1];
                if (c0 < c1) { clsCh = c0; clsAnchors = c1; }
                else         { clsCh = c1; clsAnchors = c0; }
            }

            if (clsCh > 0 && clsAnchors == numAnchors)
            {
                // Ghép bbox + class thành tensor [4+nc, N]
                Span<float> clsData  = req.Outputs[1].GetData<float>();
                int         total    = (4 + clsCh) * numAnchors;
                var         combined = new float[total];
                outData[..(4 * numAnchors)].CopyTo(combined);
                clsData[..(clsCh * numAnchors)].CopyTo(
                    combined.AsSpan(4 * numAnchors));
                NumClasses = clsCh;
                if (ClassNames.Length != NumClasses)
                    ClassNames = Enumerable.Range(0, NumClasses).Select(i => $"cls{i}").ToArray();
                return PostProcess.Decode(combined, 4 + clsCh, numAnchors, conf, iou,
                    origW, origH, InputW, InputH, scale, padX, padY, ClassNames, enabledClasses);
            }
        }

        // Lưu thông tin shape để debug
        LastOutputShapeInfo =
            $"{numOutputs} output(s) | out0: [{string.Join(",", Enumerable.Range(0, outShape.Rank).Select(i => outShape[i]))}] → numCh={numCh} numAnchors={numAnchors}";

        if (numCh <= 4 || numAnchors <= 0) return [];
        return PostProcess.Decode(outData, numCh, numAnchors, conf, iou,
            origW, origH, InputW, InputH, scale, padX, padY, ClassNames, enabledClasses);
    }

    private void LetterboxToSpan(Bitmap src, int tW, int tH, Span<float> dst,
        out float scale, out float padX, out float padY)
    {
        scale = Math.Min((float)tW / src.Width, (float)tH / src.Height);
        int nw = (int)Math.Round(src.Width  * scale);
        int nh = (int)Math.Round(src.Height * scale);
        padX = (tW - nw) / 2f;
        padY = (tH - nh) / 2f;

        var canvas = _letterboxCanvas!.Value!;
        using var g = Graphics.FromImage(canvas);
        g.Clear(Color.FromArgb(114, 114, 114));
        g.InterpolationMode = System.Drawing.Drawing2D.InterpolationMode.Bilinear;
        g.DrawImage(src, (int)padX, (int)padY, nw, nh);
        WriteBitmapToNCHW(canvas, tW, tH, dst);
    }

    private static unsafe void WriteBitmapToNCHW(Bitmap bmp, int w, int h, Span<float> dst)
    {
        var bits   = bmp.LockBits(new Rectangle(0, 0, w, h),
                        ImageLockMode.ReadOnly, PixelFormat.Format24bppRgb);
        byte* ptr  = (byte*)bits.Scan0;
        int stride = bits.Stride, plane = h * w;
        for (int y = 0; y < h; y++)
        {
            byte* row = ptr + y * stride;
            int   yo  = y * w;
            for (int x = 0; x < w; x++)
            {
                int i3 = x * 3;
                dst[0 * plane + yo + x] = row[i3 + 2] / 255f;
                dst[1 * plane + yo + x] = row[i3 + 1] / 255f;
                dst[2 * plane + yo + x] = row[i3 + 0] / 255f;
            }
        }
        bmp.UnlockBits(bits);
    }

    // ── YAML ──────────────────────────────────────────────────────────────

    public static string[] LoadClassNamesFromYaml(string yamlPath)
    {
        var lines = File.ReadAllLines(yamlPath);
        bool inNames = false;
        var dict = new SortedDictionary<int, string>();
        var list = new List<string>();

        foreach (var line in lines)
        {
            if (line.TrimStart().StartsWith("names:", StringComparison.Ordinal))
            {
                int s = line.IndexOf('['), e = line.LastIndexOf(']');
                if (s >= 0 && e > s)
                {
                    list.AddRange(line[(s + 1)..e]
                        .Split(',').Select(x => x.Trim().Trim('\'', '"')).Where(x => x.Length > 0));
                    break;
                }
                inNames = true; continue;
            }
            if (inNames)
            {
                var t = line.TrimStart();
                if (string.IsNullOrWhiteSpace(t)) continue;
                int ci = t.IndexOf(':');
                if (ci > 0 && int.TryParse(t[..ci].Trim(), out int id))
                { dict[id] = t[(ci + 1)..].Trim().Trim('\'', '"'); continue; }
                if (t.StartsWith('-'))
                { list.Add(t.TrimStart('-').Trim().Trim('\'', '"')); continue; }
                break;
            }
        }
        if (dict.Count > 0) return dict.Values.ToArray();
        return list.Count > 0 ? list.ToArray() : [];
    }

    public bool TryAutoLoadYaml(string modelFolderOrFile)
    {
        var dir = Directory.Exists(modelFolderOrFile)
            ? modelFolderOrFile : Path.GetDirectoryName(modelFolderOrFile) ?? "";
        var candidate = new[] { "metadata.yaml", "data.yaml" }
            .Select(f => Path.Combine(dir, f))
            .Concat(Directory.Exists(dir) ? Directory.GetFiles(dir, "*.yaml") : [])
            .Distinct().FirstOrDefault(File.Exists);
        if (candidate is null) return false;
        try { var n = LoadClassNamesFromYaml(candidate); if (n.Length > 0) { ClassNames = n; return true; } }
        catch { }
        return false;
    }

    // ── Dispose ───────────────────────────────────────────────────────────

    private void DisposeModel()
    {
        if (_reqPool is not null)
        {
            foreach (var r in _reqPool.Values) r?.Dispose();
            _reqPool.Dispose(); _reqPool = null;
        }
        if (_apiPool is not null)
        {
            while (_apiPool.Reader.TryRead(out var r)) r.Dispose();
            _apiPool = null;
        }
        if (_letterboxCanvas is not null)
        {
            foreach (var b in _letterboxCanvas.Values) b?.Dispose();
            _letterboxCanvas.Dispose(); _letterboxCanvas = null;
        }
        _compiled?.Dispose(); _apiCompiled?.Dispose(); _core?.Dispose();
        _compiled = null; _apiCompiled = null; _core = null;
    }

    public void Dispose() => DisposeModel();
}
