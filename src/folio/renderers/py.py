from __future__ import annotations

from textual.containers import Vertical
from textual.widgets import Button, Static

from folio.core.models import Directive
from folio.renderers.base import RenderContext


class PyRenderer:
    def render(self, directive: Directive, ctx: RenderContext) -> Static:
        code = "\n".join(directive.body) if directive.body else directive.header_line
        widget = Vertical(
            Static(code, classes="py-code"),
            Button("Run", disabled=True),
            Static("Python worker not yet wired in this scaffold.", classes="py-output"),
        )
        widget.border_title = directive.title()
        return widget
