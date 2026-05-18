@echo off
echo Killing any process on port 8000...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000"') do (
    echo Killing PID %%a
    taskkill /F /PID %%a 2>nul
)
timeout /t 2 /nobreak >nul
echo Starting raid-fun backend (no reload)...
cd /d "%~dp0backend"
python -m uvicorn main:app --host 127.0.0.1 --port 8000
pause
