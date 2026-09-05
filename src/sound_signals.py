import threading
import numpy as np
import sounddevice as sd

_SAMPLE_RATE = 44100

def _generate_bell_tone(freq: float, duration: float, volume: float) -> np.ndarray:
    """Generates a warm, organic acoustic crystal bell tone with harmonic depth."""
    t = np.linspace(0, duration, int(_SAMPLE_RATE * duration), False)
    # Organic acoustic attack and natural exponential decay
    envelope = np.exp(-t * 24.0) * (1.0 - np.exp(-t * 320.0))
    
    # Warm harmonic overtone structure (like a high-end Rhodes / marimba)
    wave = (
        0.72 * np.sin(2.0 * np.pi * freq * t) +
        0.20 * np.sin(2.0 * np.pi * freq * 2.0 * t) +
        0.08 * np.sin(2.0 * np.pi * freq * 3.0 * t)
    ) * envelope * volume
    return wave.astype(np.float32)

def _play_async(audio_buffer: np.ndarray):
    def _worker():
        try:
            sd.play(audio_buffer, samplerate=_SAMPLE_RATE, blocking=True)
        except Exception:
            pass
    threading.Thread(target=_worker, daemon=True).start()

def play_start_sound(volume: float = 0.28):
    """Gentle two-tone rising crystal bell (C5 -> E5)."""
    if volume <= 0.01:
        return
    tone1 = _generate_bell_tone(523.25, 0.075, volume * 0.75)  # C5
    silence = np.zeros(int(_SAMPLE_RATE * 0.01), dtype=np.float32)
    tone2 = _generate_bell_tone(659.25, 0.095, volume)         # E5
    chime = np.concatenate([tone1, silence, tone2])
    _play_async(chime)

def play_stop_sound(volume: float = 0.24):
    """Subtle resolving crystal bell tone (E5 -> C5)."""
    if volume <= 0.01:
        return
    tone1 = _generate_bell_tone(659.25, 0.060, volume * 0.70)  # E5
    silence = np.zeros(int(_SAMPLE_RATE * 0.01), dtype=np.float32)
    tone2 = _generate_bell_tone(523.25, 0.090, volume * 0.85)  # C5
    chime = np.concatenate([tone1, silence, tone2])
    _play_async(chime)

def play_error_sound(volume: float = 0.28):
    """Subdued mellow acoustic tone on error."""
    if volume <= 0.01:
        return
    tone1 = _generate_bell_tone(440.00, 0.08, volume * 0.65)
    silence = np.zeros(int(_SAMPLE_RATE * 0.03), dtype=np.float32)
    tone2 = _generate_bell_tone(349.23, 0.11, volume * 0.55)
    chime = np.concatenate([tone1, silence, tone2])
    _play_async(chime)
