using System.Text.Json;
using IParkingImage.Config;
using IParkingImage.Helpers;
using IParkingImage.Models;

namespace IParkingImage.Workers;

/// <summary>
/// Thu thập ảnh từ iParking Lotte.
/// API flow: Login → GET /api/parking/events?from=&to=&page=&size=
/// Phân loại xe theo keyword (description + cardGroup).
/// Ảnh tải từ MinIO hoặc URL trực tiếp.
/// </summary>
public class LotteWorker : BaseWorker
{
    private const string HistoryFile = ".lotte_done.json";
    private readonly LotteConfig _lotteCfg;

    public LotteWorker(AppConfig cfg, Action<string> log,
                       Action<WorkerStats>? onProgress = null, LaneCounters? shared = null)
        : base(cfg, log, onProgress, shared)
    {
        _lotteCfg = cfg.Lotte;
    }

    public override async Task RunAsync(CancellationToken ct)
    {
        _ct = ct;
        _stats.Reset();

        using var api = new ApiHelper();

        // ── 1. Đăng nhập ──────────────────────────────────────────────────
        LogInfo("Đăng nhập Lotte...");
        var token = await api.LotteLoginAsync(
            _lotteCfg.ApiBase, _lotteCfg.Username, _lotteCfg.Password, ct);
        if (token is null) { LogError("Đăng nhập thất bại. Kiểm tra URL / tài khoản."); return; }
        LogOk("Đăng nhập thành công.");

        // ── 2. Duyệt từng ngày ────────────────────────────────────────────
        var outDir  = _cfg.OutputDir;
        Directory.CreateDirectory(outDir);
        var histFile = Path.Combine(outDir, HistoryFile);
        var done     = FileHelper.LoadDoneHistory(histFile);
        var days     = FileHelper.BuildDayList(_cfg.FromDate, _cfg.ToDate);

        _stats.TotalDays = days.Count;
        LogInfo($"Tổng {days.Count} ngày cần xử lý. Đã có: {done.Count} ngày.");

        foreach (var day in days)
        {
            if (ct.IsCancellationRequested) break;
            if (done.Contains(day.Label))
            {
                _stats.DayIdx++;
                LogSkip($"Ngày {day.Label} — đã tải trước đó.");
                continue;
            }

            _stats.DayLabel = day.Label;
            _stats.DayIdx++;
            LogInfo($"─── Ngày {day.Label} ({_stats.DayIdx}/{_stats.TotalDays}) ───");

            await ProcessDayAsync(api, day, outDir, ct);

            FileHelper.AppendDoneHistory(histFile, day.Label, done);
        }

        LogOk($"Hoàn thành. {_stats}");
    }

    private async Task ProcessDayAsync(ApiHelper api, DayRange day,
                                        string outDir, CancellationToken ct)
    {
        int page   = 1;
        int total  = 0;
        bool hasMore = true;

        while (hasMore && !ct.IsCancellationRequested)
        {
            if (_cfg.MaxPages > 0 && page > _cfg.MaxPages) break;
            _stats.Page = page;

            var fromStr = day.Start.ToString("yyyy-MM-ddTHH:mm:ss");
            var toStr   = day.End.ToString("yyyy-MM-ddTHH:mm:ss");

            // API thường hỗ trợ GET với query params hoặc POST với body
            string url  = $"{_lotteCfg.ApiBase.TrimEnd('/')}/api/parking/events" +
                          $"?from={Uri.EscapeDataString(fromStr)}" +
                          $"&to={Uri.EscapeDataString(toStr)}" +
                          $"&page={page}&size={_cfg.PageSize}";

            if (!string.IsNullOrEmpty(_lotteCfg.Keyword))
                url += $"&keyword={Uri.EscapeDataString(_lotteCfg.Keyword)}";

            var doc = await api.GetJsonAsync(url, ct);
            if (doc is null) { LogError($"Trang {page} — không nhận được response."); break; }

            var root = doc.RootElement;

            // Trích data[] — thử các cấu trúc phổ biến
            JsonElement dataEl = default;
            bool found = root.TryGetProperty("data", out dataEl)
                      || root.TryGetProperty("content", out dataEl)
                      || root.TryGetProperty("items", out dataEl)
                      || root.TryGetProperty("records", out dataEl);

            if (!found || dataEl.ValueKind != JsonValueKind.Array)
            {
                // data là object với nested content
                if (root.TryGetProperty("data", out var dataObj) &&
                    dataObj.TryGetProperty("content", out dataEl))
                    found = true;
            }

            if (!found || dataEl.ValueKind != JsonValueKind.Array)
            {
                LogWarn($"Trang {page} — không tìm thấy mảng data.");
                break;
            }

            var records = dataEl.EnumerateArray().ToList();
            _stats.Event += records.Count;
            LogInfo($"Trang {page}: {records.Count} sự kiện.");

            if (records.Count == 0) break;

            total += records.Count;

            foreach (var rec in records)
            {
                if (ct.IsCancellationRequested) break;
                await ProcessRecordAsync(api, rec, day, outDir, ct);
                await SleepAsync();
            }

            ReportProgress();

            // Có thêm trang?
            hasMore = records.Count >= _cfg.PageSize;
            if (root.TryGetProperty("totalPages", out var tp) &&
                tp.TryGetInt32(out var totalPages))
                hasMore = page < totalPages;
            if (root.TryGetProperty("last", out var lastEl) &&
                lastEl.ValueKind == JsonValueKind.True)
                hasMore = false;

            page++;
        }
    }

    private async Task ProcessRecordAsync(ApiHelper api, JsonElement rec,
                                           DayRange day, string outDir, CancellationToken ct)
    {
        // ── Trích thông tin cơ bản ────────────────────────────────────────
        var plateIn  = rec.TryGetString("PlateIn")  ?? rec.TryGetString("plateIn")  ?? "";
        var plateOut = rec.TryGetString("PlateOut") ?? rec.TryGetString("plateOut") ?? "";
        var plateReg = rec.TryGetString("RegisteredPlate")
                    ?? rec.TryGetString("registeredPlate")
                    ?? rec.TryGetString("CardPlate") ?? rec.TryGetString("cardPlate") ?? "";
        var cardGroup = rec.TryGetString("CardGroup") ?? rec.TryGetString("cardGroup") ?? "";
        var laneRaw   = rec.TryGetString("LaneName") ?? rec.TryGetString("laneName")
                     ?? rec.TryGetString("Lane")     ?? rec.TryGetString("lane") ?? "unknown";

        // ── Keyword filter ────────────────────────────────────────────────
        if (!MatchKeyword(_lotteCfg.Keyword, plateIn, plateOut, plateReg, cardGroup))
        {
            _stats.Skipped++;
            return;
        }

        // ── GT filter ─────────────────────────────────────────────────────
        if (_cfg.OnlyGT)
        {
            var pIn  = NormPlate(plateIn);
            var pOut = NormPlate(plateOut);
            var pReg = NormPlate(plateReg);
            bool hasGt = (pIn == pOut && !string.IsNullOrEmpty(pIn))
                      || (!string.IsNullOrEmpty(pReg) && (pIn == pReg || pOut == pReg));
            if (!hasGt) { _stats.Skipped++; return; }
        }

        // ── Thời gian sự kiện ─────────────────────────────────────────────
        var dtStr = rec.TryGetString("CreatedAt") ?? rec.TryGetString("createdAt")
                 ?? rec.TryGetString("EventTime") ?? rec.TryGetString("eventTime")
                 ?? day.Start.ToString("yyyy-MM-ddTHH:mm:ss");
        if (!DateTime.TryParse(dtStr, out var dt)) dt = day.Start;

        var buoi = VehicleType.HourToBuoi(dt.Hour);
        var lane = VehicleType.SafeFileName(laneRaw);
        var plate = NormPlate(string.IsNullOrEmpty(plateOut) ? plateIn : plateOut);
        if (string.IsNullOrEmpty(plate)) plate = "UNKNOWN";

        // ── Phân loại xe ──────────────────────────────────────────────────
        var images = ExtractImages(rec);
        if (images.Count == 0) { _stats.Skipped++; return; }

        _stats.Found++;

        // ── Kiểm tra ảnh xấu ──────────────────────────────────────────────
        var badReason = GetBadReason(plateIn, plateOut, plateReg);

        foreach (var (description, imgUrl) in images)
        {
            if (ct.IsCancellationRequested) return;

            // Phân loại loại ảnh
            var imgType = VehicleType.CategorizeByKeyword(
                description, cardGroup,
                _lotteCfg.KeywordToanCanh, _lotteCfg.KeywordXeMay,
                _lotteCfg.KeywordXeDap, _lotteCfg.KeywordOTo);

            if (!IsVtypeAllowed(imgType)) continue;
            if (!CanSave(lane, imgType, buoi)) { _stats.Skipped++; continue; }

            // Tải ảnh
            byte[]? imgData = null;
            if (_lotteCfg.UseMinIO && !imgUrl.StartsWith("http", StringComparison.OrdinalIgnoreCase))
            {
                imgData = await ApiHelper.MinioDownloadAsync(
                    _lotteCfg.MinioEndpoint, _lotteCfg.MinioBucket,
                    _lotteCfg.MinioAccessKey, _lotteCfg.MinioSecretKey,
                    imgUrl, ct);
            }
            else if (!string.IsNullOrEmpty(imgUrl))
            {
                imgData = await api.DownloadBytesAsync(imgUrl, ct);
            }

            if (imgData is null || imgData.Length == 0) { _stats.Error++; continue; }

            if (badReason is not null && _cfg.CollectBad)
            {
                // Lưu ảnh xấu
                var badPath = FileHelper.BuildBadSavePath(
                    _cfg.OutputDir, lane, badReason, dt, plate);
                if (await FileHelper.SaveBytesAsync(badPath, imgData))
                    _stats.BadSaved++;
                continue;
            }
            else if (badReason is not null)
            {
                _stats.Skipped++;
                continue;
            }

            var savePath = FileHelper.BuildSavePath(
                _cfg.OutputDir, imgType, day.Label, buoi, lane, dt, plate);

            if (await FileHelper.SaveBytesAsync(savePath, imgData))
            {
                _stats.Saved++;
                RecordSave(lane, imgType, buoi);
                LogOk($"Lưu: {Path.GetFileName(savePath)}  [{imgType}]");
            }
            else
            {
                _stats.Skipped++;
            }
        }
    }

    // Trích URLs/keys ảnh từ record
    private static List<(string Description, string Url)> ExtractImages(JsonElement rec)
    {
        var result = new List<(string, string)>();
        // Cấu trúc: { "images": [{"description":"...", "url":"..."}, ...] }
        if (rec.TryGetProperty("images", out var imgs) && imgs.ValueKind == JsonValueKind.Array)
        {
            foreach (var img in imgs.EnumerateArray())
            {
                var desc = img.TryGetString("description") ?? img.TryGetString("imageType") ?? "";
                var url  = img.TryGetString("url") ?? img.TryGetString("imageUrl") ?? "";
                if (!string.IsNullOrEmpty(url)) result.Add((desc, url));
            }
        }
        // Fallback: imageIn / imageOut / imageFullIn / imageFullOut fields
        foreach (var field in new[] { "imageIn", "imageOut", "imageFullIn", "imageFullOut",
                                      "imageFull", "imagePlate", "imageUrl" })
        {
            if (rec.TryGetProperty(field, out var el) && el.ValueKind == JsonValueKind.String)
            {
                var url = el.GetString();
                if (!string.IsNullOrEmpty(url)) result.Add((field, url));
            }
        }
        return result;
    }

    private static string? GetBadReason(string plateIn, string plateOut, string plateReg)
    {
        var pIn  = NormPlate(plateIn);
        var pOut = NormPlate(plateOut);
        var pReg = NormPlate(plateReg);

        if (string.IsNullOrEmpty(pIn) && string.IsNullOrEmpty(pOut))
            return "none";
        if (!string.IsNullOrEmpty(pIn) && !string.IsNullOrEmpty(pOut) && pIn != pOut)
            return "in_out_mismatch";
        if (!string.IsNullOrEmpty(pReg))
        {
            if ((!string.IsNullOrEmpty(pIn) && pIn != pReg) ||
                (!string.IsNullOrEmpty(pOut) && pOut != pReg))
                return "register_mismatch";
        }
        return null;
    }
}

// Extension để đọc optional string từ JsonElement
internal static class JsonElementExt
{
    public static string? TryGetString(this JsonElement el, string key)
    {
        if (el.TryGetProperty(key, out var prop) && prop.ValueKind == JsonValueKind.String)
            return prop.GetString();
        return null;
    }
}
