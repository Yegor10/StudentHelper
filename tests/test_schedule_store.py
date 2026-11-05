import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from studenthelper.models import Lesson
from studenthelper.schedule import next_week_school_dates, weekdays_from_monday
from studenthelper.schedule_store import ScheduleStore, WEEKDAYS


class ScheduleStoreTests(unittest.TestCase):
    def test_weekday_schedules_and_preferences_survive_reopen(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "schedule.json"
            store = ScheduleStore(path)
            self.assertTrue(store.created_new)
            store.save_day(
                "monday",
                "09:15",
                [Lesson(None, "Math", 50, 10, "https://meet.example/math")],
            )
            store.save_day(
                "friday",
                "10:00",
                [Lesson(None, "Art", 45, 0, "")],
            )
            store.set_preferences(appearance="Dark", color_theme="green")

            reopened = ScheduleStore(path)
            self.assertFalse(reopened.created_new)
            self.assertEqual(len(json.loads(path.read_text(encoding="utf-8"))["weekdays"]), 5)
            start_time, monday_lessons = reopened.get_day("monday")
            self.assertEqual(start_time, "09:15")
            self.assertEqual(monday_lessons[0].title, "Math")
            self.assertEqual(reopened.get_day("tuesday")[1], [])
            self.assertEqual(reopened.get_preference("appearance", "System"), "Dark")
            self.assertEqual(reopened.get_preference("color_theme", "blue"), "green")

    def test_legacy_lessons_are_migrated_to_each_weekday(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ScheduleStore(Path(directory) / "schedule.json")
            store.migrate_legacy_schedule(
                [Lesson(None, "History", 45, 5, "")], "08:45"
            )
            for day in WEEKDAYS:
                start_time, lessons = store.get_day(day)
                self.assertEqual(start_time, "08:45")
                self.assertEqual(lessons[0].title, "History")

    def test_next_week_dates_are_weekdays_of_the_following_week(self) -> None:
        self.assertEqual(
            next_week_school_dates(date(2026, 11, 5)),
            [
                date(2026, 11, 9),
                date(2026, 11, 10),
                date(2026, 11, 11),
                date(2026, 11, 12),
                date(2026, 11, 13),
            ],
        )

    def test_calendar_week_starts_on_monday_and_rejects_other_days(self) -> None:
        week = weekdays_from_monday(date(2026, 11, 9))
        self.assertEqual(week[0], date(2026, 11, 9))
        self.assertEqual(week[-1], date(2026, 11, 13))
        with self.assertRaises(ValueError):
            weekdays_from_monday(date(2026, 11, 10))


if __name__ == "__main__":
    unittest.main()
