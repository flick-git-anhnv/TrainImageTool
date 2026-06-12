using iParkingv8.Object.Objects.Parkings;
using IParkingv8.API.Interfaces;
using System.Runtime.CompilerServices;

namespace IParkingv8.API.Implementation.v8.DataService
{
    public interface IAccessKeyCollection
    {
        public IAuth Auth { get; set; }
        //CREATE

        //GET
        Task<Tuple<List<Collection>?, string>> GetAllAsync(int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0,
                                                                        [CallerFilePath] string filePath = "", bool isSaveLog = true);
        Tuple<List<Collection>?, string> GetAll(int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0,
                                                               [CallerFilePath] string filePath = "", bool isSaveLog = true);
        //UPDATE
        Task<Tuple<Collection?, string>> GetByIdAsync(string id, int timeOut = 10000, [CallerMemberName] string callerName = "", [CallerLineNumber] int lineNumber = 0,
                                                      [CallerFilePath] string filePath = "", bool isSaveLog = true);

        //DELETE
    }
}
