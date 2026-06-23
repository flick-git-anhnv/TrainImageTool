namespace IParkingImage.Config;

public class AppConfig
{
    public string Source { get; set; } = "LotteImage";
    public string FromDate { get; set; } = "2026-01-01 00:00:00";
    public string ToDate { get; set; } = "2026-01-31 23:59:59";
    public string OutputDir { get; set; } = "images_ip";
    public int PageSize { get; set; } = 100;
    public int MaxPages { get; set; } = 10000;
    public double SleepSeconds { get; set; } = 0.1;
    public int MaxPerLane { get; set; } = 0;
    public int MaxPerCategory { get; set; } = 0;
    public int MaxPerBuoi { get; set; } = 0;
    public int Parallel { get; set; } = 1;
    public bool CollectBad { get; set; } = false;
    public bool OnlyGT { get; set; } = false;

    // Bỏ trống = lấy tất cả loại; ví dụ: ["o_to", "xe_may"]
    public List<string> AllowedVtypes { get; set; } = [];

    public LotteConfig Lotte { get; set; } = new();
    public Parkingv8Config Parkingv8 { get; set; } = new();
    public Parkingv6Config Parkingv6 { get; set; } = new();
}

public class LotteConfig
{
    public string ApiBase { get; set; } = "";
    public string Username { get; set; } = "";
    public string Password { get; set; } = "";
    public bool UseMinIO { get; set; } = true;
    public string MinioEndpoint { get; set; } = "";
    public string MinioBucket { get; set; } = "";
    public string MinioAccessKey { get; set; } = "";
    public string MinioSecretKey { get; set; } = "";
    public string KeywordToanCanh { get; set; } = "toàn cảnh";
    public string KeywordXeMay { get; set; } = "xe máy";
    public string KeywordXeDap { get; set; } = "xe đạp";
    public string KeywordOTo { get; set; } = "";
    public string Keyword { get; set; } = "";
}

public class Parkingv8Config
{
    public string LoginUrl { get; set; } = "";
    public string ApiUrl { get; set; } = "";
    public string ClientId { get; set; } = "";
    public string ClientSecret { get; set; } = "";
    public string Username { get; set; } = "";
    public string Password { get; set; } = "";
    public string GrantType { get; set; } = "client_credentials";
    public string EventSource { get; set; } = "exits";
    public string ImgMode { get; set; } = "url";
    public string Keyword { get; set; } = "";
}

public class Parkingv6Config
{
    public string ApiUrl { get; set; } = "";
    public string Token { get; set; } = "";
    public bool UseMinIO { get; set; } = true;
    public string MinioEndpoint { get; set; } = "";
    public string MinioBucket { get; set; } = "";
    public string MinioAccessKey { get; set; } = "";
    public string MinioSecretKey { get; set; } = "";
    public string EventSource { get; set; } = "both";
    public string Keyword { get; set; } = "";
}
