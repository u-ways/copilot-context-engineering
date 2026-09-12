# ADR-0001: ADR-driven development

- Status: Accepted
- Date: 2026-09-13

## Context

`cce` is a small open-source command-line tool maintained by one owner and reviewed largely by automation. Decisions about the toolchain, the workspace engine, the CLI contract and the release process need a home that outlives chat transcripts and pull-request threads, and that an automated reviewer can apply consistently. Without a written, binding record every pull request re-litigates the same questions and the automated review has nothing to judge against.

The chosen mechanism is Architecture Decision Records in `docs/adrs/`, in the MADR-lite shape described in `docs/adrs/README.md`. Every architecturally significant change lands in the same pull request as the ADR that permits it: either a new ADR, or an existing ADR amended with a `- Revision YYYY-MM-DD: ...` bullet placed directly under its `- Date:` bullet. "Architecturally significant" is defined mechanically rather than by taste: new files under `src/cce/`, new or changed workflows under `.github/workflows/`, and changes to the `[project]` table of `pyproject.toml`. A new entry in `[project.dependencies]` always needs an ADR that names the package; development-only stubs (typing packages such as `types-*` distributions, which live in `[dependency-groups]`) are exempt from that rule.

The `adr-review` GitHub workflow (`.github/workflows/adr-review.yml`) gates merges. It runs Claude Code non-interactively (`claude -p`) with a prompt that reads every ADR in `docs/adrs/`, reads the pull-request diff and body, judges the change against the `## Decision` and `## Review guidance` sections only, posts one review with inline comments that cite ADR identifiers, and writes a verdict file; the job fails unless the verdict reports zero violations. The prompt tolerates ADRs that exist only in the diff, so the pull request that introduces this ADR is reviewed against it: ADR-0001 is self-permitting for that pull request, and the workflow file it depends on is covered by ADR-0002.

## Decision

- Every architecturally significant change lands in the same pull request as the ADR that permits it: a new ADR, or an existing ADR with a `- Revision YYYY-MM-DD:` bullet describing the amendment.
- ADRs are the highest-authority documents in the repository. Where an ADR and any other document disagree, the ADR wins and the other document is corrected.
- ADRs follow the MADR-lite structure and status legend in `docs/adrs/README.md`. `## Review guidance` holds only `Flag ` and `Require ` bullets, each settled by a mechanical check.
- `docs/adrs/README.md` is the index and lists every ADR.
- The `adr-review` workflow gates merges to `main` as a required status check and judges against the ADRs only.
- A pull request that touches a protected area without changing a file under `docs/adrs/` must cite the permitting ADR (`ADR-NNNN`) in its body.

## Consequences

- Design intent is discoverable from the repository alone, and the automated reviewer has a fixed rubric instead of general taste.
- Contributors pay a small, predictable cost per significant change: write or amend an ADR in the same pull request. Small fixes and documentation changes pay nothing.
- Review guidance must be phrased so that a grep or a file check settles it; bullets that need judgement are rejected by this ADR's own guidance.
- The workflow depends on the `CLAUDE_CODE_OAUTH_TOKEN` secret. If the secret is unavailable the check fails closed and the owner reviews against the ADRs by hand before merging.
- Amendments accumulate as `- Revision` bullets rather than rewrites, so the history of a decision is readable in place.

## Review guidance

- Flag new files under `src/cce/`, new or changed files under `.github/workflows/`, or changes to the `[project]` table of `pyproject.toml` in a pull request that neither changes a file under `docs/adrs/` nor cites an `ADR-NNNN` in the pull-request body.
- Flag new entries in `[project.dependencies]` of `pyproject.toml` that no ADR names; development-only stubs under `[dependency-groups]` are exempt.
- Require every `docs/adrs/NNNN-*.md` file to have a first line of the form `# ADR-NNNN: <Title>`, a `- Status:` bullet, a `- Date:` bullet, and exactly the four H2 headings `## Context`, `## Decision`, `## Consequences` and `## Review guidance` in that order.
- Require every `- Status:` value to be one of `Proposed`, `Accepted`, `Superseded by ADR-NNNN` (with a real number) or `Deprecated`.
- Require `docs/adrs/README.md` to list every `docs/adrs/NNNN-*.md` file in its index table.
- Flag any bullet under `## Review guidance` in any ADR that does not start with `Flag ` or `Require `.
