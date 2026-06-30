using Microsoft.Data.Sqlite;

namespace SlotMonitor.Data;

/// <summary>
/// Một bản ghi thay đổi trạng thái.
/// slot_id/slot_name: rỗng nếu detect toàn frame, có giá trị nếu theo slot box.
/// </summary>
public sealed record StateChangeRecord
{
    public long     Id         { get; set; }
    public string   CameraId   { get; set; } = "";
    public string   CameraName { get; set; } = "";
    public string   SlotId     { get; set; } = "";   // "" = whole-frame mode
    public string   SlotName   { get; set; } = "";
    public DateTime OccurredAt { get; set; }
    public string   PrevState  { get; set; } = "";
    public string   NewState   { get; set; } = "";
    public float    Confidence { get; set; }
    public int      DetCount   { get; set; }
    public string   ImagePath  { get; set; } = "";
}

/// <summary>
/// SQLite wrapper lưu lịch sử thay đổi trạng thái.
/// Thread-safe: tất cả thao tác DB đều trong lock.
/// Hỗ trợ migration: tự thêm cột slot_id/slot_name nếu DB cũ.
/// </summary>
public sealed class SlotDb : IDisposable
{
    private readonly SqliteConnection _conn;
    private readonly object           _lock = new();

    public SlotDb(string dbPath)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(dbPath) ?? ".");
        _conn = new SqliteConnection($"Data Source={dbPath}");
        _conn.Open();
        InitSchema();
        MigrateSchema();
    }

    private void InitSchema()
    {
        // Mỗi lệnh chạy riêng để tránh lỗi khi DB cũ chưa có cột slot_id
        Exec("""
            CREATE TABLE IF NOT EXISTS state_changes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                camera_id   TEXT    NOT NULL,
                camera_name TEXT,
                slot_id     TEXT,
                slot_name   TEXT,
                occurred_at TEXT    NOT NULL,
                prev_state  TEXT,
                new_state   TEXT,
                confidence  REAL,
                det_count   INTEGER,
                image_path  TEXT
            )
            """);
        Exec("""
            CREATE INDEX IF NOT EXISTS idx_cam_time
                ON state_changes (camera_id, occurred_at DESC)
            """);
    }

    private void MigrateSchema()
    {
        // Thêm cột mới nếu DB cũ chưa có (ALTER TABLE IF NOT EXISTS không tồn tại trong SQLite)
        foreach (var col in new[] { ("slot_id", "TEXT"), ("slot_name", "TEXT") })
        {
            try { Exec($"ALTER TABLE state_changes ADD COLUMN {col.Item1} {col.Item2}"); }
            catch { /* cột đã tồn tại — bỏ qua */ }
        }
        // Tạo index slot sau khi đã chắc chắn cột tồn tại
        try { Exec("CREATE INDEX IF NOT EXISTS idx_slot_time ON state_changes (slot_id, occurred_at DESC)"); }
        catch { }
    }

    public void Insert(StateChangeRecord r)
    {
        lock (_lock)
        {
            using var cmd = _conn.CreateCommand();
            cmd.CommandText = """
                INSERT INTO state_changes
                    (camera_id, camera_name, slot_id, slot_name,
                     occurred_at, prev_state, new_state, confidence, det_count, image_path)
                VALUES
                    ($camId, $camName, $slotId, $slotName,
                     $at, $prev, $new, $conf, $det, $img)
                """;
            cmd.Parameters.AddWithValue("$camId",   r.CameraId);
            cmd.Parameters.AddWithValue("$camName",  r.CameraName);
            cmd.Parameters.AddWithValue("$slotId",  r.SlotId);
            cmd.Parameters.AddWithValue("$slotName", r.SlotName);
            cmd.Parameters.AddWithValue("$at",      r.OccurredAt.ToString("o"));
            cmd.Parameters.AddWithValue("$prev",    r.PrevState);
            cmd.Parameters.AddWithValue("$new",     r.NewState);
            cmd.Parameters.AddWithValue("$conf",    r.Confidence);
            cmd.Parameters.AddWithValue("$det",     r.DetCount);
            cmd.Parameters.AddWithValue("$img",     r.ImagePath);
            cmd.ExecuteNonQuery();
        }
    }

    public List<StateChangeRecord> Query(string? cameraId = null, string? slotId = null, int limit = 1000)
    {
        lock (_lock)
        {
            using var cmd = _conn.CreateCommand();
            var where = new List<string>();
            if (cameraId is not null) { where.Add("camera_id=$cam");  cmd.Parameters.AddWithValue("$cam",  cameraId); }
            if (slotId   is not null) { where.Add("slot_id=$slot");   cmd.Parameters.AddWithValue("$slot", slotId);   }

            cmd.CommandText =
                "SELECT id,camera_id,camera_name,slot_id,slot_name," +
                "       occurred_at,prev_state,new_state,confidence,det_count,image_path " +
                "FROM state_changes " +
                (where.Count > 0 ? $"WHERE {string.Join(" AND ", where)} " : "") +
                "ORDER BY occurred_at DESC LIMIT $lim";
            cmd.Parameters.AddWithValue("$lim", limit);

            var list = new List<StateChangeRecord>();
            using var rd = cmd.ExecuteReader();
            while (rd.Read())
            {
                list.Add(new StateChangeRecord
                {
                    Id         = rd.GetInt64(0),
                    CameraId   = rd.GetString(1),
                    CameraName = rd.IsDBNull(2)  ? "" : rd.GetString(2),
                    SlotId     = rd.IsDBNull(3)  ? "" : rd.GetString(3),
                    SlotName   = rd.IsDBNull(4)  ? "" : rd.GetString(4),
                    OccurredAt = DateTime.Parse(rd.GetString(5)),
                    PrevState  = rd.IsDBNull(6)  ? "" : rd.GetString(6),
                    NewState   = rd.IsDBNull(7)  ? "" : rd.GetString(7),
                    Confidence = rd.IsDBNull(8)  ? 0f : (float)rd.GetDouble(8),
                    DetCount   = rd.IsDBNull(9)  ? 0  : rd.GetInt32(9),
                    ImagePath  = rd.IsDBNull(10) ? "" : rd.GetString(10),
                });
            }
            return list;
        }
    }

    private void Exec(string sql)
    {
        lock (_lock)
        {
            using var cmd = _conn.CreateCommand();
            cmd.CommandText = sql;
            cmd.ExecuteNonQuery();
        }
    }

    public void Dispose() => _conn.Dispose();
}
