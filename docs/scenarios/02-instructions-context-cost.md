# Scenario 02: task runbooks in instructions are paid on every request

## What it shows

This scenario's `.github/copilot-instructions.md` inlines all eight framework procedures, about 404 KB of upstream text rendered at setup time, under a header that declares every procedure required reading before any task. Copilot CLI loads the file in full: in one measured run through the non-interactive `copilot -p` runner (Copilot CLI 1.0.83, the default model) a one-line reply cost 100,756 input tokens; `just llm copilot` re-measures it. Claude Code 2.1.270 is a second data point for the same lookup: 147,581 input tokens here against 19,461 in scenario 03.

The prompt is a one-fact lookup in one file. None of the eight procedures helps with it, yet all of them sit in context on every turn. Scenario 03 ships the same procedures as skills and serves as the control, so this guide borrows one run from it.

## Run it

Before you start: the [setup](../PREREQUISITES.md) is done and `cce list` shows scenarios 02 and 03 as `ready`. Keep a second terminal for the shell commands.

Record what you see as you go:

| Run | `/context` at turn 0 | `/context` after the reply | `/usage` | Answer and citation |
| --- | --- | --- | --- | --- |
| (a) S02, instructions on | | | | |
| (b) S02, `--no-custom-instructions` | | | | |
| (c) S03, procedures as skills | | | | |

The prompt, identical in all three runs:

```text
In insights/metrics.md, over how many days is each engineering metric calculated? Reply with the number and the path:line where you found it.
```

Do not re-word it. In particular, do not add "table" or "format": those words appear in skill descriptions and would trigger a skill in run (c), spoiling the comparison.

### Run (a): scenario 02, instructions on

1. **Start** a fresh session from the baseline:

   ```sh
   cce reset 2 && cd "$(cce path 2)" && copilot
   ```

   If the model refuses to start because the context is oversized, restart with `copilot --context long_context`.

2. **Check**: `/context`, and note the number. Expect the context to be nearly full before you have typed anything, about 100k tokens for the instructions alone. `/instructions` shows the file loaded; in the shell, `wc -c .github/copilot-instructions.md` shows why.

3. **Send** the prompt.

4. **Observe**: the reply should be 28, cited at `insights/metrics.md:24` or `:33`. Then `/context` (compare with turn 0: the whole file is still there, and every later turn will pay it again) and `/usage`. `/diff` is empty.

5. **Quit and reset**: `/exit`, then `cce reset 2`.

### Run (b): scenario 02, instructions off

1. **Start** with the instructions switched off:

   ```sh
   cce reset 2 && cd "$(cce path 2)" && copilot --no-custom-instructions
   ```

2. **Check**: `/instructions` shows the file toggled off, and `/context` starts close to empty. Note the number next to run (a)'s.

3. **Send** the same prompt.

4. **Observe**: expect the same answer and citation, at a fraction of the input tokens in `/usage`. `/diff` is empty.

5. **Quit and reset**: `/exit`, then `cce reset 2`.

### Run (c): scenario 03, the same procedures as skills

1. **Start** in scenario 03's worktree:

   ```sh
   cce reset 3 && cd "$(cce path 3)" && copilot
   ```

2. **Check**: `/context` starts close to empty, and `/skills` lists eight skills, none loaded. In the shell, `wc -c .github/copilot-instructions.md` shows a few hundred bytes.

3. **Send** the same prompt.

4. **Observe**: expect the same answer and citation, `/context` and `/usage` close to run (b), `/skills` still showing none loaded, and no `procedure:` line in the reply (the procedures end with one, so its absence proves nothing was loaded). `/diff` is empty.

5. **Quit and reset**: `/exit`, then `cce reset 3`.

## What to notice

What must hold on every run: the same answer with the same citation, run (a) starting with a nearly full context, runs (b) and (c) starting close to empty, and no skill loading in run (c). Exact token counts vary between models and runs.

- The answer is 28, cited at `insights/metrics.md:24` or `insights/metrics.md:33`. Re-derive: `grep -n '28 days' insights/metrics.md`.
- The distractor is "monthly" at `insights/metrics.md:12`, which is how often the figures are tracked, not the window they are calculated over. Re-derive: `grep -n -i monthly insights/metrics.md`. The prompt asks "how many days" for that reason.
- Row (a) of your table starts with the context nearly full before you type. Re-derive the size: `wc -c .github/copilot-instructions.md` in scenario 02, then the same command in scenario 03.
- Same answer, same citation, a fraction of the input tokens in rows (b) and (c). In (a) every later turn pays the same again, because instructions are resent with each request.

The lesson: instructions are for rules that apply to every request. A task runbook applies to one kind of task, and putting it in instructions charges every unrelated request for it. Scenario 03 shows the alternative in full.

## Reset

```sh
cce reset 2
cce reset 3
```

`cce setup 2 --force` (or `3`) recreates a worktree from scratch if a reset is not enough.
