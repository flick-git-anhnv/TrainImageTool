using iParkingv8.Object.Enums.Bases;
using iParkingv8.Object.Objects.Events;
using IParkingv8.API.Interfaces;
using System.Runtime.CompilerServices;

namespace IParkingv8.API.Implementation.v8.Operatorservice
{
    public interface IOperatorAlarm
    {
        public IAuth Auth { get; set; }
        #region Alarm
        Task<AbnormalEvent?> CreateAsync(string laneId, string plate, EmAlarmCode abnormalCode, string description, string accessKeyId, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true);
        Task<bool> SaveImageAsync(List<byte> imageData, string alarmId, EmImageType imageType, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "", bool isSaveLog = true);
        #endregion
    }
}
