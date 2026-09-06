import requests
from typing import Optional
import config

GROQ_ENDPOINT = "https://api.groq.com/openai/v1/audio/transcriptions"

class STTError(Exception):
    pass

def transcribe_audio(
    wav_bytes: bytes,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    language: Optional[str] = None,
    prompt: Optional[str] = None
) -> str:
    """
    Transcribes audio WAV bytes using Groq Whisper API.
    Returns the recognized text string.
    """
    key = (api_key or "").strip() or config.GROQ_API_KEY
    if not key:
        raise STTError("GROQ_API_KEY не установлен! Укажите его в настройках программы.")

    headers = {
        "Authorization": f"Bearer {key}"
    }

    files = {
        "file": ("audio.wav", wav_bytes, "audio/wav")
    }

    active_model = model or config.GROQ_MODEL or "whisper-large-v3-turbo"
    active_lang = language or config.LANGUAGE or "ru"
    active_prompt = prompt if prompt is not None else "Грамотная русская речь, знаки препинания: запятые, точки, вопросительные знаки."

    data = {
        "model": active_model,
        "temperature": 0.0,
        "response_format": "json"
    }

    if active_lang:
        data["language"] = active_lang
    if active_prompt:
        data["prompt"] = active_prompt

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
        raise STTError("Неверный GROQ_API_KEY. Проверьте ключ в параметрах программы.")
    elif response.status_code != 200:
        raise STTError(f"Ошибка Groq API ({response.status_code}): {response.text}")

    result = response.json()
    text = result.get("text", "").strip()
    return text
