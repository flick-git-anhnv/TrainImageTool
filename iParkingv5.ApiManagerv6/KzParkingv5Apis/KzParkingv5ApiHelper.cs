using iParkingv5.Objects;
using iParkingv5.Objects.Datas;
using iParkingv5.Objects.Datas.Devices;
using iParkingv5.Objects.Datas.parking;
using iParkingv5.Objects.Datas.payments;
using iParkingv5.Objects.Datas.system;
using iParkingv5.Objects.Enums;
using iParkingv5.Objects.EventDatas;
using iParkingv5.Objects.Invoices;
using iParkingv5.Objects.Payment;
using iParkingv5.Objects.Reporting;
using iParkingv5.Objects.warehouse;
using iParkingv6.ApiManager;
using iParkingv6.ApiManager.KzParkingv3Apis;
using Kztek.Tool;
using Kztek.Tools;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using RestSharp;
using System;
using System.Collections.Generic;
using System.Data;
using System.Threading.Tasks;
using static iParkingv5.ApiManager.KzParkingv5Apis.Filter;
using static iParkingv5.ApiManager.KzParkingv5Apis.KzParkingv5BaseApi;
using static iParkingv5.Objects.warehouse.TransactionType;
using PaymentTransaction = iParkingv5.Objects.Datas.payments.PaymentTransaction;

namespace iParkingv5.ApiManager.KzParkingv5Apis
{
    public class KzParkingv5ApiHelper : iParkingApi
    {
        const string getCompanyInfoRoute = "project/BF195768-4C7F-4F59-A50F-F41AD693BBC0";
        string getInvoiceConfigRoute => "tenant/" + "00f43ef8-f67b-446a-870a-c219b59c0c4e".ToUpper();
        string getScaleConfigRoute => "project/" + "4b9acc2f-8758-4bfa-ad08-5b7d47bf67d1".ToUpper();
        public static string UTCFormat = "yyyy-MM-ddTHH:mm:ss:0000";

        #region System Config
        //--GET--
        public async Task<ParkingSystemConfig> GetSystemConfigAsync()
        {
            StandardlizeServerName();
            string apiUrl = server + getCompanyInfoRoute;

            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, null, headers, null,
                                                                  timeOut, Method.Get);

            apiUrl = server + getInvoiceConfigRoute;
            var response2 = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, null, headers, null,
                                                               timeOut, Method.Get);

            apiUrl = server + getScaleConfigRoute;
            var response3 = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, null, headers, null,
                                                                timeOut, Method.Get);
            if (!string.IsNullOrEmpty(response2.Item1))
            {
                CompanyInfo companyInfo = JsonConvert.DeserializeObject<CompanyInfo>(response2.Item1);
                if (companyInfo != null)
                {
                    StaticPool.TaxCode = companyInfo.companyTax;
                    StaticPool.CompanyName = companyInfo.companyName;
                    StaticPool.CompanyAddress = companyInfo.companyAddress;
                }
            }
            if (!string.IsNullOrEmpty(response3.Item1))
            {
                WeighingSystemConfig weighingSystemConfig = JsonConvert.DeserializeObject<WeighingSystemConfig>(response3.Item1);
                if (weighingSystemConfig != null)
                {
                    StaticPool.scaleInvoiceTypeCode = weighingSystemConfig.invoiceTypeCode;
                    StaticPool.scaleSymbolCode = weighingSystemConfig.invoiceSymbolCode;
                    StaticPool.scaleTemplateCode = weighingSystemConfig.invoiceTemplateCode;
                    StaticPool.scaleTaxRate = weighingSystemConfig.taxRate;
                }
            }

            if (!string.IsNullOrEmpty(response.Item1))
            {
                var parkingSystemConfig = JsonConvert.DeserializeObject<ParkingSystemConfig>(response.Item1);
                if (parkingSystemConfig != null)
                {
                    StaticPool.templateCode = parkingSystemConfig.InvoiceTemplateCode;
                    StaticPool.invoiceTypeCode = parkingSystemConfig.InvoiceTypeCode;
                    StaticPool.symbolCode = parkingSystemConfig.InvoiceSymbolCode;
                    StaticPool.TaxRate = parkingSystemConfig.taxRate;
                    LogHelper.Log(LogHelper.EmLogType.INFOR,
                        LogHelper.EmObjectLogType.System,
                        noi_dung_hanh_dong: $@"Tải hóa đơn điện tử {StaticPool.CompanyName} - {StaticPool.CompanyAddress} - 
                                                                   {StaticPool.TaxCode} - {StaticPool.templateCode} - 
                                                                   {StaticPool.symbolCode} - {StaticPool.TaxRate}");
                }

                return parkingSystemConfig;
            }
            else
            {
                return null;
            }

        }
        #endregion END System Config

        #region USER --OK
        //--GET--
        public async Task GetUserInforAsync()
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
        public async Task<Tuple<List<User>, string>> GetAllUsersAsync()
        {
            return await KzParkingv5BaseApi.GetAllObjectAsync<User>(KzParkingv5ApiUrlManagement.EmParkingv5ObjectType.User);
        }
        #endregion End USER

        #region DEVICE -- OK

        #region Computer --OK
        //--GET--
        public async Task<Tuple<List<Computer>, string>> GetComputersAsync()
        {
            return await KzParkingv5BaseApi.GetAllObjectAsync<Computer>(KzParkingv5ApiUrlManagement.EmParkingv5ObjectType.Computer);
        }
        public async Task<Tuple<Computer, string>> GetComputerByIPAsync(string ip)
        {
            return await KzParkingv5BaseApi.GetTop1ObjectAsync<Computer>(KzParkingv5ApiUrlManagement.EmParkingv5ObjectType.Computer,
                                                                         EmPageSearchType.TEXT, EmPageSearchKey.IpAddress, ip);
        }
        #endregion End Computer

        #region Gate --OK
        //--GET--
        public async Task<Tuple<List<Gate>, string>> GetGatesAsync()
        {
            return await KzParkingv5BaseApi.GetAllObjectAsync<Gate>(KzParkingv5ApiUrlManagement.EmParkingv5ObjectType.Gate);
        }
        public async Task<Tuple<Gate, string>> GetGateByIdAsync(string gateId)
        {
            return await KzParkingv5BaseApi.GetObjectDetailByIdAsync<Gate>(KzParkingv5ApiUrlManagement.EmParkingv5ObjectType.Gate, gateId);
        }
        #endregion End Gate

        #region CAMERA
        //--GET--
        public async Task<Tuple<List<Camera>, string>> GetCamerasAsync()
        {
            return await KzParkingv5BaseApi.GetAllObjectAsync<Camera>(KzParkingv5ApiUrlManagement.EmParkingv5ObjectType.Camera);
        }
        public async Task<Tuple<List<Camera>, string>> GetCameraByComputerIdAsync(string computerId)
        {
            return await KzParkingv5BaseApi.GetObjectByConditionAsync<Camera>(KzParkingv5ApiUrlManagement.EmParkingv5ObjectType.Camera,
                                                           EmPageSearchType.GUID, EmPageSearchKey.ComputerId, computerId, EmOperation._eq);
        }
        #endregion END CAMERA

        #region LANE
        //--GET--
        public async Task<Tuple<List<Lane>, string>> GetLanesAsync()
        {
            return await KzParkingv5BaseApi.GetAllObjectAsync<Lane>(KzParkingv5ApiUrlManagement.EmParkingv5ObjectType.Lane);
        }
        public async Task<Tuple<List<Lane>, string>> GetLaneByComputerIdAsync(string computerId)
        {
            return await KzParkingv5BaseApi.GetObjectByConditionAsync<Lane>(KzParkingv5ApiUrlManagement.EmParkingv5ObjectType.Lane,
                                                        EmPageSearchType.GUID, EmPageSearchKey.ComputerId, computerId, EmOperation._eq);

        }
        public async Task<Tuple<Lane, string>> GetLaneByIdAsync(string paymentId)
        {
            return await KzParkingv5BaseApi.GetObjectDetailByIdAsync<Lane>(KzParkingv5ApiUrlManagement.EmParkingv5ObjectType.Lane, paymentId);
        }
        #endregion END LANE

        #region PARKING LED
        //--GET--
        public async Task<Tuple<List<Led>, string>> GetLedsAsync()
        {
            return await KzParkingv5BaseApi.GetAllObjectAsync<Led>(KzParkingv5ApiUrlManagement.EmParkingv5ObjectType.Led);
        }
        public async Task<Tuple<List<Led>, string>> GetLedByComputerIdAsync(string computerId)
        {
            return await KzParkingv5BaseApi.GetObjectByConditionAsync<Led>(KzParkingv5ApiUrlManagement.EmParkingv5ObjectType.Led,
                                                        EmPageSearchType.GUID, EmPageSearchKey.ComputerId, computerId, EmOperation._eq);
        }
        #endregion End Parking Led

        #region CONTROL UNIT
        public async Task<Tuple<List<Bdk>, string>> GetControlUnitsAsync()
        {
            return await KzParkingv5BaseApi.GetAllObjectAsync<Bdk>(KzParkingv5ApiUrlManagement.EmParkingv5ObjectType.ControlUnit);
        }
        public async Task<Tuple<List<Bdk>, string>> GetControlUnitByComputerIdAsync(string computerId)
        {
            return await KzParkingv5BaseApi.GetObjectByConditionAsync<Bdk>(KzParkingv5ApiUrlManagement.EmParkingv5ObjectType.ControlUnit,
                                                        EmPageSearchType.GUID, EmPageSearchKey.ComputerId, computerId, EmOperation._eq);
        }
        #endregion END CONTROL UNIT

        #endregion END DEVICE

        #region PARKING DATA

        #region Vehicle Type
        public async Task<Tuple<VehicleType, string>> GetVehicleTypeByIdAsync(string vehicleTypeId)
        {
            return await KzParkingv5BaseApi.GetObjectDetailByIdAsync<VehicleType>(KzParkingv5ApiUrlManagement.EmParkingv5ObjectType.VehicleType, vehicleTypeId);
        }
        public async Task<Tuple<List<VehicleType>, string>> GetVehicleTypesAsync()
        {
            return await KzParkingv5BaseApi.GetAllObjectAsync<VehicleType>(KzParkingv5ApiUrlManagement.EmParkingv5ObjectType.VehicleType);
        }
        public async Task<Tuple<List<VehicleType>, string>> GetVehicleTypesAsync(string keyword)
        {
            return await KzParkingv5BaseApi.GetObjectByConditionAsync<VehicleType>(KzParkingv5ApiUrlManagement.EmParkingv5ObjectType.VehicleType,
                                                        EmPageSearchType.TEXT, EmPageSearchKey.name, keyword, EmOperation._contains);

        }
        #endregion End Vehicle Type

        #region Identity
        public async Task<Tuple<Identity, string>> GetIdentityByIdAsync(string id)
        {
            return await KzParkingv5BaseApi.GetObjectDetailByIdAsync<Identity>(KzParkingv5ApiUrlManagement.EmParkingv5ObjectType.Identity, id);
        }
        public async Task<Tuple<List<Identity>, string>> GetIdentitiesAsync(string keyword)
        {
            return await KzParkingv5BaseApi.GetObjectByConditionAsync<Identity>(KzParkingv5ApiUrlManagement.EmParkingv5ObjectType.Identity,
                                                        EmPageSearchType.TEXT, EmPageSearchKey.name, keyword, EmOperation._contains);

        }
        public async Task<Tuple<Identity, string>> GetIdentityByCodeAsync(string code)
        {
            return await KzParkingv5BaseApi.GetTop1ObjectAsync<Identity>(KzParkingv5ApiUrlManagement.EmParkingv5ObjectType.Identity, EmPageSearchType.TEXT,
                                                      EmPageSearchKey.code, code);
        }
        public async Task<Tuple<Identity, string>> CreateIdentityAsync(Identity identity)
        {
            return await KzParkingv5BaseApi.CreateObjectAsync<Identity>(KzParkingv5ApiUrlManagement.EmParkingv5ObjectType.Identity,
                                                              identity);
        }
        #endregion End Identity

        #region Identity Group
        public async Task<Tuple<IdentityGroup, string>> GetIdentityGroupByIdAsync(string id)
        {
            return await KzParkingv5BaseApi.GetObjectDetailByIdAsync<IdentityGroup>(KzParkingv5ApiUrlManagement.EmParkingv5ObjectType.IdentityGroup, id);
        }
        public async Task<Tuple<List<IdentityGroup>, string>> GetIdentityGroupsAsync()
        {
            return await KzParkingv5BaseApi.GetAllObjectAsync<IdentityGroup>(KzParkingv5ApiUrlManagement.EmParkingv5ObjectType.IdentityGroup);
        }
        #endregion End Identity Group

        #region Register Vehicle
        public async Task<Tuple<RegisteredVehicle, string>> GetRegistedVehilceByPlateAsync(string plateNumber)
        {
            return await KzParkingv5BaseApi.GetTop1ObjectAsync<RegisteredVehicle>(KzParkingv5ApiUrlManagement.EmParkingv5ObjectType.RegisteredVehicle, EmPageSearchType.TEXT,
                                                      EmPageSearchKey.plateNumber, plateNumber);
        }
        public async Task<Tuple<RegisteredVehicle, string>> GetRegistedVehilceByIdAsync(string id)
        {
            return await KzParkingv5BaseApi.GetObjectDetailByIdAsync<RegisteredVehicle>(KzParkingv5ApiUrlManagement.EmParkingv5ObjectType.RegisteredVehicle, id);
        }
        public async Task<Tuple<List<RegisteredVehicle>, string>> GetRegisterVehiclesAsync(string keyword)
        {
            return await KzParkingv5BaseApi.GetObjectByConditionAsync<RegisteredVehicle>(KzParkingv5ApiUrlManagement.EmParkingv5ObjectType.RegisteredVehicle,
                                                            EmPageSearchType.TEXT, EmPageSearchKey.name, keyword, EmOperation._contains);

        }
        public async Task<Tuple<RegisteredVehicle, string>> CreateRegisteredVehicle(RegisteredVehicle registeredVehicle)
        {
            return await KzParkingv5BaseApi.CreateObjectAsync<RegisteredVehicle>(KzParkingv5ApiUrlManagement.EmParkingv5ObjectType.RegisteredVehicle,
                                                              registeredVehicle);
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
        #endregion End Register Vehicle

        #region Customer
        public async Task<Tuple<Customer, string>> CreateCustomer(Customer customer)
        {
            return await KzParkingv5BaseApi.CreateObjectAsync<Customer>(KzParkingv5ApiUrlManagement.EmParkingv5ObjectType.Customer, customer);
        }
        public async Task<Tuple<Customer, string>> GetCustomerByIdAsync(string id)
        {
            return await KzParkingv5BaseApi.GetObjectDetailByIdAsync<Customer>(KzParkingv5ApiUrlManagement.EmParkingv5ObjectType.Customer, id);
        }
        public async Task<Tuple<List<Customer>, string>> GetCustomersAsync()
        {
            return await KzParkingv5BaseApi.GetAllObjectAsync<Customer>(KzParkingv5ApiUrlManagement.EmParkingv5ObjectType.Customer);
        }
        public async Task<Tuple<List<Customer>, string>> GetCustomersAsync(string keyword)
        {
            return await KzParkingv5BaseApi.GetObjectByConditionAsync<Customer>(KzParkingv5ApiUrlManagement.EmParkingv5ObjectType.Customer,
                                                            EmPageSearchType.TEXT, EmPageSearchKey.name, keyword, EmOperation._contains);

        }
        public async Task<Tuple<List<Customer>, string>> GetCustomersAsync(string customerGroupName, string name, string tax)
        {
            StandardlizeServerName();
            string apiUrl = server + KzParkingv5ApiUrlManagement.SearchObjectDataRoute(KzParkingv5ApiUrlManagement.EmParkingv5ObjectType.Customer);

            List<FilterModel> filters = new List<FilterModel>
            {
                new FilterModel("name", "TEXT", name, "contains"),
                new FilterModel("customerGroup.name", "TEXT", customerGroupName, "contains"),
                new FilterModel("customerGroup.tax", "TEXT", tax, "contains")
            };
            Dictionary<string, List<FilterModel>> filterTemp = new Dictionary<string, List<FilterModel>>();
            filterTemp.Add("and", filters);

            var filterKeyword = Filter.CreateFilter(new List<Dictionary<string, List<FilterModel>>>() { filterTemp }, EmMainOperation.and, 0, 20);
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            var a = Newtonsoft.Json.JsonConvert.SerializeObject(filterKeyword);
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, filterKeyword, headers, null,
                                                                   timeOut, Method.Post);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                KzParkingv5BaseResponse<List<Customer>> kzBaseResponse =
                    NewtonSoftHelper<KzParkingv5BaseResponse<List<Customer>>>.GetBaseResponse(response.Item1);
                if (kzBaseResponse == null)
                {
                    return Tuple.Create<List<Customer>, string>(null, "Error Convert Json Data" + response.Item1);
                }
                if (kzBaseResponse.data == null)
                {
                    return Tuple.Create<List<Customer>, string>(null, kzBaseResponse.detailCode);
                }
                return Tuple.Create<List<Customer>, string>(kzBaseResponse.data, kzBaseResponse.detailCode);
            }
            return Tuple.Create<List<Customer>, string>(null, "Empty Data");

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
        #endregion End Customer

        #region Customer Group
        public async Task<Tuple<List<CustomerGroup>, string>> GetCustomerGroupsAsync()
        {
            return await KzParkingv5BaseApi.GetAllObjectAsync<CustomerGroup>(KzParkingv5ApiUrlManagement.EmParkingv5ObjectType.CustomerGroup);
        }
        #endregion End Customer Group

        #endregion END PARKING DATA

        #region PARKING PROCESS

        #region EVENT IN
        //--UPDATE--
        public async Task<bool> UpdateEventInPlateAsync(string eventId, string newPlate, string oldPlate)
        {
            StandardlizeServerName();
            string apiUrl = server + KzParkingv5ApiUrlManagement.PostObjectRoute(KzParkingv5ApiUrlManagement.EmParkingv5ObjectType.EventIn) + "/" + eventId;
            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
             {
                 { "Authorization","Bearer " + token  }
             };
            var commitData = new List<CommitData>
            {
                new CommitData()
                {
                    op = "replace",
                    path = "plateNumber",
                    value = newPlate
                }
            };
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, commitData, headers, null, timeOut, RestSharp.Method.Patch);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                LogHelper.Log(LogHelper.EmLogType.WARN, LogHelper.EmObjectLogType.System, specailName: "LPR_EDIT_IN", mo_ta_them: "EventId: " + eventId +
                                                                                                                                 "\r\nOld Plate: " + oldPlate +
                                                                                                                                 " => New Plate: " + newPlate);
                return true;
            }
            return false;
        }
        public static async Task<bool> UpdateBSXNote(string newNote, string eventId, bool isEventIn)
        {
            StandardlizeServerName();
            string apiUrl = isEventIn ?
                server + KzParkingv5ApiUrlManagement.PostObjectRoute(KzParkingv5ApiUrlManagement.EmParkingv5ObjectType.EventIn) + "/" + eventId :
                server + KzParkingv5ApiUrlManagement.PostObjectRoute(KzParkingv5ApiUrlManagement.EmParkingv5ObjectType.EventOut) + "/" + eventId
                ;
            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
             {
                 { "Authorization","Bearer " + token  }
             };
            var commitData = new List<CommitData>();
            commitData.Add(new CommitData()
            {
                op = "replace",
                path = "baseNote",
                value = newNote
            });
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, commitData, headers, null, timeOut, Method.Patch);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                return true;
            }
            return false;
        }

        //--ADD--
        public async Task<AddEventInResponse> PostCheckInAsync(string eventId, int weight,
            string _laneId, string _plateNumber, Identity? identity, List<string> imageKeys, bool isForce = false, RegisteredVehicle? registeredVehicle = null, string _note = "")
        {
            if (identity == null)
            {
                return await PostCheckInByPlateAsync(eventId, weight, _laneId, _plateNumber, identity, imageKeys, isForce, registeredVehicle, _note);
            }
            else
            {
                return await PostCheckInByIdentityAsync(eventId, weight, _laneId, _plateNumber, identity, imageKeys, isForce, registeredVehicle, _note);
            }
        }
        private async Task<AddEventInResponse> PostCheckInByIdentityAsync(string eventId, int weight, string _laneId, string _plateNumber, Identity? identity, List<string> imageKeys, bool isForce = false, RegisteredVehicle? registeredVehicle = null, string _note = "")
        {
            StandardlizeServerName();
            string apiUrl = server + KzParkingv5ApiUrlManagement.PostObjectRoute(KzParkingv5ApiUrlManagement.EmParkingv5ObjectType.EventIn) + "/identity";
            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };

            var data = new
            {
                Id = eventId,
                laneId = _laneId,
                identityCode = identity.Code,
                identityType = 0,
                plateNumber = _plateNumber,
                force = isForce,
                fileKeys = new List<string>(),
                note = _note,
                Weight = weight,
            };

            foreach (var item in imageKeys)
            {
                data.fileKeys.Add(item);
            }
            string a = JsonConvert.SerializeObject(data);
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, data, headers, null, 10000, RestSharp.Method.Post);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                try
                {
                    AddEventInResponse addEventInResponse = NewtonSoftHelper<AddEventInResponse>.GetBaseResponse(response.Item1);
                    return addEventInResponse;
                }
                catch (Exception)
                {
                }
            }
            return null;
        }
        private async Task<AddEventInResponse> PostCheckInByPlateAsync(string eventId, int weight, string _laneId, string _plateNumber, Identity? identity,
                                                                       List<string> imageKeys, bool isForce = false,
                                                                       RegisteredVehicle? registeredVehicle = null,
                                                                       string _note = "")
        {
            StandardlizeServerName();
            string apiUrl = server + KzParkingv5ApiUrlManagement.PostObjectRoute(KzParkingv5ApiUrlManagement.EmParkingv5ObjectType.EventIn) + "/vehicle";

            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };

            var data = new
            {
                Id = eventId,
                laneId = _laneId,
                plateNumber = _plateNumber,
                force = isForce,
                fileKeys = new List<string>(),
                Weight = weight,
                note = _note
            };

            foreach (var item in imageKeys)
            {
                data.fileKeys.Add(item);
            }
            string a = JsonConvert.SerializeObject(data);
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, data, headers, null, timeOut, RestSharp.Method.Post);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                try
                {
                    AddEventInResponse addEventInResponse = NewtonSoftHelper<AddEventInResponse>.GetBaseResponse(response.Item1);
                    return addEventInResponse;
                }
                catch (Exception)
                {
                }
            }
            return null;
        }
        #endregion END EVENT IN

        #region EVENT OUT
        //--ADD--
        public async Task<AddEventOutResponse> PostCheckOutAsync(string _laneId, string _plateNumber, Identity? identitiy, List<string> imageKeys, bool isForce, int weight, string eventId)
        {
            StandardlizeServerName();
            string apiUrl = server + KzApiUrlManagement.EmObjectType.EventOut.CreateRoute();
            if (identitiy == null)
            {
                return await PostCheckOutByPlateAsync(eventId, _laneId, _plateNumber, identitiy, imageKeys, isForce, null, weight);
            }
            else
            {
                return await PostCheckOutByIdentityAsync(eventId, _laneId, _plateNumber, identitiy, imageKeys, isForce, weight);
            }
        }
        private async Task<AddEventOutResponse> PostCheckOutByIdentityAsync(string eventId, string _laneId, string _plateNumber, Identity? identity, List<string> imageKeys, bool isForce = false, int weight = 0)
        {
            StandardlizeServerName();
            string apiUrl = server + KzParkingv5ApiUrlManagement.PostObjectRoute(KzParkingv5ApiUrlManagement.EmParkingv5ObjectType.EventOut) + "/identity";
            //string apiUrl = "http://10.10.0.103:3006/pk/" + KzParkingv5ApiUrlManagement.PostObjectRoute(KzParkingv5ApiUrlManagement.EmParkingv5ObjectType.EventOut) + "/identity";
            //Gửi API
            //apiUrl = "http://192.168.21.13:3004/pk/event-out/identity";
            Dictionary<string, string> headers = new Dictionary<string, string>()
                {
                { "Authorization","Bearer " + token  }
                };

            var data = new
            {
                id = eventId,
                laneId = _laneId,
                identityCode = identity.Code,
                identityType = 0,
                plateNumber = _plateNumber,
                force = isForce,
                fileKeys = new List<string>(),
                Weight = weight,
            };

            foreach (var item in imageKeys)
            {
                data.fileKeys.Add(item);
            }
            string a = JsonConvert.SerializeObject(data);
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, data, headers, null, timeOut, RestSharp.Method.Post);

            if (!string.IsNullOrEmpty(response.Item1))
            {
                try
                {
                    AddEventOutResponse addEventOutResponse = NewtonSoftHelper<AddEventOutResponse>.GetBaseResponse(response.Item1);
                    if (!addEventOutResponse.IsSuccess)
                    {
                        addEventOutResponse.eventIn = addEventOutResponse.payload.ContainsKey("EventIn") ? addEventOutResponse.payload["EventIn"] : null;
                    }
                    return addEventOutResponse;
                }
                catch (Exception)
                {
                }
            }
            return null;
        }
        private async Task<AddEventOutResponse> PostCheckOutByPlateAsync(string eventId, string _laneId, string _plateNumber, Identity? identity, List<string> imageKeys, bool isForce = false, RegisteredVehicle? registeredVehicle = null, int weight = 0)
        {
            StandardlizeServerName();
            string apiUrl = server + KzParkingv5ApiUrlManagement.PostObjectRoute(KzParkingv5ApiUrlManagement.EmParkingv5ObjectType.EventOut) + "/vehicle";

            Dictionary<string, string> headers = new Dictionary<string, string>()
                {
                { "Authorization","Bearer " + token  }
                };

            var data = new
            {
                id = eventId,
                laneId = _laneId,
                plateNumber = _plateNumber,
                force = isForce,
                fileKeys = new List<string>(),
                Weight = weight,
            };

            foreach (var item in imageKeys)
            {
                data.fileKeys.Add(item);
            }
            string a = JsonConvert.SerializeObject(data);
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, data, headers, null, timeOut, RestSharp.Method.Post);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                try
                {
                    AddEventOutResponse addEventOutResponse = NewtonSoftHelper<AddEventOutResponse>.GetBaseResponse(response.Item1);
                    if (!addEventOutResponse.IsSuccess)
                    {
                        addEventOutResponse.eventIn = addEventOutResponse.payload.ContainsKey("EventIn") ? addEventOutResponse.payload["EventIn"] : null;
                    }
                    return addEventOutResponse;
                }
                catch (Exception)
                {
                }
            }
            return null;
        }

        //--UPDATE--
        public async Task<bool> UpdateEventOutPlate(string eventId, string newPlate, string oldPlate)
        {
            StandardlizeServerName();
            string apiUrl = server + KzParkingv5ApiUrlManagement.PostObjectRoute(KzParkingv5ApiUrlManagement.EmParkingv5ObjectType.EventOut) + "/" + eventId;
            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
             {
                 { "Authorization","Bearer " + token  }
             };
            var commitData = new List<CommitData>();
            commitData.Add(new CommitData()
            {
                op = "replace",
                path = "plateNumber",
                value = newPlate
            });
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, commitData, headers, null, timeOut, RestSharp.Method.Patch);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                LogHelper.Log(LogHelper.EmLogType.WARN, LogHelper.EmObjectLogType.System, specailName: "LPR_EDIT_OUT", mo_ta_them: "EventId: " + eventId +
                                                                                                                                    "\r\nOld Plate: " + oldPlate +
                                                                                                                                    " => New Plate: " + newPlate); return true;
            }
            return false;
        }
        public async Task<bool> CommitOutAsync(AddEventOutResponse eventOut)
        {
            StandardlizeServerName();
            string apiUrl = server + KzParkingv5ApiUrlManagement.PostObjectRoute(KzParkingv5ApiUrlManagement.EmParkingv5ObjectType.EventOut) + "/" + eventOut.Id;
            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            var commitData = new List<CommitData>();
            commitData.Add(new CommitData()
            {
                op = "replace",
                path = "approve",
                value = true
            });
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, commitData, headers, null, timeOut, RestSharp.Method.Patch);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                return Convert.ToBoolean(response.Item1);
                //AddEventOutResponse addEventOutResponse = NewtonSoftHelper<AddEventOutResponse>.GetBaseResponse(response.Item1);
                //return addEventOutResponse;
            }
            return false;
        }

        public static async Task<bool> ApproveExit(string eventid)
        {
            StandardlizeServerName();
            string apiUrl = server + "event-in/" + eventid;
            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            var commitData = new List<CommitData>();
            commitData.Add(new CommitData()
            {
                op = "replace",
                path = "approveExit",
                value = true
            });
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, commitData, headers, null, timeOut, RestSharp.Method.Patch);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                return Convert.ToBoolean(response.Item1);
                //AddEventOutResponse addEventOutResponse = NewtonSoftHelper<AddEventOutResponse>.GetBaseResponse(response.Item1);
                //return addEventOutResponse;
            }
            return false;
        }

        //--DELETE--
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
        #endregion End EVENT OUT

        #region PAYMENT
        public async Task<PaymentTransaction> CreatePaymentTransaction(AddEventOutResponse eventOut, PaymentMehod.EmPaymentMethod method)
        {
            StandardlizeServerName();
            string apiUrl = "";
            if (method == PaymentMehod.EmPaymentMethod.Cash)
            {
                apiUrl = server + "order/cash";
            }
            else
            {
                apiUrl = server + KzParkingv5ApiUrlManagement.PostObjectRoute(KzParkingv5ApiUrlManagement.EmParkingv5ObjectType.PaymentTransaction);
            }
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            var data = new PaymentTransaction
            {
                EventInId = eventOut.eventIn.Id,
                targetId = eventOut.Id,
                targetType = TargetType.EventOut,
                amount = eventOut.remainingCharge,
                DeviceCode = StaticPool.selectedComputer.Id,
                details = new List<PaymentDetail>()
                {
                    new PaymentDetail(){purpose = Purpose.ParkingDay, quantity = eventOut.charge.Day, amount = eventOut.charge.DayAmount, price = eventOut.charge.DayPrice },
                    new PaymentDetail(){purpose = Purpose.ParkingNight, quantity = eventOut.charge.Night, amount = eventOut.charge.NightAmount, price = eventOut.charge.NightPrice },
                    new PaymentDetail(){purpose = Purpose.ParkingNormalCharge, quantity = 1, amount =eventOut.charge.FullDayAmount, price =eventOut.charge.FullDayPrice },
                },
                method = (int)method
            };
            string a = Newtonsoft.Json.JsonConvert.SerializeObject(data);
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, data, headers, null, timeOut, RestSharp.Method.Post);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                PaymentTransaction paymentTransaction = NewtonSoftHelper<PaymentTransaction>.GetBaseResponse(response.Item1);
                return paymentTransaction;
            }
            return null;
        }

        public async Task<Tuple<PaymentTransaction, string>> CheckPaymentAsync(string orderId)
        {
            return await KzParkingv5BaseApi.GetObjectDetailByIdAsync<PaymentTransaction>(KzParkingv5ApiUrlManagement.EmParkingv5ObjectType.PaymentTransaction, orderId);
        }

        public async Task<bool> DeletePaymentByIdAsync(string orderId)
        {
            LogHelper.Log(LogHelper.EmLogType.WARN, LogHelper.EmObjectLogType.System, specailName: "CANCEL ORDER", mo_ta_them: "OrderId: CANCEL ORDER");
            StandardlizeServerName();
            string apiUrl = server + "order" + "/" + orderId;
            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
             {
                 { "Authorization","Bearer " + token  }
             };
            var commitData = new List<CommitData>();
            commitData.Add(new CommitData()
            {
                op = "replace",
                path = "status",
                value = 1
            });
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, commitData, headers, null, timeOut, RestSharp.Method.Patch);
            return true;
        }

        #endregion END PAYMENT

        #region Alarm
        //--ADD--
        public async Task<bool> CreateAlarmAsync(string identityId, string laneId, string plate, EmAbnormalCode abnormalCode,
                                                        string imageKey, bool isLaneIn, string _identityGroupId, string customerId,
                                                        string registerVehicleId, string description)
        {
            StandardlizeServerName();
            string apiUrl = server + KzParkingv5ApiUrlManagement.PostObjectRoute(KzParkingv5ApiUrlManagement.EmParkingv5ObjectType.AbnormalEvent);
            Dictionary<string, string> headers = new Dictionary<string, string>()
                    {
                        { "Authorization","Bearer " + token  }
                    };
            var abnormalEvent = new
            {
                LaneId = laneId,
                identity = new
                {
                    id = identityId,
                    identityGroupId = _identityGroupId,
                },
                PlateNumber = plate,
                Code = abnormalCode,
                FileKeys = new List<string>()
                        {
                            imageKey + (isLaneIn? "_OVERVIEWIN.jpeg" : "_OVERVIEWOUT.jpeg"),
                            imageKey + (isLaneIn ? "_VEHICLEIN.jpeg" : "_VEHICLEOUT.jpeg")
                        },
                Description = description
            };
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, abnormalEvent, headers, null, timeOut, RestSharp.Method.Post);
            string a = Newtonsoft.Json.JsonConvert.SerializeObject(abnormalEvent);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                AbnormalEvent kzBaseResponse = NewtonSoftHelper<AbnormalEvent>.GetBaseResponse(response.Item1);
                return kzBaseResponse != null;
            }
            return false;
        }
        #endregion End Alarm

        #region WAREHOUSE
        public async Task<WarehouseService> CreateWarehouseService(string eventInId, string eventOutId, string plate, EmTransactionType type, bool isPrint = false)
        {

            StandardlizeServerName();
            string apiUrl = server + "warehouse/transaction";
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            WarehouseServiceInput warehouseService = new WarehouseServiceInput()
            {
                type = (int)type,
                plateNumber = plate,
                eventInId = eventInId,
                eventOutId = Guid.Empty,
                PrintPaper = isPrint,
            };

            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, warehouseService, headers, null, timeOut, RestSharp.Method.Post);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                try
                {
                    WarehouseService result = NewtonSoftHelper<WarehouseService>.GetBaseResponse(response.Item1);
                    if (string.IsNullOrEmpty(result.Id))
                    {
                        return null;
                    }
                    return result;
                }
                catch (Exception)
                {
                    return null;
                }
            }
            return null;
        }
        #endregion END WAREHOUSE

        #region EInvoice 
        //--ADD
        public async Task<InvoiceResponse> CreateEinvoice(string eventOutId, bool isSendNow = true, string customerId = "")
        {
            string apiUrl = "";
            StandardlizeServerName();

            apiUrl = server + KzParkingv5ApiUrlManagement.PostObjectRoute(KzParkingv5ApiUrlManagement.EmParkingv5ObjectType.Invoice);

            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            //TimeSpan parkingTime = datetimeOut - datetimeIn;
            var data = new
            {
                targetId = eventOutId,
                send = isSendNow ? 1 : 0,
                provider = (int)EmInvoiceProvider.Viettel,
                TargetType = TargetType.EventOut,
                customerId = customerId,
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
        public async Task<bool> sendPendingEInvoice(string invoiceID)
        {
            StandardlizeServerName();
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            string apiUrl = server + KzParkingv5ApiUrlManagement.PostObjectRoute(KzParkingv5ApiUrlManagement.EmParkingv5ObjectType.Invoice) + "/" + invoiceID + "/resend";
            //var data = new
            //{
            //    targetId = invoiceID,
            //    send = 1,
            //    provider = (int)EmInvoiceProvider.Viettel,
            //};
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, null, headers, null, timeOut, Method.Post);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                var pendingData = NewtonSoftHelper<InvoiceResponse>.GetBaseResponse(response.Item1);
                return pendingData != null && !string.IsNullOrEmpty(pendingData.id);
            }
            return false;
        }

        //--GET
        public async Task<InvoiceFileInfor> GetInvoiceData(string orderId, EmInvoiceProvider provider = EmInvoiceProvider.Viettel)
        {
            // string url = $"http://14.160.26.45:26868/einvoice?provider=65";
            StandardlizeServerName();
            string apiUrl = server + $"invoice/{orderId}/representation";

            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            Dictionary<string, string> parameters = new Dictionary<string, string>()
            {
                { "provider","2"  },
                { "filetType","1"  }
            };

            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, null, headers, parameters, timeOut, Method.Get);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                return NewtonSoftHelper<InvoiceFileInfor>.GetBaseResponse(response.Item1);
            }
            return null;
        }
        public async Task<List<InvoiceResponse>> GetMultipleInvoiceData(DateTime startTime, DateTime endTime, List<string> eventIds, EmInvoiceProvider provider = EmInvoiceProvider.Viettel)
        {
            //string url = $"http://14.160.26.45:26868/invoice/many";
            StandardlizeServerName();
            string apiUrl = server + KzParkingv5ApiUrlManagement.SearchObjectDataRoute(KzParkingv5ApiUrlManagement.EmParkingv5ObjectType.Invoice);

            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            string searchIds = string.Join(",", eventIds);
            var filter = Filter.CreateFilter(new List<FilterModel>()
            {
                new FilterModel("targetId", "GUID", searchIds, "in"),
                new FilterModel("targetType", "TEXT", "EventOut", "eq"),
                new FilterModel("sent", "BOOLEAN", "true", "eq"),
                //new FilterModel("targetId", "BOOLEAN", "true", "eq"),
                //new FilterModel("createdUtc", "DATETIME", startTime.ToUniversalTime().ToString(UTCFormat), "gte"),
                //new FilterModel("createdUtc", "DATETIME", endTime.ToUniversalTime().ToString(UTCFormat), "lte"),
            }, EmMainOperation.and, 0, 10000);
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, filter, headers, null, timeOut, Method.Post);
            if (!string.IsNullOrEmpty(response.Item1))
            {

                return NewtonSoftHelper<KzParkingv5BaseResponse<List<InvoiceResponse>>>.GetBaseResponse(response.Item1)?.data ?? new List<InvoiceResponse>();
            }
            return null;
        }
        public async Task<List<InvoiceResponse>> getPendingEInvoice(DateTime startTime, DateTime endTime)
        {
            //string url = $"http://14.160.26.45:26868/sent-invoice/many";
            StandardlizeServerName();
            string apiUrl = server + "invoice/search";

            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            var filter = Filter.CreateFilter(new List<FilterModel>()
            {
                new FilterModel("sent", "BOOLEAN", "false", "eq"),
                new FilterModel("createdUtc", "DATETIME", startTime.ToUniversalTime().ToString(UTCFormat), "gte"),
                new FilterModel("createdUtc", "DATETIME", endTime.ToUniversalTime().ToString(UTCFormat), "lte"),
            }, EmMainOperation.and, 0, 10000);
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, filter, headers, null, timeOut, Method.Post);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                var pendingData = NewtonSoftHelper<KzParkingv5BaseResponse<List<InvoiceResponse>>>.GetBaseResponse(response.Item1)?.data ?? new List<InvoiceResponse>();
                return pendingData;
            }
            return new List<InvoiceResponse>();
        }
        #endregion End Einvoice

        #region FEE PREVIEW
        public async Task<string> GetFeeCalculate(string dateTimeIn, string dateTimeOut, string identityGroupID)
        {
            StandardlizeServerName();
            string apiUrl = $"{server}charge/calculate";

            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            var data = new
            {
                dateTimeIn = dateTimeIn,
                dateTimeOut = dateTimeOut,
                identityGroupId = identityGroupID,
            };
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, data, headers, null,
                                                                  timeOut, Method.Post);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                try
                {
                    return response.Item1.ToString();
                }
                catch (Exception)
                {
                    return "";
                }
            }
            return "";
        }
        #endregion END FEE PREVIEW
        #endregion END PARKING PROCESS

        #region REPORTING

        #region SUMARY
        /// <summary>
        /// Gửi api lấy thông tin số lượng xe đang trong bãi, số lượng xe vào bãi trong ngày, số lượng xe ra khỏi bãi trong ngày
        /// </summary>
        /// <returns></returns>
        public async Task<SumaryCountEvent> SummaryEventAsync()
        {
            DateTime startTime = new DateTime(DateTime.Now.Year, DateTime.Now.Month, DateTime.Now.Day, 0, 0, 0);
            DateTime endTime = new DateTime(DateTime.Now.Year, DateTime.Now.Month, DateTime.Now.Day, 23, 59, 59);

            int vehicleInPark = await GetVehicleInParkCount();
            int vehicleGotInIn = await GetVehicleGotInInDay(startTime, endTime);
            int vehicleGotOutInDay = await GetVehicleGotOutCountInDay(startTime, endTime);

            return new SumaryCountEvent()
            {
                countAllEventIn = vehicleInPark,
                totalEventOut = vehicleGotOutInDay,
                totalVehicleIn = vehicleGotInIn,
            };
        }

        public async Task<int> GetVehicleInParkCount()
        {
            StandardlizeServerName();
            string apiUrl = server + "reporting/parking/event-in";
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };


            var searchData = new SearchEventIn()
            {
                FromUTC = new DateTime(2015, 1, 1, 0, 0, 0).ToUniversalTime(),
                ToUTC = new DateTime(2099, 1, 1, 0, 0, 0).ToUniversalTime(),
            };
            var data = new
            {
                filter = searchData,
                pageIndex = 0,
                pageSize = 1,
                paging = true
            };

            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, data, headers, null, timeOut, RestSharp.Method.Post);

            if (!string.IsNullOrEmpty(response.Item1))
            {
                var baseResponse = NewtonSoftHelper<KzParkingv5BaseResponse<List<EventInReport>>>.GetBaseResponse(response.Item1);
                if (baseResponse != null)
                {
                    return baseResponse.totalCount;
                }
            }
            return 0;
        }
        public async Task<int> GetVehicleGotInInDay(DateTime startTime, DateTime endTime)
        {
            StandardlizeServerName();
            string apiUrl = server + "reporting/parking/event-in";
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };


            var searchData = new
            {
                FromUTC = startTime.ToUniversalTime(),
                ToUTC = endTime.ToUniversalTime(),
            };
            var data = new
            {
                filter = searchData,
                pageIndex = 0,
                pageSize = 1,
                paging = true
            };

            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, data, headers, null, timeOut, RestSharp.Method.Post);

            if (!string.IsNullOrEmpty(response.Item1))
            {
                var baseResponse = NewtonSoftHelper<KzParkingv5BaseResponse<List<EventInReport>>>.GetBaseResponse(response.Item1);
                if (baseResponse != null)
                {
                    return baseResponse.totalCount;
                }
            }
            return 0;
        }
        public async Task<int> GetVehicleGotOutCountInDay(DateTime startTime, DateTime endTime)
        {
            StandardlizeServerName();
            string apiUrl = server + "reporting/parking/event-out";
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };


            var searchData = new SearchEventIn()
            {
                FromUTC = startTime.ToUniversalTime(),
                ToUTC = endTime.ToUniversalTime(),
            };
            var data = new
            {
                filter = searchData,
                pageIndex = 0,
                pageSize = 1,
                paging = true
            };

            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, data, headers, null, timeOut, RestSharp.Method.Post);

            if (!string.IsNullOrEmpty(response.Item1))
            {
                var baseResponse = NewtonSoftHelper<KzParkingv5BaseResponse<List<EventInReport>>>.GetBaseResponse(response.Item1);
                if (baseResponse != null)
                {
                    return baseResponse.totalCount;
                }
            }
            return 0;
        }

        private async Task<int> GetRecordCountByCmd(string apiUrl, Dictionary<string, string> headers, object data)
        {
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, data, headers, null, timeOut, RestSharp.Method.Post);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                // Deserialize JSON to JObject
                JObject jsonObject = JObject.Parse(response.Item1);

                // Extract columns and rows from JSON
                JArray columns = (JArray)jsonObject["columns"];
                JArray rows = (JArray)jsonObject["rows"];

                if (rows != null)
                {
                    if (rows.Count > 0)
                    {
                        try
                        {
                            string temp = rows[0].ToString();
                            object[] rowData = rows[0].ToObject<object[]>();
                            return int.Parse(rowData[0].ToString());
                        }
                        catch (Exception)
                        {
                            return 0;
                        }
                    }
                    return 0;
                }
            }
            return 0;
        }
        #endregion End SUMARY

        #region EVENT IN

        public async Task<KzParkingv5BaseResponse<List<EventInReport>>> GetEventIns(string keyword, DateTime startTime, DateTime endTime,
                                   string identityGroupId, string vehicleTypeId, string laneId, string user,
                                   int pageIndex = 1, int pageSize = 100)
        {
            StandardlizeServerName();
            string apiUrl = server + "reporting/parking/event-in";
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };


            var searchData = new SearchEventIn()
            {
                keyword = keyword,
                FromUTC = startTime.ToUniversalTime(),
                ToUTC = endTime.ToUniversalTime(),
                identityGroupIds = string.IsNullOrEmpty(identityGroupId) ? new List<string>() : new List<string> { identityGroupId },
                laneIds = string.IsNullOrEmpty(laneId) ? new List<string>() : new List<string> { laneId },
                upns = string.IsNullOrEmpty(user) ? new List<string>() : new List<string> { user },
                Status = EmParkingStatus.Parking,
            };
            var data = new
            {
                filter = searchData,
                pageIndex = pageIndex,
                pageSize = pageSize <= 0 ? 1 : pageSize,
                paging = pageSize <= 0 ? false : true
            };

            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, data, headers, null, 120000, RestSharp.Method.Post);

            if (!string.IsNullOrEmpty(response.Item1))
            {
                var baseResponse = NewtonSoftHelper<KzParkingv5BaseResponse<List<EventInReport>>>.GetBaseResponse(response.Item1);
                //if (baseResponse != null)
                //{
                //    return baseResponse.data;
                //}
                return baseResponse;
            }
            return null;
        }
        #endregion END EVENT IN

        #region EVENT OUT
        public async Task<KzParkingv5BaseResponse<List<EventOutReport>>> GetEventOuts(string keyword, DateTime startTime, DateTime endTime, string identityGroupId, string vehicleTypeId, string laneId, string user, int pageIndex = 1, int pageSize = 10000)
        {
            StandardlizeServerName();
            string apiUrl = server + "reporting/parking/event-out";
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };

            var searchData = new SearchEventIn()
            {
                keyword = keyword,
                FromUTC = startTime.ToUniversalTime(),
                ToUTC = endTime.ToUniversalTime(),
                identityGroupIds = string.IsNullOrEmpty(identityGroupId) ? new List<string>() : new List<string> { identityGroupId },
                laneIds = string.IsNullOrEmpty(laneId) ? new List<string>() : new List<string> { laneId },
                upns = string.IsNullOrEmpty(user) ? new List<string>() : new List<string> { user },
            };
            var data = new
            {
                filter = searchData,
                pageIndex = pageIndex,
                pageSize = pageSize <= 0 ? 1 : pageSize,
                paging = pageSize <= 0 ? false : true
            };
            string a = Newtonsoft.Json.JsonConvert.SerializeObject(data);

            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, data, headers, null, 120000, RestSharp.Method.Post);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                var baseResponse = NewtonSoftHelper<KzParkingv5BaseResponse<List<EventOutReport>>>.GetBaseResponse(response.Item1);
                return baseResponse;
                //if (baseResponse != null)
                //{
                //    return baseResponse.data;
                //}
            }
            return null;
        }


        public class TempObj
        {
            public string id { get; set; }
            public IdentityGroup identityGroup { get; set; }
            public string plateNumber { get; set; }
            public string[] fileKeys { get; set; }
            public bool force { get; set; }
            public bool approve { get; set; }
            public DateTime lastPaymentUtc { get; set; }
            public int charge { get; set; }
            public int discount { get; set; }
            public int paid { get; set; }
            public DateTime createdUtc { get; set; }
            public string createdBy { get; set; }
            public DateTime updatedUtc { get; set; }
            public string note { get; set; }
            public int weight { get; set; }
        }

        public async Task<string> GetLastEventOutIdentityGroupIdByPlateNumber(string plateNumber)
        {
            //return "";
            StandardlizeServerName();


            string apiUrl = server + "event-out/search";
            var filter = Filter.CreateFilter(new List<FilterModel>()
                         {
                             new FilterModel("plateNumber", "TEXT", plateNumber, "eq"),
                         }, EmMainOperation.and, 0, 1);
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };


            //var searchData = new SearchEventIn()
            //{
            //    keyword = plateNumber,
            //    FromUTC = new DateTime(2023, 1, 1, 0, 0, 0).ToUniversalTime(),
            //    ToUTC = new DateTime(2099, 1, 1, 0, 0, 0).ToUniversalTime(),
            ////};
            //var data = new
            //{
            //    filter = filter,
            //    pageIndex = 0,
            //    pageSize = 1,
            //    paging = true,
            //};

            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, filter, headers, null, timeOut, RestSharp.Method.Post);

            if (!string.IsNullOrEmpty(response.Item1))
            {
                var baseResponse = NewtonSoftHelper<KzParkingv5BaseResponse<List<TempObj>>>.GetBaseResponse(response.Item1);
                if (baseResponse != null)
                {
                    if (baseResponse.data.Count == 0)
                    {
                        return string.Empty;
                    }

                    return baseResponse.data[0]?.identityGroup?.Id.ToString();
                }
            }
            return string.Empty;
        }
        #endregion END EVENT OUT

        #region ALARM
        public async Task<DataTable> GetAlarmReport(string keyword, DateTime startTime, DateTime endTime, string identityGroupId, string vehicleTypeId, string laneId, int pageIndex = 1, int pageSize = 10000)
        {
            StandardlizeServerName();
            string apiUrl = server + KzParkingv5ApiUrlManagement.GetBySqlCmd;
            string cmd = string.Empty;
            cmd += "SELECT * FROM index_abnormal_event ";
            cmd += $"WHERE (createdutc Between '{startTime.ToUniversalTime():yyyy-MM-ddTHH:mm:ss.000Z}' AND '{endTime.ToUniversalTime():yyyy-MM-ddTHH:mm:ss.000Z}') ";
            if (!string.IsNullOrEmpty(laneId))
            {
                cmd += $@"AND (laneid = '{laneId.ToUpper()}' or eventinlaneid = '{laneId.ToUpper()}')  ";
            }
            if (!string.IsNullOrEmpty(identityGroupId))
            {
                cmd += $@"AND identitygroupid = '{identityGroupId.ToUpper()}' ";
            }
            if (!string.IsNullOrEmpty(vehicleTypeId))
            {
                cmd += $@"AND vehicletypeid = '{vehicleTypeId.ToUpper()}' ";
            }
            if (!string.IsNullOrEmpty(keyword))
            {
                cmd += $@"AND ((identityname like '%{keyword}%' OR platenumber like '%{keyword}%' OR identitycode like '%{keyword}%') OR
                               (eventinidentityname like '%{keyword}%' OR platenumber like '%{keyword}%' OR eventinidentitycode like '%{keyword}%'))";
            }
            cmd += "ORDER BY createdutc desc";
            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
            {
                { "Authorization","Bearer " + token  }
            };
            var data = new
            {
                query = cmd,
                fetch_size = pageSize,
            };
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, data, headers, null, timeOut, RestSharp.Method.Post);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                // Deserialize JSON to JObject
                JObject jsonObject = JObject.Parse(response.Item1);

                // Extract columns and rows from JSON
                JArray columns = (JArray)jsonObject["columns"];
                JArray rows = (JArray)jsonObject["rows"];

                // Create a new DataTable
                DataTable dataTable = new DataTable();
                if (columns != null)
                {
                    foreach (JObject column in columns)
                    {
                        string columnName = (string)column["name"];
                        string columnType = (string)column["type"];

                        Type type;

                        switch (columnType)
                        {
                            case "text":
                                type = typeof(string);
                                break;
                            case "long":
                                type = typeof(long);
                                break;
                            case "datetime":
                                type = typeof(DateTime);
                                break;
                            default:
                                type = typeof(string);
                                break;
                        }

                        dataTable.Columns.Add(columnName, type);
                    }
                    if (rows != null)
                    {
                        foreach (JArray row in rows)
                        {
                            object[] rowData = row.ToObject<object[]>();
                            dataTable.Rows.Add(rowData);
                        }

                    }
                }
                return dataTable;
            }
            return null;
        }
        #endregion END ALARM

        #endregion END REPORTING

        #region PRIVATE FUNCTION
        private static void StandardlizeServerName()
        {
            if (server[^1] != '/' && server[^1] != '\\')
            {
                server += "/";
            }
        }
        #endregion END PRIVATE FUNCTION
        public static async Task<bool> UpdateNoteOut(string eventId, string note1, string note2, string note3)
        {
            StandardlizeServerName();
            string apiUrl = server + KzParkingv5ApiUrlManagement.PostObjectRoute(KzParkingv5ApiUrlManagement.EmParkingv5ObjectType.EventOut) + "/" + eventId;
            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
                     {
                         { "Authorization","Bearer " + token  }
                     };
            var commitData = new List<CommitData>();
            commitData.Add(new CommitData()
            {
                op = "replace",
                path = "note",
                value = new List<string>() { note1, note2, note3 }
            });
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, commitData, headers, null, timeOut, Method.Patch);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                return true;
            }
            return false;
        }

        public class UpdateData
        {
            public string[] ids { get; set; }
            public List<CommitData> jsonPatchDocument { get; set; }
        }

        public static async Task<bool> DisActiveIdentity(string identityID)
        {
            StandardlizeServerName();
            string apiUrl = server + "Identity";
            //Gửi API
            Dictionary<string, string> headers = new Dictionary<string, string>()
                     {
                         { "Authorization","Bearer " + token  }
                     };
            var commitData = new List<CommitData>();
            commitData.Add(new CommitData()
            {
                op = "replace",
                path = "status",
                value = 1
            });

            var data = new UpdateData()
            {
                ids = new string[] { identityID },
                jsonPatchDocument = commitData,
            };
            var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, data, headers, null, timeOut, Method.Patch);
            if (!string.IsNullOrEmpty(response.Item1))
            {
                return true;
            }
            return false;
        }
    }
}

//public static async Task<bool> UpdateNoteIn(string eventId, string note1, string note2, string note3)
//{
//    StandardlizeServerName();
//    string apiUrl = server + KzParkingv5ApiUrlManagement.PostObjectRoute(KzParkingv5ApiUrlManagement.EmParkingv5ObjectType.EventIn) + "/" + eventId;
//    //Gửi API
//    Dictionary<string, string> headers = new Dictionary<string, string>()
//             {
//                 { "Authorization","Bearer " + token  }
//             };
//    var commitData = new List<CommitData>();
//    commitData.Add(new CommitData()
//    {
//        op = "replace",
//        path = "note",
//        value = new List<string>() { note1, note2, note3 }
//    });
//    var response = await BaseApiHelper.GeneralJsonAPIAsync(apiUrl, commitData, headers, null, timeOut, Method.Patch);
//    if (!string.IsNullOrEmpty(response.Item1))
//    {
//        return true;
//    }
//    return false;
//}
