"""Schedule time calculation and asynchronous meeting automation."""

import asyncio
import re
import threading
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from playwright.async_api import (
    Page,
    TimeoutError as PlaywrightTimeoutError,
    async_playwright,
)

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


class PlaywrightMeetingAutomation:
    """Keeps a signed-in Chromium profile alive for scheduled web meetings."""

    def __init__(self, profile_path: Path | None = None) -> None:
        self.profile_path = profile_path or (
            Path.home() / ".studenthelper" / "browser-profile"
        )
        self._playwright = None
        self._context = None
        self._lock = asyncio.Lock()

    async def prepare_and_join(self, url: str, notify: Callable[[str], None]) -> None:
        if not validate_meeting_url(url):
            raise ValueError("Meeting URL must be a valid http or https address.")
        async with self._lock:
            if self._context is None:
                self.profile_path.mkdir(parents=True, exist_ok=True)
                self._playwright = await async_playwright().start()
                try:
                    self._context = (
                        await self._playwright.chromium.launch_persistent_context(
                            str(self.profile_path),
                            headless=False,
                        )
                    )
                except Exception:
                    await self._playwright.stop()
                    self._playwright = None
                    raise

            page = await self._context.new_page()
            notify("Opening meeting link…")
            await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            await self._try_join_in_browser(page)
            await page.wait_for_load_state("domcontentloaded", timeout=15_000)
            await self._ensure_device_off(
                page,
                r"(turn off|mute(?: my)?).*(microphone|mic|audio)|mute (?:my )?microphone|mute audio",
                r"(turn on|unmute).*(microphone|mic|audio)|(microphone|mic|audio).*(off|muted)",
                "microphone",
            )
            await self._ensure_device_off(
                page,
                r"(turn off|disable|stop).*(camera|video)|stop video",
                r"(turn on|enable|start).*(camera|video)|(camera|video).*(off|disabled)",
                "camera",
            )
            await self._click_join(page)
            notify("Meeting joined with microphone and camera confirmed off.")

    async def _try_join_in_browser(self, page: Page) -> None:
        browser_join = page.get_by_role(
            "button",
            name=re.compile(r"join from (your )?browser", re.IGNORECASE),
        )
        if await browser_join.count():
            await browser_join.first.click(timeout=5_000)
            await page.wait_for_timeout(1_000)

    async def _ensure_device_off(
        self, page: Page, enabled_pattern: str, disabled_pattern: str, device: str
    ) -> None:
        disabled = page.get_by_role(
            "button", name=re.compile(disabled_pattern, re.IGNORECASE)
        )
        if await disabled.count():
            return
        enabled = page.get_by_role(
            "button", name=re.compile(enabled_pattern, re.IGNORECASE)
        )
        if await enabled.count():
            try:
                await enabled.first.click(timeout=3_000)
            except PlaywrightTimeoutError:
                raise RuntimeError(f"Could not turn off the meeting {device}.") from None
            if await disabled.count():
                return
        raise RuntimeError(
            f"Could not confirm the meeting {device} is off; "
            "the meeting was not joined."
        )

    async def _click_join(self, page: Page) -> None:
        join_button = page.get_by_role(
            "button",
            name=re.compile(
                r"^(join now|join meeting|ask to join|join)$", re.IGNORECASE
            ),
        )
        if await join_button.count():
            await join_button.first.click(timeout=10_000)
            return
        join_link = page.get_by_role(
            "link",
            name=re.compile(r"^(join now|join meeting|join)$", re.IGNORECASE),
        )
        if await join_link.count():
            await join_link.first.click(timeout=10_000)
            return
        raise RuntimeError(
            "Could not find a recognized Join button. The meeting was not joined."
        )

    async def close(self) -> None:
        async with self._lock:
            if self._context is not None:
                await self._context.close()
                self._context = None
            if self._playwright is not None:
                await self._playwright.stop()
                self._playwright = None


class SchedulerService:
    """Checks the daily schedule off the UI thread and opens due meetings."""

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
        automation = PlaywrightMeetingAutomation()
        handled: set[tuple[date, int]] = set()
        try:
            while not self._stop_event.is_set():
                now = datetime.now().astimezone()
                day = weekday_name(now.date())
                if day is not None:
                    try:
                        start_time_value, lessons = self.get_day_schedule(day)
                        start_time = datetime.strptime(
                            start_time_value, "%H:%M"
                        ).time()
                    except ValueError:
                        self.notify("Scheduler paused: start time must use HH:MM.")
                        start_time = None
                    if start_time is not None:
                        for item in next_occurrences(lessons, start_time, now):
                            lesson_id = item.lesson.id
                            key = (item.starts_at.date(), lesson_id or item.lesson.position)
                            if key in handled:
                                continue
                            join_at = item.starts_at - timedelta(minutes=1)
                            if join_at <= now < item.starts_at:
                                handled.add(key)
                                if not item.lesson.meeting_url:
                                    self.notify(
                                        f"'{item.lesson.title}' starts in 1 minute, "
                                        "but has no meeting URL."
                                    )
                                    continue
                                self.notify(f"Preparing to join {item.lesson.title}.")
                                try:
                                    await automation.prepare_and_join(
                                        item.lesson.meeting_url, self.notify
                                    )
                                except Exception as error:
                                    self.notify(
                                        f"Could not join '{item.lesson.title}': {error}"
                                    )
                        handled = {item for item in handled if item[0] >= now.date()}
                await asyncio.to_thread(self._stop_event.wait, self.poll_seconds)
        finally:
            await automation.close()
