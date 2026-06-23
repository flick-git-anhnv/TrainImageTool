using System.Text.Json;
using IParkingImage.Config;
using IParkingImage.Helpers;
using IParkingImage.Models;

namespace IParkingImage.Workers;

/// <summary>
/// Thu thập ảnh từ iParking v6.
/// Auth: Bearer token (nhập tay).
/// VehicleType: 0=Car, 2=Motorbike, 4=Bicycle, -1=Unknown.
/// Ảnh tải từ MinIO theo fileKeys hoặc URL trực tiếp.
/// </summary>
public class Parkingv6Worker : BaseWorker
{
    private const string HistoryFile = ".p6_done.json";
    private readonly Parkingv6Config _p6Cfg;

    public Parkingv6Worker(AppConfig cfg, Action<string> log,
                           Action<WorkerStats>? onProgress = null, LaneCounters? shared = null)
        : base(cfg, log, onProgress, shared)
    {
        _p6Cfg = cfg.Parkingv6;
    }

    public override async Task RunAsync(CancellationToken ct)
    {
        _ct = ct;
        _stats.Reset();

        if (string.IsNullOrWhiteSpace(_p6Cfg.Token))
        { LogError("Thiếu Bearer Token. Vui lòng thiết lập token trong appsettings.json."); return; }

        using var api = new ApiHelper();
        api.SetBearerToken(_p6Cfg.Token);

        Directory.CreateDirectory(_cfg.OutputDir);
        var histFile = Path.Combine(_cfg.OutputDir, HistoryFile);
        var done     = FileHelper.LoadDoneHistory(histFile);
        var days     = FileHelper.BuildDayList(_cfg.FromDate, _cfg.ToDate);
        _stats.TotalDays = days.Count;
        LogInfo($"Tổng {days.Count} ngày. Đã có: {done.Count}.");

        foreach (var day in days)
        {
            if (ct.IsCancellationRequested) break;
            if (done.Contains(day.Label))
            {
                _stats.DayIdx++;
                LogSkip($"Ngày {day.Label} đã tải.");
                continue;
            }
            _stats.DayLabel = day.Label;
            _stats.DayIdx++;
            LogInfo($"─── Ngày {day.Label} ({_stats.DayIdx}/{_stats.TotalDays}) ───");
            await ProcessDayAsync(api, day, ct);
            FileHelper.AppendDoneHistory(histFile, day.Label, done);
        }

        LogOk($"Hoàn thành. {_stats}");
    }

    private async Task ProcessDayAsync(ApiHelper api, DayRange day, CancellationToken ct)
    {
        var sources = _p6Cfg.EventSource == "both"
            ? ["event-in", "event-out"]
            : new[] { _p6Cfg.EventSource };

        foreach (var evtSrc in sources)
        {
            int page = 1;
            while (!ct.IsCancellationRequested)
            {
                if (_cfg.MaxPages > 0 && page > _cfg.MaxPages) break;
                _stats.Page = page;

                var body = new Dictionary<string, object>
                {
                    ["fromDate"]    = day.Start.ToString("yyyy-MM-ddTHH:mm:ss"),
                    ["toDate"]      = day.End.ToString("yyyy-MM-ddTHH:mm:ss"),
                    ["pageNumber"]  = page,
                    ["pageSize"]    = _cfg.PageSize,
                    ["eventSource"] = evtSrc,
                };
                if (!string.IsNullOrEmpty(_p6Cfg.Keyword))
                    body["keyword"] = _p6Cfg.Keyword;

                var url = _p6Cfg.ApiUrl.TrimEnd('/');
                // Thêm /events nếu chưa có
                if (!url.EndsWith("/events", StringComparison.OrdinalIgnoreCase))
                    url += "/events";

                var doc = await api.PostJsonAsync(url, body, ct);
                if (doc is null)
                {
                    // Fallback GET
                    var getUrl = $"{_p6Cfg.ApiUrl.TrimEnd('/')}/" +
                                 $"?fromDate={day.Start:yyyy-MM-ddTHH:mm:ss}" +
                                 $"&toDate={day.End:yyyy-MM-ddTHH:mm:ss}" +
                                 $"&pageNumber={page}&pageSize={_cfg.PageSize}";
                    doc = await api.GetJsonAsync(getUrl, ct);
                }

                if (doc is null) { LogError($"Trang {page} — không nhận response."); break; }

                var records = ExtractArray(doc.RootElement);
                _stats.Event += records.Count;
                LogInfo($"[{evtSrc}] Trang {page}: {records.Count} SK.");
                if (records.Count == 0) break;

                foreach (var rec in records)
                {
                    if (ct.IsCancellationRequested) break;
                    await ProcessRecordAsync(api, rec, day, evtSrc, ct);
                    await SleepAsync();
                }

                ReportProgress();
                if (records.Count < _cfg.PageSize) break;
                page++;
            }
        }
    }

    private async Task ProcessRecordAsync(ApiHelper api, JsonElement rec,
                                           DayRange day, string evtSrc, CancellationToken ct)
    {
        // ── VehicleType ───────────────────────────────────────────────────
        int vtInt = 0;
        if (rec.TryGetProperty("vehicleType", out var vtEl)) vtEl.TryGetInt32(out vtInt);
        else if (rec.TryGetProperty("VehicleType", out vtEl)) vtEl.TryGetInt32(out vtInt);
        var vehicleCategory = VehicleType.P6IntToCategory(vtInt);

        // ── Plate & Lane ──────────────────────────────────────────────────
        var plate = NormPlate(
            rec.TryGetString("plateNumber") ?? rec.TryGetString("PlateNumber")
         ?? rec.TryGetString("plate")       ?? "");
        if (string.IsNullOrEmpty(plate)) plate = "UNKNOWN";

        var laneRaw = rec.TryGetString("laneName") ?? rec.TryGetString("LaneName")
                   ?? rec.TryGetString("lane")      ?? "unknown";
        // lane.name nested
        if (rec.TryGetProperty("lane", out var laneEl) &&
            laneEl.ValueKind == JsonValueKind.Object)
        {
            var ln = laneEl.TryGetString("name") ?? laneEl.TryGetString("laneName") ?? "";
            if (!string.IsNullOrEmpty(ln)) laneRaw = ln;
        }
        var lane = VehicleType.SafeFileName(laneRaw);

        // ── DateTime ──────────────────────────────────────────────────────
        var dtStr = rec.TryGetString("eventTime") ?? rec.TryGetString("EventTime")
                 ?? rec.TryGetString("createdAt") ?? rec.TryGetString("CreatedAt")
                 ?? day.Start.ToString("O");
        if (!DateTime.TryParse(dtStr, out var dt)) dt = day.Start;

        var buoi = VehicleType.HourToBuoi(dt.Hour);

        // ── Keyword filter ────────────────────────────────────────────────
        if (!MatchKeyword(_p6Cfg.Keyword, plate, laneRaw)) { _stats.Skipped++; return; }

        // ── Trích ảnh từ fileKeys (MinIO) hoặc URLs ───────────────────────
        var images = ExtractP6Images(rec, vehicleCategory);
        if (images.Count == 0) { _stats.Skipped++; return; }

        _stats.Found++;

        foreach (var (imgType, keyOrUrl) in images)
        {
            if (ct.IsCancellationRequested) return;
            if (!IsVtypeAllowed(imgType)) continue;
            if (!CanSave(lane, imgType, buoi)) { _stats.Skipped++; continue; }

            byte[]? data = null;
            if (_p6Cfg.UseMinIO && !keyOrUrl.StartsWith("http", StringComparison.OrdinalIgnoreCase))
            {
                data = await ApiHelper.MinioDownloadAsync(
                    _p6Cfg.MinioEndpoint, _p6Cfg.MinioBucket,
                    _p6Cfg.MinioAccessKey, _p6Cfg.MinioSecretKey,
                    keyOrUrl, ct);
            }
            else
            {
                data = await api.DownloadBytesAsync(keyOrUrl, ct);
            }

            if (data is null || data.Length == 0) { _stats.Error++; continue; }

            var path = FileHelper.BuildSavePath(
                _cfg.OutputDir, imgType, day.Label, buoi, lane, dt, plate);

            if (await FileHelper.SaveBytesAsync(path, data))
            {
                _stats.Saved++;
                RecordSave(lane, imgType, buoi);
                LogOk($"Lưu: {Path.GetFileName(path)}  [{imgType}]");
            }
            else _stats.Skipped++;
        }
    }

    private static List<(string ImgType, string KeyOrUrl)> ExtractP6Images(
        JsonElement rec, string vehicleCategory)
    {
        var result = new List<(string, string)>();

        // fileKeys: [{ key: "...", type: "OVERVIEW/LPR/VEHICLE" }]
        if (rec.TryGetProperty("fileKeys", out var fk) &&
            fk.ValueKind == JsonValueKind.Array)
        {
            int idx = 0;
            foreach (var item in fk.EnumerateArray())
            {
                var key  = item.TryGetString("key") ?? item.TryGetString("fileKey") ?? "";
                var type = item.TryGetString("type") ?? item.TryGetString("imageType") ?? "";
                if (string.IsNullOrEmpty(key)) { idx++; continue; }

                var imgType = DetermineImgTypeFromKey(key, type, idx, vehicleCategory);
                result.Add((imgType, key));
                idx++;
            }
            return result;
        }

        // Fallback: trực tiếp mảng string fileKeys
        if (rec.TryGetProperty("fileKeys", out var fkArr) &&
            fkArr.ValueKind == JsonValueKind.Array)
        {
            int idx2 = 0;
            foreach (var item in fkArr.EnumerateArray())
            {
                if (item.ValueKind != JsonValueKind.String) { idx2++; continue; }
                var key = item.GetString() ?? "";
                if (string.IsNullOrEmpty(key)) { idx2++; continue; }
                var imgType = DetermineImgTypeFromKey(key, "", idx2, vehicleCategory);
                result.Add((imgType, key));
                idx2++;
            }
            return result;
        }

        // URL fields
        foreach (var field in new[] { "imageUrl", "imageFullUrl", "imagePlateUrl",
                                      "imageIn",  "imageOut", "imageFull" })
        {
            var url = rec.TryGetString(field) ?? "";
            if (string.IsNullOrEmpty(url)) continue;
            var imgType = field.Contains("Plate") || field.Contains("plate")
                ? $"{vehicleCategory}_bsx_cut"
                : field.Contains("Full") || field.Contains("full")
                    ? $"toan_canh_{vehicleCategory}"
                    : vehicleCategory;
            result.Add((imgType, url));
        }

        return result;
    }

    private static string DetermineImgTypeFromKey(
        string key, string typeHint, int idx, string vehicleCategory)
    {
        var k = (key + " " + typeHint).ToUpperInvariant();
        if (k.Contains("OVERVIEW") || k.Contains("TOAN_CANH") || k.Contains("FULL"))
            return $"toan_canh_{vehicleCategory}";
        if (k.Contains("LPR") || k.Contains("BSX") || k.Contains("PLATE"))
            return $"{vehicleCategory}_bsx_cut";
        if (k.Contains("VEHICLE") || k.Contains("VEH") || k.Contains("CAR"))
            return vehicleCategory;
        // fallback: idx 0 → toàn cảnh
        return idx == 0 ? $"toan_canh_{vehicleCategory}" : vehicleCategory;
    }

    private static List<JsonElement> ExtractArray(JsonElement root)
    {
        JsonElement arr = default;
        bool found = root.TryGetProperty("data", out arr)
                  || root.TryGetProperty("content", out arr)
                  || root.TryGetProperty("items", out arr)
                  || root.TryGetProperty("records", out arr);
        if (!found && root.TryGetProperty("data", out var d))
            d.TryGetProperty("content", out arr);
        if (arr.ValueKind == JsonValueKind.Array)
            return arr.EnumerateArray().ToList();
        return [];
    }
}
