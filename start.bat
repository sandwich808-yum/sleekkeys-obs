@echo off
title SleekKeys
cd /d "%~dp0"
echo Starting SleekKeys...  (close this window or press Ctrl+C to stop)
python sleekkeys.py --open
if errorlevel 1 pause
