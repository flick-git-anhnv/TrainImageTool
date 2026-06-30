using System.Drawing.Imaging;
using ClsTester.Models;
using Sdcb.OpenVINO;

namespace ClsTester.Inference;

/// <summary>
/// Wrapper OpenVINO inference cho YOLO Classify (và detect-on-crop fallback).
///
/// Hỗ trợ:
///   • YOLO classify ONNX/IR: output [1, nc] — softmax đã áp dụng
///   • YOLO detect  ONNX/IR: output [1, nc+4, N] — chạy trên crop, gom score
///
/// Thread-safe: mỗi thread có InferRequest riêng (ThreadLocal pool).
/// </summary>
public sealed class ClassifierRunner : IDisposable
{
    // ── Internal ──────────────────────────────────────────────────────────
    private OVCore?        _core;
    private CompiledModel? _compiled;
    private ThreadLocal<InferRequest>? _reqPool;
    private ThreadLocal<Bitmap>?       _resizeCanvas;

    // ── Public props ──────────────────────────────────────────────────────
    public bool     IsLoaded     => _compiled is not null;
    public string   ModelPath    { get; private set; } = "";
    public string   ActualDevice { get; private set; } = "";
    public int      InputW       { get; private set; } = 224;
    public int      InputH       { get; private set; } = 224;
    public int      NumClasses   { get; private set; } = 1;
    public string[] ClassNames   { get; set; } = [];
    public string   ModelInfo    { get; private set; } = "";

    public enum ModelKind { Classify, Detect }
    public ModelKind Kind { get; private set; } = ModelKind.Classify;

    // ══════════════════════════════════════════════════════════════════════
    // LOAD
    // ══════════════════════════════════════════════════════════════════════

    /// <summary>Load model. Nhận file .onnx, file .xml, hoặc folder chứa .xml.</summary>
    public void LoadModel(string path, string device = "CPU")
    {
        if (Directory.Exists(path))
        {
            var xmlFiles = Directory.GetFiles(path, "*.xml");
            if (xmlFiles.Length == 0)
                throw new FileNotFoundException($"Không tìm thấy .xml trong:\n{path}");
            path = xmlFiles[0];
        }

        DisposeModel();
        _core = new OVCore();

        var cacheDir = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
            "KZTEK", "ClsTester", "model_cache");
        Directory.CreateDirectory(cacheDir);
        _core.SetDeviceProperty("", PropertyKeys.CacheDir, cacheDir);

        Model model;
        if (path.EndsWith(".xml", StringComparison.OrdinalIgnoreCase))
        {
            var bin = Path.ChangeExtension(path, ".bin");
            if (!File.Exists(bin))
                throw new FileNotFoundException($"Thiếu file .bin:\n{bin}");
            model = _core.ReadModel(path, bin);
        }
        else model = _core.ReadModel(path);

        using (model)
        {
            // ── Input shape ───────────────────────────────────────────────
            try
            {
                var shape = model.Inputs[0].Shape;
                InputH = shape.Rank >= 3 ? (int)shape[shape.Rank >= 4 ? 2 : 1] : 224;
                InputW = shape.Rank >= 4 ? (int)shape[3] : 224;
                if (InputH <= 0) InputH = 224;
                if (InputW <= 0) InputW = 224;
            }
            catch { InputH = InputW = 224; }

            // ── Detect output type ────────────────────────────────────────
            try
            {
                var outShape = model.Outputs[0].Shape;
                if (outShape.Rank == 2)
                {
                    // [batch, nc] — classify
                    NumClasses = Math.Max(1, (int)outShape[1]);
                    Kind       = ModelKind.Classify;
                }
                else if (outShape.Rank >= 3)
                {
                    // [1, ch, N] — detect
                    int d1 = (int)outShape[1], d2 = (int)outShape[2];
                    int minD = Math.Min(d1, d2);
                    NumClasses = Math.Max(1, minD - 4);
                    Kind       = ModelKind.Detect;
                }
            }
            catch { NumClasses = 1; Kind = ModelKind.Classify; }

            var opts = new DeviceOptions(device) { PerformanceMode = PerformanceMode.Latency };
            _compiled = _core.CompileModel(model, opts);
        }

        var compiled = _compiled;
        _reqPool = new ThreadLocal<InferRequest>(
            () => compiled.CreateInferRequest(), trackAllValues: true);

        int cW = InputW, cH = InputH;
        _resizeCanvas = new ThreadLocal<Bitmap>(
            () => new Bitmap(cW, cH, PixelFormat.Format24bppRgb), trackAllValues: true);

        ModelPath    = path;
        ActualDevice = device;

        // Auto-load class names
        if (!TryAutoLoadYaml(path) || ClassNames.Length != NumClasses)
            ClassNames = Enumerable.Range(0, NumClasses).Select(i => $"cls{i}").ToArray();

        var names5 = string.Join(", ", ClassNames.Take(5));
        if (ClassNames.Length > 5) names5 += "…";
        ModelInfo = $"{Path.GetFileName(path)}  │  {InputW}×{InputH}  │  {NumClasses} class  │  [{Kind}]  │  [{device}]  │  [{names5}]";
    }

    // ══════════════════════════════════════════════════════════════════════
    // CLASSIFY
    // ══════════════════════════════════════════════════════════════════════

    /// <summary>Phân loại ảnh crop, trả về Top-N kết quả. Thread-safe.</summary>
    public List<ClsTopItem> Classify(Bitmap bmp, int topN = 5)
    {
        if (_reqPool is null) return [];
        return RunInfer(_reqPool.Value!, bmp, topN);
    }

    private List<ClsTopItem> RunInfer(InferRequest req, Bitmap bmp, int topN)
    {
        Span<float> inp = req.Inputs[0].GetData<float>();
        LetterboxToSpan(bmp, InputW, InputH, inp);
        req.Run();

        if (Kind == ModelKind.Classify)
        {
            Span<float> out0 = req.Outputs[0].GetData<float>();
            return ExtractTopN(out0, topN);
        }
        else
        {
            // Detect model trên crop — gom class score cao nhất ở mỗi anchor
            Span<float> out0     = req.Outputs[0].GetData<float>();
            var         outShape = req.Outputs[0].Shape;
            int numAnchors = outShape.Rank >= 3 ? (int)outShape[2] : 1;
            int nc         = NumClasses;
            var scores     = new float[nc];

            for (int a = 0; a < numAnchors; a++)
            {
                float best = 0f; int bestCls = 0;
                for (int c = 0; c < nc; c++)
                {
                    float s = out0[(4 + c) * numAnchors + a];
                    if (s > best) { best = s; bestCls = c; }
                }
                if (best > 0.05f) scores[bestCls] += best;
            }

            float sum = scores.Sum();
            if (sum > 0f) for (int i = 0; i < nc; i++) scores[i] /= sum;
            return ExtractTopN(scores, topN);
        }
    }

    private List<ClsTopItem> ExtractTopN(Span<float> probs, int topN)
    {
        int nc = probs.Length;
        // Copy to array to avoid Span<float> capture in LINQ
        var arr = probs.ToArray();
        var result = new List<ClsTopItem>(Math.Min(topN, nc));
        foreach (int i in Enumerable.Range(0, nc).OrderByDescending(i => arr[i]).Take(topN))
        {
            var name = i < ClassNames.Length ? ClassNames[i] : $"cls{i}";
            result.Add(new ClsTopItem(name, i, arr[i]));
        }
        return result;
    }

    // ── Letterbox ─────────────────────────────────────────────────────────

    private void LetterboxToSpan(Bitmap src, int tW, int tH, Span<float> dst)
    {
        var canvas = _resizeCanvas!.Value!;
        using var g = Graphics.FromImage(canvas);
        g.Clear(Color.FromArgb(128, 128, 128));
        g.InterpolationMode = System.Drawing.Drawing2D.InterpolationMode.Bilinear;

        float scale = Math.Min((float)tW / src.Width, (float)tH / src.Height);
        int nw = (int)(src.Width * scale), nh = (int)(src.Height * scale);
        g.DrawImage(src, (tW - nw) / 2, (tH - nh) / 2, nw, nh);

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
                dst[0 * plane + yo + x] = row[i3 + 2] / 255f; // R
                dst[1 * plane + yo + x] = row[i3 + 1] / 255f; // G
                dst[2 * plane + yo + x] = row[i3 + 0] / 255f; // B
            }
        }
        bmp.UnlockBits(bits);
    }

    // ── YAML ──────────────────────────────────────────────────────────────

    public bool TryAutoLoadYaml(string path)
    {
        var dir = Directory.Exists(path) ? path : Path.GetDirectoryName(path) ?? "";
        if (!Directory.Exists(dir)) return false;

        var candidate = new[] { "metadata.yaml", "data.yaml" }
            .Select(f => Path.Combine(dir, f))
            .Concat(Directory.GetFiles(dir, "*.yaml"))
            .Distinct()
            .FirstOrDefault(File.Exists);

        if (candidate is null) return false;
        try
        {
            var names = LoadYamlNames(candidate);
            if (names.Length > 0) { ClassNames = names; return true; }
        }
        catch { }
        return false;
    }

    public static string[] LoadYamlNames(string yamlPath)
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

    // ── Dispose ───────────────────────────────────────────────────────────

    private void DisposeModel()
    {
        if (_reqPool is not null)
        {
            foreach (var r in _reqPool.Values) r?.Dispose();
            _reqPool.Dispose(); _reqPool = null;
        }
        if (_resizeCanvas is not null)
        {
            foreach (var b in _resizeCanvas.Values) b?.Dispose();
            _resizeCanvas.Dispose(); _resizeCanvas = null;
        }
        _compiled?.Dispose(); _core?.Dispose();
        _compiled = null; _core = null;
    }

    public void Dispose() => DisposeModel();
}
