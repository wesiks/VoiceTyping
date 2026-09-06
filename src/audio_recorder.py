import io
import wave
import threading
import sounddevice as sd
import numpy as np
from config import SAMPLE_RATE, CHANNELS

class AudioRecorder:
    def __init__(self, sample_rate: int = SAMPLE_RATE, channels: int = CHANNELS, device=None):
        self.sample_rate = sample_rate
        self.channels = channels
        self.device = device
        self.is_recording = False
        self._frames = []
        self._lock = threading.RLock()
        self._stream = None
        self._chunk_callback = None
        self._level_callback = None

    def set_device(self, device):
        """Set or update default audio device."""
        with self._lock:
            self.device = device

    def _audio_callback(self, indata, frames, time_info, status):
        """Callback executed by sounddevice for each chunk of recorded audio."""
        if not self.is_recording:
            return

        chunk = indata.copy()
        with self._lock:
            if not self.is_recording:
                return
            self._frames.append(chunk)

        if self._level_callback:
            try:
                float_data = chunk.astype(np.float32) / 32768.0
                rms = float(np.sqrt(np.mean(float_data ** 2)))
                scaled = min(1.0, rms * 14.0)
                level = float(np.power(scaled, 0.75))
                self._level_callback(level)
            except Exception:
                pass

        if self._chunk_callback:
            try:
                self._chunk_callback(chunk.tobytes())
            except Exception:
                pass

    def start(self, chunk_callback=None, level_callback=None, device=None):
        """Start audio recording with real-time chunk streaming and volume level reporting."""
        with self._lock:
            # Safely close any previous stream that might still be open
            if self._stream is not None:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None

            self._frames = []
            self._chunk_callback = chunk_callback
            self._level_callback = level_callback
            self.is_recording = True

            dev_to_use = device if device is not None else self.device

            try:
                self._stream = sd.InputStream(
                    samplerate=self.sample_rate,
                    channels=self.channels,
                    dtype="int16",
                    blocksize=1200,
                    device=dev_to_use,
                    callback=self._audio_callback
                )
                self._stream.start()
            except Exception as e:
                print(f"[WARN] Ошибка старта аудиопотока: {e}")
                self.is_recording = False
                self._stream = None

    def stop(self) -> bytes | None:
        """Stop audio recording and return WAV bytes, or None if too short."""
        with self._lock:
            if not self.is_recording and self._stream is None:
                return None

            self.is_recording = False
            stream = self._stream
            self._stream = None

            if stream:
                try:
                    stream.stop()
                    stream.close()
                except Exception:
                    pass

            self._chunk_callback = None
            self._level_callback = None

            if not self._frames:
                return None

            try:
                audio_data = np.concatenate(self._frames, axis=0)
            except Exception:
                return None
            self._frames = []

        min_samples = int(self.sample_rate * 0.25)
        if len(audio_data) < min_samples:
            return None

        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio_data.tobytes())

        wav_buffer.seek(0)
        return wav_buffer.read()
