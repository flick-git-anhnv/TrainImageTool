namespace iParkingv6.ApiManager.KzParkingv3Apis
{
    public class KzBaseResponseData<T> where T : class
    {
        public MetaData metadata { get; set; }
        public T data { get; set; } = null;
    }
    public class KzBaseResponse
    {
        public bool isSuccess { get; set; }
        public string message { get; set; }
    }
    public class MetaData
    {
        public bool success { get; set; }
        public MetaDataDetail message { get; set; }
    }
    public class MetaDataDetail
    {
        public string code { get; set; }
        public string value { get; set; }
    }
}
