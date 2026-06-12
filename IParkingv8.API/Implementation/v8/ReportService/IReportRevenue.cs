using iParkingv8.Object.Enums.Parkings;
using iParkingv8.Object.Objects.Reports;
using IParkingv8.API.Interfaces;
using IParkingv8.API.Objects;
using System.Runtime.CompilerServices;

namespace IParkingv8.API.Implementation.v8.ReportService
{
    public interface IReportRevenue
    {
        IAuth Auth { get; set; }
        Task<SearchRevenueReportResponse?> GetRevenueDetail(DateTime startTime, DateTime endTime, int category,
                                                            string userId, string collectionId, string laneId,
                                                            int timeout = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true);
        Task<SumarizeTraffic?> GetSumarizeTraffic(int category, DateTime startTime, DateTime endTime, int timeout = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true);

        Task<ShiftHandOverReport> GetShiftHandOverReport(List<string> collectionNames, DateTime startTime, DateTime endTime, string created_by, int timeout = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true);
    }


    public class SumarizeTraffic
    {
        public List<Entry> Entry { get; set; } = [];
        public object[] Exit { get; set; } = [];
        public Dictionary<string, Dictionary<EmVehicleType, int>> SumarizeData()
        {
            var data = new Dictionary<string, Dictionary<EmVehicleType, int>>();
            if (Entry == null || Entry.Count == 0)
                return data;
            foreach (var e in Entry)
            {
                if (!data.ContainsKey(e.Identifier))
                {
                    data[e.Identifier] = new Dictionary<EmVehicleType, int>();
                }

                var vehicleType = Enum.Parse<EmVehicleType>(e.AdditionalIdentifier, true);

                if (!data[e.Identifier].ContainsKey(vehicleType))
                {
                    data[e.Identifier][vehicleType] = 0;
                }
                data[e.Identifier][vehicleType] += e.Count;
            }
            return data;
        }
    }

    public class Entry
    {
        /// <summary>
        /// Tên nhóm
        /// </summary>
        public string Identifier { get; set; } = string.Empty;
        /// <summary>
        /// Loại xe: Xe máy, ô tô,...
        /// </summary>
        public string AdditionalIdentifier { get; set; } = string.Empty;
        /// <summary>
        /// Số lượng vào
        /// </summary>
        public int Count { get; set; }
    }

}
