"""Ground truth for scenario 06: count the Markdown pages without a ``## Context`` section.

Usage::

    python scripts/s06_ground_truth.py [ROOT]

ROOT defaults to the current directory. The script walks every ``*.md`` file under
ROOT (sorted, recursive), skipping any path that has a component named ``.git``,
``.github`` or ``.claude``, and counts the files that have no line reading exactly
``## Context`` (at column 0, outside a fenced code block). It prints that
number followed by one sentence describing the scope, and nothing else. Standard
library only.
"""

import sys
from pathlib import Path

EXCLUDED_DIRS = frozenset({".git", ".github", ".claude"})
FENCE_MARKERS = ("```", "~~~")
SECTION_LINE = "## Context"


def is_excluded(relative: Path) -> bool:
    """True when any component of the path is one of the excluded directory names."""
    return any(part in EXCLUDED_DIRS for part in relative.parts)


def markdown_files(root: Path) -> list[Path]:
    """Every ``*.md`` file under ``root`` that is not in an excluded directory, sorted."""
    return sorted(
        path
        for path in root.rglob("*.md")
        if path.is_file() and not is_excluded(path.relative_to(root))
    )


def has_context_section(text: str) -> bool:
    """True when a line reading exactly ``## Context`` sits outside fenced code blocks.

    A fence opens or closes on any line whose stripped form starts with ``\\`\\`\\```
    or ``~~~``; both markers toggle the same state.
    """
    in_fence = False
    for line in text.splitlines():
        if line.strip().startswith(FENCE_MARKERS):
            in_fence = not in_fence
            continue
        if not in_fence and line.rstrip() == SECTION_LINE:
            return True
    return False


def pages_without_context(root: Path) -> tuple[int, dict[str, bool]]:
    """Return the number of pages lacking the section and a per-file map of who has it."""
    per_file = {
        path.relative_to(root).as_posix(): has_context_section(
            path.read_text(encoding="utf-8", errors="replace")
        )
        for path in markdown_files(root)
    }
    return sum(1 for present in per_file.values() if not present), per_file


def scope_sentence(root: str, examined: int) -> str:
    """The one-line description of what was audited, naming ``root`` as given."""
    return (
        f"Scope: {examined} *.md files under {root} excluding .git, .github and .claude, "
        "counting files with no '## Context' line at column 0 outside fenced code blocks."
    )


def main(argv: list[str] | None = None) -> int:
    """Print the count and the scope sentence; return the process exit code."""
    args = sys.argv[1:] if argv is None else argv
    root_arg = args[0] if args else "."
    root = Path(root_arg)
    if not root.is_dir():
        print(f"error: {root_arg} is not a directory", file=sys.stderr)
        return 2
    missing, per_file = pages_without_context(root)
    print(missing)
    print(scope_sentence(root_arg, len(per_file)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
