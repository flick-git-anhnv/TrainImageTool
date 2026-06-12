using iParkingv5.Lpr.Objects;
using iParkingv5.LprDetecter.LprDetecters;
using Kztek.Api;
using Kztek.Object;
using Kztek.Tool;
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.Net;
using System.Text;
using System.Threading.Tasks;
using static iParkingv5.LprDetecter.Events.Events;

namespace iParkingv5.Lpr.LprDetecters.AmericalLprs
{
    public class AmericalLpr : ILpr
    {
        public event OnLprDetectComplete? onLprDetectCompleteEvent;
        public event OnLprError? onLprErrorEvent;
        private LprConfig lprConfig;
        public AmericalLpr(LprConfig lprConfig)
        {
            this.lprConfig = lprConfig;
        }

        public async Task<bool> CreateLprAsync(LprConfig lprConfig)
        {
            return true;
        }

        public async Task<DetectLprResult> GetPlateNumberAsync(Image? vehicleImage, bool isCar, Rectangle? detectRegion,
                                                               int rotateAngle, bool isRemoveSpecialKey = true)
        {
            //vehicleImage = Image.FromFile("myImage.jpg");
            var result = new DetectLprResult
            {
                VehicleImage = vehicleImage
            };

            try
            {
                LicensePlateCollection licensePlateList = new LicensePlateCollection();

                if (vehicleImage == null)
                {
                    return result;
                }

                Bitmap bitmapCut = detectRegion != null ? ImageHelper.CropBitmap((Bitmap)vehicleImage, (Rectangle)detectRegion!) : (Bitmap)vehicleImage;
                MemoryStream ms = new MemoryStream();
                bitmapCut.Save(ms, ImageFormat.Jpeg);
                byte[] bytearray = ms.ToArray();

                PlateReaderResult plateReaderResult = await ReadAsync(lprConfig.Url, bytearray, "", true);
                if (plateReaderResult == null)
                {
                    onLprErrorEvent?.Invoke(this);
                }

                licensePlateList = GetBestResult(plateReaderResult, bitmapCut);
                if (licensePlateList.Count > 0)
                {
                    result.LprImage = licensePlateList[0].Bitmap;
                    result.PlateNumber = PlateHelper.StandardlizePlateNumber(licensePlateList[0].Text, false);
                    if (plateReaderResult?.Results != null && plateReaderResult.Results.Count > 0)
                    {
                        result.BoundingBox = plateReaderResult?.Results[0]?.Box;
                    }
                    onLprDetectCompleteEvent?.Invoke(this, new LprDetectEventArgs()
                    {
                        LprImage = licensePlateList[0].Bitmap,
                        OriginalImage = vehicleImage,
                        Result = licensePlateList[0].Text,
                    });
                    return result;
                }
                else
                {
                    onLprDetectCompleteEvent?.Invoke(this, new LprDetectEventArgs()
                    {
                        LprImage = null,
                        OriginalImage = vehicleImage,
                        Result = "",
                    });
                    result.PlateNumber = string.Empty;
                    result.BoundingBox = new Box();
                    result.LprImage = null;
                    return result;
                }
            }
            catch (Exception)
            {
                return result;
            }
        }

        public DetectLprResult GetPlateNumber(Image? vehicleImage, bool isCar, Rectangle? detectRegion,
                                              int rotateAngle, bool isRemoveSpecialKey = true)
        {
            var result = new DetectLprResult
            {
                VehicleImage = vehicleImage
            };

            try
            {
                LicensePlateCollection licensePlateList = new LicensePlateCollection();

                if (vehicleImage == null)
                {
                    return result;
                }

                Bitmap bitmapCut = detectRegion != null ? ImageHelper.CropBitmap((Bitmap)vehicleImage, (Rectangle)detectRegion!) : (Bitmap)vehicleImage;
                MemoryStream ms = new MemoryStream();
                bitmapCut.Save(ms, ImageFormat.Jpeg);
                byte[] bytearray = ms.ToArray();

                PlateReaderResult plateReaderResult = Read(lprConfig.Url, bytearray, "", true);
                if (plateReaderResult == null)
                {
                    onLprErrorEvent?.Invoke(this);
                }

                licensePlateList = GetBestResult(plateReaderResult, bitmapCut);
                if (licensePlateList.Count > 0)
                {
                    result.LprImage = licensePlateList[0].Bitmap;
                    result.PlateNumber = PlateHelper.StandardlizePlateNumber(licensePlateList[0].Text, false);
                    if (plateReaderResult?.Results != null && plateReaderResult.Results.Count > 0)
                    {
                        result.BoundingBox = plateReaderResult?.Results[0]?.Box;
                    }
                    onLprDetectCompleteEvent?.Invoke(this, new LprDetectEventArgs()
                    {
                        LprImage = licensePlateList[0].Bitmap,
                        OriginalImage = vehicleImage,
                        Result = licensePlateList[0].Text,
                    });
                    return result;
                }
                else
                {
                    onLprDetectCompleteEvent?.Invoke(this, new LprDetectEventArgs()
                    {
                        LprImage = null,
                        OriginalImage = vehicleImage,
                        Result = "",
                    });
                    result.PlateNumber = string.Empty;
                    result.BoundingBox = new Box();
                    result.LprImage = null;
                    return result;
                }
            }
            catch (Exception)
            {
                return result;
            }
        }
        #region Private Function
        public static async Task<PlateReaderResult> ReadAsync(string postUrl, byte[] data, string token, bool isRetry)
        {
            try
            {

                PlateReaderResult result = null;
                string formDataBoundary = string.Format("----------{0:N}", Guid.NewGuid());
                string contentType = "multipart/form-data; boundary=" + formDataBoundary;
                byte[] formData = GetMultipartFormData2("--", "", formDataBoundary, data);

                HttpWebRequest request = WebRequest.Create(postUrl) as HttpWebRequest;
                request.ReadWriteTimeout = 2000;
                // Set up the request properties.
                request.Method = "POST";
                request.ContentType = contentType;
                request.UserAgent = ".NET Framework CSharp Client";
                request.CookieContainer = new CookieContainer();
                request.ContentLength = formData.Length;
                request.Headers.Add("Authorization", "Token " + token);

                // Send the form data to the request.
                using (Stream requestStream = request.GetRequestStream())
                {
                    requestStream.Write(formData, 0, formData.Length);
                    requestStream.Close();
                }

                HttpWebResponse response = (HttpWebResponse)(await request.GetResponseAsync());
                if (response.StatusCode == HttpStatusCode.OK)
                {
                    WebHeaderCollection header = response.Headers;
                    var encoding = Encoding.ASCII;
                    using (var reader = new StreamReader(response.GetResponseStream(), encoding))
                    {
                        string responseText = reader.ReadToEnd();
                        try
                        {
                            result = Newtonsoft.Json.JsonConvert.DeserializeObject<PlateReaderResult>(responseText);
                        }
                        catch (Exception ex)
                        {
                        }
                    }
                    return result;
                }
                else
                {
                    if (!isRetry)
                        return null;
                    return await ReadAsync(postUrl, data, token, false);
                }
            }
            catch (Exception ex)
            {
                return null;
            }
        }
        public static PlateReaderResult Read(string postUrl, byte[] data, string token, bool isRetry)
        {
            try
            {

                PlateReaderResult result = null;
                string formDataBoundary = string.Format("----------{0:N}", Guid.NewGuid());
                string contentType = "multipart/form-data; boundary=" + formDataBoundary;
                byte[] formData = GetMultipartFormData2("--", "", formDataBoundary, data);

                HttpWebRequest request = WebRequest.Create(postUrl) as HttpWebRequest;
                request.ReadWriteTimeout = 2000;
                // Set up the request properties.
                request.Method = "POST";
                request.ContentType = contentType;
                request.UserAgent = ".NET Framework CSharp Client";
                request.CookieContainer = new CookieContainer();
                request.ContentLength = formData.Length;
                request.Headers.Add("Authorization", "Token " + token);

                // Send the form data to the request.
                using (Stream requestStream = request.GetRequestStream())
                {
                    requestStream.Write(formData, 0, formData.Length);
                    requestStream.Close();
                }

                HttpWebResponse response = (HttpWebResponse)(request.GetResponse());
                if (response.StatusCode == HttpStatusCode.OK)
                {
                    WebHeaderCollection header = response.Headers;
                    var encoding = Encoding.ASCII;
                    using (var reader = new StreamReader(response.GetResponseStream(), encoding))
                    {
                        string responseText = reader.ReadToEnd();
                        try
                        {
                            result = Newtonsoft.Json.JsonConvert.DeserializeObject<PlateReaderResult>(responseText);
                        }
                        catch (Exception ex)
                        {
                        }
                    }
                    return result;
                }
                else
                {
                    if (!isRetry)
                        return null;
                    return Read(postUrl, data, token, false);
                }
            }
            catch (Exception ex)
            {
                return null;
            }
        }

        public static PlateReaderResult Read(string postUrl, byte[] data, string token)
        {
            try
            {
                PlateReaderResult result = null;
                string formDataBoundary = string.Format("----------{0:N}", Guid.NewGuid());
                string contentType = "multipart/form-data; boundary=" + formDataBoundary;
                byte[] formData = GetMultipartFormData2("--", "", formDataBoundary, data);

                HttpWebRequest request = WebRequest.Create(postUrl) as HttpWebRequest;
                request.ReadWriteTimeout = 2000;
                // Set up the request properties.
                request.Method = "POST";
                request.ContentType = contentType;
                request.UserAgent = ".NET Framework CSharp Client";
                request.CookieContainer = new CookieContainer();
                request.ContentLength = formData.Length;
                request.Headers.Add("Authorization", "Token " + token);

                // Send the form data to the request.
                using (Stream requestStream = request.GetRequestStream())
                {
                    requestStream.Write(formData, 0, formData.Length);
                    requestStream.Close();
                }

                HttpWebResponse response = (HttpWebResponse)(request.GetResponse());
                if (response.StatusCode == HttpStatusCode.OK)
                {
                    WebHeaderCollection header = response.Headers;
                    var encoding = Encoding.ASCII;
                    using (var reader = new StreamReader(response.GetResponseStream(), encoding))
                    {
                        string responseText = reader.ReadToEnd();
                        try
                        {
                            result = Newtonsoft.Json.JsonConvert.DeserializeObject<PlateReaderResult>(responseText);
                        }
                        catch (Exception ex)
                        {
                        }
                    }
                    return result;
                }
                else
                {
                    return null;
                }
            }
            catch (Exception ex)
            {
                return null;
            }
        }

        /// <summary>
        /// Build Multipart Formdata from files and regions.
        /// </summary>
        /// <param name="filePath">File path.</param>
        /// <param name="regions">Regions</param>
        /// <param name="boundary">Boundary.</param>
        /// <returns></returns>
        private static byte[] GetMultipartFormData(string filePath, string regions, string boundary)
        {
            Stream formDataStream = new MemoryStream();
            if (!string.IsNullOrWhiteSpace(filePath))
            {
                // Add just the first part of this param, since we will write the file data directly to the Stream
                string header = string.Format("--{0}\r\nContent-Disposition: form-data; name=\"{1}\"; filename=\"{2}\"\r\nContent-Type: {3}\r\n\r\n",
                    boundary,
                    "upload",
                    filePath,
                    "application/octet-stream");

                formDataStream.Write(Encoding.UTF8.GetBytes(header), 0, Encoding.UTF8.GetByteCount(header));
                byte[] file = File.ReadAllBytes(filePath);
                // Write the file data directly to the Stream, rather than serializing it to a string.
                formDataStream.Write(file, 0, file.Length);
            }

            if (!string.IsNullOrWhiteSpace(regions))
            {
                formDataStream.Write(Encoding.UTF8.GetBytes("\r\n"), 0, Encoding.UTF8.GetByteCount("\r\n"));
                string postData = string.Format("--{0}\r\nContent-Disposition: form-data; name=\"{1}\"\r\n\r\n{2}",
                    boundary,
                    "regions",
                    regions);
                formDataStream.Write(Encoding.UTF8.GetBytes(postData), 0, Encoding.UTF8.GetByteCount(postData));
            }

            // Add the end of the request.  Start with a newline
            string footer = "\r\n--" + boundary + "--\r\n";
            formDataStream.Write(Encoding.UTF8.GetBytes(footer), 0, Encoding.UTF8.GetByteCount(footer));

            // Dump the Stream into a byte[]
            formDataStream.Position = 0;
            byte[] formData = new byte[formDataStream.Length];
            formDataStream.Read(formData, 0, formData.Length);
            formDataStream.Close();

            return formData;
        }

        private static byte[] GetMultipartFormData2(string filePath, string regions, string boundary, byte[] data)
        {
            Stream formDataStream = new MemoryStream();
            if (!string.IsNullOrWhiteSpace(filePath))
            {
                // Add just the first part of this param, since we will write the file data directly to the Stream
                string header = string.Format("--{0}\r\nContent-Disposition: form-data; name=\"{1}\"; filename=\"{2}\"\r\nContent-Type: {3}\r\n\r\n",
                    boundary,
                    "upload",
                    filePath,
                    "application/octet-stream");

                formDataStream.Write(Encoding.UTF8.GetBytes(header), 0, Encoding.UTF8.GetByteCount(header));
                byte[] file = data;//File.ReadAllBytes(filePath);
                // Write the file data directly to the Stream, rather than serializing it to a string.
                formDataStream.Write(file, 0, file.Length);
            }

            if (!string.IsNullOrWhiteSpace(regions))
            {
                formDataStream.Write(Encoding.UTF8.GetBytes("\r\n"), 0, Encoding.UTF8.GetByteCount("\r\n"));
                string postData = string.Format("--{0}\r\nContent-Disposition: form-data; name=\"{1}\"\r\n\r\n{2}",
                    boundary,
                    "regions",
                    regions);
                formDataStream.Write(Encoding.UTF8.GetBytes(postData), 0, Encoding.UTF8.GetByteCount(postData));
            }

            // Add the end of the request.  Start with a newline
            string footer = "\r\n--" + boundary + "--\r\n";
            formDataStream.Write(Encoding.UTF8.GetBytes(footer), 0, Encoding.UTF8.GetByteCount(footer));

            // Dump the Stream into a byte[]
            formDataStream.Position = 0;
            byte[] formData = new byte[formDataStream.Length];
            formDataStream.Read(formData, 0, formData.Length);
            formDataStream.Close();

            return formData;
        }
        private LicensePlateCollection GetBestResult(PlateReaderResult plateReaderResult, Bitmap bmp)
        {
            try
            {
                LicensePlateCollection licensePlateList = new LicensePlateCollection();
                var bestplate = new LicensePlate();

                if (plateReaderResult?.Results != null)
                {
                    foreach (var result in plateReaderResult.Results)
                    {
                        LicensePlate plate = new LicensePlate
                        {
                            Text = result.Plate?.ToUpper() ?? "",
                            Bitmap = bmp.Clone(new Rectangle(result.Box.Xmin, result.Box.Ymin, result.Box.Xmax - result.Box.Xmin, result.Box.Ymax - result.Box.Ymin), PixelFormat.Format24bppRgb),
                            ConfidenceLevel = (float)result.Dscore
                        };

                        if (result.Dscore > bestplate.ConfidenceLevel)
                            bestplate = plate;

                        licensePlateList.Add(plate);
                    }
                    licensePlateList.Maxcalls = plateReaderResult.usage.Max_calls;
                    licensePlateList.QueryTimes = plateReaderResult.usage.Calls;
                }
                // (plateReaderResult.usage.Calls + 5 == plateReaderResult.usage.Max_calls) bestplate.IsMaxcalls = true;

                licensePlateList.Add(bestplate);
                return licensePlateList;
            }
            catch
            {
                return new LicensePlateCollection();
            }
        }

        public async Task<bool> IsValidLprServer()
        {
            string endPoint = this.lprConfig.Url.Replace("alpr", "info");
            var response = await ApiHelper.GeneralJsonAPIAsync(endPoint, null, new Dictionary<string, string>(), new Dictionary<string, string>(), 10000, RestSharp.Method.Get);
            return response.IsSuccess;
        }
        #endregion
    }
}
