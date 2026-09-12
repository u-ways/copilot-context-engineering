"""Environment checks behind ``cce doctor`` (ADR-0006).

Every collaborator that touches the machine is injected through
:class:`Environment`, so tests use a fake ``which`` and a real ``git``.
"""

import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from cce.manifest import Manifest

MINIMUM_GIT = (2, 31)
MINIMUM_PYTHON = (3, 14)

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

    def as_row(self) -> str:
        return f"{self.status:<4}  {self.name:<12}  {self.detail}"

    def as_dict(self) -> dict[str, str]:
        return {"name": self.name, "status": str(self.status), "detail": self.detail}


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
    checks = [
        _python(environment),
        _git(environment),
        _tool(environment, "copilot", missing=Status.WARN, hint="install GitHub Copilot CLI"),
        _tool(
            environment,
            "claude",
            missing=Status.OK,
            hint="optional; only the Claude dialect uses it",
        ),
        _tool(environment, "uv", missing=Status.WARN, hint="needed by cce update"),
    ]
    if environment.env.get("HERDR_ENV") == "1":
        checks.append(
            _tool(environment, "herdr", missing=Status.WARN, hint="presenter mode needs it")
        )
    checks.append(_personal_customisation(environment))
    checks.append(_upstream(environment, manifest, offline=offline))
    return checks


def has_failures(checks: Sequence[Check]) -> bool:
    return any(check.status is Status.FAIL for check in checks)


def _python(environment: Environment) -> Check:
    version = ".".join(str(part) for part in environment.python_version)
    if environment.python_version[:2] < MINIMUM_PYTHON:
        return Check("python", Status.FAIL, f"{version} found; 3.14 or newer is required")
    return Check("python", Status.OK, version)


def _git(environment: Environment) -> Check:
    if environment.which("git") is None:
        return Check("git", Status.FAIL, "git is not on PATH")
    completed = environment.run(["git", "--version"])
    match = re.search(r"(\d+)\.(\d+)", completed.stdout)
    if completed.returncode != 0 or match is None:
        return Check("git", Status.FAIL, "git --version did not report a version")
    found = (int(match.group(1)), int(match.group(2)))
    if found < MINIMUM_GIT:
        return Check(
            "git", Status.WARN, f"{completed.stdout.strip()}; 2.31 or newer is recommended"
        )
    return Check("git", Status.OK, completed.stdout.strip())


def _tool(environment: Environment, name: str, *, missing: Status, hint: str) -> Check:
    location = environment.which(name)
    if location is None:
        return Check(name, missing, f"not found on PATH ({hint})")
    return Check(name, Status.OK, location)


_PERSONAL_PATHS = (
    ".copilot/skills",
    ".copilot/agents",
    ".copilot/hooks",
    ".copilot/copilot-instructions.md",
    ".claude/skills",
)


def _personal_customisation(environment: Environment) -> Check:
    found = [
        relative
        for relative in _PERSONAL_PATHS
        if _exists_and_not_empty(environment.home / relative)
    ]
    if _has_claude_hooks(environment.home / ".claude" / "settings.json"):
        found.append(".claude/settings.json hooks")
    if not found:
        return Check("personal", Status.OK, "no personal skills, agents, hooks or instructions")
    return Check(
        "personal",
        Status.WARN,
        "may skew scenario results: " + ", ".join("~/" + item for item in found),
    )


def _exists_and_not_empty(path: Path) -> bool:
    if path.is_dir():
        return any(path.iterdir())
    return path.is_file()


def _has_claude_hooks(settings: Path) -> bool:
    if not settings.is_file():
        return False
    try:
        data = json.loads(settings.read_text(encoding="utf-8"))
    except OSError, ValueError:
        return False
    return isinstance(data, dict) and bool(data.get("hooks"))


def _upstream(environment: Environment, manifest: Manifest, *, offline: bool) -> Check:
    if offline:
        return Check("upstream", Status.OK, "skipped (--offline)")
    completed = environment.run(["git", "ls-remote", "--exit-code", "--heads", manifest.source_url])
    if completed.returncode != 0:
        return Check("upstream", Status.FAIL, f"cannot reach {manifest.source_url}")
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
