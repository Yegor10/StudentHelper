import sqlite3
import tempfile
import unittest
from pathlib import Path

from studenthelper.database import Database
from studenthelper.models import Lesson


class DatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = Database(Path(self.temp_dir.name) / "test.sqlite3")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_schedule_and_settings_round_trip(self) -> None:
        self.database.replace_lessons(
            [
                Lesson(None, "Math", 50, 10, "https://meet.example/class"),
                Lesson(None, "English", 40, 5, ""),
            ]
        )
        lessons = self.database.list_lessons()
        self.assertEqual([lesson.title for lesson in lessons], ["Math", "English"])
        self.assertEqual(lessons[0].duration_minutes, 50)
        self.database.set_setting("first_start_time", "09:15")
        self.assertEqual(self.database.get_setting("first_start_time"), "09:15")

    def test_diary_solution_round_trip(self) -> None:
        entry_id = self.database.add_diary_entry("2 + 2", None, "2026-11-09")
        self.database.save_solution(entry_id, "2 + 2 = 4")
        entry = self.database.get_diary_entry(entry_id)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.solution, "2 + 2 = 4")
        self.assertEqual(entry.scheduled_date, "2026-11-09")

    def test_existing_diary_database_gets_due_date_column(self) -> None:
        legacy_path = Path(self.temp_dir.name) / "legacy.sqlite3"
        connection = sqlite3.connect(legacy_path)
        try:
            connection.execute(
                "CREATE TABLE diary_entries ("
                "id INTEGER PRIMARY KEY, task_text TEXT NOT NULL, image_path TEXT, "
                "solution TEXT NOT NULL DEFAULT '', "
                "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
            )
            connection.commit()
        finally:
            connection.close()
        migrated = Database(legacy_path)
        entry_id = migrated.add_diary_entry("Read chapter 2", None, "2026-11-10")
        entry = migrated.get_diary_entry(entry_id)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.scheduled_date, "2026-11-10")


if __name__ == "__main__":
    unittest.main()
