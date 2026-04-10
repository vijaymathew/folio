# Renderer Interface And Capability Registry

This note documents the current renderer authoring interface in Folio.

It is intended for people adding new directive renderers such as `::calendar`, `::chat`, or richer document-native widgets.

## Overview

Each renderer class now does three things:

1. points at an external TOML manifest via `manifest_path`
2. is registered through the capability registry
3. implements `render(directive, ctx) -> Widget`

The registry loads the TOML manifest, validates it into a `RendererManifest`, stores the original manifest source, and filters the runtime `RenderContext` down to the capabilities declared by that manifest.

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


class Renderer(Protocol):
    def render(self, directive: Directive, ctx: RenderContext) -> Widget: ...
```

`RenderContext` may provide:

- `events`: shared `EventBus` for semantic actions
- `py_results`: current `::py` evaluation results
- `document_path`: path of the current document
- `file_access`: restricted file access service for file-backed renderers
- `source_text`: current in-memory document buffer
- `directives_by_id`: directive lookup map for cross-reference use cases

But a renderer only receives the subset declared in its manifest capabilities. There are no ambient render-context fields.

## Registry Interface

The registry lives in [src/folio/core/registry.py](/home/vijay/Projects/folio/src/folio/core/registry.py).

```python
class CapabilityRegistry:
    def register(self, renderer_cls: type[Renderer]) -> None: ...
    def create(self, directive_type: str) -> Renderer | None: ...
    def renderer_for(self, directive_type: str) -> type[Renderer] | None: ...
    def manifest_for(self, directive_type: str) -> RendererManifest | None: ...
    def manifest_source_for(self, directive_type: str) -> str | None: ...
    def context_for(self, directive_type: str, base_ctx: RenderContext) -> RenderContext: ...
    def manifests(self) -> list[RendererManifest]: ...
    def supported_types(self) -> list[str]: ...
```

Current behavior:

- registration is class-based, not instance-based
- manifests are loaded from TOML, not built ad hoc in Python
- duplicate registration for the same directive type raises `ValueError`
- unknown directive types return `None`
- runtime context is filtered per directive type before `render(...)` is called

## Renderer Authoring Rules

When adding a renderer:

1. add a TOML manifest under `src/folio/renderers/manifests/`
2. define a renderer class with `manifest_path = ...`
3. implement `render(directive, ctx)`
4. return a Textual widget
5. emit semantic actions through `ctx.events`, not direct file edits
6. register the renderer class in the app

The widget must not be the source of truth. Any stateful interaction should end in an event that becomes a text mutation.

## Manifest Example

```toml
[renderer]
directive_type = "task"
display_name = "Task"
description = "Checkbox task widget with due dates and dependency metadata."
version = "1.0.0"
supports_inline_source = true
supports_editing = true

[[params]]
name = "done"
default = "\"false\""
description = "Whether the task is completed."

[[actions]]
name = "task.toggle"
description = "Toggle task completion."

[actions.payload_schema]
directive = "Directive"

[capabilities]
events = true
directive_lookup = true

[sandbox]
execution_mode = "in-process"
network = false
storage = false
document_text = false
```

## Capability Filtering

The registry enforces renderer capabilities by building a filtered `RenderContext` per directive type:

- `events`: allows semantic event emission
- `py_results`: allows reading `::py` worker results
- `directive_lookup`: allows cross-reference lookup by directive id
- `document_path`: exposes the current document path
- `filesystem_read`: exposes `ctx.file_access`
- `source_text`: exposes the full in-memory source buffer

This is the current runtime boundary for built-in renderers. It prevents ambient access to app state, but it is not equivalent to OS-level sandboxing for arbitrary third-party Python code running in-process.

## Minimal Example

```python
from pathlib import Path

from textual.widgets import Button, Static
from textual.containers import Vertical

from folio.core.models import Directive
from folio.renderers.base import RenderContext


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
    manifest_path = Path(__file__).with_name("manifests") / "counter.toml"

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
- [src/folio/renderers/manifests/](/home/vijay/Projects/folio/src/folio/renderers/manifests)

Use them as the current style guide for:

- manifest shape
- event naming
- widget composition
- capability declarations
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
- explicit capability declarations
- checked-in TOML source that can be inspected independently of Python code
- future docs/help generation
- future directive validation

It also drives runtime context filtering today. It does not yet provide full process isolation for every renderer; only `::py` currently executes in a separate hardened worker.
