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
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_ID_RE = re.compile(r"^\d{2}$")
_SLUG_RE = re.compile(r"^\d{2}-[a-z][a-z0-9-]*$")
_SCENARIO_KEYS = frozenset({"id", "slug", "title"})

FrontMatterValue = str | list[str]


class ManifestError(CceError):
    """The packaged manifest or an overlay front matter block is malformed."""


@dataclass(frozen=True, slots=True)
class Scenario:
    """One scenario as declared in the manifest."""

    id: str
    slug: str
    title: str

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
    if not _SHA_RE.match(ref):
        raise ManifestError(f"source.ref must be a 40-character commit sha, got {ref!r}")
    raw_scenarios = data.get("scenario")
    if not isinstance(raw_scenarios, list) or not raw_scenarios:
        raise ManifestError("manifest declares no [[scenario]] entries")
    scenarios = tuple(
        _scenario(_mapping(item, "scenario"), index) for index, item in enumerate(raw_scenarios)
    )
    _reject_duplicates(scenarios)
    return Manifest(source_url=url, source_ref=ref, scenarios=scenarios)


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
    return Scenario(id=scenario_id, slug=slug, title=title)


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
