using IParkingv8.API.Implementation.v8.Operatorservice;

namespace IParkingv8.API.Interfaces
{
    public interface IOperatorService
    {
        IAuth Auth { get; set; }
        public IOperatorAlarm Alarm { get; set; }
        public IOperatorEntry Entry { get; set; }
        public IOperatorExit Exit { get; set; }
    }
}
