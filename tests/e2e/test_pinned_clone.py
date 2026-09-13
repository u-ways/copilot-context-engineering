"""Every scenario renders against the real pinned upstream (ADR-0003, ADR-0004).

Run with ``just e2e``. Needs network access to clone the upstream once into a
temporary directory; asserts only paths, counts and structure, never prose.
"""

import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import Protocol, cast

import pytest
from typer.testing import CliRunner

from cce.cli import app
from cce.manifest import load
from cce.render import include_targets, load_procedures
from cce.workspace import Git, GitUpstream, stray_upstream_paths

pytestmark = pytest.mark.e2e

REPO_ROOT = Path(__file__).resolve().parents[2]
LICENCE_GUARD_MIN_CHARS = 40


class GroundTruth(Protocol):
    def count_level_two_headings(self, root: Path) -> tuple[int, dict[str, int]]: ...


def ground_truth() -> GroundTruth:
    spec = importlib.util.spec_from_file_location(
        "s06_ground_truth", REPO_ROOT / "scripts" / "s06_ground_truth.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return cast(GroundTruth, module)


@pytest.fixture(scope="module")
def workspace(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("e2e") / "ws"
    result = CliRunner().invoke(app, ["--workspace", str(root), "setup"])
    assert result.exit_code == 0, result.stderr
    return root


def scenario(workspace: Path, slug: str) -> Path:
    return workspace / "scenarios" / slug


class TestPinnedClone:
    def test_every_scenario_is_ready_on_top_of_the_pin(self, workspace: Path) -> None:
        manifest = load()
        result = CliRunner().invoke(app, ["--workspace", str(workspace), "list"])

        assert result.stdout.count("  ready  ") == len(manifest.scenarios)
        for item in manifest.scenarios:
            parent = subprocess.run(
                ["git", "-C", str(scenario(workspace, item.slug)), "rev-parse", "HEAD~1"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            assert parent == manifest.source_ref

    def test_upstream_tracks_no_instruction_files_at_the_pin(self, workspace: Path) -> None:
        manifest = load()
        reader = GitUpstream(Git(), workspace / "base", manifest.source_ref)

        assert stray_upstream_paths(reader.tracked_paths()) == []

    def test_every_include_target_exists_and_the_procedures_stay_in_band(
        self, workspace: Path
    ) -> None:
        manifest = load()
        reader = GitUpstream(Git(), workspace / "base", manifest.source_ref)
        for target in include_targets():
            if target.asof:
                assert reader.read_asof(target.path, target.asof)
            else:
                assert reader.read(target.path)
        included = 0
        for procedure in load_procedures(manifest):
            for line in procedure.source.split("\n"):
                if line.strip().startswith("<!-- cce:include "):
                    included += len(reader.read(line.split()[2]))

        assert 300_000 <= included <= 450_000

    def test_s01_instructions_point_at_the_removed_secret_scanning_tool(
        self, workspace: Path
    ) -> None:
        text = (
            scenario(workspace, "01-instructions-timeless") / ".github" / "copilot-instructions.md"
        ).read_text()
        current = (scenario(workspace, "01-instructions-timeless") / "blueprints.md").read_text()

        assert "tools/nhsd-git-secrets/README.md" in text
        assert "versioning-reference-template" not in text
        assert "tools/gitleaks.md" in current

    def test_s05_validator_reports_exactly_the_known_finding(self, workspace: Path) -> None:
        worktree = scenario(workspace, "05-agent-permissions")

        completed = subprocess.run(
            [sys.executable, "scripts/cce-check-links.py", "."],
            cwd=worktree,
            capture_output=True,
            text=True,
            check=False,
        )

        assert completed.returncode == 1
        lines = completed.stdout.split("\n")
        summary = "scanned 48 markdown files, 898 inline links "
        summary += "(313 external, 235 relative paths, 366 fragments)"
        assert lines[0] == summary
        assert "missing relative targets : 0" in lines
        assert "unresolved fragments : 0" in lines
        assert "email targets without mailto: : 1" in lines
        assert any(line.strip().startswith("SECURITY.md:23 ->") for line in lines)
        assert lines[-2] == "RESULT: FAIL"

    def test_s06_ground_truth_is_218_level_two_headings(self, workspace: Path) -> None:
        total, per_file = ground_truth().count_level_two_headings(
            scenario(workspace, "06-agent-context-isolation")
        )

        assert total == 218
        assert len(per_file) == 48

    def test_no_upstream_prose_is_shipped(self, workspace: Path) -> None:
        upstream_lines: set[str] = set()
        base = workspace / "base"
        listing = subprocess.run(
            ["git", "-C", str(base), "ls-tree", "-r", "--name-only", load().source_ref],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split("\n")
        for path in listing:
            if not path.endswith((".md", ".sh")):
                continue
            blob = subprocess.run(
                ["git", "-C", str(base), "show", f"{load().source_ref}:{path}"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            upstream_lines.update(
                line.strip()
                for line in blob.split("\n")
                if len(line.strip()) >= LICENCE_GUARD_MIN_CHARS
            )
        shipped = [
            *(REPO_ROOT / "docs").rglob("*.md"),
            *(REPO_ROOT / "src" / "cce" / "overlays").rglob("*"),
        ]
        leaks = [
            f"{path.relative_to(REPO_ROOT)}:{number}"
            for path in shipped
            if path.is_file()
            for number, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1)
            if line.strip() in upstream_lines
        ]

        assert leaks == []
