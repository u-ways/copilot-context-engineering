# ADR-0007: Release and update check

- Status: Accepted
- Date: 2026-09-13
- Revision 2026-09-13: the prompt is reachable only when stdin, stdout and stderr are all TTYs, so `cd "$(cce path N)"` and piped guide tabs never block on it.
- Revision 2026-09-13: `cce update [--check]`, the result-callback wiring and the `CCE_RELEASES_URL` override (a `file://` or https URL used by tests and forks instead of the GitHub API) land with `src/cce/update.py`.

## Context

`cce` is distributed only through GitHub Releases and installed from git with `uv tool install` (ADR-0002). No package index tells users that a newer version exists, so the tool must announce releases itself, and releasing must be cheap enough that the owner does it often. Two failure modes shape the design: release automation that turns red on unrelated merges (for example Dependabot lockfile bumps pushed to `main`) trains everyone to ignore it, and an update check that can slow down or break a command is worse than none. The version also has to live somewhere the build, the running tool and the release workflows all agree on, without a build step that computes it from git.

## Decision

- Static version in exactly two places: `version` in the `[project]` table of `pyproject.toml` and `__version__` in `src/cce/__init__.py`. No dynamic versioning from git. `tests/test_version.py` parses `pyproject.toml` and asserts that the two values are equal, so parity is enforced on every test run.
- Release drafting (`.github/workflows/release-drafter.yml`, `name: Release Drafter`, on push to `main`, `permissions: contents: write`, no Python toolchain needed) runs these steps in this order:
  1. Check out with full history (`fetch-depth: 0`).
  2. Read the version from `pyproject.toml` with `grep` and `sed`.
  3. If tag `vX.Y.Z` already exists (`git ls-remote --tags origin refs/tags/vX.Y.Z` matches), emit a `::notice::` and exit 0. This runs before every other check so that merges that do not bump the version, Dependabot merges included, never fail the workflow.
  4. Fail hard if `__version__` in `src/cce/__init__.py` differs from the pyproject version.
  5. Delete any existing draft release for the tag (`gh release view vX.Y.Z --json isDraft`, then `gh release delete vX.Y.Z --yes` when it is a draft).
  6. Create a draft release with generated notes via `softprops/action-gh-release` (`tag_name: vX.Y.Z`, `draft: true`, `generate_release_notes: true`).
- Release publishing (`.github/workflows/release.yml`, on `push` of `v*` tags and on `workflow_dispatch` with a `version` input, `permissions: contents: write`): the version comes from the input or `${GITHUB_REF_NAME#v}`; on dispatch the tag is created in-run if it does not exist; then `softprops/action-gh-release` publishes with `draft: false` and `prerelease: false`. The step is idempotent across the three starting states: a draft exists (it is published), a published release exists (it is updated in place), nothing exists (it is created).
- Update check (`src/cce/update.py`, run from Typer's `result_callback` on success only and skipped for `version`, `update` and `--help`):
  - runs at most once per `CCE_UPDATE_INTERVAL` seconds (default `86400`), tracked by `checked_at` in `$XDG_CACHE_HOME/cce/update-check.json`, which is written before the fetch so an offline machine pays the timeout at most once per interval;
  - is skipped entirely when `CCE_DISABLE_UPDATE_CHECK` or `CI` is set;
  - calls the GitHub `releases/latest` API (`RELEASES_LATEST_URL`, a module constant) through an injectable fetcher callable with a 3-second timeout; tests inject a fake fetcher and never touch the network;
  - compares the response's `tag_name` (`vX.Y.Z` or `X.Y.Z`) with `cce.__version__`;
  - when a newer version exists and stdin, stdout and stderr are all TTYs, prompts `Y/n` and on confirmation runs `uv tool upgrade copilot-context-engineering`; when not a TTY, prints one notice on stderr;
  - wraps its whole body in a top-level `except Exception` that logs at debug level, so the command's exit code never changes (raising fetcher, malformed JSON, a 404 before the first release, an unwritable cache).
- `cce update [--check]` fetches the same endpoint, prints the current and latest versions and, unless `--check` is given, runs `uv tool upgrade copilot-context-engineering` when the release is newer (uv missing exits 3, a failed upgrade exits 1). `CCE_RELEASES_URL` overrides the endpoint for tests and forks.

## Consequences

- A release bump is a two-line change reviewed like any other; the drafter turns the merge into a draft release and the owner publishes it from the Releases page.
- Every merge to `main` runs the drafter, but only merges that change the version do any work; Dependabot auto-merges, which push with a token that triggers workflows, exit at the tag-exists check.
- Forgetting one of the two version files fails the test suite locally and in CI, and fails the drafter if it somehow reaches `main`.
- Users learn about a release within a day of their next `cce` invocation, and no command ever fails or slows by more than 3 seconds because of the check.
- `releases/latest` returns 404 until the first release is published; the check treats that as "no update".
- A `git+https` install without a ref tracks `main`, so an upgrade may land a commit at or after the announced tag; `docs/RELEASING.md` documents the pinned `@vX.Y.Z` install line for readers who want exactly the tag.

## Review guidance

- Require `tests/test_version.py` to compare the `version` in `pyproject.toml` with `cce.__version__`.
- Require `pyproject.toml` to declare a static `version` (no `dynamic = ["version"]`) and `src/cce/__init__.py` to define `__version__`.
- Require `.github/workflows/release-drafter.yml` to check tag existence (`git ls-remote --tags`), then version parity against `src/cce/__init__.py`, before any `softprops/action-gh-release` step.
- Require `.github/workflows/release.yml` to publish through `softprops/action-gh-release` with `draft: false` and `prerelease: false` and to create the tag in-run on `workflow_dispatch`, so that draft-exists, release-exists and nothing-exists all succeed.
- Flag HTTP client use (`urllib.request`, `http.client`, `httpx`, `requests`, `aiohttp`) in `src/cce` outside the injectable fetcher in `update.py`.
- Flag an update-check code path in `update.py` that is not enclosed by a top-level `except Exception`.
- Flag `uv build`, wheel or sdist uploads, or PyPI steps in any workflow.
