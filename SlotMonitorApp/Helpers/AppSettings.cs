using System.Text.Json;
using System.Text.Json.Serialization;
using SlotMonitor.Models;

namespace SlotMonitor.Helpers;

/// <summary>Cài đặt toàn bộ app — đọc/ghi JSON kế thư mục exe.</summary>
public sealed class AppSettings
{
    private static readonly string _path = Path.Combine(
        AppDomain.CurrentDomain.BaseDirectory, "slot_monitor_settings.json");

    private static readonly JsonSerializerOptions _jso = new()
    {
        WriteIndented = true,
        DefaultIgnoreCondition = JsonIgnoreCondition.Never,
    };

    // ── Model ──────────────────────────────────────────────────────────────
    public string ModelPath       { get; set; } = "";
    public string Device          { get; set; } = "CPU";
    public float  Conf            { get; set; } = 0.30f;
    public float  Iou             { get; set; } = 0.45f;
    public int    EmptyClassIndex { get; set; } = 0;   // class index báo "trống"

    // ── Camera polling ─────────────────────────────────────────────────────
    public int IntervalSecs { get; set; } = 5;

    // ── Storage ────────────────────────────────────────────────────────────
    public string ImageFolder { get; set; } = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments),
        "SlotMonitor", "Events");

    public string DbPath { get; set; } = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
        "KZTEK", "SlotMonitor", "history.db");

    // ── UI state ───────────────────────────────────────────────────────────
    public int FormW { get; set; } = 1200;
    public int FormH { get; set; } = 720;

    // ── Camera list ────────────────────────────────────────────────────────
    public List<CameraConfig> Cameras { get; set; } = [];

    // ── Persistence ────────────────────────────────────────────────────────

    public static AppSettings Load()
    {
        try
        {
            if (File.Exists(_path))
                return JsonSerializer.Deserialize<AppSettings>(File.ReadAllText(_path), _jso) ?? new();
        }
        catch { }
        return new();
    }

    public void Save()
    {
        try { File.WriteAllText(_path, JsonSerializer.Serialize(this, _jso)); }
        catch { }
    }
}
