@echo off
title raid-fun — Setup
color 0B
echo.
echo  ██████╗  █████╗ ██╗██████╗       ███████╗██╗   ██╗███╗   ██╗
echo  ██╔══██╗██╔══██╗██║██╔══██╗      ██╔════╝██║   ██║████╗  ██║
echo  ██████╔╝███████║██║██║  ██║█████╗█████╗  ██║   ██║██╔██╗ ██║
echo  ██╔══██╗██╔══██║██║██║  ██║╚════╝██╔══╝  ██║   ██║██║╚██╗██║
echo  ██║  ██║██║  ██║██║██████╔╝      ██║     ╚██████╔╝██║ ╚████║
echo  ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚═════╝       ╚═╝      ╚═════╝ ╚═╝  ╚═══╝
echo.
echo  Setting up raid-fun backend...
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERR] Python not found. Download from https://python.org and re-run this.
    pause
    exit /b 1
)

:: Navigate to backend
cd /d "%~dp0backend"

:: Create virtual environment
echo  [1/3] Creating virtual environment...
python -m venv venv
if errorlevel 1 (
    echo  [ERR] Failed to create venv.
    pause
    exit /b 1
)

:: Activate and install
echo  [2/3] Installing dependencies (this takes ~1 minute)...
call venv\Scripts\activate.bat
pip install -r requirements.txt -q
if errorlevel 1 (
    echo  [ERR] pip install failed.
    pause
    exit /b 1
)

:: Create .env if it doesn't exist
if not exist .env (
    copy .env.example .env >nul
    echo  [3/3] Created .env file — OPEN IT AND FILL IN YOUR DISCORD CREDENTIALS
    echo.
    echo  ============================================================
    echo   REQUIRED: Open raid-fun\backend\.env and set:
    echo     DISCORD_CLIENT_ID=your_client_id_here
    echo     DISCORD_CLIENT_SECRET=your_client_secret_here
    echo  ============================================================
    echo.
    :: Open .env in notepad automatically
    start notepad .env
) else (
    echo  [3/3] .env already exists — skipping.
)

echo.
echo  Setup complete. Fill in .env then run START_BACKEND.bat
echo.
pause
