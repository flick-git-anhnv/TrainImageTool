using IParkingImage.Models;

namespace IParkingImage.Helpers;

public static class FileHelper
{
    /// <summary>
    /// Xây đường dẫn lưu ảnh theo cấu trúc chuẩn KZTEK:
    /// <out>/<vehicleFolder>/<subFolder>/<date>/<buoi>/<lane>/<HHmmss_BSX[_suffix].jpg>
    /// </summary>
    public static string BuildSavePath(
        string outputDir, string imgType, string date, string buoi,
        string lane, DateTime dt, string plate, string suffix = "")
    {
        var (vFolder, subFolder) = VehicleType.ImgTypeToPath(imgType);
        var laneClean = VehicleType.SafeFileName(lane);
        var plateClean = VehicleType.SafeFileName(plate);
        var timeStr = dt.ToString("HHmmss");
        var fileName = string.IsNullOrEmpty(suffix)
            ? $"{timeStr}_{plateClean}.jpg"
            : $"{timeStr}_{plateClean}_{suffix}.jpg";

        return Path.Combine(outputDir, vFolder, subFolder, date, buoi, laneClean, fileName);
    }

    public static string BuildBadSavePath(
        string outputDir, string lane, string reason, DateTime dt, string plate)
    {
        var laneClean = VehicleType.SafeFileName(lane);
        var plateClean = VehicleType.SafeFileName(plate);
        var timeStr = dt.ToString("HHmmss");
        return Path.Combine(outputDir, "bad", laneClean,
            $"{timeStr}_{reason}_{plateClean}.jpg");
    }

    public static void EnsureDir(string filePath)
    {
        var dir = Path.GetDirectoryName(filePath);
        if (!string.IsNullOrEmpty(dir))
            Directory.CreateDirectory(dir);
    }

    public static async Task<bool> SaveBytesAsync(string path, byte[] data)
    {
        try
        {
            EnsureDir(path);
            // tránh ghi đè nếu file đã tồn tại
            if (File.Exists(path)) return false;
            await File.WriteAllBytesAsync(path, data);
            return true;
        }
        catch
        {
            return false;
        }
    }

    /// <summary>Đọc done-history JSON từ file, trả về set ngày đã tải.</summary>
    public static HashSet<string> LoadDoneHistory(string filePath)
    {
        try
        {
            if (!File.Exists(filePath)) return [];
            var json = File.ReadAllText(filePath);
            var list = System.Text.Json.JsonSerializer.Deserialize<List<string>>(json);
            return list is null ? [] : [.. list];
        }
        catch
        {
            return [];
        }
    }

    /// <summary>Thêm ngày vào done-history và ghi lại file.</summary>
    public static void AppendDoneHistory(string filePath, string dayLabel, HashSet<string> doneSet)
    {
        lock (filePath)
        {
            doneSet.Add(dayLabel);
            try
            {
                var json = System.Text.Json.JsonSerializer.Serialize(doneSet.ToList());
                File.WriteAllText(filePath, json);
            }
            catch { /* non-fatal */ }
        }
    }

    /// <summary>Xây danh sách DayRange từ [fromDate, toDate] theo ngày.</summary>
    public static List<DayRange> BuildDayList(string fromDateStr, string toDateStr)
    {
        var from = ParseDate(fromDateStr);
        var to   = ParseDate(toDateStr);
        var days = new List<DayRange>();
        var cur  = from.Date;
        while (cur <= to.Date)
        {
            var dayStart = cur;
            var dayEnd   = cur.AddDays(1).AddSeconds(-1);
            // Clamp to user-specified times on first/last day
            if (cur == from.Date) dayStart = from;
            if (cur == to.Date)   dayEnd   = to;
            days.Add(new DayRange(dayStart, dayEnd, cur.ToString("yyyy-MM-dd")));
            cur = cur.AddDays(1);
        }
        return days;
    }

    private static DateTime ParseDate(string s)
    {
        s = s.Trim().Replace("T", " ");
        if (DateTime.TryParseExact(s, "yyyy-MM-dd HH:mm:ss",
                System.Globalization.CultureInfo.InvariantCulture,
                System.Globalization.DateTimeStyles.None, out var dt))
            return dt;
        if (DateTime.TryParse(s, out var dt2)) return dt2;
        throw new ArgumentException($"Không parse được ngày: {s}");
    }
}
