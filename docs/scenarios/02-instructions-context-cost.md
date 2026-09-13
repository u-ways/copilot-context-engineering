# Scenario 02: task runbooks in instructions are paid on every request

## What it shows

This scenario's `.github/copilot-instructions.md` inlines all eight framework procedures, about 413 KB of upstream text rendered at setup time, under a header that declares every procedure required reading before any task. Copilot loads the file in full into the system prompt of every request.

The prompt is a one-fact lookup in one file. None of the eight procedures helps with it, yet all of them sit in context on every turn. Scenario 03 ships the same procedures as skills and serves as the control, so this guide borrows one run from it.

## Run it

Before you start: the [setup](../PREREQUISITES.md) is done and `cce list` shows scenarios 02 and 03 as `ready`. Keep a second terminal for the shell commands.

Record what you see as you go:

| Run | `/context` at turn 0 → after | `/usage` Tokens ↑ | AI credits (≈ $) | Answer and citation |
| --- | --- | --- | --- | --- |
| (a) S02, instructions on | | | | |
| (b) S02, loading switched off | | | | |
| (c) S03, procedures as skills | | | | |

The prompt, identical in all three runs:

```text
In insights/metrics.md, over how many days is each engineering metric calculated? Reply with the number and the path:line where you found it.
```

Do not re-word it. In particular, do not add "table" or "format": those words appear in skill descriptions and would trigger a skill in run (c), spoiling the comparison.

### Run (a): scenario 02, instructions on

1. **Start** a fresh session from the baseline (answer `1. Yes` to the folder-trust question the first time):

   ```sh
   cce reset 2 && cd "$(cce path 2)" && copilot --allow-all --model claude-sonnet-5
   ```

2. **Check**: `/context` before typing. Expect the context to be nearly half full already, with the `System Prompt` line above 100k tokens: that is the instructions file. `/instructions` shows it enabled; `wc -c .github/copilot-instructions.md` in the shell shows why.

3. **Send** the prompt.

4. **Observe**: expect the answer 28. Watch whether a `Read metrics.md` line appears at all: with the file's text already in its context, the measured run answered without opening it and cited the wrong line. Then `/context` (the whole file is still there, and every later turn resends it) and `/usage` (`AI Credits`, `Tokens ↑`).

5. **Quit and reset**: `/exit`, then `cce reset 2`.

### Run (b): scenario 02, loading switched off

1. **Start** with the instructions file present but not loaded:

   ```sh
   cce reset 2 && cd "$(cce path 2)" && copilot --allow-all --no-custom-instructions --model claude-sonnet-5
   ```

2. **Check**: `/instructions` says the file is disabled for this session, and `/context` starts around 20k. Note the number next to run (a)'s.

3. **Send** the same prompt.

4. **Observe**: expect a `Read metrics.md` line, the same answer with the correct citation (`insights/metrics.md:24` and `:33`), and a fraction of run (a)'s credits in `/usage`.

5. **Quit and reset**: `/exit`, then `cce reset 2`.

### Run (c): scenario 03, the same procedures as skills

1. **Start** in scenario 03's worktree:

   ```sh
   cce reset 3 && cd "$(cce path 3)" && copilot --allow-all --model claude-sonnet-5
   ```

2. **Check**: `/context` starts around 21k, and `/skills` lists the eight repository skills (Esc to close). In the shell, `wc -c .github/copilot-instructions.md` shows a few hundred bytes.

3. **Send** the same prompt.

4. **Observe**: expect the same answer and citation, `/context` and `/usage` close to run (b)'s, no `● skill(...)` line in the transcript and no `procedure:` line in the reply: nothing was loaded.

5. **Quit and reset**: `/exit`, then `cce reset 3`.

## What to notice

What must hold on every run: the same answer, run (a) starting with a nearly full context, runs (b) and (c) starting near the baseline, and no skill loading in run (c). Exact token counts vary between runs.

Measured on Claude Sonnet 5:

| Run | `/context` turn 0 → after | `System Prompt` line | `/usage` Tokens ↑ | AI credits (≈ $) |
| --- | --- | --- | --- | --- |
| (a) S02, instructions on | 118k → 119k | 106.5k | 156.5k | 35.02 (≈ $0.35) |
| (b) S02, loading switched off | 20k → 21k | 8.3k | 81.2k | 4.15 (≈ $0.04) |
| (c) S03, procedures as skills | 21k → 22k | 9.1k | 84.4k | 4.38 (≈ $0.04) |

- The answer is 28, at `insights/metrics.md:24` and `insights/metrics.md:33`. Re-derive: `grep -n '28 days' insights/metrics.md`. In run (a) the measured reply cited line 15, a number that does not exist in the file: it answered from the copy in its context instead of reading the file.
- The distractor is "monthly" at `insights/metrics.md:12`, which is how often the figures are tracked, not the window they are calculated over. Re-derive: `grep -n -i monthly insights/metrics.md`. The prompt asks "how many days" for that reason.
- Re-derive the size difference: `wc -c .github/copilot-instructions.md` in scenario 02, then the same command in scenario 03.
- Same answer, eight times the credits. In (a) every later turn pays the same again, because instructions are resent with each request.

The lesson: instructions are for rules that apply to every request. A task runbook applies to one kind of task, and putting it in instructions charges every unrelated request for it. Scenario 03 shows the alternative in full.

### Impact in numbers

Rough figures from the measured runs (percentages are rounded):

- Credits: the lookup cost about 88% less without the runbooks in context (4.15 against 35.02), and about 87% less with them packaged as skills (4.38 against 35.02). Roughly one eighth of the price for the same answer.
- Context at turn 0: about 83% smaller (20k against 118k). The inlined file alone was 106k tokens of system prompt, about 5 times the size of everything else in the session.
- Input tokens sent: about 48% fewer for the one-turn lookup (81.2k against 156.5k). That gap widens with every turn, because the system prompt is resent each time: after ten turns the inlined session has paid for the file ten times.
- Accuracy: the only wrong citation of the three came from the inlined run, which answered from its context instead of reading the file.

## Reset

```sh
cce reset 2
cce reset 3
```

`cce setup 2 --force` (or `3`) recreates a worktree from scratch if a reset is not enough.
