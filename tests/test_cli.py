"""The ``cce`` command prints results on stdout and nothing else (ADR-0002)."""

import sys

import pytest
from typer.testing import CliRunner

import cce
from cce import CceError
from cce.cli import app, main


class TestVersionCommand:
    def test_prints_the_version_on_stdout(self, cli: CliRunner) -> None:
        result = cli.invoke(app, ["version"])

        assert result.exit_code == 0
        assert result.stdout == f"cce {cce.__version__}\n"

    def test_writes_nothing_to_stderr(self, cli: CliRunner) -> None:
        result = cli.invoke(app, ["version"])

        assert result.stderr == ""


class TestNoArguments:
    def test_shows_help_and_lists_the_version_command(self, cli: CliRunner) -> None:
        result = cli.invoke(app, [])

        assert "version" in result.stdout

    def test_unknown_command_is_a_usage_error(self, cli: CliRunner) -> None:
        result = cli.invoke(app, ["definitely-not-a-command"])

        assert result.exit_code == 2
        assert result.stdout == ""


class TestConsoleScriptEntryPoint:
    def test_main_runs_the_app_with_process_arguments(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr(sys, "argv", ["cce", "version"])

        with pytest.raises(SystemExit) as raised:
            main()

        assert raised.value.code == 0
        assert capsys.readouterr().out == f"cce {cce.__version__}\n"


class TestCceError:
    def test_defaults_to_the_runtime_failure_exit_code(self) -> None:
        error = CceError("boom")

        assert str(error) == "boom"
        assert error.exit_code == 1

    def test_carries_an_explicit_exit_code(self) -> None:
        assert CceError("refused", exit_code=3).exit_code == 3
