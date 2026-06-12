using System;
using System.Collections.Generic;
using System.Drawing;
using System.Text;

namespace iParkingv5.Lpr.Objects
{
    public class LicensePlate
    {
        // Constructor
        public LicensePlate()
        {

        }

        private bool isSuccess = false;

        private string text = "";
        public string Text
        {
            get { return text; }
            set { text = value; }
        }

        private Bitmap? bitmap = null;
        public Bitmap? Bitmap
        {
            get { return bitmap; }
            set { bitmap = value; }
        }

        private float confidenceLevel = -1;
        public float ConfidenceLevel
        {
            get { return confidenceLevel; }
            set { confidenceLevel = value; }
        }

        private int left = -1;
        public int Left
        {
            get { return left; }
            set { left = value; }
        }

        private int top = -1;
        public int Top
        {
            get { return top; }
            set { top = value; }
        }

        private int right = -1;
        public int Right
        {
            get { return right; }
            set { right = value; }
        }

        private int bottom = -1;
        public int Bottom
        {
            get { return bottom; }
            set { bottom = value; }
        }

        private int brightBackground = 0; // 0-Bien thuong, 1-Bien xanh, 2-Bien do
        public int BrightBackground
        {
            get { return brightBackground; }
            set { brightBackground = value; }
        }

        // Mau bien so xe
        private Color colorBackground = Color.White;
        public Color ColorBackground
        {
            get { return colorBackground; }
            set { colorBackground = value; }
        }

        // Mau chu
        private Color colorText = Color.Black;
        public Color ColorText
        {
            get { return colorText; }
            set { colorText = value; }
        }

        // Tinh thanh
        private string province = "";
        public string Province
        {
            get { return province; }
            set { province = value; }
        }

        // Ten loai xe (xe may, xe tai, xe khach duoi 30 cho, xe khach tren 30 cho)
        private string vehicleClassName = "";
        public string VehicleClassName
        {
            get { return vehicleClassName; }
            set { vehicleClassName = value; }
        }

        // Loai xe (0-khong xac dinh, 1-xe may, 2-xe tai, 3-xe khach duoi 30 cho, 4-xe khach tren 30 cho
        private int vehicleClass = 0;
        public int VehicleClass
        {
            get { return vehicleClass; }
            set { vehicleClass = value; }
        }



        public bool IsSuccess { get => isSuccess; set => isSuccess = value; }

    }

}
