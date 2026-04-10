from __future__ import annotations

import re
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
class RendererManifest:
    directive_type: str
    display_name: str
    description: str
    params: list[ParamSpec] = field(default_factory=list)
    actions: list[ActionSpec] = field(default_factory=list)
    supports_inline_source: bool = False
    supports_editing: bool = False


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
