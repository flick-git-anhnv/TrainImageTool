using System;
using System.Collections.Generic;
using System.Runtime.Serialization;
using System.Text;

namespace iParkingv5.Lpr.LprDetecters.AmericalLprs
{
    [DataContract]
    public class Result
    {

        [DataMember(Name = "box")]  //the bounding Box of Plate
        public Box Box { get; set; }

        [DataMember(Name = "plate")] //the plate Number
        public string Plate { get; set; }

        [DataMember(Name = "score")] //Confidence level for reading the license plate text.
        public double Score { get; set; }

        [DataMember(Name = "dscore")] //Confidence level for plate detection.
        public double Dscore { get; set; }
    }
}
