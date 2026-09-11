import os
import sys
import json
import time
import queue
import threading
import ctypes
from pathlib import Path
from typing import Optional, Callable

if getattr(sys, "frozen", False):
    meipass = getattr(sys, "_MEIPASS", "")
    if meipass:
        vosk_internal = os.path.join(meipass, "vosk")
        try:
            os.makedirs(vosk_internal, exist_ok=True)
            if hasattr(os, "add_dll_directory"):
                os.add_dll_directory(vosk_internal)
        except Exception:
            pass

import vosk
from memory_manager import trim_process_memory
from app_logger import get_logger

logger = get_logger("VoiceTyping.STT")

vosk.SetLogLevel(-1)

def get_safe_windows_path(path_str: str) -> str:
    """
    On Windows, converts a path containing unicode/Cyrillic characters
    to an 8.3 ASCII short path so C/C++ libraries (like Vosk/Kaldi) can open files safely.
    """
    if sys.platform != "win32" or not path_str:
        return path_str
    try:
        buf = ctypes.create_unicode_buffer(1024)
        res = ctypes.windll.kernel32.GetShortPathNameW(path_str, buf, 1024)
        if res > 0 and buf.value:
            return buf.value
    except Exception:
        pass
    return path_str

def find_vosk_model_path(lang: str = "ru") -> Optional[str]:
    """
    Locates an offline Vosk speech model across bundled, installed, project, and cache directories.
    Returns the string path to the model directory if found, else None.
    """
    clean_lang = (lang or "ru").lower()
    if clean_lang in ("auto", "none", ""):
        clean_lang = "ru"

    model_folder_name = "vosk-model-small-ru-0.22" if clean_lang == "ru" else "vosk-model-small-en-us-0.15"

    candidates = []

    if hasattr(sys, "_MEIPASS"):
        candidates.append(Path(sys._MEIPASS) / "models" / model_folder_name)
        candidates.append(Path(sys._MEIPASS) / model_folder_name)

    exe_dir = Path(sys.executable).resolve().parent
    candidates.append(exe_dir / "models" / model_folder_name)
    candidates.append(exe_dir / "_internal" / "models" / model_folder_name)
    candidates.append(exe_dir / model_folder_name)

    src_parent = Path(__file__).resolve().parent.parent
    candidates.append(src_parent / "models" / model_folder_name)
    candidates.append(src_parent / model_folder_name)

    appdata = os.environ.get("APPDATA")
    if appdata:
        candidates.append(Path(appdata) / "VoiceTyping" / "models" / model_folder_name)

    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        candidates.append(Path(local_appdata) / "vosk" / model_folder_name)

    user_home = Path.home()
    candidates.append(user_home / ".cache" / "vosk" / model_folder_name)

    for p in candidates:
        if p.exists() and (p / "am").exists() and (p / "graph").exists():
            safe_p = get_safe_windows_path(str(p.resolve()))
            return safe_p

    return None

class StreamRecognizer:
    def __init__(self, sample_rate: int = 16000, lang: str = "ru", auto_load: bool = False):
        self.sample_rate = sample_rate
        self.lang = lang
        self.model = None
        self.recognizer = None

        self._is_loading = False
        self._load_lock = threading.Lock()
        self._lock = threading.Lock()
        
        self.audio_queue = queue.Queue()
        self.callback: Optional[Callable[[str], None]] = None
        self._running = False
        self._accumulated_words = []
        self._worker_thread = None
        self.last_used_time = time.time()

        if auto_load:
            self.preload_async()

    def is_loaded(self) -> bool:
        return self.model is not None

    def _create_model_instance(self) -> vosk.Model:
        model_path = find_vosk_model_path(self.lang)
        if model_path:
            logger.info("Инициализация оффлайн-модели Vosk из: %s", model_path)
            return vosk.Model(model_path=model_path)

        l = (self.lang or "").lower()
        vosk_l = "ru" if l in ("auto", "none", "") else ("en-us" if l == "en" else l)
        logger.warning("Локальная модель не найдена. Попытка загрузки через Vosk API для языка '%s'...", vosk_l)
        return vosk.Model(lang=vosk_l)

    def preload_async(self):
        """Asynchronously loads Vosk model in background without freezing UI."""
        if self.model is not None or self._is_loading:
            return

        def _loader():
            with self._load_lock:
                if self.model is not None:
                    return
                self._is_loading = True
                try:
                    loaded_model = self._create_model_instance()
                    with self._lock:
                        self.model = loaded_model
                        self.last_used_time = time.time()
                    logger.info("Модель Vosk успешно предзагружена и готова к работе.")
                except Exception as e:
                    logger.error("Ошибка предзагрузки модели Vosk: %s", e)
                finally:
                    self._is_loading = False
                    trim_process_memory()

        t = threading.Thread(target=_loader, daemon=True)
        t.start()

    def ensure_model_loaded(self) -> bool:
        """Synchronously ensures the model is loaded."""
        if self.model is not None:
            return True
        with self._load_lock:
            if self.model is not None:
                return True
            try:
                self.model = self._create_model_instance()
                self.last_used_time = time.time()
                logger.info("Модель Vosk успешно синхронно загружена.")
                return True
            except Exception as e:
                logger.error("Ошибка загрузки модели Vosk: %s", e)
                return False


    def unload(self):
        """Unloads Vosk model from memory and trims working set."""
        with self._lock:
            if self._running:
                return
            self.recognizer = None
            self.model = None
        trim_process_memory()

    def check_idle_unload(self, idle_seconds: int = 180):
        """Unloads model if not used for the given duration."""
        if self._running or self._is_loading or self.model is None:
            return
        if time.time() - self.last_used_time > idle_seconds:
            self.unload()

    def start(self, on_partial_text_callback: Callable[[str], None]):
        """Prepares the recognizer for a new speech segment."""
        self.last_used_time = time.time()
        with self._lock:
            self.callback = on_partial_text_callback
            self._accumulated_words = []

            if self.model is None:
                self.preload_async()
                self._running = False
                return

            try:
                self.recognizer = vosk.KaldiRecognizer(self.model, self.sample_rate)
            except Exception:
                self.recognizer = None
                self._running = False
                return

            while not self.audio_queue.empty():
                try:
                    self.audio_queue.get_nowait()
                except queue.Empty:
                    break

            self._running = True
            self._worker_thread = threading.Thread(target=self._worker, daemon=True)
            self._worker_thread.start()

    def feed_audio(self, audio_bytes: bytes):
        """Pushes raw PCM audio bytes to the stream recognizer."""
        if self._running and self.recognizer is not None:
            self.audio_queue.put(audio_bytes)

    def stop(self) -> str:
        """Stops streaming and returns accumulated text."""
        self.last_used_time = time.time()
        with self._lock:
            was_running = self._running
            self._running = False
            self.audio_queue.put(None)

        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=0.8)

        result_text = ""
        if was_running and self.recognizer is not None:
            try:
                final_res = json.loads(self.recognizer.FinalResult())
                final_chunk = final_res.get("text", "").strip()
                if final_chunk:
                    self._accumulated_words.append(final_chunk)
            except Exception:
                pass
            result_text = " ".join(self._accumulated_words).strip()

        trim_process_memory()
        return result_text

    def transcribe_wav_bytes(self, wav_bytes: bytes) -> str:
        """Synchronously transcribes WAV bytes using local Vosk model (100% offline)."""
        if not wav_bytes:
            logger.warning("Vosk: получены пустые байты WAV для расшифровки.")
            return ""
        if not self.ensure_model_loaded():
            logger.error("Vosk: невозможно расшифровать аудио, модель не загружена.")
            return ""
        import io
        import wave
        words = []
        try:
            with io.BytesIO(wav_bytes) as bio:
                with wave.open(bio, "rb") as wf:
                    sample_rate = wf.getframerate()
                    rec = vosk.KaldiRecognizer(self.model, sample_rate)
                    while True:
                        data = wf.readframes(4000)
                        if len(data) == 0:
                            break
                        if rec.AcceptWaveform(data):
                            res = json.loads(rec.Result())
                            t = res.get("text", "").strip()
                            if t:
                                words.append(t)
                    final_res = json.loads(rec.FinalResult())
                    ft = final_res.get("text", "").strip()
                    if ft:
                        words.append(ft)
        except Exception as e:
            logger.error("Ошибка распознавания WAV через Vosk: %s", e)
        finally:
            trim_process_memory()

        recognized_phrase = " ".join(words).strip()
        if recognized_phrase:
            logger.info("Vosk офлайн распознал (%d фрагментов): '%s'", len(words), recognized_phrase)
        else:
            logger.info("Vosk: в переданном аудио речь не обнаружена (тишина или низкая громкость).")
        return recognized_phrase

    def _worker(self):
        """Worker thread to process audio chunks with zero UI lag."""
        while True:
            try:
                data = self.audio_queue.get(timeout=0.08)
            except queue.Empty:
                if not self._running:
                    break
                continue

            if data is None:
                break

            if self.recognizer is None:
                break

            try:
                if self.recognizer.AcceptWaveform(data):
                    res = json.loads(self.recognizer.Result())
                    text = res.get("text", "").strip()
                    if text:
                        self._accumulated_words.append(text)
                    current_text = " ".join(self._accumulated_words).strip()
                    if self.callback and current_text:
                        self.callback(current_text)
                else:
                    partial = json.loads(self.recognizer.PartialResult()).get("partial", "").strip()
                    if partial:
                        prefix = " ".join(self._accumulated_words).strip()
                        current_text = f"{prefix} {partial}".strip() if prefix else partial
                        if self.callback:
                            self.callback(current_text)
            except Exception:
                pass
