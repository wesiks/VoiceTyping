import re
import sys
import requests
import webbrowser
from typing import Optional, Dict, Any, Tuple

APP_VERSION = "1.3.0"
GITHUB_REPO = "wesiks/VoiceTyping"
RELEASES_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

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

def check_github_update(current_version: str = APP_VERSION, timeout: int = 6) -> Dict[str, Any]:
    """
    Queries GitHub Releases API to see if a newer version exists.
    Returns a dictionary with result metadata.
    """
    result = {
        "checked": False,
        "has_update": False,
        "current_version": current_version,
        "latest_version": current_version,
        "release_name": "",
        "release_url": f"https://github.com/{GITHUB_REPO}/releases",
        "download_url": "",
        "release_notes": "",
        "error": None
    }

    try:
        headers = {
            "User-Agent": "VoiceTyping-App",
            "Accept": "application/vnd.github.v3+json"
        }
        resp = requests.get(RELEASES_API_URL, headers=headers, timeout=timeout)
        result["checked"] = True

        if resp.status_code == 200:
            data = resp.json()
            tag = data.get("tag_name", "").strip()
            result["latest_version"] = tag.lstrip("v")
            result["release_name"] = data.get("name", f"VoiceTyping {tag}")
            result["release_url"] = data.get("html_url", result["release_url"])
            result["release_notes"] = data.get("body", "")

            # Look for installer in assets
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

    except requests.exceptions.RequestException as e:
        result["error"] = "Ошибка сети при проверке обновлений"
    except Exception as e:
        result["error"] = str(e)

    return result

def open_release_page(url: Optional[str] = None):
    """Opens the release URL in the default web browser."""
    target = url or f"https://github.com/{GITHUB_REPO}/releases/latest"
    webbrowser.open(target)
