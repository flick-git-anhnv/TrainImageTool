using iParkingv8.Object.Enums.Bases;
using iParkingv8.Object.Objects.Bases;
using iParkingv8.Object.Objects.Events;
using iParkingv8.Object.Objects.Parkings;
using IParkingv8.API.Interfaces;
using System.Runtime.CompilerServices;

namespace IParkingv8.API.Implementation.v8.Operatorservice
{
    public interface IOperatorExit
    {
        public IAuth Auth { get; set; }
        Task<Tuple<ExitData?, BaseErrorData?>?> CreateAsync(string eventId, string laneId, string accessKeyId, string plateNumber, string collectionId, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true);
        Task<bool> UpdatePlateAsync(string id, string newPlate, string oldPlate, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true);
        Task<bool> UpdateNoteAsync(string id, string note, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true);
        Task<bool> DeleteByIdAsync(string id, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true);
        Task<bool> SaveImageAsync(List<byte> imageData, string entrieId, EmImageType imageType, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true);
        Task<ExitData?> ChangeCollectionAsync(string id, string collectionId, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true);
    }
}
