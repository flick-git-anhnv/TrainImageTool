namespace SlotMonitor;

static class Program
{
    [STAThread]
    static void Main()
    {
        Application.SetHighDpiMode(HighDpiMode.SystemAware);
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);

        Application.ThreadException += (_, args) =>
            MessageBox.Show($"Lỗi không xử lý:\n{args.Exception.Message}",
                "SlotMonitor Error", MessageBoxButtons.OK, MessageBoxIcon.Error);

        Application.Run(new MainForm());
    }
}
