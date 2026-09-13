# Scenario 04: descriptions route skills

## What it shows

This scenario is scenario 03 with two mechanical changes made at setup time: the skill directories are renamed `seqf-procedure-1` to `seqf-procedure-8`, and every description is shifted one position along the procedure order, so skill N carries the description of procedure N+1 and skill 8 carries the description of procedure 1. The bodies are untouched. The conversion description therefore sits on `seqf-procedure-7`, whose body is the publishing procedure.

You will inspect the rotation from the shell first, then send the conversion prompt from scenario 03, unchanged, and watch which skill loads.

## Run it

Before you start: the [setup](../PREREQUISITES.md) is done and `cce list` shows scenario 04 as `ready`. Keep a second terminal in the worktree (`cd "$(cce path 4)"`). Scenario 03's run B is the comparison, so have its row to hand.

Record what you see:

| Run | `/context` at turn 0 | `/context` after the reply | Skill loaded (`/skills`) | Tracer line in the reply |
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

2. **Start** the session:

   ```sh
   copilot
   ```

3. **Check**: `/context` at turn 0, and `/skills`, which shows the same eight names with the rotated descriptions on the right. Copilot matches the task against that right-hand column only.

4. **Send**:

   ```text
   Prepare a conversion plan for tools/aws-fis/jmeter/README.md so that it follows this framework's page conventions. Output the plan only; do not edit any files.
   ```

5. **Observe**: `/skills` shows `seqf-procedure-7` loaded, and only that one. That is the proof, and it does not depend on the model. Then read the reply's last line and its content (expectations in the next section), `/context` (compare with turn 0), `/usage` and `/diff`, which is empty.

6. **Quit and reset**: `/exit`, then `cce reset 4`.

## What to notice

What must hold on every run: `seqf-procedure-7` loads and nothing else does, and no file changes. The reply's content varies with the model, as described below.

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

- The reply usually ends with `procedure: publish-and-open-source-a-repository`, the publishing tracer. The plan text varies with the model: licences, repository hardening, secret scanning and signed commits if it followed the wrong body, or a competent conversion plan about H1s, tables of contents and markdownlint if it noticed the mismatch and answered from the page itself. A model may also omit the tracer or remark that description and body disagree; `/skills` remains the proof.
- `/context` grew by the publishing body (about 52 KB), not by the conversion body (about 27 KB). Re-derive: `wc -c .github/skills/seqf-procedure-7/SKILL.md .github/skills/seqf-procedure-8/SKILL.md`.
- Compare with scenario 03's run B: the same prompt loaded `convert-page-to-framework-conventions` there and the reply ended with `procedure: convert-page-to-framework-conventions`.

The lesson: names carry no routing signal. The description is the only thing Copilot has when it decides whether to load a skill, so write it as the trigger condition and keep it truthful about what the body does. A good body behind an unrelated description never loads for the tasks it was written for; a wrong body behind the right description, as here, is worse, because it loads confidently and answers the wrong question.

## Reset

```sh
cce reset 4
```

`cce setup 4 --force` recreates the worktree from scratch if a reset is not enough.
