import time
import ctypes
import pyperclip

VK_CONTROL = 0x11
VK_V = 0x56
KEYEVENTF_KEYUP = 0x0002

def insert_text(text: str):
    """
    Copies the recognized text to clipboard and emulates Ctrl+V into the active window.
    """
    if not text:
        return

    if not text.endswith(" "):
        text_to_paste = text + " "
    else:
        text_to_paste = text

    pyperclip.copy(text_to_paste)
    time.sleep(0.05)

    ctypes.windll.user32.keybd_event(VK_CONTROL, 0, 0, 0)
    ctypes.windll.user32.keybd_event(VK_V, 0, 0, 0)
    time.sleep(0.02)
    ctypes.windll.user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
    ctypes.windll.user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
