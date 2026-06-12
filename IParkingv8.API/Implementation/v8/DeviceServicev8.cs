using iParkingv8.Object.Objects.Devices;
using IParkingv8.API.Interfaces;
using Kztek.Api;
using Kztek.Object;
using Kztek.Tool;
using System.Runtime.CompilerServices;

namespace IParkingv8.API.Implementation.v8
{
    public class DeviceServicev8(IAuth auth) : IDeviceService
    {
        #region Properties
        public IAuth Auth { get; set; } = auth;

        #endregion

        #region Constructor
        #endregion

        #region Public Function
        public async Task<DeviceResponse?> GetDeviceDataAsync(int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "")
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = server + ApiUrlManagement.SearchObjectDataRoute(ApiUrlManagement.EmApiObjectType.DEVICES);

            string baseLog = "Get Device Config";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);

            var body = new
            {
                paging = false,
            };
            Dictionary<string, string> headers = new()
            {
                { "Authorization","Bearer " + Auth.ApiAuthResult.AccessToken  }
            };
            var apiResponse = await ApiHelper.GeneralJsonAPIAsync(apiUrl, body, headers, null, timeOut, RestSharp.Method.Post,  callerName, lineNumber, filePath);
            if (apiResponse.IsSuccess)
            {
                try
                {
                    var response = Newtonsoft.Json.JsonConvert.DeserializeObject<DeviceResponse>(apiResponse.Response);
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Success"), callerName, lineNumber, filePath);
                    return response;
                }
                catch (Exception ex)
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error: " + apiResponse.Response, ex, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return null;
                }
            }
            else
            {
                if (apiResponse.ApiStatusCode == 401)
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error", "Un Auth", ActionType: EmSystemActionType.WARNING), callerName, lineNumber, filePath);
                    await Auth.LoginAsync();
                    return await GetDeviceDataAsync(timeOut, callerName, lineNumber, filePath);
                }
                else
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error Code", apiResponse.ApiStatusCode, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return null;
                }
            }
        }
        #endregion
    }
}
