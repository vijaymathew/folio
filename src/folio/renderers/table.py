from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.coordinate import Coordinate
from textual.widgets import DataTable, Static

from folio.core.models import Directive
from folio.renderers.base import ActionSpec, ParamSpec, RenderContext, RendererManifest, widget_id_fragment


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
        self.editing_cell: tuple[int, int] | None = None
        self.edit_buffer = ""
        self.original_value = ""
        self.key_fragment = widget_id_fragment(directive.key())

    def compose(self) -> ComposeResult:
        yield Static(self.directive.title(), classes="table-title")
        yield DataTable(id=f"table-grid-{self.key_fragment}")
        yield Static("Arrow keys move. Type to edit the highlighted cell. Enter saves. Esc cancels.", id="table-edit-status")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.cursor_type = "cell"
        table.zebra_stripes = True
        for column in self.columns:
            table.add_column(column)
        for row in self.rows:
            table.add_row(*(self._display_value(row, column) for column in self.columns))
        if self.rows and self.columns:
            self._set_active_cell(0, 0)
        table.focus()

    def on_data_table_cell_highlighted(self, event: DataTable.CellHighlighted) -> None:
        self._set_active_cell(event.coordinate.row, event.coordinate.column)

    def on_data_table_cell_selected(self, event: DataTable.CellSelected) -> None:
        self._set_active_cell(event.coordinate.row, event.coordinate.column)

    def _set_active_cell(self, row_index: int, column_index: int) -> None:
        if self.editing_cell is not None and self.editing_cell != (row_index, column_index):
            self._cancel_edit()
        self.selected = (row_index, column_index)
        column = self.columns[column_index]
        self.query_one("#table-edit-status", Static).update(
            f"{column} row {row_index + 1}. Type to edit. Enter saves. Esc cancels."
        )

    def on_key(self, event: events.Key) -> None:
        table = self.query_one(DataTable)
        if not table.has_focus:
            return

        if event.key == "enter" and self.editing_cell is not None:
            self._commit_edit()
            event.stop()
            return

        if event.key == "escape" and self.editing_cell is not None:
            self._cancel_edit()
            event.stop()
            return

        if event.key == "backspace":
            self._delete_last_character()
            event.stop()
            return

        if event.key == "delete":
            self._clear_active_cell()
            event.stop()
            return

        if event.is_printable and event.character is not None:
            self._append_character(event.character)
            event.stop()

    def _append_character(self, character: str) -> None:
        coordinate = self._active_coordinate()
        if coordinate is None:
            return

        if self.editing_cell != coordinate:
            self._begin_edit(coordinate, replace=True)

        self.edit_buffer += character
        self._update_visible_edit_buffer()

    def _delete_last_character(self) -> None:
        coordinate = self._active_coordinate()
        if coordinate is None:
            return

        if self.editing_cell != coordinate:
            self._begin_edit(coordinate, replace=False)

        self.edit_buffer = self.edit_buffer[:-1]
        self._update_visible_edit_buffer()

    def _clear_active_cell(self) -> None:
        coordinate = self._active_coordinate()
        if coordinate is None:
            return

        if self.editing_cell != coordinate:
            self._begin_edit(coordinate, replace=False)

        self.edit_buffer = ""
        self._update_visible_edit_buffer()

    def _begin_edit(self, coordinate: tuple[int, int], *, replace: bool) -> None:
        row_index, column_index = coordinate
        column = self.columns[column_index]
        current_value = self.rows[row_index].get(column, "")
        self.editing_cell = coordinate
        self.original_value = "" if current_value == "—" else str(current_value)
        self.edit_buffer = "" if replace else self.original_value
        self._update_status(editing=True)

    def _commit_edit(self) -> None:
        if self.ctx.events is None or self.editing_cell is None:
            return

        row_index, column_index = self.editing_cell
        column = self.columns[column_index]
        value = _coerce_value(self.edit_buffer)
        self.rows[row_index][column] = value
        self._update_grid_cell(self.editing_cell, str(value))
        self._reset_edit_state()
        self.ctx.events.emit(
            "table.edit",
            directive=self.directive,
            rows=deepcopy(self.rows),
        )
        self._update_status()

    def _cancel_edit(self) -> None:
        if self.editing_cell is None:
            return

        row_index, column_index = self.editing_cell
        column = self.columns[column_index]
        self._update_grid_cell(self.editing_cell, self._display_value(self.rows[row_index], column))
        self._reset_edit_state()
        self._update_status()

    def _update_visible_edit_buffer(self) -> None:
        if self.editing_cell is None:
            return
        self._update_grid_cell(self.editing_cell, self.edit_buffer)
        self._update_status(editing=True)

    def _update_grid_cell(self, coordinate: tuple[int, int], value: str) -> None:
        table = self.query_one(DataTable)
        table.update_cell_at(Coordinate(*coordinate), value, update_width=True)

    def _update_status(self, *, editing: bool = False) -> None:
        coordinate = self._active_coordinate()
        if coordinate is None:
            return
        row_index, column_index = coordinate
        column = self.columns[column_index]
        status = self.query_one("#table-edit-status", Static)
        if editing:
            status.update(
                f"Editing {column} row {row_index + 1}: {self.edit_buffer!r}. Enter saves. Esc cancels."
            )
            return
        status.update(f"{column} row {row_index + 1}. Type to edit. Enter saves. Esc cancels.")

    def _active_coordinate(self) -> tuple[int, int] | None:
        if self.selected is not None:
            return self.selected
        table = self.query_one(DataTable)
        coordinate = table.cursor_coordinate
        return (coordinate.row, coordinate.column)

    def _reset_edit_state(self) -> None:
        self.editing_cell = None
        self.edit_buffer = ""
        self.original_value = ""

    def _collect_columns(self, rows: list[dict[str, object]]) -> list[str]:
        columns: list[str] = []
        for row in rows:
            for key in row.keys():
                if key not in columns:
                    columns.append(key)
        return columns or ["value"]

    def _display_value(self, row: dict[str, object], column: str) -> str:
        value = row.get(column, "—")
        return str(value)


class TableRenderer:
    manifest = RendererManifest(
        directive_type="table",
        display_name="Table",
        description="Structured table renderer with direct in-cell editing.",
        params=[
            ParamSpec("source", description="Source ::py block key for structured rows."),
            ParamSpec("editable", default='"false"', description="Whether the table can be edited."),
            ParamSpec("sortable", default='"false"', description="Reserved flag for table sorting support."),
        ],
        actions=[
            ActionSpec(
                "table.edit",
                "Commit an edited table back to document text.",
                {
                    "directive": "Directive",
                    "rows": "list[dict[str, object]]",
                },
            )
        ],
        supports_inline_source=True,
        supports_editing=True,
    )

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
