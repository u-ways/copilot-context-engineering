# Presenting the scenarios

A run-of-show for giving the six scenarios as a live talk. Each scenario has its own guide (`cce guide N`) with the exact prompts and expected observations; this page is about sequencing, timing and recovery.

## Prerequisites

Do these before the talk, not on stage:

- `cce doctor` reports no `fail` rows. Read every `warn` row: it names personal skills, agents, hooks or instructions under `~/.copilot` or `~/.claude` that will show up in `/skills` or change behaviour. Move them aside for the talk, or expect to explain the extra entries.
- `cce setup` has run and `cce list` shows every scenario as `ready`.
- Copilot CLI is logged in (`copilot` starts without a login prompt) and is version 1.0.83 or later.
- Terminal font and size: `/context` and `/skills` output should be readable from the back of the room. Test at the projector's resolution.
- Have `cce guide N` open in a second pane for each scenario, or use presenter mode below (`cce setup --herdr` inside herdr).

## Run of show

Order 01 to 06. About 5 minutes per scenario, 30 minutes in total plus questions.

| # | Scenario | The beat |
| --- | --- | --- |
| 01 | instructions-timeless | One prompt reverts three real upstream changes because the instructions froze a table in time; the durable rules leave the file alone. |
| 02 | instructions-context-cost | A one-fact lookup costs close to 99k input tokens with the procedures inlined, and a fraction of that without them. |
| 03 | skills-on-demand | The same procedures as skills: the lookup loads nothing; the conversion prompt loads exactly one, and the tracer line proves it. |
| 04 | skills-description-routing | Rotate the descriptions and the conversion prompt loads the publishing procedure; the names never mattered. |
| 05 | agent-permissions | Same prompt, two agents: the researcher cannot write the file, the author does; the validator reports and fixes nothing by convention. |
| 06 | agent-context-isolation | Delegated, the audit returns two lines and your context stays small; run directly, 48 file reads land in your session. |

Open with the TL;DR from the README (instructions are "always follow these rules", a skill is "when doing X, here is how", an agent is "go do this and come back") and close with the comparison table.

## Reset discipline

Every beat starts from the committed baseline in a fresh Copilot session. Before each beat:

```sh
cce reset N && cd "$(cce path N)" && copilot
```

Reset even when the previous beat made no visible change: a prompt that "did nothing" may still have left a session file or a partial edit, and a reset is instant. Between scenarios, `cce reset all` clears everything. If a worktree is damaged beyond a reset, `cce setup N --force` recreates it from scratch.

Within a beat, follow the observation protocol printed in each guide: `/context` before the prompt, the prompt, then `/context`, `/usage` and `/diff` or `git status --porcelain`. Say the turn-0 number out loud before sending the prompt so the audience can compare.

## Presenter mode

`cce setup --herdr` lays out the talk in herdr.

- Opt-in only. Nothing herdr-related happens without the flag, and the flag refuses to run unless `HERDR_ENV=1` is set exactly and `herdr` is on the path.
- It creates a `DEMO` workspace (this page in one tab, `cce list` in another) plus one herdr workspace per scenario, each with tabs for the guide, the rendered overlay files and a `copilot` session in the worktree. Scenario 06 gets a second Copilot tab running `copilot --agent auditor` for run B.
- Workspaces are labelled `cce:demo` and `cce:<slug>`. If any of those labels already exists, the command refuses (exit 3) rather than creating duplicates; run `cce teardown --herdr` first.
- `cce teardown --herdr` closes only the workspaces it created, then removes the cce workspace as usual.

## When a beat goes wrong

- The model pushes back on a prompt (scenario 01 is the usual place: it may refuse to restore a dead path). Answer as the guide says (`yes, apply the list`) or take the refusal as the lesson. A cautious model demonstrating that stale instructions are wrong is a fine outcome; say so and move on.
- A personal skill or agent appears in `/skills` or gets loaded. Point at the `cce doctor` warning, note that everything under `~/.copilot` is global to the machine, and continue; the scenario's own skill still loads or does not load as expected.
- Copilot refuses to start or compacts because the context is too large (scenarios 02 and 06 run B). Restart with `copilot --context long_context`, or in scenario 06 with `copilot --agent auditor --context long_context`.
- A different number comes back (a coverage citation other than `practices/testing.md:144`, a heading count other than 218). Run the re-derivation one-liner from the guide live; the ground truth is in the worktree and takes seconds to show.
- A skill loads that should not have, or the wrong one loads in scenario 03. Check the prompt was sent verbatim: the words "table" and "format" in particular trigger skills. Reset and resend.
- The worktree is in a strange state. `cce reset N`, or `cce setup N --force` if the reset is refused.
