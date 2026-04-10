from __future__ import annotations

from pathlib import Path


class DocumentConflictError(RuntimeError):
    """Raised when the document changed on disk since the last Folio load/save."""


class DocumentStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._text = ""
        self._baseline_text = ""

    def load(self) -> str:
        self._text = self.path.read_text(encoding="utf-8") if self.path.exists() else ""
        self._baseline_text = self._text
        return self._text

    def get_text(self) -> str:
        return self._text

    def save(self, text: str) -> None:
        self._ensure_not_modified_externally()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(text, encoding="utf-8")
        self._text = text
        self._baseline_text = text

    def replace_lines(self, start_line: int, end_line: int, new_text: str) -> str:
        lines = self._text.splitlines()
        replacement = new_text.splitlines()
        updated = lines[:start_line] + replacement + lines[end_line + 1 :]
        text = "\n".join(updated)
        if self._text.endswith("\n") or new_text.endswith("\n"):
            text += "\n"
        self.save(text)
        return text

    def append_lines(self, start_line: int, new_text: str) -> str:
        return self.replace_lines(start_line, start_line - 1, new_text)

    def delete_lines(self, start_line: int, end_line: int) -> str:
        return self.replace_lines(start_line, end_line, "")

    def has_external_change(self) -> bool:
        return self._read_disk_text() != self._baseline_text

    def _ensure_not_modified_externally(self) -> None:
        if self.has_external_change():
            raise DocumentConflictError(
                f"Document changed on disk since load: {self.path}. Reload before saving."
            )

    def _read_disk_text(self) -> str:
        return self.path.read_text(encoding="utf-8") if self.path.exists() else ""
