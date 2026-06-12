@echo off
chcp 65001 > nul
set "SCRIPT_DIR=%~dp0"
set "PYTHON=C:\Users\Administrator\AppData\Local\Programs\Python\Python314\python.exe"

if not exist "%PYTHON%" (
    echo [LOI] Khong tim thay Python tai:
    echo       %PYTHON%
    echo.
    echo Vui long cap nhat duong dan Python trong file run.bat
    pause
    exit /b 1
)

"%PYTHON%" "%SCRIPT_DIR%train-image-tool.py"

if errorlevel 1 (
    echo.
    echo [LOI] Chuong trinh ket thuc voi loi.
    pause
)
