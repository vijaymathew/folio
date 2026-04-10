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
- Tracks the current loaded/saved file state in memory for overwrite safety.
- Exposes line/range-based replacement operations.
- Leaves version history, rollback, and branching to external tools such as `git`.

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

## Implementation Checklist

Status key:

- `done`: implemented and working in the current Folio scaffold
- `partial`: present, but simplified, placeholder-backed, or not implemented to the level described above
- `not started`: not implemented in the current scaffold

### Recommendation / Stack

- `done` Python host language
- `done` Textual UI
- `done` plain text file storage
- `done` external Python worker process for `::py`

### What To Build First

- `done` `::task`
- `done` `::py`
- `done` `::table`
- `done` `::note`
- `done` `::file`

### Minimal Runtime Architecture

- `done` text file → `DocumentStore`
- `done` `DocumentStore` → `DirectiveParser`
- `done` parser output → renderer registry / render loop
- `done` renderers → mutation engine → updated text file
- `done` directive index
- `done` render engine abstraction

### Core Modules

- `done` `DocumentStore`
- `done` `DirectiveParser`
- `done` `CapabilityRegistry`
- `done` `MutationEngine`
- `done` `EventBus`
- `done` `models.py`
- `done` `ui/App.py`
- `done` `ui/DocumentView.py`
- `not started` `ui/SourcePane.py`
- `not started` `ui/MutationLog.py`
- `done` `renderers/base.py`
- `done` `renderers/TaskRenderer.py`
- `done` `renderers/PyRenderer.py`
- `done` `renderers/TableRenderer.py`
- `done` `renderers/NoteRenderer.py`
- `done` `renderers/FileRenderer.py`
- `done` `python/PyWorker.py`

### Responsibilities

#### DocumentStore

- `done` loads and saves the text file
- `done` tracks current loaded/saved file state in memory
- `done` exposes line/range replacement operations directly

#### Version History

- `done` version management is treated as an external concern
  Folio relies on the document file as the source of truth and expects tools such as `git` to provide history, diffs, rollback, and branching.
- `done` overwrite safety remains an internal concern
  `DocumentStore` detects when the on-disk file changed since load before saving over it.

#### DirectiveParser

- `done` cheap line-oriented parse
- `done` extracts type, id, params, body, and source range
- `done` builds a directive index for rendering/mutation targeting

#### CapabilityRegistry

- `done` maps directive types to renderer implementations
- `done` exposes renderer manifests / capability declarations
- `done` allows partial rendering when a directive type is unsupported
  Unknown directives fall back to raw header text.

#### MutationEngine

- `done` converts widget actions into text mutations
- `done` supports append / replace / delete
- `partial` applies mutation, then triggers reparse / rerender
  The apply step is centralized, but the app still owns the parse/render refresh cycle after the mutation commits.

#### EventBus

- `done` exists
- `done` serves as the main connection between renderers and mutation layer
- `done` keeps UI concerns separated from mutation handling

#### Renderers

- `done` receive parsed directives plus context
- `done` return Textual widgets
- `done` emit semantic actions rather than direct file edits

### UI Layout

- `done` split source pane + rendered pane + bottom status pane
- `done` editable source buffer
- `done` mutation/status/error pane
- `done` per-directive source/widget toggle
- `done` single-pane alternative mode

### Python Execution

- `done` `::py` does not execute in the main TUI process
- `done` separate Python worker process
- `done` executes relevant `::py` blocks in document order
- `done` shared document-scoped namespace across blocks
- `done` returns stdout
- `done` returns exported variables
- `done` returns table-compatible structured results
- `done` returns tracebacks / errors
- `done` hardened sandboxing path
  The worker now runs under an isolated interpreter with a scrubbed environment, stronger resource limits, and audit-hook blocking for filesystem, process, and network operations. This is still not perfect sandboxing.

### Data Model

- `done` `Directive`
- `done` `TextMutation`
- `done` `PyBlockResult`
  This goes beyond the minimal model described above.

### Rendering Model

- `done` load document text
- `done` parse into directives and prose spans
- `done` build a mixed render tree
- `done` render only the visible window plus a small margin
- `partial` emit semantic event → convert to mutation → apply → reparse → rerender
  The mutation commit path is centralized now, but full reparse/rerender orchestration still lives in the app.

### First Interactive Features

#### `::task`

- `done` checkbox-like rendering with title and due metadata
- `done` toggling rewrites directive text

#### `::py`

- `done` shows code, output, and run button for manual blocks
- `done` rebuilds context in document order on each run

#### `::table`

- `done` read-only rendering from `table(rows)` output
- `done` cell editing through text mutations
- `done` direct in-cell editing UX

#### `::note`

- `done` resolve section from another file
- `done` inline rendering
- `done` document-relative note source resolution

#### `::file`

- `done` real local file preview
- `done` real directory listing
- `done` document-relative path resolution

### Why A Console Renderer Is Viable

- `done` buttons
- `done` checkboxes
- `done` text inputs
- `not started` tabbed views
- `not started` dialogs
- `done` editable tables
- `done` inline advisories
- `done` mutation logs / status pane

### Non-Goals For V1

- `done` perfect sandboxing not attempted
- `done` real-time backend sync not implemented
- `done` rich media rendering not implemented
- `done` drag and drop not implemented
- `done` full plugin distribution not implemented
- `done` conflict-resolution UX beyond simple markers not implemented
