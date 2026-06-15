using Kztek.Tools;
using System;
using System.Collections.Generic;
using System.Runtime.CompilerServices;
using System.Text;
using static Kztek.Tools.LogHelper;

namespace iParkingv6.ApiManager.KzParkingv3Apis.Responses
{
    public class LoginResponse
    {
        public string identifier { get; set; } = string.Empty;
        public int expireInSeconds { get; set; } = 5000*600;
        public string accessToken { get; set; } = string.Empty;
    }
}
