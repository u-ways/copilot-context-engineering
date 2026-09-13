# Agent guide

Binding rules for any coding agent, and any human, working in this repository.

This file holds only rules that stay true as the code changes. Anything that describes the current state of the repository (which recipes exist, which variables are read, which files live where) belongs to the place that defines it and is pointed to from here, never copied.

## Where the truth lives

- Decisions: `docs/adrs/README.md`. ADRs win over every other document, this one included. Read the index first, then the ADR an area cites before changing that area.
- Commands: the `justfile`. Run `just` to list the recipes and what each does. CI runs the same recipes, so a workflow never calls `uv`, `pytest`, `ruff` or `mypy` directly.
- Configuration: the code that reads an environment variable defines it. User-facing variables are documented in `docs/PREREQUISITES.md`, release and update ones in `docs/RELEASING.md`, the LLM tier's in ADR-0010.
- Scenarios: `src/cce/overlays/scenarios.toml` is the manifest; every id, slug, check and comparison comes from it, and no Python branches on a scenario. One guide per scenario lives under `docs/scenarios/`, indexed by that directory's `README.md`.
- The tool from the inside, its exit codes and the pull-request flow: `CONTRIBUTING.md`.

## Binding rules

- Every architecturally significant change lands in the same PR as the ADR that permits it: either a new ADR or a `- Revision YYYY-MM-DD:` bullet on an existing one. ADR-0001 defines "significant" mechanically.
- Commit and PR titles are sentence-case imperative, usually `Area: summary`.
- Branches are `feat/`, `fix/` or `docs/`; PRs are squash-merged; CI must be green before merge.
- TDD: a behaviour change lands with its test, a bug fix with a regression test.
- Tests use fakes (real scripts or injected callables), never mocks; they are class-grouped with behaviour-sentence names, fully typed, and their module docstrings cite the ADR under test.
- `# noqa` and `# type: ignore` need a bracketed code and a reason.
- Overlay files under `src/cce/overlays/` never use leading-dot path segments (`github/` renders as `.github/`).
- stdout is for results; stderr is for logs. Only `cli.py` prints or exits; every other module raises `CceError` and returns values.

## Finding your way

The layout follows conventions rather than a list:

- `src/cce/` has one module per concern, named for it. `cli.py` is the command surface; `overlays/` holds the manifest, the shared procedures, agents and scripts under `_shared/`, and one directory per scenario.
- `tests/` mirrors `src/cce/` module for module as `test_<module>.py`. `tests/e2e/` and `tests/llm/` are the opt-in tiers behind pytest markers; `tests/support/` and `tests/fakes/` hold the synthetic upstream and the shims.
- `docs/` holds the ADRs, the guides and the user-facing pages; `.github/` holds the workflows and the ADR-review prompt.
- When a file's purpose is unclear, its module docstring names the ADR it implements.
