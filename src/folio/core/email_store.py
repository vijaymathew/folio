from __future__ import annotations

import mailbox
import re
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.header import decode_header, make_header
from email.parser import BytesParser
from email.policy import default
from email.utils import parsedate_to_datetime
from pathlib import Path


@dataclass(slots=True)
class EmailSummary:
    key: str
    subject: str
    sender: str
    date: str
    flags: str
    preview: str
    folder: str


@dataclass(slots=True)
class EmailMessageView:
    key: str
    subject: str
    sender: str
    to: str
    cc: str
    date: str
    flags: str
    body: str
    preview: str
    folder: str
    headers: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class EmailDraft:
    from_addr: str
    to: str
    cc: str
    subject: str
    body: str


class EmailStoreError(RuntimeError):
    pass


class MaildirEmailStore:
    INBOX = "Inbox"
    BODY_SEPARATOR = "---"

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self._ensure_maildir()

    def list_folders(self) -> list[str]:
        root_box = mailbox.Maildir(self.root, create=False)
        folders = [self.INBOX]
        folders.extend(sorted(root_box.list_folders()))
        return folders

    def list_messages(self, folder: str = INBOX, limit: int = 50) -> list[EmailSummary]:
        box = self._mailbox_for_folder(folder)
        summaries: list[tuple[float, EmailSummary]] = []
        for key in box.iterkeys():
            message = box.get_message(key)
            parsed = self._parse_bytes(box.get_bytes(key))
            summary = EmailSummary(
                key=str(key),
                subject=self._header(parsed, "subject") or "(no subject)",
                sender=self._header(parsed, "from") or "(unknown sender)",
                date=self._header(parsed, "date") or "",
                flags=message.get_flags(),
                preview=self._preview_from_message(parsed),
                folder=folder or self.INBOX,
            )
            summaries.append((self._sort_timestamp(summary.date, message), summary))
        summaries.sort(key=lambda item: item[0], reverse=True)
        return [summary for _, summary in summaries[:limit]]

    def get_message(self, folder: str, key: str) -> EmailMessageView | None:
        box = self._mailbox_for_folder(folder)
        if key not in box:
            return None
        message = box.get_message(key)
        parsed = self._parse_bytes(box.get_bytes(key))
        body = self._body_from_message(parsed)
        return EmailMessageView(
            key=str(key),
            subject=self._header(parsed, "subject") or "(no subject)",
            sender=self._header(parsed, "from") or "(unknown sender)",
            to=self._header(parsed, "to") or "",
            cc=self._header(parsed, "cc") or "",
            date=self._header(parsed, "date") or "",
            flags=message.get_flags(),
            body=body or "(empty message)",
            preview=self._preview_from_text(body),
            folder=folder or self.INBOX,
            headers={
                "From": self._header(parsed, "from") or "",
                "To": self._header(parsed, "to") or "",
                "Cc": self._header(parsed, "cc") or "",
                "Date": self._header(parsed, "date") or "",
                "Subject": self._header(parsed, "subject") or "",
            },
        )

    def mark_read(self, folder: str, key: str, read: bool) -> None:
        box = self._mailbox_for_folder(folder)
        message = self._require_message(box, key)
        message.set_subdir("cur")
        flags = set(message.get_flags())
        if read:
            flags.add("S")
        else:
            flags.discard("S")
        message.set_flags("".join(sorted(flags)))
        box[key] = message
        box.flush()

    def set_flagged(self, folder: str, key: str, flagged: bool) -> None:
        box = self._mailbox_for_folder(folder)
        message = self._require_message(box, key)
        message.set_subdir("cur")
        flags = set(message.get_flags())
        if flagged:
            flags.add("F")
        else:
            flags.discard("F")
        message.set_flags("".join(sorted(flags)))
        box[key] = message
        box.flush()

    def move_to_folder(self, folder: str, key: str, target_folder: str) -> str:
        source_box = self._mailbox_for_folder(folder)
        message = self._require_message(source_box, key)
        target_box = self._mailbox_for_folder(target_folder, create=True)
        new_key = target_box.add(message)
        source_box.remove(key)
        source_box.flush()
        target_box.flush()
        return str(new_key)

    def save_draft(self, draft: EmailDraft, drafts_folder: str = "Drafts", existing_key: str | None = None) -> str:
        box = self._mailbox_for_folder(drafts_folder, create=True)
        if existing_key is not None and existing_key in box:
            box.remove(existing_key)
        message = self._build_draft_message(draft)
        maildir_message = mailbox.MaildirMessage(message)
        maildir_message.set_subdir("cur")
        maildir_message.set_flags("D")
        key = box.add(maildir_message)
        box.flush()
        return str(key)

    @staticmethod
    def parse_compose_body(lines: list[str]) -> EmailDraft:
        headers: dict[str, str] = {}
        body_lines: list[str] = []
        in_body = False
        for raw_line in lines:
            line = raw_line.rstrip("\n")
            if not in_body and line.strip() == MaildirEmailStore.BODY_SEPARATOR:
                in_body = True
                continue
            if in_body:
                body_lines.append(line)
                continue
            if "=" not in line:
                continue
            raw_key, raw_value = line.split("=", 1)
            headers[raw_key.strip().lower()] = raw_value.strip()
        return EmailDraft(
            from_addr=headers.get("from", ""),
            to=headers.get("to", ""),
            cc=headers.get("cc", ""),
            subject=headers.get("subject", ""),
            body="\n".join(body_lines).strip(),
        )

    @staticmethod
    def serialize_compose_body(draft: EmailDraft) -> list[str]:
        lines = [
            f"from = {draft.from_addr}",
            f"to = {draft.to}",
            f"cc = {draft.cc}",
            f"subject = {draft.subject}",
            MaildirEmailStore.BODY_SEPARATOR,
        ]
        if draft.body:
            lines.extend(draft.body.splitlines())
        return lines

    def _mailbox_for_folder(self, folder: str, *, create: bool = False):
        normalized = folder.strip() if folder else self.INBOX
        if normalized in {"", self.INBOX}:
            return mailbox.Maildir(self.root, create=create)
        root_box = mailbox.Maildir(self.root, create=False)
        folders = set(root_box.list_folders())
        if normalized in folders:
            return root_box.get_folder(normalized)
        if create:
            return root_box.add_folder(normalized)
        raise EmailStoreError(f"Maildir folder not found: {normalized}")

    def _build_draft_message(self, draft: EmailDraft) -> EmailMessage:
        message = EmailMessage()
        if draft.from_addr:
            message["From"] = draft.from_addr
        if draft.to:
            message["To"] = draft.to
        if draft.cc:
            message["Cc"] = draft.cc
        if draft.subject:
            message["Subject"] = draft.subject
        message.set_content(draft.body or "")
        return message

    def _ensure_maildir(self) -> None:
        required = [self.root / "cur", self.root / "new", self.root / "tmp"]
        if not self.root.exists():
            raise EmailStoreError(f"Maildir path not found: {self.root}")
        if not self.root.is_dir():
            raise EmailStoreError(f"Maildir path is not a directory: {self.root}")
        missing = [path.name for path in required if not path.is_dir()]
        if missing:
            raise EmailStoreError(f"Path is not a Maildir mailbox: {self.root} (missing {', '.join(missing)})")

    def _require_message(self, box, key: str):
        if key not in box:
            raise EmailStoreError(f"Maildir message not found: {key}")
        return box.get_message(key)

    def _parse_bytes(self, data: bytes):
        return BytesParser(policy=default).parsebytes(data)

    def _header(self, message, name: str) -> str | None:
        raw = message.get(name)
        if raw is None:
            return None
        try:
            return str(make_header(decode_header(raw))).strip()
        except Exception:
            return str(raw).strip()

    def _body_from_message(self, message) -> str:
        if message.is_multipart():
            for part in message.walk():
                if part.get_content_maintype() == "multipart":
                    continue
                disposition = part.get_content_disposition()
                if disposition == "attachment":
                    continue
                content_type = part.get_content_type()
                try:
                    payload = part.get_content()
                except Exception:
                    payload = None
                if not payload:
                    continue
                if content_type == "text/plain":
                    return self._normalize_text(str(payload))
                if content_type == "text/html":
                    html_text = self._strip_html(str(payload))
                    if html_text.strip():
                        return html_text
            return ""

        try:
            payload = message.get_content()
        except Exception:
            payload = message.get_payload(decode=True) or b""
        if isinstance(payload, bytes):
            charset = message.get_content_charset() or "utf-8"
            return payload.decode(charset, errors="replace")
        content_type = message.get_content_type()
        text = str(payload)
        if content_type == "text/html":
            return self._strip_html(text)
        return self._normalize_text(text)

    def _preview_from_message(self, message) -> str:
        return self._preview_from_text(self._body_from_message(message))

    def _preview_from_text(self, text: str) -> str:
        normalized = " ".join(self._normalize_text(text).split())
        if not normalized:
            return "(no preview)"
        return normalized[:140] + ("..." if len(normalized) > 140 else "")

    def _normalize_text(self, text: str) -> str:
        return text.replace("\r\n", "\n").replace("\r", "\n").strip()

    def _strip_html(self, html: str) -> str:
        no_tags = re.sub(r"<[^>]+>", " ", html)
        return re.sub(r"\s+", " ", no_tags).strip()

    def _sort_timestamp(self, raw_date: str, maildir_message) -> float:
        try:
            parsed = parsedate_to_datetime(raw_date)
            if parsed is not None:
                return parsed.timestamp()
        except Exception:
            pass
        try:
            return float(maildir_message.get_date())
        except Exception:
            return 0.0
