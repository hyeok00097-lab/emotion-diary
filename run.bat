@echo off
cd /d "%~dp0"

echo.
echo  ================================================
echo    Emonote - Emotion Diary Service
echo  ================================================
echo.
echo  Starting server...
echo  Browser will open automatically in a moment.
echo.
echo  To stop: close this window or press Ctrl+C
echo  ================================================
echo.

REM Open browser after 2-second delay
start /b cmd /c "timeout /t 2 /nobreak > nul && start http://localhost:5000"

C:\Python314\python.exe app.py

echo.
echo  Server stopped.
pause
