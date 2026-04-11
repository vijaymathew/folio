from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Footer, Header, Input, Static, TextArea

from folio.core.events import EventBus
from folio.core.contact_reader import ContactCard, ContactReader, ContactReaderError
from folio.core.email_store import EmailDraft, EmailStoreError, MaildirEmailStore
from folio.core.models import Directive, DocumentModel, TextMutation
from folio.core.mutations import MutationEngine
from folio.core.parser import DirectiveParser
from folio.core.registry import CapabilityRegistry
from folio.core.sh_runner import ShRunner
from folio.core.store import DocumentConflictError, DocumentStore
from folio.core.web_reader import WebReader, resolve_web_url
from folio.python.worker import PyWorker
from folio.renderers.base import AdvisoryAction, AdvisorySpec, RenderContext, widget_id_fragment
from folio.renderers.contact import ContactRenderer
from folio.renderers.email import EmailRenderer
from folio.renderers.file import FileRenderer
from folio.renderers.note import NoteRenderer
from folio.renderers.py import PyRenderer
from folio.renderers.sh import ShOutputRenderer, ShRenderer
from folio.renderers.table import TableRenderer
from folio.renderers.task import TaskRenderer
from folio.renderers.web import WebRenderer
from folio.ui.document_view import DocumentView


class FolioApp(App[None]):
    LAYOUT_BINDING_ID = "toggle-layout-mode"

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
    .task-widget {
      height: auto;
      border: round $surface-lighten-1;
      padding: 1;
      margin-bottom: 1;
    }
    .task-header {
      height: auto;
    }
    .task-checkbox {
      width: 5;
      min-width: 5;
      margin-right: 1;
    }
    .task-due {
      color: $text-muted;
      width: 16;
    }
    .task-meta {
      color: $text-muted;
      height: auto;
      margin-top: 1;
    }
    .task-notes {
      height: auto;
      margin-top: 1;
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
    #table-edit-status {
      height: auto;
      margin-top: 1;
      color: $text-muted;
    }
    .file-widget {
      height: auto;
      border: round $surface-lighten-1;
      padding: 1;
      margin-bottom: 1;
    }
    .file-meta {
      color: $text-muted;
      height: auto;
      margin-bottom: 1;
    }
    .file-content {
      height: auto;
    }
    .contact-widget {
      height: auto;
      border: round $surface-lighten-1;
      padding: 1;
      margin-bottom: 1;
    }
    .contact-meta, .contact-more {
      color: $text-muted;
      height: auto;
      margin-bottom: 1;
    }
    .contact-card, .contact-empty, .contact-status {
      height: auto;
      margin-bottom: 1;
    }
    .contact-form, .contact-field, .contact-actions {
      height: auto;
    }
    .contact-field {
      margin-bottom: 1;
    }
    .contact-input {
      width: 1fr;
    }
    .contact-save {
      width: 12;
    }
    .email-widget {
      height: auto;
      border: round $surface-lighten-1;
      padding: 1;
      margin-bottom: 1;
    }
    .email-meta, .email-selected-meta {
      color: $text-muted;
      height: auto;
      margin-bottom: 1;
    }
    .email-list, .email-actions {
      height: auto;
      margin-bottom: 1;
    }
    .email-open {
      width: 1fr;
      margin-bottom: 1;
    }
    .email-action {
      width: 14;
      margin-right: 1;
    }
    .email-body, .email-empty {
      height: auto;
    }
    .email-compose-widget {
      height: auto;
      border: round $surface-lighten-1;
      padding: 1;
      margin-bottom: 1;
    }
    .email-compose-meta, .email-compose-form, .email-compose-actions {
      height: auto;
      margin-bottom: 1;
    }
    .email-compose-meta {
      color: $text-muted;
    }
    .email-compose-input {
      width: 1fr;
      margin-bottom: 1;
    }
    .email-compose-body {
      height: 10;
      margin-bottom: 1;
    }
    .email-compose-save {
      width: 14;
    }
    .note-widget {
      height: auto;
      border: round $surface-lighten-1;
      padding: 1;
      margin-bottom: 1;
    }
    .note-meta, .note-status {
      color: $text-muted;
      height: auto;
      margin-bottom: 1;
    }
    .note-content {
      height: auto;
    }
    .sh-widget, .sh-output-widget {
      height: auto;
      border: round $surface-lighten-1;
      padding: 1;
      margin-bottom: 1;
    }
    .sh-toolbar, .sh-output-meta {
      height: auto;
      margin-bottom: 1;
    }
    .sh-meta, .sh-output-summary {
      width: 1fr;
      color: $text-muted;
    }
    .sh-run, .sh-output-exit {
      width: 18;
    }
    .sh-command, .sh-stdout, .sh-stderr {
      height: auto;
    }
    .sh-stderr {
      border: round $error;
      padding: 1;
      margin-top: 1;
    }
    .web-widget {
      height: auto;
      border: round $surface-lighten-1;
      padding: 1;
      margin-bottom: 1;
    }
    .web-toolbar {
      height: auto;
      margin-bottom: 1;
    }
    .web-meta {
      width: 1fr;
      color: $text-muted;
    }
    .web-reload {
      width: 12;
    }
    .web-content {
      height: auto;
    }
    .directive-container {
      height: auto;
      margin-bottom: 1;
      padding: 0 1;
      border: round transparent;
    }
    .directive-toolbar {
      height: auto;
      margin-bottom: 1;
    }
    .directive-title {
      width: 1fr;
      color: $text-muted;
    }
    .directive-container:focus, .directive-container:focus-within {
      border: round $primary;
      background: $boost;
    }
    .directive-container:focus .directive-title, .directive-container:focus-within .directive-title {
      color: $primary-lighten-2;
      text-style: bold;
    }
    .directive-toggle {
      width: 12;
    }
    .directive-source {
      height: auto;
      border: round $surface-lighten-1;
      padding: 1;
    }
    .directive-source-input {
      width: 1fr;
      margin-bottom: 1;
    }
    .advisory-widget {
      height: auto;
      border: round $surface-lighten-1;
      padding: 1;
      margin-bottom: 1;
    }
    .advisory-warning {
      border: round $warning;
    }
    .advisory-error {
      border: round $error;
    }
    .advisory-title {
      text-style: bold;
      height: auto;
      margin-bottom: 1;
    }
    .advisory-message {
      height: auto;
    }
    .advisory-actions {
      height: auto;
      margin-top: 1;
    }
    Button {
      min-width: 10;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "reload_document", "Reload"),
        Binding("ctrl+s", "save_source", "Save"),
        Binding("f6", "toggle_single_pane", "Split Pane", id=LAYOUT_BINDING_ID),
    ]

    def __init__(self, document_path: Path, *, trusted_document: bool = True) -> None:
        super().__init__()
        self.document_path = document_path
        self._trusted_document = trusted_document
        self.store = DocumentStore(document_path)
        self.parser = DirectiveParser()
        self.mutations = MutationEngine(self.store)
        self.events = EventBus()
        self.registry = CapabilityRegistry()
        self.model = DocumentModel(text="")
        self.py_worker = PyWorker()
        self.sh_runner = ShRunner()
        self.web_reader = WebReader()
        self.contact_reader = ContactReader()
        self.py_results = {}
        self.web_results = {}
        self.email_selection: dict[str, str] = {}
        self._loading_source = False
        self._source_dirty = False
        self._single_pane_mode = True
        self._source_view_keys: set[str] = set()
        self._directive_edit_buffers: dict[str, str] = {}
        self._dismissed_advisories: set[str] = set()
        self._active_conflict_message: str | None = None
        self._pending_shell_confirmations: set[str] = set()
        self._subscribe_events()
        self._register_renderers()

    def _register_renderers(self) -> None:
        self.registry.register(TaskRenderer)
        self.registry.register(PyRenderer)
        self.registry.register(ShRenderer)
        self.registry.register(ShOutputRenderer)
        self.registry.register(TableRenderer)
        self.registry.register(NoteRenderer)
        self.registry.register(FileRenderer)
        self.registry.register(ContactRenderer)
        self.registry.register(EmailRenderer)
        self.registry.register(WebRenderer)

    def _subscribe_events(self) -> None:
        self.events.subscribe("task.toggle", self.toggle_task)
        self.events.subscribe("py.run", self.run_py_block)
        self.events.subscribe("sh.run", self.run_sh_block)
        self.events.subscribe("table.edit", self.update_table_directive)
        self.events.subscribe("contact.save", self.save_contact)
        self.events.subscribe("email.select", self.select_email_message)
        self.events.subscribe("email.action", self.perform_email_action)
        self.events.subscribe("email.compose_save", self.save_email_compose)
        self.events.subscribe("directive.edit_open", self.open_directive_editor)
        self.events.subscribe("directive.edit_buffer", self.update_directive_edit_buffer)
        self.events.subscribe("directive.edit_save", self.save_directive_editor)
        self.events.subscribe("directive.edit_cancel", self.cancel_directive_editor)
        self.events.subscribe("web.reload", self.reload_web_directive)
        self.events.subscribe("ui.toggle_single_pane", self.toggle_single_pane)
        self.events.subscribe("advisory.dismiss", self.dismiss_advisory)
        self.events.subscribe("document.reload", self.handle_reload_request)

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
            yield DocumentView(id="render-pane")
        yield VerticalScroll(id="status-pane")
        yield Footer()

    def on_mount(self) -> None:
        self._reset_status_pane()
        self._refresh_layout_binding()
        self.reload_document()
        self.refresh_bindings()

    def action_reload_document(self) -> None:
        self.reload_document()

    def action_save_source(self) -> None:
        focused = self.focused
        if isinstance(focused, (TextArea, Input)) and (focused.id or "").startswith("directive-source-"):
            directive = self._directive_for_source_editor_id(focused.id or "")
            if directive is not None:
                new_text = focused.text if isinstance(focused, TextArea) else focused.value
                self.save_directive_editor(directive, new_text)
                return
        editor = self.query_one("#source-editor", TextArea)
        self._save_source_text(editor.text)

    def action_toggle_single_pane(self) -> None:
        self.toggle_single_pane()

    def reload_document(self) -> None:
        text = self.store.load()
        self._active_conflict_message = None
        model = self.parser.parse(text)
        self.model = model
        self.py_results = self._run_autorun_blocks()
        self.web_results = self._run_web_autofetch(model)

        editor = self.query_one("#source-editor", TextArea)
        self._set_source_editor_text(text)
        self._source_dirty = False
        self._set_source_title()

        self._apply_layout_mode()
        ctx = self._build_render_context(model)
        render = self.query_one("#render-pane", DocumentView)
        render.render_document(model, self.registry, ctx, title=self._render_title())
        self._log_autorun_results()

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        if event.text_area.id != "source-editor" or self._loading_source:
            return
        if event.text_area.text == self.model.text:
            return
        self._mark_source_dirty()

    def _find_directive(self, directive_type: str, target: str) -> Directive | None:
        return self.model.directive_index.find(directive_type, target)

    def _py_directives(self) -> list[Directive]:
        return self.model.directive_index.directives_of_type("py")

    def _sh_directives(self) -> list[Directive]:
        return self.model.directive_index.directives_of_type("sh")

    def _run_autorun_blocks(self) -> dict[str, object]:
        directives = self._py_directives()
        if not directives:
            return {}
        return self.py_worker.run_document(directives, autorun_only=True)

    def _web_directives(self) -> list[Directive]:
        return self.model.directive_index.directives_of_type("web")

    def _run_web_autofetch(self, model: DocumentModel) -> dict[str, object]:
        results: dict[str, object] = {}
        for directive in model.directive_index.directives_of_type("web"):
            load_mode = directive.params.get("load", '"auto"').strip('"')
            if load_mode != "manual":
                results[directive.key()] = self._fetch_web_directive(directive)
        return results

    def run_py_block(self, directive: Directive) -> None:
        self.log_status(f"Running {directive.title()} in subprocess worker.")
        key = directive.key()
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

    def reload_web_directive(self, directive: Directive) -> None:
        self.log_status(f"Fetching {directive.title()} in text-only reader.")
        result = self._fetch_web_directive(directive)
        self.web_results[directive.key()] = result
        if result.status == "ok":
            self.log_status(f"{directive.title()} fetched successfully from {result.url}.")
        else:
            self.log_status(f"{directive.title()} failed: {result.error}", error=True)
        self.reload_render_pane()

    def run_sh_block(self, directive: Directive) -> None:
        key = directive.key()
        if not self._trusted_document and key not in self._pending_shell_confirmations:
            self._pending_shell_confirmations.add(key)
            self.log_status(
                f"{directive.title()} is in an untrusted document. Review the command, then press Run again to execute.",
                error=True,
            )
            self.reload_render_pane()
            return

        self._pending_shell_confirmations.discard(key)
        command = directive.params.get("cmd", '""').strip('"')
        cwd = directive.params.get("cwd")
        self.log_status(f"Running {directive.title()} in the shell: {command}")
        result = self.sh_runner.run(key, command, cwd)
        if self._write_sh_output_block(directive, result):
            self.log_status(
                f"{directive.title()} completed with exit={result.exit_code} in {result.duration_seconds:.2f}s."
            )

    def reload_render_pane(self) -> None:
        model = self.model
        self._apply_layout_mode()
        ctx = self._build_render_context(model)
        render = self.query_one("#render-pane", DocumentView)
        render.render_document(model, self.registry, ctx, title=self._render_title())

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
        if self._apply_mutation(mutation, success_message=f"{directive.title()} toggled -> done={directive.params['done']}."):
            return

    def update_table_directive(self, directive: Directive, rows: list[dict[str, object]]) -> None:
        params = dict(directive.params)
        params.pop("source", None)
        params["editable"] = '"true"'
        self._replace_table_directive(
            directive,
            rows,
            params=params,
            source="table.edit",
            success_message=f"{directive.title()} updated from widget edit; source rows materialized into document.",
        )

    def save_contact(
        self,
        directive: Directive,
        path: str | None,
        inline_source: bool,
        card_index: int,
        full_name: str,
        title: str,
        organization: str,
        role: str,
        emails: list[str],
        phones: list[str],
        addresses: list[str],
        note: str,
    ) -> None:
        updated_card = ContactCard(
            full_name=full_name or "Unnamed Contact",
            emails=emails,
            phones=phones,
            organization=organization or None,
            title=title or None,
            role=role or None,
            addresses=addresses,
            note=note or None,
            index=card_index,
        )

        if inline_source:
            header = self._directive_header(directive.type, directive.id, dict(directive.params))
            body = self.contact_reader.serialize_inline_card(updated_card)
            new_text = "\n".join([header, *body, "::end"])
            mutation = TextMutation(
                kind="replace",
                start_line=directive.start_line,
                end_line=directive.end_line,
                new_text=new_text,
                source="contact.save",
            )
            self._apply_mutation(mutation, success_message=f"{directive.title()} saved into the document.")
            return

        base_ctx = self._build_render_context(self.model)
        ctx = self.registry.context_for("contact", base_ctx)
        if ctx.file_access is None:
            self.log_status(f"{directive.title()} save blocked: renderer file access unavailable.", error=True)
            return

        try:
            if path is None:
                self.log_status(f"{directive.title()} save failed: missing contact path.", error=True)
                return
            source_path = ctx.file_access.resolve_document_relative(path)
            cards = self.contact_reader.read_path(source_path, ctx.file_access)
            if not source_path.is_file():
                self.log_status(f"{directive.title()} save is only supported for a single .vcf file.", error=True)
                return
            if card_index < 0 or card_index >= len(cards):
                self.log_status(f"{directive.title()} save failed: contact index is no longer valid.", error=True)
                return

            original = cards[card_index]
            cards[card_index] = ContactCard(
                full_name=updated_card.full_name or original.full_name,
                emails=updated_card.emails,
                phones=updated_card.phones,
                organization=updated_card.organization,
                title=updated_card.title,
                role=updated_card.role,
                addresses=updated_card.addresses,
                note=updated_card.note,
                source=original.source,
                index=original.index,
            )
            self.contact_reader.write_path(source_path, cards, ctx.file_access)
        except (ContactReaderError, PermissionError, OSError) as exc:
            self.log_status(f"{directive.title()} save failed: {exc}", error=True)
            return

        self.log_status(f"{directive.title()} saved to {source_path}.")
        self.reload_render_pane()

    def _replace_table_directive(
        self,
        directive: Directive,
        rows: list[dict[str, object]],
        *,
        params: dict[str, str],
        source: str,
        success_message: str | None = None,
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
        self._apply_mutation(mutation, success_message=success_message)

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

    def _save_source_text(self, text: str) -> bool:
        try:
            self.store.save(text)
        except DocumentConflictError as exc:
            self._active_conflict_message = str(exc)
            self.log_status(str(exc), error=True)
            self.reload_render_pane()
            return False

        self._source_dirty = False
        self._set_source_title()
        self.log_status(f"Saved source document to {self.document_path}.")
        self.reload_document()
        return True

    def _apply_mutation(self, mutation: TextMutation, *, success_message: str | None = None) -> bool:
        try:
            self.mutations.apply(mutation)
        except DocumentConflictError as exc:
            self._active_conflict_message = str(exc)
            self.log_status(str(exc), error=True)
            self.reload_document()
            return False

        if success_message:
            self.log_status(success_message)
        self.reload_document()
        return True

    def open_directive_editor(self, directive: Directive) -> None:
        key = directive.instance_key()
        self._source_view_keys.add(key)
        self._directive_edit_buffers.setdefault(key, self._directive_source_text_from_buffer(directive))
        self.log_status(f"{directive.title()} opened in source edit mode.")
        self.reload_render_pane()

    def update_directive_edit_buffer(self, directive: Directive, new_text: str) -> None:
        self._directive_edit_buffers[directive.instance_key()] = new_text

    def save_directive_editor(self, directive: Directive, new_text: str) -> None:
        editor = self.query_one("#source-editor", TextArea)
        previous_text = self._directive_source_text_from_buffer(directive)
        updated_text = self._replace_directive_text(editor.text, directive, previous_text, new_text)
        if updated_text is None:
            self.log_status(
                f"{directive.title()} source could not be saved. Reload before editing this block again.",
                error=True,
            )
            return
        try:
            self.store.save(updated_text)
        except DocumentConflictError as exc:
            self._active_conflict_message = str(exc)
            self._directive_edit_buffers[directive.instance_key()] = new_text
            self.log_status(str(exc), error=True)
            self.reload_render_pane()
            return

        self._directive_edit_buffers.pop(directive.instance_key(), None)
        self._source_view_keys.discard(directive.instance_key())
        self._source_dirty = False
        self._set_source_title()
        self.log_status(f"{directive.title()} saved and returned to widget view.")
        self.reload_document()

    def cancel_directive_editor(self, directive: Directive) -> None:
        self._directive_edit_buffers.pop(directive.instance_key(), None)
        self._source_view_keys.discard(directive.instance_key())
        self.log_status(f"{directive.title()} edit cancelled; restored widget view.")
        self.reload_render_pane()

    def toggle_single_pane(self, advisory_id: str | None = None) -> None:
        if advisory_id is not None:
            self._dismissed_advisories.add(advisory_id)
        self._single_pane_mode = not self._single_pane_mode
        self._refresh_layout_binding()
        state = "single-pane" if self._single_pane_mode else "split-pane"
        self.log_status(f"Layout switched to {state} mode.")
        self.reload_render_pane()

    def dismiss_advisory(self, advisory_id: str) -> None:
        self._dismissed_advisories.add(advisory_id)
        self.reload_render_pane()

    def handle_reload_request(self, advisory_id: str | None = None) -> None:
        if advisory_id is not None:
            self._dismissed_advisories.discard(advisory_id)
        self.log_status(f"Reloaded {self.document_path} from disk.")
        self.reload_document()

    def _build_render_context(self, model: DocumentModel) -> RenderContext:
        editor = self.query_one("#source-editor", TextArea)
        return RenderContext(
            events=self.events,
            py_results=self.py_results,
            web_results=self.web_results,
            email_selection=dict(self.email_selection),
            document_path=self.document_path,
            source_text=editor.text,
            directives_by_id=model.directive_index.by_id,
            directive_find=model.directive_index.find,
            directive_source_view=set(self._source_view_keys),
            directive_edit_buffers=dict(self._directive_edit_buffers),
            advisories=self._build_advisories(model),
            single_pane_mode=self._single_pane_mode,
            document_trusted=self._trusted_document,
            pending_shell_confirmations=set(self._pending_shell_confirmations),
        )

    def _directive_for_source_editor_id(self, widget_id: str) -> Directive | None:
        prefix = "directive-source-"
        if not widget_id.startswith(prefix):
            return None
        fragment = widget_id[len(prefix) :]
        for directive in self.model.directives:
            if widget_id_fragment(directive.instance_key()) == fragment:
                return directive
        return None

    def _directive_source_text_from_buffer(self, directive: Directive) -> str:
        editor = self.query_one("#source-editor", TextArea)
        lines = editor.text.splitlines()
        if directive.start_line <= directive.end_line and directive.end_line < len(lines):
            return "\n".join(lines[directive.start_line : directive.end_line + 1])
        return directive.header_line

    def select_email_message(self, directive: Directive, message_key: str) -> None:
        self.email_selection[directive.key()] = message_key
        self.reload_render_pane()

    def perform_email_action(self, directive: Directive, message_key: str, action: str) -> None:
        base_ctx = self._build_render_context(self.model)
        ctx = self.registry.context_for("email", base_ctx)
        if ctx.file_access is None:
            self.log_status(f"{directive.title()} action blocked: renderer file access unavailable.", error=True)
            return

        raw_path = directive.id or directive.params.get("path", '"unknown"').strip('"')
        folder = directive.params.get("folder", '"Inbox"').strip('"') or "Inbox"
        archive_folder = directive.params.get("archive-folder", '"Archive"').strip('"') or "Archive"
        trash_folder = directive.params.get("trash-folder", '"Trash"').strip('"') or "Trash"

        try:
            path = ctx.file_access.resolve_document_relative(raw_path)
            store = MaildirEmailStore(path)
            if action == "mark_read":
                store.mark_read(folder, message_key, True)
                self.log_status(f"{directive.title()} marked message {message_key} as read.")
            elif action == "mark_unread":
                store.mark_read(folder, message_key, False)
                self.log_status(f"{directive.title()} marked message {message_key} as unread.")
            elif action == "star":
                store.set_flagged(folder, message_key, True)
                self.log_status(f"{directive.title()} starred message {message_key}.")
            elif action == "unstar":
                store.set_flagged(folder, message_key, False)
                self.log_status(f"{directive.title()} unstarred message {message_key}.")
            elif action == "trash":
                store.move_to_folder(folder, message_key, trash_folder)
                self.email_selection.pop(directive.key(), None)
                self.log_status(f"{directive.title()} moved message {message_key} to {trash_folder}.")
            elif action == "archive":
                store.move_to_folder(folder, message_key, archive_folder)
                self.email_selection.pop(directive.key(), None)
                self.log_status(f"{directive.title()} moved message {message_key} to {archive_folder}.")
            else:
                self.log_status(f"{directive.title()} unknown email action: {action}", error=True)
                return
        except (EmailStoreError, PermissionError, OSError) as exc:
            self.log_status(f"{directive.title()} action failed: {exc}", error=True)
            return

        self.reload_render_pane()

    def save_email_compose(self, directive: Directive, draft: EmailDraft) -> None:
        base_ctx = self._build_render_context(self.model)
        ctx = self.registry.context_for("email", base_ctx)
        if ctx.file_access is None:
            self.log_status(f"{directive.title()} draft save blocked: renderer file access unavailable.", error=True)
            return

        raw_path = directive.params.get("path", '""').strip('"')
        drafts_folder = directive.params.get("drafts-folder", '"Drafts"').strip('"') or "Drafts"
        existing_key = directive.params.get("draft-key", '""').strip('"') or None

        try:
            if not raw_path:
                self.log_status(f"{directive.title()} draft save failed: missing Maildir path.", error=True)
                return
            path = ctx.file_access.resolve_document_relative(raw_path)
            store = MaildirEmailStore(path)
            new_key = store.save_draft(draft, drafts_folder=drafts_folder, existing_key=existing_key)
        except (EmailStoreError, PermissionError, OSError) as exc:
            self.log_status(f"{directive.title()} draft save failed: {exc}", error=True)
            return

        params = dict(directive.params)
        params["path"] = f'"{raw_path}"'
        params["drafts-folder"] = f'"{drafts_folder}"'
        params["draft-key"] = f'"{new_key}"'
        params["from"] = f'"{draft.from_addr}"'
        params["to"] = f'"{draft.to}"'
        if draft.cc:
            params["cc"] = f'"{draft.cc}"'
        else:
            params.pop("cc", None)
        params["subject"] = f'"{draft.subject}"'
        header = self._directive_header(directive.type, directive.id, params)
        body_lines = draft.body.splitlines() if draft.body else []
        new_text = "\n".join([header, *body_lines, "::end"])
        mutation = TextMutation(
            kind="replace",
            start_line=directive.start_line,
            end_line=directive.end_line,
            new_text=new_text,
            source="email.compose_save",
        )
        self._apply_mutation(mutation, success_message=f"{directive.title()} saved draft to {drafts_folder}.")

    def _build_advisories(self, model: DocumentModel) -> list[AdvisorySpec]:
        advisories: list[AdvisorySpec] = []
        line_count = len(model.text.splitlines())

        if line_count >= 40 and "document-size" not in self._dismissed_advisories:
            actions = [AdvisoryAction("dismiss", "dismiss", "advisory.dismiss")]
            if not self._single_pane_mode:
                actions.insert(0, AdvisoryAction("single-pane", "single pane", "ui.toggle_single_pane"))
            advisories.append(
                AdvisorySpec(
                    id="document-size",
                    title="Large Document",
                    message=(
                        f"This document has {line_count} lines ({len(model.directives)} directives). "
                        "Use single-pane mode or directive source toggles to reduce visual load."
                    ),
                    actions=actions,
                    level="warning",
                )
            )

        if self._active_conflict_message is not None and "external-change" not in self._dismissed_advisories:
            advisories.append(
                AdvisorySpec(
                    id="external-change",
                    title="External Change Detected",
                    message=self._active_conflict_message,
                    actions=[
                        AdvisoryAction("reload", "reload", "document.reload"),
                        AdvisoryAction("dismiss", "dismiss", "advisory.dismiss"),
                    ],
                    level="error",
                )
            )

        return advisories

    def _apply_layout_mode(self) -> None:
        source_pane = self.query_one("#source-pane", Vertical)
        render_pane = self.query_one("#render-pane", DocumentView)
        if self._single_pane_mode:
            source_pane.styles.display = "none"
            render_pane.styles.width = "100%"
        else:
            source_pane.styles.display = "block"
            render_pane.styles.width = "1fr"

    def _render_title(self) -> str:
        return "Document (Single Pane)" if self._single_pane_mode else "Rendered"

    def _set_source_editor_text(self, text: str) -> None:
        editor = self.query_one("#source-editor", TextArea)
        self._loading_source = True
        editor.load_text(text)
        self._loading_source = False

    def _mark_source_dirty(self) -> None:
        if self._source_dirty:
            return
        self._source_dirty = True
        self._set_source_title()
        self.log_status("Source buffer modified. Press Ctrl+S to save and reparse.")

    def _replace_directive_text(
        self,
        buffer_text: str,
        directive: Directive,
        previous_text: str,
        new_text: str,
    ) -> str | None:
        lines = buffer_text.splitlines()
        if directive.start_line <= directive.end_line and directive.end_line < len(lines):
            current_slice = "\n".join(lines[directive.start_line : directive.end_line + 1])
            if current_slice == previous_text:
                replacement = [new_text] if new_text else []
                lines[directive.start_line : directive.end_line + 1] = replacement
                return "\n".join(lines)

        occurrences = buffer_text.count(previous_text)
        if occurrences == 1:
            return buffer_text.replace(previous_text, new_text, 1)

        return None

    def _layout_binding_description(self) -> str:
        return "Split Pane" if self._single_pane_mode else "Single Pane"

    def _fetch_web_directive(self, directive: Directive):
        manifest = self.registry.manifest_for("web")
        url = resolve_web_url(directive.id or directive.params.get("url", '"unknown"'))
        allowed_origins = manifest.sandbox.allowed_origins if manifest is not None else ["*"]
        max_fetch_bytes = manifest.sandbox.max_fetch_bytes if manifest is not None else 262144
        timeout_seconds = manifest.sandbox.timeout_seconds if manifest is not None else 5.0
        return self.web_reader.fetch(
            directive.key(),
            url,
            allowed_origins=allowed_origins,
            max_fetch_bytes=max_fetch_bytes,
            timeout_seconds=timeout_seconds,
        )

    def _write_sh_output_block(self, directive: Directive, result) -> bool:
        params = {
            "exit": str(result.exit_code),
            "duration": f'"{result.duration_seconds:.2f}s"',
            "ts": f'"{result.timestamp}"',
        }
        header = self._directive_header("sh-output", directive.id, params)
        body: list[str] = ["[stdout]"]
        body.extend(result.stdout or [""])
        if result.stderr:
            body.extend(["", "[stderr]", *result.stderr])
        new_text = "\n".join([header, *body, "::end"])

        existing = self.model.directive_index.find("sh-output", directive.key())
        if existing is None:
            mutation = TextMutation(
                kind="append",
                start_line=directive.end_line + 1,
                end_line=directive.end_line,
                new_text=new_text,
                source="sh.run",
            )
        else:
            mutation = TextMutation(
                kind="replace",
                start_line=existing.start_line,
                end_line=existing.end_line,
                new_text=new_text,
                source="sh.run",
            )
        return self._apply_mutation(mutation, success_message=None)

    def _refresh_layout_binding(self) -> None:
        description = self._layout_binding_description()
        for key, bindings in list(self._bindings.key_to_bindings.items()):
            updated = False
            new_bindings: list[Binding] = []
            for binding in bindings:
                if binding.id == self.LAYOUT_BINDING_ID:
                    new_bindings.append(replace(binding, description=description))
                    updated = True
                else:
                    new_bindings.append(binding)
            if updated:
                self._bindings.key_to_bindings[key] = new_bindings
        self.refresh_bindings()
