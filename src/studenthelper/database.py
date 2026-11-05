"""SQLite persistence for schedule lessons, settings, and diary entries."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from studenthelper.models import DiaryEntry, Lesson


def default_database_path() -> Path:
    return Path.home() / ".studenthelper" / "studenthelper.sqlite3"


class Database:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_database_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS lessons (
                    id INTEGER PRIMARY KEY,
                    position INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    duration_minutes INTEGER NOT NULL CHECK(duration_minutes > 0),
                    break_minutes INTEGER NOT NULL CHECK(break_minutes >= 0),
                    meeting_url TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS diary_entries (
                    id INTEGER PRIMARY KEY,
                    task_text TEXT NOT NULL,
                    image_path TEXT,
                    solution TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    scheduled_date TEXT
                );
                """
            )
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(diary_entries)")
            }
            if "scheduled_date" not in columns:
                connection.execute(
                    "ALTER TABLE diary_entries ADD COLUMN scheduled_date TEXT"
                )
            connection.execute(
                "INSERT OR IGNORE INTO app_settings(key, value) VALUES (?, ?)",
                ("first_start_time", "08:30"),
            )

    def list_lessons(self) -> list[Lesson]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, position, title, duration_minutes, break_minutes, "
                "meeting_url FROM lessons ORDER BY position, id"
            ).fetchall()
        return [
            Lesson(
                id=row["id"],
                title=row["title"],
                duration_minutes=row["duration_minutes"],
                break_minutes=row["break_minutes"],
                meeting_url=row["meeting_url"],
                position=row["position"],
            )
            for row in rows
        ]

    def replace_lessons(self, lessons: list[Lesson]) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM lessons")
            connection.executemany(
                "INSERT INTO lessons(position, title, duration_minutes, "
                "break_minutes, meeting_url) VALUES (?, ?, ?, ?, ?)",
                [
                    (
                        position,
                        lesson.title,
                        lesson.duration_minutes,
                        lesson.break_minutes,
                        lesson.meeting_url,
                    )
                    for position, lesson in enumerate(lessons)
                ],
            )

    def get_setting(self, key: str, default: str = "") -> str:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM app_settings WHERE key = ?", (key,)
            ).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO app_settings(key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    def add_diary_entry(
        self, task_text: str, image_path: str | None, scheduled_date: str | None = None
    ) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO diary_entries(task_text, image_path, scheduled_date) "
                "VALUES (?, ?, ?)",
                (task_text, image_path, scheduled_date),
            )
            return int(cursor.lastrowid)

    def list_diary_entries(self) -> list[DiaryEntry]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, task_text, image_path, solution, created_at, scheduled_date "
                "FROM diary_entries ORDER BY id DESC"
            ).fetchall()
        return [
            DiaryEntry(
                id=row["id"],
                task_text=row["task_text"],
                image_path=row["image_path"],
                solution=row["solution"],
                created_at=row["created_at"],
                scheduled_date=row["scheduled_date"],
            )
            for row in rows
        ]

    def get_diary_entry(self, entry_id: int) -> DiaryEntry | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id, task_text, image_path, solution, created_at, scheduled_date "
                "FROM diary_entries WHERE id = ?",
                (entry_id,),
            ).fetchone()
        if row is None:
            return None
        return DiaryEntry(
            id=row["id"],
            task_text=row["task_text"],
            image_path=row["image_path"],
            solution=row["solution"],
            created_at=row["created_at"],
            scheduled_date=row["scheduled_date"],
        )

    def save_solution(self, entry_id: int, solution: str) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE diary_entries SET solution = ? WHERE id = ?",
                (solution, entry_id),
            )
            if cursor.rowcount != 1:
                raise LookupError(f"Diary entry {entry_id} no longer exists.")
