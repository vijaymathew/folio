from __future__ import annotations

from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Static

from folio.core.models import Directive
from folio.renderers.base import RenderContext


class TaskWidget(Vertical):
    def __init__(self, directive: Directive, ctx: RenderContext, title: str, due: str, status: str) -> None:
        super().__init__()
        self.directive = directive
        self.ctx = ctx
        self.title = title
        self.due = due
        self.status = status
        self.button_id = f"toggle-{directive.id or directive.start_line}"
        self.border_title = directive.title()

    def compose(self):
        yield Horizontal(
            Static(f"{self.status} {self.title}", classes="task-title"),
            Static(f"due {self.due}", classes="task-due"),
            Button("Toggle", id=self.button_id, classes="task-toggle"),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == self.button_id and self.ctx.toggle_task is not None:
            self.ctx.toggle_task(self.directive)
            event.stop()


class TaskRenderer:
    def render(self, directive: Directive, ctx: RenderContext) -> Static:
        done = directive.params.get("done", "false").strip('"').lower() == "true"
        title = directive.body[0] if directive.body else directive.id or "untitled task"
        due = directive.params.get("due", '"unscheduled"').strip('"')
        status = "[x]" if done else "[ ]"
        return TaskWidget(directive, ctx, title, due, status)
