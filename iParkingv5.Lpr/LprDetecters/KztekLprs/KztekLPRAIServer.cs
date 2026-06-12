using iParkingv5.Lpr.LprDetecters.AmericalLprs;
using iParkingv5.Lpr.Objects;
using iParkingv5.LprDetecter.LprDetecters;
using Kztek.Api;
using Kztek.Object;
using Kztek.Tool;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Imaging;
using System.Threading.Tasks;
using static iParkingv5.LprDetecter.Events.Events;

namespace iParkingv5.Lpr.LprDetecters.KztekLprs
{
    public class KztekLPRAIServer : ILpr
    {
        public event OnLprDetectComplete? onLprDetectCompleteEvent;
        public event OnLprError? onLprErrorEvent;
        private LprConfig lprConfig;
        public KztekLPRAIServer(LprConfig lprConfig)
        {
            this.lprConfig = lprConfig;
        }

        public async Task<bool> CreateLprAsync(LprConfig lprConfig)
        {
            this.lprConfig = lprConfig;
            return true;
        }
        public static Bitmap DownscaleFast(Image src, int w, int h)
        {
            var dest = new Bitmap(w, h);

            using (var g = Graphics.FromImage(dest))
            {
                g.InterpolationMode = System.Drawing.Drawing2D.InterpolationMode.NearestNeighbor;
                g.DrawImage(src, 0, 0, w, h);
            }

            return dest;
        }
        public async Task<DetectLprResult> GetPlateNumberAsync(Image? vehicleImage, bool isCar, Rectangle? detectRegion, int rotateAngle, bool isRemoveSpecialKey = true)
        {
            DetectLprResult detectLprResult = new DetectLprResult();
            detectLprResult.VehicleImage = vehicleImage;
            if (vehicleImage == null)
            {
                return detectLprResult;
            }
            //vehicleImage = DownscaleFast(vehicleImage, vehicleImage.Width, vehicleImage.Height);

            var lprRequest = new LprRequest()
            {
                IsCar = isCar,
            };

            Bitmap? bitmapCut = detectRegion != null ? ImageHelper.CropBitmap((Bitmap)vehicleImage, (Rectangle)detectRegion!) : (Bitmap)vehicleImage;
            if (bitmapCut == null)
            {
                bitmapCut = (Bitmap)vehicleImage;
            }
            bitmapCut = (Bitmap)ImageHelper.RotateImage(bitmapCut, rotateAngle);
            var result = ApiHelper.GeneralJsonAPI(this.lprConfig.Url, null,
                                           new Dictionary<string, string>(),
                                           new Dictionary<string, string>() { },
                                           new Dictionary<string, object>() { { "upload", (await ImageHelper.GetByteArrayFromImageAsync(bitmapCut)).ToArray() } },
                                           10000, RestSharp.Method.Post, isSaveLog: false);

            if (!result.IsSuccess || string.IsNullOrEmpty(result.Response))
            {
                return detectLprResult;
            }

            var detectData = Newtonsoft.Json.JsonConvert.DeserializeObject<BaseKztekLprResponse>(result.Response);
            if (detectData is null || detectData.Results.Count == 0)
            {
                return detectLprResult;
            }

          
            detectLprResult.PlateNumber = detectData.Results[0].Plate;
            detectLprResult.vehicleClassify = detectData.Results[0].Vehicle;
            detectLprResult.BoundingBox = detectData.Results[0].Box;
            detectLprResult.Color = detectData.Results[0].Color;
            var box = detectData.Results[0].Box;
            if (box != null)
            {
                var bitmap = ImageHelper.CropBitmap((Bitmap)bitmapCut.Clone(), new Rectangle(box.Xmin, box.Ymin,
                                                       box.Xmax - box.Xmin, box.Ymax - box.Ymin));

                detectLprResult.LprImage = bitmap;
                detectLprResult.VehicleImage = ImageHelper.DrawRect(bitmapCut, box.Xmin, box.Ymin,
                                                                    box.Xmax - box.Xmin, box.Ymax - box.Ymin, Color.Red);

                var vehicleBox = detectLprResult.vehicleClassify?.BoundingBox;
                if (vehicleBox != null)
                {
                    detectLprResult.VehicleImage = ImageHelper.DrawRect(bitmapCut, vehicleBox.Xmin, vehicleBox.Ymin,
                                                          vehicleBox.Xmax - vehicleBox.Xmin, vehicleBox.Ymax - vehicleBox.Ymin, Color.Yellow);
                }
            }

            return detectLprResult;
        }
        public DetectLprResult GetPlateNumber(Image? vehicleImage, bool isCar, Rectangle? detectRegion, int rotateAngle, bool isRemoveSpecialKey = true)
        {
            DetectLprResult detectLprResult = new DetectLprResult
            {
                VehicleImage = vehicleImage
            };
            if (vehicleImage == null)
            {
                return detectLprResult;
            }
            vehicleImage = DownscaleFast(vehicleImage, vehicleImage.Width, vehicleImage.Height);

            var lprRequest = new LprRequest()
            {
                IsCar = isCar,
            };

            Bitmap? bitmapCut = detectRegion != null ? ImageHelper.CropBitmap((Bitmap)vehicleImage, (Rectangle)detectRegion!) : (Bitmap)vehicleImage;
            if (bitmapCut == null)
            {
                bitmapCut = (Bitmap)vehicleImage;
            }

            var result = ApiHelper.GeneralJsonAPI(this.lprConfig.Url, null,
                                           new Dictionary<string, string>(),
                                           new Dictionary<string, string>() { },
                                           new Dictionary<string, object>() { { "upload", ImageHelper.GetByteArrayFromImage(vehicleImage, ImageFormat.Jpeg) } },
                                           10000, RestSharp.Method.Post, isSaveLog: false);

            if (!result.IsSuccess || string.IsNullOrEmpty(result.Response))
            {
                return detectLprResult;
            }

            var detectData = Newtonsoft.Json.JsonConvert.DeserializeObject<BaseKztekLprResponse>(result.Response);
            if (detectData is null || detectData.Results.Count == 0)
            {
                return detectLprResult;
            }

            detectLprResult.PlateNumber = detectData.Results[0].Plate;
            detectLprResult.vehicleClassify = detectData.Results[0].Vehicle;
            detectLprResult.BoundingBox = detectData.Results[0].Box;
            var box = detectData.Results[0].Box;
            if (box != null)
            {
                var bitmap = bitmapCut.Clone(new Rectangle(box.Xmin, box.Ymin,
                                                       box.Xmax - box.Xmin, box.Ymax - box.Ymin),
                                        PixelFormat.Format24bppRgb);

                detectLprResult.LprImage = bitmap;
                detectLprResult.VehicleImage = ImageHelper.DrawRect(bitmapCut, box.Xmin, box.Ymin,
                                                                    box.Xmax - box.Xmin, box.Ymax - box.Ymin, Color.Red);

                var vehicleBox = detectLprResult.vehicleClassify?.BoundingBox;
                if (vehicleBox != null)
                {
                    detectLprResult.VehicleImage = ImageHelper.DrawRect(bitmapCut, vehicleBox.Xmin, vehicleBox.Ymin,
                                                          vehicleBox.Xmax - vehicleBox.Xmin, vehicleBox.Ymax - vehicleBox.Ymin, Color.Yellow);
                }
            }

            return detectLprResult;
            //if (rotateAngle > 0)
            //{
            //    Image rotateImg = ImageHelper.RotateImage(bitmapCut, rotateAngle);
            //    ImageHelper.ImageToBase64(rotateImg, out string base64, out int size);
            //    lprRequest.Base64 = base64;
            //    var result = await ApiHelper.GeneralJsonAPIAsync(this.lprConfig.Url, lprRequest,
            //                                               new Dictionary<string, string>(), new Dictionary<string, string>(),
            //                                               10000, RestSharp.Method.Post, isSaveLog: false);
            //    if (!result.IsSuccess)
            //    {
            //        return detectLprResult;
            //    }
            //    try
            //    {
            //        var lprResponseModels = new List<LprResponseModel>();
            //        try
            //        {
            //            lprResponseModels = Newtonsoft.Json.JsonConvert.DeserializeObject<List<LprResponseModel>>(result.Response);
            //        }
            //        catch (Exception)
            //        {
            //        }
            //        LprResponseModel lprResponseModel = new LprResponseModel();
            //        if (lprResponseModels != null && lprResponseModels.Count > 0)
            //        {
            //            lprResponseModel = lprResponseModels[0];
            //            detectLprResult.PlateNumber = lprResponseModel.PlateNumber;
            //            detectLprResult.OriginalPlate = PlateHelper.StandardlizePlateNumber(lprResponseModel.PlateNumber, isRemoveSpecialKey);
            //            detectLprResult.BoundingBox = lprResponseModel.BoundingBox;
            //            detectLprResult.LprImage = ImageHelper.Base64ToImage(lprResponseModel.PlateImageBase64);
            //        }

            //        if (string.IsNullOrEmpty(detectLprResult.PlateNumber))
            //        {
            //            ImageToBase64(bitmapCut, out base64, out size);
            //            lprRequest.Base64 = base64;
            //            result = await ApiHelper.GeneralJsonAPIAsync(this.lprConfig.Url, lprRequest,
            //                                                      new Dictionary<string, string>(), new Dictionary<string, string>(),
            //                                                      10000, RestSharp.Method.Post, isSaveLog: false);
            //            if (!result.IsSuccess)
            //            {
            //                return detectLprResult;
            //            }
            //            try
            //            {
            //                lprResponseModels = new List<LprResponseModel>();
            //                try
            //                {
            //                    lprResponseModels = Newtonsoft.Json.JsonConvert.DeserializeObject<List<LprResponseModel>>(result.Response);
            //                }
            //                catch (Exception)
            //                {
            //                }
            //                if (lprResponseModels == null || lprResponseModels.Count == 0)
            //                {
            //                    return detectLprResult;
            //                }
            //                lprResponseModel = lprResponseModels[0];
            //                detectLprResult.PlateNumber = lprResponseModel.PlateNumber;
            //                detectLprResult.OriginalPlate = PlateHelper.StandardlizePlateNumber(lprResponseModel.PlateNumber, isRemoveSpecialKey);
            //                detectLprResult.BoundingBox = lprResponseModel.BoundingBox;
            //                detectLprResult.LprImage = ImageHelper.Base64ToImage(lprResponseModel.PlateImageBase64);

            //                return detectLprResult;
            //            }
            //            catch (Exception)
            //            {
            //                return detectLprResult;
            //            }
            //        }

            //        return detectLprResult;
            //    }
            //    catch (Exception ex)
            //    {
            //        return detectLprResult;
            //    }
            //}
            //else
            //{
            //    ImageToBase64(bitmapCut, out string base64, out int size);
            //    lprRequest.Base64 = base64;
            //    var result = await ApiHelper.GeneralJsonAPIAsync(this.lprConfig.Url, lprRequest,
            //                                               new Dictionary<string, string>(), new Dictionary<string, string>(),
            //                                               10000, RestSharp.Method.Post, isSaveLog: false);
            //    if (!result.IsSuccess)
            //    {
            //        return detectLprResult;
            //    }
            //    try
            //    {
            //        var lprResponseModels = Newtonsoft.Json.JsonConvert.DeserializeObject<List<LprResponseModel>>(result.Response);
            //        if (lprResponseModels == null || lprResponseModels.Count == 0)
            //        {
            //            return detectLprResult;
            //        }
            //        var lprResponseModel = lprResponseModels[0];
            //        detectLprResult.PlateNumber = lprResponseModel.PlateNumber;
            //        detectLprResult.OriginalPlate = PlateHelper.StandardlizePlateNumber(lprResponseModel.PlateNumber, isRemoveSpecialKey);
            //        detectLprResult.BoundingBox = lprResponseModel.BoundingBox;
            //        detectLprResult.LprImage = ImageHelper.Base64ToImage(lprResponseModel.PlateImageBase64);

            //        return detectLprResult;
            //    }
            //    catch (Exception)
            //    {
            //        return detectLprResult;
            //    }
            //}
        }

        public async Task<bool> IsValidLprServer()
        {
            string endPoint = this.lprConfig.Url.Replace("alpr", "info");
            var response = await ApiHelper.GeneralJsonAPIAsync(endPoint, null, new Dictionary<string, string>(), new Dictionary<string, string>(), 10000, RestSharp.Method.Get);
            return response.IsSuccess;
        }

        private class BaseKztekLprResponse
        {
            public Usage Usage { get; set; }
            public List<BaseKztekLprResponseDetail> Results { get; set; } = new List<BaseKztekLprResponseDetail>();
        }


        public class BaseKztekLprResponseDetail
        {
            public string Plate { get; set; } = string.Empty;
            public Box? Box { get; set; }
            public DetectVehicleType? Vehicle { get; set; }
            public string Color { get; set; } = string.Empty;
        }

        public class DetectVehicleType
        {
            public string Vehicle_type { get; set; } = string.Empty;
            public float Confidence { get; set; } = 0;
            public Box? BoundingBox { get; set; }
        }
        private class Usage
        {
            public long Calls { get; set; }
            public long Max_calls { get; set; }
        }
    }
}
