"""The update check never fails a command and asks before upgrading (ADR-0007)."""

import json
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest
from typer.testing import CliRunner

import cce
from cce import CceError
from cce.cli import app, default_cache_dir
from cce.update import (
    RELEASES_LATEST_URL,
    TOOL_NAME,
    Latest,
    default_fetch,
    fetch_latest,
    maybe_notify,
    parse_version,
    releases_url,
    update,
)


class Recorder:
    """Records every injected call so tests assert on behaviour, not internals."""

    def __init__(self, body: bytes = b'{"tag_name": "v9.9.9"}', *, tty: bool = True) -> None:
        self.body = body
        self.tty = tty
        self.fetched: list[str] = []
        self.questions: list[str] = []
        self.commands: list[list[str]] = []
        self.answer = True
        self.clock = 1_000_000.0

    def fetch(self, url: str, timeout: float) -> bytes:
        assert timeout == 3.0
        self.fetched.append(url)
        return self.body

    def confirm(self, question: str) -> bool:
        self.questions.append(question)
        return self.answer

    def run(self, argv: Sequence[str]) -> int:
        self.commands.append(list(argv))
        return 0

    def notify(self, tmp_path: Path, env: dict[str, str] | None = None) -> None:
        maybe_notify(
            env=env or {},
            cache_dir=tmp_path / "cache",
            fetch=self.fetch,
            now=lambda: self.clock,
            is_tty=lambda: self.tty,
            confirm=self.confirm,
            run=self.run,
            current="0.1.0",
        )


class TestSkips:
    @pytest.mark.parametrize("variable", ["CCE_DISABLE_UPDATE_CHECK", "CI"])
    def test_environment_variables_disable_the_check(self, tmp_path: Path, variable: str) -> None:
        recorder = Recorder()

        recorder.notify(tmp_path, {variable: "1"})

        assert recorder.fetched == []
        assert not (tmp_path / "cache" / "update-check.json").exists()

    def test_checks_at_most_once_per_interval(self, tmp_path: Path) -> None:
        recorder = Recorder(b'{"tag_name": "v0.1.0"}')

        recorder.notify(tmp_path)
        recorder.clock += 100
        recorder.notify(tmp_path)
        recorder.clock += 86_400
        recorder.notify(tmp_path)

        assert len(recorder.fetched) == 2

    def test_interval_is_configurable(self, tmp_path: Path) -> None:
        recorder = Recorder(b'{"tag_name": "v0.1.0"}')

        recorder.notify(tmp_path, {"CCE_UPDATE_INTERVAL": "10"})
        recorder.clock += 11
        recorder.notify(tmp_path, {"CCE_UPDATE_INTERVAL": "10"})

        assert len(recorder.fetched) == 2

    def test_a_future_timestamp_does_not_disable_the_check(self, tmp_path: Path) -> None:
        recorder = Recorder(b'{"tag_name": "v0.1.0"}')
        cache = tmp_path / "cache" / "update-check.json"
        cache.parent.mkdir(parents=True)
        cache.write_text(json.dumps({"checked_at": recorder.clock + 10_000_000}))

        recorder.notify(tmp_path)

        assert len(recorder.fetched) == 1
        assert json.loads(cache.read_text())["checked_at"] == recorder.clock

    def test_timestamp_is_written_before_fetching_so_failures_are_not_retried(
        self, tmp_path: Path
    ) -> None:
        def failing(_url: str, _timeout: float) -> bytes:
            raise OSError("offline")

        maybe_notify(
            env={},
            cache_dir=tmp_path / "cache",
            fetch=failing,
            now=lambda: 1_000_000.0,
            is_tty=lambda: True,
            confirm=lambda _: True,
            run=lambda _: 0,
            current="0.1.0",
        )

        cache = json.loads((tmp_path / "cache" / "update-check.json").read_text())
        assert cache["checked_at"] == 1_000_000.0


class TestNotification:
    def test_prompts_on_a_tty_and_upgrades_on_yes(self, tmp_path: Path) -> None:
        recorder = Recorder()

        recorder.notify(tmp_path)

        assert recorder.fetched == [RELEASES_LATEST_URL]
        assert recorder.questions == ["cce v9.9.9 is available (you have 0.1.0). Upgrade now?"]
        assert recorder.commands == [["uv", "tool", "upgrade", TOOL_NAME]]

    def test_declining_runs_nothing(self, tmp_path: Path) -> None:
        recorder = Recorder()
        recorder.answer = False

        recorder.notify(tmp_path)

        assert recorder.commands == []

    def test_without_a_tty_only_a_log_line_is_emitted(self, tmp_path: Path) -> None:
        recorder = Recorder(tty=False)

        recorder.notify(tmp_path)

        assert recorder.questions == [] and recorder.commands == []

    def test_same_or_older_release_is_silent(self, tmp_path: Path) -> None:
        recorder = Recorder(b'{"tag_name": "0.1.0"}')

        recorder.notify(tmp_path)

        assert recorder.questions == []

    def test_custom_releases_url_is_honoured(self, tmp_path: Path) -> None:
        recorder = Recorder()

        recorder.notify(tmp_path, {"CCE_RELEASES_URL": "file:///tmp/latest.json"})

        assert recorder.fetched == ["file:///tmp/latest.json"]


class TestNeverFails:
    @pytest.mark.parametrize(
        "body", [b"not json", b'{"tag_name": "nightly"}', b"{}", b"[]", b'{"tag_name": 3}']
    )
    def test_unusable_bodies_are_ignored(self, tmp_path: Path, body: bytes) -> None:
        recorder = Recorder(body)

        recorder.notify(tmp_path)

        assert recorder.questions == []

    def test_raising_collaborators_do_not_propagate(self, tmp_path: Path) -> None:
        def boom(_url: str, _timeout: float) -> bytes:
            raise RuntimeError("boom")

        maybe_notify(
            env={},
            cache_dir=tmp_path / "cache",
            fetch=boom,
            now=lambda: 1.0,
            is_tty=lambda: True,
            confirm=lambda _: True,
            run=lambda _: 0,
        )

    def test_unwritable_cache_is_tolerated(self, tmp_path: Path) -> None:
        blocker = tmp_path / "cache"
        blocker.write_text("a file, not a directory")
        recorder = Recorder()

        recorder.notify(tmp_path)

        assert recorder.commands == []


class TestHelpers:
    def test_parse_version_accepts_optional_v_prefix(self) -> None:
        assert parse_version("v1.2.3") == (1, 2, 3)
        assert parse_version("1.2.3") == (1, 2, 3)
        assert parse_version("1.2") is None

    def test_fetch_latest_reads_a_file_url_through_the_default_fetcher(
        self, release_file: Callable[[str], str]
    ) -> None:
        assert fetch_latest(default_fetch, release_file("v2.0.0")) == Latest("v2.0.0", (2, 0, 0))

    def test_releases_url_defaults_to_the_github_api(self) -> None:
        assert releases_url({}) == RELEASES_LATEST_URL
        assert releases_url({"CCE_RELEASES_URL": "file:///x"}) == "file:///x"

    def test_cache_dir_prefers_xdg(self, tmp_path: Path) -> None:
        assert default_cache_dir({"XDG_CACHE_HOME": str(tmp_path)}, tmp_path) == tmp_path / "cce"
        assert default_cache_dir({}, tmp_path) == tmp_path / ".cache" / "cce"


class TestUpdateFunction:
    def test_check_only_reports_without_running_uv(
        self, release_file: Callable[[str], str]
    ) -> None:
        env = {"CCE_RELEASES_URL": release_file("v9.0.0")}

        current, latest, upgraded = update(env=env, check_only=True, which=lambda _: None)

        assert (current, latest, upgraded) == (cce.__version__, Latest("v9.0.0", (9, 0, 0)), False)

    def test_missing_uv_is_a_refused_precondition(self, release_file: Callable[[str], str]) -> None:
        env = {"CCE_RELEASES_URL": release_file("v9.0.0")}

        with pytest.raises(CceError) as raised:
            update(env=env, check_only=False, which=lambda _: None)

        assert raised.value.exit_code == 3

    def test_failed_upgrade_is_a_runtime_failure(self, release_file: Callable[[str], str]) -> None:
        env = {"CCE_RELEASES_URL": release_file("v9.0.0")}

        with pytest.raises(CceError) as raised:
            update(env=env, check_only=False, which=lambda _: "/bin/uv", run=lambda _: 2)

        assert raised.value.exit_code == 1


class TestUpdateCommand:
    def test_upgrades_through_uv_on_path(
        self,
        cli: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        shim_bin: Callable[[str, str], Path],
        release_file: Callable[[str], str],
    ) -> None:
        shim_bin("uv", "fake_uv.py")
        log = tmp_path / "uv.log"
        monkeypatch.setenv("FAKE_UV_LOG", str(log))
        monkeypatch.setenv("CCE_RELEASES_URL", release_file("v9.0.0"))

        result = cli.invoke(app, ["update"])

        assert result.exit_code == 0, result.stderr
        assert (
            result.stdout == f"cce {cce.__version__} (latest release: v9.0.0)\nupgraded to v9.0.0\n"
        )
        assert json.loads(log.read_text()) == ["tool", "upgrade", TOOL_NAME]

    def test_check_only_prints_versions(
        self, cli: CliRunner, monkeypatch: pytest.MonkeyPatch, release_file: Callable[[str], str]
    ) -> None:
        monkeypatch.setenv("CCE_RELEASES_URL", release_file("v9.0.0"))

        result = cli.invoke(app, ["update", "--check"])

        assert result.exit_code == 0
        assert result.stdout == f"cce {cce.__version__} (latest release: v9.0.0)\n"

    def test_up_to_date_says_so(
        self, cli: CliRunner, monkeypatch: pytest.MonkeyPatch, release_file: Callable[[str], str]
    ) -> None:
        monkeypatch.setenv("CCE_RELEASES_URL", release_file(f"v{cce.__version__}"))

        result = cli.invoke(app, ["update"])

        assert result.stdout.endswith("up to date\n")

    def test_missing_uv_exits_three(
        self,
        cli: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        release_file: Callable[[str], str],
    ) -> None:
        monkeypatch.setenv("PATH", str(tmp_path / "empty"))
        monkeypatch.setenv("CCE_RELEASES_URL", release_file("v9.0.0"))

        result = cli.invoke(app, ["update"])

        assert result.exit_code == 3 and "uv is not on PATH" in result.stderr


class TestResultCallback:
    def test_successful_commands_record_a_check_when_enabled(
        self,
        cli: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        release_file: Callable[[str], str],
    ) -> None:
        monkeypatch.delenv("CCE_DISABLE_UPDATE_CHECK")
        monkeypatch.delenv("CI", raising=False)
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg-cache"))
        monkeypatch.setenv("CCE_RELEASES_URL", release_file("v0.0.1"))

        result = cli.invoke(app, ["--workspace", str(tmp_path / "ws"), "list"])

        assert result.exit_code == 0
        assert (tmp_path / "xdg-cache" / "cce" / "update-check.json").is_file()

    def test_version_and_update_are_exempt(
        self,
        cli: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        release_file: Callable[[str], str],
    ) -> None:
        monkeypatch.delenv("CCE_DISABLE_UPDATE_CHECK")
        monkeypatch.delenv("CI", raising=False)
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg-cache"))
        monkeypatch.setenv("CCE_RELEASES_URL", release_file("v0.0.1"))

        cli.invoke(app, ["version"])
        cli.invoke(app, ["update", "--check"])

        assert not (tmp_path / "xdg-cache" / "cce" / "update-check.json").exists()
