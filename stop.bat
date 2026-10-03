@echo off
curl.exe -s -m 2 -X POST -H "X-SleekKeys: 1" http://127.0.0.1:7878/api/quit
echo.
echo SleekKeys stop requested.
timeout /t 2 >nul
