using iParkingv5.ApiManager.KzParkingv5Apis;
using iParkingv5.Objects.Datas.payments;
using iParkingv5.Objects.Invoices;
using iParkingv5.Objects.ScaleObjects;
using iParkingv6.ApiManager;
using Kztek.Tool;
using Newtonsoft.Json;
using RestSharp;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using static iParkingv5.ApiManager.KzParkingv5Apis.Filter;

namespace iParkingv5.ApiManager.KzScaleApis
{
    public class CountInDayDetail
    {
        public int numberFirstWeighing { get; set; } = 0;
        public int numberSecondWeighing { get; set; } = 0;
        public int numberOtherWeighing { get; set; } = 0;
    }
    public class KzScaleBaseResponse<T>
    {
        public int status { get; set; }
        public int run { get; set; }
        public string error { get; set; }
        public T result { get; set; }
    }

    public static class KzScaleApiHelper
    {
        public static string server = "";
        public static string username = "admin";
        public static string password = "123456";
        public static int timeOut = 30000;

        public static int expireTime = 1000;
        public static string token = string.Empty;
        public static CancellationTokenSource cts;

        #region WeighingForms
        public static async Task<List<WeighingType>> GetWeighingForms()
        {
            StandardlizeServerName();
            string apiUrl = server + KzScaleUrlManagement.GetAllWeighingFormRoute();

            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };

            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, new { }, headers, null, timeOut, RestSharp.Method.Post);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                KzParkingv5BaseResponse<List<WeighingType>> data = Newtonsoft.Json.JsonConvert.DeserializeObject<KzParkingv5BaseResponse<List<WeighingType>>>(response.Item1);
                return data?.data ?? new List<WeighingType>();
            }
            return null;
        }
        #endregion End WeighingForms

        #region Weighing Action
        public static async Task<WeighingAction> CreateScaleEvent(string plateNumber, string parkingEventId,
                                                         long weight, string weightFormId,
                                                         string user_action, string user_code,
                                                         List<string> imageKeys, string updateTrafficId = "",
                                                         string laneId = "", DateTime? createdUtc = null)
        {
            string apiUrl = server + KzScaleUrlManagement.CreateWeighingAction();
            //weight = new Random().Next(10000, 50000);
            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };

            var obj = new
            {
                plate_number = plateNumber,
                eventInId = parkingEventId,
                weighingTypeId = weightFormId,
                weight = weight.ToString(),
                fileKeys = imageKeys,
                laneId = laneId,
                CreatedUtc = createdUtc,
            };
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, obj, headers, null, timeOut, RestSharp.Method.Post);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                try
                {
                    var data = Newtonsoft.Json.JsonConvert.DeserializeObject<WeighingAction>(response.Item1);
                    return data;
                }
                catch (Exception)
                {
                    return null;
                }
            }
            return null;
        }

        public static async Task<bool> UpdatePlate(string eventInId, string newPlate)
        {
            string apiUrl = server + KzScaleUrlManagement.UpdatePlate(eventInId);

            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };

            var data = new List<object>
            {
                new
                {
                    op = "replace",
                    path = "plateNumber",
                    value = newPlate
                }
            };
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, data, headers, null, timeOut, RestSharp.Method.Patch);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                return true;
                //try
                //{
                //    KzScaleBaseResponse<WeighingAction> response = Newtonsoft.Json.JsonConvert.DeserializeObject<KzScaleBaseResponse<WeighingAction>>(response.Item1);
                //    return data?.result ?? new WeighingAction();
                //}
                //catch (Exception)
                //{
                //    return null;
                //}
            }
            return false;
        }

        public static async Task<List<WeighingAction>> GetWeighingActionDetails(DateTime startTime, DateTime endTime, string plateNumber = "",
                                        string user_code = "", string weighingFormId = "", int is_weighing_bill = 0, string id = "", string eventInId = "")
        {
            if (string.IsNullOrEmpty(server))
            {
                return new List<WeighingAction>();
            }
            StandardlizeServerName();
            string apiUrl = server + KzScaleUrlManagement.GetAllWeighingHistory();

            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };


            List<FilterModel> filterModels = new List<FilterModel>()
            {
                new FilterModel("createdUtc", EmPageSearchType.DATETIME, startTime.ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss:0000"), EmOperation._gte),
                new FilterModel("createdUtc", EmPageSearchType.DATETIME, endTime.ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss:0000"),  EmOperation._lte),
                new FilterModel("createdBy", EmPageSearchType.TEXT, user_code,  EmOperation._contains),
            };
            if (!string.IsNullOrEmpty(weighingFormId))
            {
                filterModels.Add(new FilterModel("weighingType.id", EmPageSearchType.GUID, weighingFormId, EmOperation._in));
            }
            if (!string.IsNullOrEmpty(id))
            {
                filterModels.Add(new FilterModel("id", EmPageSearchType.GUID, id, EmOperation._in));
            }
            if (!string.IsNullOrEmpty(eventInId))
            {
                filterModels.Add(new FilterModel("eventInId", EmPageSearchType.GUID, eventInId, EmOperation._in));
            }
            var filter1 = Filter.CreateFilterItem(filterModels, EmMainOperation.and);
            var filter2 = Filter.CreateFilterItem(new List<FilterModel>()
                            {
                                new FilterModel("plateNumber", "TEXT", plateNumber, "contains"),
                            }, EmMainOperation.or);
            var filter = Filter.CreateFilter(new List<Dictionary<string, List<FilterModel>>>() { filter1, filter2 },
            pageIndex: 1,
            pageSize: 10000);
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, filter, headers, null, timeOut, RestSharp.Method.Post);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                return NewtonSoftHelper<KzParkingv5BaseResponse<List<WeighingAction>>>.GetBaseResponse(response.Item1)?.data ?? new List<WeighingAction>();
            }
            return new List<WeighingAction>();
        }
        public static async Task<List<WeighingAction>> GetWeighingActionInvoiceDetails(DateTime startTime, DateTime endTime, int? isFee = null, string laneId = "",
                                        string plateNumber = "",
                                        string user_code = "", string weighingFormId = "",
                                        int is_weighing_bill = 0, string id = "", string eventInId = "")
        {
            if (string.IsNullOrEmpty(server))
            {
                return new List<WeighingAction>();
            }
            StandardlizeServerName();
            string apiUrl = server + KzScaleUrlManagement.GetReportingWeighingHistory();

            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };

            var data = new
            {
                paging = false,
                pageIndex = 0,
                pageSize = 1,
                filter = new
                {
                    fromUtc = startTime.ToUniversalTime().ToString("MM/dd/yyyy HH:mm:ss"),
                    toUtc = endTime.ToUniversalTime().ToString("MM/dd/yyyy HH:mm:ss"),
                    upns = new List<string>(),
                    keyword = plateNumber,
                    weighingTypeIds = new List<string>(),
                    laneIds = new List<string>(),
                    isFee = isFee,
                }
            };
            if (!string.IsNullOrEmpty(user_code))
            {
                data.filter.upns.Add(user_code);
            }
            if (!string.IsNullOrEmpty(laneId))
            {
                data.filter.laneIds.Add(laneId);
            }
            if (!string.IsNullOrEmpty(weighingFormId))
            {
                data.filter.weighingTypeIds.Add(weighingFormId);
            }
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, data, headers, null, timeOut, RestSharp.Method.Post);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                return NewtonSoftHelper<KzParkingv5BaseResponse<List<WeighingAction>>>.GetBaseResponse(response.Item1)?.data ?? new List<WeighingAction>();
            }
            return new List<WeighingAction>();
        }

        public static async Task<WeighingAction> UpdateWeighingActionDetailById(string weighingActionDetailId, string weighingTypeId)
        {
            if (string.IsNullOrEmpty(server))
            {
                return null;
            }
            StandardlizeServerName();
            string apiUrl = server + KzScaleUrlManagement.updateWeighingActionDetailById(weighingActionDetailId);

            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            //Dictionary<string, string> parameters = new Dictionary<string, string>()
            //{
            //    { "weighting_form_id", weighingFormId },
            //    { "weighing_action_detail_id", weighingActionDetailId },
            //};
            var data = new List<object>
            {
                new
                {
                    op = "replace",
                    path = "weighingType",
                    value = weighingTypeId
                }
            };
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, data, headers, null, timeOut, RestSharp.Method.Patch);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                var searchData = await GetWeighingActionDetails(DateTime.MinValue, DateTime.MaxValue, id: weighingActionDetailId);
                if (searchData.Count == 0)
                {
                    return null;
                }
                return searchData[0];
            }
            return null;
        }
        #endregion End Weighing Action

        #region Weighing Detail
        public static async Task<CountInDayDetail> GetCountInDayRoute()
        {
            if (string.IsNullOrEmpty(server))
            {
                return new CountInDayDetail();
            }
            StandardlizeServerName();
            string apiUrl = server + KzScaleUrlManagement.GetCountInDayRoute();

            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            DateTime queryTime = DateTime.Now;
            Dictionary<string, string> parameters = new Dictionary<string, string>()
            {
                { "fromDateTime",new DateTime(queryTime.Year, queryTime.Month, queryTime.Day, 0,0,0).ToUniversalTime().ToString("MM/dd/yyyy HH:mm:ss") },
                { "toDateTime",new DateTime(queryTime.Year, queryTime.Month, queryTime.Day, 23,59,59).ToUniversalTime().ToString("MM/dd/yyyy HH:mm:ss") }
            };

            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, null, headers, parameters, timeOut, RestSharp.Method.Get);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                CountInDayDetail data =
                  Newtonsoft.Json.JsonConvert.DeserializeObject<CountInDayDetail>(response.Item1);
                if (data == null)
                {
                    return new CountInDayDetail();
                }
                return data;
            }
            return new CountInDayDetail();
        }
        public static async Task<List<WeighingAction>> GetWeighingActionDetailsByTrafficId(string parkingEventId)
        {
            StandardlizeServerName();
            string apiUrl = server + KzScaleUrlManagement.GetAllWeighingHistory();

            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            Dictionary<string, string> parameters = new Dictionary<string, string>()
            {
                { "traffic_id",parkingEventId  }
            };

            var searchData = await GetWeighingActionDetails(DateTime.MinValue, DateTime.MaxValue, eventInId: parkingEventId) ?? new List<WeighingAction>();
            return searchData.OrderBy(e => e.createdUtcTime).ToList();
        }
        #endregion End Weighing Detai;

        #region EInvoice
        public static async Task<InvoiceResponse> CreateInvoice(string weighingActionDetailId, bool isSentNow, string customerId)
        {
            StandardlizeServerName();
            string apiUrl = server + "invoice";

            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            var data = new
            {
                targetId = weighingActionDetailId,
                send = isSentNow ? 1 : 0,
                //send =0,
                provider = (int)EmInvoiceProvider.Viettel,
                TargetType = TargetType.Weghing,
                customerId =customerId,
            };

            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, data, headers, null, timeOut, Method.Post);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                try
                {
                    return JsonConvert.DeserializeObject<InvoiceResponse>(response.Item1);
                }
                catch (Exception)
                {
                    return null;

                }
            }
            return null;
        }
        public static async Task<InvoiceResponse> sendPendingEInvoice(string invoiceID)
        {
            StandardlizeServerName();
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            string apiUrl = server + KzParkingv5ApiUrlManagement.PostObjectRoute(KzParkingv5ApiUrlManagement.EmParkingv5ObjectType.Invoice) + "/" + invoiceID + "/resend";
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, null, headers, null, timeOut, Method.Post);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                try
                {
                    return JsonConvert.DeserializeObject<InvoiceResponse>(response.Item1);
                }
                catch (Exception)
                {
                    return null;

                }
            }
            return null;
        }

        #endregion End EInvoice

        #region Privaet Function
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
