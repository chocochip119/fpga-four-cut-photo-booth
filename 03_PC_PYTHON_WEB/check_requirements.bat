@echo off
cd /d "%~dp0"
echo ==== Four Cut Python/Web requirement check ====
where python >nul 2>nul && (python --version) || (echo [FAIL] Python not found in PATH)
python -c "import serial; print('[OK] pyserial', serial.__version__)" 2>nul || echo [FAIL] pyserial
python -c "import PIL; print('[OK] Pillow', PIL.__version__)" 2>nul || echo [FAIL] Pillow
python -c "import flask; print('[OK] Flask', flask.__version__)" 2>nul || echo [FAIL] Flask
python -c "import qrcode; print('[OK] qrcode import')" 2>nul || echo [FAIL] qrcode
where cloudflared >nul 2>nul && (cloudflared --version) || (echo [FAIL] cloudflared not found in PATH)
echo.
echo Missing Python packages: python -m pip install -r requirements.txt
pause
