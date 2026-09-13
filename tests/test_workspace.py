"""One worktree per scenario, committed baselines, safe re-runs (ADR-0003, ADR-0004)."""

import fcntl
import json
import os
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from cce.cli import app
from cce.workspace import MARKER, State, Workspace, stray_upstream_paths
from tests.support.upstream import NEW_MARKER, OLD_MARKER, SyntheticUpstream, run_git

pytestmark = pytest.mark.usefixtures("quiet_environment")


class Playground:
    """Drive the CLI against a workspace under ``tmp_path`` and the synthetic upstream."""

    def __init__(self, cli: CliRunner, root: Path, upstream: SyntheticUpstream) -> None:
        self.cli = cli
        self.root = root
        self.upstream = upstream

    def run(self, *args: str, source: bool = False) -> tuple[int, str, str]:
        argv = ["--workspace", str(self.root), *args]
        if source:
            argv += ["--source-url", self.upstream.url, "--source-ref", self.upstream.head]
        result = self.cli.invoke(app, argv)
        return result.exit_code, result.stdout, result.stderr

    def setup(
        self, *ids: str, force: bool = False, dialect: str | None = None
    ) -> tuple[int, str, str]:
        extra = ["--force"] if force else []
        if dialect:
            extra += ["--dialect", dialect]
        return self.run("setup", *ids, *extra, source=True)

    def scenario(self, slug: str) -> Path:
        return self.root / "scenarios" / slug

    def base_git(self, *args: str) -> str:
        return run_git(self.root / "base", list(args))

    def objects(self) -> str:
        return self.base_git("count-objects", "-v")

    def baselines(self) -> dict[str, str]:
        listing = self.base_git(
            "for-each-ref", "--format=%(refname) %(objectname)", "refs/cce/baseline/"
        )
        return dict(line.split() for line in listing.split("\n") if line)


@pytest.fixture
def play(cli: CliRunner, tmp_path: Path, upstream: SyntheticUpstream) -> Playground:
    return Playground(cli, tmp_path / "ws", upstream)


class TestSetup:
    def test_creates_every_scenario_ready_on_a_committed_baseline(self, play: Playground) -> None:
        code, out, err = play.setup()

        assert code == 0, err
        rows = out.strip().split("\n")
        assert len(rows) == 6 and all("  ready  " in row for row in rows)
        for slug in ("01-instructions-timeless", "05-agent-permissions"):
            worktree = play.scenario(slug)
            assert run_git(worktree, ["status", "--porcelain"]) == ""
            assert run_git(worktree, ["rev-parse", "HEAD~1"]).strip() == play.upstream.head
            assert run_git(worktree, ["rev-parse", "--abbrev-ref", "HEAD"]).strip() == f"cce/{slug}"
        assert (play.root / MARKER).is_file()

    def test_overlay_files_are_committed_even_when_upstream_ignores_them(
        self, play: Playground
    ) -> None:
        play.setup("5")

        worktree = play.scenario("05-agent-permissions")
        tracked = run_git(worktree, ["ls-files"]).split("\n")
        assert "STRUGGLE.sh" in tracked
        assert ".github/agents/researcher.agent.md" in tracked
        assert os.access(worktree / "STRUGGLE.sh", os.X_OK)
        assert os.access(worktree / "scripts" / "cce-check-links.py", os.X_OK)

    def test_s01_instructions_carry_the_dated_table(self, play: Playground) -> None:
        play.setup("01")

        text = (
            play.scenario("01-instructions-timeless") / ".github" / "copilot-instructions.md"
        ).read_text()
        assert OLD_MARKER in text and NEW_MARKER not in text

    def test_setup_is_idempotent_when_already_ready(self, play: Playground) -> None:
        play.setup()
        before_objects, before_refs = play.objects(), play.baselines()

        code, out, _ = play.setup()

        assert code == 0
        assert out.count("  ready  ") == 6
        assert play.objects() == before_objects
        assert play.baselines() == before_refs

    def test_setup_refuses_modified_worktree_without_force(self, play: Playground) -> None:
        play.setup("3")
        (play.scenario("03-skills-on-demand") / "README.md").write_text("changed\n")

        code, out, err = play.setup("3")

        assert code == 3
        assert out == ""
        assert "03-skills-on-demand" in err and "--force" in err

    def test_force_recreates_a_modified_worktree(self, play: Playground) -> None:
        play.setup("3")
        (play.scenario("03-skills-on-demand") / "scratch.txt").write_text("junk\n")

        code, out, _ = play.setup("3", force=True)

        assert code == 0 and "  ready  " in out
        assert not (play.scenario("03-skills-on-demand") / "scratch.txt").exists()

    def test_partial_creation_is_reported_missing(self, play: Playground) -> None:
        play.setup("2")
        staging = play.root / "scenarios" / ".tmp-04-skills-description-routing"
        staging.mkdir()
        (staging / "junk").write_text("half-written\n")
        unregistered = play.scenario("06-agent-context-isolation")
        unregistered.mkdir()

        code, out, _ = play.run("list")
        rows = {line.split()[1]: line for line in out.strip().split("\n")}

        assert code == 0
        assert "missing" in rows["04-skills-description-routing"]
        assert "missing" in rows["06-agent-context-isolation"]

        code, _, err = play.setup("4", "6")
        assert code == 3 and "06-agent-context-isolation" in err

        code, out, _ = play.setup("4", "6", force=True)
        assert code == 0 and out.count("  ready  ") == 2
        assert not staging.exists()

    def test_changed_overlay_re_renders_a_ready_worktree_without_force(
        self, play: Playground
    ) -> None:
        play.setup("6")
        state = State.load(play.root / "state.json")
        state.scenarios["06-agent-context-isolation"].digest = "stale"
        state.save(play.root / "state.json")

        code, out, _ = play.run("list")
        assert "overlay changed" in out

        code, out, _ = play.setup("6")

        assert code == 0 and "  ready  " in out
        assert (
            State.load(play.root / "state.json").scenarios["06-agent-context-isolation"].digest
            != "stale"
        )

    def test_claude_dialect_lands_claude_layout(self, play: Playground) -> None:
        code, _, err = play.setup("3", "5", dialect="claude")

        assert code == 0, err
        three = play.scenario("03-skills-on-demand")
        assert (three / "CLAUDE.md").is_file()
        assert not (three / ".github" / "copilot-instructions.md").exists()
        assert (three / ".claude" / "skills" / "test-strategy-design" / "SKILL.md").is_file()
        five = play.scenario("05-agent-permissions")
        agent = (five / ".claude" / "agents" / "researcher.md").read_text()
        assert "tools: Read, Grep, Glob, WebFetch, WebSearch" in agent
        _, out, _ = play.run("list", "--json")
        assert {row["dialect"] for row in json.loads(out) if row["status"] == "ready"} == {"claude"}

    def test_unknown_id_is_a_usage_error(self, play: Playground) -> None:
        code, out, err = play.setup("42")

        assert code == 2 and out == "" and "valid ids" in err

    def test_unreachable_ref_is_a_runtime_failure(self, play: Playground) -> None:
        code, _, err = play.run(
            "setup", "1", "--source-url", play.upstream.url, "--source-ref", "f" * 40
        )

        assert code == 1 and "not reachable" in err

    def test_source_url_mismatch_is_refused(self, play: Playground, tmp_path: Path) -> None:
        play.setup("1")
        other = tmp_path / "other"
        subprocess.run(["git", "init", "-q", str(other)], check=True)

        code, _, err = play.run(
            "setup", "1", "--source-url", other.as_uri(), "--source-ref", play.upstream.head
        )

        assert code == 3 and "cce teardown" in err

    def test_lock_contention_is_refused(self, play: Playground) -> None:
        play.root.mkdir(parents=True)
        with (play.root / ".cce.lock").open("a+") as held:
            fcntl.flock(held, fcntl.LOCK_EX)

            code, _, err = play.setup("1")

        assert code == 3 and "lock" in err


class TestListAndPath:
    def test_list_shows_missing_before_setup_and_never_fails(self, play: Playground) -> None:
        code, out, _ = play.run("list")

        assert code == 0
        assert out.count("  missing  ") == 6

    def test_path_prints_the_absolute_worktree_path(self, play: Playground) -> None:
        play.setup("3")

        code, out, _ = play.run("path", "skills-on-demand")

        assert code == 0
        assert out.strip() == str(play.scenario("03-skills-on-demand").resolve())

    def test_path_of_a_missing_scenario_exits_three_with_empty_stdout(
        self, play: Playground
    ) -> None:
        code, out, err = play.run("path", "3")

        assert code == 3 and out == "" and "cce setup 03" in err


class TestBaselineRef:
    def test_status_follows_the_baseline_ref_not_the_state_file(self, play: Playground) -> None:
        play.setup("2")
        state_path = play.root / "state.json"
        state = State.load(state_path)
        state.scenarios["02-instructions-context-cost"].baseline = "0" * 40
        state.save(state_path)

        _, out, _ = play.run("list")

        row = next(line for line in out.split("\n") if "02-instructions-context-cost" in line)
        assert row.split()[2] == "ready"

    def test_reset_uses_the_baseline_ref(self, play: Playground) -> None:
        play.setup("2")
        worktree = play.scenario("02-instructions-context-cost")
        run_git(
            worktree,
            [
                "-c",
                "user.name=t",
                "-c",
                "user.email=t@x",
                "commit",
                "-q",
                "--allow-empty",
                "-m",
                "drift",
            ],
        )
        ref_sha = play.base_git(
            "rev-parse", "refs/cce/baseline/02-instructions-context-cost"
        ).strip()

        code, _, _ = play.run("reset", "2")

        assert code == 0
        assert run_git(worktree, ["rev-parse", "HEAD"]).strip() == ref_sha


class TestReset:
    def test_reset_restores_tracked_and_untracked_changes(self, play: Playground) -> None:
        play.setup("1")
        worktree = play.scenario("01-instructions-timeless")
        (worktree / "README.md").write_text("broken\n")
        (worktree / "extra.md").write_text("untracked\n")

        code, out, _ = play.run("reset", "1")

        assert code == 0 and out == "01-instructions-timeless reset\n"
        assert run_git(worktree, ["status", "--porcelain"]) == ""
        assert not (worktree / "extra.md").exists()

    def test_reset_all_skips_missing_scenarios_with_a_warning(self, play: Playground) -> None:
        play.setup("1")

        code, out, err = play.run("reset", "all")

        assert code == 0
        assert out == "01-instructions-timeless reset\n"
        assert "skipping missing scenario" in err

    def test_reset_of_a_missing_scenario_is_refused(self, play: Playground) -> None:
        play.setup("1")

        code, out, err = play.run("reset", "2")

        assert code == 3 and out == "" and "run `cce setup 02`" in err

    def test_reset_without_a_workspace_creates_nothing(self, play: Playground) -> None:
        code, out, err = play.run("reset", "2")

        assert code == 3 and out == "" and "not a cce workspace" in err
        assert not play.root.exists()


class TestTeardown:
    def test_removes_the_workspace_when_nothing_is_modified(self, play: Playground) -> None:
        play.setup("1", "2")

        code, out, _ = play.run("teardown")

        assert code == 0 and out == f"removed {play.root}\n"
        assert not play.root.exists()

    def test_refuses_when_a_scenario_is_modified_unless_forced(self, play: Playground) -> None:
        play.setup("1")
        (play.scenario("01-instructions-timeless") / "README.md").write_text("changed\n")

        code, _, err = play.run("teardown")
        assert code == 3 and "01-instructions-timeless" in err

        code, _, _ = play.run("teardown", "--force")
        assert code == 0 and not play.root.exists()

    def test_absent_workspace_is_a_no_op(self, play: Playground) -> None:
        code, out, err = play.run("teardown")

        assert code == 0 and out == "" and "nothing to remove" in err

    def test_directory_without_marker_is_never_removed(self, play: Playground) -> None:
        play.root.mkdir(parents=True)
        (play.root / "precious.txt").write_text("keep me\n")

        code, _, err = play.run("teardown")

        assert code == 3 and "marker" in err
        assert (play.root / "precious.txt").exists()


class TestStrayUpstreamPaths:
    def test_detects_instruction_files_that_would_skew_scenarios(self) -> None:
        tracked = frozenset(
            {"README.md", "AGENTS.md", ".github/skills/x/SKILL.md", ".github/CODEOWNERS"}
        )

        assert stray_upstream_paths(tracked) == [".github/skills/x/SKILL.md", "AGENTS.md"]

    def test_setup_warns_when_upstream_tracks_them(
        self, play: Playground, tmp_path: Path, upstream: SyntheticUpstream
    ) -> None:
        clone = tmp_path / "stray-upstream"
        subprocess.run(["git", "clone", "-q", str(upstream.path), str(clone)], check=True)
        (clone / "AGENTS.md").write_text("stray\n")
        run_git(clone, ["add", "AGENTS.md"])
        run_git(clone, ["-c", "user.name=t", "-c", "user.email=t@x", "commit", "-qm", "stray"])
        head = run_git(clone, ["rev-parse", "HEAD"]).strip()

        code, _, err = play.run("setup", "6", "--source-url", clone.as_uri(), "--source-ref", head)

        assert code == 0
        assert "may skew scenarios" in err and "AGENTS.md" in err


class TestWorkspaceObject:
    def test_rmtree_refuses_paths_outside_the_marked_workspace(
        self, tmp_path: Path, play: Playground
    ) -> None:
        from cce import CceError
        from cce.manifest import load

        workspace = Workspace(play.root, load())
        outside = tmp_path / "outside"
        outside.mkdir()

        with pytest.raises(CceError):
            workspace._rmtree(outside)
        assert outside.exists()
