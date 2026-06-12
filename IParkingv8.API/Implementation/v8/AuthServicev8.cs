using iParkingv8.Object.Objects.Systems;
using IParkingv8.API.Interfaces;
using Kztek.Object;
using Kztek.Tool;
using RestSharp;

namespace IParkingv8.API.Implementation.v8
{
    public class AuthServicev8(ServerConfig serverConfig) : IAuth
    {
        #region Properties
        public ServerConfig ServerConfig { get; set; } = serverConfig;
        public string Username { get; set; } = "";
        public string Password { get; set; } = "";
        public ClientLoginResponse ApiAuthResult { get; set; } = new ClientLoginResponse();
        public string ClientId { get; set; } = "";

        #endregion

        #region Constructor
        #endregion

        #region Public Function
        public async Task PollingAuthorizeAsync()
        {
            while (true)
            {
                try
                {
                    await LoginAsync();
                }
                finally
                {
                    GC.Collect();
                    if (string.IsNullOrEmpty(ApiAuthResult?.AccessToken))
                    {
                        await Task.Delay(TimeSpan.FromSeconds(1));
                    }
                    else
                    {
                        await Task.Delay(TimeSpan.FromMinutes(30));
                    }
                }
            }
        }

        public async Task<bool> LoginAsync()
        {
            if (!string.IsNullOrEmpty(ServerConfig.Username) && !string.IsNullOrEmpty(ServerConfig.Password))
            {
                return await LoginBySaAsync();
            }
            else
            {
                return await LoginByAccountAsync();
            }
        }
        private async Task<bool> LoginBySaAsync()
        {
            string loginUrl = ServerConfig.LoginUrl;
            if (loginUrl[^1] == '/')
            {
                loginUrl += "connect/token";
            }
            else
            {
                loginUrl += "/connect/token";
            }
            var options = new RestClientOptions(loginUrl);
            var client = new RestClient(options);
            var request = new RestRequest(loginUrl, Method.Post);
            request.AddHeader("Content-Type", "application/x-www-form-urlencoded");
            request.AddParameter("client_id", this.ServerConfig.Username);
            request.AddParameter("client_secret", this.ServerConfig.Password);
            request.AddParameter("grant_type", "client_credentials");

            string baseLog = "Connect to server";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog));

            RestResponse response = await client.ExecuteAsync(request);
            if (response.IsSuccessful)
            {
                try
                {
                    var loginResponse = Newtonsoft.Json.JsonConvert.DeserializeObject<Rootobject>(response.Content ?? "");
                    ApiAuthResult = new ClientLoginResponse()
                    {
                        AccessToken = loginResponse?.access_token ?? "",
                        RefreshToken = loginResponse?.Refresh_token ?? "",
                        Scope = ServerConfig.Scope,
                    };
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Success", ApiAuthResult));
                    return true;
                }
                catch (Exception ex)
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error", ex));
                    return false;
                }
            }
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error Code", response.StatusCode, ActionType: EmSystemActionType.ERROR));
            return false;
        }
        private async Task<bool> LoginByAccountAsync()
        {
            string loginUrl = ServerConfig.LoginUrl;
            if (loginUrl[^1] == '/')
            {
                loginUrl += "connect/token";
            }
            else
            {
                loginUrl += "/connect/token";
            }
            var options = new RestClientOptions(loginUrl);
            var client = new RestClient(options);
            var request = new RestRequest(loginUrl, Method.Post);
            request.AddHeader("Content-Type", "application/x-www-form-urlencoded");
            request.AddParameter("client_id", "27ee5d4a-4251-4e5a-a440-a8f8e22f99a6");
            request.AddParameter("client_secret", "TcMKwrekvf9UIUgNKh");
            request.AddParameter("username", this.Username);
            request.AddParameter("password", this.Password);
            request.AddParameter("grant_type", "password");

            string baseLog = "Connect to server";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog));

            RestResponse response = await client.ExecuteAsync(request);
            if (response.IsSuccessful)
            {
                try
                {
                    var loginResponse = Newtonsoft.Json.JsonConvert.DeserializeObject<Rootobject>(response.Content ?? "");
                    ApiAuthResult = new ClientLoginResponse()
                    {
                        AccessToken = loginResponse?.access_token ?? "",
                        RefreshToken = loginResponse?.Refresh_token ?? "",
                        Scope = ServerConfig.Scope,
                    };
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Success", ApiAuthResult));
                    return true;
                }
                catch (Exception ex)
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error", ex));
                    return false;
                }
            }
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error Code", response.StatusCode, ActionType: EmSystemActionType.ERROR));
            return false;
        }

        public bool Login()
        {
            if (!string.IsNullOrEmpty(ServerConfig.Username) && !string.IsNullOrEmpty(ServerConfig.Password))
            {
                return LoginBySa();
            }
            else
            {
                return LoginByAccount();
            }
        }
        private bool LoginBySa()
        {
            string loginUrl = ServerConfig.LoginUrl;
            if (loginUrl[^1] == '/')
            {
                loginUrl += "connect/token";
            }
            else
            {
                loginUrl += "/connect/token";
            }
            var options = new RestClientOptions(loginUrl);
            var client = new RestClient(options);
            var request = new RestRequest(loginUrl, Method.Post);
            request.AddHeader("Content-Type", "application/x-www-form-urlencoded");
            request.AddParameter("client_id", this.ServerConfig.Username);
            request.AddParameter("client_secret", this.ServerConfig.Password);
            request.AddParameter("grant_type", "client_credentials");

            string baseLog = "Connect to server";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog));

            RestResponse response = client.Execute(request);
            if (response.IsSuccessful)
            {
                try
                {
                    var loginResponse = Newtonsoft.Json.JsonConvert.DeserializeObject<Rootobject>(response.Content ?? "");
                    ApiAuthResult = new ClientLoginResponse()
                    {
                        AccessToken = loginResponse?.access_token ?? "",
                        RefreshToken = loginResponse?.Refresh_token ?? "",
                        Scope = ServerConfig.Scope,
                    };
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Success", ApiAuthResult));
                    return true;
                }
                catch (Exception ex)
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error", ex));
                    return false;
                }
            }
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error Code", response.StatusCode, ActionType: EmSystemActionType.ERROR));
            return false;
        }
        private bool LoginByAccount()
        {
            string loginUrl = ServerConfig.LoginUrl;
            if (loginUrl[^1] == '/')
            {
                loginUrl += "connect/token";
            }
            else
            {
                loginUrl += "/connect/token";
            }
            var options = new RestClientOptions(loginUrl);
            var client = new RestClient(options);
            var request = new RestRequest(loginUrl, Method.Post);
            request.AddHeader("Content-Type", "application/x-www-form-urlencoded");
            request.AddParameter("client_id", "27ee5d4a-4251-4e5a-a440-a8f8e22f99a6");
            request.AddParameter("client_secret", "TcMKwrekvf9UIUgNKh");
            request.AddParameter("username", this.Username);
            request.AddParameter("password", this.Password);
            request.AddParameter("grant_type", "password");

            string baseLog = "Connect to server";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog));

            RestResponse response =  client.Execute(request);
            if (response.IsSuccessful)
            {
                try
                {
                    var loginResponse = Newtonsoft.Json.JsonConvert.DeserializeObject<Rootobject>(response.Content ?? "");
                    ApiAuthResult = new ClientLoginResponse()
                    {
                        AccessToken = loginResponse?.access_token ?? "",
                        RefreshToken = loginResponse?.Refresh_token ?? "",
                        Scope = ServerConfig.Scope,
                    };
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Success", ApiAuthResult));
                    return true;
                }
                catch (Exception ex)
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error", ex));
                    return false;
                }
            }
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error Code", response.StatusCode, ActionType: EmSystemActionType.ERROR));
            return false;
        }

        public class Rootobject
        {
            public string access_token { get; set; } = string.Empty;
            public string Refresh_token { get; set; } = string.Empty;
            public int expires_in { get; set; }
            public string token_type { get; set; } = string.Empty;
            public string scope { get; set; } = string.Empty;
        }
        #endregion
    }
}
