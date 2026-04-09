# Folio Console Renderer: Technology Choice And Minimal Architecture

## Recommendation

Build the first console implementation in **Python with Textual**.

Why this is the best fit:

- The architecture already centers `::py` as the computation layer, so Python is the natural host language.
- Textual provides the terminal primitives this design needs: buttons, inputs, checkboxes, tables, scrollable panes, keyboard focus, and reactive updates.
- The document model is text-first and renderer-second, which suits a TUI well. Unsupported directives can degrade cleanly to readable raw text.
- It is the fastest path to validating the strongest part of the architecture: tasks, Python blocks, tables, transclusion, local files, and mutation logging.

## Alternative

If the priority is long-term systems robustness rather than fastest iteration, use:

- **Rust**
- **ratatui**
- **crossterm**

That stack is stronger for performance and distribution, but it slows down initial iteration and still leaves `::py` best implemented as an external Python runtime.

## What To Build First

The first serious milestone should support only document-owned state:

- `::task`
- `::py`
- `::table`
- `::note`
- `::file`

Do **not** start with:

- email
- calendar
- chat
- browser/web clipping
- OAuth-heavy integrations
- multi-device sync
- plugin marketplace

Those are renderer and backend problems. The core claim should be validated first where the document can genuinely be the source of truth.

## Minimal Runtime Architecture

```text
[ Text File ]
     ↓
[ DocumentStore ]
     ↓
[ DirectiveParser ] → [ Directive Index ]
     ↓
[ Render Engine ] ↔ [ Textual UI ]
     ↓
[ Renderer Registry ]
     ↓
[ task | py | table | note | file renderers ]
     ↓
[ Mutation Engine ]
     ↓
[ Updated Text File ]
```

## Core Modules

Suggested structure:

```text
folio/
  src/
    core/
      DocumentStore.py
      DirectiveParser.py
      CapabilityRegistry.py
      MutationEngine.py
      EventBus.py
      models.py
    ui/
      App.py
      DocumentView.py
      SourcePane.py
      MutationLog.py
    renderers/
      base.py
      TaskRenderer.py
      PyRenderer.py
      TableRenderer.py
      NoteRenderer.py
      FileRenderer.py
    python/
      PyWorker.py
```

## Responsibilities

### DocumentStore

- Loads and saves the text file.
- Tracks the current revision in memory.
- Exposes line/range-based replacement operations.

### DirectiveParser

- Performs a cheap line-oriented parse.
- Extracts directive type, id, params, body, and source range.
- Builds a directive index for rendering and mutation targeting.

### CapabilityRegistry

- Maps directive types to renderer implementations.
- Exposes renderer manifests and capability declarations.
- Allows partial rendering when a directive type is unsupported.

### MutationEngine

- Converts every widget action into a text mutation.
- Supports only three mutation forms:
  - append
  - replace
  - delete
- Applies the mutation to the text, then triggers reparse and rerender.

### EventBus

- Connects renderer actions to the mutation layer.
- Keeps UI code from mutating document text directly.

### Renderers

Each renderer:

- receives a parsed directive plus document context
- returns a Textual widget
- emits semantic actions, not direct file edits

Example:

- `TaskRenderer` emits `task.toggle(id, done=True)`
- `PyRenderer` emits `py.run(block_id)`
- `TableRenderer` emits `table.edit(cell, value)`

## UI Layout

The simplest viable TUI:

```text
┌──────────────────────────────┬──────────────────────────────┐
│ Source / Raw Text            │ Rendered Document            │
│                              │                              │
│ editable text buffer         │ prose + directive widgets    │
│                              │                              │
├──────────────────────────────┴──────────────────────────────┤
│ Mutation Log / Status / Errors                              │
└─────────────────────────────────────────────────────────────┘
```

For an even smaller first cut, drop the permanent split view and show:

- one rendered document pane
- per-directive toggle between source and widget view
- a bottom mutation log

## Python Execution

Do **not** execute `::py` blocks inside the main TUI process.

Use a separate Python worker process:

- send all relevant `::py` blocks in document order
- rebuild a shared document-scoped namespace
- execute in order
- return:
  - stdout
  - exported variables
  - table-compatible structured results
  - tracebacks on error

That gives:

- document-scoped Python context
- isolation from crashes
- a future path to stricter sandboxing

## Data Model

Minimal types are enough at the start:

```python
@dataclass
class Directive:
    type: str
    id: str | None
    params: dict[str, str]
    body: list[str]
    start_line: int
    end_line: int

@dataclass
class TextMutation:
    kind: Literal["append", "replace", "delete"]
    start_line: int
    end_line: int
    new_text: str
    source: str
```

## Rendering Model

The rendering loop should stay simple:

1. Load document text.
2. Parse into directives and prose spans.
3. Build a mixed render tree.
4. Render only the visible window plus a small margin.
5. On any user action:
   - emit a semantic event
   - convert it to a text mutation
   - apply mutation
   - reparse
   - rerender

This preserves the architecture's central rule: the widget is never the source of truth.

## First Interactive Features

### `::task`

- Render as checkbox + title + due metadata.
- Toggling checkbox rewrites directive text.

### `::py`

- Show code, output, and run button.
- Rebuild context in document order on each run.

### `::table`

- Start read-only.
- Then allow cell editing through text mutations.

### `::note`

- Resolve section from another file.
- Render inline.

### `::file`

- Show local file preview or directory listing.

## Why A Console Renderer Is Viable

This architecture does not require a browser.

A terminal renderer can support:

- buttons
- checkboxes
- text inputs
- tabbed views
- dialogs
- editable tables
- inline advisories
- mutation logs

That is enough to realize the core system. The browser-level experiences can come later.

## Non-Goals For V1

- perfect sandboxing
- real-time backend sync
- rich media rendering
- drag and drop
- full plugin distribution
- conflict-resolution UX beyond simple visible markers

## Practical Conclusion

The right first implementation is:

- **Language:** Python
- **UI:** Textual
- **Compute runtime:** external Python worker process
- **Storage:** plain text files
- **State model:** text mutations only

That is the shortest path to proving the thesis of Folio without overcommitting to the hardest parts of the system too early.
