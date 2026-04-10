from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from textual.widget import Widget

from folio.core.events import EventBus
from folio.core.models import Directive, PyBlockResult


@dataclass(slots=True)
class RenderContext:
    events: EventBus | None = None
    py_results: dict[str, PyBlockResult] | None = None
    document_path: Path | None = None
    directives_by_id: dict[str, Directive] | None = None


class Renderer(Protocol):
    def render(self, directive: Directive, ctx: RenderContext) -> Widget: ...
