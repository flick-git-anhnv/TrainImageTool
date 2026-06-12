using iParkingv5.Lpr.LprDetecters.AmericalLprs;
using System.Drawing;
using static iParkingv5.Lpr.LprDetecters.KztekLprs.KztekLPRAIServer;

namespace iParkingv5.Lpr.Objects
{
    public class DetectLprResult
    {
        public string PlateNumber { get; set; } = string.Empty;
        public string OriginalPlate { get; set; } = string.Empty;
        public Box? BoundingBox { get; set; }
        public Image? LprImage { get; set; }
        public Image? VehicleImage { get; set; }
        public DetectVehicleType? vehicleClassify { get; set; }
        public string Description { get; set; } = string.Empty;
        public string Color { get; set; } = string.Empty;
    }
}
