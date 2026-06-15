using iParkingv5.ApiManager.KzParkingv5Apis;
using Kztek.Tool.NetworkTools;
using Kztek.Tool.TextFormatingTools;
using Kztek.Tools;
using RestSharp;
using System;
using System.Collections.Generic;
using System.Net;
using System.Threading.Tasks;

namespace iParkingv6.ApiManager
{
    public class BaseApiHelper
    {
        public class DataSend
        {
            public string Url { get; set; }
            public string Method { get; set; }
            public Dictionary<string, string> Headers { get; set; }
            public Dictionary<string, string> Params { get; set; }
            public object Data { get; set; }
            public string ErrorMessage { get; set; }
        }
        #region JSON API HELPER
        public static string startupPath = "";
        public static int timeOut = 10000;
        public static string tokenHeader = "token";
        public const int max_send_times = 2;

        public static string GeneralJsonAPI(string apiUrl, object data, Dictionary<string, string>? headerValues, Dictionary<string, string> requiredParams, int timeOut, ref string error, Method method)
        {
            var client = new RestClient(apiUrl);
            var request = new RestRequest();
            request.Method = method;
            request.Timeout = TimeSpan.FromMilliseconds(timeOut); 
            request.RequestFormat = DataFormat.Json;
            if (data != null)
                request.AddJsonBody(data);

            foreach (KeyValuePair<string, string> item in headerValues)
            {
                request.AddHeader(item.Key, item.Value);
            }
            foreach (KeyValuePair<string, string> kvp in requiredParams)
            {
                request.AddQueryParameter(kvp.Key, kvp.Value);
            }
            var response = client.Execute(request);
            if (!response.IsSuccessful)
            {
                client = new RestClient(apiUrl);
                request = new RestRequest();
                request.Method = method;
                request.Timeout = TimeSpan.FromMilliseconds(timeOut);
                request.RequestFormat = DataFormat.Json;
                if (data != null)
                    request.AddJsonBody(data);
                request.AddHeaders(headerValues);
                foreach (KeyValuePair<string, string> kvp in requiredParams)
                {
                    request.AddQueryParameter(kvp.Key, kvp.Value);
                }
                response = client.Execute(request);
                if (!response.IsSuccessful)
                {
                    error = apiUrl + ":" + response.ErrorMessage;
                    return string.Empty;
                }
            }
            return response.Content;
        }
        public static string GeneralJsonAPI(string apiUrl, string data, Dictionary<string, string>? headerValues, Dictionary<string, string> requiredParams, int timeOut, ref string error, Method method)
        {
            var client = new RestClient(apiUrl);
            var request = new RestRequest
            {
                Timeout = TimeSpan.FromMilliseconds(timeOut),
                Method = method
            };
            if (data != null)
                request.AddParameter("application/json", data, ParameterType.RequestBody);

            request.AddHeaders(headerValues);
            foreach (KeyValuePair<string, string> kvp in requiredParams)
            {
                request.AddQueryParameter(kvp.Key, kvp.Value);
            }
            var response = client.Execute(request);
            if (!response.IsSuccessful)
            {
                client = new RestClient(apiUrl);
                request = new RestRequest();
                request.Timeout = TimeSpan.FromMilliseconds(timeOut); 
                request.Method = method;
                request.RequestFormat = DataFormat.Json;
                if (data != null)
                    request.AddParameter("application/json", data, ParameterType.RequestBody);
                request.AddHeaders(headerValues);
                foreach (KeyValuePair<string, string> kvp in requiredParams)
                {
                    request.AddQueryParameter(kvp.Key, kvp.Value);
                }
                response = client.Execute(request);
                if (!response.IsSuccessful)
                {
                    error = apiUrl + ":" + response.ErrorMessage;
                    return string.Empty;
                }
            }
            return response.Content;
        }

        public class LoginResult
        {
            public string id_token { get; set; }
            public string access_token { get; set; }
            public int expires_in { get; set; }
            public string token_type { get; set; }
            public string refresh_token { get; set; }
            public string scope { get; set; }
        }

        /// <summary>
        /// Hàm gửi trả về 1 Tuple trong đó Item1 là kết quả trả về, Item2 là thông tin lỗi nếu có
        /// </summary>
        /// <param name="apiUrl"></param>
        /// <param name="data"></param>
        /// <param name="headerValues"></param>
        /// <param name="requiredParams"></param>
        /// <param name="timeOut"></param>
        /// <param name="method"></param>
        /// <returns></returns>
        public static async Task<Tuple<string, string>> GeneralJsonAPIAsync(string apiUrl, object data, Dictionary<string, string>? headerValues, Dictionary<string, string>? requiredParams, int timeOut, Method method)
        {
            if (!IsValidHost(apiUrl))
            {
                return Tuple.Create<string, string>(string.Empty, "PING ERROR");
            }

            DataSend dataSend = new DataSend()
            {
                Url = apiUrl,
                Method = method.ToString(),
                Headers = headerValues,
                Params = requiredParams,
                Data = data,
            };

            string errorMessage = string.Empty;
            for (int i = 0; i < max_send_times; i++)
            {
                var client = new RestClient(apiUrl);
                var request = new RestRequest
                {
                    Method = method,
                    Timeout = TimeSpan.FromMilliseconds(timeOut),
                    RequestFormat = DataFormat.Json
                };
                if (data != null)
                    request.AddJsonBody(data);

                if (headerValues != null)
                {
                    foreach (KeyValuePair<string, string> item in headerValues)
                    {
                        request.AddHeader(item.Key, item.Value);
                    }
                }
                if (requiredParams != null)
                {
                    foreach (KeyValuePair<string, string> kvp in requiredParams)
                    {
                        request.AddQueryParameter(kvp.Key, kvp.Value);
                    }
                }
                string a = Newtonsoft.Json.JsonConvert.SerializeObject(data);
                var response = await client.ExecuteAsync(request);
                if (response.StatusCode == HttpStatusCode.Unauthorized)
                {
                    return Tuple.Create<string, string>(string.Empty, errorMessage);

                    //    LogHelper.Log(LogHelper.EmLogType.ERROR, LogHelper.EmObjectLogType.System, "MẤT ĐĂNG NHẬP HỆ THỐNG");
                    //GetToken:
                    //    {
                    //        string loginUrl = KzParkingv5BaseApi.server.Replace("5000", "3000");
                    //        if (loginUrl[loginUrl.Length - 1] == '/')
                    //        {
                    //            loginUrl += "connect/token";
                    //        }
                    //        else
                    //        {
                    //            loginUrl += "/connect/token";
                    //        }
                    //        var _client = new RestClient(loginUrl);
                    //        var _request = new RestRequest
                    //        {
                    //            Method = Method.Post,
                    //            Timeout = timeOut,
                    //        };
                    //        _request.AddHeader("content-type", "application/x-www-form-urlencoded");
                    //        _request.AddParameter("application/x-www-form-urlencoded", $"grant_type=refresh_token&refresh_token={KzParkingv5BaseApi.refresh_token}&client_id={KzParkingv5BaseApi.client_id}", ParameterType.RequestBody);

                    //        try
                    //        {
                    //            var _response = _client.Execute(_request);
                    //            var LoginResult = Newtonsoft.Json.JsonConvert.DeserializeObject<LoginResult>(_response.Content);
                    //            if (string.IsNullOrEmpty(LoginResult.access_token))
                    //            {
                    //                goto GetToken;
                    //            }
                    //            else
                    //            {
                    //                KzParkingv5BaseApi.token = LoginResult.access_token;
                    //                KzParkingv5BaseApi.refresh_token = LoginResult.refresh_token;
                    //                if (KzParkingv5BaseApi.refresh_token != LoginResult.refresh_token)
                    //                {

                    //                }
                    //                if (headerValues.ContainsKey("Authorization"))
                    //                {
                    //                    headerValues["Authorization"] = "Bearer " + KzParkingv5BaseApi.token;
                    //                }
                    //                return await GeneralJsonAPIAsync(apiUrl, data, headerValues, requiredParams, timeOut, method);
                    //            }
                    //        }
                    //        catch (Exception)
                    //        {
                    //            goto GetToken;
                    //        }

                    //    }
                }
                if (!response.IsSuccessful)
                {
                    var logResponse = response;
                    logResponse.Request = null;
                    LogHelper.Log(logType: LogHelper.EmLogType.ERROR,
                    doi_tuong_tac_dong: LogHelper.EmObjectLogType.Api,
                    hanh_dong: method.ToString(),
                    noi_dung_hanh_dong: $"Gửi {apiUrl} lần {i + 1}",
                    mo_ta_them: TextFormatingTool.BeautyJson(dataSend),
                                  obj: logResponse);
                    if (string.IsNullOrEmpty(response.Content))
                    {
                        continue;
                    }
                    else
                    {
                        return Tuple.Create<string, string>(response.Content, string.Empty);
                    }
                }

                LogHelper.Log(logType: LogHelper.EmLogType.INFOR,
                              doi_tuong_tac_dong: LogHelper.EmObjectLogType.Api,
                              hanh_dong: method.ToString(),
                              noi_dung_hanh_dong: apiUrl,
                              mo_ta_them: TextFormatingTool.BeautyJson(dataSend),
                              obj: response.Content);
                return Tuple.Create<string, string>(response.Content, string.Empty);
            }
            return Tuple.Create<string, string>(string.Empty, errorMessage);
        }
        #endregion END JSON API HELPER

        private static bool IsValidHost(string apiUrl)
        {
            Uri uri = new Uri(apiUrl);
            return true;
            if (!NetWorkTools.IsPingSuccess(uri.Host, 100))
            {
                LogHelper.Log(logType: LogHelper.EmLogType.ERROR,
                              doi_tuong_tac_dong: LogHelper.EmObjectLogType.Api,
                              hanh_dong: "PING",
                              noi_dung_hanh_dong: "Kiểm tra ping đến host " + uri.Host,
                              mo_ta_them: "PING ERROR",
                              obj: uri);
                return false;
            }
            return true;
        }
    }
}