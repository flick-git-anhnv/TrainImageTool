using Minio;
using Minio.DataModel.Args;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;

namespace IParkingImage.Helpers;

public class ApiHelper : IDisposable
{
    private readonly HttpClient _http;
    private string? _token;
    private DateTime _tokenExpiry = DateTime.MinValue;

    public ApiHelper(int timeoutSeconds = 30)
    {
        _http = new HttpClient { Timeout = TimeSpan.FromSeconds(timeoutSeconds) };
        _http.DefaultRequestHeaders.Accept.Add(
            new MediaTypeWithQualityHeaderValue("application/json"));
    }

    public void SetBearerToken(string token)
    {
        _token = token;
        _tokenExpiry = DateTime.MaxValue;
        _http.DefaultRequestHeaders.Authorization =
            new AuthenticationHeaderValue("Bearer", token);
    }

    public void ClearAuth() =>
        _http.DefaultRequestHeaders.Authorization = null;

    // ── Lotte authentication ────────────────────────────────────────────────

    public async Task<string?> LotteLoginAsync(string apiBase, string username, string password,
                                                CancellationToken ct = default)
    {
        try
        {
            var body = JsonSerializer.Serialize(new { username, password });
            var req  = new StringContent(body, Encoding.UTF8, "application/json");
            var resp = await _http.PostAsync($"{apiBase.TrimEnd('/')}/api/auth/login", req, ct);
            resp.EnsureSuccessStatusCode();
            var json = await resp.Content.ReadAsStringAsync(ct);
            var doc  = JsonDocument.Parse(json);
            // Thử các field phổ biến
            foreach (var field in new[] { "token", "access_token", "accessToken", "data" })
            {
                if (doc.RootElement.TryGetProperty(field, out var el) &&
                    el.ValueKind == JsonValueKind.String)
                {
                    var t = el.GetString();
                    if (!string.IsNullOrEmpty(t)) { SetBearerToken(t); return t; }
                }
            }
            // Nested: data.token
            if (doc.RootElement.TryGetProperty("data", out var data) &&
                data.TryGetProperty("token", out var tok))
            {
                var t = tok.GetString();
                if (!string.IsNullOrEmpty(t)) { SetBearerToken(t); return t; }
            }
            return null;
        }
        catch { return null; }
    }

    // ── Parkingv8 OAuth2 ────────────────────────────────────────────────────

    public async Task<string?> P8LoginAsync(
        string loginUrl, string grantType,
        string clientId, string clientSecret,
        string username, string password,
        CancellationToken ct = default)
    {
        try
        {
            var form = new Dictionary<string, string>
            {
                ["grant_type"]    = grantType,
                ["client_id"]     = clientId,
                ["client_secret"] = clientSecret,
            };
            if (grantType == "password")
            {
                form["username"] = username;
                form["password"] = password;
            }
            var resp = await _http.PostAsync(loginUrl,
                new FormUrlEncodedContent(form), ct);
            resp.EnsureSuccessStatusCode();
            var json = await resp.Content.ReadAsStringAsync(ct);
            var doc  = JsonDocument.Parse(json);
            if (doc.RootElement.TryGetProperty("access_token", out var el))
            {
                var t = el.GetString();
                if (!string.IsNullOrEmpty(t)) { SetBearerToken(t); return t; }
            }
            return null;
        }
        catch { return null; }
    }

    // ── Generic GET ─────────────────────────────────────────────────────────

    public async Task<JsonDocument?> GetJsonAsync(string url, CancellationToken ct = default)
    {
        try
        {
            var resp = await _http.GetAsync(url, ct);
            resp.EnsureSuccessStatusCode();
            var json = await resp.Content.ReadAsStringAsync(ct);
            return JsonDocument.Parse(json);
        }
        catch { return null; }
    }

    // ── Generic POST ────────────────────────────────────────────────────────

    public async Task<JsonDocument?> PostJsonAsync(string url, object body,
                                                   CancellationToken ct = default)
    {
        try
        {
            var json = JsonSerializer.Serialize(body);
            var req  = new StringContent(json, Encoding.UTF8, "application/json");
            var resp = await _http.PostAsync(url, req, ct);
            resp.EnsureSuccessStatusCode();
            var respJson = await resp.Content.ReadAsStringAsync(ct);
            return JsonDocument.Parse(respJson);
        }
        catch { return null; }
    }

    // ── Image download ──────────────────────────────────────────────────────

    public async Task<byte[]?> DownloadBytesAsync(string url, CancellationToken ct = default)
    {
        try
        {
            var resp = await _http.GetAsync(url, ct);
            resp.EnsureSuccessStatusCode();
            return await resp.Content.ReadAsByteArrayAsync(ct);
        }
        catch { return null; }
    }

    // ── Base64 decode ───────────────────────────────────────────────────────

    public static byte[]? DecodeBase64(string b64)
    {
        try
        {
            var s = b64.Trim().Replace("\n", "").Replace("\r", "").Replace(" ", "");
            int pad = (4 - s.Length % 4) % 4;
            s += new string('=', pad);
            return Convert.FromBase64String(s);
        }
        catch { return null; }
    }

    public static bool LooksBase64(string s) =>
        s.Length >= 64
        && !s.StartsWith("http", StringComparison.OrdinalIgnoreCase)
        && !s.StartsWith("/")
        && System.Text.RegularExpressions.Regex.IsMatch(s[..Math.Min(256, s.Length)],
               @"^[A-Za-z0-9+/\r\n]+=*$");

    // ── MinIO download (via presigned URL or SDK) ───────────────────────────

    public static async Task<byte[]?> MinioDownloadAsync(
        string endpoint, string bucket, string accessKey, string secretKey,
        string objectKey, CancellationToken ct = default)
    {
        try
        {
            var useSSL  = endpoint.StartsWith("https://", StringComparison.OrdinalIgnoreCase);
            var ep      = endpoint.Replace("https://", "").Replace("http://", "").TrimEnd('/');
            var minio   = new Minio.MinioClient()
                            .WithEndpoint(ep)
                            .WithCredentials(accessKey, secretKey)
                            .WithSSL(useSSL)
                            .Build();

            byte[]? result = null;
            using var ms   = new MemoryStream();
            var getArgs    = new Minio.DataModel.Args.GetObjectArgs()
                                .WithBucket(bucket)
                                .WithObject(objectKey)
                                .WithCallbackStream((stream, token) =>
                                {
                                    stream.CopyTo(ms);
                                    return Task.CompletedTask;
                                });
            await minio.GetObjectAsync(getArgs, ct);
            result = ms.ToArray();
            return result.Length > 0 ? result : null;
        }
        catch { return null; }
    }

    public void Dispose() => _http.Dispose();
}
