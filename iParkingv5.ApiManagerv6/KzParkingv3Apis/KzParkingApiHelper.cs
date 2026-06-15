using iParkingv5.Objects.Datas;
using iParkingv5.Objects.EventDatas;
using iParkingv6.ApiManager.KzParkingv3Apis.Responses;
using Kztek.Tools;
using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using Kztek.Tool;
using iParkingv5.Objects.Enums;
using Newtonsoft.Json;
using iParkingv5.Objects;
using RestSharp;
using iParkingv5.Objects.Invoices;
using iParkingv5.ApiManager;
using System.Data;
using iParkingv5.Objects.warehouse;
using static iParkingv5.Objects.warehouse.TransactionType;
using iParkingv5.Objects.Reporting;
using iParkingv5.Objects.Datas.Devices;
using iParkingv5.Objects.Datas.parking;
using iParkingv5.Objects.Datas.system;

namespace iParkingv6.ApiManager.KzParkingv3Apis
{
    public class KzParkingApiHelper
    {
        public class BaseReport<T> where T : class
        {
            public Paging paging { get; set; }
            public MetaData metaData { get; set; }
            public List<T> data { get; set; }
        }
        public static string server = "http://14.160.26.45:13000";
        public static string username = "admin";
        public static string password = "123456";
        public static int timeOut = 10000;

        public static int expireTime = 1000;
        public static string token = string.Empty;
        public static CancellationTokenSource cts;

        public class EventIdentity
        {
            public string code { get; set; }
            public IdentityType type { get; set; }
        }
        #region PUBLIC FUNCTION

        #region -- USER
        public async Task<Tuple<string, string>> GetToken(string _username, string _password)
        {
            StandardlizeServerName();
            string apiUrl = server + KzApiUrlManagement.PostLoginRoute;
            username = _username;
            password = _password;
            //Gửi API
            var login = new
            {
                username = _username,
                password = _password
            };

            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, login, null, null, timeOut, RestSharp.Method.Post);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                try
                {
                    KzBaseResponseData<LoginResponse> kzBaseResponse = NewtonSoftHelper<KzBaseResponseData<LoginResponse>>.GetBaseResponse(response.Item1);
                    if (kzBaseResponse == null)
                        return Tuple.Create<string, string>(string.Empty, "Data không hợp lệ");
                    if (kzBaseResponse.data != null)
                    {
                        token = kzBaseResponse.data.accessToken;
                        expireTime = kzBaseResponse.data.expireInSeconds;
                        StaticPool.userId = _username;
                        StaticPool.user_name = _username;
                    }
                    return Tuple.Create<string, string>(token, kzBaseResponse.metadata?.message?.value ?? "");
                }
                catch (Exception ex)
                {
                    LogHelper.Log(logType: LogHelper.EmLogType.ERROR,
                              doi_tuong_tac_dong: LogHelper.EmObjectLogType.Api,
                              obj: ex);
                }
            }
            return Tuple.Create<string, string>(response.Item1, string.Empty);

        }
        public void StartPollingAuthorize()
        {
            cts = new CancellationTokenSource();
            _ = Task.Run(() => PollingAuthorize(cts.Token), cts.Token);
        }
        public void StopPollingAuthorize()
        {
            cts?.Cancel();
        }
        private async Task PollingAuthorize(CancellationToken ctsToken)
        {
            return;
            while (!ctsToken.IsCancellationRequested)
            {
                int delayTime = expireTime;
                try
                {
                    string _token = (await GetToken(username, password)).Item1;
                    if (string.IsNullOrEmpty(_token))
                    {
                        delayTime = 1000;
                    }
                    else
                    {
                        token = _token;
                        delayTime = 15 * 60 * 1000;
                    }
                }
                catch (Exception ex)
                {
                    LogHelper.Log(logType: LogHelper.EmLogType.ERROR, doi_tuong_tac_dong: LogHelper.EmObjectLogType.Api, obj: ex);
                }
                finally
                {
                    await Task.Delay(TimeSpan.FromMilliseconds(delayTime), ctsToken);
                    GC.Collect();
                }
            }
        }
        public async Task GetUserInfor()
        {
            StandardlizeServerName();
            string apiUrl = server + "user/info";

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
                    User user = Newtonsoft.Json.JsonConvert.DeserializeObject<User>(response.Item1);
                    StaticPool.userId = user.id;
                    StaticPool.user_name = user.upn;
                }
                catch (Exception)
                {

                }
            }
        }
        public async Task<Tuple<List<User>, string>> GetAllUsers()
        {
            return Tuple.Create<List<User>, string>(new List<User>(), "");
        }
        #endregion END -- USER

        #region -- CAMERA
        public async Task<Tuple<List<Camera>, string>> GetCamerasAsync()
        {
            return null;
        }

        public async Task<Tuple<List<Camera>, string>> GetCameraByComputerIdAsync(string computerId)
        {
            StandardlizeServerName();
            string apiUrl = server + KzApiUrlManagement.EmObjectType.Camera.GetDataByParamsRoute();

            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            Dictionary<string, string> parameters = new Dictionary<string, string>()
            {
                { "computerId", computerId }
            };

            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, null, headers, parameters, timeOut, RestSharp.Method.Get);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                KzBaseResponseData<List<Camera>> kzBaseResponse = NewtonSoftHelper<KzBaseResponseData<List<Camera>>>.GetBaseResponse(response.Item1);
                return Tuple.Create<List<Camera>, string>(kzBaseResponse?.data, "");
            }
            return null;
        }
        #endregion

        #region -- LANE
        public async Task<Tuple<List<Lane>, string>> GetLaneByComputerIdAsync(string pcId)
        {
            StandardlizeServerName();
            string apiUrl = server + KzApiUrlManagement.EmObjectType.Lane.GetDataByParamsRoute();

            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            Dictionary<string, string> parameters = new Dictionary<string, string>()
            {
                { "computerId",pcId}
            };
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, null, headers, parameters, timeOut, RestSharp.Method.Get);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                KzBaseResponseData<List<Lane>> kzBaseResponse = NewtonSoftHelper<KzBaseResponseData<List<Lane>>>.GetBaseResponse(response.Item1);
                return Tuple.Create<List<Lane>, string>(kzBaseResponse?.data, "");
            }
            return null;
        }
        public async Task<Tuple<List<Lane>, string>> GetLanesAsync()
        {
            StandardlizeServerName();
            string apiUrl = server + KzApiUrlManagement.EmObjectType.Lane.GetDataByParamsRoute();

            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, null, headers, null, timeOut, RestSharp.Method.Get);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                KzBaseResponseData<List<Lane>> kzBaseResponse = NewtonSoftHelper<KzBaseResponseData<List<Lane>>>.GetBaseResponse(response.Item1);
                return Tuple.Create<List<Lane>, string>(kzBaseResponse?.data, "");
            }
            return null;
        }
        public async Task<Tuple<Lane, string>> GetLaneByIdAsync(string laneId)
        {
            StandardlizeServerName();
            string apiUrl = server + KzApiUrlManagement.EmObjectType.Lane.GetDataByIdRoute(laneId);

            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, null, headers, null, timeOut, RestSharp.Method.Get);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                KzBaseResponseData<Lane> kzBaseResponse = NewtonSoftHelper<KzBaseResponseData<Lane>>.GetBaseResponse(response.Item1);
                return Tuple.Create<Lane, string>(kzBaseResponse?.data, "");
            }
            return null;
        }
        #endregion

        #region -- PARKING LED
        public async Task<Tuple<List<Led>, string>> GetLedsAsync()
        {
            return null;
        }
        public async Task<Tuple<List<Led>, string>> GetLedByComputerIdAsync(string pcId)
        {
            StandardlizeServerName();
            string apiUrl = server + KzApiUrlManagement.EmObjectType.Led.GetDataByParamsRoute();

            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            Dictionary<string, string> parameters = new Dictionary<string, string>()
            {
                { "computerId",pcId  }
            };
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, null, headers, parameters, timeOut, RestSharp.Method.Get);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                KzBaseResponseData<List<Led>> kzBaseResponse = NewtonSoftHelper<KzBaseResponseData<List<Led>>>.GetBaseResponse(response.Item1);
                return Tuple.Create<List<Led>, string>(kzBaseResponse?.data, "");
            }
            return null;
        }
        public async Task<Led> GetLedByIdAsync(string ledId)
        {
            StandardlizeServerName();
            string apiUrl = server + KzApiUrlManagement.EmObjectType.Led.GetDataByIdRoute(ledId);

            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, null, headers, null, timeOut, RestSharp.Method.Get);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                KzBaseResponseData<Led> kzBaseResponse = NewtonSoftHelper<KzBaseResponseData<Led>>.GetBaseResponse(response.Item1);
                return kzBaseResponse?.data;
            }
            return null;
        }
        #endregion

        #region -- CONTROL UNIT
        public async Task<Tuple<List<Bdk>, string>> GetControlUnitByComputerIdAsync(string pcId)
        {
            StandardlizeServerName();
            string apiUrl = server + KzApiUrlManagement.EmObjectType.ControlUnit.GetDataByParamsRoute();

            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            Dictionary<string, string> parameters = new Dictionary<string, string>()
            {
                { "computerId",pcId  }
            };
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, null, headers, parameters, timeOut, RestSharp.Method.Get);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                KzBaseResponseData<List<Bdk>> kzBaseResponse = NewtonSoftHelper<KzBaseResponseData<List<Bdk>>>.GetBaseResponse(response.Item1);
                if (kzBaseResponse == null)
                {
                    return null;
                }
                return Tuple.Create<List<Bdk>, string>(kzBaseResponse?.data, "");
            }
            return null;
        }
        public async Task<Tuple<List<Bdk>, string>> GetControlUnitsAsync()
        {
            StandardlizeServerName();
            string apiUrl = server + KzApiUrlManagement.EmObjectType.ControlUnit.GetDataByParamsRoute();

            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, null, headers, null, timeOut, RestSharp.Method.Get);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                KzBaseResponseData<List<Bdk>> kzBaseResponse = NewtonSoftHelper<KzBaseResponseData<List<Bdk>>>.GetBaseResponse(response.Item1);
                if (kzBaseResponse == null)
                {
                    return null;
                }
                return Tuple.Create<List<Bdk>, string>(kzBaseResponse?.data, "");
            }
            return null;
        }
        public async Task<Bdk> GetBdkByIdAsync(string controllerId)
        {
            StandardlizeServerName();
            string apiUrl = server + KzApiUrlManagement.EmObjectType.ControlUnit.GetDataByIdRoute(controllerId);

            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, null, headers, null, timeOut, RestSharp.Method.Get);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                KzBaseResponseData<Bdk> kzBaseResponse = NewtonSoftHelper<KzBaseResponseData<Bdk>>.GetBaseResponse(response.Item1);
                return kzBaseResponse?.data;
            }
            return null;
        }
        #endregion

        #region -- COMPUTER
        public async Task<Tuple<Computer, string>> GetComputerByIPAsync(string ipAddress)
        {
            StandardlizeServerName();
            string apiUrl = server + KzApiUrlManagement.EmObjectType.Computer.GetDataByParamsRoute();

            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            Dictionary<string, string> parameters = new Dictionary<string, string>()
            {
                { "keyword", ipAddress  }
            };

            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, null, headers, parameters, timeOut, RestSharp.Method.Get);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                KzBaseResponseData<List<Computer>> kzBaseResponse = NewtonSoftHelper<KzBaseResponseData<List<Computer>>>.GetBaseResponse(response.Item1);
                if (kzBaseResponse?.data != null)
                {
                    if (kzBaseResponse?.data.Count > 0)
                    {
                        return Tuple.Create<Computer, string>(kzBaseResponse?.data[0], "");
                    }
                }
                return null;
            }
            return null;
        }
        public async Task<Computer> GetComputerByIdAsync(string id)
        {
            StandardlizeServerName();
            string apiUrl = server + KzApiUrlManagement.EmObjectType.Computer.GetDataByParamsRoute();

            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            Dictionary<string, string> parameters = new Dictionary<string, string>()
            {
                { "keyword", id  }
            };

            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, null, headers, parameters, timeOut, RestSharp.Method.Get);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                KzBaseResponseData<Computer> kzBaseResponse = NewtonSoftHelper<KzBaseResponseData<Computer>>.GetBaseResponse(response.Item1);
                if (kzBaseResponse == null)
                {
                    return null;
                }
                return kzBaseResponse?.data;
            }
            return null;
        }
        public async Task<Tuple<List<Computer>, string>> GetComputersAsync()
        {
            StandardlizeServerName();
            string apiUrl = server + KzApiUrlManagement.EmObjectType.Computer.GetDataByParamsRoute();

            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, null, headers, null, timeOut, RestSharp.Method.Get);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                KzBaseResponseData<List<Computer>> kzBaseResponse = NewtonSoftHelper<KzBaseResponseData<List<Computer>>>.GetBaseResponse(response.Item1);
                return Tuple.Create<List<Computer>, string>(kzBaseResponse?.data, "");
            }
            return null;
        }
        #endregion

        #region -- GATE
        public async Task<Tuple<List<Gate>, string>> GetGatesAsync()
        {
            StandardlizeServerName();
            string apiUrl = server + KzApiUrlManagement.EmObjectType.Gate.GetDataByParamsRoute();

            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };

            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, null, headers, null, timeOut, RestSharp.Method.Get);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                KzBaseResponseData<List<Gate>> kzBaseResponse = NewtonSoftHelper<KzBaseResponseData<List<Gate>>>.GetBaseResponse(response.Item1);
                return Tuple.Create<List<Gate>, string>(kzBaseResponse?.data, "");
            }
            return null;
        }
        public async Task<Tuple<Gate, string>> GetGateByIdAsync(string gateId)
        {
            StandardlizeServerName();
            string apiUrl = server + KzApiUrlManagement.EmObjectType.Gate.GetDataByIdRoute(gateId);

            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };

            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, null, headers, null, timeOut, RestSharp.Method.Get);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                KzBaseResponseData<Gate> kzBaseResponse = NewtonSoftHelper<KzBaseResponseData<Gate>>.GetBaseResponse(response.Item1);
                return Tuple.Create<Gate, string>(kzBaseResponse?.data, "");
            }
            return null;
        }
        #endregion

        #region -- VEHICLE TYPE
        public async Task<Tuple<VehicleType, string>> GetVehicleTypeByIdAsync(string id)
        {
            StandardlizeServerName();
            string apiUrl = server + KzApiUrlManagement.EmObjectType.VehicleType.GetDataByIdRoute(id);

            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, null, headers, null, timeOut, RestSharp.Method.Get);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                KzBaseResponseData<VehicleType> kzBaseResponse = NewtonSoftHelper<KzBaseResponseData<VehicleType>>.GetBaseResponse(response.Item1);
                return Tuple.Create<VehicleType, string>(kzBaseResponse?.data, "");
            }
            return null;
        }
        public async Task<Tuple<List<VehicleType>, string>> GetVehicleTypesAsync()
        {
            StandardlizeServerName();
            string apiUrl = server + KzApiUrlManagement.EmObjectType.VehicleType.GetDataByParamsRoute();

            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, null, headers, null, timeOut, RestSharp.Method.Get);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                KzBaseResponseData<List<VehicleType>> kzBaseResponse = NewtonSoftHelper<KzBaseResponseData<List<VehicleType>>>.GetBaseResponse(response.Item1);
                return Tuple.Create<List<VehicleType>, string>(kzBaseResponse?.data, "");
            }
            return null;
        }
        public async Task<Tuple<List<VehicleType>, string>> GetVehicleTypesAsync(string keyword)
        {
            StandardlizeServerName();
            string apiUrl = server + KzApiUrlManagement.EmObjectType.VehicleType.GetDataByParamsRoute();

            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            Dictionary<string, string> parameters = new Dictionary<string, string>()
            {
                { "keywprd", keyword }
            };
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, null, headers, parameters, timeOut, RestSharp.Method.Get);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                KzBaseResponseData<List<VehicleType>> kzBaseResponse = NewtonSoftHelper<KzBaseResponseData<List<VehicleType>>>.GetBaseResponse(response.Item1);
                return Tuple.Create<List<VehicleType>, string>(kzBaseResponse?.data, "");
            }
            return null;
        }
        #endregion

        #region -- IDENTITY
        public async Task<Tuple<Identity, string>> GetIdentityByIdAsync(string id)
        {
            StandardlizeServerName();
            string apiUrl = server + KzApiUrlManagement.EmObjectType.Identity.GetDataByIdRoute(id);

            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, null, headers, null, timeOut, RestSharp.Method.Get);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                KzBaseResponseData<Identity> kzBaseResponse = NewtonSoftHelper<KzBaseResponseData<Identity>>.GetBaseResponse(response.Item1);
                if (kzBaseResponse?.data != null)
                {
                    return Tuple.Create<Identity, string>(kzBaseResponse?.data, "");
                }
            }
            return null;
        }
        public async Task<Tuple<Identity, string>> GetIdentityByCodeAsync(string code)
        {
            StandardlizeServerName();
            string apiUrl = server + KzApiUrlManagement.GetIdentityByCodeRoute(code);

            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            Dictionary<string, string> parameters = new Dictionary<string, string>()
            {
                { "keyword", code  }
            };

            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, null, headers, null, timeOut, RestSharp.Method.Get);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                KzBaseResponseData<Identity> kzBaseResponse = NewtonSoftHelper<KzBaseResponseData<Identity>>.GetBaseResponse(response.Item1);
                if (kzBaseResponse == null)
                {
                    return Tuple.Create<Identity, string>(null, "");
                }
                if (kzBaseResponse.data == null)
                {
                    return Tuple.Create<Identity, string>(null, "");
                }
                return Tuple.Create<Identity, string>(kzBaseResponse.data, "");
            }
            return Tuple.Create<Identity, string>(null, "");
        }
        public async Task<Tuple<List<Identity>, string>> GetIdentitiesAsync(string keyword)
        {
            StandardlizeServerName();
            string apiUrl = server + KzApiUrlManagement.EmObjectType.Identity.GetDataByParamsRoute();

            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            Dictionary<string, string>? parameters = null;
            if (!string.IsNullOrEmpty(keyword))
            {
                parameters = new Dictionary<string, string>()
            {
                { "keyword",keyword }
            };
            }

            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, null, headers, parameters, timeOut, RestSharp.Method.Get);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                KzBaseResponseData<List<Identity>> kzBaseResponse = NewtonSoftHelper<KzBaseResponseData<List<Identity>>>.GetBaseResponse(response.Item1);
                return Tuple.Create<List<Identity>, string>(kzBaseResponse?.data, "");
            }
            return null;
        }
        public async Task<bool> UpdateIdentityById(Identity identity)
        {
            StandardlizeServerName();
            string apiUrl = server + KzApiUrlManagement.EmObjectType.Identity.UpdateRouteById(identity.Id);

            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, identity, headers, null, timeOut, RestSharp.Method.Put);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                KzBaseResponseData<Identity> kzBaseResponse = NewtonSoftHelper<KzBaseResponseData<Identity>>.GetBaseResponse(response.Item1);
                return kzBaseResponse?.data != null;
            }
            return false;
        }
        public async Task<Tuple<Identity, string>> CreateIdentityAsync(Identity identity)
        {
            StandardlizeServerName();
            string apiUrl = server + KzApiUrlManagement.EmObjectType.Identity.CreateRoute();

            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, identity, headers, null, timeOut, RestSharp.Method.Post);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                KzBaseResponseData<Identity> kzBaseResponse = NewtonSoftHelper<KzBaseResponseData<Identity>>.GetBaseResponse(response.Item1);
                return Tuple.Create<Identity, string>(kzBaseResponse?.data, "");
            }
            return null;
        }
        #endregion

        #region -- IDENTITY GROUP
        public async Task<Tuple<IdentityGroup, string>> GetIdentityGroupByIdAsync(string id)
        {
            StandardlizeServerName();
            string apiUrl = server + KzApiUrlManagement.EmObjectType.IdentityGroup.GetDataByIdRoute(id);

            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, null, headers, null, timeOut, RestSharp.Method.Get);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                KzBaseResponseData<IdentityGroup> kzBaseResponse = NewtonSoftHelper<KzBaseResponseData<IdentityGroup>>.GetBaseResponse(response.Item1);
                return Tuple.Create<IdentityGroup, string>(kzBaseResponse?.data, "");
            }
            return null;
        }
        public async Task<Tuple<List<IdentityGroup>, string>> GetIdentityGroupsAsync()
        {
            return await GetIdentityGroupsAsync();
        }
        public async Task<List<IdentityGroup>> GetIdentityGroupsAsync(string keyword = "", string vehicleTypeId = "")
        {
            StandardlizeServerName();
            string apiUrl = server + KzApiUrlManagement.EmObjectType.IdentityGroup.GetDataByParamsRoute();

            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            Dictionary<string, string> parameters = new Dictionary<string, string>();
            if (!string.IsNullOrEmpty(keyword))
            {
                parameters.Add("keyword", keyword);
            }
            if (!string.IsNullOrEmpty(vehicleTypeId))
            {
                parameters.Add("vehicleTypeId", vehicleTypeId);
            }
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, null, headers, parameters, timeOut, RestSharp.Method.Get);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                KzBaseResponseData<List<IdentityGroup>> kzBaseResponse = NewtonSoftHelper<KzBaseResponseData<List<IdentityGroup>>>.GetBaseResponse(response.Item1);
                return kzBaseResponse?.data;
            }
            return null;
        }
        #endregion

        #region SUMARY

        public async Task<SumaryCountEvent> SummaryEventAsync()
        {
            StandardlizeServerName();
            string apiUrl = server + "report/SummaryEvents";

            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            DateTime startTime = new DateTime(DateTime.Now.Year, DateTime.Now.Month, DateTime.Now.Day, 0, 0, 0).AddHours(-7);
            DateTime endTime = new DateTime(DateTime.Now.Year, DateTime.Now.Month, DateTime.Now.Day, 23, 59, 59).AddHours(-7);
            Dictionary<string, string> parameters = new Dictionary<string, string>();
            parameters.Add("fromUtc", startTime.ToString("yyyy-MM-ddTHH:mm:ss.000Z"));
            parameters.Add("toUtc", endTime.ToString("yyyy-MM-ddTHH:mm:ss.000Z"));
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, null, headers, parameters, timeOut, RestSharp.Method.Get);

            if (!string.IsNullOrEmpty(response.Item1))
            {
                KzBaseResponseData<SumaryCountEvent> kzBaseResponse = NewtonSoftHelper<KzBaseResponseData<SumaryCountEvent>>.GetBaseResponse(response.Item1);
                if (kzBaseResponse != null)
                {
                    if (kzBaseResponse.data != null)
                    {
                        return kzBaseResponse.data;
                    }
                }
            }

            return new SumaryCountEvent();
        }
        #endregion End SUMARY

        #region -- EVENT IN
        public async Task<bool> UpdateEventInPlateAsync(string eventId, string plate, string oldPlate)
        {
            StandardlizeServerName();
            string apiUrl = server + KzApiUrlManagement.EmObjectType.EventIn.UpdateRouteById(eventId);

            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };

            var data = new List<CommitData>()
            {
                new CommitData()
                {
                    value = plate,
                    op = "replace",
                    path = "/plateNumber"
                }
            };

            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, data, headers, null, timeOut, RestSharp.Method.Patch);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                KzBaseResponseData<string> kzBaseResponse = NewtonSoftHelper<KzBaseResponseData<string>>.GetBaseResponse(response.Item1);
                if (kzBaseResponse == null)
                {
                    return false;
                }
                return kzBaseResponse.metadata.success;
            }
            return false;
        }

        public async Task<AddEventInResponse> PostCheckInAsync(string _laneId, string _plateNumber, Identity? identity,
                                                               List<string> imageKeys, bool isForce = false, RegisteredVehicle? registeredVehicle = null, string _note = "")
        {
            StandardlizeServerName();
            string apiUrl = string.Empty;

            if (identity == null)
            {
                apiUrl = server + KzApiUrlManagement.EmObjectType.EventIn.CreateRoute() + "/vehicle";
                //Gửi API
                Dictionary<string, string> headers = new Dictionary<string, string>()
                {
                { "Authorization","Bearer " + token  }
                };
                var _vehicle = new
                {
                    id = registeredVehicle.Id,
                    plateNumber = _plateNumber,
                    customerId = registeredVehicle.CustomerId,
                };
                var data = new
                {
                    laneId = _laneId,
                    vehicle = _vehicle,
                    forceEntrance = isForce,
                    fileKeys = new List<string>()
                };

                foreach (var item in imageKeys)
                {
                    data.fileKeys.Add(item);
                }
                string a = Newtonsoft.Json.JsonConvert.SerializeObject(data);
                var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, data, headers, null, timeOut, RestSharp.Method.Post);
                if (!string.IsNullOrEmpty(response.Item1))
                {
                    try
                    {
                        KzBaseResponseData<AddEventInResponse> addEventInResponse = NewtonSoftHelper<KzBaseResponseData<AddEventInResponse>>.GetBaseResponse(response.Item1);
                        return addEventInResponse?.data;
                    }
                    catch (Exception)
                    {
                    }
                }
            }
            else
            {
                apiUrl = server + KzApiUrlManagement.EmObjectType.EventIn.CreateRoute() + "/vehicle";
                //Gửi API
                Dictionary<string, string> headers = new Dictionary<string, string>()
                {
                { "Authorization","Bearer " + token  }
                };

                var _identityCheckIn = new
                {
                    id = identity.Id,
                    code = identity.Code,
                    identityGroupId = identity.IdentityGroupId,
                };

                var data = new
                {
                    laneId = _laneId,
                    identity = _identityCheckIn,
                    plateNumber = _plateNumber,
                    //identityCode = identity == null ? null : identity?.Code,
                    //identityType = identity == null ? null : identity?.Type,
                    forceEntrance = isForce,
                    fileKeys = new List<string>()
                };

                foreach (var item in imageKeys)
                {
                    data.fileKeys.Add(item);
                }
                string a = Newtonsoft.Json.JsonConvert.SerializeObject(data);
                var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, data, headers, null, timeOut, RestSharp.Method.Post);
                if (!string.IsNullOrEmpty(response.Item1))
                {
                    try
                    {
                        KzBaseResponseData<AddEventInResponse> addEventInResponse = NewtonSoftHelper<KzBaseResponseData<AddEventInResponse>>.GetBaseResponse(response.Item1);
                        return addEventInResponse?.data;
                    }
                    catch (Exception)
                    {
                    }
                }
            }

            return null;
        }
        public async Task<DataTable> GetEventIns(string keyword, DateTime startTime, DateTime endTime,
                                                 string identityGroupId, string vehicleTypeId, string laneId, string user,
                                                 int pageIndex = 1, int pageSize = 100)
        {
            StandardlizeServerName();
            string apiUrl = server + KzApiUrlManagement.EmObjectType.EventIn.GetDataByParamsRoute();
            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            Dictionary<string, string> parameters = new Dictionary<string, string>();
            if (!string.IsNullOrEmpty(keyword))
            {
                parameters.Add("keyword", keyword);
            }
            parameters.Add("fromUtc", startTime.ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss.000Z"));
            parameters.Add("toUtc", endTime.ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss.000Z"));
            parameters.Add("pageIndex", pageIndex.ToString());
            parameters.Add("pageSize", pageSize.ToString());
            if (!string.IsNullOrEmpty(identityGroupId))
            {
                parameters.Add("identityGroupIds", identityGroupId);
            }
            if (!string.IsNullOrEmpty(laneId))
            {
                parameters.Add("laneIds", laneId);
            }

            if (!string.IsNullOrEmpty(vehicleTypeId))
            {
                parameters.Add("vehicleTypeIds", vehicleTypeId);
            }

            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, null, headers, parameters, timeOut, RestSharp.Method.Get);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                BaseReport<EventInReport> reports = NewtonSoftHelper<BaseReport<EventInReport>>.GetBaseResponse(response.Item1);
                if (reports != null)
                {
                    if (reports.data == null)
                    {
                        return null;
                    }
                    int totalCount = reports.paging.totalItem;
                    int totalPage = reports.paging.totalPage;
                    return reports?.data.ToDataTable<EventInReport>();
                }
                return null;
            }
            return null;
        }

        public async Task<List<string>> GetFileIns(List<int> fileIds)
        {
            //StandardlizeServerName();
            //string apiUrl = server + KzApiUrlManagement.GetFileNamesRoute(fileIds);
            ////Gửi API
            //Dictionary<string, string> headers = new Dictionary<string, string>()
            //{
            //    { "Authorization","Bearer " + token  }
            //};

            //var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, null, headers, null, timeOut, RestSharp.Method.Get);
            //if (!string.IsNullOrEmpty(response.Item1))
            //{
            //    KzBaseResponseData<List<string>> files = NewtonSoftHelper<KzBaseResponseData<List<string>>>.GetBaseResponse(response.Item1);
            //    return files?.data;
            //}
            return null;
        }
        #endregion

        #region -- EVENT OUT
        public async Task<string> GetLastEventOutIdentityGroupIdByPlateNumber(string plateNumber)
        {
            return "";
        }

        public async Task<bool> UpdateEventOutPlate(string eventId, string plate, string oldPlate)
        {
            StandardlizeServerName();
            string apiUrl = server + KzApiUrlManagement.EmObjectType.EventOut.UpdateRouteById(eventId);

            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };

            var data = new List<CommitData>()
            {
                new CommitData()
                {
                    value = plate,
                    op = "replace",
                    path = "/plateNumber"
                }
            };

            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, data, headers, null, timeOut, RestSharp.Method.Patch);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                KzBaseResponseData<string> kzBaseResponse = NewtonSoftHelper<KzBaseResponseData<string>>.GetBaseResponse(response.Item1);
                if (kzBaseResponse == null)
                {
                    return false;
                }
                return kzBaseResponse.metadata.success;
            }
            return false;
        }
        public async Task<DataTable> GetEventOuts(string keyword, DateTime startTime, DateTime endTime,
            string identityGroupId, string vehicleTypeId,
            string laneId, string user, int pageIndex = 1, int pageSize = 100)
        {
            StandardlizeServerName();
            string apiUrl = server + KzApiUrlManagement.EmObjectType.EventOut.GetDataByParamsRoute();

            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            Dictionary<string, string> parameters = new Dictionary<string, string>();
            if (!string.IsNullOrEmpty(keyword))
            {
                parameters.Add("keyword", keyword);
            }
            parameters.Add("fromUtc", startTime.ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss.000Z"));
            parameters.Add("toUtc", endTime.ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss.000Z"));
            parameters.Add("pageIndex", pageIndex.ToString());
            parameters.Add("pageSize", pageSize.ToString());
            if (!string.IsNullOrEmpty(identityGroupId))
            {
                parameters.Add("identityGroupIds", identityGroupId);
            }
            if (!string.IsNullOrEmpty(laneId))
            {
                parameters.Add("laneIds", laneId);
            }

            if (!string.IsNullOrEmpty(vehicleTypeId))
            {
                parameters.Add("vehicleTypeIds", vehicleTypeId);
            }


            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, null, headers, parameters, timeOut, RestSharp.Method.Get);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                BaseReport<EventOutReport> reports = NewtonSoftHelper<BaseReport<EventOutReport>>.GetBaseResponse(response.Item1);
                if (reports != null)
                {
                    if (reports.data == null)
                    {
                        return null;
                    }
                    int totalCount = reports.paging.totalItem;
                    int totalPage = reports.paging.totalPage;
                    return reports?.data.ToDataTable<EventOutReport>();
                }
                return null;
            }
            return null;
        }
        public async Task<AddEventOutResponse> PostCheckOutAsync(string _laneId, string _plateNumber, Identity? identitiy, List<string> imageKeys, bool isForce)
        {
            StandardlizeServerName();
            string apiUrl = server + KzApiUrlManagement.EmObjectType.EventOut.CreateRoute();
            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            var data = new
            {
                laneId = _laneId,
                plateNumber = string.IsNullOrEmpty(_plateNumber) ? "-" : _plateNumber,
                identityCode = identitiy == null ? null : identitiy?.Code,
                identityType = identitiy == null ? null : identitiy?.Type,
                identities = new List<EventIdentity>(),
                fileKeys = new List<string>(),
                forceEntrance = isForce,
            };
            foreach (var item in imageKeys)
            {
                data.fileKeys.Add(item);
            }
            string a = JsonConvert.SerializeObject(data);
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, data, headers, null, timeOut, RestSharp.Method.Post);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                KzBaseResponseData<AddEventOutResponse> addEventOutResponse = NewtonSoftHelper<KzBaseResponseData<AddEventOutResponse>>.GetBaseResponse(response.Item1);
                return addEventOutResponse?.data;
            }
            return null;
        }

        public async Task<bool> CommitOutAsync(AddEventOutResponse eventOut)
        {
            StandardlizeServerName();
            string apiUrl = server + KzApiUrlManagement.CommitOutRoute;
            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, eventOut, headers, null, timeOut, RestSharp.Method.Post);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                KzBaseResponseData<AddEventOutResponse> addEventOutResponse = NewtonSoftHelper<KzBaseResponseData<AddEventOutResponse>>.GetBaseResponse(response.Item1);
                return addEventOutResponse != null;
            }
            return false;
        }
        public async Task<bool> CancelCheckOut(string eventOutId)
        {
            StandardlizeServerName();
            string apiUrl = server + KzApiUrlManagement.DeleteCheckOutRoute(eventOutId);
            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, null, headers, null, timeOut, RestSharp.Method.Post);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                KzBaseResponseData<string> kzBaseResponse = NewtonSoftHelper<KzBaseResponseData<string>>.GetBaseResponse(response.Item1);
                if (kzBaseResponse == null)
                {
                    return false;
                }
                return kzBaseResponse.metadata.success;
            }
            return false;
        }
        public async Task<iParkingv5.Objects.Datas.payments.PaymentTransaction> CreatePaymentTransaction(AddEventOutResponse eventOut)
        {
            return null;
        }



    
        #endregion

        #region ABNORMAL
        public async Task<bool> CreateAlarmAsync(string identityId, string laneId, string plate, EmAbnormalCode abnormalCode,
                                                        string imageKey, bool isLaneIn, string identityGroupId, string customerId,
                                                        string registerVehicleId, string description)
        {
            StandardlizeServerName();
            string apiUrl = server + KzApiUrlManagement.EmObjectType.AbnormalEvent.CreateRoute();
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            AbnormalEvent abnormalEvent = new AbnormalEvent()
            {
                IdentityId = identityId,
                LaneId = laneId,
                PlateNumber = plate,
                AbnormalCode = abnormalCode,
                FileKeys = new List<string>()
                {
                    imageKey + (isLaneIn? "_OVERVIEWIN.jpeg" : "_OVERVIEWOUT.jpeg"),
                },
                IdentityGroupId = identityGroupId,
                CustomerId = customerId,
                RegisteredVehicleId = registerVehicleId,
                Description = description
            };
            abnormalEvent.FileKeys.Add(imageKey + (isLaneIn ? "_VEHICLEIN.jpeg" : "_VEHICLEOUT.jpeg"));
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, abnormalEvent, headers, null, timeOut, RestSharp.Method.Post);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                KzBaseResponseData<AbnormalEvent> kzBaseResponse = NewtonSoftHelper<KzBaseResponseData<AbnormalEvent>>.GetBaseResponse(response.Item1);
                return kzBaseResponse?.metadata?.success ?? false;
            }
            return false;
        }
        public async Task<DataTable> /*Task<Tuple<List<AbnormalEvent>, int, int>>*/ GetAlarmReport(string keyword, DateTime startTime, DateTime endTime, string identityGroupId, string vehicleTypeId, string laneId, int pageIndex = 1, int pageSize = 100)
        {
            StandardlizeServerName();
            string apiUrl = server + KzApiUrlManagement.EmObjectType.AbnormalEvent.GetDataByParamsRoute();
            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            Dictionary<string, string> parameters = new Dictionary<string, string>();
            if (!string.IsNullOrEmpty(keyword))
            {
                parameters.Add("keyword", keyword);
            }
            parameters.Add("fromUtc", startTime.ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss.000Z"));
            parameters.Add("toUtc", endTime.ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss.000Z"));
            parameters.Add("pageIndex", pageIndex.ToString());
            parameters.Add("pageSize", pageSize.ToString());
            if (!string.IsNullOrEmpty(identityGroupId))
            {
                parameters.Add("identityGroupIds", identityGroupId);
            }
            if (!string.IsNullOrEmpty(laneId))
            {
                parameters.Add("laneIds", laneId);
            }

            if (!string.IsNullOrEmpty(vehicleTypeId))
            {
                parameters.Add("vehicleTypeIds", vehicleTypeId);
            }

            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, null, headers, parameters, timeOut, RestSharp.Method.Get);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                BaseReport<AbnormalEvent> reports = NewtonSoftHelper<BaseReport<AbnormalEvent>>.GetBaseResponse(response.Item1);
                if (reports != null)
                {
                    if (reports.data == null)
                    {
                        return null;
                    }
                    int totalCount = reports.paging.totalItem;
                    int totalPage = reports.paging.totalPage;
                    return reports.data.ToDataTable<AbnormalEvent>();// Tuple.Create(reports?.data, totalPage, totalCount);
                }
                return null;
            }
            return null;
        }
        #endregion

        #region -- REGISTERED VEHICLE
        public async Task<Tuple<RegisteredVehicle, string>> GetRegistedVehilceByPlateAsync(string plateNumber)
        {
            StandardlizeServerName();
            string apiUrl = server + KzApiUrlManagement.EmObjectType.RegisteredVehicle.GetDataByParamsRoute();

            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            Dictionary<string, string> parameters = new Dictionary<string, string>()
            {
                { "keyword", plateNumber }
            };
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, null, headers, parameters, timeOut, RestSharp.Method.Get);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                KzBaseResponseData<List<RegisteredVehicle>> kzBaseResponse = NewtonSoftHelper<KzBaseResponseData<List<RegisteredVehicle>>>.GetBaseResponse(response.Item1);
                if (kzBaseResponse?.data != null)
                {
                    if (kzBaseResponse?.data.Count > 0)
                    {
                        foreach (var item in kzBaseResponse?.data)
                        {
                            if (item.PlateNumber == plateNumber)
                            {
                                return Tuple.Create<RegisteredVehicle, string>(item, "");
                            }
                        }
                        return null;
                    }
                }
                return null;
            }
            return null;
        }
        public async Task<Tuple<RegisteredVehicle, string>> GetRegistedVehilceByIdAsync(string id)
        {
            StandardlizeServerName();
            string apiUrl = server + KzApiUrlManagement.EmObjectType.RegisteredVehicle.GetDataByIdRoute(id);

            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, null, headers, null, timeOut, RestSharp.Method.Get);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                KzBaseResponseData<RegisteredVehicle> kzBaseResponse = NewtonSoftHelper<KzBaseResponseData<RegisteredVehicle>>.GetBaseResponse(response.Item1);
                return Tuple.Create<RegisteredVehicle, string>(kzBaseResponse?.data, "");
            }
            return null;
        }

        public async Task<Tuple<List<RegisteredVehicle>, string>> GetRegisterVehiclesAsync(string keyword)
        {
            StandardlizeServerName();
            string apiUrl = server + KzApiUrlManagement.EmObjectType.RegisteredVehicle.GetDataByParamsRoute();

            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            Dictionary<string, string> parameters = new Dictionary<string, string>()
            {
                { "keyword", keyword }
            };
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, null, headers, parameters, timeOut, RestSharp.Method.Get);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                KzBaseResponseData<List<RegisteredVehicle>> kzBaseResponse = NewtonSoftHelper<KzBaseResponseData<List<RegisteredVehicle>>>.GetBaseResponse(response.Item1);
                if (kzBaseResponse?.data != null)
                {
                    return Tuple.Create<List<RegisteredVehicle>, string>(kzBaseResponse?.data, "");
                }
                return null;
            }
            return null;
        }

        public async Task<Tuple<RegisteredVehicle, string>> CreateRegisteredVehicle(RegisteredVehicle registeredVehicle)
        {
            StandardlizeServerName();
            string apiUrl = server + KzApiUrlManagement.EmObjectType.RegisteredVehicle.CreateRoute();

            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, registeredVehicle, headers, null, timeOut, RestSharp.Method.Post);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                KzBaseResponseData<RegisteredVehicle> kzBaseResponse = NewtonSoftHelper<KzBaseResponseData<RegisteredVehicle>>.GetBaseResponse(response.Item1);
                if (kzBaseResponse == null)
                {
                    return Tuple.Create<RegisteredVehicle, string>(null, "Lỗi dữ liệu, vui lòng thử lại");
                }
                if (!(kzBaseResponse.metadata?.success ?? false))
                {
                    return Tuple.Create<RegisteredVehicle, string>(null, kzBaseResponse.metadata?.message?.value ?? response.Item1);
                }
                return Tuple.Create<RegisteredVehicle, string>(kzBaseResponse.data, string.Empty);
            }
            return Tuple.Create<RegisteredVehicle, string>(null, "Lỗi hệ thống, vui lòng thử lại");
        }

        public async Task<bool> UpdateRegisteredVehicleAsyncById(RegisteredVehicle registeredVehicle)
        {
            StandardlizeServerName();
            string apiUrl = server + KzApiUrlManagement.EmObjectType.RegisteredVehicle.UpdateRouteById(registeredVehicle.Id);

            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, registeredVehicle, headers, null, timeOut, RestSharp.Method.Put);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                KzBaseResponseData<RegisteredVehicle> kzBaseResponse = NewtonSoftHelper<KzBaseResponseData<RegisteredVehicle>>.GetBaseResponse(response.Item1);
                if (kzBaseResponse == null)
                {
                    return false;
                }
                return kzBaseResponse.metadata?.success ?? false;
            }
            return false;
        }
        #endregion

        #region -- CUSTOMER
        public async Task<Tuple<Customer, string>> CreateCustomer(Customer customer)
        {
            StandardlizeServerName();
            string apiUrl = server + KzApiUrlManagement.EmObjectType.Customer.CreateRoute();

            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, customer, headers, null, timeOut, RestSharp.Method.Post);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                KzBaseResponseData<Customer> kzBaseResponse = NewtonSoftHelper<KzBaseResponseData<Customer>>.GetBaseResponse(response.Item1);

                if (kzBaseResponse == null)
                {
                    return Tuple.Create<Customer, string>(null, "Lỗi dữ liệu, vui lòng thử lại");
                }
                if (!kzBaseResponse.metadata.success)
                {
                    var errorCode = ApiInternalErrorMessages.GetFromName(kzBaseResponse.metadata.message.code);

                    return Tuple.Create<Customer, string>(null, ApiInternalErrorMessages.ToString(errorCode));
                }
                return Tuple.Create<Customer, string>(kzBaseResponse.data, kzBaseResponse.data.Id);
            }
            return Tuple.Create<Customer, string>(null, "Lỗi hệ thống, vui lòng thử lại");
        }
        public async Task<Tuple<Customer, string>> GetCustomerByIdAsync(string id)
        {
            StandardlizeServerName();
            string apiUrl = server + KzApiUrlManagement.EmObjectType.Customer.GetDataByIdRoute(id);

            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, null, headers, null, timeOut, RestSharp.Method.Get);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                KzBaseResponseData<Customer> kzBaseResponse = NewtonSoftHelper<KzBaseResponseData<Customer>>.GetBaseResponse(response.Item1);
                return Tuple.Create<Customer, string>(kzBaseResponse?.data, "");
            }
            return null;
        }
        public async Task<Tuple<bool, string>> DeleteCustomerById(string customerId)
        {
            StandardlizeServerName();
            string apiUrl = server + KzApiUrlManagement.EmObjectType.Customer.DeleteByIdRoute(customerId);

            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, null, headers, null, timeOut, RestSharp.Method.Delete);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                KzBaseResponse kzBaseResponse = NewtonSoftHelper<KzBaseResponse>.GetBaseResponse(response.Item1);

                if (kzBaseResponse == null)
                {
                    return Tuple.Create<bool, string>(false, "Lỗi dữ liệu, vui lòng thử lại");
                }
                if (!kzBaseResponse.isSuccess)
                {
                    return Tuple.Create<bool, string>(false, kzBaseResponse.message);
                }
                return Tuple.Create<bool, string>(true, string.Empty);
            }
            return Tuple.Create<bool, string>(false, "Lỗi hệ thống, vui lòng thử lại");
        }
        public async Task<Tuple<List<Customer>, string>> GetCustomersAsync()
        {
            return await GetAllCustomers();
        }
        public async Task<Tuple<List<Customer>, string>> GetCustomersAsync(string keyWord)
        {
            StandardlizeServerName();
            string apiUrl = server + KzApiUrlManagement.EmObjectType.Customer.GetDataByParamsRoute();

            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            Dictionary<string, string> parameters = new Dictionary<string, string>()
            {
                { "keyword", keyWord }
            };
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, null, headers, parameters, timeOut, RestSharp.Method.Get);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                KzBaseResponseData<List<Customer>> kzBaseResponse = NewtonSoftHelper<KzBaseResponseData<List<Customer>>>.GetBaseResponse(response.Item1);
                if (kzBaseResponse == null)
                {
                    return Tuple.Create<List<Customer>, string>(null, response.Item2);
                }
                else
                {
                    if (kzBaseResponse.metadata.success)
                    {
                        return Tuple.Create<List<Customer>, string>(kzBaseResponse?.data, kzBaseResponse.metadata?.message?.value);
                    }
                    else
                    {
                        return Tuple.Create<List<Customer>, string>(null, kzBaseResponse.metadata?.message?.value);
                    }
                }
            }
            return Tuple.Create<List<Customer>, string>(null, response.Item2);
        }
        public async Task<Tuple<List<Customer>, string>> GetAllCustomers(string name = "", string customerGroupId = "")
        {
            StandardlizeServerName();
            string apiUrl = server + KzApiUrlManagement.EmObjectType.Customer.GetDataByParamsRoute();

            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            Dictionary<string, string> parameters = new Dictionary<string, string>()
            {
                {"keyword", name },
                {"customerGroupId", customerGroupId },
                {"enable", "true" },
            };
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, null, headers, parameters, timeOut, RestSharp.Method.Get);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                KzBaseResponseData<List<Customer>> kzBaseResponse = NewtonSoftHelper<KzBaseResponseData<List<Customer>>>.GetBaseResponse(response.Item1);
                if (kzBaseResponse == null)
                {
                    return Tuple.Create<List<Customer>, string>(null, response.Item2);
                }
                else
                {
                    if (kzBaseResponse.metadata.success)
                    {
                        return Tuple.Create<List<Customer>, string>(kzBaseResponse?.data, kzBaseResponse.metadata?.message?.value ?? "");
                    }
                    else
                    {
                        return Tuple.Create<List<Customer>, string>(null, kzBaseResponse.metadata?.message?.value);
                    }
                }
            }
            return Tuple.Create<List<Customer>, string>(null, response.Item2);
        }
        public async Task<bool> UpdateCustomer(Customer customer)
        {
            StandardlizeServerName();
            string apiUrl = server + KzApiUrlManagement.EmObjectType.Customer.UpdateRouteById(customer.Id);

            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, customer, headers, null, timeOut, RestSharp.Method.Put);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                KzBaseResponseData<Customer> kzBaseResponse = NewtonSoftHelper<KzBaseResponseData<Customer>>.GetBaseResponse(response.Item1);
                return kzBaseResponse?.metadata?.success ?? false;
            }
            return false;
        }
        #endregion

        #region -- CUSTOMER GROUP
        public async Task<Tuple<List<CustomerGroup>, string>> GetCustomerGroupsAsync()
        {
            StandardlizeServerName();
            string apiUrl = server + KzApiUrlManagement.EmObjectType.CustomerGroup.GetDataByParamsRoute();

            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, null, headers, null, timeOut, RestSharp.Method.Get);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                KzBaseResponseData<List<CustomerGroup>> kzBaseResponse = NewtonSoftHelper<KzBaseResponseData<List<CustomerGroup>>>.GetBaseResponse(response.Item1);
                return Tuple.Create<List<CustomerGroup>, string>(kzBaseResponse?.data, "");
            }
            return null;
        }
        #endregion

        #region --INVOICE
        public async Task<InvoiceResponse> CreateEinvoice(long price, string plateNumber, DateTime datetimeIn, DateTime datetimeOut, string eventOutId, bool isSendNow = true, string cardGroupName = "")
        {
            return null;
        }
        public async Task<InvoiceFileInfor> GetInvoiceData(string orderId, EmInvoiceProvider provider = EmInvoiceProvider.Viettel)
        {
            return null;
        }
        public async Task<List<InvoiceResponse>> GetMultipleInvoiceData(DateTime startTime, DateTime endTime, EmInvoiceProvider provider = EmInvoiceProvider.Viettel)
        {
            return null;
        }
        public async Task<List<InvoiceResponse>> getPendingEInvoice(DateTime startTime, DateTime endTime) { return new List<InvoiceResponse>(); }
        public async Task<bool> sendPendingEInvoice(string orderId)
        {
            StandardlizeServerName();
            return true;
        }
        #endregion

        #region WAREHOUSE
        public async Task<WarehouseService> CreateWarehouseService(string eventInId, string eventOutId, string plate, EmTransactionType type, bool isPrint = false)
        {
            return null;
        }
        #endregion

        #endregion END PUBLIC FUNCTION

        #region PRIVATE FUNCTION
        private static void StandardlizeServerName()
        {
            if (server[^1] != '/' && server[^1] != '\\')
            {
                server += "/";
            }
        }

        public Task<string> GetFeeCalculate()
        {
            throw new NotImplementedException();
        }

        public Task<string> GetFeeCalculate(string dateTimeIn, string dateTimeOut, string identityGroupID)
        {
            throw new NotImplementedException();
        }

        public Task<ParkingSystemConfig> GetSystemConfigAsync()
        {
            throw new NotImplementedException();
        }
        #endregion END PRIVATE FUNCTION       
    }
}
