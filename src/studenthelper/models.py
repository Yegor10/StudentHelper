"""Typed data records used by the local database and scheduler."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Lesson:
    id: int | None
    title: str
    duration_minutes: int
    break_minutes: int
    meeting_url: str
    position: int = 0


@dataclass(frozen=True)
class ScheduledLesson:
    lesson: Lesson
    starts_at: datetime
    ends_at: datetime


@dataclass(frozen=True)
class DiaryEntry:
    id: int
    task_text: str
    image_path: str | None
    solution: str
    created_at: str
    scheduled_date: str | None = None
