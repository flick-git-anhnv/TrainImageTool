using System.Collections.Concurrent;
using IParkingDetect.Api;
using IParkingDetect.Helpers;
using IParkingDetect.Inference;
using IParkingDetect.Models;
using IParkingDetect.UI;

namespace IParkingDetect;

/// <summary>
/// KZTEK — iParking Detection Tester
/// Giao diện test model YOLO (OpenVINO IR / ONNX) trên tập ảnh iParking.
/// Tính năng: load model, duyệt thư mục ảnh, bbox viewer, detect all,
///            bộ lọc class/review, API host, cache kết quả.
/// </summary>
public sealed partial class DetectForm : Form
{
    // ── Inference / Data ──────────────────────────────────────────────────
    private readonly YoloRunner  _yolo  = new();
    private readonly AppSettings _cfg   = AppSettings.Load();
    private readonly ConcurrentDictionary<string, List<DetectBox>> _cache = new();
    private readonly Dictionary<string, ReviewState> _review = [];
    private CancellationTokenSource? _detectCts;

    private List<string> _imageList  = [];
    private int          _currentIdx = -1;
    private Bitmap?      _origBmp;
    private bool         _isDetecting;

    // ── Timing ────────────────────────────────────────────────────────────
    private long _lastDetectMs = 0;
    private long _batchTotalMs = 0;
    private long _batchCount   = 0;

    // ── UI state ──────────────────────────────────────────────────────────
    private string _activeFilter = "all";

    // ── API ───────────────────────────────────────────────────────────────
    private ApiHost? _apiHost;

    // ── Log data ──────────────────────────────────────────────────────────
    private readonly Dictionary<Guid, ListViewItem> _logItems = [];
    private readonly ConcurrentQueue<ApiLogEntry>   _logQueue = new();

    // ── Constructor ───────────────────────────────────────────────────────
    public DetectForm()
    {
        Text           = "KZTEK — iParking Detection Tester";
        Size           = new Size(_cfg.FormW, _cfg.FormH);
        MinimumSize    = new Size(1000, 640);
        BackColor      = Theme.BG;
        ForeColor      = Theme.Txt;
        Font           = Theme.FMain;
        DoubleBuffered = true;

        InitializeComponent();
        RestoreSession();
        BindShortcuts();

        FormClosing += (_, _) => SaveSession();
        Resize      += (_, _) => { _cfg.FormW = Width; _cfg.FormH = Height; };
    }

    // ═════════════════════════════════════════════════════════════════════
    // EVENT HANDLERS — Model
    // ═════════════════════════════════════════════════════════════════════

    private void OnBrowseModel(object? s, EventArgs e)
    {
        var choice = MessageBox.Show(
            "Chọn 'Yes' để duyệt FOLDER openvino_model/\n" +
            "Chọn 'No'  để duyệt FILE (.xml hoặc .onnx)",
            "Chọn model", MessageBoxButtons.YesNoCancel, MessageBoxIcon.Question);

        if (choice == DialogResult.Yes)
        {
            using var d = new FolderBrowserDialog
            {
                Description = "Chọn folder chứa model OpenVINO (có file .xml bên trong)",
                UseDescriptionForTitle = true,
            };
            if (d.ShowDialog() == DialogResult.OK) { _cmbModel.Text = d.SelectedPath; OnLoadModel(s, e); }
        }
        else if (choice == DialogResult.No)
        {
            using var d = new OpenFileDialog
            {
                Title  = "Chọn file model OpenVINO / ONNX",
                Filter = "Model files|*.xml;*.onnx|OpenVINO IR|*.xml|ONNX|*.onnx",
            };
            if (d.ShowDialog() == DialogResult.OK) { _cmbModel.Text = d.FileName; OnLoadModel(s, e); }
        }
    }

    private async void OnLoadModel(object? s, EventArgs e)
    {
        var path = _cmbModel.Text.Trim();
        if (string.IsNullOrEmpty(path)) return;

        SetStatus($"Đang load model: {Path.GetFileName(path)}…");
        _lblModelInfo.Text = "⏳ Loading…"; _lblModelInfo.ForeColor = Theme.Warn;
        _btnDetectAll.Enabled = false;

        var device = _cmbDevice.Text.Trim();
        if (string.IsNullOrEmpty(device)) device = "CPU";

        try
        {
            await Task.Run(() => _yolo.LoadModel(path, device));
            _cfg.Device = device;
            _cfg.PushModelHistory(path);
            RefreshModelCombo();
            UpdateModelInfoLabel();
            UpdateClassFilterCombo();
            _cache.Clear();
            UpdateCacheLabel();
            SetStatus($"Model loaded: {Path.GetFileName(path)} — {_yolo.NumClasses} class(es) [{_yolo.ActualDevice}]");
        }
        catch (Exception ex)
        {
            _lblModelInfo.Text = "✗ Load thất bại"; _lblModelInfo.ForeColor = Theme.Err;
            MessageBox.Show($"Lỗi load model:\n{ex.Message}", "Load Model",
                MessageBoxButtons.OK, MessageBoxIcon.Error);
            SetStatus("Lỗi load model.");
        }
        finally
        {
            _btnDetectAll.Enabled = true;
        }
    }

    private void OnLoadYaml(object? s, EventArgs e)
    {
        using var d = new OpenFileDialog
        {
            Title = "Chọn data.yaml (class names)", Filter = "YAML|*.yaml;*.yml"
        };
        if (d.ShowDialog() != DialogResult.OK) return;
        try
        {
            var names = YoloRunner.LoadClassNamesFromYaml(d.FileName);
            if (names.Length == 0) { MessageBox.Show("Không tìm thấy names: trong file YAML."); return; }
            _yolo.ClassNames = names;
            UpdateModelInfoLabel();
            UpdateClassFilterCombo();
            _cache.Clear();
            SetStatus($"Loaded {names.Length} class names từ YAML.");
        }
        catch (Exception ex) { MessageBox.Show($"Lỗi đọc YAML:\n{ex.Message}"); }
    }

    // ═════════════════════════════════════════════════════════════════════
    // EVENT HANDLERS — Path / Images
    // ═════════════════════════════════════════════════════════════════════

    private void BrowseFile()
    {
        using var d = new OpenFileDialog
        {
            Title = "Chọn ảnh", Multiselect = false,
            Filter = "Images|*.jpg;*.jpeg;*.png;*.bmp;*.webp",
        };
        if (d.ShowDialog() == DialogResult.OK) { _cmbPath.Text = d.FileName; OnLoadPath(null, EventArgs.Empty); }
    }

    private void BrowseFolder()
    {
        using var d = new FolderBrowserDialog { Description = "Chọn thư mục ảnh" };
        if (d.ShowDialog() == DialogResult.OK) { _cmbPath.Text = d.SelectedPath; OnLoadPath(null, EventArgs.Empty); }
    }

    private void OnLoadPath(object? s, EventArgs e)
    {
        var path = _cmbPath.Text.Trim();
        if (string.IsNullOrEmpty(path)) return;

        _cfg.PushImageHistory(path);
        RefreshPathCombo();

        var exts = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
            { ".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tiff" };

        if (File.Exists(path) && exts.Contains(Path.GetExtension(path)))
        {
            _imageList = [path];
        }
        else if (Directory.Exists(path))
        {
            var opt = _chkSub.Checked ? SearchOption.AllDirectories : SearchOption.TopDirectoryOnly;
            _imageList = Directory.GetFiles(path, "*.*", opt)
                .Where(f => exts.Contains(Path.GetExtension(f)))
                .OrderBy(f => f)
                .ToList();
        }
        else { SetStatus("Đường dẫn không hợp lệ."); return; }

        _cache.Clear();
        UpdateCacheLabel();
        _currentIdx = -1;
        RebuildTree();
        SetStatus($"Loaded {_imageList.Count} ảnh.");

        if (_imageList.Count > 0) NavigateTo(0);
    }

    // ═════════════════════════════════════════════════════════════════════
    // TREE & NAVIGATION
    // ═════════════════════════════════════════════════════════════════════

    private void RebuildTree()
    {
        _tree.BeginUpdate();
        _tree.Nodes.Clear();

        var filtered = GetFilteredImages();
        var grouped  = filtered.GroupBy(p => Path.GetDirectoryName(p) ?? "");

        foreach (var grp in grouped.OrderBy(g => g.Key))
        {
            var folderNode = new TreeNode(Path.GetFileName(grp.Key.TrimEnd('\\', '/')) ?? grp.Key)
            {
                ForeColor = Theme.Dim, Tag = null,
            };
            foreach (var imgPath in grp)
            {
                var state = _review.GetValueOrDefault(imgPath, ReviewState.None);
                var node  = new TreeNode(Path.GetFileName(imgPath))
                {
                    Tag       = imgPath,
                    ForeColor = state == ReviewState.Ok    ? Theme.Ok  :
                                state == ReviewState.Wrong ? Theme.Err : Theme.Txt,
                };
                if (_cache.TryGetValue(imgPath, out var boxes))
                    node.Text += $"  [{boxes.Count}]";
                folderNode.Nodes.Add(node);
            }
            _tree.Nodes.Add(folderNode);
        }

        if (_tree.Nodes.Count <= 10) _tree.ExpandAll();
        _tree.EndUpdate();
    }

    private List<string> GetFilteredImages()
    {
        var search = _txtSearch.Text.Trim().ToLowerInvariant();
        var clsFlt = _cmbClassFlt.SelectedIndex > 0 ? _cmbClassFlt.Text : null;
        int detMin = (int)_nudDetMin.Value;
        int detMax = (int)_nudDetMax.Value;

        return _imageList.Where(p =>
        {
            if (search.Length > 0 && !Path.GetFileName(p).ToLowerInvariant().Contains(search))
                return false;

            var state = _review.GetValueOrDefault(p, ReviewState.None);
            if (_activeFilter == "ok"    && state != ReviewState.Ok)    return false;
            if (_activeFilter == "wrong" && state != ReviewState.Wrong) return false;
            if (_activeFilter == "none"  && state != ReviewState.None)  return false;

            if (_cache.TryGetValue(p, out var boxes))
            {
                if (boxes.Count < detMin || boxes.Count > detMax) return false;
                if (clsFlt != null && boxes.All(b => b.ClassName != clsFlt)) return false;
            }

            return true;
        }).ToList();
    }

    private void OnTreeSelect(object? s, TreeViewEventArgs e)
    {
        if (e.Node?.Tag is string path)
        {
            int idx = _imageList.IndexOf(path);
            if (idx >= 0) NavigateTo(idx);
        }
    }

    private void Navigate(int delta)
    {
        if (_imageList.Count == 0) return;
        NavigateTo(Math.Clamp(_currentIdx + delta, 0, _imageList.Count - 1));
    }

    private void NavigateTo(int idx)
    {
        if (idx < 0 || idx >= _imageList.Count) return;
        _currentIdx = idx;
        LoadCurrentImage();
    }

    private void LoadCurrentImage()
    {
        if (_currentIdx < 0 || _currentIdx >= _imageList.Count) return;
        var path = _imageList[_currentIdx];

        _origBmp?.Dispose();
        try { _origBmp = new Bitmap(path); }
        catch { _origBmp = null; }

        if (_yolo.IsLoaded && !_cache.ContainsKey(path))
            DetectCurrent();

        RefreshCanvas();
        UpdateResultPanel(path);
        UpdateNavLabel();
        UpdateFilmstrip();
    }

    // ═════════════════════════════════════════════════════════════════════
    // DETECTION
    // ═════════════════════════════════════════════════════════════════════

    private void DetectCurrent()
    {
        if (!_yolo.IsLoaded || _origBmp is null || _currentIdx < 0) return;
        var path = _imageList[_currentIdx];
        if (_cache.ContainsKey(path)) return;

        try
        {
            var sw    = System.Diagnostics.Stopwatch.StartNew();
            var boxes = _yolo.Detect(_origBmp, _cfg.Conf, _cfg.Iou);
            sw.Stop();
            _lastDetectMs = sw.ElapsedMilliseconds;
            _cache[path]  = boxes;
            if (_cfg.SaveLabel)
                SaveLabelFile(path, boxes, _origBmp.Width, _origBmp.Height);
        }
        catch { _cache[path] = []; }

        UpdateCacheLabel();
    }

    private void RefreshCurrentDetect()
    {
        if (_currentIdx < 0 || _currentIdx >= _imageList.Count) return;
        var path = _imageList[_currentIdx];
        _cache.TryRemove(path, out _);
        if (_yolo.IsLoaded && _origBmp is not null)
        {
            try
            {
                var sw = System.Diagnostics.Stopwatch.StartNew();
                var boxes  = _yolo.Detect(_origBmp, _cfg.Conf, _cfg.Iou);
                sw.Stop();
                _lastDetectMs = sw.ElapsedMilliseconds;
                _cache[path]  = boxes;
                if (_cfg.SaveLabel)
                    SaveLabelFile(path, boxes, _origBmp.Width, _origBmp.Height);
            }
            catch { _cache[path] = []; _lastDetectMs = 0; }
        }
        RefreshCanvas();
        UpdateResultPanel(path);
    }

    private void OnDetectCurrent(object? s, EventArgs e)
    {
        if (!_yolo.IsLoaded)  { SetStatus("Hãy load model trước."); return; }
        if (_origBmp is null || _currentIdx < 0) { SetStatus("Hãy chọn ảnh trước."); return; }

        var path = _imageList[_currentIdx];
        _cache.TryRemove(path, out _);
        try
        {
            var sw    = System.Diagnostics.Stopwatch.StartNew();
            var boxes = _yolo.Detect(_origBmp, _cfg.Conf, _cfg.Iou);
            sw.Stop();
            _lastDetectMs = sw.ElapsedMilliseconds;
            _cache[path]  = boxes;

            if (_cfg.SaveLabel)
            {
                SaveLabelFile(path, boxes, _origBmp.Width, _origBmp.Height);
                SetStatus($"⚡ Detected + 💾 Saved label: {Path.GetFileNameWithoutExtension(path)}.txt  " +
                          $"— {boxes.Count} obj  {_lastDetectMs}ms");
            }
            else
            {
                SetStatus($"⚡ Detected: {Path.GetFileName(path)}  — {boxes.Count} obj  {_lastDetectMs}ms");
            }
        }
        catch (Exception ex)
        {
            _cache[path] = [];
            SetStatus($"Lỗi detect: {ex.Message}");
        }

        UpdateCacheLabel();
        RefreshCanvas();
        UpdateResultPanel(path);
    }

    // Lưu file nhãn YOLO (.txt) cạnh file ảnh
    private static void SaveLabelFile(string imgPath, IReadOnlyList<DetectBox> boxes, int imgW, int imgH)
    {
        if (imgW <= 0 || imgH <= 0) return;
        var txtPath = Path.ChangeExtension(imgPath, ".txt");
        try
        {
            using var sw = new StreamWriter(txtPath, append: false, System.Text.Encoding.UTF8);
            foreach (var b in boxes)
            {
                float cxn = (b.X1 + b.X2) / 2f / imgW;
                float cyn = (b.Y1 + b.Y2) / 2f / imgH;
                float wn  = b.Width  / imgW;
                float hn  = b.Height / imgH;
                sw.WriteLine(
                    $"{b.ClassId} {cxn:F6} {cyn:F6} {wn:F6} {hn:F6}");
            }
        }
        catch { /* bỏ qua lỗi ghi file — không block workflow */ }
    }

    private async void OnDetectAll(object? s, EventArgs e)
    {
        if (!_yolo.IsLoaded) { MessageBox.Show("Hãy load model trước."); return; }
        if (_imageList.Count == 0) { MessageBox.Show("Hãy load ảnh trước."); return; }
        if (_isDetecting) return;

        _isDetecting  = true;
        _batchTotalMs = 0;
        _batchCount   = 0;
        _detectCts    = new CancellationTokenSource();
        _btnDetectAll.Visible = false; _btnStop.Visible = true;
        _pbDetect.Maximum = _imageList.Count; _pbDetect.Value = 0; _pbDetect.Visible = true;

        var token      = _detectCts.Token;
        var batchSw    = System.Diagnostics.Stopwatch.StartNew();
        int processed  = 0;
        float conf     = _cfg.Conf;
        float iou      = _cfg.Iou;
        bool saveLabel = _cfg.SaveLabel;
        int   total    = _imageList.Count;
        var   images   = _imageList.ToList();

        await Task.Run(() =>
        {
            var opts = new ParallelOptions
            {
                MaxDegreeOfParallelism = (int)_nudParallel.Value,
                CancellationToken      = token,
            };

            try
            {
                Parallel.ForEach(images, opts, path =>
                {
                    var prevPriority = Thread.CurrentThread.Priority;
                    Thread.CurrentThread.Priority = ThreadPriority.BelowNormal;

                    if (!_cache.ContainsKey(path))
                    {
                        var sw = System.Diagnostics.Stopwatch.StartNew();
                        List<DetectBox> boxes;
                        int bmpW = 0, bmpH = 0;
                        try
                        {
                            using var bmp = new Bitmap(path);
                            bmpW  = bmp.Width;
                            bmpH  = bmp.Height;
                            boxes = _yolo.Detect(bmp, conf, iou);
                        }
                        catch { boxes = []; }
                        sw.Stop();

                        _cache[path] = boxes;
                        if (saveLabel && bmpW > 0)
                            SaveLabelFile(path, boxes, bmpW, bmpH);
                        Interlocked.Add(ref _batchTotalMs, sw.ElapsedMilliseconds);
                        Interlocked.Increment(ref _batchCount);
                    }

                    Thread.CurrentThread.Priority = prevPriority;

                    int p = Interlocked.Increment(ref processed);
                    if (p % 5 == 0 || p == total)
                    {
                        Invoke(() =>
                        {
                            _pbDetect.Value = Math.Min(p, _pbDetect.Maximum);
                            UpdateCacheLabel();
                            long cnt   = Interlocked.Read(ref _batchCount);
                            long tms   = Interlocked.Read(ref _batchTotalMs);
                            long avgMs = cnt > 0 ? tms / cnt : 0;
                            SetStatus($"Detecting… {p}/{total}  avg {avgMs}ms/ảnh  " +
                                      $"({(avgMs > 0 ? 1000f / avgMs : 0):F1} FPS)  " +
                                      $"[{(int)_nudParallel.Value} luồng | {_yolo.ActualDevice}]");
                        });
                    }
                });
            }
            catch (OperationCanceledException) { }
        });

        batchSw.Stop();
        _isDetecting = false;
        _btnDetectAll.Visible = true; _btnStop.Visible = false; _pbDetect.Visible = false;
        RebuildTree();
        RefreshCanvas();

        long finalCnt = Interlocked.Read(ref _batchCount);
        long finalAvg = finalCnt > 0 ? Interlocked.Read(ref _batchTotalMs) / finalCnt : 0;
        float fps     = finalAvg > 0 ? 1000f / finalAvg : 0;
        var labelNote = saveLabel ? "  💾 Đã lưu nhãn (.txt)" : "";
        SetStatus($"✓ Detect All: {processed}/{_imageList.Count} ảnh  |  " +
                  $"avg {finalAvg}ms/ảnh  {fps:F1} FPS  |  " +
                  $"tổng {FormatDuration(batchSw.ElapsedMilliseconds)}  " +
                  $"[{(int)_nudParallel.Value} luồng | {_yolo.ActualDevice}]{labelNote}");
    }

    // ═════════════════════════════════════════════════════════════════════
    // DISPLAY
    // ═════════════════════════════════════════════════════════════════════

    private void RefreshCanvas()
    {
        if (_origBmp is null) { _canvas.SetImage(null); return; }
        if (_chkOrig.Checked) { _canvas.SetImage(_origBmp, fit: false); return; }

        var path  = _currentIdx >= 0 ? _imageList[_currentIdx] : "";
        var boxes = _cache.GetValueOrDefault(path, []);
        var drew  = BboxRenderer.DrawBoxes(_origBmp, boxes);
        _canvas.SetImage(drew);
        drew.Dispose();
    }

    private void UpdateResultPanel(string path)
    {
        _lblImgPath.Text = Path.GetFileName(path);
        _lstResult.Items.Clear();

        bool fromCache = _cache.TryGetValue(path, out var boxes);
        if (!fromCache) { _lblTiming.Text = ""; return; }

        foreach (var b in boxes!)
        {
            var item = new ListViewItem(b.ClassName);
            item.SubItems.Add($"{b.Confidence:P0}");
            item.SubItems.Add($"{b.Width:F0}×{b.Height:F0}");
            item.ForeColor = Theme.BboxColor(b.ClassId);
            _lstResult.Items.Add(item);
        }

        if (_lastDetectMs > 0)
        {
            float fps = 1000f / _lastDetectMs;
            _lblTiming.Text      = $"⏱ {_lastDetectMs}ms  ({fps:F1} FPS)  |  {boxes.Count} obj  [{_yolo.ActualDevice}]";
            _lblTiming.ForeColor = _lastDetectMs < 50  ? Theme.Ok   :
                                   _lastDetectMs < 200 ? Theme.Warn : Theme.Err;
        }
        else if (_batchCount > 0)
        {
            long avg = _batchTotalMs / _batchCount;
            float fps = avg > 0 ? 1000f / avg : 0;
            _lblTiming.Text      = $"⏱ ~{avg}ms/ảnh  ({fps:F1} FPS avg)  |  {boxes.Count} obj  [{_yolo.ActualDevice}]";
            _lblTiming.ForeColor = Theme.Dim;
        }
        else
        {
            _lblTiming.Text      = boxes.Count > 0 ? $"📦 {boxes.Count} đối tượng (cached)  [{_yolo.ActualDevice}]" : "";
            _lblTiming.ForeColor = Theme.Dim;
        }

        var state = _review.GetValueOrDefault(path, ReviewState.None);
        _lblMark.Text = state switch
        {
            ReviewState.Ok    => "✓ Đã đánh dấu ĐÚNG",
            ReviewState.Wrong => "✗ Đã đánh dấu SAI",
            _ => ""
        };
        _lblMark.ForeColor = state == ReviewState.Ok    ? Theme.Ok  :
                             state == ReviewState.Wrong ? Theme.Err : Theme.Dim;
    }

    private void UpdateNavLabel()
    {
        _lblNav.Text = _imageList.Count > 0
            ? $"  {_currentIdx + 1} / {_imageList.Count}  "
            : "  –  ";
    }

    private void UpdateFilmstrip()
    {
        _filmstrip.Controls.Clear();

        int half  = 15;
        int start = Math.Max(0, _currentIdx - half);
        int end   = Math.Min(_imageList.Count - 1, start + 30);

        for (int i = start; i <= end; i++)
        {
            var idx  = i;
            var path = _imageList[i];

            var cell = new Panel
            {
                Width = 84, Height = 66, BackColor = Theme.Deep,
                Margin = new Padding(2), Cursor = Cursors.Hand,
            };

            var state = _review.GetValueOrDefault(path, ReviewState.None);
            cell.BackColor = idx == _currentIdx ? Theme.Accent :
                             state == ReviewState.Ok    ? Theme.Ok  :
                             state == ReviewState.Wrong ? Theme.Err : Theme.Border;

            var pb = new PictureBox
            {
                Width = 80, Height = 60, Location = new Point(2, 2),
                SizeMode = PictureBoxSizeMode.StretchImage, BackColor = Theme.Deep,
            };

            Task.Run(() =>
            {
                try
                {
                    using var bmp = new Bitmap(path);
                    var boxes = _cache.GetValueOrDefault(path, []);
                    var thumb = BboxRenderer.MakeThumb(bmp, boxes, 80, 60);
                    if (!pb.IsDisposed) pb.Invoke(() => { pb.Image?.Dispose(); pb.Image = thumb; });
                }
                catch { }
            });

            cell.Click += (_, _) => NavigateTo(idx);
            pb.Click   += (_, _) => NavigateTo(idx);
            cell.Controls.Add(pb);
            _filmstrip.Controls.Add(cell);
        }
    }

    // ═════════════════════════════════════════════════════════════════════
    // REVIEW / MARKS
    // ═════════════════════════════════════════════════════════════════════

    private void SetReview(ReviewState state)
    {
        if (_currentIdx < 0) return;
        var path = _imageList[_currentIdx];
        if (state == ReviewState.None) _review.Remove(path);
        else _review[path] = state;

        UpdateResultPanel(path);
        UpdateFilmstrip();
        RebuildTree();
    }

    private void OnSaveWrong(object? s, EventArgs e)
    {
        if (_currentIdx < 0) return;
        var dest = _cmbWrongDir.Text.Trim();
        if (string.IsNullOrEmpty(dest)) { MessageBox.Show("Chưa chọn thư mục lưu ảnh sai."); return; }
        try
        {
            Directory.CreateDirectory(dest);
            var src      = _imageList[_currentIdx];
            var destFile = Path.Combine(dest, Path.GetFileName(src));
            File.Copy(src, destFile, overwrite: true);
            SetReview(ReviewState.Wrong);
            SetStatus($"Đã lưu: {Path.GetFileName(destFile)}");
        }
        catch (Exception ex) { MessageBox.Show($"Lỗi lưu file:\n{ex.Message}"); }
    }

    // ═════════════════════════════════════════════════════════════════════
    // UI HELPERS
    // ═════════════════════════════════════════════════════════════════════

    private void UpdateModelInfoLabel()
    {
        if (!_yolo.IsLoaded)
        {
            _lblModelInfo.Text = "Chưa load model"; _lblModelInfo.ForeColor = Theme.Dim; return;
        }
        var names = string.Join(", ", _yolo.ClassNames.Take(6));
        if (_yolo.ClassNames.Length > 6) names += "…";
        _lblModelInfo.Text = $"✓ {Path.GetFileName(_yolo.ModelPath)}  " +
                             $"In:{_yolo.InputW}×{_yolo.InputH}  " +
                             $"Classes:{_yolo.NumClasses} [{names}]  " +
                             $"[{_yolo.ActualDevice}]";
        _lblModelInfo.ForeColor = Theme.Ok;
    }

    private void UpdateClassFilterCombo()
    {
        _cmbClassFlt.Items.Clear();
        _cmbClassFlt.Items.Add("Tất cả");
        foreach (var n in _yolo.ClassNames) _cmbClassFlt.Items.Add(n);
        _cmbClassFlt.SelectedIndex = 0;
    }

    private void UpdateCacheLabel() =>
        _lblCacheInfo.Text = $"Cache: {_cache.Count}/{_imageList.Count}";

    private void HighlightFilter()
    {
        var btns = new[] { _btnAllFilter, _btnOkFilter, _btnWrongFilter, _btnUnrevFilter };
        var fltrs = new[] { "all", "ok", "wrong", "none" };
        for (int i = 0; i < btns.Length; i++)
            btns[i].BackColor = fltrs[i] == _activeFilter ? Theme.Navy : Theme.Card;
    }

    private void RefreshModelCombo()
    {
        _cmbModel.Items.Clear();
        _cmbModel.Items.AddRange(_cfg.ModelHistory.ToArray());
        if (_cfg.ModelHistory.Count > 0) _cmbModel.Text = _cfg.ModelHistory[0];
    }

    private void RefreshPathCombo()
    {
        _cmbPath.Items.Clear();
        _cmbPath.Items.AddRange(_cfg.ImageHistory.ToArray());
        if (_cfg.ImageHistory.Count > 0) _cmbPath.Text = _cfg.ImageHistory[0];
    }

    private void SetStatus(string msg) => _lblStatus.Text = msg;

    private static string FormatDuration(long ms)
    {
        if (ms < 1000)  return $"{ms}ms";
        if (ms < 60000) return $"{ms / 1000.0:F1}s";
        return $"{ms / 60000}m {(ms % 60000) / 1000}s";
    }

    private void ClearCache()
    {
        int count = _cache.Count;
        _cache.Clear();
        UpdateCacheLabel();
        SetStatus($"Đã xóa cache ({count} ảnh)");
    }

    private static string GetLocalIp()
    {
        try
        {
            using var sock = new System.Net.Sockets.UdpClient();
            sock.Connect("8.8.8.8", 80);
            return ((System.Net.IPEndPoint)sock.Client.LocalEndPoint!).Address.ToString();
        }
        catch { return "localhost"; }
    }

    // ═════════════════════════════════════════════════════════════════════
    // KEYBOARD SHORTCUTS
    // ═════════════════════════════════════════════════════════════════════

    private void BindShortcuts()
    {
        KeyPreview = true;
        KeyDown += (_, e) =>
        {
            switch (e.KeyCode)
            {
                case Keys.Left:  Navigate(-1); e.Handled = true; break;
                case Keys.Right: Navigate(+1); e.Handled = true; break;
                case Keys.Return when _currentIdx >= 0:
                    SetReview(ReviewState.Ok);    e.Handled = true; break;
                case Keys.Delete when _currentIdx >= 0:
                    SetReview(ReviewState.Wrong); e.Handled = true; break;
                case Keys.Escape: _detectCts?.Cancel(); break;
                case Keys.F5:     _btnDetectAll.PerformClick(); e.Handled = true; break;
                case Keys.O when e.Control: BrowseFolder(); e.Handled = true; break;
                case Keys.M when e.Control: OnBrowseModel(this, e); e.Handled = true; break;
                case Keys.Delete when e.Control && e.Shift: ClearCache(); e.Handled = true; break;
            }
        };
    }

    // ═════════════════════════════════════════════════════════════════════
    // SESSION SAVE / RESTORE
    // ═════════════════════════════════════════════════════════════════════

    private void RestoreSession()
    {
        _sldConf.Value         = (int)(_cfg.Conf * 100);
        _sldIou.Value          = (int)(_cfg.Iou  * 100);
        _chkOrig.Checked       = _cfg.ShowOriginal;
        _chkSaveLabel.Checked  = _cfg.SaveLabel;
        _cmbWrongDir.Text      = _cfg.WrongFolder;

        if (_cfg.ApiAutoStart) StartApi();

        if (!string.IsNullOrEmpty(_cfg.ModelPath) &&
            (File.Exists(_cfg.ModelPath) || Directory.Exists(_cfg.ModelPath)))
        {
            _cmbModel.Text = _cfg.ModelPath;
            OnLoadModel(this, EventArgs.Empty);
        }
        if (!string.IsNullOrEmpty(_cfg.ImagePath) &&
            (File.Exists(_cfg.ImagePath) || Directory.Exists(_cfg.ImagePath)))
        {
            _cmbPath.Text = _cfg.ImagePath;
            OnLoadPath(this, EventArgs.Empty);
        }
    }

    private void SaveSession()
    {
        _cfg.ModelPath      = _cmbModel.Text;
        _cfg.ImagePath      = _cmbPath.Text;
        _cfg.WrongFolder    = _cmbWrongDir.Text;
        _cfg.ScanSubfolders = _chkSub.Checked;
        _cfg.ShowOriginal   = _chkOrig.Checked;
        _cfg.Save();
    }

    // ═════════════════════════════════════════════════════════════════════
    // API HOST
    // ═════════════════════════════════════════════════════════════════════

    private void OnToggleApi(object? s, EventArgs e)
    {
        if (_apiHost?.IsRunning == true) StopApi();
        else StartApi();
    }

    private void StartApi()
    {
        int port = (int)_nudApiPort.Value;
        try
        {
            _apiHost?.Dispose();
            _apiHost = new ApiHost(_yolo, port, () => _cfg.Conf, () => _cfg.Iou);
            _apiHost.OnLog += AppendLog;
            _apiHost.Start(port);
            _nudApiPort.Enabled    = false;
            _btnApiToggle.Text     = "■ Stop API";
            var localIp            = GetLocalIp();
            _lblApiStatus.Text     = $"● {localIp}:{port}/detect";
            _lblApiStatus.ForeColor = Theme.Ok;
            SetStatus($"API đang chạy tại http://{localIp}:{port}/detect");
        }
        catch (Exception ex)
        {
            MessageBox.Show($"Không thể khởi động API:\n{ex.Message}", "Lỗi API",
                MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }

    private void StopApi()
    {
        _apiHost?.Stop();
        _nudApiPort.Enabled    = true;
        _btnApiToggle.Text     = "🌐 Start API";
        _lblApiStatus.Text     = "● Stopped";
        _lblApiStatus.ForeColor = Theme.Dim;
        SetStatus("API đã dừng.");
    }

    // ═════════════════════════════════════════════════════════════════════
    // API LOG
    // ═════════════════════════════════════════════════════════════════════

    private void AppendLog(ApiLogEntry entry) => _logQueue.Enqueue(entry);

    private void FlushLogQueue()
    {
        if (_logQueue.IsEmpty) return;
        bool anyNew = false;
        while (_logQueue.TryDequeue(out var entry))
        {
            if (_logItems.TryGetValue(entry.Id, out var item))
            {
                item.SubItems[1].Text = StatusText(entry.Status);
                item.SubItems[3].Text = entry.EndTime?.ToString("HH:mm:ss.fff") ?? "";
                item.SubItems[4].Text = entry.InferMs.HasValue ? $"{entry.InferMs}" : "";
                item.SubItems[5].Text = entry.TotalMs.HasValue ? $"{entry.TotalMs}" : "";
                item.ForeColor        = StatusColor(entry.Status);
                if (entry.ErrorMsg is not null) item.ToolTipText = entry.ErrorMsg;
            }
            else
            {
                var lvi = new ListViewItem(entry.ImageName) { Tag = entry.ImagePath };
                lvi.SubItems.Add(StatusText(entry.Status));
                lvi.SubItems.Add(entry.StartTime.ToString("HH:mm:ss.fff"));
                lvi.SubItems.Add("");
                lvi.SubItems.Add("");
                lvi.SubItems.Add("");
                lvi.ForeColor   = StatusColor(entry.Status);
                lvi.ToolTipText = entry.ImagePath;
                _logItems[entry.Id] = lvi;
                _lvLog.Items.Insert(0, lvi);

                while (_lvLog.Items.Count > 500)
                {
                    var last = _lvLog.Items[^1];
                    _logItems.Remove(_logItems.FirstOrDefault(kv => kv.Value == last).Key);
                    _lvLog.Items.RemoveAt(_lvLog.Items.Count - 1);
                }
                anyNew = true;
            }
        }
        if (anyNew) UpdateLogCount();
    }

    private static string StatusText(ApiLogStatus s) => s switch
    {
        ApiLogStatus.Processing => "🔄 Đang xử lý",
        ApiLogStatus.Done       => "✓ Xong",
        ApiLogStatus.Error      => "✗ Lỗi",
        _                       => "",
    };

    private Color StatusColor(ApiLogStatus s) => s switch
    {
        ApiLogStatus.Processing => Theme.Warn,
        ApiLogStatus.Done       => Theme.Ok,
        ApiLogStatus.Error      => Theme.Err,
        _                       => Theme.Txt,
    };

    private void UpdateLogCount() =>
        _lblLogCount.Text = $"📋 API Log  —  {_lvLog.Items.Count} yêu cầu";

    // ═════════════════════════════════════════════════════════════════════
    // DISPOSE
    // ═════════════════════════════════════════════════════════════════════

    protected override void Dispose(bool disposing)
    {
        if (disposing)
        {
            _logTimer.Stop();
            _detectCts?.Dispose();
            _origBmp?.Dispose();
            _yolo.Dispose();
            _apiHost?.Dispose();
        }
        base.Dispose(disposing);
    }
}
