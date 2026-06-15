@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo  ============================================================
echo    KZTEK Get Parking Image
echo    kztek.net  ^|  Hotline: 0988 637 099
echo  ============================================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo  [LOI] Khong tim thay Python. Cai Python 3.10+ roi thu lai.
    pause
    exit /b 1
)

python RunGetParkingImage.py
if errorlevel 1 (
    echo.
    echo  [LOI] Ung dung bi loi. Kiem tra lai Python va thu vien.
    pause
)
