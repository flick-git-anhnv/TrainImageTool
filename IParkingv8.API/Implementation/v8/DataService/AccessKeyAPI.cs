using iParkingv8.Object.Enums.ParkingEnums;
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
    public class AccessKeyAPI(IAuth auth) : IAccessKey
    {
        public IAuth Auth { get; set; } = auth;

        //CREATE
        public async Task<Tuple<AccessKey?, string>> CreateAsync(AccessKey accessKey, int timeOut = 10000, [CallerMemberName] string callerName = "",
                                                                        [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "")
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{GetInitRoute(EmApiObjectType.ACCESS_KEY)}";

            string baseLog = $"Create AccessKey {accessKey.Name} - {accessKey.Code} - {accessKey.Type} - {accessKey.Collection}";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);

            Dictionary<string, string> headers = new()
            {
                { "Authorization","Bearer " + Auth.ApiAuthResult.AccessToken  }
            };

            var data = new
            {
                name = accessKey.Name,
                code = accessKey.Code,
                CollectionId = accessKey.Collection?.Id ?? "",
                type = (int)accessKey.Type,
                CustomerId = accessKey.Customer?.Id ?? accessKey.CustomerId ?? "",
                Metrics = accessKey.Metrics,
                status = 1,
                note = "",
                ExpireUtc = new DateTime(2099, 12, 12, 12, 12, 12).ToString("yyyy-MM-ddTHH:mm:ssZ"),
                lastActivatedUtc = DateTime.Now.ToString("yyyy-MM-ddTHH:mm:ssZ")
            };

            var apiResponse = await ApiHelper.GeneralJsonAPIAsync(apiUrl, data, headers, null, timeOut, Method.Post, callerName, lineNumber, filePath);
            if (apiResponse.Response.Contains("\"errorCode\":\"ERROR.ENTITY.VALIDATION.FIELD_DUPLICATED\""))
            {
                var response = await GetByCodeAsync(accessKey.Code, timeOut, accessKeyType: accessKey.Type, callerName, lineNumber, filePath);
                SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Success", response), callerName, lineNumber, filePath);
                return Tuple.Create(response?.Item1, apiResponse.Response);
            }
            if (apiResponse.IsSuccess)
            {
                try
                {
                    var kzBaseResponse = Newtonsoft.Json.JsonConvert.DeserializeObject<AccessKey>(apiResponse.Response);
                    if (kzBaseResponse == null)
                    {
                        SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error: " + apiResponse.Response, "", ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                        return Tuple.Create<AccessKey?, string>(null, apiResponse.Response);
                    }
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Success"), callerName, lineNumber, filePath);
                    return Tuple.Create<AccessKey?, string>(kzBaseResponse, "");
                }
                catch (Exception ex)
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error: " + apiResponse.Response, ex, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return Tuple.Create<AccessKey?, string>(null, apiResponse.Response);
                }
            }
            else
            {
                if (apiResponse.ApiStatusCode == 401)
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error", "Un Auth", ActionType: EmSystemActionType.WARNING), callerName, lineNumber, filePath);
                    await Auth.LoginAsync();
                    return await CreateAsync(accessKey, timeOut, callerName, lineNumber, filePath);
                }
                else
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error Code", apiResponse.ApiStatusCode, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return Tuple.Create<AccessKey?, string>(null, apiResponse.Response);
                }
            }
        }
        public Tuple<AccessKey?, string> Create(AccessKey accessKey, int timeOut = 10000, [CallerMemberName] string callerName = "",
                                                                        [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "")
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{GetInitRoute(EmApiObjectType.ACCESS_KEY)}";

            string baseLog = $"Create AccessKey {accessKey.Name} - {accessKey.Code} - {accessKey.Type} - {accessKey.Collection}";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);

            Dictionary<string, string> headers = new()
            {
                { "Authorization","Bearer " + Auth.ApiAuthResult.AccessToken  }
            };

            var data = new
            {
                name = accessKey.Name,
                code = accessKey.Code,
                CollectionId = accessKey.Collection?.Id ?? "",
                type = (int)accessKey.Type,
                status = 1,
                note = "",
            };

            var apiResponse = ApiHelper.GeneralJsonAPI(apiUrl, data, headers, null, timeOut, Method.Post, callerName, lineNumber, filePath);
            if (apiResponse.Response.Contains("\"errorCode\":\"ERROR.ENTITY.VALIDATION.FIELD_DUPLICATED\""))
            {
                var response = GetByCode(accessKey.Code, timeOut, accessKeyType: accessKey.Type, callerName, lineNumber, filePath);
                SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Success", response), callerName, lineNumber, filePath);
                return Tuple.Create(response?.Item1, apiResponse.Response);
            }
            if (apiResponse.IsSuccess)
            {
                try
                {
                    var kzBaseResponse = Newtonsoft.Json.JsonConvert.DeserializeObject<AccessKey>(apiResponse.Response);
                    if (kzBaseResponse == null)
                    {
                        SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error: " + apiResponse.Response, "", ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                        return Tuple.Create<AccessKey?, string>(null, apiResponse.Response);
                    }
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Success"), callerName, lineNumber, filePath);
                    return Tuple.Create<AccessKey?, string>(kzBaseResponse, "");
                }
                catch (Exception ex)
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error: " + apiResponse.Response, ex, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return Tuple.Create<AccessKey?, string>(null, apiResponse.Response);
                }
            }
            else
            {
                if (apiResponse.ApiStatusCode == 401)
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error", "Un Auth", ActionType: EmSystemActionType.WARNING), callerName, lineNumber, filePath);
                    Auth.Login();
                    return Create(accessKey, timeOut, callerName, lineNumber, filePath);
                }
                else
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error Code", apiResponse.ApiStatusCode, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return Tuple.Create<AccessKey?, string>(null, apiResponse.Response);
                }
            }
        }

        //GET ALL
        public async Task<BaseReport<AccessKey>?> GetAllAsync(int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0,
                                                         [CallerFilePath] string filePath = "", int pageIndex = 0, int pageSize = Filter.PAGE_SIZE)
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{SearchObjectDataRoute(EmApiObjectType.ACCESS_KEY)}";

            string baseLog = $"Get All AccessKey";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);

            Dictionary<string, string> headers = new()
            {
                { "Authorization","Bearer " + Auth.ApiAuthResult.AccessToken  }
            };

            var filter1 = Filter.CreateFilterItem(
            [
                new FilterModel("type", "TEXT", "VEHICLE", "neq"),
                new FilterModel("deleted", "BOOLEAN", "false", "eq"),
            ], EmMainOperation.and);

            List<Dictionary<string, List<FilterModel>>> filterItems = [filter1];
            var filter = Filter.CreateAccessKeyFilter(filterItems, false, pageIndex: pageIndex, pageSize: pageSize);

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
                    return await GetAllAsync(timeOut, callerName, lineNumber, filePath, pageIndex, pageSize);
                }
                else
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error Code", apiResponse.ApiStatusCode, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return null;
                }
            }
        }
        public BaseReport<AccessKey>? GetAll(int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0,
                                                        [CallerFilePath] string filePath = "", int pageIndex = 0, int pageSize = Filter.PAGE_SIZE)
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{SearchObjectDataRoute(EmApiObjectType.ACCESS_KEY)}";

            string baseLog = $"Get All AccessKey";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);

            Dictionary<string, string> headers = new()
            {
                { "Authorization","Bearer " + Auth.ApiAuthResult.AccessToken  }
            };

            var filter1 = Filter.CreateFilterItem(
                     [
                         new FilterModel("type", "TEXT", "VEHICLE", "neq"),
                new FilterModel("deleted", "BOOLEAN", "false", "eq"),
            ], EmMainOperation.and);

            List<Dictionary<string, List<FilterModel>>> filterItems = [filter1];
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
                    return GetAll(timeOut, callerName, lineNumber, filePath, pageIndex, pageSize);
                }
                else
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error Code", apiResponse.ApiStatusCode, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return null;
                }
            }
        }

        //GET BY CONDITION
        public async Task<BaseReport<AccessKey>?> GetByConditionAsync(string keyword, string collectionId, EmAccessKeyStatus? status, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0,
                                                                      [CallerFilePath] string filePath = "", int pageIndex = 0, int pageSize = Filter.PAGE_SIZE)
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{SearchObjectDataRoute(EmApiObjectType.ACCESS_KEY)}";

            string baseLog = $"Get AccessKey By Condition {keyword}";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);

            Dictionary<string, string> headers = new()
            {
                { "Authorization","Bearer " + Auth.ApiAuthResult.AccessToken  }
            };

            List<FilterModel> filterModels = [
                      new FilterModel("type", "TEXT", "VEHICLE", "neq"),
                      new FilterModel("deleted", "BOOLEAN", "false", "eq"),
                  ];
            if (status != null)
            {
                filterModels.Add(new FilterModel("status", "TEXT", status.ToString(), "eq"));
            }
            if (!string.IsNullOrEmpty(collectionId))
            {
                filterModels.Add(new FilterModel("collectionId", "GUID", collectionId, "in"));
            }
            var filter1 = Filter.CreateFilterItem(filterModels, EmMainOperation.and);

            var filterKeyword = Filter.CreateFilterItem(
            [
                new FilterModel("name", "TEXT", keyword, "contains"),
                new FilterModel("code", "TEXT", keyword, "contains"),
                new FilterModel("metrics_json.AccessKey.Code", "TEXT", keyword, "jexists"),
                //new FilterModel("RelatedMetrics.Select(x => x.AccessKey.Code)", "TEXT", keyword, "contains"),
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
                    return await GetByConditionAsync(keyword, collectionId, status, timeOut, callerName, lineNumber, filePath, pageIndex, pageSize);
                }
                else
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error Code", apiResponse.ApiStatusCode, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return null;
                }
            }
        }
        public BaseReport<AccessKey>? GetByCondition(string keyword, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0,
                                                                     [CallerFilePath] string filePath = "", int pageIndex = 0, int pageSize = Filter.PAGE_SIZE)
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{SearchObjectDataRoute(EmApiObjectType.ACCESS_KEY)}";

            string baseLog = $"Get AccessKey By Condition {keyword}";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);

            Dictionary<string, string> headers = new()
            {
                { "Authorization","Bearer " + Auth.ApiAuthResult.AccessToken  }
            };

            var filter1 = Filter.CreateFilterItem(
         [
             new FilterModel("type", "TEXT", "VEHICLE", "neq"),
                new FilterModel("deleted", "BOOLEAN", "false", "eq"),
            ], EmMainOperation.and);

            var filterKeyword = Filter.CreateFilterItem(
            [
                new FilterModel("name", "TEXT", keyword, "contains"),
                new FilterModel("code", "TEXT", keyword, "contains"),
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
                    return GetByCondition(keyword, timeOut, callerName, lineNumber, filePath, pageIndex, pageSize);
                }
                else
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error Code", apiResponse.ApiStatusCode, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return null;
                }
            }
        }


        public async Task<Tuple<AccessKey?, BaseErrorData?>?> GetByCodeAsync(string code, int timeOut = 10000, EmAccessKeyType accessKeyType = EmAccessKeyType.CARD,
                                                       [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "")
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{GetInitRoute(EmApiObjectType.ACCESS_KEY)}";
            string baseLog = $"Get AccessKey By Code {code}";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);

            Dictionary<string, string> headers = new()
            {
                { "Authorization","Bearer " + Auth.ApiAuthResult.AccessToken  }
            };
            var parameters = new Dictionary<string, string>()
            {
                { "code",code},
                { "type", ((int)accessKeyType ).ToString()}
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
                    return await GetByCodeAsync(code, timeOut, accessKeyType, callerName, lineNumber, filePath);
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
        public Tuple<AccessKey?, BaseErrorData?>? GetByCode(string code, int timeOut = 10000, EmAccessKeyType accessKeyType = EmAccessKeyType.CARD,
                                                       [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "")
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{GetInitRoute(EmApiObjectType.ACCESS_KEY)}";
            string baseLog = $"Get AccessKey By Code {code}";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);

            Dictionary<string, string> headers = new()
            {
                { "Authorization","Bearer " + Auth.ApiAuthResult.AccessToken  }
            };
            var parameters = new Dictionary<string, string>()
            {
                { "code",code},
                { "type", ((int)accessKeyType ).ToString()}
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
                    return GetByCode(code, timeOut, accessKeyType, callerName, lineNumber, filePath);
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

        //GET BY ID
        public async Task<Tuple<AccessKey?, string>> GetByIdAsync(string id, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0,
                                                                           [CallerFilePath] string filePath = "")
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{GetInitRoute(EmApiObjectType.ACCESS_KEY)}/{id}";

            string baseLog = $"Get AccessKey By Id {id}";
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
                    var accessKey = Newtonsoft.Json.JsonConvert.DeserializeObject<AccessKey>(apiResponse.Response);
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Success", accessKey), callerName, lineNumber, filePath);
                    return Tuple.Create(accessKey, "");
                }
                catch (Exception ex)
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error: " + apiResponse.Response, ex, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return Tuple.Create<AccessKey?, string>(null, apiResponse.Response);
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
                    return Tuple.Create<AccessKey?, string>(null, apiResponse.Response);
                }
            }
        }
        public async Task<Tuple<AccessKey?, string>> GetById(string id, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0,
                                                                           [CallerFilePath] string filePath = "")
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{GetInitRoute(EmApiObjectType.ACCESS_KEY)}/{id}";

            string baseLog = $"Get AccessKey By Id {id}";
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
                    var accessKey = Newtonsoft.Json.JsonConvert.DeserializeObject<AccessKey>(apiResponse.Response);
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Success", accessKey), callerName, lineNumber, filePath);
                    return Tuple.Create(accessKey, "");
                }
                catch (Exception ex)
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error: " + apiResponse.Response, ex, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return Tuple.Create<AccessKey?, string>(null, apiResponse.Response);
                }
            }
            else
            {
                if (apiResponse.ApiStatusCode == 401)
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error", "Un Auth", ActionType: EmSystemActionType.WARNING), callerName, lineNumber, filePath);
                    Auth.Login();
                    return await GetById(id, timeOut, callerName, lineNumber, filePath);
                }
                else
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error Code", apiResponse.ApiStatusCode, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return Tuple.Create<AccessKey?, string>(null, apiResponse.Response);
                }
            }
        }

        //UPDATE
        public async Task<bool> UpdateCollectionAsync(string accessKeyId, string collectionId, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0,
                                                 [CallerFilePath] string filePath = "")
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{GetInitRoute(EmApiObjectType.ACCESS_KEY)}";

            string baseLog = $"Check AccessKey Collection {accessKeyId} - {collectionId}";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);

            Dictionary<string, string> headers = new()
            {
                { "Authorization","Bearer " + Auth.ApiAuthResult.AccessToken  }
            };

            var commitData = new List<CommitData>
            {
                new()
                {
                    Op = "replace",
                    Path = "collectionId",
                    Value = collectionId
                }
            };

            var body = new
            {
                ids = new List<string>() { accessKeyId },
                jsonPatchDocument = commitData,
            };

            var apiResponse = await ApiHelper.GeneralJsonAPIAsync(apiUrl, body, headers, null, timeOut, Method.Patch, callerName, lineNumber, filePath);
            if (apiResponse.IsSuccess)
            {
                SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Success"), callerName, lineNumber, filePath);
                return true;
            }
            else
            {
                if (apiResponse.ApiStatusCode == 401)
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error", "Un Auth", ActionType: EmSystemActionType.WARNING), callerName, lineNumber, filePath);
                    await Auth.LoginAsync();
                    return await UpdateCollectionAsync(accessKeyId, collectionId, timeOut, callerName, lineNumber, filePath);
                }
                else
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error Code", apiResponse.ApiStatusCode, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return false;
                }
            }
        }
        public bool UpdateCollection(string accessKeyId, string collectionId, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0,
                                               [CallerFilePath] string filePath = "")
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{GetInitRoute(EmApiObjectType.ACCESS_KEY)}";

            string baseLog = $"Check AccessKey Collection {accessKeyId} - {collectionId}";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);

            Dictionary<string, string> headers = new()
            {
                { "Authorization","Bearer " + Auth.ApiAuthResult.AccessToken  }
            };
            var commitData = new List<CommitData>
            {
                new()
                {
                    Op = "replace",
                    Path = "collectionId",
                    Value = collectionId
                }
            };

            var body = new
            {
                ids = new List<string>() { accessKeyId },
                jsonPatchDocument = commitData,
            };

            var apiResponse = ApiHelper.GeneralJsonAPI(apiUrl, body, headers, null, timeOut, Method.Patch, callerName, lineNumber, filePath);
            if (apiResponse.IsSuccess)
            {
                SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Success"), callerName, lineNumber, filePath);
                return true;
            }
            else
            {
                if (apiResponse.ApiStatusCode == 401)
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error", "Un Auth", ActionType: EmSystemActionType.WARNING), callerName, lineNumber, filePath);
                    Auth.Login();
                    return UpdateCollection(accessKeyId, collectionId, timeOut, callerName, lineNumber, filePath);
                }
                else
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error Code", apiResponse.ApiStatusCode, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return false;
                }
            }
        }
        //DELETE
        public async Task<bool> DeleteByIdAsync(string id, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0,
                                                 [CallerFilePath] string filePath = "")
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{GetInitRoute(EmApiObjectType.ACCESS_KEY)}/{id}";

            string baseLog = $"Delete AccessKey By Id {id}";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);

            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + Auth.ApiAuthResult.AccessToken  }
            };
            var apiResponse = await ApiHelper.GeneralJsonAPIAsync(apiUrl, null, headers, null, timeOut, Method.Delete, callerName, lineNumber, filePath);
            if (apiResponse.IsSuccess)
            {
                SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Success"), callerName, lineNumber, filePath);
                return true;
            }
            else
            {
                if (apiResponse.ApiStatusCode == 401)
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error", "Un Auth", ActionType: EmSystemActionType.WARNING), callerName, lineNumber, filePath);
                    await Auth.LoginAsync();
                    return await DeleteByIdAsync(id, timeOut, callerName, lineNumber, filePath);
                }
                else
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error Code", apiResponse.ApiStatusCode, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return false;
                }
            }
        }
        public bool DeleteById(string id, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0,
                                             [CallerFilePath] string filePath = "")
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{GetInitRoute(EmApiObjectType.ACCESS_KEY)}/{id}";

            string baseLog = $"Delete AccessKey By Id {id}";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);

            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + Auth.ApiAuthResult.AccessToken  }
            };
            var apiResponse = ApiHelper.GeneralJsonAPI(apiUrl, null, headers, null, timeOut, Method.Delete, callerName, lineNumber, filePath);
            if (apiResponse.IsSuccess)
            {
                SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Success"), callerName, lineNumber, filePath);
                return true;
            }
            else
            {
                if (apiResponse.ApiStatusCode == 401)
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error", "Un Auth", ActionType: EmSystemActionType.WARNING), callerName, lineNumber, filePath);
                    Auth.Login();
                    return DeleteById(id, timeOut, callerName, lineNumber, filePath);
                }
                else
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error Code", apiResponse.ApiStatusCode, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return false;
                }
            }
        }
        public BaseReport<AccessKey>? GetByUserId(string userId, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0,
                                                             [CallerFilePath] string filePath = "", int pageIndex = 0, int pageSize = Filter.PAGE_SIZE)
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{SearchObjectDataRoute(EmApiObjectType.ACCESS_KEY)}";

            string baseLog = $"Get AccessKey By UserId {userId}";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);

            Dictionary<string, string> headers = new()
      {
          { "Authorization","Bearer " + Auth.ApiAuthResult.AccessToken  }
      };

            var filter1 = Filter.CreateFilterItem(
            [
             new FilterModel("type", "TEXT", "FACE_ID", "eq"),
             new FilterModel("deleted", "BOOLEAN", "false", "eq"),
             new FilterModel("customer.userId", "TEXT", userId, "eq"),
      ], EmMainOperation.and);

            List<Dictionary<string, List<FilterModel>>> filterItems = [];
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
                    return GetByUserId(userId, timeOut, callerName, lineNumber, filePath, pageIndex, pageSize);
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
