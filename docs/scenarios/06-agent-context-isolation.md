# Scenario 06: delegate when you need the result, not the investigation

## What it shows

An `auditor` agent (`.github/agents/auditor.agent.md`, tools `[read, search, execute]`) is told to list every Markdown file outside `.github/` and `.claude/`, read each in full, tally the level-2 headings that sit outside code fences, cross-check the total with one shell command and reply with only the number and its scope. The short instructions say to use it for repository-wide tallies.

You will send the same prompt twice: once in a normal session, where Copilot delegates and only the two-line answer comes back, and once with the auditor as your session's own agent, where all 48 file reads land in your context.

## Run it

Before you start: the [setup](../PREREQUISITES.md) is done and `cce list` shows scenario 06 as `ready`. Keep a second terminal in the worktree (`cd "$(cce path 6)"`). These are the slowest runs in the walkthrough: allow a few minutes each.

Record what you see as you go:

| Run | `/context` at turn 0 | `/context` after the reply | `/usage` | Compaction? | Answer |
| --- | --- | --- | --- | --- | --- |
| A, delegated | | | | | |
| B, `--agent auditor` | | | | | |

The prompt, identical in both runs:

```text
How many level-2 Markdown headings (lines starting with "## ") are there across the Markdown files in this repository, excluding the .github directory? Use the auditor agent and give me only the number and its scope.
```

### Run A: delegated

1. **Start** a fresh session from the baseline:

   ```sh
   cce reset 6 && cd "$(cce path 6)" && copilot
   ```

2. **Check**: `/context` at turn 0, and note the number.

3. **Send** the prompt. Copilot hands the work to the auditor; expect to see it dispatched and to wait while the auditor reads the repository.

4. **Observe**: expect a two-line answer, 218 and its scope. Then `/context`: it should be barely larger than at turn 0, because the reads happened in the auditor's own context. `/usage` still shows the whole spend, delegated work included. `/diff` is empty.

5. **Quit and reset**: `/exit`, then `cce reset 6`.

### Run B: direct

1. **Start** with the auditor as your session's own agent:

   ```sh
   cce reset 6 && cd "$(cce path 6)" && copilot --agent auditor
   ```

   If the session refuses the growing context or compacts mid-audit, restart with `copilot --agent auditor --context long_context` and note the compaction in your table.

2. **Check**: `/context` at turn 0; it should match run A's.

3. **Send** the same prompt. This time the reads scroll past in your own session.

4. **Observe**: expect the same answer, then `/context` grown by roughly the size of the repository (48 files, about 376 KB of Markdown). Ask any follow-up question and check `/context` again: the audit is still there, and every later turn carries it. `/diff` is empty.

5. **Quit and reset**: `/exit`, then `cce reset 6`.

## What to notice

What must hold on every run: the same answer both ways, run A's `/context` barely moving, run B's growing by about the repository. Token totals vary between models and runs.

For scale, one measurement of both runs through the non-interactive `copilot -p` runner (Copilot CLI 1.0.83, the default model) gave:

| Run | Main thread, cumulative input tokens | Main thread, final call | Subagents, cumulative input tokens | Total input tokens |
| --- | --- | --- | --- | --- |
| A, delegated | 57,852 | 19,543 | 933,233 | 991,085 |
| B, `--agent auditor` | 341,578 | 89,442 | 0 | 341,578 |

Delegation isolates the parent's context; it does not make the work cheaper. The delegated run spent almost three times as many tokens overall, because the subagent re-read files across several calls. `/usage` shows the whole spend; `/context` shows whose context carries it. `just llm copilot` in this repository re-measures these figures.

Claude Code 2.1.270 is a second data point on the same prompts: delegated, 70,316 input tokens cumulative in the main thread and 1,041,446 in subagents; direct, 791,339 in the main thread. `just llm claude` re-measures those.

### The number

- The answer is 218 in both runs, scoped to the 48 upstream Markdown files with `.github` and `.claude` excluded and fenced code ignored. Re-derive: `grep -rhE '^## ' --include='*.md' --exclude-dir=.github --exclude-dir=.claude . | wc -l`.
- Only 144 heading texts are distinct: `grep -rhE '^## ' --include='*.md' --exclude-dir=.github --exclude-dir=.claude . | sort -u | wc -l`. The count is of occurrences; an agent that de-duplicates lands on 144 and is wrong.
- The file count: `git ls-files '*.md' | grep -v '^\.github/' | wc -l` prints 48.
- At this pin no upstream heading sits inside a code fence, so the naive grep agrees with the fence-aware script shipped in this repository: `python3 scripts/s06_ground_truth.py "$(cce path 6)"` from a checkout of copilot-context-engineering prints 218 and the scope sentence.

### The two contexts

- Run A: the parent's `/context` after the reply is barely larger than at turn 0; the reads happened in the auditor's own context and only two lines came back. `/usage` still shows the whole spend, delegated work included: delegation isolates context, not cost.
- Run B: `/context` balloons by roughly the size of the repository, possibly with a compaction on the way, and every later question in that session carries the audit with it.
- `git status --porcelain` is empty in both runs.

The lesson: use a custom agent when you need a result and not the trail that produced it. The investigation still costs what it costs, but it stays out of the context you keep working in. Run B is what happens when the same role is worn by the main session instead of dispatched.

## Reset

```sh
cce reset 6
```

`cce setup 6 --force` recreates the worktree from scratch if a reset is not enough.
