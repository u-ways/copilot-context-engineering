"""LLM-tier event parsing is deterministic and offline (ADR-0010)."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tests.llm.runners import (
    RunResult,
    capture,
    copilot_agent_tokens,
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

    def test_agent_metrics_split_main_from_subagents(self) -> None:
        usage = {
            "agentMetrics": {
                "main": {"modelMetrics": {"m": {"usage": {"inputTokens": 100}}}},
                "sub-1": {"modelMetrics": {"m": {"usage": {"inputTokens": 400}}}},
                "sub-2": {"modelMetrics": {"m": {"usage": {"inputTokens": 500}}}},
            }
        }

        assert copilot_agent_tokens(usage) == (100, 900)
        assert copilot_agent_tokens({}) == (0, 0)


class TestClaudeParsing:
    def test_ignores_subagent_events_and_sums_the_last_main_usage(self) -> None:
        parsed = parse_claude_events(
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

        assert parsed.text == "218\nScope: everything."
        assert parsed.skills == ["alpha"]
        assert parsed.tools == ["Skill"]
        assert parsed.input_tokens == 45
        assert parsed.main_input_tokens == 79
        assert parsed.subagent_input_tokens == 90000


class TestRunResult:
    def test_structural_view_drops_the_transcript_text(self) -> None:
        result = RunResult("secret prose", ["a"], ["Read"], 12, 12, 0, [], "/tmp/x.jsonl")

        view = result.structural()

        assert "text" not in view
        assert view["text_length"] == 12
        assert len(view["text_sha256"]) == 64
        assert view["skills_loaded"] == ["a"]


class TestCapture:
    def test_keeps_the_transcript_and_returns_stdout(self, tmp_path: Path) -> None:
        transcript = tmp_path / "t.jsonl"

        out = capture(
            [sys.executable, "-c", 'print(\'{"type": "x"}\')'],
            cwd=None,
            env={},
            transcript=transcript,
        )

        assert out.strip() == '{"type": "x"}'
        assert transcript.read_text().strip() == '{"type": "x"}'

    def test_a_silent_failure_raises_with_stderr(self, tmp_path: Path) -> None:
        with pytest.raises(RuntimeError, match="token expired"):
            capture(
                [
                    sys.executable,
                    "-c",
                    "import sys; sys.exit(sys.stderr.write('token expired') and 2)",
                ],
                cwd=None,
                env={},
                transcript=tmp_path / "t.jsonl",
            )

    def test_a_timeout_still_writes_the_partial_transcript(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import tests.llm.runners as runners

        monkeypatch.setattr(runners, "RUN_TIMEOUT_SECONDS", 1)
        transcript = tmp_path / "t.jsonl"

        with pytest.raises(subprocess.TimeoutExpired):
            capture(
                [
                    sys.executable,
                    "-c",
                    "import sys, time; print('partial'); sys.stdout.flush(); time.sleep(5)",
                ],
                cwd=None,
                env={},
                transcript=transcript,
            )

        assert transcript.read_text().startswith("partial")
