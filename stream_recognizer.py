import os
import sys

# PyInstaller compatibility fix for Vosk DLL directory resolution
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

import json
import queue
import threading
import vosk

vosk.SetLogLevel(-1)

class StreamRecognizer:
    def __init__(self, sample_rate: int = 16000, lang: str = "ru"):
        self.sample_rate = sample_rate
        self.model = vosk.Model(lang=lang)
        self.recognizer = vosk.KaldiRecognizer(self.model, self.sample_rate)
        
        self.audio_queue = queue.Queue()
        self.callback = None
        self._running = False
        self._accumulated_words = []
        self._worker_thread = None
        self._lock = threading.Lock()

    def start(self, on_partial_text_callback):
        """Prepares the recognizer for a new speech segment."""
        with self._lock:
            self.callback = on_partial_text_callback
            self._accumulated_words = []
            self.recognizer = vosk.KaldiRecognizer(self.model, self.sample_rate)
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
        if self._running:
            self.audio_queue.put(audio_bytes)

    def stop(self) -> str:
        """Stops streaming and returns accumulated text."""
        with self._lock:
            self._running = False
            self.audio_queue.put(None)

        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=0.3)

        final_res = json.loads(self.recognizer.FinalResult())
        final_chunk = final_res.get("text", "").strip()
        if final_chunk:
            self._accumulated_words.append(final_chunk)

        return " ".join(self._accumulated_words).strip()

    def _worker(self):
        """Worker thread to process audio chunks with zero UI lag."""
        while self._running:
            try:
                data = self.audio_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            if data is None:
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
