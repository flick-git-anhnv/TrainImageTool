using iParkingv8.Object.Objects.Bases;
using iParkingv8.Object.Objects.Parkings;
using IParkingv8.API.Interfaces;
using Kztek.Api;
using Kztek.Object;
using Kztek.Tool;
using RestSharp;
using System.Runtime.CompilerServices;
using static IParkingv8.API.Implementation.v8.ApiUrlManagement;

namespace IParkingv8.API.Implementation.v8.DataService
{
    public class BlackListedAPI(IAuth auth) : IBlackListed
    {
        public IAuth Auth { get; set; } = auth;
        public async Task<Tuple<BlackedList?, BaseErrorData?>?> GetByCodeAsync(string code, int timeOut = 10000,
                                                       [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true)
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{GetInitRoute(EmApiObjectType.BLACKLISTED)}";
            string baseLog = $"Get BlackListed By Code {code}";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);

            Dictionary<string, string> headers = new()
            {
                { "Authorization","Bearer " + Auth.ApiAuthResult.AccessToken  }
            };
            var parameters = new Dictionary<string, string>()
            {
                { "code",code},
            };
            var apiResponse = await ApiHelper.GeneralJsonAPIAsync(apiUrl, null, headers, parameters, timeOut, Method.Get, callerName, lineNumber, filePath);
            if (apiResponse.IsSuccess)
            {
                try
                {
                    var accessKey = Newtonsoft.Json.JsonConvert.DeserializeObject<BlackedList?>(apiResponse.Response);
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Success", accessKey), callerName, lineNumber, filePath);
                    return Tuple.Create<BlackedList?, BaseErrorData?>(accessKey, null);
                }
                catch (Exception ex)
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error: " + apiResponse.Response, ex, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return Tuple.Create<BlackedList?, BaseErrorData?>(null, null);
                }
            }
            else
            {
                if (apiResponse.ApiStatusCode == 401)
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error", "Un Auth", ActionType: EmSystemActionType.WARNING), callerName, lineNumber, filePath);
                    await Auth.LoginAsync();
                    return await GetByCodeAsync(code, timeOut, callerName, lineNumber, filePath);
                }
                else
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error Code", apiResponse.ApiStatusCode, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    var errorData = Newtonsoft.Json.JsonConvert.DeserializeObject<BaseErrorData?>(apiResponse.Response);
                    if (errorData != null)
                    {
                        errorData.Route = GetInitRoute(EmApiObjectType.BLACKLISTED);
                    }
                    return Tuple.Create<BlackedList?, BaseErrorData?>(null, errorData);
                }
            }
        }
        public Tuple<BlackedList?, BaseErrorData?>? GetByCode(string code, int timeOut = 10000,
                                                       [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true)
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{GetInitRoute(EmApiObjectType.BLACKLISTED)}";
            string baseLog = $"Get BlackedList By Code {code}";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);

            Dictionary<string, string> headers = new()
            {
                { "Authorization","Bearer " + Auth.ApiAuthResult.AccessToken  }
            };
            var parameters = new Dictionary<string, string>()
            {
                { "code", code},
            };
            var apiResponse = ApiHelper.GeneralJsonAPI(apiUrl, null, headers, parameters, timeOut, Method.Get, callerName, lineNumber, filePath);
            if (apiResponse.IsSuccess)
            {
                try
                {
                    var accessKey = Newtonsoft.Json.JsonConvert.DeserializeObject<BlackedList?>(apiResponse.Response);
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Success", accessKey), callerName, lineNumber, filePath);
                    return Tuple.Create<BlackedList?, BaseErrorData?>(accessKey, null);
                }
                catch (Exception ex)
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error: " + apiResponse.Response, ex, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return Tuple.Create<BlackedList?, BaseErrorData?>(null, null);
                }
            }
            else
            {
                if (apiResponse.ApiStatusCode == 401)
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error", "Un Auth", ActionType: EmSystemActionType.WARNING), callerName, lineNumber, filePath);
                    Auth.Login();
                    return GetByCode(code, timeOut, callerName, lineNumber, filePath);
                }
                else
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error Code", apiResponse.ApiStatusCode, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    var errorData = Newtonsoft.Json.JsonConvert.DeserializeObject<BaseErrorData?>(apiResponse.Response);
                    if (errorData != null)
                    {
                        errorData.Route = GetInitRoute(EmApiObjectType.ACCESS_KEY);
                    }
                    return Tuple.Create<BlackedList?, BaseErrorData?>(null, errorData);
                }
            }
        }

    }
}
