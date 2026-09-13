"""Environment checks behind ``cce doctor`` (ADR-0006).

The checks are for the person running the scenarios, not for developers or
presenters: nothing here reports on Claude Code or herdr. Every collaborator that
touches the machine is injected through :class:`Environment`, so tests use a fake
``which`` and a real ``git``.
"""

import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from cce import CceError
from cce.manifest import Manifest
from cce.render import PlaceholderUpstream, plan_scenario

MINIMUM_GIT = (2, 31)
MINIMUM_PYTHON = (3, 14)
MINIMUM_COPILOT = (1, 0, 83)

Runner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]
Which = Callable[[str], str | None]


class Status(StrEnum):
    OK = "ok"
    WARN = "warn"
    FAIL = "fail"


@dataclass(frozen=True, slots=True)
class Check:
    name: str
    status: Status
    detail: str
    details: tuple[str, ...] = ()
    """One line per item behind the row, printed by ``--verbose`` and carried by ``--json``."""

    def as_row(self) -> str:
        return f"{self.status:<4}  {self.name:<12}  {self.detail}"

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "status": str(self.status),
            "detail": self.detail,
            "details": list(self.details),
        }


@dataclass(frozen=True, slots=True)
class Environment:
    """The machine as seen by doctor; build with :meth:`from_system` in production."""

    env: Mapping[str, str]
    home: Path
    which: Which
    run: Runner
    python_version: tuple[int, int, int]

    @classmethod
    def from_system(cls, env: Mapping[str, str]) -> Environment:
        return cls(
            env=env,
            home=Path.home(),
            which=shutil.which,
            run=_run,
            python_version=sys.version_info[:3],
        )


def run_checks(environment: Environment, manifest: Manifest, *, offline: bool) -> list[Check]:
    """Run every check and return them in display order."""
    return [
        _python(environment),
        _git(environment),
        _copilot(environment),
        _tool(environment, "uv", missing=Status.WARN, hint="needed by cce update"),
        _personal_customisation(environment),
        _overlays(manifest),
        _upstream(environment, manifest, offline=offline),
    ]


def has_failures(checks: Sequence[Check]) -> bool:
    return any(check.status is Status.FAIL for check in checks)


def _python(environment: Environment) -> Check:
    version = ".".join(str(part) for part in environment.python_version)
    if environment.python_version[:2] < MINIMUM_PYTHON:
        return Check("python", Status.FAIL, f"{version} found; 3.14 or newer is required")
    return Check("python", Status.OK, version)


def _probe(environment: Environment, argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
    """Run a probe; a crash or timeout becomes a non-zero result, never an exception."""
    try:
        return environment.run(argv)
    except (OSError, subprocess.SubprocessError) as error:
        return subprocess.CompletedProcess(list(argv), 1, "", str(error))


def _git(environment: Environment) -> Check:
    if environment.which("git") is None:
        return Check("git", Status.FAIL, "git is not on PATH")
    completed = _probe(environment, ["git", "--version"])
    match = re.search(r"(\d+)\.(\d+)", completed.stdout)
    if completed.returncode != 0 or match is None:
        return Check("git", Status.FAIL, "git --version did not report a version")
    found = (int(match.group(1)), int(match.group(2)))
    if found < MINIMUM_GIT:
        return Check(
            "git", Status.WARN, f"{completed.stdout.strip()}; 2.31 or newer is recommended"
        )
    return Check("git", Status.OK, completed.stdout.strip())


def _copilot(environment: Environment) -> Check:
    """Copilot CLI presence and version; the recorded scenario numbers assume 1.0.83."""
    if environment.which("copilot") is None:
        return Check("copilot", Status.WARN, "not found on PATH (install GitHub Copilot CLI)")
    completed = _probe(environment, ["copilot", "--version"])
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", completed.stdout + completed.stderr)
    if completed.returncode != 0 or match is None:
        return Check("copilot", Status.WARN, "copilot --version did not report a version")
    found = tuple(int(part) for part in match.groups())
    version = ".".join(match.groups())
    if found < MINIMUM_COPILOT:
        wanted = ".".join(str(part) for part in MINIMUM_COPILOT)
        return Check(
            "copilot",
            Status.WARN,
            f"{version} found; the guides were measured on {wanted} or newer",
        )
    return Check("copilot", Status.OK, f"{version} at {environment.which('copilot')}")


def _tool(environment: Environment, name: str, *, missing: Status, hint: str) -> Check:
    location = environment.which(name)
    if location is None:
        return Check(name, missing, f"not found on PATH ({hint})")
    return Check(name, Status.OK, location)


_PERSONAL_ITEMS = ("copilot-instructions.md", "skills", "agents", "hooks")
_LISTING_LIMIT = 50


def copilot_home(environment: Environment) -> Path:
    """Where Copilot keeps its global customisation: ``$COPILOT_HOME``, else ``~/.copilot``."""
    configured = environment.env.get("COPILOT_HOME")
    return Path(configured) if configured else environment.home / ".copilot"


def _personal_customisation(environment: Environment) -> Check:
    root = copilot_home(environment)
    label = "$COPILOT_HOME" if environment.env.get("COPILOT_HOME") else "~/.copilot"
    found = [item for item in _PERSONAL_ITEMS if _exists_and_not_empty(root / item)]
    if not found:
        return Check(
            "personal", Status.OK, f"no global instructions, skills, agents or hooks under {label}"
        )
    return Check(
        "personal",
        Status.WARN,
        "global instructions may skew scenario results: "
        + ", ".join(f"{label}/{item}" for item in found)
        + " (use --verbose to see the full list)",
        tuple(_listing(root, found)),
    )


def _listing(root: Path, found: Sequence[str]) -> list[str]:
    """Every file behind the personal row, relative to Copilot's home."""
    files: list[str] = []
    for item in found:
        path = root / item
        if path.is_file():
            files.append(item)
            continue
        files.extend(
            str(child.relative_to(root)) for child in sorted(path.rglob("*")) if child.is_file()
        )
    if len(files) > _LISTING_LIMIT:
        files = [*files[:_LISTING_LIMIT], f"... and {len(files) - _LISTING_LIMIT} more"]
    return files


def _exists_and_not_empty(path: Path) -> bool:
    if path.is_dir():
        return any(path.iterdir())
    return path.is_file()


def _overlays(manifest: Manifest) -> Check:
    """Render every scenario against placeholder upstream text (syntax and structure only)."""
    placeholder = PlaceholderUpstream()
    total = 0
    for scenario in manifest.scenarios:
        try:
            total += len(plan_scenario(scenario, manifest, placeholder))
        except CceError as error:
            return Check("overlays", Status.FAIL, str(error))
    return Check(
        "overlays", Status.OK, f"{len(manifest.scenarios)} scenarios render ({total} files)"
    )


def _upstream(environment: Environment, manifest: Manifest, *, offline: bool) -> Check:
    if offline:
        return Check("upstream", Status.OK, "skipped (--offline)")
    completed = _probe(
        environment, ["git", "ls-remote", "--exit-code", "--heads", manifest.source_url]
    )
    if completed.returncode != 0:
        return Check(
            "upstream",
            Status.FAIL,
            f"cannot reach {manifest.source_url} (skip this check with --offline)",
        )
    return Check(
        "upstream",
        Status.OK,
        f"{manifest.source_url} reachable (the pinned commit is verified by setup)",
    )


def _run(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(argv),
        capture_output=True,
        text=True,
        check=False,
        env={"GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C", "PATH": _path()},
        timeout=30,
    )


def _path() -> str:
    return os.environ.get("PATH", "")
