# ADR-0009: Self-serve guides

- Status: Accepted
- Date: 2026-09-13
- Revision 2026-09-13: `docs/scenarios/README.md` is the walkthrough index, the entry point to the scenarios; it is not a guide, so the four-heading rule does not apply to it, and `cce guide scenarios` prints it. `docs/PREREQUISITES.md` holds the requirements and install steps, `CONTRIBUTING.md` the internals, exit codes and development recipes. `README.md` stays a brief front page: purpose, the comparison table with the TL;DR line, the scenario table with guide links and pointers to those pages.

## Context

The scenarios only teach if a reader can run them alone: open a worktree, type the right prompt, know what to look at, and reset. A talk's speaker notes do not survive the talk. The guides therefore need a fixed shape a reader can scan in a minute, they must ship with the tool (a `uv tool install` gives no checkout to browse), and they must never carry upstream prose, only paths and line numbers (ADR-0003).

## Decision

- One guide per scenario at `docs/scenarios/<slug>.md`, where `<slug>` is the id-prefixed manifest slug (`03-skills-on-demand.md`), plus `docs/scenarios/README.md`, the walkthrough index that links every guide, and `docs/presenting.md` for live talks. No other files live under `docs/scenarios/`.
- Every scenario guide has one level-1 title and exactly these level-2 headings, in this order: `## What it shows`, `## Run it`, `## What to notice`, `## Reset`. Level-3 headings inside them are allowed.
- Guides carry the exact commands and prompts to type, the observation protocol (`/context` before and after the prompt, `/usage`, `/diff` or `git status --porcelain`), every expected number with the one-liner that re-derives it, and cite upstream files as `path:line` only.
- The guides ship inside the wheel: `[tool.hatch.build.targets.wheel.force-include]` maps `docs/scenarios` to `cce/guides` and `docs/presenting.md` to `cce/guides/presenting.md`. `cce guide ID|presenting|scenarios` prints a guide, the presenter guide or the walkthrough index to stdout; the loader uses the packaged directory when it exists and falls back to `docs/` in an editable install, where hatchling's force-include is not visible.
- `README.md` carries the "Which should I use?" comparison table with the TL;DR line, and a scenario table listing 01–06 with links to the guides.

## Consequences

- A reader with only the installed tool can read every guide (`cce guide 3`), and herdr tabs can open them without a checkout.
- The fixed headings make the guides greppable and let a test enforce their shape.
- Changing a scenario's expected numbers means changing the guide in the same pull request; the e2e tier keeps the numbers honest.
- The force-include duplicates nothing in git: the files exist once under `docs/` and are copied only into the wheel.

## Review guidance

- Require `docs/scenarios/<slug>.md` for every `[[scenario]]` slug in `src/cce/overlays/scenarios.toml`, and no other `.md` files under `docs/scenarios/` apart from `README.md`.
- Require every `docs/scenarios/<slug>.md` guide (not the `README.md` index) to contain exactly the level-2 headings `## What it shows`, `## Run it`, `## What to notice` and `## Reset`, in that order.
- Require `README.md` to contain the rows `| Always loaded? |`, `| Adaptive? |` and `| Size concern? |`, the line starting `TL;DR: Instructions = "Always follow these rules."`, and a link to `docs/scenarios/<slug>.md` for every scenario.
- Require `docs/scenarios/README.md` to link every `docs/scenarios/<slug>.md` guide, and `docs/PREREQUISITES.md` to contain the `uv tool install` line.
- Require `[tool.hatch.build.targets.wheel.force-include]` in `pyproject.toml` to map `docs/scenarios` to `cce/guides` and `docs/presenting.md` to `cce/guides/presenting.md`.
- Require `src/cce/manifest.py` to fall back to `docs/` when the packaged `guides` directory is absent.
- Flag any `docs/scenarios/*.md` or `docs/presenting.md` line that quotes upstream prose (the e2e licence guard is the mechanical check).
