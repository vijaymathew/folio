from __future__ import annotations

from .models import TextMutation
from .store import DocumentStore


class MutationEngine:
    def __init__(self, store: DocumentStore) -> None:
        self.store = store

    def apply(self, mutation: TextMutation) -> str:
        if mutation.kind == "append":
            return self.store.append_lines(mutation.start_line, mutation.new_text)
        if mutation.kind == "delete":
            return self.store.delete_lines(mutation.start_line, mutation.end_line)
        return self.store.replace_lines(mutation.start_line, mutation.end_line, mutation.new_text)
