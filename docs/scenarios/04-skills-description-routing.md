# Scenario 04: descriptions route skills

## What it shows

### The topic

The same procedures as scenario 03 and the same ADR task, so the topic is how Copilot chooses a skill: a skill has a name, a description and a body, and the description is the only one of the three that the router reads. Everything else about the framework stays as it was in scenario 03.

### The set-up

This scenario is scenario 03 with two mechanical changes made at setup time: the skill directories are renamed `seqf-procedure-1` to `seqf-procedure-8`, and every description is shifted one position along the procedure order, so skill N carries the description of procedure N+1 and skill 8 carries the description of procedure 1. The bodies are untouched. The cloud-architecture description therefore sits on `seqf-procedure-4`, whose body is the observability procedure.

You will inspect the rotation from the shell first, then send the ADR prompt from scenario 03, unchanged, and watch which skill loads.

## Run it

Before you start: the [setup](../PREREQUISITES.md) is done and `cce list` shows scenario 04 as `ready`. Keep a second terminal in the worktree (`cd "$(cce path 4)"`). Scenario 03's run B is the comparison, so have its row to hand.

Record what you see:

| Run | `/context` at turn 0 → after | AI credits (≈ $) | `● skill(...)` line | Last line of the reply |
| --- | --- | --- | --- | --- |
| 1, the ADR prompt | | | | |

### Run 1: the ADR prompt against rotated descriptions

1. **Start** by resetting and, before opening Copilot, reading the rotated descriptions from the shell:

   ```sh
   cce reset 4 && cd "$(cce path 4)"
   ls .github/skills
   head -3 .github/skills/seqf-procedure-4/SKILL.md
   head -3 .github/skills/seqf-procedure-5/SKILL.md
   grep -l 'procedure: cloud-architecture-decision' .github/skills/*/SKILL.md
   grep -l 'procedure: observability-and-reliability' .github/skills/*/SKILL.md
   ```

   Expect: `seqf-procedure-4` describes choosing and recording a cloud architecture, while the first `grep -l` shows the cloud-architecture body actually lives in `seqf-procedure-5`, and the second shows the observability body lives in `seqf-procedure-4`. Guess which skill will load before you go on.

2. **Start** the session (answer `1. Yes` to the folder-trust question the first time):

   ```sh
   copilot --allow-all --model claude-sonnet-5
   ```

3. **Check**: `/context` at turn 0, and `/skills`, which shows the eight names with the rotated descriptions beside them (Esc to close). Copilot matches the task against the descriptions only.

4. **Send**:

   ```text
   Draft an Any Decision Record (ADR) for choosing a managed database service instead of running the database ourselves. Output the ADR only; do not edit any files.
   ```

5. **Observe**: the proof is the line

   ```text
   ● skill(seqf-procedure-4)
   ```

   and it does not depend on the model. Then read what the model does with a body about logging, tracing and SLOs when it was asked for a database decision (expectations in the next section), `/context` (compare with turn 0) and `/usage`. `git status --porcelain` prints nothing.

6. **Quit and reset**: `/exit`, then `cce reset 4`.

## What to notice

What must hold on every run: `seqf-procedure-4` loads and nothing else does, and no file changes. What the model does next varies, as described below.

Measured on Claude Sonnet 5:

| Run | `/context` turn 0 → after | `/usage` Tokens ↑ | AI credits (≈ $) | Loaded |
| --- | --- | --- | --- | --- |
| 1, the ADR prompt | 21k → 39k | 200.7k | 14.69 (≈ $0.15) | `seqf-procedure-4` (the observability body) |
| Scenario 03 run B, for comparison | 21k → 32k | 67.9k | 8.78 (≈ $0.09) | `cloud-architecture-decision` |

The rotation, for the three skills that matter here:

| Skill | Description comes from | Body is |
| --- | --- | --- |
| `seqf-procedure-3` | procedure 4 (observability) | procedure 3 (test strategy) |
| `seqf-procedure-4` | procedure 5 (cloud architecture) | procedure 4 (observability) |
| `seqf-procedure-5` | procedure 6 (secure development) | procedure 5 (cloud architecture) |

Re-derive the whole table, one line per skill (description first, then the body's tracer):

```sh
for n in 1 2 3 4 5 6 7 8; do
  printf 'seqf-procedure-%s  ' "$n"
  grep -m1 '^description:' ".github/skills/seqf-procedure-$n/SKILL.md" | cut -c1-72
  printf 'seqf-procedure-%s  ' "$n"
  grep -o 'procedure: [a-z-]*' ".github/skills/seqf-procedure-$n/SKILL.md"
done
```

- What the model does with the wrong body varies. A weaker model follows it and writes about logging, alerting and error budgets, ending with `procedure: observability-and-reliability`. The measured Claude Sonnet 5 run loaded `seqf-procedure-4` (Copilot's session log records the call), found nothing about decision records in the observability body, and built a competent ADR from the framework's cloud-services and outsourcing pages instead, at about 1.7 times the credits and 3.0 times the input tokens of scenario 03's run B. Either way the routing was wrong and you paid for it.
- `/context` grew by the observability body (about 34 KB) and whatever the model read to recover, not by the cloud-architecture body (about 35 KB). Re-derive: `wc -c .github/skills/seqf-procedure-4/SKILL.md .github/skills/seqf-procedure-5/SKILL.md`.

The lesson: names carry no routing signal. The description is the only thing Copilot has when it decides whether to load a skill, so write it as the trigger condition and keep it truthful about what the body does. A good body behind an unrelated description never loads for the tasks it was written for; a wrong body behind the right description, as here, loads confidently and either answers the wrong question or makes the model pay to work around it.

### Impact in numbers

Rough figures from the measured run against scenario 03's run B, the same prompt with truthful descriptions (percentages are rounded):

- Credits: 1.7x the price (14.69 against 8.78) for the same request.
- Input tokens sent: 3.0x as many (200.7k against 67.9k).
- Context after the reply: 22% larger (39k against 32k), and every later turn carries the extra.
- Routing accuracy: 0 of 1. The description decided; the name and the body never got a vote.

## Reset

```sh
cce reset 4
```

`cce setup 4 --force` recreates the worktree from scratch if a reset is not enough.
