import os
import sys
import json
import time
import queue
import threading
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

vosk.SetLogLevel(-1)

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
                    loaded_model = vosk.Model(lang=self.lang)
                    with self._lock:
                        self.model = loaded_model
                        self.last_used_time = time.time()
                except Exception as e:
                    print(f"[WARN] Vosk preload error: {e}")
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
                self.model = vosk.Model(lang=self.lang)
                self.last_used_time = time.time()
                return True
            except Exception as e:
                print(f"[WARN] Vosk load error: {e}")
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

            # If model isn't loaded yet, try to trigger background preload
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
            self._worker_thread.join(timeout=0.3)

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

        # Trim process memory right after recognition to release buffers
        trim_process_memory()
        return result_text

    def _worker(self):
        """Worker thread to process audio chunks with zero UI lag."""
        while self._running:
            try:
                data = self.audio_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            if data is None:
                break

            if not self._running or self.recognizer is None:
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
