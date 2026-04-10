from __future__ import annotations

from pathlib import Path

from folio.core.models import TextMutation
from folio.core.mutations import MutationEngine
from folio.core.store import DocumentConflictError, DocumentStore


def test_store_detects_external_change_before_save(tmp_path: Path) -> None:
    doc = tmp_path / "conflict.folio"
    doc.write_text("one\n", encoding="utf-8")

    store = DocumentStore(doc)
    assert store.load() == "one\n"

    doc.write_text("two\n", encoding="utf-8")

    try:
        store.save("three\n")
    except DocumentConflictError as exc:
        assert "changed on disk since load" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected external-change conflict")


def test_store_replace_lines_updates_cached_text(tmp_path: Path) -> None:
    doc = tmp_path / "replace.folio"
    doc.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")

    store = DocumentStore(doc)
    store.load()
    updated = store.replace_lines(1, 1, "BETA")

    assert updated == "alpha\nBETA\ngamma\n"
    assert store.get_text() == updated
    assert doc.read_text(encoding="utf-8") == updated


def test_mutation_engine_propagates_store_conflict(tmp_path: Path) -> None:
    doc = tmp_path / "mutation-conflict.folio"
    doc.write_text("first\nsecond\n", encoding="utf-8")

    store = DocumentStore(doc)
    store.load()
    doc.write_text("external\nsecond\n", encoding="utf-8")

    mutation = TextMutation(
        kind="replace",
        start_line=0,
        end_line=0,
        new_text="local",
        source="test",
    )

    try:
        MutationEngine(store).apply(mutation)
    except DocumentConflictError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected mutation conflict to propagate")
