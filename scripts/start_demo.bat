@echo off
REM Double-click or run from cmd. Passes any flags through, e.g.:  scripts\start_demo.bat -AllowMock
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_demo.ps1" %*
echo.
pause
