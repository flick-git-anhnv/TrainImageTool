namespace IParkingv8.API.Objects
{
    public class BaseResponse<T> where T : class
    {
        public bool IsSuccessS { get; set; } = true;
        public string Message { get; set; } = string.Empty;
        public string ErrorCode { get; set; } = string.Empty;
        public string DetailCode { get; set; } = string.Empty;
        public string TraceId { get; set; } = string.Empty;
        public ErrorDetail[]? Fields { get; set; } = null;
        public long Revenue { get; set; }
        public long DiscountAmount { get; set; }
        public int DurationInMillisecond { get; set; }
        public int TotalCount { get; set; }
        public int TotalPage { get; set; }
        public int PageSize { get; set; }
        public int PageIndex { get; set; }
        public T? Data { get; set; }
    }
    public class ErrorDetail
    {
        public string Name { get; set; } = string.Empty;
        public string ErrorCode { get; set; } = string.Empty;
    }
}
