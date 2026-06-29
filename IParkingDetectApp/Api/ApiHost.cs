using System.Diagnostics;
using System.Text.Json;
using IParkingDetect.Inference;
using IParkingDetect.Models;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.Logging;

namespace IParkingDetect.Api;

/// <summary>
/// Self-hosted Kestrel API — xử lý request song song thực sự (thread pool).
///
/// Endpoints:
///   GET  /status                 → thông tin model
///   GET  /detect?path=...        → detect từ path file
///   POST /detect  (form-data, x-www-form-urlencoded, json, raw text)
///
/// Form-data hỗ trợ cả text field "path" (đường dẫn) và file upload (bytes ảnh).
/// </summary>
public sealed class ApiHost : IDisposable
{
    private readonly YoloRunner  _yolo;
    private readonly Func<float> _getConf;
    private readonly Func<float> _getIou;
    private WebApplication?      _app;

    public bool IsRunning { get; private set; }
    public int  Port      { get; private set; }

    public event Action<ApiLogEntry>? OnLog;

    private static readonly JsonSerializerOptions _jsonOpts = new()
    {
        WriteIndented        = false,
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
    };

    public ApiHost(YoloRunner yolo, int port, Func<float> getConf, Func<float> getIou)
    {
        _yolo    = yolo;
        Port     = port;
        _getConf = getConf;
        _getIou  = getIou;
    }

    // ── Start / Stop ──────────────────────────────────────────────────────

    public void Start(int port)
    {
        if (IsRunning) Stop();
        Port = port;

        var builder = WebApplication.CreateBuilder(Array.Empty<string>());

        // Kestrel bind mọi interface → máy khác gọi được
        builder.WebHost.ConfigureKestrel(k => k.ListenAnyIP(port));

        // Tắt toàn bộ console log của ASP.NET Core
        builder.Logging.ClearProviders();

        _app = builder.Build();

        // CORS
        _app.Use(async (ctx, next) =>
        {
            ctx.Response.Headers["Access-Control-Allow-Origin"]  = "*";
            ctx.Response.Headers["Access-Control-Allow-Headers"] = "Content-Type";
            if (ctx.Request.Method == "OPTIONS") { ctx.Response.StatusCode = 204; return; }
            await next();
        });

        _app.MapGet("/",        HandleStatus);
        _app.MapGet("/status",  HandleStatus);
        _app.MapGet("/detect",  HandleDetect);
        _app.MapPost("/detect", HandleDetect);

        _ = _app.StartAsync();   // non-blocking — Kestrel chạy trên thread pool
        IsRunning = true;
    }

    public void Stop()
    {
        if (_app is null) return;
        using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(3));
        try { _app.StopAsync(cts.Token).GetAwaiter().GetResult(); } catch { }
        try { _app.DisposeAsync().AsTask().Wait(2000); } catch { }
        _app      = null;
        IsRunning = false;
    }

    // ── Handlers ─────────────────────────────────────────────────────────

    private Task HandleStatus(HttpContext ctx) =>
        WriteJson(ctx, 200, new
        {
            status       = "running",
            model        = _yolo.IsLoaded ? Path.GetFileName(_yolo.ModelPath) : null,
            model_loaded = _yolo.IsLoaded,
            classes      = _yolo.IsLoaded ? _yolo.ClassNames : null,
            endpoint     = $"http://{ctx.Request.Host}/detect",
        });

    private async Task HandleDetect(HttpContext ctx)
    {
        var receivedAt = DateTimeOffset.Now;
        var swTotal    = Stopwatch.StartNew();
        var req        = ctx.Request;

        string? filePath         = null;
        byte[]? uploadedBytes    = null;
        string? uploadedFileName = null;
        float   conf             = _getConf();
        float   iou              = _getIou();

        // ── Parse request ─────────────────────────────────────────────────

        if (req.Method == "GET")
        {
            filePath = Blank(req.Query["path"]);
            if (float.TryParse(req.Query["conf"], out var c)) conf = c;
            if (float.TryParse(req.Query["iou"],  out var u)) iou  = u;
        }
        else
        {
            var ct = req.ContentType ?? "";

            if (ct.StartsWith("multipart/form-data",               StringComparison.OrdinalIgnoreCase) ||
                ct.StartsWith("application/x-www-form-urlencoded", StringComparison.OrdinalIgnoreCase))
            {
                // ASP.NET Core tự parse form — kể cả multipart/file upload
                var form = await req.ReadFormAsync();
                filePath = Blank(form["path"].ToString());
                if (float.TryParse(form["conf"], out var c)) conf = c;
                if (float.TryParse(form["iou"],  out var u)) iou  = u;

                // File upload: field "path" dạng File, hoặc field "image"/"file"
                var file = form.Files["path"]
                        ?? form.Files["image"]
                        ?? form.Files["file"]
                        ?? form.Files.FirstOrDefault();
                if (file is not null)
                {
                    // Zero-copy: đọc thẳng vào 1 buffer, không double-copy qua MemoryStream.ToArray()
                    uploadedBytes    = new byte[file.Length];
                    await file.OpenReadStream().ReadExactlyAsync(uploadedBytes);
                    uploadedFileName = file.FileName;
                    filePath         = null;   // file upload được ưu tiên hơn text path
                }
            }
            else if (ct.StartsWith("application/json", StringComparison.OrdinalIgnoreCase))
            {
                try
                {
                    using var doc = await JsonDocument.ParseAsync(req.Body);
                    if (doc.RootElement.TryGetProperty("path", out var p))  filePath = p.GetString();
                    if (doc.RootElement.TryGetProperty("conf", out var cv)) conf = cv.GetSingle();
                    if (doc.RootElement.TryGetProperty("iou",  out var uv)) iou  = uv.GetSingle();
                }
                catch { await WriteErr(ctx, 400, "Invalid JSON body", receivedAt); return; }
            }
            else
            {
                using var reader = new StreamReader(req.Body);
                filePath = Blank(await reader.ReadToEndAsync());
            }
        }

        if (filePath is null && uploadedBytes is null)
        { await WriteErr(ctx, 400, "Missing 'path' parameter or file upload.", receivedAt); return; }

        // ── Log + validate ────────────────────────────────────────────────

        var imgName = uploadedFileName ?? (filePath is not null ? Path.GetFileName(filePath) : "");
        var logPath = filePath ?? $"(upload:{uploadedFileName})";
        var logId   = Guid.NewGuid();
        OnLog?.Invoke(new ApiLogEntry(logId, imgName, logPath, receivedAt, ApiLogStatus.Processing));

        if (uploadedBytes is null && !File.Exists(filePath!))
        {
            swTotal.Stop();
            OnLog?.Invoke(new ApiLogEntry(logId, imgName, logPath, receivedAt,
                ApiLogStatus.Error, null, swTotal.ElapsedMilliseconds, "File not found"));
            await WriteErr(ctx, 400, $"File not found: {filePath}", receivedAt); return;
        }

        if (!_yolo.IsLoaded)
        {
            swTotal.Stop();
            OnLog?.Invoke(new ApiLogEntry(logId, imgName, logPath, receivedAt,
                ApiLogStatus.Error, null, swTotal.ElapsedMilliseconds, "Model not loaded"));
            await WriteErr(ctx, 503, "Model not loaded. Load a model in the app first.", receivedAt); return;
        }

        // ── Inference ─────────────────────────────────────────────────────

        var swInfer = Stopwatch.StartNew();
        List<DetectBox> boxes;
        try
        {
            if (uploadedBytes is not null)
            {
                // File upload: tạo Bitmap thẳng từ bytes, không lưu disk
                using var imgStream = new MemoryStream(uploadedBytes);
                using var bmp = new System.Drawing.Bitmap(imgStream);
                boxes = await _yolo.DetectApiAsync(bmp, conf, iou, ctx.RequestAborted);
            }
            else
            {
                using var bmp = new System.Drawing.Bitmap(filePath!);
                boxes = await _yolo.DetectApiAsync(bmp, conf, iou, ctx.RequestAborted);
            }
        }
        catch (Exception ex)
        {
            swTotal.Stop();
            OnLog?.Invoke(new ApiLogEntry(logId, imgName, logPath, receivedAt,
                ApiLogStatus.Error, null, swTotal.ElapsedMilliseconds, ex.Message));
            await WriteErr(ctx, 500, $"Inference error: {ex.Message}", receivedAt); return;
        }
        swInfer.Stop();
        swTotal.Stop();

        OnLog?.Invoke(new ApiLogEntry(logId, imgName, logPath, receivedAt,
            ApiLogStatus.Done, swInfer.ElapsedMilliseconds, swTotal.ElapsedMilliseconds));

        await WriteJson(ctx, 200, new
        {
            received_at = receivedAt.ToString("O"),
            infer_ms    = swInfer.ElapsedMilliseconds,
            total_ms    = swTotal.ElapsedMilliseconds,
            path        = logPath,
            conf        = Math.Round(conf, 4),
            iou         = Math.Round(iou,  4),
            count       = boxes.Count,
            boxes       = boxes.Select(b => new
            {
                class_id   = b.ClassId,
                class_name = b.ClassName,
                confidence = Math.Round(b.Confidence, 4),
                x1 = Math.Round(b.X1, 1),
                y1 = Math.Round(b.Y1, 1),
                x2 = Math.Round(b.X2, 1),
                y2 = Math.Round(b.Y2, 1),
                w  = Math.Round(b.Width,  1),
                h  = Math.Round(b.Height, 1),
            }),
        });
    }

    // ── Helpers ───────────────────────────────────────────────────────────

    private Task WriteJson(HttpContext ctx, int code, object obj)
    {
        ctx.Response.StatusCode  = code;
        ctx.Response.ContentType = "application/json; charset=utf-8";
        var json = JsonSerializer.Serialize(obj, _jsonOpts);
        return ctx.Response.WriteAsync(json);
    }

    private Task WriteErr(HttpContext ctx, int code, string msg, DateTimeOffset receivedAt) =>
        WriteJson(ctx, code, new { error = msg, received_at = receivedAt.ToString("O") });

    private static string? Blank(string? s) =>
        string.IsNullOrWhiteSpace(s) ? null : s;

    public void Dispose() => Stop();
}
