from __future__ import annotations

import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from folio.core.models import ShRunResult


class ShRunner:
    def __init__(self, *, shell: str = "/bin/bash", timeout_seconds: float = 10.0) -> None:
        self.shell = shell
        self.timeout_seconds = timeout_seconds

    def run(self, key: str, command: str, cwd: str | None = None) -> ShRunResult:
        resolved_cwd = self._resolve_cwd(cwd)
        started = time.monotonic()
        timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        env = self._scrubbed_env()
        try:
            completed = subprocess.run(
                command,
                shell=True,
                executable=self.shell,
                cwd=str(resolved_cwd),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                env=env,
            )
            duration = time.monotonic() - started
            return ShRunResult(
                key=key,
                command=command,
                cwd=str(resolved_cwd),
                exit_code=completed.returncode,
                stdout=completed.stdout.splitlines(),
                stderr=completed.stderr.splitlines(),
                duration_seconds=duration,
                timestamp=timestamp,
            )
        except subprocess.TimeoutExpired as exc:
            duration = time.monotonic() - started
            stdout = (exc.stdout or "").splitlines()
            stderr = (exc.stderr or "").splitlines()
            stderr.append(f"Command timed out after {self.timeout_seconds:.1f}s")
            return ShRunResult(
                key=key,
                command=command,
                cwd=str(resolved_cwd),
                exit_code=124,
                stdout=stdout,
                stderr=stderr,
                duration_seconds=duration,
                timestamp=timestamp,
                error="timeout",
            )
        except Exception as exc:
            duration = time.monotonic() - started
            return ShRunResult(
                key=key,
                command=command,
                cwd=str(resolved_cwd),
                exit_code=1,
                stdout=[],
                stderr=[str(exc)],
                duration_seconds=duration,
                timestamp=timestamp,
                error=str(exc),
            )

    def _resolve_cwd(self, cwd: str | None) -> Path:
        if cwd is None or cwd.strip() == "":
            return Path.cwd()
        return Path(cwd.strip('"')).expanduser().resolve()

    def _scrubbed_env(self) -> dict[str, str]:
        allowed = {
            "HOME",
            "LANG",
            "LC_ALL",
            "LC_CTYPE",
            "LOGNAME",
            "PATH",
            "PWD",
            "SHELL",
            "TERM",
            "USER",
        }
        env = {key: value for key, value in os.environ.items() if key in allowed}
        env.setdefault("PATH", os.environ.get("PATH", "/usr/bin:/bin"))
        env.setdefault("HOME", str(Path.home()))
        env.setdefault("SHELL", self.shell)
        return env
