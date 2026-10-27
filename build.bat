@echo off
cd /d "%~dp0"
set "BUILD_PY=python"
if exist ".venv\Scripts\python.exe" set "BUILD_PY=.venv\Scripts\python.exe"
"%BUILD_PY%" -m pip install -r requirements-dev.txt
if errorlevel 1 exit /b 1
"%BUILD_PY%" -m PyInstaller --noconfirm BossAutoApply.spec
if errorlevel 1 exit /b 1
echo Output: dist\BossAutoApply\BossAutoApply.exe
pause
