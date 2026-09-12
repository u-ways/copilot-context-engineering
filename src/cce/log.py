"""structlog configuration: diagnostics go to stderr, results stay on stdout (ADR-0006)."""

import sys
from enum import StrEnum
from typing import TextIO

import structlog
from structlog.typing import FilteringBoundLogger, Processor


class LogFormat(StrEnum):
    """Renderer used for the stderr log stream."""

    CONSOLE = "console"
    JSON = "json"


_LEVEL_BY_VERBOSITY = {-1: 30, 0: 20, 1: 10}  # WARNING, INFO, DEBUG


class _LineWriter:
    """Write rendered records to ``stream``, resolving ``sys.stderr`` at call time.

    Resolving lazily matters: test runners and herdr swap ``sys.stderr`` per
    invocation, so binding the stream once at configuration time would write to
    a closed file later.
    """

    def __init__(self, stream: TextIO | None) -> None:
        self._stream = stream

    def msg(self, message: str) -> None:
        target = self._stream if self._stream is not None else sys.stderr
        target.write(message + "\n")
        target.flush()

    log = debug = info = warning = error = critical = exception = msg


def configure(
    verbosity: int = 0,
    fmt: LogFormat = LogFormat.CONSOLE,
    stream: TextIO | None = None,
) -> None:
    """Route every structlog record to ``stream`` (default: stderr at emit time).

    ``verbosity`` is clamped to -1 (quiet: warnings only), 0 (info) or 1 (debug).
    """
    level = _LEVEL_BY_VERBOSITY[max(-1, min(1, verbosity))]
    renderer: Processor
    if fmt is LogFormat.JSON:
        renderer = structlog.processors.JSONRenderer(sort_keys=True)
    else:
        probe = stream if stream is not None else sys.stderr
        renderer = structlog.dev.ConsoleRenderer(colors=probe.isatty())
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=lambda *_args: _LineWriter(stream),
        cache_logger_on_first_use=False,
    )


def get_logger(name: str) -> FilteringBoundLogger:
    """Return a bound logger for ``name``; call :func:`configure` first."""
    logger: FilteringBoundLogger = structlog.get_logger(name)
    return logger
