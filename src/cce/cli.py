"""Typer wiring for the ``cce`` command (ADR-0006).

Results go to stdout; diagnostics go to stderr through structlog. This is the
only module that prints, prompts or exits.
"""

import functools
import json
import os
import shutil
import sys
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer

from cce import CceError, __version__
from cce import doctor as doctor_checks
from cce import herdr as herdr_module
from cce import manifest as manifest_module
from cce import update as update_module
from cce.dialect import Dialect
from cce.log import LogFormat, configure, get_logger
from cce.workspace import HERDR_RECORD, Inspection, Status, Workspace


def default_cache_dir(env: Mapping[str, str], home: Path) -> Path:
    """``$XDG_CACHE_HOME/cce`` or ``~/.cache/cce``."""
    if env.get("XDG_CACHE_HOME"):
        return Path(env["XDG_CACHE_HOME"]).expanduser() / "cce"
    return home / ".cache" / "cce"


def after_command(*_args: object, **_options: object) -> None:
    """Run the once-a-day release check after a successful command."""
    if _INVOKED_COMMAND.get() in UPDATE_CHECK_EXEMPT:
        return
    update_module.maybe_notify(
        env=os.environ,
        cache_dir=default_cache_dir(os.environ, Path.home()),
        now=time.time,
        is_tty=lambda: sys.stdin.isatty() and sys.stdout.isatty() and sys.stderr.isatty(),
    )


UPDATE_CHECK_EXEMPT = frozenset({"version", "update"})
_INVOKED_COMMAND: ContextVar[str | None] = ContextVar("cce_invoked_command", default=None)

app = typer.Typer(
    name="cce",
    help="Prepare a local playground for GitHub Copilot CLI customisation scenarios.",
    add_completion=False,
    no_args_is_help=True,
    result_callback=after_command,
)


@dataclass(frozen=True, slots=True)
class Settings:
    """Global options resolved by the root callback."""

    workspace: Path
    verbosity: int
    log_format: LogFormat


def default_workspace(env: Mapping[str, str], home: Path) -> Path:
    """``CCE_WORKSPACE`` > ``$XDG_DATA_HOME/cce`` > ``~/.local/share/cce``."""
    if env.get("CCE_WORKSPACE"):
        return Path(env["CCE_WORKSPACE"]).expanduser()
    if env.get("XDG_DATA_HOME"):
        return Path(env["XDG_DATA_HOME"]).expanduser() / "cce"
    return home / ".local" / "share" / "cce"


def guarded[**P, R](command: Callable[P, R]) -> Callable[P, R]:
    """Turn a :class:`CceError` into a logged message and the documented exit code."""

    @functools.wraps(command)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return command(*args, **kwargs)
        except CceError as error:
            get_logger("cce").error(str(error), exit_code=error.exit_code)
            raise typer.Exit(error.exit_code) from error

    return wrapper


def _show_version(value: bool) -> None:
    if value:
        typer.echo(f"cce {__version__}")
        raise typer.Exit()


_STATUS_COLOURS = {"ok": typer.colors.GREEN, "warn": typer.colors.YELLOW, "fail": typer.colors.RED}


def _scenario_rows(rows: Sequence[Inspection]) -> Iterator[str]:
    """Aligned `id  slug  status  dialect  path` rows with the drift remedy as a suffix."""
    width = max((len(row.scenario.slug) for row in rows), default=0)
    for row in rows:
        remedy = f"cce setup {row.scenario.id}" + (
            " --force" if row.status is Status.MODIFIED else ""
        )
        suffix = f"  [overlay changed; run {remedy}]" if row.drifted else ""
        dialect = row.dialect or "-"
        yield (
            f"{row.scenario.id}  {row.scenario.slug:<{width}}  {row.status!s:<8}  "
            f"{dialect:<7}  {row.path}{suffix}"
        )


@app.callback()
def root(
    ctx: typer.Context,
    version_flag: Annotated[
        bool,
        typer.Option(
            "--version",
            "-V",
            help="Print the installed cce version and exit.",
            callback=_show_version,
            is_eager=True,
        ),
    ] = False,
    workspace: Annotated[
        Path | None,
        typer.Option(
            "--workspace", help="Workspace directory (default: CCE_WORKSPACE or XDG data dir)."
        ),
    ] = None,
    verbose: Annotated[int, typer.Option("-v", "--verbose", count=True, help="Debug logging.")] = 0,
    quiet: Annotated[bool, typer.Option("-q", "--quiet", help="Warnings only.")] = False,
    log_format: Annotated[
        LogFormat,
        typer.Option("--log-format", envvar="CCE_LOG_FORMAT", help="Log renderer on stderr."),
    ] = LogFormat.CONSOLE,
) -> None:
    """Prepare a local playground for GitHub Copilot CLI customisation scenarios."""
    del version_flag  # handled eagerly by _show_version
    if verbose and quiet:
        raise typer.BadParameter("-v/--verbose and -q/--quiet are mutually exclusive")
    verbosity = -1 if quiet else min(verbose, 1)
    configure(verbosity=verbosity, fmt=log_format)
    resolved = workspace if workspace is not None else default_workspace(os.environ, Path.home())
    ctx.obj = Settings(workspace=resolved.expanduser(), verbosity=verbosity, log_format=log_format)
    _INVOKED_COMMAND.set(ctx.invoked_subcommand)
    get_logger("cce").debug("start", argv=sys.argv[1:], workspace=str(ctx.obj.workspace))


@app.command()
def version() -> None:
    """Print the installed cce version."""
    typer.echo(f"cce {__version__}")


@app.command()
@guarded
def doctor(
    offline: Annotated[
        bool, typer.Option("--offline", help="Skip the upstream reachability check.")
    ] = False,
    as_json: Annotated[bool, typer.Option("--json", help="Print the checks as JSON.")] = False,
) -> None:
    """Check this machine for everything the scenarios need."""
    manifest = manifest_module.load()
    checks = doctor_checks.run_checks(
        doctor_checks.Environment.from_system(os.environ), manifest, offline=offline
    )
    if as_json:
        typer.echo(json.dumps([check.as_dict() for check in checks], indent=2))
    else:
        colour = False if os.environ.get("NO_COLOR") else None
        for check in checks:
            row = check.as_row()
            status = typer.style(row[:4], fg=_STATUS_COLOURS[str(check.status)])
            typer.echo(status + row[4:], color=colour)
    if doctor_checks.has_failures(checks):
        get_logger("cce").error("doctor found failures", exit_code=3)
        raise typer.Exit(3)


def _workspace(ctx: typer.Context) -> tuple[Workspace, manifest_module.Manifest]:
    settings: Settings = ctx.obj
    manifest = manifest_module.load()
    return Workspace(settings.workspace, manifest), manifest


def _one(manifest: manifest_module.Manifest, token: str) -> manifest_module.Scenario:
    return manifest_module.resolve_ids(manifest, [token])[0]


@app.command()
@guarded
def setup(
    ctx: typer.Context,
    ids: Annotated[
        list[str] | None,
        typer.Argument(help="Scenario ids (3, 03, 03-skills-on-demand); default: all."),
    ] = None,
    source_url: Annotated[
        str | None, typer.Option("--source-url", help="Override the upstream repository URL.")
    ] = None,
    source_ref: Annotated[
        str | None, typer.Option("--source-ref", help="Override the pinned upstream ref.")
    ] = None,
    force: Annotated[
        bool, typer.Option("--force", help="Recreate modified or unregistered worktrees.")
    ] = False,
    dialect: Annotated[
        Dialect, typer.Option("--dialect", help="Render overlays for copilot or claude.")
    ] = Dialect.COPILOT,
    herdr: Annotated[
        bool, typer.Option("--herdr", help="Also lay out one herdr workspace per scenario.")
    ] = False,
) -> None:
    """Clone the pinned upstream and prepare one worktree per scenario."""
    workspace, manifest = _workspace(ctx)
    scenarios = manifest_module.resolve_ids(manifest, ids or [])
    client = herdr_module.Herdr()
    if herdr:
        # Labels depend only on the requested scenarios, so the collision check
        # runs before any worktree or herdr mutation (ADR-0008).
        planned = herdr_module.plan_layout(
            manifest, workspace.root, {s.slug: workspace.path_for(s) for s in scenarios}, {}
        )
        herdr_module.preflight(os.environ, shutil.which, client, planned)
    results = workspace.setup(
        scenarios,
        source_url=source_url or manifest.source_url,
        source_ref=source_ref or manifest.source_ref,
        force=force,
        dialect=dialect,
    )
    for line in _scenario_rows(results):
        typer.echo(line)
    if herdr:
        layout = herdr_module.plan_layout(
            manifest,
            workspace.root,
            {row.scenario.slug: row.path for row in results if row.status is Status.READY},
            {row.scenario.slug: workspace.overlay_files(row.scenario) for row in results},
        )
        created = herdr_module.apply_layout(client, layout, workspace.root / HERDR_RECORD)
        typer.echo(f"herdr: created {len(created)} workspaces")


@app.command("list")
@guarded
def list_scenarios(
    ctx: typer.Context,
    as_json: Annotated[bool, typer.Option("--json", help="Print the rows as JSON.")] = False,
) -> None:
    """Show every scenario with its status (missing, ready or modified)."""
    workspace, _ = _workspace(ctx)
    rows = workspace.inspect_all()
    if as_json:
        typer.echo(
            json.dumps(
                [
                    {
                        "id": row.scenario.id,
                        "slug": row.scenario.slug,
                        "status": str(row.status),
                        "detail": row.detail,
                        "path": str(row.path),
                        "dialect": row.dialect,
                        "drifted": row.drifted,
                    }
                    for row in rows
                ],
                indent=2,
            )
        )
        return
    for line in _scenario_rows(rows):
        typer.echo(line)


@app.command()
@guarded
def path(
    ctx: typer.Context,
    scenario_id: Annotated[str, typer.Argument(metavar="ID", help="Scenario id.")],
) -> None:
    """Print the absolute worktree path of a scenario."""
    workspace, manifest = _workspace(ctx)
    inspection = workspace.inspect(_one(manifest, scenario_id))
    if inspection.status is Status.MISSING:
        raise CceError(
            f"{inspection.scenario.slug}: {inspection.detail}; run `{inspection.remedy}`",
            exit_code=3,
        )
    typer.echo(str(inspection.path.resolve()))


@app.command()
@guarded
def reset(
    ctx: typer.Context,
    scenario_id: Annotated[str, typer.Argument(metavar="ID|all", help="Scenario id or 'all'.")],
) -> None:
    """Return a scenario (or all of them) to its committed baseline."""
    workspace, manifest = _workspace(ctx)
    if scenario_id == "all":
        for scenario in manifest.scenarios:
            if workspace.inspect(scenario).status is Status.MISSING:
                get_logger("cce").warning("skipping missing scenario", slug=scenario.slug)
                continue
            workspace.reset(scenario)
            typer.echo(f"{scenario.slug} reset")
        return
    scenario = _one(manifest, scenario_id)
    workspace.reset(scenario)
    typer.echo(f"{scenario.slug} reset")


@app.command()
@guarded
def teardown(
    ctx: typer.Context,
    force: Annotated[bool, typer.Option("--force", help="Discard modified worktrees.")] = False,
    herdr: Annotated[
        bool, typer.Option("--herdr", help="Also close the herdr workspaces cce created.")
    ] = False,
) -> None:
    """Remove the workspace: the base clone and every scenario worktree."""
    workspace, _ = _workspace(ctx)
    if herdr:
        closed = herdr_module.close_layout(herdr_module.Herdr(), workspace.root / HERDR_RECORD)
        typer.echo(f"herdr: closed {len(closed)} workspaces")
    removed = workspace.teardown(force=force)
    if removed is None:
        get_logger("cce").info("nothing to remove", workspace=str(workspace.root))
        return
    typer.echo(f"removed {removed}")


@app.command()
@guarded
def update(
    check: Annotated[
        bool, typer.Option("--check", help="Only report whether a newer release exists.")
    ] = False,
) -> None:
    """Upgrade cce to the latest GitHub release with uv."""
    current, latest, upgraded = update_module.update(env=os.environ, check_only=check)
    latest_text = latest.tag if latest is not None else "unknown"
    typer.echo(f"cce {current} (latest release: {latest_text})")
    if upgraded:
        typer.echo(f"upgraded to {latest_text}")
    elif latest is not None and not check and latest.tag.lstrip("v") == current:
        typer.echo("up to date")


@app.command()
@guarded
def guide(
    scenario_id: Annotated[
        str, typer.Argument(metavar="ID|presenting", help="Scenario id or 'presenting'.")
    ],
) -> None:
    """Print a scenario guide (or the presenting guide) to stdout."""
    path = manifest_module.guide_path(manifest_module.load(), scenario_id)
    if not path.is_file():
        raise CceError(f"guide not found: {path}", exit_code=2)
    typer.echo(path.read_text(encoding="utf-8"), nl=False)


def main() -> None:
    """Console-script entry point."""
    app()
