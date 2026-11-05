# How meeting automation works

The schedule service runs on a background thread so meeting waits do not freeze the desktop UI. It checks the saved daily schedule and starts browser automation one minute before a class that has a meeting URL.

StudentHelper launches a visible Chromium browser with Playwright and keeps a local browser profile at `~/.studenthelper/browser-profile`. Sign in to your meeting provider in that profile ahead of time if your meetings require an account. When available, the app attempts to turn off microphone and camera controls before selecting a recognizable join action.

## Important limitations

- Meeting providers can change their pages, labels, and pre-join flows. Automation reports a failure if it cannot complete a step; check the opened browser before relying on a meeting being joined.
- The app does not grant camera or microphone permissions, enter credentials, bypass waiting rooms, or solve CAPTCHAs.
- Keep the StudentHelper app running for scheduled automation. Closing it closes the browser and stops the scheduler.
- Meeting URLs are opened only when entered in your local schedule.

The browser profile can retain login cookies. Protect your operating-system account and do not share that profile folder.
