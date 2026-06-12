using iParkingv8.Object.Objects.Events;
using IParkingv8.API.Interfaces;
using IParkingv8.API.Objects;
using Kztek.Api;
using Kztek.Object;
using Kztek.Tool;
using RestSharp;
using System.Runtime.CompilerServices;
using static IParkingv8.API.Implementation.v8.ApiUrlManagement;
using static IParkingv8.API.Objects.Filter;

namespace IParkingv8.API.Implementation.v8.ReportService
{
    public class ReportAlarm(IAuth auth) : IReportAlarm
    {
        public IAuth Auth { get; set; } = auth;
        public async Task<BaseReport<AbnormalEvent>?> GetDataAsync(string keyword, DateTime startTime, DateTime endTime, string collectionId,
                                                         string laneId, string user, string customerCollectionId, bool isPaging, int alarmCode = -1,
                                                         int pageIndex = 0, int pageSize = PAGE_SIZE, string eventId = "",
                                                         int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true)
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{SearchObjectDataRoute(EmApiObjectType.ALARMS)}";
            string baseLog = "Get Alarm Report By Condition";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);
            Dictionary<string, string> headers = new()
            {
                { "Authorization","Bearer " + Auth.ApiAuthResult.AccessToken  }
            };

            string startTimeStr = startTime.ToUniversalTime().ToString("yyyy-MM-dd HH:mm:ss");
            string endTimeStr = endTime.ToUniversalTime().ToString("yyyy-MM-dd HH:mm:ss");
            string timeCondition = $"[{startTimeStr},{endTimeStr}]";
            List<FilterModel> filterModels =
            [
                new FilterModel("createdUtc", "DATETIME", timeCondition, "between"),
                new FilterModel("createdBy", EmQueryType.TEXT, user,  EmOperation._contains),
            ];
            if (alarmCode >= 0)
            {
                filterModels.Add(new FilterModel("code", EmQueryType.TEXT, alarmCode.ToString(), EmOperation._in));
            }
            if (!string.IsNullOrEmpty(eventId))
            {
                filterModels.Add(new FilterModel("id", EmQueryType.GUID, eventId, EmOperation._in));
            }
            if (!string.IsNullOrEmpty(laneId))
            {
                filterModels.Add(new FilterModel("device.id", EmQueryType.GUID, laneId, EmOperation._in));
            }
            if (!string.IsNullOrEmpty(collectionId))
            {
                filterModels.Add(new FilterModel("accessKey.collectionId", EmQueryType.GUID, collectionId, EmOperation._in));
            }
            if (!string.IsNullOrEmpty(customerCollectionId))
            {
                filterModels.Add(new FilterModel("accessKey.customer.collectionId", EmQueryType.GUID, customerCollectionId, EmOperation._in));
            }
            var filter1 = CreateFilterItem(filterModels, EmMainOperation.and);
            var filter2 = CreateFilterItem(
                        [
                            new FilterModel("plateNumber", "TEXT", keyword, "contains"),
                            new FilterModel("accessKey.code", "TEXT", keyword, "contains"),
                            new FilterModel("accessKey.name", "TEXT", keyword, "contains"),
                            new FilterModel("device.name", "TEXT", keyword, "contains"),
                            new FilterModel("note", "TEXT", keyword, "contains"),
                        ], EmMainOperation.or);
            var filter = CreateFilter([filter1, filter2], isPaging,
                                            pageIndex: pageIndex,
                                            pageSize: pageSize);
            var apiResponse = await ApiHelper.GeneralJsonAPIAsync(apiUrl, filter, headers, null, timeOut, Method.Post, callerName, lineNumber, filePath);
            if (apiResponse.IsSuccess)
            {
                try
                {
                    var report = Newtonsoft.Json.JsonConvert.DeserializeObject<BaseReport<AbnormalEvent>?>(apiResponse.Response);
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Success"), callerName, lineNumber, filePath);
                    return report;
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
                    return await GetDataAsync(keyword, startTime, endTime, collectionId,
                                                    laneId, user, customerCollectionId, isPaging, alarmCode,
                                                   pageIndex, pageSize, eventId,
                                                   timeOut, callerName, lineNumber, filePath);
                }
                else
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error Code", apiResponse.ApiStatusCode, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return null;
                }
            }
        }
        public async Task<AbnormalEvent?> GetByIdAsync(string id, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true)
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{GetInitRoute(EmApiObjectType.ALARMS)}/{id}";
            string baseLog = $"Get Alarm By Id {id}";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);
            Dictionary<string, string> headers = new()
            {
                { "Authorization","Bearer " + Auth.ApiAuthResult.AccessToken  }
            };
            Dictionary<string, string> parameters = new()
            {
                { "presignedUrl", "true" }
            };

            var apiResponse = await ApiHelper.GeneralJsonAPIAsync(apiUrl, null, headers, parameters, timeOut, Method.Get, callerName, lineNumber, filePath);
            if (apiResponse.IsSuccess)
            {
                try
                {
                    var report = Newtonsoft.Json.JsonConvert.DeserializeObject<AbnormalEvent?>(apiResponse.Response);
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Success"), callerName, lineNumber, filePath);
                    return report;
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
                    return await GetByIdAsync(id, timeOut, callerName, lineNumber, filePath);
                }
                else
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error Code", apiResponse.ApiStatusCode, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return null;
                }
            }
        }

    }
}
