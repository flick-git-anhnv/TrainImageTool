using iParkingv5.Objects.Events;
using System;
using System.Drawing;

namespace iParkingv5.LprDetecter.Events
{
    public class Events
    {
        public delegate void OnLprDetectComplete(object sender, LprDetectEventArgs e);
        public delegate void OnLprError(object sender);
        public class LprDetectEventArgs : EventArgs
        {
            public Image? OriginalImage { get; set; }
            public Image? LprImage { get; set; }
            public string Result { get; set; } = string.Empty;
        }
    }
}
