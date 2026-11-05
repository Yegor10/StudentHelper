import unittest
from datetime import datetime, time

from studenthelper.models import Lesson
from studenthelper.schedule import build_schedule, next_occurrences, validate_meeting_url


class ScheduleTests(unittest.TestCase):
    def test_lessons_include_configured_breaks(self) -> None:
        start = datetime(2026, 11, 5, 8, 30)
        lessons = [
            Lesson(1, "Math", 45, 10, ""),
            Lesson(2, "Science", 50, 5, ""),
        ]
        schedule = build_schedule(lessons, start)
        self.assertEqual(schedule[0].ends_at, datetime(2026, 11, 5, 9, 15))
        self.assertEqual(schedule[1].starts_at, datetime(2026, 11, 5, 9, 25))

    def test_next_occurrences_roll_to_tomorrow_when_day_is_over(self) -> None:
        now = datetime(2026, 11, 5, 18, 0)
        result = next_occurrences(
            [Lesson(1, "Math", 45, 0, "")], time(8, 30), now
        )
        self.assertEqual(result[0].starts_at, datetime(2026, 11, 6, 8, 30))

    def test_meeting_url_requires_http_scheme_and_host(self) -> None:
        self.assertTrue(validate_meeting_url("https://meet.example/room"))
        self.assertFalse(validate_meeting_url("javascript:alert(1)"))


if __name__ == "__main__":
    unittest.main()
