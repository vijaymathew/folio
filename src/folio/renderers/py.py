from __future__ import annotations

from rich.text import Text
from textual.containers import Vertical
from textual.widgets import Button, Static

from folio.core.models import Directive
from folio.renderers.base import RenderContext


class PyBlockWidget(Vertical):
    def __init__(
        self,
        directive: Directive,
        ctx: RenderContext,
        output: str,
        key: str,
        code: str,
        run_mode: str,
    ) -> None:
        super().__init__(classes="py-block")
        self.directive = directive
        self.ctx = ctx
        self.output = output
        self.key = key
        self.code = code
        self.run_mode = run_mode
        self.border_title = Text(f"{directive.title()} [{run_mode}]")

    def compose(self):
        if self.run_mode == "manual":
            yield Button("Run", id=f"run-py-{self.key}", compact=True, classes="py-run")
        yield Static(self.code, classes="py-code", markup=False)
        yield Static(self.output, classes="py-output", markup=False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == f"run-py-{self.key}" and self.ctx.events is not None:
            self.ctx.events.emit("py.run", directive=self.directive)
            event.stop()


class PyRenderer:
    def render(self, directive: Directive, ctx: RenderContext) -> Static:
        code = "\n".join(directive.body) if directive.body else directive.header_line
        key = directive.key()
        run_mode = directive.params.get("run", '"manual"').strip('"')
        result = (ctx.py_results or {}).get(key)
        if result is None:
            output = "No result yet. Run the block to evaluate document context."
        elif result.status == "ok":
            extras = []
            if result.table is not None:
                extras.append(f"[table captured: {len(result.table)} rows]")
            stdout = "\n".join(result.stdout) if result.stdout else "(no output)"
            output = "\n".join([stdout, *extras]) if extras else stdout
        elif result.status == "manual":
            output = "Manual block. Press Run to evaluate."
        elif result.status == "blocked":
            output = result.error or "Skipped because an earlier Python block failed."
        else:
            output = result.error or "Python evaluation failed."

        return PyBlockWidget(directive, ctx, output, key, code, run_mode)
