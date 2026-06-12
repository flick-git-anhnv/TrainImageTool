using iParkingv8.Object;
using iParkingv8.Object.Objects.Users;
using IParkingv8.API.Interfaces;
using IParkingv8.API.Objects;
using Kztek.Object;
using Kztek.Tool;
using RestSharp;
using System.Runtime.CompilerServices;
using static IParkingv8.API.Implementation.v8.ApiUrlManagement;

namespace IParkingv8.API.Implementation.v8
{
    public class UserServicev8(IAuth auth) : IUserService
    {
        #region Properties
        public IAuth Auth { get; set; } = auth;

        public async Task<bool> ChangePassword(string userId, string username, string newPassword)
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}users/{userId}/reset-password";
            string baseLog = "Change user password";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog));
            Dictionary<string, string> headers = new()
            {
                { "Authorization","Bearer " + Auth.ApiAuthResult.AccessToken  }
            };
            var body = new
            {
                id = userId,
                username = username,
                password = newPassword,
                confirmPassword = newPassword
            };
            var apiResponse = await Kztek.Api.ApiHelper.GeneralJsonAPIAsync(apiUrl, body, headers, null, 10000, Method.Put);
            return apiResponse.IsSuccess;
        }

        #endregion

        #region Public Functions
        public async Task<Tuple<List<User>, string>> GetUserDataAsync([CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "")
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{ApiUrlManagement.SearchObjectDataRoute(EmApiObjectType.USERS)}";
            string baseLog = "Get All User";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);
            Dictionary<string, string> headers = new()
            {
                { "Authorization","Bearer " + Auth.ApiAuthResult.AccessToken  }
            };

            var body = new
            {
                paging = false,
                pageIndex = 0,
                pageSize = 10,
                filter = string.Empty,
            };
            var apiResponse = await Kztek.Api.ApiHelper.GeneralJsonAPIAsync(apiUrl, body, headers, null, 10000, Method.Post, callerName, lineNumber, filePath);
            if (apiResponse.IsSuccess)
            {
                try
                {
                    var kzBaseResponse = Newtonsoft.Json.JsonConvert.DeserializeObject<BaseResponse<List<User>>>(apiResponse.Response);
                    if (kzBaseResponse == null)
                    {
                        return Tuple.Create<List<User>, string>([], "Error Convert Json Data" + apiResponse.Response);
                    }
                    if (kzBaseResponse.Data == null)
                    {
                        return Tuple.Create<List<User>, string>([], kzBaseResponse.DetailCode);
                    }
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Success"), callerName, lineNumber, filePath);
                    return Tuple.Create<List<User>, string>(kzBaseResponse.Data, kzBaseResponse.DetailCode);
                }
                catch (Exception ex)
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error: " + apiResponse.Response, ex, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return Tuple.Create<List<User>, string>([], ex.Message);
                }
            }
            else
            {
                if (apiResponse.ApiStatusCode == 401)
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error", "Un Auth", ActionType: EmSystemActionType.WARNING), callerName, lineNumber, filePath);
                    await Auth.LoginAsync();
                    return await GetUserDataAsync(callerName, lineNumber, filePath);
                }
                else
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error Code", apiResponse.ApiStatusCode, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return Tuple.Create<List<User>, string>([], apiResponse.Response);
                }
            }
        }

        public async Task GetUserDetailAsync([CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "")
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{ApiUrlManagement.GetInitRoute(EmApiObjectType.USERS)}/info";
            string baseLog = "Get Login User Detail";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);
            Dictionary<string, string> headers = new()
            {
                { "Authorization","Bearer " + Auth.ApiAuthResult.AccessToken  }
            };
            var apiResponse = await Kztek.Api.ApiHelper.GeneralJsonAPIAsync(apiUrl, null, headers, null, 10000, Method.Get, callerName, lineNumber, filePath);
            if (apiResponse.IsSuccess)
            {
                try
                {
                    User? user = Newtonsoft.Json.JsonConvert.DeserializeObject<User>(apiResponse.Response);
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Success"), callerName, lineNumber, filePath);
                    StaticPool.SelectedUser = user;
                }
                catch (Exception ex)
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error: " + apiResponse.Response, ex, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    StaticPool.SelectedUser = new User();
                }
            }
            else
            {
                if (apiResponse.ApiStatusCode == 401)
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error", "Un Auth", ActionType: EmSystemActionType.WARNING), callerName, lineNumber, filePath);
                    await Auth.LoginAsync();
                    await GetUserDetailAsync(callerName, lineNumber, filePath);
                }
                else
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error Code", apiResponse.ApiStatusCode, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    StaticPool.SelectedUser = new User();
                }
            }
        }

        public async Task GetClientDetailAsync([CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "")
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}clients/info";
            string baseLog = "Get Login Client Detail";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);
            Dictionary<string, string> headers = new()
            {
                { "Authorization","Bearer " + Auth.ApiAuthResult.AccessToken  }
            };
            var apiResponse = await Kztek.Api.ApiHelper.GeneralJsonAPIAsync(apiUrl, null, headers, null, 10000, Method.Get, callerName, lineNumber, filePath);
            if (apiResponse.IsSuccess)
            {
                try
                {
                    ClientDTO? client = Newtonsoft.Json.JsonConvert.DeserializeObject<ClientDTO>(apiResponse.Response);
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Success"), callerName, lineNumber, filePath);
                    StaticPool.SelectedClient = client;
                }
                catch (Exception ex)
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error: " + apiResponse.Response, ex, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    StaticPool.SelectedClient = new ClientDTO();
                }
            }
            else
            {
                if (apiResponse.ApiStatusCode == 401)
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error", "Un Auth", ActionType: EmSystemActionType.WARNING), callerName, lineNumber, filePath);
                    await Auth.LoginAsync();
                    await GetClientDetailAsync(callerName, lineNumber, filePath);
                }
                else
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error Code", apiResponse.ApiStatusCode, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    StaticPool.SelectedClient = new ClientDTO();
                }
            }
        }
        #endregion
    }
}
