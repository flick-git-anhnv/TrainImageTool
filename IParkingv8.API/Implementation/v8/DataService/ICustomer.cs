using iParkingv8.Object.Objects.Parkings;
using IParkingv8.API.Interfaces;
using IParkingv8.API.Objects;
using System.Runtime.CompilerServices;

namespace IParkingv8.API.Implementation.v8.DataService
{
    public interface ICustomer
    {
        public IAuth Auth { get; set; }
        Task<BaseReport<CustomerDto>?> GetByConditionAsync(string keyword, string customerGroupId, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0,
                                                                   [CallerFilePath] string filePath = "", int pageIndex = 0, int pageSize = Filter.PAGE_SIZE);
        Task<Tuple<CustomerDto?, string>> GetByIdAsync(string id, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0,
                                                                              [CallerFilePath] string filePath = "");
        BaseReport<CustomerDto>? GetByCondition(string keyword, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0,
                                                                   [CallerFilePath] string filePath = "", int pageIndex = 0, int pageSize = Filter.PAGE_SIZE);
        Tuple<CustomerDto?, string> GetById(string id, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "");
        Task<Tuple<CustomerDto?, string>> CreateAsync(CustomerDto customer, int timeOut = 10000, [CallerMemberName] string callerName = "",
                                                                 [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "");

    }
}
