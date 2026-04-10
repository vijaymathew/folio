# Renderer Interface And Capability Registry

This note documents the current renderer authoring interface in Folio.

It is intended for people adding new directive renderers such as `::calendar`, `::chat`, or richer document-native widgets.

## Overview

Each renderer class does two things:

1. declares a `manifest`
2. implements `render(directive, ctx) -> Widget`

The registry stores renderer classes by directive type and exposes their manifests for introspection.

## Core Types

The interface lives in [src/folio/renderers/base.py](/home/vijay/Projects/folio/src/folio/renderers/base.py).

```python
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
```

`RenderContext` currently provides:

- `events`: shared `EventBus` for semantic actions
- `py_results`: current `::py` evaluation results
- `document_path`: path of the current document
- `directives_by_id`: directive lookup map for cross-reference use cases

## Registry Interface

The registry lives in [src/folio/core/registry.py](/home/vijay/Projects/folio/src/folio/core/registry.py).

```python
class CapabilityRegistry:
    def register(self, renderer_cls: type[Renderer]) -> None: ...
    def create(self, directive_type: str) -> Renderer | None: ...
    def renderer_for(self, directive_type: str) -> type[Renderer] | None: ...
    def manifest_for(self, directive_type: str) -> RendererManifest | None: ...
    def manifests(self) -> list[RendererManifest]: ...
    def supported_types(self) -> list[str]: ...
```

Current behavior:

- registration is class-based, not instance-based
- `directive_type` comes from `renderer_cls.manifest.directive_type`
- duplicate registration for the same directive type raises `ValueError`
- unknown directive types return `None`

## Renderer Authoring Rules

When adding a renderer:

1. define a renderer class with a `manifest`
2. implement `render(directive, ctx)`
3. return a Textual widget
4. emit semantic actions through `ctx.events`, not direct file edits
5. register the renderer class in the app

The widget must not be the source of truth. Any stateful interaction should end in an event that becomes a text mutation.

## Minimal Example

```python
from textual.widgets import Button, Static
from textual.containers import Vertical

from folio.core.models import Directive
from folio.renderers.base import (
    ActionSpec,
    ParamSpec,
    RenderContext,
    RendererManifest,
)


class CounterWidget(Vertical):
    def __init__(self, directive: Directive, ctx: RenderContext) -> None:
        super().__init__()
        self.directive = directive
        self.ctx = ctx

    def compose(self):
        yield Static("Counter placeholder")
        yield Button("Increment", id=f"increment-{self.directive.key()}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if self.ctx.events is not None:
            self.ctx.events.emit("counter.increment", directive=self.directive)


class CounterRenderer:
    manifest = RendererManifest(
        directive_type="counter",
        display_name="Counter",
        description="Simple counter widget.",
        params=[
            ParamSpec("value", default='"0"', description="Current counter value."),
        ],
        actions=[
            ActionSpec(
                "counter.increment",
                "Increment the counter value.",
                {"directive": "Directive"},
            )
        ],
        supports_inline_source=True,
        supports_editing=True,
    )

    def render(self, directive: Directive, ctx: RenderContext):
        return CounterWidget(directive, ctx)
```

And registration:

```python
registry.register(CounterRenderer)
```

## Existing Examples

Current renderers are good reference points:

- [src/folio/renderers/task.py](/home/vijay/Projects/folio/src/folio/renderers/task.py)
- [src/folio/renderers/py.py](/home/vijay/Projects/folio/src/folio/renderers/py.py)
- [src/folio/renderers/table.py](/home/vijay/Projects/folio/src/folio/renderers/table.py)
- [src/folio/renderers/note.py](/home/vijay/Projects/folio/src/folio/renderers/note.py)
- [src/folio/renderers/file.py](/home/vijay/Projects/folio/src/folio/renderers/file.py)

Use them as the current style guide for:

- manifest shape
- event naming
- widget composition
- document-relative resolution patterns
- mutation-through-events discipline

## Event Naming

The current convention is:

- `task.toggle`
- `py.run`
- `table.edit`

Use a `directive.action` shape for new renderer actions unless there is a strong reason not to.

## What The Manifest Is For

Today the manifest supports:

- renderer discovery
- supported-type listing
- action and param introspection
- future docs/help generation
- future directive validation

It does not yet drive automatic forms or parser validation, but it is designed so that Folio can grow in that direction without changing every renderer again.
