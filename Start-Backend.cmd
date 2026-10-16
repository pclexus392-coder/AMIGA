@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Jalankan Setup-Backend.cmd terlebih dahulu.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m backend.manage doctor
if errorlevel 1 (
  echo Konfigurasi database tidak valid. Perbaiki backend\.env terlebih dahulu.
  pause
  exit /b 1
)
echo AMIGA dan dua portal: http://localhost:5000/login
echo Alternatif loopback: http://127.0.0.1:5000/login
echo Buat passwordmu sendiri pada halaman aktivasi yang akan terbuka.
".venv\Scripts\python.exe" -m backend.manage serve --open-browser --reload
pause
