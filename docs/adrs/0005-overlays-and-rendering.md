# ADR-0005: Overlays and rendering

- Status: Accepted
- Date: 2026-09-13
- Revision 2026-09-13: `plan_scenario` takes the dialect and validates the translated destinations, so a Claude-dialect plan is checked against upstream-tracked paths such as `CLAUDE.md`.

## Context

Every scenario shows the same eight procedures delivered through a different context mechanism: inlined into repository instructions (S02), packaged as Agent Skills (S03, S04, S05), or not delivered at all (S01, S06). The comparison only means something if the procedure text is byte-identical across scenarios and only the delivery differs. Hand-maintained copies per scenario would drift on the first edit.

Scenarios also need pieces of the upstream repository inlined at render time. S01 shows instructions that describe repository state as of a date and have since gone stale; regenerating that text from git history is more honest than storing a snapshot. Nothing from upstream may be committed to this repository, because the upstream carries no licence: it is fetched at runtime and never redistributed (the pinned-ref decision, ADR-0003, arrives with the workspace engine).

Overlay files are package data under `src/cce/overlays/` and ship inside the wheel. Dot-prefixed path segments are a trap there: packaging tools, ignore rules and directory listings treat hidden files inconsistently, and the invariant that every overlay file is tracked by git is cheaper to check when nothing is hidden.

Copilot CLI and Claude Code read the same kinds of content from different layouts (`.github/copilot-instructions.md` versus `CLAUDE.md`, `.github/skills` versus `.claude/skills`, `.github/agents/<n>.agent.md` versus `.claude/agents/<n>.md`) and name their tools differently. A translator over the rendered plan keeps one source of truth and lets the LLM verification tier (ADR-0010) run the same scenarios under either runtime.

Some overlays ship helper scripts into the worktree (S05 ships the Markdown link validator that its validator agent runs). Those scripts execute with whatever `python3` the user has, not with the interpreter `cce` was installed into.

## Decision

- Overlays are package data under `src/cce/overlays/`: `scenarios.toml`, `_shared/procedures/NN-<name>.md` (one source file per procedure, eight in total), `_shared/agents/<name>.agent.md`, `_shared/scripts/`, and one directory per scenario slug. No path segment under `src/cce/overlays/` starts with a dot; an overlay directory named `github/` renders to `.github/` in the worktree.
- `scenarios.toml` is the only place scenarios are declared. `[source]` holds `url`, `ref` (a 40-hexadecimal-digit commit sha, the only place the pin lives under `src/`) and `procedures` (the directory `_shared/procedures`, read in `NN-` order). Each ordered `[[scenario]]` entry holds `id`, `slug`, `title`, an optional `overlay` directory, an optional `[scenario.skills]` table (its presence derives one skill per procedure; `rename = "seqf-procedure-{n}"` renames the derived skills; `rotate_descriptions = N` shifts each description N positions along the procedure order), `agents` (names under `_shared/agents/`), `files` (entries with `src`, `dest` and `executable`, passed through the same renderer as overlay files), `executable` (overlay paths to mark executable) and `[[scenario.tabs]]` entries (`label`, `command` as a shell string). Python never branches on a scenario id or slug.
- Skills are derived, never hand-written: S02 inlines every procedure body into its instructions through the `procedures` directive; S03, S04 and S05 derive `.github/skills/<name>/SKILL.md` from the same sources, S04 with renamed skills and rotated descriptions; S06 declares no skills. No `SKILL.md` file exists under `src/`.
- Three directives, each a whole line. Any line starting `<!-- cce:` that does not match the grammar is a `RenderError` naming the file and line.

  ```text
  <!-- cce:include PATH [asof=YYYY-MM-DD] -->   PATH is worktree-relative POSIX, no leading "/", no "..";
                                                content inserted verbatim and never re-scanned;
                                                asof= reads PATH at the last commit touching it on or
                                                before the date, searching backwards from the pin
  <!-- cce:procedure NAME -->                   body of _shared/procedures/NN-NAME.md, rendered
                                                recursively, depth at most 4
  <!-- cce:procedures [heading=N] -->           every procedure in order: "#" * N + " " + title,
                                                a blank line, then the body
  ```

- Includes are single-pass: text inserted by `cce:include` is never scanned for directives, so an upstream file that happens to contain `<!-- cce:` is inert. Dated includes (`asof=`) exist for S01 and read history through the reader, never through a stored snapshot.
- Rendering is pure. Its inputs are the overlay files, the procedure sources, the agents, the `files` entries and an injected `UpstreamReader` exposing `read(path)`, `read_asof(path, date)` and `tracked_paths()`; its output is `list[PlannedFile(dest, bytes, executable)]`. The workspace engine passes a git-backed reader over the base clone; tests pass the same reader class over the synthetic upstream. `render.py` runs no git commands and opens no network connections.
- Front matter is our own small grammar, parsed without a YAML library: `key: scalar`, `key: "quoted scalar"` and `key: [a, b]`; `tools` also accepts a comma-separated string. Agent front matter must carry `name`, `description` and `tools` (a subset of the Copilot tool set exported by `dialect.py`), plus an optional `model`. Emitted `SKILL.md` and agent front matter always quotes `description`, because every routing description contains `: `.
- After rendering, `residual_directives()` must be empty, duplicate destinations are an error, and a destination that upstream already tracks is an error.
- The plan's digest is the sha256 over the sorted `(dest, mode, bytes)` triples; the workspace stores it in state to detect drift.
- `dialect.py` translates a plan for Claude Code: `.github/copilot-instructions*.md` becomes `CLAUDE*.md`; `.github/skills/<n>/SKILL.md` becomes `.claude/skills/<n>/SKILL.md` unchanged; `.github/agents/<n>.agent.md` becomes `.claude/agents/<n>.md` with `tools` rewritten through the alias table (`read` to `Read`; `search` to `Grep`, `Glob`; `edit` to `Edit`, `Write`; `execute` to `Bash`; `web` to `WebFetch`, `WebSearch`; `agent` to `Agent`), `model` dropped and an unknown alias an error; everything else is copied verbatim. The alias table lives only in `dialect.py`. `cce setup --dialect copilot|claude` (default `copilot`, recorded in workspace state and shown by `cce list`) lands with the workspace engine.
- Scripts under `src/cce/overlays/_shared/scripts/` are shipped tools: standard library only, compatible with Python 3.9, importing nothing from `cce`, with their own stdout contract (ADR-0006).
- No Markdown or YAML library is added for any of this; the grammar is small enough to parse by hand.

## Consequences

- One edit to a procedure changes every scenario that delivers it, and byte-equality between S03 and S05 skills, and between S02's inlined bodies and their sources, is a plain test.
- Rendering runs offline against the synthetic upstream in the default test tier; the e2e tier repeats it against the real pin.
- S01 is reproducible: its stale instructions are regenerated from upstream history at every setup rather than stored here, so no upstream text enters the repository.
- A mistyped directive fails the render with a file and line instead of leaking an HTML comment into a worktree.
- Adding or reordering a scenario is a manifest and overlay change with no Python involved.
- The hand-parsed front matter grammar is deliberately small; agents that need nested YAML would need a `- Revision` bullet here.
- The dialect translator maps layout and tool names and nothing else; runtime-specific features beyond that are out of scope.
- Shipped scripts cannot use `typer`, `structlog` or Python features newer than 3.9, and are tested by running them as subprocesses.

## Review guidance

- Flag any path segment starting with `.` under `src/cce/overlays/`.
- Flag any file named `SKILL.md` anywhere under `src/`.
- Flag any `<!-- cce:` directive verb other than `include`, `procedure` and `procedures` in `src/cce/overlays/` or `src/cce/render.py` when this ADR carries no `- Revision` bullet naming the new verb.
- Flag any comparison against a scenario id or slug literal (for example `== "05"` or `"05-agent-permissions"`) in `src/cce/*.py`.
- Flag `pyyaml`, `PyYAML`, `ruamel`, `markdown`, `markdown-it-py` or `mistune` in `pyproject.toml`.
- Flag `import subprocess`, `import urllib` or `import http` in `src/cce/render.py`.
- Flag any import of `cce`, `typer` or `structlog` in `src/cce/overlays/_shared/scripts/`.
- Require `src/cce/overlays/scenarios.toml` to declare `url`, `ref` and `procedures` under `[source]` and `id`, `slug` and `title` on every `[[scenario]]`.
- Require the Claude tool names `Grep`, `Glob`, `Bash`, `WebFetch` and `WebSearch` to appear under `src/cce/` only in `src/cce/dialect.py`.
- Require `tests/test_render.py` to assert that no rendered file contains `<!-- cce:` and that a `<!-- cce:include` line inside included upstream text is left verbatim.
- Require `tests/test_render.py` to assert that every rendered `SKILL.md` and agent front matter has a quoted `description`.
