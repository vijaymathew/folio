from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

from folio.renderers.table import TableEditor
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
