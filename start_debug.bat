@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" goto :NO_VENV

set PYTHONIOENCODING=utf-8
echo [*] Запуск VoiceTyping в режиме отладки с консолью...
".venv\Scripts\python.exe" main.py
if errorlevel 1 pause
exit /b 0

:NO_VENV
echo [ERROR] Virtual environment .venv not found in: %~dp0
pause
exit /b 1
