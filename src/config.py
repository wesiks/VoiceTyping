import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from the project directory
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# Groq API Configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "whisper-large-v3-turbo").strip()

# Language: "ru" for Russian, "en" for English, or "" (empty) for auto-detection
LANGUAGE = os.getenv("LANGUAGE", "ru").strip()

# Hotkey for Push-to-Talk
# Examples: "f8", "f4", "caps_lock", "scroll_lock", "pause"
HOTKEY = os.getenv("HOTKEY", "f8").strip().lower()

# Sound effects on start / stop of recording
ENABLE_SOUNDS = os.getenv("ENABLE_SOUNDS", "true").lower() in ("true", "1", "yes")

# Optional punctuation and context prompt for Whisper
# This primes the AI to output grammatically correct text with punctuation
SYSTEM_PROMPT = os.getenv(
    "SYSTEM_PROMPT",
    "Привет! Это грамотная русская речь. Используй знаки препинания: запятые, точки, вопросительные и восклицательные знаки."
).strip()

# Audio settings
SAMPLE_RATE = 16000  # 16 kHz is standard for Whisper
CHANNELS = 1         # Mono
