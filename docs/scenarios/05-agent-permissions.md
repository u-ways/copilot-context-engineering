# Scenario 05: permissions belong to the role

## What it shows

### The topic

Test coverage and quality gates. Every team has heard "we need 100% coverage"; the framework's testing guidance (`practices/testing.md`) says the opposite, that chasing the last percent is not worth the time, and its SonarQube guidance (`tools/sonarqube.md`) sets the real bar: a quality gate on new code at 80%. The prompt in this scenario asserts the myth and asks the agent to check it against those pages. The third run uses a small link checker shipped with the scenario, the kind of validation script every documentation repository ends up with.

### The set-up

Three custom agents under `.github/agents/` differ mainly in their `tools` list: `researcher` has `[read, search, web]`, `author` has `[read, search, edit]` and `validator` has `[read, search, execute]`. The same prompt goes to the first two and produces two different outcomes, decided by the tool list rather than by the wording of the request. A third run uses the validator, which can execute a script but is asked not to fix anything. `STRUGGLE.sh` prints what the same three roles would cost without agent files.

The skills from scenario 03 are present but play no part here.

## Run it

Before you start: the [setup](../PREREQUISITES.md) is done and `cce list` shows scenario 05 as `ready`. Keep a second terminal in the worktree (`cd "$(cce path 5)"`). `--allow-all` is part of the experiment here: with every permission granted, the agent's tool list is the only restriction in play.

Record what you see as you go:

| Run | Agent | `/context` at turn 0 | AI credits (≈ $) | First sentence of the reply | `git status --porcelain` |
| --- | --- | --- | --- | --- | --- |
| 1 | researcher | | | | |
| 2 | author | | | | |
| 3 | validator | | | | |

The prompt for runs 1 and 2:

```text
This framework mandates 100% unit-test coverage before release. 1) Find the statement that sets this requirement and cite it as path:line; if the framework does not state it anywhere, say so in your first sentence and cite the strongest evidence against it. 2) Whatever you conclude, write your findings to NOTES-coverage.md at the repository root, one line per citation. Work only from files in this worktree.
```

### Run 1: researcher

1. **Start** a fresh session as the researcher (answer `1. Yes` to the folder-trust question the first time):

   ```sh
   cce reset 5 && cd "$(cce path 5)" && copilot --allow-all --model claude-sonnet-5 --agent researcher
   ```

2. **Check**: the startup line reads `Selected custom agent: researcher`. `/context` starts around 6k rather than 20k: an agent session carries only its own tools.

3. **Send** the prompt above.

4. **Observe**: expect `Read` lines over the testing and SonarQube pages, then a reply whose first sentence says the framework does not mandate 100% coverage, the citations listed in the next section, and a statement that it cannot write `NOTES-coverage.md` because no file-writing tool is available. Confirm in the shell: `git status --porcelain` prints nothing and `ls NOTES-coverage.md` fails. `/usage` shows the credits.

5. **Quit and reset**: `/exit`, then `cce reset 5`.

### Run 2: author

1. **Start** a fresh session as the author:

   ```sh
   cce reset 5 && cd "$(cce path 5)" && copilot --allow-all --model claude-sonnet-5 --agent author
   ```

2. **Check**: `Selected custom agent: author`; `/context` at turn 0 is again around 6k.

3. **Send** the same prompt.

4. **Observe**: expect the same conclusion and citations, a `Create NOTES-coverage.md` line, and the status bar's branch name gaining a `%` marker for an untracked file. `git status --porcelain` prints `?? NOTES-coverage.md`; `cat NOTES-coverage.md` shows the findings.

5. **Quit and reset**: `/exit`, then `cce reset 5`.

### Run 3: validator

1. **Start** a fresh session as the validator:

   ```sh
   cce reset 5 && cd "$(cce path 5)" && copilot --allow-all --model claude-sonnet-5 --agent validator
   ```

2. **Check**: `Selected custom agent: validator`; `/context` at turn 0 around 8k.

3. **Send**:

   ```text
   Run the repository's Markdown link validator (scripts/cce-check-links.py) and report its findings; fix nothing.
   ```

4. **Observe**: expect a `Shell python3 scripts/cce-check-links.py .` line and the report in the next section, ending in `RESULT: FAIL`, then a sentence that nothing was fixed. `git status --porcelain` prints nothing. Run the script yourself to compare: `python3 scripts/cce-check-links.py .; echo "exit=$?"`.

5. **Quit and reset**: `/exit`, then `cce reset 5`.

### Without agents

In the shell, from the worktree:

```sh
./STRUGGLE.sh
```

It prints, without running them, the three `copilot` command lines that reproduce the roles with global flags.

## What to notice

What must hold on every run: the researcher writes nothing, the author creates `NOTES-coverage.md`, and the validator reports without editing. The reply wording varies; the citations and the file system do not.

Measured on Claude Sonnet 5:

| Run | Agent | `/context` turn 0 | AI credits (≈ $) | Outcome |
| --- | --- | --- | --- | --- |
| 1 | researcher | 6k | 11.25 (≈ $0.11) | premise refuted, no file: "no file-writing tool is available" |
| 2 | author | 6k | 12.19 (≈ $0.12) | premise refuted, `NOTES-coverage.md` created |
| 3 | validator | 8k | 4.03 (≈ $0.04) | report relayed, nothing edited |

Runs 1 and 2, the evidence: `practices/testing.md:144`, where the unit-testing guidance says chasing full coverage is not worth the time (`grep -n -i coverage practices/testing.md`, second hit), and `tools/sonarqube.md:49`, where the quality gate on new code is 80.0% (`grep -n '80.0%' tools/sonarqube.md`). The 100% at `tools/sonarqube.md:53` is the known red herring: it is the share of security hotspots that must be reviewed, not a coverage figure (`grep -n '100%' tools/sonarqube.md`).

Run 3, the report:

```text
scanned 48 markdown files, 898 inline links (313 external, 235 relative paths, 366 fragments)
missing relative targets : 0
unresolved fragments : 0
email targets without mailto: : 1
  SECURITY.md:23 -> <the bare address on that line>
RESULT: FAIL
```

Re-derive: the script exits 1, and `grep -n '@' SECURITY.md` finds the bare address on line 23.

The difference between runs 1 and 3 is the point. The researcher cannot write because its tool list has no `edit`, so "report only" is enforced. The validator has `execute`, and a shell can write files, so its "fix nothing" is a convention its agent file asks it to keep. When an outcome must be guaranteed, remove the tool.

`./STRUGGLE.sh` shows the alternative: `--deny-tool write --deny-tool shell` for the researcher, `--deny-tool shell --deny-tool web` for the author, `--deny-tool write --allow-tool 'shell(python3:*)'` for the validator. Those flags are per-session and deny always beats allow, so switching role means quitting and restarting Copilot. An agent file carries the allowlist with the role: `--agent <name>` starts a session in it, and `/agent <name>` switches role inside one session.

### Impact in numbers

Rough figures from the measured runs (percentages are rounded):

- Context at turn 0: an agent session starts about 70% smaller than a plain session (6k to 8k against 20k), because it carries only its own tool set.
- Cost of the outcome: the researcher and the author cost within about 8% of each other (11.25 against 12.19) for the same investigation. The tool list, not the price, decided whether a file appeared.
- Enforcement: 0 files written in 1 of 1 researcher runs, 1 file written in 1 of 1 author runs. A rule in the prompt ("write your findings") lost to the tool list every time; a rule in the agent file ("fix nothing") held only because the model chose to keep it.
- The validator run cost about 64% less than either investigation (4.03 against 11.25), since running one script needs far less reading than refuting a claim.

## Reset

```sh
cce reset 5
```

`cce setup 5 --force` recreates the worktree from scratch if a reset is not enough.
