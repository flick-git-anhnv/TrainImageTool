@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul

:: ================================================================
::  KZTEK Image Tools — Auto Build Script
::  File  : buildTool.bat
::  Output: dist\KZTEK-Image-Tools.exe
::  Chay  : Double-click hoac terminal trong thu muc 3.Tools\
:: ================================================================

set "SCRIPT_DIR=%~dp0"
set "PY_FILE=%SCRIPT_DIR%train-image-tool.py"
set "APP_NAME=KZTEK-Image-Tools"
set "DIST_DIR=%SCRIPT_DIR%dist"
set "BUILD_DIR=%SCRIPT_DIR%build"
set "SPEC_DIR=%SCRIPT_DIR%"

echo.
echo  ============================================================
echo    KZTEK IMAGE TOOLS  ^|  Auto Build to EXE
echo    kztek.net  ^|  github: kztek
echo  ============================================================
echo.

:: ── 1. Kiem tra file nguon ──────────────────────────────────────
if not exist "%PY_FILE%" (
    echo  [LOI] Khong tim thay file nguon:
    echo        %PY_FILE%
    pause & exit /b 1
)
echo  [OK]  Source : %PY_FILE%

:: ── 2. Kiem tra Python ─────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo  [LOI] Khong tim thay Python. Cai Python 3.10+ roi thu lai.
    pause & exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo  [OK]  %%v

:: ── 3. Kiem tra / cai PyInstaller ──────────────────────────────
python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo  [INFO] Chua co PyInstaller. Dang cai dat...
    pip install pyinstaller
    if errorlevel 1 (
        echo  [LOI] Cai PyInstaller that bai.
        pause & exit /b 1
    )
)
for /f "tokens=*" %%v in ('python -m PyInstaller --version 2^>^&1') do echo  [OK]  PyInstaller %%v

:: ── 4. Kiem tra / cai cac thu vien ─────────────────────────────
echo.
echo  [INFO] Kiem tra va cai dat thu vien can thiet...

python -c "import PIL" >nul 2>&1
if errorlevel 1 (
    echo  [INFO] Cai dat Pillow...
    pip install pillow
)

python -c "import cv2" >nul 2>&1
if errorlevel 1 (
    echo  [INFO] Cai dat opencv-python...
    pip install opencv-python-headless
)

python -c "import numpy" >nul 2>&1
if errorlevel 1 (
    echo  [INFO] Cai dat numpy...
    pip install numpy
)

python -c "import requests" >nul 2>&1
if errorlevel 1 (
    echo  [INFO] Cai dat requests...
    pip install requests
)

python -c "import win32com.client" >nul 2>&1
if errorlevel 1 (
    echo  [WARN] Chua co pywin32 (TTS Windows se bi tat). Dang cai...
    pip install pywin32
)

python -c "from gtts import gTTS" >nul 2>&1
if errorlevel 1 (
    echo  [WARN] Chua co gTTS (Google TTS se bi tat). Dang cai...
    pip install gtts
)

python -c "import tkinterdnd2" >nul 2>&1
if errorlevel 1 (
    echo  [WARN] Chua co tkinterdnd2 (Drag-and-drop se bi tat). Dang cai...
    pip install tkinterdnd2
)

python -c "from ultralytics import YOLO" >nul 2>&1
if errorlevel 1 (
    echo  [WARN] Chua co ultralytics (YOLO Detect se bi tat). Dang cai...
    pip install ultralytics
)

echo  [OK]  Tat ca thu vien san sang.

:: ── 5. Don dep build cu ────────────────────────────────────────
echo.
echo  [INFO] Don dep build cu...
if exist "%BUILD_DIR%"                 rmdir /s /q "%BUILD_DIR%"
if exist "%SPEC_DIR%%APP_NAME%.spec"   del /q "%SPEC_DIR%%APP_NAME%.spec"
echo  [OK]  Sach se.

:: ── 6. Chay PyInstaller ────────────────────────────────────────
echo.
echo  [BUILD] Dang build EXE (co the mat 3-5 phut)...
echo  [BUILD] Output: %DIST_DIR%\%APP_NAME%.exe
echo.

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
    --hidden-import "cv2" ^
    --hidden-import "numpy" ^
    --hidden-import "numpy.core._multiarray_umath" ^
    --hidden-import "numpy.core._multiarray_tests" ^
    --hidden-import "requests" ^
    --hidden-import "requests.adapters" ^
    --hidden-import "requests.auth" ^
    --hidden-import "win32com.client" ^
    --hidden-import "win32com.shell.shell" ^
    --hidden-import "pythoncom" ^
    --hidden-import "pywintypes" ^
    --hidden-import "gtts" ^
    --hidden-import "tkinterdnd2" ^
    --hidden-import "collections.abc" ^
    --hidden-import "tool" ^
    --hidden-import "tool.app" ^
    --hidden-import "tool.imports" ^
    --hidden-import "tool.settings" ^
    --hidden-import "tool.constants" ^
    --hidden-import "tool.ui_helpers" ^
    --hidden-import "tool.core_split" ^
    --hidden-import "tool.core_crop" ^
    --hidden-import "tool.core_gt" ^
    --hidden-import "tool.core_label_norm" ^
    --hidden-import "tool.core_rename" ^
    --hidden-import "tool.lotte_image" ^
    --hidden-import "tool.parkingv8_image" ^
    --hidden-import "tool.parkingv6_image" ^
    --hidden-import "tool.bad_image_viewer" ^
    --hidden-import "tool.lotte_consolidate" ^
    --hidden-import "tool.tab_split" ^
    --hidden-import "tool.tab_rename" ^
    --hidden-import "tool.tab_crop" ^
    --hidden-import "tool.tab_labelnorm" ^
    --hidden-import "tool.tab_bbox" ^
    --hidden-import "tool.tab_lotte" ^
    --hidden-import "tool.tab_parkingv8" ^
    --hidden-import "tool.tab_parkingv6" ^
    --hidden-import "tool.tab_checker" ^
    --hidden-import "tool.tab_stats" ^
    --hidden-import "tool.tab_plate_search" ^
    --hidden-import "tool.tab_yolo" ^
    --hidden-import "tool.tab_train" ^
    --hidden-import "tool.tab_ocr" ^
    --collect-submodules "win32com" ^
    --collect-all "tkinterdnd2" ^
    --collect-all "ultralytics" ^
    "%PY_FILE%"

if errorlevel 1 (
    echo.
    echo  ============================================================
    echo   [LOI] BUILD THAT BAI!
    echo   Xem log phia tren de biet nguyen nhan.
    echo   Goi y: chay lai voi --debug=all de xem chi tiet.
    echo  ============================================================
    pause & exit /b 1
)

:: ── 7. Ket qua ─────────────────────────────────────────────────
echo.
echo  ============================================================
echo   BUILD THANH CONG!
echo   EXE : %DIST_DIR%\%APP_NAME%.exe
echo  ============================================================
echo.

if exist "%DIST_DIR%\%APP_NAME%.exe" (
    for %%F in ("%DIST_DIR%\%APP_NAME%.exe") do (
        set "SIZE=%%~zF"
        set /a "SIZE_MB=!SIZE! / 1048576"
        echo  [INFO] Kich thuoc: !SIZE_MB! MB
    )
    echo.
    explorer "%DIST_DIR%"
) else (
    echo  [WARN] Khong tim thay EXE tai: %DIST_DIR%\%APP_NAME%.exe
)

pause
endlocal
