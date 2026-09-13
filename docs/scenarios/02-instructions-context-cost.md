# Scenario 02: task runbooks in instructions are paid on every request

## What it shows

This scenario's `.github/copilot-instructions.md` inlines all eight framework procedures, about 404 KB of upstream text rendered at setup time, under a header that declares every procedure policy to be read before any task. Copilot CLI 1.0.83 loads the file in full: in our measurement a one-word reply cost 98,980 input tokens.

The prompt is a one-fact lookup in one file. None of the eight procedures helps with it, yet all of them sit in context on every turn. Scenario 03 ships the same procedures as skills and serves as the control.

## Run it

Observation protocol for every run: start a fresh Copilot session in the worktree, type `/context` before the prompt, send the prompt, then `/context`, `/usage` and `/diff` (or `git status --porcelain`). Personal skills and agents from `~/.copilot` may appear in `/skills`; `cce doctor` warns about them.

The prompt, identical for all three data points:

```text
In insights/metrics.md, over how many days is each engineering metric calculated? Reply with the number and the path:line where you found it.
```

Do not re-word it. In particular, do not add "table" or "format": those words appear in skill descriptions and would trigger a skill in scenario 03, spoiling the comparison.

If the model refuses to start because the context is oversized, add `--context long_context` to the `copilot` command.

### Data point (a): scenario 02, instructions on

```sh
cce reset 2 && cd "$(cce path 2)" && copilot
```

### Data point (b): scenario 02, instructions off

```sh
cce reset 2 && cd "$(cce path 2)" && copilot --no-custom-instructions
```

### Data point (c): scenario 03, procedures as skills

```sh
cce reset 3 && cd "$(cce path 3)" && copilot
```

Fill in the table as you go:

| Run | `/context` at turn 0 | `/context` after the reply | `/usage` | Answer and citation |
| --- | --- | --- | --- | --- |
| (a) S02, instructions on | | | | |
| (b) S02, `--no-custom-instructions` | | | | |
| (c) S03, skills | | | | |

## What to notice

- The answer is 28 in every run, cited at `insights/metrics.md:24` or `insights/metrics.md:33`. Re-derive: `grep -n '28 days' insights/metrics.md`.
- The distractor is "monthly" at `insights/metrics.md:12`, which is how often the figures are tracked, not the window they are calculated over. Re-derive: `grep -n -i monthly insights/metrics.md`. The prompt asks "how many days" for that reason.
- Row (a) starts with the context nearly full before you type: close to 99k tokens for the instructions alone. Rows (b) and (c) start close to empty. Re-derive the size: `wc -c .github/copilot-instructions.md` in scenario 02, then the same command in scenario 03.
- Same answer, same citation, a fraction of the input tokens. In (a) every later turn pays the same again, because instructions are resent with each request.
- In (c), `/skills` lists eight skills and none loads: the reply carries no `procedure:` line.

The lesson: instructions are for rules that apply to every request. A task runbook applies to one kind of task, and putting it in instructions charges every unrelated request for it. Scenario 03 shows the alternative.

## Reset

```sh
cce reset 2
cce reset 3
```

`cce setup 2 --force` (or `3`) recreates a worktree from scratch if a reset is not enough.
