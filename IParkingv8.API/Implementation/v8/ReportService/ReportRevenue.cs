using iParkingv8.Object.Objects.Events;
using iParkingv8.Object.Objects.Reports;
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
    public class ReportRevenue(IAuth auth) : IReportRevenue
    {
        public IAuth Auth { get; set; } = auth;
        public async Task<SearchRevenueReportResponse?> GetRevenueDetail(DateTime startTime, DateTime endTime, int category,
                                                                         string created_by, string collectionId, string laneId,
                                                                         int timeout = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true)
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            //string apiUrl = server + $"transactions/summarize/charge";
            string apiUrl = $"{server}statistics/revenue";
            string baseLog = "Get Revenue";
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
                new FilterModel("e.created_utc", "DATETIME", timeCondition, "between"),
                new FilterModel("e.deleted", "BOOLEAN", "false", "eq"),
            ];
            if (!string.IsNullOrEmpty(created_by))
            {
                filterModels.Add(new FilterModel("e.created_by", "TEXT", created_by, "in"));
            }
            if (!string.IsNullOrEmpty(collectionId))
            {
                filterModels.Add(new FilterModel("akc.id", "GUID", collectionId, "in"));
            }
            if (!string.IsNullOrEmpty(laneId))
            {
                filterModels.Add(new FilterModel("e.device_id", "GUID", created_by, "in"));
            }
            var filter = CreateFilterItem(filterModels, EmMainOperation.and);
            var body = new
            {
                Category = category,
                queryCriteria = new
                {
                    Filter = filter,
                }
            };
            var apiResponse = await ApiHelper.GeneralJsonAPIAsync(apiUrl, body, headers, null, timeout, Method.Post,  callerName, lineNumber, filePath);
            if (apiResponse.IsSuccess)
            {
                try
                {
                    var report = Newtonsoft.Json.JsonConvert.DeserializeObject<SearchRevenueReportResponse?>(apiResponse.Response);
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
                    return await GetRevenueDetail(startTime, endTime, category,
                                                  created_by, collectionId, laneId,
                                                  timeout, callerName, lineNumber, filePath);
                }
                else
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error Code", apiResponse.ApiStatusCode, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return null;
                }
            }
        }

        public async Task<SumarizeTraffic?> GetSumarizeTraffic(int category, DateTime startTime, DateTime endTime, int timeout = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true)
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{GetInitRoute(EmApiObjectType.TRANSACTIONS)}/summarize/traffic";
            string baseLog = "Get Sumarize Traffic";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);
            Dictionary<string, string> headers = new()
            {
                { "Authorization","Bearer " + Auth.ApiAuthResult.AccessToken  }
            };

            string startTimeStr = startTime.ToUniversalTime().ToString("yyyy-MM-dd HH:mm:ss");
            string endTimeStr = endTime.ToUniversalTime().ToString("yyyy-MM-dd HH:mm:ss");
            string timeCondition = $"[{startTimeStr},{endTimeStr}]";

            var filter = new FilterModel("e.created_utc", "DATETIME", timeCondition, "between");
            var filters = new Dictionary<string, List<FilterModel>>();
            filters.Add("and", new List<FilterModel>() { filter });
            var body = new
            {
                Category = category,
                queryCriteria = new
                {
                    filter = filters
                },
            };
            var apiResponse = await ApiHelper.GeneralJsonAPIAsync(apiUrl, body, headers, null, timeout, Method.Post,  callerName, lineNumber, filePath);
            if (apiResponse.IsSuccess)
            {
                try
                {
                    var report = Newtonsoft.Json.JsonConvert.DeserializeObject<SumarizeTraffic?>(apiResponse.Response);
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
                    return await GetSumarizeTraffic(category, startTime, endTime, timeout, callerName, lineNumber, filePath);
                }
                else
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error Code", apiResponse.ApiStatusCode, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return null;
                }
            }
        }

        public async Task<ShiftHandOverReport> GetShiftHandOverReport(List<string> collectionNames, DateTime startTime, DateTime endTime, string created_by,
                                                                      int timeout = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true)
        {
            var report = new ShiftHandOverReport();
            foreach (var item in collectionNames)
            {
                report.Report.Add(item, new ShiftHandOverDetail());
                //var entryInfo = await GetEntryDataAsync(item);
                //report.Report[item].Ton = entryInfo?.TotalCount ?? 0;
            }

            var revenue = await GetRevenueDetail(startTime, endTime, 0, created_by, "", "", timeout, callerName, lineNumber, filePath) ?? new SearchRevenueReportResponse();
            var traffic = await GetSumarizeTraffic(0, startTime, endTime, timeout, callerName, lineNumber, filePath) ?? new SumarizeTraffic();
            //Lấy số lượng xe ra + phí
            foreach (var item in revenue.Data)
            {
                if (!report.Report.ContainsKey(item.Identifier))
                {
                    report.Report.Add(item.Identifier, new ShiftHandOverDetail());
                }
                report.Report[item.Identifier].Ra += item.Count;
                report.Report[item.Identifier].Amount += item.Amount;
                report.Report[item.Identifier].Discount += item.Discount;
                report.Report[item.Identifier].RealFee += Math.Max(item.Amount - item.Discount - item.EntryAmount, 0);
            }

            //Lấy số lượng xe vào
            foreach (var item in traffic.Entry)
            {
                if (!report.Report.ContainsKey(item.Identifier))
                {
                    report.Report.Add(item.Identifier, new ShiftHandOverDetail());
                }
                report.Report[item.Identifier].Vao += item.Count;
            }

            //Lấy số lượng xe tồn

            return report;
        }

        public async Task<BaseReport<EntryData>?> GetEntryDataAsync(string collectionName, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true)
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{SearchObjectDataRoute(EmApiObjectType.ENTRIES)}";
            string baseLog = "Get Entry Report By Condition";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);
            Dictionary<string, string> headers = new()
            {
                { "Authorization","Bearer " + Auth.ApiAuthResult.AccessToken  }
            };

            List<FilterModel> filterModels =
            [
                new FilterModel("exited", "BOOLEAN", "false",  "eq"),
                new FilterModel("accesskey.collection.name", "Text", collectionName,  "eq"),
            ];
            var filter1 = CreateFilterItem(filterModels, EmMainOperation.and);
            var filter = CreateFilter([filter1], true, pageIndex: 0, pageSize: 1);
            var apiResponse = await ApiHelper.GeneralJsonAPIAsync(apiUrl, filter, headers, null, timeOut, Method.Post,  callerName, lineNumber, filePath);
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
                    return await GetEntryDataAsync(collectionName, timeOut, callerName, lineNumber, filePath);
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
