@echo off
echo Clearing any UVICORN env vars that could force multi-worker...
set UVICORN_WORKERS=
set UVICORN_RELOAD=
set UVICORN_HOST=
set UVICORN_PORT=
set WEB_CONCURRENCY=

echo Killing any process listening on port 8000...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr "LISTEN" ^| findstr ":8000 "') do (
    echo Killing PID %%a
    taskkill /F /PID %%a 2>nul
)
timeout /t 3 /nobreak >nul

echo Starting raid-fun backend...
cd /d "%~dp0backend"
python run.py
pause
