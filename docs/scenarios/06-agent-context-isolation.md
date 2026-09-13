# Scenario 06: delegate when you need the result, not the investigation

## What it shows

An `auditor` agent (`.github/agents/auditor.agent.md`, tools `[read, search, execute]`) is told to list every Markdown file outside `.github/` and `.claude/`, read each in full, tally the level-2 headings that sit outside code fences, cross-check the total with one shell command and reply with only the number and its scope. The short instructions say to use it for repository-wide tallies.

You will send the same prompt twice: once in a normal session, where Copilot delegates and only the two-line answer comes back, and once with the auditor as your session's own agent, where all 48 file reads land in your context.

## Run it

Before you start: the [setup](../PREREQUISITES.md) is done and `cce list` shows scenario 06 as `ready`. Keep a second terminal in the worktree (`cd "$(cce path 6)"`). These are the slowest runs in the walkthrough: allow about three minutes each.

Record what you see as you go:

| Run | `/context` at turn 0 → after | `Messages` line after | `/usage` Tokens ↑ | AI credits (≈ $) | Answer |
| --- | --- | --- | --- | --- | --- |
| A, delegated | | | | | |
| B, `--agent auditor` | | | | | |

The prompt, identical in both runs:

```text
How many level-2 Markdown headings (lines starting with "## ") are there across the Markdown files in this repository, excluding the .github directory? Use the auditor agent and give me only the number and its scope.
```

### Run A: delegated

1. **Start** a fresh session from the baseline (answer `1. Yes` to the folder-trust question the first time):

   ```sh
   cce reset 6 && cd "$(cce path 6)" && copilot --allow-all --model claude-sonnet-5
   ```

2. **Check**: `/context` at turn 0, around 20k; note the `Messages` line at 0.

3. **Send** the prompt. Expect a collapsed block headed `● Auditor (model: claude-sonnet-5) Count level-2 ...` with a timer: that is the delegated agent working in its own context. Wait for it.

4. **Observe**: expect a two-line answer, 218 and its scope. Then `/context`: the total is barely above turn 0 and the `Messages` line holds only a few hundred tokens, because the reads happened in the auditor's context. `/usage` still shows the whole spend, delegated work included. `git status --porcelain` prints nothing.

5. **Quit and reset**: `/exit`, then `cce reset 6`.

### Run B: direct

1. **Start** with the auditor as your session's own agent:

   ```sh
   cce reset 6 && cd "$(cce path 6)" && copilot --allow-all --model claude-sonnet-5 --agent auditor
   ```

   If the session refuses the growing context or compacts mid-audit, restart with `--context long_context` added and note the compaction in your table.

2. **Check**: `Selected custom agent: auditor`; `/context` at turn 0 is around 7k, since an agent session carries only its own tools.

3. **Send** the same prompt. This time the `Read` lines scroll past in your own session, file after file.

4. **Observe**: expect the same answer, then `/context` with the `Messages` line above 100k: the whole audit now sits in your session. Ask any follow-up question and check `/context` again; every later turn carries it. `git status --porcelain` prints nothing.

5. **Quit and reset**: `/exit`, then `cce reset 6`.

## What to notice

What must hold on every run: the same answer both ways, run A's `Messages` line staying tiny, run B's growing by about the repository. Credits and token totals vary between runs, and the two runs can cost about the same.

Measured on Claude Sonnet 5:

| Run | `/context` turn 0 → after | `Messages` line after | `/usage` Tokens ↑ | AI credits (≈ $) | Time |
| --- | --- | --- | --- | --- | --- |
| A, delegated | 20k → 21k | 467 | 949.2k | 74.97 (≈ $0.75) | 3m 04s |
| B, `--agent auditor` | 7k → 114k | 106.7k | 1.1m | 68.86 (≈ $0.69) | 2m 46s |

Delegation isolates the parent's context; it does not make the work cheaper. Both runs read the whole repository, so both paid for it; `/usage` shows the spend either way, and `/context` shows whose session carries the reads afterwards. In run A you can keep working in a 21k context; in run B every later question drags 114k along.

The non-interactive `just llm copilot` tier measures the same pair through `copilot -p` and reports main-thread and subagent input tokens separately; `just llm claude` does the same on Claude Code.

### The number

- The answer is 218 in both runs, scoped to the 48 upstream Markdown files with `.github` and `.claude` excluded and fenced code ignored. Re-derive: `grep -rhE '^## ' --include='*.md' --exclude-dir=.github --exclude-dir=.claude . | wc -l`.
- Only 144 heading texts are distinct: `grep -rhE '^## ' --include='*.md' --exclude-dir=.github --exclude-dir=.claude . | sort -u | wc -l`. The count is of occurrences; an agent that de-duplicates lands on 144 and is wrong.
- The file count: `git ls-files '*.md' | grep -v '^\.github/' | wc -l` prints 48.
- At this pin no upstream heading sits inside a code fence, so the naive grep agrees with the fence-aware script shipped in this repository: `python3 scripts/s06_ground_truth.py "$(cce path 6)"` from a checkout of copilot-context-engineering prints 218 and the scope sentence.

The lesson: use a custom agent when you need a result and not the trail that produced it. The investigation still costs what it costs, but it stays out of the context you keep working in. Run B is what happens when the same role is worn by the main session instead of dispatched.

### Impact in numbers

Rough figures from the measured runs (percentages are rounded):

- Working context afterwards: about 82% smaller when delegated (21k against 114k), and the conversation itself about 99% smaller (467 tokens against 106.7k on the `Messages` line).
- Cost: within about 8% either way (74.97 against 68.86 credits) and about the same input tokens (949k against 1.1m). Delegation saved nothing on the audit itself.
- What you keep paying: every later turn in the direct session resends the 114k it accumulated, about 5 times what the delegated session resends. Ten follow-up questions cost roughly a million extra input tokens in run B and nothing extra in run A.
- Same answer, 218, in 2 of 2 runs. The choice changes where the investigation lives, not whether it happens.

## Reset

```sh
cce reset 6
```

`cce setup 6 --force` recreates the worktree from scratch if a reset is not enough.
