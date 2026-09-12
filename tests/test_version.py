"""The version is declared in exactly two places and they must agree (ADR-0007)."""

import tomllib
from pathlib import Path

import cce

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestVersionParity:
    def test_pyproject_version_matches_package_version(self) -> None:
        pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        assert pyproject["project"]["version"] == cce.__version__

    def test_console_script_is_named_cce(self) -> None:
        pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        assert pyproject["project"]["scripts"] == {"cce": "cce.cli:main"}

    def test_version_is_semver(self) -> None:
        major, minor, patch = cce.__version__.split(".")
        assert all(part.isdigit() for part in (major, minor, patch))
