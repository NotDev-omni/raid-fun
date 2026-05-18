@echo off
echo ================================================
echo  raid-fun — Push to GitHub
echo ================================================
echo.

cd /d "%~dp0"

:: Remove broken .git if present
if exist ".git\config.lock" del /f ".git\config.lock"

:: Initialize git (safe even if already initialized)
git init
git config user.email "seratoxgaming@gmail.com"
git config user.name "Omni"
git checkout -b main 2>nul || git branch -m master main 2>nul

:: Stage everything
git add .
git status

:: Commit
git commit -m "Initial commit — raid-fun deploy-ready" 2>nul || echo Already committed.

:: Set remote (replace URL below if different)
git remote remove origin 2>nul
git remote add origin https://github.com/NotDev-omni/raid-fun.git

:: Push
echo.
echo Pushing to GitHub...
git push -u origin main

echo.
echo ================================================
echo  Done! Check GitHub for your repo.
echo ================================================
pause
