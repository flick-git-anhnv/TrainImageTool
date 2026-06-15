namespace iParkingv5.ApiManager.KzParkingv5Apis
{
    public class KzParkingv5ApiUrlManagement
    {
        public enum EmParkingv5ObjectType
        {
            User,
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
            AbnormalEvent,
            PaymentTransaction, 
            Invoice, 
            ResendInvoice
        }

        #region GET
        public static string GetBySqlCmd = "_sql?format=json";
        public static string SearchObjectDataRoute(EmParkingv5ObjectType type) => GetInitRoute(type) + "/search";
        public static string GetObjectDataDetailRoute(EmParkingv5ObjectType type, string id) => GetInitRoute(type) + "/" + id;
        #endregion End GET

        #region ADD
        public static string PostObjectRoute(EmParkingv5ObjectType type)
        {
            return GetInitRoute(type);
        }
        #endregion End ADD

        #region UPDATE

        #endregion End UPDATE

        #region DELETE

        #endregion End Delete

        #region Private Function
        private static string GetInitRoute(EmParkingv5ObjectType objectType)
        {
            switch (objectType)
            {
                case EmParkingv5ObjectType.ControlUnit:
                    return "control-unit";
                case EmParkingv5ObjectType.CustomerGroup:
                    return "customer-group";
                case EmParkingv5ObjectType.EventIn:
                    return "event-in";
                case EmParkingv5ObjectType.EventOut:
                    return "event-out";
                case EmParkingv5ObjectType.IdentityGroup:
                    return "identity-group";
                case EmParkingv5ObjectType.RegisteredVehicle:
                    return "vehicle";
                case EmParkingv5ObjectType.VehicleType:
                    return "vehicle-type";
                case EmParkingv5ObjectType.AbnormalEvent:
                    return "Abnormal-Event";
                case EmParkingv5ObjectType.PaymentTransaction:
                    return "order";
                default:
                    return objectType.ToString();
            }
        }
        #endregion End Private Function
    }
}
