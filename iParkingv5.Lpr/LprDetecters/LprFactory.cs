using iParkingv5.Lpr.LprDetecters.AmericalLprs;
using iParkingv5.Lpr.LprDetecters.KztekLprs;
using Kztek.Object;
using static iParkingv5.LprDetecter.Events.Events;
using static Kztek.Object.LprDetecter;

namespace iParkingv5.LprDetecter.LprDetecters
{
    public class LprFactory
    {
        public static ILpr? CreateLprDetecter(LprConfig lprConfig, OnLprDetectComplete? onLprDetectCompleteFunction)
        {
            ILpr? lpr = null;
            switch (lprConfig.LPRDetecterType)
            {
                case EmLprDetecter.KztekLpr:
                    lpr = new KztekLprStandardlone();
                    break;
                case EmLprDetecter.AmericalLpr:
                    lpr = new AmericalLpr(lprConfig);
                    break;
                case EmLprDetecter.KztekLPRAIServer:
                    lpr = new KztekLPRAIServer(lprConfig);
                    break;
                default:
                    return null;
            }
            lpr.onLprDetectCompleteEvent += onLprDetectCompleteFunction;
            return lpr;
        }
    }
}
