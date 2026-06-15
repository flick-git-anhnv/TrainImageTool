using iParkingv6.ApiManager;
using Kztek.Tool;
using System;
using System.Collections.Generic;
using System.Threading.Tasks;

namespace iParkingv5.ApiManager.XuanCuong
{
    public class XuanCuongApiHelper
    {
        public static string url = "https://main.xuancuong.vn/api/kztek/notify";
        public static string name = "Chima";
        //public static string url = "https://xc-main-dev.maychudev.com/api/kztek/notify";
        public static string apiKey = "5GKSWHDYSH1SKB";
        private static int timeOut = 10000;
        public class XuanCuongApiResponse
        {
            public bool isSuccess { get; set; }
            public string Message { get; set; }
        }
        public static async Task<bool> SendParkingInfo(string eventid, string direction, string plate, DateTime time, List<string> imagePaths, string eventInId)
        {
            if (string.IsNullOrEmpty(url))
            {
                return false;
            }
            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "x-api-key", apiKey  }
            };
            Dictionary<string, string> parameters = new Dictionary<string, string>()
            {
                {"idEvent", eventid  },
                {"direction", direction },
                {"plate", plate },
                {"time", time.ToString("yyyy-MM-dd HH:mm:ss") },
                {"image", string.Join(";",imagePaths) },
                //{"location", XuanCuongApiHelper.name },
            };
            if (!string.IsNullOrEmpty(eventInId))
            {
                parameters.Add("idInEvent", eventInId);
            }

            var response = await BaseApiHelper.GeneralJsonAPIAsync(url, null, headers, parameters, timeOut, RestSharp.Method.Post);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                XuanCuongApiResponse response1 = NewtonSoftHelper<XuanCuongApiResponse>.GetBaseResponse(response.Item1);
                return response1?.isSuccess ?? false;
            }
            return false;
        }
        public static async Task<bool> CreatePaymentCore(string plateNumber, long amount)
        {
            if (string.IsNullOrEmpty(url))
            {
                return false;
            }
            //https://xc-main-dev.sonthanh.net.vn/api/kztek/pay-additional-fees
            string paymentUrl = url.Replace("notify", "pay-additional-fees");
            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "x-api-key", apiKey  }
            };
            Dictionary<string, string> parameters = new Dictionary<string, string>() { };

            var body = new
            {
                plate_number = plateNumber,
                amount = amount
            };

            var response = await BaseApiHelper.GeneralJsonAPIAsync(paymentUrl, body, headers, parameters, timeOut, RestSharp.Method.Post);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                XuanCuongApiResponse response1 = NewtonSoftHelper<XuanCuongApiResponse>.GetBaseResponse(response.Item1);
                return response1?.isSuccess ?? false;
            }
            return false;
        }
    }
}
