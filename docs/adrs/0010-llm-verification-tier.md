# ADR-0010: LLM verification tier and the Claude dialect

- Status: Accepted
- Date: 2026-09-13
- Revision 2026-09-13: accepted when the tier landed (`tests/llm/`, `just llm`, `llm-tests.yml`, `[[scenario.checks]]` and `[[compare]]` in the manifest).
- Revision 2026-09-13: `RunResult` also carries `main_input_tokens` and `subagent_input_tokens` (Copilot from the usage file's `agentMetrics`; Claude from top-level versus subagent `assistant` events); scenario 06's `[[compare]]` entries assert on them, and a compare entry may set `right_metric` to compare two different metrics. The isolation bullet is corrected to match the code: `CLAUDE_CONFIG_DIR` whenever `CLAUDE_CODE_OAUTH_TOKEN` is set, `COPILOT_HOME` only when `COPILOT_GITHUB_TOKEN` is set and `CCE_LLM_ISOLATE=1`, both under `.cce-artifacts/transcripts/<runtime>/`.

## Context

The default and e2e test tiers prove that scenarios render, that worktrees match the pinned upstream and that the CLI keeps its contract. They cannot prove what the guides actually claim: that a skill loads on the matching prompt and not otherwise, that a read-only agent writes nothing, that delegation keeps the parent's context small. Verifying those claims needs a real coding agent run, which is slow, non-deterministic, paid, and produces transcripts that may quote upstream prose.

Two runtimes are in scope. Copilot CLI is the subject of the playground and runs locally for the owner. Claude Code is available in CI through the `CLAUDE_CODE_OAUTH_TOKEN` secret that the `adr-review` workflow already uses, so it is the runtime that can exercise the scenarios on a schedule. Claude Code reads a different layout and different tool names; the minimal translator in `dialect.py` (ADR-0005) closes that gap so one set of overlays serves both.

Agent frameworks such as pydantic-ai were considered for the runners and rejected: they add a runtime dependency and an abstraction over two command-line tools that are already scriptable, and whose JSON output is exactly the thing under test.

## Decision

- The LLM tier is opt-in: tests carry the pytest marker `llm`, `addopts` excludes them with `-m "not e2e and not llm"`, and `just llm copilot|claude` is the only way to run them. `ci.yml` never runs them and never references the tier's environment.
- A workflow `llm-tests.yml` runs the tier with the Claude runner on `workflow_dispatch`, a weekly cron and the pull-request label `llm-tests`. It is not a required check.
- `tests/llm/runners.py` defines `AgentRunner` with two implementations that both normalise to `RunResult(text, skills_loaded, tools_used, input_tokens, files_changed, transcript_path)`:
  - `CopilotRunner` spawns `copilot -p <prompt> --allow-all -C <worktree> -s --output-format json --usage-output-file <tmp>` plus optional `--agent`, `--model` and `--no-custom-instructions`; `skills_loaded` comes from `tool.execution_start` events whose `toolName` is `skill`; `input_tokens` is `lastCallInputTokens` from the usage file.
  - `ClaudeRunner` spawns `claude -p <prompt> --output-format stream-json --verbose --permission-mode bypassPermissions --setting-sources project` plus optional `--agent` and `--model`, inside a worktree set up with `--dialect claude`; `skills_loaded` comes from top-level `assistant` events' `tool_use` blocks named `Skill`, ignoring events that carry `parent_tool_use_id`; `input_tokens` is the last top-level assistant event's `message.usage` summed over `input_tokens`, `cache_creation_input_tokens` and `cache_read_input_tokens`, never `result.usage`, which aggregates subagent work.
- Runs are isolated from personal configuration: `CLAUDE_CONFIG_DIR=.cce-artifacts/transcripts/claude/home-claude` whenever `CLAUDE_CODE_OAUTH_TOKEN` is set; `COPILOT_HOME=.cce-artifacts/transcripts/copilot/home-copilot` only when `COPILOT_GITHUB_TOKEN` is set and `CCE_LLM_ISOLATE=1`. `.cce-artifacts/` is gitignored.
- Assertions come from `[[scenario.checks]]` in `scenarios.toml` (`name`, `prompt`, optional `agent`, `contains` and `not_contains` regexes, `skills_loaded`, `files_changed_max`, and `[[compare]]` entries with `metric`, `left`, `right` and `ratio`). Worktrees are reset before every check. No Python branches on a scenario.
- Transcripts stay in `.cce-artifacts/` and are never committed. CI uploads only the structural `RunResult` JSON, never transcript text.
- The Claude dialect is the minimal translator specified in ADR-0005: layout mapping plus the tool-alias table, with every alias literal in `src/cce/dialect.py` and nothing Claude-specific elsewhere under `src/cce/`.
- The verified flag sets are the ones listed above for `copilot` (`-p`, `--allow-all`, `-C`, `--agent`, `--model`, `--no-custom-instructions`, `-s`, `--output-format`, `--usage-output-file`, `--context`) and `claude` (`-p`, `--output-format`, `--verbose`, `--permission-mode`, `--setting-sources`, `--agent`, `--model`). Using another flag needs a `- Revision` bullet here.
- No pydantic, pydantic-ai or LLM SDK is added to the project's dependencies.

## Consequences

- The default tier stays fast and offline; agent behaviour is verified on demand and on a schedule, not on every push.
- Both runtimes produce the same `RunResult`, so a scenario check is written once in the manifest and judged the same way under Copilot and Claude.
- The token metric is the main thread's final call context, which is what the context-cost scenarios (S02, S06) claim to change; subagent usage is deliberately excluded from it and reported separately as `subagent_input_tokens`.
- Transcript text, which may contain upstream prose, never leaves the runner's machine or the CI job.
- Runner code is coupled to the two CLIs' output formats; a CLI release that changes them breaks the tier, which is visible on the weekly run and fixed with a `- Revision` bullet.

## Review guidance

- Flag any test that spawns `copilot` or `claude` (through `subprocess` or a runner) outside `tests/llm/` or without the `llm` marker.
- Require `[tool.pytest.ini_options].addopts` in `pyproject.toml` to contain `not e2e and not llm`.
- Flag `.github/workflows/ci.yml` referencing `just llm`, `-m llm`, `COPILOT_HOME` or `CLAUDE_CONFIG_DIR`.
- Flag `pydantic`, `pydantic-ai`, `anthropic`, `openai`, `google-genai` or `langchain` in `pyproject.toml`.
- Flag any `copilot` flag in `tests/llm/` outside `-p`, `--allow-all`, `-C`, `--agent`, `--model`, `--no-custom-instructions`, `-s`, `--output-format`, `--usage-output-file` and `--context`, and any `claude` flag outside `-p`, `--output-format`, `--verbose`, `--permission-mode`, `--setting-sources`, `--agent` and `--model`, when this ADR carries no `- Revision` bullet naming the flag.
- Require `.gitignore` to contain `.cce-artifacts/`.
- Require the tool-alias table (the mapping from `read`, `search`, `edit`, `execute`, `web` and `agent` to Claude tool names) to be defined in `src/cce/dialect.py`, and the Claude tool names `Grep`, `Glob`, `Bash`, `WebFetch` and `WebSearch` to appear under `src/cce/` only in that file.
- Flag any `upload-artifact` step in `.github/workflows/` whose `path` includes a transcript file (anything under `.cce-artifacts/` other than the structural result JSON).
