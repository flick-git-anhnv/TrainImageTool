using System;
using System.Collections.Generic;
using System.Runtime.Serialization;
using System.Text;

namespace iParkingv5.Lpr.LprDetecters.AmericalLprs
{
    [DataContract]
    public class PlateReaderResult
    {

        [DataMember(Name = "processing_time")]
        public double ProcessingTime { get; set; }

        [DataMember(Name = "version")]
        public int Version { get; set; }

        [DataMember(Name = "results")]
        public IList<Result> Results { get; set; }

        [DataMember(Name = "filename")]
        public string Filename { get; set; }

        [DataMember(Name = "usage")]
        public Usage usage { get; set; }
        [DataMember(Name = "error")]
        public string Error { get; set; }
    }
}
