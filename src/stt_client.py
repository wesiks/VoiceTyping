import requests
from typing import Optional, Tuple
import config

GROQ_ENDPOINT = "https://api.groq.com/openai/v1/audio/transcriptions"

class STTError(Exception):
    pass

def transcribe_audio(
    wav_bytes: bytes,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    language: Optional[str] = None,
    prompt: Optional[str] = None,
    proxy_url: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: Tuple[float, float] = (3.0, 5.0)
) -> str:
    """
    Transcribes audio WAV bytes using Groq Whisper API or compatible endpoint.
    Supports HTTP/SOCKS5 proxy and custom base URL.
    Returns the recognized text string.
    """
    key = (api_key or "").strip() or config.GROQ_API_KEY
    if not key:
        raise STTError("GROQ_API_KEY не установлен! Укажите его в настройках программы.")

    headers = {
        "Authorization": f"Bearer {key}",
        "User-Agent": f"VoiceTyping/{config.APP_VERSION}"
    }

    files = {
        "file": ("audio.wav", wav_bytes, "audio/wav")
    }

    active_model = model or config.GROQ_MODEL or "whisper-large-v3-turbo"
    active_lang = language if language is not None else config.LANGUAGE
    if active_lang in ("auto", "None", ""):
        active_lang = None

    if prompt is not None:
        active_prompt = prompt
    elif active_lang == "en":
        active_prompt = "Natural English speech, punctuation: commas, periods, question marks, exclamation marks."
    else:
        active_prompt = "Грамотная русская речь, знаки препинания: запятые, точки, вопросительные знаки."

    data = {
        "model": active_model,
        "temperature": 0.0,
        "response_format": "json"
    }

    if active_lang:
        data["language"] = active_lang
    if active_prompt:
        data["prompt"] = active_prompt

    proxies = None
    if proxy_url and proxy_url.strip():
        p_clean = proxy_url.strip()
        proxies = {"http": p_clean, "https": p_clean}

    if base_url and base_url.strip():
        clean_base = base_url.strip().rstrip("/")
        if not clean_base.endswith("/audio/transcriptions"):
            endpoint = f"{clean_base}/audio/transcriptions"
        else:
            endpoint = clean_base
    else:
        endpoint = GROQ_ENDPOINT

    try:
        response = requests.post(
            endpoint,
            headers=headers,
            files=files,
            data=data,
            proxies=proxies,
            timeout=timeout
        )
    except requests.exceptions.Timeout:
        raise STTError("Таймаут запроса к Groq API (сервер не ответил вовремя).")
    except requests.exceptions.RequestException as e:
        raise STTError(f"Ошибка соединения с Groq API: {e}")

    if response.status_code == 403:
        raise STTError("Доступ к Groq заблокирован для вашего региона (код 403). Включите VPN, укажите прокси или переключитесь на режим Vosk.")
    elif response.status_code == 401:
        raise STTError("Неверный GROQ_API_KEY. Проверьте ключ в параметрах программы.")
    elif response.status_code != 200:
        raise STTError(f"Ошибка Groq API ({response.status_code}): {response.text}")

    result = response.json()
    text = result.get("text", "").strip()
    return text
