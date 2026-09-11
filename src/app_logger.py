import os
import sys
import platform
import logging
import traceback
import subprocess
from pathlib import Path
from logging.handlers import RotatingFileHandler

_IS_INITIALIZED = False
_LOG_FILE_PATH: Path | None = None

def get_logs_dir() -> Path:
    """Returns the persistent logs directory inside %APPDATA%/VoiceTyping/logs/."""
    app_data = os.environ.get("APPDATA")
    if app_data:
        d = Path(app_data) / "VoiceTyping" / "logs"
    else:
        d = Path.home() / ".voicetyping" / "logs"
    try:
        d.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return d

def get_log_file_path() -> Path:
    global _LOG_FILE_PATH
    if _LOG_FILE_PATH is None:
        _LOG_FILE_PATH = get_logs_dir() / "voicetyping.log"
    return _LOG_FILE_PATH

def open_logs_folder():
    """Opens the directory containing log files in Windows Explorer."""
    log_dir = get_logs_dir()
    log_file = get_log_file_path()
    try:
        if sys.platform == "win32":
            if log_file.exists():
                subprocess.Popen(f'explorer.exe /select,"{log_file}"')
            else:
                os.startfile(str(log_dir))
        else:
            subprocess.Popen(["xdg-open", str(log_dir)])
    except Exception as e:
        logging.getLogger("VoiceTyping").error(f"Failed to open logs folder: {e}")

def open_log_file():
    """Opens the current log file in the default text editor (Notepad on Windows)."""
    log_file = get_log_file_path()
    try:
        if sys.platform == "win32":
            os.startfile(str(log_file))
        else:
            subprocess.Popen(["xdg-open", str(log_file)])
    except Exception as e:
        logging.getLogger("VoiceTyping").error(f"Failed to open log file: {e}")

def show_crash_dialog(error_msg: str, tb_str: str):
    """Shows a native Windows error dialog with an option to open the log file."""
    log_file = get_log_file_path()
    title = "VoiceTyping — Критическая ошибка запуска"
    text = (
        f"Произошла ошибка при работе программы:\n\n"
        f"{error_msg}\n\n"
        f"Подробный журнал записан в файл:\n"
        f"{log_file}\n\n"
        f"Нажмите «ОК», чтобы открыть папку с журналом (логами)."
    )

    if sys.platform == "win32":
        try:
            import ctypes
            res = ctypes.windll.user32.MessageBoxW(0, text, title, 0x10 | 0x01 | 0x1000)
            if res == 1:
                open_logs_folder()
            return
        except Exception:
            pass

    print(f"\n[CRASH] {text}\n{tb_str}", file=sys.stderr)

def _uncaught_exception_handler(exc_type, exc_value, exc_traceback):
    """Global hook for sys.excepthook."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger = logging.getLogger("VoiceTyping")
    tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
    tb_str = "".join(tb_lines)
    err_msg = str(exc_value) or str(exc_type.__name__)

    logger.critical("Неперехваченное исключение (Uncaught Exception):\n%s", tb_str)

    show_crash_dialog(err_msg, tb_str)

def _threading_exception_handler(args):
    """Global hook for threading.excepthook in Python 3.8+."""
    logger = logging.getLogger("VoiceTyping")
    tb_lines = traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)
    tb_str = "".join(tb_lines)
    logger.error("Ошибка в потоке [%s]:\n%s", args.thread.name if args.thread else "Unknown", tb_str)

def setup_logging(app_version: str = "2.5.0") -> logging.Logger:
    """Initializes rotating file and console logging and installs exception hooks."""
    global _IS_INITIALIZED
    logger = logging.getLogger("VoiceTyping")
    if _IS_INITIALIZED:
        return logger

    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    logger.handlers.clear()

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    log_file = get_log_file_path()
    try:
        file_handler = RotatingFileHandler(
            str(log_file),
            maxBytes=2 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"[WARN] Failed to set up file logger: {e}", file=sys.stderr)

    try:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    except Exception:
        pass

    sys.excepthook = _uncaught_exception_handler
    import threading
    if hasattr(threading, "excepthook"):
        threading.excepthook = _threading_exception_handler

    _IS_INITIALIZED = True

    logger.info("=" * 60)
    logger.info("VoiceTyping v%s запущен", app_version)
    logger.info("ОС: %s (версия %s, архитектура %s)", platform.platform(), platform.version(), platform.architecture()[0])
    logger.info("Python: %s", sys.version.replace("\n", " "))
    logger.info("Путь запуска: %s", sys.executable)
    logger.info("Заморожен (PyInstaller): %s", getattr(sys, "frozen", False))
    logger.info("Файл журнала: %s", log_file)
    logger.info("=" * 60)

    return logger

def get_logger(name: str = None) -> logging.Logger:
    if name:
        log_name = f"VoiceTyping.{name}" if not name.startswith("VoiceTyping") else name
        return logging.getLogger(log_name)
    return logging.getLogger("VoiceTyping")
