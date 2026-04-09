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
    def render(self, directive: Directive, ctx: RenderContext) -> Static:
        section = directive.params.get("section", '"full"').strip('"')
        source_path = self._resolve_source_path(directive, ctx)
        if source_path is None:
            return Static("Note source not found.", classes="note-widget")

        if not source_path.exists():
            return Static(f"Note source not found: {source_path}", classes="note-widget")

        text = source_path.read_text(encoding="utf-8", errors="replace")
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
            for path in _candidate_paths(raw_path, root):
                if path.exists():
                    return path.resolve()
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
