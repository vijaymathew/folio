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

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
folio docs/example.folio
```

## Controls

- `q`: quit
- `r`: reload document from disk
- click `Toggle` on a task to write a text mutation back to the source file

## Scope

Only document-owned state is in scope for this scaffold:

- `::task`
- `::py`
- `::table`
- `::note`
- `::file`

Remote backends are intentionally excluded from this first cut.
