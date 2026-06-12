using iParkingv8.Object.Objects.Users;
using System.Runtime.CompilerServices;

namespace IParkingv8.API.Interfaces
{
    public interface IUserService
    {
        /// <summary>
        /// Sử dụng lấy thông tin khi đăng nhập bằng tài khoản thường
        /// </summary>
        /// <param name="callerName"></param>
        /// <param name="lineNumber"></param>
        /// <param name="filePath"></param>
        /// <returns></returns>
        Task GetUserDetailAsync([CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "");
        Task<Tuple<List<User>, string>> GetUserDataAsync([CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "");

        Task<bool> ChangePassword(string userId, string username, string newPassword);

        /// <summary>
        /// Sử dụng khi lấy thông tin là tài khoản SA
        /// </summary>
        /// <param name="callerName"></param>
        /// <param name="lineNumber"></param>
        /// <param name="filePath"></param>
        /// <returns></returns>
        Task GetClientDetailAsync([CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0, [CallerFilePath] string filePath = "");

    }
}
