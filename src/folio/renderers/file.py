from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from folio.core.models import Directive
from folio.renderers.base import RenderContext


def _parse_int(raw: str | None, default: int) -> int:
    if raw is None:
        return default
    try:
        return max(1, int(raw.strip('"')))
    except ValueError:
        return default


class FileWidget(Vertical):
    def __init__(self, directive: Directive, resolved_path: Path, preview: str, lines: int) -> None:
        super().__init__(classes="file-widget")
        self.directive = directive
        self.resolved_path = resolved_path
        self.preview = preview
        self.lines = lines
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
            entries = sorted(self.resolved_path.iterdir(), key=lambda entry: (entry.is_file(), entry.name.lower()))
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

        data = self.resolved_path.read_bytes()
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
    def render(self, directive: Directive, ctx: RenderContext) -> Static:
        raw_path = directive.id or directive.params.get("path", '"unknown"').strip('"')
        preview = directive.params.get("preview", '"auto"').strip('"')
        lines = _parse_int(directive.params.get("lines"), 20)
        resolved = self._resolve_path(raw_path, ctx)

        return FileWidget(directive, resolved, preview, lines)

    def _resolve_path(self, raw_path: str, ctx: RenderContext) -> Path:
        candidate = Path(raw_path).expanduser()
        if candidate.is_absolute():
            return candidate

        search_roots: list[Path] = []
        if ctx.document_path is not None:
            base_dir = ctx.document_path.parent.resolve()
            search_roots.append(base_dir)
            search_roots.extend(base_dir.parents)
        search_roots.append(Path.cwd())

        seen: set[Path] = set()
        for root in search_roots:
            if root in seen:
                continue
            seen.add(root)
            resolved = (root / candidate).resolve()
            if resolved.exists():
                return resolved

        first_root = search_roots[0] if search_roots else Path.cwd()
        return (first_root / candidate).resolve()
