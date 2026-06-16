@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul

:: ================================================================
::  KZTEK Slot Detect — Auto Build Script
::  File  : buildSlotDetect.bat
::  Output: dist\KZTEK-Slot-Detect.exe
::  Chay  : Double-click hoac terminal trong thu muc 3.Tools\
:: ================================================================

if /i "%~1"=="__inner__" goto :MAIN
start "KZTEK Slot Detect — Build" cmd /k "%~f0" __inner__
exit /b

:MAIN
set "SCRIPT_DIR=%~dp0"
set "PY_FILE=%SCRIPT_DIR%SlotDetect.py"
set "APP_NAME=KZTEK-Slot-Detect"
set "DIST_DIR=%SCRIPT_DIR%dist"
set "BUILD_DIR=%SCRIPT_DIR%build"
set "SPEC_DIR=%SCRIPT_DIR%"
set "LOGFILE=%SCRIPT_DIR%build_slot_detect_log.txt"

echo [%date% %time%] Build started > "%LOGFILE%"

echo.
echo  ============================================================
echo    KZTEK SLOT DETECT  ^|  Auto Build to EXE
echo    kztek.net  ^|  Phan loai o do xe
echo  ============================================================
echo.

:: ── 1. Kiem tra file nguon ──────────────────────────────────────
if not exist "%PY_FILE%" (
    echo  [LOI] Khong tim thay file nguon: %PY_FILE%
    echo [LOI] File nguon khong ton tai: %PY_FILE% >> "%LOGFILE%"
    pause
    exit /b 1
)
echo  [OK]  Source : %PY_FILE%

:: ── 2. Kiem tra Python ─────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo  [LOI] Khong tim thay Python. Cai Python 3.10+ roi thu lai.
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do (
    echo  [OK]  %%v
    echo [OK] %%v >> "%LOGFILE%"
)

:: ── 3. Kiem tra / cai PyInstaller ──────────────────────────────
python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo  [INFO] Chua co PyInstaller. Dang cai dat...
    pip install pyinstaller
    if errorlevel 1 (
        echo  [LOI] Cai PyInstaller that bai.
        pause
        exit /b 1
    )
)
for /f "tokens=*" %%v in ('python -m PyInstaller --version 2^>^&1') do (
    echo  [OK]  PyInstaller %%v
)

:: ── 4. Kiem tra / cai cac thu vien ─────────────────────────────
echo.
echo  [INFO] Kiem tra thu vien...

python -c "import PIL" >nul 2>&1
if errorlevel 1 ( echo  [INFO] Cai dat Pillow... & pip install pillow )

python -c "import torch" >nul 2>&1
if errorlevel 1 ( echo  [WARN] Cai dat torch... & pip install torch --index-url https://download.pytorch.org/whl/cpu )

python -c "import yolov5" >nul 2>&1
if errorlevel 1 ( echo  [WARN] Cai dat yolov5... & pip install yolov5 )

python -c "from ultralytics import YOLO" >nul 2>&1
if errorlevel 1 ( echo  [WARN] Cai dat ultralytics... & pip install ultralytics )

python -c "import tkinterdnd2" >nul 2>&1
if errorlevel 1 ( echo  [WARN] Cai dat tkinterdnd2... & pip install tkinterdnd2 )

echo  [OK]  Thu vien san sang.

:: ── 5. Don dep build cu ────────────────────────────────────────
echo.
echo  [INFO] Don dep build cu...
if exist "%BUILD_DIR%\%APP_NAME%"        rmdir /s /q "%BUILD_DIR%\%APP_NAME%"
if exist "%SPEC_DIR%%APP_NAME%.spec"     del /q "%SPEC_DIR%%APP_NAME%.spec"
echo  [OK]  Sach se.

:: ── 6. Chay PyInstaller ────────────────────────────────────────
echo.
echo  [BUILD] Dang build EXE (co the mat 3-5 phut)...
echo  [BUILD] Output: %DIST_DIR%\%APP_NAME%.exe
echo.
echo [%date% %time%] PyInstaller start >> "%LOGFILE%"

python -m PyInstaller ^
    --onefile ^
    --noconsole ^
    --name "%APP_NAME%" ^
    --distpath "%DIST_DIR%" ^
    --workpath "%BUILD_DIR%" ^
    --specpath "%SPEC_DIR%" ^
    --hidden-import "PIL._tkinter_finder" ^
    --hidden-import "PIL.Image" ^
    --hidden-import "PIL.ImageTk" ^
    --hidden-import "PIL.BmpImagePlugin" ^
    --hidden-import "PIL.JpegImagePlugin" ^
    --hidden-import "PIL.PngImagePlugin" ^
    --hidden-import "PIL.WebPImagePlugin" ^
    --hidden-import "numpy" ^
    --hidden-import "numpy.core._multiarray_umath" ^
    --hidden-import "tkinterdnd2" ^
    --hidden-import "torch" ^
    --hidden-import "torch.hub" ^
    --hidden-import "yolov5" ^
    --hidden-import "ultralytics" ^
    --hidden-import "collections.abc" ^
    --collect-all "tkinterdnd2" ^
    --collect-all "yolov5" ^
    --collect-all "ultralytics" ^
    "%PY_FILE%"

set "BUILD_ERR=%errorlevel%"
echo [%date% %time%] PyInstaller exit code: %BUILD_ERR% >> "%LOGFILE%"

if %BUILD_ERR% neq 0 (
    echo.
    echo  ============================================================
    echo   [LOI] BUILD THAT BAI!  ^(exit code: %BUILD_ERR%^)
    echo   Xem log phia tren de biet nguyen nhan.
    echo  ============================================================
    echo [LOI] BUILD THAT BAI - exit code %BUILD_ERR% >> "%LOGFILE%"
    pause
    exit /b 1
)

:: ── 7. Ket qua ─────────────────────────────────────────────────
echo.
echo  ============================================================
echo   BUILD THANH CONG!
echo   EXE : %DIST_DIR%\%APP_NAME%.exe
echo  ============================================================
echo.
echo [OK] BUILD THANH CONG >> "%LOGFILE%"

if exist "%DIST_DIR%\%APP_NAME%.exe" (
    for %%F in ("%DIST_DIR%\%APP_NAME%.exe") do (
        set "SIZE=%%~zF"
        set /a "SIZE_MB=!SIZE! / 1048576"
        echo  [INFO] Kich thuoc: !SIZE_MB! MB
    )
    echo.
    explorer "%DIST_DIR%"
)

pause
endlocal
