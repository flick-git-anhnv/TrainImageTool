using iParkingv8.Object.Objects.Bases;
using iParkingv8.Object.Objects.Payments;
using IParkingv8.API.Interfaces;
using IParkingv8.API.Objects;
using Kztek.Api;
using Kztek.Object;
using Kztek.Tool;
using RestSharp;
using System.Runtime.CompilerServices;
using static IParkingv8.API.Implementation.v8.ApiUrlManagement;

namespace IParkingv8.API.Implementation.v8
{
    public class PaymentService8(IAuth auth) : IPaymentService
    {
        public IAuth Auth { get; set; } = auth;

        #region Transactions
        public async Task<Transaction?> CheckPaymentStatusAsync(string orderId, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true)
        {
            await Task.Delay(1);
            return null;
        }
        public async Task<Transaction?> CreateTransactionAsync(string targetId, long cost, TargetType type, OrderMethod method, OrderProvider provider, string description = "",
                                                                             int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true)
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{ApiUrlManagement.GetInitRoute(EmApiObjectType.TRANSACTIONS)}";
            string baseLog = $"Create Transaction For {type}-{targetId}-{method}-{cost}";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);
            Dictionary<string, string> headers = new()
            {
                { "Authorization","Bearer " + Auth.ApiAuthResult.AccessToken  }
            };

            var body = new
            {
                TargetId = targetId,
                TargetType = type.ToString(),
                Provider = provider.ToString(),
                Method = method.ToString(),
                Amount = cost,
                description = description,
            };
            var apiResponse = await ApiHelper.GeneralJsonAPIAsync(apiUrl, body, headers, null, timeOut, Method.Post, callerName, lineNumber, filePath);

            if (apiResponse.IsSuccess)
            {
                try
                {
                    var transaction = Newtonsoft.Json.JsonConvert.DeserializeObject<Transaction>(apiResponse.Response);
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Success"), callerName, lineNumber, filePath);
                    return transaction;
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
                    return await CreateTransactionAsync(targetId, cost, type, method, provider, description, timeOut, callerName, lineNumber, filePath);
                }
                else
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error Code", apiResponse.ApiStatusCode, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return null;
                }
            }
        }
        public async Task<Transaction?> CreateTransactionAsync(PaymentRequest paymentRequest, int timeOut = 10000,
            [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true)
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{ApiUrlManagement.GetInitRoute(EmApiObjectType.TRANSACTIONS)}";
            string baseLog = $"Create Transaction For {paymentRequest.TargetType}-{paymentRequest.TargetId}-{paymentRequest.Method}-{paymentRequest.Amount}";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);
            Dictionary<string, string> headers = new()
            {
                { "Authorization","Bearer " + Auth.ApiAuthResult.AccessToken  }
            };
            var a = Newtonsoft.Json.JsonConvert.SerializeObject(paymentRequest);
            var apiResponse = await ApiHelper.GeneralJsonAPIAsync(apiUrl, paymentRequest, headers, null, timeOut, Method.Post);

            if (apiResponse.IsSuccess)
            {
                try
                {
                    var transaction = Newtonsoft.Json.JsonConvert.DeserializeObject<Transaction>(apiResponse.Response);
                    return transaction;
                }
                catch (Exception ex)
                {
                    return null;
                }
            }
            else
            {
                if (apiResponse.ApiStatusCode == 401)
                {
                    await Auth.LoginAsync();
                    return await CreateTransactionAsync(paymentRequest, timeOut, callerName, lineNumber, filePath);
                }
                else
                {
                    return null;
                }
            }
        }

        #endregion

        #region Discounts
        public async Task<List<VoucherApply>?> GetAppliedVoucherDataAsync(string entryId, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true)
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{ApiUrlManagement.GetInitRoute(EmApiObjectType.DISCOUNTS)}";
            string baseLog = $"Get Applied Discounts By Entry Id {entryId}";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);

            var parameter = new Dictionary<string, string>()
            {
                { "entryId", entryId},
            };
            Dictionary<string, string> headers = new()
            {
                { "Authorization","Bearer " + Auth.ApiAuthResult.AccessToken  }
            };
            var apiResponse = await ApiHelper.GeneralJsonAPIAsync(apiUrl, null, headers, parameter, timeOut, Method.Get, callerName, lineNumber, filePath);
            if (apiResponse.IsSuccess)
            {
                try
                {
                    var kzBaseResponse = Newtonsoft.Json.JsonConvert.DeserializeObject<List<VoucherApply>>(apiResponse.Response);
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Success"), callerName, lineNumber, filePath);
                    return kzBaseResponse;
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
                    return await GetAppliedVoucherDataAsync(entryId, timeOut, callerName, lineNumber, filePath);
                }
                else
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error Code", apiResponse.ApiStatusCode, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return null;
                }
            }
        }
        public async Task<Tuple<VoucherDetail?, BaseErrorData?>?> ApplyVoucherEntryAsync(string voucherCode, string accessKeyCode, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true)
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{ApiUrlManagement.GetInitRoute(EmApiObjectType.DISCOUNTS)}";
            string baseLog = $"Apply Discount Entry {accessKeyCode} - {voucherCode}";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);
            Dictionary<string, string> headers = new()
            {
                { "Authorization","Bearer " + Auth.ApiAuthResult.AccessToken  }
            };

            var body = new
            {
                VoucherCode = voucherCode,
                AccessKeyCode = accessKeyCode,
                TransactionTargetType = "ENTRY",
            };
            var apiResponse = await ApiHelper.GeneralJsonAPIAsync(apiUrl, body, headers, null, timeOut, Method.Post, callerName, lineNumber, filePath);

            if (apiResponse.IsSuccess)
            {
                try
                {
                    var voucherDetail = Newtonsoft.Json.JsonConvert.DeserializeObject<VoucherDetail>(apiResponse.Response);
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Success"), callerName, lineNumber, filePath);
                    return Tuple.Create<VoucherDetail?, BaseErrorData?>(voucherDetail, null);
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
                    return await ApplyVoucherEntryAsync(voucherCode, accessKeyCode, timeOut, callerName, lineNumber, filePath);
                }
                else
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error Code", apiResponse.ApiStatusCode, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    var errorData = Newtonsoft.Json.JsonConvert.DeserializeObject<BaseErrorData>(apiResponse.Response);
                    if (errorData != null)
                    {
                        errorData.Route = "discounts";
                    }
                    return Tuple.Create<VoucherDetail?, BaseErrorData?>(null, errorData);
                }
            }
        }
        public async Task<Tuple<VoucherAppliedResult?, BaseErrorData?>?> ApplyVoucherExitAsync(string voucherCode, string accessKeyCode, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true)
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{ApiUrlManagement.GetInitRoute(EmApiObjectType.DISCOUNTS)}";
            string baseLog = $"Apply Discount Exit {accessKeyCode} - {voucherCode}";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);
            Dictionary<string, string> headers = new()
            {
                { "Authorization","Bearer " + Auth.ApiAuthResult.AccessToken  }
            };

            var body = new
            {
                VoucherCode = voucherCode,
                AccessKeyCode = accessKeyCode,
                TransactionTargetType = "EXIT",
            };

            var apiResponse = await ApiHelper.GeneralJsonAPIAsync(apiUrl, body, headers, null, timeOut, Method.Post, callerName, lineNumber, filePath);

            if (apiResponse.IsSuccess)
            {
                try
                {
                    var voucherDetail = Newtonsoft.Json.JsonConvert.DeserializeObject<VoucherAppliedResult>(apiResponse.Response);
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Success"), callerName, lineNumber, filePath);
                    return Tuple.Create<VoucherAppliedResult?, BaseErrorData?>(voucherDetail, null);
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
                    return await ApplyVoucherExitAsync(voucherCode, accessKeyCode, timeOut, callerName, lineNumber, filePath);
                }
                else
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error Code", apiResponse.ApiStatusCode, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    var errorData = Newtonsoft.Json.JsonConvert.DeserializeObject<BaseErrorData>(apiResponse.Response);
                    if (errorData != null)
                    {
                        errorData.Route = "discounts";
                    }
                    return Tuple.Create<VoucherAppliedResult?, BaseErrorData?>(null, errorData);
                }
            }
        }
        #endregion

        #region Voucher - Types
        public async Task<List<Voucher>?> GetVoucherDataAsync(string accessKeyGroupId, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true)
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{ApiUrlManagement.SearchObjectDataRoute(EmApiObjectType.VOUCHER_TYPES)}";
            string baseLog = $"Get Valid Voucher-types by CollectionId - {accessKeyGroupId}";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);
            Dictionary<string, string> headers = new()
            {
                { "Authorization","Bearer " + Auth.ApiAuthResult.AccessToken  }
            };

            var body = new
            {
                Paging = false,
                PageIndex = 0,
                PageSize = 10,
                Filter = string.Empty,
            };
            var apiResponse = await ApiHelper.GeneralJsonAPIAsync(apiUrl, body, headers, null, timeOut, Method.Post, callerName, lineNumber, filePath);
            if (apiResponse.IsSuccess)
            {
                try
                {
                    var kzBaseResponse = Newtonsoft.Json.JsonConvert.DeserializeObject<BaseResponse<List<Voucher>>>(apiResponse.Response);
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Success"), callerName, lineNumber, filePath);
                    return kzBaseResponse?.Data;
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
                    return await GetVoucherDataAsync(accessKeyGroupId, timeOut, callerName, lineNumber, filePath);
                }
                else
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error Code", apiResponse.ApiStatusCode, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return null;
                }
            }
        }

        public async Task<EPassVehicleInfo?> GetEPassVehicleInfoByCodeAsync(string code, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true)
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}transactions/epc/{code}?method=EPASS";
            string baseLog = $"Get EPass Vehcicle Info By Code - {code}";
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
                    var vehicleInfo = Newtonsoft.Json.JsonConvert.DeserializeObject<EPassVehicleInfo>(apiResponse.Response);
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Success"), callerName, lineNumber, filePath);
                    return vehicleInfo;
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
                    return await GetEPassVehicleInfoByCodeAsync(code, timeOut, callerName, lineNumber, filePath);
                }
                else
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error Code", apiResponse.ApiStatusCode, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return null;
                }
            }
        }
        #endregion
    }
}
