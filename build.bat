@echo off
rem Builds SleekKeys.exe (a single file with Python inside, so nobody needs to install anything).
rem Needs Python 3.10+ on this PC. Output: dist\SleekKeys.exe
cd /d "%~dp0"
if not exist .venv-build ( python -m venv .venv-build || goto :fail )
.venv-build\Scripts\python -m pip install --quiet --upgrade pip pyinstaller pillow || goto :fail
.venv-build\Scripts\python tools\make_icon.py || goto :fail
.venv-build\Scripts\python -m PyInstaller --noconfirm --onefile --noconsole --name SleekKeys ^
  --icon icon.ico --add-data "web;web" --add-data "icon.ico;." sleekkeys.py || goto :fail
echo.
echo Done: dist\SleekKeys.exe
exit /b 0
:fail
echo Build failed.
exit /b 1
