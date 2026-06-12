using IParkingv8.API.Interfaces;

namespace IParkingv8.API.Implementation.v8.Operatorservice
{
    public class OperatorServicev8(IAuth auth) : IOperatorService
    {
        public IAuth Auth { get; set; } = auth;
        public IOperatorAlarm Alarm { get; set; } = new OperatorAlarmAPI(auth);
        public IOperatorEntry Entry { get; set; } = new OperatorEntryAPI(auth);
        public IOperatorExit Exit { get; set; } = new OperatorExitAPI(auth);
    }
}