using iParkingv8.Object.Enums.Bases;
using iParkingv8.Object.Objects.Bases;
using iParkingv8.Object.Objects.Events;
using IParkingv8.API.Interfaces;
using Kztek.Api;
using Kztek.Object;
using Kztek.Tool;
using RestSharp;
using System.Runtime.CompilerServices;
using static IParkingv8.API.Implementation.v8.ApiUrlManagement;

namespace IParkingv8.API.Implementation.v8.Operatorservice
{
    public class OperatorExitAPI(IAuth auth) : IOperatorExit
    {
        public IAuth Auth { get; set; } = auth;
        public async Task<Tuple<ExitData?, BaseErrorData?>?> CreateAsync(string eventId, string laneId, string accessKeyId, string plateNumber, string collectionId, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true)
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{GetInitRoute(EmApiObjectType.EXITS)}";

            string baseLog = $"Create Exit {laneId} - {accessKeyId} - {plateNumber}";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);

            Dictionary<string, string> headers = new()
            {
                { "Authorization","Bearer " + Auth.ApiAuthResult.AccessToken  }
            };
            var body = new
            {
                id = eventId,
                deviceId = laneId,
                accessKeyId,
                plateNumber,
                CollectionId = collectionId
            };
#if DEBUG
            string a = Newtonsoft.Json.JsonConvert.SerializeObject(body);
#endif
            var apiResponse = await ApiHelper.GeneralJsonAPIAsync(apiUrl, body, headers, null, timeOut, Method.Post, callerName, lineNumber, filePath);
            if (apiResponse.IsSuccess)
            {
                try
                {
                    var eventData = Newtonsoft.Json.JsonConvert.DeserializeObject<ExitData?>(apiResponse.Response);
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Success"), callerName, lineNumber, filePath);
                    return Tuple.Create<ExitData?, BaseErrorData?>(eventData, null);
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
                    return await CreateAsync(eventId, laneId, accessKeyId, plateNumber, collectionId, timeOut, callerName, lineNumber, filePath);
                }
                else
                {
                    var errorData = Newtonsoft.Json.JsonConvert.DeserializeObject<BaseErrorData?>(apiResponse.Response);
                    if (errorData != null)
                    {
                        errorData.Route = GetInitRoute(EmApiObjectType.EXITS);
                    }
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error Code", apiResponse.ApiStatusCode, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return Tuple.Create<ExitData?, BaseErrorData?>(null, errorData);
                }
            }
        }
        public async Task<bool> UpdatePlateAsync(string eventId, string newPlate, string oldPlate, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true)
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{GetInitRoute(EmApiObjectType.EXITS)}/{eventId}";
            string baseLog = $"Update Exit PlateNumber {eventId} - {oldPlate} To {newPlate}";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);
            Dictionary<string, string> headers = new()
            {
                { "Authorization","Bearer " + Auth.ApiAuthResult.AccessToken  }
            };
            var commitData = new List<CommitData?>
            {
                new ()
                {
                    Op = "replace",
                    Path = "plateNumber",
                    Value = newPlate.Replace("-", "").Replace(".", "").Replace(" ", ""),
                }
            };
            var apiResponse = await ApiHelper.GeneralJsonAPIAsync(apiUrl, commitData, headers, null, timeOut, Method.Patch, callerName, lineNumber, filePath);
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
                    return await UpdatePlateAsync(eventId, newPlate, oldPlate, timeOut, callerName, lineNumber, filePath);
                }
                else
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error Code", apiResponse.ApiStatusCode, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return false;
                }
            }
        }
        public async Task<bool> UpdateNoteAsync(string eventId, string note, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true)
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = server + $"exits/{eventId}";
            string baseLog = $"Update Exit Note: {note}";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);
            Dictionary<string, string> headers = new()
            {
                { "Authorization","Bearer " + Auth.ApiAuthResult.AccessToken  }
            };
            var commitData = new List<CommitData?>
            {
                new ()
                {
                    Op = "replace",
                    Path = "note",
                    Value = note,
                }
            };
            var apiResponse = await ApiHelper.GeneralJsonAPIAsync(apiUrl, commitData, headers, null, timeOut, Method.Patch, callerName, lineNumber, filePath);
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
                    return await UpdateNoteAsync(eventId, note, timeOut, callerName, lineNumber, filePath);
                }
                else
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error Code", apiResponse.ApiStatusCode, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return false;
                }
            }
        }
        public async Task<bool> DeleteByIdAsync(string eventId, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true)
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{GetInitRoute(EmApiObjectType.EXITS)}/{eventId}";
            string baseLog = $"Revert Exit By Id {eventId}";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);
            Dictionary<string, string> headers = new()
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
                    return await DeleteByIdAsync(eventId, timeOut, callerName, lineNumber, filePath);
                }
                else
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error Code", apiResponse.ApiStatusCode, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return false;
                }
            }
        }
        public async Task<bool> SaveImageAsync(List<byte> imageData, string entrieId, EmImageType imageType, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true)
        {
            while (true)
            {
                string baseLog = $"Save Entry Image {entrieId} - {imageType}";
                SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);
                if (imageData is null)
                {
                    return false;
                }
                if (imageData.Count == 0)
                {
                    return false;
                }
                var server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();

                var options = new RestClientOptions(server);
                var client = new RestClient(options);
                var request = new RestRequest($"/exits/{entrieId}/upload/image", Method.Put);
                request.AddHeader("Authorization", "Bearer " + Auth.ApiAuthResult.AccessToken);
                request.AlwaysMultipartFormData = true;
                request.AddParameter("type", imageType.ToString());
                request.AddFile($"file", [.. imageData], "x.jpg");
                request.Timeout = TimeSpan.FromSeconds(10);
                RestResponse response = await client.ExecuteAsync(request);
                if (response.IsSuccessful)
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Success", ActionType: EmSystemActionType.WARNING), callerName, lineNumber, filePath);
                    return true;
                }
                else
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Response", response.StatusCode, ActionType: EmSystemActionType.WARNING), callerName, lineNumber, filePath);
                    await Task.Delay(2000);
                }
                return false;
            }
        }
        public async Task<ExitData?> ChangeCollectionAsync(string exitId, string collectionId, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true)
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{GetInitRoute(EmApiObjectType.EXITS)}/{exitId}";
            string baseLog = $"Update Exit {exitId} CollectionId {collectionId}";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);
            Dictionary<string, string> headers = new()
            {
                { "Authorization","Bearer " + Auth.ApiAuthResult.AccessToken  }
            };
            var body = new
            {
                collectionId = collectionId,
            };
#if DEBUG
            string a = Newtonsoft.Json.JsonConvert.SerializeObject(body);
#endif
            var apiResponse = await ApiHelper.GeneralJsonAPIAsync(apiUrl, body, headers, null, timeOut, Method.Put, callerName, lineNumber, filePath);
            if (apiResponse.IsSuccess)
            {
                try
                {
                    var eventData = Newtonsoft.Json.JsonConvert.DeserializeObject<ExitData?>(apiResponse.Response);
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Success"), callerName, lineNumber, filePath);
                    return eventData;
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
                    return await ChangeCollectionAsync(exitId, collectionId, timeOut, callerName, lineNumber, filePath);
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
