"""Scenario 06's ground-truth script counts the pages without a Context section (ADR-0003).

The upstream repository is never committed, so the count the auditor agent must
reproduce is derived at runtime by ``scripts/s06_ground_truth.py``. The e2e tier runs
that script against the pinned clone; here it runs over an invented Markdown tree.
"""

import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import Protocol, cast

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "s06_ground_truth.py"
SCOPE_TAIL = (
    "and a root CLAUDE.md or AGENTS.md, "
    "counting files with no '## Context' line at column 0 outside fenced code blocks."
)


class GroundTruth(Protocol):
    """The part of the script's surface the tests call."""

    def pages_without_context(self, root: Path) -> tuple[int, dict[str, bool]]: ...

    def main(self, argv: list[str] | None = None) -> int: ...


@pytest.fixture(scope="module")
def ground_truth() -> GroundTruth:
    spec = importlib.util.spec_from_file_location("s06_ground_truth", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return cast(GroundTruth, module)


def write(root: Path, relative: str, text: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def run_script(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


class TestSectionDetection:
    def test_a_page_with_the_section_is_not_counted(
        self, tmp_path: Path, ground_truth: GroundTruth
    ) -> None:
        write(tmp_path, "with.md", "# Title\n\n## Context\n\ntext\n")
        write(tmp_path, "without.md", "# Title\n\n## Summary\n\ntext\n")

        missing, per_file = ground_truth.pages_without_context(tmp_path)

        assert missing == 1
        assert per_file == {"with.md": True, "without.md": False}

    def test_only_an_exact_level_two_context_line_counts(
        self, tmp_path: Path, ground_truth: GroundTruth
    ) -> None:
        write(tmp_path, "three.md", "### Context\n")
        write(tmp_path, "longer.md", "## Contextual notes\n")
        write(tmp_path, "indented.md", " ## Context\n")
        write(tmp_path, "trailing.md", "## Context   \n")
        write(tmp_path, "exact.md", "## Context\n")

        missing, per_file = ground_truth.pages_without_context(tmp_path)

        assert missing == 3
        assert per_file["trailing.md"] is True
        assert per_file["exact.md"] is True

    def test_the_section_may_appear_anywhere_in_the_page(
        self, tmp_path: Path, ground_truth: GroundTruth
    ) -> None:
        write(tmp_path, "late.md", "# Title\n\n## Intro\n\n## Usage\n\n## Context\n")

        missing, _ = ground_truth.pages_without_context(tmp_path)

        assert missing == 0


class TestFences:
    def test_a_section_inside_a_backtick_fence_does_not_count(
        self, tmp_path: Path, ground_truth: GroundTruth
    ) -> None:
        write(tmp_path, "notes.md", "# Title\n\n```\n## Context\n```\n")

        missing, _ = ground_truth.pages_without_context(tmp_path)

        assert missing == 1

    def test_a_section_inside_a_tilde_fence_does_not_count(
        self, tmp_path: Path, ground_truth: GroundTruth
    ) -> None:
        write(tmp_path, "notes.md", "~~~\n## Context\n~~~\n")

        missing, _ = ground_truth.pages_without_context(tmp_path)

        assert missing == 1

    def test_a_fence_with_a_language_tag_still_opens(
        self, tmp_path: Path, ground_truth: GroundTruth
    ) -> None:
        write(tmp_path, "notes.md", "```markdown\n## Context\n```\n")

        missing, _ = ground_truth.pages_without_context(tmp_path)

        assert missing == 1

    def test_an_indented_fence_marker_still_toggles(
        self, tmp_path: Path, ground_truth: GroundTruth
    ) -> None:
        write(tmp_path, "notes.md", "  ```\n## Context\n  ```\n")

        missing, _ = ground_truth.pages_without_context(tmp_path)

        assert missing == 1

    def test_detection_resumes_after_the_fence_closes(
        self, tmp_path: Path, ground_truth: GroundTruth
    ) -> None:
        write(tmp_path, "notes.md", "```\n## Context\n```\n\n## Context\n")

        missing, _ = ground_truth.pages_without_context(tmp_path)

        assert missing == 0

    def test_an_unclosed_fence_hides_the_rest_of_the_file_only(
        self, tmp_path: Path, ground_truth: GroundTruth
    ) -> None:
        write(tmp_path, "open.md", "```\n## Context\n")
        write(tmp_path, "other.md", "## Context\n")

        missing, _ = ground_truth.pages_without_context(tmp_path)

        assert missing == 1


class TestExclusions:
    def test_skips_github_claude_and_git_directories(
        self, tmp_path: Path, ground_truth: GroundTruth
    ) -> None:
        write(tmp_path, "kept.md", "## Summary\n")
        write(tmp_path, ".github/agents/auditor.md", "## Summary\n")
        write(tmp_path, ".claude/agents/auditor.md", "## Summary\n")
        write(tmp_path, ".git/description.md", "## Summary\n")

        missing, per_file = ground_truth.pages_without_context(tmp_path)

        assert missing == 1
        assert list(per_file) == ["kept.md"]

    def test_skips_assistant_configuration_files_at_the_root_only(
        self, tmp_path: Path, ground_truth: GroundTruth
    ) -> None:
        write(tmp_path, "CLAUDE.md", "# Instructions\n")
        write(tmp_path, "AGENTS.md", "# Rules\n")
        write(tmp_path, "docs/CLAUDE.md", "# A page that happens to share the name\n")
        write(tmp_path, "page.md", "## Context\n")

        missing, per_file = ground_truth.pages_without_context(tmp_path)

        assert missing == 1
        assert list(per_file) == ["docs/CLAUDE.md", "page.md"]

    def test_skips_excluded_names_at_any_depth(
        self, tmp_path: Path, ground_truth: GroundTruth
    ) -> None:
        write(tmp_path, "docs/.github/nested.md", "## Summary\n")
        write(tmp_path, "docs/.claude/nested.md", "## Summary\n")
        write(tmp_path, "docs/kept.md", "## Summary\n")

        missing, _ = ground_truth.pages_without_context(tmp_path)

        assert missing == 1

    def test_ignores_files_without_the_md_suffix(
        self, tmp_path: Path, ground_truth: GroundTruth
    ) -> None:
        write(tmp_path, "notes.txt", "## Summary\n")
        write(tmp_path, "notes.markdown", "## Summary\n")
        write(tmp_path, "notes.md", "## Summary\n")

        missing, _ = ground_truth.pages_without_context(tmp_path)

        assert missing == 1

    def test_an_empty_tree_counts_zero(self, tmp_path: Path, ground_truth: GroundTruth) -> None:
        missing, per_file = ground_truth.pages_without_context(tmp_path)

        assert missing == 0
        assert per_file == {}


class TestPerFile:
    def test_reports_each_file_by_sorted_posix_relative_path(
        self, tmp_path: Path, ground_truth: GroundTruth
    ) -> None:
        write(tmp_path, "z/last.md", "## Context\n")
        write(tmp_path, "a/deep/first.md", "## A\n## B\n")
        write(tmp_path, "middle.md", "# none here\n")

        missing, per_file = ground_truth.pages_without_context(tmp_path)

        assert missing == 2
        assert per_file == {"a/deep/first.md": False, "middle.md": False, "z/last.md": True}
        assert list(per_file) == sorted(per_file)


class TestCommandLine:
    def test_prints_the_count_then_the_scope_sentence(self, tmp_path: Path) -> None:
        write(tmp_path, "one.md", "## Context\n")
        write(tmp_path, "two.md", "```\n## Context\n```\n")
        write(tmp_path, "three.md", "## Summary\n")

        result = run_script(tmp_path, str(tmp_path))

        assert result.returncode == 0
        assert result.stderr == ""
        assert result.stdout.splitlines() == [
            "2",
            f"Scope: 3 *.md files under {tmp_path} excluding .git, .github, .claude " + SCOPE_TAIL,
        ]

    def test_defaults_to_the_current_directory(self, tmp_path: Path) -> None:
        write(tmp_path, "one.md", "## Summary\n")

        result = run_script(tmp_path)

        assert result.returncode == 0
        assert result.stdout.splitlines() == [
            "1",
            "Scope: 1 *.md files under . excluding .git, .github, .claude " + SCOPE_TAIL,
        ]

    def test_main_is_importable_and_returns_zero(
        self, tmp_path: Path, ground_truth: GroundTruth, capsys: pytest.CaptureFixture[str]
    ) -> None:
        write(tmp_path, "one.md", "## Summary\n")

        code = ground_truth.main([str(tmp_path)])

        captured = capsys.readouterr()
        assert code == 0
        assert captured.out.splitlines()[0] == "1"

    def test_a_missing_root_fails_with_exit_code_two(self, tmp_path: Path) -> None:
        result = run_script(tmp_path, str(tmp_path / "absent"))

        assert result.returncode == 2
        assert result.stdout == ""
        assert "not a directory" in result.stderr
