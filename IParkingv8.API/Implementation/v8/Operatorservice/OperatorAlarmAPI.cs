using iParkingv8.Object.Enums.Bases;
using iParkingv8.Object.Objects.Events;
using IParkingv8.API.Interfaces;
using Kztek.Api;
using Kztek.Object;
using Kztek.Tool;
using RestSharp;
using System.Runtime.CompilerServices;
using static IParkingv8.API.Implementation.v8.ApiUrlManagement;

namespace IParkingv8.API.Implementation.v8.Operatorservice
{
    public class OperatorAlarmAPI(IAuth auth) : IOperatorAlarm
    {
        public IAuth Auth { get; set; } = auth;

        #region Alarm
        public async Task<AbnormalEvent?> CreateAsync(string laneId, string plate, EmAlarmCode abnormalCode, string description, string accessKeyId, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true)
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{GetInitRoute(EmApiObjectType.ALARMS)}";
            string baseLog = $"Create Alarms {laneId} - {abnormalCode} - {description} - {plate}";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);
            Dictionary<string, string> headers = new()
            {
                { "Authorization","Bearer " + Auth.ApiAuthResult.AccessToken  }
            };
            var body = new
            {
                deviceId = laneId,
                plateNumber = plate,
                code = abnormalCode.ToString(),
                note = description,
                accessKeyId
            };
#if DEBUG
            string a = Newtonsoft.Json.JsonConvert.SerializeObject(body);
#endif
            var apiResponse = await ApiHelper.GeneralJsonAPIAsync(apiUrl, body, headers, null, timeOut, Method.Post,  callerName, lineNumber, filePath);
            if (apiResponse.IsSuccess)
            {
                try
                {
                    var alarm = Newtonsoft.Json.JsonConvert.DeserializeObject<AbnormalEvent?>(apiResponse.Response);
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Success"), callerName, lineNumber, filePath);
                    return alarm;
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
                    return await CreateAsync(laneId, plate, abnormalCode, description, accessKeyId, timeOut, callerName, lineNumber, filePath);
                }
                else
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error Code", apiResponse.ApiStatusCode, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return null;
                }
            }
        }
        public async Task<bool> SaveImageAsync(List<byte> imageData, string alarmId, EmImageType imageType, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true)
        {
            while (true)
            {
                string baseLog = $"Save Alarm Image {alarmId} - {imageType}";
                SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);
                if (imageData is null)
                {
                    return false;
                }
                if (imageData.Count == 0)
                {
                    return false;
                }
                var server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();

                var options = new RestClientOptions(server);
                var client = new RestClient(options);
                var request = new RestRequest($"/alarms/{alarmId}/upload/image", Method.Put);
                request.AddHeader("Authorization", "Bearer " + Auth.ApiAuthResult.AccessToken);
                request.AlwaysMultipartFormData = true;
                request.AddParameter("type", imageType.ToString());
                request.AddFile($"file", [.. imageData], "x.jpg");
                RestResponse response = await client.ExecuteAsync(request);
                if (response.IsSuccessful)
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Success"), callerName, lineNumber, filePath);
                    return true;
                }
                else
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error Code", response.StatusCode, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    await Task.Delay(TimeSpan.FromSeconds(1));
                }
            }
        }
        #endregion
    }
}
