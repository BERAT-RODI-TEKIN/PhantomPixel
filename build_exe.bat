@echo off
setlocal
chcp 65001 >nul
title PhantomPixel - EXE builder
cd /d "%~dp0"

echo.
echo  ===  PhantomPixel EXE builder  ===
echo.

rem --- Find Python (py launcher or python) ---
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY goto :no_python

echo [1/4] Preparing virtual environment...
if not exist ".venv-build\Scripts\python.exe" %PY% -m venv .venv-build
if errorlevel 1 goto :failed
set "VPY=.venv-build\Scripts\python.exe"

echo [2/4] Installing libraries (internet required)...
"%VPY%" -m pip install --upgrade pip >nul
"%VPY%" -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto :failed

echo [3/4] Running tests...
"%VPY%" -m unittest discover -s tests
if errorlevel 1 goto :failed

echo [4/4] Building the EXE, this can take 1-2 minutes...
"%VPY%" -m PyInstaller --onefile --console --clean --noconfirm --name PhantomPixel --collect-submodules rich main.py
if errorlevel 1 goto :failed

echo.
echo  ============================================================
echo   DONE:  dist\PhantomPixel.exe
echo   Copy this single file to a USB stick. It runs on any Windows
echo   PC without Python. Drag an image onto it for smart mode.
echo  ============================================================
echo.
explorer dist
pause
exit /b 0

:no_python
echo [ERROR] Python was not found.
echo         Install it from https://www.python.org/downloads/ and tick
echo         "Add python.exe to PATH" during setup. Then run this again.
pause
exit /b 1

:failed
echo.
echo [ERROR] A step failed. Read the message above.
pause
exit /b 1
