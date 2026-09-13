# Scenario 01: instructions hold durable rules, not repo state

## What it shows

Repository instructions (`.github/copilot-instructions.md`) are loaded on every request, so Copilot treats whatever they say as true on every turn. This scenario's instructions embed a copy of `blueprints.md` as it stood on 2025-10-31 and declare that table the approved allowlist: rows not in it must go, drifted links must be restored. Upstream has since added a row, removed a row and retargeted a link, so an obedient assistant now reverts three real changes.

A second file, `.github/copilot-instructions.good.md`, ships alongside but is not loaded. It states the same intent as durable rules about structure (one table, these columns, links must resolve, append at the end) and never lists rows.

You will send one prompt three times: under the stale instructions, under no instructions, and under the durable ones. The prompt never changes; only the instructions do.

## Run it

Before you start: the [setup](../PREREQUISITES.md) is done, `cce doctor` shows no `fail` row and `cce list` shows scenario 01 as `ready`. Keep a second terminal in the worktree for the shell commands (`cd "$(cce path 1)"`).

Record what you see as you go:

| Run | `/context` at turn 0 | Reply: applied, refused or reported? | `/diff` |
| --- | --- | --- | --- |
| 1, stale instructions | | | |
| 2, no instructions | | | |
| 3, durable instructions | | | |

The prompt, identical in all three runs:

```text
Bring blueprints.md into line with the approved blueprints list in the repository instructions.
```

### Run 1: the stale allowlist

1. **Start** a fresh session from the baseline:

   ```sh
   cce reset 1 && cd "$(cce path 1)" && copilot
   ```

2. **Check** before typing: `/context`, and note the number in your table. Expect it to be well above an empty session, because the embedded table is already in context and will be resent on every later turn. `/instructions` confirms the file is loaded.

3. **Send** the prompt.

4. **Observe** the reply. Two outcomes are valid. Either Copilot edits `blueprints.md` to match the stale list, or it pushes back because the path it is asked to restore no longer exists or because it notices the later commits. If it pushes back, answer:

   ```text
   yes, apply the list
   ```

   A refusal is itself the lesson: the model noticed that the instructions describe a repository state that is no longer true. Record which way it went.

5. **Observe** the cost and the damage: `/context` (compare with turn 0), `/usage`, then `/diff`. Expect a diff on `blueprints.md` when the list was applied. Confirm in the shell:

   ```sh
   git diff --stat
   git cat-file -e HEAD:tools/nhsd-git-secrets/README.md; echo "exit=$?"
   ```

   Expect `exit=1`: the path the instructions want restored does not exist at this commit.

6. **Quit and reset**: `/exit`, then `cce reset 1`.

### Run 2: no instructions

1. **Start** with the instructions switched off:

   ```sh
   cce reset 1 && cd "$(cce path 1)" && copilot --no-custom-instructions
   ```

2. **Check**: `/instructions` shows the file toggled off, and `/context` starts close to empty. Note the number next to run 1's.

3. **Send** the same prompt.

4. **Observe**: there is no approved list to compare against, so expect Copilot to ask what the list is or say it cannot find one, and `/diff` to be empty. `git status --porcelain` prints nothing.

5. **Quit and reset**: `/exit`, then `cce reset 1`.

### Run 3: the durable instructions

1. **Start** after swapping in the durable file:

   ```sh
   cce reset 1 && cd "$(cce path 1)"
   cp .github/copilot-instructions.good.md .github/copilot-instructions.md
   copilot
   ```

2. **Check**: `/context` is small again, since the durable file is a few lines with no table.

3. **Send** the same prompt.

4. **Observe**: expect Copilot to report the differences it can see between the table and the rules (or say the table already conforms) and stop without editing, as the durable rules tell it to. `/diff` is empty.

5. **Quit and reset**: `/exit`, then `cce reset 1`.

## What to notice

What must hold on every run: run 1 either edits `blueprints.md` or refuses by naming the drift; runs 2 and 3 leave `/diff` empty. Wording and token counts vary between models and runs.

Run 1's evidence is the same three differences whichever way it went:

- The versioning-template row at `blueprints.md:10` (added upstream on 2025-11-04) is deleted. Re-derive: `grep -n versioning blueprints.md` before the prompt finds it on line 10.
- The secret-scanning row at `blueprints.md:14` is pointed back at `tools/nhsd-git-secrets/README.md`, a path that no longer exists. Re-derive: `grep -n gitleaks blueprints.md` shows the current target on line 14; the `git cat-file` command in run 1 fails at the pin.
- Possibly the cross-account row that upstream deliberately removed on 2025-12-16 is re-added.

A refusal is the same lesson from the other side: the model names those differences as its reason to stop instead of reverting them. Claude Code refused in one measured run and applied the list in another.

Compare the turn-0 `/context` column of your table. In run 1 the embedded table is already in context before you type, and it is paid again on every later turn. Runs 2 and 3 start close to empty, and run 3 still gets the intent across.

The lesson: instructions are the right home for rules that stay true. A snapshot of repository state is a fact with an expiry date, and once it expires the instructions become a tool for undoing progress. Keep such facts in the repository, where git keeps them current, and let the instructions say how to treat them.

## Reset

```sh
cce reset 1
```

`cce setup 1 --force` recreates the worktree from scratch if a reset is not enough.
