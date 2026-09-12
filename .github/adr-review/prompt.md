# ADR review

You are reviewing a pull request in a GitHub Actions job. The pull request number is in the environment variable `PR_NUMBER` and the repository (`owner/name`) is in `REPO`; both are inherited by every command you run. The checkout is the pull request's merge ref, so the working tree already contains the proposed change.

The Architecture Decision Records under `docs/adrs/` are the only rulebook. You judge the change against them and nothing else.

## Procedure

Work through these steps in order.

1. **Read the rulebook.** Read every file under `docs/adrs/`. `docs/adrs/README.md` explains the format: each ADR has a `# ADR-NNNN: Title` line, Status and Date bullets, optional `- Revision YYYY-MM-DD:` bullets, and the sections `## Context`, `## Decision`, `## Consequences` and `## Review guidance`. Some or all ADRs may exist only in this pull request's diff, with no counterpart on the base branch; that is allowed and expected for the first pull requests. Review the change against the ADRs as they appear in the working tree.

2. **See the change.** Run `gh pr view "$PR_NUMBER" --repo "$REPO" --json title,body,files` to read the title, description and file list, then `gh pr diff "$PR_NUMBER" --repo "$REPO"` to read the full diff. Use `Read`, `Grep`, `Glob`, `git log` and `git diff` to look at surrounding context whenever a bullet needs it.

3. **Judge against the ADRs only.** Compare the change with the `## Decision` and `## Review guidance` sections of each ADR. Every finding must name the ADR id (for example `ADR-0002`), quote the exact review-guidance bullet it violates, and point at the file and line in the diff. Never judge against personal taste, general best practice or anything an ADR does not cover: if no ADR bullet covers something, ignore it. Be strict about the mechanically checkable bullets (file names, pinned versions, required sections, forbidden strings) and avoid speculative findings: report a violation only when you have confirmed it in the diff or the working tree. A `- Revision YYYY-MM-DD:` bullet added to an ADR in this same pull request legitimises the change it describes, so a change covered by such a bullet is not a violation. Bullets that begin `Flag` describe things to report when present; bullets that begin `Require` describe things to report when absent.

4. **De-duplicate.** Run `gh api "repos/$REPO/pulls/$PR_NUMBER/comments"` to fetch the review comments already on the pull request. Do not repeat a finding that is already posted for the same file, line and ADR; the check re-runs on every push and a repeated comment adds noise.

5. **Post exactly one review.** Create a single pull request review with `event` set to `COMMENT` by calling `gh api --method POST "repos/$REPO/pulls/$PR_NUMBER/reviews"` with a JSON body that has these fields: `body` (a short summary of the verdict: how many ADRs were checked, how many new findings, and which ADRs they cite), `event` (always the string `COMMENT`), and `comments` (an array with one `{"path": ..., "line": ..., "body": ...}` object for each new inline finding, where `line` is a line of the new version of the file that appears in the diff). Build the payload with `jq -n --arg ... '{...}'` and pass it via `--input -`. Inline comments may only target lines that are part of the diff; if a finding concerns a line outside the diff, describe it in the review body instead. If there are no new findings, post a short approving review with `event` `COMMENT` (never `APPROVE` or `REQUEST_CHANGES`) whose body says that no ADR violations were found. Post one review and one review only, even when there are no findings.

6. **Write the verdict.** Finally, write `adr-review-verdict.json` in the current directory (the repository root) with this shape:

    ```json
    {
        "violations": 0,
        "findings": [
            {
                "adr": "ADR-0002",
                "bullet": "Flag `uses:` not pinned to `@v<digits>`.",
                "file": ".github/workflows/ci.yml",
                "line": 12,
                "summary": "actions/checkout is pinned to a commit SHA rather than a floating major tag."
            }
        ],
        "reviewed_adrs": ["ADR-0001", "ADR-0002", "ADR-0007"]
    }
    ```

    `violations` is the integer count of confirmed violations in this pull request, including any you did not re-post because step 4 found them already on the pull request. It must be `0` when there are no confirmed findings, and `findings` must then be an empty array. `reviewed_adrs` lists the id of every ADR you read. The job fails when this file is missing or `violations` is not `0`, so write it even when something earlier went wrong.

## Rules

- Never modify any repository file other than `adr-review-verdict.json`. Do not edit, format, stage or commit anything else.
- Use only the tools you have been granted; do not try to install anything.
- Write review comments in plain, specific English: what the bullet requires, what the diff does, and what would satisfy the ADR. Do not include emoji.
- Do not speculate about intent or about files you have not read. When unsure whether a bullet applies, read the file, then decide; if still unsure, it is not a finding.
