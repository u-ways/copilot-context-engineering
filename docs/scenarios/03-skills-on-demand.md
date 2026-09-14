# Scenario 03: the same procedures as skills cost nothing until matched

## What it shows

### The topic

Any Decision Records. An ADR is a short document that records one architectural decision: the context, the options considered, the choice and its consequences, so that the reasoning survives the people who made it. The framework ships a lightweight template (`any-decision-record-template.md`) and, in `practices/cloud-services.md` and `practices/cloud-databases.md`, its guidance on when to prefer a managed cloud service over running a component yourself. Choosing a managed database over a self-run one is the textbook case.

### The set-up

The eight procedures that scenario 02 inlined into its instructions are packaged here as Agent Skills under `.github/skills/<name>/SKILL.md`, one per procedure, derived from the same sources. The instructions shrink to a few lines saying that the procedures exist as skills and to consult one only when the task matches its description.

Copilot reads only each skill's front matter (name and description) at start-up. A body enters the context only when the model decides a task matches a description and calls the skill; that call shows in the transcript as `● skill(<name>)`. Every procedure ends with a tracer line, `procedure: <name>`, so a load is usually visible in the reply as well.

You will send two prompts in two fresh sessions: the principles lookup, which matches nothing, and an ADR-writing task, which matches exactly one skill.

## Run it

Before you start: the [setup](../PREREQUISITES.md) is done and `cce list` shows scenario 03 as `ready`. Keep a second terminal in the worktree (`cd "$(cce path 3)"`).

Record what you see as you go:

| Run | `/context` at turn 0 → after | AI credits (≈ $) | `● skill(...)` line? | `procedure:` line in the reply? |
| --- | --- | --- | --- | --- |
| A, the lookup | | | | |
| B, the decision record | | | | |

### Run A: the lookup from scenario 02

1. **Start** a fresh session from the baseline (answer `1. Yes` to the folder-trust question the first time):

   ```sh
   cce reset 3 && cd "$(cce path 3)" && copilot --allow-all --model claude-sonnet-5
   ```

2. **Check**: `/context` starts around 21k; the `System Prompt` line holds the short instructions and the eight skill descriptions. `/skills` lists the eight repository skills with their descriptions; read them, because they are what the model matches the prompt against (Esc to close).

3. **Send**:

   ```text
   In principles.md, how many engineering principles does the framework list, and what is the first one? Reply with the number, the name and the path:line where you found it.
   ```

4. **Observe**: expect seven, "Eliminate waste", at `principles.md:17` (models sometimes misreport the line; the grep in the next section settles it), no `● skill(...)` line, no `procedure:` line, and `/context` grown only by the page the model read. `git status --porcelain` prints nothing.

5. **Quit and reset**: `/exit`, then `cce reset 3`.

### Run B: a task that matches a skill

1. **Start** a fresh session:

   ```sh
   cce reset 3 && cd "$(cce path 3)" && copilot --allow-all --model claude-sonnet-5
   ```

2. **Check**: `/context` at turn 0 again; it should match run A's.

3. **Send**:

   ```text
   Draft an Any Decision Record (ADR) for choosing a managed database service instead of running the database ourselves. Output the ADR only; do not edit any files.
   ```

4. **Observe**: expect a thought along the lines of "this matches the cloud-architecture-decision skill", then the line

   ```text
   ● skill(cloud-architecture-decision)
   ```

   and an ADR whose last line is `procedure: cloud-architecture-decision`. `/context` grows by roughly that one body (about 11.5k tokens in `Messages`; the file is 35 KB, `wc -c .github/skills/cloud-architecture-decision/SKILL.md`). Check the ADR against the template with `grep -n '^#' any-decision-record-template.md` in the shell; the checklist is in the next section. `git status --porcelain` prints nothing: the prompt asked for the ADR only.

5. **Quit and reset**: `/exit`, then `cce reset 3`.

## What to notice

What must hold on every run: run A loads no skill, run B loads exactly one, and neither changes a file. The ADR's wording varies; its shape and grounding are what to judge.

Measured on Claude Sonnet 5:

| Run | `/context` turn 0 → after | `/usage` Tokens ↑ | AI credits (≈ $) | Loaded |
| --- | --- | --- | --- | --- |
| A, the lookup | 21k → 31k | 106.4k | 7.88 (≈ $0.08) | nothing |
| B, the decision record | 21k → 32k | 67.9k | 8.78 (≈ $0.09) | `cloud-architecture-decision` |

A good ADR follows the framework's template and grounds itself in the framework's guidance:

- The template's sections, in order: Context; Decision with Assumptions, Drivers, Options, Outcome and Rationale; Consequences; Compliance; Notes; Actions; Tags. Re-derive: `grep -n '^#' any-decision-record-template.md`.
- Options that name both choices, a managed service and a self-run database, and drivers drawn from the framework's cloud guidance: operational burden, patching and backups, the skills a team must keep, and lock-in. Re-derive where that guidance lives: `grep -n -i 'managed' practices/cloud-services.md practices/cloud-databases.md | head`.
- An outcome that picks the managed service and consequences that state what the team gives up as well as what it gains.
- The tracer line `procedure: cloud-architecture-decision` at the end.

Compare run A with scenario 02's run (a): the same eight procedures, and the lookup that cost 41.74 credits there costs 7.88 here. Run B paid for one body, once, in the session that needed it.

The lesson: a skill costs its front matter until it is matched, then exactly its body, and only in the session that needed it. The same text in instructions (scenario 02) is paid by every request.

### Impact in numbers

Rough figures from the measured runs (percentages are rounded):

- Unmatched task: the lookup cost about 81% less than the same lookup with every procedure inlined (7.88 against scenario 02's 41.74). Eight skills sat available for the price of their descriptions.
- Matched task: loading one skill added about 11.5k tokens to the context (21k → 32k, roughly 52% larger) and the session cost 8.78 credits. Even that run, which did real work with a procedure, cost about 79% less than scenario 02's trivial lookup with all eight inlined (8.78 against 41.74).
- Scope of the cost: one body, in one session. The other seven procedures cost nothing, and a fresh session starts at 21k again.

## Reset

```sh
cce reset 3
```

`cce setup 3 --force` recreates the worktree from scratch if a reset is not enough.
