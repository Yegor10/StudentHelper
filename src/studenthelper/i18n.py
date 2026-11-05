"""English and Ukrainian UI strings."""

TRANSLATIONS = {
    "en": {
        "app_title": "StudentHelper",
        "schedule": "Schedule",
        "diary": "Diary",
        "settings": "Settings",
        "schedule_title": "Your class schedule",
        "schedule_hint": "Set a daily start time. Meetings open one minute before class.",
        "start_time": "First lesson starts at (HH:MM)",
        "lesson": "Lesson",
        "lesson_title": "Class name",
        "duration": "Minutes",
        "break": "Break",
        "meeting_url": "Meeting URL (optional)",
        "add_lesson": "Add lesson",
        "save_schedule": "Save schedule",
        "diary_title": "Homework diary",
        "task_prompt": "Describe your homework or question…",
        "attach_image": "Attach image",
        "add_task": "Save task",
        "solve_ai": "Solve with AI",
        "solution": "Step-by-step solution",
        "select_task": "Select a saved task to view or solve it.",
        "no_image": "No image attached",
        "settings_title": "Application settings",
        "language": "Language",
        "api_key": "Gemini API key (leave blank to keep saved key)",
        "model": "Gemini model",
        "save_settings": "Save settings",
        "saved": "Saved successfully.",
        "task_saved": "Homework saved.",
        "solving": "Gemini is working on your solution…",
        "invalid_time": "Enter a valid start time in HH:MM format.",
        "invalid_lesson": "Check lesson names, durations, breaks, and URLs.",
        "add_task_first": "Enter homework text or attach an image first.",
        "english": "English",
        "ukrainian": "Українська",
        "file_types": "Images",
        "sidebar_subtitle": "Your study companion",
        "sidebar_footer": "ENGLISH  ·  УКРАЇНСЬКА",
        "appearance": "Appearance",
        "color_theme": "Accent color",
        "theme_blue": "Ocean blue",
        "theme_green": "Fresh green",
        "theme_dark_blue": "Midnight blue",
        "this_week": "This week",
        "no_homework": "Nothing planned",
        "image_homework": "Image homework",
        "more_homework": "+ {count} more",
        "weekday_monday": "Monday",
        "weekday_tuesday": "Tuesday",
        "weekday_wednesday": "Wednesday",
        "weekday_thursday": "Thursday",
        "weekday_friday": "Friday",
        "schedule_json": "Schedule saved in JSON.",
        "missing_gemini_key": "Gemini API key is missing. Add it in Settings before solving.",
        "empty_homework": "Add homework text or an image before solving.",
        "opening_link": "Opening meeting link…",
        "meeting_joined": "Meeting joined with microphone and camera confirmed off.",
        "scheduler_invalid_time": "Scheduler paused: start time must use HH:MM.",
        "scheduler_stopped": "Scheduler stopped: {error}",
        "scheduler_preparing": "Preparing to join {title}.",
        "scheduler_missing_url": "'{title}' starts in 1 minute, but has no meeting URL.",
        "scheduler_join_error": "Could not join '{title}': {error}",
    },
    "uk": {
        "app_title": "StudentHelper",
        "schedule": "Розклад",
        "diary": "Щоденник",
        "settings": "Налаштування",
        "schedule_title": "Розклад занять",
        "schedule_hint": "Вкажіть час початку дня. Зустріч відкриється за хвилину до заняття.",
        "start_time": "Початок першого заняття (ГГ:ХХ)",
        "lesson": "Заняття",
        "lesson_title": "Назва заняття",
        "duration": "Хвилини",
        "break": "Перерва",
        "meeting_url": "Посилання на зустріч (необов’язково)",
        "add_lesson": "Додати заняття",
        "save_schedule": "Зберегти розклад",
        "diary_title": "Щоденник домашніх завдань",
        "task_prompt": "Опишіть домашнє завдання або запитання…",
        "attach_image": "Додати зображення",
        "add_task": "Зберегти завдання",
        "solve_ai": "Розв’язати з ШІ",
        "solution": "Покрокове пояснення",
        "select_task": "Виберіть збережене завдання, щоб переглянути або розв’язати його.",
        "no_image": "Зображення не додано",
        "settings_title": "Налаштування програми",
        "language": "Мова",
        "api_key": "Ключ Gemini API (залиште порожнім, щоб не змінювати)",
        "model": "Модель Gemini",
        "save_settings": "Зберегти налаштування",
        "saved": "Успішно збережено.",
        "task_saved": "Завдання збережено.",
        "solving": "Gemini готує розв’язання…",
        "invalid_time": "Введіть коректний час у форматі ГГ:ХХ.",
        "invalid_lesson": "Перевірте назви занять, тривалість, перерви й посилання.",
        "add_task_first": "Спочатку введіть завдання або додайте зображення.",
        "english": "English",
        "ukrainian": "Українська",
        "file_types": "Зображення",
        "sidebar_subtitle": "Твій помічник у навчанні",
        "sidebar_footer": "ENGLISH  ·  УКРАЇНСЬКА",
        "appearance": "Режим вигляду",
        "color_theme": "Акцентний колір",
        "theme_blue": "Океанічний синій",
        "theme_green": "Свіжий зелений",
        "theme_dark_blue": "Темно-синій",
        "this_week": "Цей тиждень",
        "no_homework": "Немає завдань",
        "image_homework": "Завдання із зображенням",
        "more_homework": "Ще: {count}",
        "weekday_monday": "Понеділок",
        "weekday_tuesday": "Вівторок",
        "weekday_wednesday": "Середа",
        "weekday_thursday": "Четвер",
        "weekday_friday": "П’ятниця",
        "schedule_json": "Розклад збережено у JSON.",
        "missing_gemini_key": "Не вказано ключ Gemini API. Додайте його в налаштуваннях.",
        "empty_homework": "Спочатку введіть завдання або додайте зображення.",
        "opening_link": "Відкриваємо посилання на зустріч…",
        "meeting_joined": "Ви приєдналися до зустрічі з вимкненими мікрофоном і камерою.",
        "scheduler_invalid_time": "Планувальник призупинено: час має бути у форматі ГГ:ХХ.",
        "scheduler_stopped": "Планувальник зупинено: {error}",
        "scheduler_preparing": "Підготовка до приєднання: {title}.",
        "scheduler_missing_url": "За хвилину почнеться «{title}», але посилання не вказано.",
        "scheduler_join_error": "Не вдалося приєднатися до «{title}»: {error}",
    },
}


def translate(language: str, key: str) -> str:
    return TRANSLATIONS.get(language, TRANSLATIONS["en"]).get(
        key, TRANSLATIONS["en"].get(key, key)
    )


def translate_notification(language: str, message: str) -> str:
    if message == "Opening meeting link…":
        return translate(language, "opening_link")
    if message == "Meeting joined with microphone and camera confirmed off.":
        return translate(language, "meeting_joined")
    if message == "Scheduler paused: start time must use HH:MM.":
        return translate(language, "scheduler_invalid_time")
    if message.startswith("Scheduler stopped: "):
        return translate(language, "scheduler_stopped").format(
            error=message.removeprefix("Scheduler stopped: ")
        )
    if message.startswith("Preparing to join "):
        title = message.removeprefix("Preparing to join ").removesuffix(".")
        return translate(language, "scheduler_preparing").format(title=title)
    if message.startswith("'") and message.endswith(
        "' starts in 1 minute, but has no meeting URL."
    ):
        title = message.split("'", 2)[1]
        return translate(language, "scheduler_missing_url").format(title=title)
    if message.startswith("Could not join '") and "': " in message:
        title, error = message[len("Could not join '") :].split("': ", 1)
        return translate(language, "scheduler_join_error").format(
            title=title, error=error
        )
    return message
