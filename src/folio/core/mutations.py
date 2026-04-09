from __future__ import annotations

from .models import TextMutation
from .store import DocumentStore


class MutationEngine:
    def __init__(self, store: DocumentStore) -> None:
        self.store = store

    def apply(self, mutation: TextMutation) -> str:
        lines = self.store.get_text().splitlines()
        start = mutation.start_line
        end = mutation.end_line + 1
        replacement = mutation.new_text.splitlines()

        if mutation.kind == "append":
            start = end = mutation.start_line
        elif mutation.kind == "delete":
            replacement = []

        updated = lines[:start] + replacement + lines[end:]
        new_text = "\n".join(updated)
        if self.store.get_text().endswith("\n") or mutation.new_text.endswith("\n"):
            new_text += "\n"
        self.store.save(new_text)
        return new_text
