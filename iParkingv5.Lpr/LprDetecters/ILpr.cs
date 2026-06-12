using iParkingv5.Lpr.Objects;
using Kztek.Object;
using System.Drawing;
using System.Threading.Tasks;
using static iParkingv5.LprDetecter.Events.Events;

namespace iParkingv5.LprDetecter.LprDetecters
{
    public interface ILpr
    {
        event OnLprDetectComplete? onLprDetectCompleteEvent;
        event OnLprError? onLprErrorEvent;

        Task<bool> CreateLprAsync(LprConfig lprConfig);
        //DetectLprResult GetPlateNumber(Image? originalImage, bool isCar, Rectangle? detectRegion, out Image? lprImage, int rotateAngle, bool isRemoveSpecialKey);
        Task<DetectLprResult> GetPlateNumberAsync(Image? vehicleImage, bool isCar, Rectangle? detectRegion, int rotateAngle, bool isRemoveSpecialKey = true);
        DetectLprResult GetPlateNumber(Image? vehicleImage, bool isCar, Rectangle? detectRegion, int rotateAngle, bool isRemoveSpecialKey = true);

        //Kiểm tra xem server hiện tại có sẵn sàng sử dụng chưa
        Task<bool> IsValidLprServer();
    }
}
