using System.Collections.Concurrent;
using System.Drawing.Imaging;
using SlotMonitor.Data;
using SlotMonitor.Helpers;
using SlotMonitor.Inference;
using SlotMonitor.Models;
using OpenCvSharp;

namespace SlotMonitor.Workers;

/// <summary>
/// Worker per camera: poll RTSP → detect → emit sự kiện thay đổi trạng thái.
///
/// Hai chế độ:
///   - Whole-frame (Slots rỗng): toàn frame là 1 đơn vị giám sát.
///   - Per-slot (Slots có giá trị): mỗi SlotBox là 1 đơn vị riêng, track độc lập.
///
/// Logic xác định trạng thái:
///   - Detect class EmptyClassIndex → Empty (trống).
///   - Không detect → Occupied (có xe).
///   Với per-slot: kiểm tra tâm detection box có nằm trong vùng slot không.
/// </summary>
public sealed class CameraWorker : IDisposable
{
    private readonly CameraConfig _cam;
    private readonly YoloRunner   _yolo;
    private readonly AppSettings  _cfg;
    private readonly SlotDb       _db;

    private CancellationTokenSource? _cts;
    private Task?                    _task;

    // ── Atomic state (read from UI thread, written from worker thread) ─────
    private volatile int    _stateVal  = (int)SlotState.Unknown;
    private volatile string _statusMsg = "Chưa khởi động";
    private          long   _detectMs;     // Interlocked
    private volatile float  _lastConf  = 0f;
    private          long   _checkTicks;   // Interlocked

    // ── Per-slot state + crop (guarded by _slotLock) ──────────────────────
    private readonly object                         _slotLock   = new();
    private readonly Dictionary<string, SlotStatus> _slotStatus = [];
    private readonly Dictionary<string, Bitmap?>    _slotCrops  = [];

    // ── Current frame (guarded by _frameLock) ─────────────────────────────
    private readonly object _frameLock = new();
    private Bitmap? _frame;

    // ── Event queue — dequeued by MainForm timer on UI thread ──────────────
    public ConcurrentQueue<StateChangeRecord> Events { get; } = new();

    // ── Public props ───────────────────────────────────────────────────────
    public CameraConfig Config       => _cam;
    public SlotState    CurrentState => (SlotState)_stateVal;
    public string       StatusMsg    => _statusMsg;
    public long         LastDetectMs => Interlocked.Read(ref _detectMs);
    public float        LastConf     => _lastConf;
    public DateTime     LastCheckTime
    {
        get { long t = Interlocked.Read(ref _checkTicks); return t > 0 ? new DateTime(t, DateTimeKind.Local) : DateTime.MinValue; }
    }
    public bool IsRunning => _task is { IsCompleted: false };

    /// <summary>Snapshot trạng thái tất cả slot (thread-safe clone).</summary>
    public List<SlotStatus> GetSlotStatuses()
    {
        lock (_slotLock)
            return _slotStatus.Values.Select(s => new SlotStatus
            {
                SlotId    = s.SlotId, SlotName  = s.SlotName,
                State     = s.State,  Conf      = s.Conf,
                UpdatedAt = s.UpdatedAt,
            }).ToList();
    }

    /// <summary>Clone crop ảnh của slot để UI hiển thị. Caller phải Dispose.</summary>
    public Bitmap? GetSlotCropClone(string slotId)
    {
        lock (_slotLock)
            return _slotCrops.TryGetValue(slotId, out var b) && b is not null
                ? (Bitmap)b.Clone() : null;
    }

    public CameraWorker(CameraConfig cam, YoloRunner yolo, AppSettings cfg, SlotDb db)
    {
        _cam = cam; _yolo = yolo; _cfg = cfg; _db = db;
        InitSlotStatus();
    }

    private void InitSlotStatus()
    {
        lock (_slotLock)
        {
            _slotStatus.Clear();
            foreach (var s in _cam.Slots)
                _slotStatus[s.Id] = new SlotStatus { SlotId = s.Id, SlotName = s.Name };
        }
    }

    // ── Control ────────────────────────────────────────────────────────────

    public void Start()
    {
        if (IsRunning) return;
        InitSlotStatus();
        _cts  = new CancellationTokenSource();
        _task = Task.Run(() => RunLoop(_cts.Token));
    }

    public void Stop()
    {
        _cts?.Cancel();
        _statusMsg = "Đang dừng…";
    }

    public Bitmap? GetFrameClone()
    {
        lock (_frameLock)
            return _frame is null ? null : (Bitmap)_frame.Clone();
    }

    // ── Main loop ──────────────────────────────────────────────────────────

    private async Task RunLoop(CancellationToken ct)
    {
        _statusMsg = "Đang kết nối…";
        while (!ct.IsCancellationRequested)
        {
            try    { await ConnectAndPoll(ct); }
            catch (OperationCanceledException) { break; }
            catch (Exception ex)
            {
                _statusMsg = $"Lỗi: {ex.Message[..Math.Min(60, ex.Message.Length)]}";
                try { await Task.Delay(5_000, ct); } catch { break; }
            }
        }
        _statusMsg = "Đã dừng";
    }

    private async Task ConnectAndPoll(CancellationToken ct)
    {
        using var cap = new VideoCapture();

        if (!cap.Open(_cam.RtspUrl, VideoCaptureAPIs.FFMPEG) || !cap.IsOpened())
        {
            _statusMsg = "Không mở được RTSP";
            await Task.Delay(5_000, ct);
            return;
        }

        cap.Set(VideoCaptureProperties.BufferSize, 1);
        _statusMsg = "Đang chạy";

        using var mat      = new Mat();
        var       prevWhole = SlotState.Unknown;                       // whole-frame prev
        var       prevSlot  = new Dictionary<string, SlotState>();     // per-slot prev

        while (!ct.IsCancellationRequested)
        {
            if (!cap.Read(mat) || mat.Empty())
            {
                _statusMsg = "Mất tín hiệu — đang thử lại…";
                break;
            }

            using var bmp = MatToBitmap(mat);

            // Cập nhật preview frame (trước khi detect để UI không chờ)
            lock (_frameLock)
            {
                _frame?.Dispose();
                _frame = (Bitmap)bmp.Clone();
            }

            Interlocked.Exchange(ref _checkTicks, DateTime.Now.Ticks);
            bool hasSlots = _cam.Slots.Count > 0;

            if (!hasSlots)
            {
                // ── Whole-frame mode: detect toàn frame ───────────────────
                var sw    = System.Diagnostics.Stopwatch.StartNew();
                var boxes = _yolo.IsLoaded ? _yolo.Detect(bmp, _cfg.Conf, _cfg.Iou) : [];
                sw.Stop();
                Interlocked.Exchange(ref _detectMs, sw.ElapsedMilliseconds);
                _lastConf = boxes.Count > 0 ? boxes.Max(b => b.Confidence) : 0f;

                var newState = DetermineWholeFrameState(boxes);
                _stateVal = (int)newState;

                if (newState != prevWhole && prevWhole != SlotState.Unknown)
                {
                    string? imgPath = SaveEventImage(bmp, "", newState);
                    EmitAndInsert("", "", prevWhole, newState, _lastConf, boxes.Count, imgPath);
                }
                prevWhole = newState;
            }
            else
            {
                // ── Per-slot mode: crop từng slot → detect riêng ──────────
                int   emptyCount = 0;
                long  totalMs    = 0;
                float maxConf    = 0f;

                foreach (var slot in _cam.Slots)
                {
                    // B1: Crop vùng slot từ ảnh gốc
                    using var crop = CropSlot(bmp, slot);

                    // B2: Detect trên crop
                    var sw = System.Diagnostics.Stopwatch.StartNew();
                    var boxes = _yolo.IsLoaded ? _yolo.Detect(crop, _cfg.Conf, _cfg.Iou) : [];
                    sw.Stop();
                    totalMs += sw.ElapsedMilliseconds;

                    // B3: Xác định trạng thái từ kết quả detect
                    var emptyBox = boxes.FirstOrDefault(b => b.ClassId == _cfg.EmptyClassIndex);
                    var newState = emptyBox is not null ? SlotState.Empty : SlotState.Occupied;
                    float conf   = emptyBox?.Confidence ?? 0f;
                    if (newState == SlotState.Empty) emptyCount++;
                    if (conf > maxConf) maxConf = conf;

                    // Cập nhật slot status + lưu crop để UI hiển thị
                    lock (_slotLock)
                    {
                        if (_slotStatus.TryGetValue(slot.Id, out var ss))
                        {
                            ss.State     = newState;
                            ss.Conf      = conf;
                            ss.UpdatedAt = DateTime.Now;
                        }
                        _slotCrops.TryGetValue(slot.Id, out var oldCrop);
                        oldCrop?.Dispose();
                        _slotCrops[slot.Id] = (Bitmap)crop.Clone();
                    }

                    // Emit event nếu trạng thái thay đổi
                    prevSlot.TryGetValue(slot.Id, out var prev);
                    if (prev == SlotState.Unknown) { prevSlot[slot.Id] = newState; continue; }
                    if (newState != prev)
                    {
                        string? imgPath = SaveEventImage(bmp, slot.Id, newState);
                        EmitAndInsert(slot.Id, slot.Name, prev, newState, conf, boxes.Count, imgPath);
                        prevSlot[slot.Id] = newState;
                    }
                }

                Interlocked.Exchange(ref _detectMs, totalMs);
                _lastConf = maxConf;

                // Aggregate state cho card overview
                _stateVal = (int)(emptyCount == _cam.Slots.Count ? SlotState.Empty :
                                  emptyCount == 0                ? SlotState.Occupied :
                                                                   SlotState.Unknown);
            }

            int delayMs = Math.Max(500, _cfg.IntervalSecs * 1_000);
            await Task.Delay(delayMs, ct);
        }
    }

    // ── Helpers ────────────────────────────────────────────────────────────

    /// <summary>Crop vùng slot từ bitmap gốc. Clamp vào biên ảnh để tránh out-of-bounds.</summary>
    private static Bitmap CropSlot(Bitmap src, SlotBox slot)
    {
        var rf = slot.ToPixelRect(src.Width, src.Height);
        var r  = Rectangle.FromLTRB(
            Math.Max(0, (int)rf.Left),
            Math.Max(0, (int)rf.Top),
            Math.Min(src.Width,  (int)Math.Ceiling(rf.Right)),
            Math.Min(src.Height, (int)Math.Ceiling(rf.Bottom)));

        if (r.Width < 1 || r.Height < 1)
            return new Bitmap(1, 1); // fallback tránh crash

        var crop = new Bitmap(r.Width, r.Height, System.Drawing.Imaging.PixelFormat.Format24bppRgb);
        using var g = Graphics.FromImage(crop);
        g.DrawImage(src, 0, 0, r, GraphicsUnit.Pixel);
        return crop;
    }

    private SlotState DetermineWholeFrameState(List<DetectBox> boxes)
    {
        if (!_yolo.IsLoaded) return SlotState.Unknown;
        return boxes.Any(b => b.ClassId == _cfg.EmptyClassIndex)
            ? SlotState.Empty : SlotState.Occupied;
    }

    private void EmitAndInsert(
        string slotId, string slotName,
        SlotState prev, SlotState next,
        float conf, int detCount, string? imgPath)
    {
        var rec = new StateChangeRecord
        {
            CameraId   = _cam.Id,
            CameraName = _cam.Name,
            SlotId     = slotId,
            SlotName   = slotName,
            OccurredAt = DateTime.Now,
            PrevState  = prev.ToString(),
            NewState   = next.ToString(),
            Confidence = conf,
            DetCount   = detCount,
            ImagePath  = imgPath ?? "",
        };
        _db.Insert(rec);
        Events.Enqueue(rec);
    }

    private string? SaveEventImage(Bitmap bmp, string slotId, SlotState state)
    {
        try
        {
            var sub    = string.IsNullOrEmpty(slotId) ? "frame" : slotId;
            var folder = Path.Combine(
                _cfg.ImageFolder, _cam.Id, sub, DateTime.Now.ToString("yyyy-MM-dd"));
            Directory.CreateDirectory(folder);
            var path = Path.Combine(folder, $"{DateTime.Now:HHmmss_fff}_{state}.jpg");
            bmp.Save(path, ImageFormat.Jpeg);
            return path;
        }
        catch { return null; }
    }

    /// <summary>
    /// Convert OpenCV Mat (BGR, 8-bit) → Bitmap.
    /// GDI+ Format24bppRgb lưu byte B,G,R — giống OpenCV BGR → không cần swap.
    /// </summary>
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
                dstStride,
                Math.Min(srcStride, dstStride));
        bmp.UnlockBits(data);
        return bmp;
    }

    public void Dispose()
    {
        _cts?.Cancel();
        _cts?.Dispose();
        lock (_frameLock) { _frame?.Dispose(); _frame = null; }
        lock (_slotLock)
        {
            foreach (var b in _slotCrops.Values) b?.Dispose();
            _slotCrops.Clear();
        }
    }
}
