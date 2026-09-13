"""Opt-in presenter layout over the herdr JSON command line (ADR-0008).

Nothing here runs unless ``cce setup --herdr`` or ``cce teardown --herdr`` is
given. Every herdr call goes through :class:`Herdr`, whose runner is injected
so tests use a fake ``herdr`` executable on PATH.
"""

import json
import shlex
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cce import CceError
from cce.log import get_logger
from cce.manifest import Manifest, Scenario

LABEL_PREFIX = "cce:"
DEMO_LABEL = "cce:demo"
RECORD_FILE = "herdr.json"

Runner = Callable[..., subprocess.CompletedProcess[str]]
Which = Callable[[str], str | None]

log = get_logger("cce.herdr")


class HerdrError(CceError):
    """A herdr subcommand failed or answered with something that is not JSON."""


@dataclass(frozen=True, slots=True)
class PlannedTab:
    label: str
    command: str


@dataclass(frozen=True, slots=True)
class PlannedWorkspace:
    label: str
    cwd: Path
    tabs: tuple[PlannedTab, ...]


def plan_layout(
    manifest: Manifest,
    workspace_root: Path,
    scenario_paths: Mapping[str, Path],
    overlay_files: Mapping[str, Sequence[str]],
) -> list[PlannedWorkspace]:
    """The DEMO workspace plus one workspace per ready scenario, in manifest order."""
    demo = PlannedWorkspace(
        DEMO_LABEL,
        workspace_root,
        (
            PlannedTab("presenting", "cce guide presenting | less -R"),
            PlannedTab("status", "cce list"),
        ),
    )
    layout = [demo]
    for scenario in manifest.scenarios:
        if scenario.slug not in scenario_paths:
            continue
        files = " ".join(shlex.quote(path) for path in overlay_files.get(scenario.slug, ()))
        tabs = [
            PlannedTab("guide", f"cce guide {scenario.id} | less -R"),
            PlannedTab("overlay", f"less -R {files}".rstrip()),
            PlannedTab("copilot", "copilot"),
        ]
        tabs.extend(PlannedTab(tab.label, tab.command) for tab in scenario.tabs)
        layout.append(
            PlannedWorkspace(_label(scenario), scenario_paths[scenario.slug], tuple(tabs))
        )
    return layout


class Herdr:
    """Thin client over ``herdr <group> <verb> ... --json`` answers."""

    def __init__(self, runner: Runner = subprocess.run, executable: str = "herdr") -> None:
        self._runner = runner
        self._executable = executable

    def workspace_labels(self) -> list[str]:
        result = self._call("workspace", "list")
        workspaces = result.get("workspaces", [])
        return [str(item.get("label", "")) for item in workspaces if isinstance(item, dict)]

    def create_workspace(self, cwd: Path, label: str) -> tuple[str, str, str]:
        result = self._call(
            "workspace", "create", "--cwd", str(cwd), "--label", label, "--no-focus"
        )
        return (
            _id(result, "workspace", "workspace_id"),
            _id(result, "tab", "tab_id"),
            _id(result, "root_pane", "pane_id"),
        )

    def create_tab(self, workspace_id: str, cwd: Path, label: str) -> tuple[str, str]:
        result = self._call(
            "tab",
            "create",
            "--workspace",
            workspace_id,
            "--cwd",
            str(cwd),
            "--label",
            label,
            "--no-focus",
        )
        return _id(result, "tab", "tab_id"), _id(result, "root_pane", "pane_id")

    def rename_tab(self, tab_id: str, label: str) -> None:
        self._call("tab", "rename", tab_id, label)

    def run_in_pane(self, pane_id: str, command: str) -> None:
        self._call("pane", "run", pane_id, command)

    def focus_workspace(self, workspace_id: str) -> None:
        self._call("workspace", "focus", workspace_id)

    def close_workspace(self, workspace_id: str) -> None:
        self._call("workspace", "close", workspace_id)

    def _call(self, *args: str) -> dict[str, Any]:
        completed: subprocess.CompletedProcess[str] = self._runner(
            [self._executable, *args], capture_output=True, text=True, check=False
        )
        subcommand = " ".join(args[:2])
        if completed.returncode != 0:
            raise HerdrError(
                f"herdr {subcommand} failed: {completed.stderr.strip() or completed.stdout.strip()}"
            )
        try:
            payload = json.loads(completed.stdout)
        except ValueError as error:
            raise HerdrError(f"herdr {subcommand} did not answer with JSON") from error
        result = payload.get("result") if isinstance(payload, dict) else None
        if not isinstance(result, dict):
            raise HerdrError(f"herdr {subcommand} answered without a result object")
        return result


def preflight(
    env: Mapping[str, str], which: Which, herdr: Herdr, layout: Sequence[PlannedWorkspace]
) -> None:
    """Refuse before any mutation unless herdr is usable and no label collides."""
    if env.get("HERDR_ENV") != "1":
        raise CceError("presenter mode needs HERDR_ENV=1; run cce inside herdr", exit_code=3)
    if which("herdr") is None:
        raise CceError("presenter mode needs the herdr executable on PATH", exit_code=3)
    existing = set(herdr.workspace_labels())
    collisions = [item.label for item in layout if item.label in existing]
    if collisions:
        raise CceError(
            "herdr already has workspaces labelled "
            + ", ".join(collisions)
            + "; close them or run `cce teardown --herdr`",
            exit_code=3,
        )


def apply_layout(herdr: Herdr, layout: Sequence[PlannedWorkspace], record: Path) -> list[str]:
    """Create every workspace and tab; each workspace id is recorded as soon as it exists."""
    created: list[str] = []
    for item in layout:
        workspace_id, first_tab, first_pane = herdr.create_workspace(item.cwd, item.label)
        created.append(workspace_id)
        _write_record(record, created)
        log.info("created herdr workspace", label=item.label, id=workspace_id)
        first, *rest = item.tabs
        herdr.rename_tab(first_tab, first.label)
        herdr.run_in_pane(first_pane, first.command)
        for tab in rest:
            _, pane = herdr.create_tab(workspace_id, item.cwd, tab.label)
            herdr.run_in_pane(pane, tab.command)
    if created:
        herdr.focus_workspace(created[0])
    return created


def close_layout(herdr: Herdr, record: Path) -> list[str]:
    """Close only the workspaces ``apply_layout`` recorded; forget them afterwards."""
    ids = read_record(record)
    for workspace_id in ids:
        herdr.close_workspace(workspace_id)
    if record.exists():
        record.unlink()
    return ids


def read_record(record: Path) -> list[str]:
    if not record.is_file():
        return []
    try:
        data = json.loads(record.read_text(encoding="utf-8"))
    except ValueError:
        return []
    ids = data.get("workspaces", []) if isinstance(data, dict) else []
    return [str(item) for item in ids]


def _write_record(record: Path, ids: Sequence[str]) -> None:
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text(json.dumps({"workspaces": list(ids)}, indent=2) + "\n", encoding="utf-8")


def _label(scenario: Scenario) -> str:
    return f"{LABEL_PREFIX}{scenario.slug}"


def _id(result: Mapping[str, Any], section: str, key: str) -> str:
    value = result.get(section, {}).get(key) if isinstance(result.get(section), dict) else None
    if not isinstance(value, str) or not value:
        raise HerdrError(f"herdr answer has no {section}.{key}")
    return value
