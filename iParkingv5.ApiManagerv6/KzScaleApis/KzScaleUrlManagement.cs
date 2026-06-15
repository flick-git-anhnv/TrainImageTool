using System;
using System.Collections.Generic;
using System.Text;

namespace iParkingv5.ApiManager.KzScaleApis
{
    public static class KzScaleUrlManagement
    {

        public static string GetCountInDayRoute() => "weighing/count";
        public static string GetAllWeighingFormRoute() => "weighing-type/search";

        public static string CreateWeighingAction() => "weighing";
        public static string GetAllWeighingHistory() => "weighing/search";
        public static string GetReportingWeighingHistory() => "reporting/weighing";
        public static string UpdatePlate(string id) => $"weighing/{id}";
        public static string updateWeighingActionDetailById(string id) => $"weighing/{id}";

        public static string GetWeighingActionDetailsByTrafficIdRoute(string trafficId) => "";
        public static string CreateInvoice() => "create_invoice";

    }
}
