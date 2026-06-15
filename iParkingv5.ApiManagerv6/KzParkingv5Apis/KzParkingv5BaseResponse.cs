namespace iParkingv5.ApiManager.KzParkingv5Apis
{
    public class KzParkingv5BaseResponse<T> where T : class
    {
        public decimal revenue { get; set; }
        public long TotalCashAmount { get; set; }
        public long TotalQrAmount { get; set; }
        public long TotalWalletAmount { get; set; }
        public bool isSuccess { get; set; } = true;
        public string message { get; set; } = string.Empty;
        public string errorCode { get; set; } = string.Empty;
        public string detailCode { get; set; } = string.Empty;
        public string traceId { get; set; } = string.Empty;
        public ErrorDetail[]? fields { get; set; } = null;

        public int durationInMillisecond { get; set; }
        public int totalCount { get; set; }
        public int totalPage { get; set; }
        public int pageSize { get; set; }
        public string laneName { get; set; }
        public T data { get; set; }
    }

    public class ErrorDetail
    {
        public string name { get; set; }
        public string errorCode { get; set; }
    }

}
