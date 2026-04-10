from __future__ import annotations

import ast
import contextlib
import io
import json
import math
import os
import re
import statistics
import string
import subprocess
import sys
import tempfile
import textwrap
import traceback
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from fractions import Fraction
from functools import reduce
from itertools import chain
from pathlib import Path
from typing import Any

from folio.core.models import Directive, PyBlockResult

try:
    import resource
except ImportError:  # pragma: no cover
    resource = None


ALLOWED_IMPORTS: dict[str, Any] = {
    "collections": __import__("collections"),
    "datetime": __import__("datetime"),
    "decimal": __import__("decimal"),
    "fractions": __import__("fractions"),
    "functools": __import__("functools"),
    "itertools": __import__("itertools"),
    "math": math,
    "re": re,
    "statistics": statistics,
    "string": string,
    "textwrap": textwrap,
}

SAFE_BUILTINS: dict[str, Any] = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "float": float,
    "filter": filter,
    "int": int,
    "len": len,
    "list": list,
    "map": map,
    "max": max,
    "min": min,
    "print": print,
    "range": range,
    "reversed": reversed,
    "round": round,
    "set": set,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "zip": zip,
}

FORBIDDEN_NAMES = {
    "__import__",
    "breakpoint",
    "compile",
    "eval",
    "exec",
    "getattr",
    "globals",
    "help",
    "input",
    "locals",
    "open",
    "setattr",
    "delattr",
    "vars",
}

FORBIDDEN_NODES = (
    ast.AsyncFor,
    ast.AsyncFunctionDef,
    ast.AsyncWith,
    ast.Await,
    ast.ClassDef,
    ast.Delete,
    ast.FunctionDef,
    ast.Global,
    ast.Nonlocal,
    ast.Raise,
    ast.Try,
    ast.While,
    ast.With,
    ast.Yield,
    ast.YieldFrom,
)

BLOCKED_AUDIT_PREFIXES = (
    "cpython._PySys_ClearAuditHooks",
    "fcntl.",
    "ftplib.",
    "glob.glob",
    "glob.glob/2",
    "http.client.",
    "imaplib.",
    "marshal.load",
    "marshal.loads",
    "os.chdir",
    "os.chflags",
    "os.chmod",
    "os.chown",
    "os.exec",
    "os.fork",
    "os.fwalk",
    "os.kill",
    "os.link",
    "os.listdir",
    "os.listxattr",
    "os.lockf",
    "os.mkdir",
    "os.open",
    "os.remove",
    "os.rename",
    "os.replace",
    "os.rmdir",
    "os.scandir",
    "os.setxattr",
    "os.spawn",
    "os.startfile",
    "os.symlink",
    "os.system",
    "pathlib.",
    "poplib.",
    "pty.",
    "resource.prlimit",
    "shutil.",
    "smtplib.",
    "socket.",
    "sqlite3.",
    "ssl.",
    "subprocess.",
    "telnetlib.",
    "urllib.",
    "webbrowser.",
)

BLOCKED_AUDIT_EVENTS = {
    "code.__new__",
    "open",
}


def _block_key(directive: Directive) -> str:
    return directive.key()


def _safe_error(message: str) -> str:
    return f"SafeExecutionError: {message}"


def _validate_code(code: str) -> ast.AST:
    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as exc:
        raise ValueError(f"syntax error on line {exc.lineno}: {exc.msg}") from exc

    for node in ast.walk(tree):
        if isinstance(node, FORBIDDEN_NODES):
            raise ValueError(f"{type(node).__name__} is not allowed in ::py blocks")

        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root not in ALLOWED_IMPORTS:
                    raise ValueError(f"import of '{alias.name}' is not allowed")

        if isinstance(node, ast.ImportFrom):
            module = (node.module or "").split(".", 1)[0]
            if module not in ALLOWED_IMPORTS:
                raise ValueError(f"import from '{node.module}' is not allowed")

        if isinstance(node, ast.Name):
            if node.id in FORBIDDEN_NAMES or node.id.startswith("__"):
                raise ValueError(f"name '{node.id}' is not allowed")

        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise ValueError(f"attribute '{node.attr}' is not allowed")

        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in FORBIDDEN_NAMES:
                raise ValueError(f"call to '{func.id}' is not allowed")

    return tree


def _export(value: Any, depth: int = 0) -> Any:
    if depth > 3:
        return repr(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_export(item, depth + 1) for item in value[:64]]
    if isinstance(value, tuple):
        return [_export(item, depth + 1) for item in value[:64]]
    if isinstance(value, dict):
        return {
            str(key): _export(item, depth + 1)
            for key, item in list(value.items())[:64]
        }
    if isinstance(value, set):
        return [_export(item, depth + 1) for item in list(value)[:64]]
    return repr(value)


def _coerce_table(rows: Any) -> list[dict[str, object]] | None:
    if not isinstance(rows, list):
        return None
    if not rows:
        return []
    normalized: list[dict[str, object]] = []
    for row in rows[:128]:
        if isinstance(row, dict):
            normalized.append({str(key): _export(value) for key, value in row.items()})
        else:
            normalized.append({"value": _export(row)})
    return normalized


def _safe_import(name: str, globals_: dict[str, Any] | None = None, locals_: dict[str, Any] | None = None, fromlist: tuple[str, ...] = (), level: int = 0) -> Any:
    root = name.split(".", 1)[0]
    if root not in ALLOWED_IMPORTS:
        raise ImportError(f"import of '{name}' is not allowed")
    return ALLOWED_IMPORTS[root]


def _safe_builtins() -> dict[str, Any]:
    builtins_copy = dict(SAFE_BUILTINS)
    builtins_copy["__import__"] = _safe_import
    return builtins_copy


def _should_block_audit_event(event: str) -> bool:
    if event in BLOCKED_AUDIT_EVENTS:
        return True
    return any(event.startswith(prefix) for prefix in BLOCKED_AUDIT_PREFIXES)


def _install_audit_hook() -> None:
    def audit(event: str, args: tuple[Any, ...]) -> None:
        if _should_block_audit_event(event):
            raise PermissionError(f"audit event '{event}' is blocked")

    sys.addaudithook(audit)


def _harden_runtime() -> None:
    sys.dont_write_bytecode = True
    sys.setrecursionlimit(250)
    sys.path[:] = []

    sandbox_dir = Path.cwd()
    os.environ.clear()
    os.environ.update(
        {
            "HOME": str(sandbox_dir),
            "TMPDIR": str(sandbox_dir),
            "PYTHONNOUSERSITE": "1",
        }
    )

    try:
        os.umask(0o077)
    except Exception:
        pass

    if resource is not None:
        limits: list[tuple[int, tuple[int, int]]] = [
            (resource.RLIMIT_CPU, (2, 2)),
            (resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024)),
            (resource.RLIMIT_NOFILE, (32, 32)),
        ]
        memory = 128 * 1024 * 1024
        for limit_name in ("RLIMIT_AS", "RLIMIT_DATA"):
            limit = getattr(resource, limit_name, None)
            if limit is not None:
                limits.append((limit, (memory, memory)))
        stack_limit = getattr(resource, "RLIMIT_STACK", None)
        if stack_limit is not None:
            limits.append((stack_limit, (16 * 1024 * 1024, 16 * 1024 * 1024)))
        nproc_limit = getattr(resource, "RLIMIT_NPROC", None)
        if nproc_limit is not None:
            limits.append((nproc_limit, (0, 0)))
        core_limit = getattr(resource, "RLIMIT_CORE", None)
        if core_limit is not None:
            limits.append((core_limit, (0, 0)))

        for limit, value in limits:
            try:
                resource.setrlimit(limit, value)
            except Exception:
                continue

    _install_audit_hook()


def _evaluate_payload(blocks: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    shared: dict[str, Any] = {"__builtins__": _safe_builtins()}
    shared.update(
        {
            "Counter": Counter,
            "Decimal": Decimal,
            "Fraction": Fraction,
            "date": date,
            "datetime": datetime,
            "timedelta": timedelta,
            "defaultdict": defaultdict,
            "reduce": reduce,
            "chain": chain,
        }
    )
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
                "table": None,
            }
            continue

        if not block.get("execute", False):
            results[key] = {
                "key": key,
                "status": "manual",
                "stdout": [],
                "error": None,
                "context": {},
                "table": None,
            }
            continue

        buf = io.StringIO()
        table_output: dict[str, list[dict[str, object]] | None] = {"rows": None}

        def table(rows: Any) -> Any:
            normalized = _coerce_table(rows)
            if normalized is None:
                raise ValueError("table(...) expects a list of rows or values")
            table_output["rows"] = normalized
            return rows

        shared["table"] = table
        try:
            tree = _validate_code(block["code"])
            with contextlib.redirect_stdout(buf):
                exec(compile(tree, f"<py:{key}>", "exec"), shared)

            exported = {
                name: _export(value)
                for name, value in shared.items()
                if not name.startswith("__") and name != "table"
            }
            results[key] = {
                "key": key,
                "status": "ok",
                "stdout": buf.getvalue().splitlines(),
                "error": None,
                "context": exported,
                "table": table_output["rows"],
            }
        except Exception as exc:
            halted = True
            error = _safe_error(str(exc)) if isinstance(exc, (ValueError, ImportError)) else traceback.format_exc().rstrip()
            results[key] = {
                "key": key,
                "status": "error",
                "stdout": buf.getvalue().splitlines(),
                "error": error,
                "context": {},
                "table": None,
            }
        finally:
            shared.pop("table", None)

    return results


def _limit_subprocess() -> None:
    if resource is None:  # pragma: no cover
        return
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
        memory = 128 * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
        nofile = getattr(resource, "RLIMIT_NOFILE", None)
        if nofile is not None:
            resource.setrlimit(nofile, (32, 32))
        core_limit = getattr(resource, "RLIMIT_CORE", None)
        if core_limit is not None:
            resource.setrlimit(core_limit, (0, 0))
    except Exception:
        return


class PyWorker:
    """Subprocess-backed runtime for hardened document-scoped ::py evaluation."""

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

        try:
            with tempfile.TemporaryDirectory(prefix="folio-py-") as sandbox_dir:
                proc = subprocess.run(
                    self._worker_command(),
                    input=json.dumps(payload),
                    text=True,
                    capture_output=True,
                    check=False,
                    timeout=3,
                    env=self._subprocess_env(sandbox_dir),
                    cwd=sandbox_dir,
                    preexec_fn=_limit_subprocess if resource is not None else None,
                )
        except subprocess.TimeoutExpired:
            return self._worker_error_results(directives, "SafeExecutionError: execution timed out")

        if proc.returncode != 0:
            error = proc.stderr.strip() or "Python worker failed."
            return self._worker_error_results(directives, error)

        raw_results = json.loads(proc.stdout or "{}")
        return {
            key: PyBlockResult(
                key=key,
                status=value.get("status", "error"),
                stdout=value.get("stdout", []),
                error=value.get("error"),
                context=value.get("context", {}),
                table=value.get("table"),
            )
            for key, value in raw_results.items()
        }

    def _worker_command(self) -> list[str]:
        src_root = str(Path(__file__).resolve().parents[2])
        bootstrap = (
            "import sys; "
            f"sys.path.insert(0, {src_root!r}); "
            "from folio.python.worker import _main; "
            "raise SystemExit(_main())"
        )
        return [sys.executable, "-I", "-S", "-B", "-c", bootstrap]

    def _subprocess_env(self, sandbox_dir: str) -> dict[str, str]:
        return {
            "HOME": sandbox_dir,
            "TMPDIR": sandbox_dir,
            "PATH": os.environ.get("PATH", ""),
            "PYTHONNOUSERSITE": "1",
            "PYTHONSAFEPATH": "1",
            "PYTHONHASHSEED": "0",
        }

    def _worker_error_results(self, directives: list[Directive], error: str) -> dict[str, PyBlockResult]:
        return {
            _block_key(directive): PyBlockResult(
                key=_block_key(directive),
                status="error",
                stdout=[],
                error=error,
                context={},
                table=None,
            )
            for directive in directives
        }

    def _should_execute(
        self,
        directives: list[Directive],
        directive: Directive,
        *,
        trigger_key: str | None,
        autorun_only: bool,
    ) -> bool:
        run_mode = directive.params.get("run", '"manual"').strip('"')
        if autorun_only:
            return run_mode == "auto"

        if trigger_key is None:
            return run_mode == "auto"

        keys = [_block_key(item) for item in directives]
        current_key = _block_key(directive)
        target_index = keys.index(trigger_key)
        current_index = keys.index(current_key)
        return current_index <= target_index


def _main() -> int:
    _harden_runtime()
    payload = json.loads(sys.stdin.read() or "{}")
    blocks = payload.get("blocks", [])
    results = _evaluate_payload(blocks)
    sys.stdout.write(json.dumps(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
