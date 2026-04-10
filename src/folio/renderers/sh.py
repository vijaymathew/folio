from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Static

from folio.core.models import Directive
from folio.renderers.base import RenderContext, widget_id_fragment


class ShWidget(Vertical):
    def __init__(self, directive: Directive, ctx: RenderContext) -> None:
        super().__init__(classes="sh-widget")
        self.directive = directive
        self.ctx = ctx
        self.key_fragment = widget_id_fragment(directive.key())
        self.border_title = Text(directive.title())

    def compose(self) -> ComposeResult:
        with Horizontal(classes="sh-toolbar"):
            yield Static(self._meta_text(), classes="sh-meta", markup=False)
            yield Button(self._button_label(), id=f"run-sh-{self.key_fragment}", compact=True, classes="sh-run")
        yield Static(self._command_text(), classes="sh-command", markup=False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == f"run-sh-{self.key_fragment}" and self.ctx.events is not None:
            self.ctx.events.emit("sh.run", directive=self.directive)
            event.stop()

    def _meta_text(self) -> str:
        trust = self.directive.params.get("trust", '"review-before-running"').strip('"')
        cwd = self.directive.params.get("cwd", '""').strip('"') or "."
        state = "trusted" if self.ctx.document_trusted else "untrusted"
        return f"{state} doc | trust={trust} | cwd={cwd}"

    def _button_label(self) -> str:
        pending = self.directive.key() in (self.ctx.pending_shell_confirmations or set())
        if pending:
            return "Confirm Run"
        if self._has_output():
            return "Re-run"
        return "Run"

    def _command_text(self) -> str:
        command = self.directive.params.get("cmd", '""').strip('"')
        return command or "(missing cmd)"

    def _has_output(self) -> bool:
        if self.ctx.directive_find is None:
            return False
        return self.ctx.directive_find("sh-output", self.directive.key()) is not None


class ShOutputWidget(Vertical):
    def __init__(self, directive: Directive) -> None:
        stdout, stderr = self._parse_body(directive.body)
        classes = "sh-output-widget"
        if directive.params.get("exit", "0") != "0" or stderr:
            classes += " advisory-error"
        super().__init__(classes=classes)
        self.directive = directive
        self.stdout = stdout
        self.stderr = stderr
        self.border_title = Text(directive.title())

    def compose(self) -> ComposeResult:
        with Horizontal(classes="sh-output-meta"):
            yield Static(self._summary_text(), classes="sh-output-summary", markup=False)
            yield Static(f"exit {self.directive.params.get('exit', '0')}", classes="sh-output-exit", markup=False)
        yield Static("\n".join(self.stdout) or "(no stdout)", classes="sh-stdout", markup=False)
        if self.stderr:
            yield Static("\n".join(self.stderr), classes="sh-stderr", markup=False)

    def _summary_text(self) -> str:
        duration = self.directive.params.get("duration", '"?"').strip('"')
        ts = self.directive.params.get("ts", '"unknown"').strip('"')
        return f"ts={ts} | duration={duration}"

    def _parse_body(self, lines: list[str]) -> tuple[list[str], list[str]]:
        section = "stdout"
        stdout: list[str] = []
        stderr: list[str] = []
        for line in lines:
            if line.strip() == "[stdout]":
                section = "stdout"
                continue
            if line.strip() == "[stderr]":
                section = "stderr"
                continue
            if section == "stderr":
                stderr.append(line)
            else:
                stdout.append(line)
        while stdout and stdout[-1] == "":
            stdout.pop()
        while stderr and stderr[-1] == "":
            stderr.pop()
        return stdout, stderr


class ShRenderer:
    manifest_path = Path(__file__).with_name("manifests") / "sh.toml"

    def render(self, directive: Directive, ctx: RenderContext) -> Static:
        return ShWidget(directive, ctx)


class ShOutputRenderer:
    manifest_path = Path(__file__).with_name("manifests") / "sh-output.toml"

    def render(self, directive: Directive, ctx: RenderContext) -> Static:
        return ShOutputWidget(directive)
