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

Topic: the framework's GitHub Actions security page. In March 2026 upstream made SHA pinning mandatory, replaced `@v3` tags with pinned SHAs and added a Dependabot `cooldown`.

What it shows: instructions are sent with every request and treated as true. This one embeds that page as it stood on 2025-10-31 and calls it the approved text.

Three runs, one prompt:

1. Stale guidance: `cce reset 1 && cd "$(cce path 1)" && copilot --allow-all --model claude-sonnet-5`
2. Durable rules: `cp .github/copilot-instructions.good.md .github/copilot-instructions.md && git commit -qam "durable"`, then the same
3. Loading switched off: the same with `--no-custom-instructions`

```text
Bring practices/actions-best-practices.md into line with the approved GitHub Actions guidance in the repository instructions.
```

---

# 01 What you see

Measured on Claude Sonnet 5, Copilot CLI 1.0.83:

| Run | `/context` | AI credits | Outcome |
| --- | --- | --- | --- |
| 1, stale guidance | 23k → 30k | 15.53 | page rewritten: five `@v3` tags back, cooldown gone, "must" softened |
| 2, durable rules | 20k → 26k | 7.21 | differences reported, nothing changed |
| 3, loading off | 20k → 34k | 16.38 | searched, read the file from disk, same damage |

Re-derive: `grep -c 'actions/checkout@v3' practices/actions-best-practices.md` (0 at the baseline) and `grep -c cooldown` (2).

Lesson: a snapshot of repository content is a fact with an expiry date. Keep the content in the repository; keep how to treat it in the instructions. Switching loading off is a cost lever, not a firewall.

---

# 02 Task runbooks in instructions are paid on every request

Topic: `principles.md`, the framework's seven lean-inspired engineering principles, and its eight long task procedures (about 413 KB).

What it shows: `.github/copilot-instructions.md` inlines all eight procedures under a header saying to read them all before any task. The prompt is a one-fact lookup on the principles page; none of the procedures helps with it.

```sh
cce reset 2 && cd "$(cce path 2)" && copilot --allow-all --model claude-sonnet-5   # (a) instructions on
cce reset 2 && cd "$(cce path 2)" && copilot --allow-all --model claude-sonnet-5 --no-custom-instructions   # (b) off
cce reset 3 && cd "$(cce path 3)" && copilot --allow-all --model claude-sonnet-5   # (c) same procedures as skills
```

```text
In principles.md, how many engineering principles does the framework list, and what is the first one? Reply with the number, the name and the path:line where you found it.
```

---

# 02 What you see

Same answer every time: seven, "Eliminate waste", `principles.md:17`.

Measured on Claude Sonnet 5:

| Run | `/context` at turn 0 | `System Prompt` | Tokens ↑ | AI credits |
| --- | --- | --- | --- | --- |
| (a) inlined as instructions | 118k | 106.5k | 470.0k | 41.74 |
| (b) loading switched off | 20k | 8.3k | 81.2k | 4.00 |
| (c) as skills, none loaded | 21k | 9.1k | 106.4k | 7.88 |

- In (a) `/context` is nearly half full before you type, and every later turn pays it again
- In (c) `/skills` lists eight skills and none loads: no `● skill(...)` line, no `procedure:` line

Lesson: instructions are for rules that apply to every request. A runbook applies to one kind of task.

---

<!-- _class: dense -->

# 03 The same procedures as skills cost nothing until matched

Topic: Any Decision Records, the framework's template for recording one architectural decision, and its guidance on managed cloud services versus self-run components.

What it shows: the eight procedures now live at `.github/skills/<name>/SKILL.md`, one each, derived from the same sources. The instructions shrink to a few lines. A load shows as `● skill(<name>)` in the transcript, and every procedure ends with a tracer line, `procedure: <name>`.

Run A: the principles lookup from scenario 02, in a fresh session. Run B, in another fresh session, a task that matches exactly one skill:

```text
Draft an Any Decision Record (ADR) for choosing a managed database service instead of running the database ourselves. Output the ADR only; do not edit any files.
```

---

# 03 What you see

Run A: seven principles, "Eliminate waste"; no skill loads; 7.88 credits against 41.74 with everything inlined.

Run B (8.78 credits, `/context` 21k → 32k):

- `● skill(cloud-architecture-decision)` appears in the transcript, and nothing else loads
- the ADR follows the framework's template: Context; Decision with Assumptions, Drivers, Options, Outcome and Rationale; Consequences; Compliance; Notes; Actions; Tags
- it grounds the drivers in the framework's cloud-services guidance and ends with the tracer line:

```text
procedure: cloud-architecture-decision
```

`git status --porcelain` is empty after both prompts. Lesson: a skill costs its front matter until matched, then exactly its body, only in the session that needed it.

---

<!-- _class: dense -->

# 04 Descriptions route skills

What it shows: scenario 03 with two mechanical changes made at setup. The skill directories are renamed `seqf-procedure-1` to `seqf-procedure-8`, and every description is shifted one place along the procedure order; the bodies are untouched. The cloud-architecture description now sits on `seqf-procedure-4`, whose body is the observability procedure.

```sh
cce reset 4 && cd "$(cce path 4)"
head -3 .github/skills/seqf-procedure-4/SKILL.md
grep -l 'procedure: cloud-architecture-decision' .github/skills/*/SKILL.md
copilot --allow-all --model claude-sonnet-5
```

The ADR prompt from scenario 03, unchanged:

```text
Draft an Any Decision Record (ADR) for choosing a managed database service instead of running the database ourselves. Output the ADR only; do not edit any files.
```

---

# 04 What you see

- `/skills` lists eight names with rotated descriptions; Copilot matches the task against the description column only
- `● skill(seqf-procedure-4)` appears, and only that one: the observability body, asked for a database decision record
- a weaker model follows the wrong body and writes about logging, alerting and error budgets; Claude Sonnet 5 noticed the mismatch and rebuilt the ADR from the framework pages instead
- either way you paid for it: 14.69 credits against 8.78 in scenario 03, 200.7k input tokens against 67.9k, `/context` 39k against 32k

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

Topic: the framework's page conventions. Most pages open with a `## Context` section; at the pin, 23 of 48 do and 25 do not. Finding out which means reading every page.

What it shows: an `auditor` agent (`tools: [read, search, execute]`) reads every Markdown file outside `.github/` and `.claude/` in full, notes which lack a `## Context` section, cross-checks with one shell command and replies with only the number and its scope.

- Run A, delegated: `cce reset 6 && cd "$(cce path 6)" && copilot --allow-all --model claude-sonnet-5`
- Run B, direct: the same with `--agent auditor`

```text
How many Markdown pages in this repository are missing a "## Context" section? Exclude the .github directory. Use the auditor agent and give me only the number and its scope.
```

---

<!-- _class: dense -->

# 06 What you see

Answer both ways: 25 of 48 pages. Re-derive: `git ls-files '*.md' | grep -v '^\.github/' | while read -r f; do grep -qx '## Context' "$f" || echo "$f"; done | wc -l`

Measured on Claude Sonnet 5:

| Run | `/context` | `Messages` after | Tokens ↑ | AI credits |
| --- | --- | --- | --- | --- |
| A, delegated | 20k → 21k | 468 | 1.3m | 75.44 |
| B, direct (`--agent auditor`) | 7k → 112k | 104.2k | 472.7k | 55.37 |

- Run A: `/context` after the reply is barely larger than at turn 0; two lines came back
- Run B: `/context` grows by roughly the repository; every later question carries the audit
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
