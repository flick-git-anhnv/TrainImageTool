using iParkingv5.Lpr.Objects;
using iParkingv5.LprDetecter.LprDetecters;
using Kztek.Object;
using System.Drawing;
using System.Text;
using System.Windows.Forms;
using static Kztek.Object.LprDetecter;

namespace iParkingv8.LprTester;

public partial class FrmLprTester : Form
{
    private ILpr? _lpr;
    private Image? _loadedImage;
    private CancellationTokenSource? _detectCts;
    private CancellationTokenSource? _folderCts;

    private static readonly string[] ImageExtensions =
        [".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".tif"];

    public FrmLprTester()
    {
        InitializeComponent();
        this.Load += new EventHandler(this.FrmLprTester_Load);
        this.cboLprType.SelectedIndexChanged += new EventHandler(this.cboLprType_SelectedIndexChanged);
        this.btnConnect.Click += new EventHandler(this.btnConnect_Click);
        this.btnCheckServer.Click += new EventHandler(this.btnCheckServer_Click);
        this.btnLoadImage.Click += new EventHandler(this.btnLoadImage_Click);
        this.btnDetect.Click += new EventHandler(this.btnDetect_Click);
        this.btnClearLog.Click += new EventHandler(this.btnClearLog_Click);
        this.btnBrowseFolder.Click += new EventHandler(this.btnBrowseFolder_Click);
        this.btnTestFolder.Click += new EventHandler(this.btnTestFolder_Click);
        this.btnStopFolder.Click += new EventHandler(this.btnStopFolder_Click);
        this.btnExportCsv.Click += new EventHandler(this.btnExportCsv_Click);
        this.dgvResults.SelectionChanged += new EventHandler(this.dgvResults_SelectionChanged);
        this.btnSaveCorrect.Click += new EventHandler(this.btnSaveCorrect_Click);
        this.btnSaveWrong.Click += new EventHandler(this.btnSaveWrong_Click);
        LoadLprTypes();
        SetupResultsGrid();
    }

    // ───────────────────────── Init ─────────────────────────

    private void LoadLprTypes()
    {
        cboLprType.Items.Add(new LprTypeItem(EmLprDetecter.KztekLPRAIServer, "Kztek LPR AI Server"));
        cboLprType.Items.Add(new LprTypeItem(EmLprDetecter.AmericalLpr, "American LPR (OpenALPR)"));
        cboLprType.Items.Add(new LprTypeItem(EmLprDetecter.KztekLpr, "Kztek LPR Standalone (Local)"));
        cboLprType.SelectedIndex = 0;
    }

    private void SetupResultsGrid()
    {
        dgvResults.Columns.Add(new DataGridViewTextBoxColumn
        {
            Name = "colNo", HeaderText = "#", Width = 45, ReadOnly = true,
            SortMode = DataGridViewColumnSortMode.NotSortable
        });
        dgvResults.Columns.Add(new DataGridViewTextBoxColumn
        {
            Name = "colFile", HeaderText = "Tên file", MinimumWidth = 150, ReadOnly = true,
            AutoSizeMode = DataGridViewAutoSizeColumnMode.Fill,
            SortMode = DataGridViewColumnSortMode.NotSortable
        });
        dgvResults.Columns.Add(new DataGridViewTextBoxColumn
        {
            Name = "colPlate", HeaderText = "Biển số", Width = 130, ReadOnly = true,
            SortMode = DataGridViewColumnSortMode.NotSortable
        });
        dgvResults.Columns.Add(new DataGridViewTextBoxColumn
        {
            Name = "colOriginal", HeaderText = "Biển gốc", Width = 120, ReadOnly = true,
            SortMode = DataGridViewColumnSortMode.NotSortable
        });
        dgvResults.Columns.Add(new DataGridViewTextBoxColumn
        {
            Name = "colVehicle", HeaderText = "Loại xe", Width = 100, ReadOnly = true,
            SortMode = DataGridViewColumnSortMode.NotSortable
        });
        dgvResults.Columns.Add(new DataGridViewTextBoxColumn
        {
            Name = "colMs", HeaderText = "Thời gian (ms)", Width = 110, ReadOnly = true,
            DefaultCellStyle = new DataGridViewCellStyle { Alignment = DataGridViewContentAlignment.MiddleRight },
            SortMode = DataGridViewColumnSortMode.NotSortable
        });
        dgvResults.Columns.Add(new DataGridViewTextBoxColumn
        {
            Name = "colStatus", HeaderText = "Trạng thái", Width = 120, ReadOnly = true,
            SortMode = DataGridViewColumnSortMode.NotSortable
        });
    }

    private void FrmLprTester_Load(object sender, EventArgs e)
    {
        splitMain.Panel1MinSize = 350;
        splitMain.Panel2MinSize = 300;
        splitMain.SplitterDistance = splitMain.Width / 2;
    }

    // ───────────────────────── Single image handlers ─────────────────────────

    private async void btnConnect_Click(object sender, EventArgs e)
    {
        var config = BuildConfig();
        if (config == null) return;

        SetConnecting(true);
        Log($"[Kết nối] Đang khởi tạo {config.LPRDetecterType}...");
        try
        {
            _lpr = LprFactory.CreateLprDetecter(config, null);
            if (_lpr == null)
            {
                Log("[Lỗi] Không thể tạo LPR detector.");
                return;
            }
            bool ok = await _lpr.CreateLprAsync(config);
            Log(ok ? "[OK] Khởi tạo thành công." : "[Lỗi] Khởi tạo thất bại.");
            btnDetect.Enabled = ok;
            btnTestFolder.Enabled = ok;
        }
        catch (Exception ex)
        {
            Log($"[Lỗi] {ex.Message}");
        }
        finally
        {
            SetConnecting(false);
        }
    }

    private async void btnCheckServer_Click(object sender, EventArgs e)
    {
        if (_lpr == null)
        {
            MessageBox.Show("Chưa khởi tạo kết nối. Nhấn 'Kết nối' trước.", "Thông báo",
                MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return;
        }
        Log("[Kiểm tra] Đang kiểm tra server...");
        btnCheckServer.Enabled = false;
        try
        {
            bool valid = await _lpr.IsValidLprServer();
            string status = valid ? "✓ Server sẵn sàng" : "✗ Server không phản hồi";
            lblServerStatus.Text = status;
            lblServerStatus.ForeColor = valid ? Color.Green : Color.Red;
            Log($"[Kiểm tra] {status}");
        }
        catch (Exception ex)
        {
            lblServerStatus.Text = "✗ Lỗi kết nối";
            lblServerStatus.ForeColor = Color.Red;
            Log($"[Lỗi] {ex.Message}");
        }
        finally
        {
            btnCheckServer.Enabled = true;
        }
    }

    private void btnLoadImage_Click(object sender, EventArgs e)
    {
        using var dlg = new OpenFileDialog
        {
            Title = "Chọn ảnh xe",
            Filter = "Ảnh|*.jpg;*.jpeg;*.png;*.bmp;*.gif;*.tiff|Tất cả|*.*"
        };
        if (dlg.ShowDialog() != DialogResult.OK) return;

        try
        {
            _loadedImage?.Dispose();
            _loadedImage = Image.FromFile(dlg.FileName);
            picVehicle.Image = _loadedImage;
            lblImagePath.Text = Path.GetFileName(dlg.FileName);
            Log($"[Ảnh] Đã tải: {dlg.FileName}");
            ClearResults();
        }
        catch (Exception ex)
        {
            Log($"[Lỗi] Không tải được ảnh: {ex.Message}");
        }
    }

    private async void btnDetect_Click(object sender, EventArgs e)
    {
        if (_lpr == null)
        {
            MessageBox.Show("Chưa kết nối LPR server.", "Thông báo",
                MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return;
        }
        if (_loadedImage == null)
        {
            MessageBox.Show("Chưa tải ảnh xe.", "Thông báo",
                MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return;
        }

        _detectCts?.Cancel();
        _detectCts = new CancellationTokenSource();
        SetDetecting(true);
        ClearResults();

        bool isCar = chkIsCar.Checked;
        int rotateAngle = (int)numRotate.Value;
        Log($"[Nhận dạng] isCar={isCar}, rotateAngle={rotateAngle}...");

        try
        {
            var sw = System.Diagnostics.Stopwatch.StartNew();
            DetectLprResult result = await _lpr.GetPlateNumberAsync(
                _loadedImage, isCar, null, rotateAngle, isRemoveSpecialKey: true);
            sw.Stop();

            DisplayResult(result);
            Log($"[OK] Biển số: \"{result.PlateNumber}\" | Thời gian: {sw.ElapsedMilliseconds}ms");
        }
        catch (Exception ex)
        {
            Log($"[Lỗi] {ex.Message}");
        }
        finally
        {
            SetDetecting(false);
        }
    }

    private void btnClearLog_Click(object sender, EventArgs e)
    {
        rtbLog.Clear();
    }

    private void cboLprType_SelectedIndexChanged(object sender, EventArgs e)
    {
        if (cboLprType.SelectedItem is not LprTypeItem item) return;
        bool needsUrl = item.Type != EmLprDetecter.KztekLpr;
        txtUrl.Enabled = needsUrl;
        txtUsername.Enabled = item.Type == EmLprDetecter.AmericalLpr;
        txtPassword.Enabled = item.Type == EmLprDetecter.AmericalLpr;
        if (!needsUrl) txtUrl.Text = "(Standalone - không cần URL)";

        _lpr = null;
        btnDetect.Enabled = false;
        btnTestFolder.Enabled = false;
        lblServerStatus.Text = "Chưa kết nối";
        lblServerStatus.ForeColor = Color.Gray;
    }

    // ───────────────────────── Folder test handlers ─────────────────────────

    private void btnBrowseFolder_Click(object sender, EventArgs e)
    {
        using var dlg = new FolderBrowserDialog
        {
            Description = "Chọn thư mục chứa ảnh xe cần test",
            UseDescriptionForTitle = true
        };
        if (dlg.ShowDialog() == DialogResult.OK)
            txtFolderPath.Text = dlg.SelectedPath;
    }

    private async void btnTestFolder_Click(object sender, EventArgs e)
    {
        if (_lpr == null)
        {
            MessageBox.Show("Chưa kết nối LPR server. Nhấn 'Kết nối' trước.", "Thông báo",
                MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return;
        }
        string folder = txtFolderPath.Text.Trim();
        if (string.IsNullOrEmpty(folder) || !Directory.Exists(folder))
        {
            MessageBox.Show("Thư mục không hợp lệ hoặc không tồn tại.", "Thông báo",
                MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return;
        }

        _folderCts = new CancellationTokenSource();
        SetFolderTesting(true);

        try
        {
            await TestFolderAsync(folder, chkSubfolders.Checked, _folderCts.Token);
        }
        catch (OperationCanceledException)
        {
            Log("[Thư mục] Đã dừng bởi người dùng.");
            lblFolderStatus.Text = "Đã dừng.";
        }
        finally
        {
            SetFolderTesting(false);
        }
    }

    private void btnStopFolder_Click(object sender, EventArgs e)
    {
        _folderCts?.Cancel();
    }

    private void btnExportCsv_Click(object sender, EventArgs e)
    {
        if (dgvResults.Rows.Count == 0)
        {
            MessageBox.Show("Không có dữ liệu để xuất.", "Thông báo",
                MessageBoxButtons.OK, MessageBoxIcon.Information);
            return;
        }

        using var dlg = new SaveFileDialog
        {
            Title = "Xuất kết quả CSV",
            Filter = "CSV files (*.csv)|*.csv|Tất cả|*.*",
            DefaultExt = "csv",
            FileName = $"lpr_results_{DateTime.Now:yyyyMMdd_HHmmss}.csv"
        };
        if (dlg.ShowDialog() != DialogResult.OK) return;

        try
        {
            using var sw = new StreamWriter(dlg.FileName, false, new UTF8Encoding(encoderShouldEmitUTF8Identifier: true));
            sw.WriteLine("STT,Tên file,Biển số,Biển gốc,Loại xe,Thời gian (ms),Trạng thái");
            foreach (DataGridViewRow row in dgvResults.Rows)
            {
                var cells = new string[row.Cells.Count];
                for (int i = 0; i < row.Cells.Count; i++)
                    cells[i] = EscapeCsv(row.Cells[i].Value?.ToString() ?? string.Empty);
                sw.WriteLine(string.Join(",", cells));
            }
            Log($"[CSV] Đã xuất {dgvResults.Rows.Count} dòng → {dlg.FileName}");
            MessageBox.Show($"Xuất thành công {dgvResults.Rows.Count} dòng.", "Xuất CSV",
                MessageBoxButtons.OK, MessageBoxIcon.Information);
        }
        catch (Exception ex)
        {
            Log($"[Lỗi] Xuất CSV: {ex.Message}");
            MessageBox.Show($"Lỗi xuất file: {ex.Message}", "Lỗi",
                MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }

    // ───────────────────────── Folder test logic ─────────────────────────

    private async Task TestFolderAsync(string folderPath, bool includeSubfolders, CancellationToken ct)
    {
        var searchOption = includeSubfolders ? SearchOption.AllDirectories : SearchOption.TopDirectoryOnly;
        var files = Directory.GetFiles(folderPath, "*.*", searchOption)
            .Where(f => ImageExtensions.Contains(Path.GetExtension(f), StringComparer.OrdinalIgnoreCase))
            .OrderBy(f => f)
            .ToArray();

        if (files.Length == 0)
        {
            Log("[Thư mục] Không tìm thấy ảnh nào trong thư mục.");
            lblFolderStatus.Text = "Không tìm thấy ảnh.";
            return;
        }

        DisposeRowImages();
        dgvResults.Rows.Clear();
        ClearFolderPreview();
        progressFolder.Maximum = files.Length;
        progressFolder.Value = 0;
        progressFolder.Visible = true;

        int success = 0, failed = 0;
        long totalMs = 0;
        bool isCar = chkFolderIsCar.Checked;
        int rotateAngle = (int)numFolderRotate.Value;

        Log($"[Thư mục] Bắt đầu: {files.Length} ảnh | isCar={isCar} | xoay={rotateAngle}°");

        for (int i = 0; i < files.Length; i++)
        {
            ct.ThrowIfCancellationRequested();

            string file = files[i];
            string filename = includeSubfolders
                ? Path.GetRelativePath(folderPath, file)
                : Path.GetFileName(file);

            lblFolderStatus.Text = $"Đang xử lý {i + 1}/{files.Length}: {Path.GetFileName(file)}";
            progressFolder.Value = i;

            try
            {
                using var img = Image.FromFile(file);
                var sw = System.Diagnostics.Stopwatch.StartNew();
                var result = await _lpr!.GetPlateNumberAsync(img, isCar, null, rotateAngle, isRemoveSpecialKey: true);
                sw.Stop();

                long ms = sw.ElapsedMilliseconds;
                bool detected = !string.IsNullOrWhiteSpace(result.PlateNumber);
                if (detected) success++; else failed++;
                totalMs += ms;

                string vehicleType = result.vehicleClassify != null
                    ? $"{result.vehicleClassify.Vehicle_type} ({result.vehicleClassify.Confidence:P0})"
                    : string.Empty;

                AddResultRow(i + 1, filename, result.PlateNumber ?? string.Empty,
                    result.OriginalPlate ?? string.Empty, vehicleType, ms,
                    detected ? "OK" : "Không nhận dạng", result.LprImage);
            }
            catch (OperationCanceledException)
            {
                throw;
            }
            catch (Exception ex)
            {
                failed++;
                AddResultRow(i + 1, filename, string.Empty, string.Empty, string.Empty, 0, $"Lỗi: {ex.Message}");
                Log($"[Lỗi] {Path.GetFileName(file)}: {ex.Message}");
            }

            UpdateFolderStats(success, failed, files.Length, totalMs);
        }

        progressFolder.Value = files.Length;
        string summary = $"Hoàn thành {files.Length} ảnh | OK: {success} | Thất bại: {failed} | TB: {(files.Length > 0 ? totalMs / files.Length : 0)}ms";
        lblFolderStatus.Text = summary;
        Log($"[Thư mục] {summary}");
    }

    private void AddResultRow(int no, string filename, string plate, string original,
        string vehicleType, long ms, string status, Image? lprImage = null)
    {
        if (dgvResults.InvokeRequired)
        {
            dgvResults.Invoke(() => AddResultRow(no, filename, plate, original, vehicleType, ms, status, lprImage));
            return;
        }

        int rowIdx = dgvResults.Rows.Add(no, filename, plate, original, vehicleType,
            ms > 0 ? ms.ToString() : "-", status);

        var row = dgvResults.Rows[rowIdx];
        if (status == "OK")
            row.DefaultCellStyle.BackColor = Color.Honeydew;
        else if (status.StartsWith("Lỗi"))
            row.DefaultCellStyle.BackColor = Color.MistyRose;
        else
            row.DefaultCellStyle.BackColor = Color.LightYellow;

        row.Tag = lprImage;
        dgvResults.FirstDisplayedScrollingRowIndex = rowIdx;
    }

    private void UpdateFolderStats(int success, int failed, int total, long totalMs)
    {
        if (lblFolderStats.InvokeRequired)
        {
            lblFolderStats.Invoke(() => UpdateFolderStats(success, failed, total, totalMs));
            return;
        }
        int done = success + failed;
        long avg = done > 0 ? totalMs / done : 0;
        lblFolderStats.Text = $"Đã xử lý: {done}/{total}  |  OK: {success}  |  Thất bại: {failed}  |  TB: {avg}ms";
    }

    // ───────────────────────── Folder preview ─────────────────────────

    private void dgvResults_SelectionChanged(object sender, EventArgs e)
    {
        var row = dgvResults.CurrentRow;
        if (row == null)
        {
            ClearFolderPreview();
            btnSaveCorrect.Enabled = false;
            btnSaveWrong.Enabled = false;
            return;
        }

        string filename = row.Cells["colFile"].Value?.ToString() ?? string.Empty;
        string plate = row.Cells["colPlate"].Value?.ToString() ?? string.Empty;
        string ms = row.Cells["colMs"].Value?.ToString() ?? string.Empty;

        bool hasFile = !string.IsNullOrEmpty(filename) && !string.IsNullOrEmpty(txtFolderPath.Text);
        btnSaveCorrect.Enabled = hasFile;
        btnSaveWrong.Enabled = hasFile;

        lblPreviewInfo.Text = string.IsNullOrWhiteSpace(plate)
            ? "(không nhận dạng)"
            : $"{plate}   {(ms != "-" ? ms + "ms" : string.Empty)}".Trim();

        // Ảnh cắt biển số từ row.Tag (borrowed reference, không dispose)
        picFolderPlate.Image = row.Tag as Image;

        if (string.IsNullOrEmpty(filename) || string.IsNullOrEmpty(txtFolderPath.Text))
        {
            var oldVehicle = picFolderPreview.Image;
            picFolderPreview.Image = null;
            oldVehicle?.Dispose();
            return;
        }

        try
        {
            string fullPath = Path.Combine(txtFolderPath.Text, filename);
            if (!File.Exists(fullPath))
            {
                var oldVehicle = picFolderPreview.Image;
                picFolderPreview.Image = null;
                oldVehicle?.Dispose();
                return;
            }
            var old = picFolderPreview.Image;
            picFolderPreview.Image = Image.FromFile(fullPath);
            old?.Dispose();
        }
        catch
        {
            var old = picFolderPreview.Image;
            picFolderPreview.Image = null;
            old?.Dispose();
        }
    }

    private void ClearFolderPreview(bool keepLabel = false)
    {
        var old = picFolderPreview.Image;
        picFolderPreview.Image = null;
        old?.Dispose();

        picFolderPlate.Image = null; // borrowed reference, không dispose

        if (!keepLabel) lblPreviewInfo.Text = string.Empty;
    }

    private void DisposeRowImages()
    {
        picFolderPlate.Image = null;
        foreach (DataGridViewRow row in dgvResults.Rows)
        {
            if (row.Tag is Image img)
            {
                img.Dispose();
                row.Tag = null;
            }
        }
    }

    private void btnSaveCorrect_Click(object sender, EventArgs e) => SaveCurrentImageToGt(isCorrect: true);
    private void btnSaveWrong_Click(object sender, EventArgs e) => SaveCurrentImageToGt(isCorrect: false);

    private void SaveCurrentImageToGt(bool isCorrect)
    {
        var row = dgvResults.CurrentRow;
        if (row == null) return;

        string filename = row.Cells["colFile"].Value?.ToString() ?? string.Empty;
        string plate = row.Cells["colPlate"].Value?.ToString() ?? string.Empty;
        string sourceFolder = txtFolderPath.Text.Trim();

        if (string.IsNullOrEmpty(filename) || string.IsNullOrEmpty(sourceFolder)) return;

        string sourcePath = Path.Combine(sourceFolder, filename);
        if (!File.Exists(sourcePath))
        {
            Log($"[GT] Không tìm thấy file: {sourcePath}");
            return;
        }

        string subFolder = isCorrect ? "dung" : "sai";
        string gtFolder = Path.Combine(sourceFolder, "_gt", subFolder);
        Directory.CreateDirectory(gtFolder);

        string destName = Path.GetFileName(filename);
        string destPath = Path.Combine(gtFolder, destName);
        File.Copy(sourcePath, destPath, overwrite: true);

        // Sidecar .txt chứa biển số (chỉ khi đúng và có nhận dạng)
        if (isCorrect && !string.IsNullOrWhiteSpace(plate))
            File.WriteAllText(Path.ChangeExtension(destPath, ".txt"), plate, Encoding.UTF8);

        // Đánh dấu trong grid
        string gtLabel = isCorrect ? "GT: Đúng ✓" : "GT: Sai ✗";
        row.Cells["colStatus"].Value = gtLabel;
        row.DefaultCellStyle.BackColor = isCorrect ? Color.PaleGreen : Color.LightCoral;

        Log($"[GT] {Path.GetFileName(filename)} → _gt/{subFolder}/ | {plate}");
    }

    // ───────────────────────── Display helpers ─────────────────────────

    private void DisplayResult(DetectLprResult result)
    {
        txtPlate.Text = result.PlateNumber;
        txtOriginal.Text = result.OriginalPlate;
        txtDescription.Text = result.Color;

        if (result.BoundingBox != null)
        {
            var bb = result.BoundingBox;
            txtBbox.Text = $"({bb.Xmin}, {bb.Ymin}) → ({bb.Xmax}, {bb.Ymax})";
        }
        else
        {
            txtBbox.Text = "(không có)";
        }

        if (result.vehicleClassify != null)
        {
            txtVehicleType.Text = $"{result.vehicleClassify.Vehicle_type} " +
                                  $"({result.vehicleClassify.Confidence:P1})";
        }
        else
        {
            txtVehicleType.Text = "(không nhận dạng)";
        }

        if (result.LprImage != null)
            picLpr.Image = result.LprImage;

        txtPlate.BackColor = string.IsNullOrWhiteSpace(result.PlateNumber)
            ? Color.MistyRose
            : Color.LightGreen;
    }

    private void ClearResults()
    {
        txtPlate.Text = string.Empty;
        txtPlate.BackColor = SystemColors.Window;
        txtOriginal.Text = string.Empty;
        txtBbox.Text = string.Empty;
        txtVehicleType.Text = string.Empty;
        txtDescription.Text = string.Empty;
        picLpr.Image = null;
    }

    private void SetConnecting(bool connecting)
    {
        btnConnect.Enabled = !connecting;
        btnConnect.Text = connecting ? "Đang kết nối..." : "Kết nối";
        lblServerStatus.Text = connecting ? "Đang kết nối..." : "Chưa kết nối";
        lblServerStatus.ForeColor = connecting ? Color.Orange : Color.Gray;
    }

    private void SetDetecting(bool detecting)
    {
        btnDetect.Enabled = !detecting;
        btnDetect.Text = detecting ? "Đang nhận dạng..." : "Nhận dạng biển số";
        progressBar.Style = detecting ? ProgressBarStyle.Marquee : ProgressBarStyle.Blocks;
        progressBar.Visible = detecting;
    }

    private void SetFolderTesting(bool testing)
    {
        btnTestFolder.Enabled = !testing;
        btnStopFolder.Enabled = testing;
        btnBrowseFolder.Enabled = !testing;
        chkSubfolders.Enabled = !testing;
        progressFolder.Visible = true;
    }

    private LprConfig? BuildConfig()
    {
        if (cboLprType.SelectedItem is not LprTypeItem item)
        {
            MessageBox.Show("Vui lòng chọn loại LPR.", "Thông báo",
                MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return null;
        }

        bool needsUrl = item.Type != EmLprDetecter.KztekLpr;
        if (needsUrl && string.IsNullOrWhiteSpace(txtUrl.Text))
        {
            MessageBox.Show("Vui lòng nhập URL server LPR.", "Thông báo",
                MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return null;
        }

        return new LprConfig
        {
            LPRDetecterType = item.Type,
            Url = needsUrl ? txtUrl.Text.Trim() : string.Empty,
            Username = txtUsername.Text.Trim(),
            Password = txtPassword.Text.Trim(),
            IsDetectVehicleType = chkDetectVehicle.Checked,
            RetakePhotoDelay = 300,
            RetakePhotoTimes = 1
        };
    }

    private static string EscapeCsv(string value)
    {
        if (value.Contains(',') || value.Contains('"') || value.Contains('\n'))
            return $"\"{value.Replace("\"", "\"\"")}\"";
        return value;
    }

    private void Log(string message)
    {
        string line = $"[{DateTime.Now:HH:mm:ss.fff}] {message}";
        if (rtbLog.InvokeRequired)
            rtbLog.Invoke(() => AppendLog(line));
        else
            AppendLog(line);
    }

    private void AppendLog(string line)
    {
        rtbLog.AppendText(line + Environment.NewLine);
        rtbLog.ScrollToCaret();
    }

    // ───────────────────────── Helper class ─────────────────────────

    private sealed class LprTypeItem(EmLprDetecter type, string display)
    {
        public EmLprDetecter Type { get; } = type;
        public override string ToString() => display;
    }
}
