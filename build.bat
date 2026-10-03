@echo off
setlocal
cd /d "%~dp0"
set "TASK_PYTHON=python"
if exist ".venv\Scripts\python.exe" set "TASK_PYTHON=.venv\Scripts\python.exe"
"%TASK_PYTHON%" -m PyInstaller --noconfirm PaloAlto.spec
if errorlevel 1 exit /b 1
if not exist "dist\data" mkdir "dist\data"
copy /y "data\scenarios.json" "dist\data\scenarios.json" >nul
copy /y "launch.bat" "dist\launch.bat" >nul
copy /y "launch-online.bat" "dist\launch-online.bat" >nul
echo EXE disponible : dist\PaloAlto.exe
echo Scenario editable : dist\data\scenarios.json
