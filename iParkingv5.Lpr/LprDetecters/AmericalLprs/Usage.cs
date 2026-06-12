using System;
using System.Collections.Generic;
using System.Runtime.Serialization;
using System.Text;

namespace iParkingv5.Lpr.LprDetecters.AmericalLprs
{
    [DataContract]
    public class Usage
    {
        [DataMember(Name = "max_calls")]
        public int Max_calls { get; set; }

        [DataMember(Name = "calls")]
        public int Calls { get; set; }
    }
}
