from __future__ import annotations

from textual.widgets import Static

from folio.core.models import Directive
from folio.renderers.base import RenderContext


class FileRenderer:
    def render(self, directive: Directive, ctx: RenderContext) -> Static:
        path = directive.id or directive.params.get("path", '"unknown"').strip('"')
        return Static(f"File renderer placeholder\n{path}", classes="file-widget")
