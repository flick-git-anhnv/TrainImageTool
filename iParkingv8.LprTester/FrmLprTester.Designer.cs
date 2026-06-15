using System.Drawing;
using System.Windows.Forms;

namespace iParkingv8.LprTester
{
    partial class FrmLprTester
    {
        private System.ComponentModel.IContainer components = null;

        // Config panel
        private Panel pnlConfig;
        private GroupBox gbConfig;
        private Label lblLprType;
        private ComboBox cboLprType;
        private Label lblUrl;
        private TextBox txtUrl;
        private Label lblUsername;
        private TextBox txtUsername;
        private Label lblPassword;
        private TextBox txtPassword;
        private CheckBox chkDetectVehicle;
        private Button btnConnect;
        private Button btnCheckServer;
        private Label lblServerStatus;

        // Tab control
        private TabControl tabMain;
        private TabPage tabSingle;
        private TabPage tabFolder;

        // ── Tab "Ảnh đơn" ──────────────────────────────────────
        private SplitContainer splitMain;

        // Left panel – image input
        private Panel pnlImageTop;
        private Button btnLoadImage;
        private Label lblImagePath;
        private CheckBox chkIsCar;
        private Label lblRotate;
        private NumericUpDown numRotate;
        private PictureBox picVehicle;
        private Panel pnlDetect;
        private Button btnDetect;
        private ProgressBar progressBar;

        // Right panel – results
        private GroupBox gbResults;
        private TableLayoutPanel tblResults;
        private Label lblPlateLabel;
        private TextBox txtPlate;
        private Label lblOriginalLabel;
        private TextBox txtOriginal;
        private Label lblVehicleTypeLabel;
        private TextBox txtVehicleType;
        private Label lblBboxLabel;
        private TextBox txtBbox;
        private Label lblDescLabel;
        private TextBox txtDescription;
        private PictureBox picLpr;
        private Label lblLprImgLabel;

        // ── Tab "Test thư mục" ─────────────────────────────────
        private Panel pnlFolderTop;
        private Label lblFolderPath;
        private TextBox txtFolderPath;
        private Button btnBrowseFolder;
        private CheckBox chkSubfolders;
        private CheckBox chkFolderIsCar;
        private Label lblFolderRotate;
        private NumericUpDown numFolderRotate;
        private Button btnExportCsv;
        private Button btnStopFolder;
        private Button btnTestFolder;
        private DataGridView dgvResults;
        private Panel pnlFolderBottom;
        private Label lblFolderStatus;
        private Label lblFolderStats;
        private ProgressBar progressFolder;
        private TableLayoutPanel tblFolderContent;
        private Panel pnlPreview;
        private PictureBox picFolderPreview;
        private Label lblPreviewInfo;
        private PictureBox picFolderPlate;
        private Label lblFolderPlateLabel;
        private Panel pnlPreviewActions;
        private Button btnSaveCorrect;
        private Button btnSaveWrong;

        // Log panel
        private Panel pnlLog;
        private Panel pnlLogHeader;
        private Label lblLog;
        private Button btnClearLog;
        private RichTextBox rtbLog;

        protected override void Dispose(bool disposing)
        {
            if (disposing && (components != null))
                components.Dispose();
            base.Dispose(disposing);
        }

        private void InitializeComponent()
        {
            // ── Existing controls ──────────────────────────────
            pnlConfig = new Panel();
            gbConfig = new GroupBox();
            lblLprType = new Label();
            cboLprType = new ComboBox();
            lblUrl = new Label();
            txtUrl = new TextBox();
            chkDetectVehicle = new CheckBox();
            lblUsername = new Label();
            txtUsername = new TextBox();
            lblPassword = new Label();
            txtPassword = new TextBox();
            btnConnect = new Button();
            btnCheckServer = new Button();
            lblServerStatus = new Label();

            tabMain = new TabControl();
            tabSingle = new TabPage();
            tabFolder = new TabPage();

            splitMain = new SplitContainer();
            picVehicle = new PictureBox();
            pnlDetect = new Panel();
            btnDetect = new Button();
            progressBar = new ProgressBar();
            pnlImageTop = new Panel();
            btnLoadImage = new Button();
            lblImagePath = new Label();
            chkIsCar = new CheckBox();
            lblRotate = new Label();
            numRotate = new NumericUpDown();
            gbResults = new GroupBox();
            tblResults = new TableLayoutPanel();
            lblPlateLabel = new Label();
            txtPlate = new TextBox();
            lblOriginalLabel = new Label();
            txtOriginal = new TextBox();
            lblVehicleTypeLabel = new Label();
            txtVehicleType = new TextBox();
            lblBboxLabel = new Label();
            txtBbox = new TextBox();
            lblDescLabel = new Label();
            txtDescription = new TextBox();
            lblLprImgLabel = new Label();
            picLpr = new PictureBox();

            // ── Folder tab controls ────────────────────────────
            pnlFolderTop = new Panel();
            lblFolderPath = new Label();
            txtFolderPath = new TextBox();
            btnBrowseFolder = new Button();
            chkSubfolders = new CheckBox();
            chkFolderIsCar = new CheckBox();
            lblFolderRotate = new Label();
            numFolderRotate = new NumericUpDown();
            btnExportCsv = new Button();
            btnStopFolder = new Button();
            btnTestFolder = new Button();
            dgvResults = new DataGridView();
            pnlFolderBottom = new Panel();
            lblFolderStatus = new Label();
            lblFolderStats = new Label();
            progressFolder = new ProgressBar();
            tblFolderContent = new TableLayoutPanel();
            pnlPreview = new Panel();
            picFolderPreview = new PictureBox();
            lblPreviewInfo = new Label();
            picFolderPlate = new PictureBox();
            lblFolderPlateLabel = new Label();
            pnlPreviewActions = new Panel();
            btnSaveCorrect = new Button();
            btnSaveWrong = new Button();

            pnlLog = new Panel();
            rtbLog = new RichTextBox();
            pnlLogHeader = new Panel();
            lblLog = new Label();
            btnClearLog = new Button();

            // ── SuspendLayout ──────────────────────────────────
            pnlConfig.SuspendLayout();
            gbConfig.SuspendLayout();
            tabMain.SuspendLayout();
            tabSingle.SuspendLayout();
            tabFolder.SuspendLayout();
            ((System.ComponentModel.ISupportInitialize)splitMain).BeginInit();
            splitMain.Panel1.SuspendLayout();
            splitMain.Panel2.SuspendLayout();
            splitMain.SuspendLayout();
            ((System.ComponentModel.ISupportInitialize)picVehicle).BeginInit();
            pnlDetect.SuspendLayout();
            pnlImageTop.SuspendLayout();
            ((System.ComponentModel.ISupportInitialize)numRotate).BeginInit();
            gbResults.SuspendLayout();
            tblResults.SuspendLayout();
            ((System.ComponentModel.ISupportInitialize)picLpr).BeginInit();
            pnlFolderTop.SuspendLayout();
            ((System.ComponentModel.ISupportInitialize)numFolderRotate).BeginInit();
            ((System.ComponentModel.ISupportInitialize)dgvResults).BeginInit();
            pnlFolderBottom.SuspendLayout();
            tblFolderContent.SuspendLayout();
            pnlPreview.SuspendLayout();
            ((System.ComponentModel.ISupportInitialize)picFolderPreview).BeginInit();
            ((System.ComponentModel.ISupportInitialize)picFolderPlate).BeginInit();
            pnlLog.SuspendLayout();
            pnlLogHeader.SuspendLayout();
            SuspendLayout();

            // ── pnlConfig ──────────────────────────────────────
            pnlConfig.Controls.Add(gbConfig);
            pnlConfig.Dock = DockStyle.Top;
            pnlConfig.Location = new Point(0, 0);
            pnlConfig.Name = "pnlConfig";
            pnlConfig.Padding = new Padding(8, 6, 8, 0);
            pnlConfig.Size = new Size(1104, 115);
            pnlConfig.TabIndex = 1;

            // ── gbConfig ───────────────────────────────────────
            gbConfig.Controls.Add(lblLprType);
            gbConfig.Controls.Add(cboLprType);
            gbConfig.Controls.Add(lblUrl);
            gbConfig.Controls.Add(txtUrl);
            gbConfig.Controls.Add(chkDetectVehicle);
            gbConfig.Controls.Add(lblUsername);
            gbConfig.Controls.Add(txtUsername);
            gbConfig.Controls.Add(lblPassword);
            gbConfig.Controls.Add(txtPassword);
            gbConfig.Controls.Add(btnConnect);
            gbConfig.Controls.Add(btnCheckServer);
            gbConfig.Controls.Add(lblServerStatus);
            gbConfig.Dock = DockStyle.Fill;
            gbConfig.Font = new Font("Segoe UI", 9F, FontStyle.Bold);
            gbConfig.Location = new Point(8, 6);
            gbConfig.Name = "gbConfig";
            gbConfig.Padding = new Padding(10, 14, 10, 6);
            gbConfig.Size = new Size(1088, 109);
            gbConfig.TabIndex = 0;
            gbConfig.TabStop = false;
            gbConfig.Text = "Cấu hình LPR";

            lblLprType.Location = new Point(10, 26);
            lblLprType.Name = "lblLprType";
            lblLprType.Size = new Size(80, 20);
            lblLprType.TabIndex = 0;
            lblLprType.Text = "Loại LPR:";
            lblLprType.TextAlign = ContentAlignment.MiddleRight;

            cboLprType.DropDownStyle = ComboBoxStyle.DropDownList;
            cboLprType.Location = new Point(94, 22);
            cboLprType.Name = "cboLprType";
            cboLprType.Size = new Size(200, 23);
            cboLprType.TabIndex = 1;

            lblUrl.Location = new Point(306, 26);
            lblUrl.Name = "lblUrl";
            lblUrl.Size = new Size(38, 20);
            lblUrl.TabIndex = 2;
            lblUrl.Text = "URL:";
            lblUrl.TextAlign = ContentAlignment.MiddleRight;

            txtUrl.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right;
            txtUrl.Location = new Point(348, 22);
            txtUrl.Name = "txtUrl";
            txtUrl.Size = new Size(1268, 23);
            txtUrl.TabIndex = 3;
            txtUrl.Text = "http://192.168.1.100:8088/alpr";

            chkDetectVehicle.Anchor = AnchorStyles.Top | AnchorStyles.Right;
            chkDetectVehicle.Location = new Point(1636, 24);
            chkDetectVehicle.Name = "chkDetectVehicle";
            chkDetectVehicle.Size = new Size(160, 20);
            chkDetectVehicle.TabIndex = 4;
            chkDetectVehicle.Text = "Nhận dạng loại xe";

            lblUsername.Location = new Point(10, 60);
            lblUsername.Name = "lblUsername";
            lblUsername.Size = new Size(80, 20);
            lblUsername.TabIndex = 5;
            lblUsername.Text = "Username:";
            lblUsername.TextAlign = ContentAlignment.MiddleRight;

            txtUsername.Location = new Point(94, 56);
            txtUsername.Name = "txtUsername";
            txtUsername.Size = new Size(120, 23);
            txtUsername.TabIndex = 6;

            lblPassword.Location = new Point(222, 60);
            lblPassword.Name = "lblPassword";
            lblPassword.Size = new Size(80, 20);
            lblPassword.TabIndex = 7;
            lblPassword.Text = "Password:";
            lblPassword.TextAlign = ContentAlignment.MiddleRight;

            txtPassword.Location = new Point(306, 56);
            txtPassword.Name = "txtPassword";
            txtPassword.PasswordChar = '●';
            txtPassword.Size = new Size(120, 23);
            txtPassword.TabIndex = 8;

            btnConnect.Location = new Point(444, 54);
            btnConnect.Name = "btnConnect";
            btnConnect.Size = new Size(100, 28);
            btnConnect.TabIndex = 9;
            btnConnect.Text = "Kết nối";

            btnCheckServer.Location = new Point(552, 54);
            btnCheckServer.Name = "btnCheckServer";
            btnCheckServer.Size = new Size(130, 28);
            btnCheckServer.TabIndex = 10;
            btnCheckServer.Text = "Kiểm tra server";

            lblServerStatus.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right;
            lblServerStatus.Font = new Font("Segoe UI", 9F, FontStyle.Italic);
            lblServerStatus.ForeColor = Color.Gray;
            lblServerStatus.Location = new Point(694, 60);
            lblServerStatus.Name = "lblServerStatus";
            lblServerStatus.Size = new Size(1188, 20);
            lblServerStatus.TabIndex = 11;
            lblServerStatus.Text = "Chưa kết nối";
            lblServerStatus.TextAlign = ContentAlignment.MiddleLeft;

            // ── tabMain ────────────────────────────────────────
            tabMain.Controls.Add(tabSingle);
            tabMain.Controls.Add(tabFolder);
            tabMain.Dock = DockStyle.Fill;
            tabMain.Location = new Point(0, 115);
            tabMain.Name = "tabMain";
            tabMain.SelectedIndex = 0;
            tabMain.Size = new Size(1104, 466);
            tabMain.TabIndex = 0;

            // ── tabSingle ──────────────────────────────────────
            tabSingle.Controls.Add(splitMain);
            tabSingle.Location = new Point(4, 24);
            tabSingle.Name = "tabSingle";
            tabSingle.Padding = new Padding(3);
            tabSingle.Size = new Size(1096, 438);
            tabSingle.TabIndex = 0;
            tabSingle.Text = "Ảnh đơn";

            // ── splitMain (inside tabSingle) ───────────────────
            splitMain.Dock = DockStyle.Fill;
            splitMain.Location = new Point(3, 3);
            splitMain.Name = "splitMain";
            splitMain.Panel1.Controls.Add(picVehicle);
            splitMain.Panel1.Controls.Add(pnlDetect);
            splitMain.Panel1.Controls.Add(progressBar);
            splitMain.Panel1.Controls.Add(pnlImageTop);
            splitMain.Panel2.Controls.Add(gbResults);
            splitMain.Size = new Size(1090, 432);
            splitMain.SplitterDistance = 368;
            splitMain.TabIndex = 0;

            picVehicle.BackColor = Color.FromArgb(40, 40, 40);
            picVehicle.BorderStyle = BorderStyle.FixedSingle;
            picVehicle.Dock = DockStyle.Fill;
            picVehicle.Location = new Point(0, 42);
            picVehicle.Name = "picVehicle";
            picVehicle.Size = new Size(368, 370);
            picVehicle.SizeMode = PictureBoxSizeMode.Zoom;
            picVehicle.TabIndex = 0;
            picVehicle.TabStop = false;

            pnlDetect.Controls.Add(btnDetect);
            pnlDetect.Dock = DockStyle.Bottom;
            pnlDetect.Location = new Point(0, 412);
            pnlDetect.Name = "pnlDetect";
            pnlDetect.Padding = new Padding(4);
            pnlDetect.Size = new Size(368, 50);
            pnlDetect.TabIndex = 1;

            btnDetect.BackColor = Color.SteelBlue;
            btnDetect.Dock = DockStyle.Fill;
            btnDetect.Enabled = false;
            btnDetect.FlatAppearance.BorderSize = 0;
            btnDetect.FlatStyle = FlatStyle.Flat;
            btnDetect.Font = new Font("Segoe UI", 11F, FontStyle.Bold);
            btnDetect.ForeColor = Color.White;
            btnDetect.Location = new Point(4, 4);
            btnDetect.Name = "btnDetect";
            btnDetect.Size = new Size(360, 42);
            btnDetect.TabIndex = 0;
            btnDetect.Text = "Nhận dạng biển số";
            btnDetect.UseVisualStyleBackColor = false;

            progressBar.Dock = DockStyle.Bottom;
            progressBar.Location = new Point(0, 462);
            progressBar.Name = "progressBar";
            progressBar.Size = new Size(368, 4);
            progressBar.TabIndex = 2;
            progressBar.Visible = false;

            pnlImageTop.Controls.Add(btnLoadImage);
            pnlImageTop.Controls.Add(lblImagePath);
            pnlImageTop.Controls.Add(chkIsCar);
            pnlImageTop.Controls.Add(lblRotate);
            pnlImageTop.Controls.Add(numRotate);
            pnlImageTop.Dock = DockStyle.Top;
            pnlImageTop.Location = new Point(0, 0);
            pnlImageTop.Name = "pnlImageTop";
            pnlImageTop.Padding = new Padding(4);
            pnlImageTop.Size = new Size(368, 42);
            pnlImageTop.TabIndex = 3;

            btnLoadImage.Location = new Point(4, 8);
            btnLoadImage.Name = "btnLoadImage";
            btnLoadImage.Size = new Size(90, 28);
            btnLoadImage.TabIndex = 0;
            btnLoadImage.Text = "Tải ảnh...";

            lblImagePath.AutoEllipsis = true;
            lblImagePath.ForeColor = Color.DimGray;
            lblImagePath.Location = new Point(100, 12);
            lblImagePath.Name = "lblImagePath";
            lblImagePath.Size = new Size(200, 20);
            lblImagePath.TabIndex = 1;
            lblImagePath.Text = "(chưa tải ảnh)";

            chkIsCar.Checked = true;
            chkIsCar.CheckState = CheckState.Checked;
            chkIsCar.Location = new Point(305, 10);
            chkIsCar.Name = "chkIsCar";
            chkIsCar.Size = new Size(100, 20);
            chkIsCar.TabIndex = 2;
            chkIsCar.Text = "Ô tô (isCar)";

            lblRotate.Location = new Point(410, 12);
            lblRotate.Name = "lblRotate";
            lblRotate.Size = new Size(70, 20);
            lblRotate.TabIndex = 3;
            lblRotate.Text = "Góc xoay:";

            numRotate.Location = new Point(482, 8);
            numRotate.Maximum = new decimal(new int[] { 360, 0, 0, 0 });
            numRotate.Name = "numRotate";
            numRotate.Size = new Size(60, 23);
            numRotate.TabIndex = 4;

            gbResults.Controls.Add(tblResults);
            gbResults.Dock = DockStyle.Fill;
            gbResults.Font = new Font("Segoe UI", 9F, FontStyle.Bold);
            gbResults.Location = new Point(0, 0);
            gbResults.Name = "gbResults";
            gbResults.Padding = new Padding(10, 14, 10, 8);
            gbResults.Size = new Size(718, 432);
            gbResults.TabIndex = 0;
            gbResults.TabStop = false;
            gbResults.Text = "Kết quả nhận dạng";

            tblResults.ColumnCount = 2;
            tblResults.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 110F));
            tblResults.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100F));
            tblResults.Controls.Add(lblPlateLabel, 0, 0);
            tblResults.Controls.Add(txtPlate, 1, 0);
            tblResults.Controls.Add(lblOriginalLabel, 0, 1);
            tblResults.Controls.Add(txtOriginal, 1, 1);
            tblResults.Controls.Add(lblVehicleTypeLabel, 0, 2);
            tblResults.Controls.Add(txtVehicleType, 1, 2);
            tblResults.Controls.Add(lblBboxLabel, 0, 3);
            tblResults.Controls.Add(txtBbox, 1, 3);
            tblResults.Controls.Add(lblDescLabel, 0, 4);
            tblResults.Controls.Add(txtDescription, 1, 4);
            tblResults.Controls.Add(lblLprImgLabel, 0, 5);
            tblResults.Controls.Add(picLpr, 0, 6);
            tblResults.Dock = DockStyle.Fill;
            tblResults.Location = new Point(10, 30);
            tblResults.Name = "tblResults";
            tblResults.RowCount = 7;
            tblResults.RowStyles.Add(new RowStyle(SizeType.Absolute, 32F));
            tblResults.RowStyles.Add(new RowStyle(SizeType.Absolute, 32F));
            tblResults.RowStyles.Add(new RowStyle(SizeType.Absolute, 32F));
            tblResults.RowStyles.Add(new RowStyle(SizeType.Absolute, 32F));
            tblResults.RowStyles.Add(new RowStyle(SizeType.Absolute, 32F));
            tblResults.RowStyles.Add(new RowStyle(SizeType.Absolute, 32F));
            tblResults.RowStyles.Add(new RowStyle(SizeType.Percent, 100F));
            tblResults.Size = new Size(698, 410);
            tblResults.TabIndex = 0;

            lblPlateLabel.Dock = DockStyle.Fill;
            lblPlateLabel.Font = new Font("Segoe UI", 9F, FontStyle.Bold);
            lblPlateLabel.Location = new Point(3, 0);
            lblPlateLabel.Name = "lblPlateLabel";
            lblPlateLabel.Size = new Size(104, 32);
            lblPlateLabel.TabIndex = 0;
            lblPlateLabel.Text = "Biển số:";
            lblPlateLabel.TextAlign = ContentAlignment.MiddleRight;

            txtPlate.Dock = DockStyle.Fill;
            txtPlate.Font = new Font("Segoe UI", 16F, FontStyle.Bold);
            txtPlate.Location = new Point(113, 3);
            txtPlate.Name = "txtPlate";
            txtPlate.ReadOnly = true;
            txtPlate.Size = new Size(582, 36);
            txtPlate.TabIndex = 1;
            txtPlate.TextAlign = HorizontalAlignment.Center;

            lblOriginalLabel.Dock = DockStyle.Fill;
            lblOriginalLabel.Font = new Font("Segoe UI", 9F, FontStyle.Bold);
            lblOriginalLabel.Location = new Point(3, 32);
            lblOriginalLabel.Name = "lblOriginalLabel";
            lblOriginalLabel.Size = new Size(104, 32);
            lblOriginalLabel.TabIndex = 2;
            lblOriginalLabel.Text = "Gốc (raw):";
            lblOriginalLabel.TextAlign = ContentAlignment.MiddleRight;

            txtOriginal.Dock = DockStyle.Fill;
            txtOriginal.Location = new Point(113, 35);
            txtOriginal.Name = "txtOriginal";
            txtOriginal.ReadOnly = true;
            txtOriginal.Size = new Size(582, 23);
            txtOriginal.TabIndex = 3;

            lblVehicleTypeLabel.Dock = DockStyle.Fill;
            lblVehicleTypeLabel.Font = new Font("Segoe UI", 9F, FontStyle.Bold);
            lblVehicleTypeLabel.Location = new Point(3, 64);
            lblVehicleTypeLabel.Name = "lblVehicleTypeLabel";
            lblVehicleTypeLabel.Size = new Size(104, 32);
            lblVehicleTypeLabel.TabIndex = 4;
            lblVehicleTypeLabel.Text = "Loại xe:";
            lblVehicleTypeLabel.TextAlign = ContentAlignment.MiddleRight;

            txtVehicleType.Dock = DockStyle.Fill;
            txtVehicleType.Location = new Point(113, 67);
            txtVehicleType.Name = "txtVehicleType";
            txtVehicleType.ReadOnly = true;
            txtVehicleType.Size = new Size(582, 23);
            txtVehicleType.TabIndex = 5;

            lblBboxLabel.Dock = DockStyle.Fill;
            lblBboxLabel.Font = new Font("Segoe UI", 9F, FontStyle.Bold);
            lblBboxLabel.Location = new Point(3, 96);
            lblBboxLabel.Name = "lblBboxLabel";
            lblBboxLabel.Size = new Size(104, 32);
            lblBboxLabel.TabIndex = 6;
            lblBboxLabel.Text = "Bounding box:";
            lblBboxLabel.TextAlign = ContentAlignment.MiddleRight;

            txtBbox.Dock = DockStyle.Fill;
            txtBbox.Location = new Point(113, 99);
            txtBbox.Name = "txtBbox";
            txtBbox.ReadOnly = true;
            txtBbox.Size = new Size(582, 23);
            txtBbox.TabIndex = 7;

            lblDescLabel.Dock = DockStyle.Fill;
            lblDescLabel.Font = new Font("Segoe UI", 9F, FontStyle.Bold);
            lblDescLabel.Location = new Point(3, 128);
            lblDescLabel.Name = "lblDescLabel";
            lblDescLabel.Size = new Size(104, 32);
            lblDescLabel.TabIndex = 8;
            lblDescLabel.Text = "Màu biển:";
            lblDescLabel.TextAlign = ContentAlignment.MiddleRight;

            txtDescription.Dock = DockStyle.Fill;
            txtDescription.Location = new Point(113, 131);
            txtDescription.Name = "txtDescription";
            txtDescription.ReadOnly = true;
            txtDescription.Size = new Size(582, 23);
            txtDescription.TabIndex = 9;

            lblLprImgLabel.Dock = DockStyle.Fill;
            lblLprImgLabel.Font = new Font("Segoe UI", 9F, FontStyle.Bold);
            lblLprImgLabel.Location = new Point(3, 160);
            lblLprImgLabel.Name = "lblLprImgLabel";
            lblLprImgLabel.Size = new Size(104, 32);
            lblLprImgLabel.TabIndex = 10;
            lblLprImgLabel.Text = "Ảnh biển:";
            lblLprImgLabel.TextAlign = ContentAlignment.MiddleRight;

            picLpr.BackColor = Color.FromArgb(240, 240, 240);
            picLpr.BorderStyle = BorderStyle.FixedSingle;
            tblResults.SetColumnSpan(picLpr, 2);
            picLpr.Dock = DockStyle.Fill;
            picLpr.Location = new Point(3, 195);
            picLpr.Name = "picLpr";
            picLpr.Size = new Size(692, 212);
            picLpr.SizeMode = PictureBoxSizeMode.Zoom;
            picLpr.TabIndex = 11;
            picLpr.TabStop = false;

            // ── tabFolder ──────────────────────────────────────
            // Dock order (highest index docks first): Top → Bottom → Fill
            tabFolder.Controls.Add(tblFolderContent);
            tabFolder.Controls.Add(pnlFolderBottom);
            tabFolder.Controls.Add(pnlFolderTop);
            tabFolder.Location = new Point(4, 24);
            tabFolder.Name = "tabFolder";
            tabFolder.Padding = new Padding(3);
            tabFolder.Size = new Size(1096, 438);
            tabFolder.TabIndex = 1;
            tabFolder.Text = "Test thư mục";

            // ── pnlFolderTop ───────────────────────────────────
            pnlFolderTop.Controls.Add(lblFolderPath);
            pnlFolderTop.Controls.Add(txtFolderPath);
            pnlFolderTop.Controls.Add(btnBrowseFolder);
            pnlFolderTop.Controls.Add(chkSubfolders);
            pnlFolderTop.Controls.Add(chkFolderIsCar);
            pnlFolderTop.Controls.Add(lblFolderRotate);
            pnlFolderTop.Controls.Add(numFolderRotate);
            pnlFolderTop.Controls.Add(btnExportCsv);
            pnlFolderTop.Controls.Add(btnStopFolder);
            pnlFolderTop.Controls.Add(btnTestFolder);
            pnlFolderTop.Dock = DockStyle.Top;
            pnlFolderTop.Location = new Point(3, 3);
            pnlFolderTop.Name = "pnlFolderTop";
            pnlFolderTop.Size = new Size(1090, 78);

            lblFolderPath.Location = new Point(8, 12);
            lblFolderPath.Name = "lblFolderPath";
            lblFolderPath.Size = new Size(70, 20);
            lblFolderPath.TabIndex = 0;
            lblFolderPath.Text = "Thư mục:";
            lblFolderPath.TextAlign = ContentAlignment.MiddleRight;

            txtFolderPath.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right;
            txtFolderPath.Location = new Point(82, 10);
            txtFolderPath.Name = "txtFolderPath";
            txtFolderPath.Size = new Size(896, 23);
            txtFolderPath.TabIndex = 0;

            btnBrowseFolder.Anchor = AnchorStyles.Top | AnchorStyles.Right;
            btnBrowseFolder.Location = new Point(986, 8);
            btnBrowseFolder.Name = "btnBrowseFolder";
            btnBrowseFolder.Size = new Size(96, 28);
            btnBrowseFolder.TabIndex = 1;
            btnBrowseFolder.Text = "Duyệt...";

            chkSubfolders.Location = new Point(8, 48);
            chkSubfolders.Name = "chkSubfolders";
            chkSubfolders.Size = new Size(155, 22);
            chkSubfolders.TabIndex = 2;
            chkSubfolders.Text = "Bao gồm sub-folder";

            chkFolderIsCar.Checked = true;
            chkFolderIsCar.CheckState = CheckState.Checked;
            chkFolderIsCar.Location = new Point(170, 48);
            chkFolderIsCar.Name = "chkFolderIsCar";
            chkFolderIsCar.Size = new Size(100, 22);
            chkFolderIsCar.TabIndex = 3;
            chkFolderIsCar.Text = "Ô tô (isCar)";

            lblFolderRotate.Location = new Point(276, 50);
            lblFolderRotate.Name = "lblFolderRotate";
            lblFolderRotate.Size = new Size(68, 20);
            lblFolderRotate.TabIndex = 4;
            lblFolderRotate.Text = "Góc xoay:";

            numFolderRotate.Location = new Point(348, 47);
            numFolderRotate.Maximum = new decimal(new int[] { 360, 0, 0, 0 });
            numFolderRotate.Name = "numFolderRotate";
            numFolderRotate.Size = new Size(60, 23);
            numFolderRotate.TabIndex = 5;

            btnExportCsv.Anchor = AnchorStyles.Top | AnchorStyles.Right;
            btnExportCsv.Location = new Point(782, 44);
            btnExportCsv.Name = "btnExportCsv";
            btnExportCsv.Size = new Size(96, 28);
            btnExportCsv.TabIndex = 6;
            btnExportCsv.Text = "Xuất CSV";

            btnStopFolder.Anchor = AnchorStyles.Top | AnchorStyles.Right;
            btnStopFolder.BackColor = Color.Salmon;
            btnStopFolder.Enabled = false;
            btnStopFolder.FlatAppearance.BorderSize = 0;
            btnStopFolder.FlatStyle = FlatStyle.Flat;
            btnStopFolder.Font = new Font("Segoe UI", 9F, FontStyle.Bold);
            btnStopFolder.ForeColor = Color.White;
            btnStopFolder.Location = new Point(886, 44);
            btnStopFolder.Name = "btnStopFolder";
            btnStopFolder.Size = new Size(90, 28);
            btnStopFolder.TabIndex = 7;
            btnStopFolder.Text = "Dừng";
            btnStopFolder.UseVisualStyleBackColor = false;

            btnTestFolder.Anchor = AnchorStyles.Top | AnchorStyles.Right;
            btnTestFolder.BackColor = Color.SeaGreen;
            btnTestFolder.FlatAppearance.BorderSize = 0;
            btnTestFolder.FlatStyle = FlatStyle.Flat;
            btnTestFolder.Font = new Font("Segoe UI", 9F, FontStyle.Bold);
            btnTestFolder.ForeColor = Color.White;
            btnTestFolder.Location = new Point(984, 44);
            btnTestFolder.Name = "btnTestFolder";
            btnTestFolder.Size = new Size(98, 28);
            btnTestFolder.TabIndex = 8;
            btnTestFolder.Text = "Bắt đầu test";
            btnTestFolder.UseVisualStyleBackColor = false;

            // ── tblFolderContent (TableLayoutPanel, Dock=Fill) ─
            tblFolderContent.ColumnCount = 2;
            tblFolderContent.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100F));
            tblFolderContent.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 340F));
            tblFolderContent.Controls.Add(dgvResults, 0, 0);
            tblFolderContent.Controls.Add(pnlPreview, 1, 0);
            tblFolderContent.Dock = DockStyle.Fill;
            tblFolderContent.Location = new Point(3, 81);
            tblFolderContent.Name = "tblFolderContent";
            tblFolderContent.RowCount = 1;
            tblFolderContent.RowStyles.Add(new RowStyle(SizeType.Percent, 100F));
            tblFolderContent.Size = new Size(1090, 309);
            tblFolderContent.TabIndex = 2;

            // ── pnlPreview ─────────────────────────────────────
            pnlPreview.Controls.Add(picFolderPreview);
            pnlPreview.Controls.Add(lblPreviewInfo);
            pnlPreview.Controls.Add(lblFolderPlateLabel);
            pnlPreview.Controls.Add(picFolderPlate);
            pnlPreview.Controls.Add(pnlPreviewActions);
            pnlPreview.Dock = DockStyle.Fill;
            pnlPreview.Location = new Point(750, 0);
            pnlPreview.Name = "pnlPreview";
            pnlPreview.Size = new Size(340, 309);
            pnlPreview.TabIndex = 1;

            // ── lblPreviewInfo ─────────────────────────────────
            lblPreviewInfo.BackColor = Color.FromArgb(45, 45, 45);
            lblPreviewInfo.Dock = DockStyle.Top;
            lblPreviewInfo.Font = new Font("Segoe UI", 10F, FontStyle.Bold);
            lblPreviewInfo.ForeColor = Color.LightGreen;
            lblPreviewInfo.Location = new Point(0, 0);
            lblPreviewInfo.Name = "lblPreviewInfo";
            lblPreviewInfo.Size = new Size(340, 28);
            lblPreviewInfo.TabIndex = 1;
            lblPreviewInfo.Text = "";
            lblPreviewInfo.TextAlign = ContentAlignment.MiddleCenter;

            // ── picFolderPreview ───────────────────────────────
            picFolderPreview.BackColor = Color.FromArgb(40, 40, 40);
            picFolderPreview.Dock = DockStyle.Fill;
            picFolderPreview.Location = new Point(0, 28);
            picFolderPreview.Name = "picFolderPreview";
            picFolderPreview.Size = new Size(340, 181);
            picFolderPreview.SizeMode = PictureBoxSizeMode.Zoom;
            picFolderPreview.TabIndex = 0;
            picFolderPreview.TabStop = false;

            // ── lblFolderPlateLabel ────────────────────────────
            lblFolderPlateLabel.BackColor = Color.FromArgb(45, 45, 45);
            lblFolderPlateLabel.Dock = DockStyle.Bottom;
            lblFolderPlateLabel.Font = new Font("Segoe UI", 8.5F);
            lblFolderPlateLabel.ForeColor = Color.Silver;
            lblFolderPlateLabel.Name = "lblFolderPlateLabel";
            lblFolderPlateLabel.Size = new Size(340, 20);
            lblFolderPlateLabel.TabIndex = 3;
            lblFolderPlateLabel.Text = "  Ảnh biển số:";
            lblFolderPlateLabel.TextAlign = ContentAlignment.MiddleLeft;

            // ── picFolderPlate ─────────────────────────────────
            picFolderPlate.BackColor = Color.FromArgb(30, 30, 30);
            picFolderPlate.Dock = DockStyle.Bottom;
            picFolderPlate.Height = 80;
            picFolderPlate.Name = "picFolderPlate";
            picFolderPlate.SizeMode = PictureBoxSizeMode.Zoom;
            picFolderPlate.TabIndex = 2;
            picFolderPlate.TabStop = false;

            // ── pnlPreviewActions ──────────────────────────────
            pnlPreviewActions.BackColor = Color.FromArgb(50, 50, 50);
            pnlPreviewActions.Controls.Add(btnSaveWrong);
            pnlPreviewActions.Controls.Add(btnSaveCorrect);
            pnlPreviewActions.Dock = DockStyle.Bottom;
            pnlPreviewActions.Height = 38;
            pnlPreviewActions.Name = "pnlPreviewActions";
            pnlPreviewActions.Padding = new Padding(4, 4, 4, 4);
            pnlPreviewActions.TabIndex = 4;

            // ── btnSaveCorrect ─────────────────────────────────
            btnSaveCorrect.BackColor = Color.FromArgb(39, 120, 74);
            btnSaveCorrect.Dock = DockStyle.Left;
            btnSaveCorrect.Enabled = false;
            btnSaveCorrect.FlatStyle = FlatStyle.Flat;
            btnSaveCorrect.FlatAppearance.BorderSize = 0;
            btnSaveCorrect.Font = new Font("Segoe UI", 9F, FontStyle.Bold);
            btnSaveCorrect.ForeColor = Color.White;
            btnSaveCorrect.Name = "btnSaveCorrect";
            btnSaveCorrect.Text = "✓  Đúng";
            btnSaveCorrect.Width = 162;
            btnSaveCorrect.TabIndex = 0;
            btnSaveCorrect.UseVisualStyleBackColor = false;

            // ── btnSaveWrong ───────────────────────────────────
            btnSaveWrong.BackColor = Color.FromArgb(180, 60, 60);
            btnSaveWrong.Dock = DockStyle.Fill;
            btnSaveWrong.Enabled = false;
            btnSaveWrong.FlatStyle = FlatStyle.Flat;
            btnSaveWrong.FlatAppearance.BorderSize = 0;
            btnSaveWrong.Font = new Font("Segoe UI", 9F, FontStyle.Bold);
            btnSaveWrong.ForeColor = Color.White;
            btnSaveWrong.Name = "btnSaveWrong";
            btnSaveWrong.Text = "✗  Sai";
            btnSaveWrong.TabIndex = 1;
            btnSaveWrong.UseVisualStyleBackColor = false;

            // ── dgvResults ─────────────────────────────────────
            dgvResults.AllowUserToAddRows = false;
            dgvResults.AllowUserToDeleteRows = false;
            dgvResults.AllowUserToResizeRows = false;
            dgvResults.BackgroundColor = Color.White;
            dgvResults.BorderStyle = BorderStyle.None;
            dgvResults.ColumnHeadersHeightSizeMode = DataGridViewColumnHeadersHeightSizeMode.AutoSize;
            dgvResults.Dock = DockStyle.Fill;
            dgvResults.Location = new Point(0, 0);
            dgvResults.Name = "dgvResults";
            dgvResults.ReadOnly = true;
            dgvResults.RowHeadersVisible = false;
            dgvResults.SelectionMode = DataGridViewSelectionMode.FullRowSelect;
            dgvResults.Size = new Size(750, 309);
            dgvResults.TabIndex = 0;

            // ── pnlFolderBottom ────────────────────────────────
            pnlFolderBottom.Controls.Add(lblFolderStats);
            pnlFolderBottom.Controls.Add(lblFolderStatus);
            pnlFolderBottom.Controls.Add(progressFolder);
            pnlFolderBottom.Dock = DockStyle.Bottom;
            pnlFolderBottom.Location = new Point(3, 387);
            pnlFolderBottom.Name = "pnlFolderBottom";
            pnlFolderBottom.Size = new Size(1090, 48);

            lblFolderStatus.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right;
            lblFolderStatus.ForeColor = Color.DimGray;
            lblFolderStatus.Location = new Point(4, 4);
            lblFolderStatus.Name = "lblFolderStatus";
            lblFolderStatus.Size = new Size(620, 18);
            lblFolderStatus.TabIndex = 0;
            lblFolderStatus.Text = "Chưa bắt đầu";

            lblFolderStats.Anchor = AnchorStyles.Top | AnchorStyles.Right;
            lblFolderStats.ForeColor = Color.DimGray;
            lblFolderStats.Location = new Point(630, 4);
            lblFolderStats.Name = "lblFolderStats";
            lblFolderStats.Size = new Size(456, 18);
            lblFolderStats.TabIndex = 1;
            lblFolderStats.Text = "";
            lblFolderStats.TextAlign = ContentAlignment.MiddleRight;

            progressFolder.Anchor = AnchorStyles.Bottom | AnchorStyles.Left | AnchorStyles.Right;
            progressFolder.Location = new Point(4, 28);
            progressFolder.Name = "progressFolder";
            progressFolder.Size = new Size(1082, 16);
            progressFolder.TabIndex = 2;
            progressFolder.Visible = false;

            // ── pnlLog ─────────────────────────────────────────
            pnlLog.Controls.Add(rtbLog);
            pnlLog.Controls.Add(pnlLogHeader);
            pnlLog.Dock = DockStyle.Bottom;
            pnlLog.Location = new Point(0, 581);
            pnlLog.Name = "pnlLog";
            pnlLog.Size = new Size(1104, 160);
            pnlLog.TabIndex = 2;

            rtbLog.BackColor = Color.FromArgb(30, 30, 30);
            rtbLog.BorderStyle = BorderStyle.None;
            rtbLog.Dock = DockStyle.Fill;
            rtbLog.Font = new Font("Consolas", 8.5F);
            rtbLog.ForeColor = Color.LightGreen;
            rtbLog.Location = new Point(0, 28);
            rtbLog.Name = "rtbLog";
            rtbLog.ReadOnly = true;
            rtbLog.ScrollBars = RichTextBoxScrollBars.Vertical;
            rtbLog.Size = new Size(1104, 132);
            rtbLog.TabIndex = 0;
            rtbLog.Text = "";

            pnlLogHeader.Controls.Add(lblLog);
            pnlLogHeader.Controls.Add(btnClearLog);
            pnlLogHeader.Dock = DockStyle.Top;
            pnlLogHeader.Location = new Point(0, 0);
            pnlLogHeader.Name = "pnlLogHeader";
            pnlLogHeader.Padding = new Padding(4, 4, 4, 0);
            pnlLogHeader.Size = new Size(1104, 28);
            pnlLogHeader.TabIndex = 1;

            lblLog.Font = new Font("Segoe UI", 9F, FontStyle.Bold);
            lblLog.Location = new Point(4, 6);
            lblLog.Name = "lblLog";
            lblLog.Size = new Size(40, 20);
            lblLog.TabIndex = 0;
            lblLog.Text = "Log:";

            btnClearLog.Anchor = AnchorStyles.Top | AnchorStyles.Right;
            btnClearLog.Location = new Point(1704, 2);
            btnClearLog.Name = "btnClearLog";
            btnClearLog.Size = new Size(80, 24);
            btnClearLog.TabIndex = 1;
            btnClearLog.Text = "Xóa log";

            // ── Form ───────────────────────────────────────────
            ClientSize = new Size(1104, 741);
            Controls.Add(tabMain);
            Controls.Add(pnlConfig);
            Controls.Add(pnlLog);
            Font = new Font("Segoe UI", 9F);
            MinimumSize = new Size(900, 650);
            Name = "FrmLprTester";
            StartPosition = FormStartPosition.CenterScreen;
            Text = "LPR Tester — Nhận dạng biển số xe";

            // ── ResumeLayout ───────────────────────────────────
            pnlConfig.ResumeLayout(false);
            gbConfig.ResumeLayout(false);
            gbConfig.PerformLayout();
            splitMain.Panel1.ResumeLayout(false);
            splitMain.Panel2.ResumeLayout(false);
            ((System.ComponentModel.ISupportInitialize)splitMain).EndInit();
            splitMain.ResumeLayout(false);
            ((System.ComponentModel.ISupportInitialize)picVehicle).EndInit();
            pnlDetect.ResumeLayout(false);
            pnlImageTop.ResumeLayout(false);
            ((System.ComponentModel.ISupportInitialize)numRotate).EndInit();
            gbResults.ResumeLayout(false);
            tblResults.ResumeLayout(false);
            tblResults.PerformLayout();
            ((System.ComponentModel.ISupportInitialize)picLpr).EndInit();
            tabSingle.ResumeLayout(false);
            pnlFolderTop.ResumeLayout(false);
            pnlFolderTop.PerformLayout();
            ((System.ComponentModel.ISupportInitialize)numFolderRotate).EndInit();
            ((System.ComponentModel.ISupportInitialize)dgvResults).EndInit();
            pnlFolderBottom.ResumeLayout(false);
            ((System.ComponentModel.ISupportInitialize)picFolderPreview).EndInit();
            ((System.ComponentModel.ISupportInitialize)picFolderPlate).EndInit();
            pnlPreview.ResumeLayout(false);
            tblFolderContent.ResumeLayout(false);
            tabFolder.ResumeLayout(false);
            tabMain.ResumeLayout(false);
            pnlLog.ResumeLayout(false);
            pnlLogHeader.ResumeLayout(false);
            ResumeLayout(false);
        }
    }
}
