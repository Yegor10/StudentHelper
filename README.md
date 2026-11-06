# StudentHelper

StudentHelper is a student study planner with two interfaces:

- **Chrome extension** — the current browser workflow: a five-day timetable, Google Classroom assignment list, optional Gemini explanations, and manually confirmed file submission.
- **Python desktop app** — a bilingual, installable CustomTkinter application with a weekly timetable, homework diary, Classroom assignment list, Gemini help, and scheduled meeting links opened in your regular browser.

## Get started with Chrome

1. Open `chrome://extensions` in Google Chrome and enable **Developer mode**.
2. Select **Load unpacked** and choose [`extension/chrome`](extension/chrome).
3. Configure a Google Cloud OAuth client of type **Chrome Extension** using the extension ID shown by Chrome. Add your Google account as an OAuth test user if the consent screen is in testing mode.
4. Put the generated public OAuth Client ID in `oauth2.client_id` in [`extension/chrome/manifest.json`](extension/chrome/manifest.json). Do not add a client secret or service-account key.
5. Enable the Google Classroom API and Google Drive API in the same Google Cloud project, reload the extension, then connect Google from StudentHelper.

The extension opens scheduled meeting links but does not join calls or change microphone/camera settings. Classroom file attachment and turning in work are separate actions; turning in requires your confirmation.

See the [complete Chrome extension setup and usage guide](docs/chrome-extension.md) for OAuth details, permissions, troubleshooting, and privacy notes.

## Install or run the desktop app

On Windows, install the app with `StudentHelper-Setup-0.2.0.exe` from the GitHub Actions **StudentHelper-Windows-Setup** artifact. Python is not required on the computer running the installer.

To connect Classroom in the desktop app, create and select a Google OAuth client JSON of type **Desktop app**. The Chrome extension's OAuth client cannot be reused. See [desktop installation and OAuth setup](docs/installation.md).

To run from source:

The desktop app requires Python 3.10 or later:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
studenthelper
```

For AI features, copy `.env.example` to `.env` and configure your Gemini API key. See the [desktop installation guide](docs/installation.md).

## Documentation

The full documentation site is built with MkDocs Material:

```powershell
pip install -r requirements.txt
mkdocs serve
```

Open the local address printed by MkDocs. To build the static site, run `mkdocs build`.

- [Feature overview](docs/features.md)
- [Weekly schedule and homework diary](docs/schedule.md)
- [Gemini API configuration](docs/gemini.md)
- [Desktop meeting links](docs/playwright.md)
- [Chrome extension guide](docs/chrome-extension.md)
- [Desktop installation and Classroom setup](docs/installation.md)

## Development checks

Run the test suite from the repository root:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

## Credential safety

Never commit `.env` files, OAuth client secrets, service-account JSON files, private keys, or API keys. The extension's Gemini key is saved in Chrome local extension storage; use a dedicated key and revoke it if exposed.
