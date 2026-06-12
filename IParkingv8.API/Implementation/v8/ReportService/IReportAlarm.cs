using iParkingv8.Object.Objects.Events;
using IParkingv8.API.Interfaces;
using IParkingv8.API.Objects;
using System.Runtime.CompilerServices;
using static IParkingv8.API.Objects.Filter;

namespace IParkingv8.API.Implementation.v8.ReportService
{
    public interface IReportAlarm
    {
        IAuth Auth { get; set; }
        Task<BaseReport<AbnormalEvent>?> GetDataAsync(string keyword, DateTime startTime, DateTime endTime, string collectionId,
                                                      string laneId, string user, string customerCollectionId, bool isPaging, int alarmCode = -1,
                                                      int pageIndex = 0, int pageSize = PAGE_SIZE, string eventId = "",
                                                      int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true);
        Task<AbnormalEvent?> GetByIdAsync(string id, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true);
    }
}
