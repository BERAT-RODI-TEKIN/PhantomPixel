@echo off
setlocal
chcp 65001 >nul
title PhantomPixel
cd /d "%~dp0"

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY goto :no_python

if not exist ".venv\Scripts\python.exe" %PY% -m venv .venv
if errorlevel 1 goto :failed
set "VPY=.venv\Scripts\python.exe"

rem Install libraries when they are missing (e.g. an interrupted first run)
"%VPY%" -c "import rich, cryptography, PIL, numpy" >nul 2>nul
if errorlevel 1 (
    echo Installing libraries, internet required...
    "%VPY%" -m pip install -r requirements.txt
    if errorlevel 1 goto :failed
)

"%VPY%" main.py %*
pause
exit /b 0

:no_python
echo [ERROR] Python was not found. Install it from python.org first, or use the EXE version.
pause
exit /b 1

:failed
echo.
echo [ERROR] Setup failed. Check your internet connection and try again.
pause
exit /b 1
