import asyncio
import unittest
from datetime import datetime, time
from unittest.mock import patch

from studenthelper.models import Lesson
from studenthelper.schedule import (
    SchedulerService,
    build_schedule,
    next_occurrences,
    validate_meeting_url,
)


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

    def test_scheduler_opens_links_in_the_default_browser(self) -> None:
        class FixedDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 11, 6, 8, 0, 30)

            def astimezone(self, tz=None):
                return self

        messages: list[str] = []
        scheduler = SchedulerService(
            lambda _day: (
                "08:01",
                [Lesson(1, "Math", 50, 5, "https://meet.example/math")],
            ),
            lambda message: messages.append(message),
            poll_seconds=1,
        )
        with patch(
            "studenthelper.schedule.webbrowser.open", return_value=True
        ) as open_browser, patch("studenthelper.schedule.datetime", FixedDateTime):
            def stop_after_notification(message: str) -> None:
                messages.append(message)
                scheduler._stop_event.set()

            scheduler.notify = stop_after_notification
            asyncio.run(scheduler._run())

        open_browser.assert_called_once_with("https://meet.example/math", new=2)
        self.assertIn("Opening meeting link for Math.", messages)

    def test_scheduler_reports_when_default_browser_cannot_open_link(self) -> None:
        class FixedDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 11, 6, 8, 0, 30)

            def astimezone(self, tz=None):
                return self

        messages: list[str] = []
        scheduler = SchedulerService(
            lambda _day: (
                "08:01",
                [Lesson(1, "Math", 50, 5, "https://meet.example/math")],
            ),
            lambda message: messages.append(message),
            poll_seconds=1,
        )
        def stop_after_notification(message: str) -> None:
            messages.append(message)
            scheduler._stop_event.set()

        scheduler.notify = stop_after_notification
        with patch(
            "studenthelper.schedule.webbrowser.open", return_value=False
        ), patch("studenthelper.schedule.datetime", FixedDateTime):
            asyncio.run(scheduler._run())

        self.assertTrue(
            any(message.startswith("Could not open link for 'Math'") for message in messages)
        )


if __name__ == "__main__":
    unittest.main()
