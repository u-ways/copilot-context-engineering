"""Scenario 06's ground-truth script counts fence-aware level-2 headings (ADR-0003).

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
SCOPE_PREFIX = "Scope: lines beginning with '## ' at column 0 and outside fenced code blocks, "


class GroundTruth(Protocol):
    """The part of the script's surface the tests call."""

    def count_level_two_headings(self, root: Path) -> tuple[int, dict[str, int]]: ...

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


class TestHeadingDetection:
    def test_counts_lines_starting_with_two_hashes_and_a_space(
        self, tmp_path: Path, ground_truth: GroundTruth
    ) -> None:
        write(tmp_path, "notes.md", "# Title\n\n## First\n\ntext\n\n## Second\n\n## Third\n")

        total, _ = ground_truth.count_level_two_headings(tmp_path)

        assert total == 3

    def test_ignores_other_levels_and_near_misses(
        self, tmp_path: Path, ground_truth: GroundTruth
    ) -> None:
        write(
            tmp_path,
            "notes.md",
            "# Level one\n### Level three\n#### Level four\n##x not a heading\n"
            " ## indented\n\t## tabbed\n##\n## Counted\n",
        )

        total, _ = ground_truth.count_level_two_headings(tmp_path)

        assert total == 1

    def test_counts_repeated_heading_text_as_separate_occurrences(
        self, tmp_path: Path, ground_truth: GroundTruth
    ) -> None:
        write(tmp_path, "a.md", "## Same\n\n## Same\n")
        write(tmp_path, "b.md", "## Same\n")

        total, _ = ground_truth.count_level_two_headings(tmp_path)

        assert total == 3


class TestFences:
    def test_ignores_headings_inside_backtick_fences(
        self, tmp_path: Path, ground_truth: GroundTruth
    ) -> None:
        write(tmp_path, "notes.md", "## Real\n\n```\n## Fenced\n## Also fenced\n```\n")

        total, _ = ground_truth.count_level_two_headings(tmp_path)

        assert total == 1

    def test_ignores_headings_inside_tilde_fences(
        self, tmp_path: Path, ground_truth: GroundTruth
    ) -> None:
        write(tmp_path, "notes.md", "~~~\n## Fenced\n~~~\n\n## Real\n")

        total, _ = ground_truth.count_level_two_headings(tmp_path)

        assert total == 1

    def test_a_fence_with_a_language_tag_still_opens(
        self, tmp_path: Path, ground_truth: GroundTruth
    ) -> None:
        write(tmp_path, "notes.md", "```markdown\n## Fenced\n```\n\n## Real\n")

        total, _ = ground_truth.count_level_two_headings(tmp_path)

        assert total == 1

    def test_an_indented_fence_marker_still_toggles(
        self, tmp_path: Path, ground_truth: GroundTruth
    ) -> None:
        write(tmp_path, "notes.md", "  ```\n## Fenced\n  ```\n## Real\n")

        total, _ = ground_truth.count_level_two_headings(tmp_path)

        assert total == 1

    def test_counting_resumes_after_the_fence_closes(
        self, tmp_path: Path, ground_truth: GroundTruth
    ) -> None:
        write(
            tmp_path,
            "notes.md",
            "## One\n```\n## Hidden\n```\n## Two\n~~~\n## Hidden\n~~~\n## Three\n",
        )

        total, _ = ground_truth.count_level_two_headings(tmp_path)

        assert total == 3

    def test_an_unclosed_fence_hides_the_rest_of_the_file_only(
        self, tmp_path: Path, ground_truth: GroundTruth
    ) -> None:
        write(tmp_path, "open.md", "## Seen\n```\n## Hidden\n")
        write(tmp_path, "other.md", "## Seen\n")

        total, _ = ground_truth.count_level_two_headings(tmp_path)

        assert total == 2


class TestExclusions:
    def test_skips_github_claude_and_git_directories(
        self, tmp_path: Path, ground_truth: GroundTruth
    ) -> None:
        write(tmp_path, "kept.md", "## Kept\n")
        write(tmp_path, ".github/agents/auditor.md", "## Skipped\n")
        write(tmp_path, ".claude/agents/auditor.md", "## Skipped\n")
        write(tmp_path, ".git/description.md", "## Skipped\n")

        total, tally = ground_truth.count_level_two_headings(tmp_path)

        assert total == 1
        assert list(tally) == ["kept.md"]

    def test_skips_excluded_names_at_any_depth(
        self, tmp_path: Path, ground_truth: GroundTruth
    ) -> None:
        write(tmp_path, "docs/.github/nested.md", "## Skipped\n")
        write(tmp_path, "docs/.claude/nested.md", "## Skipped\n")
        write(tmp_path, "docs/kept.md", "## Kept\n")

        total, _ = ground_truth.count_level_two_headings(tmp_path)

        assert total == 1

    def test_ignores_files_without_the_md_suffix(
        self, tmp_path: Path, ground_truth: GroundTruth
    ) -> None:
        write(tmp_path, "notes.txt", "## Not markdown\n")
        write(tmp_path, "notes.markdown", "## Not counted\n")
        write(tmp_path, "notes.md", "## Counted\n")

        total, _ = ground_truth.count_level_two_headings(tmp_path)

        assert total == 1

    def test_an_empty_tree_counts_zero(self, tmp_path: Path, ground_truth: GroundTruth) -> None:
        total, tally = ground_truth.count_level_two_headings(tmp_path)

        assert total == 0
        assert tally == {}


class TestTally:
    def test_reports_each_file_by_sorted_posix_relative_path(
        self, tmp_path: Path, ground_truth: GroundTruth
    ) -> None:
        write(tmp_path, "z/last.md", "## A\n")
        write(tmp_path, "a/deep/first.md", "## A\n## B\n")
        write(tmp_path, "middle.md", "# none here\n")

        total, tally = ground_truth.count_level_two_headings(tmp_path)

        assert total == 3
        assert tally == {"a/deep/first.md": 2, "middle.md": 0, "z/last.md": 1}
        assert list(tally) == sorted(tally)


class TestCommandLine:
    def test_prints_the_total_then_the_scope_sentence(self, tmp_path: Path) -> None:
        write(tmp_path, "one.md", "## A\n## B\n")
        write(tmp_path, "two.md", "```\n## Hidden\n```\n## C\n")

        result = run_script(tmp_path, str(tmp_path))

        assert result.returncode == 0
        assert result.stderr == ""
        assert result.stdout.splitlines() == [
            "3",
            f"{SCOPE_PREFIX}in every *.md file under {tmp_path} "
            "excluding .git, .github and .claude.",
        ]

    def test_defaults_to_the_current_directory(self, tmp_path: Path) -> None:
        write(tmp_path, "one.md", "## A\n")

        result = run_script(tmp_path)

        assert result.returncode == 0
        assert result.stdout.splitlines() == [
            "1",
            f"{SCOPE_PREFIX}in every *.md file under . excluding .git, .github and .claude.",
        ]

    def test_main_is_importable_and_returns_zero(
        self, tmp_path: Path, ground_truth: GroundTruth, capsys: pytest.CaptureFixture[str]
    ) -> None:
        write(tmp_path, "one.md", "## A\n")

        code = ground_truth.main([str(tmp_path)])

        captured = capsys.readouterr()
        assert code == 0
        assert captured.out.splitlines()[0] == "1"

    def test_a_missing_root_fails_with_exit_code_two(self, tmp_path: Path) -> None:
        result = run_script(tmp_path, str(tmp_path / "absent"))

        assert result.returncode == 2
        assert result.stdout == ""
        assert "not a directory" in result.stderr
