from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, Footer, Header, Static

from folio.core.events import EventBus
from folio.core.models import Directive, DocumentModel, TextMutation
from folio.core.mutations import MutationEngine
from folio.core.parser import DirectiveParser
from folio.core.registry import CapabilityRegistry
from folio.core.store import DocumentStore
from folio.renderers.base import RenderContext
from folio.renderers.file import FileRenderer
from folio.renderers.note import NoteRenderer
from folio.renderers.py import PyRenderer
from folio.renderers.table import TableRenderer
from folio.renderers.task import TaskRenderer


class FolioApp(App[None]):
    CSS = """
    Screen {
      layout: vertical;
    }
    #body {
      height: 1fr;
    }
    #source-pane, #render-pane {
      width: 1fr;
      border: round $surface;
      padding: 1 2;
      overflow: auto;
    }
    .pane-title {
      text-style: bold;
      margin-bottom: 1;
    }
    .task-title {
      width: 1fr;
    }
    .task-due {
      color: $text-muted;
      width: 16;
    }
    Button {
      min-width: 10;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "reload_document", "Reload"),
    ]

    def __init__(self, document_path: Path) -> None:
        super().__init__()
        self.document_path = document_path
        self.store = DocumentStore(document_path)
        self.parser = DirectiveParser()
        self.mutations = MutationEngine(self.store)
        self.events = EventBus()
        self.registry = CapabilityRegistry()
        self.model = DocumentModel(text="")
        self._register_renderers()

    def _register_renderers(self) -> None:
        self.registry.register("task", TaskRenderer)
        self.registry.register("py", PyRenderer)
        self.registry.register("table", TableRenderer)
        self.registry.register("note", NoteRenderer)
        self.registry.register("file", FileRenderer)

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="body"):
            yield VerticalScroll(id="source-pane")
            yield VerticalScroll(id="render-pane")
        yield Footer()

    def on_mount(self) -> None:
        self.reload_document()

    def action_reload_document(self) -> None:
        self.reload_document()

    def reload_document(self) -> None:
        text = self.store.load()
        model = self.parser.parse(text)
        self.model = model

        source = self.query_one("#source-pane", VerticalScroll)
        source.remove_children()
        source.mount(Static("Source", classes="pane-title"))
        source.mount(Static(text or "(empty document)"))

        render = self.query_one("#render-pane", VerticalScroll)
        render.remove_children()
        render.mount(Static("Rendered", classes="pane-title"))

        ctx = RenderContext(toggle_task=self.toggle_task)
        prose_index = 0
        directives = iter(model.directives)
        current = next(directives, None)

        for line_no, line in enumerate(text.splitlines() or [""]):
            while prose_index < len(model.prose) and model.prose[prose_index].start_line == line_no:
                block = model.prose[prose_index]
                if any(part.strip() for part in block.lines):
                    render.mount(Static("\n".join(block.lines)))
                prose_index += 1
            while current and current.start_line == line_no:
                renderer = self.registry.create(current.type)
                widget = renderer.render(current, ctx) if renderer else Static(current.header_line)
                render.mount(widget)
                current = next(directives, None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if not button_id.startswith("toggle-"):
            return

        target = button_id.removeprefix("toggle-")
        directive = next(
            (
                item
                for item in self.model.directives
                if item.type == "task"
                and str(item.id or item.start_line) == target
            ),
            None,
        )
        if directive is not None:
            self.toggle_task(directive)

    def toggle_task(self, directive: Directive) -> None:
        done = directive.params.get("done", '"false"').strip('"').lower() == "true"
        directive.params["done"] = '"false"' if done else '"true"'
        if done:
            directive.params.pop("completed", None)
        else:
            directive.params["completed"] = '"now"'

        header = directive.header_text()
        mutation = TextMutation(
            kind="replace",
            start_line=directive.start_line,
            end_line=directive.start_line,
            new_text=header,
            source="task.toggle",
        )
        self.mutations.apply(mutation)
        self.reload_document()
