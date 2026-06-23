# KZTEK — iParking Image Collector (C#)

Thu thập ảnh từ hệ thống iParking: **LotteImage**, **Parkingv8**, **Parkingv6**.

## Cấu trúc project

```
IParkingImageCSharp/
├── Program.cs                  ← Entry point, CLI args, parallel runner
├── appsettings.json            ← Cấu hình mặc định (chỉnh sửa trước khi chạy)
├── IParkingImageCSharp.csproj
├── Config/
│   └── AppConfig.cs            ← Model cấu hình (LotteConfig, P8Config, P6Config)
├── Models/
│   ├── WorkerStats.cs          ← Thống kê, LaneCounters (thread-safe)
│   └── VehicleType.cs          ← Phân loại xe, đường dẫn ảnh, helper
├── Workers/
│   ├── BaseWorker.cs           ← Abstract base (filter, save, log)
│   ├── LotteWorker.cs          ← iParking Lotte (API login + MinIO)
│   ├── Parkingv8Worker.cs      ← Parkingv8 (OAuth2 + PresignedUrl/Base64)
│   └── Parkingv6Worker.cs      ← Parkingv6 (Bearer token + MinIO fileKeys)
└── Helpers/
    ├── ApiHelper.cs            ← HTTP client, auth, image download, MinIO
    └── FileHelper.cs           ← Đường dẫn, lịch sử ngày, lưu file
```

## Build & chạy

```bash
# Build
dotnet build

# Chạy với appsettings.json mặc định
dotnet run

# Chỉ định config file khác
dotnet run -- --config myconfig.json

# Override từ CLI
dotnet run -- --source LotteImage --from "2026-01-01" --to "2026-01-31" --out D:/images

# Publish thành exe đơn
dotnet publish -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true
```

## Cấu hình `appsettings.json`

| Tham số | Mô tả |
|---|---|
| `Source` | `LotteImage` \| `Parkingv8` \| `Parkingv6` |
| `FromDate` | Từ ngày (UTC) — `"2026-01-01 00:00:00"` |
| `ToDate` | Đến ngày (UTC) |
| `OutputDir` | Thư mục lưu ảnh |
| `PageSize` | Số bản ghi mỗi trang API |
| `MaxPages` | Giới hạn số trang mỗi ngày (0=không giới hạn) |
| `SleepSeconds` | Nghỉ giữa các request (giây) |
| `MaxPerLane` | Giới hạn tổng ảnh/làn (0=không giới hạn) |
| `MaxPerCategory` | Giới hạn ảnh/ngày/loại/làn |
| `MaxPerBuoi` | Giới hạn ảnh/buổi/loại/làn |
| `Parallel` | Số luồng song song (chia ngày) |
| `CollectBad` | `true` = lưu ảnh xấu vào thư mục `bad/` |
| `OnlyGT` | `true` = chỉ lấy ảnh có GT (biển vào=ra) |
| `AllowedVtypes` | Danh sách loại xe cần lấy, ví dụ `["o_to","xe_may"]` |

## Cấu trúc thư mục ảnh đầu ra

```
<OutputDir>/
  o_to/
    anh_toan_canh/<date>/<sang|trua|chieu|toi>/<lane>/HHmmss_BSX.jpg
    anh_xe/       <date>/<buoi>/<lane>/HHmmss_BSX.jpg
    anh_bsx/      <date>/<buoi>/<lane>/HHmmss_BSX.jpg
  xe_may/  (tương tự)
  xe_dap/  (tương tự)
  bad/<lane>/HHmmss_reason_BSX.jpg
  .lotte_done.json   ← lịch sử ngày đã tải (LotteImage)
  .p8_done.json      ← lịch sử (Parkingv8)
  .p6_done.json      ← lịch sử (Parkingv6)
```

## Ghi chú

- **Ctrl+C** để dừng gracefully — lịch sử ngày đã lưu sẽ được giữ lại
- Chạy lại sau khi dừng sẽ bỏ qua ngày đã tải (resume)
- Parkingv6 cần nhập `Token` trong `appsettings.json` (không tự đăng nhập)
- MinIO: để `UseMinIO: false` nếu server trả về URL trực tiếp
