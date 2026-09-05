import os
import sys
import shutil
import subprocess
from pathlib import Path

def main():
    print("=" * 60)
    print("      Сборка VoiceTyping в автономное приложение")
    print("=" * 60)

    base_dir = Path(__file__).resolve().parent

    # 1. Kill running instances to prevent file lock
    subprocess.run(["taskkill", "/F", "/IM", "VoiceTyping.exe"], capture_output=True)
    try:
        subprocess.run([
            "powershell", "-NoProfile", "-Command",
            "$app = New-Object -ComObject Shell.Application; "
            "$app.Windows() | Where-Object { $_.LocationURL -like '*VoiceTyping*' } | ForEach-Object { $_.Quit() }"
        ], capture_output=True)
    except Exception:
        pass

    # 2. Clean old builds
    build_dir = base_dir / "build"
    dist_app_dir = base_dir / "dist" / "VoiceTyping"
    
    if build_dir.exists():
        try:
            shutil.rmtree(build_dir)
        except Exception:
            pass

    if dist_app_dir.exists():
        try:
            shutil.rmtree(dist_app_dir)
        except Exception:
            pass

    # 3. Locate vosk in venv
    venv_vosk = base_dir / ".venv" / "Lib" / "site-packages" / "vosk"
    icon_path = base_dir / "app.ico"

    cmd = [
        str(base_dir / ".venv" / "Scripts" / "pyinstaller.exe"),
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name", "VoiceTyping",
        "--icon", str(icon_path),
        "--collect-all", "vosk",
        "--add-data", f"{venv_vosk};vosk",
        "--add-data", "app.ico;.",
        "--add-data", "themes.py;.",
        "--add-data", "live_punctuator.py;.",
        "--add-data", "qt_overlay.py;.",
        "--add-data", "settings_window.py;.",
        "--add-data", "sound_signals.py;.",
        "--add-data", "tray_icon.py;.",
        "--add-data", "app_settings.py;.",
        "--add-data", "font_loader.py;.",
        "--add-data", "fonts;fonts",
        "main.py"
    ]

    print("[*] Запуск PyInstaller...")
    ret = subprocess.run(cmd, cwd=base_dir)

    if ret.returncode == 0:
        if build_dir.exists():
            try:
                shutil.rmtree(build_dir)
            except Exception:
                pass

        print()
        print("=" * 60)
        print("[УСПЕХ] Сборка успешно завершена!")
        print("Готовая программа: dist\\VoiceTyping\\VoiceTyping.exe")
        print("=" * 60)

        try:
            os.startfile(str(dist_app_dir))
        except Exception:
            pass
    else:
        print("[!] Ошибка во время сборки.")

if __name__ == "__main__":
    main()
