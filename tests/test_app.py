from __future__ import annotations

import asyncio
import mailbox
import shutil
from email.message import EmailMessage
from pathlib import Path

from folio.core.models import ShRunResult, WebLink, WebPageResult
from folio.renderers.contact import ContactWidget
from folio.renderers.email import EmailComposeWidget, EmailWidget
from folio.renderers.base import widget_id_fragment
from folio.renderers.table import TableEditor
from folio.ui.document_view import DocumentView
from folio.ui.app import FolioApp
from textual.widgets import Button, DataTable, Input, TextArea


async def _find_visible_button(app: FolioApp, pilot, button_id: str) -> Button:
    render = app.query_one("#render-pane", DocumentView)
    for offset in range(0, 240, 8):
        matches = list(app.query(f"#{button_id}"))
        if matches:
            return matches[0]
        render.scroll_to(y=offset, animate=False)
        await pilot.pause(0.1)
    raise AssertionError(f"button #{button_id} was not mounted in the render viewport")


async def _find_visible_table(app: FolioApp, pilot) -> TableEditor:
    render = app.query_one("#render-pane", DocumentView)
    for offset in range(0, 280, 8):
        matches = list(app.query(TableEditor))
        if matches:
            return matches[0]
        render.scroll_to(y=offset, animate=False)
        await pilot.pause(0.1)
    raise AssertionError("TableEditor was not mounted in the render viewport")


def _seed_maildir(path: Path) -> None:
    maildir = mailbox.Maildir(path, create=True)
    for subject, sender, body in (
        ("Launch Notes", "maya@example.com", "Release checklist attached in plain text."),
        ("Budget Review", "sara@example.com", "Please review the Q3 budget variance."),
    ):
        message = EmailMessage()
        message["From"] = sender
        message["To"] = "team@example.com"
        message["Subject"] = subject
        message["Date"] = "Fri, 11 Apr 2026 10:00:00 +0000"
        message.set_content(body)
        maildir.add(message)
    maildir.flush()


def test_task_checkbox_click_rewrites_source(tmp_path: Path) -> None:
    source = Path("/home/vijay/Projects/folio/docs/example.folio")
    doc = tmp_path / "example.folio"
    shutil.copyfile(source, doc)

    async def scenario() -> None:
        app = FolioApp(doc)
        async with app.run_test(size=(140, 45)) as pilot:
            await pilot.pause(0.2)
            await pilot.click("#toggle-call-finance")
            await pilot.pause(0.2)

    asyncio.run(scenario())

    updated = doc.read_text()
    assert 'done="true"' in updated
    assert 'completed="now"' in updated


def test_run_py_materializes_live_table_widget(tmp_path: Path) -> None:
    source = Path("/home/vijay/Projects/folio/docs/example.folio")
    doc = tmp_path / "example.folio"
    shutil.copyfile(source, doc)

    async def scenario() -> None:
        app = FolioApp(doc)
        async with app.run_test(size=(140, 45)) as pilot:
            await pilot.pause(0.2)
            (await _find_visible_button(app, pilot, "run-py-budget-check")).press()
            await pilot.pause(0.2)
            table = await _find_visible_table(app, pilot)
            assert len(table.rows) == 4

    asyncio.run(scenario())


def test_table_edit_updates_document_text(tmp_path: Path) -> None:
    source = Path("/home/vijay/Projects/folio/docs/example.folio")
    doc = tmp_path / "example.folio"
    shutil.copyfile(source, doc)

    async def scenario() -> None:
        app = FolioApp(doc)
        async with app.run_test(size=(140, 45)) as pilot:
            await pilot.pause(0.2)
            (await _find_visible_button(app, pilot, "run-py-budget-check")).press()
            await pilot.pause(0.2)
            table = await _find_visible_table(app, pilot)
            grid = table.query_one(DataTable)
            grid.move_cursor(row=0, column=2)
            grid.focus()
            await pilot.pause(0.2)
            await pilot.press("9", "9", "9", "9", "enter")
            await pilot.pause(0.2)

    asyncio.run(scenario())

    updated = doc.read_text()
    assert '"budget": 9999' in updated


def test_render_pane_only_mounts_visible_window(tmp_path: Path) -> None:
    doc = tmp_path / "windowed.folio"
    blocks = []
    for index in range(30):
        blocks.append(
            "\n".join(
                [
                    f'::task[item-{index}]{{done="false" due="soon"}}',
                    f"Task {index}",
                    "::end",
                ]
            )
        )
    doc.write_text("\n\n".join(blocks))

    async def scenario() -> None:
        app = FolioApp(doc)
        async with app.run_test(size=(100, 18)) as pilot:
            await pilot.pause(0.2)
            initial_buttons = [button.id for button in app.query(Button) if button.id and button.id.startswith("toggle-item-")]
            assert len(initial_buttons) < 30
            assert list(app.query("#toggle-item-0"))
            assert not list(app.query("#toggle-item-29"))

            render = app.query_one("#render-pane", DocumentView)
            render.scroll_end(animate=False)
            await pilot.pause(0.3)

            scrolled_buttons = [button.id for button in app.query(Button) if button.id and button.id.startswith("toggle-item-")]
            assert len(scrolled_buttons) < 30
            assert list(app.query("#toggle-item-29"))
            assert not list(app.query("#toggle-item-0"))

    asyncio.run(scenario())


def test_directive_can_toggle_between_widget_and_source_view(tmp_path: Path) -> None:
    source = Path("/home/vijay/Projects/folio/docs/example.folio")
    doc = tmp_path / "example.folio"
    shutil.copyfile(source, doc)

    async def scenario() -> None:
        app = FolioApp(doc)
        async with app.run_test(size=(140, 45)) as pilot:
            await pilot.pause(0.2)
            assert list(app.query("#toggle-call-finance"))
            await pilot.click("#toggle-view-call-finance")
            await pilot.pause(0.2)
            assert not list(app.query("#toggle-call-finance"))
            assert app.query_one("#directive-source-call-finance", TextArea)

    asyncio.run(scenario())


def test_inline_directive_source_editor_updates_main_source_buffer(tmp_path: Path) -> None:
    source = Path("/home/vijay/Projects/folio/docs/example.folio")
    doc = tmp_path / "example.folio"
    shutil.copyfile(source, doc)

    async def scenario() -> None:
        app = FolioApp(doc)
        async with app.run_test(size=(140, 45)) as pilot:
            await pilot.pause(0.2)
            app.query_one("#toggle-view-call-finance", Button).press()
            await pilot.pause(0.2)

            inline_editor = app.query_one("#directive-source-call-finance", TextArea)
            updated_text = inline_editor.text.replace('done="false"', 'done="true"', 1)
            inline_editor.load_text(updated_text)
            await pilot.pause(0.2)

            source_editor = app.query_one("#source-editor", TextArea)
            assert updated_text in source_editor.text
            assert app._source_dirty is True

    asyncio.run(scenario())


def test_file_directive_toggle_uses_safe_widget_ids(tmp_path: Path) -> None:
    source = Path("/home/vijay/Projects/folio/docs/example.folio")
    doc = tmp_path / "example.folio"
    shutil.copyfile(source, doc)
    key_fragment = widget_id_fragment("docs/renderer-interface.md")

    async def scenario() -> None:
        app = FolioApp(doc)
        async with app.run_test(size=(140, 45)) as pilot:
            await pilot.pause(0.2)
            render = app.query_one("#render-pane", DocumentView)
            render.scroll_end(animate=False)
            await pilot.pause(0.3)
            assert list(app.query(f"#toggle-view-{key_fragment}"))
            app.query_one(f"#toggle-view-{key_fragment}", Button).press()
            await pilot.pause(0.2)
            assert list(app.query(f"#directive-source-{key_fragment}"))

    asyncio.run(scenario())


def test_single_pane_mode_is_default_and_f6_switches_to_split_pane(tmp_path: Path) -> None:
    source = Path("/home/vijay/Projects/folio/docs/example.folio")
    doc = tmp_path / "example.folio"
    shutil.copyfile(source, doc)

    async def scenario() -> None:
        app = FolioApp(doc)
        async with app.run_test(size=(140, 45)) as pilot:
            await pilot.pause(0.2)
            source_pane = app.query_one("#source-pane")
            assert app._single_pane_mode is True
            assert source_pane.styles.display == "none"
            assert app._render_title() == "Document (Single Pane)"
            assert app.active_bindings["f6"].binding.description == "Split Pane"

            await pilot.press("f6")
            await pilot.pause(0.2)
            assert app._single_pane_mode is False
            assert source_pane.styles.display == "block"
            assert app._render_title() == "Rendered"
            assert app.active_bindings["f6"].binding.description == "Single Pane"

    asyncio.run(scenario())


def test_large_document_shows_inline_advisory(tmp_path: Path) -> None:
    doc = tmp_path / "advisory.folio"
    blocks = []
    for index in range(16):
        blocks.append(
            "\n".join(
                [
                    f'::task[item-{index}]{{done="false" due="soon"}}',
                    f"Task {index}",
                    "::end",
                    "",
                ]
            )
        )
    doc.write_text("\n".join(blocks), encoding="utf-8")

    async def scenario() -> None:
        app = FolioApp(doc)
        async with app.run_test(size=(140, 45)) as pilot:
            await pilot.pause(0.2)
            assert not list(app.query("#advisory-action-document-size-single-pane"))
            assert list(app.query("#advisory-action-document-size-dismiss"))
            await pilot.click("#advisory-action-document-size-dismiss")
            await pilot.pause(0.2)
            assert not list(app.query("#advisory-action-document-size-dismiss"))

    asyncio.run(scenario())


def test_large_document_advisory_can_toggle_single_pane(tmp_path: Path) -> None:
    doc = tmp_path / "advisory-toggle.folio"
    blocks = []
    for index in range(16):
        blocks.append(
            "\n".join(
                [
                    f'::task[item-{index}]{{done="false" due="soon"}}',
                    f"Task {index}",
                    "::end",
                    "",
                ]
            )
        )
    doc.write_text("\n".join(blocks), encoding="utf-8")

    async def scenario() -> None:
        app = FolioApp(doc)
        async with app.run_test(size=(140, 45)) as pilot:
            await pilot.pause(0.2)
            assert app._single_pane_mode is True
            await pilot.press("f6")
            await pilot.pause(0.2)
            assert app._single_pane_mode is False
            assert list(app.query("#advisory-action-document-size-single-pane"))
            await pilot.click("#advisory-action-document-size-single-pane")
            await pilot.pause(0.2)
            assert app._single_pane_mode is True
            assert "document-size" in app._dismissed_advisories

    asyncio.run(scenario())


def test_web_reader_fetches_text_only_page(tmp_path: Path) -> None:
    doc = tmp_path / "web.folio"
    url = "https://example.test/article"
    doc.write_text(f'::web[{url}]{{load="manual" lines="20"}}\n', encoding="utf-8")

    async def scenario() -> None:
        app = FolioApp(doc)
        app.web_reader.fetch = lambda key, requested_url, **kwargs: WebPageResult(
            key=key,
            status="ok",
            url=requested_url,
            title="Example article",
            content="Launch Notes\n\nThis is the first paragraph of the article.",
            links=[WebLink(index=1, text="documentation", url="https://example.test/docs")],
            content_type="text/html",
        )
        async with app.run_test(size=(140, 45)) as pilot:
            await pilot.pause(0.2)
            reload_button = next(
                button for button in app.query(Button) if button.id and button.id.startswith("reload-web-")
            )
            reload_button.press()
            await pilot.pause(0.3)

            result = app.web_results[url]
            assert result.status == "ok"
            assert result.title == "Example article"
            assert "Launch Notes" in result.content
            assert len(result.links) == 1
            assert result.links[0].url.endswith("/docs")

    asyncio.run(scenario())


def test_contact_renderer_reads_local_vcard_file(tmp_path: Path) -> None:
    contacts_dir = tmp_path / "contacts"
    contacts_dir.mkdir()
    (contacts_dir / "sara.vcf").write_text(
        "\n".join(
            [
                "BEGIN:VCARD",
                "VERSION:3.0",
                "FN:Sara Chen",
                "EMAIL;TYPE=work:sara@example.com",
                "ORG:Northwind Labs",
                "TITLE:Finance Lead",
                "END:VCARD",
                "",
            ]
        ),
        encoding="utf-8",
    )
    doc = tmp_path / "contacts.folio"
    doc.write_text("::contact[contacts/sara.vcf]\n", encoding="utf-8")

    async def scenario() -> None:
        app = FolioApp(doc)
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.pause(0.2)
            widget = app.query_one(ContactWidget)
            assert len(widget.contacts) == 1
            assert widget.contacts[0].full_name == "Sara Chen"
            assert widget.contacts[0].emails == ["sara@example.com"]

    asyncio.run(scenario())


def test_contact_widget_edits_and_saves_vcard_file(tmp_path: Path) -> None:
    contacts_dir = tmp_path / "contacts"
    contacts_dir.mkdir()
    contact_path = contacts_dir / "sara.vcf"
    contact_path.write_text(
        "\n".join(
            [
                "BEGIN:VCARD",
                "VERSION:3.0",
                "FN:Sara Chen",
                "EMAIL;TYPE=work:sara@example.com",
                "ORG:Northwind Labs",
                "TITLE:Finance Lead",
                "END:VCARD",
                "",
            ]
        ),
        encoding="utf-8",
    )
    doc = tmp_path / "contacts.folio"
    doc.write_text("::contact[contacts/sara.vcf]\n", encoding="utf-8")

    async def scenario() -> None:
        app = FolioApp(doc)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.2)
            app.query_one("#contact-title-contacts-sara-vcf", Input).value = "VP Finance"
            app.query_one("#contact-emails-contacts-sara-vcf", Input).value = "sara@example.com, finance@example.com"
            app.query_one("#contact-note-contacts-sara-vcf", Input).value = "Budget owner"
            app.query_one("#save-contact-contacts-sara-vcf", Button).press()
            await pilot.pause(0.3)

    asyncio.run(scenario())

    updated = contact_path.read_text(encoding="utf-8")
    assert "TITLE:VP Finance" in updated
    assert "EMAIL;TYPE=internet:sara@example.com" in updated
    assert "EMAIL;TYPE=internet:finance@example.com" in updated
    assert "NOTE:Budget owner" in updated


def test_contact_widget_renders_and_saves_inline_contact_block(tmp_path: Path) -> None:
    doc = tmp_path / "contacts-inline.folio"
    doc.write_text(
        "\n".join(
            [
                "::contact[sara.chen]",
                "name = Sara Chen",
                "email = sara@example.com",
                "role = Head of Product",
                "org = Example Ltd",
                "phone = +44 7700 900123",
                "notes = Met at ProductCon 2025.",
                "::end",
                "",
            ]
        ),
        encoding="utf-8",
    )

    async def scenario() -> None:
        app = FolioApp(doc)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.2)
            widget = app.query_one(ContactWidget)
            assert widget.inline_source is True
            assert widget.contacts[0].full_name == "Sara Chen"
            app.query_one("#contact-role-sara-chen", Input).value = "Chief Product Officer"
            app.query_one("#contact-note-sara-chen", Input).value = "Prefers async communication."
            app.query_one("#save-contact-sara-chen", Button).press()
            await pilot.pause(0.3)

    asyncio.run(scenario())

    updated = doc.read_text(encoding="utf-8")
    assert "role = Chief Product Officer" in updated
    assert "notes = Prefers async communication." in updated


def test_email_widget_reads_maildir_and_runs_actions(tmp_path: Path) -> None:
    maildir_path = tmp_path / "mail"
    _seed_maildir(maildir_path)
    doc = tmp_path / "mail.folio"
    doc.write_text('::email[mail]{folder="Inbox" limit="10"}\n', encoding="utf-8")

    async def scenario() -> None:
        app = FolioApp(doc)
        async with app.run_test(size=(140, 45)) as pilot:
            await pilot.pause(0.2)
            widget = app.query_one(EmailWidget)
            assert len(widget.summaries) == 2
            assert widget.selected is not None
            first_subject = widget.selected.subject

            app.query_one(f"#email-read-{widget.key_fragment}", Button).press()
            await pilot.pause(0.2)
            widget = app.query_one(EmailWidget)
            assert widget.selected is not None
            assert "S" in widget.selected.flags

            app.query_one(f"#email-star-{widget.key_fragment}", Button).press()
            await pilot.pause(0.2)
            widget = app.query_one(EmailWidget)
            assert widget.selected is not None
            assert "F" in widget.selected.flags

            app.query_one(f"#email-archive-{widget.key_fragment}", Button).press()
            await pilot.pause(0.3)
            widget = app.query_one(EmailWidget)
            assert len(widget.summaries) == 1
            assert widget.selected is not None
            assert widget.selected.subject != first_subject

    asyncio.run(scenario())


def test_email_draft_saves_draft_and_updates_document(tmp_path: Path) -> None:
    maildir_path = tmp_path / "mail"
    _seed_maildir(maildir_path)
    doc = tmp_path / "compose.folio"
    doc.write_text(
        "\n".join(
            [
                '::email[draft]{path="mail" drafts-folder="Drafts" from="vijay@example.com" to="team@example.com" cc="" subject="Weekly briefing"}',
                "Please review the latest draft before noon.",
                "::end",
                "",
            ]
        ),
        encoding="utf-8",
    )

    async def scenario() -> None:
        app = FolioApp(doc)
        async with app.run_test(size=(140, 45)) as pilot:
            await pilot.pause(0.2)
            widget = app.query_one(EmailComposeWidget)
            app.query_one(f"#email-compose-subject-{widget.key_fragment}", Input).value = "Weekly briefing v2"
            body = app.query_one(f"#email-compose-body-{widget.key_fragment}", TextArea)
            body.load_text("Please review the updated draft.\nThanks.")
            await pilot.pause(0.1)
            app.query_one(f"#email-compose-save-{widget.key_fragment}", Button).press()
            await pilot.pause(0.3)

    asyncio.run(scenario())

    updated = doc.read_text(encoding="utf-8")
    assert 'draft-key="' in updated
    assert 'subject="Weekly briefing v2"' in updated
    assert "Please review the updated draft." in updated


def test_sh_run_writes_output_block_and_rerun_replaces_it(tmp_path: Path) -> None:
    doc = tmp_path / "runbook.folio"
    doc.write_text('::sh[check]{cmd="echo one" cwd=/tmp trust=author}\n', encoding="utf-8")

    results = [
        ShRunResult(
            key="check",
            command="echo one",
            cwd="/tmp",
            exit_code=0,
            stdout=["first run"],
            stderr=[],
            duration_seconds=0.2,
            timestamp="2026-04-10T12:00:00+00:00",
        ),
        ShRunResult(
            key="check",
            command="echo one",
            cwd="/tmp",
            exit_code=1,
            stdout=[],
            stderr=["second run failed"],
            duration_seconds=0.4,
            timestamp="2026-04-10T12:01:00+00:00",
        ),
    ]

    async def scenario() -> None:
        app = FolioApp(doc)
        app.sh_runner.run = lambda key, command, cwd=None: results.pop(0)
        async with app.run_test(size=(140, 45)) as pilot:
            await pilot.pause(0.2)
            app.query_one("#run-sh-check", Button).press()
            await pilot.pause(0.3)
            app.query_one("#run-sh-check", Button).press()
            await pilot.pause(0.3)

    asyncio.run(scenario())

    updated = doc.read_text(encoding="utf-8")
    assert updated.count("::sh-output[check]") == 1
    assert "second run failed" in updated
    assert "first run" not in updated
    assert 'exit=1' in updated


def test_sh_in_untrusted_document_requires_confirmation_before_execution(tmp_path: Path) -> None:
    doc = tmp_path / "untrusted.folio"
    doc.write_text('::sh[check]{cmd="echo one" cwd=/tmp trust=author}\n', encoding="utf-8")
    called = {"count": 0}

    async def scenario() -> None:
        app = FolioApp(doc, trusted_document=False)

        def fake_run(key, command, cwd=None):
            called["count"] += 1
            return ShRunResult(
                key=key,
                command=command,
                cwd=cwd or ".",
                exit_code=0,
                stdout=["ok"],
                stderr=[],
                duration_seconds=0.1,
                timestamp="2026-04-10T12:00:00+00:00",
            )

        app.sh_runner.run = fake_run
        async with app.run_test(size=(140, 45)) as pilot:
            await pilot.pause(0.2)
            run_button = app.query_one("#run-sh-check", Button)
            assert run_button.label.plain == "Run"
            run_button.press()
            await pilot.pause(0.2)
            assert called["count"] == 0
            assert "check" in app._pending_shell_confirmations
            confirm_button = app.query_one("#run-sh-check", Button)
            assert confirm_button.label.plain == "Confirm Run"
            confirm_button.press()
            await pilot.pause(0.3)

    asyncio.run(scenario())

    updated = doc.read_text(encoding="utf-8")
    assert called["count"] == 1
    assert "::sh-output[check]" in updated
