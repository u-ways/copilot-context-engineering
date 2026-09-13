# Scenario 04: descriptions route skills

## What it shows

This scenario is scenario 03 with two mechanical changes made at setup time: the skill directories are renamed `seqf-procedure-1` to `seqf-procedure-8`, and every description is shifted one position along the procedure order, so skill N carries the description of procedure N+1 and skill 8 carries the description of procedure 1. The bodies are untouched. The conversion description therefore sits on `seqf-procedure-7`, whose body is the publishing procedure.

The conversion prompt from scenario 03 is sent again, unchanged.

## Run it

Observation protocol: start a fresh Copilot session in the worktree, type `/context` before the prompt, send the prompt, then `/context`, `/usage`, `/skills` and `/diff` (or `git status --porcelain`). Personal skills and agents from `~/.copilot` may appear in `/skills`; `cce doctor` warns about them.

```sh
cce reset 4 && cd "$(cce path 4)"
```

Before starting Copilot, read the rotated descriptions from the shell:

```sh
ls .github/skills
head -3 .github/skills/seqf-procedure-7/SKILL.md
head -3 .github/skills/seqf-procedure-8/SKILL.md
grep -l 'procedure: convert-page-to-framework-conventions' .github/skills/*/SKILL.md
grep -l 'procedure: publish-and-open-source-a-repository' .github/skills/*/SKILL.md
```

Then start the session and send the prompt:

```sh
copilot
```

```text
Prepare a conversion plan for tools/aws-fis/jmeter/README.md so that it follows this framework's page conventions. Output the plan only; do not edit any files.
```

## What to notice

The rotation, for the three skills that matter here:

| Skill | Description comes from | Body is |
| --- | --- | --- |
| `seqf-procedure-6` | procedure 7 (publishing) | procedure 6 (secure development) |
| `seqf-procedure-7` | procedure 8 (conversion) | procedure 7 (publishing) |
| `seqf-procedure-8` | procedure 1 (maturity review) | procedure 8 (conversion) |

Re-derive the whole table, one line per skill (description first, then the body's tracer; a model may omit the tracer in its reply or remark that description and body disagree, and `/skills` remains the proof):

```sh
for n in 1 2 3 4 5 6 7 8; do
  printf 'seqf-procedure-%s  ' "$n"
  grep -m1 '^description:' ".github/skills/seqf-procedure-$n/SKILL.md" | cut -c1-72
  printf 'seqf-procedure-%s  ' "$n"
  grep -o 'procedure: [a-z-]*' ".github/skills/seqf-procedure-$n/SKILL.md"
done
```

- `head -3 .github/skills/seqf-procedure-7/SKILL.md` shows the description about rewriting a Markdown page to the framework's conventions; the first `grep -l` shows the conversion body actually lives in `seqf-procedure-8`, whose description is about engineering maturity; the second `grep -l` shows the publishing body is in `seqf-procedure-7`.
- `/skills` in Copilot shows the same eight names with the same rotated descriptions: name on the left, description on the right. Copilot matches the task against the right-hand column only.
- After the prompt, `/skills` shows `seqf-procedure-7` loaded, and only that one. This is the proof, and it does not depend on the model.
- The reply usually ends with `procedure: publish-and-open-source-a-repository`, the publishing tracer. The plan text varies with the model: licences, repository hardening, secret scanning and signed commits if it followed the wrong body, or a competent conversion plan about H1s, tables of contents and markdownlint if it noticed the mismatch and answered from the page itself.
- `/context` grew by the publishing body (about 52 KB), not by the conversion body (about 27 KB). Re-derive: `wc -c .github/skills/seqf-procedure-7/SKILL.md .github/skills/seqf-procedure-8/SKILL.md`.
- `git status --porcelain` is empty.

The lesson: names carry no routing signal. The description is the only thing Copilot has when it decides whether to load a skill, so write it as the trigger condition and keep it truthful about what the body does. A good body behind an unrelated description never loads for the tasks it was written for; a wrong body behind the right description, as here, is worse, because it loads confidently and answers the wrong question.

Compare with scenario 03, where the same prompt loaded `convert-page-to-framework-conventions` and the reply ended with `procedure: convert-page-to-framework-conventions`.

## Reset

```sh
cce reset 4
```

`cce setup 4 --force` recreates the worktree from scratch if a reset is not enough.
