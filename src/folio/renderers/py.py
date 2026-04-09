from __future__ import annotations

from textual.containers import Vertical
from textual.widgets import Button, Static

from folio.core.models import Directive
from folio.renderers.base import RenderContext


class PyRenderer:
    def render(self, directive: Directive, ctx: RenderContext) -> Static:
        code = "\n".join(directive.body) if directive.body else directive.header_line
        key = directive.id or str(directive.start_line)
        result = (ctx.py_results or {}).get(key)
        if result is None:
            output = "No result yet. Run the block to evaluate document context."
        elif result.status == "ok":
            output = "\n".join(result.stdout) if result.stdout else "(no output)"
        elif result.status == "manual":
            output = "Manual block. Press Run to evaluate."
        elif result.status == "blocked":
            output = result.error or "Skipped because an earlier Python block failed."
        else:
            output = result.error or "Python evaluation failed."

        widget = Vertical(
            Static(code, classes="py-code"),
            Button("Run", id=f"run-py-{key}"),
            Static(output, classes="py-output"),
        )
        widget.border_title = directive.title()
        return widget
