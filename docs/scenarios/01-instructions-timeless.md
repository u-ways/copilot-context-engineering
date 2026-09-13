# Scenario 01: instructions hold durable rules, not repo state

## What it shows

Repository instructions (`.github/copilot-instructions.md`) are loaded on every request, so Copilot treats whatever they say as true on every turn. This scenario's instructions embed a copy of the `blueprints.md` table as it stood on 2025-10-31 and declare it the approved allowlist: rows not in it must go, drifted links must be restored. Upstream has since added a row, removed a row and retargeted a link, so an obedient assistant now reverts three real changes.

A second file, `.github/copilot-instructions.good.md`, ships alongside but is not loaded. It states the same intent as durable rules about structure (a heading, an intro, one table with these columns, links must resolve, append at the end) and never lists rows.

You will send one prompt three times: under the stale instructions, under the durable ones, and with instruction loading switched off. The prompt never changes; only the instructions do.

## Run it

Before you start: the [setup](../PREREQUISITES.md) is done, `cce doctor` shows no `fail` row and `cce list` shows scenario 01 as `ready`. Keep a second terminal in the worktree for the shell commands (`cd "$(cce path 1)"`).

Record what you see as you go:

| Run | `/context` at turn 0 → after | AI credits (≈ $) | Reply: applied, refused or reported? | `git status --porcelain` |
| --- | --- | --- | --- | --- |
| 1, stale instructions | | | | |
| 2, durable instructions | | | | |
| 3, loading switched off | | | | |

The prompt, identical in all three runs:

```text
Bring blueprints.md into line with the approved blueprints list in the repository instructions.
```

### Run 1: the stale allowlist

1. **Start** a fresh session from the baseline (answer `1. Yes` to the folder-trust question the first time):

   ```sh
   cce reset 1 && cd "$(cce path 1)" && copilot --allow-all --model claude-sonnet-5
   ```

2. **Check**: `/instructions` lists `.github/copilot-instructions.md` as enabled (Esc to close). `/context`: note the total and the `System Prompt` line, which is where the instructions sit. The embedded table is small, so expect only a little more than an empty session here; scenario 02 shows what a large file does.

3. **Send** the prompt.

4. **Observe** the reply. Expect a `Read blueprints.md` line, then `Edit blueprints.md +8 -8`, and a summary of three changes: a row removed, the secret-scanning row's link and type changed, a row added. If the model pushes back instead, because the path it is asked to restore no longer exists or because it notices the later commits, answer `yes, apply the list`; a refusal is itself the lesson, and worth recording.

5. **Observe** the cost and the damage: `/context` (the `Messages` line now holds the conversation) and `/usage` (`AI Credits`). Confirm in the shell:

   ```sh
   git diff --stat
   git cat-file -e HEAD:tools/nhsd-git-secrets/README.md; echo "exit=$?"
   ```

   Expect `blueprints.md | 16 ++++++++--------` and `exit=128`: the path the instructions want restored does not exist at this commit.

6. **Quit and reset**: `/exit`, then `cce reset 1`.

### Run 2: the durable instructions

1. **Start** after swapping in the durable file and committing the swap. The commit matters: an uncommitted swap shows up as a modified file, and a model that checks `git status` will "restore" the stale original before applying it.

   ```sh
   cce reset 1 && cd "$(cce path 1)"
   cp .github/copilot-instructions.good.md .github/copilot-instructions.md
   git commit -qam "Use the durable instructions"
   copilot --allow-all --model claude-sonnet-5
   ```

2. **Check**: `/context` at turn 0; the `System Prompt` line is a little smaller than run 1's, since the durable file has no table.

3. **Send** the same prompt.

4. **Observe**: expect Copilot to read the file and both instruction files, then report that the instructions contain no list to reconcile against and that the table is the source of truth, and stop without editing. `git status --porcelain` prints nothing, and `/diff` lists only the scenario's own commits, not `blueprints.md`.

5. **Quit and reset**: `/exit`, then `cce reset 1`.

### Run 3: loading switched off

1. **Start** with the instructions file present but not loaded:

   ```sh
   cce reset 1 && cd "$(cce path 1)" && copilot --allow-all --no-custom-instructions --model claude-sonnet-5
   ```

2. **Check**: `/instructions` says the file is disabled for this session; `/context` starts at the bare baseline.

3. **Send** the same prompt.

4. **Observe**: the flag is not a firewall. The prompt names "the repository instructions", so expect the model to go looking: `Search` and `Read copilot-instructions.md` lines, sometimes even a `git show` of the file from history. Having found the stale table on disk, it applies it (`Edit blueprints.md +2 -2` in the measured run). What changed is the turn-0 context, not the outcome.

5. **Quit and reset**: `/exit`, then `cce reset 1`.

## What to notice

What must hold on every run: run 1 edits `blueprints.md` (or refuses by naming the drift); run 2 leaves it untouched; run 3 shows the model searching for the file. Wording and token counts vary between runs.

Measured on Claude Sonnet 5:

| Run | `/context` turn 0 → after | AI credits (≈ $) | Outcome |
| --- | --- | --- | --- |
| 1, stale instructions | 21k → 23k | 6.71 (≈ $0.07) | `+8 -8`: three rows reverted |
| 2, durable instructions | 20k → 23k | 5.46 (≈ $0.05) | no change; differences reported |
| 3, loading switched off | 20k → 26k | 12.78 (≈ $0.13) | searched, found the file, `+2 -2` |

Run 1's evidence is the same three differences whichever way it went:

- The versioning-template row at `blueprints.md:10` (added upstream on 2025-11-04) is deleted. Re-derive: `grep -n versioning blueprints.md` before the prompt finds it on line 10.
- The secret-scanning row at `blueprints.md:14` is pointed back at `tools/nhsd-git-secrets/README.md`, a path that no longer exists. Re-derive: `grep -n gitleaks blueprints.md` shows the current target on line 14; the `git cat-file` command in run 1 fails at the pin.
- The cross-account row that upstream deliberately removed on 2025-12-16 is re-added.

A refusal is the same lesson from the other side: the model names those differences as its reason to stop instead of reverting them.

Run 3 cost the most of the three: without the table in context the model spent its turns hunting for it. Loading is a cost lever; what the file says decides the outcome.

The lesson: instructions are the right home for rules that stay true. A snapshot of repository state is a fact with an expiry date, and once it expires the instructions become a tool for undoing progress. Keep such facts in the repository, where git keeps them current, and let the instructions say how to treat them.

## Reset

```sh
cce reset 1
```

`cce setup 1 --force` recreates the worktree from scratch if a reset is not enough.
