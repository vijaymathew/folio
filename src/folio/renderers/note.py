from __future__ import annotations

import re
from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from folio.core.models import Directive
from folio.renderers.base import RenderContext


def _slug(text: str) -> str:
    lowered = text.strip().lower()
    lowered = re.sub(r"[^a-z0-9]+", "-", lowered)
    return lowered.strip("-")


def _candidate_paths(raw_path: str, root: Path) -> list[Path]:
    base = root / Path(raw_path)
    candidates = [base]
    if base.suffix:
        return candidates
    candidates.extend(base.with_suffix(ext) for ext in (".md", ".folio", ".txt"))
    return candidates


class NoteWidget(Vertical):
    def __init__(self, directive: Directive, source_path: Path, content: str, status: str) -> None:
        super().__init__(classes="note-widget")
        self.directive = directive
        self.source_path = source_path
        self.content = content
        self.status = status
        self.border_title = Text(directive.title())

    def compose(self) -> ComposeResult:
        yield Static(f"source: {self.source_path}", classes="note-meta", markup=False)
        if self.status:
            yield Static(self.status, classes="note-status", markup=False)
        yield Static(self.content, classes="note-content", markup=False)


class NoteRenderer:
    manifest_path = Path(__file__).with_name("manifests") / "note.toml"

    def render(self, directive: Directive, ctx: RenderContext) -> Static:
        if ctx.file_access is None:
            return Static("Renderer capability denied: filesystem_read.", classes="note-widget")
        section = directive.params.get("section", '"full"').strip('"')
        try:
            source_path = self._resolve_source_path(directive, ctx)
        except PermissionError as exc:
            return Static(str(exc), classes="note-widget")
        if source_path is None:
            return Static("Note source not found.", classes="note-widget")

        if not source_path.exists():
            return Static(f"Note source not found: {source_path}", classes="note-widget")

        text = ctx.file_access.read_text(source_path)
        content, status = self._extract_section(text, section)
        return NoteWidget(directive, source_path, content, status)

    def _resolve_source_path(self, directive: Directive, ctx: RenderContext) -> Path | None:
        raw_path = directive.params.get("path")
        if raw_path is not None:
            explicit = raw_path.strip('"')
            return self._resolve_from_search_roots(explicit, ctx)

        if directive.id:
            return self._resolve_from_search_roots(directive.id, ctx)
        return None

    def _resolve_from_search_roots(self, raw_path: str, ctx: RenderContext) -> Path | None:
        if ctx.file_access is None:
            return None
        candidate = Path(raw_path).expanduser()
        if candidate.is_absolute():
            try:
                resolved = ctx.file_access.resolve_document_relative(str(candidate))
            except PermissionError:
                return None
            return resolved if resolved.exists() else None

        search_roots = ctx.file_access.search_roots()
        for root in search_roots:
            for path in _candidate_paths(raw_path, root):
                try:
                    resolved = ctx.file_access.resolve_document_relative(str(path))
                except PermissionError:
                    continue
                if resolved.exists():
                    return resolved
        return None

    def _extract_section(self, text: str, section: str) -> tuple[str, str]:
        if section == "full":
            return (text.strip() or "(empty note)", "")

        lines = text.splitlines()
        target_slug = _slug(section)
        match_index: int | None = None
        match_level: int | None = None

        for index, line in enumerate(lines):
            heading = self._parse_heading(line)
            if heading is None:
                continue
            level, title = heading
            if _slug(title) == target_slug:
                match_index = index
                match_level = level
                break

        if match_index is None or match_level is None:
            return (f"Section not found: {section}", "")

        body: list[str] = []
        for line in lines[match_index + 1 :]:
            heading = self._parse_heading(line)
            if heading is not None and heading[0] <= match_level:
                break
            body.append(line)

        content = "\n".join(body).strip()
        if not content:
            content = "(empty section)"
        return (content, f"section: {section}")

    def _parse_heading(self, line: str) -> tuple[int, str] | None:
        match = re.match(r"^(#{1,6})\s+(.*\S)\s*$", line)
        if not match:
            return None
        return (len(match.group(1)), match.group(2))
