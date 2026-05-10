@echo off
cd /d "%~dp0"

echo.
echo ================================================
echo   Emonote Server
echo ================================================
echo.
echo Starting... browser opens when server is ready.
echo To stop: press Ctrl+C
echo.

start /b powershell -NoProfile -WindowStyle Hidden -Command "do { Start-Sleep 1; try { $null = Invoke-WebRequest http://localhost:5000 -UseBasicParsing -TimeoutSec 1 -ErrorAction Stop; $up = $true } catch { $up = $false } } until ($up); Start-Process 'http://localhost:5000'"

C:\Python314\python.exe app.py

echo.
echo Server stopped.
pause
