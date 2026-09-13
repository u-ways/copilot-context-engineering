"""LLM-tier event parsing is deterministic and offline (ADR-0010)."""

import json

from tests.llm.runners import (
    RunResult,
    copilot_input_tokens,
    parse_claude_events,
    parse_copilot_events,
)


def lines(*events: object) -> list[str]:
    return [json.dumps(event) for event in events] + ["", "not json"]


class TestCopilotParsing:
    def test_collects_text_skills_and_tools(self) -> None:
        text, skills, tools = parse_copilot_events(
            lines(
                {
                    "type": "tool.execution_start",
                    "data": {"toolName": "skill", "arguments": {"skill": "alpha"}},
                },
                {"type": "tool.execution_start", "data": {"toolName": "view", "arguments": {}}},
                {
                    "type": "tool.execution_start",
                    "data": {"toolName": "skill", "arguments": {"skill": "alpha"}},
                },
                {"type": "assistant.message", "data": {"content": "done"}},
                {"type": "assistant.message", "data": {"content": "procedure: alpha"}},
            )
        )

        assert text == "done\nprocedure: alpha"
        assert skills == ["alpha"]
        assert tools == ["skill", "view"]

    def test_usage_reads_the_last_call_context(self) -> None:
        assert copilot_input_tokens({"lastCallInputTokens": 98980}) == 98980
        assert copilot_input_tokens({}) == 0
        assert copilot_input_tokens({"lastCallInputTokens": "x"}) == 0


class TestClaudeParsing:
    def test_ignores_subagent_events_and_sums_the_last_main_usage(self) -> None:
        text, skills, tools, tokens = parse_claude_events(
            lines(
                {
                    "type": "assistant",
                    "message": {
                        "content": [
                            {"type": "tool_use", "name": "Skill", "input": {"skill": "alpha"}}
                        ],
                        "usage": {
                            "input_tokens": 4,
                            "cache_creation_input_tokens": 10,
                            "cache_read_input_tokens": 20,
                        },
                    },
                },
                {
                    "type": "assistant",
                    "parent_tool_use_id": "toolu_1",
                    "message": {
                        "content": [{"type": "tool_use", "name": "Read", "input": {}}],
                        "usage": {"input_tokens": 90000},
                    },
                },
                {
                    "type": "assistant",
                    "message": {
                        "content": [{"type": "text", "text": "218"}],
                        "usage": {"input_tokens": 5, "cache_read_input_tokens": 40},
                    },
                },
                {"type": "result", "result": "218\nScope: everything."},
            )
        )

        assert text == "218\nScope: everything."
        assert skills == ["alpha"]
        assert tools == ["Skill"]
        assert tokens == 45


class TestRunResult:
    def test_structural_view_drops_the_transcript_text(self) -> None:
        result = RunResult("secret prose", ["a"], ["Read"], 12, [], "/tmp/x.jsonl")

        view = result.structural()

        assert "text" not in view
        assert view["text_length"] == 12
        assert len(view["text_sha256"]) == 64
        assert view["skills_loaded"] == ["a"]
