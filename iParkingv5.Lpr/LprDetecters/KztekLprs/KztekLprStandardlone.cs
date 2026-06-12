using HawkeyeCS;
using iParkingv5.Lpr.Objects;
using iParkingv5.LprDetecter.LprDetecters;
using Kztek.Object;
using Kztek.Tool;
using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.Threading.Tasks;
using static iParkingv5.LprDetecter.Events.Events;

namespace iParkingv5.Lpr.LprDetecters.KztekLprs
{
    public class KztekLprStandardlone : ILpr
    {
        #region PROPERTIES
        public KztekLpr? lpr;
        #endregion END PROPERTIES
        public event OnLprDetectComplete? onLprDetectCompleteEvent;
        public event OnLprError? onLprErrorEvent;
        public static object lockobj = new object();

        public async Task<bool> CreateLprAsync(LprConfig lprConfig)
        {
            return await Task.Run(() =>
            {
                try
                {
                    lpr = new KztekLpr();
                    return true;
                }
                catch (Exception ex)
                {
                    return false;
                    throw new Exception(ex.Message);
                }
            });
        }
        public async Task<DetectLprResult> GetPlateNumberAsync(Image? vehicleImage, bool isCar, Rectangle? detectRegion, int rotateAngle, bool isRemoveSpecialKey = true)
        {
            var result = new DetectLprResult
            {
                VehicleImage = vehicleImage,
            };
            if (vehicleImage == null) { return result; }
            if (lpr is null) { return result; }

            try
            {
                string plateNumber = string.Empty;
                var lPRObject_Result = new ResultKztekLpr();
                BBox box = new BBox();
                Bitmap bitmapCut = detectRegion != null ? ((Bitmap)vehicleImage).CropBitmap((Rectangle)detectRegion!) :
                                                          ((Bitmap)vehicleImage).CropBitmap(new Rectangle(0, 0, vehicleImage.Width, vehicleImage.Height));

                //Nếu có config rotate thì rotate image ==> nhận dạng
                //Quay với 2 góc rotateAngle và 360 - rotateAngle
                if (rotateAngle > 0)
                {
                    Image? rotateImg = vehicleImage.RotateImage(rotateAngle);
                    var rotateImageData = ImageHelper.GetByteArrayFromImage(rotateImg, ImageFormat.Jpeg);
                    var results = lpr.Recognizer(rotateImageData);
                    if (results != null && results.Count > 0)
                    {
                        plateNumber = results[0].Text;
                        box = results[0].BBox;
                    }


                    if (string.IsNullOrEmpty(plateNumber))
                    {
                        rotateImg = vehicleImage.RotateImage(360 - rotateAngle);
                        results = lpr.Recognizer(rotateImageData);
                        if (results != null && results.Count > 0)
                        {
                            plateNumber = results[0].Text;
                            box = results[0].BBox;
                            //result.LprImage = lPRObject_Result.plateImage;
                        }
                    }
                }

                //Nếu có config góc quay nhưng không đọc được biển || không có config góc quay thì đọc biển theo ảnh gốc
                if (string.IsNullOrEmpty(plateNumber))
                {
                    var imageData = ImageHelper.GetByteArrayFromImage(bitmapCut, ImageFormat.Jpeg);
                    var results = lpr.Recognizer(imageData);
                    if (results != null && results.Count > 0)
                    {
                        plateNumber = results[0].Text;
                        box = results[0].BBox;
                    }
                }
                result.PlateNumber = plateNumber;
                result.LprImage = ImageHelper.CropBitmap((Bitmap)bitmapCut, new Rectangle()
                {
                    X = box.X,
                    Y = box.Y,
                    Width = box.Width,
                    Height = box.Height
                });
                return result;
            }
            catch (Exception ex)
            {
                return result;
            }
        }
        public DetectLprResult GetPlateNumber(Image? vehicleImage, bool isCar, Rectangle? detectRegion, int rotateAngle, bool isRemoveSpecialKey = true)
        {
            var result = new DetectLprResult
            {
                VehicleImage = vehicleImage,
            };
            if (vehicleImage == null) { return result; }
            if (lpr is null) { return result; }

            try
            {
                string plateNumber = string.Empty;
                var lPRObject_Result = new ResultKztekLpr();
                BBox box = new BBox();
                Bitmap bitmapCut = detectRegion != null ? ((Bitmap)vehicleImage).CropBitmap((Rectangle)detectRegion!) :
                                                          ((Bitmap)vehicleImage).CropBitmap(new Rectangle(0, 0, vehicleImage.Width, vehicleImage.Height));

                //Nếu có config rotate thì rotate image ==> nhận dạng
                //Quay với 2 góc rotateAngle và 360 - rotateAngle
                if (rotateAngle > 0)
                {
                    Image? rotateImg = vehicleImage.RotateImage(rotateAngle);
                    var rotateImageData = ImageHelper.GetByteArrayFromImage(rotateImg, ImageFormat.Jpeg);
                    var results = lpr.Recognizer(rotateImageData);
                    if (results != null && results.Count > 0)
                    {
                        plateNumber = results[0].Text;
                        box = results[0].BBox;
                    }


                    if (string.IsNullOrEmpty(plateNumber))
                    {
                        rotateImg = vehicleImage.RotateImage(360 - rotateAngle);
                        results = lpr.Recognizer(rotateImageData);
                        if (results != null && results.Count > 0)
                        {
                            plateNumber = results[0].Text;
                            box = results[0].BBox;
                            //result.LprImage = lPRObject_Result.plateImage;
                        }
                    }
                }

                //Nếu có config góc quay nhưng không đọc được biển || không có config góc quay thì đọc biển theo ảnh gốc
                if (string.IsNullOrEmpty(plateNumber))
                {
                    var imageData = ImageHelper.GetByteArrayFromImage(bitmapCut, ImageFormat.Jpeg);
                    var results = lpr.Recognizer(imageData);
                    if (results != null && results.Count > 0)
                    {
                        plateNumber = results[0].Text;
                        box = results[0].BBox;
                    }
                }
                result.PlateNumber = plateNumber;
                result.LprImage = ImageHelper.CropBitmap((Bitmap)vehicleImage, new Rectangle()
                {
                    X = box.X,
                    Y = box.Y,
                    Width = box.Width,
                    Height = box.Height
                });

                return result;
            }
            catch (Exception ex)
            {
                return result;
            }
        }

        public async Task<bool> IsValidLprServer()
        {
            return lpr != null;
        }
    }
}
