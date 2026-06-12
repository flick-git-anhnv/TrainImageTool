using iParkingv8.Object.Objects.Events;
using IParkingv8.API.Interfaces;
using IParkingv8.API.Objects;
using System.Runtime.CompilerServices;
using static IParkingv8.API.Objects.Filter;

namespace IParkingv8.API.Implementation.v8.ReportService
{
    public interface IReportEntry
    {
        IAuth Auth { get; set; }
        Task<BaseReport<EntryData>?> GetEntryDataAsync(string keyword, DateTime startTime, DateTime endTime, string collectionId,
                                                             string vehicleType, string laneId, string user, string customerCollectionId, bool isPaging,
                                                             int pageIndex = 0, int pageSize = PAGE_SIZE, string eventId = "",
                                                             int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true);
        Task<BaseReport<EntryData>?> GetEntryDataByPlateAsync(string plateNumber, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true);

        Task<EntryData?> GetEntryByAccessKeyIdAsync(string accessId, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true);

        Task<EntryData?> GetEntryByIdAsync(string id, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true);

    }
}
