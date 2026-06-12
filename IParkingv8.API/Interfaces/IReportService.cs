using IParkingv8.API.Implementation.v8.ReportService;

namespace IParkingv8.API.Interfaces
{
    public interface IReportService
    {
        public IAuth Auth { get; set; }
        public IReportEntry Entry { get; set; }
        public IReportExit Exit { get; set; }
        public IReportRevenue Revenue { get; set; }
        public IReportAlarm Alarm { get; set; }
    }
}
