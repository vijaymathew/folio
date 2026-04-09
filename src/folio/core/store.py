from __future__ import annotations

from pathlib import Path


class DocumentStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._text = ""

    def load(self) -> str:
        self._text = self.path.read_text(encoding="utf-8") if self.path.exists() else ""
        return self._text

    def get_text(self) -> str:
        return self._text

    def save(self, text: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(text, encoding="utf-8")
        self._text = text
