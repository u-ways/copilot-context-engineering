"""The shipped link validator reports missing targets, fragments and bare emails (ADR-0005).

The script runs inside a scenario worktree with the user's own ``python3``, so
every test executes it as a subprocess against a synthetic Markdown tree.
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "src" / "cce" / "overlays" / "_shared" / "scripts" / "cce-check-links.py"


def write(root: Path, relative: str, text: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def run_checker(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )


class TestCleanTree:
    def test_passes_with_the_exact_summary_line(self, tmp_path: Path) -> None:
        write(tmp_path, "README.md", "# Guide\n\nSee [the notes](docs/notes.md#detail).\n")
        write(tmp_path, "docs/notes.md", "# Notes\n\n## Detail\n\nBack to [home](../README.md).\n")

        result = run_checker(tmp_path)

        assert result.returncode == 0
        assert result.stdout.splitlines() == [
            "scanned 2 markdown files, 2 inline links (0 external, 2 relative paths, 1 fragments)",
            "missing relative targets : 0",
            "unresolved fragments : 0",
            "email targets without mailto: : 0",
            "RESULT: PASS",
        ]

    def test_root_defaults_to_the_current_directory(self, tmp_path: Path) -> None:
        write(tmp_path, "one.md", "[two](two.md)\n")
        write(tmp_path, "two.md", "[one](one.md)\n")

        explicit = run_checker(tmp_path, str(tmp_path))
        implicit = run_checker(tmp_path)

        assert explicit.stdout == implicit.stdout
        assert explicit.returncode == implicit.returncode == 0

    def test_external_links_are_counted_but_never_checked(self, tmp_path: Path) -> None:
        write(
            tmp_path,
            "README.md",
            "[web](https://example.test/x) [plain](http://example.test) "
            "[phone](tel:+441234567890) [ftp](ftp://example.test/f) "
            "[mail](mailto:team@example.test)\n",
        )

        result = run_checker(tmp_path)

        assert result.returncode == 0
        assert result.stdout.startswith(
            "scanned 1 markdown files, 5 inline links (5 external, 0 relative paths, 0 fragments)"
        )


class TestMissingTargets:
    def test_a_missing_relative_target_fails(self, tmp_path: Path) -> None:
        write(tmp_path, "README.md", "Intro.\n\nSee [gone](docs/gone.md).\n")

        result = run_checker(tmp_path)

        assert result.returncode == 1
        assert "missing relative targets : 1" in result.stdout
        assert "  README.md:3 -> docs/gone.md" in result.stdout
        assert result.stdout.endswith("RESULT: FAIL\n")

    def test_targets_resolve_relative_to_the_containing_file(self, tmp_path: Path) -> None:
        write(tmp_path, "docs/a/deep.md", "[up](../sibling.md) [root](/README.md) [dir](../)\n")
        write(tmp_path, "docs/sibling.md", "ok\n")
        write(tmp_path, "README.md", "ok\n")

        result = run_checker(tmp_path)

        assert result.returncode == 0, result.stdout
        assert "missing relative targets : 0" in result.stdout

    def test_a_target_above_the_root_is_missing_even_if_the_file_exists(
        self, tmp_path: Path
    ) -> None:
        write(tmp_path, "outside.md", "ok\n")
        write(tmp_path, "repo/README.md", "[escape](../outside.md)\n")

        result = run_checker(tmp_path / "repo")

        assert result.returncode == 1
        assert "  README.md:1 -> ../outside.md" in result.stdout

    def test_a_percent_encoded_path_that_exists_passes(self, tmp_path: Path) -> None:
        write(tmp_path, "README.md", "[spaced](docs/my%20page.md) [angled](<docs/my page.md>)\n")
        write(tmp_path, "docs/my page.md", "ok\n")

        result = run_checker(tmp_path)

        assert result.returncode == 0, result.stdout
        assert "2 relative paths" in result.stdout


class TestFragments:
    def test_an_unresolved_fragment_fails_while_a_resolved_one_passes(self, tmp_path: Path) -> None:
        write(tmp_path, "README.md", "[ok](notes.md#setup) [bad](notes.md#teardown)\n")
        write(tmp_path, "notes.md", "# Notes\n\n## Setup\n")

        result = run_checker(tmp_path)

        assert result.returncode == 1
        assert "unresolved fragments : 1" in result.stdout
        assert "  README.md:1 -> notes.md#teardown" in result.stdout
        assert "notes.md#setup" not in result.stdout

    def test_same_file_fragments_resolve_against_the_containing_file(self, tmp_path: Path) -> None:
        write(tmp_path, "README.md", "## Getting Started\n\n[jump](#getting-started) [no](#nope)\n")

        result = run_checker(tmp_path)

        assert result.returncode == 1
        assert "(0 external, 0 relative paths, 2 fragments)" in result.stdout
        assert "unresolved fragments : 1" in result.stdout
        assert "  README.md:3 -> #nope" in result.stdout

    def test_slugs_strip_links_and_entities_like_github(self, tmp_path: Path) -> None:
        write(
            tmp_path,
            "README.md",
            "[a](notes.md#tools--and-scripts)\n"
            "[b](notes.md#running-tests-locally)\n"
            "[c](notes.md#snake_case_names)\n"
            "[d](notes.md#emphasis)\n",
        )
        write(
            tmp_path,
            "notes.md",
            "## [Tools](tools.md) &mdash; and `scripts`\n"
            "## Running tests, locally!\n"
            "## snake_case_names\n"
            "## _Emphasis_\n",
        )
        write(tmp_path, "tools.md", "ok\n")

        result = run_checker(tmp_path)

        assert result.returncode == 0, result.stdout

    def test_duplicate_headings_get_numeric_suffixes(self, tmp_path: Path) -> None:
        write(tmp_path, "README.md", "[first](notes.md#step) [second](notes.md#step-1)\n")
        write(tmp_path, "notes.md", "## Step\n\ntext\n\n## Step\n")

        result = run_checker(tmp_path)

        assert result.returncode == 0, result.stdout

    def test_html_anchors_count_as_targets(self, tmp_path: Path) -> None:
        write(tmp_path, "README.md", "[named](notes.md#legacy) [by-id](notes.md#custom-id)\n")
        write(tmp_path, "notes.md", '<a name="legacy"></a>\n\n<div id="custom-id">box</div>\n')

        result = run_checker(tmp_path)

        assert result.returncode == 0, result.stdout

    def test_headings_inside_fences_are_not_anchors(self, tmp_path: Path) -> None:
        write(tmp_path, "README.md", "[x](notes.md#fake-heading)\n")
        write(tmp_path, "notes.md", "```md\n## Fake heading\n```\n")

        result = run_checker(tmp_path)

        assert result.returncode == 1
        assert "  README.md:1 -> notes.md#fake-heading" in result.stdout

    def test_fragments_on_non_markdown_targets_are_not_checked(self, tmp_path: Path) -> None:
        write(tmp_path, "README.md", "[svg](diagram.svg#layer-1)\n")
        write(tmp_path, "diagram.svg", "<svg></svg>\n")

        result = run_checker(tmp_path)

        assert result.returncode == 0, result.stdout


class TestCodeIsIgnored:
    def test_links_inside_fenced_blocks_are_ignored(self, tmp_path: Path) -> None:
        write(
            tmp_path,
            "README.md",
            "```markdown\n[nope](missing.md)\n```\n\n~~~\n[nope](also-missing.md)\n~~~\n",
        )

        result = run_checker(tmp_path)

        assert result.returncode == 0
        assert "0 inline links" in result.stdout

    def test_links_inside_code_spans_are_ignored(self, tmp_path: Path) -> None:
        write(tmp_path, "README.md", "Use `[text](missing.md)` syntax; see [real](real.md).\n")
        write(tmp_path, "real.md", "ok\n")

        result = run_checker(tmp_path)

        assert result.returncode == 0, result.stdout
        assert "1 inline links" in result.stdout


class TestEmailTargets:
    def test_a_bare_email_target_fails(self, tmp_path: Path) -> None:
        write(tmp_path, "SECURITY.md", "Intro.\n\nReport to [the team](security@example.test).\n")

        result = run_checker(tmp_path)

        assert result.returncode == 1
        assert "email targets without mailto: : 1" in result.stdout
        assert "  SECURITY.md:3 -> security@example.test" in result.stdout
        assert "missing relative targets : 0" in result.stdout

    def test_a_mailto_link_is_external_and_passes(self, tmp_path: Path) -> None:
        write(tmp_path, "SECURITY.md", "Report to [the team](mailto:security@example.test).\n")

        result = run_checker(tmp_path)

        assert result.returncode == 0
        assert "1 external" in result.stdout
        assert "email targets without mailto: : 0" in result.stdout


class TestImages:
    def test_images_are_checked_like_links(self, tmp_path: Path) -> None:
        write(
            tmp_path,
            "README.md",
            '![logo](assets/logo.png "Logo") ![lost](assets/lost.png)\n'
            "[![badge](assets/badge.svg)](docs/status.md)\n",
        )
        write(tmp_path, "assets/logo.png", "png\n")
        write(tmp_path, "assets/badge.svg", "svg\n")

        result = run_checker(tmp_path)

        assert result.returncode == 1
        assert "4 inline links" in result.stdout
        assert "missing relative targets : 2" in result.stdout
        assert "  README.md:1 -> assets/lost.png" in result.stdout
        assert "  README.md:2 -> docs/status.md" in result.stdout


class TestSkippedDirectories:
    def test_tooling_directories_are_not_scanned(self, tmp_path: Path) -> None:
        write(tmp_path, "README.md", "ok\n")
        write(tmp_path, ".github/PULL_REQUEST_TEMPLATE.md", "[x](missing.md)\n")
        write(tmp_path, ".claude/skills/demo/SKILL.md", "[x](missing.md)\n")
        write(tmp_path, ".git/COMMIT_EDITMSG.md", "[x](missing.md)\n")

        result = run_checker(tmp_path)

        assert result.returncode == 0, result.stdout
        assert result.stdout.startswith("scanned 1 markdown files, 0 inline links")

    def test_links_may_still_point_into_skipped_directories(self, tmp_path: Path) -> None:
        write(tmp_path, "README.md", "[workflow](.github/workflows/ci.yml)\n")
        write(tmp_path, ".github/workflows/ci.yml", "name: ci\n")

        result = run_checker(tmp_path)

        assert result.returncode == 0, result.stdout


class TestExitCodes:
    def test_findings_of_every_class_share_exit_code_one(self, tmp_path: Path) -> None:
        write(
            tmp_path,
            "README.md",
            "## Only\n\n[gone](gone.md) [frag](#nothing) [mail](someone@example.test)\n",
        )

        result = run_checker(tmp_path)

        assert result.returncode == 1
        assert result.stdout.splitlines() == [
            "scanned 1 markdown files, 3 inline links (0 external, 1 relative paths, 1 fragments)",
            "missing relative targets : 1",
            "  README.md:3 -> gone.md",
            "unresolved fragments : 1",
            "  README.md:3 -> #nothing",
            "email targets without mailto: : 1",
            "  README.md:3 -> someone@example.test",
            "RESULT: FAIL",
        ]

    def test_an_empty_tree_passes(self, tmp_path: Path) -> None:
        result = run_checker(tmp_path)

        assert result.returncode == 0
        assert result.stdout.splitlines()[0] == (
            "scanned 0 markdown files, 0 inline links (0 external, 0 relative paths, 0 fragments)"
        )

    def test_a_root_that_is_not_a_directory_is_a_usage_error(self, tmp_path: Path) -> None:
        result = run_checker(tmp_path, str(tmp_path / "absent"))

        assert result.returncode == 2
        assert result.stdout == ""
        assert "not a directory" in result.stderr
