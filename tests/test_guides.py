"""One guide per scenario with fixed sections, shipped in the wheel (ADR-0009)."""

import re
import tomllib
from pathlib import Path

import pytest
from typer.testing import CliRunner

from cce.cli import app
from cce.manifest import Scenario, guide_path, guides_root, load

REPO_ROOT = Path(__file__).resolve().parent.parent
SCENARIOS_DOCS = REPO_ROOT / "docs" / "scenarios"
REQUIRED_SECTIONS = ["## What it shows", "## Run it", "## What to notice", "## Reset"]


class TestGuideFiles:
    def test_every_scenario_has_exactly_one_guide_and_no_extras(self) -> None:
        expected = {f"{scenario.slug}.md" for scenario in load().scenarios}

        assert {path.name for path in SCENARIOS_DOCS.glob("*.md")} == expected

    @pytest.mark.parametrize("scenario", load().scenarios, ids=lambda s: s.id)
    def test_guides_carry_the_four_sections_in_order(self, scenario: Scenario) -> None:
        slug = scenario.slug
        text = (SCENARIOS_DOCS / f"{slug}.md").read_text(encoding="utf-8")

        headings = [line for line in text.split("\n") if line.startswith("## ")]
        assert headings == REQUIRED_SECTIONS, slug
        assert text.startswith("# "), slug

    def test_presenting_guide_exists(self) -> None:
        assert (REPO_ROOT / "docs" / "presenting.md").read_text().startswith("# ")


class TestReadme:
    def test_lists_every_scenario_with_its_guide_link(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

        for scenario in load().scenarios:
            assert f"| {scenario.id} |" in readme, scenario.id
            assert f"docs/scenarios/{scenario.slug}.md" in readme, scenario.slug

    def test_carries_the_comparison_table_and_the_tldr(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

        for row in ("| Always loaded? |", "| Adaptive? |", "| Size concern? |"):
            assert row in readme
        assert 'TL;DR: Instructions = "Always follow these rules."' in readme
        assert re.search(
            r"fetched at runtime.*not (part of this distribution|redistributed)", readme
        )


class TestPackaging:
    def test_wheel_force_includes_the_guides(self) -> None:
        pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        mapping = pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"]

        assert mapping == {
            "docs/scenarios": "cce/guides",
            "docs/presenting.md": "cce/guides/presenting.md",
        }

    def test_loader_prefers_the_packaged_directory_and_falls_back_to_docs(
        self, tmp_path: Path
    ) -> None:
        packaged = tmp_path / "guides"
        fallback = tmp_path / "docs"

        assert guides_root(packaged, fallback) == fallback
        packaged.mkdir()
        assert guides_root(packaged, fallback) == packaged

    def test_guide_path_uses_the_layout_of_each_root(self, tmp_path: Path) -> None:
        manifest = load()

        packaged = tmp_path / "guides"
        assert guide_path(manifest, "3", packaged) == packaged / "03-skills-on-demand.md"
        assert guide_path(manifest, "presenting", packaged) == packaged / "presenting.md"

        docs = tmp_path / "docs"
        assert guide_path(manifest, "03-skills-on-demand", docs) == (
            docs / "scenarios" / "03-skills-on-demand.md"
        )
        assert guide_path(manifest, "presenting", docs) == docs / "presenting.md"


class TestGuideCommand:
    def test_prints_the_scenario_guide(self, cli: CliRunner) -> None:
        result = cli.invoke(app, ["guide", "skills-on-demand"])

        assert result.exit_code == 0
        assert result.stdout == (SCENARIOS_DOCS / "03-skills-on-demand.md").read_text()

    def test_prints_the_presenting_guide(self, cli: CliRunner) -> None:
        result = cli.invoke(app, ["guide", "presenting"])

        assert result.exit_code == 0
        assert result.stdout.startswith("# ")

    def test_unknown_id_is_a_usage_error(self, cli: CliRunner) -> None:
        result = cli.invoke(app, ["guide", "99"])

        assert result.exit_code == 2 and result.stdout == ""
