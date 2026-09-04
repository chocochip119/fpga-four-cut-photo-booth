@echo off
setlocal
cd /d "%~dp0"

set "WEB_PORT=%~1"
if not defined WEB_PORT (
    for /f %%P in ('powershell -NoProfile -Command "(Get-Content -Raw 'web_config.json' ^| ConvertFrom-Json).web_port" 2^>nul') do set "WEB_PORT=%%P"
)

if not defined WEB_PORT set "WEB_PORT=5000"
start "" "http://127.0.0.1:%WEB_PORT%/static/state_debug.html?state=3"
endlocal
