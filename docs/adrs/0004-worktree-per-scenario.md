# ADR-0004: One git worktree per scenario with a resettable baseline

- Status: Accepted
- Date: 2026-09-13
- Revision 2026-09-13: `setup` refuses a directory that already holds files cce did not create, before writing the marker or the lock; an unreadable or foreign-schema `state.json` is a refused precondition (exit 3, remedy `cce teardown --force`, which is the one command that tolerates it), so `cce list` can exit 3 in that single case; teardown removes the tree while the lock is still held; the workspace root is resolved once so every printed path agrees.
- Revision 2026-09-13: the `cce doctor` bullet in Decision was not implemented as written. Workspace path, status and overlay drift are reported by `cce list` and `cce path`; `cce doctor` checks the machine and renders every overlay against placeholder text (ADR-0006).

## Context

A scenario is only useful if a reader can break it and put it back. Every guide ends with a reset step, and a presenter running six scenarios back to back needs each one restored to a known state between runs without re-cloning anything. Presenters also need all six open side by side, each with its own session, so scenarios cannot share a checkout.

The overlay (the customisation files rendered by ADR-0005) has to be part of the baseline rather than loose files on top of it. If it were uncommitted, `git status` in the worktree would show the overlay itself as noise, a reset would have to re-render, and the question "has the reader changed anything?" would need a bespoke comparison. Committing the overlay makes reset one git command and lets status be derived from git alone.

The workspace lives outside the repository (`--workspace`, then `CCE_WORKSPACE`, then `$XDG_DATA_HOME/cce`, then `~/.local/share/cce`) and is created, modified and deleted by a tool that never prompts (ADR-0006). Deleting a directory tree the user pointed at by mistake must be impossible, and two invocations must not race on the same workspace.

## Decision

Layout:

```text
<ws>/.cce-workspace     marker; rmtree is refused without it
<ws>/.cce.lock          fcntl.flock held by setup, reset and teardown; contention exits 3
<ws>/state.json         {schema, source_url, source_ref, dialect, scenarios: {slug: {baseline, digest}}};
                        written to a temporary file, then os.replace
<ws>/base/              the shared --no-checkout clone (ADR-0003)
<ws>/scenarios/<slug>/  worktree on branch cce/<slug>; staged at scenarios/.tmp-<slug>/ during creation
<ws>/herdr.json         presenter ids recorded by --herdr (ADR-0008)
```

- Every git call passes `-c user.name=cce -c user.email=cce@localhost -c commit.gpgsign=false -c core.hooksPath=/dev/null` and runs with `GIT_TERMINAL_PROMPT=0` and `LC_ALL=C` in the environment. The user's global config is not disabled, so proxies and credential helpers keep working; the test fixture supplies the hermetic environment.
- Exactly three statuses. `missing`: the directory is absent, the slug is not in state, only the staging directory exists, or `refs/cce/baseline/<slug>` is absent; a `detail` string says which. `ready`: HEAD equals `refs/cce/baseline/<slug>` and `git status --porcelain` is empty. `modified`: anything else, with the first changed paths in `detail`. Status is always computed from git against the baseline ref, never from state alone.
- `setup` runs in this order: validate the manifest; resolve ids (none means all); take the lock; ensure the base clone; render every requested scenario in memory before any worktree is written; then per scenario: `missing` creates; `ready` with an equal digest and dialect skips with zero git writes; `ready` with a different digest or dialect (after `cce update`) re-renders without `--force`; `modified` without `--force` is collected and refused with exit 3 once the other scenarios have been processed; with `--force` the worktree is removed and recreated. Stale `scenarios/.tmp-<slug>/` directories are always removed first.
- Creation: `git worktree add -B cce/<slug> scenarios/.tmp-<slug> <sha>`; write the rendered plan; `chmod` the files marked executable; `git add --force -- <explicit list of destinations>` so an upstream `.gitignore` cannot drop overlay files; `git commit --no-verify`; `git update-ref refs/cce/baseline/<slug> HEAD`; `git worktree move` into `scenarios/<slug>/`; write state. Any failure runs `git worktree remove --force` on the staging path, then `git worktree prune` and `git branch -D cce/<slug>`, leaving the scenario `missing` so the next `setup` recreates it.
- `reset ID` is `git reset --hard refs/cce/baseline/<slug>` followed by `git clean -fdxq`; it performs no rendering. `reset all` does the same for every scenario and skips `missing` ones with a warning.
- `teardown`: an absent workspace exits 0; a directory without the marker exits 3; any `modified` scenario without `--force` exits 3 listing them; otherwise `git worktree remove --force` on each scenario, then `rmtree` on the workspace. It never prompts.
- `cce list` never fails: one row per manifest scenario with status, dialect and whether the stored digest differs from the current render (overlay drift). `cce path ID` prints only the absolute path; when the scenario is `missing` it prints nothing to stdout and exits 3.
- `cce doctor` reports the workspace path, marker, writability and lock, the state ref against the pin, and overlay digest drift; an absent workspace is never `fail`.
- `--force` is the only escalation. No command removes a `modified` worktree without it, and no code path deletes a directory tree that lacks the `.cce-workspace` marker unless the tree is a `.tmp-` staging path.

## Consequences

- Reset is one git operation with no rendering, so it is fast and cannot fail because an overlay changed underneath it; a changed overlay appears as drift in `cce list` and is applied by the next `setup`.
- Status is trustworthy because it is derived from git against a ref the reader is never told to touch; `state.json` only records what was rendered and with which dialect.
- A second unchanged `setup` is a no-op with no git writes, so guides can tell readers to run it freely.
- Six worktrees share one object store: the workspace costs one clone plus six checkouts, not six clones.
- Interrupted creation cannot leave a half-built scenario in place, because the worktree only moves into `scenarios/<slug>/` after its baseline commit and ref exist.
- A reader's uncommitted work is protected by exit 3 on `setup` and `teardown`; only `--force` discards it. A presenter who wants a clean slate types `--force` or runs `cce reset all` first.
- The lock serialises setup, reset and teardown; a second invocation fails fast with exit 3 instead of corrupting state.
- Branches named `cce/<slug>` and refs under `refs/cce/` appear in the base clone. They are namespaced so they cannot collide with upstream refs, and anyone inspecting `base/` will see them.

## Review guidance

- Require every baseline ref written or read in `src/cce/workspace.py` to live under `refs/cce/baseline/`, and require status to be computed by comparing HEAD against that ref.
- Require `reset` in `src/cce/workspace.py` to run `git reset --hard` and `git clean -fdx`, and to call nothing from `src/cce/render.py`.
- Flag `shutil.rmtree` in `src/cce/` whose target is not guarded by a `.cce-workspace` marker check and is not a `.tmp-` staging path.
- Flag any `git worktree remove` in `src/cce/workspace.py` reachable for a `modified` worktree while `force` is false.
- Flag `git add` in `src/cce/workspace.py` without `--force` and an explicit path list (for example `git add .` or `git add -A`).
- Require `tests/test_workspace.py` to define `test_setup_is_idempotent_when_already_ready`, `test_setup_refuses_modified_worktree_without_force` and `test_partial_creation_is_reported_missing`.
- Require `tests/test_workspace.py` to assert that a second unchanged `setup` performs no git writes.
