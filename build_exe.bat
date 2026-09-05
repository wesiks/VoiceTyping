@echo off
chcp 65001 > nul
cd /d "%~dp0"
title Сборка VoiceTyping

echo =========================================================
echo       Сборка VoiceTyping в автономное приложение
echo =========================================================

if not exist ".venv\Scripts\pyinstaller.exe" (
    echo [ОШИБКА] PyInstaller не найден в виртуальном окружении.
    pause
    exit /b 1
)

echo [*] Удаление старых сборок...
if exist "build" rmdir /s /q "build"
if exist "dist\VoiceTyping" rmdir /s /q "dist\VoiceTyping"

echo [*] Компиляция приложения через PyInstaller...
".venv\Scripts\pyinstaller.exe" ^
    --noconfirm ^
    --onedir ^
    --windowed ^
    --name "VoiceTyping" ^
    --collect-all "vosk" ^
    --add-data ".venv\Lib\site-packages\vosk;vosk" ^
    --add-data "themes.py;." ^
    --add-data "live_punctuator.py;." ^
    --add-data "qt_overlay.py;." ^
    --add-data "settings_window.py;." ^
    --add-data "sound_signals.py;." ^
    --add-data "tray_icon.py;." ^
    --add-data "app_settings.py;." ^
    main.py

if %ERRORLEVEL% EQU 0 (
    echo [*] Очистка временных файлов сборки...
    if exist "build" rmdir /s /q "build"

    echo.
    echo =========================================================
    echo [УСПЕХ] Сборка успешно завершена!
    echo.
    echo Готовая программа находится в папке:
    echo dist\VoiceTyping\VoiceTyping.exe
    echo.
    echo ВАЖНО: Запускайте файл из папки DIST!
    echo =========================================================
    
    explorer.exe "dist\VoiceTyping"
) else (
    echo.
    echo [!] Во время сборки произошла ошибка.
    pause
)
