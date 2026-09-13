# Agent guide

Binding rules for any coding agent, and any human, working in this repository.

## Binding rules

- Read `docs/adrs/README.md` first. ADRs win over every other document, this one included.
- Every architecturally significant change lands in the same PR as the ADR that permits it: either a new ADR or a `- Revision YYYY-MM-DD:` bullet on an existing one.
- Never copy text from the upstream NHS repository (`NHSDigital/software-engineering-quality-framework`) into this repo: no excerpts, fixtures or quotes. Cite `path:line` and paraphrase in our own words.
- Never reference private or internal projects, companies or people.
- No AI attribution in commits or PRs: no `Co-Authored-By` trailers, no "generated with" lines.
- Commit and PR titles are sentence-case imperative, usually `Area: summary`.
- Branches are `feat/`, `fix/` or `docs/`; PRs are squash-merged; CI must be green before merge.
- TDD: a behaviour change lands with its test, a bug fix with a regression test.
- Tests use fakes (real scripts or injected callables), never mocks; they are class-grouped with behaviour-sentence names, fully typed, and their module docstrings cite the ADR under test.
- `# noqa` and `# type: ignore` need a bracketed code and a reason.
- Overlay files under `src/cce/overlays/` never use leading-dot path segments (`github/` renders as `.github/`).
- stdout is for results; stderr is for logs.

## Commands

`just` is the only command surface. CI calls these same recipes; never invoke `uv`, `pytest`, `ruff` or `mypy` directly in a workflow.

| Recipe | Purpose |
| --- | --- |
| `just` | List recipes (default) |
| `just install` | `uv sync --locked --all-groups` |
| `just fmt` | Format the code with ruff |
| `just lint` | Ruff lint and format check, no auto-fix |
| `just typecheck` | mypy strict over `src`, `tests` and `scripts` |
| `just test *ARGS` | Default (offline) test tier; extra arguments go to pytest |
| `just cov` | Default tier with branch coverage, terminal and XML reports |
| `just e2e *ARGS` | Opt-in e2e tier: real pinned clone into a temporary directory |
| `just llm RUNTIME *ARGS` | Opt-in LLM tier against `copilot` or `claude` |
| `just audit` | Export the locked requirements and run pip-audit |
| `just check` | `lint`, `typecheck` and `cov` |
| `just run *ARGS` | Run `cce` from the working tree |
| `just version` | Check that `pyproject.toml` and `__version__` agree |
| `just smoke` | Install as a uv tool and exercise the CLI; grows as commands land |
| `just slides` | Render the developer deck to `dist/slides.html` with Marp (needs `npx`) |
| `just clean` | Remove build, cache and coverage artefacts |

## Layout

Modules and directories marked with a PR number arrive in that later pull request.

```text
.editorconfig  .gitignore  .python-version  AGENTS.md  CLAUDE.md  LICENSE  README.md
justfile  pyproject.toml  uv.lock
.github/
    dependabot.yml                 uv and github-actions, weekly
    adr-review/prompt.md           prompt for the ADR review workflow
    workflows/                     ci, security, adr-review, dependabot-auto-merge,
                                   release-drafter, release; e2e (PR4), llm-tests (PR8)
docs/
    RELEASING.md                   release and update process
    adrs/                          index plus ADR-0001..0010; ADRs win over other docs
    scenarios/                     one guide per scenario slug, shipped as cce/guides (PR6)
    presenting.md                  presenter guide (PR6)
scripts/
    s06_ground_truth.py            dev-only ground truth for scenario 06 (PR4)
src/cce/
    __init__.py                    __version__ and CceError
    __main__.py                    python -m cce
    cli.py                         Typer app; the only module that prints or exits
    log.py                         structlog to stderr, console or json (PR2)
    manifest.py                    scenarios.toml loader, id parsing, front matter (PR2)
    doctor.py                      environment checks (PR2)
    render.py                      overlay directives to planned files (PR3)
    dialect.py                     Copilot to Claude Code layout translator (PR3)
    workspace.py                   pinned clone, worktrees, baselines, lock (PR4)
    update.py                      throttled release check and cce update (PR5)
    herdr.py                       opt-in presenter layout (PR7)
    overlays/                      scenarios.toml, _shared procedures, agents and
                                   scripts, one directory per scenario (PR3)
tests/
    conftest.py  support/  fakes/  fixtures, synthetic upstream, herdr and uv shims
    test_*.py                      default tier, offline
    e2e/                           real pinned clone, marker e2e (PR4)
    llm/                           opt-in LLM tier, marker llm (PR8)
```
