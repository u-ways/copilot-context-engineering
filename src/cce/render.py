"""Render scenario overlays into the files that land in a worktree (ADR-0005).

Rendering is pure: it reads package data and an injected :class:`UpstreamReader`
and returns :class:`PlannedFile` values. Nothing here touches git or the
workspace.
"""

import hashlib
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from cce import CceError
from cce.dialect import COPILOT_TOOLS
from cce.manifest import (
    FrontMatterValue,
    Manifest,
    Scenario,
    as_list,
    render_front_matter,
    split_front_matter,
)

OVERLAYS_ROOT = Path(__file__).resolve().parent / "overlays"
AGENTS_DIR = "_shared/agents"
MAX_PROCEDURE_DEPTH = 4
DOT_MAPPING = {"github": ".github"}

_DIRECTIVE_RE = re.compile(r"^\s*<!--\s*cce:(?P<verb>[a-z]+)(?P<args>(?:\s+[^\s>]+)*)\s*-->\s*$")
_PREFIX_RE = re.compile(r"^\s*<!--\s*cce:")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_PROCEDURE_FILE_RE = re.compile(r"^(?P<number>\d{2})-(?P<name>[a-z][a-z0-9-]*)\.md$")


class RenderError(CceError):
    """An overlay, procedure or agent source cannot be rendered."""


class UpstreamReader(Protocol):
    """The pinned upstream tree as rendering sees it."""

    def read(self, path: str) -> bytes: ...

    def read_asof(self, path: str, date: str) -> bytes: ...

    def tracked_paths(self) -> frozenset[str]: ...


class PlaceholderUpstream:
    """An upstream whose every file is a one-line placeholder (syntax checks only)."""

    def read(self, path: str) -> bytes:
        return f"[placeholder for {path}]\n".encode()

    def read_asof(self, path: str, date: str) -> bytes:
        return f"[placeholder for {path} as of {date}]\n".encode()

    def tracked_paths(self) -> frozenset[str]:
        return frozenset()


@dataclass(frozen=True, slots=True)
class PlannedFile:
    """A file to write into the worktree, relative POSIX ``dest``."""

    dest: str
    content: bytes
    executable: bool = False


@dataclass(frozen=True, slots=True)
class Procedure:
    """One shared procedure source."""

    number: int
    name: str
    title: str
    description: str
    source: str


@dataclass(frozen=True, slots=True)
class IncludeTarget:
    """An upstream path an overlay includes, optionally as of a date."""

    path: str
    asof: str | None = None


def load_procedures(manifest: Manifest, root: Path = OVERLAYS_ROOT) -> tuple[Procedure, ...]:
    """Load ``NN-<name>.md`` procedure sources in numeric order."""
    directory = root / manifest.procedures
    if not directory.is_dir():
        raise RenderError(f"procedures directory {manifest.procedures!r} is missing")
    procedures: list[Procedure] = []
    for path in sorted(directory.iterdir()):
        match = _PROCEDURE_FILE_RE.match(path.name)
        if match is None:
            raise RenderError(f"{path.name}: procedure files are named NN-<name>.md")
        fields, body = _front_matter(path)
        name = _field(fields, "name", path)
        if name != match.group("name"):
            raise RenderError(f"{path.name}: front matter name {name!r} does not match the file")
        procedures.append(
            Procedure(
                number=int(match.group("number")),
                name=name,
                title=_field(fields, "title", path),
                description=_field(fields, "description", path),
                source=body,
            )
        )
    if [procedure.number for procedure in procedures] != list(range(1, len(procedures) + 1)):
        raise RenderError("procedure numbers must run 01, 02, ... without gaps")
    return tuple(procedures)


def render_text(
    text: str,
    upstream: UpstreamReader,
    procedures: Mapping[str, Procedure],
    *,
    source: str = "<text>",
    depth: int = 0,
) -> str:
    """Expand every directive line in ``text``; included text is never re-scanned."""
    lines: list[str] = []
    for number, line in enumerate(text.split("\n"), start=1):
        match = _DIRECTIVE_RE.match(line)
        if match is None:
            if _PREFIX_RE.match(line):
                raise RenderError(f"{source}:{number}: malformed directive {line.strip()!r}")
            lines.append(line)
            continue
        verb = match.group("verb")
        args = match.group("args").split()
        where = f"{source}:{number}"
        if verb == "include":
            lines.extend(_include(args, upstream, where).split("\n"))
        elif verb == "procedure":
            lines.extend(_procedure(args, upstream, procedures, where, depth).split("\n"))
        elif verb == "procedures":
            lines.extend(_procedures(args, upstream, procedures, where, depth).split("\n"))
        else:
            raise RenderError(f"{where}: unknown directive verb {verb!r}")
    return "\n".join(lines)


def plan_scenario(
    scenario: Scenario,
    manifest: Manifest,
    upstream: UpstreamReader,
    root: Path = OVERLAYS_ROOT,
) -> list[PlannedFile]:
    """Every file the scenario lands in its worktree, sorted by destination."""
    procedures = load_procedures(manifest, root)
    by_name = {procedure.name: procedure for procedure in procedures}
    planned: list[PlannedFile] = []
    planned.extend(_overlay_files(scenario, upstream, by_name, root))
    planned.extend(_skills(scenario, procedures, upstream, by_name))
    planned.extend(_agents(scenario, upstream, by_name, root))
    planned.extend(_files(scenario, upstream, by_name, root))
    _validate(planned, upstream, scenario)
    return sorted(planned, key=lambda file: file.dest)


def residual_directives(planned: Iterable[PlannedFile]) -> list[str]:
    """``dest:line`` for every directive-looking line left in a planned file."""
    found: list[str] = []
    for file in planned:
        for number, line in enumerate(file.content.decode("utf-8", "replace").split("\n"), 1):
            if _PREFIX_RE.match(line):
                found.append(f"{file.dest}:{number}")
    return found


def digest(planned: Iterable[PlannedFile]) -> str:
    """A stable sha256 over destinations, modes and contents."""
    hasher = hashlib.sha256()
    for file in sorted(planned, key=lambda file: file.dest):
        hasher.update(file.dest.encode())
        hasher.update(b"\0" + (b"x" if file.executable else b"-") + b"\0")
        hasher.update(file.content)
        hasher.update(b"\0")
    return hasher.hexdigest()


def include_targets(root: Path = OVERLAYS_ROOT) -> frozenset[IncludeTarget]:
    """Every upstream path any packaged source includes (for the test upstream)."""
    targets: set[IncludeTarget] = set()
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix not in {".md", ".sh", ".py", ".txt"}:
            continue
        for line in path.read_text(encoding="utf-8").split("\n"):
            match = _DIRECTIVE_RE.match(line)
            if match and match.group("verb") == "include":
                args = match.group("args").split()
                targets.add(IncludeTarget(args[0], _asof(args[1:])))
    return frozenset(targets)


def map_dest(relative: str) -> str:
    """Overlay path to worktree path: the top-level ``github`` becomes ``.github``."""
    parts = relative.split("/")
    parts[0] = DOT_MAPPING.get(parts[0], parts[0])
    return "/".join(parts)


def _include(args: list[str], upstream: UpstreamReader, where: str) -> str:
    if not args:
        raise RenderError(f"{where}: include needs a path")
    path = args[0]
    _check_path(path, where)
    asof = _asof(args[1:], where)
    try:
        raw = upstream.read_asof(path, asof) if asof else upstream.read(path)
    except (FileNotFoundError, KeyError) as error:
        detail = f" as of {asof}" if asof else " at the pinned ref"
        raise RenderError(f"{where}: upstream file {path!r} not found{detail}") from error
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise RenderError(f"{where}: upstream file {path!r} is not UTF-8 text") from error
    return text.rstrip("\n")


def _procedure(
    args: list[str],
    upstream: UpstreamReader,
    procedures: Mapping[str, Procedure],
    where: str,
    depth: int,
) -> str:
    if len(args) != 1:
        raise RenderError(f"{where}: procedure needs exactly one name")
    return _render_procedure(args[0], upstream, procedures, where, depth)


def _procedures(
    args: list[str],
    upstream: UpstreamReader,
    procedures: Mapping[str, Procedure],
    where: str,
    depth: int,
) -> str:
    heading = 2
    for arg in args:
        key, _, value = arg.partition("=")
        if key != "heading" or not value.isdigit() or not 1 <= int(value) <= 6:
            raise RenderError(f"{where}: procedures accepts only heading=1..6, got {arg!r}")
        heading = int(value)
    chunks = [
        f"{'#' * heading} {procedure.title}\n\n"
        + _render_procedure(procedure.name, upstream, procedures, where, depth)
        for procedure in sorted(procedures.values(), key=lambda procedure: procedure.number)
    ]
    return "\n\n".join(chunks)


def _render_procedure(
    name: str,
    upstream: UpstreamReader,
    procedures: Mapping[str, Procedure],
    where: str,
    depth: int,
) -> str:
    if name not in procedures:
        raise RenderError(f"{where}: unknown procedure {name!r}")
    if depth >= MAX_PROCEDURE_DEPTH:
        raise RenderError(f"{where}: procedures nest deeper than {MAX_PROCEDURE_DEPTH}")
    return render_text(
        procedures[name].source,
        upstream,
        procedures,
        source=f"procedure {name}",
        depth=depth + 1,
    ).strip("\n")


def _overlay_files(
    scenario: Scenario,
    upstream: UpstreamReader,
    procedures: Mapping[str, Procedure],
    root: Path,
) -> list[PlannedFile]:
    if scenario.overlay is None:
        return []
    directory = root / scenario.overlay
    if not directory.is_dir():
        raise RenderError(f"{scenario.slug}: overlay directory {scenario.overlay!r} is missing")
    planned: list[PlannedFile] = []
    for path in sorted(p for p in directory.rglob("*") if p.is_file()):
        relative = path.relative_to(directory).as_posix()
        dest = map_dest(relative)
        rendered = render_text(
            path.read_text(encoding="utf-8"),
            upstream,
            procedures,
            source=f"{scenario.overlay}/{relative}",
        )
        executable = relative in scenario.executable or dest in scenario.executable
        planned.append(PlannedFile(dest, rendered.encode("utf-8"), executable))
    return planned


def _skills(
    scenario: Scenario,
    procedures: Sequence[Procedure],
    upstream: UpstreamReader,
    by_name: Mapping[str, Procedure],
) -> list[PlannedFile]:
    if scenario.skills is None:
        return []
    planned: list[PlannedFile] = []
    for index, procedure in enumerate(procedures):
        number = index + 1
        rename = scenario.skills.rename
        name = rename.format(n=number) if rename else procedure.name
        donor = procedures[(index + scenario.skills.rotate_descriptions) % len(procedures)]
        body = _render_procedure(procedure.name, upstream, by_name, f"skill {name}", 0)
        content = (
            render_front_matter({"name": name, "description": donor.description})
            + "\n"
            + body
            + "\n"
        )
        planned.append(PlannedFile(f".github/skills/{name}/SKILL.md", content.encode("utf-8")))
    return planned


def _agents(
    scenario: Scenario,
    upstream: UpstreamReader,
    procedures: Mapping[str, Procedure],
    root: Path,
) -> list[PlannedFile]:
    planned: list[PlannedFile] = []
    for agent in scenario.agents:
        path = root / AGENTS_DIR / f"{agent}.agent.md"
        if not path.is_file():
            raise RenderError(f"{scenario.slug}: agent source {path.name!r} is missing")
        fields, body = _front_matter(path)
        name = _field(fields, "name", path)
        if name != agent:
            raise RenderError(f"{path.name}: front matter name {name!r} does not match the file")
        tools = as_list(fields.get("tools", []))
        unknown = [tool for tool in tools if tool not in COPILOT_TOOLS]
        if unknown:
            allowed = ", ".join(COPILOT_TOOLS)
            raise RenderError(
                f"{path.name}: unknown tools {', '.join(unknown)}; allowed: {allowed}"
            )
        header: dict[str, FrontMatterValue] = {
            "name": name,
            "description": _field(fields, "description", path),
            "tools": tools,
        }
        model = fields.get("model")
        if isinstance(model, str):
            header["model"] = model
        rendered = render_text(body, upstream, procedures, source=f"{AGENTS_DIR}/{path.name}")
        content = render_front_matter(header) + rendered
        planned.append(PlannedFile(f".github/agents/{agent}.agent.md", content.encode("utf-8")))
    return planned


def _files(
    scenario: Scenario,
    upstream: UpstreamReader,
    procedures: Mapping[str, Procedure],
    root: Path,
) -> list[PlannedFile]:
    planned: list[PlannedFile] = []
    for spec in scenario.files:
        path = root / spec.src
        if not path.is_file():
            raise RenderError(f"{scenario.slug}: shared file {spec.src!r} is missing")
        rendered = render_text(
            path.read_text(encoding="utf-8"), upstream, procedures, source=spec.src
        )
        planned.append(PlannedFile(spec.dest, rendered.encode("utf-8"), spec.executable))
    return planned


def _validate(planned: Sequence[PlannedFile], upstream: UpstreamReader, scenario: Scenario) -> None:
    seen: set[str] = set()
    tracked = upstream.tracked_paths()
    for file in planned:
        _check_path(file.dest, scenario.slug)
        if file.dest in seen:
            raise RenderError(f"{scenario.slug}: destination {file.dest!r} is planned twice")
        seen.add(file.dest)
        if file.dest in tracked:
            raise RenderError(
                f"{scenario.slug}: destination {file.dest!r} already exists upstream at the pin"
            )
    leftovers = residual_directives(planned)
    if leftovers:
        raise RenderError(f"{scenario.slug}: unexpanded directives at {', '.join(leftovers)}")


def _check_path(path: str, where: str) -> None:
    parts = path.split("/")
    if (
        not path
        or path.startswith("/")
        or path.endswith("/")
        or any(p in {"", ".", ".."} for p in parts)
    ):
        raise RenderError(
            f"{where}: path {path!r} must be relative, normalised and inside the tree"
        )


def _asof(args: Sequence[str], where: str = "<text>") -> str | None:
    if not args:
        return None
    key, _, value = args[0].partition("=")
    if len(args) != 1 or key != "asof" or not _DATE_RE.match(value):
        raise RenderError(f"{where}: include accepts only asof=YYYY-MM-DD, got {' '.join(args)!r}")
    return value


def _front_matter(path: Path) -> tuple[dict[str, FrontMatterValue], str]:
    try:
        return split_front_matter(path.read_text(encoding="utf-8"))
    except CceError as error:
        raise RenderError(f"{path.name}: {error}") from error


def _field(fields: Mapping[str, FrontMatterValue], key: str, path: Path) -> str:
    value = fields.get(key)
    if not isinstance(value, str) or not value:
        raise RenderError(f"{path.name}: front matter needs a non-empty {key!r}")
    return value
