from __future__ import annotations

import json
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
from folio.python.worker import PyWorker
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
    #status-pane {
      height: 10;
      border: round $surface;
      padding: 1 2;
      overflow: auto;
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
    .status-line {
      color: $text-muted;
    }
    .status-line.error {
      color: $error;
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
        self.py_worker = PyWorker()
        self.py_results = {}
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
        yield VerticalScroll(id="status-pane")
        yield Footer()

    def on_mount(self) -> None:
        self._reset_status_pane()
        self.reload_document()

    def action_reload_document(self) -> None:
        self.reload_document()

    def reload_document(self) -> None:
        text = self.store.load()
        model = self.parser.parse(text)
        self.model = model
        self.py_results = self._run_autorun_blocks()

        source = self.query_one("#source-pane", VerticalScroll)
        source.remove_children()
        source.mount(Static("Source", classes="pane-title"))
        source.mount(Static(text or "(empty document)"))

        render = self.query_one("#render-pane", VerticalScroll)
        render.remove_children()
        render.mount(Static("Rendered", classes="pane-title"))

        ctx = RenderContext(
            toggle_task=self.toggle_task,
            run_py=self.run_py_block,
            update_table=self.update_table_directive,
            py_results=self.py_results,
        )
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

        self._log_autorun_results()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id.startswith("toggle-"):
            target = button_id.removeprefix("toggle-")
            directive = self._find_directive("task", target)
            if directive is not None:
                self.toggle_task(directive)
            return

        if button_id.startswith("run-py-"):
            target = button_id.removeprefix("run-py-")
            directive = self._find_directive("py", target)
            if directive is not None:
                self.run_py_block(directive)

    def _find_directive(self, directive_type: str, target: str) -> Directive | None:
        return next(
            (
                item
                for item in self.model.directives
                if item.type == directive_type
                and str(item.id or item.start_line) == target
            ),
            None,
        )

    def _py_directives(self) -> list[Directive]:
        return [item for item in self.model.directives if item.type == "py"]

    def _run_autorun_blocks(self) -> dict[str, object]:
        directives = self._py_directives()
        if not directives:
            return {}
        return self.py_worker.run_document(directives, autorun_only=True)

    def run_py_block(self, directive: Directive) -> None:
        self.log_status(f"Running {directive.title()} in subprocess worker.")
        results = self.py_worker.run_document(
            self._py_directives(),
            trigger_key=directive.id or str(directive.start_line),
        )
        self.py_results = results
        result = results.get(directive.id or str(directive.start_line))
        if result is not None:
            if result.status == "ok":
                summary = f"stdout lines={len(result.stdout)}"
                if result.table is not None:
                    summary += f", table rows={len(result.table)}"
                self.log_status(f"{directive.title()} completed successfully ({summary}).")
            else:
                self.log_status(f"{directive.title()} failed: {result.error}", error=True)
        self.reload_render_pane()

    def reload_render_pane(self) -> None:
        text = self.store.get_text()
        model = self.model

        render = self.query_one("#render-pane", VerticalScroll)
        render.remove_children()
        render.mount(Static("Rendered", classes="pane-title"))

        ctx = RenderContext(
            toggle_task=self.toggle_task,
            run_py=self.run_py_block,
            update_table=self.update_table_directive,
            py_results=self.py_results,
        )
        prose_index = 0
        directives = iter(model.directives)
        current = next(directives, None)

        for line_no, _line in enumerate(text.splitlines() or [""]):
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
        self.log_status(f"{directive.title()} toggled -> done={directive.params['done']}.")
        self.reload_document()

    def update_table_directive(self, directive: Directive, rows: list[dict[str, object]]) -> None:
        params = dict(directive.params)
        params.pop("source", None)
        params["editable"] = '"true"'
        header = self._directive_header(directive.type, directive.id, params)
        body = [json.dumps(row, ensure_ascii=True) for row in rows]
        new_text = "\n".join([header, *body, "::end"])
        mutation = TextMutation(
            kind="replace",
            start_line=directive.start_line,
            end_line=directive.end_line,
            new_text=new_text,
            source="table.edit",
        )
        self.mutations.apply(mutation)
        self.log_status(f"{directive.title()} updated from widget edit; source rows materialized into document.")
        self.reload_document()

    def _directive_header(self, directive_type: str, directive_id: str | None, params: dict[str, str]) -> str:
        ident = f"[{directive_id}]" if directive_id else ""
        if not params:
            return f"::{directive_type}{ident}"
        items = " ".join(f"{key}={value}" for key, value in params.items())
        return f"::{directive_type}{ident}{{{items}}}"

    def _reset_status_pane(self) -> None:
        pane = self.query_one("#status-pane", VerticalScroll)
        pane.remove_children()
        pane.mount(Static("Status", classes="pane-title"))

    def log_status(self, message: str, *, error: bool = False) -> None:
        pane = self.query_one("#status-pane", VerticalScroll)
        classes = "status-line error" if error else "status-line"
        pane.mount(Static(message, classes=classes))

    def _log_autorun_results(self) -> None:
        for key, result in self.py_results.items():
            if result.status == "ok":
                self.log_status(f"Autorun ::py[{key}] completed.")
            elif result.status == "error":
                self.log_status(f"Autorun ::py[{key}] failed: {result.error}", error=True)
