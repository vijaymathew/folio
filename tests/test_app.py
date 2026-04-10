from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

from folio.renderers.table import TableEditor
from folio.ui.document_view import DocumentView
from folio.ui.app import FolioApp
from textual.widgets import Button, DataTable


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
            app.query_one("#run-py-budget-check", Button).press()
            await pilot.pause(0.2)
            tables = list(app.query(TableEditor))
            assert len(tables) == 1
            assert len(tables[0].rows) == 4

    asyncio.run(scenario())


def test_table_edit_updates_document_text(tmp_path: Path) -> None:
    source = Path("/home/vijay/Projects/folio/docs/example.folio")
    doc = tmp_path / "example.folio"
    shutil.copyfile(source, doc)

    async def scenario() -> None:
        app = FolioApp(doc)
        async with app.run_test(size=(140, 45)) as pilot:
            await pilot.pause(0.2)
            app.query_one("#run-py-budget-check", Button).press()
            await pilot.pause(0.2)
            table = app.query_one(TableEditor)
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
