using iParkingv8.Object.Objects.Parkings;
using IParkingv8.API.Interfaces;
using IParkingv8.API.Objects;
using Kztek.Api;
using Kztek.Object;
using Kztek.Tool;
using RestSharp;
using System.ComponentModel.DataAnnotations;
using System.Runtime.CompilerServices;
using static IParkingv8.API.Implementation.v8.ApiUrlManagement;
using static IParkingv8.API.Objects.Filter;

namespace IParkingv8.API.Implementation.v8.DataService
{
    public class SystemConfigAPI(IAuth auth) : ISystemConfig
    {
        public IAuth Auth { get; set; } = auth;

        public async Task<BaseReport<SystemConfig>?> GetSystemConfigAsync(int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", int pageIndex = 0, int pageSize = 50)
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{SearchObjectDataRoute(EmApiObjectType.Configs)}";

            string baseLog = $"Get configs";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);

            Dictionary<string, string> headers = new()
            {
                { "Authorization","Bearer " + Auth.ApiAuthResult.AccessToken  }
            };

            string filter = CreateFilter(
            new List<FilterModel>()
            , false, pageIndex: pageIndex, pageSize: pageSize);
            var apiResponse = ApiHelper.GeneralJsonAPI(apiUrl, new { paging = false }, headers, null, timeOut, Method.Post,  callerName, lineNumber, filePath);
            if (apiResponse.IsSuccess)
            {
                var baseResponse = NewtonSoftHelper<BaseReport<SystemConfig>>.GetBaseResponse(apiResponse.Response);
                SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Success"), callerName, lineNumber, filePath);
                return baseResponse;
            }
            else
            {
                if (apiResponse.ApiStatusCode == 401)
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error", "Un Auth", ActionType: EmSystemActionType.WARNING), callerName, lineNumber, filePath);
                    Auth.Login();
                    return await GetSystemConfigAsync(timeOut, callerName, lineNumber, filePath, pageIndex, pageSize);
                }
                else
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error Code", apiResponse.ApiStatusCode, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return null;
                }
            }
        }

        public class ServerHealth
        {
            [Display(Name = "Giờ Vào", Order = 2)]
            [DisplayFormat(DataFormatString = "{HH:mm:ss}", ApplyFormatInEditMode = true)]
            public DateTime Now
            {
                get
                {
                    try
                    {
                        if (utcNow.Contains('T'))
                        {
                            return DateTime.ParseExact(utcNow[.."yyyy-MM-ddTHH:mm:ss".Length], "yyyy-MM-ddTHH:mm:ss", null).AddHours(7);
                        }
                        else
                        {
                            return DateTime.Parse(utcNow).AddHours(7);
                        }
                    }
                    catch
                    {
                        return DateTime.Now;
                    }
                }
            }

            public string utcNow { get; set; }
        }
        public async Task<DateTime?> GetServerTime(int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", int pageIndex = 0, int pageSize = 50)
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}health";

            //string baseLog = $"Get configs";
            //SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);

            Dictionary<string, string> headers = new()
            {
                { "Authorization","Bearer " + Auth.ApiAuthResult.AccessToken  }
            };

            var apiResponse = ApiHelper.GeneralJsonAPI(apiUrl, null, headers, null, timeOut, Method.Get,  callerName, lineNumber, filePath);
            if (apiResponse.IsSuccess)
            {
                var baseResponse = NewtonSoftHelper<ServerHealth>.GetBaseResponse(apiResponse.Response);
                //SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Success"), callerName, lineNumber, filePath);
                return baseResponse?.Now ?? null;
            }
            else
            {
                if (apiResponse.ApiStatusCode == 401)
                {
                    //SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error", "Un Auth", ActionType: EmSystemActionType.WARNING), callerName, lineNumber, filePath);
                    Auth.Login();
                    return await GetServerTime(timeOut, callerName, lineNumber, filePath, pageIndex, pageSize);
                }
                else
                {
                    //SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error Code", apiResponse.ApiStatusCode, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return null;
                }
            }
        }
    }
}
