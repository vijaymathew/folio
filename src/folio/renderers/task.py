from __future__ import annotations

from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Static

from folio.core.models import Directive
from folio.renderers.base import RenderContext


class TaskRenderer:
    def render(self, directive: Directive, ctx: RenderContext) -> Static:
        done = directive.params.get("done", "false").strip('"').lower() == "true"
        title = directive.body[0] if directive.body else directive.id or "untitled task"
        due = directive.params.get("due", '"unscheduled"').strip('"')
        status = "[x]" if done else "[ ]"

        row = Horizontal(
            Static(f"{status} {title}", classes="task-title"),
            Static(f"due {due}", classes="task-due"),
            Button("Toggle", id=f"toggle-{directive.id or directive.start_line}", classes="task-toggle"),
        )
        row.border_title = directive.title()
        return Vertical(row)
