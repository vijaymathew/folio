from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from folio.core.models import Directive
from folio.renderers.base import RenderContext, RendererFileAccess


def _parse_int(raw: str | None, default: int) -> int:
    if raw is None:
        return default
    try:
        return max(1, int(raw.strip('"')))
    except ValueError:
        return default


class FileWidget(Vertical):
    def __init__(self, directive: Directive, resolved_path: Path, preview: str, lines: int, file_access: RendererFileAccess) -> None:
        super().__init__(classes="file-widget")
        self.directive = directive
        self.resolved_path = resolved_path
        self.preview = preview
        self.lines = lines
        self.file_access = file_access
        self.border_title = Text(directive.title())

    def compose(self) -> ComposeResult:
        yield Static(self._meta_text(), classes="file-meta", markup=False)
        yield Static(self._content_text(), classes="file-content", markup=False)

    def _meta_text(self) -> str:
        kind = "directory" if self.resolved_path.is_dir() else "file"
        return f"{kind}: {self.resolved_path}"

    def _content_text(self) -> str:
        if not self.resolved_path.exists():
            return f"Path not found: {self.resolved_path}"

        if self.resolved_path.is_dir():
            entries = self.file_access.list_dir(self.resolved_path)
            if not entries:
                return "(empty directory)"
            lines = []
            for entry in entries[: self.lines]:
                marker = "/" if entry.is_dir() else ""
                lines.append(f"{entry.name}{marker}")
            if len(entries) > self.lines:
                lines.append(f"... {len(entries) - self.lines} more")
            return "\n".join(lines)

        if self.preview not in {"auto", "text"}:
            return f"Preview mode '{self.preview}' is not implemented."

        data = self.file_access.read_bytes(self.resolved_path)
        if b"\0" in data:
            return f"Binary file ({len(data)} bytes)"

        text = data.decode("utf-8", errors="replace")
        lines = text.splitlines()
        preview_lines = lines[: self.lines]
        if not preview_lines:
            return "(empty file)"
        if len(lines) > self.lines:
            preview_lines.append(f"... {len(lines) - self.lines} more lines")
        return "\n".join(preview_lines)


class FileRenderer:
    manifest_path = Path(__file__).with_name("manifests") / "file.toml"

    def render(self, directive: Directive, ctx: RenderContext) -> Static:
        if ctx.file_access is None:
            return Static("Renderer capability denied: filesystem_read.", classes="file-widget")
        raw_path = directive.id or directive.params.get("path", '"unknown"').strip('"')
        preview = directive.params.get("preview", '"auto"').strip('"')
        lines = _parse_int(directive.params.get("lines"), 20)
        try:
            resolved = self._resolve_path(raw_path, ctx)
        except PermissionError as exc:
            return Static(str(exc), classes="file-widget")

        assert ctx.file_access is not None
        return FileWidget(directive, resolved, preview, lines, ctx.file_access)

    def _resolve_path(self, raw_path: str, ctx: RenderContext) -> Path:
        assert ctx.file_access is not None
        return ctx.file_access.resolve_document_relative(raw_path)
