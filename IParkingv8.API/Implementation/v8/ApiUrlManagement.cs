namespace IParkingv8.API.Implementation.v8
{
    public class ApiUrlManagement
    {
        public enum EmApiObjectType
        {
            ACCESS_KEY,
            ACCESS_KEY_COLLECTIONS,
            ALARMS,
            CUSOMER_COLLECTIONS,
            CUSTOMERS,
            DEVICES,
            DISCOUNTS,
            ENTRIES,
            EXITS,
            TRANSACTIONS,
            VOUCHER_TYPES,
            USERS,
            BLACKLISTED,
            Configs,
        }
        public static string SearchObjectDataRoute(EmApiObjectType type) => GetInitRoute(type) + "/search";
        public static string GetInitRoute(EmApiObjectType objectType)
        {
            switch (objectType)
            {
                case EmApiObjectType.ACCESS_KEY_COLLECTIONS:
                    return "access-key-collections";
                case EmApiObjectType.ACCESS_KEY:
                    return "access-keys";
                case EmApiObjectType.ALARMS:
                    return "alarms";
                case EmApiObjectType.CUSOMER_COLLECTIONS:
                    return "customer-collections";
                case EmApiObjectType.CUSTOMERS:
                    return "customers";
                case EmApiObjectType.DEVICES:
                    return "devices";
                case EmApiObjectType.DISCOUNTS:
                    return "discounts";
                case EmApiObjectType.ENTRIES:
                    return "entries";
                case EmApiObjectType.EXITS:
                    return "exits";
                case EmApiObjectType.TRANSACTIONS:
                    return "transactions";
                case EmApiObjectType.VOUCHER_TYPES:
                    return "voucher-types";
                case EmApiObjectType.USERS:
                    return "users";
                case EmApiObjectType.BLACKLISTED:
                    return "blacklisted";
                case EmApiObjectType.Configs:
                    return "configs";
                default:
                    return objectType.ToString();
            }
        }
    }
}
