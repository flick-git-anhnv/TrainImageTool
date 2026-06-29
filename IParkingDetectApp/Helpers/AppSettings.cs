using System.Text.Json;
using System.Text.Json.Serialization;

namespace IParkingDetect.Helpers;

/// <summary>Persistence cài đặt người dùng sang JSON.</summary>
public sealed class AppSettings
{
    private static readonly string _path = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
        "KZTEK", "IParkingDetect", "settings.json");

    private static readonly JsonSerializerOptions _json = new()
    {
        WriteIndented = true, DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull
    };

    // ── Fields ─────────────────────────────────────────────────────────────
    public string  ModelPath      { get; set; } = "";
    public string  ImagePath      { get; set; } = "";
    public string  WrongFolder    { get; set; } = "";
    public float   Conf           { get; set; } = 0.30f;
    public float   Iou            { get; set; } = 0.45f;
    public bool    ScanSubfolders { get; set; } = false;
    public bool    ShowOriginal   { get; set; } = false;
    public int     Parallelism    { get; set; } = 4;     // số ảnh detect song song
    public int     ApiPort        { get; set; } = 5000;  // cổng HTTP API host
    public bool    ApiAutoStart   { get; set; } = false; // tự khởi động API khi mở app
    public string  Device         { get; set; } = "CPU";  // CPU | AUTO | GPU
    public bool    SaveLabel      { get; set; } = false; // tự lưu file .txt khi detect
    public int     FilmCols       { get; set; } = 8;
    public int     SplitLeft      { get; set; } = 260;
    public int     SplitRight     { get; set; } = 220;
    public int     SplitFilm      { get; set; } = 130;
    public int     FormW          { get; set; } = 1350;
    public int     FormH          { get; set; } = 860;

    // Lịch sử nhập (20 mục gần nhất)
    public List<string> ModelHistory { get; set; } = [];
    public List<string> ImageHistory { get; set; } = [];

    // Review state: path → "ok"/"wrong"
    [JsonIgnore] public Dictionary<string, string> ReviewState { get; set; } = [];

    // ── Load / Save ────────────────────────────────────────────────────────

    public static AppSettings Load()
    {
        try
        {
            if (File.Exists(_path))
            {
                var json = File.ReadAllText(_path);
                return JsonSerializer.Deserialize<AppSettings>(json, _json) ?? new();
            }
        }
        catch { /* ignore — return defaults */ }
        return new();
    }

    public void Save()
    {
        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(_path)!);
            File.WriteAllText(_path, JsonSerializer.Serialize(this, _json));
        }
        catch { /* ignore */ }
    }

    // ── History helpers ───────────────────────────────────────────────────

    public void PushModelHistory(string path)   => PushHistory(ModelHistory, path);
    public void PushImageHistory(string path)   => PushHistory(ImageHistory, path);

    private static void PushHistory(List<string> hist, string val, int max = 20)
    {
        if (string.IsNullOrWhiteSpace(val)) return;
        hist.Remove(val);
        hist.Insert(0, val);
        if (hist.Count > max) hist.RemoveRange(max, hist.Count - max);
    }
}
