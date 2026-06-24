"""
gen_report_2406.py — Đọc kết quả training và tạo HTML report
Gọi bởi monitoring loop sau mỗi lần wakeup.
"""
import os, json, csv, datetime
from pathlib import Path

PROJECT   = r"K:/Software/1.PhanLoaiPhuongTienChuan/Model/VietAnh"
S1_NAME   = "kztek_train_2406_s1"
S2_NAME   = "kztek_train_2406"
LOG_FILE  = os.path.join(PROJECT, "kztek_train_2406_progress.json")
OUT_HTML  = r"K:/Software/3.Tools/docs/train/train-report-2406.html"
DATASET   = r"K:/Software/PhanLoaiPhuongTien-TrainDataset"

# ── Đọc progress JSON ────────────────────────────────────────────────────
progress = {}
if os.path.exists(LOG_FILE):
    with open(LOG_FILE, encoding="utf-8") as f:
        progress = json.load(f)

# ── Đọc results.csv ───────────────────────────────────────────────────────
def read_csv(path):
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({k.strip(): v.strip() for k, v in row.items()})
    return rows

s1_csv = os.path.join(PROJECT, S1_NAME, "results.csv")
s2_csv = os.path.join(PROJECT, S2_NAME, "results.csv")
s1_rows = read_csv(s1_csv)
s2_rows = read_csv(s2_csv)

# ── Dataset thống kê ──────────────────────────────────────────────────────
def count_files(p):
    p = Path(p)
    return len(list(p.glob("*.*"))) if p.exists() else 0

train_imgs = count_files(f"{DATASET}/train/images")
val_imgs   = count_files(f"{DATASET}/valid/images")
train_lbl  = count_files(f"{DATASET}/train/labels")

# ── Thời gian sinh báo cáo ────────────────────────────────────────────────
generated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def best_row(rows, key="metrics/mAP50(B)"):
    """Tìm row có mAP50 cao nhất."""
    if not rows:
        return None
    try:
        return max(rows, key=lambda r: float(r.get(key, 0) or 0))
    except Exception:
        return None

def fmt(val, pct=False, dec=4):
    try:
        v = float(val)
        if pct:
            return f"{v*100:.2f}%"
        return f"{v:.{dec}f}"
    except Exception:
        return str(val) if val else "—"

def status_badge(s1r, s2r, prog):
    if prog.get("training_complete"):
        return '<span style="color:#3fb950;font-weight:700">✅ HOÀN THÀNH</span>'
    stage = prog.get("stage", "")
    status = prog.get("status", "")
    if stage == "stage2" and status == "started":
        ep = len(s2r)
        return f'<span style="color:#f0a922;font-weight:700">🔄 Stage 2 — Epoch {ep}/60</span>'
    if stage == "stage1" and status == "started":
        ep = len(s1r)
        return f'<span style="color:#42a5f5;font-weight:700">🔄 Stage 1 — Epoch {ep}/30</span>'
    if stage == "stage1" and status == "done":
        return '<span style="color:#42a5f5;font-weight:700">✅ Stage 1 xong — Stage 2 chưa bắt đầu</span>'
    return '<span style="color:#8888a8">⏳ Chờ bắt đầu</span>'

def table_rows(rows, stage_label, color):
    if not rows:
        return f'<tr><td colspan="12" style="text-align:center;color:#8888a8;padding:20px">Chưa có dữ liệu — {stage_label} chưa chạy</td></tr>'
    html = ""
    for r in rows:
        ep = r.get("epoch", "")
        box_l  = fmt(r.get("train/box_loss"))
        cls_l  = fmt(r.get("train/cls_loss"))
        dfl_l  = fmt(r.get("train/dfl_loss"))
        prec   = fmt(r.get("metrics/precision(B)"), pct=True)
        rec    = fmt(r.get("metrics/recall(B)"), pct=True)
        map50  = fmt(r.get("metrics/mAP50(B)"), pct=True)
        map595 = fmt(r.get("metrics/mAP50-95(B)"), pct=True)
        vbox   = fmt(r.get("val/box_loss"))
        vcls   = fmt(r.get("val/cls_loss"))
        vdfl   = fmt(r.get("val/dfl_loss"))
        lr     = fmt(r.get("lr/pg0"), dec=6)
        # highlight last row
        style = f'style="background:rgba({color},.08)"' if r == rows[-1] else ""
        html += f"""<tr {style}>
          <td style="font-family:'Courier New',monospace;color:#8888a8">{ep}</td>
          <td>{box_l}</td><td>{cls_l}</td><td>{dfl_l}</td>
          <td style="color:#42a5f5">{prec}</td>
          <td style="color:#42a5f5">{rec}</td>
          <td style="color:#3fb950;font-weight:700">{map50}</td>
          <td style="color:#f0a922">{map595}</td>
          <td style="color:#8888a8">{vbox}</td>
          <td style="color:#8888a8">{vcls}</td>
          <td style="color:#8888a8">{vdfl}</td>
          <td style="font-family:'Courier New',monospace;font-size:11px;color:#8888a8">{lr}</td>
        </tr>\n"""
    return html

s1_best_row = best_row(s1_rows)
s2_best_row = best_row(s2_rows)

def kv(k, v, color="#e0e0f0"):
    return f'<div style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid #2e2e48"><span style="color:#8888a8">{k}</span><span style="color:{color};font-family:\'Courier New\',monospace;font-size:12px">{v}</span></div>'

# ── Generate HTML ──────────────────────────────────────────────────────────
html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<title>KZTEK Training Report — kztek_train_2406</title>
<style>
  :root {{
    --ground:#12121f;--card:#1a1a2c;--card2:#1f1f35;
    --border:#2e2e48;--text:#e0e0f0;--dim:#8888a8;
    --accent:#F05922;--accent2:#4A3F8C;
  }}
  *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:var(--ground);color:var(--text);
    font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;
    font-size:13px;line-height:1.6}}
  header{{background:var(--card);border-bottom:1px solid var(--border);
    padding:20px 36px;display:flex;align-items:center;gap:16px}}
  .logo{{font-family:'Courier New',monospace;font-size:20px;font-weight:900;color:var(--accent)}}
  .logo span{{font-size:9px;display:block;letter-spacing:4px;color:var(--dim)}}
  .hdiv{{width:1px;height:32px;background:var(--border)}}
  .htxt h1{{font-size:15px;font-weight:700}}
  .htxt p{{font-size:11px;color:var(--dim);font-family:'Courier New',monospace}}
  .status-chip{{margin-left:auto;padding:6px 16px;background:var(--ground);
    border:1px solid var(--border);border-radius:4px;font-size:13px}}
  main{{padding:24px 36px 50px;max-width:1400px}}
  .grid2{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:24px}}
  .grid3{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:24px}}
  .card{{background:var(--card);border:1px solid var(--border);border-radius:6px;padding:16px 18px}}
  .card-title{{font-size:10px;font-weight:700;text-transform:uppercase;
    letter-spacing:1.5px;color:var(--dim);margin-bottom:10px}}
  .big-num{{font-family:'Courier New',monospace;font-size:28px;font-weight:900;color:var(--accent)}}
  .big-lbl{{font-size:10px;color:var(--dim);text-transform:uppercase;letter-spacing:1px}}
  .sec{{margin-bottom:28px}}
  .sec-hdr{{display:flex;align-items:center;gap:8px;padding-bottom:6px;
    border-bottom:1px solid var(--border);margin-bottom:12px}}
  .sec-dot{{width:7px;height:7px;border-radius:50%;background:var(--accent)}}
  .sec-ttl{{font-size:11px;font-weight:700;text-transform:uppercase;
    letter-spacing:2px;color:var(--accent)}}
  .tbl-wrap{{overflow-x:auto}}
  table{{width:100%;border-collapse:collapse;font-size:12px}}
  thead th{{background:var(--card2);color:var(--dim);font-size:10px;font-weight:600;
    text-transform:uppercase;letter-spacing:1px;padding:7px 10px;
    text-align:left;border:1px solid var(--border);white-space:nowrap}}
  tbody tr{{border-bottom:1px solid var(--border)}}
  tbody tr:hover{{background:rgba(255,255,255,.02)}}
  tbody td{{padding:7px 10px;border-right:1px solid var(--border)}}
  tbody td:first-child{{border-left:1px solid var(--border)}}
  .param-table td:first-child{{color:var(--dim);width:200px}}
  .param-table td:last-child{{font-family:'Courier New',monospace;color:#a0c0ff}}
  footer{{border-top:1px solid var(--border);padding:14px 36px;
    display:flex;justify-content:space-between;font-size:11px;
    color:var(--dim);font-family:'Courier New',monospace}}
</style>
</head>
<body>
<header>
  <div class="logo">KZ<span>TEK</span></div>
  <div class="hdiv"></div>
  <div class="htxt">
    <h1>Training Report — kztek_train_2406</h1>
    <p>yolo11n · PhanLoaiPhuongTien · 90 epochs · 2-Stage · 2026-06-24</p>
  </div>
  <div class="status-chip">{status_badge(s1_rows, s2_rows, progress)}</div>
</header>

<main>

<!-- KPI ROW -->
<div class="grid3" style="margin-top:20px">
  <div class="card">
    <div class="card-title">Stage 1 — Best mAP50</div>
    <div class="big-num">{fmt(s1_best_row.get("metrics/mAP50(B)","0") if s1_best_row else "0", pct=True)}</div>
    <div class="big-lbl">Epoch {s1_best_row.get("epoch","—") if s1_best_row else "—"} / 30 · Freeze backbone</div>
  </div>
  <div class="card">
    <div class="card-title">Stage 2 — Best mAP50</div>
    <div class="big-num" style="color:#3fb950">{fmt(s2_best_row.get("metrics/mAP50(B)","0") if s2_best_row else "0", pct=True)}</div>
    <div class="big-lbl">Epoch {s2_best_row.get("epoch","—") if s2_best_row else "—"} / 60 · Full fine-tune</div>
  </div>
  <div class="card">
    <div class="card-title">Stage 2 — Best mAP50-95</div>
    <div class="big-num" style="color:#f0a922">{fmt(s2_best_row.get("metrics/mAP50-95(B)","0") if s2_best_row else "0", pct=True)}</div>
    <div class="big-lbl">Precision {fmt(s2_best_row.get("metrics/precision(B)","0") if s2_best_row else "0", pct=True)} · Recall {fmt(s2_best_row.get("metrics/recall(B)","0") if s2_best_row else "0", pct=True)}</div>
  </div>
</div>

<!-- INPUT CONFIG -->
<div class="sec">
  <div class="sec-hdr"><div class="sec-dot"></div><span class="sec-ttl">Input — Cấu hình Training</span></div>
  <div class="grid2">
    <div class="card">
      <div class="card-title">Dataset</div>
      <table class="param-table"><tbody>
        <tr><td>Path</td><td>{DATASET}</td></tr>
        <tr><td>Train images</td><td>{train_imgs:,}</td></tr>
        <tr><td>Val images</td><td>{val_imgs:,}</td></tr>
        <tr><td>Train labels</td><td>{train_lbl:,}</td></tr>
        <tr><td>Classes (nc=6)</td><td>car · motorcycle · bus · truck · bicycle · license_plate</td></tr>
        <tr><td>Format</td><td>YOLO normalized (cx,cy,w,h)</td></tr>
      </tbody></table>
    </div>
    <div class="card">
      <div class="card-title">Model &amp; Output</div>
      <table class="param-table"><tbody>
        <tr><td>Base model</td><td>yolo11n.pt (nano, ~2.6M params)</td></tr>
        <tr><td>Architecture</td><td>YOLO11 — CSP backbone + SPPF + C2f</td></tr>
        <tr><td>Input size</td><td>640×640</td></tr>
        <tr><td>Stage 1 output</td><td>{PROJECT}/{S1_NAME}/weights/best.pt</td></tr>
        <tr><td>Stage 2 output</td><td>{PROJECT}/{S2_NAME}/weights/best.pt</td></tr>
      </tbody></table>
    </div>
  </div>
</div>

<!-- HYPERPARAMETERS -->
<div class="sec">
  <div class="sec-hdr"><div class="sec-dot"></div><span class="sec-ttl">Hyperparameters</span></div>
  <div class="grid2">
    <div class="card">
      <div class="card-title">Stage 1 — Freeze Backbone (epoch 1–30)</div>
      <table class="param-table"><tbody>
        <tr><td>epochs</td><td>30</td></tr>
        <tr><td>freeze</td><td>10 layers (backbone)</td></tr>
        <tr><td>lr0</td><td>0.001 (bảo vệ pretrained features)</td></tr>
        <tr><td>cos_lr</td><td>True</td></tr>
        <tr><td>amp</td><td>True (FP16)</td></tr>
        <tr><td>batch</td><td>-1 (auto)</td></tr>
        <tr><td>label_smoothing</td><td>0.1</td></tr>
        <tr><td>cls</td><td>1.5</td></tr>
        <tr><td>warmup_epochs</td><td>3</td></tr>
        <tr><td>mosaic / mixup / copy_paste</td><td>0 / 0 / 0 (tắt)</td></tr>
        <tr><td>degrees</td><td>0° (tắt)</td></tr>
        <tr><td>patience</td><td>30 (early stop)</td></tr>
      </tbody></table>
    </div>
    <div class="card">
      <div class="card-title">Stage 2 — Full Fine-tune (epoch 1–60)</div>
      <table class="param-table"><tbody>
        <tr><td>epochs</td><td>60</td></tr>
        <tr><td>freeze</td><td>0 (unfreeze toàn bộ)</td></tr>
        <tr><td>lr0</td><td>0.0005 (thấp hơn stage 1)</td></tr>
        <tr><td>cos_lr</td><td>True</td></tr>
        <tr><td>amp</td><td>True (FP16)</td></tr>
        <tr><td>batch</td><td>-1 (auto)</td></tr>
        <tr><td>label_smoothing</td><td>0.1</td></tr>
        <tr><td>cls</td><td>1.5</td></tr>
        <tr><td>warmup_epochs</td><td>3</td></tr>
        <tr><td>mosaic / mixup / copy_paste</td><td>1.0 / 0.15 / 0.1</td></tr>
        <tr><td>degrees</td><td>10° (rotation aug)</td></tr>
        <tr><td>patience</td><td>30 (early stop)</td></tr>
      </tbody></table>
    </div>
  </div>
</div>

<!-- STAGE 1 RESULTS TABLE -->
<div class="sec">
  <div class="sec-hdr"><div class="sec-dot" style="background:#42a5f5"></div>
    <span class="sec-ttl" style="color:#42a5f5">Stage 1 — Per-epoch Metrics (freeze backbone)</span>
    <span style="margin-left:auto;font-family:'Courier New',monospace;font-size:11px;color:var(--dim)">{len(s1_rows)}/30 epochs</span>
  </div>
  <div class="tbl-wrap">
    <table>
      <thead><tr>
        <th>Epoch</th><th>Train Box↓</th><th>Train Cls↓</th><th>Train DFL↓</th>
        <th>Precision↑</th><th>Recall↑</th><th>mAP50↑</th><th>mAP50-95↑</th>
        <th>Val Box↓</th><th>Val Cls↓</th><th>Val DFL↓</th><th>LR</th>
      </tr></thead>
      <tbody>{table_rows(s1_rows, "Stage 1", "66,165,245")}</tbody>
    </table>
  </div>
</div>

<!-- STAGE 2 RESULTS TABLE -->
<div class="sec">
  <div class="sec-hdr"><div class="sec-dot" style="background:#3fb950"></div>
    <span class="sec-ttl" style="color:#3fb950">Stage 2 — Per-epoch Metrics (full fine-tune)</span>
    <span style="margin-left:auto;font-family:'Courier New',monospace;font-size:11px;color:var(--dim)">{len(s2_rows)}/60 epochs</span>
  </div>
  <div class="tbl-wrap">
    <table>
      <thead><tr>
        <th>Epoch</th><th>Train Box↓</th><th>Train Cls↓</th><th>Train DFL↓</th>
        <th>Precision↑</th><th>Recall↑</th><th>mAP50↑</th><th>mAP50-95↑</th>
        <th>Val Box↓</th><th>Val Cls↓</th><th>Val DFL↓</th><th>LR</th>
      </tr></thead>
      <tbody>{table_rows(s2_rows, "Stage 2", "63,185,80")}</tbody>
    </table>
  </div>
</div>

<!-- TRAINING STATUS -->
<div class="sec">
  <div class="sec-hdr"><div class="sec-dot"></div><span class="sec-ttl">Trạng thái training</span></div>
  <div class="card" style="max-width:600px">
    {kv("Stage hiện tại", progress.get("stage", "—"))}
    {kv("Status", progress.get("status", "—"))}
    {kv("Timestamp", progress.get("timestamp", "—"))}
    {kv("Stage 1 best weights", progress.get("best", "—") if progress.get("stage")=="stage1" else (progress.get("stage1_weights","—") if progress.get("stage")=="stage2" else "—"))}
    {kv("Báo cáo sinh lúc", generated_at, "#F05922")}
  </div>
</div>

</main>
<footer>
  <span>docs/train/train-report-2406.html</span>
  <span>Generated {generated_at}</span>
  <span style="color:var(--accent)">kztek.net</span>
</footer>
</body>
</html>"""

os.makedirs(os.path.dirname(OUT_HTML), exist_ok=True)
with open(OUT_HTML, "w", encoding="utf-8") as f:
    f.write(html)

print(f"[REPORT] Generated -> {OUT_HTML}")
print(f"  Stage 1: {len(s1_rows)} epochs, best mAP50 = {fmt(s1_best_row.get('metrics/mAP50(B)','0') if s1_best_row else '0', pct=True)}")
print(f"  Stage 2: {len(s2_rows)} epochs, best mAP50 = {fmt(s2_best_row.get('metrics/mAP50(B)','0') if s2_best_row else '0', pct=True)}")
print(f"  Status  : {progress.get('stage','—')} / {progress.get('status','—')}")
