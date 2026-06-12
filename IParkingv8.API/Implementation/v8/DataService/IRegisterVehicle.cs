using iParkingv8.Object.Enums.Parkings;
using iParkingv8.Object.Objects.Bases;
using iParkingv8.Object.Objects.Parkings;
using IParkingv8.API.Interfaces;
using IParkingv8.API.Objects;
using System.Runtime.CompilerServices;

namespace IParkingv8.API.Implementation.v8.DataService
{
    public interface IRegisterVehicle
    {
        public IAuth Auth { get; set; }
        Task<BaseReport<AccessKey>> GetByConditionAsync(string keyword, string collectionId, EmVehicleType? vehicleType, 
                                                        string customerGroupId, int timeOut = 10000,
                             [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true,
                             int pageIndex = 0, int pageSize = Filter.PAGE_SIZE);
        Task<Tuple<AccessKey?, BaseErrorData?>?> GetByPlateNumberAsync(string plateNumber, int timeOut = 10000,
                             [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true);

        Task<bool> IsBlackListAsync(string plateNumber);
        BaseReport<AccessKey> GetByCondition(string keyword, string collectionId, int timeOut = 10000,
                             [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true,
                             int pageIndex = 0, int pageSize = Filter.PAGE_SIZE);
        Tuple<AccessKey?, BaseErrorData?> GetByPlateNumber(string plateNumber, int timeOut = 10000,
                             [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true);

        bool IsBlackList(string plateNumber);
    }
}
