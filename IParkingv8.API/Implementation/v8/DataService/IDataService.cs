using iParkingv8.Object.Objects.Parkings;
using IParkingv8.API.Interfaces;
using IParkingv8.API.Objects;
using System.Runtime.CompilerServices;

namespace IParkingv8.API.Implementation.v8.DataService
{
    public interface ISystemConfig
    {
        public IAuth Auth { get; set; }
        Task<BaseReport<SystemConfig>?> GetSystemConfigAsync(int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0,
                                                             [CallerFilePath] string filePath = "",  int pageIndex = 0, int pageSize = Filter.PAGE_SIZE);

        Task<DateTime?> GetServerTime(int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0,
                                                                [CallerFilePath] string filePath = "",  int pageIndex = 0, int pageSize = Filter.PAGE_SIZE);

    }
}
