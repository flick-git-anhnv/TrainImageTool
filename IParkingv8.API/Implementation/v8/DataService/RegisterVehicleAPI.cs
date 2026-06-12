using iParkingv8.Object.Enums.ParkingEnums;
using iParkingv8.Object.Enums.Parkings;
using iParkingv8.Object.Objects.Bases;
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
    public class RegisterVehicleAPI(IAuth auth) : IRegisterVehicle
    {
        public IAuth Auth { get; set; } = auth;

        public async Task<BaseReport<AccessKey>> GetByConditionAsync(string keyword, string collectionId, EmVehicleType? vehicleType,
                                                        string customerGroupId, int timeOut = 10000,
                                [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true,
                                int pageIndex = 0, int pageSize = Filter.PAGE_SIZE)
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{SearchObjectDataRoute(EmApiObjectType.ACCESS_KEY)}";

            string baseLog = $"Get Register Vehicles By Condition {keyword} - {collectionId}";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);

            Dictionary<string, string> headers = new()
            {
                { "Authorization","Bearer " + Auth.ApiAuthResult.AccessToken  }
            };

            List<FilterModel> filterModels = [
                new FilterModel("type", "TEXT", "VEHICLE", "eq"),
                new FilterModel("deleted", "BOOLEAN", "false", "eq"),
            ];

            if (!string.IsNullOrEmpty(collectionId))
            {
                filterModels.Add(new FilterModel("collectionId", "GUID", collectionId, "in"));
            }
            if (vehicleType != null)
            {
                filterModels.Add(new FilterModel("collection_json ->> 'VehicleType'", "TEXT", vehicleType.ToString(), "eq"));
            }

            if (!string.IsNullOrEmpty(customerGroupId))
            {
                filterModels.Add(new FilterModel("customer_json ->> 'CollectionId'", "TEXT", customerGroupId, "in"));
            }
            var filter1 = Filter.CreateFilterItem(filterModels, EmMainOperation.and);

            var filterKeyword = Filter.CreateFilterItem(
            [
                new FilterModel("name", "TEXT", keyword, "contains"),
                new FilterModel("customer_json ->> 'Name'", "TEXT", keyword, "contains"),
                new FilterModel("note", "TEXT", keyword, "contains"),
                new FilterModel("metrics_json.RelatedAccessKey.Code", "TEXT", keyword, "jexists"),
                new FilterModel("metrics_json.RelatedAccessKey.Name", "TEXT", keyword, "jexists"),
                new FilterModel("REGEXP_REPLACE(Code, '[^a-zA-Z0-9.]', '', 'g')", "TEXT", keyword, "contains"),
            ], EmMainOperation.or);

            List<Dictionary<string, List<FilterModel>>> filterItems = [];
            if (!string.IsNullOrEmpty(keyword))
            {
                filterItems.Add(filterKeyword);
            }
            filterItems.Add(filter1);
            var filter = Filter.CreateAccessKeyFilter(filterItems, true, pageIndex: pageIndex, pageSize: pageSize);

            var apiResponse = await ApiHelper.GeneralJsonAPIAsync(apiUrl, filter, headers, null, timeOut, Method.Post, callerName, lineNumber, filePath);
            if (apiResponse.IsSuccess)
            {
                var baseResponse = NewtonSoftHelper<BaseReport<AccessKey>>.GetBaseResponse(apiResponse.Response);
                SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Success"), callerName, lineNumber, filePath);
                return baseResponse;
            }
            else
            {
                if (apiResponse.ApiStatusCode == 401)
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error", "Un Auth", ActionType: EmSystemActionType.WARNING), callerName, lineNumber, filePath);
                    await Auth.LoginAsync();
                    return await GetByConditionAsync(keyword, collectionId, vehicleType, customerGroupId, timeOut, callerName, lineNumber, filePath, true, pageIndex, pageSize);
                }
                else
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error Code", apiResponse.ApiStatusCode, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return null;
                }
            }
        }
        public BaseReport<AccessKey> GetByCondition(string keyword, string collectionId, int timeOut = 10000,
                             [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true,
                             int pageIndex = 0, int pageSize = Filter.PAGE_SIZE)
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{SearchObjectDataRoute(EmApiObjectType.ACCESS_KEY)}";

            string baseLog = $"Get Register Vehicles By Condition {keyword} - {collectionId}";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);

            Dictionary<string, string> headers = new()
            {
                { "Authorization","Bearer " + Auth.ApiAuthResult.AccessToken  }
            };

            var filter1 = Filter.CreateFilterItem(
              [
                  new FilterModel("type", "TEXT", "VEHICLE", "eq"),
                new FilterModel("deleted", "BOOLEAN", "false", "eq"),
            ], EmMainOperation.and);

            var filterKeyword = Filter.CreateFilterItem(
            [
                new FilterModel("name", "TEXT", keyword, "contains"),
                new FilterModel("customer_json ->> 'Name'", "TEXT", keyword, "contains"),
                new FilterModel("note", "TEXT", keyword, "contains"),
                new FilterModel("metrics_json.RelatedAccessKey.Code", "TEXT", keyword, "jexists"),
                new FilterModel("metrics_json.RelatedAccessKey.Name", "TEXT", keyword, "jexists"),
                new FilterModel("REGEXP_REPLACE(Code, '[^a-zA-Z0-9.]', '', 'g')", "TEXT", keyword, "contains"),
            ], EmMainOperation.or);

            List<Dictionary<string, List<FilterModel>>> filterItems = [];
            if (!string.IsNullOrEmpty(keyword))
            {
                filterItems.Add(filterKeyword);
            }
            filterItems.Add(filter1);
            var filter = Filter.CreateAccessKeyFilter(filterItems, true, pageIndex: pageIndex, pageSize: pageSize);

            var apiResponse = ApiHelper.GeneralJsonAPI(apiUrl, filter, headers, null, timeOut, Method.Post, callerName, lineNumber, filePath);
            if (apiResponse.IsSuccess)
            {
                var baseResponse = NewtonSoftHelper<BaseReport<AccessKey>>.GetBaseResponse(apiResponse.Response);
                SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Success"), callerName, lineNumber, filePath);
                return baseResponse;
            }
            else
            {
                if (apiResponse.ApiStatusCode == 401)
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error", "Un Auth", ActionType: EmSystemActionType.WARNING), callerName, lineNumber, filePath);
                    Auth.Login();
                    return GetByCondition(keyword, collectionId, timeOut, callerName, lineNumber, filePath, true, pageIndex, pageSize);
                }
                else
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error Code", apiResponse.ApiStatusCode, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return null;
                }
            }
        }

        public async Task<bool> IsBlackListAsync(string plateNumber)
        {
            return false;
        }
        public bool IsBlackList(string plateNumber)
        {
            return false;
        }

        public async Task<Tuple<AccessKey?, BaseErrorData?>?> GetByPlateNumberAsync(string plateNumber, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true)
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{GetInitRoute(EmApiObjectType.ACCESS_KEY)}";
            string baseLog = $"Get AccessKey By Code {plateNumber}";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);

            Dictionary<string, string> headers = new()
            {
                { "Authorization","Bearer " + Auth.ApiAuthResult.AccessToken  }
            };
            var parameters = new Dictionary<string, string>()
            {
                { "code", plateNumber},
                { "type", ((int)EmAccessKeyType.VEHICLE ).ToString()}
            };
            var apiResponse = await ApiHelper.GeneralJsonAPIAsync(apiUrl, null, headers, parameters, timeOut, Method.Get, callerName, lineNumber, filePath);
            if (apiResponse.IsSuccess)
            {
                try
                {
                    var accessKey = Newtonsoft.Json.JsonConvert.DeserializeObject<AccessKey?>(apiResponse.Response);
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Success", accessKey), callerName, lineNumber, filePath);
                    return Tuple.Create<AccessKey?, BaseErrorData?>(accessKey, null);
                }
                catch (Exception ex)
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error: " + apiResponse.Response, ex, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return Tuple.Create<AccessKey?, BaseErrorData?>(null, null);
                }
            }
            else
            {
                if (apiResponse.ApiStatusCode == 401)
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error", "Un Auth", ActionType: EmSystemActionType.WARNING), callerName, lineNumber, filePath);
                    await Auth.LoginAsync();
                    return await GetByPlateNumberAsync(plateNumber, timeOut, callerName, lineNumber, filePath);
                }
                else
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error Code", apiResponse.ApiStatusCode, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    var errorData = Newtonsoft.Json.JsonConvert.DeserializeObject<BaseErrorData?>(apiResponse.Response);
                    if (errorData != null)
                    {
                        errorData.Route = GetInitRoute(EmApiObjectType.ACCESS_KEY);
                    }
                    return Tuple.Create<AccessKey?, BaseErrorData?>(null, errorData);
                }
            }
        }
        public Tuple<AccessKey?, BaseErrorData?> GetByPlateNumber(string plateNumber, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true)
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{GetInitRoute(EmApiObjectType.ACCESS_KEY)}";
            string baseLog = $"Get AccessKey By Code {plateNumber}";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);

            Dictionary<string, string> headers = new()
            {
                { "Authorization","Bearer " + Auth.ApiAuthResult.AccessToken  }
            };
            var parameters = new Dictionary<string, string>()
            {
                { "code", plateNumber},
                { "type", ((int)EmAccessKeyType.VEHICLE).ToString()}
            };
            var apiResponse = ApiHelper.GeneralJsonAPI(apiUrl, null, headers, parameters, timeOut, Method.Get, callerName, lineNumber, filePath);
            if (apiResponse.IsSuccess)
            {
                try
                {
                    var accessKey = Newtonsoft.Json.JsonConvert.DeserializeObject<AccessKey?>(apiResponse.Response);
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Success", accessKey), callerName, lineNumber, filePath);
                    return Tuple.Create<AccessKey?, BaseErrorData?>(accessKey, null);
                }
                catch (Exception ex)
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error: " + apiResponse.Response, ex, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return Tuple.Create<AccessKey?, BaseErrorData?>(null, null);
                }
            }
            else
            {
                if (apiResponse.ApiStatusCode == 401)
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error", "Un Auth", ActionType: EmSystemActionType.WARNING), callerName, lineNumber, filePath);
                    Auth.Login();
                    return GetByPlateNumber(plateNumber, timeOut, callerName, lineNumber, filePath);
                }
                else
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error Code", apiResponse.ApiStatusCode, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    var errorData = Newtonsoft.Json.JsonConvert.DeserializeObject<BaseErrorData?>(apiResponse.Response);
                    if (errorData != null)
                    {
                        errorData.Route = GetInitRoute(EmApiObjectType.ACCESS_KEY);
                    }
                    return Tuple.Create<AccessKey?, BaseErrorData?>(null, errorData);
                }
            }
        }
    }
}
