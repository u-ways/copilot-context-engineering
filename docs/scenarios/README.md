# Walkthrough Guide

This guide covers everything you need to run the scenarios successfully. By the end, you should have a strong understanding of why the choice between instructions, skills and agents can significantly improve your outcomes and your value per token.

> [!WARNING]
> Please complete the [setup instructions](../PREREQUISITES.md) before proceeding. This is a technical walkthrough on non-deterministic systems; the setup guide ensures the right environment for an optimal experience.

Once the setup instructions are complete, please read below.

## Background: NHS Software Engineering Quality Framework

The scenarios run on a pinned commit of [our fork](https://github.com/u-ways/software-engineering-quality-framework) of the [Software Engineering Quality Framework](https://github.com/NHSDigital/software-engineering-quality-framework), a guide maintained by the UK's [National Health Service (NHS)](https://en.wikipedia.org/wiki/National_Health_Service). In our words, it sets out to give teams:

- a shared, cross-team picture of what good engineering looks like;
- ways to gauge their current engineering maturity and their technical debt;
- material that helps them raise that maturity and pay the debt down.

It is a rich repository of insights, patterns and practices: plenty for frontier models to reason about, without asking you to learn an entire codebase just to study agentic AI behaviour. `cce setup` clones it into your workspace at runtime; none of its content is redistributed here.

## What are we going to do with this?

Each scenario takes that repository and adds a small, deliberate set of Copilot customisation files, an overlay, that sets up one pattern and one predictable outcome. The overlay is committed as the scenario's baseline, so you can break a scenario as often as you like and put it back with one command.

Each scenario is self-contained: it starts from the state the [setup instructions](../PREREQUISITES.md) left you in, and its guide tells you when to run each command, when to look at Copilot's `/context`, `/usage` and `/diff`, what you should expect to see, and what to compare it with.

Every guide has the same four sections, so you can scan one in a minute:

1. **What it shows**: the lesson, and the overlay files that produce it.
2. **Run it**: the exact commands and prompts to type, run by run, with a table to record what you see.
3. **What to notice**: what must hold on every run, the measured figures for scale, and the one-liner that re-derives each number from the worktree.
4. **Reset**: how to put the scenario back.

Inside **Run it**, every run is a short numbered sequence with the same cues:

| Cue | What you do |
| --- | --- |
| **Start** | Reset the scenario and open a fresh Copilot session in its worktree |
| **Check** | Look before you type: `/context` at turn 0, and sometimes `/instructions` or `/skills` |
| **Send** | Type the prompt exactly as written; the wording is part of the experiment |
| **Observe** | Read the reply, then `/context`, `/usage` and `/diff`, and run the shell commands that confirm what happened |
| **Quit and reset** | `/exit` Copilot and `cce reset N`, so the next run starts clean |

Two terminals make this comfortable: one for Copilot, one for the shell commands (`cd "$(cce path N)"` puts it in the right worktree). Models are non-deterministic, so token counts and wording will differ from the figures in the guides; each guide says what must hold on every run and treats its numbers as scale.

## Scenarios

Run them in order. Each one leans on the one before it, and the six together cover the three mechanisms in the [comparison table](../SUMMARY.md).

| # | Scenario | The question it answers | Runs | Guide |
| --- | --- | --- | --- | --- |
| 01 | instructions-timeless | What belongs in repository instructions? Durable rules, never a snapshot of the repository. | 3 | [01-instructions-timeless.md](01-instructions-timeless.md) |
| 02 | instructions-context-cost | What does a runbook in the instructions cost? Its full size, on every request. | 3 | [02-instructions-context-cost.md](02-instructions-context-cost.md) |
| 03 | skills-on-demand | What do the same procedures cost as skills? Nothing, until a prompt matches one. | 2 | [03-skills-on-demand.md](03-skills-on-demand.md) |
| 04 | skills-description-routing | Which skill loads? The one whose description matches; the name never counts. | 1 | [04-skills-description-routing.md](04-skills-description-routing.md) |
| 05 | agent-permissions | Who may write a file? The agent whose tool list allows it, whatever the prompt says. | 3 (+ `./STRUGGLE.sh`) | [05-agent-permissions.md](05-agent-permissions.md) |
| 06 | agent-context-isolation | Whose context pays for the investigation? The agent's, when you delegate; yours, when you do not. | 2 | [06-agent-context-isolation.md](06-agent-context-isolation.md) |

The guides also ship with the tool: `cce guide 1` prints a guide and `cce guide scenarios` prints this page.
