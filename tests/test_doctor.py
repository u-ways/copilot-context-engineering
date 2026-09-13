"""Doctor reports the machine state without ever raising (ADR-0006)."""

import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from cce.doctor import Check, Environment, Status, has_failures, run_checks
from cce.manifest import Manifest, parse

MANIFEST_TEXT = """
[source]
url = "{url}"
ref = "0123456789abcdef0123456789abcdef01234567"

[[scenario]]
id = "01"
slug = "01-only"
title = "Only"
"""


def real_run(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
    """Real git; a canned Copilot CLI so the suite does not depend on it being installed."""
    if argv[0] == "copilot":
        return subprocess.CompletedProcess(list(argv), 0, "GitHub Copilot CLI 1.0.83.\n", "")
    return subprocess.run(list(argv), capture_output=True, text=True, check=False)


def environment(
    tmp_path: Path,
    *,
    tools: Sequence[str] = ("git", "copilot", "uv"),
    env: dict[str, str] | None = None,
    python: tuple[int, int, int] = (3, 14, 7),
) -> Environment:
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    return Environment(
        env=env or {},
        home=home,
        which=lambda name: f"/fake/bin/{name}" if name in tools else None,
        run=real_run,
        python_version=python,
    )


@pytest.fixture
def manifest(tmp_path: Path) -> Manifest:
    upstream = tmp_path / "upstream"
    subprocess.run(["git", "init", "-q", "-b", "main", str(upstream)], check=True)
    (upstream / "README.md").write_text("synthetic\n")
    subprocess.run(["git", "-C", str(upstream), "add", "-A"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(upstream),
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@x",
            "commit",
            "-qm",
            "init",
        ],
        check=True,
    )
    return parse(MANIFEST_TEXT.format(url=upstream.as_uri()))


def by_name(checks: Sequence[Check]) -> dict[str, Check]:
    return {check.name: check for check in checks}


class TestHealthyMachine:
    def test_everything_present_is_ok(self, tmp_path: Path, manifest: Manifest) -> None:
        checks = by_name(run_checks(environment(tmp_path), manifest, offline=True))

        assert {name: check.status for name, check in checks.items()} == {
            "python": Status.OK,
            "git": Status.OK,
            "copilot": Status.OK,
            "uv": Status.OK,
            "personal": Status.OK,
            "overlays": Status.OK,
            "upstream": Status.OK,
        }
        assert not has_failures(list(checks.values()))

    def test_overlays_render_against_placeholders(self, tmp_path: Path, manifest: Manifest) -> None:
        checks = by_name(run_checks(environment(tmp_path), manifest, offline=True))

        assert "1 scenarios render" in checks["overlays"].detail

    def test_unrenderable_overlays_fail(self, tmp_path: Path) -> None:
        manifest = parse(
            MANIFEST_TEXT.format(url="file:///nowhere").replace(
                'title = "Only"', 'title = "Only"\nagents = ["ghost"]'
            )
        )

        checks = by_name(run_checks(environment(tmp_path), manifest, offline=True))

        assert checks["overlays"].status is Status.FAIL
        assert "ghost" in checks["overlays"].detail

    def test_offline_skips_the_upstream_check(self, tmp_path: Path, manifest: Manifest) -> None:
        checks = by_name(run_checks(environment(tmp_path), manifest, offline=True))

        assert "skipped" in checks["upstream"].detail

    def test_reachable_upstream_is_ok(self, tmp_path: Path, manifest: Manifest) -> None:
        checks = by_name(run_checks(environment(tmp_path), manifest, offline=False))

        assert checks["upstream"].status is Status.OK

    def test_a_hanging_upstream_probe_is_a_fail_row_not_a_traceback(
        self, tmp_path: Path, manifest: Manifest
    ) -> None:
        def hanging(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
            if argv[:2] == ["git", "ls-remote"]:
                raise subprocess.TimeoutExpired(list(argv), 30)
            return real_run(argv)

        env = environment(tmp_path)
        env = Environment(env.env, env.home, env.which, hanging, env.python_version)

        check = by_name(run_checks(env, manifest, offline=False))["upstream"]
        assert check.status is Status.FAIL and "--offline" in check.detail

    def test_unreachable_upstream_fails(self, tmp_path: Path) -> None:
        manifest = parse(MANIFEST_TEXT.format(url=(tmp_path / "missing").as_uri()))

        checks = by_name(run_checks(environment(tmp_path), manifest, offline=False))

        assert checks["upstream"].status is Status.FAIL
        assert has_failures(list(checks.values()))


class TestCopilotVersion:
    def test_reports_the_version_when_new_enough(self, tmp_path: Path, manifest: Manifest) -> None:
        def copilot_run(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
            if argv[0] == "copilot":
                return subprocess.CompletedProcess(
                    list(argv), 0, "GitHub Copilot CLI 1.0.90.\n", ""
                )
            return real_run(argv)

        env = environment(tmp_path)
        env = Environment(env.env, env.home, env.which, copilot_run, env.python_version)

        check = by_name(run_checks(env, manifest, offline=True))["copilot"]
        assert check.status is Status.OK and check.detail.startswith("1.0.90")

    def test_warns_when_older_than_the_measured_version(
        self, tmp_path: Path, manifest: Manifest
    ) -> None:
        def copilot_run(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
            if argv[0] == "copilot":
                return subprocess.CompletedProcess(
                    list(argv), 0, "GitHub Copilot CLI 1.0.42.\n", ""
                )
            return real_run(argv)

        env = environment(tmp_path)
        env = Environment(env.env, env.home, env.which, copilot_run, env.python_version)

        check = by_name(run_checks(env, manifest, offline=True))["copilot"]
        assert check.status is Status.WARN and "1.0.83" in check.detail

    def test_unparseable_or_failing_probe_warns(self, tmp_path: Path, manifest: Manifest) -> None:
        def copilot_run(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
            if argv[0] == "copilot":
                raise OSError("cannot execute")
            return real_run(argv)

        env = environment(tmp_path)
        env = Environment(env.env, env.home, env.which, copilot_run, env.python_version)

        assert by_name(run_checks(env, manifest, offline=True))["copilot"].status is Status.WARN


class TestMissingTools:
    def test_missing_copilot_and_uv_warn(self, tmp_path: Path, manifest: Manifest) -> None:
        checks = by_name(run_checks(environment(tmp_path, tools=["git"]), manifest, offline=True))

        assert checks["copilot"].status is Status.WARN
        assert checks["uv"].status is Status.WARN

    def test_developer_and_presenter_tools_are_not_reported(
        self, tmp_path: Path, manifest: Manifest
    ) -> None:
        env = environment(tmp_path, tools=["git", "claude", "herdr"], env={"HERDR_ENV": "1"})

        names = {check.name for check in run_checks(env, manifest, offline=True)}

        assert "claude" not in names and "herdr" not in names

    def test_missing_git_fails(self, tmp_path: Path, manifest: Manifest) -> None:
        checks = by_name(run_checks(environment(tmp_path, tools=[]), manifest, offline=True))

        assert checks["git"].status is Status.FAIL

    def test_old_git_warns(self, tmp_path: Path, manifest: Manifest) -> None:
        def old_git(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(
                list(argv), 0, stdout="git version 2.20.1\n", stderr=""
            )

        env = environment(tmp_path)
        env = Environment(env.env, env.home, env.which, old_git, env.python_version)

        assert by_name(run_checks(env, manifest, offline=True))["git"].status is Status.WARN

    def test_unparseable_git_version_fails(self, tmp_path: Path, manifest: Manifest) -> None:
        def broken_git(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(list(argv), 1, stdout="", stderr="boom")

        env = environment(tmp_path)
        env = Environment(env.env, env.home, env.which, broken_git, env.python_version)

        assert by_name(run_checks(env, manifest, offline=True))["git"].status is Status.FAIL

    def test_old_python_fails(self, tmp_path: Path, manifest: Manifest) -> None:
        checks = by_name(
            run_checks(environment(tmp_path, python=(3, 13, 2)), manifest, offline=True)
        )

        assert checks["python"].status is Status.FAIL


class TestPersonalCustomisation:
    def test_global_instructions_warn_and_list_every_file(
        self, tmp_path: Path, manifest: Manifest
    ) -> None:
        env = environment(tmp_path)
        (env.home / ".copilot" / "skills" / "mine").mkdir(parents=True)
        (env.home / ".copilot" / "skills" / "mine" / "SKILL.md").write_text("x")
        (env.home / ".copilot" / "hooks").mkdir()
        (env.home / ".copilot" / "hooks" / "stop.json").write_text("{}")
        (env.home / ".copilot" / "copilot-instructions.md").write_text("be terse\n")

        check = by_name(run_checks(env, manifest, offline=True))["personal"]

        assert check.status is Status.WARN
        assert check.detail.startswith("global instructions may skew scenario results: ")
        assert (
            "~/.copilot/copilot-instructions.md, ~/.copilot/skills, ~/.copilot/hooks"
            in check.detail
        )
        assert "docs/PREREQUISITES.md" in check.detail
        assert check.details == (
            "copilot-instructions.md",
            "skills/mine/SKILL.md",
            "hooks/stop.json",
        )

    def test_copilot_home_is_honoured_and_claude_is_ignored(
        self, tmp_path: Path, manifest: Manifest
    ) -> None:
        scratch = tmp_path / "scratch-home"
        env = environment(tmp_path, env={"COPILOT_HOME": str(scratch)})
        (env.home / ".copilot" / "skills" / "mine").mkdir(parents=True)
        (env.home / ".copilot" / "skills" / "mine" / "SKILL.md").write_text("x")
        (env.home / ".claude" / "skills" / "theirs").mkdir(parents=True)
        (env.home / ".claude" / "skills" / "theirs" / "SKILL.md").write_text("y")

        check = by_name(run_checks(env, manifest, offline=True))["personal"]
        assert check.status is Status.OK and "$COPILOT_HOME" in check.detail

        (scratch / "agents").mkdir(parents=True)
        (scratch / "agents" / "a.agent.md").write_text("z")
        check = by_name(run_checks(env, manifest, offline=True))["personal"]
        assert check.status is Status.WARN and "$COPILOT_HOME/agents" in check.detail
        assert check.details == ("agents/a.agent.md",)

    def test_empty_directories_are_fine(self, tmp_path: Path, manifest: Manifest) -> None:
        env = environment(tmp_path)
        (env.home / ".copilot" / "agents").mkdir(parents=True)

        assert by_name(run_checks(env, manifest, offline=True))["personal"].status is Status.OK

    def test_long_listings_are_capped(self, tmp_path: Path, manifest: Manifest) -> None:
        env = environment(tmp_path)
        hooks = env.home / ".copilot" / "hooks"
        hooks.mkdir(parents=True)
        for index in range(60):
            (hooks / f"{index:02}.json").write_text("{}")

        check = by_name(run_checks(env, manifest, offline=True))["personal"]

        assert len(check.details) == 51 and check.details[-1] == "... and 10 more"


class TestPresentation:
    def test_rows_and_dicts_carry_status_name_and_detail(self) -> None:
        check = Check("git", Status.OK, "git version 2.50.0")

        assert check.as_row() == "ok    git           git version 2.50.0"
        assert check.as_dict() == {
            "name": "git",
            "status": "ok",
            "detail": "git version 2.50.0",
            "details": [],
        }

    def test_from_system_uses_the_running_interpreter(self) -> None:
        env = Environment.from_system({"HOME": "/nowhere"})

        assert env.python_version[0] == 3
        assert env.which("git") is not None
        assert env.run(["git", "--version"]).returncode == 0
