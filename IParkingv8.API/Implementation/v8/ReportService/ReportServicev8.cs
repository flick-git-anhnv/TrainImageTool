using IParkingv8.API.Interfaces;

namespace IParkingv8.API.Implementation.v8.ReportService
{
    public class ReportServicev8(IAuth auth) : IReportService
    {
        #region Properties
        public IAuth Auth { get; set; } = auth;
        public IReportEntry Entry { get; set; } = new ReportEntry(auth);
        public IReportExit Exit { get; set; } = new ReportExit(auth);
        public IReportRevenue Revenue { get; set; } = new ReportRevenue(auth);
        public IReportAlarm Alarm { get; set; } = new ReportAlarm(auth);
        #endregion
    }
}
