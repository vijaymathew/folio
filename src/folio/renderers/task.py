from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Static

from folio.core.models import Directive
from folio.renderers.base import RenderContext, widget_id_fragment


def _bool_param(value: str | None) -> bool:
    return (value or "false").strip('"').lower() == "true"


class TaskWidget(Vertical):
    def __init__(self, directive: Directive, ctx: RenderContext) -> None:
        super().__init__(classes="task-widget")
        self.directive = directive
        self.ctx = ctx
        self.done = _bool_param(directive.params.get("done"))
        self.title_text = directive.body[0] if directive.body else directive.id or "untitled task"
        self.notes = directive.body[1:]
        self.button_id = f"toggle-{widget_id_fragment(directive.key())}"
        self.border_title = Text(directive.title())

    def compose(self) -> ComposeResult:
        status = "[x]" if self.done else "[ ]"
        due = self.directive.params.get("due", '"unscheduled"').strip('"')

        with Horizontal(classes="task-header"):
            yield Button(status, id=self.button_id, classes="task-checkbox", compact=True)
            yield Static(self.title_text, classes="task-title", markup=False)
            yield Static(f"due {due}", classes="task-due", markup=False)

        yield Static(self._meta_text(), classes="task-meta", markup=False)

        if self.notes:
            yield Static("\n".join(self.notes), classes="task-notes", markup=False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == self.button_id and self.ctx.events is not None:
            self.ctx.events.emit("task.toggle", directive=self.directive)
            event.stop()

    def _meta_text(self) -> str:
        items: list[str] = []

        priority = self.directive.params.get("priority")
        if priority:
            items.append(f"priority {priority.strip('\"')}")

        blocked_by = self.directive.params.get("blocked-by")
        if blocked_by:
            dep_id = blocked_by.strip('"')
            items.append(self._blocked_text(dep_id))

        completed = self.directive.params.get("completed")
        if completed:
            items.append(f"completed {completed.strip('\"')}")

        if not items:
            return "no additional metadata"
        return " | ".join(items)

    def _blocked_text(self, dep_id: str) -> str:
        target = (self.ctx.directives_by_id or {}).get(dep_id)
        if target is None:
            return f"blocked by {dep_id} (missing)"

        dep_done = _bool_param(target.params.get("done"))
        state = "done" if dep_done else "open"
        return f"blocked by {dep_id} ({state})"


class TaskRenderer:
    manifest_path = Path(__file__).with_name("manifests") / "task.toml"

    def render(self, directive: Directive, ctx: RenderContext) -> Static:
        return TaskWidget(directive, ctx)
