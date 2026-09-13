# Scenario 03: the same procedures as skills cost nothing until matched

## What it shows

The eight procedures that scenario 02 inlined into its instructions are packaged here as Agent Skills under `.github/skills/<name>/SKILL.md`, one per procedure, derived from the same sources. The instructions shrink to a few lines saying that the procedures exist as skills and to consult one only when the task matches its description.

Copilot reads only each skill's front matter (name and description) at start-up. A body enters the context only when a task matches its description. Every procedure ends with a tracer line, `procedure: <name>`, so a load is usually visible in the reply as well as in `/skills`; if a model omits the line, `/skills` is still the proof.

Two prompts: a lookup that matches nothing, and a page-conversion task that matches exactly one skill.

## Run it

Observation protocol for every prompt: start a fresh Copilot session in the worktree, type `/context` before the prompt, send the prompt, then `/context`, `/usage`, `/skills` and `/diff` (or `git status --porcelain`). Personal skills and agents from `~/.copilot` may appear in `/skills`; `cce doctor` warns about them.

```sh
cce reset 3 && cd "$(cce path 3)" && copilot
```

### Prompt A: the lookup from scenario 02

```text
In insights/metrics.md, over how many days is each engineering metric calculated? Reply with the number and the path:line where you found it.
```

### Prompt B: a task that matches a skill

Start a fresh session, then send:

```text
Prepare a conversion plan for tools/aws-fis/jmeter/README.md so that it follows this framework's page conventions. Output the plan only; do not edit any files.
```

## What to notice

Prompt A: the answer is 28 at `insights/metrics.md:24` or `:33` (`grep -n '28 days' insights/metrics.md`); no skill loads; no `procedure:` line; `/context` stays small.

Prompt B: `/skills` shows `convert-page-to-framework-conventions` loaded and nothing else, `/context` grows by that one body, and the reply ends with:

```text
procedure: convert-page-to-framework-conventions
```

A good plan covers the points below, each checkable against the target page (`cat -n tools/aws-fis/jmeter/README.md`):

- Add an H1 (MD041): the page has none.
- Split the content under level-2 headings and, since there will be two or more, add a bulleted table of contents with anchors.
- Add a `## Context` section that opens with the framework's cross-reference line. The page sits three directories deep, so the link must resolve to `../../../principles.md`. A plan with two levels is the likely miss.
- Turn the two bare URLs on lines 5 and 9 into Markdown links (MD034).
- Give the three code fences a language (MD040) and surround them with blank lines (MD031).
- Remove the trailing whitespace on lines 1 and 34 (MD009).
- Replace the routing to an internal team contact on line 36 with a route that works for any reader, in keeping with `CONTRIBUTING.md`.
- Flag the non-inclusive terms in the sibling scripts `start_test.sh` and `jmeter_stop.sh` as follow-up work only; they are outside the page.
- Leave line lengths alone: MD013 is disabled in the repository's lint invocation (`scripts/markdown-check-format.sh:21`), so prose must not be re-wrapped.

Re-derive each point:

```sh
grep -c '^# ' tools/aws-fis/jmeter/README.md          # 0: no H1
grep -n 'https\?://' tools/aws-fis/jmeter/README.md     # lines 5 and 9
grep -n '^`\{3\}' tools/aws-fis/jmeter/README.md       # six fence lines, three blocks
grep -n ' $' tools/aws-fis/jmeter/README.md            # lines 1 and 34
grep -n -i -w master tools/aws-fis/jmeter/*.sh         # the sibling scripts
grep -n MD013 scripts/markdown-check-format.sh         # line 21
```

`git status --porcelain` is empty after both prompts.

The lesson: a skill costs its front matter until it is matched, then exactly its body, and only in the session that needed it. The same text in instructions (scenario 02) is paid by every request.

## Reset

```sh
cce reset 3
```

`cce setup 3 --force` recreates the worktree from scratch if a reset is not enough.
