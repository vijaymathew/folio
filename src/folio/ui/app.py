from __future__ import annotations

import json
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Footer, Header, Static, TextArea

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
    #source-editor {
      height: 1fr;
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
    .py-run {
      width: 12;
      margin-bottom: 1;
    }
    .py-block {
      height: auto;
      border: round $surface-lighten-1;
      padding: 1;
      margin-bottom: 1;
    }
    .py-code, .py-output {
      height: auto;
    }
    .table-editor {
      height: auto;
      border: round $surface-lighten-1;
      padding: 1;
      margin-bottom: 1;
    }
    .table-editor-controls {
      height: auto;
      margin-top: 1;
    }
    .table-editor-input-row {
      height: auto;
      margin-top: 1;
    }
    #table-edit-status {
      height: auto;
      margin-top: 1;
    }
    #table-edit-input {
      width: 1fr;
    }
    #table-apply {
      width: 10;
      margin-left: 1;
    }
    Button {
      min-width: 10;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "reload_document", "Reload"),
        ("ctrl+s", "save_source", "Save"),
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
        self._loading_source = False
        self._source_dirty = False
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
            with Vertical(id="source-pane"):
                yield Static("Source", id="source-title", classes="pane-title")
                yield TextArea(
                    "",
                    id="source-editor",
                    language="markdown",
                    soft_wrap=False,
                    show_line_numbers=True,
                )
            yield VerticalScroll(id="render-pane")
        yield VerticalScroll(id="status-pane")
        yield Footer()

    def on_mount(self) -> None:
        self._reset_status_pane()
        self.reload_document()

    def action_reload_document(self) -> None:
        self.reload_document()

    def action_save_source(self) -> None:
        editor = self.query_one("#source-editor", TextArea)
        self.store.save(editor.text)
        self._source_dirty = False
        self._set_source_title()
        self.log_status(f"Saved source document to {self.document_path}.")
        self.reload_document()

    def reload_document(self) -> None:
        text = self.store.load()
        model = self.parser.parse(text)
        self.model = model
        self.py_results = self._run_autorun_blocks()

        editor = self.query_one("#source-editor", TextArea)
        self._loading_source = True
        editor.load_text(text)
        self._loading_source = False
        self._source_dirty = False
        self._set_source_title()

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

        render.refresh(repaint=True, layout=True)
        self._log_autorun_results()

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        if event.text_area.id != "source-editor" or self._loading_source:
            return
        if not self._source_dirty:
            self._source_dirty = True
            self._set_source_title()
            self.log_status("Source buffer modified. Press Ctrl+S to save and reparse.")

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
        key = directive.id or str(directive.start_line)
        results = self.py_worker.run_document(
            self._py_directives(),
            trigger_key=key,
        )
        self.py_results = results
        result = results.get(key)
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

        render.refresh(repaint=True, layout=True)

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
        self._replace_table_directive(directive, rows, params=params, source="table.edit")
        self.log_status(f"{directive.title()} updated from widget edit; source rows materialized into document.")
        self.reload_document()

    def _replace_table_directive(
        self,
        directive: Directive,
        rows: list[dict[str, object]],
        *,
        params: dict[str, str],
        source: str,
    ) -> None:
        header = self._directive_header(directive.type, directive.id, params)
        body = [json.dumps(row, ensure_ascii=True) for row in rows]
        new_text = "\n".join([header, *body, "::end"])
        mutation = TextMutation(
            kind="replace",
            start_line=directive.start_line,
            end_line=directive.end_line,
            new_text=new_text,
            source=source,
        )
        self.mutations.apply(mutation)

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

    def _set_source_title(self) -> None:
        title = self.query_one("#source-title", Static)
        title.update("Source *" if self._source_dirty else "Source")

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
