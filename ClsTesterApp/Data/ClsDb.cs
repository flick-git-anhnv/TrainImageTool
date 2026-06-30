using ClsTester.Models;
using Microsoft.Data.Sqlite;

namespace ClsTester.Data;

/// <summary>
/// SQLite persistence cho lịch sử thay đổi phân loại.
/// Thread-safe: INSERT dùng lock, SELECT tạo connection riêng.
/// </summary>
public sealed class ClsDb : IDisposable
{
    private readonly string           _connStr;
    private readonly SqliteConnection _conn;
    private readonly object           _writeLock = new();

    public ClsDb(string dbPath)
    {
        var dir = Path.GetDirectoryName(dbPath);
        if (!string.IsNullOrEmpty(dir))
            Directory.CreateDirectory(dir);

        _connStr = $"Data Source={dbPath}";
        _conn    = new SqliteConnection(_connStr);
        _conn.Open();
        CreateSchema();
        MigrateSchema();
    }

    private void CreateSchema()
    {
        using var cmd = _conn.CreateCommand();
        cmd.CommandText = """
            CREATE TABLE IF NOT EXISTS cls_changes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                camera_id   TEXT    NOT NULL DEFAULT '',
                camera_name TEXT    NOT NULL DEFAULT '',
                region_id   TEXT    NOT NULL,
                region_name TEXT    NOT NULL,
                occurred_at TEXT    NOT NULL,
                prev_class  TEXT    NOT NULL,
                new_class   TEXT    NOT NULL,
                confidence  REAL    NOT NULL,
                image_path  TEXT    NOT NULL DEFAULT '',
                top_n_json  TEXT    NOT NULL DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_occurred ON cls_changes(occurred_at DESC);
            CREATE INDEX IF NOT EXISTS idx_region   ON cls_changes(region_id);
            """;
        cmd.ExecuteNonQuery();
    }

    private void MigrateSchema()
    {
        // Thêm cột camera_id/camera_name vào DB cũ (nếu chưa có)
        try
        {
            using var cmd = _conn.CreateCommand();
            cmd.CommandText = "ALTER TABLE cls_changes ADD COLUMN camera_id TEXT NOT NULL DEFAULT ''";
            cmd.ExecuteNonQuery();
        }
        catch { /* cột đã tồn tại */ }

        try
        {
            using var cmd = _conn.CreateCommand();
            cmd.CommandText = "ALTER TABLE cls_changes ADD COLUMN camera_name TEXT NOT NULL DEFAULT ''";
            cmd.ExecuteNonQuery();
        }
        catch { /* cột đã tồn tại */ }

        // Tạo index sau khi cột chắc chắn tồn tại
        try
        {
            using var cmd = _conn.CreateCommand();
            cmd.CommandText = "CREATE INDEX IF NOT EXISTS idx_camera ON cls_changes(camera_id)";
            cmd.ExecuteNonQuery();
        }
        catch { }
    }

    // ── Write ─────────────────────────────────────────────────────────────

    public void Insert(ClsChangeRecord rec)
    {
        lock (_writeLock)
        {
            using var cmd = _conn.CreateCommand();
            cmd.CommandText = """
                INSERT INTO cls_changes
                    (camera_id, camera_name, region_id, region_name,
                     occurred_at, prev_class, new_class, confidence, image_path, top_n_json)
                VALUES
                    (@cam, @cname, @rid, @rname, @at, @prev, @new, @conf, @img, @topn)
                """;
            cmd.Parameters.AddWithValue("@cam",   rec.CameraId);
            cmd.Parameters.AddWithValue("@cname", rec.CameraName);
            cmd.Parameters.AddWithValue("@rid",   rec.RegionId);
            cmd.Parameters.AddWithValue("@rname", rec.RegionName);
            cmd.Parameters.AddWithValue("@at",    rec.OccurredAt.ToString("o"));
            cmd.Parameters.AddWithValue("@prev",  rec.PrevClass);
            cmd.Parameters.AddWithValue("@new",   rec.NewClass);
            cmd.Parameters.AddWithValue("@conf",  rec.Confidence);
            cmd.Parameters.AddWithValue("@img",   rec.ImagePath);
            cmd.Parameters.AddWithValue("@topn",  rec.TopNJson);
            cmd.ExecuteNonQuery();
        }
    }

    // ── Query ─────────────────────────────────────────────────────────────

    public List<ClsChangeRecord> Query(
        string? cameraId = null,
        string? regionId = null,
        DateTime? from   = null,
        DateTime? to     = null,
        int limit        = 500)
    {
        using var conn = new SqliteConnection(_connStr);
        conn.Open();

        using var cmd = conn.CreateCommand();
        var where = new List<string>();
        if (cameraId is not null) { where.Add("camera_id = @cam");    cmd.Parameters.AddWithValue("@cam",  cameraId); }
        if (regionId is not null) { where.Add("region_id = @rid");    cmd.Parameters.AddWithValue("@rid",  regionId); }
        if (from     is not null) { where.Add("occurred_at >= @from"); cmd.Parameters.AddWithValue("@from", from.Value.ToString("o")); }
        if (to       is not null) { where.Add("occurred_at <= @to");   cmd.Parameters.AddWithValue("@to",   to.Value.ToString("o")); }

        var ws = where.Count > 0 ? "WHERE " + string.Join(" AND ", where) : "";
        cmd.CommandText = $"SELECT * FROM cls_changes {ws} ORDER BY id DESC LIMIT @lim";
        cmd.Parameters.AddWithValue("@lim", limit);

        var result = new List<ClsChangeRecord>();
        using var reader = cmd.ExecuteReader();
        while (reader.Read())
        {
            result.Add(new ClsChangeRecord
            {
                Id         = reader.GetInt32(reader.GetOrdinal("id")),
                CameraId   = reader.GetString(reader.GetOrdinal("camera_id")),
                CameraName = reader.GetString(reader.GetOrdinal("camera_name")),
                RegionId   = reader.GetString(reader.GetOrdinal("region_id")),
                RegionName = reader.GetString(reader.GetOrdinal("region_name")),
                OccurredAt = DateTime.Parse(reader.GetString(reader.GetOrdinal("occurred_at"))),
                PrevClass  = reader.GetString(reader.GetOrdinal("prev_class")),
                NewClass   = reader.GetString(reader.GetOrdinal("new_class")),
                Confidence = (float)reader.GetDouble(reader.GetOrdinal("confidence")),
                ImagePath  = reader.GetString(reader.GetOrdinal("image_path")),
                TopNJson   = reader.GetString(reader.GetOrdinal("top_n_json")),
            });
        }
        return result;
    }

    public int TotalCount()
    {
        using var cmd = _conn.CreateCommand();
        cmd.CommandText = "SELECT COUNT(*) FROM cls_changes";
        return Convert.ToInt32(cmd.ExecuteScalar());
    }

    public List<(string Id, string Name)> DistinctRegions()
    {
        using var cmd = _conn.CreateCommand();
        cmd.CommandText = "SELECT DISTINCT region_id, region_name FROM cls_changes ORDER BY region_name";
        var result = new List<(string, string)>();
        using var reader = cmd.ExecuteReader();
        while (reader.Read()) result.Add((reader.GetString(0), reader.GetString(1)));
        return result;
    }

    public List<(string Id, string Name)> DistinctCameras()
    {
        using var cmd = _conn.CreateCommand();
        cmd.CommandText = "SELECT DISTINCT camera_id, camera_name FROM cls_changes WHERE camera_id != '' ORDER BY camera_name";
        var result = new List<(string, string)>();
        using var reader = cmd.ExecuteReader();
        while (reader.Read()) result.Add((reader.GetString(0), reader.GetString(1)));
        return result;
    }

    public void DeleteRegion(string regionId)
    {
        lock (_writeLock)
        {
            using var cmd = _conn.CreateCommand();
            cmd.CommandText = "DELETE FROM cls_changes WHERE region_id = @rid";
            cmd.Parameters.AddWithValue("@rid", regionId);
            cmd.ExecuteNonQuery();
        }
    }

    public void DeleteAll()
    {
        lock (_writeLock)
        {
            using var cmd = _conn.CreateCommand();
            cmd.CommandText = "DELETE FROM cls_changes";
            cmd.ExecuteNonQuery();
        }
    }

    public void Dispose() => _conn.Dispose();
}
