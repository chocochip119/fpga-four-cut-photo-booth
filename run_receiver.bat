@echo off
cd /d "%~dp0"
set /p PORT=Basys3 COM port (ex: COM5): 
python receive_uart_image.py --port %PORT% --baud 1000000
pause
