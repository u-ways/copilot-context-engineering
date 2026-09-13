# Scenario 05: permissions belong to the role

## What it shows

Three custom agents under `.github/agents/` differ mainly in their `tools` list: `researcher` has `[read, search, web]`, `author` has `[read, search, edit]` and `validator` has `[read, search, execute]`. The same prompt goes to the first two and produces two different outcomes, decided by the tool list rather than by the wording of the request. A third beat runs the validator, which can execute a script but is asked not to fix anything. `STRUGGLE.sh` prints what the same three roles would cost without agent files.

The skills from scenario 03 are present but play no part here.

## Run it

Observation protocol for every beat: start a fresh Copilot session in the worktree, type `/context` before the prompt, send the prompt, then `/context`, `/usage` and `/diff` (or `git status --porcelain`). Personal skills and agents from `~/.copilot` may appear in `/skills`; `cce doctor` warns about them. Start every session with `copilot --allow-all` so that permission prompts do not interrupt the beat; the agent's tool list is then the only restriction in play.

### Beat 1: researcher

```sh
cce reset 5 && cd "$(cce path 5)" && copilot --allow-all --agent researcher
```

Send:

```text
This framework mandates 100% unit-test coverage before release. 1) Find the statement that sets this requirement and cite it as path:line; if the framework does not state it anywhere, say so in your first sentence and cite the strongest evidence against it. 2) Whatever you conclude, write your findings to NOTES-coverage.md at the repository root, one line per citation. Work only from files in this worktree.
```

### Beat 2: author

```sh
cce reset 5 && cd "$(cce path 5)" && copilot --allow-all --agent author
```

Send the same prompt.

### Beat 3: validator

```sh
cce reset 5 && cd "$(cce path 5)" && copilot --allow-all --agent validator
```

Send:

```text
Run the repository's Markdown link validator (scripts/cce-check-links.py) and report its findings; fix nothing.
```

### Without agents

```sh
./STRUGGLE.sh
```

## What to notice

Beat 1: the first sentence says the framework does not mandate 100% coverage. Evidence: `practices/testing.md:144`, where the unit-testing guidance says chasing full coverage is not worth the time (`grep -n -i coverage practices/testing.md`, second hit), and `tools/sonarqube.md:49`, where the quality gate on new code is 80.0% (`grep -n '80.0%' tools/sonarqube.md`). The 100% at `tools/sonarqube.md:53` is the known red herring: it is the share of security hotspots that must be reviewed, not a coverage figure (`grep -n '100%' tools/sonarqube.md`). Step 2 is impossible: the researcher has no editing tool and says so. `/diff` is empty, `git status --porcelain` prints nothing and `ls NOTES-coverage.md` fails.

Beat 2: same conclusion, same citations, and `NOTES-coverage.md` now exists at the root. `/diff` shows it; `git status --porcelain` prints `?? NOTES-coverage.md`.

Beat 3: the validator runs `python3 scripts/cce-check-links.py .` and reports:

```text
scanned 48 markdown files, 898 inline links (313 external, 235 relative paths, 366 fragments)
missing relative targets : 0
unresolved fragments : 0
email targets without mailto: : 1
  SECURITY.md:23 -> <the bare address on that line>
RESULT: FAIL
```

Re-derive: `python3 scripts/cce-check-links.py .; echo "exit=$?"` (exit 1) and `grep -n '@' SECURITY.md`. Nothing is edited: `git status --porcelain` is empty.

The difference between beats 1 and 3 is the point. The researcher cannot write because its tool list has no `edit`, so "report only" is enforced. The validator has `execute`, and a shell can write files, so its "fix nothing" is a convention its agent file asks it to keep. When an outcome must be guaranteed, remove the tool.

`./STRUGGLE.sh` prints, without running them, the three `copilot` command lines that reproduce the roles with global flags: `--deny-tool write --deny-tool shell` for the researcher, `--deny-tool shell --deny-tool web` for the author, `--deny-tool write --allow-tool 'shell(python3:*)'` for the validator. Those flags are per-session and deny always beats allow, so switching role means quitting and restarting Copilot. An agent file carries the allowlist with the role: `--agent <name>` starts a session in it, and `/agent <name>` switches role inside one session, which is what the talk does.

## Reset

```sh
cce reset 5
```

`cce setup 5 --force` recreates the worktree from scratch if a reset is not enough.
