namespace IParkingv8.API.Implementation.v8
{
    public static class ApiExtension
    {
        #region Private Function
        public static string StandardlizeServerName(this string serverUrl)
        {
            if (serverUrl[^1] != '/' && serverUrl[^1] != '\\')
            {
                serverUrl += "/";
            }
            return serverUrl;
        }
        #endregion End Private Function
    }
}
