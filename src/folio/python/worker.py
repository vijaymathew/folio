from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import traceback
from dataclasses import asdict
from typing import Any

from folio.core.models import Directive, PyBlockResult


def _block_key(directive: Directive) -> str:
    return directive.id or str(directive.start_line)


def _export(value: Any, depth: int = 0) -> Any:
    if depth > 3:
        return repr(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_export(item, depth + 1) for item in value[:32]]
    if isinstance(value, tuple):
        return [_export(item, depth + 1) for item in value[:32]]
    if isinstance(value, dict):
        return {
            str(key): _export(item, depth + 1)
            for key, item in list(value.items())[:32]
        }
    if isinstance(value, set):
        return [_export(item, depth + 1) for item in list(value)[:32]]
    return repr(value)


def _evaluate_payload(blocks: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    shared: dict[str, Any] = {"__builtins__": __builtins__}
    results: dict[str, dict[str, Any]] = {}
    halted = False

    for block in blocks:
        key = block["key"]

        if halted:
            results[key] = {
                "key": key,
                "status": "blocked",
                "stdout": [],
                "error": "Skipped because an earlier Python block failed.",
                "context": {},
            }
            continue

        if not block.get("execute", False):
            results[key] = {
                "key": key,
                "status": "manual",
                "stdout": [],
                "error": None,
                "context": {},
            }
            continue

        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                exec(block["code"], shared)

            exported = {
                name: _export(value)
                for name, value in shared.items()
                if not name.startswith("__")
            }
            results[key] = {
                "key": key,
                "status": "ok",
                "stdout": buf.getvalue().splitlines(),
                "error": None,
                "context": exported,
            }
        except Exception:
            halted = True
            results[key] = {
                "key": key,
                "status": "error",
                "stdout": buf.getvalue().splitlines(),
                "error": traceback.format_exc().rstrip(),
                "context": {},
            }

    return results


class PyWorker:
    """Subprocess-backed runtime for document-scoped ::py evaluation."""

    def run_document(
        self,
        directives: list[Directive],
        *,
        trigger_key: str | None = None,
        autorun_only: bool = False,
    ) -> dict[str, PyBlockResult]:
        payload = {
            "blocks": [
                {
                    "key": _block_key(directive),
                    "code": "\n".join(directive.body),
                    "execute": self._should_execute(
                        directives,
                        directive,
                        trigger_key=trigger_key,
                        autorun_only=autorun_only,
                    ),
                }
                for directive in directives
            ]
        }

        proc = subprocess.run(
            [sys.executable, "-m", "folio.python.worker"],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            error = proc.stderr.strip() or "Python worker failed."
            return {
                _block_key(directive): PyBlockResult(
                    key=_block_key(directive),
                    status="error",
                    stdout=[],
                    error=error,
                    context={},
                )
                for directive in directives
            }

        raw_results = json.loads(proc.stdout or "{}")
        return {
            key: PyBlockResult(
                key=key,
                status=value.get("status", "error"),
                stdout=value.get("stdout", []),
                error=value.get("error"),
                context=value.get("context", {}),
            )
            for key, value in raw_results.items()
        }

    def _should_execute(
        self,
        directives: list[Directive],
        directive: Directive,
        *,
        trigger_key: str | None,
        autorun_only: bool,
    ) -> bool:
        if autorun_only:
            return directive.params.get("run", '"manual"').strip('"') == "auto"

        if trigger_key is None:
            return directive.params.get("run", '"manual"').strip('"') == "auto"

        keys = [_block_key(item) for item in directives]
        current_key = _block_key(directive)
        target_index = keys.index(trigger_key)
        current_index = keys.index(current_key)
        return current_index <= target_index


def _main() -> int:
    payload = json.loads(sys.stdin.read() or "{}")
    blocks = payload.get("blocks", [])
    results = _evaluate_payload(blocks)
    sys.stdout.write(json.dumps(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
