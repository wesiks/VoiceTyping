import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
if (BASE_DIR.parent / ".env").exists():
    load_dotenv(BASE_DIR.parent / ".env")
elif (BASE_DIR / ".env").exists():
    load_dotenv(BASE_DIR / ".env")
else:
    load_dotenv()


APP_VERSION = "2.5.0"


GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "whisper-large-v3-turbo").strip()

LANGUAGE = os.getenv("LANGUAGE", "ru").strip()

HOTKEY = os.getenv("HOTKEY", "f8").strip().lower()

ENABLE_SOUNDS = os.getenv("ENABLE_SOUNDS", "true").lower() in ("true", "1", "yes")

SYSTEM_PROMPT = os.getenv(
    "SYSTEM_PROMPT",
    "Привет! Это грамотная русская речь. Используй знаки препинания: запятые, точки, вопросительные и восклицательные знаки."
).strip()

SAMPLE_RATE = 16000
CHANNELS = 1
