"""CustomTkinter interface and application entry point."""

import threading
import webbrowser
from collections.abc import Callable
from dataclasses import replace
from datetime import date, datetime
from datetime import timedelta
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import TypeVar

import customtkinter as ctk

from studenthelper.classroom import ClassroomAssignment, ClassroomService
from studenthelper.config import ConfigManager
from studenthelper.database import Database
from studenthelper.diary import GeminiDiaryService
from studenthelper.i18n import translate, translate_notification
from studenthelper.models import DiaryEntry, Lesson
from studenthelper.schedule import (
    SchedulerService,
    next_week_school_dates,
    validate_meeting_url,
    weekdays_from_monday,
)
from studenthelper.schedule_store import ScheduleStore, WEEKDAYS

T = TypeVar("T")


class StudentHelperApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.config_manager = ConfigManager()
        self.classroom = ClassroomService(self.config_manager)
        self.classroom_assignments: list[ClassroomAssignment] = []
        self.selected_classroom_assignment: ClassroomAssignment | None = None
        self.classroom_ai_answer = ""
        self.database = Database()
        self.schedule_store = ScheduleStore()
        if self.schedule_store.created_new:
            legacy_lessons = self.database.list_lessons()
            legacy_start_time = self.database.get_setting(
                "first_start_time", "08:30"
            )
        else:
            legacy_lessons = []
            legacy_start_time = "08:30"
        if self.schedule_store.created_new and (
            legacy_lessons or legacy_start_time != "08:30"
        ):
            self.schedule_store.migrate_legacy_schedule(
                legacy_lessons,
                legacy_start_time,
            )
        self.language = self.config_manager.language
        self.appearance = self.schedule_store.get_preference("appearance", "System")
        self.color_theme = self.schedule_store.get_preference("color_theme", "blue")
        ctk.set_appearance_mode(self.appearance)
        ctk.set_default_color_theme(self.color_theme)
        self.title(self.t("app_title"))
        self.geometry("1280x820")
        self.minsize(980, 650)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.sidebar = ctk.CTkFrame(self, width=205, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(6, weight=1)
        self.content = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.content.grid(row=0, column=1, sticky="nsew", padx=24, pady=22)
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

        self.scheduler = SchedulerService(
            self.schedule_store.get_day,
            self.notify_from_thread,
        )
        self.scheduler.start()
        self.current_view = "schedule"
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.show_view("schedule")

    def t(self, key: str) -> str:
        return translate(self.language, key)

    def render_sidebar(self) -> None:
        for child in self.sidebar.winfo_children():
            child.destroy()
        ctk.CTkLabel(
            self.sidebar,
            text="StudentHelper",
            font=ctk.CTkFont(size=23, weight="bold"),
        ).grid(row=0, column=0, padx=20, pady=(30, 2), sticky="w")
        ctk.CTkLabel(
            self.sidebar,
            text=self.t("sidebar_subtitle"),
            text_color=("gray45", "gray65"),
        ).grid(row=1, column=0, padx=20, pady=(0, 25), sticky="w")
        for row, name in enumerate(
            ("schedule", "diary", "classroom", "settings"), start=2
        ):
            ctk.CTkButton(
                self.sidebar,
                text=self.t(name),
                anchor="w",
                height=46,
                corner_radius=12,
                fg_color=("gray75", "gray25")
                if self.current_view == name
                else "transparent",
                text_color=("gray10", "gray90"),
                hover_color=("gray80", "gray30"),
                command=lambda selected=name: self.show_view(selected),
            ).grid(row=row, column=0, padx=12, pady=5, sticky="ew")
        ctk.CTkLabel(
            self.sidebar,
            text=self.t("sidebar_footer"),
            text_color=("gray45", "gray65"),
        ).grid(row=7, column=0, padx=16, pady=16, sticky="sw")

    def show_view(self, name: str) -> None:
        if (
            self.current_view == "schedule"
            and name != "schedule"
            and not self._save_schedule(show_success=False)
        ):
            return
        self.current_view = name
        self.render_sidebar()
        for row in range(7):
            self.content.grid_rowconfigure(row, weight=0)
        for child in self.content.winfo_children():
            child.destroy()
        if name == "schedule":
            self.build_schedule_view()
        elif name == "diary":
            self.build_diary_view()
        elif name == "classroom":
            self.build_classroom_view()
        else:
            self.build_settings_view()

    def heading(self, parent: ctk.CTkFrame, title: str, hint: str | None = None) -> None:
        ctk.CTkLabel(
            parent, text=title, font=ctk.CTkFont(size=26, weight="bold")
        ).grid(row=0, column=0, sticky="w", pady=(2, 4))
        if hint:
            ctk.CTkLabel(
                parent, text=hint, text_color=("gray40", "gray70"), wraplength=800
            ).grid(row=1, column=0, sticky="w", pady=(0, 18))

    def build_schedule_view(self) -> None:
        self.content.grid_rowconfigure(0, weight=0)
        self.heading(self.content, self.t("schedule_title"), self.t("schedule_hint"))

        today_weekday = date.today().weekday()
        default_day = WEEKDAYS[today_weekday] if today_weekday < 5 else WEEKDAYS[0]
        self.active_day = getattr(self, "active_day", default_day)
        self.weekday_labels = {
            self.t(f"weekday_{day}"): day for day in WEEKDAYS
        }
        self.weekday_segment = ctk.CTkSegmentedButton(
            self.content,
            values=list(self.weekday_labels),
            command=self.change_schedule_day,
            height=38,
            corner_radius=10,
        )
        self.weekday_segment.grid(row=2, column=0, sticky="w", pady=(10, 14))
        self.weekday_segment.set(self.t(f"weekday_{self.active_day}"))

        top = ctk.CTkFrame(self.content, fg_color="transparent")
        top.grid(row=3, column=0, sticky="ew", pady=(0, 12))
        top.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(top, text=self.t("start_time")).grid(
            row=0, column=0, padx=(0, 12), sticky="w"
        )
        self.start_time_entry = ctk.CTkEntry(top, width=120)
        start_time, lessons = self.schedule_store.get_day(self.active_day)
        self.start_time_entry.insert(0, start_time)
        self.start_time_entry.grid(row=0, column=1, sticky="w")

        headers = ctk.CTkFrame(self.content, fg_color="transparent")
        headers.grid(row=4, column=0, sticky="ew")
        headers.grid_columnconfigure(1, weight=2)
        headers.grid_columnconfigure(4, weight=4)
        for column, key in enumerate(
            ("lesson", "lesson_title", "duration", "break", "meeting_url")
        ):
            ctk.CTkLabel(headers, text=self.t(key), anchor="w").grid(
                row=0, column=column, padx=4, pady=4, sticky="ew"
            )
        self.lesson_list = ctk.CTkScrollableFrame(self.content, height=360)
        self.lesson_list.grid(row=5, column=0, sticky="nsew", pady=(4, 12))
        self.content.grid_rowconfigure(5, weight=1)
        self.lesson_rows: list[dict[str, ctk.CTkEntry]] = []
        self.lesson_row_frames: list[ctk.CTkFrame] = []
        for lesson in lessons:
            self.add_lesson_row(lesson)

        buttons = ctk.CTkFrame(self.content, fg_color="transparent")
        buttons.grid(row=6, column=0, sticky="ew")
        ctk.CTkButton(
            buttons,
            text=f"+  {self.t('add_lesson')}",
            height=40,
            corner_radius=10,
            command=self.add_lesson_row,
        ).pack(side="left", padx=(0, 10))
        ctk.CTkButton(
            buttons,
            text=self.t("save_schedule"),
            height=40,
            corner_radius=10,
            command=self.save_schedule,
        ).pack(side="left")

    def change_schedule_day(self, selected_label: str) -> None:
        new_day = self.weekday_labels[selected_label]
        if new_day == self.active_day:
            return
        if not self._save_schedule(show_success=False):
            self.weekday_segment.set(self.t(f"weekday_{self.active_day}"))
            return
        self.active_day = new_day
        self.show_view("schedule")

    def add_lesson_row(self, lesson: Lesson | None = None) -> None:
        lesson = lesson or Lesson(None, "", 45, 10, "")
        row_number = len(self.lesson_rows)
        row = ctk.CTkFrame(self.lesson_list, fg_color="transparent")
        row.grid(row=row_number, column=0, sticky="ew", pady=3)
        for column, weight in enumerate((0, 2, 1, 1, 4, 0)):
            row.grid_columnconfigure(column, weight=weight)
        label = ctk.CTkLabel(row, text=f"{row_number + 1}", width=28)
        label.grid(row=0, column=0, padx=3, sticky="w")
        widgets: dict[str, ctk.CTkEntry] = {}
        for column, key, value, width in (
            (1, "title", lesson.title, 130),
            (2, "duration", str(lesson.duration_minutes), 68),
            (3, "break", str(lesson.break_minutes), 68),
            (4, "url", lesson.meeting_url, 220),
        ):
            entry = ctk.CTkEntry(row, width=width)
            entry.insert(0, value)
            entry.grid(row=0, column=column, padx=3, sticky="ew")
            widgets[key] = entry
        ctk.CTkButton(
            row,
            text="×",
            width=32,
            fg_color="transparent",
            text_color=("gray20", "gray90"),
            command=lambda target=row: self.remove_lesson_row(target),
        ).grid(row=0, column=5, padx=(3, 0))
        self.lesson_rows.append(widgets)
        self.lesson_row_frames.append(row)

    def remove_lesson_row(self, target: ctk.CTkFrame) -> None:
        index = next(
            (
                i
                for i, widgets in enumerate(self.lesson_rows)
                if widgets["title"].master is target
            ),
            None,
        )
        if index is not None:
            target.destroy()
            self.lesson_rows.pop(index)
            self.lesson_row_frames.pop(index)
            for row_number, frame in enumerate(self.lesson_row_frames):
                frame.grid_configure(row=row_number)
                frame.winfo_children()[0].configure(text=str(row_number + 1))

    def save_schedule(self) -> None:
        self._save_schedule(show_success=True)

    def _save_schedule(self, show_success: bool) -> bool:
        start_time = self.start_time_entry.get().strip()
        try:
            datetime.strptime(start_time, "%H:%M")
            lessons: list[Lesson] = []
            for row in self.lesson_rows:
                title = row["title"].get().strip()
                duration = int(row["duration"].get())
                break_minutes = int(row["break"].get())
                url = row["url"].get().strip()
                if not title or duration < 1 or break_minutes < 0:
                    raise ValueError("Invalid lesson fields.")
                if url and not validate_meeting_url(url):
                    raise ValueError("Invalid meeting URL.")
                lessons.append(
                    Lesson(None, title, duration, break_minutes, url)
                )
        except (ValueError, TypeError):
            message = (
                self.t("invalid_time")
                if self._invalid_start_time(start_time)
                else self.t("invalid_lesson")
            )
            self.toast(message, error=True)
            return False
        try:
            self.schedule_store.save_day(self.active_day, start_time, lessons)
        except (OSError, ValueError, RuntimeError) as error:
            self.toast(str(error), error=True)
            return False
        if show_success:
            self.toast(self.t("saved"))
        return True

    @staticmethod
    def _invalid_start_time(value: str) -> bool:
        try:
            datetime.strptime(value, "%H:%M")
            return False
        except ValueError:
            return True

    def build_diary_view(self) -> None:
        self.content.grid_rowconfigure(0, weight=0)
        self.heading(self.content, self.t("diary_title"))
        self.content.grid_rowconfigure(2, weight=0)
        self.content.grid_rowconfigure(3, weight=0)
        self.content.grid_rowconfigure(4, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        next_monday = next_week_school_dates(date.today())[0]
        self.calendar_week_start = getattr(
            self, "calendar_week_start", next_monday
        )
        self.selected_calendar_date = getattr(
            self, "selected_calendar_date", self.calendar_week_start
        )
        self.selected_entry_id: int | None = None
        self.build_homework_calendar()
        self.build_homework_editor()
        self.build_homework_solution()

    def _format_homework_date(self, day: date) -> str:
        translated_day = self.t(f"weekday_{WEEKDAYS[day.weekday()]}")
        return f"{translated_day}, {day.strftime('%d.%m.%Y')}"

    def build_homework_calendar(self) -> None:
        calendar = ctk.CTkFrame(self.content, corner_radius=14)
        calendar.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        calendar.grid_columnconfigure(0, weight=1)
        toolbar = ctk.CTkFrame(calendar, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))
        toolbar.grid_columnconfigure(1, weight=1)
        ctk.CTkButton(
            toolbar,
            text="‹",
            width=36,
            height=32,
            command=lambda: self.shift_calendar_week(-7),
        ).grid(row=0, column=0, padx=(0, 8))
        self.calendar_title = ctk.CTkLabel(
            toolbar, font=ctk.CTkFont(size=16, weight="bold")
        )
        self.calendar_title.grid(row=0, column=1, sticky="w")
        ctk.CTkButton(
            toolbar,
            text=self.t("this_week"),
            width=110,
            height=32,
            command=self.show_current_week,
        ).grid(row=0, column=2, padx=4)
        ctk.CTkButton(
            toolbar,
            text="›",
            width=36,
            height=32,
            command=lambda: self.shift_calendar_week(7),
        ).grid(row=0, column=3, padx=(4, 0))

        self.calendar_grid = ctk.CTkFrame(calendar, fg_color="transparent")
        self.calendar_grid.grid(row=1, column=0, sticky="ew", padx=8, pady=(4, 10))
        for column in range(5):
            self.calendar_grid.grid_columnconfigure(column, weight=1, uniform="day")
        self.render_homework_calendar()

    def render_homework_calendar(self) -> None:
        for child in self.calendar_grid.winfo_children():
            child.destroy()
        days = weekdays_from_monday(self.calendar_week_start)
        self.calendar_title.configure(
            text=f"{days[0].strftime('%d.%m')} – {days[-1].strftime('%d.%m.%Y')}"
        )
        entries_by_date: dict[str, list[DiaryEntry]] = {}
        for entry in self.database.list_diary_entries():
            if entry.scheduled_date:
                entries_by_date.setdefault(entry.scheduled_date, []).append(entry)

        for column, day in enumerate(days):
            selected = day == self.selected_calendar_date
            card = ctk.CTkFrame(
                self.calendar_grid,
                corner_radius=10,
                fg_color=("gray90", "gray20") if selected else ("gray96", "gray14"),
                border_width=1,
                border_color=("gray82", "gray28"),
                height=164,
            )
            card.grid(row=0, column=column, padx=4, sticky="nsew")
            card.grid_propagate(False)
            card.grid_columnconfigure(0, weight=1)
            ctk.CTkButton(
                card,
                text=f"{self.t(f'weekday_{WEEKDAYS[day.weekday()]}')}  {day.day}",
                anchor="w",
                height=32,
                corner_radius=8,
                fg_color=("gray82", "gray28") if selected else "transparent",
                text_color=("gray10", "gray90"),
                hover_color=("gray80", "gray30"),
                command=lambda selected_day=day: self.select_calendar_date(
                    selected_day
                ),
            ).grid(row=0, column=0, padx=5, pady=(5, 2), sticky="ew")
            day_entries = entries_by_date.get(day.isoformat(), [])
            if not day_entries:
                ctk.CTkLabel(
                    card,
                    text=self.t("no_homework"),
                    text_color=("gray55", "gray60"),
                    anchor="nw",
                    font=ctk.CTkFont(size=11),
                ).grid(row=1, column=0, padx=9, pady=(8, 3), sticky="ew")
            for row, entry in enumerate(day_entries[:3], start=1):
                summary = entry.task_text.strip() or self.t("image_homework")
                if len(summary) > 24:
                    summary = summary[:22] + "…"
                ctk.CTkButton(
                    card,
                    text=summary,
                    anchor="w",
                    height=25,
                    corner_radius=6,
                    fg_color=("lightblue", "#24485A"),
                    text_color=("gray10", "gray95"),
                    hover_color=("skyblue", "#316078"),
                    font=ctk.CTkFont(size=11),
                    command=lambda item=entry: self.select_entry(item),
                ).grid(row=row, column=0, padx=5, pady=2, sticky="ew")
            if len(day_entries) > 3:
                ctk.CTkLabel(
                    card,
                    text=self.t("more_homework").format(count=len(day_entries) - 3),
                    anchor="w",
                    font=ctk.CTkFont(size=10),
                    text_color=("gray45", "gray70"),
                ).grid(row=4, column=0, padx=8, sticky="ew")

    def shift_calendar_week(self, days: int) -> None:
        self.calendar_week_start += timedelta(days=days)
        self.selected_calendar_date = self.calendar_week_start
        self.selected_date_label.configure(
            text=self._format_homework_date(self.selected_calendar_date)
        )
        self.render_homework_calendar()

    def show_current_week(self) -> None:
        today = date.today()
        self.calendar_week_start = today - timedelta(days=today.weekday())
        self.selected_calendar_date = (
            today if today.weekday() < 5 else self.calendar_week_start
        )
        self.selected_date_label.configure(
            text=self._format_homework_date(self.selected_calendar_date)
        )
        self.render_homework_calendar()

    def select_calendar_date(self, selected_day: date) -> None:
        self.selected_calendar_date = selected_day
        self.selected_date_label.configure(
            text=self._format_homework_date(selected_day)
        )
        self.render_homework_calendar()

    def build_homework_editor(self) -> None:
        editor = ctk.CTkFrame(self.content, corner_radius=14)
        editor.grid(row=3, column=0, sticky="ew", pady=(0, 12))
        editor.grid_columnconfigure(0, weight=1)
        self.selected_date_label = ctk.CTkLabel(
            editor,
            text=self._format_homework_date(self.selected_calendar_date),
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.selected_date_label.grid(
            row=0, column=0, padx=12, pady=(10, 0), sticky="w"
        )
        self.task_text = ctk.CTkTextbox(editor, height=64, wrap="word")
        self.task_text.grid(
            row=1, column=0, columnspan=3, padx=12, pady=8, sticky="ew"
        )
        self.draft_image_path: str | None = None
        self.image_label = ctk.CTkLabel(editor, text=self.t("no_image"), anchor="w")
        self.image_label.grid(row=2, column=0, padx=12, pady=(0, 10), sticky="ew")
        ctk.CTkButton(
            editor, text=self.t("attach_image"), command=self.attach_image
        ).grid(row=2, column=1, padx=6, pady=(0, 10))
        ctk.CTkButton(
            editor, text=self.t("add_task"), command=self.save_task
        ).grid(row=2, column=2, padx=(6, 12), pady=(0, 10))

    def build_homework_solution(self) -> None:
        lower = ctk.CTkFrame(self.content, fg_color="transparent")
        lower.grid(row=4, column=0, sticky="nsew")
        lower.grid_columnconfigure(0, weight=1)
        lower.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(
            lower,
            text=self.t("solution"),
            font=ctk.CTkFont(size=15, weight="bold"),
        ).grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.solution_box = ctk.CTkTextbox(lower, wrap="word")
        self.solution_box.grid(row=1, column=0, sticky="nsew")
        self.solution_box.insert("1.0", self.t("select_task"))
        self.solution_box.configure(state="disabled")
        ctk.CTkButton(
            lower,
            text=self.t("solve_ai"),
            command=self.solve_selected,
        ).grid(row=2, column=0, sticky="e", pady=(8, 0))

    def attach_image(self) -> None:
        path = filedialog.askopenfilename(
            title=self.t("attach_image"),
            filetypes=[
                (self.t("file_types"), "*.png *.jpg *.jpeg *.webp *.bmp"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self.draft_image_path = path
            self.image_label.configure(text=Path(path).name)

    def save_task(self) -> None:
        task_text = self.task_text.get("1.0", "end").strip()
        if not task_text and not self.draft_image_path:
            self.toast(self.t("add_task_first"), error=True)
            return
        scheduled_date = self.selected_calendar_date.isoformat()
        entry_id = self.database.add_diary_entry(
            task_text, self.draft_image_path, scheduled_date
        )
        self.task_text.delete("1.0", "end")
        self.draft_image_path = None
        self.image_label.configure(text=self.t("no_image"))
        self.render_homework_calendar()
        entry = self.database.get_diary_entry(entry_id)
        if entry:
            self.select_entry(entry)
        self.toast(self.t("task_saved"))

    def select_entry(self, entry: DiaryEntry) -> None:
        self.selected_entry_id = entry.id
        if entry.scheduled_date:
            entry_date = date.fromisoformat(entry.scheduled_date)
            self.calendar_week_start = entry_date - timedelta(
                days=entry_date.weekday()
            )
            self.selected_calendar_date = entry_date
            self.selected_date_label.configure(
                text=self._format_homework_date(entry_date)
            )
            self.render_homework_calendar()
        self.solution_box.configure(state="normal")
        self.solution_box.delete("1.0", "end")
        self.solution_box.insert("1.0", entry.solution or self.t("select_task"))
        self.solution_box.configure(state="disabled")

    def solve_selected(self) -> None:
        if self.selected_entry_id is None:
            self.toast(self.t("add_task_first"), error=True)
            return
        entry = self.database.get_diary_entry(self.selected_entry_id)
        if entry is None:
            self.toast(self.t("add_task_first"), error=True)
            return
        self.solution_box.configure(state="normal")
        self.solution_box.delete("1.0", "end")
        self.solution_box.insert("1.0", self.t("solving"))
        self.solution_box.configure(state="disabled")
        thread = threading.Thread(
            target=self._solve_in_background,
            args=(entry,),
            name="studenthelper-gemini",
            daemon=True,
        )
        thread.start()

    def _solve_in_background(self, entry: DiaryEntry) -> None:
        try:
            solution = GeminiDiaryService(self.config_manager).solve(
                entry.task_text, entry.image_path
            )
            self.database.save_solution(entry.id, solution)
            self._post_to_ui(self._show_solution, entry.id)
        except Exception as error:
            self._post_to_ui(self._show_solution_error, entry.id, str(error))

    def _show_solution(self, entry_id: int) -> None:
        if self.current_view == "diary":
            entry = self.database.get_diary_entry(entry_id)
            if entry:
                self.select_entry(entry)
        self.toast(self.t("saved"))

    def _show_solution_error(self, entry_id: int, message: str) -> None:
        if self.current_view == "diary" and self.selected_entry_id == entry_id:
            self.solution_box.configure(state="normal")
            self.solution_box.delete("1.0", "end")
            self.solution_box.insert("1.0", message)
            self.solution_box.configure(state="disabled")
        self.toast(message, error=True)

    def _post_to_ui(self, callback, *args: object) -> None:
        try:
            self.after(0, callback, *args)
        except RuntimeError:
            pass

    def build_classroom_view(self) -> None:
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(5, weight=1)
        self.heading(
            self.content,
            self.t("classroom_title"),
            self.t("classroom_hint"),
        )

        toolbar = ctk.CTkFrame(self.content, fg_color="transparent")
        toolbar.grid(row=2, column=0, sticky="ew", pady=(2, 10))
        self.classroom_connect_button = ctk.CTkButton(
            toolbar,
            text=self.t("classroom_connect"),
            height=40,
            corner_radius=10,
            command=self.connect_classroom,
        )
        self.classroom_connect_button.pack(side="left", padx=(0, 10))
        self.classroom_refresh_button = ctk.CTkButton(
            toolbar,
            text=self.t("classroom_refresh"),
            height=40,
            corner_radius=10,
            command=self.refresh_classroom_assignments,
        )
        self.classroom_refresh_button.pack(side="left")

        self.classroom_status = ctk.CTkLabel(
            self.content,
            text=self.t("classroom_not_connected"),
            anchor="w",
            text_color=("gray35", "gray75"),
            corner_radius=10,
            fg_color=("gray92", "gray17"),
            padx=14,
            pady=11,
        )
        self.classroom_status.grid(row=3, column=0, sticky="ew", pady=(0, 10))

        summary = ctk.CTkFrame(self.content, fg_color="transparent")
        summary.grid(row=4, column=0, sticky="ew", pady=(0, 10))
        summary.grid_columnconfigure((0, 1), weight=1, uniform="classroom-summary")
        self.classroom_count_value = self._classroom_metric(
            summary, 0, self.t("classroom_count")
        )
        self.classroom_deadline_value = self._classroom_metric(
            summary, 1, self.t("classroom_next_deadline")
        )

        workspace = ctk.CTkFrame(self.content, fg_color="transparent")
        workspace.grid(row=5, column=0, sticky="nsew")
        workspace.grid_columnconfigure(0, weight=2, uniform="classroom-pane")
        workspace.grid_columnconfigure(1, weight=3, uniform="classroom-pane")
        workspace.grid_rowconfigure(0, weight=1)

        assignment_panel = ctk.CTkFrame(workspace, corner_radius=14)
        assignment_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        assignment_panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            assignment_panel,
            text=self.t("classroom"),
            font=ctk.CTkFont(size=17, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=14, pady=(13, 8))
        self.classroom_assignment_list = ctk.CTkScrollableFrame(
            assignment_panel,
            corner_radius=10,
            height=460,
        )
        self.classroom_assignment_list.grid(
            row=1, column=0, sticky="nsew", padx=8, pady=(0, 8)
        )
        assignment_panel.grid_rowconfigure(1, weight=1)

        self.classroom_detail_panel = ctk.CTkScrollableFrame(
            workspace, corner_radius=14
        )
        self.classroom_detail_panel.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self.classroom_detail_panel.grid_columnconfigure(0, weight=1)
        self.render_classroom_assignments()
        self.render_classroom_detail()

    def open_classroom_link(self, url: str) -> None:
        try:
            if not webbrowser.open(url):
                raise RuntimeError("The default browser could not open this link.")
        except (OSError, RuntimeError) as error:
            self.toast(str(error), error=True)

    def _classroom_metric(
        self, parent: ctk.CTkFrame, column: int, title: str
    ) -> ctk.CTkLabel:
        card = ctk.CTkFrame(parent, corner_radius=12)
        card.grid(row=0, column=column, sticky="ew", padx=(0, 6) if column == 0 else (6, 0))
        ctk.CTkLabel(
            card,
            text=title,
            anchor="w",
            text_color=("gray40", "gray70"),
            font=ctk.CTkFont(size=11, weight="bold"),
        ).pack(fill="x", padx=13, pady=(9, 0))
        value = ctk.CTkLabel(
            card,
            text="—",
            anchor="w",
            font=ctk.CTkFont(size=17, weight="bold"),
        )
        value.pack(fill="x", padx=13, pady=(0, 9))
        return value

    def _format_classroom_due(
        self, due_at: datetime | None, due_has_time: bool = True
    ) -> str:
        if due_at is None:
            return self.t("classroom_due_none")
        current_date = date.today()
        if due_at.date() == current_date:
            due_date = self.t("classroom_due_today")
        elif due_at.date() == current_date + timedelta(days=1):
            due_date = self.t("classroom_due_tomorrow")
        else:
            due_date = due_at.strftime("%d.%m.%Y")
        formatted_date = (
            f"{due_date} {due_at.strftime('%H:%M')}"
            if due_has_time
            else due_date
        )
        return self.t("classroom_due").format(date=formatted_date)

    def render_classroom_assignments(self) -> None:
        for child in self.classroom_assignment_list.winfo_children():
            child.destroy()
        self.classroom_count_value.configure(
            text=str(len(self.classroom_assignments))
        )
        next_deadline = next(
            (
                assignment
                for assignment in self.classroom_assignments
                if assignment.due_at is not None
            ),
            None,
        )
        self.classroom_deadline_value.configure(
            text=(
                self._format_classroom_due(
                    next_deadline.due_at, next_deadline.due_has_time
                )
                if next_deadline
                else self.t("classroom_no_deadline")
            )
        )
        if not self.classroom_assignments:
            ctk.CTkLabel(
                self.classroom_assignment_list,
                text=self.t("classroom_empty"),
                text_color=("gray40", "gray70"),
                wraplength=310,
            ).pack(fill="x", padx=10, pady=14)
            return

        for assignment in self.classroom_assignments:
            selected = (
                self.selected_classroom_assignment is not None
                and assignment.course_id == self.selected_classroom_assignment.course_id
                and assignment.coursework_id
                == self.selected_classroom_assignment.coursework_id
            )
            card = ctk.CTkButton(
                self.classroom_assignment_list,
                text=f"{assignment.course_name}\n{assignment.title}\n"
                f"{self._format_classroom_due(assignment.due_at, assignment.due_has_time)}",
                anchor="w",
                height=82,
                corner_radius=10,
                fg_color=("gray82", "#24485A") if selected else ("gray93", "gray18"),
                text_color=("gray10", "gray92"),
                hover_color=("gray86", "gray25"),
                command=lambda item=assignment: self.select_classroom_assignment(item),
            )
            card.pack(fill="x", padx=5, pady=4)

    def render_classroom_detail(self) -> None:
        for child in self.classroom_detail_panel.winfo_children():
            child.destroy()
        assignment = self.selected_classroom_assignment
        if assignment is None:
            ctk.CTkLabel(
                self.classroom_detail_panel,
                text=self.t("classroom_select"),
                text_color=("gray40", "gray70"),
                wraplength=480,
                justify="center",
            ).grid(row=0, column=0, padx=30, pady=50)
            return

        ctk.CTkLabel(
            self.classroom_detail_panel,
            text=assignment.course_name.upper(),
            text_color=("gray40", "gray70"),
            anchor="w",
            font=ctk.CTkFont(size=11, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=18, pady=(16, 2))
        ctk.CTkLabel(
            self.classroom_detail_panel,
            text=assignment.title,
            anchor="w",
            justify="left",
            wraplength=550,
            font=ctk.CTkFont(size=21, weight="bold"),
        ).grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 4))
        ctk.CTkLabel(
            self.classroom_detail_panel,
            text=self._format_classroom_due(
                assignment.due_at, assignment.due_has_time
            ),
            anchor="w",
            text_color=("gray40", "gray70"),
        ).grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 10))
        description = ctk.CTkTextbox(
            self.classroom_detail_panel,
            height=110,
            wrap="word",
            corner_radius=10,
        )
        description.grid(row=3, column=0, sticky="ew", padx=14, pady=(0, 8))
        description.insert(
            "1.0", assignment.description or self.t("classroom_missing_description")
        )
        description.configure(state="disabled")
        if assignment.alternate_link:
            ctk.CTkButton(
                self.classroom_detail_panel,
                text=self.t("classroom_open"),
                fg_color="transparent",
                text_color=("gray20", "#8fd8cb"),
                anchor="w",
                command=lambda url=assignment.alternate_link: self.open_classroom_link(
                    url
                ),
            ).grid(row=4, column=0, sticky="w", padx=14, pady=(0, 8))

        ctk.CTkLabel(
            self.classroom_detail_panel,
            text=self.t("classroom_attachments"),
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        ).grid(row=5, column=0, sticky="ew", padx=18, pady=(4, 2))
        attachment_text = (
            ", ".join(assignment.attachments)
            if assignment.attachments
            else self.t("classroom_no_attachments")
        )
        self.classroom_attachment_status = ctk.CTkLabel(
            self.classroom_detail_panel,
            text=attachment_text,
            anchor="w",
            justify="left",
            wraplength=540,
            text_color=("gray40", "gray70"),
        )
        self.classroom_attachment_status.grid(
            row=6, column=0, sticky="ew", padx=18, pady=(0, 7)
        )
        file_row = ctk.CTkFrame(self.classroom_detail_panel, fg_color="transparent")
        file_row.grid(row=7, column=0, sticky="ew", padx=14, pady=(0, 5))
        file_row.grid_columnconfigure(0, weight=1)
        self.classroom_file_path: str | None = None
        self.classroom_file_label = ctk.CTkLabel(
            file_row,
            text=self.t("classroom_choose_file"),
            anchor="w",
            text_color=("gray40", "gray70"),
        )
        self.classroom_file_label.grid(row=0, column=0, sticky="ew", padx=(3, 8))
        ctk.CTkButton(
            file_row,
            text=self.t("classroom_oauth_browse"),
            width=120,
            command=self.choose_classroom_work_file,
        ).grid(row=0, column=1)
        actions = ctk.CTkFrame(self.classroom_detail_panel, fg_color="transparent")
        actions.grid(row=8, column=0, sticky="ew", padx=14, pady=(0, 10))
        self.classroom_attach_button = ctk.CTkButton(
            actions,
            text=self.t("classroom_attach"),
            command=self.attach_classroom_file,
        )
        self.classroom_attach_button.pack(side="left", padx=(0, 8))
        self.classroom_turn_in_button = ctk.CTkButton(
            actions,
            text=self.t("classroom_turn_in"),
            command=self.turn_in_classroom_assignment,
            state="normal" if assignment.attachments else "disabled",
        )
        self.classroom_turn_in_button.pack(side="left")

        ai_box = ctk.CTkFrame(self.classroom_detail_panel, corner_radius=11)
        ai_box.grid(row=9, column=0, sticky="ew", padx=14, pady=(4, 14))
        ai_box.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            ai_box,
            text=self.t("classroom_ai_title"),
            anchor="w",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 0))
        ctk.CTkLabel(
            ai_box,
            text=self.t("classroom_ai_hint"),
            anchor="w",
            justify="left",
            wraplength=500,
            text_color=("gray40", "gray70"),
        ).grid(row=1, column=0, sticky="ew", padx=12, pady=(2, 6))
        self.classroom_ai_button = ctk.CTkButton(
            ai_box,
            text=self.t("classroom_ai_explain"),
            command=self.explain_classroom_assignment,
        )
        self.classroom_ai_button.grid(
            row=2, column=0, sticky="w", padx=12, pady=(0, 8)
        )
        self.classroom_ai_text = ctk.CTkTextbox(
            ai_box, height=120, wrap="word", corner_radius=8
        )
        self.classroom_ai_text.grid(
            row=3, column=0, sticky="ew", padx=10, pady=(0, 8)
        )
        if self.classroom_ai_answer:
            self.classroom_ai_text.insert("1.0", self.classroom_ai_answer)
        else:
            self.classroom_ai_text.insert("1.0", self.t("classroom_ai_empty"))
        self.classroom_ai_text.configure(state="disabled")
        self.classroom_ai_download_button = ctk.CTkButton(
            ai_box,
            text=self.t("classroom_ai_download"),
            command=self.download_classroom_explanation,
            state="normal" if self.classroom_ai_answer else "disabled",
        )
        self.classroom_ai_download_button.grid(
            row=4, column=0, sticky="w", padx=12, pady=(0, 10)
        )

    def select_classroom_assignment(
        self, assignment: ClassroomAssignment
    ) -> None:
        self.selected_classroom_assignment = assignment
        self.classroom_ai_answer = ""
        self.render_classroom_assignments()
        self.render_classroom_detail()

    def connect_classroom(self) -> None:
        self.classroom_status.configure(text=self.t("classroom_connecting"))
        self._run_classroom_task(
            self.classroom_connect_button,
            self.t("classroom_connecting"),
            self.classroom.connect,
            self._classroom_connected,
        )

    def _classroom_connected(self, _result: object) -> None:
        self.classroom_status.configure(text=self.t("classroom_connected"))
        self.toast(self.t("classroom_connected"))
        self.refresh_classroom_assignments()

    def refresh_classroom_assignments(self) -> None:
        self.classroom_status.configure(text=self.t("classroom_loading"))
        self._run_classroom_task(
            self.classroom_refresh_button,
            self.t("classroom_loading"),
            self.classroom.fetch_assignments,
            self._classroom_assignments_loaded,
        )

    def _classroom_assignments_loaded(
        self, assignments: list[ClassroomAssignment]
    ) -> None:
        selected_key = (
            (
                self.selected_classroom_assignment.course_id,
                self.selected_classroom_assignment.coursework_id,
            )
            if self.selected_classroom_assignment
            else None
        )
        self.classroom_assignments = assignments
        self.selected_classroom_assignment = next(
            (
                item
                for item in assignments
                if selected_key == (item.course_id, item.coursework_id)
            ),
            None,
        )
        self.classroom_status.configure(
            text=self.t("classroom_loaded").format(count=len(assignments))
        )
        self.render_classroom_assignments()
        self.render_classroom_detail()

    def _run_classroom_task(
        self,
        button: ctk.CTkButton,
        busy_text: str,
        operation: Callable[[], T],
        on_success: Callable[[T], None],
    ) -> None:
        original_text = button.cget("text")
        button.configure(text=busy_text, state="disabled")

        def worker() -> None:
            try:
                result = operation()
            except Exception as error:
                self._post_to_ui(
                    self._finish_classroom_task,
                    button,
                    original_text,
                    None,
                    error,
                    on_success,
                )
            else:
                self._post_to_ui(
                    self._finish_classroom_task,
                    button,
                    original_text,
                    result,
                    None,
                    on_success,
                )

        threading.Thread(
            target=worker,
            name="studenthelper-classroom",
            daemon=True,
        ).start()

    def _finish_classroom_task(
        self,
        button: ctk.CTkButton,
        original_text: str,
        result: T | None,
        error: Exception | None,
        on_success: Callable[[T], None],
    ) -> None:
        try:
            if button.winfo_exists():
                button.configure(text=original_text, state="normal")
        except RuntimeError:
            return
        if self.current_view != "classroom":
            return
        if error is not None:
            message = str(error)
            if "temporarily unavailable (503)" in message:
                message = self.t("classroom_service_unavailable")
            self.classroom_status.configure(text=message)
            self.toast(message, error=True)
            return
        on_success(result)

    def choose_classroom_work_file(self) -> None:
        path = filedialog.askopenfilename(
            title=self.t("classroom_choose_file"),
            filetypes=[("All files", "*.*")],
        )
        if path:
            self.classroom_file_path = path
            self.classroom_file_label.configure(text=Path(path).name)

    def attach_classroom_file(self) -> None:
        assignment = self.selected_classroom_assignment
        if assignment is None:
            return
        if not self.classroom_file_path:
            self.toast(self.t("classroom_choose_file"), error=True)
            return
        path = Path(self.classroom_file_path)
        self._run_classroom_task(
            self.classroom_attach_button,
            self.t("classroom_attaching"),
            lambda: self.classroom.attach_file(assignment, path),
            lambda name: self._classroom_file_attached(assignment, name),
        )

    def _classroom_file_attached(
        self, assignment: ClassroomAssignment, name: str
    ) -> None:
        updated = replace(
            assignment,
            attachments=(*assignment.attachments, str(name)),
        )
        self._replace_classroom_assignment(updated)
        self.classroom_status.configure(
            text=self.t("classroom_attached").format(name=name)
        )
        self.toast(self.t("classroom_attached").format(name=name))

    def _replace_classroom_assignment(
        self, replacement: ClassroomAssignment
    ) -> None:
        self.classroom_assignments = [
            replacement
            if (
                item.course_id == replacement.course_id
                and item.coursework_id == replacement.coursework_id
            )
            else item
            for item in self.classroom_assignments
        ]
        self.selected_classroom_assignment = replacement
        self.render_classroom_assignments()
        self.render_classroom_detail()

    def turn_in_classroom_assignment(self) -> None:
        assignment = self.selected_classroom_assignment
        if assignment is None:
            return
        confirmed = messagebox.askyesno(
            self.t("classroom_turn_in"),
            self.t("classroom_turn_in_confirm").format(
                title=assignment.title,
                course=assignment.course_name,
            ),
            parent=self,
        )
        if not confirmed:
            return
        self._run_classroom_task(
            self.classroom_turn_in_button,
            self.t("classroom_turning_in"),
            lambda: self.classroom.turn_in(assignment),
            lambda _result: self._classroom_assignment_turned_in(assignment),
        )

    def _classroom_assignment_turned_in(
        self, assignment: ClassroomAssignment
    ) -> None:
        self.classroom_assignments = [
            item
            for item in self.classroom_assignments
            if (
                item.course_id != assignment.course_id
                or item.coursework_id != assignment.coursework_id
            )
        ]
        self.selected_classroom_assignment = None
        self.classroom_status.configure(text=self.t("classroom_submitted"))
        self.render_classroom_assignments()
        self.render_classroom_detail()
        self.toast(self.t("classroom_submitted"))

    def explain_classroom_assignment(self) -> None:
        assignment = self.selected_classroom_assignment
        if assignment is None:
            return
        prompt = (
            f"Course: {assignment.course_name}\n"
            f"Assignment: {assignment.title}\n\n{assignment.description}"
        )
        self._run_classroom_task(
            self.classroom_ai_button,
            self.t("classroom_ai_working"),
            lambda: GeminiDiaryService(self.config_manager).solve(prompt),
            self._classroom_ai_ready,
        )

    def _classroom_ai_ready(self, answer: str) -> None:
        self.classroom_ai_answer = answer
        self.render_classroom_detail()

    def download_classroom_explanation(self) -> None:
        if not self.classroom_ai_answer:
            self.toast(self.t("classroom_ai_empty"), error=True)
            return
        path = filedialog.asksaveasfilename(
            title=self.t("classroom_ai_download"),
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt")],
            initialfile="studenthelper-explanation.txt",
        )
        if not path:
            return
        try:
            Path(path).write_text(self.classroom_ai_answer, encoding="utf-8")
        except OSError as error:
            self.toast(str(error), error=True)
            return
        self.toast(self.t("saved"))

    def build_settings_view(self) -> None:
        self.content.grid_rowconfigure(0, weight=0)
        self.heading(self.content, self.t("settings_title"))
        form = ctk.CTkScrollableFrame(self.content)
        form.grid(row=2, column=0, sticky="nsew", pady=(12, 0))
        self.content.grid_rowconfigure(2, weight=1)
        form.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(form, text=self.t("language"), anchor="w").grid(
            row=0, column=0, padx=16, pady=(18, 5), sticky="ew"
        )
        self.language_menu = ctk.CTkOptionMenu(
            form,
            values=["English", "Українська"],
        )
        self.language_menu.set("English" if self.language == "en" else "Українська")
        self.language_menu.grid(row=1, column=0, padx=16, sticky="w")

        ctk.CTkLabel(form, text=self.t("api_key"), anchor="w").grid(
            row=2, column=0, padx=16, pady=(14, 5), sticky="ew"
        )
        self.api_key_entry = ctk.CTkEntry(form, show="•")
        self.api_key_entry.grid(row=3, column=0, padx=16, sticky="ew")
        ctk.CTkLabel(form, text=self.t("model"), anchor="w").grid(
            row=4, column=0, padx=16, pady=(18, 5), sticky="ew"
        )
        self.model_entry = ctk.CTkEntry(form)
        self.model_entry.insert(0, self.config_manager.gemini_model)
        self.model_entry.grid(row=5, column=0, padx=16, sticky="ew")
        ctk.CTkLabel(form, text=self.t("appearance"), anchor="w").grid(
            row=6, column=0, padx=16, pady=(20, 5), sticky="ew"
        )
        self.appearance_menu = ctk.CTkOptionMenu(
            form,
            values=["System", "Light", "Dark"],
            command=self.apply_appearance,
        )
        self.appearance_menu.set(self.appearance)
        self.appearance_menu.grid(row=7, column=0, padx=16, sticky="w")
        ctk.CTkLabel(form, text=self.t("color_theme"), anchor="w").grid(
            row=8, column=0, padx=16, pady=(16, 5), sticky="ew"
        )
        self.color_theme_labels = {
            self.t("theme_blue"): "blue",
            self.t("theme_green"): "green",
            self.t("theme_dark_blue"): "dark-blue",
        }
        self.color_theme_menu = ctk.CTkOptionMenu(
            form,
            values=list(self.color_theme_labels),
        )
        self.color_theme_menu.set(
            next(
                label
                for label, theme in self.color_theme_labels.items()
                if theme == self.color_theme
            )
        )
        self.color_theme_menu.grid(row=9, column=0, padx=16, sticky="w")
        ctk.CTkLabel(
            form,
            text=self.t("classroom_oauth_file"),
            anchor="w",
        ).grid(row=10, column=0, padx=16, pady=(18, 5), sticky="ew")
        oauth_row = ctk.CTkFrame(form, fg_color="transparent")
        oauth_row.grid(row=11, column=0, padx=16, sticky="ew")
        oauth_row.grid_columnconfigure(0, weight=1)
        self.classroom_oauth_entry = ctk.CTkEntry(oauth_row)
        if self.config_manager.classroom_client_file:
            self.classroom_oauth_entry.insert(
                0, self.config_manager.classroom_client_file
            )
        self.classroom_oauth_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ctk.CTkButton(
            oauth_row,
            text=self.t("classroom_oauth_browse"),
            command=self.choose_classroom_oauth_file,
        ).grid(row=0, column=1)
        ctk.CTkLabel(
            form,
            text=self.t("classroom_oauth_hint"),
            anchor="w",
            justify="left",
            wraplength=780,
            text_color=("gray45", "gray65"),
        ).grid(row=12, column=0, padx=16, pady=(6, 0), sticky="ew")
        ctk.CTkButton(
            form, text=self.t("save_settings"), command=self.save_settings
        ).grid(row=13, column=0, padx=16, pady=20, sticky="w")

    def choose_classroom_oauth_file(self) -> None:
        path = filedialog.askopenfilename(
            title=self.t("classroom_oauth_file"),
            filetypes=[(self.t("classroom_oauth_filter"), "*.json")],
        )
        if path:
            self.classroom_oauth_entry.delete(0, "end")
            self.classroom_oauth_entry.insert(0, path)

    def apply_appearance(self, appearance: str) -> None:
        ctk.set_appearance_mode(appearance)

    def save_settings(self) -> None:
        selected_language = self.language_menu.get()
        language = "uk" if selected_language == "Українська" else "en"
        key = self.api_key_entry.get().strip()
        appearance = self.appearance_menu.get()
        color_theme = self.color_theme_labels[self.color_theme_menu.get()]
        try:
            self.schedule_store.set_preferences(
                appearance=appearance,
                color_theme=color_theme,
            )
            self.config_manager.save(
                api_key=key or None,
                model=self.model_entry.get(),
                language=language,
                classroom_client_file=self.classroom_oauth_entry.get(),
            )
        except (OSError, ValueError) as error:
            self.toast(str(error), error=True)
            return
        self.language = language
        self.appearance = appearance
        self.color_theme = color_theme
        ctk.set_appearance_mode(self.appearance)
        ctk.set_default_color_theme(self.color_theme)
        self.show_view("settings")
        self.toast(self.t("saved"))

    def notify_from_thread(self, message: str) -> None:
        self._post_to_ui(self.toast, translate_notification(self.language, message))

    def toast(self, message: str, error: bool = False) -> None:
        dialog = ctk.CTkToplevel(self)
        dialog.title(self.t("app_title"))
        dialog.geometry("440x120")
        dialog.transient(self)
        dialog.attributes("-topmost", True)
        color = ("#FDECEC", "#482626") if error else ("#E8F5E9", "#23432A")
        text_color = ("#8B1E1E", "#FFB4AB") if error else ("#1B5E20", "#B7F7C2")
        ctk.CTkLabel(
            dialog,
            text=message,
            fg_color=color,
            text_color=text_color,
            corner_radius=10,
            wraplength=390,
        ).pack(fill="both", expand=True, padx=12, pady=12)
        dialog.after(3500, dialog.destroy)

    def close(self) -> None:
        if self.current_view == "schedule" and not self._save_schedule(
            show_success=False
        ):
            return
        self.scheduler.stop()
        self.destroy()


def main() -> None:
    app = StudentHelperApp()
    app.mainloop()


if __name__ == "__main__":
    main()
