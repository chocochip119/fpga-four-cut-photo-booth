@echo off
cd /d "%~dp0"
set /p UART_PORT=COM port input (example COM5): 
python receive_uart_image.py --port %UART_PORT% --baud 1000000 --width 640 --height 480
pause
