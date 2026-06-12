using iParkingv8.Object.Objects.Systems;
using IParkingv8.API.Implementation.v8.DataService;
using IParkingv8.API.Implementation.v8.Operatorservice;
using IParkingv8.API.Implementation.v8.ReportService;
using IParkingv8.API.Interfaces;

namespace IParkingv8.API.Implementation.v8
{
    public class ApiServerv8 : IAPIServer
    {
        public IAuth Auth { get; set; }
        public IDeviceService DeviceService { get; set; }
        public IReportService ReportingService { get; set; }
        public IOperatorService OperatorService { get; set; }
        public IDataService DataService { get; set; }
        public IUserService UserService { get; set; }
        public IPaymentService PaymentService { get; set; }
        public IInvoiceService InvoiceService { get; set; }

        public ApiServerv8(ServerConfig serverConfig)
        {
            Auth = new AuthServicev8(serverConfig);
            DeviceService = new DeviceServicev8(Auth);
            OperatorService = new OperatorServicev8(Auth);
            UserService = new UserServicev8(Auth);
            DataService = new DataServicev8(Auth);
            this.ReportingService = new ReportServicev8(Auth);
            this.PaymentService = new PaymentService8(Auth);
            this.InvoiceService = new InvoiceService8(Auth);
        }
    }
}
