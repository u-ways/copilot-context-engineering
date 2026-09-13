"""Shared fixtures for the offline test suite (ADR-0002)."""

import json
import os
import stat
import sys
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
import structlog
from typer.testing import CliRunner

from cce.render import include_targets
from tests.support.upstream import GitUpstream, SyntheticUpstream, build

REPO_ROOT = Path(__file__).resolve().parent.parent


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--runtime",
        choices=("copilot", "claude"),
        default=os.environ.get("CCE_LLM_RUNTIME", "copilot"),
        help="Coding agent the llm tier drives (copilot or claude).",
    )


@pytest.fixture(autouse=True)
def quiet_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    """Keep every test hermetic: no update checks, no user config, no herdr."""
    monkeypatch.setenv("CCE_DISABLE_UPDATE_CHECK", "1")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg-data"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg-cache"))
    monkeypatch.delenv("HERDR_ENV", raising=False)
    monkeypatch.delenv("CCE_WORKSPACE", raising=False)
    yield
    structlog.reset_defaults()


@pytest.fixture
def cli() -> CliRunner:
    """A Typer runner that keeps stdout and stderr separate."""
    return CliRunner()


@pytest.fixture(scope="session")
def upstream(tmp_path_factory: pytest.TempPathFactory) -> SyntheticUpstream:
    """The synthetic upstream repository, built once per session."""
    return build(tmp_path_factory.mktemp("upstream") / "repo", include_targets())


@pytest.fixture
def reader(upstream: SyntheticUpstream) -> GitUpstream:
    """An upstream reader over the synthetic repository's head."""
    return GitUpstream(upstream.path, upstream.head)


@pytest.fixture
def shim_bin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[[str, str], Path]:
    """Install fake executables on PATH: ``shim_bin("uv", "fake_uv.py")``."""
    bin_dir = tmp_path / "shim-bin"
    bin_dir.mkdir(exist_ok=True)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    def install(name: str, fake: str) -> Path:
        script = REPO_ROOT / "tests" / "fakes" / fake
        shim = bin_dir / name
        shim.write_text(f'#!/bin/sh\nexec {sys.executable} {script} "$@"\n', encoding="utf-8")
        shim.chmod(shim.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        return shim

    return install


@pytest.fixture
def release_file(tmp_path: Path) -> Callable[[str], str]:
    """Write a releases/latest body for ``tag`` and return its file:// URL."""

    def write(tag: str) -> str:
        path = tmp_path / "latest.json"
        path.write_text(json.dumps({"tag_name": tag}), encoding="utf-8")
        return path.as_uri()

    return write
