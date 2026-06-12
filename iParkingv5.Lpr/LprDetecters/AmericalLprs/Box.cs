using System;
using System.Collections.Generic;
using System.Runtime.Serialization;
using System.Text;

namespace iParkingv5.Lpr.LprDetecters.AmericalLprs
{
    [DataContract]
    public class Box
    {

        [DataMember(Name = "xmin")]
        public int Xmin { get; set; }

        [DataMember(Name = "ymin")]
        public int Ymin { get; set; }

        [DataMember(Name = "ymax")]
        public int Ymax { get; set; }

        [DataMember(Name = "xmax")]
        public int Xmax { get; set; }
    }
}
