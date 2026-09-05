@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" goto :NO_VENV

set PYTHONIOENCODING=utf-8
start "" ".venv\Scripts\pythonw.exe" main.py
exit /b 0

:NO_VENV
echo [ERROR] Virtual environment .venv not found in: %~dp0
echo Please run: python -m venv .venv
pause
exit /b 1
