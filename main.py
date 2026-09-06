import os
import sys
import time
import threading
import webbrowser
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

if getattr(sys, "frozen", False):
    app_dir = Path(sys.executable).resolve().parent
else:
    app_dir = Path(__file__).resolve().parent
try:
    os.chdir(app_dir)
except Exception:
    pass

from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtGui import QAction
from PyQt6.QtCore import QTimer
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from pynput import keyboard

src_dir = app_dir / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

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
from updater import APP_VERSION, check_github_update, open_release_page
from memory_manager import trim_process_memory

app_settings = load_settings()
recorder = AudioRecorder(device=app_settings.get("audio_device", None))
stream_recognizer = None
bridge = None
hud = None
tray = None
settings_win = None

is_recording = False
state_lock = threading.Lock()
current_target_key = None
current_session_id = 0
last_press_time = 0.0
last_release_time = 0.0

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
        apply_vp = app_settings.get("voice_punctuation", True)
        formatted = format_live_text(raw_text, apply_voice_punct=apply_vp)
        bridge.sig_live_text.emit(formatted)

def _process_final_audio_worker(session_id: int, wav_bytes: bytes, fallback_raw_text: str):
    final_text = ""
    api_key = app_settings.get("groq_api_key", "").strip() or config.GROQ_API_KEY

    try:
        if session_id != current_session_id or is_recording:
            return

        if bridge:
            bridge.sig_processing.emit()

        if wav_bytes and api_key:
            final_text = transcribe_audio(wav_bytes, api_key=api_key)
    except STTError as e:
        print(f"\n[INFO] Groq API: {e}. Переключение на локальный текст...")
    except Exception as e:
        print(f"\n[INFO] Ошибка: {e}. Переключение на локальный текст...")

    if session_id != current_session_id or is_recording:
        return

    apply_vp = app_settings.get("voice_punctuation", True)
    if final_text:
        final_text = format_live_text(final_text, apply_voice_punct=apply_vp)
    elif fallback_raw_text:
        final_text = format_live_text(fallback_raw_text, apply_voice_punct=apply_vp)

    if final_text:
        if app_settings.get("trailing_space", False):
            final_text += " "
        print(f"\n[OK] \"{final_text}\"")
        insert_text(final_text)
        if bridge and session_id == current_session_id and not is_recording:
            bridge.sig_done.emit(final_text)
    else:
        if app_settings.get("sound_enabled", True):
            play_error_sound()
        if bridge and session_id == current_session_id and not is_recording:
            bridge.sig_hide.emit()

    threading.Timer(2.0, trim_process_memory).start()

def _start_recording(now: float):
    global is_recording, current_session_id, last_press_time
    with state_lock:
        if is_recording:
            return
        is_recording = True
        current_session_id += 1
        last_press_time = now

    if app_settings.get("sound_enabled", True):
        play_start_sound(volume=0.30)

    if bridge:
        bridge.sig_recording_started.emit()

    use_stream = app_settings.get("stream_preview", True) and stream_recognizer is not None
    if use_stream:
        stream_recognizer.start(on_partial_text_callback=on_live_text)

    recorder.start(
        chunk_callback=stream_recognizer.feed_audio if use_stream else None,
        level_callback=bridge.sig_audio_level.emit if bridge else None,
        device=app_settings.get("audio_device", None)
    )

def _stop_recording(now: float):
    global is_recording, last_release_time
    with state_lock:
        if not is_recording:
            return
        is_recording = False
        last_release_time = now
        session_id = current_session_id
        duration = now - last_press_time

    use_stream = app_settings.get("stream_preview", True) and stream_recognizer is not None
    wav_bytes = recorder.stop()
    fallback_raw_text = stream_recognizer.stop() if use_stream else ""

    if duration < 0.22 or (not wav_bytes and not fallback_raw_text):
        if bridge and session_id == current_session_id:
            bridge.sig_hide.emit()
        return

    if app_settings.get("sound_enabled", True):
        play_stop_sound(volume=0.25)

    threading.Thread(
        target=_process_final_audio_worker,
        args=(session_id, wav_bytes, fallback_raw_text),
        daemon=True
    ).start()

def on_press(key):
    if not is_target_key(key):
        return

    now = time.time()
    mode = app_settings.get("activation_mode", "hold")

    if mode == "toggle":
        if now - last_press_time < 0.20:
            return
        with state_lock:
            rec = is_recording
        if rec:
            _stop_recording(now)
        else:
            _start_recording(now)
        return

    if now - last_release_time < 0.10:
        return

    _start_recording(now)

def on_release(key):
    if not is_target_key(key):
        return

    mode = app_settings.get("activation_mode", "hold")
    if mode == "toggle":
        return

    now = time.time()
    _stop_recording(now)

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
    global app_settings, current_target_key, stream_recognizer
    new_stream = new_settings.get("stream_preview", True)
    app_settings = new_settings
    current_target_key = parse_target_key(app_settings.get("hotkey", "f8"))
    config.GROQ_API_KEY = app_settings.get("groq_api_key", "").strip()
    recorder.set_device(app_settings.get("audio_device", None))
    on_theme_changed(app_settings.get("theme", "claude"))
    if hud:
        hud.set_hotkey(app_settings.get("hotkey", "f8"))
    if tray:
        tray.setToolTip(f"VoiceTyping [{app_settings.get('hotkey', 'f8').upper()}]")

    if not new_stream:
        if stream_recognizer:
            stream_recognizer.unload()
            stream_recognizer = None
        trim_process_memory()
    elif stream_recognizer is None:
        stream_recognizer = StreamRecognizer(sample_rate=config.SAMPLE_RATE, lang="ru", auto_load=False)
        stream_recognizer.preload_async()

def main():
    global hud, bridge, stream_recognizer, tray
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    ipc_name = "VoiceTyping_SingleInstance_IPC"
    client_socket = QLocalSocket()
    client_socket.connectToServer(ipc_name)
    if client_socket.waitForConnected(400):
        client_socket.write(b"SHOW_SETTINGS")
        client_socket.waitForBytesWritten(400)
        client_socket.disconnectFromServer()
        sys.exit(0)

    ipc_server = QLocalServer()
    QLocalServer.removeServer(ipc_name)
    ipc_server.listen(ipc_name)

    def _handle_ipc_connection():
        conn = ipc_server.nextPendingConnection()
        if conn:
            if conn.waitForReadyRead(400):
                msg = conn.readAll().data().decode("utf-8", errors="ignore")
                if "SHOW_SETTINGS" in msg:
                    open_settings_dialog()
            conn.disconnectFromServer()

    ipc_server.newConnection.connect(_handle_ipc_connection)

    init_custom_fonts()
    app.setFont(get_body_font(10))

    bridge = AudioSignalBridge()
    hud = ModernHUD(theme_id=app_settings.get("theme", "claude"), hotkey=app_settings.get("hotkey", "f8"))

    bridge.sig_recording_started.connect(hud.show_recording)
    bridge.sig_live_text.connect(hud.update_live_text)
    bridge.sig_audio_level.connect(hud.set_audio_level)
    bridge.sig_processing.connect(hud.show_processing)
    bridge.sig_done.connect(hud.show_done)
    bridge.sig_hide.connect(hud.hide_hud)

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
        QMenu::item {{
            padding: 7px 18px;
            border-radius: 5px;
        }}
        QMenu::item:selected {{
            background-color: #262634;
            color: #FFFFFF;
        }}
        QMenu::separator {{
            height: 1px;
            background: #282834;
            margin: 4px 8px;
        }}
    """)

    act_settings = QAction("Параметры...", app)
    act_settings.triggered.connect(open_settings_dialog)
    tray_menu.addAction(act_settings)

    act_info = QAction(f"Горячая клавиша: {app_settings.get('hotkey', 'f8').upper()}", app)
    act_info.setEnabled(False)
    tray_menu.addAction(act_info)

    tray_menu.addSeparator()

    act_update = QAction("Проверить обновления...", app)
    def _manual_update_check():
        def _worker():
            res = check_github_update(current_version=config.APP_VERSION)
            if res.get("has_update"):
                url = res.get("download_url") or res.get("release_url")
                tray.showMessage(
                    "Доступно обновление VoiceTyping",
                    f"Вышла новая версия v{res.get('latest_version')}. Открываем страницу загрузки...",
                    QSystemTrayIcon.MessageIcon.Information,
                    8000
                )
                open_release_page(url)
            elif res.get("error"):
                tray.showMessage(
                    "VoiceTyping",
                    f"Ошибка проверки: {res.get('error')}",
                    QSystemTrayIcon.MessageIcon.Warning,
                    4000
                )
            else:
                tray.showMessage(
                    "VoiceTyping",
                    f"У вас установлена последняя версия (v{config.APP_VERSION}).",
                    QSystemTrayIcon.MessageIcon.Information,
                    4000
                )
        threading.Thread(target=_worker, daemon=True).start()

    act_update.triggered.connect(_manual_update_check)
    tray_menu.addAction(act_update)

    act_github = QAction("Репозиторий GitHub", app)
    act_github.triggered.connect(lambda: webbrowser.open("https://github.com/wesiks/VoiceTyping"))
    tray_menu.addAction(act_github)

    act_quit = QAction("Выход", app)
    act_quit.triggered.connect(app.quit)
    tray_menu.addAction(act_quit)

    tray.setContextMenu(tray_menu)
    tray.activated.connect(lambda reason: open_settings_dialog() if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None)
    tray.show()

    pending_update_url = None

    def _on_tray_message_clicked():
        nonlocal pending_update_url
        if pending_update_url:
            open_release_page(pending_update_url)
            pending_update_url = None

    tray.messageClicked.connect(_on_tray_message_clicked)

    current_hk = app_settings.get("hotkey", "f8").upper()
    hud.show_greeting(current_hk)
    tray.showMessage(
        "VoiceTyping готов к работе",
        f"Зажмите клавишу {current_hk} в любой программе для ввода текста.",
        QSystemTrayIcon.MessageIcon.Information,
        3500
    )

    if app_settings.get("stream_preview", True):
        stream_recognizer = StreamRecognizer(sample_rate=config.SAMPLE_RATE, lang="ru", auto_load=False)
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(2500, stream_recognizer.preload_async)

    idle_timer = QTimer()
    idle_timer.setInterval(35000)
    def _on_idle_tick():
        trim_process_memory()
        if stream_recognizer and app_settings.get("stream_preview", True):
            stream_recognizer.check_idle_unload(idle_seconds=180)
    idle_timer.timeout.connect(_on_idle_tick)
    idle_timer.start()

    def _check_startup_updates():
        nonlocal pending_update_url
        if not app_settings.get("check_updates", True):
            return
        res = check_github_update(current_version=config.APP_VERSION)
        if res.get("has_update"):
            pending_update_url = res.get("download_url") or res.get("release_url")
            latest_ver = res.get("latest_version")
            tray.showMessage(
                "Доступно обновление VoiceTyping",
                f"Вышла новая версия v{latest_ver}. Нажмите для загрузки установщика.",
                QSystemTrayIcon.MessageIcon.Information,
                10000
            )

    QTimer.singleShot(4500, lambda: threading.Thread(target=_check_startup_updates, daemon=True).start())

    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.daemon = True
    listener.start()

    if not app_settings.get("groq_api_key", "").strip() and not config.GROQ_API_KEY:
        open_settings_dialog()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
