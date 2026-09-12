"""Shared fixtures for the offline test suite (ADR-0002)."""

from collections.abc import Iterator
from pathlib import Path

import pytest
import structlog
from typer.testing import CliRunner

REPO_ROOT = Path(__file__).resolve().parent.parent


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
