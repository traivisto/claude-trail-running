@echo off
:: update-dashboard.bat
:: Refreshes training-dashboard.html from the latest activity-cache.csv.
:: Tries several ways to find Python on Windows.

cd /d "%~dp0"
echo Updating training dashboard...
echo.

:: Try the Windows Python Launcher first (installed with most Python versions)
where py >nul 2>&1
if %errorlevel% equ 0 (
    py update-dashboard.py
    goto :check
)

:: Try plain python
where python >nul 2>&1
if %errorlevel% equ 0 (
    python update-dashboard.py
    goto :check
)

:: Try python3
where python3 >nul 2>&1
if %errorlevel% equ 0 (
    python3 update-dashboard.py
    goto :check
)

:: Try common install paths
for %%P in (
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    "C:\Python313\python.exe"
    "C:\Python312\python.exe"
    "C:\Python311\python.exe"
) do (
    if exist %%P (
        %%P update-dashboard.py
        goto :check
    )
)

echo ERROR: Python not found.
echo.
echo Options:
echo   1. Install Python from https://python.org  (tick "Add to PATH")
echo   2. Open this folder in VS Code, open Terminal, and run:
echo         python update-dashboard.py
echo.
pause
exit /b 1

:check
if %errorlevel% neq 0 (
    echo.
    echo Script failed - see error above.
    pause
    exit /b 1
)
echo.
echo Done! Refresh training-dashboard.html in your browser.
pause
