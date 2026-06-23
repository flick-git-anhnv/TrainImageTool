using System.Text.Json;
using IParkingImage.Config;
using IParkingImage.Helpers;
using IParkingImage.Models;

namespace IParkingImage.Workers;

/// <summary>
/// Thu thập ảnh từ iParking v8.
/// Auth: OAuth2 client_credentials hoặc password → Bearer token.
/// VehicleType: 0=Car, 1=Motorbike, 2=Bicycle.
/// Ảnh tải qua PresignedUrl hoặc Base64.
/// </summary>
public class Parkingv8Worker : BaseWorker
{
    private const string HistoryFile = ".p8_done.json";
    private readonly Parkingv8Config _p8Cfg;

    // EmImageType: 0=VEHICLE, 1=PLATE, 2=PANORAMA, 3=FACE, 4=OTHER
    private static readonly Dictionary<int, (string suffix, bool isPlate, bool isPano)> _imgTypeMap = new()
    {
        [0] = ("vo",   false, false),
        [1] = ("po",   true,  false),
        [2] = ("fo",   false, true),
        [3] = ("face", false, false),
        [4] = ("other",false, false),
    };

    public Parkingv8Worker(AppConfig cfg, Action<string> log,
                           Action<WorkerStats>? onProgress = null, LaneCounters? shared = null)
        : base(cfg, log, onProgress, shared)
    {
        _p8Cfg = cfg.Parkingv8;
    }

    public override async Task RunAsync(CancellationToken ct)
    {
        _ct = ct;
        _stats.Reset();
        using var api = new ApiHelper();

        // ── 1. Đăng nhập ─────────────────────────────────────────────────
        LogInfo("Đăng nhập Parkingv8...");
        var token = await api.P8LoginAsync(
            _p8Cfg.LoginUrl, _p8Cfg.GrantType,
            _p8Cfg.ClientId, _p8Cfg.ClientSecret,
            _p8Cfg.Username, _p8Cfg.Password, ct);
        if (token is null) { LogError("Đăng nhập thất bại. Kiểm tra LoginUrl / credentials."); return; }
        LogOk("Đăng nhập thành công.");

        // ── 2. Duyệt từng ngày ───────────────────────────────────────────
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
        var sources = _p8Cfg.EventSource == "both"
            ? ["exits", "entries"]
            : new[] { _p8Cfg.EventSource };

        foreach (var src in sources)
        {
            int page = 1;
            while (!ct.IsCancellationRequested)
            {
                if (_cfg.MaxPages > 0 && page > _cfg.MaxPages) break;
                _stats.Page = page;

                // Parkingv8 thường dùng POST với body JSON hoặc GET
                var body = new
                {
                    fromDate = day.Start.ToString("yyyy-MM-ddTHH:mm:ss"),
                    toDate   = day.End.ToString("yyyy-MM-ddTHH:mm:ss"),
                    pageNum  = page,
                    pageSize = _cfg.PageSize,
                    keyword  = string.IsNullOrEmpty(_p8Cfg.Keyword) ? (object?)null : _p8Cfg.Keyword,
                };

                var url = $"{_p8Cfg.ApiUrl.TrimEnd('/')}/{src}";
                var doc = await api.PostJsonAsync(url, body, ct);

                if (doc is null)
                {
                    // Thử GET fallback
                    var getUrl = $"{_p8Cfg.ApiUrl.TrimEnd('/')}/{src}" +
                                 $"?fromDate={Uri.EscapeDataString(day.Start.ToString("yyyy-MM-ddTHH:mm:ss"))}" +
                                 $"&toDate={Uri.EscapeDataString(day.End.ToString("yyyy-MM-ddTHH:mm:ss"))}" +
                                 $"&pageNum={page}&pageSize={_cfg.PageSize}";
                    doc = await api.GetJsonAsync(getUrl, ct);
                }

                if (doc is null) { LogError($"Trang {page} — không nhận response."); break; }

                var records = ExtractArray(doc.RootElement);
                _stats.Event += records.Count;
                LogInfo($"[{src}] Trang {page}: {records.Count} SK.");
                if (records.Count == 0) break;

                foreach (var rec in records)
                {
                    if (ct.IsCancellationRequested) break;
                    await ProcessRecordAsync(api, rec, day, src, ct);
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
        var vehicleCategory = VehicleType.P8IntToCategory(vtInt);

        // ── Plate & Lane ──────────────────────────────────────────────────
        var plate = NormPlate(
            rec.TryGetString("plateNumber") ?? rec.TryGetString("plate")
         ?? rec.TryGetString("PlateNumber") ?? "");
        if (string.IsNullOrEmpty(plate)) plate = "UNKNOWN";

        var laneRaw = rec.TryGetString("laneName") ?? rec.TryGetString("LaneName")
                   ?? rec.TryGetString("lane")     ?? "unknown";
        var lane = VehicleType.SafeFileName(laneRaw);

        // ── DateTime ──────────────────────────────────────────────────────
        var dtStr = rec.TryGetString("createdAt") ?? rec.TryGetString("eventTime")
                 ?? rec.TryGetString("CreatedAt") ?? day.Start.ToString("O");
        if (!DateTime.TryParse(dtStr, out var dt)) dt = day.Start;

        var buoi = VehicleType.HourToBuoi(dt.Hour);

        // ── Keyword filter ────────────────────────────────────────────────
        if (!MatchKeyword(_p8Cfg.Keyword, plate, laneRaw)) { _stats.Skipped++; return; }

        // ── GT filter ─────────────────────────────────────────────────────
        if (_cfg.OnlyGT)
        {
            var pReg = NormPlate(rec.TryGetString("registeredPlate") ?? "");
            if (!string.IsNullOrEmpty(pReg) && plate != pReg)
            { _stats.Skipped++; return; }
        }

        // ── Trích ảnh ─────────────────────────────────────────────────────
        var images = ExtractP8Images(rec, evtSrc, vehicleCategory);
        if (images.Count == 0) { _stats.Skipped++; return; }

        _stats.Found++;

        foreach (var (imgType, urlOrB64) in images)
        {
            if (ct.IsCancellationRequested) return;
            if (!IsVtypeAllowed(imgType)) continue;
            if (!CanSave(lane, imgType, buoi)) { _stats.Skipped++; continue; }

            byte[]? data = null;
            if (_p8Cfg.ImgMode == "base64" || ApiHelper.LooksBase64(urlOrB64))
                data = ApiHelper.DecodeBase64(urlOrB64);
            else
                data = await api.DownloadBytesAsync(urlOrB64, ct);

            if (data is null || data.Length == 0) { _stats.Error++; continue; }

            var path = FileHelper.BuildSavePath(
                _cfg.OutputDir, imgType, day.Label, buoi, lane, dt, plate,
                evtSrc == "entries" ? "in" : "");

            if (await FileHelper.SaveBytesAsync(path, data))
            {
                _stats.Saved++;
                RecordSave(lane, imgType, buoi);
                LogOk($"Lưu: {Path.GetFileName(path)}  [{imgType}]");
            }
            else _stats.Skipped++;
        }
    }

    private static List<(string ImgType, string UrlOrB64)> ExtractP8Images(
        JsonElement rec, string evtSrc, string vehicleCategory)
    {
        var result = new List<(string, string)>();
        bool isEntry = evtSrc == "entries";

        // PresignedUrl: cấu trúc [{ imageType: 0, presignedUrl: "..." }, ...]
        if (rec.TryGetProperty("presignedUrls", out var pUrls) &&
            pUrls.ValueKind == JsonValueKind.Array)
        {
            foreach (var p in pUrls.EnumerateArray())
            {
                int emType = 0;
                p.TryGetProperty("imageType", out var et); et.TryGetInt32(out emType);
                var url = p.TryGetString("presignedUrl") ?? p.TryGetString("url") ?? "";
                if (string.IsNullOrEmpty(url)) continue;

                var imgType = MapEmImageType(emType, vehicleCategory, isEntry);
                result.Add((imgType, url));
            }
            return result;
        }

        // Fallback: field-level image URLs
        var suffixMap = isEntry
            ? new Dictionary<string, string>
              { ["imageFullIn"] = "fi", ["imagePlateIn"] = "pi", ["imageIn"] = "vi" }
            : new Dictionary<string, string>
              { ["imageFullOut"] = "fo", ["imagePlateOut"] = "po", ["imageOut"] = "vo" };

        foreach (var (field, suffix) in suffixMap)
        {
            var url = rec.TryGetString(field) ?? "";
            if (string.IsNullOrEmpty(url)) continue;
            var imgType = suffix switch
            {
                "fi" or "fo" => $"toan_canh_{vehicleCategory}",
                "pi" or "po" => $"{vehicleCategory}_bsx_cut",
                _            => vehicleCategory,
            };
            result.Add((imgType, url));
        }

        // Base64 variants
        var b64Map = isEntry
            ? new Dictionary<string, string>
              { ["imageFullInBase64"] = "fi", ["imagePlateInBase64"] = "pi", ["imageInBase64"] = "vi" }
            : new Dictionary<string, string>
              { ["imageFullOutBase64"] = "fo", ["imagePlateOutBase64"] = "po", ["imageOutBase64"] = "vo" };

        foreach (var (field, suffix) in b64Map)
        {
            var b64 = rec.TryGetString(field) ?? "";
            if (string.IsNullOrEmpty(b64) || !ApiHelper.LooksBase64(b64)) continue;
            var imgType = suffix switch
            {
                "fi" or "fo" => $"toan_canh_{vehicleCategory}",
                "pi" or "po" => $"{vehicleCategory}_bsx_cut",
                _            => vehicleCategory,
            };
            result.Add((imgType, b64));
        }

        return result;
    }

    private static string MapEmImageType(int emType, string vehicleCategory, bool isEntry)
    {
        string suffix = emType switch
        {
            0 => isEntry ? "vi" : "vo",
            1 => isEntry ? "pi" : "po",
            2 => isEntry ? "fi" : "fo",
            _ => isEntry ? "vi" : "vo",
        };
        return suffix switch
        {
            "fi" or "fo" => $"toan_canh_{vehicleCategory}",
            "pi" or "po" => $"{vehicleCategory}_bsx_cut",
            _            => vehicleCategory,
        };
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
