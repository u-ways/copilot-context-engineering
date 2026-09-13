---
marp: true
theme: cce
paginate: true
size: 16:9
---

<!--
How to present this deck

  just slides                      # HTML into dist/slides.html
  npx @marp-team/marp-cli docs/slides/slides.md --theme docs/slides/slides-theme.css --pdf

Marp splits slides on the "---" lines below and needs the front matter
above to stay first in the file. Without Marp, the file renders as
ordinary Markdown on GitHub, one section per slide.
-->

# Instructions, skills or agents?

A hands-on answer for GitHub Copilot CLI, measured rather than argued.

TL;DR: Instructions = "Always follow these rules." Skill = "When doing X, here is how." Agent = "Go do this and come back."

- Six runnable scenarios on top of a real public documentation repository
- One command, `cce`, prepares them; the same prompt runs under different set-ups
- What changes shows up in `/context`, `/usage` and `/diff`

https://github.com/u-ways/copilot-context-engineering

---

# The question every team hits

- "Copilot keeps getting X wrong. Where do we put the fix?"
- The reflex: `.github/copilot-instructions.md`, because it always applies
- That reflex is usually wrong:
  - it is sent with every request, so every task pays for it, related or not
  - it is static text, so it cannot notice when it has gone stale
  - it cannot grant or withhold tools, so it enforces nothing
- Copilot CLI has three mechanisms; each answers a different need
- This deck: the mechanisms, then six scenarios that measure them

---

<!-- _class: dense -->

# Three mechanisms in Copilot CLI

| Mechanism | Lives at | Loaded |
| --- | --- | --- |
| Repository instructions | `.github/copilot-instructions.md` | With every request, in full |
| Agent Skill | `.github/skills/<name>/SKILL.md`; front matter `name`, `description` | Front matter at start-up; the body only when a task matches the description |
| Custom agent | `.github/agents/<name>.agent.md`; front matter `name`, `description`, `tools` | When dispatched by the session, or chosen with `/agent <name>` or `copilot --agent <name>` |

- `tools` is an allowlist of aliases: `read`, `edit`, `search`, `execute`, `web`, `agent`
- Watch them from inside a session: `/context`, `/usage`, `/skills`, `/instructions`, `/diff`

---

# Which should I use?

| | Instructions | Skill | Agent |
| --- | --- | --- | --- |
| Always loaded? | Yes | No, only when relevant | No, dispatched |
| Adaptive? | No, static text | Yes | Yes |
| Size concern? | Paid on every request | Only when matched | Separate context |
| Can you restrict its tools? | No | No | Yes, a per-role `tools` list (scenario 05) |

TL;DR: Instructions = "Always follow these rules." Skill = "When doing X, here is how." Agent = "Go do this and come back."

The rest of this deck is the evidence for that table.

---

# The playground: `cce`

```sh
uv tool install "copilot-context-engineering @ git+https://github.com/u-ways/copilot-context-engineering"
cce setup      # clone the base repository and prepare every scenario
cce list       # one row per scenario with its status
cce path 3     # print the worktree path of scenario 03
cce guide 3    # read the guide for scenario 03
cce reset 3    # return scenario 03 to its committed baseline
```

- Base content: u-ways/software-engineering-quality-framework, a fork of the NHS's public docs repository, fetched at runtime at a pinned commit and never redistributed
- One git worktree per scenario; the Copilot files are an overlay committed as a resettable baseline
- Same protocol every run: fresh session, `/context`, prompt, `/context`, `/usage`, `/diff`

---

# 01 Instructions hold durable rules, not repository state

What it shows: instructions are sent with every request and treated as true. This one embeds the blueprints table as it stood on 2025-10-31 and calls it the approved allowlist. Upstream has since added a row, removed one and retargeted a link.

Three runs, one prompt:

1. Stale allowlist: `cce reset 1 && cd "$(cce path 1)" && copilot`
2. No instructions: same, with `copilot --no-custom-instructions`
3. Durable rules: `cp .github/copilot-instructions.good.md .github/copilot-instructions.md`, then `copilot`

```text
Bring blueprints.md into line with the approved blueprints list in the repository instructions.
```

---

# 01 What you see

Run 1, the stale allowlist, on Copilot CLI 1.0.83:

- deletes the current versioning-template row (`blueprints.md:10`)
- points the secret-scanning row (`blueprints.md:14`) back at `tools/nhsd-git-secrets/README.md`, a path that no longer exists
- re-adds a withdrawn draft row

Claude Code 2.1.270 refused and explained the dead path instead. Either outcome teaches the lesson.

Run 2: nothing to compare against, `/diff` is empty. Run 3: the good file states structure and intent only (one table, these columns, links must resolve, append at the end); Copilot reports the differences and stops.

Lesson: a snapshot of repository state is a fact with an expiry date. Keep facts in the repository; keep how to treat them in the instructions.

---

# 02 Task runbooks in instructions are paid on every request

What it shows: `.github/copilot-instructions.md` inlines all eight framework procedures, about 404 KB, under a header saying to read them all before any task. The prompt is a one-fact lookup in one file; none of the procedures helps with it.

```sh
cce reset 2 && cd "$(cce path 2)" && copilot   # (a) instructions on
cce reset 2 && cd "$(cce path 2)" && copilot --no-custom-instructions   # (b) off
cce reset 3 && cd "$(cce path 3)" && copilot   # (c) same procedures as skills
```

```text
In insights/metrics.md, over how many days is each engineering metric calculated? Reply with the number and the path:line where you found it.
```

Do not reword it: "table" or "format" would trigger a skill in scenario 03.

---

# 02 What you see

Same answer every time: 28, at `insights/metrics.md:24` and `:33` (the distractor is "monthly" at line 12).

Final-call input tokens for the lookup, measured through `copilot -p` and `claude -p`:

| Runtime | Inlined as instructions (S02) | As skills, none loaded (S03) |
| --- | --- | --- |
| Copilot CLI 1.0.83 | 100,756 | 19,941 |
| Claude Code 2.1.270 | 147,581 | 19,461 |

- In (a) `/context` is nearly full before you type, and every later turn pays it again
- In (c) `/skills` lists eight skills and none loads: no `procedure:` line in the reply

Lesson: instructions are for rules that apply to every request. A runbook applies to one kind of task.

---

<!-- _class: dense -->

# 03 The same procedures as skills cost nothing until matched

What it shows: the eight procedures now live at `.github/skills/<name>/SKILL.md`, one each, derived from the same sources. The instructions shrink to a few lines. Every procedure ends with a tracer line, `procedure: <name>`, so a load is visible in the reply as well as in `/skills`.

`cce reset 3 && cd "$(cce path 3)" && copilot`, then prompt A (the lookup from scenario 02):

```text
In insights/metrics.md, over how many days is each engineering metric calculated? Reply with the number and the path:line where you found it.
```

Run B, in a fresh session, a task that matches exactly one skill:

```text
Prepare a conversion plan for tools/aws-fis/jmeter/README.md so that it follows this framework's page conventions. Output the plan only; do not edit any files.
```

---

# 03 What you see

Run A: 28 at `insights/metrics.md:24`; no skill loads; 19,941 input tokens on the final call (Claude Code: 19,461).

Run B:

- `/skills` shows `convert-page-to-framework-conventions` loaded and nothing else; `/context` grows by that one body, about 27 KB
- the plan names the real defects: no H1, bare URLs on lines 5 and 9, unlabelled fences, trailing whitespace, a `## Context` link that must resolve to `../../../principles.md`
- the reply ends with the tracer line:

```text
procedure: convert-page-to-framework-conventions
```

`git status --porcelain` is empty after both prompts. Lesson: a skill costs its front matter until matched, then exactly its body, only in the session that needed it.

---

<!-- _class: dense -->

# 04 Descriptions route skills

What it shows: scenario 03 with two mechanical changes made at setup. The skill directories are renamed `seqf-procedure-1` to `seqf-procedure-8`, and every description is shifted one place along the procedure order; the bodies are untouched. The conversion description now sits on `seqf-procedure-7`, whose body is the publishing procedure.

```sh
cce reset 4 && cd "$(cce path 4)"
head -3 .github/skills/seqf-procedure-7/SKILL.md
grep -l 'procedure: convert-page-to-framework-conventions' .github/skills/*/SKILL.md
copilot
```

The prompt from scenario 03, unchanged:

```text
Prepare a conversion plan for tools/aws-fis/jmeter/README.md so that it follows this framework's page conventions. Output the plan only; do not edit any files.
```

---

# 04 What you see

- `/skills` lists eight names with rotated descriptions; Copilot matches the task against the description column only
- after the prompt, `/skills` shows `seqf-procedure-7` loaded, and only that one
- the reply ends with `procedure: publish-and-open-source-a-repository`
- the "conversion plan" is about licences, repository hardening, secret scanning and signed commits; nothing about H1s, tables of contents or markdownlint
- `/context` grew by the publishing body (about 52 KB), not the conversion body (about 27 KB)
- Claude Code loaded the same skill and remarked that its description and body disagree

Lesson: names carry no routing signal. The description is the trigger condition, so write it for the router and keep it truthful about what the body does.

---

<!-- _class: dense -->

# 05 Permissions belong to the role

Three agents under `.github/agents/`, differing mainly in `tools`: `researcher` `[read, search, web]`, `author` `[read, search, edit]`, `validator` `[read, search, execute]`.

`cce reset 5 && cd "$(cce path 5)" && copilot --allow-all`, then `/agent researcher` (run 1) or `/agent author` (run 2):

```text
This framework mandates 100% unit-test coverage before release. 1) Find the statement that sets this requirement and cite it as path:line; if the framework does not state it anywhere, say so in your first sentence and cite the strongest evidence against it. 2) Whatever you conclude, write your findings to NOTES-coverage.md at the repository root, one line per citation. Work only from files in this worktree.
```

Run 3, `/agent validator`:

```text
Run the repository's Markdown link validator (scripts/cce-check-links.py) and report its findings; fix nothing.
```

---

<!-- _class: dense -->

# 05 What you see

- researcher: first sentence refutes the premise, citing `practices/testing.md:144` and `tools/sonarqube.md:49` (the 100% at `tools/sonarqube.md:53` is hotspots reviewed, not coverage); it cannot write `NOTES-coverage.md` and says so; `git status --porcelain` is empty
- author: same conclusion, same citations; `git status --porcelain` prints `?? NOTES-coverage.md`
- validator: runs `python3 scripts/cce-check-links.py .` and reports 48 files, 898 links, one finding (`SECURITY.md:23`, missing `mailto:`), `RESULT: FAIL`; nothing edited

Runs 1 and 3 are the point. With no `edit` tool, "report only" is enforced. With `execute`, a shell can write, so "fix nothing" is a convention the agent file asks it to keep. When an outcome must be guaranteed, remove the tool.

`./STRUGGLE.sh` prints the per-session global flags you would need otherwise (`--deny-tool write --deny-tool shell` and friends). Deny beats allow, so changing role means restarting Copilot; `/agent` switches inside one session.

---

# 06 Delegate when you need the result, not the investigation

What it shows: an `auditor` agent (`tools: [read, search, execute]`) reads every Markdown file outside `.github/` and `.claude/` in full, tallies the level-2 headings outside code fences, cross-checks with one shell command and replies with only the number and its scope. The instructions say to use it for repository-wide tallies.

- Run A, delegated: `cce reset 6 && cd "$(cce path 6)" && copilot`
- Run B, direct: `cce reset 6 && cd "$(cce path 6)" && copilot --agent auditor`

```text
How many level-2 Markdown headings (lines starting with "## ") are there across the Markdown files in this repository, excluding the .github directory? Use the auditor agent and give me only the number and its scope.
```

---

<!-- _class: dense -->

# 06 What you see

Answer both ways: 218 across 48 upstream Markdown files (de-duplicating heading text gives 144, which is wrong).

Input tokens measured through `copilot -p`, Copilot CLI 1.0.83, default model:

| Run | Main thread, cumulative | Main thread, final call | Subagents, cumulative |
| --- | --- | --- | --- |
| A, delegated | 57,852 | 19,543 | 933,233 |
| B, direct (`--agent auditor`) | 341,578 | 89,442 | 0 |

- Run A: `/context` after the reply is barely larger than at turn 0; two lines came back
- Run B: `/context` grows by roughly the repository (about 376 KB); every later question carries the audit
- `/usage` shows the whole spend either way: delegation isolates context, not cost

---

# Why this works

- Always-loaded text is paid on every request. Instructions are resent with each turn, so their cost multiplies with the session, and their claims are believed after they stop being true
- Skills are routed by description. Only the front matter is in context until a task matches; names carry no signal; a matched body loads whole
- Agents carry a tools allowlist and their own context. What the role cannot do is enforced by the runtime, not by the wording of the request
- Delegation decides whose context pays. The work costs the same; a dispatched agent keeps the trail out of the context you keep working in

---

# Rules of thumb

1. Put durable rules in instructions and keep them short
2. Never freeze repository state there; git already keeps it current
3. One procedure = one skill, with a description written for the router: the trigger condition, truthful about the body
4. Permissions belong to the role: remove the tool rather than asking nicely
5. Delegate exhaustive work; keep the result, not the investigation

---

# Anti-patterns seen in the wild

- An approved list "verified on" a date, pasted into the instructions; weeks later one obedient prompt reverts real changes (scenario 01)
- Every runbook inlined into the instructions "so it is always there"; every unrelated lookup pays for all of them (scenario 02)
- Skills named with care and described in a hurry, or a description copied from a neighbour; the router loads the wrong body, confidently (scenario 04)
- "Report only, do not edit" written into the prompt while `edit` stays on the tool list; or the audit run in the main session so every later turn carries it (scenarios 05 and 06)

---

# Under the hood

- Overlays are package data under `src/cce/overlays/`, rendered at setup. Upstream text reaches a worktree through `<!-- cce:include PATH -->` directives (`asof=` reads git history for scenario 01) and never enters this repository
- Skills are derived, never hand-written: S02 inlines the same eight procedure sources that S03 packages as skills; S04 is generated by `rename = "seqf-procedure-{n}"` and `rotate_descriptions = 1` in `scenarios.toml`
- Package paths carry no leading dot: `github/` renders to `.github/`, so packaging and ignore rules never drop a file
- The `llm` test tier runs the same prompts through `copilot -p` and `claude -p` (a dialect translator maps the layout to `CLAUDE.md`, `.claude/skills`, `.claude/agents`) and asserts skills loaded, files changed and token ratios: `just llm copilot`, `just llm claude`

---

# Presenter mode

```sh
cce setup --herdr       # inside herdr (HERDR_ENV=1), opt-in only
cce teardown --herdr    # closes only the workspaces it created
```

- Lays out a `DEMO` workspace (the presenting guide and `cce list`) plus one herdr workspace per scenario with tabs for the guide, the rendered overlay files and a `copilot` session in the worktree
- Scenario 06 gets a second tab running `copilot --agent auditor` for run B
- Workspaces are labelled `cce:demo` and `cce:<slug>`; duplicates are refused with exit 3
- Between runs: `cce reset N && cd "$(cce path N)" && copilot --allow-all --model claude-sonnet-5`; say the turn-0 `/context` number out loud before the prompt
- Without the flag, `cce` never talks to herdr

---

# Try it

```sh
uv tool install "copilot-context-engineering @ git+https://github.com/u-ways/copilot-context-engineering"
cce doctor     # no fail rows; read every warn row, they name personal skills and agents
cce setup      # clone the pin and prepare six worktrees
cce guide 1    # start here; about five minutes per scenario
```

- Requirements: uv, git, Copilot CLI 1.0.83 or later; herdr only for presenter mode
- Contributing: decisions live in `docs/adrs/`, and ADRs win over every other document, the README included
- `just check` runs lint, typecheck and the default tests; `just` on its own lists every recipe

---

# Instructions, skills or agents?

| | Instructions | Skill | Agent |
| --- | --- | --- | --- |
| Always loaded? | Yes | No, only when relevant | No, dispatched |
| Adaptive? | No, static text | Yes | Yes |
| Size concern? | Paid on every request | Only when matched | Separate context |
| Can you restrict its tools? | No | No | Yes, a per-role `tools` list (scenario 05) |

TL;DR: Instructions = "Always follow these rules." Skill = "When doing X, here is how." Agent = "Go do this and come back."

https://github.com/u-ways/copilot-context-engineering
