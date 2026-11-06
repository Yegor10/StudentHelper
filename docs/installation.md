# Installation

The Windows desktop app now includes the same Google Classroom workflow as the Chrome extension, along with its local schedule, homework diary, Gemini help, and appearance settings.

## Install on Windows

Run the **Build Windows installer** workflow on GitHub and download its `StudentHelper-Windows-Setup` artifact. Run `StudentHelper-Setup-0.2.0.exe` from the artifact to install StudentHelper for your Windows account and create a Start menu shortcut. Python does not need to be installed separately.

## Connect Google Classroom

The desktop app requires a separate OAuth client of type **Desktop app**; the Chrome Extension Client ID cannot be reused.

1. Open the [Google Cloud API Library](https://console.cloud.google.com/apis/library) in the project used for Classroom.
2. Enable the [Google Classroom API](https://console.cloud.google.com/apis/library/classroom.googleapis.com) and [Google Drive API](https://console.cloud.google.com/apis/library/drive.googleapis.com).
3. Configure the [OAuth consent screen](https://console.cloud.google.com/auth/audience). If the app is in testing mode, add your Google account under **Test users**.
4. On the [OAuth Clients page](https://console.cloud.google.com/auth/clients), create or select the **Desktop app** client with ID `411370766360-fnhev2h5tti5q1p10t03n739vf1634hh.apps.googleusercontent.com`, then download its JSON file.
5. In StudentHelper, open **Settings**, choose the downloaded OAuth JSON, and save settings.
6. Open **Google Classroom** in the sidebar and select **Connect Google**. Complete Google's sign-in and consent in the browser window.

The OAuth Desktop app JSON is used only to start Google's local sign-in flow. The installed-app client ID and secret are public application identifiers, not user passwords; the user's refresh token is stored separately in the user's profile. Google may restrict unverified projects or require a school administrator to allow the requested Classroom and Drive scopes.

The app stores its OAuth refresh token in your Windows user profile under `%APPDATA%\StudentHelper\classroom-token.json`. It is not included in the installer or project.

## Run from source

## Requirements

- Python 3.10 or later
- A desktop environment supported by Tkinter
- A Gemini API key to use AI homework solutions

## Install

From the project directory, create and activate a virtual environment:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

Copy `.env.example` to `.env`. Add a Gemini key to use the diary or Classroom AI features; the rest of the app works without it.

Run the app:

```powershell
studenthelper
```

Alternatively, run `python -m studenthelper` from the project with `src` on `PYTHONPATH`.

## Build the Windows installer

Install the project's build dependencies and [Inno Setup 6](https://jrsoftware.org/isinfo.php), activate the project's virtual environment, then run:

```powershell
pip install -e ".[build]"
.\scripts\build_windows.ps1
```

The installer is written to `dist\installer`. On GitHub, manually run the **Build Windows installer** workflow, or push a `v*` tag, and download the resulting `StudentHelper-Windows-Setup` artifact.

## Run tests

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

## Build this documentation

```powershell
mkdocs serve
```

Use `mkdocs build` to generate the static site in `site/`.
