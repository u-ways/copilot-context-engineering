# Presenting the scenarios

A run-of-show for giving the six scenarios as a live talk. Each scenario has its own guide (`cce guide N`) with the exact prompts and expected observations; this page is about sequencing, timing and recovery.

## Prerequisites

Do these before the talk, not on stage:

- `cce doctor` reports no `fail` rows. Read every `warn` row: it names global instructions, skills, agents or hooks under `~/.copilot` that will show up in `/skills` or change behaviour (`cce doctor --verbose` lists every file). Move them aside for the talk, or expect to explain the extra entries. Doctor does not look at Claude Code's `~/.claude`; isolate that as below when running the Claude dialect.
- Or isolate instead of moving: run the talk's sessions with `COPILOT_HOME` (and `CLAUDE_CONFIG_DIR` for Claude Code) pointed at a scratch directory, for example `export COPILOT_HOME="$(mktemp -d)"`. A fresh `COPILOT_HOME` hides the credentials that `copilot /login` stored, so also pass `COPILOT_GITHUB_TOKEN="$(gh auth token)"` in that terminal.
- `cce setup` has run and `cce list` shows every scenario as `ready`.
- Copilot CLI is logged in (`copilot` starts without a login prompt) and is version 1.0.83 or later.
- Export `CCE_DISABLE_UPDATE_CHECK=1` in the terminal you present from: the once-a-day release check runs after any successful command, including `cce reset N`, and its Y/n prompt defaults to yes.
- Terminal font and size: `/context` and `/skills` output should be readable from the back of the room. Test at the projector's resolution.
- Have `cce guide N` open in a second pane for each scenario, or use presenter mode below (`cce setup --herdr` inside herdr).

## Run of show

Order 01 to 06. The run counts below add up to thirteen live sessions (plus `./STRUGGLE.sh`, which prints and exits), and the runs are not equal: scenario 04 is one prompt, while scenario 06's two runs are the slowest (in one measurement roughly two and a half minutes delegated and just over one minute direct, before reading `/context`). Give scenario 06 eight minutes, budget the others by their run count, and never leave 06 last with no slack behind it.

| # | Scenario | Runs | The point |
| --- | --- | --- | --- |
| 01 | instructions-timeless | 3 | One prompt reverts three real upstream changes because the instructions froze a table in time; the durable rules leave the file alone. |
| 02 | instructions-context-cost | 3 | A one-fact lookup costs about 100k input tokens with the procedures inlined, and a fraction of that without them. |
| 03 | skills-on-demand | 2 | The same procedures as skills: the lookup loads nothing; the conversion prompt loads exactly one, and the tracer line proves it. |
| 04 | skills-description-routing | 1 | Rotate the descriptions and the conversion prompt loads the publishing procedure; the names never mattered. |
| 05 | agent-permissions | 3 (+ `./STRUGGLE.sh`) | Same prompt, two agents: the researcher cannot write the file, the author does; the validator reports and fixes nothing by convention. |
| 06 | agent-context-isolation | 2 | Delegated, the audit returns two lines and your context stays small; run directly, 48 file reads land in your session. |

Scenario 02's run (c) is scenario 03's run A, done once and counted under 03.

Open with the TL;DR from `docs/SUMMARY.md` (instructions are "always follow these rules", a skill is "when doing X, here is how", an agent is "go do this and come back") and close with the comparison table.

## Bring the room in

Three runs work best as a guess first, then the number:

- 02: before typing anything, ask how many input tokens the first `/context` will show. Rooms guess an order of magnitude low.
- 04: after `ls .github/skills`, ask which skill will load. The names lie; only the description column routes.
- 06: ask whether the two runs will cost the same. Total tokens and whose context pays are different questions, and the room usually conflates them.

## Reset discipline

Every run starts from the committed baseline in a fresh Copilot session. Before each run:

```sh
cce reset N && cd "$(cce path N)" && copilot --allow-all --model claude-sonnet-5
```

The first session in each worktree asks whether you trust the folder (`1. Yes`); `--allow-all` keeps permission prompts off the stage and `--model claude-sonnet-5` keeps the numbers comparable with the guides, since `Auto` picks a different model per session. Quit a session with `/exit`.

Reset even when the previous run made no visible change: a prompt that "did nothing" may still have left a session file or a partial edit, and a reset is instant. Between scenarios, `cce reset all` clears everything. If a worktree is damaged beyond a reset, `cce setup N --force` recreates it from scratch.

Within a run, follow the numbered steps printed in each guide: `/context` before the prompt, the prompt, then `/context`, `/usage` and `/diff` or `git status --porcelain`. Say the turn-0 number out loud before sending the prompt so the audience can compare.

## Presenter mode

`cce setup --herdr` lays out the talk in herdr.

- Opt-in only. Nothing herdr-related happens without the flag, and the flag refuses to run unless `HERDR_ENV=1` is set exactly and `herdr` is on the path.
- It creates a `DEMO` workspace (this page in one tab, `cce list` in another) plus one herdr workspace per scenario, each with tabs for the guide, the rendered overlay files and a `copilot` session in the worktree. Scenario 06 gets a second Copilot tab running `copilot --agent auditor` for run B.
- Both scenario 06 runs leave the worktree untouched, so they can overlap: start run A in the `copilot` tab and run B in the `copilot:auditor` tab while A is still reading. Never overlap two runs that both write to the same worktree.
- Workspaces are labelled `cce:demo` and `cce:<slug>`. If any of those labels already exists, the command refuses (exit 3) rather than creating duplicates; run `cce teardown --herdr` first.
- `cce teardown --herdr` closes only the workspaces it created, then removes the cce workspace as usual.

## When a run goes wrong

- The model pushes back on a prompt (scenario 01 is the usual place: it may refuse to restore a dead path). Answer as the guide says (`yes, apply the list`) or take the refusal as the lesson. A cautious model demonstrating that stale instructions are wrong is a fine outcome; say so and move on.
- A personal skill or agent appears in `/skills` or gets loaded. Point at the `cce doctor` warning, note that everything under `~/.copilot` is global to the machine, and continue; the scenario's own skill still loads or does not load as expected.
- Copilot refuses to start or compacts because the context is too large (scenarios 02 and 06 run B). Restart with `copilot --context long_context`, or in scenario 06 with `copilot --agent auditor --context long_context`.
- A different number comes back (a coverage citation other than `practices/testing.md:144`, a heading count other than 218). Run the re-derivation one-liner from the guide live; the ground truth is in the worktree and takes seconds to show.
- A skill loads that should not have, or the wrong one loads in scenario 03. Check the prompt was sent verbatim: the words "table" and "format" in particular trigger skills. Reset and resend.
- The worktree is in a strange state. `cce reset N`, or `cce setup N --force` if the reset is refused.

## Fallbacks

- Record each run the day before into `.cce-artifacts/stage/` with any terminal recorder (`script` is everywhere; `asciinema` if it is available). The recordings contain upstream prose, so they stay local: `.cce-artifacts/` is gitignored, and nothing under it is committed or uploaded except the structural result JSON (ADR-0003, ADR-0010).
- A dead network: the measured figures committed in the guides and the slides survive it. Talk through them over the recording.
- A model refusal: the guide's "two valid outcomes" text survives it. Scenario 01 is written for both branches, and a refusal is the lesson from the other side.
