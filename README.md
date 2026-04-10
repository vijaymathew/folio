# Folio

**Folio** is a CLI-based prototype for a text-native architecture where **the document is the computer**. 

Instead of standalone applications owning your data, Folio treats a plain text file as the primary substrate for computing. Applications are downgraded to **renderers**—transient lenses that interpret structured directives (`::type[id]{params}`) inline within your prose and write all state changes back as human-readable text mutations.

This implementation is a minimal Textual-based scaffold designed to validate the core pillars of the [The Document is the Computer](https://vijaymathew.github.io/books/ui/the-document-is-the-computer.html) philosophy:

- **Text as Ground Truth:** All data (tasks, tables, calculations) lives in a durable, portable `.folio` file.
- **Apps as Renderers:** Capabilities like task management, Python execution, and structured tables are summoned via a universal grammar.
- **No Hidden State:** The document serves as an event-sourced log; every action is recorded as a text mutation.
- **Graceful Degradation:** The information remains readable by humans and simple Unix tools even without a specialized renderer.

## Core Components

- `DocumentStore`: Manages loading and atomic saving of the text substrate.
- `DirectiveParser`: A line-oriented parser for `::directive` blocks.
- `CapabilityRegistry`: Maps directive types to their respective renderers and manages manifests.
- `MutationEngine`: Applies surgical text mutations to the source file and triggers reparsing.
- `Textual UI`: A dual-pane console interface providing a raw source view and a rich rendered view.
- **Built-in Renderers:** Initial implementations for `task`, `py` (sandboxed Python execution), `table` (grid editing), `note`, and `file`.

## Installation

To install Folio globally on your system:

```bash
bash install.sh
```

This will set up an isolated environment in `~/.local/share/folio` and add the `folio` command to your `~/.local/bin`.

## Run (Development)

For local development or to run without installing:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
folio docs/example.folio
```

## Usage & Controls

- `q`: Quit.
- `r`: Reload document from disk.
- `f6`: Toggle between single-pane and split-pane view.
- `Ctrl+S`: Save the source pane, reparse, and rerender.
- **Interactions:**
    - Click a **task checkbox** to write a mutation back to the source file.
    - Click **Run** on a `::py` block to execute sandboxed Python in a subprocess.
    - Click **Source / Widget** to toggle the rendered view for a specific directive.
    - Use arrow keys and `Enter` to edit `::table` cells directly in the grid.

## Project Documentation

- [Console Architecture Detail](docs/console-architecture.md)
- [Renderer & Registry Authoring](docs/renderer-interface.md)
- [Example .folio File](docs/example.folio)
