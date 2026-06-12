using iParkingv5.Lpr.LprDetecters.AmericalLprs;
using System;

namespace iParkingv5.Lpr.LprDetecters.KztekLprs
{
    public class LprResponseModel
    {

        private bool isSuccess = false;
        private int height = 0;
        private int width = 0;
        private string plateNumber = String.Empty;
        private double confidence = 0;
        private string plateImageBase64 = String.Empty;

        public int Height { get => height; set => height = value; }
        public int Width { get => width; set => width = value; }
        public string PlateNumber { get => plateNumber; set => plateNumber = value; }
        public double Confidence { get => confidence; set => confidence = value; }
        public string PlateImageBase64 { get => plateImageBase64; set => plateImageBase64 = value; }
        public string LprImage { get => plateImageBase64; set => plateImageBase64 = value; }
        public bool IsSuccess { get => isSuccess; set => isSuccess = value; }
        public Box? BoundingBox { get; set; }
    }
}
