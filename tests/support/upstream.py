"""A synthetic upstream repository with dated history, served over ``file://`` (ADR-0003).

The repository contains only invented text. It carries a placeholder for every
path the packaged overlays include, an older revision of ``blueprints.md`` so
``asof=`` includes have something to find, an inert directive line to prove
included text is never re-scanned, and an ignore rule for ``*.sh`` so overlay
files must be added with ``--force``.
"""

import subprocess
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from cce.render import IncludeTarget

OLD_MARKER = "synthetic-blueprints-table-as-of-2020"
NEW_MARKER = "synthetic-blueprints-table-current"
INERT_LINE = "<!-- cce:include never-expanded.md -->"

_GIT_IDENTITY = ["-c", "user.name=synthetic", "-c", "user.email=synthetic@example.invalid"]


@dataclass(frozen=True, slots=True)
class SyntheticUpstream:
    path: Path
    head: str

    @property
    def url(self) -> str:
        return self.path.as_uri()


def build(root: Path, targets: Iterable[IncludeTarget]) -> SyntheticUpstream:
    """Create the repository under ``root`` with three dated commits."""
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q", "-b", "main")
    _write(root / "README.md", "# Synthetic upstream\n\nInvented content for tests.\n")
    _write(root / "blueprints.md", f"| Topic |\n| --- |\n| {OLD_MARKER} |\n")
    _commit(root, "Old blueprints table", "2020-01-01T00:00:00Z")
    for target in sorted(targets, key=lambda target: target.path):
        _write(root / target.path, f"Placeholder for {target.path} (synthetic upstream)\n")
    _write(root / "blueprints.md", f"| Topic |\n| --- |\n| {NEW_MARKER} |\n")
    _write(root / "inert.md", f"An included file keeps this literal line:\n{INERT_LINE}\n")
    _write(root / ".gitignore", "*.sh\n")
    _commit(root, "Current tree with placeholders", "2026-06-01T00:00:00Z")
    _write(root / "README.md", "# Synthetic upstream\n\nInvented content for tests, revised.\n")
    _commit(root, "Revise readme", "2026-07-01T00:00:00Z")
    head = _git(root, "rev-parse", "HEAD").strip()
    return SyntheticUpstream(path=root, head=head)


class GitUpstream:
    """An :class:`cce.render.UpstreamReader` backed by ``git show`` on a repository."""

    def __init__(self, repository: Path, ref: str) -> None:
        self._repository = repository
        self._ref = ref

    def read(self, path: str) -> bytes:
        return self._show(self._ref, path)

    def read_asof(self, path: str, date: str) -> bytes:
        revision = _git(
            self._repository, "rev-list", "-1", f"--before={date}T23:59:59Z", self._ref, "--", path
        ).strip()
        if not revision:
            raise FileNotFoundError(f"{path} has no revision on or before {date}")
        return self._show(revision, path)

    def tracked_paths(self) -> frozenset[str]:
        listing = _git(self._repository, "ls-tree", "-r", "--name-only", self._ref)
        return frozenset(line for line in listing.split("\n") if line)

    def _show(self, revision: str, path: str) -> bytes:
        completed = subprocess.run(
            ["git", "-C", str(self._repository), "show", f"{revision}:{path}"],
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            raise FileNotFoundError(f"{path} is not in {revision}")
        return completed.stdout


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _commit(root: Path, message: str, date: str) -> None:
    _git(root, "add", "-A", "--force")
    _git(root, *_GIT_IDENTITY, "commit", "-q", "-m", message, env_date=date)


def _git(root: Path, *args: str, env_date: str | None = None) -> str:
    env = {"GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C", "PATH": _path()}
    if env_date is not None:
        env["GIT_AUTHOR_DATE"] = env_date
        env["GIT_COMMITTER_DATE"] = env_date
    completed = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=False, env=env
    )
    if completed.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {completed.stderr}")
    return completed.stdout


def _path() -> str:
    import os

    return os.environ.get("PATH", "")


def run_git(root: Path, args: Sequence[str]) -> str:
    """Run a read-only git command in ``root`` and return stdout."""
    return _git(root, *args)
