@echo off
rem Runs SleekKeys from source (needs Python). Normal users just double-click SleekKeys.exe instead.
cd /d "%~dp0"
start "" pythonw sleekkeys.py --editor
