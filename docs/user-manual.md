# Folio User Manual

This manual explains how to run Folio, how the document format works, and how to use the currently supported `::` directives.

## Starting Folio

Install and run Folio from the repo root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
folio docs/example.folio
```

If you installed Folio globally with `bash install.sh`, you can run:

```bash
folio path/to/document.folio
```

Folio opens one text document at a time. The document on disk is the source of truth.

## Basic UI

Folio has two main panes:

- source pane: the raw `.folio` text
- render pane: widgets generated from `::` directives

Default startup is single-pane widget view. Press `F6` to switch between single-pane and split-pane. If you want to add new plain text or new directives, switch to split view with `F6` and edit the source pane.

Keyboard controls:

- `q`: quit
- `r`: reload the document from disk
- `Ctrl+S`: save the current source buffer or inline directive edit, then reparse and rerender
- `F6`: toggle split-pane / single-pane
- `F8`: open source find
- `F3` / `Shift+F3`: next / previous source match
- `Ctrl+Z` / `Ctrl+Y`: undo / redo in the full source view

Common interactions:

- focus a directive and press `Enter` or `e` to edit that directive's source inline
- press `Ctrl+S` to save an inline directive edit
- press `Esc` to cancel an inline directive edit and restore the widget
- click a task checkbox to toggle completion
- click `Run` on `::py` and `::sh`
- use arrow keys plus typing / `Enter` to edit `::table`
- select and act on messages in `::email`
- edit fields and click `Save` or `Save Draft` where supported

## Document Syntax

Folio directives use this general form:

```text
::type[id]{key="value" other=value}
body lines here
::end
```

Short single-line directives are also supported:

```text
::file[docs/readme.md]{preview="text"}
```

Conventions:

- `type` selects the renderer, for example `task` or `py`
- `id` is optional
- params are optional
- block directives end with `::end`
- body text stays part of the document and remains readable without Folio

## Directive Reference

### `::task`

Purpose:
- Track a task with checkbox state and metadata.

Example:

```text
::task[send-q3]{due="2026-03-25" blocked-by="call-finance" done="false"}
Send Q3 brief to Sara
::end
```

Common params:

- `done="true"` or `done="false"`
- `due="..."` for a date or label
- `priority="high"` or similar labels
- `blocked-by="other-task-id"`
- `completed="now"` or a timestamp

Widget behavior:

- click the checkbox to toggle completion
- Folio writes the updated directive back into the document

### `::py`

Purpose:
- Run document-scoped Python in a hardened subprocess worker.

Example:

```text
::py[q3-data]{run="auto"}
actuals = [4200, 1850, 6700, 3100]
budget = [3500, 2000, 5000, 3000]
categories = ["Travel", "Software", "Hardware", "Marketing"]
::end
```

Common params:

- `run="auto"` to evaluate on reload
- `run="manual"` to require clicking `Run`

Behavior:

- `::py` blocks run in document order
- later blocks can use values from earlier blocks
- stdout is shown in the widget
- `table(rows)` captures structured rows for `::table`

Current security model:

- subprocess execution
- restricted builtins and imports
- not arbitrary host Python

### `::table`

Purpose:
- Render structured rows from inline JSON or a `::py` source block.

Example:

```text
::table[q3-breakdown]{source="budget-check" sortable="true" editable="true"}
```

Or inline rows:

```text
::table[people]{editable="true"}
{"name":"Sara","role":"Product"}
{"name":"Maya","role":"Ops"}
::end
```

Common params:

- `source="py-block-id"`
- `editable="true"`
- `sortable="true"` reserved for future richer sorting

Widget behavior:

- arrow keys move the active cell
- type to start editing
- `Enter` commits the new value
- `Esc` cancels
- edits are written back into the `::table` block in the document

### `::note`

Purpose:
- Transclude a section from a local text or Markdown file.

Example:

```text
::note[docs/sample/design-principles.md]{section="colours"}
```

Common params:

- `path="docs/design.md"` when the id is not the source path
- `section="heading-name"` to extract one heading section

Behavior:

- resolves paths relative to the document
- supports `.md`, `.txt`, and `.folio`
- heading-based extraction for sections

### `::file`

Purpose:
- Preview a file or list a directory.

Example:

```text
::file[docs/renderer-interface.md]{preview="text" lines="20"}
```

Common params:

- `path="..."` when the id is not the target path
- `preview="auto"` or `preview="text"`
- `lines="20"` to limit output

Behavior:

- text files render inline
- directories list entries
- binary files are identified but not previewed

### `::contact`

Purpose:
- Render contacts from inline text or local vCard files.

Inline example:

```text
::contact[sara.chen]
name = Sara Chen
email = sara@example.com
role = Head of Product
org = Example Ltd
phone = +44 7700 900123
notes = Prefers async communication.
::end
```

File-backed examples:

```text
::contact[contacts/sara.vcf]
::contact[contacts]{limit="10"}
```

Common params:

- `path="..."` when the id is not a vCard path
- `limit="6"` for directory-backed contact lists

Behavior:

- inline body form renders a single editable contact
- single `.vcf` file renders as an editable contact card
- directory or multi-contact sources render as read-only lists
- saving rewrites the inline block or the `.vcf` file

### `::email`

Purpose:
- Read a local Maildir mailbox or render a draft compose form.

Mailbox example:

```text
::email[mail]{folder="Inbox" limit="20" archive-folder="Archive" trash-folder="Trash"}
```

Draft example:

```text
::email[draft]{path="mail" drafts-folder="Drafts" from="vijay@example.com" to="team@example.com" cc="ops@example.com" subject="Weekly briefing"}
Please review the latest draft before noon.
::end
```

Mailbox params:

- `folder="Inbox"`
- `limit="20"`
- `archive-folder="Archive"`
- `trash-folder="Trash"`

Draft params:

- `path="maildir-path"`
- `drafts-folder="Drafts"`
- `from="..."`
- `to="..."`
- `cc="..."`
- `subject="..."`
- `draft-key="..."` added after saving

Mailbox behavior:

- shows a message list plus the selected message
- supports:
  - select message
  - mark read / unread
  - star / unstar
  - move to `Trash`
  - move to `Archive`

Draft behavior:

- renders editable compose fields
- body is the plain text between the directive tags
- `Save Draft` writes the draft to the Maildir `Drafts` folder
- the directive is rewritten with updated params and `draft-key`

Current scope:

- local Maildir only
- no SMTP sending yet
- no attachments yet

### `::web`

Purpose:
- Render a text-only view of a web page.

Example:

```text
::web[https://example.com/article]{load="manual" lines="40"}
```

Common params:

- `url="..."` when the id is not the URL
- `load="auto"` or `load="manual"`
- `view="reader"` currently only reader mode is supported
- `lines="40"`

Behavior:

- fetches HTTP/HTTPS pages through the app-level web reader
- extracts readable text and links
- `Reload` refetches the page

### `::sh`

Purpose:
- Run a privileged shell command in runbook style.

Example:

```text
::sh[build-report]{cmd="make build" cwd=~/projects/q3-report trust=author}
```

Common params:

- `cmd="..."`
- `cwd=...`
- `trust=author` or `trust=review-before-running`

Behavior:

- manual only
- runs in the user’s shell, not the `::py` sandbox
- untrusted documents require extra confirmation
- output is written back into the document as `::sh-output[id]{...}`

### `::sh-output`

Purpose:
- Display captured output for a `::sh` block.

Example:

```text
::sh-output[build-report]{exit=0 duration="4.2s" ts="2026-03-24T14:32"}
[stdout]
Build successful.
::end
```

This directive is usually written by Folio after running `::sh`.

## Paths And Local Data

File-backed directives resolve relative paths from the document directory first, then ancestor directories. This applies to:

- `::file`
- `::note`
- `::contact`
- `::email`

Examples:

```text
::file[docs/renderer-interface.md]
::contact[docs/sample/contacts]
::email[docs/sample/email]{folder="Inbox"}
```

Absolute paths also work if they stay inside Folio’s allowed file-access roots.

## Inline Directive Editing

Existing rendered directives can be edited inline from widget view.

How to use it:

- focus a directive and press `Enter` or `e`
- edit the directive source inline
- press `Ctrl+S` to save, reparse, and restore the widget
- press `Esc` to cancel the edit session and restore the current widget view

If you want to add new plain text or new directives, switch to split view with `F6` and edit the source pane directly. Use `F8` to open find in the full source view. Some terminal emulators intercept `Ctrl+Shift+F`, so `F8` is the reliable Folio-local shortcut.

## Safety Notes

Important boundaries:

- `::py` is sandboxed and subprocess-based
- `::sh` is privileged and should be treated as dangerous
- `::web` performs live network fetches
- `::email` and `::contact` mutate local Maildir and vCard files when you save changes

For untrusted documents:

- read before running `::sh`
- review local-path directives before saving file-backed mutations

## Sample Document

The best starting point is:

- [example.folio](./example.folio)

It includes working examples of:

- tasks
- contacts
- email inbox
- email draft
- python
- table
- note
- file preview

