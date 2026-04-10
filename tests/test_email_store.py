from __future__ import annotations

import mailbox
from email.message import EmailMessage
from pathlib import Path

from folio.core.email_store import MaildirEmailStore


def _seed_maildir(path: Path) -> MaildirEmailStore:
    inbox = mailbox.Maildir(path, create=True)
    for subject, sender, body in (
        ("Launch Notes", "maya@example.com", "Here are the launch notes for the release."),
        ("Budget Review", "sara@example.com", "Please review the latest budget sheet."),
    ):
        message = EmailMessage()
        message["From"] = sender
        message["To"] = "team@example.com"
        message["Subject"] = subject
        message["Date"] = "Fri, 11 Apr 2026 10:00:00 +0000"
        message.set_content(body)
        inbox.add(message)
    inbox.flush()
    return MaildirEmailStore(path)


def test_maildir_store_lists_messages_and_reads_body(tmp_path: Path) -> None:
    store = _seed_maildir(tmp_path / "mail")

    summaries = store.list_messages("Inbox", limit=10)

    assert len(summaries) == 2
    subjects = {summary.subject for summary in summaries}
    assert subjects == {"Launch Notes", "Budget Review"}
    launch_summary = next(summary for summary in summaries if summary.subject == "Launch Notes")
    message = store.get_message("Inbox", launch_summary.key)
    assert message is not None
    assert "launch notes" in message.body.lower()


def test_maildir_store_updates_flags_and_moves_messages(tmp_path: Path) -> None:
    store = _seed_maildir(tmp_path / "mail")
    summaries = store.list_messages("Inbox", limit=10)
    key = summaries[0].key
    subject = summaries[0].subject

    store.mark_read("Inbox", key, True)
    assert "S" in (store.get_message("Inbox", key).flags)  # type: ignore[union-attr]

    store.set_flagged("Inbox", key, True)
    assert "F" in (store.get_message("Inbox", key).flags)  # type: ignore[union-attr]

    moved_key = store.move_to_folder("Inbox", key, "Archive")
    archived = store.get_message("Archive", moved_key)
    assert archived is not None
    assert archived.subject == subject
