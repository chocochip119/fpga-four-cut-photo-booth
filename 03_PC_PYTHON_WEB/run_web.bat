@echo off
cd /d "%~dp0"

where python.exe >nul 2>nul
if not errorlevel 1 goto RUN_PYTHON

where py.exe >nul 2>nul
if not errorlevel 1 goto RUN_PY

echo Python was not found.
echo Install Python or add it to PATH, then try again.
pause
exit /b 1

:RUN_PYTHON
echo Starting FPGA Photo Booth and Cloudflare Tunnel...
echo Keep this window open while using the program.
python uart_photo_web.py
goto END

:RUN_PY
echo Starting FPGA Photo Booth and Cloudflare Tunnel...
echo Keep this window open while using the program.
py -3 uart_photo_web.py

:END
echo.
echo Program stopped.
pause
