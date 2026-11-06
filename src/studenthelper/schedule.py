"""Schedule time calculation and browser-link scheduling."""

import asyncio
import threading
from datetime import date, datetime, time, timedelta
from typing import Callable
from urllib.parse import urlparse
import webbrowser

from studenthelper.models import Lesson, ScheduledLesson
from studenthelper.schedule_store import WEEKDAYS


def build_schedule(lessons: list[Lesson], start_at: datetime) -> list[ScheduledLesson]:
    result: list[ScheduledLesson] = []
    current_start = start_at
    for lesson in lessons:
        end_at = current_start + timedelta(minutes=lesson.duration_minutes)
        result.append(ScheduledLesson(lesson, current_start, end_at))
        current_start = end_at + timedelta(minutes=lesson.break_minutes)
    return result


def next_occurrences(
    lessons: list[Lesson], start_time: time, now: datetime
) -> list[ScheduledLesson]:
    today_start = datetime.combine(now.date(), start_time, tzinfo=now.tzinfo)
    schedule = build_schedule(lessons, today_start)
    if not schedule or schedule[-1].ends_at <= now:
        tomorrow_start = datetime.combine(
            now.date() + timedelta(days=1), start_time, tzinfo=now.tzinfo
        )
        return build_schedule(lessons, tomorrow_start)
    return schedule


def weekday_name(day: date) -> str | None:
    return WEEKDAYS[day.weekday()] if day.weekday() < len(WEEKDAYS) else None


def next_week_school_dates(today: date) -> list[date]:
    next_monday = today + timedelta(days=7 - today.weekday())
    return weekdays_from_monday(next_monday)


def weekdays_from_monday(monday: date) -> list[date]:
    if monday.weekday() != 0:
        raise ValueError("The calendar week must start on Monday.")
    return [monday + timedelta(days=offset) for offset in range(5)]


def validate_meeting_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


class SchedulerService:
    """Checks the daily schedule off the UI thread and opens meeting links."""

    def __init__(
        self,
        get_day_schedule: Callable[[str], tuple[str, list[Lesson]]],
        notify: Callable[[str], None],
        poll_seconds: int = 5,
    ) -> None:
        self.get_day_schedule = get_day_schedule
        self.notify = notify
        self.poll_seconds = poll_seconds
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._thread_main, name="studenthelper-scheduler", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)

    def _thread_main(self) -> None:
        try:
            asyncio.run(self._run())
        except Exception as error:
            self.notify(f"Scheduler stopped: {error}")

    async def _run(self) -> None:
        handled: set[tuple[date, int]] = set()
        while not self._stop_event.is_set():
            now = datetime.now().astimezone()
            day = weekday_name(now.date())
            if day is not None:
                try:
                    start_time_value, lessons = self.get_day_schedule(day)
                    start_time = datetime.strptime(start_time_value, "%H:%M").time()
                except ValueError:
                    self.notify("Scheduler paused: start time must use HH:MM.")
                    start_time = None
                if start_time is not None:
                    for item in next_occurrences(lessons, start_time, now):
                        lesson_id = item.lesson.id
                        key = (
                            item.starts_at.date(),
                            lesson_id or item.lesson.position,
                        )
                        if key in handled:
                            continue
                        open_at = item.starts_at - timedelta(minutes=1)
                        if open_at <= now < item.starts_at:
                            handled.add(key)
                            if not item.lesson.meeting_url:
                                self.notify(
                                    f"'{item.lesson.title}' starts in 1 minute, "
                                    "but has no meeting URL."
                                )
                                continue
                            try:
                                if not webbrowser.open(item.lesson.meeting_url, new=2):
                                    raise RuntimeError(
                                        "The default browser could not open this link."
                                    )
                                self.notify(
                                    f"Opening meeting link for {item.lesson.title}."
                                )
                            except (OSError, RuntimeError) as error:
                                self.notify(
                                    f"Could not open link for '{item.lesson.title}': {error}"
                                )
                    handled = {item for item in handled if item[0] >= now.date()}
            await asyncio.to_thread(self._stop_event.wait, self.poll_seconds)
