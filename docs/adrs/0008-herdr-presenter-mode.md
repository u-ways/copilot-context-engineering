# ADR-0008: herdr presenter mode is opt-in

- Status: Accepted
- Date: 2026-09-13
- Revision 2026-09-13: `cce doctor` no longer reports on herdr; the `--herdr` preflight is the only check (ADR-0006).

## Context

Live talks want every scenario open side by side: its guide, its overlay files and a Copilot session, ready to switch between in seconds. herdr, a terminal workspace manager, can build that layout through a JSON command line. Self-serve readers, CI and anyone not running herdr must never be affected: a tool that talks to a multiplexer because it happens to be running inside one is a surprise, not a feature.

## Decision

- Presenter mode runs only when `cce setup --herdr` or `cce teardown --herdr` is given. It is never auto-detected from the environment: `HERDR_ENV` is read solely to refuse when it is not exactly `1`.
- Before any worktree or herdr mutation, `preflight` checks `HERDR_ENV == "1"`, that `herdr` is on `PATH`, and runs `herdr workspace list`; if any planned label already exists the command exits 3 without creating anything. Labels are `cce:demo` and `cce:<slug>`; every label starts with `cce:`.
- The layout is pure data from the manifest: a DEMO workspace (cwd the workspace root; tabs `presenting` running `cce guide presenting | less -R` and `status` running `cce list`) and one workspace per ready scenario (cwd the worktree; tabs `guide`, `overlay` listing the files the baseline commit added, `copilot`, plus the manifest's `[[scenario.tabs]]`, which is how scenario 06 gets `copilot --agent auditor`). Tab commands are shell strings passed verbatim to `herdr pane run`.
- The client speaks the JSON command line only: `workspace create --cwd P --label L --no-focus` (reading `result.workspace.workspace_id`, `result.tab.tab_id`, `result.root_pane.pane_id`), `tab rename`, `tab create --workspace W --cwd P --label L --no-focus`, `pane run`, `workspace focus`, `workspace close`. A failed or non-JSON answer exits 1 naming the subcommand.
- Every created workspace id is appended to `<workspace>/herdr.json` as soon as it exists, so a failure part-way through leaves a record. `cce teardown --herdr` closes exactly the recorded ids and then removes the record; it never closes anything else.
- All herdr calls go through `src/cce/herdr.py`; tests drive it through a fake `herdr` executable on `PATH` that records its arguments and answers with canned JSON.

## Consequences

- A reader who never passes `--herdr` never sees herdr mentioned by the tool, even inside a herdr session.
- Presenters get the layout in one command and remove it in one command, without touching workspaces they created by hand.
- The client is coupled to herdr's JSON shapes; a change there breaks presenter mode only, visible in the recorded-call tests.
- `HERDR_ENV=1` is a hard requirement, checked by the `--herdr` preflight together with `herdr` being on the path; `cce doctor` does not report on herdr.

## Review guidance

- Flag `herdr` references in `src/cce/` outside `src/cce/herdr.py`, `src/cce/cli.py`, `src/cce/workspace.py` and `src/cce/doctor.py`.
- Flag reads of `HERDR_ENV` in `src/cce/` outside `src/cce/herdr.py` and `src/cce/doctor.py`, and any read that enables behaviour instead of refusing when the value is not `1`.
- Require every workspace label built in `src/cce/herdr.py` to start with `cce:`.
- Require `tests/test_herdr.py` to assert the exact recorded call sequence of `apply_layout` and the refusal on a pre-existing `cce:` label before any `workspace create` call.
- Flag any test that invokes `herdr` other than through the fake executable installed by the `shim_bin` fixture.
- Require `tests/test_herdr.py` to assert that `cce setup` without `--herdr` records no herdr call.
