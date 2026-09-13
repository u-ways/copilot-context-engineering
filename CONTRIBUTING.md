# Contributing

This page explains how the tool works inside, what its exit codes mean, and the development loop. The binding rules for anyone, human or agent, changing this repository are in [AGENTS.md](AGENTS.md). The decisions behind the design are recorded in [docs/adrs/](docs/adrs/README.md); ADRs win over every other document, this one included.

## How it works

The base content is [u-ways/software-engineering-quality-framework](https://github.com/u-ways/software-engineering-quality-framework), a fork of the NHS's [NHSDigital/software-engineering-quality-framework](https://github.com/NHSDigital/software-engineering-quality-framework), fetched at runtime at a pinned commit. Neither repository has a licence, so none of that content is redistributed here: it is cloned into your workspace when you run `cce setup`, and every scenario is a git worktree of it with a small overlay of Copilot customisation files committed as a resettable baseline. `cce reset` takes a scenario back to that baseline; `cce teardown` removes the whole workspace.

Overlays are stored in this package without leading dots (`github/copilot-instructions.md` rather than `.github/copilot-instructions.md`) so that packaging and ignore rules never drop them, and they are rendered at setup time. Where an overlay needs upstream text, an include directive pulls it from the clone into the worktree; that text is never part of this repository. `cce setup --dialect claude` renders the same overlays into Claude Code's layout (`CLAUDE.md`, `.claude/skills`, `.claude/agents`) through the translator in `src/cce/dialect.py`. `just llm copilot` or `just llm claude` runs the scenario prompts through the real agents and asserts which skills loaded, which files changed and the token ratios between runs.

Presenter mode is opt-in via `cce setup --herdr`, which lays out one herdr workspace per scenario with its guide, its rendered overlay and a Copilot tab. It is never auto-detected: without the flag, `cce` does not talk to herdr at all.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Success |
| 1 | Runtime failure (git, herdr, uv) |
| 2 | Usage error (bad option or unknown scenario id) |
| 3 | Refused precondition; the message names the remedy, for example a modified worktree without `--force` |

## Development

`just` is the only command surface; CI runs the same recipes. Run `just` on its own to list them.

| Recipe | What it does |
| --- | --- |
| `just install` | Sync the locked environment with every dependency group |
| `just check` | Lint, typecheck and run the default tests with coverage |
| `just test` | Run the default (offline) test tier |
| `just e2e` | Opt-in: clone the real pinned repository and verify every scenario |
| `just llm copilot` or `just llm claude` | Opt-in: LLM-backed scenario checks against the chosen runtime |
| `just smoke` | Install the tool with uv and exercise the CLI end to end |
| `just audit` | Audit the locked dependencies for known vulnerabilities |

Decisions live in [docs/adrs/](docs/adrs/); ADRs win over every other document, this page included. Releases are described in [docs/RELEASING.md](docs/RELEASING.md).

A developer-facing slide deck lives in [docs/slides.md](docs/slides.md) (Marp; render with `just slides`).

## Pull requests

- Branch from `main` as `feat/…`, `fix/…` or `docs/…`. Titles are sentence-case imperative, usually `Area: summary`. Pull requests are squash-merged once every check is green.
- An architecturally significant change (new files under `src/cce/`, workflow changes, the `[project]` table) lands in the same pull request as the ADR that permits it: a new ADR, or a `- Revision YYYY-MM-DD:` bullet on an existing one. The ADR review workflow checks every pull request against the ADRs and posts its findings inline.
- A behaviour change lands with its test and a bug fix with a regression test. Tests use fakes, never mocks, and are named as behaviour sentences.
- Never copy text from the upstream framework into this repository; cite `path:line` and paraphrase. Never reference private projects, companies or people. No AI attribution in commits or pull requests.
