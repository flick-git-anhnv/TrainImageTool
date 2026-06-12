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
    public class ReportExit(IAuth auth) : IReportExit
    {
        public IAuth Auth { get; set; } = auth;
        public async Task<BaseReport<ExitData>?> GetExitDataAsync(string keyword, DateTime startTime, DateTime endTime, string collectionId,
                                                     string vehicleType, string laneId, string user, bool isPaging,
                                                     int pageIndex = 0, int pageSize = PAGE_SIZE, string eventId = "",
                                                     int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true)
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{SearchObjectDataRoute(EmApiObjectType.EXITS)}";
            string baseLog = "Get Exit Report By Condition";
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
            if (!string.IsNullOrEmpty(eventId))
            {
                filterModels.Add(new FilterModel("id", EmQueryType.GUID, eventId, EmOperation._in));
            }
            if (!string.IsNullOrEmpty(collectionId))
            {
                filterModels.Add(new FilterModel("accessKey.collectionId", EmQueryType.GUID, collectionId, EmOperation._in));
            }
            if (!string.IsNullOrEmpty(vehicleType))
            {
                filterModels.Add(new FilterModel("accessKey.collection.vehicleType", EmQueryType.TEXT, vehicleType.ToString(), EmOperation._eq));
            }
            var filter1 = CreateFilterItem(filterModels, EmMainOperation.and);

            var filterKeyword = CreateFilterItem(
            [
                new FilterModel("plateNumber", "TEXT", keyword, "contains"),
                new FilterModel("accessKey.code", "TEXT", keyword, "contains"),
                new FilterModel("accessKey.name", "TEXT", keyword, "contains"),
                new FilterModel("note", "TEXT", keyword, "contains"),
            ], EmMainOperation.or);

            List<Dictionary<string, List<FilterModel>>> filterItems = [filter1, filterKeyword];
            if (!string.IsNullOrEmpty(laneId))
            {
                var filterLane = CreateFilterItem(
                [
                    new FilterModel("entry.device.id", EmQueryType.GUID, laneId, EmOperation._eq),
                    new FilterModel("device.id", EmQueryType.GUID, laneId, EmOperation._eq)
                ], EmMainOperation.or);
                filterItems.Add(filterLane);
            }

            var filter = CreateFilter(filterItems, isPaging, pageIndex: pageIndex, pageSize: pageSize);
            var apiResponse = await ApiHelper.GeneralJsonAPIAsync(apiUrl, filter, headers, null, timeOut, Method.Post, callerName, lineNumber, filePath);
            if (apiResponse.IsSuccess)
            {
                try
                {
                    var report = Newtonsoft.Json.JsonConvert.DeserializeObject<BaseReport<ExitData>?>(apiResponse.Response);
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
                    return await GetExitDataAsync(keyword, startTime, endTime, collectionId,
                                              vehicleType, laneId, user, isPaging,
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
        public async Task<ExitData?> GetExitByAccessKeyIdAsync(string accessId, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true)
        {
            await Task.Delay(1);
            return new ExitData();
        }
        public async Task<ExitData?> GetExitByIdAsync(string id, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true)
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{GetInitRoute(EmApiObjectType.EXITS)}/{id}";
            string baseLog = $"Get Entry Report By Id {id}";
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
                    var report = Newtonsoft.Json.JsonConvert.DeserializeObject<ExitData?>(apiResponse.Response);
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
                    return await GetExitByIdAsync(id, timeOut, callerName, lineNumber, filePath);
                }
                else
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error Code", apiResponse.ApiStatusCode, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return null;
                }
            }
        }
        public async Task<BaseReport<ExitData>?> GetEventInAndOuts(DateTime startTime, DateTime endTime,
                                                                      bool isPaging, int pageIndex = 1, int pageSize = PAGE_SIZE,
                                                                      int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true)
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{SearchObjectDataRoute(EmApiObjectType.EXITS)}";
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
            ];
            var filter1 = CreateFilterItem(filterModels, EmMainOperation.and);

            var filterKeyword = CreateFilterItem(
            [
                new FilterModel("plateNumber", "TEXT", "", "contains"),
                new FilterModel("accessKey.code", "TEXT","" , "contains"),
                new FilterModel("accessKey.name", "TEXT", "", "contains"),
                new FilterModel("note", "TEXT", "", "contains"),
            ], EmMainOperation.or);

            List<Dictionary<string, List<FilterModel>>> filterItems = [filter1, filterKeyword];

            var filter = CreateFilter(filterItems, isPaging,
                                            pageIndex: pageIndex,
                                            pageSize: pageSize);

            var apiResponse = await ApiHelper.GeneralJsonAPIAsync(apiUrl, filter, headers, null, timeOut, Method.Post, callerName, lineNumber, filePath);
            if (apiResponse.IsSuccess)
            {
                var baseResponse = NewtonSoftHelper<BaseReport<ExitData>>.GetBaseResponse(apiResponse.Response);
                return baseResponse;
            }
            else
            {
                if (apiResponse.ApiStatusCode == 401)
                {
                    await Auth.LoginAsync();
                    return await GetEventInAndOuts(startTime, endTime, isPaging, pageIndex, pageSize, timeOut, callerName, lineNumber, filePath);
                }
                else
                {
                    return null;
                }
            }
        }
    }
}
