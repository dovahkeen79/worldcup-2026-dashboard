@echo off
REM ===============================================================
REM  World Cup 2026 Match Analyser - one-click launcher
REM  Starts the dashboard server and opens it in your browser.
REM ===============================================================
cd /d "%~dp0"
title World Cup 2026 Dashboard

echo.
echo   Starting the World Cup 2026 Dashboard...
echo   A browser tab will open at http://127.0.0.1:5000
echo   Keep this window open while you use it. Close it (or press
echo   Ctrl+C) to stop the server.
echo.

REM Open the browser a few seconds after the server starts booting.
start "" cmd /c "ping 127.0.0.1 -n 4 >nul & start "" http://127.0.0.1:5000"

python app.py

echo.
echo   Server stopped. You can close this window.
pause
