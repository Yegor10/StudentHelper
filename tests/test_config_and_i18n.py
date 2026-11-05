import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from studenthelper.config import ConfigManager
from studenthelper.i18n import translate_notification


class ConfigAndTranslationTests(unittest.TestCase):
    def test_settings_are_saved_to_local_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            env_path = Path(directory) / ".env"
            with patch.dict(os.environ, {}, clear=True):
                config = ConfigManager(env_path)
                config.save(
                    api_key="test-key",
                    model="gemini-test",
                    language="uk",
                )
                self.assertEqual(config.gemini_api_key, "test-key")
                self.assertEqual(config.gemini_model, "gemini-test")
                self.assertEqual(config.language, "uk")
                self.assertTrue(env_path.is_file())

    def test_scheduler_notifications_are_translated(self) -> None:
        message = "Preparing to join Mathematics."
        self.assertEqual(
            translate_notification("uk", message),
            "Підготовка до приєднання: Mathematics.",
        )


if __name__ == "__main__":
    unittest.main()
