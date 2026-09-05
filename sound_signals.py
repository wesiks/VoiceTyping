import threading
import numpy as np
import sounddevice as sd

_SAMPLE_RATE = 44100

def _generate_tone(freq: float, duration: float, volume: float) -> np.ndarray:
    """Generates a smooth sine wave with cosine envelope to eliminate harsh clicks."""
    t = np.linspace(0, duration, int(_SAMPLE_RATE * duration), False)
    # Cosine fade in and fade out (Hann window envelope)
    envelope = 0.5 * (1.0 - np.cos(2.0 * np.pi * t / duration))
    wave = np.sin(2.0 * np.pi * freq * t) * envelope * volume
    return wave.astype(np.float32)

def _play_async(audio_buffer: np.ndarray):
    def _worker():
        try:
            sd.play(audio_buffer, samplerate=_SAMPLE_RATE, blocking=True)
        except Exception:
            pass
    threading.Thread(target=_worker, daemon=True).start()

def play_start_sound(volume: float = 0.35):
    """Silky-smooth soft two-tone rising chime (Apple/Siri style)."""
    if volume <= 0.01:
        return
    tone1 = _generate_tone(523.25, 0.055, volume * 0.7)  # C5
    tone2 = _generate_tone(659.25, 0.070, volume)        # E5
    chime = np.concatenate([tone1, tone2])
    _play_async(chime)

def play_stop_sound(volume: float = 0.30):
    """Gentle resolving soft tone when speech ends."""
    if volume <= 0.01:
        return
    tone1 = _generate_tone(659.25, 0.050, volume * 0.7)  # E5
    tone2 = _generate_tone(523.25, 0.065, volume * 0.8)  # C5
    chime = np.concatenate([tone1, tone2])
    _play_async(chime)

def play_error_sound(volume: float = 0.35):
    """Soft subdued double chime on error."""
    if volume <= 0.01:
        return
    tone1 = _generate_tone(440.0, 0.08, volume * 0.7)
    silence = np.zeros(int(_SAMPLE_RATE * 0.04), dtype=np.float32)
    tone2 = _generate_tone(349.23, 0.10, volume * 0.6)
    chime = np.concatenate([tone1, silence, tone2])
    _play_async(chime)
