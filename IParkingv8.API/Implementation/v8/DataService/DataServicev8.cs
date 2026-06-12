using IParkingv8.API.Interfaces;

namespace IParkingv8.API.Implementation.v8.DataService
{
    public class DataServicev8(IAuth auth) : IDataService
    {
        public IAuth Auth { get; set; } = auth;
        public IAccessKey AccessKey { get; set; } = new AccessKeyAPI(auth);
        public IAccessKeyCollection AccessKeyCollection { get; set; } = new AccessKeyCollectionAPI(auth);
        public ICustomer Customer { get; set; } = new CustomerAPI(auth);
        public ICustomerCollection CustomerCollection { get; set; } = new CustomerCollectionAPI(auth);
        public IRegisterVehicle RegisterVehicle { get; set; } = new RegisterVehicleAPI(auth);
        public IBlackListed BlackListed { get; set; } = new BlackListedAPI(auth);
        public ISystemConfig SystemConfig { get; set; } = new SystemConfigAPI(auth);
    }
}
