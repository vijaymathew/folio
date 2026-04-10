# folio

Minimal Textual scaffold for a console-first Folio prototype.

## What is here

- `DocumentStore`: loads and saves the text file.
- `DirectiveParser`: line-oriented parser for `::directive[id]{params}` blocks.
- `CapabilityRegistry`: maps directive types to renderers.
- `MutationEngine`: applies text mutations and reparses.
- `Textual` app: source pane plus rendered document pane.
- Sample directive renderers for `task`, `py`, `table`, `note`, and `file`.

This is intentionally small. It is a starting point for validating the text-first architecture in a console renderer.

Renderer and registry authoring notes live in [docs/renderer-interface.md](/home/vijay/Projects/folio/docs/renderer-interface.md).

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
folio docs/example.folio
```

## Tests

```bash
pip install -e ".[dev]"
pytest
```

## Controls

- `q`: quit
- `r`: reload document from disk
- edit the source pane directly, then press `Ctrl+S` to save, reparse, and rerender
- click a task checkbox to write a text mutation back to the source file
- click `Run` on a `::py` block to execute document-scoped Python in a subprocess worker

## Scope

Only document-owned state is in scope for this scaffold:

- `::task`
- `::py`
- `::table`
- `::note`
- `::file`

Remote backends are intentionally excluded from this first cut.

## Python Execution

`::py` blocks now execute in a subprocess-backed worker:

- blocks are evaluated in document order
- earlier blocks populate the shared namespace for later ones
- `run="auto"` blocks execute on reload
- manual blocks execute when `Run` is pressed
- stdout and tracebacks are returned to the renderer without running code in the main TUI process

The worker uses a hardened sandbox policy:

- only a small safe subset of builtins is exposed
- imports are restricted to an explicit allowlist
- dangerous names like `open`, `eval`, `exec`, and `__import__` are blocked
- function/class definitions, `try`, `with`, `raise`, and `while` are rejected
- the worker runs in an isolated interpreter (`-I -S -B`) with a scrubbed environment and temp working directory
- subprocess execution is time-limited, with stricter CPU, memory, file-size, descriptor, and core-dump limits where the platform supports them
- Python audit hooks block filesystem, process, and network operations even if user code escapes the AST-level restrictions

The allowlist currently includes common document-compute modules such as:

- `math`
- `statistics`
- `collections`
- `datetime`
- `decimal`
- `fractions`
- `functools`
- `itertools`
- `re`
- `string`
- `textwrap`

This is substantially stronger than the earlier “safe subset” worker, but it is still not a formal kernel-enforced sandbox against malicious native code or CPython escape bugs.

`table(rows)` is also available inside `::py` blocks. When a block calls it with a list of dictionaries, the corresponding `::table` renderer can display those structured rows directly.

`::table` supports direct keyboard editing in the grid itself: move the cell cursor with the arrow keys, type to replace the highlighted value, press `Enter` to save the text mutation, and press `Esc` to cancel the active edit.

`::note` directives can resolve a section from a local `.md`, `.folio`, or `.txt` file. If `path="..."` is omitted, Folio will try to resolve the note id as a document-relative file name.

The bottom status pane surfaces:

- autorun completion
- manual worker runs
- safety policy failures
- external-change save conflicts
- source buffer dirty/save state
- task toggles
- table-edit mutations
