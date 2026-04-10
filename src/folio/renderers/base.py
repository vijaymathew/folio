from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from textual.widget import Widget

from folio.core.events import EventBus
from folio.core.models import Directive, PyBlockResult


@dataclass(slots=True)
class RendererFileAccess:
    document_path: Path | None = None

    def resolve_document_relative(self, raw_path: str) -> Path:
        candidate = Path(raw_path).expanduser()
        if candidate.is_absolute():
            resolved = candidate.resolve()
            if self._is_allowed(resolved):
                return resolved
            raise PermissionError(f"path '{resolved}' is outside renderer file-access roots")

        search_roots = self.search_roots()
        for root in search_roots:
            resolved = (root / candidate).resolve()
            if resolved.exists() and self._is_allowed(resolved):
                return resolved

        first_root = search_roots[0] if search_roots else Path.cwd()
        fallback = (first_root / candidate).resolve()
        if not self._is_allowed(fallback):
            raise PermissionError(f"path '{fallback}' is outside renderer file-access roots")
        return fallback

    def read_text(self, path: Path) -> str:
        resolved = self._guard(path)
        return resolved.read_text(encoding="utf-8", errors="replace")

    def read_bytes(self, path: Path) -> bytes:
        resolved = self._guard(path)
        return resolved.read_bytes()

    def list_dir(self, path: Path) -> list[Path]:
        resolved = self._guard(path)
        return sorted(resolved.iterdir(), key=lambda entry: (entry.is_file(), entry.name.lower()))

    def _guard(self, path: Path) -> Path:
        resolved = path.resolve()
        if not self._is_allowed(resolved):
            raise PermissionError(f"path '{resolved}' is outside renderer file-access roots")
        return resolved

    def _is_allowed(self, path: Path) -> bool:
        for root in self.search_roots():
            try:
                path.relative_to(root)
                return True
            except ValueError:
                continue
        return False

    def search_roots(self) -> list[Path]:
        roots: list[Path] = []
        if self.document_path is not None:
            base_dir = self.document_path.parent.resolve()
            roots.append(base_dir)
            roots.extend(base_dir.parents)
        roots.append(Path.cwd().resolve())

        deduped: list[Path] = []
        seen: set[Path] = set()
        for root in roots:
            if root in seen:
                continue
            seen.add(root)
            deduped.append(root)
        return deduped


@dataclass(slots=True)
class RenderContext:
    events: EventBus | None = None
    py_results: dict[str, PyBlockResult] | None = None
    document_path: Path | None = None
    file_access: RendererFileAccess | None = None
    source_text: str | None = None
    directives_by_id: dict[str, Directive] | None = None
    directive_source_view: set[str] | None = None
    advisories: list[AdvisorySpec] | None = None
    single_pane_mode: bool = False


@dataclass(slots=True)
class ParamSpec:
    name: str
    required: bool = False
    default: str | None = None
    description: str = ""


@dataclass(slots=True)
class ActionSpec:
    name: str
    description: str
    payload_schema: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class CapabilitySpec:
    events: bool = False
    py_results: bool = False
    document_path: bool = False
    source_text: bool = False
    directive_lookup: bool = False
    filesystem_read: bool = False


@dataclass(slots=True)
class SandboxSpec:
    execution_mode: str = "in-process"
    network: bool = False
    storage: bool = False
    document_text: bool = False
    notes: str = ""


@dataclass(slots=True)
class RendererManifest:
    directive_type: str
    display_name: str
    description: str
    version: str = "1.0.0"
    params: list[ParamSpec] = field(default_factory=list)
    actions: list[ActionSpec] = field(default_factory=list)
    capabilities: CapabilitySpec = field(default_factory=CapabilitySpec)
    sandbox: SandboxSpec = field(default_factory=SandboxSpec)
    supports_inline_source: bool = False
    supports_editing: bool = False
    manifest_path: Path | None = None


@dataclass(slots=True)
class AdvisoryAction:
    key: str
    label: str
    event_name: str
    payload: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class AdvisorySpec:
    id: str
    title: str
    message: str
    actions: list[AdvisoryAction] = field(default_factory=list)
    level: str = "info"


class Renderer(Protocol):
    manifest: RendererManifest

    def render(self, directive: Directive, ctx: RenderContext) -> Widget: ...


_INVALID_WIDGET_ID_CHARS = re.compile(r"[^A-Za-z0-9_-]+")
_DASH_RUNS = re.compile(r"-{2,}")


def widget_id_fragment(value: str) -> str:
    fragment = _INVALID_WIDGET_ID_CHARS.sub("-", value.strip())
    fragment = _DASH_RUNS.sub("-", fragment).strip("-")
    if not fragment:
        return "id"
    if fragment[0].isdigit():
        return f"id-{fragment}"
    return fragment
