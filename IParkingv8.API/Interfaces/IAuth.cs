using iParkingv8.Object.Objects.Systems;

namespace IParkingv8.API.Interfaces
{
    public interface IAuth
    {
        ServerConfig ServerConfig { get; set; }
        ClientLoginResponse ApiAuthResult { get; set; }
        Task PollingAuthorizeAsync();
        Task<bool> LoginAsync();
        bool Login();
        string Username { get; set; }
        string Password { get; set; }
    }
}

