@echo off
cd /d "%~dp0"
if exist .venv\Scripts\python.exe goto install
py -3.12 -m venv .venv
if errorlevel 1 goto failed
:install
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto failed
echo.
echo Open http://127.0.0.1:8002 in your browser.
echo Keep this window open. Press Ctrl+C to stop.
.venv\Scripts\python.exe run.py
pause
exit /b
:failed
echo Setup failed. Read the error above and README.md.
pause
exit /b 1
