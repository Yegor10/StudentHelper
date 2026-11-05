"""Gemini homework solution generation."""

from pathlib import Path

from PIL import Image

from studenthelper.config import ConfigManager
from studenthelper.i18n import translate


class GeminiDiaryService:
    def __init__(self, config: ConfigManager) -> None:
        self.config = config

    def solve(self, task_text: str, image_path: str | None = None) -> str:
        api_key = self.config.gemini_api_key
        if not api_key:
            raise ValueError(translate(self.config.language, "missing_gemini_key"))
        if not task_text.strip() and not image_path:
            raise ValueError(translate(self.config.language, "empty_homework"))

        import google.generativeai as genai

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(self.config.gemini_model)
        prompt = (
            "Help the student learn. Solve the homework accurately and explain "
            "the reasoning step by step. Clearly state assumptions, and do not "
            "invent unreadable details from an image.\n\n"
            f"Homework text:\n{task_text.strip() or '(no text provided)'}"
        )
        contents: list[object] = [prompt]
        if image_path:
            path = Path(image_path)
            if not path.is_file():
                raise FileNotFoundError(f"Image attachment not found: {path.name}")
            with Image.open(path) as source_image:
                source_image.load()
                contents.append(source_image.copy())

        response = model.generate_content(contents)
        answer = response.text
        if not answer:
            raise RuntimeError("Gemini returned an empty solution.")
        return answer.strip()
