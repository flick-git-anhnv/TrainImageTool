using System.Collections.Concurrent;
using System.Drawing.Imaging;
using System.Text.Json;
using ClsTester.Data;
using ClsTester.Inference;
using ClsTester.Models;
using OpenCvSharp;

namespace ClsTester.Workers;

/// <summary>
/// Worker RTSP → classify mỗi bbox region → emit sự kiện thay đổi.
///
/// Vòng lặp:
///   1. Đọc frame liên tục từ RTSP (camera hoặc file video).
///   2. Cập nhật _frame (preview UI 200 ms).
///   3. Cứ mỗi IntervalMs: crop từng region → classify → detect thay đổi class.
///   4. Khi class thay đổi: lưu DB + enqueue event → UI đọc qua timer.
/// </summary>
public sealed class StreamWorker : IDisposable
{
    private readonly ClassifierRunner _runner;
    private readonly AppSettings      _cfg;
    private readonly ClsDb            _db;
    private readonly CameraConfig     _cam;

    private CancellationTokenSource? _cts;
    private Task?                    _task;
    private volatile bool            _inferActive = true;

    // prevClass tồn tại xuyên suốt reconnect (field, không phải local)
    private readonly Dictionary<string, string> _prevClass = [];

    // ── Current frame ─────────────────────────────────────────────────────
    private readonly object _frameLock = new();
    private Bitmap? _frame;

    // ── Per-region state & crop ────────────────────────────────────────────
    private readonly object _stateLock = new();
    private readonly Dictionary<string, RegionClsState> _states = [];
    private readonly Dictionary<string, Bitmap?>        _crops  = [];

    // ── Events → UI ──────────────────────────────────────────────────────
    public ConcurrentQueue<ClsChangeRecord> Events { get; } = new();

    // ── Status props ──────────────────────────────────────────────────────
    public string     CameraId   => _cam.Id;
    public string     CameraName => _cam.Name;
    public bool       IsRunning  => _task is { IsCompleted: false };
    public string     StatusMsg  { get; private set; } = "Chưa khởi động";
    public long       LastInferMs { get; private set; }
    public int        FrameCount  { get; private set; }

    public StreamWorker(ClassifierRunner runner, AppSettings cfg, ClsDb db, CameraConfig cam)
    {
        _runner = runner; _cfg = cfg; _db = db; _cam = cam;
    }

    // ── Control ───────────────────────────────────────────────────────────

    public void Start()
    {
        if (IsRunning) return;
        _inferActive = true;
        _cts  = new CancellationTokenSource();
        _task = Task.Run(() => RunLoop(_cts.Token));
    }

    public void Stop()
    {
        _inferActive = false;   // dừng inference ngay lập tức
        _cts?.Cancel();
        StatusMsg = "Đã dừng";
    }

    // ── Thread-safe getters for UI ────────────────────────────────────────

    public Bitmap? GetFrameClone()
    {
        lock (_frameLock) return _frame is null ? null : (Bitmap)_frame.Clone();
    }

    public List<RegionClsState> GetStates()
    {
        lock (_stateLock)
            return _states.Values.Select(s => new RegionClsState
            {
                RegionId   = s.RegionId,   RegionName = s.RegionName,
                ClassName  = s.ClassName,  ClassId    = s.ClassId,
                Conf       = s.Conf,       TopN       = [.. s.TopN],
                UpdatedAt  = s.UpdatedAt,
            }).ToList();
    }

    public Bitmap? GetCropClone(string regionId)
    {
        lock (_stateLock)
            return _crops.TryGetValue(regionId, out var b) && b is not null
                ? (Bitmap)b.Clone() : null;
    }

    // ═══════════════════════════════════════════════════════════════════════
    // MAIN LOOP
    // ═══════════════════════════════════════════════════════════════════════

    private async Task RunLoop(CancellationToken ct)
    {
        StatusMsg = "Đang kết nối…";
        while (!ct.IsCancellationRequested)
        {
            try    { await ConnectAndProcess(ct); }
            catch (OperationCanceledException) { break; }
            catch (Exception ex)
            {
                StatusMsg = $"Lỗi: {ex.Message[..Math.Min(60, ex.Message.Length)]}";
                try { await Task.Delay(5_000, ct); } catch { break; }
            }
        }
        StatusMsg = "Đã dừng";
    }

    private async Task ConnectAndProcess(CancellationToken ct)
    {
        using var cap = new VideoCapture();

        bool opened = cap.Open(_cam.Url, VideoCaptureAPIs.FFMPEG) && cap.IsOpened();
        if (!opened)
            opened = cap.Open(_cam.Url) && cap.IsOpened();

        if (!opened)
        {
            StatusMsg = "Không mở được nguồn video";
            await Task.Delay(5_000, ct);
            return;
        }

        cap.Set(VideoCaptureProperties.BufferSize, 1);
        StatusMsg = "Đang chạy";

        using var mat = new Mat();
        var nextInfer = DateTime.MinValue;

        while (!ct.IsCancellationRequested)
        {
            if (!cap.Read(mat) || mat.Empty())
            {
                StatusMsg = "Hết video / mất tín hiệu — đang thử lại…";
                break;
            }

            if (ct.IsCancellationRequested) break;

            var newFrame = MatToBitmap(mat);

            if (_inferActive && _runner.IsLoaded && _cam.Regions.Count > 0
                && DateTime.Now >= nextInfer)
            {
                var sw = System.Diagnostics.Stopwatch.StartNew();
                ProcessRegions(newFrame);
                sw.Stop();
                LastInferMs = sw.ElapsedMilliseconds;
                nextInfer   = DateTime.Now.AddMilliseconds(_cfg.IntervalMs);
            }

            Bitmap? oldFrame;
            lock (_frameLock) { oldFrame = _frame; _frame = newFrame; }
            oldFrame?.Dispose();
            FrameCount++;

            await Task.Delay(30, ct);
        }
    }

    // ── Per-region classify ───────────────────────────────────────────────

    private void ProcessRegions(Bitmap fullFrame)
    {
        foreach (var region in _cam.Regions)
        {
            var rect = region.ToPixelRect(fullFrame.Width, fullFrame.Height);
            if (rect.Width < 4 || rect.Height < 4) continue;

            using var crop = CropBitmap(fullFrame, rect);
            var topN = _runner.Classify(crop, _cfg.TopN);
            if (topN.Count == 0) continue;

            var top1 = topN[0];

            lock (_stateLock)
            {
                if (!_states.TryGetValue(region.Id, out var st))
                    _states[region.Id] = st = new RegionClsState { RegionId = region.Id };

                st.RegionName = region.Name;
                st.ClassName  = top1.ClassName;
                st.ClassId    = top1.ClassId;
                st.Conf       = top1.Conf;
                st.TopN       = topN;
                st.UpdatedAt  = DateTime.Now;

                _crops.TryGetValue(region.Id, out var old); old?.Dispose();
                _crops[region.Id] = (Bitmap)crop.Clone();
            }

            _prevClass.TryGetValue(region.Id, out var prev);
            bool changed = prev is not null && prev != top1.ClassName;

            if (changed)
            {
                // Lưu ảnh chỉ khi trạng thái thay đổi
                string? cropPath = SaveSnapshots(fullFrame, crop, region.Name, top1.ClassName);
                var topNJson = JsonSerializer.Serialize(
                    topN.Select(t => new { t.ClassName, t.Conf }));

                var rec = new ClsChangeRecord
                {
                    CameraId   = _cam.Id,
                    CameraName = _cam.Name,
                    RegionId   = region.Id,
                    RegionName = region.Name,
                    OccurredAt = DateTime.Now,
                    PrevClass  = prev!,
                    NewClass   = top1.ClassName,
                    Confidence = top1.Conf,
                    ImagePath  = cropPath ?? "",
                    TopNJson   = topNJson,
                };
                _db.Insert(rec);
                Events.Enqueue(rec);
            }

            if (prev is null || changed)
                _prevClass[region.Id] = top1.ClassName;
        }
    }

    // ── Helpers ───────────────────────────────────────────────────────────

    private static Bitmap CropBitmap(Bitmap src, Rectangle r)
    {
        r.Intersect(new Rectangle(0, 0, src.Width, src.Height));
        if (r.Width < 1 || r.Height < 1) return new Bitmap(1, 1);

        var crop = new Bitmap(r.Width, r.Height, PixelFormat.Format24bppRgb);
        using var g = Graphics.FromImage(crop);
        g.DrawImage(src, 0, 0, r, GraphicsUnit.Pixel);
        return crop;
    }

    /// <summary>
    /// Lưu ảnh khi trạng thái thay đổi.
    /// Cấu trúc: {ImageFolder}/{cam_name}/{new_class}/{yyyyMMdd_HHmmss_fff}/
    ///   - crop_{region_name}.jpg  — vùng phát hiện
    ///   - full.jpg                — toàn khung hình
    /// Trả về đường dẫn ảnh crop (dùng làm ImagePath trong DB).
    /// </summary>
    private string? SaveSnapshots(Bitmap fullFrame, Bitmap crop, string regionName, string newClass)
    {
        if (string.IsNullOrEmpty(_cfg.ImageFolder)) return null;
        try
        {
            var eventId  = DateTime.Now.ToString("yyyyMMdd_HHmmss_fff");
            var folder   = Path.Combine(
                _cfg.ImageFolder,
                SanitizeName(_cam.Name),
                SanitizeName(newClass),
                eventId);
            Directory.CreateDirectory(folder);

            var cropPath = Path.Combine(folder, $"crop_{SanitizeName(regionName)}.jpg");
            var fullPath = Path.Combine(folder, "full.jpg");
            crop.Save(cropPath,      ImageFormat.Jpeg);
            fullFrame.Save(fullPath, ImageFormat.Jpeg);
            return cropPath;
        }
        catch { return null; }
    }

    private static string SanitizeName(string name)
    {
        var invalid = Path.GetInvalidFileNameChars();
        return new string(name.Select(c => Array.IndexOf(invalid, c) >= 0 ? '_' : c).ToArray()).Trim('_', ' ');
    }

    private static unsafe Bitmap MatToBitmap(Mat mat)
    {
        int w = mat.Cols, h = mat.Rows;
        var bmp  = new Bitmap(w, h, PixelFormat.Format24bppRgb);
        var data = bmp.LockBits(new Rectangle(0, 0, w, h),
                        ImageLockMode.WriteOnly, PixelFormat.Format24bppRgb);
        int srcStride = (int)mat.Step(), dstStride = data.Stride;
        byte* src = (byte*)mat.Data, dst = (byte*)data.Scan0;
        for (int y = 0; y < h; y++)
            Buffer.MemoryCopy(
                src + (long)y * srcStride,
                dst + (long)y * dstStride,
                dstStride, Math.Min(srcStride, dstStride));
        bmp.UnlockBits(data);
        return bmp;
    }

    // ── Dispose ───────────────────────────────────────────────────────────

    public void Dispose()
    {
        _cts?.Cancel(); _cts?.Dispose();
        lock (_frameLock) { _frame?.Dispose(); _frame = null; }
        lock (_stateLock) { foreach (var b in _crops.Values) b?.Dispose(); _crops.Clear(); }
    }
}
