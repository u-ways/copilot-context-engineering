# copilot-context-engineering

A hands-on playground that answers one question for GitHub Copilot CLI: *should I add repository instructions, write an Agent Skill, or create a custom agent?* Rather than arguing the answer in prose, the `cce` command prepares six ready-to-explore scenarios on top of a real public documentation repository. Each scenario is a git worktree with a small, deliberate set of Copilot customisation files and a short guide, so you can run the same prompt under different set-ups and watch what changes in `/context`, `/usage` and `/diff`.

## Which should I use?

| | Instructions | Skill | Agent |
| --- | --- | --- | --- |
| Always loaded? | Yes | No, only when relevant | No, dispatched |
| Adaptive? | No, static text | Yes | Yes |
| Size concern? | Paid on every request | Only when matched | Separate context |

TL;DR: Instructions = "Always follow these rules." Skill = "When doing X, here is how." Agent = "Go do this and come back."

## Install

Requirements:

- [uv](https://docs.astral.sh/uv/)
- Git
- GitHub Copilot CLI 1.0.83 or later
- Optional: herdr, for presenter mode

Install the `cce` command as a uv tool:

```sh
uv tool install "copilot-context-engineering @ git+https://github.com/u-ways/copilot-context-engineering"
```

Upgrade with `cce update`. The CLI also checks GitHub Releases at most once a day after a successful command and asks before upgrading; set `CCE_DISABLE_UPDATE_CHECK=1` to switch the check off. It is skipped automatically when `CI` is set.

## Quickstart

```sh
cce setup      # clone the base repository and prepare every scenario
cce list       # one row per scenario with its status
cce path 3     # print the worktree path of scenario 03
cce guide 3    # read the guide for scenario 03
cce reset 3    # return scenario 03 to its committed baseline
cce teardown   # remove the workspace
```

The workspace lives under the XDG data directory (default `~/.local/share/cce`) or wherever `CCE_WORKSPACE` points. Scenario ids accept `3`, `03`, `03-skills-on-demand` or `skills-on-demand`.

The decisions behind every command are recorded in [docs/adrs/README.md](docs/adrs/README.md).

## Scenarios

| # | Scenario | Lesson | Guide |
| --- | --- | --- | --- |
| 01 | instructions-timeless | Instructions hold durable rules, not changing repo state | [01-instructions-timeless.md](docs/scenarios/01-instructions-timeless.md) |
| 02 | instructions-context-cost | Task runbooks in instructions are paid on every request | [02-instructions-context-cost.md](docs/scenarios/02-instructions-context-cost.md) |
| 03 | skills-on-demand | The same procedures as skills cost nothing until matched | [03-skills-on-demand.md](docs/scenarios/03-skills-on-demand.md) |
| 04 | skills-description-routing | Descriptions route skills | [04-skills-description-routing.md](docs/scenarios/04-skills-description-routing.md) |
| 05 | agent-permissions | Permissions belong to the role | [05-agent-permissions.md](docs/scenarios/05-agent-permissions.md) |
| 06 | agent-context-isolation | Delegate when you need the result, not the investigation | [06-agent-context-isolation.md](docs/scenarios/06-agent-context-isolation.md) |

Read a guide without a checkout with `cce guide 3` (or `cce guide presenting`).

## How it works

The base content is [NHSDigital/software-engineering-quality-framework](https://github.com/NHSDigital/software-engineering-quality-framework), fetched at runtime at a pinned commit. That repository has no licence, so none of its content is redistributed here: it is cloned into your workspace when you run `cce setup`, and every scenario is a git worktree of it with a small overlay of Copilot customisation files committed as a resettable baseline. `cce reset` takes a scenario back to that baseline; `cce teardown` removes the whole workspace.

Overlays are stored in this package without leading dots (`github/copilot-instructions.md` rather than `.github/copilot-instructions.md`) so that packaging and ignore rules never drop them, and they are rendered at setup time. Where an overlay needs upstream text, an include directive pulls it from the clone into the worktree; that text is never part of this repository.

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

Decisions live in [docs/adrs/](docs/adrs/); ADRs win over every other document, this README included. Releases are described in [docs/RELEASING.md](docs/RELEASING.md).

## Licence

This repository is licensed under the MIT licence; see [LICENSE](LICENSE). The upstream framework content is fetched at runtime and is not part of this distribution.
