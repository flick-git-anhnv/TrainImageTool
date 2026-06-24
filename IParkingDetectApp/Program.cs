namespace IParkingDetect;

internal static class Program
{
    [STAThread]  // bắt buộc để FileDialog / COM hoạt động đúng trên WinForms
    internal static void Main()
    {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        Application.Run(new DetectForm());
    }
}
