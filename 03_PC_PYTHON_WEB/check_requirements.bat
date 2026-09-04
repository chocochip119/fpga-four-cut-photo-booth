@echo off
setlocal
cd /d "%~dp0"

echo ==== Four Cut Python/Web requirement check ====
set "FAILED=0"
set "PY_CMD="

where python.exe >nul 2>nul
if not errorlevel 1 set "PY_CMD=python"

if not defined PY_CMD (
    where py.exe >nul 2>nul
    if not errorlevel 1 set "PY_CMD=py"
)

if not defined PY_CMD (
    echo [FAIL] Python not found in PATH
    set "FAILED=1"
) else (
    %PY_CMD% --version

    %PY_CMD% -c "import serial; print('[OK] pyserial', serial.__version__)" 2>nul
    if errorlevel 1 (
        echo [FAIL] pyserial
        set "FAILED=1"
    )

    %PY_CMD% -c "import PIL; print('[OK] Pillow', PIL.__version__)" 2>nul
    if errorlevel 1 (
        echo [FAIL] Pillow
        set "FAILED=1"
    )

    %PY_CMD% -c "from importlib.metadata import version; import flask; print('[OK] Flask', version('Flask'))" 2>nul
    if errorlevel 1 (
        echo [FAIL] Flask
        set "FAILED=1"
    )

    %PY_CMD% -c "from importlib.metadata import version; import qrcode; print('[OK] qrcode', version('qrcode'))" 2>nul
    if errorlevel 1 (
        echo [FAIL] qrcode
        set "FAILED=1"
    )
)

where cloudflared >nul 2>nul
if errorlevel 1 (
    echo [FAIL] cloudflared not found in PATH
    set "FAILED=1"
) else (
    cloudflared --version
)

echo.
if "%FAILED%"=="0" (
    echo [OK] All required programs and Python packages are available.
) else (
    echo Some requirements are missing.
    echo Run install_requirements.bat, or install Python packages with:
    echo   python -m pip install -r requirements.txt
)

pause
endlocal
