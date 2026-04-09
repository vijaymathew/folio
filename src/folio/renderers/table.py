from __future__ import annotations

from textual.widgets import Static

from folio.core.models import Directive
from folio.renderers.base import RenderContext


class TableRenderer:
    def render(self, directive: Directive, ctx: RenderContext) -> Static:
        summary = directive.params.get("source", '"inline"').strip('"')
        return Static(f"Table renderer placeholder\nsource={summary}", classes="table-widget")
