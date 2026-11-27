@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup-demo.ps1"
set "RESULT=%ERRORLEVEL%"
pause
exit /b %RESULT%
