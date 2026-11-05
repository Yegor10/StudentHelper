# Weekly schedule & homework

## Make a weekday plan

1. Open **Schedule**.
2. Choose a weekday tab: Monday through Friday each has an independent plan.
3. Enter that day's first lesson time in `HH:MM` format.
4. Add lessons with a title, duration, break, and optional `https://` meeting URL.
5. Press **Save schedule**. Valid changes are also saved when you switch weekdays, leave the Schedule screen, or close the app.

Lesson start times are calculated from the first class and the durations and breaks before each lesson. The meeting scheduler checks only that weekday's plan. For a class with a meeting URL, it prepares the browser one minute before class.

## Durable JSON storage

The app writes `schedule.json` atomically, so a partially written file does not replace a valid schedule:

- Windows: `%APPDATA%\StudentHelper\schedule.json`
- Other platforms: `~/.studenthelper/schedule.json`

The file contains all five weekday plans and your theme preferences. It is local to your user account; make a backup by copying this file while the app is closed.

On the first launch after this update, an existing SQLite schedule is copied to all five weekdays as a starting point. Edit each day as needed. The old database remains untouched.

## Plan homework in the weekly calendar

The **Diary** opens on a five-day calendar for next week. Use the arrows to move between weeks or **This week** to return to the current Monday–Friday. Each date is a column; saved homework appears as a small event card under its date. Select a day, then write a task and save it to that day. Select an event card to view its solution or ask Gemini to solve it.

!!! note "Calendar week"
    “Next week” means the next Monday through Friday, even if today is already a weekday. Homework dates and solutions are stored in the local SQLite diary. Tasks are one-time events and are not automatically repeated.
