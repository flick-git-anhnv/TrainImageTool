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
    public class ReportEntry(IAuth auth) : IReportEntry
    {
        public IAuth Auth { get; set; } = auth;
        public async Task<BaseReport<EntryData>?> GetEntryDataAsync(string keyword, DateTime startTime, DateTime endTime, string collectionId,
                                                         string vehicleType, string laneId, string user, string customerCollectionId, bool isPaging,
                                                         int pageIndex = 0, int pageSize = PAGE_SIZE, string eventId = "",
                                                         int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true)
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{SearchObjectDataRoute(EmApiObjectType.ENTRIES)}";
            string baseLog = "Get Entry Report By Condition";
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
                new FilterModel("exited", "BOOLEAN", "false",  "eq"),
            ];
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
            if (!string.IsNullOrEmpty(vehicleType))
            {
                filterModels.Add(new FilterModel("accessKey.collection.vehicleType", EmQueryType.TEXT, vehicleType.ToString(), EmOperation._eq));
            }
            if (!string.IsNullOrEmpty(customerCollectionId))
            {
                filterModels.Add(new FilterModel("customer.collectionId", EmQueryType.GUID, customerCollectionId, EmOperation._in));
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
                    var report = Newtonsoft.Json.JsonConvert.DeserializeObject<BaseReport<EntryData>?>(apiResponse.Response);
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
                    return await GetEntryDataAsync(keyword, startTime, endTime, collectionId,
                                                   vehicleType, laneId, user, customerCollectionId, isPaging,
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
        public async Task<BaseReport<EntryData>?> GetEntryDataByPlateAsync(string plateNumber, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true)
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{SearchObjectDataRoute(EmApiObjectType.ENTRIES)}";
            string baseLog = $"Get Entry Report By Plate {plateNumber}";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);
            Dictionary<string, string> headers = new()
            {
                { "Authorization","Bearer " + Auth.ApiAuthResult.AccessToken  }
            };

            DateTime minTime = new(2000, DateTime.Now.Month, DateTime.Now.Day, 0, 0, 0);
            DateTime endTime = new(DateTime.Now.Year, DateTime.Now.Month, DateTime.Now.Day, 23, 59, 59);

            string startTimeStr = minTime.ToUniversalTime().ToString("yyyy-MM-dd HH:mm:ss");
            string endTimeStr = endTime.ToUniversalTime().ToString("yyyy-MM-dd HH:mm:ss");
            string timeCondition = $"[{startTimeStr},{endTimeStr}]";
            List<FilterModel> filterModels =
            [
                new ("createdUtc", "DATETIME", timeCondition, "between"),
                new ("plateNumber", "TEXT", plateNumber, "contains"),
                new ("exited", "BOOLEAN", "false",  "eq"),
            ];
            var filter1 = CreateFilterItem(filterModels, EmMainOperation.and);
            var filter = CreateFilter([filter1], false, pageIndex: 0, pageSize: 100);
            var apiResponse = await ApiHelper.GeneralJsonAPIAsync(apiUrl, filter, headers, null, timeOut, Method.Post, callerName, lineNumber, filePath);
            if (apiResponse.IsSuccess)
            {
                try
                {
                    var report = Newtonsoft.Json.JsonConvert.DeserializeObject<BaseReport<EntryData>?>(apiResponse.Response);
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
                    return await GetEntryDataByPlateAsync(plateNumber, timeOut, callerName, lineNumber, filePath);
                }
                else
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error Code", apiResponse.ApiStatusCode, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return null;
                }
            }
        }

        public async Task<EntryData?> GetEntryByAccessKeyIdAsync(string accessId, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true)
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{GetInitRoute(EmApiObjectType.ENTRIES)}";
            string baseLog = $"Get Entry By AccessKeyId {accessId}";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);
            Dictionary<string, string> headers = new()
            {
                { "Authorization","Bearer " + Auth.ApiAuthResult.AccessToken  }
            };
            var parameters = new Dictionary<string, string>
            {
                { "accessKeyId", accessId },
                { "presignedUrl", "true" }
            };
            var apiResponse = await ApiHelper.GeneralJsonAPIAsync(apiUrl, null, headers, parameters, timeOut, Method.Get, callerName, lineNumber, filePath);
            if (apiResponse.IsSuccess)
            {
                try
                {
                    var report = Newtonsoft.Json.JsonConvert.DeserializeObject<EntryData?>(apiResponse.Response);
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
                    return await GetEntryByAccessKeyIdAsync(accessId, timeOut, accessId, lineNumber, filePath);
                }
                else
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error Code", apiResponse.ApiStatusCode, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return null;
                }
            }
        }

        public async Task<EntryData?> GetEntryByIdAsync(string id, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true)
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{GetInitRoute(EmApiObjectType.ENTRIES)}/{id}";
            string baseLog = $"Get Entry By Id {id}";
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
                    var report = Newtonsoft.Json.JsonConvert.DeserializeObject<EntryData?>(apiResponse.Response);
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
                    return await GetEntryByIdAsync(id, timeOut, callerName, lineNumber, filePath);
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
