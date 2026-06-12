using static IParkingv8.API.Objects.Filter;

namespace IParkingv8.API.Objects
{
    public class FilterModel
    {
        public string QueryKey { get; set; } = "";
        public string QueryType { get; set; } = "";
        public string QueryValue { get; set; } = "";
        public string Operation { get; set; } = "";

        public FilterModel() { }
        public FilterModel(string queryKey, string queryType, string queryValue, string operation)
        {
            QueryKey = queryKey;
            QueryType = queryType;
            QueryValue = queryValue;
            Operation = operation;
        }
        public FilterModel(EmPageSearchKey queryKey, EmQueryType queryType, string queryValue, EmOperation operation)
        {
            QueryKey = queryKey.ToString();
            QueryType = queryType.ToString();
            QueryValue = queryValue;
            Operation = operation.ToString().Replace("_", "");
        }
        public FilterModel(string queryKey, EmQueryType queryType, string queryValue, EmOperation operation)
        {
            QueryKey = queryKey;
            QueryType = queryType.ToString();
            QueryValue = queryValue;
            Operation = operation.ToString().Replace("_", "");
        }
    }

    public class Filter
    {
        public const int PAGE_SIZE = 20;
        public enum EmMainOperation
        {
            and,
            or,
        }
        public enum EmOperation
        {
            _eq = 0,
            _neq = 1,
            _in = 2,
            _contains = 3,
            _lt = 4,
            _lte = 5,
            _gt = 6,
            _gte = 7,
        }

        public enum EmQueryType
        {
            TEXT = 1,
            NUMBER = 2,
            BOOLEAN = 3,
            GUID = 4,
            DATE = 5,
            DATETIME = 6,
            DATETIME2 = 7,
            NULLABLE_GUID = 8,
            NULLABLE_DATE = 9,
            NULLABLE_DATETIME = 10,
            NULLABLE_DATETIME2 = 11
        }
        public enum EmPageSearchKey
        {
            id,
            name,
            code,
            plateNumber,
            IpAddress,
            ComputerId,
            CreatedUtc,
            LaneId,
            CustomerId,
            identityGroupId
        }

        public class DetailCode
        {
            public const string ERROR_VALIDATION = "ERROR.VALIDATION.FAILED";

            public const string ERROR_VALIDATION_REQUIRED = "ERROR.ENTITY.VALIDATION.FIELD_REQUIRED";

            public const string ERROR_VALIDATION_SOME_ITEMS_DELETED = "ERROR.ENTITY.VALIDATION.SOME_ITEMS_DELETED";

            public const string ERROR_VALIDATION_DUPLICATED = "ERROR.ENTITY.VALIDATION.FIELD_DUPLICATED";

            public const string ERROR_VALIDATION_NOT_FOUND = "ERROR.ENTITY.VALIDATION.FIELD_NOT_FOUND";

            public const string ERROR_ENTITY_NOT_FOUND_SOME_ITEMS_DELETED = "ERROR.ENTITY.NOT_FOUND.SOME_ITEMS_DELETED";

            public const string ERROR_VALIDATION_NOT_ACTIVE = "ERROR.ENTITY.VALIDATION.FIELD_NOT_ACTIVE";

            public const string ERROR_VALIDATION_INVALID = "ERROR.ENTITY.VALIDATION.FIELD_INVALID";
        }

        public static Dictionary<string, List<FilterModel>> CreateFilterItem(List<FilterModel> filterModels, EmMainOperation mainOperation = EmMainOperation.and)
        {
            var filterData = new Dictionary<string, List<FilterModel>>
            {
                { mainOperation.ToString(), filterModels }
            };
            return filterData;
        }

        public static string CreateFilter(List<Dictionary<string, List<FilterModel>>> filterItems, bool isPaging,
                                          EmMainOperation mainOperation = EmMainOperation.and,
                                          int pageIndex = 0, int pageSize = PAGE_SIZE)
        {
            var filterData = new Dictionary<string, List<Dictionary<string, List<FilterModel>>>>
            {
                { mainOperation.ToString(), filterItems }
            };
            var temp = new
            {
                pageIndex,
                pageSize,
                paging = isPaging,
                filter = Newtonsoft.Json.JsonConvert.SerializeObject(filterData),
                fields = new List<object>()
            };
            return Newtonsoft.Json.JsonConvert.SerializeObject(temp);
        }

        public static string CreateFilter(List<FilterModel> filterModels, bool isPaging,
                                          EmMainOperation mainOperation = EmMainOperation.and,
                                          int pageIndex = 0, int pageSize = PAGE_SIZE)
        {
            var filterData = new Dictionary<string, List<FilterModel>>
            {
                { mainOperation.ToString(), filterModels }
            };
            var temp = new
            {
                pageIndex,
                pageSize,
                filter = filterData.Count == 0 ? null : Newtonsoft.Json.JsonConvert.SerializeObject(filterData),
                fields = new List<object>(),
                paging = isPaging
            };
            return Newtonsoft.Json.JsonConvert.SerializeObject(temp);
        }
        public static string CreateVoucherFilter(List<FilterModel> filterModels, bool isPaging, string identityGroupId,
                                   EmMainOperation mainOperation = EmMainOperation.and,
                                   int pageIndex = 0, int pageSize = PAGE_SIZE)
        {
            var filterData = new Dictionary<string, List<FilterModel>>
            {
                { mainOperation.ToString(), filterModels }
            };
            var temp = new
            {
                pageIndex,
                pageSize,
                filter = filterData.Count == 0 ? null : Newtonsoft.Json.JsonConvert.SerializeObject(filterData),
                fields = new List<object>(),
                paging = isPaging,
                identityGroupIds = new List<string>() { identityGroupId }
            };
            return Newtonsoft.Json.JsonConvert.SerializeObject(temp);
        }
        public static string CreateFilter(FilterModel filterModel, bool isPaging, EmMainOperation mainOperation = EmMainOperation.and,
                                          int _pageIndex = 0, int _pageSize = PAGE_SIZE)
        {
            var filterData = new Dictionary<string, List<FilterModel>>
            {
                { mainOperation.ToString(), new List<FilterModel>(){ filterModel } }
            };
            var temp = new
            {
                pageIndex = _pageIndex,
                pageSize = _pageSize,
                paging = isPaging,
                filter = string.IsNullOrEmpty(filterModel.QueryKey) ? null : Newtonsoft.Json.JsonConvert.SerializeObject(filterData),
                fields = new List<object>()
            };
            return Newtonsoft.Json.JsonConvert.SerializeObject(temp);
        }
        public static string CreateFilter(EmPageSearchKey queryKey, EmQueryType pageSearchType,
                                          EmOperation operation, string searchValue, bool isPaging,
                                          EmMainOperation mainOperation = EmMainOperation.and,
                                          int _pageIndex = 0, int _pageSize = PAGE_SIZE)
        {
            var filterData = new Dictionary<string, List<FilterModel>>
            {
                { mainOperation.ToString(), new List<FilterModel>(){ new(queryKey,pageSearchType, searchValue,operation) } }
            };

            string _filter = Newtonsoft.Json.JsonConvert.SerializeObject(filterData);
            var temp = new
            {
                pageIndex = _pageIndex,
                pageSize = _pageSize,
                paging = isPaging,
                filter = _filter,
                fields = new List<object>()
            };
            return Newtonsoft.Json.JsonConvert.SerializeObject(temp);
        }

        public static string CreateAccessKeyFilter(List<Dictionary<string, List<FilterModel>>> filterItems, bool isPaging,
                                 EmMainOperation mainOperation = EmMainOperation.and,
                                 int pageIndex = 0, int pageSize = PAGE_SIZE)
        {
            var filterData = new Dictionary<string, List<Dictionary<string, List<FilterModel>>>>
            {
                { mainOperation.ToString(), filterItems }
            };
            var temp = new
            {
                pageIndex,
                pageSize,
                //filter = filterData,
                filter = Newtonsoft.Json.JsonConvert.SerializeObject(filterData),
                fields = new List<object>(),
                paging = isPaging,
                sorts = "updatedUtc=desc"
            };
            return Newtonsoft.Json.JsonConvert.SerializeObject(temp);
        }
    }
}
