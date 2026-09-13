"""The ``cce`` command prints results on stdout and logs on stderr (ADR-0006)."""

import json
import sys
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

import cce
from cce import CceError
from cce.cli import app, default_workspace, guarded, main


class TestVersionCommand:
    def test_prints_the_version_on_stdout(self, cli: CliRunner) -> None:
        result = cli.invoke(app, ["version"])

        assert result.exit_code == 0
        assert result.stdout == f"cce {cce.__version__}\n"

    def test_writes_nothing_to_stderr(self, cli: CliRunner) -> None:
        result = cli.invoke(app, ["version"])

        assert result.stderr == ""


class TestNoArguments:
    def test_shows_help_and_lists_the_commands(self, cli: CliRunner) -> None:
        result = cli.invoke(app, [])

        assert "version" in result.stdout
        assert "doctor" in result.stdout

    def test_unknown_command_is_a_usage_error(self, cli: CliRunner) -> None:
        result = cli.invoke(app, ["definitely-not-a-command"])

        assert result.exit_code == 2
        assert result.stdout == ""


class TestVersionFlag:
    def test_dash_dash_version_prints_and_exits_zero(self, cli: CliRunner) -> None:
        result = cli.invoke(app, ["--version"])

        assert result.exit_code == 0
        assert result.stdout == f"cce {cce.__version__}\n"

    def test_short_flag_works_before_a_command(self, cli: CliRunner) -> None:
        result = cli.invoke(app, ["-V", "doctor"])

        assert result.exit_code == 0
        assert result.stdout == f"cce {cce.__version__}\n"


class TestGlobalOptions:
    def test_verbose_and_quiet_together_are_a_usage_error(self, cli: CliRunner) -> None:
        result = cli.invoke(app, ["-v", "-q", "version"])

        assert result.exit_code == 2
        assert "mutually exclusive" in result.stderr

    def test_verbose_json_logs_go_to_stderr_as_json(self, cli: CliRunner) -> None:
        result = cli.invoke(app, ["-v", "--log-format", "json", "version"])

        assert result.exit_code == 0
        assert result.stdout == f"cce {cce.__version__}\n"
        record = json.loads(result.stderr.splitlines()[0])
        assert record["event"] == "start"
        assert record["level"] == "debug"

    def test_log_format_can_come_from_the_environment(
        self, cli: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("CCE_LOG_FORMAT", "json")

        result = cli.invoke(app, ["-v", "version"])

        assert json.loads(result.stderr.splitlines()[0])["event"] == "start"

    def test_quiet_suppresses_the_start_record(self, cli: CliRunner) -> None:
        result = cli.invoke(app, ["-q", "version"])

        assert result.stderr == ""


class TestDefaultWorkspace:
    def test_cce_workspace_wins(self, tmp_path: Path) -> None:
        env = {"CCE_WORKSPACE": str(tmp_path / "ws"), "XDG_DATA_HOME": str(tmp_path / "xdg")}

        assert default_workspace(env, tmp_path) == tmp_path / "ws"

    def test_xdg_data_home_is_next(self, tmp_path: Path) -> None:
        assert default_workspace({"XDG_DATA_HOME": str(tmp_path / "xdg")}, tmp_path) == (
            tmp_path / "xdg" / "cce"
        )

    def test_falls_back_to_local_share(self, tmp_path: Path) -> None:
        assert default_workspace({}, tmp_path) == tmp_path / ".local" / "share" / "cce"


class TestGuarded:
    def test_turns_cce_error_into_its_exit_code(self) -> None:
        @guarded
        def command() -> None:
            raise CceError("refused", exit_code=3)

        with pytest.raises(typer.Exit) as raised:
            command()

        assert raised.value.exit_code == 3

    def test_passes_results_through(self) -> None:
        @guarded
        def command(value: int) -> int:
            return value * 2

        assert command(21) == 42


class TestDoctorCommand:
    def test_offline_doctor_prints_rows_and_exits_zero(self, cli: CliRunner) -> None:
        result = cli.invoke(app, ["doctor", "--offline"])

        assert result.exit_code == 0, result.stderr
        rows = result.stdout.splitlines()
        assert rows[0].startswith("ok    python")
        assert any(row.startswith("ok    upstream") for row in rows)
        assert "\x1b[" not in result.stdout

    def test_colour_is_applied_only_on_a_colour_terminal(
        self, cli: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("NO_COLOR", "1")

        result = cli.invoke(app, ["doctor", "--offline"], color=True)

        assert "\x1b[" not in result.stdout

    def test_json_output_is_a_list_of_checks(self, cli: CliRunner) -> None:
        result = cli.invoke(app, ["doctor", "--offline", "--json"])

        checks = json.loads(result.stdout)
        assert {"name", "status", "detail", "details"} <= set(checks[0])

    def test_verbose_lists_the_files_behind_a_warn_row(
        self, cli: CliRunner, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        home = tmp_path / "copilot-home"
        (home / "skills" / "mine").mkdir(parents=True)
        (home / "skills" / "mine" / "SKILL.md").write_text("x")
        monkeypatch.setenv("COPILOT_HOME", str(home))

        quiet = cli.invoke(app, ["doctor", "--offline"])
        verbose = cli.invoke(app, ["doctor", "--offline", "--verbose"])

        assert "warn  personal      global instructions may skew" in quiet.stdout
        assert "skills/mine/SKILL.md" not in quiet.stdout
        assert f"{'':20}skills/mine/SKILL.md\n" in verbose.stdout

    def test_failures_exit_three_after_printing_rows(
        self, cli: CliRunner, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("PATH", str(tmp_path / "empty-bin"))

        result = cli.invoke(app, ["doctor", "--offline"])

        assert result.exit_code == 3
        assert "fail  git" in result.stdout
        assert "doctor found failures" in result.stderr


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
