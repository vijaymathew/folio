from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Input, Static

from folio.core.models import Directive
from folio.renderers.base import RenderContext


def _coerce_value(raw: str) -> object:
    text = raw.strip()
    if text.lower() == "true":
        return True
    if text.lower() == "false":
        return False
    if text.lower() == "null":
        return None
    try:
        if "." in text:
            return float(text)
        return int(text)
    except ValueError:
        return text


class TableEditor(Vertical):
    def __init__(self, directive: Directive, rows: list[dict[str, object]], ctx: RenderContext) -> None:
        super().__init__(classes="table-editor")
        self.directive = directive
        self.rows = deepcopy(rows)
        self.ctx = ctx
        self.columns = self._collect_columns(rows)
        self.selected: tuple[int, int] | None = None

    def compose(self) -> ComposeResult:
        yield Static(self.directive.title(), classes="table-title")
        yield DataTable(id=f"table-grid-{self.directive.id or self.directive.start_line}")
        yield Static("Select a cell to edit.", id="table-edit-status")
        with Horizontal(classes="table-editor-input-row"):
            yield Input(placeholder="New cell value", id="table-edit-input")
            yield Button("Apply", id="table-apply")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.cursor_type = "cell"
        table.zebra_stripes = True
        for column in self.columns:
            table.add_column(column)
        for row in self.rows:
            table.add_row(*(str(row.get(column, "—")) for column in self.columns))
        if self.rows and self.columns:
            self._set_active_cell(0, 0)

    def on_data_table_cell_highlighted(self, event: DataTable.CellHighlighted) -> None:
        self._set_active_cell(event.coordinate.row, event.coordinate.column)

    def on_data_table_cell_selected(self, event: DataTable.CellSelected) -> None:
        self._set_active_cell(event.coordinate.row, event.coordinate.column)

    def _set_active_cell(self, row_index: int, column_index: int) -> None:
        self.selected = (row_index, column_index)
        column = self.columns[column_index]
        value = self.rows[row_index].get(column, "")
        self.query_one("#table-edit-status", Static).update(f"Editing {column} at row {row_index + 1}")
        edit_input = self.query_one("#table-edit-input", Input)
        edit_input.value = str(value)
        edit_input.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "table-edit-input":
            self._apply_edit()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "table-apply":
            self._apply_edit()

    def _apply_edit(self) -> None:
        if self.ctx.update_table is None:
            return
        if self.selected is None:
            table = self.query_one(DataTable)
            coordinate = table.cursor_coordinate
            self._set_active_cell(coordinate.row, coordinate.column)

        row_index, column_index = self.selected
        column = self.columns[column_index]
        raw = self.query_one("#table-edit-input", Input).value
        self.rows[row_index][column] = _coerce_value(raw)
        self.ctx.update_table(self.directive, deepcopy(self.rows))

    def _collect_columns(self, rows: list[dict[str, object]]) -> list[str]:
        columns: list[str] = []
        for row in rows:
            for key in row.keys():
                if key not in columns:
                    columns.append(key)
        return columns or ["value"]


class TableRenderer:
    def render(self, directive: Directive, ctx: RenderContext) -> Static:
        rows = self._rows_from_directive(directive)
        if rows is None:
            source = directive.params.get("source", '"inline"').strip('"')
            if source and ctx.py_results:
                result = ctx.py_results.get(source)
                if result and result.table is not None:
                    rows = result.table
                elif result and result.status == "error":
                    return Static("Source block failed; table data unavailable.", classes="table-widget")
                elif result and result.status == "manual":
                    return Static("Source block is manual. Run it to materialize table rows.", classes="table-widget")

        if rows is None:
            return Static(f"{directive.title()}\nNo structured table rows available.", classes="table-widget")

        return TableEditor(directive, rows, ctx)

    def _rows_from_directive(self, directive: Directive) -> list[dict[str, object]] | None:
        if not directive.body:
            return None

        rows: list[dict[str, object]] = []
        for line in directive.body:
            stripped = line.strip()
            if not stripped:
                continue
            parsed = json.loads(stripped)
            if isinstance(parsed, dict):
                rows.append(parsed)
            else:
                rows.append({"value": parsed})
        return rows or None
