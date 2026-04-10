from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, Static

from folio.core.contact_reader import ContactCard, ContactReader, ContactReaderError
from folio.core.models import Directive
from folio.renderers.base import RenderContext, widget_id_fragment


def _parse_int(raw: str | None, default: int) -> int:
    if raw is None:
        return default
    try:
        return max(1, int(raw.strip('"')))
    except ValueError:
        return default


class ContactWidget(Vertical):
    def __init__(self, directive: Directive, contacts: list[ContactCard], source_path: Path, limit: int, ctx: RenderContext) -> None:
        super().__init__(classes="contact-widget")
        self.directive = directive
        self.contacts = contacts
        self.source_path = source_path
        self.limit = limit
        self.ctx = ctx
        self.key_fragment = widget_id_fragment(directive.key())
        self.border_title = Text(directive.title())

    @property
    def visible_contacts(self) -> list[ContactCard]:
        return self.contacts[: self.limit]

    @property
    def editable_contact(self) -> ContactCard | None:
        if self.source_path.is_file() and len(self.contacts) == 1:
            return self.contacts[0]
        return None

    def compose(self) -> ComposeResult:
        yield Static(self._meta_text(), classes="contact-meta", markup=False)
        if not self.contacts:
            yield Static("(no contacts found)", classes="contact-empty", markup=False)
            return
        editable_contact = self.editable_contact
        if editable_contact is not None:
            yield Static("Edit fields and press Save to write the .vcf file.", classes="contact-status", markup=False)
            with Vertical(classes="contact-form"):
                yield ContactField("Full name", "name", editable_contact.full_name, self.key_fragment)
                yield ContactField("Title", "title", editable_contact.title or "", self.key_fragment)
                yield ContactField("Organization", "organization", editable_contact.organization or "", self.key_fragment)
                yield ContactField("Role", "role", editable_contact.role or "", self.key_fragment)
                yield ContactField("Email", "emails", ", ".join(editable_contact.emails), self.key_fragment)
                yield ContactField("Phone", "phones", ", ".join(editable_contact.phones), self.key_fragment)
                yield ContactField("Address", "addresses", " | ".join(editable_contact.addresses), self.key_fragment)
                yield ContactField("Note", "note", editable_contact.note or "", self.key_fragment)
                with Horizontal(classes="contact-actions"):
                    yield Button("Save", id=f"save-contact-{self.key_fragment}", compact=True, classes="contact-save")
            return
        for contact in self.visible_contacts:
            yield Static(self._contact_text(contact), classes="contact-card", markup=False)
        if len(self.contacts) > self.limit:
            yield Static(f"... {len(self.contacts) - self.limit} more contacts", classes="contact-more", markup=False)
        if self.source_path.is_dir() or len(self.contacts) > 1:
            yield Static("Editing is available for single-contact .vcf files.", classes="contact-status", markup=False)

    def _meta_text(self) -> str:
        count = len(self.contacts)
        noun = "contact" if count == 1 else "contacts"
        return f"vCard source: {self.source_path} ({count} {noun})"

    def _contact_text(self, contact: ContactCard) -> str:
        lines = [contact.full_name]
        detail_parts = [part for part in (contact.title, contact.organization or contact.role) if part]
        if detail_parts:
            lines.append(" — ".join(detail_parts))
        if contact.emails:
            lines.append("Email: " + ", ".join(contact.emails))
        if contact.phones:
            lines.append("Phone: " + ", ".join(contact.phones))
        if contact.addresses:
            lines.append("Address: " + " | ".join(contact.addresses))
        if contact.note:
            first_line = contact.note.splitlines()[0]
            lines.append("Note: " + first_line)
        if contact.source and len(self.contacts) > 1:
            lines.append(f"Source: {contact.source}")
        return "\n".join(lines)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != f"save-contact-{self.key_fragment}" or self.ctx.events is None:
            return
        contact = self.editable_contact
        if contact is None:
            return
        self.ctx.events.emit(
            "contact.save",
            directive=self.directive,
            path=str(self.source_path),
            card_index=contact.index,
            full_name=self._input_value("name"),
            title=self._input_value("title"),
            organization=self._input_value("organization"),
            role=self._input_value("role"),
            emails=self._split_csv(self._input_value("emails")),
            phones=self._split_csv(self._input_value("phones")),
            addresses=self._split_pipe(self._input_value("addresses")),
            note=self._input_value("note"),
        )
        event.stop()

    def _input_value(self, field_name: str) -> str:
        input_widget = self.query_one(f"#contact-{field_name}-{self.key_fragment}", Input)
        return input_widget.value.strip()

    def _split_csv(self, value: str) -> list[str]:
        return [item.strip() for item in value.split(",") if item.strip()]

    def _split_pipe(self, value: str) -> list[str]:
        return [item.strip() for item in value.split("|") if item.strip()]


class ContactRenderer:
    manifest_path = Path(__file__).with_name("manifests") / "contact.toml"

    def __init__(self) -> None:
        self.reader = ContactReader()

    def render(self, directive: Directive, ctx: RenderContext) -> Static:
        if ctx.file_access is None:
            return Static("Renderer capability denied: filesystem_read.", classes="contact-widget")

        raw_path = directive.id or directive.params.get("path", '"unknown"').strip('"')
        limit = _parse_int(directive.params.get("limit"), 6)

        try:
            source_path = ctx.file_access.resolve_document_relative(raw_path)
            contacts = self.reader.read_path(source_path, ctx.file_access)
        except (ContactReaderError, PermissionError) as exc:
            return Static(str(exc), classes="contact-widget")

        return ContactWidget(directive, contacts, source_path, limit, ctx)


class ContactField(Vertical):
    def __init__(self, label: str, field_name: str, value: str, key_fragment: str) -> None:
        super().__init__(classes="contact-field")
        self.label = label
        self.field_name = field_name
        self.value = value
        self.key_fragment = key_fragment
        self.border_title = label

    def compose(self) -> ComposeResult:
        yield Input(
            self.value,
            id=f"contact-{self.field_name}-{self.key_fragment}",
            classes="contact-input",
        )
