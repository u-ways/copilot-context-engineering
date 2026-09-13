"""The scenario manifest: loading, validation, id parsing and front matter (ADR-0005).

The manifest ``overlays/scenarios.toml`` is the single place where scenarios are
declared; Python never branches on a scenario id or slug.
"""

import re
import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

from cce import CceError

MANIFEST_RESOURCE = "overlays/scenarios.toml"
PACKAGED_GUIDES = Path(__file__).resolve().parent / "guides"
DOCS_FALLBACK = Path(__file__).resolve().parents[2] / "docs"
PRESENTING = "presenting"
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_ID_RE = re.compile(r"^\d{2}$")
_SLUG_RE = re.compile(r"^\d{2}-[a-z][a-z0-9-]*$")
_SCENARIO_KEYS = frozenset(
    {"id", "slug", "title", "overlay", "skills", "agents", "files", "executable", "tabs", "checks"}
)
_CHECK_KEYS = frozenset(
    {
        "name",
        "prompt",
        "agent",
        "contains",
        "not_contains",
        "skills_loaded",
        "files_changed",
        "files_changed_max",
    }
)
_NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")
DEFAULT_PROCEDURES_DIR = "_shared/procedures"

FrontMatterValue = str | list[str]


class ManifestError(CceError):
    """The packaged manifest or an overlay front matter block is malformed."""


def is_commit_sha(ref: str) -> bool:
    """True when ``ref`` is a 40-hexadecimal-digit commit sha (ADR-0003)."""
    return bool(_SHA_RE.match(ref))


@dataclass(frozen=True, slots=True)
class SkillsSpec:
    """How a scenario derives its skills from the shared procedures."""

    rename: str | None = None
    rotate_descriptions: int = 0


@dataclass(frozen=True, slots=True)
class FileSpec:
    """A shared file copied (rendered) into the worktree at ``dest``."""

    src: str
    dest: str
    executable: bool = False


@dataclass(frozen=True, slots=True)
class Tab:
    """A herdr tab: label plus the shell command it runs."""

    label: str
    command: str


@dataclass(frozen=True, slots=True)
class Check:
    """One LLM-tier check: a prompt and the structural assertions on its run."""

    name: str
    prompt: str
    agent: str | None = None
    contains: tuple[str, ...] = ()
    not_contains: tuple[str, ...] = ()
    skills_loaded: tuple[str, ...] | None = None
    files_changed: tuple[str, ...] | None = None
    files_changed_max: int | None = None


@dataclass(frozen=True, slots=True)
class Compare:
    """A cross-run assertion: ``left``'s ``metric`` must exceed ``ratio`` times ``right``'s.

    ``right_metric`` defaults to ``metric``; set it to compare two different
    metrics, for example a run's subagent tokens against its own main thread.
    """

    metric: str
    left: str
    right: str
    ratio: float
    right_metric: str | None = None


@dataclass(frozen=True, slots=True)
class Scenario:
    """One scenario as declared in the manifest."""

    id: str
    slug: str
    title: str
    overlay: str | None = None
    skills: SkillsSpec | None = None
    agents: tuple[str, ...] = ()
    files: tuple[FileSpec, ...] = ()
    executable: tuple[str, ...] = ()
    tabs: tuple[Tab, ...] = ()
    checks: tuple[Check, ...] = ()

    @property
    def name(self) -> str:
        """The slug without its numeric prefix (``skills-on-demand``)."""
        return self.slug[len(self.id) + 1 :]


@dataclass(frozen=True, slots=True)
class Manifest:
    """The validated manifest."""

    source_url: str
    source_ref: str
    scenarios: tuple[Scenario, ...]
    procedures: str = DEFAULT_PROCEDURES_DIR
    compares: tuple[Compare, ...] = ()

    def find(self, token: str) -> Scenario | None:
        """Resolve ``3``, ``03``, ``03-skills-on-demand`` or ``skills-on-demand``."""
        wanted = token.zfill(2) if token.isdigit() else token
        for scenario in self.scenarios:
            if wanted in {scenario.id, scenario.slug, scenario.name}:
                return scenario
        return None

    @property
    def valid_ids(self) -> str:
        return ", ".join(scenario.slug for scenario in self.scenarios)


def load(path: Path | None = None) -> Manifest:
    """Load the packaged manifest, or the TOML file at ``path``."""
    if path is None:
        text = resources.files("cce").joinpath(MANIFEST_RESOURCE).read_text(encoding="utf-8")
    else:
        text = path.read_text(encoding="utf-8")
    return parse(text)


def parse(text: str) -> Manifest:
    """Parse and validate manifest TOML."""
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise ManifestError(f"manifest is not valid TOML: {error}") from error
    source = _mapping(data.get("source"), "source")
    url = _string(source.get("url"), "source.url")
    ref = _string(source.get("ref"), "source.ref")
    if not is_commit_sha(ref):
        raise ManifestError(f"source.ref must be a 40-character commit sha, got {ref!r}")
    raw_scenarios = data.get("scenario")
    if not isinstance(raw_scenarios, list) or not raw_scenarios:
        raise ManifestError("manifest declares no [[scenario]] entries")
    scenarios = tuple(
        _scenario(_mapping(item, "scenario"), index) for index, item in enumerate(raw_scenarios)
    )
    _reject_duplicates(scenarios)
    procedures = source.get("procedures", DEFAULT_PROCEDURES_DIR)
    compares = tuple(
        _compare(_mapping(item, "compare"), index)
        for index, item in enumerate(_list(data.get("compare", []), "compare"))
    )
    manifest = Manifest(
        source_url=url,
        source_ref=ref,
        scenarios=scenarios,
        procedures=_string(procedures, "source.procedures"),
        compares=compares,
    )
    _validate_compares(manifest)
    return manifest


def resolve_ids(manifest: Manifest, tokens: Iterable[str]) -> list[Scenario]:
    """Turn user-supplied ids into scenarios; no tokens means every scenario."""
    tokens = list(tokens)
    if not tokens:
        return list(manifest.scenarios)
    resolved: list[Scenario] = []
    for token in tokens:
        scenario = manifest.find(token)
        if scenario is None:
            raise CceError(
                f"unknown scenario {token!r}; valid ids: {manifest.valid_ids}", exit_code=2
            )
        if scenario not in resolved:
            resolved.append(scenario)
    return resolved


def split_front_matter(text: str) -> tuple[dict[str, FrontMatterValue], str]:
    """Split a Markdown document into its front matter fields and body.

    Supported field forms: ``key: value``, ``key: "quoted value"`` and
    ``key: [a, b]``. Anything else is an error; no YAML library is involved.
    """
    lines = text.split("\n")
    if not lines or lines[0] != "---":
        raise ManifestError("front matter must start with a '---' line")
    try:
        end = lines.index("---", 1)
    except ValueError as error:
        raise ManifestError("front matter is not closed by a '---' line") from error
    fields: dict[str, FrontMatterValue] = {}
    for number, line in enumerate(lines[1:end], start=2):
        if not line.strip():
            continue
        key, separator, raw = line.partition(":")
        key = key.strip()
        if not separator or not key or " " in key:
            raise ManifestError(f"front matter line {number} is not 'key: value': {line!r}")
        if key in fields:
            raise ManifestError(f"front matter repeats the key {key!r}")
        fields[key] = _front_matter_value(raw.strip(), number)
    body = "\n".join(lines[end + 1 :])
    return fields, body


def render_front_matter(fields: Mapping[str, FrontMatterValue]) -> str:
    """Render fields as a front matter block; strings are always quoted."""
    rendered = ["---"]
    for key, value in fields.items():
        if isinstance(value, str):
            rendered.append(f"{key}: {_quote(value)}")
        else:
            rendered.append(f"{key}: [{', '.join(_quote(item) for item in value)}]")
    rendered.append("---")
    return "\n".join(rendered) + "\n"


def as_list(value: FrontMatterValue) -> list[str]:
    """Normalise a list field that may have been written as ``a, b``."""
    if isinstance(value, list):
        return list(value)
    return [item.strip() for item in value.split(",") if item.strip()]


def _front_matter_value(raw: str, number: int) -> FrontMatterValue:
    if raw.startswith("["):
        if not raw.endswith("]"):
            raise ManifestError(f"front matter line {number} has an unclosed list")
        inner = raw[1:-1].strip()
        return [_unquote(item.strip()) for item in inner.split(",")] if inner else []
    return _unquote(raw)


def _unquote(raw: str) -> str:
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {'"', "'"}:
        return raw[1:-1].replace('\\"', '"')
    return raw


def _quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _scenario(data: Mapping[str, Any], index: int) -> Scenario:
    unknown = set(data) - _SCENARIO_KEYS
    if unknown:
        raise ManifestError(f"scenario {index} has unknown keys: {', '.join(sorted(unknown))}")
    scenario_id = _string(data.get("id"), f"scenario[{index}].id")
    slug = _string(data.get("slug"), f"scenario[{index}].slug")
    title = _string(data.get("title"), f"scenario[{index}].title")
    if not _ID_RE.match(scenario_id):
        raise ManifestError(f"scenario id must be two digits, got {scenario_id!r}")
    if not _SLUG_RE.match(slug) or not slug.startswith(scenario_id + "-"):
        raise ManifestError(f"scenario slug must be '{scenario_id}-<name>', got {slug!r}")
    where = f"scenario {slug}"
    overlay = data.get("overlay")
    if overlay is not None:
        overlay = _string(overlay, f"{where}.overlay")
    return Scenario(
        id=scenario_id,
        slug=slug,
        title=title,
        overlay=overlay,
        skills=_skills(data.get("skills"), where),
        agents=tuple(_names(data.get("agents", []), f"{where}.agents")),
        files=tuple(
            _file(_mapping(item, f"{where}.files"), where)
            for item in _list(data.get("files", []), f"{where}.files")
        ),
        executable=tuple(_strings(data.get("executable", []), f"{where}.executable")),
        tabs=tuple(
            _tab(_mapping(item, f"{where}.tabs"), where)
            for item in _list(data.get("tabs", []), f"{where}.tabs")
        ),
        checks=tuple(
            _check(_mapping(item, f"{where}.checks"), where)
            for item in _list(data.get("checks", []), f"{where}.checks")
        ),
    )


def _check(data: Mapping[str, Any], where: str) -> Check:
    unknown = set(data) - _CHECK_KEYS
    if unknown:
        raise ManifestError(f"{where}.checks has unknown keys: {', '.join(sorted(unknown))}")
    name = _string(data.get("name"), f"{where}.checks.name")
    if not _NAME_RE.match(name):
        raise ManifestError(f"{where}.checks.name must be a lowercase name, got {name!r}")
    agent = data.get("agent")
    if agent is not None:
        agent = _string(agent, f"{where}.checks.agent")
    skills = data.get("skills_loaded")
    files = data.get("files_changed")
    maximum = data.get("files_changed_max")
    if maximum is not None and (
        not isinstance(maximum, int) or isinstance(maximum, bool) or maximum < 0
    ):
        raise ManifestError(f"{where}.checks.files_changed_max must be a non-negative integer")
    return Check(
        name=name,
        prompt=_string(data.get("prompt"), f"{where}.checks.prompt"),
        agent=agent,
        contains=tuple(_strings(data.get("contains", []), f"{where}.checks.contains")),
        not_contains=tuple(_strings(data.get("not_contains", []), f"{where}.checks.not_contains")),
        skills_loaded=None
        if skills is None
        else tuple(_strings(skills, f"{where}.checks.skills_loaded")),
        files_changed=None
        if files is None
        else tuple(_strings(files, f"{where}.checks.files_changed")),
        files_changed_max=maximum,
    )


def _compare(data: Mapping[str, Any], index: int) -> Compare:
    unknown = set(data) - {"metric", "left", "right", "ratio", "right_metric"}
    if unknown:
        raise ManifestError(f"compare[{index}] has unknown keys: {', '.join(sorted(unknown))}")
    ratio = data.get("ratio", 1.0)
    if isinstance(ratio, bool) or not isinstance(ratio, int | float) or ratio <= 0:
        raise ManifestError(f"compare[{index}].ratio must be a positive number")
    right_metric = data.get("right_metric")
    if right_metric is not None:
        right_metric = _string(right_metric, f"compare[{index}].right_metric")
    return Compare(
        metric=_string(data.get("metric"), f"compare[{index}].metric"),
        left=_string(data.get("left"), f"compare[{index}].left"),
        right=_string(data.get("right"), f"compare[{index}].right"),
        ratio=float(ratio),
        right_metric=right_metric,
    )


def _validate_compares(manifest: Manifest) -> None:
    known = {
        f"{scenario.id}/{check.name}"
        for scenario in manifest.scenarios
        for check in scenario.checks
    }
    for compare in manifest.compares:
        for side in (compare.left, compare.right):
            if side not in known:
                raise ManifestError(f"compare refers to unknown check {side!r}")


def _skills(value: object, where: str) -> SkillsSpec | None:
    if value is None:
        return None
    data = _mapping(value, f"{where}.skills")
    unknown = set(data) - {"rename", "rotate_descriptions"}
    if unknown:
        raise ManifestError(f"{where}.skills has unknown keys: {', '.join(sorted(unknown))}")
    rename = data.get("rename")
    if rename is not None:
        rename = _string(rename, f"{where}.skills.rename")
        if "{n}" not in rename:
            raise ManifestError(f"{where}.skills.rename must contain '{{n}}'")
    rotate = data.get("rotate_descriptions", 0)
    if not isinstance(rotate, int) or isinstance(rotate, bool) or rotate < 0:
        raise ManifestError(f"{where}.skills.rotate_descriptions must be a non-negative integer")
    return SkillsSpec(rename=rename, rotate_descriptions=rotate)


def _file(data: Mapping[str, Any], where: str) -> FileSpec:
    unknown = set(data) - {"src", "dest", "executable"}
    if unknown:
        raise ManifestError(f"{where}.files has unknown keys: {', '.join(sorted(unknown))}")
    executable = data.get("executable", False)
    if not isinstance(executable, bool):
        raise ManifestError(f"{where}.files.executable must be a boolean")
    return FileSpec(
        src=_string(data.get("src"), f"{where}.files.src"),
        dest=_string(data.get("dest"), f"{where}.files.dest"),
        executable=executable,
    )


def _tab(data: Mapping[str, Any], where: str) -> Tab:
    unknown = set(data) - {"label", "command"}
    if unknown:
        raise ManifestError(f"{where}.tabs has unknown keys: {', '.join(sorted(unknown))}")
    return Tab(
        label=_string(data.get("label"), f"{where}.tabs.label"),
        command=_string(data.get("command"), f"{where}.tabs.command"),
    )


def _names(value: object, name: str) -> list[str]:
    names = _strings(value, name)
    for item in names:
        if not _NAME_RE.match(item):
            raise ManifestError(f"{name} entries must be lowercase names, got {item!r}")
    return names


def _strings(value: object, name: str) -> list[str]:
    items = _list(value, name)
    return [_string(item, name) for item in items]


def _list(value: object, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise ManifestError(f"manifest field {name!r} must be a list")
    return value


def _reject_duplicates(scenarios: Iterable[Scenario]) -> None:
    seen: set[str] = set()
    for scenario in scenarios:
        for key in (scenario.id, scenario.slug):
            if key in seen:
                raise ManifestError(f"scenario id or slug declared twice: {key!r}")
            seen.add(key)


def _mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ManifestError(f"manifest section {name!r} is missing or not a table")
    return value


def _string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ManifestError(f"manifest field {name!r} must be a non-empty string")
    return value


def guides_root(packaged: Path = PACKAGED_GUIDES, fallback: Path = DOCS_FALLBACK) -> Path:
    """Where guides live: the wheel's ``cce/guides`` or, in an editable install, ``docs/``."""
    return packaged if packaged.is_dir() else fallback


def guide_path(manifest: Manifest, token: str, root: Path | None = None) -> Path:
    """The Markdown file for ``presenting`` or a scenario id (any accepted form)."""
    base = root if root is not None else guides_root()
    packaged = base.name == "guides"
    if token == PRESENTING:
        return base / "presenting.md"
    scenario = resolve_ids(manifest, [token])[0]
    directory = base if packaged else base / "scenarios"
    return directory / f"{scenario.slug}.md"
