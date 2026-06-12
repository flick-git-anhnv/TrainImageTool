using iParkingv8.Object.Objects.Invoices;
using IParkingv8.API.Objects;
using System.Runtime.CompilerServices;

namespace IParkingv8.API.Interfaces
{
    public interface IInvoiceService
    {
        Task<Tuple<InvoiceData?, string>> CreateInvoiceAsync(string exitId, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "");
        Task<BaseReport<InvoiceData>?> GetInvoicesAsync(string keyword, DateTime startTime, DateTime endTime, string user, int status, bool isPaging = true, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", int pageIndex = 0, int pageSize = 20);
    }
}
