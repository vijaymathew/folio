from __future__ import annotations

from pathlib import Path

from folio.core.parser import DirectiveParser
from folio.python.worker import PyWorker


def _py_directives_from(path: Path):
    text = path.read_text()
    model = DirectiveParser().parse(text)
    return model.directive_index.directives_of_type("py")


def test_worker_runs_document_in_order_and_captures_table() -> None:
    directives = _py_directives_from(Path("/home/vijay/Projects/folio/docs/example.folio"))
    results = PyWorker().run_document(directives, trigger_key="budget-check")

    assert results["q3-data"].status == "ok"
    assert results["budget-check"].status == "ok"
    assert results["budget-check"].stdout == ["2350"]
    assert results["budget-check"].table is not None
    assert len(results["budget-check"].table) == 4
    assert results["budget-check"].table[0]["category"] == "Travel"


def test_worker_autorun_only_skips_manual_block() -> None:
    directives = _py_directives_from(Path("/home/vijay/Projects/folio/docs/example.folio"))
    results = PyWorker().run_document(directives, autorun_only=True)

    assert results["q3-data"].status == "ok"
    assert results["budget-check"].status == "manual"


def test_worker_rejects_unsafe_code(tmp_path: Path) -> None:
    doc = tmp_path / "unsafe.folio"
    doc.write_text(
        """::py[unsafe]{run="manual"}
open("/etc/passwd")
::end
""",
        encoding="utf-8",
    )
    directives = _py_directives_from(doc)
    results = PyWorker().run_document(directives, trigger_key="unsafe")

    assert results["unsafe"].status == "error"
    assert results["unsafe"].error is not None
    assert "SafeExecutionError" in results["unsafe"].error
