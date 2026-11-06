import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "extension" / "chrome"


class ChromeExtensionTests(unittest.TestCase):
    def test_manifest_declares_mv3_and_required_google_scopes(self) -> None:
        manifest = json.loads((EXTENSION / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["manifest_version"], 3)
        self.assertIn("identity", manifest["permissions"])
        self.assertIn("alarms", manifest["permissions"])
        self.assertIn(
            "https://www.googleapis.com/auth/classroom.coursework.me",
            manifest["oauth2"]["scopes"],
        )
        self.assertIn(
            "https://www.googleapis.com/auth/drive.file",
            manifest["oauth2"]["scopes"],
        )
        self.assertTrue((EXTENSION / manifest["icons"]["128"]).is_file())

    def test_default_week_contains_the_provided_five_day_timetable(self) -> None:
        schedule = json.loads(
            (EXTENSION / "default-schedule.json").read_text(encoding="utf-8")
        )
        weekdays = schedule["weekdays"]
        self.assertEqual(
            list(weekdays),
            ["monday", "tuesday", "wednesday", "thursday", "friday"],
        )
        self.assertEqual(weekdays["monday"]["lessons"][0]["title"], "Фізика і астрономія")
        self.assertEqual(weekdays["friday"]["lessons"][0]["title"], "Математика")
        self.assertEqual(weekdays["wednesday"]["lessons"][0]["meeting_url"], "")

    def test_no_oauth_client_secret_is_bundled(self) -> None:
        for path in EXTENSION.rglob("*"):
            if path.is_file() and path.suffix in {".js", ".json", ".html"}:
                content = path.read_text(encoding="utf-8")
                self.assertNotIn("GOCSPX-", content, str(path))
                self.assertNotIn('"client_secret"', content, str(path))


if __name__ == "__main__":
    unittest.main()
