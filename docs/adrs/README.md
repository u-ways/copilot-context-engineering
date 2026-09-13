# Architecture Decision Records

This directory holds the Architecture Decision Records (ADRs) for `copilot-context-engineering` (`cce`). When an ADR and any other document in this repository disagree (README, guides, `docs/RELEASING.md`, `AGENTS.md`, code comments), the ADR wins and the other document is corrected.

This index file is not itself an ADR.

## Index

| ADR | Title | Status | Date |
| --- | --- | --- | --- |
| [ADR-0001](0001-adr-driven-development.md) | ADR-driven development | Accepted | 2026-09-13 |
| [ADR-0002](0002-toolchain-and-delivery.md) | Toolchain and delivery | Accepted | 2026-09-13 |
| [ADR-0003](0003-runtime-fetched-base-repo.md) | Runtime-fetched base repository at a pinned ref | Accepted | 2026-09-13 |
| [ADR-0004](0004-worktree-per-scenario.md) | One git worktree per scenario with a resettable baseline | Accepted | 2026-09-13 |
| [ADR-0005](0005-overlays-and-rendering.md) | Overlays and rendering | Accepted | 2026-09-13 |
| [ADR-0006](0006-cli-output-and-logging.md) | CLI output and logging | Accepted | 2026-09-13 |
| [ADR-0007](0007-release-and-update-check.md) | Release and update check | Accepted | 2026-09-13 |
| [ADR-0008](0008-herdr-presenter-mode.md) | herdr presenter mode is opt-in | Accepted | 2026-09-13 |
| [ADR-0009](0009-self-serve-guides.md) | Self-serve guides | Accepted | 2026-09-13 |
| [ADR-0010](0010-llm-verification-tier.md) | LLM verification tier and the Claude dialect | Proposed | 2026-09-13 |

Numbers are allocated per decision area and are never reused.

## File naming

`docs/adrs/NNNN-slug.md`: four zero-padded digits, a hyphen, and a lowercase hyphenated slug (for example `0002-toolchain-and-delivery.md`).

## Structure (MADR-lite)

Every ADR uses exactly these headings, in this order, and nothing else:

```markdown
# ADR-NNNN: <Title>

- Status: <see legend>
- Date: YYYY-MM-DD
- Revision YYYY-MM-DD: <what changed and why>

## Context
## Decision
## Consequences
## Review guidance
```

The `- Revision YYYY-MM-DD:` bullet is optional and sits directly under `- Date:`; add one bullet per amendment instead of rewriting history. `## Review guidance` contains only bullets that start with `Flag ` or `Require `, and every bullet must be settled by a mechanical check (a grep, a file-existence check, a value comparison) rather than a judgement call. The `adr-review` workflow applies these bullets to every pull request.

## Status legend

| Status | Meaning |
| --- | --- |
| Proposed | Under discussion; not yet binding. |
| Accepted | Binding. Amend with a `- Revision YYYY-MM-DD:` bullet. |
| Superseded by ADR-NNNN | Replaced by a later ADR. The pointer to the replacing ADR is required. |
| Deprecated | No longer applies and has no replacement. |
