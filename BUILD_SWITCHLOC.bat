@echo off
setlocal
cd /d "%~dp0"
where python >nul 2>&1
if errorlevel 1 (echo Python 3.9+ not found.& exit /b 1)
python -m pip install -e . pyinstaller
if errorlevel 1 exit /b 1
python -m PyInstaller --noconfirm --clean --windowed --name SwitchLoc switchloc_launcher.py
if errorlevel 1 exit /b 1
echo Build completed. Test on a clean Windows machine before distribution.
endlocal
