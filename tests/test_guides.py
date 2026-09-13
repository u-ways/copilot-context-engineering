"""One guide per scenario with fixed sections, shipped in the wheel, plus the entry pages.

ADR-0009 (guides, index, summary), ADR-0006 (exit codes) and ADR-0003 (the runtime-fetch
statement), the latter two in CONTRIBUTING.md.
"""

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
        expected = {f"{scenario.slug}.md" for scenario in load().scenarios} | {"README.md"}

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


class TestEntryPoints:
    def test_scenarios_index_links_every_guide(self) -> None:
        index = (SCENARIOS_DOCS / "README.md").read_text(encoding="utf-8")

        assert index.startswith("# ")
        for scenario in load().scenarios:
            assert f"({scenario.slug}.md)" in index, scenario.slug

    def test_prerequisites_carry_the_install_line(self) -> None:
        text = (REPO_ROOT / "docs" / "PREREQUISITES.md").read_text(encoding="utf-8")

        assert 'uv tool install "copilot-context-engineering @ git+' in text

    def test_contributing_states_the_runtime_fetch_rule(self) -> None:
        text = (REPO_ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")

        assert "fetched at runtime" in text
        assert re.search(r"(not|none of [^.]* is) redistributed", text)

    def test_contributing_carries_the_exit_code_table(self) -> None:
        text = (REPO_ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")

        for code in range(4):
            assert f"| {code} |" in text, code


class TestSummary:
    def test_carries_the_comparison_table_and_the_tldr(self) -> None:
        summary = (REPO_ROOT / "docs" / "SUMMARY.md").read_text(encoding="utf-8")

        for row in ("| Always loaded? |", "| Adaptive? |", "| Size concern? |"):
            assert row in summary
        assert 'TL;DR: Instructions = "Always follow these rules."' in summary

    def test_every_row_links_a_scenario_guide(self) -> None:
        summary = (REPO_ROOT / "docs" / "SUMMARY.md").read_text(encoding="utf-8")
        guides = [f"scenarios/{scenario.slug}.md" for scenario in load().scenarios]

        for row in ("| Always loaded? |", "| Adaptive? |", "| Size concern? |"):
            line = next(line for line in summary.split("\n") if line.startswith(row))
            assert any(guide in line for guide in guides), row


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
        assert guide_path(manifest, "scenarios", packaged) == packaged / "README.md"

        docs = tmp_path / "docs"
        assert guide_path(manifest, "03-skills-on-demand", docs) == (
            docs / "scenarios" / "03-skills-on-demand.md"
        )
        assert guide_path(manifest, "presenting", docs) == docs / "presenting.md"
        assert guide_path(manifest, "scenarios", docs) == docs / "scenarios" / "README.md"


class TestGuideCommand:
    def test_prints_the_scenario_guide(self, cli: CliRunner) -> None:
        result = cli.invoke(app, ["guide", "skills-on-demand"])

        assert result.exit_code == 0
        assert result.stdout == (SCENARIOS_DOCS / "03-skills-on-demand.md").read_text()

    def test_prints_the_presenting_guide(self, cli: CliRunner) -> None:
        result = cli.invoke(app, ["guide", "presenting"])

        assert result.exit_code == 0
        assert result.stdout.startswith("# ")

    def test_prints_the_walkthrough_index(self, cli: CliRunner) -> None:
        result = cli.invoke(app, ["guide", "scenarios"])

        assert result.exit_code == 0
        assert result.stdout == (SCENARIOS_DOCS / "README.md").read_text()

    def test_unknown_id_is_a_usage_error(self, cli: CliRunner) -> None:
        result = cli.invoke(app, ["guide", "99"])

        assert result.exit_code == 2 and result.stdout == ""
