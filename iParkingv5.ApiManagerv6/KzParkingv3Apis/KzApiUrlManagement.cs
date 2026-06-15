using iParkingv5.Objects.Invoices;

namespace iParkingv6.ApiManager.KzParkingv3Apis
{
    public static class KzApiUrlManagement
    {
        public static string BaseRoute => "api";
        #region -- USER -- OK
        public static string PostLoginRoute => "Auth/Login";
        public static string summaryRoute = "Event-Out/Summary";
        public static string CommitOutRoute = "Event-Out";
        public static string DeleteCheckOutRoute(string id) => $"Check-Out/{id}";
        public static string GetIdentityByCodeRoute(string code) => $"Identity/Code/{code}";
        #endregion

        public enum EmObjectType
        {
            Camera,
            Computer,
            ControlUnit,
            Customer,
            CustomerGroup,
            EventIn,
            EventOut,
            Gate,
            Identity,
            IdentityGroup,
            Lane,
            Led,
            RegisteredVehicle,
            VehicleType,
            AbnormalEvent
        }

        public static string GetDataByIdRoute(this EmObjectType emObjectType, string objectId)
        {
            switch (emObjectType)
            {
                case EmObjectType.EventIn:
                    return $"Event-In/{objectId}";

                case EmObjectType.VehicleType:
                    return $"Vehicle-Type/{objectId}";
                case EmObjectType.CustomerGroup:
                    return $"Customer-Group/{objectId}";
                case EmObjectType.IdentityGroup:
                    return $"Identity-Group/{objectId}";
                case EmObjectType.RegisteredVehicle:
                    return $"Registered-Vehicle/{objectId}";
                case EmObjectType.AbnormalEvent:
                    return $"Abnormal-Event/{objectId}";
                case EmObjectType.EventOut:
                    return $"Event-Out/{objectId}";
                default:
                    return $"{emObjectType}/{objectId}";
            }

        }
        public static string GetDataByParamsRoute(this EmObjectType emObjectType)
        {
            switch (emObjectType)
            {
                case EmObjectType.EventIn:
                    return $"Event-In";
                case EmObjectType.EventOut:
                    return $"Event-Out";
                case EmObjectType.VehicleType:
                    return $"Vehicle-Type";
                case EmObjectType.CustomerGroup:
                    return $"Customer-Group";
                case EmObjectType.IdentityGroup:
                    return $"Identity-Group";
                case EmObjectType.AbnormalEvent:
                    return $"Abnormal-Event/";
                case EmObjectType.RegisteredVehicle:
                    return $"Registered-Vehicle";
                default:
                    return $"{emObjectType}";
            }
        }

        public static string CreateRoute(this EmObjectType emObjectType)
        {
            switch (emObjectType)
            {
                case EmObjectType.EventIn:
                    return $"Event-In";
                case EmObjectType.EventOut:
                    return $"Check-Out";
                case EmObjectType.VehicleType:
                    return $"Vehicle-Type/";
                case EmObjectType.CustomerGroup:
                    return $"Customer-Group/";
                case EmObjectType.IdentityGroup:
                    return $"Identity-Group/";
                case EmObjectType.RegisteredVehicle:
                    return $"Registered-Vehicle/";
                case EmObjectType.AbnormalEvent:
                    return $"Abnormal-Event/";
                default:
                    return $"{emObjectType}";
            }
        }
        public static string UpdateRouteById(this EmObjectType emObjectType, string id)
        {
            switch (emObjectType)
            {
                case EmObjectType.EventIn:
                    return $"Event-In/{id}";
                case EmObjectType.EventOut:
                    return $"Event-Out/{id}";
                case EmObjectType.VehicleType:
                    return $"Vehicle-Type/{id}";
                case EmObjectType.CustomerGroup:
                    return $"Customer-Group/{id}";
                case EmObjectType.IdentityGroup:
                    return $"Identity-Group/{id}";
                case EmObjectType.RegisteredVehicle:
                    return $"Registered-Vehicle/{id}";
                case EmObjectType.AbnormalEvent:
                    return $"Abnormal-Event/{id}";
                default:
                    return $"{emObjectType}/{id}";
            }
        }
        public static string DeleteByIdRoute(this EmObjectType emObjectType, string objectId)
        {
            switch (emObjectType)
            {
                case EmObjectType.EventIn:
                    return $"Event-In/{objectId}";
                case EmObjectType.EventOut:
                    return $"Event-Out/{objectId}";
                case EmObjectType.VehicleType:
                    return $"Vehicle-Type/{objectId}";
                case EmObjectType.CustomerGroup:
                    return $"Customer-Group/{objectId}";
                case EmObjectType.IdentityGroup:
                    return $"Identity-Group/{objectId}";
                case EmObjectType.RegisteredVehicle:
                    return $"Registered-Vehicle/{objectId}";
                case EmObjectType.AbnormalEvent:
                    return $"Abnormal-Event/{objectId}";
                default:
                    return $"{emObjectType}/{objectId}";
            }
        }

        #region INVOICE
        public static string createInvoiceRoute(EmInvoiceProvider provider)
        {
            return "einvoice?provider=" + provider.ToString();
        }
        public static string GetInvoiceRoute(EmInvoiceProvider provider)
        {
            return "einvoice?provider=" + provider.ToString();
        }
        #endregion End INVOICE
    }
}
