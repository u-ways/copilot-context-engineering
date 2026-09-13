# Scenario 04: descriptions route skills

## What it shows

This scenario is scenario 03 with two mechanical changes made at setup time: the skill directories are renamed `seqf-procedure-1` to `seqf-procedure-8`, and every description is shifted one position along the procedure order, so skill N carries the description of procedure N+1 and skill 8 carries the description of procedure 1. The bodies are untouched. The conversion description therefore sits on `seqf-procedure-7`, whose body is the publishing procedure.

You will inspect the rotation from the shell first, then send the conversion prompt from scenario 03, unchanged, and watch which skill loads.

## Run it

Before you start: the [setup](../PREREQUISITES.md) is done and `cce list` shows scenario 04 as `ready`. Keep a second terminal in the worktree (`cd "$(cce path 4)"`). Scenario 03's run B is the comparison, so have its row to hand.

Record what you see:

| Run | `/context` at turn 0 → after | AI credits (≈ $) | `● skill(...)` line | Last line of the reply |
| --- | --- | --- | --- | --- |
| 1, the conversion prompt | | | | |

### Run 1: the conversion prompt against rotated descriptions

1. **Start** by resetting and, before opening Copilot, reading the rotated descriptions from the shell:

   ```sh
   cce reset 4 && cd "$(cce path 4)"
   ls .github/skills
   head -3 .github/skills/seqf-procedure-7/SKILL.md
   head -3 .github/skills/seqf-procedure-8/SKILL.md
   grep -l 'procedure: convert-page-to-framework-conventions' .github/skills/*/SKILL.md
   grep -l 'procedure: publish-and-open-source-a-repository' .github/skills/*/SKILL.md
   ```

   Expect: `seqf-procedure-7` describes rewriting a Markdown page to the framework's conventions, while the first `grep -l` shows the conversion body actually lives in `seqf-procedure-8`, and the second shows the publishing body lives in `seqf-procedure-7`. Guess which skill will load before you go on.

2. **Start** the session (answer `1. Yes` to the folder-trust question the first time):

   ```sh
   copilot --allow-all --model claude-sonnet-5
   ```

3. **Check**: `/context` at turn 0, and `/skills`, which shows the eight names with the rotated descriptions beside them (Esc to close). Copilot matches the task against the descriptions only.

4. **Send**:

   ```text
   Prepare a conversion plan for tools/aws-fis/jmeter/README.md so that it follows this framework's page conventions. Output the plan only; do not edit any files.
   ```

5. **Observe**: the proof is the line

   ```text
   ● skill(seqf-procedure-7)
   ```

   and it does not depend on the model. Then read what the model does with a body that does not match the description (expectations in the next section), `/context` (compare with turn 0) and `/usage`. `git status --porcelain` prints nothing.

6. **Quit and reset**: `/exit`, then `cce reset 4`.

## What to notice

What must hold on every run: `seqf-procedure-7` loads and nothing else does, and no file changes. What the model does next varies, as described below.

Measured on Claude Sonnet 5:

| Run | `/context` turn 0 → after | `/usage` Tokens ↑ | AI credits (≈ $) | Loaded |
| --- | --- | --- | --- | --- |
| 1, the conversion prompt | 21k → 51k | 665.6k | 30.7 (≈ $0.31) | `seqf-procedure-7` (the publishing body) |
| Scenario 03 run B, for comparison | 21k → 32k | 182.5k | 14.9 (≈ $0.15) | `convert-page-to-framework-conventions` |

The rotation, for the three skills that matter here:

| Skill | Description comes from | Body is |
| --- | --- | --- |
| `seqf-procedure-6` | procedure 7 (publishing) | procedure 6 (secure development) |
| `seqf-procedure-7` | procedure 8 (conversion) | procedure 7 (publishing) |
| `seqf-procedure-8` | procedure 1 (maturity review) | procedure 8 (conversion) |

Re-derive the whole table, one line per skill (description first, then the body's tracer):

```sh
for n in 1 2 3 4 5 6 7 8; do
  printf 'seqf-procedure-%s  ' "$n"
  grep -m1 '^description:' ".github/skills/seqf-procedure-$n/SKILL.md" | cut -c1-72
  printf 'seqf-procedure-%s  ' "$n"
  grep -o 'procedure: [a-z-]*' ".github/skills/seqf-procedure-$n/SKILL.md"
done
```

- What the model does with the wrong body varies. A weaker model follows it and writes about licences, repository hardening, secret scanning and signed commits, ending with `procedure: publish-and-open-source-a-repository`. The measured Claude Sonnet 5 run noticed the mismatch, said so ("returned reference material that doesn't match its own description"), discarded the body and rebuilt the conventions from the exemplar pages, at twice the credits and more than three times the input tokens of scenario 03's run B. Either way the routing was wrong and you paid for it.
- `/context` grew by the publishing body (about 52 KB) and everything the model read to recover, not by the conversion body (about 27 KB). Re-derive: `wc -c .github/skills/seqf-procedure-7/SKILL.md .github/skills/seqf-procedure-8/SKILL.md`.

The lesson: names carry no routing signal. The description is the only thing Copilot has when it decides whether to load a skill, so write it as the trigger condition and keep it truthful about what the body does. A good body behind an unrelated description never loads for the tasks it was written for; a wrong body behind the right description, as here, loads confidently and either answers the wrong question or makes the model pay to work around it.

### Impact in numbers

Rough figures from the measured run against scenario 03's run B, the same prompt with truthful descriptions (percentages are rounded):

- Credits: about 2 times the price (30.7 against 14.9, roughly 106% more) for a plan of similar quality.
- Input tokens sent: about 3.6 times as many (665.6k against 182.5k), spent on loading the wrong body and then rebuilding the conventions from the exemplar pages.
- Context after the reply: about 59% larger (51k against 32k), and the extra is the wrong body plus the recovery reads, all of which every later turn carries.
- Routing accuracy: 0 of 1. The description decided, the name and the body never got a vote.

## Reset

```sh
cce reset 4
```

`cce setup 4 --force` recreates the worktree from scratch if a reset is not enough.
