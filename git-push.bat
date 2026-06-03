@echo off
cd /d "%~dp0"
set /p MSG="Commit message: "
if "%MSG%"=="" (
    echo No message entered. Aborting.
    pause
    exit /b 1
)
git add .
git commit -m "%MSG%"
git push
pause
