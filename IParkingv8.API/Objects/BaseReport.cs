namespace IParkingv8.API.Objects
{
    public class BaseReport<T> where T : class
    {
        public int DurationInMillisecond { get; set; }
        public int TotalCount { get; set; }
        public int TotalPage { get; set; }
        public int PageSize { get; set; }
        public int PageIndex { get; set; }
        public List<T> Data { get; set; } = [];
        public AdditionalData? AdditionalData { get; set; }
    }

    public class AdditionalData
    {
        public long TotalDiscountAmount { get; set; }
        public long TotalAmount { get; set; }
        public long TotalPrepaid { get; set; } = 0;
    }
}
