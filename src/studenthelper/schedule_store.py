"""Atomic JSON storage for weekday schedules and desktop appearance preferences."""

import json
import os
import tempfile
from pathlib import Path

from studenthelper.models import Lesson

WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday")


def default_schedule_path() -> Path:
    app_data = os.getenv("APPDATA")
    root = Path(app_data) if app_data else Path.home() / ".studenthelper"
    return root / "StudentHelper" / "schedule.json" if app_data else root / "schedule.json"


class ScheduleStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_schedule_path()
        self.created_new = not self.path.exists()
        if not self.path.exists():
            bundled_schedule = Path(__file__).with_name("default-schedule.json")
            try:
                data = json.loads(bundled_schedule.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                raise RuntimeError(
                    f"Could not load the bundled default schedule: {error}"
                ) from error
            self._write(data)
        self._read()

    def _read(self) -> dict:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError(f"Could not read schedule file {self.path}: {error}") from error
        if (
            not isinstance(data, dict)
            or data.get("version") != 1
            or not isinstance(data.get("weekdays"), dict)
            or not isinstance(data.get("preferences"), dict)
        ):
            raise ValueError(f"Unsupported or invalid schedule file: {self.path}")
        return data

    def _write(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f"{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                json.dump(data, temporary_file, ensure_ascii=False, indent=2)
                temporary_file.write("\n")
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.replace(temporary_path, self.path)
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()

    def migrate_legacy_schedule(
        self, lessons: list[Lesson], start_time: str = "08:30"
    ) -> None:
        data = self._read()
        for day in WEEKDAYS:
            day_data = data["weekdays"].get(day, {})
            if self.created_new or not day_data.get("lessons"):
                day_data["start_time"] = start_time
                day_data["lessons"] = [
                    {
                        "title": lesson.title,
                        "duration_minutes": lesson.duration_minutes,
                        "break_minutes": lesson.break_minutes,
                        "meeting_url": lesson.meeting_url,
                    }
                    for lesson in lessons
                ]
                data["weekdays"][day] = day_data
        self._write(data)

    def get_day(self, day: str) -> tuple[str, list[Lesson]]:
        if day not in WEEKDAYS:
            raise ValueError(f"Unsupported school day: {day}")
        data = self._read()
        day_data = data["weekdays"].get(day, {})
        start_time = day_data.get("start_time", "08:30")
        raw_lessons = day_data.get("lessons", [])
        if not isinstance(start_time, str) or not isinstance(raw_lessons, list):
            raise ValueError(f"Invalid schedule data for {day}.")
        lessons: list[Lesson] = []
        for position, item in enumerate(raw_lessons):
            if not isinstance(item, dict):
                raise ValueError(f"Invalid lesson #{position + 1} for {day}.")
            try:
                lessons.append(
                    Lesson(
                        id=position + 1,
                        title=str(item["title"]),
                        duration_minutes=int(item["duration_minutes"]),
                        break_minutes=int(item["break_minutes"]),
                        meeting_url=str(item.get("meeting_url", "")),
                        position=position,
                    )
                )
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError(
                    f"Invalid lesson #{position + 1} for {day}."
                ) from error
        return start_time, lessons

    def save_day(self, day: str, start_time: str, lessons: list[Lesson]) -> None:
        if day not in WEEKDAYS:
            raise ValueError(f"Unsupported school day: {day}")
        data = self._read()
        data["weekdays"][day] = {
            "start_time": start_time,
            "lessons": [
                {
                    "title": lesson.title,
                    "duration_minutes": lesson.duration_minutes,
                    "break_minutes": lesson.break_minutes,
                    "meeting_url": lesson.meeting_url,
                }
                for lesson in lessons
            ],
        }
        self._write(data)

    def get_preference(self, key: str, default: str) -> str:
        value = self._read()["preferences"].get(key, default)
        return value if isinstance(value, str) else default

    def set_preferences(self, *, appearance: str, color_theme: str) -> None:
        if appearance not in {"System", "Light", "Dark"}:
            raise ValueError("Appearance must be System, Light, or Dark.")
        if color_theme not in {"blue", "green", "dark-blue"}:
            raise ValueError("Unsupported color theme.")
        data = self._read()
        data["preferences"] = {
            "appearance": appearance,
            "color_theme": color_theme,
        }
        self._write(data)
