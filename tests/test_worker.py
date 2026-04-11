from __future__ import annotations

from pathlib import Path

from folio.core.parser import DirectiveParser
from folio.python.worker import PyWorker, _should_block_audit_event
from conftest import EXAMPLE_DOC


def _py_directives_from(path: Path):
    text = path.read_text()
    model = DirectiveParser().parse(text)
    return model.directive_index.directives_of_type("py")


def test_worker_runs_document_in_order_and_captures_table() -> None:
    directives = _py_directives_from(EXAMPLE_DOC)
    results = PyWorker().run_document(directives, trigger_key="budget-check")

    assert results["q3-data"].status == "ok"
    assert results["budget-check"].status == "ok"
    assert results["budget-check"].stdout == ["2350"]
    assert results["budget-check"].table is not None
    assert len(results["budget-check"].table) == 4
    assert results["budget-check"].table[0]["category"] == "Travel"


def test_worker_autorun_only_skips_manual_block() -> None:
    directives = _py_directives_from(EXAMPLE_DOC)
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


def test_worker_allows_safe_imports_under_hardened_runtime(tmp_path: Path) -> None:
    doc = tmp_path / "safe-imports.folio"
    doc.write_text(
        """::py[calc]{run="manual"}
import math
from statistics import mean
print(math.isclose(mean([2, 4, 6]), 4))
::end
""",
        encoding="utf-8",
    )
    directives = _py_directives_from(doc)
    results = PyWorker().run_document(directives, trigger_key="calc")

    assert results["calc"].status == "ok"
    assert results["calc"].stdout == ["True"]


def test_audit_policy_blocks_io_process_and_network_events() -> None:
    assert _should_block_audit_event("open")
    assert _should_block_audit_event("socket.connect")
    assert _should_block_audit_event("subprocess.Popen")
    assert _should_block_audit_event("os.listdir")
    assert not _should_block_audit_event("import")
