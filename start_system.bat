@echo off
title He Thong Quan Ly Bai Giu Xe Thong Minh
color 0A

echo ============================================================
echo   KHOI DONG HE THONG QUAN LY BAI GIU XE THONG MINH
echo ============================================================
echo.

:: Di chuyen ve thu muc chua file bat nay
cd /d "%~dp0"

:: Kiem tra xem moi truong ao .venv co ton tai khong
if not exist ".venv\Scripts\python.exe" (
    echo [LOI] Khong tim thay moi truong ao .venv!
    echo Vui long kiem tra lai thu muc cai dat.
    pause
    exit /b
)

echo [1/2] Dang khoi dong Web Server & Camera...
start "" http://localhost:5000

echo [2/2] Dang chay ung dung... Nhan Ctrl+C de dung server.
echo.
.venv\Scripts\python.exe app.py

pause
