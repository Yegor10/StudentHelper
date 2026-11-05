"""Local .env configuration for language and Gemini credentials."""

import os
from pathlib import Path

from dotenv import load_dotenv, set_key


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / ".env"


class ConfigManager:
    def __init__(self, env_path: Path = ENV_PATH) -> None:
        self.env_path = env_path
        load_dotenv(self.env_path, override=False)

    @property
    def gemini_api_key(self) -> str:
        return os.getenv("GEMINI_API_KEY", "").strip()

    @property
    def gemini_model(self) -> str:
        return os.getenv("GEMINI_MODEL", "gemini-1.5-flash").strip()

    @property
    def language(self) -> str:
        value = os.getenv("APP_LANGUAGE", "en").strip().lower()
        return value if value in {"en", "uk"} else "en"

    def save(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        language: str | None = None,
    ) -> None:
        self.env_path.parent.mkdir(parents=True, exist_ok=True)
        updates: dict[str, str] = {}
        if api_key is not None:
            updates["GEMINI_API_KEY"] = api_key.strip()
        if model is not None:
            if not model.strip():
                raise ValueError("The Gemini model name cannot be empty.")
            updates["GEMINI_MODEL"] = model.strip()
        if language is not None:
            normalized_language = language.strip().lower()
            if normalized_language not in {"en", "uk"}:
                raise ValueError("Language must be 'en' or 'uk'.")
            updates["APP_LANGUAGE"] = normalized_language

        for key, value in updates.items():
            set_key(
                str(self.env_path),
                key,
                value,
                quote_mode="always",
                encoding="utf-8",
            )
            os.environ[key] = value
