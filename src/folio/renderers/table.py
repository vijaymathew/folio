from __future__ import annotations

from rich.table import Table
from textual.widgets import Static

from folio.core.models import Directive
from folio.renderers.base import RenderContext


class TableRenderer:
    def render(self, directive: Directive, ctx: RenderContext) -> Static:
        summary = directive.params.get("source", '"inline"').strip('"')
        if summary and ctx.py_results:
            result = ctx.py_results.get(summary)
            if result and result.table is not None:
                table = self._build_table(result.table)
                table.title = directive.title()
                return Static(table, classes="table-widget")
            if result and result.status == "error":
                return Static("Source block failed; table data unavailable.", classes="table-widget")
            if result and result.status == "manual":
                return Static("Source block is manual. Run it to materialize table rows.", classes="table-widget")
        return Static(f"{directive.title()}\nNo structured table rows available.", classes="table-widget")

    def _build_table(self, rows: list[dict[str, object]]) -> Table:
        table = Table(expand=True, show_lines=False)
        if not rows:
            table.add_column("value")
            table.add_row("(empty)")
            return table

        columns: list[str] = []
        for row in rows:
            for key in row.keys():
                if key not in columns:
                    columns.append(key)

        for column in columns:
            table.add_column(column, overflow="fold")

        for row in rows:
            table.add_row(*(str(row.get(column, "—")) for column in columns))

        return table
