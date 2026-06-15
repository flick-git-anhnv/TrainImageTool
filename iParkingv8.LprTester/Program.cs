using iParkingv8.LprTester;
using Kztek.Tool;

namespace iParkingv8.LprTester;

static class Program
{
    [STAThread]
    static void Main()
    {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
            SystemUtils.logger = LoggerFactory.CreateLoggerService(Kztek.Object.EmLogServiceType.OFFLINE_DB, Application.StartupPath);

        Application.Run(new FrmLprTester());
    }
}
