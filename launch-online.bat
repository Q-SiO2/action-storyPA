@echo off
setlocal
cd /d "%~dp0"
if not defined PALO_ALTO_SERVER_URL set "PALO_ALTO_SERVER_URL=https://palo-alto-game-backend-production.up.railway.app"
if exist "dist\PaloAlto.exe" (
    start "" "dist\PaloAlto.exe"
    exit /b 0
)
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" main.py
) else (
    python main.py
)
