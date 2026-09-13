# ADR-0006: CLI output and logging

- Status: Accepted
- Date: 2026-09-13
- Revision 2026-09-13: `cce --version`/`-V` prints the version eagerly; `list` and `setup` rows are column-aligned and carry the dialect; `doctor` colours its status token on a colour terminal (`NO_COLOR` disables it), probes `copilot --version` against the measured minimum 1.0.83, and reports an `overlays` render check; exit-3 messages name the exact remedy (`cce setup N` or `cce setup N --force`); `reset` refuses without a workspace before creating anything.

## Context

`cce` is used both interactively and from scripts (`cd "$(cce path 3)"`, CI smoke runs, herdr tabs). Those callers need results on stdout that they can capture, diagnostics on stderr that they can ignore or collect as structured records, and exit codes with a fixed meaning. Typer gives the command surface; structlog gives structured, filterable diagnostics. Without a written contract, `print` calls and ad-hoc `sys.exit` values creep into every module and scripts break on the first change.

## Decision

- stdout carries results only: the rows of `list` and `doctor`, the path from `path`, the version, guide text. stderr carries every diagnostic through structlog, rendered by `structlog.dev.ConsoleRenderer` (colour only on a TTY) or, with `--log-format json` (env `CCE_LOG_FORMAT`), `structlog.processors.JSONRenderer` as one JSON object per line. Stdlib `logging` is not used.
- Global options precede the command: `--workspace PATH` (default `CCE_WORKSPACE`, then `$XDG_DATA_HOME/cce`, then `~/.local/share/cce`), `-v/--verbose` (debug, logs the argv), `-q/--quiet` (warnings only), `--log-format console|json`. `-v` together with `-q` is a usage error.
- Exit codes: 0 success; 1 runtime failure (git, herdr, uv); 2 usage error (bad option, unknown scenario id); 3 refused precondition, whose message names the remedy. Every failure is raised as `cce.CceError(message, exit_code=...)` and turned into a logged message plus `typer.Exit(code)` by the `guarded` decorator in `cli.py`; stdout stays empty on failure, except for `doctor`, which prints its rows and then exits 3 when any check fails.
- No interactive prompts anywhere except the update notice (ADR-0007). Commands never read stdin.
- Scenario ids are accepted as `3`, `03`, `03-skills-on-demand` or `skills-on-demand`; `all` is accepted by `reset`. Unknown ids exit 2 and list the valid slugs.
- `cce doctor [--offline] [--json]` reports `ok|warn|fail  name  detail` rows for: Python version, git presence and version, `copilot` presence and version (1.0.83 or newer recommended), `claude` (optional), `uv`, `herdr` (only when `HERDR_ENV=1`), personal customisation that can skew scenarios (`~/.copilot/{skills,agents,hooks,copilot-instructions.md}`, `~/.claude/skills`, hooks in `~/.claude/settings.json`), whether every overlay renders against placeholder upstream text, and upstream reachability (skipped with `--offline`). An absent workspace is never a failure.
- Scope: these rules govern `src/cce/*.py`. Scripts shipped inside overlays (`src/cce/overlays/**`) are tools that run inside a scenario worktree and keep their own stdout contract.

## Consequences

- Shell composition works: `cce path 3` prints exactly one path or nothing, and a non-zero exit code is the only failure signal on stdout.
- Every diagnostic is machine-readable on request, which is what the herdr tabs and the LLM test tier consume.
- Modules other than `cli.py` cannot print or exit; they raise `CceError` and return values, which keeps them testable with plain function calls.
- `doctor` is the one command that both prints and fails, so a reader always sees which check failed.

## Review guidance

- Flag `print(` or `typer.echo(` in `src/cce/*.py` outside `cli.py`.
- Flag `import logging` or `logging.` in `src/cce/*.py`, and structlog configured with any factory or stream other than stderr in `src/cce/log.py`.
- Flag `sys.exit(` or `typer.Exit(` in `src/cce/*.py` outside `cli.py`.
- Flag `input(`, `typer.prompt(` or `typer.confirm(` in `src/cce/*.py` outside `update.py`.
- Require `README.md` to contain an exit-code table listing 0, 1, 2 and 3.
- Require `tests/test_cli.py` to assert that `-v` with `-q` exits 2 and that `--log-format json` writes JSON to stderr.
