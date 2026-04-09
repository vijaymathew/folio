from __future__ import annotations


class PyWorker:
    """Placeholder for a future subprocess-backed ::py runtime."""

    def run_document(self, blocks: list[str]) -> dict[str, object]:
        return {
            "status": "not_implemented",
            "stdout": [],
            "context": {},
            "blocks": blocks,
        }
