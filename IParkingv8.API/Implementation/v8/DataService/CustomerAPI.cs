using iParkingv8.Object.Objects.Parkings;
using IParkingv8.API.Interfaces;
using IParkingv8.API.Objects;
using Kztek.Api;
using Kztek.Object;
using Kztek.Tool;
using RestSharp;
using System.Runtime.CompilerServices;
using static IParkingv8.API.Implementation.v8.ApiUrlManagement;
using static IParkingv8.API.Objects.Filter;

namespace IParkingv8.API.Implementation.v8.DataService
{
    public class CustomerAPI(IAuth auth) : ICustomer
    {
        public IAuth Auth { get; set; } = auth;
        public async Task<BaseReport<CustomerDto>?> GetByConditionAsync(string keyword, string customerGroupId, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0,
                                                                 [CallerFilePath] string filePath = "", int pageIndex = 0, int pageSize = Filter.PAGE_SIZE)
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{SearchObjectDataRoute(EmApiObjectType.CUSTOMERS)}";

            string baseLog = $"Get Customers";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);

            Dictionary<string, string> headers = new()
            {
                { "Authorization","Bearer " + Auth.ApiAuthResult.AccessToken  }
            };
            List<Dictionary<string, List<FilterModel>>> filters = [];

            //Lọc theo keyword
            Dictionary<string, List<FilterModel>> filters1 = [];
            List<FilterModel> filterModels = [
                 new FilterModel(EmPageSearchKey.code, EmQueryType.TEXT, keyword, EmOperation._contains),
                 new FilterModel(EmPageSearchKey.name, EmQueryType.TEXT, keyword, EmOperation._contains),
            ];
            filters1.Add("or", filterModels);
            filters.Add(filters1);

            //Lọc theo nhóm khách hàng
            if (!string.IsNullOrEmpty(customerGroupId))
            {
                List<FilterModel> filterModels2 = [
                                    new FilterModel("collectionId", EmQueryType.GUID, customerGroupId, EmOperation._in)
                                                  ];
                Dictionary<string, List<FilterModel>> filters2 = [];
                filters2.Add("and", filterModels2);
                filters.Add(filters2);
            }
            string filter = CreateFilter(
            filters
            , true, pageIndex: pageIndex, pageSize: pageSize);
            var apiResponse = await ApiHelper.GeneralJsonAPIAsync(apiUrl, filter, headers, null, timeOut, Method.Post, callerName, lineNumber, filePath);
            if (apiResponse.IsSuccess)
            {
                var baseResponse = NewtonSoftHelper<BaseReport<CustomerDto>>.GetBaseResponse(apiResponse.Response);
                SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Success"), callerName, lineNumber, filePath);
                return baseResponse;
            }
            else
            {
                if (apiResponse.ApiStatusCode == 401)
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error", "Un Auth", ActionType: EmSystemActionType.WARNING), callerName, lineNumber, filePath);
                    await Auth.LoginAsync();
                    return await GetByConditionAsync(keyword, customerGroupId, timeOut, callerName, lineNumber, filePath, pageIndex, pageSize);
                }
                else
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error Code", apiResponse.ApiStatusCode, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return null;
                }
            }
        }
        public async Task<Tuple<CustomerDto?, string>> GetByIdAsync(string id, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0,
                                                                            [CallerFilePath] string filePath = "")
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{GetInitRoute(EmApiObjectType.CUSTOMERS)}/{id}";

            string baseLog = $"Get Customers By Id {id}";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);

            Dictionary<string, string> headers = new()
            {
                { "Authorization","Bearer " + Auth.ApiAuthResult.AccessToken  }
            };
            var apiResponse = await ApiHelper.GeneralJsonAPIAsync(apiUrl, null, headers, null, timeOut, Method.Get, callerName, lineNumber, filePath);
            if (apiResponse.IsSuccess)
            {
                try
                {
                    var accessKey = Newtonsoft.Json.JsonConvert.DeserializeObject<CustomerDto>(apiResponse.Response);
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Success"), callerName, lineNumber, filePath);
                    return Tuple.Create(accessKey, "");
                }
                catch (Exception ex)
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error: " + apiResponse.Response, ex, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return Tuple.Create<CustomerDto?, string>(null, ex.Message);
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
                    return Tuple.Create<CustomerDto?, string>(null, apiResponse.Response);
                }
            }
        }

        public BaseReport<CustomerDto>? GetByCondition(string keyword, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0,
                                                                 [CallerFilePath] string filePath = "", int pageIndex = 0, int pageSize = Filter.PAGE_SIZE)
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{SearchObjectDataRoute(EmApiObjectType.CUSTOMERS)}";

            string baseLog = $"Get Customers";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);

            Dictionary<string, string> headers = new()
            {
                { "Authorization","Bearer " + Auth.ApiAuthResult.AccessToken  }
            };

            string filter = CreateFilter(
            [
                 new FilterModel(EmPageSearchKey.code, EmQueryType.TEXT, keyword, EmOperation._contains),
                 new FilterModel(EmPageSearchKey.name, EmQueryType.TEXT, keyword, EmOperation._contains),
            ]
            , true, pageIndex: pageIndex, pageSize: pageSize);
            var apiResponse = ApiHelper.GeneralJsonAPI(apiUrl, filter, headers, null, timeOut, Method.Post, callerName, lineNumber, filePath);
            if (apiResponse.IsSuccess)
            {
                var baseResponse = NewtonSoftHelper<BaseReport<CustomerDto>>.GetBaseResponse(apiResponse.Response);
                SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Success"), callerName, lineNumber, filePath);
                return baseResponse;
            }
            else
            {
                if (apiResponse.ApiStatusCode == 401)
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error", "Un Auth", ActionType: EmSystemActionType.WARNING), callerName, lineNumber, filePath);
                    Auth.Login();
                    return GetByCondition(keyword, timeOut, callerName, lineNumber, filePath, pageIndex, pageSize);
                }
                else
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error Code", apiResponse.ApiStatusCode, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return null;
                }
            }
        }
        public Tuple<CustomerDto?, string> GetById(string id, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0,
                                                                            [CallerFilePath] string filePath = "")
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{GetInitRoute(EmApiObjectType.CUSTOMERS)}/{id}";

            string baseLog = $"Get Customers By Id {id}";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);

            Dictionary<string, string> headers = new()
            {
                { "Authorization","Bearer " + Auth.ApiAuthResult.AccessToken  }
            };
            var apiResponse = ApiHelper.GeneralJsonAPI(apiUrl, null, headers, null, timeOut, Method.Get, callerName, lineNumber, filePath);
            if (apiResponse.IsSuccess)
            {
                try
                {
                    var accessKey = Newtonsoft.Json.JsonConvert.DeserializeObject<CustomerDto>(apiResponse.Response);
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Success"), callerName, lineNumber, filePath);
                    return Tuple.Create(accessKey, "");
                }
                catch (Exception ex)
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error: " + apiResponse.Response, ex, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return Tuple.Create<CustomerDto?, string>(null, ex.Message);
                }
            }
            else
            {
                if (apiResponse.ApiStatusCode == 401)
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error", "Un Auth", ActionType: EmSystemActionType.WARNING), callerName, lineNumber, filePath);
                    Auth.Login();
                    return GetById(id, timeOut, callerName, lineNumber, filePath);
                }
                else
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error Code", apiResponse.ApiStatusCode, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return Tuple.Create<CustomerDto?, string>(null, apiResponse.Response);
                }
            }
        }
        public async Task<Tuple<CustomerDto?, string>> CreateAsync(CustomerDto customer, int timeOut = 10000, [CallerMemberName] string callerName = "",
                                                                [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "")
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{GetInitRoute(EmApiObjectType.CUSTOMERS)}";

            string baseLog = $"Create Customer {customer.Name} - {customer.Code} - {customer.Collection}";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);

            Dictionary<string, string> headers = new()
            {
                { "Authorization","Bearer " + Auth.ApiAuthResult.AccessToken  }
            };

            var apiResponse = await ApiHelper.GeneralJsonAPIAsync(apiUrl, customer, headers, null, timeOut, Method.Post, callerName, lineNumber, filePath);
            if (apiResponse.IsSuccess)
            {
                try
                {
                    var kzBaseResponse = Newtonsoft.Json.JsonConvert.DeserializeObject<CustomerDto>(apiResponse.Response);
                    if (kzBaseResponse == null)
                    {
                        SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error: " + apiResponse.Response, "", ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                        return Tuple.Create<CustomerDto?, string>(null, apiResponse.Response);
                    }
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Success"), callerName, lineNumber, filePath);
                    return Tuple.Create<CustomerDto?, string>(kzBaseResponse, "");
                }
                catch (Exception ex)
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error: " + apiResponse.Response, ex, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return Tuple.Create<CustomerDto?, string>(null, apiResponse.Response);
                }
            }
            else
            {
                if (apiResponse.ApiStatusCode == 401)
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error", "Un Auth", ActionType: EmSystemActionType.WARNING), callerName, lineNumber, filePath);
                    await Auth.LoginAsync();
                    return await CreateAsync(customer, timeOut, callerName, lineNumber, filePath);
                }
                else
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error Code", apiResponse.ApiStatusCode, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return Tuple.Create<CustomerDto?, string>(null, apiResponse.Response);
                }
            }
        }
    }
}
