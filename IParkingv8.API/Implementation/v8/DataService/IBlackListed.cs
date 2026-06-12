using iParkingv8.Object.Enums.ParkingEnums;
using iParkingv8.Object.Objects.Bases;
using iParkingv8.Object.Objects.Parkings;
using System.Runtime.CompilerServices;

namespace IParkingv8.API.Implementation.v8.DataService
{
    public interface IBlackListed
    {
        Task<Tuple<BlackedList?, BaseErrorData?>?> GetByCodeAsync(string code, int timeOut = 10000,
                                                     [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true);
        Tuple<BlackedList?, BaseErrorData?>? GetByCode(string code, int timeOut = 10000,
                                                      [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true);

    }
}
