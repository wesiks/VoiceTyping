import time
import threading
import ctypes
import pyperclip
from app_logger import get_logger

logger = get_logger("VoiceTyping.Injector")

VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_V = 0x56
KEYEVENTF_KEYUP = 0x0002

def insert_text(text: str, restore_clipboard: bool = True):
    """
    Copies the recognized text to clipboard, emulates Ctrl+V into the active window,
    and restores the previous clipboard content in background so user data isn't lost.
    """
    if not text:
        return

    prev_clipboard = None
    if restore_clipboard:
        try:
            prev_clipboard = pyperclip.paste()
        except Exception:
            prev_clipboard = None

    try:
        pyperclip.copy(text)
    except Exception as e:
        logger.error("Не удалось скопировать распознанный текст в буфер обмена: %s", e)
        return

    try:
        ctypes.windll.user32.keybd_event(VK_SHIFT, 0, KEYEVENTF_KEYUP, 0)
        ctypes.windll.user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
    except Exception:
        pass

    time.sleep(0.06)

    ctypes.windll.user32.keybd_event(VK_CONTROL, 0, 0, 0)
    ctypes.windll.user32.keybd_event(VK_V, 0, 0, 0)
    time.sleep(0.03)
    ctypes.windll.user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
    ctypes.windll.user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)

    logger.info("Успешно отправлен Ctrl+V в активное окно (длина текста: %d символов)", len(text))

    if restore_clipboard and prev_clipboard is not None:
        def _restore_worker():
            time.sleep(1.5)
            try:
                pyperclip.copy(prev_clipboard)
            except Exception:
                pass
        threading.Thread(target=_restore_worker, daemon=True).start()

