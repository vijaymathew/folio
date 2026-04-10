from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from textual.widget import Widget

from folio.core.events import EventBus
from folio.core.models import Directive, PyBlockResult


@dataclass(slots=True)
class RenderContext:
    events: EventBus | None = None
    py_results: dict[str, PyBlockResult] | None = None
    document_path: Path | None = None
    directives_by_id: dict[str, Directive] | None = None


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
class RendererManifest:
    directive_type: str
    display_name: str
    description: str
    params: list[ParamSpec] = field(default_factory=list)
    actions: list[ActionSpec] = field(default_factory=list)
    supports_inline_source: bool = False
    supports_editing: bool = False


class Renderer(Protocol):
    manifest: RendererManifest

    def render(self, directive: Directive, ctx: RenderContext) -> Widget: ...
