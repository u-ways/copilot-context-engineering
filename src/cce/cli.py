"""Typer wiring for the ``cce`` command.

Results go to stdout; diagnostics go to stderr. Commands land incrementally:
this module currently exposes ``version`` only.
"""

import typer

from cce import __version__

app = typer.Typer(
    name="cce",
    help="Prepare a local playground for GitHub Copilot CLI customisation scenarios.",
    add_completion=False,
    no_args_is_help=True,
)


@app.callback()
def root() -> None:
    """Prepare a local playground for GitHub Copilot CLI customisation scenarios."""


@app.command()
def version() -> None:
    """Print the installed cce version."""
    typer.echo(f"cce {__version__}")


def main() -> None:
    """Console-script entry point."""
    app()
