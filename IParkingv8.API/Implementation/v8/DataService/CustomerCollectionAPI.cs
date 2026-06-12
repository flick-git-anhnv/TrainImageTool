using iParkingv8.Object.Objects.Parkings;
using IParkingv8.API.Interfaces;
using IParkingv8.API.Objects;
using Kztek.Api;
using Kztek.Object;
using Kztek.Tool;
using RestSharp;
using System.Runtime.CompilerServices;
using static IParkingv8.API.Implementation.v8.ApiUrlManagement;

namespace IParkingv8.API.Implementation.v8.DataService
{
    public class CustomerCollectionAPI(IAuth auth) : ICustomerCollection
    {
        public IAuth Auth { get; set; } = auth;
        public async Task<Tuple<List<CustomerGroup>?, string>> GetAllAsync(int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0,
                                                                         [CallerFilePath] string filePath = "", bool isSaveLog = true)
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{SearchObjectDataRoute(EmApiObjectType.CUSOMER_COLLECTIONS)}";

            string baseLog = $"Get CustomerCollections";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);

            Dictionary<string, string> headers = new()
            {
                { "Authorization","Bearer " + Auth.ApiAuthResult.AccessToken  }
            };
            var filterItem = Filter.CreateFilterItem(
            [
                new FilterModel()
                {
                    QueryType = "BOOLEAN",
                    Operation = "eq",
                    QueryKey = "cc.deleted",
                    QueryValue = "false"
                }
            ]);
            var filter = new
            {
                paging = false,
                filter = filterItem,
                pageIndex = 1,
                pageSize = 1,
            };
            var apiResponse = await ApiHelper.GeneralJsonAPIAsync(apiUrl, filter, headers, null, timeOut, Method.Post, callerName, lineNumber, filePath);
            if (apiResponse.IsSuccess)
            {
                try
                {
                    var kzBaseResponse = Newtonsoft.Json.JsonConvert.DeserializeObject<BaseResponse<List<CustomerGroup>>>(apiResponse.Response);
                    if (kzBaseResponse == null)
                    {
                        return Tuple.Create<List<CustomerGroup>?, string>(null, apiResponse.Response);
                    }
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Success"), callerName, lineNumber, filePath);
                    return Tuple.Create(kzBaseResponse.Data, kzBaseResponse.DetailCode);
                }
                catch (Exception ex)
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error: " + apiResponse.Response, ex, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return Tuple.Create<List<CustomerGroup>?, string>(null, apiResponse.Response);
                }
            }
            else
            {
                if (apiResponse.ApiStatusCode == 401)
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error", "Un Auth", ActionType: EmSystemActionType.WARNING), callerName, lineNumber, filePath);
                    await Auth.LoginAsync();
                    return await GetAllAsync(timeOut, callerName, lineNumber, filePath);
                }
                else
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error Code", apiResponse.ApiStatusCode, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return Tuple.Create<List<CustomerGroup>?, string>(null, apiResponse.Response);
                }
            }
        }
        public Tuple<List<CustomerGroup>?, string> GetAll(int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0,
                                                                         [CallerFilePath] string filePath = "", bool isSaveLog = true)
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{SearchObjectDataRoute(EmApiObjectType.CUSOMER_COLLECTIONS)}";

            string baseLog = $"Get CustomerCollections";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);

            Dictionary<string, string> headers = new()
            {
                { "Authorization","Bearer " + Auth.ApiAuthResult.AccessToken  }
            };
            var filterItem = Filter.CreateFilterItem(
            [
                new FilterModel()
                {
                    QueryType = "BOOLEAN",
                    Operation = "eq",
                    QueryKey = "cc.deleted",
                    QueryValue = "false"
                }
            ]);
            var filter = new
            {
                paging = false,
                filter = filterItem,
            };
            var body = new
            {
                queryCriteria = filter,
            };
            var apiResponse = ApiHelper.GeneralJsonAPI(apiUrl, body, headers, null, timeOut, Method.Post, callerName, lineNumber, filePath);
            if (apiResponse.IsSuccess)
            {
                try
                {
                    var kzBaseResponse = Newtonsoft.Json.JsonConvert.DeserializeObject<BaseResponse<List<CustomerGroup>>>(apiResponse.Response);
                    if (kzBaseResponse == null)
                    {
                        return Tuple.Create<List<CustomerGroup>?, string>(null, apiResponse.Response);
                    }
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Success"), callerName, lineNumber, filePath);
                    return Tuple.Create(kzBaseResponse.Data, kzBaseResponse.DetailCode);
                }
                catch (Exception ex)
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error: " + apiResponse.Response, ex, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return Tuple.Create<List<CustomerGroup>?, string>(null, apiResponse.Response);
                }
            }
            else
            {
                if (apiResponse.ApiStatusCode == 401)
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error", "Un Auth", ActionType: EmSystemActionType.WARNING), callerName, lineNumber, filePath);
                    Auth.Login();
                    return GetAll(timeOut, callerName, lineNumber, filePath);
                }
                else
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error Code", apiResponse.ApiStatusCode, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return Tuple.Create<List<CustomerGroup>?, string>(null, apiResponse.Response);
                }
            }
        }
    }
}
