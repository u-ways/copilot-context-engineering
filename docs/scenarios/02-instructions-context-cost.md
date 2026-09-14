# Scenario 02: task runbooks in instructions are paid on every request

## What it shows

### The topic

The framework's engineering principles. `principles.md` lists the seven lean-inspired principles the whole framework rests on, from eliminating waste to optimising the whole, each with a short explanation. It is the page a newcomer reads first, and a question about it needs nothing else.

The framework also holds eight long task procedures (this repository packages them as "procedures"): how to review engineering maturity, set up a delivery pipeline, design a test strategy, make a service observable, record a cloud architecture decision, run security scanning, open-source a repository, and convert a page to the house conventions. Together they are about 413 KB of text.

### The set-up

This scenario's `.github/copilot-instructions.md` inlines all eight procedures under a header that declares them required reading before any task. Copilot loads the file in full into the system prompt of every request.

The prompt is a one-fact lookup on the principles page. None of the eight procedures helps with it, yet all of them sit in context on every turn. Scenario 03 ships the same procedures as skills and serves as the control, so this guide borrows one run from it.

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
In principles.md, how many engineering principles does the framework list, and what is the first one? Reply with the number, the name and the path:line where you found it.
```

Do not re-word it. In particular, do not mention maturity, quality checks or reviews: those words appear in a skill description and would trigger a skill in run (c), spoiling the comparison.

### Run (a): scenario 02, instructions on

1. **Start** a fresh session from the baseline (answer `1. Yes` to the folder-trust question the first time):

   ```sh
   cce reset 2 && cd "$(cce path 2)" && copilot --allow-all --model claude-sonnet-5
   ```

   If the model refuses to start because the context is oversized, restart with `copilot --context long_context`.

2. **Check**: `/context` before typing. Expect the context to be nearly half full already, with the `System Prompt` line above 100k tokens: that is the instructions file. `/instructions` shows it enabled; `wc -c .github/copilot-instructions.md` in the shell shows why.

3. **Send** the prompt.

4. **Observe**: the reply should say seven, "Eliminate waste", at `principles.md:17`. The measured run answered correctly, but first ran two searches over a file that was already sitting in its context. Then `/context` (the whole file is still there, and every later turn will resend it) and `/usage` (`AI Credits`, `Tokens ↑`).

5. **Quit and reset**: `/exit`, then `cce reset 2`.

### Run (b): scenario 02, loading switched off

1. **Start** with the instructions file present but not loaded:

   ```sh
   cce reset 2 && cd "$(cce path 2)" && copilot --allow-all --no-custom-instructions --model claude-sonnet-5
   ```

2. **Check**: `/instructions` says the file is disabled for this session, and `/context` starts around 20k. Note the number next to run (a)'s.

3. **Send** the same prompt.

4. **Observe**: expect a `Read principles.md` line, the same answer and citation, and a fraction of run (a)'s credits in `/usage`.

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
| (a) S02, instructions on | 118k → 119k | 106.5k | 470.0k | 41.74 (≈ $0.42) |
| (b) S02, loading switched off | 20k → 21k | 8.3k | 81.2k | 4.0 (≈ $0.04) |
| (c) S03, procedures as skills | 21k → 31k | 9.1k | 106.4k | 7.88 (≈ $0.08) |

- The answer is seven principles, the first being "Eliminate waste" at `principles.md:17`. Re-derive: `grep -n '^### ' principles.md` prints the seven headings with their line numbers.
- Re-derive the size difference: `wc -c .github/copilot-instructions.md` in scenario 02, then the same command in scenario 03.
- Same answer, 10x the credits. In (a) every later turn pays the same again, because instructions are resent with each request.

The lesson: instructions are for rules that apply to every request. A task runbook applies to one kind of task, and putting it in instructions charges every unrelated request for it. Scenario 03 shows the alternative in full.

### Impact in numbers

Rough figures from the measured runs (percentages are rounded):

- Credits: the lookup cost about 90% less without the runbooks in context (4.0 against 41.74), and about 81% less with them packaged as skills (7.88 against 41.74).
- Context at turn 0: about 83% smaller (20k against 118k). The inlined file alone was 106.5k tokens of system prompt.
- Input tokens sent: about 83% fewer for the one-turn lookup (81.2k against 470.0k). That gap widens with every turn, because the system prompt is resent each time: after ten turns the inlined session has paid for the file ten times.

## Reset

```sh
cce reset 2
cce reset 3
```

`cce setup 2 --force` (or `3`) recreates a worktree from scratch if a reset is not enough.
