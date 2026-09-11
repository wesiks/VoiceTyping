import sys
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
src_dir = BASE_DIR / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from live_punctuator import format_live_text
from updater import parse_version
from themes import THEMES, get_theme

class TestLivePunctuator(unittest.TestCase):
    def test_russian_voice_punctuation(self):
        text = "привет запятая как дела вопросительный знак"
        res = format_live_text(text)
        self.assertEqual(res, "Привет, как дела?")

    def test_english_voice_punctuation(self):
        text = "hello comma how are you question mark"
        res = format_live_text(text)
        self.assertEqual(res, "Hello, how are you?")

    def test_ellipses(self):
        text = "привет многоточие как дела"
        res = format_live_text(text)
        self.assertNotIn(". . .", res)
        self.assertIn("...", res)

    def test_pre_existing_dots(self):
        text = "привет... как дела"
        res = format_live_text(text)
        self.assertNotIn(". . .", res)
        self.assertIn("...", res)

    def test_newline_capitalization(self):
        text = "первая строка с новой строки вторая строка"
        res = format_live_text(text)
        self.assertIn("\nВторая", res)

    def test_english_newline(self):
        text = "first line new line second line"
        res = format_live_text(text)
        self.assertIn("\nSecond", res)

    def test_conjunction_commas(self):
        text = "я думаю что это работает потому что мы проверили"
        res = format_live_text(text)
        self.assertIn("думаю, что", res)
        self.assertIn("работает, потому что", res)

class TestUpdater(unittest.TestCase):
    def test_parse_version(self):
        self.assertEqual(parse_version("1.4.0"), (1, 4, 0))
        self.assertEqual(parse_version("v1.4.0"), (1, 4, 0))
        self.assertEqual(parse_version("v1.5.0-alpha"), (1, 5, 0))
        self.assertEqual(parse_version("v2.0"), (2, 0, 0))
        self.assertTrue(parse_version("1.4.1") > parse_version("1.4.0"))
        self.assertTrue(parse_version("v1.5.0-alpha") > parse_version("1.4.0"))
        self.assertTrue(parse_version("v2.0.0") > parse_version("1.5.0-alpha"))


class TestThemes(unittest.TestCase):
    def test_all_themes_exist(self):
        expected = ["claude", "cyan", "emerald", "purple", "crimson", "amber"]
        for t in expected:
            self.assertIn(t, THEMES)
            theme = get_theme(t)
            self.assertEqual(theme["id"], t)
            self.assertIn("accent", theme)
            self.assertIn("card_bg", theme)

class TestAppSettings(unittest.TestCase):
    def test_default_settings_keys(self):
        from app_settings import DEFAULT_SETTINGS
        self.assertIn("stt_mode", DEFAULT_SETTINGS)
        self.assertIn("proxy_url", DEFAULT_SETTINGS)
        self.assertIn("api_base_url", DEFAULT_SETTINGS)
        self.assertEqual(DEFAULT_SETTINGS["stt_mode"], "auto")
        self.assertEqual(DEFAULT_SETTINGS["proxy_url"], "")
        self.assertEqual(DEFAULT_SETTINGS["api_base_url"], "")

class TestSTTClient(unittest.TestCase):
    from unittest.mock import patch, MagicMock

    @patch("requests.post")
    def test_transcribe_with_proxy(self, mock_post):
        from stt_client import transcribe_audio
        mock_resp = self.MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"text": "тестовый текст"}
        mock_post.return_value = mock_resp

        res = transcribe_audio(
            b"fake_wav",
            api_key="gsk_test123",
            proxy_url="http://127.0.0.1:7890"
        )
        self.assertEqual(res, "тестовый текст")
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["proxies"], {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"})

    @patch("requests.post")
    def test_transcribe_with_base_url(self, mock_post):
        from stt_client import transcribe_audio
        mock_resp = self.MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"text": "привет мир"}
        mock_post.return_value = mock_resp

        res = transcribe_audio(
            b"fake_wav",
            api_key="gsk_test123",
            base_url="https://api.myproxy.com/v1"
        )
        self.assertEqual(res, "привет мир")
        call_args, _ = mock_post.call_args
        self.assertEqual(call_args[0], "https://api.myproxy.com/v1/audio/transcriptions")

    @patch("requests.post")
    def test_transcribe_403_geo_block(self, mock_post):
        from stt_client import transcribe_audio, STTError
        mock_resp = self.MagicMock()
        mock_resp.status_code = 403
        mock_post.return_value = mock_resp

        with self.assertRaises(STTError) as ctx:
            transcribe_audio(b"fake_wav", api_key="gsk_test123")
        self.assertIn("403", str(ctx.exception))
        self.assertIn("Vosk", str(ctx.exception))

class TestUpdaterNetwork(unittest.TestCase):
    from unittest.mock import patch, MagicMock

    def setUp(self):
        import updater
        with updater._CACHE_LOCK:
            updater._CACHE_DATA = None
            updater._CACHE_TIME = 0.0

    @patch("requests.get")
    def test_check_github_update_proxy(self, mock_get):
        import updater
        mock_resp = self.MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "version": "1.6.0",
            "tag": "v1.6.0",
            "release_name": "VoiceTyping v1.6.0",
            "release_url": "https://github.com/wesiks/VoiceTyping/releases/v1.6.0",
            "download_url": "https://setup.exe"
        }
        mock_get.return_value = mock_resp

        res = updater.check_github_update(
            current_version="1.5.0",
            proxy_url="socks5://127.0.0.1:1080",
            force_refresh=True
        )
        self.assertTrue(res["checked"])
        self.assertTrue(res["has_update"])
        self.assertEqual(res["latest_version"], "1.6.0")
        self.assertEqual(res["download_url"], "https://setup.exe")
        _, kwargs = mock_get.call_args
        self.assertEqual(kwargs["proxies"], {"http": "socks5://127.0.0.1:1080", "https": "socks5://127.0.0.1:1080"})

    @patch("requests.get")
    def test_check_github_update_caching(self, mock_get):
        import updater
        mock_resp = self.MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "version": "2.5.0",
            "tag": "v2.5.0"
        }
        mock_get.return_value = mock_resp

        res1 = updater.check_github_update(current_version="2.5.0", force_refresh=True)
        self.assertFalse(res1.get("from_cache"))
        self.assertEqual(mock_get.call_count, 1)

        res2 = updater.check_github_update(current_version="2.5.0", force_refresh=False)
        self.assertTrue(res2.get("from_cache"))
        self.assertEqual(mock_get.call_count, 1)

class TestProjectFiles(unittest.TestCase):
    def test_version_json_exists_and_valid(self):
        import json
        v_file = BASE_DIR / "version.json"
        self.assertTrue(v_file.exists())
        data = json.loads(v_file.read_text(encoding="utf-8"))
        self.assertIn("version", data)
        self.assertIn("download_url", data)

    def test_privacy_and_terms_docs_exist(self):
        p_file = BASE_DIR / "PRIVACY.md"
        t_file = BASE_DIR / "TERMS.md"
        self.assertTrue(p_file.exists())
        self.assertTrue(t_file.exists())
        self.assertIn("VoiceTyping", p_file.read_text(encoding="utf-8"))
        self.assertIn("MIT", t_file.read_text(encoding="utf-8"))

class TestFonts(unittest.TestCase):
    def test_font_loader_families(self):
        from font_loader import get_font_families
        families = get_font_families()
        self.assertIn("title", families)
        self.assertIn("body", families)
        self.assertIn("mono", families)
        self.assertEqual(families["title"], families["body"])

class TestAppLogger(unittest.TestCase):
    def test_logger_paths_and_initialization(self):
        from app_logger import get_logs_dir, get_log_file_path, setup_logging, get_logger
        logs_dir = get_logs_dir()
        log_file = get_log_file_path()
        self.assertTrue(str(logs_dir).endswith("logs"))
        self.assertEqual(log_file.name, "voicetyping.log")

        logger = setup_logging()
        logger.info("Unit test message for VoiceTyping logger")
        self.assertTrue(log_file.exists())
        content = log_file.read_text(encoding="utf-8")
        self.assertIn("Unit test message for VoiceTyping logger", content)

class TestOfflineModel(unittest.TestCase):
    def test_model_resolver_and_bridge_error_signal(self):
        from stream_recognizer import find_vosk_model_path, get_safe_windows_path
        from qt_overlay import AudioSignalBridge

        model_path = find_vosk_model_path("ru")
        self.assertIsNotNone(model_path)
        safe_path = get_safe_windows_path(model_path)
        self.assertTrue(len(safe_path) > 0)

        bridge = AudioSignalBridge()
        self.assertTrue(hasattr(bridge, "sig_error"))

class TestAppMainModule(unittest.TestCase):
    def test_app_main_import_and_callable(self):
        import app_main
        self.assertTrue(hasattr(app_main, "run_app"))
        self.assertTrue(callable(app_main.run_app))
        self.assertTrue(hasattr(app_main, "parse_target_key"))
        self.assertTrue(callable(app_main.parse_target_key))

if __name__ == "__main__":
    unittest.main()


