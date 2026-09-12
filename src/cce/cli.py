"""Typer wiring for the ``cce`` command (ADR-0006).

Results go to stdout; diagnostics go to stderr through structlog. This is the
only module that prints, prompts or exits.
"""

import functools
import json
import os
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer

from cce import CceError, __version__
from cce import doctor as doctor_checks
from cce import manifest as manifest_module
from cce.log import LogFormat, configure, get_logger

app = typer.Typer(
    name="cce",
    help="Prepare a local playground for GitHub Copilot CLI customisation scenarios.",
    add_completion=False,
    no_args_is_help=True,
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


@app.callback()
def root(
    ctx: typer.Context,
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
    if verbose and quiet:
        raise typer.BadParameter("-v/--verbose and -q/--quiet are mutually exclusive")
    verbosity = -1 if quiet else min(verbose, 1)
    configure(verbosity=verbosity, fmt=log_format)
    resolved = workspace if workspace is not None else default_workspace(os.environ, Path.home())
    ctx.obj = Settings(workspace=resolved.expanduser(), verbosity=verbosity, log_format=log_format)
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
        for check in checks:
            typer.echo(check.as_row())
    if doctor_checks.has_failures(checks):
        get_logger("cce").error("doctor found failures", exit_code=3)
        raise typer.Exit(3)


def main() -> None:
    """Console-script entry point."""
    app()
