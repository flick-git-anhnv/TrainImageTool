using iParkingv6.ApiManager;
using Kztek.Tool;
using Newtonsoft.Json.Linq;
using RestSharp;
using System;
using System.Collections.Generic;
using System.Text;
using static iParkingv5.ApiManager.KzParkingv5Apis.Filter;
using System.Threading.Tasks;
using System.Threading;
using iParkingv6.ApiManager.KzParkingv3Apis;

namespace iParkingv5.ApiManager.KzParkingv5Apis
{
    public static class KzParkingv5BaseApi
    {
        #region Properties
        public static string server = "http://14.160.26.45:5000";
        public static string loginUrl = "http://14.160.26.45:5000";
        public static string username = "admin";
        public static string password = "123456";
        public static int timeOut = 10000;
        public static string refresh_token = "";
        public static string client_id = "";
        public static int expireTime = 1000;
        public static string token = string.Empty;
        public static CancellationTokenSource cts;
        #endregion End Properties

        #region Base
        #region GET
        /// <summary>
        /// Lấy tất cả dữ liệu lưu trong database 
        /// </summary>
        /// <typeparam name="T"></typeparam>
        /// <param name="objectType"></param>
        /// <returns></returns>
        public static async Task<Tuple<List<T>, string>> GetAllObjectAsync<T>(
            KzParkingv5ApiUrlManagement.EmParkingv5ObjectType objectType) where T : class
        {
            StandardlizeServerName();
            string apiUrl = server + KzParkingv5ApiUrlManagement.SearchObjectDataRoute(objectType);

            var filter = Filter.CreateFilter(new FilterModel(), mainOperation: EmMainOperation.and, _pageIndex: 0, _pageSize: 500);
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, filter, headers, null,
                                                                   timeOut, RestSharp.Method.Post);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                KzParkingv5BaseResponse<List<T>> kzBaseResponse =
                    NewtonSoftHelper<KzParkingv5BaseResponse<List<T>>>.GetBaseResponse(response.Item1);
                if (kzBaseResponse == null)
                {
                    return Tuple.Create<List<T>, string>(null, "Error Convert Json Data" + response.Item1);
                }
                if (kzBaseResponse.data == null)
                {
                    return Tuple.Create<List<T>, string>(null, kzBaseResponse.detailCode);
                }
                return Tuple.Create<List<T>, string>(kzBaseResponse.data, kzBaseResponse.detailCode);
            }
            return Tuple.Create<List<T>, string>(null, "Empty Data");
        }

        /// <summary>
        /// Lấy bản ghi có điều kiện = điều kiện tìm kiếm
        /// </summary>
        /// <typeparam name="T"></typeparam>
        /// <param name="objectType"></param>
        /// <param name="emPageSearchType"></param>
        /// <param name="emPageSearchKey"></param>
        /// <param name="searchValue"></param>
        /// <returns></returns>
        public static async Task<Tuple<T, string>> GetTop1ObjectAsync<T>(
            KzParkingv5ApiUrlManagement.EmParkingv5ObjectType objectType,
            EmPageSearchType emPageSearchType, EmPageSearchKey emPageSearchKey, string searchValue) where T : class
        {
            StandardlizeServerName();
            string apiUrl = server + KzParkingv5ApiUrlManagement.SearchObjectDataRoute(objectType);

            var filter = Filter.CreateFilter(new FilterModel(emPageSearchKey, emPageSearchType, searchValue, EmOperation._eq));
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, filter, headers, null,
                                                                   timeOut, RestSharp.Method.Post);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                KzParkingv5BaseResponse<List<T>> kzBaseResponse =
                    NewtonSoftHelper<KzParkingv5BaseResponse<List<T>>>.GetBaseResponse(response.Item1);
                if (kzBaseResponse == null)
                {
                    return Tuple.Create<T, string>(null, "Error Convert Json Data" + response.Item1);
                }
                if (kzBaseResponse.data == null)
                {
                    return Tuple.Create<T, string>(null, kzBaseResponse.detailCode);
                }
                return Tuple.Create<T, string>(kzBaseResponse.data.Count > 0 ? kzBaseResponse.data[0] : null, kzBaseResponse.detailCode);
            }
            return Tuple.Create<T, string>(null, "Empty Data");
        }

        /// <summary>
        /// Lấy bản ghi có điều kiện = điều kiện tìm kiếm
        /// </summary>
        /// <typeparam name="T"></typeparam>
        /// <param name="objectType"></param>
        /// <param name="emPageSearchType"></param>
        /// <param name="emPageSearchKey"></param>
        /// <param name="searchValue"></param>
        /// <returns></returns>
        public static async Task<Tuple<List<T>, string>> GetObjectByConditionAsync<T>(
            KzParkingv5ApiUrlManagement.EmParkingv5ObjectType objectType,
            EmPageSearchType emPageSearchType, EmPageSearchKey emPageSearchKey, string searchValue, EmOperation operation) where T : class
        {
            StandardlizeServerName();
            string apiUrl = server + KzParkingv5ApiUrlManagement.SearchObjectDataRoute(objectType);

            var filter = Filter.CreateFilter(new FilterModel(emPageSearchKey, emPageSearchType, searchValue, operation));
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, filter, headers, null,
                                                                   timeOut, Method.Post);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                KzParkingv5BaseResponse<List<T>> kzBaseResponse =
                    NewtonSoftHelper<KzParkingv5BaseResponse<List<T>>>.GetBaseResponse(response.Item1);
                if (kzBaseResponse == null)
                {
                    return Tuple.Create<List<T>, string>(null, "Error Convert Json Data" + response.Item1);
                }
                if (kzBaseResponse.data == null)
                {
                    return Tuple.Create<List<T>, string>(null, kzBaseResponse.detailCode);
                }
                return Tuple.Create<List<T>, string>(kzBaseResponse.data, kzBaseResponse.detailCode);
            }
            return Tuple.Create<List<T>, string>(null, "Empty Data");
        }

        /// <summary>
        /// Lấy bản ghi có điều kiện = điều kiện tìm kiếm
        /// </summary>
        /// <typeparam name="T"></typeparam>
        /// <param name="id"></param>
        /// <returns></returns>
        public static async Task<Tuple<T, string>> GetObjectDetailByIdAsync<T>(
            KzParkingv5ApiUrlManagement.EmParkingv5ObjectType objectType, string id) where T : class
        {
            StandardlizeServerName();
            string apiUrl = server + KzParkingv5ApiUrlManagement.GetObjectDataDetailRoute(objectType, id);

            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, null, headers, null,
                                                                   timeOut, Method.Get);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                try
                {
                    var data = Newtonsoft.Json.JsonConvert.DeserializeObject<T>(response.Item1);
                    return Tuple.Create<T, string>(data, response.Item2);
                }
                catch (Exception e)
                {
                    return null;
                }
            }
            return Tuple.Create<T, string>(null, "Empty Data");
        }

        public static async Task<bool> DeleteObjectDetailByIdAsync<T>(
    KzParkingv5ApiUrlManagement.EmParkingv5ObjectType objectType, string id) where T : class
        {
            StandardlizeServerName();
            string apiUrl = server + KzParkingv5ApiUrlManagement.GetObjectDataDetailRoute(objectType, id);

            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, null, headers, null, timeOut, Method.Delete);
            if (string.IsNullOrEmpty(response?.Item1))
            {
                return false;
            }
            try
            {
                var data = Newtonsoft.Json.JsonConvert.DeserializeObject<KzBaseResponse>(response.Item1);
                return data?.isSuccess ?? false;
            }
            catch (Exception)
            {
                return false;
            }
        }
        #endregion END GET

        #region ADD
        public static async Task<Tuple<T, string>> CreateObjectAsync<T>(
                                    KzParkingv5ApiUrlManagement.EmParkingv5ObjectType objectType,
                                    T obj) where T : class
        {
            StandardlizeServerName();
            string apiUrl = server + KzParkingv5ApiUrlManagement.PostObjectRoute(objectType);

            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, obj, headers, null,
                                                                  timeOut, Method.Post);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                var data = Newtonsoft.Json.JsonConvert.DeserializeObject<T>(response.Item1);
                return Tuple.Create<T, string>(data, response.Item2);
            }
            return Tuple.Create<T, string>(null, "Empty Data");
        }

        #endregion End ADD

        #endregion End Base


        #region Private Function
        private static void StandardlizeServerName()
        {
            if (server[^1] != '/' && server[^1] != '\\')
            {
                server += "/";
            }
        }
        #endregion End Private Function
    }
}
