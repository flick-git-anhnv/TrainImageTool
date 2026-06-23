using System.Text.Json;
using System.Text.Json.Nodes;
using IParkingImage.Config;

namespace IParkingImage.Helpers;

/// <summary>Đọc/ghi cài đặt người dùng ra file JSON (appsettings.json).</summary>
public static class SettingsManager
{
    private static readonly string _file =
        Path.Combine(AppContext.BaseDirectory, "appsettings.json");

    private static readonly JsonSerializerOptions _opts = new()
    {
        WriteIndented = true,
        PropertyNameCaseInsensitive = true,
    };

    public static AppConfig Load()
    {
        try
        {
            if (!File.Exists(_file)) return new AppConfig();
            var json = File.ReadAllText(_file);
            return JsonSerializer.Deserialize<AppConfig>(json, _opts) ?? new AppConfig();
        }
        catch
        {
            return new AppConfig();
        }
    }

    public static void Save(AppConfig cfg)
    {
        try
        {
            var json = JsonSerializer.Serialize(cfg, _opts);
            File.WriteAllText(_file, json);
        }
        catch { /* non-fatal */ }
    }

    // ── History helpers ─────────────────────────────────────────────────

    private static Dictionary<string, List<string>> _history = [];
    private static readonly string _histFile =
        Path.Combine(AppContext.BaseDirectory, "ui_history.json");

    public static void LoadHistory()
    {
        try
        {
            if (!File.Exists(_histFile)) return;
            var json = File.ReadAllText(_histFile);
            _history = JsonSerializer.Deserialize<Dictionary<string, List<string>>>(json, _opts)
                       ?? [];
        }
        catch { _history = []; }
    }

    public static void SaveHistory()
    {
        try
        {
            var json = JsonSerializer.Serialize(_history, _opts);
            File.WriteAllText(_histFile, json);
        }
        catch { }
    }

    public static List<string> GetHistory(string key) =>
        _history.TryGetValue(key, out var list) ? list : [];

    public static void PushHistory(string key, string value, int maxItems = 20)
    {
        if (string.IsNullOrWhiteSpace(value)) return;
        if (!_history.TryGetValue(key, out var list))
        {
            list = [];
            _history[key] = list;
        }
        list.Remove(value);
        list.Insert(0, value);
        if (list.Count > maxItems)
            list.RemoveRange(maxItems, list.Count - maxItems);
    }

    /// <summary>Bind a ComboBox to a history key — loads existing history and saves on change.</summary>
    public static void BindHistory(ComboBox combo, string key, int maxItems = 20)
    {
        var hist = GetHistory(key);
        combo.Items.Clear();
        combo.Items.AddRange(hist.ToArray<object>());
        if (hist.Count > 0) combo.Text = hist[0];

        void OnChange(object? s, EventArgs e)
        {
            var val = combo.Text.Trim();
            if (string.IsNullOrEmpty(val)) return;
            PushHistory(key, val, maxItems);
            var cur = combo.Text;
            var hist2 = GetHistory(key);
            combo.Items.Clear();
            combo.Items.AddRange(hist2.ToArray<object>());
            combo.Text = cur;
        }
        combo.Leave += OnChange;
        combo.KeyDown += (s, e) => { if (e.KeyCode == Keys.Return) OnChange(s, e); };
    }
}
