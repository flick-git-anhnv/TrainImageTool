using System.Collections.Concurrent;
using SlotMonitor.Data;
using SlotMonitor.Forms;
using SlotMonitor.Helpers;
using SlotMonitor.Inference;
using SlotMonitor.Models;
using SlotMonitor.UI;
using SlotMonitor.Workers;

namespace SlotMonitor;

/// <summary>
/// KZTEK Slot Monitor — Form chính.
///
/// Layout:
///   ┌─ Toolbar (model, device, conf, iou, interval, folder) ─────────────┐
///   ├─ Camera cards ─────────────────────┬─ Event log ────────────────────┤
///   └─ Status bar ────────────────────────────────────────────────────────┘
///
/// Timer 200 ms: refresh card thumbnails/state + per-slot badges, flush events.
/// </summary>
public sealed partial class MainForm : Form
{
    // ── Core ──────────────────────────────────────────────────────────────
    private readonly AppSettings _cfg  = AppSettings.Load();
    private readonly YoloRunner  _yolo = new();
    private readonly SlotDb      _db;
    private readonly List<CameraWorker> _workers = [];

    // Per-camera typed control refs (no Control.Find overhead in timer)
    private record SlotMiniCard(PictureBox Pb, Label StateLbl, Label TimeLbl);

    private record CardControls(
        PictureBox                       Pb,
        Label                            State,
        Label                            Conf,
        Label                            Time,
        Label                            Ms,
        Label                            Dot,
        Button                           Toggle,
        Dictionary<string, SlotMiniCard> SlotMinis);  // slotId → mini-card

    private readonly Dictionary<string, CardControls> _cardCtls = [];
    private string? _selectedCamId;

    // ── UI controls ───────────────────────────────────────────────────────
    private ComboBox      _cmbModel    = null!;
    private ComboBox      _cmbDevice   = null!;
    private NumericUpDown _nudConf     = null!;
    private NumericUpDown _nudIou      = null!;
    private NumericUpDown _nudInterval = null!;
    private NumericUpDown _nudEmpty    = null!;
    private TextBox       _txtFolder   = null!;
    private Label         _lblModelInfo = null!;
    private FlowLayoutPanel _camPanel  = null!;
    private ListView      _lvEvents    = null!;
    private Label         _lblStatus   = null!;
    private Button        _btnLoadModel = null!;

    private readonly System.Windows.Forms.Timer _timer;

    // ── Constructor ───────────────────────────────────────────────────────

    public MainForm()
    {
        _db = new SlotDb(_cfg.DbPath);

        Text           = "KZTEK — Slot Monitor";
        Size           = new Size(_cfg.FormW, _cfg.FormH);
        MinimumSize    = new Size(980, 620);
        BackColor      = Theme.BG;
        ForeColor      = Theme.Txt;
        Font           = Theme.FMain;
        DoubleBuffered = true;

        BuildUI();
        RestoreSession();

        _timer = new System.Windows.Forms.Timer { Interval = 200 };
        _timer.Tick += OnTimerTick;
        _timer.Start();

        FormClosing += (_, _) => OnClose();
        Resize      += (_, _) => { _cfg.FormW = Width; _cfg.FormH = Height; };
        Shown       += (_, _) => RebuildCards();
        KeyPreview   = true;
        KeyDown     += OnKeyDown;
    }

    // ══════════════════════════════════════════════════════════════════════
    // BUILD UI
    // ══════════════════════════════════════════════════════════════════════

    private void BuildUI()
    {
        var toolbar = BuildToolbar();
        var split   = BuildSplitContent();
        _lblStatus  = new Label
        {
            Dock = DockStyle.Bottom, Height = 24,
            BackColor = Theme.NavyDk, ForeColor = Theme.Dim,
            TextAlign = ContentAlignment.MiddleLeft,
            Padding   = new Padding(10, 0, 0, 0),
            Text      = "Sẵn sàng",
        };
        Controls.AddRange([split, toolbar, _lblStatus]);
    }

    // ── Toolbar (2 rows) ──────────────────────────────────────────────────

    private Panel BuildToolbar()
    {
        var bar = new Panel { Dock = DockStyle.Top, Height = 88, BackColor = Theme.Card };

        // Row 1
        int x = 8, y = 8;
        bar.Controls.Add(MkLbl("Model:", x, y + 2)); x += 50;
        _cmbModel = new ComboBox
        {
            Left = x, Top = y, Width = 280,
            BackColor = Theme.Deep, ForeColor = Theme.Txt, DropDownStyle = ComboBoxStyle.DropDown,
        };
        bar.Controls.Add(_cmbModel); x += 284;

        var btnBrowse = Theme.Btn("📁", Theme.Card);
        btnBrowse.SetBounds(x, y - 1, 34, 26); btnBrowse.Click += OnBrowseModel;
        bar.Controls.Add(btnBrowse); x += 38;

        _btnLoadModel = Theme.Btn("⚙ Load", Theme.Accent);
        _btnLoadModel.SetBounds(x, y - 1, 80, 26); _btnLoadModel.Click += OnLoadModel;
        bar.Controls.Add(_btnLoadModel); x += 88;

        bar.Controls.Add(MkLbl("Device:", x, y + 2)); x += 52;
        _cmbDevice = new ComboBox
        {
            Left = x, Top = y, Width = 90, DropDownStyle = ComboBoxStyle.DropDownList,
            BackColor = Theme.Deep, ForeColor = Theme.Txt,
        };
        _cmbDevice.Items.AddRange(["CPU", "GPU", "AUTO"]);
        _cmbDevice.SelectedIndex = 0;
        bar.Controls.Add(_cmbDevice); x += 96;

        bar.Controls.Add(MkLbl("Conf%:", x, y + 2)); x += 46;
        _nudConf = Theme.Num(1, 99, (decimal)(_cfg.Conf * 100), 55);
        _nudConf.SetBounds(x, y, 55, 24); bar.Controls.Add(_nudConf); x += 60;

        bar.Controls.Add(MkLbl("IOU%:", x, y + 2)); x += 42;
        _nudIou = Theme.Num(1, 99, (decimal)(_cfg.Iou * 100), 55);
        _nudIou.SetBounds(x, y, 55, 24); bar.Controls.Add(_nudIou); x += 60;

        bar.Controls.Add(MkLbl("Interval(s):", x, y + 2)); x += 76;
        _nudInterval = Theme.Num(1, 300, _cfg.IntervalSecs, 60);
        _nudInterval.SetBounds(x, y, 60, 24); bar.Controls.Add(_nudInterval); x += 66;

        bar.Controls.Add(MkLbl("Cls trống:", x, y + 2)); x += 64;
        _nudEmpty = Theme.Num(0, 99, _cfg.EmptyClassIndex, 52);
        _nudEmpty.SetBounds(x, y, 52, 24); bar.Controls.Add(_nudEmpty);

        // Row 1.5 — model info
        _lblModelInfo = new Label
        {
            Left = 8, Top = 34, Width = bar.Width - 16, Height = 18,
            Anchor = AnchorStyles.Left | AnchorStyles.Right | AnchorStyles.Top,
            Text = "Chưa load model", ForeColor = Theme.Dim, BackColor = Color.Transparent, Font = Theme.FSm,
        };
        bar.Controls.Add(_lblModelInfo);

        // Row 2 — folder + start/stop all
        x = 8; y = 54;
        bar.Controls.Add(MkLbl("Thư mục ảnh:", x, y + 2)); x += 90;
        _txtFolder = new TextBox
        {
            Left = x, Top = y, Width = 360,
            BackColor = Theme.Deep, ForeColor = Theme.Txt, BorderStyle = BorderStyle.FixedSingle,
        };
        bar.Controls.Add(_txtFolder); x += 364;

        var btnFld = Theme.Btn("📁", Theme.Card);
        btnFld.SetBounds(x, y - 1, 34, 26); btnFld.Click += OnBrowseFolder;
        bar.Controls.Add(btnFld); x += 38;

        var btnStart = Theme.Btn("▶ Start All", Theme.Ok);
        btnStart.SetBounds(x, y - 1, 106, 26); btnStart.Click += (_, _) => StartAll();
        bar.Controls.Add(btnStart); x += 110;

        var btnStop = Theme.Btn("■ Stop All", Theme.Err);
        btnStop.SetBounds(x, y - 1, 106, 26); btnStop.Click += (_, _) => StopAll();
        bar.Controls.Add(btnStop);

        return bar;
    }

    // ── Split: camera list (left) + event log (right) ─────────────────────

    private SplitContainer BuildSplitContent()
    {
        var split = new SplitContainer
        {
            Dock = DockStyle.Fill, Orientation = Orientation.Vertical,
            SplitterWidth = 4, BackColor = Theme.Border,
        };
        split.Panel1.Controls.Add(BuildCameraSection());
        split.Panel2.Controls.Add(BuildEventSection());
        split.SplitterDistance = _cfg.FormW * 58 / 100;
        return split;
    }

    private Panel BuildCameraSection()
    {
        var root = new Panel { Dock = DockStyle.Fill, BackColor = Theme.BG };

        var hdr = new Panel { Dock = DockStyle.Top, Height = 38, BackColor = Theme.NavyDk };
        Theme.Lbl("📷  Danh sách camera", Theme.FBold, Theme.Txt)
             .Also(l => { l.Location = new Point(8, 10); hdr.Controls.Add(l); });

        var btnFlow = new FlowLayoutPanel
        {
            Dock = DockStyle.Right, Width = 290, Height = 38,
            FlowDirection = FlowDirection.RightToLeft,
            Padding = new Padding(4), WrapContents = false, BackColor = Color.Transparent,
        };
        var btnDel  = Theme.Btn("✕ Xóa",    Theme.Card, Theme.Err);  btnDel.Width = 80;
        var btnEdit = Theme.Btn("✎ Sửa",    Theme.Navy);              btnEdit.Width = 80;
        var btnAdd  = Theme.Btn("+ Thêm",   Theme.Accent);            btnAdd.Width = 80;
        btnAdd.Click += OnAddCamera; btnEdit.Click += OnEditCamera; btnDel.Click += OnDeleteCamera;
        btnFlow.Controls.AddRange([btnDel, btnEdit, btnAdd]);
        hdr.Controls.Add(btnFlow);

        _camPanel = new FlowLayoutPanel
        {
            Dock = DockStyle.Fill, FlowDirection = FlowDirection.TopDown,
            WrapContents = false, AutoScroll = true,
            BackColor = Theme.BG, Padding = new Padding(6),
        };

        // Resize cards when panel changes width
        _camPanel.SizeChanged += (_, _) =>
        {
            int w = Math.Max(340, _camPanel.ClientSize.Width - 18);
            foreach (Control c in _camPanel.Controls)
                if (c is Panel p && p.Width != w) p.Width = w;
        };

        root.Controls.AddRange([_camPanel, hdr]);
        return root;
    }

    private Panel BuildEventSection()
    {
        var root = new Panel { Dock = DockStyle.Fill, BackColor = Theme.BG };

        var hdr = new Panel { Dock = DockStyle.Top, Height = 38, BackColor = Theme.NavyDk };
        Theme.Lbl("📋  Sự kiện thay đổi trạng thái", Theme.FBold, Theme.Txt)
             .Also(l => { l.Location = new Point(8, 10); hdr.Controls.Add(l); });

        var btnFlow = new FlowLayoutPanel
        {
            Dock = DockStyle.Right, Width = 220, Height = 38,
            FlowDirection = FlowDirection.RightToLeft,
            Padding = new Padding(4), WrapContents = false, BackColor = Color.Transparent,
        };
        var btnClear = Theme.Btn("Xóa log",     Theme.Card, Theme.Dim);
        var btnHist  = Theme.Btn("📜 Lịch sử",  Theme.Navy);
        btnHist.Width = 100; btnClear.Width = 80;
        btnHist.Click  += (_, _) => new HistoryForm(_db, _cfg).Show(this);
        btnClear.Click += (_, _) => _lvEvents.Items.Clear();
        btnFlow.Controls.AddRange([btnClear, btnHist]);
        hdr.Controls.Add(btnFlow);

        _lvEvents = new ListView
        {
            Dock = DockStyle.Fill, View = View.Details, FullRowSelect = true,
            BackColor = Theme.Deep, ForeColor = Theme.Txt, BorderStyle = BorderStyle.None,
        };
        _lvEvents.Columns.AddRange([
            new ColumnHeader { Text = "Thời gian",  Width = 110 },
            new ColumnHeader { Text = "Camera",     Width = 100 },
            new ColumnHeader { Text = "Slot",       Width = 80  },
            new ColumnHeader { Text = "Trước",      Width = 72  },
            new ColumnHeader { Text = "Sau",        Width = 72  },
            new ColumnHeader { Text = "Conf",       Width = 52  },
        ]);
        _lvEvents.DoubleClick += OnEventDoubleClick;

        root.Controls.AddRange([_lvEvents, hdr]);
        return root;
    }

    // ══════════════════════════════════════════════════════════════════════
    // CAMERA CARDS
    // ══════════════════════════════════════════════════════════════════════

    private void RebuildCards()
    {
        foreach (var w in _workers) { w.Stop(); w.Dispose(); }
        _workers.Clear();
        _camPanel.Controls.Clear();
        _cardCtls.Clear();
        _selectedCamId = null;

        foreach (var cam in _cfg.Cameras)
        {
            var (card, ctls) = BuildCard(cam);
            _cardCtls[cam.Id] = ctls;
            _camPanel.Controls.Add(card);
            _workers.Add(new CameraWorker(cam, _yolo, _cfg, _db));
        }
    }

    private (Panel card, CardControls ctls) BuildCard(CameraConfig cam)
    {
        bool hasSlots = cam.Slots.Count > 0;

        // ── Tính chiều cao card ───────────────────────────────────────────
        //   Không có slot : 228px (thumbnail 218×118 + info + buttons)
        //   Có slot        : 168px header+url+buttons + mỗi hàng mini-card 100px
        const int miniW = 108, miniH = 100, miniMargin = 3;
        int slotsPerRow = hasSlots
            ? Math.Max(1, (Math.Max(340, _camPanel.ClientSize.Width - 18) - 16) / (miniW + miniMargin * 2))
            : 0;
        int slotRows  = hasSlots ? (int)Math.Ceiling((double)cam.Slots.Count / slotsPerRow) : 0;
        int cardH     = hasSlots ? 168 + slotRows * (miniH + miniMargin) : 228;

        var card = new Panel
        {
            Width = Math.Max(340, _camPanel.ClientSize.Width - 18),
            Height = cardH, BackColor = Theme.Card, Margin = new Padding(0, 0, 0, 6),
        };

        // ── Status dot ────────────────────────────────────────────────────
        var dot = new Label
        {
            Text = "●", ForeColor = Theme.Dim, BackColor = Color.Transparent,
            Font = new Font("Segoe UI", 12f), AutoSize = false,
            Width = 22, Height = 22, Left = card.Width - 26, Top = 6,
            Anchor = AnchorStyles.Right | AnchorStyles.Top,
            TextAlign = ContentAlignment.MiddleCenter,
        };

        // ── Camera name ───────────────────────────────────────────────────
        var lblName = new Label
        {
            Text = cam.Name, Left = 8, Top = 7, Width = card.Width - 40, Height = 20,
            ForeColor = Theme.Txt, Font = Theme.FBold, BackColor = Color.Transparent,
            Anchor = AnchorStyles.Left | AnchorStyles.Right | AnchorStyles.Top,
        };

        // ── Preview thumbnail (ẩn khi có slot — mini-card thay thế) ──────
        var pb = new PictureBox
        {
            Left = 8, Top = 30, Width = hasSlots ? 0 : 218, Height = hasSlots ? 0 : 118,
            SizeMode = PictureBoxSizeMode.StretchImage, BackColor = Theme.Deep,
            Visible = !hasSlots,
        };
        pb.DoubleClick += (_, _) => OpenPreviewWindow(cam.Id);

        // ── Info area ─────────────────────────────────────────────────────
        int rx = hasSlots ? 8  : 234;
        int ry = hasSlots ? 28 : 30;
        int rw = hasSlots ? card.Width - 16 : card.Width - 234 - 8;

        var lblState = new Label
        {
            Left = rx, Top = ry, Width = rw, Height = hasSlots ? 22 : 28,
            Text = "⬜ CHƯA BIẾT", ForeColor = Theme.Dim, BackColor = Color.Transparent,
            Font = hasSlots ? Theme.FMain : Theme.FBold,
            TextAlign = hasSlots ? ContentAlignment.MiddleLeft : ContentAlignment.MiddleCenter,
            Anchor = AnchorStyles.Left | AnchorStyles.Right | AnchorStyles.Top,
        };
        ry += hasSlots ? 22 : 32;

        var lblConf = new Label
        {
            Left = rx, Top = ry, Width = rw / 2, Height = 16,
            ForeColor = Theme.Dim, BackColor = Color.Transparent, Font = Theme.FSm,
            Anchor = AnchorStyles.Left | AnchorStyles.Top,
        };

        var lblMs = new Label
        {
            Left = rx + rw / 2, Top = ry, Width = rw / 2, Height = 16,
            ForeColor = Theme.Dim, BackColor = Color.Transparent, Font = Theme.FSm,
            TextAlign = ContentAlignment.MiddleRight,
            Anchor = AnchorStyles.Left | AnchorStyles.Top,
        };
        ry += 18;

        var lblTime = new Label
        {
            Left = rx, Top = ry, Width = rw, Height = 16,
            ForeColor = Theme.Dim, BackColor = Color.Transparent, Font = Theme.FMono,
            Anchor = AnchorStyles.Left | AnchorStyles.Top,
        };

        // ── RTSP URL ──────────────────────────────────────────────────────
        int urlY = hasSlots ? 28 + 22 + 18 + 16 + 4 : 152;
        var lblUrl = new Label
        {
            Left = 8, Top = urlY, Width = card.Width - 16, Height = 14,
            Text = ShortenUrl(cam.RtspUrl), ForeColor = Color.FromArgb(80, 144, 144, 176),
            BackColor = Color.Transparent, Font = Theme.FMono,
            Anchor = AnchorStyles.Left | AnchorStyles.Right | AnchorStyles.Top,
        };

        // ── Per-slot mini-cards ───────────────────────────────────────────
        int miniAreaTop = hasSlots ? urlY + 16 : urlY + 18;
        var slotMinis   = new Dictionary<string, SlotMiniCard>();

        var miniFlow = new FlowLayoutPanel
        {
            Left = 6, Top = miniAreaTop,
            Width = card.Width - 12,
            Height = slotRows * (miniH + miniMargin) + 2,
            FlowDirection = FlowDirection.LeftToRight, WrapContents = true,
            BackColor = Color.Transparent, Visible = hasSlots,
            Anchor = AnchorStyles.Left | AnchorStyles.Right | AnchorStyles.Top,
        };

        var miniTimeFont = new Font("Consolas", 7f);
        foreach (var slot in cam.Slots)
        {
            var miniPanel = new Panel
            {
                Width = miniW, Height = miniH,
                BackColor = Theme.Deep, Margin = new Padding(miniMargin),
            };

            var miniPb = new PictureBox
            {
                Left = 0, Top = 0, Width = miniW, Height = 66,
                SizeMode = PictureBoxSizeMode.StretchImage,
                BackColor = Color.FromArgb(15, 15, 30),
            };

            var miniState = new Label
            {
                Left = 2, Top = 67, Width = miniW - 4, Height = 18,
                Text = $"⬜ {slot.Name}", ForeColor = Theme.Dim,
                BackColor = Color.Transparent, Font = Theme.FSm,
                AutoEllipsis = true,
            };

            var miniTime = new Label
            {
                Left = 2, Top = 84, Width = miniW - 4, Height = 14,
                ForeColor = Color.FromArgb(100, 144, 144, 176),
                BackColor = Color.Transparent, Font = miniTimeFont,
            };

            miniPanel.Controls.AddRange([miniPb, miniState, miniTime]);
            miniFlow.Controls.Add(miniPanel);
            slotMinis[slot.Id] = new SlotMiniCard(miniPb, miniState, miniTime);
        }

        // ── Bottom buttons ────────────────────────────────────────────────
        int btnY = cardH - 30;

        var btnToggle = Theme.Btn("▶ Start", Theme.Ok);
        btnToggle.SetBounds(8, btnY, 86, 26);
        btnToggle.Anchor = AnchorStyles.Left | AnchorStyles.Bottom;
        btnToggle.Click += (_, _) => ToggleWorker(cam.Id);

        var btnOpenDir = Theme.Btn("📁 Ảnh", Theme.Navy);
        btnOpenDir.SetBounds(100, btnY, 80, 26);
        btnOpenDir.Anchor = AnchorStyles.Left | AnchorStyles.Bottom;
        btnOpenDir.Click += (_, _) => OpenCamFolder(cam.Id);

        var btnSlots = Theme.Btn("⬛ Slots", Theme.Card);
        btnSlots.ForeColor = hasSlots ? Theme.Warn : Theme.Dim;
        btnSlots.SetBounds(186, btnY, 80, 26);
        btnSlots.Anchor = AnchorStyles.Left | AnchorStyles.Bottom;
        btnSlots.Click += (_, _) => OpenSlotEditor(cam.Id);

        // ── Card click → select ───────────────────────────────────────────
        void SelectThis(object? s, EventArgs e) { _selectedCamId = cam.Id; HighlightSelectedCard(); }
        card.Click += SelectThis; lblName.Click += SelectThis; pb.Click += SelectThis;

        card.Controls.AddRange([
            dot, lblName, pb,
            lblState, lblConf, lblTime, lblMs,
            lblUrl, miniFlow,
            btnToggle, btnOpenDir, btnSlots,
        ]);

        return (card, new CardControls(pb, lblState, lblConf, lblTime, lblMs, dot, btnToggle, slotMinis));
    }

    private void HighlightSelectedCard()
    {
        foreach (Control c in _camPanel.Controls)
        {
            if (c is Panel p)
            {
                string? id = _cardCtls.FirstOrDefault(kv => ReferenceEquals(kv.Value.Pb.Parent, p)).Key;
                p.BackColor = id == _selectedCamId ? Theme.Navy : Theme.Card;
            }
        }
    }

    // ══════════════════════════════════════════════════════════════════════
    // TIMER — refresh cards + flush events
    // ══════════════════════════════════════════════════════════════════════

    private void OnTimerTick(object? s, EventArgs e)
    {
        foreach (var w in _workers)
        {
            if (!_cardCtls.TryGetValue(w.Config.Id, out var c)) continue;

            // Lấy slot statuses một lần — dùng chung cho vẽ box + badge
            var statuses = w.Config.Slots.Count > 0 ? w.GetSlotStatuses() : null;

            // Thumbnail + vẽ slot box
            var frame = w.GetFrameClone();
            if (frame is not null)
            {
                if (statuses is not null)
                    DrawSlotBoxes(frame, w.Config.Slots, statuses);
                var old = c.Pb.Image;
                c.Pb.Image = frame;
                old?.Dispose();
            }

            // Aggregate state label
            if (statuses is null)
            {
                (c.State.Text, c.State.ForeColor) = w.CurrentState switch
                {
                    SlotState.Empty    => ("🟢 TRỐNG",    Theme.Ok),
                    SlotState.Occupied => ("🔴 CÓ XE",    Theme.Err),
                    _                  => ("⬜ CHƯA BIẾT", Theme.Dim),
                };
            }
            else
            {
                int emptyN = statuses.Count(x => x.State == SlotState.Empty);
                int totalN = statuses.Count;
                c.State.Text      = $"🟢 {emptyN}/{totalN} trống";
                c.State.ForeColor = emptyN == totalN ? Theme.Ok :
                                    emptyN == 0      ? Theme.Err : Theme.Warn;

                // Per-slot mini-cards: cập nhật ảnh crop + state + time
                foreach (var ss in statuses)
                {
                    if (!c.SlotMinis.TryGetValue(ss.SlotId, out var mini)) continue;

                    // Ảnh crop
                    var crop = w.GetSlotCropClone(ss.SlotId);
                    if (crop is not null)
                    {
                        var old = mini.Pb.Image;
                        mini.Pb.Image = crop;
                        old?.Dispose();
                    }

                    // Trạng thái
                    (mini.StateLbl.Text, mini.StateLbl.ForeColor) = ss.State switch
                    {
                        SlotState.Empty    => ($"🟢 {ss.SlotName}", Theme.Ok),
                        SlotState.Occupied => ($"🔴 {ss.SlotName}", Theme.Err),
                        _                  => ($"⬜ {ss.SlotName}", Theme.Dim),
                    };

                    // Thời gian kiểm tra cuối
                    mini.TimeLbl.Text = ss.UpdatedAt != default
                        ? ss.UpdatedAt.ToString("HH:mm:ss")
                        : "";
                }
            }

            c.Conf.Text = w.LastConf > 0f ? $"Conf: {w.LastConf:P0}" : "";
            c.Time.Text = w.LastCheckTime != DateTime.MinValue ? w.LastCheckTime.ToString("HH:mm:ss") : "";
            c.Ms.Text   = w.LastDetectMs > 0 ? $"{w.LastDetectMs} ms" : "";
            c.Dot.ForeColor = w.IsRunning ? Theme.Ok : Theme.Dim;

            if (w.IsRunning && c.Toggle.Text.StartsWith("▶"))
                { c.Toggle.Text = "■ Stop";  c.Toggle.BackColor = Theme.Err; }
            else if (!w.IsRunning && c.Toggle.Text.StartsWith("■"))
                { c.Toggle.Text = "▶ Start"; c.Toggle.BackColor = Theme.Ok; }

            while (w.Events.TryDequeue(out var rec))
                AddEventRow(rec);
        }

        int running = _workers.Count(x => x.IsRunning);
        var shapeInfo = !string.IsNullOrEmpty(_yolo.LastOutputShapeInfo)
            ? $"  │  shape: {_yolo.LastOutputShapeInfo}" : "";
        _lblStatus.Text =
            $"Model: {(_yolo.IsLoaded ? Path.GetFileName(_yolo.ModelPath) : "chưa load")}  " +
            $"│  {_cfg.Cameras.Count} camera  │  {running} đang chạy{shapeInfo}";
    }

    // ── Vẽ slot box lên bitmap preview ───────────────────────────────────────

    private static readonly Font _boxFont = new("Segoe UI", 7.5f, FontStyle.Bold);

    private static void DrawSlotBoxes(Bitmap bmp, List<SlotBox> slots, List<SlotStatus> statuses)
    {
        var statusMap = statuses.ToDictionary(s => s.SlotId);
        using var g   = Graphics.FromImage(bmp);
        g.InterpolationMode  = System.Drawing.Drawing2D.InterpolationMode.NearestNeighbor;
        g.SmoothingMode      = System.Drawing.Drawing2D.SmoothingMode.AntiAlias;
        g.TextRenderingHint  = System.Drawing.Text.TextRenderingHint.ClearTypeGridFit;

        foreach (var slot in slots)
        {
            var rect = slot.ToPixelRect(bmp.Width, bmp.Height);
            statusMap.TryGetValue(slot.Id, out var ss);

            Color fill, border;
            switch (ss?.State)
            {
                case SlotState.Empty:
                    fill   = Color.FromArgb(55,  76, 175, 80);   // xanh mờ
                    border = Color.FromArgb(220, 76, 175, 80);
                    break;
                case SlotState.Occupied:
                    fill   = Color.FromArgb(55,  239, 83, 80);   // đỏ mờ
                    border = Color.FromArgb(220, 239, 83, 80);
                    break;
                default:
                    fill   = Color.FromArgb(35,  144, 144, 176); // xám mờ
                    border = Color.FromArgb(160, 144, 144, 176);
                    break;
            }

            // Fill mờ
            using (var b = new SolidBrush(fill))
                g.FillRectangle(b, rect);

            // Viền
            using (var p = new Pen(border, 1.8f))
                g.DrawRectangle(p, rect.X, rect.Y, rect.Width, rect.Height);

            // Label tên slot (nền đen mờ, chữ trắng)
            var label    = slot.Name;
            var textSize = g.MeasureString(label, _boxFont);
            float tx = rect.X + 3, ty = rect.Y + 2;
            using (var bg = new SolidBrush(Color.FromArgb(140, 0, 0, 0)))
                g.FillRectangle(bg, tx - 1, ty - 1, textSize.Width + 2, textSize.Height);
            using (var fg = new SolidBrush(Color.White))
                g.DrawString(label, _boxFont, fg, tx, ty);
        }
    }

    private void AddEventRow(StateChangeRecord rec)
    {
        var slotLabel = string.IsNullOrEmpty(rec.SlotName) ? "–" : rec.SlotName;
        var item = new ListViewItem(rec.OccurredAt.ToString("HH:mm:ss.fff"));
        item.SubItems.Add(rec.CameraName);
        item.SubItems.Add(slotLabel);
        item.SubItems.Add(StateLabel(rec.PrevState));
        item.SubItems.Add(StateLabel(rec.NewState));
        item.SubItems.Add($"{rec.Confidence:P0}");
        item.ForeColor = Theme.StateColor(rec.NewState);
        item.Tag       = rec;
        _lvEvents.Items.Insert(0, item);
        while (_lvEvents.Items.Count > 300) _lvEvents.Items.RemoveAt(_lvEvents.Items.Count - 1);
    }

    private static string StateLabel(string s) => s switch
    {
        "Empty"    => "🟢 Trống",
        "Occupied" => "🔴 Có xe",
        _          => s,
    };

    private void OnEventDoubleClick(object? s, EventArgs e)
    {
        if (_lvEvents.SelectedItems.Count == 0) return;
        var rec = (StateChangeRecord)_lvEvents.SelectedItems[0].Tag!;
        if (string.IsNullOrEmpty(rec.ImagePath) || !File.Exists(rec.ImagePath)) return;
        try { System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo(rec.ImagePath) { UseShellExecute = true }); }
        catch { }
    }

    // ══════════════════════════════════════════════════════════════════════
    // SLOT EDITOR
    // ══════════════════════════════════════════════════════════════════════

    private void OpenSlotEditor(string camId)
    {
        var cam = _cfg.Cameras.FirstOrDefault(c => c.Id == camId);
        if (cam is null) return;

        // Grab current frame from worker as background image
        var w     = _workers.FirstOrDefault(x => x.Config.Id == camId);
        var frame = w?.GetFrameClone();

        using var editor = new SlotBoxEditor(cam.Slots, frame);
        frame?.Dispose();

        if (editor.ShowDialog(this) != DialogResult.OK) return;

        // Save updated slots
        cam.Slots.Clear();
        cam.Slots.AddRange(editor.Result);
        _cfg.Save();

        // Rebuild cards to reflect new slots
        RebuildCards();
    }

    // ══════════════════════════════════════════════════════════════════════
    // MODEL
    // ══════════════════════════════════════════════════════════════════════

    private void OnBrowseModel(object? s, EventArgs e)
    {
        var choice = MessageBox.Show(
            "Yes → chọn FOLDER openvino_model/\nNo  → chọn FILE (.xml / .onnx)",
            "Chọn model", MessageBoxButtons.YesNoCancel, MessageBoxIcon.Question);
        if (choice == DialogResult.Yes)
        {
            using var d = new FolderBrowserDialog { Description = "Folder OpenVINO (chứa .xml)" };
            if (d.ShowDialog() == DialogResult.OK) { _cmbModel.Text = d.SelectedPath; OnLoadModel(s, e); }
        }
        else if (choice == DialogResult.No)
        {
            using var d = new OpenFileDialog { Filter = "Model|*.xml;*.onnx" };
            if (d.ShowDialog() == DialogResult.OK) { _cmbModel.Text = d.FileName; OnLoadModel(s, e); }
        }
    }

    private async void OnLoadModel(object? s, EventArgs e)
    {
        var path = _cmbModel.Text.Trim();
        if (string.IsNullOrEmpty(path)) return;

        SyncCfgFromUI();
        _btnLoadModel.Enabled  = false;
        _lblModelInfo.Text     = "⏳ Loading…";
        _lblModelInfo.ForeColor = Theme.Warn;
        SetStatus("Đang load model…");

        var device = _cmbDevice.SelectedItem?.ToString() ?? "CPU";
        try
        {
            await Task.Run(() => _yolo.LoadModel(path, device));
            _cfg.ModelPath = path;
            var names      = string.Join(", ", _yolo.ClassNames.Take(5));
            if (_yolo.ClassNames.Length > 5) names += "…";
            _lblModelInfo.Text      = $"✓  {Path.GetFileName(path)}  │  {_yolo.InputW}×{_yolo.InputH}  │  {_yolo.NumClasses} class: [{names}]  │  [{_yolo.ActualDevice}]";
            _lblModelInfo.ForeColor = Theme.Ok;
            SetStatus($"Model loaded — {_yolo.NumClasses} class [{_yolo.ActualDevice}]");
        }
        catch (Exception ex)
        {
            _lblModelInfo.Text      = $"✗  {ex.Message[..Math.Min(80, ex.Message.Length)]}";
            _lblModelInfo.ForeColor = Theme.Err;
            SetStatus("Lỗi load model.");
        }
        finally { _btnLoadModel.Enabled = true; }
    }

    // ══════════════════════════════════════════════════════════════════════
    // CAMERA MANAGEMENT
    // ══════════════════════════════════════════════════════════════════════

    private void OnAddCamera(object? s, EventArgs e)
    {
        using var dlg = new CameraEditForm();
        if (dlg.ShowDialog(this) != DialogResult.OK) return;
        _cfg.Cameras.Add(dlg.Result);
        _cfg.Save();
        RebuildCards();
    }

    private void OnEditCamera(object? s, EventArgs e)
    {
        var cam = GetSelectedCam();
        if (cam is null) { MessageBox.Show("Hãy click vào camera cần sửa trước."); return; }
        using var dlg = new CameraEditForm(cam);
        if (dlg.ShowDialog(this) != DialogResult.OK) return;
        // Preserve slots
        dlg.Result.Slots.AddRange(cam.Slots);
        int idx = _cfg.Cameras.FindIndex(c => c.Id == cam.Id);
        if (idx >= 0) _cfg.Cameras[idx] = dlg.Result;
        _cfg.Save();
        RebuildCards();
    }

    private void OnDeleteCamera(object? s, EventArgs e)
    {
        var cam = GetSelectedCam();
        if (cam is null) { MessageBox.Show("Hãy click vào camera cần xóa trước."); return; }
        if (MessageBox.Show($"Xóa camera '{cam.Name}'?", "Xác nhận",
            MessageBoxButtons.YesNo, MessageBoxIcon.Warning) != DialogResult.Yes) return;

        var w = _workers.FirstOrDefault(x => x.Config.Id == cam.Id);
        w?.Stop(); w?.Dispose();
        if (w is not null) _workers.Remove(w);
        _cfg.Cameras.RemoveAll(c => c.Id == cam.Id);
        _cfg.Save();
        _selectedCamId = null;
        RebuildCards();
    }

    private CameraConfig? GetSelectedCam() =>
        _selectedCamId is null ? null : _cfg.Cameras.FirstOrDefault(c => c.Id == _selectedCamId);

    private void ToggleWorker(string camId)
    {
        SyncCfgFromUI();
        var w = _workers.FirstOrDefault(x => x.Config.Id == camId);
        if (w is null) return;
        if (w.IsRunning) w.Stop(); else w.Start();
    }

    private void StartAll()
    {
        SyncCfgFromUI();
        foreach (var w in _workers) if (!w.IsRunning) w.Start();
    }

    private void StopAll() { foreach (var w in _workers) w.Stop(); }

    private void OpenPreviewWindow(string camId)
    {
        var w = _workers.FirstOrDefault(x => x.Config.Id == camId);
        var frame = w?.GetFrameClone();
        if (frame is null) { MessageBox.Show("Chưa có frame."); return; }

        var win = new Form
        {
            Text = $"Preview — {w!.Config.Name}", BackColor = Color.Black,
            Size = new Size(800, 600), StartPosition = FormStartPosition.CenterParent,
        };
        var pb2 = new PictureBox
        {
            Dock = DockStyle.Fill, SizeMode = PictureBoxSizeMode.Zoom,
            Image = frame, BackColor = Color.Black,
        };
        win.FormClosed += (_, _) => { pb2.Image?.Dispose(); };
        win.Controls.Add(pb2);
        win.Show(this);
    }

    private void OpenCamFolder(string camId)
    {
        var dir = Path.Combine(_cfg.ImageFolder, camId);
        Directory.CreateDirectory(dir);
        try { System.Diagnostics.Process.Start("explorer.exe", dir); } catch { }
    }

    // ══════════════════════════════════════════════════════════════════════
    // HELPERS
    // ══════════════════════════════════════════════════════════════════════

    private void OnBrowseFolder(object? s, EventArgs e)
    {
        using var d = new FolderBrowserDialog { Description = "Thư mục lưu ảnh sự kiện" };
        if (d.ShowDialog() == DialogResult.OK) _txtFolder.Text = d.SelectedPath;
    }

    private void SyncCfgFromUI()
    {
        _cfg.Conf            = (float)_nudConf.Value / 100f;
        _cfg.Iou             = (float)_nudIou.Value  / 100f;
        _cfg.IntervalSecs    = (int)_nudInterval.Value;
        _cfg.EmptyClassIndex = (int)_nudEmpty.Value;
        _cfg.ImageFolder     = _txtFolder.Text.Trim();
        _cfg.Device          = _cmbDevice.SelectedItem?.ToString() ?? "CPU";
    }

    private void RestoreSession()
    {
        _cmbModel.Text      = _cfg.ModelPath;
        _nudConf.Value      = (decimal)Math.Round(_cfg.Conf * 100);
        _nudIou.Value       = (decimal)Math.Round(_cfg.Iou  * 100);
        _nudInterval.Value  = _cfg.IntervalSecs;
        _nudEmpty.Value     = _cfg.EmptyClassIndex;
        _txtFolder.Text     = _cfg.ImageFolder;

        if (_cmbDevice.Items.Contains(_cfg.Device)) _cmbDevice.SelectedItem = _cfg.Device;

        if (!string.IsNullOrEmpty(_cfg.ModelPath) &&
            (File.Exists(_cfg.ModelPath) || Directory.Exists(_cfg.ModelPath)))
            OnLoadModel(this, EventArgs.Empty);
    }

    private void OnClose()
    {
        _timer.Stop();
        SyncCfgFromUI();
        _cfg.ModelPath = _cmbModel.Text;
        _cfg.Save();
        StopAll();
        foreach (var w in _workers) w.Dispose();
        _yolo.Dispose();
        _db.Dispose();
    }

    private void OnKeyDown(object? s, KeyEventArgs e)
    {
        if (e.KeyCode == Keys.Escape)             { StopAll(); e.Handled = true; }
        if (e.KeyCode == Keys.F5)                 { StartAll(); e.Handled = true; }
        if (e.Control && e.KeyCode == Keys.L)     { OnBrowseModel(s, e); e.Handled = true; }
    }

    private void SetStatus(string msg) => _lblStatus.Text = msg;

    private static Label MkLbl(string text, int x, int y) => new()
    {
        Text = text, Left = x, Top = y, AutoSize = true,
        ForeColor = Theme.Dim, BackColor = Color.Transparent, Font = Theme.FMain,
    };

    private static string ShortenUrl(string url) =>
        url.Length <= 50 ? url : url[..22] + "…" + url[^22..];

    protected override void Dispose(bool disposing)
    {
        if (disposing) _timer.Dispose();
        base.Dispose(disposing);
    }
}

// ── Extension để chuỗi builder gọn hơn ───────────────────────────────────────
internal static class ControlExt
{
    public static T Also<T>(this T ctrl, Action<T> action) where T : Control
        { action(ctrl); return ctrl; }
}
