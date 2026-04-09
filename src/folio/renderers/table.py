from __future__ import annotations

from textual.widgets import Static

from folio.core.models import Directive
from folio.renderers.base import RenderContext


class TableRenderer:
    def render(self, directive: Directive, ctx: RenderContext) -> Static:
        summary = directive.params.get("source", '"inline"').strip('"')
        lines = [f"Table renderer placeholder", f"source={summary}"]
        if summary and ctx.py_results:
            result = ctx.py_results.get(summary)
            if result and result.context:
                exported = ", ".join(sorted(result.context.keys()))
                lines.append(f"exported context: {exported}")
            elif result and result.status == "error":
                lines.append("source block failed; table context unavailable")
        return Static("\n".join(lines), classes="table-widget")
