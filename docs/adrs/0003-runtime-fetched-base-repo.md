# ADR-0003: Runtime-fetched base repository at a pinned ref

- Status: Accepted
- Date: 2026-09-13
- Revision 2026-09-13: the manifest's `source.url` is the fork `u-ways/software-engineering-quality-framework`, whose `main` sits at the pinned commit, so the pin and every measured number are unchanged and the pinned history can no longer move or vanish underneath the scenarios. A fork cannot relicense the content, so every rule below applies to it unchanged; wherever this ADR names `NHSDigital/`, the fork's name counts the same way.
- Revision 2026-09-13: `--source-ref` must be a 40-hexadecimal-digit commit sha like the manifest's pin (a branch name would silently freeze at the clone-time snapshot); anything else is a usage error. Upstream blobs are read as bytes so a non-UTF-8 file reaches the renderer's own error path.

## Context

The scenarios are built on a real repository so that what a reader sees in `/context`, in token counts and in diffs comes from real pages rather than invented filler. The base content is the NHS's `NHSDigital/software-engineering-quality-framework`, cloned from the fork `u-ways/software-engineering-quality-framework`. That repository carries no licence, which means no right to copy, modify or redistribute any part of it: no file, snapshot or excerpt from it may be committed here, shipped in the wheel, or uploaded from CI.

The scenarios still need its real pages at a fixed point in history. S01 regenerates stale instructions from dated history (ADR-0005), and every guide states expected numbers (token counts, link counts, file counts) that only hold at one commit. A moving `main` would silently change the demo between two readers.

Tests run on every pull request and must not depend on the network or on the upstream repository staying available. A periodic check against the real pin is still needed to catch upstream drift and to enforce the licence position mechanically rather than by review.

LLM-backed runs (ADR-0010) produce transcripts that may echo upstream prose verbatim, so their outputs fall under the same rule as source files.

## Decision

- The base repository is cloned at runtime into the workspace `base/` directory (ADR-0004) as a full-history `--no-checkout` clone: no `--depth`, no `--filter`. History is needed for dated includes and for checking out the pinned commit; the clone is never shallow or blob-filtered.
- The pin is `source.ref` in `src/cce/overlays/scenarios.toml`, a 40-hexadecimal-digit commit sha. It is the only place the pin lives under `src/`; guides, tests and workflows read it from the manifest rather than repeating it.
- `cce setup` first runs `git cat-file -e <ref>^{commit}` in the base clone. When that succeeds no network is used. Only when it fails does setup run `git fetch --no-tags origin <ref>`, falling back to a full fetch when the remote refuses a sha fetch. Repeat runs are therefore offline.
- `source.url` in the manifest is the fork `u-ways/software-engineering-quality-framework`; its `main` stays at or ahead of the pin and is never rewritten, so `cce setup` on a fresh machine always finds the pinned commit.
- `cce setup --source-url` and `--source-ref` override the manifest for tests and forks. A `source_url` that differs from the one recorded in workspace state is refused with exit 3 rather than mixed into an existing clone.
- The default test tier never touches the real upstream. `tests/support/upstream.py` builds a synthetic repository from invented text, with a placeholder file for every path returned by `render.include_targets()`, and serves it over `file://`. Only `tests/e2e/` and `tests/llm/` may name the framework repository (`u-ways/software-engineering-quality-framework` or `NHSDigital/software-engineering-quality-framework`) or clone from a URL that is not `file://`.
- The e2e tier clones the real pin into a temporary directory and asserts: six `ready` worktrees; every baseline commit's parent is the pinned sha; every include target exists; total included bytes stay within 300 to 450 KB; and the licence guard, which fails when any line of forty or more characters in `docs/` or `src/cce/overlays/` equals a line of any upstream file at the pin.
- Guides, tests and overlays cite upstream as `path:line` and paraphrase in their own words; they never quote upstream text. No directory named `fixtures`, `testdata` or `golden` under `tests/` holds `.md` files, because that is where upstream snapshots would otherwise accumulate.
- After a fetch, setup warns when the pinned tree tracks any of `AGENTS.md`, `CLAUDE.md`, `.github/copilot-instructions.md`, `.github/instructions/**`, `.github/skills/**`, `.github/agents/**` or `.claude/**`, because upstream customisation would skew every scenario. The e2e tier asserts that none of these exist at the pin, so moving the pin to a commit that adds one is a deliberate, reviewed change.
- Transcripts from LLM runs stay under `.cce-artifacts/` (gitignored) and are never committed or uploaded; CI uploads only the structural `RunResult` JSON.
- `README.md` states that upstream content is fetched at runtime and is not redistributed.

## Consequences

- This repository contains only its own text and the overlay files; a clone of it is not a copy of any upstream content, and the wheel ships none.
- The first `cce setup` needs the network and pays for a full-history clone; every later run is offline until the pin moves.
- Moving the pin is a one-line manifest change followed by an e2e run, which re-derives every expected number in the guides.
- The default tier proves the engine against an invented repository, so a behaviour that only appears with real upstream content is caught by the scheduled e2e run rather than on every pull request. The e2e tier exists for exactly that gap.
- Contributors cannot paste upstream text into a guide to explain a scenario; they cite `path:line` and describe it in their own words. The licence guard fails the e2e run when the rule is broken.
- Forks pointing at a different upstream use `--source-url` and `--source-ref`, and their overlays must render against that upstream's include targets.
- The fork insulates the scenarios from the original repository deleting or rewriting history at the pin. It is a GitHub fork of a public repository, which GitHub's terms allow; that permission does not extend to copying the content into this repository, the wheel or CI artefacts, so no copy exists outside GitHub, by design.

## Review guidance

- Require the pinned 40-hexadecimal-digit sha to appear in the repository only in `src/cce/overlays/scenarios.toml`.
- Flag `--depth` or `--filter` anywhere under `src/cce/`.
- Flag any file under `tests/` outside `tests/e2e/` and `tests/llm/` that contains `NHSDigital/` or `u-ways/software-engineering-quality-framework`, or clones from a URL that does not start with `file://`.
- Flag any directory named `fixtures`, `testdata` or `golden` under `tests/` that contains a `.md` file.
- Flag quoted upstream prose in `docs/`, `src/cce/overlays/` or `tests/`; the mechanical check is the e2e licence guard under `tests/e2e/` (no line of forty or more characters in `docs/` or `src/cce/overlays/` equals a line of any upstream file at the pin).
- Require `README.md` to state that upstream content is fetched at runtime and is not redistributed.
- Require `tests/e2e/` to contain a test asserting that none of `AGENTS.md`, `CLAUDE.md`, `.github/copilot-instructions.md`, `.github/instructions/`, `.github/skills/`, `.github/agents/` and `.claude/` exist in the pinned tree.
