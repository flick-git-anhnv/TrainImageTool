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
    public class OperatorEntryAPI(IAuth auth) : IOperatorEntry
    {
        public IAuth Auth { get; set; } = auth;
        public async Task<Tuple<EntryData?, BaseErrorData?>?> CreateAsync(string eventId, string laneId, string accessKeyId, string plateNumber, string accessKeyCollectionId, int timeOut = 10000,
                                                                      [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true)
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{GetInitRoute(EmApiObjectType.ENTRIES)}";
            string baseLog = $"Create Entry {laneId} - {accessKeyId} - {plateNumber}";
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
                CollectionId = accessKeyCollectionId
            };
#if DEBUG
            var a = Newtonsoft.Json.JsonConvert.SerializeObject(body);
#endif
            var apiResponse = await ApiHelper.GeneralJsonAPIAsync(apiUrl, body, headers, null, timeOut,
                                                                  Method.Post, callerName, lineNumber, filePath);
            if (apiResponse.IsSuccess)
            {
                try
                {
                    var eventData = Newtonsoft.Json.JsonConvert.DeserializeObject<EntryData?>(apiResponse.Response);
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Success"), callerName, lineNumber, filePath);
                    return Tuple.Create<EntryData?, BaseErrorData?>(eventData, null);
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
                    return await CreateAsync(eventId, laneId, accessKeyId, plateNumber, accessKeyCollectionId, timeOut, callerName, lineNumber, filePath);
                }
                else
                {
                    var errorData = Newtonsoft.Json.JsonConvert.DeserializeObject<BaseErrorData?>(apiResponse.Response);
                    if (errorData != null)
                    {
                        errorData.Route = GetInitRoute(EmApiObjectType.ENTRIES);
                    }
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Success"), callerName, lineNumber, filePath);
                    return Tuple.Create<EntryData?, BaseErrorData?>(null, errorData);
                }
            }
        }
        public async Task<bool> UpdatePlateAsync(string eventId, string newPlate, string oldPlate, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true)
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{GetInitRoute(EmApiObjectType.ENTRIES)}/{eventId}";
            string baseLog = $"Update Entry PlateNumber {eventId} - {oldPlate} To {newPlate}";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);
            Dictionary<string, string> headers = new()
            {
                { "Authorization","Bearer " + Auth.ApiAuthResult.AccessToken  }
            };
            var commitData = new List<CommitData?>
            {
                new()
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
        public async Task<bool> UpdateNoteAsync(string newNote, string eventId, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true)
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{GetInitRoute(EmApiObjectType.ENTRIES)}/{eventId}";
            string baseLog = $"Update Entry Note {eventId} - {newNote}";
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
                    Value = newNote,
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
                    return await UpdateNoteAsync(newNote, eventId, timeOut, callerName, lineNumber, filePath);
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
            string apiUrl = $"{server}{GetInitRoute(EmApiObjectType.ENTRIES)}/{eventId}";
            string baseLog = $"Revert Entry By Id {eventId}";
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
                var request = new RestRequest($"/entries/{entrieId}/upload/image", Method.Put);
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
            }
        }
        public async Task<long> CheckFeeAsync(string collectionId, DateTime startTime, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true)
        {
            string server = Auth.ServerConfig.ApiUrl.StandardlizeServerName();
            string apiUrl = $"{server}{GetInitRoute(EmApiObjectType.ENTRIES)}/compute/charge";

            string baseLog = $"Check Entry Charge";
            SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess(baseLog), callerName, lineNumber, filePath);
            Dictionary<string, string> headers = new()
            {
                { "Authorization","Bearer " + Auth.ApiAuthResult.AccessToken  }
            };
            var body = new
            {
                CollectionId = collectionId,
                FromUtc = startTime.ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss.0000")
            };
#if DEBUG
            string a = Newtonsoft.Json.JsonConvert.SerializeObject(body);
#endif
            var apiResponse = await ApiHelper.GeneralJsonAPIAsync(apiUrl, body, headers, null, timeOut, Method.Post, callerName, lineNumber, filePath);
            if (apiResponse.IsSuccess)
            {
                try
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Success"), callerName, lineNumber, filePath);
                    return long.Parse(apiResponse.Response);
                }
                catch (Exception ex)
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error: " + apiResponse.Response, ex, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return -1;
                }
            }
            else
            {
                if (apiResponse.ApiStatusCode == 401)
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error", "Un Auth", ActionType: EmSystemActionType.WARNING), callerName, lineNumber, filePath);
                    await Auth.LoginAsync();
                    return await CheckFeeAsync(collectionId, startTime, timeOut, callerName, lineNumber, filePath);
                }
                else
                {
                    SystemUtils.logger.SaveSystemLog(SystemLog.CreateApplicationProccess($"{baseLog} Error Code", apiResponse.ApiStatusCode, ActionType: EmSystemActionType.ERROR), callerName, lineNumber, filePath);
                    return -1;
                }
            }
        }
    }
}
