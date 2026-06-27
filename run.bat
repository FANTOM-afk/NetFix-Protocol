@echo off
echo Running NetFixProtocol...
cd /d "%~dp0"
python main.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ======================
    echo ERROR: App exited with code %ERRORLEVEL%
    echo Check error_log.txt for details
    echo ======================
    pause
)
pause
