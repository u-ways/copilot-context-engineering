"""The workspace: a pinned base clone and one resettable worktree per scenario.

ADR-0003 (runtime-fetched base repository) and ADR-0004 (worktree per
scenario) describe the layout::

    <ws>/.cce-workspace     marker; nothing is ever removed without it
    <ws>/.cce.lock          flock held by setup, reset and teardown
    <ws>/state.json         registered scenarios, their baselines and digests
    <ws>/base/              full-history --no-checkout clone of the upstream
    <ws>/scenarios/<slug>/  worktree on branch cce/<slug>
"""

import errno
import fcntl
import json
import os
import shutil
import subprocess
from collections.abc import Callable, Iterable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from cce import CceError
from cce.dialect import Dialect
from cce.log import get_logger
from cce.manifest import Manifest, Scenario
from cce.render import OVERLAYS_ROOT, PlannedFile, digest, plan_scenario

HERDR_RECORD = "herdr.json"

MARKER = ".cce-workspace"
LOCK_FILE = ".cce.lock"
STATE_FILE = "state.json"
BASE_DIR = "base"
SCENARIOS_DIR = "scenarios"
STAGING_PREFIX = ".tmp-"
BASELINE_REF_PREFIX = "refs/cce/baseline/"
STATE_SCHEMA = 1
OWNED_ENTRIES = frozenset(
    {MARKER, LOCK_FILE, STATE_FILE, f"{STATE_FILE}.tmp", BASE_DIR, SCENARIOS_DIR, "herdr.json"}
)
STRAY_UPSTREAM_PATHS = (
    "AGENTS.md",
    "CLAUDE.md",
    ".github/copilot-instructions.md",
    ".github/instructions/",
    ".github/skills/",
    ".github/agents/",
    ".claude/",
)

_GIT_CONFIG = (
    "-c",
    "user.name=cce",
    "-c",
    "user.email=cce@localhost",
    "-c",
    "commit.gpgsign=false",
    "-c",
    "core.hooksPath=/dev/null",
)

log = get_logger("cce.workspace")

Runner = Callable[..., subprocess.CompletedProcess[Any]]


class Status(StrEnum):
    MISSING = "missing"
    READY = "ready"
    MODIFIED = "modified"


class GitError(CceError):
    """A git command failed; exit code 1."""


@dataclass(frozen=True, slots=True)
class Inspection:
    """What ``cce list`` reports for one scenario."""

    scenario: Scenario
    status: Status
    detail: str
    path: Path
    dialect: str | None = None
    drifted: bool = False

    @property
    def remedy(self) -> str:
        """The command that clears this state (exit code 3 messages name it)."""
        force = " --force" if self.path.exists() else ""
        return f"cce setup {self.scenario.id}{force}"


@dataclass(slots=True)
class ScenarioRecord:
    baseline: str
    digest: str
    dialect: str


@dataclass(slots=True)
class State:
    """``state.json``; written atomically."""

    source_url: str = ""
    source_ref: str = ""
    scenarios: dict[str, ScenarioRecord] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> State:
        """Read ``state.json``; an unreadable or foreign file is a refused precondition."""
        if not path.is_file():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise TypeError("state is not a JSON object")
            if data.get("schema") != STATE_SCHEMA:
                raise CceError(
                    f"{path} was written by a different cce version (schema "
                    f"{data.get('schema')!r}, expected {STATE_SCHEMA}); run `cce teardown --force`",
                    exit_code=3,
                )
            records = {
                slug: ScenarioRecord(
                    str(item["baseline"]), str(item["digest"]), str(item["dialect"])
                )
                for slug, item in data.get("scenarios", {}).items()
            }
            return cls(str(data.get("source_url", "")), str(data.get("source_ref", "")), records)
        except (OSError, ValueError, TypeError, AttributeError, KeyError) as error:
            raise CceError(
                f"{path} is unreadable ({error}); run `cce teardown --force` to start over",
                exit_code=3,
            ) from error

    def save(self, path: Path) -> None:
        payload = {
            "schema": STATE_SCHEMA,
            "source_url": self.source_url,
            "source_ref": self.source_ref,
            "scenarios": {
                slug: {"baseline": r.baseline, "digest": r.digest, "dialect": r.dialect}
                for slug, r in sorted(self.scenarios.items())
            },
        }
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        tmp.replace(path)


class Git:
    """Run git with a fixed identity and no prompts; raises :class:`GitError`."""

    def __init__(self, runner: Runner = subprocess.run) -> None:
        self._runner = runner

    @staticmethod
    def _env() -> dict[str, str]:
        env = {
            "GIT_TERMINAL_PROMPT": "0",
            "LC_ALL": "C",
            "PATH": os.environ.get("PATH", ""),
            "HOME": os.environ.get("HOME", ""),
        }
        for key in ("GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM", "XDG_CONFIG_HOME"):
            if key in os.environ:
                env[key] = os.environ[key]
        return env

    def show(self, revision: str, path: str, *, cwd: Path) -> bytes | None:
        """``git show REV:PATH`` as raw bytes, or ``None`` when the blob does not exist."""
        completed: subprocess.CompletedProcess[bytes] = self._runner(
            ["git", *_GIT_CONFIG, "show", f"{revision}:{path}"],
            cwd=cwd,
            env=self._env(),
            capture_output=True,
            check=False,
        )
        return None if completed.returncode != 0 else completed.stdout

    def run(
        self, args: Sequence[str], *, cwd: Path | None = None, check: bool = True
    ) -> subprocess.CompletedProcess[str]:
        completed: subprocess.CompletedProcess[str] = self._runner(
            ["git", *_GIT_CONFIG, *args],
            cwd=cwd,
            env=self._env(),
            capture_output=True,
            text=True,
            check=False,
        )
        if check and completed.returncode != 0:
            raise GitError(f"git {' '.join(args)} failed: {completed.stderr.strip()}")
        return completed

    def output(self, args: Sequence[str], *, cwd: Path | None = None) -> str:
        return self.run(args, cwd=cwd).stdout.strip()

    def succeeds(self, args: Sequence[str], *, cwd: Path | None = None) -> bool:
        return self.run(args, cwd=cwd, check=False).returncode == 0


class GitUpstream:
    """An :class:`cce.render.UpstreamReader` backed by the base clone."""

    def __init__(self, git: Git, repository: Path, ref: str) -> None:
        self._git = git
        self._repository = repository
        self._ref = ref

    def read(self, path: str) -> bytes:
        return self._show(self._ref, path)

    def read_asof(self, path: str, date: str) -> bytes:
        revision = self._git.output(
            ["rev-list", "-1", f"--before={date}T23:59:59Z", self._ref, "--", path],
            cwd=self._repository,
        )
        if not revision:
            raise FileNotFoundError(f"{path} has no revision on or before {date}")
        return self._show(revision, path)

    def tracked_paths(self) -> frozenset[str]:
        listing = self._git.output(
            ["ls-tree", "-r", "--name-only", self._ref], cwd=self._repository
        )
        return frozenset(line for line in listing.split("\n") if line)

    def _show(self, revision: str, path: str) -> bytes:
        blob = self._git.show(revision, path, cwd=self._repository)
        if blob is None:
            raise FileNotFoundError(f"{path} is not in {revision}")
        return blob


class Workspace:
    """All mutating operations on a workspace directory."""

    def __init__(
        self,
        root: Path,
        manifest: Manifest,
        git: Git | None = None,
        overlays_root: Path = OVERLAYS_ROOT,
    ) -> None:
        self.root = root
        self.manifest = manifest
        self.git = git or Git()
        self.overlays_root = overlays_root
        self.base = root / BASE_DIR
        self.scenarios_dir = root / SCENARIOS_DIR
        self.state_path = root / STATE_FILE
        self.marker = root / MARKER

    # --- queries -----------------------------------------------------------------------

    def path_for(self, scenario: Scenario) -> Path:
        return self.scenarios_dir / scenario.slug

    def inspect(self, scenario: Scenario, state: State | None = None) -> Inspection:
        state = state if state is not None else State.load(self.state_path)
        path = self.path_for(scenario)
        record = state.scenarios.get(scenario.slug)
        if not path.exists():
            return Inspection(scenario, Status.MISSING, "not created", path)
        if record is None:
            return Inspection(
                scenario, Status.MISSING, "directory exists but is unregistered", path
            )
        baseline = self.baseline_sha(scenario)
        if baseline is None:
            return Inspection(
                scenario, Status.MISSING, "baseline ref is absent", path, record.dialect
            )
        head = self.git.run(["rev-parse", "HEAD"], cwd=path, check=False)
        porcelain = self.git.run(["status", "--porcelain"], cwd=path, check=False)
        if head.returncode != 0 or porcelain.returncode != 0:
            return Inspection(
                scenario, Status.MISSING, "worktree is unreadable", path, record.dialect
            )
        changed = [line[3:] for line in porcelain.stdout.split("\n") if line]
        if head.stdout.strip() == baseline and not changed:
            return Inspection(scenario, Status.READY, "at baseline", path, record.dialect)
        if changed:
            detail = "changed: " + ", ".join(changed[:5]) + (" ..." if len(changed) > 5 else "")
        else:
            detail = "HEAD moved from the baseline"
        return Inspection(scenario, Status.MODIFIED, detail, path, record.dialect)

    def baseline_sha(self, scenario: Scenario) -> str | None:
        """The commit ``refs/cce/baseline/<slug>`` points at, or ``None`` when absent."""
        if not self.base.is_dir():
            return None
        resolved = self.git.run(
            ["rev-parse", "--verify", "-q", f"{BASELINE_REF_PREFIX}{scenario.slug}"],
            cwd=self.base,
            check=False,
        )
        if resolved.returncode != 0:
            return None
        return resolved.stdout.strip()

    def overlay_files(self, scenario: Scenario) -> list[str]:
        """Paths the baseline commit added on top of the pinned upstream tree."""
        listing = self.git.run(
            [
                "diff-tree",
                "--no-commit-id",
                "--name-only",
                "-r",
                f"{BASELINE_REF_PREFIX}{scenario.slug}",
            ],
            cwd=self.base,
            check=False,
        )
        return [line for line in listing.stdout.split("\n") if line]

    def inspect_all(self) -> list[Inspection]:
        """Every scenario's status plus overlay drift; raises only for an unreadable state file."""
        state = State.load(self.state_path)
        reader = self._reader(state.source_ref) if state.source_ref and self.base.is_dir() else None
        results: list[Inspection] = []
        for scenario in self.manifest.scenarios:
            inspection = self.inspect(scenario, state)
            record = state.scenarios.get(scenario.slug)
            drifted = False
            if (
                inspection.status is not Status.MISSING
                and record is not None
                and reader is not None
            ):
                try:
                    drifted = (
                        self._digest(scenario, reader, Dialect(record.dialect)) != record.digest
                    )
                except CceError, ValueError:
                    drifted = True
            results.append(
                Inspection(
                    scenario,
                    inspection.status,
                    inspection.detail,
                    inspection.path,
                    inspection.dialect,
                    drifted,
                )
            )
        return results

    # --- mutations ---------------------------------------------------------------------

    @contextmanager
    def locked(self) -> Iterator[None]:
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / LOCK_FILE).open("a+") as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as error:
                if error.errno in (errno.EACCES, errno.EAGAIN):
                    raise CceError(
                        f"another cce command holds the workspace lock at {self.root}",
                        exit_code=3,
                    ) from error
                raise CceError(f"cannot lock {self.root}: {error}") from error
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def ensure_base(self, source_url: str, source_ref: str) -> State:
        self.root.mkdir(parents=True, exist_ok=True)
        self.marker.touch()
        state = State.load(self.state_path)
        if state.source_url and state.source_url != source_url:
            raise CceError(
                f"workspace {self.root} was created from {state.source_url}; run `cce teardown` "
                "or use another --workspace",
                exit_code=3,
            )
        if not (self.base / ".git").exists():
            log.info("cloning upstream", url=source_url)
            self.git.run(["clone", "--quiet", "--no-checkout", source_url, str(self.base)])
        if not self.git.succeeds(["cat-file", "-e", f"{source_ref}^{{commit}}"], cwd=self.base):
            log.info("fetching pinned ref", ref=source_ref)
            if not self.git.succeeds(
                ["fetch", "--quiet", "--no-tags", "origin", source_ref], cwd=self.base
            ):
                self.git.run(["fetch", "--quiet", "origin"], cwd=self.base, check=False)
            if not self.git.succeeds(["cat-file", "-e", f"{source_ref}^{{commit}}"], cwd=self.base):
                raise CceError(f"pinned ref {source_ref} is not reachable at {source_url}")
        self._warn_about_stray_upstream_files(source_ref)
        state.source_url = source_url
        state.source_ref = source_ref
        state.save(self.state_path)
        return state

    def setup(
        self,
        scenarios: Sequence[Scenario],
        *,
        source_url: str,
        source_ref: str,
        force: bool,
        dialect: Dialect,
    ) -> list[Inspection]:
        self._claim_root()
        with self.locked():
            state = self.ensure_base(source_url, source_ref)
            reader = self._reader(source_ref)
            plans = {
                scenario.slug: plan_scenario(
                    scenario, self.manifest, reader, self.overlays_root, dialect=dialect
                )
                for scenario in scenarios
            }
            refused: list[str] = []
            total = len(scenarios)
            for position, scenario in enumerate(scenarios, start=1):
                self._remove_staging(scenario)
                inspection = self.inspect(scenario, state)
                plan = plans[scenario.slug]
                if inspection.status is Status.READY:
                    record = state.scenarios[scenario.slug]
                    if record.digest == digest(plan) and record.dialect == dialect:
                        log.debug("scenario already ready", slug=scenario.slug)
                        continue
                    log.info("overlay changed; re-rendering", slug=scenario.slug)
                    self._remove_scenario(scenario, state)
                elif inspection.status is Status.MODIFIED or inspection.path.exists():
                    if not force:
                        refused.append(f"{scenario.slug} ({inspection.detail})")
                        continue
                    self._remove_scenario(scenario, state)
                log.info("creating scenario", slug=scenario.slug, progress=f"{position}/{total}")
                self._create(scenario, plan, source_ref, dialect, state)
            if refused:
                raise CceError(
                    "refusing to overwrite: " + "; ".join(refused) + " (use --force to recreate)",
                    exit_code=3,
                )
        return [self.inspect(scenario) for scenario in scenarios]

    def reset(self, scenario: Scenario) -> None:
        if not self.marker.is_file():
            raise CceError(f"{self.root} is not a cce workspace; run `cce setup`", exit_code=3)
        with self.locked():
            state = State.load(self.state_path)
            inspection = self.inspect(scenario, state)
            if inspection.status is Status.MISSING:
                raise CceError(
                    f"{scenario.slug}: {inspection.detail}; run `{inspection.remedy}`",
                    exit_code=3,
                )
            ref = f"{BASELINE_REF_PREFIX}{scenario.slug}"
            self.git.run(["reset", "-q", "--hard", ref], cwd=inspection.path)
            self.git.run(["clean", "-fdxq"], cwd=inspection.path)

    def teardown(self, *, force: bool) -> Path | None:
        if not self.root.exists():
            return None
        if not self.marker.is_file():
            raise CceError(
                f"{self.root} is not a cce workspace (no {MARKER} marker); refusing to remove it",
                exit_code=3,
            )
        with self.locked():
            try:
                state = State.load(self.state_path)
            except CceError:
                if not force:
                    raise CceError(
                        f"{self.state_path} is unreadable; cannot tell which scenarios are "
                        "modified (use --force to remove the workspace anyway)",
                        exit_code=3,
                    ) from None
                state = State()
            modified = [
                inspection.scenario.slug
                for inspection in (self.inspect(s, state) for s in self.manifest.scenarios)
                if inspection.status is Status.MODIFIED
            ]
            if modified and not force:
                raise CceError(
                    "modified scenarios: " + ", ".join(modified) + " (use --force to discard)",
                    exit_code=3,
                )
            for scenario in self.manifest.scenarios:
                path = self.path_for(scenario)
                if path.exists() and self.base.is_dir():
                    self.git.run(
                        ["worktree", "remove", "--force", str(path)], cwd=self.base, check=False
                    )
            # Removed while the lock is held: a concurrent setup cannot slip into the gap.
            self._rmtree(self.root)
        return self.root

    # --- internals ---------------------------------------------------------------------

    def _reader(self, ref: str) -> GitUpstream:
        return GitUpstream(self.git, self.base, ref)

    def _digest(self, scenario: Scenario, reader: GitUpstream, dialect: Dialect) -> str:
        return digest(
            plan_scenario(scenario, self.manifest, reader, self.overlays_root, dialect=dialect)
        )

    def _claim_root(self) -> None:
        """Refuse a directory cce did not create; the marker is teardown's only gate."""
        if self.marker.is_file() or not self.root.exists():
            return
        foreign = sorted(p.name for p in self.root.iterdir() if p.name not in OWNED_ENTRIES)
        if foreign:
            raise CceError(
                f"{self.root} already contains files cce did not create "
                f"({', '.join(foreign[:5])}); point --workspace at an empty directory",
                exit_code=3,
            )

    def _create(
        self,
        scenario: Scenario,
        plan: Sequence[PlannedFile],
        source_ref: str,
        dialect: Dialect,
        state: State,
    ) -> None:
        staging = self.scenarios_dir / f"{STAGING_PREFIX}{scenario.slug}"
        branch = f"cce/{scenario.slug}"
        final = self.path_for(scenario)
        self.scenarios_dir.mkdir(parents=True, exist_ok=True)
        log.debug("writing overlay", slug=scenario.slug, files=len(plan))
        try:
            self.git.run(
                ["worktree", "add", "--quiet", "-B", branch, str(staging), source_ref],
                cwd=self.base,
            )
            for file in plan:
                target = staging / file.dest
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(file.content)
                if file.executable:
                    target.chmod(target.stat().st_mode | 0o111)
            self.git.run(["add", "--force", "--", *(file.dest for file in plan)], cwd=staging)
            self.git.run(
                ["commit", "--quiet", "--no-verify", "-m", f"cce: baseline for {scenario.slug}"],
                cwd=staging,
            )
            baseline = self.git.output(["rev-parse", "HEAD"], cwd=staging)
            self.git.run(
                ["update-ref", f"{BASELINE_REF_PREFIX}{scenario.slug}", baseline], cwd=self.base
            )
            self.git.run(["worktree", "move", str(staging), str(final)], cwd=self.base)
        except Exception:
            self._remove_staging(scenario)
            raise
        state.scenarios[scenario.slug] = ScenarioRecord(baseline, digest(plan), str(dialect))
        state.save(self.state_path)

    def _remove_scenario(self, scenario: Scenario, state: State) -> None:
        path = self.path_for(scenario)
        if self.base.is_dir():
            self.git.run(["worktree", "remove", "--force", str(path)], cwd=self.base, check=False)
            self.git.run(["worktree", "prune"], cwd=self.base, check=False)
            self.git.run(["branch", "-D", "-q", f"cce/{scenario.slug}"], cwd=self.base, check=False)
        if path.exists():
            self._rmtree(path)
        state.scenarios.pop(scenario.slug, None)
        state.save(self.state_path)

    def _remove_staging(self, scenario: Scenario) -> None:
        staging = self.scenarios_dir / f"{STAGING_PREFIX}{scenario.slug}"
        if self.base.is_dir():
            self.git.run(
                ["worktree", "remove", "--force", str(staging)], cwd=self.base, check=False
            )
            self.git.run(["worktree", "prune"], cwd=self.base, check=False)
            if not self.path_for(scenario).exists():
                self.git.run(
                    ["branch", "-D", "-q", f"cce/{scenario.slug}"], cwd=self.base, check=False
                )
        if staging.exists():
            self._rmtree(staging)

    def _rmtree(self, path: Path) -> None:
        """Remove ``path`` only when it is the marked workspace or lives inside one."""
        resolved = path.resolve()
        inside = resolved == self.root.resolve() or self.root.resolve() in resolved.parents
        if not inside or not self.marker.is_file():
            raise CceError(
                f"refusing to remove {path}: not inside a marked cce workspace", exit_code=3
            )
        shutil.rmtree(resolved)

    def _warn_about_stray_upstream_files(self, ref: str) -> None:
        tracked = self._reader(ref).tracked_paths()
        stray = sorted(
            path
            for path in tracked
            if any(
                path == s or (s.endswith("/") and path.startswith(s)) for s in STRAY_UPSTREAM_PATHS
            )
        )
        if stray:
            log.warning(
                "upstream tracks instruction files that may skew scenarios", paths=stray[:10]
            )


def stray_upstream_paths(tracked: Iterable[str]) -> list[str]:
    """Paths among ``tracked`` that would skew scenarios."""
    return sorted(
        path
        for path in tracked
        if any(path == s or (s.endswith("/") and path.startswith(s)) for s in STRAY_UPSTREAM_PATHS)
    )
