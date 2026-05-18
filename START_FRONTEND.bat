@echo off
title raid-fun — Frontend [http://localhost:5500]
color 0B
echo.
echo  raid-fun // frontend starting...
echo  Open your browser at: http://localhost:5500
echo.

cd /d "%~dp0frontend"

:: Try Python server
python --version >nul 2>&1
if not errorlevel 1 (
    echo  Serving frontend on http://localhost:5500
    echo  Press Ctrl+C to stop.
    echo.
    python -m http.server 5500
    goto :end
)

echo  [ERR] Python not found.
echo  Open frontend\index.html manually or install a static server.
pause

:end
