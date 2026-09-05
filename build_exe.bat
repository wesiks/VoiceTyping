@echo off
cd /d "%~dp0"
echo =========================================================
echo       Сборка VoiceTyping в автономный .exe файл
echo =========================================================

if not exist ".venv\Scripts\pyinstaller.exe" (
    echo [ОШИБКА] PyInstaller не найден в виртуальном окружении.
    pause
    exit /b 1
)

echo [*] Компиляция приложения...
".venv\Scripts\pyinstaller.exe" ^
    --noconfirm ^
    --onedir ^
    --windowed ^
    --name "VoiceTyping" ^
    --add-data "themes.py;." ^
    --add-data "live_punctuator.py;." ^
    --add-data "qt_overlay.py;." ^
    --add-data "settings_window.py;." ^
    --add-data "sound_signals.py;." ^
    --add-data "tray_icon.py;." ^
    --add-data "app_settings.py;." ^
    main.py

if %ERRORLEVEL% EQU 0 (
    echo.
    echo =========================================================
    echo [УСПЕХ] Сборка завершена!
    echo Готовая программа находится в папке: dist\VoiceTyping\
    echo Запустите: dist\VoiceTyping\VoiceTyping.exe
    echo =========================================================
) else (
    echo.
    echo [!] Во время сборки произошла ошибка.
)

pause
