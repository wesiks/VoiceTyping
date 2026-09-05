import os
import sys
import threading
import webbrowser
from pathlib import Path

# Configure Windows console encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtGui import QAction
from pynput import keyboard

import config
from app_settings import load_settings
from themes import get_theme
from audio_recorder import AudioRecorder
from stream_recognizer import StreamRecognizer
from stt_client import transcribe_audio, STTError
from text_injector import insert_text
from sound_signals import play_start_sound, play_stop_sound, play_error_sound
from qt_overlay import ModernHUD, AudioSignalBridge
from live_punctuator import format_live_text
from settings_window import SettingsWindow
from tray_icon import create_app_icon
from font_loader import init_custom_fonts, get_body_font, get_font_families

# Global state
app_settings = load_settings()
recorder = AudioRecorder()
stream_recognizer = None
bridge = None
hud = None
tray = None
settings_win = None

is_recording = False
state_lock = threading.Lock()
current_target_key = None

def parse_target_key(hotkey_str: str):
    name = hotkey_str.lower().strip()
    special_keys = {
        "f1": keyboard.Key.f1,
        "f2": keyboard.Key.f2,
        "f3": keyboard.Key.f3,
        "f4": keyboard.Key.f4,
        "f5": keyboard.Key.f5,
        "f6": keyboard.Key.f6,
        "f7": keyboard.Key.f7,
        "f8": keyboard.Key.f8,
        "f9": keyboard.Key.f9,
        "f10": keyboard.Key.f10,
        "f11": keyboard.Key.f11,
        "f12": keyboard.Key.f12,
        "caps_lock": keyboard.Key.caps_lock,
        "scroll_lock": keyboard.Key.scroll_lock,
        "pause": keyboard.Key.pause,
        "insert": keyboard.Key.insert,
        "alt_r": keyboard.Key.alt_r,
        "ctrl_r": keyboard.Key.ctrl_r,
    }
    return special_keys.get(name, name)

current_target_key = parse_target_key(app_settings.get("hotkey", "f8"))

def is_target_key(key) -> bool:
    if isinstance(current_target_key, keyboard.Key):
        return key == current_target_key
    if hasattr(key, "char") and key.char:
        return key.char.lower() == current_target_key
    return False

def on_live_text(raw_text: str):
    if bridge and raw_text:
        formatted = format_live_text(raw_text)
        bridge.sig_live_text.emit(formatted)

def _process_final_audio_worker(wav_bytes: bytes, fallback_raw_text: str):
    final_text = ""
    api_key = app_settings.get("groq_api_key", "").strip() or config.GROQ_API_KEY

    try:
        if bridge:
            bridge.sig_processing.emit()

        if wav_bytes and api_key:
            final_text = transcribe_audio(wav_bytes)
    except STTError as e:
        print(f"\n[INFO] Groq API: {e}. Переключение на локальный текст...")
    except Exception as e:
        print(f"\n[INFO] Ошибка: {e}. Переключение на локальный текст...")

    if not final_text and fallback_raw_text:
        final_text = format_live_text(fallback_raw_text)

    if final_text:
        print(f"\n[OK] \"{final_text}\"")
        insert_text(final_text)
        if bridge:
            bridge.sig_done.emit(final_text)
    else:
        if app_settings.get("sound_enabled", True):
            play_error_sound()
        if bridge:
            bridge.sig_hide.emit()

def on_press(key):
    global is_recording
    if not is_target_key(key):
        return

    with state_lock:
        if is_recording:
            return
        is_recording = True

    if app_settings.get("sound_enabled", True):
        play_start_sound(volume=0.30)

    if bridge:
        bridge.sig_recording_started.emit()

    if stream_recognizer:
        stream_recognizer.start(on_partial_text_callback=on_live_text)

    recorder.start(
        chunk_callback=stream_recognizer.feed_audio if stream_recognizer else None,
        level_callback=bridge.sig_audio_level.emit if bridge else None
    )

def on_release(key):
    global is_recording
    if not is_target_key(key):
        return

    with state_lock:
        if not is_recording:
            return
        is_recording = False

    if app_settings.get("sound_enabled", True):
        play_stop_sound(volume=0.25)

    wav_bytes = recorder.stop()
    fallback_raw_text = stream_recognizer.stop() if stream_recognizer else ""

    threading.Thread(
        target=_process_final_audio_worker,
        args=(wav_bytes, fallback_raw_text),
        daemon=True
    ).start()

def open_settings_dialog():
    global settings_win
    if settings_win is None:
        settings_win = SettingsWindow()
        settings_win.theme_changed.connect(on_theme_changed)
        settings_win.settings_saved.connect(on_settings_saved)
    settings_win.show()
    settings_win.raise_()
    settings_win.activateWindow()

def on_theme_changed(theme_id: str):
    if hud:
        hud.set_theme(theme_id)
    if tray:
        theme = get_theme(theme_id)
        tray.setIcon(create_app_icon(theme["accent"]))

def on_settings_saved(new_settings: dict):
    global app_settings, current_target_key
    app_settings = new_settings
    current_target_key = parse_target_key(app_settings.get("hotkey", "f8"))
    config.GROQ_API_KEY = app_settings.get("groq_api_key", "").strip()
    on_theme_changed(app_settings.get("theme", "claude"))
    if tray:
        tray.setToolTip(f"VoiceTyping [{app_settings.get('hotkey', 'f8').upper()}]")

def main():
    global hud, bridge, stream_recognizer, tray
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    init_custom_fonts()
    app.setFont(get_body_font(10))

    bridge = AudioSignalBridge()
    hud = ModernHUD(theme_id=app_settings.get("theme", "claude"))

    bridge.sig_recording_started.connect(hud.show_recording)
    bridge.sig_live_text.connect(hud.update_live_text)
    bridge.sig_audio_level.connect(hud.set_audio_level)
    bridge.sig_processing.connect(hud.show_processing)
    bridge.sig_done.connect(hud.show_done)
    bridge.sig_hide.connect(hud.hide_hud)

    # Setup System Tray without emojis
    theme = get_theme(app_settings.get("theme", "claude"))
    tray = QSystemTrayIcon(create_app_icon(theme["accent"]), app)
    tray.setToolTip(f"VoiceTyping [{app_settings.get('hotkey', 'f8').upper()}]")

    fams = get_font_families()
    tray_menu = QMenu()
    tray_menu.setStyleSheet(f"""
        QMenu {{
            background-color: #16161C;
            color: #FAF8F5;
            border: 1px solid #282834;
            border-radius: 8px;
            padding: 5px;
            font-family: '{fams["body"]}', sans-serif;
            font-size: 12px;
        }}
        QMenu::item {
            padding: 7px 18px;
            border-radius: 5px;
        }
        QMenu::item:selected {
            background-color: #262634;
            color: #FFFFFF;
        }
        QMenu::separator {
            height: 1px;
            background: #282834;
            margin: 4px 8px;
        }
    """)

    act_settings = QAction("Параметры...", app)
    act_settings.triggered.connect(open_settings_dialog)
    tray_menu.addAction(act_settings)

    act_info = QAction(f"Горячая клавиша: {app_settings.get('hotkey', 'f8').upper()}", app)
    act_info.setEnabled(False)
    tray_menu.addAction(act_info)

    tray_menu.addSeparator()

    act_github = QAction("Репозиторий GitHub", app)
    act_github.triggered.connect(lambda: webbrowser.open("https://github.com"))
    tray_menu.addAction(act_github)

    act_quit = QAction("Выход", app)
    act_quit.triggered.connect(app.quit)
    tray_menu.addAction(act_quit)

    tray.setContextMenu(tray_menu)
    tray.activated.connect(lambda reason: open_settings_dialog() if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None)
    tray.show()

    def _init_vosk():
        global stream_recognizer
        stream_recognizer = StreamRecognizer(sample_rate=config.SAMPLE_RATE, lang="ru")
    threading.Thread(target=_init_vosk, daemon=True).start()

    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.daemon = True
    listener.start()

    # Open clean settings dialog on first launch if key missing
    if not app_settings.get("groq_api_key", "").strip() and not config.GROQ_API_KEY:
        open_settings_dialog()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
