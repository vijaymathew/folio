from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

from textual.widget import Widget

from folio.core.models import Directive


@dataclass(slots=True)
class RenderContext:
    toggle_task: Callable[[Directive], None] | None = None


class Renderer(Protocol):
    def render(self, directive: Directive, ctx: RenderContext) -> Widget: ...
