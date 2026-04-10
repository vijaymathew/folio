from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Static

from folio.core.models import Directive, WebPageResult
from folio.core.web_reader import resolve_web_url
from folio.renderers.base import RenderContext, widget_id_fragment


def _parse_int(raw: str | None, default: int) -> int:
    if raw is None:
        return default
    try:
        return max(1, int(raw.strip('"')))
    except ValueError:
        return default


class WebWidget(Vertical):
    def __init__(self, directive: Directive, ctx: RenderContext, result: WebPageResult | None, lines: int) -> None:
        super().__init__(classes="web-widget")
        self.directive = directive
        self.ctx = ctx
        self.result = result
        self.lines = lines
        self.key_fragment = widget_id_fragment(directive.key())
        self.border_title = Text(directive.title())

    def compose(self) -> ComposeResult:
        with Horizontal(classes="web-toolbar"):
            yield Static(self._meta_text(), classes="web-meta", markup=False)
            yield Button("Reload", id=f"reload-web-{self.key_fragment}", compact=True, classes="web-reload")
        yield Static(self._content_text(), classes="web-content", markup=False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == f"reload-web-{self.key_fragment}" and self.ctx.events is not None:
            self.ctx.events.emit("web.reload", directive=self.directive)
            event.stop()

    def _meta_text(self) -> str:
        url = resolve_web_url(self.directive.id or self.directive.params.get("url", '"unknown"'))
        if self.result is None:
            return f"web reader: {url}"
        return f"{self.result.title} — {self.result.url}"

    def _content_text(self) -> str:
        load_mode = self.directive.params.get("load", '"auto"').strip('"')
        if self.result is None:
            return "Manual page. Press Reload to fetch." if load_mode == "manual" else "No page fetched yet."
        if self.result.status != "ok":
            return self.result.error or "Web fetch failed."

        lines = self.result.content.splitlines()
        body = "\n".join(lines[: self.lines]).strip()
        if len(lines) > self.lines:
            body += f"\n\n... {len(lines) - self.lines} more lines"

        if self.result.links:
            preview_links = self.result.links[: min(8, len(self.result.links))]
            link_lines = [f"[{link.index}] {link.text} — {link.url}" for link in preview_links]
            if len(self.result.links) > len(preview_links):
                link_lines.append(f"... {len(self.result.links) - len(preview_links)} more links")
            body = f"{body}\n\nLinks\n" + "\n".join(link_lines)

        return body or "(empty page)"


class WebRenderer:
    manifest_path = Path(__file__).with_name("manifests") / "web.toml"

    def render(self, directive: Directive, ctx: RenderContext) -> Static:
        result = (ctx.web_results or {}).get(directive.key())
        lines = _parse_int(directive.params.get("lines"), 40)
        return WebWidget(directive, ctx, result, lines)
