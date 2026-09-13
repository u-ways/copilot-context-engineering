"""The throttled, never-failing release check and ``cce update`` (ADR-0007).

Every collaborator that touches the machine or the network is injected:
``fetch`` (HTTP), ``now`` (clock), ``is_tty``, ``confirm`` (the only prompt in
``cce``) and ``run`` (``uv``). Tests pass fakes; production passes the defaults.
"""

import json
import re
import shutil
import subprocess
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from cce import CceError, __version__
from cce.log import get_logger

RELEASES_LATEST_URL = (
    "https://api.github.com/repos/u-ways/copilot-context-engineering/releases/latest"
)
RELEASES_URL_ENV = "CCE_RELEASES_URL"
DEFAULT_INTERVAL_SECONDS = 86_400
FETCH_TIMEOUT_SECONDS = 3.0
TOOL_NAME = "copilot-context-engineering"
CACHE_FILE = "update-check.json"

Fetcher = Callable[[str, float], bytes]
Clock = Callable[[], float]
Confirm = Callable[[str], bool]
Runner = Callable[[Sequence[str]], int]
Which = Callable[[str], str | None]

_VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")

log = get_logger("cce.update")


@dataclass(frozen=True, slots=True)
class Latest:
    tag: str
    version: tuple[int, int, int]


def default_fetch(url: str, timeout: float) -> bytes:
    """GET ``url`` (https or file) and return the body."""
    request = urllib.request.Request(
        url, headers={"Accept": "application/vnd.github+json", "User-Agent": "cce"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body: bytes = response.read()
        return body


def default_run(argv: Sequence[str]) -> int:
    return subprocess.run(list(argv), check=False).returncode


def parse_version(tag: str) -> tuple[int, int, int] | None:
    match = _VERSION_RE.match(tag.strip())
    if match is None:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def releases_url(env: Mapping[str, str]) -> str:
    return env.get(RELEASES_URL_ENV) or RELEASES_LATEST_URL


def fetch_latest(fetch: Fetcher, url: str) -> Latest | None:
    """The latest release, or ``None`` when there is none or the body is unusable."""
    try:
        data = json.loads(fetch(url, FETCH_TIMEOUT_SECONDS).decode("utf-8"))
    except (OSError, ValueError) as error:
        log.debug("release lookup failed", error=str(error))
        return None
    tag = data.get("tag_name") if isinstance(data, dict) else None
    if not isinstance(tag, str):
        return None
    version = parse_version(tag)
    if version is None:
        return None
    return Latest(tag=tag, version=version)


def maybe_notify(
    *,
    env: Mapping[str, str],
    cache_dir: Path,
    fetch: Fetcher = default_fetch,
    now: Clock,
    is_tty: Callable[[], bool],
    confirm: Confirm,
    run: Runner = default_run,
    current: str = __version__,
) -> None:
    """Check for a newer release at most once per interval; never raises."""
    try:
        if "CCE_DISABLE_UPDATE_CHECK" in env or "CI" in env:
            return
        interval = int(env.get("CCE_UPDATE_INTERVAL", DEFAULT_INTERVAL_SECONDS))
        cache = cache_dir / CACHE_FILE
        if now() - _last_checked(cache) < interval:
            return
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({"checked_at": now()}), encoding="utf-8")
        latest = fetch_latest(fetch, releases_url(env))
        installed = parse_version(current)
        if latest is None or installed is None or latest.version <= installed:
            return
        if is_tty() and confirm(
            f"cce {latest.tag} is available (you have {current}). Upgrade now?"
        ):
            run(["uv", "tool", "upgrade", TOOL_NAME])
        elif not is_tty():
            log.warning(
                "a newer cce is available",
                latest=latest.tag,
                current=current,
                hint="run cce update",
            )
    except Exception as error:  # the check must never fail a command (ADR-0007)
        log.debug("update check skipped", error=str(error))


def update(
    *,
    env: Mapping[str, str],
    fetch: Fetcher = default_fetch,
    run: Runner = default_run,
    which: Which = shutil.which,
    check_only: bool,
    current: str = __version__,
) -> tuple[str, Latest | None, bool]:
    """Report the latest release and, unless ``check_only``, upgrade when it is newer.

    Returns ``(current, latest, upgraded)``.
    """
    latest = fetch_latest(fetch, releases_url(env))
    installed = parse_version(current)
    newer = latest is not None and installed is not None and latest.version > installed
    if check_only or not newer:
        return current, latest, False
    if which("uv") is None:
        raise CceError(
            "uv is not on PATH; install uv and run `uv tool upgrade " + TOOL_NAME + "`", exit_code=3
        )
    code = run(["uv", "tool", "upgrade", TOOL_NAME])
    if code != 0:
        raise CceError(f"uv tool upgrade {TOOL_NAME} failed with exit code {code}")
    return current, latest, True


def _last_checked(cache: Path) -> float:
    try:
        value = json.loads(cache.read_text(encoding="utf-8")).get("checked_at", 0)
        return float(value)
    except OSError, ValueError, AttributeError, TypeError:
        return 0.0
