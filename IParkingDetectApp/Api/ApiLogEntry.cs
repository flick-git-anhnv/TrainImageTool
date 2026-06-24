namespace IParkingDetect.Api;

public enum ApiLogStatus { Processing, Done, Error }

public sealed record ApiLogEntry(
    Guid           Id,
    string         ImageName,   // filename only
    string         ImagePath,   // full path
    DateTimeOffset StartTime,
    ApiLogStatus   Status,
    long?          InferMs  = null,
    long?          TotalMs  = null,
    string?        ErrorMsg = null
)
{
    /// <summary>Timestamp khi xử lý xong (StartTime + TotalMs).</summary>
    public DateTimeOffset? EndTime =>
        TotalMs.HasValue ? StartTime.AddMilliseconds(TotalMs.Value) : null;
}
