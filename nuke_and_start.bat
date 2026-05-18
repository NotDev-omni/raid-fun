@echo off
echo Killing ALL Python processes...
taskkill /F /IM python.exe /T 2>nul
taskkill /F /IM python3.exe /T 2>nul
echo Waiting 3 seconds for port to release...
timeout /t 3 /nobreak >nul
echo Starting raid-fun backend (clean start)...
cd /d "%~dp0backend"
python -m uvicorn main:app --host 127.0.0.1 --port 8000
pause
