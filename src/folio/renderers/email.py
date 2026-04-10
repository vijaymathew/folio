from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, Static, TextArea

from folio.core.email_store import EmailDraft, EmailMessageView, EmailStoreError, EmailSummary, MaildirEmailStore
from folio.core.models import Directive
from folio.renderers.base import RenderContext, widget_id_fragment


def _parse_int(raw: str | None, default: int) -> int:
    if raw is None:
        return default
    try:
        return max(1, int(raw.strip('"')))
    except ValueError:
        return default


class EmailWidget(Vertical):
    def __init__(
        self,
        directive: Directive,
        ctx: RenderContext,
        path: Path,
        folder: str,
        summaries: list[EmailSummary],
        selected: EmailMessageView | None,
        *,
        limit: int,
        folders: list[str],
    ) -> None:
        super().__init__(classes="email-widget")
        self.directive = directive
        self.ctx = ctx
        self.path = path
        self.folder = folder
        self.summaries = summaries
        self.selected = selected
        self.limit = limit
        self.folders = folders
        self.key_fragment = widget_id_fragment(directive.key())
        self.border_title = Text(directive.title())

    def compose(self) -> ComposeResult:
        yield Static(self._meta_text(), classes="email-meta", markup=False)
        if not self.summaries:
            yield Static("(empty mailbox folder)", classes="email-empty", markup=False)
            return

        with Vertical(classes="email-list"):
            for index, summary in enumerate(self.summaries):
                label = self._summary_label(summary)
                yield Button(label, id=f"email-open-{self.key_fragment}-{index}", compact=True, classes="email-open")

        if self.selected is not None:
            with Horizontal(classes="email-actions"):
                yield Button(self._read_label(), id=f"email-read-{self.key_fragment}", compact=True, classes="email-action")
                yield Button(self._star_label(), id=f"email-star-{self.key_fragment}", compact=True, classes="email-action")
                yield Button("Trash", id=f"email-trash-{self.key_fragment}", compact=True, classes="email-action")
                yield Button("Archive", id=f"email-archive-{self.key_fragment}", compact=True, classes="email-action")
            yield Static(self._selected_header_text(), classes="email-selected-meta", markup=False)
            yield Static(self.selected.body, classes="email-body", markup=False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if self.ctx.events is None:
            return

        button_id = event.button.id or ""
        open_prefix = f"email-open-{self.key_fragment}-"
        if button_id.startswith(open_prefix):
            try:
                index = int(button_id[len(open_prefix) :])
            except ValueError:
                return
            if 0 <= index < len(self.summaries):
                self.ctx.events.emit(
                    "email.select",
                    directive=self.directive,
                    message_key=self.summaries[index].key,
                )
                event.stop()
            return

        if self.selected is None:
            return

        action_map = {
            f"email-read-{self.key_fragment}": "mark_unread" if "S" in self.selected.flags else "mark_read",
            f"email-star-{self.key_fragment}": "unstar" if "F" in self.selected.flags else "star",
            f"email-trash-{self.key_fragment}": "trash",
            f"email-archive-{self.key_fragment}": "archive",
        }
        action = action_map.get(button_id)
        if action is None:
            return
        self.ctx.events.emit(
            "email.action",
            directive=self.directive,
            message_key=self.selected.key,
            action=action,
        )
        event.stop()

    def _meta_text(self) -> str:
        folder_list = ", ".join(self.folders[:6])
        if len(self.folders) > 6:
            folder_list += f", ... {len(self.folders) - 6} more"
        return f"Maildir: {self.path} | folder={self.folder} | showing {len(self.summaries)} | folders: {folder_list}"

    def _summary_label(self, summary: EmailSummary) -> str:
        selected_key = self.selected.key if self.selected is not None else self.summaries[0].key
        marker = ">" if summary.key == selected_key else " "
        unread = "•" if "S" not in summary.flags else " "
        starred = "*" if "F" in summary.flags else " "
        subject = summary.subject[:48]
        sender = summary.sender[:24]
        return f"{marker}{unread}{starred} {sender} | {subject} | {summary.date}"

    def _selected_header_text(self) -> str:
        if self.selected is None:
            return ""
        lines = [
            f"From: {self.selected.sender}",
            f"To: {self.selected.to or '(none)'}",
            f"Date: {self.selected.date or '(unknown)'}",
            f"Subject: {self.selected.subject}",
            f"Flags: {self.selected.flags or '(none)'}",
        ]
        if self.selected.cc:
            lines.insert(2, f"Cc: {self.selected.cc}")
        return "\n".join(lines)

    def _read_label(self) -> str:
        assert self.selected is not None
        return "Mark Unread" if "S" in self.selected.flags else "Mark Read"

    def _star_label(self) -> str:
        assert self.selected is not None
        return "Unstar" if "F" in self.selected.flags else "Star"


class EmailComposeWidget(Vertical):
    def __init__(self, directive: Directive, ctx: RenderContext, draft: EmailDraft) -> None:
        super().__init__(classes="email-compose-widget")
        self.directive = directive
        self.ctx = ctx
        self.draft = draft
        self.key_fragment = widget_id_fragment(directive.key())
        self.border_title = Text(directive.title())

    def compose(self) -> ComposeResult:
        yield Static(self._meta_text(), classes="email-compose-meta", markup=False)
        with Vertical(classes="email-compose-form"):
            yield self._field("From", "from", self.draft.from_addr)
            yield self._field("To", "to", self.draft.to)
            yield self._field("Cc", "cc", self.draft.cc)
            yield self._field("Subject", "subject", self.draft.subject)
            editor = TextArea(
                self.draft.body,
                id=f"email-compose-body-{self.key_fragment}",
                classes="email-compose-body",
                language="markdown",
                soft_wrap=True,
                show_line_numbers=False,
            )
            editor.border_title = "Body"
            yield editor
            with Horizontal(classes="email-compose-actions"):
                yield Button("Save Draft", id=f"email-compose-save-{self.key_fragment}", compact=True, classes="email-compose-save")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != f"email-compose-save-{self.key_fragment}" or self.ctx.events is None:
            return
        draft = EmailDraft(
            from_addr=self.query_one(f"#email-compose-from-{self.key_fragment}", Input).value.strip(),
            to=self.query_one(f"#email-compose-to-{self.key_fragment}", Input).value.strip(),
            cc=self.query_one(f"#email-compose-cc-{self.key_fragment}", Input).value.strip(),
            subject=self.query_one(f"#email-compose-subject-{self.key_fragment}", Input).value.strip(),
            body=self.query_one(f"#email-compose-body-{self.key_fragment}", TextArea).text.rstrip(),
        )
        self.ctx.events.emit("email.compose_save", directive=self.directive, draft=draft)
        event.stop()

    def _field(self, label: str, name: str, value: str) -> Input:
        field = Input(value, id=f"email-compose-{name}-{self.key_fragment}", classes="email-compose-input")
        field.border_title = label
        return field

    def _meta_text(self) -> str:
        drafts_folder = self.directive.params.get("drafts-folder", '"Drafts"').strip('"') or "Drafts"
        path = self.directive.params.get("path", '""').strip('"') or "(missing path)"
        draft_key = self.directive.params.get("draft-key", '""').strip('"')
        suffix = f" | draft-key={draft_key}" if draft_key else ""
        return f"Maildir: {path} | drafts={drafts_folder}{suffix}"


class EmailRenderer:
    manifest_path = Path(__file__).with_name("manifests") / "email.toml"

    def render(self, directive: Directive, ctx: RenderContext) -> Static:
        if directive.id == "draft":
            draft = EmailDraft(
                from_addr=directive.params.get("from", '""').strip('"'),
                to=directive.params.get("to", '""').strip('"'),
                cc=directive.params.get("cc", '""').strip('"'),
                subject=directive.params.get("subject", '""').strip('"'),
                body="\n".join(directive.body).strip(),
            )
            return EmailComposeWidget(directive, ctx, draft)

        if ctx.file_access is None:
            return Static("Renderer capability denied: filesystem_read.", classes="email-widget")

        raw_path = directive.id or directive.params.get("path", '"unknown"').strip('"')
        folder = directive.params.get("folder", '"Inbox"').strip('"') or "Inbox"
        limit = _parse_int(directive.params.get("limit"), 20)

        try:
            path = ctx.file_access.resolve_document_relative(raw_path)
            store = MaildirEmailStore(path)
            summaries = store.list_messages(folder, limit=limit)
            selected_key = (ctx.email_selection or {}).get(directive.key()) or (summaries[0].key if summaries else None)
            selected = store.get_message(folder, selected_key) if selected_key is not None else None
            return EmailWidget(
                directive,
                ctx,
                path,
                folder,
                summaries,
                selected,
                limit=limit,
                folders=store.list_folders(),
            )
        except (EmailStoreError, PermissionError) as exc:
            return Static(str(exc), classes="email-widget")
