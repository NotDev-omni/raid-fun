@echo off
cd /d "%~dp0backend"
echo Starting raid-fun backend...
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --workers 1
pause
