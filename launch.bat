@echo off
setlocal
cd /d "%~dp0"
if exist "PaloAlto.exe" (
    start "" "PaloAlto.exe"
    exit /b 0
)
if exist "dist\PaloAlto.exe" (
    start "" "dist\PaloAlto.exe"
    exit /b 0
)
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" main.py
) else (
    python main.py
)
