@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul

:: ================================================================
::  KZTEK Image Tools — Build Script
::  File  : buildTool.bat
::  Output: dist\KZTEK-Image-Tools.exe
::  Chay  : Click doi hoac tu terminal trong thu muc 3.Tools\
:: ================================================================

set "SCRIPT_DIR=%~dp0"
set "PY_FILE=%SCRIPT_DIR%train-image-tool.py"
set "APP_NAME=KZTEK-Image-Tools"
set "DIST_DIR=%SCRIPT_DIR%dist"
set "BUILD_DIR=%SCRIPT_DIR%build"
set "SPEC_DIR=%SCRIPT_DIR%"

echo.
echo  ============================================================
echo    KZTEK IMAGE TOOLS  ^|  Build to EXE
echo    kztek.net
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
    echo  [LOI] Khong tim thay Python. Cai Python 3.x roi thu lai.
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

:: ── 4. Kiem tra / cai cac thu vien can thiet ───────────────────
echo.
echo  [INFO] Kiem tra thu vien...

python -c "import PIL" >nul 2>&1
if errorlevel 1 (
    echo  [INFO] Cai dat Pillow...
    pip install pillow
)

python -c "import win32com.client" >nul 2>&1
if errorlevel 1 (
    echo  [WARN] Chua co pywin32 (TTS se bi tat). Dang cai...
    pip install pywin32
)

python -c "from gtts import gTTS" >nul 2>&1
if errorlevel 1 (
    echo  [WARN] Chua co gTTS (Google TTS se bi tat). Dang cai...
    pip install gtts
)

echo  [OK]  Tat ca thu vien san sang.

:: ── 5. Don dep build cu ────────────────────────────────────────
echo.
echo  [INFO] Don dep build cu...
if exist "%BUILD_DIR%"            rmdir /s /q "%BUILD_DIR%"
if exist "%SPEC_DIR%%APP_NAME%.spec" del /q "%SPEC_DIR%%APP_NAME%.spec"
echo  [OK]  Sach se.

:: ── 6. Chay PyInstaller ────────────────────────────────────────
echo.
echo  [BUILD] Dang build EXE...
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
    --hidden-import "win32com.client" ^
    --hidden-import "win32com.shell.shell" ^
    --hidden-import "pythoncom" ^
    --hidden-import "pywintypes" ^
    --hidden-import "gtts" ^
    --hidden-import "collections.abc" ^
    --collect-submodules win32com ^
    "%PY_FILE%"

if errorlevel 1 (
    echo.
    echo  ============================================================
    echo   [LOI] BUILD THAT BAI!
    echo   Xem log phia tren de biet nguyen nhan.
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

:: Mo thu muc dist
if exist "%DIST_DIR%\%APP_NAME%.exe" (
    explorer "%DIST_DIR%"
) else (
    echo  [WARN] Khong tim thay EXE dau ra tai %DIST_DIR%
)

pause
endlocal
