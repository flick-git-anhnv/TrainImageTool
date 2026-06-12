using iParkingv8.Object.Objects.Devices;
using System.Runtime.CompilerServices;

namespace IParkingv8.API.Interfaces
{
    public interface IDeviceService
    {
        IAuth Auth { get; set; }
        Task<DeviceResponse?> GetDeviceDataAsync(int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "");
    }
}
