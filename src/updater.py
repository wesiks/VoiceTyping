import re
import sys
import time
import threading
import requests
import webbrowser
from typing import Optional, Dict, Any, Tuple

APP_VERSION = "2.5.0"

GITHUB_REPO = "wesiks/VoiceTyping"
RELEASES_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
RAW_VERSION_URL = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/version.json"
CDN_VERSION_URL = f"https://cdn.jsdelivr.net/gh/{GITHUB_REPO}@main/version.json"

_CACHE_LOCK = threading.Lock()
_CACHE_DATA: Optional[Dict[str, Any]] = None
_CACHE_TIME: float = 0.0
CACHE_TTL_SECONDS = 60.0

def parse_version(v_str: str) -> Tuple[int, ...]:
    """Parses semantic version string like 'v1.2.0' or '1.2' into an integer tuple."""
    clean = re.sub(r"^[^\d]*", "", v_str.strip())
    numbers = []
    for part in clean.split("."):
        m = re.match(r"\d+", part)
        if m:
            numbers.append(int(m.group(0)))
        else:
            break
    while len(numbers) < 3:
        numbers.append(0)
    return tuple(numbers)

def check_github_update(
    current_version: str = APP_VERSION,
    timeout: Tuple[float, float] = (1.2, 1.8),
    proxy_url: Optional[str] = None,
    force_refresh: bool = False
) -> Dict[str, Any]:
    """
    Rapidly checks if an update is available for VoiceTyping.
    Uses cached result if checked within the last 60 seconds.
    Tries fast CDN/raw endpoints first, then falls back to GitHub Releases API.
    """
    global _CACHE_DATA, _CACHE_TIME

    with _CACHE_LOCK:
        if not force_refresh and _CACHE_DATA is not None:
            if time.time() - _CACHE_TIME < CACHE_TTL_SECONDS:
                cached = dict(_CACHE_DATA)
                cached["from_cache"] = True
                return cached

    result: Dict[str, Any] = {
        "checked": False,
        "has_update": False,
        "current_version": current_version,
        "latest_version": current_version,
        "release_name": "",
        "release_url": f"https://github.com/{GITHUB_REPO}/releases",
        "download_url": "",
        "release_notes": "",
        "error": None,
        "from_cache": False
    }

    proxies = None
    if proxy_url and proxy_url.strip():
        p_clean = proxy_url.strip()
        proxies = {"http": p_clean, "https": p_clean}

    fast_endpoints = [CDN_VERSION_URL, RAW_VERSION_URL]
    for url in fast_endpoints:
        try:
            r = requests.get(
                url,
                headers={"User-Agent": "VoiceTyping-App"},
                proxies=proxies,
                timeout=(1.0, 1.5)
            )
            if r.status_code == 200:
                v_data = r.json()
                latest_tag = v_data.get("version") or v_data.get("tag", "")
                if latest_tag:
                    result["checked"] = True
                    result["latest_version"] = latest_tag.lstrip("v")
                    result["release_name"] = v_data.get("release_name", f"VoiceTyping {latest_tag}")
                    result["release_url"] = v_data.get("release_url", result["release_url"])
                    result["download_url"] = v_data.get("download_url", "")
                    result["release_notes"] = v_data.get("release_notes", "")

                    if parse_version(latest_tag) > parse_version(current_version):
                        result["has_update"] = True

                    with _CACHE_LOCK:
                        _CACHE_DATA = dict(result)
                        _CACHE_TIME = time.time()
                    return result
        except Exception:
            pass

    try:
        headers = {
            "User-Agent": "VoiceTyping-App",
            "Accept": "application/vnd.github.v3+json"
        }
        resp = requests.get(RELEASES_API_URL, headers=headers, proxies=proxies, timeout=timeout)
        result["checked"] = True

        if resp.status_code == 200:
            data = resp.json()
            tag = data.get("tag_name", "").strip()
            result["latest_version"] = tag.lstrip("v")
            result["release_name"] = data.get("name", f"VoiceTyping {tag}")
            result["release_url"] = data.get("html_url", result["release_url"])
            result["release_notes"] = data.get("body", "")

            for asset in data.get("assets", []):
                name = asset.get("name", "").lower()
                if name.endswith(".exe") and "setup" in name:
                    result["download_url"] = asset.get("browser_download_url", "")
                    break
            if not result["download_url"] and data.get("assets"):
                result["download_url"] = data["assets"][0].get("browser_download_url", "")

            current_tuple = parse_version(current_version)
            latest_tuple = parse_version(tag)

            if latest_tuple > current_tuple:
                result["has_update"] = True
        elif resp.status_code == 404:
            result["error"] = "Релизы не найдены"
        else:
            result["error"] = f"Сервер вернул статус {resp.status_code}"

    except requests.exceptions.Timeout:
        result["error"] = "Таймаут соединения с GitHub (медленный интернет/VPN)"
    except requests.exceptions.ConnectionError:
        result["error"] = "Нет подключения к GitHub (проверьте интернет/VPN)"
    except requests.exceptions.RequestException as e:
        result["error"] = "Ошибка сети при проверке обновлений"
    except Exception as e:
        result["error"] = str(e)

    if result["checked"] and not result.get("error"):
        with _CACHE_LOCK:
            _CACHE_DATA = dict(result)
            _CACHE_TIME = time.time()

    return result

def open_release_page(url: Optional[str] = None):
    """Opens the release URL in the default web browser."""
    target = url or f"https://github.com/{GITHUB_REPO}/releases/latest"
    webbrowser.open(target)
