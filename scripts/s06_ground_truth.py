"""Ground truth for scenario 06: count level-2 Markdown headings outside code fences.

Usage::

    python scripts/s06_ground_truth.py [ROOT]

ROOT defaults to the current directory. The script walks every ``*.md`` file under
ROOT (sorted, recursive), skipping any path that has a component named ``.git``,
``.github`` or ``.claude``, and counts the lines that start with exactly ``## `` at
column 0 and sit outside a fenced code block. It prints the total followed by one
sentence describing the scope, and nothing else. Standard library only.
"""

import sys
from pathlib import Path

EXCLUDED_DIRS = frozenset({".git", ".github", ".claude"})
FENCE_MARKERS = ("```", "~~~")
HEADING_PREFIX = "## "


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


def count_in_text(text: str) -> int:
    """Count ``## `` lines at column 0 that are outside fenced code blocks.

    A fence opens or closes on any line whose stripped form starts with ``\\`\\`\\```
    or ``~~~``; both markers toggle the same state.
    """
    total = 0
    in_fence = False
    for line in text.splitlines():
        if line.strip().startswith(FENCE_MARKERS):
            in_fence = not in_fence
            continue
        if not in_fence and line.startswith(HEADING_PREFIX):
            total += 1
    return total


def count_level_two_headings(root: Path) -> tuple[int, dict[str, int]]:
    """Return the grand total and a per-file tally keyed by posix path relative to ``root``."""
    tally = {
        path.relative_to(root).as_posix(): count_in_text(
            path.read_text(encoding="utf-8", errors="replace")
        )
        for path in markdown_files(root)
    }
    return sum(tally.values()), tally


def scope_sentence(root: str) -> str:
    """The one-line description of what was counted, naming ``root`` as given."""
    return (
        "Scope: lines beginning with '## ' at column 0 and outside fenced code blocks, "
        f"in every *.md file under {root} excluding .git, .github and .claude."
    )


def main(argv: list[str] | None = None) -> int:
    """Print the total and the scope sentence; return the process exit code."""
    args = sys.argv[1:] if argv is None else argv
    root_arg = args[0] if args else "."
    root = Path(root_arg)
    if not root.is_dir():
        print(f"error: {root_arg} is not a directory", file=sys.stderr)
        return 2
    total, _ = count_level_two_headings(root)
    print(total)
    print(scope_sentence(root_arg))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
