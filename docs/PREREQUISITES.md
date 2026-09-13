# Prerequisites

Everything to have in place before the first scenario. Work through it once; `cce doctor` tells you what is still missing.

## Who this is for

Intermediate Copilot users. This is not for people who are new to Copilot or have never used it: come back once you start hitting your weekly limits and wondering how to make your tokens stretch further. Until then, focus on finding value in agentic AI, then apply cost optimisation. If Copilot is producing no value for you, there is nothing to optimise yet.

## Requirements

| Tool | Why | Check |
| --- | --- | --- |
| [uv](https://docs.astral.sh/uv/) | Installs and upgrades `cce` | `uv --version` |
| Git 2.31 or later | The workspace is a clone with one worktree per scenario | `git --version` |
| [GitHub Copilot CLI](https://github.com/github/copilot-cli) 1.0.83 or later, signed in to an account with Copilot access | Runs the scenarios | `copilot --version`, then `copilot` starts without a login prompt (`/login` inside it if not) |
| Optional: herdr | Presenter mode, `cce setup --herdr` (see [presenting.md](presenting.md)) | `herdr --version` with `HERDR_ENV=1` set |
| Optional: Claude Code | `cce setup --dialect claude` renders the same scenarios in Claude Code's layout | `claude --version` |

## Install

```sh
uv tool install "copilot-context-engineering @ git+https://github.com/u-ways/copilot-context-engineering"
# to remove it again: uv tool uninstall copilot-context-engineering
```

Upgrade with `cce update`. The CLI also checks GitHub Releases at most once a day after a successful command and asks before upgrading; set `CCE_DISABLE_UPDATE_CHECK=1` to switch the check off. It is skipped automatically when `CI` is set.

## Check your machine

```sh
cce doctor
```

Every row is `ok`, `warn` or `fail`. Fix every `fail` row before going on. Read every `warn` row: they name personal skills, agents, hooks or instructions under `~/.copilot` or `~/.claude` that load into every session and change what you see in `/context` and `/skills`. Move them aside for the walkthrough, or expect the extra entries. `cce doctor --offline` skips the upstream reachability check.

## Prepare the scenarios

```sh
cce setup   # clone the base repository once and prepare every scenario
cce list    # one row per scenario with its status
```

The first `cce setup` needs the network: it clones the framework at its pinned commit, with full history, into the workspace and creates one worktree per scenario. Running it again is safe; it only touches scenarios that are missing or whose overlay changed after an upgrade, and it refuses to replace a modified worktree unless you pass `--force`.

The workspace lives at `CCE_WORKSPACE` if set, otherwise `$XDG_DATA_HOME/cce`, otherwise `~/.local/share/cce`.

## Everyday commands

```sh
cce path 3                      # print the worktree path of scenario 03
cd "$(cce path 3)" && copilot   # run the scenario in its worktree
cce guide 3                     # read the guide for scenario 03
cce guide scenarios             # read the walkthrough index
cce reset 3                     # return scenario 03 to its committed baseline
cce reset all                   # reset every scenario
cce teardown                    # remove the whole workspace
```

Scenario ids accept `3`, `03`, `03-skills-on-demand` or `skills-on-demand`. Every command exits non-zero on failure and names the remedy; the codes are listed in [CONTRIBUTING.md](../CONTRIBUTING.md).

## Environment variables

| Variable | Effect | Default |
| --- | --- | --- |
| `CCE_WORKSPACE` | Where the clone and the worktrees live | `$XDG_DATA_HOME/cce`, then `~/.local/share/cce` |
| `CCE_LOG_FORMAT` | Log renderer on stderr: `console` or `json` | `console` |
| `CCE_DISABLE_UPDATE_CHECK` | Any value switches the release check off (`CI` does the same) | unset |
| `CCE_UPDATE_INTERVAL` | Seconds between release checks | `86400` |

Next: the [walkthrough](scenarios/README.md).
