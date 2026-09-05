import requests
from config import GROQ_API_KEY, GROQ_MODEL, LANGUAGE, SYSTEM_PROMPT

GROQ_ENDPOINT = "https://api.groq.com/openai/v1/audio/transcriptions"

class STTError(Exception):
    pass

def transcribe_audio(wav_bytes: bytes) -> str:
    """
    Transcribes audio WAV bytes using Groq Whisper API.
    Returns the recognized text string.
    """
    if not GROQ_API_KEY:
        raise STTError("GROQ_API_KEY не установлен! Укажите его в файле .env")

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}"
    }

    files = {
        "file": ("audio.wav", wav_bytes, "audio/wav")
    }

    data = {
        "model": GROQ_MODEL,
        "temperature": 0.0,
        "response_format": "json"
    }

    if LANGUAGE:
        data["language"] = LANGUAGE
    if SYSTEM_PROMPT:
        data["prompt"] = SYSTEM_PROMPT

    try:
        response = requests.post(
            GROQ_ENDPOINT,
            headers=headers,
            files=files,
            data=data,
            timeout=15
        )
    except requests.exceptions.Timeout:
        raise STTError("Таймаут запроса к серверу Groq (превышено 15 сек).")
    except requests.exceptions.RequestException as e:
        raise STTError(f"Ошибка соединения с Groq API: {e}")

    if response.status_code == 401:
        raise STTError("Неверный GROQ_API_KEY. Проверьте ключ в файле .env")
    elif response.status_code != 200:
        raise STTError(f"Ошибка Groq API ({response.status_code}): {response.text}")

    result = response.json()
    text = result.get("text", "").strip()
    return text
