"""Fixtures for the LLM tier: one rendered workspace per runtime, results shared per session."""

import json
import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from cce.cli import app
from cce.manifest import Manifest, load
from tests.llm.runners import AgentRunner, RunResult, runner_for

REPO_ROOT = Path(__file__).resolve().parents[2]
ARTEFACTS = REPO_ROOT / ".cce-artifacts"


@pytest.fixture(scope="session")
def runtime(request: pytest.FixtureRequest) -> AgentRunner:
    name = str(request.config.getoption("--runtime"))
    if shutil.which(name) is None:
        pytest.skip(f"{name} is not on PATH")
    return runner_for(name)


@pytest.fixture(scope="session")
def manifest() -> Manifest:
    return load()


@pytest.fixture(scope="session")
def llm_workspace(runtime: AgentRunner, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The real pinned upstream rendered in the runtime's dialect."""
    root = tmp_path_factory.mktemp("llm") / "ws"
    result = CliRunner().invoke(
        app, ["--workspace", str(root), "setup", "--dialect", str(runtime.dialect)]
    )
    assert result.exit_code == 0, result.stderr
    return root


@pytest.fixture(scope="session")
def artefacts(runtime: AgentRunner) -> Path:
    directory = ARTEFACTS / "transcripts" / runtime.name
    directory.mkdir(parents=True, exist_ok=True)
    return directory


@pytest.fixture(scope="session")
def results(runtime: AgentRunner) -> Iterator[dict[str, RunResult]]:
    """Results keyed by ``<scenario id>/<check name>``; structural JSON is written on exit."""
    store: dict[str, RunResult] = {}
    yield store
    out = ARTEFACTS / "results" / runtime.name
    out.mkdir(parents=True, exist_ok=True)
    for key, result in store.items():
        path = out / (key.replace("/", "-") + ".json")
        path.write_text(json.dumps(result.structural(), indent=2) + "\n", encoding="utf-8")
