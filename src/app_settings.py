import json
import os
import sys
import winreg
from pathlib import Path

SETTINGS_FILE = Path(__file__).resolve().parent / "settings.json"
ENV_FILE = Path(__file__).resolve().parent / ".env"

DEFAULT_SETTINGS = {
    "groq_api_key": "",
    "hotkey": "f8",
    "theme": "claude",
    "sound_enabled": True,
    "sound_volume": 0.5,
    "eq_sensitivity": 1.2,
    "language": "ru",
    "autostart": False
}

def load_settings() -> dict:
    settings = DEFAULT_SETTINGS.copy()

    # Try reading from settings.json
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                settings.update(saved)
        except Exception:
            pass

    # If groq_api_key is empty, fallback to .env if available
    if not settings.get("groq_api_key") and ENV_FILE.exists():
        try:
            with open(ENV_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("GROQ_API_KEY="):
                        key = line.split("=", 1)[1].strip()
                        if key:
                            settings["groq_api_key"] = key
                            break
        except Exception:
            pass

    return settings

def save_settings(settings: dict):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Ошибка сохранения настроек: {e}")

    # Also keep .env in sync for CLI scripts
    if "groq_api_key" in settings:
        try:
            with open(ENV_FILE, "w", encoding="utf-8") as f:
                f.write(f"GROQ_API_KEY={settings['groq_api_key']}\n")
                f.write(f"HOTKEY={settings.get('hotkey', 'f8')}\n")
                f.write(f"THEME={settings.get('theme', 'claude')}\n")
        except Exception:
            pass

def set_windows_autostart(enable: bool, app_name: str = "VoiceTyping"):
    """Adds or removes the application from Windows registry Run key."""
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
        if enable:
            # Determine path to executable or script
            if getattr(sys, "frozen", False):
                exe_path = f'"{sys.executable}"'
            else:
                script_path = Path(__file__).resolve().parent / "main.py"
                python_exe = sys.executable
                exe_path = f'"{python_exe}" "{script_path}"'
            winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, exe_path)
        else:
            try:
                winreg.DeleteValue(key, app_name)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
        return True
    except Exception as e:
        print(f"Ошибка настройки автозапуска: {e}")
        return False
