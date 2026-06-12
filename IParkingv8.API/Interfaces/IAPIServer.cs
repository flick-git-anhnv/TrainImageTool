namespace IParkingv8.API.Interfaces
{
    public interface IAPIServer
    {
        /// <summary>
        /// Login (token, ..)
        /// </summary>
        IAuth Auth { get; set; }
        /// <summary>
        /// Thiết bị (cam, bdk, loop...)
        /// </summary>
        IDeviceService DeviceService { get; set; }

        /// <summary>
        /// CRUD Data (thẻ, xe nhóm định danh)
        /// </summary>
        IDataService DataService { get; set; }
        /// <summary>
        /// Vận hành vào ra (Checkin, checkout, update event)
        /// </summary>
        IOperatorService OperatorService { get; set; }
        /// <summary>
        /// Báo cáo 
        /// </summary>
        IReportService ReportingService { get; set; }
        /// <summary>
        /// Thông tin người dùng, phân quyền
        /// </summary>
        IUserService UserService { get; set; }
        /// <summary>
        /// Thanh toán (offline, online, voucher)
        /// </summary>
        IPaymentService PaymentService { get; set; }
        IInvoiceService InvoiceService { get; set; }
    }

}
