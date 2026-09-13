# Walkthrough Guide

This guide covers everything you need to run the scenarios successfully, so you get a clear picture of how different context-loading mechanisms affect correctness and usage cost. By the end you should have a strong understanding of why the choice between instructions, skills and agents can significantly improve your outcomes and your value per token.

> [!WARNING]
> Please complete the [setup instructions](../PREREQUISITES.md) before proceeding. This is a technical walkthrough on non-deterministic systems; the setup guide ensures the right environment for a good experience.

## Background: NHS Software Engineering Quality Framework

The scenarios run on a pinned commit of the [Software Engineering Quality Framework](https://github.com/NHSDigital/software-engineering-quality-framework), a guide maintained by the UK's [National Health Service (NHS)](https://en.wikipedia.org/wiki/National_Health_Service). In our words, it sets out to give teams:

- a shared, cross-team picture of what good engineering looks like;
- ways to gauge their current engineering maturity and their technical debt;
- material that helps them raise that maturity and pay the debt down.

It is a rich repository of insights, patterns and practices: plenty for frontier models to reason about, without asking you to learn an entire codebase just to study agentic AI behaviour. `cce setup` clones it into your workspace at runtime; none of its content is redistributed here.

## Scenarios

Run them in order. Each one leans on the one before it, and the six together cover the three mechanisms in the [comparison table](../../README.md#which-should-i-use).

| # | Scenario | The question it answers | Runs | Guide |
| --- | --- | --- | --- | --- |
| 01 | instructions-timeless | What belongs in repository instructions? Durable rules, never a snapshot of the repository. | 3 | [01-instructions-timeless.md](01-instructions-timeless.md) |
| 02 | instructions-context-cost | What does a runbook in the instructions cost? Its full size, on every request. | 3 | [02-instructions-context-cost.md](02-instructions-context-cost.md) |
| 03 | skills-on-demand | What do the same procedures cost as skills? Nothing, until a prompt matches one. | 2 | [03-skills-on-demand.md](03-skills-on-demand.md) |
| 04 | skills-description-routing | Which skill loads? The one whose description matches; the name never counts. | 1 | [04-skills-description-routing.md](04-skills-description-routing.md) |
| 05 | agent-permissions | Who may write a file? The agent whose tool list allows it, whatever the prompt says. | 3 (+ `./STRUGGLE.sh`) | [05-agent-permissions.md](05-agent-permissions.md) |
| 06 | agent-context-isolation | Whose context pays for the investigation? The agent's, when you delegate; yours, when you do not. | 2 | [06-agent-context-isolation.md](06-agent-context-isolation.md) |

## How each guide is laid out

Every guide has the same four sections, so you can scan one in a minute:

1. **What it shows**: the lesson, and the overlay files that produce it.
2. **Run it**: the exact commands and prompts to type, run by run.
3. **What to notice**: the expected outcome, every expected number, and the one-liner that re-derives it from the worktree.
4. **Reset**: how to put the scenario back.

## The protocol for every run

Each run is one prompt in a fresh Copilot session, started from the scenario's committed baseline:

```sh
cce reset N && cd "$(cce path N)" && copilot
```

1. Type `/context` before the prompt and note the turn-0 number.
2. Send the prompt from the guide, word for word.
3. Type `/context`, then `/usage`, then `/diff` (or run `git status --porcelain` in the worktree).
4. Reset with `cce reset N`, even when nothing visible changed.

Models are non-deterministic, so token counts and wording differ between runs. The guides state what must hold on every run (which skills load, which files change, the ratios between runs) and give the measured figures only for scale. Personal skills, agents and hooks under `~/.copilot` add entries to `/skills` and tokens to `/context`; `cce doctor` lists them.

## Reading the guides without a checkout

The guides ship with the tool: `cce guide 3` prints a scenario guide, `cce guide scenarios` prints this page and `cce guide presenting` prints the presenter guide.

## Next

Running the six scenarios as a talk, with timings, audience prompts and an optional herdr layout, is covered in [presenting.md](../presenting.md).
