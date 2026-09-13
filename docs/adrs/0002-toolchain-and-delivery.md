# ADR-0002: Toolchain and delivery

- Status: Accepted
- Date: 2026-09-13
- Revision 2026-09-13: the `justfile` gains a documentation-only `slides` recipe that renders the developer deck with Marp; CI does not call it and it needs `npx`, which the toolchain otherwise does not require.

## Context

`cce` is a Python command-line tool that clones an upstream repository at runtime, builds git worktrees and renders overlays into them. Readers run it on their own machines; CI runs it on Linux and macOS. The project needs one reproducible way to build, check and run it, a delivery channel that does not require publishing to a package index, and quality gates that an automated reviewer can verify from the repository alone. Tool choices left implicit drift between local machines and CI; a single command surface removes that drift.

## Decision

- Language and interpreter: Python 3.14. `.python-version` pins `3.14.7`; `pyproject.toml` declares `requires-python = ">=3.14"`.
- Package management: uv, with a committed `uv.lock` and `[tool.uv] required-version = ">=0.12"`. Installs run `uv sync --locked --all-groups`.
- Build: hatchling with the `src` layout (`src/cce`) and the console script `cce = "cce.cli:main"`.
- Runtime dependencies: exactly two, `typer` and `structlog`. Any further runtime dependency needs an ADR that names it (ADR-0001).
- Command surface: the `justfile` is the only command surface. Its recipes are `default`, `install`, `fmt`, `lint`, `typecheck`, `test`, `cov`, `e2e`, `llm`, `audit`, `check`, `run`, `version`, `smoke`, `slides` and `clean`. CI steps call `just <recipe>` and never invoke `uv`, `uvx`, `pytest`, `ruff`, `mypy` or `cce` directly; humans run the same recipes locally.
- Lint and format: ruff with `line-length = 100` and `select = ["E", "W", "F", "I", "UP", "B", "SIM", "C4", "ARG", "PTH", "RUF"]`, with no `ignore` list. Any suppression carries a bracketed code and a reason.
- Types: mypy `strict = true` with `warn_unreachable = true` over `src` and `tests` (a `scripts` directory joins the same configuration when it exists).
- Tests: pytest with `addopts = "--strict-markers -ra -m \"not e2e and not llm\""`; coverage is measured with branches and `fail_under = 85`. Development is test-driven: a behaviour change lands with its test and a bug fix lands with a regression test. Tests use fakes (real scripts on `PATH` or injected callables), not `unittest.mock`.
- CI: GitHub Actions. Every `uses:` is pinned to a floating major tag (`@v<digits>`); `astral-sh/setup-uv@v7` is that action's newest floating major tag as of 2026-09-12 even though its releases run beyond v7. Every workflow declares `permissions:`.
- Distribution: GitHub Releases only. Users install with `uv tool install "copilot-context-engineering @ git+https://github.com/u-ways/copilot-context-engineering"`. No PyPI publishing, no wheel or sdist uploads, no binaries.

## Consequences

- One lockfile and one interpreter version make local runs and CI identical; `just install` is the only setup step.
- The `justfile` is the contract: adding a check means adding a recipe, and CI picks it up by name. The one workflow step that is not a `just` recipe is the `claude -p` step that ADR-0001 mandates in `.github/workflows/adr-review.yml`; it is explicitly excepted in the review guidance below, as are `npm install -g`, `gh`, `git`, `grep` and `sed` used for plumbing.
- Dependabot (`.github/dependabot.yml`, ecosystems `uv` and `github-actions`, weekly) proposes lockfile and action bumps; the floating-major pin means most action updates arrive as a tag move rather than a pull request.
- Strict lint, type and coverage gates reject code that a looser configuration would pass; the trade is fewer style debates in review.
- An unpinned git install tracks `main`; `docs/RELEASING.md` documents the `@vX.Y.Z` form for readers who want exactly a tag.
- No PyPI means no index account, token or release checklist to maintain, at the cost of a longer install line.

## Review guidance

- Require `.python-version` to start with `3.14` and `pyproject.toml` to contain `requires-python = ">=3.14"`.
- Require `uv.lock` to exist and `pyproject.toml` to declare a `[build-system]` that uses `hatchling`.
- Flag `run:` steps in `.github/workflows/*.yml` that invoke `uv`, `uvx`, `pytest`, `ruff`, `mypy` or `cce` directly instead of `just`; the `claude -p` step in `adr-review.yml`, `npm install -g`, `gh`, `git`, `grep` and `sed` are excepted.
- Flag `uses:` lines in `.github/workflows/*.yml` that are not pinned to `@v<digits>`.
- Flag `# noqa` or `# type: ignore` comments without a bracketed code and a reason.
- Flag `fail_under` below 85, any `[tool.ruff.lint].ignore` entry, and any PyPI or binary publishing step (`uv publish`, `uv build`, `twine`, `pypa/gh-action-pypi-publish`, `pyinstaller`, wheel or sdist uploads).
