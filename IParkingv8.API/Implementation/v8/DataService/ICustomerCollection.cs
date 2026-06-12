using iParkingv8.Object.Objects.Parkings;
using IParkingv8.API.Interfaces;
using System.Runtime.CompilerServices;

namespace IParkingv8.API.Implementation.v8.DataService
{
    public interface ICustomerCollection
    {
        public IAuth Auth { get; set; }
        Task<Tuple<List<CustomerGroup>?, string>> GetAllAsync(int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true);
        Tuple<List<CustomerGroup>?, string> GetAll(int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true);
    }
}
