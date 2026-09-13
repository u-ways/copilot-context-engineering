# Scenario 01: instructions hold durable rules, not repo state

## What it shows

Repository instructions are loaded on every request, so Copilot treats whatever they say as true on every turn. This scenario ships a `.github/copilot-instructions.md` that embeds a copy of `blueprints.md` as it stood on 2025-10-31 and declares that table the approved allowlist: rows not in it must go, drifted links must be restored. Upstream has since added a row, removed a row and retargeted a link, so an obedient assistant now reverts three real changes.

A second file, `.github/copilot-instructions.good.md`, is shipped alongside but not loaded. It states the same intent as durable rules about structure (one table, these columns, links must resolve, append at the end) and never lists rows.

Three beats run one prompt under the stale instructions, under no instructions and under the durable ones.

## Run it

Observation protocol for every beat: start a fresh Copilot session in the worktree, type `/context` before the prompt, send the prompt, then `/context`, `/usage` and `/diff` (or `git status --porcelain`). Personal skills and agents from `~/.copilot` may appear in `/skills`; `cce doctor` warns about them.

The prompt is the same in all three beats:

```text
Bring blueprints.md into line with the approved blueprints list in the repository instructions.
```

### Beat 1: the stale allowlist

```sh
cce reset 1 && cd "$(cce path 1)" && copilot
```

Send the prompt. If the model pushes back, because the path it is asked to restore no longer exists or because it spots the later commits, answer:

```text
yes, apply the list
```

A refusal is itself a valid lesson: the model noticed that the instructions describe a repository state that is no longer true. Record which way it went.

### Beat 2: no instructions

```sh
cce reset 1 && cd "$(cce path 1)" && copilot --no-custom-instructions
```

Type `/instructions` to confirm the file is toggled off, then send the prompt.

### Beat 3: the durable instructions

```sh
cce reset 1 && cd "$(cce path 1)"
cp .github/copilot-instructions.good.md .github/copilot-instructions.md
copilot
```

Send the prompt.

## What to notice

Beat 1 has two valid outcomes, and the same three differences are the evidence for both:

- The versioning-template row at `blueprints.md:10` (added upstream on 2025-11-04) is deleted. Re-derive: `grep -n versioning blueprints.md` before the prompt finds it on line 10.
- The secret-scanning row at `blueprints.md:14` is pointed back at `tools/nhsd-git-secrets/README.md`, a path that no longer exists. Re-derive: `grep -n gitleaks blueprints.md` shows the current target on line 14; `git cat-file -e HEAD:tools/nhsd-git-secrets/README.md` fails at the pin.
- Possibly the cross-account row that upstream deliberately removed on 2025-12-16 is re-added.

A refusal is the same lesson from the other side, the model naming those differences as its reason to stop instead of reverting them; Claude Code refused in one measured run and applied the list in another.

```sh
git diff --stat
git cat-file -e HEAD:tools/nhsd-git-secrets/README.md; echo "exit=$?"
```

Beat 2: there is no approved list to compare against, so Copilot changes nothing; `/diff` is empty. Beat 3: Copilot reports the differences it can see and stops, as the durable rules tell it to; `/diff` is empty.

Compare the turn-0 `/context` across beats. In beat 1 the embedded table is already in context before you type, and it is paid again on every later turn. Beat 2 starts close to empty.

The lesson: instructions are the right home for rules that stay true. A snapshot of repository state is a fact with an expiry date, and once it expires the instructions become a tool for undoing progress. Keep such facts in the repository, where git keeps them current, and let the instructions say how to treat them.

## Reset

```sh
cce reset 1
```

`cce setup 1 --force` recreates the worktree from scratch if a reset is not enough.
