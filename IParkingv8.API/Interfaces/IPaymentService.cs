using iParkingv8.Object.Objects.Bases;
using iParkingv8.Object.Objects.Payments;
using Kztek.Object;
using System.Runtime.CompilerServices;

namespace IParkingv8.API.Interfaces
{
    public interface IPaymentService
    {
        Task<Transaction?> CreateTransactionAsync(string eventId, long cost, TargetType type, OrderMethod method, OrderProvider provider, string desctiption = "", int timeOut = 10000,
                                                                [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true);

        Task<Transaction?> CheckPaymentStatusAsync(string transactionId, int timeOut = 10000,
                                                   [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true);

        Task<Transaction?> CreateTransactionAsync(PaymentRequest paymentRequest, int timeOut = 10000,
                                                                [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true);

        #region Voucher
        Task<List<Voucher>?> GetVoucherDataAsync(string collectionId, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true);

        Task<List<VoucherApply>?> GetAppliedVoucherDataAsync(string entryId, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true);
        Task<Tuple<VoucherDetail?, BaseErrorData?>?> ApplyVoucherEntryAsync(string voucherData, string entryId, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true);
        Task<Tuple<VoucherAppliedResult?, BaseErrorData?>?> ApplyVoucherExitAsync(string voucherData, string exitId, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true);
        #endregion

        Task<EPassVehicleInfo?> GetEPassVehicleInfoByCodeAsync(string code, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true);
    }
}
