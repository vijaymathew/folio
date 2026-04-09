from __future__ import annotations

from textual.widgets import Static

from folio.core.models import Directive
from folio.renderers.base import RenderContext


class NoteRenderer:
    def render(self, directive: Directive, ctx: RenderContext) -> Static:
        section = directive.params.get("section", '"full"').strip('"')
        return Static(f"Transclusion placeholder\nsection={section}", classes="note-widget")
