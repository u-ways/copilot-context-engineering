"""Directives expand once, never re-scan included text, and fail closed (ADR-0005)."""

from pathlib import Path

import pytest

from cce.manifest import Manifest, parse
from cce.render import (
    IncludeTarget,
    PlaceholderUpstream,
    PlannedFile,
    Procedure,
    RenderError,
    digest,
    include_targets,
    load_procedures,
    map_dest,
    plan_scenario,
    render_text,
    residual_directives,
)
from tests.support.upstream import INERT_LINE, NEW_MARKER, OLD_MARKER, GitUpstream

PROCEDURES = {
    "alpha": Procedure(1, "alpha", "Alpha", "Alpha description: first", "Alpha body\n"),
    "beta": Procedure(2, "beta", "Beta", "Beta description: second", "Beta body\n"),
    "nested": Procedure(3, "nested", "Nested", "Nested", "<!-- cce:procedure alpha -->\n"),
    "loop": Procedure(4, "loop", "Loop", "Loop", "<!-- cce:procedure loop -->\n"),
}


class TestInclude:
    def test_inserts_the_upstream_file_verbatim(self, reader: GitUpstream) -> None:
        rendered = render_text("before\n<!-- cce:include blueprints.md -->\nafter", reader, {})

        assert rendered == f"before\n| Topic |\n| --- |\n| {NEW_MARKER} |\nafter"

    def test_asof_reads_the_revision_on_or_before_the_date(self, reader: GitUpstream) -> None:
        rendered = render_text("<!-- cce:include blueprints.md asof=2025-10-31 -->", reader, {})

        assert OLD_MARKER in rendered
        assert NEW_MARKER not in rendered

    def test_included_text_is_never_rescanned(self, reader: GitUpstream) -> None:
        rendered = render_text("<!-- cce:include inert.md -->", reader, {})

        assert INERT_LINE in rendered

    @pytest.mark.parametrize(
        ("line", "message"),
        [
            ("<!-- cce:include -->", "needs a path"),
            ("<!-- cce:include /etc/passwd -->", "relative"),
            ("<!-- cce:include ../outside.md -->", "relative"),
            ("<!-- cce:include a//b.md -->", "relative"),
            ("<!-- cce:include missing.md -->", "not found at the pinned ref"),
            ("<!-- cce:include blueprints.md asof=2019-01-01 -->", "not found as of 2019-01-01"),
            ("<!-- cce:include blueprints.md when=2025-10-31 -->", "asof=YYYY-MM-DD"),
            ("<!-- cce:include blueprints.md asof=yesterday -->", "asof=YYYY-MM-DD"),
            ("<!-- cce:frobnicate x -->", "unknown directive verb"),
            ("<!-- cce:include blueprints.md", "malformed directive"),
            ("  <!-- cce: -->", "malformed directive"),
        ],
    )
    def test_rejects_bad_directives_with_file_and_line(
        self, reader: GitUpstream, line: str, message: str
    ) -> None:
        with pytest.raises(RenderError, match=message) as raised:
            render_text(f"ok\n{line}\n", reader, {}, source="overlay.md")

        assert str(raised.value).startswith("overlay.md:2:")

    def test_non_utf8_upstream_text_is_an_error(self) -> None:
        class Binary(PlaceholderUpstream):
            def read(self, path: str) -> bytes:
                assert path
                return b"\xff\xfe"

        with pytest.raises(RenderError, match="not UTF-8"):
            render_text("<!-- cce:include x.bin -->", Binary(), {})


class TestProcedureDirectives:
    def test_procedure_inserts_the_rendered_body(self) -> None:
        rendered = render_text("<!-- cce:procedure alpha -->", PlaceholderUpstream(), PROCEDURES)

        assert rendered == "Alpha body"

    def test_procedures_lists_every_procedure_with_headings(self) -> None:
        two = {name: PROCEDURES[name] for name in ("alpha", "beta")}

        rendered = render_text("<!-- cce:procedures heading=3 -->", PlaceholderUpstream(), two)

        assert rendered == "### Alpha\n\nAlpha body\n\n### Beta\n\nBeta body"

    def test_procedures_defaults_to_level_two_headings(self) -> None:
        one = {"alpha": PROCEDURES["alpha"]}

        assert render_text("<!-- cce:procedures -->", PlaceholderUpstream(), one).startswith("## ")

    def test_nested_procedures_render_recursively(self) -> None:
        assert render_text("<!-- cce:procedure nested -->", PlaceholderUpstream(), PROCEDURES) == (
            "Alpha body"
        )

    @pytest.mark.parametrize(
        ("line", "message"),
        [
            ("<!-- cce:procedure -->", "exactly one name"),
            ("<!-- cce:procedure ghost -->", "unknown procedure"),
            ("<!-- cce:procedure loop -->", "nest deeper"),
            ("<!-- cce:procedures heading=9 -->", "heading=1..6"),
            ("<!-- cce:procedures depth=2 -->", "heading=1..6"),
        ],
    )
    def test_rejects_bad_procedure_directives(self, line: str, message: str) -> None:
        with pytest.raises(RenderError, match=message):
            render_text(line, PlaceholderUpstream(), PROCEDURES)


class TestPackagedProcedures:
    def test_load_eight_numbered_procedures(self) -> None:
        procedures = load_procedures(parse(MANIFEST))

        assert [procedure.number for procedure in procedures] == list(range(1, 9))
        assert procedures[6].name == "publish-and-open-source-a-repository"
        assert procedures[7].name == "convert-page-to-framework-conventions"

    def test_every_description_contains_no_newline(self) -> None:
        for procedure in load_procedures(parse(MANIFEST)):
            assert "\n" not in procedure.description
            assert procedure.title

    def test_rejects_misnamed_or_gapped_files(self, tmp_path: Path) -> None:
        procedures = tmp_path / "procs"
        procedures.mkdir()
        (procedures / "01-alpha.md").write_text(
            "---\nname: alpha\ntitle: A\ndescription: d\n---\nbody\n"
        )
        (procedures / "03-gamma.md").write_text(
            "---\nname: gamma\ntitle: G\ndescription: d\n---\nbody\n"
        )
        manifest = parse(
            MANIFEST.replace('procedures = "_shared/procedures"', 'procedures = "procs"')
        )

        with pytest.raises(RenderError, match="without gaps"):
            load_procedures(manifest, tmp_path)

        (procedures / "03-gamma.md").rename(procedures / "02-delta.md")
        with pytest.raises(RenderError, match="does not match the file"):
            load_procedures(manifest, tmp_path)


class TestPlanScenario:
    @pytest.fixture
    def manifest(self) -> Manifest:
        return parse(MANIFEST)

    def scenario_plan(
        self, manifest: Manifest, reader: GitUpstream, token: str
    ) -> dict[str, PlannedFile]:
        scenario = manifest.find(token)
        assert scenario is not None
        return {file.dest: file for file in plan_scenario(scenario, manifest, reader)}

    @pytest.mark.parametrize("token", ["01", "02", "03", "04", "05", "06"])
    def test_every_scenario_renders_without_residue_or_collisions(
        self, manifest: Manifest, reader: GitUpstream, token: str
    ) -> None:
        plan = self.scenario_plan(manifest, reader, token)

        assert plan, token
        assert residual_directives(plan.values()) == []
        assert not set(plan) & reader.tracked_paths()
        assert all(dest == dest.strip("/") and ".." not in dest for dest in plan)

    def test_s01_carries_the_dated_table_and_the_good_variant(
        self, manifest: Manifest, reader: GitUpstream
    ) -> None:
        plan = self.scenario_plan(manifest, reader, "01")

        bad = plan[".github/copilot-instructions.md"].content.decode()
        assert OLD_MARKER in bad
        assert NEW_MARKER not in bad
        assert ".github/copilot-instructions.good.md" in plan

    def test_s02_embeds_all_eight_procedures_in_order(
        self, manifest: Manifest, reader: GitUpstream
    ) -> None:
        text = self.scenario_plan(manifest, reader, "02")[
            ".github/copilot-instructions.md"
        ].content.decode()
        procedures = load_procedures(manifest)

        positions = [text.index(f"## {procedure.title}") for procedure in procedures]
        assert positions == sorted(positions)
        assert all(f"procedure: {procedure.name}" in text for procedure in procedures)

    def test_s03_derives_one_skill_per_procedure_with_natural_names(
        self, manifest: Manifest, reader: GitUpstream
    ) -> None:
        plan = self.scenario_plan(manifest, reader, "03")
        procedures = load_procedures(manifest)

        for procedure in procedures:
            skill = plan[f".github/skills/{procedure.name}/SKILL.md"].content.decode()
            assert skill.startswith(f'---\nname: "{procedure.name}"\ndescription: "')
            assert skill.rstrip().endswith(f"`procedure: {procedure.name}`.")

    def test_s04_renames_and_rotates_descriptions_by_one(
        self, manifest: Manifest, reader: GitUpstream
    ) -> None:
        plan = self.scenario_plan(manifest, reader, "04")
        procedures = load_procedures(manifest)

        for index, procedure in enumerate(procedures):
            number = index + 1
            skill = plan[f".github/skills/seqf-procedure-{number}/SKILL.md"].content.decode()
            donor = procedures[(index + 1) % len(procedures)]
            assert f'description: "{donor.description}"' in skill
            assert f"`procedure: {procedure.name}`" in skill
        assert 'description: "' + procedures[7].description in (
            plan[".github/skills/seqf-procedure-7/SKILL.md"].content.decode()
        )

    def test_s05_reuses_s03_skills_and_adds_agents_and_tools(
        self, manifest: Manifest, reader: GitUpstream
    ) -> None:
        three = self.scenario_plan(manifest, reader, "03")
        five = self.scenario_plan(manifest, reader, "05")

        skills = [dest for dest in three if dest.startswith(".github/skills/")]
        assert skills and all(five[dest].content == three[dest].content for dest in skills)
        assert {".github/agents/researcher.agent.md", ".github/agents/author.agent.md"} <= set(five)
        assert five["STRUGGLE.sh"].executable
        assert five["scripts/cce-check-links.py"].executable
        assert (
            'tools: ["read", "search", "web"]'
            in five[".github/agents/researcher.agent.md"].content.decode()
        )

    def test_s06_has_the_auditor_and_no_skills_or_level_two_headings(
        self, manifest: Manifest, reader: GitUpstream
    ) -> None:
        plan = self.scenario_plan(manifest, reader, "06")

        assert ".github/agents/auditor.agent.md" in plan
        assert not any(dest.startswith(".github/skills/") for dest in plan)
        for file in plan.values():
            assert not any(line.startswith("## ") for line in file.content.decode().split("\n"))

    def test_unknown_agent_tool_is_rejected(self, tmp_path: Path, reader: GitUpstream) -> None:
        root = tmp_path / "overlays"
        (root / "_shared" / "procedures").mkdir(parents=True)
        (root / "_shared" / "agents").mkdir()
        (root / "_shared" / "procedures" / "01-alpha.md").write_text(
            '---\nname: alpha\ntitle: A\ndescription: "d"\n---\nbody\n'
        )
        (root / "_shared" / "agents" / "bad.agent.md").write_text(
            '---\nname: bad\ndescription: "d"\ntools: [read, teleport]\n---\nbody\n'
        )
        manifest = parse(MANIFEST_WITH_AGENT)

        with pytest.raises(RenderError, match="unknown tools teleport"):
            plan_scenario(manifest.scenarios[0], manifest, reader, root)

    def test_destination_tracked_upstream_is_rejected(
        self, tmp_path: Path, reader: GitUpstream
    ) -> None:
        root = tmp_path / "overlays"
        (root / "_shared" / "procedures").mkdir(parents=True)
        (root / "_shared" / "procedures" / "01-alpha.md").write_text(
            '---\nname: alpha\ntitle: A\ndescription: "d"\n---\nbody\n'
        )
        (root / "clash").mkdir()
        (root / "clash" / "README.md").write_text("ours\n")
        manifest = parse(MANIFEST_WITH_CLASH)

        with pytest.raises(RenderError, match="already exists upstream"):
            plan_scenario(manifest.scenarios[0], manifest, reader, root)


class TestHelpers:
    def test_map_dest_only_rewrites_the_top_level_github_directory(self) -> None:
        assert map_dest("github/skills/x/SKILL.md") == ".github/skills/x/SKILL.md"
        assert map_dest("STRUGGLE.sh") == "STRUGGLE.sh"
        assert map_dest("docs/github/x.md") == "docs/github/x.md"

    def test_digest_is_stable_and_content_sensitive(self) -> None:
        first = [PlannedFile("a", b"1"), PlannedFile("b", b"2", executable=True)]
        same = [PlannedFile("b", b"2", executable=True), PlannedFile("a", b"1")]

        assert digest(first) == digest(same)
        assert digest(first) != digest([PlannedFile("a", b"1"), PlannedFile("b", b"2")])

    def test_include_targets_cover_the_dated_blueprints_include(self) -> None:
        targets = include_targets()

        assert IncludeTarget("blueprints.md", "2025-10-31") in targets
        assert IncludeTarget("practices/testing.md") in targets
        assert all(not target.path.startswith("/") for target in targets)


MANIFEST = """
[source]
url = "file:///synthetic"
ref = "0123456789abcdef0123456789abcdef01234567"
procedures = "_shared/procedures"

[[scenario]]
id = "01"
slug = "01-instructions-timeless"
title = "S01"
overlay = "01-instructions-timeless"

[[scenario]]
id = "02"
slug = "02-instructions-context-cost"
title = "S02"
overlay = "02-instructions-context-cost"

[[scenario]]
id = "03"
slug = "03-skills-on-demand"
title = "S03"
overlay = "03-skills-on-demand"
skills = {}

[[scenario]]
id = "04"
slug = "04-skills-description-routing"
title = "S04"
overlay = "04-skills-description-routing"
skills = { rename = "seqf-procedure-{n}", rotate_descriptions = 1 }

[[scenario]]
id = "05"
slug = "05-agent-permissions"
title = "S05"
overlay = "05-agent-permissions"
skills = {}
agents = ["researcher", "author", "validator"]
executable = ["STRUGGLE.sh"]

[[scenario.files]]
src = "_shared/scripts/cce-check-links.py"
dest = "scripts/cce-check-links.py"
executable = true

[[scenario]]
id = "06"
slug = "06-agent-context-isolation"
title = "S06"
overlay = "06-agent-context-isolation"
agents = ["auditor"]
"""

MANIFEST_WITH_AGENT = """
[source]
url = "file:///synthetic"
ref = "0123456789abcdef0123456789abcdef01234567"

[[scenario]]
id = "01"
slug = "01-only"
title = "Only"
agents = ["bad"]
"""

MANIFEST_WITH_CLASH = """
[source]
url = "file:///synthetic"
ref = "0123456789abcdef0123456789abcdef01234567"

[[scenario]]
id = "01"
slug = "01-only"
title = "Only"
overlay = "clash"
"""
