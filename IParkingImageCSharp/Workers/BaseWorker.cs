using System.Collections.Concurrent;
using IParkingImage.Config;
using IParkingImage.Helpers;
using IParkingImage.Models;

namespace IParkingImage.Workers;

public abstract class BaseWorker
{
    protected readonly AppConfig _cfg;
    protected readonly Action<string> _log;
    protected readonly Action<WorkerStats>? _onProgress;
    protected readonly LaneCounters _laneCounters;
    protected readonly HashSet<string> _allowedVtypes;
    protected CancellationToken _ct;

    private readonly ManualResetEventSlim _pauseEvent = new(true);
    private volatile bool _stopped = false;

    protected readonly WorkerStats _stats = new();
    public WorkerStats Stats => _stats;

    protected BaseWorker(AppConfig cfg, Action<string> log,
                         Action<WorkerStats>? onProgress = null,
                         LaneCounters? shared = null)
    {
        _cfg          = cfg;
        _log          = log;
        _onProgress   = onProgress;
        _laneCounters = shared ?? new LaneCounters();
        _allowedVtypes = cfg.AllowedVtypes is { Count: > 0 }
            ? new HashSet<string>(cfg.AllowedVtypes)
            : [];
    }

    public abstract Task RunAsync(CancellationToken ct);

    // ── Pause / Stop ─────────────────────────────────────────────────────

    public void Pause()  => _pauseEvent.Reset();
    public void Resume() => _pauseEvent.Set();
    public void Stop()   { _stopped = true; _pauseEvent.Set(); }

    // ── Helpers ──────────────────────────────────────────────────────────

    protected bool IsVtypeAllowed(string vtype) =>
        _allowedVtypes.Count == 0 || _allowedVtypes.Contains(vtype);

    protected bool CanSave(string lane, string cat, string buoi) =>
        _laneCounters.AllowSave(lane, cat, buoi,
            _cfg.MaxPerLane, _cfg.MaxPerCategory, _cfg.MaxPerBuoi);

    protected void RecordSave(string lane, string cat, string buoi) =>
        _laneCounters.Increment(lane, cat, buoi);

    protected void ReportProgress() => _onProgress?.Invoke(Stats);

    protected async Task SleepAsync()
    {
        // blocks until resumed (or cancelled)
        _pauseEvent.Wait(_ct);
        if (_stopped) _ct.ThrowIfCancellationRequested();
        if (_cfg.SleepSeconds > 0)
            await Task.Delay(TimeSpan.FromSeconds(_cfg.SleepSeconds), _ct);
    }

    protected void LogInfo(string msg)  => _log($"[INFO] {msg}");
    protected void LogOk(string msg)    => _log($"[OK]   {msg}");
    protected void LogSkip(string msg)  => _log($"[SKIP] {msg}");
    protected void LogError(string msg) => _log($"[ERR]  {msg}");
    protected void LogWarn(string msg)  => _log($"[WARN] {msg}");

    protected static bool MatchKeyword(string keyword, params string[] fields)
    {
        if (string.IsNullOrWhiteSpace(keyword)) return true;
        var kw = keyword.ToLowerInvariant();
        foreach (var f in fields)
            if (!string.IsNullOrEmpty(f) && f.ToLowerInvariant().Contains(kw)) return true;
        return false;
    }

    protected static string NormPlate(string? s)
    {
        if (string.IsNullOrEmpty(s)) return "";
        return System.Text.RegularExpressions.Regex.Replace(s, @"[^0-9A-Za-z]", "").ToUpperInvariant();
    }
}
