# Installation

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
python -m playwright install chromium
```

Copy `.env.example` to `.env`. Add a Gemini key to use the diary's AI feature; the rest of the app works without it.

Run the app:

```powershell
studenthelper
```

Alternatively, run `python -m studenthelper` from the project with `src` on `PYTHONPATH`.

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
