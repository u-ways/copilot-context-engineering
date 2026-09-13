# Scenario 03: the same procedures as skills cost nothing until matched

## What it shows

The eight procedures that scenario 02 inlined into its instructions are packaged here as Agent Skills under `.github/skills/<name>/SKILL.md`, one per procedure, derived from the same sources. The instructions shrink to a few lines saying that the procedures exist as skills and to consult one only when the task matches its description.

Copilot reads only each skill's front matter (name and description) at start-up. A body enters the context only when the model decides a task matches a description and calls the skill; that call shows in the transcript as `● skill(<name>)`. Every procedure ends with a tracer line, `procedure: <name>`, so a load is usually visible in the reply as well.

You will send two prompts in two fresh sessions: a lookup that matches nothing, and a page-conversion task that matches exactly one skill.

## Run it

Before you start: the [setup](../PREREQUISITES.md) is done and `cce list` shows scenario 03 as `ready`. Keep a second terminal in the worktree (`cd "$(cce path 3)"`).

Record what you see as you go:

| Run | `/context` at turn 0 → after | AI credits (≈ $) | `● skill(...)` line? | `procedure:` line in the reply? |
| --- | --- | --- | --- | --- |
| A, the lookup | | | | |
| B, the conversion plan | | | | |

### Run A: the lookup from scenario 02

1. **Start** a fresh session from the baseline (answer `1. Yes` to the folder-trust question the first time):

   ```sh
   cce reset 3 && cd "$(cce path 3)" && copilot --allow-all --model claude-sonnet-5
   ```

2. **Check**: `/context` starts around 21k; the `System Prompt` line holds the short instructions and the eight skill descriptions. `/skills` lists the eight repository skills with their descriptions; read them, because they are what the model matches the prompt against (Esc to close).

3. **Send**:

   ```text
   In insights/metrics.md, over how many days is each engineering metric calculated? Reply with the number and the path:line where you found it.
   ```

4. **Observe**: expect 28, cited at `insights/metrics.md:24` and `:33`, no `● skill(...)` line, no `procedure:` line, and `/context` barely changed. `git status --porcelain` prints nothing.

5. **Quit and reset**: `/exit`, then `cce reset 3`.

### Run B: a task that matches a skill

1. **Start** a fresh session:

   ```sh
   cce reset 3 && cd "$(cce path 3)" && copilot --allow-all --model claude-sonnet-5
   ```

2. **Check**: `/context` at turn 0 again; it should match run A's.

3. **Send**:

   ```text
   Prepare a conversion plan for tools/aws-fis/jmeter/README.md so that it follows this framework's page conventions. Output the plan only; do not edit any files.
   ```

4. **Observe**: expect a thought along the lines of "this task matches the convert-page-to-framework-conventions skill", then the line

   ```text
   ● skill(convert-page-to-framework-conventions)
   ```

   and a plan whose last line is `procedure: convert-page-to-framework-conventions`. `/context` grows by roughly that one body (about 10k tokens in `Messages`; the file is 27 KB, `wc -c .github/skills/convert-page-to-framework-conventions/SKILL.md`). Check the plan against the page with `cat -n tools/aws-fis/jmeter/README.md` in the shell; the checklist is in the next section. `git status --porcelain` prints nothing: the prompt asked for a plan only.

5. **Quit and reset**: `/exit`, then `cce reset 3`.

## What to notice

What must hold on every run: run A loads no skill, run B loads exactly one, and neither changes a file. The plan's wording varies; its coverage of the checklist below is what to judge.

Measured on Claude Sonnet 5:

| Run | `/context` turn 0 → after | `/usage` Tokens ↑ | AI credits (≈ $) | Loaded |
| --- | --- | --- | --- | --- |
| A, the lookup | 21k → 22k | 84.4k | 4.38 (≈ $0.04) | nothing |
| B, the conversion plan | 21k → 32k | 182.5k | 14.9 (≈ $0.15) | `convert-page-to-framework-conventions` |

A good plan covers these points, each checkable against the page:

- Add an H1 (MD041): the page has none.
- Split the content under level-2 headings and, since there will be two or more, add a bulleted table of contents with anchors.
- Add a `## Context` section that opens with the framework's cross-reference line. The page sits three directories deep, so the link must resolve to `../../../principles.md`; the measured plan worked that out explicitly.
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

Compare run A with scenario 02's run (a): the same eight procedures, and the lookup that cost 35 credits there costs 4 here. Run B paid for one body, once, in the session that needed it.

The lesson: a skill costs its front matter until it is matched, then exactly its body, and only in the session that needed it. The same text in instructions (scenario 02) is paid by every request.

## Reset

```sh
cce reset 3
```

`cce setup 3 --force` recreates the worktree from scratch if a reset is not enough.
