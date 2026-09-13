"""The Claude dialect moves files and rewrites tool aliases, nothing more (ADR-0010)."""

import pytest

from cce.dialect import CLAUDE_TOOLS, COPILOT_TOOLS, Dialect, claude_tools, translate
from cce.render import PlannedFile

AGENT = (
    b'---\nname: "researcher"\ndescription: "Find: things"\ntools: ["read", "search", "web"]\n'
    b'model: "gpt-5"\n---\nBody\n'
)


class TestTranslate:
    def test_copilot_dialect_is_the_identity(self) -> None:
        plan = [PlannedFile(".github/copilot-instructions.md", b"x")]

        assert translate(plan, Dialect.COPILOT) == plan

    def test_instructions_become_claude_md_keeping_suffixes(self) -> None:
        plan = [
            PlannedFile(".github/copilot-instructions.md", b"bad"),
            PlannedFile(".github/copilot-instructions.good.md", b"good"),
        ]

        assert [file.dest for file in translate(plan, Dialect.CLAUDE)] == [
            "CLAUDE.md",
            "CLAUDE.good.md",
        ]

    def test_skills_move_under_dot_claude_unchanged(self) -> None:
        plan = [PlannedFile(".github/skills/alpha/SKILL.md", b"skill")]

        [moved] = translate(plan, Dialect.CLAUDE)

        assert moved == PlannedFile(".claude/skills/alpha/SKILL.md", b"skill")

    def test_agents_are_rewritten_with_claude_tool_names_and_no_model(self) -> None:
        [agent] = translate(
            [PlannedFile(".github/agents/researcher.agent.md", AGENT)], Dialect.CLAUDE
        )

        assert agent.dest == ".claude/agents/researcher.md"
        assert agent.content == (
            b'---\nname: researcher\ndescription: "Find: things"\n'
            b"tools: Read, Grep, Glob, WebFetch, WebSearch\n---\nBody\n"
        )

    def test_other_files_pass_through(self) -> None:
        plan = [
            PlannedFile("STRUGGLE.sh", b"#!", executable=True),
            PlannedFile("scripts/x.py", b""),
        ]

        assert translate(plan, Dialect.CLAUDE) == plan


class TestAliases:
    def test_every_copilot_alias_has_a_claude_mapping(self) -> None:
        assert set(COPILOT_TOOLS) == set(CLAUDE_TOOLS)

    def test_claude_tools_preserve_order_and_deduplicate(self) -> None:
        assert claude_tools(["edit", "read", "edit"]) == ["Edit", "Write", "Read"]

    def test_unknown_alias_is_an_error(self) -> None:
        with pytest.raises(KeyError):
            claude_tools(["teleport"])
