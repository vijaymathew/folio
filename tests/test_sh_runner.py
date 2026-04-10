from __future__ import annotations

from folio.core.sh_runner import ShRunner


def test_sh_runner_captures_stdout_and_stderr_separately() -> None:
    result = ShRunner().run("check", "printf 'hello\\n'; printf 'warn\\n' 1>&2")

    assert result.exit_code == 0
    assert result.stdout == ["hello"]
    assert result.stderr == ["warn"]
    assert result.timestamp


def test_sh_runner_reports_nonzero_exit_code() -> None:
    result = ShRunner().run("fail", "printf 'bad\\n' 1>&2; exit 2")

    assert result.exit_code == 2
    assert result.stdout == []
    assert result.stderr == ["bad"]
