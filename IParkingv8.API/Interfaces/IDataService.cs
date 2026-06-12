using IParkingv8.API.Implementation.v8.DataService;

namespace IParkingv8.API.Interfaces
{
    public interface IDataService
    {
        public IAuth Auth { get; set; }
        public IAccessKey AccessKey { get; set; }
        public IAccessKeyCollection AccessKeyCollection { get; set; }
        public ICustomer Customer { get; set; }
        public ICustomerCollection CustomerCollection { get; set; }
        public IRegisterVehicle RegisterVehicle { get; set; }
        public IBlackListed BlackListed { get; set; }
        public ISystemConfig SystemConfig { get; set; }
    }
}
