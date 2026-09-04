@echo off
setlocal
cd /d "%~dp0"

set "PY_CMD="
where python.exe >nul 2>nul
if not errorlevel 1 set "PY_CMD=python"

if not defined PY_CMD (
    where py.exe >nul 2>nul
    if not errorlevel 1 set "PY_CMD=py"
)

if not defined PY_CMD (
    echo Python not found. Install Python or add python.exe/py.exe to PATH.
    pause
    exit /b 1
)

set /p UART_PORT=COM port input (example COM5): 
%PY_CMD% receive_uart_image.py --port %UART_PORT% --baud 1000000 --width 640 --height 480
pause
endlocal
