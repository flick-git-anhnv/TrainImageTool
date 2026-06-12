using iParkingv8.Object.Objects.Invoices;
using IParkingv8.API.Interfaces;
using IParkingv8.API.Objects;
using Kztek.Object;
using Kztek.Tool;
using RestSharp;
using System.Runtime.CompilerServices;
using static IParkingv8.API.Objects.Filter;

namespace IParkingv8.API.Implementation.v8
{
    public class InvoiceService8(IAuth auth) : IInvoiceService
    {
        public IAuth Auth { get; set; } = auth;

        public async Task<Tuple<InvoiceData?, string>> CreateInvoiceAsync(string exitId, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "")
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = server + "invoices";
            string baseLog = $"Create invoices for exit id {exitId}";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);
            Dictionary<string, string> headers = new()
            {
                { "Authorization","Bearer " + Auth.ApiAuthResult.AccessToken  }
            };

            var data = new
            {
                exitId = exitId,
            };

            var apiResponse = await Kztek.Api.ApiHelper.GeneralJsonAPIAsync(apiUrl, data, headers, null, timeOut, Method.Post);
            if (apiResponse.IsSuccess)
            {
                var baseResponse = NewtonSoftHelper<InvoiceData>.GetBaseResponse(apiResponse.Response);
                return Tuple.Create<InvoiceData?, string>(baseResponse, apiResponse.Response);
            }
            else
            {
                if (apiResponse.ApiStatusCode == 401)
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error", "Un Auth", ActionType: EmSystemActionType.WARNING), callerName, lineNumber, filePath);
                    await Auth.LoginAsync();
                    return await CreateInvoiceAsync(exitId, timeOut, callerName, lineNumber, filePath);
                }
                else
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error Code", apiResponse.ApiStatusCode, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return Tuple.Create<InvoiceData?, string>(null, apiResponse.Response);
                }
            }
        }
        public async Task<BaseReport<InvoiceData>?> GetInvoicesAsync(string keyword, DateTime startTime, DateTime endTime, string user, int status, bool isPaging = true, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", int pageIndex = 0, int pageSize = 20)
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = server + "invoices/search";
            string baseLog = $"Get invoices";
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
            ];

            if (!string.IsNullOrEmpty(user))
            {
                filterModels.Add(new FilterModel("createdBy", EmQueryType.TEXT, user, EmOperation._contains));
            }
            if (status > 0)
            {
                filterModels.Add(new FilterModel("status", EmQueryType.TEXT, status.ToString(), EmOperation._eq));
            }
            var filter1 = Filter.CreateFilterItem(filterModels, EmMainOperation.and);
            var filter2 = Filter.CreateFilterItem(
                        [
                            new FilterModel("lookUpCode", "TEXT", keyword, "contains"),
                            new FilterModel("exit.plateNumber", "TEXT", keyword, "contains"),
                        ], EmMainOperation.or);
            List<Dictionary<string, List<FilterModel>>> filterItems = new List<Dictionary<string, List<FilterModel>>>();
            filterItems.Add(filter1);
            if (!string.IsNullOrEmpty(keyword))
            {
                filterItems.Add(filter2);
            }
            var filter = Filter.CreateFilter(filterItems, true,
                                            pageIndex: pageIndex,
                                            pageSize: pageSize);
            var apiResponse = await Kztek.Api.ApiHelper.GeneralJsonAPIAsync(apiUrl, filter, headers, null, timeOut, Method.Post, callerName, lineNumber, filePath);
            if (apiResponse.IsSuccess)
            {
                var baseResponse = NewtonSoftHelper<BaseReport<InvoiceData>>.GetBaseResponse(apiResponse.Response);
                SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Success"), callerName, lineNumber, filePath);
                return baseResponse;
            }
            else
            {
                if (apiResponse.ApiStatusCode == 401)
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error", "Un Auth", ActionType: EmSystemActionType.WARNING), callerName, lineNumber, filePath);
                    await Auth.LoginAsync();
                    return await GetInvoicesAsync(keyword, startTime, endTime, user, status, isPaging, timeOut, callerName, lineNumber, filePath, pageIndex, pageSize);
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
