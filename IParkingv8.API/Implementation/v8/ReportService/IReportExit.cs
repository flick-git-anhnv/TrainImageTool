using iParkingv8.Object.Objects.Events;
using IParkingv8.API.Interfaces;
using IParkingv8.API.Objects;
using System.Runtime.CompilerServices;
using static IParkingv8.API.Objects.Filter;

namespace IParkingv8.API.Implementation.v8.ReportService
{
    public interface IReportExit
    {
        IAuth Auth { get; set; }
        Task<BaseReport<ExitData>?> GetExitDataAsync(string keyword, DateTime startTime, DateTime endTime, string collectionId,
                                                         string vehicleType, string laneId, string user, bool isPaging,
                                                         int pageIndex = 0, int pageSize = PAGE_SIZE, string eventId = "",
                                                         int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true);
        Task<ExitData?> GetExitByAccessKeyIdAsync(string accessId, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true);
        Task<ExitData?> GetExitByIdAsync(string id, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true);
        Task<BaseReport<ExitData>?> GetEventInAndOuts(DateTime startTime, DateTime endTime,
                                                                      bool isPaging, int pageIndex = 1, int pageSize = PAGE_SIZE,
                                                                      int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true);

    }
}
