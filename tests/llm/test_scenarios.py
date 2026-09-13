"""Every manifest check holds under the chosen runtime (ADR-0010).

Run with ``just llm copilot`` or ``just llm claude``. Assertions are structural
(skills loaded, files changed, tracer lines, main-thread token ratios); the
transcripts stay under ``.cce-artifacts/`` and are never shipped.
"""

import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from cce.cli import app
from cce.manifest import Check, Compare, Scenario, load
from tests.llm.runners import AgentRunner, RunResult

pytestmark = pytest.mark.llm

MANIFEST = load()
CHECKS = [(scenario, check) for scenario in MANIFEST.scenarios for check in scenario.checks]


def check_id(item: tuple[Scenario, Check]) -> str:
    scenario, check = item
    return f"{scenario.id}/{check.name}"


@pytest.mark.parametrize("item", CHECKS, ids=check_id)
def test_check(
    item: tuple[Scenario, Check],
    runtime: AgentRunner,
    llm_workspace: Path,
    artefacts: Path,
    results: dict[str, RunResult],
) -> None:
    scenario, check = item
    reset = CliRunner().invoke(app, ["--workspace", str(llm_workspace), "reset", scenario.id])
    assert reset.exit_code == 0, reset.stderr
    worktree = llm_workspace / "scenarios" / scenario.slug

    result = runtime.run(
        worktree,
        check.prompt,
        agent=check.agent,
        artefacts=artefacts,
        label=f"{scenario.id}-{check.name}",
    )
    results[f"{scenario.id}/{check.name}"] = result

    for pattern in check.contains:
        assert re.search(pattern, result.text), (
            f"missing /{pattern}/ in reply: {result.text[:400]!r}"
        )
    for pattern in check.not_contains:
        assert not re.search(pattern, result.text), f"unexpected /{pattern}/ in reply"
    if check.skills_loaded is not None:
        assert sorted(result.skills_loaded) == sorted(check.skills_loaded)
    if check.files_changed is not None:
        assert result.files_changed == sorted(check.files_changed)
    if check.files_changed_max is not None:
        assert len(result.files_changed) <= check.files_changed_max, result.files_changed


@pytest.mark.parametrize(
    "compare", MANIFEST.compares, ids=lambda c: f"{c.left}>{c.ratio}x{c.right}"
)
def test_compare(compare: Compare, results: dict[str, RunResult]) -> None:
    missing = [side for side in (compare.left, compare.right) if side not in results]
    if missing:
        pytest.fail(f"compare needs results for {missing}; run the full tier")
    right_metric = compare.right_metric or compare.metric
    left = getattr(results[compare.left], compare.metric)
    right = getattr(results[compare.right], right_metric)
    assert isinstance(left, int | float) and isinstance(right, int | float)
    assert left > compare.ratio * right, (
        f"{compare.left}.{compare.metric}={left} is not more than {compare.ratio}x "
        f"{compare.right}.{right_metric}={right}"
    )
