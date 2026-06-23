@echo off
chcp 65001 >nul
echo KZTEK — Build iParking Image Collector (C#)

dotnet build -c Release
if %ERRORLEVEL% NEQ 0 (
    echo [FAIL] Build failed.
    pause
    exit /b 1
)

echo.
echo [OK] Build thanh cong.
echo.
echo De publish thanh file exe don:
echo   dotnet publish -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true
echo.
pause
