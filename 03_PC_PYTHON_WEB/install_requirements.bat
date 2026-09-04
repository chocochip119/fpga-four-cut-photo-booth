@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo Four Cut Python/Web dependency installer
echo ============================================
echo.

set "PY_CMD="
where python.exe >nul 2>nul
if not errorlevel 1 set "PY_CMD=python"

if not defined PY_CMD (
    where py.exe >nul 2>nul
    if not errorlevel 1 set "PY_CMD=py"
)

if not defined PY_CMD (
    echo [FAIL] Python not found.
    echo Install Python first, then run this file again.
    pause
    exit /b 1
)

echo [1/2] Installing Python packages...
%PY_CMD% -m pip install -r requirements.txt
if errorlevel 1 (
    echo [FAIL] Python package installation failed.
    pause
    exit /b 1
)

echo.
echo [2/2] Checking cloudflared...
where cloudflared >nul 2>nul
if not errorlevel 1 (
    echo [OK] cloudflared is already installed.
    cloudflared --version
) else (
    where winget >nul 2>nul
    if errorlevel 1 (
        echo [FAIL] winget not found.
        echo Install cloudflared manually, then reopen PowerShell/CMD.
        pause
        exit /b 1
    )

    echo Installing cloudflared with winget...
    winget install --id Cloudflare.cloudflared -e --accept-package-agreements --accept-source-agreements
    if errorlevel 1 (
        echo [FAIL] cloudflared installation failed.
        pause
        exit /b 1
    )

    echo.
    echo [OK] cloudflared installation command completed.
    echo If cloudflared is not recognized in this window, close it and open a new CMD/PowerShell.
)

echo.
echo ============================================
echo Installation finished.
echo Run check_requirements.bat to verify.
echo ============================================
pause
endlocal
